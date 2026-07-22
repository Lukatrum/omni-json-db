|Version| |License| |Language1| |Language2| |Language3|

|Logo|

..

   A nimble squirrel swiftly gathers a golden forest’s worth of acorns!

|Build Status| |readthedocs| |Pylint| |Codacy| |Coverage|


|Python Version|

..

   If you find **omni-json-db** useful, please consider giving it a **⭐️**!


👉 Quick Links
**************

- `✨ Introduction`_
- `🤔 Why omni-json-db?`_
- `🚀 Features`_
- `🛠️ Quick Start`_
- `📝 Specifications`_
- `📊 Benchmarking`_
- `📄 Documentation <https://omni-json-db.readthedocs.io>`_
- `👥 Contributing`_
- `📄 License`_


✨ Introduction
****************
**omni-json-db** is a high-performance, embedded database engine designed for Python developers. It combines the raw speed of a Key-Value store with the flexible querying of a document database and the associative power of a graph database.

Built for high throughput and thread safety, **omni-json-db** utilizes modern serialization (e.g., *JSON*, *MsgPack*, *Pickle*) and efficient compression to provide a compact storage layer. Whether you are building a local cache, a log aggregator, or a complex knowledge graph, **omni-json-db** offers "Zero-Config" simplicity at scale.

* **Schema-LESS**: Store complex, nested data without pre-defining tables.
* **Server-LESS**: Access data directly on disk without a database server overhead.
* **SQL-LESS**: Manipulate data using standard Python syntax, Regex, and Lambdas.


🤔 Why omni-json-db?
********************

Unlike traditional SQL or NoSQL databases, **omni-json-db** allows you to query and manipulate data using native Python syntax—including slicing, lambdas, regex, and set operations. It also features built-in "Time-Travel" (undo/redo), a property-graph engine, and pluggable serialization.

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
| Relative speed 500K records [1]_ | 1.00x (baseline)  | 41.47x    | 60.95x    |  4.28x  | 0.94x      | 0.45x     | 0.13x     | 0.21x     |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+
| Relative speed 10M records [1]_  | 1.00x (baseline)  | N/A [2]_  | N/A [2]_  | 24.07x  | 1.31x      | 0.55x     | 0.16x     | 0.05x     |
+----------------------------------+-------------------+-----------+-----------+---------+------------+-----------+-----------+-----------+

.. [1] Lower is faster
.. [2] Impractically slow

 **omni-json-db** has been tested with Python 3.7+ and PyPy3. (~100% test coverage)
 
🚀 Features
***********
* **Native Graph Engine**: Transform your Key-Value store into a Property Graph. The ``GraphDb`` layer supports O(1) adjacency indexing and classic algorithms (BFS, Dijkstra, DFS, cycle detection) without sacrificing performance. [refer to `Graph Database`_]

* **Pythonic Interaction**: Interact with data using familiar Python ``dict`` methods, list slicing, and set operations, avoiding complex SQL queries. [refer to `Basic`_ + `Operator`_]

* **Advanced Serialization & Compression**: Combine formats (JSON, MsgPack, Pickle, YAML) with algorithms like LZ4, Zstandard, or Brotli to optimize your I/O and disk usage. [refer to `Change Type`_ + `Supported Data Formats`_ + `Supported Zip Formats`_]

* **Powerful Query Engine**: Execute searches via Regex, Lambda filters, and rich operators (``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``, ...). [refer to `Query Engine`_ + `More Query Examples`_ + `Pythonic Query Examples`_]

* **Operational Modes**: Supports In-Memory mode (``JMemFiles``) for high performance and Network mode (``JNetFiles``) to serve data over a network. [refer to `In-memory Mode`_ + `Network Mode`_ ]

*  **State Management**: Built-in "Time-Travel" allows you to track states, undo modifications (``unmodify()``), or recover deleted data (``unremove()``). [refer to `Unremove & Unmodify`_ + `Backup & Restore`_]

* **Data Migration**: Effortlessly migrate from SQLite or import/export via CSV, INI, and TOML with simple commands. [refer to `CSV Import / Export`_ + `SQLite Import`_ + `INI / TOML Import`_]

* **Time-Series Ready**: Native timestamping allows for efficient date-based slicing (e.g., ``jdb[yesterday:now]``). [refer to `Time-Series`_]

* **Memory Caching**: Adjustable ``cache_limit`` to balance RAM usage and I/O speed. [refer to `Supported Key Table Formats`_]

* **Grouping & Namespaces**: Easily isolate and manage different data modules using groups. [refer to `Groups Mode`_]

* **Concurrency Control**: Optimized for Many-Read / Single-Write environments using a robust file-locking and Lock mechanism. [refer to `Advanced`_]


🛠️ Quick Start
**************

Installation
------------

.. code-block:: bash

   pip install omni-json-db


Basic
-----

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Json+mSgpack without compression
   jdb = JDb("example.jdb")

   # Store data
   jdb["user1"] = {"name" : "Ryan", "role": "Developer"}
   
   # Retrieve data
   user = jdb["user1"]
   print(user["name"], user["role"]) # Output: Ryan Developer
   
All standard ``dict`` methods work: ``keys()``, ``values()``, ``items()``, ``get()``,  ``pop()``, ``setdefault()``, ``update()``.

In-Memory Mode
---------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+mSgpack without compression
   jdb1 = JDb()

   # Store data
   jdb1 += {"user1" : {"name" : "Joe", "role": "Senior Developer"}}
   
   # Retrieve data
   print(jdb1["user1"]["name"]) # Output: Joe

   # create 2nd JDb sharing same memory
   jdb2 = JDb(jdb1)

   # Store data to 2nd JDb
   jdb2["user2"] = {"name" : "Kathy", "role": "CEO"}

   # newly inserted data (by 2nd JDb)
   print(jdb1["user2"]["name"]) # Output: Kathy

Query Engine
------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+Marshal with no compression
   jdb = JDb(data_type="J+M")
   
   # insert many records without key
   jdb += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]
   
   # get all records from database
   print(jdb[:]) # print all records from jdb

   # show table
   jdb.show()

   # Use FUNCTION to find record(s) matching the name 'John'
   matches = jdb.find(FUNC=lambda key,val: val['name'] == 'John') 
   print(matches) # Output : {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}}
   
   # Use Regex to find record(s) matching the name 'John' or 'Bob'
   matches = jdb.find(RE='John|Bob')
   print(matches) # {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}, '2': {'name': 'Bob', 'age': 42}}

Condition operators: ``EQ``, ``NE``, ``GT``, ``LT``, ``GTE``, ``LTE``, ``HAS``, ``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOR``, ``NOT``, ``NAND``, ``SIZE``, ``ANY``, ``ALL``, ``NONE``, ``IHAS``, ``NHAS``,  ``EXISTS``, ``TYPE``, ``MOD``, ``BETWEEN``, ``NEAR``, ``MATCH``, ``SW``, ``EW``, ``NIN``, ``ANYIN``.

Transform operators: ``ABS``, ``CEIL``, ``FLOOR``, ``ROUND``, ``FLOAT``, ``INT``, ``NEG``, ``STR``, ``AVG``, ``STD``, ``MAX``, ``MID``, ``MIN``, ``SUM``, ``FIRST``, ``LAST``, ``LEN``, ``SORT``, ``UNIQUE``, ``LOWER``, ``UPPER``, ``STRIP``.

Know `More Query Examples`_ or `Pythonic Query Examples`_

Unremove & Unmodify
-------------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Json+Pickle with zstandard compression
   jdb = JDb("fruit.jdb", data_type="J+P", zip_type='zs')

   # add key
   jdb["apple"] = "red"

   # modify key
   jdb["apple"] = "blue" 

   # unmodify key (equivalent to jdb.unmodify())
   jdb.revert("apple")
   assert jdb["apple"] == 'red'

   # remove key
   del jdb["apple"] 
   assert "apple" not in jdb

   # unremove key (equivalent to jdb.unremove())
   jdb.revert("apple")
   assert jdb["apple"] == "red"

Backup & Restore
----------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is mSgpack+Json with Bzip2 compression
   jdb = JDb("fruit.jdb", data_type="S+J", zip_type='bz')

   # Add fruit to jdb
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits
   assert jdb == fruits

   # backup jdb to bak folder = ./bak/fruit.jdb
   jdb_bak = jdb.backup(folder='bak')
   assert jdb_bak == jdb

   # del all jdb data
   del jdb[fruits]
   assert len(jdb) == 0

   # restore bak folder to jdb
   jdb.restore(folder='bak')
   assert jdb == fruits

Groups Mode
-----------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Json+mSgpack with no compression
   jdb = JDb('fruit_group.jdb')

   # add red group
   r_jdb = jdb.add_group('red')
   assert r_jdb is jdb['red']

   # add yellow group
   y_jdb = jdb.add_group('yellow')
   assert y_jdb is jdb['yellow']

   # add fruits to red group
   r_jdb += {'apple': {'qty':1}, 'tomato': {'qty':2}}

   # add fruits to yellow group
   y_jdb += {'banana': {'qty':4}, 'lemon': {'qty':6}, 'mango': {'qty':8}}

   # read group records
   print(jdb['red']['apple']['qty'])   # Output: 1
   print(jdb['red:::apple'])           # Output: {'red:::apple': {'qty': 1}}
   print(jdb['yellow:::banana'])       # Output: {'yellow:::banana': {'qty': 4}}

   # find fruits which contain 'a' from all groups
   matches = jdb.find(r':::a')
   print(matches) # Output: ['red:::apple', 'red:::tomato', 'yellow:::banana', 'yellow:::mango']


Graph Database
--------------
**omni-json-db** natively supports Property Graph structures with the ``GraphDb`` class. You can easily manage nodes, edges, and run complex graph algorithms out of the box.

.. code-block:: python

   from omni_json_db import GraphDb, Query

   # Initialize the graph database in memory (or from a file)
   db = GraphDb()

   # 1. Add Nodes with Schema-less Properties
   db.add_node('Alice', age=25, role='admin')
   db.add_node('Bob', age=30, role='user')
   db.add_node('Charlie', age=35, role='user')

   # 2. Add Edges (Directed or Undirected) with Properties
   db.add_edge('Alice', 'Bob', directed=True, weight=1.5, relation='friend')
   db.add_edge('Bob', 'Charlie', directed=True, weight=2.0, relation='colleague')
   db.add_edge('Charlie', 'Alice', directed=False, weight=0.5) # Undirected edge

   # 3. Neighborhood & Adjacency queries (O(1) lookups)
   print(db.neighbors('Alice')) 
   # Output: {'Bob', 'Charlie'}
   
   print(db.degree('Alice'))
   # Output: {'in': 0, 'out': 1, 'undirected': 1, 'total': 2}

   # 4. Classic Graph Algorithms Built-in
   # Find the shortest path using Dijkstra based on edge weights
   dist, path = db.dijkstra_shortest_path('Alice', 'Charlie', weight_key='weight')
   print(f"Distance: {dist}, Path: {path}") 
   # Output: Distance: 0.5, Path: ['Alice', 'Charlie']

   # Detect cycles in the graph (Alice -> Bob -> Charlie -> Alice)
   print(db.is_cyclic()) 
   # Output: True 

   # 5. Seamless Query Engine Integration
   # You can still use the powerful Query object to filter nodes/edges!
   q = Query()
   admin_nodes = db.find_nodes(q.role == 'admin')
   print(list(admin_nodes)) 
   # Output: ['Alice']

   # 6. Cascade Deletion
   # Removing a node automatically cleans up all connected edges
   db.remove_node('Bob')
   print(db.has_node('Bob')) # Output: False
   print(db.get_edge('Alice', 'Bob', directed=True)) # Output: None


CSV Import / Export
-------------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+Json with no compression      
   jdb1 = JDb(data_type="J+J")

   # insert value without key
   jdb1 += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]
   
   # export the data to CSV
   jdb1.to_csv('example.csv')

   # show table
   jdb1.show()

   # create another JDb in memory
   jdb2 = JDb()
   
   # import the data from CSV
   jdb2.from_csv('example.csv')
   print(jdb2.find(RE='Bob')) # Output: {'2': {'name': 'Bob', 'age': 42}}

   # show table
   jdb2.show(RE='Bob')

INI / TOML Import
-----------------

.. code-block:: python
   
   from omni_json_db import JDb
   import io

   jdb = JDb()

   # --- Load INI Format ---
   ini_data = """
   [server]
   host = 127.0.0.1
   port = 8080
   """

   jdb.from_ini(io.StringIO(ini_data)) # Also supports direct file paths like 'config.ini'
   print(jdb['server/host']) # Output: 127.0.0.1

   # --- Load TOML Format ---
   toml_data = """
   app_name = "Omni Test"
   [network]
   ip = "192.168.1.1"
   port = 8181
   """
   
   jdb.from_toml(io.StringIO(toml_data))

   print(jdb['/app_name'])    # Output: Omni Test
   print(jdb['network/ip'])   # Output: 192.168.1.1

SQLite Import
-------------

Step 1: Prepare *sample.sqlite*

.. code-block:: python

   import sqlite3
   conn = sqlite3.connect('sample.sql')
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

Step 2: Import to ``JDb``

.. code-block:: python

   from omni_json_db import JDb   
   jdb = JDb("migrated_data.jdb")

   # Load an entire SQLite database with one line of code
   jdb.from_sqlite('sample.sqlite')

   # SQLite tables (e.g., 'projects' and 'project_logs') automatically become groups
   projects = jdb['projects']
   logs = jdb['project_logs']

   # Query relational data using the NoSQL interface
   print(projects[3]['name'])  # Get the name of the project with ID 3
   print(len(logs))            # Get the total number of logs

   # Combine with powerful Lambda queries to find logs for a specific project
   project_3_logs = logs.find(FUNC=lambda val: val['project_id'] == 3)

Network Mode
------------

**Server side**

.. code-block:: python
   
   from omni_json_db import JDb, run_files_server   
   
   jdb = JDb('storage.jdb')

   # equivalent to: files='storage.jdb'
   run_files_server(host='127.0.0.1', port=59898, files=jdb)

   # write key to JDb
   jdb['remote-key'] = 'secret'

**Client side**

.. code-block:: python

   from omni_json_db import JDb

   # connect to files server
   jdb = JDb('127.0.0.1:59898')

   # read remote key from JDb
   print(jdb['remote-key']) # Output: secret

Change Type
-----------

.. code-block:: python

   from omni_json_db import JDb

   # Initialize the database in memory
   # Key-Value is Json+Json with no compression
   jdb = JDb(data_type='J+J')

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # add all fruits to database
   jdb += fruits
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: J+J no

   # change data_type to 'S+S' and zip_type to 'lz'
   jdb.upgrade(data_type='S+S', zip_type='lz')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: S+S lz

   # only change KEY type from 'S' to 'J'
   jdb.change_KEY('J')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: J+S lz

Time-Series
------------

.. code-block:: python

   from omni_json_db import JDb
   import datetime as dt

   # Initialize the database in memory
   # Key+Value is Json+Json with Gzip compression
   # using BTree as Key Table for better memory usage
   jdb = JDb(data_type="J+J(gz)", key_limit="bt")

   # insert data
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits 

   # datetime for create date, date for modify date
   now = dt.datetime.now()
   today = now.date()
   
   # find create date: date == now
   matches = jdb[now]
   assert matches == fruits

   # find create date: date >= now
   matches = jdb[now:]
   assert matches == fruits

   # find create date: date < now
   matches = jdb[:now]
   assert len(matches) == 0

   # find create date: now <= date <= now+1
   next_date = now + dt.timedelta(days=1)
   matches = jdb[now:next_date]
   assert matches == fruits

   prev_date = now - dt.timedelta(days=1)
   prev_week = now - dt.timedelta(days=7)
   
   # change key create date
   jdb.keys['apple', 'tomato'] = prev_date
   jdb.keys['mango'] = prev_week
   assert jdb[prev_date] == {'apple':'red', 'tomato':'red'}
   assert jdb[prev_week] == {'mango':'yellow'}

   # find create date: date == now
   matches = jdb[now]
   assert set(matches) == {'banana', 'lemon'}

   # find create date: date < now
   matches = jdb[:now]
   assert set(matches) == {'apple', 'mango', 'tomato'}

   # find modify date: date == today
   matches = jdb[today]
   assert matches == fruits

   # change key modify date + create date
   new_modify_date = prev_date.date()
   new_create_date = prev_week.date()
   assert new_modify_date >= new_create_date
   jdb.keys['lemon'] = f'{new_modify_date} {new_create_date}'
   
   # find modify date: date == today   
   matches = jdb[today]
   assert set(matches) == {'apple', 'banana', 'mango', 'tomato'}

   # find modify date: date == prev_date
   matches = jdb[prev_date.date()]
   assert set(matches) == {'lemon'}

   # change all keys create date
   jdb.keys[:] = today
   assert jdb[today] == fruits

Operator
--------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key+Value is mSgpack+mSgpack with lz4 compression
   jdb = JDb(data_type="S+S(lz)")

   # [1] KEY+VAL operators
   # <jdb += data> == jdb.update(data)
   data = {f'key{v}':v for v in range(100)}   
   jdb += data
   assert len(jdb) == 100

   # <jdb == data>
   assert jdb == data

   # <jdb |= ..> == jdb.insert(..)
   jdb |= {f'key{v}':v+1 for v in range(102)}
   assert jdb['key100'] == 101
   assert jdb[-2.:] == {'key100':101, 'key101':102} # get last two modified records
   assert jdb[(f'key{v}' for v in range(100))] == data # equivalent to jdb[data] == data

   # <jdb -= ..> == jdb.remove(..)
   jdb -= ['key100', 'key101', 'key102', 'key103']
   assert jdb == data

   # <jdb &= ..> == jdb.replace(..)
   jdb &= {f'key{v}':v+1 for v in range(200)}
   assert jdb == {f'key{v}':v+1 for v in range(100)}

   # <jdb ^= ..> == jdb.unmodify(..)
   jdb ^= {f'key{v}' for v in range(100)} # equivalent to jdb ^= data
   assert jdb == data

   # <jdb[:] = ..> == jdb.update(..)
   jdb[:] = 0 # set all records to zero
   assert jdb == {f'key{v}':0 for v in range(100)}
   assert jdb.find(NE=0) == {}

   # remove all records
   jdb -= jdb # equivalent to del jdb[:]
   assert len(jdb) == 0

   # <jdb ^= ..> == jdb.unremove(..)
   jdb ^= {f'key{v}' for v in range(100)} # equivalent to jdb ^= data
   assert all(val == 0 for key,val in jdb.items())

   # lambda VALUE operation
   jdb[:] = lambda key,val: int(key.replace('key', '')) + val
   assert jdb == data

   # <del jdb[..]> == jdb.remove_fast(..)
   del jdb[data] # equivalent to del jdb[:]

   # unremove all data
   jdb ^= data
   assert jdb == data

   # <jdb[..]> == jdb.get_n(..) or jdb.get_all()
   matches = jdb[('key2', 'key22', 'key44', 'key111')]
   assert matches == {'key2':2, 'key22':22, 'key44':44}

   # lambda KEY operation
   matches = jdb[lambda key:key.endswith('1')]
   assert set(matches) == {'key1', 'key11', 'key21', 'key31', 'key41', 'key51', 'key61', 'key71', 'key81', 'key91'}

   # set all matched records to -1
   jdb[matches] = -1
   matches_2 = jdb[lambda key,val: val == -1]
   assert set(matches) == set(matches_2)
   assert matches_2 == jdb.find(EQ=-1)
   assert matches_2 == jdb.find(FUNC=lambda val: val == -1)

   # RE search
   matches_3 = jdb[::r'1$']
   assert matches_2 == matches_3

   # unmodify
   jdb ^= matches
   assert jdb == data

   # [2] KEY operators
   # <jdb & {..}> == jdb.intersection(..)
   matches = jdb & {f'key{v}' for v in range(98, 120)}
   assert matches == {'key98', 'key99'}

   # <{..} & jdb> == {..}.intersection(jdb)
   matches_2 = {f'key{v}' for v in range(98, 120)} & jdb
   assert matches == matches_2
   
   # <jdb | {..}> == jdb.union(..)
   matches = jdb | {f'key{v}' for v in range(10, 120)}
   assert matches == {f'key{v}' for v in range(0, 120)}

   # <{..} | jdb> == {..}.union(jdb)
   matches_2 = {f'key{v}' for v in range(10, 120)} | jdb
   assert matches == matches_2
   
   # <jdb + {..}> == jdb.union(..)
   matches = jdb + {f'key{v}' for v in range(10, 120)}
   assert matches == matches_2

   # <{..} + jdb> == {..}.union(jdb)   
   matches_2 = {f'key{v}' for v in range(10, 120)} + jdb
   assert matches == matches_2
   
   # <jdb - {..}> == jdb.difference(..)
   matches = jdb - {f'key{v}' for v in range(0, 98)}
   assert matches == {'key98', 'key99'}

   # <{..} - jdb> == {..}.difference(jdb)
   matches = {f'key{v}' for v in range(2, 102)} - jdb
   assert matches == {'key100', 'key101'}

   # <jdb ^ {..}> == jdb.non_intersection(..)
   matches = jdb ^ {f'key{v}' for v in range(1, 101)}
   assert matches == {'key0', 'key100'}

   # <{..} ^ jdb> == {..}.non_intersection(jdb)
   matches_2 = {f'key{v}' for v in range(1, 101)} ^ jdb
   assert matches == matches_2

   # <.. in jdb> == jdb.has_all(..)
   assert 'key10' in jdb
   assert {'key10', 'key90'} in jdb
   assert {'key10', 'key90', 'key110', 'key190'} not in jdb
   assert jdb.has('key10')
   assert jdb.has_all('key10')
   assert jdb.has_any('key10')
   assert jdb.has_all({'key10', 'key90'})
   assert jdb.has_any({'key10', 'key90', 'key110', 'key190'})
   assert jdb.is_disjoint({'key110', 'key190'})

All standard ``set`` methods work: ``union()``, ``intersection()``, ``difference()``, ``isdisjoint()``, ``issubset()``, ``issuperset()``.

More Query Examples
--------------------
Below are examples of how to utilize the various parameters and NoSQL syntax.

.. code-block:: python

   from omni_json_db import JDb
   import re

   # Initialize an in-memory database
   jdb = JDb()

   # Sample user records
   users = {
      'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
      'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
      'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
      'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # Insert data 
   jdb += users

   # 1. Exact Match & Global Search (ANY, RE, RE2)
   #----------------------------------------------------------
   # Find users where any attribute exactly matches 'Alice'
   res = jdb.find(ANY='Alice')
   assert list(res) == ['user_1']

   res2 = jdb.find(vals={'name': 'Alice'})
   assert res == res2

   # converts values into JSON string format for searching.
   # Find any record that has the string 'designer' inside it
   res = jdb.find(RE=r'designer') # vals={'$re':r'designer'}
   assert list(res) == ['user_4']

   # RE2 removes JSON symbols (,[]{}") before searching
   res = jdb.find(RE2=r'role:designer')
   assert list(res) == ['user_4']

   res2 = jdb.show(vals={'role.$re': r'd.+ner'}) # {'role': re.compile(r'd.+ner')}
   assert res == res2
   
   # 2. Relational & Conditional Operators (vals)
   #----------------------------------------------------------
   # Age is greater than or equal to 30
   res = jdb.find(vals={'age': {'$gte': 30}}) # find(ANY={'$gte': 30})
   assert list(res) == ['user_1', 'user_3']

   res2 = jdb.find(vals={'age.$ge': 30})
   assert res == res2

   # Age is strictly less than 30
   res = jdb.find(vals={'age': {'$lt': 30}}) # find(ANY={'$lt': 30})
   assert list(res) == ['user_2', 'user_4']

   res2 = jdb.find(vals={'age.$lt': 30})
   assert res == res2

   # Role is either 'admin' or 'designer'
   res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
   assert list(res) == ['user_1', 'user_4']

   res2 = jdb.find(vals={'role': ['admin', 'designer']}) # {'role.$in': ['admin', 'designer']}
   assert res == res2

   # tags contains 'python'
   res = jdb.find(vals={'tags': {'$has': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   res2 = jdb.find(vals={'tags.$has': 'python'})
   assert res == res2

   # Age is NOT 30
   res = jdb.find(vals={'age': {'$ne': 30}}) # find(ANY={'$ne': 30})
   assert list(res) == ['user_2', 'user_3', 'user_4']

   res2 = jdb.find(vals={'!age': 30}) # {'age.$ne': 30}
   assert res == res2

   # Age is 28
   res = jdb.find(vals={'age': {'$eq': 28}}) # find(ANY={'$eq': 28})
   assert list(res) == ['user_4']

   res2 = jdb.find(vals={'age': 28})
   assert res == res2

   # 40 >= Age > 25
   res = jdb.find(vals={'age': {'$gt': 25, '$lte': 40}}) # {'age.$gt':25, 'age.$lte':40}
   assert list(res) == ['user_1', 'user_3', 'user_4']

   res2 = jdb.show(vals={'age.$between': (26, 40)})
   assert res == res2

   # 3. Logical Grouping (AND, OR, NOR, NOT)
   #----------------------------------------------------------
   # Age >= 25 AND Age <= 30
   res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}])
   assert list(res) == ['user_1', 'user_2', 'user_4']

   res2 = jdb.find(vals={'age.$ge': 25, 'age.$le': 30})
   assert res == res2
   
   # Role is 'admin' OR Age > 30
   res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
   assert list(res) == ['user_1', 'user_3']

   res2 = jdb.find(OR=[{'r*e': 'admin'}, {'age.$gt': 30}])
   assert res == res2

   # Role is not 'admin' AND Age <= 30
   res = jdb.find(NOR=[{'role': 'admin'}, {'age.$gt': 30}])
   assert list(res) == ['user_2', 'user_4']

   # User is NOT a developer
   res = jdb.find(NOT={'role': 'developer'})
   assert list(res) == ['user_1', 'user_4']

   res2 = jdb.find(vals={'!role': 'developer'})
   assert res == res2

   # (Role is 'admin' OR Age > 30) AND 'linux' not in tags
   res = jdb.find(AND=[
      {'$or': [
         {'role': 'admin'},
         {'age': {'$gt': 30}}
      ]},
      {'$not': {'tags': {'$has': 'linux'}}}
   ])
   assert list(res) == ['user_1']

   res2 = jdb.show(vals={'$or': [{'role': 'admin'}, {'age.$gt': 30}], '!tags.$has': 'linux'})
   assert res == res2

   # 4. Regular Expressions (RE, RE2, re.compile)
   #----------------------------------------------------------
   # Values matching an email domain regex
   res = jdb.find(vals={'email': re.compile(r'.@example.com')})
   assert list(res) == ['user_1']

   # Find users where any attribute exactly matches regex
   res = jdb.find(ANY=re.compile(r'.@example.com'))
   assert list(res) == ['user_1']

   # Global regex search for strings containing 'li' (matches 'Alice', 'Charlie', 'linux')
   res = jdb.find(RE=r'li[a-z]')
   assert list(res) == ['user_1', 'user_3']

   # Match specific Database Keys using compiled regex (e.g., matching 'user_1', 'user_2')
   res = jdb.show(re.compile(r'^user_[1-2]$'))
   assert list(res) == ['user_1', 'user_2']

   # 5. Array / List Operations
   #----------------------------------------------------------
   # Users with exactly 2 tags in their list
   res = jdb.find(vals={'tags': {'$size': 2}})
   assert list(res) == ['user_1', 'user_2', 'user_4']

   res2 = jdb.find(vals={'tags.$size': 2})
   assert res == res2

   # Users whose FIRST tag (index 0) is 'python'
   res = jdb.find(vals={'tags': {'$0': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   res2 = jdb.show(vals={'tags.0': 'python'})
   assert res == res2

   # 6. Lambda / Custom Functions (FUNC) & Pagination (limit)
   #----------------------------------------------------------
   # Pass a lambda to evaluate both the key and the value dynamically
   # Example: Find the first users whose age is an even number
   res = jdb.find(
       FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0, 
      limit=1
   )
   assert list(res) == ['user_1']

   res2 = jdb.find(vals={'age.$mod': (2, 0)}, limit=1)
   assert res == res2

   # Users with email
   res = jdb.find(vals={'email': lambda v: v != ''})
   assert list(res) == ['user_1', 'user_4']

   res2 = jdb.find(EXISTS='email')
   assert res == res2

   # Users without email
   res = jdb.find(NOT={'email': lambda v: v != ''})
   assert list(res) == ['user_2', 'user_3']

   res2 = jdb.find(vals={'!$exists': 'email'})
   assert res == res2

   # For primitive stored values (non-nested), you can use quick keyword arguments:
   jdb['simple_counter'] = 50
   res = jdb.find(EQ=50)
   assert list(res) == ['simple_counter']

   res = jdb.show(IN=[40, 50]) # Value in list
   assert list(res) == ['simple_counter']

Operators Reference
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 30 30
   :header-rows: 1

   * - Operator
     - Description
     - Example Usage     
   * - ``.``  ``|``  ``/``
     - Accesses nested fields within a document using a deep path.
     - ``{'user.profile.age': {'$gt': 20}}``, ``{'user|tags|0': 'db'}``
   * - ``?``
     - [Single-char Wildcard] Matches exactly one single character within a key name.
     - ``{'user?.prof???.?ge': {'$gt': 20}}``, ``{'user?.tags.?': 'db'}``
   * - ``*``
     - [Wildcard] Matches any key at the current level in the document structure. 
     - ``{'users.*.role': 'admin'}``, ``{'user*|t*gs|*': 'db'}``
   * - ``**``
     - [Recursive Wildcard] Recursively searches and matches the specified key or field at any depth level within the document.
     - ``{'**.role': 'admin'}``, ``{'meta.**': 'database'}``
   * -
     -
     -
   * - ``$0``, ``$1``, ...
     - Matches the element exactly at the specified index (0, 1...) of an array.
     - ``{'$0': 'python'}``
   * - ``$date`` / ``_date``
     - Targets the database record's internal date for condition matching.
     - ``{'$date': {'$lt': date(2001, 1, 1)}}``, ``{'_date': date(2011,12,1)}``
   * - ``$key`` / ``_id``
     - Targets the database record's dictionary key/ID for condition matching.
     - ``{'$key': 'user_1'}``, ``{'_id': 'user_1'}``   
   * -
     -
     -
   * - ``$not`` / ``!``
     - Inverts the effect of a query expression (Logical NOT).
     - ``{'$not': {'tags': {'$has': 'linux'}}}``, ``{'!tags': {'$has': 'linux'}}``, ``{'tags': {'!$has': 'linux'}}``
   * - ``$and``
     - Joins query clauses with a logical AND.
     - ``{'$and': [{'$has':'python'}, {'$has':'linux'}]}``
   * - ``$nand`` / ``!$and``
     - Joins query clauses with a logical NAND (Not AND).
     - ``{'$nand': [{'$has':'python'}, {'$has':'linux'}]}``
   * - ``$or``
     - Joins query clauses with a logical OR.
     - ``{'$or': [{'$eq': 2000}, {'$eq': 2010}]}``
   * - ``$nor`` / ``!$or``
     - Joins query clauses with a logical NOR.
     - ``{'$nor': [{'$eq': 2000}, {'$eq': 2010}]}``
   * -
     -
     -      
   * - ``$all``
     - Matches if ALL elements in the value array/iterable match the condition.
     - ``{'$all': {'$ne': 0}}``
   * - ``$any``
     - Matches if ANY element in the value array/iterable matches the condition.
     - ``{'$any': 'python'}``
   * - ``$none`` / ``!$any``
     - Matches if NO elements in the value array/iterable match the condition.
     - ``{'$none': {'age': 30}}``
   * - ``$func``
     - Evaluates a custom lambda function on the field to determine match.
     - ``{'$func': lambda x: x > 0}``   
   * -
     -
     -
   * - ``$eq``
     - Matches values that are exactly equal to the specified value.
     - ``{'$eq': 28}``
   * - ``!$eq`` / ``$ne``
     - Matches values that are not equal to the specified value.
     - ``{'$ne': 30}``,  ``{'!$eq': 30}``
   * - ``$gt``
     - Matches values strictly greater than the specified value.
     - ``{'$gt': 25}``
   * - ``$gte`` / ``$ge``
     - Matches values greater than or equal to the specified value.
     - ``{'$gte': 30}``
   * - ``$lt``
     - Matches values strictly less than the specified value.
     - ``{'$lt': 30}``
   * - ``$lte`` / ``$le``
     - Matches values less than or equal to the specified value.
     - ``{'$lte': 40}``
   * -
     -
     -
   * - ``$in``
     - Matches if the value is any of the elements specified in an array/set.
     - ``{'$in': ['admin', 'designer']}``
   * - ``!$in`` / ``$nin``
     - Matches if the value does NOT exist in the specified array/set.
     - ``{'$nin': ['python', 'db']}``, ``{'!$in': ['python', 'db']}``
   * - ``$anyin``
     - Matches if ANY element in the value array/iterable exists in the specified array/set.
     - ``{'$anyin': ['admin', 'manager']}``
   * - ``$between``
     - Matches values within a specified inclusive range (min, max).
     - ``{'$between': (26, 40)}``
   * - ``!$between``
     - Matches values strictly outside a specified range.
     - ``{'!$between': (26, 40)}``
   * - ``$near``
     - Matches numeric/date values within a tolerance range (target, offset).
     - ``{'$near': (20, 9)}``
   * - ``$mod``
     - Matches values where value % divisor == remainder (passed as a tuple).
     - ``{'$mod': (10, 5)}``
   * -
     -
     -
   * - ``$has``
     - Matches arrays or strings containing the specified element/substring.
     - ``{'$has': 'python'}``
   * - ``!$has`` / ``$nhas``
     - Matches if the specified element or substring is NOT contained.
     - ``{'$nhas': 'r_1'}``, ``{'!$has': 'r_1'}``
   * - ``$ihas``
     - Case-insensitive match for arrays or strings containing the specified element/substring.
     - ``{'$ihas': 'UseR_'}``   
   * - ``$re`` / ``$regex``
     - Matches string values using a Regular Expression.
     - ``{'$re': r'li[a-z]'}``, ``{'$re': re.compile(r'li[a-z]')}``
   * - ``$re2``
     - Matches using Regex after stripping JSON formatting symbols (``[]{}""``) from the string.
     - ``{'$re2': r'role:admin'}``
   * - ``$ew``
     - Matches string values that end with a specified substring.
     - ``{'$ew': '_suffix'}``
   * - ``$sw``
     - Matches string values that start with a specified substring.
     - ``{'$sw': 'prefix_'}``
   * - 
     -
     -
   * - ``$exists``
     - Matches documents that have the specified field/key.
     - ``{'$exists': ['age', 'tags']}``, ``{'$exists': 'tags'}``
   * - ``!$exists``
     - Matches documents that lack the specified field/key.
     - ``{'!$exists': 'age'}``
   * - ``$size``
     - Matches if the size/length of an array/string equals the specified value.
     - ``{'$size': [1,2,3]}``
   * - ``!$size``
     - Matches if the size/length does NOT equal the specified value(s).
     - ``{'!$size': [1,2,3]}``
   * - ``$type``
     - Matches if the value is of the specified Python variable type.
     - ``{'$type': list}``
   * - 
     -
     -   
   * - ``$abs``
     - Takes the absolute value of a number before comparing.
     - ``{'$abs': 3.14}``
   * - ``$ceil``
     - Takes the ceiling (math.ceil) of a number before comparing.
     - ``{'$ceil': 2}``
   * - ``$floor``
     - Takes the floor (math.floor) of a number before comparing.
     - ``{'$floor': 2}``
   * - ``$round``
     - Round a number before comparing.
     - ``{'$round': 2}``
   * - 
     -
     -
   * - ``$float``
     - Casts the value to a float before comparing.
     - ``{'$float': 1.0}``
   * - ``$int``
     - Casts the value to an integer before comparing.
     - ``{'$int': 1.0}``
   * - ``$neg``
     - Negates the value (``-val``) before comparing.
     - ``{'$neg': -1.2}``
   * - ``$str``
     - Casts the value to a string before comparing.
     - ``{'$str': '1.2'}``
   * - 
     -
     -
   * - ``$avg``
     - Calculates the arithmetic mean of an iterable before comparing.
     - ``{'$avg': 2.0}``
   * - ``$std``
     - Calculates the population standard deviation of an iterable before comparing.
     - ``{'$std': 2.0}``
   * - ``$max``
     - Finds the maximum value in an iterable before comparing.
     - ``{'$max': 4}``
   * - ``$mid``
     - Extracts the middle element or character (index ``len//2``) before comparing.
     - ``{'$mid': 4}``
   * - ``$min``
     - Finds the minimum value in an iterable before comparing.
     - ``{'$min': 1}``
   * - ``$sum``
     - Calculates the sum of an iterable before comparing.
     - ``{'$sum': 8}``
   * - 
     -
     -
   * - ``$first``
     - Extracts the first item or character before comparing.
     - ``{'$first': 1}``
   * - ``$flat``
     - Flattens a nested iterable before comparing.
     - ``{'$flat': [1,2,2,3]}``
   * - ``$last``
     - Extracts the last item or character before comparing.
     - ``{'$last': 3}``
   * - ``$len``
     - Calculates the length of an array or string before comparing.
     - ``{'$len': 3}``
   * - ``$sort``
     - Sorts the iterable values before comparing.
     - ``{'$sort': [1,2,3]}``
   * - ``$unique``
     - Performs order-preserving deduplication on an iterable before comparing.
     - ``{'$unique': [2,3,1]}``
   * - 
     -
     -
   * - ``$lower``
     - Converts a string to lowercase before comparing.
     - ``{'$lower': 'alice'}``
   * - ``$upper``
     - Converts a string to uppercase before comparing.
     - ``{'$upper': 'ALICE'}``
   * - ``$strip``
     - Strips leading and trailing whitespaces from a string before comparing.
     - ``{'$strip': 'hi'}``
   
Pythonic Query Examples
-------------------------
For developers who prefer a Pythonic and object-oriented syntax for filtering data (similar to the **TinyDB** experience), ``omni-json-db`` provides the ``Query`` object. You can elegantly use native Python operators (e.g., ``==``, ``>``, ``&``, ``|``, ``~``) and chained methods to construct complex search conditions.

.. code-block:: python

   from omni_json_db import JDb, Query

   # 1. Initialize database and add test data
   jdb = JDb()
   jdb += {
       'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
       'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
       'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
       'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # 2. Create a Query instance
   User = Query()

   # Basic Comparison: Find users older than 28
   res = jdb.find(User.age > 28)
   assert set(res) == {'user_1', 'user_3'}

   # Logical Combinations (AND & OR): Find developers under 30 OR admins
   res = jdb.find((User.role == 'developer') & (User.age < 30) | (User.role == 'admin'))
   assert set(res) == {'user_1', 'user_2'}

   # Array Query: Find users whose tags include 'python'
   res = jdb.find(User.tags.has('python'))
   assert set(res) == {'user_1', 'user_3'}

   # Path Wildcard: Regex search across all fields recursively (Find email containing example.com)
   res = jdb.find(User['**'].matches(r'.@example\.com'))
   assert set(res) == {'user_1'}

   # Advanced Filters: Find users who DO NOT have an 'email' field (~ is the NOT operator)
   res = jdb.find(~User.exists('email'))
   assert set(res) == {'user_2', 'user_3'}

   # Lambda Test: Find users whose age is an even number
   res = jdb.find(User.age.test(lambda age: age % 2 == 0), sort=User.name, reverse=True)
   assert set(res) == {'user_1', 'user_4'}

   # rename admin to Administrator
   res = jdb.update_if(User.role == 'admin', {'role': 'Administrator'})
   assert res == 1 and (User.role == 'Administrator') in jdb

   # sorted by user name
   res = jdb.show(sort=User.name, reverse=True)
   assert res == jdb

   # grouped by user role
   res = jdb.show(group_by=User.role) # jdb.show(group_by='role')
   assert 'developer' in res

   res = jdb.show(group_by={'role':['name', 'age.$avg']})
   assert 'developer' in res

Methods & Operators Reference
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
.. list-table::
   :widths: 20 40 30
   :header-rows: 1

   * - Syntax / Operator
     - Description
     - Example Usage     
   * - ``==``, ``!=``
     - Equals / Not equals
     - ``User.name != 'Bob'``
   * - ``>``, ``>=``, ``<``, ``<=``
     - Numeric comparison 
     - ``User.age > 30``, ``User.age < 30``
   * - ``&``
     - Logical AND
     - ``(User.age > 20) & (User.role == 'admin')``
   * - ``|``
     - Logical OR
     - ``(User.name == 'Alice') | (User.age < 30)``
   * - ``~``
     - Logical NOT
     - ``~ User.exists('email')``
   * - ``.has(val)``
     -  Contains specific string or array element
     - ``User.tags.has('database')``
   * - ``.not_has(val)``
     -  Does not contain specific string or array element
     - ``User.name.not_has('ice')``
   * - ``.ihas(val)``
     - Case-insensitive contains
     - ``User.name.ihas('alice')``
   * - ``.startswith(val)``
     - String starts with prefix
     - ``User.city.startswith(('L', 'H'))``
   * - ``.endswith(val)``
     - String ends with suffix
     - ``User.name.endswith('b')``
   * - ``.matches(pattern)``
     - Regular expression search (equivalent to ``re.search``)
     - ``User.name.matches(r'[bB]ob')``
   * - ``.fullmatch(pattern)``
     - Regular expression full match (equivalent to ``re.fullmatch``)
     - ``User.name.fullmatch(r'.lic.')``
   * - ``.one_of(col)``
     - Value is within the specified collection
     - ``User.role.one_of(['admin', 'dev'])``
   * - ``.not_in(col)``
     - Value is not within the specified collection
     - ``User.role.not_in(['admin', 'dev'])``
   * - ``.any_in(col)``
     - Any element in the array is within the specified collection
     - ``User.role.any_in(['admin', 'ceo'])``
   * - ``.between(low, high)``
     - Value or string is within the specified range
     - ``User.age.between(20, 30)``
   * - ``.size_of(size)``     
     - Array or string length matches
     - ``User.tags.size_of(2)``
   * - ``.exists(fields)``
     - Checks if specified fields exist
     - ``User.exists('email')``
   * - ``.type_of(type)``
     - Checks the data type
     - ``User.age.type_of(int)``
   * - ``.mod(div, rem)``
     - Modulo condition (remainder is ``rem`` when divided by ``div``)
     - ``User._date.mod(7, 5)``
   * - ``.near(target, tol)``
     -  Numeric value is near the target within tolerance ``tol``
     - ``User._date.near(today, 1)``
   * - ``.test(func)``
     - Passes a custom Lambda function for condition evaluation
     - ``User.age.test(lambda v: 40 >= v > 18)``
   * - ``.abs()``
     - Takes the absolute value of a number before comparing.
     - ``Query().price.abs() == 3.14``
   * - ``.ceil()``
     - Takes the ceiling (math.ceil) of a number before comparing.
     - ``Query().price.ceil() > 3``
   * - ``.floor()``
     - Takes the floor (math.floor) of a number before comparing.
     - ``Query().price.floor() <= 2``
   * - ``.round()``
     - Round a number before comparing.
     - ``Query().price.round() == 2``
   * - ``.float()``
     - Casts the value to a float before comparing.
     - ``Query().price.float() == 2.1``
   * - ``.int()``
     - Casts the value to a integer before comparing.
     - ``Query().price.int() != 1```
   * - ``.neg()``
     - Negates the value (``-val``) before comparing.
     - ``Query().price.neg() == -1.2``
   * - ``.str()``
     - Casts the value to a string before comparing.
     - ``Query().price.str() == '1.2'``
   * - ``.avg()``
     - Calculates the arithmetic mean of an iterable before comparing.
     - ``Query().prices.avg() == 2.5```
   * - ``.std()``
     - Calculates the population standard deviation of an iterable before comparing.
     - ``Query().prices.std() >= 2.0``
   * - ``.max()``
     - Finds the maximum value in an iterable before comparing.
     - ``Query().prices.max() == 4``
   * - ``.mid()``
     - Extracts the middle element or character (index ``len//2``) before comparing.
     - ``Query().prices.mid() == 4``
   * - ``.min()``
     - Finds the minimum value in an iterable before comparing.
     - ``Query().prices.min() == 1``
   * - ``.sum()``
     - Calculates the sum of an iterable before comparing.
     - ``Query().prices.sum() == 8``
   * - ``.first()``
     - Extracts the first item or character before comparing.
     - ``Query().prices.first() == 1``
   * - ``.flat()``
     - Flattens a nested iterable before comparing.
     - ``Query().prices.flat().max() == 4``
   * - ``.last()``
     - Extracts the last item or character before comparing.
     - ``Query().prices.last() == 3``
   * - ``.len()``
     - Calculates the length of an array or string before comparing.
     - ``Query().prices.len() == 3``
   * - ``.sort()``
     - Sorts the iterable values before comparing.
     - ``Query().prices.sort().mid() == 2``
   * - ``.unique()``
     - Performs order-preserving deduplication on an iterable before comparing.
     - ``Query().prices.unique().first() == 1``
   * - ``.lower()``
     - Converts a string to lowercase before comparing.
     - ``Query().name.lower() == 'alice'``
   * - ``.upper()``
     - Converts a string to uppercase before comparing.
     - ``Query().name.upper() == 'ALICE'``
   * - ``.strip()``
     - Strips leading and trailing whitespaces from a string before comparing.
     - ``Query().name.strip() == 'Hi'``
   * - ``field['field']``
     - Accesses a specific field
     - ``User['addr'].city``, ``User.addr.city``
   * - ``.field[0]`` 
     - specific index of an array (supports negative index like ``User.tags[-1]``)
     - ``User.tags[1].has('db')``
   * - ``'*'`` / ``'**'`` / ``'?'``
     - First-level wildcard / Recursive multi-level wildcard / Single-char wildcard path search
     - ``User['*']``, ``User['**']``, ``User['ci?y']``, ``User['c*y']``
   * - ``._id`` / ``._date``
     - system reserved keys: access Document ID (Primary key) and Timestamp respectively
     - ``User._id``, ``User._date``

Advanced
--------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+mSgpack with no compression
   jdb = JDb()

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # insert records
   with jdb.open() as fp:
      for fruit,color in fruits.items():
         jdb.f_write(fp, fruit, color)

   assert jdb == fruits

   # modify records
   with jdb.open() as fp:
      for fruit in fruits:
         color = jdb.f_read(fp, fruit)
         jdb.f_write(fp, fruit, color.upper())

   assert jdb != fruits
   assert set(jdb) == set(fruits)
   
   # unmodify records
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_unwrite(fp, fruit)

   assert jdb == fruits
   
   # remove records
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_delete(fp, fruit)

   assert len(jdb) == 0

   # unremove records
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_undelete(fp, fruit)

   assert jdb == fruits
   
   #---------------------------------------
   with jdb.open() as fp:
      key_table = jdb.key_table

      # replace
      for fruit in key_table:
         color = jdb.f_read(fp, fruit)
         jdb.f_write(fp, fruit, color.upper())

      # unmodify
      for fruit in key_table:
         jdb.f_unwrite(fp, fruit)

      # remove
      for fruit in fruits:
         jdb.f_delete(fp, fruit)

      # unremove
      for fruit in fruits:
         jdb.f_undelete(fp, fruit)

   assert jdb == fruits
   
   #---------------------------------------
   # replace all
   jdb[:] = lambda k,v: v.upper()

   # unmodify all
   jdb ^= jdb

   # remove all
   jdb -= jdb

   # unremove all
   jdb ^= fruits

   assert jdb == fruits


📝 Specifications
*****************

Supported Data Formats
----------------------

Configure ``data_type`` during initialization:

* ``J+J``: JSON Key + JSON Value
* ``J+S``: JSON Key + MsgPack Value (default)
* ``J+M``: JSON Key + Marshal Value
* ``J+P``: JSON Key + Pickle Value
* ``J+Y``: JSON Key + YAML Value
* ``S+J``: MsgPack Key + JSON Value
* ``S+S``: MsgPack Key + MsgPack Value
* ``S+M``: MsgPack Key + Marshal Value
* ``S+P``: MsgPack Key + Pickle Value
* ``S+Y``: MsgPack Key + YAML Value

*Data size = 70,840,580 bytes (MB = 1,000,000 bytes, no zip)*

+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``data_type``     | size       | ratio | read     | write     | Pros           | Cons             |
+===================+============+=======+==========+===========+================+==================+
| ``J+J`` or ``S+J``| 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest write |* no set [a]_     |
|                   |            |       |          |           |* faster read   |* no tuple [a]_   |
|                   |            |       |          |           |* readable      |* weak bytes [b]_ |
|                   |            |       |          |           |                |* weak dict [c]_  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+S`` or ``S+S``| 47,616,008 | 1.48  | 77.4MB/s | 354.2MB/s |* smallest size |* no tuple [a]_   |
|                   |            |       |          |           |* faster read   |* unreadable      |
|                   |            |       |          |           |* faster write  |                  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+M`` or ``S+M``| 72,430,958 | 0.97  | 81.4MB/s | 177.1MB/s |* all type [d]_ |* bigger size     |
|                   |            |       |          |           |* fastest read  |* unreadable      |
|                   |            |       |          |           |                |* security issue  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+P`` or ``S+P``| 70,207,207 | 1.01  | 64.9MB/s | 22.8MB/s  |* all type [d]_ |* slower read     |
|                   |            |       |          |           |                |* slower write    |
|                   |            |       |          |           |                |* unreadable      |
|                   |            |       |          |           |                |* security issue  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+Y`` or ``S+Y``| 181,894,885| 2.57  | 0.146MB/s| 0.352MB/s |* readable      |* biggest size    |
|                   |            |       |          |           |                |* slowest read    |
|                   |            |       |          |           |                |* slowest write   |
|                   |            |       |          |           |                |* no tuple [a]_   |
+-------------------+------------+-------+----------+-----------+----------------+------------------+

.. [a] convert to ``list``
.. [b] convert to hex string
.. [c] only support string key
.. [d] all type = ``str``, ``bytes``, ``bool``, ``int``, ``float``, ``list``, ``tuple``, ``set``, ``dict``, ``None``

Supported Zip Formats
---------------------

Configure ``zip_type`` during initialization:

* ``no``: no compression for Value (default)
* ``gz``: Gzip (mode=1) compression for Value
* ``bz``: Bzip2 (mode=9) compression for Value
* ``xz``: LZMA compression for Value
* ``zs``: Zstandard (mode=22) compression for Value
* ``br``: Brotli (mode=6) compression for Value (better than ``gz``)
* ``z1``: Zstandard (mode=6) compression for Value (better than ``gz``)
* ``z2``: Zstandard (mode=11) compression for Value
* ``lz``: LZ4 (mode=0) compression for Value

**Data size = 70,840,580 (MB = 1,000,000B)**

+------------+------------+-------+----------+-----------+---------------+---------------+
|``zip_type``| size       | ratio | read     | write     | Pros          | Cons          |
+============+============+=======+==========+===========+===============+===============+
| ``no``     | 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest speed|* biggest size |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``gz``     | 16,915,844 | 4.18  | 65.5MB/s | 5.1MB/s   |* built-in     |* slower zip   |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``bz``     | 11,394,042 | 6.21  | 26.4MB/s | 10.8MB/s  |* better ratio |* slowest unzip|
|            |            |       |          |           |* built-in     |* slower unzip |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``xz``     | 11,340,548 | 6.24  | 54.9MB/s | 2.3MB/s   |* better ratio |* slower zip   |
|            |            |       |          |           |* built-in     |* slower unzip |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``zs``     | 11,119,665 | 6.37  | 73.0MB/s | 1.7MB/s   |* best ratio   |* slowest zip  |
|            |            |       |          |           |* faster unzip |               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``br``     | 13,700,696 | 5.17  | 65.8MB/s | 25.3MB/s  |* better ``gz``|               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``z1``     | 14,738,859 | 4.80  | 73.6MB/s | 70.8MB/s  |* faster zip   |               |
|            |            |       |          |           |* faster unzip |               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``z2``     | 13,799,407 | 5.13  | 72.7MB/s | 23.6MB/s  |* faster unzip |               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``lz``     | 26,226,039 | 2.70  | 75.6MB/s | 202.4MB/s |* fastest zip  |* worst ratio  |
|            |            |       |          |           |* fastest unzip|               |
+------------+------------+-------+----------+-----------+---------------+---------------+

Supported Key Table Formats
---------------------------

Configure ``key_limit`` during initialization:

* ``no``: ``dict`` for key_table (default)
* ``bt``: ``BTree`` for key_table (save 44.3% vs ``dict``)
* ``l0`` - ``l5``: ``LiteKeyTable`` modes (save 60-75% vs ``dict``)

**Table size = 3,241,854 keys**

+---------------+--------+--------------+------------+--------------+
| ``key_limit`` | memory | key search   | HIT > get()| MISS > get() |
+===============+========+==============+============+==============+
| ``no``        | 519MB  | 48.59Mo/s    | 29.28Mo/s  | 18.3Mo/s     |
+---------------+--------+--------------+------------+--------------+
| ``bt``        | 289MB  | 3.46Mo/s     | 3.07Mo/s   | 8.04Mo/s     |
+---------------+--------+--------------+------------+--------------+
| ``l3``        | 85MB   | 2.01Mo/s     | 2.01Mo/s   | 1.59Mo/s     |
+---------------+--------+--------------+------------+--------------+

📊 Benchmarking
***************

Testing
-------

.. code-block:: python

   >>> from omni_json_db import JDb
   >>> size = 1_000_000
   >>> jdb = JDb(data_type='J+J')
   >>> data = {f'key{k}':k for k in range(size)}
   
   >>> # Benchmarking operations
   >>> jdb += data        # insert
   >>> jdb[:]             # get_all
   >>> jdb -= data        # remove
   >>> jdb ^= data        # revert=unremove
   >>> jdb[data] = -1     # replace
   >>> jdb ^= data        # revert=unmodify
   >>> print(jdb == data) # Output: True

Results
-------

+-------+---------+---------+---------+----------+---------+----------+
| size  | insert  | get_all | remove  | unremove | replace | unmodify |
+=======+=========+=========+=========+==========+=========+==========+
| 1     | 132 μs  | 89 μs   | 111 μs  | 96 μs    | 91 μs   | 83 μs    |
+-------+---------+---------+---------+----------+---------+----------+
| 10    | 136 μs  | 93 μs   | 142 μs  | 145 μs   | 183 μs  | 177 μs   |
+-------+---------+---------+---------+----------+---------+----------+
| 100   | 442 μs  | 319 μs  | 594 μs  | 680 μs   | 876 μs  | 976 μs   |
+-------+---------+---------+---------+----------+---------+----------+
| 1K    | 3.37 ms | 2.71 ms | 5.24 ms | 5.9 ms   | 7.61 ms | 9.12 ms  |
+-------+---------+---------+---------+----------+---------+----------+
| 10K   | 32.2 ms | 26 ms   | 54.3 ms | 55.8 ms  | 77.5 ms | 91.1 ms  |
+-------+---------+---------+---------+----------+---------+----------+
| 100K  | 358 ms  | 262 ms  | 626 ms  | 583 ms   | 774 ms  | 930 ms   |
+-------+---------+---------+---------+----------+---------+----------+
| 1M    | 3.87 s  | 2.78 s  | 7 s     | 6.09 s   | 8.15 s  | 9.83 s   |
+-------+---------+---------+---------+----------+---------+----------+

 
👥 Contributing
***************
 
Contributions to **omni-json-db** are highly welcome! Whether you are reporting bugs, proposing new features, or improving documentation:

1. Check the existing issues for open tasks or start a discussion.
2. Fork the repository and create a new branch.
3. Include tests for any new features or bug fixes.
4. Open a Pull Request and reach out to the maintainers for review.
 
 
📄 License
**********
 
**omni-json-db** is released under the terms of the `LICENSE <https://github.com/lukatrum/omni-json-db/blob/main/LICENSE>`_ file.


.. |Logo| image:: https://raw.githubusercontent.com/lukatrum/omni-json-db/master/artwork/logo.png
      :height: 400px
      :target: https://pypi.python.org/pypi/omni-json-db/

.. |Build Status| image:: https://img.shields.io/pypi/status/omni-json-db?logo=python&logoColor=white
   :alt: PyPI - Status
   :target: https://github.com/lukatrum/omni-json-db

.. |readthedocs| image:: https://img.shields.io/badge/docs-passing-brightgreen?logo=readthedocs
   :target: https://omni-json-db.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status
   
.. |Version| image:: https://img.shields.io/pypi/v/omni-json-db?pypiBaseUrl=https%3A%2F%2Fpypi.org&logo=pypi&logoColor=white
   :alt: PyPI - Version
   :target: https://pypi.python.org/pypi/omni-json-db/

.. |Python Version| image:: https://img.shields.io/pypi/pyversions/omni-json-db?logo=python&logoColor=white
   :alt: PyPI - Python Version

.. |License| image:: https://img.shields.io/pypi/l/omni-json-db?color=800080&logo=ticktick&logoColor=white
   :alt: PyPI - License
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/LICENSE

.. |Pylint| image:: https://img.shields.io/github/actions/workflow/status/lukatrum/omni-json-db/pylint.yml?label=pylint&logo=lintcode&logoColor=white
   :alt: GitHub Actions Workflow Status
   :target: https://github.com/Lukatrum/omni-json-db/actions/workflows/pylint.yml

.. |Coverage| image:: https://img.shields.io/codecov/c/github/lukatrum/omni-json-db?logo=codecov&logoColor=white
   :alt: Codecov
   :target: https://github.com/Lukatrum/omni-json-db/actions/workflows/codecov.yml

.. |Codacy| image:: https://app.codacy.com/project/badge/Grade/861e1d81ccad4b8292d0062413b6daec    
   :target: https://app.codacy.com/gh/Lukatrum/omni-json-db/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade

.. |Language1| image:: https://img.shields.io/badge/-ENG-d3d3d3?logo=googletranslate&logoColor=white
   :target: https://github.com/lukatrum/omni-json-db/

.. |Language2| image:: https://img.shields.io/badge/-%E4%B8%AD%E6%96%87-d3d3d3?logo=googletranslate&logoColor=white
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/README-tc.rst

.. |Language3| image:: https://img.shields.io/badge/-%E6%97%A5%E6%96%87-d3d3d3?logo=googletranslate&logoColor=white
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/README-jp.rst
