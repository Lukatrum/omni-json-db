Introduction
============

**omni-json-db** is a high-performance, embedded database engine designed for Python developers. It bridges the gap between the extreme speed of a Key-Value store and the powerful querying capabilities of a document database.


Built for ultra-high throughput and thread-safety, **omni-json-db** leverages modern serialization (*JSON*, *MsgPack*, *marshal*, *pickle*, *YAML*) and compression to provide a storage layer that is often significantly faster than *SQLite* for *JSON*-heavy workloads. Whether you are building a local cache, a log aggregator, or a distributed microservice, **omni-json-db** provides the tools to handle data at scale with "Zero-Config" simplicity.

* **Schema-LESS**: Store complex, nested data without pre-defining tables.

* **Server-LESS**: Direct disk access without the overhead of a database server.

* **SQL-LESS**: Use native Python syntax, Regex, and Lambdas for data manipulation.

* **Dependency-LESS**: Runs on a clean Python install with **zero required third-party packages** — optional C-accelerators and extra formats are one ``pip install "omni-json-db[full]"`` away.

🤔 Why omni-json-db?
********************

Unlike traditional SQL or NoSQL databases, **omni-json-db** lets you use native
Python syntax — slicing, lambdas, regex, and ``set`` operations — to query and
manipulate data. It adds built-in "Time-Travel" (undo/redo), a property-graph
engine, and pluggable serialization/compression.

..

   **omni-json-db** has been tested with Python 3.7+ and PyPy3. (~100% test coverage)

+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
|                                  | **omni-json-db**  | TinyDB    | DiskCache | UnQLite | LMDB       | RocksDict | SQLite    | DuckDB    |
+==================================+===================+===========+===========+=========+============+===========+===========+===========+
| Transactions / ACID              | ⚠️ (atomic ops)   | ❌        | ❌        | ❌      | ✅         | ✅        | ✅        | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Thread-safe concurrency          | ✅ (MR/SW)        | ❌        | ✅        | ✅      | ✅         | ✅        | ✅        | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Multi-process access             | ✅ (file lock)    | ❌        | ✅        | ✅      | ✅         | ⚠️ (RO)   | ✅        | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| In-memory mode                   | ✅                | ✅        | ❌        | ✅      | ❌         | ❌        | ✅        | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| CSV / SQLite migration built-in  | ✅                | ❌        | ❌        | ❌      | ❌         | ❌        | ⚠️ (CLI)  | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Compression built-in             | ✅                | ❌        | ✅        | ❌      | ❌         | ✅        | ❌        | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| No schema (Schema-less)          | ✅                | ✅        | ✅        | ✅      | ✅         | ✅        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Groups / Namespaces              | ✅                | ✅        | ⚠️        | ✅      | ✅         | ✅        | ✅        | ✅        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Nested groups + fan-out queries  | ✅                | ⚠️ (flat) | ❌        | ⚠️      | ⚠️ (flat)  | ⚠️ (CF)   | ⚠️ (SQL)  | ⚠️ (SQL)  |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Pure Python (PyPy-friendly)      | ✅                | ✅        | ✅        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Pythonic queries (Lambda/Regex)  | ✅                | ✅        | ❌        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Deep nested search               | ✅                | ❌        | ❌        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Graph database engine            | ✅                | ❌        | ❌        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Undo / Redo (Time-Travel)        | ✅                | ❌        | ❌        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Time-series date slicing         | ✅                | ❌        | ❌        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Network mode (incl. groups)      | ✅                | ❌        | ❌        | ❌      | ❌         | ❌        | ❌        | ❌        |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+


Features
--------
* **Native Graph Engine**: Transform your Key-Value store into a Property Graph. The ``GraphDb`` layer supports O(1) adjacency indexing and classic algorithms (BFS, Dijkstra, DFS, cycle detection) without sacrificing performance.

* **Pythonic Interaction**: Interact with data using familiar Python ``dict`` methods, list slicing, and set operations, avoiding complex SQL queries.

* **Dataclass Objects**: Read and write any ``@dataclass`` directly — ``jdb += user``, ``jdb['u1'] = user``, ``del jdb[user]``. The object is flattened into a plain ``dict`` rather than pickled, so records written from objects stay fully queryable, exportable, and language-neutral.

* **Advanced Serialization & Compression**: Combine formats (JSON, MsgPack, Pickle, YAML) with algorithms like LZ4, Zstandard, or Brotli to optimize your I/O and disk usage.

* **Pluggable Codec & Encryption**: Bring your own serialization or encryption logic via a simple ``dumps``/``loads`` interface — no forking required. Supports both a process-wide default and per-instance codecs (e.g. per-tenant encryption keys).

* **Powerful Query Engine**: Execute searches via Regex, Lambda filters, and rich operators (``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``, ...).

* **Operational Modes**: Supports In-Memory mode (``JMemFiles``) for high performance and Network mode (``JNetFiles``) to serve data over a network.

* **State Management**: Built-in "Time-Travel" allows you to track states, undo modifications (``unmodify()``), or recover deleted data (``unremove()``).

* **Data Migration**: Effortlessly migrate from SQLite or import/export via CSV, Parquet, INI, and TOML with simple commands. Parquet imports stream in constant memory via ``pyarrow`` record batches, so multi-GB files are no problem.

* **Time-Series Ready**: Native timestamping allows for efficient date-based slicing (e.g., ``jdb[yesterday:now]``).

* **Memory Caching**: Adjustable ``cache_limit`` to balance RAM usage and I/O speed.

* **Grouping & Namespaces**: Easily isolate and manage different data modules using groups.

* **Per-Record Flags**: Give any record file-system-like attributes with a ``chmod``-style syntax — read-only, append-only, hidden, uncached, no-history — plus symbolic links to other records or groups.

* **Concurrency Control**: Optimized for Many-Read / Single-Write environments using a robust file-locking and Lock mechanism.

