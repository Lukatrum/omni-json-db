Getting Started
===============


Installating **omni-json-db**
-------------------------------

**omni-json-db has zero required dependencies.** It runs on a clean Python install using built-in pure-Python fallbacks, so this is all you need:

.. code-block:: bash

   pip install omni-json-db

For the fastest, full-featured build — C-accelerated serializers(``orjson`` / ``ormsgpack`` / ``msgpack``), extra compression codecs(``zstandard`` / ``lz4`` / ``brotli``), ``YAML`` value formats, and the ``BTrees`` key-index backend — install the ``full`` extra:

.. code-block:: bash

   pip install "omni-json-db[full]"

Or pick only what you need:

.. code-block:: bash

   pip install "omni-json-db[speed]"        # faster serializers only (drop-in, no new features)
   pip install "omni-json-db[compression]"  # zstd / lz4 / brotli value compression
   pip install "omni-json-db[yaml]"         # YAML value formats
   pip install "omni-json-db[btree]"        # B-tree key-index backend

.. note::

   The bundles (``[full]`` / ``[all]``) use self-referencing extras and need ``pip >= 21.2``. On an older pip (e.g. a stock Python 3.7), either upgrade pip (``python -m pip install -U pip``) or install the granular extras together, e.g. ``pip install "omni-json-db[speed,compression,yaml,btree]"``.


Quick Start
------------

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
