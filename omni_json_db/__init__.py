"""
omni-json-db: A Three-LESS (Schema-LESS + Server-LESS + SQL-LESS) High-Performance Database.

Provides rapid JSON and MsgPack serialization with robust concurrency controls
for many-read single-write multithreading/multiprocessing environments.
"""
from .jdb_file import JDiskFiles, JMemFiles
from .jdb_net import JNetFiles
from .jdb_lite import JDbReader, SEP_SYM, JFlag, run_files_server
from .jdb import JDb
from .utils import JError, JKeyError, JValueError, JTypeError

__package_name__    = 'omni_json_db'
__author__          = 'Lukatrum'
__email__           = 'lukatrum@gmail.com'
__description__     = 'A zero-config, powerful JSON database with compression. No schema, no setup, just data.'
__url__             = 'https://github.com/Lukatrum/omni-json-db'
__version__         = '2.12.37'

__all__ = [
    'JDb',
    'JDbReader',
    'JError', 
    'JKeyError', 
    'JTypeError',
    'JValueError', 
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

#
