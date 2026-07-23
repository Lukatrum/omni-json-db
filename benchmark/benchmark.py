# pylint: disable=unspecified-encoding, use-dict-literal, multiple-imports
"""Benchmark orchestrator.

Runs every (engine, mode) combination in an isolated subprocess so that
peak-RSS numbers are clean, then prints a comparison table and saves
results.json.

Usage: python3 run_benchmark.py [--rows N] [--k K] [--csv path]
"""
import os, sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import argparse, importlib.util, json, multiprocessing as mp, shutil
from bench_worker import run_test, gen_csv_data

HERE = os.path.dirname(os.path.abspath(__file__))

ENGINE_MODES = [
    ('omnijdb', 'memory'),  ('sqlite', 'memory'),   ('duckdb', 'memory'),   ('unqlite', 'memory'),  ('tinydb', 'memory'),
    ('omnijdb', 'file'),    ('sqlite', 'file'),     ('duckdb', 'file'),     ('unqlite', 'file'),    ('tinydb', 'file'),
    ('lmdb', 'file'),       ('diskcache', 'file'),  ('rocksdict', 'file')
]

OPS = ['load_s', 'point_query_s', 'filter_query_s', 'agg_query_s',
       'point_update_s', 'bulk_update_s', 'point_insert_s', 'point_delete_s',
       'close_s', 'total_s']
LABEL = {'load_s': 'Load CSV', 'point_query_s': 'Point query xK',
         'filter_query_s': 'Filter scan', 'agg_query_s': 'Aggregate',
         'point_update_s': 'Point update xK', 'bulk_update_s': 'Bulk update',
         'point_insert_s': 'Point insert xK', 'point_delete_s': 'Point delete xK',
         'close_s': 'Close/flush', 'total_s': 'TOTAL open->close'}

def have(mod):
    return importlib.util.find_spec(mod) is not None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rows', type=int, default=1_000_000)
    ap.add_argument('--k', type=int, default=1_000)
    ap.add_argument('--csv', default=None)
    ap.add_argument('--no-isolate', action='store_true',
                    help='run in-process (debugging only: RSS numbers get contaminated)')
    args = ap.parse_args()
    ctx = mp.get_context('spawn')   # fresh interpreter per run: clean RSS + MemTracker

    csv_path = args.csv or os.path.join(HERE, f'data_{args.rows}.csv')
    if not os.path.exists(csv_path):
        print(f'== generating {args.rows:,} row CSV ...', flush=True)
        gen_csv_data(args.rows, csv_path)

    results = []
    for engine,mode in ENGINE_MODES:
        if engine in ('duckdb', 'tinydb', 'lmdb', 'unqlite', 'diskcache') and not have(engine):
            print(f'== {engine} not installed, skipping (pip install {engine})', flush=True)
            continue

        if engine in ('tinydb', 'diskcache') and (args.rows > 500_000 or args.k > 10_000) or \
                engine in ('unqlite') and (args.rows > 1_000_000 or args.k > 10_000):
            print(f'== {engine} skip this test (rows={args.rows})')
            continue

        workdir = os.path.join(HERE, f'dbwork_{engine}_{mode}')
        shutil.rmtree(workdir, ignore_errors=True)
        os.makedirs(workdir, exist_ok=True)
        print(f'== running {engine} / {mode} ...', flush=True)
        if args.no_isolate:
            r = run_test(engine, mode, csv_path, args.k, workdir)
        else:
            with ctx.Pool(1) as pool:
                r = pool.apply(run_test, (engine, mode, csv_path, args.k, workdir))
        results.append(r)
        if r.get('ok'):
            print(f'   done: load={r["load_s"]:.2f}s peakRSS={r["rss_after_load_mb"]:.0f}MB total={r["total_s"]:.2f}s')
        else:
            print(f'   FAILED: {r.get("error")}')
        shutil.rmtree(workdir, ignore_errors=True)

    out = os.path.join(HERE, 'results.json')
    with open(out, 'w') as f:
        json.dump(dict(rows=args.rows, k=args.k, results=results), f, indent=2)

 # ---------------- report ----------------
    ok = [r for r in results if r.get('ok')]
    if not ok:
        return
    cols = [f'{r["engine"]}/{r["mode"]}' for r in ok]
    w = max(16, max(len(c) for c in cols) + 2)
    tag = ''
    print(f'\n===== BENCHMARK  rows={args.rows:,}  K={args.k:,}{tag} =====')
    print('Time in seconds (lower is better)\n')
    print('operation'.ljust(18) + ''.join(c.rjust(w) for c in cols))
    for op in OPS:
        line = LABEL[op].ljust(18)
        for r in ok:
            line += f'{r.get(op, float("nan")):.3f}'.rjust(w)
        print(line)
    print()
    for metric, label in [('rss_load_delta_mb', 'RSS after load MB'),
                          ('sampled_peak_mb', 'Peak RSS MB'),
                          ('file_size_mb', 'DB file size MB')]:
        line = label.ljust(18)
        for r in ok:
            v = r.get(metric)
            line += (f'{v:.0f}' if v is not None else '-').rjust(w)
        print(line)
    # ---- memory checkpoint table (RSS in MB after each phase) ----
    labels = []
    for r in ok:
        for c in r.get('mem_checkpoints', []):
            if c['label'] not in labels:
                labels.append(c['label'])
    if labels:
        print('\nMemory checkpoints - RSS MB right after each phase')
        print('(phase peak in parentheses when psutil sampling is available)\n')
        print('checkpoint'.ljust(18) + ''.join(c.rjust(w) for c in cols))
        for lb in labels:
            line = lb.ljust(18)
            for r in ok:
                m = {c['label']: c for c in r.get('mem_checkpoints', [])}
                c = m.get(lb)
                if c is None:
                    cell = '-'
                elif c.get('phase_peak_mb') is not None:
                    cell = f"{c['rss_mb']:.0f} ({c['phase_peak_mb']:.0f})"
                else:
                    cell = f"{c['rss_mb']:.0f}"
                line += cell.rjust(w)
            print(line)

    # sanity: filter counts should match across engines
    counts = {f'{r["engine"]}/{r["mode"]}': (r.get('filter_match'), r.get('point_query_r'), r.get('rows_final')) for r in ok}
    print('\nfilter_match sanity:', counts)

if __name__ == '__main__':
    main()
