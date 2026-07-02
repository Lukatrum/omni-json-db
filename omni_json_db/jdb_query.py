# pylint: disable=too-many-lines
from __future__ import annotations
from functools import lru_cache
from math import ceil, floor
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

QUERY_OPS = frozenset({
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
    # ---- Transform operator
    'ABS',          # {'$abs': chk}                         # Value.abs() == chk
    'CEIL',         # {'$ceil': chk}                        # Value.ceil() == chk
    'FLOOR',        # {'$floor': chk}                       # Value.floor() == chk
    'ROUND',        # {'$round': chk}                       # Value.round() == chk

    'FLOAT',        # {'$float': chk}                       # Value.float() == chk
    'INT',          # {'$int': chk}                         # Value.int() == chk
    'NEG',          # {'$neg': chk}                         # Value.neg() == chk
    'STR',          # {'$str': chk}                         # Value.str() == chk

    'AVG',          # {'$avg': chk}                         # Value.avg() == chk
    'STD',          # {'$std': chk}                         # Value.std() == chk
    'MAX',          # {'$max': chk}                         # Value.max() == chk
    'MID',          # {'$mid': chk}                         # Value.mid() == chk
    'MIN',          # {'$min': chk}                         # Value.min() == chk
    'SUM',          # {'$sum': chk}                         # Value.sum() == chk

    'FIRST',        # {'$first': chk}                       # Value.first() == chk
    'FLAT',         # {'$flat': chk}                        # Value.flat() == chk
    'LAST',         # {'$last': chk}                        # Value.last() == chk
    'LEN',          # {'$len': chk}                         # Value.len() == chk
    'SORT',         # {'$sort': chk}                        # Value.sort() == chk
    'UNIQUE',       # {'$unique': chk'}                     # Value.unique() == chk

    'LOWER',        # {'$lower': chk}                       # Value.lower() == chk
    'STRIP',        # {'$strip': chk}                       # Value.strip() == chk
    'UPPER',        # {'$upper': chk}                       # Value.upper() == chk
})

TRANSFORM_OPS = frozenset({
    '$abs',     # abs()                   -3.14         -> 3.14
    '$ceil',    # math.ceil(va)           1.1           -> 2
    '$floor',   # math.floor(val)         1.9           -> 1
    '$round',   # math.round(val)         1.5           -> 2    
    #----
    '$float',   # float(str/int)          1             -> 1.
    '$int',     # int(str/float)          1.1           -> 1    
    '$neg',     # -val                    1.2           -> -1.2    
    '$str',     # str()                   1             -> '1'
    #----
    '$avg',     # arithmetic mean         [1,2,3]       -> 2.0
    '$std',     # population std-dev      [2,4,4,4,5,5,7,9] -> 2.0
    '$max',     # max(iterable)           [3,1,4]       -> 4
    '$mid',     # middle element/char     [1,0,4,5,3]   -> 4  (index len//2)
    '$min',     # min(iterable)           [3,1,4]       -> 1
    '$sum',     # sum(iterable)           [3,1,4]       -> 8
    #----
    '$first',   # first item/char         [1,2,3]       -> 1
    '$flat',    # flat(iterable)          [[1,2],[2,3]] -> [1,2,2,3]
    '$last',    # last item/char          [1,2,3]       -> 3
    '$len',     # len()                   [1,2,3]       -> 3
    '$sort',    # sorted(val)             [2,3,1]       -> [1,2,3]
    '$unique',  # order-presrving dedup   [2,2,3,1,1]   -> [2,3,1]
    #----
    '$lower',   # lower()                 'Alice'       -> 'alice'
    '$upper',   # upper()                 'alice'       -> 'ALICE'
    '$strip',   # strip()                 '  hi  '      -> 'hi'
})

@lru_cache(maxsize=256)
def _compile_rule(rule:str, flags:int=0) -> Pattern:
    """Compile and cache a regular expression pattern.

    Args:
        rule (str): The regular expression string to compile.
        flags (int, optional): Regex flags (e.g., ``re.IGNORECASE``). Defaults to 0.

    Returns:
        re.Pattern: The compiled regular expression object.
    """
    return re_compile(rule, flags=flags)

@lru_cache(maxsize=256)
def _compile_path_glob(pattern: str) -> Pattern:
    """Compile and cache a glob-style path pattern into a regular expression.

    Converts single-character wildcards (``?``) to regex dots (``.``) and 
    standardises greedy asterisks (``*``) for dictionary key matching.

    Args:
        pattern (str): The glob pattern string (e.g., ``'addr*'`` or ``'*c?ty'``).

    Returns:
        re.Pattern: The compiled regular expression object for exact path matching.
    """
    return re_compile(f'^{PATH_RE_sub(".*", pattern.replace("?", "."))}$')

@lru_cache(maxsize=256)
def _lower_cmd(cmd:str) -> Tuple[bool,bool,str]:
    """Parse a command string to identify operator flags and negation.

    Determines if the command is negated (starts with ``!``) and if it is 
    a built-in operator (starts with ``$``). Automatically lowercases the 
    operator name for standardized evaluation.

    Args:
        cmd (str): The command key to evaluate (e.g., ``'$gt'``, ``'!$eq'``, ``'name'``).

    Returns:
        Tuple[bool, bool, str]: A tuple containing:
            * ``reverse_it`` (bool): ``True`` if the command starts with ``!``.
            * ``is_cmd`` (bool): ``True`` if the string indicates an operator (starts with ``$``).
            * ``cmd_string`` (str): The parsed, lowercased command string (or original key).

    Example:
        >>> _lower_cmd('!$EQ')
        (True, True, '$eq')
        >>> _lower_cmd('username')
        (False, False, 'username')
    """
    reverse_it = cmd.startswith('!')
    cmd = cmd[1:] if reverse_it else cmd
    if cmd and cmd[0] == '$':
        return reverse_it, True, cmd.lower()

    return reverse_it, False, cmd

#-----------------------------------------------------------------------------
_CONDITION_DEFAULTS = {'$and': [], '$or': [], '$not': {}}

class Condition(dict):
    """Represents a logical query condition, inheriting from ``dict``.

    Provides overloaded bitwise operators to easily combine multiple query 
    conditions using MongoDB-style logical operators (``$and``, ``$or``, ``$not``).
    """

    __slots__ = ()

    def copy(self) -> Condition:
        """Create a shallow copy of the Condition.

        Returns:
            Condition: A new Condition instance with identical key-value pairs.
        """
        return Condition(super().copy())

    def __missing__(self, key:str) -> None: # pragma: no cover
        """Handle missing keys by providing default empty structures for logical operators.

        Args:
            key (str): The requested dictionary key.

        Returns:
            Any: ``[]`` for ``$and``/``$or``, or ``{}`` for ``$not``.

        Raises:
            KeyError: If the key is not a recognized logical operator.
        """
        if key in _CONDITION_DEFAULTS:
            return _CONDITION_DEFAULTS[key]
        raise KeyError(key)

    def __and__(self, other:Condition) -> Condition:
        """Combine two conditions using the logical AND (``&``) operator.

        Args:
            other (Condition): The condition to combine with the current one.

        Returns:
            Condition: A new Condition wrapped in an ``$and`` operator array.
        """
        left  = self['$and']  if '$and' in self and len(self) == 1 else [dict(self)]
        right = other['$and'] if '$and' in other and len(other) == 1 else [dict(other)]
        return Condition({'$and': left + right})

    def __or__(self, other:Condition) -> Condition:
        """Combine two conditions using the logical OR (``|``) operator.

        Args:
            other (Condition): The condition to combine with the current one.

        Returns:
            Condition: A new Condition wrapped in an ``$or`` operator array.
        """
        left  = self['$or']  if '$or' in self  and len(self) == 1 else [dict(self)]
        right = other['$or'] if '$or' in other and len(other) == 1 else [dict(other)]
        return Condition({'$or': left + right})

    def __invert__(self) -> Condition:
        """Negate the current condition using the logical NOT (``~``) operator.

        Returns:
            Condition: A new Condition wrapped in a ``$not`` operator dictionary.
        """
        return Condition({'$not': dict(self)})

    def __repr__(self) -> str:
        return f'Condition({dict.__repr__(self)})'

class Query:
    """A builder class for constructing MongoDB-style query dictionaries safely.

    Provides a fluent, Pythonic interface to generate query filters using 
    magic methods (``==``, ``>``) and chained method calls.

    Args:
        _path (str, optional): The initial path segment for the query. Defaults to ``''``.

    Example:
        >>> q = Query()
        >>> condition = (q.age > 18) & (q.name.startswith("Al"))
        >>> print(condition)
        Condition({'$and': [{'age': {'$gt': 18}}, {'name': {'$sw': 'Al'}}]})
    """
    __slots__ = ('_path', )

    def __init__(self, _path:str = ''):
        object.__setattr__(self, '_path', _path)

    def __getattr__(self, name:str) -> Query:
        """Extend the query path using attribute access (e.g., ``q.user.name``)."""
        path = self._path
        return Query(f'{path}.{name}' if path else name)

    def __getitem__(self, segment:Any) -> Query:
        """Extend the query path using item access (e.g., ``q['user']['name']``)."""
        path = self._path
        seg  = str(segment)
        return Query(f'{path}.{seg}' if path else seg)

    def _cond(self, op:str, val:Any) -> Condition:
        """Internal helper to construct a Condition dictionary for a specific operator."""
        path = self._path
        return Condition({path: {op: val}} if path else {op: val})

    def __eq__(self, val:Any) -> Condition:
        """Build an equality condition (``==``)."""
        path = self._path
        return Condition({path: val} if path else {}) if path else NotImplemented

    def __ne__(self, val:Any) -> Condition:
        """Build a not-equal condition (``!=``). Maps to ``$ne``."""
        return self._cond('$ne', val)

    def __gt__(self, val:Any) -> Condition:
        """Build a greater-than condition (``>``). Maps to ``$gt``."""
        return self._cond('$gt', val)

    def __ge__(self, val:Any) -> Condition:
        """Build a greater-than-or-equal condition (``>=``). Maps to ``$gte``."""
        return self._cond('$gte', val)

    def __lt__(self, val:Any) -> Condition:
        """Build a less-than condition (``<``). Maps to ``$lt``."""
        return self._cond('$lt', val)

    def __le__(self, val:Any) -> Condition:
        """Build a less-than-or-equal condition (``<=``). Maps to ``$lte``."""
        return self._cond('$lte', val)

    def __repr__(self) -> str:
        return f"Query('{self._path}')"

    def has(self, val:Union[str,tuple]) -> Condition:
        """Check if the target string or collection contains the value. Maps to ``$has``."""
        return self._cond('$has', val)

    def ihas(self, val:Union[str,tuple]) -> Condition:
        """Check if the target string contains the value (case-insensitive). Maps to ``$ihas``."""
        return self._cond('$ihas', val)

    def not_has(self, val:Union[str,tuple]) -> Condition:
        """Check if the target string or collection does *not* contain the value. Maps to ``$nhas``."""
        return self._cond('$nhas', val)

    def startswith(self, prefix:Union[str,tuple]) -> Condition:
        """Check if the target string starts with the given prefix. Maps to ``$sw``."""
        return self._cond('$sw', prefix)

    def endswith(self, suffix:Union[str,tuple]) -> Condition:
        """Check if the target string ends with the given suffix. Maps to ``$ew``."""
        return self._cond('$ew', suffix)

    def between(self, lo:Union[str,int,float], hi:Union[str,int,float]) -> Condition:
        """Check if the target value falls strictly between two bounds. Maps to ``$between``."""
        return self._cond('$between', (lo, hi))

    def near(self, target:Union[int,float], tol:Union[int,float]) -> Condition:
        """Check if the target value is within a specified tolerance of a number. Maps to ``$near``."""
        return self._cond('$near', (target, tol))

    def mod(self, div:Union[int,float], rem:Union[int,float]) -> Condition:
        """Check if the target value divided by ``div`` leaves a remainder of ``rem``. Maps to ``$mod``."""
        return self._cond('$mod', (div, rem))

    def size_of(self, size:Union[int,Tuple[int]]) -> Condition:
        """Check if the length of the target collection matches the given size. Maps to ``$size``."""
        return self._cond('$size', size)

    def exists(self, fields:Union[Any,Tuple[Any]]) -> Condition:
        """Check if the specified keys/fields exist in the target dictionary. Maps to ``$exists``."""
        return self._cond('$exists', fields)

    def type_of(self, _type:str) -> Condition:
        """Check if the target value matches a specific data type. Maps to ``$type``."""
        return self._cond('$type', _type)

    def any_in(self, col:Union[tuple,list,set]) -> Condition:
        """Check if *any* element of the target iterable exists within the provided collection. Maps to ``$anyin``."""
        return self._cond('$anyin', col)

    def matches(self, pattern:Union[str,Pattern], flags:int=0) -> Condition:
        """Check if the target string contains a regex pattern match. Maps to ``$re``."""
        rx = _compile_rule(pattern, flags) if isinstance(pattern, str) else pattern
        return self._cond('$re', rx)

    def fullmatch(self, pattern:Union[str,Pattern], flags:int=0) -> Condition:
        """Check if the target string perfectly matches a regex pattern. Maps to ``$match``."""
        rx = _compile_rule(pattern, flags) if isinstance(pattern, str) else pattern
        return self._cond('$match', rx)

    def test(self, func:Union[Callable[[Any],bool],Callable[[str,Any],bool]]) -> Condition:
        """Evaluate the target using a custom callback function. Maps to ``$func``."""
        return self._cond('$func', func)

    def one_of(self, collection:Any) -> Condition:
        """Check if the target value exists within the provided collection. Maps to ``$in``."""
        return self._cond('$in', collection)

    def not_in(self, collection:Any) -> Condition:
        """Check if the target value does *not* exist within the provided collection. Maps to ``$nin``."""
        return self._cond('$nin', collection)

    def lower(self) -> Query:
        """Apply ``str.lower()`` in the path chain. Maps to ``$lower``.

        Example:
            >>> Query().name.lower().has('alice')
            Condition({'name.$lower': {'$has': 'alice'}})
        """
        path = self._path
        return Query(f'{path}.$lower' if path else '$lower')

    def upper(self) -> Query:
        """Apply ``str.upper()`` in the path chain. Maps to ``$upper``."""
        path = self._path
        return Query(f'{path}.$upper' if path else '$upper')

    def strip(self) -> Query:
        """Apply ``str.strip()`` in the path chain. Maps to ``$strip``."""
        path = self._path
        return Query(f'{path}.$strip' if path else '$strip')

    def str(self) -> Query:
        """Convert scalar to string

        Example:
            >>> Query().price.str() == "99.9"
            Condition({'price.$str': {'$eq': 99.9}})
        """
        path = self._path
        return Query(f'{path}.$str' if path else '$str')

    def int(self) -> Query:
        """Convert a number or string to an integer.

        Example:
            >>> Query().price.int() == 99
            Condition({'price.$int': {'$eq': 99}})
        """
        path = self._path
        return Query(f'{path}.$int' if path else '$int')

    def float(self) -> Query:
        """Convert a number or string to an floating point.

        Example:
            >>> Query().price.float() == 99.9
            Condition({'price.$float': {'$eq': 99.9}})
        """
        path = self._path
        return Query(f'{path}.$float' if path else '$float')

    def abs(self) -> Query:
        """Apply ``abs()`` in the path chain. Maps to ``$abs``.
        
        Example:
            >>> Query().delta.abs_() < 0.1
            Condition({'delta.$abs': {'$lt': 0.1}})
        """
        path = self._path
        return Query(f'{path}.$abs' if path else '$abs')

    def ceil(self) -> Query:
        """Return the ceiling of x as an Integral.

        Example:
            >>> Query().price.ceil() == 10
            Condition({'price.$ceil': {'$eq': 10}})
        """
        path = self._path
        return Query(f'{path}.$ceil' if path else '$ceil')

    def floor(self) -> Query:
        """Return the floor of x as an Integral.

        Example:
            >>> Query().price.floor() == 10
            Condition({'price.$floor': {'$eq': 10}})
        """
        path = self._path
        return Query(f'{path}.$floor' if path else '$floor')

    def round(self) -> Query:
        """Round a number to a given precision in decimal digits.

        Example:
            >>> Query().price.round() == 10
            Condition({'price.$round': {'$eq': 10}})
        """
        path = self._path
        return Query(f'{path}.$round' if path else '$round')

    def len(self) -> Query:
        """Apply ``len()`` in the path chain. Maps to ``$len``.

        Works on ``str``, ``list``, ``tuple``, ``dict``, ``set``, ``bytes``.

        Example:
            >>> Query().tags.len_() >= 3
            Condition({'tags.$len': {'$gte': 3}})
        """
        path = self._path
        return Query(f'{path}.$len' if path else '$len')

    def sum(self) -> Query:
        """Apply ``sum()`` in the path chain. Maps to ``$sum``.

        Works on ``str``, ``list``, ``tuple``, ``dict``, ``set``, ``bytes``.

        Example:
            >>> Query().tags.sum() == 3
            Condition({'tags.$sum': 3})
        """
        path = self._path
        return Query(f'{path}.$sum' if path else '$sum')

    def min(self) -> Query:
        """Apply ``min()`` in the path chain. Maps to ``$min``.

        Applicable to non-string iterables (``list``, ``tuple``, ``set``).

        Example:
            >>> Query().scores.min_() >= 60
            Condition({'scores.$min': {'$gte': 60}})
        """
        path = self._path
        return Query(f'{path}.$min' if path else '$min')

    def max(self) -> Query:
        """Apply ``max()`` in the path chain. Maps to ``$max``.
        
        Example:
            >>> Query().scores.max_() == 100
            Condition({'scores.$max': {'$eq': 100}})
        """
        path = self._path
        return Query(f'{path}.$max' if path else '$max')

    def avg(self) -> Query:
        """Apply arithmetic mean in the path chain. Maps to ``$avg``.

        Returns ``None`` (no-match) for empty sequences.

        Example:
            >>> Query().scores.avg().between(70, 90)
            Condition({'scores.$avg': {'$between': (70, 90)}})
        """
        path = self._path
        return Query(f'{path}.$avg' if path else '$avg')

    def std(self) -> Query:
        """Apply population standard deviation in the path chain. Maps to ``$std``.

        Uses population std-dev (divides by ``n``).  Returns ``0.0`` for
        single-element sequences and ``None`` for empty ones.

        Example:
            >>> Query().readings.std() < 2.0
            Condition({'readings.$std': {'$lt': 2.0}})
        """
        path = self._path
        return Query(f'{path}.$std' if path else '$std')

    def mid(self) -> Query:
        """Return the middle element/character in the path chain. Maps to ``$mid``.

        Uses index ``len(val) // 2``.  Works on ``list``, ``tuple``, ``str``,
        ``bytes``.

        Example:
            >>> Query().tags.mid() == 'python'
            Condition({'tags.$mid': {'$eq': 'python'}})
        """
        path = self._path
        return Query(f'{path}.$mid' if path else '$mid')

    def neg(self) -> Query:
        """Convert a number or string to an negative integer.

        Example:
            >>> Query().price.neg() == -99
            Condition({'price.$neg': {'$eq': -99}})
        """
        path = self._path
        return Query(f'{path}.$neg' if path else '$neg')

    def first(self) -> Query:
        """Extracts the first item or character** before comparing. Maps to ``$first``."""
        path = self._path
        return Query(f'{path}.$first' if path else '$first')

    def last(self) -> Query:
        """Extracts the last item or character** before comparing. Maps to ``$last``."""
        path = self._path
        return Query(f'{path}.$last' if path else '$last')

    def flat(self) -> Query:
        """Flattens a nested iterable before comparing. Maps to ``$flat``."""
        path = self._path
        return Query(f'{path}.$flat' if path else '$flat')

    def sort(self) -> Query:
        """Sort the iterable values before comparing. Maps to ``$sort``."""
        path = self._path
        return Query(f'{path}.$sort' if path else '$sort')

    def unique(self) -> Query:
        """Performs order-preserving deduplication on an iterable before comparing. Maps to ``$unique``."""
        path = self._path
        return Query(f'{path}.$unique' if path else '$unique')

#-----------------------------------------------------------------------------
def _apply_transform(op: str, val: Any) -> Any:
    """Apply a single in-path value-transform operator.

    These operators reshape the current value in a dot-notation path chain
    before handing it to the next segment or leaf query operator.  They
    never produce a final match/no-match decision themselves.

    Args:
        op (str): One of the ``TRANSFORM_OPS`` strings (e.g. ``'$lower'``).
        val (Any): The current value to transform.

    Returns:
        Any: The transformed value, or ``None`` if the operator is not
        applicable to this value's type (caller should treat ``None`` as
        no-match).

    Raises:
        Nothing – all internal errors are caught and surfaced as ``None``.

    Semantics of each operator:

    * ``$lower`` / ``$upper`` / ``$strip`` – ``str`` only; returns ``None``
      for non-strings.
    * ``$abs`` – ``int`` / ``float`` only.
    * ``$len`` – any object with ``__len__``; includes ``str``, ``list``,
      ``dict``, ``tuple``, ``set``.
    * ``$min`` / ``$max`` – non-string iterables only (use ``$len`` +
      comparison for character counts on strings).
    * ``$avg`` – non-string iterable; returns ``None`` for empty sequences.
    * ``$std`` – population standard deviation (divides by ``n``); returns
      ``0.0`` for a single-element sequence, ``None`` for empty.
    * ``$mid`` – returns ``val[len(val) // 2]``; works on any subscriptable
      with ``__len__`` (string, list, tuple, bytes).
    """
    try:
        if op == '$abs':
            return abs(val) if isinstance(val, (int, float)) else \
                [abs(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$avg':
            items = val if isinstance(val, (list, tuple, set)) else \
                    (val,) if val.__hash__ else ()

            n = len(items)
            return sum(items) / n if n else None

        if op == '$ceil':
            return ceil(val) if isinstance(val, (str,bytes,bool,float)) else \
                val if isinstance(val, int) else \
                [ceil(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$flat':
            if not isinstance(val, (list, tuple)): return None
            result = []
            for item in val:
                if isinstance(item, (list, tuple)):
                    result.extend(item)
                else:
                    result.append(item)
            return result

        if op == '$float':
            return float(val) if isinstance(val, (str,bytes,int,bool)) else \
                val if isinstance(val, float) else \
                [float(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$floor':
            return floor(val) if isinstance(val, (str,bytes,bool,float)) else \
                val if isinstance(val, int) else \
                [floor(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$first':
            return val[:1] if isinstance(val, (str,bytes)) else \
                val[0] if isinstance(val, (list,tuple)) else \
                next(iter(val), None) if hasattr(val, '__iter__') else None

        if op == '$last':
            return val[-1:] if isinstance(val, (str,bytes)) else \
                val[-1] if isinstance(val, (list,tuple)) else \
                tuple(val)[-1] if hasattr(val, '__iter__') else None

        if op == '$len':
            return len(val) if hasattr(val, '__len__') else None

        if op == '$lower':
            return val.lower() if isinstance(val, str) else \
                [vv.lower() for vv in val] if hasattr(val, '__iter__') else None

        if op == '$int':
            return int(val) if isinstance(val, (str,bytes,float,bool)) else \
                val if isinstance(val, int) else \
                [int(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$max':
            return max(val) if isinstance(val, (list, tuple, set)) else \
                    val if val.__hash__ else None

        if op == '$mid':
            items = val if isinstance(val, (list, tuple)) else \
                    list(val) if isinstance(val, set) else \
                    (val,) if val.__hash__ else ()

            n = len(val) if hasattr(val, '__len__') else None
            return val[n // 2] if n else None

        if op == '$min':
            return min(val) if isinstance(val, (list, tuple, set)) else \
                    val if val.__hash__ else None

        if op == '$neg':
            return -val if isinstance(val, (int,float)) else \
                -float(val) if isinstance(val, str) and val.find('.') >= 0 else \
                -int(val) if isinstance(val, str) else \
                [-int(vv) if isinstance(vv, int) else \
                -float(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$sort':
            return sorted(val) if isinstance(val, (list, tuple, set, frozenset)) else None

        if op == '$std':
            items = val if isinstance(val, (list, tuple, set)) else \
                    (val,) if val.__hash__ else ()

            n = len(items)
            if n == 0: return None
            if n == 1: return 0.0
            mean = sum(items) / n
            return (sum((x - mean) ** 2 for x in items) / n) ** 0.5

        if op == '$str':
            return val if isinstance(val, str) else \
                str(val) if isinstance(val, (bytes,int,float,bool)) else \
                [str(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$strip':
            return val.strip() if isinstance(val, str) else \
                [vv.strip() for vv in val] if hasattr(val, '__iter__') else None

        if op == '$sum':
            return sum(val) if isinstance(val, (list, tuple, set)) else \
                    val if val.__hash__ else None

        if op == '$round':
            return round(val) if isinstance(val, (str,bytes,bool,float)) else \
                val if isinstance(val, int) else \
                [round(vv) for vv in val] if hasattr(val, '__iter__') else None

        if op == '$unique':
            if isinstance(val, (str, bytes, int, float)): return None
            if isinstance(val, (dict, set, frozenset)): return val
            if isinstance(val, (list, tuple)):
                seen = set()
                result = []
                for v in val:
                    if v not in seen:
                        seen.add(v)
                        result.append(v)
                return result

            return None

        if op == '$upper':
            return val.upper() if isinstance(val, str) else \
                [vv.upper() for vv in val] if hasattr(val, '__iter__') else None

    except (TypeError, ValueError, IndexError, ZeroDivisionError, AttributeError): # pragma: no cover
        return None

    return None

def match_KEY_rules(key:str, rules:Any, level:int=0) -> bool:
    """Evaluate whether a document key matches a specified set of rules or MongoDB-like operators.

    Supports various operations including comparative (``$gt``, ``$ge``, ``$lt``, ``$le``), 
    equality (``$eq``, ``$ne``), inclusion (``$in``, ``$has``), regular expressions 
    (``$re``, ``$re2``), custom functions (``$func``), string matching (``$sw``, ``$ew``), 
    size constraints (``$size``), and logical operators (``$not``, ``$or``, ``$nor``, ``$and``).

    Args:
        key (str): The string key to be evaluated.
        rules (Any): A dictionary of operators mapping to their conditions, or a direct 
            match condition (e.g., string, regex pattern, callable).
        level (int, optional): The current recursion depth. Defaults to 0.
    
    Returns:
        bool: ``True`` if the key satisfies all specified rules, ``False`` otherwise.

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
        reverse_it, is_cmd, cmd = _lower_cmd(cmd)
        if is_cmd:
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
                    _rules.append(_compile_rule(rule))

                elif isinstance(rule, (dict, list, tuple, set, frozenset)): # pragma: no cover
                    for _rule in rule:
                        if isinstance(_rule, Pattern):
                            _rules.append(_rule)
                        elif isinstance(_rule, str):
                            _rules.append(_compile_rule(_rule))

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
                    try:
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

            elif cmd in TRANSFORM_OPS:
                transformed = _apply_transform(cmd, key)
                if transformed is not None:
                    is_matched = match_KEY_rules(transformed, rule, level=level+1)
                    is_matched = (not is_matched) if reverse_it else is_matched
            else:
                for sep in './|\\':
                    idx = cmd.find(sep)
                    if idx < 0: continue
                    parts = cmd.split(sep)
                    _key = key
                    _rule = rule
                    _check = True
                    _reverse_it = reverse_it
                    _size = len(parts)
                    for ii, part in enumerate(parts):
                        __reverse_it = part.startswith('!')
                        _part = part[1:] if __reverse_it else part
                        if _part in TRANSFORM_OPS:
                            transformed = _apply_transform(_part, _key)
                            if transformed is None: # pragma: no cover
                                _check = False
                                break
                            _key = transformed
                        elif ii+1 >= _size:
                            _rule = {_part: _rule}
                        else: # pragma: no cover
                            _check = False
                            break
                        _reverse_it = (not _reverse_it) if __reverse_it else _reverse_it

                    if _check:
                        is_matched = match_KEY_rules(_key, _rule, level=level+1)
                        is_matched = (not is_matched) if _reverse_it else is_matched
                    break

        elif cmd == '_id': # pragma: no cover
            is_matched = match_KEY_rules(key, rule, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        if not is_matched: return False

    return True

def match_DATE_rules(cdate:dt_date, mdate:dt_date, rules:Any, level:int=0) ->bool:
    """Evaluate whether a document's creation or modification date matches a set of rules.

    Supports operations such as ``$gt``, ``$ge``, ``$lt``, ``$le``, ``$eq``, ``$ne``, 
    ``$in``, ``$has``, ``$re``, ``$func``, logical grouping, and time-deltas. If `rules` 
    is provided as an integer, it evaluates a date range relative to today (e.g., ``0`` for 
    today, positive for future windows, negative for past windows).

    Args:
        cdate (datetime.date): The created date of the key/document.
        mdate (datetime.date): The modified date of the key/document.
        rules (Any): A dictionary of operators and their targets, a date object, 
            an integer (representing a day offset from today), or a direct match condition.
        level (int, optional): The current recursion depth. Defaults to 0.
    
    Returns:
        bool: ``True`` if the dates satisfy all specified rules, ``False`` otherwise.

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
                    rules = {'$has': date_list[0]}
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
        reverse_it, is_cmd, cmd = _lower_cmd(cmd)
        if is_cmd:
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
                    _rules.append(_compile_rule(rule))

                elif isinstance(rule, (dict, list, tuple, set, frozenset)): # pragma: no cover
                    for _rule in rule:
                        if isinstance(_rule, Pattern):
                            _rules.append(_rule)
                        elif isinstance(_rule, str):
                            _rules.append(_compile_rule(_rule))

                if _rules:
                    date_s = JSON_RE_sub('', date_s) if cmd[-1] == '2' else date_s
                    use_fullmatch = cmd == '$match'
                    for _rule in _rules:
                        is_matched = _rule.fullmatch(date_s) if use_fullmatch else _rule.search(date_s)
                        if not is_matched:
                            break

                    is_matched = (not is_matched) if reverse_it else is_matched

            elif cmd == '$func':
                if callable(rule):
                    try:
                        is_matched = (not rule(cdate, mdate)) if reverse_it else rule(cdate, mdate)
                    except Exception as e: # pragma: no cover
                        print(e)

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

        elif cmd == '_date': # pragma: no cover
            is_matched = match_DATE_rules(cdate, mdate, rule, level=level+1)
            is_matched = (not is_matched) if reverse_it else is_matched

        if not is_matched: return False

    return True

def match_VAL_rules(key:str, val:Any, rules:Any, cdate:dt_date, mdate:dt_date, level:int=0, ANY:bool=False, ALL:bool=False) -> bool:
    """Evaluate whether a data value matches a set of rules or MongoDB-like operators.

    This function performs deep evaluation of values, supporting nested dictionaries, 
    iterables, and path wildcards. It supports an extensive list of operators including 
    comparisons (``$gt``, ``$gte``), array operators (``$any``, ``$all``, ``$none``, 
    ``$size``, ``$anyin``), string queries (``$has``, ``$sw``, ``$re``), type checking 
    (``$type``), existence (``$exists``), and complex logic (``$and``, ``$or``).

    When applied to iterables (except strings/bytes) alongside ``ANY`` or ``ALL``, 
    the evaluation recurses through the elements.

    Args:
        key (str): The key associated with the value being evaluated.
        val (Any): The actual data value to be checked.
        rules (Any): A dictionary of evaluation rules/operators or a direct match condition.
        cdate (datetime.date): The created date associated with the data.
        mdate (datetime.date): The modified date associated with the data.        
        level (int, optional): The current recursion depth. Defaults to 0.
        ANY (bool, optional): If ``True``, evaluates to ``True`` if *any* element in 
            an iterable value matches the rules. Defaults to ``False``.
        ALL (bool, optional): If ``True``, evaluates to ``True`` if *all* elements in 
            an iterable value match the rules. Defaults to ``False``.

    Returns:
        bool: ``True`` if the value satisfies all specified rules, ``False`` otherwise.

    Example:
        >>> rules = {'$gt': 10, '$lt': 20}
        >>> match_VAL_rules("age", 15, rules, cdate, mdate)
        True
        >>> match_VAL_rules("name", "Alice", {"$re": r"Al.*"}, cdate, mdate)
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
        reverse_it, is_cmd, cmd = _lower_cmd(cmd)
        if is_cmd:
            is_same_type = isinstance(val, type(rule)) \
                or isinstance(val, (int, float)) and isinstance(rule, (int, float)) \
                or isinstance(val, (bytes, bytearray)) and isinstance(rule, (bytes, bytearray))

            if cmd == '$gt':
                try:
                    if is_same_type:
                        is_matched = (val <= rule) if reverse_it else (val > rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$gte', '$ge'):
                try:
                    if is_same_type:
                        is_matched = (val < rule) if reverse_it else (val >= rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd == '$lt':
                try:
                    if is_same_type:
                        is_matched = (val >= rule) if reverse_it else (val < rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$lte', '$le'):
                try:
                    if is_same_type:
                        is_matched = (val > rule) if reverse_it else (val <= rule)
                except TypeError: # pragma: no cover
                    pass

            elif cmd in ('$eq', '$ne'):
                try:
                    if is_same_type:
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

                        if  _is_same_type:
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

                        else: # val is iterable (list/set/tuple/etc)
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
                    _rules.append(_compile_rule(rule))

                elif isinstance(rule, (dict, list, tuple, set, frozenset)): # pragma: no cover
                    for _rule in rule:
                        if isinstance(_rule, Pattern):
                            _rules.append(_rule)
                        elif isinstance(_rule, str):
                            _rules.append(_compile_rule(_rule))

                if _rules:
                    try:
                        if isinstance(val, (bytes, bytearray)):
                            val_s = val.decode('utf8')
                        elif not isinstance(val, str):
                            val_s = json_dumps(val)
                            val_s = val_s.decode('utf8') if isinstance(val_s, bytes) else val_s
                        else:
                            val_s = val

                        use_fullmatch = cmd == '$match'
                        val_s = JSON_RE_sub('', val_s) if cmd[-1] == '2' else val_s
                        for _rule in _rules:
                            is_matched = _rule.fullmatch(val_s) if use_fullmatch else _rule.search(val_s)
                            if not is_matched:
                                break

                        is_matched = (not is_matched) if reverse_it else is_matched

                    except Exception as e: # pragma: no cover
                        print(e)

            elif cmd == '$func':
                if callable(rule):
                    arg_cnt = rule.__code__.co_argcount
                    try:
                        is_matched = rule(key, val) if arg_cnt == 2 else rule(val)
                        is_matched = (not is_matched) if reverse_it else is_matched

                    except Exception as e: # pragma: no cover
                        print(e)

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
                        is_matched = all(match_VAL_rules(key, _val, rule, cdate, mdate, ALL=True, level=level+1) for _val in items)
                else:
                    is_matched = match_VAL_rules(key, val, rule, cdate, mdate, level=level+1)

                if not is_matched and isinstance(rule, dict):
                    _is_matched = False
                    if is_dict:
                        for _ref, _rule in rule.items():
                            _reverse_it, _is_cmd, _ref_l = _lower_cmd(_ref)
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

            elif cmd in TRANSFORM_OPS:
                transformed = _apply_transform(cmd, val)
                if transformed is not None:
                    is_matched = match_VAL_rules(key, transformed, rule, cdate, mdate, level=level+1)
                    is_matched = (not is_matched) if reverse_it else is_matched

            else:
                for sep in './|\\':
                    idx = cmd.find(sep)
                    if idx < 0: continue
                    parts = cmd.split(sep)
                    _val = val
                    _rule = rule
                    _check = True
                    _reverse_it = reverse_it
                    _size = len(parts)
                    for ii, part in enumerate(parts):
                        __reverse_it = part.startswith('!')
                        _part = part[1:] if __reverse_it else part
                        if _part in TRANSFORM_OPS:
                            transformed = _apply_transform(_part, _val)
                            if transformed is None:
                                _check = False
                                break
                            _val = transformed
                        elif ii+1 >= _size:
                            _rule = {_part: _rule}
                        else: # pragma: no cover
                            _check = False
                            break
                        _reverse_it = (not _reverse_it) if __reverse_it else _reverse_it

                    if _check:
                        is_matched = match_VAL_rules(key, _val, _rule, cdate, mdate, level=level+1)
                        is_matched = (not is_matched) if _reverse_it else is_matched
                    break

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
                    _rule = rule
                    _check = True
                    _reverse_it = reverse_it
                    _size = len(parts)
                    for ii,part in enumerate(parts):
                        part_s = part.lstrip(' ')
                        if part.startswith(('!$', '$')):
                            __reverse_it = part.startswith('!')
                            _part = part[1:] if __reverse_it else part
                            if _part in TRANSFORM_OPS:
                                transformed = _apply_transform(_part, _val)
                                if transformed is None: # pragma: no cover
                                    _check = False
                                    break
                                _val = transformed
                            elif ii+1 >= _size:
                                _rule = {_part: _rule}
                            else: # pragma: no cover
                                _check = False
                                break
                            _reverse_it = (not _reverse_it) if __reverse_it else _reverse_it

                        elif isinstance(_val, dict):
                            _val = _val[part_s]
                        elif isinstance(_val, (list, tuple)):
                            _val = _val[int(part_s)]
                        else: # pragma: no cover
                            _check = False
                            break

                    if _check:
                        _cnt += 1
                        is_matched = match_VAL_rules(key, _val, _rule, cdate, mdate, level=level+1)
                        is_matched = (not is_matched) if _reverse_it else is_matched
                    break

                except (KeyError, IndexError, ValueError, TypeError): # pragma: no cover
                    pass

            if _cnt == 0 and ('*' in cmd or '?' in cmd):
                is_matched = _match_PATH([cmd], key, val, rule, cdate, mdate, level=level+1)
                is_matched = (not is_matched) if reverse_it else is_matched

        if not is_matched: return False

    return True

def _iter_all_node(node:Any) -> Generator[Any]:
    """Recursively traverse and yield every node in a nested structure.

    Navigates through nested dictionaries, lists, and tuples, yielding the 
    root node followed by all child elements recursively.

    Args:
        node (Any): The root structure to traverse (e.g., ``dict``, ``list``, or scalar).

    Yields:
        Generator[Any, None, None]: An iterator that yields each nested element.
    """

    yield node

    if isinstance(node, dict):
        for v in node.values():
            yield from _iter_all_node(v)

    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _iter_all_node(v)

def _match_PATH(key_parts:List[str], key:str, val: Any, rules:Any, cdate:dt_date, mdate:dt_date, level:int) -> bool:
    """Recursively navigate a value following path segments to apply filter rules.
    
    Supports resolving complex dictionary/list hierarchies using literals, indexes, 
    wildcards (``*``, ``**``, ``?``), and glob patterns (e.g., ``addr*``, ``*city``). 
    The function applies 'ANY' semantics: it returns ``True`` if any matching resolved 
    path satisfies the given rules.

    Args:
        key_parts (List[str]): Ordered list of remaining path segments to traverse, typically 
            produced by splitting a delimited path string (e.g. ``'addr*.city'`` becomes 
            ``['addr*', 'city']``). Supported segment types include:

            * **Literal string:** Exact dictionary key lookup.
            * **Integer string:** Zero-based index for list/tuple access.
            * **``?`` wildcard:** - On dict: Matches keys of exactly N characters (e.g. ``??`` matches 2-char keys).
              - On list: Selects the N-th decade of indices (e.g. ``?`` = 0–9, ``??`` = 10-19).
            * **``*`` wildcard:** Expands to every dictionary value or sequence element.
            * **``**`` wildcard:** Recursively expands to every node in the structure.
            * **Glob pattern:** A string with ``*`` matched against dict keys (e.g. ``a*z``).
            * **Operator segment:** Starts with ``$`` or ``!$``, applied as a query operator 
              at the leaf. Add a leading space to treat as a literal key.

        key (str): The original key associated with the root value.
        val (Any): The current node's data value during traversal.
        rules (Any): A dictionary of rules/operators or a direct match condition.
        cdate (datetime.date): The created date associated with the data.
        mdate (datetime.date): The modified date associated with the data.        
        level (int): The current recursion depth.
        
    Returns:
        bool: ``True`` if any navigated path satisfies the rules, ``False`` otherwise.

    Example:
        >>> _match_PATH(['addr*', 'city'], 'user', user_dict, {'$eq': 'Paris'}, cdate, mdate, 0)
        True
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
                child_vals = val.values() # any field
            else:
                # Glob -> regex : 'addr*' -> r'^addr.*$'
                rx = _compile_path_glob(child_key_s)
                child_vals = (v for k,v in val.items() if rx.match(k))

        elif isinstance(val, (list, tuple)):
            if child_key_s in ('*', '?*', '*?'):
                child_vals = val
            elif child_key_s.startswith('?'):
                _cnt = child_key_s.count('?')
                if _cnt == len(child_key_s):
                    child_vals = (_val for ii,_val in enumerate(val) if (ii//10)+1 == _cnt)

        return any(_match_PATH(rest_parts, key, child_val, rules, cdate, mdate, level) for child_val in child_vals) if child_vals else False

    else:
        try:
            if child_key.startswith(('!$', '$')):
                _reverse_it = child_key.startswith('!')
                _child_key = child_key[1:] if _reverse_it else child_key
                if _child_key in TRANSFORM_OPS: # pragma: no cover
                    transformed = _apply_transform(_child_key, val)
                    if transformed is None:
                        return False

                    val = transformed

                if not rest_parts:
                    rules = {child_key:rules}
                    child_val = val
                else: # pragma: no cover
                    return False

            elif isinstance(val, dict):
                child_val = val[child_key_s]
            elif isinstance(val, (list, tuple)):
                child_val = val[int(child_key_s)]
            else: # pragma: no cover
                return False

            return _match_PATH(rest_parts, key, child_val, rules, cdate, mdate, level)

        except (KeyError, IndexError, ValueError, TypeError): # pragma: no cover
            pass

        return False

#
