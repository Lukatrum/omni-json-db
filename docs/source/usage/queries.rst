Queries
=======

**omni-json-db** is equipped with a powerful, flexible NoSQL-like query engine.
Through a single ``find()`` method you can run deep structural queries, regular
expressions, logical combinations, and custom Python functions. ``show()``
takes the same arguments and additionally prints a console table.

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
   print(matches) # Output: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}}

   # Use Regex to find record(s) matching the name 'John' or 'Bob'
   matches = jdb.find(RE='John|Bob')
   print(matches) # Output: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}, '2': {'name': 'Bob', 'age': 42}}

Condition operators: ``EQ``, ``NE``, ``GT``, ``LT``, ``GTE``, ``LTE``, ``HAS``,
``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOR``, ``NOT``, ``NAND``,
``SIZE``, ``ANY``, ``ALL``, ``NONE``, ``IHAS``, ``NHAS``, ``EXISTS``, ``TYPE``,
``MOD``, ``BETWEEN``, ``NEAR``, ``MATCH``, ``SW``, ``EW``, ``IN``, ``NIN``,
``ANYIN``.

Transform operators: ``ABS``, ``CEIL``, ``FLOOR``, ``ROUND``, ``FLOAT``,
``INT``, ``NEG``, ``STR``, ``AVG``, ``STD``, ``MAX``, ``MID``, ``MIN``, ``SUM``,
``FIRST``, ``FLAT``, ``LAST``, ``LEN``, ``SORT``, ``UNIQUE``, ``LOWER``,
``UPPER``, ``STRIP``.

.. note::

   A query that filters on *values* returns ``{key: value}``. A query that only
   matches *keys* (a plain string, a regex over the key space) returns
   ``{key: None}`` — pass ``with_value=True`` to load the values too.

More Query Examples
-------------------

Every example below runs against the same four records:

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

1. Exact Match & Global Search (ANY, RE, RE2)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Find records where any field exactly matches or contains a specific value.

.. code-block:: python

   # Find users where any attribute exactly matches 'Alice'
   res = jdb.find(ANY='Alice')
   assert list(res) == ['user_1']

   res2 = jdb.find(vals={'name': 'Alice'})
   assert res == res2

   # RE converts values into JSON string format for searching.
   # Find any record that has the string 'designer' inside it
   res = jdb.find(RE=r'designer')  # vals={'$re': r'designer'}
   assert list(res) == ['user_4']

   # RE2 removes JSON symbols (,[]{}") before searching
   res = jdb.find(RE2=r'role:designer')
   assert list(res) == ['user_4']

   res2 = jdb.show(vals={'role.$re': r'd.+ner'})  # {'role': re.compile(r'd.+ner')}
   assert res == res2

2. Relational & Conditional Operators
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Filter data inside dictionary fields with NoSQL operators. Every operator has a
nested form (``{'age': {'$gte': 30}}``) and a flat dotted form
(``{'age.$ge': 30}``) — they are equivalent.

.. code-block:: python

   # Age is greater than or equal to 30
   res = jdb.find(vals={'age': {'$gte': 30}})  # find(ANY={'$gte': 30})
   assert list(res) == ['user_1', 'user_3']

   res2 = jdb.find(vals={'age.$ge': 30})
   assert res == res2

   # Age is strictly less than 30
   res = jdb.find(vals={'age': {'$lt': 30}})
   assert list(res) == ['user_2', 'user_4']

   # Role is either 'admin' or 'designer'
   res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
   assert list(res) == ['user_1', 'user_4']

   res2 = jdb.find(vals={'role': ['admin', 'designer']})  # a bare list means $in
   assert res == res2

   # Role is neither 'admin' nor 'designer'
   res = jdb.find(vals={'role': {'$nin': ['admin', 'designer']}})
   assert list(res) == ['user_2', 'user_3']

   # tags contains 'python'
   res = jdb.find(vals={'tags': {'$has': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   # Age is NOT 30
   res = jdb.find(vals={'age': {'$ne': 30}})
   assert list(res) == ['user_2', 'user_3', 'user_4']

   res2 = jdb.find(vals={'!age': 30})  # {'age.$ne': 30}
   assert res == res2

   # Age is 28
   res = jdb.find(vals={'age': {'$eq': 28}})
   assert list(res) == ['user_4']

   res2 = jdb.find(vals={'age': 28})
   assert res == res2

   # 40 >= Age > 25
   res = jdb.find(vals={'age': {'$gt': 25, '$lte': 40}})  # {'age.$gt':25, 'age.$lte':40}
   assert list(res) == ['user_1', 'user_3', 'user_4']

   res2 = jdb.show(vals={'age.$between': (26, 40)})
   assert res == res2

3. Logical Grouping (AND, OR, NOR, NOT)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Combine multiple conditions for complex lookups.

.. code-block:: python

   # Age >= 25 AND Age <= 30
   res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}])
   assert list(res) == ['user_1', 'user_2', 'user_4']

   res2 = jdb.find(vals={'age.$ge': 25, 'age.$le': 30})
   assert res == res2

   # Role is 'admin' OR Age > 30
   res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
   assert list(res) == ['user_1', 'user_3']

   res2 = jdb.find(OR=[{'r*e': 'admin'}, {'age.$gt': 30}])  # '*' is a wildcard
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

4. Regular Expressions (RE, RE2, re.compile)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Regex works on both keys and values.

.. code-block:: python

   # Values matching an email domain regex
   res = jdb.find(vals={'email': re.compile(r'.@example.com')})
   assert list(res) == ['user_1']

   # Find users where any attribute matches the regex
   res = jdb.find(ANY=re.compile(r'.@example.com'))
   assert list(res) == ['user_1']

   # Global regex search for strings containing 'li' (matches 'Alice', 'Charlie', 'linux')
   res = jdb.find(RE=r'li[a-z]')
   assert list(res) == ['user_1', 'user_3']

   # Match record keys with a compiled regex (e.g. 'user_1', 'user_2')
   res = jdb.show(re.compile(r'^user_[1-2]$'))
   assert list(res) == ['user_1', 'user_2']

5. Array / List Operations
~~~~~~~~~~~~~~~~~~~~~~~~~~

Query list sizes or elements at specific array indices.

.. code-block:: python

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

6. Lambda / Custom Functions (FUNC) & Pagination (limit)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For rules the operators do not cover, pass a Python callable. ``limit`` stops
the scan once enough results are found.

.. code-block:: python

   # Pass a lambda to evaluate both the key and the value dynamically
   # Example: find the first user whose age is an even number
   res = jdb.find(
       FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0,
      limit=1
   )
   assert list(res) == ['user_1']

   res2 = jdb.find(vals={'age.$mod': (2, 0)}, limit=1)
   assert res == res2

   # Users with an email
   res = jdb.find(vals={'email': lambda v: v != ''})
   assert list(res) == ['user_1', 'user_4']

   res2 = jdb.find(EXISTS='email')
   assert res == res2

   # Users without an email
   res = jdb.find(NOT={'email': lambda v: v != ''})
   assert list(res) == ['user_2', 'user_3']

   res2 = jdb.find(vals={'!$exists': 'email'})
   assert res == res2

   # For primitive stored values (non-nested), use the quick keyword arguments:
   jdb['simple_counter'] = 50
   res = jdb.find(EQ=50)
   assert list(res) == ['simple_counter']

   res = jdb.show(IN=[40, 50])  # Value in list
   assert list(res) == ['simple_counter']

Operators Reference
-------------------

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