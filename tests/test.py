# pylint: disable=too-many-lines, multiple-imports
import unittest, time, random, threading, inspect, re, os, io
import datetime as dt
import sqlite3
from omni_json_db import JDb, JDbReader, JMemFiles, JFlag, JNetFiles, JDiskFiles, run_files_server, loads, dumps

_g_basetime = time.perf_counter()
def Style(msg, bold=None, dim=None, smso=None, underscore=None, blink=None, reverse=None, hidden=None, bright=None, fg=None, black=None, red=None, green=None, yellow=None, blue=None, magenta=None, cyan=None, white=None, bg=None, bg_black=None, bg_red=None, bg_green=None, bg_yellow=None, bg_blue=None, bg_magenta=None, bg_cyan=None, bg_white=None):
    if not '_g_basetime'  in globals():
        globals()['_g_basetime'] = time.perf_counter()

    code = ''
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

    msg = f'{tt:08.3f}|{fm.f_code.co_name}:{fm.f_lineno}|{msg}'
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

class TestJDb(unittest.TestCase):
    def setUp(self):
        self.server1 = run_files_server('127.0.0.1', 59898, files='db/test_3n.jdb', verbose=0)
        self.server2 = run_files_server('127.0.0.1', 59899, files=None, verbose=0)

        self.jdb_configs = [
            {'KEY_file':'net_59898_3',      'api_ver':1, 'data_type':'J+J', 'zip_type':'--', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 16, 'min_value_size': 8, 'index_size':64, 'key_limit':'l4'},
            {'KEY_file':'net_59899_6',      'api_ver':1, 'data_type':'S+S', 'zip_type':'--', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 16, 'min_value_size': 8, 'index_size':64, 'key_limit':'bt'},

            {'KEY_file':'mem_3br_v0',       'api_ver':0, 'data_type':'J+J', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': -1, 'min_value_size': 8, 'index_size':64, 'key_limit':'bt'},

            {'KEY_file':'mem_3lz',          'api_ver':1, 'data_type':'J+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'mem_6z1',          'api_ver':1, 'data_type':'S+S', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
                # {'KEY_file':'mem_7lz',          'api_ver':1, 'data_type':'J+S', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},

            {'KEY_file':'db/test_1lz_v0.jdb', 'api_ver':0, 'data_type':'L+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'no'},
            {'KEY_file':'db/test_2br_v0.jdb', 'api_ver':0, 'data_type':'M+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'l3'},
            {'KEY_file':'db/test_5z1_v0.jdb', 'api_ver':0, 'data_type':'J+P', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'l4'},
            {'KEY_file':'db/test_6lz_v0.jdb', 'api_ver':0, 'data_type':'S+S', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'l5'},
                # {'KEY_file':'db/test_7z2_v0.jdb', 'api_ver':0, 'data_type':'J+S', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size':8, 'index_size':64, 'key_limit':'bt'},

            {'KEY_file':'db/test_1.jdb',    'api_ver':1, 'data_type':'L+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
            {'KEY_file':'db/test_1gz.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
            {'KEY_file':'db/test_1bz.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1xz.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1zs.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1br.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1z1.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1z2.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_1lz.jdb',  'api_ver':1, 'data_type':'L+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x1.jdb',   'api_ver':1, 'data_type':'L+J', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l0'},
            {'KEY_file':'db/test_x1gz.jdb', 'api_ver':1, 'data_type':'L+J', 'zip_type':'gz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':0},

            {'KEY_file':'db/test_2.jdb',    'api_ver':1, 'data_type':'M+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2gz.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2bz.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
            {'KEY_file':'db/test_2xz.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
            {'KEY_file':'db/test_2zs.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2br.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2z1.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2z2.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':0},
                # {'KEY_file':'db/test_2lz.jdb',  'api_ver':1, 'data_type':'M+M', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x2.jdb',   'api_ver':1, 'data_type':'M+M', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l1'},
            {'KEY_file':'db/test_x2bz.jdb', 'api_ver':1, 'data_type':'M+M', 'zip_type':'bz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':0},

            {'KEY_file':'db/test_3.jdb',    'api_ver':1, 'data_type':'J+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3gz.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3bz.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3xz.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3zs.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3br.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3z1.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3z2.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_3lz.jdb',  'api_ver':1, 'data_type':'J+J', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x3.jdb',   'api_ver':1, 'data_type':'J+J', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l2'},
            {'KEY_file':'db/test_x3xz.jdb', 'api_ver':1, 'data_type':'J+J', 'zip_type':'xz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

            {'KEY_file':'db/test_4.jdb',    'api_ver':1, 'data_type':'J+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4gz.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4bz.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4xz.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4zs.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_4br.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_4z1.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4z2.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_4lz.jdb',  'api_ver':1, 'data_type':'J+M', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x4.jdb',   'api_ver':1, 'data_type':'J+M', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l3'},
            {'KEY_file':'db/test_x4z1.jdb', 'api_ver':1, 'data_type':'J+M', 'zip_type':'z1', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

            {'KEY_file':'db/test_5.jdb',    'api_ver':1, 'data_type':'J+P', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5gz.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5bz.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5xz.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5zs.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5br.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
                # {'KEY_file':'db/test_5z1.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_5z2.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_5lz.jdb',  'api_ver':1, 'data_type':'J+P', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x5.jdb',   'api_ver':1, 'data_type':'J+P', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l4'},
            {'KEY_file':'db/test_x5br.jdb', 'api_ver':1, 'data_type':'J+P', 'zip_type':'br', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

            {'KEY_file':'db/test_6.jdb',    'api_ver':1, 'data_type':'S+S', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6gz.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6bz.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6xz.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6zs.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6br.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6z1.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6z2.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_6lz.jdb',  'api_ver':1, 'data_type':'S+S', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'-'},
            {'KEY_file':'db/test_x6.jdb',   'api_ver':1, 'data_type':'S+S', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'l5'},
            {'KEY_file':'db/test_x6z2.jdb', 'api_ver':1, 'data_type':'S+S', 'zip_type':'z2', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'-'},

            {'KEY_file':'db/test_7.jdb',    'api_ver':1, 'data_type':'J+S', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7gz.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'gz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7bz.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'bz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7xz.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'xz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7zs.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'zs', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
            {'KEY_file':'db/test_7br.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'br', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'no'},
                # {'KEY_file':'db/test_7z1.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'z1', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
                # {'KEY_file':'db/test_7z2.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'z2', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_7lz.jdb',  'api_ver':1, 'data_type':'J+S', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x7.jdb',   'api_ver':1, 'data_type':'J+S', 'zip_type':'no', 'max_file_size' : 32 * 100, 'reserved_rate': 0.1, 'cache_limit': 2, 'min_value_size':  2, 'index_size': 64, 'key_limit':'bt'},
            {'KEY_file':'db/test_x7lz.jdb', 'api_ver':1, 'data_type':'J+S', 'zip_type':'lz', 'max_file_size' :     None, 'reserved_rate': 0.0, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'--'},

            {'KEY_file':'db/test_8.jdb',    'api_ver':1, 'data_type':'S+M', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x8gz.jdb', 'api_ver':1, 'data_type':'S+M', 'zip_type':'gz', 'max_file_size' :     None, 'reserved_rate': 0.2, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'l5'},

            {'KEY_file':'db/test_9.jdb',    'api_ver':1, 'data_type':'S+J', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x9z1.jdb', 'api_ver':1, 'data_type':'S+J', 'zip_type':'z1', 'max_file_size' :     None, 'reserved_rate': 0.2, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'bt'},

            {'KEY_file':'db/test_10.jdb',    'api_ver':1, 'data_type':'S+P', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_x10lz.jdb', 'api_ver':1, 'data_type':'S+P', 'zip_type':'lz', 'max_file_size' :     None, 'reserved_rate': 0.2, 'cache_limit':-1, 'min_value_size':128, 'index_size':128, 'key_limit':'<4'},

            {'KEY_file':'db/test_11.jdb',    'api_ver':1, 'data_type':'J+Y', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_11lz.jdb',  'api_ver':1, 'data_type':'J+Y', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'bt'},

            {'KEY_file':'db/test_12.jdb',    'api_ver':1, 'data_type':'S+Y', 'zip_type':'no', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'--'},
            {'KEY_file':'db/test_12lz.jdb',  'api_ver':1, 'data_type':'S+Y', 'zip_type':'lz', 'max_file_size' : 64 * 100, 'reserved_rate':None, 'cache_limit': 0, 'min_value_size': 16, 'index_size':256, 'key_limit':'l4'},
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
        for config in self.jdb_configs:
            filename = config['KEY_file']
            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.remove_fast(jdb)
            self.assertTrue(len(jdb) == 0)
            if jdb.n_lines > 0:
                jdb.recycle(level=4, merge=False, verbose=False)
                if jdb.n_lines == 0:
                    self.assertFalse(jdb.file_table)
                    self.assertTrue(jdb.n_lines == jdb.n_records == 0)

            print(Style(f'Down {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}%', blue=1))

        for server in (self.server1, self.server2):
            if not server: continue
            server.shutdown()
            server.server_close()

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
            jmem = JDb()
            jmem['group'] = jdb1 = JDb(jdb)
            jmem.clear(agree='yes', wait_sec=0)

            jdb.from_ini(io.StringIO(ini_data))
            self.assertEqual(set(jdb), {'server/host', 'server/port'})
            self.assertEqual(jdb['server/port'], '8080')

            jdb.from_toml(io.StringIO(toml_data))
            total = len(jdb)
            self.assertEqual(total, 5)
            self.assertEqual(jdb - {'server/host', 'server/port'}, {'/app_name', 'network/ip', 'network/port'})
            self.assertEqual(jdb['network/port'], 8181)

            if not isinstance(jdb.files_obj, JNetFiles):
                # JNetFiles does not support group
                jdb.from_sqlite(db_path)
                project_jdb = jdb.get_group('projects')
                log_jdb = jdb.get_group('project_logs')
                self.assertEqual(project_jdb, jdb['projects'])
                self.assertEqual(log_jdb, jdb['project_logs'])
                self.assertEqual(len(log_jdb), 4)
                self.assertEqual(len(project_jdb), 3)
                self.assertEqual(project_jdb[3]['name'], 'coding')
                self.assertEqual(project_jdb[3]['name'], 'coding')
                logs = log_jdb.find(FUNC=lambda v:v.get('project_id') == 3)
                self.assertEqual([log for _id,log in logs.items()], [{'project_id': 3, 'action': 'setup environment', 'log_date': '2024-01-01'}])

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

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
            # Sample user records
            users = {
               'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
               'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
               'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
               'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
            }
            # Insert data
            jdb += users
            self.assertTrue(jdb == users)

            # 1. Exact Match & Global Search (ANY, RE, RE2)
            #----------------------------------------------------------
            # Find users where any attribute exactly matches 'Alice'
            res = jdb.find(ANY='Alice')
            self.assertTrue(set(res) == {'user_1'})

            # RE/RE2 convert value into JSON string format for searching.
            # Find any record that has the string 'designer' inside it
            res = jdb.find(RE=r'designer')
            self.assertTrue(set(res) == {'user_4'})

            # RE2 remove some JSON symbol ([]{}") before searching (not RE)
            res = jdb.find(RE2=r'role:designer')
            self.assertTrue(set(res) == {'user_4'})

            res = jdb.find(RE=r'role:designer')
            self.assertTrue(set(res) == set())

            # 2. Relational & Conditional Operators (vals)
            #----------------------------------------------------------
            # Age is greater than or equal to 30
            res = jdb.find(vals={'age': {'$ge': 30}})
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            res = jdb.find(ANY={'$ge': 30})
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            # Age is strictly less than 30
            res = jdb.find(vals={'age': {'$lt': 30}})
            self.assertTrue(set(res) == {'user_2', 'user_4'})

            res = jdb.find(ANY={'$lt': 30})
            self.assertTrue(set(res) == {'user_2', 'user_4'})

            # Role is either 'admin' or 'designer'
            res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
            self.assertTrue(set(res) == {'user_1', 'user_4'})

            res = jdb.find(ANY={'$in': ['admin', 'designer']})
            self.assertTrue(set(res) == {'user_1', 'user_4'})

            # tags contains 'python'
            res = jdb.find(vals={'tags': {'$has': 'python'}})
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            res = jdb.find(ANY={'$has': 'python'})
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            # Age is NOT 30
            res = jdb.find(vals={'age': {'$ne': 30}})
            self.assertTrue(set(res) == {'user_2', 'user_3', 'user_4'})

            res = jdb.find(ANY={'$ne': 30})
            self.assertTrue(set(res) == {'user_2', 'user_3', 'user_4'})

            # Age is 28
            res = jdb.find(vals={'age': {'$eq': 28}})
            self.assertTrue(set(res) == {'user_4'})

            res = jdb.find(ANY={'$eq': 28})
            self.assertTrue(set(res) == {'user_4'})

            # 3. Logical Grouping (AND, OR, NOT)
            #----------------------------------------------------------
            # Age >= 25 AND Age <= 30
            res = jdb.find(AND=[{'age': {'$ge': 25}}, {'age': {'$le': 30}}])
            self.assertTrue(set(res) == {'user_1', 'user_2', 'user_4'})

            # Role is 'admin' OR Age > 30
            res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            # User is NOT a developer
            res = jdb.find(NOT={'role': 'developer'})
            self.assertTrue(set(res) == {'user_1', 'user_4'})

            # (Role is 'admin' OR Age > 30) AND 'linux' not in tags
            res = jdb.find(AND=[
               {'$or': [
                  {'role': 'admin'},
                  {'age': {'$gt': 30}}
               ]},
               {'$not': {'tags': {'$has': 'linux'}}}
            ])
            self.assertTrue(set(res) == {'user_1'})

            # 4. Regular Expressions (RE, RE2, re.compile)
            #----------------------------------------------------------
            # Values matching an email domain regex
            res = jdb.find(vals={'email': r'.@example.com'})
            self.assertTrue(set(res) == {'user_1'})

            # Find users where any attribute exactly matches regex
            res = jdb.find(ANY=r'.@example.com')
            self.assertTrue(set(res) == {'user_1'})

            # Global regex search for strings containing 'li' (matches 'Alice', 'Charlie', 'linux')
            res = jdb.find(RE=r'li[a-z]')
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            # Match specific Database Keys using compiled regex (e.g., matching 'user_1', 'user_2')
            res = jdb.find(re.compile(r'^user_[1-2]$'))
            self.assertTrue(set(res) == {'user_1', 'user_2'})

            # 5. Array / List Operations
            #----------------------------------------------------------
            # Users with exactly 2 tags in their list
            res = jdb.find(vals={'tags': {'$size': 2}})
            self.assertTrue(set(res) == {'user_1', 'user_2', 'user_4'})

            # Users whose FIRST tag (index 0) is 'python'
            res = jdb.find(vals={'tags': {'$0': 'python'}})
            self.assertTrue(set(res) == {'user_1', 'user_3'})

            # 6. Lambda / Custom Functions (FUNC) & Pagination (limit)
            #----------------------------------------------------------
            # Pass a lambda to evaluate both the key and the value dynamically
            # Example: Find the first users whose age is an even number
            res = jdb.find(
                FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0,
               limit=1
            )
            self.assertTrue(set(res) == {'user_1'})

            del jdb[:]
            users = [{'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'author', 'tags':['Java']},
                        {'name': 'Bob', 'age': 25, 'role': 'helper'},
                        {'name': 'Charlie', 'age': 35, 'tags' :['python', 'programming']}]

            jdb += users
            self.assertEqual(len(jdb), 3)

            matches = jdb.find(ANY={'name': 'Alice'})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})
            matches_2 = jdb.find(ANY='Alice')
            self.assertEqual(matches, matches_2)

            # name contains 'li[a-e]' regex
            matches = jdb.find(vals={'name': r'li[a-z]'})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Charlie'})

            matches_2 = jdb.find(ANY=r'li[a-z]')
            self.assertEqual(matches, matches_2)

            matches = jdb.find(ANY=r'li[a-z]', limit=1)
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})

            # any contains r'ob'
            matches = jdb.find(ANY=r'ob')
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob'})

            # with email
            matches = jdb.find(vals={'email': r'[a-z]@[a-z]'})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})

            # age >= 30
            matches = jdb.find(vals={'age': {'$le':30}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Bob'})
            matches_2 = jdb.find(ANY={'$le':30})
            self.assertEqual(matches, matches_2)

            # age == 30
            matches = jdb.find(vals={'age': {'$eq':30}})
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

            # age in [25, 35]
            matches = jdb.find(ANY={'age': {'$in': [25, 35]}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob', 'Charlie'})
            matches_2 = jdb.find(vals={'age': {'$in': [25, 35]}})
            self.assertEqual(matches, matches_2)
            matches_2 = jdb.find(ANY={'$in': [25, 35]})
            self.assertEqual(matches, matches_2)

            # age not in [25, 35]
            matches = jdb.find(vals={'$not': {'age':{'$in':[25, 35]}}})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice'})

            matches_2 = jdb.find(NOT={'age':{'$in':[25, 35]}})
            self.assertEqual(matches, matches_2)

            # age != 30
            matches = jdb.find(NOT={'age':30})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Bob', 'Charlie'})

            # 35 >= age >= 25
            matches = jdb.find(vals={'$and': [
                {'age':{'$ge': 25}},
                {'age':{'$le': 35}}
            ]})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Bob', 'Charlie'})

            matches_2 = jdb.find(AND=[
                {'age':{'$ge': 25}},
                {'age':{'$le': 35}}
            ])
            self.assertEqual(matches, matches_2)

            matches_2 = jdb.find(vals={'age': {'$ge': 25 , '$le': 35}})
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

            # age == 25 or role != '' or name[:2] == 'Bo'
            matches = jdb.find(OR=[{'age': 25}, {'role':'.'}, {'name':r'^Bo'}])
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Alice', 'Bob'})

            # not age >= 19
            matches = jdb.find(NOT={'age': {'$ge': 18}})
            self.assertEqual(len(matches), 0)

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
            jdb[matches_2] = lambda key,val: add_tag(key, val, 'database') #pylint: disable=cell-var-from-loop
            matches = jdb.find(ANY={'$2': 'database'})
            self.assertEqual({vv['name'] for vv in matches.values()}, {'Charlie'})

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
            jmem = JDb()
            jmem['group'] = jdb1 = JDb(jdb)
            jmem.clear(agree='yes', wait_sec=0)

            csv_file = 'db/test.csv'
            jdb += {'key1':1, 'key2':'a', 'key3':3., 'key4':True, 'key5':None}
            jdb.to_csv(csv_file)
            with open(csv_file, 'rt', encoding='utf8') as fp:
                print(fp.read())

            jmem2 = JDb(data_type=jdb.data_type, zip_type=jdb.zip_type)
            jmem2.from_csv(csv_file)
            self.assertEqual(set(jdb), set(jmem2))
            self.assertNotEqual(jdb, jmem2)

            del jdb[:]
            jdb += {'key1':[1, 2], 'key2':('a', 'b'), 'key3':[3., 4.], 'key4':[True, False], 'key5':[5, 'a', 6.], 'key6':['value']}
            jdb.to_csv(csv_file)

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
            csv_example = 'ID0,name,age\n0,Alice,30\n1,Bob,25\n2,Charlie,35\n'
            with io.StringIO(csv_example) as fp:
                jdb.from_csv(fp)

            self.assertEqual(len(jdb), 3)

            matches = jdb.find(ANY={'name': 'Alice'})
            self.assertEqual(len(matches), 1)

            # name contains 'li[a-e]' regex
            matches = jdb.find(vals={'name': r'li[a-z]'})
            self.assertEqual(len(matches), 2)

            matches_2 = jdb.find(ANY=r'li')
            self.assertEqual(matches, matches_2)

            matches_3 = jdb.find(ANY=r'o')
            self.assertEqual(set(jdb), set(matches_2).union(matches_3))

            # age start with 3x
            matches = jdb.find(ANY={'age': {'$re':r'^3\d$'}})
            self.assertEqual(len(matches), 2)

            del jmem2[:]
            with io.StringIO() as fp:
                jdb.to_csv(fp)
                jmem2.from_csv(fp)
            self.assertEqual(jdb, jmem2)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jmem.recycle(level=2)
            error = jmem.check_error(level=2)
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_group_key(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            cache_limit = config['cache_limit']
            jdb = self.jdbs[filename]
            jdb.clear(agree='yes', wait_sec=0, **config)
            self.assertIsNotNone(jdb)
            self.assertEqual(len(jdb), 0)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
            if isinstance(jdb.files_obj, JNetFiles):
                continue

            gp_a = jdb.add_group('group_a')
            self.assertIsNotNone(gp_a)
            self.assertIsInstance(gp_a, JDb)
            gp_a['a'] = 1

            gp_b = jdb.add_group('group_b')
            self.assertIsNotNone(gp_b)
            self.assertIsInstance(gp_b, JDb)
            gp_b['b'] = 0

            jdb['group_b:::b'] = 2
            jdb[':::c'] = 3

            with jdb.open() as fp:
                for key in jdb.key_table:
                    child = jdb.f_get_child(fp, key)
                    if key == 'a':
                        self.assertTrue(child is gp_a)
                    elif key == 'b':
                        self.assertTrue(child is gp_b)

            key_info = gp_a.keys['a']
            self.assertEqual(key_info, jdb['group_a'].keys['a'])
            key_info2 = jdb.keys['group_a:::a']
            self.assertEqual(key_info, key_info2['group_a:::a'])
            self.assertEqual(jdb['group_a:::a'], jdb[':::a'])
            self.assertEqual(jdb.keys['group_a:::a'], jdb.keys[':::a'])
            self.assertEqual(jdb['group_a:::a'], {'group_a:::a':1})
            self.assertEqual(jdb[':::b'], {'group_b:::b':2})
            self.assertEqual(jdb[':::c'], {'group_a:::c':3, 'group_b:::c':3})
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

            with self.assertRaises(KeyError):
                gp = jdb.get_group('!!group_c')

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
            self.assertIsNotNone(gp)
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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

            jdb1.info()
            jdb.restore('bak')
            self.assertNotEqual(jdb['group_b'], expect)
            self.assertNotEqual(gp_b, expect)
            self.assertEqual(len(gp_b), 0)
            self.assertEqual(len(jdb['group_b']), 0)

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
            self.assertEqual(jdb['key3'], jdb1['key3'])

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
            self.assertEqual(jdb[0.:], jdb1[0.:])
            self.assertEqual(jdb[''], None)
            self.assertEqual(jdb['key1'], False)
            self.assertEqual(jdb['key2'], False)
            self.assertEqual(jdb['key3'], '3')
            jdb1.sync(True)
            for key,val in jdb.items():
                self.assertEqual(jdb1.get_cache(key, None), val)

            self.assertEqual(jdb1.get_cache('xxx', default_val='not exist'), 'not exist')

            error = jdb.check_error()
            self.assertTrue(not error)

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

            jmem = JDb(data_type=jdb.data_type)
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
                        _bytes = jdb.f_read_bytes(src_fp, key)
                        self.assertTrue(len(_bytes) > 0)
                        _ret = jmem.f_write_bytes(dst_fp, key, _bytes, max_wsize=0, flags=JFlag(0))
                        self.assertTrue(_ret)

                    # test nest file lock in write mode
                    with jmem.file_lock.rlock():
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
                    jmem.f_write_bytes(fp, key, val_bytes, flags=JFlag.REVERT if key.endswith('1') else None)

            self.assertEqual(jmem, expect)

            with jmem.open(read_only=False) as fp:
                for key,val in expect.items():
                    val_bytes = dumps(0, jmem.data_type[-1])
                    jmem.f_write_bytes(fp, key, val_bytes, flags=JFlag.REVERT)

            self.assertEqual(set(jmem.values()), {0})

            expect = {f'key{v}':list(range(32-v)) for v in range(32)}
            with jmem.open(read_only=False) as fp:
                for key,val in expect.items():
                    val_bytes = dumps(val, jmem.data_type[-1])
                    jmem.f_write_bytes(fp, key, val_bytes, flags=JFlag.SPLIT)

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

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            if error:
                print(error)

            self.assertTrue(not error)

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
            chg = jdb.insert(data)
            self.assertEqual(chg, data)
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
            self.assertEqual(len(jdb[lambda k,v:v in _vals]), len(chg)) # pylint: disable=W0640

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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

            ret = jdb[::r'kk1\d+']
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
                key, file_id, offset, rsize, vsize, _ver, _days, valid, val = val
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

            with jdb.open(read_only=False) as fp:
                for key,val in expect2.items():
                    jdb.f_write(fp, key, val)

            ret = jdb[float(sync_id):]
            self.assertEqual(ret, expect2)

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            jmem = JDb()
            jmem['group'] = jdb1 = JDb(jdb)
            jmem.clear(agree='yes', wait_sec=0)
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
            jdb2.remove(jdb2)
            jdb2.reinit(jdb, agree='yes', wait_sec=0)
            self.assertEqual(jdb2, expect)

            jdb2 = JDb('db/tmp.jdb')
            jdb2.remove(jdb2)
            self.assertEqual(len(jdb2), 0)

            jdb2.insert(jdb)
            self.assertEqual(jdb, jdb2)
            jdb2.remove(jdb2)
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

            matches = jdb2[::r'k[45]']
            self.assertGreaterEqual(len(matches), 2)
            self.assertEqual(set(matches), set(jdb2.keys[::r'k[45]']))
            jdb2 -= matches
            matches = jdb2[::r'k[45]']
            self.assertEqual(len(matches), 0)

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
            self.assertEqual(jdb.n_records, jdb.n_lines)
            jdb.remove(keys)
            self.assertNotEqual(jdb.n_records, jdb.n_lines)
            jdb.recycle(merge=True)
            self.assertEqual(jdb.n_records, jdb.n_lines)
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

            jdb['key1', 'key2'] = 10
            del jdb['key1', 'key2']
            self.assertEqual(jdb.get('key1', -1), -1)
            self.assertEqual(jdb.get('key2', -1), -1)
            self.assertEqual(len(jdb), 0)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            expect = {f'kkk{i}' : list(range(i+1)) for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(id(jdb._cache), cache_id)
            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertEqual(len(jdb), len(chg))

            sync_id = jdb.sync_id
            val = jdb['kkk10']
            val.append(-99)
            jdb['kkk10'] = val
            self.assertNotEqual(jdb.sync_id, sync_id)
            jdb._cache.clear()
            self.assertEqual(val, jdb['kkk10'])
            self.assertNotEqual(val, expect['kkk10'])

            sync_id = jdb.sync_id
            expect = {f'ddd{i}' : {str(v):i for v in range(i+1)} for i in range(test_size)}
            chg = jdb.insert(expect)
            self.assertEqual(chg, expect)
            self.assertNotEqual(sync_id, jdb.sync_id)
            self.assertEqual(id(jdb._cache), cache_id)

            sync_id = jdb.sync_id
            val = jdb['ddd20']
            val['dd'] = -99
            jdb['ddd20'] = val
            self.assertNotEqual(jdb.sync_id, sync_id)
            jdb._cache.clear()
            self.assertEqual(val, jdb['ddd20'])
            self.assertNotEqual(val, expect['ddd20'])
            self.assertEqual(jdb, jdb1)

            if jdb.cache_limit > 0:
                _data = jdb.find(r'kkk\d', with_value=1)
                val = jdb['ddd30']
                self.assertEqual(val, expect['ddd30'])

            del jdb[jdb - expect]
            jdb += expect
            self.assertEqual(jdb, expect)
            for limit in (-1, 0, 1):
                jdb.key_limit = limit
                jdb.unsync()
                jdb.get_all(cache_only=True)
                self.assertEqual(jdb, expect)

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            if not filename.endswith('.jdb'): continue
            _ref = jdb.restore('bak_e')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])

            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            _ref = jdb.restore('bak_j')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])

            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            _ref = jdb.restore('bak_m')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])

            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            _ref = jdb.restore('bak_x')
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])

            self.assertEqual(jdb.file_table, jdb1.file_table)
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
            self.assertEqual(jdb['sub'], sub_expect)
            jdb.remove(jdb)

            error = jdb.check_error()
            self.assertTrue(not error)
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
            zip_type = config['zip_type']
            cache_limit = config['cache_limit']
            min_value_size = config['min_value_size']
            index_size = config['index_size']

            if zip_type:
                continue

            jdb = self.jdbs[filename]
            self.assertIsNotNone(jdb)
            jdb.clear(agree='yes', wait_sec=0, **config)
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            min_value_size = jdb.min_value_size
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.n_lines, 0)
            self.assertEqual(jdb.n_records, 0)
            jdb.info()
            print(jdb.dir_name, jdb.file_name, jdb.path, jdb.key_limit)

            _val = '1' * (min_value_size // 2)
            jdb['key1'] = _val
            self.assertEqual(jdb.n_lines, 1)
            self.assertEqual(jdb.n_records, 1)
            self.assertEqual(jdb['key1'], _val)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)
            jdb['key2'] = _val = '2' * (min_value_size // 2)
            self.assertEqual(jdb.n_lines, 2)
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key2'], _val)
            row = jdb.check_row(1)
            self.assertEqual(row[0], 'key2')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            info = jdb.keys['key1']
            jdb['key1'] = _val = 'x' * (min_value_size // 2)
            self.assertNotEqual(info, jdb.keys['key1'])
            self.assertEqual(jdb.n_lines, 2)
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key1'], _val)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key1'] = _val = 'y' * (min_value_size - 3)
            self.assertEqual(jdb.n_lines, 2)
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key1'], _val)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key1'] = _val = 'z' * (min_value_size * 2)
            self.assertEqual(jdb.n_records, 2)
            self.assertEqual(jdb['key1'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table) # {0: 33} != {}
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key3'] = _val = '3' * (min_value_size * 2)
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key3'], _val)
            row = jdb.check_row(-1)
            self.assertEqual(row[0], 'key3')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key2'] = _val = '2' * (min_value_size * 2)
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key2'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key2'] = _val = '2' * (min_value_size)
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key2'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key1'] = _val = '1' * (min_value_size)
            self.assertEqual(jdb.n_records, 3)
            self.assertEqual(jdb['key1'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key4'] = _val = '4' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 4)
            self.assertEqual(jdb['key4'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key5'] = _val = '5' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 5)
            self.assertEqual(jdb['key5'], _val)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key6'] = '6' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key7'] = '7' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 7)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            del jdb['key2']
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            del jdb['key6']
            self.assertEqual(jdb.n_records, 5)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb['key8'] = 'v'+'8' * (min_value_size * 4)
            self.assertEqual(jdb.n_records, 6)
            row = jdb.check_row(-1)
            self.assertEqual(row[0], 'key8')

            jdb['key9'] = 'v'+'9' * (min_value_size // 2)
            self.assertEqual(jdb.n_records, 7)
            row = jdb.check_row(-1)
            self.assertEqual(row[0], 'key9')

            keys,_files = jdb.load_table()
            keys = set(keys)
            for key in keys:
                del jdb[key]

            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb, {})

            self.assertEqual(jdb.index_size, index_size)
            key = 'a' * jdb.index_size

            jdb[key] = 'too long'
            self.assertGreater(jdb.index_size, index_size)

            _size = len(jdb)
            jdb += ['row1', 'row1', 'row2']
            self.assertEqual(len(jdb), _size+3)

            jdb |= ('row2', 'row2', 'row3')
            self.assertEqual(len(jdb), _size+3+3)

            jdb &= {'row3', 'row4', 'row5'}
            self.assertEqual(len(jdb), _size+3+3+3)

            jdb += 'new_key0'
            self.assertEqual(jdb['new_key0'], None)
            _size = len(jdb)

            jdb |= 'new_key0'
            self.assertEqual(len(jdb), _size)

            jdb &= 'new_key0'
            self.assertEqual(len(jdb), _size)
            self.assertEqual(jdb['new_key0'], None)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb[''] = None
            jdb[None] = ''
            jdb[' '] = []
            jdb[True] = {}

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb[:], jdb1[:])
            error = jdb.check_error()
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

            # --------------------------------------------

    def test_basic2(self):
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

            if zip_type != 0:
                continue

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key2', '2' * (min_value_size // 2))
            self.assertEqual(jdb.n_lines, 2)
            self.assertEqual(jdb.n_records, 2)
            row = jdb.check_row(1)
            self.assertEqual(row[0], 'key2')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', 'x' * (min_value_size // 2))
            self.assertEqual(jdb.n_lines, 2)
            self.assertEqual(jdb.n_records, 2)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', 'y' * (min_value_size - 3))
            self.assertEqual(jdb.n_lines, 2)
            self.assertEqual(jdb.n_records, 2)
            row = jdb.check_row(0)
            self.assertEqual(row[0], 'key1')
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', 'z' * (min_value_size * 2))
            self.assertEqual(jdb.n_records, 2)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key3', '3' * (min_value_size * 2))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key2', '2' * (min_value_size * 2))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key2', '2' * (min_value_size))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key1', '1' * (min_value_size))
            self.assertEqual(jdb.n_records, 3)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key4', '4' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 4)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key5', '5' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 5)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key6', '6' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key7', '7' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 7)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.remove('key2')
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.remove('key6')
            self.assertEqual(jdb.n_records, 5)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key8', '8' * (min_value_size * 4))
            self.assertEqual(jdb.n_records, 6)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            jdb.update('key9', '9' * (min_value_size // 2))
            self.assertEqual(jdb.n_records, 7)
            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            keys,_files = jdb.load_table()
            jdb.remove(keys)

            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb, {})

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            self.assertEqual(jdb.index_size, index_size)
            key = 'a' * jdb.index_size
            jdb[key] = 'too long'
            self.assertGreater(jdb.index_size, index_size)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')
            # --------------------------------------------

    def test_basic3(self):
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

            if zip_type != 0:
                continue

            jdb.sync()
            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)

            with jdb.open(read_only=False) as fp:
                min_value_size = jdb.min_value_size
                self.assertEqual(jdb.n_lines, 0)
                self.assertEqual(jdb.n_records, 0)
                jdb.f_write(fp, 'key1', '1' * (min_value_size // 2))
                self.assertEqual(jdb.n_lines, 1)
                self.assertEqual(jdb.n_records, 1)
                row = jdb.f_read_row(fp, 0)
                self.assertEqual(row[0], 'key1')

                jdb.f_write(fp, 'key2', '2' * (min_value_size // 2))
                self.assertEqual(jdb.n_lines, 2)
                self.assertEqual(jdb.n_records, 2)
                row = jdb.f_read_row(fp, 1)
                self.assertEqual(row[0], 'key2')

                jdb.f_write(fp, 'key1', 'x' * (min_value_size // 2))
                self.assertEqual(jdb.n_lines, 2)
                self.assertEqual(jdb.n_records, 2)
                row = jdb.f_read_row(fp, 0)
                self.assertEqual(row[0], 'key1')

                jdb.f_write(fp, 'key1', 'y' * (min_value_size - 3))
                self.assertEqual(jdb.n_lines, 2)
                self.assertEqual(jdb.n_records, 2)
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
                self.assertEqual(jdb.index_size, index_size)
                key = 'a' * jdb.index_size
                jdb.f_write(fp, key, 'too long')
                self.assertGreater(jdb.index_size, index_size)

                jdb.f_write(fp, 'key9', '9' * (min_value_size // 2))

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            with jdb.open(read_only=True) as fp:
                val = jdb.f_read(fp, 'key9')
                self.assertEqual(val, '9' * (min_value_size // 2))

                self.assertNotIn('key10', jdb.key_table)
                with jdb.f_switch(fp, read_only=False) as fp1:
                    self.assertTrue(fp1 is fp)
                    jdb.f_write(fp, 'key10', 'a' * (min_value_size // 2))
                    self.assertIn('key10', jdb.key_table)

                    with jdb.f_switch(fp, read_only=True) as fp2:
                        self.assertTrue(fp1 is fp2)

                        with jdb.f_switch(fp, read_only=True) as fp3:
                            self.assertTrue(fp1 is fp3)

                with jdb.f_switch(fp, read_only=False) as fp1:
                    self.assertTrue(fp1 is fp)
                    self.assertNotIn('key111', jdb.key_table)
                    jdb.f_write(fp1, 'key111', 'b' * (min_value_size // 2))
                    self.assertIn('key111', jdb.key_table)
                    val = jdb.f_read(fp1, 'key111')
                    self.assertEqual(val.strip('b'), '')
                    with jdb.f_switch(fp, read_only=False) as fp2:
                        jdb.f_write(fp2, 'key222', 'c' * (min_value_size // 2))

                    val = jdb.f_read(fp1, 'key222')
                    self.assertEqual(val.strip('c'), '')


            _val = 'TEST' * min_value_size
            jdb[:] = _val
            self.assertTrue(all(vv == _val for vv in jdb.values()))

            jdb -= jdb # delete
            self.assertEqual(len(jdb), 0)

            test_size = 100
            expect = {f'key{v}':list(range(v+1)) for v in range(test_size)}
            jdb += expect # update
            self.assertEqual(jdb[:], expect)

            chg = {f'key{v}':v for v in range(80, test_size+20)}
            jdb &= chg # replace
            self.assertNotEqual(jdb, expect)
            self.assertEqual(jdb['key80'], chg['key80'])
            self.assertEqual(jdb['key99'], chg['key99'])

            jdb ^= chg # revert
            self.assertEqual(jdb, expect)

            jdb |= chg # insert
            self.assertEqual(len(jdb), len(expect)+20)
            self.assertEqual(jdb[jdb & expect], expect)

            jdb -= (chg - jdb)
            self.assertEqual(jdb, expect)
            self.assertTrue('key0' in jdb)
            self.assertTrue({'key0', 'key99'} in jdb)
            self.assertTrue([f'key{v}' for v in range(test_size)] in jdb)
            self.assertTrue({f'key{v}' for v in range(test_size+1)} not in jdb)
            self.assertTrue({f'key{v}':v for v in range(20,90)} not in jdb)
            self.assertTrue({'key0', 99} not in jdb)
            self.assertTrue(expect in jdb)
            self.assertTrue(chg not in jdb)
            self.assertTrue(set(expect) == jdb)
            self.assertTrue({f'key{v}' for v in range(test_size)} == jdb)
            self.assertTrue(set(chg) != jdb)

            vals = []
            try:
                vals = jdb[:]
                val = jdb['key0']
                with jdb.open(read_only=True) as fp:
                    val = jdb.f_read(fp, 'key0')
                    raise TypeError

            except TypeError:
                self.assertEqual(jdb['key0'], val)
                self.assertEqual(jdb, vals)

            try:
                with jdb.open(read_only=True) as fp:
                    val = jdb.f_read(fp, 'key0')
                    jdb.f_write(fp, 'key0', val * 2)
                    raise TypeError

            except TypeError:
                self.assertEqual(jdb['key0'], val * 2)

            try:
                self.assertTrue('new_key0' not in jdb)
                with jdb.open(read_only=True) as fp:
                    val = jdb.f_read(fp, 'key0')
                    jdb.f_write(fp, 'new_key0', val * 2)
                    raise TypeError

            except TypeError:
                self.assertEqual(jdb['key0'], val)
                self.assertEqual(jdb['new_key0'], val * 2)

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

            jdb2 = JDb(jdb)
            self.assertFalse(jdb2.is_latest())
            with self.assertRaises(KeyboardInterrupt):
                with jdb2.open(read_only=True) as fp:
                    self.assertTrue(jdb2.io.is_updated())
                    raise KeyboardInterrupt

            self.assertFalse(jdb2.is_latest())
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

            matches = jdb.find(lambda k: k.find('0') > 0)
            self.assertEqual(matches, {f'kkk{i}':None for i in range(0,100,10)})

            matches = jdb.find(lambda k,v: k.find('0') > 0 and v <= 20)
            self.assertEqual(matches, {f'kkk{i}':i for i in (0, 10,20)})

            matches = jdb.find(NOT={'$ge':10})
            self.assertEqual(matches, {f'kkk{i}':i for i in range(10)})

            matches = jdb.find(AND=[{'$ge':10}, {'$lt':20}])
            self.assertEqual(matches, {f'kkk{i}':i for i in range(10, 20)})

            matches = jdb.find(NOT={'$or':[{'$lt':10}, {'$ge':20}]})
            self.assertEqual(matches, {f'kkk{i}':i for i in range(10, 20)})

            matches = jdb.find('kkk', sort=1)
            self.assertEqual(matches, expect)
            self.assertEqual(list(matches.items())[0], ('kkk0', 0))
            self.assertEqual(list(matches.items())[99], ('kkk99', 99))

            matches = jdb.find('kkk', sort=-1)
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

            matches = jdb.find(LE=10)
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

            keys = jdb.keys[0.]
            matches = dict(jdb.item_iter(0.))
            self.assertEqual(jdb[keys], matches)

            matches = jdb.find(HAS='洲')
            self.assertEqual(set(matches), {'美國'})

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

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            jdb = JDb(jdb)
            self.assertFalse(jdb.is_latest())
            self.assertEqual(jdb.fsize, 0)
            self.assertEqual(len(jdb), 0)

            jdb.sync()
            self.assertTrue(jdb.is_latest())
            self.assertGreaterEqual(jdb.fsize, 128)

            print(Style(f'Testing {filename} {jdb} rate:{jdb.reserved_rate*100.:.1f}% cache:{cache_limit}', yellow=1, bright=1))
            # --------------------------------------------
            jdb1 = JDb(jdb)
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

            self.assertNotEqual(jdb.sync_id, jdb1.sync_id)
            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[::3], jdb1.keys[::3])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            file_table = jdb.file_table
            for file_id in file_table:
                self.assertTrue(jdb.files_obj.VAL_exist(file_id))

            jdb.clear()
            self.assertEqual(jdb, expect)

            jdb.clear(agree='yes', wait_sec=1)
            self.assertNotEqual(jdb, expect)
            self.assertEqual(len(jdb.file_table), 0)
            self.assertEqual(len(jdb), 0)
            self.assertEqual(jdb.n_lines, 0)

            for file_id in file_table:
                self.assertFalse(jdb.files_obj.VAL_exist(file_id))

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
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
                with jdb2.f_switch(fp, read_only=False) as fp2:
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
            self.assertEqual(jdb, expect2)
            self.assertEqual(jdb2, expect2)

            ret = jdb.rename({f'xxx{i}' : f'kkkk{i}' for i in range(test_size)})
            self.assertEqual(len(ret), 0)
            self.assertEqual(jdb, expect2)
            self.assertEqual(jdb2, expect2)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            self.assertEqual(jdb.sync_id, sync_id)

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

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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

            if jdb.key_limit == 'no':
                for key,val in jdb.items(read_only=False):
                    jdb.f_write(None, key, val + 1)
                    self.assertEqual(val + 1, jdb.f_read(None, key))
            else:
                keys = list(jdb)
                with jdb.open(read_only=False) as fp:
                    for key in keys:
                        val = jdb.f_read(fp, key)
                        jdb.f_write(fp, key, val + 1)
                        self.assertEqual(val + 1, jdb.f_read(fp, key))

            for key,val in jdb.item_iter():
                self.assertEqual(expect[key] + 1, val)

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            self.assertEqual(len(jdbl), len(jdb))
            self.assertEqual(jdbl.get_n(), jdb.get_all())
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

            self.assertFalse(jdbl.is_latest())
            self.assertNotEqual(jdbl.sync_id, jdb.sync_id)
            self.assertEqual(jdbl.get_n(), jdb.get_all())
            self.assertTrue(jdbl.is_latest())

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_write(self):
        for config in self.jdb_configs:
            st_time = time.perf_counter()
            filename = config['KEY_file']
            zip_type = config['zip_type']
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

            sync_id = jdb.sync_id
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

            if zip_type == 0:
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
            jdb.remove('zzz1')
            jdb.remove('zzz3')
            self.assertNotEqual(jdb.sync_id, jdb2.sync_id)

            self.assertEqual(jdb, jdb2)

            jdb.remove('zzz2')
            self.assertEqual(jdb, jdb2)

            jdb['zzz1'] = 34
            jdb['zzz2'] = 45
            jdb['zzz3'] = 56
            jdb2.sync()
            self.assertEqual(jdb.sync_id, jdb2.sync_id)
            jdb.remove('zzz1')
            jdb.remove('zzz3')
            jdb.remove('zzz2')
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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

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
            self.assertTrue(not error)

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
            with jdb.open(read_only=False) as fp:
                _io, fp, _key_fp = jdb.f_get_fp(fp)
                for key,val in new_expect.items():
                    if key not in jdb.key_table:
                        expect[key] = val
                        jdb.f_write(fp, key, val)

                    elif not random.randint(0, 1):
                        jdb.f_delete(fp, key)
                    else:
                        jdb.f_write(fp, key, val) # change

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

            jmem = JDb()
            jmem['key13', 'key23'] = 1
            jdb ^= jmem
            self.assertEqual(jdb, expect)

            jdb['key13', 'key23'] = 'val'
            jdb.unmodify('key13', 'key23')
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
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_date(self):
        now = dt.datetime.now()
        old_date = now - dt.timedelta(days=10)
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
            _old_date = jdb.io.z_conv_days(old_date.timestamp())
            self.assertEqual(_old_date + 10, _now)

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

            matches = jdb[old_date:]
            self.assertEqual(matches, expect)
            matches = jdb.keys[old_date:]
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
            self.assertTrue(not matches)

            matches = jdb[:old_date]
            self.assertTrue(not matches)
            matches = jdb.keys[:old_date]
            self.assertTrue(not matches)

            matches = jdb[old_date:_now]
            self.assertEqual(matches, expect)
            matches = jdb.keys[old_date:_now]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[dt.datetime(2010, 1, 1):_now]
            self.assertEqual(matches, expect)
            matches = jdb.keys[dt.datetime(2010, 1, 1):_now]
            self.assertEqual(set(matches), set(expect))

            matches = jdb[now:old_date]
            self.assertTrue(not matches)
            matches = jdb.keys[now:old_date]
            self.assertTrue(not matches)

            info0 = jdb.keys['kk1']
            self.assertNotEqual(info0[-1], str(old_date.date()))

            with jdb.open(read_only=False) as fp:
                jdb.f_change_days(fp, 'kk1', _old_date)

            self.assertEqual(jdb.keys['kk1'][-1], str(old_date.date()))
            info1 = jdb.keys['kk2']
            self.assertNotEqual(info1[-1], str(old_date.date()))
            jdb.keys['kk2'] = _old_date

            _old = old_date + dt.timedelta(days=1)
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
            self.assertNotEqual(info[-1], str(old_date.date()))
            jdb.set_days('kk3', old_date.date())
            info1 = jdb.keys['kk3']
            self.assertNotEqual(info, info1)
            self.assertEqual(info1[-1], str(old_date.date()))

            del jdb['kk3']
            jdb.unremove('kk3')
            info = jdb.keys['kk3']
            self.assertEqual(info[-1], str(old_date.date()))

            val = jdb['kk3']
            jdb.remove('kk3')
            jdb['kk3'] = val
            info = jdb.keys['kk3']
            self.assertNotEqual(info[-1], str(old_date.date()))
            ref_days = jdb.keys['kk4'][-1]
            self.assertEqual(info[-1], ref_days)

            jdb.set_days('kk3', old_date.date())
            jdb2 = JDb(jdb)
            self.assertEqual(jdb, jdb2)
            jdb['kk3'] = 'kk3'
            if jdb.n_lines != jdb2.n_lines:
                self.assertEqual(jdb['kk3'], jdb2['kk3'])
                self.assertEqual(jdb.key_table, jdb2.key_table)
                self.assertEqual(jdb.file_table, jdb2.file_table)

            info = jdb.keys['kk3']
            self.assertNotEqual(info[-1], ref_days)
            self.assertEqual(info[-1], str(old_date.date()))

            jdb.remove('kk3')
            jdb.unremove('kk3')
            info = jdb.keys['kk3']
            self.assertEqual(info[-1], str(old_date.date()))

            jdb.upgrade()
            info = jdb.keys['kk3']
            self.assertEqual(info[-1], str(old_date.date()))

            jdb.set_days('kk3', '1000-01-01')
            info1 = jdb.keys['kk3']
            self.assertEqual(info1[-1], '1000-01-01')
            self.assertEqual(info[-2], info1[-2])

            jdb.set_days('kk3', '2000-10-10 1900-01-01')
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], '1900-01-01')
            self.assertEqual(info2[-2], '2000-10-10')
            self.assertEqual(len(jdb.keys[:dt.date(2000,12,12)]), 1)
            self.assertEqual(len(jdb.keys[:dt.date(1900,12,12)]), 0)
            self.assertEqual(len(jdb.keys[:dt.datetime(1900,12,12)]), 1)
            self.assertEqual(len(jdb[:dt.date(2000,12,12)]), 1)
            self.assertEqual(len(jdb[:dt.date(1900,12,12)]), 0)
            self.assertEqual(len(jdb[:dt.datetime(1900,12,12)]), 1)
            self.assertEqual(set(jdb.find('kk', date='2000-10-10')), {'kk3'})
            self.assertEqual(set(jdb.find('kk', date='2000-10-1 2000-10-30')), {'kk3'})
            self.assertEqual(set(jdb.find('kk', date='1900-12-1 1900-12-30')), set())
            self.assertEqual(set(jdb.find('kk', date=dt.date(2000, 10, 10))), {'kk3'})
            self.assertEqual(set(jdb.find('kk', date=dt.datetime(1900, 1, 1))), {'kk3'})

            jdb.keys['kk3'] = '2000-1-1 1900-10-10'
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], '1900-10-10')
            self.assertEqual(info2[-2], '2000-01-01')

            jdb.keys['kk3'] = '1900-10-10 2000-1-1'
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], '1900-10-10')
            self.assertEqual(info2[-2], '2000-01-01')

            today = dt.date.today()
            yesterday = today - dt.timedelta(days=1)
            prev_week = today - dt.timedelta(days=7)
            prev_prev_week = today - dt.timedelta(days=14)

            jdb.keys['kk3'] = today
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
            for key,val in jdb1.keys.item_iter(slice(None)):
                self.assertEqual(jdb.keys[key], val)

            jmem = JDb()
            jmem['group'] = jdb
            jmem.keys['group:::kk3'] = yesterday
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], str(yesterday))
            self.assertEqual(info2[-2], str(today))

            jdb.keys['kk4'] = yesterday
            info2 = jdb.keys['kk4']
            self.assertEqual(info2[-1], str(yesterday))

            jdb.keys['kk3', 'kk4'] = today
            for key,info in jdb.keys.item_iter(('kk3', 'kk4')):
                self.assertEqual(info[-1], str(today))

            jdb.keys[re.compile(r'k[34]$')] = yesterday
            for key,info in jdb.keys.item_iter(re.compile(r'k[34]$')):
                self.assertEqual(info[-1], str(yesterday))

            matches = jdb.keys[lambda key,info:info[-1] == str(yesterday)]  # pylint: disable=W0640
            jdb.keys[lambda key,info:info[-1] == str(yesterday)] = today  # pylint: disable=W0640
            for key,info in jdb.keys.item_iter(lambda key:key.endswith(('k3', 'k4'))):
                self.assertEqual(info[-1], str(today))

            jdb.keys[lambda key:key.endswith(('k3', 'k4'))] = yesterday
            for key,info in jdb.keys.item_iter(('kk3', 'kk4')):
                self.assertEqual(info[-1], str(yesterday))

            jmem.keys[':::kk3'] = today
            info2 = jdb.keys['kk3']
            self.assertEqual(info2[-1], str(today))

            jdb.keys[::'kk4'] = '2000-1-1 1900-10-10'
            matches = jdb.keys[::'kk4']
            self.assertTrue(len(matches) > 4)
            for key,info2 in matches.items():
                self.assertEqual(info2[-1], '1900-10-10')
                self.assertEqual(info2[-2], '2000-01-01')

            matches = jdb.keys[1]
            self.assertTrue(len(matches) == 1)
            key = list(matches)[0]
            jdb.keys[1] = prev_week
            for key,info in jmem.keys[f'group:::{key}'].items():
                self.assertEqual(info[-1], str(prev_week))

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
            self.assertTrue(jdb[1].startswith(r'1_'))

            matches = jdb.keys[prev_prev_week:prev_week]
            self.assertTrue(len(matches) == 0)
            jdb.keys[prev_prev_week:prev_week] = today

            prev_week = dt.datetime(prev_week.year, prev_week.month, prev_week.day)
            matches = jdb.keys[:prev_week]
            self.assertTrue(len(matches) > 0)
            jdb.keys[:prev_week] = today

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
                self.assertEqual(info[-1], str(yesterday))

            matches = jmem.keys[[':::kk13', ':::kk14', ':::kk13']]
            self.assertEqual(len(matches), 2)
            jmem.keys[[':::kk13', ':::kk14', ':::kk13']] = prev_prev_week
            for key,info in jmem.keys[matches].items():
                self.assertEqual(info[-1], str(prev_prev_week))

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
                jdb.f_write(fp, 'new_key100', 'new_value', days=str(yesterday))

            info = jdb.keys['new_key100']
            self.assertEqual(info[-1], str(yesterday))

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

    def test_type(self):
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

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb.keys[:], jdb1.keys[:])
            self.assertEqual(jdb.keys[0.:], jdb1.keys[0.:])
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.sync_id, jdb1.sync_id)

            error = jdb.check_error()
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

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
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A=1] chg N
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['A'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('D', 'E')
                jmem1 = JDb(jmem).sync()
                jmem['B'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E', 'F'], val0)
                jmem.remove('D', 'E', 'F')
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A=2] chg N
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['A'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem['D'] = val1_0
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['B'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem['D'] = val1_0
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A=3] del N + add N (ADD == DEL)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C')
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C', 'D')
                jmem.insert(['E', 'F'], val0)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C', 'D')
                jmem.insert(['E', 'F', 'G', 'H'], val0)
                jmem.remove('G', 'H')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.insert(['E', 'F'], val0)
                jmem.remove('E', 'F')
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.insert({'D':val1, 'E':val0})
                jmem.remove('D', 'E')
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A-1] del N (N > 0)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A-2] del N + add M (DEL > ADD)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                jmem['B'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C')
                jmem.insert(['C', 'D'], val1)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C')
                jmem['C'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
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
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                jmem.remove(['B', 'C', 'D'])
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                jmem.remove(['C', 'D'])
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
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
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A-3] add N + del M (DEL > ADD)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                jmem.remove('C', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.insert(['E', 'F'], val0)
                jmem.remove('D', 'E', 'F')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A+1] add N
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('D', 'E')
                jmem1 = JDb(jmem).sync()
                jmem['E'] = val1
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem.remove('D')
                jmem1 = JDb(jmem).sync()
                jmem['E'] = val1_0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A+2] add N + chg M
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val0, 'X':val1})
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'B'], val0)
                jmem.remove('B')
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val0, 'X':val1_0})
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val0, 'B':val0, 'X':val1_0, 'Y':val1_0})
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [A+3] add N + del M  or del M + add N (ADD > DEL)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.insert(['A', 'B'], val0)
                jmem.remove('B')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['X', 'Y', 'Z', 'A', 'B'], val0)
                jmem.remove('B')
                jmem1 = JDb(jmem).sync()
                jmem.remove('A')
                jmem.insert(['C', 'D'], val0)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'X':val1_0, 'Y':val0, 'Z':val0})
                jmem1 = JDb(jmem).sync()
                jmem.insert(['A', 'B'], val0)
                jmem.remove('B')
                jmem['X'] = val0
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'A':val1_0, 'B':val1_0, 'C':val0, 'D':val0})
                jmem1 = JDb(jmem).sync()
                jmem.insert(['E', 'F', 'G'], val0)
                jmem.remove('G')
                jmem.replace(['A', 'B'], val0)
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
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
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B1-2]
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('A')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem.remove('B', 'C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.remove('A', 'B', 'C', 'D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B1=0]
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1_0
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['C', 'E'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['C', 'E', 'A'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['E','A'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['A', 'E'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem.remove('E')
                jmem1 = JDb(jmem).sync()
                jmem['B'] = val1_0
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['A', 'B', 'C'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E', 'F'], val0)
                jmem.remove('D', 'E', 'F')
                jmem1 = JDb(jmem).sync()
                jmem.update(['A', 'B', 'C'], val1_0)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B2-0] chg N + del M (DEL > ADD)
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['C'] = val1_0
                jmem.remove('C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['D', 'C'], val1_0)
                jmem.remove('C')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update(['D', 'C'], val1_0)
                jmem.remove('D')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem['A'] = val1_0
                jmem.remove('A')
                self.assertNotEqual(jmem.key_table, jmem1.key_table)
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                # [B2=0] ADD == DEL
                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert(['A', 'B', 'C', 'D', 'E'], val0)
                jmem1 = JDb(jmem).sync()
                jmem.update({'A':val1_0, 'E':val1_1})
                jmem['E'] = val1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

                jmem = JDb(data_type=data_type, zip_type=zip_type, key_limit=key_limit)
                jmem.insert({'A':val0, 'B':val0, 'C':val0, 'D':val0, 'E':val1_0, 'F':val0, 'G':val0})
                jmem.remove('F', 'G')
                jmem1 = JDb(jmem).sync()
                jmem['D'] = val1_1
                jmem['B'] = val1_1
                self.assertEqual(jmem, jmem1)
                self.assertEqual(jmem.file_table, jmem1.file_table)
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
                self.assertEqual(jmem.file_table, jmem1.file_table)
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
                self.assertEqual(jmem.file_table, jmem1.file_table)
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
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.key_table, jmem1.key_table)

            #------------------------------
            jmem = JDb(None, data_type=data_type, zip_type=zip_type, key_limit=key_limit)
            self.assertTrue(isinstance(jmem.files_obj, JMemFiles))

            jmem1 = JDb(jmem, flags=JFlag.REVERT|JFlag.SPLIT)
            jmem1['key0'] = val = list(range(200))
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

            test_size = 100
            expect = {f'key{v}':1 for v in range(test_size)}
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

            ret = jmem[lambda k: k.endswith('1')]
            self.assertEqual(len(ret),  9)

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

            expect = {f'key{v}': {
                        'str':f'value-{v:03d}'*((v%test_size)+1),
                        'list':[random.randrange(v+test_size) for _ in range(test_size)],
                        'float1':1.1,
                        'float2':-1.,
                        'bool': True,
                        'max_int':2**64-1,
                        'min_int':-(2**63)} for v in range(test_size)}

            total = len(expect)
            expect.update({'max_int':2**64-1, 'min_int':-(2**63), 'bool': True, 'float1':1.1, 'float2':-1.})

            del jmem[:]
            ret = jmem.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(jmem, expect)
            self.assertEqual(len(jmem), len(expect))
            self.assertEqual(len(jmem.keys[lambda k:k.startswith('key')]), total)
            self.assertEqual(len(jmem.keys[lambda k,v:k.startswith('key') and v[3] > 0]), total)
            self.assertEqual(len(jmem.find(FUNC=lambda v:isinstance(v, dict))), total)
            self.assertEqual(len(jmem.find(FUNC=lambda k,v:k.startswith('key') and isinstance(v, dict))), total)

            for data_type_str in ('L+J', 'J+J', 'M+M', 'J+P', 'S+S', 'S+Y'):
                for zip_type_str in ('no', 'gz', 'bz', 'xz', 'br', 'z1', 'lz'):
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
            ret = jdb.remove_fast(jdb)
            self.assertEqual(ret, set(expect))
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
            self.assertEqual(len(jdb), total - 10)

            total = jdb.len_()
            del jdb[lambda key: key.endswith('1')]
            self.assertEqual(len(jdb), total - 11)

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
                self.assertEqual(jmem.file_table, jmem1.file_table)
                self.assertEqual(jmem.sync_id, jmem1.sync_id)

            ret = jdb.remove_fast(jdb)
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

            expect = {f'key{k}':f'vvv{k}' for k in range(test_size)}
            ret = jdb.insert(expect)
            self.assertEqual(ret, expect)
            self.assertEqual(jdb, expect)
            self.assertEqual(jdb1, expect)
            self.assertEqual(set(jdb.keys), set(jdb1.keys))
            self.assertEqual(set(jdb.keys.items()), set(jdb1.keys.items()))
            self.assertEqual(set(jdb.keys.values()), set(jdb1.keys.values()))

            ret = jdb.remove_fast(jdb)
            self.assertEqual(ret, set(expect))
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
            self.assertEqual(jdb.file_table, jdb0.file_table)
            self.assertEqual(jdb.sync_id, jdb0.sync_id)

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
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.file_table, jdb2.file_table)

            jdb['C'] = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' * min_value_size * 2
            del jdb['C']

            self.assertEqual(jdb, jdb1)
            self.assertEqual(jdb, jdb2)
            self.assertEqual(dict(jdb.key_table), dict(jdb1.key_table))
            self.assertEqual(dict(jdb.key_table), dict(jdb2.key_table))
            self.assertEqual(dict(jdb1.key_table), dict(jdb2.key_table))
            self.assertEqual(jdb.file_table, jdb1.file_table)
            self.assertEqual(jdb.file_table, jdb2.file_table)

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

            error = jdb.check_error()
            self.assertTrue(not error)

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

            self.assertEqual(jdb0, expect)
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
                                worker.f_delete(fp, key)
                            else:
                                old_val = worker.f_read(fp, key)
                                worker.f_write(fp, key, new_val)
                                worker.f_delete(fp, key)
                                worker.f_undelete(fp, key)
                                worker.f_unwrite(fp, key)
                                worker.f_write(fp, key, old_val)
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
                                worker.f_delete(fp, key)
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
                        if key in key_table:
                            worker.f_delete(fp, key)
                        else:
                            worker.f_write(fp, key, new_val)

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

                                worker.f_delete(fp, new_key)

                            else:
                                if old_key in key_table:
                                    worker.f_delete(fp, old_key)
                                else:
                                    worker.f_write(fp, old_key, new_val)

                                worker.f_undelete(fp, new_key)
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
                        JDb(jdb, key_limit='no', cache_limit=-1)]

            expect = {f'k{v}' : [v%10] * (test_size + 1) for v in range(test_size)}
            jmem = JDb()
            jmem['main'] = jdb
            self.assertTrue(jmem.get_child('main') is jdb)

            jdb.insert(expect)
            self.assertEqual(jdb, expect)

            for ii,_jdb in enumerate(jdb_list):
                self.assertEqual(_jdb, expect)
                self.assertEqual(set(_jdb.key_table), set(expect))
                self.assertEqual(jdb, _jdb)
                self.assertEqual(jdb.get_all(), _jdb.get_all())
                self.assertEqual(jdb.file_table, _jdb.file_table)
                self.assertEqual(jdb.key_table, _jdb.key_table)

            steps = [(ii,random.randint(1,8),random.randint(0,len(jdb_list)-1),random.randint(0,6),random.randint(1, 32),random.randint(0,99)) for ii in range(step_size)]
            random.shuffle(steps)
            th_list = [None] * len(jdb_list)
            for step,(key_id,n_keys,_id,op,_ll,th_id) in enumerate(steps):
                step += 1
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
                    # if id(_jdb) != id(jdb):
                    #     error = _jdb.check_error()
                    #     self.assertTrue(not error)
                    #     self.assertEqual(jdb, _jdb)
                    #     with jdb.open():
                    #         with _jdb.open():
                    #             # safe to check key_table/file_table in multi-thread
                    #             self.assertEqual(jdb.file_table, _jdb.file_table)
                    #             self.assertEqual(jdb.key_table, _jdb.key_table)

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
                self.assertTrue(not error)
                self.assertEqual(jdb, _jdb)
                self.assertEqual(jdb.get_all(), _jdb.get_all())
                self.assertEqual(jdb.file_table, _jdb.file_table)
                self.assertEqual(jdb.key_table, _jdb.key_table)

            jmem.unsync(with_child=True)
            error = jmem.check_error(level=2)
            self.assertTrue(not error)

            used_s = time.perf_counter() - st_time
            fsize = sum(jdb.file_table.values()) if jdb.file_table else 0
            print(f'{filename}|{jdb}| size:{fsize//1024:,}KB used:{used_s:.4f}s')

if __name__ == '__main__':
    print(Style('JDb Unit Testing ...', blink=1, cyan=1))
    unittest.main(verbosity=2)

#
