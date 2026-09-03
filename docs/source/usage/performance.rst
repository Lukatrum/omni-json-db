Faster Open
===========


Opening a database with ``key_limit='no'`` builds the key table by scanning the
whole KEY file. Two independent options take that cost off the critical path;
both are off by default.

**Key-table snapshot —** ``index_cache=True``
   Keeps a disposable copy of the table beside the database — ``<KEY>.KIX`` on
   disk, a shared buffer for ``JMemFiles``, a server-side sidecar over
   ``JNetFiles`` — so the next handle fast-forwards to the snapshot and scans
   only the rows written since.

**Warm-up —** ``warm_up=True``
   Builds the table on a background thread the moment the instance is created,
   so application start-up overlaps with the load instead of the first
   ``open()`` paying for all of it.

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb('data/app.KEY', key_limit='no', index_cache=True, warm_up=True)
   with jdb.open() as fp:       # restored from the snapshot, and already warmed
      ...

   # or drive both by hand
   jdb = JDb('data/app.KEY', key_limit='no', index_cache=True)
   th  = jdb.warm_up()          # the Thread, or None when there is nothing to warm
   jdb.insert(rows)
   jdb.save_index()             # take control of when the snapshot lands, e.g. after an import

``save_index()`` returns ``False`` when it declines to write — most often
because the database is still below ``JIo.min_kix_rows``. Pass
``save_index(force=True)`` to snapshot anyway.

Measured on 300,000 records (16-byte keys, ``key_limit='no'``):

+--------------------------------+-----------+---------------------+
|                                | full scan | ``.KIX``            |
+================================+===========+=====================+
| cold open (median)             | 326 ms    | 80 ms (**4.1x**)    |
+--------------------------------+-----------+---------------------+
| ``save_index()``               | —         | 19.5 ms             |
+--------------------------------+-----------+---------------------+
| sidecar size                   | —         | 7.5 MB (25 B/key)   |
+--------------------------------+-----------+---------------------+

The snapshot is written on its own when a close leaves the sidecar far enough
behind, and is skipped entirely below ``JIo.min_kix_rows`` (16,384 records),
where a full scan is cheaper than maintaining one. A snapshot that does not
match the KEY file — different layout or ``data_type``, a database newer than
the sidecar, a truncated, corrupted or foreign file — is rejected and the full
scan runs, so it can never serve a stale table. ``clear()``, an API change and
``resize_index_size()`` delete it outright.

.. note::

   Both options apply to the ``dict``-backed tables only (``key_limit='no'`` and
   ``'bt'``). ``LiteKeyTable`` (``'l0'``–``'l5'``) and ``PartialKeyTable``
   (``+ve``) load lazily and have nothing to snapshot or warm, so they silently
   do nothing. Warm-up *hides* latency rather than removing it: the load holds
   the GIL, so the caller only wins while it is waiting on I/O of its own, and a
   concurrent ``open()`` simply blocks until the table is complete — it can
   never see a half-filled one.
