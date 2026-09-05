"""
omni-json-db: A Three-LESS (Schema-LESS + Server-LESS + SQL-LESS) High-Performance Database.

Provides rapid JSON and MsgPack serialization with robust concurrency controls
for many-read single-write multithreading/multiprocessing environments.
"""
from .utils import JError, JKeyError, JValueError, JTypeError, JAttributeError, \
                    JLockError, JKeyFlag, JFlag, MISSING, LOCKED, INT_manager
from .jdb_file import JDiskFiles, JMemFiles, JBytesIO
from .jdb_net import JNetFiles
from .jdb_lite import JDbReader, SEP_SYM
from .jdb import JDb, IMPORT_BATCH_ROWS
from .jdb_server import run_files_server
from .jdb_query import Query
from .jdb_notify import JEvent, JNotify, ALL_OPS as NOTIFY_OPS
from .jdb_graph import GraphDb
from .jdb_io import JIoVAL_U, JIoKEY_U, API_LATEST, \
                    register_user_key_codec, unregister_user_key_codec, \
                    register_user_val_codec, unregister_user_val_codec
from .jdb_codec import MIN_TTL_DAYS, MAX_TTL_DAYS, MAX_TTL_MINS, MIN_OF_DAY, conv_ttl

__package_name__    = 'omni_json_db'
__author__          = 'Lukatrum'
__email__           = 'lukatrum@gmail.com'
__description__     = 'A zero-config, powerful KV JSON database with compression/Time-travel/Concurrency. No schema, no setup, just data.'
__url__             = 'https://github.com/Lukatrum/omni-json-db'
__version__         = '3.00.14'

__all__ = (
    'GraphDb',
    'JDb',
    'JDbReader',
    'JError',
    'JKeyError',
    'JTypeError',
    'JValueError',
    'JAttributeError',
    'JLockError',
    'JKeyFlag',
    'JFlag',
    'JEvent',
    'JNotify',
    'NOTIFY_OPS',
    'JBytesIO',
    'JIoVAL_U',
    'JIoKEY_U',
    'JDiskFiles',
    'JMemFiles',
    'JNetFiles',
    'LOCKED',
    'MISSING',
    'Query',
    'SEP_SYM',
    'dumps',
    'loads',
    'run_files_server',
    'register_user_key_codec',
    'register_user_val_codec',
    'unregister_user_key_codec',
    'unregister_user_val_codec',
    'INT_manager',
    'API_LATEST',
    'MAX_TTL_MINS',
    'MAX_TTL_DAYS',
    'MIN_TTL_DAYS',
    'MIN_OF_DAY',
    'IMPORT_BATCH_ROWS',
    'conv_ttl',
)

loads = JDb.z_loads
dumps = JDb.z_dumps


#
