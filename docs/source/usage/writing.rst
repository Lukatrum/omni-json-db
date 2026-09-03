Writing Data
============

Bulk Insert
-----------

Writing many records at once goes through a dedicated append path, so there is
nothing to switch on — every batch entry point already uses it:

.. code-block:: python

   from omni_json_db import JDb

   jdb  = JDb('users.jdb')
   rows = {f'user{i}': {'age': i % 80} for i in range(100_000)}

   jdb += rows                 # __iadd__ -> add()
   jdb.insert(rows)            # never overwrites a key that already exists
   jdb.update(rows)            # only touches keys already present
   jdb.from_csv('users.csv')   # every importer streams in IMPORT_BATCH_ROWS-sized batches

``add()`` splits the batch by key. A key that already exists is rewritten one at
a time by ``f_write()``, so update semantics, dead-row reuse and history are
unchanged. Every *new* key is collected and handed to ``f_extend()``, which
appends the whole group in one pass: values are serialized and padded ahead of
the writes, the padded bytes reach each VAL file in a single ``write()`` instead
of one per record, and the KEY rows are encoded into one block and written once.

A batch append never takes a row back from the DEAD area. ``n_lines`` grows by
exactly one row per new record, and the space parked by ``f_delete()`` stays
available for later rewrites instead of being consumed by the insert — which is
why the gain widens on a database that has already seen deletes.

.. list-table:: 50,000 records, best of 4
   :widths: 45 20 25
   :header-rows: 1

   * -
     - v3.00.00
     - v3.00.10+
   * - fresh insert
     - 0.616 s
     - 0.366 s (1.7x)
   * - insert into a DB with 10,000 DEAD rows
     - 1.892 s
     - 0.419 s (4.5x)
   * - in-memory insert
     - 0.540 s
     - 0.324 s (1.7x)
   * - inline (KEY-row) values
     - 0.305 s
     - 0.215 s (1.4x)
   * - 500 x 20-record batches
     - 0.167 s
     - 0.110 s (1.5x)

Under an explicit file handle, ``f_extend()`` is the batch counterpart of
``f_write()`` — it takes the write lock itself, so the caller does not have to:

.. code-block:: python

   with jdb.open(read_only=False) as fp:
      new = {'a': 1, 'b': [2, 3]}
      print(jdb.f_extend(fp, new, ttl=7))       # Output: True
      # on return, `new` holds exactly the records that were written
      jdb.f_extend(fp, {'a': 99}, replace=True) # rewrite existing keys too: a bulk upsert

``ttl=`` and ``key_flags=`` are shared by every record in the call, and the work
is done in bounded passes, so memory stays flat however long ``records`` is.

In-Memory Mode
--------------

Passing no file name keeps everything in RAM. Handing an existing instance to
``JDb()`` opens a second view over the *same* memory, so both see each other's
writes.

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+MsgPack without compression
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

Change Type
-----------

``upgrade()`` rewrites the whole database into another ``data_type`` /
``zip_type``; ``change_KEY()`` touches the KEY side alone.

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

.. note::

   Both calls hand the rewrite to a background worker. Reading the database
   (the ``assert`` above is enough) waits for it to finish, so check
   ``data_type`` *after* a read rather than immediately on return.

Backup & Restore
----------------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is MsgPack+Json with Bzip2 compression
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

   # ... or let the whole block undo itself (see the Transactions page)
   try:
      with jdb.transaction() as fp:
         for fruit in fruits:
            jdb.f_delete(fp, fruit)

         raise RuntimeError

   except RuntimeError:
      pass

   assert jdb == fruits
