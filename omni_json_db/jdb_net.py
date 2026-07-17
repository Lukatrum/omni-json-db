from __future__ import annotations # pylint: disable=too-many-lines
from enum import IntFlag
from io import RawIOBase
from struct import Struct
from socket import socket, AF_INET, SOCK_STREAM
from threading import RLock
from typing import Optional, Union, Tuple, IO
#-----------------------------------------------------------------------------
from msgpack import packb as msg_dumps, unpackb as msg_loads
#-----------------------------------------------------------------------------
from .jdb_file import JFilesBase
#-----------------------------------------------------------------------------

class JErrCode(IntFlag):
    """Enumeration flags representing database and network error codes."""
    OKAY            = 0x00
    INVALID_FMT     = 0x01
    INVALID_ID      = 0x02
    INVALID_CMD     = 0x04
    INVALID_ARGS    = 0x08
    FAIL_OPEN       = 0x10
    INVALID_VAL     = 0x100
    FAIL_CALL       = 0x200
    NOT_FOUND       = 0x1000
    BLOCK_IO        = 0x2000

Struct_header = Struct('>Q')

def recv_exactly(sock, size:int) -> bytes:
    """Receive an exact amount of bytes from a TCP socket, aligned to 8-byte boundaries.

    Args:
        sock (socket.socket): The active network socket connection.
        size (int): The target payload length in bytes before alignment.

    Returns:
        bytes: The raw data received from the socket.

    Raises:
        EOFError: If the socket connection closes before the expected bytes are received.
    """
    align_size = ((size >> 3) << 3) + (8 if size & 0x7 else 0)
    chunks = []
    got = 0
    recv = sock.recv
    while got < align_size:
        packet = recv(align_size - got)
        if not packet:
            raise EOFError

        chunks.append(packet)
        got += len(packet)

    return b''.join(chunks)

def recv_and_load(sock):
    """Receive a network packet and decode its MsgPack payload.

    Args:
        sock (socket.socket): The active network socket connection.

    Returns:
        Any: The unpacked Python object from the network transmission.

    Raises:
        ValueError: If the payload header signature is corrupted or invalid.
    """
    header_size = Struct_header.size
    header, = Struct_header.unpack(recv_exactly(sock, header_size))
    if (header & 0X_FFFF_0000_0000_0000) != 0X_FEED_0000_0000_0000:
        raise ValueError

    size = header & 0X_0000_FFFF_FFFF_FFFF
    req = recv_exactly(sock, size)
    if size > 0 and not req:
        raise ValueError

    try:
        return msg_loads(req[:size])

    except (ValueError, EOFError) as e: # pragma: no cover
        raise ValueError from e

def dump_and_send(sock, obj):
    """Serialize an object into MsgPack format and transmit it over a TCP socket.

    Prepends an 8-byte aligned synchronization header before sending the data.

    Args:
        sock (socket.socket): The destination network socket.
        obj (Any): The payload dictionary or object to transmit.
    """
    data = msg_dumps(obj) or b''
    size = len(data)
    pad_size = ((size >> 3) << 3) + (8 if size & 0x7 else 0) - size
    header = Struct_header.pack(0X_FEED_0000_0000_0000 | size)
    buf = bytearray(8 + size + pad_size)
    buf[0:8] = header
    buf[8:8+size] = data
    sock.sendall(buf)

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JNetIO(RawIOBase):
    """Simulates a file-like stream object over a TCP network connection.

    Translates native I/O stream methods into network commands routed to a 
    remote database server.
    """
    __slots__ = ('file', 'sock', 'lock', 'mode', 'not_found')

    def __init__(self, sock:IO, file:str, mode:str='rb+', lock:RLock=None, **kwargs):
        """Initialize the network-backed file I/O stream.

        Args:
            sock (socket.socket): Active network socket connected to the remote host.
            file (str): File identity profile path (e.g., ``'KEY'``, ``'VAL.0'``).
            mode (str, optional): Target access mode. Defaults to ``'rb+'``.
            lock (RLock, optional): Lock for socket operation
            **kwargs: Extra parameters passed to the remote open command.

        Raises:
            TypeError: If the socket or filename variables are invalid.
        """
        if not hasattr(sock, 'getsockname'): # pragma: no cover
            raise TypeError

        if not isinstance(file, str) or not file[:4] in {'KEY', 'LCK', 'VAL.'}: # pragma: no cover
            raise TypeError

        super().__init__()
        self.lock = RLock() if lock is None else lock
        self.file = file
        self.mode = mode
        self.sock = sock
        self.not_found = False
        self.offset = 0
        with self.lock:
            try:
                self.open(mode=mode, **kwargs)

            except FileNotFoundError:
                self.not_found = True

    def __del__(self):
        """Safely close the stream context upon garbage collection."""
        self.close()
        super().__del__()

    def __repr__(self) -> str:
        """Return a string representation of the network stream context."""
        return f'<{type(self).__name__} sock:{self.sock}  mode:{self.mode} found:{not self.not_found} at {hex(id(self))}>'

    def __exec(self, cmd:str, args:tuple=None, kwargs:dict=None, pre_check:bool=True) -> dict:
        if pre_check:
            if self.closed: # pragma: no cover
                raise ValueError(f'I/O operation on closed file. ({self.file})')

            if self.not_found: # pragma: no cover
                raise FileNotFoundError(f'Cannot find {self.file}')

        if args is None: args = ()
        if kwargs is None: kwargs = {}

        dump_and_send(self.sock, (self.file, cmd, args, kwargs))
        resp = recv_and_load(self.sock)
        if not resp.get('ok'): # pragma: no cover
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                self.not_found = True
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp

    def open(self, *args, **kwargs):
        """Transmit an open command to configure the remote file handle.

        Args:
            *args: Variable arguments for the remote file driver.
            **kwargs: Keyword arguments for the remote file driver.

        Raises:
            FileNotFoundError: If the remote file does not exist.
            ValueError: If the remote server returns an error code.
        """
        with self.lock:
            if self.closed: return # pragma: no cover
            self.__exec('open', args, kwargs, pre_check=False)
            self.not_found = False
            self.offset = self.__exec('tell', pre_check=False).get('ret', 0)

    def close(self):
        """Disconnect and release the remote file handle on the server."""
        with self.lock:
            if self.closed or self.not_found: return # pragma: no cover
            try:
                self.__exec('close', pre_check=False)
            except FileNotFoundError: # pragma: no cover
                self.not_found = True
            except ValueError: # pragma: no cover
                pass

            super().close()

    def readline(self, size:Optional[int]= -1) -> bytes:
        """Read a single line from the remote stream.

        Args:
            size (int, optional): The maximum number of bytes to read. Defaults to -1.

        Returns:
            bytes: The extracted line from the remote server.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            rx_buf = self.__exec('readline', (size,)).get('ret', b'')
            self.offset += len(rx_buf)
            return rx_buf

    def readlines(self, size:Optional[int]=None) -> list: # pragma: no cover
        """Read and return a list of lines from the remote stream.

        Args:
            size (int, optional): The maximum number of bytes to read. Defaults to ``None``.

        Returns:
            list: A list of byte strings, each representing a line.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            rx_list = self.__exec('readlines', (size,)).get('ret', [])
            for rx_buf in rx_list:
                self.offset += len(rx_buf)
            return rx_list

    def seek(self, offset:int, whence:int=0) -> int:
        """Change the stream position on the remote server.

        Args:
            offset (int): The byte offset to move.
            whence (int, optional): The reference point (0: start, 1: current, 2: end). 
                Defaults to 0.

        Returns:
            int: The new absolute position returned by the server.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            if self.closed:
                raise ValueError(f'I/O operation on closed file. ({self.file})')

            if self.not_found: # pragma: no cover
                raise FileNotFoundError(f'Cannot find {self.file}')

            if whence == 0 and offset != self.offset or \
                    whence == 1 and offset != 0 or \
                    whence not in (0, 1):

                self.offset = self.__exec('seek', (offset, whence), pre_check=False).get('ret', 0)

            return self.offset

    def seekable(self) -> bool: # pragma: no cover
        """Determine if stream navigation is supported.

        Returns:
            bool: Always returns ``True`` if the stream is open.
        """
        with self.lock:
            if self.closed:
                raise ValueError(f'I/O operation on closed file. ({self.file})')

            if self.not_found: # pragma: no cover
                raise FileNotFoundError(f'Cannot find {self.file}')

            return True

    def readable(self) -> bool: # pragma: no cover
        """Determine if the stream supports reading.

        Returns:
            bool: Always returns ``True`` if the stream is open.
        """
        with self.lock:
            if self.closed:
                raise ValueError(f'I/O operation on closed file. ({self.file})')

            if self.not_found: # pragma: no cover
                raise FileNotFoundError(f'Cannot find {self.file}')

            return True

    def writable(self) -> bool: # pragma: no cover
        """Determine if the stream supports writing.

        Returns:
            bool: returns ``True`` if the stream is writable.
        """
        with self.lock:
            if self.closed:
                raise ValueError(f'I/O operation on closed file. ({self.file})')

            if self.not_found: # pragma: no cover
                raise FileNotFoundError(f'Cannot find {self.file}')

            return self.mode.startswith(('a', 'w')) or self.mode.endswith('+')

    def tell(self) -> int:
        """Return the current stream position from the remote server.

        Returns:
            int: The current byte address index.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            if self.closed:
                raise ValueError(f'I/O operation on closed file. ({self.file})')

            if self.not_found: # pragma: no cover
                raise FileNotFoundError(f'Cannot find {self.file}')

            return self.offset

    def truncate(self, size:Optional[int]=None):
        """Resize the remote file to the given size.

        Args:
            size (int, optional): The target size in bytes. Defaults to ``None``.

        Returns:
            int: The new terminal boundary length.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            return self.__exec('truncate', (size,)).get('ret', 0)

    def writelines(self, lines): # pragma: no cover
        """Write an iterable list of lines to the remote server.

        Args:
            lines (Any): An iterable of byte strings to write.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            self.__exec('writelines', (lines,))
            for line in lines:
                self.offset += len(line)

    def read(self, size:int=-1) -> bytes:
        """Read bytes from the remote stream.

        Args:
            size (int, optional): The maximum number of bytes to read. Defaults to -1.

        Returns:
            bytes: The binary data extracted from the remote storage.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            rx_buf = self.__exec('read', (size,)).get('ret', b'')
            self.offset += len(rx_buf)
            return rx_buf

    def readall(self) -> bytes: # pragma: no cover
        """Read all remaining bytes from the remote stream.

        Returns:
            bytes: The remaining binary data.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            rx_buf = self.__exec('readall').get('ret', b'')
            self.offset += len(rx_buf)
            return rx_buf

    def readinto(self, b) -> int:
        """Read bytes directly into a pre-allocated buffer from the network.

        Args:
            b (Any): The mutable destination buffer to populate.

        Returns:
            int: The number of bytes successfully mapped.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        with self.lock:
            size = len(b)
            rx_buf =  self.__exec('read', (size,)).get('ret', b'')
            rx_size = len(rx_buf)
            b[:rx_size] = rx_buf
            self.offset += rx_size
            return rx_size

    def write(self, b) -> int:
        """Write raw binary data to the remote server.

        Args:
            b (bytes | bytearray): The raw binary payload to dispatch.

        Returns:
            int: The number of bytes successfully written to the remote storage.

        Raises:
            ValueError: If the stream is closed, or if the server returns an error.
        """
        data = bytes(b) if not isinstance(b, (bytes, bytearray)) else b
        with self.lock:
            tx_size = self.__exec('write', (data,)).get('ret', 0)
            if tx_size >= 0:
                self.offset += tx_size
            return tx_size

    def flush(self) -> None:
        """Flush the write buffers on the remote server.

        Does nothing for read-only or non-blocking streams.

        Raises:
            FileNotFoundError: If the server cannot find the target file to flush.
        """
        with self.lock:
            if self.closed or self.not_found: # pragma: no cover
                return

            try:
                self.__exec('flush', pre_check=False)
            except FileNotFoundError: # pragma: no cover
                self.not_found = True
            except ValueError: # pragma: no cover
                pass

    def fileno(self) -> int:
        """Return the underlying file descriptor.

        Returns:
            int: Returns ``-1`` since this is a network proxy interface, or as returned 
            by the remote server.
        """
        with self.lock:
            return self.__exec('fileno').get('ret', -1)

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JNetFiles(JFilesBase):
    """Network proxy client implementing the JFilesBase filesystem driver.

    Routes file system operations to a remote `ThreadedTCPServer` database instance.
    """
    __slots__ = ('server_addr', 'sock')

    def __init__(self, address:Tuple[str,int]=('127.0.0.1', 59898)):
        """Initialize the network database client.

        Args:
            address (Tuple[str, int], optional): A tuple containing the host IP and port. 
                Defaults to ``('127.0.0.1', 59898)``.

        Raises:
            RuntimeError: If the socket connection fails.
        """
        self.lock = RLock()
        self.server_addr = address
        self.sock = None
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.connect(address)
            self.sock = sock
        except Exception as e: # pragma: no cover
            raise RuntimeError from e

    def __del__(self):
        """Disconnect the socket cleanly upon garbage collection."""
        with self.lock:
            if self.sock and not self.sock._closed:
                self.sock.close()
                self.sock = None

    def __repr__(self) -> str:
        """Return a string representation of the network client configuration."""
        try:
            local_port = self.sock.getsockname()[-1]
        except:
            local_port = -1

        return f'<{type(self).__name__} {local_port} <-> s:{self.server_addr} at {hex(id(self))}>'

    def __eq__(self, obj:JNetFiles) -> bool:
        """Check if two network clients point to the same server address.

        Args:
            obj (Any): The candidate client to compare.

        Returns:
            bool: ``True`` if the server addresses match exactly.
        """
        return isinstance(obj, JNetFiles) and self.server_addr == obj.server_addr

    def get_KEY(self) -> str:
        """Get the primary identifier path for the remote database index.

        Returns:
            str: The master key identifier from the remote server.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_KEY', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_folder(self) -> str: # pragma: no cover
        """Get the parent directory path of the remote database.

        Returns:
            str: The absolute directory path on the remote machine.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_folder', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_name(self) -> str:
        """Get the specific filename of the remote database.

        Returns:
            str: The filename string from the remote server.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_name', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_path(self, folder:str='') -> str:
        """Resolve the absolute physical path to the remote database.

        Args:
            folder (str, optional): A subdirectory to append. Defaults to ``''``.

        Returns:
            str: The resolved absolute path on the remote machine.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_path', (), {'folder':folder}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def copy(self) -> JNetFiles:
        """Create a duplicate client connected to the same server address.

        Returns:
            JNetFiles: A new network connection context proxy.

        Raises:
            IOError: If the original socket is closed.
        """
        if self.sock and not self.sock._closed:
            return JNetFiles(self.server_addr)

        raise IOError

    def fsync(self, fd:int) -> None:
        """Force the remote server to write buffers to the physical disk.
        
        Args:
            fd (int): Target file descriptor.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote fsync command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'fsync', (), {'fd':fd}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def is_group(self, KEY_file:Union[str,JFilesBase], name:str) -> bool:
        """Validate if a path belongs to a named database group on the remote server.

        Args:
            KEY_file (str | JFilesBase): The file node indicator path.
            name (str): Label matching targeted group workspace boundaries.

        Returns:
            bool: ``True`` if the group validation succeeds on the server.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                KEY_file = KEY_file.get_KEY() if isinstance(KEY_file, JFilesBase) else KEY_file
                dump_and_send(self.sock, ('KEY', 'is_group', (), {'KEY_file':KEY_file, 'name':name}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def create_group(self, name:str) -> JFilesBase:
        """Attempt to spawn a child group over the network.

        Args:
            name (str): The group namespace.

        Raises:
            RuntimeError: Always raised, as remote multi-group creation is disallowed.
            IOError: If the network socket is disconnected.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                raise RuntimeError

            raise IOError

    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO:
        """Open a network stream to read or write the remote main index (KEY) file.

        Args:
            mode (str, optional): Access mode (e.g., ``'rb'``). Defaults to ``'rb'``.
            buffering (int, optional): Buffer allocation boundaries. Defaults to -1.
            **kwargs: Extra parameters passed to the remote driver.

        Returns:
            IO: A :class:`JNetIO` stream controller object.

        Raises:
            IOError: If the network socket is disconnected.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                return JNetIO(self.sock, 'KEY', mode=mode, buffering=buffering, lock=self.lock, **kwargs)

            raise IOError

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO:
        """Open a network stream to read or write a specific remote value partition.

        Args:
            file_id (int, optional): The partition ID to open. Defaults to 0.
            mode (str, optional): Access mode (e.g., ``'rb'``). Defaults to ``'rb'``.
            buffering (int, optional): Buffer limits. Defaults to 0.
            **kwargs: Extra parameters passed to the remote driver.

        Returns:
            IO: A :class:`JNetIO` stream controller object.

        Raises:
            IOError: If the network socket is disconnected.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                return JNetIO(self.sock, f'VAL.{file_id}', mode=mode, buffering=buffering, lock=self.lock, **kwargs)

            raise IOError

    def VAL_remove(self, file_id:int=0) -> bool:
        """Delete a specific value partition file on the remote server.

        Args:
            file_id (int, optional): The partition ID to remove. Defaults to 0.

        Returns:
            bool: ``True`` if successfully deleted by the server.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'remove', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', False)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def VAL_exist(self, file_id:int=0) -> bool:
        """Check if a specific value partition exists on the remote server.

        Args:
            file_id (int, optional): The partition ID to check. Defaults to 0.

        Returns:
            bool: ``True`` if the partition exists.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'exist', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', False)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def VAL_size(self, file_id:int=0) -> int:
        """Get the byte size of a remote value partition.

        Args:
            file_id (int, optional): The partition ID to measure. Defaults to 0.
        
        Returns:
            int: The size in bytes, or ``-1`` if it does not exist.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'size', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', -1)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def KEY_size(self) -> int:
        """Get the total byte size of the remote main index (KEY) file.

        Returns:
            int: The size in bytes.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'size', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', 0)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def KEY_date(self) -> int:
        """Get the UNIX timestamp of the remote main index file modification.

        Returns:
            int: The epoch timestamp.

        Raises:
            IOError: If the network socket is disconnected.
            ValueError: If the remote command fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'date', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', 0)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def LCK_rlock(self, block:bool=False):
        """Acquire a shared reader lock on the remote server.

        Args:
            block (bool, optional): If ``True``, block until acquired. Defaults to ``False``.

        Raises:
            BlockingIOError: If an exclusive writer lock is currently active.
            RuntimeError: If a general connection or internal state error occurs.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'rlock', (block,), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

                raise BlockingIOError

            raise RuntimeError

    def LCK_wlock(self, block:bool=False):
        """Acquire an exclusive writer lock on the remote server.

        Args:
            block (bool, optional): If ``True``, block until acquired. Defaults to ``False``.

        Raises:
            BlockingIOError: If any lock (read or write) is currently active.
            RuntimeError: If a general connection or internal state error occurs.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'wlock', (block,), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

                raise BlockingIOError

            raise RuntimeError

    def LCK_unlock(self):
        """Release any held locks on the remote server.

        Raises:
            BlockingIOError: If the unlock command is rejected.
            RuntimeError: If a general connection or internal state error occurs.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'unlock', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

                raise BlockingIOError

            raise RuntimeError

    def LCK_close(self): # pragma: no cover
        """Safely close lock channels to prevent remote resource starvation."""
        with self.lock:
            if self.sock and not self.sock._closed:
                try:
                    dump_and_send(self.sock, ('LCK', 'close', (), {}))
                    resp = recv_and_load(self.sock)

                    if resp.get('ok'):
                        return

                except OSError:
                    return

    def LCK_remove(self): # pragma: no cover
        """Delete the lock file physically from the remote server.

        Raises:
            RuntimeError: If the network socket is disconnected or fails.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'remove', (), {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise RuntimeError

#---------------------------------------------------------------------
#
