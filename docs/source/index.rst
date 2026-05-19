|Logo|

..

   A nimble squirrel swiftly gathers a golden forest’s worth of acorns!

|Version| |Build Status| |Pylint| |Codacy| |Coverage| |License|


.. omni-json-db documentation master file, created by
   sphinx-quickstart on Mon May 18 11:13:03 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

|Python Version|


Welcome to omni-json-db!
-------------------------
**omni-json-db** is a high-performance, embedded database engine designed for Python developers. It bridges the gap between the extreme speed of a Key-Value store and the powerful querying capabilities of a document database.

Built for ultra-high throughput and thread-safety, **omni-json-db** leverages modern serialization (*JSON*, *MsgPack*, *marshal*, *pickle*, *YAML*) and compression to provide a storage layer that is often significantly faster than *SQLite* for *JSON*-heavy workloads. Whether you are building a local cache, a log aggregator, or a distributed microservice, **omni-json-db** provides the tools to handle data at scale with "Zero-Config" simplicity.

Unlike traditional *SQLite* or *NoSQL* databases, **omni-json-db** allows you to use native Python syntax (slicing, Lambdas, Regex, Set operations) to query and manipulate data. It also features built-in "Time-Travel", state rollbacks (Undo/Redo).

* **Schema-LESS**: Store complex, nested data without pre-defining tables.

* **Server-LESS**: Direct disk access without the overhead of a database server.

* **SQL-LESS**: Use native Python syntax, Regex, and Lambdas for data manipulation.

**Installation**:

.. code-block:: bash

   pip install omni-json-db

**Quick Start**:

.. code-block:: python

   from omni_json_db import JDb

   # Initialize the database
   jdb = JDb("example.jdb")

   # Store data
   jdb["user:1"] = {"name": "Ryan", "role": "Developer"}

   # Retrieve data
   print(jdb["user:1"]["name"]) # Output: Ryan

   # Bulk Update
   jdb += {
       "user:2": {"name": "Alice", "role": "Admin"},
       "user:3": {"name": "Bob", "role": "Developer"}
   }

   # Query data
   matches = jdb.find(ANY="Alice")
   print(matches["user:2"]["name"]) # Output: Alice

API Reference
-------------

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/modules


.. |Logo| image:: https://raw.githubusercontent.com/lukatrum/omni-json-db/master/artwork/logo.png
      :height: 400px
      :target: https://pypi.python.org/pypi/omni-json-db/

.. |Build Status| image:: https://img.shields.io/pypi/status/omni-json-db?logo=python&logoColor=white
   :alt: PyPI - Status
   :target: https://github.com/lukatrum/omni-json-db

.. |Version| image:: https://img.shields.io/pypi/v/omni-json-db?pypiBaseUrl=https%3A%2F%2Fpypi.org&logo=pypi&logoColor=white
   :alt: PyPI - Version
   :target: https://pypi.python.org/pypi/omni-json-db/

.. |Python Version| image:: https://img.shields.io/pypi/pyversions/omni-json-db?logo=python&logoColor=white
   :alt: PyPI - Python Version

.. |License| image:: https://img.shields.io/pypi/l/omni-json-db?color=800080&logo=ticktick&logoColor=white
   :alt: PyPI - License
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/LICENSE

.. |Pylint| image:: https://img.shields.io/github/actions/workflow/status/lukatrum/omni-json-db/pylint.yml?label=pylint&logo=lintcode&logoColor=white
   :alt: GitHub Actions Workflow Status
   :target: https://github.com/Lukatrum/omni-json-db/actions/workflows/pylint.yml

.. |Coverage| image:: https://img.shields.io/codecov/c/github/lukatrum/omni-json-db?logo=codecov&logoColor=white
   :alt: Codecov
   :target: https://github.com/Lukatrum/omni-json-db/actions/workflows/codecov.yml

.. |Codacy| image:: https://app.codacy.com/project/badge/Grade/861e1d81ccad4b8292d0062413b6daec    
   :target: https://app.codacy.com/gh/Lukatrum/omni-json-db/dashboard?utm_source=gh&utm_medium=referral&utm_content=&utm_campaign=Badge_grade

