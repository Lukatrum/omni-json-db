# pylint: disable=broad-except,ungrouped-imports
"""Dataclass <-> record conversion (used by :meth:`JDb.f_write_dc` / :meth:`JDbReader.f_read_dc`).

A dataclass is stored as a plain ``dict`` -- its ``id`` field lifted out to
become the record key -- so values stay queryable by :class:`Query` and readable
under every data_type, unlike pickle's opaque Python-only blob.
"""
from typing import Any, Union, Optional, Tuple, Dict, get_type_hints
from datetime import date as dt_date, datetime, time as dt_time
from dataclasses import MISSING as DC_MISSING, fields as dc_fields, is_dataclass
from decimal import Decimal
from enum import Enum
from functools import lru_cache
from pathlib import PurePath, Path
from uuid import UUID
try:
    from types import UnionType # py3.10+ "int | None"
except ImportError: # pragma: no cover
    UnionType = None

try:
    from typing import get_args, get_origin # py3.8+
except ImportError: # pragma: no cover
    def get_origin(tp:Any) -> Any:
        """py3.7 fallback: ``List[str]`` -> ``list``, ``Optional[X]`` -> ``typing.Union``."""
        return getattr(tp, '__origin__', None)

    def get_args(tp:Any) -> tuple:
        """py3.7 fallback: ``Dict[str, int]`` -> ``(str, int)``."""
        return getattr(tp, '__args__', ()) or ()
#---------------------------------------------------------------------
from .utils import JValueError, JTypeError, deepcopy
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
DC_ID = 'id' # the mandatory primary-key field name

__all__ = ('DC_ID', 'is_dc', 'dc_key', 'dc_to_dict', 'dc_value', 'dc_fill', 'dc_records', 'dc_keys')

#-----------------------------------------------------------------------------
def is_dc(obj:Any) -> bool:
    """Return True if ``obj`` is a dataclass *instance* (not the class itself)."""
    return is_dataclass(obj) and not isinstance(obj, type)

@lru_cache(maxsize=256)
def _dc_meta(cls:type) -> Tuple[Dict[str,Any], Tuple[str, ...], bool]:
    """Cache ``(annotations, value-field names, has-id)`` for one dataclass.

    ``value-field names`` excludes :data:`DC_ID`, which is stored as the record
    key rather than inside the value. Unresolvable forward refs fall back to the
    raw annotation strings, in which case :func:`_decode` passes those values
    through untouched instead of raising.
    """
    try:
        hints = get_type_hints(cls)

    except Exception: # pragma: no cover -- e.g. a dataclass declared inside a function
        hints = {f.name: f.type for f in dc_fields(cls)}

    names = tuple(f.name for f in dc_fields(cls))
    return hints, tuple(n for n in names if n != DC_ID), DC_ID in names

#-----------------------------------------------------------------------------
def _encode(val:Any) -> Any:
    """Recursively convert one field value into something every JDb codec accepts."""
    if val is None or type(val) in (str, int, float, bool, bytes):
        return val

    if isinstance(val, Enum): # must precede the primitive check: str/IntEnum are subclasses
        return _encode(val.value)

    if is_dataclass(val) and not isinstance(val, type):
        return {f.name: _encode(getattr(val, f.name)) for f in dc_fields(val)}

    if isinstance(val, dict):
        return {(k if isinstance(k, (str,int)) else str(k)): _encode(v) for k,v in val.items()}

    if isinstance(val, (list, tuple)):
        return [_encode(v) for v in val]

    if isinstance(val, (set, frozenset)):
        return {_encode(v) for v in val}

    if isinstance(val, (datetime, dt_date, dt_time)):
        return val.isoformat()

    if isinstance(val, (Decimal, UUID, PurePath)):
        return str(val)

    if isinstance(val, (bytearray, memoryview)): # pragma: no cover
        return bytes(val)

    for base in (str, bytes, float, int):  # pragma: no cover
        # narrow a str/int subclass back to its base
        if isinstance(val, base):
            return base(val)

    raise JTypeError(f'cannot encode field type {type(val).__name__} into a JDb record')

def _detach(val:Any) -> Any:
    """Deep-copy a container that :func:`_decode` hands back untouched.

    ``f_read_dc`` reads with ``copy=False``, so a field whose annotation carries
    no type information (``Any``, a bare ``dict``/``list``, an unresolvable
    forward ref) would otherwise alias the record cache -- mutating it through
    the dataclass would silently corrupt the database.
    """
    if isinstance(val, bytearray): # deepcopy() would turn this into a list of ints
        return bytearray(val)

    return deepcopy(val) if isinstance(val, (dict, list, set)) else val

def _decode(val:Any, hint:Any) -> Any:
    """Rebuild ``val`` into the Python type described by the annotation ``hint``."""
    if hint is None or hint is Any or val is None:
        return _detach(val)

    origin = get_origin(hint)
    args = get_args(hint)
    if origin is Union or (UnionType is not None and origin is UnionType):
        for arg in args: # first annotation that round-trips wins
            if arg is type(None): # pylint: disable=unidiomatic-typecheck
                continue

            try:
                return _decode(val, arg)

            except (TypeError, ValueError, KeyError): # pragma: no cover
                continue

        return _detach(val)

    if origin is list: # a missing arg -> hint None -> _detach(): a shallow copy would alias
        return [_decode(v, args[0] if args else None) for v in val]

    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis: # pragma: no cover
            return tuple(_decode(v, args[0]) for v in val)

        return tuple(_decode(v, a) for v,a in zip(val, args)) if args else tuple(_decode(v, None) for v in val)

    if origin in (set, frozenset):
        items = (_decode(v, args[0] if args else None) for v in val)
        return frozenset(items) if origin is frozenset else set(items)

    if origin is dict:
        k_hint, v_hint = args if len(args) == 2 else (None, None)
        return {_decode(k, k_hint): _decode(v, v_hint) for k,v in val.items()}

    if not isinstance(hint, type):
        return _detach(val)

    if is_dataclass(hint):
        return _build(hint, val)

    if issubclass(hint, Enum):
        return hint(val)

    if issubclass(hint, bool):
        return bool(val)

    if issubclass(hint, datetime):
        return val if isinstance(val, datetime) else datetime.fromisoformat(val)

    if issubclass(hint, dt_date):
        return val if isinstance(val, dt_date) else dt_date.fromisoformat(val)

    if issubclass(hint, dt_time):
        return val if isinstance(val, dt_time) else dt_time.fromisoformat(val)

    if issubclass(hint, (Decimal, UUID)):
        return val if isinstance(val, hint) else hint(val)

    if issubclass(hint, PurePath):
        return val if isinstance(val, PurePath) else Path(val)

    if issubclass(hint, bytearray): # _encode() stores it as bytes, so mirror the bytes rule below
        if not isinstance(val, (bytes, bytearray, memoryview)):
            raise JValueError(f'expected bytearray, got {type(val).__name__}')

        return bytearray(val)

    if issubclass(hint, (int, float)) and not isinstance(val, bool):
        try: # also covers 'id', which always comes back as the str record key
            return hint(val)

        except (TypeError, ValueError):
            return _detach(val)

    if issubclass(hint, (str, bytes)) and not isinstance(val, hint):
        raise JValueError(f'expected {hint.__name__}, got {type(val).__name__}')

    return _detach(val)

def _build(cls:type, doc:Any) -> Any:
    """Construct a *nested* dataclass from a stored ``dict`` (top level uses :func:`dc_fill`)."""
    if not isinstance(doc, dict):
        raise JValueError(f'{cls.__name__}: expected a dict, got {type(doc).__name__}')

    hints = _dc_meta(cls)[0]
    init_kw, post = {}, {}
    for f in dc_fields(cls):
        if f.name not in doc: # pragma: no cover
            if f.default is DC_MISSING and f.default_factory is DC_MISSING: # type: ignore[misc]
                raise JValueError(f'{cls.__name__}: missing required field "{f.name}"')

            continue

        value = _decode(doc[f.name], hints.get(f.name))
        (init_kw if f.init else post)[f.name] = value

    obj = cls(**init_kw)
    for name,value in post.items(): # init=False fields, frozen-safe
        object.__setattr__(obj, name, value) # pragma: no cover

    return obj

#-----------------------------------------------------------------------------
def dc_key(obj:Any) -> str:
    """Return the record key of a dataclass instance: ``str(obj.id)``.

    Args:
        obj (Any): The dataclass instance.

    Returns:
        str: The record key. A non-str ``id`` (``int``, ``UUID`` ...) is
        stringified here and coerced back to its annotated type on read.

    Raises:
        JTypeError: If ``obj`` is not a dataclass instance.
        JValueError: If the class has no ``id`` field, or ``id`` is None/empty.
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        raise JTypeError(f'expected a dataclass instance, got {type(obj).__name__}')

    if not _dc_meta(type(obj))[2]:
        raise JValueError(f'{type(obj).__name__} has no "{DC_ID}" field (required as the record key)')

    key = getattr(obj, DC_ID)
    key = '' if key is None else str(key)
    if not key:
        raise JValueError(f'{type(obj).__name__}.{DC_ID} must not be empty')

    return key

def dc_to_dict(obj:Any, with_id:bool=False) -> dict:
    """Convert a dataclass instance into the ``dict`` stored as the record value.

    Args:
        obj (Any): The dataclass instance.
        with_id (bool, optional): Keep the ``id`` field in the dict. Defaults to
            False, because ``id`` is lifted out to become the record key.

    Returns:
        dict: A JDb-storable mapping of field name to encoded value.

    Raises:
        JTypeError: If ``obj`` is not a dataclass instance, or holds an unencodable value.
        JValueError: If ``with_id`` is set but the class has no ``id`` field.
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        raise JTypeError(f'expected a dataclass instance, got {type(obj).__name__}')

    _, names, has_id = _dc_meta(type(obj))
    doc = {name: _encode(getattr(obj, name)) for name in names}
    if with_id:
        if not has_id:
            raise JValueError(f'{type(obj).__name__} has no "{DC_ID}" field')

        doc[DC_ID] = _encode(getattr(obj, DC_ID))

    return doc

def dc_value(obj:Any, key:Any=None) -> dict:
    """Encode a dataclass for storage under an explicit ``key`` (the ``jdb[key] = obj`` form).

    ``id`` is kept inside the value only when it would otherwise be lost -- that
    is, when it is set and differs from ``key``. So ``jdb[obj.id] = obj`` stores
    exactly the same bytes as ``jdb += obj``, while ``jdb['alias'] = obj`` still
    reads back carrying its original ``id`` rather than the alias.

    Args:
        obj (Any): The dataclass instance.
        key (Any, optional): The key the record is filed under. Defaults to None,
            which always keeps ``id`` (no key to fall back on).

    Returns:
        dict: A JDb-storable mapping of field name to encoded value.

    Raises:
        JTypeError: If ``obj`` is not a dataclass instance, or holds an unencodable value.
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        raise JTypeError(f'expected a dataclass instance, got {type(obj).__name__}')

    obj_id = getattr(obj, DC_ID, None) if _dc_meta(type(obj))[2] else None
    obj_id = '' if obj_id is None else str(obj_id) # keep '0': only None/'' count as unset
    return dc_to_dict(obj, with_id=bool(obj_id) and obj_id != key)

def dc_fill(obj:Any, doc:dict, key:Optional[str]=None, strict:bool=False) -> Any:
    """Populate every member of an existing dataclass instance *in place* from ``doc``.

    Works on ``frozen=True`` dataclasses and never calls ``__init__``, so a
    partially-populated object can be reused as a read buffer across a loop.

    Args:
        obj (Any): The dataclass instance to fill.
        doc (dict): The stored record value.
        key (Optional[str], optional): Record key written back to the ``id``
            field, coerced to its annotated type. Ignored when ``doc`` already
            carries an ``id`` (see :func:`dc_value`). Defaults to None.
        strict (bool, optional): Raise on fields present in ``doc`` but not on the
            dataclass, instead of ignoring them. Defaults to False.

    Returns:
        Any: ``obj`` itself, for chaining.

    Raises:
        JTypeError: If ``obj`` is not a dataclass instance.
        JValueError: If ``doc`` is not a dict, if ``key`` is given but the class
            has no ``id`` field, or (with ``strict``) ``doc`` carries unknown fields.
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        raise JTypeError(f'expected a dataclass instance, got {type(obj).__name__}')

    if not isinstance(doc, dict):
        raise JValueError(f'{type(obj).__name__}: expected a dict record, got {type(doc).__name__}')

    hints, names, has_id = _dc_meta(type(obj))
    if strict: # pragma: no cover
        extra = set(doc) - set(names) - {DC_ID}
        if extra:
            raise JValueError(f'{type(obj).__name__}: unknown field(s) {sorted(extra)}')

    for name in names:
        if name in doc:
            object.__setattr__(obj, name, _decode(doc[name], hints.get(name)))

    if key is not None and not has_id:
        raise JValueError(f'{type(obj).__name__} has no "{DC_ID}" field')

    if has_id and (DC_ID in doc or key is not None): # a stored id wins: see dc_value()
        object.__setattr__(obj, DC_ID, _decode(doc.get(DC_ID, key), hints.get(DC_ID)))

    return obj

def dc_records(objs:Any, with_id:bool=False) -> Optional[Dict[str,dict]]:
    """Convert a dataclass instance, or any iterable of them, into ``{key: doc}``.

    Args:
        objs (Any): One dataclass instance, or a list/tuple/set of them.
        with_id (bool, optional): Keep ``id`` inside each value. Defaults to False.

    Returns:
        Optional[Dict[str, dict]]: The records, or None if ``objs`` holds no dataclass.
    """
    if is_dataclass(objs) and not isinstance(objs, type):
        return {dc_key(objs): dc_to_dict(objs, with_id)}

    if objs and isinstance(objs, (tuple, list, set, frozenset)) and all(is_dataclass(o) for o in objs):
        return {dc_key(o): dc_to_dict(o, with_id) for o in objs}

    return None

def dc_keys(objs:Any) -> Optional[Union[str, set]]:
    """Extract record key(s) from a dataclass instance or an iterable of them.

    Args:
        objs (Any): One dataclass instance, or a list/tuple/set of them.

    Returns:
        Optional[Union[str, set]]: A ``str`` for one instance, a ``set`` for many,
        or None if ``objs`` holds no dataclass.
    """
    if is_dataclass(objs) and not isinstance(objs, type):
        return dc_key(objs)

    if objs and isinstance(objs, (tuple, list, set, frozenset)) and all(is_dataclass(o) for o in objs):
        return {dc_key(o) for o in objs}

    return None

#
