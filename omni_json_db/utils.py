from collections import defaultdict
from contextlib import contextmanager
from threading import Lock, Event, Condition, get_ident
from signal import SIGINT, signal, default_int_handler # SIG_IGN
# from typing import Union, Optional
#-----------------------------------------------------------------------------
from .jdb_file import JFilesBase
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
def Style(msg, bold=None, dim=None, smso=None, underscore=None, blink=None, reverse=None, hidden=None, bright=None, fg=None, black=None, red=None, green=None, yellow=None, blue=None, magenta=None, cyan=None, white=None, bg=None, bg_black=None, bg_red=None, bg_green=None, bg_yellow=None, bg_blue=None, bg_magenta=None, bg_cyan=None, bg_white=None):
    """Format and apply ANSI terminal styling codes onto text strings for decorative command-line outputs.

    Args:
        msg (str): The destination target string payload to be styled.
        bold (Optional[bool], optional): Enable bold or increased intensity layout mode. Defaults to None.
        dim (Optional[bool], optional): Enable decreased intensity text mode. Defaults to None.
        smso (Optional[bool], optional): Enable standout parameter configuration mode. Defaults to None.
        underscore (Optional[bool], optional): Render text with a continuous bottom line. Defaults to None.
        blink (Optional[bool], optional): Force active text animation loops blinking characters. Defaults to None.
        reverse (Optional[bool], optional): Swap default foreground colors with background arrays colors. Defaults to None.
        hidden (Optional[bool], optional): Keep matching output segments masked from visibility screens. Defaults to None.
        bright (Optional[bool], optional): Boost chosen foreground saturation levels parameters. Defaults to None.
        fg (Optional[Union[int, str, tuple, list]], optional): Manual configuration mapping foreground color values. Defaults to None.
        black (Optional[bool], optional): Quick flag routing terminal text color straight to black. Defaults to None.
        red (Optional[bool], optional): Quick flag routing terminal text color straight to red. Defaults to None.
        green (Optional[bool], optional): Quick flag routing terminal text color straight to green. Defaults to None.
        yellow (Optional[bool], optional): Quick flag routing terminal text color straight to yellow. Defaults to None.
        blue (Optional[bool], optional): Quick flag routing terminal text color straight to blue. Defaults to None.
        magenta (Optional[bool], optional): Quick flag routing terminal text color straight to magenta. Defaults to None.
        cyan (Optional[bool], optional): Quick flag routing terminal text color straight to cyan. Defaults to None.
        white (Optional[bool], optional): Quick flag routing terminal text color straight to white. Defaults to None.
        bg (Optional[Union[int, str, tuple, list]], optional): Manual configuration mapping background space color block rules. Defaults to None.
        bg_black (Optional[bool], optional): Apply solid black background matrices blocks onto output spans. Defaults to None.
        bg_red (Optional[bool], optional): Apply solid red background matrices blocks onto output spans. Defaults to None.
        bg_green (Optional[bool], optional): Apply solid green background matrices blocks onto output spans. Defaults to None.
        bg_yellow (Optional[bool], optional): Apply solid yellow background matrices blocks onto output spans. Defaults to None.
        bg_blue (Optional[bool], optional): Apply solid blue background matrices blocks onto output spans. Defaults to None.
        bg_magenta (Optional[bool], optional): Apply solid magenta background matrices blocks onto output spans. Defaults to None.
        bg_cyan (Optional[bool], optional): Apply solid cyan background matrices blocks onto output spans. Defaults to None.
        bg_white (Optional[bool], optional): Apply solid white background matrices blocks onto output spans. Defaults to None.

    Returns:
        str: Styled alphanumeric text enclosed inside proper ANSI escape sequence boundary frames.

    Examples:
        >>> print(Style("Database Connected Successfully!", green=True, bold=True))
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
    """Thread-safe signal execution interceptor routing keyboard interrupt SIGINT behaviors.

    Postpones default termination actions during active critical system I/O database transactions.
    """
    __slots__ = ('count', 'lock', 'call_flag')

    def __init__(self):
        """Initialize the interrupt handler subsystem, overriding global SIGINT handlers frameworks."""
        self.count = 0
        self.count = 0
        self.lock = Lock()
        self.call_flag = Event()
        signal(SIGINT, self.handler)

    def disable(self):
        """Increment transaction isolation counters to suppress immediate SIGINT runtime execution crashes."""
        with self.lock:
            count = self.count
            self.count = count + 1
            if count == 0:
                self.call_flag.clear()

    def enable(self):
        """Decrement transaction isolation counters, enabling system restoration towards default signal actions cascades."""
        with self.lock:
            count = self.count = max(0, self.count-1)
            if count == 0:
                self.call_flag.clear()

    def reset(self):
        """Forcibly reset inner concurrency tracking integers clearing pending cancellation events back onto zero parameters."""
        with self.lock: # pragma: no cover
            self.count = 0
            self.call_flag.clear()

    def is_called(self) -> bool:
        """Validate if a keyboard interrupt happened while transaction isolation boundaries were active.

        Returns:
            bool: True if SIGINT was captured during isolated operations, False otherwise.
        """
        if self.call_flag.is_set():
            with self.lock: # pragma: no cover
                return self.count > 0 and self.call_flag.is_set()

        return False

    def handler(self, signum, frame): #pragma: no cover
        """Callback handler managing operational signal indicators states routing parameters.

        Args:
            signum (int): The identifier matching incoming signal codes (e.g., SIGINT).
            frame (Any): Current system execution stack frame trace pointer context references.
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
class FileLockException(Exception):
    """Custom exception class thrown when internal file locking resource allocations timeout or hit collision errors."""
    pass # pylint: disable=unnecessary-pass

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class FileLock:
    """High-performance thread-safe and process-safe synchronization locking mechanism manager proxy.

    Coordinates multi-threaded read/write exclusion barriers around structural database assets files pools.
    """
    __slots__ = ('files_obj', '_lock', '_cond', '_idents', '_mode', 'SIGINT')

    def __init__(self, files_obj:JFilesBase):
        """Initialize lock control environments tying mechanisms straight onto chosen driver handles parameters rules.

        Args:
            files_obj (JFilesBase): Persistent abstract dataset filesystem connection controller interface object instance.

        Raises:
            TypeError: If the incoming asset driver fails core framework datatype matching rules verification checkpoints.
        """
        if not isinstance(files_obj, JFilesBase):
            raise TypeError
        self.files_obj = files_obj
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._idents = defaultdict(int)
        self._mode = ''
        self.SIGINT = INT_manager

    def __repr__(self) -> str:
        """Generate summary tracking indicators metrics describing active lock status criteria templates.

        Returns:
            str: Diagnostic status metrics representation presentation text layout string text.
        """
        return f'<{type(self).__name__} lock:{int(self.is_locked)} mode:{self._mode} at {hex(id(self))}>'

    def __del__(self):
        """Systematically release outstanding acquired lock layers ensuring clear background thread disconnection cleanups loops."""
        self.release_all()
        self.files_obj.LCK_close()

    def release_all(self) -> bool: # pragma: no cover
        """Forcibly clear outstanding threads registries resetting allocation states metrics fields.

        Returns:
            bool: True if parameters resolve and wake pending queues entities cleanly, False if lock primitives fail.
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
        """systematically purge and delete physical transaction lock tracker files nodes anchors from disk storage devices pools."""
        try:
            self.files_obj.LCK_remove()
        except FileNotFoundError:
            pass

    @property
    def is_locked(self) -> bool:
        """Check if any transaction thread currently holds active exclusive control flags markers indices.

        Returns:
            bool: True if the internal active transaction indicator is set, False otherwise.
        """
        return self._mode == 'r' or self._mode == 'w'

    @property
    def mode(self) -> str:
        """Get the current operational access lock rule character indicator code token text format.

        Returns:
            str: Status string token ('r' for read shared lock, 'w' for write exclusive lock, or empty '').
        """
        return self._mode

    @contextmanager
    def rlock(self): # pragma: no cover
        """Context manager abstraction handling safe shared reading transaction loop isolation blocks rules workflows parameters.

        Yields:
            None: Context controller manager lifecycle initialization yield lane track.
        """
        self.acquire(read_only=True)
        try:
            yield
        finally:
            self.release()

    @contextmanager
    def wlock(self): # pragma: no cover
        """Context manager abstraction handling exclusive transaction barrier limits preventing mutative concurrency overlaps cross execution lines.

        Yields:
            None: Context controller manager lifecycle initialization yield lane track.
        """
        self.acquire(read_only=False)
        try:
            yield

        finally:
            self.release()

    def has_SIGINT(self) -> bool:
        """Verify if a cancellation signal triggered while thread operations were isolated inside critical transactional logic boundaries.

        Returns:
            bool: True if an interruption happened, False otherwise.
        """
        return self.SIGINT.is_called()

    def can_lock(self) -> bool:
        """Test and verify if the storage system allows immediate write lock allocation profiles setup without blocking.

        Returns:
            bool: True if system resources are ready for non-blocking lock setup, False otherwise.
        """
        try:
            self.acquire(block=False, read_only=False)
            return True

        except FileLockException: # pragma: no cover
            return False

        finally:
            self.release()

    def acquire(self, block:bool=True, read_only:bool=False) -> int:
        """Request and secure process isolation locks matching shared reading or exclusive writing transaction guidelines parameters.

        Handles complex scenario workflows like downgrading and upward re-escalation from read tokens straight to write tokens.

        Args:
            block (bool, optional): True = block mode, False = non-block mode
            read_only (bool, optional): Choose shared multi-reader capabilities instead of unique execution write slots properties. Defaults to False.

        Returns:
            int: The active unique execution thread identifier key integer address logging resource allocation controls.

        Raises:
            RuntimeError: If primary application mutex components break or fail thread lock synchronization steps.
            FileLockException: If thread operations trigger timeout thresholds limits or encounter non-blocking lock collisions.
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
                                self.files_obj.LCK_unlock()

                            except OSError as e: # pragma: no cover
                                print(e)
                                if self._mode == 'x':
                                    continue

                            _mode = self._mode = ''
                            self._cond.notify_all()
                            continue

                    else: # pragma: no cover
                        _idents[ident] = _cnt - 1

                if _mode != '':
                    if not block:
                        raise FileLockException(f"Could not acquire lock on {self.files_obj.get_name()}") # pragma: no cover

                    self._cond.wait()
                    continue

                # [2] process level
                try:
                    if read_only:
                        self.files_obj.LCK_rlock(block=False)
                        self._mode = 'r'
                    else:
                        self.files_obj.LCK_wlock(block=False)
                        self._mode = 'w'
                        self.SIGINT.disable()

                    _idents[ident] += 1
                    self._cond.notify_all()
                    return ident

                except BlockingIOError as e:
                    if not block: # pragma: no cover
                        raise FileLockException(f"Could not acquire lock on {self.files_obj.get_name()}") from e

                    self._mode = 'p'
                    self._lock.release()
                    os_lock_acquired = False
                    os_err = None
                    if self._mode != 'p':  # pragma: no cover
                        continue

                    try:
                        if read_only:
                            self.files_obj.LCK_rlock(block=True)
                        else:
                            self.files_obj.LCK_wlock(block=True)
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
                                self.files_obj.LCK_unlock()
                            except OSError as e1:
                                print(e1)

                        raise FileLockException("FileLock is closed or being destroyed.") from e

                    if os_err is not None: # pragma: no cover
                        raise FileLockException(f"Could not acquire lock on {self.files_obj.get_name()}") from os_err

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
        """Relinquish acquired concurrency control privileges yielding structural access metrics keys back onto common system execution pools.

        Returns:
            int: The active executing thread location identifier number integer value.

        Raises:
            RuntimeError: If multi-threaded file locks primitive synchronization drivers break execution pathways models.
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
                        self.files_obj.LCK_unlock()
                    except OSError as e1: # pragma: no cover
                        print(e1)
                    self._mode =  ''

                self._cond.notify_all()

            return ident

        finally:
            self._lock.release()

#
