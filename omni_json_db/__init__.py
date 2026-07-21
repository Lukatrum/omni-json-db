"""
omni-json-db: A Three-LESS (Schema-LESS + Server-LESS + SQL-LESS) High-Performance Database.

Provides rapid JSON and MsgPack serialization with robust concurrency controls
for many-read single-write multithreading/multiprocessing environments.
"""
from .utils import JError, JKeyError, JValueError, JTypeError
from .jdb_file import JDiskFiles, JMemFiles, JBytesIO
from .jdb_net import JNetFiles
from .jdb_lite import JDbReader, SEP_SYM, JFlag
from .jdb import JDb
from .jdb_server import run_files_server
from .jdb_query import Query
from .jdb_graph import GraphDb

__package_name__    = 'omni_json_db'
__author__          = 'Lukatrum'
__email__           = 'lukatrum@gmail.com'
__description__     = 'A zero-config, powerful KV JSON database with compression/Time-travel/Concurrency. No schema, no setup, just data.'
__url__             = 'https://github.com/Lukatrum/omni-json-db'
__version__         = '2.14.15'

__all__ = (
    'GraphDb',
    'JDb',
    'JDbReader',
    'JError', 
    'JKeyError', 
    'JTypeError',
    'JValueError', 
    'JFlag',
    'JBytesIO',
    'JDiskFiles',
    'JMemFiles',
    'JNetFiles',
    'Query',
    'SEP_SYM',
    'dumps',
    'loads',
    'run_files_server',
)

loads = JDb.z_loads
dumps = JDb.z_dumps


#
