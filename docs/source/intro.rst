Introduction
============

**omni-json-db** is a high-performance, embedded database engine designed for Python developers. It bridges the gap between the extreme speed of a Key-Value store and the powerful querying capabilities of a document database.


Built for ultra-high throughput and thread-safety, **omni-json-db** leverages modern serialization (*JSON*, *MsgPack*, *marshal*, *pickle*, *YAML*) and compression to provide a storage layer that is often significantly faster than *SQLite* for *JSON*-heavy workloads. Whether you are building a local cache, a log aggregator, or a distributed microservice, **omni-json-db** provides the tools to handle data at scale with "Zero-Config" simplicity.

* **Schema-LESS**: Store complex, nested data without pre-defining tables.

* **Server-LESS**: Direct disk access without the overhead of a database server.

* **SQL-LESS**: Use native Python syntax, Regex, and Lambdas for data manipulation.


🤔 Why omni-json-db?
********************

Unlike traditional SQL or NoSQL databases, **omni-json-db** lets you use native
Python syntax — slicing, lambdas, regex, and ``set`` operations — to query and
manipulate data. It adds built-in "Time-Travel" (undo/redo), a property-graph
engine, and pluggable serialization/compression.

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

 **omni-json-db** has been tested with Python 3.7+ and PyPy3.


Features
--------
* **Native Graph Engine**: Transform your Key-Value store into a Property Graph. The ``GraphDb`` layer supports O(1) adjacency indexing and classic algorithms (BFS, Dijkstra, DFS, cycle detection) without sacrificing performance.

* **Pythonic Interaction**: Interact with data using familiar Python ``dict`` methods, list slicing, and set operations, avoiding complex SQL queries.

* **Advanced Serialization & Compression**: Combine formats (JSON, MsgPack, Pickle, YAML) with algorithms like LZ4, Zstandard, or Brotli to optimize your I/O and disk usage.

* **Powerful Query Engine**: Execute searches via Regex, Lambda filters, and rich operators (``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``, ...).

* **Operational Modes**: Supports In-Memory mode (``JMemFiles``) for high performance and Network mode (``JNetFiles``) to serve data over a network.

* **State Management**: Built-in "Time-Travel" allows you to track states, undo modifications (``unmodify()``), or recover deleted data (``unremove()``).

* **Data Migration**: Effortlessly migrate from SQLite or import/export via CSV, INI, and TOML with simple commands.

* **Time-Series Ready**: Native timestamping allows for efficient date-based slicing (e.g., ``jdb[yesterday:now]``).

* **Memory Caching**: Adjustable ``cache_limit`` to balance RAM usage and I/O speed.

* **Grouping & Namespaces**: Easily isolate and manage different data modules using groups.

* **Concurrency Control**: Optimized for Many-Read / Single-Write environments using a robust file-locking and Lock mechanism.

