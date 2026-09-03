Dataclass Objects
=================

Any ``@dataclass`` with an ``id`` field can be written and read directly. The
object is flattened into a plain ``dict`` — ``id`` is lifted out to become the
record key — so the stored record is an ordinary one: still queryable, still
exportable to CSV, still readable under every ``data_type``.

.. code-block:: python

   from dataclasses import dataclass, field
   from datetime import date
   from decimal import Decimal
   from enum import Enum
   from typing import List, Optional
   from omni_json_db import JDb, Query

   class Role(str, Enum):
       ADMIN = 'admin'
       USER  = 'user'

   @dataclass
   class Address:
       city: str
       zipcode: str = ''

   @dataclass
   class User:
       id: str                                       # required: becomes the record key
       name: str
       age: int = 0
       role: Role = Role.USER
       tags: List[str] = field(default_factory=list)
       address: Optional[Address] = None
       joined: Optional[date] = None
       balance: Decimal = Decimal('0')

   jdb = JDb('users.jdb')

   # --- Create ---
   jdb += User('u1', 'Alice', 30, Role.ADMIN, ['python'], Address('Taipei', '110'), date(2024, 5, 1), Decimal('12.50'))
   jdb += [User('u2', 'Bob', 25), User('u3', 'Charlie', 35)] # batch: one transaction
   jdb |= User('u1', 'Ignored')                              # insert only: u1 exists, nothing changes
   jdb &= User('u2', 'Bobby', 26)                            # replace only
   jdb['u4'] = User('u4', 'Diana', 28)                       # explicit key

   # --- Read: members are filled in place, so one buffer can be reused ---
   user = User(id='', name='')
   jdb.get_dc('u1', user)
   print(user.role, user.address.city, user.balance) # Output: Role.ADMIN Taipei 12.50

   # --- Update ---
   user.age += 1
   jdb += user

   # --- Delete ---
   jdb -= user
   del jdb[User('u2', '')]
   del jdb[User('u3', ''), User('u4', '')] # del jdb['u3', 'u4']

   # --- Still an ordinary record: queries run against the fields ---
   jdb += [User('u5', 'Eve', 41, tags=['python']), User('u6', 'Frank', 22, address=Address('Taipei'))]
   print(jdb.find(Query().age > 28))
   # Output: {'u5': {'name': 'Eve', 'age': 41, 'role': 'user', 'tags': ['python'], ...}}

   print(jdb.find(vals={'address.city': 'Taipei'}))
   # Output: {'u6': {'name': 'Frank', 'age': 22, ..., 'address': {'city': 'Taipei', 'zipcode': ''}, ...}}

For explicit control over the file pointer, ``f_write_dc`` / ``f_read_dc`` are
the low-level equivalents of ``f_write`` / ``f_read``:

.. code-block:: python

   with jdb.open(read_only=False) as fp:
      jdb.f_write_dc(fp, User('u9', 'Grace'), ttl=30)

   buf = User(id='', name='')
   with jdb.open() as fp:
      for key in jdb.key_table:
         jdb.f_read_dc(fp, key, buf) # filled in place: no allocation per record

Supported field types: nested dataclasses, ``Optional`` / ``Union``, ``Enum``,
``date`` / ``time`` / ``datetime``, ``Decimal``, ``UUID``, ``Path``, ``List`` /
``Dict`` / ``Set`` / ``Tuple``, ``frozen=True``, and ``init=False`` fields.
Values are rebuilt from the annotations, so a ``Set[str]`` comes back as a
``set`` even under a ``data_type`` whose codec has no native set type.

.. note::
   ``id`` is stored as the record key and is *not* duplicated inside the value,
   so ``jdb += user`` and ``jdb['u1'] = user`` write identical bytes. Filing an
   object under a different key (``jdb['alias'] = user``) keeps ``id`` inside the
   value instead, so the original identity survives the round-trip.

   This is what separates the mapping from ``data_type='J+P'``: pickle would
   store the object as an opaque blob, ending queries, CSV export, and
   cross-language reads. Here the record stays a normal dict, so ``find()``,
   ``update_if()``, ``show()``, and ``to_csv()`` keep working on its fields.
