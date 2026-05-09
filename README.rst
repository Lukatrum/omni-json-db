|Logo|

.. highlights::
   A nimble squirrel swiftly gathering a golden forest’s worth of acorns!

|Version| |Build Status| |Pylint| |Coverage| |License|

👉 Quick Links
**************

- `📌 Supported Python Versions`_
- `🛠️ Quick Start`_
- `📝 Specifications`_
- `📊 Benchmarking`_
- `👥 Contributing`_

✨ Introduction
***************
``omni-json-db`` is a high-performance, embedded database engine designed for Python developers who need the speed of a Key-Value store with the querying power of a document database. Built for extreme throughput and thread-safety, ``omni-json-db`` leverages modern serialization (``json``, ``msgpack``, ``marshal``, ``pickle``) and compression to provide a storage layer that is often significantly faster than SQLite for JSON-heavy workloads. Whether you are building a local cache, a log aggregator, or a distributed microservice, ``omni-json-db`` provides the tools to handle data at scale with "Zero-Config" simplicity.

* **Schema-LESS**: Store complex, nested data without pre-defining tables.

* **Server-LESS**: Direct disk access without the overhead of a database server.

* **SQL-LESS**: Use native Python syntax, Regex, and Lambdas for data manipulation.

🚀 Features
***********
* **Extreme Performance**: Leverages ``orjson`` and ``ormsgpack`` for serialization. [refer to `Supported Data Formats`_]

* **Concurrency Control**: Optimized for Many-Read / Single-Write environments using a robust file-locking and Lock mechanism.

* **Advanced Compression**: Supports LZ4 (speed-focused), Zstandard (balanced), and Brotli (size-focused) to minimize storage footprint. [refer to `Supported Zip Formats`_]

* **Powerful Querying**: Search using Regular Expressions (RE), Lambda filters, or modification timestamps (Time-Travel query). [refer to `Query`_]

* **Memory Caching**: Adjustable cache_limit to balance RAM usage and I/O speed. [refer to `Supported Key Table Formats`_]

* **Network Mode** (``JNetFiles``): Transform a local ``omni-json-db`` instance into a networked service with a single command using run_files_server. [refer to `Network`_]

* **In-Memory Mode** (``JMemFiles``): Run the entire database in RAM for extreme performance (ideal for real-time caches or volatile session storage). [refer to `In-memory`_]

* **Revertable**: Unlike traditional NoSQL stores, ``omni-json-db`` tracks internal states allowing you to unwrite (rollback a modification) or undelete a record. This provides a safety net similar to a manual "Undo" or a lightweight ACID rollback. [refer to `Rollback`_, `Backup & Restore`_]

* **Native CSV Support**: Built-in hooks for DictReader and DictWriter allow you to import massive datasets from CSV files or export your ``omni-json-db`` collections for analysis in Excel or Pandas. [refer to `CSV`_]

* **Date-Based Lookups**: Every record is timestamped, enabling queries like "Give me all users modified last Tuesday." [refer to `Date Lookups`_]

📌 Supported Python Versions
****************************

``omni-json-db`` has been tested with Python 3.7 - 3.14 and PyPy3.

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
   # Key-Value is Json+Json without compression
   jdb = JDb("example.jdb")

   # Store data
   jdb["user1"] = {"name" : "Ryan", "role": "Developer"}
   
   # Retrieve data
   user = jdb["user1"]
   print(user["name"], user["role"]) # Output: Ryan Developer
   
All standard ``dict`` methods work: ``keys()``, ``values()``, ``items()``, ``get()``, ``set()``, ``pop()``, ``setdefault()``, ``update()``.

In-memory
---------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   jdb1 = JDb()

   # Store data
   jdb1 += {"user1" : {"name" : "Joe", "role": "Senior Developer"}}
   
   # Retrieve data
   print(jdb1["user1"]["name"]) # Output: Joe

   # create 2nd JDb sharing same memory
   jdb2 = JDb(jdb1)

   # Store data to 2nd JDb
   jdb2["user2"] = {"name" : "Kathy", "role": "CEO"}

   # Retrieve the new inserted data (by 2nd JDb)
   print(jdb1["user2"]["name"]) # Output: Kathy

Rollback
--------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Json+Pickle with zstandard compression
   jdb = JDb("fruit.jdb", data_type="J+P", zip_type='zs')

   jdb["apple"] = "red"
   jdb["apple"] = "blue" # modify
   jdb.revert("apple") # unmodify
   assert jdb["apple"] == 'red'

   del jdb["apple"] 
   assert "apple" not in jdb

   jdb.revert("apple") # unremove
   assert jdb["apple"] == "red"

Backup & Restore
----------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Msgpack+Json with Bzip2 compression
   jdb = JDb("fruit.jdb", data_type="S+J", zip_type='bz')

   # Add fruit to jdb
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits
   assert jdb == fruits

   # backup jdb to bak folder = ./bak/fruit.jdb
   jdb_bak = jdb.backup('bak')
   assert jdb_bak == fruits
   assert jdb_bak == jdb

   # del all jdb data
   del jdb[fruits]
   assert jdb != fruits
   assert jdb != jdb_bak
   assert len(jdb) == 0

   # restore bak folder to jdb
   jdb.restore('bak')
   assert jdb == fruits
   assert jdb == jdb_bak

Query
-----

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+Marshal with no compression
   jdb = JDb(data_type="J+M")
   
   # insert value without key
   jdb += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]
   
   print(jdb[:]) # print all records from jdb

   matches = jdb.find(FUNC=lambda k,v: v.get('name', '') == 'John') 
   print(matches) # Output : {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}}
   
   matches = jdb.find(RE='John|Bob')
   print(matches) # {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}, '2': {'name': 'Bob', 'age': 42}}   

Operator
--------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key+Value is Msgpack+Msgpack with lz4 compression
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
   assert len(jdb) == 102
   assert jdb['key100'] == 101
   assert jdb[-2.:] == {'key100':101, 'key101':102} # get last two modified records
   assert jdb[(f'key{v}' for v in range(100))] == data # same as jdb[data] == data

   # <jdb -= ..> == jdb.remove(..)
   jdb -= ['key100', 'key101', 'key102', 'key103']
   assert len(jdb) == 100
   assert jdb == data

   # <jdb &= ..> == jdb.replace(..)
   jdb &= {f'key{v}':v+1 for v in range(200)}
   assert len(jdb) == 100
   assert jdb == {f'key{v}':v+1 for v in range(100)}

   # <jdb ^= ..> == jdb.unmodify(..)
   jdb ^= {f'key{v}' for v in range(100)} # same as jdb ^= data
   assert len(jdb) == 100
   assert jdb == data

   # <jdb[:] = ..> == jdb.update(..)
   jdb[:] = 0 # set all records to zero
   assert len(jdb) == 100
   assert jdb == {f'key{v}':0 for v in range(100)}
   assert jdb.find(NE=0) == {}

   # remove all records
   jdb -= jdb # same as del jdb[:]
   assert len(jdb) == 0

   # <jdb ^= ..> == jdb.unremove(..)
   jdb ^= {f'key{v}' for v in range(100)} # same as jdb ^= data
   assert len(jdb) == 100
   assert all(val == 0 for key,val in jdb.items())

   # lambda VALUE operation
   jdb[:] = lambda key,val: int(key.replace('key', '')) + val
   assert jdb == data

   # <del jdb[..]> == jdb.remove_fast(..)
   del jdb[data] # same as del jdb[:]
   assert len(jdb) == 0

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
   assert len(matches) == 120
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

Date Lookups
------------

.. code-block:: python

   from omni_json_db import JDb
   import datetime as dt

   # Initialize the database in memory
   # Key+Value is Json+Msgpack with Brotli compression
   # using BTree as Key Table for better memory usage
   jdb = JDb(data_type="J+S(br)", key_limit="bt")

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

Group
-----

.. code-block:: python

   from omni_json_db import JDb

   # Initialize the database from file
   # Key-Value is Json+Json with no compression
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

   # find fruits which contains 'a' from all groups
   matches = jdb.find(r':::a')
   print(matches) # Output: ['red:::apple', 'red:::tomato', 'yellow:::banana', 'yellow:::mango']

CSV
---

.. code-block:: python

   from omni_json_db import JDb
      
   jdb1 = JDb()

   # insert value without key
   jdb1 += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]
   
   # export to CSV file
   jdb1.to_csv('example.csv')

   # create another JDb in memory
   jdb2 = JDb()
   
   # import from CSV file
   jdb2.from_csv('example.csv')
   print(jdb2.find(RE='Bob')) # Output: {'name': 'Bob', 'age': 42}

Advanced
--------

.. code-block:: python

   from omni_json_db import JDb
   
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

Network
-------

**Server side:**

.. code-block:: python

   >> from omni_json_db import run_files_server
   >> run_files_server(host='127.0.0.1', port=59898, files='net_storage.jdb')

**Client side:**

.. code-block:: python

   >> from omni_json_db import JDb
   >> jdb = JDb('127.0.0.1:59898')

📝 Specifications
*****************

Supported Data Formats
----------------------

Configure ``data_type`` during initialization:

* ``J+J``: JSON Key + JSON Value (default)
* ``J+S``: JSON Key + MsgPack Value
* ``J+M``: JSON Key + Marshal Value
* ``J+P``: JSON Key + Pickle Value
* ``S+J``: MsgPack Key + JSON Value
* ``S+S``: MsgPack Key + MsgPack Value
* ``S+M``: MsgPack Key + Marshal Value
* ``S+P``: MsgPack Key + Pickle Value

**Data size = 70,840,580 (MB = 1,000,000B, no zip)**

+-------------------+------------+-------+----------+-----------+----------------+---------------+
| ``data_type``     | size       | ratio | read     | write     | GOODs          | BADs          |
+===================+============+=======+==========+===========+================+===============+
| ``J+J`` or ``S+J``| 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest write |* no set()     |
|                   |            |       |          |           |* faster read   |* no tuple()   |
|                   |            |       |          |           |* readable      |* weak bytes   |
+-------------------+------------+-------+----------+-----------+----------------+---------------+
| ``J+S`` or ``S+S``| 47,616,008 | 1.48  | 77.4MB/s | 354.2MB/s |* smallest size |* no tuple()   |
|                   |            |       |          |           |* faster read   |* unreadable   |
|                   |            |       |          |           |* faster write  |               |
+-------------------+------------+-------+----------+-----------+----------------+---------------+
| ``J+M`` or ``S+M``| 72,430,958 | 0.97  | 81.4MB/s | 177.1MB/s |* all type [1]_ |* biggest size |
|                   |            |       |          |           |* fastest read  |* unreadable   |
+-------------------+------------+-------+----------+-----------+----------------+---------------+
| ``J+P`` or ``S+P``| 70,207,207 | 1.01  | 64.9MB/s | 22.8MB/s  |* all type [1]_ |* slowest read |
|                   |            |       |          |           |                |* slowest write|
|                   |            |       |          |           |                |* unreadable   |
+-------------------+------------+-------+----------+-----------+----------------+---------------+

.. [1] all type = ``str``, ``bytes``, ``bool``, ``int``, ``float``, ``list``, ``tuple``, ``set``, ``dict``, ``None``

Supported Zip Formats
---------------------

Configure ``zip_type`` during initialization:

* ``no``: no compression for Value (default)
* ``gz``: Gzip (mode=9) compression for Value
* ``bz``: Bzip2 (mode=9) compression for Value
* ``xz``: LZMA compression for Value
* ``zs``: Zstandard (mode=22) compression for Value
* ``br``: Brotli (mode=6) compression for Value (better than ``gz``)
* ``z1``: Zstandard (mode=6) compression for Value (better than ``gz``)
* ``z2``: Zstandard (mode=11) compression for Value
* ``lz``: LZ4 (mode=0) compression for Value

**Data size = 70,840,580 (MB = 1,000,000B)**

+------------+------------+-------+----------+-----------+---------------+---------------+
|``zip_type``| size       | ratio | read     | write     | GOODs         | BADs          |
+============+============+=======+==========+===========+===============+===============+
| ``no``     | 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest speed|* biggest size |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``gz``     | 16,915,844 | 4.18  | 65.5MB/s | 5.1MB/s   |               |* slower zip   |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``bz``     | 11,394,042 | 6.21  | 26.4MB/s | 10.8MB/s  |* better ratio |* slowest unzip|
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``xz``     | 11,340,548 | 6.24  | 54.9MB/s | 2.3MB/s   |* better ratio |* slower zip   |
|            |            |       |          |           |               |* slower unzip |
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

   >> from omni_json_db import JDb
   >> size = 1_000_000
   >> jdb = JDb(data_type='J+J')
   >> data = {f'key{k}':k for k in range(size)}
   
   >> # Benchmarking operations
   >> jdb += data        # insert
   >> jdb[:]             # get_all
   >> jdb -= data        # remove
   >> jdb ^= data        # revert=unremove
   >> jdb[data] = -1     # replace
   >> jdb ^= data        # revert=unmodify
   >> print(jdb == data) # Output: True

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

Whether reporting bugs, discussing improvements and new ideas or writing extensions: Contributions to ``omni-json-db`` are welcome! Here's how to get started:

1. Check for open issues or open a fresh issue to start a discussion around a feature idea or a bug.
2. Fork `the repository <https://github.com/lukatrum/omni-json-db/>`_ on Github, create a new branch off the ``master`` branch and start making your changes (known as `GitHub Flow <https://docs.github.com/en/get-started/using-github/github-flow>`_).
3. Write a test which shows that the bug was fixed or that the feature works as expected.
4. Send a pull request and bug the maintainer until it gets merged and published ☺

.. |Logo| image:: https://raw.githubusercontent.com/lukatrum/omni-json-db/master/artwork/logo.png
      :height: 400px
      :target: https://pypi.python.org/pypi/omni-json-db/

.. |Build Status| image:: https://img.shields.io/pypi/status/omni-json-db?logo=python&logoColor=white
   :alt: PyPI - Status
   :target: https://github.com/lukatrum/omni-json-db

.. |Version| image:: https://img.shields.io/pypi/v/omni-json-db?pypiBaseUrl=https%3A%2F%2Fpypi.org&logo=pypi&logoColor=white
   :alt: PyPI - Version
   :target: https://pypi.python.org/pypi/omni-json-db/

.. |License| image:: https://img.shields.io/pypi/l/omni-json-db?color=800080&logo=ticktick&logoColor=white
   :alt: PyPI - License
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/LICENSE

.. |Pylint| image:: https://img.shields.io/github/actions/workflow/status/lukatrum/omni-json-db/pylint.yml?label=pylint&logo=lintcode&logoColor=white
   :alt: GitHub Actions Workflow Status
   :target: https://github.com/Lukatrum/omni-json-db/actions/workflows/pylint.yml

.. |Coverage| image:: https://img.shields.io/codecov/c/github/lukatrum/omni-json-db?logo=codecov&logoColor=white
   :alt: Codecov
   :target: https://github.com/Lukatrum/omni-json-db/actions/workflows/codecov.yml




.. image:: https://api.codacy.com/project/badge/Grade/4dd774b5d9804647889bee3b57b3761d
   :alt: Codacy Badge
   :target: https://app.codacy.com/gh/Lukatrum/omni-json-db?utm_source=github.com&utm_medium=referral&utm_content=Lukatrum/omni-json-db&utm_campaign=Badge_Grade