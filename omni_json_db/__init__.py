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
__version__         = '2.10.01'

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
    Return:
        TCPServer

    Raises:
        TypeError: If the provided `files` parameter is invalid.    
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
