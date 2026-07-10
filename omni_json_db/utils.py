# pylint: disable=too-many-lines
from __future__ import annotations
from collections import defaultdict
from contextlib import contextmanager
from abc import ABCMeta
from threading import Lock, Event, Condition, get_ident
from signal import SIGINT, signal, default_int_handler # SIG_IGN
from typing import Callable, Any, Union
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

#-----------------------------------------------------------------------------
# try:
#     from bitarray import bitarray # pylint: disable=unused-import
# except ImportError: # pragma: no cover
try:
    (0).bit_count #pylint: disable=pointless-statement
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
        """Append bits. Accepts a '01' string (bitarray-compatible, e.g.
        '0'*n) or an int meaning "append this many zero bits"."""
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

# pylint: disable=too-few-public-methods
class JDbBase(metaclass=ABCMeta): # pragma: no cover
    pass

# pylint: disable=too-few-public-methods
class JIoBase(metaclass=ABCMeta): # pragma: no cover
    pass

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
    pass # pylint: disable=unnecessary-pass

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
        self.release_all()
        self._close()

    def release_all(self) -> bool: # pragma: no cover
        """Wait for all threads to release their locks, then mark the lock as destroyed.
 
        Blocks until ``_idents`` is empty (every thread has called
        :meth:`release` enough times to drop its count to zero).  Once
        drained, the mode is set to ``'x'`` to prevent any new
        :meth:`acquire` calls from succeeding.  If a write lock was
        active, the SIGINT handler is re-enabled before closing.
 
        This method is called by :meth:`__del__` and should not normally
        be called directly.
 
        Returns:
            bool: ``True`` if the internal mutex was acquired and the
            shutdown sequence completed.  ``False`` if the mutex itself
            could not be acquired (should not happen in practice).
        """
        if not self._lock.acquire(): # pylint: disable=consider-using-with
            return False

        try:
            while self._idents:
                self._cond.wait()

            if self._mode == 'w':
                self.SIGINT.enable()

            self._mode = 'x'
            self._idents.clear()
            self._cond.notify_all()

        finally:
            self._lock.release()

        return True

    def reset_lock(self) -> None: # pragma: no cover
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
    def rlock(self): # pragma: no cover
        """Context manager that acquires a shared read lock and releases it on exit.
 
        Yields:
            None: Control is yielded to the ``with`` block with the read lock held.
 
        Example:
            ::
 
                with file_lock.rlock():
                    data = read_from_file()
        """
        self.acquire(read_only=True)
        try:
            yield
        finally:
            self.release()

    @contextmanager
    def wlock(self): # pragma: no cover
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
        self.acquire(read_only=False)
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
        if not self._lock.acquire(): # pylint: disable=consider-using-with
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
                        self._lock.acquire() # pylint: disable=consider-using-with
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
        if not self._lock.acquire(): # pylint: disable=consider-using-with
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
                    self._mode =  ''

                self._cond.notify_all()

            return ident

        finally:
            self._lock.release()

#
