Introduction
============

**omni-json-db** is a high-performance, embedded database engine designed for
Python developers. It combines the raw speed of a Key-Value store with the
flexible querying of a document database and the associative power of a graph
database.

Built for high throughput and thread safety, **omni-json-db** utilizes modern
serialization (*JSON*, *MsgPack*, *marshal*, *Pickle*, *YAML*) and efficient
compression to provide a compact storage layer. Whether you are building a local
cache, a log aggregator, or a complex knowledge graph, **omni-json-db** offers
"Zero-Config" simplicity at scale.

* **Schema-LESS**: Store complex, nested data without pre-defining tables.

* **Server-LESS**: Access data directly on disk without a database server overhead.

* **SQL-LESS**: Manipulate data using standard Python syntax, Regex, and Lambdas.

* **Dependency-LESS**: Runs on a clean Python install with **zero required third-party packages** — optional C-accelerators and extra formats are one ``pip install "omni-json-db[full]"`` away.

Why omni-json-db?
-----------------

Unlike traditional SQL or NoSQL databases, **omni-json-db** allows you to query and manipulate data using native Python syntax—including slicing, lambdas, regex, and set operations. It also features built-in "Time-Travel" (undo/redo), a property-graph engine, and pluggable serialization.

..

   **omni-json-db** has been tested with Python 3.7+ and PyPy3. (~100% test coverage)

.. list-table::
   :widths: 30 16 10 11 10 9 11 9 9
   :header-rows: 1

   * - 
     - **omni-json-db**
     - TinyDB
     - DiskCache
     - UnQLite
     - LMDB
     - RocksDict
     - SQLite
     - DuckDB
   * - Transactions / ACID [t]_
     - ⚠️ (transaction)
     - ❌
     - ❌
     - ❌
     - ✅
     - ✅
     - ✅
     - ✅
   * - Thread-safe concurrency
     - ✅ (MR/SW)
     - ❌
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
   * - Multi-process access
     - ✅ (file lock)
     - ❌
     - ✅
     - ✅
     - ✅
     - ⚠️ (read only)
     - ✅
     - ✅
   * - In-memory mode
     - ✅
     - ✅
     - ❌
     - ✅
     - ❌
     - ❌
     - ✅
     - ✅
   * - CSV / SQLite / Parquet built-in
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ⚠️ (CLI)
     - ✅
   * - Compression built-in
     - ✅
     - ❌
     - ✅
     - ❌
     - ❌
     - ✅
     - ❌
     - ✅
   * - No schema (Schema-less)
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ❌
     - ❌
   * - Dataclass mapping [z]_
     - ✅
     - ❌
     - ⚠️
     - ❌
     - ❌
     - ⚠️
     - ❌
     - ❌
   * - Groups / Namespaces
     - ✅
     - ✅
     - ⚠️
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
   * - Nested groups + fan-out queries
     - ✅
     - ⚠️ (flat)
     - ❌
     - ⚠️
     - ⚠️ (flat)
     - ⚠️ (CF)
     - ⚠️ (SQL)
     - ⚠️ (SQL)
   * - Pure Python (PyPy-friendly)
     - ✅
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Pythonic queries (Lambda/Regex)
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Deep nested search
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Graph database engine
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Undo / Redo (Time-Travel)
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Time-series date slicing 
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Network mode (incl. groups)
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Relative speed 500K records [x]_
     - 1.00x (baseline)
     - 41.47x
     - 60.95x
     - 4.28x
     - 0.94x
     - 0.45x
     - 0.13x
     - 0.21x
   * - Relative speed 10M records [x]_
     - 1.00x (baseline)
     - N/A [y]_
     - N/A [y]_
     - 24.07x
     - 1.31x
     - 0.55x
     - 0.16x
     - 0.05x

.. [t] ``with jdb.transaction():`` undoes everything the block wrote if it raises — see :doc:`usage/transactions`. Exception-safe, not crash-safe: a ``kill -9`` is not rolled back.
.. [x] Lower is faster. (see the `benchmark <https://github.com/lukatrum/omni-json-db/blob/main/benchmark/report.txt>`_ for the full breakdown and methodology)
.. [y] Impractically slow
.. [z] Write a ``@dataclass`` and read it back as an object. ⚠️ = the object can be *stored*, but only as an opaque ``pickle`` blob: its fields are invisible to queries, and the file is unreadable outside Python.

Features
--------
* **Native Graph Engine**: Transform your Key-Value store into a Property Graph. The ``GraphDb`` layer supports O(1) adjacency indexing and classic algorithms (BFS, Dijkstra, DFS, cycle detection) without sacrificing performance.

* **Pythonic Interaction**: Interact with data using familiar Python ``dict`` methods, list slicing, and set operations, avoiding complex SQL queries.

* **Dataclass Objects**: Read and write any ``@dataclass`` directly — ``jdb += user``, ``jdb['u1'] = user``, ``del jdb[user]``. The object is flattened into a plain ``dict`` rather than pickled, so records written from objects stay fully queryable, exportable, and language-neutral.

* **Advanced Serialization & Compression**: Combine formats (JSON, MsgPack, Pickle, YAML) with algorithms like LZ4, Zstandard, or Brotli to optimize your I/O and disk usage.

* **Pluggable Codec & Encryption**: Bring your own serialization or encryption logic via a simple ``dumps``/``loads`` interface — no forking required. Supports both a process-wide default and per-instance codecs (e.g. per-tenant encryption keys).

* **Powerful Query Engine**: Execute searches via Regex, Lambda filters, and rich operators (``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``, ...).

* **Operational Modes**: Supports In-Memory mode (``JMemFiles``) for high performance and Network mode (``JNetFiles``) to serve data over a network.

* **State Management**: Built-in "Time-Travel" allows you to track states, undo modifications (``unmodify()``), or recover deleted data (``unremove()``). ``history()`` lists every version still reachable, and ``min_safe`` decides how many of them survive.

* **All-or-Nothing Writes**: ``with jdb.transaction():`` opens a write session that puts back everything it changed if the block raises — modifications, deletions, bulk inserts and renames alike. Nesting acts as a savepoint.

* **Batch Writes**: Bulk inserts take a dedicated append path — one ``write()`` per VAL file and one encoded block for the KEY rows instead of a syscall per record — so ``jdb += rows``, ``insert()`` and every importer land 1.4x–4.5x faster with no API change.

* **Fast Open at Scale**: A disposable key-table snapshot (``index_cache``) cuts a cold open by ~4x, and ``warm_up`` moves what is left onto a background thread.

* **Data Migration**: Effortlessly migrate from SQLite or import/export via CSV, Parquet, INI, and TOML with simple commands. Parquet imports stream in constant memory via ``pyarrow`` record batches, so multi-GB files are no problem.

* **Time-Series Ready**: Native timestamping allows for efficient date-based slicing (e.g., ``jdb[yesterday:now]``).

* **Memory Caching**: Adjustable ``cache_limit`` to balance RAM usage and I/O speed.

* **Grouping & Namespaces**: Easily isolate and manage different data modules using groups.

* **Per-Record Flags**: Give any record file-system-like attributes with a ``chmod``-style syntax — read-only, append-only, hidden, uncached, no-history — plus symbolic links to other records or groups, and per-record TTLs from one minute to 511 days.

* **Concurrency Control**: Optimized for Many-Read / Single-Write environments using a robust file-locking and Lock mechanism.

