Getting Started
===============

Installing **omni-json-db**
---------------------------

**omni-json-db has zero required dependencies.** It runs on a clean Python install using built-in pure-Python fallbacks, so this is all you need:

.. code-block:: bash

   pip install omni-json-db

For the fastest, full-featured build — C-accelerated serializers (``orjson`` / ``ormsgpack`` / ``msgspec`` / ``msgpack`` / ``bitarray``), extra compression codecs (``zstandard`` / ``lz4`` / ``brotli``), ``YAML`` value formats, and the ``BTrees`` key-index backend — install the ``full`` extra:

.. code-block:: bash

   pip install "omni-json-db[full]"

Or pick only what you need:

.. code-block:: bash

   pip install "omni-json-db[speed]"        # faster serializers only (drop-in, no new features)
   pip install "omni-json-db[compression]"  # zstd / lz4 / brotli value compression
   pip install "omni-json-db[yaml]"         # YAML
   pip install "omni-json-db[btree]"        # B-tree key-index backend

.. note::

   ``[speed]`` adds no features and changes no file format — it only swaps the
   default code paths for C implementations: ``orjson`` for JSON values,
   ``ormsgpack`` for MsgPack values, ``msgspec.msgpack`` for the KEY index rows
   (byte-identical output, the single hottest path in the engine), ``msgpack``
   for the value extension types and the streaming unpacker, and ``bitarray``
   for the dead-row bitmap. Anything missing falls back to a pure-Python
   implementation, so a clean install behaves identically — just slower. On PyPy
   the pure-Python paths are already fast, so ``orjson`` / ``msgspec`` are
   skipped there.

   The bundles (``[full]`` / ``[all]``) use self-referencing extras and need ``pip >= 21.2``. On an older pip (e.g. a stock Python 3.7), either upgrade pip (``python -m pip install -U pip``) or install the granular extras together, e.g. ``pip install "omni-json-db[speed,compression,yaml,btree]"``.


Basic
-----


.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database from file
   # Key-Value is Json+MsgPack without compression
   jdb = JDb("example.jdb")

   # Store data
   jdb["user1"] = {"name" : "Ryan", "role": "Developer"}
   
   # Retrieve data
   user = jdb["user1"]
   print(user["name"], user["role"]) # Output: Ryan Developer
   
All standard ``dict`` methods work: ``keys()``, ``values()``, ``items()``, ``get()``,  ``pop()``, ``setdefault()``, ``update()``.


Quick Start
-----------

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

Where to next
-------------

* :doc:`usage/writing` — inserting, bulk loading, in-memory databases
* :doc:`usage/queries` — the query engine and the full operator table
* :doc:`usage/history` and :doc:`usage/transactions` — undo, versions, rollback
* :doc:`specifications` — ``data_type``, ``zip_type`` and ``key_limit`` reference
