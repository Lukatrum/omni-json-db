"""
omni-json-db: A Three-LESS (Schema-LESS + Server-LESS + SQL-LESS) High-Performance Database.

Provides rapid JSON and MsgPack serialization with robust concurrency controls
for many-read single-write multithreading/multiprocessing environments.
"""
from .jdb import JDb
from .jdb_lite import JDbReader, SEP_SYM, JFlag
from .jdb_file import JDiskFiles, JMemFiles
from .jdb_net import JNetFiles, run_files_server

__package_name__    = 'omni_json_db'
__author__          = 'Lukatrum'
__email__           = 'lukatrum@gmail.com'
__description__     = 'A zero-config, serverless JSON-based KV database. No schema, no setup, just data.'
__url__             = 'https://github.com/Lukatrum/omni-json-db'
__version__         = '2.07.00'

loads = JDb.z_loads
dumps = JDb.z_dumps

__all__ = [
    'JDb',
    'JDbReader',
    'JFlag',
    'JDiskFiles',
    'JMemFiles',
    'JNetFiles',
    'loads',
    'dumps',
    'run_files_server',
]
