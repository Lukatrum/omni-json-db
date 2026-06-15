# pylint: disable=ungrouped-imports,too-many-lines,W1514,R1732
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from io import RawIOBase
from typing import Optional, Union, IO
from os import SEEK_SET, SEEK_CUR, SEEK_END, makedirs, getcwd
from os import remove as os_remove, stat as os_stat
from os.path import basename, dirname, join as path_join, exists as path_exists
from datetime import datetime
from threading import RLock, get_ident
#-----------------------------------------------------------------------------

try:
    from os import open as os_open, close as os_close, O_APPEND, O_CREAT
    from fcntl import LOCK_SH, LOCK_NB, LOCK_EX, LOCK_UN, flock

    OPEN_FLAGS = O_APPEND | O_CREAT
    def file_rlock(fd:int, LCK_file:str) -> int:
        """Acquire a non-blocking shared (read) lock on a physical file descriptor.

        Args:
            fd (int): An existing file descriptor. If 0, a new file descriptor will be opened.
            LCK_file (str): System path pointing to the targeted lock file.

        Returns:
            int: The active file descriptor holding the shared lock.

        Raises:
            BlockingIOError: If the file lock cannot be acquired immediately because another thread/process holds an exclusive lock.
        """
        if not fd:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            flock(fd, LOCK_SH | LOCK_NB)
            return fd

        except (IOError, OSError) as e: # pragma: no cover
            os_close(fd)
            raise BlockingIOError from e

    def file_wlock(fd:int, LCK_file:str) -> int:
        """Acquire a non-blocking exclusive (write) lock on a physical file descriptor.

        Args:
            fd (int): An existing file descriptor. If 0, a new file descriptor will be opened.
            LCK_file (str): System path pointing to the targeted lock file.

        Returns:
            int: The active file descriptor holding the exclusive lock.

        Raises:
            BlockingIOError: If the lock cannot be acquired immediately due to existing readers or writers.
        """
        if not fd:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            flock(fd, LOCK_EX | LOCK_NB)
            return fd

        except (IOError, OSError) as e: # pragma: no cover
            os_close(fd)
            raise BlockingIOError from e

    def file_unlock(fd:int):
        """Release the acquired file lock and safely close the associated file descriptor.

        Args:
            fd (int): The open file descriptor to unlock and terminate.
        """
        if fd:
            flock(fd, LOCK_UN)
            os_close(fd)

except ImportError:
    from portalocker import LOCK_SH, LOCK_NB, LOCK_EX, lock as pl_lock, unlock as pl_unlock, LockException

    def file_rlock(fd:IO, LCK_file:str) -> IO:
        """Acquire a non-blocking shared (read) lock on a file object via cross-platform portalocker fallback.

        Args:
            fd (IO): An existing open file-like streaming handle. If None, a new file object is initialized.
            LCK_file (str): System path pointing to the targeted lock file.

        Returns:
            IO: The stream interface object holding the active shared read lock.

        Raises:
            BlockingIOError: If the shared lock cannot be established immediately.
        """
        if not fd:
            fd = open(LCK_file, 'a+')

        try:
            pl_lock(fd, LOCK_SH | LOCK_NB)
            return fd

        except (IOError, OSError, LockException) as e: # pragma: no cover
            fd.close()
            raise BlockingIOError from e

    def file_wlock(fd:IO, LCK_file:str) -> IO:
        """Acquire a non-blocking exclusive (write) lock on a file object via cross-platform portalocker fallback.

        Args:
            fd (IO): An existing open file-like streaming handle. If None, a new file object is initialized.
            LCK_file (str): System path pointing to the targeted lock file.

        Returns:
            IO: The stream interface object holding the active exclusive write lock.

        Raises:
            BlockingIOError: If the exclusive lock cannot be established immediately.
        """
        if not fd:
            fd = open(LCK_file, 'a+')

        try:
            pl_lock(fd, LOCK_EX | LOCK_NB)
            return fd

        except (IOError, OSError, LockException) as e: # pragma: no cover
            fd.close()
            raise BlockingIOError from e

    def file_unlock(fd:IO):
        """Release the portalocker-managed file lock and safely terminate the file object stream.

        Args:
            fd (IO): The open file object stream interface to unlock and close.
        """
        if fd:
            pl_unlock(fd)
            fd.close()

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JBytesIO(RawIOBase):
    """A highly optimized, raw in-memory binary stream interface managing mutable bytearray buffers.

    Inherits from `io.RawIOBase` to provide standard I/O streaming integration compatibility layers.
    """
    __slots__ = ('buf', 'idx')

    def __init__(self, buffer:bytearray, *args, **kwargs):
        """Initialize the JBytesIO stream interface instance wrapper with a mutable byte storage target.

        Args:
            buffer (bytearray): The mutable byte array serving as underlying storage framework.
            *args: Variable length arguments passed directly onto RawIOBase initializer routines.
            **kwargs: Keyword arguments passed directly onto RawIOBase initializer routines.

        Raises:
            TypeError: If the provided buffer object violates standard bytearray definitions constraints.
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
        """Determine if the underlying memory stream state actively allows reading procedures.

        Returns:
            bool: Always returns True if the stream pipeline remains open.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def readline(self, size:Optional[int]=-1) -> bytes:
        """Extract a single line array up to the nearest newline trailing character marker boundary.

        Args:
            size (Optional[int], optional): Maximum capacity ceiling threshold constraining total lookahead bytes. Defaults to -1.

        Returns:
            bytes: Raw array string containing the segment sequence elements including the line break symbol.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        idx = self.idx
        buf = self.buf
        max_size = len(buf)
        if idx >= max_size:
            return b''

        max_idx = max_size if size is None or size < 0 else min(max_size, idx+size)
        next_idx = buf.find(b'\n', idx, max_idx)
        if next_idx < 0: # pragma: no cover
            self.idx = max_idx
            return bytes(buf[idx:max_idx])

        next_idx = min(max_idx, next_idx+1)
        self.idx = next_idx
        return bytes(buf[idx:next_idx])

    def readlines(self, size:Optional[int]=None) -> list: # pragma: no cover
        """Extract all remaining segmented row matrices elements sequences wrapped as a collection list object.

        Args:
            size (Optional[int], optional): Dimensional constraint limit regulating the overall byte reading scope width. Defaults to None.

        Returns:
            list: A list array of raw bytes segments tracking rows layout arrays.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        idx = self.idx
        buf = self.buf
        max_size = len(buf)
        if idx >= max_size:
            return []

        lines = []
        max_idx = max_size if size is None or size < 0 else min(max_size, idx+size)
        while idx < max_idx:
            next_idx = buf.find(b'\n', idx, max_idx)
            if next_idx < 0:
                if idx < max_idx:
                    lines.append(bytes(buf[idx:max_idx]))

                idx = max_idx
                break

            next_idx = min(max_idx, next_idx+1)
            lines.append(bytes(buf[idx:next_idx]))
            idx = next_idx

        self.idx = idx
        return lines

    def seek(self, offset:int, whence:int=SEEK_SET) -> int:
        """Shift the absolute structural stream navigation indexing cursor position parameter.

        Args:
            offset (int): Displaced length magnitude integer modifying the track vector pointer location.
            whence (int, optional): Anchor evaluation baseline configuration rules flag (SEEK_SET, SEEK_CUR, SEEK_END). Defaults to SEEK_SET.

        Returns:
            int: The newly repositioned operational memory pointer absolute index address position.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state or invalid seek modes.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        max_size = len(self.buf)
        idx = self.idx
        if whence == SEEK_SET:
            next_idx = offset
            self.idx = next_idx
            return next_idx

        if whence == SEEK_END:
            next_idx = max_size+offset
            idx = self.idx = next_idx
            return idx

        if whence == SEEK_CUR:
            next_idx = idx+offset
            idx = self.idx = next_idx
            return idx

        raise ValueError

    def seekable(self) -> bool: # pragma: no cover
        """Determine if stream navigation repositioning procedures are supported.

        Returns:
            bool: Always returns True if the resource state is active.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def tell(self) -> int:
        """Extract the exact current absolute index cursor displacement address coordinate location metric.

        Returns:
            int: Numerical value indicating pointer address tracking position inside memory space.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return self.idx

    def truncate(self, size:Optional[int]=None):
        """Resize storage capacity thresholds forcing absolute tail adjustments.

        Args:
            size (Optional[int], optional): Boundary length parameter setting the target truncate cut. Defaults to None.

        Returns:
            int: The absolute index representing the terminal boundary length of the array after truncation.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        max_size = len(buf)
        if size is None:
            idx = self.idx
            if idx < max_size:
                del buf[idx:]
                idx = self.idx = len(buf)
            else:
                idx = self.idx = max_size
        else: # pragma: no cover
            if size < max_size:
                del buf[:size]
                idx = self.idx = len(buf)
            else:
                idx = self.idx = max_size

        return idx

    def writable(self) -> bool: # pragma: no cover
        """Determine if stream alteration or modification write pipeline behaviors are available.

        Returns:
            bool: Always returns True if the stream controller state remains open.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def writelines(self, lines): # pragma: no cover
        """Sequentially commit an iterable list collection mapping lines bytes content entries straight to storage.

        Args:
            lines (Any): An iterable container processing individual byte arrays or structures.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        idx = self.idx
        max_size = len(buf)
        if idx > max_size:
            fill_size = idx - max_size
            buf[max_size:idx] = b'\x00' * fill_size
            max_size = len(buf)

        for line in lines:
            next_idx = idx + len(line)
            if idx >= max_size:
                buf.extend(line)
            else:
                buf[idx:next_idx] = line
            idx = next_idx

        self.idx = idx

    def read(self, size:Optional[int]=-1) -> bytes:
        """Extract a structured segment continuous array block sequence matching a target width span parameter.

        Args:
            size (Optional[int], optional): Target limit value indicating total sequential element count to fetch. Defaults to -1.

        Returns:
            bytes: Copied binary payload tracking items extracted from current workspace positions.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        max_size = len(buf)
        next_idx = max_size if size is None or size < 0 else min(max_size, self.idx+size)
        part = buf[self.idx:next_idx]
        self.idx = next_idx
        return bytes(part)

    def readall(self) -> bytes: # pragma: no cover
        """Extract every remaining byte configuration sequence element left untracked behind cursor indices pointers.

        Returns:
            bytes: Unread layout array section sequence containing terminal binary contents.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        next_idx = len(buf)
        part = buf[self.idx:next_idx]
        self.idx = next_idx
        return bytes(part)

    def readinto(self, b) -> int: # pragma: no cover
        """Populate a pre-allocated external mutable data frame object directly with internal streaming buffer items.

        Args:
            b (Any): The destination mutable storage object array (e.g., bytearray) to write items into in-place.

        Returns:
            int: The total count value tracking bytes committed into the destination target layer.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
        """
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        next_idx = len(buf)
        b[:] = bytes(buf[self.idx:next_idx])
        self.idx = next_idx
        return len(b)

    def write(self, b) -> int:
        """Commit raw binary segments matrices bytes payload straight into active tracking index slots.

        Args:
            b (Union[bytes, bytearray]): Raw stream sequence input configuration layer to write.

        Returns:
            int: Total count verification number logging actual bytes committed.

        Raises:
            ValueError: If execution runs against an explicitly closed stream instance state.
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
            fill_size = idx - max_size
            buf[max_size:idx] = b'\x00' * fill_size
            max_size = len(buf)

        if idx >= max_size:
            buf.extend(b)
            self.idx = len(buf)

        else:
            next_idx = idx + n_byte
            buf[idx:next_idx] = b
            self.idx = next_idx

        return n_byte

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JFilesBase(metaclass=ABCMeta): # pragma: no cover
    """Abstract Base Class (ABC) defining explicit structural workspace pipeline blueprints for database filesystem drivers."""
    @abstractmethod
    def __eq__(self, obj) -> bool: ...
    @abstractmethod
    def copy(self) -> JFilesBase: ...
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
    def LCK_rlock(self): ...
    @abstractmethod
    def LCK_wlock(self): ...
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
    """Transient in-memory virtual filesystem backend simulation implementation bypassing storage devices hardware limits.

    Manages layout matrices and dataset segments arrays completely within memory using mutable structures wrappers.
    """
    __slots__ = ('name', 'KEY_file', 'VAL_table', 'LCK_file', 'timestamp', 'lock')

    def __init__(self, KEY_file:Optional[bytearray]=None, VAL_table:Optional[dict]=None, LCK_file:Optional[bytearray]=None, lock:Optional[RLock]=None, timestamp:Optional[float]=None, name:Optional[str]=None):
        """Initialize volatile in-memory transient array datasets mapping virtual backend tables.

        Args:
            KEY_file (Optional[bytearray], optional): In-memory buffer tracking key index structure lines maps. Defaults to None.
            VAL_table (Optional[dict], optional): Repository tracking mapped file_ids onto internal rows bytearrays blocks contents. Defaults to None.
            LCK_file (Optional[bytearray], optional): Mutex tracker array mapping shared concurrent access status bits. Defaults to None.
            lock (Optional[RLock], optional): Primitive synchronization engine tracking multi-threaded operations flows boundaries. Defaults to None.
            timestamp (Optional[float], optional): Baseline initialization timestamp mapping creation timeline markers records. Defaults to None.
            name (Optional[str], optional): File object name

        Raises:
            TypeError: If input values fail framework datatype matching specifications.
        """
        if KEY_file is None:
            KEY_file = bytearray()

        if VAL_table is None:
            VAL_table = {0:bytearray()}

        if LCK_file is None:
            LCK_file = bytearray()

        if lock is None:
            lock = RLock()

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

        if len(LCK_file) != 16:
            LCK_file[:] = b'\x00' * 16

        self.KEY_file = KEY_file
        self.LCK_file = LCK_file
        self.VAL_table = VAL_table
        self.lock = lock
        self.timestamp = timestamp
        self.name = name

    def __repr__(self) -> str:
        """Generate tracking diagnostic indicators parameters monitoring object state details.

        Returns:
            str: Telemetry presentation tracking pointer identity configurations details.
        """
        return f'<{type(self).__name__} KEY{self.get_KEY()}:{len(self.KEY_file)}@{hex(id(self.KEY_file))} +{len(self.VAL_table)} at {hex(id(self))}>'

    def __eq__(self, obj) -> bool:
        """Compare transient memory allocations checking structural source equivalence parameters trackers.

        Args:
            obj (Any): Target entity evaluation candidate.

        Returns:
            bool: True if underlying byte buffers share structural properties matching internal benchmarks.
        """
        return isinstance(obj, JMemFiles) and obj.KEY_file == self.KEY_file

    def get_KEY(self) -> str:
        """Identify primary core index data file designation token label.

        Returns:
            str: Always returns volatile code placeholder string starting with `<MEM`.
        """
        return f'<MEM.{self.name}>' if self.name else '<MEM>'

    def get_folder(self) -> str: # pragma: no cover
        """Identify parent directory folder configuration profiles.

        Returns:
            str: Empty string as records exist unbound to storage folders trees nodes paths.
        """
        return ''

    def get_name(self) -> str:
        """Identify tracking label signature mapping active address descriptors metrics.

        Returns:
            str: Descriptive placeholder tracking internal identity index tags text.
        """
        return f'{self.get_KEY()}@{hex(id(self.KEY_file))}'

    def get_path(self, folder:str='') -> str:
        """Retrieve complete directory locations tracking variables mappings on local sheets layers.

        Args:
            folder (str, optional): Context configuration placeholder. Defaults to ''.

        Returns:
            str: Empty string because pathing rules are absent inside transient environments.
        """
        return ''

    def copy(self) -> JMemFiles:
        """Clone driver parameters tracking transient state objects reference points maps structures.

        Returns:
            JMemFiles: Replicated virtual storage management context instance.
        """
        return JMemFiles(self.KEY_file, self.VAL_table, self.LCK_file, lock=self.lock, timestamp=self.timestamp, name=self.name)

    def is_group(self, KEY_file:Union[str,JFilesBase], name:str) -> bool:
        """Validate if specified layout keys resolve fine within volatile partition contexts criteria blocks.

        Args:
            KEY_file (Union[str,JFileBase]): Allocation identifier tracking targeted structural maps files context.
            name (str): Label matching targeted workspace cluster boundaries text.

        Returns:
            bool: True if key equals default runtime constraints string constants.
        """
        KEY_file = KEY_file.get_KEY() if isinstance(KEY_file, JFilesBase) else KEY_file
        return KEY_file.startswith('<MEM.') and KEY_file[-1] == '>'

    def create_group(self, name:str) -> JMemFiles:
        """Spawn virtual child dataset storage segments maps bound inside transient scopes spaces rules profiles.

        Args:
            name (str): Partition context identity token string classification label.

        Returns:
            JMemFiles: Empty virtual memory storage manager workspace pipeline handle.
        """
        return JMemFiles(name=f'{self.name}.{name}' if self.name else name)

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO:
        """Initialize in-memory file interface wrappers matching chosen virtual row content segments parts blocks.

        Args:
            file_id (int, optional): Segment index number code identifying target partition layer maps. Defaults to 0.
            mode (str, optional): Functional access configurations rule mapping. Defaults to 'rb'.
            buffering (int, optional): Buffer allocation value mapping variables configuration context rules metrics. Defaults to 0.
            **kwargs: Extra attributes ignored by virtual ram streaming controllers.

        Returns:
            IO: Memory streaming wrapper instance handling reading and writing against specific array tracks directly.
        """
        VAL_file = self.VAL_table.get(file_id, None)
        if VAL_file is None:
            self.VAL_table[file_id] = VAL_file = bytearray()

        return JBytesIO(VAL_file)

    def VAL_remove(self, file_id:int=0) -> bool:
        """Clear memory array elements unlinking selected partition byte targets completely from table maps registries.

        Args:
            file_id (int, optional): Targeted partition tracker layer identification number code index value. Defaults to 0.

        Returns:
            bool: True if cleanup execution maps confirm structural clearance, False otherwise.
        """
        buffer = self.VAL_table.pop(file_id, None)
        if buffer is not None:
            buffer.clear()
            return True

        return False

    def VAL_exist(self, file_id:int=0) -> bool:
        """Check if designated database file segment partition layers maps are allocated inside registries records.

        Args:
            file_id (int, optional): Core partition code tracker integer. Defaults to 0.

        Returns:
            bool: True if active tracks map onto valid storage arrays targets blocks.
        """
        buffer = self.VAL_table.get(file_id, None)
        return buffer is not None

    def VAL_size(self, file_id:int=0) -> int:
        """Calculate the VAL file size

        Args:
            file_id (int, optional): Classification partition track locator code integer number index. Defaults to 0.
        
        Returns:
            int: +ve = file size in byte, -ve = not exist
        """
        buffer = self.VAL_table.get(file_id, None)
        return -1 if buffer is None else len(buffer)

    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO:
        """Open raw stream tracking descriptors mapping transient core index allocations.

        Args:
            mode (str, optional): Verification operation profiles specification token code text. Defaults to 'rb'.
            buffering (int, optional): Buffer parameters sizing constraints markers variables values. Defaults to -1.
            **kwargs: Extra execution runtime attributes.

        Returns:
            IO: Virtual stream handler managing read/write changes onto master key index tables sheets fields.

        Raises:
            FileNotFoundError: If read modes strike completely unallocated data sheets contexts structures.
        """
        if not self.KEY_file and mode.startswith('r'):
            raise FileNotFoundError

        return JBytesIO(self.KEY_file)

    def KEY_size(self) -> int:
        """Calculate total index structural tracking sheets array width byte parameters.

        Returns:
            int: Number of elements currently tracking allocations size across local bytearray rows blocks.
        """
        return len(self.KEY_file)

    def KEY_date(self) -> int:
        """Extract recorded simulation unix timestamps logged during core initialization setup events timelines.

        Returns:
            int: Integer timestamp code indicating active version session baseline creation moments tracks.
        """
        return int(self.timestamp)

    def LCK_rlock(self):
        """Acquire volatile thread shared reader locks blocking writers but encouraging parallel reader paths.

        Raises:
            BlockingIOError: If an exclusive write session lock context is currently active under another execution context thread.
        """
        current_id = get_ident()
        LCK_file = self.LCK_file
        with self.lock:
            write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
            if write_id == 0 or write_id == current_id:
                # set reader
                read_cnt = int.from_bytes(LCK_file[0:4], 'big') + 1
                LCK_file[0:4] = read_cnt.to_bytes(4, 'big')
                return

        raise BlockingIOError

    def LCK_wlock(self):
        """Acquire volatile transaction exclusive writer barriers freezing alternative threads operations execution metrics.

        Raises:
            BlockingIOError: If existing active transaction records indicate reading or writing overlapping activities.
        """
        current_id = get_ident()
        LCK_file = self.LCK_file
        with self.lock:
            write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
            if write_id == current_id: # pragma: no cover
                write_cnt = int.from_bytes(LCK_file[12:16], 'big') + 1
                LCK_file[12:16] = write_cnt.to_bytes(4, 'big')
                return

            read_cnt = int.from_bytes(LCK_file[0:4], 'big')
            if read_cnt == 0 and write_id == 0:
                LCK_file[4:12] = current_id.to_bytes(8, 'big')
                LCK_file[12:16] = int(1).to_bytes(4, 'big') # set write_cnt = 1
                return

        raise BlockingIOError

    def LCK_unlock(self):
        """Release session concurrency tracking markers yielding resource block access rules control indicators back to pools."""
        current_id = get_ident()
        LCK_file = self.LCK_file
        with self.lock:
            write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
            if write_id == current_id:
                write_cnt = max(0, int.from_bytes(LCK_file[12:16], 'big') - 1)
                LCK_file[12:16] = write_cnt.to_bytes(4, 'big')
                if write_cnt == 0:
                    LCK_file[4:12] = int(0).to_bytes(8, 'big') # set write_id = 0

                return

            read_cnt = int.from_bytes(LCK_file[0:4], 'big')
            if read_cnt > 0:
                read_cnt -= 1
                LCK_file[0:4] = read_cnt.to_bytes(4, 'big') # set read_id - 1

    def LCK_close(self): # pragma: no cover
        """Placeholder system stream shutdown routine tracking pipeline variables preservation parameters limits."""
        return

    def LCK_remove(self): # pragma: no cover
        """Reset virtual concurrency tracker values initializing lock bytes matrices structures layers directly back to zero values."""
        with self.lock:
            self.LCK_file[:] = b'\x00' * 16

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDiskFiles(JFilesBase):
    """Production file-system storage driver implementing physical disk storage for database operations blocks.

    Translates logical indexing layers properties straight into file nodes segments maps paths allocations on local storage media.
    """
    __slots__ = ('KEY_file', 'VAL_file', 'LCK_file', 'LCK_fp', 'file_name', 'dir_name', 'group_KEY_file')

    def __init__(self, KEY_file:str):
        """Initialize and configure a database management context pointing toward real storage resources anchors.

        Args:
            KEY_file (str): Full target system text string path locating primary database data elements indexes sheets.

        Raises:
            TypeError: If incoming workspace path context breaks standard text string verification.
            ValueError: If string configuration evaluation checks resolve completely white-spaced or empty.
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
        self.LCK_fp = None

        _parts = KEY_file.split('.')
        self.group_KEY_file = ('.'.join(_parts[:-1]) + '+{group_key}.' + _parts[-1]) if len(_parts) > 1 else \
                            (KEY_file + '+{group_key}')

    def __repr__(self) -> str:
        """Generate string descriptions summarizing primary driver tracking configurations metrics.

        Returns:
            str: Identity properties tracking presentation text layout details.
        """
        return f'<{type(self).__name__} KEY:{self.file_name} at {hex(id(self))}>'

    def __eq__(self, obj) -> bool:
        """Evaluate structural file layout identity alignment properties across active instances paths registrations.

        Args:
            obj (Any): Candidate comparison storage manager instance selector entity.

        Returns:
            bool: True if path coordinates variables precisely match absolute path strings values targets rules.
        """
        return isinstance(obj, JDiskFiles) and obj.KEY_file == self.KEY_file

    def get_KEY(self) -> str:
        """Extract the exact physical workspace entry address matching core key index arrays layout files path.

        Returns:
            str: System descriptor string path string.
        """
        return self.KEY_file

    def get_folder(self) -> str: # pragma: no cover
        """Extract the absolute workspace parent directory path reference.

        Returns:
            str: Target directory tree path string.
        """
        return self.dir_name

    def get_name(self) -> str:
        """Extract isolated structural primary dataset filename reference string token text descriptor.

        Returns:
            str: File identity element code text name label.
        """
        return self.file_name

    def get_path(self, folder:str='') -> str:
        """Assemble accurate physical storage descriptors target addresses locating file system tree nodes.

        Args:
            folder (str, optional): Target layer customization subdirectory constraint code string. Defaults to ''.

        Returns:
            str: Absolute resolved system system node path string.
        """
        if folder == '':
            return self.KEY_file

        return path_join(self.dir_name, folder, self.file_name)

    def copy(self) -> JDiskFiles:
        """Construct an absolute replica workspace instance referencing identical target files system storage parameters.

        Returns:
            JDiskFiles: Duplicate disk space storage driver context interface controller.
        """
        return JDiskFiles(self.KEY_file)

    def is_group(self, KEY_file:Union[str, JFilesBase], name:str) -> bool:
        """Cross-verify group naming schema structures ensuring correct cluster namespace allocations alignments.

        Args:
            KEY_file (Union[str,JFilesBase]): Absolute file node layout address indicator parameter string path.
            name (str): Selector token text descriptor matching target group workspace boundaries tags context fields.

        Returns:
            bool: True if criteria tests locate matching layouts configuration blueprints rules.
        """
        KEY_file = KEY_file.get_KEY() if isinstance(KEY_file, JFilesBase) else KEY_file
        return KEY_file.startswith('<MEM.') or KEY_file == self.group_KEY_file.format(group_key=name)

    def create_group(self, name:str) -> JDiskFiles:
        """Assemble an isolated disk space subdirectory tree driver instance configured for a specific partition domain cluster.

        Args:
            name (str): Cluster classification identity label parameter key code text format layout selector.

        Returns:
            JDiskFiles: Dedicated subfolder disk system management component profile framework instance handle.
        """
        return JDiskFiles(self.group_KEY_file.format(group_key=name))

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, encoding:Optional[str]=None, **kwargs) -> IO:
        """Open streaming data lines interfaces channels pointing straight into physical contents segments blocks partitions files.

        Args:
            file_id (int, optional): Data slot track segmentation integer index number value selector code. Defaults to 0.
            mode (str, optional): Open operational access parameters strategy indicator string code. Defaults to 'rb'.
            buffering (int, optional): Operational pipeline stream array buffering system density constraints width. Defaults to 0.
            encoding (Optional[str], optional): String serialization processing algorithm format specifications token context. Defaults to None.
            **kwargs: Extra parameters passed down seamlessly onto native filesystem initialization routines frameworks.

        Returns:
            IO: Open system stream file object interface pointing toward the designated storage blocks data file slot.

        Raises:
            FileNotFoundError: If reading modes encounter absent resource targets entries paths on disk.
        """
        path = self.VAL_file.format(file_id=file_id)
        try:
            return open(path, mode=mode, buffering=buffering, encoding=encoding, **kwargs)

        except FileNotFoundError:
            if mode[0] == 'r' and mode[-1] == '+':
                return open(path, mode='w'+mode[1:], buffering=buffering, encoding=encoding, **kwargs)
            raise

    def VAL_remove(self, file_id:int=0) -> bool:
        """Unlink physical storage contents chunk segment partition files data nodes cleanly from file system layers.

        Args:
            file_id (int, optional): Targeted contents partition reference number code selection index. Defaults to 0.

        Returns:
            bool: True if data file node unlinking process completes without error, False otherwise.
        """
        path = self.VAL_file.format(file_id=file_id)
        if path_exists(path):
            os_remove(path)
            return True

        return False

    def VAL_exist(self, file_id:int=0) -> bool:
        """Validate if specified layout row blocks sections items exist inside physical disk tracks boundaries.

        Args:
            file_id (int, optional): Classification partition track locator code integer number index. Defaults to 0.

        Returns:
            bool: True if targeted files system location check tests discover live resources records, False otherwise.
        """
        path = self.VAL_file.format(file_id=file_id)
        return path_exists(path)

    def VAL_size(self, file_id:int=0) -> int:
        """Calculate the VAL file size

        Args:
            file_id (int, optional): Classification partition track locator code integer number index. Defaults to 0.

        Returns:
            int: +ve = file size in byte, -ve = not exist
        """
        path = self.VAL_file.format(file_id=file_id)
        if path_exists(path):
            file_stat = os_stat(path)
            return int(file_stat.st_size)

        return -1

    def KEY_open(self, mode:str='rb', buffering:int=-1, encoding:Optional[str]=None, **kwargs) -> IO:
        """Acquire persistent transactional stream pointers connected straight onto the core master index database keys sheets files records.

        Args:
            mode (str, optional): Target operational mode rules specification string descriptor layout context text. Defaults to 'rb'.
            buffering (int, optional): Local input output operational array sizing parameters buffers limits boundaries. Defaults to -1.
            encoding (Optional[str], optional): Explicit character translation blueprint configuration code rules. Defaults to None.
            **kwargs: Extra arguments passed down directly to storage management engines layers wrappers factories.

        Returns:
            IO: Active file descriptor stream interface binding data operations directly to primary dataset structural maps indexes tracks.

        Raises:
            FileNotFoundError: If lookups fail encountering missing system sheets targets across specified execution tracks parameters paths.
        """
        try:
            return open(self.KEY_file, mode=mode, buffering=buffering, encoding=encoding, **kwargs)

        except FileNotFoundError:
            if mode[0] == 'r' and mode[-1] == '+':
                return open(self.KEY_file, mode='w'+mode[1:], buffering=buffering, encoding=encoding, **kwargs)
            raise

    def KEY_size(self) -> int:
        """Measure current overall real byte allocations size metrics reporting primary database index index file stats.

        Returns:
            int: Structural layout allocation tracking measures integer representing file width size parameters.
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

    def LCK_rlock(self):
        """Request and secure a platform-safe shared reader lock on file layer blocking writers but enabling read parallelism features."""
        self.LCK_fp = file_rlock(self.LCK_fp, self.LCK_file)

    def LCK_wlock(self):
        """Request and secure a platform-safe exclusive write barrier lock blocking parallel transactions modifications across execution boundaries threads."""
        self.LCK_fp = file_wlock(self.LCK_fp, self.LCK_file)

    def LCK_unlock(self):
        """Relinquish secured filesystem concurrency lock structures allowing outstanding queue entities processing paths access permissions."""
        if self.LCK_fp:
            file_unlock(self.LCK_fp)
            self.LCK_fp = None

    def LCK_close(self): # pragma: no cover
        """Disengage background isolation primitives handlers streams closing file locks safely avoiding resource starvation profile leaks."""
        if self.LCK_fp:
            file_unlock(self.LCK_fp)
            self.LCK_fp = None

    def LCK_remove(self): # pragma: no cover
        """Purge system lock indicators files physically from disk storage pools completely erasing active synchronization markers tracks."""
        self.LCK_close()
        os_remove(self.LCK_file)

#
