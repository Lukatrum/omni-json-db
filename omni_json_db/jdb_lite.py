# pylint: disable=too-many-lines, unnecessary-comprehension, contextmanager-generator-missing-cleanup, consider-using-with, too-many-boolean-expressions
from __future__ import annotations
from contextlib import contextmanager
from collections import OrderedDict
from datetime import date as dt_date, datetime, timedelta
from re import compile as re_compile, match as re_match, Pattern
from os.path import exists as path_exists
from threading import RLock, get_ident
from struct import Struct
from enum import IntFlag
from unicodedata import east_asian_width
from time import perf_counter
from typing import Any, Union, Optional, Tuple, Set, List, Dict, \
                Callable, Generator, IO
#-----------------------------------------------------------------------------
from .jdb_io import JIo, KeyTable, KEY_FILE_BUF_SIZE, VAL_FILE_BUF_SIZE # THE_1ST_DATE
from .jdb_file import JFilesBase, JMemFiles, JDiskFiles
from .jdb_net import JNetFiles
from .jdb_query import QUERY_OPS, Condition, \
            sorted_by_rules, parse_group_by, grouped_by_rules, \
            match_KEY_rules, match_DATE_rules, match_VAL_rules
from .utils import FileLock, Style, JError, JKeyError, JValueError, \
                JTypeError, JDbBase, deepcopy
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
_Float64_pack = Struct("<d").pack   # sizeof() == 8 thread-safe  | <d = little-endian
_Float64_unpack = Struct("<d").unpack
_Int64_pack = Struct("q").pack      # sizeof() == 8 thread-safe
_Int64_unpack = Struct("q").unpack
_UInt64_pack = Struct("Q").pack     # sizeof() == 8 thread-safe
_UInt64_unpack = Struct("Q").unpack
_UInt64_x2_pack = Struct("QQ").pack # thread-safe
_UInt64_x2_unpack = Struct("QQ").unpack

SEP_SYM = ':::' # ignore to use re symbols (+-*?.{}()[]^$|\)
SEP_LEN = len(SEP_SYM)

_MISSING = object()

class JFlag(IntFlag):
    """Enumeration flag to control write/delete behavior in database operations."""

    REVERT  = 0x01  # allow to revert after write/delete operation
    SPLIT   = 0x02  # allow to split large row into two
    FSYNC   = 0x04  # fsync after updating

    @classmethod
    def _missing_(cls, value):
        """Allow constructing flags from a letter string: ``'r'`` = REVERT,
        ``'s'`` = SPLIT, ``'f'`` = FSYNC (e.g. ``JFlag('rs')``). Unknown
        letters are ignored.

        Args:
            value (Any): The letter string (case-insensitive).

        Returns:
            JFlag: The combined flag instance.
        """
        if isinstance(value, str):
            _value = 0
            for ch in value.lower():
                if ch == 'r':
                    _value |= JFlag.REVERT
                elif ch == 's':
                    _value |= JFlag.SPLIT
                elif ch == 'f':
                    _value |= JFlag.FSYNC

            value = _value

        return super()._missing_(value)

    def __str__(self):
        """Return a compact string showing which flags are active.

        Each position holds the flag's uppercase initial when set, or ``'_'``
        when not — e.g. ``'RS_'`` for REVERT+SPLIT, ``'___'`` for no flags.

        Returns:
            str: The flag summary string.
        """
        ret = ''
        for flag in JFlag:
            if flag in self:
                ret += flag.name[0]
            else:
                ret += '_'

        return ret

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDbKey:
    """A lightweight, read-only interface for interacting strictly with the keys of a :class:`JDbReader` instance."""
    __slots__ = ('jdb', )

    def __init__(self, jdb:JDbReader):
        """Initialize the JDbKey instance.

        Args:
            jdb (JDbReader): The parent database reader instance to bind to.
        """
        self.jdb:JDbReader = jdb

    def __repr__(self) -> str:
        """Return the string representation of the JDbKey instance.

        Returns:
            str: The object's memory address and class name.
        """
        return f'<{type(self).__name__} at {hex(id(self))}>'

    def __getitem__(self, key:Any) -> Union[dict,tuple,None]:
        """Retrieve key metadata or filter keys based on a variety of condition types.

        Args:
            key (Any): The filter criteria.
                
                - str | bool | bytes

                    - val = jdb.keys['name']

                - Condition

                    - val = jdb.keys[Query().name.startswith('A')]

                - slice | date | datetime | float | int

                    >>> matches = jdb.keys[date(2020,1,1)::r'key[0-9]'] # get date from 2020-1-1 to now key and match r'key[0-9]'
                    >>> matches = jdb.keys[:100:r'key[0-9]'] # get 1-100th row keys and match r'key[0-9]'
                    >>> matches = jdb.keys[date.today()]     # get today modified/new keys
                    >>> matches = jdb.keys[datetime.now()]   # get today new keys
                    >>> matches = jdb.keys[1:10:2]   # get 2nd - 9th and step=2 key info
                    >>> matches = jdb.keys[-10.:]    # keys written in the last 10 write sessions
                    >>> matches = jdb.keys[:]        # get all key info
                    >>> matches = jdb.keys[0]        # get 1st key info
                    >>> matches = jdb.keys[-1]       # get last key info
                    >>> matches = jdb.keys[-1.]      # get all key info which sync_id is matched

                - re.Pattern

                    >>> matches = jdb.keys[re.compile(r'key[0-9]')]

                - function(k,v)

                    >>> matches = jdb.keys[lambda k,v: k.startswith('key')]
                    >>> matches = jdb.keys[lambda k,v: v == 10]

                - function(k)

                    >>> matches = jdb.keys[lambda k: k[0] == 'k']

                - tuple | set | list | dict

                    >>> matches = jdb.keys[1, 2, 3, 'a']
                    >>> matches = jdb.keys[(1, 2, 3, 'a')]
                    >>> matches = jdb.keys[{1, 2, 3, 'a'}]
                    >>> matches = jdb.keys[[1, 2, 3, 'a']]
                    >>> matches = jdb.keys[{1:0, 2:1, 3:2, 'a':3}]

        Returns:
            dict | tuple | None: Metadata tuple if a single string is passed, a dictionary of matched keys to their metadata, or ``None`` if not found.

        """
        if isinstance(key, str):
            if key.find(SEP_SYM) >= 0 and key not in self.jdb:
                return {k:v for k,v in self.item_iter(key)}

        elif isinstance(key, (bytes, bytearray)): # pragma: no cover
            key = bytes(key) if isinstance(key, bytearray) else key
            try:
                key = key.decode('utf8')
            except (UnicodeDecodeError, ValueError):
                key = str(key)

        elif isinstance(key, Condition):
            jdb = self.jdb
            matches = {}
            with jdb.open(read_only=True) as fp:
                io, fp, key_fp = jdb.f_get_fp(fp)
                key_table = io.key_table
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                for _key,_val in jdb.find_iter(key):
                    row_id = key_table[_key] if not isinstance(key_table, KeyTable) else key_table.get(_key, -1, fp=key_fp)
                    _k, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                    old_date, new_date  = io_conv_date(days)
                    matches[_key] = (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

            return matches

        elif isinstance(key, (int, float, slice, dt_date, datetime, Pattern)) \
                or callable(key) \
                or hasattr(key, '__iter__'):
            return {k:v for k,v in self.item_iter(key)}

        jdb = self.jdb
        with jdb.open(read_only=True) as fp:
            io, fp, key_fp = jdb.f_get_fp(fp)
            key = str(key) if not isinstance(key, str) else key
            key_table = io.key_table
            row_id = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
            if io.n_records > row_id >= 0:
                _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                old_date, new_date  = io.z_conv_date(days)
                return (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

        return None

    def __setitem__(self, key:Any, val:Any) -> None:
        """Prevent item modification on a read-only key interface.

        Args:
            key (Any): The storage key or identifier.
            val (Any): The value payload to assign.

        Raises:
            AttributeError: Always raised to enforce read-only integrity.
        """
        raise AttributeError('read only')

    def __delitem__(self, key:Any):
        """Prevent item deletion from a read-only key interface.

        Args:
            key (Any): The storage key to remove.

        Raises:
            AttributeError: Always raised to enforce read-only integrity.
        """
        raise AttributeError('read only')

    def __len__(self) -> int:
        """Get the total number of records in the associated database.

        Returns:
            int: The record count.
        """
        return len(self.jdb)

    def __call__(self, keys:Optional[Any]=None, vals:Optional[Any]=None, date:Optional[Any]=None, limit:int=0, skip:int=0, **kwargs) -> Generator[str, None, None]:
        """Execute a search query returning matching keys as a generator.
        
        Args:
            keys (Any, optional): Condition for filtering keys. Defaults to ``None``.
            vals (Any, optional): Condition for filtering values. Defaults to ``None``.
            date (Any, optional): Date range filter. Defaults to ``None``.
            limit (int, optional): Maximum number of results to yield. Defaults to 0 (no limit).
            skip (int, optional): skip number of matched records, Defaults to 0.
            **kwargs: Additional filtering arguments.

        Yields:
            str: Matched key.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'key1':[0,1], 'key2':[1,2], 'key3':[3,4,5]}
            >>> print(set(jdb.keys(r'[12]$', ANY=2)))
            {'key2'}
            >>> print(set(jdb.keys(HAS=3))) # any record contains 3
            {'key3'}
        """
        jdb = self.jdb
        if keys or vals or date or kwargs:
            for key, _val in jdb.find_iter(keys=keys, vals=vals, date=date, limit=limit, skip=skip, with_value=False, with_date=False, **kwargs):
                yield key

        else:
            yield from self

    def __iter__(self) -> Generator[str, None, None]:
        """Iterate over all keys present in the database.
        
        Yields:
            str: The next key in the database.
        """
        jdb = self.jdb
        with jdb.open(read_only=True):
            yield from jdb.io.key_table

    def __contains__(self, keys:Set[str]) -> bool:
        """Check if the current key table is a superset of the provided keys.
        
        Args:
            keys (Set[str]): A set of keys to check.

        Returns:
            bool: ``True`` if all provided keys exist in the database, ``False`` otherwise.

        Example:
            >>> jdb = JDb()
            >>> jdb['user_1', 'user_2', 'user_3'] = 0
            >>> {'user_1', 'user_2'} in jdb.keys
            True
        """
        return self.is_superset(keys)

    def __eq__(self, keys:Union[set,dict,JDbReader,JDbKey]) -> bool:
        """Compare with another collection or database (delegates to the
        parent database's ``==``).

        Args:
            keys (set | dict | JDbReader | JDbKey): The target to compare
                against. A ``set`` or :class:`JDbKey` compares keys only;
                a ``dict`` or :class:`JDbReader` compares keys AND values.

        Returns:
            bool: ``True`` if equal, ``False`` otherwise.

        Example:
            >>> jdb = JDb()
            >>> jdb['user_1', 'user_2'] = 0
            >>> jdb.keys == {'user_1', 'user_2'}
            True
        """
        return self.jdb == keys

    def __sub__(self, keys:Set[str]) -> Set[str]:
        """
        Return the difference between current keys and the provided set.

        Args:
            keys (Set[str]): The keys to subtract.

        Returns:
            Set[str]: The resulting difference set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {f'user_{v+1}':v for v in range(3)}
            >>> jdb.keys - {'user_1'}
            {'user_2', 'user_3'}
        """
        return self.difference(keys)

    def __add__(self, keys:Set[str]) -> Set[str]:
        """
        Return the union of current keys and the provided set.

        Args:
            keys (Set[str]): The keys to add.

        Returns:
            Set[str]: The resulting union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.keys + {'new_user'}
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __or__(self, keys:Set[str]) -> Set[str]:
        """
        Return the union of current keys and the provided set using the bitwise OR operator.

        Args:
            keys (Set[str]): The keys to unify.

        Returns:
            Set[str]: The union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.keys | {'new_user'}
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __and__(self, keys:Set[str]) -> Set[str]:
        """
        Return the intersection of current keys and the provided set.

        Args:
            keys (Set[str]): The keys to intersect with.

        Returns:
            Set[str]: The intersection set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.keys & {'user_1', 'missing_user'}
            {'user_1'}
        """
        return self.intersection(keys)

    def __xor__(self, keys:Set[str]) -> Set[str]:
        """
        Return the symmetric difference between current keys and the provided set.

        Args:
            keys (Set[str]): The keys to compare.

        Returns:
            Set[str]: The symmetric difference set.
        
        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.keys ^ {'user_1', 'new_user'}
            {'user_2', 'new_user'}
        """
        return self.non_intersection(keys)

    def __rsub__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side subtraction (difference) operation.

        Args:
            keys (Set[str]): The baseline set.

        Returns:
            Set[str]: Elements in the given set but not in the database.
    
        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'user_1', 'new_user'} - jdb.keys
            {'new_user'}
        """
        return self.jdb.__rsub__(keys)

    def __radd__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side addition (union) operation.

        Args:
            keys (Set[str]): The set to add.

        Returns:
            Set[str]: The union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'new_user'} + jdb.keys
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __ror__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side bitwise OR (union) operation.

        Args:
            keys (Set[str]): The set to unify.

        Returns:
            Set[str]: The union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'new_user'} | jdb.keys
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __rand__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side bitwise AND (intersection) operation.

        Args:
            keys (Set[str]): The set to intersect.

        Returns:
            Set[str]: The intersection set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'user_1', 'missing_user'} & jdb.keys
            {'user_1'}
        """
        return self.intersection(keys)

    def __rxor__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side bitwise XOR (symmetric difference) operation.

        Args:
            keys (Set[str]): The set to compare.

        Returns:
            Set[str]: The symmetric difference set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'user_1', 'new_user'} ^ jdb.keys
            {'user_2', 'new_user'}
        """
        return self.symmetric_difference(keys)

    def non_joint(self, keys:Set[str]) -> Set[str]:
        """
        Return the keys from the provided set that do NOT exist in the database.

        Note: this is the reverse of :meth:`difference` — ``non_joint(x)`` is
        ``x - db.keys`` while ``difference(x)`` is ``db.keys - x``.

        Args:
            keys (Set[str]): The keys to check.

        Returns:
            Set[str]: Keys from ``keys`` that are not present in the database.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.keys.non_joint({'user_1', 'new_user'})
            {'new_user'}
        """
        return self.jdb.non_joint(keys)

    def joint(self, keys:Set[str]) -> Set[str]:
        """
        Find the intersection (joint) between this database keys and the provided set.

        Args:
            keys (Set[str]): The set of keys to check.

        Returns:
            Set[str]: The intersected set of keys.
        """
        return self.jdb.joint(keys)

    def union(self, keys:Set[str]) -> Set[str]:
        """
        Combine current database keys with the provided set.

        Args:
            keys (Set[str]): The keys to unite.

        Returns:
            Set[str]: The combined set.
        """
        return self.jdb.union(keys)

    def intersection(self, keys:Set[str]) -> Set[str]:
        """
        Calculate the intersection between database keys and the provided set.

        Args:
            keys (Set[str]): The set to intersect.

        Returns:
            Set[str]: The intersected set.
        """
        return self.jdb.intersection(keys)

    def non_intersection(self, keys:Set[str]) -> Set[str]:
        """
        Calculate the non-intersecting elements (symmetric difference).

        Args:
            keys (Set[str]): The set to compare.

        Returns:
            Set[str]: Elements in either sets but not both.
        """
        return self.jdb.non_intersection(keys)

    def symmetric_difference(self, keys:Set[str]) -> Set[str]:
        """
        Alias for non_intersection. Calculate the symmetric difference.

        Args:
            keys (Set[str]): The set to compare.

        Returns:
            Set[str]: The symmetric difference set.
        """
        return self.jdb.symmetric_difference(keys)

    def difference(self, keys:Set[str]) -> Set[str]:
        """
        Calculate the difference between database keys and the provided set.

        Args:
            keys (Set[str]): The set to subtract.

        Returns:
            Set[str]: The difference set.
        """
        return self.jdb.difference(keys)

    def is_superset(self, keys:Set[str]) -> bool:
        """
        Check if the database key table contains all keys in the provided set.

        Args:
            keys (Set[str]): The set to check.

        Returns:
            bool: True if it is a superset, False otherwise.
        """
        return self.jdb.is_superset(keys)

    def is_subset(self, keys:Set[str]) -> bool:
        """
        Check if all database keys exist within the provided set.

        Args:
            keys (Set[str]): The set to check against.

        Returns:
            bool: True if it is a subset, False otherwise.
        """
        return self.jdb.is_subset(keys)

    def is_disjoint(self, keys:Set[str]) -> bool:
        """
        Check if the database key table and the provided set have no keys in common.

        Args:
            keys (Set[str]): The set to check.

        Returns:
            bool: True if disjoint, False otherwise.
        """
        return self.jdb.is_disjoint(keys)

    def has(self, key:str) -> bool:
        """
        Check if a specific key exists in the database.

        Args:
            key (str): The key to locate.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        return self.jdb.has(key)

    def has_any(self, keys:Set[str]) -> bool:
        """
        Check if at least one key from the provided set exists in the database.

        Args:
            keys (Set[str]): The keys to search for.

        Returns:
            bool: True if any key matches, False otherwise.
        """
        return self.jdb.has_any(keys)

    def has_all(self, keys:Set[str]) -> bool:
        """
        Check if all keys from the provided set exist in the database.

        Args:
            keys (Set[str]): The keys to search for.

        Returns:
            bool: True if all keys match, False otherwise.
        """
        return self.jdb.has_all(keys)

    def item_iter(self, key:Optional[Any]=None) -> Generator[Tuple[str,tuple], None, None]:
        """
        Iterate over keys and their corresponding metadata tuples based on filter criteria.

        Args:
            key (Optional[Any], optional): Filtering criteria (slice, date, regex, etc.). Defaults to None.

                - str | bool | bytes
                    >>> matches = jdb.keys['name']
                    >>> matches = jdb.keys['child:::name']   # key 'name' inside child DB 'child'
                    >>> matches = jdb.keys[':::name']        # key 'name' inside any child DB

                - int (row index)
                    >>> matches = jdb.keys[1]        # 2nd row's key info
                    >>> matches = jdb.keys[-1]       # last row's key info

                - float (sync_id / version)
                    >>> matches = jdb.keys[-1.]      # keys written in the latest write session
                    >>> matches = jdb.keys[5.]       # keys whose version == 5

                - slice | date | datetime | Condition
                    >>> matches = jdb.keys[date(2020,1,1)::r'key[0-9]'] # get date from 2020-1-1 to now key and match r'key[0-9]'
                    >>> matches = jdb.keys[:100:r'key[0-9]'] # get 1-100th row keys and match r'key[0-9]'
                    >>> matches = jdb.keys[date.today()]     # get today modified/new keys
                    >>> matches = jdb.keys[datetime.now()]   # get today new keys
                    >>> matches = jdb.keys[1:10:2]   # get 2nd - 9th and step=2 key info
                    >>> matches = jdb.keys[-10.:]    # keys written in the last 10 write sessions
                    >>> matches = jdb.keys[:]        # get all key info
                    >>> matches = jdb.keys[Query().name.endswith('e')]

                - re.Pattern
                    >>> matches = jdb.keys[re.compile(r'key[0-9]')]

                - function(k,v)
                    >>> matches = jdb.keys[lambda k,v: k.startswith('key')]
                    >>> matches = jdb.keys[lambda k,v: v == 10]

                - function(k)
                    >>> matches = jdb.keys[lambda k: k[0] == 'k']

                - tuple | set | list | dict
                    >>> matches = jdb.keys[1, 2, 3, 'a']
                    >>> matches = jdb.keys[(1, 2, 3, 'a')]
                    >>> matches = jdb.keys[{1, 2, 3, 'a'}]
                    >>> matches = jdb.keys[[1, 2, 3, 'a']]
                    >>> matches = jdb.keys[{1:0, 2:1, 3:2, 'a':3}]

                - None: get all items
                    >>> all_keys = dict(jdb.keys.item_iter(None))

        Yields:
            (str, tuple):

                - [0] key
                - [1] tuple

                    - [0] row_id:int
                    - [1] file_id:int
                    - [2] offset:int
                    - [3] row_size:int
                    - [4] val_size:int
                    - [5] version:int
                    - [6] days:int - combine modified date + created date
                    - [7] modified date: str (eg. '2000-01-01')
                    - [8] created date: str  (eg. '2000-01-01')
        """
        if isinstance(key, Pattern):
            is_matched = key.search
            k_arg_cnt = 1

        elif callable(key):
            is_matched = key
            k_arg_cnt = is_matched.__code__.co_argcount
            if not 2 >= k_arg_cnt >= 1:
                raise TypeError(f'invalid function {k_arg_cnt}')

        else:
            is_matched = None
            k_arg_cnt = 0
            key = slice(0,None) if key is None else key

        jdb = self.jdb

        with jdb.open(read_only=True) as fp:
            io, fp, key_fp = jdb.f_get_fp(fp)
            key_table = io.key_table
            if isinstance(key, str):
                idx = key.find(SEP_SYM)
                if idx < 0:
                    row_id = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
                    if io.n_records > row_id >= 0:
                        _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                        old_date, new_date  = io.z_conv_date(days)
                        yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                    return

                childs = set(io.groups).union(jdb.childs)
                if childs:
                    jdb_name, jdb_key = key[:idx], key[idx+SEP_LEN:]
                    f_get_child = jdb.f_get_child
                    if not jdb_name:
                        for jdb_name in childs:
                            child = f_get_child(fp, jdb_name)
                            if isinstance(child, JDbReader):
                                for _key,_info in child.keys.item_iter(jdb_key):
                                    yield jdb_name+SEP_SYM+_key, _info
                    else:
                        child = f_get_child(fp, jdb_name)
                        if isinstance(child, JDbReader):
                            for _key,_info in child.keys.item_iter(jdb_key):
                                yield jdb_name+SEP_SYM+_key, _info

                return

            if isinstance(key, int) and not isinstance(key, bool):
                n_records = io.n_records
                row_id = (n_records + key) if key < 0 else key
                if n_records > row_id >= 0:
                    _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                    old_date, new_date = io.z_conv_date(days)
                    yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            if isinstance(key, float):
                sync_id = int(key)
                sync_id = (io.sync_id + sync_id) if sync_id < 0 else sync_id
                if not (sync_id >= io.sync_id or sync_id < 0):
                    io_conv_date = io.z_conv_date
                    row_id = 0
                    for (_key, file_id, offset, size, vsize, ver, days) in io.KEY_iter(key_fp, row_id, io.n_records):
                        if ver == sync_id:
                            old_date, new_date = io_conv_date(days)
                            yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))
                        row_id += 1

                return

            if isinstance(key, (slice, dt_date, datetime, Condition)):
                yield from jdb.f_key_iter(fp, key)
                return

            if k_arg_cnt > 0:
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                if k_arg_cnt == 2:
                    row_id = 0
                    for (_key, file_id, offset, size, vsize, ver, days) in io.KEY_iter(key_fp, row_id, io.n_records):
                        old_date, new_date = io_conv_date(days)
                        val = (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))
                        if is_matched(_key, val):
                            yield _key, val
                        row_id += 1

                elif k_arg_cnt == 1:
                    for _key,row_id in io.key_table.items():
                        if io.n_records > row_id >= 0 and is_matched(_key):
                            key_fp = fp[-1]
                            _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                            old_date, new_date = io_conv_date(days)
                            yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            if isinstance(key, (bytes, bytearray)): # pragma: no cover
                key = bytes(key) if isinstance(key, bytearray) else key
                try:
                    key = key.decode('utf8')
                except (UnicodeDecodeError, ValueError):
                    key = str(key)

            elif hasattr(key, '__iter__'):
                done = set()
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                has_childs = len(io.groups) > 0 or len(jdb.childs) > 0
                for _key in key:
                    if isinstance(_key, (int, float)): # pragma: no cover
                        row_id = int(_key)
                        if row_id < 0:
                            row_id = io.n_records + row_id

                        if io.n_records > row_id >= 0:
                            key_fp = fp[-1]
                            _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                            old_date, new_date = io_conv_date(days)
                            yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                        continue

                    _key = str(_key)
                    if _key not in done: # pragma: no cover
                        done.add(_key)
                        row_id = key_table[_key] if not isinstance(key_table, KeyTable) else key_table.get(_key, -1, fp=key_fp)
                        if row_id < 0:
                            if has_childs and _key.find(SEP_SYM) >= 0: # pragma: no cover
                                for kk,_info in self.item_iter(_key):
                                    yield kk,_info

                            continue

                        if row_id < io.n_records:
                            _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                            old_date, new_date = io_conv_date(days)
                            yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            # bytes | bytearray | bool
            key = str(key)
            row_id = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
            if io.n_records > row_id >= 0:
                _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                old_date, new_date = io.z_conv_date(days)
                yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

    def items(self) -> Generator[Tuple[str,tuple], None, None]:
        """
        Iterate over all keys and their metadata tuples.

        Yields:
            (str, tuple):
            
                - [0] key
                - [1] tuple

                    - [0] row_id:int
                    - [1] file_id:int
                    - [2] offset:int
                    - [3] row_size:int
                    - [4] val_size:int
                    - [5] version:int
                    - [6] days:int - combine modified date + created date
                    - [7] modified date: str (eg. '2000-01-01')
                    - [8] created date: str  (eg. '2000-01-01')
        """
        yield from self.item_iter()

    def values(self) -> Generator[tuple, None, None]:
        """
        Iterate over all metadata tuples without their keys.

        Yields:
            tuple: The metadata tuple for each key.
                
                - [0] row_id:int
                - [1] file_id:int
                - [2] offset:int
                - [3] row_size:int
                - [4] val_size:int
                - [5] version:int
                - [6] days:int - combine modified date + created date
                - [7] modified date: str (eg. '2000-01-01')
                - [8] created date: str  (eg. '2000-01-01')
        """
        for _key,val in self.item_iter():
            yield val

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDbReader(JDbBase):
    """Read-only base class for JDb operations.

    Handles data retrieval, filtering, and caching logic without allowing 
    data modification. Designed for safe, concurrent read operations.
    """
    __slots__ = ('files_obj', 'lock', '_cache_limit', '_cache', 'file_lock', 'keys',
                'io', 'fsize', 'fp_table', 'th_table', 'childs', 'safe_line', 'chg_keys',
                'write_hook', 'max_wsize', 'flags')

    def __init__(self,\
                KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None]=None,\
                data_type:Union[str,int,None]='J+S',\
                zip_type:Union[str,int,None]='no',\
                key_limit:Union[str,int,None]='no',\
                cache_limit:int=0,\
                max_file_size:Optional[int]=None,\
                min_value_size:Optional[int]=None,\
                index_size:Optional[int]=None,\
                reserved_rate:Optional[float]=None,\
                api_ver:Optional[int]=None,\
                write_hook:Optional[Callable[[str,Any],bool]]=None,\
                max_wsize:Optional[int]=None,\
                flags:Optional[JFlag]=None, **kwargs):
        """
        Initialize the JDbReader instance with specific backend storage and formatting options.

        Args:
            KEY_file (Union[str, bytearray, JFilesBase, JDbReader, None], optional): File path, memory buffer, or network host.
                
                - None | bytearray
                    - JMemFiles() or JMemFiles(bytearray)
                - str
                    - ''                  = use JMemFiles() in memory
                    - '127.0.0.1:8001'    = use JNetFiles(('127.0.0.1', 8001))
                    - 'database/test.jdb' = use JDiskFiles(database/test.jdb)
                - JDbReader               = use JDb.files_obj
                - JMemFiles | JNetFiles | JDiskFiles

            data_type (Union[str, int, None], optional): Serialization format
                
                - "J+J" | KEY=JSON    | VAL=JSON
                - "J+M" | KEY=JSON    | VAL=Marshal
                - "J+P" | KEY=JSON    | VAL=Pickle
                - "J+S" | KEY=JSON    | VAL=msgpack (default)
                - "J+Y" | KEY=JSON    | VAL=YAML
                - "S+J" | KEY=Msgpack | VAL=JSON
                - "S+M" | KEY=Msgpack | VAL=Marshal
                - "S+P" | KEY=Msgpack | VAL=Pickle
                - "S+S" | KEY=Msgpack | VAL=msgpack
                - "S+Y" | KEY=Msgpack | VAL=YAML
                - "L+J" | KEY=split   | VAL=Json
                - "M+M" | KEY=Marshal | VAL=Marshal

            zip_type (Union[str, int, None], optional): Compression algorithm to use.
                
                - "no" = no compression for VAL. (default)
                - "gz" = gzip compression(9) for VAL.
                - "bz" = bz2 compression(9) for VAL.
                - "xz" = lzma compression for VAL.
                - "zs" = zstandard compression(22) for VAL.
                - "br" = brotli compression(6) for VAL.
                - "z1" = zstandard compression(6) for VAL.
                - "z2" = zstandard compression(11) for VAL.
                - "lz" = lz4 compression(0) for VAL.

            key_limit (Union[str, int, None], optional): Key table limitation constraint.
                
                - "no" = use DictKeyTable. (default). 
                - "bt" = use BTreeKeyTable.
                - "l0"-"l5" = use LiteKeyTable.
                - +ve: use PartialKeyTable.

            cache_limit (int, optional): In-memory object cache limit.
                
                - -1 = unlimited cache.
                - 0 =  no cache. (default)
                - +ve = with cache.

            max_file_size (Optional[int], optional): Max size of a single data part.
            min_value_size (Optional[int], optional): Minimum byte size for value padding.
            index_size (Optional[int], optional): Fixed byte size for the key index records.
            reserved_rate (Optional[float], optional): Expansion buffer rate for data rows.
            api_ver (Optional[int], optional): API structural version limit.
                
                - 0 = oldest version.
                - None = latest version. (default)

            write_hook (Optional[Callable[[str, Any], bool]], optional): Callback triggered before writing.
            max_wsize (Optional[int], optional): Search window for dead lines. Defaults to 4.
            flags (Optional[JFlag], optional): Enum flags for modifying revert/split behavior.
            **kwargs: Extra arguments passed to internal components.
        
        Raises:
            TypeError: Raised if provided arguments are of the incorrect type.
        """
        JDbKey_obj = kwargs.pop('JDbKey_obj', None)

        if isinstance(KEY_file, JDbReader):
            jdb = KEY_file
            jio = jdb.io
            if index_size is None:
                index_size = jio.index_size

            if reserved_rate is None:
                reserved_rate = jio.reserved_rate

            if write_hook is None:
                write_hook = jdb.write_hook

            if max_wsize is None:
                max_wsize = jdb.max_wsize

            if flags is None:
                flags = jdb.flags

            # override
            api_ver = jio.api_ver
            zip_type = jio._zip_type
            data_type = jio._data_type
            files_obj = jdb.files_obj.copy()

        elif isinstance(KEY_file, str):
            if not KEY_file: # pragma: no cover
                files_obj = JMemFiles(None, **kwargs)
            elif re_match(r'^([12]?\d\d?[:.]){4}(?<=:)\d{1,5}$', KEY_file): # pragma: no cover
                server_ip, server_port = KEY_file.split(':')
                server_port = int(server_port)
                if not 65535 >= server_port > 0 or not all(255 >= int(vv) >= 0 for vv in server_ip.split('.')): # pragma: no cover
                    raise TypeError
                files_obj = JNetFiles((server_ip, server_port))
            else:
                files_obj = JDiskFiles(KEY_file)

        elif KEY_file is None or isinstance(KEY_file, bytearray):
            # KEY_file=bytearray(), VAL_table={}, LCK_file=bytearray()
            files_obj = JMemFiles(KEY_file, **kwargs)

        elif isinstance(KEY_file, JFilesBase):
            files_obj = KEY_file.copy()

        else:
            raise TypeError

        if not isinstance(files_obj, JFilesBase):
            raise TypeError

        if write_hook is not None:
            if not callable(write_hook):
                raise TypeError('write_hook must be function')

            if write_hook.__code__.co_argcount != 2:
                raise TypeError('write_hook must have 2 args (key, val)')

        if max_wsize is not None:
            if not isinstance(max_wsize, int):
                raise TypeError('max_wsize must be integer')

        self.files_obj:JFilesBase = files_obj
        self.file_lock:FileLock = FileLock(rlock=files_obj.LCK_rlock, \
                                        wlock=files_obj.LCK_wlock, \
                                        unlock=files_obj.LCK_unlock, \
                                        close=files_obj.LCK_close, \
                                        remove=files_obj.LCK_remove)
        self.lock = RLock() # solve iter issue [cannot use Lock]
        self.fsize = self.safe_line = 0
        self.childs:Dict[str,JDbReader] = {}
        self.fp_table:Dict[int,dict] = {}
        self.th_table:Dict[int,int] = {}
        self.chg_keys:Set = set()
        self._cache:Dict[str,Any] = OrderedDict()
        self._cache_limit = cache_limit
        self.keys:JDbKey = JDbKey(self) if JDbKey_obj is None else JDbKey_obj
        self.write_hook:Callable[[str,Any],bool] = write_hook
        self.flags:JFlag = JFlag.REVERT if flags is None else JFlag(flags)
        self.max_wsize:int = 4 if max_wsize is None else max_wsize
        self.io:JIo = JIo(
                files_obj=files_obj,
                data_type=data_type,
                zip_type=zip_type,
                key_limit=key_limit,
                api_ver=api_ver,
                index_size=index_size,
                min_value_size=min_value_size,
                max_file_size=max_file_size,
                reserved_rate=reserved_rate)

    def __del__(self):
        """
        Destructor to ensure all internal file descriptors and locks are safely released upon garbage collection.
        """
        with self.lock:
            fp_table = self.fp_table
            if fp_table: # pragma: no cover
                for _ident,fp_dict in fp_table.items():
                    for fp in fp_dict.values():
                        if fp is not None:
                            fp.close()

                    fp_dict.clear()

                fp_table.clear()

            self.file_lock.release()

    def __repr__(self) -> str:
        """
        Return the string representation showing core parameters of the JDbReader instance.

        Returns:
            str: Descriptive text about the DB instance state and pointers.
        """
        io = self.io
        return f'<{type(self).__name__}[v{io.api_ver}|{io.data_type_str}|{io.zip_type_str}|{io.key_limit_str}|{io.index_size:3d}|{"H" if self.write_hook else "_"}{"c" if self._cache_limit > 0 else "C" if self._cache_limit < 0 else "_"}{str(self.flags)}] at {hex(id(self))}>'

    def __len__(self) -> int:
        """
        Get the current number of active records by re-reading the KEY
        file header from storage (in-memory counters are left untouched).

        Returns:
            int: Total active record count.
        """
        with self.KEY_fopen() as key_fp:
            io = self.io
            sync_id =io.sync_id
            swap_id =io.swap_id
            remv_id =io.remv_id
            io.read_header(key_fp)
            io.sync_id = sync_id
            io.swap_id = swap_id
            io.remv_id = remv_id

            return io.n_records

    def __iter__(self) -> Generator[str, None, None]:
        """
        Iterate over the keys present in the database.

        Yields:
            str: A database key.
        """
        with self.open(read_only=True):
            yield from self.io.key_table

    def __getitem__(self, key:Set[str]) -> Union[Dict[str,Any],Any]:
        """
        Retrieve data by key or filter data dynamically.

        Args:
            key (Set[str]): The identifier or condition mapping to locate specific values.
                
                - str | int | float | bool | bytes
                    >>> val = jdb['name']

                - Condition
                    >>> user = Query()
                    >>> data = jdb[user.name == 'Alice']

                - slice | date | datetime
                    >>> data = jdb[1:10:2]
                    >>> data = jdb[-10.:]
                    >>> data = jdb[:]
                    >>> data = jdb[dt.date(2020,1,1)::r'key[0-9]']
                    >>> data = jdb[:100:r'key[0-9]']

                - function(k,v)
                    >>> data = jdb[lambda k,v: k.startswith('key')]
                    >>> data = jdb[lambda k,v: v == 10]

                - function(k)
                    >>> data = jdb[lambda k: k[0] == 'k']

                - tuple | set | list | dict
                    >>> data = jdb[1, 2, 3, 'a']
                    >>> data = jdb[(1, 2, 3, 'a')]
                    >>> data = jdb[{1, 2, 3, 'a'}]
                    >>> data = jdb[[1, 2, 3, 'a']]
                    >>> data = jdb[{1:0, 2:1, 3:2, 'a':3}]

        Returns:
            Union[Dict[str, Any], Any]: The target value, or a dictionary of matched keys and values.
                
                - dict: multiple keys with values
                - Any: target key's value        
        """
        if isinstance(key, str):
            if key.find(SEP_SYM) >= 0:
                with self.open(read_only=True):
                    if key not in self.io.key_table:
                        return {k:v for k,v in self.item_iter(key)}

        elif isinstance(key, (bytes, bytearray)): # pragma: no cover
            key = bytes(key) if isinstance(key, bytearray) else key
            try:
                key = key.decode('utf8')
            except (UnicodeDecodeError, ValueError):
                key = str(key)

        elif isinstance(key, Condition):
            return {k:v for k,v in self.find_iter(key, with_value=True, with_date=False)}

        elif isinstance(key, (slice, dt_date, datetime, Pattern)) \
                or callable(key) \
                or hasattr(key, '__iter__'):

            return {k:v for k,v in self.item_iter(key)}

        # str | bytes | int | float | bool
        with self.open(read_only=True) as fp:
            return self.f_read(fp, key, copy=True, default_val=_MISSING)

    def __contains__(self, keys:Union[str,Set[str],Condition]) -> bool:
        """
        Check if the current key table is a superset of the provided keys.

        Args:
            keys (str | Set[str] | Condition): A set of keys to check.

        Returns:
            bool: True if all provided keys exist in the database, False otherwise.

        Example:
            >>> jdb = JDb()
            >>> jdb['user_1', 'user_2', 'user_3'] = 0
            >>> {'user_1', 'user_2'} in jdb
            True
            >>> 'user_1' in jdb
            True
            >>> (Query().age > 999) in jdb
            False
        """
        if isinstance(keys, Condition):
            return next(self.find_iter(keys, limit=1), None) is not None

        return self.is_superset(keys)

    def __eq__(self, jdb:Union[set,dict,JDbReader,JDbKey]) -> bool:
        """
        Compare the current keys/dict with another collection or database.

        Args:
            jdb (Union[set, dict, JDbReader, JDbKey]): The target to compare against.
                
                - JDb | dict: compare KEYs and VALs
                - set: compare KEYs only

        Returns:
            bool: True if the keys are identical, False otherwise.

        Example:
            >>> jdb = JDb()
            >>> jdb['user_1', 'user_2'] = 0
            >>> jdb == {'user_1', 'user_2'}
            True    
        """
        if isinstance(jdb, JDbReader):
            if jdb is self:
                return True

            with self.open(read_only=True) as fp:
                with jdb.open(read_only=True) as ref_fp:
                    if jdb.files_obj == self.files_obj: # must after jdb.open()
                        return True

                    if jdb.io.n_records != self.io.n_records:
                        return False

                    f_read = self.f_read
                    jdb_read = jdb.f_read
                    jdb_key_table = jdb.io.key_table
                    jdb_key_fp = ref_fp[-1]
                    for key,row in self.io.sorted_key_table_items():
                        ref_row = jdb_key_table[key] if not isinstance(jdb_key_table, KeyTable) else jdb_key_table.get(key, -1, fp=jdb_key_fp)
                        if ref_row < 0 or f_read(fp, key, row=row, copy=False) != jdb_read(ref_fp, key, row=ref_row, copy=False):
                            return False

        elif isinstance(jdb, JDbKey):
            jdb = jdb.jdb
            if jdb is not self:
                with self.open(read_only=True):
                    with jdb.open(read_only=True):
                        return jdb.io.key_table  == self.io.key_table

        elif isinstance(jdb, dict):
            with self.open(read_only=True) as fp:
                if self.io.n_records != len(jdb):
                    return False

                f_read = self.f_read
                for key,row in self.io.sorted_key_table_items():
                    if key not in jdb or f_read(fp, key, row=row, copy=False) != jdb[key]:
                        return False


        elif isinstance(jdb, set):
            with self.open(read_only=True):
                io = self.io
                if io.n_records != len(jdb):
                    return False

                key_table = io.key_table
                for key in jdb:
                    key = str(key) if not isinstance(key, str) else key
                    if key not in key_table:
                        return False

                return True

        else:
            return False

        return True

    def __sub__(self, keys:Set[str]) -> Set[str]:
        """
        Return the difference between current keys and the provided set.

        Args:
            keys (Set[str]): The keys to subtract.

        Returns:
            Set[str]: The resulting difference set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {f'user_{v+1}':v for v in range(3)}
            >>> jdb - {'user_1'}
            {'user_2', 'user_3'}
        """
        return self.difference(keys)

    def __add__(self, keys:Set[str]) -> Set[str]:
        """
        Return the union of current keys and the provided set.

        Args:
            keys (Set[str]): The keys to add.

        Returns:
            Set[str]: The resulting union set.
        
        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb + {'new_user'}
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __or__(self, keys:Set[str]) -> Set[str]:
        """
        Return the union of current keys and the provided set using the bitwise OR operator.

        Args:
            keys (Set[str]): The keys to unify.

        Returns:
            Set[str]: The union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb | {'new_user'}
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __and__(self, keys:Set[str]) -> Set[str]:
        """
        Return the intersection of current keys and the provided set.

        Args:
            keys (Set[str]): The keys to intersect with.

        Returns:
            Set[str]: The intersection set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb & {'user_1', 'missing_user'}
            {'user_1'}
        """
        return self.intersection(keys)

    def __xor__(self, keys:Set[str]) -> Set[str]:
        """
        Return the symmetric difference between current keys and the provided set.

        Args:
            keys (Set[str]): The keys to compare.

        Returns:
            Set[str]: The symmetric difference set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb ^ {'user_1', 'new_user'}
            {'user_2', 'new_user'}
        """
        return self.non_intersection(keys)

    def __rsub__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side subtraction (difference) operation.

        Args:
            keys (Set[str]): The baseline set.

        Returns:
            Set[str]: Elements in the given set but not in the database.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'user_1', 'new_user'} - jdb
            {'new_user'}
        """
        if isinstance(keys, str):
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif hasattr(keys, '__iter__'):
            if not keys:
                return set()

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            return keys.difference(self.io.key_table)

    def __radd__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side addition (union) operation.

        Args:
            keys (Set[str]): The set to add.

        Returns:
            Set[str]: The union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'new_user'} + jdb
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __ror__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side bitwise OR (union) operation.

        Args:
            keys (Set[str]): The set to unify.

        Returns:
            Set[str]: The union set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'new_user'} | jdb
            {'user_1', 'user_2', 'new_user'}
        """
        return self.union(keys)

    def __rand__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side bitwise AND (intersection) operation.

        Args:
            keys (Set[str]): The set to intersect.

        Returns:
            Set[str]: The intersection set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'user_1', 'missing_user'} & jdb
            {'user_1'}
        """
        return self.intersection(keys)

    def __rxor__(self, keys:Set[str]) -> Set[str]:
        """
        Right-side bitwise XOR (symmetric difference) operation.

        Args:
            keys (Set[str]): The set to compare.

        Returns:
            Set[str]: The symmetric difference set.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> {'user_1', 'new_user'} ^ jdb
            {'user_2', 'new_user'}
        """
        return self.symmetric_difference(keys)

    def f_slice(self, fp_dict:dict, key:Union[dt_date,datetime,Condition,slice]) -> tuple:
        """Normalize a slice / date / datetime / Condition filter into row and
        version iteration bounds for :meth:`f_key_iter`.

        A ``date`` becomes a one-day range on the modified date; a
        ``datetime`` becomes a one-day range on the created date; a
        ``Condition`` becomes a full-range slice with the condition as the
        key rule. Slice ``start``/``stop`` may be ints (row ids), floats or
        strs (version bounds), or dates; a str/Condition ``step`` becomes a
        key-matching rule.

        Args:
            fp_dict (dict): The thread's open file-pointer table.
            key (Union[dt_date, datetime, Condition, slice]): The filter.

        Returns:
            tuple: ``(row_slice, max_ver, min_ver, max_date, min_date,
            key_rules, chk_new_date)`` — the row range to scan, version
            bounds, date bounds, an optional key rule, and whether the date
            bounds apply to the modified (``True``) or created (``False``)
            date.
        """
        chk_new_date = True
        if isinstance(key, datetime): # before dt_date
            key = slice(key, key+timedelta(days=1)) # created date
            chk_new_date = False

        elif isinstance(key, dt_date):
            key = slice(key, key+timedelta(days=1)) # modified date

        elif isinstance(key, Condition):
            key = slice(0, self.io.n_records, key)

        if not isinstance(key, slice):
            raise JTypeError

        io = self.io
        n_records = io.n_records
        n_lines = io.n_lines
        key_table = io.key_table
        sync_id = io.sync_id

        _start = key.start
        _stop = key.stop
        _step = key.step
        chk_ver = chk_days = False
        key_rules = None

        min_days = None # THE_1ST_DATE
        max_days = None # dt_date.today() + timedelta(days=1)
        min_ver = 0
        max_ver = sync_id
        if _step is None:
            _step = 1
        else:
            if isinstance(_step, int):
                pass

            elif isinstance(_step, float): # pragma: no cover
                _step = int(_step)

            elif isinstance(_step, str):
                key_rules = {'$re': _step}
                _step = 1
            elif isinstance(_step, Condition):
                key_rules = _step
                _step = 1
            else:
                raise JTypeError(key)

            if _step == 0:
                raise JValueError('step must not be zero')

        if _start is None:
            _start = 0
        else:
            if isinstance(_start, int):
                if _start < 0:
                    _start = max(0, n_records + _start)

                if _start >= n_records:
                    _start = n_records - 1

                _start = max(0, _start)

            elif isinstance(_start, (str, float)):
                chk_ver = True

            elif isinstance(_start, datetime): # before dt_date
                chk_days = True
                chk_new_date = False
                min_days = _start.date()

            elif isinstance(_start, dt_date):
                chk_days = True
                min_days = _start

            else:
                raise JTypeError(key)

        if _stop is None:
            if _step is None or _step > 0:
                _stop = n_records
            else:
                _stop = -1 if n_records > 0 else 0

        else:
            if isinstance(_stop, int):
                if _stop < 0:
                    _stop  = max(0, n_records + _stop)

                _stop = max(0, min(n_records, _stop))

            elif isinstance(_stop, (float, str)):
                chk_ver = True

            elif isinstance(_stop, datetime): # before dt_date
                chk_days = True
                chk_new_date = False
                max_days = _stop.date()

            elif isinstance(_stop, dt_date):
                chk_days = True
                max_days = _stop

            else:
                raise JTypeError(key)

        if chk_ver:
            _start = 0
            _stop  = n_lines

            if key.start is None:
                pass

            elif isinstance(key.start, str):
                io, fp_dict, key_fp = self.f_get_fp(fp_dict)
                _row_id = key_table[key.start] if not isinstance(key_table, KeyTable) else key_table.get(key.start, -1, fp=key_fp)
                if n_records > _row_id >= 0:
                    _k, _f, _o, _s, _vs, ver, _d = io.read_key(key_fp, _row_id)
                    min_ver = ver
                else:
                    min_ver = 0

            else:
                min_ver = (sync_id + int(key.start)) if key.start < 0 else int(key.start)

            if key.stop is None:
                pass

            elif isinstance(key.stop, str):
                io, fp_dict, key_fp = self.f_get_fp(fp_dict)
                _row_id = key_table[key.stop] if not isinstance(key_table, KeyTable) else key_table.get(key.stop, -1, fp=key_fp)
                if n_records > _row_id >= 0:
                    _k, _f, _o, _s, _vs, ver, _d = io.read_key(key_fp, _row_id)
                    max_ver = ver
                else:
                    max_ver = sync_id

            else:
                max_ver = (sync_id + int(key.stop)) if key.stop < 0 else int(key.stop)


        elif chk_days:
            _start = 0
            _stop  = n_records
            _step = 1

        return slice(_start, _stop, _step), max_ver, min_ver, max_days, min_days, key_rules, chk_new_date

    def f_open(self, read_only:bool=True) -> Dict[int,IO]:
        """Manually acquire the file lock and open the KEY file for the current thread.

        This is the non-context-manager counterpart of :meth:`open`; every
        ``f_open()`` call must be paired with a matching :meth:`f_close`.
        Re-entrant calls from the same thread are counted and only the last
        :meth:`f_close` actually closes the files. The key table is reloaded
        from disk if it is out of date.

        Args:
            read_only (bool, optional): If ``True``, acquire a shared read lock;
                otherwise acquire an exclusive write lock. Defaults to ``True``.

        Returns:
            Dict[int, IO]: The thread's file-pointer table. Index ``-1`` maps to
            the KEY file pointer; VAL file pointers are added on demand.
        """
        with self.lock:
            file_lock = self.file_lock
            ident = file_lock.acquire(read_only=read_only) # raise RuntimeError if fail
            key_fp = None
            chg_keys = self.chg_keys
            _cache = self._cache
            files_obj = self.files_obj
            fp_table = self.fp_table
            th_table = self.th_table
            io = self.io
            fp_table[ident] = fp_dict = fp_table.get(ident, {-1:None})
            th_table[ident] = th_table.get(ident, 0) + 1
            try:
                try:
                    if file_lock.get_count(ident) > 1: # pragma: no cover
                        if not read_only:
                            for _id in list(fp_dict):
                                fp = fp_dict[_id]
                                if fp is not None and not fp.writable():
                                    fp.close()
                                    fp_dict.pop(_id, None)

                        key_fp = fp_dict.get(-1, None)
                        return fp_dict

                    data_type = io._data_type
                    if read_only:
                        if data_type != 0 and io.is_updated():
                            if files_obj.KEY_size() == io.file_size:
                                self.safe_line = io.n_records
                                chg_keys.clear()
                                return fp_dict

                        is_latest = False # pragma: no cover
                    else:
                        io.update_days()
                        is_latest = data_type != 0 and files_obj.KEY_size() == io.file_size

                    key_fp = fp_dict.get(-1, None)
                    if key_fp is not None: # pragma: no cover
                        key_fp.seek(0)
                    else:
                        key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

                    io.read_header(key_fp)
                    if not io.is_updated() or not is_latest:
                        io.load_keys(key_fp, force=data_type==0)
                        _cache.clear()
                        self.fsize = io.file_size

                except FileNotFoundError:
                    if key_fp is not None:
                        key_fp.close()

                    io, key_fp = self._init_KEY()
                    fp_dict[-1] = key_fp

                self.safe_line = self.io.n_records
                chg_keys.clear()
                return fp_dict

            except: # pragma: no cover
                io = self.io
                _cache.clear()
                chg_keys.clear()
                self.fsize = io.file_size = 0

                for fp in fp_dict.values():
                    if fp is not None:
                        fp.close()

                fp_dict.clear()
                fp_table.pop(ident, None)
                file_lock.release()
                raise

        return None

    def f_close(self):
        """Release one :meth:`f_open` acquisition for the current thread.

        In write mode, the KEY file header is flushed to disk. When the
        thread's last nested acquisition is released, all of its file
        pointers are closed (with an ``fsync`` first when ``JFlag.FSYNC``
        is set and data was modified) and the file lock is released.
        """
        with self.lock:
            ident = get_ident()
            chg_keys = self.chg_keys
            _cache = self._cache
            file_lock = self.file_lock
            files_obj = self.files_obj
            fp_table = self.fp_table
            fp_dict = fp_table.get(ident, None)
            if fp_dict is None: # pragma: no cover
                self.th_table.pop(ident, 0)
                return

            th_table = self.th_table
            th_cnt = th_table.get(ident, 0) - 1
            try:
                io = self.io
                if not io.is_updated():
                    if file_lock.mode == 'w':
                        key_fp = fp_dict.get(-1, None)
                        if key_fp is None: # pragma: no cover
                            try:
                                fp_dict[-1] = key_fp = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

                            except FileNotFoundError:
                                io, key_fp = self._init_KEY()
                                fp_dict[-1] = key_fp
                        else:
                            key_fp.seek(0)

                        if _cache: # pragma: no cover
                            if not io.key_table:
                                _cache.clear()
                            else:
                                for kk in set(_cache).difference(io.key_table):
                                    _cache.pop(kk, 0)

                        self.fsize = io.write_header(key_fp)

                    # read mode
                    elif io.file_size == 0 or io.n_records != len(io.key_table): # pragma: no cover
                        _cache.clear()
                        io.key_table.clear()
                        io.file_table.clear()
                        self.fsize = io.n_records = io.n_lines = io._n_records = io._n_lines = io.file_size = 0

            finally:
                if th_cnt <= 0:
                    flags = self.flags
                    chg_keys.clear()
                    is_dirty = file_lock.mode == 'w'
                    for fp in fp_dict.values():
                        if fp is not None:
                            if is_dirty and JFlag.FSYNC in flags: # pragma: no cover
                                files_obj.fsync(fp.fileno())
                            fp.close()

                    fp_dict.clear()
                    fp_table.pop(ident, None)
                    th_table.pop(ident, 0)
                else:
                    th_table[ident] = th_cnt

                file_lock.release()

    @contextmanager
    def open(self, read_only:bool=True, no_raise:bool=False) -> Generator[Dict[int,IO], None, None]:
        """Context manager giving thread-safe read/write access to the
        database files. Nested calls from the same thread are counted; files
        are closed and the lock released when the outermost call exits.

        Args:
            read_only (bool, optional): Request a shared read lock instead of
                an exclusive write lock. Defaults to ``True``.
            no_raise (bool, optional): If ``True``, errors are suppressed and,
                on an unexpected error, the KEY file is re-initialized
                (all records discarded) instead of raising.
                Defaults to ``False``.

        Yields:
            Dict[int, IO]: The thread's file-pointer table. Index ``-1`` maps
            to the KEY file pointer; VAL file pointers are added on demand.
        """
        if not self.lock.acquire(): # 70% faster vs with self.lock
            raise RuntimeError

        try:
            file_lock = self.file_lock
            ident = file_lock.acquire(read_only=read_only) # raise RuntimeError if fail
            fsize = sync_id = -1
            key_fp = None
            is_error = False
            chg_keys = self.chg_keys
            _cache = self._cache
            files_obj = self.files_obj
            fp_table = self.fp_table
            th_table = self.th_table
            fp_table[ident] = fp_dict = fp_table.get(ident, {-1:None})
            th_table[ident] = th_cnt = th_table.get(ident, 0) + 1
            io = self.io
            try:
                try:
                    if file_lock.get_count(ident) > 1:
                        if not read_only:
                            for _id in list(fp_dict):
                                fp = fp_dict[_id]
                                if fp is not None and not fp.writable():
                                    fp.close()
                                    fp_dict.pop(_id, None)

                        key_fp = fp_dict.get(-1, None)
                        sync_id = io.sync_id
                        fsize = io.file_size
                        yield fp_dict
                        return

                    data_type = io._data_type
                    if read_only:
                        if data_type != 0 and io.is_updated():
                            if files_obj.KEY_size() == io.file_size:
                                self.safe_line = io.n_records
                                chg_keys.clear()
                                sync_id = io.sync_id
                                fsize = io.file_size
                                yield fp_dict
                                return

                        is_latest = False
                    else:
                        io.update_days()
                        is_latest = data_type != 0 and files_obj.KEY_size() == io.file_size

                    key_fp = fp_dict.get(-1, None)
                    if key_fp is not None: # pragma: no cover
                        key_fp.seek(0)
                    else:
                        key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

                    io.read_header(key_fp)
                    if not io.is_updated() or not is_latest:
                        io.load_keys(key_fp, force=data_type==0)
                        _cache.clear()
                        self.fsize = io.file_size

                except FileNotFoundError:
                    if key_fp is not None:
                        key_fp.close()

                    io, key_fp = self._init_KEY()
                    fp_dict[-1] = key_fp

                self.safe_line = io.n_records
                chg_keys.clear()
                sync_id = io.sync_id
                fsize = io.file_size
                yield fp_dict

            except JKeyError as e: # pragma: no cover
                if not no_raise:
                    raise KeyError from e

            except JValueError as e: # pragma: no cover
                if not no_raise:
                    raise ValueError from e

            except JTypeError as e: # pragma: no cover
                if not no_raise:
                    raise TypeError from e

            except JError as e: # pragma: no cover
                if not no_raise:
                    raise RuntimeError from e

            except Exception as e:
                is_error = True
                io = self.io
                if file_lock.mode == 'w':
                    try:
                        key_fp = fp_dict.pop(-1, None)
                        if key_fp is not None:
                            if io.file_size > 0 and io.n_lines > 0: # pragma: no cover
                                self.fsize = io.write_header(key_fp)
                            key_fp.close()

                    except Exception as e1: # pragma: no cover
                        print(e, e1)

                if no_raise or sync_id != io.sync_id or fsize != io.file_size:
                    io.key_table.clear()
                    io.file_table.clear()
                    _cache.clear()
                    chg_keys.clear()
                    self.fsize = io.n_records = io.n_lines = io._n_records = io._n_lines = io.file_size = 0

                for fp in fp_dict.values():
                    if fp is not None:
                        fp.close()

                fp_dict.clear()
                if no_raise:
                    is_error = False
                    print(Style(f'\n{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io._key_limit}|Exception:{e}: try to reset KEY header', yellow=1))
                    io, key_fp = self._init_KEY()
                    fp_dict[-1] = key_fp
                    chg_keys.clear()
                    self.safe_line = io.n_records
                    sync_id = io.sync_id
                    fsize = io.file_size
                    yield fp_dict

                else:
                    raise

            finally:
                try:
                    io = self.io
                    if not io.is_updated():
                        if file_lock.mode == 'w':
                            if not is_error:
                                key_fp = fp_dict.get(-1, None)
                                if key_fp is None: # pragma: no cover
                                    fp_dict[-1] = key_fp = files_obj.KEY_open('ab+', buffering=KEY_FILE_BUF_SIZE)

                                if _cache and io.remv_id != io._remv_id:
                                    for kk in set(_cache).difference(io.key_table):
                                        _cache.pop(kk, 0)

                                self.fsize = io.write_header(key_fp)

                        elif files_obj.KEY_size() != io.file_size: # read mode
                            _cache.clear()
                            io.key_table.clear()
                            io.file_table.clear()
                            self.fsize = io.n_records = io.n_lines = io._n_records = io._n_lines = io.file_size = 0

                finally:
                    th_cnt -= 1
                    if th_cnt <= 0:
                        flags = self.flags
                        chg_keys.clear()
                        is_dirty = file_lock.mode == 'w' and (fsize != io.file_size or sync_id != io.sync_id)
                        for fp in fp_dict.values():
                            if fp is not None:
                                if is_dirty and JFlag.FSYNC in flags:
                                    files_obj.fsync(fp.fileno())
                                fp.close()

                        fp_dict.clear()
                        fp_table.pop(ident, None)
                        th_table.pop(ident, 0)
                    else:
                        th_table[ident] = th_cnt

                    file_lock.release()

        finally:
            self.lock.release()

    @contextmanager
    def KEY_fopen(self, read_only:bool=True) -> Generator[IO, None, None]:
        """
        Context manager that locks the database and opens the raw KEY file,
        creating a fresh one when it does not exist. Unlike :meth:`open`, it
        does not load the key table.

        Args:
            read_only (bool, optional): Acquire a shared read lock instead of
                an exclusive write lock. Defaults to ``True``.

        Yields:
            IO: The open KEY file pointer.
        """
        if not self.lock.acquire():
            raise RuntimeError

        try:
            file_lock = self.file_lock
            file_lock.acquire(read_only=read_only) # raise RuntimeError if fail
            key_fp = None
            files_obj = self.files_obj
            try:
                key_fp = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)
                yield key_fp

            except FileNotFoundError:
                _io, key_fp = self._init_KEY()
                yield key_fp

            finally:
                if key_fp is not None:
                    key_fp.close()

                file_lock.release()

        finally:
            self.lock.release()

    @property
    def dir_name(self) -> str:
        """Get the parent directory path of the primary DB file.

        Returns:
            str: Directory path.
        """
        return self.files_obj.get_folder()

    @property
    def file_name(self) -> str:
        """Get the file name of the primary DB KEY file.

        Returns:
            str: File name.
        """
        return self.files_obj.get_name()

    @property
    def path(self) -> str:
        """
        Get the full system path to the primary DB file.

        Returns:
            str: Absolute or relative file path.
        """
        return self.files_obj.get_path()

    @property
    def key_table(self) -> Dict[str,int]:
        """
        Access the in-memory key table mapping each key to its row id in the
        KEY file (``-1`` for missing keys on tables with a default).

        Returns:
            Dict[str, int]: ``{key: row_id}``.
        """
        return self.io.key_table

    @property
    def file_table(self) -> Dict[int,int]:
        """Get the VAL data file usage table.

        Returns:
            Dict[int, int]: ``{val_file_id: used_bytes}``.
        """
        return self.io.file_table

    @property
    def n_records(self) -> int:
        """Get the count of valid active records currently indexed.

        Returns:
            int: The total number of active keys.
        """
        return self.io.n_records

    @property
    def n_lines(self) -> int:
        """Get the total number of rows in the KEY file, including
        dead/history rows kept for revert support.

        Returns:
            int: Total row count (active + dead).
        """
        return self.io.n_lines

    @property
    def index_size(self) -> int:
        """Get the fixed byte size of one KEY file index row.

        Returns:
            int: Bytes per index row.
        """
        return self.io.index_size

    @property
    def reserved_rate(self) -> float:
        """Get the extra space ratio reserved when writing a value row, so the
        row can grow in place without relocation (e.g. ``0.2`` reserves 20%).

        Returns:
            float: Reserved expansion ratio.
        """
        return self.io.reserved_rate

    @property
    def min_value_size(self) -> int:
        """Get the minimum number of bytes allocated for a stored value row.

        Returns:
            int: Minimum value row size in bytes.
        """
        return self.io.min_value_size

    @property
    def sync_id(self) -> int:
        """Get the write-session counter. It is incremented once per write
        transaction, and each record stores the ``sync_id`` of the session
        that last modified it (its version).

        Returns:
            int: Current write-session counter.
        """
        return self.io.sync_id

    @property
    def swap_id(self) -> int:
        """Get the compaction counter. It is incremented whenever the KEY file
        is rearranged (rows swapped/compacted), letting readers detect that
        row positions may have changed.

        Returns:
            int: Current compaction counter.
        """
        return self.io.swap_id

    @property
    def remv_id(self) -> int:
        """Get the deletion counter, incremented whenever records are deleted.

        Returns:
            int: Current deletion counter.
        """
        return self.io.remv_id

    @property
    def api_ver(self) -> int:
        """Get the on-disk format version of the database file.

        Returns:
            int: File format (API) version.
        """
        return self.io.api_ver

    @property
    def data_type(self) -> str:
        """Get the serialization format code as ``'<KEY>+<VAL>'``
        (e.g. ``'J+S'`` = JSON keys + msgpack values).

        Returns:
            str: Serialization format code.
        """
        return self.io.data_type_str

    @property
    def zip_type(self) -> str:
        """Get the value compression code (e.g. ``'no'``, ``'gz'``, ``'zs'``).

        Returns:
            str: Compression algorithm code.
        """
        return self.io.zip_type_str

    @property
    def key_limit(self) -> str:
        """Get the key-table implementation code (e.g. ``'no'`` = plain dict,
        ``'bt'`` = B-tree, ``'l0'``-``'l5'`` = lite table, integer = partial table).

        Returns:
            str: Key-table type code.
        """
        return self.io.key_limit_str

    @key_limit.setter
    def key_limit(self, value:Union[int,str]):
        """Switch the key-table implementation (thread-safe).

        Args:
            value (Union[int, str]): New key-table type — a code string
                (``'no'``, ``'bt'``, ``'l0'``-``'l5'``) or an integer size
                for a partial key table.
        """
        with self.lock:
            self.io.key_limit = value

    @property
    def cache_limit(self) -> int:
        """
        Get the maximum number of items allowed in the read cache.

        Returns:
            int: The cache limit (0 implies off, -1 implies unlimited).
        """
        return self._cache_limit

    @cache_limit.setter
    def cache_limit(self, value:int):
        """
        Set the maximum read cache limit, flushing the cache if the limit is reduced.

        Args:
            value (int): The new cache limit.
        """
        with self.lock:
            old_value = self._cache_limit
            if value < 0:
                self._cache_limit = -1
            elif value > 0:
                if value < old_value: # pragma: no cover
                    self._cache.clear()
                self._cache_limit = value
            else:  #value == 0
                self._cache.clear()
                self._cache_limit = value

    def len_(self) -> int:
        """Read the active record count directly from the KEY file header,
        without acquiring locks or loading the key table. Returns ``0`` when
        the KEY file does not exist.

        Returns:
            int: Active record count, or ``0`` if the file is missing.
        """
        key_fp = None
        try:
            key_fp = self.files_obj.KEY_open('rb', buffering=KEY_FILE_BUF_SIZE)
            io = self.io.read_header(key_fp)
            return io.n_records

        except FileNotFoundError: # pragma: no cover
            pass

        finally:
            if key_fp is not None:
                key_fp.close()

        return 0

    def create_jdb(self, KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None]) -> JDbReader: # pragma: no cover
        """Create a new instance that reuses this database's configuration
        (data_type, zip_type, key_limit, cache_limit, sizes, etc.) but points
        at a different storage target.

        Args:
            KEY_file (Union[str, bytearray, JFilesBase, JDbReader, None]): Target
                file path, memory buffer, files object, or source database —
                same forms accepted by :meth:`__init__`.

        Returns:
            JDbReader: The new instance.
        """
        jio = self.io
        return JDbReader(KEY_file=KEY_file,
                    data_type=jio._data_type,
                    zip_type=jio._zip_type,
                    reserved_rate=jio.reserved_rate,
                    cache_limit=self._cache_limit,
                    key_limit=jio._key_limit,
                    min_value_size=jio.min_value_size,
                    max_file_size=jio.max_file_size,
                    index_size=jio.index_size)

    def can_lock(self) -> bool:
        """Check whether file locking works on the underlying storage
        (some filesystems, e.g. certain network mounts, do not support it).

        Returns:
            bool: ``True`` if file locks can be acquired, ``False`` otherwise.
        """
        if not self.lock.acquire():
            return False

        try:
            return self.file_lock.can_lock()

        except: # pragma: no cover
            return False

        finally:
            self.lock.release()

    def non_joint(self, keys:Set[str]) -> Set[str]:
        """Return the keys from the provided collection that do NOT exist in
        this database.

        Note: this is the reverse of :meth:`difference` — ``non_joint(x)`` is
        ``x - db.keys`` while ``difference(x)`` is ``db.keys - x``.

        Args:
            keys (Set[str]): Keys to check. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            Set[str]: Keys from ``keys`` that are not present in the database.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.non_joint({'user_1', 'new_user'})
            {'new_user'}
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            if jdb is self:
                return set()

            with self.open(read_only=True):
                with jdb.open(read_only=True):
                    if jdb.files_obj == self.files_obj:
                        return set()

                    keys = set(jdb.io.key_table)
                    if keys:
                        for key in self.io.key_table:
                            if key in keys:
                                keys.remove(key)
                                if not keys:
                                    return keys

                    return keys

        elif hasattr(keys, '__iter__'):
            keys = {key if isinstance(key, str) else str(key) for key in keys}
        else: # pragma: no cover
            keys = {str(keys)}

        if keys:
            with self.open(read_only=True):
                for key in self.io.key_table:
                    if key not in keys: continue
                    keys.remove(key)
                    if not keys:
                        return keys

        return keys

    def joint(self, keys:Set[str]) -> Set[str]:
        """Alias for :meth:`intersection` — keys present in both the database
        and the provided collection.

        Args:
            keys (Set[str]): Keys to intersect with.

        Returns:
            Set[str]: The common keys.
        """
        return self.intersection(keys)

    def union(self, keys:Set[str]) -> Set[str]:
        """Return all database keys combined with the provided collection.

        Args:
            keys (Set[str]): Keys to add. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            Set[str]: The union of the database keys and ``keys``.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.union({'new_user'})
            {'user_1', 'user_2', 'new_user'}
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            with self.open(read_only=True):
                key_table = set(self.io.key_table)
                if jdb is self or jdb.files_obj == self.files_obj:
                    return key_table

                with jdb.open(read_only=True):
                    return key_table.union(jdb.io.key_table)

        elif hasattr(keys, '__iter__'):
            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            key_table = set(self.io.key_table)
            if not keys:
                return key_table

            return keys.union(key_table)

    def intersection(self, keys:Set[str]) -> Set[str]:
        """Return the keys present in both the database and the provided
        collection.

        Args:
            keys (Set[str]): Keys to intersect with. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            Set[str]: The common keys.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.intersection({'user_1', 'missing'})
            {'user_1'}
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            with self.open(read_only=True):
                key_table = set(self.io.key_table)
                if jdb is self or not key_table or jdb.files_obj == self.files_obj:
                    return key_table

                with jdb.open(read_only=True):
                    return key_table.intersection(jdb.io.key_table)

        elif hasattr(keys, '__iter__'):
            if not keys:
                return set()

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            key_table = set(self.io.key_table)
            if not keys or not key_table:
                return set()

            return keys.intersection(key_table)

    def non_intersection(self, keys:Set[str]) -> Set[str]:
        """Return the symmetric difference — keys that exist in either the
        database or the provided collection, but not in both.

        Args:
            keys (Set[str]): Keys to compare. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            Set[str]: Keys unique to one side.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.non_intersection({'user_1', 'new_user'})
            {'user_2', 'new_user'}
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            with self.open(read_only=True):
                if jdb is self or jdb.files_obj == self.files_obj:
                    return set()

                key_table = set(self.io.key_table)
                with jdb.open(read_only=True):
                    return key_table.symmetric_difference(jdb.io.key_table)

        elif hasattr(keys, '__iter__'): # pragma: no cover
            if not keys:
                with self.open(read_only=True):
                    return set(self.io.key_table)

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            return keys.symmetric_difference(self.key_table)

    def symmetric_difference(self, keys:Set[str]) -> Set[str]:
        """Alias for :meth:`non_intersection` (matches the :class:`set` API name).

        Args:
            keys (Set[str]): Keys to compare.

        Returns:
            Set[str]: The symmetric difference.
        """
        return self.non_intersection(keys)

    def difference(self, keys:Set[str]) -> Set[str]:
        """Return the database keys that are NOT in the provided collection
        (``db.keys - keys``).

        Args:
            keys (Set[str]): Keys to subtract. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            Set[str]: Database keys not present in ``keys``.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'user_1':1, 'user_2':2}
            >>> jdb.difference({'user_1'})
            {'user_2'}
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            with self.open(read_only=True):
                if jdb is self or jdb.files_obj == self.files_obj:
                    return set()

                with jdb.open(read_only=True):
                    return set(self.io.key_table).difference(jdb.io.key_table)

        elif hasattr(keys, '__iter__'):
            if not keys:
                with self.open(read_only=True):
                    return set(self.io.key_table)

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            return set(self.io.key_table).difference(keys)

    def is_superset(self, keys:Set[str]) -> bool:
        """Check whether every key in the provided collection exists in the
        database (the database is a superset of ``keys``).

        Args:
            keys (Set[str]): Keys to check. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            bool: ``True`` if all of ``keys`` exist in the database.
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            if jdb is self:
                return True

            with self.open(read_only=True):
                with jdb.open(read_only=True):
                    if jdb.files_obj == self.files_obj:
                        return True

                    key_table = self.io.key_table
                    for key in jdb.io.key_table:
                        if key not in key_table:
                            return False

                    return True

        elif hasattr(keys, '__iter__'):
            pass

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            key_table = self.io.key_table
            for key in keys:
                key = str(key) if not isinstance(key, str) else key
                if key not in key_table:
                    return False

        return True

    def is_subset(self, keys:Set[str]) -> bool:
        """Check whether every database key exists in the provided collection
        (the database is a subset of ``keys``).

        Args:
            keys (Set[str]): The larger collection to check against. May also
                be another :class:`JDbReader`/:class:`JDbKey` or any iterable.

        Returns:
            bool: ``True`` if all database keys exist in ``keys``.
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            if jdb is self:
                return True

            with self.open(read_only=True):
                with jdb.open(read_only=True):
                    if jdb.files_obj == self.files_obj:
                        return True

                    io = self.io
                    if io.n_records > jdb.io.n_records:
                        return False

                    key_table = io.key_table
                    ref_key_table = jdb.io.key_table
                    for key in key_table:
                        if key not in ref_key_table:
                            return False

                    return True

        elif hasattr(keys, '__iter__'):
            pass

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            io = self.io
            key_table = io.key_table
            #n_records = io.n_records
            if io.n_records > len(keys):
                return False

            keys = {key if isinstance(key, str) else str(key) for key in keys}
            for key in key_table:
                if key not in keys:
                    return False

        return True

    def is_disjoint(self, keys:Set[str]) -> bool:
        """Check whether the database and the provided collection share no keys.

        Args:
            keys (Set[str]): Keys to check. May also be another
                :class:`JDbReader`/:class:`JDbKey`, a string, or any iterable.

        Returns:
            bool: ``True`` if no key is shared, ``False`` otherwise.
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            if jdb is self:
                return False

            with self.open(read_only=True):
                with jdb.open(read_only=True):
                    if jdb.files_obj == self.files_obj:
                        return False

                    io = self.io
                    jio = jdb.io
                    min_key_table, max_key_table = (jio.key_table, io.key_table) if io.n_records > jio.n_records \
                                                else (io.key_table, jio.key_table)
                    for key in min_key_table:
                        if key in max_key_table:
                            return False

                    return True

        elif hasattr(keys, '__iter__'):
            pass

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            io = self.io
            keys = {key if isinstance(key, str) else str(key) for key in keys}
            min_key_table, max_key_table = (keys, io.key_table) if io.n_records > len(keys) \
                                                else (io.key_table, keys)
            for key in min_key_table:
                if key in max_key_table:
                    return False

        return True

    def has(self, key:str) -> bool:
        """
        Check if a specific key exists in the database.

        Args:
            key (str): The key to locate.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        if not self.lock.acquire():
            return False

        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        try:
            io = self.io
            if io.is_updated():
                return key in io.key_table

        finally:
            self.lock.release()

        with self.open(read_only=True):
            return key in self.io.key_table

    def has_(self, key:str) -> bool:
        """Fast key-existence check that prefers the in-memory key table and
        avoids file locks when possible. The result may be slightly stale if
        another process modified the database; use :meth:`has` for an
        up-to-date answer.

        Args:
            key (str): The key to look up.

        Returns:
            bool: ``True`` if the key exists, ``False`` otherwise.
        """
        io = self.io
        if io.key_table:
            return key in io.key_table

        if not self.lock.acquire():
            return False

        try:
            if self.io.is_updated():
                return False

        finally:
            self.lock.release()

        with self.open(read_only=True):
            return key in self.io.key_table

    def has_any(self, keys:Set[str]) -> bool:
        """
        Check if at least one key from the provided set exists in the database.

        Args:
            keys (Set[str]): The keys to search for.

        Returns:
            bool: True if any key matches, False otherwise.
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            if jdb is self:
                return True

            with self.open(read_only=True):
                with jdb.open(read_only=True):
                    if jdb.files_obj == self.files_obj:
                        return True

                    key_table = self.io.key_table
                    for key in jdb.io.key_table:
                        if key in key_table:
                            return True

                return False

        elif hasattr(keys, '__iter__'):
            if not keys:
                return False

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else:  # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            key_table = self.io.key_table
            return any(key in key_table for key in keys)

    def has_all(self, keys:Set[str]) -> bool:
        """
        Check if all keys from the provided set exist in the database.

        Args:
            keys (Set[str]): The keys to search for.

        Returns:
            bool: True if all keys match, False otherwise.
        """
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, (JDbReader, JDbKey)):
            jdb = keys.jdb if isinstance(keys, JDbKey) else keys
            if jdb is self:
                return True

            with self.open(read_only=True):
                with jdb.open(read_only=True):
                    if jdb.files_obj == self.files_obj:
                        return True

                    key_table = self.io.key_table
                    for key in jdb.io.key_table:
                        if key not in key_table:
                            return False

                return True

        elif hasattr(keys, '__iter__'):
            if not keys:
                return False

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else:  # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            key_table = self.io.key_table
            return all(key in key_table for key in keys)

    def info(self, prefix:str='', key:str=''):
        """
        Print formatted database statistics and configuration details to the console.

        Args:
            prefix (str, optional): Indentation prefix string for nested groups. Defaults to ''.
            key (str, optional): Title or designated key name representing this branch. Defaults to ''.
        """
        if prefix == key == '':
            with self.open(read_only=True) as fp:
                io = self.io
                files_obj = self.files_obj
                path = files_obj.get_KEY()
                info = f'[KEY] {path}'
                info += f'\n[JFiles] {files_obj}'
                info += f'\n[Config] min_value_size:{io.min_value_size} max_file_size:{io.max_file_size/(2**20):,.1f}MB reserved:{io.reserved_rate*100.:.2f}% max_wsize:{self.max_wsize}'
                # info += f'\n[LOCK] {self.file_lock}'

                api_ver = io.api_ver
                zip_str = io.zip_type_str
                type_str = io.data_type_str
                limit_str = io.key_limit_str
                data_size = ''
                size = self.fsize
                if size > 128: # pragma: no cover
                    if size >= (2**30):
                        data_size = f' k:{size/(2**30):,.1f}GB |'
                    elif size >= (2**20):
                        data_size = f' k:{size/(2**20):,.1f}MB |'
                    elif size > 0:
                        data_size = f' k:{size/1024:,.1f}KB |'

                if io.file_table: # pragma: no cover
                    size = sum(io.file_table.values())
                    if size > 0:
                        if size >= (2**30):
                            data_size += f' v:{size/(2**30):,.1f}GB/{len(io.file_table)} |'
                        elif size >= (2**20):
                            data_size += f' v:{size/(2**20):,.1f}MB/{len(io.file_table)} |'
                        elif size > 0:
                            data_size += f' v:{size/1024:,.1f}KB/{len(io.file_table)} |'

                        info += f'\n[VAL] {",".join(f"<{k}>:{v * 100 / io.max_file_size:5.2f}%" for k,v in io.file_table.items())}'

                info += '\n' + '='*80
                print(info)
                print(f'[v{api_ver}|{type_str}|{zip_str}|{limit_str}|{io.index_size:3d}|{"H" if self.write_hook else "_"}{"c" if self._cache_limit > 0 else "C" if self._cache_limit < 0 else "_"}{str(self.flags)}] {files_obj.get_name()} | {io.n_records:,}+{io.n_lines-io.n_records:,} |{data_size} s:{io.sync_id}/{io.swap_id}/{io.remv_id}')

                for _key in sorted(io.groups): # pragma: no cover
                    jdb = self.f_get_group(fp, _key)
                    if isinstance(jdb, JDbReader):
                        jdb.info(prefix + '  ', key=_key)

                for _key,jdb in sorted(self.childs.items()): # pragma: no cover
                    if not isinstance(jdb, JDbReader): continue
                    if _key not in io.key_table: continue
                    jdb.info(prefix + SEP_SYM, key=_key)

        else:
            with self.KEY_fopen('r') as key_fp:
                io = self.io.read_header(key_fp)
                api_ver = io.api_ver
                zip_str = io.zip_type_str
                type_str = io.data_type_str
                limit_str = io.key_limit_str
                data_size = ''
                size = key_fp.seek(0,2)
                if size > 128: # pragma: no cover
                    if size >= (2**30):
                        data_size = f' k:{size/(2**30):,.1f}GB |'
                    elif size >= (2**20):
                        data_size = f' k:{size/(2**20):,.1f}MB |'
                    elif size > 0:
                        data_size = f' k:{size/1024:,.1f}KB |'

                io.update_file_table()
                if io.file_table: # pragma: no cover
                    size = sum(list(io.file_table.values()))
                    if size > 0:
                        if size >= (2**30):
                            data_size += f' v:{size/(2**30):,.1f}GB/{len(io.file_table)} |'
                        elif size >= (2**20):
                            data_size += f' v:{size/(2**20):,.1f}MB/{len(io.file_table)} |'
                        elif size > 0:
                            data_size += f' v:{size/1024:,.1f}KB/{len(io.file_table)} |'

                print(prefix+f'[v{api_ver}|{type_str}|{zip_str}|{limit_str}|{io.index_size:3d}|{"H" if self.write_hook else "_"}{"c" if self._cache_limit > 0 else "C" if self._cache_limit < 0 else "_"}{str(self.flags)}] {key} | {self.files_obj.get_name()} | {io.n_records:,}+{io.n_lines-io.n_records:,} |{data_size} s:{io.sync_id}/{io.swap_id}/{io.remv_id} ')
                for _key in sorted(io.groups): # pragma: no cover
                    jdb = self.f_get_group(key_fp, _key)
                    if isinstance(jdb, JDbReader):
                        jdb.info(prefix + '  ', key=_key)

                for _key,jdb in sorted(self.childs.items()): # pragma: no cover
                    if not isinstance(jdb, JDbReader): continue
                    if _key not in io.key_table: continue
                    jdb.info(prefix + SEP_SYM, key=_key)

    def values(self) -> Generator[Any, None, None]:
        """Iterate over all stored values in row order.

        Note: cached values are yielded by reference (no deep copy); do not
        mutate them in place.

        Yields:
            Any: Each record's deserialized value.
        """
        with self.open(read_only=True) as fp:
            for _key,val in self.f_items(fp):
                yield val

    def items(self, reverse:bool=False) -> Generator[Tuple[str,Any], None, None]:
        """Iterate over all ``(key, value)`` pairs in row order.

        Note: cached values are yielded by reference (no deep copy); do not
        mutate them in place.

        Args:
            reverse (bool, optional): Iterate rows in reverse order.
                Defaults to ``False``.

        Yields:
            (str, Any): Each record's key and deserialized value.
        """
        with self.open(read_only=True) as fp:
            for key,val in self.f_items(fp, reverse=reverse):
                yield key, val

    def item_iter(self, key:Optional[Any]=None) -> Generator[Tuple[str,Any]]:
        """Iterate over ``(key, value)`` pairs matching the given filter.

        Args:
            key (Optional[Any], optional): Filter criteria. ``None`` iterates
                all records. Defaults to ``None``. Accepted forms:

                - re.Pattern: keys matching the pattern
                - function(k) | function(k,v): keys/pairs the function accepts
                - str: an exact key (``'child:::key'`` reaches into a child DB)
                - int: a row index (negative counts from the end)
                - float: a write-session id (version); negative is relative
                  to the current ``sync_id``
                - bytes | bytearray | bool: converted to ``str`` and looked up
                - slice | date | datetime | Condition: see :meth:`JDbKey.item_iter`
                - list | tuple | set | dict: multiple keys

        Yields:
            Tuple[str, Any]: The matched key and its deserialized value.
        """

        if isinstance(key, Pattern):
            is_matched = key.search
            k_arg_cnt = 1

        elif callable(key):
            is_matched = key
            k_arg_cnt = is_matched.__code__.co_argcount
            if not 2 >= k_arg_cnt >= 1:
                raise TypeError(f'invalid function {k_arg_cnt}')

        else:
            is_matched = None
            k_arg_cnt = 0
            if key is None:
                key = slice(0, None)

        with self.open(read_only=True) as fp:
            io, fp, key_fp = self.f_get_fp(fp)
            key_table = io.key_table
            if isinstance(key, str):
                idx = key.find(SEP_SYM)
                if idx < 0:
                    row_id = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
                    if row_id >= 0:
                        yield key, self.f_read(fp, key, row=row_id, copy=False)

                    return

                childs = set(io.groups).union(self.childs)
                if not childs:
                    return

                jdb_name, jdb_key = key[:idx], key[idx+SEP_LEN:]
                f_get_child = self.f_get_child
                f_read = self.f_read
                if not jdb_name:
                    for jdb_name in childs:
                        child = f_get_child(fp, jdb_name)
                        if isinstance(child, JDbReader):
                            for _key,_val in child.item_iter(jdb_key):
                                yield jdb_name+SEP_SYM+_key, _val
                else:
                    child = f_get_child(fp, jdb_name)
                    if isinstance(child, JDbReader):
                        for _key,_val in child.item_iter(jdb_key):
                            yield jdb_name+SEP_SYM+_key, _val

                return

            if isinstance(key, int) and not isinstance(key, bool):
                n_records = io.n_records
                row_id = (n_records + key) if key < 0 else key
                if n_records > row_id >= 0:
                    _key, _file_id, _offset, _size, _vsize, _ver, _days = io.read_key(key_fp, row_id)
                    yield _key, self.f_read(fp, _key, row=row_id, copy=False)

                return

            if isinstance(key, float):
                sync_id = int(key)
                sync_id = (io.sync_id + sync_id) if sync_id < 0 else sync_id
                if not (sync_id >= io.sync_id or sync_id < 0):
                    row_id = 0
                    for (_key, _file_id, _offset, _size, _vsize, _ver, _days) in io.KEY_iter(key_fp, row_id, io.n_records):
                        if _ver == sync_id:
                            yield _key, self.f_read(fp, _key, row=row_id, copy=False)
                        row_id += 1

                return

            if isinstance(key, Condition):
                yield from self.find_iter(key, with_value=True, with_date=False)
                return

            if isinstance(key, (slice, dt_date, datetime)):
                _cache = self._cache
                cache_limit = self._cache_limit
                _update_cache = self._update_cache
                _decode_row = self._decode_row
                f_get_val_fp = self.f_get_val_fp
                n_records = io.n_records
                io_read_value = io.read_value
                for _key, (row_id, file_id, offset, size, vsize, _ver, _days, _mdate, _cdate) in self.f_key_iter(fp, key):
                    if not n_records > row_id >= 0: continue
                    if _cache and _key in _cache:
                        val = _cache.get(_key, None)
                    else:
                        if size == 0:
                            val = _decode_row(file_id, offset, _key, vsize)
                        else:
                            val_fp, __i, __o  = f_get_val_fp(fp, file_id)
                            val = io_read_value(val_fp, offset, size, vsize)

                        if cache_limit != 0:
                            _update_cache(_key, val, copy=False)

                    yield _key, val

                return

            if k_arg_cnt > 0:
                f_read = self.f_read
                if k_arg_cnt == 2:
                    for _key,row_id in key_table.items():
                        val = f_read(fp, _key, row=row_id, copy=False)
                        if is_matched(_key, val):
                            yield _key, val

                elif k_arg_cnt == 1:
                    for _key,row_id in key_table.items():
                        if is_matched(_key):
                            yield _key, f_read(fp, _key, row=row_id, copy=False)

                return

            if isinstance(key, (bytes, bytearray)): # pragma: no cover
                key = bytes(key) if isinstance(key, bytearray) else key
                try:
                    key = key.decode('utf8')
                except (UnicodeDecodeError, ValueError):
                    key = str(key)

            elif hasattr(key, '__iter__'):
                done = set()
                f_read = self.f_read
                has_childs = len(io.groups) > 0 or len(self.childs) > 0
                for _key in key:
                    _key = str(_key)
                    if _key not in done:
                        done.add(_key)

                        row_id = key_table[_key] if not isinstance(key_table, KeyTable) else key_table.get(_key, -1, fp=key_fp)
                        if row_id < 0:
                            if has_childs and _key.find(SEP_SYM) >= 0:
                                for kk,vv in self.item_iter(_key): # pragma: no cover
                                    yield kk,vv

                            continue

                        val = f_read(fp, _key, row=row_id, copy=False)
                        yield _key, val

                return

            # bytes | bytearray | bool
            key = str(key) if not isinstance(key, str) else key
            row_id = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
            if row_id >= 0:
                yield key, self.f_read(fp, key, row=row_id, copy=False)

    def find_iter(self, keys:Optional[Any]=None, vals:Optional[Dict[str,Any]]=None, date:Optional[Any]=None, limit:int=0, skip:int=0, with_value:bool=False, with_date:bool=False, stats:Dict[str,float]=None, reverse:bool=False, **kwargs) -> Generator[Tuple[str,Any], None, None]:
        """
        Iterate over the database records yielding key-value pairs matching complex query criteria.

        Args:
            keys (Optional[Any], optional): Pattern, function, or string key matches.
                
                >>> jdb.find(re.compile(r'Jo(e|hn)')) == jdb.find(r'Jo(e|hn)')
                >>> jdb.find(lambda k: k[-1] == 'n')
                >>> jdb.find({'$sw': 'Jo'})

            vals (Optional[Dict[str, Any]], optional): Dictionary of value constraint operators (e.g., {'$gt': 10}).
                
                >>> jdb.find(GT=12) == dict(jdb.find_iter(vals={'$gt':12})) # value > 12
                >>> jdb.find(GTE=12) == dict(jdb.find_iter(vals={'$gte':12})) # value >= 12
                >>> jdb.find(GE=12) == dict(jdb.find_iter(vals={'$ge':12})) # value >= 12
                >>> jdb.find(LT=12) == dict(jdb.find_iter(vals={'$lt':12})) # value < 12
                >>> jdb.find(LTE=12) == dict(jdb.find_iter(vals={'$lte':12})) # value <= 12
                >>> jdb.find(LE=12) == dict(jdb.find_iter(vals={'$le':12})) # value <= 12
                >>> jdb.find(EQ=12) == dict(jdb.find_iter(vals={'$eq':12})) # value == 12
                >>> jdb.find(NE=12) == dict(jdb.find_iter(vals={'$ne':12})) # value != 12
                >>> jdb.find(NE=12) == dict(jdb.find_iter(vals={'!$eq':12})) # value != 12
                >>> jdb.find(EQ='Joe') == dict(jdb.find_iter(vals={'$eq':'Joe'})) # value == "Joe"
                >>> jdb.find(NE='Joe') == dict(jdb.find_iter(vals={'$ne':'Joe'})) # value != "Joe"
                >>> jdb.find(RE=r'Jo(hn|e)') == dict(jdb.find_iter(vals={'$re':'Jo(hn|e)'})) # re.search(r'Jo(hn|e)', value)
                >>> jdb.find(HAS=12) == dict(jdb.find_iter(vals={'$has':12})) # 12 in value
                >>> jdb.find(IN=[1,2]) == dict(jdb.find_iter(vals={'$in':[1,2]})) # value in [1,2]
                >>> jdb.find(NIN=[1,2]) == dict(jdb.find_iter(vals={'$nin':[1,2]})) # value not in [1,2]
                >>> jdb.find(NIN=[1,2]) == dict(jdb.find_iter(vals={'$!in':[1,2]})) # value not in [1,2]
                >>> jdb.find(FUNC=lambda k,v: v == 1) == dict(jdb.find_iter(vals={'$func':lambda k,v: v == 1}))
                >>> jdb.find(AND=[{'name':'A'}, {'age':{'$gte':20}}]) # value['name'] == 'A' and value['age'] >= 20
                >>> jdb.find(OR=[{'name':'A'}, {'age':{'$ge':20}}]) # value['name'] == 'A' or value['age'] >= 20
                >>> jdb.find(NOR=[{'name':'A'}, {'age':{'$gte':20}}]) # value['name'] != 'A' and value['age'] < 20
                >>> jdb.find(NOT={'name':'A'}) # not (value['name'] == 'A')
                >>> jdb.find(ANY='A')  # any record's value equal to  'A'
                >>> jdb.find(vals={'name.$has': 'ice'})
                >>> jdb.find(vals={'!name.$ihas': 'ice'})
                >>> jdb.find(vals={'tags.0': ['db', 'c++']})
                >>> jdb.find(vals={'country.city': ['US', 'UK']})
                >>> jdb.find(vals={'c*t*y.c*y': ['US', 'UK']})
                
            date (Optional[Any], optional): Timeline constraint for record modifications.

                >>> jdb.find(date={'$ne': date(2011,1)})

            limit (int, optional): Max results to return. 0 means unlimited. Defaults to 0.
            skip (int, optional): skip number of matched records, Defaults to 0.
            with_value (bool, optional): Whether to decode and return the actual value, or just None. Defaults to False.
            with_date (bool, optional): Whether to return the actual value + created date + modified date Defaults to False.
            stats (Dict[str,float], optional): statistic: loops, records, matched, key.filter, date.filter, value.filter, used_s
            **kwargs: Extra filter configurations (e.g., regex flags).

        Yields:
            (str, Any): Matching key and its associated value (or None if `with_value` is False).

        Example:

            >>> jdb.find_iter(vals={'$eq': "value"})
            >>> jdb.find_iter(EQ="value")
            >>> jdb.find_iter(vals={'$in': ["value1", "value2"]})
            >>> jdb.find_iter(IN=["value1", "value2"])
            >>> jdb.find_iter(NIN=["value1", "value2"])
            >>> jdb.find_iter(vals={'$func': lambda value:value == "any"})
            >>> jdb.find_iter(FUNC=lambda value:value == "any")
            >>> jdb.find_iter(FUNC=lambda key,val:val == "any")
            >>> jdb.find_iter(r'^[Rr].*[Nn]$', IN=[8,27])
            >>> jdb.find_iter(r'^[Rr].*[Nn]$', NIN=[8,27])
            >>> jdb.find_iter(keys=[r'^[Rr]', r'[Nn]$'], vals={'$in' : [8, 27]})
            >>> jdb.find_iter(keys=[r'^[Rr]', r'[Nn]$'], vals={'$gt' : 8, '$lt' : 100})
            >>> jdb.find_iter(keys=[r'^[Rr]', r'[Nn]$'], vals={'$or' : {'$eq' : 8, '$lt' : 50}})
            >>> jdb.find_iter(vals={'name' : r'Jo(e|hn)'})
            >>> jdb.find_iter(ANY='name')
            >>> jdb.find_iter(vals={'$any' : r'name'})
            >>> jdb.find_iter(vals={'$any' : {'$re' : r'name'}})
            >>> jdb.find_iter(vals={'$or': [{'name1':{'$eq':'value1'}}, {'name2':{'$eq':'value2'}}]})
            >>> jdb.find_iter(OR=[{'name1':{'$eq':'value1'}}, {'name2':{'$eq':'value2'}}])
            >>> jdb.find_iter(NOR=[{'name1':{'$eq':'value1'}}, {'name2':{'$eq':'value2'}}])
            >>> jdb.find_iter(vals={'$and': [{'age':{'$gt':0}}, {'age':{'$lte':100}}]})
            >>> jdb.find_iter(AND=[{'age':{'$gt':0}}, {'age':{'$lte':100}}]) # 100 >= age >= 0
            >>> jdb.find_iter(vals={'$not': {'$eq':'value1'}})
            >>> jdb.find_iter(NOT={'$eq':'value1'}) # find_iter(NE='value1')
            >>> jdb.find_iter(EXISTS='role')
            >>> jdb.find_iter(vals={'name.$has': 'ice'})      # $has as query operator
            >>> jdb.find_iter(vals={'name. $has': 'ice'})     # ' $has' as a literal dict key
        """
        st_time = perf_counter()
        if vals is None:
            vals = {}
        elif isinstance(vals, Condition):
            vals = dict(vals)
        elif isinstance(vals, dict):
            pass
        elif callable(vals):
            vals = {'$func': vals}
        elif isinstance(vals, (str, int, float, bool, bytes, dt_date, datetime)):
            vals = {'$eq': vals}
        elif isinstance(vals, Pattern):
            vals = {'$re': vals}
        elif isinstance(vals, (list, set, tuple)):
            vals = {'$in': vals}
        elif isinstance(vals, (frozenset, range)):
            vals = {'$in': set(vals)}
        else:
            raise TypeError('invalid VAL type')

        for key,val in kwargs.items():
            if key in QUERY_OPS:
                vals[f'${key.lower()}'] = val
            else:
                raise TypeError(f'invalid query command {key}')

        if isinstance(keys, Condition):
            vals.update(keys)
            keys = {}

        if not keys and '_id' in vals:
            keys = vals.pop('_id', keys)

        if keys is None:
            keys = {}
        elif isinstance(keys, dict):
            pass
        elif callable(keys):
            keys = {'$func': keys}
        elif isinstance(keys, Pattern):
            keys = {'$re': keys}
        elif isinstance(keys, str):
            idx = keys.find(SEP_SYM)
            if idx >= 0:
                # 'jdb_name:::jdb_key'
                key_rule = keys[:idx]
                key_rule = re_compile(key_rule) if key_rule else None
                next_keys = keys[idx+SEP_LEN:]
                next_idx = next_keys.find(SEP_SYM)

                if next_idx < 0 and not next_keys: # pragma: no cover
                    next_keys = None

                with self.open(read_only=True) as fp:
                    io = self.io
                    key_table = io.key_table
                    childs = set(self.childs).union(io.groups)
                    f_get_child = self.f_get_child
                    for child_name in childs:
                        if child_name not in key_table: continue
                        if not (key_rule and not key_rule.search(child_name)):
                            child = f_get_child(fp, child_name)
                            if isinstance(child, JDbReader):
                                for _key,_val in child.find_iter(next_keys, vals=vals, date=date, limit=limit, skip=skip, with_value=with_value, with_date=with_date, stats=stats, reverse=reverse):
                                    yield f'{child_name}{SEP_SYM}{_key}', _val
                return
            keys = {'$re': re_compile(keys)}
        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {'$eq': keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {'$eq': str(keys)}
        elif isinstance(keys, (int, float, bool, dt_date, datetime)):
            keys = {'$eq': str(keys)}
        elif hasattr(keys, '__iter__'):
            keys = {'$in': {key if isinstance(key, str) else str(key) for key in keys}}
        else:
            raise TypeError('invalid KEY type')

        if not date and '_date' in vals:
            date = vals.pop('_date', date)

        if date is None:
            date = {}
        elif isinstance(date, Condition):
            date = dict(date)
        elif isinstance(date, dict):
            pass
        elif callable(date):
            date = {'$func': date}
        elif isinstance(date, (dt_date, datetime)):
            date = {'$eq': date}
        elif isinstance(date, Pattern):
            date = {'$re': date}
        elif isinstance(date, (set, list, tuple)):
            date = {'$anyin': date}
        elif isinstance(date, (frozenset, range)):
            date = {'$anyin': set(date)}
        elif isinstance(date, str):
            date = {'$has': date}
        elif isinstance(date, (int, float, bool)):
            today = dt_date.today() if isinstance(date, int) else datetime.now()
            days = int(date)
            date = {'$eq': today} if date == 0 else \
                    {'$between': (today, today + timedelta(days=days))} if date > 0 else \
                    {'$between': (today - timedelta(days=-days), today)}
        else:
            raise TypeError('invalid DATE type')

        old_with_value = with_value
        if vals and not old_with_value:
            with_value = True

        n_loops = k_filter = d_filter = v_filter = m_count = 0
        with self.open(read_only=True) as fp:
            io, fp, key_fp = self.f_get_fp(fp)
            count = skipped = 0
            n_records = io.n_records
            io_read_key = io.read_key
            io_conv_date = io.z_conv_date
            data_type = io.data_type_str
            _j_type = data_type.endswith('J')
            _val_conds = []
            for cmd, rules in vals.items():
                cmd_l = cmd[1:].lower() if cmd.startswith('!') else cmd.lower()
                if cmd_l not in ('$key', '$date'):
                    use_bytes = isinstance(rules, bytes) if cmd_l in ('$eq', '$ne') else \
                            (isinstance(rules, bytes) or (isinstance(rules, str) and _j_type)) if cmd_l in ('$has', '$nhas', '$ihas') else \
                            _j_type if cmd_l in ('$re', '$re2', '$regex', '$match') else False
                    _val_conds.append(({cmd:rules}, use_bytes))

            cache = self._cache
            for key,row_id in io.sorted_key_table_items(reverse=reverse):
                n_loops += 1
                if count >= limit > 0:
                    break

                is_matched = not keys or match_KEY_rules(key, keys)
                if not is_matched:
                    k_filter += 1
                    continue

                key_fp = fp[-1]
                if date:
                    _k, _fi, _of, _rs, _vs, mod_id, _days = io_read_key(key_fp, row_id)
                    cdate, mdate = io_conv_date(_days)
                    if not match_DATE_rules(cdate, mdate, date):
                        d_filter += 1
                        continue
                else:
                    mod_id = cdate = mdate = None

                if not with_value:
                    m_count += 1
                    if skipped < skip:
                        skipped += 1
                        continue

                    if with_date:
                        if cdate is None:
                            _k, _fi, _of, _rs, _vs, mod_id, _days = io_read_key(key_fp, row_id)
                            cdate, mdate = io_conv_date(_days)
                        yield key, (None, cdate, mdate, mod_id)
                    else:
                        yield key, None

                    count += 1
                    continue

                if key not in cache:
                    move_to_end = 0
                    value, value_b = self.f_read_with_bytes(fp, key)
                else:
                    move_to_end = 1
                    value_b = None
                    value = cache.get(key, _MISSING)
                    if value is _MISSING: # pragma: no cover
                        value, value_b = self.f_read_with_bytes(fp, key)
                    else:
                        move_to_end += 1

                if vals and isinstance(value, JDbReader):
                    child = value
                    if '$key' in vals or '$date' in vals:
                        _vals = dict(vals)
                        _keys = _vals.pop('$key', None)
                        _date = _vals.pop('$date', date)
                    else:
                        _vals, _keys, _date = vals, None, date

                    child_limit = (limit-count) if limit > 0 else 0
                    for _key,_val in child.find_iter(keys=_keys, vals=_vals, date=_date, limit=child_limit, with_value=old_with_value, with_date=with_date, reverse=reverse):
                        if skipped < skip:
                            skipped += 1
                            continue

                        yield f'{key}{SEP_SYM}{_key}', _val

                        count += 1
                        if count >= limit > 0: # pragma: no cover
                            break

                    continue

                if cdate is None:
                    _k, _fi, _of, _rs, _vs, mod_id, _days = io_read_key(key_fp, row_id)
                    cdate, mdate = io_conv_date(_days)

                for rules,use_bytes in _val_conds:
                    if use_bytes:
                        if value_b is None:
                            try:
                                value_b = io.VAL_dumps(value)
                            except ValueError: # pragma: no cover
                                value, value_b = self.f_read_with_bytes(fp, key)

                        _value = value_b
                    else:
                        _value = value

                    if not match_VAL_rules(key, _value, rules, cdate, mdate):
                        v_filter += 1
                        is_matched = False
                        break

                if is_matched:
                    m_count += 1
                    if skipped < skip:
                        skipped += 1
                        continue

                    if move_to_end > 1:
                        cache.move_to_end(key)
                        value = deepcopy(value)

                    if with_date:
                        yield key, (value, cdate, mdate, mod_id)
                    else:
                        yield key, value

                    count += 1

        ed_time = perf_counter()
        if isinstance(stats, dict):
            stats.update({'loops': n_loops, 'records':n_records, 'matched':m_count, \
                    'key.filter':k_filter, 'date.filter':d_filter, 'value.filter':v_filter, 'used_s':ed_time-st_time})

    def map(self, map_func:Callable[[str,Any],Any], keys:Optional[Any]=None, vals:Optional[Any]=None, date:Optional[Any]=None, **kwargs) -> List[Any]:
        """
        Apply a mapping function to the results of a query and return a list.

        Args:
            map_func (Callable[[str, Any], Any]): The lambda or function to process (key, value) pairs.
            keys (Any, optional): Condition for key filtering.
            vals (Any, optional): Condition for value filtering using operators.
            date (Any, optional): Date filters.            
            **kwargs: Extra find arguments.

        Returns:
            List[Any]: Transformed list of objects returned by map_func.
        """
        if not callable(map_func):
            raise TypeError('not callable')

        matched_list = []
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, with_value=True, with_date=False, **kwargs):
            matched_list.append(map_func(key, val))

        return matched_list

    def find(self, keys:Optional[Any]=None, vals:Optional[Any]=None, date:Optional[Any]=None, limit:int=0, skip:int=0, with_value:Optional[bool]=None, stats:Dict[str,float]=None, sort:Optional[Any]=None, reverse:Optional[bool]=None, group_by:Optional[Any]=None, **kwargs) -> Dict[str,Any]:
        """
        Find and return a dictionary of records matching complex query criteria.

        Args:
            keys (Any, optional): Condition for key filtering.
            vals (Any, optional): Condition for value filtering using operators.
            date (Any, optional): Date filters.
            limit (int, optional): Maximum item cap. Defaults to 0.
            skip (int, optional): skip number of matched records, Defaults to 0.
            with_value (Optional[bool], optional): Whether to read the key's value. Defaults to False.
            stats (Dict[str,float], optional): statistic: loops, records, matched, key.filter, date.filter, value.filter, used_s
            sort (Any, optional): Sorting specification. One of:

                * ``int`` – legacy mode: ``0`` = unsorted, ``1`` = ascending,
                  ``-1`` = descending. Sorts by value when every matched value
                  is a simple orderable scalar, otherwise falls back to
                  sorting by key. Preserved for backward compatibility.
                * ``str`` – a dot-notation field path, e.g. ``'name'``,
                  ``'name.$lower'``, ``'_id'``, ``'_date'``.
                * :class:`Query` – built via attribute/item access, e.g.
                  ``Query()._id``, ``Query().address.city``.
                * ``list[str | Query]`` – multiple fields; sorts by the first,
                  breaking ties with the second, and so on (like SQL
                  ``ORDER BY a, b``).

                Records where a specified field cannot be resolved (missing
                key, or a non-orderable type such as ``dict``/``list``) are
                placed after all sortable records ("nulls last"), regardless
                of ``reverse``.

                >>> jdb.find(sort=Query()._id)                       # key ascending
                >>> jdb.find(sort='_id', reverse=True)               # key descending
                >>> jdb.find(sort=Query()._date)                     # by (created, modified) date
                >>> jdb.find(sort=['_id', '_date'])                  # key, then date as tie-break
                >>> jdb.find(sort=['_id.$first', '_date'])           # key's first char, then date
                >>> jdb.find(sort=['name', '_date'])                 # value['name'], then date

            reverse (bool, optional): Reverse the sort order. Defaults to
                ``False`` for the new spec-based modes; for the legacy ``int``
                mode, defaults to ``sort < 0`` when not explicitly given.
            group_by (Any, optional): Group the matched records; the resolved
                group value becomes the new ``_id`` (record key) and every
                grouped field is aggregated. Defaults to ``None`` (no
                grouping). Grouping happens **after** ``limit``/``skip``
                (which act on raw records) and **before** ``sort`` (which
                acts on the grouped rows). All ``TRANSFORM_OPS`` are accepted
                as aggregation operators; when an operator cannot process a
                group's collected list, that field becomes ``None``.
                Supported spec forms:

                * ``str`` / :class:`Query` — group by this field, collect all
                  other top-level fields as **lists**. A *trailing*
                  ``TRANSFORM_OPS`` segment is the aggregation operator
                  applied to every collected list; earlier ops transform the
                  group key itself.

                  >>> jdb.find(group_by='category')             # fields -> lists
                  >>> jdb.find(group_by='category.$avg')        # fields -> averages
                  >>> jdb.find(group_by='name.$lower.$avg')     # key=lower(name), fields -> averages
                  >>> jdb.find(group_by='category.$list')       # explicit list mode (== 'category')

                * ``list`` / ``tuple`` — composite key; the new ``_id`` is a
                  ``tuple`` of the resolved components. Ops inside an element
                  (including trailing ones) transform *that key component*;
                  a standalone op element sets the aggregation operator.

                  >>> jdb.find(group_by=['category', 'role'])           # _id=(category, role)
                  >>> jdb.find(group_by=['category', 'role', '$sum'])   # + fields -> sums
                  >>> jdb.find(group_by=['name.$lower'])                # key=lower(name), fields -> lists

                * ``dict`` — exactly one ``{key_spec: field_specs}`` pair;
                  only the listed fields appear in the output, each with its
                  own optional trailing aggregation op (default: list).
                  ``'_id'`` yields the original record keys; a ``tuple``
                  key_spec builds a composite key.

                  >>> jdb.find(group_by={'category': ['price.$max', 'qty.$sum', '_id']})
                  >>> jdb.find(group_by={('category','role'): ['qty.$avg', '_id.$len']})

                A spec without any group-key field (e.g. ``'$avg'`` or
                ``['$sum']``) raises ``ValueError``; an unsupported spec type
                raises ``TypeError``. Records whose group-key path cannot be
                resolved fall into the ``None`` group; unhashable group
                values are stringified.
                Non-``dict`` record values are collected under the pseudo
                field ``'_val'`` (unwrapped to a bare list/aggregate when the
                whole group is non-``dict``). Besides value fields, the
                special roots ``'_id'`` (record key) and ``'_date'`` (the
                ``(created, modified)`` date tuple) can be used anywhere a
                path is accepted — as group key, key component, or output
                field:

                >>> jdb.find(group_by='_date')                 # _id=(cdate, mdate)
                >>> jdb.find(group_by=['_date.$first'])        # _id=created date only
                >>> jdb.find(group_by=['category', '_date.$last']) # _id=(category, modified)
                >>> jdb.find(group_by={'_date': ['_id', 'qty.$sum']})

        Returns:
            Dict[str, Any]: The subset of matched data, or — when *group_by*
            is given — ``{group_value: aggregated_fields}``.

        Example:
            >>> jdb += {'apple':  {'category':'fruit', 'price':10, 'qty':10},
            ...         'banana': {'category':'fruit', 'price':20, 'qty':20},
            ...         'carrot': {'category':'veg',   'price':30, 'qty':30}}
            >>> jdb.find(group_by='category')
            {'fruit': {'price': [10, 20], 'qty': [10, 20]}, 'veg': {'price': [30], 'qty': [30]}}
            >>> jdb.find(group_by='category.$avg')
            {'fruit': {'price': 15.0, 'qty': 15.0}, 'veg': {'price': 30.0, 'qty': 30.0}}
            >>> jdb.find(group_by={'category': ['price.$max', 'qty.$sum', '_id']})
            {'fruit': {'price': 20, 'qty': 30, '_id': ['apple', 'banana']}, 'veg': {'price': 30, 'qty': 30, '_id': ['carrot']}}
        """
        if group_by is not None:
            with_value = True
            key_parts_list, default_op, field_specs = parse_group_by(group_by)
        else:
            with_value = not (not vals and not kwargs and sort is None) if with_value is None else with_value
            key_parts_list = default_op = field_specs = None

        data_rows = []
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, limit=limit, skip=skip, with_value=with_value, with_date=True, stats=stats, **kwargs):
            data_rows.append((key, val))

        data_rows = grouped_by_rules(data_rows, key_parts_list, default_op, field_specs)
        data_rows = sorted_by_rules(data_rows, sort, reverse)

        return {k:v[0] for k,v in data_rows}

    def show(self, keys:Optional[Any]=None, vals:Optional[Any]=None, date:Optional[Any]=None, limit:int=50, skip:int=0, with_date:bool=False, sort:Optional[Any]=None, reverse:Optional[bool]=None, group_by:Optional[Any]=None, **kwargs) -> Dict[str,Any]:
        """
        Print the matched records as a formatted console table and return them.

        Args:
            keys (Any, optional): Condition for key filtering.
            vals (Any, optional): Condition for value filtering using operators.
            date (Any, optional): Date filters.
            limit (int, optional): Maximum rows to display. ``0`` shows all
                matched items. Defaults to ``50``.
            skip (int, optional): Number of matched records to skip before
                collecting rows for display. Defaults to ``0``.
            with_date (bool, optional): Whether to include a ``_date`` column
                showing each record's created/modified dates. Defaults to
                ``False``. Sorting by ``'_date'`` still works even when this is
                ``False`` — dates are always fetched internally for ordering
                purposes, and are only omitted from the printed table.
            sort (Any, optional): Sorting specification — see :meth:`find` for
                the full ``int`` / ``str`` / ``Query`` / ``list`` spec format.
            reverse (bool, optional): Reverse the sort order. Defaults to
                ``False``.
            group_by (Any, optional): Group the matched records before
                display — see :meth:`find` for the full ``str`` / ``list`` /
                ``dict`` spec format. The group value is shown in the ``_id``
                column; when the spec requests the original record keys via
                ``'_id'`` (dict form), they are displayed in an ``_ids``
                column to avoid clashing with the group ``_id``. With
                ``with_date=True`` the ``_date`` column shows each group's
                ``min(created)``/``max(modified)`` dates. Defaults to ``None``.

        Returns:
            Dict[str, Any]: The subset of matched data, or — when *group_by*
            is given — ``{group_value: aggregated_fields}``.

        Example:
            >>> jdb = JDb()
            >>> jdb += {'apple': {'color':'red', 'qty':10}, 'banana':{'color':'yellow', 'qty':100, 'from':'Japan'}}
            >>> matches = jdb.show(limit=0) # show all records
                +--------+--------+-----+-------+
                | _id    | color  | qty | from  |
                +--------+--------+-----+-------+
                | apple  | red    | 10  |       |
                | banana | yellow | 100 | Japan |
                +--------+--------+-----+-------+
            >>> matches = jdb.show(limit=1)
                +--------+--------+-----+-------+
                | _id    | color  | qty | from  |
                +--------+--------+-----+-------+
                | apple  | red    | 10  |       |
                +--------+--------+-----+-------+
            >>> matches = jdb.show(vals={'qty': {'$gt': 50}})
                +--------+--------+-----+-------+
                | _id    | color  | qty | from  |
                +--------+--------+-----+-------+
                | banana | yellow | 100 | Japan |
                +--------+--------+-----+-------+
        """
        key_parts_list, default_op, field_specs = parse_group_by(group_by) if group_by is not None else (None, None, None)
        stats = {}
        data_rows = []
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, limit=limit, skip=skip, with_value=True, with_date=True, stats=stats, **kwargs):
            data_rows.append((key,val))

        data_rows = grouped_by_rules(data_rows, key_parts_list, default_op, field_specs)
        data_rows = sorted_by_rules(data_rows, sort, reverse)
        grouped = group_by is not None
        fields = ['_id']
        patterns = {'_id'}
        if with_date:
            fields.append('_date')
            patterns.add('_date')

        for _key,(val,cdate,mdate,_mod_id) in data_rows:
            if isinstance(val, dict):
                kk = '|'.join(val)
                if kk not in patterns:
                    patterns.add(kk)
                    for kk in val:
                        if grouped and kk == '_id':
                            kk = '_ids' # keep the group value in the _id column
                        if kk not in fields:
                            fields.append(kk)

            elif isinstance(val, (str, bytes, bytearray, int, float, bool)) or val is None:
                kk = '__1__'
                if kk not in patterns:
                    patterns.add(kk)
                    fields.insert(1, kk)

            elif hasattr(val, '__iter__') and val:
                nn = len(val)
                kk = f'__V{nn}__'
                offset = 2 if '__1__' in patterns else 1
                if kk not in patterns:
                    patterns.add(kk)
                    for ii in range(nn):
                        kk = f'__V{ii+1}__'
                        patterns.add(kk)
                        if kk not in fields:
                            fields.insert(ii+offset, kk)

        clean_re = re_compile(r'\x1b\[\d\d?m')

        def _format_cell(val:Any) -> str:
            """Render one value as display text (colored scalars, short lists,
            or an underlined ``<type:len>`` placeholder)."""
            if val is None:
                return ""

            if isinstance(val, str):
                return val

            if isinstance(val, (int, float, bool, bytes, bytearray)):
                # with yellow color
                return f"\x1b[93m{val}\x1b[0m"

            if grouped and isinstance(val, (list, tuple)):
                # grouped lists are usually the payload -> show contents when short
                vv_s = str(val)
                if len(vv_s) <= 48:
                    return vv_s

            try:
                # with underscore
                return f"\x1b[4m<{type(val).__name__}:{len(val)}>\x1b[0m"
            except TypeError: # pragma: no cover
                # with underscore
                return f"\x1b[4m'<{type(val).__name__}>\x1b[0m"

        def _get_display_width(s_str:str) -> int:
            """Terminal display width of a string, counting East-Asian wide
            characters as 2 and ignoring ANSI color codes."""
            width = 0
            s_str_ = clean_re.sub('', s_str) if s_str.find('\x1b[') >= 0 else s_str
            for ch in s_str_:
                width += (2 if east_asian_width(ch) in ('W', 'F', 'A') else 1)
            return width

        col_widths = {field: _get_display_width(field) for field in fields}
        matrix = []
        for key,(val,cdate,mdate,_mod_id) in data_rows:
            row_data = {field:'' for field in fields}
            if with_date:
                row_data['_date'] = _date = f'{cdate} {mdate}'
                col_widths['_date'] = max(col_widths['_date'], _get_display_width(_date))

            row_data['_id'] = key_s = key if isinstance(key, str) else str(key)
            col_widths['_id'] = max(col_widths['_id'], _get_display_width(key_s))
            if isinstance(val, dict):
                for field,vv in val.items():
                    if grouped and field == '_id':
                        field = '_ids' # keep the group value in the _id column
                    row_data[field] = vv_s = _format_cell(vv)
                    col_widths[field] = max(col_widths[field], _get_display_width(vv_s))

            elif isinstance(val, (str, bytes, bytearray, int, float, bool)) or val is None:
                field = '__1__'
                row_data[field] = vv_s = _format_cell(val)
                col_widths[field] = max(col_widths[field], _get_display_width(vv_s))

            elif hasattr(val, '__iter__'):
                for ii, vv in enumerate(val):
                    field = f'__V{ii+1}__'
                    row_data[field] = vv_s = _format_cell(vv)
                    col_widths[field] = max(col_widths[field], _get_display_width(vv_s))

            matrix.append(row_data)

        def _pad_string(s_str, target_width):
            """Right-pad a string to the target display width."""
            return s_str + " " * (target_width - _get_display_width(s_str))

        sep = "┼".join("─" * (col_widths[field] + 2) for field in fields)
        top = "╔" + "╤".join("═" * (col_widths[field] + 2) for field in fields) + "╗"
        mid = "╟" + sep + "╢"
        bot = "╚" + "╧".join("═" * (col_widths[field] + 2) for field in fields) + "╝"
        print()
        print(top)
        # with bold+cyan color
        print("║" + "│".join(" \x1b[96m\x1b[1m" + _pad_string(field, col_widths[field]) + "\x1b[0m " for field in fields) + "║")
        print(mid)
        for row_data in matrix:
            print("║" + "│".join(" " + _pad_string(row_data[field], col_widths[field]) + " " for field in fields) + "║")
        print(bot)
        _used_s = stats.get('used_s', 0.)
        n_loops = stats.get('loops', 0)
        n_records = stats.get('records', 0)
        ops = n_loops / max(_used_s, 1e-9)
        ops, o_unit = (ops / 1_000_000, 'M') if ops >= 1_000_000 else \
                        (ops / 1_000, 'K') if ops >= 1_000 else (ops, '')
        progress = 100. if n_loops >= n_records else (n_loops / n_records) * 100.
        used_s, unit = (_used_s, 's') if _used_s * 10 > 1. else \
                        (_used_s * 1_000, 'ms') if _used_s * 10_000 > 1. else \
                        (_used_s * 1_000_000, 'us')
        print(f"\x1b[2mUsed:{used_s:.3f}{unit} | {ops:.3f}{o_unit}/s | {n_loops:,}/{n_records:,}({progress:.2f}%) -> #{len(data_rows):,}\x1b[0m")
        return {k:v[0] for k,v in data_rows}

    def sync(self, force:bool=False, with_child:bool=False) -> JDbReader:
        """Reload the in-memory key table from disk so it reflects changes
        made by other processes.

        Args:
            force (bool, optional): Drop all in-memory state first
                (see :meth:`unsync`) to force a full reload. Defaults to ``False``.
            with_child (bool, optional): Also sync every child/group database.
                Defaults to ``False``.

        Returns:
            JDbReader: ``self``, for call chaining.
        """
        with self.open(read_only=True) as fp:
            if force:
                self.unsync()

            io = self.io
            if len(self.key_table) != io.n_records: # pragma: no cover
                self.f_load_keys(fp)

            if with_child:
                childs = set(io.groups).union(self.childs)
                for name in childs:
                    child = self.f_get_child(fp, name)
                    if isinstance(child, JDbReader):
                        child.sync(force=force, with_child=True)

        return self

    def unsync(self, with_child:bool=False) -> JDbReader:
        """Drop the in-memory key table, file table, and value cache so the
        next access reloads everything from disk. No file content is changed.

        Args:
            with_child (bool, optional): Also unsync every child/group database.
                Defaults to ``False``.

        Returns:
            JDbReader: ``self``, for call chaining.
        """
        if not self.lock.acquire():
            raise RuntimeError

        try:
            io = self.io
            if with_child:
                with self.open(read_only=True) as fp:
                    childs = set(io.groups).union(self.childs)
                    for name in childs:
                        child = self.f_get_child(fp, name)
                        if isinstance(child, JDbReader):
                            child.unsync(with_child=True)

            self._cache.clear()
            io.key_table.clear()
            io.file_table.clear()
            io._n_records = io._n_lines = io.file_size = 0

        finally:
            self.lock.release()

        return self

    def load_table(self, force:bool=False) -> Tuple[Dict[str,int],Dict[int,int]]:
        """Load the key table and file table from disk (skipped when the
        in-memory copy is already up to date) and return both.

        Args:
            force (bool, optional): Rebuild the tables even if they appear
                up to date. Defaults to ``False``.

        Returns:
            Tuple[Dict[str, int], Dict[int, int]]: ``(key_table, file_table)`` —
            key -> row id, and VAL file id -> used size.
        """
        with self.open(read_only=True) as fp:
            self.f_load_keys(fp, force=force)
            return self.io.key_table, self.io.file_table

    def get(self, key:str, default_val:Any=None, copy:bool=True) -> Any:
        """Safely fetch a value for a specific key, returning a default if not found.

        Args:
            key (str): The target key.
            default_val (Any, optional): Value to return upon missing key. Defaults to ``None``.
            copy (bool, optional): Retrieve a deep copy to prevent mutation. Defaults to ``True``.

        Returns:
            Any: The stored value or the default value.
        """
        with self.open(read_only=True) as fp:
            io = self.io
            key_table = io.key_table
            key_fp = fp[-1]
            row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
            if row < 0:
                return default_val

            try:
                return self.f_read(fp, key, copy=copy, row=row)

            except KeyError: # pragma: no cover
                return default_val

    def get_cache(self, key:str, default_val:Any=None, copy:bool=False) -> Any:
        """
        Retrieve a value, checking the in-memory cache first to avoid disk
        I/O. A cache hit is returned without verifying against the file, so
        the value may be stale if another process modified the database.

        Args:
            key (str): The target key.
            default_val (Any, optional): Returned when the key is missing.
                Defaults to ``None``.
            copy (bool, optional): Return a deep copy of a cached value.
                Defaults to ``False``.

        Returns:
            Any: The value, or ``default_val``.
        """
        val = self._cache.get(key, _MISSING)
        if val is not _MISSING:
            return deepcopy(val) if copy else val

        io = self.io
        key_table = io.key_table
        if key not in key_table:
            n_records = io.n_records
            if not (n_records == 0 or n_records != len(key_table)):
                return default_val

        return self.get(key, default_val, copy=copy)

    def get_n(self, *records:str) -> Dict[str,Any]:
        """
        Retrieve multiple keys at once and pack them into a dictionary.
        Missing keys are silently skipped; calling with no arguments returns
        the whole database (see :meth:`get_all`).

        Args:
            *records: Keys to fetch. Each argument may be a string, any
                hashable (converted with ``str``), or an iterable of keys.

        Returns:
            Dict[str, Any]: A mapping of the found keys to their values.
        """
        keys = set()
        for key in records: # pragma: no cover
            if isinstance(key, str):
                keys.add(key)
            elif key.__hash__:
                keys.add(str(key))
            else:
                for kk in key:
                    keys.add(kk if isinstance(kk, str) else str(kk))

        if not keys:
            return self.get_all()

        data = {}
        with self.open(read_only=True) as fp:
            io = self.io
            f_read = self.f_read
            keys = set(keys).intersection(io.key_table)
            for key in keys:
                data[key] = f_read(fp, key, copy=False)

        return data

    def get_all(self, cache_only:bool=False) -> Dict[str,Any]:
        """
        Retrieve the entire database content into a single dictionary.

        Args:
            cache_only (bool, optional): If ``True``, records are read only to
                warm the in-memory cache (up to ``cache_limit``) and an
                **empty** dict is returned. Defaults to ``False``.

        Returns:
            Dict[str, Any]: A full ``{key: value}`` snapshot, or ``{}`` when
            ``cache_only=True``.
        """
        data = {}
        with self.open(read_only=True) as fp:
            f_read = self.f_read
            if cache_only:
                cache_limit = self._cache_limit
                _cache = self._cache
                for key,row in self.io.sorted_key_table_items():
                    if len(_cache) >= cache_limit >= 0:
                        break

                    f_read(fp, key, row=row, copy=False)
            else:
                for key,row in self.io.sorted_key_table_items():
                    data[key] = f_read(fp, key, row=row, copy=False)

            return data

    def check_version(self, version:int, max_version:Optional[int]=None, with_value:bool=False) -> dict:
        """Return the rows whose version (write-session id) falls within
        ``version <= ver <= max_version``, including dead/history rows.

        Args:
            version (int): Lowest version to include (clamped to 0).
            max_version (Optional[int], optional): Highest version to include.
                ``None`` means no upper bound. Defaults to ``None``.
            with_value (bool, optional): Also decode and append each row's
                value. Defaults to ``False``.

        Returns:
            dict: ``{row_id: [key, file_id, offset, row_size, val_size, ver,
            days, is_active(, value)]}`` — see :meth:`f_read_version`.
        """
        with self.open(read_only=True) as fp:
            return self.f_read_version(fp, version=version, max_version=max_version, with_value=with_value)

    def check_row(self, row_id:int=0, with_value:bool=False) -> Optional[tuple]:
        """Read one row's stored metadata (and optionally its value) by row
        index, including dead/history rows.

        Args:
            row_id (int, optional): Row index; negative counts from the end of
                the active records. Defaults to ``0``.
            with_value (bool, optional): Also decode and append the row's
                value. Defaults to ``False``.

        Returns:
            Optional[tuple]: ``(key, file_id, offset, row_size, val_size, ver,
            days, is_active(, value))``, or ``None`` if ``row_id`` is out of
            range.
        """
        with self.open(read_only=True) as fp:
            return self.f_read_row(fp, row_id, with_value)

    def get_bytes(self, key:str) -> bytes:
        """Return a value's serialized (and, when compression is enabled,
        compressed) bytes without deserializing. Small values packed inline in
        the KEY row are re-serialized on the fly.

        Args:
            key (str): The record key.

        Returns:
            bytes: The stored payload, or ``b''`` if the key is not found.
        """
        with self.open(read_only=True) as fp:
            return self.f_read_bytes(fp, key)

    def check_status(self, keys:dict) -> Dict[str,Tuple[str,int]]:
        """Compare keys against known versions and report what changed.

        Args:
            keys (dict): ``{key: last_known_version}``. A ``None`` version just
                fetches the current status/version. The special key ``''``
                reports every active record whose version is >= the given
                version as ``('+', ver)`` (new or modified).

        Returns:
            Dict[str, Tuple[str, int]]: ``{key: (status, version)}`` where
            status is ``''`` = unchanged (or current version when the input
            version was ``None``), ``'!'`` = changed, ``'-'`` = deleted,
            ``'x'`` = does not exist, ``'+'`` = new/modified (only from the
            ``''`` query).
        """
        status = {}
        with self.open(read_only=True) as fp_dict:
            io, fp_dict, key_fp = self.f_get_fp(fp_dict)
            f_read_status = self.f_read_status

            for key,ver in keys.items():
                if key == '':
                    if ver is None: # pragma: no cover
                        ver = io._sync_id

                    max_ver = io.sync_id
                    for (_key, _f, _o, _r, _v, _ver, _d) in io.KEY_iter(key_fp, 0, io.n_records):
                        if max_ver >= _ver >= ver:
                            if _key not in status:
                                status[_key] = ('+', _ver)
                else:
                    status[key] = f_read_status(fp_dict, key, ver)

        return status

    def is_latest(self) -> bool:
        """Check whether the in-memory state matches the file on disk (same
        header counters and file size), i.e. no other process has modified
        the database since it was last loaded.

        Returns:
            bool: ``True`` if the in-memory state is current.
        """
        with self.KEY_fopen():
            if self.io.is_updated():
                fsize = self.files_obj.KEY_size()
                return fsize == self.io.file_size

        return False

    def get_group(self, key:str) -> Optional[JDbReader]:
        """Get the nested group database stored under ``key``. A group is a
        sub-database whose files live alongside the parent's files.

        Args:
            key (str): Group name; must match ``[0-9A-Za-z_]+`` or ``KeyError``
                is raised.

        Returns:
            Optional[JDbReader]: The group database, or ``None`` if ``key`` is
            not a group.
        """
        if not re_match(r'^[0-9A-Za-z_]+$', key):
            raise KeyError

        with self.open(read_only=True) as fp:
            return self.f_get_group(fp, key)

    def get_child(self, name:str) -> Optional[JDbReader]:
        """Get the child database registered under ``name``. A child is either
        a group (see :meth:`get_group`) or an external database whose KEY file
        path is stored as the record's value.

        Args:
            name (str): Child name (a key of this database).

        Returns:
            Optional[JDbReader]: The child database, or ``None`` if ``name``
            is not a child or its file no longer exists.
        """
        with self.open(read_only=True) as fp:
            return self.f_get_child(fp, name)

    def f_get_group(self, fp_dict:Dict[int,IO], key:str) -> Optional[JDbReader]:
        """Internal :meth:`get_group` — resolve a group database using an
        already-open file-pointer table (must be called inside :meth:`open`).
        The resolved instance is cached in ``io.groups``.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table
                (or a raw KEY file pointer).
            key (str): Group name.

        Returns:
            Optional[JDbReader]: The group database, or ``None`` if ``key`` is
            not a group.
        """
        io = self.io
        key_fp = fp_dict[-1]
        key_table = io.key_table
        row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
        if io.n_records > row >= 0:
            jdb = io.groups[key]
            if jdb is not None:
                return jdb

            if not isinstance(fp_dict, dict): # pragma: no cover
                key_fp = fp_dict
            else:
                io, fp_dict, key_fp = self.f_get_fp(fp_dict)

            _key, file_id, offset, row_size, val_size, _ver, _old_days = io.read_key(key_fp, row)
            if row_size == 0 and file_id == 0x10:
                jdb = self._decode_row(file_id, offset, key, val_size)
                if isinstance(jdb, JDbReader) and self.files_obj.is_group(jdb.files_obj, key):
                    io.groups[key] = jdb
                    self.childs.pop(key, None)
                    return jdb

        self.io.groups.pop(key, None)
        return None

    def f_get_child(self, fp_dict:Dict[int,IO], name:str) -> Optional[JDbReader]: # pragma: no cover
        """Internal :meth:`get_child` — resolve a child database (group or
        external file) using an already-open file-pointer table (must be
        called inside :meth:`open`). External children are opened from the
        KEY file path stored as the record's value and cached in
        ``self.childs``.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            name (str): Child name (a key of this database).

        Returns:
            Optional[JDbReader]: The child database, or ``None`` if ``name``
            is not a child or its file no longer exists.
        """
        io = self.io
        childs = self.childs
        groups = io.groups

        if name not in io.key_table:
            childs.pop(name, None)
            groups.pop(name, None)
            return None

        if name in childs:
            jdb = childs.get(name, None)
        elif name in groups:
            jdb = self.f_get_group(fp_dict, name)
        else:
            return None

        if isinstance(jdb, JDbReader):
            return jdb

        KEY_path = self.f_read(fp_dict, name)
        if not isinstance(KEY_path, str):
            return None

        if not KEY_path:
            KEY_path = None

        elif not path_exists(KEY_path):
            return None

        childs[name] = jdb = JDbReader(KEY_path)
        return jdb

    def _update_cache(self, key:str, val:Any, copy:bool=True):
        """Store a value in the in-memory read cache with LRU eviction: when
        the cache is full the least-recently-used entry is evicted, and the
        stored key is moved to the most-recently-used position. Does nothing
        when ``cache_limit == 0``.

        Args:
            key (str): The record key.
            val (Any): The deserialized value to cache.
            copy (bool, optional): Store a deep copy instead of the object
                itself. Defaults to ``True``.
        """
        cache_limit = self._cache_limit
        if cache_limit != 0:
            _cache = self._cache
            if cache_limit < 0:
                # infinity cache
                pass
            else:
                _size = len(_cache)
                if _size > 0 and cache_limit <= _size and key not in _cache:
                    _cache.popitem(last=False)

            _cache[key] = deepcopy(val) if copy else val
            _cache.move_to_end(key, last=True)

    def f_read_row(self, fp_dict:Dict[int,IO], row_id:int, with_value:bool=False) -> Optional[tuple]:
        """Internal :meth:`check_row` — read one row's stored metadata (and
        optionally its value) by row index, including dead/history rows.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            row_id (int): Row index; negative counts from the end of the
                active records.
            with_value (bool, optional): Also decode and append the row's
                value. Defaults to ``False``.

        Returns:
            Optional[tuple]: ``(key, file_id, offset, row_size, val_size, ver,
            days, is_active(, value))`` where ``is_active`` is ``True`` for a
            live record and ``False`` for a dead/history row, or ``None`` if
            ``row_id`` is out of range.
        """
        io, fp_dict, key_fp = self.f_get_fp(fp_dict)

        # [Case A] -------------------------------------
        if row_id < 0:
            row_id = io.n_records + row_id

        if io.n_lines > row_id >= 0:
            # [Case B] -------------------------------------
            key, file_id, offset, row_size, val_size, ver, days =  io.read_key(key_fp, row_id)
            if with_value:
                _cache = self._cache
                if _cache and key in _cache:
                    val = _cache[key]
                else:
                    if row_size == 0:
                        val = self._decode_row(file_id, offset, key, val_size)
                    else:
                        val_fp, __i, __o  = self.f_get_val_fp(fp_dict, file_id)
                        val = io.read_value(val_fp, offset, row_size, val_size)

                    if self._cache_limit != 0:
                        self._update_cache(key, val, copy=False)

                return key, file_id, offset, row_size, val_size, ver, days, row_id < io.n_records, val

            return key, file_id, offset, row_size, val_size, ver, days, row_id < io.n_records

        # [Case C] -------------------------------------
        return None

    def f_read_version(self, fp_dict:Dict[int,IO], version:int, max_version:Optional[int]=None, with_value:bool=False) -> Dict[str,list]:
        """Internal :meth:`check_version` — return every row (active and
        dead/history) whose version satisfies ``version <= ver <= max_version``.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            version (int): Lowest version to include (clamped to 0).
            max_version (Optional[int], optional): Highest version to include.
                ``None`` means no upper bound. Defaults to ``None``.
            with_value (bool, optional): Also decode and append each row's
                value. Defaults to ``False``.

        Returns:
            Dict[int, list]: ``{row_id: [key, file_id, offset, row_size,
            val_size, ver, days, is_active(, value)]}``.
        """
        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        if max_version is None:
            max_version = io.n_lines

        version = max(version, 0)
        matched_list = {}
        io_read_value = io.read_value
        _decode_row = self._decode_row
        f_get_val_fp = self.f_get_val_fp
        _update_cache = self._update_cache
        cache_limit = self._cache_limit
        _cache = self._cache
        n_records = io.n_records
        row_id = 0
        for (key, file_id, offset, row_size, val_size, ver, days) in io.KEY_iter(key_fp, row_id, io.n_lines):
            if max_version >= ver >= version:
                data = [key, file_id, offset, row_size, val_size, ver, days, row_id < n_records]
                if with_value:
                    if _cache and key in _cache:
                        val = _cache[key]
                    else:
                        if row_size == 0:
                            val = _decode_row(file_id, offset, key, val_size)
                        else:
                            val_fp, __i, __o  = f_get_val_fp(fp_dict, file_id)
                            val = io_read_value(val_fp, offset, row_size, val_size)

                        if cache_limit != 0:
                            _update_cache(key, val, copy=False)

                    data.append(val)

                matched_list[row_id] = data
            row_id += 1

        return matched_list

    def f_read_bytes(self, fp_dict:Dict[int,IO], key:str) -> bytes:
        """Internal :meth:`get_bytes` — return a value's serialized (and, when
        compression is enabled, compressed) bytes without deserializing.
        Values packed inline in the KEY row are re-serialized on the fly.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            key (str): The record key.

        Returns:
            bytes: The stored payload, or ``b''`` if the key does not exist.
        """
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io = self.io
        key_fp = fp_dict[-1]
        key_table = io.key_table
        row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
        if not io.n_records > row >= 0:
            return b''

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        _key, file_id, offset, row_size, val_size, _ver, _days = io.read_key(key_fp, row)
        if row_size == 0:
            val = self._decode_row(file_id, offset, key, val_size)
            return io.dumps_with_zip(val)

        val_fp, __i, __o  = self.f_get_val_fp(fp_dict, file_id)
        return io.read_bytes(val_fp, offset, row_size, val_size)

    def f_read_with_bytes(self, fp_dict:Dict[int,IO], key:str) -> Tuple[Any, bytes]:
        """Read a value together with its serialized (decompressed) bytes,
        so callers can match byte-level rules without re-serializing.

        Args:
            fp_dict (Optional[Dict[int, IO]]): The thread's open file-pointer
                table; ``None`` looks up the current thread's table.
            key (str): The record key. Raises ``JKeyError`` when missing.

        Returns:
            Tuple[Any, bytes]: ``(value, serialized_bytes)``. For a child or
            group record the bytes are ``None`` and the value is the child
            :class:`JDbReader`.
        """
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io = self.io
        key_fp = fp_dict[-1]
        key_table = io.key_table
        row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
        if not io.n_records > row >= 0: # pragma: no cover
            raise JKeyError(key)

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        _key, file_id, offset, row_size, val_size, _ver, _days = io.read_key(key_fp, row)
        if _key in io.groups or _key in self.childs:
            val = self.f_get_child(fp_dict, _key)
            return val, None

        if row_size == 0:
            val = self._decode_row(file_id, offset, key, val_size)
            val_bytes = io.VAL_dumps(val) # without zip
            return val, val_bytes

        val_fp, __i, __o  = self.f_get_val_fp(fp_dict, file_id)
        val_fp.seek(offset)
        val_bytes, zip_type = (val_fp.read(val_size), -(io.zip_type+1)) if val_size > 0 else \
                            (val_fp.read(row_size), io.zip_type)

        if not val_bytes: # pragma: no cover
            raise ValueError

        val_bytes = io.unzip(val_bytes, zip_type=zip_type)
        val = io.VAL_loads(val_bytes)
        return val, val_bytes

    def f_read(self, fp_dict:Dict[int,IO], key:Optional[str], default_val:Optional[Any]=None, row:Optional[int]=None, copy:bool=True) -> Any:
        """Low-level read of a single record, preferring the in-memory cache
        over disk (must be called inside :meth:`open`).

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            key (Optional[str]): The record key (non-strings are converted).
            default_val (Optional[Any], optional): Returned when the key is
                missing; pass the internal ``_MISSING`` sentinel to raise
                ``JKeyError`` instead. Defaults to ``None``.
            row (Optional[int], optional): The key's known row id, to skip the
                key-table lookup. Defaults to ``None``.
            copy (bool, optional): Return a deep copy when the value comes
                from (or enters) the cache. Defaults to ``True``.

        Returns:
            Any: The deserialized value, or ``default_val``.
        """
        key = str(key) if not isinstance(key, str) else key

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        key_table = io.key_table
        # Priority: cache > file
        _cache = self._cache
        if _cache:
            _row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
            if row is None or _row == row:
                val = _cache.get(key, _MISSING)
                if val is not _MISSING:
                    _cache.move_to_end(key, last=True)
                    return deepcopy(val) if copy else val

        if row is None:
            row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
            if row < 0:
                if default_val is not _MISSING:
                    return default_val

                raise JKeyError(key)

        if row >= io.n_records: # pragma: no cover
            if isinstance(key_table, KeyTable):
                key_table.pop(key, fp=key_fp)
            else:
                key_table.pop(key, -1)

            if default_val is not _MISSING:
                return default_val

            raise JKeyError(key)

        _key, file_id, offset, row_size, val_size, _ver, _days = io.read_key(key_fp, row)
        if key != _key:
            if _cache:
                val = _cache.get(_key, _MISSING)
                if val is not _MISSING:
                    _cache.move_to_end(_key, last=True)
                    return deepcopy(val) if copy else val

        if row_size == 0:
            val = self._decode_row(file_id, offset, _key, val_size)
        else:
            val_fp, __i, __o  = self.f_get_val_fp(fp_dict, file_id)
            try:
                val = io.read_value(val_fp, offset, row_size, val_size)

            except Exception as e: # pragma: no cover
                raise JValueError from e

        if self._cache_limit == 0:
            return val

        self._update_cache(_key, val, copy=False)
        return deepcopy(val) if copy else val

    def f_load_keys(self, fp_dict:Dict[int,IO], force:bool=False):
        """Load the key table from the KEY file into memory, opening the file
        (or creating a fresh one) if needed. The load is skipped when the
        in-memory copy is already up to date, unless ``force`` is set.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            force (bool, optional): Reload even if the in-memory copy appears
                up to date. Defaults to ``False``.
        """
        key_fp = fp_dict.get(-1, None)
        if key_fp is None:
            files_obj = self.files_obj
            try:
                key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

            except FileNotFoundError: # pragma: no cover
                io, key_fp = self._init_KEY()
                fp_dict[-1] = key_fp
        else:
            key_fp.seek(0)

        io = self.io.read_header(key_fp)
        if force or not io.is_updated():
            io.load_keys(key_fp, force=force)
            self._cache.clear()
            self.fsize = io.file_size

    def f_find_keys(self, fp_dict:Dict[int,IO], pattern:Union[str,Pattern], **kwargs) -> Set[str]:
        """Return every key matching a regular expression (``re.search``).

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            pattern (Union[str, Pattern]): A compiled pattern, or a pattern
                string compiled with ``**kwargs`` (e.g. ``flags=re.I``).

        Returns:
            Set[str]: The matching keys.
        """
        if isinstance(pattern, Pattern):
            pass
        elif isinstance(pattern, str):
            pattern = re_compile(pattern, **kwargs)
        else:
            raise JTypeError(pattern)

        io, fp_dict, _key_fp = self.f_get_fp(fp_dict)
        matches = set()
        for key in io.key_table:
            if pattern.search(key):
                matches.add(key)

        return matches

    def f_read_status(self, fp_dict:Dict[int,IO], key:str, ver:int) -> Tuple[str,int]:
        """Report a key's change status relative to a known version.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            key (str): The key to check.
            ver (int): The last version known to the caller, or ``None`` to
                just fetch the current version.

        Returns:
            Tuple[str, int]: ``(status, version)`` where status is
            ``''`` = unchanged (or current version when ``ver`` is ``None``),
            ``'!'`` = changed, ``'-'`` = deleted (version of the deletion),
            ``'x'`` = does not exist.
        """
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        key_table = io.key_table
        row = key_table[key] if not isinstance(key_table, KeyTable) else key_table.get(key, -1, fp=key_fp)
        if row < 0:
            for (_key, _f, _o, _r, _v, _ver, _d) in io.KEY_iter(key_fp, io.n_records, io.n_lines):
                if _key == key:
                    return ('-', _ver) # deleted

            return ('x', io._sync_id) # Not exist

        if row >= io.n_records: #  pragma: no cover
            if isinstance(key_table, KeyTable):
                key_table.pop(key, fp=key_fp)
            else:
                key_table.pop(key, -1)
            return ('x', io._sync_id) # Not exist

        _key, _f, _o, _r, _v, _ver, _d = io.read_key(key_fp, row)
        if ver is None:
            return ('', _ver) # get status and current version

        if ver == _ver:
            return ('', ver) # No change

        return ('!', _ver) # changed

    def f_get_fp(self, fp_dict:Optional[Dict[int,IO]]) -> Tuple[JIo,Dict[int,IO],IO]:
        """Ensure the KEY file is open for the current thread and return the
        working handles. If the KEY file was not open yet it is opened (or
        created) and the key table is reloaded when out of date.

        Args:
            fp_dict (Optional[Dict[int, IO]]): The thread's file-pointer
                table; ``None`` looks up the current thread's table.

        Returns:
            Tuple[JIo, Dict[int, IO], IO]: ``(io, fp_dict, key_fp)`` — the IO
            engine, the file-pointer table, and the open KEY file pointer.
        """
        if fp_dict is None:
            ident = get_ident()
            fp_dict = self.fp_table[ident]

        io = self.io
        key_fp = fp_dict.get(-1, None)
        if key_fp is None:
            files_obj = self.files_obj
            try:
                io.update_days()
                is_latest = files_obj.KEY_size() == io.file_size
                key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)
                data_type = io._data_type
                io.read_header(key_fp)
                if not is_latest or not io.is_updated():
                    io.load_keys(key_fp, force=data_type == 0)
                    self._cache.clear()
                    self.fsize = io.file_size

            except FileNotFoundError:
                io, key_fp = self._init_KEY()
                fp_dict[-1] = key_fp

        return io, fp_dict, key_fp

    def f_get_val_fp(self, fp_dict:Dict[int,IO], file_id:Optional[int]=None, req_size:Optional[int]=None, max_fp:int=32) -> Tuple[IO,int,int]:
        """Open (or reuse) the VAL data file identified by ``file_id`` for the
        current thread. When ``file_id`` is ``None``, pick a VAL file with at
        least ``req_size`` free bytes, creating a new one when all existing
        files are full. Excess VAL file pointers beyond ``max_fp`` are closed
        first (the KEY pointer is never closed).

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            file_id (Optional[int], optional): VAL file id to open, or ``None``
                to pick one with enough free space. Defaults to ``None``.
            req_size (Optional[int], optional): Bytes required when picking a
                file. Defaults to ``1024``.
            max_fp (int, optional): Maximum number of VAL file pointers kept
                open per thread. Defaults to ``32``.

        Returns:
            Tuple[IO, int, int]: ``(val_fp, file_id, offset)`` — the open VAL
            file pointer, its file id, and the file's current used size.
        """
        io = self.io
        file_table = io.file_table
        if req_size is None:
            req_size = 1024

        if file_id is None:
            max_file_size = io.max_file_size
            num_files = len(file_table)
            step = max(1, num_files//4)
            file_id = max(0, num_files-1)
            while True:
                offset = file_table.get(file_id, 0)
                if offset+req_size <= max_file_size:
                    break

                file_id -= step
                if file_id < 0:
                    # new VAL file, start from 0
                    file_id = num_files
                    offset = 0
                    break
        else:
            offset = file_table.get(file_id, 0)

        if file_id not in fp_dict:
            file_lock = self.file_lock
            files_obj = self.files_obj

            num_fp = len(fp_dict) - max_fp
            if num_fp > 0:
                for _id in list(fp_dict):
                    if _id < 0:
                        continue

                    fp = fp_dict.get(_id, None)
                    if fp is not None:
                        fp.close()

                    fp_dict.pop(_id, None)
                    num_fp -= 1
                    if num_fp <= 0:
                        break

            try:
                if file_lock.mode != 'w':
                    val_fp = fp_dict[file_id] = files_obj.VAL_open(file_id, 'rb', buffering=VAL_FILE_BUF_SIZE)
                else:
                    val_fp = fp_dict[file_id] = files_obj.VAL_open(file_id, 'rb+', buffering=0)

            except FileNotFoundError: # pragma: no cover
                self._init_VAL(file_id)
                if file_lock.mode != 'w':
                    val_fp = fp_dict[file_id] = files_obj.VAL_open(file_id, 'rb', buffering=VAL_FILE_BUF_SIZE)
                else:
                    val_fp = fp_dict[file_id] = files_obj.VAL_open(file_id, 'rb+', buffering=0)
        else:
            val_fp = fp_dict[file_id]

        return val_fp, file_id, offset

    def f_key_iter(self, fp_dict:Dict[int,IO], slice_obj:Union[slice, dt_date, datetime, Condition]) -> Generator[Tuple[str,tuple], None, None]:
        """Iterate over keys and their stored metadata for a slice / date /
        Condition filter (resolved by :meth:`f_slice`).

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            slice_obj (Union[slice, dt_date, datetime, Condition]): The filter;
                see :meth:`JDbKey.item_iter` for the accepted slice forms.

        Yields:
            (str, tuple): ``key, (row_id, file_id, offset, row_size, val_size,
            version, days, modified_date, created_date)``. When a version
            (float) slice includes dead/history rows, their keys are yielded
            decorated as ``'|<key>|~~<ver>~\t\t'`` so they cannot collide with
            live keys.
        """
        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        n_records = io.n_records
        io_conv_date = io.z_conv_date
        io_read_key = io.read_key
        new_slice, max_ver, min_ver, max_date, min_date, key_rules, chk_new_date = self.f_slice(fp_dict, slice_obj)
        start, stop, step = new_slice.start, new_slice.stop, new_slice.step
        if key_rules:
            for _key,row_id in io.sorted_key_table_items(start_row=start, stop_row=stop):
                if not match_KEY_rules(_key, key_rules):
                    continue

                key_fp = fp_dict[-1]
                __key, file_id, offset, row_size, val_size, ver, days = io_read_key(key_fp, row_id)
                if not max_ver > ver >= min_ver:
                    continue

                old_date, new_date = io_conv_date(days)
                if chk_new_date and (min_date and new_date < min_date or max_date and new_date >= max_date) or \
                        not chk_new_date and (min_date and old_date < min_date or max_date and old_date >= max_date): # pragma: no cover
                    continue

                yield __key, (row_id, file_id, offset, row_size, val_size, ver, days, str(new_date), str(old_date))

        else:
            for row_id in range(start, stop, step):
                key_fp = fp_dict[-1]
                _key, file_id, offset, row_size, val_size, ver, days = io_read_key(key_fp, row_id)
                if not max_ver > ver >= min_ver:
                    continue

                old_date, new_date = io_conv_date(days)
                if chk_new_date and (min_date and new_date < min_date or max_date and new_date >= max_date) or \
                        not chk_new_date and (min_date and old_date < min_date or max_date and old_date >= max_date):
                    continue

                if row_id >= n_records:
                    _key = f'|{_key}|~~{ver}~\t\t'

                yield _key, (row_id, file_id, offset, row_size, val_size, ver, days, str(new_date), str(old_date))

    def f_items(self, fp_dict:Dict[int,IO], with_value:bool=True, reverse:bool=False) -> Generator[Tuple[str,Any], None, None]:
        """Iterate over all active ``(key, value)`` pairs in row order, reading
        the KEY file in large blocks for speed.

        Note: cached values are yielded by reference (no deep copy); do not
        mutate them in place.

        Args:
            fp_dict (Dict[int, IO]): The thread's open file-pointer table.
            with_value (bool, optional): Decode each row's value; when
                ``False`` the value is ``None``. Defaults to ``True``.
            reverse (bool, optional): Iterate rows in reverse order.
                Defaults to ``False``.

        Yields:
            (str, Any): Each record's key and value (or ``None``).
        """
        n_records = self.io.n_records
        if n_records > 0:
            io, fp_dict, key_fp = self.f_get_fp(fp_dict)
            _cache = self._cache
            _decode_row = self._decode_row
            f_get_val_fp = self.f_get_val_fp
            io_read_value = io.read_value
            for (key, file_id, offset, row_size, val_size, _ver, _days) in io.KEY_iter(key_fp, 0, n_records, reverse=reverse):
                if not with_value:
                    yield key, None
                    continue

                val = _cache.get(key, _MISSING)
                if val is not _MISSING:
                    _cache.move_to_end(key, last=True)
                    yield key, val
                    continue

                if row_size == 0:
                    yield key, _decode_row(file_id, offset, key, val_size)
                    continue

                val_fp, __i, __o  = f_get_val_fp(fp_dict, file_id)
                try:
                    yield key, io_read_value(val_fp, offset, row_size, val_size)
                except Exception as e: # pragma: no cover
                    raise JValueError from e

    def _init_KEY(self) -> Tuple[JIo,IO]:
        """Create (or truncate) the KEY file, reset the IO state and cache,
        and write a fresh header. All existing records are discarded.

        Returns:
            Tuple[JIo, IO]: ``(io, key_fp)`` — the reset IO engine and the
            newly opened KEY file pointer (positioned at 0).
        """
        io = self.io
        key_fp = self.files_obj.KEY_open('wb+', buffering=KEY_FILE_BUF_SIZE)
        io.reset()
        self._cache.clear()
        self.fsize = io.write_header(key_fp)
        key_fp.seek(0)
        return io, key_fp

    def _init_VAL(self, file_id:int): # pragma: no cover
        """Create an empty VAL data file for the given file id.

        Args:
            file_id (int): The VAL file id to create.
        """
        val_fp = None
        try:
            val_fp = self.files_obj.VAL_open(file_id, 'wb', buffering=0)

        finally:
            if val_fp is not None:
                val_fp.close()

    def _decode_row(self, file_id:int, offset:int, key:str, val_size:int=0) -> Any:
        """
        Decode a value that was packed inline into the KEY row's metadata
        fields (``row_size == 0``) instead of the VAL file — the reverse of
        :meth:`_encode_row`. See that method's table for the type-id layout.

        Args:
            file_id (int): Inline type id (``0x00`` = empties/None,
                ``0x01`` = bool, ``0x02``/``0x03`` = int, ``0x04`` = float,
                ``0x08``/``0x09`` = serialized bytes <= 8, high-bit ids =
                serialized bytes <= 15, ``0x10`` = group JDb, ``0x18`` = date,
                ``0x19`` = datetime).
            offset (int): The packed payload (interpreted per ``file_id``).
            key (str): The record key (used to resolve group databases).
            val_size (int, optional): Serialized byte length for the
                bytes-payload type ids. Defaults to ``0``.

        Returns:
            Any: The decoded Python object.

        Raises:
            ValueError: If ``file_id`` is not a known inline type id.
        """
        if offset < 0: # pragma: no cover
            # BUG fixed: offset must be uint64
            offset, = _UInt64_unpack(_Int64_pack(offset))

        if file_id == 0: # None type
            if offset == 0:     return None
            if offset == 0x01:  return []
            if offset == 0x02:  return {}
            if offset == 0x04:  return set()
            if offset == 0x08:  return tuple()
            if offset == 0x10:  return ''
            if offset == 0x20:  return b''
            if offset == 0x40:  return bytearray() # pragma: no cover
            if offset == 0x100: return False # pragma: no cover
            if offset == 0x200: return 0 # pragma: no cover
            if offset == 0x400: return 0. # pragma: no cover

        if file_id == 0x01: # bool type
            return offset > 0

        if file_id == 0x02: # int type
            val, = _Int64_unpack(_UInt64_pack(offset))
            return val

        if file_id == 0x03: # uint type
            return offset

        if file_id == 0x04: # float type
            val, = _Float64_unpack(_UInt64_pack(offset))
            return val

        if 0x09 >= file_id >= 0x08: # ANY type(8 bytes)
            _bytes = _UInt64_pack(offset)
            if val_size > 0:
                return self.io.loads_with_unzip(_bytes[:val_size], zip_type=-1)

            return self.io.loads_with_unzip(_bytes, zip_type=0)

        if file_id & 0x01_000000_00000000: #ANY type(15 bytes)
            _bytes = _UInt64_x2_pack(offset, file_id)
            if val_size > 0:
                return self.io.loads_with_unzip(_bytes[:val_size], zip_type=-1)

            return self.io.loads_with_unzip(_bytes[:-1], zip_type=0)

        if file_id == 0x10: # JDb
            io = self.io
            jdb = self.childs.get(key, None)
            if isinstance(jdb, JDbReader):
                return jdb

            jdb = io.groups[key]
            if jdb is None:
                io.groups[key] = jdb = self.create_jdb(KEY_file=self.files_obj.create_group(key))

            return jdb

        if file_id == 0x18: # dt.date
            return dt_date.fromordinal(offset)

        if file_id == 0x19: # dt.datetime
            val, = _Float64_unpack(_UInt64_pack(offset))
            return datetime.fromtimestamp(val)

        raise ValueError

    def _encode_row(self, key:str, val:Any) -> Tuple[int,Union[int,bytes],int]:
        """
        Choose how to store a value: pack it inline into the KEY row's 8-byte
        metadata fields when possible (see the type-id table below), or
        serialize (and optionally compress) it for the VAL file.
        +---------------------------+----------------------------------+
        | type_id = file_id (uint64)| type_val = offset (uint64)       |
        +===========================+==================================+
        | 0x0000                    | None                             |  [0x00]
        +===========================+==================================+
        | 0x0001                    | bool                             |  [0x01]
        +===========================+==================================+
        |                           | int  (sign+63bit)                |  [0x02] -2**63 <= i <= 2**63-1
        | 0x0002 ~ 0x0003  (1)      +----------------------------------+
        |                           | uint (64bit)                     |  [0x03] 2**64-1
        +===========================+==================================+
        |                           | float                            |  [0x04] -1.7976931348623157e+308 <= f <= 1.7976931348623157e+308
        | 0x0004 ~ 0x0007  (2)      +----------------------------------+
        |                           | RESERVED                         |  [0x05 ~ 0x07]
        +===========================+==================================+
        |                           | bytes J,M,P,S for VAL (n<=8)     |  [0x08, 0x09]
        | 0x0008 ~ 0x000f  (3)      +----------------------------------+
        |                           | object RESERVED                  |  [0x0a ~ 0x0f]
        +===========================+==================================+
        |                           | object JDb                       |  [0x10]
        |                           +----------------------------------+
        |                           | object RESERVED                  |  [0x11 ~ 0x17]
        | 0x0010 ~ 0x001f  (4)      +----------------------------------+
        |                           | object date                      |  [0x18]
        |                           +----------------------------------+
        |                           | object datetime                  |  [0x19]
        |                           +----------------------------------+
        |                           | object RESERVED                  |  [0x1a ~ 0x1f]
        +===========================+==================================+
        | 0x01000000_00000000       |                                  |
        | 0x01ffffff_ffffffff (56)  | bytes J,M,P,S for VAL (n<=15)    |
        +---------------------------+----------------------------------+
    
        Args:
            key (str): The record key (used to register group databases).
            val (Any): The value to encode.

        Returns:
            Tuple[int, Union[int, bytes], int]: ``(type_id, payload, n_bytes)``.
            For inline values: the type id, the packed integer payload, and
            the serialized length (``0`` for primitives). For VAL-file values:
            ``-1``, the serialized (possibly compressed) ``bytes``, and the
            uncompressed length.
        """
        is_jdb = isinstance(val, JDbReader)
        if not is_jdb and not val:
            if val is None:         return (0, 0, 0)

            _type = type(val)
            if _type is list:       return (0, 0x01, 0)
            if _type is dict:       return (0, 0x02, 0)
            if _type is set:        return (0, 0x04, 0)
            if _type is tuple:      return (0, 0x08, 0)
            if _type is str:        return (0, 0x10, 0)
            if _type is bytes:      return (0, 0x20, 0)
            if _type is bytearray:  return (0, 0x40, 0)
            # if _type is bool:     return (0, 0x100, 0)
            # if _type is int:      return (0, 0x200, 0)
            # if _type is float:    return (0, 0x400, 0)
        else:
            # 0x10 ~ 0x1f
            if is_jdb:
                io = self.io
                if key not in io.groups and self.files_obj.is_group(val.files_obj, key):
                    io.groups[key] = val
                    self.childs.pop(key, None)

                return (0x10, 0, 0)

            _type = type(val)

        if _type is bool:
            return (0x01, 1 if val else 0, 0)

        # 0x02 ~ 0x03
        if _type is int:
            if val < 0:
                type_val, = _UInt64_unpack(_Int64_pack(val))
                return (0x02, type_val, 0)

            return (0x03, val, 0)

        # 0x04 ~ 0x07
        if _type is float:
            type_val, = _UInt64_unpack(_Float64_pack(val))
            return (0x04, type_val, 0)

        # 0x18, 0x19
        if _type is dt_date:
            return (0x18, val.toordinal(), 0)

        if _type is datetime:
            type_val, = _UInt64_unpack(_Float64_pack(val.timestamp()))
            return (0x19, type_val, 0)

        io = self.io
        _bytes = io.dumps_with_zip(val, zip_type=0)
        n_bytes = len(_bytes)

        # 0x08 ~ 0x0f
        if io.row_bytes >= 0 and n_bytes <= 15:
            if n_bytes <= 8:
                _bytes = io.pad(_bytes, max_size=8, no_zip=True)
                type_val, = _UInt64_unpack(_bytes)
                return (0x08, type_val, n_bytes)

            _bytes = io.pad(_bytes, max_size=15, no_zip=True) + b'\x01'
            type_val, type_id = _UInt64_x2_unpack(_bytes)
            return (type_id, type_val, n_bytes)


        return (-1, _bytes if io._zip_type == 0 else io.zip(_bytes, zip_type=io._zip_type), n_bytes)

#
