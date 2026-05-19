"""
omni-json-db: A Three-LESS (Schema-LESS + Server-LESS + SQL-LESS) High-Performance Database.

Provides rapid JSON and MsgPack serialization with robust concurrency controls
for many-read single-write multithreading/multiprocessing environments.
"""
from threading import Thread
from socketserver import TCPServer
from typing import Union
from re import match as re_match
from .jdb import JDb
from .jdb_lite import JDbReader, SEP_SYM, JFlag
from .jdb_file import JFilesBase, JDiskFiles, JMemFiles
from .jdb_net import JNetFiles, ThreadedTCPServer, ServerHandler
# from .jdb_io import JIo, LiteKeyTable, BTreeKeyTable

__package_name__    = 'omni_json_db'
__author__          = 'Lukatrum'
__email__           = 'lukatrum@gmail.com'
__description__     = 'A zero-config, powerful JSON database with compression. No schema, no setup, just data.'
__url__             = 'https://github.com/Lukatrum/omni-json-db'
__version__         = '2.11.33'

__all__ = [
    'JDb',
    'JDbReader',
    'JFlag',
    'JDiskFiles',
    'JMemFiles',
    'JNetFiles',
    'SEP_SYM',
    'dumps',
    'loads',
    'run_files_server',
]

loads = JDb.z_loads
dumps = JDb.z_dumps

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
    
    Returns
        TCPServer: The started TCP server instance.

    Raises:
        TypeError: Raised when the provided type for the files parameter is invalid.

    Examples
        >>> server = run_files_server(host='127.0.0.1', port=8080)
        >>> server.serve_forever()
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

    print(f'staring server at {host}:{port} -> {files_obj} (files={type(files)})')
    server = ThreadedTCPServer((host, port), ServerHandler, files_obj=files_obj, verbose=verbose)
    thd = Thread(target=server.serve_forever, daemon=True)
    thd.start()
    return server
#
