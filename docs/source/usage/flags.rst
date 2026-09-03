Record Flags
============

Every record carries a set of ``JKeyFlag`` bits in the key index, giving it
file-system-like attributes. Set them with a ``chmod``-style string: a bare
letter or ``+`` sets a flag, ``-`` clears it, and anything you don't name keeps
its current value.

Flags come in three kinds. **Stored** flags are properties of the record and
persist on disk. **Derived** flags are maintained by the engine and cannot be
set by name. **Transient** flags describe a single call rather than a record —
they are never written to disk, and passing one leaves the record's stored
flags untouched.

**Stored — properties of the record**

======  ===============  =======================================================================================
Letter  Flag             Effect
======  ===============  =======================================================================================
``r``   ``READ_ONLY``    Writes and deletes are refused.
``a``   ``APPEND_ONLY``  The value may only grow; shrinking, rewriting and deleting are refused.
``p``   ``NO_DELETE``    Deletes are refused, but updates still go through — editable, never removed.
``h``   ``HIDDEN``       Skipped by ``find()`` / ``show()``; every other API still sees it.
``c``   ``NO_CACHE``     Never enters the LRU read cache — keeps big blobs from evicting hot records.
``v``   ``NO_REVERT``    No previous version is kept, so a hot counter never grows the index.
``0``   ``USER0``        Free for your application (``0``–``3``); carries no engine behaviour.
======  ===============  =======================================================================================

``READ_ONLY`` and ``APPEND_ONLY`` block deleting as well as writing, so
``NO_DELETE`` is the only way to say *this record may change, but must never
disappear* — the retention guarantee a config row or an account record wants.

**Derived — maintained by the engine**

======  ===============  =======================================================================================
Letter  Flag             Effect
======  ===============  =======================================================================================
``e``   ``EXPIRE``       The record has a TTL. Set it with ``ttl=`` (days, or a ``timedelta``), never by name.
``g``   ``GROUP``        The record holds a group. Never settable.
``l``   ``LINK``         A symbolic link; set it with ``set_link()``.
======  ===============  =======================================================================================

**Transient — properties of a single call**

======  ===============  =======================================================================================
Letter  Flag             Effect
======  ===============  =======================================================================================
``u``   ``UNLOCK``       Waives the read-only / append-only / no-delete locks for this one call, like ``sudo``.
``w``   ``EXCL``         Refuse the write if the key already exists — create-only.
``m``   ``MUST_EXIST``   Refuse the write if the key does *not* exist — update-only. The mirror of ``EXCL``.
``n``   ``NO_FOLLOW``    Read a ``LINK`` as its own target path instead of following it; on write, retarget it.
``y``   ``NO_ATIME``     Write without moving the modified date, so an existing TTL is not renewed.
``q``   ``QUIET``        Fail quietly: a lock refuses by return value instead of raising ``JLockError``.
======  ===============  =======================================================================================

Transient flags are passed to the operation itself, not to ``set_key_flags()``.
They are consumed rather than stored, so ``jdb.set(k, v, key_flags='w+r')``
refuses an existing key *and* stores ``READ_ONLY`` on a new one. Naming a
transient flag in a ``find()`` predicate raises ``JValueError`` rather than
silently matching every record.

**Refusals are loud, typos are louder**

Naming a locked record raises ``JLockError`` (a ``JKeyError``, so a ``KeyError``):
``jdb['config'] = x`` on a ``READ_ONLY`` row no longer looks like a successful
write. Two flags opt out, per call: ``'u'`` (``UNLOCK``) does it anyway, ``'q'``
(``QUIET``) refuses the old way — ``set()`` returns ``None``, ``remove()`` returns
``{}``, ``f_write()`` returns ``False`` and ``f_delete()`` returns ``LOCKED``.
Selector-driven sweeps (``jdb[re.compile(...)] = v``, ``update_if()``, ``jdb -= jdb``,
the CSV/INI/SQL importers, ``insert()`` and the other batch writers) keep skipping
what they may not touch — they are best-effort by design; only an explicitly
*named* key refuses loudly. ``EXCL`` (``'w'``) and ``MUST_EXIST`` (``'m'``) also
stay quiet: those are conditions the *caller* asked for, not a record saying no,
which is exactly what ``setdefault()`` is built on.

A malformed ``key_flags`` is a different thing and always raises ``JValueError``,
``'q'`` or not: an unknown letter (``key_flags='f'``) and an undefined bit
(``key_flags=0x200``, which ``KEY_FLAG_MASK`` was wide enough to write to disk)
used to be dropped without a word.

.. code-block:: python

   from omni_json_db import JDb, JKeyFlag, JLockError

   jdb = JDb()
   jdb['config']        = {'theme': 'dark'}
   jdb['audit/2026-08'] = ['created']

   # read-only: writes are refused, and say so
   jdb.set_key_flags('config', 'r')
   try:
       jdb['config'] = {'theme': 'light'}
   except JLockError as e:
       print(e)                            # write[config] refused: record is locked ...

   print(jdb.set('config', {'theme': 'light'}, key_flags='q'))
                                           # Output: None   (refused quietly)
   print(jdb['config'])                    # Output: {'theme': 'dark'}

   # append-only + no history: an audit log that can only grow
   jdb.set_key_flags('audit/2026-08', 'av')
   jdb['audit/2026-08'] = ['created', 'updated']   # extension -> allowed
   for bad in (['wiped'], 'not a list'):           # not an extension -> refused
       try:
           jdb['audit/2026-08'] = bad
       except JLockError:
           pass

   print(jdb.remove('audit/2026-08', key_flags='q'))   # delete refused too
                                           # Output: {}
   print(jdb['audit/2026-08'])             # Output: ['created', 'updated']

   # inspect, then unlock again ('-r' clears only READ_ONLY).
   # every flag API returns {key: (flags, ttl)}
   flags, ttl = jdb.get_key_flags('audit/2026-08')['audit/2026-08']
   print(str(JKeyFlag(flags)), ttl)        # Output: __a_v______________ 0
   jdb.set_key_flags('config', '-r')
   jdb['config'] = {'theme': 'light'}
   print(jdb['config'])                    # Output: {'theme': 'light'}

   # hidden: kept out of query results, but not a secret — items() still sees it
   jdb['_scratch'] = 'internal'
   jdb.set_key_flags('_scratch', 'h')
   print(list(jdb.find()))                 # Output: ['config', 'audit/2026-08']
   print(jdb['_scratch'])                  # Output: internal
   print(list(jdb.find(with_hidden=True))) # Output: ['config', 'audit/2026-08', '_scratch']

   # tag records for your own use, and combine flags freely
   jdb.set_key_flags('config', '+0')       # USER0
   jdb.keys.set_flags('config', '+c-0')    # add NO_CACHE, drop USER0

   # no-delete: the record stays editable, but nothing can remove it
   jdb['account/42'] = {'plan': 'pro'}
   jdb.set_key_flags('account/42', '+p')
   jdb['account/42'] = {'plan': 'team'}    # update -> allowed
   print(jdb['account/42'])                # Output: {'plan': 'team'}
   print(jdb.remove('account/42', key_flags='q'))
                                           # Output: {}
   print(jdb.remove('account/42', key_flags='u'))
                                           # Output: {'account/42': {'plan': 'team'}}

   # create-only ('w') and update-only ('m'), decided under the write handle
   # rather than by a test-then-write, so neither races another writer
   print(jdb.set('config', {'theme': 'dark'}, key_flags='w'))   # exists -> refused
                                           # Output: None
   print(jdb.set('session/abc', ['new'], key_flags='w'))
                                           # Output: ['new']
   print(jdb.set('session/xyz', ['nope'], key_flags='m'))       # absent -> refused
                                           # Output: None
   print(jdb.set('session/abc', ['touched'], key_flags='m'))
                                           # Output: ['touched']

   # no-follow: read the link itself instead of what it points at
   jdb.set_link('latest', 'config')
   print(jdb['latest'])                    # Output: {'theme': 'light'}
   print(jdb.get('latest', key_flags='n')) # Output: config

Expiring Records (TTL)
----------------------

A record can be given a lifetime with ``ttl=``, counted from the moment it was
last modified. Three argument types are accepted, and one rule decides the unit:

=================  =============================================================================
``ttl=``           Meaning
=================  =============================================================================
``int``            Whole days — ``ttl=7`` is a week. Clamped to ``MAX_TTL_DAYS`` (511).
``float``          Days, so a fraction falls through to minutes — ``0.25`` is 6 hours.
``timedelta``      Taken as it stands — ``timedelta(minutes=30)``, ``timedelta(hours=6)``.
=================  =============================================================================

**Anything under a day rounds up to whole minutes; a day or more rounds up to
whole days.** So ``timedelta(hours=23)`` is 1380 minutes, ``timedelta(hours=24)``
is 1 day and ``timedelta(hours=40)`` is 2 days. A positive lifetime never rounds
down to nothing: ``timedelta(seconds=1)`` is one minute, not "no TTL".

``ttl`` reads back as *days remaining* in the same form ``ttl=`` accepts — an
``int`` for a whole-day TTL, a ``float`` below ``1.0`` for a minute one — so a
value taken from ``get_key_flags()`` can be written straight back. Multiply by
``MIN_OF_DAY`` (1440) to read a sub-day TTL in minutes.

**A TTL never expires early.** Both units are stored coarsely — to the day or to
the minute — and a record stays readable through the end of its last day or
minute. A record written today with ``ttl=1`` is still there today and gone
tomorrow; a one-minute TTL lives between 61 and 120 seconds.

``EXPIRE`` is **derived**: it is set whenever the record has a TTL and cleared
when it does not. Naming ``'e'`` yourself does nothing — use ``ttl=``.

Because the countdown runs from the modified date, an ordinary write renews it.
Pass ``key_flags='y'`` (``NO_ATIME``) to update a record *without* extending its
life — the difference between touching a session and prolonging it.

.. code-block:: python

   import datetime as dt
   from omni_json_db import JDb, JKeyFlag, MIN_OF_DAY

   jdb = JDb()
   jdb['session/abc'] = {'user': 'ana'}

   # give an existing record a lifetime, in days
   print(jdb.set_key_flags('session/abc', ttl=7))
                                           # Output: {'session/abc': (128, 7)}
   flags, ttl = jdb.get_key_flags('session/abc')['session/abc']
   print(str(JKeyFlag(flags)), ttl)        # Output: _______e___________ 7

   # a TTL combines with the other flags, and survives a rewrite
   print(jdb.set_key_flags('session/abc', '+r'))
                                           # Output: {'session/abc': (129, 7)}

   # ttl=0 removes it; ttl=None (the default) leaves it untouched
   print(jdb.set_key_flags('session/abc', ttl=0))
                                           # Output: {'session/abc': (1, 0)}

   # sub-day lifetimes: a timedelta, or a fraction of a day
   jdb['cart/9'] = ['socks']
   print(jdb.set_key_flags('cart/9', ttl=dt.timedelta(minutes=30)))
                                           # Output: {'cart/9': (128, 0.020833333333333332)}
   ttl = jdb.get_key_flags('cart/9')['cart/9'][1]
   print(round(ttl * MIN_OF_DAY), 'minutes')
                                           # Output: 30 minutes

   # 0.25 of a day is 6 hours; a day or more becomes whole days
   print(jdb.set_key_flags('cart/9', ttl=0.25))
                                           # Output: {'cart/9': (128, 0.25)}
   print(jdb.set_key_flags('cart/9', ttl=1.5))
                                           # Output: {'cart/9': (128, 2)}

   # or set it as the record is written
   with jdb.open() as fp:
       jdb.f_write(fp, 'otp/123', '558021', ttl=1)
       jdb.f_write(fp, 'otp/456', '331902', ttl=dt.timedelta(seconds=90))

   print(jdb.get_key_flags('otp/123'))     # Output: {'otp/123': (128, 1)}
   print(round(jdb.keys['otp/456'][8] * MIN_OF_DAY), 'minutes')
                                           # Output: 2 minutes

   # jdb.set() takes it too, so a one-liner cache entry needs no open()
   jdb.set('tmp/quote', 41.2, ttl=dt.timedelta(minutes=10))

An expired record is gone from every read surface — ``jdb[key]``, ``in``,
``items()``, ``find()`` and ``show()`` all skip it — and the row is reclaimed
lazily on the next write that needs space, so expiry costs no background thread.

Symbolic Links
--------------

``set_link()`` points one key at another record, at a group, or at a key inside a
group. Reads and writes are forwarded to the target; deleting the link leaves the
target alone.

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb()
   reports = jdb.add_group('reports')
   reports['2026-08'] = {'rows': 12}

   # link to a record inside a group
   jdb.set_link('latest', 'reports:::2026-08')
   print(jdb['latest'])                    # Output: {'rows': 12}

   jdb['latest'] = {'rows': 13}            # writes through to the target
   print(reports['2026-08'])               # Output: {'rows': 13}

   # link to a whole group, like a folder
   jdb.set_link('current', 'reports')
   print(jdb['current']['2026-08'])        # Output: {'rows': 13}

   print(jdb.get_link('latest'))           # Output: reports:::2026-08
   del jdb['latest']                       # removes the link only
   print(reports['2026-08'])               # Output: {'rows': 13}

   # 'n' (NO_FOLLOW) reads or rewrites the link itself instead of its target
   jdb.set_link('newest', 'reports:::2026-08')
   print(jdb.get('newest', key_flags='n')) # Output: reports:::2026-08

   reports['2026-09'] = {'rows': 20}
   jdb.set('newest', 'reports:::2026-09', key_flags='n')   # retarget in place
   print(jdb['newest'])                    # Output: {'rows': 20}

``NO_FOLLOW`` is ``open(O_NOFOLLOW)`` rather than ``readlink()``: a record that
is *not* a link still reads normally, where ``get_link()`` reports that it is
not a link.

.. note::

   Flags are enforced by the library, not by the operating system — an older
   release reading the same file will not know about newer flags. ``HIDDEN`` in
   particular is **not** access control: it only filters ``find()`` and
   ``show()``, so ``dict(jdb.items())`` still contains the record. ``EXPIRE`` is
   not access control either — expiry is measured in whole days against the
   local clock, so it is a housekeeping tool, not a security deadline. A flag on
   a group row applies to that row alone, not to the records inside the group.
   
