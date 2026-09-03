Pythonic Queries
================

For a Pythonic, object-oriented filtering syntax (similar to the **TinyDB**
experience), **omni-json-db** provides the ``Query`` object. Native Python
operators (``==``, ``>``, ``&``, ``|``, ``~``) and chained methods build the
same conditions the dictionary syntax expresses.

.. code-block:: python

   from omni_json_db import JDb, Query

   # 1. Initialize database and add test data
   jdb = JDb()
   jdb += {
       'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
       'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
       'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
       'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # 2. Create a Query instance
   User = Query()

   # Basic Comparison: Find users older than 28
   res = jdb.find(User.age > 28)
   assert set(res) == {'user_1', 'user_3'}

   # Logical Combinations (AND & OR): Find developers under 30 OR admins
   res = jdb.find((User.role == 'developer') & (User.age < 30) | (User.role == 'admin'))
   assert set(res) == {'user_1', 'user_2'}

   # Array Query: Find users whose tags include 'python'
   res = jdb.find(User.tags.has('python'))
   assert set(res) == {'user_1', 'user_3'}

   # Path Wildcard: Regex search across all fields recursively
   res = jdb.find(User['**'].matches(r'.@example\.com'))
   assert set(res) == {'user_1'}

   # Advanced Filters: Find users who DO NOT have an 'email' field (~ is the NOT operator)
   res = jdb.find(~User.exists('email'))
   assert set(res) == {'user_2', 'user_3'}

   # Lambda Test: Find users whose age is an even number
   res = jdb.find(User.age.test(lambda age: age % 2 == 0), sort=User.name, reverse=True)
   assert set(res) == {'user_1', 'user_4'}

   # rename admin to Administrator
   res = jdb.update_if(User.role == 'admin', {'role': 'Administrator'})
   assert res == 1 and (User.role == 'Administrator') in jdb

   # sorted by user name
   res = jdb.show(sort=User.name, reverse=True)
   assert res == jdb

   # grouped by user role
   res = jdb.show(group_by=User.role) # jdb.show(group_by='role')
   assert 'developer' in res

   res = jdb.show(group_by={'role':['name', 'age.$avg']})
   assert 'developer' in res

Methods & Operators Reference
-----------------------------

.. list-table::
   :widths: 20 40 30
   :header-rows: 1

   * - Syntax / Operator
     - Description
     - Example Usage
   * - ``==``, ``!=``
     - Equals / Not equals
     - ``User.name != 'Bob'``
   * - ``>``, ``>=``, ``<``, ``<=``
     - Numeric comparison
     - ``User.age > 30``, ``User.age < 30``
   * - ``&``
     - Logical AND
     - ``(User.age > 20) & (User.role == 'admin')``
   * - ``|``
     - Logical OR
     - ``(User.name == 'Alice') | (User.age < 30)``
   * - ``~``
     - Logical NOT
     - ``~ User.exists('email')``
   * - ``.has(val)``
     - Contains specific string or array element
     - ``User.tags.has('database')``
   * - ``.not_has(val)``
     - Does not contain specific string or array element
     - ``User.name.not_has('ice')``
   * - ``.ihas(val)``
     - Case-insensitive contains
     - ``User.name.ihas('alice')``
   * - ``.startswith(val)``
     - String starts with prefix
     - ``User.city.startswith(('L', 'H'))``
   * - ``.endswith(val)``
     - String ends with suffix
     - ``User.name.endswith('b')``
   * - ``.matches(pattern)``
     - Regular expression search (equivalent to ``re.search``)
     - ``User.name.matches(r'[bB]ob')``
   * - ``.fullmatch(pattern)``
     - Regular expression full match (equivalent to ``re.fullmatch``)
     - ``User.name.fullmatch(r'.lic.')``
   * - ``.one_of(col)``
     - Value is within the specified collection
     - ``User.role.one_of(['admin', 'dev'])``
   * - ``.not_in(col)``
     - Value is not within the specified collection
     - ``User.role.not_in(['admin', 'dev'])``
   * - ``.any_in(col)``
     - Any element in the array is within the specified collection
     - ``User.role.any_in(['admin', 'ceo'])``
   * - ``.between(low, high)``
     - Value or string is within the specified range
     - ``User.age.between(20, 30)``
   * - ``.size_of(size)``
     - Array or string length matches
     - ``User.tags.size_of(2)``
   * - ``.exists(fields)``
     - Checks if specified fields exist
     - ``User.exists('email')``
   * - ``.type_of(type)``
     - Checks the data type
     - ``User.age.type_of(int)``
   * - ``.mod(div, rem)``
     - Modulo condition (remainder is ``rem`` when divided by ``div``)
     - ``User._date.mod(7, 5)``
   * - ``.near(target, tol)``
     - Numeric value is near the target within tolerance ``tol``
     - ``User._date.near(today, 1)``
   * - ``.test(func)``
     - Passes a custom Lambda function for condition evaluation
     - ``User.age.test(lambda v: 40 >= v > 18)``
   * - ``.abs()``
     - Takes the absolute value of a number before comparing.
     - ``Query().price.abs() == 3.14``
   * - ``.ceil()``
     - Takes the ceiling (math.ceil) of a number before comparing.
     - ``Query().price.ceil() > 3``
   * - ``.floor()``
     - Takes the floor (math.floor) of a number before comparing.
     - ``Query().price.floor() <= 2``
   * - ``.round()``
     - Round a number before comparing.
     - ``Query().price.round() == 2``
   * - ``.float()``
     - Casts the value to a float before comparing.
     - ``Query().price.float() == 2.1``
   * - ``.int()``
     - Casts the value to an integer before comparing.
     - ``Query().price.int() != 1``
   * - ``.neg()``
     - Negates the value (``-val``) before comparing.
     - ``Query().price.neg() == -1.2``
   * - ``.str()``
     - Casts the value to a string before comparing.
     - ``Query().price.str() == '1.2'``
   * - ``.avg()``
     - Calculates the arithmetic mean of an iterable before comparing.
     - ``Query().prices.avg() == 2.5``
   * - ``.std()``
     - Calculates the population standard deviation of an iterable before comparing.
     - ``Query().prices.std() >= 2.0``
   * - ``.max()``
     - Finds the maximum value in an iterable before comparing.
     - ``Query().prices.max() == 4``
   * - ``.mid()``
     - Extracts the middle element or character (index ``len//2``) before comparing.
     - ``Query().prices.mid() == 4``
   * - ``.min()``
     - Finds the minimum value in an iterable before comparing.
     - ``Query().prices.min() == 1``
   * - ``.sum()``
     - Calculates the sum of an iterable before comparing.
     - ``Query().prices.sum() == 8``
   * - ``.first()``
     - Extracts the first item or character before comparing.
     - ``Query().prices.first() == 1``
   * - ``.flat()``
     - Flattens a nested iterable before comparing.
     - ``Query().prices.flat().max() == 4``
   * - ``.last()``
     - Extracts the last item or character before comparing.
     - ``Query().prices.last() == 3``
   * - ``.len()``
     - Calculates the length of an array or string before comparing.
     - ``Query().prices.len() == 3``
   * - ``.sort()``
     - Sorts the iterable values before comparing.
     - ``Query().prices.sort().mid() == 2``
   * - ``.unique()``
     - Performs order-preserving deduplication on an iterable before comparing.
     - ``Query().prices.unique().first() == 1``
   * - ``.lower()``
     - Converts a string to lowercase before comparing.
     - ``Query().name.lower() == 'alice'``
   * - ``.upper()``
     - Converts a string to uppercase before comparing.
     - ``Query().name.upper() == 'ALICE'``
   * - ``.strip()``
     - Strips leading and trailing whitespaces from a string before comparing.
     - ``Query().name.strip() == 'Hi'``
   * - ``field['field']``
     - Accesses a specific field
     - ``User['addr'].city``, ``User.addr.city``
   * - ``.field[0]``
     - specific index of an array (supports negative index like ``User.tags[-1]``)
     - ``User.tags[1].has('db')``
   * - ``'*'`` / ``'**'`` / ``'?'``
     - First-level wildcard / Recursive multi-level wildcard / Single-char wildcard path search
     - ``User['*']``, ``User['**']``, ``User['ci?y']``, ``User['c*y']``
   * - ``._id`` / ``._date``
     - system reserved keys: access Document ID (Primary key) and Timestamp respectively
     - ``User._id``, ``User._date``
