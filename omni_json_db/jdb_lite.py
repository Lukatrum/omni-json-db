# pylint: disable=too-many-lines
from __future__ import annotations
from contextlib import contextmanager
from datetime import date as dt_date, datetime, timedelta
from re import compile as re_compile, search as re_search, findall as re_findall, match as re_match, Pattern, I as re_I, S as re_S
from os.path import exists as path_exists # basename, dirname, join as path_join
from threading import RLock, get_ident, Thread
from socketserver import TCPServer
from struct import Struct
from enum import IntFlag
from unicodedata import east_asian_width
from typing import Any, Union, Optional, Tuple, Set, Dict, Callable, Generator, IO
# from os import makedirs, stat as os_stat, getcwd
# from time import time
#-----------------------------------------------------------------------------
from .jdb_io import JIo, json_dumps, KEY_FILE_BUF_SIZE, VAL_FILE_BUF_SIZE # THE_1ST_DATE
from .jdb_file import JFilesBase, JMemFiles, JDiskFiles
from .jdb_net import JNetFiles, ThreadedTCPServer, ServerHandler
from .utils import FileLock, Style, JError, JKeyError, JValueError, JTypeError
# from .utils import debug_break
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
# from copy import deepcopy
#  __hash__ if type is immutable
def deepcopy(src):
    """
    Create a deep copy of the given object, optimized for immutable types.
    
    If the object has a valid `__hash__` (is immutable), it returns the object itself.
    Otherwise, it recursively copies dictionaries, sets, lists, and JDbReader instances.

    Args:
        src (Any): The source object to be deeply copied.

    Returns:
        Any: A deeply copied instance of the source object.
    """
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

SEP_SYM = ':::' # ignore to use re symbols (+-*?.{}()[]^$|\)
SEP_LEN = len(SEP_SYM)

FIND_OPS = {
    # MongoDB syntax
    'AND', 'NOT', 'OR', 'NOR',
    'IN', 'NIN', 'EQ', 'NE',
    'GT', 'LT', 'GTE', 'LTE',
    'SIZE', 'REGEX',
    # Not official
    'GE', 'LE','RE', 'RE2',
    'ANY', 'FUNC', 'HAS'
}

def run_files_server(host:str='127.0.0.1', port:int=59898, files:Union[str,bytearray,JFilesBase,JDbReader,None]=None, verbose:int=0) -> TCPServer:
    """
    Initialize and start a multi-threaded TCP server to allow external access to the JDb object.
    
    Args:
        host (str, optional): The host address for the server to listen on. Defaults to '127.0.0.1'.
        port (int, optional): The port number for the server to listen on. Defaults to 59898.
        files (Union[str, bytearray, JFilesBase, JDbReader, None], optional):
            The specified source for the database file:
                - str: Uses JMemFiles() if empty; otherwise, parses as JDiskFiles(path).
                - bytearray: Uses JMemFiles(KEY_file).
                - JFilesBase: Various file objects (JDiskFiles, JMemFiles, JNetFiles).
                - JDbReader: An existing JDbReader object.
                - None: Defaults to JMemFiles().
        verbose (int, optional): Logging verbosity level (-1: Off, 0: Limited, 1: Error, 2: Warning, 3: Info, 4: Debug). Defaults to 0.
    
    Returns
        TCPServer: The started TCP server instance.

    Raises:
        TypeError: Raised when the provided type for the files parameter is invalid.

    Examples
        >>> server = run_files_server(host='127.0.0.1', port=8080)
        >>> server.shutdown()
    """
    if files is None or isinstance(files, bytearray):
        files_obj = JMemFiles(files)
    elif isinstance(files, JDbReader): # pragma: no cover
        files_obj = files.files_obj
    elif isinstance(files, JFilesBase): # pragma: no cover
        files_obj = files
    elif isinstance(files, str):
        if re_match(r'^([12]?\d\d?[:.]){4}(?<=:)\d{1,5}$', files): # pragma: no cover
            server_ip, server_port = files.split(':')
            server_port = int(server_port)
            if not 65535 >= server_port > 0 or not all(255 > int(vv) >= 0 for vv in server_ip.split('.')):
                raise TypeError

            files_obj = JNetFiles((server_ip, server_port))
        else:
            files_obj = JDiskFiles(files) if files else JMemFiles()
    else:
        raise TypeError

    if not isinstance(files_obj, JFilesBase):
        raise TypeError

    print(f'staring server at {host}:{port} -> {files_obj} (files={type(files)})')
    server = ThreadedTCPServer((host, port), ServerHandler, files_obj=files_obj, verbose=verbose)
    thd = Thread(target=server.serve_forever, daemon=True)
    thd.start()
    return server

class JFlag(IntFlag):
    """
    Enumeration flag to control write/delete behavior in database operations.
    """

    REVERT  = 0x01  # allow to revert after write/delete operation
    SPLIT   = 0x02  # allow to split large row into two

    @classmethod
    def _missing_(cls, value):
        """
        Handle missing values by parsing string combinations into valid IntFlags.

        Args:
            value (Any): The string representation of flags.

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

            value = _value

        return super()._missing_(value)

    def __str__(self):
        """
        Return a string representation of the currently active flags.

        Returns:
            str: A string where each character represents an active flag's initial.
        """
        ret = ''
        for flag in JFlag:
            if flag in self:
                ret += flag.name[0]
            else:
                ret += '_'

        return ret

def _match_KEY_rules(key:str, rules:Any, level:int=0) -> bool:
    """
    Evaluate if a KEY matches a given set of conditions or MongoDB-like operators.

    Supports operations such as `$gt`, `$ge`, `$gte`, `$lt`, `$le`, `$lte`, `$eq`, `$ne`, `$in`, 
    `$has`, `$re`, `$re2`, `$func`, `$size`, `$not`, `$or`, `$nor` and `$and`.

    Args:
        key (str): The key associated with the value being evaluated.
        rules (Any): The dictionary of rules/operators or a direct match condition.
        level (int, optional): The current recursion depth. Defaults to 0.
    
    Returns:
        bool: True if the value satisfies all specified rules, False otherwise.

    Example:
        >>> rules = {'$has': 'ob'}
        >>> _match_KEY_rules("Bob", rules)
        True
        >>> _match_KEY_rules("Alice", {"$re": r"Al.*"})
        True
    """
    if not isinstance(rules, dict): # pragma: no cover
        if isinstance(rules, str):
            rules = {'$eq': rules}
        elif isinstance(rules, Pattern):
            rules = {'$re': rules}
        elif callable(rules):
            rules = {'$func': rules}
        elif isinstance(rules, (list, set, frozenset, tuple, range)):
            rules = {'$in': {str(_key) for _key in rules}}
        elif isinstance(rules, (int, float, bool, bytes, dt_date, datetime)):
            rules = {'$eq': str(rules)}
        else:
            return False

    for cmd,rule in rules.items():
        cmd = cmd.lower()
        if cmd == '$re' or cmd == '$re2' or cmd == '$regex':
            is_matched = False
            key_s = JSON_RE_sub('', key) if cmd[-1] == '2' else key
            if isinstance(rule, Pattern):
                is_matched = rule.search(key_s)

            elif isinstance(rule, str):
                is_matched = re_search(rule, key_s)

            elif isinstance(rule, (dict, list, tuple, set, frozenset)): # pragma: no cover
                # rule0 AND rule1 AND ...
                for _rule in rule:
                    if isinstance(_rule, Pattern):
                        if not _rule.search(key_s):
                            return False

                        is_matched = True

                    elif isinstance(_rule, str):
                        if not re_search(_rule, key_s):
                            return False

                        is_matched = True

                    else:
                        return False

            if is_matched:
                continue

        elif cmd == '$func':
            if callable(rule): # pragma: no cover
                arg_cnt = rule.__code__.co_argcount
                try:
                    if arg_cnt == 1 and rule(key):
                        continue

                except: # pragma: no cover
                    return False

        else:
            is_same_type = isinstance(rule, str)
            if cmd == '$gt':
                if is_same_type and key > rule:
                    continue

            elif cmd == '$gte' or cmd == '$ge':
                if is_same_type and key >= rule:
                    continue

            elif cmd == '$lt':
                if is_same_type and key < rule:
                    continue

            elif cmd == '$lte' or cmd == '$le':
                if is_same_type and key <= rule:
                    continue

            elif cmd == '$eq':
                if is_same_type and key == rule:
                    continue

            elif cmd == '$ne':
                if is_same_type and key != rule:
                    continue

            elif cmd == '$in':
                try:
                    if key in rule:
                        continue

                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$nin':
                try:
                    if not key in rule:
                        continue

                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$has':
                if isinstance(rule, str):
                    if key.find(rule) >= 0:
                        continue

            elif cmd == '$size':
                _len = len(key)
                if isinstance(rule, (float, int)):
                    if _len == int(rule):
                        continue

                elif isinstance(rule, (list, set, frozenset, tuple, range)):
                    if _len in rule:
                        continue

            elif cmd == '$not':
                if not _match_KEY_rules(key, rule, level=level+1):
                    continue

            elif cmd == '$or':
                if isinstance(rule, (list,tuple)):
                    is_matched = False
                    for _rule in rule:
                        if _match_KEY_rules(key, _rule, level=level+1):
                            is_matched = True
                            break

                    if is_matched:
                        continue

            elif cmd == '$nor':
                if isinstance(rule, (list,tuple)):
                    for _rule in rule:
                        if _match_KEY_rules(key, _rule, level=level+1):
                            return False
                    continue

            elif cmd == '$and':
                if isinstance(rule, (list,tuple)):
                    for _rule in rule:
                        if not _match_KEY_rules(key, _rule, level=level+1):
                            return False

                    continue

        return False

    return True

def _match_DATE_rules(cdate:dt_date, mdate:dt_date, rules:Any, level:int=0) ->bool:
    """
    Evaluate if a DATE matches a given set of conditions or MongoDB-like operators.

    Supports operations such as `$gt`, `$ge`, `$gte`, `$lt`, `$le`, `$lte`, `$eq`, `$ne`, `$in`, 
    `$has`, `$re`, `$re2`, `$func`, `$not`, `$or`, `$nor` and `$and`.

    Args:
        cdate (date): KEY created date
        mdate (date): KEY modified date
        rules (Any): The dictionary of rules/operators or a direct match condition.
        level (int, optional): The current recursion depth. Defaults to 0.
    
    Returns:
        bool: True if the value satisfies all specified rules, False otherwise.

    Example:
        >>> today = dt.date.today()
        >>> _match_DATE_rules(today, today, rules={'$eq': today})
        True        
    """
    if not isinstance(rules, dict): # pragma: no cover
        if isinstance(rules, (dt_date, datetime)):
            rules = {'$eq': rules}
        elif isinstance(rules, Pattern):
            rules = {'$re': rules}
        elif callable(rules):
            rules = {'$func': rules}
        elif isinstance(rules, (set, list, tuple)):
            rules = {'$in': rules}
        elif isinstance(rules, (frozenset, range)):
            rules = {'$in': set(rules)}
        elif isinstance(rules, str):
            matches = re_findall(r'(?<!\d)(\d{1,4})\W([01]?\d)\W([0123]?\d)(?!\d)', rules)
            if matches:
                date_list = []
                for dd in matches:
                    try:
                        date_list.append(dt_date(*[int(v) for v in dd]))
                    except ValueError: # pragma: no cover
                        return False

                if len(date_list) > 1:
                    date_list = sorted(date_list)
                    rules = {'$ge': date_list[0], '$le': date_list[-1]}
                elif date_list:
                    rules = {'$eq': date_list[0]}
                else:
                    return False
            else:
                return False
        elif isinstance(rules, (int, float)):
            today = dt_date.today() if isinstance(rules, int) else datetime.now()
            days = int(rules)
            if rules == 0:
                rules = {'$eq': today}
            elif rules > 0:
                rules = {'$ge': today, '$le': today + timedelta(days=days)}
            else:
                rules = {'$ge': today - timedelta(days=-days), '$le': today}
        else:
            return False

    cdate_s = str(cdate)
    mdate_s = str(mdate)
    date_s = f'{cdate_s} {mdate_s}'
    for cmd,rule in rules.items():
        cmd = cmd.lower()
        if cmd == '$func':
            if callable(rule):
                arg_cnt = rule.__code__.co_argcount
                try:
                    if arg_cnt == 2 and rule(cdate, mdate):
                        continue

                except: # pragma: no cover
                    return False

        elif cmd == '$re' or cmd == '$re2' or cmd == '$regex':
            is_matched = False
            date_s = JSON_RE_sub('', date_s) if cmd[-1] == '2' else date_s
            if isinstance(rule, Pattern):
                is_matched = rule.search(date_s)

            elif isinstance(rule, str):
                is_matched = re_search(rule, date_s)

            elif isinstance(rule, (dict, list, tuple, set, frozenset)): # pragma: no cover
                # rule0 AND rule1 AND ...
                for _rule in rule:
                    if isinstance(_rule, Pattern):
                        if not _rule.search(date_s):
                            return False

                        is_matched = True

                    elif isinstance(_rule, str):
                        if not re_search(_rule, date_s):
                            return False

                        is_matched = True

                    else:
                        return False

            if is_matched:
                continue

        else:
            is_cdate = isinstance(rule, datetime)
            is_mdate = isinstance(rule, dt_date) and not isinstance(rule, datetime)
            is_same_type = is_cdate or is_mdate
            if cmd == '$gt':
                if is_same_type and (is_cdate and cdate > rule.date() or is_mdate and mdate > rule):
                    continue

            elif cmd == '$gte' or cmd == '$ge':
                if is_same_type and (is_cdate and cdate >= rule.date() or is_mdate and mdate >= rule):
                    continue

            elif cmd == '$lt':
                if is_same_type and (is_cdate and cdate < rule.date() or is_mdate and mdate < rule):
                    continue

            elif cmd == '$lte' or cmd == '$le':
                if is_same_type and (is_cdate and cdate <= rule.date() or is_mdate and mdate <= rule):
                    continue

            elif cmd == '$eq':
                if is_same_type and (is_cdate and cdate == rule.date() or is_mdate and mdate == rule):
                    continue

            elif cmd == '$ne':
                if is_same_type and (is_cdate and cdate != rule.date() or is_mdate and mdate != rule):
                    continue

            elif cmd == '$in':
                try:
                    if isinstance(rule, set):
                        if mdate in rule or mdate_s in rule:
                            continue
                    else:
                        if cdate in rule or cdate_s in rule:
                            continue

                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$nin':
                try:
                    if isinstance(rule, set):
                        if not (mdate in rule or mdate_s in rule):
                            continue
                    else:
                        if not (cdate in rule or cdate_s in rule):
                            continue

                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$has':
                if isinstance(rule, str):
                    if date_s.find(rule) >= 0:
                        continue

                elif isinstance(rule, datetime):
                    if date_s.find(str(rule.date())) >= 0:
                        continue

                elif isinstance(rule, dt_date):
                    if date_s.find(str(rule)) >= 0:
                        continue

            elif cmd == '$not':
                if not _match_DATE_rules(cdate, mdate, rule, level=level+1):
                    continue

            elif cmd == '$or':
                if isinstance(rule, (list,tuple)):
                    is_matched = False
                    for _rule in rule:
                        if _match_DATE_rules(cdate, mdate, _rule, level=level+1):
                            is_matched = True
                            break

                    if is_matched:
                        continue

            elif cmd == '$nor':
                if isinstance(rule, (list,tuple)):
                    for _rule in rule:
                        if _match_DATE_rules(cdate, mdate, _rule, level=level+1):
                            return False
                    continue

            elif cmd == '$and':
                if isinstance(rule, (list,tuple)):
                    for _rule in rule:
                        if not _match_DATE_rules(cdate, mdate, _rule, level=level+1):
                            return False

                    continue

        return False

    return True

def _match_VAL_rules(key:str, val:Any, rules:Any, level:int=0, ANY:bool=False) -> bool:
    """
    Evaluate if a value matches a given set of conditions or MongoDB-like operators.

    Supports operations such as `$gt`, `$ge`, `$gte`, `$lt`, `$le`, `$lte`, `$eq`, `$ne`, `$in`, 
    `$has`, `$re`, `$re2`, `$regex`, `$func`, `$size`, `$not`, `$or`, `$nor` and `$and`.

    Args:
        key (str): The key associated with the value being evaluated.
        val (Any): The actual data value to be checked.
        rules (Any): The dictionary of rules/operators or a direct match condition.
        level (int, optional): The current recursion depth. Defaults to 0.
        ANY (bool, optional): If True, checks if any element in an iterable value matches. Defaults to False.

    Returns:
        bool: True if the value satisfies all specified rules, False otherwise.

    Example:
        >>> rules = {'$gt': 10, '$lt': 20}
        >>> _match_VAL_rules("age", 15, rules)
        True
        >>> _match_VAL_rules("name", "Alice", {"$re": r"Al.*"})
        True
    """
    if ANY and hasattr(val, '__iter__'): # pragma: no cover
        if isinstance(val, (list, set, frozenset, tuple)):
            if any(_match_VAL_rules(key, _val, rules, level=level+1, ANY=True) for _val in val):
                return True

        elif isinstance(val, dict):
            if any(_match_VAL_rules(key, _val, rules, level=level+1, ANY=True) for _val in val.values()):
                return True

    if not isinstance(rules, dict): # pragma: no cover
        if isinstance(rules, (str, int, float, bool, bytes)):
            rules = {'$eq': rules}
        elif isinstance(rules, Pattern):
            rules = {'$re': rules}
        elif callable(rules):
            rules = {'$func': rules}
        elif isinstance(rules, (list, set, tuple, frozenset)):
            rules = {'$in': set(rules)}
        elif isinstance(rules, (dt_date, datetime)):
            rules = {'$eq': rules}
        else:
            return False

    for cmd,rule in rules.items():
        if cmd and cmd[0] == '$':
            cmd = cmd.lower()
            is_same_type = isinstance(val, type(rule)) \
                or isinstance(val, (int, float, bool)) and isinstance(rules, (int, float, bool)) \
                or isinstance(val, (bytes, bytearray)) and isinstance(rules, (bytes, bytearray))

            if cmd == '$gt':
                try:
                    if not is_same_type or not val.__gt__ or not rule.__gt__ or not val > rule:
                        return False
                    continue
                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$gte' or cmd == '$ge':
                try:
                    if not is_same_type or not val.__ge__ or not rule.__ge__ or not val >= rule:
                        return False
                    continue
                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$lt':
                try:
                    if not is_same_type or not val.__lt__ or not rule.__lt__ or not val < rule:
                        return False
                    continue
                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$lte' or cmd == '$le':
                try:
                    if not is_same_type or not val.__le__ or not rule.__le__ or not val <= rule:
                        return False
                    continue
                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$eq':
                try:
                    if not is_same_type or not val.__eq__ or not rule.__eq__ or not val == rule:
                        return False
                    continue
                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$ne':
                try:
                    if not is_same_type or not val.__ne__ or not rule.__ne__ or not val != rule:
                        return False
                    continue
                except TypeError: # pragma: no cover
                    return False

            elif cmd == '$in':
                if hasattr(rule, '__contains__'):
                    try:
                        if val.__hash__ and not isinstance(val, (list, set, frozenset, tuple, range)):
                            if val not in rule:
                                return False
                            continue

                        if val.__iter__:
                            _set_a = set(rule) if not isinstance(rule, (set, frozenset)) else rule
                            _set_b = set(val) if not isinstance(val, (set, frozenset)) else val
                            if _set_a.intersection(_set_b) == _set_a:
                                continue

                    except TypeError: # pragma: no cover
                        return False

            elif cmd == '$nin':
                if hasattr(rule, '__contains__'):
                    try:
                        if val.__hash__ and not isinstance(val, (list, set, frozenset, tuple, range)):
                            if val in rule:
                                return False
                            continue

                        if val.__iter__:
                            _set_a = set(rule) if not isinstance(rule, (set, frozenset)) else rule
                            _set_b = set(val) if not isinstance(val, (set, frozenset)) else val
                            if _set_a - _set_b:
                                continue

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
                        val_s = val if isinstance(rule, bytes) else val.decode('utf8')
                    else:
                        val_s = json_dumps(val) if isinstance(val_s, bytes) else val_s.decode('utf8')

                except: # pragma: no cover
                    return False

                if isinstance(val_s, bytes) and isinstance(rule, bytes) \
                        or isinstance(val_s, str) and isinstance(rule, str):

                    if val_s.find(rule) >= 0:
                        continue

            elif cmd == '$re' or cmd == '$re2' or cmd == '$regex':
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

                if _rules:
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

                    val_s = JSON_RE_sub('', val_s) if cmd[-1] == '2' else val_s
                    for _rule in _rules:
                        if not _rule.search(val_s):
                            return False
                    continue

            elif cmd == '$func':
                if callable(rule): # pragma: no cover
                    arg_cnt = rule.__code__.co_argcount
                    try:
                        if arg_cnt == 2 and rule(key, val):
                            continue

                        if arg_cnt == 1 and rule(val):
                            continue

                    except: # pragma: no cover
                        return False

            elif cmd == '$size':
                if hasattr(val, '__iter__'):
                    _len = len(val)
                    if isinstance(rule, (float, int)):
                        if _len == int(rule):
                            continue

                    if isinstance(rule, (list, set, frozenset, tuple, range)):
                        if _len in rule:
                            continue

            elif cmd == '$not':
                if not _match_VAL_rules(key, val, rule, level=level+1):
                    continue

            elif cmd == '$or':
                if isinstance(rule, (list,tuple)):
                    is_matched = False
                    for _rule in rule:
                        if _match_VAL_rules(key, val, _rule, level=level+1):
                            is_matched = True
                            break

                    if is_matched:
                        continue

            elif cmd == '$nor':
                if isinstance(rule, (list,tuple)):
                    for _rule in rule:
                        if _match_VAL_rules(key, val, _rule, level=level+1):
                            return False
                    continue

            elif cmd == '$and':
                if isinstance(rule, (list,tuple)):
                    for _rule in rule:
                        if not _match_VAL_rules(key, val, _rule, level=level+1):
                            return False
                    continue

            elif cmd == '$any':
                is_matched = True
                if isinstance(val, dict):
                    if not any(_match_VAL_rules(key, _val, rule, ANY=True, level=level+1) for _val in val.values()):
                        is_matched = False

                elif not hasattr(val, '__iter__'):
                    if not _match_VAL_rules(key, val, rule, level=level+1):
                        is_matched = False

                elif isinstance(val, (list, set, frozenset, tuple, range)):
                    if not any(_match_VAL_rules(key, _val, rule, ANY=True, level=level+1) for _val in val):
                        is_matched = False

                else: # pragma: no cover
                    if not _match_VAL_rules(key, val, rule, level=level+1):
                        is_matched = False

                if not is_matched and isinstance(rule, dict):
                    _is_matched = False
                    if isinstance(val, dict):
                        for _ref, _rule in rule.items():
                            if _ref in val:
                                if _match_VAL_rules(key, val[_ref], _rule, level=level+1):
                                    _is_matched = True
                                    break

                    is_matched = True if _is_matched else is_matched

                if is_matched:
                    continue

            elif cmd[1:].isdigit():
                if isinstance(val, (list, tuple)):
                    try:
                        if _match_VAL_rules(key, val[int(cmd[1:])], rule, level=level+1):
                            continue

                    except IndexError: # pragma: no cover
                        return False

        elif isinstance(val, dict) and cmd in val:
            if _match_VAL_rules(key, val[cmd], rule, level=level+1):
                continue

        elif cmd == '_id':
            if _match_KEY_rules(key, rule, level=level):
                continue

        return False

    return True

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDbKey:
    """
    A lightweight, read-only interface for interacting strictly with the keys of a JDbReader instance.
    """
    __slots__ = {'jdb'}

    def __init__(self, jdb:JDbReader):
        """
        Initialize the JDbKey instance.

        Args:
            jdb (JDbReader): The parent database reader instance to bind to.
        """
        self.jdb:JDbReader = jdb

    def __repr__(self) -> str:
        """
        Return the string representation of the JDbKey instance.

        Returns:
            str: The object's memory address and class name.
        """
        return f'<{type(self).__name__} at {hex(id(self))}>'

    def __getitem__(self, key:Any) -> Union[dict,tuple,None]:
        """
        Retrieve key metadata or filter keys based on a variety of condition types.

            Args:
                key (Any): The filter criteria which can be a string, slice, date, regex pattern, function, or iterable.
                    - str | bool | bytes
                        - val = jdb.keys['name']

                    - slice | date | datetime | float | int
                        >>> matches = jdb.keys[date(2020,1,1)::r'key[0-9]'] # get date from 2020-1-1 to now key and match r'key[0-9]'
                        >>> matches = jdb.keys[:100:r'key[0-9]'] # get 1-100th row keys and match r'key[0-9]'
                        >>> matches = jdb.keys[date.today()]     # get today modified/new keys
                        >>> matches = jdb.keys[datetime.now()]   # get today new keys
                        >>> matches = jdb.keys[1:10:2]   # get 2nd - 9th and step=2 key info
                        >>> matches = jdb.keys[-10.:]    # get key info and match sync_id
                        >>> matches = jdb.keys[:]        # get all key info
                        >>> matches = jdb.keys[0]        # get 1st key info
                        >>> matches = jdb.keys[-1]       # get last key info
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
                Union[dict, tuple, None]: Metadata tuple if a single string is passed, or a dictionary of matched keys to their metadata.
        """
        if isinstance(key, str):
            if key.find(SEP_SYM) >= 0 and key not in self.jdb:
                # pylint: disable=unnecessary-comprehension
                return {k:v for k,v in self.item_iter(key)}

        elif isinstance(key, (bytes, bytearray)): # pragma: no cover
            key = bytes(key) if isinstance(key, bytearray) else key
            try:
                key = key.decode('utf8')
            except (UnicodeDecodeError, ValueError):
                key = str(key)

        elif isinstance(key, (int, float, slice, dt_date, datetime, Pattern)) \
                or callable(key) \
                or hasattr(key, '__iter__'):
            # pylint: disable=unnecessary-comprehension
            return {k:v for k,v in self.item_iter(key)}

        jdb = self.jdb
        with jdb.open(read_only=True) as fp:
            io, fp, key_fp = jdb.f_get_fp(fp)
            key = str(key) if not isinstance(key, str) else key
            row_id = io.key_table[key]
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
        """
        Get the total number of records in the associated database.

        Returns:
            int: The record count.
        """
        return len(self.jdb)

    def __call__(self, keys:Optional[Any]=None, vals:Optional[Any]=None, date:Optional[Any]=None, limit:int=0, **kwargs) -> Generator[str]:
        """
        Execute a search query returning matching keys or key-metadata pairs as a generator.

        Args:
            keys (Optional[Any], optional): Condition for filtering keys. Defaults to None.
            vals (Optional[Any], optional): Condition for filtering values. Defaults to None.
            date (Optional[Any], optional): Date range filter. Defaults to None.
            limit (int, optional): Maximum number of results to yield. Defaults to 0 (no limit).
            **kwargs: Additional filtering arguments.

        Yields:
            str: Matched key

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
            for key, _val in jdb.find_iter(keys=keys, vals=vals, date=date, limit=limit, with_value=False, **kwargs):
                yield key

        else:
            yield from self

    def __iter__(self) -> Generator[str]:
        """
        Iterate over all keys present in the database.

        Yields:
            str: The next key in the database.
        """
        jdb = self.jdb
        with jdb.open(read_only=True):
            yield from jdb.io.key_table

    def __contains__(self, keys:Set[str]) -> bool:
        """
        Check if the current key table is a superset of the provided keys.

        Args:
            keys (Set[str]): A set of keys to check.

        Returns:
            bool: True if all provided keys exist in the database, False otherwise.

        Example:
            >>> jdb = JDb()
            >>> jdb['user_1', 'user_2', 'user_3'] = 0
            >>> {'user_1', 'user_2'} in jdb.keys
            True
        """
        return self.is_superset(keys)

    def __eq__(self, keys:Union[set,dict,JDbReader,JDbKey]) -> bool:
        """
        Compare the current keys with another collection or database.

        Args:
            keys (Union[set, dict, JDbReader, JDbKey]): The target to compare against.

        Returns:
            bool: True if the keys are identical, False otherwise.
        
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
        Find keys that are strictly in this database but not in the provided set.

        Args:
            keys (Set[str]): The set of keys to exclude.

        Returns:
            Set[str]: The set of non-joint keys.
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

    def item_iter(self, key:Optional[Any]=None) -> Generator[str,tuple]:
        """
        Iterate over keys and their corresponding metadata tuples based on filter criteria.

        Args:
            key (Optional[Any], optional): Filtering criteria (slice, date, regex, etc.). Defaults to None.

                - str | bool | bytes
                    >>> matches = jdb.keys['name']
                    >>> matches = jdb.key['child:::name']
                    >>> matches = jdb.key[':::name']

                - int
                    >>> matches = jdb.keys[1]             # get 2nd line row key info
                    >>> matches = jdb.keys[-1]            # get last line row key info

                - float
                    >>> matches = jdb.keys[-1.]      # get all key info which sync_id is matched

                - slice | date | datetime
                    >>> matches = jdb.keys[date(2020,1,1)::r'key[0-9]'] # get date from 2020-1-1 to now key and match r'key[0-9]'
                    >>> matches = jdb.keys[:100:r'key[0-9]'] # get 1-100th row keys and match r'key[0-9]'
                    >>> matches = jdb.keys[date.today()]     # get today modified/new keys
                    >>> matches = jdb.keys[datetime.now()]   # get today new keys
                    >>> matches = jdb.keys[1:10:2]   # get 2nd - 9th and step=2 key info
                    >>> matches = jdb.keys[-10.:]    # get key info and match sync_id
                    >>> matches = jdb.keys[:]        # get all key info

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
            Tuple[str, tuple]

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
                raise TypeError('invalid function {k_arg_cnt}')

        else:
            is_matched = None
            k_arg_cnt = 0
            key = slice(0,None) if key is None else key

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
                    io_read_key = io.read_key
                    io_conv_date = io.z_conv_date
                    n_records = io.n_records
                    for row_id in range(io.n_records):
                        _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                        if ver == sync_id:
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
                        if is_matched(_key, val):
                            yield _key, val

                elif k_arg_cnt == 1:
                    for _key,row_id in io.key_table.items():
                        if io.n_records > row_id >= 0 and is_matched(_key):
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
                    if _key not in done: # pragma: no cover
                        done.add(_key)
                        row_id = key_table[_key]
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
            row_id = io.key_table[key]
            if io.n_records > row_id >= 0:
                _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                old_date, new_date = io.z_conv_date(days)
                yield _key, (row_id, file_id, offset, size, vsize, ver, days, str(new_date), str(old_date))

    def items(self) -> Generator[str,tuple]:
        """
        Iterate over all keys and their metadata tuples.

        Yields:
            Tuple[str, tuple]
            
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

    def values(self) -> Generator[tuple]:
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

        self.files_obj:JFilesBase = files_obj
        self.file_lock:FileLock = FileLock(files_obj)
        self.lock = RLock() # solve iter issue [cannot use Lock]
        self.fsize = self.safe_line = 0
        self.childs:Dict[str,JDbReader] = {}
        self.fp_table:Dict[int,dict] = {}
        self.chg_keys:Set = set()
        self._cache:Dict[str,Any] = {}
        self._cache_limit = cache_limit
        if JDbKey_obj is None:
            self.keys:JDbKey = JDbKey(self)
        else:
            self.keys:JDbKey = JDbKey_obj

        self.write_hook = write_hook
        self.flags:JFlag = flags
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
                        if fp is None:
                            continue

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
        Get the current number of valid records in the database.

        Returns:
            int: Total record count.
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

    def __iter__(self) -> Generator[str]:
        """
        Iterate over the keys present in the database.

        Yields:
            str: A database key.
        """
        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True):
            yield from self.io.key_table

    def __getitem__(self, key:Set[str]) -> Union[Dict[str,Any],Any]:
        """
        Retrieve data by key or filter data dynamically.

        Args:
            key (Set[str]): The identifier or condition mapping to locate specific values.
                
                - str | int | float | bool | bytes
                    >>> val = jdb['name']

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

                - tuple | se | list | dict
                    >>> data = jdb[1, 2, 3, 'a']
                    >>> data = jdb[(1, 2, 3, 'a')]
                    >>> data = jdb[{1, 2, 3, 'a'}]
                    >>> data = jdb[[1, 2, 3, 'a']]
                    >>> data = jdb[{1:0, 2:1, 3:2, 'a':3}]

        Returns:
            Union[Dict[str, Any], Any]: The target value, or a dictionary of matched keys and values.
                
                - dict: mutliple keys with value
                - Any: target key's value        
        """
        if isinstance(key, str):
            if key.find(SEP_SYM) >= 0:
                with self.open(read_only=True):
                    if key not in self.io.key_table:
                        # pylint: disable=unnecessary-comprehension
                        return {k:v for k,v in self.item_iter(key)}

        elif isinstance(key, (bytes, bytearray)): # pragma: no cover
            key = bytes(key) if isinstance(key, bytearray) else key
            try:
                key = key.decode('utf8')
            except (UnicodeDecodeError, ValueError):
                key = str(key)

        elif isinstance(key, (slice, dt_date, datetime, Pattern)) \
                or callable(key) \
                or hasattr(key, '__iter__'):

            # pylint: disable=unnecessary-comprehension
            return {k:v for k,v in self.item_iter(key)}

        # str | bytes | int | float | bool
        with self.open(read_only=True) as fp:
            return self.f_read(fp, key, copy=True)

    def __contains__(self, keys:Set[str]) -> bool:
        """
        Check if the current key table is a superset of the provided keys.

        Args:
            keys (Set[str]): A set of keys to check.

        Returns:
            bool: True if all provided keys exist in the database, False otherwise.

        Example:
            >>> jdb = JDb()
            >>> jdb['user_1', 'user_2', 'user_3'] = 0
            >>> {'user_1', 'user_2'} in jdb
            True
        """
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
                    for key,row in self.io.sorted_key_table_items():
                        ref_row = jdb_key_table[key]
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

    def f_slice(self, fp_dict:dict, key:Union[dt_date,datetime,Any]) -> tuple:
        """
        Compute row and version iteration boundaries for a given slice or datetime constraint.

        Args:
            fp_dict (dict): Active file pointer dictionary.
            key (Union[dt_date, datetime, Any]): The time or slice specification for filtering.

        Returns:
            tuple: A tuple containing (slice_obj, max_ver, min_ver, max_date, min_date, filter_re, chk_new_date).
        """
        chk_new_date = True
        if isinstance(key, datetime):
            key = slice(key, key+timedelta(days=1)) # created date
            chk_new_date = False

        elif isinstance(key, dt_date):
            key = slice(key, key+timedelta(days=1)) # modified date

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

            elif isinstance(_start, datetime):
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

            elif isinstance(_stop, datetime):
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
        """Explicitly initialize and acquire transaction streams allocated to internal pools.

        Args:
            read_only (bool, optional): If True, grabs shared reading channels. 
                Otherwise requests exclusive system control flags. Defaults to True.

        Returns:
            Dict[int, IO]: Table tracking open IO objects bound to current thread session.
        """
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

                    io.read_header(key_fp)
                    if not io.is_updated() or not is_latest: # pragma: no cover
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
        """Flush pending changes and systematically decouple file streams handles registers."""
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

                            self.fsize = io.write_header(key_fp)

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
        """
        Context manager to acquire thread-safe read/write access to the database files.

        Args:
            read_only (bool, optional): Whether to request a shared read lock vs exclusive write lock. Defaults to True.
            no_raise (bool, optional): If True, suppresses exceptions and attempts to reset corrupted DB headers. Defaults to False.

        Yields:
            Dict[int, IO]: A dictionary of open file pointers.
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
            fp_table[ident] = fp_dict = fp_table.get(ident, {-1:None})
            io = self.io
            try:
                try:
                    if read_only:
                        if io.is_updated():
                            if files_obj.KEY_size() == io.file_size:
                                sync_id = io.sync_id
                                fsize = io.file_size
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

                    io.read_header(key_fp)
                    if not io.is_updated() or not is_latest:
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
                    fsize = io.file_size
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
        """
        Context manager explicitly for opening and accessing the KEY structure file safely.

        Args:
            read_only (bool, optional): Access mode request. Defaults to True.

        Yields:
            IO: The file pointer for the KEY table storage.
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
        """
        Get the parent directory path of the primary DB file.

        Returns:
            str: Directory path.
        """
        return self.files_obj.get_folder()

    @property
    def file_name(self) -> str:
        """
        Get the file name of the primary DB KEY file.

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
        Access the loaded dictionary mapping keys to their exact line row numbers.

        Returns:
            Dict[str, int]: Key table map.
        """
        return self.io.key_table

    @property
    def file_table(self) -> Dict[int,int]:
        """Get the internal file mapping metadata database table.

        Returns:
            Dict[int, int]: A dictionary mapping file segment IDs to current offsets.
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
        """Get the total row line count inside the structural index file.

        Returns:
            int: Total logical index rows, including dead and deleted entries.
        """
        return self.io.n_lines

    @property
    def index_size(self) -> int:
        """Get the allocated storage byte size of an individual index block row.

        Returns:
            int: Number of fixed allocation bytes per index.
        """
        return self.io.index_size

    @property
    def reserved_rate(self) -> int:
        """Get the padding reserve multiplier allocated for runtime object drift expansion.

        Returns:
            float: Pre-allocation expansion reservation rate.
        """
        return self.io.reserved_rate

    @property
    def min_value_size(self) -> int:
        """Get the minimum floor alignment constraint for data segment storage arrays.

        Returns:
            int: Minimal byte width allocation limit.
        """
        return self.io.min_value_size

    @property
    def sync_id(self) -> int:
        """Get the master execution tracking generation version sequence signature.

        Returns:
            int: Current synchronization session sequence value number.
        """
        return self.io.sync_id

    @property
    def swap_id(self) -> int:
        """Get the compact sequence reference ID utilized during index storage updates.

        Returns:
            int: Garbage collection lifecycle phase index tracker.
        """
        return self.io.swap_id

    @property
    def remv_id(self) -> int:
        """Get the total deletion count sequence identifier used for data tracking.

        Returns:
            int: Counter indicating total deleted element lines.
        """
        return self.io.remv_id

    @property
    def api_ver(self) -> int:
        """Get the physical structural schema iteration version of the engine binary interface.

        Returns:
            int: Underlying logical structural iteration identification value.
        """
        return self.io.api_ver

    @property
    def data_type(self) -> str:
        """Get the format encoding specification string token representing the engine layout.

        Returns:
            str: Operational data schema classification code string (e.g., 'J+S').
        """
        return self.io.data_type_str

    @property
    def zip_type(self) -> str:
        """Get the active algorithm code string indicating row-level compression profile rules.

        Returns:
            str: Compression blueprint nomenclature code string (e.g., 'zs', 'no').
        """
        return self.io.zip_type_str

    @property
    def key_limit(self) -> str:
        """Get the operational threshold rule limiting active reference cache structures.

        Returns:
            str: Tracking limits context operational string code.
        """
        return self.io.key_limit_str

    @key_limit.setter
    def key_limit(self, value:Union[int,str]):
        """Set the key indexing boundary parameters dynamically with thread lock boundaries.

        Args:
            value (Union[int, str]): New indexing tracking restriction code string or integer size.
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
        """Extract the exact active record count by checking core filesystem headers directly.

        Returns:
            int: Number of live unique records verified on device layer.
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

    def create_jdb(self, KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None], **kwargs) -> JDbReader:
        """Spawn a relative reader instance sharing configuration models matching local presets.

        Args:
            KEY_file (Union[str, bytearray, JFilesBase, JDbReader, None]): Direct target path or source buffer.
            **kwargs: Extra overrides for instance parameters.

        Returns:
            JDbReader: A newly spawned reader environment reference.
        """
        return JDbReader(KEY_file=KEY_file, **kwargs)

    def can_lock(self) -> bool:
        """Validate if the storage medium filesystem architecture supports isolation parameters control.

        Returns:
            bool: True if locks can be safely managed, False otherwise.
        """
        if not self.lock.acquire(): # pylint: disable=consider-using-with
            return False

        try:
            return self.file_lock.can_lock()

        except: # pragma: no cover
            return False

        finally:
            self.lock.release()

    def non_joint(self, keys:Set[str]) -> Set[str]:
        """Compute the relative difference containing items unique to this instance.

        Args:
            keys (Set[str]): Comparison collection base criteria target.

        Returns:
            Set[str]: The resulting asymmetric difference subset array.
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
        """Find overlapping keys existing symmetrically between database space and criteria sets.

        Args:
            keys (Set[str]): Query tracking indicators set.

        Returns:
            Set[str]: Intersected structural keys slice.
        """
        return self.intersection(keys)

    def union(self, keys:Set[str]) -> Set[str]:
        """Aggregate local tracking records together with external target collection frames.

        Args:
            keys (Set[str]): Collection items to incorporate into query results.

        Returns:
            Set[str]: Complete combination matrix unique elements array.
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
        """Intersect internal active index dictionary indices against query sequences fields.

        Args:
            keys (Set[str]): Cross-reference set to check items matching domain rules.

        Returns:
            Set[str]: Shared element set output.
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
        """Isolate nodes that evaluate unique to either target dataset boundaries.

        Args:
            keys (Set[str]): Target comparison index space.

        Returns:
            Set[str]: Computed symmetric difference tracking array.
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
        """Standard alias routing directly onto the non_intersection layout method.

        Args:
            keys (Set[str]): Target values mapping sets to isolate.

        Returns:
            Set[str]: Unique divergent components layout map.
        """
        return self.non_intersection(keys)

    def difference(self, keys:Set[str]) -> Set[str]:
        """Exclude entries from native collection sets which match entries provided in inputs parameters.

        Args:
            keys (Set[str]): Elements to strip away from internal arrays indices.

        Returns:
            Set[str]: Filtered difference array output.
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
        """Determine if every key inside an external collection exists in the local collection.

        Args:
            keys (Set[str]): Target slice layout candidates to cross-verify.

        Returns:
            bool: True if local structures envelope all values inside inputs, False otherwise.
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
        """Determine if local elements exist fully nested within a broader external pool space.

        Args:
            keys (Set[str]): Broader parent context set.

        Returns:
            bool: True if completely nested, False if any unique outlier is found.
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
        """Confirm if there are zero intersecting items common between tracking layers.

        Args:
            keys (Set[str]): External evaluation frame array.

        Returns:
            bool: True if overlap evaluates empty, False if items are shared.
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
        """Check key presence strictly within local fast lookup caches avoiding heavy execution locks.

        Args:
            key (str): Target dictionary lookup query string.

        Returns:
            bool: True if active memory cache recognizes item reference, False otherwise.
        """
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

    def values(self) -> Generator[Any]:
        """Generate object values decoded directly from sequential segments records data blocks.

        Yields:
            Any: The unpacked deserialized python object row mapping.
        """
        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True) as fp:
            f_read = self.f_read
            for key,row in self.io.key_table.items():
                yield f_read(fp, key, row=row, copy=False)

    def items(self, read_only:bool=True) -> Generator[str,Any]:
        """Generate structured key-value maps pairs extracted from indices tables.

        Args:
            read_only (bool, optional): Engage shared serialization pipes logic optimization. Defaults to True.

        Yields:
            Tuple[str, Any]: A structural tuple pair associating key name strings with content values.
        """
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
        """Iterate entities across datasets utilizing customizable indexing, criteria lambdas or slices parameters.

        Args:
            key (Optional[Any], optional): Query target constraint layer rule. Defaults to None.

                - re.Pattern
                - function(k) | function(k,v)
                - str: record name
                - int: record index                
                - float: records sync ID
                - bytes | bytearray | bool
                - slice | date | datetime
                - list | tuple | set | dict

        Yields:
            Tuple[str, Any]: Matching target values aligned with identity descriptors records fields.
        """

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

            if isinstance(key, int) and not isinstance(key, bool):
                n_records = io.n_records
                row_id = (n_records + key) if key < 0 else key
                if n_records > row_id > 0:
                    _key, file_id, offset, size, vsize, ver, days = io.read_key(key_fp, row_id)
                    yield _key, self.f_read(fp, _key, row=row_id, copy=False)

                return

            if isinstance(key, float):
                sync_id = int(key)
                sync_id = (io.sync_id + sync_id) if sync_id < 0 else sync_id
                if not (sync_id >= io.sync_id or sync_id < 0):
                    io_read_key = io.read_key
                    n_records = io.n_records
                    for row_id in range(n_records):
                        _key, file_id, offset, size, vsize, ver, days = io_read_key(key_fp, row_id)
                        if ver == sync_id:
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
                        if is_matched(_key, val):
                            yield _key, val

                elif k_arg_cnt == 1:
                    for _key,row_id in io.key_table.items():
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
                key_table = io.key_table
                has_childs = len(io.groups) > 0 or len(self.childs) > 0
                for _key in key:
                    _key = str(_key)
                    if _key not in done:
                        done.add(_key)

                        row_id = key_table[_key]
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
            row_id = io.key_table[key]
            if row_id >= 0:
                yield key, self.f_read(fp, key, row=row_id, copy=False)

    def find_iter(self, keys:Optional[Any]=None, vals:Optional[Dict[str,Any]]=None, date:Optional[Any]=None, limit:int=0, with_value:bool=False, **kwargs) -> Generator[Tuple[str,Any]]:
        """
        Iterate over the database records yielding key-value pairs matching complex query criteria.

        Args:
            keys (Optional[Any], optional): Pattern, function, or string key matches.
                
                >>> jdb.find(re.compile(r'Jo(e|hn)')) == jdb.find(r'Jo(e|hn)')
                >>> jdb.find(lambda k: k[-1] == 'n')

            vals (Optional[Dict[str, Any]], optional): Dictionary of value constraint operators (e.g., {'$gt': 10}).                
                
                >>> jdb.find(GT=12) == dict(jdb.find_iter(vals={'$gt':12})) # value > 12
                >>> jdb.find(GTE=12) == dict(jdb.find_iter(vals={'$gte':12})) # value >= 12
                >>> jdb.find(GE=12) == dict(jdb.find_iter(vals={'$ge':12})) # value >= 12
                >>> jdb.find(LT=12) == dict(jdb.find_iter(vals={'$lt':12})) # value < 12
                >>> jdb.find(LTE=12) == dict(jdb.find_iter(vals={'$lte':12})) # value <= 12
                >>> jdb.find(LE=12) == dict(jdb.find_iter(vals={'$le':12})) # value <= 12
                >>> jdb.find(EQ=12) == dict(jdb.find_iter(vals={'$eq':12})) # value == 12
                >>> jdb.find(NE=12) == dict(jdb.find_iter(vals={'$ne':12})) # value != 12
                >>> jdb.find(EQ='Joe') == dict(jdb.find_iter(vals={'$eq':'Joe'})) # value == "Joe"
                >>> jdb.find(NE='Joe') == dict(jdb.find_iter(vals={'$ne':'Joe'})) # value != "Joe"
                >>> jdb.find(RE=r'Jo(hn|e)') == dict(jdb.find_iter(vals={'$re':'Jo(hn|e)'})) # re.search(r'Jo(hn|e)', value)
                >>> jdb.find(HAS=12) == dict(jdb.find_iter(vals={'$has':12})) # 12 in value
                >>> jdb.find(IN=[1,2]) == dict(jdb.find_iter(vals={'$in':[1,2]})) # value in [1,2]
                >>> jdb.find(NIN=[1,2]) == dict(jdb.find_iter(vals={'$nin':[1,2]})) # value not in [1,2]
                >>> jdb.find(FUNC=lambda k,v: v == 1) == dict(jdb.find_iter(vals={'$func':lambda k,v: v == 1}))
                >>> jdb.find(AND=[{'name':'A'}, {'age':{'$gte':20}}]) # value['name'] == 'A' and value['age'] >= 20
                >>> jdb.find(OR=[{'name':'A'}, {'age':{'$ge':20}}]) # value['name'] == 'A' or value['age'] >= 20
                >>> jdb.find(NOR=[{'name':'A'}, {'age':{'$gte':20}}]) # value['name'] != 'A' and value['age'] < 20
                >>> jdb.find(NOT={'name':'A'}}]) # not value['name] == 'A'
                >>> jdb.find(ANY='A')  # any record's value equal to  'A'
                
            date (Optional[Any], optional): Timeline constraint for record modifications.
            limit (int, optional): Max results to return. 0 means unlimited. Defaults to 0.
            with_value (bool, optional): Whether to decode and return the actual value, or just None. Defaults to False.
            **kwargs: Extra filter configurations (e.g., regex flags).

        Yields:
            Tuple[str, Any]: Matching key and its associated value (or None if `with_value` is False).

        Example:

            >>> jdb.find_iter(vals={'$eq': "value"})
            >>> jdb.find_iter(EQ="value")
            >>> jdb.find_iter(vals={'$in': ["value1", "value2"]})
            >>> jdb.find_iter(IN=["value1", "value2"])
            >>> jdb.find_iter(NIN=["value1", "value2"])
            >>> jdb.find_iter(vals={'$func': lamdba value:value == "any"})
            >>> jdb.find_iter(FUNC=lambda value:value == "any")
            >>> jdb.find_iter(FUNC=lambda key,val:val == "any")
            >>> jdb.find_iter(r'^[Rr].*[Nn]$', IN=[8,27])
            >>> jdb.find_iter(r'^[Rr].*[Nn]$', NIN=[8,27])
            >>> jdb.find_iter(keys=[r'^[Rr]', r'[Nn]$'], vals={'$in' : [8, 27]})
            >>> jdb.find_iter(keys=[r'^[Rr]', r'[Nn]$'], vals={'$gt' : 8, '$lt' : 100})
            >>> jdb.find_iter(keys=[r'^[Rr]', r'[Nn]$'], vals={'$or' : {'$eq' : 8, '$lt' : 50}})
            >>> jdb.find_iter(vals={'name' : r'Jo(e|hn)'}, re_flags=re.I)
            >>> jdb.find_iter(ANY='name')
            >>> jdb.find_iter(vals={'$any' : r'name'})
            >>> jdb.find_iter(vals={'$any' : {'$re' : r'name'}})
            >>> jdb.find_iter(vals={'$or': [{'name1':{'$eq':'value1'}, {'name2':{'$eq':'value2'}}])
            >>> jdb.find_iter(OR=[{'name1':{'$eq':'value1'}, {'name2':{'$eq':'value2'}}])
            >>> jdb.find_iter(NOR=[{'name1':{'$eq':'value1'}, {'name2':{'$eq':'value2'}}])
            >>> jdb.find_iter(vals={'$and': [{'age':{'$gt':0}, {'age':{'$lte':100}}])
            >>> jdb.find_iter(AND=[{'age':{'$gt':0}, {'age':{'$lte':100}}]) # 100 >= age >= 0
            >>> jdb.find_iter(vals={'$not: {'$eq':'value1'})
            >>> jdb.find_iter(NOT={'$eq':'value1'}) # find_iter(NE='value1')
        """
        re_flags = kwargs.get('re_flags', re_I)

        if not vals: vals = {}

        for key,val in kwargs.items():
            if key in FIND_OPS:
                vals[f'${key.lower()}'] = val

        if vals:
            with_value = True

        if not keys: keys = {}

        if isinstance(keys, dict):
            pass

        elif isinstance(keys, Pattern):
            keys = {'$re': keys}

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
                    io = self.io
                    key_table = io.key_table
                    childs = set(self.childs).union(io.groups)
                    f_get_child = self.f_get_child
                    for child_name in childs:
                        if child_name not in key_table: continue
                        if not (key_rule and not key_rule.search(child_name)):
                            child = f_get_child(fp, child_name)
                            if isinstance(child, JDbReader):
                                for kk,vv in child.find_iter(next_keys, vals=vals, date=date, limit=limit, with_value=with_value, **kwargs):
                                    yield child_name+SEP_SYM+kk,vv
                return

            keys = {'$re': re_compile(keys, flags=re_flags)}

        elif isinstance(keys, (bytes, bytearray)): # pragma: no cover
            keys = bytes(keys) if isinstance(keys, bytearray) else keys
            try:
                keys = {keys.decode('utf8')}
            except (UnicodeDecodeError, ValueError):
                keys = {str(keys)}

        elif hasattr(keys, '__iter__'):
            keys = {'$in': {key if isinstance(key, str) else str(key) for key in keys}}

        elif callable(keys):
            keys = {'$func': keys}

        if not isinstance(keys, dict):  # pragma: no cover
            raise TypeError('invalid type')

        # pylint: disable=contextmanager-generator-missing-cleanup
        with self.open(read_only=True) as fp:
            io, fp, key_fp = self.f_get_fp(fp)
            count = 0
            io_read_key = io.read_key
            io_conv_date = io.z_conv_date
            data_type = io.data_type_str
            cache = self._cache
            for key,row_id in io.sorted_key_table_items():
                if count >= limit > 0:
                    break

                is_matched = True
                for cmd,rules in keys.items():
                    if _match_KEY_rules(key, {cmd: rules}):
                        continue

                    is_matched = False
                    break

                if not is_matched:
                    continue

                if date is not None:
                    key, _file_id, _offset, _row_size, _val_size, _ver, _days =  io_read_key(key_fp, row_id)
                    cdate, mdate = io_conv_date(_days)
                    if not _match_DATE_rules(cdate, mdate, date):
                        continue

                if not with_value:
                    yield key, None
                    count += 1
                    continue

                if key not in cache:
                    value, value_b = self.f_read_with_bytes(fp, key)
                else:
                    value = cache.get(key, None)
                    value_b = None

                for cmd,rules in vals.items():
                    cmd = cmd.lower()
                    use_bytes = False
                    if cmd == '$eq' or cmd == '$ne':
                        use_bytes = isinstance(rules, bytes) and not isinstance(value, bytes)

                    elif cmd == '$has':
                        use_bytes = isinstance(rules, bytes) and not isinstance(value, bytes) \
                                    or isinstance(rules, str) and data_type.endswith('J')

                    elif cmd == '$re' or cmd == '$re2' or cmd == '$regex':
                        use_bytes = data_type.endswith('J')

                    if use_bytes:
                        if value_b is None:
                            try:
                                value_b = io.VAL_dumps(value)
                            except ValueError: # pragma: no cover
                                value, value_b = self.f_read_with_bytes(fp, key)

                        _value = value_b
                    else:
                        _value = value

                    if not _match_VAL_rules(key, _value, {cmd: rules}):
                        is_matched = False
                        break

                if is_matched:
                    yield (key, value)
                    count += 1

    def map(self, map_func:Callable[[str,Any],Any], keys:Optional[Any]=None, vals:Optional[Any]=None, date:Union[str,datetime,dt_date,int,None]=None, sort:int=0, **kwargs) -> list:
        """
        Apply a mapping function to the results of a query and return a list.

        Args:
            map_func (Callable[[str, Any], Any]): The lambda or function to process (key, value) pairs.
            keys (Optional[Any], optional): Key criteria.
            vals (Optional[Any], optional): Value criteria.
            date (Union[str, datetime, dt_date, int, None], optional): Date criteria.
            sort (int, optional): Sort direction flag.
            **kwargs: Extra find arguments.

        Returns:
            list: Transformed list of objects returned by map_func.
        """
        if not callable(map_func):
            raise TypeError('not callable')

        matches = []
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, with_value=True, **kwargs):
            matches.append(map_func(key, val))

        if sort:
            return sorted(matches, reverse=sort<0, **kwargs)

        return matches

    def find(self, keys:Optional[Any]=None, vals:Optional[Dict[str,Any]]=None, date:Optional[Any]=None, limit:int=0, with_value:Optional[bool]=None, sort:int=0, **kwargs) -> Dict[str,Any]:
        """
        Find and return a dictionary of records matching complex query criteria.

        Args:
            keys (Optional[Any], optional): Condition for key filtering.
            vals (Optional[Dict[str, Any]], optional): Condition for value filtering using operators.
            date (Optional[Any], optional): Date filters.
            limit (int, optional): Maximum item cap. Defaults to 0.
            with_value (Optional[bool], optional): Whether to read the key's value. Defaults to False.
            sort (int, optional): Sorting direction (1 for ascending, -1 for descending, 0 for unsorted). Defaults to 0.

        Returns:
            Dict[str, Any]: The subset of matched data.
        """
        if with_value is None:
            with_value = not (not vals and not kwargs and sort == 0)

        matches = {}
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, limit=limit, with_value=with_value, **kwargs):
            matches[key] = val

        if len(matches) > 1 and sort != 0:
            return dict(sorted(matches.items(), key=lambda v : v[1], reverse=sort<0))

        return matches

    def show(self, keys:Optional[Any]=None, vals:Optional[Dict[str,Any]]=None, date:Optional[Any]=None, limit:int=20, **kwargs) -> Dict[str,Any]:
        """
        show matched key+value in table.

        Args:
            keys (Optional[Any], optional): Condition for key filtering.
            vals (Optional[Dict[str, Any]], optional): Condition for value filtering using operators.
            date (Optional[Any], optional): Date filters.
            limit (int, optional): +ve matched item. 0=all matched items (default=20)

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

        data_rows = []
        for key,val in self.find_iter(keys=keys, vals=vals, date=date, limit=limit, with_value=True, **kwargs):
            data_rows.append((key, val))

        fields = ['_id']
        patterns = {'_id'}
        for _key, val in data_rows:
            if isinstance(val, dict):
                kk = '|'.join(val)
                if kk not in patterns:
                    patterns.add(kk)
                    for kk in val:
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

        def _format_cell(val:Any) -> str:
            if val is None:
                return ""

            if isinstance(val, str):
                return val

            if isinstance(val, (int, float, bool, bytes, bytearray)):
                return str(val)

            return f"<{type(val).__name__}>"

        def _get_display_width(s_str:str) -> int:
            width = 0
            for ch in s_str:
                width += (2 if east_asian_width(ch) in ('W', 'F', 'A') else 1)
            return width

        col_widths = {field: _get_display_width(field) for field in fields}
        matrix = []
        for key, val in data_rows:
            row_data = {field:'' for field in fields}
            row_data['_id'] = key
            col_widths['_id'] = max(col_widths['_id'], _get_display_width(key))
            if isinstance(val, dict):
                for field,vv in val.items():
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
            return s_str + " " * (target_width - _get_display_width(s_str))

        border = "+" + "+".join("-" * (col_widths[field] + 2) for field in fields) + "+"
        print(border)
        print("|" + "|".join(" " + _pad_string(field, col_widths[field]) + " " for field in fields) + "|")
        print(border)
        for row_data in matrix:
            print("|" + "|".join(" " + _pad_string(row_data[field], col_widths[field]) + " " for field in fields) + "|")
        print(border)
        return dict(data_rows) if data_rows else {}

    def sync(self, force:bool=False, with_child:bool=False) -> JDbReader:
        """Refresh configuration maps arrays state ensuring compatibility with concurrent system modifications.

        Args:
            force (bool, optional): Obliterate internal state layouts prior to polling system state logs. Defaults to False.
            with_child (bool, optional): Cascades environment register purge rules downwards to inner instances. Defaults to False.

        Returns:
            JDbReader: The updated synchronization reference object instance.
        """
        if force:
            self.unsync()

        with self.open(read_only=True) as fp:
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
        """Flush and drop internal tracker registries resetting structures states to standard zero parameters.

        Args:
            with_child (bool, optional): Cascades environment register purge rules downwards to inner instances. Defaults to False.

        Returns:
            JDbReader: Clean slate structural tracking instance.
        """
        if not self.lock.acquire(): # pylint: disable=consider-using-with
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
        """Synchronize primary tables records maps checking current physical descriptor files states signatures.

        Args:
            force (bool, optional): Bypass transaction timeline validation checks forcing an absolute rebuild. Defaults to False.

        Returns:
            Tuple[Dict[str, int], Dict[int, int]]: Synced key_table map paired with active file_table indices.
        """
        with self.open(read_only=True) as fp:
            self.f_load_keys(fp, force=force)
            return self.io.key_table, self.io.file_table

    def get(self, key:str, default_val:Any=None, copy:bool=True) -> Any:
        """
        Safely fetch a value for a specific key, returning a default if not found.

        Args:
            key (str): The target key.
            default_val (Any, optional): Value to return upon missing key. Defaults to None.
            copy (bool, optional): Retrieve a deep copy to prevent mutation. Defaults to True.

        Returns:
            Any: The stored value or default.
        """
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
        """
        Attempt to retrieve the value from memory cache first, minimizing disk I/O.

        Args:
            key (str): The target key.
            default_val (Any, optional): Fallback value. Defaults to None.
            copy (bool, optional): Return a deep copy. Defaults to False.

        Returns:
            Any: The resolved data.
        """
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
        """
        Retrieve multiple keys simultaneously and pack them into a dictionary.

        Args:
            *records (str): Variable arguments representing the keys to fetch.

        Returns:
            Dict[str, Any]: A mapping of the requested keys to their values.
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
        Retrieve the entirety of the database content into a single dictionary.

        Args:
            cache_only (bool, optional): If True, only load what fits in the predefined cache_limit. Defaults to False.

        Returns:
            Dict[str, Any]: A full snapshot of the database.
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
        """Query modifications records parameters isolated within variable version sequence ranges markers.

        Args:
            version (int): Floor execution sequence baseline constraint number.
            max_version (Optional[int], optional): Cutoff ceiling phase identifier number index. Defaults to None.
            with_value (bool, optional): Decouple data arrays forcing real row data content parsing execution. Defaults to False.

        Returns:
            dict: Historical mapping records subset data.
        """
        with self.open(read_only=True) as fp:
            return self.f_read_version(fp, version=version, max_version=max_version, with_value=with_value)

    def check_row(self, row_id:int=0, with_value:bool=False) -> Optional[tuple]:
        """Inspect item layout metadata configurations across specific segment slots boundaries positions.

        Args:
            row_id (int, optional): Target alignment index position integer. Defaults to 0.
            with_value (bool, optional): Load true content alongside structural layout configurations metrics. Defaults to False.

        Returns:
            Optional[tuple]: Tuple containing binary allocation mapping profiles parameters or None.
        """
        with self.open(read_only=True) as fp:
            return self.f_read_row(fp, row_id, with_value)

    def get_bytes(self, key:str) -> bytes:
        """
        Extract the raw, compressed (if applicable) binary payload of a stored value without deserializing it.

        Args:
            key (str): The key mapping to the payload.

        Returns:
            bytes: Raw binary block. Returns empty bytes if key not found.
        """
        with self.open(read_only=True) as fp:
            return self.f_read_bytes(fp, key)

    def check_status(self, keys:dict) -> Dict[str,Tuple[str,int]]:
        """Evaluate status delta trackers processing system divergence tags across active entries collections.

        Args:
            keys (dict): Target mapping assigning reference variables tokens to distinct version baseline thresholds.

        Returns:
            Dict[str, Tuple[str, int]]: Dictionary associating identifiers with state change indicators (e.g., '+', '-', '!').
        """
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
        """Verify absolute parity matching current application memory arrays states with filesystem indicators on disk.

        Returns:
            bool: True if records mirror filesystem metrics perfectly, False if changes are pending.
        """
        with self.KEY_fopen():
            if self.io.is_updated():
                fsize = self.files_obj.KEY_size()
                return fsize == self.io.file_size

        return False

    def get_group(self, key:str) -> Optional[JDbReader]:
        """Isolate nested dataset directories initializing separate partitions spaces bound to distinct data keys.

        Args:
            key (str): Selector name defining sub-database namespace boundaries.

        Returns:
            Optional[JDbReader]: Active partition workspace or None if allocation rules break.
        """
        if not re_match(r'^[0-9A-Za-z_]+$', key):
            raise KeyError

        with self.open(read_only=True) as fp:
            return self.f_get_group(fp, key)

    def get_child(self, name:str) -> Optional[JDbReader]:
        """Resolve specific detached child storage database elements indexed under active mappings names.

        Args:
            name (str): Named partition token directory target selector.

        Returns:
            Optional[JDbReader]: Initialized isolated reader interface or None if file records break.
        """
        with self.open(read_only=True) as fp:
            return self.f_get_child(fp, name)

    def f_get_group(self, fp_dict:Dict[int,IO], key:str) -> Optional[JDbReader]:
        """Extract partition headers from stream context buffers generating group space profiles models.

        Args:
            fp_dict (Dict[int, IO]): Persistent active handles arrays pool mapping current thread.
            key (str): Unique sub-space path allocation label selector string.

        Returns:
            Optional[JDbReader]: Context bound group instance or None.
        """
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
                if isinstance(jdb, JDbReader) and self.files_obj.is_group(jdb.files_obj, key):
                    io.groups[key] = jdb
                    self.childs.pop(key, None)
                    return jdb

        self.io.groups.pop(key, None)
        return None

    def f_get_child(self, fp_dict:Dict[int,IO], name:str) -> Optional[JDbReader]: # pragma: no cover
        """Assemble child dataset references by evaluating storage descriptor arrays fields.

        Args:
            fp_dict (Dict[int, IO]): Persistent active registers tables.
            name (str): Selector token string matching underlying index rows data layers.

        Returns:
            Optional[JDbReader]: Disconnected instance context or None.
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
        """Append metadata entries into local tracking registers using LFU/FIFO capacity control logic.

        Args:
            key (str): Content selector lookups reference string.
            val (Any): Deserialized object instance data to store.
            copy (bool, optional): Isolate storage pointers utilizing deep copies to protect thread variables. Defaults to True.
        """
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
        """Low level data chunk stream parsing factory isolating specific physical slot blocks parameters.

        Args:
            fp_dict (Dict[int, IO]): Active file pointer table session.
            row_id (int): Hardware data sector alignment index value.
            with_value (bool, optional): Engage serialization routines unpacking real row contents blocks. Defaults to False.

        Returns:
            Optional[tuple]: Segment tracking array schema mapping allocation boundaries metrics or None.
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
        """
        Extract history lines and records bounded by version (sync/swap) IDs.

        Args:
            fp_dict (Dict[int, IO]): Active file pointers.
            version (int): The starting threshold version.
            max_version (Optional[int], optional): The capping threshold version. Defaults to None.
            with_value (bool, optional): Whether to also extract the true value into the returned array. Defaults to False.

        Returns:
            Dict[str, list]: A map of row-ID to a list containing metadata elements.
        """
        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        if max_version is None:
            max_version = io.n_lines

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
        """Extract compressed raw row values segments records bypassing standard engine factory loading steps.

        Args:
            fp_dict (Dict[int, IO]): Current workspace active file descriptors map.
            key (str): Lookup selection parameter string identifier.

        Returns:
            bytes: Compressed or raw unparsed payload binary segment array block.
        """
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

                - None = use current thread

            key (str): read key from database
        
        Returns:
            Tuple[Any, bytes]: key's data and key's unzip bytes

        """
        if not isinstance(key, str): # pragma: no cover
            key = str(key)

        io = self.io
        row = io.key_table[key]
        if not io.n_records > row >= 0: # pragma: no cover
            raise JKeyError(key)

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

        val_bytes = io.unzip(val_bytes, zip_type=zip_type)
        val = io.VAL_loads(val_bytes)
        return val, val_bytes

    def f_read(self, fp_dict:Dict[int,IO], key:Optional[str], default_val:Optional[Any]=None, row:Optional[int]=None, copy:bool=True) -> Any:
        """
        Low-level internal function to extract and deserialize a single data row via file pointers.

        Args:
            fp_dict (Dict[int, IO]): Dictionary holding active open files.
            key (Optional[str]): The target key string.
            default_val (Optional[Any], optional): Fallback if missing. Defaults to None.
            row (Optional[int], optional): Precise row integer to skip indexing. Defaults to None.
            copy (bool, optional): Ensure safety by returning a deepcopy. Defaults to True.

        Returns:
            Any: Deserialized object.
        """
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

                raise JKeyError(key)

        io, fp_dict, key_fp = self.f_get_fp(fp_dict)
        if row >= io.n_records: # pragma: no cover
            io.key_table.pop(key, -1)
            if default_val is not None:
                return default_val

            raise JKeyError(key)

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
        """Populate transactional key tables by evaluating raw data blocks tracking structures logs.

        Args:
            fp_dict (Dict[int, IO]): Open file pointers collections tracking variables.
            force (bool, optional): Overrule native consistency timestamps forcing full stream reconstruction. Defaults to False.
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
            key_fp.flush()
            key_fp.seek(0)

        io = self.io.read_header(key_fp)
        if force or not io.is_updated():
            io.load_keys(key_fp, force=force)
            self._cache.clear()
            self.fsize = io.file_size

    def f_find_keys(self, fp_dict:Dict[int,IO], pattern:Union[str,Pattern], **kwargs) -> Set[str]:
        """Filter record namespaces utilizing regex compilation routines inside storage descriptor environments.

        Args:
            fp_dict (Dict[int, IO]): Collection tracking active system streams pointers.
            pattern (Union[str, Pattern]): String token or compiled pattern layout blueprint matching queries.

        Returns:
            Set[str]: Filtered collection array tracking matching variables.
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
        """Compare operational transactional signatures identifying delta indicators across historical timelines.

        Args:
            fp_dict (Dict[int, IO]): Transaction registers maps array handles pool.
            key (str): Target reference lookup indicator selection token string.
            ver (int): Base reference comparison epoch phase index constraint value.

        Returns:
            Tuple[str, int]: Operational structural status code mapping paired with active transaction number index.
        """
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
        """Resolve environment processing configuration mappings matching active isolation boundaries records.

        Args:
            fp_dict (Optional[Dict[int, IO]]): Current session file pointer register collection array map or None.

        Returns:
            Tuple[JIo, Dict[int, IO], IO]: Primary processing engine engine block, register mappings, and master stream handles context.
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

    def f_get_val_fp(self, fp_dict:Dict[int,IO], file_id:Optional[int]=None, req_size:Optional[int]=None, max_fp:int=64) -> Tuple[IO,int,int]:
        """Manage active record segment storage files limiting concurrent hardware descriptive blocks allocation density.

        Args:
            fp_dict (Dict[int, IO]): Active file handler matrix registration array mappings table.
            file_id (Optional[int], optional): Target segment classification index code identifier. Defaults to None.
            req_size (Optional[int], optional): request new file size
            max_fp (int, optional): System density boundary constraining total allocated storage streams descriptors. Defaults to 64.

        Returns:
            Tuple[IO, int, int]: Target segment file stream controller instance, active section block index, and current capacity offset tracker.
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

    def _init_KEY(self) -> Tuple[JIo,IO]:
        """Wipe tracking maps writing fresh primary configuration sheets records blueprints templates.

        Returns:
            Tuple[JIo, IO]: Re-initialized pipeline engine coupled with active structural index file descriptor interface.
        """
        io = self.io
        key_fp = self.files_obj.KEY_open('wb+', buffering=KEY_FILE_BUF_SIZE)
        io.reset()
        self._cache.clear()
        self.fsize = io.write_header(key_fp)
        key_fp.flush()
        key_fp.seek(0)
        return io, key_fp

    def _init_VAL(self, file_id:int): # pragma: no cover
        """Format structural block segment file containers allocated onto physical memory frames arrays layers.

        Args:
            file_id (int): Segment data section classification token identifier integer number.
        """
        val_fp = None
        try:
            val_fp = self.files_obj.VAL_open(file_id, 'wb', buffering=0)

        finally:
            if val_fp is not None:
                val_fp.close()

    def _decode_row(self, file_id:int, offset:int, key:str, val_size:int=0) -> Any:
        """
        Deserialize extremely compact structures stored strictly within the 8-byte metadata limit.

        Args:
            file_id (int): Type flag identifier indicating base data type (int, float, date, bool, etc.).
            offset (int): Raw integer offset containing the packed binary payload.
            key (str): Associated key name.
            val_size (int, optional): Expected byte size. Defaults to 0.

        Returns:
            Any: The unpacked python primitive or short object.
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
        """
        Determine compact serialization strategies and compress objects to map onto the 8-byte metadata layout.        
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
    
        Args:
            key (str): The key target.
            val (Any): The payload object.

        Returns:
            Tuple[int, Union[int, bytes], int]: File ID classification, serialized value/offset, and actual byte length.
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
