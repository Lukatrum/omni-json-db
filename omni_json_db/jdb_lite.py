# pylint: disable=too-many-lines
from __future__ import annotations
from contextlib import contextmanager
from datetime import date as dt_date, datetime, timedelta
from re import compile as re_compile, findall as re_findall, match as re_match, Pattern, I as re_I, S as re_S
from os.path import exists as path_exists # basename, dirname, join as path_join
from threading import RLock, get_ident
from struct import Struct
from enum import IntFlag
from typing import Any, Union, Optional, Tuple, Set, Dict, Callable, Generator, IO
# from os import makedirs, stat as os_stat, getcwd
# from time import time
#-----------------------------------------------------------------------------
from .jdb_io import JIo, json_dumps, KEY_FILE_BUF_SIZE, VAL_FILE_BUF_SIZE # THE_1ST_DATE
from .jdb_file import JFilesBase, JMemFiles, JDiskFiles
from .jdb_net import JNetFiles
from .utils import FileLock, Style
# from .utils import debug_break
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
# from copy import deepcopy
#  __hash__ if type is immutable
def deepcopy(src):
    if src.__hash__:
        return src

    if isinstance(src, dict):
        return {key:deepcopy(val) for key, val in src.items()}

    if isinstance(src, set):
        return src.copy()

    if isinstance(src, JDbReader):
        return src

    return [deepcopy(val) for val in src]

_Float64_pack = Struct("<d").pack    # sizeof() == 8 thread-safe  | <d = little-ending
_Float64_unpack = Struct("<d").unpack
_Int64_pack = Struct("q").pack   # sizeof() == 8 thread-safe
_Int64_unpack = Struct("q").unpack
_UInt64_pack = Struct("Q").pack   # sizeof() == 8 thread-safe
_UInt64_unpack = Struct("Q").unpack
_UInt64_x2_pack = Struct("QQ").pack # thread-safe
_UInt64_x2_unpack = Struct("QQ").unpack

JSON_RE_sub = re_compile(r'[",{}\[\]]', flags=re_I|re_S).sub
SET_RE_finditer = re_compile(r'(?<=\")([^\"\n]{1,32})(?=\")', flags=re_I|re_S).finditer

SEP_SYM = ':::' # ignore to use re symbols (+-*?.{}()[]^$|\)
SEP_LEN = len(SEP_SYM)

FIND_OPS = {'AND', 'NOT', 'OR', 'ANY',
            'FUNC', 'RE', 'RE2',
            'HAS', 'IN', 'NE', 'EQ',
            'GE', 'GT', 'LE', 'LT'}

class JFlag(IntFlag):
    REVERT  = 0x01  # [r]allow to revert after write/delete operation
    SPLIT   = 0x02  # [s]allow to split large row into two

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            _value = 0
            for ch in value.lower():
                if ch == 'r':
                    _value |= JFlag.REVERT
                elif ch == 's':
                    _value |= JFlag.SPLIT

            value = _value

        return super()._missing_(value)

    def __str__(self):
        ret = ''
        for flag in JFlag:
            if flag in self:
                ret += flag.name[0]
            else:
                ret += '_'

        return ret

def _match_rules(key:str, val:Any, rules:Any, level:int=0, ANY:bool=False) -> bool:
    if ANY and hasattr(val, '__iter__'): # pragma: no cover
        if isinstance(val, (list, set, frozenset, tuple)):
            if any(_match_rules(key, vv, rules, level=level+1, ANY=True) for vv in val):
                return True

        elif isinstance(val, dict):
            if any(_match_rules(key, vv, rules, level=level+1, ANY=True) for vv in val.values()):
                return True

    if not isinstance(rules, dict): # pragma: no cover
        if isinstance(rules, str):
            rules = {'$re': rules}
        elif isinstance(rules, int):
            rules = {'$eq' : rules}
        elif isinstance(rules, float):
            rules = {'$eq' : rules}
        elif isinstance(rules, bool):
            rules = {'$eq' : rules}
        elif isinstance(rules, bytes) and isinstance(val, bytes):
            rules = {'$eq' : rules}
        elif isinstance(rules, (list, set, tuple, frozenset)):
            rules = {'$in' : rules}
        elif callable(rules):
            rules = {'$func' : rules}

    for cmd,rule in rules.items():
        if cmd == '$val':
            if not _match_rules(key, val, rule, level=level+1):
                return False

        elif cmd[0] == '$':
            if cmd == '$gt':
                if not val.__gt__ or not rule.__gt__ or not val > rule:
                    return False

            elif cmd == '$ge':
                if not val.__ge__ or not rule.__ge__ or not val >= rule:
                    return False

            elif cmd == '$lt':
                if not val.__lt__ or not rule.__lt__ or not val < rule:
                    return False

            elif cmd == '$le':
                if not val.__le__ or not rule.__le__ or not val <= rule:
                    return False

            elif cmd == '$eq':
                if not val.__eq__ or not rule.__eq__ or not val == rule:
                    return False

            elif cmd == '$ne':
                if not val.__ne__ or not rule.__ne__ or not val != rule:
                    return False

            elif cmd == '$in':
                if not hasattr(rule, '__contains__'):
                    return False

                try:
                    if val.__hash__ and not isinstance(val, tuple):
                        if not val in rule:
                            return False

                    elif val.__iter__:
                        for kk in val:
                            if kk not in rule:
                                return False

                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$has':
                if hasattr(val, '__contains__') and not isinstance(val, (str, bytes, bytearray)):
                    if rule not in val:
                        return False

                    continue

                try:
                    if isinstance(val, str):
                        val_s = val

                    elif isinstance(val, (bytes, bytearray)):
                        if isinstance(rule, bytes):
                            val_s = val
                        else:
                            val_s = val.decode('utf8')
                    else:
                        val_s = json_dumps(val)
                        if isinstance(val_s, bytes):
                            val_s = val_s.decode('utf8')
                except:
                    return False

                if isinstance(val_s, bytes) and isinstance(rule, bytes):
                    if val_s.find(rule) < 0:
                        return False

                    continue

                try:
                    val = {kk.group() for kk in SET_RE_finditer(val_s)}
                    if rule.__hash__ and not isinstance(rule, tuple):
                        if rule not in val:
                            return False

                    elif rule.__iter__:
                        for kk in rule:
                            if kk not in val:
                                return False

                except TypeError: # pragma: no cover
                    return False

            elif cmd in {'$re', '$re2'}:
                _rules = []
                if isinstance(rule, Pattern):
                    _rules.append(rule)

                elif isinstance(rule, str):
                    _rules.append(re_compile(rule))

                elif isinstance(rule, (dict, list, tuple, set, frozenset)): # pragma: no cover
                    for _rule in rule:
                        if isinstance(_rule, Pattern):
                            _rules.append(_rule)
                        elif isinstance(_rule, str):
                            _rules.append(re_compile(_rule))

                if not _rules:
                    return False

                if not isinstance(val, str):
                    try:
                        if isinstance(val, (bytes, bytearray)):
                            val_s = val.decode('utf8')
                        else:
                            val_s = json_dumps(val)
                            if isinstance(val_s, bytes):
                                val_s = val_s.decode('utf8')

                    except: # pragma: no cover
                        return False

                else: # pragma: no cover
                    val_s = val

                if cmd[-1] != 'e':
                    val_s = JSON_RE_sub('', val_s)

                for _rule in _rules:
                    if not _rule.search(val_s):
                        return False

            elif cmd == '$func':
                if not callable(rule): # pragma: no cover
                    return False

                arg_cnt = rule.__code__.co_argcount
                if arg_cnt == 2:
                    if not rule(key, val):
                        return False
                elif arg_cnt == 1:
                    if not rule(val):
                        return False
                else:
                    return False

            # elif cmd == '$len':
            #     if not hasattr(rule, '__iter__'):
            #         return False

            #     _len = len(val)
            #     if isinstance(rule, range):
            #         if _len not in rule:
            #             return False

            #     elif isinstance(rule, int):
            #         if _len != rule:
            #             return False

            #     elif isinstance(rule, float):
            #         if _len != int(rule):
            #             return False

            #     elif isinstance(rule, (list, set, frozenset, tuple)):
            #         if _len not in rule:
            #             return False

            #     else:
            #         return False

            elif cmd == '$not':
                if _match_rules(key, val, rule, level=level+1):
                    return False

            elif cmd == '$or':
                if not isinstance(rule, dict): # pragma: no cover
                    return False

                is_matched = False
                for _cmd,_rule in rule.items():
                    _cmd = _cmd.rstrip('_')
                    if _match_rules(key, val, {_cmd : _rule}, level=level+1):
                        is_matched = True
                        break

                if not is_matched:
                    return False

            elif cmd == '$and':
                if not isinstance(rule, dict): # pragma: no cover
                    return False

                is_matched = True
                for _cmd,_rule in rule.items():
                    _cmd = _cmd.rstrip('_')
                    if not _match_rules(key, val, {_cmd : _rule}, level=level+1):
                        is_matched = False
                        break

                if not is_matched:
                    return False

            elif cmd[1:].isdigit():
                if not isinstance(val, (list, tuple)): # pragma: no cover
                    return False

                try:
                    if not _match_rules(key, val[int(cmd[1:])], rule, level=level+1):
                        return False

                except IndexError: # pragma: no cover
                    return False

            else:
                return False

        elif hasattr(val, '__iter__') and cmd in val:
            if not isinstance(val, dict): # pragma: no cover
                return False

            if not _match_rules(key, val[cmd], rule, level=level+1):
                return False

        else:
            return False

    return True

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDbKey:
    __slots__ = {'jdb'}

    def __init__(self, jdb:JDbReader):
        self.jdb = jdb

    def __repr__(self) -> str:
        return f'<{type(self).__name__} at {hex(id(self))}>'

    def __getitem__(self, key:Any) -> Union[dict,tuple,None]:
        '''
            [1] key
                type = str | bool | bytes
                    > val = jdb.keys['name']

                type = slice() | date() | datetime() | float | int
                    > val:dict = jdb.keys[date(2020,1,1)::r'key[0-9]'] # get date from 2020-1-1 to now key and match r'key[0-9]'
                    > val:dict = jdb.keys[:100:r'key[0-9]'] # get 1-100th row keys and match r'key[0-9]'
                    > val:dict = jdb.keys[date.today()]     # get today modified/new keys
                    > val:dict = jdb.keys[datetime.now()]   # get today new keys
                    > val:dict = jdb.keys[1:10:2]   # get 2nd - 9th and step=2 key info
                    > val:dict = jdb.keys[-10.:]    # get key info and match sync_id
                    > val:dict = jdb.keys[:]        # get all key info
                    > val:dict = jdb.keys[0]        # get 1st key info
                    > val:dict = jdb.keys[-1]       # get last key info
                    > val:dict = jdb.keys[0]        # get 1st key info
                    > val:dict = jdb.keys[-1]       # get last key info
                    > val:dict = jdb.keys[-1.]      # get all key info which sync_id is matched

                type = re.Pattern
                    > val:dict = jdb.keys[re.compile(r'key[0-9]')]

                type = function(k,v)
                    > val:dict = jdb.keys[lambda k,v: k.startswith('key')]
                    > val:dict = jdb.keys[lambda k,v: v == 10]

                type = function(k)
                    > val:dict = jdb.keys[lambda k: k[0] == 'k']

                type = tuple() | set() | list() | dict()
                    > val:dict = jdb.keys[1, 2, 3, 'a']
                    > val:dict = jdb.keys[(1, 2, 3, 'a')]
                    > val:dict = jdb.keys[{1, 2, 3, 'a'}]
                    > val:dict = jdb.keys[[1, 2, 3, 'a']]
                    > val:dict = jdb.keys[{1:0, 2:1, 3:2, 'a':3}]
        '''
        key_type = type(key)
        if key_type is str:
            if key.find(SEP_SYM) >= 0 and key not in self.jdb:
                # pylint: disable=unnecessary-comprehension
                return {k:v for k,v in self.item_iter(key)}

        elif key_type in {bytes, bytearray}: # pragma: no cover
            pass

        elif key_type in {int, float, slice, dt_date, datetime, Pattern} \
                or callable(key) \
                or hasattr(key, '__iter__'):
            # pylint: disable=unnecessary-comprehension
            return {k:v for k,v in self.item_iter(key)}

        jdb = self.jdb
        with jdb.open(read_only=True) as fp:
            io, fp, key_fp = jdb.f_get_fp(fp)
            if key_type is not str: # pragma: no cover
                key = str(key)

            row_id = io.key_table[key]
            if io.n_records > row_id >= 0:
                _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                old_date, new_date  = io.z_conv_date(days)
                return (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

        return None

    def __setitem__(self, key:Any, val:Any) -> None:
        raise AttributeError('read only')

    def __delitem__(self, key:Any):
        raise AttributeError('read only')

    def __len__(self) -> int:
        return len(self.jdb)

    def __call__(self, keys:Optional[Any]=None, vals:Optional[Any]=None, date:Optional[Any]=None, limit:int=0, with_value:bool=False, copy:bool=False, **kwargs) -> Generator[Union[str,Tuple[str,tuple]]]:
        jdb = self.jdb
        if keys or vals or kwargs:
            for key, _val in jdb.find_iter(keys=keys, vals=vals, date=date, limit=limit, with_value=with_value, **kwargs):
                yield key

        else:
            with jdb.open(read_only=True):
                io = jdb.io
                key_table = io.key_table.copy() if copy else io.key_table
                yield from key_table

    def __iter__(self) -> Generator[str]:
        jdb = self.jdb
        with jdb.open(read_only=True):
            yield from jdb.io.key_table

    def item_iter(self, key:Optional[Any]=None) -> Generator[str,tuple]:
        '''
            [1] key
                type = str | bool | bytes
                    > val = jdb.keys['name']
                    > val:dict = jdb.key['child:::name']
                    > val:dict = jdb.key[':::name']

                type = int
                    > val = jdb.keys[1]             # get 2nd line row key info
                    > val = jdb.keys[-1]            # get last line row key info

                type = float
                    > val:dict = jdb.keys[-1.]      # get all key info which sync_id is matched

                type = slice() | date() | datetime()
                    > val:dict = jdb.keys[date(2020,1,1)::r'key[0-9]'] # get date from 2020-1-1 to now key and match r'key[0-9]'
                    > val:dict = jdb.keys[:100:r'key[0-9]'] # get 1-100th row keys and match r'key[0-9]'
                    > val:dict = jdb.keys[date.today()]     # get today modified/new keys
                    > val:dict = jdb.keys[datetime.now()]   # get today new keys
                    > val:dict = jdb.keys[1:10:2]   # get 2nd - 9th and step=2 key info
                    > val:dict = jdb.keys[-10.:]    # get key info and match sync_id
                    > val:dict = jdb.keys[:]        # get all key info

                type = re.Pattern
                    > val:dict = jdb.keys[re.compile(r'key[0-9]')]

                type = function(k,v)
                    > val:dict = jdb.keys[lambda k,v: k.startswith('key')]
                    > val:dict = jdb.keys[lambda k,v: v == 10]

                type = function(k)
                    > val:dict = jdb.keys[lambda k: k[0] == 'k']

                type = tuple() | set() | list() | dict()
                    > val:dict = jdb.keys[1, 2, 3, 'a']
                    > val:dict = jdb.keys[(1, 2, 3, 'a')]
                    > val:dict = jdb.keys[{1, 2, 3, 'a'}]
                    > val:dict = jdb.keys[[1, 2, 3, 'a']]
                    > val:dict = jdb.keys[{1:0, 2:1, 3:2, 'a':3}]

                type = None == slice(0,None)
                    > get all items

            Return: Tuple[str,tuple]
                0: key:str 
                1: tuple:
                    0: row_id:int
                    1: file_id:int
                    2: offset:int
                    3: row_size:int
                    4: val_size:int
                    5: version:int
                    6: days:int - combine modified date + created date
                    7: modified date: str (eg. '2000-01-01')
                    8: created date: str  (eg. '2000-01-01')
        '''
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
            if key is None:
                key = slice(0,None)

        jdb = self.jdb

        with jdb.open(read_only=True) as fp:
            io, fp, key_fp = jdb.f_get_fp(fp)
            if isinstance(key, str):
                idx = key.find(SEP_SYM)
                if idx < 0:
                    row_id = io.key_table[key]
                    if io.n_records > row_id >= 0:
                        _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                        old_date, new_date  = io.z_conv_date(days)
                        yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                    return

                childs = set(io.groups).union(jdb.childs)
                if not childs:
                    return

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

            if isinstance(key, int):
                n_records = io.n_records
                row_id = key
                if row_id < 0:
                    row_id = n_records + row_id

                if n_records > row_id >= 0:
                    _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                    old_date, new_date = io.z_conv_date(days)
                    yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            if isinstance(key, float):
                sync_id = int(key)
                if sync_id < 0:
                    sync_id = io.sync_id + sync_id

                if sync_id >= io.sync_id or sync_id < 0:
                    return

                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                n_records = io.n_records
                for row_id in range(io.n_records):
                    _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                    if ver != sync_id:
                        continue

                    old_date, new_date = io_conv_date(days)
                    yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            if isinstance(key, (slice, dt_date, datetime)):
                n_records = io.n_records
                n_lines = io.n_lines
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                new_slice, max_ver, min_ver, max_date, min_date, filter_re, chk_new_date = jdb.f_slice(fp, key)
                for row_id in range(new_slice.start, new_slice.stop, new_slice.step):
                    if not n_lines > row_id >= 0: continue

                    _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                    if not max_ver > ver >= min_ver or filter_re and not filter_re.search(_key):
                        continue

                    old_date, new_date = io_conv_date(days)
                    if chk_new_date:
                        if min_date and new_date < min_date or max_date and new_date >= max_date:
                            continue
                    else:
                        if min_date and old_date < min_date or max_date and old_date >= max_date:
                            continue

                    if row_id >= n_records:
                        _key = f'|{_key}|~~{ver}~\t\t'

                    yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            if k_arg_cnt > 0:
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                if k_arg_cnt == 2:
                    for row_id in range(io.n_records):
                        _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                        old_date, new_date = io_conv_date(days)
                        val = (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))
                        if not is_matched(_key, val):
                            continue

                        yield _key, val

                elif k_arg_cnt == 1:
                    for _key,row_id in io.key_table.items():
                        if not io.n_records > row_id >= 0 or not is_matched(_key):
                            continue

                        _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                        old_date, new_date = io_conv_date(days)
                        yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            if isinstance(key, (bytes, bytearray)): # pragma: no cover
                pass

            elif hasattr(key, '__iter__'):
                done = set()
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                key_table = io.key_table
                has_childs = len(io.groups) > 0 or len(jdb.childs) > 0
                for _key in key:
                    if isinstance(_key, (int, float)): # pragma: no cover
                        row_id = int(_key)
                        if row_id < 0:
                            row_id = io.n_records + row_id

                        if io.n_records > row_id >= 0:
                            _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                            old_date, new_date = io_conv_date(days)
                            yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                        continue

                    _key = str(_key)
                    if _key in done: # pragma: no cover
                        continue

                    done.add(_key)

                    row_id = key_table[_key]
                    if row_id < 0:
                        if has_childs and _key.find(SEP_SYM) >= 0: # pragma: no cover
                            for kk,_info in self.item_iter(_key):
                                yield kk,_info

                        continue

                    if row_id >= io.n_records: # pragma: no cover
                        continue

                    _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                    old_date, new_date = io_conv_date(days)
                    yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

                return

            # bytes | bytearray | bool
            key = str(key)
            row_id = io.key_table[key]
            if io.n_records > row_id >= 0: # pragma: no cover
                _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                old_date, new_date = io.z_conv_date(days)
                yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

    def items(self) -> Generator[str,tuple]:
        yield from self.item_iter()

    def values(self) -> Generator[tuple]:
        for _key,val in self.item_iter():
            yield val

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDbReader:
    """
    Read-only base class for JDb. 

    Handles data retrieval, filtering, and caching logic without allowing 
    data modification. Designed for safe, concurrent read operations.
    """
    __slots__ = {'files_obj', 'lock', '_cache_limit', '_cache', 'file_lock', 'keys',
                'io', 'fsize', 'fp_table', 'childs', 'safe_line', 'chg_keys',
                'write_hook', 'max_wsize', 'flags'}

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

        '''
            KEY_file [str,None,bytearray,JFilesBase,JMemFiles,JDiskFiles,JDbReader]
                [None|bytearray] JMemFiles() or JMemFiles(bytearray)
                [str]
                    ''                  = use JMemFiles() in memory
                    '127.0.0.1:8001'    = use JNetFiles(('127.0.0.1', 8001))
                    'database/test.jdb' = use JDiskFiles(database/test.jdb)
                [JDbReader]     JDb.files_obj
                [JFilesBase]    JMemFiles, JNetFiles or JDiskFiles

            max_file_Size [int]
                max partial DATA file size
            min_value_size [int]
                min DATA record size                [default=16]
            index_size [int, 64 bit alignment]
                KEY record size                     [default=128]
            reserved_rate [float]
                Actual DATA record size = DATA size * (1 + reserved_rate) [default=0.001]
            cache_limit [int]
                -1 = unlimited cache
                0 = no cache                        [default]
                +ve = with cache
            key_limit [str/int]
                no       = [0] no key table limit        [default]
                l[0-6]   = [-ve] light key table
                <=[0-9]+ = [+ve] limit size

            data_type [str]
                L+J = [1] KEY=split   : VAL=Json
                M+M = [2] KEY=Marshal : VAL=Marshal
                J+J = [3] KEY=Json    : VAL=Json        [default]
                J+M = [4] KEY=Json    : VAL=Marshal
                J+P = [5] KEY=Json    : VAL=Pickle
                S+S = [6] KEY=struct  : VAL=msgpack
                J+S = [7] KEY=Json    : VAL=msgpack

            zip_typ [str]
                no = [0] no compression for VAL         [default]
                gz = [1] gzip compression(9) for VAL
                bz = [2] bz2 compression(9) for VAL
                xz = [3] lzma compression for VAL
                zs = [4] zstandard compression(22) for VAL
                br = [5] brotli compression(6) for VAL
                z1 = [6] zstandard compression(6) for VAL
                z2 = [7] zstandard compression(11) for VAL
                lz = [8] lz4 compression(0) for VAL

            api_ver [int]
                API version
                0 = oldest version
                1 = seperate row_size and val_size
                None = latest version [default]

            write_hook [function[str,Any]->bool]
                VAL hook before write to JDB

            flags [JFlag | int | str]
                flags to control write/delete behavior (default = JFlag.REVERT)

            max_wsize [int]
                max dead lines searching for new/change KEY (default=4)

        '''
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
                if not 65535 >= server_port > 0 or not all(255 > int(vv) >= 0 for vv in server_ip.split('.')): # pragma: no cover
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
                raise TypeError('write_hook(key,val) must have 2 args')

            write_hook('key', 'val')

        if max_wsize is not None:
            if not isinstance(max_wsize, int):
                raise TypeError('max_wsize must be integer')

        if flags is None:
            flags = JFlag.REVERT
        else:
            flags = JFlag(flags)

        self.files_obj = files_obj
        self.file_lock = FileLock(files_obj)
        self.lock = RLock() # solve iter issue [cannot use Lock]
        self.fsize = self.safe_line = 0
        self.childs = {}
        self.fp_table = {}
        self.chg_keys = set()
        self._cache = {}
        self._cache_limit = cache_limit
        if JDbKey_obj is None:
            self.keys = JDbKey(self)
        else:
            self.keys = JDbKey_obj

        self.write_hook = write_hook
        self.flags = flags
        self.max_wsize = 4 if max_wsize is None else max_wsize
        self.io = JIo(
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
        with self.lock:
            fp_table = self.fp_table
            if fp_table: # pragma: no cover
                for _ident,fp_dict in fp_table.items():
                    for fp in fp_dict.values():
                        if fp is None:
                            continue

                        fp.close()

                    fp_dict.clear()

                fp_table.clear()

            self.file_lock.release()

    def __repr__(self) -> str:
        io = self.io
        return f'<{type(self).__name__}[v{io.api_ver}|{io.data_type_str}|{io.zip_type_str}|{io.key_limit_str}|{io.index_size:3d}|{"H" if self.write_hook else "_"}{"c" if self._cache_limit > 0 else "C" if self._cache_limit < 0 else "_"}{str(self.flags)}] at {hex(id(self))}>'

    def __len__(self) -> int:
        with self.KEY_fopen() as key_fp:
            io = self.io
            sync_id =io.sync_id
            swap_id =io.swap_id
            remv_id =io.remv_id
            io.read_header(key_fp, seek=False)
            io.sync_id = sync_id
            io.swap_id = swap_id
            io.remv_id = remv_id

            return io.n_records

    def __iter__(self) -> Generator[str]:
        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True):
            yield from self.io.key_table

    def __getitem__(self, key:Set[str]) -> Union[Dict[str,Any],Any]:
        '''
        read data from JDbReader

        Args:
            key (Any):
                TYPE = str | int | float | bool | bytes
                    > val = jdb['name']

                TYPE = slice() | date() | datetime()
                    > val:dict = jdb[1:10:2]
                    > val:dict = jdb[-10.:]
                    > val:dict = jdb[:]
                    > val:dict = jdb[dt.date(2020,1,1)::r'key[0-9]']
                    > val:dict = jdb[:100:r'key[0-9]']

                TYPE = function(k,v)
                    > val:dict = jdb[lambda k,v: k.startswith('key')]
                    > val:dict = jdb[lambda k,v: v == 10]

                TYPE = function(k)
                    > val:dict = jdb[lambda k: k[0] == 'k']

                TYPE = tuple() | set() | list() | dict()
                    > val:dict = jdb[1, 2, 3, 'a']
                    > val:dict = jdb[(1, 2, 3, 'a')]
                    > val:dict = jdb[{1, 2, 3, 'a'}]
                    > val:dict = jdb[[1, 2, 3, 'a']]
                    > val:dict = jdb[{1:0, 2:1, 3:2, 'a':3}]

        Returns:
            TYPE = dict
                > mutliple keys with value

            TYPE = Any
                > target key's value
        
        '''
        if isinstance(key, str):
            if key.find(SEP_SYM) >= 0:
                with self.open(read_only=True):
                    if key not in self.io.key_table:
                        # pylint: disable=unnecessary-comprehension
                        return {k:v for k,v in self.item_iter(key)}

        elif isinstance(key, (bytes, bytearray)): # pragma: no cover
            pass

        elif isinstance(key, (slice, dt_date, datetime, Pattern)) \
                or callable(key) \
                or hasattr(key, '__iter__'):

            # pylint: disable=unnecessary-comprehension
            return {k:v for k,v in self.item_iter(key)}

        # str | bytes | int | float | bool
        with self.open(read_only=True) as fp:
            return self.f_read(fp, key, copy=True)

    def __contains__(self, keys:Set[str]) -> bool:
        return self.is_superset(keys)

    def __eq__(self, jdb:Union[set,dict,JDbReader]) -> bool:
        '''
            [1] jdb
                type = JDb | dict()
                    > compare KEYs and VALs

                type = set()
                    > compare KEYs only
        '''
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
                    for key,row in self.io.key_table.items():
                        ref_row = jdb_key_table[key]
                        if ref_row < 0:
                            return False

                        if f_read(fp, key, row=row, copy=False) != jdb_read(ref_fp, key, row=ref_row, copy=False):
                            return False

        elif isinstance(jdb, dict):
            with self.open(read_only=True) as fp:
                if self.io.n_records != len(jdb):
                    return False

                f_read = self.f_read
                for key,row in self.io.sorted_key_table_items():
                    if key not in jdb:
                        return False

                    if f_read(fp, key, row=row, copy=False) != jdb[key]:
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
        return self.difference(keys)

    def __add__(self, keys:Set[str]) -> Set[str]:
        return self.union(keys)

    def __or__(self, keys:Set[str]) -> Set[str]:
        return self.union(keys)

    def __and__(self, keys:Set[str]) -> Set[str]:
        return self.intersection(keys)

    def __xor__(self, keys:Set[str]) -> Set[str]:
        return self.non_intersection(keys)

    def __rsub__(self, keys:Set[str]) -> Set[str]:
        if isinstance(keys, str):
            keys = {keys}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
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
        return self.union(keys)

    def __ror__(self, keys:Set[str]) -> Set[str]:
        return self.union(keys)

    def __rand__(self, keys:Set[str]) -> Set[str]:
        return self.intersection(keys)

    def __rxor__(self, keys:Set[str]) -> Set[str]:
        return self.symmetric_difference(keys)

    def f_slice(self, fp_dict:dict, key:Union[dt_date,datetime,Any]) -> tuple:
        chk_new_date = True
        if isinstance(key, dt_date):
            key = slice(key, key+timedelta(days=1))

        elif isinstance(key, datetime):
            key = slice(key, key+timedelta(days=1))
            chk_new_date = False

        if not isinstance(key, slice):
            raise TypeError

        io = self.io
        n_records = io.n_records
        n_lines = io.n_lines
        key_table = io.key_table
        sync_id = io.sync_id

        _start = key.start
        _stop = key.stop
        _step = key.step
        chk_ver = chk_days = False
        filter_re = None

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
                if _step:
                    filter_re = re_compile(_step)#, flags=re.I)

                _step = 1
            else:
                raise TypeError(key)

            if _step == 0:
                raise ValueError('step must not be zero')

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

            elif isinstance(_start, datetime):
                chk_days = True
                chk_new_date = False
                min_days = _start.date()

            elif isinstance(_start, dt_date):
                chk_days = True
                min_days = _start

            else:
                raise TypeError(key)

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

            elif isinstance(_stop, datetime):
                chk_days = True
                chk_new_date = False
                max_days = _stop.date()

            elif isinstance(_stop, dt_date):
                chk_days = True
                max_days = _stop

            else:
                raise TypeError(key)

        if chk_ver:
            _start = 0
            _stop  = n_lines

            if key.start is None:
                pass

            elif isinstance(key.start, str):
                io, fp_dict, key_fp = self.f_get_fp(fp_dict)
                _row_id = key_table[key.start]
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
                _row_id = key_table[key.stop]
                if n_records > _row_id >= 0:
                    _k, _f, _o, _s, _vs, ver, _d = io.read_key(key_fp, _row_id)
                    max_ver = ver
                else:
                    max_ver = sync_id

            else:
                max_ver = (sync_id + int(key.stop)) if key.stop < 0 else int(key.stop)


        elif chk_days:
            _start = 0
            _stop  = n_lines if chk_new_date else n_records
            _step = 1

        return slice(_start, _stop, _step), max_ver, min_ver, max_days, min_days, filter_re, chk_new_date

    def f_open(self, read_only:bool=True) -> Dict[int,IO]:
        with self.lock:
            file_lock = self.file_lock
            ident = file_lock.acquire(read_only=read_only) # raise RuntimeError if fail
            key_fp = None
            chg_keys = self.chg_keys
            _cache = self._cache
            files_obj = self.files_obj
            fp_table = self.fp_table
            io = self.io
            fp_table[ident] = fp_dict = fp_table.get(ident, {-1:None})
            try:
                try:
                    is_latest = False
                    if read_only:
                        if io.is_updated():
                            is_latest = files_obj.KEY_size() == io.file_size
                            if is_latest:
                                self.safe_line = io.n_records
                                if chg_keys: chg_keys.clear()
                                return fp_dict
                    else:
                        io.update_days()
                        is_latest = files_obj.KEY_size() == io.file_size

                    data_type = io._data_type
                    key_fp = fp_dict.get(-1, None)
                    if key_fp is not None: # pragma: no cover
                        key_fp.flush()
                        key_fp.seek(0)
                    else:
                        key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

                    io.read_header(key_fp, seek=False) # [1] first time [2] changed by other
                    if not is_latest or not io.is_updated(): # pragma: no cover
                        io.load_keys(key_fp, force=data_type==0)
                        if _cache: _cache.clear()
                        self.fsize = io.file_size

                except FileNotFoundError:
                    if key_fp is not None:
                        key_fp.close()

                    io, key_fp = self._init_KEY()
                    fp_dict[-1] = key_fp

                self.safe_line = self.io.n_records
                if chg_keys: chg_keys.clear()
                return fp_dict

            except: # pragma: no cover
                io = self.io
                if _cache: _cache.clear()
                if chg_keys: chg_keys.clear()
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
        with self.lock:
            ident = get_ident()
            chg_keys = self.chg_keys
            _cache = self._cache
            file_lock = self.file_lock
            files_obj = self.files_obj
            fp_table = self.fp_table
            fp_dict = fp_table.get(ident, None)
            if fp_dict is None:
                return

            try:
                io = self.io
                if not io.is_updated():
                    if file_lock.mode == 'w':
                        key_fp = fp_dict.pop(-1, None)
                        try:
                            if key_fp is None: # pragma: no cover
                                try:
                                    key_fp = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

                                except FileNotFoundError:
                                    io, key_fp = self._init_KEY()
                            else:
                                key_fp.flush()
                                key_fp.seek(0)

                            if _cache: # pragma: no cover
                                if not io.key_table:
                                    _cache.clear()
                                else:
                                    for kk in set(_cache).difference(io.key_table):
                                        _cache.pop(kk, 0)

                            self.fsize = io.write_header(key_fp, seek=False)

                        finally:
                            if key_fp is not None:
                                key_fp.close()

                    # read mode
                    elif io.file_size == 0 or io.n_records != len(io.key_table): # pragma: no cover
                        if _cache:
                            _cache.clear()

                        if chg_keys:
                            chg_keys.clear()
                        io.key_table.clear()
                        io.file_table.clear()
                        self.fsize = io.n_records = io.n_lines = io._n_records = io._n_lines = io.file_size = 0

            finally:
                if chg_keys:
                    chg_keys.clear()

                for fp in fp_dict.values():
                    if fp is not None:
                        fp.close()

                fp_dict.clear()
                fp_table.pop(ident, None)
                file_lock.release()

    @contextmanager
    def open(self, read_only:bool=True, no_raise:bool=False) -> Generator[Dict[int,IO]]:
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
            fp_table[ident] = fp_dict = fp_table.get(ident, {-1:None})
            io = self.io
            try:
                try:
                    if read_only:
                        if io.is_updated():
                            if files_obj.KEY_size() == io.file_size:
                                sync_id = io.sync_id
                                self.safe_line = io.n_records
                                if chg_keys: chg_keys.clear()
                                yield fp_dict
                                return

                        is_latest = False
                    else:
                        io.update_days()
                        is_latest = files_obj.KEY_size() == io.file_size

                    data_type = io._data_type
                    key_fp = fp_dict.get(-1, None)
                    if key_fp is not None: # pragma: no cover
                        key_fp.flush()
                        key_fp.seek(0)
                    else:
                        key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

                    io.read_header(key_fp, seek=False) # [1] first time [2] changed by other
                    if not is_latest or not io.is_updated():
                        io.load_keys(key_fp, force=data_type==0)
                        if _cache: _cache.clear()
                        self.fsize = io.file_size

                except FileNotFoundError:
                    if key_fp is not None:
                        key_fp.close()

                    io, key_fp = self._init_KEY()
                    fp_dict[-1] = key_fp

                sync_id = io.sync_id
                fsize = io.file_size
                self.safe_line = io.n_records
                if chg_keys: chg_keys.clear()
                yield fp_dict

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
                    if _cache: _cache.clear()
                    if chg_keys: chg_keys.clear()
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
                    sync_id = io.sync_id
                    if chg_keys: chg_keys.clear()
                    self.safe_line = io.n_records
                    yield fp_dict

                else:
                    raise

            finally:
                try:
                    io = self.io
                    if not io.is_updated():
                        if file_lock.mode == 'w':
                            if not is_error:
                                key_fp = fp_dict.pop(-1, None)
                                try:
                                    if key_fp is None: # pragma: no cover
                                        key_fp = files_obj.KEY_open('ab+', buffering=KEY_FILE_BUF_SIZE)
                                    else:
                                        key_fp.flush()

                                    if _cache and io.remv_id != io._remv_id:
                                        for kk in set(_cache).difference(io.key_table):
                                            _cache.pop(kk, 0)

                                    self.fsize = io.write_header(key_fp)

                                finally:
                                    if key_fp is not None:
                                        key_fp.close()

                        elif io.file_size == 0 or io.n_records != len(io.key_table): # read mode
                            if _cache: _cache.clear()
                            if chg_keys: chg_keys.clear()
                            io.key_table.clear()
                            io.file_table.clear()
                            self.fsize = io.n_records = io.n_lines = io._n_records = io._n_lines = io.file_size = 0

                finally:
                    for fp in fp_dict.values():
                        if fp is not None:
                            fp.close()

                    fp_dict.clear()
                    fp_table.pop(ident, None)
                    file_lock.release()

        finally:
            self.lock.release()

    @contextmanager
    def KEY_fopen(self, read_only:bool=True) -> Generator[IO]:
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
        return self.files_obj.get_folder()

    @property
    def file_name(self) -> str:
        return self.files_obj.get_name()

    @property
    def path(self) -> str:
        return self.files_obj.get_path()

    @property
    def key_table(self) -> Dict[str,int]:
        return self.io.key_table

    @property
    def file_table(self) -> Dict[int,int]:
        return self.io.file_table

    @property
    def n_records(self) -> int:
        return self.io.n_records

    @property
    def n_lines(self) -> int:
        return self.io.n_lines

    @property
    def index_size(self) -> int:
        return self.io.index_size

    @property
    def reserved_rate(self) -> int:
        return self.io.reserved_rate

    @property
    def min_value_size(self) -> int:
        return self.io.min_value_size

    @property
    def sync_id(self) -> int:
        return self.io.sync_id

    @property
    def swap_id(self) -> int:
        return self.io.swap_id

    @property
    def remv_id(self) -> int:
        return self.io.remv_id

    @property
    def api_ver(self) -> int:
        return self.io.api_ver

    @property
    def data_type(self) -> str:
        return self.io.data_type_str

    @property
    def zip_type(self) -> str:
        return self.io.zip_type_str

    @property
    def key_limit(self) -> str:
        return self.io.key_limit_str

    @key_limit.setter
    def key_limit(self, value:Union[int,str]):
        with self.lock:
            self.io.key_limit = value

    @property
    def cache_limit(self) -> int:
        return self._cache_limit

    @cache_limit.setter
    def cache_limit(self, value:int):
        with self.lock:
            old_value = self._cache_limit
            if value < 0:
                self._cache_limit = -1
            elif value > 0:
                if value < old_value:
                    self._cache.clear()

                self._cache_limit = value
            else:  #value == 0
                if self._cache:
                    self._cache.clear()

                self._cache_limit = value

    def len_(self) -> int:
        key_fp = None
        try:
            key_fp = self.files_obj.KEY_open('rb', buffering=KEY_FILE_BUF_SIZE)
            io = self.io.read_header(key_fp, seek=False)
            return io.n_records

        except FileNotFoundError: # pragma: no cover
            pass

        finally:
            if key_fp is not None:
                key_fp.close()

        return 0

    def create_jdb(self, KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None], **kwargs) -> JDbReader:
        return JDbReader(KEY_file=KEY_file, **kwargs)

    def can_lock(self) -> bool:
        if not self.lock.acquire(): # pylint: disable=consider-using-with
            return False

        try:
            return self.file_lock.can_lock()

        except: # pragma: no cover
            return False

        finally:
            self.lock.release()

    def non_joint(self, keys:Set[str]) -> Set[str]:
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        return self.intersection(keys)

    def union(self, keys:Set[str]) -> Set[str]:
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
            with self.open(read_only=True):
                if jdb is self or jdb.files_obj == self.files_obj:
                    return set()

                key_table = set(self.io.key_table)
                with jdb.open(read_only=True):
                    return key_table.symmetric_difference(jdb.io.key_table)

        elif hasattr(keys, '__iter__'):
            if not keys:
                with self.open(read_only=True):
                    return set(self.io.key_table)

            keys = {key if isinstance(key, str) else str(key) for key in keys}

        else: # pragma: no cover
            keys = {str(keys)}

        with self.open(read_only=True):
            return keys.symmetric_difference(self.key_table)

    def symmetric_difference(self, keys:Set[str]) -> Set[str]:
        return self.non_intersection(keys)

    def difference(self, keys:Set[str]) -> Set[str]:
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if isinstance(keys, str): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if not self.lock.acquire(): # pylint: disable=consider-using-with
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
        io = self.io
        if io.key_table:
            return key in io.key_table

        if not self.lock.acquire(): # pylint: disable=consider-using-with
            return False

        try:
            if self.io.is_updated():
                return False

        finally:
            self.lock.release()

        with self.open(read_only=True):
            return key in self.io.key_table

    def has_any(self, keys:Set[str]) -> bool:
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
        if isinstance(keys, str): # pragma: no cover
            keys = {keys}

        elif isinstance(keys, bytes): # pragma: no cover
            keys = {str(keys)}

        elif isinstance(keys, JDbReader):
            jdb = keys
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
                    size = sum(list(io.file_table.values()))
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
                io = self.io.read_header(key_fp, seek=False)
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

    def values(self) -> Generator[Any]:
        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True) as fp:
            f_read = self.f_read
            for key,row in self.io.key_table.items():
                yield f_read(fp, key, row=row, copy=False)

    def items(self, read_only:bool=True) -> Generator[str,Any]:
        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=read_only) as fp:
            f_read = self.f_read
            if read_only:
                for key,row in self.io.key_table.items():
                    yield key, f_read(fp, key, row=row, copy=False)
            else:
                for key,row in self.io.sorted_key_table_items(copy=True):
                    # cannot use row argument while using yield
                    yield key, f_read(fp, key, copy=False)

    def item_iter(self, key:Optional[Any]=None) -> Generator[str,Any]:
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
            if key is None:
                key = slice(0, None)

        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True) as fp:
            io, fp, key_fp = self.f_get_fp(fp)
            if isinstance(key, str):
                idx = key.find(SEP_SYM)
                if idx < 0:
                    row_id = io.key_table[key]
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

            if isinstance(key, int):
                n_records = io.n_records
                row_id = key
                if row_id < 0:
                    row_id = n_records + row_id

                if n_records > row_id > 0:
                    _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                    yield _key, self.f_read(fp, _key, row=row_id, copy=False)

                return

            if isinstance(key, float):
                sync_id = int(key)
                sync_id = (io.sync_id + sync_id) if sync_id < 0 else sync_id
                if sync_id >= io.sync_id or sync_id < 0:
                    return

                io_read_key = io.read_key
                n_records = io.n_records
                for row_id in range(n_records):
                    _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                    if ver != sync_id:
                        continue
                    yield _key, self.f_read(fp, _key, row=row_id, copy=False)

                return

            if isinstance(key, (slice, dt_date, datetime)):
                _cache = self._cache
                cache_limit = self._cache_limit
                _update_cache = self._update_cache
                _decode_row = self._decode_row
                f_get_val_fp = self.f_get_val_fp
                n_records = io.n_records
                io_read_key = io.read_key
                io_conv_date = io.z_conv_date
                io_read_value = io.read_value
                new_slice, max_ver, min_ver, max_date, min_date, filter_re, chk_new_date = self.f_slice(fp, key)
                chk_date = max_date is not None or min_date is not None
                for row_id in range(new_slice.start, new_slice.stop, new_slice.step):
                    if not n_records > row_id >= 0: continue

                    _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                    if not max_ver > ver >= min_ver or filter_re and not filter_re.search(_key):
                        continue

                    if chk_date:
                        old_date, new_date = io_conv_date(days)
                        if chk_new_date:
                            if min_date and new_date < min_date or max_date and new_date >= max_date:
                                continue
                        else:
                            if min_date and old_date < min_date or max_date and old_date >= max_date:
                                continue

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
                    for _key,row_id in io.key_table.items():
                        val = f_read(fp, _key, row=row_id, copy=False)
                        if not is_matched(_key, val): continue
                        yield _key, val

                elif k_arg_cnt == 1:
                    for _key,row_id in io.key_table.items():
                        if not is_matched(_key): continue
                        val = f_read(fp, _key, row=row_id, copy=False)
                        yield _key, val

                return

            if isinstance(key, (bytes, bytearray)): # pragma: no cover
                pass

            elif hasattr(key, '__iter__'):
                done = set()
                f_read = self.f_read
                key_table = io.key_table
                has_childs = len(io.groups) > 0 or len(self.childs) > 0
                for _key in key:
                    _key = str(_key)
                    if _key not in done:
                        done.add(_key)

                        row_id = key_table[_key]
                        if row_id < 0:
                            if has_childs and _key.find(SEP_SYM) >= 0:
                                for kk,vv in self.item_iter(_key):
                                    yield kk,vv

                            continue

                        val = f_read(fp, _key, row=row_id, copy=False)
                        yield _key, val

                return

            # bytes | bytearray | bool
            if not isinstance(key, str): # pragma: no cover
                key = str(key)
                row_id = io.key_table[key]
                if row_id >= 0:
                    yield key, self.f_read(fp, key, row=row_id, copy=False)

    def find_iter(self, keys:Optional[Any]=None, vals:Optional[Dict[str,Any]]=None, date:Union[str,datetime,dt_date,int,None]=None, limit:int=0, with_value:bool=False, **kwargs) -> Generator[Tuple[str,Any]]:
        '''
            $gt, $ge, $lt, $le, $eq, $ne, $in ,$re, $re2, $has, $func : value
                find_iter(vals={'$eq': "value"})
                    == find_iter(EQ="value")
                find_iter(vals={'$in': ["value1", "value2"]})
                    == find_iter(IN=["value1", "value2"])
                find_iter(vals={'$func': lamdba value:value == "any"})
                    == find_iter(FUNC=lambda value:value == "any")
                    == find_iter(FUNC=lambda key,val:val == "any")
                
            $and, $or, $not : {...}
                find_iter(vals={'$or': {'$eq':'value1', '$eq_':'value2'}})
                    == find_iter(OR={'$eq':'value1', '$eq_':'value2'})
                find_iter(vals={'$and': {'$gt':0, '$le':100}})
                    == find_iter(AND={'$gt':0, '$le':100}) # 100 >= value >= 0
                find_iter(vals={'$not: {'$eq':'value1'})
                    == find_iter(NOT={'$eq':'value1'}) # find_iter(NE='value1')

            $all

            $val : {...}
                $gt, $ge, $lt, $le, $eq, $ne : value
                $in : {a, b, c}
                $func : func(a)
                $has : value
                $re : string (obj -> json -> str)
                $re2 : string (obj -> json -> sub(W) -> str)
                $and, $or, $not {...}
                $[0-9]+ : {...}
                $val : {...},
                field_name : {...}

            field_name : {...}
                $gt, $ge, $lt, $le, $eq, $ne : value
                $in : {a, b, c}
                $has : value
                $re : string (obj -> json -> str)
                $re2 : string (obj -> json -> sub(W) -> str)
                $and, $or, $not {...}
                $[0-9]+ : {...}
                $val : {...},
                field_name : {...}}

            field_name : 1  -> {field_name : {'$eq' : 1}}
            field_name : 'a'  -> {field_name : {'$re' : 'a'}}
            field_name : lambda v : v  -> {field_name : {'$func' : lambda v : v}}
            field_name : [1,2,3] -> {field_name : {'$in' : [1,2,3]}}

            example
                find(r'^[Rr].*[Nn]$', IN=[8,27])
                    -> find(keys=[r'^[Rr]', r'[Nn]$'], vals={'$in' : [8, 27]})
                find(keys=[r'^[Rr]', r'[Nn]$'], vals={'$val' : {'$gt' : 8} })
                find(keys=[r'^[Rr]', r'[Nn]$'], vals={'$gt' : 8, '$lt' : 100})
                find(keys=[r'^[Rr]', r'[Nn]$'], vals={'$or' : {'$eq' : 8, '$lt' : 50}})
                find(vals={'name' : r'Jo(e|hn)'}, re_flags=re.I)
                find(ANY='name')
                    -> find(vals={'$any' : r'name'})
                    -> find(vals={'$any' : {'$re' : r'name'}})

        '''

        re_flags = kwargs.get('re_flags', re_I)

        if not vals:
            vals = {}

        for key,val in kwargs.items():
            if key in FIND_OPS:
                vals[f'${key.lower()}'] = val

        if vals:
            with_value = True

        key_rule = None
        if keys:
            if isinstance(keys, Pattern):
                key_rule = keys

            elif isinstance(keys, str):
                idx = keys.find(SEP_SYM)
                if idx >= 0:
                    # 'jdb_name:::jdb_key'
                    key_rule = keys[:idx]
                    key_rule = re_compile(key_rule, flags=re_flags) if key_rule else None
                    next_keys = keys[idx+SEP_LEN:]
                    next_idx = next_keys.find(SEP_SYM)

                    if next_idx < 0 and not next_keys: # pragma: no cover
                        next_keys = None

                    # pylint: disable=contextmanager-generator-missing-cleanup
                    with self.open(read_only=True) as fp:
                        f_get_child = self.f_get_child
                        for child_name in self.io.key_table:
                            if not (key_rule and not key_rule.search(child_name)):
                                child = f_get_child(fp, child_name)
                                if isinstance(child, JDbReader):
                                    for kk,vv in child.find_iter(next_keys, vals=vals, date=date, limit=limit, with_value=with_value, **kwargs):
                                        yield child_name+SEP_SYM+kk,vv
                    return

                key_rule = re_compile(keys, flags=re_flags)

            elif hasattr(keys, '__iter__'):
                key_rule = {key if isinstance(key, str) else str(key) for key in keys}

            elif callable(keys):
                key_rule = keys

            else:  # pragma: no cover
                raise TypeError('invalid type')

        min_date = max_date = None
        chk_new_date = True
        if isinstance(date, str):
            matches = re_findall(r'(?<!\d)(\d{1,4})\W([01]?\d)\W([0123]?\d)(?!\d)', date)
            if matches:
                date_list = []
                for dd in matches:
                    try:
                        date_list.append(dt_date(*[int(v) for v in dd]))
                    except ValueError: # pragma: no cover
                        pass

                if len(date_list) > 1:
                    min_date = date_list[0]
                    max_date = date_list[-1]
                elif date_list:
                    max_date = min_date = date_list[0]

        elif isinstance(date, datetime):
            chk_new_date = False
            min_date = max_date =  date.date()

        elif isinstance(date, dt_date):
            chk_new_date = True
            min_date = max_date = date

        elif isinstance(date, int):
            max_date = dt_date.today()
            min_date = max_date - timedelta(days=abs(date))

        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True) as fp:
            io, fp, key_fp = self.f_get_fp(fp)
            count = 0
            io_read_key = io.read_key
            io_conv_date = io.z_conv_date
            n_records = io.n_records
            data_type = io.data_type_str
            cache = self._cache
            for row in range(n_records):
                if count >= limit > 0:
                    break

                key, _file_id, _offset, _row_size, _val_size, _ver, _days =  io_read_key(key_fp, row)
                if min_date and max_date:
                    old_date, new_date = io_conv_date(_days)
                    if chk_new_date:
                        if not max_date >= new_date >= min_date:
                            continue
                    else:
                        if not max_date >= old_date >= min_date:
                            continue

                value = value_b = None
                is_matched = True
                if key_rule:
                    if callable(key_rule):
                        arg_cnt = key_rule.__code__.co_argcount
                        if arg_cnt == 2:
                            if key not in cache:
                                value, value_b = self.f_read_with_bytes(fp, key)
                            else:
                                value = cache.get(key, None)

                            if not key_rule(key, value):
                                is_matched = False
                            else:
                                with_value = True

                        elif arg_cnt == 1:
                            if not key_rule(key):
                                is_matched = False
                        else:
                            raise TypeError(f'invalid function {arg_cnt} != 1 or 2')

                    elif isinstance(key_rule, set):
                        if key not in key_rule:
                            is_matched = False

                    elif not key_rule.search(key):
                        is_matched = False

                    if not is_matched:
                        continue

                if not with_value:
                    yield key, None
                    count += 1
                    continue

                if value is None:
                    if key not in cache:
                        value, value_b = self.f_read_with_bytes(fp, key)
                    else:
                        value = cache.get(key, None)

                for ref,rules in vals.items():
                    if ref == '$val':
                        if not _match_rules(key, value, rules):
                            is_matched = False
                            break

                    elif ref == '$any':
                        if isinstance(value, dict):
                            if not any(_match_rules(key, vv, rules, ANY=True) for vv in value.values()):
                                is_matched = False

                        elif not hasattr(value, '__iter__'):
                            if not _match_rules(key, value, rules):
                                is_matched = False

                        elif isinstance(value, (list, tuple, set, frozenset)):
                            if not any(_match_rules(key, vv, rules, ANY=True) for vv in value):
                                is_matched = False

                        else:
                            if not _match_rules(key, value, rules):
                                is_matched = False

                        if not is_matched and isinstance(rules, dict):
                            _is_matched = False
                            if isinstance(value, dict):
                                for _ref,_rules in rules.items():
                                    if _ref in value:
                                        if _match_rules(key, value[_ref], _rules):
                                            _is_matched = True
                                        else:
                                            _is_matched = False
                                            break

                            if _is_matched:
                                is_matched = True

                        if not is_matched:
                            break

                    elif ref[0] == '$':
                        if ref[1:].isdigit(): # eg $1, $2
                            if not isinstance(value, list):
                                is_matched = False
                                break

                            try:
                                if not _match_rules(key, value[int(ref[1:])], rules):
                                    is_matched = False
                                    break

                            except IndexError:
                                is_matched = False
                                break
                        else:
                            use_bytes = False
                            if ref in {'$eq', '$ne'}:
                                if isinstance(rules, bytes) and not isinstance(value, bytes):
                                    use_bytes = True

                            elif ref == '$has':
                                if isinstance(rules, bytes) and not isinstance(value, bytes):
                                    use_bytes = True
                                elif isinstance(rules, str) and data_type.endswith('J'):
                                    use_bytes = True

                            elif ref in {'$re', '$re2'}:
                                if data_type.endswith('J'):
                                    use_bytes = True

                            if use_bytes:
                                if value_b is None:
                                    try:
                                        value_b = io.VAL_dumps(value)
                                    except ValueError: # pragma: no cover
                                        value, value_b = self.f_read_with_bytes(fp, key)

                                _value = value_b
                            else:
                                _value = value

                            if not _match_rules(key, _value, {ref : rules}):
                                is_matched = False
                                break

                    elif isinstance(value, dict) and ref in value:
                        if not _match_rules(key, value[ref], rules):
                            is_matched = False
                            break
                    else:
                        is_matched = False
                        break

                if is_matched:
                    yield (key, value)
                    count += 1

    def map(self, map_func:Callable[[str,Any],Any], keys:Optional[Any]=None, vals:Optional[Any]=None, date:Union[str,datetime,dt_date,int,None]=None, sort:int=0, **kwargs) -> list:
        matches = []

        if not callable(map_func):
            raise TypeError('not callable')

        for key,val in self.find_iter(keys=keys, vals=vals, date=date, with_value=True, **kwargs):
            matches.append(map_func(key, val))

        if sort:
            return sorted(matches, reverse=sort<0, **kwargs)

        return matches

    def find(self, keys:Optional[Any]=None, vals:Optional[Dict[str,Any]]=None, date:Union[str,datetime,dt_date,int,None]=None, limit:int=0, with_value:bool=False, sort:int=0, **kwargs) -> Dict[str,Any]:
        if not vals:
            vals = {}

        for key,val in kwargs.items():
            if key in FIND_OPS:
                vals[f'${key.lower()}'] = val

        if vals or sort:
            with_value = True

        matches = {}
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, limit=limit, with_value=with_value, **kwargs):
            matches[key] = val

        if sort:
            return dict(sorted(matches.items(), key=lambda v : v[1], reverse=sort<0))

        return matches

    def sync(self, force:bool=False) -> JDbReader:
        if force:
            self.unsync()

        with self.open(read_only=True) as fp:
            if len(self.key_table) != self.io.n_records: # pragma: no cover
                self.f_load_keys(fp)

        return self

    def unsync(self, with_child:bool=False) -> JDbReader:
        if not self.lock.acquire(): # pylint: disable=consider-using-with
            raise RuntimeError

        try:
            io = self.io
            if with_child:
                for _key,child in io.groups.items():
                    if isinstance(child, JDbReader):
                        child.unsync()

                for _key,child in self.childs.items():
                    if isinstance(child, JDbReader):
                        child.unsync()

            self._cache.clear()
            io.key_table.clear()
            io.file_table.clear()
            io._n_records = io._n_lines = io.file_size = 0

        finally:
            self.lock.release()

        return self

    def load_table(self, force:bool=False) -> Tuple[Dict[str,int],Dict[int,int]]:
        with self.open(read_only=True) as fp:
            self.f_load_keys(fp, force=force)
            return self.io.key_table, self.io.file_table

    def get(self, key:str, default_val:Any=None, copy:bool=True) -> Any:
        with self.open(read_only=True) as fp:
            io = self.io
            row = io.key_table[key]
            if row < 0:
                return default_val

            try:
                return self.f_read(fp, key, copy=copy, row=row)

            except KeyError: # pragma: no cover
                return default_val

    def get_cache(self, key:str, default_val:Any=None, copy:bool=False) -> Any:
        val = self._cache.get(key, None)
        if val is not None:
            return deepcopy(val) if copy else val

        io = self.io
        key_table = io.key_table
        if key not in key_table:
            n_records = io.n_records
            if not (n_records == 0 or n_records != len(key_table)):
                return default_val

        return self.get(key, default_val, copy=copy)

    def get_n(self, *records:str) -> Dict[str,Any]:
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
        data = {}
        with self.open(read_only=True) as fp:
            f_read = self.f_read
            if cache_only:
                cache_limit = self._cache_limit
                _cache = self._cache
                for key,row in self.io.key_table.items():
                    if len(_cache) >= cache_limit >= 0:
                        break

                    f_read(fp, key, row=row, copy=False)

            else:
                for key,row in self.io.key_table.items():
                    data[key] = f_read(fp, key, row=row, copy=False)

            return data

    def check_version(self, version:int, max_version:Optional[int]=None, with_value:bool=False) -> dict:
        with self.open(read_only=True) as fp:
            return self.f_read_version(fp, version=version, max_version=max_version, with_value=with_value)

    def check_row(self, row_id:int=0, with_value:bool=False) -> Optional[tuple]:
        with self.open(read_only=True) as fp:
            return self.f_read_row(fp, row_id, with_value)

    def get_bytes(self, key:str) -> bytes:
        with self.open(read_only=True) as fp:
            return self.f_read_bytes(fp, key)

    def check_status(self, keys:dict) -> Dict[str,Tuple[str,int]]:
        status = {}
        with self.open(read_only=True) as fp_dict:
            io, fp_dict, key_fp = self.f_get_fp(fp_dict)
            io_read_key = io.read_key
            f_read_status = self.f_read_status

            for key,ver in keys.items():
                if key == '':
                    if ver is None: # pragma: no cover
                        ver = io._sync_id

                    max_ver = io.sync_id
                    for _row in range(io.n_records):
                        _key, _f, _o, _r, _v, _ver, _d = io_read_key(key_fp, _row)
                        if max_ver >= _ver >= ver:
                            if _key not in status:
                                status[_key] = ('+', _ver)
                else:
                    status[key] = f_read_status(fp_dict, key, ver)

        return status

    def is_latest(self) -> bool:
        with self.KEY_fopen():
            if self.io.is_updated():
                fsize = self.files_obj.KEY_size()
                return fsize == self.io.file_size

        return False

    def get_group(self, key:str) -> Optional[JDbReader]:
        if not re_match(r'^[0-9A-Za-z_]+$', key):
            raise KeyError

        with self.open(read_only=True) as fp:
            return self.f_get_group(fp, key)

    def get_child(self, name:str) -> Optional[JDbReader]:
        with self.open(read_only=True) as fp:
            return self.f_get_child(fp, name)

    def f_get_group(self, fp_dict:Dict[int,IO], key:str) -> Optional[JDbReader]:
        io = self.io
        row = io.key_table[key]
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
                if isinstance(jdb, JDbReader) and self.files_obj.is_group(jdb.files_obj.get_KEY(), key):
                    io.groups[key] = jdb
                    self.childs.pop(key, None)
                    return jdb

        self.io.groups.pop(key, None)
        return None

    def f_get_child(self, fp_dict:Dict[int,IO], name:str) -> Optional[JDbReader]:
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
        cache_limit = self._cache_limit
        if cache_limit != 0:
            _cache = self._cache
            if cache_limit < 0:
                # infinity cache
                pass
            else:
                _size = len(_cache)
                if cache_limit > _size:
                    # cache capacity < upper limit
                    pass

                elif _size > 0:
                    _key = next(iter(_cache))
                    _cache.pop(_key, None)

            _cache[key] = deepcopy(val) if copy else val

    def f_read_row(self, fp_dict:Dict[int,IO], row_id:int, with_value:bool=False) -> Optional[tuple]:
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
        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        if max_version is None:
            max_version = io.n_lines

        #pass;0;assert isinstance(max_version, int)
        version = max(version, 0)
        matched_list = {}
        io_read_key = io.read_key
        io_read_value = io.read_value
        _decode_row = self._decode_row
        f_get_val_fp = self.f_get_val_fp
        _update_cache = self._update_cache
        cache_limit = self._cache_limit
        _cache = self._cache
        for row in range(io.n_lines):
            key, file_id, offset, row_size, val_size, ver, days = io_read_key(key_fp, row)
            if not max_version >= ver >= version: continue
            data = [key, file_id, offset, row_size, val_size, ver, days, row < io.n_records]
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

            matched_list[row] = data

        return matched_list

    def f_read_bytes(self, fp_dict:Dict[int,IO], key:str) -> bytes:
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io = self.io
        row = io.key_table[key]
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
        """
        read value with unzip bytes
        
        Args:
            fp_dict (Optional, Dict[int, IO])
                None = use current thread
            key (str): read key from database
        
        Returns:
            Tuple[Any, bytes]: key's data and key's unzip bytes

        """
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io = self.io
        row = io.key_table[key]
        if not io.n_records > row >= 0: # pragma: no cover
            raise KeyError(key)

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        _key, file_id, offset, row_size, val_size, _ver, _days = io.read_key(key_fp, row)
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

        try:
            val_bytes = io.unzip(val_bytes, zip_type=zip_type)
            val = io.VAL_loads(val_bytes)
            return val, val_bytes

        except Exception as e: # pragma: no cover
            raise ValueError from e

    def f_read(self, fp_dict:Dict[int,IO], key:Optional[str], default_val:Optional[Any]=None, row:Optional[int]=None, copy:bool=True) -> Any:
        if not isinstance(key, str):
            key = str(key)

        # Priority: cache > file
        _cache = self._cache
        if _cache and key in _cache:
            if row is None or self.io.key_table[key] == row:
                _cache[key] = val = _cache.pop(key, None)
                return deepcopy(val) if copy else val

        if row is None:
            row = self.io.key_table[key]
            if row < 0:
                if default_val is not None:
                    return default_val

                raise KeyError(key)

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        if row >= io.n_records: # pragma: no cover
            io.key_table.pop(key, -1)
            if default_val is not None:
                return default_val

            raise KeyError(key)

        _key, file_id, offset, row_size, val_size, _ver, _days = io.read_key(key_fp, row)
        if key != _key:
            if _cache and _key in _cache:
                _cache[_key] = val = _cache.pop(_key, None)
                return deepcopy(val) if copy else val

        if row_size == 0:
            val = self._decode_row(file_id, offset, _key, val_size)
        else:
            val_fp, __i, __o  = self.f_get_val_fp(fp_dict, file_id)
            try:
                val = io.read_value(val_fp, offset, row_size, val_size)

            except Exception as e: # pragma: no cover
                raise ValueError from e

        if self._cache_limit == 0:
            return val

        self._update_cache(_key, val, copy=False)
        return deepcopy(val) if copy else val

    def f_load_keys(self, fp_dict:Dict[int,IO], force:bool=False):
        key_fp = fp_dict.get(-1, None)
        if key_fp is None:
            files_obj = self.files_obj
            try:
                key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)

            except FileNotFoundError: # pragma: no cover
                io, key_fp = self._init_KEY()
                fp_dict[-1] = key_fp
        else:
            key_fp.flush()
            key_fp.seek(0)

        io = self.io.read_header(key_fp, seek=False)
        if force or not io.is_updated():
            io.load_keys(key_fp, force=force)
            self._cache.clear()
            self.fsize = io.file_size

    def f_find_keys(self, fp_dict:Dict[int,IO], pattern:Union[str,Pattern], **kwargs) -> Set[str]:
        if isinstance(pattern, Pattern):
            pass
        elif isinstance(pattern, str):
            pattern = re_compile(pattern, **kwargs)
        else:
            raise TypeError(pattern)

        io, fp_dict, _key_fp = self.f_get_fp(fp_dict)
        matches = set()
        for key in io.key_table:
            if pattern.search(key):
                matches.add(key)

        return matches

    def f_read_status(self, fp_dict:Dict[int,IO], key:str, ver:int) -> Tuple[str,int]:
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        row = io.key_table[key]
        if row < 0:
            io_read_key = io.read_key
            for _row in range(io.n_records, io.n_lines):
                _key, _f, _o, _r, _v, _ver, _d = io_read_key(key_fp, _row)
                if _key == key:
                    return ('-', _ver) # deleted

            return ('x', io._sync_id) # Not exist

        if row >= io.n_records: #  pragma: no cover
            io.key_table.pop(key, -1)
            return ('x', io._sync_id) # Not exist

        _key, _f, _o, _r, _v, _ver, _d = io.read_key(key_fp, row)
        if ver is None:
            return ('', _ver) # get status and current version

        if ver == _ver:
            return ('', ver) # No change

        return ('!', _ver) # changed

    def f_get_fp(self, fp_dict:Optional[Dict[int,IO]]) -> Tuple[JIo,Dict[int,IO],IO]:
        if fp_dict is None:
            ident = get_ident()
            fp_dict = self.fp_table[ident]

        io = self.io
        #pass;0;assert isinstance(fp_dict, dict)
        key_fp = fp_dict.get(-1, None)
        if key_fp is None:
            files_obj = self.files_obj
            try:
                io.update_days()
                is_latest = files_obj.KEY_size() == io.file_size
                key_fp = fp_dict[-1] = files_obj.KEY_open('rb+', buffering=KEY_FILE_BUF_SIZE)
                data_type = io._data_type
                io.read_header(key_fp, seek=False)
                if not is_latest or not io.is_updated():
                    io.load_keys(key_fp, force=data_type == 0)
                    self._cache.clear()
                    self.fsize = io.file_size

            except FileNotFoundError:
                io, key_fp = self._init_KEY()
                fp_dict[-1] = key_fp

        return io, fp_dict, key_fp

    def f_get_val_fp(self, fp_dict:Dict[int,IO], file_id:Optional[int]=None, max_fp:int=64) -> Tuple[IO,int,int]:
        io = self.io
        file_table = io.file_table

        if file_id is None:
            max_file_size = io.max_file_size
            num_files = len(file_table)
            step = max(1, num_files//4)
            file_id = max(0, num_files-1)
            while True:
                offset = file_table.get(file_id, 0)
                if offset <= max_file_size:
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

    def _init_KEY(self) -> Tuple[JIo,IO]:
        io = self.io
        key_fp = self.files_obj.KEY_open('wb+', buffering=KEY_FILE_BUF_SIZE)
        io.reset()
        self._cache.clear()
        self.fsize = io.write_header(key_fp, seek=False)
        key_fp.flush()
        key_fp.seek(0)
        return io, key_fp

    def _init_VAL(self, file_id:int): # pragma: no cover
        val_fp = None
        try:
            val_fp = self.files_obj.VAL_open(file_id, 'wb', buffering=0)

        finally:
            if val_fp is not None:
                val_fp.close()

    def _decode_row(self, file_id:int, offset:int, key:str, val_size:int=0) -> Any:
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
            if self.files_obj.get_KEY() == '<MEM>':
                jdb = self.childs.get(key, None)
                if isinstance(jdb, JDbReader):
                    return jdb

            jdb = io.groups[key]
            if jdb is None:
                io.groups[key] = jdb = self.create_jdb(
                    KEY_file=self.files_obj.create_group(key),
                    data_type=io._data_type,
                    zip_type=io._zip_type,
                    reserved_rate=io.reserved_rate,
                    cache_limit=self._cache_limit,
                    key_limit=io._key_limit,
                    min_value_size=io.min_value_size,
                    max_file_size=io.max_file_size,
                    index_size=io.index_size)

                self.childs.pop(key, None)

            return jdb

        if file_id == 0x18: # dt.date
            return dt_date.fromordinal(offset)

        if file_id == 0x19: # dt.datetime
            val, = _Float64_unpack(_UInt64_pack(offset))
            return datetime.fromtimestamp(val)

        raise ValueError

    def _encode_row(self, key:str, val:Any) -> Tuple[int,Union[int,bytes],int]:
        '''
            +---------------------------+----------------------------------+
            | type_id = file_id (uint64)| type_val = offset (uint64)       |
            +===========================+==================================+
            | 0x0000                    | None                             |  [0x00]
            +===========================+==================================+
            | 0x0001                    | bool                             |  [0x01]
            +===========================+==================================+
            |                           | int  (sign+63bit)                |  [0x02] -2**63 <= i <= 2*63-1
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
        '''
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

        else:
            # 0x10 ~ 0x1f
            if is_jdb:
                io = self.io
                if key not in io.groups and self.files_obj.is_group(val.files_obj.get_KEY(), key):
                    io.groups[key] = val
                    self.childs.pop(key, None)

                return (0x10, 0, 0)

            _type = type(val)

        if _type is bool:
            return (0x01, 1 if val else 0, 0)

        io = self.io
        if io.row_bytes < 0 and _type not in {dt_date, datetime}:
            # for better KEY row size
            _bytes = io.dumps_with_zip(val, zip_type=0)
            n_bytes = len(_bytes)
            return (-1, _bytes if io._zip_type == 0 else io.zip(_bytes, zip_type=io._zip_type), n_bytes)

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

        _bytes = io.dumps_with_zip(val, zip_type=0)
        n_bytes = len(_bytes)

        # 0x08 ~ 0x0f
        if n_bytes <= 15:
            if n_bytes <= 8:
                _bytes = io.pad(_bytes, max_size=8, no_zip=True)
                type_val, = _UInt64_unpack(_bytes)
                return (0x08, type_val, n_bytes)

            _bytes = io.pad(_bytes, max_size=15, no_zip=True) + b'\x01'
            type_val, type_id = _UInt64_x2_unpack(_bytes)
            return (type_id, type_val, n_bytes)


        return (-1, _bytes if io._zip_type == 0 else io.zip(_bytes, zip_type=io._zip_type), n_bytes)

#
