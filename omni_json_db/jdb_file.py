# pylint: disable=ungrouped-imports,too-many-lines,W1514,R1732
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from io import RawIOBase
from typing import Optional, Union, IO
from os import SEEK_SET, SEEK_CUR, SEEK_END, makedirs, getcwd
from os import remove as os_remove, stat as os_stat, fsync as os_fsync
from os.path import basename, dirname, join as path_join, exists as path_exists
from os import open as os_open, close as os_close, O_APPEND, O_CREAT
from datetime import datetime
from threading import Lock, Condition
#-----------------------------------------------------------------------------
OPEN_FLAGS = O_APPEND | O_CREAT
try:
    from fcntl import LOCK_SH, LOCK_NB, LOCK_EX, LOCK_UN, flock

    def file_rlock(fd:int, LCK_file:str, block:bool=False) -> int:  # pragma: no cover
        """Acquire a shared (read) OS-level file lock.

        Args:
            fd (int | IO): An existing file descriptor or file object. If ``None`` or ``0``, 
                a new descriptor/object will be opened.
            LCK_file (str): The system path pointing to the targeted lock file.
            block (bool, optional): If ``True``, block until the lock can be acquired. 
                If ``False``, attempt non-blocking mode. Defaults to ``False``.

        Returns:
            int | IO: The active file descriptor or file object holding the shared lock.

        Raises:
            BlockingIOError: If ``block=False`` and the lock cannot be acquired immediately 
                because another process holds an exclusive lock.
        """
        if fd is None:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            flock(fd, (LOCK_SH | LOCK_NB) if not block else LOCK_SH)
            return fd

        except (IOError, OSError) as e:
            if fd is not None:
                try:
                    os_close(fd)
                except OSError as e1: # pragma: no cover
                    print(e1)
            raise BlockingIOError from e

    def file_wlock(fd:int, LCK_file:str, block:bool=False) -> int:  # pragma: no cover
        """Acquire an exclusive (write) OS-level file lock.

        Args:
            fd (int | IO): An existing file descriptor or file object. If ``None`` or ``0``, 
                a new descriptor/object will be opened.
            LCK_file (str): The system path pointing to the targeted lock file.
            block (bool, optional): If ``True``, block until the lock can be acquired. 
                If ``False``, attempt non-blocking mode. Defaults to ``False``.

        Returns:
            int | IO: The active file descriptor or file object holding the exclusive lock.

        Raises:
            BlockingIOError: If ``block=False`` and the lock cannot be acquired immediately 
                due to existing readers or writers.
        """
        if fd is None:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            flock(fd, (LOCK_EX | LOCK_NB) if not block else LOCK_EX)
            return fd

        except (IOError, OSError) as e:
            if fd is not None:
                try:
                    os_close(fd)
                except OSError as e1: # pragma: no cover
                    print(e1)
            raise BlockingIOError from e

    def file_unlock(fd:int):  # pragma: no cover
        """Release the file lock and safely close the file descriptor/object.

        Args:
            fd (int | IO): The open file descriptor or file object to unlock and close.
        """
        if fd is not None:
            try:
                flock(fd, LOCK_UN)
                os_close(fd)
            except (IOError, OSError) as e: # pragma: no cover
                print(e)

except ImportError:
    # Windows fallback: call the Win32 API (LockFileEx / UnlockFileEx) directly
    # through ctypes. This natively provides BOTH shared (read) and exclusive
    # (write) advisory locks, so portalocker is no longer required.
    #
    # NOTE: the stdlib ``msvcrt.locking()`` only exposes exclusive byte-range
    # locks and cannot express a true shared/read lock (multiple concurrent
    # readers), which is why LockFileEx is used here instead.
    import msvcrt
    import ctypes
    from ctypes import wintypes

    # The lock file is never read from or written to -- it is only a target for
    # byte-range locks -- so a raw OS file descriptor (os.open / os.close) is
    # used instead of a buffered Python file object, mirroring the POSIX branch.

    _LOCKFILE_FAIL_IMMEDIATELY = 0x00000001  # non-blocking attempt
    _LOCKFILE_EXCLUSIVE_LOCK   = 0x00000002  # write lock; omit the flag for a shared lock

    # Lock exactly one byte at offset 0. Every rlock/wlock/unlock call operates
    # on this same region, so shared vs. exclusive requests conflict correctly.
    # Windows allows locking byte ranges beyond EOF, so an empty lock file is fine.
    _LOCK_OFFSET_LOW  = 0x00000000
    _LOCK_OFFSET_HIGH = 0x00000000
    _LOCK_BYTES_LOW   = 0x00000001
    _LOCK_BYTES_HIGH  = 0x00000000

    class _OVERLAPPED(ctypes.Structure): # pylint: disable=too-few-public-methods
        _fields_ = [
            ('Internal',     ctypes.c_void_p),
            ('InternalHigh', ctypes.c_void_p),
            ('Offset',       wintypes.DWORD),
            ('OffsetHigh',   wintypes.DWORD),
            ('hEvent',       wintypes.HANDLE),
        ]

    _kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    _LockFileEx = _kernel32.LockFileEx
    _LockFileEx.restype = wintypes.BOOL
    _LockFileEx.argtypes = [
        wintypes.HANDLE,             # hFile
        wintypes.DWORD,              # dwFlags
        wintypes.DWORD,              # dwReserved (must be 0)
        wintypes.DWORD,              # nNumberOfBytesToLockLow
        wintypes.DWORD,              # nNumberOfBytesToLockHigh
        ctypes.POINTER(_OVERLAPPED), # lpOverlapped
    ]

    _UnlockFileEx = _kernel32.UnlockFileEx
    _UnlockFileEx.restype = wintypes.BOOL
    _UnlockFileEx.argtypes = [
        wintypes.HANDLE,             # hFile
        wintypes.DWORD,              # dwReserved (must be 0)
        wintypes.DWORD,              # nNumberOfBytesToUnlockLow
        wintypes.DWORD,              # nNumberOfBytesToUnlockHigh
        ctypes.POINTER(_OVERLAPPED), # lpOverlapped
    ]

    def _win_overlapped() -> _OVERLAPPED:
        """Build an OVERLAPPED struct pointing at the fixed lock region (offset 0)."""
        ov = _OVERLAPPED()
        ov.Offset = _LOCK_OFFSET_LOW        # pylint: disable=W0201
        ov.OffsetHigh = _LOCK_OFFSET_HIGH   # pylint: disable=W0201
        return ov

    def _win_lock(fd:int, exclusive:bool, block:bool):
        """Acquire a Win32 byte-range lock on the handle backing ``fd``.

        Raises:
            BlockingIOError: If the lock cannot be acquired (immediately, when
                ``block`` is False).
        """
        handle = msvcrt.get_osfhandle(fd)
        flags = 0
        if exclusive:
            flags |= _LOCKFILE_EXCLUSIVE_LOCK
        if not block:
            flags |= _LOCKFILE_FAIL_IMMEDIATELY

        ov = _win_overlapped()
        ok = _LockFileEx(handle, flags, 0, _LOCK_BYTES_LOW, _LOCK_BYTES_HIGH, ctypes.byref(ov))
        if not ok:
            err = ctypes.get_last_error()
            raise BlockingIOError(err, 'LockFileEx failed')

    def _win_unlock(fd:int):
        """Release the Win32 byte-range lock on the handle backing ``fd``."""
        handle = msvcrt.get_osfhandle(fd)
        ov = _win_overlapped()
        _UnlockFileEx(handle, 0, _LOCK_BYTES_LOW, _LOCK_BYTES_HIGH, ctypes.byref(ov))

    def file_rlock(fd:int, LCK_file:str, block:bool=False) -> int:  # pragma: no cover
        """Acquire a shared (read) OS-level file lock.

        Args:
            fd (int): An existing file descriptor. If ``None``, a new descriptor
                will be opened.
            LCK_file (str): The system path pointing to the targeted lock file.
            block (bool, optional): If ``True``, block until the lock can be acquired. 
                If ``False``, attempt non-blocking mode. Defaults to ``False``.

        Returns:
            int: The active file descriptor holding the shared lock.

        Raises:
            BlockingIOError: If ``block=False`` and the lock cannot be acquired immediately 
                because another process holds an exclusive lock.
        """
        if fd is None:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            _win_lock(fd, exclusive=False, block=block)
            return fd

        except (IOError, OSError) as e:
            if fd is not None:
                try:
                    os_close(fd)
                except OSError as e1: # pragma: no cover
                    print(e1)
            raise BlockingIOError from e

    def file_wlock(fd:int, LCK_file:str, block:bool=False) -> int:  # pragma: no cover
        """Acquire an exclusive (write) OS-level file lock.

        Args:
            fd (int): An existing file descriptor. If ``None``, a new descriptor
                will be opened.
            LCK_file (str): The system path pointing to the targeted lock file.
            block (bool, optional): If ``True``, block until the lock can be acquired. 
                If ``False``, attempt non-blocking mode. Defaults to ``False``.

        Returns:
            int: The active file descriptor holding the exclusive lock.

        Raises:
            BlockingIOError: If ``block=False`` and the lock cannot be acquired immediately 
                due to existing readers or writers.
        """
        if fd is None:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            _win_lock(fd, exclusive=True, block=block)
            return fd

        except (IOError, OSError) as e:
            if fd is not None:
                try:
                    os_close(fd)
                except OSError as e1: # pragma: no cover
                    print(e1)
            raise BlockingIOError from e

    def file_unlock(fd:int):  # pragma: no cover
        """Release the file lock and safely close the file descriptor.

        Args:
            fd (int): The open file descriptor to unlock and close.
        """
        if fd is not None:
            try:
                _win_unlock(fd)
                os_close(fd)
            except (IOError, OSError) as e: # pragma: no cover
                print(e)

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JBytesIO(RawIOBase):
    """An optimized, in-memory binary stream interface managing a mutable bytearray buffer.

    Inherits from :class:`io.RawIOBase` to provide standard I/O streaming integration.
    """
    __slots__ = ('buf', 'idx')

    def __init__(self, buffer:Optional[bytearray], *args, **kwargs):
        """Initialize the stream interface with a mutable byte storage target.

        Args:
            buffer (Optional[bytearray]): The mutable byte array serving as the underlying storage.
            *args: Variable length arguments passed directly to ``RawIOBase``.
            **kwargs: Keyword arguments passed directly to ``RawIOBase``.

        Raises:
            TypeError: If the provided buffer is not a ``bytearray``.
        """
        super().__init__(*args, **kwargs)
        self.buf = bytearray() if buffer is None else buffer
        if not isinstance(self.buf, bytearray):
            raise TypeError

        self.idx = 0

    def __del__(self):
        """Safely destruct the current context ensuring active resource components disengage."""
        self.close()
        super().__del__()

    def readable(self) -> bool: # pragma: no cover
        """Determine if the stream supports reading.

        Returns:
            bool: ``True`` if the stream is open and readable.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def readline(self, size:Optional[int]=-1) -> bytes:
        """Read and return one line from the stream.

        Reads until a newline (``\\n``) is found or the stream ends.

        Args:
            size (int, optional): The maximum number of bytes to read. Defaults to -1 (no limit).

        Returns:
            bytes: The read line, including the trailing newline character if present.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        idx = self.idx
        buf = self.buf
        max_size = len(buf)
        if idx >= max_size:
            return b''

        mv_buf = memoryview(buf)
        max_idx = max_size if size is None or size < 0 else min(max_size, idx+size)
        next_idx = buf.find(b'\n', idx, max_idx)
        if next_idx < 0: # pragma: no cover
            self.idx = max_idx
            return mv_buf[idx:max_idx].tobytes()

        next_idx = min(max_idx, next_idx+1)
        self.idx = next_idx
        return mv_buf[idx:next_idx].tobytes()

    def readlines(self, hint:Optional[int]=None) -> list: # pragma: no cover
        """Read and return a list of lines from the stream.

        Args:
            hint (int, optional): The maximum number of bytes to read across all lines. 
                Defaults to ``None`` (read all lines).

        Returns:
            list: A list of byte strings, each representing a line.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        idx = self.idx
        buf = self.buf
        max_size = len(buf)
        lines = []
        if idx >= max_size:
            return lines

        total_read = 0
        while True:
            line = self.readline()
            if not line:
                break
            lines.append(line)
            total_read += len(line)
            if hint is not None and hint > 0 and total_read >= hint: # pylint: disable=chained-comparison
                break

        return lines

    def seek(self, offset:int, whence:int=SEEK_SET) -> int:
        """Change the stream position to the given byte offset.

        Raises:
            TypeError: If ``offset`` is not an integer (matches ``io.BytesIO``).
            ValueError: If the stream is closed, ``whence`` is invalid, or the
                resulting position is negative.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        if whence == SEEK_SET:
            next_idx = int(offset)
        elif whence == SEEK_END:
            next_idx = len(self.buf)+int(offset)
        elif whence == SEEK_CUR:
            next_idx = self.idx+int(offset)
        else:
            raise ValueError(f"Invalid whence ({whence}, should be 0, 1 or 2)")

        if next_idx < 0:
            raise ValueError("negative seek position")

        self.idx = next_idx
        return next_idx

    def seekable(self) -> bool: # pragma: no cover
        """Determine if stream navigation is supported.

        Returns:
            bool: Always returns ``True`` if the stream is open.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def tell(self) -> int:
        """Return the current stream position.

        Returns:
            int: The current absolute byte offset from the start of the stream.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return self.idx

    def truncate(self, size:Optional[int]=None) -> int:
        """Resize the stream to the given size in bytes.

        Matches ``io.BytesIO`` semantics: never enlarges the buffer, raises on
        negative sizes, and returns ``size`` (the requested size) rather than
        the possibly-smaller actual buffer length.

        Raises:
            ValueError: If the stream is closed or ``size`` is negative.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        size = self.idx if size is None else size
        if size < 0:
            raise ValueError(f"negative size value {size}")

        buf = self.buf
        if size < len(buf):
            del buf[size:]

        return size

    def writable(self) -> bool: # pragma: no cover
        """Determine if the stream supports writing.

        Returns:
            bool: Always returns ``True`` if the stream is open.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def writelines(self, lines): # pragma: no cover
        """Write a list of lines to the stream.

        Args:
            lines (Any): An iterable of byte-like objects to write.

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        for line in lines:
            self.write(line)

    def read(self, size:Optional[int]=-1) -> bytes:
        """Read up to size bytes from the stream (single-copy)."""
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        max_size = len(buf)
        idx = self.idx
        next_idx = max_size if size is None or size < 0 else min(max_size, idx+size)
        if next_idx <= idx:
            return b''

        with memoryview(buf) as mv_buf:
            result = mv_buf[idx:next_idx].tobytes()

        self.idx = next_idx
        return result

    def readall(self) -> bytes: # pragma: no cover
        """Read and return all remaining bytes in the stream.

        Returns:
            bytes: The remaining binary data.

        Raises:
            ValueError: If the stream is closed.
        """
        return self.read(-1)

    def readinto(self, b) -> int:
        """Read bytes directly into a pre-allocated, mutable byte-like object.

        bytearray targets use a size-based hybrid strategy: small reads assign
        through a plain bytearray slice (CPython builds a tiny temporary, but
        object overhead is minimal), while large reads assign into
        ``memoryview(b)`` for a single direct ``memcpy`` (a plain bytearray
        slice assignment from a memoryview would first build a temporary
        bytearray, i.e. copy twice). Non-bytearray writable buffers (memoryview
        slices, ``array('I', ...)``, ...) always take the memoryview path and
        are measured in bytes like ``io.BytesIO.readinto``.

        Returns:
            int: The number of bytes copied (0 at EOF or past-end positions).

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        idx = self.idx
        rest_size = len(buf) - idx
        if rest_size <= 0:
            return 0

        rd_size = min(len(b), rest_size)
        if rd_size > 0:
            next_idx = idx+rd_size
            if rd_size < 8192:
                b[:rd_size] = memoryview(buf)[idx:next_idx]
            else:
                memoryview(b)[:rd_size] = memoryview(buf)[idx:next_idx]

            self.idx = next_idx

        return max(rd_size, 0)

    def write(self, b) -> int:
        """Write the given bytes-like object to the stream.

        Returns:
            int: The number of *bytes* written (multi-byte-itemsize inputs such
            as ``array('I', ...)`` are measured in bytes, like ``io.BytesIO``).

        Raises:
            ValueError: If the stream is closed.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        n_byte = len(b)
        if n_byte <= 0:
            return 0

        buf = self.buf
        idx = self.idx
        max_size = len(buf)
        if idx > max_size:
            buf.extend(bytes(idx - max_size)) # zero-fill the seek gap
            max_size = len(buf)

        if idx >= max_size:
            buf.extend(b)
            self.idx = len(buf)

        else:
            next_idx = idx + n_byte
            buf[idx:next_idx] = b
            self.idx = next_idx

        return n_byte

    def getvalue(self) -> bytes: # pragma: no cover
        """Return the entire buffer contents as bytes (``io.BytesIO`` parity helper)."""
        return bytes(self.buf)

    def fileno(self) -> int:
        return -1

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JFilesBase(metaclass=ABCMeta): # pragma: no cover
    """Abstract Base Class defining the standard interface for database filesystem drivers."""
    @abstractmethod
    def __eq__(self, obj) -> bool: ...
    @abstractmethod
    def copy(self) -> JFilesBase: ...
    @abstractmethod
    def fsync(self, fd:int) -> None: ...
    @abstractmethod
    def get_KEY(self) -> str: ...
    @abstractmethod
    def get_folder(self) -> str: ...
    @abstractmethod
    def get_name(self) -> str: ...
    @abstractmethod
    def get_path(self, folder:str='') -> str: ...
    @abstractmethod
    def is_group(self, KEY_file:Union[str,JFilesBase], name:str) -> bool: ...
    @abstractmethod
    def create_group(self, name:str) -> JFilesBase: ...
    @abstractmethod
    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO: ...
    @abstractmethod
    def VAL_remove(self, file_id:int=0) -> bool: ...
    @abstractmethod
    def VAL_exist(self, file_id:int=0) -> bool: ...
    @abstractmethod
    def VAL_size(self, file_id:int=0) -> int: ...
    @abstractmethod
    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO: ...
    @abstractmethod
    def KEY_size(self) -> int: ...
    @abstractmethod
    def KEY_date(self) -> int: ...
    @abstractmethod
    def LCK_rlock(self, block:bool=False): ...
    @abstractmethod
    def LCK_wlock(self, block:bool=False): ...
    @abstractmethod
    def LCK_unlock(self): ...
    @abstractmethod
    def LCK_close(self): ...
    @abstractmethod
    def LCK_remove(self): ...

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JMemFiles(JFilesBase):
    """In-memory virtual filesystem backend for transient database operations.

    Manages layout matrices and dataset segments entirely within RAM using 
    mutable bytearrays, bypassing physical storage devices.
    """
    __slots__ = ('name', 'KEY_file', 'VAL_table', 'LCK_file', 'timestamp', 'lock', 'cond')

    def __init__(self, KEY_file:Optional[bytearray]=None, VAL_table:Optional[dict]=None, LCK_file:Optional[bytearray]=None, lock:Optional[Lock]=None, cond:Optional[Condition]=None, timestamp:Optional[float]=None, name:Optional[str]=None):
        """Initialize a volatile in-memory storage manager.

        Args:
            KEY_file (bytearray, optional): Buffer for index mapping. Defaults to a new bytearray.
            VAL_table (dict, optional): Dictionary tracking ``file_id`` to content bytearrays.
            LCK_file (bytearray, optional): Mutex tracker array. Defaults to a new bytearray.
            lock (Lock, optional): Primitive synchronization engine.
            cond (Condition, optional): Condition variable for blocking concurrency.
            timestamp (float, optional): Baseline creation timestamp.
            name (str, optional): The virtual file object name.

        Raises:
            TypeError: If input parameters do not match required native types.
        """
        if KEY_file is None:
            KEY_file = bytearray()

        if VAL_table is None:
            VAL_table = {0:bytearray()}

        if LCK_file is None:
            LCK_file = bytearray()

        if lock is None:
            lock = Lock()

        if cond is None:
            cond = Condition(lock)

        if timestamp is None:
            timestamp = datetime.now().timestamp()

        name = '' if not name else name
        if not isinstance(KEY_file, bytearray):
            raise TypeError
        if not isinstance(LCK_file, bytearray):
            raise TypeError
        if not isinstance(VAL_table, dict):
            raise TypeError
        if not isinstance(timestamp, float):
            raise TypeError
        if not isinstance(name, str):
            raise TypeError

        if len(LCK_file) != 17:
            LCK_file[:] = b'\x00' * 17

        self.KEY_file = KEY_file
        self.LCK_file = LCK_file
        self.VAL_table = VAL_table
        self.lock = lock
        self.cond = cond
        self.timestamp = timestamp
        self.name = name

    def __repr__(self) -> str:
        """Generate a string representation of the memory file state.

        Returns:
            str: Diagnostic telemetry regarding memory allocations.
        """
        return f'<{type(self).__name__} KEY{self.get_KEY()}:{len(self.KEY_file)}@{hex(id(self.KEY_file))} +{len(self.VAL_table)} at {hex(id(self))}>'

    def __eq__(self, obj) -> bool:
        """Check if two memory instances share the exact same underlying key buffer.

        Args:
            obj (Any): Target entity evaluation candidate.

        Returns:
            bool: ``True`` if both objects wrap the identical in-memory bytearray.
        """
        return isinstance(obj, JMemFiles) and obj.KEY_file == self.KEY_file

    def get_KEY(self) -> str:
        """Get the primary identifier tag for this memory instance.

        Returns:
            str: A placeholder string starting with ``<MEM``.
        """
        return f'<MEM.{self.name}>' if self.name else '<MEM>'

    def get_folder(self) -> str: # pragma: no cover
        """Get the parent directory path.

        Returns:
            str: Always an empty string ``''`` in transient memory environments.
        """
        return ''

    def get_name(self) -> str:
        """Get the descriptive file signature.

        Returns:
            str: The memory signature string including the memory address.
        """
        return f'{self.get_KEY()}@{hex(id(self.KEY_file))}'

    def get_path(self, folder:str='') -> str:
        """Resolve the path mapping for the file.

        Args:
            folder (str, optional): Target layer customization. Defaults to ``''``.

        Returns:
            str: Always an empty string ``''`` in transient memory environments.
        """
        return ''

    def copy(self) -> JMemFiles:
        """Create a duplicate instance referencing the same memory buffers.

        Returns:
            JMemFiles: A replicated virtual storage controller.
        """
        return JMemFiles(self.KEY_file, self.VAL_table, self.LCK_file, lock=self.lock, cond=self.cond, timestamp=self.timestamp, name=self.name)

    def fsync(self, fd:int) -> None: # pragma: no cover
        """Mock file synchronization. Does nothing in memory mode.

        Args:
            fd (int): Target file descriptor.
        """
        if fd >= 0:
            try:
                os_fsync(fd)
            except (OSError, PermissionError, AttributeError) as e: # pragma: no cover
                print(fd, e)

    def is_group(self, KEY_file:Union[str,JFilesBase], name:str) -> bool:
        """Validate if the layout keys resolve to a volatile partition context.

        Args:
            KEY_file (str | JFilesBase): Allocation identifier.
            name (str): Label matching targeted group boundaries.

        Returns:
            bool: ``True`` if the target is a memory group.
        """
        KEY_file = KEY_file.get_KEY() if isinstance(KEY_file, JFilesBase) else KEY_file
        return KEY_file.startswith('<MEM.') and KEY_file[-1] == '>'

    def create_group(self, name:str) -> JMemFiles:
        """Create a child dataset partition in memory.

        Args:
            name (str): The cluster group name.

        Returns:
            JMemFiles: A new empty memory storage manager.
        """
        return JMemFiles(name=f'{self.name}.{name}' if self.name else name)

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO:
        """Initialize an in-memory file stream for a specific value block.

        Args:
            file_id (int, optional): The ID of the partition to open. Defaults to 0.
            mode (str, optional): Access mode (e.g., ``'rb'``). Defaults to ``'rb'``.
            buffering (int, optional): Ignored for memory arrays. Defaults to 0.
            **kwargs: Extra parameters (ignored).

        Returns:
            IO: A :class:`JBytesIO` wrapper for reading and writing memory arrays.
        """
        VAL_file = self.VAL_table.get(file_id, None)
        if VAL_file is None:
            self.VAL_table[file_id] = VAL_file = bytearray()

        return JBytesIO(VAL_file)

    def VAL_remove(self, file_id:int=0) -> bool:
        """Clear memory array elements unlinking selected partitions.

        Args:
            file_id (int, optional): The ID of the partition to delete. Defaults to 0.

        Returns:
            bool: ``True`` if successfully cleared, ``False`` if not found.
        """
        buffer = self.VAL_table.pop(file_id, None)
        if buffer is not None:
            buffer.clear()
            return True

        return False

    def VAL_exist(self, file_id:int=0) -> bool:
        """Check if a specific segment block exists in memory.

        Args:
            file_id (int, optional): The partition ID. Defaults to 0.

        Returns:
            bool: ``True`` if the byte block exists.
        """
        buffer = self.VAL_table.get(file_id, None)
        return buffer is not None

    def VAL_size(self, file_id:int=0) -> int:
        """Calculate the size of a specific in-memory partition block.

        Args:
            file_id (int, optional): The partition ID. Defaults to 0.
        
        Returns:
            int: The size in bytes, or ``-1`` if the block does not exist.
        """
        buffer = self.VAL_table.get(file_id, None)
        return -1 if buffer is None else len(buffer)

    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO:
        """Open a raw stream tracking the primary key index in memory.

        Args:
            mode (str, optional): Operation modes (e.g., ``'rb'``). Defaults to ``'rb'``.
            buffering (int, optional): Ignored. Defaults to -1.
            **kwargs: Extra attributes.

        Returns:
            IO: Virtual stream handler managing the master key bytearray.

        Raises:
            FileNotFoundError: If reading is attempted on an uninitialized context.
        """
        if not self.KEY_file and mode.startswith('r'):
            raise FileNotFoundError

        return JBytesIO(self.KEY_file)

    def KEY_size(self) -> int:
        """Calculate the total size of the key index buffer.

        Returns:
            int: The number of bytes tracking the main index.
        """
        return len(self.KEY_file)

    def KEY_date(self) -> int:
        """Get the UNIX timestamp of the memory instance creation.

        Returns:
            int: The integer timestamp.
        """
        return int(self.timestamp)

    def LCK_rlock(self, block:bool=False):
        """Acquire a shared reader lock for the memory instance.

        Allows multiple threads to read concurrently while blocking write threads.

        Args:
            block (bool, optional): If ``True``, wait until the lock is available. 
                If ``False``, raise immediately if a writer is active. Defaults to ``False``.

        Raises:
            BlockingIOError: If an exclusive write lock is held by another thread.
            RuntimeError: If the lock file has been marked as closed/removed.
        """
        current_id = id(self)
        with self.lock:
            LCK_file = self.LCK_file
            while not LCK_file[-1]:
                write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
                if write_id == 0 or write_id == current_id:
                    # set reader
                    read_cnt = int.from_bytes(LCK_file[0:4], 'big') + 1
                    LCK_file[0:4] = read_cnt.to_bytes(4, 'big')
                    self.cond.notify_all()
                    return

                if not block:
                    raise BlockingIOError('cannot acquire the lock')

                self.cond.wait() # pragma: no cover

            raise RuntimeError(f'closed {LCK_file}')

    def LCK_wlock(self, block:bool=False):
        """Acquire an exclusive writer lock for the memory instance.

        Prevents other threads from reading or writing while held.

        Args:
            block (bool, optional): If ``True``, wait until the lock is available. 
                If ``False``, raise immediately. Defaults to ``False``.
    
        Raises:
            BlockingIOError: If active transaction records indicate overlapping activities.
            RuntimeError: If the lock file has been marked as closed/removed.
        """
        current_id = id(self)
        with self.lock:
            LCK_file = self.LCK_file
            while not LCK_file[-1]:
                write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
                if write_id == current_id: # pragma: no cover
                    write_cnt = int.from_bytes(LCK_file[12:16], 'big') + 1
                    LCK_file[12:16] = write_cnt.to_bytes(4, 'big')
                    self.cond.notify_all()
                    return

                read_cnt = int.from_bytes(LCK_file[0:4], 'big')
                if read_cnt == 0 and write_id == 0:
                    LCK_file[4:12] = current_id.to_bytes(8, 'big')
                    LCK_file[12:16] = int(1).to_bytes(4, 'big') # set write_cnt = 1
                    self.cond.notify_all()
                    return

                if not block:
                    raise BlockingIOError('cannot acquire the lock')

                self.cond.wait() # pragma: no cover

            raise RuntimeError(f'closed {LCK_file}')

    def LCK_unlock(self):
        """Release session concurrency locks, returning access control to the pool."""
        current_id = id(self)
        with self.lock:
            LCK_file = self.LCK_file
            write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
            if write_id == current_id:
                write_cnt = max(0, int.from_bytes(LCK_file[12:16], 'big') - 1)
                LCK_file[12:16] = write_cnt.to_bytes(4, 'big')
                if write_cnt == 0:
                    LCK_file[4:12] = int(0).to_bytes(8, 'big') # set write_id = 0
            else:
                read_cnt = max(0, int.from_bytes(LCK_file[0:4], 'big') - 1)
                LCK_file[0:4] = read_cnt.to_bytes(4, 'big') # set read_id - 1

            self.cond.notify_all()

    def LCK_close(self): # pragma: no cover
        """Placeholder system stream shutdown routine. Does nothing in memory mode."""
        return

    def LCK_remove(self): # pragma: no cover
        """Reset concurrency tracker values, clearing the lock bytes structure."""
        with self.lock:
            LCK_file = self.LCK_file
            LCK_file[-1] = True # set remove flag
            while LCK_file[:-1].strip(b'\x00'):
                self.cond.notify_all()
                self.cond.wait(1)

            LCK_file[:] = b'\x00' * 17

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDiskFiles(JFilesBase):
    """Production file-system storage driver implementing physical disk storage.

    Maps database operations and logical indexing directly to file nodes and 
    segments on the local storage media.
    """
    __slots__ = ('KEY_file', 'VAL_file', 'LCK_file', 'LCK_fp', 'file_name', 'dir_name', 'group_KEY_file')

    def __init__(self, KEY_file:str):
        """Initialize a database management context pointing to real disk storage.

        Args:
            KEY_file (str): The absolute or relative file path locating the primary database index.

        Raises:
            TypeError: If ``KEY_file`` is not a string.
            ValueError: If ``KEY_file`` is empty or entirely whitespace.
        """
        if not isinstance(KEY_file, str):
            raise TypeError

        if not KEY_file.strip():
            raise ValueError

        file_name = basename(KEY_file)
        dir_name = dirname(KEY_file)
        if dir_name == '': # pragma: no cover
            dir_name = getcwd()

        if dir_name != '' and not path_exists(dir_name):
            makedirs(dir_name)

        self.dir_name = dir_name
        self.file_name = file_name
        self.KEY_file = KEY_file = path_join(dir_name, file_name)
        self.VAL_file = KEY_file + '.{file_id}'
        self.LCK_file = KEY_file  + '.lock'
        self.LCK_fp:Optional[Union[int, IO]] = None

        _parts = KEY_file.split('.')
        self.group_KEY_file = ('.'.join(_parts[:-1]) + '+{group_key}.' + _parts[-1]) if len(_parts) > 1 else \
                            (KEY_file + '+{group_key}')

    def __repr__(self) -> str:
        """Generate string descriptions summarizing the active driver configuration.

        Returns:
            str: Identity properties presenting the target file layout.
        """
        return f'<{type(self).__name__} KEY:{self.file_name} at {hex(id(self))}>'

    def __eq__(self, obj) -> bool:
        """Evaluate if two disk drivers point to the same physical file.

        Args:
            obj (Any): Candidate comparison storage manager instance.

        Returns:
            bool: ``True`` if path coordinates precisely match.
        """
        return isinstance(obj, JDiskFiles) and obj.KEY_file == self.KEY_file

    def get_KEY(self) -> str:
        """Extract the exact physical path to the core key index file.

        Returns:
            str: The system descriptor path string.
        """
        return self.KEY_file

    def get_folder(self) -> str: # pragma: no cover
        """Extract the absolute workspace parent directory path.

        Returns:
            str: The target directory path.
        """
        return self.dir_name

    def get_name(self) -> str:
        """Extract the specific filename of the database.

        Returns:
            str: The base filename string.
        """
        return self.file_name

    def get_path(self, folder:str='') -> str:
        """Assemble the absolute path locating the database file.

        Args:
            folder (str, optional): An optional subdirectory to append. Defaults to ``''``.

        Returns:
            str: The resolved absolute system path.
        """
        if folder == '':
            return self.KEY_file

        return path_join(self.dir_name, folder, self.file_name)

    def copy(self) -> JDiskFiles:
        """Create a duplicate driver instance pointing to the exact same file target.

        Returns:
            JDiskFiles: Duplicate disk space storage driver context.
        """
        return JDiskFiles(self.KEY_file)

    def fsync(self, fd:int) -> None:
        """Force the operating system to flush internal buffers to the physical disk.
        
        Args:
            fd (int): Target open file descriptor.
        """
        if fd >= 0:
            try:
                os_fsync(fd)
            except (OSError, PermissionError, AttributeError) as e: # pragma: no cover
                print(fd, e)

    def is_group(self, KEY_file:Union[str, JFilesBase], name:str) -> bool:
        """Cross-verify group naming structures ensuring correct namespace allocations.

        Args:
            KEY_file (str | JFilesBase): The file node indicator path.
            name (str): Label matching targeted group workspace boundaries.

        Returns:
            bool: ``True`` if criteria tests locate matching configurations.
        """
        KEY_file = KEY_file.get_KEY() if isinstance(KEY_file, JFilesBase) else KEY_file
        return KEY_file.startswith('<MEM.') or KEY_file == self.group_KEY_file.format(group_key=name)

    def create_group(self, name:str) -> JDiskFiles:
        """Assemble an isolated disk subdirectory tree configured for a partition group.

        Args:
            name (str): Cluster classification identity label.

        Returns:
            JDiskFiles: Dedicated subfolder disk management framework instance.
        """
        return JDiskFiles(self.group_KEY_file.format(group_key=name))

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, encoding:Optional[str]=None, **kwargs) -> IO:
        """Open a standard file stream for a specific value partition (VAL file).

        Args:
            file_id (int, optional): The ID of the partition file to open. Defaults to 0.
            mode (str, optional): The file access mode (e.g., ``'rb'``, ``'ab'``). Defaults to ``'rb'``.
            buffering (int, optional): Buffer size policy. Defaults to 0.
            encoding (str, optional): Character encoding (only applies to text modes). Defaults to ``None``.
            **kwargs: Extra parameters passed to the native Python ``open()``.

        Returns:
            IO: An open file object pointing to the specific storage block file.

        Raises:
            FileNotFoundError: If a read mode targets a non-existent file segment.
        """
        path = self.VAL_file.format(file_id=file_id)
        try:
            return open(path, mode=mode, buffering=buffering, encoding=encoding, **kwargs)

        except FileNotFoundError:
            if mode[0] == 'r' and mode[-1] == '+':
                return open(path, mode='w'+mode[1:], buffering=buffering, encoding=encoding, **kwargs)
            raise

    def VAL_remove(self, file_id:int=0) -> bool:
        """Delete a physical value partition file from the file system.

        Args:
            file_id (int, optional): Targeted contents partition index. Defaults to 0.

        Returns:
            bool: ``True`` if the node is successfully unlinked, ``False`` otherwise.
        """
        path = self.VAL_file.format(file_id=file_id)
        if path_exists(path):
            try:
                os_remove(path)
                return True

            except PermissionError as e: # pragma: no cover
                print(e)
                return False

        return False

    def VAL_exist(self, file_id:int=0) -> bool:
        """Validate if a specified value partition file exists on the physical disk.

        Args:
            file_id (int, optional): Partition locator code integer. Defaults to 0.

        Returns:
            bool: ``True`` if the file exists on the system.
        """
        path = self.VAL_file.format(file_id=file_id)
        return path_exists(path)

    def VAL_size(self, file_id:int=0) -> int:
        """Calculate the size of the specific VAL file.

        Args:
            file_id (int, optional): Partition locator code integer. Defaults to 0.

        Returns:
            int: The size in bytes, or ``-1`` if the file does not exist.
        """
        path = self.VAL_file.format(file_id=file_id)
        if path_exists(path):
            file_stat = os_stat(path)
            return int(file_stat.st_size)

        return -1

    def KEY_open(self, mode:str='rb', buffering:int=-1, encoding:Optional[str]=None, **kwargs) -> IO:
        """Acquire persistent transactional stream pointers connected to the core index file.

        Args:
            mode (str, optional): Target operational mode (e.g., ``'rb'``). Defaults to ``'rb'``.
            buffering (int, optional): IO array sizing buffer limits. Defaults to -1.
            encoding (str, optional): Explicit character translation rules. Defaults to ``None``.
            **kwargs: Extra arguments passed down directly to native Python ``open()``.

        Returns:
            IO: Active file stream connecting directly to the index dataset.

        Raises:
            FileNotFoundError: If a lookup fails encountering missing files across specified paths.
        """
        try:
            return open(self.KEY_file, mode=mode, buffering=buffering, encoding=encoding, **kwargs)

        except FileNotFoundError:
            if mode[0] == 'r' and mode[-1] == '+':
                return open(self.KEY_file, mode='w'+mode[1:], buffering=buffering, encoding=encoding, **kwargs)
            raise

    def KEY_size(self) -> int:
        """Extract baseline UNIX timestamp marking index file creation/modification.

        Returns:
            int: The integer timestamp log from the file system metadata.
        """
        if path_exists(self.KEY_file):
            file_stat = os_stat(self.KEY_file)
            return int(file_stat.st_size)

        return 0

    def KEY_date(self) -> int:
        """Extract baseline system epoch unix registration modification timelines indices numbers from files metadata fields layers.

        Returns:
            int: Numerical sequence timestamp logging phase alteration points timelines historical shifts.
        """
        if path_exists(self.KEY_file):
            file_stat = os_stat(self.KEY_file)
            return int(file_stat.st_ctime)

        return 0

    def LCK_rlock(self, block:bool=False):
        """Secure a platform-safe shared reader lock blocking writers but enabling read parallelism.

        Args:
            block (bool, optional): If ``True``, block until the lock becomes available. 
                If ``False``, attempt non-blocking mode. Defaults to ``False``.
    
        Raises:
            BlockingIOError: If an exclusive writer is currently active.
        """
        self.LCK_fp = file_rlock(self.LCK_fp, self.LCK_file, block=block)

    def LCK_wlock(self, block:bool=False):
        """Secure a platform-safe exclusive write barrier lock blocking parallel transactions.

        Args:
            block (bool, optional): If ``True``, block until the lock becomes available. 
                If ``False``, attempt non-blocking mode. Defaults to ``False``.
    
        Raises:
            BlockingIOError: If existing active transactions (readers or writers) overlap.
        """
        self.LCK_fp = file_wlock(self.LCK_fp, self.LCK_file, block=block)

    def LCK_unlock(self):
        """Relinquish secured filesystem concurrency locks."""
        if self.LCK_fp is not None:
            file_unlock(self.LCK_fp)
            self.LCK_fp = None

    def LCK_close(self): # pragma: no cover
        """Disengage isolation streams and safely close the lock file descriptor."""
        self.LCK_unlock()

    def LCK_remove(self): # pragma: no cover
        """Purge system lock indicators physically from disk storage."""
        self.LCK_close()
        try:
            os_remove(self.LCK_file)

        except FileNotFoundError as e: # pragma: no cover
            print(e)

        except PermissionError as e: # pragma: no cover
            print(e)
#
