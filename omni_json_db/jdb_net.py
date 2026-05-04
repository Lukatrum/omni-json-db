from __future__ import annotations
from enum import IntFlag
from io import RawIOBase
from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from struct import Struct
from socket import socket, AF_INET, SOCK_STREAM
from threading import RLock, get_ident
from typing import Optional, Union, Tuple, IO
#-----------------------------------------------------------------------------
from .jdb_file import JFilesBase, JMemFiles, JDiskFiles
from .jdb_io import msg_dumps, msg_loads, MIN_VALUE_SIZE, MAX_VALUE_SIZE # pylint: disable=unused-import
from .jdb_lite import JDbReader
from .utils import debug_break, Style # pylint: disable=unused-import
#-----------------------------------------------------------------------------
class JErrCode(IntFlag):
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

def run_files_server(host:str='127.0.0.1', port:int=59898, files:Union[str,bytearray,JFilesBase,JDbReader,None]=None, verbose:int=0): # pragma: no cover
    """
    Initializes and runs a multi-threaded TCP server to expose the JDb object.
    
    Args:
        host (str, optional): host address (default='127.0.0.1')
        port (int, optional): host listening port (default=59898)
        files (Union[str, bytearray, JFilesBase, JDbReader, None], optional): 
            > [str] JDiskFiles(path) object for JDb,  if empty str, use JMemFiles()
            > [bytearry] JMemFiles(KEY_file) for JDb
            > [JDiskFiles] disk files object for JDb
            > [JMemFiles] memory files object for JDb
            > [JNetFiles] network files object for JDb
            > [JDbReader] JDb files object
            > [default=None] JMemFiles()            
        verbose (int, optional): Logging level (-ve: off, 0: limit, 1: err, 4: debug).
            > -ve = disable
            > 0~4 = enable
                > 0=LIMIT (default)
                > 1=ERROR 
                > 2=WARNING 
                > 3=INFO
                > 4=DEBUG    
    Raises:
        TypeError: If the provided `files` parameter is invalid.    
    """

    if files is None or isinstance(files, bytearray):
        files_obj = JMemFiles(files)
    elif isinstance(files, JDbReader):
        files_obj = files.files_obj
    elif isinstance(files, JFilesBase):
        files_obj = files
    elif isinstance(files, str):
        files_obj = JDiskFiles(files) if files else JMemFiles()
    else:
        raise TypeError

    assert isinstance(files_obj, JFilesBase)
    print(Style(f'staring server at {host}:{port} -> {files_obj} (files={type(files)})', green=1))
    with ThreadedTCPServer((host, port), ServerHandler, files_obj=files_obj, verbose=verbose) as server:
        server.serve_forever()

Struct_header = Struct('>Q')

def recv_exactly(sock, size:int) -> bytes:
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

    except (ValueError, EOFError) as e:
        raise ValueError from e

def dump_and_send(sock, obj):
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
    """
    Simulates a file-like object using TCP network sockets. 
    Maintains synchronization between local I/O calls and the remote JFiles Server.
    """
    __slots__ = {'file', 'sock', 'lock', 'mode'}

    def __init__(self, sock:IO, file:str, mode:str='rb+', **kwargs):
        assert file[:4] in {'KEY', 'LCK', 'VAL.'}
        assert hasattr(sock, 'getsockname')
        super().__init__()
        self.lock = RLock()
        self.file = file
        self.mode = mode
        self.sock = sock
        self.open(mode=mode, **kwargs)

    def __del__(self):
        self.close()
        super().__del__()

    def __repr__(self) -> str:
        return f'<{type(self).__name__} sock:{self.sock}  mode:{self.mode} at {hex(id(self))}>'

    def open(self, *args, **kwargs):
        if self.closed: return
        with self.lock:
            dump_and_send(self.sock, (self.file, 'open', args, kwargs))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'):
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
                raise ValueError(f'Fail to call {cmd} -> {str(err)}')

    def close(self):
        with self.lock:
            if self.closed: return
            dump_and_send(self.sock, (self.file, 'close', [], {}))
            _resp = recv_and_load(self.sock)
        super().close()

    def readline(self, size:Optional[int]= -1) -> bytes:
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, [self.file, 'readline', [size], {}])
            resp = recv_and_load(self.sock)
            if not resp.get('ok'):
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
                raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', b'')

    def readlines(self, size:Optional[int]=None) -> list: # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'readlines', [size], {}))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'):
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
                raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', [])

    def seek(self, offset:int, whence:int=0) -> int:
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'seek', [offset, whence], {}))
            resp = recv_and_load(self.sock)
            if not resp.get('ok'):
                cmd = resp.get("cmd", "")
                err = JErrCode(resp.get('err', 0))
                if err == JErrCode.NOT_FOUND:
                    raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
                raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', 0)

    def seekable(self) -> bool: # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            return True

    def readable(self) -> bool: # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            return True

    def writable(self) -> bool: # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            return True

    def tell(self) -> int:
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'tell', [], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', 0)

    def truncate(self, size:Optional[int]=None):
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'truncate', [size], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', 0)

    def writelines(self, lines): # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'writelines', [lines], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

    def read(self, size:int=-1) -> bytes:
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'read', [size], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', b'')

    def readall(self) -> bytes: # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'readall', [], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', b'')

    def readinto(self, b) -> int: # pragma: no cover
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'readinto', [b], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', 0)

    def write(self, b) -> int:
        with self.lock:
            if self.closed:
                raise ValueError('I/O operation on closed file.')

            dump_and_send(self.sock, (self.file, 'write', [b], {}))
            resp = recv_and_load(self.sock)

        if not resp.get('ok'):
            cmd = resp.get("cmd", "")
            err = JErrCode(resp.get('err', 0))
            if err == JErrCode.NOT_FOUND:
                raise FileNotFoundError(f'Fail to call {cmd} -> {str(err)}')
            raise ValueError(f'Fail to call {cmd} -> {str(err)}')

        return resp.get('ret', 0)

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class JNetFiles(JFilesBase):
    """
    Network-based implementation of JFilesBase. 
    Routes local database requests to the remote `ThreadedTCPServer`.
    """
    __slots__ = ('server_addr', 'sock')

    def __init__(self, address:Tuple[str,int]=('127.0.0.1', 59898)):
        """
        JFiles client
        
        Args:
            address (Tuple[str, int], optional): JFiles server address+port (Default=('127.0.0.1',59898))
        """
        self.lock = RLock()
        self.server_addr = address
        self.sock = None
        try:
            sock = socket(AF_INET, SOCK_STREAM)
            sock.connect(address)
            self.sock = sock
        except Exception as e:
            raise RuntimeError from e

    def __del__(self):
        with self.lock:
            if self.sock and not self.sock._closed:
                self.sock.close()
                self.sock = None

    def __repr__(self) -> str:
        try:
            local_port = self.sock.getsockname()[-1]
        except:
            local_port = -1

        return f'<{type(self).__name__} {local_port} <-> s:{self.server_addr} at {hex(id(self))}>'

    def __eq__(self, obj:JNetFiles) -> bool:
        return isinstance(obj, JNetFiles) and self.server_addr == obj.server_addr

    def get_KEY(self) -> str:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_KEY', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_folder(self) -> str: # pragma: no cover
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_folder', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_name(self) -> str:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_name', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def get_path(self, folder:str='') -> str:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'get_path', [], {'folder':folder}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def copy(self) -> JNetFiles:
        if self.sock and not self.sock._closed:
            return JNetFiles(self.server_addr)

        raise IOError

    def is_group(self, KEY_file:str, name:str) -> bool:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'is_group', [], {'KEY_file':KEY_file, 'name':name}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', '')

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def create_group(self, name:str) -> JFilesBase:
        with self.lock:
            if self.sock and not self.sock._closed:
                raise RuntimeError

            raise IOError

    def KEY_open(self, mode:str='rb', buffering:int=-1, **kwargs) -> IO:
        with self.lock:
            if self.sock and not self.sock._closed:
                return JNetIO(self.sock, 'KEY', mode=mode, buffering=buffering, **kwargs)

            raise IOError

    def VAL_open(self, file_id:int=0, mode:str='rb', buffering:int=0, **kwargs) -> IO:
        with self.lock:
            if self.sock and not self.sock._closed:
                return JNetIO(self.sock, f'VAL.{file_id}', mode=mode, buffering=buffering, **kwargs)

            raise IOError

    def VAL_remove(self, file_id:int=0) -> bool:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'remove', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', False)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def VAL_exist(self, file_id:int=0) -> bool:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, (f'VAL.{file_id}', 'exist', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', False)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def KEY_size(self) -> int:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'size', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', 0)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def KEY_date(self) -> int:
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('KEY', 'date', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return resp.get('ret', 0)

                raise ValueError(f'Fail to call {resp.get("cmd", "")} {resp.get("err", 0)}')

            raise IOError

    def LCK_rlock(self):
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'rlock', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise BlockingIOError

    def LCK_wlock(self):
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'wlock', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise BlockingIOError

    def LCK_unlock(self):
        with self.lock:
            if self.sock and not self.sock._closed:
                dump_and_send(self.sock, ('LCK', 'unlock', [], {}))
                resp = recv_and_load(self.sock)

                if resp.get('ok'):
                    return

            raise BlockingIOError

    def LCK_close(self): # pragma: no cover
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
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address:str='127.0.0.1', RequestHandlerClass:Optional[BaseRequestHandler]=None, bind_and_activate:bool=True, files_obj:Optional[JFilesBase]=None, verbose:int=0, **kwargs):
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
    def handle(self):
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
                except:
                    pass

            if verbose >= 0:
                print(Style(f'[OUT|#{server.active_cnt}] client:{client} on {hex(thread_id)} [sock={sock}] files:{files_obj}', cyan=1, bright=1))

            server.active_cnt = max(server.active_cnt-1, 0)
            fp_table.clear()
            try:
                del files_obj
            except:
                pass

#---------------------------------------------------------------------
# Pylint=8.99
