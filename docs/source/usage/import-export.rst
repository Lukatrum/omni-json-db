Import & Export
===============

CSV
---

Built-in hooks for ``DictReader`` and ``DictWriter`` import large datasets from
*CSV* or export **omni-json-db** collections for analysis in *Excel* or
*Pandas*.

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
   print(jdb2.find(RE='Bob')) # Output: {'2': {'name': 'Bob', 'age': '42'}}

   # show table
   jdb2.show(RE='Bob')

The record key is written as the ``_id`` column and read back from it. CSV has
no types, so every imported field arrives as a ``str`` — cast on the way out, or
re-type the records after the import if you need numbers.

INI / TOML
----------

**omni-json-db** parses structured configuration files (*INI*, *TOML*) natively.
Sections become path segments, so a value is addressed as ``section/key``.

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

SQLite
------

The built-in conversion engine turns a relational database into *NoSQL* grouped
structures: one group per table.

Step 1: Prepare *sample.sqlite*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import sqlite3
   conn = sqlite3.connect('sample.sqlite')
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
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_json_db import JDb
   jdb = JDb("migrated_data.jdb")

   # Load an entire SQLite database with one line of code
   jdb.from_sqlite('sample.sqlite')

   # SQLite tables (e.g., 'projects' and 'project_logs') automatically become groups
   projects = jdb['projects']
   logs = jdb['project_logs']

   # Query relational data using the NoSQL interface
   print(projects[3]['name'])  # Output: coding
   print(len(logs))            # Output: 4

   # Combine with powerful Lambda queries to find logs for a specific project
   project_3_logs = logs.find(FUNC=lambda val: val['project_id'] == 3)
   print(project_3_logs)
   # Output: {'3': {'project_id': 3, 'action': 'setup environment', 'log_date': '2024-01-01'}}

A table with an ``INTEGER PRIMARY KEY`` uses it as the record key; a table
without one is keyed by row number.

Parquet
-------

Requires the optional ``pyarrow`` dependency (``pip install pyarrow``).

.. code-block:: python

   import pyarrow as pa
   import pyarrow.parquet as pq

   # write a sample Parquet file
   table = pa.table({
       '_id':   ['p1', 'p2', 'p3'],
       'name':  ['Alice', 'Bob', 'Charlie'],
       'age':   [30, 25, 35],
   })
   pq.write_table(table, 'sample.parquet')


.. code-block:: python

   from omni_json_db import JDb
   jdb = JDb()

   # by default, the first column ('_id') becomes the record key
   jdb.from_parquet('sample.parquet')
   print(jdb['p1'])  # Output: {'name': 'Alice', 'age': 30}

   # rows stream in via pyarrow RecordBatches, so multi-GB files
   # import with a small, constant memory footprint
   jdb.from_parquet('sample.parquet', batch_size=65536)

   # pick a different key column, and prune to only the columns you need
   jdb.from_parquet('sample.parquet', key='_id', columns=['name'])
   print(dict(jdb.items()))
   # Output: {'p1': {'name': 'Alice'}, 'p2': {'name': 'Bob'}, 'p3': {'name': 'Charlie'}}

Unlike CSV, Parquet is typed, so ``age`` comes back as an ``int``.

pandas / polars
---------------

:meth:`~omni_json_db.JDb.to_pandas` and :meth:`~omni_json_db.JDb.to_polars`
export the same table :meth:`~omni_json_db.JDb.to_csv` writes;
:meth:`~omni_json_db.JDb.from_pandas` and
:meth:`~omni_json_db.JDb.from_polars` read it back. Only the export side needs
the optional package installed (``pip install pandas`` / ``pip install
polars``) — the importers consume an object the caller already holds and never
import the library themselves.

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb(data_type='J+J')
   jdb.set_n({'p1': {'name': 'Alice',   'age': 30},
              'p2': {'name': 'Bob',     'age': 25},
              'p3': {'name': 'Charlie', 'age': 35}})

   df = jdb.to_pandas()
   print(df)
   #   _id     name  age
   # 0  p1    Alice   30
   # 1  p2      Bob   25
   # 2  p3  Charlie   35

   # the record key leads, named '_id' unless you rename it
   print(jdb.to_pandas(key='uid').columns.tolist())
   # Output: ['uid', 'name', 'age']

   # round-trip: the first column becomes the record key again
   jdb2 = JDb()
   jdb2.from_pandas(df)
   print(jdb2['p1'])
   # Output: {'name': 'Alice', 'age': 30}

   # polars works the same way, and accepts a LazyFrame
   jdb3 = JDb()
   jdb3.from_polars(jdb.to_polars().lazy(), key='_id')

Like Parquet and unlike CSV, both formats are typed, so ``age`` comes back as
an ``int``.

Export flattens each record into columns exactly as CSV export does: a ``dict``
record contributes its own keys, a scalar record lands in ``__1__``, and any
other iterable spreads over ``__V1__`` ... ``__Vn__``. A database whose records
have different shapes therefore produces a sparse frame — the union of all
columns, with ``None``/``NaN`` where a record has nothing to put there.
``to_polars()`` builds with ``strict=False``, so a column holding more than one
type widens instead of raising; pass ``strict=True`` to get that error back.

On the import side, a ``pandas`` index that has a name is materialised as a
column first, so ``df.set_index('_id')`` round-trips and ``key='_id'`` still
finds it; an unnamed ``RangeIndex`` is dropped, exactly as
``DataFrame.to_csv(index=False)`` would drop it. Missing values (``NaN``,
``NaT``, ``pd.NA``, polars ``null``) are stored as ``None``.

.. note::

   Every importer streams in ``IMPORT_BATCH_ROWS``-sized batches through the
   same append path described in :doc:`writing`, so import speed and memory use
   do not depend on the size of the source file. ``from_pandas()`` and
   ``from_polars()`` additionally convert the frame one ``batch_size`` slice at
   a time, so a large frame never becomes a full list-of-dicts copy.
 
   