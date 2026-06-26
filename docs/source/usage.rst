Examples
==============

Unremove & Unmodify
-------------------

The database tracks internal states, allowing you to undo modifications (``unmodify()``) or recover deleted data (``unremove()``). 

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
-----------------

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

Easily isolate and manage different data modules using groups.

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

   # find fruits which contains 'a' from all groups
   matches = jdb.find(r':::a')
   print(matches) # Output: ['red:::apple', 'red:::tomato', 'yellow:::banana', 'yellow:::mango']

CSV Import / Export
-------------------

Built-in hooks for ``DictReader`` and ``DictWriter`` allow you to import massive datasets from *CSV* files or export your **omni-json-db** collections for analysis in *Excel* or *Pandas*. 

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

   # create another JDb in memory
   jdb2 = JDb()
   
   # import the data from CSV
   jdb2.from_csv('example.csv')
   print(jdb2.find(RE='Bob')) # Output: {'name': 'Bob', 'age': 42}

INI / TOML Import
-----------------

**omni-json-db** natively supports parsing structured configuration files (*INI*, *TOML*).

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

The built-in conversion engine effortlessly transforms relational databases (*SQLite*) into *NoSQL* grouped structures.

Step 1: Prepare *sample.sql*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_json_db import JDb   
   jdb = JDb("migrated_data.jdb")

   # Load an entire SQLite database with one line of code
   jdb.from_sqlite('sample.sql')

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

Transform a local **omni-json-db** instance into a networked service with a single command using ``run_files_server()``.


**Server side**
~~~~~~~~~~~~~~~~

.. code-block:: python
   
   from omni_json_db import JDb, run_files_server   
   
   jdb = JDb('storage.jdb')

   # equivalent to: files='storage.jdb'
   run_files_server(host='127.0.0.1', port=59898, files=jdb)

   # write key to JDb
   jdb['remote-key'] = 'secret'

**Client side**
~~~~~~~~~~~~~~~~~

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

   # change date_type to 'S+S' and zip_type to 'lz'
   jdb.upgrade(data_type='S+S', zip_type='lz')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: S+S lz

   # only change KEY type from 'S' to 'J'
   jdb.change_KEY('J')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: J+S lz

Time-Series
------------

Every record is timestamped, unlocking powerful date-based slicing. For example, grab all records modified since yesterday with ``jdb[yesterday:now]``.

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
-----------------

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

Queries
------------------

**omni-json-db** is equipped with an exceptionally powerful and flexible NoSQL-like query engine. Through a single ``find()`` method, you can execute deep structural queries, regular expressions, logical combinations, and even custom Python functions.


Let's initialize an in-memory JDb instance (``jdb = JDb()``) and populate it with some sample JSON-like data to demonstrate the querying capabilities.

.. list-table::
   :widths: 10 35 35
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
     - ``{'$exists': ['age', 'tags']}``
   * - ``!$exists``
     - Matches documents that lack the specified field/key.
     - ``{'!$exists': ['age']}``
   * - ``$size``
     - Matches if the size/length of an array/string equals the specified value.
     - ``{'$size': [1,2,3]}``
   * - ``!$size``
     - Matches if the size/length does NOT equal the specified value(s).
     - ``{'!$size': [1,2,3]}``
   * - ``$type``
     - Matches if the value is of the specified Python variable type.
     - ``{'$type': list}``   

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

**omni-json-db** covers over 90% of typical query scenarios right out of the box. Below are examples of how to utilize the various parameters and NoSQL syntax.

1. Exact Match & Global Search (ANY, RE, RE2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Find records where any field exactly matches or contains a specific value.

.. code-block:: python

    # Find users where any attribute exactly matches 'Alice'
    res = jdb.find(ANY='Alice')
    assert list(res) == ['user_1']

    # RE/RE2 convert value into JSON string format for searching.
    # Find any record that has the string 'designer' inside it
    res = jdb.find(RE=r'designer')
    assert list(res) == ['user_4']

    # RE2 remove some JSON symbol (,[]{}") before searching
    res = jdb.find(RE2=r'role:designer')
    assert list(res) == ['user_4']


2. Relational & Conditional Operators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Filter data within dictionary fields using NoSQL operators (``$eq``, ``$ne``, ``$lt``, ``$lte``, ``$gt``, ``$gte``, ``$in``, ``$has``).

.. code-block:: python

    # Age is greater than or equal to 30
    res = jdb.find(vals={'age': {'$gte': 30}}) # find(ANY={'$gte': 30})
    assert list(res) == ['user_1', 'user_3']

    # Age is strictly less than 30
    res = jdb.find(vals={'age': {'$lt': 30}}) # find(ANY={'$lt': 30})
    assert list(res) == ['user_2', 'user_4']

    # Role is either 'admin' or 'designer'
    res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
    assert list(res) == ['user_1', 'user_4']

    # Role is not 'admin' and not 'designer'
    res = jdb.find(vals={'role': {'$nin': ['admin', 'designer']}})
    assert list(res) == ['user_2', 'user_3']

    # tags contains 'python'
    res = jdb.find(vals={'tags': {'$has': 'python'}})
    assert list(res) == ['user_1', 'user_3']

    # Age is NOT 30
    res = jdb.find(vals={'age': {'$ne': 30}}) # find(ANY={'$ne': 30})
    assert list(res) == ['user_2', 'user_3', 'user_4']

    # Age is 28
    res = jdb.find(vals={'age': {'$eq': 28}}) # find(ANY={'$eq': 28})
    assert list(res) == ['user_4']

    # 40 >= Age > 25
    res = jdb.find(vals={'age': {'$gt': 25, '$lte': 40}})
    assert list(res) == ['user_1', 'user_3', 'user_4']


3. Logical Grouping (AND, OR, NOR, NOT)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Combine multiple conditions for complex lookups.

.. code-block:: python

    # Age >= 25 AND Age <= 30
    res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}])
    assert list(res) == ['user_1', 'user_2', 'user_4']

    # Role is 'admin' OR Age > 30
    res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
    assert list(res) == ['user_1', 'user_3']

    # Role is not 'admin' AND Age <= 30
    res = jdb.find(NOR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
    assert list(res) == ['user_2', 'user_4']

    # User is NOT a developer
    res = jdb.find(NOT={'role': 'developer'})
    assert list(res) == ['user_1', 'user_4']

    # (Role is 'admin' OR Age > 30) AND 'linux' not in tags
    res = jdb.find(AND=[
      {'$or': [
         {'role': 'admin'},
         {'age': {'$gt': 30}}
      ]},
      {'$not': {'tags': {'$has': 'linux'}}}
    ])
    assert list(res) == ['user_1']

4. Regular Expressions (RE, RE2, re.compile)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**omni-json-db** natively supports regex for fuzzy matching on both keys and values.

.. code-block:: python

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
    res = jdb.find(re.compile(r'^user_[1-2]$'))
    assert list(res) == ['user_1', 'user_2']


5. Array / List Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Directly query list sizes or elements at specific array indices.

.. code-block:: python

    # Users with exactly 2 tags in their list
    res = jdb.find(vals={'tags': {'$size': 2}})
    assert list(res) == ['user_1', 'user_2', 'user_4']

    # Users whose FIRST tag (index 0) is 'python'
    res = jdb.find(vals={'tags': {'$0': 'python'}})
    assert list(res) == ['user_1', 'user_3']


6. Lambda / Custom Functions (FUNC) & Pagination (limit)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For highly specific rules, pass a Python function. Use ``limit`` to stop searching once enough results are found.

.. code-block:: python

    # Pass a lambda to evaluate both the key and the value dynamically
    # Example: Find the first users whose age is an even number
    res = jdb.find(
       FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0, 
      limit=1
    )
    assert list(res) == ['user_1']

    # Users has email
    res = jdb.find(vals={'email': lambda v: v != ''})
    assert list(res) == ['user_1', 'user_4']

    # Users don't have email
    res = jdb.find(NOT={'email': lambda v: v != ''})
    assert list(res) == ['user_2', 'user_3']

    # For primitive stored values (non-nested), you can use quick keyword arguments:
    jdb['simple_counter'] = 50
    res = jdb.find(EQ=50)       # Equals 50
    assert list(res) == ['simple_counter']

    res = jdb.find(IN=[40, 50]) # Value in list
    assert list(res) == ['simple_counter']

Advanced
---------

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

