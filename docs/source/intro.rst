Introduction
============

**omni-json-db** is a high-performance, embedded database engine designed for Python developers. It bridges the gap between the extreme speed of a Key-Value store and the powerful querying capabilities of a document database.


Built for ultra-high throughput and thread-safety, **omni-json-db** leverages modern serialization (*JSON*, *MsgPack*, *marshal*, *pickle*, *YAML*) and compression to provide a storage layer that is often significantly faster than *SQLite* for *JSON*-heavy workloads. Whether you are building a local cache, a log aggregator, or a distributed microservice, **omni-json-db** provides the tools to handle data at scale with "Zero-Config" simplicity.

Unlike traditional *SQLite* or *NoSQL* databases, **omni-json-db** allows you to use native Python syntax (slicing, Lambdas, Regex, Set operations) to query and manipulate data. It also features built-in "Time-Travel", state rollbacks (Undo/Redo).

* **Schema-LESS**: Store complex, nested data without pre-defining tables.

* **Server-LESS**: Direct disk access without the overhead of a database server.

* **SQL-LESS**: Use native Python syntax, Regex, and Lambdas for data manipulation.


Features
--------

* **Deeply Pythonic**: Forget SQL! Interact with your database using standard Python ``dict`` methods, slicing, and even ``set`` operations. 

* **Dynamic Serialization & Advanced Compression**: Mix and match JSON(*orjson*), MsgPack(*ormsgpack*), Marshal, Pickle and YAML with advanced compression algorithms like LZ4, Zstandard (z1/z2/zs), Brotli, and Bzip2 to perfectly balance I/O speed and disk footprint.

* **Powerful Query Engine**: Powerful Query Engine: Search effortlessly using Regular Expressions (Regex), Lambda filters (``jdb[lambda k, v: v > 10]``), and rich condition operators (``EQ``, ``NE``, ``GT``, ``GTE`` ``LT``, ``LTE``, ``IN``, ``HAS``, ``RE``, ``RE2``, ``SIZE``, ``FUNC``, ``ANY``).

* **Memory Caching**: Adjustable ``cache_limit`` to balance RAM usage and I/O speed.

* **Network Mode** (``JNetFiles``): Transform a local **omni-json-db** instance into a networked service with a single command using ``run_files_server()``.

* **In-Memory Mode** (``JMemFiles``): Run the entire database in RAM for high performance (ideal for real-time caches or volatile session storage).

* **"Time-Travel" & Rollbacks**: The database tracks internal states, allowing you to undo modifications (``unmodify()``) or recover deleted data (``unremove()``). Accidentally deleted a record? One line of code brings it back.

* **Grouping & Namespaces**: Easily isolate and manage different data modules using groups.

* **Native CSV Support**: Built-in hooks for ``DictReader`` and ``DictWriter`` allow you to import massive datasets from *CSV* files or export your **omni-json-db** collections for analysis in *Excel* or *Pandas*.

* **Seamless Data Migration**: Import and export with a single line of code! The built-in conversion engine effortlessly transforms relational databases (*SQLite*) into *NoSQL* grouped structures. It also natively supports parsing structured configuration files (*INI*, *TOML*) and handling complex *CSV* datasets, making data migration and integration a breeze.

* **Time-Series Support:**: Every record is timestamped, unlocking powerful date-based slicing. For example, grab all records modified since yesterday with ``jdb[yesterday:now]``.

* **Concurrency Control**: Optimized for Many-Read / Single-Write environments using a robust file-locking and Lock mechanism.

