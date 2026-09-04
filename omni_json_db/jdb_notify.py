"""Change notification for :class:`~omni_json_db.JDb` -- pull model.

The writer records every changed key in a plain dict (the *sink*) as it writes
the KEY index row, and the outermost :meth:`JDbReader.open` exit turns that dict
into finished :class:`JEvent` objects and appends them to a bounded ring buffer.
Consumers call :meth:`JDb.get_notify` when it suits them; each subscription owns
a cursor into the ring, so several consumers may poll at different rates.

There is no worker thread, no queue and no callback: the consumer's code runs on
the consumer's own stack, outside every database lock.

Opcodes:

===== ==========================================================
``C`` created
``U`` value updated
``D`` deleted by the caller
``X`` dropped because its TTL ran out
``R`` renamed -- :attr:`JEvent.old_key` carries the previous name
``M`` metadata only (flags, ttl, dates); the value did not change
``W`` written, create-or-update -- only from the cross-process scan
``Z`` resync: the key space may have changed wholesale, re-read it
===== ==========================================================

See ``claude/notify-pull-model.md`` and ``claude/notify-events-crud.md`` for the
design study and the measurements behind it.
"""
# pylint: disable=too-few-public-methods
from __future__ import annotations
from fnmatch import fnmatchcase
from typing import Callable, Dict, Iterable, List, NamedTuple, Optional, Pattern, Tuple, Union, IO
from .utils import JIoBase

OP_CREATE   = 'C'
OP_UPDATE   = 'U'
OP_DELETE   = 'D'
OP_EXPIRE   = 'X'
OP_RENAME   = 'R'
OP_META     = 'M'
OP_WRITE    = 'W'
OP_RESYNC   = 'Z'
ALL_OPS     = 'CUDXRMWZ'
DEFAULT_OPS = 'CUDXRM'  # everything a data consumer wants; 'W' is reserved, 'Z' is unfiltered
RING_LIMIT  = 1 << 16   # events held for the slowest consumer

# a Selector is an exact key, a glob, a compiled regex or a predicate
Selector = Union[str, Pattern, Callable[[str], bool]]


class JEvent(NamedTuple):
    """One change to one key.

    Unpacks as ``key, op, ver`` for the common case; ``old_key`` and ``flags``
    default, so a three-field consumer keeps working when a rename or a flag
    filter is added later.

    Attributes:
        key (str): The record key. Empty for :data:`OP_RESYNC`.
        op (str): One of :data:`ALL_OPS`.
        ver (int): The ``sync_id`` stamp of the row that produced the event.
        old_key (str): The previous name, for :data:`OP_RENAME` only.
        flags (int): :class:`~omni_json_db.JKeyFlag` bits after the change;
            ``0`` for deletes, expiries and resyncs.
    """
    key: str
    op: str
    ver: int
    old_key: str = ''
    flags: int = 0

    def split(self) -> Tuple[JEvent,JEvent]:
        """Express a rename as the delete/create pair it is equivalent to.

        Returns:
            Tuple[JEvent, JEvent]: ``(D old_key, C key)``. Calling this on any
            other opcode returns the event twice, so a caller can splat it
            unconditionally.

        Example:
            >>> JEvent('z', 'R', 7, old_key='b').split()
            (JEvent(key='b', op='D', ver=7, old_key='', flags=0), JEvent(key='z', op='C', ver=7, old_key='', flags=0))
        """
        if self.op != OP_RENAME:
            return self, self

        return (JEvent(self.old_key, OP_DELETE, self.ver),
                JEvent(self.key, OP_CREATE, self.ver, '', self.flags))

def compile_match(key:Selector) -> Callable[[str], bool]:
    """Turn a subscription selector into a predicate.

    Args:
        key (Selector): ``'*'`` for everything, a plain string for an exact
            match, a string holding ``*``/``?``/``[`` for a glob, a compiled
            regular expression (matched with ``search``), or any callable
            taking the key and returning a bool.

    Returns:
        Callable[[str], bool]: The predicate.

    Raises:
        TypeError: If ``key`` is none of the above.

    Example:
        >>> compile_match('user:*')('user:42'), compile_match('a')('b')
        (True, False)
    """
    if isinstance(key, str):
        if key == '*':
            return lambda _k: True

        if '*' in key or '?' in key or '[' in key:
            return lambda k, _p=key: fnmatchcase(k, _p)

        return lambda k, _e=key: k == _e

    search = getattr(key, 'search', None)
    if search is not None:
        return lambda k, _s=search: _s(k) is not None

    if callable(key):
        return key

    raise TypeError(f'invalid notify selector: {type(key).__name__}')

class JNotifySub:
    """One pull subscription: a selector, an opcode filter and a cursor."""

    __slots__ = ('token', 'key', 'ops', 'match', 'cursor')

    def __init__(self, token:int, key:Selector, ops:str, cursor:int):
        self.token  = token
        self.key    = key
        self.ops    = ops
        self.match  = compile_match(key)
        self.cursor = cursor

    def __repr__(self) -> str:
        return f'JNotifySub(token={self.token}, key={self.key!r}, ops={self.ops!r}, cursor={self.cursor})'

class JNotify:
    """The per-handle event ring and its subscriptions.

    Not locked internally: every entry point is called with the owning
    :class:`JDbReader`'s ``lock`` already held.

    Args:
        limit (int, optional): Events retained for the slowest consumer.
            Past this the oldest are dropped and the consumer that fell behind
            receives a :data:`OP_RESYNC` in their place. Defaults to
            :data:`RING_LIMIT`.
    """

    __slots__ = ('_ring', '_base', '_limit', '_subs', '_token', '_epoch', '_lost', '_hi')

    def __init__(self, limit:int=RING_LIMIT):
        self._ring:List[JEvent] = []
        self._base  = 0                     # absolute index of _ring[0]
        self._limit = max(1, int(limit))
        self._subs:Dict[int,JNotifySub] = {}
        self._token = 0
        self._epoch:Optional[Tuple[int,int,int]] = None
        self._lost  = 0                     # events dropped by the ring cap
        self._hi:Optional[int] = None       # sync_id at the end of the last collect

    # ------------------------------------------------------------------ subs

    def add(self, key:Selector, ops:str) -> int:
        """Register a subscription starting from the current ring position.

        Args:
            key (Selector): What to match.
            ops (str): Opcodes to deliver.

        Returns:
            int: The subscription token.
        """
        self._token += 1
        token = self._token
        self._subs[token] = JNotifySub(token, key, ops, self._base + len(self._ring))
        return token

    def set(self, token:int, key:Optional[Selector], ops:Optional[str]) -> bool:
        """Retarget a subscription in place, keeping its cursor.

        Args:
            token (int): The subscription to change.
            key (Optional[Selector]): New selector, or ``None`` to keep.
            ops (Optional[str]): New opcode filter, or ``None`` to keep.

        Returns:
            bool: True if the subscription existed.
        """
        sub = self._subs.get(token, None)
        if sub is None:
            return False

        if key is not None:
            sub.key = key
            sub.match = compile_match(key)

        if ops is not None:
            sub.ops = ops

        return True

    def remove(self, token:Optional[int]=None, key:Optional[Selector]=None) -> int:
        """Drop subscriptions by token, by selector, or all of them.

        Args:
            token (Optional[int]): Drop just this one.
            key (Optional[Selector]): Drop every subscription registered with
                an equal selector.

        Returns:
            int: How many were dropped.
        """
        subs = self._subs
        if token is not None:
            return 1 if subs.pop(token, None) is not None else 0

        if key is not None:
            gone = [t for t, s in subs.items() if s.key == key]
            for t in gone:
                subs.pop(t, None)

            return len(gone)

        gone = len(subs)
        subs.clear()
        return gone

    def __len__(self) -> int:
        return len(self._subs)

    def stats(self) -> Dict[str,int]:
        """Ring occupancy, for tests and diagnostics.

        Returns:
            Dict[str, int]: ``subs``, ``buffered``, ``base``, ``lost``.
        """
        return {'subs': len(self._subs), 'buffered': len(self._ring), 'base': self._base, 'lost': self._lost}

    # ----------------------------------------------------------------- write

    def push(self, events:Iterable[JEvent]) -> None:
        """Append finished events and trim the ring to its cap.

        Args:
            events (Iterable[JEvent]): Events in delivery order.
        """
        ring = self._ring
        ring.extend(events)
        over = len(ring) - self._limit
        if over > 0:
            del ring[:over]
            self._base += over
            self._lost += over

    def push_resync(self, ver:int) -> None:
        """Append one :data:`OP_RESYNC`, unless the ring already ends with one.

        Args:
            ver (int): The ``sync_id`` to stamp it with.
        """
        ring = self._ring
        if ring and ring[-1].op == OP_RESYNC:
            return

        self.push((JEvent('', OP_RESYNC, ver),))

    def collect(self, io:JIoBase, key_fp:Optional[IO]=None) -> None:
        """Drain the writer's sink into the ring and re-arm it.

        Called from the outermost :meth:`JDbReader.open` / :meth:`f_close` exit,
        with the write lock still held, so ``io.key_table`` is consistent.

        Args:
            io (JIoBase): The handle's IO engine.
            key_fp (Optional[IO]): The open KEY file pointer, for key tables
                that resolve lazily.
        """
        sink = io.notify_sink
        if sink:
            self.push(self.z_resolve(sink, io, key_fp, self.wanted()))
            sink.clear()

        elif sink is None:
            io.notify_sink = {}             # io was re-initialized under us
            io.notify_want = self.wanted()
            self._epoch = None

        if self._epoch_broke(io):
            self.push_resync(io.sync_id)

        self._hi = io.sync_id

    def check_foreign(self, sync_id:int) -> bool:
        """Report a database somebody else moved while this handle was idle.

        Called from the outermost :meth:`JDbReader.open` *entry* (after the
        header has been re-read, so nothing this handle does has happened yet)
        and from :meth:`JDb.get_notify`'s header peek. Any ``sync_id`` that is
        not the one we last flushed came from somewhere else.

        Which keys changed is not recoverable -- a delete leaves no live row,
        and the row it parks can be handed to the very next write -- so this is
        reported as one resync rather than a guess.

        Args:
            sync_id (int): The ``sync_id`` now on disk or in the reloaded header.

        Returns:
            bool: True if a resync was queued.
        """
        hi = self._hi
        if hi is None or sync_id == hi:
            return False

        self.push_resync(sync_id)
        self._hi = sync_id
        return True

    def wanted(self) -> Optional[Callable[[str], bool]]:
        """Build one predicate covering every subscription.

        A key no subscription matches never becomes an event, which keeps a
        narrow subscription cheap on a bulk load.

        Returns:
            Optional[Callable[[str], bool]]: ``None`` when some subscription
            takes everything, so the caller can skip the test entirely.
        """
        subs = list(self._subs.values())
        if not subs:
            return None

        if len(subs) == 1:
            sub = subs[0]
            return None if sub.key == '*' else sub.match

        matchers = []
        for sub in subs:
            if sub.key == '*':
                return None

            matchers.append(sub.match)

        return lambda k, _m=matchers: any(m(k) for m in _m)

    @staticmethod
    def z_resolve(sink:dict, io:JIoBase, key_fp:Optional[IO]=None, \
            wanted:Optional[Callable[[str],bool]]=None) -> List[JEvent]:
        """Confirm each sink entry against the key table and finish the event.

        A ``D`` on a key that is still live was an update in disguise -- the
        old version was parked in the DEAD region before the new one was
        written. A ``C``/``U``/``M`` on a key that has since gone is a delete.

        Args:
            sink (dict): ``{key: (op, ver, flags, old_key)}``.
            io (JIoBase): The handle's IO engine.
            key_fp (Optional[IO], optional): The open KEY file pointer.
            wanted (Optional[Callable[[str], bool]], optional): Keep only the keys
                this predicate accepts; ``None`` keeps every key.

        Returns:
            List[JEvent]: One event per changed key, in first-touch order.
        """
        get = io.key_table.get
        event = JEvent
        out = []
        add = out.append
        for key, (op, ver, flags, old_key) in sink.items():
            if op == OP_RESYNC:             # the sink overflowed; nothing else counts
                return [event('', OP_RESYNC, ver)]

            if wanted is not None and not (wanted(key) or (old_key and wanted(old_key))):
                continue

            if op == OP_RENAME:
                add(event(key, OP_RENAME, ver, old_key, flags))
            elif get(key, -1, key_fp) >= 0:
                add(event(key, OP_UPDATE if op == OP_DELETE else op, ver, '', flags))
            elif op == OP_EXPIRE:
                add(event(key, OP_EXPIRE, ver))
            else:
                add(event(key, OP_DELETE, ver))

        return out

    def _epoch_broke(self, io:JIoBase) -> bool:
        """Detect a key space that was reset or renumbered under us.

        ``clear()``, ``recycle()`` on an empty database and
        ``resize_index_size(min_ver=True)`` all move ``sync_id`` *backwards*,
        which a delta reader would otherwise read as "nothing happened" -- and
        then stay silent forever.

        Args:
            io (JIoBase): The handle's IO engine.

        Returns:
            bool: True when the caller should emit a resync.
        """
        now = (io.sync_id, io.index_size, io.n_lines)
        was = self._epoch
        self._epoch = now
        if was is None:
            return False

        return now[0] < was[0] or now[1] != was[1]

    # ------------------------------------------------------------------ read
    def drain(self, token:Optional[int], peek:bool=False, limit:Optional[int]=None) -> List[JEvent]:
        """Return the events one subscription has not seen yet.

        Args:
            token (Optional[int]): The subscription, or ``None`` for every one
                of them merged (each cursor advances).
            peek (bool, optional): Leave the cursors where they are.
                Defaults to False.
            limit (Optional[int], optional): Stop after this many events.
                Defaults to None.

        Returns:
            List[JEvent]: Matching events in ``sync_id`` order -- the merged form
            is ordered by ring position and de-duplicated by value, so two
            subscriptions sitting at different cursors still yield one stream.
            A leading :data:`OP_RESYNC` means the ring dropped events this
            subscription had not read.
        """
        subs = self._subs
        if token is not None:
            sub = subs.get(token, None)
            out = [] if sub is None else [ev for _pos, ev in self._drain_sub(sub, peek, limit)]
        else:
            # de-duplicate by value, not by identity: a resync raised for a subscription
            # that fell behind, and the halves of a split rename, are built per
            # subscription, so two subscriptions produce equal-but-distinct objects
            merged:Dict[JEvent,int] = {}
            for sub in subs.values():
                for pos, ev in self._drain_sub(sub, peek, limit):
                    if ev not in merged:    # keep the earliest position it was seen at
                        merged[ev] = pos

            # ... and order the union by ring position, which per-subscription
            # concatenation does not do once two cursors sit apart
            out = [ev for ev, _pos in sorted(merged.items(), key=lambda item: item[1])]

        if not peek:
            ring = self._ring
            if not subs:
                self._base += len(ring)
                ring.clear()
            else:
                n = min(s.cursor for s in subs.values()) - self._base
                if n > 0:
                    del ring[:n]
                    self._base += n

        return out

    def _drain_sub(self, sub:JNotifySub, peek:bool, limit:Optional[int]) -> List[Tuple[int,JEvent]]:
        """Filter the unread slice of the ring for one subscription.

        Args:
            sub (JNotifySub): The subscription.
            peek (bool): Leave the cursor where it is.
            limit (Optional[int]): Stop after this many events.

        Returns:
            List[Tuple[int, JEvent]]: ``(absolute ring position, event)`` pairs.
            The position is what lets :meth:`drain` merge two subscriptions back
            into one ordered stream; a synthetic resync and the halves of a split
            rename carry the position of the entry they were derived from.
        """
        ring = self._ring
        base = self._base
        lost = sub.cursor < base
        start = 0 if lost else sub.cursor - base
        stop = len(ring) if limit is None else min(len(ring), start + limit)

        match = sub.match
        ops = sub.ops
        out = [(base + start, JEvent('', OP_RESYNC, ring[start].ver if start < len(ring) else 0))] if lost else []
        for ii, ev in enumerate(ring[start:stop], start=base+start):
            op = ev.op
            if op == OP_RESYNC:             # control: never filtered out
                out.append((ii, ev))
            elif op == OP_RENAME and OP_RENAME not in ops:
                for part in ev.split():     # 'CUD' subscribers still see the move
                    if part.op in ops and match(part.key):
                        out.append((ii, part))

            elif op in ops and (match(ev.key) or (ev.old_key and match(ev.old_key))):
                out.append((ii, ev))

        if not peek:
            sub.cursor = base + stop

        return out
#
