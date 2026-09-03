Transactions
============

``transaction()`` is ``open(read_only=False)`` plus an undo log: it yields the
same file-pointer table, but if the block leaves through an exception every KEY
row it touched is put back.

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb("fruit.jdb")
   jdb["apple"] = "red"

   try:
       with jdb.transaction():
           jdb["apple"] = "green"        # modify
           jdb["banana"] = "yellow"      # add
           del jdb["apple"]              # delete
           raise RuntimeError("something went wrong")

   except RuntimeError:
       pass

   assert jdb["apple"] == "red"          # every change is undone
   assert "banana" not in jdb

Anything the block writes is rolled back — ``insert()``/``+=`` bulk paths and
``rename()`` included — and it does not need ``JFlag.REVERT``: the undo log is
the KEY rows themselves, not the parked history ``revert()`` walks.

Nesting is a savepoint. An inner block that fails rolls back only its own
writes; an outer rollback still reaches the state from before either block.

.. code-block:: python

   with jdb.transaction():
       jdb["a"] = 1
       try:
           with jdb.transaction():       # savepoint
               jdb["a"] = 2
               raise RuntimeError
       except RuntimeError:
           pass

       assert jdb["a"] == 1              # only the inner block was undone

   assert jdb["a"] == 1                  # ... and the outer block committed

The block yields the file-pointer table, so the ``f_*`` API works inside it
exactly as it does inside ``open()``:

.. code-block:: python

   fruits = {'apple': 'red', 'banana': 'yellow'}

   with jdb.transaction() as fp:
       for fruit, color in fruits.items():
           jdb.f_write(fp, fruit, color)

..

   **What it does not promise.** The undo log lives in memory: an exception is
   undone, a crash is not. Rollback restores the KEY index only, so bytes
   appended to the VAL files stay as dead space until ``recycle()`` collects
   them, and while the block is open no dead row or dead VAL slot is reused —
   a long transaction therefore grows the files faster than the same writes
   outside one would. Operations that reach outside the KEY index
   (``add_group()``, ``del_group()``, ``recycle()``, ``clear()``,
   ``resize_index_size()``, ``change_KEY()``) raise ``JValueError`` rather than
   escape the rollback, and a group is a separate KEY file, so writes routed
   into one are not covered.
