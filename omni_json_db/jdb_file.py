# pylint: disable=ungrouped-imports,W1514,R1732
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from io import RawIOBase
from typing import Optional, IO
from os import SEEK_SET, SEEK_CUR, SEEK_END, makedirs, getcwd, O_APPEND, O_CREAT
from os import remove as os_remove, stat as os_stat
from os.path import basename, dirname, join as path_join, exists as path_exists
from datetime import datetime
from threading import RLock, get_ident
#-----------------------------------------------------------------------------

try:
    OPEN_FLAGS = O_APPEND | O_CREAT
    from os import oen as os_open, close as os_close
    from fcntl import LOCK_SH, LOCK_NB, LOCK_EX, LOCK_UN, flock

    def file_rlock(fd:int, LCK_file:str) -> int:
        if not fd:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            flock(fd, LOCK_SH | LOCK_NB)
            return fd

        except (IOError, OSError) as e: # pragma: no cover
            os_close(fd)
            raise BlockingIOError from e

    def file_wlock(fd:int, LCK_file:str) -> int:
        if not fd:
            fd = os_open(LCK_file, OPEN_FLAGS)

        try:
            flock(fd, LOCK_EX | LOCK_NB)
            return fd

        except (IOError, OSError) as e: # pragma: no cover
            os_close(fd)
            raise BlockingIOError from e

    def file_unlock(fd:int):
        if fd:
            flock(fd, LOCK_UN)
            os_close(fd)

except ImportError:
    from portalocker import LOCK_SH, LOCK_NB, LOCK_EX, lock as pl_lock, unlock as pl_unlock, LockException

    def file_rlock(fd:IO, LCK_file:str) -> IO:
        if not fd:
            fd = open(LCK_file, 'a+')

        try:
            pl_lock(fd, LOCK_SH | LOCK_NB)
            return fd

        except (IOError, OSError, LockException) as e: # pragma: no cover
            fd.close()
            raise BlockingIOError from e

    def file_wlock(fd:IO, LCK_file:str) -> IO:
        if not fd:
            fd = open(LCK_file, 'a+')

        try:
            pl_lock(fd, LOCK_EX | LOCK_NB)
            return fd

        except (IOError, OSError, LockException) as e: # pragma: no cover
            fd.close()
            raise BlockingIOError from e

    def file_unlock(fd:IO):
        if fd:
            pl_unlock(fd)
            fd.close()

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JBytesIO(RawIOBase):
    __slots__ = {'buf', 'idx'}

    def __init__(self, buffer:bytearray, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buf = bytearray() if buffer is None else buffer
        assert isinstance(self.buf, bytearray)
        self.idx = 0

    def __del__(self):
        self.close()
        super().__del__()

    def readable(self) -> bool: # pragma: no cover
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def readline(self, size:Optional[int]=-1) -> bytes:
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        idx = self.idx
        buf = self.buf
        max_size = len(buf)
        if idx >= max_size:
            return b''

        max_idx = max_size if size is None or size < 0 else min(max_size, idx+size)
        next_idx = buf.find(b'\n', idx, max_idx)
        if next_idx < 0:
            self.idx = max_idx
            return bytes(buf[idx:max_idx])

        next_idx = min(max_idx, next_idx+1)
        self.idx = next_idx
        return bytes(buf[idx:next_idx])

    def readlines(self, size:Optional[int]=None) -> list: # pragma: no cover
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
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        max_size = len(self.buf)
        idx = self.idx
        if whence == SEEK_SET:
            next_idx = offset
            self.idx = next_idx
            return next_idx

        if whence == SEEK_CUR:
            next_idx = idx+offset
            idx = self.idx = next_idx
            return idx

        if whence == SEEK_END:
            next_idx = max_size+offset
            idx = self.idx = next_idx
            return idx

        raise ValueError

    def seekable(self) -> bool: # pragma: no cover
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def tell(self) -> int:
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return self.idx

    def truncate(self, size:Optional[int]=None):
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
        else:
            if size < max_size:
                del buf[:size]
                idx = self.idx = len(buf)
            else:
                idx = self.idx = max_size

        return idx

    def writable(self) -> bool: # pragma: no cover
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        return True

    def writelines(self, lines): # pragma: no cover
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
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        max_size = len(buf)
        if size is None or size < 0:
            next_idx = max_size
        else:
            next_idx = min(max_size, self.idx+size)

        part = buf[self.idx:next_idx]
        self.idx = next_idx
        return bytes(part)

    def readall(self) -> bytes: # pragma: no cover
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        next_idx = len(buf)
        part = buf[self.idx:next_idx]
        self.idx = next_idx
        return bytes(part)

    def readinto(self, b) -> int: # pragma: no cover
        if self.closed:
            raise ValueError('I/O operation on closed file.')

        buf = self.buf
        next_idx = len(buf)
        b[:] = bytes(buf[self.idx:next_idx])
        self.idx = next_idx
        return len(b)

    def write(self, b) -> int:
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
    def is_group(self, KEY_file:str, name:str) -> bool: ...
    @abstractmethod
    def create_group(self, name:str) -> object: ...
    @abstractmethod
    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO: ...
    @abstractmethod
    def VAL_remove(self, file_id:int=0) -> bool: ...
    @abstractmethod
    def VAL_exist(self, file_id:int=0) -> bool: ...
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
    __slots__ = {'KEY_file', 'VAL_table', 'LCK_file', 'timestamp', 'lock'}

    def __init__(self, KEY_file:Optional[bytearray]=None, VAL_table:Optional[dict]=None, LCK_file:Optional[bytearray]=None, lock:Optional[RLock]=None, timestamp:Optional[float]=None):
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

        assert isinstance(KEY_file, bytearray)
        assert isinstance(LCK_file, bytearray)
        assert isinstance(VAL_table, dict)
        assert isinstance(timestamp, float)

        if len(LCK_file) != 16:
            LCK_file[:] = b'\x00' * 16

        self.KEY_file = KEY_file
        self.LCK_file = LCK_file
        self.VAL_table = VAL_table
        self.lock = lock
        self.timestamp = timestamp

    def __repr__(self) -> str:
        return f'<{type(self).__name__} KEY:{len(self.KEY_file)}@{hex(id(self.KEY_file))} +{len(self.VAL_table)} at {hex(id(self))}>'

    def __eq__(self, obj) -> bool:
        return isinstance(obj, JMemFiles) and obj.KEY_file == self.KEY_file

    def get_KEY(self) -> str:
        return '<MEM>'

    def get_folder(self) -> str: # pragma: no cover
        return ''

    def get_name(self) -> str:
        return f'<MEM@{hex(id(self.KEY_file))}>'

    def get_path(self, folder:str='') -> str:
        return ''

    def copy(self) -> JMemFiles:
        return JMemFiles(self.KEY_file, self.VAL_table, self.LCK_file, lock=self.lock, timestamp=self.timestamp)

    def is_group(self, KEY_file:str, name:str) -> bool:
        return KEY_file == '<MEM>'

    def create_group(self, name:str) -> JMemFiles:
        return JMemFiles()

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO:
        VAL_file = self.VAL_table.get(file_id, None)
        if VAL_file is None:
            self.VAL_table[file_id] = VAL_file = bytearray()

        return JBytesIO(VAL_file)

    def VAL_remove(self, file_id:int=0) -> bool:
        buffer = self.VAL_table.pop(file_id, None)
        if buffer is not None:
            buffer.clear()
            return True

        return False

    def VAL_exist(self, file_id:int=0) -> bool:
        buffer = self.VAL_table.get(file_id, None)
        return buffer is not None

    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO:
        return JBytesIO(self.KEY_file)

    def KEY_size(self) -> int:
        return len(self.KEY_file)

    def KEY_date(self) -> int:
        return int(self.timestamp)

    def LCK_rlock(self):
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
        current_id = get_ident()
        LCK_file = self.LCK_file
        with self.lock:
            write_id = int.from_bytes(LCK_file[4:12], 'big') # get write_id
            if write_id == current_id:
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
        pass

    def LCK_remove(self): # pragma: no cover
        with self.lock:
            self.LCK_file[:] = b'\x00' * 16

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JDiskFiles(JFilesBase):
    __slots__ = {'KEY_file', 'VAL_file', 'LCK_file', 'LCK_fp', 'file_name', 'dir_name', 'group_KEY_file'}

    def __init__(self, KEY_file:str):
        assert isinstance(KEY_file, str)
        assert KEY_file != ''
        file_name = basename(KEY_file)
        dir_name = dirname(KEY_file)

        if dir_name == '':
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
        if len(_parts) > 1:
            self.group_KEY_file = '.'.join(_parts[:-1]) + '+{group_key}.' + _parts[-1]
        else:
            self.group_KEY_file = KEY_file + '+{group_key}'

    def __repr__(self) -> str:
        return f'<{type(self).__name__} KEY:{self.file_name} at {hex(id(self))}>'

    def __eq__(self, obj) -> bool:
        return isinstance(obj, JDiskFiles) and obj.KEY_file == self.KEY_file

    def get_KEY(self) -> str:
        return self.KEY_file

    def get_folder(self) -> str: # pragma: no cover
        return self.dir_name

    def get_name(self) -> str:
        return self.file_name

    def get_path(self, folder:str='') -> str:
        if folder == '':
            return self.KEY_file

        return path_join(self.dir_name, folder, self.file_name)

    def copy(self) -> JDiskFiles:
        return JDiskFiles(self.KEY_file)

    def is_group(self, KEY_file:str, name:str) -> bool:
        return KEY_file == '<MEM>' or KEY_file == self.group_KEY_file.format(group_key=name)

    def create_group(self, name:str) -> JDiskFiles:
        return JDiskFiles(self.group_KEY_file.format(group_key=name))

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, encoding:Optional[str]=None, **kwargs) -> IO:
        path = self.VAL_file.format(file_id=file_id)
        try:
            return open(path, mode=mode, buffering=buffering, encoding=encoding, **kwargs)

        except FileNotFoundError:
            if mode[0] == 'r' and mode[-1] == '+':
                return open(path, mode='w'+mode[1:], buffering=buffering, encoding=encoding, **kwargs)
            raise

    def VAL_remove(self, file_id:int=0) -> bool:
        path = self.VAL_file.format(file_id=file_id)
        if path_exists(path):
            os_remove(path)
            return True

        return False

    def VAL_exist(self, file_id:int=0) -> bool:
        path = self.VAL_file.format(file_id=file_id)
        return path_exists(path)

    def KEY_open(self, mode:str='rb', buffering:int=-1, encoding:Optional[str]=None, **kwargs) -> IO:
        try:
            return open(self.KEY_file, mode=mode, buffering=buffering, encoding=encoding, **kwargs)

        except FileNotFoundError:
            if mode[0] == 'r' and mode[-1] == '+':
                return open(self.KEY_file, mode='w'+mode[1:], buffering=buffering, encoding=encoding, **kwargs)
            raise

    def KEY_size(self) -> int:
        if path_exists(self.KEY_file):
            file_stat = os_stat(self.KEY_file)
            return int(file_stat.st_size)

        return 0

    def KEY_date(self) -> int:
        if path_exists(self.KEY_file):
            file_stat = os_stat(self.KEY_file)
            return int(file_stat.st_ctime)

        return 0

    def LCK_rlock(self):
        self.LCK_fp = file_rlock(self.LCK_fp, self.LCK_file)

    def LCK_wlock(self):
        self.LCK_fp = file_wlock(self.LCK_fp, self.LCK_file)

    def LCK_unlock(self):
        if self.LCK_fp:
            file_unlock(self.LCK_fp)
            self.LCK_fp = None

    def LCK_close(self): # pragma: no cover
        if self.LCK_fp:
            file_unlock(self.LCK_fp)
            self.LCK_fp = None

    def LCK_remove(self): # pragma: no cover
        self.LCK_close()
        os_remove(self.LCK_file)

# Pylint=8.16
