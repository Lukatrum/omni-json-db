Advanced (File-Pointer API)
===========================

Opening the file handle yourself keeps one lock for a whole batch of
``f_*`` calls instead of taking a new one per record.


.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+MsgPack with no compression
   jdb = JDb()

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # insert records
   with jdb.open() as fp:
      for fruit,color in fruits.items():
         jdb.f_write(fp, fruit, color)

   assert jdb == fruits

   # ... or append the whole group in one pass (see the Bulk Insert section)
   with jdb.open(read_only=False) as fp:
      jdb.f_extend(fp, dict(fruits))

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
   