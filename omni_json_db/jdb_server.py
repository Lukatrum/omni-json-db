# pylint: disable=too-many-lines
from __future__ import annotations
from socketserver import BaseRequestHandler, ThreadingMixIn, TCPServer
from threading import get_ident, Thread, RLock
from re import match as re_match
from typing import Optional, Union
#-----------------------------------------------------------------------------
from .utils import Style
from .jdb_file import JFilesBase, JMemFiles, JDiskFiles
from .jdb_net import JErrCode, dump_and_send, recv_and_load, JNetFiles
from .jdb_lite import JDbReader
from .jdb import JDb
#-----------------------------------------------------------------------------

def run_files_server(host:str='127.0.0.1', port:int=59898, files:Union[str,bytearray,JFilesBase,JDbReader,None]=None, verbose:int=0) -> TCPServer:
    """
    Initialize and start a multi-threaded TCP server to allow external access to the JDb object.
    
    Args:
        host (str, optional): The host address for the server to listen on. Defaults to '127.0.0.1'.
        port (int, optional): The port number for the server to listen on. Defaults to 59898.
        files (Union[str, bytearray, JFilesBase, JDbReader, None], optional):
            The specified source for the database file:
                - str: Uses JMemFiles() if empty; otherwise, parses as JDiskFiles(path).
                - bytearray: Uses JMemFiles(KEY_file).
                - JFilesBase: Various file objects (JDiskFiles, JMemFiles, JNetFiles).
                - JDbReader: An existing JDbReader object.
                - None: Defaults to JMemFiles().
        verbose (int, optional): Logging verbosity level (-1: Off, 0: Limited, 1: Error, 2: Warning, 3: Info, 4: Debug). Defaults to 0.
    
    Returns:
        TCPServer: The started TCP server instance.

    Raises:
        TypeError: Raised when the provided type for the files parameter is invalid.

    Examples:
        >>> server = run_files_server(host='127.0.0.1', port=8080)
        >>> server.shutdown()
    """
    if files is None or isinstance(files, bytearray):
        files_obj = JMemFiles(files)
    elif isinstance(files, JDbReader): # pragma: no cover
        files_obj = files.files_obj
    elif isinstance(files, JFilesBase): # pragma: no cover
        files_obj = files
    elif isinstance(files, str):
        if re_match(r'^([12]?\d\d?[:.]){4}(?<=:)\d{1,5}$', files): # pragma: no cover
            server_ip, server_port = files.split(':')
            server_port = int(server_port)
            if not 65535 >= server_port > 0 or not all(255 > int(vv) >= 0 for vv in server_ip.split('.')):
                raise TypeError

            files_obj = JNetFiles((server_ip, server_port))
        else:
            files_obj = JDiskFiles(files) if files else JMemFiles()
    else:
        raise TypeError

    if not isinstance(files_obj, JFilesBase):
        raise TypeError

    print(f'starting server at {host}:{port} -> {files_obj} (files={type(files)})')
    server = ThreadedTCPServer((host, port), ServerHandler, files_obj=files_obj, verbose=verbose)
    thd = Thread(target=server.serve_forever, daemon=True)
    thd.start()
    return server

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class ThreadedTCPServer(ThreadingMixIn, TCPServer):
    """Multi-threaded TCP server exposing a :class:`JFilesBase` backend to remote clients."""
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address:str='127.0.0.1', RequestHandlerClass:Optional[BaseRequestHandler]=None, bind_and_activate:bool=True, files_obj:Optional[JFilesBase]=None, verbose:int=0, **kwargs):
        """Initialize the TCP server.

        Args:
            server_address (Tuple[str, int]): The ``(host, port)`` to bind to. Defaults to ``'127.0.0.1'`` (no port).
            RequestHandlerClass (Optional[BaseRequestHandler], optional): Handler class used per connection. Defaults to :class:`ServerHandler`.
            bind_and_activate (bool, optional): If True, bind and activate the socket immediately. Defaults to True.
            files_obj (Optional[JFilesBase], optional): The backend to serve. Required.
            verbose (int, optional): Verbosity level for logging. Defaults to 0.
            **kwargs: Extra arguments passed through to :class:`socketserver.TCPServer`.

        Raises:
            TypeError: If ``files_obj`` is not a :class:`JFilesBase`.
        """
        super().__init__(server_address, ServerHandler if RequestHandlerClass is None else RequestHandlerClass, bind_and_activate, **kwargs)

        if not isinstance(files_obj, JFilesBase):
            raise TypeError('invalid files_obj type')

        self.jdb = JDb(files_obj)
        self.active_cnt = 0
        self.verbose = verbose
        # shared registry of group backends so every connection resolves the
        # same group instance (essential for JMemFiles-backed groups)
        self.group_files = {}
        self.group_lock = RLock()

    def get_group_files(self, group_path:str) -> JFilesBase:
        """Resolve (and lazily create) the shared backend for a nested group path.

        Args:
            group_path (str): Slash-separated group names, e.g. ``'grp_a/grp_b'``.
                An empty string resolves to the root database backend.

        Returns:
            JFilesBase: The shared backend files object serving that group.

        Raises:
            KeyError: If a group name violates the ``[0-9A-Za-z_]+`` constraint.
        """
        if not group_path:
            return self.jdb.files_obj

        with self.group_lock:
            files_obj = self.group_files.get(group_path, None)
            if files_obj is None:
                files_obj = self.jdb.files_obj
                _path = ''
                for part in group_path.split('/'):
                    if not re_match(r'^[0-9A-Za-z_]+$', part):
                        raise KeyError(part)

                    _path = f'{_path}/{part}' if _path else part
                    _obj = self.group_files.get(_path, None)
                    if _obj is None:
                        self.group_files[_path] = _obj = files_obj.create_group(part)

                    files_obj = _obj

            return files_obj

#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
#---------------------------------------------------------------------
class ServerHandler(BaseRequestHandler):
    """Per-connection request handler that dispatches client commands to a :class:`JFilesBase` backend."""

    def handle(self):
        """Handle one client connection: read commands, dispatch them, and send responses until disconnect."""
        thread_id = get_ident()
        client = f'{self.client_address}'
        sock = self.request
        server = self.server
        server.active_cnt += 1
        verbose = server.verbose
        files_obj = server.jdb.files_obj.copy() # need to copy()
        if verbose >= 0:
            print(Style(f'[IN|#{server.active_cnt}] client:{client} on {hex(thread_id)} [sock={sock}] files:{files_obj}', green=1, bright=1))

        fp_table = {}
        group_table = {'': files_obj}    # connection-local backends, keyed by group path
        locker_table = {}                # pending lock counts, keyed by group path
        try:
            while True:
                try:
                    packet = recv_and_load(sock)
                    if not packet: # pragma: no cover
                        continue

                except (EOFError, ConnectionResetError):
                    break

                except ValueError as e: # pragma: no cover
                    if verbose >= 0:
                        print(Style(f'[ERROR|{client}|{hex(thread_id)}|{files_obj}] exception:{e}', yellow=1, bright=1))
                    continue

                except Exception as e: # pragma: no cover
                    if verbose >= 0:
                        print(Style(f'[ERROR|{client}|{hex(thread_id)}|{files_obj}] exception:{e}', red=1, bright=1))
                    raise

                try:
                    file, cmd, _args, _kwargs = packet

                except ValueError: # pragma: no cover
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]Invalid format: {packet}', yellow=1))

                    dump_and_send(sock, {'ok':False, 'cmd':'', 'ret':None, 'err':JErrCode.INVALID_FMT})
                    continue

                base_file, _, group_path = file.partition('@')
                if not base_file.startswith(('VAL.', 'KEY', 'LCK')): # pragma: no cover
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]Invalid file: {packet}', yellow=1))
                    dump_and_send(sock, {'ok':False, 'cmd':f'{file}', 'ret':None, 'err':JErrCode.INVALID_ID})
                    continue

                grp_files_obj = group_table.get(group_path, None)
                if grp_files_obj is None:
                    try:
                        # copy() the shared backend so file pointers and lock
                        # state stay private to this connection
                        group_table[group_path] = grp_files_obj = server.get_group_files(group_path).copy()

                    except (KeyError, TypeError, ValueError, RuntimeError, IOError) as e: # pragma: no cover
                        if verbose >= 1:
                            print(Style(f'[FAIL|{client}]Invalid group: {packet} err:{e}', yellow=1))
                        dump_and_send(sock, {'ok':False, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.INVALID_ID})
                        continue

                file_id = 0
                if base_file.startswith('VAL.'):
                    try:
                        _val_file, file_id = base_file.split('.')
                        file_id = int(file_id)

                    except ValueError: # pragma: no cover
                        dump_and_send(sock, {'ok':False, 'cmd':f'{file}', 'ret':None, 'err':JErrCode.INVALID_ID})
                        continue

                if not cmd or not isinstance(cmd, str): # pragma: no cover
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]{file}:Invalid command: {packet}', yellow=1))
                    dump_and_send(sock, {'ok':False, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.INVALID_CMD})
                    continue

                if not isinstance(_kwargs, dict): # pragma: no cover
                    if verbose >= 1:
                        print(Style(f'[FAIL|{client}]{file}:Invalid arg type: {packet}', yellow=1))
                    dump_and_send(sock, {'ok':False, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.INVALID_ARGS})
                    continue

                is_done = True
                fp = fp_table.get(file, None)
                resp = {'ok':True, 'cmd':f'{file}:{cmd}', 'ret':None, 'err':JErrCode.OKAY}
                if base_file == 'LCK':
                    if cmd == 'remove':  # pragma: no cover
                        try:
                            resp['ret'] = grp_files_obj.LCK_remove()
                            locker_table[group_path] = 0
                        except (RuntimeError, IOError, FileNotFoundError):
                            resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'rlock':
                        try:
                            resp['ret'] = grp_files_obj.LCK_rlock(*_args, **_kwargs)
                            locker_table[group_path] = locker_table.get(group_path, 0) + 1
                        except BlockingIOError: # pragma: no cover
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)
                        except (RuntimeError, IOError, FileNotFoundError): # pragma: no cover
                            resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'wlock':
                        try:
                            resp['ret'] = grp_files_obj.LCK_wlock(*_args, **_kwargs)
                            locker_table[group_path] = locker_table.get(group_path, 0) + 1
                        except BlockingIOError: # pragma: no cover
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)
                        except (RuntimeError, IOError, FileNotFoundError): # pragma: no cover
                            resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'unlock':
                        try:
                            resp['ret'] = grp_files_obj.LCK_unlock()
                            locker_table[group_path] = locker_table.get(group_path, 0) - 1
                        except BlockingIOError: # pragma: no cover
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)
                        except (RuntimeError, IOError): # pragma: no cover
                            resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'close':
                        try:
                            resp['ret'] = grp_files_obj.LCK_close()
                        except BlockingIOError: # pragma: no cover
                            resp.update(ok=False, err=JErrCode.BLOCK_IO)
                        except (RuntimeError, IOError, FileNotFoundError): # pragma: no cover
                            resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    else: # pragma: no cover
                        if verbose >= 1:
                            print(Style(f'[FAIL|{client}]{file}: cannot find command: {packet}', yellow=1))
                        resp.update(ok=False, err=JErrCode.INVALID_CMD)

                elif base_file == 'KEY':
                    if cmd == 'open':
                        if fp is not None: # pragma: no cover
                            if verbose >= 0:
                                print(Style(f'[WARN|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs}) reopen() fp={fp}', yellow=1))
                            fp.flush()
                            fp.seek(0)
                        else:
                            try:
                                fp_table[file] = fp = resp['ret'] = grp_files_obj.KEY_open(*_args, **_kwargs)
                                if fp is None: # pragma: no cover
                                    if verbose >= 1:
                                        print(Style(f'[FAIL|{client}]{file}:{cmd}({_args},{_kwargs})', yellow=1))

                                    resp.update(ok=False, err=JErrCode.FAIL_OPEN)

                            except FileNotFoundError:
                                if verbose >= 1:
                                    print(Style(f'[FAIL|{client}]{file}:{cmd}({_args},{_kwargs}) File not found', yellow=1))
                                resp.update(ok=False, err=JErrCode.NOT_FOUND)

                    elif cmd == 'get_folder':
                        # self.dir_name
                        resp['ret'] = grp_files_obj.get_folder()

                    elif cmd == 'get_name':
                        # self.file_name
                        resp['ret'] = grp_files_obj.get_name()

                    elif cmd == 'get_KEY':
                        # self.file_name
                        resp['ret'] = grp_files_obj.get_KEY()

                    elif cmd == 'get_path':
                        resp['ret'] = grp_files_obj.get_path(*_args, **_kwargs)

                    elif cmd == 'is_group':
                        resp['ret'] = grp_files_obj.is_group(*_args, **_kwargs)

                    elif cmd == 'create_group': # pragma: no cover
                        resp['ret'] = grp_files_obj.create_group(*_args, **_kwargs).get_KEY()

                    elif cmd == 'size':
                        resp['ret'] = grp_files_obj.KEY_size()

                    elif cmd == 'date':
                        resp['ret'] = grp_files_obj.KEY_date()

                    elif cmd == 'fsync':
                        resp['ret'] = grp_files_obj.fsync(*_args, **_kwargs)

                    else:
                        is_done = False

                else: # file == 'VAL'
                    if cmd == 'open':
                        if fp is not None: # pragma: no cover
                            if verbose >= 0:
                                print(Style(f'[WARN|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs}) reopen() fp={fp}', yellow=1))
                            fp.flush()
                            fp.seek(0)
                        else:
                            try:
                                fp_table[file] = fp = resp['ret'] = grp_files_obj.VAL_open(file_id, *_args, **_kwargs)
                                if fp is None: # pragma: no cover
                                    if verbose >= 1:
                                        print(Style(f'[FAIL|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs})', yellow=1))
                                    resp.update(ok=False, err=JErrCode.FAIL_OPEN)

                            except FileNotFoundError:
                                if verbose >= 1:
                                    print(Style(f'[FAIL|{client}]{file}:{cmd}(file_id={file_id},{_args},{_kwargs}) File not found', yellow=1))
                                resp.update(ok=False, err=int(JErrCode.NOT_FOUND))

                    elif cmd == 'remove':
                        resp['ret'] = grp_files_obj.VAL_remove(file_id)

                    elif cmd == 'exist':
                        resp['ret'] = grp_files_obj.VAL_exist(file_id)

                    elif cmd == 'size':
                        resp['ret'] = grp_files_obj.VAL_size(file_id)

                    else:
                        is_done = False

                if not is_done:

                    if cmd == 'closed': # pragma: no cover
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

                            elif cmd == 'readall': # pragma: no cover
                                resp['ret'] = fp.readall(*_args, **_kwargs)

                            elif cmd == 'readinto': # pragma: no cover
                                resp['ret'] = fp.readinto(*_args, **_kwargs)

                            elif cmd == 'readline': # pragma: no cover
                                resp['ret'] = fp.readline(*_args, **_kwargs)

                            elif cmd == 'readlines': # pragma: no cover
                                resp['ret'] = fp.readlines(*_args, **_kwargs)

                            elif cmd == 'writelines': # pragma: no cover
                                resp['ret'] = fp.writelines(*_args, **_kwargs)

                            elif cmd == 'fileno':
                                resp['ret'] = fp.fileno()

                            else: # pragma: no cover
                                if verbose >= 1:
                                    print(Style(f'[FAIL|{client}]{file}:cannot find command: {packet}', yellow=1))
                                resp.update(ok=False, err=JErrCode.INVALID_CMD)

                        except Exception as e: # pragma: no cover
                            if verbose >= 1:
                                print(Style(f'[FAIL|{client}]{file}:{cmd}(fp={fp}, {_args}, {_kwargs}) err:{e}', yellow=1))
                            resp.update(ok=False, err=JErrCode.FAIL_CALL)

                if resp['ok']:
                    ret = resp['ret']
                    if ret is None or isinstance(ret, (int,bool,float,str)):
                        ret_s = str(ret)
                    elif isinstance(ret, (list,tuple,str,bytes,bytearray)):
                        ret_s = f"{ret[:64]}+{len(ret):,}"
                    elif isinstance(ret, (dict,set)): # pragma: no cover
                        ret_s = f"{type(ret)}+{len(ret):,}"
                    else:
                        resp['ret'] = ret_s = str(type(ret))

                    if verbose >= 2:
                        print(Style(f'[OKAY|{client}]{file}:{cmd}(fp={fp}, {_args}, {_kwargs}) -> {ret_s}', blue=1))

                dump_and_send(sock, resp)

            # if verbose >= 0:
            #     print(Style(f'[OUT|#{server.active_cnt}] client:{client} on {hex(thread_id)} [sock={sock}] files:{files_obj}', cyan=1, bright=1))

        finally:
            for _group_path,n_lockers in locker_table.items(): # pragma: no cover
                _files_obj = group_table.get(_group_path, None)
                if _files_obj is None: continue
                while n_lockers > 0:
                    n_lockers -= 1
                    try:
                        _files_obj.LCK_unlock()
                    except (BlockingIOError, RuntimeError, IOError): # pragma: no cover
                        break

            for _file_name,fp in fp_table.items(): # pragma: no cover
                if fp is None: continue
                fp.close()

            server.active_cnt = max(server.active_cnt-1, 0)
            fp_table.clear()
            del files_obj

#---------------------------------------------------------------------
#
