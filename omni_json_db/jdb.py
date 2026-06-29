from __future__ import annotations # pylint: disable=too-many-lines
from datetime import date as dt_date, datetime
from re import match as re_match, Pattern
from os.path import exists as path_exists
from os import stat as os_stat
from time import time, sleep
from typing import Any, Union, Optional, Tuple, Dict, List, Set, Callable, IO
from random import randint, randrange
from csv import DictReader, DictWriter
from collections import OrderedDict
from configparser import ConfigParser
from sqlite3 import connect as sql_connect, Row as sql_Row, Connection
#-----------------------------------------------------------------------------
try:
    from tomllib import loads as toml_loads
except ImportError: # pragma: no cover
    try:
        from tomli import loads as toml_loads
    except ImportError:
        toml_loads = None
#-----------------------------------------------------------------------------
from .jdb_io import JIo, MIN_INDEX_SIZE, VAL_FILE_BUF_SIZE, KEY_FILE_BUF_SIZE,\
            MAX_KEY_SIZE, API_LATEST, CHG_DAY_FLAG, NEW_DAY_MASK, OLD_DAY_MASK,\
            MAX_INDEX_SIZE, g_VAL_J, g_VAL_S, g_VAL_M, g_VAL_P, g_VAL_Y, NEW_DAY_SHIFT
from .jdb_lite import JDbReader, JDbKey, JFlag, SEP_SYM, SEP_LEN
from .utils import Style, JValueError, JKeyError, JTypeError, deepcopy
from .jdb_file import JFilesBase
from .jdb_query import Condition

MAX_BLOCK_SIZE = 2**20
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JDbKey2(JDbKey):
    """Extended read-write key navigation proxy subsystem handling conditional timeline transformations."""

    def __setitem__(self, key:Union[str,Any], val:Union[str,int,datetime,dt_date]) -> None:
        """Modify the calendar tracking metrics associated with specific database keys dynamically.

        Processes complex queries including string identifiers, regex targets, or filtering lambdas.

        Args:
            key (Union[str, Any]): Unique selection text string, compiled regex pattern, callable condition filter, or historical slice.
            val (Union[str, int, datetime, dt_date]): Normalized time token descriptor, datetime instance, or calculated days integer.

        Raises:
            TypeError: If the incoming value or functional keys violate standard layout validation parameters rules.
        """
        jdb = self.jdb
        #pass;0;assert isinstance(jdb, JDb)
        if isinstance(val, str): # pragma: no cover
            val = JIo.z_conv_str_to_days(val)

        elif isinstance(val, datetime): # before dt_date
            val = JIo.z_conv_days(val)

        elif isinstance(val, dt_date):
            val = JIo.z_conv_days(val) << NEW_DAY_SHIFT

        if not isinstance(val, int):
            raise TypeError

        if isinstance(key, Pattern):
            is_matched = key.search
            k_arg_cnt = 1

        elif callable(key):
            is_matched = key
            k_arg_cnt = is_matched.__code__.co_argcount
            if not 2 >= k_arg_cnt >= 1:
                raise TypeError('invalid function {k_arg_cnt}')

        else:
            is_matched = None
            k_arg_cnt = 0

        with jdb.open(read_only=True) as fp:
            has_SIGINT = jdb.file_lock.has_SIGINT
            io, fp, key_fp = jdb.f_get_fp(fp)
            if isinstance(key, str):
                idx = key.find(SEP_SYM)
                if idx < 0:
                    row_id = io.key_table[key]
                    if io.n_records > row_id >= 0:
                        _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                        jdb.f_change_days(fp, _key, val)

                    return

                childs = set(io.groups).union(jdb.childs)
                if not childs:
                    return

                jdb_name, jdb_key = key[:idx], key[idx+SEP_LEN:]
                f_get_child = jdb.f_get_child
                if not jdb_name:
                    for jdb_name in childs:
                        if has_SIGINT(): break
                        child = f_get_child(fp, jdb_name)
                        if isinstance(child, JDb):
                            child.keys[jdb_key] = val
                else:
                    child = f_get_child(fp, jdb_name)
                    if isinstance(child, JDb):
                        child.keys[jdb_key] = val

                return

            if isinstance(key, int) and not isinstance(key, bool):
                n_records = io.n_records
                row_id = (n_records + key) if key < 0 else key
                if n_records > row_id >= 0:
                    _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                    jdb.f_change_days(fp, _key, val)

                return

            if isinstance(key, float):
                sync_id = int(key)
                sync_id = (io.sync_id + sync_id) if sync_id < 0 else sync_id
                if not (sync_id >= io.sync_id or sync_id < 0):
                    io, fp, key_fp, _sync_chg = jdb.f_get_write_fp(fp)
                    io_read_key = io.read_key
                    for row_id in range(io.n_records):
                        if has_SIGINT(): break
                        _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                        if ver == sync_id:
                            jdb.f_change_days(fp, _key, val)
                return

            if isinstance(key, (bytes, bytearray)): # pragma: no cover
                key = bytes(key) if isinstance(key, bytearray) else key
                try:
                    key = key.decode('utf8')
                except (UnicodeDecodeError, ValueError):
                    key = str(key)

            elif isinstance(key, (slice, dt_date, datetime, Condition)):
                matched_keys = [_key for _key,_val in jdb.find_iter(key)] if isinstance(key, Condition) else \
                                [_key for _key,_info in jdb.f_key_iter(fp, key)]

                if matched_keys:
                    io, fp, key_fp, _sync_chg = jdb.f_get_write_fp(fp)
                    for _key in matched_keys:
                        if has_SIGINT(): break
                        jdb.f_change_days(fp, _key, val)

                return

            elif callable(is_matched):
                if k_arg_cnt == 2:
                    io_read_key = io.read_key
                    io_conv_date = io.z_conv_date
                    for row_id in range(io.n_records):
                        if has_SIGINT():
                            break

                        _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                        if val != days:
                            old_date, new_date = io_conv_date(days)
                            if is_matched(_key, (file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))):
                                jdb.f_change_days(fp, _key, val)
                                io, fp, key_fp = jdb.f_get_fp(fp) # key_fp is changed after switch to write mode

                elif k_arg_cnt == 1:
                    io_read_key = io.read_key
                    for _key,row_id in io.sorted_key_table_items():
                        if has_SIGINT():
                            break

                        if is_matched(_key):
                            _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                            if days != val:
                                jdb.f_change_days(fp, _key, val)
                                io, fp, key_fp = jdb.f_get_fp(fp) # key_fp is changed after switch to write mode

                return

            elif hasattr(key, '__iter__'):
                done = set()
                has_childs = len(io.groups) > 0 or len(jdb.childs) > 0
                io, fp, key_fp, _sync_chg = jdb.f_get_write_fp(fp)
                key_table = io.key_table
                n_records = io.n_records
                for _key in key:
                    if isinstance(_key, (int, float)):
                        row_id = int(_key)
                        row_id = (n_records + row_id) if row_id < 0 else row_id
                        if n_records > row_id >= 0:
                            _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                            jdb.f_change_days(fp, _key, val)

                        continue

                    _key = str(_key)
                    if _key not in done:
                        done.add(_key)
                        row_id = key_table[_key]
                        if row_id < 0:
                            if has_childs and _key.find(SEP_SYM) >= 0:
                                jdb.keys[_key] = val

                            continue

                        jdb.f_change_days(fp, _key, val)

                return

            # bytes | bytearray | bool
            if not isinstance(key, str): # pragma: no cover
                key = str(key)
                row_id = io.key_table[key]
                if row_id >= 0:
                    jdb.f_change_days(fp, key, val)

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class JDb(JDbReader):
    """Main Database controller managing reading, writing, transaction rollbacks, and multi-part data compaction pipelines.

    Ensures data consistency under high concurrent load using fine-grained file-level system locking primitives.
    """
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
        Initialize the transactional JDb controller object mapping configurations sheets models.

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

        Example:
            >>> jdb = JDb() # in-memory mode
            >>> jdb = JDb('192.168.0.1:8181') # Network mode
            >>> jdb = JDb('file.jdb') # file mode
            >>> jdb = JDb('example.jdb', data_type='J+J', zip_type='gz')
        
        """
        super().__init__(KEY_file=KEY_file,
            min_value_size=min_value_size,
            max_file_size=max_file_size,
            index_size=index_size,
            reserved_rate=reserved_rate,
            cache_limit=cache_limit,
            key_limit=key_limit,
            data_type=data_type,
            zip_type=zip_type,
            api_ver=api_ver,
            JDbKey_obj=kwargs.pop('JDbKey_obj', JDbKey2(self)),
            write_hook=write_hook,
            max_wsize=max_wsize,
            flags=flags,
            **kwargs)

    def __setitem__(self, key:Union[str,Any], val:Any):
        """Commit or modify entry content mapping values utilizing scalar indicators, regex arrays or functions parameters.

        Args:
            key (Union[str, Any]): Target database lookups selection token lookup identifier or filter schema block query criteria fields.
                
                - str | int | float | bool | bytes
                    
                    >>> jdb['name'] = val

                - Condition

                    >>> User = Query()
                    >>> jdb[User.name == 'Alice'] = val
            
                - slice | date | datetime
                    
                    >>> jdb[1:10:2] = val
                    >>> jdb[-10.:] = val
                    >>> jdb[:] = val
                    >>> jdb[date(2020,1,1)::r'key[0-9]'] = val
                    >>> jdb[:100:r'key[0-9]'] = val
                    >>> jdb[date(2020,1,1)] = val
                    >>> jdb[datetime(2020,1,1)] = val
            
                - function(k,v)
                    
                    >>> jdb[lambda k,v: k.startswith('key') and v > 0] = val
                    >>> jdb[lambda k,v: v == 10] = val
            
                - function(k)
                    
                    >>> jdb[lambda k: k[0] == 'k'] = val
            
                - re.Pattern
                    
                    >>> jdb[re.compile(r'key[0-9]')] = val
            
                - tuple | set | list | dict
                    
                    >>> jdb['a', 'b', 'c', 'd'] = val | func
                    >>> jdb[('a', 'b'', 'c', 'd')] = val | func
                    >>> jdb[{'a', 'b'', 'c', 'd'}] = val | func
                    >>> jdb[['a', 'b'', 'c', 'd']] = val | func
                    >>> jdb[{'a':0, 'b':1, 'c':2, 'd':3}] = val | func

            val (Any): Payload value context or updating mutation callback functional lambda routine.

                - any type but function
                    
                    >>> jdb['name'] = val
            
                - function(k,v)
                    
                    >>> jdb['name'] = lambda k,v : v+1
                    >>> jdb['name'] = lambda k,v : v+1 if v is not None else None # replace if exist
                    >>> jdb['name'] = lambda k,v : v if v is not None else 1 # insert if not exist        

        Raises:
            TypeError: If input validation layers discover corrupted lambda parameter signatures rules or mismatched data types.

        Example:
            >>> jdb['name'] = 'Charlie'
            >>> jdb[lambda k,v: v == 10] = 11
            >>> jdb[1:10:2] = "updated"
        """
        if isinstance(key, str):
            idx = key.find(SEP_SYM)
            if idx >= 0:
                with self.open(read_only=True) as fp:
                    io, fp, _key_fp = self.f_get_fp(fp)
                    childs = set(io.groups).union(self.childs)
                    if childs and key not in self.io.key_table:
                        jdb_name, jdb_key = key[:idx], key[idx+SEP_LEN:]
                        f_get_child = self.f_get_child
                        if not jdb_name:
                            has_SIGINT = self.file_lock.has_SIGINT
                            for jdb_name in childs:
                                if has_SIGINT(): break
                                child = f_get_child(fp, jdb_name)
                                if isinstance(child, JDb):
                                    child[jdb_key] = val
                        else:
                            child = f_get_child(fp, jdb_name)
                            if isinstance(child, JDb):
                                child[jdb_key] = val

                        return

        if callable(val):
            func = val
            arg_cnt = func.__code__.co_argcount
            if arg_cnt != 2:
                raise TypeError
        else:
            func = None

        if isinstance(key, Pattern):
            is_matched = key.search
            k_arg_cnt = 1

        elif callable(key):
            is_matched = key
            k_arg_cnt = is_matched.__code__.co_argcount
            if not 2 >= k_arg_cnt >= 1:
                raise TypeError('invalid function {k_arg_cnt}')
        else:
            k_arg_cnt = 0

        with self.open(read_only=True) as fp:
            io = self.io
            if isinstance(key, str):
                if func:
                    row_id = io.key_table[key]
                    old_val = None if row_id < 0 else self.f_read(fp, key, row=row_id, copy=False)
                    new_val = func(key, deepcopy(old_val))
                    if new_val != old_val:
                        self.f_write(fp, key, new_val)
                else:
                    self.f_write(fp, key, val)

                return

            if isinstance(key, (bytes, bytearray)): # pragma: no cover
                key = bytes(key) if isinstance(key, bytearray) else key
                try:
                    key = key.decode('utf8')
                except (UnicodeDecodeError, ValueError):
                    key = str(key)

            elif isinstance(key, (slice, dt_date, datetime, Condition)):
                matched_keys = [_key for _key,_val in self.find_iter(key)] if isinstance(key, Condition) else \
                                [_key for _key,_info in self.f_key_iter(fp, key)]

                if matched_keys:
                    io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
                    has_SIGINT = self.file_lock.has_SIGINT
                    f_write = self.f_write
                    if func:
                        f_read = self.f_read
                        key_table = io.key_table
                        for _key in matched_keys:
                            if has_SIGINT(): break
                            row_id = key_table[_key]
                            old_val = None if row_id < 0 else f_read(fp, _key, row=row_id, copy=True)
                            new_val = func(_key, deepcopy(old_val))
                            if new_val != old_val:
                                f_write(fp, _key, new_val)

                    else:
                        for _key in matched_keys:
                            if has_SIGINT(): break
                            f_write(fp, _key, val)

                return

            elif k_arg_cnt > 0:
                keys = {}
                f_read = self.f_read
                for _key,row_id in io.sorted_key_table_items():
                    if k_arg_cnt == 2:
                        old_val = f_read(fp, _key, row=row_id, copy=False)
                        _is_matched = is_matched(_key, old_val)
                    else:
                        _is_matched = is_matched(_key)
                        old_val = f_read(fp, _key, row=row_id, copy=False) if _is_matched else None

                    if _is_matched:
                        if func:
                            new_val = func(_key, deepcopy(old_val))
                            if new_val != old_val:
                                keys[_key] = new_val

                        elif old_val != val:
                            keys[_key] = val

                if keys:
                    has_SIGINT = self.file_lock.has_SIGINT
                    f_write = self.f_write
                    for _key,_val in keys.items():
                        if has_SIGINT(): break
                        f_write(fp, _key, _val)

                return

            # tuple | list | set | dict
            elif hasattr(key, '__iter__'):
                has_SIGINT = self.file_lock.has_SIGINT
                has_childs = len(io.groups) > 0 or len(self.childs) > 0
                f_read = self.f_read
                f_write = self.f_write
                done = set()
                key_table = io.key_table
                for _key in key:
                    _key = str(_key)
                    if _key in done: # pragma: no cover
                        continue

                    done.add(_key)
                    if has_SIGINT(): break
                    row_id = key_table[_key]
                    if has_childs and row_id < 0 and _key.find(SEP_SYM) >= 0: # pylint: disable=R
                        self[_key] = val
                        continue

                    if func:
                        old_val = None if row_id < 0 else f_read(fp, _key, row=row_id, copy=False)
                        new_val = func(_key, deepcopy(old_val))
                        if new_val != old_val:
                            f_write(fp, _key, new_val)
                    else:
                        f_write(fp, _key, val)

                return

            else:
                key = str(key)

            # int | float | bool
            if func:
                row_id = io.key_table[key]
                old_val = None if row_id < 0 else self.f_read(fp, key, row=row_id, copy=False)
                new_val = func(key, deepcopy(old_val))
                if new_val != old_val:
                    self.f_write(fp, key, new_val)
            else:
                self.f_write(fp, key, val)

    def __delitem__(self, key:Union[str,Any]):
        """Physically drop or unlink selected record entries spaces from database index tracking registries.

        Args:
            key (Union[str, Any]): Unique entry character label token text descriptor, query filter conditional lambda function, regex sequence pattern, or subset iterable sequence.

                - str | int | float | bool | bytes
                    
                    >>> del jdb['name']

                - Condition

                    >>> user = Query()
                    >>> del jdb[user.age >= 40]
            
                - slice | date | datetime
                    
                    >>> del jdb[1:10:2]
                    >>> del jdb[-10.:]
                    >>> del jdb[:]
                    >>> del jdb[dt.date(2020,1,1)::r'key[0-9]']
                    >>> del jdb[:100:r'key[0-9]']
                    >>> del jdb[date(2020,1,1)]
                    >>> del jdb[datetime(2020,1,1)]
            
                - function(k,v)
                    
                    >>> del jdb[lambda k,v: k.startswith('key')]
                    >>> del jdb[lambda k,v: v == 10] = val
            
                - function(k)
                    
                    >>> del jdb[lambda k: k[0] == 'k']
            
                - re.Pattern
                    
                    >>> del jdb[re.compile(r'key[0-9]')]
            
                - tuple | set | list | dict
                    
                    >>> del jdb['a', 'b', 'c', 'd']
                    >>> del jdb[('a', 'b', 'c', 'd')]
                    >>> del jdb[{'a', 'b', 'c', 'd'}]
                    >>> del jdb[['a', 'b', 'c', 'd']]
                    >>> del jdb[{'a':0, 'b':1, 'c':2, 'd':3}]

        Raises:
            TypeError: If lookups evaluation candidates strike unrecognizable parameter types rules boundaries models.

        Example:
            >>> del jdb[:] # delete all records
            >>> del jdb['name']
            >>> del jdb[lambda k,v: k.startswith('temp_')]
        """
        if isinstance(key, str):
            idx = key.find(SEP_SYM)
            if idx >= 0:
                with self.open(read_only=True) as fp:
                    io, fp, _key_fp = self.f_get_fp(fp)
                    childs = set(io.groups).union(self.childs)
                    if childs and key not in io.key_table:
                        jdb_name, jdb_key = key[:idx], key[idx+SEP_LEN:]
                        f_get_child = self.f_get_child
                        if not jdb_name:
                            has_SIGINT = self.file_lock.has_SIGINT
                            for jdb_name in childs:
                                if has_SIGINT(): break
                                child = f_get_child(fp, jdb_name)
                                if isinstance(child, JDb):
                                    del child[jdb_key]
                        else:
                            child = f_get_child(fp, jdb_name)
                            if isinstance(child, JDb):
                                del child[jdb_key]

                        return

        if isinstance(key, Pattern):
            is_matched = key.search
            k_arg_cnt = 1

        elif callable(key):
            is_matched = key
            k_arg_cnt = is_matched.__code__.co_argcount
            if not 2 >= k_arg_cnt >= 1:
                raise TypeError

        else:
            k_arg_cnt = 0

        with self.open(read_only=True) as fp:
            io = self.io
            has_childs = len(io.groups) > 0 or len(self.childs) > 0
            del_keys = set()
            if isinstance(key, str):
                pass

            elif isinstance(key, (bytes, bytearray)): # pragma: no cover
                key = bytes(key) if isinstance(key, bytearray) else key
                try:
                    key = key.decode('utf8')
                except (UnicodeDecodeError, ValueError):
                    key = str(key)

            elif isinstance(key, Condition):
                for _key,_val in self.find_iter(key):
                    del_keys.add(_key)

                if not del_keys:
                    return

            elif isinstance(key, (slice, dt_date, datetime, Condition)):
                del_keys = {_key for _key,_val in self.find_iter(key)} if isinstance(key, Condition) else \
                            {_key for _key,_info in self.f_key_iter(fp, key)}

                if not del_keys:
                    return

            elif k_arg_cnt > 0:
                if k_arg_cnt == 2:
                    f_read = self.f_read
                    for _key,row_id in io.sorted_key_table_items():
                        val = f_read(fp, _key, row=row_id, copy=False)
                        if is_matched(_key, val):
                            del_keys.add(_key)

                elif k_arg_cnt == 1:
                    for _key,row_id in io.sorted_key_table_items():
                        if is_matched(_key):
                            del_keys.add(_key)

                if not del_keys:
                    return

            # tuple | list | set | dict
            elif hasattr(key, '__iter__'):
                key_table = io.key_table
                if has_childs:
                    del_keys = {kk if isinstance(kk, str) else str(kk) for kk in key}
                else:
                    del_keys = {kk if isinstance(kk, str) else str(kk) for kk in key}.intersection(key_table)

                if not del_keys:
                    return
            else:
                key = str(key)

            key_table = io.key_table
            if not del_keys:
                # int | float | bool | str | bytes
                key = str(key) if not isinstance(key, str) else key
                row_id = key_table[key]
                if row_id < 0:
                    raise JKeyError(key)

                del_keys = [(row_id, key)]
                io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
            else:
                io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
                del_keys = sorted([(key_table[_key], _key) for _key in del_keys], reverse=True)

            f_delete = self.f_delete
            files_obj = self.files_obj
            has_SIGINT = self.file_lock.has_SIGINT
            has_childs = len(io.groups) > 0 or len(self.childs) > 0
            for row_id,_key in del_keys:
                if has_SIGINT():
                    break

                if row_id < 0:
                    if has_childs and _key.find(SEP_SYM) >= 0: # pylint: disable=R
                        del self[_key]

                    continue

                jdb = f_delete(fp, _key, read_value=False, row=row_id)
                if isinstance(jdb, JDb) and files_obj.is_group(jdb.files_obj, _key):
                    with jdb.open(read_only=True) as jdb_fp:
                        for _row_id in range(jdb.io.n_records-1, -1, -1):
                            jdb.f_delete(jdb_fp, key='', read_value=False, row=_row_id)
        return

    def __isub__(self, keys:Set[str]) -> JDb:
        """Batch remove outstanding entries index references using LIFO strategy blocks optimization.

        Args:
            keys (Set[str]): Target dataset collection maps array or sibling JDbReader source instance candidate.

                - JDbReader
                    
                    >>> jdb -= other_jdb 
            
                - str | int | float | bool | bytes
                    
                    >>> jdb -= "name" # jdb -= {"name"}
            
                - tuple | set | list | dict
                    
                    >>> jdb -= {'a'', 'b'', 'c', 'd'}
                    >>> jdb -= ('a'', 'b'', 'c', 'd')
                    >>> jdb -= ['a'', 'b'', 'c', 'd']
                    >>> jdb -= {'a':0, 'd':1, 'c':2, 'd':3}      

        Returns:
            JDb: Self instance with specified nodes decoupled completely.

        Example:
            >>> jdb = JDb()
            >>> jdb['key1', 'key2', 'key3'] = 1
            >>> jdb -= {'key1', 'key2', 'key3'}
        """
        if isinstance(keys, JDbReader):
            with self.open(read_only=True) as fp:
                io = self.io
                n_records = io.n_records
                if n_records == 0:
                    return self

                jdb = keys
                if jdb is self or jdb.files_obj == self.files_obj:
                    has_SIGINT = self.file_lock.has_SIGINT
                    f_delete = self.f_delete
                    files_obj = self.files_obj
                    io, fp, key_fp, sync_chg = self.f_get_write_fp(fp)
                    io_read_key = io.read_key
                    for row_id in range(io.n_records-1, -1, -1):
                        if has_SIGINT(): break
                        _key, _file_id, _offset, _row_size, _val_size, _ver, _days = io_read_key(key_fp, row_id)
                        child = f_delete(fp, _key, row=row_id, read_value=False)
                        if isinstance(child, JDb) and files_obj.is_group(child.files_obj, _key):
                            child.remove_fast(child)

                    return self

                # jdb != self
                with jdb.open(read_only=True):
                    jio = jdb.io
                    if jio.n_records <= 0:
                        return self

                    ref_key_table = jio.key_table
                    key_table = io.key_table
                    while True:
                        keys = set(key_table).intersection(ref_key_table)
                        if not keys:
                            return self

                        io, fp, _key_fp, sync_chg = self.f_get_write_fp(fp)
                        if not sync_chg:
                            break

                    has_SIGINT = self.file_lock.has_SIGINT
                    f_delete = self.f_delete
                    files_obj = self.files_obj
                    del_keys = sorted([(key_table[kk], kk) for kk in keys], reverse=True)
                    for row_id,_key in del_keys:
                        if has_SIGINT() or row_id < 0:
                            break

                        child = _val = f_delete(fp, key=_key, row=row_id, read_value=False)
                        if isinstance(child, JDb) and files_obj.is_group(child.files_obj, _key):
                            with child.open(read_only=True) as child_fp:
                                for _row_id in range(child.io.n_records-1, -1, -1):
                                    child.f_delete(child_fp, key='', row=_row_id, read_value=False)

                return self

        self.__delitem__(keys)
        return self

    def __iadd__(self, records:Dict[str,Any]) -> JDb:
        """Batch load elements dictionaries mapping records directly in-place rewriting overlapping values lines.

        Args:
            records (Dict[str, Any]): Collection mapping identifiers to target value instances or iterable primitives arrays.
                
                - JDbReader
                    
                    >>> jdb += other_jdb 

                - dict == Dict[str,Any] == {key1:val1, key2:val2, ..}
                    
                    >>> jdb += {'a':1, 'b':2}
            
                - tuple | set | list == List[Any] == (val1, val2, ..)
                    
                    >>> jdb += {'a', 'b'} # jdb.update_vals({'a', 'b'})
                    >>> jdb += ('a', 'b') # jdb.update_vals(('a', 'b'))
                    >>> jdb += ['a', 'b'] # jdb.update_vals(['a', 'b'])
        
                - str | int | float | bool | bytes
                    
                    >>> jdb += 'name' # jdb['name'] = None
        
        Returns:
            JDb: Self repository context manager interface handle reference.
        
        Example:
            >>> jdb = JDb()
            >>> jdb['key1', 'key2', 'key3'] = 1
            >>> jdb += {'new_key': 99}
        """
        if isinstance(records, (JDbReader, dict)):
            self.update(records)

        elif isinstance(records, (tuple, list, set, frozenset)): # pragma: no cover
            self.append(records)

        else: # pragma: no cover
            self.__setitem__(records, None)

        return self

    def __ior__(self, records:Dict[str,Any]) -> JDb:
        """Batch insert unallocated entities matrices structures arrays in-place strictly bypassing existing nodes bounds.

        Args:
            records (Dict[str, Any]): Target context source map entries.
                
                - JDbReader
                    
                    >>> jdb |= other_jdb 

                - dict == Dict[str,Any] == {key1:val1, key2:val2, ..}
                    
                    >>> jdb |= {'a':1, 'b':2}
            
                - tuple | set | list == List[Any] == (val1, val2, ..)
                    
                    >>> jdb |= {'a', 'b'} # jdb.insert_vals({'a', 'b'})
                    >>> jdb |= ('a', 'b') # jdb.insert_vals(('a', 'b'))
                    >>> jdb |= ['a', 'b'] # jdb.insert_vals(['a', 'b'])
        
                - str | int | float | bool | bytes
                    
                    >>> jdb |= 'name' # jdb['name'] = None
        Returns:
            JDb: Self proxy repository interface controller instance framework.
        
        Example:
            >>> jdb = JDb()
            >>> jdb['key1', 'key2', 'key3'] = 1
            >>> jdb |= {'new_key': 99}
        """
        if isinstance(records, (JDbReader, dict)):
            self.insert(records)

        elif isinstance(records, (tuple, list, set, frozenset)): # pragma: no cover
            self.insert_vals(records)

        else: # pragma: no cover
            self.insert({records:None})

        return self

    def __iand__(self, records:Dict[str,Any]) -> JDb:
        """Batch update or override known elements row values data rows avoiding adding unknown outliers into index layers maps.

        Args:
            records (Dict[str, Any]): Translation adjustments dictionary mapping context models fields.

                - JDbReader
                    
                    >>> jdb &= other_jdb 

                - dict == Dict[str,Any] == {key1:val1, key2:val2, ..}
                    
                    >>> jdb &= {'a':1, 'b':2}
            
                - tuple | set | list == Tuple[Any] == (val1, val2, ..)
                    
                    >>> jdb &= {'a', 'b'} # jdb.replace_vals({'a', 'b'})
                    >>> jdb &= ('a', 'b') # jdb.replace_vals(('a', 'b'))
                    >>> jdb &= ['a', 'b'] # jdb.replace_vals(['a', 'b'])
        
                - str | int | float | bool | bytes
                    
                    >>> jdb &= 'name' # jdb['name'] = None
        Returns:
            JDb: Self database environment framework instance configuration wrapper.

        Example:
            >>> jdb = JDb()
            >>> jdb['key1', 'key2', 'key3'] = 1
            >>> jdb &= {'key1': 99}
            >>> jdb['key1']
            99
        """
        if isinstance(records, (JDbReader, dict)):
            self.replace(records)

        elif isinstance(records, (tuple, list, set, frozenset)): # pragma: no cover
            self.replace_vals(records)

        else: # pragma: no cover
            self.replace({records:None})

        return self

    def __ixor__(self, keys:Set[str]) -> JDb:
        """Revert or roll back transaction shifts processing selected node indicators parameters history blocks fields.

        Args:
            keys (Set[str]): Target indicator strings mapping historical recovery boundaries paths.

                - JDbReader
                    
                    >>> jdb ^= other_jdb 

                - str | int | float | bool | bytes
                    
                    >>> jdb ^= 'name' 
            
                - dict | tuple | set | list
                    
                    >>> jdb ^= {'a', 'b'} 
                    >>> jdb ^= ('a', 'b') 
                    >>> jdb ^= ['a', 'b'] 
                    >>> jdb ^= {'a':1, 'b':2} # == {'a', 'b}
        

        Returns:
            JDb: Self chronologically synchronized operational workspace manager proxy.

        Example:
            >>> jdb = JDb()
            >>> jdb['key1'] = 1
            >>> jdb['key1'] = 99
            >>> jdb ^= {'key1'}
            >>> jdb['key1']
            1
        """
        if isinstance(keys, str):
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
            if jdb is self or jdb.files_obj == self.files_obj:
                with self.open(read_only=True) as fp:
                    io = self.io
                    if io.n_lines == io.n_records:
                        return self

                    io, fp, key_fp, _sync_chg = self.f_get_write_fp(fp)
                    has_SIGINT = self.file_lock.has_SIGINT
                    unwrite = self.f_unwrite
                    undelete = self.f_undelete
                    key_table = io.key_table
                    io_read_key = io.read_key
                    row_id = io.n_records
                    done_set = set()
                    for row_id in range(io.n_records, io.n_lines):
                        if has_SIGINT():
                            break

                        _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                        if not (_key not in key_table or _key in done_set):
                            chg_row = unwrite(fp, _key, row=row_id)
                            if chg_row: done_set.add(_key)

                return self

            # jdb != self
            keys = set(jdb)

        elif hasattr(keys, '__iter__'):
            if not keys:
                return self

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True) as fp:
            io = self.io
            if io.n_records == io.n_lines:
                return self

            io, fp, key_fp, _sync_chg = self.f_get_write_fp(fp)
            has_SIGINT = self.file_lock.has_SIGINT
            undelete = self.f_undelete
            unwrite = self.f_unwrite
            key_table = io.key_table
            io_read_key = io.read_key
            chg_keys = keys.intersection(key_table)
            add_keys = keys.difference(key_table)
            keys.clear()
            if add_keys:
                row_id = io.n_records
                while add_keys and row_id < io.n_lines:
                    if has_SIGINT(): break

                    _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                    if _key in add_keys:
                        add_keys.remove(_key)
                        add_row = undelete(fp, _key, row=row_id)
                        if add_row:
                            row_id = io.n_records
                            continue

                    else: # pragma: no cover
                        row_id += 1

            if chg_keys:
                row_id = io.n_records
                while chg_keys and row_id < io.n_lines:
                    if has_SIGINT(): break

                    _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                    if _key in chg_keys:
                        chg_keys.remove(_key)
                        unwrite(fp, _key, row=row_id)

                    row_id += 1

        return self

    def create_jdb(self, KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None]) -> JDb:
        """Spawn a child read-write companion database instance mimicking host properties models parameters grids.

        Args:
            KEY_file (Union[str, bytearray, JFilesBase, JDbReader, None]): File path or core buffer source stream.

        Returns:
            JDb: A relative fresh JDb session workspace environment instance.
        """
        jio = self.io
        return JDb(KEY_file=KEY_file,
                    data_type=jio._data_type,
                    zip_type=jio._zip_type,
                    reserved_rate=jio.reserved_rate,
                    cache_limit=self._cache_limit,
                    key_limit=jio._key_limit,
                    min_value_size=jio.min_value_size,
                    max_file_size=jio.max_file_size,
                    index_size=jio.index_size)

    def pop(self, key:str, default_val:Optional[Any]=None) -> Any:
        """Isolate, pop, and erase an individual item record from indices returning previous python object contents.

        Args:
            key (str): Target dictionary lookup query choice token text string descriptor criteria.
            default_val (Optional[Any], optional): Fallback data assigned if lookup registers miss elements indicators. Defaults to None.

        Returns:
            Any: Unpacked Python object value, or default_val if missing from storage tables.

        Example:
            >>> previous_value = jdb.pop('key_to_remove', default_val=0)
        """
        with self.open(read_only=True) as fp:
            try:
                return self.f_delete(fp, key)

            # Not a gzipped file
            except OSError: # pragma: no cover
                self.f_delete(fp, key, read_value=False)
                return default_val

            except KeyError: # pragma: no cover
                return default_val

    def unmodify(self, *records:str) -> Dict[str,Any]:
        """Undo dynamic value row mutations rolling records states back onto prior chronological signatures logs on file layer.

        Args:
            *records (str): Variadic sequence choosing target keys or groups tracking indicators strings to restore.

        Returns:
            Dict[str, Any]: Mapping dictionary summarizing all successfully restored entities linked along previous positions data.
        
        Example:
            >>> recovered_info = jdb.unremove('accidental_delete_key')
        """
        keys = set()
        results = {}
        for key in records: # pragma: no cover
            if isinstance(key, str):
                keys.add(key)
            elif key.__hash__:
                keys.add(str(key))
            else:
                for kk in key:
                    keys.add(kk if isinstance(kk, str) else str(kk))

        if not keys:
            return results

        with self.open(read_only=True) as fp:
            io = self.io
            if io.n_records == io.n_lines:
                return results

            io, fp, key_fp, _sync_chg = self.f_get_write_fp(fp)
            has_SIGINT = self.file_lock.has_SIGINT
            unwrite = self.f_unwrite
            key_table = io.key_table
            io_read_key = io.read_key
            row_id = io.n_records
            keys = keys.intersection(key_table)
            while keys and row_id < io.n_lines:
                if has_SIGINT():
                    break

                _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                if _key in keys:
                    keys.remove(_key)
                    chg_row = unwrite(fp, _key, row=row_id)
                    if chg_row:
                        results[_key] = ('CHG', ) + chg_row

                row_id += 1

            return results

    def unremove(self, *records:str) -> Dict[str,Any]:
        """Resurrect dropped index tracking references pulling deleted outlier components back into live databases index pools blocks.

        Args:
            *records (str): Unique identifier token strings matching targeted deleted records candidates tracking keys data.

        Returns:
            Dict[str, Any]: Execution summary index tracing resurrected targets aligned with recovered layouts coordinates parameters logs.
        """
        keys = set()
        results = {}
        for key in records: # pragma: no cover
            if isinstance(key, str):
                keys.add(key)
            elif key.__hash__:
                keys.add(str(key))
            else:
                for kk in key:
                    keys.add(kk if isinstance(kk, str) else str(kk))

        if not keys:
            return results

        with self.open(read_only=True) as fp:
            io = self.io
            if io.n_records == io.n_lines:
                return results

            io, fp, key_fp, _sync_chg = self.f_get_write_fp(fp)
            has_SIGINT = self.file_lock.has_SIGINT
            undelete = self.f_undelete
            key_table = io.key_table
            io_read_key = io.read_key
            row_id = io.n_records
            keys = keys.difference(key_table)
            while keys and row_id < io.n_lines:
                if has_SIGINT():
                    break

                _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                if _key in keys:
                    keys.remove(_key)
                    add_row = undelete(fp, _key, row=row_id)
                    if add_row:
                        results[_key] = ('ADD', ) + add_row
                        row_id = io.n_records
                        continue

                row_id += 1

            return results

    def revert(self, *records:str) -> Dict[str,Any]:
        """Symmetrically execute recovery pipelines rolling back either variable values updates or item omissions based on history bounds logs.

        Args:
            *records (str): Target text identifiers tracking variables contexts fields.

        Returns:
            Dict[str, Any]: Collection mapping keys fields onto recovery structural outcomes status codes.
            
        Example:
            >>> status = jdb.revert('target_key_1', 'target_key_2')
        """
        results = {}
        keys = set()
        for key in records:  # pragma: no cover
            if isinstance(key, str):
                keys.add(key)
            elif key.__hash__:
                keys.add(str(key))
            else:
                for kk in key:
                    keys.add(kk if isinstance(kk, str) else str(kk))

        if not keys:
            return results

        with self.open(read_only=True) as fp:
            io = self.io
            if io.n_records == io.n_lines:
                return results

            io, fp, key_fp, _sync_chg = self.f_get_write_fp(fp)
            has_SIGINT = self.file_lock.has_SIGINT
            undelete = self.f_undelete
            unwrite = self.f_unwrite
            key_table = io.key_table
            io_read_key = io.read_key
            chg_keys = keys.intersection(key_table)
            add_keys = keys.difference(key_table)
            keys.clear()
            if add_keys:
                row_id = io.n_records
                while add_keys and row_id < io.n_lines:
                    if has_SIGINT():
                        break

                    _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                    if _key in add_keys:
                        add_keys.remove(_key)
                        add_row = undelete(fp, _key, row=row_id)
                        if add_row:
                            results[_key] = ('ADD', ) + add_row
                            row_id = io.n_records
                            continue

                    row_id += 1

            if chg_keys:
                row_id = io.n_records
                while chg_keys and row_id < io.n_lines:
                    if has_SIGINT():
                        break

                    _key, _f, _o, _r, _v, _s, _d = io_read_key(key_fp, row_id)
                    if _key in chg_keys:
                        chg_keys.remove(_key)
                        chg_row = unwrite(fp, _key, row=row_id)
                        if chg_row:
                            results[_key] = ('CHG', ) + chg_row

                    row_id += 1

            return results

    def recycle(self, parent:str='', level:int=0, merge:bool=False, fill_zero:bool=False, verbose:bool=True):
        """Purge unlinked dead storage slots rewriting physical indexes sheets to reclaim unallocated disk space footprints metrics.

        Args:
            parent (str, optional): Hierarchy prefix namespace path denoting partition trees boundaries. Defaults to ''.
            level (int, optional): Recursion limitation deepness constraining nested children evaluation scopes paths rules. Defaults to 0.
            merge (bool, optional): Combine contiguous sparse gaps inside data segments layout storage files. Defaults to False.
            fill_zero (bool, optional): Overwrite unallocated physical tracks with structural zeroes vectors preventing leakage traces. Defaults to False.
            verbose (bool, optional): Enable terminal logging text parameters metrics visualization alerts. Defaults to True.
        
        Example:
            >>> jdb.recycle(merge=False)
        """
        del_rows = []
        with self.open(read_only=False) as fp:
            io = self.io
            io, fp, key_fp = self.f_get_fp(fp)
            has_SIGINT = self.file_lock.has_SIGINT
            if level > 0:
                for key in sorted(set(io.groups).union(self.childs)):
                    if has_SIGINT():
                        return

                    jdb = self.f_get_child(fp, key)
                    if isinstance(jdb, JDb):
                        full_key = f'{SEP_SYM}{key}' if not parent else f'{parent}{SEP_SYM}{key}'
                        print(Style(f'Recycling .. {full_key} (merge={merge}, fill_zero={fill_zero})', green=1))
                        jdb.recycle(parent=full_key, level=level-1, merge=merge, fill_zero=fill_zero)

            if io.n_records == io.n_lines:
                io.update_file_table()
                if io.n_records == 0: # io.n_lines == 0
                    for file_id in io.file_table: # pragma: no cover
                        self.files_obj.VAL_remove(file_id)
                    io.file_table.clear()
                    io.key_table.clear()
                    self._cache.clear()

                curr_pos = io.seek(key_fp, io.n_lines)
                end_pos = key_fp.seek(0,2)
                if end_pos - curr_pos >= io.index_size: # pragma: no cover
                    self.fsize = io.write_header(key_fp, truncate=True)
                    print(f'[Done|{"M" if merge else "C"}] truncate size:{curr_pos:,}/{end_pos:,}={self.fsize:,} ... {io.n_records:,}/{io.n_lines:,} tb:{len(io.file_table)}')
                    return

                print(f'[Done|{"M" if merge else "C"}] no extra rows! row:{io.n_records:,}/{io.n_lines:,} tb:{len(io.file_table)}')
                return

            io_read_key = io.read_key
            f_get_val_fp = self.f_get_val_fp
            file_table = io.file_table
            old_lines = n_lines = io.n_lines
            sortable = False
            for row_id in range(io.n_records, n_lines):
                if has_SIGINT():
                    return

                key, file_id, offset, row_size, val_size, ver, days = io_read_key(key_fp, row_id)
                if row_size == 0:
                    # if verbose:
                    #     print(f'del0 KV-row[{key}] #{row_id}')

                    sortable = True
                else:
                    curr_end = offset + row_size
                    file_end = file_table.get(file_id, curr_end)
                    del_rows.append((file_id, offset, row_size, val_size, ver, days, key, row_id))
                    sortable = sortable or curr_end >= file_end

            if not merge and not sortable: # pragma: no cover
                curr_pos = key_fp.tell()
                end_pos = key_fp.seek(0,2)
                if end_pos - curr_pos >= io.index_size:  # pragma: no cover
                    self.fsize = io.write_header(key_fp, truncate=True)
                    print(f'[Done|{"M" if merge else "C"}] truncate size:{curr_pos:,}/{end_pos:,}={self.fsize:,} ... {io.n_records:,}/{io.n_lines:,} tb:{len(io.file_table)}  #{len(del_rows)}')
                    return

                print(f'[Done|{"M" if merge else "C"}] no row can be recycled! size:{curr_pos:,}/{end_pos:,}={self.fsize:,} row:{io.n_records:,}/{io.n_lines:,} tb:{len(io.file_table)} #{len(del_rows)}')
                return

            if sortable:
                io.n_lines = io.n_records
                if del_rows:
                    new_del_rows = []
                    io_write_key = io.write_key
                    del_rows = sorted(del_rows, reverse=True)
                    for (file_id, offset, row_size, val_size, ver, days, key, _row_id) in del_rows:
                        curr_end = offset + row_size
                        file_end = file_table.get(file_id, curr_end)
                        if curr_end >= file_end:
                            file_table[file_id] = offset = max(offset, 0)
                            val_fp = None
                            try:
                                val_fp = self.files_obj.VAL_open(file_id, 'rb+', buffering=0)
                                val_fp.seek(offset)
                                val_fp.truncate()

                            finally:
                                if val_fp is not None:
                                    self.files_obj.fsync(val_fp.fileno())
                                    val_fp.close()

                            if verbose: # pragma: no cover
                                print(f'del0 K-row[{key}] -> file_id:{file_id} offset:{offset:,}:{curr_end:,} tb:{file_table[file_id]:,}')

                        else:
                            io.n_lines += 1 # before write_key
                            io_write_key(key_fp, io.n_lines-1, key, file_id, offset, row_size, val_size, ver, days)
                            file_table[file_id] = max(file_end, curr_end)
                            new_del_rows.append((file_id, offset, offset+row_size, io.n_lines-1, 1))

                    del_rows.clear()
                    del_rows = new_del_rows

            elif del_rows: # not sortable
                new_del_rows = []
                for (file_id, offset, row_size, val_size, ver, days, key, row_id) in del_rows:
                    new_del_rows.append((file_id, offset, offset+row_size, row_id, 1))

                del_rows.clear()
                del_rows = new_del_rows

            if del_rows and merge:
                del_rows = sorted(del_rows)
                prev = del_rows[0]
                new_rows = {}
                for curr in del_rows[1:]:
                    prev_id, prev_start, prev_end, prev_row, prev_cnt = prev
                    curr_id, curr_start, curr_end, _curr_row, _curr_cnt = curr
                    if prev_id == curr_id and prev_end == curr_start:
                        prev = prev_id, prev_start, curr_end, prev_row, prev_cnt+1
                    else:
                        new_rows[prev_id,prev_start] = prev_end - prev_start
                        if fill_zero: # pragma: no cover
                            val_fp, __i, __o  = f_get_val_fp(fp, prev_id)
                            val_fp.seek(prev_start)
                            val_fp.write(b'\0' * (prev_end-prev_start))

                        if verbose: # pragma: no cover
                            print(f'#{len(new_rows)}. DEL K-row #{prev_row}+{prev_cnt} file_id:{prev_id} offset:{prev_start:,}~{prev_end:,} tb:{file_table[prev_id]:,}')

                        prev = curr

                prev_id, prev_start, prev_end, prev_row, prev_cnt = prev
                new_rows[prev_id,prev_start] = prev_end - prev_start
                if fill_zero: # pragma: no cover
                    val_fp, __i, __o  = f_get_val_fp(fp, prev_id)
                    val_fp.seek(prev_start)
                    val_fp.write(b'\0' * (prev_end-prev_start))

                if verbose: # pragma: no cover
                    print(f'#{len(new_rows)}. DEL K-row #{prev_row}+{prev_cnt} file_id:{prev_id} offset:{prev_start:,}~{prev_end:,} tb:{file_table[prev_id]:,}')

                print(f'!MEG K-row #{len(del_rows):,} -> #{len(new_rows):,}')
                io_write_key = io.write_key
                # rows = {}
                for row_id in range(io.n_records):
                    key, file_id, offset, row_size, val_size, ver, days = io_read_key(key_fp, row_id)
                    if row_size > 0:
                        del_size = new_rows.pop((file_id, offset+row_size), -1)
                        if del_size > 0:
                            new_size = row_size + del_size
                            if val_size == 0: # pragma: no cover
                                val_fp, __i, __o  = f_get_val_fp(fp, file_id)
                                val_fp.seek(offset + row_size)
                                val_fp.write(io.pad_byte * del_size)

                            io_write_key(key_fp, row_id, key, file_id, offset, new_size, val_size, ver, days=days)
                            if verbose: # pragma: no cover
                                print(f'CHG K-row #{row_id} file_id:{file_id} offset:{offset:,} size:{val_size:,}/({row_size:,}+{del_size:,}={new_size:,}) tb:{file_table[file_id]:,} [DEAD=#{len(new_rows)}]')

                        # rows[file_id,offset] = key,row_id,row_size,val_size,ver,days

                print(f'GOOD=#{io.n_records} + DEAD=#{len(new_rows):,}')
                io.n_lines = io.n_records
                if io.n_records > 0:
                    for (file_id,offset),del_size in new_rows.items():
                        next_offset = offset+del_size
                        file_end = file_table.get(file_id, next_offset)
                        if next_offset >= file_end: # pragma: no cover
                            file_table[file_id] = offset = max(offset, 0)
                            val_fp = None
                            try:
                                val_fp = self.files_obj.VAL_open(file_id, 'rb+', buffering=0)
                                val_fp.seek(offset)
                                val_fp.truncate()

                            finally:
                                if val_fp is not None:
                                    self.files_obj.fsync(val_fp.fileno())
                                    val_fp.close()

                            if verbose: # pragma: no cover
                                print(f'KILL K-row #file_id:{file_id} offset:{offset:,}:{file_end:,} tb:{file_table[file_id]:,}')

                            continue

                        io.write_key(key_fp, io.n_lines, '', file_id, offset, del_size, 0)
                        io.n_lines += 1

                        if verbose: # pragma: no cover
                            print(Style(f'{io.n_records}/{io.n_lines} DEAD #file_id:{file_id} offset:{offset:,}+{del_size:,} tb:{file_table[file_id]:,}', yellow=1))

                        # _key = file_id,next_offset
                        # if _key in rows:
                        #     key,row_id,row_size,val_size,ver,days = rows[_key]
                        #     new_size = row_size + del_size
                        #     if verbose:
                        #         print(f'CHG K-row[{key}] #{row_id} file_id:{file_id} offset:{_key[-1]:,}-{del_size:,} size:{val_size:,}/({row_size:,}+{del_size:,}={new_size:,}) tb:{file_table[file_id]:,}')

                        #     if val_size == 0 and del_size > 0:
                        #         val_fp, __i, __o  = f_get_val_fp(fp, file_id)
                        #         val_fp.seek(offset + row_size)
                        #         val_fp.write(io.pad_byte * del_size)

                        #     io_write_key(key_fp, row_id, key, file_id, offset, new_size, val_size, ver, days=days|CHG_DAY_FLAG)
                        #     val_fp, __i, __o  = f_get_val_fp(fp, file_id)
                        #     val_fp.seek(_key[-1])
                        #     if val_size > 0:
                        #         data = val_fp.read(val_size)
                        #     else:
                        #         data = val_fp.read(row_size)

                        #     val_fp.seek(offset)
                        #     val_fp.write(data)
                        # else:
                        #     if verbose:
                        #         print(Style(f'BAD K-row #file_id:{file_id} offset:{offset:,}+{del_size:,} tb:{file_table[file_id]:,}', yellow=1))
                        #     io.n_lines += 1 # before??
                        #     io_write_key(key_fp, io.n_lines, '', file_id, offset, del_size, 0)

            io.update_file_table()
            if io.n_lines == 0:
                for file_id in io.file_table: # pragma: no cover
                    self.files_obj.VAL_remove(file_id)
                io.file_table.clear()
                io.key_table.clear()
                self._cache.clear()

            io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
            self.fsize = io.write_header(key_fp, truncate=True)
            print(f'[Done|{"M" if merge else "C"}] recycle ... size:{self.fsize:,} {io.n_records:,}/{io.n_lines:,}(old={old_lines:,}) tb:{len(io.file_table)}')

    def clear(self, agree:str='no', wait_sec:int=10, **kwargs) -> bool:
        """Obliterate data registries resetting storage files templates entirely to an empty layout framework.

        Args:
            agree (str, optional): Validation security phrase. Must equal strictly string token 'yes' to proceed. Defaults to 'no'.
            wait_sec (int, optional): Counting delay buffer allowing developers to abort using Ctrl-C indicators. Defaults to 10.
            **kwargs: Extra settings overrides configuring properties mapped onto the fresh structural sheets.

        Returns:
            bool: True if destruction and reallocation finalize properly, False otherwise.
        """
        if agree.lower() == 'yes':
            if wait_sec > 0:
                print(Style(f'!!! After {wait_sec}s, all the data will be cleared !!! (Ctrl-C to stop)', cyan=1, bold=1, underscore=1))
                for _ in range(wait_sec):
                    sleep(1)
                    print('.', end='', flush=True)
        else:
            print('make sure [agree=yes] to clear all data !')
            return False

        swap_id = remv_id = (int(time() * 1000 + randrange(1000)) * 2) % 1000
        file_table = {}
        groups = {}
        with self.open(read_only=False, no_raise=True) as fp:
            io = self.io
            io.update_file_table()
            file_table = io.file_table.copy()
            swap_id += io.swap_id % 2
            remv_id += io.remv_id % 2
            io, fp, key_fp = self.f_get_fp(fp)
            f_get_group = self.f_get_group
            for key in io.groups:
                _jdb = f_get_group(fp, key)
                if not isinstance(_jdb, JDbReader): continue
                groups[key] = _jdb

            io.data_type        = kwargs.get('data_type', io._data_type)
            io.zip_type         = kwargs.get('zip_type', io._zip_type)
            io.key_limit        = kwargs.get('key_limit', io._key_limit)
            io.api_ver          = kwargs.get('api_ver', io.api_ver)
            io.min_value_size   = kwargs.get('min_value_size', io.min_value_size)
            io.max_file_size    = kwargs.get('max_file_size', io.max_file_size)
            io.index_size       = kwargs.get('index_size', io.index_size)
            io.reserved_rate    = kwargs.get('reserved_rate', io.reserved_rate)
            io.sync_id          = 0
            io.swap_id          = swap_id + 1
            io.remv_id          = remv_id + 1

            for file_id in file_table:
                if self.files_obj.VAL_remove(file_id):
                    print(f'\nremoved VAL file -> {file_id}') # pragma: no cover

            io.change_APIs(io.api_ver, io._data_type, io._zip_type, reset=True)
            io.write_header(key_fp, truncate=True)
            io.load_keys(key_fp, force=True)
            self.fsize = io.file_size

            for key,jdb in groups.items():
                jdb.clear(agree='yes', wait_sec=0, **kwargs)

        return True

    def resize_index_size(self, index_size:int=0, extra_size:int=8, min_ver:bool=True) -> int:
        """Modify fixed tracking structural allocation padding bounding database row dimensions headers fields permanently.

        Args:
            index_size (int, optional): Targeted byte allocation width constraint indicator. 0 forces dynamic scan configuration. Defaults to 0.
            extra_size (int, optional): Buffer allocation extension safety boundary width metrics. Defaults to 8.
            min_ver (bool, optional): Reset baseline synchronizations version markers indices. Defaults to True.

        Returns:
            int: Calculated final index padding dimension assigned across files structures.
        """
        extra_size = max(1, extra_size)
        with self.open(read_only=False) as fp_dict:
            io, fp_dict, key_fp = self.f_get_fp(fp_dict)
            min_index_size = 64
            old_index_size = io.index_size

            io.seek(key_fp, 0)
            for _row_id in range(io.n_lines):
                row = key_fp.read(old_index_size).rstrip(b'\n \x00')
                min_index_size = max(min_index_size, len(row)+extra_size)

            print(f'resize_index_size(index_size={index_size}) index_size={old_index_size} check_size={min_index_size}')
            if index_size == 0:
                index_size = min_index_size
            else:
                index_size = min(max(min_index_size, index_size), MAX_INDEX_SIZE)

            io.resize_keys(key_fp, index_size, min_ver=min_ver)
            self.fsize = io.file_size
            return io.index_size

    def change_KEY(self, KEY_type:str, api_ver:Optional[int]=None) -> bool:
        """Transcode indexing layouts formats blueprint rules rewriting master entry trackers parameters configurations.

        Args:
            KEY_type (str): Format encoding specification classification string token text ('J', 'L', 'M', 'S').
            api_ver (Optional[int], optional): Physical logical standard implementation layout version index number. Defaults to None.

        Returns:
            bool: True if structure transposition completes altering the master file, False otherwise.

        Raises:
            ValueError: If target codes evaluate out of structural ranges definitions thresholds.

        Example:
            >>> jdb = JDb(date_type='J+J')
            >>> jdb.change_KEY('S')
            >>> print(jdb.data_type)
            S+J
        """
        KEY_type_u = KEY_type.upper()
        if KEY_type_u not in 'LMJS':
            raise ValueError('KEY_type must be J|L|M|S')

        with self.open(read_only=True) as fp:
            io, fp, key_fp = self.f_get_fp(fp)
            if api_ver is None: # pragma: no cover
                api_ver = io.api_ver

            if not API_LATEST >= api_ver >= 0:
                raise JValueError('invalid API version')

            old_data_type_s = io.data_type_str
            if api_ver == io.api_ver and old_data_type_s.startswith(KEY_type_u):
                # same KEY type
                return False

            io, fp, key_fp, _chg = self.f_get_write_fp(fp)
            n_lines = io.n_lines
            data_type_s = KEY_type_u + old_data_type_s[1:]
            tmp_jdb = JDb(data_type=data_type_s, zip_type=io._zip_type, api_ver=api_ver, index_size=MIN_INDEX_SIZE)
            with tmp_jdb.open(read_only=False) as dst_fp:
                tmp_io, dst_fp, tmp_key_fp = tmp_jdb.f_get_fp(dst_fp)
                tmp_io.sync_id = io.sync_id
                io.seek(key_fp, 0)
                # calculate index size
                for row_id in range(n_lines):
                    row_info = io.read_key(key_fp, row_id)
                    if row_info:
                        tmp_io.write_key(tmp_key_fp, 0, *row_info)

                table = {}
                src_row_id = dst_row_id = 0
                size_diff = tmp_io.index_size - io.index_size
                if size_diff > 0:
                    table_size = min(n_lines, int(n_lines * size_diff / io.index_size) + 8)
                    io.seek(key_fp, 0)
                    while src_row_id < table_size:
                        row_info = io.read_key(key_fp, src_row_id)
                        if row_info:
                            table[src_row_id] = row_info

                        src_row_id += 1

                print(Style(f'!!! [{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{io.files_obj.get_KEY()}|{tmp_io.data_type_str}({tmp_io.zip_type_str}).{tmp_io.api_ver} (old={io.data_type_str}({io.zip_type_str}).{io.api_ver})] WAIT until KEY file is DONE!!! size:{io.index_size}->{tmp_io.index_size} buffer:{len(table)}/{n_lines}', cyan=1, bold=1, underscore=1))
                tmp_io.n_lines = n_lines
                while dst_row_id < n_lines:
                    if src_row_id < n_lines:
                        row_info = io.read_key(key_fp, src_row_id)
                        if row_info:
                            table[src_row_id] = row_info

                        src_row_id += 1

                    key_info = table.pop(dst_row_id, None)
                    if not key_info: # pragma: no cover
                        break

                    tmp_io.write_key(key_fp, dst_row_id, *key_info)
                    dst_row_id += 1

                key_fp.truncate()
                index_size = io.index_size = tmp_io.index_size
                io.change_APIs(tmp_io.api_ver, data_type=tmp_io._data_type, zip_type=tmp_io._zip_type, reset=False)
                io.window_size = max(1, int(KEY_FILE_BUF_SIZE / index_size))
                io.row_bytes = index_size - io.min_value_size * (1 + io.reserved_rate)
                io._n_lines = 0
                io.write_header(key_fp)
                io.load_keys(key_fp, force=True)
                self.fsize = io.file_size

            del tmp_jdb

        return True

    def upgrade(self, folder:str='bak', data_type:Union[str,int,None]=None, zip_type:Union[str,int,None]=None, fast_mode:bool=True, **kwargs) -> JDb:
        """Migrate database models records maps layouts transforming internal formats properties fields seamlessly via proxy nodes staging tracks.

        Args:
            folder (str, optional): Target temporary folder location token. Defaults to 'bak'.
            data_type (Union[str, int, None], optional): Override serialization schema standard encoding format settings. Defaults to None.
                
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
            
            zip_type (Union[str, int, None], optional): Override compression layout parameters criteria markers fields. Defaults to None.
                
                - "no" = no compression for VAL. (default)
                - "gz" = gzip compression(9) for VAL.
                - "bz" = bz2 compression(9) for VAL.
                - "xz" = lzma compression for VAL.
                - "zs" = zstandard compression(22) for VAL.
                - "br" = brotli compression(6) for VAL.
                - "z1" = zstandard compression(6) for VAL.
                - "z2" = zstandard compression(11) for VAL.
                - "lz" = lz4 compression(0) for VAL.

            fast_mode (bool, optional): Skip extraction loop algorithms stages if transcoders align uniformly. Defaults to True.
            **kwargs: Extra parameters passed straight to construction modules.

        Returns:
            JDb: Updated system interface reference workspace engine.
        """
        if zip_type is None:
            zip_type = self.io._zip_type

        if data_type is None:
            data_type = self.io._data_type

        if not folder: # pragma: no cover
            folder = 'bak'

        kwargs['api_ver'] = kwargs.get('api_ver', self.io.api_ver)
        path = self.files_obj.get_path(folder=folder)
        bak_jdb = JDb(path if path else None, data_type=data_type, zip_type=zip_type, **kwargs)
        bak_jdb = self.clone_to(bak_jdb, signal='b', data_type=data_type, zip_type=zip_type, fast_mode=fast_mode, **kwargs)

        with self.KEY_fopen(read_only=False) as key_fp_d:
            with bak_jdb.open(read_only=True):
                old_file_table = self.io.file_table
                bak_file_table = bak_jdb.io.file_table

                # update VAL file
                for file_id in bak_file_table:
                    val_fp_d = val_fp_s = None
                    try:
                        val_fp_d = self.files_obj.VAL_open(file_id, 'wb', buffering=VAL_FILE_BUF_SIZE)
                        try:
                            val_fp_s = bak_jdb.files_obj.VAL_open(file_id, 'rb', buffering=VAL_FILE_BUF_SIZE)
                            buf_size = VAL_FILE_BUF_SIZE
                            while buf_size == VAL_FILE_BUF_SIZE:
                                buf = val_fp_s.read(VAL_FILE_BUF_SIZE)
                                buf_size = len(buf)
                                if buf_size > 0:
                                    val_fp_d.write(buf)
                                    print('.', end='', flush=True)

                            offset = val_fp_d.tell()
                            val_fp_d.truncate()

                            old_offset = old_file_table.get(file_id, -1)
                            if offset != old_offset:
                                print(f'\ntruncating VAL file -> {file_id} [{old_offset:,} -> {offset:,}]') # pragma: no cover

                        finally:
                            if val_fp_s is not None:
                                val_fp_s.close()

                    finally:
                        if val_fp_d is not None:
                            self.files_obj.fsync(val_fp_d.fileno())
                            val_fp_d.close()

                for file_id,old_offset in old_file_table.items():
                    offset = bak_file_table.get(file_id, -1)
                    if offset < 0 and self.files_obj.VAL_remove(file_id):
                        print(f'\nremoving VAL file -> {file_id}') # pragma: no cover

                # update KEY file
                key_fp_s = None
                try:
                    if key_fp_d is None: # pragma: no cover
                        key_fp_d = self.files_obj.KEY_open('wb', buffering=0)
                    else:
                        key_fp_d.seek(0)
                    try:
                        key_fp_s = bak_jdb.files_obj.KEY_open('rb', buffering=KEY_FILE_BUF_SIZE)
                        buf_size = KEY_FILE_BUF_SIZE
                        while buf_size == KEY_FILE_BUF_SIZE:
                            buf = key_fp_s.read(KEY_FILE_BUF_SIZE)
                            buf_size = len(buf)
                            if buf_size > 0:
                                key_fp_d.write(buf)
                                print('r', end='', flush=True) # pragma: no cover

                        key_fp_d.truncate()

                    finally:
                        if key_fp_s is not None:
                            key_fp_s.close()

                finally:
                    if key_fp_d is not None:
                        self.files_obj.fsync(key_fp_d.fileno())
                        key_fp_d.close()

            # unsync
            self._cache.clear()
            self.childs.clear()
            io = self.io
            io.init_APIs(None, reset=True)
            return self

    def restore(self, folder:str='bak', fast_mode:bool=True, **kwargs) -> JDb:
        """Overwrite current repository layers tracking matrices components structures using elements matching chosen backup files templates.

        Args:
            folder (Union[str, JDb]): File directory absolute lookup address string parameter or active source driver reader object workspace. Defaults to 'bak'.
            fast_mode (bool, optional): Skip complex transposition steps if files properties mirror baseline configurations structures. Defaults to True.
            **kwargs: Extra parameters routed forward seamlessly onto replication controllers.

        Returns:
            JDb: Current context active database session interface manager handle.

        Raises:
            ValueError: If lookup coordinates target unallocated positions boundaries paths context lines.
            TypeError: If input structural data candidate fails standard module validation checks.

        Example:
            >>> jdb = JDb('example.jdb')
            >>> jdb.restore(folder='bak')
        """
        if isinstance(folder, JDb):
            jdb = folder

        elif isinstance(folder, str):
            if not folder: # pragma: no cover
                folder = 'bak'

            path = self.files_obj.get_path(folder)
            if not path or not path_exists(path):
                raise ValueError

            jdb = JDb(path)

        else:
            raise TypeError

        return jdb.clone_to(self, signal='r', fast_mode=fast_mode, **kwargs)

    def backup(self, folder:Optional[str]=None, data_type:Union[str,int,None]=None, zip_type:Union[str,int,None]=None, fast_mode:bool=True, **kwargs) -> JDb:
        """Clone structural matrix database state tracking sheets records fields exporting backups profiles to targeted destination folders clusters.

        Args:
            folder (Optional[str], optional): Target system descriptor path code string identifier template context. Defaults to None.
            data_type (Union[str, int, None], optional): Override layout specifications format setting selection index. Defaults to None.
                
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

            zip_type (Union[str, int, None], optional): Override snapshot baseline row compression properties values limits rules. Defaults to None.

                - "no" = no compression for VAL. (default)
                - "gz" = gzip compression(9) for VAL.
                - "bz" = bz2 compression(9) for VAL.
                - "xz" = lzma compression for VAL.
                - "zs" = zstandard compression(22) for VAL.
                - "br" = brotli compression(6) for VAL.
                - "z1" = zstandard compression(6) for VAL.
                - "z2" = zstandard compression(11) for VAL.
                - "lz" = lz4 compression(0) for VAL.

            fast_mode (bool, optional): Accelerate copy algorithms utilizing binary segment streams maps mirroring rules. Defaults to True.
            **kwargs: Extra attributes routed down seamlessly to child construction factories.

        Returns:
            JDb: Initialized destination replica workspace proxy connection interface object.

        Example:
            >>> jdb = JDb('example.jdb', data_type='J+M', zip_type='gz')
            >>> jdb += {f'key{v}':list(range(v)) for v in range(100)}
            >>> bak_jdb = jdb.backup(folder='bak', data_type='S+S', zip_type='br')
            >>> print(bak_jdb.date_type, bak_jdb.zip_type)
            S+S br
        """
        if zip_type is None:
            zip_type = self.io._zip_type

        if data_type is None:
            data_type = self.io._data_type

        if not folder: # pragma: no cover
            folder = 'bak'

        path = self.files_obj.get_path(folder) or None
        target_jdb = JDb(path if path else None, zip_type=zip_type, data_type=data_type, **kwargs)
        return self.clone_to(target_jdb, data_type=data_type,  zip_type=zip_type, fast_mode=fast_mode, **kwargs)

    def clone_to(self, target:Union[JDb,JFilesBase,str], signal:str='.', fast_mode:bool=True, max_file_size:Optional[int]=None, min_value_size:Optional[int]=None, index_size:Optional[int]=None, reserved_rate:Optional[float]=None, data_type:Union[str,int,None]=None, zip_type:Union[str,int,None]=None, cache_limit:int=0, api_ver:Optional[int]=None, **kwargs) -> JDb:
        """Clone data mapping layouts structures templates from self source environment into target destination storage configurations drivers arrays frames.

        Args:
            target (Union[JDb, JFilesBase, str]): Target storage manager engine wrapper, location token path text format layout selector string, or absolute instance proxy context.
            signal (str, optional): Heartbeat monitoring output string token mapped onto runtime console loops indicators text. Defaults to '.'.
            fast_mode (bool, optional): Engage raw binary stream optimization mechanics bypassing transcoders pipelines loops if schemas align uniformly. Defaults to True.
            max_file_size (Optional[int], optional): Custom destination storage capacity parameter setting data file segment bounds. Defaults to None.
            min_value_size (Optional[int], optional): Minimum alignment floor width constraint bounding row expansion buffers tracks. Defaults to None.
            index_size (Optional[int], optional): Fixed byte width defining destination row padding boundaries constraints markers fields. Defaults to None.
            reserved_rate (Optional[float], optional): Cushion expansion multiplier allocated across target workspace segments fields. Defaults to None.
            data_type (Union[str, int, None], optional): Format coding classification token specifying serialization configurations layout schemas. Defaults to None.
                
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
          
            zip_type (Union[str, int, None], optional): Targeted compression algorithm code token selection settings options values. Defaults to None.
            
                - "no" = no compression for VAL. (default)
                - "gz" = gzip compression(9) for VAL.
                - "bz" = bz2 compression(9) for VAL.
                - "xz" = lzma compression for VAL.
                - "zs" = zstandard compression(22) for VAL.
                - "br" = brotli compression(6) for VAL.
                - "z1" = zstandard compression(6) for VAL.
                - "z2" = zstandard compression(11) for VAL.
                - "lz" = lz4 compression(0) for VAL.

            cache_limit (int, optional): Memory limitation constraint variables values bounding destination cache lookup objects registry. Defaults to 0.
            api_ver (Optional[int], optional): Logical logical operational standard blueprint standard iteration version identifier. Defaults to None.
            **kwargs: Extra settings overrides routed down seamlessly onto compilation factory pipelines matrices.

        Returns:
            JDb: The initialized populated target destination session environment workspace model context.

        Raises:
            TypeError: If input target elements candidates fail driver framework integration matching expectations rules profiles metrics tracks.
        """
        if isinstance(target, JDb):
            jdb = target
            if self is jdb:
                return self

        elif isinstance(target, (str, JFilesBase)):
            jdb = JDb(target)

        else:
            raise TypeError('cannot create JDb')

        with self.open(read_only=True) as src_fp:
            _index_size = 64
            src_io, src_fp, key_fp_s = self.f_get_fp(src_fp)
            src_index_size = src_io.index_size
            src_io.seek(key_fp_s, 0)
            for row_id in range(src_io.n_records):
                row = key_fp_s.read(src_index_size).rstrip(b'\n \x00')
                _index_size = max(_index_size, len(row)+2)

            if index_size is None:
                index_size = _index_size
            else:
                index_size = max(index_size, _index_size)

            index_size = ((index_size >> 3) << 3) + (8 if index_size & 0x7 else 0)
            with jdb.open(read_only=False, no_raise=True) as dst_fp:
                dst_io, dst_fp, key_fp_d = jdb.f_get_fp(dst_fp)

                if isinstance(target, JDb):
                    max_file_size = dst_io.max_file_size if max_file_size is None else max_file_size
                    min_value_size = dst_io.min_value_size if min_value_size is None else min_value_size
                    index_size = dst_io.index_size if index_size is None else index_size
                    reserved_rate = dst_io.reserved_rate if reserved_rate is None else reserved_rate
                    zip_type = dst_io._zip_type if zip_type is None else zip_type
                    data_type = dst_io._data_type if data_type is None else data_type
                    api_ver = dst_io.api_ver if api_ver is None else api_ver
                else:
                    max_file_size = src_io.max_file_size if max_file_size is None else max_file_size
                    min_value_size = src_io.min_value_size if min_value_size is None else min_value_size
                    index_size = src_io.index_size if index_size is None else index_size
                    reserved_rate = src_io.reserved_rate if reserved_rate is None else reserved_rate
                    zip_type = src_io._zip_type if zip_type is None else zip_type
                    data_type = src_io._data_type if data_type is None else data_type
                    api_ver = src_io.api_ver if api_ver is None else api_ver

                old_file_table = dst_io.file_table.copy()

                for key in dst_io.groups:
                    _jdb = jdb.f_get_group(dst_fp, key)
                    if isinstance(_jdb, JDb):
                        _jdb.clear(agree='yes', wait_sec=0)

                rand_id = (int(time() * 1000 + randrange(1000))) % 1000 + 1
                swap_id = rand_id * 2 + dst_io.swap_id % 2 + 1
                remv_id = rand_id * 2 + dst_io.remv_id % 2 + 1
                sync_id = dst_io.sync_id if dst_io.file_table else 0

                dst_io = jdb.io = JIo(
                            files_obj=dst_io.files_obj.copy(), # due to JNetFiles
                            data_type=data_type,
                            zip_type=zip_type,
                            key_limit=dst_io._key_limit,
                            api_ver=api_ver,
                            index_size=index_size,
                            sync_id=sync_id,
                            swap_id=swap_id,
                            remv_id=remv_id,
                            max_file_size=max_file_size,
                            min_value_size=min_value_size,
                            reserved_rate=reserved_rate)

                dst_io.change_APIs(api_ver, dst_io._data_type, dst_io._zip_type)
                dst_io.write_header(key_fp_d, truncate=True)

                fast_mode = fast_mode and dst_io._data_type == src_io._data_type and dst_io._zip_type == src_io._zip_type
                src_io_read_key = src_io.read_key
                src_io_read_value = src_io.read_value
                src_io_unpad = src_io.unpad
                src_decode_row = self._decode_row
                src_get_val_fp = self.f_get_val_fp
                src_childs = self.childs

                dst_io_write_key = dst_io.write_key
                dst_io_pad = dst_io.pad
                dst_encode_row = jdb._encode_row
                dst_get_val_fp = jdb.f_get_val_fp
                dst_childs = jdb.childs
                dst_files_obj = jdb.files_obj
                dst_create_jdb = jdb.create_jdb
                dst_childs.clear()
                dst_io.groups.clear()

                for src_child, src_jdb in src_childs.items(): # pragma: no cover
                    dst_childs[src_child] = src_jdb

                if signal:
                    print(signal, end='', flush=True)

                for row_id in range(src_io.n_records):
                    key, file_id, offset, row_size, val_size, _ver, days = src_io_read_key(key_fp_s, row_id)
                    if row_size == 0:
                        try:
                            val = src_decode_row(file_id, offset, key, val_size)

                        except: # pragma: no cover
                            print(Style(f'Skip to read value {key} file_id:{file_id}+{offset} size:{val_size}/{row_size}', yellow=1))
                            continue

                        if file_id == 0x10 and isinstance(val, JDbReader): # pragma: no cover
                            val = dst_io.groups.get(key, None)
                            if val is None:
                                val = dst_io.groups[key] = dst_create_jdb(dst_files_obj.create_group(key))

                        if fast_mode:
                            dst_io.n_lines += 1 # before write key
                            file_id_d = file_id
                            offset_d = offset
                            val_size_d = val_size
                            row_size_d = 0
                        else:
                            file_id_d, offset_d, val_size_d = dst_encode_row(key, val)
                            dst_io.n_lines += 1 # before write key
                            if file_id_d >= 0:
                                row_size_d = 0

                            else:
                                data = offset_d
                                val_size_d = len(data)
                                data_d = dst_io_pad(data, max_size=0)
                                val_fp_d, file_id_d, offset_d = dst_get_val_fp(dst_fp, req_size=len(data_d))
                                val_fp_d.seek(offset_d)
                                row_size_d = val_fp_d.write(data_d)
                                dst_io.file_table[file_id_d] = max(dst_io.file_table[file_id_d], offset_d + row_size_d)
                    else:
                        val_fp, __i, __o  = src_get_val_fp(src_fp, file_id)
                        if fast_mode:
                            val_fp.seek(offset)
                            if val_size > 0:
                                data = val_fp.read(val_size)
                            else: # pragma: no cover
                                data = val_fp.read(row_size)
                                data = src_io_unpad(data)

                            dst_io.n_lines += 1  # before write key
                            if not data: # pragma: no cover
                                file_id_d, offset_d, val_size_d = dst_encode_row(key, None)
                                row_size_d = 0
                            else:
                                val_size_d = len(data)
                                data_d = dst_io_pad(data, max_size=0)
                                val_fp_d, file_id_d, offset_d = dst_get_val_fp(dst_fp, req_size=len(data_d))
                                val_fp_d.seek(offset_d)
                                row_size_d = val_fp_d.write(data_d)
                                dst_io.file_table[file_id_d] = max(dst_io.file_table[file_id_d], offset_d + row_size_d)
                        else:
                            try:
                                val = src_io_read_value(val_fp, offset, row_size, val_size)
                                file_id_d, offset_d, val_size_d = dst_encode_row(key, val)

                            except: # pragma: no cover
                                print(Style(f'Skip to read value {key} file_id:{file_id}+{offset} size:{val_size}/{row_size}', yellow=1))
                                continue

                            dst_io.n_lines += 1  # before write key
                            if file_id_d >= 0:
                                row_size_d = 0
                            else:
                                data = offset_d
                                val_size_d = len(data)
                                data_d = dst_io_pad(data, max_size=0)
                                val_fp_d, file_id_d, offset_d = dst_get_val_fp(dst_fp, req_size=len(data_d))
                                val_fp_d.seek(offset_d)
                                row_size_d = val_fp_d.write(data_d)
                                dst_io.file_table[file_id_d] = max(dst_io.file_table[file_id_d], offset_d + row_size_d)

                    dst_io_write_key(key_fp_d, dst_io.n_records, key, file_id_d, offset_d, row_size_d, val_size_d, dst_io.sync_id, days=days)
                    key_fp_d.flush() # before key_table
                    dst_io.key_table[key] = dst_io.n_records
                    dst_io.sync_id = (dst_io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                    dst_io.n_records += 1

                    child = src_childs.get(key, None)
                    if isinstance(child, JDbReader): # pragma: no cover
                        dst_childs[key] = child

                    if signal and ((dst_io.n_records + 1) % 1000) == 0: # pragma: no cover
                        print(signal, end='', flush=True)

                key_fp_d.truncate()
                jdb.fsize = dst_io.file_size = 0
                files_obj = jdb.files_obj
                for file_id,old_offset in old_file_table.items():
                    offset = dst_io.file_table.get(file_id, -1)
                    if offset < 0:
                        if files_obj.VAL_remove(file_id):
                            print(f'\nremoving VAL file -> {file_id}')

                        continue

                    if offset < old_offset:
                        print(f'\ntruncating VAL file -> {file_id} [{old_offset:,} -> {offset:,}]')
                        val_fp = None
                        try:
                            val_fp = files_obj.VAL_open(file_id, 'rb+', buffering=0)
                            val_fp.seek(offset)
                            val_fp.truncate()

                        finally:
                            if val_fp is not None:
                                files_obj.fsync(val_fp.fileno())
                                val_fp.close()

                for key,s_jdb in src_io.groups.items():
                    if not isinstance(s_jdb, JDb): continue
                    d_jdb = jdb.f_get_group(dst_fp, key)
                    #pass;0;assert isinstance(d_jdb, JDb)
                    s_jdb.clone_to(d_jdb,
                        signal=signal,
                        data_type=data_type,
                        zip_type=zip_type,
                        max_file_size=max_file_size,
                        min_value_size=min_value_size,
                        index_size=index_size,
                        reserved_rate=reserved_rate,
                        cache_limit=cache_limit, **kwargs)

                if src_io.swap_id == dst_io.swap_id:
                    dst_io.swap_id += (rand_id + 1)

                if src_io.remv_id == dst_io.remv_id:
                    dst_io.remv_id += (rand_id + 1)

        return jdb

    def setdefault(self, key:str, val:Any):
        """Initialize chosen lookup strings with default values if currently missing from the index registries.

        Args:
            key (str): Target text reference indicator lookup query string token context.
            val (Any): Fallback object template payload context rules data fields variables.
        """
        with self.open(read_only=True) as fp:
            if key not in self.io.key_table:
                self.f_write(fp, key, val)

    def set(self, key:str, val:Any, flags:Optional[JFlag]=None, max_wsize:Optional[int]=None) -> Optional[Any]:
        """Write single entry content maps configuring transaction modifiers rules indices tracks.

        Args:
            key (str): Target unique key lookup choice token identifier text string.
                
                - str

                    >>> jdb[ke)] = val

                - int | float | bool

                    >>> jdb[str(key)] = val

            val (Any): Scalar object layout payload or conditional update callback lambda routine context.

                - any type but function
                    
                    >>> jdb['name'] = val

                - function(k,v)

                    >>> jdb['name'] = lambda k,v : v+1
                    >>> jdb['name'] = lambda k,v : v+1 if v is not None else None # replace if exist
                    >>> jdb['name'] = lambda k,v : v if v is not None else 1 # insert if not exist
            
            flags (Optional[JFlag], optional): strategic behavioral modifiers. Defaults to None.

                    - REVERT  = allow to revert
                    - SPLIT   = allow to split largest row size to two

            max_wsize (Optional[int], optional): Maximum search scope bounding lookahead sweeps across dead lines elements. Defaults to None.

                    - None = use default max_wsize (4)
                    - -ve = disable searching

        Returns:
            Optional[Any]: The committed data payload if changes successfully execute, old value context otherwise.

        Raises:
            TypeError: If input candidate argument structures fail validation tests specifications models.
        """
        if callable(val):
            func = val
            arg_cnt = func.__code__.co_argcount
            if arg_cnt != 2:
                raise TypeError
        else:
            func = None

        with self.open(read_only=True) as fp:
            if func:
                row_id = self.io.key_table[key]
                old_val = None if row_id < 0 else self.f_read(fp, key, row=row_id, copy=True)
                new_val = func(key, deepcopy(old_val))
                if new_val != old_val:
                    if self.f_write(fp, key, new_val, flags=flags, max_wsize=max_wsize):
                        return new_val

                return old_val

            if self.f_write(fp, key, val, flags=flags, max_wsize=max_wsize):
                return val

        return None

    def set_n(self, records:Dict[str,Any], default_val:Optional[Any]=None, replace:bool=True, insert:bool=True, **kwargs) -> Dict[str,Any]:
        """Batch commit key-value collections mapping records into active database frames indexes lanes.

        Args:
            records (Dict[str, Any]): Inputs target mapping records collections datasets.
            default_val (Optional[Any], optional): Fallback value mapping variables context if entries lookups evaluate abstract. Defaults to None.
            replace (bool, optional): Rewrite existing data points if indexes discover overlapping indicators matches parameters. Defaults to True.
            insert (bool, optional): Initialize unknown outliers creating fresh structural slots sheets fields records lines. Defaults to True.
            **kwargs: Extra parameters routed down directly into underlying translation execution engines factories.

        Returns:
            Dict[str, Any]: Changed objects log maps summary array tracing modified elements paths.

        Raises:
            TypeError: If input candidate collection elements break schema constraints maps parameters.
        """
        return self.add(records, default_val=default_val, replace=replace, insert=insert, is_list=False, **kwargs)

    def set_days(self, key:str, days:Union[int,float,str,dt_date,datetime]) -> bool:
        """Modify tracking calendar timestamps elapsed days values logs stored within entry index parameters coordinates.

        Args:
            key (str): Target descriptor lookups selection token lookup string classification label context.
            days (Union[int, float, str, dt_date, datetime]): Timeline offset integer, calendar object instance, or formatted date text code.
                
                - int : days since 1-1-1
                    
                    >>> jdb.set_days('key', 1)

                - str : 'YYYY-MM-DD' or 'YYYY-MM-DD YYYY-MM-DD'

                    >>> jdb.set_days('key', "2000-01-01")
                    >>> jdb.set_days('key', "2000-01-01 2001-12-31")

                - date | datetime 

                    >>> jdb.set_days('key', date(2000, 1, 1))
                    >>> jdb.set_days('key', datetime(2000, 1, 1))

                - float : timestamp

        Returns:
            bool: True if modification markers indices write successfully, False fallback if errors strike connections.
        """
        with self.open(read_only=True) as fp:
            return self.f_change_days(fp, key, days)

    def insert(self, records:Dict[str,Any], default_val:Optional[Any]=None, **kwargs) -> Dict[str,Any]:
        """Batch write new elements parameters metrics ignoring existing records overlaps boundaries positions lines fields metrics logs maps.

        Args:
            records (Dict[str, Any]): Core context source dictionary mapping indices properties fields.
            default_val (Optional[Any], optional): Fallback placeholder variable options parameters settings models. Defaults to None.
            **kwargs: Extra transaction isolation modifiers parameters variables.

        Returns:
            Dict[str, Any]: Subset tracking entries successfully registered inside indices fields.
        """
        return self.add(records, default_val=default_val, replace=False, insert=True, is_list=False, **kwargs)

    def update(self, records:Dict[str,Any], default_val:Optional[Any]=None, **kwargs) -> Dict[str,Any]:
        """Batch load elements dictionaries mapping records directly in-place rewriting overlapping lines fields metrics fields.

        Args:
            records (Dict[str, Any]): Datasets records dictionary mapping collections lines tracks.
            default_val (Optional[Any], optional): Fallback parameter value context fields variables. Defaults to None.
            **kwargs: Strategic execution modifier attributes passed smoothly onto translation processors factories frameworks wrappers.

        Returns:
            Dict[str, Any]: Catalog tracing successfully updated dataset items.
        """
        return self.add(records, default_val=default_val, replace=True, insert=True, is_list=False, **kwargs)

    def replace(self, records:Dict[str,Any], default_val:Optional[Any]=None, **kwargs) -> Dict[str,Any]:
        """Batch rewrite pre-existing record lines parameters properties fields metrics values profiles avoiding adding unknown outliers into index pools blocks.

        Args:
            records (Dict[str, Any]): Target translation dictionary allocating adjustments details configurations rules models sheets text fields context layers frameworks grids.
            default_val (Optional[Any], optional): Fallback value. Defaults to None.
            **kwargs: Extra execution runtime attributes.

        Returns:
            Dict[str, Any]: Replaced records data array tracking modified items coordinates parameters positions numbers blocks.
        """
        return self.add(records, default_val=default_val, replace=True, insert=False, is_list=False, **kwargs)

    def append(self, records:List[Any], **kwargs) -> Dict[str, Any]:
        """Batch append continuous sequence datasets mapping rows values content segments parts blocks anonymously utilizing sequence numbers as descriptors labels markers arrays sheets.

        Args:
            records (List[Any]): Array container processing distinct values entries configurations records fields metrics.
            **kwargs: Strategic flags variables modifiers parameters context settings blocks layers maps tracks systems.

        Returns:
            Dict[str, Any]: Generated mapping fields matching identity codes tokens integers sequences keys to individual saved objects data lines.
        """
        return self.add(records, default_val=None, replace=True, insert=True, is_list=True, **kwargs)

    def insert_vals(self, records:List[Any], **kwargs) -> Dict[str,Any]:
        """Batch insert row value metrics collections anonymously into new entries indices slots.

        Args:
            records (List[Any]): Sequence collection containing target entries values arrays fields indicators models tracks metrics.
            **kwargs: Extra transactional parameter switches.

        Returns:
            Dict[str, Any]: Mapping catalog aligning sequence identities variables to generated records outputs.
        """
        return self.add(records, default_val=None, replace=False, insert=True, is_list=True, **kwargs)

    def update_vals(self, records:List[Any], **kwargs) -> Dict[str,Any]:
        """Batch update or append anonymous values collections entries into database lanes maps.

        Args:
            records (List[Any]): Input items sequences list container.
            **kwargs: Strategic transaction properties context configuration rules parameters trackers handles.

        Returns:
            Dict[str, Any]: Generated identity key dictionary tracks tracking saved row models.
        """
        return self.add(records, default_val=None, replace=True, insert=True, is_list=True, **kwargs)

    def replace_vals(self, records:List[Any], **kwargs) -> Dict[str,Any]:
        """Batch rewrite anonymous value elements sequences arrays avoiding appending unknown new index records lines.

        Args:
            records (List[Any]): Input sequences collection mapping variables targets logs properties.
            **kwargs: Extra hardware processing configuration overrides.

        Returns:
            Dict[str, Any]: Updated objects matrix maps summary results array tracking modified items.
        """
        return self.add(records, default_val=None, replace=True, insert=False, is_list=True, **kwargs)

    def to_csv(self, csv_file:Union[str,IO], key:Optional[str]=None, **kwargs) -> bool:
        """Export internal data frames records fields matrices structures logs straight into tabular structured CSV data formats sheets files documents models.

        Args:
            csv_file (Union[str, IO]): Target filename string locator path or open streaming file-like interface stream descriptor handle context.
            key (Optional[str], optional): Custom field token labeling the principal identifier index row data columns fields layout. Defaults to None.
            **kwargs: Extra formatting parameters routed directly onto inner DictWriter configuration profiles blueprints rules options fields.

        Returns:
            bool: True if extraction workflows finish completely without errors metrics profiles, False fallback otherwise.
        """
        fields = []
        with self.open(read_only=True) as fp:
            csv_fp,owns_it = (open(csv_file, 'w', newline='', encoding='utf-8'), True) \
                    if isinstance(csv_file, str) else (csv_file, False) # pylint: disable=consider-using-with

            csv_fp.seek(0)
            io, fp, key_fp = self.f_get_fp(fp)
            f_read = self.f_read
            patterns = set()
            for row_id in range(io.n_records):
                val = f_read(fp, None, row=row_id, copy=False)
                if (row_id % 1000) == 0: # pragma: no cover
                    print('-', end='', flush=True)

                if isinstance(val, dict):
                    kk = '|'.join(val)
                    if kk not in patterns:
                        patterns.add(kk)
                        for kk in val:
                            if kk not in fields:
                                fields.append(kk)

                elif isinstance(val, (str, bytes, bytearray, int, float, bool)):
                    kk = '__1__'
                    if kk not in patterns:
                        patterns.add(kk)
                        fields.insert(0, kk)

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

            if not fields:
                return False

            kk = '_id' if not key else key
            while kk in fields and kk != fields[0]: # pragma: no cover
                kk += '$'

            if kk != fields[0]:
                fields.insert(0, kk)

            try:
                io, fp, key_fp = self.f_get_fp(fp)
                _cache = self._cache
                _decode_row = self._decode_row
                f_get_val_fp = self.f_get_val_fp
                _update_cache = self._update_cache
                n_records = io.n_records
                io_read_key = io.read_key
                io_read_value = io.read_value
                writer = DictWriter(csv_fp, fieldnames=fields, **kwargs)
                writer.writeheader()
                for row_id in range(n_records):
                    _key, _file_id, _offset, _size, _vsize, _ver, _days = io_read_key(key_fp, row_id)
                    if _cache and _key in _cache:
                        val = _cache.get(_key, None)
                    else:
                        if _size == 0:
                            val = _decode_row(_file_id, _offset, _key, _vsize)
                        else:
                            val_fp, __i, __o  = f_get_val_fp(fp, _file_id)
                            val = io_read_value(val_fp, _offset, _size, _vsize)

                    csv_row = {field:None for field in fields}
                    csv_row[fields[0]] = _key

                    if isinstance(val, dict):
                        for field,vv in val.items():
                            csv_row[field] = val.get(field, None)

                    elif isinstance(val, (str, bytes, bytearray, int, float, bool)):
                        csv_row['__1__'] = val

                    elif hasattr(val, '__iter__'):
                        for ii,vv in enumerate(val):
                            csv_row[f'__V{ii+1}__'] = vv

                    else:
                        csv_row['__1__'] = str(val)

                    writer.writerow(csv_row)
                    if (row_id % 1000) == 0:
                        print('.', end='', flush=True)

            finally:
                if owns_it and csv_fp is not None:
                    csv_fp.close()

        return True

    def from_csv(self, csv_file:Union[str,IO], key:Optional[str]=None, flags:Optional[JFlag]=None, max_wsize:Optional[int]=None, **kwargs) -> JDb:
        """Import structured CSV text streams context sheets fields records translating tabular elements rows matrices back onto native database maps datasets collections.

        Args:
            csv_file (Union[str, IO]): Source filesystem node address string path notation text or open stream descriptor channel container proxy.
            key (Optional[str], optional): Identity reference label indicating target unique row key column header text layout. Defaults to None.
            flags (Optional[JFlag], optional): strategic operational behavioral modifiers flags. Defaults to None.
            max_wsize (Optional[int], optional): Search window capacity constraint bounding dead structural entry lookahead scans width parameters. Defaults to None.
            **kwargs: Extra parameters routed down seamlessly onto secondary underlying DictReader extraction components.

        Returns:
            JDb: Current context modified active database environment workspace proxy handle.
        """
        csv_fp,owns_it = (open(csv_file, 'r', newline='', encoding='utf-8'), True) \
                if isinstance(csv_file, str) else (csv_file, False) # pylint: disable=consider-using-with

        csv_fp.seek(0)
        #pass;0;assert hasattr(csv_fp, 'close')
        try:
            with self.open(read_only=False) as fp:
                has_SIGINT = self.file_lock.has_SIGINT
                io = self.io
                # [BUG: python 3.7] marshal.dumps(Ordereddict) throw exception
                fix_it = io.data_type_str.endswith('+M')
                # key_table = io.key_table
                reader = DictReader(csv_fp, **kwargs)
                for ii,row in enumerate(reader):
                    if has_SIGINT(): break

                    if key is None:
                        # Python 3.7: row is OrderedDict
                        fields = [field for field in row.keys()] # pylint: disable=unnecessary-comprehension
                        key = fields[0]

                    key_id = row.pop(key)
                    if fix_it or isinstance(row, OrderedDict):
                        row = dict(row)

                    self.f_write(fp, key_id, row, flags=flags, max_wsize=max_wsize)
                    if (ii % 1000) == 0:
                        print('.', end='', flush=True)

        finally:
            if owns_it and csv_fp is not None:
                csv_fp.close()

        return self

    def from_sqlite(self, src:Union[str,Connection], batch_size:int=-1) -> JDb:
        """Migrate SQLite transaction tables models matrices records mapping columns profiles straight into isolated nested database groups spaces partitions layers.

        Args:
            src (Union[str, Connection]): Full database file system address string text path context layout parameters maps or active connection instance handle proxy.
            batch_size (int, optional): Iteration size constraint capping total rows fetched during single chunk cycles processes frames metrics. Defaults to -1.

        Returns:
            JDb: Updated relational engine state interface snapshot workspace.

        Raises:
            TypeError: If input sources violate target standard database connection configurations criteria parameters properties fields.
        """
        owns_conn = False
        if isinstance(src, str):
            conn = sql_connect(src)
            owns_conn = True
        else: # pragma: no cover
            conn = src

        if not isinstance(conn, Connection): # pragma: no cover
            raise TypeError

        org_row_factory = conn.row_factory
        conn.row_factory = sql_Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row['name'] for row in cursor.fetchall() if row['name'] != 'sqlite_sequence']
            for tb_name in tables:
                child_jdb = self.add_group(tb_name)

                cursor.execute(f"PRAGMA table_info({tb_name})")
                columns_info = cursor.fetchall()

                pk_cols = [col['name'] for col in columns_info if col['pk'] > 0]
                all_cols = [col['name'] for col in columns_info]
                val_cols = [col for col in all_cols if col not in pk_cols]

                cursor.execute(f"SELECT * FROM {tb_name}")
                with child_jdb.open(read_only=False) as fp:
                    jio = child_jdb.io
                    while True:
                        rows = cursor.fetchmany(batch_size) if batch_size > 0 else cursor.fetchall()
                        if not rows:
                            break

                        for row in rows:
                            val = {col: row[col] for col in val_cols}
                            key = '|'.join(str(row[col]) for col in pk_cols) if pk_cols else str(jio.sync_id)
                            child_jdb.f_write(fp, key, val)

            return self

        finally:
            conn.row_factory = org_row_factory
            if owns_conn:
                conn.close()

    def from_ini(self, src:Union[str,IO]) -> JDb:
        """Parse configuration template sheets fields context records extracting variables settings structures from classic text INI files layout templates blocks rules.

        Args:
            src (Union[str, IO]): Full target system text string path context layout parameters maps or active open file object stream interface pointer locator.

        Returns:
            JDb: Updated relational configuration workspace context handle.
        """
        parser = ConfigParser()
        if isinstance(src, str): # pragma: no cover
            parser.read(src)
        else:
            parser.read_file(src)

        with self.open(read_only=False) as fp:
            for section in parser.sections():
                for key,val in parser.items(section):
                    self.f_write(fp, f'{section}/{key}', val)

            return self

    def from_toml(self, src:Union[str,IO]) -> JDb:
        """Parse TOML specification sheets structures arrays data profiles converting unified hierarchical trees structures documents models directly into record metrics paths context.

        Args:
            src (Union[str, IO]): Target localization filename string path context blueprint text or open streaming object channel handle wrapper proxy.

        Returns:
            JDb: Updated dataset configurations management engine state.

        Raises:
            ModuleNotFoundError: If the host runtime environment misses required third party parsing extensions framework dependencies libraries wrapper hooks.
        """
        if not toml_loads:
            raise ModuleNotFoundError("tomli is not installed. Please pip install tomli.")

        if isinstance(src, str): # pragma: no cover
            with open(src, 'rt', encoding='utf-8') as fp:
                content = fp.read()
        else:
            _content = src.read()
            content = _content.decode('utf-8') if isinstance(_content, bytes) else _content

        data = toml_loads(content)
        with self.open(read_only=False) as fp:
            for section,attributes in data.items():
                if isinstance(attributes, dict):
                    for key,val in attributes.items():
                        self.f_write(fp, f'{section}/{key}', val)
                else:
                    self.f_write(fp, f'/{section}', attributes)

            return self

    def reinit(self, records:Dict[str,Any], default_val:Optional[Any]=None, is_list:bool=False, agree:str='no', wait_sec:int=10, **kwargs) -> bool:
        """Purge tracking maps drop active registers systematically rebuilding complete datasets layout configurations from scratch matching incoming records fields.

        Args:
            records (Dict[str, Any]): Incoming context source matrix data candidates.
            default_val (Optional[Any], optional): Fallback variable context setting parameter assigned if structures evaluate blank. Defaults to None.
            is_list (bool, optional): Adjust entry evaluation tracks converting lists structures sequences anonymously vs mapping dictionaries keys fields text format. Defaults to False.
            agree (str, optional): Safeguard validation checkpoint rule phrase. Must equal strictly 'yes' to proceed. Defaults to 'no'.
            wait_sec (int, optional): Interactive buffer countdown seconds threshold capping destruction loops parameters. Defaults to 10.
            **kwargs: Extra attributes override keys passed down seamlessly to re-initialization routines.

        Returns:
            bool: True if allocation routines commit the fresh structures records maps smoothly, False if checkpoint guards intercept execution paths tracks.
        """
        jdb = None
        if isinstance(records, JDbReader):
            if records == jdb:
                return True

            jdb = records

        elif isinstance(records, dict):
            pass

        elif is_list: # pragma: no cover
            if isinstance(records, str):
                records = [records]

            elif hasattr(records, '__iter__'):
                records = list(records)

            else:
                records = [records]

        else:
            if isinstance(records, str): # pragma: no cover
                records = {records: default_val}

            elif hasattr(records, '__iter__'):
                records = {kk: default_val for kk in records}

            else: # pragma: no cover
                records = {records: default_val}

        if not self.clear(agree=agree, wait_sec=wait_sec, **kwargs):
            return False

        if not records:
            return True

        with self.open(read_only=False, no_raise=True) as fp:
            swap_id = self.io.swap_id
            remv_id = self.io.remv_id
            self.io.reset(**kwargs)
            self.io.swap_id = (swap_id + 1) & 0X_7FF_FFFF_FFFF
            self.io.remv_id = (remv_id + 1) & 0X_7FF_FFFF_FFFF
            f_write = self.f_write
            has_SIGINT = self.file_lock.has_SIGINT
            if not jdb:
                for key in records:
                    if has_SIGINT():
                        break

                    if is_list: # pragma: no cover
                        val = key
                        key = str(self.io.sync_id)
                    else:
                        val = records[key]

                    f_write(fp, str(key) if not isinstance(key, str) else key, val, flags=JFlag(0), max_wsize=0)

            else:
                with jdb.open(read_only=True) as fp1:
                    jdb_read = jdb.f_read
                    for key,row in jdb.io.sorted_key_table_items():
                        if has_SIGINT():
                            break

                        val = jdb_read(fp1, key, row=row, copy=False)
                        f_write(fp, key, val, flags=JFlag(0), max_wsize=0)

            return self.io.n_records > 0

    def add(self, records:Dict[str,Any], default_val:Optional[Any]=None, replace:bool=True, insert:bool=True, is_list:bool=False, flags:Optional[JFlag]=None, max_wsize:Optional[int]=None) -> Dict[str,Any]:
        """Core serialization writing gatekeeper pipeline routing entries insertions or value replacements into database tracks layers maps.

        Args:
            records (Dict[str, Any]): Repository container processing elements candidates maps records fields text tokens variables.
            default_val (Optional[Any], optional): Fallback value mapping variables context assigned if source candidate parses abstract. Defaults to None.
            replace (bool, optional): Overwrite pre-existing records keys if lookups discover shared matching indicators indices parameters logs. Defaults to True.
            insert (bool, optional): Generate brand new data records lines spaces if target descriptors evaluate absent from index pools. Defaults to True.
            is_list (bool, optional): Toggle switch adapting input types tracking sequences listing vs dictionaries tracking key-value parameters. Defaults to False.
            flags (Optional[JFlag], optional): strategic behavioral modifiers. Defaults to None.
            max_wsize (Optional[int], optional): Scan scope lookahead density limit constraining dead rows tracking checks loops fields. Defaults to None.

        Returns:
            Dict[str, Any]: Descriptive dictionary summary array tracking all successfully committed modified entries fields log data metrics records fields.

        Raises:
            TypeError: If input validation candicates structures break system framework specifications classes.
        """
        if not insert and not replace:
            # not insert and not replace [do nothing]
            return {}

        if isinstance(records, JDbReader):
            jdb = records
            if jdb is self or jdb.files_obj == self.files_obj:
                return {}
        else:
            jdb = None

        with self.open(read_only=True) as fp:
            io = self.io
            key_table = io.key_table
            #file_table = io.file_table
            chg_table = {}
            if jdb is not None:
                with jdb.open(read_only=True) as src_fp:
                    jio = jdb.io
                    if jio.n_records <= 0:
                        return chg_table

                    src_read = jdb.f_read
                    dst_write = self.f_write
                    has_SIGINT = self.file_lock.has_SIGINT
                    if insert and replace:
                        # insert + replace = update
                        for _key,row_id in jio.sorted_key_table_items():
                            _val = src_read(src_fp, _key, row=row_id, copy=False)
                            if dst_write(fp, _key, _val, flags=flags, max_wsize=max_wsize):
                                chg_table[_key] = _val
                            if has_SIGINT(): break

                    elif insert:
                        # insert only
                        for _key,row_id in jio.sorted_key_table_items():
                            if _key in key_table: continue
                            _val = src_read(src_fp, _key, row=row_id, copy=False)
                            if dst_write(fp, _key, _val, flags=flags, max_wsize=max_wsize):
                                chg_table[_key] = _val
                            if has_SIGINT():break

                    elif replace:
                        # replace only
                        for _key,row_id in jio.sorted_key_table_items():
                            if _key not in key_table: continue
                            _val = src_read(src_fp, _key, row=row_id, copy=False)
                            if dst_write(fp, _key, _val, flags=flags, max_wsize=max_wsize):
                                chg_table[_key] = _val
                            if has_SIGINT(): break
                    else:
                        # not insert and not replace [do nothing]
                        pass

                return chg_table

            if isinstance(records, dict):
                if not records:
                    return {}

            elif is_list:
                if isinstance(records, str):
                    records = [records]

                elif hasattr(records, '__iter__'):
                    if not records:
                        return {}

                    records = list(records)

                else: # pragma: no cover
                    records = [records]

            else:
                if isinstance(records, str):
                    records = {records : default_val}

                elif hasattr(records, '__iter__'):
                    if not records:
                        return {}

                    records = {kk : default_val for kk in records}

                else: # pragma: no cover
                    records = {records : default_val}

            # quick replace and insert mode
            f_read = self.f_read
            f_write = self.f_write
            _cache = self._cache
            has_SIGINT = self.file_lock.has_SIGINT
            for key in records:
                if has_SIGINT():
                    break

                if is_list:
                    val = key
                    str_key = str(io.sync_id)
                    func = None
                else:
                    val = records[key]
                    if callable(val):
                        func = val
                        arg_cnt = func.__code__.co_argcount
                        if arg_cnt != 2:
                            raise TypeError

                    else:
                        func = None

                    str_key = key if isinstance(key, str) else str(key)

                row = io.key_table[str_key]
                if row >= 0:
                    if replace:
                        if func:
                            old_val = f_read(fp, str_key, row=row, copy=False)
                            new_val = func(str_key, deepcopy(old_val))
                            if new_val != old_val:
                                if f_write(fp, str_key, new_val, flags=flags, max_wsize=max_wsize):
                                    chg_table[str_key] = new_val

                            continue

                        if not (_cache and str_key in _cache and _cache[str_key] == val):
                            if f_write(fp, str_key, val, flags=flags, max_wsize=max_wsize):
                                chg_table[str_key] = val

                    continue

                if insert:
                    if func:
                        new_val = func(str_key, None)
                        if f_write(fp, str_key, new_val, flags=flags, max_wsize=max_wsize):
                            chg_table[str_key] = new_val

                        continue

                    f_write(fp, str_key, val, flags=flags, max_wsize=max_wsize)
                    chg_table[str_key] = val

        return chg_table

    def remove(self, *records:str) -> Dict[str,Any]:
        """Batch decouple unlinking targeted index entry row selections extracting values payloads concurrently back onto general system pools.

        Args:
            *records (str): Variadic references containing key strings tokens to systematically purge from active pools sheets.

        Returns:
            Dict[str, Any]: Dictionary mapping successfully deleted record elements strings identifiers back onto their contents maps arrays blocks.
        """
        keys = set()
        for key in records:
            if isinstance(key, str):
                keys.add(key)
            elif key.__hash__: # pragma: no cover
                keys.add(str(key))
            else:
                if isinstance(key, JDbReader) and key.files_obj == self.files_obj:
                    ret = {}
                    with self.open(read_only=False) as fp:
                        has_SIGINT = self.file_lock.has_SIGINT
                        f_delete = self.f_delete
                        files_obj = self.files_obj
                        io, fp, key_fp = self.f_get_fp(fp)
                        io_read_key = io.read_key
                        for row_id in range(io.n_records-1, -1, -1):
                            if has_SIGINT(): break
                            key, _file_id, _offset, _row_size, _val_size, _ver, _days = io_read_key(key_fp, row_id)
                            jdb = _val = f_delete(fp, key, row=row_id)
                            if isinstance(jdb, JDb) and files_obj.is_group(jdb.files_obj, key):
                                jdb.remove_fast(jdb)

                            ret[key] = _val
                    return ret

                for kk in key:
                    keys.add(kk if isinstance(kk, str) else str(kk))

        ret = {}
        if not keys:
            return ret

        with self.open(read_only=True) as fp:
            io = self.io
            if io.n_records == 0:
                return ret

            key_table = io.key_table
            while True:
                keys = keys.intersection(key_table)
                if not keys:
                    return ret

                io, fp, _key_fp, sync_chg = self.f_get_write_fp(fp)
                if not sync_chg:
                    break

            has_SIGINT = self.file_lock.has_SIGINT
            f_delete = self.f_delete
            files_obj = self.files_obj
            keys = sorted([(kk,key_table[kk]) for kk in keys], key=lambda vv: -vv[1])
            for key,row_id in keys:
                if has_SIGINT():
                    break

                try:
                    jdb = val = f_delete(fp, key, row=row_id)
                    if isinstance(jdb, JDb) and files_obj.is_group(jdb.files_obj, key):
                        # cleanup the sub database
                        jdb.remove_fast(jdb)

                    ret[key] = val

                except OSError: # pragma: no cover
                    val = f_delete(fp, key, read_value=False)
                    ret[key] = None

                except KeyError: # pragma: no cover
                    pass

            return ret

    def remove_fast(self, *records:str) -> Set[str]:
        """Batch decouple index parameters keys ignoring payload decryption parsing stages optimizing deletion streams throughput processing speed metrics profiles.

        Args:
            *records (str): Unique text identifier token references variadic selection arguments context layout parameters maps tracks systems layers.

        Returns:
            Set[str]: Registry containing successfully discarded items keys list mappings logs.
        """
        keys = set()
        for key in records:
            if isinstance(key, str):
                keys.add(key)
            elif key.__hash__: # pragma: no cover
                keys.add(str(key))
            else:
                if isinstance(key, JDbReader) and key.files_obj == self.files_obj:
                    ret = set()
                    with self.open(read_only=False) as fp:
                        has_SIGINT = self.file_lock.has_SIGINT
                        f_delete = self.f_delete
                        files_obj = self.files_obj
                        io, fp, key_fp = self.f_get_fp(fp)
                        io_read_key = io.read_key
                        for row_id in range(io.n_records-1, -1, -1):
                            if has_SIGINT(): break
                            key, _file_id, _offset, _row_size, _val_size, _ver, _days = io_read_key(key_fp, row_id)
                            jdb = f_delete(fp, key, row=row_id, read_value=False)
                            if isinstance(jdb, JDb) and files_obj.is_group(jdb.files_obj, key):
                                jdb.remove_fast(jdb)

                            ret.add(key)
                    return ret

                for kk in key:
                    keys.add(kk if isinstance(kk, str) else str(kk))

        ret = set()
        if not keys:
            return ret

        with self.open(read_only=True) as fp:
            io = self.io
            if io.n_records == 0:
                return ret

            key_table = io.key_table
            while True:
                keys = keys.intersection(key_table)
                if not keys:
                    return ret

                io, fp, _key_fp, sync_chg = self.f_get_write_fp(fp)
                if not sync_chg:
                    break

            has_SIGINT = self.file_lock.has_SIGINT
            f_delete = self.f_delete
            files_obj = self.files_obj
            keys = sorted([(kk,key_table[kk]) for kk in keys], key=lambda vv: -vv[1])
            for key,row in keys:
                if has_SIGINT():
                    break

                try:
                    jdb = _val = f_delete(fp, key, row=row, read_value=False)
                    if isinstance(jdb, JDb) and files_obj.is_group(jdb.files_obj, key):
                        jdb.remove_fast(jdb)

                    ret.add(key)

                # Not a gzip file
                except OSError: # pragma: no cover
                    f_delete(fp, key, read_value=False)
                    ret.add(key)

                except KeyError: # pragma: no cover
                    pass

        return ret

    def rename(self, keys:Dict[str,str]) -> Dict[str,str]:
        """Batch re-label items mapping old text identifier codes tokens parameters straight into new destination unique name strings indices.

        Args:
            keys (Dict[str, str]): Translation target dictionary pairing former tags descriptors keys with freshly requested identifiers text.

        Returns:
            Dict[str, str]: Catalog mapping all altered item names coordinates changes records fields logs properties context.

        Raises:
            TypeError: If input mapping elements fail standard structural collection constraints.
        """
        if not isinstance(keys, dict):
            raise TypeError(keys)

        ret = {}
        if keys:
            with self.open(read_only=True) as fp:
                has_SIGINT = self.file_lock.has_SIGINT
                f_rename = self.f_rename
                for key,new_key in keys.items():
                    if has_SIGINT():
                        break

                    if key != new_key:
                        try:
                            if f_rename(fp, key, new_key):
                                ret[key] = new_key

                        except KeyError: # pragma: no cover
                            print(Style(f'Exception: {key} -> {new_key} already exist', yellow=1))

        return ret

    def check_error(self, parent:str='', level:int=0, fix_it:bool=False, verbose:bool=True) -> dict:
        """Validate logical structure integrity scan index layers maps checking anomalies corruptions cross-referencing files parameters indicators metrics models.

        Args:
            parent (str, optional): Hierarchy node namespace trace tracking origin references variables tokens. Defaults to ''.
            level (int, optional): Deepness limitation parameter capping child database recursion lookahead cycles. Defaults to 0.
            fix_it (bool, optional): Trigger dynamic reconstruction algorithms rewriting mismatching structures headers rows templates objects. Defaults to False.
            verbose (bool, optional): Enable terminal diagnostics print traces mapping structural verification flows metrics grids windows panels fields fields logs. Defaults to True.

        Returns:
            dict: Registry tracing all identified data alignment failures associated against internal sequence identifiers numbers lines.
        """
        error = {}
        del_parts = {}
        cache = []
        keys = {}
        cnt = 0
        is_unsync = self.fsize == 0
        with self.open(read_only=not fix_it) as fp: # pragma: no cover
            has_SIGINT = self.file_lock.has_SIGINT
            self._cache.clear()
            io, fp, key_fp = self.f_get_fp(fp)
            if verbose:
                print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] checking #{io.n_records:,}/{io.n_lines:,} [fix:{"Y" if fix_it else "N"}]', bright=1))

            io_read_key = io.read_key
            if level > 0: # pragma: no cover
                for key in sorted(io.groups):
                    if has_SIGINT():
                        return error

                    jdb = self.f_get_child(fp, key)
                    if isinstance(jdb, JDb):
                        full_key = f'{SEP_SYM}{key}' if not parent else f'{parent}{SEP_SYM}{key}'
                        _error = jdb.check_error(parent=full_key, level=level-1, fix_it=fix_it, verbose=False)
                        for _row, _key in _error.items():
                            error[f'{full_key}#{_row}'] = _key

                        print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{full_key}] #{jdb.io.n_records:,}/{jdb.io.n_lines:,}! {len(_error)} -> {len(error)}', red=len(_error) > 0, green=not _error, bright=1))

                for key,jdb in sorted(self.childs.items()):
                    if has_SIGINT():
                        return error

                    if jdb is None or key not in io.key_table or not isinstance(jdb, JDb):
                        continue

                    full_key = f'{key}' if not parent else f'{parent}{SEP_SYM}{key}'
                    _error = jdb.check_error(parent=full_key, level=level-1, fix_it=fix_it, verbose=False)
                    for _row, _key in _error.items():
                        error[f'{full_key}#{_row}'] = _key

                    print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{full_key}] #{jdb.io.n_records:,}/{jdb.io.n_lines:,}! {len(_error)} -> {len(error)}', red=len(_error) > 0, green=not _error, bright=1))

            for row_id in range(io.n_lines):
                if has_SIGINT():
                    return error

                try:
                    key, file_id, offset, row_size, val_size, _ver, _days = io_read_key(key_fp, row_id)
                except TypeError as e: # pragma: no cover
                    print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|error: {row_id}/{io.n_records}/{io.n_lines} {e}', red=1))
                    if fix_it:
                        io.write_key(key_fp, row_id, '', 0, 0, 0, 0)
                        continue

                    raise e

                if row_size > 0:
                    cache.append((file_id, offset, offset+row_size, val_size, row_id, key))

                if row_id >= io.n_records:
                    continue

                if key in keys: # pragma: no cover
                    _row_id = keys.get(key, -1)
                    val_a = val_b = None
                    try:
                        val_a = self.f_read(fp, key, row=row_id, copy=False)

                    except:
                        error[row_id] = (key, f'{file_id}:{offset}+{val_size}/{row_size}' if row_size > 0 else '', -1, -_row_id)
                        del_parts[row_id] = (file_id, offset, row_size, key)

                    if _row_id >= 0:
                        #pass;0;assert _row_id != row_id
                        _key, _file_id, _offset, _row_size, _val_size, _ver, _days = io_read_key(key_fp, _row_id)
                        try:
                            val_b = self.f_read(fp, _key, row=_row_id, copy=False)
                            if row_id not in error:
                                error[row_id] = (key, f'{file_id}:{offset}+{val_size}/{row_size}' if row_size > 0 else '', -1, -_row_id)
                                del_parts[row_id] = (file_id, offset, row_size, key)
                                val_a = None

                        except:
                            error[_row_id] = (_key, f'{_file_id}:{_offset}+{_val_size}/{_row_size}' if _row_size > 0 else '', -1, -row_id)
                            del_parts[_row_id] = (_file_id, _offset, _row_size, _key)

                    if val_b is None and val_a is not None:
                        keys[key] = row_id

                else:
                    keys[key] = row_id

            print(Style(f'CHK0 err:{len(error)} cache:{len(cache)} {io.n_records}/{io.n_lines}', red=len(error) > 0))
            keys.clear()
            cache = sorted(cache)
            total = len(cache)
            miss_parts = []
            # fail_parts = []
            chk_parts = {}
            rep_parts = {}
            if total > 1:
                curr_file_id = -1
                curr_vsize = curr_row = curr_offset = file_size = next_offset = record_cnt = 0
                curr_key = ''
                for ii in range(total):
                    if has_SIGINT():
                        return error

                    file_id1, head1, tail1, size1, row1, key1 = cache[ii]
                    if curr_file_id != file_id1:
                        if curr_file_id >= 0: # pragma: no cover
                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|finish file_id:{curr_file_id} offset:{next_offset:,} tb:{file_size:,} records:{record_cnt:,}', green=1, bg_red=file_size!=next_offset))

                        curr_file_id = file_id1
                        file_size = io.file_table[curr_file_id]
                        if head1 > 0:  # pragma: no cover
                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|miss. file_id:{curr_file_id} expect:0 diff:{head1:,} tb:{file_size:,}', yellow=1))
                            miss_parts.append((curr_file_id, 0, head1))

                        #pass;0;assert tail1 > head1
                        curr_offset = head1
                        next_offset = tail1
                        curr_vsize = size1
                        curr_row = row1
                        curr_key = key1
                        record_cnt = 0
                        print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|check file_id:{curr_file_id} tb:{file_size:,}', cyan=0))

                    elif head1 == next_offset:
                        curr_offset = head1
                        next_offset = tail1
                        curr_vsize = size1
                        curr_row = row1
                        curr_key = key1
                    else:  # pragma: no cover
                        if head1 > next_offset:
                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|miss.. file_id:{curr_file_id} expect:{next_offset:,} diff:{head1-next_offset:,} tb:{file_size:,}', yellow=1))
                            miss_parts.append((curr_file_id, next_offset, head1-next_offset))
                            curr_offset = head1
                            next_offset = tail1

                        elif head1 == curr_offset and tail1 == next_offset:
                            rep_parts[row1] = curr_file_id, head1, tail1-head1, key1

                        else:
                            val_size1 = val_size2 = 0
                            if row1 not in chk_parts:
                                try:
                                    if row1 < io.n_records:
                                        val1 = self.f_read(fp, key1, row=row1, copy=False)
                                        if size1 > 0:
                                            chk_parts[row1] = val_size1 = size1
                                        else:
                                            _bytes = io.dumps_with_zip(val1)
                                            chk_parts[row1] = val_size1 = len(_bytes)
                                            size1 = min(tail1-head1, val_size1)
                                    else:
                                        chk_parts[row1] = 0
                                except:
                                    chk_parts[row1] = -1
                            else:
                                val_size1 = chk_parts.get(row1, 0)

                            if curr_row not in chk_parts:
                                try:
                                    if curr_row < io.n_records:
                                        val2 = self.f_read(fp, curr_key, row=curr_row, copy=False)
                                        if curr_vsize > 0:
                                            chk_parts[curr_row] = val_size2 = curr_vsize
                                        else:
                                            _bytes = io.dumps_with_zip(val2)
                                            chk_parts[curr_row] = val_size2 = len(_bytes)
                                            curr_vsize = min(next_offset-curr_offset, val_size2)
                                    else:
                                        chk_parts[curr_row] = 0
                                except:
                                    chk_parts[curr_row] = -1
                            else:
                                val_size2 = chk_parts.get(curr_row, 0)

                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|fail file_id:{curr_file_id} prev:{curr_offset:,}~{next_offset:,}:{val_size2} vs {head1:,}~{tail1:,}:{val_size1} | records:{record_cnt+1} tb:{file_size:,}', red=1))
                            # #pass;0;assert curr_offset < head1 < next_offset

                            if val_size1 > 0 and val_size2 <= 0: # pylint: disable=R
                                # |xxxx]          [xxxxxxx]
                                #    [vvvv]          [vvv]
                                del_parts[curr_row] = (curr_file_id, curr_offset, head1-curr_offset, curr_key)
                                curr_offset = head1
                                next_offset = max(tail1, next_offset)
                                curr_vsize = size1
                                curr_row = row1
                                curr_key = key1

                            elif val_size1 <= 0 and val_size2 > 0: # pylint: disable=R
                                # |vvvv]          [vvvvvvv]
                                #    [xxxx]          [xxx]
                                del_parts[row1] = (curr_file_id, next_offset, tail1-next_offset, key1)

                            elif val_size1 <= 0 and val_size2 <= 0:
                                # [xxxx]           [xxxxxx]
                                #    [xxxx]          [xxx]
                                next_offset = max(tail1, next_offset)
                                del_parts[curr_row] = (curr_file_id, curr_offset, head1-curr_offset, curr_key)
                                del_parts[row1] = (curr_file_id, head1, next_offset-head1, key1)

                            else: # val_size1 > 0 and val_size2 > 0
                                del_parts[curr_row] = (curr_file_id, curr_offset, head1-curr_offset, curr_key)
                                del_parts[row1] = (curr_file_id, next_offset, tail1-next_offset, key1)
                                curr_offset = head1
                                next_offset = max(tail1, next_offset)
                                curr_vsize = size1
                                curr_row = row1
                                curr_key = key1

                            # fail_parts.append((curr_file_id, curr_offset, next_offset-curr_offset, curr_row, curr_key, curr_vsize, val_size2, head1, tail1-head1, row1, key1, size1, val_size1))

                    record_cnt += 1
                    jj = ii + 1
                    if jj < total:  # pragma: no cover
                        file_id2, head2, tail2, size2, row2, key2 = cache[jj]
                        if file_id2 == file_id1 and head1 <= head2 < tail1: # row2 overlap row1
                            val_size1 = val_size2 = 0
                            if row1 not in chk_parts:
                                try:
                                    if row1 < io.n_records:
                                        val1 = self.f_read(fp, key1, row=row1, copy=False)
                                        if size1 > 0:
                                            chk_parts[row1] = val_size1 = size1
                                        else:
                                            _bytes = io.dumps_with_zip(val1)
                                            chk_parts[row1] = val_size1 = len(_bytes)
                                            size1 = min(tail1-head1, val_size1)
                                    else:
                                        chk_parts[row1] = 0
                                except:
                                    chk_parts[row1] = -1
                            else:
                                val_size1 = chk_parts.get(row1, 0)
                                if size1 == 0:
                                    size1 = min(tail1-head1, val_size1)

                            if row2 not in chk_parts:
                                try:
                                    if row2 < io.n_records:
                                        val2 = self.f_read(fp, key2, row=row2, copy=False)
                                        if size2 > 0:
                                            chk_parts[row2] = val_size2 = size2
                                        else:
                                            _bytes = io.dumps_with_zip(val2)
                                            chk_parts[row2] = val_size2 = len(_bytes)
                                            size2 = min(tail2-head2, val_size2)
                                    else:
                                        if val_size1 > 0 and head1+size1 <= head2:
                                            if size2 > 0:
                                                chk_parts[row2] = val_size2 = size2
                                            else:
                                                chk_parts[row2] = tail2-head2
                                        else:
                                            chk_parts[row2] = 0
                                except:
                                    chk_parts[row2] = -1
                            else:
                                val_size2 = chk_parts.get(row2, 0)
                                if size2 == 0:
                                    size2 = min(tail2-head2, val_size2)

                            fix_offset1 = fix_size1 = -1
                            if val_size1 > 0:
                                if size1 < val_size1:
                                    pass
                                elif head1+size1 <= head2:
                                    fix_offset1 = head1
                                    fix_size1 = head2 - head1
                                else:
                                    fix_offset1 = head1
                                    fix_size1 = size1

                            fix_offset2 = fix_size2 = -1
                            if val_size2 > 0 :
                                if size2 < val_size2:
                                    pass
                                elif head2+size2 <= tail2:
                                    fix_offset2 = head2
                                    fix_size2 = tail2 - head2
                                else:
                                    fix_offset2 = head2
                                    fix_size2 = size2

                            if fix_offset1 >= 0:
                                _key, _file_id, _offset, _row_size, _val_size, _ver, _days = io.read_key(key_fp, row1)
                                fix_val_size = val_size1 if _val_size == 0 else _val_size
                                if file_id1 == _file_id and _offset == fix_offset1 and _row_size >= fix_size1 and _key == key1:
                                    if fix_it:
                                        io.write_key(key_fp, row1, key1, _file_id, _offset, fix_size1, fix_val_size, _ver, days=_days)
                                        print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] FIX {_key} row:{row1} @{_file_id}:{_offset} size:{_val_size}/{_row_size} -> {fix_val_size}/{fix_size1} ', green=1, bright=1))
                                    else:
                                        print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] TRY {_key} row:{row1} @{_file_id}:{_offset} size:{_val_size}/{_row_size} -> {fix_val_size}/{fix_size1} ', green=1))
                                else:
                                    error[row1] = (key1, f'{file_id1}:{head1}+{fix_size1 if fix_size1 > 0 else 0}/{tail1-head1}', fix_offset1, fix_size1)
                            else:
                                error[row1] = (key1, f'{file_id1}:{head1}+{fix_size1 if fix_size1 > 0 else 0}/{tail1-head1}', fix_offset1, fix_size1)

                            if fix_offset2 >= 0:
                                _key, _file_id, _offset, _row_size, _val_size, _ver, _days = io.read_key(key_fp, row2)
                                fix_val_size = val_size2 if _val_size == 0 else _val_size
                                if file_id2 == _file_id and _offset == fix_offset2 and _row_size >= fix_size2 and _key == key2:
                                    if fix_it:
                                        io.write_key(key_fp, row2, key2, _file_id, _offset, fix_size2, fix_val_size, _ver, days=_days)
                                        print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] FIX {_key} row:{row1} @{_file_id}:{_offset} size:{_val_size}/{_row_size} -> {fix_val_size}/{fix_size2} ', green=1, bright=1))
                                    else:
                                        print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] TRY {_key} row:{row1} @{_file_id}:{_offset} size:{_val_size}/{_row_size} -> {fix_val_size}/{fix_size2} ', green=1))
                                else:
                                    error[row2] = (key2, f'{file_id2}:{head2}+{fix_size2 if fix_size2 > 0 else 0}/{tail2-head2}', fix_offset2, fix_size2)

                            else:
                                error[row2] = (key2, f'{file_id2}:{head2}+{fix_size2 if fix_size2 > 0 else 0}/{tail2-head2}', fix_offset2, fix_size2)

                            if verbose and (row2 in error or row1 in error):
                                print(Style(f'[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] ERROR '\
                                    f'\n\t{row1}:{key1}({file_id1},{head1}+{size1}:{tail1})=>{fix_offset1}+{fix_size1}'\
                                    f'\n\t{row2}:{key2}({file_id2},{head2}+{size2}:{tail2})=>{fix_offset2},{fix_size2}',
                                    yellow=1, bright=(row1 < io.n_records or row2 < io.n_records)))

                            cnt += 1

                    if verbose and (ii % 1000) == 0:
                        print('.' if cnt == 0 else 'x', end='', flush=True)
                        cnt = 0

                print(Style(f'\nRESULT err:{len(error)} miss:{len(miss_parts)} del:{len(del_parts)} rep:{len(rep_parts)}', yellow=1))
                if fix_it and (miss_parts or del_parts or rep_parts):
                    for _ in range(10):
                        if has_SIGINT():
                            return error

                        sleep(10)

                if miss_parts:
                    if fix_it:
                        for (_file_id, _offset, _size) in miss_parts:
                            io.write_key(key_fp, io.n_lines, '', _file_id, _offset, _size, 0)
                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] ADD row:{io.n_lines} @{_file_id}:{_offset}+{_size}', green=1, bright=1))
                            io.n_lines += 1
                            io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF

                    print('\nMISS:', miss_parts)

                if del_parts:
                    if fix_it:
                        for row_id,(_file_id, _offset, _size, _key) in del_parts.items():
                            record_t = io.n_records-1
                            if row_id > record_t:
                                io.write_key(key_fp, row_id, '', 0, 0, 0, 0)
                                io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                                continue

                            if row_id < record_t:
                                io.key_table.pop(_key, 0)
                                rec_args = io.copy_key(key_fp, record_t, row_id, decode=True)
                                io.key_table[rec_args[0]] = row_id
                                io.swap_id = (io.swap_id + 1) & 0X_7FF_FFFF_FFFF

                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] DEL row:{row_id}/{record_t+1} @{_file_id}:{_offset}+{_size}', cyan=1, bright=1))
                            io.n_records = max(io.n_records - 1, 0) # must before write_key, after key_table.pop
                            io.write_key(key_fp, record_t, '', _file_id, _offset, _size, 0)
                            io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                            io.remv_id = (io.remv_id + 1) & 0X_7FF_FFFF_FFFF

                    print('\nDEL:', del_parts, '\nCHK:', chk_parts)

                if rep_parts:
                    if fix_it:
                        for row_id,(_file_id, _offset, _size, _key) in rep_parts.items():
                            line_t = io.n_lines - 1
                            if row_id < line_t:
                                rec_args = io.read_key(key_fp, line_t)
                                io.write_key(key_fp, row_id, *rec_args)

                            print(Style(f'\n[{level}|{id(self):x}|{hex(id(io))[-5:-1]}|{io.sync_id%10000}|{io.key_limit_str}|{parent}] REP row:{row_id}/{line_t+1} @{_file_id}:{_offset}+{_size}', cyan=1, bright=1))
                            io.write_key(key_fp, line_t, '', 0, 0, 0, 0)
                            io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                            key_fp.flush() # before key_table
                            io.key_table.pop(_key, 0)

                    print('\nREP:', rep_parts)

        if is_unsync: # pragma: no cover
            self.unsync()

        return error

    def add_group(self, key:str) -> JDb:
        """Initialize an isolated nested cluster sub-database partition workspace domain.

        Args:
            key (str): Subfolder tracking name selector token text string.

        Returns:
            JDb: The newly constructed partition node interface.

        Raises:
            KeyError: If incoming cluster nomenclature violates basic string character constraints.
        """
        if not re_match(r'^[0-9A-Za-z_]+$', key):
            raise KeyError

        with self.open(read_only=True) as fp:
            jdb = self.f_get_group(fp, key)
            if jdb is None:
                jdb = self._decode_row(0x10, 0, key, 0)
                self.f_write(fp, key, jdb)
                self.io.groups[key] = jdb
                self.childs.pop(key, None)

            #pass;0;assert isinstance(jdb, JDbReader)
            return jdb

    def del_group(self, key:str) -> Optional[JDb]:
        """Exterminate a nested sub-database cluster namespace dropping structural tracking indicators permanently.

        Args:
            key (str): Sub-space lookup target selector token text string.

        Returns:
            Optional[JDb]: The destroyed group instance handle if successfully cleared, None fallback otherwise.
        """
        with self.open(read_only=True) as fp:
            jdb = self.f_get_group(fp, key)
            if isinstance(jdb, JDb):
                self.f_delete(fp, key, read_value=False, flags=JFlag(0))
                self.io.groups.pop(key, None)
                self.childs.pop(key, None)
                return jdb

        return None

    def f_get_child(self, fp_dict:Dict[int,IO], name:str) -> Optional[JDb]:
        """Low level routing factory resolving child detached storage pipelines inside current streams boundaries maps trackers.

        Args:
            fp_dict (Dict[int, IO]): Active file pointers registration collection maps table.
            name (str): Named item node partition token text descriptor selector.

        Returns:
            Optional[JDb]: Open operational child dataset workspace reference, or None if validation fails.
        """
        io = self.io
        childs = self.childs
        groups = io.groups

        if name not in io.key_table: # pragma: no cover
            childs.pop(name, None)
            groups.pop(name, None)
            return None

        if name in childs:
            jdb = childs.get(name, None)
        elif name in groups:
            jdb = self.f_get_group(fp_dict, name)
        else: # pragma: no cover
            return None

        if jdb is None: # pragma: no cover
            KEY_path = self.f_read(fp_dict, name)
            if not isinstance(KEY_path, str):
                return None

            if not KEY_path:
                KEY_path = None

            elif not path_exists(KEY_path):
                return None

            childs[name] = jdb = JDb(KEY_path)

        return jdb

    def f_change_days(self, fp_dict:Dict[int,IO], key:str, days:Union[int,float,str,dt_date,datetime]=-1) -> bool:
        """
        Modify the timestamp of a specific Key at the low level without changing the data content.

        Args:
            fp_dict (Dict[int, IO]): The file descriptor set for the current thread.
            key (str): The name of the target key.
            days (Union[int, float, str, dt_date, datetime], optional): The number of days, time object, or string representation of the date to be written. Defaults to -1.

        Returns:
            bool: Returns True if the write is successful; returns False if it fails or the Key is not found.

        """
        key = str(key) if not isinstance(key, str) else key
        if isinstance(days, str): # pragma: no cover
            try:
                days = JIo.z_conv_str_to_days(days)
            except ValueError: # pragma: no cover
                return False

        elif not isinstance(days, int):
            days = JIo.z_conv_days(days)

        try:
            io, fp_dict, key_fp, _sync_chg = self.f_get_write_fp(fp_dict)
            row = io.key_table[key]
            if not io.n_records > row >= 0:
                return False

            _key, file_id, offset, row_size, val_size, _ver, old_days = io.read_key(key_fp, row)
            _new2, _old2 = old_days & NEW_DAY_MASK, old_days & OLD_DAY_MASK
            if days < 0:
                _new1, _old1 = 0, io.days
            else:
                _new1, _old1 = days & NEW_DAY_MASK, days & OLD_DAY_MASK
                if _old1 == 0 and _new1 > 0:
                    _new1 >>= NEW_DAY_SHIFT
                    _new1, _old1 = (0, _new1) if _new1 < _old2 else ((_new1 - _old2), _old2)
                    _new1 <<= NEW_DAY_SHIFT
                    days = (_new1 & NEW_DAY_MASK) | (_old1 & OLD_DAY_MASK)
                    _new1 = 1 if _new1 == 0 else _new1

            if _new1 & _new1 != _new2 or _old1 != _old2:
                io.write_key(key_fp, row, key, file_id, offset, row_size, val_size, days=days if days < 0 or _new1 else days|CHG_DAY_FLAG)
                io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF

            return True

        except KeyError: # pragma: no cover
            return False

        return False

    def _get_dead_row(self, key_fp, key:str, req_size:int, flags:Optional[JFlag]=None, max_wsize:Optional[int]=None) -> Tuple[int,int,str,int,int,int]:
        """ Internal core method: Find a reusable space block within the "deleted or invalid rows (Dead Lines)" of the database index structure.

        Args:
            key_fp (IO): The open stream pointer of the KEY index file.
            key (str): The target key name currently undergoing the write operation.
            req_size (int): The space capacity required for the newly written binary data.
            flags (Optional[JFlag], optional): Operation flags controlling whether space Revert or Split is allowed.
            max_wsize (Optional[int], optional): The maximum search window length for finding dead lines.

        Returns:
            Tuple[int, int, int, int, int]: Contains (safe baseline row, found reusable row number, file ID, offset, block size).
        """
        io = self.io
        n_lines = io.n_lines
        n_records = io.n_records

        max_wsize = self.max_wsize if max_wsize is None else max_wsize
        can_revert = JFlag.REVERT in flags
        can_split = JFlag.SPLIT in flags

        if can_revert:
            start_line = safe_line = min(max(self.safe_line, n_records), n_lines)
            chg_keys = self.chg_keys
            if key not in chg_keys:
                chg_keys.add(key)
                self.safe_line = safe_line + 1

        else:
            start_line = safe_line = self.safe_line = n_records

        extra_rows = n_lines - safe_line
        if extra_rows > 0 and req_size >= 0 and max_wsize > 0:
            row, file_id, offset, row_size = io.get_dead_row(safe_line, req_size)
            if n_lines > row >= safe_line:
                if row_size >= req_size > 0:
                    if can_split:
                        min_value_size = io.min_value_size
                        split_size = max(min_value_size, int(req_size * (1 + io.reserved_rate)))
                        if row_size >= (split_size + max(64, min_value_size)):
                            new_offset = offset + split_size
                            new_size = row_size - split_size
                            io.n_lines += 1
                            io.write_key(key_fp, n_lines, '', file_id, new_offset, new_size, 0, 0)
                            io.write_key(key_fp, row, '', file_id, offset, split_size, 0, 0)
                            row_size = split_size

                return start_line, row, file_id, offset, row_size

            index_size = io.index_size
            window_size = min(max_wsize, io.window_size)
            start_row = safe_line + randint(0, extra_rows // window_size) * window_size
            row = min(n_lines, start_row + window_size) - 1
            io.seek(key_fp, start_row)
            buffer_size = index_size * (row + 1 - start_row)
            buffer = key_fp.read(buffer_size)
            if len(buffer) == buffer_size:
                KEY_loads = io.KEY_loads
                idx = buffer_size - index_size
                ext_row = -1
                while row >= start_row:
                    try:
                        _dead_key, file_id, offset, row_size, __s, __v, __d = KEY_loads(buffer[idx:idx+index_size])
                    except ValueError: # pragma: no cover
                        # reset dead row if fail to load
                        file_id = offset = row_size = 0
                        io.write_key(key_fp, row, '', file_id, offset, row_size, 0, 0, 0)

                    if req_size == 0:
                        if row_size == 0:
                            return start_line, row, file_id, offset, row_size

                    elif row_size >= req_size:
                        if can_split:
                            min_value_size = io.min_value_size
                            split_size = max(min_value_size, int(req_size * (1 + io.reserved_rate)))
                            if row_size >= (split_size + max(64, min_value_size)):
                                new_offset = offset + split_size
                                new_size = row_size - split_size
                                if ext_row < 0:
                                    io.n_lines += 1
                                    io.write_key(key_fp, n_lines, '', file_id, new_offset, new_size, 0, 0)
                                else:
                                    io.write_key(key_fp, ext_row, '', file_id, new_offset, new_size, 0, 0)

                                io.write_key(key_fp, row, '', file_id, offset, split_size, 0, 0)
                                row_size = split_size

                        return start_line, row, file_id, offset, row_size

                    elif row_size == 0:
                        ext_row = row

                    row -= 1
                    idx -= index_size

        return start_line, -1, 0, 0, 0

    def f_write_bytes(self, fp_dict:Dict[int,IO], key:str, val:bytes, days:int=-1, flags:Optional[JFlag]=None, max_wsize:Optional[int]=None) -> bool:
        """ Low-level pipeline method: directly commit raw un-serialized binary byte blocks into physical content sectors tracks.

        Args:
            fp_dict (Dict[int, IO]): Current thread transactional context opens registries handles maps.
            key (str): Unique data record pointer lookup name token layout string.
            val (bytes): Raw uncompressed payload byte configuration data chunk array.
            days (int, optional): Compact timeline relative days counter index selection number. Defaults to -1.
            flags (Optional[JFlag], optional): Custom modifier bitflags overrides. Defaults to None.
            max_wsize (Optional[int], optional): Maximum search lookahead steps window constraint index number. Defaults to None.

        Returns:
            bool: True if binary persistence pipelines execute smoothly, False fallback otherwise.
        """
        if isinstance(days, str): # pragma: no cover
            try:
                days = JIo.z_conv_str_to_days(days)
            except ValueError: # pragma: no cover
                days = -1

        key = str(key) if not isinstance(key, str) else key
        val = bytes(val) if isinstance(val, bytearray) else val
        if not isinstance(val, bytes): # pragma: no cover
            raise JTypeError('invalid value type')

        if len(key) > MAX_KEY_SIZE:
            raise JKeyError(f'key[{key}] too long (max={MAX_KEY_SIZE})')

        flags = self.flags if flags is None else JFlag(flags)
        can_revert = JFlag.REVERT in flags
        _cache = self._cache
        row = self.io.key_table[key]
        while True:
            if row >= 0:
                # (Exist + Value|Header)
                io, fp_dict, key_fp = self.f_get_fp(fp_dict)
                if can_revert:
                    safe_line = min(max(self.safe_line, io.n_records), io.n_lines)
                else:
                    safe_line = self.safe_line = io.n_records

                _key, file_id, offset, row_size, val_size, _ver, old_days = row_info = io.read_key(key_fp, row)
                # (Exist + Header)
                if row_size == 0:
                    # (Exist + Header != CHG + Header/Value)
                    io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
                    if sync_chg: # pragma: no cover
                        row = io.key_table[key]
                        if not io.n_records > row >= 0:
                            continue

                        _row_info = io.read_key(key_fp, row)
                        if _row_info != row_info:
                            continue

                    # (Exist + Header != CHG + Value) -> use dead/new row
                    data = val
                    new_val_size = len(data)
                    safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, new_val_size, flags=flags, max_wsize=max_wsize)
                    n_lines = io.n_lines
                    safe_h = io.n_records # n_records =
                    if dead_row < 0: # use new_row
                        dead_row = n_lines
                        io.n_lines = n_lines = n_lines + 1 # MUST call write_key(dead_row, ..) first
                        data = io.pad(data, max_size=0)
                        new_row_size = len(data)
                        val_fp, new_file_id, new_offset = self.f_get_val_fp(fp_dict, req_size=new_row_size) # create new space

                    else: # use dead row
                        new_file_id = dead_file_id
                        new_offset = dead_offset
                        new_row_size = dead_row_size
                        val_fp, __i, __o = self.f_get_val_fp(fp_dict, new_file_id)

                    val_fp.seek(new_offset)
                    _write_size = val_fp.write(data)

                    dead_h = safe_line
                    if dead_row > dead_h: # pragma: no cover
                        # DEAD[h] -> DEAD[t+1] or DEAD[m]
                        _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
                    else: # pragma: no cover
                        pass

                    # old value -> DEAD[h]
                    # new value -> REC[n]
                    io.write_key(key_fp, dead_h, key, file_id, offset, row_size, val_size, days=old_days)
                    io.write_key(key_fp, row, key, new_file_id, new_offset, new_row_size, new_val_size, days=old_days|CHG_DAY_FLAG)
                    _cache.pop(key, None)
                    io.file_table[new_file_id] = max(io.file_table[new_file_id], new_offset + new_row_size)
                    io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                    return True

                # (Exist + Value vs CHG + Value)
                new_row_size = row_size
                data = val
                new_val_size = len(data)
                if new_row_size >= new_val_size and val_size == new_val_size: # pragma: no cover
                    # (Exist + Value != CHG + Value) use dead/new row
                    io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
                    if sync_chg:
                        row = io.key_table[key]
                        if not io.n_records > row >= 0:
                            continue

                        _row_info = io.read_key(key_fp, row)
                        if _row_info != row_info:
                            continue

                if row_size >= new_val_size and (not can_revert or key in self.chg_keys):
                    # use same row
                    _cache.pop(key, None)
                    n_lines = io.n_lines
                    val_fp, __i, __o = self.f_get_val_fp(fp_dict, file_id)
                    val_fp.seek(offset)
                    _write_size = val_fp.write(data)
                    io.write_key(key_fp, row, key, file_id, offset, row_size, new_val_size, days=old_days|CHG_DAY_FLAG)
                    io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                    return True

                safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, new_val_size, flags=flags, max_wsize=max_wsize)
                n_lines = io.n_lines
                if dead_row < 0: # use new row
                    dead_row = n_lines
                    io.n_lines = n_lines = n_lines + 1  # MUST call write_key(dead_row, ..) first
                    data = io.pad(data, max_size=0)
                    new_row_size = len(data)
                    val_fp, new_file_id, new_offset  = self.f_get_val_fp(fp_dict, req_size=new_row_size)

                else: # use dead row
                    new_file_id = dead_file_id
                    new_offset = dead_offset
                    new_row_size = dead_row_size
                    val_fp, __i, __o = self.f_get_val_fp(fp_dict, new_file_id)

                val_fp.seek(new_offset)
                _write_size = val_fp.write(data)
                dead_h = safe_line
                if dead_row > dead_h:
                    # DEAD[h] -> DEAD[t+1] or DEAD[m]
                    _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
                else: # pragma: no cover
                    pass

                # old value -> DEAD[h]
                # new value -> REC[n]
                io.write_key(key_fp, dead_h, key, file_id, offset, row_size, val_size, days=old_days)
                io.write_key(key_fp, row, key, new_file_id, new_offset, new_row_size, new_val_size, days=old_days|CHG_DAY_FLAG)
                _cache.pop(key, None)
                io.file_table[new_file_id] = max(io.file_table[new_file_id], new_offset + new_row_size)
                io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                return True

            # (Not Exist)
            io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
            if sync_chg: # pragma: no cover
                row = io.key_table[key]
                if row >= 0:
                    continue

            break

        # (Not Exist, ADD + Value) -> use dead/new row
        data = val
        new_val_size = len(data)
        safe_line, dead_row, new_file_id, new_offset, new_row_size = self._get_dead_row(key_fp, key, new_val_size, flags=flags, max_wsize=max_wsize)
        safe_h = io.n_records
        n_lines = io.n_lines
        if dead_row < 0: # use new row
            dead_row = n_lines
            io.n_lines = n_lines = n_lines + 1  # MUST call write_key(dead_row, ..) first
            data = io.pad(data, max_size=0)
            new_row_size = len(data)
            val_fp, new_file_id, new_offset  = self.f_get_val_fp(fp_dict, req_size=new_row_size)

        # use dead row
        else: # pragma: no cover
            val_fp, __i, __o = self.f_get_val_fp(fp_dict, new_file_id)

        val_fp.seek(new_offset)
        _write_size = val_fp.write(data)
        dead_h = safe_line
        if dead_row > dead_h:
            # DEAD[h] -> DEAD[t+1] or DEAD[m]
            _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
        else: # pragma: no cover
            pass

        # SAFE[h] -> DEAD[h]
        _safe_bytes = io.copy_key(key_fp, safe_h, dead_h) if dead_h > safe_h else None

        # new key -> SAFE[h] (= REC[t+1])
        io.write_key(key_fp, safe_h, key, new_file_id, new_offset, new_row_size, new_val_size, days=days if days < 0 or days & NEW_DAY_MASK else days|CHG_DAY_FLAG)
        _cache.pop(key, None)
        io.file_table[new_file_id] = max(io.file_table[new_file_id], new_offset + new_row_size)
        io.n_records += 1
        io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
        key_fp.flush() # before key_table
        io.key_table[key] = safe_h
        return True

    def f_write(self, fp_dict:Dict[int,IO], key:str, val:Any, days:int=-1, flags:Optional[JFlag]=None, max_wsize:Optional[int]=None) -> bool:
        """ Low-level pipeline method: serialize, compress, and record dynamic Python value entries mapping into target filesystem tracks safely.

        Args:
            fp_dict (Dict[int, IO]): Open file handles tracking collections metrics maps.
            key (str): Destination dictionary descriptor reference character token text string layout context.
            val (Any): Payload instance content python object structure to serialize.
            days (int, optional): Calendar modification timing tracking parameter representation number. Defaults to -1.
            flags (Optional[JFlag], optional): strategic behavioral modifiers flags. Defaults to None.
            max_wsize (Optional[int], optional): Maximum search lookahead steps window constraint index number. Defaults to None.

        Returns:
            bool: True if serialization persistence completes smoothly, False if transaction logic drops inputs.

        Raises:
            TypeError: If interceptor write hooks reject incoming inputs configuration candidate attributes.
        """
        if isinstance(days, str):
            try:
                days = JIo.z_conv_str_to_days(days)
            except ValueError: # pragma: no cover
                days = -1

        key = str(key) if not isinstance(key, str) else key
        val = bytes(val) if isinstance(val, bytearray) else val

        if self.write_hook and not self.write_hook(key, val):
            raise JTypeError(f'invalid format: key="{key}" val_type={type(val)})')

        if len(key) > MAX_KEY_SIZE:
            raise JKeyError(f'key[{key}] too long (max={MAX_KEY_SIZE})')

        flags = self.flags if flags is None else JFlag(flags)
        can_revert = JFlag.REVERT in flags
        _cache = self._cache
        cache_limit = self._cache_limit
        row = self.io.key_table[key]
        checked = False
        while True:
            if row >= 0:
                # (Exist + Value|Header)
                if not checked and cache_limit != 0 and key in _cache:
                    if _cache[key] == val:
                        _cache.move_to_end(key, last=True)
                        return False

                    checked = True

                io, fp_dict, key_fp = self.f_get_fp(fp_dict)
                if can_revert:
                    safe_line = min(max(self.safe_line, io.n_records), io.n_lines)
                else:
                    safe_line = self.safe_line = io.n_records

                _key, file_id, offset, row_size, val_size, _ver, old_days = row_info = io.read_key(key_fp, row)

                _type_id, _type_val, _type_size = self._encode_row(key, val)
                # (Exist + Header)
                if row_size == 0:
                    if _type_id == file_id and _type_val == offset and _type_size == val_size:
                        # (Exist + Header == CHG + Header)
                        if file_id == 0x10 and isinstance(val, JDbReader): # pragma: no cover
                            self._set_child(key, val)

                        if cache_limit != 0:
                            self._update_cache(key, val, copy=True)

                        return False

                    # (Exist + Header != CHG + Header/Value)
                    io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
                    if sync_chg: # pragma: no cover
                        row = io.key_table[key]
                        if not io.n_records > row >= 0:
                            continue

                        _row_info = io.read_key(key_fp, row)
                        if _row_info != row_info:
                            continue

                    if _type_id >= 0:
                        # (Exist + Header != CHG + Header) -> use dead/new row
                        if not can_revert or key in self.chg_keys:
                            # use same row
                            n_lines = io.n_lines
                            io.write_key(key_fp, row, key, _type_id, _type_val, 0, _type_size, days=old_days|CHG_DAY_FLAG)

                        else:
                            safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, 0, flags=flags, max_wsize=max_wsize)
                            n_lines = io.n_lines
                            if dead_row < 0: # use new row
                                dead_row = n_lines
                                io.n_lines = n_lines = n_lines + 1 # MUST call write_key(dead_row, ..) first

                            dead_h = safe_line
                            if dead_row > dead_h:
                                # DEAD[h] -> DEAD[t+1] or DEAD[m]
                                _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
                            else:
                                pass

                            # old value -> DEAD[h] (=SAFE[t+1])
                            # new value -> REC[n]
                            io.write_key(key_fp, dead_h, key, file_id, offset, row_size, val_size, days=old_days)
                            io.write_key(key_fp, row, key, _type_id, _type_val, 0, _type_size, days=old_days|CHG_DAY_FLAG)

                        if _type_id == 0x10 and isinstance(val, JDbReader):
                            self._set_child(key, val)

                        # without change key table and file table
                        io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                        if cache_limit != 0:
                            self._update_cache(key, val, copy=True)
                        return True

                    # (Exist + Header != CHG + Value) -> use dead/new row
                    data = _type_val
                    new_val_size = len(data)
                    safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, new_val_size, flags=flags, max_wsize=max_wsize)
                    n_lines = io.n_lines
                    safe_h = io.n_records # = n_records
                    if dead_row < 0: # use new_row
                        dead_row = n_lines
                        io.n_lines = n_lines = n_lines + 1 # MUST call write_key(dead_row, ..) first
                        data = io.pad(data, max_size=0)
                        new_row_size = len(data)
                        val_fp, new_file_id, new_offset = self.f_get_val_fp(fp_dict, req_size=new_row_size) # create new space

                    else: # use dead row
                        new_file_id = dead_file_id
                        new_offset = dead_offset
                        new_row_size = dead_row_size
                        val_fp, __i, __o = self.f_get_val_fp(fp_dict, new_file_id)

                    val_fp.seek(new_offset)
                    _write_size = val_fp.write(data)
                    dead_h = safe_line
                    if dead_row > dead_h:
                        # DEAD[h] -> DEAD[t+1] or DEAD[m]
                        _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
                    else:
                        pass

                    # old value -> DEAD[h]
                    # new value -> REC[n]
                    io.write_key(key_fp, dead_h, key, file_id, offset, row_size, val_size, days=old_days)
                    io.write_key(key_fp, row, key, new_file_id, new_offset, new_row_size, new_val_size, days=old_days|CHG_DAY_FLAG)
                    io.file_table[new_file_id] = max(io.file_table[new_file_id], new_offset + new_row_size)
                    io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                    if cache_limit != 0:
                        self._update_cache(key, val, copy=True)
                    return True

                new_row_size = row_size
                # (Exist + Value)
                if _type_id >= 0:
                    # (Exist + Value != CHG + Header) -> use dead/new row
                    io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
                    if sync_chg: # pragma: no cover
                        row = io.key_table[key]
                        if not io.n_records > row >= 0:
                            continue

                        _row_info = io.read_key(key_fp, row)
                        if _row_info != row_info:
                            continue

                    safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, 0, flags=flags, max_wsize=max_wsize)
                    n_lines = io.n_lines
                    if dead_row < 0: # use new row
                        dead_row = n_lines
                        io.n_lines = n_lines = n_lines + 1 # MUST call write_key(dead_row, ..) first

                    dead_h = safe_line
                    if dead_row > dead_h:
                        # DEAD[h] -> DEAD[t+1] or DEAD[m]
                        _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
                    else:
                        pass

                    # old value -> DEAD[h]
                    # new value -> REC[n]
                    io.write_key(key_fp, dead_h, key, file_id, offset, row_size, val_size, days=old_days)
                    io.write_key(key_fp, row, key, _type_id, _type_val, 0, _type_size, days=old_days|CHG_DAY_FLAG)

                    if _type_id == 0x10 and isinstance(val, JDbReader):
                        self._set_child(key, val)

                    # without change key table and file table
                    io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                    if cache_limit != 0:
                        self._update_cache(key, val, copy=True)
                    return True

                # (Exist + Value vs CHG + Value)
                data = _type_val
                new_val_size = len(data)
                if new_row_size >= new_val_size and val_size == new_val_size:
                    # (Exist + Value vs CHG + Value)
                    if not checked:
                        rd_data = b''
                        try:
                            val_fp, __i, __o = self.f_get_val_fp(fp_dict, file_id)
                            val_fp.seek(offset)
                            rd_size = min(MAX_BLOCK_SIZE, new_val_size)
                            n_block = new_val_size // rd_size
                            for ii in range(n_block):
                                _ix = ii * rd_size
                                _rd_data = val_fp.read(rd_size)
                                _wr_data = data[_ix:_ix+rd_size]
                                if _rd_data != _wr_data:
                                    if ii == 0 and io.zip_type_str == 'gz' and new_val_size >= 16:
                                        # [FIX] gzip random at 5th byte
                                        # len(gzip.compress(b''')) == 20 bytes
                                        _rd_data = bytearray(_rd_data)
                                        _rd_data[4] = data[4]
                                        if _rd_data != _wr_data:
                                            rd_data = b''
                                            break
                                    else:
                                        rd_data = b''
                                        break

                                rd_data += _rd_data

                            if rd_data:
                                rd_size = len(rd_data)
                                rd_data = (rd_data + val_fp.read(new_val_size-rd_size)) if new_val_size > rd_size else rd_data

                                # (Exist + Value == CHG + Value)
                                if rd_data == data:
                                    if cache_limit != 0:
                                        self._update_cache(key, val, copy=True)

                                    return False

                                # rd_data = None

                        except KeyError: # pragma: no cover
                            pass

                # (Exist + Value != CHG + Value) use dead/new row
                io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
                if sync_chg: # pragma: no cover
                    row = io.key_table[key]
                    if not io.n_records > row >= 0:
                        continue

                    _row_info = io.read_key(key_fp, row)
                    if _row_info != row_info:
                        continue

                if row_size >= new_val_size and (not can_revert or key in self.chg_keys):
                    # use same row
                    n_lines = io.n_lines
                    val_fp, __i, __o = self.f_get_val_fp(fp_dict, file_id)
                    val_fp.seek(offset)
                    _write_size = val_fp.write(data)
                    io.write_key(key_fp, row, key, file_id, offset, row_size, new_val_size, days=old_days|CHG_DAY_FLAG)
                    io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                    if cache_limit != 0:
                        self._update_cache(key, val, copy=True)
                    return True

                safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, new_val_size, flags=flags, max_wsize=max_wsize)
                n_lines = io.n_lines
                if dead_row < 0: # use new row
                    dead_row = n_lines
                    io.n_lines = n_lines = n_lines + 1  # MUST before call write_key(dead_row, ..)
                    data = io.pad(data, max_size=0)
                    new_row_size = len(data)
                    val_fp, new_file_id, new_offset  = self.f_get_val_fp(fp_dict, req_size=new_row_size)

                else: # use dead row
                    new_file_id = dead_file_id
                    new_offset = dead_offset
                    new_row_size = dead_row_size
                    val_fp, __i, __o = self.f_get_val_fp(fp_dict, new_file_id)

                val_fp.seek(new_offset)
                _write_size = val_fp.write(data)
                dead_h = safe_line
                if dead_row > dead_h:
                    # DEAD[h] -> DEAD[t+1] or DEAD[m]
                    _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
                else: # pragma: no cover
                    pass

                # old value -> DEAD[h]
                # new value -> REC[n]
                io.write_key(key_fp, dead_h, key, file_id, offset, row_size, val_size, days=old_days)
                io.write_key(key_fp, row, key, new_file_id, new_offset, new_row_size, new_val_size, days=old_days|CHG_DAY_FLAG)
                io.file_table[new_file_id] = max(io.file_table[new_file_id], new_offset + new_row_size)
                io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
                if cache_limit != 0:
                    self._update_cache(key, val, copy=True)
                return True

            # (Not Exist)
            io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
            if sync_chg: # pragma: no cover
                row = io.key_table[key]
                if row >= 0:
                    continue

            break

        # (Not Exist)
        _type_id, _type_val, _type_size = self._encode_row(key, val)
        if _type_id >= 0:
            # [Not Exist, ADD + Header] -> use dead/new row
            safe_line, dead_row, dead_file_id, dead_offset, dead_row_size = self._get_dead_row(key_fp, key, 0, flags=flags, max_wsize=max_wsize)
            safe_h = io.n_records
            n_lines = io.n_lines
            if dead_row < 0: # use new row
                dead_row = n_lines
                io.n_lines = n_lines = n_lines + 1  # MUST call write_key(dead_row, ..) first

            dead_h = safe_line
            if dead_row > dead_h:
                # DEAD[h] -> DEAD[t+1] or DEAD[m]
                _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
            else:
                pass

            if dead_h > safe_h:
                # SAFE[h] -> DEAD[h]
                _safe_bytes = io.copy_key(key_fp, safe_h, dead_h)
            else:
                pass

            # new key -> SAFE[h] (=REC[t+1]) | may trigger io.resize_keys() -> io.load_keys()
            io.write_key(key_fp, safe_h, key, _type_id, _type_val, 0, _type_size, days=days if days < 0 or days & NEW_DAY_MASK else days|CHG_DAY_FLAG)
            if _type_id == 0x10 and isinstance(val, JDbReader):
                self._set_child(key, val)

        else:
            # (Not Exist, ADD + Value) -> use dead/new row
            data = _type_val
            new_val_size = len(data)
            safe_line, dead_row, new_file_id, new_offset, new_row_size = self._get_dead_row(key_fp, key, new_val_size, flags=flags, max_wsize=max_wsize)
            safe_h = io.n_records
            n_lines = io.n_lines
            if dead_row < 0: # use new row
                dead_row = n_lines
                io.n_lines = n_lines = n_lines + 1  # MUST call write_key(dead_row, ..) first
                data = io.pad(data, max_size=0)
                new_row_size = len(data)
                val_fp, new_file_id, new_offset  = self.f_get_val_fp(fp_dict, req_size=new_row_size)

            else: # use dead row
                val_fp, __i, __o = self.f_get_val_fp(fp_dict, new_file_id)

            val_fp.seek(new_offset)
            _write_size = val_fp.write(data)

            dead_h = safe_line
            if dead_row > dead_h:
                # DEAD[h] -> DEAD[t+1] or DEAD[m]
                _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
            else:
                pass

            if dead_h > safe_h:
                # SAFE[h] -> DEAD[h]
                _safe_bytes = io.copy_key(key_fp, safe_h, dead_h)
            else:
                pass

            # new key -> SAFE[h] (= REC[t+1]) | may trigger io.resize_keys() -> io.load_keys()
            io.write_key(key_fp, safe_h, key, new_file_id, new_offset, new_row_size, new_val_size, days=days if days < 0 or days & NEW_DAY_MASK else days|CHG_DAY_FLAG)
            io.file_table[new_file_id] = max(io.file_table[new_file_id], new_offset + new_row_size)

        if cache_limit != 0:
            self._update_cache(key, val, copy=True)

        io.n_records += 1
        io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
        key_fp.flush() # before key_table
        io.key_table[key] = safe_h
        return True

    def f_delete(self, fp_dict:Dict[int,IO], key:str, read_value:bool=True, row:Optional[int]=None, flags:Optional[JFlag]=None):
        """ Low-level pipeline method: physically unlink a specified entity, compact index arrays, and manage transaction rollbacks.

        Args:
            fp_dict (Dict[int, IO]): Open file pointers maps repository.
            key (str): Unique entry identification lookup code label string.
            read_value (bool, optional): Unpack and return original data contents before discarding tracking pointers. Defaults to True.
            row (Optional[int], optional): Precise allocation row block offset index to bypass search indices. Defaults to None.
            flags (Optional[JFlag], optional): strategic behavioral modifiers flags. Defaults to None.

        Returns:
            Any: The unlinked python value payload object, or group workspace if targeted entity maps a nested sub-database.
        """
        key = str(key) if not isinstance(key, str) else key
        self._cache.pop(key, None)
        io = self.io
        if row is None or key:
            row = io.key_table[key]
            if row < 0:
                raise JKeyError(key)

        io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
        if sync_chg and key: # pragma: no cover
            row = io.key_table[key]
            if row < 0:
                # already deleted
                return None

        flags = self.flags if flags is None else JFlag(flags)
        can_revert = JFlag.REVERT in flags

        _key, file_id, offset, row_size, val_size, _ver, days = io.read_key(key_fp, row)
        if not key:
            key = _key

        elif _key != key: # pragma: no cover
            raise JKeyError(key)

        set_key_table = []
        val = None
        if row_size == 0:
            if file_id == 0x10:
                grp_jdb = io.groups.get(key, None)
                grp_jdb = grp_jdb if grp_jdb is not None else \
                    val if isinstance(val, JDbReader) else \
                    self._decode_row(file_id, offset, key, 0)

                io.groups.pop(key, None)
                val = grp_jdb

            elif read_value:
                val = self._decode_row(file_id, offset, key, val_size)

        elif read_value:
            val_fp, __i, __o  = self.f_get_val_fp(fp_dict, file_id)
            try:
                val = io.read_value(val_fp, offset, row_size, val_size)
            except ValueError as e: # pragma: no cover
                print(e)

        self.childs.pop(key, None)
        io.groups.pop(key, None)
        swap_id = io.swap_id
        n_lines = io.n_lines
        _safe_h = n_records = io.n_records
        dead_h = min(max(self.safe_line, n_records), n_lines)
        safe_t = dead_h - 1
        record_t = io.n_records = max(io.n_records - 1, 0) # must before write_key
        if row  < record_t:
            # it is not last record, swap it
            # REC[t] -> REC[r]
            io.key_table.pop(key, -1)
            rec_args = io.copy_key(key_fp, record_t, row, decode=True)
            set_key_table.append((rec_args[0], row))
            swap_id = (swap_id + 1) & 0X_7FF_FFFF_FFFF

        # row == record_t
        else: # pragma: no cover
            pass

        if safe_t == record_t:
            # del key -> REC[t] (=SAFE[h])
            pass

        # safe_t > record_t
        else:
            if not can_revert:
                safe_t = record_t

            elif key not in self.chg_keys:
                # del key -> REC[t] (=SAFE[h])
                safe_t = record_t

            else:
                # SAFE[t] -> REC[t]
                # del key -> SAFE[t]
                _safe_bytes = io.copy_key(key_fp, safe_t, record_t)

        # del key -> SAFE[t]
        io.write_key(key_fp, safe_t, key, file_id, offset, row_size, val_size, days=days)
        io.swap_id = swap_id
        io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
        io.remv_id = (io.remv_id + 1) & 0X_7FF_FFFF_FFFF
        key_fp.flush() # before key_table
        for _key,_row_id in set_key_table:
            io.key_table[_key] = _row_id
        io.key_table.pop(key, -1)
        return val

    def f_undelete(self, fp_dict:Dict[int,IO], key:str, row:Optional[int]=None, flags:Optional[JFlag]=None) -> Optional[Tuple[int,int,int,int,int]]:
        """ Low-level pipeline method: resurrect dropped or unlinked indices descriptors variables from dead logs sectors.

        Args:
            fp_dict (Dict[int, IO]): Persistent active handles arrays tables registers.
            key (str): Missing identifier text selector string to target and recover.
            row (Optional[int], optional): Precise hardware target slot alignment position index to bypass lookup cycles loops. Defaults to None.
            flags (Optional[JFlag], optional): strategic modifiers flags. Defaults to None.

        Returns:
            Optional[Tuple[int,int,int,int,int]]: Core allocation parameters metadata tuple summarizing recovered slot parameters if successful, None otherwise.
        """
        key = str(key) if not isinstance(key, str) else key
        if key == '':
            return None

        flags = self.flags if flags is None else flags
        can_revert = JFlag.REVERT in flags
        self._cache.pop(key, None)
        tmp_row = row
        io = self.io
        file_id = offset = row_size = val_size = days = 0
        while True:
            if key in io.key_table:
                return None

            io, fp_dict, key_fp = self.f_get_fp(fp_dict)
            io_read_key = io.read_key
            if row is None:
                for _row in range(io.n_records, io.n_lines):
                    _key, file_id, offset, row_size, val_size, _ver, days = io_read_key(key_fp, _row)
                    if _key == key:
                        row = _row
                        break

                if row is None:
                    return None
            else:
                _key, file_id, offset, row_size, val_size, _ver, days = io_read_key(key_fp, row)
                if _key != key:
                    return None

            io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
            if sync_chg: # pragma: no cover
                row = tmp_row
                continue

            break

        dead_row = row
        n_lines = io.n_lines
        safe_h = n_records = io.n_records
        dead_h = safe_line = min(max(self.safe_line, n_records), n_lines) if can_revert else n_records
        if dead_row >= dead_h:
            if can_revert:
                self.chg_keys.add(key)
                self.safe_line = safe_line = safe_line + 1
            else:
                self.safe_line = safe_line = n_records

            if dead_row > dead_h:
                # DEAD[h] -> DEAD[m]
                _dead_bytes = io.copy_key(key_fp, dead_h, dead_row)
            else: # pragma: no cover
                pass

            if dead_h > safe_h:
                # SAFE[h] -> DEAD[h]
                _safe_bytes = io.copy_key(key_fp, safe_h, dead_h)
            else: # pragma: no cover
                pass

        # dead_row < dead_h
        else:
            if key in self.chg_keys:
                self.chg_keys.remove(key)

            if dead_row > safe_h: # pragma: no cover
                # SAFE[h] -> DEAD[m]
                _safe_bytes = io.copy_key(key_fp, safe_h, dead_row)
            else: # pragma: no cover
                pass

        self._cache.pop(key, None)

        # undelete key -> SAFE[h] (=REC[t+1]) | may trigger io.resize_keys() -> io.load_keys()
        io.write_key(key_fp, safe_h, key, file_id, offset, row_size, val_size, days=days)

        io.n_records += 1
        io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
        key_fp.flush() # before key_table
        io.key_table[key] = safe_h
        return safe_h, file_id, offset, row_size, val_size

    def f_unwrite(self, fp_dict:Dict[int,IO], key:str, row:Optional[int]=None, flags:Optional[JFlag]=None) -> Optional[Tuple[int,int,int,int,int]]:
        """ Low-level pipeline method: roll back dynamic record modifications shifting indices properties maps back to legacy content points maps.

        Args:
            fp_dict (Dict[int, IO]): Persistent active system registers stream descriptor collections.
            key (str): Unique dictionary descriptive name string token format selector query fields.
            row (Optional[int], optional): Target layout position index bounding search rows loops. Defaults to None.
            flags (Optional[JFlag], optional): strategic modifiers behavioral flags. Defaults to None.

        Returns:
            Optional[Tuple[int,int,int,int,int]]: Execution parameters logging adjusted item metrics parameters integers if successful, None otherwise.
        """
        key = str(key) if not isinstance(key, str) else key
        if key == '':
            return None

        self._cache.pop(key, None)
        flags = self.flags if flags is None else JFlag(flags)
        _can_revert = JFlag.REVERT in flags
        file_id = offset = row_size = val_size = days = 0
        tmp_row = row
        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        io_read_key = io.read_key
        key_table = io.key_table
        while True:
            if key not in key_table:
                return None

            if row is None:
                for _row in range(io.n_records, io.n_lines):
                    _key, file_id, offset, row_size, val_size, _ver, days =  io_read_key(key_fp, _row)
                    if _key == key:
                        row = _row
                        break

                if row is None:
                    return None
            else:
                if row < io.n_records:
                    return None

                _key, file_id, offset, row_size, val_size, _ver, days =  io_read_key(key_fp, row)
                if _key != key:
                    return None

            io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
            if sync_chg: # pragma: no cover
                row = tmp_row
                continue

            break

        dead_row = row
        # REC[n]
        old_row = key_table[key]
        if not io.n_records > old_row >= 0:
            return None

        _key, old_file_id, old_offset, old_row_size, old_val_size, _old_ver, old_days = io_read_key(key_fp, old_row)
        if _key != key:
            return None

        io_write_key = io.write_key
        # old value: REC[n]-> DEAD[n]
        # new value -> REC[n]
        io_write_key(key_fp, dead_row, key, old_file_id, old_offset, old_row_size, old_val_size, days=old_days)
        io_write_key(key_fp, old_row, key, file_id, offset, row_size, val_size, days=days)
        io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
        if key in self.chg_keys:
            self.chg_keys.remove(key)

        return old_row, file_id, offset, row_size, val_size

    def f_rename(self, fp_dict:Dict[int,IO], key:str, new_key:str) -> bool:
        """ Low-level pipeline method: alter unique index reference tokens text strings mapping keys metadata blocks layout configurations.

        Args:
            fp_dict (Dict[int, IO]): Active file handler matrix registration array mapping pools handles.
            key (str): Existing unique query selector name token label string format context fields fields.
            new_key (str): Newly requested target character string identification indicator code text.

        Returns:
            bool: True if identity name properties switch successfully inside tracking registers, False otherwise.

        Raises:
            KeyError: If destination identifier string token collides against pre-allocated records fields data layers.
        """
        key = str(key) if not isinstance(key, str) else key
        new_key = str(new_key) if not isinstance(new_key, str) else new_key

        if key == new_key:
            return False

        self._cache.pop(key, None)
        io = self.io
        while True:
            if new_key in io.key_table: # pragma: no cover
                raise JKeyError(f'{new_key} already exist')

            row = io.key_table[key]
            if row < 0: # pragma: no cover
                raise JKeyError(f'{key} not exist')

            io, fp_dict, key_fp, sync_chg = self.f_get_write_fp(fp_dict)
            if not sync_chg:
                break


        _key, file_id, offset, row_size, val_size, _ver, days = io.read_key(key_fp, row)
        if io.write_key(key_fp, row, new_key, file_id, offset, row_size, val_size, days=days) > 0:
            io.sync_id = (io.sync_id + 1) & 0X_7FF_FFFF_FFFF
            io.swap_id = (io.swap_id + 1) & 0X_7FF_FFFF_FFFF
            key_fp.flush() # before key_table
            io.key_table.pop(key, 0)
            io.key_table[new_key] = row
            return True

        return False

    def f_get_write_fp(self, fp_dict:Dict[int,IO]) -> Tuple[JIo,Dict[int,IO],IO,bool]:
        """ Acquire and configure exclusive writing streams access permissions channels context maps matrices metrics.

        Args:
            fp_dict (Dict[int, IO]): Active file handler dictionary tracking metrics variables configuration parameters.

        Returns:
            Tuple[JIo, Dict[int, IO], IO, bool]: Consolidated processing context payload group returning core matrix, file map registers, main descriptor pointer, and timeline shift synchronization flag state.

        Raises:
            RuntimeError: If multi-threaded file locks context cannot initialize isolation guards blocks parameters thresholds numbers.
        """
        sync_id = self.io.sync_id
        file_lock = self.file_lock
        if file_lock.is_locked:
            if file_lock.mode == 'w':
                io, fp_dict, key_fp = self.f_get_fp(fp_dict)
                return io, fp_dict, key_fp, sync_id != io.sync_id

        ident = file_lock.acquire(read_only=False, switch=True)
        if ident is None: # pragma: no cover
            raise RuntimeError

        fp_dict = self.fp_table[ident] if fp_dict is None else fp_dict
        # Must close all files due to OS Cache issue
        for fp in fp_dict.values():
            if fp is None: continue
            fp.close()

        fp_dict.clear()
        io = self.io
        io.update_days()
        is_latest = self.files_obj.KEY_size() == io.file_size
        try:
            key_fp = fp_dict[-1] = self.files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)
            data_type = io._data_type
            io.read_header(key_fp)
            if not is_latest or not io.is_updated():
                io.load_keys(key_fp, force=data_type==0)
                self.fsize = io.file_size
                self._cache.clear()

        except FileNotFoundError:
            if key_fp is not None:
                key_fp.close()

            io, key_fp = self._init_KEY()
            fp_dict[-1] = key_fp

        self.safe_line = io.n_records
        return io, fp_dict, key_fp, sync_id != io.sync_id

    def _set_child(self, name:str, child:JDbReader) -> None:
        """Add child JDb to JDb

        Args:
            name (str): child name.
            child (JDbReader): JDbReader object

        """
        jio = self.io
        if name in jio.groups:
            jio.groups[name] = child
            self.childs.pop(name, None)

        elif name not in self.childs and self.files_obj.is_group(child.files_obj, name): # pragma: no cover
            jio.groups[name] = child
        else:
            self.childs[name] = child

    @staticmethod
    def z_upgrade_API(KEY_path:Union[str,JDb]) -> JDb: # pragma: no cover
        """
        Upgrade an older version of the database to the latest API structural format.

        This method reads the existing database schema, resizes the index structure if necessary,
        migrates all tracking properties and physical indices to match the specifications of `API_LATEST`,
        and overwrites the legacy header. It ensures backward compatibility for older `.jdb` files by 
        re-encoding the storage pipelines.

        Args:
            KEY_path (Union[str, JDb]): The file path string to the legacy database, or an already 
                initialized JDb instance that requires upgrading.

        Returns:
            JDb: The fully upgraded database controller instance running on the newest API format.

        Raises:
            TypeError: If the provided `KEY_path` cannot be resolved into a valid JDb instance, 
                or if the current API version is missing/invalid.

        Example:
            >>> from omni_json_db import JDb
            >>> # Upgrade a legacy database file to the latest API
            >>> upgraded_db = JDb.z_upgrade_API('db/legacy_data.jdb')
            >>> print(upgraded_db.io.api_ver)
        """
        if isinstance(KEY_path, JDb):
            jdb = KEY_path
        else:
            jdb = JDb(KEY_path)

        if not isinstance(jdb, JDb):
            raise TypeError

        if not isinstance(jdb.io.api_ver, int):
            raise TypeError

        KEY_path = jdb.files_obj.get_path()
        if jdb.io.api_ver >= API_LATEST:
            print(f'[JDb|v{jdb.io.api_ver}] {KEY_path} uses the latest API')
            return jdb

        print(Style(f'[JDb|v{jdb.io.api_ver}] Start to upgrade {KEY_path}, DON\'T STOP until finish !!!', yellow=1))
        with jdb.open(read_only=False) as fp:
            src_io, fp, key_fp = jdb.f_get_fp(fp)
            zip_type    = src_io.zip_type_str
            data_type   = src_io.data_type_str
            index_size  = old_index_size = src_io.index_size
            n_records   = src_io.n_records
            n_lines     = src_io.n_lines
            extra_size  = 8 if jdb.io.api_ver > 0 else 24

            src_io.seek(key_fp, 0)
            for row_id in range(n_lines):
                row = key_fp.read(old_index_size).rstrip(b'\n \x00')
                index_size = max(index_size, len(row)+extra_size)

            if index_size > src_io.index_size:
                src_io.resize_keys(key_fp, index_size)

            src_io      = jdb.io
            index_size  = src_io.index_size
            print(f'[JDb|v{src_io.api_ver}|{data_type}({zip_type})|i{index_size}|#{n_records}/{n_lines}] upgrading {KEY_path} to v{API_LATEST}')

            if data_type == 'L+J':
                data_type = 'J+J'

            dst_io = JIo(
                files_obj=src_io.files_obj.copy(), # due to JNetFiles
                data_type=data_type,
                zip_type=zip_type,
                key_limit=src_io._key_limit,
                api_ver=src_io.api_ver,
                index_size=index_size,
                sync_id=0,
                min_value_size=src_io.min_value_size,
                max_file_size=src_io.max_file_size,
                reserved_rate=src_io.reserved_rate)

            dst_io.change_APIs(API_LATEST, dst_io._data_type, dst_io._zip_type) # use latest API
            dst_io.sync_id      = (src_io.sync_id + 1) & 0X_7FF_FFFF_FFFF
            dst_io.n_records    = n_records
            dst_io.n_lines      = n_lines
            dst_io.swap_id      = src_io.swap_id
            dst_io.remv_id      = src_io.remv_id

            src_read_key = src_io.read_key
            dst_write_key = dst_io.write_key
            for row_id in range(n_lines):
                row_data = src_read_key(key_fp, row_id)
                dst_write_key(key_fp, row_id, *row_data)

            dst_io.write_header(key_fp)
            dst_io.file_size = key_fp.seek(0,2) + 1
            key_fp.write(b'\n')

            dst_io.key_table = src_io.key_table
            dst_io.file_table = src_io.file_table
            jdb.io = dst_io

        print(Style(f'[JDb|v{jdb.io.api_ver}|{jdb.io.data_type_str}({jdb.io.zip_type_str})|i{jdb.io.index_size}|#{jdb.io.n_records}/{jdb.io.n_lines}] {KEY_path} is finished to upgrade !!!', green=1))
        return jdb

    @staticmethod
    def z_upgrade_KEY_day(KEY_path:Union[str,JDbReader]) -> JDb: # pragma: no cover
        """
        Upgrade and rectify the legacy timeline tracking format (days) inside the database index.

        This migration method patches older date formats (specifically targeting pre-2000 epoch offsets)
        within the index registries. It sequentially scans all allocated rows, updates the timestamp 
        metadata values directly via bitwise masks, and rewrites the file header safely.

        Args:
            KEY_path (Union[str, JDbReader]): The absolute file path to the database, or an active 
                JDb/JDbReader instance wrapper.

        Returns:
            JDb: The database controller instance with fully rectified timeline index matrices.

        Raises:
            TypeError: If the input target cannot be instantiated or validated as a proper JDb environment.

        Example:
            >>> from omni_json_db import JDb
            >>> # Fix timeline metadata constraints for an older database
            >>> fixed_db = JDb.z_upgrade_KEY_day('db/old_timestamps.jdb')
        """
        if isinstance(KEY_path, JDbReader):
            jdb = KEY_path
        else:
            jdb = JDb(KEY_path)

        if not isinstance(jdb, JDb):
            raise TypeError

        KEY_path = jdb.files_obj.get_path()
        if not path_exists(KEY_path):
            return jdb

        stats = os_stat(KEY_path)
        if stats.st_mtime > 1769506826:
            print(f'[JDb|v{jdb.io.api_ver}] {KEY_path} uses the latest API')
            return jdb

        year_2000  = 730119
        print(Style(f'[JDb|v{jdb.io.api_ver}] Start to upgrade {KEY_path}, DON\'T STOP until finish !!!', yellow=1))
        with jdb.open(read_only=False) as fp:
            io, fp, key_fp = jdb.f_get_fp(fp)
            read_key = io.read_key
            write_key = io.write_key
            for row_id in range(io.n_lines):
                key, file_id, offset, row_size, val_size, ver, days = read_key(key_fp, row_id)
                _old = days & OLD_DAY_MASK
                if _old < year_2000:
                    _days = (days & NEW_DAY_MASK) | ((_old + year_2000) & OLD_DAY_MASK)
                    write_key(key_fp, row_id, key, file_id, offset, row_size, val_size, ver, _days)

                if (row_id+1)%1000 == 0:
                    print('.', end='', flush=True)

            io.write_header(key_fp)
            io.file_size = key_fp.seek(0,2) + 1
            key_fp.write(b'\n')

        print(Style(f'[JDb|v{jdb.io.api_ver}|{jdb.io.data_type_str}({jdb.io.zip_type_str})|i{jdb.io.index_size}|#{jdb.io.n_records}/{jdb.io.n_lines}] {KEY_path} is finished to upgrade !!!', green=1))
        return jdb

    @staticmethod
    def z_dumps(data:Union(Any,JDbReader), ret_type:Optional[str]=None) -> bytes:
        """
        convert any data into Json/Marshal/Pickle/Msgpack/YAML format
        
        Args:
            data (Any): target Python data
                
                - support str/bytes/int/float/bool/None/dict/list/set/tuple/JDb
            
            ret_type (str, optional): return format                
                
                - "J" = JSON format (default)
                - "M" = Marshal format
                - "P" = Pickle format
                - "S" = Msgpack format
                - "Y" = YAML format

        Returns:
            bytes: converted data 
        
        Raises:
            ValueError: invalid ret_type

        Example:
            >>> dumps([1,2], 'J')
            >>> dumps([1,2], 'M') 
            >>> dumps([1,2], 'P') 
            >>> dumps([1,2], 'S') 
            >>> dumps([1,2], 'Y')
        """
        if isinstance(data, JDbReader):
            ret_type = data.data_type[-1] if ret_type is None else ret_type
            data = dict(data)

        if ret_type is None: # pragma: no cover
            ret_type = 'J'

        ret_type_u = ret_type.upper()
        if ret_type_u not in 'JMPSY':
            raise ValueError('date_type must be (J)son/(M)arshal/(P)ickle/M(S)gpack/(Y)aml')

        dumps = g_VAL_J.dumps if ret_type_u == 'J' else \
            g_VAL_M.dumps if ret_type_u == 'M' else \
            g_VAL_P.dumps if ret_type_u == 'P' else \
            g_VAL_S.dumps if ret_type_u == 'S' else \
            g_VAL_Y.dumps

        return dumps(data)

    @staticmethod
    def z_loads(data:bytes, ret_type:str='J') -> Any:
        """
        convert Json/Marshal/Pickle/Msgpack/YAML bytes into Python data
        
        Args:
            data (Any): Json/Msgpack/Marshal/Pickle bytes                
            ret_type (str, optional): return format

                - "J" = JSON format
                - "M" = Marshal format
                - "P" = Pickle format
                - "S" = Msgpack format
                - "Y" = YAML format

        Returns:
            bytes: Python data
        
        Raises:
            ValueError: invalid ret_type

        Example:
            >>> loads(dumps([1,2], 'J'), 'J') # Output: [1,2]
            >>> loads(dumps([1,2], 'M'), 'M') # Output: [1,2] 
            >>> loads(dumps([1,2], 'P'), 'P') # Output: [1,2]
            >>> loads(dumps([1,2], 'S'), 'S') # Output: [1,2]
            >>> loads(dumps([1,2], 'Y'), 'J') # Output: [1,2]
        """
        ret_type_u = ret_type.upper()
        if ret_type_u not in 'JMPSY':
            raise ValueError('date_type must be (J)son/(M)arshal/(P)ickle/M(S)gpack/(Y)aml')

        loads = g_VAL_J.loads if ret_type_u == 'J' else \
            g_VAL_M.loads if ret_type_u == 'M' else \
            g_VAL_P.loads if ret_type_u == 'P' else \
            g_VAL_S.loads if ret_type_u == 'S' else \
            g_VAL_Y.loads

        return loads(data)

#
