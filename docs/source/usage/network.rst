Network Mode
============

``run_files_server()`` turns a local **omni-json-db** instance into a networked
service. A client opens it by passing ``'host:port'`` in place of a file name,
and every API — including groups and queries — works unchanged.

**Server side**

.. code-block:: python

   from omni_json_db import JDb, run_files_server

   jdb = JDb('storage.jdb')

   # equivalent to: files='storage.jdb'
   run_files_server(host='127.0.0.1', port=59898, files=jdb)

   # write key to JDb
   jdb['remote-key'] = 'secret'

**Client side**

.. code-block:: python

   from omni_json_db import JDb

   # connect to files server
   jdb = JDb('127.0.0.1:59898')

   # read remote key from JDb
   print(jdb['remote-key']) # Output: secret

``JNetFiles`` is the file layer behind the client handle, so a network database
carries the same locking semantics as a local one — many readers, one writer.