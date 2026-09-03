Groups Mode
===========

A group is a namespace with its own KEY file. ``add_group()`` returns a ``JDb``
that behaves exactly like the parent, and the ``:::`` separator addresses a
record inside one from the top level.

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Json+MsgPack with no compression
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
   print(list(matches))
   # Output: ['red:::apple', 'red:::tomato', 'yellow:::banana', 'yellow:::mango']

   # a key-only match carries no values -- ask for them explicitly
   print(jdb.find(r':::a', with_value=True))
   # Output: {'red:::apple': {'qty': 1}, 'red:::tomato': {'qty': 2},
   #          'yellow:::banana': {'qty': 4}, 'yellow:::mango': {'qty': 8}}

The pattern before ``:::`` filters the group names and the pattern after it
filters the record keys, so ``jdb.find('_a$:::[ac]')`` fans out over every group
whose name ends in ``_a`` and keeps the records starting with ``a`` or ``c``.
Groups nest, and the separator repeats: ``'1st:::2nd:::3rd:::group_a:::a'``.

.. note::

   A group is a record in the parent's KEY file, marked with the derived
   ``GROUP`` flag. A flag set on that row applies to the row itself, not to the
   records inside the group.
