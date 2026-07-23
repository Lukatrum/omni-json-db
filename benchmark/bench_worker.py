"""Benchmark worker: runs ONE engine in ONE storage mode inside a clean process.
 
Engines : sqlite | duckdb | omnijdb
Modes   : memory | file
 
Measured operations (identical logical workload for every engine):
  load          bulk-load the whole CSV (N rows, 6 columns)
  point_query   K random primary-key lookups
  filter_query  full-scan filter: category='electronics' AND price>500 (count)
  agg_query     AVG(price) + SUM(qty) grouped by category
  point_update  K random single-row updates (qty = qty + 1)
  bulk_update   update every row with category='toys' (price = price*1.1)
 
Memory  : peak RSS of this process (ru_maxrss), plus RSS delta after load.
Output  : one JSON object on stdout.
 
Usage: python3 bench_worker.py <engine> <mode> <csv_path> <k_ops> [workdir]
"""
# pylint: disable=multiple-imports, import-error, unused-import, consider-using-max-builtin
# pylint: disable=unspecified-encoding, consider-using-dict-items, subprocess-run-check
# pylint: disable=use-dict-literal, use-yield-from, import-outside-toplevel, too-few-public-methods
import sqlite3
import csv, json, os, random, resource, sys, time, subprocess
from collections import defaultdict
try:
    import duckdb
except ImportError:
    duckdb = None
try:
    from tinydb import TinyDB, Query
    from tinydb.storages import MemoryStorage, JSONStorage
    from tinydb.middlewares import CachingMiddleware
    from tinydb.operations import add
except ImportError:
    TinyDB = None
from omni_json_db import JDb, __version__

try:
    import lmdb
except ImportError:
    lmdb = None

try:
    from unqlite import UnQLite
except ImportError:
    UnQLite = None

try:
    import diskcache
except ImportError:
    diskcache = None

try:
    import diskcache
except ImportError:
    diskcache = None
try:
    from rocksdict import Rdict
    try:
        from rocksdict import WriteBatch
    except ImportError:
        WriteBatch = None
except ImportError:
    Rdict = None

K_SEED = 1234

def fsync_files(workdir, prefix):
    """fsync every db file. On macOS use F_FULLFSYNC: plain fsync() there
    only reaches the drive cache, not stable storage."""
    for f in os.listdir(workdir):
        if not f.startswith(prefix):
            continue
        fd = os.open(os.path.join(workdir, f), os.O_RDONLY)
        try:
            if sys.platform == 'darwin':
                import fcntl
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
            else:
                os.fsync(fd)
        finally:
            os.close(fd)

class MemTracker:
    """Checkpoint-based memory measurement (macOS-safe).
 
    - rss()  : current RSS via psutil > /proc (linux) > `ps` (macOS/unix)
    - mark() : record a named RSS checkpoint OUTSIDE timed regions
    - sampler: if psutil is available, a daemon thread samples RSS at 20 Hz
               so transient peaks inside a phase are captured too.
    ru_maxrss is NOT used: on macOS it is a whole-process historical
    high-water mark in bytes (KB on Linux) and is often misleading.
    """
    def __init__(self):
        self._psutil = None
        try:
            import psutil
            self._psutil = psutil.Process()
        except ImportError:
            pass
        self.checkpoints = []          # [(label, rss_mb), ...]
        self.sampled_peak = 0.0
        self._phase_peak = 0.0
        if self._psutil is not None:
            import threading
            def _sample():
                while True:
                    r = self.rss()
                    if r > self.sampled_peak:
                        self.sampled_peak = r
                    if r > self._phase_peak:
                        self._phase_peak = r
                    time.sleep(0.05)
            threading.Thread(target=_sample, daemon=True).start()

    def rss(self):
        if self._psutil is not None:
            return self._psutil.memory_info().rss / 1e6
        if sys.platform == 'linux':
            with open('/proc/self/status') as f:
                for line in f:
                    if line.startswith('VmRSS'):
                        return int(line.split()[1]) / 1024.0
            return 0.0

        out = subprocess.run(['ps', '-o', 'rss=', '-p', str(os.getpid())],
                             capture_output=True, text=True).stdout.strip()
        return int(out) / 1024.0 if out else 0.0

    def reset(self):
        """Fresh per-run state: MUST be called at the start of run_test,
        otherwise checkpoints/peaks leak across runs in the same process."""
        self.checkpoints = []          # new list: results must not share refs
        self.sampled_peak = 0.0
        self._phase_peak = 0.0

    def mark(self, label):
        r = self.rss()
        peak = max(self._phase_peak, r) if self._psutil else None
        self._phase_peak = r           # reset for next phase
        self.checkpoints.append(
            dict(label=label, rss_mb=round(r, 1),
                 phase_peak_mb=round(peak, 1) if peak is not None else None))
        if r > self.sampled_peak:
            self.sampled_peak = r
        return r

MT = MemTracker()

def rss_mb():
    return MT.rss()

def timed(fn, *args, **kwargs):
    t = time.perf_counter()
    out = fn(*args, **kwargs)
    return time.perf_counter() - t, out

def read_csv_rows(path):
    with open(path, newline='') as f:
        r = csv.reader(f)
        # pylint: disable=stop-iteration-return
        next(r)  # header
        for row in r:
            yield row

CATEGORIES = ['electronics', 'toys', 'books', 'grocery', 'clothing',
              'sports', 'garden', 'auto', 'health', 'office']

FIRST = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot',
         'golf', 'hotel', 'india', 'juliet']

def gen_csv_data(rows:int=1_000_000, out:str='data_.csv'):
    rnd  = random.Random(42)                      # deterministic
    t0   = int(time.time()) - 86400 * 365
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'name', 'category', 'price', 'qty', 'created_ts'])
        for i in range(rows):
            w.writerow([
                i,
                f'{rnd.choice(FIRST)}-{i}',
                rnd.choice(CATEGORIES),
                round(rnd.uniform(1, 1000), 2),
                rnd.randint(0, 500),
                t0 + rnd.randint(0, 86400 * 365),
            ])

    print(f'wrote {rows} rows -> {out}')

def phase_sync(mode, workdir):
    if mode != 'file':
        return
    fsync_files(workdir, 'bench.')

# --------------------------------------------------------------------------- SQL engines
def run_sql(engine, mode, csv_path, k, workdir):
    if engine == 'sqlite':
        db_file = ':memory:' if mode == 'memory' else os.path.join(workdir, 'bench.sqlite')
        if db_file != ':memory:' and os.path.exists(db_file):
            os.remove(db_file)
        con = sqlite3.connect(db_file)
        con.execute('PRAGMA synchronous=NORMAL')
        con.execute('PRAGMA journal_mode=WAL' if mode == 'file' else 'PRAGMA journal_mode=MEMORY')
        ph = '?, ?, ?, ?, ?, ?'
    else:  # duckdb
        db_file = ':memory:' if mode == 'memory' else os.path.join(workdir, 'bench.duckdb')
        if db_file != ':memory:' and os.path.exists(db_file):
            os.remove(db_file)
        con = duckdb.connect(db_file)
        ph = '?, ?, ?, ?, ?, ?'

    res = {}
    con.execute('''CREATE TABLE items (
        id INTEGER PRIMARY KEY, name TEXT, category TEXT,
        price DOUBLE PRECISION, qty INTEGER, created_ts BIGINT)'''
        .replace('DOUBLE PRECISION', 'REAL') if engine == 'sqlite' else
        '''CREATE TABLE items (
        id INTEGER PRIMARY KEY, name VARCHAR, category VARCHAR,
        price DOUBLE, qty INTEGER, created_ts BIGINT)''')

    rss_before = rss_mb()
    MT.mark('start')

    # -- load ---------------------------------------------------------------
    def load():
        if engine == 'duckdb':
            # DuckDB native CSV reader is its idiomatic bulk-load path
            con.execute(f"INSERT INTO items SELECT * FROM read_csv_auto('{csv_path}', header=true)")
        else:
            cur = con.cursor()
            batch = []
            for row in read_csv_rows(csv_path):
                batch.append((int(row[0]), row[1], row[2], float(row[3]), int(row[4]), int(row[5])))
                if len(batch) >= 50_000:
                    cur.executemany(f'INSERT INTO items VALUES ({ph})', batch)
                    batch.clear()
            if batch:
                cur.executemany(f'INSERT INTO items VALUES ({ph})', batch)
            con.commit()

    res['load_s'], _ = timed(load)
    MT.mark('load')
    res['rss_after_load_mb'] = rss_mb()
    res['rss_load_delta_mb'] = res['rss_after_load_mb'] - rss_before

    n_rows = con.execute('SELECT COUNT(*) FROM items').fetchone()[0]
    res['rows'] = n_rows
    rnd = random.Random(K_SEED)
    ids = [rnd.randrange(n_rows) for _ in range(k)]

    # -- point_query ----------------------------------------------------------
    def point_query():
        s = 0.0
        for i in ids:
            s += con.execute('SELECT price FROM items WHERE id=?', (i,)).fetchone()[0]
        return s
    res['point_query_s'], total = timed(point_query)
    MT.mark('point_query')
    res['point_query_r'] = total

    # -- filter_query -----------------------------------------------------------
    def filter_query():
        return con.execute(
            "SELECT COUNT(*) FROM items WHERE category='electronics' AND price>500"
        ).fetchone()[0]
    times = []
    for _ in range(3):
        t, cnt = timed(filter_query)
        times.append(t)
    res['filter_query_s'] = sum(times) / len(times)
    MT.mark('filter_query')
    res['filter_match'] = cnt

    # -- agg_query --------------------------------------------------------------
    def agg_query():
        return con.execute(
            'SELECT category, AVG(price), SUM(qty) FROM items GROUP BY category'
        ).fetchall()
    res['agg_query_s'], rows = timed(agg_query)
    MT.mark('agg_query')
    res['agg_groups'] = len(rows)

    # -- point_update -----------------------------------------------------------
    def point_update():
        for i in ids:
            con.execute('UPDATE items SET qty = qty + 1 WHERE id=?', (i,))
        if engine == 'sqlite':
            con.commit()
    res['point_update_s'], _ = timed(point_update)
    MT.mark('point_update')

    # -- bulk_update ------------------------------------------------------------
    def bulk_update():
        con.execute("UPDATE items SET price = price * 1.1 WHERE category='toys'")
        if engine == 'sqlite':
            con.commit()

    res['bulk_update_s'], _ = timed(bulk_update)
    MT.mark('bulk_update')

    # -- point_insert: K single-row inserts (new ids) ---------------------------
    new_rows = [(n_rows + j, f'new-{j}', 'inserted', 9.99, 1, 1700000000 + j)
                for j in range(len(ids))]
    def point_insert():
        for r in new_rows:
            con.execute(f'INSERT INTO items VALUES ({ph})', r)
        if engine == 'sqlite':
            con.commit()
    res['point_insert_s'], _ = timed(point_insert)
    MT.mark('point_insert')

    # -- point_delete: delete those K rows one by one ---------------------------
    def point_delete():
        for r in new_rows:
            con.execute('DELETE FROM items WHERE id=?', (r[0],))
        if engine == 'sqlite':
            con.commit()
    res['point_delete_s'], _ = timed(point_delete)
    MT.mark('point_delete')
    res['rows_final'] = con.execute('SELECT COUNT(*) FROM items').fetchone()[0]

    def _close():
        con.close()
        phase_sync(mode, workdir)

    res['close_s'], _ = timed(_close)

    if mode == 'file':
        res['file_size_mb'] = sum(
            os.path.getsize(os.path.join(workdir, f)) / 1e6
            for f in os.listdir(workdir) if f.startswith('bench.')
        )

    res['sampled_peak_mb'] = round(MT.sampled_peak, 1) if MT._psutil else None
    res['mem_checkpoints'] = MT.checkpoints
    return res

# --------------------------------------------------------------------------- TinyDB
def run_tinydb(mode, csv_path, k, workdir):
    """TinyDB benchmark.

    Notes on fairness:
    - memory mode : MemoryStorage
    - file mode   : JSONStorage wrapped in CachingMiddleware. Without the
      cache TinyDB rewrites the ENTIRE json file on every single write,
      which makes per-op updates at 1M rows take days. We therefore batch
      in memory and time explicit flush() calls so writes really hit disk
      once per phase - this is TinyDB's documented best practice.
    - point ops use doc_id access (rows inserted in order => doc_id = id+1),
      which is TinyDB's fastest lookup path.
    """
    res = {}
    if mode == 'memory':
        db = TinyDB(storage=MemoryStorage)
        flush = lambda: None
    else:
        path = os.path.join(workdir, 'bench.tinydb.json')
        if os.path.exists(path):
            os.remove(path)
        db = TinyDB(path, storage=CachingMiddleware(JSONStorage))
        db.storage.WRITE_CACHE_SIZE = float('inf')   # flush manually per phase
        flush = db.storage.flush

    rss_before = rss_mb()
    MT.mark('start')

    # -- load -----------------------------------------------------------------
    def load():
        batch = []
        for row in read_csv_rows(csv_path):
            batch.append({
                'id': int(row[0]), 'name': row[1], 'category': row[2],
                'price': float(row[3]), 'qty': int(row[4]), 'created_ts': int(row[5]),
            })
            if len(batch) >= 50_000:
                db.insert_multiple(batch)
                batch.clear()
        if batch:
            db.insert_multiple(batch)
        flush()
    res['load_s'], _ = timed(load)
    MT.mark('load')
    res['rss_after_load_mb'] = rss_mb()
    res['rss_load_delta_mb'] = res['rss_after_load_mb'] - rss_before

    n_rows = len(db)
    res['rows'] = n_rows
    rnd = random.Random(K_SEED)
    ids = [rnd.randrange(n_rows) for _ in range(k)]

    # -- point_query: doc_id lookup (fastest TinyDB path) ----------------------
    def point_query():
        s = 0.0
        for i in ids:
            s += db.get(doc_id=i + 1)['price']
        return s
    res['point_query_s'], total = timed(point_query)
    MT.mark('point_query')
    res['point_query_r'] = total

    # -- filter_query -----------------------------------------------------------
    Item = Query()
    cond = (Item.category == 'electronics') & (Item.price > 500)
    def filter_query():
        return len(db.search(cond))
    times = []
    for _ in range(3):
        t, cnt = timed(filter_query)
        times.append(t)
    res['filter_query_s'] = sum(times) / len(times)
    MT.mark('filter_query')
    res['filter_match'] = cnt

    # -- agg_query: manual scan aggregation ------------------------------------
    def agg_query():
        sums, cnts, qtys = {}, {}, {}
        for v in db:
            c = v['category']
            sums[c] = sums.get(c, 0.0) + v['price']
            cnts[c] = cnts.get(c, 0) + 1
            qtys[c] = qtys.get(c, 0) + v['qty']
        return {c: (sums[c] / cnts[c], qtys[c]) for c in sums}

    res['agg_query_s'], groups = timed(agg_query)
    MT.mark('agg_query')
    res['agg_groups'] = len(groups)

    # -- point_update -----------------------------------------------------------
    def point_update():
        for i in ids:
            db.update(add('qty', 1), doc_ids=[i + 1])
        flush()
    res['point_update_s'], _ = timed(point_update)
    MT.mark('point_update')

    # -- bulk_update ------------------------------------------------------------
    def scale_price(doc):
        doc['price'] *= 1.1
    def bulk_update():
        db.update(scale_price, Item.category == 'toys')
        flush()
    res['bulk_update_s'], _ = timed(bulk_update)
    MT.mark('bulk_update')

    # -- point_insert: K single-doc inserts -------------------------------------
    new_docs = [{'id': n_rows + j, 'name': f'new-{j}', 'category': 'inserted',
                 'price': 9.99, 'qty': 1, 'created_ts': 1700000000 + j}
                for j in range(len(ids))]

    def point_insert():
        for d in new_docs:
            db.insert(d)
        flush()
    res['point_insert_s'], _ = timed(point_insert)
    MT.mark('point_insert')

    # -- point_delete: remove those K docs by doc_id one by one -----------------
    def point_delete():
        for j in range(len(new_docs)):
            db.remove(doc_ids=[n_rows + 1 + j])
        flush()
    res['point_delete_s'], _ = timed(point_delete)
    MT.mark('point_delete')
    res['rows_final'] = len(db)

    def _close():
        db.close()
        phase_sync(mode, workdir)

    res['close_s'], _ = timed(_close)
    if mode == 'file':
        res['file_size_mb'] = os.path.getsize(
            os.path.join(workdir, 'bench.tinydb.json')) / 1e6

    res['sampled_peak_mb'] = round(MT.sampled_peak, 1) if MT._psutil else None
    res['mem_checkpoints'] = list(MT.checkpoints)
    return res

# --------------------------------------------------------------------------- omni-json-db
def run_omnijdb(mode, csv_path, k, workdir):
    res = {}
    if mode == 'memory':
        path = ''
    else:
        path = os.path.join(workdir, 'bench.jdb')
        for f in os.listdir(workdir):
            if f.startswith('bench.jdb'):
                os.remove(os.path.join(workdir, f))

    jdb = JDb(path, data_type='J+J', index_size=64, flags=0, max_wsize=0)
    print(f'\t\tomni-json-db({__version__}) mode:{mode} {jdb}')
    rss_before = rss_mb()
    MT.mark('start')

    # -- load: key = id (str), value = row dict ------------------------------
    def load():
        with jdb.open(read_only=False) as fp:
            f_append = jdb.f_append
            for (key, name, cat, price, qty, ts) in read_csv_rows(csv_path):
                f_append(fp, key, {'name': name, 'category': cat, 'price': float(price), 'qty': int(qty), 'create_ts': int(ts)})

    res['load_s'], _ = timed(load)
    MT.mark('load')
    res['rss_after_load_mb'] = rss_mb()
    res['rss_load_delta_mb'] = res['rss_after_load_mb'] - rss_before

    # old_data = dict(jdb)
    n_rows = len(jdb)
    res['rows'] = n_rows
    rnd = random.Random(K_SEED)
    ids = [str(rnd.randrange(n_rows)) for _ in range(k)]
    # -- point_query: key lookup (JDb's O(1) native strength) ------------------
    def point_query():
        s = 0.0
        with jdb.open() as fp:
            f_read = jdb.f_read
            for i in ids:
                s += f_read(fp, i, copy=False)['price']
        return s

    res['point_query_s'], total = timed(point_query)
    MT.mark('point_query')
    res['point_query_r'] = total

    # sum(old_data[k]['price'] for k in ids) != total and breakpoint()
    # -- filter_query: lambda full scan -----------------------------------------
    def filter_query():
        cnt = 0
        with jdb.open() as fp:
            for _key,val in jdb.f_items(fp):
                if val['category'] == 'electronics' and val['price'] > 500:
                    cnt += 1
        return cnt

    times = []
    for _ in range(3):
        t, cnt = timed(filter_query)
        times.append(t)

    res['filter_query_s'] = sum(times) / len(times)
    MT.mark('filter_query')
    res['filter_match'] = cnt

    # -- agg_query: manual scan aggregation (no SQL GROUP BY equivalent) -------
    def agg_query():
        sums, cnts, qtys = defaultdict(int), defaultdict(int), defaultdict(int)
        with jdb.open() as fp:
            for _key,val in jdb.f_items(fp):
                c = val['category']
                sums[c] += val['price']
                cnts[c] += 1
                qtys[c] += val['qty']

        return {c: (sums[c] / cnts[c], qtys[c]) for c in sums}

    res['agg_query_s'], groups = timed(agg_query)
    MT.mark('agg_query')
    res['agg_groups'] = len(groups)
    # -- point_update: read-modify-write per key -------------------------------
    def point_update():
        with jdb.open(read_only=False) as fp:
            f_read = jdb.f_read
            f_write = jdb.f_write
            for i in ids:
                v = f_read(fp, i, copy=False)
                v['qty'] += 1
                f_write(fp, i, v, overwrite=True)

    res['point_update_s'], _ = timed(point_update)
    MT.mark('point_update')

    # -- bulk_update: find matches then write back ------------------------------
    def bulk_update():
        # (1) M:59,559 O/s F: 56,242 O/s
        # jdb.update_if(lambda v:v['category'] == 'toys', lambda k,v: {'price' : v['price'] * 1.1})
        # (2) M:139,470 O/s F:81,833 O/s vs SQL F: 2,040,816 O/s
        with jdb.open(read_only=False) as fp:
            f_write = jdb.f_write
            for key,val in jdb.f_items(fp):
                if val['category'] == 'toys':
                    val['price'] *= 1.1
                    f_write(fp, key, val, overwrite=True, max_wsize=0, flags=0)

    res['bulk_update_s'], _ = timed(bulk_update)
    MT.mark('bulk_update')
    # any(v['price'] * 1.1 != jdb[k]['price'] for k,v in old_data.items() if v['category']  == 'toys') and breakpoint()

    # -- point_insert: K single-key inserts -------------------------------------
    new_items = {str(n_rows + j): {'name': f'new-{j}',
                 'category': 'inserted', 'price': 9.99, 'qty': 1,
                 'created_ts': 1700000000 + j} for j in range(len(ids))}    

    def point_insert(jdb):
        jdb += new_items
    res['point_insert_s'], _ = timed(point_insert, jdb)
    MT.mark('point_insert')

    # -- point_delete: delete those K keys one by one ---------------------------
    def point_delete(jdb):
        jdb -= new_items

    res['point_delete_s'], _ = timed(point_delete, jdb)
    MT.mark('point_delete')
    res['rows_final'] = len(jdb)

    def _close():
        phase_sync(mode, workdir)

    res['close_s'], _ = timed(_close)
    # -----------------------------------------------
    if mode == 'file':
        res['file_size_mb'] = sum(
            os.path.getsize(os.path.join(workdir, f)) / 1e6
            for f in os.listdir(workdir) if f.startswith('bench.jdb')
        )

    res['sampled_peak_mb'] = round(MT.sampled_peak, 1) if MT._psutil else None
    res['mem_checkpoints'] = list(MT.checkpoints)
    return res

# --------------------------------------------------------------------------- KV engines
# One generic runner + tiny adapters. Serialization follows each engine's
# native idiom: LMDB/UnQLite store JSON bytes (like omnijdb 'J+J'),
# DiskCache/Shelve store dicts via their built-in pickle protocol.
class _LmdbKV:                                    # file-only (mmap B-tree)
    prefix = 'bench.lmdb'
    def __init__(self, _mode, workdir):
        # sync=False ~= sqlite WAL synchronous=NORMAL tier (OS crash may lose
        # recent txns, app crash safe). strict mode would use sync=True.
        self.env = lmdb.open(os.path.join(workdir, self.prefix),
                             map_size=8 << 30, subdir=True,
                             sync=False, metasync=False)
    def put_many(self, items):
        with self.env.begin(write=True) as txn:
            for k, v in items:
                txn.put(k.encode(), json.dumps(v, separators=(',', ':')).encode())
    def get(self, key):
        with self.env.begin() as txn:
            b = txn.get(key.encode())
        return None if b is None else json.loads(b)
    def put(self, key, val):
        with self.env.begin(write=True) as txn:
            txn.put(key.encode(), json.dumps(val, separators=(',', ':')).encode())
    def delete(self, key):
        with self.env.begin(write=True) as txn:
            txn.delete(key.encode())
    def iter_vals(self):
        with self.env.begin() as txn:
            for _k, b in txn.cursor():
                yield json.loads(b)
    def iter_items(self):
        with self.env.begin() as txn:
            for kb, b in txn.cursor():
                yield kb.decode(), json.loads(b)
    def phase_commit(self):
        self.env.sync(False)
    def close(self):
        self.env.close()

class _UnqliteKV:                                 # memory + file
    prefix = 'bench.unqlite'
    def __init__(self, mode, workdir):
        self.db = UnQLite(':mem:' if mode == 'memory' else
                          os.path.join(workdir, self.prefix))
    def put_many(self, items):
        db = self.db
        with db.transaction():
            for k, v in items:
                db[k] = json.dumps(v, separators=(',', ':'))
    def get(self, key):
        return json.loads(self.db[key])
    def put(self, key, val):
        self.db[key] = json.dumps(val, separators=(',', ':'))
    def delete(self, key):
        del self.db[key]
    def iter_vals(self):
        for _k, b in self.db:
            yield json.loads(b)
    def iter_items(self):
        for kk, b in self.db:
            yield kk if isinstance(kk, str) else kk.decode(), json.loads(b)
    def phase_commit(self):
        self.db.commit()
    def close(self):
        self.db.close()

class _DiskcacheKV:                               # file-only (sqlite-backed)
    prefix = 'bench.diskcache'
    def __init__(self, _mode, workdir):
        self.c = diskcache.Cache(os.path.join(workdir, self.prefix))
    def put_many(self, items):
        cset = self.c.set
        for k, v in items:
            cset(k, v)
    def get(self, key):
        return self.c[key]
    def put(self, key, val):
        self.c[key] = val
    def delete(self, key):
        del self.c[key]
    def iter_vals(self):
        c = self.c
        for k in c.iterkeys():
            yield c[k]
    def iter_items(self):
        c = self.c
        for k in c.iterkeys():
            yield k, c[k]
    def phase_commit(self):
        pass                                      # sqlite autocommit per op
    def close(self):
        self.c.close()

class _RocksdictKV:                               # file-only (RocksDB LSM-tree)
    """rocksdict: Rust binding to RocksDB. Values stored as native Python
    objects via its built-in serialization (same treatment as DiskCache)."""
    prefix = 'bench.rocksdict'
    def __init__(self, _mode, workdir):
        self.db = Rdict(os.path.join(workdir, self.prefix))
    def put_many(self, items):
        db = self.db
        if WriteBatch is not None:
            wb = WriteBatch()
            for k, v in items:
                wb.put(k, v)
            db.write(wb)
        else:
            for k, v in items:
                db[k] = v
    def get(self, key):
        return self.db[key]
    def put(self, key, val):
        self.db[key] = val
    def delete(self, key):
        del self.db[key]
    def iter_vals(self):
        for _k, v in self.db.items():
            yield v
    def iter_items(self):
        for k, v in self.db.items():
            yield k, v
    def phase_commit(self):
        self.db.flush()
    def close(self):
        self.db.close()

KV_ADAPTERS = {'lmdb': _LmdbKV, 'unqlite': _UnqliteKV, 'rocksdict': _RocksdictKV,
               'diskcache': _DiskcacheKV}

def run_kv(engine, mode, csv_path, k, workdir):
    kv = KV_ADAPTERS[engine](mode, workdir)
    res = {}
    rss_before = rss_mb()
    MT.mark('start')

    def load():
        batch = []
        for row in read_csv_rows(csv_path):
            batch.append((row[0], {'name': row[1], 'category': row[2],
                          'price': float(row[3]), 'qty': int(row[4]),
                          'create_ts': int(row[5])}))
            if len(batch) >= 50_000:
                kv.put_many(batch); batch.clear()
        if batch:
            kv.put_many(batch)
        kv.phase_commit()
    res['load_s'], _ = timed(load)
    MT.mark('load')
    res['rss_after_load_mb'] = rss_mb()
    res['rss_load_delta_mb'] = res['rss_after_load_mb'] - rss_before

    n_rows = sum(1 for _ in kv.iter_vals())
    res['rows'] = n_rows
    rnd = random.Random(K_SEED)
    ids = [str(rnd.randrange(n_rows)) for _ in range(k)]

    def point_query():
        total = 0.0
        for i in ids:
            total += kv.get(i)['price']
        return total
    res['point_query_s'], total = timed(point_query)
    res['point_query_r'] = round(total, 2)
    MT.mark('point_query')

    def filter_query():
        return sum(1 for v in kv.iter_vals()
                   if v['category'] == 'electronics' and v['price'] > 500)
    times = []
    for _ in range(3):
        t, cnt = timed(filter_query)
        times.append(t)
    res['filter_query_s'] = sum(times) / len(times)
    res['filter_match'] = cnt
    MT.mark('filter_query')

    def agg_query():
        sums, cnts, qtys = {}, {}, {}
        for v in kv.iter_vals():
            c = v['category']
            sums[c] = sums.get(c, 0.0) + v['price']
            cnts[c] = cnts.get(c, 0) + 1
            qtys[c] = qtys.get(c, 0) + v['qty']
        return {c: (sums[c] / cnts[c], qtys[c]) for c in sums}
    res['agg_query_s'], groups = timed(agg_query)
    res['agg_groups'] = len(groups)
    MT.mark('agg_query')

    def point_update():
        for i in ids:
            v = kv.get(i)
            v['qty'] += 1
            kv.put(i, v)
        kv.phase_commit()
    res['point_update_s'], _ = timed(point_update)
    MT.mark('point_update')

    def bulk_update():
        hits = [(kk, v) for kk, v in kv.iter_items() if v['category'] == 'toys']
        for kk, v in hits:
            v['price'] *= 1.1
            kv.put(kk, v)
        kv.phase_commit()
        return len(hits)
    res['bulk_update_s'], _ = timed(bulk_update)
    MT.mark('bulk_update')

    new_items = [(str(n_rows + j), {'name': f'new-{j}', 'category': 'inserted',
                 'price': 9.99, 'qty': 1, 'create_ts': 1700000000 + j})
                 for j in range(len(ids))]
    def point_insert():
        for kk, vv in new_items:
            kv.put(kk, vv)
        kv.phase_commit()
    res['point_insert_s'], _ = timed(point_insert)
    MT.mark('point_insert')

    def point_delete():
        for kk, _vv in new_items:
            kv.delete(kk)
        kv.phase_commit()
    res['point_delete_s'], _ = timed(point_delete)
    MT.mark('point_delete')
    res['rows_final'] = sum(1 for _ in kv.iter_vals())

    def _close():
        kv.close()
    res['close_s'], _ = timed(_close)
    if mode == 'file':
        total = 0
        for root, _d, files in os.walk(workdir):
            for f in files:
                total += os.path.getsize(os.path.join(root, f))
        res['file_size_mb'] = total / 1e6
    res['sampled_peak_mb'] = round(MT.sampled_peak, 1) if MT._psutil else None
    res['mem_checkpoints'] = list(MT.checkpoints)
    return res

def run_test(engine:str, mode:str, csv_path:str, k:int, workdir:str='/tmp/benchdb'):
    MT.reset()
    t_start = time.perf_counter()
    os.makedirs(workdir, exist_ok=True)
    try:
        if engine in ('sqlite', 'duckdb'):
            res = run_sql(engine, mode, csv_path, k, workdir)
        elif engine == 'tinydb':
            res = run_tinydb(mode, csv_path, k, workdir)
        elif engine in KV_ADAPTERS:
            res = run_kv(engine, mode, csv_path, k, workdir)
        elif engine == 'omnijdb':
            res = run_omnijdb(mode, csv_path, k, workdir)
        else:
            raise ValueError(engine)

        res['total_s'] = time.perf_counter() - t_start
        res.update(engine=engine, mode=mode, ok=True)

    except Exception as e:  # noqa: BLE001
        res = dict(engine=engine, mode=mode, ok=False, error=f'{type(e).__name__}: {e}')

    return res

#
