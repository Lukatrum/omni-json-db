Examples
==============

Queries
------------------

**omni-json-db** is equipped with an exceptionally powerful and flexible NoSQL-like query engine. Through a single ``find()`` method, you can execute deep structural queries, regular expressions, logical combinations, and even custom Python functions.


Let's initialize an in-memory JDb instance (``jdb = JDb()``) and populate it with some sample JSON-like data to demonstrate the querying capabilities.

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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

