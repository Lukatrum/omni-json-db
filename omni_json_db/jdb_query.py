# pylint: disable=too-many-lines
from __future__ import annotations
from functools import lru_cache
from datetime import date as dt_date, datetime, timedelta
from typing import Any, List, Generator, Union, Callable, Tuple
from re import compile as re_compile, findall as re_findall, Pattern, S as re_S
#-----------------------------------------------------------------------------
from .jdb_io import json_dumps
#-----------------------------------------------------------------------------

JSON_RE_sub = re_compile(r'[",{}\[\]]', flags=re_S).sub
PATH_RE_sub = re_compile(r'(?<!\W)\*+|\*+(?!\W|$)').sub

TYPE_MAP = {
    'int': int, 'bool': bool, 'float': float, \
    'str': str, 'bytes': bytes, \
    'list': list, 'dict': dict, 'set': set, 'tuple': tuple, \
    'none': type(None),
}

QUERY_OPS = {
    # --- MongoDB syntax
    'AND',          # {'$and': [A, B, ..]}                  # (A and B and ..)
                    # {A, B, ...}                           # {$gt:.., $lt:100, ...}
    'NOT',          # {'$not': A}                           # not A                    
    'OR',           # {'$or': [A, B, ..]}                   # (A or B or ..)
    'NOR',          # {'$nor': [A, B, ..]}                  # not (A or B or ..)
                    # {'!$or': [A, B, ..]}
    'IN',           # {'$in': {...}}                        # Value in {...}/[...]/(...)
                    # {...} / [...] / (...)
    'NIN',          # {'$nin': {...}}                       # Value not in {...}/[...]/(...)
                    # {'!$in': {...}}
    'EQ',           # {'$eq': chk }                         # Value == chk
                    # chk
    'NE',           # {'$ne': chk }                         # Value != chk
                    # {'!$eq': chk}
    'GT',           # {'$gt': chk }                         # Value > chk
    'LT',           # {'$lt': chk }                         # Value < chk
    'GTE',          # {'$gte': chk }                        # Value >= chk
    'LTE',          # {'$lte': chk }                        # Value <= chk
    'SIZE',         # {'$size': chk }                       # len(Value) == chk
    'REGEX',        # {'$regex': re.Pattern(...)}           # pattern.search(chk, Value)
                    # {'$regex': r'...'}                    # re.search(chk, Value)
                    # re.Pattern(...)
    # --- Not official
    'GE',           # {'$ge': chk }                         # Value >= chk
                    # {'$gte': chk }
    'LE',           # {'$le': chk }                         # Value <= chk
                    # {'$gte': chk }
    'RE',           # {'$re': re.Pattern(...)}              # pattern.search(chk, Value)
                    # {'$re': r'...'}                       # re.search(chk, Value)
                    # re.Pattern(...)
    'RE2',          # {'$re2': re.Pattern(...)}             # pattern.search(chk, JSON_RE_sub('', Value))
                    # {'$re2': r'...'}                      # re.search(chk, JSON_RE_sub('', Value))
    'MATCH',        # {'$match': re.Pattern(...)}           # pattern.fullmatch(chk, Value)
                    # {'$match': r'...'}                    # re.fullmatch(chk, Value)
    'FUNC',         # {'$func': lambda key,val: ..}         # bool(func(Key, Value))
                    # {'$func': lambda val: ..}             # bool(func(Value))
                    # lambda key,val: ...
                    # lambda val: ...
    'HAS',          # {'$has': chk}                         # Value.find(chk) >= 0
                    # {'$has': {...}                        # {...}.issubset(Value)
    # ---
    'IHAS',         # {'$ihas': chk}                        # Value.lower().find(chk.lower()) >= 0  
                    # {'$ihas': [...]}                      # {lower(...)}.issubset(Value.lower())
    'NHAS',         # {'$nhas': chk}                        # Value.find(chk) < 0  or chk not in Value
                    # {'$nhas' : {...}}                     # not {...}.issubset(Value)
                    # {'!$has' : chk}
    'SW',           # {'$sw': chk}                          # Value.startswith(chk)
                    # {'$sw': (...)}                        # Value.startswith((...))
    'EW',           # {'$ew': chk}                          # Value.endswith(chk)
                    # {'$sw': (...)}                        # Value.endswith((...))
    'ANYIN',        # {'$anyin': {...}}                     # any(kk in Value for kk in {...})
    'NAND',         # {'$nand': [A, B, ..]}                 # not (A and B and ..)
                    # {'!$and': [A, B, ..]}
    'BETWEEN',      # {'$between': (low, high)}             # low <= Value <= high
    'NEAR',         # {'$near': (target, tol)}              # abs(Value - target) <= tol
    'MOD',          # {'$mod': (divisor, remainder))        # (Value % divisor) == remainder
    # --- Only support VAL (not KEY and DATE)
    'ANY',          # {'$any': ... }                        # any(...)
    'ALL',          # {'$all': ... }                        # all(...)
    'NONE',         # {'$none': ... }                       # not any(...)
                    # {'!$any': ... }
    'TYPE',         # {'$type': chk}                        # type(Value) == chk
    'EXISTS',       # {'$exists': chk}                      # chk in Value
                    # {'$exists': {...}}                    # all(chk in Value for chk in {...})
}

#-----------------------------------------------------------------------------

class Condition(dict):
    def copy(self) -> Condition:
        return Condition(super().copy())

    def __missing__(self, key:str) -> None: # pragma: no cover
        return ''

    def __and__(self, other:Condition) -> Condition:
        left  = self['$and']  if '$and' in self and len(self) == 1 else [dict(self)]
        right = other['$and'] if '$and' in other and len(other) == 1 else [dict(other)]
        return Condition({'$and': left + right})

    def __or__(self, other:Condition) -> Condition:
        left  = self['$or']  if '$or' in self  and len(self) == 1 else [dict(self)]
        right = other['$or'] if '$or' in other and len(other) == 1 else [dict(other)]
        return Condition({'$or': left + right})

    def __invert__(self) -> Condition:
        return Condition({'$not': dict(self)})

    def __repr__(self) -> str:
        return f'Condition({dict.__repr__(self)})'

class Query:
    def __init__(self, _path:str = ''):
        object.__setattr__(self, '_path', _path)

    def __getattr__(self, name:str) -> Query:
        path = self._path
        return Query(f'{path}.{name}' if path else name)

    def __getitem__(self, segment:Any) -> Query:
        path = self._path
        seg  = str(segment)
        return Query(f'{path}.{seg}' if path else seg)

    def _cond(self, op:str, val:Any) -> Condition:
        path = self._path
        return Condition({path: {op: val}} if path else {op: val})

    def __eq__(self, val:Any) -> Condition:
        path = self._path
        return Condition({path: val} if path else {}) if path else NotImplemented

    def __ne__(self, val:Any) -> Condition:
        return self._cond('$ne', val)

    def __gt__(self, val:Any) -> Condition:
        return self._cond('$gt', val)

    def __ge__(self, val:Any) -> Condition:
        return self._cond('$gte', val)

    def __lt__(self, val:Any) -> Condition:
        return self._cond('$lt', val)

    def __le__(self, val:Any) -> Condition:
        return self._cond('$lte', val)

    def has(self, val:Union[str,tuple]) -> Condition:
        return self._cond('$has', val)

    def ihas(self, val:Union[str,tuple]) -> Condition:
        return self._cond('$ihas', val)

    def not_has(self, val:Union[str,tuple]) -> Condition:
        return self._cond('$nhas', val)

    def startswith(self, prefix:Union[str,tuple]) -> Condition:
        return self._cond('$sw', prefix)

    def endswith(self, suffix:Union[str,tuple]) -> Condition:
        return self._cond('$ew', suffix)

    def between(self, lo:Union[str,int,float], hi:[Union[str,int,float]]) -> Condition:
        return self._cond('$between', (lo, hi))

    def near(self, target:Union[int,float], tol:Union[int,float]) -> Condition:
        return self._cond('$near', (target, tol))

    def mod(self, div:Union[int,float], rem:Union[int,float]) -> Condition:
        return self._cond('$mod', (div, rem))

    def size_of(self, size:Union[int,Tuple[int]]) -> Condition:
        return self._cond('$size', size)

    def exists(self, fields:Union[Any,Tuple[Any]]) -> Condition:
        return self._cond('$exists', fields)

    def type_of(self, _type:str) -> Condition:
        return self._cond('$type', _type)

    def any_in(self, col:Union[tuple,list,set]) -> Condition:
        return self._cond('$anyin', col)

    def matches(self, pattern:Union[str,Pattern], flags:int=0) -> Condition:
        rx = re_compile(pattern, flags) if isinstance(pattern, str) else pattern
        return self._cond('$re', rx)

    def fullmatch(self, pattern:Union[str,Pattern], flags:int=0) -> Condition:
        rx = re_compile(pattern, flags) if isinstance(pattern, str) else pattern
        return self._cond('$match', rx)

    def test(self, func:Union[Callable[[Any],bool],Callable[[str,Any],bool]]) -> Condition:
        return self._cond('$func', func)

    def one_of(self, collection:Any) -> Condition:
        return self._cond('$in', collection)

    def not_in(self, collection:Any) -> Condition:
        return self._cond('$nin', collection)

    def __repr__(self) -> str:
        return f"Query('{self._path}')"

#-----------------------------------------------------------------------------
def match_KEY_rules(key:str, rules:Any, level:int=0) -> bool:
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
        >>> match_KEY_rules("Bob", rules)
        True
        >>> match_KEY_rules("Alice", {"$re": r"Al.*"})
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
        is_matched = False
        reverse_it = cmd.startswith('!')
        cmd = cmd[1:] if reverse_it else cmd
        if cmd and cmd[0] == '$':
            cmd = cmd.lower()
            is_same_type = isinstance(rule, str)
            if cmd == '$gt':
                if is_same_type:
                    is_matched = (key <= rule) if reverse_it else (key > rule)

            elif cmd in ('$gte', '$ge'):
                if is_same_type:
                    is_matched = (key < rule) if reverse_it else (key >= rule)

            elif cmd == '$lt':
                if is_same_type:
                    is_matched = (key >= rule) if reverse_it else (key < rule)

            elif cmd in ('$lte', '$le'):
                if is_same_type:
                    is_matched = (key > rule) if reverse_it else (key <= rule)

            elif cmd in ('$eq', '$ne'):
                if is_same_type:
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    is_matched = (key != rule) if reverse_it else (key == rule)

            elif cmd == '$between':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    low, high = rule
                    try:
                        if isinstance(low, str) and isinstance(high, str):
                            is_matched = low <= key <= high
                            is_matched = (not is_matched) if reverse_it else is_matched
                        elif isinstance(low, (int, float)) and isinstance(high, (int, float)):
                            is_matched = low <= float(key) <= high
                            is_matched = (not is_matched) if reverse_it else is_matched

                    except (TypeError, ValueError): # pragma: no cover
                        pass

            elif cmd == '$near':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    target, tol = rule
                    try:

                        if isinstance(target, (int, float)) and isinstance(tol, (int, float)):
                            is_matched = abs(float(key) - target) <= tol
                            is_matched = (not is_matched) if reverse_it else is_matched
                    except (TypeError, ValueError): # pragma: no cover
                        pass

            elif cmd == '$mod':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    divisor, remainder = rule
                    try:
                        if isinstance(divisor, (int, float)) and isinstance(remainder, (int, float)):
                            is_matched = float(key) % divisor == remainder
                            is_matched = (not is_matched) if reverse_it else is_matched
                    except (TypeError, ValueError): # pragma: no cover
                        pass

            elif cmd in ('$sw', '$ew'):
                if isinstance(rule, (tuple, str)):
                    try:
                        is_matched = key.startswith(rule) if cmd[1] == 's' else key.endswith(rule)
                        is_matched = (not is_matched) if reverse_it else is_matched
                    except (TypeError, ValueError): # pragma: no cover
                        pass

            elif cmd in ('$in', '$nin', '$anyin'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                try:
                    is_matched = (key not in rule) if reverse_it else (key in rule)

                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$has', '$nhas', '$ihas'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                if isinstance(rule, str):
                    key_l = key.lower() if cmd[1] == 'i' else key
                    rule_l = rule.lower() if cmd[1] == 'i' else rule
                    is_matched = (key_l.find(rule_l) < 0) if reverse_it else (key_l.find(rule_l) >= 0)

            elif cmd in ('$re', '$re2', '$regex', '$match'):
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
                    key_s = JSON_RE_sub('', key) if cmd[-1] == '2' else key
                    use_fullmatch = cmd == '$match'
                    for _rule in _rules:
                        is_matched = _rule.fullmatch(key_s) if use_fullmatch else _rule.search(key_s)
                        if not is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd == '$func':
                if callable(rule): # pragma: no cover
                    arg_cnt = rule.__code__.co_argcount
                    try:
                        if arg_cnt == 1:
                            is_matched = (not rule(key)) if reverse_it else rule(key)
                    except Exception as e: # pragma: no cover
                        print(e)

            elif cmd == '$size':
                _len = len(key)
                if isinstance(rule, (float, int)):
                    is_matched = (_len != int(rule)) if reverse_it else (_len == int(rule))

                elif isinstance(rule, (list, set, frozenset, tuple, range)):
                    is_matched = (_len not in rule) if reverse_it else (_len in rule)

            elif cmd == '$not':
                is_matched = not match_KEY_rules(key, rule, level=level+1)
                is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$or', '$nor'):
                if isinstance(rule, (list,tuple)):
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    for _rule in rule:
                        is_matched = match_KEY_rules(key, _rule, level=level+1)
                        if is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$and', '$nand'):
                if isinstance(rule, (list,tuple)):
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    for _rule in rule:
                        is_matched = match_KEY_rules(key, _rule, level=level+1)
                        if not is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

        elif cmd == '_id':
            is_matched = match_KEY_rules(key, rule, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        if not is_matched: return False

    return True

def match_DATE_rules(cdate:dt_date, mdate:dt_date, rules:Any, level:int=0) ->bool:
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
        >>> match_DATE_rules(today, today, rules={'$eq': today})
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
        is_matched = False
        reverse_it = cmd.startswith('!')
        cmd = cmd[1:] if reverse_it else cmd
        if cmd and cmd[0] == '$':
            cmd = cmd.lower()
            is_cdate = isinstance(rule, datetime)
            is_mdate = not is_cdate and isinstance(rule, dt_date)
            is_same_type = is_cdate or is_mdate
            if cmd == '$gt':
                if is_same_type:
                    is_matched = (is_cdate and cdate <= rule.date() or is_mdate and mdate <= rule) if reverse_it else \
                            (is_cdate and cdate > rule.date() or is_mdate and mdate > rule)

            elif cmd in ('$gte', '$ge'):
                if is_same_type:
                    is_matched = (is_cdate and cdate < rule.date() or is_mdate and mdate < rule) if reverse_it else \
                            (is_cdate and cdate >= rule.date() or is_mdate and mdate >= rule)

            elif cmd == '$lt':
                if is_same_type:
                    is_matched = (is_cdate and cdate >= rule.date() or is_mdate and mdate >= rule) if reverse_it else \
                            (is_cdate and cdate < rule.date() or is_mdate and mdate < rule)

            elif cmd in ('$le', '$lte'):
                if is_same_type:
                    is_matched = (is_cdate and cdate > rule.date() or is_mdate and mdate > rule) if reverse_it else \
                            (is_cdate and cdate <= rule.date() or is_mdate and mdate <= rule)

            elif cmd in ('$eq', '$ne'):
                if is_same_type:
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    is_matched = (is_cdate and cdate != rule.date() or is_mdate and mdate != rule) if reverse_it else \
                            (is_cdate and cdate == rule.date() or is_mdate and mdate == rule)

            elif cmd == '$between':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    low, high = rule
                    try:
                        if isinstance(low, datetime) and isinstance(high, datetime):
                            is_matched = low.date() <= cdate <= high.date()
                            is_matched = (not is_matched) if reverse_it else is_matched
                        elif isinstance(low, dt_date) and isinstance(high, dt_date):
                            is_matched = low <= mdate <= high
                            is_matched = (not is_matched) if reverse_it else is_matched
                        elif isinstance(low, str) and isinstance(high, str):
                            is_matched = low <= str(mdate) <= high or low <= str(cdate) <= high
                            is_matched = (not is_matched) if reverse_it else is_matched

                    except TypeError: # pragma: no cover
                        pass

            elif cmd == '$near':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    target, tol = rule
                    try:
                        if isinstance(target, datetime) and isinstance(tol, (int, float)):
                            is_matched = abs((cdate - target.date()).days) <= tol
                            is_matched = (not is_matched) if reverse_it else is_matched
                        elif isinstance(target, dt_date) and isinstance(tol, (int,float)):
                            is_matched = abs((mdate - target).days) <= tol
                            is_matched = (not is_matched) if reverse_it else is_matched
                    except TypeError: # pragma: no cover
                        pass

            elif cmd == '$mod':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    divisor, remainder = rule
                    if isinstance(divisor, (int, float)) and isinstance(remainder, (int, float)):
                        try:
                            # date % 7: (0 = monday, ... 6 = sunday)
                            first_date = dt_date(1, 1, 1)
                            is_matched = isinstance(divisor, float) and (((cdate - first_date).days) % divisor) == remainder or \
                                        isinstance(divisor, int) and (((mdate - first_date).days) % divisor) == remainder
                            is_matched = (not is_matched) if reverse_it else is_matched
                        except TypeError: # pragma: no cover
                            pass

            elif cmd in ('$sw', '$ew'):
                if isinstance(rule, (tuple, str)):
                    try:
                        is_matched = date_s.startswith(rule) if cmd[1] == 's' else date_s.endswith(rule)
                        is_matched = (not is_matched) if reverse_it else is_matched
                    except TypeError: # pragma: no cover
                        pass

            elif cmd in ('$in', '$nin', '$anyin'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                try:
                    is_matched = (mdate in rule or mdate_s in rule or cdate in rule or cdate_s in rule) if cmd.endswith('anyin') else \
                                (mdate in rule or mdate_s in rule) if isinstance(rule, set) else \
                                (cdate in rule or cdate_s in rule)
                    is_matched = (not is_matched) if reverse_it else is_matched
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$has', '$nhas', '$ihas'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                date_s = date_s.lower() if cmd[1] == 'i' else date_s
                if isinstance(rule, str):
                    rule_l = rule.lower() if cmd[1] == 'i' else rule
                    is_matched = (date_s.find(rule_l) < 0) if reverse_it else (date_s.find(rule_l) >= 0)

                elif isinstance(rule, datetime): # before dt_date
                    is_matched = (date_s.find(str(rule.date())) < 0) if reverse_it else (date_s.find(str(rule.date())) >= 0)

                elif isinstance(rule, dt_date):
                    is_matched = (date_s.find(str(rule)) < 0) if reverse_it else (date_s.find(str(rule)) >= 0)

            elif cmd in ('$re', '$re2', '$regex', '$match'):
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
                    date_s = JSON_RE_sub('', date_s) if cmd[-1] == '2' else date_s
                    use_fullmatch = cmd == '$match'
                    for _rule in _rules:
                        is_matched = _rule.fullmatch(date_s) if use_fullmatch else \
                                    _rule.search(date_s)
                        if not is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd == '$func':
                if callable(rule):
                    arg_cnt = rule.__code__.co_argcount
                    try:
                        if arg_cnt == 2:
                            is_matched = (not rule(cdate, mdate)) if reverse_it else rule(cdate, mdate)
                    except: # pragma: no cover
                        pass

            elif cmd == '$not':
                is_matched = not match_DATE_rules(cdate, mdate, rule, level=level+1)
                is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$or', '$nor'):
                if isinstance(rule, (list,tuple)):
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    for _rule in rule:
                        is_matched = match_DATE_rules(cdate, mdate, _rule, level=level+1)
                        if is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$and', '$nand'):
                if isinstance(rule, (list,tuple)):
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    for _rule in rule:
                        is_matched = match_DATE_rules(cdate, mdate, _rule, level=level+1)
                        if not is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

        elif cmd == '_date':
            is_matched = match_DATE_rules(cdate, mdate, rule, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        if not is_matched: return False

    return True

def match_VAL_rules(key:str, val:Any, rules:Any, cdate:dt_date, mdate:dt_date, level:int=0, ANY:bool=False, ALL:bool=False) -> bool:
    """
    Evaluate if a value matches a given set of conditions or MongoDB-like operators.

    Supports operations such as `$gt`, `$ge`, `$gte`, `$lt`, `$le`, `$lte`, `$eq`, `$ne`, `$in`, 
    `$has`, `$re`, `$re2`, `$regex`, `$func`, `$size`, `$not`, `$or`, `$nor` and `$and`.

    Args:
        key (str): The key associated with the value being evaluated.
        val (Any): The actual data value to be checked.
        rules (Any): The dictionary of rules/operators or a direct match condition.
        cdate (date): KEY created date.
        mdate (date): KEY modified date.        
        level (int, optional): The current recursion depth. Defaults to 0.
        ANY (bool, optional): If True, checks if any element in an iterable value matches. Defaults to False.
        ALL (bool, optional): If True, checks if all element in an iterable value matches. Defaults to False.

    Returns:
        bool: True if the value satisfies all specified rules, False otherwise.

    Example:
        >>> rules = {'$gt': 10, '$lt': 20}
        >>> match_VAL_rules("age", 15, rules)
        True
        >>> match_VAL_rules("name", "Alice", {"$re": r"Al.*"})
        True
    """
    is_dict = isinstance(val, dict)
    if (ANY or ALL) and hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
        items = val.values() if is_dict else val
        if ANY and any(match_VAL_rules(key, _val, rules, cdate, mdate, level=level+1, ANY=True) for _val in items) or \
                ALL and all(match_VAL_rules(key, _val, rules, cdate, mdate, level=level+1, ALL=True) for _val in items):
            return True

    if not isinstance(rules, dict): # pragma: no cover
        if isinstance(rules, (str, int, float, bool, bytes)):
            rules = {'$eq': rules}
        elif isinstance(rules, Pattern):
            rules = {'$re': rules}
        elif callable(rules):
            rules = {'$func': rules}
        elif isinstance(rules, (list, set, tuple, frozenset, range)):
            rules = {'$in': set(rules)}
        elif isinstance(rules, (dt_date, datetime)):
            rules = {'$eq': rules}
        else:
            return False

    for cmd,rule in rules.items():
        is_matched = False
        reverse_it = cmd.startswith('!')
        cmd = cmd[1:] if reverse_it else cmd
        if cmd and cmd[0] == '$':
            cmd = cmd.lower()
            is_same_type = isinstance(val, type(rule)) \
                or isinstance(val, (int, float)) and isinstance(rule, (int, float)) \
                or isinstance(val, (bytes, bytearray)) and isinstance(rule, (bytes, bytearray))

            if cmd == '$gt':
                try:
                    if is_same_type and val.__gt__ and rule.__gt__:
                        is_matched = (val <= rule) if reverse_it else (val > rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$gte', '$ge'):
                try:
                    if is_same_type and val.__ge__ and rule.__ge__:
                        is_matched = (val < rule) if reverse_it else (val >= rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd == '$lt':
                try:
                    if is_same_type and val.__lt__ and rule.__lt__:
                        is_matched = (val >= rule) if reverse_it else (val < rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$lte', '$le'):
                try:
                    if is_same_type and val.__le__ and rule.__le__:
                        is_matched = (val > rule) if reverse_it else (val <= rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$eq', '$ne'):
                try:
                    if is_same_type and val.__eq__ and rule.__eq__:
                        reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                        is_matched = (val != rule) if reverse_it else (val == rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd == '$between':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    low, high = rule
                    try:
                        _is_same_type = isinstance(val, type(low)) and isinstance(val, type(high)) \
                                or isinstance(high, type(low)) and (\
                                    isinstance(val, (int, float)) and isinstance(high, (int, float)) or \
                                    isinstance(val, (bytes, bytearray)) and isinstance(high, (bytes, bytearray)))

                        if  _is_same_type and val.__le__ and high.__ge__:
                            is_matched = low <= val <= high
                            is_matched = (not is_matched) if reverse_it else is_matched

                    except TypeError: # pragma: no cover
                        pass

            elif cmd == '$near':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    target, tol = rule
                    if isinstance(target, (int, float)) and isinstance(tol, (int, float)) and isinstance(val, (int, float)):
                        try:
                            is_matched = abs(val - target) <= tol
                            is_matched = (not is_matched) if reverse_it else is_matched
                        except TypeError: # pragma: no cover
                            pass

            elif cmd == '$mod':
                if isinstance(rule, (list, tuple)) and len(rule) == 2:
                    divisor, remainder = rule
                    if isinstance(divisor, (int, float)) and isinstance(remainder, (int, float)) and isinstance(val, (int, float)):
                        try:
                            is_matched = (val % divisor) == remainder
                            is_matched = (not is_matched) if reverse_it else is_matched
                        except TypeError: # pragma: no cover
                            pass

            elif cmd in ('$sw', '$ew'):
                try:
                    val_s = val if isinstance(val, str) else \
                            (val if isinstance(rule, bytes) else val.decode('utf8')) if isinstance(val, (bytes, bytearray)) else \
                            (json_dumps(val) if isinstance(rule, bytes) else val.decode('utf8'))

                    if isinstance(val_s, bytes) and isinstance(rule, (bytes,tuple)) or isinstance(val_s, str) and isinstance(rule, (str, tuple)):
                        is_matched = val_s.startswith(rule) if cmd[1] == 's' else val_s.endswith(rule)
                        is_matched = (not is_matched) if reverse_it else is_matched

                except (TypeError, ValueError, AttributeError): # pragma: no cover
                    pass

            elif cmd in ('$in', '$nin', '$anyin'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                if hasattr(rule, '__contains__'):
                    try:
                        if val.__hash__ and not isinstance(val, (list, set, frozenset, tuple, range)):
                            is_matched = val in rule

                        elif val.__iter__:
                            _set_r = set(rule) if not isinstance(rule, (set, frozenset)) else rule
                            _set_v = set(val) if not isinstance(val, (set, frozenset)) else val
                            is_matched = len(_set_r & _set_v) > 0 if cmd.endswith('anyin') else \
                                        _set_r.issubset(_set_v)

                        is_matched = (not is_matched) if reverse_it else is_matched

                    except TypeError: # pragma: no cover
                        pass

            elif cmd in ('$has', '$nhas', '$ihas'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                if hasattr(val, '__contains__') and not isinstance(val, (str, bytes, bytearray)):
                    try:
                        _set_r = rule if isinstance(rule, (set, frozenset)) else \
                                set(rule) if isinstance(rule, (list, tuple)) else {rule}
                        _set_r = {vv.lower() for vv in _set_r} if cmd[1] == 'i' else _set_r
                        _set_v = set(val) if not isinstance(val, (set, frozenset)) else val
                        _set_v = {vv.lower() for vv in _set_v} if cmd[1] == 'i' else _set_v
                        is_matched = _set_r.issubset(_set_v)
                        is_matched = (not is_matched) if reverse_it else is_matched

                    except (TypeError, ValueError, AttributeError): # pragma: no cover
                        pass
                else:
                    try:
                        val_s = val if isinstance(val, str) else \
                                (val if isinstance(rule, bytes) else val.decode('utf8')) if isinstance(val, (bytes, bytearray)) else \
                                (json_dumps(val) if isinstance(rule, bytes) else val.decode('utf8'))

                        if isinstance(val_s, bytes) and isinstance(rule, bytes) or isinstance(val_s, str) and isinstance(rule, str):
                            val_s = val_s if cmd[1] != 'i' else val_s.lower()
                            rule_l = rule.lower() if cmd[1] == 'i' else rule
                            is_matched = (val_s.find(rule_l) < 0) if reverse_it else (val_s.find(rule_l) >= 0)

                    except (TypeError, ValueError, AttributeError): # pragma: no cover
                        pass

            elif cmd in ('$re', '$re2', '$regex', '$match'):
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
                            val_s = None

                    else: # pragma: no cover
                        val_s = val

                    if val_s is not None:
                        use_fullmatch = cmd == '$match'
                        val_s = JSON_RE_sub('', val_s) if cmd[-1] == '2' else val_s
                        for _rule in _rules:
                            is_matched = _rule.fullmatch(val_s) if use_fullmatch else \
                                        _rule.search(val_s)
                            if not is_matched:
                                break

                        is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd == '$func':
                if callable(rule): # pragma: no cover
                    arg_cnt = rule.__code__.co_argcount
                    try:
                        if arg_cnt == 2:
                            is_matched = (not rule(key, val)) if reverse_it else (rule(key, val))

                        elif arg_cnt == 1:
                            is_matched = (not rule(val)) if reverse_it else (rule(val))

                    except: # pragma: no cover
                        pass

            elif cmd == '$size':
                if hasattr(val, '__iter__'):
                    _len = len(val)
                    if isinstance(rule, (float, int)):
                        is_matched = (_len != int(rule)) if reverse_it else (_len == int(rule))

                    elif isinstance(rule, (list, set, frozenset, tuple, range)):
                        is_matched = (_len not in rule) if reverse_it else (_len in rule)

            elif cmd == '$type':
                if isinstance(rule, str):
                    target_type = TYPE_MAP.get(rule.lower(), '')
                    if target_type:
                        is_matched = isinstance(val, int) and not isinstance(val, bool) if target_type == int else \
                                    isinstance(val, bool) if target_type == bool else isinstance(val, target_type)
                        is_matched = (not is_matched) if reverse_it else is_matched

                elif isinstance(rule, type):
                    is_matched = isinstance(val, rule)
                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd == '$exists':
                if isinstance(val, dict) and isinstance(rule, (str, list, set, frozenset, tuple)):
                    fields = [rule] if isinstance(rule, str) else rule
                    is_matched = all(field in val for field in fields)
                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd == '$not':
                is_matched = not match_VAL_rules(key, val, rule, cdate, mdate, level=level+1)
                is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$or', '$nor'):
                if isinstance(rule, (list,tuple)):
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    for _rule in rule:
                        is_matched = match_VAL_rules(key, val, _rule, cdate, mdate, level=level+1)
                        if is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$and', '$nand'):
                if isinstance(rule, (list,tuple)):
                    reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                    for _rule in rule:
                        is_matched = match_VAL_rules(key, val, _rule, cdate, mdate, level=level+1)
                        if not is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd in ('$any', '$none', '$all'):
                reverse_it = (not reverse_it) if cmd[1] == 'n' else reverse_it
                is_any = cmd != '$all'
                if hasattr(val, '__iter__') and not isinstance(val, (str, bytes)):
                    items = val.values() if is_dict else val
                    if is_any:
                        is_matched = any(match_VAL_rules(key, _val, rule, cdate, mdate, ANY=True, level=level+1) for _val in items)
                    else:
                        is_matched = all(match_VAL_rules(key, _val, rule, cdate, mdate, ANY=True, level=level+1) for _val in items)
                else:
                    is_matched = match_VAL_rules(key, val, rule, cdate, mdate, level=level+1)

                if not is_matched and isinstance(rule, dict):
                    _is_matched = False
                    if is_dict:
                        for _ref, _rule in rule.items():
                            _reverse_it = _ref.startswith('!')
                            _ref_l = _ref[1:] if _reverse_it else _ref
                            if _ref_l in val:
                                _is_matched = match_VAL_rules(key, val[_ref_l], _rule, cdate, mdate, level=level+1)
                                _is_matched = (not _is_matched) if _reverse_it else _is_matched
                                if is_any and _is_matched or not is_any and not _is_matched:
                                    break

                    is_matched = True if _is_matched else is_matched

                is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd[1:].isdigit():
                if isinstance(val, (list, tuple)):
                    try:
                        is_matched = match_VAL_rules(key, val[int(cmd[1:])], rule, cdate, mdate, level=level+1)
                        is_matched = (not is_matched) if reverse_it else is_matched

                    except IndexError: # pragma: no cover
                        pass

        elif is_dict and cmd in val:
            is_matched = match_VAL_rules(key, val[cmd], rule, cdate, mdate, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        elif cmd == '_id':
            is_matched = match_KEY_rules(key, rule, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        elif cmd == '_date':
            is_matched = match_DATE_rules(cdate, mdate, rule, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        elif is_dict:
            _cnt = 0
            for sep in './|\\':
                idx = cmd.find(sep)
                if idx < 0: continue
                parts = cmd.split(sep)
                if any('*' in part or '?' in part for part in parts): # any wildcard in parts
                    _cnt += 1
                    is_matched = _match_PATH(parts, key, val, rule, cdate, mdate, level=level+1)
                    is_matched = (not is_matched) if reverse_it else is_matched
                    break

                try:
                    _val = val
                    _size = len(parts)
                    for ii,part in enumerate(parts):
                        part_s = part.lstrip(' ')
                        if ii+1 == _size and part.startswith(('!$', '$')):
                            rule = {part_s:rule}
                        elif isinstance(_val, dict):
                            _val = _val[part_s]
                        elif isinstance(_val, (list, tuple)):
                            _val = _val[int(part_s)]
                        else: # pragma: no cover
                            raise TypeError

                    _cnt += 1
                    is_matched = match_VAL_rules(key, _val, rule, cdate, mdate, level=level+1)
                    is_matched = (not is_matched) if reverse_it else is_matched
                    break

                except (KeyError, IndexError, ValueError, TypeError): # pragma: no cover
                    pass

            if _cnt == 0 and ('*' in cmd or '?' in cmd):
                is_matched = _match_PATH([cmd], key, val, rule, cdate, mdate, level=level+1)
                is_matched = (not is_matched) if reverse_it else is_matched

        if not is_matched: return False

    return True

def _iter_all_node(node:Any) -> Generator[Any]:
    """Recursively yield every node in a nested dict/list structure."""
    yield node

    if isinstance(node, dict):
        for v in node.values():
            yield from _iter_all_node(v)

    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _iter_all_node(v)

@lru_cache(maxsize=256)
def _compile_path_glob(pattern: str) -> Pattern:
    """Compile and cache a glob path pattern to regex."""
    return re_compile(f'^{PATH_RE_sub(".*", pattern.replace("?", "."))}$')

def _match_PATH(key_parts:List[str], key:str, val: Any, rules:Any, cdate:dt_date, mdate:dt_date, level:int) -> bool:
    """
    Recursively navigate val following path segments (parts).
    Supports '*'/'**'/'?' wildcard and glob patterns (e.g. 'addr*', '*c?ty').
    ANY semantics: returns True if any matching path satisfies the rule.

    Args:
        key_parts (List[str]): Ordered list of remaining path segments to traverse, produced by splitting a separator-delimited path string (e.g. 'addr*.city' becomes ['addr*', 'city']). Each element is consumed one level per recursive call. Accepted forms for each segment are:
            - Literal string  : exact dict key lookup (e.g. 'meta', 'address').
            - Integer string  : zero-based index for list/tuple access (e.g. '0', '2').
            - `?` wildcard    :
                    - On dict : '?' is a single-char wildcard in the key name (regex '.').
                                N '?'s match keys of exactly N characters.
                                e.g. '?' -> 1-char keys; 'addr?' -> 5-char keys starting with 'addr'.
                    - On list :  N '?'s select the N-th decade of indices (0-based).
                                '?'  -> indices 0–9   (decade 1)
                                '??' -> indices 10–19 (decade 2)

            - `*` wildcard    : '*' expands to every dict value or every sequence element.
            - `**` wildcard   : '**' expands to every dict value or every sequence element recursively.
            - Glob pattern    : a string containing '*' matched against dict key names
                                (e.g. 'addr*', '*city', 'a*z'); only supported on dicts.
            - Operator segment : a segment starting with '$' or '!$' (no leading space), applied as a query operator at the leaf (e.g. '$has', '!$eq'). 
                                Add a leading space to treat it as a literal dict key instead.
            An empty list is the base case: the filter rule is applied directly to the current val without further navigation.
        key (str): The key associated with the value being evaluated.
        val (Any): The actual data value to be checked.
        rules (Any): The dictionary of rules/operators or a direct match condition.
        cdate (date): KEY created date.
        mdate (date): KEY modified date.        
        level (int, optional): The current recursion depth. Defaults to 0.
        
    Returns:
        bool: True if the value satisfies all specified rules, False otherwise.

    Examples:
        key_parts=['addr*','city']          -> match any key starting with 'addr', check .city
        key_parts=['*','0']                 -> any child's element at index 0
        key_parts=['tags','*']              -> any element inside .tags
        key_parts=['addr*', 'c*y', '$eq']   -> key_parts=['addr*', 'c*y'], rules={'$eq':rules}
    """

    if not key_parts:
        return match_VAL_rules(key, val, rules, cdate, mdate, level=level+1)

    child_key, rest_parts = key_parts[0], key_parts[1:]
    child_key_s = child_key.lstrip(' ') # if map's key starts with '$', child_key must add ' ' before '$'
    if '*' in child_key_s or '?' in child_key_s:
        if child_key_s == '**':
            return any(_match_PATH(rest_parts, key, child_val, rules, cdate, mdate, level) for child_val in _iter_all_node(val))

        child_vals = None
        if isinstance(val, dict):
            if child_key_s == '*':
                child_vals = list(val.values()) # any field
            else:
                # Glob -> regex : 'addr*' -> r'^addr.*$'
                rx = _compile_path_glob(child_key_s)
                child_vals = [v for k,v in val.items() if rx.match(k)]

        elif isinstance(val, (list, tuple)):
            if child_key_s in ('*', '?*', '*?'):
                child_vals = list(val)
            elif child_key_s.startswith('?'):
                _cnt = child_key_s.count('?')
                if _cnt == len(child_key_s):
                    child_vals = [val for ii,val in enumerate(val) if (ii//10)+1 == _cnt]

        return any(_match_PATH(rest_parts, key, child_val, rules, cdate, mdate, level) for child_val in child_vals) if child_vals else False

    else:
        try:
            if not rest_parts and child_key.startswith(('!$', '$')):
                rules = {child_key_s:rules}
                child_val = val
            elif isinstance(val, dict):
                child_val = val[child_key_s]
            elif isinstance(val, (list, tuple)):
                child_val = val[int(child_key_s)]
            else: # pragma: no cover
                raise TypeError

            return _match_PATH(rest_parts, key, child_val, rules, cdate, mdate, level)

        except (KeyError, IndexError, ValueError, TypeError): # pragma: no cover
            pass

        return False

#
