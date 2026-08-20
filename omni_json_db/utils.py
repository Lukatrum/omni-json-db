# pylint: disable=too-many-lines,unused-import,pointless-statement,too-few-public-methods,consider-using-with,unnecessary-pass
from __future__ import annotations
from enum import IntFlag
from collections import defaultdict
from contextlib import contextmanager
from re import findall as re_findall, compile as re_compile
from threading import Lock, Event, Condition, get_ident
from signal import SIGINT, signal, default_int_handler # SIG_IGN
from typing import Callable, Any, Union, Tuple, List, Dict
from unicodedata import east_asian_width
#-----------------------------------------------------------------------------
try:
    import ipdb
    debug_break = ipdb.set_trace

except ImportError:
    debug_break = breakpoint

class JError(Exception):
    pass

class JKeyError(JError, KeyError):
    pass

class JValueError(JError, ValueError):
    pass

class JTypeError(JError, TypeError):
    pass

class JAttributeError(JError, AttributeError):
    pass

MISSING = object()  # 'not found' -> raise
LOCKED = object()
EXPIRED = object()  # 'found but its TTL ran out' -> drop from a (key, value) stream

#-----------------------------------------------------------------------------
KEY_FLAG_MASK = 0xFFFF # on-disk width reserved for JKeyFlag

class JKeyFlag(IntFlag):
    """Per-record flags stored inside a KEY index row.

    Supported on every API version: v2 has a dedicated field, while v0/v1 pack
    the bits above the ``days`` field (see ``KEY_FLAG_SHIFT``). The flags travel
    with the row itself, so they survive defragmentation, ``resize_keys()`` and
    swap/undelete round-trips.

    The members are documented individually below. Do not describe them again in
    a Google-style ``Attributes:`` section here: autodoc already emits one
    ``py:attribute`` per enum member, and napoleon would emit a second one from
    the section, which Sphinx reports as a duplicate object description.
    """

    #: ``'r'`` -- the record cannot be modified or deleted.
    READ_ONLY = 0x01

    #: ``'a'`` -- the value may only grow. A write is accepted only when the
    #: new value is a strict extension of the stored one (see
    #: :func:`is_value_extension`); delete and unwrite are refused. Complements
    #: :attr:`READ_ONLY`, which forbids growth as well.
    APPEND_ONLY = 0x02

    #: ``'g'`` -- the record holds a group (child) database. Always derived
    #: from the stored value, never taken from a caller's ``key_flags``.
    GROUP = 0x04

    #: ``'l'`` -- the record is a symbolic link: its stored value is the name
    #: of another record in the same database, and reads and writes are
    #: forwarded there. Like :attr:`GROUP` this describes what the VALUE is, so
    #: it is never taken from a caller's ``key_flags``; use ``set_link()``,
    #: which enforces the two invariants that keep resolution a single hop:
    #: a link may not point at a group (:attr:`GROUP`) and may not point at
    #: another link. Deleting a link removes the link alone; deleting its
    #: target leaves the link dangling, and a dangling link reads as ``None``
    #: -- use ``get_link()`` to tell "points nowhere" apart from "stores None".
    LINK = 0x08

    #: ``'h'`` -- the record is not part of the database's *default working
    #: set*, the way a dotfile is not part of a plain ``ls``.
    #:
    #: Which APIs honour it follows one rule: **an API that takes a query
    #: skips hidden records; an API that implements the mapping protocol does
    #: not.** Concretely:
    #:
    #: * **Query surfaces -- hidden by default, opt back in with**
    #:   ``with_hidden=True``: :meth:`JDbReader.find`, :meth:`JDbReader.show`,
    #:   :meth:`JDbReader.map` and ``jdb.keys(...)``.
    #: * **Query-driven side effects -- hidden by default**:
    #:   :meth:`JDb.update_if` will not rewrite or delete a hidden record, and
    #:   :meth:`JDb.to_csv` will not export one. These are the teeth of the
    #:   flag: hiding a record takes it out of reach of ``Query()``-shaped
    #:   sweeps and of the default dump.
    #: * **Mapping surfaces -- always exhaustive**: ``jdb[key]``, ``in``,
    #:   ``len()``, ``items()``, ``values()``, ``item_iter()``, ``jdb[:]``,
    #:   ``iter()``, ``==``, :meth:`JDb.check_error`, :meth:`JDb.recycle` and
    #:   :meth:`JDb.clone_to` all include hidden records, and a *key-selector*
    #:   bulk write (``jdb[re.compile(...)] = v``) still reaches them.
    #: * **Raw iterators -- exhaustive unless asked**: :meth:`JDbReader.find_iter`
    #:   and ``jdb.keys.item_iter()`` default to ``with_hidden=True``.
    #:
    #: The split is deliberate. Keeping every mapping-like API in agreement is
    #: what makes ``len(jdb) == len(dict(jdb.items()))`` hold, while the query
    #: side is where "show me the data" lives -- so that is where hiding pays
    #: off. It costs one extra key-row read only inside ``find_iter``.
    #:
    #: **This is still not access control.** A caller who wants the record can
    #: always read it by name, and ``dict(jdb.items())`` still contains it.
    #: Use it for engine bookkeeping and derived state -- :mod:`.jdb_graph`
    #: marks its adjacency lists and node/edge counters ``HIDDEN`` so a user's
    #: ``find()`` and CSV export see the graph, not its plumbing -- not for
    #: secrets.
    HIDDEN = 0x10

    #: ``'c'`` -- never place this record's value in the LRU read cache, and
    #: evict it if it is already there. For large blobs that would otherwise
    #: flush ``cache_limit`` worth of small hot records.
    NO_CACHE = 0x20

    #: ``'v'`` -- do not keep a previous version of this record. ``f_write``
    #: rewrites the row in place even when :attr:`JFlag.REVERT` is active, so a
    #: high-frequency counter does not grow the DEAD region without bound.
    #: Only applies when the row can be reused (header->header, or
    #: value->value that still fits); a write that changes the storage class
    #: must move the row and still parks the old value for reclamation.
    NO_REVERT = 0x40

    #: ``'e'`` -- the record carries a TTL. **Derived**: it is set iff the row's
    #: 9-bit ttl field (bits 39..47 of ``days``) is non-zero, and is never taken
    #: from a caller's ``key_flags`` -- use the ``ttl=`` argument of
    #: :meth:`JDb.f_write` or :meth:`JDb.set_key_flags`.
    #: While set, ``days`` switches layout: the modified-delta narrows from 22
    #: to 13 bits.
    EXPIRE = 0x80

    #: ``'p'`` -- protect the record from deletion while still allowing it to be
    #: updated. :attr:`READ_ONLY` and :attr:`APPEND_ONLY` both block deletion as
    #: well as writing, so this is the only way to express "freely editable, but
    #: never removed" -- the retention guarantee a config or account row wants.
    #:
    #: Checked through :data:`DELETE_LOCK_MASK`, so it stops :meth:`JDb.remove`,
    #: ``del jdb[key]`` and ``jdb -= jdb` alike, and :attr:`UNLOCK` waives it for
    #: one call the same way it waives the write locks.
    NO_DELETE = 0x100

    #: ``'0'`` -- free for the application. Carries no engine behaviour: it is
    #: stored, round-trips through delete/undelete and defragmentation, and can
    #: be filtered on, but nothing in JDb reads it. Use these instead of
    #: forking the enum, so a future JKeyFlag never collides with your tag.
    USER0 = 0x1000

    #: ``'1'`` -- free for the application. See :attr:`USER0`.
    USER1 = 0x2000

    #: ``'2'`` -- free for the application. See :attr:`USER0`.
    USER2 = 0x4000

    #: ``'3'`` -- free for the application. See :attr:`USER0`.
    USER3 = 0x8000

    #: ``'u'`` -- **transient**. The only JKeyFlag that is never stored: it sits
    #: above :data:`KEY_FLAG_MASK`, so every path that writes a KEY row masks it
    #: away and no record can ever carry it.
    #:
    #: Passed as ``key_flags`` to a single :meth:`JDb.f_write` / :meth:`JDb.f_delete`
    #: call -- and to anything that forwards there, such as :meth:`JDb.set`,
    #: :meth:`JDb.remove` and :meth:`JDb.pop` -- it waives the
    #: :data:`WRITE_LOCK_MASK` check for that one call, the way ``sudo`` waives a
    #: permission check for one command. The record's stored flags are left
    #: untouched, so a :attr:`READ_ONLY` record is still read-only afterwards.
    #:
    #: It waives *locks only*. Derived bits, :attr:`HIDDEN` and every other rule
    #: are unaffected, and :meth:`JDb.set_key_flags` never needed it -- changing
    #: flags is already a privileged operation.
    UNLOCK = 0x10000

    #: ``'n'`` -- **transient**. Read a :attr:`LINK` row *itself* instead of
    #: following it: the read yields the stored target path, not the target's
    #: value. This is ``open(O_NO_FOLLOW)``, not :meth:`JDbReader.get_link` -- a
    #: record that is not a link reads normally rather than reporting "not a
    #: link", which is what makes it composable with an ordinary
    #: :meth:`JDbReader.get`.
    #:
    #: The target path is never placed in the LRU cache under the link's key,
    #: so a NO_FOLLOW read can never be served to a later following read.
    #: Passed to :meth:`JDb.f_write` it *retargets* the link in place, the
    #: low-level equivalent of :meth:`JDb.set_link`; the new value must then be
    #: a ``str``.
    NO_FOLLOW = 0x20000

    #: ``'w'`` -- **transient**. Refuse the write when the key already exists,
    #: leaving the stored record untouched. The check is made under the write
    #: handle and is repeated after a concurrent-writer retry, so it is
    #: race-free where a test-then-write is not.
    #:
    #: This is what :meth:`JDb.setdefault` means, expressed precisely: the
    #: refusal is silent (``f_write`` returns ``False``), matching how
    #: :attr:`READ_ONLY` and :attr:`APPEND_ONLY` already refuse.
    EXCL = 0x40000

    #: ``'y'`` -- **transient**. Keep the record's stored *modified* day instead
    #: of stamping today. An explicit ``mdays=`` argument still wins, and a new
    #: record has no old day to keep, so this is a no-op there.
    #:
    #: A TTL is counted from ``mdays``, so writing with NO_ATIME deliberately
    #: does **not** renew an expiring record -- useful for touching a session
    #: without extending it, and a footgun everywhere else.
    NO_ATIME = 0x80000

    #: ``'m'`` -- **transient**. Refuse the write when the key does *not* already
    #: exist, the exact mirror of :attr:`EXCL`. Together the pair expresses the
    #: two halves of ``open(O_CREAT|O_EXCL)``: ``'w'`` is create-only, ``'m'`` is
    #: update-only, and neither is a read-then-write, so both are race-free where
    #: a test against :meth:`JDbReader.__contains__` is not.
    MUST_EXIST = 0x100000

    @classmethod
    def _missing_(cls, value):
        """Allow constructing flags from a letter string, mirroring ``JFlag``.

        e.g. ``JKeyFlag('ac')`` == ``APPEND_ONLY | NO_CACHE``. Unknown letters
        are ignored.

        Args:
            value (Any): The letter string (case-insensitive) or an int.

        Returns:
            JKeyFlag: The combined flag instance.
        """
        if isinstance(value, str):
            _by_letter = KEY_FLAG_BY_LETTER
            _value = 0
            for ch in value.lower():
                _value |= _by_letter.get(ch, 0)

            value = _value

        return super()._missing_(value)

    def __str__(self) -> str:
        """Return a compact string showing which flags are active.

        One position per entry of :data:`KEY_FLAG_LETTERS`, holding the flag's
        letter when set and ``'_'`` when not -- e.g. ``'r_a_v'``.

        Returns:
            str: The flag summary string.
        """
        return ''.join(ch if flag in self else '_' for flag, ch in KEY_FLAG_LETTERS.items())

KF_READ_ONLY   = int(JKeyFlag.READ_ONLY)
KF_APPEND_ONLY = int(JKeyFlag.APPEND_ONLY)
KF_GROUP       = int(JKeyFlag.GROUP)
KF_LINK        = int(JKeyFlag.LINK)
KF_HIDDEN      = int(JKeyFlag.HIDDEN)
KF_NO_CACHE    = int(JKeyFlag.NO_CACHE)
KF_NO_REVERT   = int(JKeyFlag.NO_REVERT)
KF_EXPIRE      = int(JKeyFlag.EXPIRE)
KF_NO_DELETE   = int(JKeyFlag.NO_DELETE)
KF_USER0       = int(JKeyFlag.USER0)
KF_USER1       = int(JKeyFlag.USER1)
KF_USER2       = int(JKeyFlag.USER2)
KF_USER3       = int(JKeyFlag.USER3)
KF_UNLOCK      = int(JKeyFlag.UNLOCK)
KF_NO_FOLLOW   = int(JKeyFlag.NO_FOLLOW)
KF_EXCL        = int(JKeyFlag.EXCL)
KF_NO_ATIME    = int(JKeyFlag.NO_ATIME)
KF_MUST_EXIST  = int(JKeyFlag.MUST_EXIST)

KEY_FLAG_LETTERS = {
    JKeyFlag.READ_ONLY:   'r',
    JKeyFlag.GROUP:       'g',
    JKeyFlag.APPEND_ONLY: 'a',
    JKeyFlag.NO_CACHE:    'c',
    JKeyFlag.NO_REVERT:   'v',
    JKeyFlag.LINK:        'l',
    JKeyFlag.HIDDEN:      'h',
    JKeyFlag.EXPIRE:      'e',
    JKeyFlag.NO_DELETE:   'p',
    JKeyFlag.USER0:       '0',
    JKeyFlag.USER1:       '1',
    JKeyFlag.USER2:       '2',
    JKeyFlag.USER3:       '3',
    JKeyFlag.UNLOCK:      'u',
    JKeyFlag.NO_FOLLOW:   'n',
    JKeyFlag.EXCL:        'w',
    JKeyFlag.NO_ATIME:    'y',
    JKeyFlag.MUST_EXIST:  'm',
}

KEY_FLAG_BY_LETTER  = {v: int(k) for k, v in KEY_FLAG_LETTERS.items()}

TRANSIENT_FLAG_MASK = KF_UNLOCK | KF_NO_FOLLOW | KF_EXCL | KF_NO_ATIME | KF_MUST_EXIST

TRANSIENT_FLAG_BY_LETTER = {ch: int(f) for f, ch in KEY_FLAG_LETTERS.items() if int(f) & TRANSIENT_FLAG_MASK}

WRITE_LOCK_MASK     = KF_READ_ONLY | KF_APPEND_ONLY

DELETE_LOCK_MASK    = WRITE_LOCK_MASK | KF_NO_DELETE

DERIVED_FLAG_MASK   = KF_GROUP | KF_LINK | KF_EXPIRE

REDERIVED_FLAG_MASK = KF_GROUP | KF_EXPIRE

PAYLOAD_FLAG_MASK   = DERIVED_FLAG_MASK & ~REDERIVED_FLAG_MASK

WRITABLE_FLAG_MASK  = KEY_FLAG_MASK & ~DERIVED_FLAG_MASK

USER_FLAG_MASK      = KEY_FLAG_MASK & ~KF_GROUP

def conv_to_key_flags(flags:str) -> Tuple[int,int]:
    """Parse a ``chmod``-style flag string into three masks.

    Each letter is one :class:`JKeyFlag` (see :data:`KEY_FLAG_LETTERS`),
    optionally prefixed to say what should happen to it:

    ==========  ====================================================
    Prefix      Meaning
    ==========  ====================================================
    ``+`` none  Set the flag (when writing) / require it (when querying).
    ``-``       Clear the flag / forbid it.
    ==========  ====================================================

    Parsing is case-insensitive, and letters that name no flag are ignored,
    mirroring :meth:`JKeyFlag._missing_`.

    The masks are returned separately so callers can apply them *relative* to a
    record's current flags -- ``(old | set_mask) & ~clear_mask`` -- which is what
    makes ``'-c'`` mean "clear NO_CACHE, leave everything else alone".

    Callers are responsible for masking the result with
    :data:`WRITABLE_FLAG_MASK`; this function does not, so it can also be used
    to build a mask that includes the derived :attr:`JKeyFlag.GROUP` /
    :attr:`JKeyFlag.LINK` bits for inspection.

    Args:
        flags (str): The flag string, e.g. ``'ra'``, ``'+h-c'``, ``'+0'``.
            A non-``str`` (or empty) argument yields ``(0, 0)``.

    Returns:
        Tuple[int, int]: ``(set_mask, clear_mask)``. A letter
        given more than one way ends up in each mask it was given, and when
        applied the clear wins over the set.

    Example:
        >>> conv_to_key_flags('ra')
        (3, 0)
        >>> conv_to_key_flags('+h-c')
        (16, 32)
    """
    set_mask = clr_mask = 0
    if flags:
        for flag in re_findall(r'[+\-]?[a-z0-9]', flags.lower()):
            val = KEY_FLAG_BY_LETTER.get(flag[-1:], None)
            if val is not None:
                if flag[0] == '-':
                    clr_mask |= val
                else:
                    set_mask |= val

    return set_mask, clr_mask

def pop_transient_flags(flags:Union[str,int,'JKeyFlag',None]) -> Tuple[int, Any]:
    """Split every :data:`TRANSIENT_FLAG_MASK` bit out of a caller's ``key_flags``.

    Transient flags are call-scoped, so they must be consumed before the rest of
    the argument is treated as flags to *store*. Asking only for transient
    behaviour -- ``'w'``, ``'uy'``, ``JKeyFlag.NO_ATIME`` -- has to leave the
    record's stored flags alone, which is why the remainder comes back as
    ``None`` in that case rather than an empty mask: an empty mask given as an
    ``int`` means "clear everything".

    In the string form a transient letter is consumed whichever way it was
    prefixed, but only a ``'+'``/bare letter turns the bit on -- ``'-w'`` asks
    for the default, not for a stored flag, so it must not survive into the
    remainder either.

    Args:
        flags (Union[str, int, JKeyFlag, None]): The caller's ``key_flags``.

    Returns:
        Tuple[int, Any]: ``(transient_mask, remaining_flags)``, where
        ``remaining_flags`` is safe to hand to :func:`apply_key_flags`.

    Example:
        >>> pop_transient_flags('wy') == (int(JKeyFlag.EXCL | JKeyFlag.NO_ATIME), None)
        True
        >>> pop_transient_flags('+u+r') == (int(JKeyFlag.UNLOCK), '+r')
        True
        >>> pop_transient_flags(None)
        (0, None)
    """
    if flags is None:
        return 0, None

    if isinstance(flags, str):
        trans, rest = 0, []
        for tok in re_findall(r'[+\-]?[a-z0-9]', flags.lower()):
            bit = TRANSIENT_FLAG_BY_LETTER.get(tok[-1:], None)
            if bit is not None:
                if tok[0] != '-':
                    trans |= bit

            elif tok[-1:] in KEY_FLAG_BY_LETTER:
                rest.append(tok)

        return trans, (''.join(rest) or None)

    flags = int(flags)
    trans = flags & TRANSIENT_FLAG_MASK
    rest = flags & ~TRANSIENT_FLAG_MASK
    return trans, (None if trans and not rest else rest)

def is_value_extension(old: Any, new: Any) -> bool:
    """Return ``True`` when *new* only adds to *old*.

    Enforces :attr:`JKeyFlag.APPEND_ONLY`: a write is allowed only when every
    element already stored is still present, unchanged, and in the same
    position. Types with no meaningful append (scalars, ``bool``) always
    return ``False``, which makes an append-only scalar effectively read-only.

    Args:
        old (Any): The currently stored value.
        new (Any): The value the caller wants to write.

    Returns:
        bool: ``True`` if *new* is a strict extension of *old*.

    Example:
        >>> is_value_extension([1, 2], [1, 2, 3])
        True
        >>> is_value_extension([1, 2], [9, 2, 3])
        False
    """
    if old is None:
        return new is not None

    if type(old) is not type(new):
        return False

    if isinstance(old, (str, bytes, bytearray)):
        return len(new) > len(old) and new.startswith(old)

    if isinstance(old, (list, tuple)):
        return len(new) > len(old) and new[:len(old)] == old

    if isinstance(old, dict):
        return len(new) > len(old) and all(k in new and new[k] == v for k, v in old.items())

    if isinstance(old, (set, frozenset)):
        return len(new) > len(old) and old <= new

    return False

#-----------------------------------------------------------------------------
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
                    _value |= F_REVERT
                elif ch == 's':
                    _value |= F_SPLIT
                elif ch == 'f':
                    _value |= F_FSYNC

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

# Plain-int aliases of every JFlag member; see the KF_* block above.
F_REVERT = int(JFlag.REVERT)
F_SPLIT  = int(JFlag.SPLIT)
F_FSYNC  = int(JFlag.FSYNC)

#-----------------------------------------------------------------------------
try:
    from bitarray import bitarray
except ImportError: # pragma: no cover
    try:
        (0).bit_count
        def _popcount(buf: bytearray) -> int:
            return int.from_bytes(buf, 'little').bit_count()

    except AttributeError: # pragma: no cover
        def _popcount(buf: bytearray) -> int:
            return bin(int.from_bytes(buf, 'little')).count('1')

    class bitarray:
        """Bit-packed boolean flag array (1 bit per flag, zero-initialized)."""
        __slots__ = ('_buf', '_nbits')

        def __init__(self, nbits: int = 0):
            self._nbits = nbits
            self._buf = bytearray((nbits + 7) >> 3)

        def __len__(self) -> int:
            return self._nbits

        def __repr__(self) -> str:
            return f'<bitarray n={self._nbits} nbytes={len(self._buf)}>'

        @property
        def nbytes(self) -> int:
            return len(self._buf)

        def __getitem__(self, idx: int) -> int:
            if idx < 0:
                idx += self._nbits
            if not 0 <= idx < self._nbits:
                raise IndexError(idx)
            return (self._buf[idx >> 3] >> (idx & 7)) & 1

        def __setitem__(self, idx: int, val: Union[bool, int]):
            if idx < 0:
                idx += self._nbits
            if not 0 <= idx < self._nbits:
                raise IndexError(idx)
            if val:
                self._buf[idx >> 3] |= 1 << (idx & 7)
            else:
                self._buf[idx >> 3] &= 0xff ^ (1 << (idx & 7))

        def extend(self, bits: Union[str, int]):
            if isinstance(bits, int):
                n_new, ones = bits, ()
            else:
                n_new = len(bits)
                ones = tuple(i for i, b in enumerate(bits) if b in ('1', 1, True))

            old_nbits = self._nbits
            self._nbits = old_nbits + n_new
            need = (self._nbits + 7) >> 3
            if need > len(self._buf):
                self._buf.extend(bytes(need - len(self._buf)))
            for i in ones:
                self[old_nbits + i] = True

        def setall(self, val: Union[bool, int]):
            """Set every bit to 0 or 1 in one bulk C-speed operation."""
            n_bytes = len(self._buf)
            if val:
                self._buf[:] = b'\xff' * n_bytes
                tail = self._nbits & 7
                if tail:  # mask unused bits in the last byte so count() is exact
                    self._buf[-1] &= (1 << tail) - 1
            else:
                self._buf[:] = bytes(n_bytes)

        def clear(self):
            """Drop all bits (length becomes 0), like bitarray.clear()."""
            self._nbits = 0
            self._buf.clear()

        def count(self, val: Union[bool, int] = 1) -> int:
            ones = _popcount(self._buf)
            return ones if val else self._nbits - ones

#-----------------------------------------------------------------------------

# These three are marker bases: no abstract methods and no virtual-subclass
# registration, so ABCMeta enforced nothing while making every isinstance()
# against them (or any subclass) go through ABCMeta.__instancecheck__ -- about
# 3x the cost of a plain type check, on paths that run once per record.
class JDbBase: # pragma: no cover
    pass

class JIoBase: # pragma: no cover
    pass

class KeyTableBase: # pragma: no cover
    def get_mode(self) -> int:
        """Get the current classification mode configuration.

        Returns:
            int: The constant indicating the current mode, defaults to -1.
        """
        return -1

def deepcopy(src:Any) -> Any:
    """Create a selective deep copy optimised for the types used in JDb.
 
    Common immutable types and :class:`JDbBase` instances are returned
    as-is without copying.  Containers are handled as follows:
 
    * ``tuple``  – new tuple whose elements are recursively deep-copied.
    * ``dict``   – new dict whose *values* are recursively deep-copied
      (keys are not copied because dict keys must be hashable).
    * ``set``    – shallow copy via ``set.copy()`` (set elements are
      hashable scalars and need no further copying).
    * Any other object whose ``__hash__`` attribute is truthy (e.g.
      a compiled :class:`re.Pattern` or a ``frozenset``) is treated as
      effectively immutable and returned without copying.
    * Everything else (typically a ``list``) – new list whose elements
      are recursively deep-copied.
 
    Args:
        src (Any): The object to copy.
 
    Returns:
        Any: A deep copy of *src*, or *src* itself for immutable types.
 
    Example:
        >>> original = {'key': [1, 2, 3]}
        >>> copied = deepcopy(original)
        >>> copied['key'] is original['key']
        False
    """
    if src is None or isinstance(src, (str, bytes, int, float, bool, JDbBase)):
        return src

    if isinstance(src, tuple):
        return tuple(deepcopy(v) for v in src)

    if isinstance(src, dict):
        return {key:deepcopy(val) for key, val in src.items()}

    if isinstance(src, set):
        return src.copy()

    if src.__hash__:
        return src

    return [deepcopy(val) for val in src]

#-----------------------------------------------------------------------------
def Style(msg, bold=None, dim=None, smso=None, underscore=None, blink=None, reverse=None, hidden=None, bright=None, fg=None, black=None, red=None, green=None, yellow=None, blue=None, magenta=None, cyan=None, white=None, bg=None, bg_black=None, bg_red=None, bg_green=None, bg_yellow=None, bg_blue=None, bg_magenta=None, bg_cyan=None, bg_white=None):
    """Wrap a string in ANSI escape codes to apply terminal colour and text styling.
 
    If no styling flags are set, *msg* is returned unchanged.
    All boolean parameters default to ``None`` (off).
 
    **Foreground colour precedence** – ``fg`` overrides the named colour
    shortcuts (``black``, ``red``, … ``white``).  Only the *first* truthy
    shortcut is applied.
 
    **Colour encoding for** ``fg`` **and** ``bg``:
 
    * ``int``  (0–7) – standard ANSI colour index directly.
    * ``str``  – bit-mapped from the characters present: ``'r'`` → +1,
      ``'g'`` → +2, ``'b'`` → +4.  E.g. ``'rg'`` → yellow (3).
    * ``tuple`` / ``list`` – three-element sequence ``[r, g, b]`` where each
      value is 0 or 1, bit-mapped the same way.
 
    When ``bright=True`` the foreground uses high-intensity ANSI codes
    (90–97) instead of standard codes (30–37).
 
    Args:
        msg (str): The text to style.
        bold (bool, optional): Bold / increased intensity.
        dim (bool, optional): Dim / decreased intensity.
        smso (bool, optional): Standout mode (terminal-defined highlight).
        underscore (bool, optional): Underline the text.
        blink (bool, optional): Blinking text.
        reverse (bool, optional): Swap foreground and background colours.
        hidden (bool, optional): Hide the text (invisible).
        bright (bool, optional): Use high-intensity foreground colour codes.
        fg (int | str | tuple | list, optional): Foreground colour; see
            colour encoding above.
        black (bool, optional): Set foreground colour to black.
        red (bool, optional): Set foreground colour to red.
        green (bool, optional): Set foreground colour to green.
        yellow (bool, optional): Set foreground colour to yellow.
        blue (bool, optional): Set foreground colour to blue.
        magenta (bool, optional): Set foreground colour to magenta.
        cyan (bool, optional): Set foreground colour to cyan.
        white (bool, optional): Set foreground colour to white.
        bg (int | str | tuple | list, optional): Background colour; see
            colour encoding above.
        bg_black (bool, optional): Set background colour to black.
        bg_red (bool, optional): Set background colour to red.
        bg_green (bool, optional): Set background colour to green.
        bg_yellow (bool, optional): Set background colour to yellow.
        bg_blue (bool, optional): Set background colour to blue.
        bg_magenta (bool, optional): Set background colour to magenta.
        bg_cyan (bool, optional): Set background colour to cyan.
        bg_white (bool, optional): Set background colour to white.
 
    Returns:
        str: *msg* wrapped in ANSI escape codes, or *msg* unchanged if no
        styling is requested.
 
    Example:
        >>> print(Style("OK", green=True, bold=True))
        >>> print(Style("ERROR", fg='r', bold=True))
        >>> print(Style("INFO", fg=[0, 0, 1], bg=0))   # blue on black
    """
    code = ''
    for ii,vv in enumerate([bold, dim, smso, underscore, blink, reverse, hidden]):
        if not vv:
            continue

        code += f'\033[{ii+1}m'

    if fg is None:
        for ii,vv in enumerate([black, red, green, yellow, blue, magenta, cyan, white]):
            if not vv:
                continue

            v1 = 9 if bool(bright) else 3
            code += f'\033[{v1}{ii}m'
            break
    else:
        if isinstance(fg, int):
            vv = max(min(fg, 7), 0)
        elif isinstance(fg, str):
            vv = 1 * ('r' in fg) + 2 * ('g' in fg) + 4 * ('b' in fg)
        else:
            vv = 1 * fg[0] + 2 * fg[1] + 4 * fg[2]
        v1 = 9 if bool(bright) else 3
        code += f'\033[{v1}{vv}m'


    if bg is None:
        for ii,vv in enumerate([bg_black, bg_red, bg_green, bg_yellow, bg_blue, bg_magenta, bg_cyan, bg_white]):
            if not vv:
                continue

            code += f'\033[4{ii}m'
            break
    else:
        if isinstance(bg, int):
            vv = max(min(bg, 7), 0)
        elif isinstance(bg, str):
            vv = 1 * ('r' in bg) + 2 * ('g' in bg) + 4 * ('b' in bg)
        else:
            vv = 1 * bg[0] + 2 * bg[1] + 4 * bg[2]

        code += f'\033[4{vv}m'

    if not code:
        return msg

    return f'{code}{msg}\033[0m'

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class INT_Handler:
    """Deferred SIGINT handler that protects critical sections from keyboard interrupts.
 
    When code enters a protected section (via :meth:`disable`) any ``Ctrl+C``
    (SIGINT) is captured silently and recorded instead of raising
    :exc:`KeyboardInterrupt` immediately.  Once all protected sections have
    exited (via :meth:`enable`), callers can check :meth:`is_called` to
    discover whether an interrupt was received and act accordingly.
 
    This is used internally by :class:`FileLock` to prevent SIGINT from
    interrupting a write-locked database operation mid-transaction.
    """
    __slots__ = ('count', 'lock', 'call_flag')

    def __init__(self):
        """Set up the deferred SIGINT handler and install it as the process SIGINT handler."""
        self.count = 0
        self.lock = Lock()
        self.call_flag = Event()
        signal(SIGINT, self.handler)

    def disable(self):
        """Enter a protected section where SIGINT is deferred rather than raised.
 
        Increments the internal nesting counter.  If this is the outermost
        ``disable()`` call (counter was 0), the pending-interrupt flag is
        cleared so stale events from a previous section cannot bleed through.
 
        This method is re-entrant: multiple nested calls are allowed and each
        must be matched by a corresponding :meth:`enable` call.
        """
        with self.lock:
            count = self.count
            self.count = count + 1
            if count == 0:
                self.call_flag.clear()

    def enable(self):
        """Leave a protected section, decrementing the nesting counter.
 
        When the counter reaches zero the pending-interrupt flag is cleared,
        discarding any deferred SIGINT that was recorded during the section.
        Callers should check :meth:`is_called` *before* calling ``enable()``
        if they need to act on a deferred interrupt.
 
        The counter is never decremented below zero.
        """
        with self.lock:
            count = self.count = max(0, self.count-1)
            if count == 0:
                self.call_flag.clear()

    def reset(self):
        """Force-reset the nesting counter to zero and clear the pending-interrupt flag.
 
        Use this only in emergency cleanup paths (e.g. after an unhandled
        exception) where normal :meth:`enable` pairing is not possible.
        """
        with self.lock: # pragma: no cover
            self.count = 0
            self.call_flag.clear()

    def is_called(self) -> bool:
        """Return whether a SIGINT was received while inside a protected section.
 
        Returns ``True`` only if the pending-interrupt flag is set *and* the
        nesting counter is still greater than zero (i.e. the signal arrived
        inside an active protected section that has not yet been fully exited).
 
        Returns:
            bool: ``True`` if a deferred interrupt is pending, ``False`` otherwise.
        """
        if self.call_flag.is_set():
            with self.lock: # pragma: no cover
                return self.count > 0 and self.call_flag.is_set()

        return False

    def handler(self, signum, frame): #pragma: no cover
        """SIGINT signal handler installed at construction time.
 
        If no protected section is active (``count == 0``), the default
        interrupt handler is invoked immediately, which raises
        :exc:`KeyboardInterrupt` in the normal way.
 
        If a protected section is active (``count > 0``), the signal is
        captured silently and recorded via the pending-interrupt flag so
        that :meth:`is_called` returns ``True`` after the section exits.
 
        Args:
            signum (int): Signal number (always ``signal.SIGINT`` here).
            frame (frame): Current stack frame at the point the signal arrived.
        """

        with self.lock:
            count = self.count
            if count == 0:
                self.call_flag.clear()
                default_int_handler(signum, frame)
            else:
                self.call_flag.set()


INT_manager = INT_Handler()

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class FileLockException(BlockingIOError):
    """Raised when a :class:`FileLock` operation cannot be completed.
 
    Thrown in two situations:
 
    * A non-blocking lock acquisition (``block=False``) fails because
      another process already holds an incompatible lock.
    * A lock acquisition is attempted after the :class:`FileLock` has
      been closed or is being destroyed (mode ``'x'``).
    """
    pass

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class FileLock:
    """Combined thread-level and process-level read/write lock backed by OS file locks.
 
    Wraps a set of OS-level file-lock callables to provide:
 
    * **Shared read locks** (``mode='r'``) – multiple threads *and*
      processes may hold a read lock simultaneously.
    * **Exclusive write locks** (``mode='w'``) – only one thread in one
      process may hold a write lock; all readers are excluded.
    * **Re-entrant acquisition** – the same thread may call
      :meth:`acquire` multiple times; each call must be matched by a
      :meth:`release` call.
    * **Lock upgrade** – a thread holding a read lock may promote it to
      a write lock without fully releasing via ``switch=True`` in
      :meth:`acquire`.
    * **SIGINT protection** – write locks automatically engage
      :class:`INT_Handler` so that ``Ctrl+C`` is deferred until the
      write section completes.
 
    Internal mode values stored in ``_mode``:
 
    * ``''``  – no lock held.
    * ``'r'`` – shared read lock active.
    * ``'w'`` – exclusive write lock active.
    * ``'p'`` – pending: a thread is waiting for the OS-level lock.
    * ``'x'`` – closed/destroyed; no new acquisitions are permitted.
    """
    __slots__ = ('_rlock', '_wlock', '_unlock', '_close', '_remove', \
                '_lock', '_cond', '_idents', '_mode', 'SIGINT')

    def __init__(self, \
            rlock:Callable[[bool], None],
            wlock:Callable[[bool], None],
            unlock:Callable[[], None],
            close:Callable[[], None],
            remove:Callable[[], None]):

        """Initialise the lock with OS-level locking callables.
 
        Args:
            rlock (Callable[[bool], None]): Acquire a shared (read) OS-level
                file lock.  The single ``bool`` argument indicates whether the
                call should block.
            wlock (Callable[[bool], None]): Acquire an exclusive (write)
                OS-level file lock.  The single ``bool`` argument indicates
                whether the call should block.
            unlock (Callable[[], None]): Release the current OS-level file lock.
            close (Callable[[], None]): Close the underlying lock file handle.
            remove (Callable[[], None]): Delete the lock file from disk.
 
        Raises:
            TypeError: If any of the five arguments is not callable.
        """
        if not callable(rlock) or not callable(wlock) or not callable(unlock) or not callable(close) or not callable(remove):
            raise TypeError

        self._rlock = rlock
        self._wlock = wlock
        self._unlock = unlock
        self._close = close
        self._remove = remove
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._idents = defaultdict(int)
        self._mode = ''
        self.SIGINT = INT_manager

    def __repr__(self) -> str:
        """Return a diagnostic string showing the lock's current state.
 
        Returns:
            str: A string of the form
            ``<FileLock lock:<bool> mode:<mode> at <hex_address>>``.
            ``lock`` is ``1`` when a read or write lock is active, ``0``
            otherwise; ``mode`` is one of ``''``, ``'r'``, ``'w'``,
            ``'p'``, or ``'x'``.
        """
        return f'<{type(self).__name__} lock:{int(self.is_locked)} mode:{self._mode} at {hex(id(self))}>'

    def __del__(self):
        """Clean up on garbage collection: release all pending locks and close the lock file."""
        with self._lock:
            while self._idents:
                self._cond.wait() # pragma: no cover

            if self._mode == 'w':
                self.SIGINT.enable() # pragma: no cover

            self._mode = 'x'
            self._idents.clear()
            self._cond.notify_all()

        self._close()

    def reset_lock(self) -> None:
        """Delete the lock file from disk, ignoring the error if it does not exist.
 
        Use this to clean up a stale lock file left behind by a crashed
        process.  Only call this when no other process holds or awaits
        the lock.
        """
        try:
            self._remove()
        except FileNotFoundError:
            pass

    @property
    def is_locked(self) -> bool:
        """Whether any thread currently holds a read or write lock.
 
        Returns:
            bool: ``True`` if ``mode`` is ``'r'`` or ``'w'``, ``False``
            otherwise.
        """
        return self._mode == 'r' or self._mode == 'w'

    @property
    def mode(self) -> str:
        """Current lock mode as a single character string.
 
        Returns:
            str: One of:
 
            * ``''``  – no lock held.
            * ``'r'`` – shared read lock active.
            * ``'w'`` – exclusive write lock active.
            * ``'p'`` – a thread is blocked waiting for the OS-level lock.
            * ``'x'`` – lock is closed; no new acquisitions permitted.
        """
        return self._mode

    @contextmanager
    def rlock(self):
        """Context manager that acquires a shared read lock and releases it on exit.
 
        Yields:
            None: Control is yielded to the ``with`` block with the read lock held.
 
        Example:
            ::
 
                with file_lock.rlock():
                    data = read_from_file()
        """
        self.acquire(read_only=True, block=True, switch=False)
        try:
            yield
        finally:
            self.release()

    @contextmanager
    def wlock(self):
        """Context manager that acquires an exclusive write lock and releases it on exit.
 
        SIGINT (``Ctrl+C``) is deferred while the write lock is held and
        re-enabled automatically on release.
 
        Yields:
            None: Control is yielded to the ``with`` block with the write lock held.
 
        Example:
            ::
 
                with file_lock.wlock():
                    write_to_file(data)
        """
        self.acquire(read_only=False, block=True, switch=False)
        try:
            yield

        finally:
            self.release()

    def has_SIGINT(self) -> bool:
        """Return whether a ``Ctrl+C`` was received while a write lock was held.
 
        This delegates to :meth:`INT_Handler.is_called` on the shared
        :data:`INT_manager` instance.
 
        Returns:
            bool: ``True`` if a deferred SIGINT is pending, ``False`` otherwise.
        """
        return self.SIGINT.is_called()

    def can_lock(self) -> bool:
        """Test whether an exclusive write lock can be acquired immediately without blocking.
 
        Attempts a non-blocking ``acquire(block=False, read_only=False)``
        and releases it straight away.
 
        Returns:
            bool: ``True`` if the write lock was obtained (and released),
            ``False`` if another holder would have caused a block.
        """
        try:
            self.acquire(block=False, read_only=False)
            return True

        except FileLockException: # pragma: no cover
            return False

        finally:
            self.release()

    def get_count(self, thread_id:int) -> int:
        """Return the re-entrance count for a given thread.
 
        Each call to :meth:`acquire` increments the count for the calling
        thread; each :meth:`release` decrements it.  The OS-level lock is
        released only when the count returns to zero.
 
        Args:
            thread_id (int): Thread identifier as returned by
                :func:`threading.get_ident`.
 
        Returns:
            int: Number of times the thread has acquired this lock without
            a matching release.  Returns ``0`` if the thread holds no lock.
        """
        return self._idents.get(thread_id, 0)

    def acquire(self, block:bool=True, read_only:bool=False, switch:bool=False) -> int:
        """Acquire a read or write lock for the calling thread.
 
        Thread-level re-entrance is supported: calling ``acquire`` again
        from a thread that already holds a compatible lock simply increments
        the re-entrance counter and returns immediately.
 
        **Lock promotion (** ``switch=True`` **)** – a thread that currently
        holds a read lock may atomically promote it to a write lock.  The
        read lock is released and the write lock is acquired without
        allowing other threads to sneak in between.
 
        Args:
            block (bool, optional): If ``True`` (default), block until the
                lock becomes available.  If ``False``, raise
                :exc:`FileLockException` immediately when the lock cannot
                be acquired.
            read_only (bool, optional): If ``True``, acquire a shared read
                lock (multiple threads/processes may hold it simultaneously).
                If ``False`` (default), acquire an exclusive write lock.
            switch (bool, optional): If ``True``, upgrade the current
                thread's read lock to a write lock without fully releasing.
                Only valid when the calling thread already holds a read lock.
                Defaults to ``False``.
 
        Returns:
            int: The calling thread's identifier (as returned by
            :func:`threading.get_ident`).
 
        Raises:
            RuntimeError: If the internal threading mutex cannot be acquired.
            FileLockException: If ``block=False`` and the lock is held by
                another thread or process, or if the lock has been closed
                (mode ``'x'``).
        """
        if not self._lock.acquire():
            raise RuntimeError

        try:
            ident = get_ident()
            _idents = self._idents
            while True:
                _mode = self._mode
                if _mode == 'x': # pragma: no cover
                    raise FileLockException("FileLock is closed or being destroyed.")

                # [1] Thread level
                if _mode == 'r' and read_only and _idents: # allow multiple reader
                    _idents[ident] += 1
                    return ident

                if _mode == 'w' and ident in _idents: # only allow one writer (same thread)
                    _idents[ident] += 1
                    return ident

                elif _mode == 'r' and ident in _idents:
                    # switch 'r' to 'w'
                    _cnt = _idents[ident]
                    if _cnt <= 1:
                        _idents.pop(ident)
                        if not _idents:
                            # this thread is the last lock owner
                            try:
                                self._unlock()

                            except OSError as e: # pragma: no cover
                                print(e)
                                if self._mode == 'x':
                                    continue

                            _mode = self._mode = ''
                            if not switch:
                                self._cond.notify_all()
                                _idents[ident] = _cnt
                                continue

                        if not switch and _cnt > 0: # pragma: no cover
                            _idents[ident] = _cnt

                    elif switch: # pragma: no cover
                        _idents[ident] = _cnt - 1
                        if _cnt > 1 and len(_idents) == 1:
                            try:
                                self._unlock()

                            except OSError as e:
                                print(e)
                                if self._mode == 'x':
                                    continue

                            _mode = self._mode = ''

                if _mode != '': # pragma: no cover
                    if not block:
                        raise FileLockException("Could not acquire lock") # pragma: no cover

                    self._cond.wait()
                    continue

                # [2] process level
                try:
                    if read_only:
                        self._rlock(block=False)
                        self._mode = 'r'
                    else:
                        self._wlock(block=False)
                        self._mode = 'w'
                        self.SIGINT.disable()

                    _idents[ident] += 1
                    if read_only:
                        self._cond.notify_all()
                    return ident

                except BlockingIOError as e:
                    if not block: # pragma: no cover
                        if ident in _idents:
                            self._mode = 'r'
                        raise FileLockException("Could not acquire lock") from e

                    self._mode = 'p'
                    self._lock.release()
                    os_lock_acquired = False
                    os_err = None
                    if self._mode != 'p':  # pragma: no cover
                        continue

                    try:
                        if read_only:
                            self._rlock(block=True)
                        else:
                            self._wlock(block=True)
                        os_lock_acquired = True

                    except Exception as ex: # pragma: no cover
                        os_err = ex

                    finally:
                        self._lock.acquire()
                        if self._mode == 'p': # pragma: no cover
                            self._mode = ''

                        self._cond.notify_all()

                    if self._mode == 'x': # pragma: no cover
                        if os_lock_acquired:
                            try:
                                self._unlock()
                            except OSError as e1:
                                print(e1)

                        raise FileLockException("FileLock is closed or being destroyed.") from e

                    if os_err is not None: # pragma: no cover
                        raise FileLockException("Could not acquire lock") from os_err

                    if read_only:
                        self._mode = 'r'
                    else:
                        self._mode = 'w'
                        self.SIGINT.disable()

                    _idents[ident] += 1
                    self._cond.notify_all() # wake up all thread due to 'p'
                    return ident

        finally:
            self._lock.release()

        return ident

    def release(self) -> int:
        """Release one acquisition of the lock for the calling thread.
 
        Decrements the re-entrance counter for the calling thread.  When
        the counter reaches zero and no other threads hold the lock, the
        OS-level file lock is released and SIGINT handling is re-enabled
        (if a write lock was held).
 
        Calling ``release`` from a thread that does not hold the lock has
        no effect.
 
        Returns:
            int: The calling thread's identifier (as returned by
            :func:`threading.get_ident`).
 
        Raises:
            RuntimeError: If the internal threading mutex cannot be acquired.
        """
        if not self._lock.acquire():
            raise RuntimeError

        try:
            _idents = self._idents
            ident = get_ident()
            if ident in _idents:
                if _idents.get(ident, 0) <= 1:
                    _idents.pop(ident, 0)
                else:
                    _idents[ident] -= 1

                if not _idents:
                    if self._mode == 'w':
                        self.SIGINT.enable()
                    try:
                        self._unlock()
                    except OSError as e1: # pragma: no cover
                        print(e1)
                    self._mode = ''
                    self._cond.notify_all()

            return ident

        finally:
            self._lock.release()


_ANSI_RE = re_compile(r'\x1b\[[\d;]*m') # strip SGR colour codes before measuring a cell

def get_display_width(s_str:str) -> int:
    """Return the terminal column width of ``s_str``.

    ANSI colour codes are stripped first and East-Asian wide/fullwidth glyphs
    count as two columns, so a table built from mixed CJK/ASCII text still
    lines up.

    Args:
        s_str (str): The already-rendered cell text.

    Returns:
        int: The number of terminal columns the text occupies.
    """
    if s_str.find('\x1b[') >= 0:
        s_str = _ANSI_RE.sub('', s_str)

    width = 0
    for ch in s_str:
        width += (2 if east_asian_width(ch) in ('W', 'F', 'A') else 1)

    return width

def pad_string(s_str:str, target_width:int) -> str:
    """Right-pad ``s_str`` with spaces to ``target_width`` display columns.

    Args:
        s_str (str): The already-rendered cell text.
        target_width (int): The column width to fill.

    Returns:
        str: The padded text; unchanged when it is already that wide or wider.
    """
    return s_str + ' ' * (target_width - get_display_width(s_str))

def print_table(fields:List[str], matrix:List[Dict[str,str]], footer:str='', title:str='') -> None:
    """Print a box-drawn console table shared by :meth:`JDbReader.show` and :meth:`JDbReader.history`.

    Args:
        fields (List[str]): Column names, in display order; also the lookup
            keys into every row of ``matrix``.
        matrix (List[Dict[str, str]]): One dict per row, mapping a field name
            to its already-rendered text. A missing field renders empty.
        footer (str, optional): A dim summary line printed under the table.
            Defaults to ``''`` (no footer).
        title (str, optional): A heading printed above the table. Defaults to
            ``''`` (no heading).
    """
    col_widths = {field: get_display_width(field) for field in fields}
    for row_data in matrix:
        for field in fields:
            cell = row_data.get(field, '')
            width = get_display_width(cell)
            if width > col_widths[field]:
                col_widths[field] = width

    top = '╔' + '╤'.join('═' * (col_widths[f] + 2) for f in fields) + '╗'
    mid = '╟' + '┼'.join('─' * (col_widths[f] + 2) for f in fields) + '╢'
    bot = '╚' + '╧'.join('═' * (col_widths[f] + 2) for f in fields) + '╝'
    print()
    if title:
        print(title)

    print(top)
    # with bold+cyan color
    print('║' + '│'.join(' \x1b[96m\x1b[1m' + pad_string(f, col_widths[f]) + '\x1b[0m ' for f in fields) + '║')
    print(mid)
    for row_data in matrix:
        print('║' + '│'.join(' ' + pad_string(row_data.get(f, ''), col_widths[f]) + ' ' for f in fields) + '║')

    print(bot)
    if footer:
        print(footer)

#
