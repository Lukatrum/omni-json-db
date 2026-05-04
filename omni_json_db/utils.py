from collections import defaultdict
from contextlib import contextmanager
from time import perf_counter
from threading import Lock, Event, Condition, get_ident
from random import random
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
#-----------------------------------------------------------------------------
def Style(msg, bold=None, dim=None, smso=None, underscore=None, blink=None, reverse=None, hidden=None, bright=None, fg=None, black=None, red=None, green=None, yellow=None, blue=None, magenta=None, cyan=None, white=None, bg=None, bg_black=None, bg_red=None, bg_green=None, bg_yellow=None, bg_blue=None, bg_magenta=None, bg_cyan=None, bg_white=None):
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

# https://github.com/dmfrey/FileLock
# https://github.com/benediktschmitt/py-filelock

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class INT_Handler: # pragma: no cover
    __slots__ = {'count', 'lock', 'call_flag'}

    def __init__(self):
        self.count = 0
        self.lock = Lock()
        self.call_flag = Event()
        signal(SIGINT, self.handler)

    def disable(self):
        with self.lock:
            count = self.count
            self.count = count + 1
            if count == 0:
                self.call_flag.clear()

    def enable(self):
        with self.lock:
            count = self.count = max(0, self.count-1)
            if count == 0:
                self.call_flag.clear()

    def reset(self):
        with self.lock:
            self.count = 0
            self.call_flag.clear()

    def is_called(self) -> bool:
        if self.call_flag.is_set():
            with self.lock:
                return self.count > 0 and self.call_flag.is_set()

        return False

    def handler(self, signum, frame):
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
    pass

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
DELAY_S = 1

class FileLock:
    __slots__ = {'files_obj', '_is_locked', '_lock', '_cond', '_idents', '_mode', 'SIGINT'}

    def __init__(self, files_obj:JFilesBase):
        assert isinstance(files_obj, JFilesBase)
        self.files_obj = files_obj
        self._is_locked = Event()
        self._lock = Lock()
        self._cond = Condition(self._lock)
        self._idents = defaultdict(int)
        self._mode = ''
        self.SIGINT = INT_manager

    def __repr__(self) -> str:
        return f'<{type(self).__name__} lock:{int(self.is_locked)} mode:{self._mode} at {hex(id(self))}>'

    def __del__(self):
        self.release_all()
        self.files_obj.LCK_close()

    def release_all(self) -> bool: # pragma: no cover
        if not self._lock.acquire(): # pylint: disable=consider-using-with
            return False

        try:
            while self._is_locked.is_set():
                self._cond.wait(DELAY_S)

            if self._mode == 'w':
                self.SIGINT.enable()

            self._mode = 'x'
            self._idents.clear()
            self._is_locked.clear()
            self._cond.notify_all()

        finally:
            self._lock.release()

        return True

    def reset_lock(self) -> None: # pragma: no cover
        try:
            self.files_obj.LCK_remove()
        except FileNotFoundError:
            pass

    @property
    def is_locked(self) -> bool:
        return self._is_locked.is_set()

    @property
    def mode(self) -> str:
        return self._mode

    @contextmanager
    def rlock(self): # pragma: no cover
        self.acquire(read_only=True)
        try:
            yield
        finally:
            self.release()

    @contextmanager
    def wlock(self): # pragma: no cover
        self.acquire(read_only=False)
        try:
            yield

        finally:
            self.release()

    def has_SIGINT(self) -> bool:
        return self.SIGINT.is_called()

    def can_lock(self) -> bool:
        try:
            self.acquire(timeout=0, read_only=False)
            return True

        except FileLockException: # pragma: no cover
            return False

        finally:
            self.release()

    def acquire(self, timeout:int=-1, read_only:bool=False) -> int:
        if not self._lock.acquire(): # pylint: disable=consider-using-with
            raise RuntimeError

        try:
            ident = get_ident()
            _mode = self._mode
            _idents = self._idents
            if _mode and self._is_locked.is_set():
                if _mode == 'r' and read_only:
                    # allow multiple reader
                    _idents[ident] += 1
                    return ident

                if _mode == 'w':
                    if ident in _idents:
                        # only one writer
                        _idents[ident] += 1
                        return ident

                else: # _mode == 'r' and read_only == False ('w' request)
                    _cnt = _idents[ident] = _idents.get(ident, 0) - 1
                    if _cnt <= 0:
                        _idents.pop(ident, 0)
                        if not _idents:
                            # release 'r'
                            self.files_obj.LCK_unlock()
                            self._mode = ''
                            self._is_locked.clear()
                            self._cond.notify_all()

                            # switch 'r' to 'w'
                            try:
                                self.files_obj.LCK_wlock()
                                self._mode = 'w'
                                self.SIGINT.disable()
                                _idents[ident] += 1
                                self._is_locked.set()
                                return ident

                            except BlockingIOError:
                                pass

            start_time = perf_counter() if timeout > 0 else 0
            wait = False
            while self._mode != 'x':
                try:
                    if wait:
                        wait_s = (DELAY_S if read_only else DELAY_S / 2) + random()
                        self._cond.wait(wait_s)

                    if read_only:
                        self.files_obj.LCK_rlock()
                        self._mode = 'r'

                    else:
                        self.files_obj.LCK_wlock()
                        self._mode = 'w'
                        self.SIGINT.disable()

                    _idents[ident] += 1
                    self._is_locked.set()
                    break

                except BlockingIOError as e:
                    if __debug__:
                        print(f'\t\t\t[{self.files_obj.get_name()}] {hex(ident)[-8:]} mode:{self._mode} req:{"r" if read_only else "w"} lock:{self._is_locked.is_set()} {e}')

                    if timeout == 0: # pragma: no cover
                        raise FileLockException(f"Could not acquire lock on {self.files_obj.get_name()}") from e

                    if timeout > 0: # pragma: no cover
                        if (perf_counter() - start_time) >= timeout:
                            raise FileLockException("Timeout occured.") from e

                wait = True

        finally:
            self._lock.release()

        return ident

    def release(self) -> int:
        if not self._lock.acquire(): # pylint: disable=consider-using-with
            raise RuntimeError

        try:
            _idents = self._idents
            ident = get_ident()
            if self._is_locked.is_set():
                if _idents.get(ident, 0) <= 1:
                    _idents.pop(ident, 0)
                else:
                    _idents[ident] -= 1

                if not _idents:
                    if self._mode == 'w':
                        self.SIGINT.enable()
                    self.files_obj.LCK_unlock()
                    self._mode =  ''
                    self._is_locked.clear()
                    self._cond.notify_all()

            return ident

        finally:
            self._lock.release()


# Pylint=8.28
