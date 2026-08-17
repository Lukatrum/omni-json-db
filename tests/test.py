# pylint: disable=too-many-lines, multiple-imports, W0640, cell-var-from-loop, import-outside-toplevel
import unittest, time, random, threading, inspect, re, os, io
from marshal import loads as marshal_loads, dumps as marshal_dumps
import datetime as dt
import sqlite3
import networkx as nx
from omni_json_db import JDb, JDbReader, JMemFiles, JFlag, JKeyFlag, \
                    JNetFiles, JDiskFiles, run_files_server, LOCKED, \
                    GraphDb, loads, dumps, Query, JIoVAL_U, \
                    register_user_val_codec, register_user_key_codec, \
                    unregister_user_val_codec, unregister_user_key_codec, \
                    MAX_TTL_DAYS

try:
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < 2048 <= hard:
        resource.setrlimit(resource.RLIMIT_NOFILE, (2048, hard))
except (ImportError, ValueError, OSError): # pragma: no cover
    pass

_g_basetime = time.perf_counter()
def Style(msg, bold=None, dim=None, smso=None, underscore=None, blink=None, reverse=None, hidden=None, bright=None, fg=None, black=None, red=None, green=None, yellow=None, blue=None, magenta=None, cyan=None, white=None, bg=None, bg_black=None, bg_red=None, bg_green=None, bg_yellow=None, bg_blue=None, bg_magenta=None, bg_cyan=None, bg_white=None):
    if not '_g_basetime'  in globals():
        globals()['_g_basetime'] = time.perf_counter()

    code = ''
    now = dt.datetime.now().strftime(format="%H%M%S")
    tt = time.perf_counter() - _g_basetime
    fm = inspect.currentframe().f_back
    for ii,vv in enumerate([bold, dim, smso, underscore, blink, reverse, hidden]):
        if not vv:
            continue

        code += f'\033[{ii+1}m'

    if fg is None:
        for ii,vv in enumerate([black, red, green, yellow, blue, magenta, cyan, white]):
            if not vv:
                continue

            v1 = 9 if bool(bright) else 3
            code += f'\033[{v1}{ii}m'
            break
    else:
        if isinstance(fg, int):
            vv = max(min(fg, 7), 0)
        elif isinstance(fg, str):
            vv = 1 * ('r' in fg) + 2 * ('g' in fg) + 4 * ('b' in fg)
        else:
            vv = 1 * fg[0] + 2 * fg[1] + 4 * fg[2]
        v1 = 9 if bool(bright) else 3
        code += f'\033[{v1}{vv}m'


    if bg is None:
        for ii,vv in enumerate([bg_black, bg_red, bg_green, bg_yellow, bg_blue, bg_magenta, bg_cyan, bg_white]):
            if not vv:
                continue

            code += f'\033[4{ii}m'
            break
    else:
        if isinstance(bg, int):
            vv = max(min(bg, 7), 0)
        elif isinstance(bg, str):
            vv = 1 * ('r' in bg) + 2 * ('g' in bg) + 4 * ('b' in bg)
        else:
            vv = 1 * bg[0] + 2 * bg[1] + 4 * bg[2]

        code += f'\033[4{vv}m'

    msg = f'{tt:08.3f}|{now}|{fm.f_code.co_name}:{fm.f_lineno}|{msg}'
    if not code:
        return msg

    return f'{code}{msg}\033[0m'

def create_sample_db(db_path:str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY, 
        name text NOT NULL, 
        begin_date DATE, 
        end_date DATE
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS project_logs (
        project_id INTEGER,
        action TEXT NOT NULL,
        log_date DATE
    )
    ''')

    cursor.execute('DELETE FROM projects')
    cursor.execute('DELETE FROM project_logs')

    projects_data = [
        (1, 'cooking', '2000-01-02', '2003-01-13'),
        (2, 'reading', '2023-05-01', '2023-12-31'),
        (3, 'coding', '2024-01-01', '2024-06-30')
    ]
    cursor.executemany('INSERT INTO projects (id, name, begin_date, end_date) VALUES (?, ?, ?, ?)', projects_data)

    logs_data = [
        (1, 'bought ingredients', '2000-01-01'),
        (1, 'started cooking', '2000-01-02'),
        (2, 'bought books', '2023-04-20'),
        (3, 'setup environment', '2024-01-01')
    ]
    cursor.executemany('INSERT INTO project_logs (project_id, action, log_date) VALUES (?, ?, ?)', logs_data)

    conn.commit()
    conn.close()

def xor_dumps(data):
    return bytes(b ^ 0x5A for b in marshal_dumps(data))

def xor_loads(data):
    return marshal_loads(bytes(b ^ 0x5A for b in data))

class TestJDb(unittest.TestCase):
    def setUp(self):
        unregister_user_val_codec()
        register_user_val_codec(xor_dumps, xor_loads)

        unregister_user_key_codec()
        register_user_key_codec(xor_dumps, xor_loads)

        self.server0 = run_files_server('127.0.0.1', 59897, files=None, verbose=0)
        self.server1 = run_files_server('127.0.0.1', 59898, files='db/test_3n.jdb', verbose=0)
        self.server2 = run_files_server('127.0.0.1', 59899, files=None, verbose=0)

        self.server0.jdb.clear(agree='yes', wait_sec=0)
        self.server1.jdb.clear(agree='yes', wait_sec=0)
        self.server2.jdb.clear(agree='yes', wait_sec=0)

        self.jdb_configs = [
            {'KEY_file':'net_59898_3',      'api_ver':2, 'data_type':'J+J', 'zip_type':'--', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 16, 'min_value_size': 8, 'index_size':64, 'key_limit':'l4'},
            {'KEY_file':'net_59899_6',      'api_ver':2, 'data_type':'S+S', 'zip_type':'--', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 16, 'min_value_size': 8, 'index_size':64, 'key_limit':'--'},

            {'KEY_file':'mem_3gz',          'api_ver':2, 'data_type':'J+J', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':64, 'key_limit':'--'},
            {'KEY_file':'mem_6bz',          'api_ver':2, 'data_type':'S+S', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':64, 'key_limit':'--'},
            {'KEY_file':'mem_11lz',         'api_ver':2, 'data_type':'J+Y', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit': 0, 'min_value_size': 16, 'index_size':64, 'key_limit':'--'},

            {'KEY_file':'mem_3br_v1',       'api_ver':1, 'data_type':'J+J', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit':  0, 'min_value_size': 8,  'index_size':64, 'key_limit':'--'},
            {'KEY_file':'mem_6z1_v1',       'api_ver':1, 'data_type':'S+S', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': -1, 'min_value_size': 8,  'index_size':64, 'key_limit':'--'},
            {'KEY_file':'mem_12_v1',        'api_ver':1, 'data_type':'S+Y', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit': -1, 'min_value_size': 8,  'index_size':64, 'key_limit':'--'},

            {'KEY_file':'mem_7gz_v0',       'api_ver':0, 'data_type':'J+S', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit':  0, 'min_value_size': 8, 'index_size':64, 'key_limit':'--'},
            {'KEY_file':'mem_9z2_v0',       'api_ver':0, 'data_type':'S+J', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': -1, 'min_value_size': 8, 'index_size':64, 'key_limit':'bt'},

            {'KEY_file':'db/test_1lz_v1.jdb',   'api_ver':1, 'data_type':'L+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'<32'},
            {'KEY_file':'db/test_2br_v1.jdb',   'api_ver':1, 'data_type':'M+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'l3'},
            {'KEY_file':'db/test_10z1_v1.jdb',  'api_ver':1, 'data_type':'S+P', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'bt'},
            {'KEY_file':'db/test_11lz_v1.jdb',  'api_ver':1, 'data_type':'J+Y', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'no'},
            {'KEY_file':'db/test_15_v1.jdb',    'api_ver':1, 'data_type':'U+U', 'zip_type':'--', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'no'},

            {'KEY_file':'db/test_1lz_v0.jdb',   'api_ver':0, 'data_type':'L+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'<64'},
            {'KEY_file':'db/test_2br_v0.jdb',   'api_ver':0, 'data_type':'M+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'l2'},
            {'KEY_file':'db/test_5z1_v0.jdb',   'api_ver':0, 'data_type':'J+P', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'bt'},
            {'KEY_file':'db/test_12lz_v0.jdb',  'api_ver':0, 'data_type':'S+Y', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'no'},
            {'KEY_file':'db/test_15_v0.jdb',    'api_ver':0, 'data_type':'U+U', 'zip_type':'--', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'no'},

            {'KEY_file':'db/test_1.jdb',    'api_ver':2, 'data_type':'L+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_1gz.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1bz.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1xz.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1zs.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1br.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1z1.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1z2.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1lz.jdb',  'api_ver':2, 'data_type':'L+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x1.jdb',   'api_ver':2, 'data_type':'L+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l0'},
            {'KEY_file':'db/test_x1gz.jdb', 'api_ver':2, 'data_type':'L+J', 'zip_type':'gz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':0},

            {'KEY_file':'db/test_2.jdb',    'api_ver':2, 'data_type':'M+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2gz.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2bz.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2xz.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2zs.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2br.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2z1.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2z2.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2lz.jdb',  'api_ver':2, 'data_type':'M+M', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x2.jdb',   'api_ver':2, 'data_type':'M+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l1'},
            {'KEY_file':'db/test_x2bz.jdb', 'api_ver':2, 'data_type':'M+M', 'zip_type':'bz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':0},

            {'KEY_file':'db/test_3.jdb',    'api_ver':2, 'data_type':'J+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3gz.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3bz.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3xz.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3zs.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3br.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3z1.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3z2.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_3lz.jdb',  'api_ver':2, 'data_type':'J+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x3.jdb',   'api_ver':2, 'data_type':'J+J', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l2'},
            {'KEY_file':'db/test_x3xz.jdb', 'api_ver':2, 'data_type':'J+J', 'zip_type':'xz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

                # {'KEY_file':'db/test_4.jdb',    'api_ver':2, 'data_type':'J+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4gz.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4bz.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4xz.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4zs.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4br.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4z1.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4z2.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4lz.jdb',  'api_ver':2, 'data_type':'J+M', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x4.jdb',   'api_ver':2, 'data_type':'J+M', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l3'},
            {'KEY_file':'db/test_x4zs.jdb', 'api_ver':2, 'data_type':'J+M', 'zip_type':'zs', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

                # {'KEY_file':'db/test_5.jdb',    'api_ver':2, 'data_type':'J+P', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5gz.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5bz.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5xz.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5zs.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5br.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5z1.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5z2.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5lz.jdb',  'api_ver':2, 'data_type':'J+P', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x5.jdb',   'api_ver':2, 'data_type':'J+P', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l4'},
            {'KEY_file':'db/test_x5br.jdb', 'api_ver':2, 'data_type':'J+P', 'zip_type':'br', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

            {'KEY_file':'db/test_6.jdb',    'api_ver':2, 'data_type':'S+S', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6gz.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6bz.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6xz.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6zs.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6br.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6z1.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6z2.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_6lz.jdb',  'api_ver':2, 'data_type':'S+S', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x6.jdb',   'api_ver':2, 'data_type':'S+S', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l4'},
            {'KEY_file':'db/test_x6z1.jdb', 'api_ver':2, 'data_type':'S+S', 'zip_type':'z1', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

                # {'KEY_file':'db/test_7.jdb',    'api_ver':2, 'data_type':'J+S', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7gz.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7bz.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7xz.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7zs.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7br.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7z1.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
                # {'KEY_file':'db/test_7z2.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
                # {'KEY_file':'db/test_7lz.jdb',  'api_ver':2, 'data_type':'J+S', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x7.jdb',   'api_ver':2, 'data_type':'J+S', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'<16'},
            {'KEY_file':'db/test_x7z2.jdb', 'api_ver':2, 'data_type':'J+S', 'zip_type':'z2', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'--'},

                # {'KEY_file':'db/test_8.jdb',    'api_ver':2, 'data_type':'S+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x8gz.jdb', 'api_ver':2, 'data_type':'S+M', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'l4'},

                # {'KEY_file':'db/test_9.jdb',    'api_ver':2, 'data_type':'S+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x9z1.jdb', 'api_ver':2, 'data_type':'S+J', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'<8'},

                # {'KEY_file':'db/test_10.jdb',    'api_ver':2, 'data_type':'S+P', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x10br.jdb', 'api_ver':2, 'data_type':'S+P', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'bt'},

                # {'KEY_file':'db/test_11.jdb',   'api_ver':2, 'data_type':'J+Y', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
                # {'KEY_file':'db/test_x11.jdb',  'api_ver':2, 'data_type':'J+Y', 'zip_type':'no', 'max_file_size' :  64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'--'},

                # {'KEY_file':'db/test_12.jdb',    'api_ver':2, 'data_type':'S+Y', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
                # {'KEY_file':'db/test_x12lz.jdb', 'api_ver':2, 'data_type':'S+Y', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'--'},

                # {'KEY_file':'db/test_13.jdb',    'api_ver':2, 'data_type':'J+U', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x13gz.jdb',  'api_ver':2, 'data_type':'J+U', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'--'},

                # {'KEY_file':'db/test_14.jdb',    'api_ver':2, 'data_type':'S+U', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x14z1.jdb',  'api_ver':2, 'data_type':'S+U', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'l2'},

                # {'KEY_file':'db/test_15.jdb',    'api_ver':2, 'data_type':'U+U', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x15lz.jdb',  'api_ver':2, 'data_type':'U+U', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate': 0.2, 'cache_limit':0, 'min_value_size':128, 'index_size':64, 'key_limit':'<32'},
        ]

        self.jdbs = {}
        for config in self.jdb_configs:
            filename = config['KEY_file']
            if filename.endswith('.jdb'):
                _config = config
            else:
                _config = config.copy()
                if filename.startswith('net_'):
                    port = int(filename.split('_')[1])
                    try:
                        _config['KEY_file'] = JNetFiles(('localhost', port))
                    except RuntimeError:
                        _config['KEY_file'] = None
                else:
                    _config['KEY_file'] = None

            jdb = JDb(**_config)
            self.jdbs[filename] = jdb
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb.key_table), 0)
            self.assertEqual(len(jdb.file_table), 0)
            self.assertEqual(len(jdb.io.groups), 0)
            print(jdb, jdb.files_obj, jdb.io, jdb.key_table)
            print(Style(f'Up {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{jdb.cache_limit}', cyan=1))

            self.assertTrue(jdb.files_obj.get_name() != '')
            self.assertEqual(len(jdb), 0)
            self.assertEqual(len(jdb.key_table), 0)
            self.assertEqual(len(jdb.file_table), 0)
            self.assertTrue(jdb.can_lock())
            self.assertFalse('key' in jdb)
            self.assertFalse(jdb.has('key'))
            cnt = 0
            for _ in jdb:
                cnt += 1

            self.assertEqual(cnt, 0)
            key_table, file_table = jdb.load_table(force=True)
            self.assertEqual(len(key_table), 0)
            self.assertEqual(len(file_table), 0)
            jdb.sync()

    def tearDown(self):
        try:
            for config in self.jdb_configs:
                filename = config['KEY_file']
                jdb = self.jdbs[filename]
                self.assertIsNotNone(jdb)
                jdb.clear(agree='yes', wait_sec=0, **config)
                print(Style(f'Down {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}%', blue=1))

        finally:
            for server in (self.server1, self.server2, self.server0):
                if not server: continue
                server.jdb.clear(agree='yes', wait_sec=0)
                server.shutdown()
                server.server_close()

    def test_key_flag(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            # letter table: every flag owns a unique letter and round-trips
            self.assertEqual(JKeyFlag('r'), JKeyFlag.READ_ONLY)
            self.assertEqual(JKeyFlag('g'), JKeyFlag.GROUP)
            self.assertEqual(JKeyFlag('a'), JKeyFlag.APPEND_ONLY)
            self.assertEqual(JKeyFlag('c'), JKeyFlag.NO_CACHE)
            self.assertEqual(JKeyFlag('v'), JKeyFlag.NO_REVERT)
            self.assertEqual(JKeyFlag('l'), JKeyFlag.LINK)
            self.assertEqual(JKeyFlag('p'), JKeyFlag.NO_DELETE)
            self.assertEqual(JKeyFlag('m'), JKeyFlag.MUST_EXIST)
            self.assertEqual(JKeyFlag('n'), JKeyFlag.NO_FOLLOW)
            self.assertEqual(JKeyFlag('w'), JKeyFlag.EXCL)
            self.assertEqual(JKeyFlag('y'), JKeyFlag.NO_ATIME)
            self.assertEqual(JKeyFlag('ac'), JKeyFlag.APPEND_ONLY | JKeyFlag.NO_CACHE)
            self.assertEqual(JKeyFlag('RV'), JKeyFlag.READ_ONLY | JKeyFlag.NO_REVERT)
            self.assertEqual(JKeyFlag('?'), JKeyFlag(0))  # unknown letters ignored
            self.assertEqual(set(str(JKeyFlag('rv'))), {'r', 'v', '_'})
            self.assertEqual(set(str(JKeyFlag('gl'))), {'g', 'l', '_'})
            self.assertEqual(set(str(JKeyFlag(0))), {'_'})
            # NO_CACHE/NO_REVERT share an initial: __str__ must not collide
            self.assertEqual(len({str(f) for f in JKeyFlag}), len(list(JKeyFlag)))
            self.assertEqual(len({JKeyFlag(str(f).replace('_', '')) for f in JKeyFlag}), len(list(JKeyFlag)))

            test_size = 8
            expect = {f'key{v}': list(range(v*2+1)) for v in range(test_size)}
            self.assertEqual(jdb.insert(expect), expect)
            self.assertEqual(jdb, expect)

            # ---------------- READ_ONLY ----------------
            ro_key = 'key3'
            ro_val = jdb[ro_key]
            self.assertEqual(jdb.set_key_flags(ro_key, read_only=True), {ro_key: (int(JKeyFlag.READ_ONLY), 0)})
            self.assertEqual(jdb.get_key_flags(ro_key), {ro_key: (int(JKeyFlag.READ_ONLY),0)})

            jdb[ro_key] = 'blocked'                   # refused silently
            self.assertEqual(jdb[ro_key], ro_val)
            del jdb[ro_key]                           # refused silently
            self.assertTrue(ro_key in jdb)
            self.assertEqual(jdb.remove(ro_key), {})  # a locked row is never reported as deleted
            self.assertTrue(ro_key in jdb)
            self.assertEqual(jdb.pop(ro_key, -1), ro_val)
            self.assertTrue(ro_key in jdb)
            self.assertEqual(jdb.unmodify(ro_key), {})
            self.assertEqual(jdb[ro_key], ro_val)
            self.assertEqual(jdb, expect)

            # set_flags is privileged: it is the only way back out
            self.assertEqual(jdb.keys.set_flags(ro_key, read_only=False), {ro_key: (0,0)})
            jdb[ro_key] = 'writable again'
            self.assertEqual(jdb[ro_key], 'writable again')
            jdb.unmodify(ro_key)
            self.assertEqual(jdb, expect)

            # ---------------- GROUP ----------------
            sub_expect = {'g1': 1, 'g2': [2, 3]}
            grp = jdb.add_group('grp')
            self.assertTrue(isinstance(grp, JDb))
            grp.insert(sub_expect)
            self.assertEqual(grp, sub_expect)
            self.assertEqual(jdb.keys.get_flags('grp'), {'grp': (int(JKeyFlag.GROUP),0)})

            # the derived GROUP bit must survive any flag rewrite, or the group
            # becomes unreadable
            self.assertEqual(jdb.keys.set_flags('grp', no_cache=True), {'grp': (int(JKeyFlag.GROUP | JKeyFlag.NO_CACHE),0)})
            self.assertEqual(jdb['grp'], sub_expect)
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write_key_flags(fp, 'grp', JKeyFlag.READ_ONLY))

            self.assertEqual(JKeyFlag(jdb.keys['grp'][9]), JKeyFlag.READ_ONLY | JKeyFlag.GROUP)
            self.assertEqual(jdb['grp'], sub_expect)
            self.assertEqual(jdb.keys.set_flags('grp', read_only=False), {'grp': (int(JKeyFlag.GROUP),0)})

            # ... and it is never accepted from a caller either
            val = jdb.set('plain', 10, key_flags='+gc')
            self.assertEqual(val, 10)
            self.assertEqual(jdb.keys.get_flags('plain'), {'plain': (int(JKeyFlag.NO_CACHE),0)})
            self.assertEqual(jdb['plain'], 10)

            # a group-scoped selector is routed to the child index
            self.assertEqual(jdb.keys.set_flags('grp:::g1', read_only=True), {'grp:::g1': (int(JKeyFlag.READ_ONLY),0)})
            self.assertEqual(grp.keys.get_flags('g1'), {'g1': (int(JKeyFlag.READ_ONLY),0)})

            grp['g1'] = 'blocked'
            self.assertEqual(grp, sub_expect)
            self.assertEqual(jdb.keys.set_flags('grp:::g1', read_only=False), {'grp:::g1': (0,0)})

            del jdb['grp:::g1']
            self.assertEqual(grp, {'g2': [2, 3]})
            grp['g1'] = sub_expect['g1']

            # ---------------- APPEND_ONLY ----------------
            log_key = 'audit'
            jdb[log_key] = [1]
            self.assertEqual(jdb.keys.set_flags(log_key, append_only=True), {log_key: (int(JKeyFlag.APPEND_ONLY),0)})
            jdb[log_key] = [1, 2]                     # strict extension -> allowed
            self.assertEqual(jdb[log_key], [1, 2])
            jdb[log_key] = [1]                        # truncation -> refused
            self.assertEqual(jdb[log_key], [1, 2])
            jdb[log_key] = [9, 2, 3]                  # rewrites history -> refused
            self.assertEqual(jdb[log_key], [1, 2])
            jdb[log_key] = [1, 2]                     # equal is not growth -> refused
            self.assertEqual(jdb[log_key], [1, 2])
            jdb[log_key] = 'not a list'               # type change -> refused
            self.assertEqual(jdb[log_key], [1, 2])
            jdb[log_key] = [1, 2, 3, 4]               # extension -> allowed
            self.assertEqual(jdb[log_key], [1, 2, 3, 4])
            del jdb[log_key]                          # append-only forbids removal
            self.assertTrue(log_key in jdb)
            self.assertEqual(jdb.remove(log_key), {})
            self.assertEqual(jdb.unmodify(log_key), {})  # and the unwrite back door
            self.assertEqual(jdb[log_key], [1, 2, 3, 4])

            jdb['txt'] = 'ab'
            self.assertEqual(jdb.keys.set_flags('txt', append_only=True), {'txt': (int(JKeyFlag.APPEND_ONLY),0)})
            jdb['txt'] = 'abc'
            self.assertEqual(jdb['txt'], 'abc')
            jdb['txt'] = 'xabc'                       # not a suffix append -> refused
            self.assertEqual(jdb['txt'], 'abc')

            if jdb.data_type.endswith(('+S', '+M', '+P')):
                jdb['set'] = val = {'a', 'b', 'c'}
                self.assertEqual(jdb.keys.set_flags('set', append_only=True), {'set': (int(JKeyFlag.APPEND_ONLY),0)})
                jdb['set'] = {'a'}
                self.assertEqual(jdb['set'], val)
                jdb['set'] = {'a', 'b', 'e'}
                self.assertEqual(jdb['set'], val)
                jdb['set'] = _val = {'a', 'b', 'c', 'd'}
                self.assertEqual(jdb['set'], _val)

            jdb['map'] = {'a': 1}
            self.assertEqual(jdb.keys.set_flags('map', append_only=True), {'map': (int(JKeyFlag.APPEND_ONLY),0)})
            jdb['map'] = {'a': 1, 'b': 2}
            self.assertEqual(jdb['map'], {'a': 1, 'b': 2})
            jdb['map'] = {'a': 9, 'b': 2}             # changed an existing key -> refused
            jdb['map'] = {'b': 2}                     # dropped an existing key -> refused
            self.assertEqual(jdb['map'], {'a': 1, 'b': 2})

            self.assertEqual(jdb.keys.set_flags(log_key, append_only=False), {log_key: (0,0)})
            jdb[log_key] = []
            self.assertEqual(jdb[log_key], [])

            # ---------------- NO_CACHE ----------------
            blob = 'x' * 256
            jdb['blob'] = blob
            self.assertEqual(jdb['blob'], blob)
            if cache_limit != 0:
                self.assertTrue('blob' in jdb._cache)

            self.assertEqual(jdb.keys.set_flags('blob', no_cache=True), {'blob': (int(JKeyFlag.NO_CACHE),0)})
            self.assertFalse('blob' in jdb._cache)    # turning it on evicts immediately
            self.assertEqual(jdb['blob'], blob)
            self.assertFalse('blob' in jdb._cache)    # a read never re-populates
            jdb['blob'] = blob * 2
            self.assertFalse('blob' in jdb._cache)    # nor does a write
            self.assertEqual(jdb['blob'], blob * 2)

            # neighbouring records keep using the cache
            jdb['hot'] = 'hot'
            self.assertEqual(jdb['hot'], 'hot')
            self.assertEqual('hot' in jdb._cache, cache_limit != 0)

            self.assertEqual(jdb.keys.set_flags('blob', no_cache=False), {'blob': (0,0)})
            self.assertEqual(jdb['blob'], blob * 2)
            self.assertEqual('blob' in jdb._cache, cache_limit != 0)

            # ---------------- NO_REVERT ----------------
            # NOTE: adding a NEW key consumes the SAFE region, so create both
            # rows first and only then give an existing key a history to protect.
            jdb['cnt', 'ctl'] = 0
            self.assertEqual(jdb.keys.set_flags('cnt', no_revert=True), {'cnt': (int(JKeyFlag.NO_REVERT),0)})

            hist_key = 'key5'
            hist_val = jdb[hist_key]
            jdb[hist_key] = 'changed'
            n_lines = jdb.n_lines

            for i in range(1, 64):
                jdb['cnt'] = i

            self.assertEqual(jdb['cnt'], 63)
            self.assertEqual(jdb.n_lines, n_lines)     # not one dead row consumed
            self.assertEqual(jdb.unmodify('cnt'), {})  # nothing was ever parked
            self.assertEqual(jdb['cnt'], 63)

            # the decision is per-row: another key's pending history survived
            self.assertTrue(hist_key in jdb.unmodify(hist_key))
            self.assertEqual(jdb[hist_key], hist_val)

            # a control key without the flag does keep a previous version
            for i in range(1, 64):
                jdb['ctl'] = i

            self.assertEqual(jdb['ctl'], 63)
            self.assertTrue('ctl' in jdb.unmodify('ctl'))  # a previous version WAS parked
            self.assertNotEqual(jdb['ctl'], 63)

            self.assertEqual(jdb.keys.set_flags('cnt', no_revert=False), {'cnt': (0,0)})
            jdb['cnt'] = 64
            self.assertTrue('cnt' in jdb.unmodify('cnt'))
            self.assertEqual(jdb['cnt'], 63)

            # ---------------- LINK ----------------
            jdb['report'] = {'rows': 12}
            self.assertTrue(jdb.set_link('latest', 'report'))
            self.assertEqual(jdb.get_key_flags('latest'), {'latest': (int(JKeyFlag.LINK),0)})
            self.assertEqual(jdb.get_link('latest'), 'report')
            self.assertEqual(jdb.get_link('report', '-'), '-')   # not a link
            self.assertEqual(jdb.get_link('nosuch', '-'), '-')   # not a key

            self.assertEqual(jdb['latest'], {'rows': 12})        # reads follow
            jdb['latest'] = {'rows': 13}                         # writes follow
            self.assertEqual(jdb['report'], {'rows': 13})
            self.assertEqual(jdb['latest'], {'rows': 13})
            self.assertFalse(jdb.set_link('latest', 'report'))   # already points there

            # links are transparent to iteration, comparison and queries
            self.assertEqual(dict(jdb.find_iter(keys='latest', with_value=True)), {'latest': {'rows': 13}})

            # ---- a link may point INTO a group ----
            arc = jdb.add_group('archive')
            arc += {'2026-07': [7], '2026-08': [8]} # replace it
            arc['deep'] = JDb(data_type=arc.data_type, zip_type=arc.zip_type)
            deep = arc['deep']
            deep['x'] = 'X'

            self.assertTrue(jdb.set_link('cur', 'archive:::2026-08'))
            self.assertEqual(jdb['cur'], [8])
            jdb['cur'] = [8, 8]                                  # writes reach the child
            self.assertEqual(arc['2026-08'], [8, 8])

            self.assertTrue(jdb.set_link('deepx', 'archive:::deep:::x'))
            self.assertEqual(jdb['deepx'], 'X')                  # nested to any depth
            jdb['deepx'] = 'Y'
            self.assertEqual(deep['x'], 'Y')

            # ---- a link may point AT a group: a folder link ----
            self.assertTrue(jdb.set_link('folder', 'archive'))
            self.assertTrue(isinstance(jdb['folder'], JDb))
            self.assertEqual(jdb['folder']['2026-07'], [7])
            jdb['folder']['2026-07'] = [70]                      # write via the handle
            self.assertEqual(arc['2026-07'], [70])
            jdb['folder'] = 'clobber'                            # refused: would destroy the group
            self.assertTrue(isinstance(jdb['folder'], JDb))
            self.assertEqual(arc['2026-07'], [70])

            # ---- a link may LIVE inside a group; its target resolves there ----
            self.assertTrue(jdb.set_link('archive:::newest', '2026-08'))
            self.assertEqual(arc.get_link('newest'), '2026-08')
            self.assertEqual(jdb.get_link('archive:::newest'), '2026-08')
            self.assertEqual(arc['newest'], [8, 8])
            arc['newest'] = [8, 8, 8]
            self.assertEqual(arc['2026-08'], [8, 8, 8])

            # ---- links never nest ----
            with self.assertRaises(TypeError):
                jdb.set_link('bad', 'latest')                    # target is a link
            with self.assertRaises(TypeError):
                jdb.set_link('bad', 'archive:::newest')          # target is a link in a group
            with self.assertRaises(KeyError):
                jdb.set_link('bad', 'no_such_key')
            with self.assertRaises(KeyError):
                jdb.set_link('bad', 'archive:::no_such_key')
            with self.assertRaises(TypeError):
                jdb.set_link('bad', 'report:::x')                # component is not a group
            with self.assertRaises(KeyError):
                jdb.set_link('bad', 'bad')                       # itself
            with self.assertRaises(TypeError):
                jdb.set_link('archive', 'report')                # a group cannot become a link
            self.assertFalse('bad' in jdb)

            # a folder link is not traversable as a path component, by design
            with self.assertRaises((KeyError, TypeError)):
                jdb.set_link('bad', 'folder:::2026-07')

            # LINK is derived, so it is never accepted from a caller
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'notalink', 'report', key_flags=JKeyFlag.LINK))

            self.assertEqual(jdb.get_key_flags('notalink'), {'notalink': (0,0)})
            self.assertEqual(jdb['notalink'], 'report')

            # ... and a flag rewrite never drops it
            self.assertEqual(jdb.keys.set_flags('latest', no_revert=True), {'latest': (int(JKeyFlag.LINK | JKeyFlag.NO_REVERT), 0)})
            self.assertEqual(jdb['latest'], {'rows': 13})
            self.assertEqual(jdb.keys.set_flags('latest', no_revert=False), {'latest': (int(JKeyFlag.LINK), 0)})

            # a locked record refuses to become a link
            self.assertEqual(jdb.keys.set_flags('notalink', read_only=True), {'notalink': (int(JKeyFlag.READ_ONLY),0)})
            self.assertFalse(jdb.set_link('notalink', 'report'))
            self.assertEqual(jdb.keys.set_flags('notalink', read_only=False), {'notalink': (0,0)})

            # deleting a link removes the link alone and reports its target path
            self.assertEqual(jdb.remove('cur'), {'cur': 'archive:::2026-08'})
            self.assertFalse('cur' in jdb)
            self.assertEqual(arc['2026-08'], [8, 8, 8])
            self.assertEqual(jdb.remove('folder'), {'folder': 'archive'})
            self.assertEqual(arc['2026-07'], [70])               # the group survives

            # deleting the target leaves the link dangling but still removable
            self.assertEqual(jdb.remove('latest'), {'latest': 'report'})
            self.assertTrue(jdb.set_link('latest', 'report'))
            del jdb['report']
            self.assertEqual(jdb.get_link('latest'), 'report')   # still reports its target
            self.assertEqual(jdb['latest'], None)

            self.assertEqual(dict(jdb.find_iter(vals={'$eq': {'rows': 13}})), {})  # skipped, not raised
            self.assertEqual(jdb.remove('latest'), {'latest': 'report'})
            self.assertFalse('latest' in jdb)

            # relinking an existing link retargets it, across kinds too
            jdb['t1'] = [1]
            self.assertTrue(jdb.set_link('cur', 't1'))
            self.assertEqual(jdb['cur'], [1])
            self.assertTrue(jdb.set_link('cur', 'archive:::2026-07'))
            self.assertEqual(jdb.get_link('cur'), 'archive:::2026-07')
            self.assertEqual(jdb['cur'], [70])
            self.assertEqual(jdb['t1'], [1])                     # old target untouched
            jdb.remove('cur', 't1', 'deepx', 'notalink')
            del jdb['archive:::newest']

            # ---------------- string (chmod-style) flag arguments ----------------
            jdb['strf'] = [1]
            # a string is RELATIVE: bare letters set, '+' sets, '-' clears
            self.assertEqual(jdb.set_key_flags('strf', 'ra'), {'strf': (int(JKeyFlag.READ_ONLY | JKeyFlag.APPEND_ONLY), 0)})
            self.assertEqual(jdb.set_key_flags('strf', '-a+c'), {'strf': (int(JKeyFlag.READ_ONLY | JKeyFlag.NO_CACHE),0)})
            self.assertEqual(jdb.keys.set_flags('strf', '+h'), {'strf': (int(JKeyFlag.READ_ONLY | JKeyFlag.NO_CACHE | JKeyFlag.HIDDEN),0)})
            self.assertEqual(jdb.set_key_flags('strf', 'RCH'), {})      # case-insensitive -> no change
            self.assertEqual(jdb.set_key_flags('strf', '+x'), {})       # unknown letter ignored

            # an int/JKeyFlag is ABSOLUTE: the record ends up with exactly those bits
            self.assertEqual(jdb.set_key_flags('strf', JKeyFlag.NO_REVERT), {'strf': (int(JKeyFlag.NO_REVERT),0)})

            # per-flag keywords still win over the string
            self.assertEqual(jdb.set_key_flags('strf', '+r+c', no_cache=False), {'strf': (int(JKeyFlag.READ_ONLY | JKeyFlag.NO_REVERT),0)})

            # USER0-3 use digit letters and must parse
            self.assertEqual(jdb.set_key_flags('strf', '-r+0+3'), {'strf': (int(JKeyFlag.NO_REVERT | JKeyFlag.USER0 | JKeyFlag.USER3),0)})

            # derived bits can never be set from a string
            self.assertEqual(jdb.set_key_flags('strf', '-v-0-3+g+l'), {'strf': (0,0)})
            jdb.remove('strf')

            # f_write / f_append / f_write_key_flags accept the same forms
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'sw', 1, key_flags='ra'))
                self.assertTrue(jdb.f_append(fp, 'sa', 1, key_flags='+h+0'))
                self.assertTrue(jdb.f_write_key_flags(fp, 'sw', '-a'))

            self.assertEqual(jdb.get_key_flags('sw'), {'sw': (int(JKeyFlag.READ_ONLY),0)})
            self.assertEqual(jdb.get_key_flags('sa'), {'sa': (int(JKeyFlag.HIDDEN | JKeyFlag.USER0),0)})
            jdb.set_key_flags('sw', '-r')
            jdb.remove('sw', 'sa')

            # a group keeps its derived GROUP bit through a string flag write
            sgrp = jdb.add_group('sgrp')
            sgrp['x'] = 1
            self.assertEqual(jdb.set_key_flags('sgrp', '+c'), {'sgrp': (int(JKeyFlag.GROUP | JKeyFlag.NO_CACHE),0)})
            self.assertEqual(jdb['sgrp'], {'x': 1})
            jdb.remove('sgrp')

            # ---------------- HIDDEN ----------------
            jdb['shown'] = [1]
            jdb['quiet'] = [9]
            self.assertEqual(jdb.set_key_flags('quiet', hidden=True), {'quiet': (int(JKeyFlag.HIDDEN),0)})

            # the three query APIs hide it ...
            self.assertFalse('quiet' in jdb.find())
            self.assertFalse('quiet' in jdb.show(limit=0))
            self.assertFalse('quiet' in set(jdb.keys(vals={'$eq': [9]})))
            self.assertEqual(jdb.find(vals={'$eq': [9]}), {})

            # ... and with_hidden=True opts back in
            self.assertTrue('quiet' in jdb.find(with_hidden=True))
            self.assertTrue('quiet' in jdb.show(limit=0, with_hidden=True))
            self.assertTrue('quiet' in set(jdb.keys(vals={'$eq': [9]}, with_hidden=True)))

            # everything else treats it as an ordinary record: this flag is NOT
            # access control, and every mapping-like API must stay in agreement
            self.assertEqual(jdb['quiet'], [9])
            self.assertTrue('quiet' in jdb)
            self.assertTrue('quiet' in dict(jdb.items()))
            self.assertTrue([9] in list(jdb.values()))
            self.assertTrue('quiet' in dict(jdb.item_iter()))
            self.assertTrue('quiet' in dict(jdb.item_iter(re.compile(r'quiet'))))
            self.assertTrue('quiet' in dict(jdb.item_iter(lambda k: True)))
            self.assertTrue('quiet' in jdb[:])
            self.assertTrue('quiet' in set(jdb))
            self.assertTrue('quiet' in set(jdb.keys))
            self.assertTrue('quiet' in dict(jdb.keys.items()))
            self.assertEqual(len(dict(jdb.items())), len(jdb))
            self.assertEqual(jdb.get_key_flags('quiet'), {'quiet': (int(JKeyFlag.HIDDEN),0)})

            # find_iter is the raw iterator: it does NOT hide
            self.assertTrue('quiet' in dict(jdb.find_iter()))
            self.assertFalse('quiet' in dict(jdb.find_iter(with_hidden=False)))

            # a key-selector bulk write is a MAPPING op, so it does reach it
            # (documented, not a bug); only Query-shaped APIs hide
            jdb[re.compile(r'quiet')] = [0]
            self.assertEqual(jdb['quiet'], [0])

            # map() is a query surface too, so it hides by default
            self.assertEqual(jdb.map(lambda k, v: k, keys=r'^(shown|quiet)$'), ['shown'])
            self.assertEqual(sorted(jdb.map(lambda k, v: k, keys=r'^(shown|quiet)$', with_hidden=True)), ['quiet', 'shown'])
            self.assertRaises(TypeError, jdb.map, None)

            self.assertEqual(jdb.set_key_flags('quiet', '-h'), {'quiet': (0,0)})
            self.assertTrue('quiet' in jdb.find())
            self.assertEqual(jdb.set_key_flags('quiet', 'h'), {'quiet': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(jdb.set_key_flags('quiet', '+h'), {})   # already hidden -> no change
            self.assertEqual(jdb.set_key_flags('quiet', '+r+0'), {'quiet': (int(JKeyFlag.HIDDEN | JKeyFlag.READ_ONLY | JKeyFlag.USER0),0)})
            self.assertEqual(jdb.set_key_flags('quiet', hidden=False), {'quiet': (int(JKeyFlag.READ_ONLY | JKeyFlag.USER0),0)})
            self.assertEqual(jdb.set_key_flags('quiet', hidden=True), {'quiet': (int(JKeyFlag.HIDDEN | JKeyFlag.READ_ONLY | JKeyFlag.USER0), 0)})
            self.assertEqual(jdb.set_key_flags('quiet', '-r-0'), {'quiet': (int(JKeyFlag.HIDDEN),0)})

            # ... and take every selector set_key_flags does
            self.assertEqual(jdb.set_key_flags(re.compile(r'^shown$'), '+h'), {'shown': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(jdb.set_key_flags(lambda k: k == 'shown', '-h'), {'shown': (0,0)})
            self.assertEqual(jdb.set_key_flags(['shown'], hidden=True), {'shown': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(sorted(jdb.find(keys=r'^(shown|quiet)$')), [])
            self.assertEqual(jdb.set_key_flags('shown', hidden=False), {'shown': (0,0)})

            # a bare keys() call is still a QUERY, so it hides -- and it must not
            # short-circuit past limit/skip either
            self.assertFalse('quiet' in set(jdb.keys()))
            self.assertTrue('quiet' in set(jdb.keys(with_hidden=True)))
            self.assertTrue('quiet' in set(jdb.keys))            # the property is the mapping surface
            self.assertEqual(len(set(jdb.keys(limit=2))), 2)
            self.assertEqual(len(set(jdb.keys(limit=2, with_hidden=True))), 2)
            self.assertEqual(len(set(jdb.keys(skip=len(jdb) - 2, with_hidden=True))), 2)

            # ---- update_if: a Query sweep must not reach a hidden record ----
            jdb['ud1'] = {'hcnt': 1}
            jdb['ud2'] = {'hcnt': 2}
            self.assertEqual(jdb.set_key_flags('ud2', hidden=True), {'ud2': (int(JKeyFlag.HIDDEN),0)})

            self.assertEqual(jdb.update_if(Query().hcnt > 0, {'seen': True}), 1)
            self.assertEqual(jdb['ud1'], {'hcnt': 1, 'seen': True})
            self.assertEqual(jdb['ud2'], {'hcnt': 2})            # untouched
            self.assertEqual(jdb.update_if(Query().hcnt > 0, {'seen': True}, with_hidden=True), 1)
            self.assertEqual(jdb['ud2'], {'hcnt': 2, 'seen': True})

            # the delete branch honours it as well
            self.assertEqual(jdb.update_if(Query().hcnt > 0, None), 1)
            self.assertFalse('ud1' in jdb)
            self.assertTrue('ud2' in jdb)
            self.assertEqual(jdb.update_if(Query().hcnt > 0, None, with_hidden=True), 1)
            self.assertFalse('ud2' in jdb)

            # ---- to_csv / clone_to, on a db of this config's own format ----
            from csv import DictReader
            jhid = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jhid.insert({'c1': {'n': 1}, 'c2': {'n': 2}, '_meta': {'n': 9, 'secret': 'x'}})
            self.assertEqual(jhid.set_key_flags('_meta', '+h'), {'_meta': (int(JKeyFlag.HIDDEN),0)})

            # a dump leaves the hidden row out -- and never discovers its columns
            with io.StringIO() as fp:
                self.assertTrue(jhid.to_csv(fp))
                fp.seek(0)
                rows = list(DictReader(fp))

            self.assertEqual({r['_id'] for r in rows}, {'c1', 'c2'})
            self.assertFalse('secret' in rows[0])

            with io.StringIO() as fp:
                self.assertTrue(jhid.to_csv(fp, with_hidden=True))
                fp.seek(0)
                rows = list(DictReader(fp))

            self.assertEqual({r['_id'] for r in rows}, {'c1', 'c2', '_meta'})
            self.assertTrue('secret' in rows[0])

            # a clone is faithful by default (backup/restore/upgrade rely on it)
            cln = jhid.clone_to(JDb(data_type=jdb.data_type, zip_type=jdb.zip_type), signal='')
            self.assertEqual(len(cln), 3)
            self.assertEqual(cln.get_key_flags('_meta'), {'_meta': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(cln['_meta'], {'n': 9, 'secret': 'x'})

            # ... but can be asked to strip the bookkeeping, groups included
            hgrp = jhid.add_group('hgrp')
            hgrp.insert({'g': {'n': 1}, '_g': {'n': 2}})
            self.assertEqual(hgrp.set_key_flags('_g', 'h'), {'_g': (int(JKeyFlag.HIDDEN),0)})

            cln = jhid.clone_to(JDb(data_type=jdb.data_type, zip_type=jdb.zip_type), signal='', with_hidden=False)
            self.assertEqual(set(cln.keys(with_hidden=True)), {'c1', 'c2', 'hgrp'})
            self.assertEqual(set(cln['hgrp'].keys(with_hidden=True)), {'g'})

            # ---- a hidden GROUP keeps its subtree out of a query ----
            self.assertEqual(sorted(jhid.find(':::')), ['hgrp:::g'])
            self.assertEqual(jhid.set_key_flags('hgrp', 'h'), {'hgrp': (int(JKeyFlag.GROUP | JKeyFlag.HIDDEN),0)})
            self.assertEqual(sorted(jhid.find(':::')), [])
            self.assertEqual(sorted(jhid.find(':::', with_hidden=True)), ['hgrp:::_g', 'hgrp:::g'])
            self.assertEqual(jhid['hgrp']['g'], {'n': 1})        # still reachable by name

            # a group-scoped selector routes to the child index
            self.assertEqual(jhid.set_key_flags('hgrp:::g', 'h'), {'hgrp:::g': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(hgrp.get_key_flags('g'), {'g': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(jhid.set_key_flags('hgrp:::g', '-h'), {'hgrp:::g': (0,0)})

            # un-hiding needs no special casing
            self.assertEqual(jdb.set_key_flags('quiet', '-h'), {'quiet': (0,0)})
            self.assertTrue('quiet' in jdb.find())
            jdb.remove('quiet', 'shown')

            # ---------------- UNLOCK: a per-call sudo ----------------
            jdb['lk'] = [1]
            jdb['ao'] = [1]
            self.assertEqual(jdb.set_key_flags('lk', '+r+2'), {'lk': (int(JKeyFlag.READ_ONLY | JKeyFlag.USER2),0)})
            self.assertEqual(jdb.set_key_flags('ao', '+a'), {'ao': (int(JKeyFlag.APPEND_ONLY),0)})

            # without it, the locks hold
            self.assertIsNone(jdb.set('lk', [9]))
            self.assertEqual(jdb['lk'], [1])
            self.assertIsNone(jdb.set('ao', [0]))
            self.assertEqual(jdb['ao'], [1])

            # with it, both locks are waived for that one call
            self.assertEqual(jdb.set('lk', [9], key_flags='u'), [9])
            self.assertEqual(jdb['lk'], [9])
            self.assertEqual(jdb.set('ao', [0], key_flags=JKeyFlag.UNLOCK), [0])
            self.assertEqual(jdb['ao'], [0])

            # ... and the record's own flags are untouched
            self.assertEqual(jdb.get_key_flags('lk'), {'lk': (int(JKeyFlag.READ_ONLY | JKeyFlag.USER2),0)})
            self.assertEqual(jdb.get_key_flags('ao'), {'ao': (int(JKeyFlag.APPEND_ONLY),0)})
            self.assertIsNone(jdb.set('lk', [8]))                 # still locked afterwards
            self.assertEqual(jdb['lk'], [9])

            # UNLOCK can be combined with real flag changes
            self.assertEqual(jdb.set('lk', [9, 9], key_flags='+u+c'), [9, 9])
            self.assertEqual(jdb.get_key_flags('lk'), {'lk': (int(JKeyFlag.READ_ONLY | JKeyFlag.USER2 | JKeyFlag.NO_CACHE),0)})

            # deletes: remove() / pop() / f_delete()
            self.assertEqual(jdb.remove('lk'), {})                # refused, not reported
            self.assertTrue('lk' in jdb)
            self.assertEqual(jdb.remove('lk', key_flags='u'), {'lk': [9, 9]})
            self.assertFalse('lk' in jdb)

            jdb['lk'] = [1]
            jdb.set_key_flags('lk', '+r')
            self.assertEqual(jdb.pop('lk'), [1])                  # locked: value returned, key kept
            self.assertTrue('lk' in jdb)
            self.assertEqual(jdb.pop('lk', key_flags='u'), [1])
            self.assertFalse('lk' in jdb)

            jdb.set('ao', [0, 1, 2], key_flags='f')                # grow back for the next checks
            with jdb.open() as fp:
                self.assertFalse(jdb.f_write(fp, 'ao', [7]))      # shrink refused
                self.assertTrue(jdb.f_write(fp, 'ao', [7], key_flags='u'))
                self.assertIs(jdb.f_delete(fp, 'ao'), LOCKED)
                self.assertEqual(jdb.f_delete(fp, 'ao', key_flags='u'), [7])

            self.assertFalse('ao' in jdb)

            # UNLOCK is transient: above KEY_FLAG_MASK, so it can never be stored
            self.assertEqual(int(JKeyFlag.UNLOCK) & 0xFFFF, 0)
            jdb['tr'] = [1]
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'tr2', [1], key_flags='u'))
                self.assertTrue(jdb.f_append(fp, 'tr3', [1], key_flags='+u+r'))

            # f_append on an EXISTING key forwards to f_write, so key_flags has to
            # survive that hop in every form it can arrive in -- None and str both
            # used to reach an `int | key_flags` and raise TypeError
            jdb['fa'] = [1]
            with jdb.open() as fp:
                self.assertTrue(jdb.f_append(fp, 'fa', [1, 2]))                    # None
                self.assertTrue(jdb.f_append(fp, 'fa', [1, 2, 3], key_flags='+0')) # str
                self.assertTrue(jdb.f_append(fp, 'fa', [1, 2, 3, 4], key_flags=JKeyFlag.USER1))

            self.assertEqual(jdb['fa'], [1, 2, 3, 4])
            self.assertEqual(jdb.get_key_flags('fa'), {'fa': (int(JKeyFlag.USER1),0)})
            jdb.set_key_flags('fa', '-0-1')
            jdb.remove('fa')

            self.assertEqual(jdb.get_key_flags('tr2'), {'tr2': (0,0)})
            self.assertEqual(jdb.get_key_flags('tr3'), {'tr3': (int(JKeyFlag.READ_ONLY),0)})
            self.assertEqual(jdb.set_key_flags('tr', 'u'), {})     # nothing to store
            self.assertEqual(jdb.get_key_flags('tr'), {'tr': (0,0)})
            for bad in ('+u', '+n', '+w', '+y', JKeyFlag.EXCL):
                with self.assertRaises(ValueError):
                    jdb.find(key_flags=bad)

            jdb.set_key_flags('tr3', '-r')
            jdb.remove('tr', 'tr2', 'tr3')

            # ---------------- MUST_EXIST: update-or-nothing ----------------
            self.assertEqual(int(JKeyFlag.MUST_EXIST) & 0xFFFF, 0)
            self.assertIsNone(jdb.set('me', [1], key_flags='m'))     # refused: no such key
            self.assertNotIn('me', jdb)
            jdb['me'] = [1]
            self.assertEqual(jdb.set('me', [2], key_flags='m'), [2]) # allowed: it exists
            self.assertEqual(jdb['me'], [2])

            # transient, so it is consumed rather than stored
            self.assertEqual(jdb.set('me', [3], key_flags='+m+c'), [3])
            self.assertEqual(jdb.get_key_flags('me'), {'me': (int(JKeyFlag.NO_CACHE),0)})
            jdb.set_key_flags('me', '-c')

            with jdb.open() as fp:
                self.assertFalse(jdb.f_write(fp, 'me_gone', [1], key_flags='m'))
                self.assertTrue(jdb.f_write(fp, 'me', [4], key_flags=JKeyFlag.MUST_EXIST))

            self.assertNotIn('me_gone', jdb)
            self.assertEqual(jdb['me'], [4])

            # EXCL and MUST_EXIST are mirrors: together they can never both pass
            for key in ('me', 'me_absent'):
                self.assertNotEqual(bool(jdb.set(key, [9], key_flags='w')), bool(jdb.set(key, [9], key_flags='m')))

            jdb.remove('me', 'me_absent')

            # ---------------- NO_DELETE: editable but not removable ----------------
            jdb['nd'] = [1]
            jdb.set_key_flags('nd', '+p')
            self.assertEqual(jdb.get_key_flags('nd'), {'nd': (int(JKeyFlag.NO_DELETE),0)})

            # the whole point: writes still go through
            self.assertEqual(jdb.set('nd', [1, 2]), [1, 2])
            self.assertEqual(jdb['nd'], [1, 2])

            # ... while every delete path refuses
            self.assertEqual(jdb.remove('nd'), {})
            self.assertIn('nd', jdb)
            jdb.remove_fast('nd')                                  # returns None by design
            self.assertIn('nd', jdb)
            del jdb['nd']
            self.assertIn('nd', jdb)
            jdb -= jdb
            self.assertIn('nd', jdb)

            # UNLOCK waives it for one call, exactly like the write locks
            self.assertEqual(jdb.remove('nd', key_flags='u'), {'nd': [1, 2]})
            self.assertNotIn('nd', jdb)

            # the keyword form sets the same bit
            jdb['nd2'] = [1]
            self.assertEqual(jdb.set_key_flags('nd2', no_delete=True), {'nd2': (int(JKeyFlag.NO_DELETE),0)})
            self.assertEqual(jdb.remove('nd2'), {})
            self.assertEqual(jdb.set_key_flags('nd2', no_delete=False), {'nd2': (0,0)})
            self.assertEqual(jdb.remove('nd2'), {'nd2': [1]})

            # READ_ONLY still blocks both, so NO_DELETE is strictly the weaker lock
            jdb['ro'] = [1]
            jdb.set_key_flags('ro', '+r')
            self.assertIsNone(jdb.set('ro', [2]))
            self.assertEqual(jdb.remove('ro'), {})
            jdb.set_key_flags('ro', '-r')
            jdb.remove('ro')

            # ---------------- EXCL: create-or-nothing ----------------
            jdb['ex'] = [1]
            self.assertIsNone(jdb.set('ex', [2], key_flags='w'))   # refused silently
            self.assertEqual(jdb['ex'], [1])
            self.assertIsNone(jdb.set('ex', [1], key_flags='w'))   # even when the value matches
            self.assertEqual(jdb.set('ex2', [2], key_flags='w'), [2])
            self.assertEqual(jdb['ex2'], [2])

            # the refusal happens before any flag is applied
            self.assertIsNone(jdb.set('ex', [3], key_flags='+w+r'))
            self.assertEqual(jdb.get_key_flags('ex'), {'ex': (0,0)})

            # EXCL is transient: it is consumed, never stored
            self.assertEqual(int(JKeyFlag.EXCL) & 0xFFFF, 0)
            self.assertEqual(jdb.set('ex3', [1], key_flags='+w+c'), [1])
            self.assertEqual(jdb.get_key_flags('ex3'), {'ex3': (int(JKeyFlag.NO_CACHE),0)})

            with jdb.open() as fp:
                self.assertFalse(jdb.f_write(fp, 'ex', [9], key_flags='w'))
                self.assertTrue(jdb.f_write(fp, 'ex4', [9], key_flags=JKeyFlag.EXCL))

            self.assertEqual(jdb['ex'], [1])
            self.assertEqual(jdb.get_key_flags('ex4'), {'ex4': (0,0)})

            # EXCL outranks UNLOCK: sudo waives locks, it does not create twice
            jdb.set_key_flags('ex', '+r')
            self.assertIsNone(jdb.set('ex', [5], key_flags='+w+u'))
            self.assertEqual(jdb['ex'], [1])
            jdb.set_key_flags('ex', '-r')

            # setdefault is EXCL, and now reports who won
            self.assertTrue(jdb.setdefault('sd', [1]))
            self.assertFalse(jdb.setdefault('sd', [2]))
            self.assertEqual(jdb['sd'], [1])
            self.assertTrue(jdb.setdefault('sd2', [1], key_flags='+h'))
            self.assertEqual(jdb.get_key_flags('sd2'), {'sd2': (int(JKeyFlag.HIDDEN),0)})
            jdb.set_key_flags('sd2', '-h')
            jdb.remove('ex', 'ex2', 'ex3', 'ex4', 'sd', 'sd2')

            # ---------------- NO_ATIME: write without touching the day ----------------
            self.assertEqual(int(JKeyFlag.NO_ATIME) & 0xFFFF, 0)
            old_day = '2026-01-01'
            old_days = jdb.io.z_conv_str_to_days(old_day)
            mdays_of = lambda k: jdb.keys[k][7]                    # read_key: 6=cdays, 7=mdays
            with jdb.open() as fp:
                # mdays is stored as a delta from cdays, so back-dating needs both
                self.assertTrue(jdb.f_write(fp, 'na', [1], cdays=old_day, mdays=old_day))

            self.assertEqual(mdays_of('na'), old_days)
            self.assertEqual(jdb.set('na', [1, 2], key_flags='y'), [1, 2])
            self.assertEqual(jdb['na'], [1, 2])
            self.assertEqual(mdays_of('na'), old_days)            # the day did not move

            # without it, the same write stamps today
            self.assertEqual(jdb.set('na', [1, 2, 3]), [1, 2, 3])
            self.assertEqual(mdays_of('na'), jdb.io.days)

            # an explicit mdays= still wins, and NO_ATIME stores nothing
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'na', [4], mdays='2026-03-04', key_flags='+y+c'))

            self.assertEqual(mdays_of('na'), jdb.io.z_conv_str_to_days('2026-03-04'))
            self.assertEqual(jdb.get_key_flags('na'), {'na': (int(JKeyFlag.NO_CACHE),0)})

            # on a new record there is no day to keep, so it is a no-op
            self.assertEqual(jdb.set('na2', [1], key_flags='y'), [1])
            self.assertEqual(mdays_of('na2'), jdb.io.days)

            # a TTL counts from mdays, so NO_ATIME deliberately does NOT renew it
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'na3', [1], cdays=old_day, mdays=old_day, ttl=5))

            self.assertEqual(jdb.get_key_flags('na3'), {'na3': (int(JKeyFlag.EXPIRE), 5)})
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'na3', [1, 2], key_flags='y'))

            self.assertEqual(mdays_of('na3'), old_days)
            self.assertEqual(jdb.get_key_flags('na3'), {'na3': (int(JKeyFlag.EXPIRE), 5)})
            jdb.remove('na', 'na2', 'na3')

            # ---------------- NO_FOLLOW: the link itself, not its target ----------------
            self.assertEqual(int(JKeyFlag.NO_FOLLOW) & 0xFFFF, 0)
            jdb['nf_dst'] = {'rows': 12}
            self.assertTrue(jdb.set_link('nf', 'nf_dst'))
            self.assertEqual(jdb.get('nf'), {'rows': 12})           # reads follow
            self.assertEqual(jdb.get('nf', key_flags='n'), 'nf_dst')

            # a NO_FOLLOW read must never leave the target path in the cache
            self.assertEqual(jdb.get('nf'), {'rows': 12})
            self.assertEqual(jdb.get('nf', key_flags='n'), 'nf_dst')
            self.assertEqual(jdb['nf'], {'rows': 12})

            # unlike get_link, a record that is NOT a link still reads normally
            self.assertEqual(jdb.get_link('nf_dst', '-'), '-')
            self.assertEqual(jdb.get('nf_dst', key_flags='n'), {'rows': 12})
            self.assertEqual(jdb.get('nosuch', -1, key_flags='n'), -1)

            # a dangling link reports its target either way
            del jdb['nf_dst']
            self.assertIsNone(jdb.get('nf'))
            self.assertEqual(jdb.get('nf', key_flags='n'), 'nf_dst')
            jdb['nf_dst'] = {'rows': 12}

            # on write it retargets the link in place, like set_link
            jdb['nf_alt'] = {'rows': 99}
            self.assertEqual(jdb.set('nf', 'nf_alt', key_flags='n'), 'nf_alt')
            self.assertEqual(jdb.get('nf', key_flags='n'), 'nf_alt')
            self.assertEqual(jdb['nf'], {'rows': 99})
            self.assertEqual(jdb['nf_dst'], {'rows': 12})           # old target untouched
            self.assertEqual(jdb.get_key_flags('nf'), {'nf': (int(JKeyFlag.LINK),0)})

            # ... and a plain write still goes THROUGH the link
            jdb['nf'] = {'rows': 100}
            self.assertEqual(jdb['nf_alt'], {'rows': 100})
            self.assertEqual(jdb.get('nf', key_flags='n'), 'nf_alt')

            # a retarget needs a path, not a value (open() re-raises as plain TypeError)
            with self.assertRaises(TypeError):
                jdb.set('nf', {'not': 'a path'}, key_flags='n')

            # writing through a link now carries key_flags to the target
            self.assertEqual(jdb.set('nf', {'rows': 101}, key_flags='+h'), {'rows': 101})
            self.assertEqual(jdb.get_key_flags('nf_alt'), {'nf_alt': (int(JKeyFlag.HIDDEN),0)})
            self.assertEqual(jdb.get_key_flags('nf'), {'nf': (int(JKeyFlag.LINK),0)})
            jdb.set_key_flags('nf_alt', '-h')
            jdb.remove('nf', 'nf_dst', 'nf_alt')

            # ---------------- key_flags= query filter ----------------
            jdb.set_key_flags(None, '-r-a')          # unlock leftovers
            jdb.remove(jdb)
            jdb.insert({'p': [1], 'q': [2], 'r': [3], 'z': [9]})
            jdb.set_key_flags('p', '+0')
            jdb.set_key_flags('q', '+0+r')
            jdb.set_key_flags('z', '+h+0')

            # '+x' requires, '-x' forbids, an unnamed flag keeps the method default
            self.assertEqual(sorted(jdb.find(key_flags='+0')), ['p', 'q'])
            self.assertEqual(sorted(jdb.find(key_flags='+0+r')), ['q'])
            self.assertEqual(sorted(jdb.find(key_flags='-0')), ['r'])
            self.assertEqual(sorted(jdb.find(key_flags='+0-r')), ['p'])
            self.assertEqual(sorted(jdb.find(key_flags=JKeyFlag.READ_ONLY)), ['q'])
            self.assertEqual(sorted(jdb.find(key_flags='+1')), [])

            # 'h' is the one flag with a non-neutral default, so key_flags can
            # express every state with_hidden can -- plus one it cannot
            self.assertEqual(sorted(jdb.find()), ['p', 'q', 'r'])
            self.assertEqual(sorted(jdb.find(with_hidden=True)), ['p', 'q', 'r', 'z'])
            self.assertEqual(sorted(jdb.find(key_flags='+h')), ['z'])
            self.assertEqual(sorted(jdb.find(key_flags='-h')), ['p', 'q', 'r'])
            self.assertEqual(sorted(jdb.find(key_flags='+0', with_hidden=True)), ['p', 'q', 'z'])

            # composes with every other query rule, on every query surface
            self.assertEqual(jdb.find(keys=r'^[pq]$', key_flags='+0', vals={'$eq': [2]}), {'q': [2]})
            self.assertEqual(sorted(jdb.show(limit=0, key_flags='+0')), ['p', 'q'])
            self.assertEqual(sorted(jdb.keys(key_flags='+0')), ['p', 'q'])

            # find_iter is the raw iterator: it does not hide unless asked
            self.assertEqual(sorted(dict(jdb.find_iter())), ['p', 'q', 'r', 'z'])
            self.assertEqual(sorted(dict(jdb.find_iter(key_flags='-h'))), ['p', 'q', 'r'])
            self.assertEqual(sorted(dict(jdb.find_iter(key_flags='+0'))), ['p', 'q', 'z'])

            # group scans: the descent gate uses HIDDEN only, the record filter uses all
            kgrp = jdb.add_group('kgrp')
            kgrp.insert({'gv': [1], 'gh': [2]})
            kgrp.set_key_flags('gh', '+h+0')
            kgrp.set_key_flags('gv', '+0')
            self.assertEqual(sorted(jdb.find(':::')), ['kgrp:::gv'])
            self.assertEqual(sorted(jdb.find(':::', key_flags='+0')), ['kgrp:::gv'])
            self.assertEqual(sorted(jdb.find(':::', key_flags='+h')), ['kgrp:::gh'])
            self.assertEqual(sorted(jdb.find(':::', with_hidden=True)), ['kgrp:::gh', 'kgrp:::gv'])

            # a hidden group keeps its whole subtree out of a query
            jdb.set_key_flags('kgrp', '+h')
            self.assertEqual(sorted(jdb.find(':::')), [])
            self.assertEqual(sorted(jdb.find(':::', with_hidden=True)), ['kgrp:::gh', 'kgrp:::gv'])
            jdb.set_key_flags('kgrp', '-h')
            jdb.remove('kgrp')

            jdb.set_key_flags(None, '-0-r')
            jdb.set_key_flags('z', '-h-0')
            jdb.remove(jdb)
            self.assertEqual(jdb.insert(expect), expect)

            # ---------------- USER0-3: stored, inert ----------------
            user_all = int(JKeyFlag.USER0 | JKeyFlag.USER1 | JKeyFlag.USER2 | JKeyFlag.USER3)
            self.assertEqual(JKeyFlag('0123'), JKeyFlag(user_all))
            self.assertEqual(jdb.set_key_flags('key7', '+0+3'), {'key7': (int(JKeyFlag.USER0 | JKeyFlag.USER3),0)})
            self.assertEqual(jdb['key7'], expect['key7'])        # no behaviour attached
            jdb['key7'] = expect['key7'] + [99]
            self.assertEqual(jdb['key7'], expect['key7'] + [99])

            # they survive a delete/undelete round-trip and combine with real flags
            self.assertEqual(jdb.remove('key7'), {'key7': expect['key7'] + [99]})
            self.assertTrue('key7' in jdb.unremove('key7'))
            self.assertEqual(jdb.get_key_flags('key7'), {'key7': (int(JKeyFlag.USER0 | JKeyFlag.USER3),0)})
            self.assertEqual(jdb.set_key_flags('key7', '12r'), {'key7': (user_all | int(JKeyFlag.READ_ONLY),0)})
            jdb['key7'] = 'blocked'
            self.assertEqual(jdb['key7'], expect['key7'] + [99])
            self.assertEqual(jdb.set_key_flags('key7', '-0-1-2-3', read_only=False), {'key7': (0,0)})
            jdb['key7'] = expect['key7']

            # ---------------- flags survive a delete/undelete round-trip ----------------
            jdb['ghost'] = 1
            ghost_flags = int(JKeyFlag.NO_CACHE | JKeyFlag.NO_REVERT), 0
            self.assertEqual(jdb.keys.set_flags('ghost', '+c', no_revert=True), {'ghost': ghost_flags})
            del jdb['ghost']
            self.assertFalse('ghost' in jdb)
            self.assertTrue('ghost' in jdb.unremove('ghost'))
            self.assertEqual(jdb['ghost'], 1)
            self.assertEqual(jdb.keys.get_flags('ghost'), {'ghost': ghost_flags})

            # ---------------- set_flags: selectors and tri-state ----------------
            jdb['sel1', 'sel2'] = 1
            both = int(JKeyFlag.NO_CACHE), 0
            self.assertEqual(jdb.keys.set_flags(['sel1', 'sel2'], no_cache=True), {'sel1': both, 'sel2': both})
            self.assertEqual(jdb.keys.set_flags(re.compile(r'sel[12]$'), no_cache=True), {})  # already set
            self.assertEqual(jdb.keys.set_flags('sel1'), {})                                  # all None -> no-op

            both = int(JKeyFlag.NO_CACHE | JKeyFlag.NO_REVERT), 0
            self.assertEqual(jdb.keys.set_flags(Query().startswith('sel'), no_revert=True), {'sel1': both, 'sel2': both}) # no_cache untouched
            self.assertEqual(jdb.keys.set_flags('sel1', no_cache=False), {'sel1': (int(JKeyFlag.NO_REVERT),0)})
            self.assertEqual(jdb.keys.set_flags(lambda k: k.startswith('sel'), '-c-v'), {'sel1': (0,0), 'sel2': (0,0)})

            # ---------------- EXPIRE: derived from ttl, never from the caller ----------------
            expire = int(JKeyFlag.EXPIRE)
            jdb['exp'] = 1
            self.assertEqual(jdb.get_key_flags('exp'), {'exp': (0, 0)})

            # a ttl sets EXPIRE, and the reported ttl is what actually got stored
            self.assertEqual(jdb.set_key_flags('exp', ttl=30), {'exp': (expire, 30)})
            self.assertEqual(jdb.get_key_flags('exp'), {'exp': (expire, 30)})
            self.assertEqual(jdb.set_key_flags('exp', ttl=30), {})   # unchanged -> not reported

            # ttl=None leaves it alone, ttl=0 removes it
            self.assertEqual(jdb.set_key_flags('exp', ttl=None), {})
            self.assertEqual(jdb.get_key_flags('exp'), {'exp': (expire, 30)})
            self.assertEqual(jdb.set_key_flags('exp', ttl=0), {'exp': (0, 0)})
            self.assertEqual(jdb.set_key_flags('exp', ttl=0), {})     # already gone

            # out of range is clamped, and the return value never claims otherwise
            self.assertEqual(jdb.set_key_flags('exp', ttl=MAX_TTL_DAYS * 100), {'exp': (expire, MAX_TTL_DAYS)})
            self.assertEqual(jdb.get_key_flags('exp'), {'exp': (expire, MAX_TTL_DAYS)})
            self.assertEqual(jdb.set_key_flags('exp', ttl=-5), {'exp': (0, 0)})    # <=0 clears

            # EXPIRE is derived: a caller may never set it by name
            jdb['exp2'] = 1
            self.assertEqual(jdb.set_key_flags('exp2', '+e'), {})
            self.assertEqual(jdb.set_key_flags('exp2', JKeyFlag.EXPIRE), {})
            self.assertEqual(jdb.get_key_flags('exp2'), {'exp2': (0, 0)})
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'exp2', 2, key_flags=JKeyFlag.EXPIRE))

            self.assertEqual(jdb.get_key_flags('exp2'), {'exp2': (0, 0)})

            # ... nor clear one: an absolute int flags= only speaks for writable bits
            self.assertEqual(jdb.set_key_flags('exp2', ttl=7), {'exp2': (expire, 7)})
            self.assertEqual(jdb.set_key_flags('exp2', JKeyFlag.READ_ONLY), {'exp2': (expire | int(JKeyFlag.READ_ONLY), 7)})
            self.assertEqual(jdb.set_key_flags('exp2', '-r'), {'exp2': (expire, 7)})

            # a ttl combines with the writable flags and survives a rewrite
            self.assertEqual(jdb.set_key_flags('exp2', '+c+0'), {'exp2': (expire | int(JKeyFlag.NO_CACHE | JKeyFlag.USER0), 7)})
            jdb['exp2'] = 3
            self.assertEqual(jdb['exp2'], 3)
            self.assertEqual(jdb.get_key_flags('exp2'), {'exp2': (expire | int(JKeyFlag.NO_CACHE | JKeyFlag.USER0), 7)})

            # ... and a delete/undelete round-trip
            del jdb['exp2']
            self.assertTrue('exp2' in jdb.unremove('exp2'))
            self.assertEqual(jdb.get_key_flags('exp2'), {'exp2': (expire | int(JKeyFlag.NO_CACHE | JKeyFlag.USER0), 7)})

            # the EXPIRE layout narrows the modified-delta, so the dates must still hold
            old_date = dt.date.today() - dt.timedelta(days=400)
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'exp3', 1, cdays=old_date, ttl=45))

            _meta = jdb.keys['exp3']
            self.assertEqual(_meta[8], 45)
            self.assertTrue(_meta[9] & expire)
            self.assertEqual(_meta[11], str(old_date))                  # created
            self.assertEqual(_meta[10], str(dt.date.today()))           # modified
            self.assertEqual(_meta[7] - _meta[6], 400)                  # delta survives 13 bits

            # f_write inherits the ttl on a plain rewrite and ttl=0 clears it
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'exp3', 2, overwrite=True))

            self.assertEqual(jdb.keys['exp3'][8], 45)
            self.assertEqual(jdb.keys['exp3'][11], str(old_date))       # creation date untouched
            with jdb.open() as fp:
                self.assertTrue(jdb.f_write(fp, 'exp3', 3, ttl=0, overwrite=True))

            self.assertEqual(jdb.keys['exp3'][8], 0)
            self.assertFalse(jdb.keys['exp3'][9] & expire)

            # a group hides nothing: ttl routes into the child the way other flags do
            egrp = jdb.add_group('egrp')
            egrp['g1'] = 1
            self.assertEqual(jdb.set_key_flags('egrp:::g1', ttl=9), {'egrp:::g1': (expire, 9)})
            self.assertEqual(egrp.get_key_flags('g1'), {'g1': (expire, 9)})
            self.assertEqual(jdb.set_key_flags('egrp:::g1', ttl=0), {'egrp:::g1': (0, 0)})
            del jdb['egrp']

            for _k in ('exp', 'exp2', 'exp3'):
                del jdb[_k]

            self.assertEqual(jdb.unremove(['exp', 'exp2', 'exp3']).keys() | set(), {'exp', 'exp2', 'exp3'})
            jdb.set_key_flags(['exp2'], '-c-0')
            for _k in ('exp', 'exp2', 'exp3'):
                del jdb[_k]

            # ---------------- an expired record reads as gone, everywhere ----------------
            today = dt.date.today()
            _ago = lambda n: today - dt.timedelta(days=n)
            with jdb.open() as _fp:
                jdb.f_write(_fp, 'x_live', 1, ttl=30)
                jdb.f_write(_fp, 'x_edge', 2, cdays=_ago(5),  mdays=_ago(5),  ttl=5)
                jdb.f_write(_fp, 'x_dead', 3, cdays=_ago(10), mdays=_ago(9), ttl=5)
                jdb.f_write(_fp, 'x_none', 4)
                jdb.f_write(_fp, 'x_long', 5, cdays=_ago(1000*365), mdays=_ago(15), ttl=10)

            ret = jdb.show(with_date=True, key_flags='+e')
            self.assertEqual(set(ret), {'x_live', 'x_edge'})

            # the metadata view shows it, and says why -- check before any read,
            # since reading an expired record is what queues it for deletion
            ret = jdb.keys.get_flags('x_dead')
            self.assertEqual(ret['x_dead'][1], 5)
            self.assertTrue(ret['x_dead'][0] & expire)
            self.assertEqual(dict(jdb.keys.item_iter('x_dead', with_expired=False)), {})
            ret = jdb.keys['x_dead']
            self.assertEqual(ret[-1], str(_ago(10)))
            self.assertEqual(ret[-2], str(_ago(9)))

            ret = jdb.get_key_flags('x_long')
            self.assertEqual(ret['x_long'][1], 10)
            self.assertTrue(ret['x_long'][0] & expire)
            ret = jdb.keys['x_long']
            self.assertEqual(ret[-1], str(_ago(15))) # overflow check
            self.assertEqual(ret[-2], str(_ago(15)))

            # ttl counts days remaining, so a record whose last day is today lives
            self.assertEqual(jdb['x_edge'], 2)
            self.assertEqual(jdb.get('x_dead', 'GONE'), 'GONE')
            self.assertRaises(KeyError, lambda: jdb['x_dead'])
            self.assertFalse('x_dead' in jdb)
            self.assertFalse({'x_live', 'x_dead'} in jdb)
            self.assertTrue({'x_live', 'x_edge'} in jdb)

            # every value view agrees with the single-key read
            self.assertNotIn('x_dead', dict(jdb.items()))
            self.assertNotIn('x_dead', jdb[:])
            self.assertNotIn('x_dead', jdb[lambda k: True])
            self.assertNotIn('x_dead', jdb['x_live', 'x_dead'])
            self.assertNotIn('x_dead', jdb.find(''))
            self.assertEqual(len(jdb[:dt.date.today() + dt.timedelta(days=1)]), len(dict(jdb.items())))

            # reading it queued the row; open() dropped it on the way out
            self.assertEqual(dict(jdb.keys.item_iter('x_dead')), {})
            self.assertEqual(sorted(k for k in dict(jdb.items()) if k.startswith('x_')), ['x_edge', 'x_live', 'x_none'])
            self.assertEqual(len(jdb), len(dict(jdb.items()))) # len() agrees again

            # a cached value must not outlive the record it came from
            self.assertEqual(jdb['x_live'], 1)
            with jdb.open() as _fp:
                jdb.f_write(_fp, 'x_live', 9, cdays=_ago(10), mdays=_ago(10), ttl=5, overwrite=True)

            self.assertEqual(jdb.get('x_live', 'GONE'), 'GONE')

            # the f_open/f_close pair drops expired rows too, not just open()
            with jdb.open() as _fp:
                jdb.f_write(_fp, 'x_fc', 1, cdays=_ago(10), mdays=_ago(10), ttl=5)

            _fp = jdb.f_open(read_only=False)
            try:
                self.assertEqual(jdb.f_read(_fp, 'x_fc', 'GONE'), 'GONE')
            finally:
                jdb.f_close()

            self.assertEqual(dict(jdb.keys.item_iter('x_fc')), {})
            jdb.f_close() # without a matching f_open: must not raise

            # recycle() sheds expired rows even with nothing ever reading them
            with jdb.open() as _fp:
                jdb.f_write(_fp, 'x_rec', 1, cdays=_ago(10), mdays=_ago(10), ttl=5)

            self.assertIn('x_rec', dict(jdb.keys.item_iter(None)))
            jdb.recycle(verbose=False)
            self.assertEqual(dict(jdb.keys.item_iter('x_rec')), {})

            for _k in ('x_edge', 'x_none'):
                del jdb[_k]

            # ---------------- teardown: unlock everything ----------------
            jdb.keys.set_flags(None, read_only=False, append_only=False, no_cache=False, no_revert=False)
            for _key, _meta in jdb.keys.items():
                self.assertEqual(JKeyFlag(_meta[9]) & ~JKeyFlag.GROUP, JKeyFlag(0), _key)

            jdb.remove(jdb)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(dict(jdb.keys.item_iter(None, with_hidden=True)), {})

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_graph(self):
        nodes = {
            'A': {'name': 'Alice', 'age': 25, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
            'B': {'name': 'Bob', 'age': 30, 'role': 'developer', 'tags': ['javascript', 'web']},
            'C': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
            'D': {'name': 'Diana', 'age': 40, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
        }

        edges = {
            ('A', 'B', True) : {'weight':1.},
            ('B', 'C', True) : {'weight':2.},
            ('A', 'C', True) : {'weight':4.},
            ('C', 'D', True) : {'weight':1.},
        }

        def build(db, edges, nodes=()):
            db -= db
            with db.open(read_only=False) as fp:
                for n in nodes:
                    db.f_add_node(fp, n)

                for spec in edges:
                    u, v, directed = spec[0], spec[1], spec[2]
                    kw = spec[3] if len(spec) > 3 else {}
                    db.f_add_edge(fp, u, v, directed=directed, **kw)

        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            db = GraphDb(jdb, key_limit=jdb.key_limit, cache_limit=cache_limit)
            jmem['users'] = db
            jdb['key1'] = 0
            for node_id,props in nodes.items():
                self.assertTrue(db.add_node(node_id, **props))
                self.assertEqual(db.get_node(node_id), props)

            for (u,v,directed),props in edges.items():
                self.assertTrue(db.add_edge(u, v, directed, **props))
                self.assertEqual(db.get_edge(u, v, directed), props)

            with db.open() as fp:
                for node_id in nodes:
                    self.assertTrue(db.f_has_node(fp, node_id))
                    db.f_remove_node(fp, node_id)

                for node_id,props in nodes.items():
                    self.assertFalse(db.f_has_node(fp, node_id))
                    self.assertTrue(db.f_add_node(fp, node_id, **props))
                    self.assertTrue(db.f_has_node(fp, node_id))
                    self.assertEqual(db.f_get_node(fp, node_id), props)

                for (u,v,directed),props in edges.items():
                    self.assertFalse(db.f_has_edge(fp, u, v, directed))
                    self.assertTrue(db.f_add_edge(fp, u, v, directed, **props))
                    self.assertTrue(db.f_has_edge(fp, u, v, directed))
                    self.assertEqual(db.f_get_edge(fp, u, v, directed), props)

            self.assertTrue(db.has_node('A'))
            self.assertFalse(db.has_node('E'))
            self.assertEqual(db.get_node('A')['age'], nodes['A']['age'])
            self.assertEqual(db.get_node('B')['role'], 'developer')

            self.assertEqual(db.get_edge('A', 'B', directed=True)['weight'], 1.)
            self.assertEqual(db.get_edge('B', 'C', directed=True)['weight'], 2.)
            self.assertEqual(db.get_edge('B', 'D', directed=True), None)
            self.assertEqual(db.get_edge('B', 'C', directed=False), None)

            self.assertTrue(db.add_node('B', role='user'))
            self.assertTrue(db.add_node('C', role='user'))

            self.assertEqual({k for k,v in db.nodes()}, {'A','B','C','D'})
            self.assertEqual(sum(1 for k in db.edges()), 4)
            self.assertEqual(db.number_of_edges(), 4)
            self.assertEqual(db.number_of_nodes(), 4)

            self.assertIn('B', db.successors('A'))
            self.assertIn('C', db.successors('A'))
            self.assertIn('A', db.predecessors('B'))
            self.assertNotIn('B', db.predecessors('A'))

            self.assertFalse(db.is_cyclic())

            topo_order = db.topological_sort() #???
            self.assertEqual(len(topo_order), 4)
            self.assertTrue(topo_order.index('A') < topo_order.index('B'))
            self.assertTrue(topo_order.index('B') < topo_order.index('C'))

            dfs_path = db.dfs_traverse('A')
            self.assertEqual(set(dfs_path), {'A', 'B', 'C', 'D'})

            dist, path = db.dijkstra_shortest_path('A', 'D', weight_key='weight')
            self.assertEqual(dist, 4.)
            self.assertEqual(path, ['A', 'B', 'C', 'D'])

            path = db.bfs_shortest_path('A', 'D')
            self.assertEqual(path, ['A', 'C', 'D'])

            # A->B->C->D->A
            db.add_edge('D', 'A', directed=True)
            self.assertTrue(db.is_cyclic())

            db.remove_edge('D', 'A', directed=True)
            self.assertFalse(db.is_cyclic())

            db.add_node('E', type='island')
            db.add_node('F', type='island')
            db.add_edge('E', 'F', directed=False, relation='peer', weight=2.)
            db.add_edge('B', 'C', directed=True, relation='peer')

            self.assertIn('E', db.neighbors('F'))
            self.assertIn('F', db.neighbors('E'))

            weight = db.get_edge('E', 'F', directed=False)['weight']
            db.boost_edge_weights(relation_type='peer', boost_value=4.)
            self.assertEqual(db.get_edge('E', 'F', directed=False)['weight'], weight+4)
            self.assertEqual(db.get_edge('B', 'C', directed=True)['weight'], weight+4)

            today = dt.date.today()
            db.add_temporal_edge('E', 'F', directed=False, expire_days=f'{today} {today+dt.timedelta(days=7)}')
            res = db[dt.date.today()+dt.timedelta(days=2):]
            self.assertEqual(set(res), {'E:E:-:F:'})

            components = db.connected_components()
            self.assertEqual(len(components), 2)

            comp_e = next(comp for comp in components if 'E' in comp)
            self.assertEqual(set(comp_e), {'E', 'F'})

            node = Query()
            res = db.find_nodes((node.age >= 30) & (node.role == 'user'))
            self.assertEqual(set(res), {'B', 'C'})

            edge = Query()
            res = db.find_edges(edge.weight.between(2.5, 4.))
            self.assertEqual(set(res), {('A', '>', 'C')})

            res = db.show(node.weight > 0., with_date=1, sort=node._date)
            self.assertEqual(len(res), 5)

            res = db.degree('C')
            self.assertEqual(res, {'in':2, 'out':1, 'total':3, 'undirected':0})

            db.remove_node('C')
            self.assertFalse(db.has_node('C'))
            self.assertNotIn('C', db.successors('A'))
            self.assertNotIn('C', db.successors('B'))
            self.assertNotIn('C', db.predecessors('D'))
            self.assertEqual(len(db.successors('B')), 0)

            # only show nodes
            res = db.show(db.NODE_RE)
            self.assertEqual(len(res), 5)

            # only show edges
            res = db.show(db.EDGE_RE, with_date=1, sort=node._date.last())
            self.assertGreaterEqual(len(res), 2)

            # only show adjacency
            res = db.show(db.ADJ_RE, with_date=1, sort=node._id, with_hidden=True)
            self.assertGreaterEqual(len(res), 4)

            res = dict(db.iter_adjs())
            self.assertEqual(set(res), {'A', 'B', 'E', 'F'})

            for node_id in nodes:
                db.remove_node(node_id)

            for node_id in ('E', 'F'):
                db.remove_node(node_id)

            jdb -= jdb
            self.assertTrue(db.add_node('A', x=1))            # created
            self.assertFalse(db.add_node('A', x=1))           # no-op merge
            self.assertTrue(db.add_node('A', y=2))            # merge adds key
            self.assertEqual(db.get_node('A'), {'x': 1, 'y': 2})

            self.assertTrue(db.add_edge('A', 'B', directed=True, w=1))   # created (+ node B)
            self.assertFalse(db.add_edge('A', 'B', directed=True, w=1))  # no-op
            self.assertTrue(db.add_edge('A', 'B', directed=True, w=9))   # merge
            self.assertEqual(db.get_edge('A', 'B', directed=True)['w'], 9)

            # self-loop must be rejected
            with self.assertRaises(KeyError):
                db.add_edge('A', 'A', directed=True)

            with self.assertRaises(KeyError):
                db.add_edge('N:A:', 'B')

            with self.assertRaises(KeyError):
                db.add_node('N:Z:')

            # =====================================================
            # get_edge undirected endpoint-order independence
            # =====================================================
            build(db, [('F', 'E', False, {'weight': 3})])
            self.assertEqual(db.get_edge('F', 'E', directed=False)['weight'], 3)
            self.assertEqual(db.get_edge('E', 'F', directed=False)['weight'], 3)  # order agnostic
            self.assertIsNone(db.get_edge('E', 'F', directed=True))               # not a directed edge

            # =====================================================
            # remove_edge / remove_node return values and missing keys
            # =====================================================
            build(db, [('A', 'B', True, {'w': 5})])
            res = db.remove_edge('A', 'B', directed=True)
            self.assertIn('E:A:>:B:', res)
            self.assertIsNone(db.get_edge('A', 'B', directed=True))
            self.assertEqual(db.remove_edge('X', 'Y', directed=True), {})  # missing edge

            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'B', False)])
            res = db.remove_node('B')
            self.assertIn('N:B:', res)
            self.assertGreaterEqual(len(res), 3)            # node + its incident edges
            self.assertFalse(db.has_node('B'))
            self.assertEqual(db.remove_node('NOPE'), {})  # missing node

            # =====================================================
            # degree: mixed directions and isolated node
            # =====================================================
            build(db, [('A', 'B', True), ('C', 'A', True), ('A', 'D', False)], nodes=('ISO',))
            self.assertEqual(db.degree('A'), {'in': 1, 'out': 1, 'undirected': 1, 'total': 3})
            self.assertEqual(db.degree('ISO'), {'in': 0, 'out': 0, 'undirected': 0, 'total': 0})

            # =====================================================
            # undirected edge appears in BOTH successors and predecessors
            # =====================================================
            build(db, [('X', 'Y', False, {'r': 'peer'})])
            self.assertIn('Y', db.successors('X'))
            self.assertIn('X', db.successors('Y'))
            self.assertIn('Y', db.predecessors('X'))
            self.assertIn('X', db.predecessors('Y'))
            self.assertEqual(db.neighbors('X'), {'Y'})

            # =====================================================
            # CYCLE VARIETIES  (the heart of the robustness suite)
            # =====================================================
            # directed 2-cycle
            build(db, [('A', 'B', True), ('B', 'A', True)])
            self.assertTrue(db.is_cyclic())

            # directed 3-cycle
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True)])
            self.assertTrue(db.is_cyclic())

            # single undirected edge is NOT a cycle
            build(db, [('A', 'B', False)])
            self.assertFalse(db.is_cyclic())

            # undirected chain is NOT a cycle
            build(db, [('A', 'B', False), ('B', 'C', False)])
            self.assertFalse(db.is_cyclic())

            # undirected triangle IS a cycle
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)])
            self.assertTrue(db.is_cyclic())

            # undirected square IS a cycle
            build(db, [('A', 'B', False), ('B', 'C', False), ('C', 'D', False), ('D', 'A', False)])
            self.assertTrue(db.is_cyclic())

            # undirected tree is NOT a cycle
            build(db, [('A', 'B', False), ('A', 'C', False), ('B', 'D', False), ('B', 'E', False)])
            self.assertFalse(db.is_cyclic())

            # undirected star is NOT a cycle
            build(db, [('H', 'B', False), ('H', 'C', False), ('H', 'D', False)])
            self.assertFalse(db.is_cyclic())

            # directed diamond DAG is NOT a cycle
            build(db, [('A', 'B', True), ('A', 'C', True), ('B', 'D', True), ('C', 'D', True)])
            self.assertFalse(db.is_cyclic())

            # cycle buried inside a larger graph  (A->B, B->C->D->B)
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'D', True), ('D', 'B', True)])
            self.assertTrue(db.is_cyclic())

            # two components, only one cyclic
            build(db, [('A', 'B', False), ('X', 'Y', True), ('Y', 'X', True)])
            self.assertTrue(db.is_cyclic())

            # mixed directed + undirected between the same pair is a cycle
            build(db, [('A', 'B', True), ('B', 'A', False)])
            self.assertTrue(db.is_cyclic())

            # =====================================================
            # topological_sort: raises on cycle, valid on DAG
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True)])
            with self.assertRaises(ValueError):
                db.topological_sort()

            build(db, [('A', 'B', True), ('A', 'C', True), ('B', 'D', True), ('C', 'D', True)])
            res = db.show()
            self.assertGreaterEqual(len(res), 4)

            order = db.topological_sort()
            self.assertEqual(set(order), {'A', 'B', 'C', 'D'})
            pos = {n: i for i, n in enumerate(order)}
            self.assertTrue(pos['A'] < pos['B'] < pos['D'])
            self.assertTrue(pos['A'] < pos['C'] < pos['D'])

            # =====================================================
            # SHORTEST PATH edge cases
            # =====================================================
            build(db, [('A', 'B', True, {'weight': 1.}), ('B', 'C', True, {'weight': 2.}),
                   ('A', 'C', True, {'weight': 4.}), ('C', 'D', True, {'weight': 1.})])

            res = db.show()
            self.assertGreaterEqual(len(res), 4)
            # unreachable (directed backward)
            self.assertEqual(db.bfs_shortest_path('D', 'A'), [])
            self.assertEqual(db.dijkstra_shortest_path('D', 'A'), (float('inf'), []))
            # missing node
            self.assertEqual(db.bfs_shortest_path('A', 'ZZZ'), [])
            self.assertEqual(db.dijkstra_shortest_path('ZZZ', 'A'), (float('inf'), []))
            # start == end
            self.assertEqual(db.bfs_shortest_path('A', 'A'), ['A'])
            self.assertEqual(db.dijkstra_shortest_path('A', 'A'), (0, ['A']))
            # dijkstra prefers cheaper multi-hop over expensive direct edge
            self.assertEqual(db.dijkstra_shortest_path('A', 'C', weight_key='weight'), (3., ['A', 'B', 'C']))
            # bfs prefers fewest hops (direct) regardless of weight
            self.assertEqual(db.bfs_shortest_path('A', 'C'), ['A', 'C'])

            # undirected shortest path works both directions
            build(db, [('A', 'B', False, {'weight': 2.}), ('B', 'C', False, {'weight': 3.})])
            self.assertEqual(db.bfs_shortest_path('C', 'A'), ['C', 'B', 'A'])
            self.assertEqual(db.dijkstra_shortest_path('C', 'A', weight_key='weight'), (5., ['C', 'B', 'A']))

            # =====================================================
            # dfs_traverse: missing start, shared visited, forward-only, cycle-safe
            # =====================================================
            build(db, [('A', 'B', True)])
            self.assertEqual(db.dfs_traverse('NOPE'), [])

            build(db, [('A', 'B', True), ('A', 'C', True)])
            shared = {'B'}
            got = db.dfs_traverse('A', shared)
            self.assertNotIn('B', got)
            self.assertEqual(set(got), {'A', 'C'})

            build(db, [('A', 'B', True), ('X', 'A', True)])       # X->A must not be reached from A
            self.assertEqual(set(db.dfs_traverse('A')), {'A', 'B'})

            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True)])  # cycle must terminate
            self.assertEqual(set(db.dfs_traverse('A')), {'A', 'B', 'C'})

            # =====================================================
            # connected_components: isolated node forms its own component
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', False)], nodes=('ISO',))
            comps = db.connected_components()
            norm = sorted(sorted(c) for c in comps)
            self.assertEqual(norm, [['A', 'B', 'C'], ['ISO']])
            # directed edges still weakly connect
            build(db, [('A', 'B', True), ('C', 'B', True)])
            self.assertEqual(len(db.connected_components()), 1)

            # =====================================================
            # add_temporal_edge renewal (second call must keep the edge alive)
            # =====================================================
            db -= db
            today = dt.date.today()
            span1 = f'{today} {today + dt.timedelta(days=7)}'
            span2 = f'{today} {today + dt.timedelta(days=14)}'
            with self.assertRaises(KeyError):
                db.add_temporal_edge('E', 'E', directed=False, expire_days=span1)

            with self.assertRaises(KeyError):
                db.add_temporal_edge('N:E:', 'N:F:', directed=False, expire_days=span1)

            self.assertTrue(db.add_temporal_edge('E', 'F', directed=False, expire_days=span1))
            self.assertTrue(db.add_temporal_edge('E', 'F', directed=False, expire_days=span2))  # renewal
            self.assertIsNotNone(db.get_edge('E', 'F', directed=False))

            # =====================================================
            # k_hop_neighbors: directed chain + branch
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'D', True), ('A', 'E', True)])
            self.assertEqual(db.k_hop_neighbors('A', 1), {'B': 1, 'E': 1})
            self.assertEqual(db.k_hop_neighbors('A', 2), {'B': 1, 'E': 1, 'C': 2})
            self.assertEqual(db.k_hop_neighbors('A', 3), {'B': 1, 'E': 1, 'C': 2, 'D': 3})
            self.assertEqual(db.k_hop_neighbors('A', 10), {'B': 1, 'E': 1, 'C': 2, 'D': 3})  # stops early
            self.assertEqual(db.k_hop_neighbors('D', 1), {})                                  # no out-edges
            self.assertEqual(db.k_hop_neighbors('D', 2, direction='in'), {'C': 1, 'B': 2})
            self.assertEqual(db.k_hop_neighbors('ZZZ', 2), {})                                # missing node
            self.assertEqual(db.k_hop_neighbors('A', 0), {})                                  # k=0

            # =====================================================
            # k_hop_neighbors: undirected edges count in both directions
            # =====================================================
            build(db, [('A', 'B', False), ('B', 'C', True)])
            self.assertEqual(db.k_hop_neighbors('A', 1), {'B': 1})
            self.assertEqual(db.k_hop_neighbors('A', 2), {'B': 1, 'C': 2})
            self.assertEqual(db.k_hop_neighbors('C', 1), {})                       # B->C directed, C has no out
            self.assertEqual(db.k_hop_neighbors('C', 1, direction='in'), {'B': 1})
            self.assertEqual(db.k_hop_neighbors('C', 2, direction='in'), {'B': 1, 'A': 2})
            self.assertEqual(db.k_hop_neighbors('A', 2, direction='both'), {'B': 1, 'C': 2})

            # =====================================================
            # ego_graph: node/edge set is the correct induced subgraph
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('A', 'C', True)], nodes=('ISO',))
            ego = db.ego_graph('A', 1, direction='out')
            self.assertEqual(set(ego['nodes']), {'A', 'B', 'C'})
            # B and C are both in the 1-hop set, so the B->C edge is included too
            self.assertEqual(set(ego['edges']), {('A', '>', 'B'), ('A', '>', 'C'), ('B', '>', 'C')})

            ego_in = db.ego_graph('C', 1, direction='in')
            self.assertEqual(set(ego_in['nodes']), {'A', 'B', 'C'})

            self.assertEqual(db.ego_graph('ISO', 1)['nodes'], {'ISO': {}})
            self.assertEqual(db.ego_graph('ISO', 1)['edges'], {})
            self.assertEqual(db.ego_graph('ZZZ', 1), {'nodes': {}, 'edges': {}})

            # radius 1 excludes a node two hops away
            build(db, [('A', 'B', True), ('B', 'D', True), ('X', 'D', True)])
            ego2 = db.ego_graph('A', 1, direction='out')
            self.assertEqual(set(ego2['nodes']), {'A', 'B'})
            self.assertEqual(set(ego2['edges']), {('A', '>', 'B')})

            # k=0 is just the center node, no edges
            build(db, [('A', 'B', True)])
            ego0 = db.ego_graph('A', 0)
            self.assertEqual(set(ego0['nodes']), {'A'})
            self.assertEqual(ego0['edges'], {})

            # edge properties are preserved in the ego subgraph
            build(db, [('A', 'B', True, {'w': 7})])
            ego3 = db.ego_graph('A', 1)
            self.assertEqual(ego3['edges'][('A', '>', 'B')], {'w': 7})

            # =====================================================
            # subgraph(nodes): induced subgraph over an explicit node set
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('A', 'C', True), ('C', 'D', True)], nodes=('ISO',))
            sg = db.subgraph({'A', 'B', 'C'})
            self.assertEqual(set(sg['nodes']), {'A', 'B', 'C'})
            self.assertEqual(set(sg['edges']), {('A', '>', 'B'), ('A', '>', 'C'), ('B', '>', 'C')})
            self.assertNotIn(('C', '>', 'D'), sg['edges'])          # D excluded from the set

            sg2 = db.subgraph({'A', 'ZZZ', 'ISO'})                  # missing id silently skipped
            self.assertEqual(set(sg2['nodes']), {'A', 'ISO'})
            self.assertEqual(sg2['edges'], {})                       # A and ISO are disconnected

            self.assertEqual(db.subgraph([]), {'nodes': {}, 'edges': {}})
            self.assertEqual(db.subgraph(['ZZZ']), {'nodes': {}, 'edges': {}})

            # =====================================================
            # export_graph() / import_graph(): backup, migration, interop
            # =====================================================
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', False, {'w': 2})], nodes=('ISO',))
            db.add_node('A', name='alice')

            exp = db.export_graph()
            self.assertEqual(set(exp['nodes']), {'A', 'B', 'C', 'ISO'})
            self.assertEqual(len(exp['edges']), 2)
            self.assertTrue(any(e['u'] == 'A' and e['v'] == 'B' and e['directed'] is True
                                and e['properties'] == {'w': 1} for e in exp['edges']))
            self.assertTrue(any(e['directed'] is False and e['properties'] == {'w': 2}
                                for e in exp['edges']))

            # round-trip into a fresh, independent graph
            db_fresh = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            r = db_fresh.import_graph(exp)
            self.assertEqual(r, {'nodes': 4, 'edges': 2})
            self.assertEqual(db_fresh.get_node('A'), db.get_node('A'))
            self.assertEqual(db_fresh.get_edge('A', 'B', directed=True), {'w': 1})
            self.assertEqual(db_fresh.get_edge('B', 'C', directed=False), {'w': 2})
            self.assertTrue(db_fresh.has_node('ISO'))
            self.assertEqual(db_fresh.verify_index(), {'missing': [], 'orphan': [], 'counters':{}})

            # export a subset via the nodes= filter
            exp_sub = db.export_graph(nodes={'A', 'B'})
            self.assertEqual(set(exp_sub['nodes']), {'A', 'B'})
            self.assertEqual(len(exp_sub['edges']), 1)
            self.assertEqual(exp_sub['edges'][0]['u'], 'A')
            self.assertEqual(exp_sub['edges'][0]['v'], 'B')

            # import into a non-empty graph merges properties on existing nodes
            db_existing = GraphDb(data_type=jdb.data_type)
            db_existing.add_node('A', extra='keep')
            db_existing.import_graph(exp)
            self.assertEqual(db_existing.get_node('A'), {'extra': 'keep', 'name': 'alice'})


            # =====================================================
            # to_networkx() / from_networkx(): interop with networkx
            # (skipped entirely if networkx is not installed)
            # =====================================================
            # all-directed -> exactly nx.DiGraph
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', True, {'w': 2})])
            db.add_node('A', name='alice')
            G = db.to_networkx()
            self.assertIs(type(G), nx.DiGraph)
            self.assertEqual(set(G.nodes), {'A', 'B', 'C'})
            self.assertEqual(G.nodes['A']['name'], 'alice')
            self.assertEqual(G['A']['B']['w'], 1)
            self.assertFalse(G.has_edge('B', 'A'))              # directed, no reciprocal

            # all-undirected -> exactly nx.Graph
            build(db, [('X', 'Y', False, {'w': 5}), ('Y', 'Z', False)])
            G2 = db.to_networkx()
            self.assertIs(type(G2), nx.Graph)
            self.assertEqual(G2['X']['Y']['w'], 5)

            # mixed -> nx.DiGraph, undirected edges become a reciprocal pair
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', False, {'w': 2})])
            G3 = db.to_networkx()
            self.assertIs(type(G3), nx.DiGraph)
            self.assertTrue(G3.has_edge('A', 'B'))
            self.assertFalse(G3.has_edge('B', 'A'))              # directed stays one-way
            self.assertTrue(G3.has_edge('B', 'C') and G3.has_edge('C', 'B'))  # undirected mirrored

            # subset conversion via nodes=
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'D', True)])
            Gs = db.to_networkx(nodes={'A', 'B'})
            self.assertEqual(set(Gs.nodes), {'A', 'B'})
            self.assertEqual(set(Gs.edges), {('A', 'B')})

            # from_networkx: DiGraph -> directed edges
            Gd = nx.DiGraph()
            Gd.add_node('A', name='alice')
            Gd.add_edge('A', 'B', w=1)
            db_nx1 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            r_nx1 = db_nx1.from_networkx(Gd)
            self.assertEqual(r_nx1, {'nodes': 2, 'edges': 1})
            self.assertEqual(db_nx1.get_node('A'), {'name': 'alice'})
            self.assertEqual(db_nx1.get_edge('A', 'B', directed=True), {'w': 1})
            self.assertIsNone(db_nx1.get_edge('A', 'B', directed=False))

            # from_networkx: Graph -> undirected edges
            Gu = nx.Graph()
            Gu.add_edge('X', 'Y', w=5)
            db_nx2 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            db_nx2.from_networkx(Gu)
            self.assertEqual(db_nx2.get_edge('X', 'Y', directed=False), {'w': 5})
            self.assertEqual(db_nx2.get_edge('Y', 'X', directed=False), {'w': 5})  # order agnostic

            # full round trip is faithful for a purely directed graph
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', True, {'w': 2})])
            Grt = db.to_networkx()
            db_nx3 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            db_nx3.from_networkx(Grt)
            self.assertEqual(db_nx3.neighbors('A'), db.neighbors('A'))
            self.assertEqual(db_nx3.get_edge('A', 'B', directed=True), db.get_edge('A', 'B', directed=True))

            # full round trip is faithful for a purely undirected graph
            build(db, [('X', 'Y', False, {'w': 9})])
            Gru = db.to_networkx()
            db_nx4 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            db_nx4.from_networkx(Gru)
            self.assertEqual(db_nx4.get_edge('X', 'Y', directed=False), db.get_edge('X', 'Y', directed=False))
            self.assertIsNone(db_nx4.get_edge('X', 'Y', directed=True))

            # from_networkx uses f_add_node/f_add_edge directly (single write
            # transaction), but must still reject the same things add_node/
            # add_edge would: self-loops and ':' in an id
            G_selfloop = nx.DiGraph()
            G_selfloop.add_edge('A', 'A', w=1)
            db_nx5 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            with self.assertRaises(KeyError):
                db_nx5.from_networkx(G_selfloop)

            G_bad_node = nx.DiGraph()
            G_bad_node.add_node('bad:id')
            db_nx6 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            with self.assertRaises(KeyError):
                db_nx6.from_networkx(G_bad_node)

            G_bad_edge = nx.DiGraph()
            G_bad_edge.add_edge('A', 'bad:v')
            db_nx7 = GraphDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, cache_limit=cache_limit)
            with self.assertRaises(KeyError):
                db_nx7.from_networkx(G_bad_edge)

            # =====================================================
            # direction-filtered traversal (bfs_shortest_path / dfs_traverse)
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True)])
            self.assertEqual(db.bfs_shortest_path('C', 'A'), [])                           # default 'out'
            self.assertEqual(db.bfs_shortest_path('C', 'A', direction='both'), ['C', 'B', 'A'])
            self.assertEqual(db.bfs_shortest_path('C', 'A', direction='in'), ['C', 'B', 'A'])
            self.assertEqual(db.bfs_shortest_path('A', 'C'), ['A', 'B', 'C'])              # unaffected

            build(db, [('A', 'B', True), ('X', 'A', True)])
            self.assertEqual(set(db.dfs_traverse('A')), {'A', 'B'})                        # default 'out'
            self.assertEqual(set(db.dfs_traverse('A', direction='both')), {'A', 'B', 'X'})
            self.assertEqual(set(db.dfs_traverse('A', direction='in')), {'A', 'X'})

            # =====================================================
            # property-filtered traversal (edge_filter)
            # =====================================================
            build(db, [('A', 'B', True, {'w': 1}), ('A', 'C', True, {'w': 9})])
            light = lambda p: p.get('w', 0) < 5
            self.assertEqual(set(db.dfs_traverse('A', edge_filter=light)), {'A', 'B'})
            self.assertEqual(db.bfs_shortest_path('A', 'C', edge_filter=light), [])
            self.assertEqual(db.bfs_shortest_path('A', 'B', edge_filter=light), ['A', 'B'])

            # direction + edge_filter combined
            build(db, [('A', 'B', True, {'w': 1}), ('C', 'B', True, {'w': 9})])
            self.assertEqual(db.bfs_shortest_path('B', 'A', direction='in', edge_filter=light),
                             ['B', 'A'])
            self.assertEqual(db.bfs_shortest_path('B', 'C', direction='in', edge_filter=light), [])

            # =====================================================
            # centrality: degree_centrality
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('A', 'C', True)])
            dc = db.degree_centrality()
            self.assertAlmostEqual(dc['A'], 1.0)   # out 2 / (3-1)
            self.assertAlmostEqual(dc['B'], 1.0)   # in1 + out1
            self.assertAlmostEqual(dc['C'], 1.0)   # in 2

            build(db, [('A', 'B', True)], nodes=('ISO',))
            self.assertEqual(db.degree_centrality()['ISO'], 0.0)

            # =====================================================
            # centrality: closeness_centrality
            # =====================================================
            # nx's own reference example: undirected graph with a documented
            # exact expected result
            build(db, [('n0', 'n1', False), ('n0', 'n2', False), ('n0', 'n3', False),
                   ('n1', 'n2', False), ('n1', 'n3', False)])
            cc = db.closeness_centrality()
            self.assertAlmostEqual(cc['n0'], 1.0)
            self.assertAlmostEqual(cc['n1'], 1.0)
            self.assertAlmostEqual(cc['n2'], 0.75)
            self.assertAlmostEqual(cc['n3'], 0.75)

            # empty graph / single node
            build(db, [])
            self.assertEqual(db.closeness_centrality(), {})

            db -= db
            db.add_node('A')
            self.assertEqual(db.closeness_centrality(), {'A': 0.0})

            # directed graph, default direction='in': a source node (no
            # predecessors) has closeness 0 — nobody can reach it
            build(db, [('A', 'B', True), ('A', 'C', True)])
            cc2 = db.closeness_centrality()
            self.assertEqual(cc2['A'], 0.0)
            self.assertGreater(cc2['B'], 0.0)
            self.assertGreater(cc2['C'], 0.0)

            # isolated node among otherwise-connected nodes scores 0
            build(db, [('A', 'B', True), ('B', 'C', True)], nodes=('ISO',))
            self.assertEqual(db.closeness_centrality()['ISO'], 0.0)

            # star graph: center has strictly higher closeness than a leaf
            build(db, [('H', 'B', False), ('H', 'C', False), ('H', 'D', False)])
            cc3 = db.closeness_centrality()
            self.assertGreater(cc3['H'], cc3['B'])

            # u=: single-node query returns a float, matching cc[u]
            build(db, [('n0', 'n1', False), ('n0', 'n2', False), ('n0', 'n3', False),
                   ('n1', 'n2', False), ('n1', 'n3', False)])
            single = db.closeness_centrality(u='n2')
            self.assertIsInstance(single, float)
            self.assertAlmostEqual(single, 0.75)

            # wf_improved=False: raw reciprocal of average distance, no
            # component-size scaling (differs from the default when the
            # graph has more than one component)
            build(db, [('A', 'B', False)], nodes=('X', 'Y'))
            db.add_edge('X', 'Y', directed=False)
            cc_wf = db.closeness_centrality(wf_improved=True)
            cc_raw = db.closeness_centrality(wf_improved=False)
            self.assertNotEqual(cc_wf['A'], cc_raw['A'])
            self.assertAlmostEqual(cc_raw['A'], 1.0)   # within its own 2-node component

            # distance=: weighted closeness via edge weights; missing the
            # attribute on an edge defaults that edge's weight to 1
            build(db, [('A', 'B', False, {'weight': 5}), ('B', 'C', False)])
            cc_w = db.closeness_centrality(distance='weight')
            self.assertTrue(all(0.0 <= v <= 1.0 for v in cc_w.values()))
            # unweighted (hop-count) closeness must differ from weighted here,
            # since A-B costs 5 while B-C costs the default of 1
            cc_unw = db.closeness_centrality()
            self.assertNotAlmostEqual(cc_w['B'], cc_unw['B'])

            # =====================================================
            # Centrality: pagerank
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('A', 'C', True)])
            pr = db.pagerank()
            self.assertAlmostEqual(sum(pr.values()), 1.0, places=5)
            self.assertGreater(pr['C'], pr['A'])   # sink accumulates rank

            # parallel directed + undirected edge between the same pair must
            # not be double-counted (out-neighbor dedupe)
            build(db, [('A', 'B', True), ('B', 'A', False)])
            pr2 = db.pagerank()
            self.assertAlmostEqual(sum(pr2.values()), 1.0, places=5)

            # weight=: rank splits across out-edges in proportion to edge
            # weight (matches networkx's default weight='weight'); missing
            # the property on an edge defaults that edge's weight to 1
            build(db, [('A', 'B', True, {'weight': 5}), ('A', 'C', True)])
            pr3 = db.pagerank(max_iter=300, tol=1e-12)
            self.assertAlmostEqual(sum(pr3.values()), 1.0, places=5)
            self.assertGreater(pr3['B'], pr3['C'])   # B gets the heavier share

            # weight=None: pure structural PageRank, ignoring any weight prop
            pr4 = db.pagerank(weight=None, max_iter=300, tol=1e-12)
            self.assertAlmostEqual(pr4['B'], pr4['C'])
            # =====================================================
            # centrality: betweenness_centrality
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True)])
            bc = db.betweenness_centrality(normalized=False)
            self.assertEqual(bc['B'], 1.0)   # middle node on the only path
            self.assertEqual(bc['A'], 0.0)
            self.assertEqual(bc['C'], 0.0)

            build(db, [('A', 'B', True), ('B', 'C', True), ('A', 'C', True)])
            bc2 = db.betweenness_centrality(normalized=True)
            self.assertTrue(all(0.0 <= v <= 1.0 for v in bc2.values()))

            # =====================================================
            # all_shortest_paths: multiple equal-length paths
            # =====================================================
            build(db, [('A', 'B', True), ('A', 'C', True), ('B', 'D', True), ('C', 'D', True)])
            self.assertEqual(sorted(db.all_shortest_paths('A', 'D')),
                             [['A', 'B', 'D'], ['A', 'C', 'D']])
            self.assertEqual(db.all_shortest_paths('A', 'A'), [['A']])
            self.assertEqual(db.all_shortest_paths('A', 'ZZZ'), [])

            build(db, [('A', 'B', True), ('B', 'C', True)])
            self.assertEqual(db.all_shortest_paths('A', 'C'), [['A', 'B', 'C']])
            self.assertEqual(db.all_shortest_paths('C', 'A'), [])                       # unreachable, default 'out'
            self.assertEqual(db.all_shortest_paths('C', 'A', direction='in'), [['C', 'B', 'A']])

            # edge_filter restricts which paths qualify
            build(db, [('A', 'B', True, {'w': 1}), ('A', 'C', True, {'w': 9})])
            light = lambda p: p.get('w', 0) < 5
            self.assertEqual(db.all_shortest_paths('A', 'B', edge_filter=light), [['A', 'B']])
            self.assertEqual(db.all_shortest_paths('A', 'C', edge_filter=light), [])

            # a direct edge (1 hop) is preferred over any 2-hop alternative
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)])
            self.assertEqual(db.all_shortest_paths('A', 'C'), [['A', 'C']])

            # weight=: minimum-total-weight paths instead of fewest-hop; a
            # longer (more hops) but lighter path can beat a direct heavy edge
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', True, {'w': 1}),
                   ('A', 'C', True, {'w': 5})])
            self.assertEqual(db.all_shortest_paths('A', 'C', weight='w'), [['A', 'B', 'C']])
            # ties at equal minimum weight are all returned
            build(db, [('A', 'B', True, {'w': 2}), ('A', 'C', True, {'w': 1}),
                   ('B', 'D', True, {'w': 1}), ('C', 'D', True, {'w': 2})])
            self.assertEqual(sorted(db.all_shortest_paths('A', 'D', weight='w')),
                             [['A', 'B', 'D'], ['A', 'C', 'D']])
            # missing weight property defaults that edge's weight to 1
            build(db, [('A', 'B', True), ('B', 'C', True, {'w': 2})])
            self.assertEqual(db.all_shortest_paths('A', 'C', weight='w'), [['A', 'B', 'C']])

            # =====================================================
            # #7 strongly_connected_components
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True), ('C', 'D', True)])
            self.assertEqual(sorted(sorted(c) for c in db.strongly_connected_components()), [['A', 'B', 'C'], ['D']])

            build(db, [('A', 'B', True), ('B', 'C', True)])           # DAG -> all singletons
            self.assertEqual(sorted(sorted(c) for c in db.strongly_connected_components()), [['A'], ['B'], ['C']])

            build(db, [('A', 'B', False), ('B', 'C', False)])         # undirected chain -> one SCC
            self.assertEqual(sorted(sorted(c) for c in db.strongly_connected_components()), [['A', 'B', 'C']])

            # every node appears in exactly one component (partition invariant)
            build(db, [('A', 'B', True), ('B', 'A', True), ('C', 'D', True), ('D', 'C', True), ('B', 'C', True)])
            comps = db.strongly_connected_components()
            allnodes = [n for c in comps for n in c]
            self.assertEqual(sorted(allnodes), ['A', 'B', 'C', 'D'])
            self.assertEqual(len(allnodes), len(set(allnodes)))

            # nodes with no edges are singleton components
            build(db, [], nodes=('X', 'Y', 'Z'))
            self.assertEqual(sorted(sorted(c) for c in db.strongly_connected_components()), [['X'], ['Y'], ['Z']])

            # =====================================================
            # verify_index() / reindex(): adjacency-index consistency tools
            # =====================================================
            # a clean graph must report no drift
            build(db, [('A', 'B', True), ('B', 'C', True), ('A', 'C', False)])
            self.assertEqual(db.verify_index(), {'missing': [], 'orphan': [], 'counters':{}})

            # directed edge deleted directly (bypassing remove_edge) leaves
            # a stale adjacency entry on BOTH endpoints
            del db[db._generate_edge_key('A', 'B', True)]
            v = db.verify_index()
            self.assertIn(('A', '>B'), v['orphan'])
            self.assertIn(('B', '<A'), v['orphan'])
            self.assertEqual(v['missing'], [])
            self.assertIn('B', db.neighbors('A'))          # phantom neighbor before repair

            res = db.reindex()
            self.assertGreaterEqual(res['removed'], 1)
            self.assertEqual(db.verify_index(), {'missing': [], 'orphan': [], 'counters':{}})
            self.assertNotIn('B', db.neighbors('A'))       # phantom neighbor gone
            self.assertNotIn('A', db.neighbors('B'))
            self.assertIn('C', db.neighbors('A'))          # surviving edges untouched
            self.assertIn('C', db.neighbors('B'))

            # undirected edge deleted directly: stale entry on both endpoints
            build(db, [('X', 'Y', False), ('Y', 'Z', True)])
            del db[db._generate_edge_key('X', 'Y', False)]
            v2 = db.verify_index()
            self.assertIn(('X', '-Y'), v2['orphan'])
            self.assertIn(('Y', '-X'), v2['orphan'])
            db.reindex()
            self.assertEqual(db.verify_index(), {'missing': [], 'orphan': [], 'counters':{}})
            self.assertNotIn('Y', db.neighbors('X'))
            self.assertIn('Z', db.neighbors('Y'))           # surviving edge untouched

            # an edge key written directly (bypassing add_edge) is detected
            # as 'missing' adjacency rather than 'orphan'
            build(db, [('A', 'B', True)], nodes=('C',))
            db[db._generate_edge_key('A', 'C', True)] = {}
            v3 = db.verify_index()
            self.assertIn(('A', '>C'), v3['missing'])
            self.assertIn(('C', '<A'), v3['missing'])
            self.assertEqual(v3['orphan'], [])
            db.reindex()
            self.assertEqual(db.verify_index(), {'missing': [], 'orphan': [], 'counters':{}})
            self.assertIn('C', db.neighbors('A'))

            del db['N:C:']
            v4 = db.verify_index()
            self.assertNotEqual(v4['counters']['N_NODES'], {})
            db.reindex()
            self.assertEqual(db.verify_index(), {'missing': [], 'orphan': [], 'counters':{}})
            self.assertFalse(db.has_node('C'))

            # =====================================================
            # common_neighbors() / jaccard_coefficient()
            # =====================================================
            # diamond: B and C share the exact same neighbor set {A, D}
            build(db, [('A', 'B', True), ('A', 'C', True), ('B', 'D', True), ('C', 'D', True)])
            self.assertEqual(db.common_neighbors('B', 'C'), {'A', 'D'})
            self.assertEqual(db.jaccard_coefficient('B', 'C'), 1.0)

            # disjoint neighbor sets
            build(db, [('A', 'B', True), ('C', 'D', True)])
            self.assertEqual(db.common_neighbors('A', 'C'), set())
            self.assertEqual(db.jaccard_coefficient('A', 'C'), 0.0)

            # partial overlap: A={B,C}, D={C,E} -> common={C}, union={B,C,E}
            build(db, [('A', 'B', True), ('A', 'C', True), ('D', 'C', True), ('D', 'E', True)])
            self.assertEqual(db.common_neighbors('A', 'D'), {'C'})
            self.assertAlmostEqual(db.jaccard_coefficient('A', 'D'), 1 / 3)

            # both nodes isolated -> jaccard is 0.0 by convention (empty union)
            build(db, [], nodes=('X', 'Y'))
            self.assertEqual(db.common_neighbors('X', 'Y'), set())
            self.assertEqual(db.jaccard_coefficient('X', 'Y'), 0.0)

            # missing node -> empty result, no error raised
            build(db, [('A', 'B', True)])
            self.assertEqual(db.common_neighbors('A', 'ZZZ'), set())
            self.assertEqual(db.jaccard_coefficient('A', 'ZZZ'), 0.0)

            # direction-agnostic, same as get_neighbors: undirected + directed mix
            build(db, [('A', 'B', False), ('C', 'B', True)])
            self.assertEqual(db.common_neighbors('A', 'C'), {'B'})

            # comparing a node with itself: identical sets -> jaccard 1.0
            build(db, [('A', 'B', True), ('A', 'C', True)])
            self.assertEqual(db.common_neighbors('A', 'A'), {'B', 'C'})
            self.assertEqual(db.jaccard_coefficient('A', 'A'), 1.0)

            # =====================================================
            # batch write API
            # =====================================================
            db -= db
            n = db.add_nodes(['A', ('B', {'x': 1}), 'C'])
            self.assertEqual(n, 3)
            self.assertEqual(db.get_node('A'), {})
            self.assertEqual(db.get_node('B'), {'x': 1})

            n2 = db.add_nodes({'X': {'y': 2}, 'Z': {}})
            self.assertEqual(n2, 2)
            self.assertEqual(db.get_node('X'), {'y': 2})

            # merge semantics on re-add
            db -= db
            db.add_nodes([('A', {'a': 1})])
            self.assertEqual(db.add_nodes([('A', {'b': 2})]), 1)   # merge counted
            self.assertEqual(db.get_node('A'), {'a': 1, 'b': 2})
            self.assertEqual(db.add_nodes([('A', {'a': 1, 'b': 2})]), 0)  # no-op not counted

            # validation preserved
            with self.assertRaises(KeyError):
                db.add_nodes(['bad:id'])

            # edges: (u,v) / (u,v,directed) / (u,v,directed,props) all accepted
            db -= db
            n3 = db.add_edges([('A', 'B'), ('B', 'C', False), ('C', 'D', True, {'w': 5})])
            self.assertEqual(n3, 3)
            self.assertEqual(db.get_edge('A', 'B', directed=True), {})
            self.assertEqual(db.get_edge('B', 'C', directed=False), {})
            self.assertEqual(db.get_edge('C', 'D', directed=True), {'w': 5})

            with self.assertRaises(KeyError):
                db.add_edges([('A', 'A')])                          # self-loop
            with self.assertRaises(KeyError):
                db.add_edges([('bad:id', 'X')])                     # invalid id

            # =====================================================
            # weighted_degree(): sum of edge weights, grouped by direction
            # =====================================================
            build(db, [('A', 'B', True, {'weight': 3}), ('C', 'A', True, {'weight': 5}),
                    ('A', 'D', False, {'weight': 2})], nodes=('ISO',))
            self.assertEqual(db.weighted_degree('A'), {'in': 5, 'out': 3, 'undirected': 2, 'total': 10})
            self.assertEqual(db.weighted_degree('ISO'),
                             {'in': 0.0, 'out': 0.0, 'undirected': 0.0, 'total': 0.0})
            self.assertEqual(db.weighted_degree('ZZZ'),
                             {'in': 0.0, 'out': 0.0, 'undirected': 0.0, 'total': 0.0})

            # missing weight property falls back to `default`
            build(db, [('A', 'B', True)])
            self.assertEqual(db.weighted_degree('A', default=1.0)['out'], 1.0)
            self.assertEqual(db.weighted_degree('A', default=7.0)['out'], 7.0)

            # custom weight_key
            build(db, [('A', 'B', True, {'cost': 4})])
            self.assertEqual(db.weighted_degree('A', weight_key='cost')['out'], 4)

            # =====================================================
            # clustering() / average_clustering()
            # =====================================================
            # triangle: fully connected -> coefficient 1.0
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)])
            self.assertEqual(db.clustering('A'), 1.0)
            self.assertEqual(db.average_clustering(), 1.0)

            # star: leaves not connected to each other -> center coefficient 0.0
            build(db, [('H', 'B', False), ('H', 'C', False), ('H', 'D', False)])
            self.assertEqual(db.clustering('H'), 0.0)
            self.assertEqual(db.clustering('B'), 0.0)          # < 2 neighbors

            # path: middle node's 2 neighbors are not connected -> 0.0
            build(db, [('A', 'B', False), ('B', 'C', False)])
            self.assertEqual(db.clustering('B'), 0.0)

            self.assertEqual(db.clustering('ZZZ'), 0.0)        # missing node

            build(db, [])
            self.assertEqual(db.average_clustering(), 0.0)                 # empty graph

            # clustering() with no args returns a dict for every node
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)])
            all_cc = db.clustering()
            self.assertEqual(set(all_cc), {'A', 'B', 'C'})
            self.assertEqual(all_cc['A'], 1.0)

            # nodes=: an iterable of ids returns a dict for just those
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)], nodes=('D',))
            subset_cc = db.clustering(nodes=['A', 'D'])
            self.assertEqual(set(subset_cc), {'A', 'D'})
            self.assertEqual(subset_cc['A'], 1.0)
            self.assertEqual(subset_cc['D'], 0.0)   # isolated

            # weight=: weighted (geometric-mean) undirected clustering
            build(db, [('A', 'B', False, {'weight': 2}), ('B', 'C', False, {'weight': 4}),
                   ('A', 'C', False, {'weight': 8})])
            unweighted = db.clustering('A')
            weighted = db.clustering('A', weight='weight')
            self.assertAlmostEqual(unweighted, 1.0)         # still a full triangle
            self.assertLess(weighted, 1.0)                  # but weights aren't all equal to the max

            # average_clustering(count_zeros=False) excludes exact-zero nodes
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)], nodes=('D',))
            self.assertLess(db.average_clustering(), db.average_clustering(count_zeros=False))
            self.assertAlmostEqual(db.average_clustering(count_zeros=False), 1.0)

            # directed graph: uses the Fagiolo directed-triangle formula
            # (distinct from the undirected formula), matching networkx's
            # clustering() for a DiGraph
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True)])
            dc = db.clustering()
            self.assertTrue(all(0.0 <= v <= 1.0 for v in dc.values()))
            self.assertGreater(dc['A'], 0.0)   # A is part of a 3-cycle

            # =====================================================
            # density()
            # =====================================================
            build(db, [])
            self.assertEqual(db.density(), 0.0)                            # empty graph

            db -= db
            db.add_node('A')
            self.assertEqual(db.density(), 0.0)                            # single node

            # complete directed graph on 3 nodes: 6 possible ordered pairs, all present -> density 1.0
            build(db, [('A', 'B', True), ('B', 'A', True), ('B', 'C', True),
                   ('C', 'B', True), ('A', 'C', True), ('C', 'A', True)])
            self.assertAlmostEqual(db.density(), 1.0)

            # single undirected edge on 3 nodes: counts as 2 directed-equivalents / 6 possible
            build(db, [('A', 'B', False)], nodes=('C',))
            self.assertAlmostEqual(db.density(), 2 / 6)

            # =====================================================
            # edge_betweenness_centrality()
            # =====================================================
            # path A-B-C (undirected): both edges carry equal, nonzero betweenness
            build(db, [('A', 'B', False), ('B', 'C', False)])
            eb = db.edge_betweenness_centrality(normalized=False)
            self.assertEqual(eb[('A', '-', 'B')], eb[('B', '-', 'C')])
            self.assertGreater(eb[('A', '-', 'B')], 0.0)

            # single directed edge: the only shortest path (its two endpoints)
            # crosses it entirely -> betweenness 1.0 (matches networkx)
            build(db, [('A', 'B', True)])
            self.assertEqual(db.edge_betweenness_centrality(normalized=False), {('A', '>', 'B'): 1.0})

            # mixed graph: edge-type in the result key matches how each edge was created
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', False, {'w': 2})])
            eb2 = db.edge_betweenness_centrality(normalized=False)
            self.assertIn(('A', '>', 'B'), eb2)
            self.assertIn(('B', '-', 'C'), eb2)
            self.assertTrue(all(v >= 0.0 for v in eb2.values()))

            # no edges -> empty result, no error
            db -= db
            n = db.add_nodes(['X', 'Y'])
            self.assertEqual(n, 2)
            self.assertEqual(db.edge_betweenness_centrality(), {})

            # =====================================================
            # has_edge() / is_directed() / number_of_nodes() / number_of_edges()
            # =====================================================
            build(db, [('A', 'B', True, {'w': 1}), ('B', 'C', False)], nodes=('D',))
            self.assertEqual(db.number_of_nodes(), 4)
            self.assertEqual(db.number_of_edges(), 2)
            self.assertTrue(db.has_edge('A', 'B', directed=True))
            self.assertFalse(db.has_edge('B', 'A', directed=True))     # wrong direction
            self.assertFalse(db.has_edge('A', 'B', directed=False))    # stored as directed, not undirected
            self.assertTrue(db.has_edge('B', 'C', directed=False))
            self.assertTrue(db.has_edge('C', 'B', directed=False))     # order-agnostic
            self.assertFalse(db.has_edge('X', 'Y'))                    # missing nodes
            self.assertTrue(db.is_directed())                          # has a directed edge

            build(db, [('A', 'B', False)])
            self.assertFalse(db.is_directed())                         # purely undirected

            build(db, [])
            self.assertEqual(db.number_of_nodes(), 0)
            self.assertEqual(db.number_of_edges(), 0)
            self.assertFalse(db.is_directed())

            # =====================================================
            # ancestors() / descendants()
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True)], nodes=('ISO',))
            self.assertEqual(db.descendants('A'), {'B', 'C'})
            self.assertEqual(db.ancestors('C'), {'A', 'B'})
            self.assertEqual(db.descendants('C'), set())               # leaf, nothing further
            self.assertEqual(db.ancestors('A'), set())                 # root, nothing precedes it
            self.assertEqual(db.descendants('ISO'), set())
            self.assertEqual(db.descendants('ZZZ'), set())              # missing node, no error
            self.assertEqual(db.ancestors('ZZZ'), set())

            # =====================================================
            # transitivity(): global clustering coefficient
            # =====================================================
            # triangle: every possible triad is also a triangle -> 1.0
            build(db, [('A', 'B', False), ('B', 'C', False), ('A', 'C', False)])
            self.assertAlmostEqual(db.transitivity(), 1.0)

            # star: every triad (leaf-center-leaf) is open, no triangles -> 0.0
            build(db, [('H', 'B', False), ('H', 'C', False), ('H', 'D', False)])
            self.assertAlmostEqual(db.transitivity(), 0.0)

            build(db, [])
            self.assertEqual(db.transitivity(), 0.0)                    # empty graph

            # =====================================================
            # find_cycle()
            # =====================================================
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True)])
            cyc = db.find_cycle()
            self.assertEqual(len(cyc), 3)
            n = len(cyc)
            for i in range(n):
                self.assertEqual(cyc[i][2], cyc[(i + 1) % len(cyc)][0])  # contiguous chain

            # DAG has no cycle -> raises
            build(db, [('A', 'B', True), ('A', 'C', True), ('B', 'D', True), ('C', 'D', True)])
            with self.assertRaises(ValueError):
                db.find_cycle()

            # source=: only search from that node; a cycle in a different
            # component is not found
            build(db, [('A', 'B', True), ('B', 'C', True), ('C', 'A', True), ('X', 'Y', True)])
            self.assertEqual(len(db.find_cycle(source='A')), 3)
            with self.assertRaises(ValueError):
                db.find_cycle(source='X')
            with self.assertRaises(ValueError):
                db.find_cycle(source='ZZZ')                              # missing node

            # a directed AND undirected edge between the same pair form a
            # 2-edge cycle
            build(db, [('A', 'B', True)])
            db.add_edge('A', 'B', directed=False)
            cyc2 = db.find_cycle()
            self.assertEqual(len(cyc2), 2)
            self.assertEqual(cyc2[0][2], cyc2[1][0])

            # a single undirected edge alone is NOT a cycle
            build(db, [('A', 'B', False)])
            with self.assertRaises(ValueError):
                db.find_cycle()

            # =====================================================
            self.assertEqual(jdb, db)
            self.assertEqual(jdb.keys[:], db.keys[:])
            self.assertEqual(jdb.keys[0.:], db.keys[0.:])
            self.assertEqual(jdb.sync_id, db.sync_id)

            jmem.recycle(level=2)
            error = jmem.check_error(level=2)
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_import(self):
        ini_data = """
            [server]
            host = 127.0.0.1
            port = 8080
        """

        toml_data = """
            app_name = "Omni Test"
            [network]
            ip = "192.168.1.1"
            port = 8181
        """

        db_path = 'db/sample.sqlite'
        create_sample_db(db_path)

        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['group'] = jdb1 = JDb(jdb)

            jdb.from_ini(io.StringIO(ini_data))
            self.assertEqual(set(jdb), {'server/host', 'server/port'})
            self.assertEqual(jdb['server/port'], '8080')

            jdb.from_toml(io.StringIO(toml_data))
            total = len(jdb)
            self.assertEqual(total, 5)
            self.assertEqual(jdb - {'server/host', 'server/port'}, {'/app_name', 'network/ip', 'network/port'})
            self.assertEqual(jdb['network/port'], 8181)

            jdb.from_sqlite(db_path)
            project_jdb = jdb.get_group('projects')
            log_jdb = jdb.get_group('project_logs')
            self.assertEqual(project_jdb, jdb['projects'])
            self.assertEqual(log_jdb, jdb['project_logs'])
            self.assertEqual(len(log_jdb), 4, Style(f'{filename}:{jdb}', red=1))
            self.assertEqual(len(project_jdb), 3)
            self.assertEqual(project_jdb[3]['name'], 'coding')
            self.assertEqual(project_jdb[3]['name'], 'coding')
            logs = log_jdb.find(FUNC=lambda v:v.get('project_id') == 3)
            self.assertEqual([log for _id,log in logs.items()], [{'project_id': 3, 'action': 'setup environment', 'log_date': '2024-01-01'}])

            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError:
                pa = None

            if pa is None: # pragma: no cover
                print(Style(f'{filename}: pyarrow not installed, skipping from_parquet test', yellow=1))
            else:
                parquet_path = 'db/sample.parquet'
                table = pa.table({
                    '_id': ['p1', 'p2', 'p3', 'p4'],
                    'name': ['Alice', 'Bob', 'Charlie', 'Diana'],
                    'age': [30, 25, 35, 28],
                    'active': [True, False, True, True],
                })
                pq.write_table(table, parquet_path)

                before = len(jdb)
                jdb.from_parquet(parquet_path)
                self.assertEqual(len(jdb), before + 4)
                self.assertEqual(jdb['p1'], {'name': 'Alice', 'age': 30, 'active': True})
                self.assertEqual(jdb['p3']['name'], 'Charlie')

                matches = jdb.find(ANY={'name': 'Diana'})
                self.assertEqual(len(matches), 1)

                jdb.remove(['p1', 'p2', 'p3', 'p4'])
                self.assertEqual(len(jdb), before)

                # explicit key column + column pruning (only 'name' imported)
                jdb.from_parquet(parquet_path, key='_id', columns=['name'])
                self.assertEqual(jdb['p2'], {'name': 'Bob'})
                self.assertNotIn('age', jdb['p2'])

                jdb.remove(['p1', 'p2', 'p3', 'p4'])
                self.assertEqual(len(jdb), before)

                # streaming with a tiny batch_size still yields correct results
                jdb.from_parquet(parquet_path, batch_size=1)
                self.assertEqual(len(jdb), before + 4)

                jdb.remove(['p1', 'p2', 'p3', 'p4'])
                self.assertEqual(len(jdb), before)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_query(self):
        # Sample user records
        users = {
           'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
           'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
           'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
           'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
        }

        user = Query()
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            # Insert data
            jdb += users
            self.assertEqual(jdb, users)

            self.assertTrue((user.age > 30) in jdb)
            self.assertFalse((user.age <= 10) | (user.age >= 99) in jdb)
            self.assertFalse(user.name.endswith('an') in jdb)
            self.assertTrue(user.name.startswith('A') in jdb)

            res = jdb.show(with_date=True, sort=[user._date, user.age])
            self.assertEqual(res, users)

            res = jdb.find(sort=[user._date.last(), user.age])
            self.assertEqual(res, users)

            today = dt.date.today()
            res = jdb.find(date=Query() >= today, with_value=True)
            self.assertEqual(res, users)

            yesterday = today - dt.timedelta(days=1)
            res = jdb.find(date=frozenset([str(today), str(yesterday)]), with_value=True)
            self.assertEqual(res, users)

            jdb.keys[user.name == 'Alice'] = dt_2000 = dt.datetime(2000, 1, 1) # change created date
            jdb.keys[user.role.ihas('develop')] = dt_2005 = dt.datetime(2005, 5, 5) # change created date
            jdb.keys[user.age >= 35] = dt_2010 = dt.datetime(2010, 10, 10) # change created date
            jdb.keys[user.email.endswith('test.com')] = dt_2015 = dt.datetime(2015, 12, 12) # change created date
            jdb.keys['user_1'] = today  # change modified date
            jdb.keys['user_2'] = prev_date1 = today - dt.timedelta(days=1) # change modified date
            jdb.keys['user_3'] = prev_date2 = today - dt.timedelta(days=2) # change modified date
            jdb.keys['user_4'] = prev_date3 = today - dt.timedelta(days=3) # change modified date
            self.assertEqual(jdb, users)

            res = jdb.show(with_date=True, sort=1, reverse=True)
            self.assertEqual(res, users)

            res = jdb.find(sort=user.age)
            self.assertEqual(res, users)

            res = jdb.find(sort=[user.role, user.name, user.age])
            self.assertEqual(res, users)

            res = jdb.find(sort=[user._id, user._date])
            self.assertEqual(res, users)

            res = jdb.find(sort=[user.tags[0], user.email])

            # --------------------------------------------
            res = jdb.find(user._date.startswith('2005'))
            self.assertEqual(set(res), {'user_2'})

            # modified date == tuesday (0 = monday, ... 5 = saturday, 6 = sunday)
            res = jdb.find(user._date.mod(7, today.weekday()))
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find(user._date.mod(7, today.weekday()))
            self.assertEqual(res, res2)

            res2 = jdb[user._date.mod(7, today.weekday())]
            self.assertEqual(set(res), set(res2))

            # created date == saturday
            res = jdb.find(user._date.mod(7., 5))
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # created date near 2005-05-01 +/- 10 days
            res = jdb.find(user._date.near(dt.datetime(2005, 5, 1), 10))
            self.assertEqual(set(res), {'user_2'})

            # modified date near today() +/- 1 days
            res = jdb.find(user._date.near(today, 1))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            # 2005-05-05 <= created date <= 2010-10-10
            res = jdb.find(user._date.between(dt_2005, dt_2010))
            self.assertEqual(set(res), {'user_2', 'user_3'})

            res = jdb.find(user._date == dt_2005)
            self.assertEqual(set(res), {'user_2'})

            res = jdb.find(user._date != dt_2005)
            self.assertEqual(set(res), {'user_1', 'user_3', 'user_4'})

            res = jdb.find(user._date >= dt_2010)
            self.assertEqual(set(res), {'user_3', 'user_4'})

            res = jdb.find(user._date < dt_2015)
            self.assertEqual(set(res), {'user_1', 'user_2', 'user_3'})

            res = jdb.find(user._date <= dt_2000)
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(user._date > prev_date1)
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find((user._date >= prev_date1) & (user._date <= today))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res = jdb.find(user._date < prev_date2)
            self.assertEqual(set(res), {'user_4'})

            res = jdb.find(user._date <= prev_date3)
            self.assertEqual(set(res), {'user_4'})

            res = jdb.find(user._date.has('201'))
            self.assertEqual(set(res), {'user_3', 'user_4'})

            res = jdb.find(user._date.not_has('201'))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res = jdb.find(user._date.has(today))
            self.assertEqual(set(res), {'user_1'})

            # check modified date in set()
            res = jdb.find(user._date.one_of({prev_date3, prev_date1}))
            self.assertEqual(set(res), {'user_2', 'user_4'})

            res = jdb.find(user._date.not_in({prev_date3, prev_date1}), with_value=True)
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res = jdb.find(user._date.test(lambda cdate,mdate: cdate < today and mdate >= prev_date1))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            # -------------------------------------
            # group_by: str spec — group key becomes the new _id,
            # other fields are collected as lists (record order)
            res = jdb.find(group_by='role')
            self.assertEqual(set(res), {'admin', 'developer', 'designer'})
            self.assertEqual(res['developer']['name'], ['Bob', 'Charlie'])
            self.assertEqual(res['developer']['age'], [25, 35])
            self.assertNotIn('role', res['developer']) # group key not repeated in the value

            # Query spec == str spec
            res2 = jdb.find(group_by=user.role)
            self.assertEqual(res, res2)

            # '$list' pseudo-op == the default list mode
            res2 = jdb.find(group_by='role.$list')
            self.assertEqual(res, res2)

            # trailing op = aggregation method applied to every collected list;
            # inapplicable op (e.g. $avg over names) -> None
            res = jdb.find(group_by='role.$avg')
            self.assertEqual(res['developer']['age'], 30.)
            self.assertIsNone(res['developer']['name'])

            res2 = jdb.find(group_by=user.role.avg()) # Query().role.avg() -> 'role.$avg'
            self.assertEqual(res, res2)

            res = jdb.find(group_by=user.role.max())
            self.assertEqual(res['developer']['age'], 35)
            self.assertEqual(res['developer']['name'], 'Charlie')

            # ops before the trailing one transform the group key itself
            res = jdb.find(group_by='role.$upper.$len')
            self.assertEqual(set(res), {'ADMIN', 'DEVELOPER', 'DESIGNER'})
            self.assertEqual(res['DEVELOPER']['age'], 2)

            # unresolvable group-key path -> the None group
            res = jdb.find(group_by='email')
            self.assertEqual(set(res[None]['name']), {'Bob', 'Charlie'})

            # -------------------------------------
            # group_by: list spec — composite key, new _id is a tuple
            res = jdb.find(group_by=['role', user.age])
            self.assertEqual(res[('developer', 25)]['name'], ['Bob'])
            self.assertEqual(res[('developer', 35)]['name'], ['Charlie'])

            # a standalone op element sets the aggregation for all fields
            res = jdb.find(group_by=['role', '$sum'])
            self.assertEqual(res['developer']['age'], 60)

            # ops inside a list element (incl. trailing) transform that key component
            res = jdb.find(group_by=[user.name.lower().first()])
            self.assertEqual(set(res), {'a', 'b', 'c', 'd'})
            self.assertEqual(res['c']['age'], [35])

            # -------------------------------------
            # group_by: dict spec — only listed fields, per-field aggregation,
            # '_id' yields the original record keys
            res = jdb.find(group_by={'role': ['age.$max', 'age.$min', '_id']})
            self.assertEqual(res['developer'], {'age': 35, 'age.$min': 25, '_id': ['user_2', 'user_3']})

            # Query as dict key and as field specs; '_id.$len' == group size
            res = jdb.show(group_by={user.role: [user.age.avg(), user._id.len()]})
            self.assertEqual(res['developer'], {'age': 30., '_id': 2})

            # $flat merges the collected list-of-lists
            res = jdb.find(group_by={user.role: [user.tags.flat()]})
            self.assertEqual(res['developer']['tags'], ['javascript', 'web', 'python', 'linux', 'aws'])

            # tuple dict key -> composite group key
            res = jdb.find(group_by={('role', user.age): ['_id']})
            self.assertEqual(res[('developer', 25)], {'_id': ['user_2']})

            res2 = jdb.find(group_by={(user.role, user.age): ['_id']})
            self.assertEqual(res, res2)

            # -------------------------------------
            # group_by: '_date' root -> (created, modified) date tuple
            res = jdb.find(group_by='_date')
            self.assertEqual(len(res), 4) # all (cdate, mdate) pairs are distinct
            self.assertEqual(res[(dt_2005.date(), prev_date1)]['name'], ['Bob'])

            # created date only / modified date only (list form: op transforms the key)
            res = jdb.find(group_by=[user._date.first()])
            self.assertEqual(set(res), {dt_2000.date(), dt_2005.date(), dt_2010.date(), dt_2015.date()})
            self.assertEqual(res[dt_2010.date()]['name'], ['Charlie'])

            res = jdb.find(group_by=['_date.$last'])
            self.assertEqual(res[today]['name'], ['Alice'])
            self.assertEqual(res[prev_date3]['name'], ['Diana'])

            res = jdb.find(group_by={'_date': ['_id', 'age.$sum']})
            self.assertEqual(res[(dt_2000.date(), today)], {'_id': ['user_1'], 'age': 30})

            # -------------------------------------
            # group_by + sort: sorting applies to the grouped rows
            res = jdb.find(group_by='role.$avg', sort='age')
            self.assertEqual(list(res), ['designer', 'admin', 'developer']) # 28. < 30. == 30. (stable)

            res = jdb.find(group_by='role', sort='_id', reverse=True)
            self.assertEqual(list(res), ['developer', 'designer', 'admin'])

            # show() accepts the same group_by specs and returns the grouped dict
            res = jdb.show(group_by={user.role: [user.age.avg(), '_id']}, with_date=True, sort=user._id)
            self.assertEqual(list(res), ['admin', 'designer', 'developer'])
            self.assertEqual(res['developer']['_id'], ['user_2', 'user_3'])

            # -------------------------------------
            # group_by: invalid specs
            with self.assertRaises(ValueError):
                jdb.find(group_by='$avg') # no group-key field

            with self.assertRaises(ValueError):
                jdb.find(group_by=['$avg']) # list form: still no group-key field

            with self.assertRaises(ValueError):
                jdb.find(group_by={(): ['_id']}) # empty composite key

            with self.assertRaises(ValueError):
                jdb.find(group_by={'role': ['_id'], 'age': ['_id']}) # dict must hold one pair

            with self.assertRaises(TypeError):
                jdb.find(group_by=123) # unsupported spec type

            res = jdb.find(user._date.has(today))
            self.assertEqual(set(res), {'user_1'})

            # check modified date in set()
            res = jdb.find(user._date.one_of({prev_date3, prev_date1}))
            self.assertEqual(set(res), {'user_2', 'user_4'})

            res = jdb.find(user._date.not_in({prev_date3, prev_date1}), with_value=True)
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res = jdb.find(user._date.test(lambda cdate,mdate: cdate < today and mdate >= prev_date1))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            #------------------------------------
            # KEY.endswith('_3')
            res = jdb.show(user._id.endswith(('_3', '_2')))
            self.assertEqual(set(res), {'user_2', 'user_3'})

            res2 = jdb.find(user._id.endswith(('_3', '_2')), with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb[user._id.endswith(('_3', '_2'))]
            self.assertEqual(res, res2)

            res2 = jdb.keys[user._id.endswith(('_3', '_2'))]
            self.assertEqual(set(res), set(res2))

            # 'user_2' <= KEY <= 'user_4'
            res = jdb.find(user._id.between('user_2', 'user_4'))
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res = jdb.find(user._id.size_of([4,5,6]))
            self.assertEqual(set(res), set(users))

            res = jdb.find(user._id.size_of(6))
            self.assertEqual(set(res), set(users))

            res = jdb.find(user._id.has('r_1'))
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(user._id.not_has('r_1'))
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res = jdb.find(user._date.any_in([prev_date3, prev_date1]), with_value=True)
            self.assertEqual(set(res), {'user_2', 'user_4'})

            res2 = jdb.find(user._id.fullmatch(r'user_[24]'), with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(user._date.any_in([prev_date3, prev_date1]) & user._id.matches(r'er_[24]'))
            self.assertEqual(set(res), set(res2))

            res2 = jdb[user._date.any_in([prev_date3, prev_date1]) & user._id.matches(r'er_[24]')]
            self.assertEqual(res, res2)
            #----------------------------------------------------------
            # VAL['name'].endswith('e')
            res = jdb.find(user.name.endswith('e'))
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.find(user.name.last() == 'e')
            self.assertEqual(res, res2)

            # 'Aa' <= VAL['name'] <= 'Bz'
            res = jdb.find(user.name.between('Aa', 'Bz'))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            # not 'Aa' <= VAL['name'] <= 'Bz'
            res = jdb.find(~user.name.between('Aa', 'Bz'))
            self.assertEqual(set(res), {'user_3', 'user_4'})

            #----------------------------------------------------------
            res = jdb.find(user.name == 'Alice')
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find(user.name.lower() == 'alice')
            self.assertEqual(res, res2)

            res2 = jdb.find(user.name.lower().first() == 'a')
            self.assertEqual(res, res2)

            res2 = jdb.find(user.name.strip().upper().has('ALI'))
            self.assertEqual(res, res2)

            res = jdb.find(user['**'].matches(r'designer'))
            self.assertEqual(set(res), {'user_4'})

            res = jdb.find(user.role.ihas('designer'))
            self.assertEqual(set(res), {'user_4'})

            # 2. Relational & Conditional Operators (vals)
            #----------------------------------------------------------
            res = jdb.show(user.age.type_of(int))
            self.assertEqual(res, users)

            # Age % 10 == 5
            res = jdb.find(user.age.mod(10, 5))
            self.assertEqual(set(res), {'user_2', 'user_3'})

            # Age is greater than or equal to 30
            res = jdb.find(user.age >= 30)
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # Age is strictly less than 30
            res = jdb.find(user.age < 30)
            self.assertEqual(set(res), {'user_2', 'user_4'})

            # not any(Value['age'] == 30 for k in Value)
            res = jdb.find(~(user['**'].age == 30))
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            # Role is either 'admin' or 'designer'
            res = jdb.find(user.role.one_of(['admin', 'designer']))
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # Role is not 'admin' and not 'designer'
            res = jdb.find(user.role.not_in(['admin', 'designer']))
            self.assertEqual(set(res), {'user_2', 'user_3'})

            # tags contains 'python'
            res = jdb.find(user.tags.has('python'))
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # Value['tags'][-1] == 'aws'
            res = jdb.find(user.tags.one_of(['python', 'database']))
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(user.tags.any_in(['linux', 'database']))
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res = jdb.find(user.tags.not_in(['python', 'database']))
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            # tags contains 'python' AND 'linux'
            res = jdb.find(user.tags.has('python') & user.tags.has('linux'))
            self.assertEqual(set(res), {'user_3'})

            # ANY contains 'Bo'
            res = jdb.find(user['*'].has('Bo'))
            self.assertEqual(set(res), {'user_2'})

            res2 = jdb.find(user['*'].ihas('bo'))
            self.assertEqual(res, res2)

            res2 = jdb.keys[user['*'].ihas('bo')]
            self.assertEqual(set(res), set(res2))

            # Age is NOT 30
            res = jdb.find(user.age != 30)
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res = jdb.find(user['*'] !=  30)
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            # Age is 28
            res = jdb.find(user.age == 28)
            self.assertEqual(set(res), {'user_4'})

            # 40 >= Age > 25
            res = jdb.find((user.age > 25) & (user.age <= 40))
            self.assertEqual(set(res), {'user_1', 'user_3', 'user_4'})

            # not 40 >= Age > 25
            res = jdb.find(~(user.age > 25) | ~(user.age <= 40))
            self.assertEqual(set(res), {'user_2'})

            # name in ['Alice', 'Bob'] AND age in [30, 25]
            res = jdb.find(user.name.fullmatch('Alice|Bob') & user.age.one_of([30, 25]))
            self.assertEqual(set(res), {'user_1', 'user_2'})

            # 3. Logical Grouping (AND, OR, NOR, NOT)
            #----------------------------------------------------------
            # Age >= 25 AND Age <= 30
            res = jdb.find((user.age >= 25) & (user.age <= 30))
            self.assertEqual(set(res), {'user_1', 'user_2', 'user_4'})

            # Role is 'admin' OR Age > 30
            res = jdb.find((user.role == 'admin') | (user.age > 30))
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # Role is not 'admin' AND Age <= 30
            res = jdb.find(~((user.role == 'admin') | (user.age > 30)))
            self.assertEqual(set(res), {'user_2', 'user_4'})

            # User is NOT a developer
            res = jdb.find(user.role.not_has('developer'))
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # (Role is 'admin' OR Age > 30) AND 'linux' not in tags
            res = jdb.find((((user.role == 'admin') | (user.age > 30)) & ~(user.tags.has('linux'))))
            self.assertEqual(set(res), {'user_1'})

            # 4. Regular Expressions (RE, RE2, re.compile)
            #----------------------------------------------------------
            # Values matching an email domain regex
            res = jdb.find(user.email.matches(r'.@example.com'))
            self.assertEqual(set(res), {'user_1'})

            # Find users where any attribute exactly matches regex
            res = jdb.find(user['*'].matches(r'.@example.com'))
            self.assertEqual(set(res), {'user_1'})

            # Global regex search for strings containing 'li' (matches 'Alice', 'Charlie', 'linux')
            res = jdb.find(user['*'].matches('li[a-z]'))
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # 5. Array / List Operations
            #----------------------------------------------------------
            # Users with exactly 2 tags in their list
            res = jdb.find(user.tags.size_of(2))
            self.assertEqual(set(res), {'user_1', 'user_2', 'user_4'})

            # Users whose FIRST tag (index 0) is 'python'
            res = jdb.find(user.tags[0] == 'python')
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # 6. Lambda / Custom Functions (FUNC) & Pagination (limit)
            #----------------------------------------------------------
            # Pass a lambda to evaluate both the key and the value dynamically
            # Example: Find the first users whose age is an even number
            res = jdb.find(user.test(lambda k,v: isinstance(v, dict) and v.get('age', 1) % 2 == 0), limit=1)
            self.assertTrue(set(res), {'user_1'})

            # Users has email
            res = jdb.find(user.email.test(lambda v: v != ''))
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # Users don't have email
            res = jdb.find(~user.email.test(lambda v: v != ''))
            self.assertEqual(set(res), {'user_2', 'user_3'})

            res = jdb.find(~user.exists('email'))
            self.assertEqual(set(res), {'user_2', 'user_3'})

            #----------------------------------------------------------
            jdb += {
                'user_5': {
                    'name': 'Eva','age': 32, 'email': 'eva@company_a.com', 'role': 'officer',
                    'addr_home': {'city': 'NYC', 'zip': 10001}, 'addr_work': {'city': 'LA'},
                    'meta': {'tags': ['db', 'excel'], 'labels': ['backend', 'api']}, 'scores': [85.1, 90.2, 78.3]},
                'user_6': {
                    'name': 'Fiona', 'age': 44, 'email': 'fiona@company_b.com', 'role': 'CEO',
                    'addr_home': {'city': 'Tokyo', 'zip':4000}, 'addr_work': {'city': 'HK', 'zip': 5001},
                    'meta': {'tags': ['python', 'excel'], 'labels': ['api', 'frontend']}, 'scores': [92.4, 95.5, 99.6]}
            }

            res = jdb.show(sort=[user.addr_home.city, user.addr_work.city, user._date, user._id])
            self.assertEqual(set(res), {f'user_{v+1}' for v in range(6)})

            # int(scores[0]) == 92
            res = jdb.find(user.scores.first().int() == 92)
            self.assertEqual(set(res), {'user_6'})

            # sorted(flat(scores))[0] > 90
            res = jdb.find(user.scores.flat().sort().first() > 90)
            self.assertEqual(set(res), {'user_6'})

            # sorted(flat(scores))[-1] < 91
            res = jdb.find(user.scores.unique().sort().last().floor() < 91)
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(user.scores.last().round() < 91)
            self.assertEqual(res, res2)

            res2 = jdb.find(user.scores.last().str() == '78.3')
            self.assertEqual(res, res2)

            # int(scores[-1]) < 90
            res = jdb.find(user.scores.last() <= 90)
            self.assertEqual(set(res), {'user_5'})

            # average(scores) >= 90
            res = jdb.find(user.scores.avg() >= 90)
            self.assertEqual(set(res), {'user_6'})

            # max(scores) > 90.2
            res = jdb.find(user.scores.max() > 90.2)
            self.assertEqual(set(res), {'user_6'})

            # max(scores) == 99
            res = jdb.find(user.scores.max().int() == 99)
            self.assertEqual(set(res), {'user_6'})

            res2 = jdb.find(user.scores.max().floor().str() == '99')
            self.assertEqual(res, res2)

            res2 = jdb.find(user.scores.ceil().max() > 99)
            self.assertEqual(res, res2)

            res2 = jdb.find(user.scores.round().max() == 100)
            self.assertEqual(res, res2)

            res2 = jdb.find(user.scores.floor().max() == 99)
            self.assertEqual(res, res2)

            # max(scores) in [90, 88]
            res = jdb.find(user.scores.max().int().one_of((90, 99)))
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(user.scores.str().float().int().max().one_of((90, 99)))
            self.assertEqual(res, res2)

            res2 = jdb.find(user.scores.len() == 3)
            self.assertEqual(res, res2)

            # min(scores) <= 80
            res = jdb.find(user.scores.min() <= 80)
            self.assertEqual(set(res), {'user_5'})

            # 91 >= mid(scores) >= 90
            res = jdb.find(user.scores.mid().between(90, 91))
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(user.scores.sort().mid().int() == 85)
            self.assertEqual(res, res2)

            # sum(scores) < 270
            res = jdb.find(user.scores.sum() < 270)
            self.assertEqual(set(res), {'user_5'})

            # abs(std(scores)) > 0
            res = jdb.find(user.scores.std().abs() > 0.)
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(user.scores.std().neg().abs() > 0.)
            self.assertEqual(res, res2)

            # len(tags) > 2
            res = jdb.find(user.tags.len() == 3)
            self.assertEqual(set(res), {'user_3'})

            res = jdb.show(user.exists('email'))
            self.assertEqual(set(res), {'user_1', 'user_4', 'user_5', 'user_6'})

            # city name == 'NYC'
            res = jdb.find(user.addr_home.city == 'NYC')
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(user['addr*'].city == 'NYC')
            self.assertEqual(res, res2)

            res2 = jdb[user['addr*'].city == 'NYC']
            self.assertEqual(res, res2)

            # find frontend in meta field
            res = jdb.find(user.meta['**'].ihas('frontend'))
            self.assertEqual(set(res), {'user_6'})

            # 'meta' exists and not city == Tokyo
            res = jdb.find(user.exists('meta') & ~(user['addr*'].city == 'Tokyo'))
            self.assertEqual(set(res), {'user_5'})

            # 'email' exists
            res = jdb.find(user.exists('email'))
            self.assertEqual(set(res), {'user_1', 'user_4', 'user_5', 'user_6'})

            # both 'email' and 'meta' exist
            res = jdb.find(user.exists(('email', 'meta')))
            self.assertEqual(set(res), {'user_5', 'user_6'})

            # city name start with 'L' or 'H'
            res = jdb.find(user['addr?*'].city.startswith(('L', 'H')))
            self.assertEqual(set(res), {'user_5', 'user_6'})

            # addr_home.zip >= 5000
            res = jdb.find(user.addr_home.zip >= 5000)
            self.assertEqual(set(res), {'user_5'})

            # meta.tags[0] == 'python' or meta.labels[0] == 'python'
            res = jdb.find(user.meta['*'][0] == 'python')
            self.assertEqual(set(res), {'user_6'})

            # meta.tags[-1] == 'api' or meta.labels[-1] == 'api'
            res = jdb.find(user.meta['*'][-1] == 'api')
            self.assertEqual(set(res), {'user_5'})

            # meta.tags[0].endswith(('b', 'i')) or meta.labels[0].endswith(('b', 'i'))
            res = jdb.find(user.meta['*'][0].endswith(('b', 'i')))
            self.assertEqual(set(res), {'user_5', 'user_6'})

            # 'db' in meta.tags
            res = jdb.find(user.meta.tags['*'] == 'db')
            self.assertEqual(set(res), {'user_5'})

            # any(socre >= 90 for score in scores)
            res = jdb.find(user.scores['*'] >= 90)
            self.assertEqual(set(res), {'user_5', 'user_6'})

            # any(score > 95 for score in scores)
            res = jdb.find(user.scores['*'] > 95)
            self.assertEqual(set(res), {'user_6'})

            # -------------------------------------
            res = jdb.update_if(user.role == 'admin', {'role': 'Administrator'})
            self.assertEqual(res, 1)

            res = jdb[user.role.endswith('trator')]
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(user.age >= 45)
            self.assertEqual(len(res), 0)

            res = jdb.update_if(user.age < 45, lambda key,old_val:{'age':old_val['age']+1, 'license':old_val.get('expired', old_val['age']+1 >= 45)})
            self.assertEqual(res, 6)

            res = jdb.find(user.age >= 45)
            self.assertEqual(set(res), {'user_6'})

            res2 = jdb.find(user.license.int() != 0)
            self.assertEqual(res, res2)

            cond = (user.age >= 32) & (user.age <= 50)
            res = jdb[cond]
            self.assertEqual(set(res), {'user_3', 'user_5', 'user_6'})

            jdb[cond] = 'modified'
            res2 = jdb.find(EQ='modified')
            self.assertEqual(set(res), set(res2))

            cnt = len(jdb)
            del jdb[user.email != '']
            self.assertEqual(len(jdb), cnt-2)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_nosql(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['users'] = jdb

            # Sample user records
            users = {
               'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
               'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
               'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
               'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
            }

            # Insert data
            jdb += users
            self.assertEqual(jdb, users)

            jdb.keys['user_1'] = dt_2000 = dt.datetime(2000, 1, 1) # change created date
            jdb.keys['user_2'] = dt_2005 = dt.datetime(2005, 5, 5) # change created date
            jdb.keys['user_3'] = dt_2010 = dt.datetime(2010, 10, 10) # change created date
            jdb.keys['user_4'] = dt_2015 = dt.datetime(2015, 12, 12) # change created date
            jdb.keys['user_1'] = today = dt.date.today() # change modified date
            jdb.keys['user_2'] = prev_date1 = today - dt.timedelta(days=1) # change modified date
            jdb.keys['user_3'] = prev_date2 = today - dt.timedelta(days=2) # change modified date
            jdb.keys['user_4'] = prev_date3 = today - dt.timedelta(days=3) # change modified date
            self.assertEqual(jdb, users)

            res = jdb.show(limit=0, with_date=True) # display all
            self.assertEqual(res, users)

            res1 = jmem.show(vals={'$key':None, '$date':None}, limit=0, with_date=True)
            self.assertEqual({f'users:::{kk}' for kk in res}, set(res1))

            # --------------------------------------------
            res = jdb.find(date={'$sw': '2005'})
            self.assertEqual(set(res), {'user_2'})

            res2 = jdb.find(date={'$ew': str(prev_date1)})
            self.assertEqual(res, res2)

            res2 = jdb.find(['user_1', 'user_2'], date={'$ew': str(prev_date1)})
            self.assertEqual(res, res2)

            # modified date == tuesday (0 = monday, ... 5 = saturday, 6 = sunday)
            res = jdb.find(date={'$mod': (7, today.weekday())})
            self.assertEqual(set(res), {'user_1'})

            # created date == saturday
            res = jdb.find(date={'$mod': (7., 5)})
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # created date near 2005-05-01 +/- 10 days
            res = jdb.find(date={'$near': (dt.datetime(2005, 5, 1), 10)})
            self.assertEqual(set(res), {'user_2'})

            # modified date near today() +/- 1 days
            res = jdb.find(date={'$near': (today, 1)})
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res = jdb.find(date={'$near': (today, 1)}, limit=1)
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(date={'$near': (today, 1)}, skip=1)
            self.assertEqual(set(res), {'user_2'})

            # 2005-05-05 <= created date <= 2010-10-10
            res = jdb.find(date={'$between': (dt_2005, dt_2010)})
            self.assertEqual(set(res), {'user_2', 'user_3'})

            # (today - 2 ) <= modified date <= yesterday
            res2 = jdb.find(date={'$between': (prev_date2, prev_date1)})
            self.assertEqual(res, res2)

            # '2005-01' <= modified/created date <= '2010-12'
            res2 = jdb.find(date={'$between': ('2005-01', '2010-12')})
            self.assertEqual(res, res2)

            res = jdb.find(date=dt_2005)
            self.assertEqual(set(res), {'user_2'})

            res2 = jdb.find(date={'$eq': dt_2005})
            self.assertEqual(res, res2)

            res2 = jdb.find(date=prev_date1)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$eq': prev_date1})
            self.assertEqual(res, res2)

            res = jdb.find(date={'$ne': dt_2005})
            self.assertEqual(set(res), {'user_1', 'user_3', 'user_4'})

            res2 = jdb.find(date={'!$eq': dt_2005}) # {'$not':{'$eq': dt_2005}}
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$ne': prev_date1})
            self.assertEqual(res, res2)

            res = jdb.find(date={'$gt': dt_2010})
            self.assertEqual(set(res), {'user_4'})

            res = jdb.find(date={'$gte': dt_2010})
            self.assertEqual(set(res), {'user_3', 'user_4'})

            res2 = jdb.find(date={'!$lt': dt_2010}) # {'$not':{'$lt': dt_2010}}
            self.assertEqual(res, res2)

            res = jdb.find(date={'$lt': dt_2015})
            self.assertEqual(set(res), {'user_1', 'user_2', 'user_3'})

            res = jdb.find(date={'$lte': dt_2000})
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(date={'$gt': prev_date1})
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(date={'$gte': prev_date1})
            self.assertEqual(set(res), {'user_1', 'user_2'})

            # created_date in (today, prev_date1) or modified_date in (today, prev_date1)
            res2 = jdb.find(date=(today, prev_date1))
            self.assertEqual(res, res2)

            res = jdb.find(date={'$lt': prev_date2})
            self.assertEqual(set(res), {'user_4'})

            res = jdb.find(date={'$lte': prev_date3})
            self.assertEqual(set(res), {'user_4'})

            res = jdb.find(date=today)
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find(date=str(today))
            self.assertEqual(res, res2)

            res = jdb.find(date={'$has': '201'})
            self.assertEqual(set(res), {'user_3', 'user_4'})

            res = jdb.find(date={'$not': {'$has': '201'}})
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res2 = jdb.find(date={'!$has': '201'})
            self.assertEqual(res, res2)

            res1 = jmem.find(vals={'$date':{'$not': {'$has': '201'}}})
            self.assertEqual(set(res1), {'users:::user_1', 'users:::user_2'})

            res2 = jmem.find(vals={'$date':{'$nhas': '201'}})
            self.assertEqual(res1, res2)

            res = jdb.find(date={'$has': today})
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find(date={'$has': dt_2000})
            self.assertEqual(res, res2)

            res2 = jdb.find(date=0)
            self.assertEqual(res, res2)

            res = jdb.find(date=-1)
            self.assertEqual(set(res), {'user_1', 'user_2'})

            # check modified date in set()
            res = jdb.find(date={'$in': {prev_date3, prev_date1}})
            self.assertEqual(set(res), {'user_2', 'user_4'})

            res2 = jdb.find(date={prev_date3, prev_date1})
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$anyin': [prev_date3, prev_date1]})
            self.assertEqual(res, res2)

            # check created date in tuple or list
            res2 = jdb.find(date=(dt_2005.date(), dt_2015.date()))
            self.assertEqual(res, res2)

            res2 = jdb.find(date=[dt_2015.date(), dt_2005.date()])
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$anyin': {dt_2015.date(), dt_2005.date()}})
            self.assertEqual(res, res2)

            res = jdb.find(date={'$nin': {prev_date3, prev_date1}}, with_value=True)
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.find(date={'!$in': {prev_date3, prev_date1}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'!$anyin': {prev_date3, prev_date1}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$nin': (dt_2005.date(), dt_2015.date())}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date=re.compile(r'20[01]0-'), with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$re2': r'20\d0-'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$match': r'20\d0-'}, with_value=True)
            self.assertNotEqual(res, res2)

            res2 = jdb.find(date={'$re': [r'20\d[0-4]', r'20\d[6-9]']}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$not': {'$in': {prev_date3, prev_date1}}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'!$in': {prev_date3, prev_date1}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$or': [{'$eq': dt_2000}, {'$eq': dt_2010}]}, with_value=True)
            self.assertEqual(res, res2)

            res1 = jmem.find(vals={'$date': {'$or': [{'$eq': dt_2000}, {'$eq': dt_2010}]}}, with_value=True)
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res1)

            res2 = jdb.find(date={'$or': [dt_2000, dt_2010]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$nor':[{'$eq': dt_2005}, {'$eq': dt_2015}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'!$or':[{'$eq': dt_2005}, {'$eq': dt_2015}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_date': {'$nor':[{'$eq': dt_2005}, {'$eq': dt_2015}]}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'!_date': {'$or':[{'$eq': dt_2005}, {'$eq': dt_2015}]}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$and':[{'$ne': dt_2005}, {'$ne': dt_2015}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(date={'$ne': dt_2005, '!$eq': dt_2015}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_date.$and':[{'$ne': dt_2005}, {'$ne': dt_2015}]})
            self.assertEqual(res, res2)

            res2 = jdb.show(date={'$and':[{'$ne': dt_2005}, {'$ne': dt_2015}]}, with_date=True)
            self.assertEqual(res, res2)

            res1 = jmem.show(vals={'$date': {'$and':[{'$ne': dt_2005}, {'$ne': dt_2015}]}}, with_date=True)
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res1)

            res = jdb.find(date=lambda cdate,mdate: cdate < today and mdate >= prev_date1)
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res2 = jdb.find(date={'$func': lambda cdate,mdate: mdate >= prev_date1})
            self.assertEqual(res, res2)

            #------------------------------------
            # KEY.endswith('_3')
            res = jdb.find({'$ew': '_3'})
            self.assertEqual(set(res), {'user_3'})

            res2 = jdb.find_iter({'$ew': '_3'}, with_date=True)
            self.assertEqual({k:v[0] for k,v in res2 if len(v) >= 3}, res)

            # 'user_2' <= KEY <= 'user_4'
            res = jdb.find({'$between': ('user_2', 'user_4')})
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res2 = jdb.find({'$upper.$between': ('USER_2', 'USER_4')})
            self.assertEqual(res, res2)

            res2 = jdb.find({'$upper.$lower.$upper.$ge': 'USER_2'})
            self.assertEqual(res, res2)

            res = jdb.find({'$upper': 'USER_2'})
            self.assertEqual(set(res), {'user_2'})

            res = jdb.find(r'_[12]', with_value=True) # == jdb.find(keys=...)
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res1 = jmem.find('users', vals={'$key':'_[12]'}, with_value=True)
            self.assertEqual(set(res1), {'users:::user_1', 'users:::user_2'})

            res2 = jdb.find({'$re':r'_[12]'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jmem.find(vals={'$key': {'$re': '_[12]'}}, with_value=True)
            self.assertEqual(res1, res2)

            res2 = jdb.find({'$re2':r'_[12]'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$match':r'_[12]'}, with_value=True)
            self.assertNotEqual(res, res2)

            res2 = jdb.find({'$match':r'user_[12]'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(re.compile(r'_[12]'), with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(['user_1', 'user_2'], with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_id': {'user_1', 'user_2'}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_id.$last.$between': ('1', '2')}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jmem.find(vals={'$key': {'user_1', 'user_2'}})
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            res2 = jdb.find(lambda k: k.endswith(('1', '2')), with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$lte':  'user_2'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$lt':  'user_3'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$or': ['user_1', 'user_2']}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$or': [{'$eq':'user_1'}, {'$eq':'user_2'}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$and': [{'$ne':'user_4'}, {'$ne':'user_3'}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$ne':'user_4', '!$eq':'user_3'}, with_value=True)

            res2 = jdb.find({'$nor': ['user_3', 'user_4']}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'!$or': ['user_3', 'user_4']}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$and': [{'$ge':'user_1'}, {'$le':'user_2'}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$ge':'user_1', '$le':'user_2'}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'$not': {'$or':[{'$gt':'user_2'}, {'$lt':'user_1'}]}}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.find({'!$or':[{'$gt':'user_2'}, {'$lt':'user_1'}]}, with_value=True)
            self.assertEqual(res, res2)

            res2 = jdb.show({'$not': {'$or':[{'$gt':'user_2'}, {'$lt':'user_1'}]}})
            self.assertEqual(res, res2)

            res2 = jmem.show(vals={'$key': {'$not': {'$or':[{'$gt':'user_2'}, {'$lt':'user_1'}]}}})
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            res2 = jdb.find({'$not': ['user_3', 'user_4']}, with_value=True) # not in ['user_3', 'user_4']
            self.assertEqual(res, res2)

            res2 = jdb.find({'$nin': ['user_3', 'user_4']}, with_value=True) # not in ['user_3', 'user_4']
            self.assertEqual(res, res2)

            res2 = jdb.find({'!$in': ['user_3', 'user_4']}, with_value=True) # not in ['user_3', 'user_4']
            self.assertEqual(res, res2)

            res2 = jdb.find({'!$anyin': ['user_3', 'user_4']}, with_value=True)
            self.assertEqual(res, res2)

            res = jdb.find({'$size': [4,5,6]})
            self.assertEqual(set(res), set(users))

            res = jdb.find({'!$size': [1,2,3,4,5,7]})
            self.assertEqual(set(res), set(users))

            res = jdb.find({'$size': 6})
            self.assertEqual(set(res), set(users))

            res = jdb.find({'!$size': 6})
            self.assertEqual(set(res), set())

            res = jdb.find({'$size': 4})
            self.assertEqual(set(res), set())

            res = jdb.find({'!$size': 4})
            self.assertEqual(set(res), set(users))

            res = jdb.find({'$has': 'r_1'})
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find({'$nhas': 'r_1'})
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res2 = jdb.find({'!$has': 'r_1'})
            self.assertEqual(res, res2)

            res2 = jdb.find({'!$ihas': 'USER_1'})
            self.assertEqual(res, res2)

            res = jdb.find({'$has': 'user_'})
            self.assertEqual(set(res),set(users))

            res2 = jdb.find({'$ihas': 'UseR_'})
            self.assertEqual(res, res2)

            for skip in range(len(jdb)):
                res = jdb.find('', limit=1, skip=skip)
                self.assertEqual(res, {f'user_{skip+1}':None})

            #----------------------------------------------------------
            # VAL['name'].endswith('e')
            res = jdb.find(vals={'name': {'$ew': 'e'}})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.find(vals={'name.$last': 'e'})
            self.assertEqual(res, res2)

            res = jmem.show(r'users:::user_', vals={'name': {'$ew': 'e'}}, with_date=True)
            self.assertEqual(set(res), {'users:::user_1', 'users:::user_3'})

            # 'Aa' <= VAL['name'] <= 'Bz'
            res = jdb.find(vals={'name': {'$between': ('Aa', 'Bz')}})
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res2 = jdb.find(vals={'name.$lower.$first': ['a', 'b']})
            self.assertEqual(res, res2)

            # not 'Aa' <= VAL['name'] <= 'Bz'
            res = jdb.find(vals={'name': {'!$between': ('Aa', 'Bz')}})
            self.assertEqual(set(res), {'user_3', 'user_4'})

            # 1. Exact Match & Global Search (ANY, RE, RE2)
            #----------------------------------------------------------
            # Find users where any attribute exactly matches 'Alice'
            res = jdb.find(ANY='Alice')
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find(vals={'name':'Alice'}) # vals['name'] == 'Alice'
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'name.$lower': 'alice'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'name.$strip.$upper.$eq': 'ALICE'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'name.$lower.$has': 'ali'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'name.$lower.$strip.$has': 'ali'})
            self.assertEqual(res, res2)

            res2 = jdb.find(keys={'$in':['user_1', 'user_3']}, ANY='Alice')
            self.assertEqual(res, res2)

            res2 = jdb.find(keys={'user_1', 'user_3'}, ANY='Alice')
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_id':{'$not':{'$in':['user_2', 'user_4']}}, 'name':{'$eq': 'Alice'}})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_id':{'!$in':['user_2', 'user_4']}, 'name':{'$eq': 'Alice'}})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_id':{'user_1', 'user_3'}, 'name':'Alice'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'_id':{'$nin':{'user_2', 'user_4'}}, 'name':'Alice'})
            self.assertEqual(res, res2)

            res2 = jdb.find(AND=[{'_id':{'user_1', 'user_3'}}, {'name':'Alice'}])
            self.assertEqual(res, res2)

            # RE/RE2 convert value into JSON string format for searching.
            # Find any record that has the string 'designer' inside it
            res = jdb.find(RE=r'designer') # find(vals={'$re': r'designer'})
            self.assertEqual(set(res), {'user_4'})

            # RE2 remove some JSON symbol ([]{}") before searching (not RE)
            res = jdb.find(RE2=r'role:designer') # find(vals={'$re2': r'role:designer'})
            self.assertEqual(set(res), {'user_4'})

            res2 = jdb.show(RE2=r'role:designer', with_date=True)
            self.assertEqual(res, res2)

            res2 = jmem.show(RE2=r'role:designer')
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            res = jdb.find(RE=r'role:designer')
            self.assertEqual(set(res), set())

            # 2. Relational & Conditional Operators (vals)
            #----------------------------------------------------------
            res = jdb.find(vals={'age': {'$mod': (10, 5)}})
            self.assertEqual(set(res), {'user_2', 'user_3'})

            # Age is greater than or equal to 30
            res = jdb.find(vals={'age': {'$gte': 30}})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res = jdb.find(ANY={'$gte': 30})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # Age is strictly less than 30
            res = jdb.find(vals={'age': {'$lt': 30}})
            self.assertEqual(set(res), {'user_2', 'user_4'})

            # age near 20 +/- 9
            res2 = jdb.find(vals={'age': {'$near': (20, 9)}})
            self.assertEqual(res, res2)

            # Not Age >= 30
            res2 = jdb.find(vals={'!age': {'$ge': 30}})
            self.assertEqual(res, res2)

            # any(Value[k] <= 30 for k in Value)
            res = jdb.find(ANY={'$lt': 30})
            self.assertEqual(set(res), {'user_2', 'user_4'})

            # not any(Value['age'] == 30 for k in Value)
            res = jdb.find(NONE={'age': 30}) # vals={'$none':{'age':30}}
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            # Role is either 'admin' or 'designer'
            res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
            self.assertEqual(set(res), {'user_1', 'user_4'})

            res = jdb.find(ANY={'$in': ['admin', 'designer']})
            self.assertEqual(set(res), {'user_1', 'user_4'})

            res2 = jdb.find(vals={'role': {'admin', 'designer'}}) # vals['role'] in {'admin', 'designer'}
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'role': ['admin', 'designer']}) # vals['role'] in ['admin', 'designer']
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'role': ('admin', 'designer')}) # vals['role'] in ('admin', 'designer')
            self.assertEqual(res, res2)

            # Role is not 'admin' and not 'designer'
            res = jdb.find(ANY={'role': {'$nin': ['admin', 'designer']}})
            self.assertEqual(set(res), {'user_2', 'user_3'})

            res2 = jdb.find(ANY={'!role': ['admin', 'designer']})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'!role': ['admin', 'designer']})
            self.assertEqual(res, res2)

            # tags contains 'python'
            res = jdb.find(vals={'tags': {'$has': 'python'}})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.find(vals={'tags': {'$ihas': 'Python'}})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'tags': {'$any': 'python'}})
            self.assertEqual(res, res2)

            # Value['tags'][0] == 'python'
            res2 = jdb.find(vals={'tags.0': 'python'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'t?gs.?': 'python'})
            self.assertEqual(res, res2)

            # Value['tags'][-1] == 'aws'
            res = jdb.find(vals={'tags.-1': 'aws'})
            self.assertEqual(set(res), {'user_3'})

            res = jdb.find(vals={'tags': {'$in': ['python', 'database']}})
            self.assertNotEqual(res, res2)
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(vals={'tags': {'$anyin': ['linux', 'database']}})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res = jdb.find(vals={'tags': {'$nin': ['python', 'database']}})
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res2 = jdb.find(vals={'!tags': ['python', 'database']})
            self.assertEqual(res, res2)

            res = jdb.find(ANY={'$has': 'python'})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            # tags contains 'python' AND 'linux'
            res = jdb.find(vals={'tags': {'$and' : [{'$has':'python'}, {'$has':'linux'}]}})
            self.assertEqual(set(res), {'user_3'})

            res2 = jdb.find(vals={'tags.$has':'python', 'tags.!$nhas':'linux'})
            self.assertEqual(set(res), {'user_3'})

            res2 = jdb.find(vals={'tags.$has':'python', ' tags.$has':'linux'})
            self.assertEqual(set(res), {'user_3'})

            # ANY contains 'Bo'
            res = jdb.find(ANY={'$has': 'Bo'})
            self.assertEqual(set(res), {'user_2'})

            res2 = jdb.find(ANY={'$ihas': 'bo'})
            self.assertEqual(res, res2)

            # Age is NOT 30
            res = jdb.find(vals={'age': {'$ne': 30}})
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res2 = jdb.find(vals={'!age': 30})
            self.assertEqual(res, res2)

            res = jdb.find(ANY={'$ne': 30})
            self.assertEqual(set(res), {'user_2', 'user_3', 'user_4'})

            res2 = jdb.find(vals={'!$any': 30})
            self.assertEqual(res, res2)

            # Age is 28
            res = jdb.find(vals={'age': {'$eq': 28}})
            self.assertEqual(set(res), {'user_4'})

            res2 = jdb.find(vals={'!age': {'!$eq': 28}})
            self.assertEqual(res, res2)

            res2 = jdb.find(ANY={'$eq': 28})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'age': 28}) # vals['age'] == 28
            self.assertEqual(res, res2)

            # 40 >= Age > 25
            res = jdb.find(vals={'age': {'$gt': 25, '$lte':40}})
            self.assertEqual(set(res), {'user_1', 'user_3', 'user_4'})

            res2 = jdb.find(vals={'age.$gt': 25, 'age.$le':40})
            self.assertEqual(res, res2)

            # 26 <= Age <= 40
            res2 = jdb.find(ANY={'$between': (26, 40)})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'age': {'$between': (26, 40)}})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'age.$between': (26, 40)})
            self.assertEqual(res, res2)

            # 40 > Age > 25 and KEY in ['user_1', 'user_4']
            res = jdb.find(vals={'_id': ['user_1', 'user_4'], 'age': {'$gt': 25, '$lte':40}})
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # 40 > Age > 25 and key in ['user_1', 'user_4'] and created date <= date(2010, 1, 1)
            res = jdb.find(vals={'_id': ['user_1', 'user_4'], '_date': {'$lt': dt_2010}, 'age': {'$gt': 25, '$lte':40}})
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find({'$ew': ('_1', '_4')}, date={'$lt': dt_2010}, vals={'age.$between': (26, 40)})
            self.assertEqual(res, res2)

            res = jmem.find(vals={'$key': ['user_1', 'user_4'], '$date': {'$lt': dt_2010}, 'age': {'$gt': 25, '$lte':40}})
            self.assertEqual(set(res), {'users:::user_1'})

            res2 = jmem.find(vals={'$key': ''}, limit=1)
            self.assertEqual(res, res2)

            res = jmem.find(vals={'$key': ''}, limit=1, skip=1)
            self.assertNotEqual(set(res), {'users:::user_1'})

            # not 40 >= Age > 25
            res = jdb.find(NOT={'age': {'$gt': 25, '$lte':40}})
            self.assertEqual(set(res), {'user_2'})

            res2 = jdb.find(vals={'!age.$between': (26, 40)})
            self.assertEqual(res, res2)

            # name in ['Alice', 'Bob'] AND age in [30, 25]
            res = jdb.find(vals={'name':re.compile('Alice|Bob'), 'age':[30, 25]})
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res2 = jdb.find(vals={'n*e':re.compile(r'Alice|Bob'), 'age':[30, 25]})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'n??e':re.compile(r'Alice|Bob'), 'age':[30, 25]})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'n?me.$match':re.compile(r'Alice|Bob'), 'age':[30, 25]})
            self.assertEqual(res, res2)

            res2 = jdb.show(vals={'name':re.compile('Alice|Bob'), 'age':[30, 25]}, skip=1)
            self.assertEqual(set(res2), {'user_2'})

            res2 = jdb.show(vals={'name':re.compile('Alice|Bob'), 'age':[30, 25]})
            self.assertEqual(res, res2)

            res2 = jmem.show(vals={'name':re.compile('Alice|Bob'), 'age':[30, 25]}, with_date=True)
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            # 3. Logical Grouping (AND, OR, NOR, NOT)
            #----------------------------------------------------------
            # Age >= 25 AND Age <= 30
            res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}])
            self.assertEqual(set(res), {'user_1', 'user_2', 'user_4'})

            res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}], limit=1, skip=1)
            self.assertEqual(set(res), {'user_2'})

            # Role is 'admin' OR Age > 30
            res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.find(NAND=[{'role': {'!$eq': 'admin'}}, {'age': {'!$gt': 30}}])
            self.assertEqual(res, res2)

            res2 = jdb.find(NAND=[{'!role': 'admin'}, {'!age': {'$gt': 30}}])
            self.assertEqual(res, res2)

            res2 = jdb.find(NAND=[{'!role': 'admin'}, {'!age.$gt': 30}])
            self.assertEqual(res, res2)

            # Role is not 'admin' AND Age <= 30
            res = jdb.find(NOR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
            self.assertEqual(set(res), {'user_2', 'user_4'})

            res2 = jmem.find(NOR=[{'role': 'admin'}, {'age.$gt': 30}])
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            # User is NOT a developer
            res = jdb.find(NOT={'role': 'developer'})
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # (Role is 'admin' OR Age > 30) AND 'linux' not in tags
            res = jdb.find(AND=[
               {'$or': [
                  {'role':{'$eq': 'admin'}},
                  {'age': {'$gt': 30}}
               ]},
               {'$not': {'tags': {'$has': 'linux'}}}
            ])
            self.assertEqual(set(res), {'user_1'})

            res2 = jdb.find(AND=[
                {'$or': [
                    {'role': 'admin'},
                    {'age.$gt': 30}
                ]},
                {'!tags.$has': 'linux'},
            ])
            self.assertEqual(res, res2)

            # 4. Regular Expressions (RE, RE2, re.compile)
            #----------------------------------------------------------
            # Values matching an email domain regex
            res = jdb.find(vals={'email': {'$re':r'.@example.com'}})
            self.assertEqual(set(res), {'user_1'})

            # Find users where any attribute exactly matches regex
            res = jdb.find(ANY=re.compile(r'.@example.com'))
            self.assertEqual(set(res), {'user_1'})

            # Global regex search for strings containing 'li' (matches 'Alice', 'Charlie', 'linux')
            res = jdb.find(RE=r'li[a-z]')
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.find(vals={'!$re': r'li[a-z]'})
            self.assertEqual(set(res2), {'user_2', 'user_4'})

            # Match specific Database Keys using compiled regex (e.g., matching 'user_1', 'user_2')
            res = jdb.find(re.compile(r'^user_[1-2]$'), with_value=True)
            self.assertEqual(set(res), {'user_1', 'user_2'})

            res2 = jdb.show(re.compile(r'^user_[1-2]$'), with_date=True)
            self.assertEqual(res, res2)

            res2 = jmem.show(vals={'$key': re.compile(r'^user_[1-2]$')}, with_date=True)
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            # 5. Array / List Operations
            #----------------------------------------------------------
            # Users with exactly 2 tags in their list
            res = jdb.find(vals={'tags': {'$size': 2}})
            self.assertEqual(set(res), {'user_1', 'user_2', 'user_4'})

            # Users whose FIRST tag (index 0) is 'python'
            res = jdb.find(vals={'tags': {'$0': 'python'}})
            self.assertEqual(set(res), {'user_1', 'user_3'})

            res2 = jdb.show(vals={'tags': {'$0': 'python'}})
            self.assertEqual(res, res2)

            res2 = jmem.show(vals={'tags': {'$0': 'python'}}, with_date=True)
            self.assertEqual({f'users:::{kk}':vv for kk,vv in res.items()}, res2)

            res = jdb.find(vals={'tags': {'!$0': 'python'}})
            self.assertEqual(set(res), {'user_2', 'user_4'})

            # 6. Lambda / Custom Functions (FUNC) & Pagination (limit)
            #----------------------------------------------------------
            # Pass a lambda to evaluate both the key and the value dynamically
            # Example: Find the first users whose age is an even number
            res = jdb.find(
                FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0,
                limit=1)
            self.assertTrue(set(res), {'user_1'})

            # Users has email
            res = jdb.find(vals={'email': lambda v: v != ''})
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # Users don't have email
            res = jdb.find(NOT={'email': lambda v: v != ''})
            self.assertEqual(set(res), {'user_2', 'user_3'})

            #----------------------------------------------------------
            jdb += {
                'user_5': {
                    'name': 'Eva','age': 32, 'email': 'eva@company_a.com', 'role': 'officer',
                    'addr_home': {'city': 'NYC', 'zip': 10001}, 'addr_work': {'city': 'LA'},
                    'meta': {'tags': ['db', 'excel'], 'labels': ['backend', 'api']}, 'scores': [85.1, 90.2, 78.3]},
                'user_6': {
                    'name': 'Fiona', 'age': 44, 'email': 'fiona@company_b.com', 'role': 'CEO',
                    'addr_home': {'city': 'Tokyo', 'zip':4000}, 'addr_work': {'city': 'HK', 'zip': 5001},
                    'meta': {'tags': ['python', 'excel'], 'labels': ['api', 'frontend']}, 'scores': [92.4, 95.5, 99.6]}
            }

            # int(scores[0]) == 92
            res = jdb.find(vals={'scores.$first.$int': 92})
            self.assertEqual(set(res), {'user_6'})

            # int(scores[-1]) <= 90
            res = jdb.find(vals={'scores.$last.$le': 90})
            self.assertEqual(set(res), {'user_5'})

            # average(scores) >= 90
            res = jdb.find(vals={'scores.$avg.$ge': 90})
            self.assertEqual(set(res), {'user_6'})

            # max(scores) > 90.2
            res = jdb.find(vals={'scores.$max.$gt': 90.2})
            self.assertEqual(set(res), {'user_6'})

            # max(scores) == 99
            res = jdb.find(vals={'scores.$max.$int': 99})
            self.assertEqual(set(res), {'user_6'})

            res2 = jdb.find(vals={'scores.$max.$floor.$str': '99'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'scores.$ceil.$max': 100})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'scores.$round.$max': 100})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'scores.$floor.$max': 99})
            self.assertEqual(res, res2)

            # max(scores) in [90, 88]
            res = jdb.find(vals={'scores.$max.$int': [90, 99]})
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(vals={'scores.$str.$float.$int.$max': [90, 99]})
            self.assertEqual(res, res2)

            # min(scores) <= 80
            res = jdb.find(vals={'scores.$min.$lte': 80})
            self.assertEqual(set(res), {'user_5'})

            # 91 >= mid(scores) >= 90
            res = jdb.find(vals={'scores.$mid.$between': (90,91)})
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(vals={'scores.$sort.$mid.$int': 85})
            self.assertEqual(res, res2)

            # sum(scores) < 270
            res = jdb.find(vals={'scores.$sum.$lt': 270})
            self.assertEqual(set(res), {'user_5'})

            # abs(std(scores)) > 0
            res = jdb.find(vals={'scores.$std.$abs.$gt': 0.})
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(vals={'scores.$std.$neg.$abs.$gt': 0.})
            self.assertEqual(res, res2)

            # len(tags) > 2
            res = jdb.find(vals={'tags.$len': 3})
            self.assertEqual(set(res), {'user_3'})

            # city name == 'NYC'
            res = jdb.find(vals={'addr*.city': 'NYC'})
            self.assertEqual(set(res), {'user_5'})

            # city name start with 'L'
            res2 = jdb.find(vals={'addr*.city': {'$sw': 'L'}})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'*.city.$sw': 'L'})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'*.c???.$sw': 'L'})
            self.assertEqual(res, res2)

            # find frontend in meta field
            res = jdb.find(vals={'meta.**': 'frontend'})
            self.assertEqual(set(res), {'user_6'})

            # 'meta' exists and not city == Tokyo
            res = jdb.find(vals={'!addr*.city': 'Tokyo'}, EXISTS='meta')
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(vals={'!*.city.$eq': 'Tokyo', '$exists':'meta'})
            self.assertEqual(res, res2)

            # 'email' exists
            res = jdb.find(EXISTS='email')
            self.assertEqual(set(res), {'user_1', 'user_4', 'user_5', 'user_6'})

            # both 'email' and 'meta' exist
            res = jdb.find(EXISTS=('email', 'meta'))
            self.assertEqual(set(res), {'user_5', 'user_6'})

            # city name start with 'L' or 'H'
            res = jdb.find(vals={'addr*.city': {'$sw': ('L', 'H')}})
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(vals={'*.city.!$sw': ('A', 'B')})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'addr*|ci*|$sw': ('L', 'H')})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'addr*/ci*/$sw': ('L', 'H')})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'addr*\\ci*\\$sw': ('L', 'H')})
            self.assertEqual(res, res2)

            # zip code >= 5000
            res2 = jdb.find(vals={'addr*.zip': {'$ge': 5000}})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'a*|zip|$ge': 5000})
            self.assertEqual(res, res2)

            # addr_home.zip >= 5000
            res = jdb.find(vals={'addr_home.zip': {'$ge': 5000}})
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(vals={'a*_h*|z*|!$lt': 5000})
            self.assertEqual(res, res2)

            # meta.tags[0] == 'python' or meta.labels[0] == 'python'
            res = jdb.find(vals={'meta.*.0': 'python'})
            self.assertEqual(set(res), {'user_6'})

            # meta.tags[-1] == 'api' or meta.labels[-1] == 'api'
            res = jdb.find(vals={'meta.*.-1': 'api'})
            self.assertEqual(set(res), {'user_5'})

            # meta.tags[0].endswith(('b', 'i')) or meta.labels[0].endswith(('b', 'i'))
            res = jdb.find(vals={'meta.*.0': {'$ew': ('b', 'i')}})
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(vals={'m*a.*.0.$ew': ('b', 'i')})
            self.assertEqual(res, res2)

            # 'db' in meta.tags
            res = jdb.find(vals={'meta.tags.*': 'db'})
            self.assertEqual(set(res), {'user_5'})

            res = jdb.find(vals={'meta.tags.*': {'$ew': ('b', 'i')}})
            self.assertEqual(set(res), {'user_5'})

            res2 = jdb.find(vals={'me*.tags.*.$ew': ('b', 'i')})
            self.assertEqual(res, res2)

            res2 = jdb.find(vals={'?et*.tag?.*.$ew': ('b', 'i')})
            self.assertEqual(res, res2)

            # any(socre >= 90 for score in scores)
            res = jdb.find(vals={'scores.*': {'$gte': 90}})
            self.assertEqual(set(res), {'user_5', 'user_6'})

            res2 = jdb.find(vals={'sco*.*.$ge': 90})
            self.assertEqual(res, res2)

            # any(score > 95 for score in scores)
            res = jdb.find(vals={'scores.*': {'$gt': 95}})
            self.assertEqual(set(res), {'user_6'})

            res2 = jdb.find(vals={'*ores.*.!$le': 95})
            self.assertEqual(res, res2)

            res = jdb.update_if({'role.$ew': 'admin'}, {'role':'Administrator'})
            self.assertEqual(res, 1)

            res = jdb.update_if({'role.$ew': 'admin'}, {'role':'Administrator'})
            self.assertEqual(res, 0)

            res = jdb.find(vals={'role.$has':'trator'})
            self.assertEqual(set(res), {'user_1'})

            res = jdb.find(vals={'age.$ge':45})
            self.assertEqual(len(res), 0)

            # update age and insert license
            res = jdb.update_if({'!age.$ge':45}, lambda key,old_val:{'age':old_val['age']+1, 'license':old_val.get('expired', old_val['age']+1 >= 45)})
            self.assertEqual(res, 6)

            res = jdb.find(vals={'age.$ge':45})
            self.assertEqual(set(res), {'user_6'})

            res2 = jdb.find(vals={'license':True})
            self.assertEqual(res, res2)

            # delete age in [26, 36]
            n_users = len(jdb)
            res = jdb.update_if({'age':[26, 36]}, None)
            self.assertEqual(res, 2)
            self.assertEqual(len(jdb), n_users - res)

            res = jdb.find(EXISTS='tags')
            self.assertEqual(set(res), {'user_1', 'user_4'})

            # delete tags and update age
            res2 = jdb.update_if({'$exists': 'tags'}, lambda key,old_val:{'tags': None, 'age':old_val['age']+1})
            self.assertEqual(res2, 2)

            res = jdb.find(EXISTS='tags')
            self.assertEqual(len(res), 0)
            #----------------------------------------------------------
            del jdb[:]
            users = [{'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'author', 'tags':['Java']},
                        {'name': 'Bob', 'age': 25, 'role': 'helper'},
                        {'name': 'Charlie', 'age': 35, 'tags' :['python', 'programming']}]

            jdb += users
            self.assertEqual(len(jdb), 3)

            matches = jdb.find(EXISTS='email')
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})

            matches = jdb.find(EXISTS=['age', 'tags'])
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Charlie'})

            matches = jdb.find(vals={'!$exists': ['age', 'tags']})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob'})

            matches = jdb.find(ANY={'name': 'Alice'})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})
            matches_2 = jdb.find(ANY='Alice')
            self.assertEqual(matches, matches_2)

            # name contains 'li[a-e]' regex
            matches = jdb.find(vals={'name': re.compile(r'li[a-z]')})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Charlie'})

            matches_2 = jdb.find(ANY=re.compile(r'li[a-z]'))
            self.assertEqual(matches, matches_2)

            matches = jdb.find(ANY=re.compile(r'li[a-z]'), limit=1)
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})

            # any contains r'ob'
            matches = jdb.find(ANY=re.compile(r'ob'))
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob'})

            # with email
            matches = jdb.find(vals={'email': re.compile(r'[a-z]@[a-z]')})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})

            # without email
            matches = jdb.find(NOT={'email': lambda v: v != ''})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob', 'Charlie'})

            # age >= 30
            matches = jdb.find(vals={'age': {'$le': 30}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Bob'})

            matches_2 = jdb.find(ANY={'$le': 30})
            self.assertEqual(matches, matches_2)

            # age == 30
            matches = jdb.find(vals={'age': {'$eq': 30}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})
            matches_2 = jdb.find(vals={'age': 30})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(ANY={'age': 30})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(RE=r'\D30\D')
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(ANY=30)
            self.assertEqual(matches, matches_2)

            # age != 30
            matches = jdb.find(vals={'age': {'$ne':30}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob', 'Charlie'})
            matches_2 = jdb.find(RE=r'\D\d\d(?<!30)')
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(vals={'!age': 30})
            self.assertEqual(matches, matches_2)

            # age in [25, 35]
            matches = jdb.find(ANY={'age': {'$in': [25, 35]}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob', 'Charlie'})
            matches_2 = jdb.show(ANY={'age': {'$in': [25, 35]}})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(vals={'age': [25, 35]})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(ANY={'$in': [25, 35]})
            self.assertEqual(matches, matches_2)
            matches_2 = jmem.find(ANY={'$in': [25, 35]})
            self.assertEqual({f'users:::{kk}':vv for kk,vv in matches.items()}, matches_2)

            # age not in [25, 35]
            matches = jdb.find(vals={'$not': {'age': {'$in': [25, 35]}}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})
            matches_2 = jdb.find(NOT={'age': [25, 35]})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(vals={'!age': [25, 35]})
            self.assertEqual(matches, matches_2)

            # age != 30
            matches = jdb.find(NOT={'age':30})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob', 'Charlie'})

            matches_2 = jdb.find(vals={'!age':30})
            self.assertEqual(matches, matches_2)

            # 35 >= age >= 25
            matches = jdb.find(vals={'$and': [
                {'age':{'$ge': 25}},
                {'age':{'$le': 35}}
            ]})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Bob', 'Charlie'})

            matches_2 = jdb.find(AND=[
                {'age':{'$gte': 25}},
                {'age':{'$lte': 35}}
            ])
            self.assertEqual(matches, matches_2)

            matches_2 = jdb.find(vals={'age': {'$gte': 25 , '$lte': 35}})
            self.assertEqual(matches, matches_2)

            # age < 25 or age > 35
            matches = jdb.find(vals={'$or': [
                {'age':{'$lt': 25}},
                {'age':{'$gt': 35}}
            ]})
            self.assertEqual(len(matches), 0)

            matches_2 = jdb.find(OR=[
                {'age':{'$lt': 25}},
                {'age':{'$gt': 35}}
            ])
            self.assertEqual(matches, matches_2)

            matches_2 = jdb.find(NAND=[
                {'age':{'!$lt': 25}},
                {'age':{'!$gt': 35}}
            ])
            self.assertEqual(matches, matches_2)

            # age == 25 or role != '' or name[:2] == 'Bo'
            matches = jdb.find(OR=[{'age': 25}, {'role':re.compile(r'.')}, {'name':re.compile(r'^Bo')}])
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Bob'})

            # not age >= 19
            matches = jdb.find(NOT={'age': {'$gte': 18}})
            self.assertEqual(len(matches), 0)
            matches_2 = jdb.find(vals={'age': {'!$gte': 18}})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(vals={'!age': {'$ge': 18}})
            self.assertEqual(matches, matches_2)

            # len(tags) == 2
            matches = jdb.find(vals={'tags': {'$size': 2}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Charlie'})
            matches_2 = jdb.find(ANY={'$size': 2})
            self.assertEqual(matches, matches_2)

            # len(tags) in [1,2]
            matches = jdb.find(vals={'tags': {'$size': [1,2,3]}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Charlie'})

            # tags[0] == 'Java'
            matches = jdb.find(vals={'tags': {'$0': 'Java'}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})
            matches_2 = jdb.find(ANY={'$0': 'Java'})
            self.assertEqual(matches, matches_2)

            matches = jdb.find(vals={'tags': {'$1': 'programming'}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Charlie'})
            matches_2 = jdb.find(ANY={'$1': 'programming'})
            self.assertEqual(matches, matches_2)

            matches = jdb.find(vals={'tags': {'$2': 'database'}})
            self.assertEqual({vv['name'] for vv in matches.values()}, set())

            def add_tag(_key, val, new_tag):
                tags = val['tags']
                if new_tag not in tags:
                    val = val.copy()
                    tags = tags.copy()
                    tags.append(new_tag)
                    val['tags'] = tags

                return val

            # add 'database' to tags for matched records
            jdb[matches_2] = lambda key,val: add_tag(key, val, 'database')
            matches = jdb.find(ANY={'$2': 'database'})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Charlie'})
            # --------------------------------------
            jmem1 = jmem.add_group('other')
            jmem1 += {'key1':[1, 2, 3, 4], 'key2':[0, 9, 8, 7, 6], 'key3':[0, 6, 2, 2]}
            matches = jmem1.find(ALL={'$ne':0})
            self.assertEqual(set(matches), {'key1'})

            matches = jmem1.find('key', ANY={'$ne':0})
            self.assertEqual(set(matches), {'key1', 'key2', 'key3'})

            # 2 in Value
            matches = jmem1.find(HAS=2)
            self.assertEqual(set(matches), {'key1', 'key3'})

            # 2 not in Value
            matches = jmem1.find(NHAS=2)
            self.assertEqual(set(matches), {'key2'})

            jmem1 += {str(v):v for v in range(10)}

            matches = jmem1.find(5, with_value=True)
            self.assertEqual(matches['5'], jmem1['5'])

            matches_2 = jmem1.find(vals=lambda k,v: k == '5' and v == 5)
            self.assertEqual(matches, matches_2)

            matches_2 = jmem1.find(vals=lambda v: v == 5)
            self.assertEqual(matches, matches_2)

            matches_2 = jmem1.find(vals=5)
            self.assertEqual(matches, matches_2)

            matches_2 = jmem1.find(vals=[5,15,25])
            self.assertEqual(matches, matches_2)

            matches = jmem1.find(vals=range(5, 10))
            self.assertEqual(matches, jmem1[5,6,7,8,9])

            matches_2 = jmem1.find(vals=re.compile(r'^[5-9]$'))
            self.assertEqual(matches, matches_2)

            matches = jmem1.find(vals={'$len': {'$gt': 3}})
            self.assertEqual(set(matches), {'key1', 'key2', 'key3'})

            matches_2 = jmem1.find(vals={'$len.$gt': 3})
            self.assertEqual(matches, matches_2)

            # int(KEY) % 3 == 1
            matches = jmem1.find({'$mod': (3, 1)})
            self.assertEqual(set(matches), {'1', '4', '7'})

            # 2 <= int(KEY) <= 4
            matches = jmem1.find({'$between': (2, 4)})
            self.assertEqual(set(matches), {'2', '3', '4'})

            # int(KEY) near 3 +/- 1
            matches_2 = jmem1.find({'$near': (3, 1)})
            self.assertEqual(matches, matches_2)

            matches = jmem1.find(TYPE='list')
            self.assertEqual(set(matches), {'key1', 'key2', 'key3'})

            matches = jmem1.find(AND=[{'$type':list}, {'$size': 4}])
            self.assertEqual(set(matches), {'key1', 'key3'})

            matches = jmem1.find(AND=[{'!$type':list}, {'$ge': 8}])
            self.assertEqual(set(matches), {'8', '9'})

            jmem1[:] = lambda k,v: (v + [v[-1], v[0]]) if isinstance(v, list) else v
            matches = jmem1.find(vals={'$last': 0})
            self.assertEqual(set(matches), {'key2', 'key3'})

            matches_2 = jmem1.find(vals={'$first': 0})
            self.assertEqual(matches, matches_2)

            matches = jmem1.find(AND=[{'$type':list}, {'$size': 6}])
            self.assertEqual(set(matches), {'key1', 'key3'})

            matches = jmem1.find(vals={'$unique.$size': 4})
            self.assertEqual(set(matches), {'key1'})

            jmem1['key4'] = [[1,2], [3,4], [5,6], [2,4]]
            matches = jmem1.find(vals={'$flat.$unique.$len.$ge': 6})
            self.assertEqual(set(matches), {'key4'})

            jmem1 += {f'1st_{v}':{f'2nd_{vv}':{f'3rd_{vvv}':vvv for vvv in range(vv+2)} for vv in range(v+1)} for v in range(8)}
            matches = jmem1.show('1st_', vals={'2nd_4.3rd_3': range(6)})
            self.assertEqual(set(matches), {'1st_4', '1st_5', '1st_6', '1st_7'})

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_csv(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['group'] = jdb1 = JDb(jdb)

            csv_file = 'db/test.csv'
            jdb += {'key1':1, 'key2':'a', 'key3':3., 'key4':True, 'key5':None}
            jdb.to_csv(csv_file)
            with open(csv_file, 'rt', encoding='utf8') as fp:
                print(fp.read())

            jdb.show(with_date=True)

            jmem2 = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem2.from_csv(csv_file)
            self.assertEqual(set(jdb), set(jmem2))
            self.assertNotEqual(jdb, jmem2)

            del jdb[:]
            jdb += {'key1':[1, 2], 'key2':('a', 'b'), 'key3':[3., 4.], 'key4':[True, False], 'key5':[5, 'a', 6.], 'key6':['value']}
            jdb.to_csv(csv_file)

            jdb.show()

            # jmem2 = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem2.from_csv(csv_file)
            self.assertEqual(set(jdb), set(jmem2))
            self.assertNotEqual(jdb, jmem2)
            self.assertTrue(all(len(v) == 3 for v in jmem2.values()))

            del jdb[:]
            del jmem2[:]
            expect = {f'key{v}': {
                        'str':f'value-{v:03d}'*((v%100)+1),
                        'list':str([random.randrange(v+100) for _ in range(32)]),
                        'float1':str(1.1),
                        'float2':str(-1.),
                        'bool': str(True),
                        'max_int':str(2**64-1),
                        'min_int':str(-(2**63))} for v in range(8)}

            jdb += expect
            jdb.to_csv(csv_file)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(jmem2, expect)

            jmem2.from_csv(csv_file)
            self.assertEqual(jmem2, expect)
            self.assertEqual(jmem2, jdb)

            del jdb[:]
            csv_example = '_id,name,age\n0,Alice,30\n1,Bob,25\n2,Charlie,35\n'
            with io.StringIO(csv_example) as fp:
                jdb.from_csv(fp)

            self.assertEqual(len(jdb), 3)

            matches = jdb.find(ANY={'name': 'Alice'})
            self.assertEqual(len(matches), 1)

            jdb.show(ANY={'name': 'Alice'})

            # name contains 'li[a-e]' regex
            matches = jdb.find(vals={'name': re.compile(r'li[a-z]')})
            self.assertEqual(len(matches), 2)

            jdb.show(vals={'name': re.compile(r'li[a-z]')})

            matches_2 = jdb.find(ANY=re.compile(r'li'))
            self.assertEqual(matches, matches_2)

            jdb.show(ANY=re.compile(r'li'))

            matches_3 = jdb.find(ANY=re.compile(r'o'))
            self.assertEqual(set(jdb), set(matches_2).union(matches_3))

            jdb.show(ANY=re.compile(r'o'))

            # age start with 3x
            matches = jdb.find(ANY={'age': {'$re':r'^3\d$'}})
            self.assertEqual(len(matches), 2)

            jdb.show(ANY={'age': {'$re':r'^3\d$'}})

            del jmem2[:]
            with io.StringIO() as fp:
                jdb.to_csv(fp)
                jmem2.from_csv(fp)
            self.assertEqual(jdb, jmem2)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jmem.recycle(level=2)
            error = jmem.check_error(level=2)
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_group_key(self):
        remote_jdb_mem0 = self.server0.jdb
        remote_jdb_disk = self.server1.jdb
        remote_jdb_mem = self.server2.jdb

        remote_jdb_net = JDb(JNetFiles(self.server0.server_address))
        local_jdb_disk = JDb(JNetFiles(self.server1.server_address))
        local_jdb_mem = JDb(JNetFiles(self.server2.server_address))

        self.assertEqual(len(remote_jdb_disk), 0)
        self.assertEqual(len(remote_jdb_mem), 0)
        self.assertEqual(len(local_jdb_disk), 0)
        self.assertEqual(len(local_jdb_mem), 0)

        self.assertEqual(len(remote_jdb_disk.groups), 0)
        self.assertEqual(len(remote_jdb_mem.groups), 0)
        self.assertEqual(len(local_jdb_disk.groups), 0)
        self.assertEqual(len(local_jdb_mem.groups), 0)

        tmp_data = {f'key{v}':list(range(v+1)) for v in range(32)}
        tmp_jdb = remote_tmp_disk = JDb('db/remote.jdb', flags=0) # disk
        tmp_jdb -= tmp_jdb
        remote_tmp_disk += tmp_data

        remote_jdb_disk['key'] = 1000
        remote_jdb_mem['key'] = 2000

        remote_jdb_disk['disk'] = remote_tmp_disk
        remote_jdb_mem['disk'] = remote_tmp_disk
        self.assertEqual(remote_tmp_disk, tmp_data)
        self.assertEqual(len(remote_jdb_disk.groups), 1)
        self.assertEqual(len(remote_jdb_mem.groups), 1)

        remote_tmp_mem = JDb()          # mem
        remote_tmp_mem[tmp_data] = 1

        remote_jdb_disk['mem'] = remote_tmp_mem
        remote_jdb_mem['mem'] = remote_tmp_mem
        self.assertEqual(len(remote_tmp_mem), len(tmp_data))
        self.assertEqual(len(remote_jdb_disk.groups), 2)
        self.assertEqual(len(remote_jdb_mem.groups), 2)

        remote_group_disk = remote_jdb_disk.add_group('group') # group
        remote_group_disk[tmp_data] = 2
        self.assertEqual(len(remote_group_disk), len(tmp_data))

        remote_group_mem = remote_jdb_mem.add_group('group') # group
        remote_group_mem[tmp_data] = 3
        self.assertEqual(len(remote_group_mem), len(tmp_data))
        self.assertEqual(len(remote_jdb_disk.groups), 3)
        self.assertEqual(len(remote_jdb_mem.groups), 3)

        self.assertEqual(remote_jdb_disk['disk'][:], tmp_data)
        self.assertEqual(remote_jdb_disk['mem'[:]], remote_tmp_mem)
        self.assertEqual(remote_jdb_disk['group'][:], remote_group_disk)

        self.assertEqual(remote_jdb_mem['disk'][:], tmp_data)
        self.assertEqual(remote_jdb_mem['mem'][:], remote_tmp_mem)
        self.assertEqual(remote_jdb_mem['group'][:], remote_group_mem)

        remote_jdb_disk2 = JDb(remote_jdb_disk)
        self.assertEqual(remote_jdb_disk2, remote_jdb_disk)

        remote_jdb_mem2 = JDb(remote_jdb_mem)
        self.assertEqual(remote_jdb_mem2, remote_jdb_mem)

        self.assertEqual(len(remote_jdb_disk2.groups), 3)
        self.assertEqual(len(remote_jdb_mem2.groups), 3)

        self.assertEqual(local_jdb_disk['key'], 1000)
        self.assertEqual(local_jdb_disk['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_disk['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_disk['group'][:], remote_group_disk[:])

        self.assertEqual(local_jdb_mem['key'], 2000)
        self.assertEqual(local_jdb_mem['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_mem['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_mem['group'][:], remote_group_mem[:])

        self.assertEqual(len(local_jdb_disk.groups), 3)
        self.assertEqual(len(local_jdb_mem.groups), 3)

        local_jdb_disk2 = JDb(local_jdb_disk)
        self.assertEqual(local_jdb_disk2, local_jdb_disk)
        self.assertEqual(local_jdb_disk2['disk'][:], local_jdb_disk['disk'][:])
        self.assertEqual(local_jdb_disk2['mem'][:], local_jdb_disk['mem'][:])
        self.assertEqual(local_jdb_disk2['group'][:], local_jdb_disk['group'][:])
        self.assertEqual(local_jdb_disk2['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_disk2['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_disk2['group'][:], remote_group_disk[:])

        local_jdb_mem2 = JDb(local_jdb_mem)
        self.assertEqual(local_jdb_mem2, local_jdb_mem)
        self.assertEqual(local_jdb_mem2['disk'][:], local_jdb_mem['disk'][:])
        self.assertEqual(local_jdb_mem2['mem'][:], local_jdb_mem['mem'][:])
        self.assertEqual(local_jdb_mem2['group'][:], local_jdb_mem['group'][:])
        self.assertEqual(local_jdb_mem2['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_mem2['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_mem2['group'][:], remote_group_mem[:])

        self.assertEqual(len(local_jdb_disk2.groups), 3)
        self.assertEqual(len(local_jdb_mem2.groups), 3)

        local_tmp_disk = JDb('db/local.jdb', flags=0) # disk2
        local_tmp_disk -= local_tmp_disk
        local_tmp_disk.recycle()
        local_tmp_disk[tmp_data] = 4

        local_tmp_mem = JDb()                # mem2
        local_tmp_mem[tmp_data] = 5

        local_jdb_disk['disk2'] = local_tmp_disk # clone
        local_jdb_disk['mem2'] = local_tmp_mem   # clone
        local_group_disk = local_jdb_disk.add_group('group2') # group2
        local_group_disk[tmp_data] = 6
        self.assertTrue(isinstance(local_tmp_disk.files_obj, JDiskFiles))
        self.assertTrue(isinstance(local_tmp_mem.files_obj, JMemFiles))
        self.assertTrue(isinstance(local_group_disk.files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['disk2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['mem2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['group2'].files_obj, JNetFiles))

        self.assertEqual(local_jdb_disk['disk2'][:], local_tmp_disk[:])
        self.assertEqual(local_jdb_disk['mem2'][:], local_tmp_mem[:])
        self.assertEqual(local_jdb_disk['group2'][:], local_group_disk[:])
        self.assertEqual(remote_jdb_disk['disk2'][:], local_tmp_disk[:])
        self.assertEqual(remote_jdb_disk['mem2'][:], local_tmp_mem[:])
        self.assertEqual(remote_jdb_disk['group2'][:], local_group_disk[:])

        local_jdb_mem['disk2'] = local_tmp_disk # clone
        local_jdb_mem['mem2'] = local_tmp_mem   # clone

        local_group_mem = local_jdb_mem.add_group('group2') # group2
        local_group_mem[tmp_data] = 7

        self.assertTrue(isinstance(local_tmp_disk.files_obj, JDiskFiles))
        self.assertTrue(isinstance(local_tmp_mem.files_obj, JMemFiles))
        self.assertTrue(isinstance(local_group_mem.files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['disk2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['mem2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['group2'].files_obj, JNetFiles))

        self.assertEqual(local_jdb_mem['disk2'][:], local_tmp_disk[:])
        self.assertEqual(local_jdb_mem['mem2'][:], local_tmp_mem[:])
        self.assertEqual(local_jdb_mem['group2'][:], local_group_mem[:])
        self.assertEqual(remote_jdb_mem['disk2'][:], local_tmp_disk[:])
        self.assertEqual(remote_jdb_mem['mem2'][:], local_tmp_mem[:])
        self.assertEqual(remote_jdb_mem['group2'][:], local_group_mem[:])

        self.assertEqual(len(local_jdb_disk.groups), 6)
        self.assertEqual(len(local_jdb_mem.groups), 6)

        local_jdb_disk['key2'] = 3000
        local_jdb_mem['key2'] = 4000

        self.assertEqual(local_jdb_disk['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_disk['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_disk['group'][:], remote_group_disk[:])
        self.assertEqual(remote_jdb_disk['key2'], 3000)
        self.assertEqual(local_jdb_disk['disk2'][:], local_tmp_disk[:])   # XX
        self.assertEqual(local_jdb_disk['mem2'][:], local_tmp_mem[:])     # XX
        self.assertEqual(local_jdb_disk['group2'][:], local_group_disk[:])

        self.assertEqual(local_jdb_mem['disk2'][:], local_tmp_disk[:])      # XX
        self.assertEqual(local_jdb_mem['mem2'][:], local_tmp_mem[:])        # XX
        self.assertEqual(local_jdb_mem['group2'][:], local_group_mem[:])
        self.assertEqual(remote_jdb_mem['key2'], 4000)
        self.assertEqual(remote_jdb_mem['disk2'][:], local_jdb_disk['disk2'][:])     # XX
        self.assertEqual(remote_jdb_mem['mem2'][:], local_jdb_mem['mem2'][:])       # XX
        self.assertEqual(remote_jdb_mem['group2'][:], local_group_mem[:])

        self.assertEqual(set(remote_jdb_disk.groups), set(local_jdb_disk.groups))
        self.assertEqual(set(remote_jdb_mem.groups), set(local_jdb_mem.groups))

        self.assertNotEqual(id(local_tmp_mem), id(local_jdb_mem['mem2']))
        self.assertNotEqual(id(local_tmp_disk), id(local_jdb_mem['disk2']))
        self.assertNotEqual(id(local_tmp_mem), id(local_jdb_disk['mem2']))
        self.assertNotEqual(id(local_tmp_disk), id(local_jdb_disk['disk2']))

        self.assertEqual(local_jdb_mem['mem2'][:], local_jdb_disk['mem2'][:])
        self.assertEqual(local_jdb_mem['disk2'][:], local_jdb_disk['disk2'][:])

        local_jdb_disk['key'] = -1000
        local_jdb_mem['key'] = -2000
        local_group_mem[:] = -7     # group2
        local_group_disk[:] = -6    # group2
        local_jdb_disk['mem2'][:] = -5       # mem2
        local_jdb_disk['disk2'][:] = -4      # disk2
        local_jdb_mem['mem2'][:] = -5.1       # mem2
        local_jdb_mem['disk2'][:] = -4.1     # disk2

        self.assertNotEqual(local_jdb_mem['mem2'][:], local_jdb_disk['mem2'][:])
        self.assertNotEqual(local_jdb_mem['disk2'][:], local_jdb_disk['disk2'][:])

        remote_jdb_disk['key2'] = -3000
        remote_jdb_mem['key2'] = -4000
        remote_group_mem[:] = -3    # group
        remote_group_disk[:] = -2   # group
        remote_tmp_mem[:] = -1      # mem
        remote_tmp_disk[:] = 0      # disk

        self.assertEqual(local_jdb_disk['key2'], -3000)
        self.assertEqual(local_jdb_disk['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_disk['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_disk['group'][:], remote_group_disk[:])
        self.assertEqual(local_jdb_disk['group2'][:], local_jdb_disk['group2'][:])

        self.assertEqual(local_jdb_mem['key2'], -4000)
        self.assertEqual(local_jdb_mem['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_mem['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_mem['group'][:], remote_group_mem[:])
        self.assertEqual(local_jdb_mem['group2'][:], local_jdb_mem['group2'][:])

        self.assertEqual(remote_jdb_disk['key'], -1000)
        self.assertEqual(remote_jdb_disk['disk'][:], remote_tmp_disk[:])
        self.assertEqual(remote_jdb_disk['mem'][:], remote_tmp_mem[:])
        self.assertEqual(remote_jdb_disk['group'][:], remote_group_disk[:])
        self.assertEqual(remote_jdb_disk['disk2'][:], local_jdb_disk['disk2'][:])
        self.assertEqual(remote_jdb_disk['mem2'][:], local_jdb_disk['mem2'][:])
        self.assertEqual(remote_jdb_disk['group2'][:], local_jdb_disk['group2'][:])

        self.assertEqual(remote_jdb_mem['key'], -2000)
        self.assertEqual(remote_jdb_mem['disk'][:], remote_tmp_disk[:])
        self.assertEqual(remote_jdb_mem['mem'][:], remote_tmp_mem[:])
        self.assertEqual(remote_jdb_mem['group'][:], remote_group_mem[:])
        self.assertEqual(remote_jdb_mem['disk2'][:], local_jdb_mem['disk2'][:])
        self.assertEqual(remote_jdb_mem['mem2'][:], local_jdb_mem['mem2'][:])
        self.assertEqual(remote_jdb_mem['group2'][:], local_jdb_mem['group2'][:])

        self.assertEqual(local_jdb_disk2, local_jdb_disk)
        self.assertEqual(local_jdb_disk2['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_disk2['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_disk2['group'][:], remote_group_disk[:])
        self.assertEqual(local_jdb_disk2['disk2'][:], local_jdb_disk['disk2'][:])
        self.assertEqual(local_jdb_disk2['mem2'][:], local_jdb_disk['mem2'][:])
        self.assertEqual(local_jdb_disk2['group2'][:], local_group_disk[:])

        self.assertEqual(local_jdb_mem2, local_jdb_mem)
        self.assertEqual(local_jdb_mem2['disk'][:], remote_tmp_disk[:])
        self.assertEqual(local_jdb_mem2['mem'][:], remote_tmp_mem[:])
        self.assertEqual(local_jdb_mem2['group'][:], remote_group_mem[:])
        self.assertEqual(local_jdb_mem2['disk2'][:], local_jdb_mem['disk2'][:])
        self.assertEqual(local_jdb_mem2['mem2'][:], local_jdb_mem['mem2'][:])
        self.assertEqual(local_jdb_mem2['group2'][:], local_group_mem[:])

        self.assertEqual(remote_jdb_disk2, remote_jdb_disk)
        self.assertEqual(remote_jdb_disk2['disk'][:], remote_tmp_disk[:])
        self.assertEqual(remote_jdb_disk2['mem'][:], remote_tmp_mem[:])
        self.assertEqual(remote_jdb_disk2['group'][:], remote_group_disk[:])
        self.assertEqual(remote_jdb_disk2['disk2'][:], local_jdb_disk['disk2'][:])
        self.assertEqual(remote_jdb_disk2['mem2'][:], local_jdb_disk['mem2'][:])
        self.assertEqual(remote_jdb_disk2['group2'][:], local_group_disk[:])

        self.assertEqual(remote_jdb_mem2, remote_jdb_mem)
        self.assertEqual(remote_jdb_mem2['disk'][:], remote_tmp_disk[:])
        self.assertEqual(remote_jdb_mem2['mem'][:], remote_tmp_mem[:])
        self.assertEqual(remote_jdb_mem2['group'][:], remote_group_mem[:])
        self.assertEqual(remote_jdb_mem2['disk2'][:], local_jdb_mem['disk2'][:])
        self.assertEqual(remote_jdb_mem2['mem2'][:], local_jdb_mem['mem2'][:])
        self.assertEqual(remote_jdb_mem2['group2'][:], local_group_mem[:])

        remote_jdb_net[tmp_data] = 8
        _grp = remote_jdb_net.add_group('group')
        _grp[tmp_data] = 9

        remote_jdb_mem0['mem'] = _grp = JDb()
        _grp[tmp_data] = 10

        remote_jdb_mem0['disk'] = _grp = JDb('db/remote_net.jdb', flags=0) # disk
        _grp -= _grp
        _grp[tmp_data] = 11

        remote_jdb_disk['net'] = remote_jdb_net
        remote_jdb_mem['net'] = remote_jdb_net

        self.assertEqual(remote_jdb_disk['net'][:], remote_jdb_net[:])
        self.assertEqual(remote_jdb_disk['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(remote_jdb_disk['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(remote_jdb_disk['net']['disk'][:], remote_jdb_mem0['disk'][:])

        self.assertEqual(remote_jdb_mem['net'][:], remote_jdb_net[:])
        self.assertEqual(remote_jdb_mem['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(remote_jdb_mem['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(remote_jdb_mem['net']['disk'][:], remote_jdb_mem0['disk'][:])

        self.assertEqual(remote_jdb_disk2['net'][:], remote_jdb_net[:])
        self.assertEqual(remote_jdb_mem2['net'][:], remote_jdb_net[:])

        self.assertEqual(local_jdb_disk['net'][:], remote_jdb_net[:])
        self.assertEqual(local_jdb_disk['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(local_jdb_disk['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(local_jdb_disk['net']['disk'][:], remote_jdb_mem0['disk'][:])

        self.assertEqual(local_jdb_mem['net'][:], remote_jdb_net[:])
        self.assertEqual(local_jdb_mem['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(local_jdb_mem['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(local_jdb_mem['net']['disk'][:], remote_jdb_mem0['disk'][:])

        self.assertEqual(local_jdb_disk2['net'][:], remote_jdb_net[:])
        self.assertEqual(local_jdb_mem2['net'][:], remote_jdb_net[:])

        remote_jdb_net[tmp_data] = -8
        remote_jdb_mem0['group'][:] = -9
        remote_jdb_mem0['mem'][:] = -10
        remote_jdb_mem0['disk'][:] = -11

        self.assertEqual(remote_jdb_disk['net'][:], remote_jdb_net[:])
        self.assertEqual(remote_jdb_disk['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(remote_jdb_disk['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(remote_jdb_disk['net']['disk'][:], remote_jdb_mem0['disk'][:])
        self.assertEqual(remote_jdb_mem['net'][:], remote_jdb_net[:])
        self.assertEqual(remote_jdb_mem['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(remote_jdb_mem['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(remote_jdb_mem['net']['disk'][:], remote_jdb_mem0['disk'][:])
        self.assertEqual(local_jdb_disk['net'][:], remote_jdb_net[:])
        self.assertEqual(local_jdb_disk['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(local_jdb_disk['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(local_jdb_disk['net']['disk'][:], remote_jdb_mem0['disk'][:])
        self.assertEqual(local_jdb_mem['net'][:], remote_jdb_net[:])
        self.assertEqual(local_jdb_mem['net']['group'][:], remote_jdb_mem0['group'][:])
        self.assertEqual(local_jdb_mem['net']['mem'][:], remote_jdb_mem0['mem'][:])
        self.assertEqual(local_jdb_mem['net']['disk'][:], remote_jdb_mem0['disk'][:])

        self.assertTrue(isinstance(remote_jdb_net.files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_mem.files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_mem2.files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_disk.files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_disk2.files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_tmp_disk.files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_tmp_mem.files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_group_disk.files_obj, JDiskFiles))

        self.assertTrue(isinstance(local_jdb_mem.files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem2.files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk.files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk2.files_obj, JNetFiles))
        self.assertTrue(isinstance(local_group_disk.files_obj, JNetFiles))

        self.assertTrue(isinstance(remote_jdb_disk['net'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_disk['net']['disk'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_disk['net']['mem'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_disk['net']['group'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_disk['disk'].files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_disk['mem'].files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_disk['group'].files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_disk['disk2'].files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_disk['mem2'].files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_disk['group2'].files_obj, JDiskFiles))

        self.assertTrue(isinstance(remote_jdb_mem['net'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_mem['net']['disk'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_mem['net']['mem'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_mem['net']['group'].files_obj, JNetFiles))
        self.assertTrue(isinstance(remote_jdb_mem['disk'].files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_mem['mem'].files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_mem['group'].files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_mem['disk2'].files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_mem['mem2'].files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_mem['group2'].files_obj, JMemFiles))

        self.assertTrue(isinstance(remote_jdb_mem0['disk'].files_obj, JDiskFiles))
        self.assertTrue(isinstance(remote_jdb_mem0['mem'].files_obj, JMemFiles))
        self.assertTrue(isinstance(remote_jdb_mem0['group'].files_obj, JMemFiles))

        self.assertTrue(isinstance(local_jdb_disk['net'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['net']['disk'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['net']['mem'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['net']['group'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['disk'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['mem'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['group'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['disk2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['mem2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_disk['group2'].files_obj, JNetFiles))

        self.assertTrue(isinstance(local_jdb_mem['net'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['net']['disk'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['net']['mem'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['net']['group'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['disk'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['mem'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['group'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['disk2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['mem2'].files_obj, JNetFiles))
        self.assertTrue(isinstance(local_jdb_mem['group2'].files_obj, JNetFiles))

        remote_jdb_disk.info()
        local_jdb_disk.info()
        remote_jdb_mem.info()
        local_jdb_mem.info()

        self.server0.jdb.clear(agree='yes', wait_sec=0)
        self.server1.jdb.clear(agree='yes', wait_sec=0)
        self.server2.jdb.clear(agree='yes', wait_sec=0)
        remote_jdb_disk.clear(agree='yes', wait_sec=0)
        remote_jdb_mem.clear(agree='yes', wait_sec=0)
        local_jdb_disk.clear(agree='yes', wait_sec=0)
        local_jdb_mem.clear(agree='yes', wait_sec=0)

        del local_jdb_disk
        del local_jdb_disk2
        del remote_jdb_disk2
        del local_jdb_mem
        del local_jdb_mem2
        del remote_jdb_mem2
        del remote_jdb_mem0

        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            jdb['root_key'] = 'local'
            self.assertEqual(jdb['root_key'], 'local')
            if isinstance(jdb.files_obj, JNetFiles):
                server = None
                for r_jdb in (remote_jdb_disk, remote_jdb_mem):
                    r_jdb -= r_jdb
                    if len(jdb) == 0:
                        server = r_jdb
                    r_jdb['root_key'] = 'remote0'
                    r_jdb['group1'] = group1 = JDb()
                    r_jdb['group1']['key1'] = 'remote1'
                    group2 = r_jdb.add_group('group2')
                    group2['key2'] = 'remote2'
                    self.assertEqual(r_jdb['root_key'], 'remote0')
                    self.assertEqual(r_jdb['group1']['key1'], group1['key1'])
                    self.assertEqual(group1['key1'], 'remote1')
                    self.assertEqual(r_jdb['group2']['key2'], group2['key2'])
                    self.assertEqual(group2['key2'], 'remote2')

                self.assertTrue(server is not None)
                self.assertEqual(server.keys[:], jdb.keys[:])
                self.assertEqual(server, jdb)
                self.assertEqual(server.data_type, jdb.data_type)
                self.assertEqual(server.zip_type, jdb.zip_type)
                self.assertTrue(not isinstance(server.files_obj, JNetFiles))
                self.assertTrue(isinstance(jdb.files_obj, JNetFiles))

                tmp_jdb += tmp_data
                server['group0'] = tmp_jdb
                self.assertEqual(tmp_jdb, tmp_data, filename)
                self.assertEqual(server['group0'], tmp_data)
                self.assertEqual(jdb['group0'], tmp_jdb)
                self.assertEqual(jdb['group0'], tmp_data)
                self.assertTrue(isinstance(jdb['group0'].files_obj, JNetFiles))

                self.assertEqual(jdb['root_key'], 'remote0')
                self.assertEqual(jdb['group1']['key1'], 'remote1')
                self.assertEqual(jdb['group2']['key2'], 'remote2')
                jdb['root_key'] = 'local'
                self.assertEqual(server['root_key'], 'local')
                self.assertTrue('group3' not in jdb)
                server['group3'] = JDb()
                server['group3']['key3'] = 'remote3'
                self.assertEqual(jdb['group3']['key3'], 'remote3')

                jdb1 = JDb(jdb)
                jdb1['group4'] = JDb()
                jdb1['group4']['key4'] = 'local4'
                self.assertTrue(isinstance(jdb1.files_obj, JNetFiles))

                self.assertEqual(jdb1['group4']['key4'], 'local4')
                self.assertEqual(jdb['group4']['key4'], 'local4')
                self.assertEqual(server['group4']['key4'], 'local4')
                self.assertTrue(isinstance(jdb['group4'].files_obj, JNetFiles))
                self.assertTrue(isinstance(jdb1['group4'].files_obj, JNetFiles))
                self.assertTrue(not isinstance(server['group4'].files_obj, JNetFiles))

                group5 = jdb1.add_group('group5')
                group5['key5'] = 'local5'
                self.assertTrue(isinstance(group5.files_obj, JNetFiles))
                self.assertEqual(jdb1['group5']['key5'], 'local5')
                self.assertEqual(jdb['group5']['key5'], 'local5')
                self.assertEqual(server['group5']['key5'], 'local5')
                self.assertTrue(not isinstance(server['group5'].files_obj, JNetFiles))

                server['group4']['key4'] = 'remote4'
                server['group5']['key5'] = 'remote5'
                self.assertEqual(jdb['group4']['key4'], 'remote4')
                self.assertEqual(jdb['group5']['key5'], 'remote5')
                self.assertEqual(group5['key5'], 'remote5')
                server2 = JDb(JNetFiles(self.server1.server_address if server == self.server2.jdb else self.server2.server_address))
                server['group6'] = server2
                server2['key6'] = 'remote6'
                self.assertEqual(jdb['group6']['key6'], 'remote6')
                self.assertTrue(isinstance(jdb['group6'].files_obj, JNetFiles))
                jdb['group6']['key6'] = 'local6'
                self.assertEqual(server['group6']['key6'], 'local6')
                self.assertEqual(server2['key6'], 'local6')
                self.assertEqual(jdb1['group0'], tmp_jdb)

            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertIsNotNone(jdb)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['1st'] = jdb
            jmem.files_obj.is_group(jdb1.files_obj, '1st')
            jdb.files_obj.is_group(jmem.files_obj, '1st')

            jdb0 = jmem.pop('1st', None)
            self.assertEqual(jdb0, jdb)
            jmem1 = jmem.add_group('1st')
            jmem2 = jmem1.add_group('2nd')
            self.assertIn('1st', jmem)
            self.assertIn('2nd', jmem1)

            jmem.clear(agree='yes', wait_sec=0)
            self.assertNotIn('1st', jmem)

            jmem1 = jmem.add_group('1st')
            self.assertTrue(jmem['1st'] is jmem1)
            jmem2 = jmem1.add_group('2nd')
            self.assertTrue(jmem1['2nd'] is jmem2)
            with jmem.open() as fp:
                self.assertTrue('1st' in jmem.key_table)
                self.assertTrue(jmem.f_get_group(fp, '1st') is jmem1)
                with jmem1.open() as fp1:
                    self.assertTrue('2nd' in jmem1.key_table)
                    self.assertTrue(jmem1.f_get_group(fp1, '2nd') is jmem2)

            self.assertTrue(jmem['1st'] is jmem1)
            self.assertTrue(jmem1['2nd'] is jmem2)
            self.assertTrue(jmem['1st']['2nd'] is jmem2)
            self.assertIn('1st', jmem)
            self.assertIn('2nd', jmem1)
            jmem2['3rd'] = jdb
            self.assertTrue(jmem2['3rd'] is jdb)
            self.assertTrue(jmem['1st']['2nd']['3rd'] is jdb)

            jmem.unsync(with_group=True)
            jmem.recycle(level=8, merge=True, fill_zero=True)
            jmem.check_error(level=8, fix_it=True)

            self.assertTrue(jmem['1st'] is jmem1)
            self.assertTrue(jmem1['2nd'] is jmem2)
            self.assertTrue(jmem2['3rd'] is jdb)

            jdb['group_a'] = list(range(128))
            jdb['group_b'] = None
            jdb['test_key'] = list(range(8))

            self.assertEqual(jmem2['3rd'], jdb)

            gp_a = jdb.add_group('group_a')
            self.assertIsNotNone(gp_a)
            self.assertIsInstance(gp_a, JDb)
            gp_a['a'] = 1
            self.assertTrue(jdb.files_obj.is_group(gp_a.files_obj, 'group_a'))
            self.assertEqual(jdb.get_group('group_a'), gp_a)

            gp_b = jdb.add_group('group_b')
            self.assertIsNotNone(gp_b)
            self.assertIsInstance(gp_b, JDb)
            gp_b['b'] = 0
            self.assertTrue(jdb.files_obj.is_group(gp_b.files_obj, 'group_b'))
            self.assertEqual(jdb.get_group('group_b'), gp_b)

            jdb['group_b:::b'] = 2
            jdb[':::c'] = 3

            with jdb.open() as fp:
                for key in jdb.key_table:
                    group = jdb.f_get_group(fp, key)
                    if key == 'a':
                        self.assertTrue(group is gp_a)
                    elif key == 'b':
                        self.assertTrue(group is gp_b)

            key_info = gp_a.keys['a']
            self.assertEqual(key_info, jdb['group_a'].keys['a'])
            key_info2 = jdb.keys['group_a:::a']
            self.assertEqual(key_info, key_info2['group_a:::a'])
            self.assertEqual(jdb['group_a:::a'], jdb[':::a'])
            self.assertEqual(jdb.keys['group_a:::a'], jdb.keys[':::a'])
            self.assertEqual(jdb['group_a:::a'], {'group_a:::a':1})
            self.assertEqual(jmem['1st:::2nd:::3rd:::group_a:::a'], {'1st:::2nd:::3rd:::group_a:::a':1}) # XX
            self.assertEqual(jdb[':::b'], {'group_b:::b':2})
            self.assertEqual(jdb[':::c'], {'group_a:::c':3, 'group_b:::c':3})
            self.assertEqual(jmem['::::::::::::c'], {'1st:::2nd:::3rd:::group_a:::c':3, '1st:::2nd:::3rd:::group_b:::c':3}) # XX
            self.assertEqual(jmem['::::::3rd::::::c'], {'1st:::2nd:::3rd:::group_a:::c':3, '1st:::2nd:::3rd:::group_b:::c':3}) # XX
            self.assertEqual(jmem[':::2nd:::::::::c'], {'1st:::2nd:::3rd:::group_a:::c':3, '1st:::2nd:::3rd:::group_b:::c':3}) # XX
            self.assertEqual(jmem['1st::::::::::::c'], {'1st:::2nd:::3rd:::group_a:::c':3, '1st:::2nd:::3rd:::group_b:::c':3}) # XX
            self.assertEqual(jmem.find(':::2:::3:::_a$:::[ac]', with_value=True), {'1st:::2nd:::3rd:::group_a:::a': 1, '1st:::2nd:::3rd:::group_a:::c': 3}) # XX
            self.assertEqual(jdb.find('_a$:::[ac]', with_value=True), {'group_a:::a': 1, 'group_a:::c': 3})
            self.assertTrue(gp_a is not gp_b)
            gp = jdb.get_group('group_a')
            self.assertTrue(gp_a is gp)
            gp = jdb['group_b']
            self.assertTrue(gp_b is gp)
            self.assertIsInstance(gp, JDb)
            gp = jdb.get('group_a')
            self.assertTrue(gp_a is gp)

            matches = jdb.find(':::[ab]')
            self.assertEqual(set(matches), {'group_a:::a', 'group_b:::b'})

            matches = jdb.keys[matches]
            self.assertEqual(set(matches), {'group_a:::a', 'group_b:::b'})

            gp = jdb.get_group('!!group_c')
            self.assertEqual(gp, None)

            gp = jdb.get_group('group_c')
            self.assertEqual(gp, None)

            gp = jdb.del_group('group_a')
            self.assertIsNotNone(gp)
            self.assertEqual(gp, gp_a)

            gp = jdb.get_group('group_a')
            self.assertIsNone(gp)

            if filename.endswith('.jdb'):
                gp = jdb.add_group('group_a')
                self.assertFalse(gp_a is gp)
            else:
                jdb['group_a'] = gp_a
                gp = jdb['group_a']

            self.assertIsInstance(gp, JDb)
            self.assertEqual(gp_a, gp)
            self.assertNotEqual(gp_b, gp)

            self.assertEqual(jdb['group_a']['a'], gp_a['a'])
            self.assertEqual(jdb['group_b']['b'], gp_b['b'])
            self.assertEqual(jdb.get_group('group_b')['b'], gp_b['b'])

            gp = jdb.del_group('group_b')
            self.assertIsNotNone(gp)
            self.assertEqual(gp, gp_b)

            if filename.endswith('.jdb'):
                jdb.unremove('group_b')
            else:
                jdb['group_b'] = gp_b

            gp = jdb['group_b']
            self.assertIsNotNone(gp, filename)
            self.assertEqual(gp, gp_b)
            self.assertGreater(len(gp), 0)

            dels = jdb.remove('group_b')
            self.assertEqual(len(dels), 1)
            self.assertEqual(len(gp_b), 0)

            if filename.endswith('.jdb'):
                jdb.unremove('group_b')
            else:
                jdb['group_b'] = gp_b

            gp = jdb['group_b']
            self.assertEqual(gp, gp_b)
            self.assertEqual(len(gp_b), 0)
            jdb_bak = jdb.backup('bak', zip_type=0 if jdb.zip_type != 'no' else 'lz')
            self.assertEqual(jdb_bak, jdb)
            self.assertNotEqual(jdb_bak.zip_type, jdb.zip_type)
            self.assertEqual(jdb_bak['group_a'], jdb['group_a'])
            self.assertEqual(jdb_bak['group_b'], jdb['group_b'])
            self.assertEqual(jdb_bak['group_a'], gp_a)
            self.assertEqual(jdb_bak['group_b'], gp_b)
            self.assertNotEqual(jdb_bak['group_a'].files_obj, gp_a.files_obj)
            self.assertNotEqual(jdb_bak['group_b'].files_obj, gp_b.files_obj)
            self.assertEqual(jdb['test_key'], jdb_bak['test_key'])

            if not filename.endswith('.jdb'):
                continue

            expect = {f'k{ii}':'v'+str(ii) * (ii+1) for ii in range(8)}
            ret = gp_b.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(gp_b, expect)
            self.assertNotEqual(jdb_bak['group_b'], expect)
            self.assertEqual(jdb['group_b'], expect)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            jdb1.info()
            jdb.restore('bak')
            self.assertNotEqual(jdb['group_b'], expect)
            self.assertNotEqual(gp_b, expect)
            self.assertEqual(len(gp_b), 0)
            self.assertEqual(len(jdb['group_b']), 0, filename)

            jdb -= {'group_a', 'group_b'}
            self.assertEqual(len(gp_a), 0, filename)
            self.assertEqual(len(gp_b), 0)

            jdb.restore('bak')
            self.assertNotEqual(len(gp_a), 0)
            self.assertEqual(jdb['group_a'], gp_a)

            jmem4 = JDb(data_type=f'{jdb.data_type}({jdb.zip_type})', flags=0)
            jmem4['group_a', 'group_b'] = 0
            jdb -= jmem4
            self.assertEqual(len(gp_a), 0)

            jdb.restore('bak')
            self.assertNotEqual(len(gp_a), 0)

            error = jdb.check_error(level=10, fix_it=True)
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb1['group_a'], gp_a)

            jmem.sync(with_group=True)
            self.assertTrue(jmem.is_latest())
            jmem.unsync(with_group=True)
            self.assertFalse(jmem.is_latest())
            jmem.sync(with_group=True)
            self.assertTrue(jmem.is_latest())

            self.assertTrue(jmem['1st'] is jmem1)
            self.assertTrue(jmem1['2nd'] is jmem2)
            self.assertTrue(jmem2['3rd'] is jdb)

            jmem -= jmem
            self.assertEqual(len(jmem), 0)

            jdb -= jdb
            self.assertEqual(len(jdb), 0)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_none(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.sync()
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb, cache_limit=-1)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.n_records, 0)

            jdb['key1'] = val = True
            self.assertEqual(jdb.n_records, 1)
            self.assertEqual(jdb['key1'], val)
            self.assertEqual(jdb1['key1'], val)
            self.assertTrue(jdb.file_lock.can_lock())
            self.assertTrue(jdb1.file_lock.can_lock())

            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')

            jdb['key2'] = val = None
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key2'], val)
            row = jdb.check_row(1)
            self.assertEqual(row[0], 'key2')

            info = jdb.keys['key1']
            jdb['key1'] = val = '1'
            self.assertNotEqual(info, jdb.keys['key1'])
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key1'], val)
            self.assertEqual(jdb['key1'], jdb1['key1'])

            jdb['key1'] = val = None
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key1'], val)

            jdb['key3'] = val = '3'
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)

            jdb['key3'] = val = False
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)
            self.assertEqual(jdb['key3'], jdb1['key3'])

            jdb['key3'] = val = 0
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)
            self.assertEqual(jdb['key3'], jdb1['key3'])

            jdb['key3'] = val = 0.
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)
            self.assertEqual(jdb['key3'], jdb1['key3'])

            jdb['key3'] = val = []
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)
            self.assertEqual(val, jdb1['key3'])

            jdb['key3'] = val = ''
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)
            self.assertEqual(jdb['key3'], jdb1['key3'])

            jdb['key3'] = val = b''
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], val)
            self.assertEqual(jdb['key3'], jdb1['key3'])

            jdb.remove('key2')
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb, jdb1)

            jdb.remove('key1')
            self.assertEqual(jdb.n_records, 1)
            self.assertEqual(jdb, jdb1)

            jdb.remove('key3')
            self.assertEqual(jdb.n_records, 0)
            self.assertEqual(jdb, jdb1)

            jdb.insert({'key1':'v1', 'key2':'v2', 'key3':'v3'})
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb1['key1'], 'v1')
            self.assertEqual(jdb1['key2'], 'v2')
            self.assertEqual(jdb1['key3'], 'v3')

            jdb[:] = val = True
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = ''
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = b''
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = []
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = [1]
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = [1,2]
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = list(range(16))
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = set()
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = set(range(16))
            self.assertEqual(set(jdb1['key1']), val)  # json unsupport set()
            self.assertEqual(set(jdb1['key2']), val)
            self.assertEqual(set(jdb1['key3']), val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = {}
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = {'a':1}
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = {f'{k}':k for k in range(16)}
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = tuple()
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = tuple(k for k in range(16))
            self.assertEqual(tuple(jdb1['key1']), val) # json unsupport tuple()
            self.assertEqual(tuple(jdb1['key2']), val)
            self.assertEqual(tuple(jdb1['key3']), val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = None
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = -99
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            jdb[:] = val = 1.125
            self.assertEqual(jdb1['key1'], val)
            self.assertEqual(jdb1['key2'], val)
            self.assertEqual(jdb1['key3'], val)
            self.assertEqual(jdb.n_records, 3)

            for i in range(10):
                jdb[:] = val = -(1.0 + 0.1*i)
                self.assertEqual(jdb1['key1'], val)
                self.assertEqual(jdb1['key2'], val)
                self.assertEqual(jdb1['key3'], val)
                self.assertEqual(jdb.n_records, 3)

            del jdb[:]
            self.assertEqual(jdb.n_records, 0)

            jdb[range(10)] = 10
            self.assertEqual(jdb, {str(k):10 for k in range(10)})

            del jdb[range(0, 10, 2)]
            self.assertEqual(len(jdb), 5)

            del jdb[range(1, 10, 2)]
            self.assertEqual(len(jdb), 0)

            jdb.insert({'key1':'1', 'key2':'2', 'key3':'3'})
            jdb[:2] = False
            self.assertEqual(jdb1['key1'], False)
            self.assertEqual(jdb1['key2'], False)
            self.assertEqual(jdb1['key3'], '3')
            self.assertEqual(jdb1.n_records, 3)

            today = dt.date.today()
            jdb['today'] = val = today
            self.assertEqual(jdb['today'], today)
            self.assertTrue(isinstance(jdb['today'], dt.date))

            now = dt.datetime.now()
            jdb['now'] = val = now
            self.assertEqual(jdb['now'], now)
            self.assertTrue(isinstance(jdb['now'], dt.datetime))

            jdb['today_str'] = val = str(today)
            self.assertEqual(jdb['today_str'], str(today))

            jdb['today_str'] = today = '二〇一九年〇七月廿一日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '二〇一九年七月二十四日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '一九九七年七月一日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '十二月卅一日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '十月〇一日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '2019年07月21日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = today = '2019年7月01日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '2019年7月2日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '6月4日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '6月30日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '12月30日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '19年1月1日'
            self.assertEqual(jdb['today_str'], today)

            jdb['today_str'] = val = today = '19年11月11日'
            self.assertEqual(jdb['today_str'], today)

            jdb['now_str'] = val = now = '2025-01-01 12:13:14'
            self.assertEqual(jdb['now_str'], now)

            jdb['now_str'] = val = now = '2025-01-01 12:13:14.098'
            self.assertEqual(jdb['now_str'], now)

            jdb['now_str'] = val = now = '2025-01-01 12:13:14.098765'
            self.assertEqual(jdb['now_str'], now)

            now = dt.datetime.now()
            jdb['now_str'] = val = str(now)
            self.assertEqual(jdb['now_str'], val)

            jdb['time_str'] = val = now = '12:13:14'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '1:13:14'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '999:13:14'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '42:13:14.456789'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '1:13:14.456789'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '123:13:14.456789'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '123:13:14.45678'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '123:13:14.4567'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '123:13:14.456'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '123:13:14.45'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '123:13:14.4'
            self.assertEqual(jdb['time_str'], now)

            jdb['time_str'] = val = now = '1:13:14.4'
            self.assertEqual(jdb['time_str'], now)

            jdb['ip_addr'] = val = ip = '192.168.1.123'
            self.assertEqual(jdb['ip_addr'], ip)

            jdb['ip_addr'] = val = ip = '192.168.1.222:9876'
            self.assertEqual(jdb['ip_addr'], ip)

            jdb['int_val'] = val = str(2**63)
            self.assertEqual(jdb['int_val'], val)

            jdb['int_val'] = val = str(2**64-1)
            self.assertEqual(jdb['int_val'], val)

            jdb['int_val'] = val = '-'+str(2**64-1)
            self.assertEqual(jdb['int_val'], val)

            jdb['int_val'] = val = '+'+str(2**63)
            self.assertEqual(jdb['int_val'], val)

            jdb['int_val'] = val = '+'+str(2**63) + '%'
            self.assertEqual(jdb['int_val'], val)

            jdb['int_val'] = val = '$1000000.'
            self.assertEqual(jdb['int_val'], val)

            jdb['int_val'] = val = '$0000009.'
            self.assertEqual(jdb['int_val'], val)

            jdb['float_val'] = val = '12345678.1'
            self.assertEqual(jdb['float_val'], val)

            jdb['float_val'] = val = '$12,345,678.10'
            self.assertEqual(jdb['float_val'], val)

            jdb['float_val'] = val = '-12,345,678.0987%'
            self.assertEqual(jdb['float_val'], val)

            jdb['float_val'] = val = '+0.0987654321'
            self.assertEqual(jdb['float_val'], val)

            jdb['rep_ptn'] = val = '00000000000000000000'
            self.assertEqual(jdb['rep_ptn'], val)

            jdb['rep_ptn'] = val = '你好' * 60
            self.assertEqual(jdb['rep_ptn'], val)

            jdb['rep_ptn'] = val = '你好!' * 80
            self.assertEqual(jdb['rep_ptn'], val)

            jdb['rep_ptn'] = val = 'hell' * 128
            self.assertEqual(jdb['rep_ptn'], val)

            jdb['rep_ptn'] = val = 'hello!!!' * 512
            self.assertEqual(jdb['rep_ptn'], val)

            jdb['rep_ptn'] = val = '😂😘' * 256
            self.assertEqual(jdb['rep_ptn'], val)

            jdb['mac_addr'] = val = '01:23:45:67:89:ab'
            self.assertEqual(jdb['mac_addr'], val)

            jdb['mac_addr'] = val = '00:AA:BB:CC:DD:EE'
            self.assertEqual(jdb['mac_addr'], val)

            jdb['ch_phone'] = val = '〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇-〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇 〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇-〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇 〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '〇〇〇〇〇〇〇〇〇〇〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇 〇〇〇 〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇-〇〇〇-〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇-〇〇〇〇-〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇-〇〇〇+〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇 〇〇〇〇〇-〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇〇-〇〇〇〇〇-〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇〇 〇〇〇〇〇 〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇〇-〇〇〇〇〇-〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+〇〇〇+〇〇〇〇〇+〇〇〇〇〇〇〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+一二三 一二二四五 一二三四五六七'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['ch_phone'] = val = '+八七六五-四三二一〇'
            self.assertEqual(jdb['ch_phone'], val)

            jdb['phone'] = val = '10-0000'
            self.assertEqual(jdb['phone'], val)

            jdb['phone'] = val = '100-0000'
            self.assertEqual(jdb['phone'], val)

            jdb['phone'] = val = '1000 0000'
            self.assertEqual(jdb['phone'], val)

            jdb['phone'] = val = '+852 9876-1234'
            self.assertEqual(jdb['phone'], val)

            jdb['phone'] = val = '9999-1234'
            self.assertEqual(jdb['phone'], val)

            jdb['phone'] = val = '+86-138-2345-6789'
            self.assertEqual(jdb['phone'], val)

            jdb['ch_num'] = val = '8千9百萬'
            self.assertEqual(jdb['ch_num'], val)

            jdb['ch_num'] = val = '八千九百萬'
            self.assertEqual(jdb['ch_num'], val)

            jdb['ch_num'] = val = '十月初七'
            self.assertEqual(jdb['ch_num'], val)

            jdb['ch_num'] = val = '第1000個'
            self.assertEqual(jdb['ch_num'], val)

            jdb['ch_num'] = val = '第一千五百萬日'
            self.assertEqual(jdb['ch_num'], val)

            jdb['ch_num'] = val = '10時56分55秒'
            self.assertEqual(jdb['ch_num'], val)

            jdb['obj'] = val = ['2025/05-14']
            self.assertEqual(jdb['obj'], val)
            jdb['limit'] = val = (2**64)-1
            self.assertEqual(jdb['limit'], val)

            jdb['limit'] = val = -(2**63)
            self.assertEqual(jdb['limit'], val)

            jdb['limit'] = val = -1.7976931348623157e+308
            self.assertEqual(jdb['limit'], val)

            jdb['limit'] = val = 1.7976931348623157e+308
            self.assertEqual(jdb['limit'], val)

            jdb['url'] = val = 'https://www.google.com'
            self.assertEqual(jdb['url'], val)

            jdb['url'] = val = 'www.google.co.jp'
            self.assertEqual(jdb['url'], val)

            jdb['url'] = val = 'www.polyu.edu.hk/index.html'
            self.assertEqual(jdb['url'], val)

            jdb['url'] = val = 'http://www.polyu.edu.hk/index.html'
            self.assertEqual(jdb['url'], val)

            jdb['url'] = val = 'https://www.yahoo.com.hk/'
            self.assertEqual(jdb['url'], val)

            jdb1[''] = None
            jdb1[None] = ''
            jdb1[' '] = []
            jdb1[True] = {}

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb[:], jdb1[:])
            self.assertEqual(jdb[0.:], jdb1[0.:], filename)
            self.assertEqual(jdb[''], None)
            self.assertEqual(jdb['key1'], False)
            self.assertEqual(jdb['key2'], False)
            self.assertEqual(jdb['key3'], '3')
            jdb1.sync(True)
            for key,val in jdb.items():
                self.assertEqual(jdb1.get_cache(key, None), val)

            self.assertEqual(jdb1.get_cache('xxx', default_val='not exist'), 'not exist')

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            del jdb[:]
            self.assertEqual(len(jdb1), 0)
            self.assertEqual(jdb1.n_records, 0)

            self.assertEqual(jdb, jdb1)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')
            # --------------------------------------------

    def test_set(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            key = 'Hello, my world\t, Testing'
            val = {'a' : [1, 2, 3], 'b' : {'x' : 'X', 'y' : 'Y'}, 'c' : 18, 'd' : None, 'e' : True, 'f' : False, 'g': 12, 'h' : 'hello', 'i' : 9.99}
            jdb[key] = val
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            jdb.recycle()
            sync_id = jdb.sync_id
            jdb1 = JDbReader(jdb)

            jdb['key1'] = 12345678
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertNotEqual(jdb.sync_id, sync_id)
            sync_id = jdb.sync_id
            jdb['key1'] = 12345678
            self.assertEqual(jdb.sync_id, sync_id)

            sync_id = jdb.sync_id
            jdb['key2'] = 'string'
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertNotEqual(jdb.sync_id, sync_id)

            self.assertTrue(jdb == {'key1' : 12345678, 'key2' : 'string'})
            self.assertTrue(jdb != {'key1' : 1234567, 'key2' : 'strin'})
            self.assertNotEqual(jdb.get_bytes('key1'), b'')
            self.assertNotEqual(jdb.get_bytes('key2'), b'')
            self.assertEqual(jdb.get_bytes('key7'), b'')
            self.assertEqual(jdb.get_bytes('key6'), b'')
            jdb['key3'] = True
            jdb['key4'] = None
            jdb['key5'] = 12.3456789
            jdb['key6'] = [12345678, 'string', True, None, 12.3456789]
            jdb['key7'] = {'k1' : 12345678, 'k2' : 'string'}
            bb = jdb.get_bytes('key7')
            self.assertTrue(len(bb) > 0)
            self.assertNotEqual(jdb.get_bytes('key7'), b'')
            self.assertEqual(len(jdb), 7)
            self.assertEqual(jdb['key1'], 12345678)
            self.assertEqual(jdb['key2'], 'string')
            self.assertTrue(jdb['key3'])
            self.assertIsNone(jdb['key4'])
            self.assertAlmostEqual(jdb['key5'], 12.3456789)
            self.assertIsInstance(jdb['key6'], list)
            self.assertEqual(len(jdb['key6']), 5)
            self.assertIsInstance(jdb['key7'], dict)
            self.assertEqual(len(jdb['key7']), 2)
            self.assertEqual(jdb['key7'], {'k1' : 12345678, 'k2' : 'string'})
            self.assertIn('k1', jdb['key7'])
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb[:], jdb1[:])
            self.assertEqual(jdb[0.:], jdb1[0.:])

            ret = jdb.check_row(-1, with_value=True)
            self.assertEqual(ret[0], 'key7')
            self.assertEqual(ret[-1], jdb['key7'])
            ret = jdb.check_row(0, with_value=True)
            self.assertEqual(ret[0], 'key1')
            self.assertEqual(ret[-1], jdb['key1'])
            ret = jdb.check_version(0, 7, with_value=True)
            self.assertEqual(len(ret), len(jdb))
            self.assertEqual(ret[0][0], 'key1')
            self.assertEqual(ret[0][-1], jdb['key1'])
            self.assertEqual(ret[6][0], 'key7')
            self.assertEqual(ret[6][-1], jdb['key7'])

            jdb.set('key11',  12345678)
            jdb.set('key12',  'string')
            jdb.set('key13',  True)
            jdb.set('key14',  None)
            jdb.set('key15',  12.3456789)
            jdb.set('key16',  [12345678, 'string', True, None, 12.3456789])
            jdb.set('key17',  {'k1' : 12345678, 'k2' : 'string'})
            self.assertTrue(jdb.keys['key17'] is not None)
            with self.assertRaises(AttributeError):
                del jdb.keys['key16']

            self.assertEqual(len(jdb), 14)
            self.assertEqual(jdb['key11'], 12345678)
            self.assertEqual(jdb['key12'], 'string')
            self.assertTrue(jdb['key13'])
            self.assertIsNone(jdb['key14'])
            self.assertAlmostEqual(jdb['key15'], 12.3456789)
            self.assertIsInstance(jdb['key16'], list)
            self.assertEqual(len(jdb['key16']), 5)
            self.assertIsInstance(jdb['key17'], dict)
            self.assertEqual(len(jdb['key17']), 2)
            self.assertIn('k1', jdb['key17'])
            self.assertEqual(jdb['key11'], jdb['key1'])
            self.assertEqual(jdb['key12'], jdb['key2'])
            self.assertEqual(jdb['key13'], jdb['key3'])
            self.assertEqual(jdb['key14'], jdb['key4'])
            self.assertEqual(jdb['key15'], jdb['key5'])
            self.assertEqual(jdb['key16'], jdb['key6'])
            self.assertEqual(jdb['key17'], jdb['key7'])

            jdb.setdefault('key11',  1)
            jdb.setdefault('key12',  2)
            jdb.setdefault('key13',  3)
            jdb.setdefault('key14',  4)
            jdb.setdefault('key15',  5)
            jdb.setdefault('key16',  6)
            jdb.setdefault('key17',  7)
            self.assertEqual(len(jdb), 14)
            self.assertEqual(jdb['key11'], 12345678)
            self.assertEqual(jdb['key12'], 'string')
            self.assertTrue(jdb['key13'])
            self.assertIsNone(jdb['key14'])
            self.assertAlmostEqual(jdb['key15'], 12.3456789)
            self.assertIsInstance(jdb['key16'], list)
            self.assertEqual(len(jdb['key16']), 5)
            self.assertIsInstance(jdb['key17'], dict)
            self.assertEqual(len(jdb['key17']), 2)
            self.assertIn('k1', jdb['key17'])

            self.assertEqual(jdb['key11'], jdb.get('key1', None))
            self.assertEqual(jdb['key12'], jdb.get('key2', None))
            self.assertEqual(jdb['key13'], jdb.get('key3', None))
            self.assertEqual(jdb['key14'], jdb.get('key4', None))
            self.assertEqual(jdb['key15'], jdb.get('key5', None))
            self.assertEqual(jdb['key16'], jdb.get('key6', None))
            self.assertEqual(jdb['key17'], jdb.get('key7', None))

            jdb.setdefault('key21',  1)
            jdb.setdefault('key22',  2)
            jdb.setdefault('key23',  3)
            jdb.setdefault('key24',  4)
            jdb.setdefault('key25',  5)
            jdb.setdefault('key26',  6)
            jdb.setdefault('key27',  7)
            self.assertEqual(len(jdb), 21)
            self.assertEqual(jdb['key21'], 1)
            self.assertEqual(jdb['key22'], 2)
            self.assertEqual(jdb['key23'], 3)
            self.assertEqual(jdb['key24'], 4)
            self.assertEqual(jdb['key25'], 5)
            self.assertEqual(jdb['key26'], 6)
            self.assertEqual(jdb['key27'], 7)

            self.assertIn('key21', jdb)
            self.assertIn('key22', jdb)
            self.assertIn('key23', jdb)
            info = jdb.keys['key21', 'key22', 'key23']
            self.assertIn('key21', info)
            self.assertIn('key22', info)
            self.assertIn('key23', info)

            with self.assertRaises(KeyError):
                _val = jdb['key8']

            self.assertIsNone(jdb.keys['key8'])

            self.assertIsNone(jdb.get('key18'))

            ret = jdb.pop('key28')
            self.assertIsNone(ret)
            self.assertIsNone(jdb.keys['key28'])

            self.assertEqual(jdb.get('key8', 1024), 1024)
            self.assertEqual(jdb.pop('key18', 1024), 1024)
            self.assertEqual(len(jdb), 21)
            self.assertNotEqual(jdb, 12)

            for ii in range(10, 20):
                jdb[ii] = ii

            for ii in range(10, 20):
                self.assertEqual(ii, jdb[ii])

            jdb[1.1] = 'hello'
            self.assertEqual(jdb[1.1], jdb["1.1"])
            self.assertIn(1.1, jdb)
            self.assertIn('1.1', jdb)
            self.assertEqual(jdb[1.1], 'hello')
            self.assertEqual(jdb['1.1'], 'hello')

            jdb['中文'] = '語文'
            self.assertIn('中文', jdb)
            sync_id = jdb.sync_id
            key = 'Hello, my world\t, Testing'
            val = {'a' : [1, 2, 3], 'b' : {'x' : 'X', 'y' : 'Y'}, 'c' : 18, 'd' : None, 'e' : True, 'f' : False, 'g': 12, 'h' : 'hello', 'i' : 9.99}
            jdb[key] = val

            self.assertEqual(jdb[key], val)
            row = jdb.check_version(sync_id, with_value=1)
            row = row[jdb.key_table[key]]
            self.assertEqual(row[0], key)
            self.assertEqual(row[-1], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'a' * 256 + 'b' * 256 + 'c' * 256 + 'd' * 256
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val
            self.assertEqual(jdb['big'], val)
            self.assertEqual(sync_id, jdb.sync_id)

            jdb['big'] = val = 'a' * 32
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'b' * 32
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'b' * 256 + 'c' * 256 * 3
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'b' * 256 + 'c' * 256 * 3 + 'd' * 1024
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'b' * 256 + 'c' * 256 * 3
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'b' * 256 + 'c' * 256
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val = 'b' * 256 + 'c' * 1024
            self.assertEqual(jdb['big'], val)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb['big'] = val
            self.assertEqual(jdb['big'], val)
            self.assertEqual(sync_id, jdb.sync_id)

            val = b'1234567890ABCDEFGHIJKLMNOPQRSTUVEXYZ'
            jdb['byte_1'] = val
            self.assertEqual(jdb['byte_1'], val)

            val = bytearray(list(range(256)))
            jdb['byte_2'] = val
            self.assertEqual(jdb['byte_2'], val)

            data = {f'key{v}':list(range(v+1)) for v in range(16)}
            for _key in ('J:json', 'S:msgpack', 'M:marshal', 'P:pickle'):
                jdb[_key] = jdb.z_dumps(data, ret_type=_key[0])
                _data = jdb.z_loads(jdb[_key], ret_type=_key[0])
                self.assertEqual(_data, data)

            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            data_b = dumps(jdb)
            jmem += loads(data_b, jdb.data_type[-1])
            self.assertEqual(jmem, jdb)

            val = jdb.set('value1', lambda key,old_val: -1 if old_val is None  else old_val+1)
            self.assertEqual(val, -1)
            self.assertEqual(jdb['value1'], val)

            val = jdb.set('value1', 2)
            self.assertEqual(val, 2)
            self.assertEqual(jdb['value1'], val)

            val = jdb.set('value1', lambda key,old_val: old_val*2)
            self.assertEqual(val, 4)
            self.assertEqual(jdb['value1'], val)

            _sync_id = jdb.io.sync_id
            jdb['value1'] = lambda key,old_val: old_val
            self.assertEqual(jdb['value1'], val)
            self.assertEqual(jdb.sync_id, _sync_id)

            jdb['value1'] = lambda key,val: val//2
            self.assertEqual(jdb['value1'], 2)

            key_list = {f'A{v}'*(v+1) for v in range(8)}
            ret = jdb.insert(key_list, lambda key,old_val: len(key))
            self.assertEqual(ret, {kk:len(kk) for kk in key_list})

            key_list_b = {f'A{v}'*(v+1) for v in range(9)}
            ret_b = jdb.replace(key_list_b, lambda key,old_val: old_val+1)
            self.assertEqual(key_list, set(ret_b))
            self.assertEqual(ret_b, {kk:vv+1 for kk,vv in ret.items()})

            key_list_c = {f'A{v}'*(v+1) for v in range(10)}
            ret_c = jdb.update(key_list_c, lambda key,old_val: len(key))
            self.assertEqual(ret_c, {kk:len(kk) for kk in key_list_c})

            jdb[::r'^A[0-9]'] = lambda key,val: len(key) + val
            ret = jdb.get_n(ret_c)
            self.assertEqual(ret, {kk:len(kk)*2 for kk in key_list_c})

            chk = jdb[lambda key,val: key.isdigit() and isinstance(val, int)]
            for kk,vv in chk.items():
                self.assertTrue(kk.isdigit() and isinstance(vv, int))

            jdb[lambda key,val: key.isdigit() and isinstance(val, int)] = lambda key,val: val * 2
            chk2 = jdb[lambda key,val: key.isdigit() and isinstance(val, int)]
            self.assertTrue(all(chk2[kk] == vv*2 for kk,vv in chk.items()))

            old_v = jdb[re.compile(r'A[0-9]')]
            self.assertEqual(set(old_v), set(key_list_c))
            self.assertEqual(set(old_v), set(jdb.keys[re.compile(r'A[0-9]')]))
            jdb[re.compile(r'A[0-9]')] = -1
            new_v = jdb[old_v]
            self.assertNotEqual(old_v, new_v)
            self.assertEqual(new_v, {k:-1 for k in old_v})

            del jdb[re.compile(r'A[0-9]')]
            new_v = jdb[old_v]
            self.assertTrue(len(new_v) == 0)

            jdb['pad'] = val = {'NO':0x0a_0a_0a_0a}
            self.assertEqual(jdb['pad'], val)

            jdb['pad'] = val = {'NO:MsgPack':0xc1_c1_c1_c1}
            self.assertEqual(jdb['pad'], val)

            jdb['pad'] = val = {'GZ,BZ,ZS':0x00_00_00_00}
            self.assertEqual(jdb['pad'], val)

            jdb['pad'] = val = {'XZ,BR':0xff_ff_ff_ff}
            self.assertEqual(jdb['pad'], val)

            all_data = jdb[:]
            self.assertEqual(all_data['pad'], val)

            new_keys = {'xx':0, 'yy':1, 'zz':2}
            ret = jdb[new_keys]
            self.assertTrue(not ret)

            jdb[new_keys] = val
            ret = jdb[set(new_keys)]
            self.assertEqual(set(ret), set(new_keys))
            self.assertEqual(ret['xx'], val)
            self.assertEqual(ret['yy'], val)
            self.assertEqual(ret['zz'], val)

            ret2 = jdb[tuple(new_keys)]
            self.assertEqual(ret, ret2)

            ret2 = jdb[list(new_keys)]
            self.assertEqual(ret, ret2)

            ret2 = jdb[new_keys]
            self.assertEqual(ret, ret2)

            jdb -= new_keys
            ret2 = jdb[new_keys]
            self.assertTrue(not ret2)

            del jdb[new_keys]
            ret2 = jdb[set(new_keys)]
            self.assertTrue(not ret2)

            jdb[list(new_keys)] = 1
            ret = jdb[new_keys]
            self.assertEqual(set(ret), set(new_keys))
            self.assertTrue(all(vv == 1 for vv in ret.values()))
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            with jdb.open() as src_fp:
                with jmem.open(read_only=False) as dst_fp:
                    for key in jdb.key_table:
                        _bytes = jdb.io.VAL_dumps(jdb.f_read(src_fp, key))
                        self.assertTrue(len(_bytes) > 0)
                        _ret = jmem.f_write(dst_fp, key, jdb.io.VAL_loads(_bytes), max_wsize=0, flags=JFlag(0))
                        self.assertTrue(_ret)

                    # test nest file lock in write mode
                    with jmem.file_lock.rlock():
                        for key in jdb.key_table:
                            val = jmem.f_read(dst_fp, key)
                            self.assertEqual(val, jdb.f_read(src_fp, key))

                    with jmem.file_lock.wlock():
                        for key in jdb.key_table:
                            val = jmem.f_read(dst_fp, key)
                            self.assertEqual(val, jdb.f_read(src_fp, key))

            self.assertEqual(jdb, jmem)

            jmem.remove_fast(jmem)
            with jdb.open() as src_fp:
                with jmem.open(read_only=False) as dst_fp:
                    for key in jdb.key_table:
                        _data = jdb.f_read(src_fp, key)
                        _ret = jmem.f_write(dst_fp, key, _data, max_wsize=0, flags=JFlag(0))
                        self.assertTrue(_ret)

            self.assertEqual(jdb, jmem)
            expect = {f'key{v}':list(range(v+1)) for v in range(32)}
            jmem = JDb(data_type=jdb.data_type, flags=JFlag.SPLIT)
            jmem[expect] = 0
            self.assertEqual(set(jmem.values()), {0})

            with jmem.open(read_only=False) as fp:
                for key,val in expect.items():
                    val_bytes = dumps(val, jmem.data_type[-1])
                    _val = loads(val_bytes, jmem.data_type[-1])
                    self.assertEqual(val, _val)
                    jmem.f_write(fp, key, _val, flags=JFlag.REVERT if key.endswith('1') else None)
                    self.assertEqual(jmem.f_read(fp, key), val)

            self.assertEqual(jmem, expect)

            with jmem.open(read_only=False) as fp:
                for key,val in expect.items():
                    val_bytes = dumps(0, jmem.data_type[-1])
                    _val = loads(val_bytes, jmem.data_type[-1])
                    self.assertEqual(_val, 0)
                    jmem.f_write(fp, key, _val, flags=JFlag.REVERT)
                    self.assertEqual(_val, jmem.f_read(fp, key))

            self.assertEqual(sum(jmem.values()), 0)

            expect = {f'key{v}':list(range(32-v)) for v in range(32)}
            with jmem.open(read_only=False) as fp:
                for key,val in expect.items():
                    val_bytes = dumps(val, jmem.data_type[-1])
                    _val = loads(val_bytes, jmem.data_type[-1])
                    self.assertEqual(_val, val)
                    jmem.f_write(fp, key, _val, flags=JFlag.REVERT)
                    self.assertEqual(_val, jmem.f_read(fp, key))

            self.assertEqual(jmem, expect)

            with jmem.open() as fp:
                for key,val in expect.items():
                    jmem.f_write(fp, key, set(range(32)))
                    jmem.f_write(fp, key, val, flags=JFlag.REVERT)
                    jmem.f_delete(fp, key)
                    jmem.f_write(fp, key, val, flags=JFlag.REVERT|JFlag.SPLIT)

            self.assertEqual(jmem, expect)

            jmem2 = JDb(data_type=f'{jdb.data_type}({jdb.zip_type})')
            jmem2['key2', 'key3'] = 1
            self.assertTrue(jdb.is_superset(jmem2))
            self.assertFalse(jdb.is_disjoint(jmem2))
            self.assertTrue(jdb.has_all(jmem2))
            self.assertTrue(jdb.keys.is_superset(jmem2))
            self.assertFalse(jdb.keys.is_disjoint(jmem2))
            self.assertTrue(jdb.keys.has_all(jmem2))
            jmem2['kkey2'] = 2
            self.assertFalse(jdb.is_superset(jmem2))
            self.assertTrue(jdb.has_any(jmem2))
            self.assertFalse(jdb.has_all(jmem2))
            self.assertFalse(jdb.keys.is_superset(jmem2))
            self.assertTrue(jdb.keys.has_any(jmem2))
            self.assertFalse(jdb.keys.has_all(jmem2))
            jmem2[jdb] = 3
            self.assertTrue(jdb.is_subset(jmem2))
            self.assertTrue(jdb.keys.is_subset(jmem2))
            jmem2 -= {'key2'}
            self.assertFalse(jdb.is_subset(jmem2))
            self.assertFalse(jdb.keys.is_subset(jmem2))
            jmem2 -= jdb
            self.assertTrue(jdb.is_disjoint(jmem2))
            self.assertTrue(jdb.keys.is_disjoint(jmem2))
            jmem2 += jdb
            self.assertTrue(jdb.is_subset(jmem2))
            self.assertTrue(jdb.keys.is_subset(jmem2))
            self.assertEqual(jmem2[jdb], jdb)
            del jmem2[jdb]
            self.assertEqual(jmem2[jdb], {})
            jmem2 |= {kk:0 for kk in jdb}
            self.assertNotEqual(jmem2[jdb], jdb)
            self.assertEqual(len(jmem2[jdb]), len(jdb))
            self.assertTrue(all(jmem2[kk] == 0 for kk in jdb))
            jmem2 &= jdb
            self.assertEqual(jmem2[jdb], jdb)
            jmem2 ^= jdb
            self.assertTrue(all(jmem2[kk] == 0 for kk in jdb))
            jmem2 -= (jmem2 | jdb)
            self.assertEqual(len(jmem2), 0)
            jmem2 += jdb
            self.assertEqual(jmem2, jdb)
            for kk in jdb:
                jmem2.pop(kk, 0)

            self.assertEqual(len(jmem2), 0)
            expect2 = {f'key{k}':k for k in range(16)}
            jmem2 += expect2
            self.assertEqual(jmem2, expect2)
            jmem2.set('key10', lambda k,v: v+1)
            self.assertEqual(expect2['key10']+1, jmem2['key10'])

            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type, key_limit=jdb.key_limit, flags=JFlag.SPLIT)
            jmem += {'k1':1, 'k2':list(range(64)), 'k3':list(range(64))}
            del jmem['k2', 'k3']
            with jmem.open() as fp:
                jmem.f_write(fp, 'k1', list(range(32)))
                jmem.f_write(fp, 'k2', list(range(16)))

            self.assertEqual(len(jmem), 2)
            self.assertEqual(jmem['k1'], list(range(32)))
            self.assertEqual(jmem['k2'], list(range(16)))

            val = ('abc', 4, 2.1, True, None)
            jdb['tuple()'] = val
            if jdb.data_type.endswith(('M', 'P')):
                self.assertEqual(jdb['tuple()'], val)
            else:
                self.assertEqual(tuple(jdb['tuple()']), val)

            jdb['list()'] = _val = list(val)
            self.assertEqual(jdb['list()'], _val)

            jdb['set()'] = _val = set(val)
            if jdb.data_type.endswith(('M', 'P', 'S')):
                self.assertEqual(jdb['set()'], _val)
            else:
                self.assertEqual(set(jdb['set()']), _val)

            jdb['frozenset()'] = _val = frozenset(val)
            if jdb.data_type.endswith(('M', 'P', 'S')):
                self.assertEqual(jdb['frozenset()'], _val)
            else:
                self.assertEqual(frozenset(jdb['frozenset()']), _val)

            jdb -= {'tuple()', 'set()', 'list()', 'frozenset()'}

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())
                self.assertEqual(last_jdb, jdb)

            last_jdb = jdb

            jdb.get_all(cache_only=True)
            if cache_limit > 0:
                if cache_limit >= len(jdb):
                    self.assertEqual(len(jdb._cache), len(jdb))
                else:
                    self.assertEqual(len(jdb._cache), cache_limit)

            elif cache_limit < 0:
                self.assertEqual(len(jdb._cache), len(jdb))

            else:
                self.assertEqual(len(jdb._cache), 0)

            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertGreater(jdb.sync_id, 0)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_insert(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            jdb['key1'] = 12345678
            jdb['key2'] = 'string'
            jdb.insert({'key28' : None})
            self.assertIsNone(jdb['key28'])

            _keys = {'key1', 'key2', 'key31', 'key32', 'key33', 'key34', 'key35', 'key36', 'key37'}
            chg = jdb.insert(_keys, 8051)
            _keys.remove('key1')
            _keys.remove('key2')
            self.assertEqual(set(chg), _keys)
            for key in _keys:
                self.assertEqual(jdb[key], 8051)
            self.assertTrue(jdb['key1'] != 8051)
            self.assertTrue(jdb['key2'] != 8051)

            test_size = 10
            sync_id = jdb.sync_id
            data = {f'k{i}':99 for i in range(test_size)}
            chg = jdb.insert(list(data), 99)
            self.assertEqual(chg, data)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            data = {f'k{i+100}':999 for i in range(test_size)}
            chg = jdb.insert(set(data), 999)
            self.assertEqual(chg, data)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            data = {f'k{i+200}':9999 for i in range(test_size)}
            chg = jdb.insert(tuple(data), 9999)
            self.assertEqual(chg, data)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            data = {f'{i}':99999 for i in range(300, 300+test_size)}
            chg = jdb.insert(range(300,300+test_size), 99999)
            self.assertEqual(chg, data)
            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb[:], jdb1[:])
            self.assertEqual(jdb[0.:], jdb1[0.:])

            sync_id = jdb.sync_id
            data = {f'k{i+400}':999999 for i in range(test_size)}
            with jdb.open(read_only=False) as fp:
                for key,val in data.items():
                    jdb.f_append(fp, key, val)

            self.assertEqual(jdb[data], data)
            self.assertNotEqual(sync_id, jdb.sync_id)

            _size = len(jdb)
            chg = jdb.insert_vals('a')
            self.assertEqual(_size+len(chg), len(jdb))
            self.assertEqual(len(jdb[lambda k,v:v=='a']), 1)

            _size = len(jdb)
            chg = jdb.insert_vals('a')
            self.assertEqual(_size+len(chg), len(jdb))
            self.assertEqual(len(jdb[lambda k,v:v=='a']), 2)

            _size = len(jdb)
            _vals = ['x', 'b', 'c', 'd']
            chg = jdb.insert_vals(_vals)
            self.assertEqual(_size+len(chg), len(jdb))
            self.assertEqual(len(jdb[lambda k,v:v in _vals]), len(chg))

            sync_id = jdb.sync_id
            expect = {f'{kk}':'Hello' for kk in range(100, 120)}
            chg1 = jdb.insert(range(100, 120), 'Hello')
            self.assertEqual(chg1, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            expect = {f'{sync_id+ii}':f'a{ii}' for ii in range(test_size)}
            chg = jdb.insert_vals([f'a{v}' for v in range(test_size)])
            expect = {f'{sync_id+ii}':f'a{ii}' for ii in range(test_size)}
            self.assertEqual(chg, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)
            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())
                self.assertEqual(last_jdb, jdb)

            last_jdb = jdb

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_replace(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            sync_id = jdb.sync_id
            jdb1 = JDb(jdb)
            test_size = 100
            data = {f'k{ii}':list(range(ii+1)) for ii in range(test_size)}
            chg = jdb.replace(data)
            self.assertEqual(len(chg), 0)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertEqual(sync_id, jdb.sync_id)

            chg = jdb.update({f'k{ii}':list(range(ii+10)) for ii in range(test_size)})
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(data)
            self.assertEqual(chg, data)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(list(data), -1)
            self.assertNotEqual(chg, data)
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertNotEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(data)
            self.assertEqual(chg, data)

            sync_id = jdb.sync_id
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(set(data), -2)
            self.assertNotEqual(chg, data)
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertNotEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(data)
            self.assertEqual(chg, data)

            sync_id = jdb.sync_id
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(tuple(data), -3)
            self.assertNotEqual(chg, data)
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertNotEqual(sync_id, jdb.sync_id)

            data1 = {f'{ii}':ii for ii in range(1000,1000+test_size)}
            chg = jdb.update(data1)
            self.assertEqual(chg, data1)
            self.assertEqual(len(jdb), test_size*2)
            self.assertEqual(len(jdb), len(jdb.key_table))

            sync_id = jdb.sync_id
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size*2)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertEqual(sync_id, jdb.sync_id)

            chg = jdb.replace(range(1000, 1000+test_size), -3)
            self.assertNotEqual(chg, data1)
            self.assertEqual(len(chg), test_size)
            self.assertEqual(len(jdb), test_size*2)
            self.assertEqual(len(jdb), len(jdb.key_table))
            self.assertNotEqual(sync_id, jdb.sync_id)

            jdb['chg'] = 100  # New Item
            self.assertEqual(jdb['chg'], 100)
            row = jdb.key_table['chg']
            self.assertTrue(0 <= row < jdb.n_records)

            sync_id = jdb.sync_id
            jdb['chg'] = 111
            self.assertEqual(jdb['chg'], 111)
            row1 = jdb.key_table['chg']
            self.assertEqual(row, row1)
            self.assertNotEqual(sync_id, jdb.sync_id)

            lines, records = jdb.n_lines, jdb.n_records
            self.assertLessEqual(records, lines)
            jdb['add'] = 200 # New Item
            self.assertEqual(jdb['add'], 200)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())
                self.assertEqual(last_jdb, jdb)

            last_jdb = jdb

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_get(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            sync_id = jdb.sync_id
            test_size = 100
            expect = {f'kk{i}' : i+123 for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(len(jdb), len(chg))
            self.assertEqual(expect, dict(jdb.items()))
            self.assertEqual(expect, dict(jdb.items(reverse=True)))

            with jdb.open() as fp:
                res = {key for key,val in jdb.f_items(fp, with_value=False)}
            self.assertEqual(set(res), set(expect))

            keys = jdb.keys[dt.date.today()]
            self.assertEqual(set(keys), set(expect))

            keys = jdb.keys[dt.datetime.now()]
            self.assertEqual(set(keys), set(expect))

            self.assertEqual(expect['kk0'], jdb['kk0'])

            ret = jdb[:]
            self.assertEqual(ret, expect)

            ret = jdb[:1000]
            self.assertEqual(ret, expect)

            ret = jdb[-test_size:]
            self.assertEqual(ret, expect)

            ret = jdb[-1:]
            self.assertEqual(ret['kk99'], expect['kk99'])

            ret = jdb[:10]
            self.assertEqual(len(ret), 10)
            self.assertEqual(list(expect.items())[:10], list(ret.items()))

            ret = jdb[0:10]
            self.assertEqual(len(ret), 10)
            self.assertEqual(list(expect.items())[:10], list(ret.items()))

            ret = jdb[:'kk10']
            self.assertEqual(len(ret), 10)
            self.assertEqual(list(expect.items())[:10], list(ret.items()))

            ret = jdb[:-10]
            self.assertEqual(len(ret), 90)
            self.assertEqual(list(expect.items())[:-10], list(ret.items()))

            ret = jdb[10:-10]
            self.assertEqual(len(ret), 80)
            self.assertEqual(list(expect.items())[10:-10], list(ret.items()))
            ret = jdb['kk10':'kk90']
            self.assertEqual(len(ret), 80)
            self.assertEqual(list(expect.items())[10:-10], list(ret.items()))

            ret = jdb[10:-10:2]
            self.assertEqual(len(ret), 40)
            self.assertEqual(list(expect.items())[10:-10:2], list(ret.items()))
            ret = jdb['kk10':'kk90':2]
            self.assertEqual(len(ret), 40)
            self.assertEqual(list(expect.items())[10:-10:2], list(ret.items()))

            ret = jdb[-1:0:-1]
            self.assertEqual(list(expect.items())[-1:0:-1], list(ret.items()))

            ret = jdb[-1::-1]
            self.assertEqual(list(expect.items())[-1::-1], list(ret.items()))

            ret = jdb[-1::-2]
            self.assertEqual(list(expect.items())[-1::-2], list(ret.items()))

            ret = jdb[10.:300.]
            self.assertGreater(len(ret), 0)

            ret = jdb[0.:]
            self.assertEqual(ret, expect)

            ret = jdb['kk10':'kk999']
            self.assertEqual(len(ret), 90)

            ret = jdb['kk111':'kk99']
            self.assertEqual(len(ret), 99)

            ret = jdb[::Query().matches(r'kk1\d+')]
            self.assertEqual(set(ret), {'kk10', 'kk11', 'kk12', 'kk13', 'kk14', 'kk15', 'kk16', 'kk17', 'kk18', 'kk19'})

            ret = jdb['kk11'::r'kk1\d+']
            self.assertEqual(set(ret), {'kk11', 'kk12', 'kk13', 'kk14', 'kk15', 'kk16', 'kk17', 'kk18', 'kk19'})

            sync_id = jdb.sync_id
            chg = {}
            for key,val in jdb.items():
                chg[key] = val

            self.assertEqual(chg, expect)
            self.assertEqual(jdb.sync_id, sync_id)

            chg = {}
            ret = jdb.check_version(0, with_value=True)
            for row,val in ret.items():
                key, file_id, offset, rsize, vsize, _ver, _cdays, _mdays, _ttl, _kflags, valid, val = val
                self.assertLessEqual(row, jdb.n_lines)
                if rsize > 0:
                    self.assertIn(file_id, jdb.file_table)
                    self.assertGreaterEqual(offset, 0)
                    self.assertGreaterEqual(rsize, min_value_size)
                    self.assertGreaterEqual(rsize, vsize)

                if valid:
                    chg[key] = val

            self.assertEqual(chg, expect)

            chg = {f'kk{i}':jdb[f'kk{i}'] for i in range(test_size)}
            self.assertEqual(chg, expect)
            self.assertEqual(jdb.get('kk100'), None)
            self.assertEqual(jdb.get('kk100', -100), -100)

            cnt = sum(key in jdb for key in expect)
            self.assertEqual(len(expect), cnt)

            cnt = sum(jdb.has(key) for key in expect)
            self.assertEqual(len(expect), cnt)
            self.assertEqual(jdb, expect)

            ret = jdb - expect
            self.assertEqual(len(ret), 0)

            chg = {f'kk{i}' : jdb.get_cache(f'kk{i}') for i in range(test_size)}
            self.assertEqual(chg, expect)

            chg = jdb.get_n(set(expect))
            self.assertEqual(chg, expect)

            chg = jdb.get_n(expect)
            self.assertEqual(chg, expect)

            chg = jdb.get_n(list(expect))
            self.assertEqual(chg, expect)

            key_table, _file_table = jdb.load_table()
            chg = {}
            for key,row in key_table.items():
                info = jdb.check_row(row, with_value=True)
                self.assertEqual(info[0], key)
                self.assertTrue(info[-2])
                chg[key] = info[-1]

            self.assertEqual(chg, expect)
            self.assertEqual(chg, jdb)

            chg = {}
            with jdb.open(read_only=True) as fp:
                for row_id in range(jdb.n_records):
                    info = jdb.f_read_row(fp, row_id, with_value=True)
                    self.assertTrue(info[-2])
                    chg[info[0]] = info[-1]

            self.assertEqual(chg, expect)
            self.assertEqual(chg, jdb)

            chg = jdb.get_n(['kk1', 'kk2', 'kk1000'])
            self.assertEqual(len(chg), 2)
            self.assertNotIn('kk1000', chg)
            self.assertNotIn('kk1000', jdb)
            self.assertEqual(sync_id, jdb.sync_id)
            expect2 = {f'dd{i}' : list(range(i+1)) for i in range(test_size)}
            try:
                _fp1 = jdb.f_open(read_only=True)
                try:
                    fp2 = jdb.f_open(read_only=False)
                    for key,val in expect2.items():
                        jdb.f_write(fp2, key, val)
                finally:
                    jdb.f_close()
                    fp2 = None
            finally:
                jdb.f_close()
                _fp1 = None

            ret = jdb[float(sync_id):]
            self.assertEqual(ret, expect2)

            jdb[expect2] = 0
            try:
                jdb.io.data_type = 0
                _fp1 = jdb.f_open(read_only=False)
                try:
                    fp2 = jdb.f_open(read_only=False)
                    for key,val in expect2.items():
                        jdb.f_write(fp2, key, val)
                finally:
                    jdb.f_close()
                    fp2 = None
            finally:
                jdb.f_close()
                fp2 = None
            self.assertEqual(jdb[expect2], expect2)

            jdb[expect2] = 1
            try:
                _fp1 = jdb.f_open(read_only=False)
                try:
                    fp2 = jdb.f_open(read_only=True)
                    for key,val in expect2.items():
                        jdb.f_write(fp2, key, val)
                finally:
                    jdb.f_close()
                    fp2 = None
            finally:
                jdb.f_close()
                fp2 = None
            self.assertEqual(jdb[expect2], expect2)

            jdb[expect2] = 2
            with jdb.open(read_only=False) as fp:
                for key,val in expect2.items():
                    jdb.f_write(fp, key, val)

            self.assertEqual(jdb[expect2], expect2)

            chg = {}
            with jdb.open() as fp:
                for row_id in range(jdb.n_lines):
                    info = jdb.f_read_row(fp, row_id, with_value=True)
                    if info[-2]:
                        chg[info[0]] = info[-1]

            ret = jdb[0.:sync_id]
            self.assertEqual(ret, expect)

            ret = jdb[sync_id/1.:]
            self.assertEqual(ret, expect2)

            expect2.update(expect)
            self.assertEqual(chg, expect2)
            self.assertEqual(chg, jdb)

            self.assertNotEqual(set(jdb[20:40].values()), {0})
            sync_id = jdb.sync_id
            keys = jdb[20:40]
            jdb[keys] = 0
            self.assertTrue(set(jdb[keys].values()) == {0})
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())
                self.assertEqual(last_jdb, jdb)

            last_jdb = jdb

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_remove(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            zip_type = config['zip_type']
            reserved_rate = config['reserved_rate']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['group'] = jdb1 = JDb(jdb)
            jmem.recycle(level=2, merge=True, fill_zero=True)

            sync_id = jdb.sync_id
            test_size = 100
            expect = {f'kk{i}' : 'vv'+f'{i}'*(i+min_value_size) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertEqual(len(jdb), len(chg))

            key_table, _file_table = jdb.load_table()
            chg = {}
            file_size = 0
            for key,row in key_table.items():
                info = jdb.check_row(row, with_value=True)
                self.assertEqual(info[0], key)
                self.assertTrue(info[-2])
                val_size = len(expect[key]) # with ''
                self.assertGreaterEqual(val_size, min_value_size)
                if not zip_type and info[3] > 0:
                    self.assertLessEqual(val_size, info[3])
                    if reserved_rate > 0.:
                        _size = int(val_size * (1. + reserved_rate))
                    else:
                        _size = val_size

                    _size = max(min_value_size, _size + 1) # with '\n' or '\0'
                    self.assertGreaterEqual(info[3], _size)

                chg[key] = info[-1]
                file_size += info[3]

            self.assertEqual(chg, expect)
            self.assertEqual(jdb, chg)

            sync_id = jdb.sync_id
            with self.assertRaises(KeyError):
                del jdb['kkk1']

            self.assertEqual(sync_id, jdb.sync_id)
            self.assertEqual(jdb, expect)
            del jdb['kk1']
            self.assertNotEqual(jdb, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            ret = jdb.insert(expect)
            self.assertIn('kk1', ret)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            ret = jdb.remove(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(len(jdb), 0)
            self.assertNotEqual(sync_id, jdb.sync_id)
            sync_id = jdb.sync_id

            ret = jdb.remove(expect)
            self.assertNotEqual(ret, expect)
            self.assertEqual(len(ret), 0)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(sync_id, jdb.sync_id)

            jdb.reinit(expect, agree='yes', wait_sec=1)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            ret = jdb.remove(['k3', 'kk2', 'kkk3'])
            self.assertNotEqual(jdb, expect)
            self.assertEqual(len(jdb)+1, len(expect))
            self.assertNotIn('kk2', jdb)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb.reinit(expect, agree='yes', wait_sec=0)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)

            sync_id = jdb.sync_id
            jdb.reinit(expect, wait_sec=0)
            self.assertEqual(sync_id, jdb.sync_id)

            jdb2 = JDb('db/tmp.jdb')
            val = jdb2[:]
            val2 = jdb2.remove(jdb2)
            self.assertEqual(val, val2)
            jdb2.reinit(jdb, agree='yes', wait_sec=0)
            self.assertEqual(jdb2, expect)

            jdb2 = JDb('db/tmp.jdb')
            jdb2.remove(jdb2)
            self.assertEqual(len(jdb2), 0)

            jdb2.insert(jdb)
            self.assertEqual(jdb, jdb2)
            val = jdb2.remove(jdb2)
            self.assertEqual(val, jdb)
            self.assertEqual(len(jdb2), 0)
            self.assertNotEqual(jdb, jdb2)
            jdb2.update(jdb)
            self.assertEqual(jdb, jdb2)

            keys = set(jdb2[2:10])
            len0 = len(jdb2)
            self.assertEqual(len(keys), 8)
            del jdb2[2:10]
            self.assertEqual(len0 - 8, len(jdb2))
            self.assertFalse(jdb2.get_n(keys))

            self.assertTrue(all(re.search(r'^\tkk\d+\t~~\t\d+\t$', v) for v in set(jdb2[-8.:])))
            keys = {f'kk{v}' for v in range(60,70)}
            self.assertTrue(jdb2.get_n(keys))
            del jdb2['kk60', 'kk61', 'kk62']
            self.assertFalse(jdb2.get_n('kk60'))

            Key = Query()
            matches = jdb2[::r'k[45]']
            self.assertGreaterEqual(len(matches), 2)
            matches_2 = jdb2[::Key.has('k4') | Key.has('k5')]
            self.assertEqual(matches, matches_2)
            self.assertEqual(set(matches), set(jdb2.keys[::r'k[45]']))
            self.assertEqual(set(matches), set(jdb2.keys[::Key.has('k4') | Key.has('k5')]))
            jdb2 -= matches
            matches = jdb2[::r'k[45]']
            self.assertEqual(len(matches), 0)

            matches = jdb2[::Key.endswith(('2', '3'))]
            self.assertGreaterEqual(len(matches), 2)

            del jdb2[::Key.endswith(('2', '3'))]
            matches = jdb2[::Key.endswith(('2', '3'))]
            self.assertEqual(len(matches), 0)

            matches = jdb2[::Key.has('6')]
            jdb2[::Key.has('6')] = lambda k,v: v.replace('6', '*')

            matches_2 = jdb2.find(vals=Query().has('*'))
            self.assertEqual(set(matches), set(matches_2))

            jdb.reinit(keys, default_val=1234, agree='yes', wait_sec=0)
            ret = jdb.get_n(keys)
            self.assertEqual(set(ret), keys)
            self.assertEqual(set(ret.values()), {1234})

            self.assertEqual(jdb.n_records, jdb.n_lines)
            n_lines = jdb.n_lines
            jdb.remove({f'kk{v}' for v in range(60,70,2)})
            self.assertEqual(n_lines, jdb.n_lines)
            jdb.recycle(merge=True, fill_zero=True)
            self.assertGreater(n_lines, jdb.n_lines)
            jdb.remove({f'kk{v}' for v in range(60,70)})
            jdb.recycle(merge=True)
            self.assertEqual(jdb.n_lines, 0)

            keys = {f'kk{v}':f'{v}'*1024 for v in range(10)}
            jdb.insert(keys)
            n_lines = jdb.n_lines
            self.assertEqual(jdb.n_records, jdb.n_lines)
            prev_infos = jdb.keys[:]
            self.assertEqual(jdb.n_records, len(prev_infos))
            jdb.remove({f'kk{v}' for v in range(0,10,2)})
            self.assertNotEqual(jdb.n_records, jdb.n_lines)
            jdb.recycle(merge=True)
            for kk,vv in jdb.items():
                self.assertEqual(vv, keys[kk])

            jdb.remove(keys)
            self.assertNotEqual(jdb.n_records, jdb.n_lines)

            jdb.recycle(merge=True)
            self.assertEqual(jdb.n_records, 0)

            keys = {f'kk{v}':f'{v}'*(v+1) for v in range(128)}
            jdb.insert(keys)
            self.assertEqual(jdb.get_all(), keys)

            jdb2 = JDb(jdb, cache_limit=-1)
            ret = jdb2.get_all(cache_only=True)
            self.assertFalse(ret)
            self.assertEqual(jdb2._cache, keys)

            rnd_list = list(range(128))
            random.shuffle(rnd_list)
            for v in rnd_list:
                del jdb[f'kk{v}']
                jdb.recycle(merge=True)

            self.assertEqual(jdb.n_records, jdb.n_lines)
            self.assertEqual(jdb.n_records, 0)

            expect2 = {f'key{k}':list(range(k+1)) for k in range(128)}
            jdb += expect2
            self.assertEqual(len(jdb), 128)
            self.assertEqual(jdb, expect2)

            jdb -= {f'key{k}' for k in range(128)}
            self.assertEqual(len(jdb), 0)

            jdb ^= expect2
            self.assertEqual(len(jdb), 128)
            self.assertEqual(jdb, expect2)

            del jdb[0.:]
            self.assertEqual(len(jdb), 0)

            jdb.revert(expect2)
            self.assertEqual(len(jdb), 128)
            self.assertEqual(jdb, expect2)

            del jdb[:jdb.n_records]
            self.assertEqual(len(jdb), 0)

            jdb ^= set(expect2)
            self.assertEqual(jdb, expect2)

            del jdb[dt.date.today()]
            self.assertEqual(len(jdb), 0)

            with jdb.open() as fp:
                ret = jdb.f_write(fp, 'key1', 10)
                self.assertTrue(ret)
                ret = jdb.f_write_key_flags(fp, 'key1', JKeyFlag.READ_ONLY)
                self.assertTrue(ret)
                ret = jdb.f_write(fp, 'key2', 10, key_flags=JKeyFlag.READ_ONLY|JKeyFlag.GROUP)
                self.assertTrue(ret)
                ret = jdb.f_write_key_flags(fp, 'key2', JKeyFlag.READ_ONLY)
                self.assertFalse(ret)

            ret = jdb.keys.set_flags(Query().endswith(('y1', 'y2')), read_only=False)
            self.assertEqual(ret, {'key1': (0,0), 'key2': (0,0)})

            ret = jdb.keys.set_flags(re.compile(r'key[12]$'), read_only=False)
            self.assertEqual(ret, {})

            ret = jdb.keys.set_flags(['key1', 'key2'], read_only=True)
            self.assertEqual(set(ret), {'key1', 'key2'})

            self.assertTrue(jdb['key1'] == jdb['key2'] == 10)
            del jdb['key1']
            self.assertTrue('key1' in jdb)

            old_val = jdb['key2']
            jdb['key2'] = list(range(16))
            self.assertEqual(jdb['key2'], old_val)

            with jdb.open() as fp:
                ret = jdb.f_write_key_flags(fp, 'key1', 0)
                self.assertTrue(ret)
                ret = jdb.f_write_key_flags(fp, 'key2', JKeyFlag.READ_ONLY)
                self.assertFalse(ret)
                ret = jdb.f_write_key_flags(fp, 'key2', 0)
                self.assertTrue(ret)

            self.assertTrue(jdb['key1'] == jdb['key2'] == 10)
            del jdb['key1', 'key2']
            self.assertEqual(jdb.get('key1', -1), -1)
            self.assertEqual(jdb.get('key2', -1), -1)
            self.assertEqual(len(jdb), 0)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())

            last_jdb = jdb

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_cache(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))

            # --------------------------------------------
            jdb.cache_limit = 0
            jdb.cache_limit = cache_limit

            jdb1 = JDb(jdb)
            cache_id = id(jdb._cache)
            sync_id = jdb.sync_id

            test_size = 100
            expect0 = {f'kkk{i}' : list(range(i+1)) for i in range(test_size)}
            chg = jdb.insert(expect0)
            self.assertEqual(chg, expect0)
            self.assertEqual(jdb, expect0)
            self.assertEqual(id(jdb._cache), cache_id)
            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertEqual(len(jdb), len(chg))
            self.assertEqual(jdb, jdb1)

            sync_id = jdb.sync_id
            val = jdb['kkk10']
            val.append(-99)
            jdb['kkk10'] = val
            self.assertNotEqual(jdb.sync_id, sync_id, filename)
            jdb._cache.clear()
            self.assertEqual(val, jdb['kkk10'])
            self.assertNotEqual(val, expect0['kkk10'])
            expect0['kkk10'] = val
            self.assertEqual(jdb[expect0], expect0)
            self.assertEqual(jdb, jdb1)

            sync_id = jdb.sync_id
            expect = {f'ddd{i}' : {str(v):i for v in range(i+1)} for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertEqual(id(jdb._cache), cache_id)
            self.assertEqual(jdb[expect], expect)
            self.assertEqual(jdb[expect0], expect0)
            self.assertEqual(jdb, jdb1)

            sync_id = jdb.sync_id
            val = jdb['ddd20']
            val['dd'] = -99
            jdb['ddd20'] = val
            self.assertNotEqual(jdb.sync_id, sync_id)
            jdb._cache.clear()
            self.assertEqual(val, jdb['ddd20'])
            self.assertNotEqual(val, expect['ddd20'])
            expect['ddd20'] = val
            self.assertEqual(jdb[expect], expect)
            self.assertEqual(jdb[expect0], expect0)
            self.assertEqual(jdb, jdb1)

            if jdb.cache_limit > 0:
                _data = jdb.find(r'kkk\d', with_value=1)
                val = jdb['ddd30']
                self.assertEqual(val, expect['ddd30'])

            del_keys = jdb - expect
            self.assertEqual(del_keys, set(expect0))
            self.assertEqual(jdb[del_keys], expect0)
            del jdb[del_keys]
            self.assertEqual(jdb, expect)
            for limit in (-1, 0, 1):
                jdb.key_limit = limit
                jdb.unsync()
                jdb.get_all(cache_only=True)
                self.assertEqual(jdb, expect)

            self.assertEqual(jdb, jdb1)
            used_s = time.perf_counter() - st_time
            self.assertEqual(id(jdb._cache), cache_id)

            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_clone(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            zip_type = config['zip_type']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            index_size = config['index_size']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit} #{len(jdb.keys[:])}', yellow=1))

            # --------------------------------------------
            jdb1 = JDb(jdb)
            sync_id = jdb.sync_id
            test_size = 64
            expect = {f'kkk{i}' : 'v'+(str(i) * int((i+1)*1.5)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(jdb.sync_id, sync_id)
            self.assertEqual(len(jdb), len(chg))
            jdb.recycle()
            self.assertEqual(jdb, expect)

            sync_id = jdb.sync_id
            _jdb = jdb.backup('bak_e')
            self.assertEqual(_jdb, expect)
            self.assertEqual(jdb.sync_id, sync_id)
            self.assertEqual(jdb, _jdb)
            _jdb.recycle()
            self.assertEqual(_jdb, expect)

            sync_id = jdb.sync_id
            j_jdb = jdb.backup('bak_j', zip_type=(0 if zip_type else 'gz'), data_type='J:J', min_value_size=1)
            self.assertEqual(j_jdb, expect)
            self.assertEqual(j_jdb.min_value_size, 1)
            self.assertEqual(jdb.sync_id, sync_id)
            self.assertEqual(jdb, j_jdb)
            m_jdb = jdb.backup('bak_m', zip_type=(0 if zip_type else 'z1'), data_type='M:M', min_value_size=1)
            self.assertEqual(m_jdb, expect)
            self.assertEqual(m_jdb.min_value_size, 1)
            self.assertEqual(jdb.sync_id, sync_id)
            self.assertEqual(jdb, m_jdb)
            x_jdb = jdb.backup('bak_x', zip_type=(0 if zip_type else 'lz'), data_type='S:S', min_value_size=1)
            self.assertEqual(x_jdb, expect)
            self.assertEqual(x_jdb.min_value_size, 1)
            self.assertEqual(jdb.sync_id, sync_id)
            self.assertEqual(jdb, x_jdb)
            self.assertEqual(jdb, expect)
            chg = jdb.remove(expect)
            self.assertNotEqual(jdb.sync_id, sync_id)
            self.assertEqual(chg, expect)
            self.assertEqual(len(jdb), 0)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            if not filename.endswith('.jdb'): continue
            _ref = jdb.restore('bak_e')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            _ref = jdb.restore('bak_j')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            _ref = jdb.restore('bak_m')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            _ref = jdb.restore('bak_x')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            j_jdb.clone_to(jdb, zip_type='br', data_type='J+J', min_value_size=1)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(jdb.min_value_size, min_value_size)
            self.assertEqual(jdb.data_type, 'J+J')
            self.assertEqual(jdb.zip_type, 'br')
            self.assertNotEqual(jdb.get_bytes('kkk10'), j_jdb.get_bytes('kkk10'))
            self.assertEqual(jdb.get_bytes('kkk10'), jdb1.get_bytes('kkk10'))

            jdb = m_jdb.clone_to(jdb.files_obj, zip_type='z2', data_type='S+J', min_value_size=1)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(jdb.min_value_size, min_value_size)
            self.assertEqual(jdb.data_type, 'S+J')
            self.assertEqual(jdb.zip_type, 'z2')
            self.assertNotEqual(jdb.get_bytes('kkk10'), m_jdb.get_bytes('kkk10'))
            self.assertEqual(jdb.get_bytes('kkk10'), jdb1.get_bytes('kkk10'))

            jdb = x_jdb.clone_to(jdb, zip_type='br', data_type='S+M', min_value_size=1)
            self.assertEqual(jdb, expect)
            self.assertNotEqual(jdb.min_value_size, min_value_size)
            self.assertEqual(jdb.data_type, 'S+M')
            self.assertEqual(jdb.zip_type, 'br')
            self.assertNotEqual(jdb.get_bytes('kkk10'), x_jdb.get_bytes('kkk10'))
            self.assertEqual(jdb.get_bytes('kkk10'), jdb1.get_bytes('kkk10'))

            for data_str,zip_str in [
                    ('M+M','gz'), ('S+P','bz'),
                    ('S+S','br'), ('L+J','lz'), ('J+Y', 'z1')]:
                jdb.upgrade(data_type=data_str, zip_type=zip_str)
                self.assertEqual(jdb, expect)
                self.assertNotEqual(jdb.min_value_size, min_value_size)
                self.assertEqual(jdb.data_type, data_str)
                self.assertEqual(jdb.zip_type, zip_str)
                jdb.resize_index_size(0)
                self.assertEqual(jdb, expect)
                index_size = jdb.index_size
                jdb.resize_index_size(index_size*2)
                self.assertEqual(jdb.index_size, index_size*2)
                self.assertEqual(jdb, expect)
                jdb.resize_index_size(index_size)
                self.assertLessEqual(jdb.index_size, index_size*2)
                self.assertEqual(jdb, expect)

            self.assertEqual(jdb, expect)
            jdb.remove(expect)
            self.assertEqual(len(jdb), 0)

            jdb.restore()
            self.assertEqual(jdb, expect)

            sub_expect = {f'sss{i}' : 'x'+(str(i) * int((i+1)*1.5)) for i in range(test_size)}
            sub_jdb = jdb.add_group('sub')
            self.assertTrue(isinstance(sub_jdb, JDb))
            sub_jdb.insert(sub_expect)
            self.assertEqual(sub_jdb, sub_expect)

            _keys = set(jdb)
            _jdb = jdb.backup('bak_x')
            self.assertEqual(_jdb['sub'], sub_expect)
            del _jdb

            jdb.remove_fast(jdb)
            jdb.recycle(merge=True)
            self.assertEqual(jdb.n_lines, 0)

            jdb.restore('bak_x')
            self.assertEqual(set(jdb), _keys)
            self.assertEqual(jdb['sub'], sub_expect, filename)
            jdb.remove(jdb)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))
            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())
                self.assertEqual(last_jdb, jdb)

            last_jdb = jdb

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_basic1(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            index_size = config['index_size']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb, cache_limit=1_000)

            long_key = 'L'*8000
            jdb[long_key] = long_key # Testing long long key
            self.assertEqual(jdb[long_key], long_key)
            old_index_size = jdb.index_size

            with self.assertRaises(KeyError):
                jdb[long_key * 8] = long_key

            self.assertEqual(jdb.index_size, old_index_size)
            self.assertTrue(jdb.is_latest())
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb1[long_key], long_key)

            jdb.clear(agree='yes', wait_sec=0, **config)
            min_value_size = jdb.min_value_size
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.n_records, 0)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            jdb.info()
            print(jdb.dir_name, jdb.file_name, jdb.path, jdb.key_limit)

            _val = '1' * (min_value_size // 2)
            jdb['key1'] = _val
            self.assertEqual(jdb.n_records, 1)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key1'], _val)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)
            jdb['key2'] = _val = '2' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 2)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key2'], _val)
            row = jdb.check_row(1)
            self.assertEqual(row[0], 'key2')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            info = jdb.keys['key1']
            jdb['key1'] = _val = 'x' * (min_value_size // 2)
            self.assertNotEqual(info, jdb.keys['key1'])
            self.assertEqual(jdb.n_records, 2)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key1'], _val)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key1'] = _val = 'y' * (min_value_size - 3)
            self.assertEqual(jdb.n_records, 2)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key1'], _val)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key1'] = _val = 'z' * (min_value_size * 2)
            self.assertEqual(jdb.n_records, 2)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key1'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key3'] = _val = '3' * (min_value_size * 2)
            self.assertEqual(jdb.n_records, 3)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key3'], _val)
            row = jdb.check_row(-1)
            self.assertEqual(row[0], 'key3')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key2'] = _val = '2' * (min_value_size * 2)
            self.assertEqual(jdb.n_records, 3)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key2'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key2'] = _val = '2' * (min_value_size)
            self.assertEqual(jdb.n_records, 3)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key2'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            sync_id = jdb.sync_id
            jdb['key2'] = _val
            self.assertEqual(jdb['key2'], _val)
            self.assertEqual(jdb.sync_id, sync_id)

            jdb['key1'] = _val = '1' * (min_value_size)
            self.assertEqual(jdb.n_records, 3)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key1'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key4'] = _val = '4' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 4)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key4'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key5'] = _val = '5' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 5)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb['key5'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key6'] = '6' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key7'] = '7' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 7)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            del jdb['key2']
            self.assertEqual(jdb.n_records, 6)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            del jdb['key6']
            self.assertEqual(jdb.n_records, 5)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key8'] = 'v'+'8' * (min_value_size * 4)
            self.assertEqual(jdb.n_records, 6)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            row = jdb.check_row(-1)
            self.assertEqual(row[0], 'key8')

            jdb['key9'] = 'v'+'9' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 7)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            row = jdb.check_row(-1)
            self.assertEqual(row[0], 'key9')

            keys,_files = jdb.load_table()
            keys = set(keys)
            for key in keys:
                del jdb[key]

            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb, {})

            key = 'a' * jdb.index_size
            jdb[key] = 'too long'
            self.assertGreater(jdb.index_size, index_size)

            _size = len(jdb)
            jdb += ['row1', 'row1', 'row2']
            self.assertEqual(len(jdb), _size+3)

            jdb |= ('row2', 'row2', 'row3')
            self.assertEqual(len(jdb), _size+3+3)

            jdb &= {'row3', 'row4', 'row5'} # replace
            self.assertEqual(len(jdb), _size+3+3)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)

            jdb += 'new_key0'
            self.assertEqual(jdb['new_key0'], None)
            _size = len(jdb)

            jdb |= 'new_key0'
            self.assertEqual(len(jdb), _size)

            jdb &= 'new_key0'
            self.assertEqual(len(jdb), _size)
            self.assertEqual(jdb['new_key0'], None)
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb[''] = None
            jdb[None] = ''
            jdb[' '] = []
            jdb[True] = {}

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb[:], jdb1[:])

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

            # --------------------------------------------

    def test_basic2(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            index_size = config['index_size']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)

            jdb.sync()
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------

            jdb1 = JDb(jdb)
            min_value_size = jdb.min_value_size
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.n_lines, 0)
            self.assertEqual(jdb.n_records, 0)
            jdb.update('key1', '1' * (min_value_size // 2))
            self.assertEqual(jdb.n_lines, 1)
            self.assertEqual(jdb.n_records, 1)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key2', '2' * (min_value_size // 2))
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb.n_records, 2)
            row = jdb.check_row(1)
            self.assertEqual(row[0], 'key2')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', 'x' * (min_value_size // 2))
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb.n_records, 2)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', 'y' * (min_value_size - 3))
            self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(jdb.n_records, 2)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', 'z' * (min_value_size * 2))
            self.assertEqual(jdb.n_records, 2)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key3', '3' * (min_value_size * 2))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key2', '2' * (min_value_size * 2))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key2', '2' * (min_value_size))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', '1' * (min_value_size))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key4', '4' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 4)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key5', '5' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 5)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key6', '6' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key7', '7' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 7)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.remove('key2')
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.remove('key6')
            self.assertEqual(jdb.n_records, 5)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key8', '8' * (min_value_size * 4))
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key9', '9' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 7)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            keys,_files = jdb.load_table()
            jdb.remove(keys)

            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb, {})

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            key = 'a' * jdb.index_size
            jdb[key] = 'too long'
            self.assertGreater(jdb.index_size, index_size)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')
            # --------------------------------------------

    def test_basic3(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            index_size = config['index_size']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)

            jdb.sync()
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            with jdb.open(read_only=False) as fp:
                min_value_size = jdb.min_value_size
                self.assertEqual(jdb.n_records, 0)
                self.assertGreaterEqual(jdb.n_lines, jdb.n_records)

                jdb.f_write(fp, 'key1', '1' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 1)
                self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
                row = jdb.f_read_row(fp, 0)
                self.assertEqual(row[0], 'key1')

                jdb.f_write(fp, 'key2', '2' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 2)
                self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
                row = jdb.f_read_row(fp, 1)
                self.assertEqual(row[0], 'key2')

                jdb.f_write(fp, 'key1', 'x' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 2)
                self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
                row = jdb.f_read_row(fp, 0)
                self.assertEqual(row[0], 'key1')

                jdb.f_write(fp, 'key1', 'y' * (min_value_size - 3))
                self.assertEqual(jdb.n_records, 2)
                self.assertGreaterEqual(jdb.n_lines, jdb.n_records)
                row = jdb.f_read_row(fp, 0)
                self.assertEqual(row[0], 'key1')

                jdb.f_write(fp, 'key1', 'z' * (min_value_size * 2))
                self.assertEqual(jdb.n_records, 2)

                jdb.f_write(fp, 'key3', '3' * (min_value_size * 2))
                self.assertEqual(jdb.n_records, 3)

                jdb.f_write(fp, 'key2', '2' * (min_value_size * 2))
                self.assertEqual(jdb.n_records, 3)

                jdb.f_write(fp, 'key2', '2' * (min_value_size))
                self.assertEqual(jdb.n_records, 3)

                jdb.f_write(fp, 'key1', '1' * (min_value_size))
                self.assertEqual(jdb.n_records, 3)

                jdb.f_write(fp, 'key4', '4' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 4)

                jdb.f_write(fp, 'key5', '5' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 5)

                jdb.f_write(fp, 'key6', '6' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 6)

                jdb.f_write(fp, 'key7', '7' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 7)

                jdb.f_delete(fp, 'key2')
                self.assertEqual(jdb.n_records, 6)

                jdb.f_delete(fp, 'key6')
                self.assertEqual(jdb.n_records, 5)

                jdb.f_write(fp, 'key8', '8' * (min_value_size * 4))
                self.assertEqual(jdb.n_records, 6)

                jdb.f_write(fp, 'key9', '9' * (min_value_size // 2))
                self.assertEqual(jdb.n_records, 7)

                for key in set(jdb.key_table):
                    jdb.f_delete(fp, key)

                self.assertEqual(jdb.n_records, 0)
                key = 'a' * jdb.index_size
                jdb.f_write(fp, key, 'too long')
                self.assertGreater(jdb.index_size, index_size)

                jdb.f_write(fp, 'key9', '9' * (min_value_size // 2))

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            self.assertFalse(jdb.file_lock.is_locked)
            with jdb.open(read_only=True) as fp:
                self.assertTrue(jdb.file_lock.is_locked)
                self.assertEqual(jdb.file_lock.mode, 'r')

                val = jdb.f_read(fp, 'key9')
                self.assertEqual(val, '9' * (min_value_size // 2))
                self.assertNotIn('key10', jdb.key_table)

                with jdb.open(read_only=False) as fp1:
                    self.assertTrue(jdb.file_lock.is_locked)
                    self.assertEqual(jdb.file_lock.mode, 'w')
                    self.assertTrue(fp1 is fp)

                    jdb.f_write(fp1, 'key10', 'a' * (min_value_size // 2))
                    self.assertIn('key10', jdb.key_table)

                    with jdb.open(read_only=True) as fp2:
                        self.assertTrue(jdb.file_lock.is_locked)
                        self.assertEqual(jdb.file_lock.mode, 'w')
                        self.assertTrue(fp1 is fp2)

                        with jdb.open(read_only=True) as fp3:
                            self.assertTrue(jdb.file_lock.is_locked)
                            self.assertEqual(jdb.file_lock.mode, 'w')
                            self.assertTrue(fp1 is fp3)

                        self.assertEqual(jdb.file_lock.mode, 'w')
                        self.assertTrue(jdb.file_lock.is_locked)

                    self.assertEqual(jdb.file_lock.mode, 'w')
                    self.assertTrue(jdb.file_lock.is_locked)

                self.assertEqual(jdb.file_lock.mode, 'w')
                self.assertTrue(jdb.file_lock.is_locked)

                with jdb.open(read_only=False) as fp1:
                    self.assertEqual(jdb.file_lock.mode, 'w')
                    self.assertTrue(jdb.file_lock.is_locked)

                    self.assertTrue(fp1 is fp)
                    self.assertNotIn('key111', jdb.key_table)
                    jdb.f_write(fp1, 'key111', 'b' * (min_value_size // 2))
                    self.assertIn('key111', jdb.key_table)
                    val = jdb.f_read(fp1, 'key111')
                    self.assertEqual(val.strip('b'), '')

                    with jdb.open(read_only=False) as fp2:
                        self.assertEqual(jdb.file_lock.mode, 'w')
                        self.assertTrue(jdb.file_lock.is_locked)
                        self.assertTrue(fp1 is fp2)

                        jdb.f_write(fp2, 'key222', 'c' * (min_value_size // 2))

                    self.assertEqual(jdb.file_lock.mode, 'w')
                    self.assertTrue(jdb.file_lock.is_locked)

                    val = jdb.f_read(fp1, 'key222')
                    self.assertEqual(val.strip('c'), '')

                self.assertEqual(jdb.file_lock.mode, 'w')
                self.assertTrue(jdb.file_lock.is_locked)

            self.assertEqual(jdb.file_lock.mode, '')
            self.assertFalse(jdb.file_lock.is_locked)

            _val = 'TEST' * min_value_size
            jdb[:] = _val
            self.assertTrue(all(vv == _val for vv in jdb.values()), filename)

            jdb -= jdb # delete
            self.assertEqual(len(jdb), 0)

            test_size = 100
            expect = {f'key_{v}':list(range(v+1)) for v in range(test_size)}
            jdb += expect # update
            self.assertEqual(jdb[:], expect)

            chg = {f'key_{v}':v for v in range(80, test_size+20)}
            jdb &= chg # replace
            self.assertNotEqual(jdb, expect)
            self.assertEqual(jdb['key_80'], chg['key_80'])
            self.assertEqual(jdb['key_99'], chg['key_99'])

            jdb ^= chg # revert
            self.assertEqual(jdb, expect, filename)

            jdb |= chg # insert
            self.assertEqual(len(jdb), len(expect)+20)
            self.assertEqual(jdb[jdb & expect], expect)

            jdb -= (jdb - expect)
            self.assertEqual(jdb, expect)
            self.assertTrue('key_0' in jdb)
            self.assertTrue({'key_0', 'key_99'} in jdb)
            self.assertTrue([f'key_{v}' for v in range(test_size)] in jdb)
            self.assertTrue({f'key_{v}' for v in range(test_size+1)} not in jdb)
            # self.assertTrue({f'key_{v}':v for v in range(20,90)} not in jdb)
            self.assertTrue({'key_0', 99} not in jdb)
            self.assertTrue(expect in jdb)
            self.assertTrue(chg not in jdb)
            self.assertTrue(set(expect) == jdb)
            self.assertTrue({f'key_{v}' for v in range(test_size)} == jdb)
            self.assertTrue(set(chg) != jdb)

            vals = []
            try:
                vals = jdb[:]
                val = jdb['key_0']
                with jdb.open(read_only=True) as fp:
                    val = jdb.f_read(fp, 'key_0')
                    raise TypeError

            except TypeError:
                self.assertEqual(jdb['key_0'], val)
                self.assertEqual(jdb, vals)

            try:
                with jdb.open(read_only=True) as fp:
                    val = jdb.f_read(fp, 'key_0')
                    jdb.f_write(fp, 'key_0', val * 2)
                    raise TypeError

            except TypeError:
                self.assertEqual(jdb['key_0'], val * 2)

            try:
                self.assertTrue('new_key0' not in jdb)
                with jdb.open(read_only=True) as fp:
                    val = jdb.f_read(fp, 'key_0')
                    jdb.f_write(fp, 'new_key0', val * 2)
                    raise TypeError

            except TypeError:
                self.assertEqual(jdb['key_0'], val)
                self.assertEqual(jdb['new_key0'], val * 2)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            jdb2 = JDb(jdb)
            self.assertFalse(jdb2.is_latest())
            with self.assertRaises(KeyboardInterrupt):
                with jdb2.open(read_only=True) as fp:
                    self.assertTrue(jdb2.io.is_updated())
                    raise KeyboardInterrupt

            self.assertEqual(jdb2, jdb)
            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')
            # --------------------------------------------

    def test_find(self):
        last_jdb = None
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            range_100 = list(range(100))
            random.shuffle(range_100)
            expect = {f'kkk{i}' : i for i in range_100}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(len(jdb), len(chg))

            matches = jdb.find(IN=[2,4,6,8])
            self.assertEqual(matches, {f'kkk{i}':i for i in (2,4,6,8)})

            matches = jdb.find(NIN=[2,4,6,8])
            self.assertEqual(matches, {f'kkk{i}':i for i in range_100 if i not in {2,4,6,8}})

            matches = jdb.find(lambda k: k.find('0') > 0)
            self.assertEqual(matches, {f'kkk{i}':None for i in range(0,100,10)})

            matches = jdb.find(lambda k: k.find('0') > 0, LE=20)
            self.assertEqual(matches, {f'kkk{i}':i for i in (0, 10,20)})

            matches = jdb.find(NOT={'$gte':10})
            self.assertEqual(matches, {f'kkk{i}':i for i in range(10)})

            matches = jdb.find(AND=[{'$gte':10}, {'$lt':20}])
            self.assertEqual(matches, {f'kkk{i}':i for i in range(10, 20)})

            matches = jdb.find(NOT={'$or':[{'$lt':10}, {'$gte':20}]})
            self.assertEqual(matches, {f'kkk{i}':i for i in range(10, 20)})

            matches = jdb.find('kkk', sort=1)
            self.assertEqual(matches, expect)
            self.assertEqual(list(matches.items())[0], ('kkk0', 0))
            self.assertEqual(list(matches.items())[99], ('kkk99', 99))

            matches = jdb.find('kkk', sort=1, reverse=True)
            self.assertEqual(matches, expect)
            self.assertEqual(list(matches.items())[-1], ('kkk0', 0))
            self.assertEqual(list(matches.items())[0], ('kkk99', 99))

            ret = jdb.map(lambda kk,vv: (kk,vv+100), keys=r'^kkk\d')
            self.assertEqual(len(ret), len(expect))
            self.assertEqual(dict(ret), {k:v+100 for k,v in expect.items()})

            sync_id = jdb.sync_id
            matches = jdb.find(r'k1\d$', with_value=True)
            self.assertEqual(set(matches), {'kkk10', 'kkk11', 'kkk12', 'kkk13', 'kkk14', 'kkk15', 'kkk16', 'kkk17', 'kkk18', 'kkk19'})

            matches = jdb.find(r'k1\d$', with_value=False)
            self.assertEqual(set(matches), {'kkk10', 'kkk11', 'kkk12', 'kkk13', 'kkk14', 'kkk15', 'kkk16', 'kkk17', 'kkk18', 'kkk19'})
            matches = jdb.keys(r'k1\d$')
            self.assertEqual(set(matches), {'kkk10', 'kkk11', 'kkk12', 'kkk13', 'kkk14', 'kkk15', 'kkk16', 'kkk17', 'kkk18', 'kkk19'})

            matches = jdb.find(re.compile(r'k1\d$'))
            self.assertEqual(set(matches), {'kkk10', 'kkk11', 'kkk12', 'kkk13', 'kkk14', 'kkk15', 'kkk16', 'kkk17', 'kkk18', 'kkk19'})

            matches = jdb.find({'kkk11', 'kkk22', 'kkk33', 'kkk9999'})
            self.assertEqual(set(matches), {'kkk11', 'kkk22', 'kkk33'})

            matches = jdb.find(('kkk11', 'kkk22', 'kkk33', 'kkk9999'))
            self.assertEqual(set(matches), {'kkk11', 'kkk22', 'kkk33'})

            matches = jdb.find(['kkk11', 'kkk22', 'kkk33', 'kkk9999'])
            self.assertEqual(set(matches), {'kkk11', 'kkk22', 'kkk33'})

            with jdb.open(read_only=True) as fp:
                matches = jdb.f_find_keys(fp, r'k1\d$')

            self.assertEqual(set(matches), {'kkk10', 'kkk11', 'kkk12', 'kkk13', 'kkk14', 'kkk15', 'kkk16', 'kkk17', 'kkk18', 'kkk19'})

            with jdb.open(read_only=True) as fp:
                matches2 = jdb.f_find_keys(fp, re.compile(r'k1\d$'))

            self.assertEqual(matches, matches2)

            matches = jdb.find(r'abc\d+$')
            self.assertEqual(len(matches), 0)

            matches = jdb.find(EQ=50)
            self.assertEqual(len(matches), 1)

            matches = jdb.find(NE=50)
            self.assertEqual(len(matches), 99)

            matches = jdb.find(LT=10)
            self.assertEqual(len(matches), 10)

            matches = jdb.find(LTE=10)
            self.assertEqual(len(matches), 11)

            matches = jdb.find(GT=10)
            self.assertEqual(len(matches), 89)

            matches = jdb.find(GE=10)
            self.assertEqual(len(matches), 90)

            matches = jdb.find(LE=10, GT=1)
            self.assertEqual(len(matches), 9)

            matches = jdb.find(IN={1, 3, 5, 7})
            self.assertEqual(len(matches), 4)

            matches = jdb.find(IN=[1, 1, 3, 5, 7])
            self.assertEqual(len(matches), 4)

            matches = jdb.find(IN=(1, 3, 5, 7))
            self.assertEqual(len(matches), 4)

            matches = jdb.find(FUNC=lambda v : 10 <= v < 20)
            self.assertEqual(len(matches), 10)

            matches = jdb.find(ANY=lambda v : 10 <= v < 20)
            self.assertEqual(len(matches), 10)

            matches = jdb.find(ANY=lambda v : 10 <= v < 20, limit=3)
            self.assertEqual(len(matches), 3)

            self.assertEqual(sync_id, jdb.sync_id)

            jdb['中文'] = ['數學', '文字', '人類', 999, ]

            matches = jdb.find(ANY=999)
            self.assertEqual(len(matches), 1)
            self.assertIn('中文', matches)

            matches = jdb.find(vals={'$1':{'$eq':'文字'}})
            self.assertEqual(len(matches), 1)
            self.assertIn('中文', matches)

            jdb[b'bytes'] = val = 'testing'
            matches = dict(jdb.keys.item_iter(bytearray(b'bytes')))
            self.assertTrue('bytes' in matches)

            matches = dict(jdb.item_iter(bytearray(b'bytes')))
            self.assertEqual(matches.get('bytes', None), val)

            country = {
                '美國' : {'國旗':['紅色', '白色', '藍色'], '語言':'英文', '洲':'北美洲'},
                '英國' : {'國旗':['紅色', '白色', '藍色'], '語言':'英文'},
                '法國' : {'國旗':['紅色', '白色', '藍色'], '語言':'法文'},
                '加拿大' : {'國旗':['紅色', '白色'], '語言':'英文'},
                '澳洲' : {'國旗':['紅色', '白色', '藍色'], '語言':'英文'},
                '中國' : {'國旗':['紅色', '黃色'], '語言':'普通話'},
                '德國' : {'國旗':['紅色', '黃色', '黑色'], '語言':'德文'},
                '日本' : {'國旗':['紅色', '白色'], '語言':'日文'},
                '意大利' : {'國旗':['紅色', '白色', '綠色'], '語言':'意大利文'},
            }
            jdb.insert(country)

            keys = jdb.keys[-1]
            matches = dict(jdb.item_iter(-1))
            self.assertEqual(jdb[keys], matches)

            matches_2 = dict(jdb.item_iter(Query().語言.has('意大利文')))
            if keys == '意大利':
                self.assertEqual(matches, matches_2)

            keys = jdb.keys[0.]
            matches = dict(jdb.item_iter(0.))
            self.assertEqual(jdb[keys], matches)

            matches = jdb.find(HAS='洲')
            self.assertEqual(set(matches), {'美國'})

            matches_2 = jdb.find(EXISTS='洲')
            self.assertEqual(matches, matches_2)

            matches = jdb.show(vals={'國旗.1':'黃色'})
            self.assertEqual(set(matches), {'中國', '德國'})

            matches = jdb.find(RE=r'英文')
            self.assertEqual(set(matches), {'美國', '英國', '澳洲', '加拿大'})

            matches = jdb.find(RE=r'紅色')
            self.assertEqual(matches, country)

            matches = jdb.find(RE=r'綠色')
            self.assertEqual(set(matches), {'意大利'})

            matches = jdb.find(RE=r'灰色')
            self.assertTrue(not matches)

            matches = jdb.find(RE=r'[黃綠]色|法文')
            self.assertEqual(set(matches), {'意大利', '德國', '中國', '法國'})

            matches = jdb.find(RE=re.compile(r'[黃綠]色|法文'))
            self.assertEqual(set(matches), {'意大利', '德國', '中國', '法國'})

            matches = jdb.find(RE2=r'[黃綠]色|法文')
            self.assertEqual(set(matches), {'意大利', '德國', '中國', '法國'})

            matches = jdb.find(FUNC=lambda v: isinstance(v, dict) and v.get('語言', '') == '英文')
            self.assertEqual(set(matches), {'美國', '英國', '加拿大', '澳洲'})

            # 國旗 is exists and (語言 is not 英文 and (len(國旗) == 3 and 國旗[1] == '白色'))
            matches = jdb.show(EXISTS='國旗', vals={'!語言': '英文', '國旗':{'$size': 3, '$1':'白色'}}, with_date=True)
            self.assertEqual(set(matches), {'法國', '意大利'})

            matches_2 = jdb.show(vals={'!語言.$eq':'英文', '國旗.$size':3, '國旗.1':'白色'}, with_date=True)
            self.assertEqual(matches, matches_2)

            matches_2 = jdb.show(vals={'!*言.$eq':'英文', '國*.$size':3, '*旗.1':'白色'}, with_date=True)
            self.assertEqual(matches, matches_2)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            # --------------------------------------------
            if last_jdb is not None:
                self.assertEqual(last_jdb - jdb, set())
                self.assertEqual(last_jdb, jdb)

            last_jdb = jdb

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_open(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            if isinstance(jdb.files_obj, JDiskFiles):
                os.remove(jdb.files_obj.get_KEY())

            test_size = 100
            expect = {f'kkk{i}' : i for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(len(jdb), len(chg))

            sync_id = jdb.sync_id
            with jdb.open() as fp:
                val = jdb.f_read(fp, 'kkk0')
                self.assertEqual(val, expect['kkk0'])
                val = jdb.f_read(None, 'kkk0')
                self.assertEqual(val, expect['kkk0'])

                val = jdb.f_read(fp, 'kkk99')
                self.assertEqual(val, expect['kkk99'])

                val = jdb.f_read(fp, 'kkk10')
                ref = jdb.f_read_row(fp, expect['kkk10'])
                self.assertEqual(ref[0], 'kkk10')

                ref = jdb.f_read_row(None, 10)
                self.assertEqual(ref[0], 'kkk10')

                ref = jdb.f_read_row(fp, 10, with_value=True)
                self.assertEqual(ref[-1], val)

            self.assertEqual(sync_id, jdb.sync_id)

            with jdb.open(read_only=False) as fp:
                # self.assertIsNotNone(fp[-1])
                val = jdb.f_read(fp, 'kkkk100', -1)
                self.assertEqual(val, -1)
                _row1 = jdb.f_write(fp, 'kkkk100', 100)
                val = jdb.f_read(fp, 'kkkk100')
                self.assertEqual(val, 100)
                _row2 = jdb.f_write(None, 'kkkk101', 101)

            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertIn('kkkk100', jdb)
            self.assertIn('kkkk101', jdb)

            self.assertEqual(len(jdb), test_size+2)

            sync_id = jdb.sync_id
            with jdb.open(read_only=False) as fp:
                val = jdb.f_read(fp, 'kkkk100', -1)
                self.assertEqual(val, 100)
                val = jdb.f_delete(fp, 'kkkk100')
                self.assertEqual(val, 100)

                val = jdb.f_read(fp, 'kkkk100', -1)
                self.assertEqual(val, -1)
                val = jdb.f_delete(None, 'kkkk101')
                self.assertEqual(val, 101)
                with self.assertRaises(KeyError):
                    val = jdb.f_delete(fp, 'kkkk100')
                val = jdb.f_delete(fp, f'kkk{test_size-1}')

            self.assertEqual(len(jdb), test_size-1)
            self.assertNotEqual(sync_id, jdb.sync_id)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_sync(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            jdb.flags = JFlag.REVERT|JFlag.SPLIT|JFlag.FSYNC
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            self.assertFalse(jdb1.is_latest())
            self.assertEqual(jdb1.fsize, 0)
            self.assertEqual(len(jdb1), 0)

            jdb1.sync()
            self.assertTrue(jdb1.is_latest())
            self.assertGreaterEqual(jdb1.fsize, 128)

            test_size = 100
            expect = {f'kkk{i}' : list(range(i)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(len(jdb), len(chg))

            jdb2 = JDb(jdb)
            self.assertFalse(jdb2.is_latest())
            self.assertTrue(jdb2.has('kkk5'))
            self.assertTrue(jdb2.is_latest())

            sync_id = jdb.sync_id
            jdb2 = JDb(jdb.files_obj)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb2, expect)
            self.assertEqual(jdb2.files_obj.get_KEY(), jdb.files_obj.get_KEY())
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            jdb2.remove({f'kkk{i}' for i in range(4, 7)})
            self.assertFalse(jdb2.has('kkk4'))
            self.assertFalse(jdb2.has('kkk5'))
            self.assertFalse(jdb2.has('kkk6'))

            self.assertTrue(jdb.has('kkk4')) # Not sync
            self.assertTrue(jdb.has('kkk5')) # Not sync
            self.assertTrue(jdb.has('kkk6')) # Not sync

            self.assertNotIn('kkk4', jdb2)
            self.assertNotIn('kkk5', jdb2)
            self.assertNotIn('kkk6', jdb2)
            self.assertNotEqual(jdb2.sync_id, jdb.sync_id)

            self.assertNotIn('kkk4', jdb) # auto sync by __contains__ -> jdb.open(read_only=True)
            self.assertNotIn('kkk5', jdb)
            self.assertNotIn('kkk6', jdb)

            self.assertFalse(jdb.has('kkk4')) # Not sync
            self.assertFalse(jdb.has('kkk5')) # Not sync
            self.assertFalse(jdb.has('kkk6')) # Not sync

            self.assertNotEqual(jdb2, expect)
            self.assertNotEqual(jdb, expect)
            self.assertEqual(jdb, jdb2)
            self.assertNotEqual(jdb2.sync_id, sync_id)
            self.assertEqual(jdb2.sync_id, jdb.sync_id)

            jdb = JDb(jdb)
            self.assertFalse(jdb.is_latest())
            self.assertEqual(jdb.fsize, 0)
            self.assertEqual(len(jdb.key_table), 0)
            with jdb.open() as fp:
                self.assertTrue(jdb.io.is_updated())
                self.assertGreater(jdb.fsize, 128)
                self.assertGreater(jdb.sync_id, 0)
                self.assertEqual(jdb.fsize, jdb.io.file_size)
                self.assertGreater(len(jdb.key_table), 0)

            self.assertEqual(jdb.fsize, jdb.io.file_size)
            self.assertGreater(len(jdb.key_table), 0)
            self.assertTrue(jdb.is_latest())
            self.assertEqual(jdb, jdb2)

            jdb = JDb(jdb)
            self.assertFalse(jdb.is_latest())
            self.assertEqual(jdb.fsize, 0)
            self.assertEqual(len(jdb.key_table), 0)
            self.assertEqual(jdb, jdb2)

            self.assertTrue(jdb.is_latest())
            self.assertEqual(jdb.fsize, jdb.io.file_size)
            self.assertGreater(len(jdb.key_table), 0)
            self.assertTrue(jdb.is_latest())

            jdb2.insert(expect)
            self.assertNotEqual(jdb2.sync_id, jdb.sync_id)
            self.assertNotEqual(jdb2.fsize, jdb.fsize)
            if jdb.key_limit == 'no':
                self.assertNotEqual(jdb2.key_table, jdb.key_table)
            self.assertFalse(jdb.is_latest())

            with jdb.open(read_only=True) as fp:
                self.assertEqual(jdb2.sync_id, jdb.sync_id)
                self.assertEqual(jdb2.fsize, jdb.fsize)
                if jdb.key_limit == 'no':
                    self.assertEqual(jdb2.key_table, jdb.key_table)
                jdb.f_load_keys(fp)
                self.assertEqual(jdb2.sync_id, jdb.sync_id)
                self.assertEqual(jdb2.fsize, jdb.fsize)
                if jdb.key_limit == 'no':
                    self.assertEqual(jdb2.key_table, jdb.key_table)
                jdb.f_load_keys(fp, force=True)
                self.assertEqual(jdb2.sync_id, jdb.sync_id)
                self.assertEqual(jdb2.fsize, jdb.fsize)
                if jdb.key_limit == 'no':
                    self.assertEqual(jdb2.key_table, jdb.key_table)
            self.assertTrue(jdb.is_latest())
            self.assertTrue(jdb2.is_latest())

            file_id = len(jdb.file_table)
            if file_id > 0:
                new_file_id = file_id + 2
                fp = jdb.files_obj.VAL_open(new_file_id, 'wb+')
                if fp is not None:
                    fp.write(b'1' * 16)
                    fp.close()
                jdb.io.update_file_table()
                self.assertEqual(new_file_id+1, len(jdb.file_table))
                self.assertEqual(jdb.file_table[new_file_id], 16)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[::3], jdb1.keys[::3])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_file(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            self.assertEqual(len(jdb.file_table), 0)
            jdb1 = JDb(jdb)
            test_size = 100
            expect = {f'kkk{i}' : list(range(i)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertGreater(len(jdb.file_table), 0)
            with jdb.open(read_only=False) as fp:
                jio, fp, key_fp = jdb.f_get_fp(fp)
                self.assertTrue(key_fp.readable())
                self.assertTrue(key_fp.writable())
                self.assertTrue(key_fp.seekable())
                index_size = jio.index_size
                idx = jio.seek(key_fp, 0)
                self.assertTrue(idx >= 128)
                self.assertEqual(idx, key_fp.tell())
                line = key_fp.read(index_size)
                self.assertEqual(len(line), index_size)
                idx2 = jio.seek(key_fp, 0)
                self.assertEqual(idx, idx2)
                if jdb.data_type.startswith('J+'):
                    line2 = key_fp.readline()
                    self.assertEqual(line, line2)
                    line3 = key_fp.readline()
                    self.assertEqual(len(line3), index_size)
                    idx3 = key_fp.tell()
                    key_fp.seek(idx2)
                    key_fp.writelines([line2, line3])
                    self.assertEqual(key_fp.tell(), idx3)
                    key_fp.seek(idx2)
                    _lines = key_fp.readlines(index_size)
                    self.assertEqual(key_fp.tell(), idx3)
                    self.assertEqual(len(_lines), 2)
                    self.assertEqual(_lines, [line2, line3])
                else:
                    _lines = bytearray(index_size * 2)
                    rd_size = key_fp.readinto(_lines)
                    idx3 = key_fp.tell()
                    self.assertEqual(line, _lines[:index_size])
                    self.assertEqual(rd_size, index_size * 2)
                    key_fp.seek(idx2)
                    key_fp.write(_lines)
                    self.assertEqual(key_fp.tell(), idx3)

                for key in jio.key_table:
                    self.assertEqual(expect[key], jdb.f_read(fp, key, copy=False))

            jdb2 = JDb(jdb)
            self.assertFalse(jdb2.is_latest())
            jdb2.sync()
            self.assertTrue(jdb2.is_latest())
            self.assertEqual(jdb2.n_lines, jdb.n_lines)
            self.assertEqual(jdb2.n_records, jdb.n_records)
            self.assertEqual(jdb2.sync_id, jdb.sync_id)
            self.assertEqual(len(jdb2.key_table), test_size)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb2, expect)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            file_table = jdb.file_table
            for file_id in file_table:
                self.assertTrue(jdb.files_obj.VAL_exist(file_id))
                self.assertGreaterEqual(jdb.files_obj.VAL_size(file_id), 0)

            jdb.clear()
            self.assertEqual(jdb, expect)

            jdb.clear(agree='yes', wait_sec=1)
            self.assertNotEqual(jdb, expect)
            self.assertEqual(len(jdb.file_table), 0)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.n_lines, 0)

            for file_id in file_table:
                self.assertFalse(jdb.files_obj.VAL_exist(file_id))
                self.assertGreaterEqual(jdb.files_obj.VAL_size(file_id), 0)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_rename(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            self.assertEqual(len(jdb.file_table), 0)
            jdb1 = JDb(jdb)
            test_size = 128
            expect = {f'xxx{i}' : list(range(i+1)) for i in range(test_size)}
            expect2 = {f'kkkk{i}' : expect[f'xxx{i}'] for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertTrue(jdb.is_latest())

            jdb2 = JDb(jdb.files_obj)
            self.assertFalse(jdb2.is_latest())
            self.assertEqual(jdb2, expect)
            self.assertTrue(jdb2.is_latest())

            ret = jdb.rename({f'xxx{i}' : f'kkkk{i}' for i in range(test_size)})
            self.assertEqual(len(ret), len(expect2))
            self.assertNotEqual(jdb, expect)
            self.assertEqual(jdb, expect2)
            self.assertTrue(jdb.is_latest())
            self.assertFalse(jdb2.is_latest())

            with jdb2.open(read_only=True) as fp:
                with jdb2.open(read_only=False) as fp2:
                    self.assertTrue(fp is fp2)
                    ret = jdb2.f_rename(fp2, 'kkkk1', 'kkkk1')
                    self.assertFalse(ret)

                    ret = jdb2.f_rename(fp2, 'kkkk1', 'xxx1')
                    self.assertTrue(ret)

                    with self.assertRaises(KeyError):
                        jdb2.f_rename(fp2, 'kkkk2', 'kkkk3')

                    with self.assertRaises(KeyError):
                        jdb2.f_rename(fp2, 'xxx2', 'kkkk3')

                    ret = jdb2.f_rename(fp2, 'kkkk10', 'xxx10')
                    self.assertTrue(ret)
                    ret = jdb2.f_rename(fp2, 'kkkk100', 'xxx100')
                    self.assertTrue(ret)

            self.assertTrue(jdb2.is_latest())
            self.assertFalse(jdb.is_latest())

            self.assertTrue(jdb2.has('xxx1'))
            self.assertTrue(jdb2.has('xxx10'))
            self.assertTrue(jdb2.has('xxx100'))
            self.assertFalse(jdb2.has('kkkk100'))
            self.assertFalse(jdb2.has('kkkk10'))
            self.assertFalse(jdb2.has('kkkk1'))

            self.assertIn('xxx1', jdb)
            self.assertIn('xxx10', jdb)
            self.assertIn('xxx100', jdb)
            self.assertTrue(jdb.is_latest())

            ret = jdb.rename({f'xxx{i}' : f'kkkk{i}' for i in range(test_size)})
            self.assertEqual(len(ret), 3)
            self.assertEqual(jdb2, expect2)
            self.assertEqual(jdb, expect2)

            ret = jdb.rename({f'xxx{i}' : f'kkkk{i}' for i in range(test_size)})
            self.assertEqual(len(ret), 0)
            self.assertEqual(jdb, expect2)
            self.assertEqual(jdb2, expect2)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_key_table(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            index_size = config['index_size']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            self.assertEqual(len(jdb.file_table), 0)
            jdb1 = JDb(jdb)
            test_size = 100
            expect = {f'xxx{i}' : list(range(i+1)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertTrue(jdb.is_latest())
            self.assertEqual(jdb.n_lines, jdb.n_records)
            self.assertEqual(len(expect), jdb.n_lines)
            print(jdb.key_table)

            if hasattr(jdb.key_table, 'files_obj'):
                jdb.key_table.clear()
                row_id = jdb.key_table.pop('xxxx1', -1)
                self.assertEqual(row_id, -1)
                jdb.key_table.clear()
                row_id = jdb.key_table.pop('xxx1', -1)
                self.assertEqual(row_id, 1)
                with self.assertRaises(KeyError):
                    del jdb.key_table['xxxx2']

            row_id = jdb.key_table['xxx10']
            self.assertEqual(jdb.key_table['xxx10'], row_id)

            kt = list(jdb.key_table.items())
            random.shuffle(kt)
            jdb.key_table.clear()
            for key,row in kt:
                jdb.key_table[key] = row

            self.assertEqual(jdb, expect)
            sync_id = jdb.sync_id
            chg = {}
            with jdb.open() as fp:
                _prev_row = -1
                for key,row in jdb.io.sorted_key_table_items():
                    self.assertGreater(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=False)
                    _prev_row = row

            self.assertEqual(chg, expect)
            self.assertEqual(jdb.sync_id, sync_id)

            chg = {}
            with jdb.open() as fp:
                _prev_row = jdb.n_lines
                for key,row in jdb.io.sorted_key_table_items(reverse=True):
                    self.assertLess(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=False)
                    _prev_row = row

                self.assertEqual(chg, expect)

                chg.clear()
                _prev_row = jdb.n_lines
                for key,row in jdb.io.sorted_key_table_items(copy=True, reverse=True):
                    self.assertLess(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=True)
                    _prev_row = row

            self.assertEqual(chg, expect)
            self.assertEqual(jdb.sync_id, sync_id)

            chg = {}
            with jdb.open() as fp:
                key_table = list(jdb.key_table.items())
                random.shuffle(key_table)
                jdb.io.key_table.clear()
                for key,row in key_table:
                    jdb.io.key_table[key] = row

                _prev_row = -1
                for key,row in jdb.io.sorted_key_table_items():
                    self.assertGreater(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=False)
                    _prev_row = row
                self.assertEqual(chg, expect)

                chg.clear()
                _prev_row = jdb.n_lines
                for key,row in jdb.io.sorted_key_table_items(reverse=True):
                    self.assertLess(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=False)
                    _prev_row = row
                self.assertEqual(chg, expect)

                chg.clear()
                _prev_row = -1
                for key,row in jdb.io.sorted_key_table_items(copy=True):
                    self.assertGreater(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=False)
                    _prev_row = row
                self.assertEqual(chg, expect)

                chg.clear()
                _prev_row = jdb.n_lines
                for key,row in jdb.io.sorted_key_table_items(copy=True, reverse=True):
                    self.assertLess(row, _prev_row)
                    chg[key] = jdb.f_read(fp, key, row=row, copy=False)
                    _prev_row = row
                self.assertEqual(chg, expect)

                key_table = dict(jdb.key_table)
                self.assertEqual(key_table, jdb.key_table)
                self.assertEqual(set(key_table.values()), set(jdb.key_table.values()))
                self.assertEqual(set(key_table.keys()), set(jdb.key_table.keys()))

            jdb.remove({f'xxx{i}' for i in range(test_size//2,test_size)})
            self.assertNotEqual(jdb, expect)
            self.assertEqual(len(expect), jdb.n_lines)
            self.assertEqual(len(expect)-(test_size//2), jdb.n_records)

            jdb['a' * index_size] = 1234
            self.assertGreater(jdb.index_size, index_size)

            kt = jdb.key_table.copy()
            self.assertEqual(kt, jdb.key_table)
            self.assertEqual(kt, kt)
            self.assertEqual(len(kt), len(set(kt.values())))

            for _type in ('bt', 'l2', '<8', config['key_limit']):
                jdb.key_limit = _type
                _key_table, _file_table = jdb.load_table()
                self.assertEqual(kt, _key_table)
                self.assertTrue(_key_table, _key_table.copy())
                self.assertTrue(_file_table, _file_table.copy())
                if hasattr(_key_table, 'files_obj'):
                    self.assertEqual(set(jdb), set(_key_table))
                    row = _key_table.pop('xxx16', -1)
                    self.assertEqual(row, _key_table.get('xxx16', -1), _key_table)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_version(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            self.assertEqual(len(jdb.file_table), 0)
            test_size = 100
            expect = {f'xxx{i}' : list(range(i)) for i in range(test_size)}
            ret = jdb.check_status({'xxx0' : None, 'xxx1' : None})
            self.assertEqual(len(ret), 2)
            self.assertIn('xxx0', ret)
            self.assertIn('xxx1', ret)
            self.assertEqual(ret['xxx0'][0], 'x')
            self.assertEqual(ret['xxx1'][0], 'x')

            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)

            matches = jdb.keys[-1.]
            self.assertTrue(len(matches), 1)

            ret = jdb.check_status({'xxx0' : -1, 'xxx1' : -1})
            self.assertEqual(ret['xxx0'][0], '!')
            self.assertEqual(ret['xxx1'][0], '!')
            self.assertTrue(ret['xxx0'][1] == 0)
            self.assertTrue(ret['xxx1'][1] == 1)

            ret = jdb.check_status({'xxx0' : 0, 'xxx1' : 0})
            self.assertEqual(ret['xxx0'][0], '')
            self.assertEqual(ret['xxx1'][0], '!')
            self.assertTrue(ret['xxx0'][1] == 0)
            self.assertTrue(ret['xxx1'][1] == 1)

            ret = jdb.check_status({'xxx0' : None, 'xxx1' : None})
            self.assertEqual(ret['xxx0'][0], '')
            self.assertEqual(ret['xxx1'][0], '')
            self.assertTrue(ret['xxx0'][1] == 0)
            self.assertTrue(ret['xxx1'][1] == 1)

            ret = jdb.check_status({'xxx0' : 1, 'xxx1' : 1})
            self.assertEqual(ret['xxx0'][0], '!')
            self.assertEqual(ret['xxx1'][0], '')
            self.assertTrue(ret['xxx0'][1] == 0)
            self.assertTrue(ret['xxx1'][1] == 1)

            jdb['xxx1'] = 'change'
            ret = jdb.check_status({'xxx0' : 0, 'xxx1' : 1})
            self.assertEqual(ret['xxx0'][0], '')
            self.assertEqual(ret['xxx1'][0], '!')
            self.assertTrue(ret['xxx0'][1] == 0)
            self.assertTrue(ret['xxx1'][1] != 1)

            last_ret = ret
            jdb['xxx0'] = 'change'
            ret = jdb.check_status({kk:vv[1] for kk,vv in last_ret.items()})
            self.assertEqual(ret['xxx0'][0], '!')
            self.assertEqual(ret['xxx1'][0], '')
            self.assertTrue(ret['xxx0'][1] != last_ret['xxx0'][1])
            self.assertTrue(ret['xxx1'][1] == last_ret['xxx1'][1])

            del jdb['xxx1']
            last_ret = ret
            ret = jdb.check_status({kk:vv[1] for kk,vv in last_ret.items()})
            self.assertEqual(ret['xxx0'][0], '')
            self.assertEqual(ret['xxx1'][0], '-')
            self.assertTrue(ret['xxx0'][1] == last_ret['xxx0'][1])
            self.assertTrue(ret['xxx1'][1] != last_ret['xxx1'][1])

            last_ret = ret
            jdb['xxx1'] = 'renew'
            ret = jdb.check_status({kk:vv[1] for kk,vv in last_ret.items()})
            self.assertEqual(ret['xxx0'][0], '')
            self.assertEqual(ret['xxx1'][0], '!')
            self.assertTrue(ret['xxx0'][1] == last_ret['xxx0'][1])
            self.assertTrue(ret['xxx1'][1] != last_ret['xxx1'][1])

            last_ver = jdb.sync_id
            jdb.insert({'key99' : 99, 'key999' : 999})
            ret = jdb.check_status({'':last_ver})
            self.assertEqual(ret['key99'][0], '+')
            self.assertEqual(ret['key999'][0], '+')

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_lock(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            test_size = 100
            expect = {f'xxx{i}' : 10000+i for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)

            for key in jdb:
                val = jdb.f_read(None, key)
                self.assertEqual(expect[key], val)

            for key in jdb:
                val = jdb[key]
                self.assertEqual(expect[key], val)

            for key,val in jdb.items():
                self.assertEqual(expect[key], val)

            for key,val in jdb.item_iter():
                self.assertEqual(expect[key], val)

            for val in jdb.values():
                self.assertEqual(expect[f'xxx{val-10000}'], val)

            with jdb.open():
                for key in jdb.key_table:
                    val = jdb.f_read(None, key)
                    jdb.f_write(None, key, val + 1)
                    self.assertEqual(val+1, jdb.f_read(None, key))

            keys = list(jdb)
            with jdb.open(read_only=False) as fp:
                for key in keys:
                    val = jdb.f_read(fp, key)
                    jdb.f_write(fp, key, val + 1)
                    self.assertEqual(val + 1, jdb.f_read(fp, key))

            with jdb.open(read_only=False) as fp:
                with jdb.open(read_only=False) as fp1:
                    for key in keys:
                        val = jdb.f_read(fp, key)
                        jdb.f_write(fp1, key, val + 1)
                        self.assertEqual(val + 1, jdb.f_read(fp1, key))

            with jdb.open(read_only=False) as fp:
                try:
                    fp1 = jdb.f_open(read_only=False)
                    for key in keys:
                        val = jdb.f_read(fp, key)
                        jdb.f_write(fp1, key, val + 1)
                        self.assertEqual(val + 1, jdb.f_read(fp1, key))
                finally:
                    jdb.f_close()

            self.assertEqual(jdb.file_lock.mode, '')
            ident1 = jdb.file_lock.acquire(read_only=True, block=True)
            try:
                self.assertEqual(jdb.file_lock.mode, 'r')
                self.assertEqual(jdb.file_lock.get_count(ident1), 1)
                self.assertEqual(jdb1.file_lock.get_count(ident1), 0)

                ident2 = jdb1.file_lock.acquire(read_only=True, block=False)
                try:
                    self.assertEqual(ident1, ident2)
                    self.assertEqual(jdb.file_lock.get_count(ident1), 1)
                    self.assertEqual(jdb1.file_lock.get_count(ident2), 1)
                    self.assertEqual(jdb.file_lock.mode, 'r')
                    self.assertEqual(jdb1.file_lock.mode, 'r')

                    with self.assertRaises(BlockingIOError):
                        ident1a = jdb1.file_lock.acquire(read_only=False, block=False)

                    self.assertEqual(jdb.file_lock.mode, 'r')
                    self.assertEqual(jdb.file_lock.get_count(ident1), 1)
                    self.assertEqual(jdb1.file_lock.get_count(ident2), 1)

                finally:
                    jdb1.file_lock.release()
                    self.assertEqual(jdb1.file_lock.mode, '')

                self.assertEqual(jdb.file_lock.get_count(ident1), 1)
                self.assertEqual(jdb1.file_lock.get_count(ident1), 0)
                self.assertEqual(jdb.file_lock.mode, 'r')

                ident1a = jdb.file_lock.acquire(read_only=False, block=True, switch=True)
                self.assertEqual(jdb.file_lock.get_count(ident1), 1)
                self.assertEqual(ident1, ident1a)
                self.assertEqual(jdb.file_lock.mode, 'w')

                ident1b = jdb.file_lock.acquire(read_only=True, block=True)
                try:
                    self.assertEqual(jdb.file_lock.get_count(ident1), 2)
                    self.assertEqual(ident1, ident1b)
                    self.assertEqual(jdb.file_lock.mode, 'w')

                    self.assertEqual(jdb1.file_lock.get_count(ident1), 0)
                    with self.assertRaises(BlockingIOError):
                        ident2 = jdb1.file_lock.acquire(read_only=True, block=False)

                    with self.assertRaises(BlockingIOError):
                        ident2 = jdb1.file_lock.acquire(read_only=False, block=False)

                    self.assertEqual(jdb1.file_lock.mode, '')
                    self.assertEqual(jdb1.file_lock.get_count(ident1), 0)
                    self.assertEqual(jdb.file_lock.get_count(ident1), 2)

                finally:
                    jdb.file_lock.release()
                    self.assertEqual(jdb.file_lock.get_count(ident1), 1)

                with jdb.file_lock.rlock():
                    self.assertEqual(jdb.file_lock.get_count(ident1), 2)
                    with jdb.file_lock.wlock():
                        self.assertEqual(jdb.file_lock.get_count(ident1), 3)

                    self.assertEqual(jdb.file_lock.get_count(ident1), 2)

                self.assertEqual(jdb.file_lock.get_count(ident1), 1)
                self.assertEqual(jdb.file_lock.mode, 'w')
            finally:
                jdb.file_lock.release()

            self.assertEqual(jdb.file_lock.get_count(ident1), 0)
            self.assertEqual(jdb.file_lock.mode, '')

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            jdb.file_lock.reset_lock()
            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_reader(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            test_size = 100
            expect = {f'kk{i}' : {'sub':list(range(i))} for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertTrue(isinstance(jdb, JDbReader))
            self.assertTrue(isinstance(jdb, JDb))

            jdbl = JDbReader(jdb.files_obj)
            self.assertTrue(isinstance(jdbl, JDbReader))
            self.assertEqual(len(jdbl), test_size)
            self.assertEqual(jdbl.get_n(), expect)
            self.assertTrue(jdbl.is_latest())
            self.assertEqual(jdbl.sync_id, jdb.sync_id)

            chg = {}
            for key,val in jdb.items():
                chg[key] = val
            self.assertEqual(chg, expect)

            chg = dict(jdb)
            self.assertEqual(chg, expect)

            chg = {}
            for key in jdbl:
                chg[key] = jdbl.get(key)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, jdbl)

            chg = dict(jdbl)
            self.assertEqual(dict(jdbl), expect)

            chg = {}
            with jdbl.open(read_only=True) as fp:
                for key in jdbl.key_table:
                    chg[key] = jdbl.f_read(fp, key)
            self.assertEqual(chg, expect)

            cnt = sum(key in jdbl for key in expect)
            self.assertEqual(len(expect), cnt)

            cnt = sum(jdbl.has(key) for key in expect)
            self.assertEqual(len(expect), cnt)
            self.assertEqual(jdbl, expect)

            chg = {f'kk{i}' : jdbl.get_cache(f'kk{i}') for i in range(test_size)}
            self.assertEqual(chg, expect)

            _key_table, _file_table = jdbl.load_table()
            chg = jdbl.get_n(set(expect))
            self.assertEqual(chg, expect)

            chg = jdbl.get_n({'kk1', 'kk20'})
            self.assertEqual(chg['kk1'], expect['kk1'])
            self.assertEqual(chg['kk20'], expect['kk20'])

            expect2 = {f'aa{i}' : i+456 for i in range(test_size)}
            chg = jdb.update(expect2)
            self.assertEqual(chg, expect2)
            expect3 = jdb.get_all()

            self.assertFalse(jdbl.is_latest())
            self.assertNotEqual(jdbl.sync_id, jdb.sync_id)
            self.assertEqual(jdbl.get_n(), expect3)
            self.assertTrue(jdbl.is_latest())

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_write(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            jdb2 = JDb(jdb)

            sync_id = jdb.sync_id
            test_size = 300
            expect = {f'xxx{i}' : list(range(i)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            jmem = JDb(flags=JFlag.REVERT)
            jmem += expect
            self.assertEqual(jdb, jmem)
            jmem -= jmem
            self.assertEqual(len(jmem), 0)
            for _ in range(2):
                with jmem.open(read_only=False) as fp:
                    cnt = 0
                    jmem.f_write(fp, 'xxx0', 0)
                    for key,val in expect.items():
                        jmem.f_append(fp, key, val)
                        cnt += 1
                    self.assertEqual(cnt, jmem.n_records)
                self.assertEqual(jdb, jmem)

            sync_id = jdb.sync_id
            with jdb.open() as fp:
                for key,val in expect.items():
                    jdb.f_write(fp, key, val)
            self.assertEqual(jdb.sync_id, sync_id)
            self.assertEqual(jdb, expect)

            expect2 = {f'yyy{i}' : list(range(i+1)) for i in range(test_size)}
            chg = jdb.update(expect2)
            self.assertEqual(chg, expect2)
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            sync_id = jdb.sync_id
            expect3 = {f'yyy{i}' : {str(i):list(range(i+2))} for i in range(test_size)}
            chg = jdb.insert(expect3)
            self.assertFalse(chg)
            self.assertEqual(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            chg = jdb.replace(expect3)
            self.assertEqual(set(chg), set(expect3))
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            sync_id = jdb.sync_id

            for key in ['yyy299', 'yyy298', 'yyy297']:
                jdb.remove(key)
                self.assertGreater(jdb.sync_id, sync_id)
                self.assertEqual(jdb, jdb2)
                self.assertEqual(jdb.sync_id, jdb2.sync_id)
                sync_id = jdb.sync_id

            del jdb['xxx10']
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            sync_id = jdb.sync_id

            self.assertFalse(jdb2.has('xxx10'))
            self.assertTrue(jdb2.has('xxx11'))
            self.assertTrue(jdb2.has_any('xxx11'))
            self.assertFalse(jdb2.has_all('xxx10'))
            self.assertTrue(jdb2.has_any(['xxx11', 'xxx10', 'yyy299']))
            self.assertTrue(jdb1.has_any(['xxx11', 'xxx10', 'yyy299']))
            self.assertTrue(jdb2.has_any({'xxx11', 'xxx10', 'yyy299'}))
            self.assertTrue(jdb2.has_any(('xxx11', 'xxx10', 'yyy299')))
            self.assertFalse(jdb2.has_any(['yyy299', 'yyy298', 'yyy297']))
            self.assertFalse(jdb2.has_all(('xxx11', 'xxx10', 'yyy299')))

            jdb1 = JDb(jdb)
            self.assertTrue(jdb2.has_all(('xxx11', 'xxx12')))
            self.assertTrue(jdb1.has_all(('xxx11', 'xxx12')))

            ret = jdb.non_joint({'xxx11', 'xxx12', 'abc8888'})
            self.assertEqual(ret, {'abc8888'})

            ret = jdb1.non_joint(['xxx11', 'xxx12', 'abc8888'])
            self.assertEqual(ret, {'abc8888'})

            jdb['xxx10'] = 0
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            sync_id = jdb.sync_id

            jdb['xxx10'] = 100
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            sync_id = jdb.sync_id

            if jdb.zip_type == 'no':
                jdb['xxx20'] = 'a' * jdb.check_row(jdb.key_table['xxx20'])[-3] * 2
                self.assertGreater(jdb.sync_id, sync_id)
                self.assertEqual(jdb, jdb2)
                self.assertEqual(jdb.sync_id, jdb2.sync_id)

            sync_id = jdb.sync_id
            jdb.remove(jdb)
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertTrue(len(jdb) == 0)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            self.assertEqual(jdb.n_records, 0)
            self.assertEqual(jdb2.n_records, 0)

            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertGreater(jdb.sync_id, sync_id)
            self.assertGreater(jdb.sync_id, jdb2.sync_id)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            jdb['yyy1'] = 12
            jdb['yyy2'] = 23
            del jdb['yyy2']
            del jdb['yyy1']

            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb2)

            jdb['zzz1'] = 12
            jdb['zzz2'] = 23
            del jdb['zzz1']
            del jdb['zzz2']

            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb2)

            jdb['zzz1'] = 12
            jdb['zzz2'] = 23
            jdb.remove(['zzz1', 'zzz2'])

            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb2)

            jdb['zzz1'] = 34
            jdb['zzz2'] = 45
            jdb['zzz3'] = 56
            jdb2.sync()
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            self.assertEqual(jdb.key_table, jdb2.key_table)
            jdb.remove_fast('zzz1')
            jdb.remove_fast('zzz3')
            self.assertNotEqual(jdb.sync_id, jdb2.sync_id)

            self.assertEqual(jdb, jdb2)

            jdb.remove_fast('zzz2')
            self.assertEqual(jdb, jdb2)

            jdb['zzz1'] = 34
            jdb['zzz2'] = 45
            jdb['zzz3'] = 56
            jdb2.sync()
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            jdb.remove_fast('zzz1', 'zzz3', 'zzz3')
            self.assertNotEqual(jdb.sync_id, jdb2.sync_id)
            self.assertEqual(jdb, jdb2)

            jdb['zzz1'] = 34
            jdb['zzz2'] = 45
            jdb['zzz3'] = 56
            jdb['zzz4'] = 67
            jdb2.sync()
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            jdb.remove('zzz1')
            jdb.remove('zzz2')
            self.assertNotEqual(jdb.sync_id, jdb2.sync_id)
            self.assertEqual(jdb, jdb2)
            jdb.remove(['zzz3', 'zzz2', 'zzz1', 'zzz4'])
            self.assertEqual(jdb, jdb2)

            for _ in range(9):
                jdb.insert({'www1' : 31, 'www2' : 32, 'www3' : 33,  'www4' : 34})
                jdb.remove(['www1', 'www3', 'www2', 'www4'])

            self.assertEqual(jdb, expect)
            self.assertNotEqual(jdb.sync_id, jdb2.sync_id)
            self.assertEqual(jdb, jdb2)

            jdb['new_line'] = '\n\n\n\n'
            self.assertEqual(jdb['new_line'], '\n\n\n\n')

            jdb['new_line'] = '\0\0\0\0'
            self.assertEqual(jdb['new_line'], '\0\0\0\0')

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_unremove(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            index_size = config['index_size']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            self.assertFalse(jdb.keys[0])
            test_size = 300
            expect = {f'kkk{i}' : list(range(i+1)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertTrue(jdb.has_('kkk1'))
            self.assertTrue(jdb1.has_('kkk1'))
            self.assertTrue(set(jdb.keys[0]), {'kkk0'})
            self.assertTrue(set(jdb.keys[-1]), {'kkk299'})
            self.assertFalse(jdb.keys[len(expect)*4])

            rows = jdb.keys[:]
            self.assertEqual(len(rows), len(expect))
            self.assertEqual(rows.keys(), expect.keys())

            rows = jdb.keys[{'kkk1', 'kkk10', 'kkk100', 'kkk1000'}]
            self.assertEqual(rows.keys(), {'kkk1', 'kkk10', 'kkk100'})

            rows = jdb.keys[1:5]
            self.assertEqual(rows.keys(), {'kkk1', 'kkk2', 'kkk3', 'kkk4'})

            chg = jdb.remove(jdb[10:20])
            self.assertEqual(len(chg), 10)
            self.assertEqual(len(jdb), test_size-10)

            rows = jdb.keys[:]
            self.assertEqual(len(rows), test_size-10)

            rows = jdb.keys[::2]
            self.assertEqual(len(rows), test_size-155)

            rows = jdb.keys[0:]
            self.assertEqual(len(rows), test_size-10)

            rows = jdb.keys[:-1]
            self.assertEqual(len(rows), test_size-11)

            rows = jdb.keys[0.:]
            self.assertEqual(len(rows), len(expect))

            chk = jdb.check_row(test_size-10)
            self.assertEqual(chk[0], 'kkk10')

            chk = jdb.check_row(test_size-1)
            self.assertEqual(chk[0], 'kkk19')

            chk = jdb.check_row(test_size)
            self.assertFalse(chk)

            chk = jdb.unremove('kkk1000')
            self.assertFalse(chk)
            self.assertEqual(len(jdb), test_size-10)
            self.assertNotIn('kkk10', jdb)

            chk = jdb.unremove('kkk10')
            self.assertEqual(chk.keys(), {'kkk10'})
            self.assertEqual(len(jdb), test_size-9)
            self.assertIn('kkk10', jdb)

            chk = jdb.unremove('kkk15')
            self.assertEqual(chk.keys(), {'kkk15'})
            self.assertEqual(len(jdb), test_size-8)
            self.assertIn('kkk15', jdb)

            chk = jdb.unremove('kkk19')
            self.assertEqual(chk.keys(), {'kkk19'})
            self.assertEqual(len(jdb), test_size-7)
            self.assertIn('kkk19', jdb)

            lst = {'kkk11', 'kkk12', 'kkk16', 'kkk17'}
            for _ in range(9):
                chk = jdb.unremove(lst)
                self.assertEqual(chk.keys(), lst)
                chg = jdb.remove(lst)
                self.assertEqual(set(chg), lst)

            rows = jdb.keys[10:50]
            for kk in rows:
                val = jdb.pop(kk, None)
                self.assertFalse(kk in jdb)
                jdb.unremove(kk)
                self.assertTrue(kk in jdb)
                self.assertEqual(val, jdb[kk])

            del jdb[:]
            self.assertEqual(len(jdb), 0)

            expect = {f'k{v}':'b'+str(v) for v in range(test_size)}
            chg = jdb.insert(expect)

            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)

            del_keys = {'k10', }
            chg = jdb.remove(del_keys)
            self.assertEqual(set(chg), del_keys)

            chg = jdb.unremove(del_keys)
            self.assertEqual(set(chg), del_keys)
            self.assertEqual(jdb, expect)

            jdb['k1'] = '11' * 4 * index_size
            chg = jdb.remove(del_keys)
            self.assertEqual(set(chg), del_keys)

            del_keys2 = {'k15', }
            chg = jdb.remove(del_keys2)
            self.assertEqual(set(chg), del_keys2)

            chg = jdb.unremove(del_keys)
            self.assertEqual(set(chg), del_keys)

            chg = jdb.unremove(del_keys2)
            self.assertEqual(set(chg), del_keys2)

            self.assertEqual(jdb, jdb1)
            jdb['k1'] = 'b1'
            self.assertEqual(jdb, expect)
            jdb[123] = 'b2'
            self.assertIn(123, jdb)
            self.assertIn('123', jdb.keys)
            del jdb[123]
            self.assertNotIn(123, jdb)

            self.assertEqual(jdb, jdb1)
            with jdb.open(read_only=False) as fp:
                jdb.f_undelete(fp, 123)

            self.assertIn(123, jdb)
            self.assertEqual(jdb[123], 'b2')
            self.assertEqual(jdb['123'], 'b2')

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_revert(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            test_size = 100
            expect = {f'key{v}':list(range(v+1)) for v in range(test_size)}
            jdb1 = JDb(jdb)

            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)

            jdb1[:] = 0
            jdb ^= jdb1
            self.assertEqual(jdb, expect)

            key = 'key8'
            old_val = jdb[key]
            jdb[key] = new_val = 8
            self.assertNotEqual(jdb[key], old_val)
            self.assertEqual(jdb[key], new_val)

            ret = jdb.revert(key)
            self.assertTrue(key in ret)
            self.assertEqual(jdb[key], old_val)
            self.assertEqual(jdb1[key], old_val)

            ret = jdb.revert(key)
            self.assertTrue(key in ret)
            self.assertNotEqual(jdb[key], old_val)
            self.assertEqual(jdb[key], new_val)
            self.assertEqual(jdb1[key], new_val)

            ret = jdb.revert(key)
            self.assertTrue(key in ret)
            self.assertEqual(jdb[key], old_val)
            self.assertEqual(jdb1[key], old_val)
            self.assertEqual(jdb, expect)

            jdb.remove('key1', 'key2', 'key4', 'key8', 'key16')
            self.assertTrue(key not in jdb)
            self.assertEqual(jdb, jdb1)
            self.assertNotEqual(jdb, expect)

            ret = jdb.revert(key)
            self.assertTrue(key in ret)
            self.assertEqual(jdb[key], old_val)
            self.assertEqual(jdb1[key], old_val)
            self.assertNotEqual(jdb, expect)

            # ret = jdb.revert('key1', 'key2', 'key4', 'key16')
            jdb ^= 'key1'
            jdb ^= ['key2', 'key4', 'key16']
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)

            new_expect = {f'key{v}':list(range(test_size-v)) for v in range(test_size)}
            chg = jdb.replace(new_expect)
            self.assertNotEqual(jdb, expect)
            self.assertEqual(jdb, new_expect)
            self.assertEqual(jdb, jdb1)

            ret = jdb.revert(set(expect))
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)

            chg = jdb.remove(expect)
            self.assertEqual(len(jdb), 0)

            ret = jdb.revert(set(expect))
            self.assertEqual(jdb, expect)

            new_expect = {f'key{v}':list(range(test_size*2-v)) for v in range(test_size*2)}
            with jdb.open(read_only=True) as fp:
                _io0, fp0, _key_fp0 = jdb.f_get_fp(None)
                _io1, fp1, _key_fp, _chg = jdb.f_get_write_fp(None)
                self.assertFalse(_chg)
                self.assertTrue(_io0 is _io1)
                self.assertTrue(fp0 is fp)
                self.assertTrue(fp1 is fp)

                for key,val in new_expect.items():
                    if key not in jdb.key_table:
                        expect[key] = val
                        jdb.f_write(fp, key, val)

                    elif not random.randint(0, 1):
                        jdb.f_delete(fp, key)
                    else:
                        jdb.f_write(fp, key, val) # change

                    _key_fp.flush()

            self.assertNotEqual(jdb, expect)
            ret = jdb.revert(expect)
            self.assertEqual(jdb, expect)

            jdb['key13', 'key23'] = -1
            self.assertNotEqual(jdb, expect)

            jdb.unmodify('key13', 'key23')
            self.assertEqual(jdb, expect)

            jdb['key13', 'key23'] = -2
            self.assertNotEqual(jdb, expect)
            jdb ^= {'key13', 'key23'}
            self.assertEqual(jdb, expect)

            jdb.remove('key13', 'key23')
            self.assertNotEqual(jdb, expect)

            jdb.unremove('key13', 'key23')
            self.assertEqual(jdb, expect)

            del jdb['key13', 'key23']
            self.assertNotEqual(jdb, expect)
            jdb ^= {'key13', 'key23'}
            self.assertEqual(jdb, expect)

            jdb['key13'] = -3
            del jdb['key23']
            self.assertNotEqual(jdb, expect)
            jdb ^= {'key13', 'key23'}
            self.assertEqual(jdb, expect)

            jdb['key13'] = -3
            del jdb['key23']
            self.assertNotEqual(jdb, expect)

            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['key13', 'key23'] = 1
            jdb ^= jmem
            self.assertEqual(jdb, expect)

            jdb['key13', 'key23'] = 'val'
            jdb.unmodify('key13', 'key23')
            self.assertEqual(jdb, expect)

            # ---------------- derived flags through f_unwrite ----------------
            # f_unwrite swaps two rows, so the two payloads change places. A
            # preference (READ_ONLY, HIDDEN, ...) describes the record and stays
            # put, but LINK describes the VALUE and has to travel with it --
            # keeping the live row's bit left the record flagged as a link while
            # holding a plain value, which made it unreadable.
            jdb['lnk_dst'] = [7, 7]
            jdb['lnk_src'] = {'plain': 1}
            self.assertTrue(jdb.set_link('lnk_src', 'lnk_dst'))
            self.assertEqual(jdb['lnk_src'], [7, 7])
            self.assertEqual(jdb.keys.get_flags('lnk_src'), {'lnk_src': (int(JKeyFlag.LINK),0)})

            self.assertTrue('lnk_src' in jdb.revert('lnk_src'))
            self.assertEqual(jdb.keys.get_flags('lnk_src'), {'lnk_src': (0,0)})
            self.assertEqual(jdb['lnk_src'], {'plain': 1})
            self.assertEqual(jdb.get_link('lnk_src'), None)

            # ... and travel back up again on the next step
            self.assertTrue('lnk_src' in jdb.unmodify('lnk_src'))
            self.assertEqual(jdb.keys.get_flags('lnk_src'), {'lnk_src': (int(JKeyFlag.LINK),0)})
            self.assertEqual(jdb.get_link('lnk_src'), 'lnk_dst')
            self.assertEqual(jdb['lnk_src'], [7, 7])

            jdb ^= {'lnk_src'}                        # the third entry point
            self.assertEqual(jdb.keys.get_flags('lnk_src'), {'lnk_src': (0,0)})
            self.assertEqual(jdb['lnk_src'], {'plain': 1})

            # a link reverted onto an older link is still a link
            jdb['lnk_dst2'] = [8, 8]
            self.assertTrue(jdb.set_link('lnk2', 'lnk_dst'))
            self.assertTrue(jdb.set_link('lnk2', 'lnk_dst2'))
            self.assertEqual(jdb['lnk2'], [8, 8])
            self.assertTrue('lnk2' in jdb.revert('lnk2'))
            self.assertEqual(jdb.keys.get_flags('lnk2'), {'lnk2': (int(JKeyFlag.LINK),0)})
            self.assertEqual(jdb.get_link('lnk2'), 'lnk_dst')
            self.assertEqual(jdb['lnk2'], [7, 7])

            # preferences belong to the record, not to the version
            jdb['pref'] = 1
            jdb['pref'] = 2
            pref_flags = int(JKeyFlag.NO_CACHE | JKeyFlag.USER0)
            self.assertEqual(jdb.keys.set_flags('pref', no_cache=True, user0=True), {'pref': (pref_flags,0)})
            self.assertTrue('pref' in jdb.revert('pref'))
            self.assertEqual(jdb.keys.get_flags('pref'), {'pref': (pref_flags,0)})
            self.assertEqual(jdb['pref'], 1)

            # GROUP and EXPIRE are re-derived by write_key, so no revert can desync them
            rv_grp = jdb.add_group('rv_grp')
            rv_grp['n'] = 1
            jdb.revert('pref')
            self.assertEqual(jdb.keys.get_flags('rv_grp'), {'rv_grp': (int(JKeyFlag.GROUP),0)})
            self.assertEqual(jdb['rv_grp'], {'n': 1})

            jdb['exp'] = 1
            jdb.keys.set_flags('exp', ttl=5)
            jdb.set('exp', 2, key_flags='u')
            jdb.keys.set_flags('exp', ttl=0)
            jdb.revert('exp')
            exp_flags, exp_ttl = jdb.keys.get_flags('exp')['exp']
            self.assertEqual(bool(exp_flags & JKeyFlag.EXPIRE), exp_ttl > 0)

            # the fix must not open a back door on a write-locked record
            jdb['ro'] = 1
            jdb['ro'] = 2
            self.assertEqual(jdb.keys.set_flags('ro', read_only=True), {'ro': (int(JKeyFlag.READ_ONLY),0)})
            self.assertEqual(jdb.revert('ro'), {})
            self.assertEqual(jdb['ro'], 2)
            self.assertEqual(jdb.keys.set_flags('ro', read_only=False), {'ro': (0,0)})

            self.assertTrue(isinstance(jdb.del_group('rv_grp'), JDb))
            jdb.remove('lnk_src', 'lnk_dst', 'lnk_dst2', 'lnk2', 'pref', 'exp', 'ro')
            self.assertEqual(jdb, expect)

            # unrevertable but faster: flags=0
            jmem1 = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type, flags=JFlag.REVERT)
            jmem2 = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type, flags=0)

            jmem1 += expect
            jmem2 += expect
            self.assertEqual(jmem1, expect)
            self.assertEqual(jmem1, jmem2)

            jmem1 &= {key:list(range(16)) for key in expect}
            jmem2 &= jmem1
            self.assertEqual(jmem1, jmem2)

            jmem1 ^= expect
            self.assertEqual(jmem1, expect)

            jmem2 ^= expect
            self.assertNotEqual(jmem2, expect)
            self.assertNotEqual(jmem1, jmem2)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_date(self):
        now = dt.datetime.now()
        cdate = now - dt.timedelta(days=10)
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            _now = jdb.io.z_conv_days(now.timestamp())
            _cdate = jdb.io.z_conv_days(cdate.timestamp())
            self.assertEqual(_cdate + 10, _now)

            _today = dt.date.today()
            _next_day = _today + dt.timedelta(days=1)
            now = _today2 = dt.datetime.now()
            _prev_day = _today2 - dt.timedelta(days=1)
            expect = {f'kk{i}' : 'vvvvvvvv'+str(i+123) for i in range(100)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb.get_all(), expect)
            self.assertEqual(jdb.get_n(expect), expect)
            self.assertEqual(jdb[:], expect)
            self.assertEqual(jdb[_today], expect)
            self.assertEqual(jdb[_today2], expect)
            self.assertEqual(jdb[_today:_next_day], expect)
            self.assertEqual(jdb[_prev_day:_next_day], expect)
            self.assertEqual(set(jdb.keys[_today]), set(expect))
            self.assertEqual(set(jdb.keys[_today2]), set(expect))
            self.assertEqual(set(jdb.keys[_today:_next_day]), set(expect))
            self.assertEqual(set(jdb.keys[_prev_day:_next_day]), set(expect))

            self.assertEqual(jdb.find('', date=0, with_value=True), expect)
            self.assertEqual(jdb.find('', date=_today, with_value=True), expect)
            self.assertEqual(jdb.find('', date=_today2, with_value=True), expect)
            self.assertEqual(jdb.find('', date=str(_today), with_value=True), expect)

            matches = jdb[_today:]
            self.assertEqual(matches, expect)
            matches = jdb.keys[_today:]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[now:]
            self.assertEqual(matches, expect)
            matches = jdb.keys[now:]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[dt.date(2010, 1, 1):]
            self.assertEqual(matches, expect)
            matches = jdb.keys[dt.date(2010,1, 1):]
            self.assertEqual(set(matches), set(expect))
            matches_2 = jdb.keys[Query()._date >= dt.date(2010,1,1)]
            self.assertEqual(matches, matches_2)

            matches = jdb[cdate:]
            self.assertEqual(matches, expect)
            matches = jdb.keys[cdate:]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[:_next_day]
            self.assertEqual(matches, expect)
            matches = jdb.keys[:_next_day]
            self.assertEqual(set(matches), set(expect))

            _now = now + dt.timedelta(days=1)
            matches = jdb[:_now]
            self.assertEqual(matches, expect)
            matches = jdb.keys[:_now]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[:dt.date(2010, 1, 1)]
            self.assertTrue(not matches)
            matches = jdb.keys[:dt.date(2010, 1, 1)]
            matches_2 = jdb.keys[Query()._date <= dt.date(2010, 1, 1)]

            matches = jdb[:cdate]
            self.assertTrue(not matches)
            matches = jdb.keys[:cdate]
            self.assertTrue(not matches)

            matches = jdb[cdate:_now]
            self.assertEqual(matches, expect)
            matches = jdb.keys[cdate:_now]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[dt.datetime(2010, 1, 1):_now]
            self.assertEqual(matches, expect)
            matches = jdb.keys[dt.datetime(2010, 1, 1):_now]
            self.assertEqual(set(matches), set(expect))
            matches_2 = jdb.keys[Query()._date.between(dt.datetime(2010, 1, 1),_now)]
            self.assertEqual(matches, matches_2)

            matches = jdb[now:cdate]
            self.assertTrue(not matches)
            matches = jdb.keys[now:cdate]
            self.assertTrue(not matches)

            info0 = jdb.keys['kk1']
            self.assertNotEqual(info0[-1], str(cdate.date()))

            with jdb.open(read_only=False) as fp:
                jdb.f_change_days(fp, 'kk1', _cdate)

            self.assertEqual(jdb.keys['kk1'][-1], str(cdate.date()))
            info1 = jdb.keys['kk2']
            self.assertNotEqual(info1[-1], str(cdate.date()))
            jdb.keys['kk2'] = _cdate

            _old = cdate + dt.timedelta(days=1)
            matches = jdb[:_old]
            self.assertEqual(len(matches), 2)
            self.assertEqual(expect['kk1'], matches['kk1'])
            self.assertEqual(expect['kk2'], matches['kk2'])

            matches = jdb[_old:]
            self.assertEqual(set(expect) - set(matches), {'kk1', 'kk2'})
            jdb[:_old] = 'test'
            self.assertEqual(jdb['kk1'], 'test')
            self.assertEqual(jdb['kk2'], 'test')

            matches = jdb[:_old]
            self.assertEqual(len(matches), 2)
            self.assertNotEqual(expect['kk1'], matches['kk1'])
            self.assertNotEqual(expect['kk2'], matches['kk2'])

            matches = jdb[:_now]
            self.assertEqual(set(matches), set(expect))
            self.assertEqual(matches['kk1'], 'test')
            self.assertEqual(matches['kk2'], 'test')

            info = jdb.keys['kk3']
            self.assertNotEqual(info[-1], str(cdate.date()))
            jdb.set_date('kk3', cdate.date())
            info1 = jdb.keys['kk3']
            self.assertNotEqual(info, info1)
            self.assertEqual(info1[-1], str(cdate.date()))
            self.assertNotEqual(info1[-2], str(cdate.date()))

            jdb.set_date('kk3', mdate=cdate.date())
            info2 = jdb.keys['kk3']
            self.assertNotEqual(info, info2)
            self.assertNotEqual(info1, info2)
            self.assertEqual(info2[-1], str(cdate.date()))
            self.assertEqual(info2[-2], str(cdate.date()))

            del jdb['kk3']
            jdb.unremove('kk3')
            info = jdb.keys['kk3']
            self.assertEqual(info[-1], str(cdate.date()))
            self.assertEqual(info[-2], str(cdate.date()))

            val = jdb['kk3']
            jdb.remove('kk3')
            jdb['kk3'] = val
            info = jdb.keys['kk3']
            self.assertNotEqual(info[-1], str(cdate.date()))
            ref_days = jdb.keys['kk4'][-1]
            self.assertEqual(info[-1], ref_days)

            jdb.set_date('kk3', cdate.date())
            jdb2 = JDb(jdb)
            self.assertEqual(jdb, jdb2)
            jdb['kk3'] = 'kk3'
            if jdb.n_lines != jdb2.n_lines:
                self.assertEqual(jdb['kk3'], jdb2['kk3'])
                self.assertEqual(jdb.key_table, jdb2.key_table)
                self.assertEqual(jdb.sync_id, jdb2.sync_id)

            info = jdb.keys['kk3']
            self.assertNotEqual(info[-1], ref_days)
            self.assertEqual(info[-1], str(cdate.date()))

            jdb.remove('kk3')
            jdb.unremove('kk3')
            info = jdb.keys['kk3']
            self.assertEqual(info[-1], str(cdate.date()))

            jdb.upgrade()
            info = jdb.keys['kk3']
            self.assertEqual(info[-1], str(cdate.date()))

            jdb.set_date('kk3', '1000-01-01')
            info1 = jdb.keys['kk3']
            self.assertEqual(info1[-1], '1000-01-01')
            self.assertEqual(info[-2], info1[-2])

            jdb.set_date('kk3', '1990-01-01', '2000-10-10', ttl=30)
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], '1990-01-01')
            self.assertEqual(info2[-2], '2000-10-10')
            # ttl=30 from a 2000-10-10 modified date: the row is long expired.
            # keys[...] is the metadata view and still shows it ...
            self.assertEqual(len(jdb.keys[:dt.date(2000,12,12)]), 1)
            self.assertEqual(len(jdb.keys[:dt.date(1990,12,12)]), 0)
            self.assertEqual(len(jdb.keys[:dt.datetime(1990,12,12)]), 1)
            # ... while the value view no longer has a value to return for it
            self.assertEqual(len(jdb[:dt.date(2000,12,12)]), 0)
            self.assertEqual(len(jdb[:dt.date(1990,12,12)]), 0)
            self.assertEqual(len(jdb[:dt.datetime(1990,12,12)]), 0)
            self.assertEqual(dict(jdb.keys.item_iter('kk3', with_expired=False)), {})
            self.assertEqual(set(jdb.find('kk', date='2000-10-10')), set())
            self.assertEqual(set(jdb.find('kk', date={'$between': ('2000-10-01', '2000-10-30')})), set())
            self.assertEqual(set(jdb.find('kk', date='1990-12-1 1990-12-30')), set())
            self.assertEqual(set(jdb.find('kk', date=dt.date(2000, 10, 10))), set())
            self.assertEqual(set(jdb.find('kk', date=dt.datetime(1990, 1, 1))), set())

            jdb.keys['kk3'] = '2000-1-1 1990-10-10'
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], '1990-10-10')
            self.assertEqual(info2[-2], '2000-01-01')

            jdb.keys['kk3'] = '1990-10-10 2000-1-1'
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], '1990-10-10')
            self.assertEqual(info2[-2], '2000-01-01')

            today = dt.date.today()
            yesterday = today - dt.timedelta(days=1)
            prev_week = today - dt.timedelta(days=7)
            prev_prev_week = today - dt.timedelta(days=14)

            jdb.keys['kk3'] = f'{today} {today}'
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], str(today))
            self.assertEqual(info2[-2], str(today))

            today2 = dt.datetime.now()
            jdb.keys['kk3'] = today2
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], str(today))
            self.assertEqual(info2[-2], str(today))

            jdb.keys['kk3'] = -1
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], str(today))
            self.assertEqual(info2[-2], str(today))
            info3 = dict(jdb.keys.item_iter('kk3'))
            self.assertEqual(info2, info3.get('kk3',None))
            info4 = dict(jdb.keys.item_iter(Query()._id == 'kk3'))
            self.assertEqual(info3, info4)
            for key,val in jdb1.keys.item_iter(slice(None)):
                self.assertEqual(jdb.keys[key], val)

            jmem = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem['group'] = jdb
            jmem.keys['group:::kk3'] = dt.datetime(yesterday.year, yesterday.month, yesterday.day)
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], str(yesterday))
            self.assertEqual(info2[-2], str(yesterday))

            jdb.keys['kk4'] = yesterday
            info2 = jdb.keys['kk4']
            self.assertEqual(info2[-2], str(yesterday))

            jdb.keys['kk3', 'kk4'] = today
            for key,info in jdb.keys.item_iter(('kk3', 'kk4')):
                self.assertEqual(info[-2], str(today))

            jdb.keys[re.compile(r'k[34]$')] = yesterday
            for key,info in jdb.keys.item_iter(re.compile(r'k[34]$')):
                self.assertEqual(info[-2], str(yesterday))

            matches = jdb.keys[lambda key,info:info[-1] == str(yesterday)]
            jdb.keys[lambda key,info:info[-2] == str(yesterday)] = today
            for key,info in jdb.keys.item_iter(lambda key:key.endswith(('k3', 'k4'))):
                self.assertEqual(info[-2], str(today))

            jdb.keys[lambda key:key.endswith(('k3', 'k4'))] = yesterday
            for key,info in jdb.keys.item_iter(('kk3', 'kk4')):
                self.assertEqual(info[-2], str(yesterday))

            jmem.keys[':::kk3'] = today
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-2], str(today))
            jdb.keys[::'kk4'] = '2000-1-1 1990-10-10'
            matches = jdb.keys[::'kk4']
            self.assertTrue(len(matches) > 4)
            for key,info2 in matches.items():
                self.assertEqual(info2[-1], '1990-10-10', filename)
                self.assertEqual(info2[-2], '2000-01-01', filename)

            matches = jdb.keys[1]
            self.assertTrue(len(matches) == 1)
            key = list(matches)[0]
            jdb.keys[1] = prev_week
            for key,info in jmem.keys[f'group:::{key}'].items():
                self.assertEqual(info[-2], str(prev_week))

            matches = jdb.keys[-1.]
            self.assertTrue(len(matches) >= 1)
            jdb.keys[-1.] = f'{prev_prev_week} {prev_prev_week}'
            for key,info2 in jmem.keys[f'group:::{key}'].items():
                self.assertEqual(info2[-1], str(prev_prev_week))
                self.assertEqual(info2[-2], str(prev_prev_week))

            jdb[matches] = lambda k,v : f'{k}_{v.replace("v", "")}'
            for key,info2 in jdb.keys[matches].items():
                self.assertEqual(info2[-1], str(prev_prev_week))
                self.assertEqual(info2[-2], str(today))

            jdb[1] = lambda k,v : f'{k}_{v}'
            self.assertTrue(jdb[1].startswith('1_'))

            matches = jdb.keys[prev_prev_week:prev_week]
            self.assertTrue(len(matches) == 0)
            jdb.keys[prev_prev_week:prev_week] = today

            prev_week = dt.datetime(prev_week.year, prev_week.month, prev_week.day)
            matches = jdb.keys[:prev_week]
            self.assertTrue(len(matches) > 0)
            jdb.keys[:prev_week] = dt.datetime.now()

            matches = jdb.keys[:prev_week]
            self.assertTrue(len(matches) == 0)

            matches = jdb.keys[[5, -1]] # get 5th & last records
            self.assertEqual(len(matches), 2)
            jdb.keys[[5, -1]] = prev_week
            for key in matches:
                info = jdb.keys[key]
                self.assertEqual(info[-1], str(prev_week.date()))

            jdb.keys[-1] = yesterday
            for key,info in jdb.keys[-1].items():
                self.assertEqual(info[-2], str(yesterday))

            matches = jmem.keys[[':::kk13', ':::kk14', ':::kk13']]
            self.assertEqual(len(matches), 2)
            jmem.keys[[':::kk13', ':::kk14', ':::kk13']] = prev_prev_week
            for key,info in jmem.keys[matches].items():
                self.assertEqual(info[-2], str(prev_prev_week))

            jmem[matches] = None
            for key,info in jmem.keys[matches].items():
                self.assertEqual(info[-2], str(today))
                self.assertEqual(info[-1], str(prev_prev_week))

            del jmem[matches]
            self.assertEqual(len(jmem[matches]), 0)
            self.assertEqual(len(jmem.keys[matches]), 0)

            if 'kk15' in jdb.keys:
                del jmem[':::kk15']
                info = jmem.keys[':::kk15']
                self.assertEqual(info, {})

            with jdb.open() as fp:
                jdb.f_write(fp, 'new_key100', 'new_value', cdays=str(yesterday))
                jdb.f_write(fp, 'new_key101', list(range(16)), cdays=jdb.io.z_conv_str_to_days(f'{str(yesterday)} {str(today)}'))

            info = jdb.keys['new_key100']
            self.assertEqual(info[-1], str(yesterday))
            self.assertEqual(info[-2], str(today))

            info = jdb.keys['new_key101']
            self.assertEqual(info[-1], str(yesterday))
            self.assertEqual(info[-2], str(today))

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_type(self):
        codec = JIoVAL_U()
        with self.assertRaises(TypeError):
            jdb = JDb(data_type='J+U', key_codec=None, val_codec=codec)

        codec.register(
            dumps=lambda data: bytes(b ^ 0xA5 for b in marshal_dumps(data)),
            loads=lambda data: marshal_loads(bytes(b ^ 0xA5 for b in data)),
        )

        unregister_user_key_codec()
        with self.assertRaises(RuntimeError):
            jdb = JDb(data_type='U+U', key_codec=None, val_codec=codec)

        register_user_key_codec(xor_dumps, xor_loads)
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb, write_hook=lambda k,v:bool(k) and isinstance(v, list))
            test_size = 100
            expect = {f'key{v}'*((v&0x7)+1) : list(range(v+1)) for v in range(test_size)}
            jdb += expect
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb.get_all(), expect)
            self.assertEqual(jdb[expect], expect)
            self.assertEqual(jdb, jdb1)
            old_val = jdb['key0']
            with self.assertRaises(TypeError):
                jdb1['key0'] = 0

            with self.assertRaises(TypeError):
                jdb1[Query()._id == 'key0'] = 0

            self.assertEqual(jdb1['key0'], old_val)
            old_data_type = jdb.data_type
            old_api_ver = jdb.api_ver
            chg_type_lut = {'J':'S', 'M':'J', 'L':'S', 'S':'J'}
            chg_api_lut = {0:1, 1:0}
            new_type = chg_type_lut.get(old_data_type[0], 'S')
            new_api = chg_api_lut.get(old_api_ver, 0)
            jdb.change_KEY(api_ver=new_api, KEY_type=new_type)
            self.assertNotEqual(jdb.api_ver, old_api_ver)
            self.assertNotEqual(jdb.data_type, old_data_type)
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            with self.assertRaises(TypeError):
                jdb1['key0'] = 0
            self.assertEqual(jdb1['key0'], old_val)
            jdb.change_KEY(api_ver=old_api_ver, KEY_type=old_data_type[0])
            self.assertEqual(jdb.api_ver, old_api_ver)
            self.assertEqual(jdb.data_type, old_data_type)
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            with self.assertRaises(TypeError):
                jdb1['key0'] = 0
            self.assertEqual(jdb1['key0'], old_val)

            jdb2 = JDb(data_type='J+U', zip_type=jdb.zip_type, key_limit=jdb.key_limit,  val_codec=codec)
            jdb2 += jdb
            self.assertEqual(jdb2, jdb)

            jdb3 = JDb(data_type='S+U', zip_type=jdb.zip_type, key_limit=jdb.key_limit,  val_codec=codec)
            jdb3 += jdb
            self.assertEqual(jdb3, jdb)
            self.assertEqual(jdb2, jdb3)

            jdb4 = JDb(data_type='U+U', zip_type=jdb.zip_type, key_limit=jdb.key_limit,  val_codec=codec)
            jdb4 += jdb
            self.assertEqual(jdb4, jdb)
            self.assertEqual(jdb3, jdb4)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

        codec.unregister()
        with self.assertRaises(TypeError):
            jdb = JDb(data_type='S+U', key_codec=None, val_codec=codec)

    def test_memory(self):
        test_size = 10
        jdb = JDb()
        jdb1 = JDb(jdb)
        expect = {str(k):0 for k in range(test_size)}
        chg = jdb.insert(expect)
        self.assertEqual(chg, expect)
        self.assertEqual(jdb, expect)
        self.assertEqual(jdb.n_lines, test_size)
        jdb[:] = 1
        self.assertNotEqual(jdb, expect)
        self.assertGreaterEqual(jdb.n_lines, test_size*2)
        jdb[:] = 0
        self.assertEqual(jdb, expect)
        self.assertGreaterEqual(jdb.n_lines, test_size*2)
        jdb[:] = 2
        self.assertNotEqual(jdb, expect)
        self.assertGreaterEqual(jdb.n_lines, test_size*2)
        jdb.revert(expect)
        self.assertEqual(jdb, expect)
        self.assertGreaterEqual(jdb.n_lines, test_size*2)
        self.assertEqual(jdb, jdb1)

        expect = {str(k):list(range(32)) for k in range(test_size)}
        expect2 = {str(k):list(range(16)) for k in range(test_size)}

        jdb.replace(expect)
        self.assertEqual(jdb, expect)
        self.assertGreaterEqual(jdb.n_lines, test_size*3)

        jdb.replace(expect2)
        self.assertEqual(jdb, expect2)
        self.assertGreaterEqual(jdb.n_lines, test_size*4)

        jdb.revert(expect)
        self.assertEqual(jdb, expect)
        self.assertGreaterEqual(jdb.n_lines, test_size*4)

        jdb.replace(expect2)
        self.assertEqual(jdb, expect2)
        self.assertGreaterEqual(jdb.n_lines, test_size*4)
        self.assertEqual(jdb, jdb1)

        test_size_a = 32
        expect_a = {f'key{v}':1 for v in range(test_size_a)}
        expect_b = {f'key{v}': {
            'str':f'value-{v:03d}'*((v%test_size_a)+1),
            'list':[random.randrange(v+test_size_a) for _ in range(test_size_a)],
            'float1':1.1,
            'float2':-1.,
            'bool': True,
            'max_int':2**64-1,
            'min_int':-(2**63)} for v in range(test_size_a)}
        expect_b.update({'max_int':2**64-1, 'min_int':-(2**63), 'bool': True, 'float1':1.1, 'float2':-1.})
        expect_c = {f'key{k}':f'vvv{k}' for k in range(test_size_a)}

        for config in self.jdb_configs:
            filename = config['KEY_file']
            zip_type = config['zip_type']
            data_type = config['data_type']
            cache_limit = config['cache_limit']
            key_limit = config['key_limit']

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            for (val0, val1, val1_0, val1_1) in [(0, 1, [0]*16, [1]*16),
                                                ([0]*16, [1]*16, 0, 1),
                                                (0, [0]*16, 1, [1]*16),
                                                ([0]*16, 0, [1]*16, 1),
                                                ([0]*16, 0, 1, [1]*16),
                                                (0, [0]*16, [1]*16, 1),
                                                (0, [0]*16, [1]*32, [1]*64),
                                                ([0]*64, 0, [1]*32, [1]*16),
                                                ([0]*64, [0]*32, [1]*16, [1]*1)]:
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem['E'] = val1_0
                jmem['A'] = val1
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem.revert(['A', 'E'])
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A=1] chg N
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['A'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('D', 'E')
                jmem1 = JDb(jmem).sync()
                jmem['B'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E', 'F'], val0)
                jmem.remove('D', 'E', 'F')
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A=2] chg N
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['A'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem['D'] = val1_0
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['B'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem['D'] = val1_0
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A=3] del N + add N (ADD == DEL)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C')
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C', 'D')
                jmem.insert(['E', 'F'], val0)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C', 'D')
                jmem.insert(['E', 'F', 'G', 'H'], val0)
                jmem.remove('G', 'H')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.insert(['E', 'F'], val0)
                jmem.remove('E', 'F')
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.insert({'D':val1, 'E':val0})
                jmem.remove('D', 'E')
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A-1] del N (N > 0)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A-2] del N + add M (DEL > ADD)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                jmem['B'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C')
                jmem.insert(['C', 'D'], val1)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C')
                jmem['C'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                with jmem.open() as fp:
                    for kk in 'XYZABC':
                        jmem.f_write(fp, kk, val0)
                    jmem.f_write(fp, 'D', val1_0)
                    jmem.f_delete(fp, 'D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C')
                jmem['C'] = val1_1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                jmem.remove(['B', 'C', 'D'])
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                jmem.remove(['C', 'D'])
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                with jmem.open() as fp:
                    for kk in 'XYZABC':
                        jmem.f_write(fp, kk, val0)
                    jmem.f_write(fp, 'D', val1_0)
                    jmem.f_delete(fp, 'D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val1_1
                jmem.remove('C', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A-3] add N + del M (DEL > ADD)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                jmem.remove('C', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.insert(['E', 'F'], val0)
                jmem.remove('D', 'E', 'F')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A+1] add N
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('D', 'E')
                jmem1 = JDb(jmem).sync()
                jmem['E'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['E'] = val1_0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A+2] add N + chg M
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val0, 'X':val1})
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'B'], val0)
                jmem.remove('B')
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val0, 'X':val1_0})
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val0, 'B':val0, 'X':val1_0, 'Y':val1_0})
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A+3] add N + del M  or del M + add N (ADD > DEL)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.insert(['A', 'B'], val0)
                jmem.remove('B')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B'], val0)
                jmem.remove('B')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A')
                jmem.insert(['C', 'D'], val0)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'X':val1_0, 'Y':val0, 'Z':val0})
                jmem1 = JDb(jmem).sync()
                jmem.insert(['A', 'B'], val0)
                jmem.remove('B')
                jmem['X'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'A':val1_0, 'B':val1_0, 'C':val0, 'D':val0})
                jmem1 = JDb(jmem).sync()
                jmem.insert(['E', 'F', 'G'], val0)
                jmem.remove('G')
                jmem.replace(['A', 'B'], val0)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'A':val1_0, 'B':val1_0, 'C':val1_0, 'D':val0, 'E':val0, 'F':val0})
                jmem.remove(['D', 'E', 'F'])
                jmem1 = JDb(jmem).sync()
                jmem.revert('E')
                with jmem.open() as fp:
                    jmem.f_write(fp, 'X', val1_0)
                    jmem.f_delete(fp, 'X')
                jmem['B'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B1-2]
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('A')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B1=0]
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1_0
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['C', 'E'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['C', 'E', 'A'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['E','A'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['A', 'E'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem['B'] = val1_0
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['A', 'B', 'C'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E', 'F'], val0)
                jmem.remove('D', 'E', 'F')
                jmem1 = JDb(jmem).sync()
                jmem.update(['A', 'B', 'C'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B2-0] chg N + del M (DEL > ADD)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1_0
                jmem.remove('C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['D', 'C'], val1_0)
                jmem.remove('C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['D', 'C'], val1_0)
                jmem.remove('D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['A'] = val1_0
                jmem.remove('A')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B2=0] ADD == DEL
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val1_0, 'E':val1_1})
                jmem['E'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'A':val0, 'B':val0, 'C':val0, 'D':val0, 'E':val1_0, 'F':val0, 'G':val0})
                jmem.remove('F', 'G')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val1_1
                jmem['B'] = val1_1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # --
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(list(range(32)), val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove(list(range(0,32,3)))         # DEL
                jmem.update(list(range(0,32,3)), val1)   # ADD + CHG
                jmem.update(list(range(1,32,3)), val1_0) # ADD + CHG
                jmem.update(list(range(2,32,3)), val1_1) # ADD + CHG
                jmem.remove(list(range(1,32,2)))         # DEL
                jmem.revert(list(range(32)))             # ADD + CHG
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                #--
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                adds = jmem.insert(['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'], val0)
                jmem.remove(adds)
                jmem1 = JDb(jmem).sync()
                with jmem.open() as fp:
                    jmem.f_undelete(fp, 'E')
                    jmem.f_write(fp, 'E', val1_0)
                    jmem.f_unwrite(fp, 'E')
                    jmem.f_delete(fp, 'E')
                    jmem.f_undelete(fp, 'H')

                with jmem1.open() as fp:
                    jmem1.f_write(fp, 'C', val1_0*2)
                    jmem1.f_undelete(fp, 'E')

                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                error = jmem.check_error()
                self.assertTrue(not error)
                #--
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem['A'] = val1_0
                jmem.insert(['B', 'C', 'D', 'E'], val0)
                jmem['E'] = val1_0
                jmem.remove('B', 'C', 'D')
                jmem1 = JDb(jmem).sync()
                with jmem.open() as fp:
                    jmem.f_undelete(fp, 'C')
                    jmem.f_write(fp, 'C', val1_0)
                    jmem.f_unwrite(fp, 'C')
                    jmem.f_delete(fp, 'C')

                jmem.revert('E')
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)
                self.assertEqual(jmem.key_table, jmem1.key_table)

            #------------------------------
            jmem = JDb(None, data_type=data_type, zip_type=zip_type, key_limit=key_limit)
            self.assertTrue(isinstance(jmem.files_obj, JMemFiles))

            jmem1 = JDb(jmem, flags=JFlag.REVERT|JFlag.SPLIT)
            jmem1['key0'] = val = list(range(200))

            val_fp = jmem.files_obj.VAL_open(0)
            pos = val_fp.seek(0, 2)
            val_fp.seek(pos+100)
            val_fp.write(b'\n')
            self.assertEqual(val_fp.tell(), pos+101)
            val_fp.close()

            self.assertEqual(jmem1['key0'], val)
            self.assertEqual(jmem1, jmem)
            del jmem1['key0']
            self.assertEqual(jmem1, jmem)
            self.assertEqual(jmem1.n_lines, 1)
            val = list(range(100))
            jmem1 += {f'key{k+1}':val for k in range(2)}
            self.assertEqual(jmem1['key1'], val)
            self.assertEqual(jmem1['key2'], val)
            self.assertLessEqual(jmem1.n_lines, 3)
            jmem1 -= jmem
            self.assertEqual(len(jmem1), 0)
            jmem1.recycle()
            self.assertEqual(len(jmem.keys[0.:]), 0)
            test_size = test_size_a
            expect = expect_a
            jmem.insert(expect)
            self.assertEqual(jmem, expect)

            jmem[:] = lambda k,v:v+1 if k.endswith('0') else v
            self.assertEqual(jmem, {k:v+1 if k.endswith('0') else v for k,v in expect.items()})
            jmem[:10] = 0
            ret = jmem.find(EQ=0)
            self.assertEqual(len(ret), 10)

            del jmem[:10]
            ret = jmem.find(EQ=0)
            self.assertEqual(len(ret), 0)

            del jmem[lambda k: k.endswith('1')]
            self.assertEqual(set(ret), jmem.non_joint(ret))

            ret = jmem[lambda k,v: k.find('2') >= 0 and v > 1]
            del jmem[lambda k,v: k.find('2') >= 0 and v > 1]
            self.assertEqual(set(ret), jmem.non_joint(ret))

            ret = jmem[lambda k: k.find('2') >= 0]
            jmem[lambda k:k.find('2') >= 0] = lambda k,v:v+10
            self.assertEqual(jmem[lambda k:k.find('2') >= 0], {k:v+10 for k,v in ret.items()})

            jmem[lambda k,v:k.find('1') >= 0 and v > 10] = lambda k,v:v+10
            ret = jmem.find(GT=20)
            self.assertEqual(len(ret), 1)

            expect = expect_b
            total = test_size_a
            del jmem[:]
            ret = jmem.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(jmem, expect)
            self.assertEqual(len(jmem), len(expect))
            self.assertEqual(len(jmem.keys[lambda k:k.startswith('key')]), total)
            self.assertEqual(len(jmem.keys[lambda k,v:k.startswith('key') and v[3] > 0]), total)
            self.assertEqual(len(jmem.find(FUNC=lambda v:isinstance(v, dict))), total)
            self.assertEqual(len(jmem.find(FUNC=lambda k,v:k.startswith('key') and isinstance(v, dict))), total)

            for data_type_str in ('L+J', 'M+M', 'J+P', 'S+S', 'J+Y'):
                for zip_type_str in ('gz', 'bz', 'xz', 'br', 'z1', 'lz'):
                    if jmem.data_type == data_type_str and jmem.zip_type == zip_type_str: continue
                    jmem.upgrade(zip_type=zip_type_str, data_type=data_type_str)
                    self.assertEqual(jmem, expect)
                    self.assertEqual(jmem.data_type, data_type_str)
                    self.assertEqual(jmem.zip_type, zip_type_str)

            jmem.upgrade(data_type=data_type, zip_type=zip_type)

            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.len_(), 0)

            ret = jdb.insert(expect)
            self.assertEqual(len(jdb), len(expect))
            self.assertEqual(jdb.len_(), len(expect))
            self.assertEqual(ret, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(len(jdb.keys[lambda k:k.startswith('key')]), total)
            self.assertEqual(len(jdb.keys[lambda k,v:k.startswith('key') and v[3] > 0]), total)
            self.assertEqual(len(jdb.find(FUNC=lambda v:isinstance(v, dict))), total)
            self.assertEqual(len(jdb.find(FUNC=lambda k,v:k.startswith('key') and isinstance(v, dict))), total)
            ret = jdb.remove(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(len(jdb), 0)
            ret = jdb.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(jdb, expect)
            jdb.remove_fast(expect)
            self.assertEqual(len(jdb), 0)
            ret = jdb.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(jmem, jdb)

            jmem_list = []
            for _ in range(4):
                jmem_list.append(JDb(jmem))

            jmem1 = jmem_list[0]
            self.assertEqual(jmem.files_obj, jmem1.files_obj)

            self.assertEqual(len(jmem), len(expect))
            self.assertEqual(jmem.len_(), len(expect))

            val = jmem.pop('key0')
            self.assertEqual(val, expect['key0'])

            jmem[:] = 0
            for kk,vv in jmem.items():
                self.assertEqual(vv, 0)

            self.assertNotEqual(jmem, expect)

            jmem['key-1'] = expect['key0']
            self.assertEqual(jmem['key-1'], expect['key0'])

            jmem.restore(jdb)
            self.assertEqual(jmem, jdb)

            total = jdb.len_()
            del jdb[lambda key,val: key.endswith('0')]
            self.assertLess(len(jdb), total)

            Key = Query()
            total = jdb.len_()
            del jdb[::Key.endswith('1')]
            self.assertLess(len(jdb), total)

            old = jdb.get_all()
            jdb['not_exist'] = lambda k,v: v
            self.assertEqual(len(jdb), len(old))
            self.assertEqual(jdb, old)

            jmem[:] = 1
            jmem[:] = lambda k,v: v+1
            for kk,vv in jmem.items():
                self.assertEqual(vv, 2)

            for ref in (0x01010101_01010101, 0x01010101_0101, 0x01010101, 0x0101):
                val = {f'pad{v}':ref*v for v in range(test_size)}
                ret = jdb.update(val)
                self.assertEqual(jdb.get_n(val), val)

                val = {f'pad{v}':{'VAL':ref*v} for v in range(test_size)}
                ret = jdb.replace(val)
                self.assertEqual(jdb.get_n(val), val)

                val = {f'pad{v}':[ref*v] for v in range(test_size)}
                ret = jdb.replace(val)
                self.assertEqual(jdb.get_n(val), val)

            for jmem1 in jmem_list:
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.get_all(), jmem1.get_all())
                self.assertEqual(jmem.keys[:], jmem1.keys[:])
                self.assertEqual(jmem.sync_id, jmem1.sync_id)

            jdb.remove_fast(set(jdb))
            self.assertEqual(len(jdb), 0)

            jdb1 = JDb(jdb)
            self.assertEqual(len(jdb1), 0)

            max_value = 2 ** 43 - 16
            with jdb.open(read_only=False) as fp:
                jdb.io.sync_id = max_value
                jdb.io.swap_id = max_value
                jdb.io.remv_id = max_value

            with jdb.open() as fp:
                jio, fp, key_fp = jdb.f_get_fp(fp)
                self.assertTrue(key_fp is not None)
                self.assertTrue(jio is not None)
                key_fp.seek(0) # begin
                self.assertEqual(key_fp.tell(), 0)
                key_fp.seek(128, 1) # current
                self.assertEqual(key_fp.tell(), 128)
                key_fp.seek(0, 2) # end
                self.assertGreaterEqual(key_fp.tell(), 128)
                self.assertEqual(jdb.sync_id, max_value)
                self.assertEqual(jdb.swap_id, max_value)
                self.assertEqual(jdb.remv_id, max_value)

            expect = expect_c
            ret = jdb.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb1, expect)
            self.assertEqual(set(jdb.keys), set(jdb1.keys))
            self.assertEqual(set(jdb.keys.items()), set(jdb1.keys.items()))
            self.assertEqual(set(jdb.keys.values()), set(jdb1.keys.values()))

            jdb.remove_fast(expect)
            self.assertEqual(len(jdb), 0)

            self.assertEqual(jdb1, jdb)
            self.assertEqual(set(jdb.keys), set(jdb1.keys))
            self.assertEqual(set(jdb.keys.items()), set(jdb1.keys.items()))
            self.assertEqual(set(jdb.keys.values()), set(jdb1.keys.values()))

            jdb['test'] = val = list(range(test_size))
            self.assertEqual(val, jdb['test'])
            info = jdb.keys['test']
            file_id, offset, _row_size, val_size = info[1:5]
            err_byte = b'\x00' if jdb.data_type.endswith('Y') else b'a'

            with jdb.files_obj.VAL_open(file_id, 'rb+') as fp:
                fp.seek(offset)
                fp.write(err_byte * val_size)

            try:
                ret = jdb1['test']
                self.assertNotEqual(val, ret)
                jdb1['test'] = val
            except:
                jdb1['test'] = val

            self.assertEqual(val, jdb['test'])
            with jdb.files_obj.VAL_open(file_id, 'rb+') as fp:
                fp.seek(offset)
                fp.write(err_byte * val_size)

            del jdb['test']
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb1, jdb)

            # write error data to KEY header
            header = b''
            with jdb.files_obj.KEY_open('rb+') as fp:
                print(jdb.files_obj.get_folder())
                header = fp.read(512)
                self.assertGreaterEqual(len(header), 128)
                fp.seek(0)
                fp.write(err_byte * len(header))
                jdb.io.file_size = 0

            with self.assertRaises(ValueError):
                with jdb.open(read_only=True) as fp:
                    pass

            with jdb1.files_obj.KEY_open('wb') as fp:
                fp.write(header)

            self.assertEqual(len(jdb.get_all()), 0)

            with jdb.files_obj.KEY_open('wb') as fp:
                fp.write(err_byte * len(header))
                jdb.io.file_size = 0

            jdb.clear(agree='yes', wait_sec=0, data_type='J+S', api_ver=0)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.data_type, 'J+S')
            self.assertEqual(jdb.api_ver, 0)

            jdb_a = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
            jdb_b = jdb

            val_a = {'a':1, 'b':list(range(test_size)), 'c':'C', 'd':1.}
            val_b = {'b':list(range(test_size)), 'c':'C', 'e':['a']*test_size, 'f':'F'}
            ret = jdb_a.insert(val_a)
            self.assertEqual(ret, val_a)
            self.assertEqual(jdb_a, val_a)
            self.assertNotEqual(jdb_a, val_b)

            ret = jdb_b.insert(val_b) # {a, b, c, d}
            self.assertEqual(ret, val_b) # {b, c, e, f}
            self.assertEqual(jdb_b, val_b)
            self.assertNotEqual(jdb_b, val_a)

            ret = jdb_a.union(jdb_b)
            set_b = set(jdb_b)
            set_a = set(jdb_a)
            self.assertEqual(ret, {'a', 'b', 'c', 'd', 'e', 'f'})
            self.assertEqual(jdb_a + jdb_b, ret)
            self.assertEqual(jdb_a | jdb_b, ret)
            self.assertEqual(jdb_a - jdb_b, {'a', 'd'})
            self.assertEqual(jdb_a ^ jdb_b, {'a', 'd', 'e', 'f'})
            self.assertEqual(jdb_a & jdb_b, {'b', 'c'})
            self.assertEqual(jdb_a + set_b, ret)
            self.assertEqual(jdb_a | set_b, ret)
            self.assertEqual(jdb_a - set_b, {'a', 'd'})
            self.assertEqual(jdb_a ^ set_b, {'a', 'd', 'e', 'f'})
            self.assertEqual(jdb_a & set_b, {'b', 'c'})
            self.assertEqual(set_a + jdb_b, ret)
            self.assertEqual(set_a | jdb_b, ret)
            self.assertEqual(set_a - jdb_b, {'a', 'd'})
            self.assertEqual(set_a ^ jdb_b, {'a', 'd', 'e', 'f'})
            self.assertEqual(set_a & jdb_b, {'b', 'c'})
            self.assertEqual(jdb_a + jdb_b, jdb_a | jdb_b)
            self.assertEqual(jdb_a.non_joint(set_a), set())
            self.assertEqual(jdb_a.non_joint(jdb_b), {'e', 'f'})
            self.assertEqual(jdb_a.non_joint(set_b), {'e', 'f'})
            self.assertEqual(jdb_a.non_joint('e'), {'e'})
            self.assertEqual(jdb_a.non_joint('a'), set())
            self.assertEqual(jdb_a.joint(set_a), set_a)
            self.assertEqual(jdb_a.joint(jdb_b), {'b', 'c'})
            self.assertEqual(jdb_a.joint('e'), set())
            self.assertEqual(jdb_a.joint('a'), {'a'})
            self.assertEqual(jdb_a + {'a', 'f'}, {'a', 'b', 'c', 'd', 'f'})
            self.assertEqual({'a', 'f'} + jdb_a, {'a', 'b', 'c', 'd', 'f'})
            self.assertEqual(jdb_a ^ {'a', 'b', 'xx', 'yy'}, {'c', 'd', 'xx', 'yy'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} - jdb_a, {'xx', 'yy'})
            self.assertEqual(jdb_b - jdb_a, {'e', 'f'})
            self.assertEqual('a' - jdb_a, set())
            self.assertEqual('z' - jdb_a, {'z'})
            self.assertEqual('a' + jdb_a, {'a', 'b', 'c', 'd'})
            self.assertEqual('z' + jdb_a, {'a', 'b', 'c', 'd', 'z'})
            self.assertEqual('z' | jdb_a, {'a', 'b', 'c', 'd', 'z'})
            self.assertEqual('a' & jdb_a, {'a'})
            self.assertEqual('z' & jdb_a, set())
            self.assertEqual('a' ^ jdb_a, {'b', 'c', 'd'})
            self.assertEqual('z' ^ jdb_a, {'a', 'b', 'c', 'd', 'z'})
            self.assertEqual(jdb_a - 'a', {'b', 'c', 'd'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} + jdb_a, {'a', 'b', 'c', 'd', 'xx', 'yy'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} | jdb_a, {'a', 'b', 'c', 'd', 'xx', 'yy'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} & jdb_a, {'a', 'b'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} ^ jdb_a, {'c', 'd', 'xx', 'yy'})
            self.assertTrue({'a', 'b', 'c', 'd'} == jdb_a)
            self.assertTrue({'a', 'b', 'c', 'd', 'xx', 'yy'} != jdb_a)
            self.assertTrue({'a', 'b', 'c', } != jdb_a)
            self.assertTrue(jdb_a == {'a', 'b', 'c', 'd'})
            self.assertTrue(jdb_a != {'a', 'b', 'xx', 'yy'})
            self.assertTrue(jdb_a.is_subset(jdb_a))
            self.assertTrue(jdb_a.is_superset(jdb_a))
            self.assertFalse(jdb_a.is_disjoint(jdb_a))
            self.assertTrue(jdb_a.is_subset({'a', 'b', 'c', 'd', 'xx'}))
            self.assertFalse(jdb_a.is_subset({'b', 'c', 'd', 'xx'}))
            self.assertFalse(jdb_a.is_subset({'b', 'c', 'd'}))
            self.assertTrue(jdb_a.is_superset({'b', 'c', 'd'}))
            self.assertTrue(jdb_a.is_superset({'c', 'd'}))
            self.assertFalse(jdb_a.is_superset({'c', 'd', 'xx'}))
            self.assertTrue(jdb_a.is_disjoint({'xx', 'yy'}))

            self.assertEqual(jdb_a.keys + jdb_b.keys, ret)
            self.assertEqual(jdb_a.keys | jdb_b.keys, ret)
            self.assertEqual(jdb_a.keys - jdb_b.keys, {'a', 'd'})
            self.assertEqual(jdb_a.keys ^ jdb_b.keys, {'a', 'd', 'e', 'f'})
            self.assertEqual(jdb_a.keys & jdb_b.keys, {'b', 'c'})
            self.assertEqual(jdb_a.keys + set_b, ret)
            self.assertEqual(jdb_a.keys | set_b, ret)
            self.assertEqual(jdb_a.keys - set_b, {'a', 'd'})
            self.assertEqual(jdb_a.keys ^ set_b, {'a', 'd', 'e', 'f'})
            self.assertEqual(jdb_a.keys & set_b, {'b', 'c'})
            self.assertEqual(set_a + jdb_b.keys, ret)
            self.assertEqual(set_a | jdb_b.keys, ret)
            self.assertEqual(set_a - jdb_b.keys, {'a', 'd'})
            self.assertEqual(set_a ^ jdb_b.keys, {'a', 'd', 'e', 'f'})
            self.assertEqual(set_a & jdb_b.keys, {'b', 'c'})
            self.assertEqual(jdb_a.keys + jdb_b.keys, jdb_a.keys | jdb_b.keys)
            self.assertEqual(jdb_a.keys.non_joint(set_a), set())
            self.assertEqual(jdb_a.keys.non_joint(jdb_b.keys), {'e', 'f'})
            self.assertEqual(jdb_a.keys.non_joint(set_b), {'e', 'f'})
            self.assertEqual(jdb_a.keys.non_joint('e'), {'e'})
            self.assertEqual(jdb_a.keys.non_joint('a'), set())
            self.assertEqual(jdb_a.keys.joint(set_a), set_a)
            self.assertEqual(jdb_a.keys.joint(jdb_b.keys), {'b', 'c'})
            self.assertEqual(jdb_a.keys.joint('e'), set())
            self.assertEqual(jdb_a.keys.joint('a'), {'a'})
            self.assertEqual(jdb_a.keys + {'a', 'f'}, {'a', 'b', 'c', 'd', 'f'})
            self.assertEqual({'a', 'f'} + jdb_a.keys, {'a', 'b', 'c', 'd', 'f'})
            self.assertEqual(jdb_a.keys ^ {'a', 'b', 'xx', 'yy'}, {'c', 'd', 'xx', 'yy'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} - jdb_a.keys, {'xx', 'yy'})
            self.assertEqual(jdb_b.keys - jdb_a.keys, {'e', 'f'})
            self.assertEqual('a' - jdb_a.keys, set())
            self.assertEqual('z' - jdb_a.keys, {'z'})
            self.assertEqual('a' + jdb_a.keys, {'a', 'b', 'c', 'd'})
            self.assertEqual('z' + jdb_a.keys, {'a', 'b', 'c', 'd', 'z'})
            self.assertEqual('z' | jdb_a.keys, {'a', 'b', 'c', 'd', 'z'})
            self.assertEqual('a' & jdb_a.keys, {'a'})
            self.assertEqual('z' & jdb_a.keys, set())
            self.assertEqual('a' ^ jdb_a.keys, {'b', 'c', 'd'})
            self.assertEqual('z' ^ jdb_a.keys, {'a', 'b', 'c', 'd', 'z'})
            self.assertEqual(jdb_a.keys - 'a', {'b', 'c', 'd'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} + jdb_a.keys, {'a', 'b', 'c', 'd', 'xx', 'yy'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} | jdb_a.keys, {'a', 'b', 'c', 'd', 'xx', 'yy'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} & jdb_a.keys, {'a', 'b'})
            self.assertEqual({'a', 'b', 'xx', 'yy'} ^ jdb_a.keys, {'c', 'd', 'xx', 'yy'})
            self.assertTrue({'a', 'b', 'c', 'd'} == jdb_a.keys)
            self.assertTrue({'a', 'b', 'c', 'd', 'xx', 'yy'} != jdb_a.keys)
            self.assertTrue({'a', 'b', 'c', } != jdb_a.keys)
            self.assertTrue(jdb_a.keys == {'a', 'b', 'c', 'd'})
            self.assertTrue(jdb_a == jdb_a.keys)
            self.assertTrue(jdb_a != jdb_b.keys)
            self.assertTrue(jdb_a.keys == jdb_a)
            self.assertTrue(jdb_a.keys != jdb_b)
            self.assertTrue(jdb_a.keys != {'a', 'b', 'xx', 'yy'})
            self.assertTrue(jdb_a.keys.is_subset(jdb_a))
            self.assertTrue(jdb_a.keys.is_superset(jdb_a.keys))
            self.assertFalse(jdb_a.keys.is_disjoint(jdb_a.keys))
            self.assertTrue(jdb_a.keys.is_subset({'a', 'b', 'c', 'd', 'xx'}))
            self.assertFalse(jdb_a.keys.is_subset({'b', 'c', 'd', 'xx'}))
            self.assertFalse(jdb_a.keys.is_subset({'b', 'c', 'd'}))
            self.assertTrue(jdb_a.keys.is_superset({'b', 'c', 'd'}))
            self.assertTrue(jdb_a.keys.is_superset({'c', 'd'}))
            self.assertFalse(jdb_a.keys.is_superset({'c', 'd', 'xx'}))
            self.assertTrue(jdb_a.keys.is_disjoint({'xx', 'yy'}))
            ret = jdb_a.keys.union(jdb_a)
            self.assertEqual(ret, set(jdb_a.keys))
            self.assertEqual(jdb_a.keys & jdb_a.keys, ret)

            ret = jdb_a.non_joint(jdb_b)
            self.assertEqual(ret, {'e', 'f'})
            self.assertEqual(jdb_a.keys.non_joint(jdb_b.keys), ret)

            ret = jdb_a.non_joint(jdb_a)
            self.assertEqual(ret, set())
            self.assertEqual(jdb_a.keys.non_joint(jdb_a), ret)
            self.assertEqual(jdb_a - jdb_a, ret)
            self.assertEqual(jdb_a.keys - jdb_a.keys, ret)

            ret = jdb_b.non_joint(jdb_a)
            self.assertEqual(ret, {'a', 'd'})
            self.assertEqual(jdb_b.keys.non_joint(jdb_a.keys), ret)

            ret = jdb_a.difference(jdb_b)
            self.assertEqual(ret, {'a', 'd'})
            self.assertEqual(jdb_a - jdb_b, ret)
            self.assertEqual(jdb_a - set(jdb_b), ret)

            self.assertEqual(jdb_a.keys.difference(jdb_b.keys), ret)
            self.assertEqual(jdb_a.keys - jdb_b, ret)
            self.assertEqual(jdb_a.keys - set(jdb_b), ret)

            ret = jdb_a.difference(jdb_a)
            self.assertEqual(ret, set())
            self.assertEqual(jdb_a - jdb_a, ret)

            self.assertEqual(jdb_a.keys.difference(jdb_a.keys), ret)
            self.assertEqual(jdb_a - jdb_a.keys, ret)

            ret = jdb_a - jdb_a
            self.assertEqual(ret, set())
            self.assertEqual(jdb_a.keys - jdb_a.keys, ret)

            ret = set() - jdb_a
            self.assertEqual(ret, set())
            self.assertEqual(set() - jdb_a.keys, ret)

            ret = {'xx', 'yy'} - jdb_a
            self.assertEqual(ret, {'xx', 'yy'})
            self.assertEqual({'xx', 'yy'} - jdb_a.keys, ret)

            ret = jdb_a - set()
            self.assertEqual(ret, set(jdb_a))
            self.assertEqual(jdb_a.keys - set(), ret)

            ret = jdb_a.joint(jdb_b)
            self.assertEqual(ret, {'b', 'c'})
            self.assertEqual(jdb_a & jdb_b, ret)
            self.assertEqual(jdb_a.keys.joint(jdb_b), ret)
            self.assertEqual(jdb_a.keys & jdb_b.keys, ret)

            ret = jdb_a.joint(jdb_a)
            self.assertEqual(ret, set(jdb_a))
            self.assertEqual(jdb_a & jdb_a, ret)
            self.assertEqual(jdb_a.keys.joint(jdb_a), ret)
            self.assertEqual(jdb_a.keys & jdb_a.keys, ret)

            ret = jdb_a.joint({'b', 'g'})
            self.assertEqual(ret, {'b'})
            self.assertEqual(jdb_a & {'b', 'g'}, ret)
            self.assertEqual(jdb_a.keys.joint({'b', 'g'}), ret)
            self.assertEqual(jdb_a.keys & {'b', 'g'}, ret)

            ret = jdb_b.intersection(jdb_a)
            self.assertEqual(ret, {'b', 'c'})
            self.assertEqual(jdb_b.keys.intersection(jdb_a.keys), ret)

            ret = {'b', 'c', 'xx'} & jdb_a
            self.assertEqual(ret, {'b', 'c'})
            self.assertEqual({'b', 'c', 'xx'} & jdb_a.keys, ret)

            ret = jdb_a & {'b', 'c', 'xx'}
            self.assertEqual(ret, {'b', 'c'})
            self.assertEqual(jdb_a.keys & {'b', 'c', 'xx'}, ret)

            ret = jdb_a.intersection({'c', 'g'})
            self.assertEqual(ret, {'c'})
            self.assertEqual(jdb_a & {'c', 'g'}, ret)
            self.assertEqual(jdb_a.keys.intersection({'c', 'g'}), ret)
            self.assertEqual(jdb_a.keys & {'c', 'g'}, ret)

            ret = jdb_a.intersection(jdb_a)
            self.assertEqual(ret, set(jdb_a))
            self.assertEqual(jdb_a & jdb_a, ret)
            self.assertEqual(jdb_a.keys & jdb_a.keys, ret)

            ret = jdb_b.non_intersection(jdb_a)
            self.assertEqual(ret, {'a', 'd', 'e', 'f'})
            self.assertEqual(jdb_b ^ jdb_a, ret)
            self.assertEqual(jdb_a ^ jdb_b, ret)
            self.assertEqual(jdb_b.keys.non_intersection(jdb_a.keys), ret)
            self.assertEqual(jdb_b.keys ^ jdb_a.keys, ret)
            self.assertEqual(jdb_a.keys ^ jdb_b.keys, ret)

            ret = jdb_a.non_intersection({'c', 'g'})
            self.assertEqual(ret, {'a', 'b', 'd', 'g'})
            self.assertEqual(jdb_a ^ {'c', 'g'}, ret)
            self.assertEqual(jdb_a.keys.non_intersection({'c', 'g'}), ret)
            self.assertEqual(jdb_a.keys ^ {'c', 'g'}, ret)

            ret = jdb_a.non_intersection(jdb_a)
            self.assertEqual(ret, set())
            self.assertEqual(jdb_a ^ jdb_a, ret)
            self.assertEqual(jdb_a.keys.non_intersection(jdb_a), ret)
            self.assertEqual(jdb_a.keys ^ jdb_a, ret)
            self.assertEqual(jdb_a.keys ^ jdb_a.keys, ret)

    def test_process(self):
        def _chg_func(jdb, key, val, wait1, wait2):
            with jdb.open(read_only=True) as fp:
                time.sleep(wait1)
                jdb.f_write(fp, key, val)
                time.sleep(wait2)

        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            current_state = random.getstate()
            test_size = 100
            expect = {f'k{v}' : 'v'+str(v) for v in range(test_size)}
            expect2 = {f'a{v}' : 'v'+str(v)+'100' for v in range(test_size)}

            jdb0 = JDb(jdb)
            jdb1 = JDb(jdb, key_limit=0)
            jdb2 = JDb(jdb, key_limit=0)

            jdb1.key_limit = 'l2'
            jdb2.key_limit = 'bt'

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)

            for ii,kk in enumerate(expect):
                if (ii % 3) == 0:
                    jdb[kk] = expect[kk]
                    self.assertEqual(jdb.n_records, ii+1)
                elif (ii % 3) == 1:
                    jdb1[kk] = expect[kk]
                    self.assertEqual(jdb1.n_records, ii+1)
                elif (ii % 3) == 2:
                    jdb2[kk] = expect[kk]
                    self.assertEqual(jdb2.n_records, ii+1)

            self.assertEqual(jdb, expect)
            self.assertEqual(jdb1, expect)
            self.assertEqual(jdb2, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[:], jdb2.keys[:])
            self.assertEqual(jdb1.keys[:], jdb2.keys[:])

            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.keys[0.:], jdb2.keys[0.:])
            self.assertEqual(jdb1.keys[0.:], jdb2.keys[0.:])
            for ii,kk in enumerate(expect):
                if (ii % 3) == 0:
                    jdb[kk] = 'a' * min_value_size * 8
                    self.assertEqual(jdb.n_records, len(expect))
                elif (ii % 3) == 1:
                    jdb1[kk] = 'b' * min_value_size * 16
                    self.assertEqual(jdb1.n_records, len(expect))
                elif (ii % 3) == 2:
                    jdb2[kk] = 'c' * min_value_size * 32
                    self.assertEqual(jdb2.n_records, len(expect))

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[:], jdb2.keys[:])
            self.assertEqual(jdb1.keys[:], jdb2.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.keys[0.:], jdb2.keys[0.:])
            self.assertEqual(jdb1.keys[0.:], jdb2.keys[0.:])

            for ii,kk in enumerate(expect):
                if (ii % 3) == 0:
                    del jdb[kk]
                    self.assertEqual(jdb.n_records, len(expect)-ii-1)
                elif (ii % 3) == 1:
                    del jdb1[kk]
                    self.assertEqual(jdb1.n_records, len(expect)-ii-1)
                elif (ii % 3) == 2:
                    del jdb2[kk]
                    self.assertEqual(jdb2.n_records, len(expect)-ii-1)

            self.assertEqual(len(jdb), 0)
            self.assertEqual(len(jdb1), 0)
            self.assertEqual(len(jdb2), 0)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[:], jdb2.keys[:])
            self.assertEqual(jdb1.keys[:], jdb2.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.keys[0.:], jdb2.keys[0.:])
            self.assertEqual(jdb1.keys[0.:], jdb2.keys[0.:])

            for ii, kk in enumerate(expect):
                if (ii % 3) == 0:
                    ret = jdb.unremove(kk)
                    self.assertIn(kk, ret)
                    self.assertEqual(jdb.n_records, ii+1)
                elif (ii % 3) == 1:
                    ret = jdb1.unremove(kk)
                    self.assertIn(kk, ret)
                    self.assertEqual(jdb1.n_records, ii+1)
                elif (ii % 3) == 2:
                    ret = jdb2.unremove(kk)
                    self.assertIn(kk, ret)
                    self.assertEqual(jdb2.n_records, ii+1)

            self.assertEqual(set(jdb), set(expect))
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[:], jdb2.keys[:])
            self.assertEqual(jdb1.keys[:], jdb2.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.keys[0.:], jdb2.keys[0.:])
            self.assertEqual(jdb1.keys[0.:], jdb2.keys[0.:])

            for ii, (kk1, kk2) in enumerate(zip(expect, expect2)):
                if (ii % 3) == 0:
                    jdb.remove(kk1)
                    jdb[kk2] = expect2[kk2]
                elif (ii % 3) == 1:
                    jdb1.remove(kk1)
                    jdb1[kk2] = expect2[kk2]
                elif (ii % 3) == 2:
                    jdb2.remove(kk1)
                    jdb2[kk2] = expect2[kk2]

            self.assertEqual(jdb, expect2)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[:], jdb2.keys[:])
            self.assertEqual(jdb1.keys[:], jdb2.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.keys[0.:], jdb2.keys[0.:])
            self.assertEqual(jdb1.keys[0.:], jdb2.keys[0.:])

            list1 = list(expect)
            list2 = list(expect2)
            random.shuffle(list1)
            random.shuffle(list2)
            for ii, (kk1, kk2) in enumerate(zip(list2, list1)):
                if (ii % 3) == 0:
                    jdb[kk2] = expect[kk2]
                    jdb.remove(kk1)
                elif (ii % 3) == 1:
                    jdb1[kk2] = expect[kk2]
                    jdb1.remove(kk1)
                elif (ii % 3) == 2:
                    jdb2[kk2] = expect[kk2]
                    jdb2.remove(kk1)

            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[:], jdb2.keys[:])
            self.assertEqual(jdb1.keys[:], jdb2.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.keys[0.:], jdb2.keys[0.:])
            self.assertEqual(jdb1.keys[0.:], jdb2.keys[0.:])

            self.assertEqual(jdb, jdb0)
            self.assertEqual(jdb.keys[:], jdb0.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb0.keys[0.:])
            self.assertEqual(jdb.sync_id, jdb0.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb} {current_state}', red=1))

            jdb.insert('A', '999')
            jdb1.remove('A')
            jdb1.insert('B', '888')
            self.assertTrue('B' in jdb)
            self.assertTrue('B' in jdb1)
            self.assertTrue('A' not in jdb)
            self.assertTrue('A' not in jdb1)
            jdb1.remove('B')
            self.assertTrue('B' not in jdb)
            self.assertTrue('B' not in jdb2)

            jdb.insert('A', '100')
            jdb1.remove('A')
            jdb2.insert('B', '200')
            self.assertTrue('B' in jdb)
            self.assertTrue('B' in jdb1)
            self.assertTrue('A' not in jdb)
            self.assertTrue('A' not in jdb1)
            self.assertTrue('A' not in jdb2)

            jdb1.remove('B')
            jdb.insert('A', '300')
            jdb1.remove('A')
            jdb1.insert('B', '400')
            jdb1.insert('C', '500')
            jdb2.insert('D', '600')
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)

            self.assertTrue('B' in jdb)
            self.assertTrue('C' in jdb)
            self.assertTrue('D' in jdb)
            self.assertTrue('B' in jdb2)
            self.assertTrue('C' in jdb2)
            self.assertTrue('A' not in jdb)
            self.assertTrue('A' not in jdb1)
            self.assertTrue('A' not in jdb2)
            self.assertTrue('D' in jdb1)

            jdb['D'] = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' * min_value_size
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(dict(jdb.key_table), dict(jdb1.key_table))
            self.assertEqual(dict(jdb.key_table), dict(jdb2.key_table))
            self.assertEqual(dict(jdb1.key_table), dict(jdb2.key_table))
            self.assertEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            jdb['C'] = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' * min_value_size * 2
            del jdb['C']

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(dict(jdb.key_table), dict(jdb1.key_table))
            self.assertEqual(dict(jdb.key_table), dict(jdb2.key_table))
            self.assertEqual(dict(jdb1.key_table), dict(jdb2.key_table))
            self.assertEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb.sync_id, jdb2.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb} {current_state}', red=1))

            id_list = []
            for i in range(32):
                jdb.insert(f'A{i}', str(i))
                id_list.append(i)

            random.shuffle(id_list)
            for i in id_list:
                jdb1.remove(f'A{i}', str(i))
                jdb2.insert(f'B{i}', str(-i))
                self.assertTrue(f'B{i}' in jdb1)
                self.assertTrue(f'A{i}' not in jdb2)

            self.assertTrue('B1' in jdb)
            self.assertTrue('B1' in jdb1)
            self.assertTrue('A1' not in jdb)
            self.assertTrue('A1' not in jdb2)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)

            for i in range(32):
                del jdb[f'B{i}']
            self.assertEqual(jdb, jdb1)

            jdb.insert(['a','b','c', 'd', 'e'], 1)
            jdb.remove('d', 'e')
            self.assertEqual(jdb, jdb1)

            jdb['a'] = 2
            self.assertEqual(jdb, jdb1)

            jdb.remove(['d', 'e', 'f'])
            jdb.recycle(merge=True)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb} {current_state}', red=1))

            self.assertEqual(jdb, jdb1)
            jdb.insert(['d', 'e'], 3)
            jdb.remove(['c', 'd', 'e'])
            self.assertEqual(jdb, jdb1)

            jdb.revert(['c', 'd', 'e'])
            jdb.replace({'a': 11, 'b' : 12})
            self.assertEqual(jdb, jdb1)

            last = jdb[:]
            with jdb1.open() as fp:
                jdb1.f_write(fp, 'a', [11] * 10)
                jdb1.f_delete(fp, 'b')
                jdb1.f_undelete(fp, 'b')
                jdb1.f_unwrite(fp, 'a')

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, last)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb} {current_state}', red=1))

            n_lines = jdb.n_lines
            with jdb.open() as fp:
                for v in range(100):
                    jdb.f_write(fp, 'a', v)
                    jdb.f_write(fp, 'a', [v]*10)
                    jdb.f_write(fp, 'a', [v]*20)

                jdb.f_unwrite(fp, 'a')

            self.assertEqual(jdb, last)
            self.assertEqual(jdb, jdb1)
            self.assertLess(jdb.n_lines, n_lines+100)

            sync_id = jdb.sync_id
            th0 = threading.Thread(target=_chg_func, args=(jdb0, 'NEW_VAL', list(range(4)), 0.01, 0.02))
            th0.start()

            th1 = threading.Thread(target=_chg_func, args=(jdb1, 'NEW_VAL', list(range(8)), 0.02, 0.01))
            th1.start()

            th2 = threading.Thread(target=_chg_func, args=(jdb2, 'NEW_VAL', list(range(16)), 0.03, 0.))
            th2.start()

            th0.join()
            th1.join()
            with jdb.open() as fp:
                time.sleep(0.03)
                jdb.f_write(fp, 'NEW_VAL', list(range(32)))

            th2.join()

            self.assertEqual(jdb, jdb0)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(sync_id+4, jdb.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error, Style(f'{filename}:{jdb} {current_state}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_thread(self):
        def _chg_func(jdb, tasks):
            for kk,vv in tasks:
                jdb[kk] = vv + '100'

        def _add_func(jdb, tasks):
            for kk,vv in tasks:
                jdb[kk] = vv

        def _del_func(_id, jdb, tasks):
            for _step,(kk,_vv) in enumerate(tasks):
                with jdb.open(read_only=False) as fp:
                    row = jdb.key_table.get(kk, -1)
                    if row >= 0:
                        _val = jdb.f_delete(fp, kk, row=row)
                    else:
                        _val = None

        def _undel_func(jdb, tasks):
            for kk,_vv in tasks:
                jdb.unremove(kk)

        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            test_size = 40
            with jdb.open(read_only=False):
                jdb.io.sync_id = 0X_7FF_0000_0000
                jdb.io.swap_id = 0X_7FF_0000_0000
                jdb.io.remv_id = 0X_7FF_0000_0000

            jdb0 = JDb(jdb, key_limit='bt', cache_limit=10)
            jdb1 = JDb(jdb, key_limit='l2', cache_limit=-1)
            jdb2 = JDb(jdb, key_limit=8)

            expect = {f'k{v}' : 'v'+str(v) for v in range(test_size)}
            tasks = [[], [], []]
            for kk,vv in expect.items():
                tasks[random.randint(0,2)].append((kk,vv))

            th_list = [
                threading.Thread(target=_add_func, args=(jdb0, tasks[0])),
                threading.Thread(target=_add_func, args=(jdb1, tasks[1])),
                threading.Thread(target=_add_func, args=(jdb2, tasks[2]))
            ]

            for th in th_list:
                th.start()

            for th in th_list:
                th.join()

            self.assertEqual(jdb0, expect, Style(f'{filename}:{jdb}', red=1))
            self.assertEqual(jdb1, jdb0)
            self.assertEqual(jdb2, jdb0)

            tasks = [[], [], []]
            for kk,vv in expect.items():
                tasks[random.randint(0,2)].append((kk,vv))


            th_list = [
                threading.Thread(target=_del_func, args=(0, jdb0, tasks[0])),
                threading.Thread(target=_del_func, args=(1, jdb1, tasks[1])),
                threading.Thread(target=_del_func, args=(2, jdb2, tasks[2]))
            ]

            for th in th_list:
                th.start()

            for th in th_list:
                th.join()

            self.assertNotEqual(jdb0, expect)
            self.assertTrue(not jdb0)
            self.assertEqual(jdb1, jdb0)
            self.assertEqual(jdb2, jdb0)

            tasks = [[], [], []]
            for kk,vv in expect.items():
                tasks[random.randint(0,2)].append((kk,vv))


            th_list = [
                threading.Thread(target=_undel_func, args=(jdb0, tasks[0])),
                threading.Thread(target=_undel_func, args=(jdb1, tasks[1])),
                threading.Thread(target=_undel_func, args=(jdb2, tasks[2]))
            ]

            for th in th_list:
                th.start()

            for th in th_list:
                th.join()

            self.assertEqual(jdb0, expect)
            self.assertEqual(jdb1, jdb0)
            self.assertEqual(jdb2, jdb0)


            tasks = [[], [], []]
            for kk,vv in expect.items():
                tasks[random.randint(0,2)].append((kk,vv))

            th_list = [
                threading.Thread(target=_chg_func, args=(jdb0, tasks[0])),
                threading.Thread(target=_chg_func, args=(jdb1, tasks[1])),
                threading.Thread(target=_chg_func, args=(jdb2, tasks[2]))
            ]

            for th in th_list:
                th.start()

            for th in th_list:
                th.join()

            self.assertNotEqual(jdb0, expect)
            self.assertEqual(jdb0, {k:v+'100' for k,v in expect.items()})
            self.assertEqual(jdb1, jdb0)
            self.assertEqual(jdb2, jdb0)

            error = jdb0.check_error()
            self.assertTrue(not error)
            error = jdb1.check_error()
            self.assertTrue(not error)
            error = jdb2.check_error()
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_random(self):
        def _worker(worker, _filename, op, key_id, n_keys, step, _id, _ll):
            if _ll >= 14:
                new_val = [f'#{step}|{hex(id(worker.io))[-5:-1]}|k{key_id}+{n_keys}|{op}+{_ll}'] + [op] * _ll
            else:
                new_val = str(op) * _ll

            keys = [f'k{key_id+vv}' for vv in range(n_keys)]

            if op == 0:
                worker.update(keys, new_val)

            elif op == 1:
                worker.remove(keys)

            elif op == 2:
                worker.revert(keys)

            elif op == 3:
                with worker.open() as fp:
                    jio, fp, _key_fp = worker.f_get_fp(fp)
                    key_table = jio.key_table
                    for key in keys:
                        try:
                            if key not in key_table:
                                worker.f_undelete(fp, key)
                                worker.f_write(fp, key, new_val)
                                worker.f_unwrite(fp, key)
                                worker.f_delete(fp, key, flags=JFlag.SPLIT)
                            else:
                                old_val = worker.f_read(fp, key)
                                worker.f_write(fp, key, new_val)
                                worker.f_delete(fp, key)
                                worker.f_undelete(fp, key)
                                worker.f_unwrite(fp, key)
                                worker.f_write(fp, key, old_val, flags=JFlag.REVERT | JFlag.SPLIT)
                        except KeyError:
                            pass

            elif op == 4:
                with worker.open() as fp:
                    jio, fp, _key_fp = worker.f_get_fp(fp)
                    key_table = jio.key_table
                    for key in keys:
                        try:
                            if key not in key_table:
                                worker.f_undelete(fp, key)
                                worker.f_write(fp, key, new_val)
                                worker.f_unwrite(fp, key)
                                worker.f_delete(fp, key, flags=0)
                            else:
                                old_val = worker.f_read(fp, key)
                                worker.f_write(fp, key, new_val)
                                worker.f_delete(fp, key)
                                worker.f_undelete(fp, key)
                                worker.f_unwrite(fp, key)
                                worker.f_write(fp, key, old_val)
                        except KeyError:
                            pass

                    for key in [f'n{key_id+vv}' for vv in range(n_keys)]:
                        try:
                            if key in key_table:
                                worker.f_delete(fp, key)
                            else:
                                worker.f_write(fp, key, new_val)
                        except KeyError:
                            pass

            elif op == 5:
                with worker.open() as fp:
                    jio, fp, _key_fp = worker.f_get_fp(fp)
                    key_table = jio.key_table
                    for old_key in keys:
                        try:
                            new_key = f'n{old_key[1:]}'
                            if new_key in key_table:
                                if old_key in key_table:
                                    worker.f_unwrite(fp, old_key)
                                else:
                                    worker.f_undelete(fp, old_key)

                                worker.f_unwrite(fp, new_key)

                            else:
                                if old_key in key_table:
                                    worker.f_write(fp, old_key, new_val)
                                else:
                                    worker.f_undelete(fp, old_key)

                                worker.f_write(fp, new_key, new_val)
                        except KeyError:
                            pass

            else:
                with worker.open() as fp:
                    jio, fp, _key_fp = worker.f_get_fp(fp)
                    key_table = jio.key_table
                    for old_key in keys:
                        try:
                            new_key = f'n{old_key[1:]}'
                            if new_key in key_table:
                                if old_key in key_table:
                                    worker.f_delete(fp, old_key)
                                else:
                                    worker.f_write(fp, old_key, new_val)

                                worker.f_delete(fp, new_key, flags=JFlag.REVERT)

                            else:
                                if old_key in key_table:
                                    worker.f_delete(fp, old_key)
                                else:
                                    worker.f_write(fp, old_key, new_val)

                                worker.f_undelete(fp, new_key, flags=JFlag.SPLIT)
                        except KeyError:
                            pass

        csize = len(self.jdb_configs)
        for cid,config in enumerate(self.jdb_configs):
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            jdb.sync()
            test_size = 16
            step_size = test_size * 2
            name = filename.replace('.jdb', '').replace('db/', '')

            print(Style(f'{cid+1}/{csize}|Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit} #{test_size}/{step_size}', yellow=1, bright=1))
            # --------------------------------------------
            jdb_list = [jdb,
                        JDb(jdb, key_limit='l4', cache_limit=0),
                        JDb(jdb, key_limit='bt', cache_limit=32),
                        JDb(jdb, key_limit='<9', cache_limit=-1)]

            expect = {f'k{v}' : [v%10] * (test_size + 1) for v in range(test_size)}
            jmem = JDb()
            jmem['main'] = jdb
            self.assertTrue(jmem.get_group('main') is jdb)

            jdb.insert(expect)
            self.assertEqual(jdb, expect)

            for ii,_jdb in enumerate(jdb_list):
                self.assertEqual(_jdb, expect)
                self.assertEqual(set(_jdb.key_table), set(expect))
                self.assertEqual(jdb, _jdb)
                self.assertEqual(jdb.get_all(), _jdb.get_all())
                self.assertEqual(jdb.sync_id, _jdb.sync_id)
                self.assertEqual(jdb.key_table, _jdb.key_table)

            steps = [(ii,random.randint(1,8),random.randint(0,len(jdb_list)-1),random.randint(0,6),random.randint(1, 32),random.randint(0,99)) for ii in range(step_size)]
            random.shuffle(steps)
            th_list = [None] * len(jdb_list)
            for ii,(key_id,n_keys,_id,op,_ll,th_id) in enumerate(steps):
                step = ii + 1
                _jdb = jdb_list[_id]
                key_id %= test_size
                if th_id >= 50:
                    while True:
                        old_th = th_list[_id]
                        if not old_th:
                            break

                        if old_th.is_alive():
                            _id = (_id + 1) % len(jdb_list)
                            time.sleep(0)
                            continue

                        old_th.join()
                        th_list[_id] = None
                        break

                    th = threading.Thread(target=_worker, args=(_jdb, name, op, key_id, n_keys, step, _id, _ll))
                    th_list[_id] = th
                    th.start()
                else:
                    _worker(_jdb, name, op, key_id, n_keys, step, _id, _ll)

            for th in th_list:
                if not th:
                    continue
                th.join()

            jmem.sync(force=True)
            jdb.sync()
            for _jdb in jdb_list:
                if id(_jdb) == id(jdb):
                    continue

                _jdb.unsync()
                error = _jdb.check_error()
                self.assertTrue(not error, Style(f'{filename}:{jdb} - {_jdb}', red=1))
                self.assertEqual(jdb, _jdb)
                self.assertEqual(jdb.get_all(), _jdb.get_all())
                self.assertEqual(jdb.sync_id, _jdb.sync_id)
                self.assertEqual(jdb.key_table, _jdb.key_table)

            jmem.unsync(with_group=True)
            error = jmem.check_error(level=2)
            self.assertTrue(not error, Style(f'{filename}:{jdb}', red=1))

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

if __name__ == '__main__':
    print(Style('JDb Unit Testing ...', blink=1, cyan=1))
    unittest.main(verbosity=2)

#
