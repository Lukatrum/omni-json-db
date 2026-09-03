|Version| |License|

|Logo|

..

   A nimble squirrel swiftly gathers a golden forest’s worth of acorns!

|Build Status| |Pylint| |Codacy| |Coverage|


.. omni-json-db documentation master file, created by
   sphinx-quickstart on Mon May 18 11:13:03 2026.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

|Python Version|


Welcome to omni-json-db!
========================

**omni-json-db** is a zero-config, powerful JSON database with compression. No schema, no setup, just data.

.. code-block:: python
   
   >>> from omni_json_db import JDb
   >>> jdb = JDb('db.jdb')
   >>> jdb += [{'name': 'John', 'age': 22}]
   >>> jdb.find(ANY='John')
   {'0': {'name': 'John', 'age': 22}}


User's Guide
========================

.. toctree::
   :maxdepth: 2

   intro
   getting-started
   usage/index


Reference
========================

.. toctree::
   :maxdepth: 2

   specifications
   benchmark
   api/modules

Additional Notes
========================

.. toctree::
   :maxdepth: 2

   contribute


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

