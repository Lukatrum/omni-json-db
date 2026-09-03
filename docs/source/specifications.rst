Specifications
==============

Supported Data Formats
----------------------


Configure ``data_type`` during initialization:

* ``J+J`` or ``S+J``: JSON/MsgPack Key + JSON Value
* ``J+S`` or ``S+S``: JSON/MsgPack Key + MsgPack Value (default)
* ``J+M`` or ``S+M``: JSON/MsgPack Key + Marshal Value
* ``J+P`` or ``S+P``: JSON/MsgPack Key + Pickle Value
* ``J+Y`` or ``S+Y``: JSON/MsgPack Key + YAML Value
* ``J+U`` or ``S+U``: JSON/MsgPack Key + User-Defined Value (pluggable codec, e.g. encryption)
* ``U+U``: User-Defined Key + User-Defined Value (pluggable codec for both)

Two legacy layouts are still accepted for reading databases written by early
releases: ``L+J`` (split Key + JSON Value) and ``M+M`` (Marshal Key + Marshal
Value). Neither is a good choice for a new database.

*Data size = 70,840,580 bytes (MB = 1,000,000 bytes, no zip)*

+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``data_type``     | size       | ratio | read     | write     | Pros           | Cons             |
+===================+============+=======+==========+===========+================+==================+
| ``J+J`` or ``S+J``| 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest write |* no set [a]_     |
|                   |            |       |          |           |* faster read   |* no tuple [a]_   |
|                   |            |       |          |           |* readable      |* weak bytes [b]_ |
|                   |            |       |          |           |                |* weak dict [c]_  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+S`` or ``S+S``| 47,616,008 | 1.48  | 77.4MB/s | 354.2MB/s |* smallest size |* no tuple [a]_   |
|                   |            |       |          |           |* faster read   |* unreadable      |
|                   |            |       |          |           |* faster write  |                  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+M`` or ``S+M``| 72,430,958 | 0.97  | 81.4MB/s | 177.1MB/s |* all type [d]_ |* bigger size     |
|                   |            |       |          |           |* fastest read  |* unreadable      |
|                   |            |       |          |           |                |* security issue  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+P`` or ``S+P``| 70,207,207 | 1.01  | 64.9MB/s | 22.8MB/s  |* all type [d]_ |* slower read     |
|                   |            |       |          |           |                |* slower write    |
|                   |            |       |          |           |                |* unreadable      |
|                   |            |       |          |           |                |* security issue  |
+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``J+Y`` or ``S+Y``| 181,894,885| 2.57  | 0.146MB/s| 0.352MB/s |* readable      |* biggest size    |
|                   |            |       |          |           |                |* slowest read    |
|                   |            |       |          |           |                |* slowest write   |
|                   |            |       |          |           |                |* no tuple [a]_   |
+-------------------+------------+-------+----------+-----------+----------------+------------------+

.. [a] convert to ``list``
.. [b] convert to hex string
.. [c] only support string key
.. [d] all type = ``str``, ``bytes``, ``bool``, ``int``, ``float``, ``list``, ``tuple``, ``set``, ``dict``, ``None``

Pluggable User-Defined Codec (U)
--------------------------------


``J+U``, ``S+U``, and ``U+U`` let you plug in your own codec instead of using a
built-in format. This is the extension point for encryption, custom
compression, protobuf, or any other serialization you want full control over.

* ``J+U`` / ``S+U``: Key stays JSON/MsgPack (readable/small), only the Value
  goes through your codec.
* ``U+U``: Both the Key row and the Value go through your own codec.

There are two ways to register a codec:

1. **Process-wide default** — register once, every ``JDb`` opened with a
   ``U`` data_type uses it.

.. code-block:: python

   from marshal import loads as marshal_loads, dumps as marshal_dumps
   from omni_json_db import JDb, register_user_val_codec

   # --- Process-wide default: encrypt every Value with Fernet ---
   from cryptography.fernet import Fernet
   fernet = Fernet(Fernet.generate_key())

   register_user_val_codec(
       dumps=lambda data: fernet.encrypt(marshal_dumps(data)),
       loads=lambda raw: marshal_loads(fernet.decrypt(raw)),
   )

   # Key=JSON (readable), Value=encrypted
   jdb = JDb("secure.jdb", data_type="J+U")
   jdb["alice"] = {"ssn": "123-45-6789", "balance": 42.5}

   # Re-open and decrypt transparently
   jdb2 = JDb("secure.jdb", data_type="J+U")
   assert jdb2["alice"] == {"ssn": "123-45-6789", "balance": 42.5}

2. **Per-instance** — pass ``val_codec=`` (and optionally ``key_codec=``) to
   ``JDb()`` so different instances (e.g. different tenants) can use
   different codecs/keys at the same time.

.. code-block:: python

   from marshal import loads as marshal_loads, dumps as marshal_dumps
   from omni_json_db import JDb, JIoVAL_U
   from cryptography.fernet import Fernet

   # --- Per-instance codec: each tenant gets its own encryption key ---
   def make_codec(fernet):
       codec = JIoVAL_U()
       codec.register(
           dumps=lambda data: fernet.encrypt(marshal_dumps(data)),
           loads=lambda raw: marshal_loads(fernet.decrypt(raw)),
       )
       return codec

   key_a = Fernet.generate_key()
   key_b = Fernet.generate_key()
   tenant_a = JDb("tenant_a.jdb", data_type="J+U", val_codec=make_codec(Fernet(key_a)))
   tenant_b = JDb("tenant_b.jdb", data_type="S+U", val_codec=make_codec(Fernet(key_b)))

Supported Zip Formats
---------------------


Configure ``zip_type`` during initialization:

* ``no``: no compression for Value (default)
* ``gz``: Gzip (mode=1) compression for Value
* ``bz``: Bzip2 (mode=9) compression for Value
* ``xz``: LZMA compression for Value
* ``zs``: Zstandard (mode=22) compression for Value (better than ``xz``)
* ``br``: Brotli (mode=6) compression for Value (better than ``gz``)
* ``z1``: Zstandard (mode=6) compression for Value (better than ``gz``)
* ``z2``: Zstandard (mode=11) compression for Value (better than ``gz``)
* ``lz``: LZ4 (mode=0) compression for Value

**Data size = 70,840,580 (MB = 1,000,000B)**

+-------------+------------+-------+----------+-----------+-----------------+----------------+
|``zip_type`` | size       | ratio | read     | write     | Pros            | Cons           |
+=============+============+=======+==========+===========+=================+================+
| ``no``      | 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest speed  |* biggest size  |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``gz``      | 16,915,844 | 4.18  | 65.5MB/s | 5.1MB/s   |* built-in       |* slower zip    |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``bz``      | 11,394,042 | 6.21  | 26.4MB/s | 10.8MB/s  |* better ratio   |* slowest unzip |
|             |            |       |          |           |* built-in       |* slower unzip  |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``xz``      | 11,340,548 | 6.24  | 54.9MB/s | 2.3MB/s   |* better ratio   |* slower zip    |
|             |            |       |          |           |* built-in       |* slower unzip  |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``zs``      | 11,119,665 | 6.37  | 73.0MB/s | 1.7MB/s   |* best ratio     |* slowest zip   |
|             |            |       |          |           |* faster unzip   |                |
|             |            |       |          |           |* better ``xz``  |                |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``br``      | 13,700,696 | 5.17  | 65.8MB/s | 25.3MB/s  |* better ``gz``  |                |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``z1``      | 14,738,859 | 4.80  | 73.6MB/s | 70.8MB/s  |* faster zip     |                |
|             |            |       |          |           |* faster unzip   |                |
|             |            |       |          |           |* better ``gz``  |                |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``z2``      | 13,799,407 | 5.13  | 72.7MB/s | 23.6MB/s  |* faster unzip   |                |
|             |            |       |          |           |* better ``gz``  |                |
+-------------+------------+-------+----------+-----------+-----------------+----------------+
| ``lz``      | 26,226,039 | 2.70  | 75.6MB/s | 202.4MB/s |* fastest zip    |* worst ratio   |
|             |            |       |          |           |* fastest unzip  |                |
+-------------+------------+-------+----------+-----------+-----------------+----------------+

Supported Key Table Formats
---------------------------

Configure ``key_limit`` during initialization:

* ``no``: ``dict`` for key_table (default)
* ``bt``: ``BTree`` for key_table (save 44.3% vs ``dict``)
* ``l0`` - ``l5``: ``LiteKeyTable`` modes (save 60-75% vs ``dict``)
* ``+ve``: ``PartialKeyTable`` — an integer caps how many keys stay resident, the rest are read from the KEY file on demand

``no`` and ``bt`` load the whole table on open, which is what ``index_cache``
and ``warm_up`` are for (see :doc:`usage/performance`). ``l0``–``l5`` and ``+ve`` load
lazily and need neither.

**Table size = 3,241,854 keys**

+---------------+--------+--------------+------------+--------------+
| ``key_limit`` | memory | key search   | HIT > get()| MISS > get() |
+===============+========+==============+============+==============+
| ``no``        | 519MB  | 48.59Mo/s    | 29.28Mo/s  | 18.3Mo/s     |
+---------------+--------+--------------+------------+--------------+
| ``bt``        | 289MB  | 3.46Mo/s     | 3.07Mo/s   | 8.04Mo/s     |
+---------------+--------+--------------+------------+--------------+
| ``l3``        | 85MB   | 2.01Mo/s     | 2.01Mo/s   | 1.59Mo/s     |
+---------------+--------+--------------+------------+--------------+