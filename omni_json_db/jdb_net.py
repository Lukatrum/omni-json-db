from __future__ import annotations # pylint: disable=too-many-lines
from enum import IntFlag
from io import RawIOBase
from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from struct import Struct
from socket import socket, AF_INET, SOCK_STREAM
from threading import RLock, get_ident
from typing import Optional, Union, Tuple, IO
#-----------------------------------------------------------------------------
from msgpack import packb as msg_dumps, unpackb as msg_loads
#-----------------------------------------------------------------------------
from .jdb_file import JFilesBase, JMemFiles
from .utils import Style
#from .utils import debug_break
#-----------------------------------------------------------------------------

class JErrCode(IntFlag):
    """Enumeration flags representing operational database and network transmission error codes."""
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
        bytes: The raw data received from the socket matching the 8-byte alignment structure.

    Raises:
        EOFError: If the socket connection closes before the expected byte size is received.
    """
    align_size = ((size >> 3) << 3) + (8 if size & 0x7 else 0)
    data = b''
    recv = sock.recv
    while len(data) < align_size:
        packet = recv(align_size - len(data))
        if not packet:
            raise EOFError

        data += packet

    return data

def recv_and_load(sock):
    """Receive a network stream transmission packet and decode its MsgPack payload.

    Args:
        sock (socket.socket): The active network socket connection.

    Returns:
        Any: The unpacked python structure or object from the network transmission.

    Raises:
        ValueError: If the payload header magic signature is corrupted or invalid.
    """
    header_size = Struct_header.size
    _header = recv_exactly(sock, header_size)
    if not _header:
        raise ValueError

    header, = Struct_header.unpack(_header)
    if (header & 0X_FFFF_0000_0000_0000) != 0X_FEED_0000_0000_0000:
        raise ValueError

    size = header & 0X_0000_FFFF_FFFF_FFFF
    req = recv_exactly(sock, size)
    if not req:
        raise ValueError

    try:
        return msg_loads(req[:size])

    except (ValueError, EOFError) as e: # pragma: no cover
        raise ValueError from e

def dump_and_send(sock, obj):
    """Serialize a Python object into MsgPack format and transmit it over a TCP socket.

    Prepend a magic numeric synchronization header code and pad the total transmission
    array block to align perfectly with an 8-byte matrix boundary width.

    Args:
        sock (socket.socket): The destination network socket interface stream.
        obj (Any): The payload dictionary or object structure to transmit.
    """
    data = msg_dumps(obj) or b''
    size = len(data)
    pad_size = ((size >> 3) << 3) + (8 if size & 0x7 else 0) - size
    header = Struct_header.pack(0X_FEED_0000_0000_0000 | size)
    pad_data = (header+data) if pad_size == 0 else (header+data+(b'\x00'*pad_size))
    sock.sendall(pad_data)

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JNetIO(RawIOBase):
    """Simulates a file-like streaming descriptor object over TCP network sockets.

    Translates native I/O stream method sequences down into network call sequences routed
    and tracked synchronously against a remote specialized files server.
    """
    __slots__ = {'file', 'sock', 'lock', 'mode'}

    def __init__(self, sock:IO, file:str, mode:str='rb+', **kwargs):
        """Initialize the network-backed simulated file IO pipeline stream context.

        Args:
            sock (socket.socket): Active network socket bound to the remote host.
            file (str): File identity profile path classification target (e.g., 'KEY', 'VAL.0').
            mode (str, optional): Target access mode descriptor blueprint rules. Defaults to 'rb+'.
            **kwargs: Extra parameters passed to the internal open processor.

        Raises:
            TypeError: If incoming socket or filename variables break validation constraints.
        """
        if not hasattr(sock, 'getsockname'): # pragma: no cover
            raise TypeError

        if not isinstance(file, str) or not file[:4] in {'KEY', 'LCK', 'VAL.'}: # pragma: no cover
            raise TypeError

        super().__init__()
        self.lock = RLock()
        self.file = file
        self.mode = mode
        self.sock = sock
        try:
            self.open(mode=mode, **kwargs)
        except FileNotFoundError as e: # pragma: no cover
            if __debug__:
                print(e)

    def __del__(self):
        """Safely destruct the current context ensuring network resource components disengage."""
        self.close()
        super().__del__()

    def __repr__(self) -> str:
        """Generate string descriptions summarizing primary network IO tracking configurations metrics.

        Returns:
            str: Identity properties tracking representation details.
        """
        return f'<{type(self).__name__} sock:{self.sock}  mode:{self.mode} at {hex(id(self))}>'

    def open(self, *args, **kwargs):
        """Transmit an open command block via network sockets to configure remote storage handles.

        Args:
            *args: Variable arguments matching remote file opening drivers parameters.
            **kwargs: Keyword arguments containing configuration properties overrides.

        Raises:
            FileNotFoundError: If the remote file tracking database node doesn't exist.
            ValueError: If the remote transaction context signals a corrupted operational state.
        """
        if self.closed: return # pragma: no cover
        with self.lock:
            dump_and_send(self.sock, (self.file, 'open', args, kwargs))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'): # pragma: no cover
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
                raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

    def close(self):
        """Disconnect and release streaming handles notifying the remote storage server process."""
        with self.lock:
            if self.closed: return # pragma: no cover
            dump_and_send(self.sock, (self.file, 'close', [], {}))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'): # pragma: no cover
                pass # do nothing
        super().close()

    def readline(self, size:Optional[int]= -1) -> bytes:
        """Fetch a single row line entry from the remote file endpoint bounded by a newline marker.

        Args:
            size (Optional[int], optional): Maximum byte scope limit bounding overall lookahead. Defaults to -1.

        Returns:
            bytes: The binary sequence row section line extracted from the server source.

        Raises:
            ValueError: If operating against a closed network file stream context.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, [self.file, 'readline', [size], {}])
            resp = recv_and_load(self.sock)
            if not resp.get('ok'): # pragma: no cover
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
                raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', b'')

    def readlines(self, size:Optional[int]=None) -> list: # pragma: no cover
        """Fetch all remaining rows entries lists structures systematically from remote file matrices.

        Args:
            size (Optional[int], optional): Sizing operational constraint boundary width parameters. Defaults to None.

        Returns:
            list: A list tracking segmented rows elements bytes collections matrices.

        Raises:
            ValueError: If working across deactivated network handles nodes paths.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'readlines', [size], {}))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'):
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
                raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', [])

    def seek(self, offset:int, whence:int=0) -> int:
        """Shift the file position indicator index mapping coordinates across the remote device file layer.

        Args:
            offset (int): Displaced coordinate magnitude length modifying absolute stream alignment tracking.
            whence (int, optional): Evaluation baseline anchorage strategy codes rules (0: set, 1: cur, 2: end). Defaults to 0.

        Returns:
            int: The new resolved absolute position offset metric returned by the server filesystem layer.

        Raises:
            ValueError: If executing against invalid descriptors states or network closures.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'seek', [offset, whence], {}))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'): # pragma: no cover
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
                raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', 0)

    def seekable(self) -> bool: # pragma: no cover
        """Verify if stream repositioning index operations are supported on the remote node.

        Returns:
            bool: True if tracking handles support seek operations.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            return True

    def readable(self) -> bool: # pragma: no cover
        """Verify if dataset content collection reading channels are functional.

        Returns:
            bool: True if files maps allow standard binary reading operations.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            return True

    def writable(self) -> bool: # pragma: no cover
        """Verify if system alteration write pipeline metrics can be pushed forward.

        Returns:
            bool: True if remote tracking paths authorize data updates.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            return True

    def tell(self) -> int:
        """Extract the exact active cursor position coordinate tracking address from the remote system context.

        Returns:
            int: Current byte address index tracking coordinate on device partition records.

        Raises:
            ValueError: If execution fails across corrupted network connection layers.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'tell', [], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'): # pragma: no cover
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', 0)

    def truncate(self, size:Optional[int]=None):
        """Resize storage capacity allocations forcing absolute tail changes on remote systems.

        Args:
            size (Optional[int], optional): Boundary length parameter defining the truncation cutoff length. Defaults to None.

        Returns:
            int: The terminal boundary length value logged after structural trimming execution.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'truncate', [size], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'): # pragma: no cover
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', 0)

    def writelines(self, lines): # pragma: no cover
        """Transmit an entire collection list array of line components bytes straight to server nodes storage tracks.

        Args:
            lines (Any): An iterable container processing distinct rows strings entries matrices.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'writelines', [lines], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

    def read(self, size:int=-1) -> bytes:
        """Fetch continuous segmented byte blocks arrays sequences spanning a targeted data range width.

        Args:
            size (int, optional): Count value targeting total continuous elements bytes to parse. Defaults to -1.

        Returns:
            bytes: The extracted block data component payload binary stream from remote storage.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'read', [size], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'): # pragma: no cover
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', b'')

    def readall(self) -> bytes: # pragma: no cover
        """Fetch every residual remaining unread byte block trace sitting behind remote file stream cursors.

        Returns:
            bytes: Terminal unread network data binary payload segment array block.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'readall', [], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', b'')

    def readinto(self, b) -> int: # pragma: no cover
        """Populate local external pre-allocated buffers frames in-place with bytes streamed from the network.

        Args:
            b (Any): Destination pre-allocated target bytearray.

        Returns:
            int: Measure tracking total absolute count value of bytes mapped.
        """
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'readinto', [b], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', 0)

    def write(self, b) -> int:
        """Commit binary arrays or structural payloads over the network into active database tracking regions.

        Args:
            b (Union[bytes, bytearray]): Raw input data sequence elements block array to dispatch.

        Returns:
            int: Verification logger code noting total count bytes written into server systems storage layers.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'write', [b], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'): # pragma: no cover
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            raise ValueError(f'Fail to call {cmd} -> {repr(err)}')

        return resp.get('ret', 0)

    def flush(self) -> None:
        """Flush the write buffers of the stream if applicable. This does nothing for read-only and non-blocking streams.
        """
        with self.lock:
            if self.closed: # pragma: no cover
                return

            dump_and_send(self.sock, (self.file, 'flush', [], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'): # pragma: no cover
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {repr(err)}')
            return

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JNetFiles(JFilesBase):
    """Network proxy distribution engine implementation mapping JFilesBase interfaces.

    Encapsulates and routes structural framework directives directly toward remote active
    `ThreadedTCPServer` systems instances pools.
    """
    __slots__ = ('server_addr', 'sock')

    def __init__(self, address:Tuple[str,int]=('127.0.0.1', 59898)):
        """Initialize the distributed network cluster communication client architecture.

        Args:
            address (Tuple[str, int], optional): Cluster host IP address and communication port index. Defaults to ('127.0.0.1', 59898).

        Raises:
            RuntimeError: If socket initialization workflows break or fail connection setup thresholds.
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
        """Systematically teardown communication proxies ensuring clean socket disconnection loops."""
        with self.lock:
            if self.sock and not self.sock._closed:
                self.sock.close()
                self.sock = None

    def __repr__(self) -> str:
        """Construct descriptive string layout presenting baseline port allocation markers coordinates.

        Returns:
            str: Operational configuration status summary text format.
        """
        try:
            local_port = self.sock.getsockname()[-1]
        except:
            local_port = -1

        return f'<{type(self).__name__} {local_port} <-> s:{self.server_addr} at {hex(id(self))}>'

    def __eq__(self, obj:JNetFiles) -> bool:
        """Evaluate configuration alignment checking if host addresses endpoints resolve identical matches.

        Args:
            obj (Any): Selected candidate database proxy file management object.

        Returns:
            bool: True if target server coordinates share complete profile specifications.
        """
        return isinstance(obj, JNetFiles) and self.server_addr == obj.server_addr

    def get_KEY(self) -> str:
        """Fetch remote baseline master keys identifier token code strings labels descriptors.

        Returns:
            str: Shared unique identifier naming baseline core file targets index on the server.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_KEY', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_folder(self) -> str: # pragma: no cover
        """Fetch parent location reference tree paths hosting database entities on the remote machine.

        Returns:
            str: Directory name absolute locator address string.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_folder', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_name(self) -> str:
        """Fetch dataset name tag classification code text descriptor string from the remote server.

        Returns:
            str: Filename label context text descriptor signature.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_name', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_path(self, folder:str='') -> str:
        """Assemble complete file node system addressing layout strings across server file clusters layers.

        Args:
            folder (str, optional): Target subdirectory parameter layout selector tag. Defaults to ''.

        Returns:
            str: Full path directory layout pointer notation map string.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_path', [], {'folder':folder}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def copy(self) -> JNetFiles:
        """Spawn a mirror client node instance mapping onto an identical cluster endpoint address block configuration.

        Returns:
            JNetFiles: Replicated network connection context proxy framework stream client.
        """
        if self.sock and not self.sock._closed:
            return JNetFiles(self.server_addr)

        raise IOError

    def is_group(self, KEY_file:Union[str,JFilesBase], name:str) -> bool:
        """Query if designated partition trees paths match layout guidelines managed on the remote workspace.

        Args:
            KEY_file (Union[str,JFilesBase]): Identification context key targeting specific files metrics coordinates.
            name (str): Label matching targeted group space configuration block entries properties fields.

        Returns:
            bool: True if boundaries check evaluations approve structural lineage rules alignment indicators.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                KEY_file = KEY_file.get_KEY() if isinstance(KEY_file, JFilesBase) else KEY_file
                dump_and_send(self.sock, ('KEY', 'is_group', [], {'KEY_file':KEY_file, 'name':name}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def create_group(self, name:str) -> JFilesBase:
        """Placeholder system routine managing child generation directives over active nodes parameters pipelines.

        Args:
            name (str): Designated group domain nomenclature.

        Raises:
            RuntimeError: Always raised since client configurations disallow remote multi-group creation blocks.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                raise RuntimeError

            raise IOError

    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO:
        """Initialize remote interactive access pipes targeting primary key metrics tables indices fields records.

        Args:
            mode (str, optional): Reading/writing operation access design model token code text format. Defaults to 'rb'.
            buffering (int, optional): Cache allocation boundaries sizing constraint variables rules. Defaults to -1.
            **kwargs: Extra parameters dispatched to remote file descriptor factories.

        Returns:
            IO: Open network-simulated file structure controller object.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                return JNetIO(self.sock, 'KEY', mode=mode, buffering=buffering, **kwargs)

            raise IOError

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO:
        """Initialize remote streaming pipelines targeting specific row item content components segments storage targets.

        Args:
            file_id (int, optional): Classification index tracking file segmentation boundaries numbers lines slots. Defaults to 0.
            mode (str, optional): Target access profile strategy indicator string code. Defaults to 'rb'.
            buffering (int, optional): Array processing buffering layouts constraint specifications width parameters. Defaults to 0.
            **kwargs: Extra runtime environment configurations parameters overrides.

        Returns:
            IO: Context bound network simulated data chunk input output streaming controller.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                return JNetIO(self.sock, f'VAL.{file_id}', mode=mode, buffering=buffering, **kwargs)

            raise IOError

    def VAL_remove(self, file_id:int=0) -> bool:
        """Instruct the remote instance server layer to delete selected data components partition blocks permanently.

        Args:
            file_id (int, optional): Target partition layout identification number code indicator integer position. Defaults to 0.

        Returns:
            bool: True if cleanup execution codes affirm successful item destruction, False otherwise.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'remove', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', False)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def VAL_exist(self, file_id:int=0) -> bool:
        """Query remote database indexes confirming if specific partition files lines tracks contain data assets blocks.

        Args:
            file_id (int, optional): Selection target code identification parameter integer value. Defaults to 0.

        Returns:
            bool: True if remote tracking registers identify existing data entities allocations.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'exist', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', False)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def VAL_size(self, file_id:int=0) -> int:
        """Calculate the VAL file size

        Args:
            file_id (int, optional): Classification partition track locator code integer number index. Defaults to 0.
        
        Returns:
            int: +ve = file size in byte, -ve = not exist
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'size', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', -1)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def KEY_size(self) -> int:
        """Query overall allocated width size metrics computing total index byte blocks parameters of the master key file.

        Returns:
            int: Allocation tracking value representing core index tables physical width parameters bytes layout.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'size', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', 0)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def KEY_date(self) -> int:
        """Query server metadata fields returning active unix session tracking timeline modification integers.

        Returns:
            int: Epoch sequence modification integer tracing server index sheets historical alterations.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'date', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', 0)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def LCK_rlock(self):
        """Acquire distributed thread shared reader locks executing over network transaction scopes boundaries blocks.

        Raises:
            BlockingIOError: If an exclusive writer session lock condition is active across server execution domains.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'rlock', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise BlockingIOError

    def LCK_wlock(self):
        """Acquire a distributed network-wide exclusive write barrier lock blocking parallel mutative calls.

        Raises:
            BlockingIOError: If overlapping read or write activity blocks immediate exclusive locking execution metrics.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'wlock', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise BlockingIOError

    def LCK_unlock(self):
        """Relinquish acquired concurrency network lock indicators resetting multi-threading parameters indicators."""
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'unlock', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise BlockingIOError

    def LCK_close(self): # pragma: no cover
        """Gracefully release lock indicators channels context variables avoiding distributed resource starvation models."""
        with self.lock:
            if self.sock and not self.sock._closed:
                try:
                    dump_and_send(self.sock, ('LCK', 'close', [], {}))
                    resp = recv_and_load(self.sock)

                    if resp.get('ok'):
                        return

                except OSError:
                    return

            # raise BlockingIOError

    def LCK_remove(self): # pragma: no cover
        """Purge and wipe network synchronization lock tracking references elements from remote system pools.

        Raises:
            FileNotFoundError: If lookups fail targeting missing cluster components signatures records.
        """
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'remove', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise FileNotFoundError

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class ThreadedTCPServer(ThreadingMixIn, TCPServer): # pragma: no cover
    """Multi-threaded high-performance TCP server architecture acting as distributed backend engine for JFiles."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address:str='127.0.0.1', RequestHandlerClass:Optional[BaseRequestHandler]=None, bind_and_activate:bool=True, files_obj:Optional[JFilesBase]=None, verbose:int=0, **kwargs):
        """Initialize the asynchronous socket routing engine mapping data threads limits variables configurations rules.

        Args:
            server_address (Tuple[str, int]): Endpoint combination configuration assignment supplying network IP with port. Defaults to ('127.0.0.1', 59898).
            RequestHandlerClass (Optional[BaseRequestHandler], optional): Strategy driver parsing individual connection streams logic profiles. Defaults to None.
            bind_and_activate (bool, optional): Auto-engage socket layer binding parameters directly. Defaults to True.
            files_obj (Optional[JFilesBase], optional): Baseline abstract dataset backend pipeline mapping real tables records files drivers. Defaults to None.
            verbose (int, optional): Monitoring debug resolution output granularity metric code selection value. Defaults to 0.
            **kwargs: Extra attributes routed down seamlessly into underlying initialization classes.

        Raises:
            TypeError: If incoming dataset managers violate target class interface expectations profiles.
        """
        if RequestHandlerClass is None:
            RequestHandlerClass = ServerHandler

        super().__init__(server_address, RequestHandlerClass, bind_and_activate, **kwargs)

        if files_obj is None:
            _files_obj = JMemFiles(**kwargs)
        elif isinstance(files_obj, JFilesBase):
            _files_obj = files_obj
        else:
            raise TypeError('invalid files_obj type')

        self.files_obj = _files_obj
        self.active_cnt = 0
        self.verbose = verbose

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class ServerHandler(BaseRequestHandler): # pragma: no cover
    """Asynchronous transaction stream interpreter routing incoming socket instructions into structural operations."""

    def handle(self):
        """Process incoming client execution requests continuously within an isolated, thread-safe network layer session."""
        thread_id = get_ident()
        client = f'{self.client_address}' # on {thread_id}'
        sock = self.request
        server = self.server
        server.active_cnt += 1
        verbose = server.verbose
        files_obj = server.files_obj.copy() # need to copy()
        if verbose >= 0:
            print(Style(f'[IN|#{server.active_cnt}] client:{client} on {hex(thread_id)} [sock={sock}] files:{files_obj}', green=1, bright=1))

        fp_table = {}
        try:
            while True:
                try:
                    packet = recv_and_load(sock)
                    if not packet:
                        continue

                except (EOFError, ConnectionResetError):
                    break

                except ValueError as e:
                    if verbose >= 0:
                        print(Style(f'[ERROR|{client}|{hex(thread_id)}|{files_obj}] exception:{e}', yellow=1, bright=1))
                    continue

                except Exception as e:
                    if verbose >= 0:
                        print(Style(f'[ERROR|{client}|{hex(thread_id)}|{files_obj}] exception:{e}', red=1, bright=1))
                    raise

                try:
                    file, cmd, _args, _kwargs = packet

                except ValueError:
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]Invalid format: {packet}', yellow=1))

                    dump_and_send(sock, {'ok':False, 'cmd':'', 'ret':None, 'err':JErrCode.INVALID_FMT})
                    continue

                if not file.startswith(('VAL.', 'KEY', 'LCK')):
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]Invalid file: {packet}', yellow=1))
                    dump_and_send(sock, {'ok':False, 'cmd':f'{file}', 'ret':None, 'err':JErrCode.INVALID_ID})
                    continue

                file_id = 0
                if file.startswith('VAL.'):
                    try:
                        _val_file, file_id = file.split('.')
                        file_id = int(file_id)

                    except ValueError:
                        dump_and_send(sock, {'ok':False, 'cmd':f'{file}', 'ret':None, 'err':JErrCode.INVALID_ID})
                        continue

                if not cmd or not isinstance(cmd, str):
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]{file}:Invalid command: {packet}', yellow=1))
                    dump_and_send(sock, {'ok':False, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.INVALID_CMD})
                    continue

                if not isinstance(_kwargs, dict):
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]{file}:Invalid arg type: {packet}', yellow=1))
                    dump_and_send(sock, {'ok':False, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.INVALID_ARGS})
                    continue

                is_done = True
                fp = fp_table.get(file, None)
                resp = {'ok':True, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.OKAY}
                if file == 'LCK':
                    if cmd == 'remove':
                        try:
                            resp['ret'] = files_obj.LCK_remove()
                        except FileNotFoundError:
                            resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'rlock':
                        try:
                            resp['ret'] = files_obj.LCK_rlock()
                        except BlockingIOError:
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)

                    elif cmd == 'wlock':
                        try:
                            resp['ret'] = files_obj.LCK_wlock()
                        except BlockingIOError:
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)

                    elif cmd == 'unlock':
                        try:
                            resp['ret'] = files_obj.LCK_unlock()
                        except BlockingIOError:
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)

                    elif cmd == 'close':
                        try:
                            resp['ret'] = files_obj.LCK_close()
                        except BlockingIOError:
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)

                    else:
                        if verbose >= 1:
                            print(Style(f'[FAIL|{client}]{file}: cannot find command: {packet}', yellow=1))
                        resp.update(ok=False, err=JErrCode.INVALID_CMD)

                elif file == 'KEY':
                    if cmd == 'open':
                        if fp is not None:
                            if verbose >= 0:
                                print(Style(f'[WARN|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs}) reopen() fp={fp}', yellow=1))
                            fp.flush()
                            fp.seek(0)
                        else:
                            try:
                                fp_table[file] = fp = resp['ret'] = files_obj.KEY_open(*_args, **_kwargs)
                                if fp is None:
                                    if verbose >= 1:
                                        print(Style(f'[FAIL|{client}]{file}:{cmd}({_args},{_kwargs})', yellow=1))

                                    resp.update(ok=False, err=JErrCode.FAIL_OPEN)

                            except FileNotFoundError:
                                if verbose >= 1:
                                    print(Style(f'[FAIL|{client}]{file}:{cmd}({_args},{_kwargs}) File not found', yellow=1))
                                resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'get_folder':
                        # self.dir_name
                        resp['ret'] = files_obj.get_folder()

                    elif cmd == 'get_name':
                        # self.file_name
                        resp['ret'] = files_obj.get_name()

                    elif cmd == 'get_KEY':
                        # self.file_name
                        resp['ret'] = files_obj.get_KEY()

                    elif cmd == 'get_path':
                        resp['ret'] = files_obj.get_path(*_args, **_kwargs)

                    elif cmd == 'is_group':
                        resp['ret'] = files_obj.is_group(*_args, **_kwargs)

                    elif cmd == 'create_group':
                        resp['ret'] = files_obj.create_group(*_args, **_kwargs)

                    elif cmd == 'size':
                        resp['ret'] = files_obj.KEY_size()

                    elif cmd == 'date':
                        resp['ret'] = files_obj.KEY_date()

                    else:
                        is_done = False

                else:
                    if cmd == 'open':
                        if fp is not None:
                            if verbose >= 0:
                                print(Style(f'[WARN|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs}) reopen() fp={fp}', yellow=1))
                            fp.flush()
                            fp.seek(0)
                        else:
                            try:
                                fp_table[file] = fp = resp['ret'] = files_obj.VAL_open(file_id, *_args, **_kwargs)
                                if fp is None:
                                    if verbose >= 1:
                                        print(Style(f'[FAIL|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs})', yellow=1))
                                    resp.update(ok=False, err=JErrCode.FAIL_OPEN)

                            except FileNotFoundError:
                                if verbose >= 1:
                                    print(Style(f'[FAIL|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs}) File not found', yellow=1))
                                resp.update(ok=False, err=int(JErrCode.NOT_FOUND))

                    elif cmd == 'remove':
                        resp['ret'] = files_obj.VAL_remove(file_id)

                    elif cmd == 'exist':
                        resp['ret'] = files_obj.VAL_exist(file_id)

                    elif cmd == 'size':
                        resp['ret'] = files_obj.VAL_size(file_id)

                    else:
                        is_done = False

                if not is_done:

                    if cmd == 'closed':
                        if fp is None:
                            resp['ret'] = True
                        elif fp.closed:
                            resp['ret'] = True
                            fp_table.pop(file, None)
                        else:
                            resp['ret'] = False

                    elif fp is None or fp.closed:
                        if verbose >= 1:
                            print(Style(f'[FAIL|{client}]{file}: no file object: {packet}', yellow=1))
                        resp.update(ok=False, err=JErrCode.INVALID_VAL) # ValueError

                    else:
                        try:
                            if cmd == 'close':
                                if fp is not None:
                                    fp.close()

                                fp_table.pop(file, None)

                            elif cmd == 'flush':
                                if fp is not None:
                                    fp.flush()

                            elif cmd == 'seek':
                                resp['ret'] = fp.seek(*_args, **_kwargs)

                            elif cmd == 'tell':
                                resp['ret'] = fp.tell(*_args, **_kwargs)

                            elif cmd == 'read':
                                resp['ret'] = ret = fp.read(*_args, **_kwargs)

                            elif cmd == 'write':
                                resp['ret'] = fp.write(*_args, **_kwargs)

                            elif cmd == 'truncate':
                                resp['ret'] = fp.truncate(*_args, **_kwargs)

                            elif cmd == 'readall':
                                resp['ret'] = fp.readall(*_args, **_kwargs)

                            elif cmd == 'readinto':
                                resp['ret'] = fp.readinto(*_args, **_kwargs)

                            elif cmd == 'readline':
                                resp['ret'] = fp.readline(*_args, **_kwargs)

                            elif cmd == 'readlines':
                                resp['ret'] = fp.readlines(*_args, **_kwargs)

                            elif cmd == 'writelines':
                                resp['ret'] = fp.writelines(*_args, **_kwargs)

                            else:
                                if verbose >= 1:
                                    print(Style(f'[FAIL|{client}]{file}:cannot find command: {packet}', yellow=1))
                                resp.update(ok=False, err=JErrCode.INVALID_CMD)

                        except Exception as e:
                            if verbose >= 1:
                                print(Style(f'[FAIL|{client}]{file}:{cmd}(fp={fp}, {_args}, {_kwargs}) err:{e}', yellow=1))
                            resp.update(ok=False, err=JErrCode.FAIL_CALL)

                if resp['ok']:
                    ret = resp['ret']
                    if ret is None or isinstance(ret, (int,bool,float,str)):
                        ret_s = str(ret)
                    elif isinstance(ret, (list,tuple,str,bytes,bytearray)):
                        ret_s = f"{ret[:64]}+{len(ret):,}"
                    elif isinstance(ret, (dict,set)):
                        ret_s = f"{type(ret)}+{len(ret):,}"
                    else:
                        resp['ret'] = ret_s = str(type(ret))

                    if verbose >= 2:
                        print(Style(f'[OKAY|{client}]{file}:{cmd}(fp={fp}, {_args}, {_kwargs}) -> {ret_s}', blue=1))

                dump_and_send(sock, resp)

        finally:
            for _file_name,fp in fp_table.items():
                if fp is None: continue
                try:
                    fp.close()
                except Exception as e:
                    print(e)

            if verbose >= 0:
                print(Style(f'[OUT|#{server.active_cnt}] client:{client} on {hex(thread_id)}', cyan=1, bright=1))

            server.active_cnt = max(server.active_cnt-1, 0)
            fp_table.clear()
            try:
                del files_obj
            except Exception as e:
                print(e)

#---------------------------------------------------------------------
#
