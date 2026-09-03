Time-Travel
===========

Unremove & Unmodify
-------------------

The database tracks internal states, so you can undo modifications
(``unmodify()``) or recover deleted data (``unremove()``). ``revert()`` picks
whichever of the two applies.


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

Record History
--------------

A superseded version stays parked in the index's dead region for as long as
``JFlag.REVERT`` is active. ``history()`` lists what is still reachable, newest
first, and hands back the ``ver`` numbers that ``revert()``, ``unmodify()`` and
``unremove()`` accept as ``version=``:

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb('history.jdb')    # JFlag.REVERT is what parks the old row
   jdb['apple'] = 'red'
   jdb['apple'] = 'green'
   jdb['apple'] = 'blue'

   versions = jdb.history('apple', with_value=True, show=True)
   #   history[apple]
   #   ╔═════╤═════╤══════╤════════════╤════════════╤═══════╤═════╤══════╤═══════╗
   #   ║ ver │ row │ live │ created    │ modified   │ flags │ TTL │ size │ value ║
   #   ╟─────┼─────┼──────┼────────────┼────────────┼───────┼─────┼──────┼───────╢
   #   ║ 2   │ 0   │ YES  │ 2026-08-20 │ 2026-08-20 │       │     │ 5    │ blue  ║
   #   ║ 2   │ 1   │ NO   │ 2026-08-20 │ 2026-08-20 │       │     │ 6    │ green ║
   #   ╚═════╧═════╧══════╧════════════╧════════════╧═══════╧═════╧══════╧═══════╝

   print([(v['live'], v['value']) for v in versions])
   # Output: [(True, 'blue'), (False, 'green')]

Each entry is a dict holding ``row``, ``key``, ``file_id``, ``offset``,
``row_size``, ``val_size``, ``ver``, ``cdays``, ``mdays``, ``ttl``,
``key_flags`` and ``live`` — plus ``value`` when ``with_value=True``. ``live``
is True for the one record ``jdb[key]`` reads today and False for every parked
version, so a deleted key has no live entry at all.

Only two versions come back above: ``'red'``'s row had already been reclaimed to
make room for a later write. That is the rule, not a fault — ``history()`` is a
*best-effort* audit trail, never a write-ahead log. Treat a missing version as
expected.

.. note::

   With the default ``min_safe=0``, a write to **any** key can reclaim the row
   holding another key's previous version, so on a busy database ``history()``
   often returns the live record alone. Construct the database with
   ``min_safe=N`` to hold N index rows out of reach of reuse:

   .. code-block:: python

      jdb = JDb('history.jdb', min_safe=1000)   # keep ~1000 rows of history reachable

   Rows beyond the reserve are recycled exactly as before, so the cost is a
   constant rather than one that grows with the number of writes. It only
   applies while ``JFlag.REVERT`` is active — without it there is no history to
   protect.
