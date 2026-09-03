Time-Series
===========

Every record carries two dates in the key index: a **created** date and a
**modified** date. Slicing the database with a date object queries them
directly, with no extra index to maintain.

Which date a slice looks at is decided by the argument's type:

.. list-table::
   :widths: 25 30 45
   :header-rows: 1

   * - Argument
     - Queries
     - Example
   * - ``datetime.datetime``
     - created date
     - ``jdb[now]``, ``jdb[week_ago:now]``
   * - ``datetime.date``
     - modified date
     - ``jdb[today]``, ``jdb[:yesterday]``
   * - ``float`` (negative)
     - the N most recently modified records
     - ``jdb[-2.:]``

Assignment through ``jdb.keys`` follows the same rule, plus a string form that
sets both at once — ``'<modified> <created>'``:

.. list-table::
   :widths: 40 60
   :header-rows: 1

   * - Assignment
     - Effect
   * - ``jdb.keys[key] = datetime``
     - sets the created **and** the modified date
   * - ``jdb.keys[key] = date``
     - sets the modified date only
   * - ``jdb.keys[key] = '2026-09-02 2026-08-27'``
     - modified ``2026-09-02``, created ``2026-08-27``
   * - ``jdb.set_date(key, cdate)``
     - sets the created date only
   * - ``jdb.set_date(key, cdate, mdate, ttl=...)``
     - sets both, and optionally the TTL

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

   # a datetime moves BOTH the create and the modify date
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
   assert set(matches) == {'banana', 'lemon'}

   # set the two dates independently: '<modified> <created>'
   new_modify_date = prev_date.date()
   new_create_date = prev_week.date()
   assert new_modify_date >= new_create_date
   jdb.keys['lemon'] = f'{new_modify_date} {new_create_date}'

   # find modify date: date == today
   matches = jdb[today]
   assert set(matches) == {'banana'}

   # find modify date: date == prev_date
   matches = jdb[prev_date.date()]
   assert set(matches) == {'apple', 'lemon', 'tomato'}

   # set_date() touches the create date alone
   jdb.set_date('banana', new_create_date)
   assert jdb.keys['banana'][-1] == str(new_create_date)

   # change every record's modify date
   jdb.keys[:] = today
   assert jdb[today] == fruits

``jdb.keys[key]`` returns the raw index row; its last two elements are the
modified date (``[-2]``) and the created date (``[-1]``) as ``YYYY-MM-DD``
strings.

.. note::

   ``jdb.keys[...]`` is the metadata view and still lists a record whose TTL has
   run out; ``jdb[...]`` is the value view and no longer has a value to return
   for it. See :doc:`flags` for TTLs.
