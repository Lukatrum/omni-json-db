English_ | 中文_
~~~~~~~~~~~~~~~~
.. _English: https://github.com/lukatrum/omni-json-db/
.. _中文: https://github.com/Lukatrum/omni-json-db/blob/main/README-tc.rst

|Logo|

..

	一隻敏捷的小松鼠迅速地收集森林裡的金色橡子！

|Version| |Build Status| |Pylint| |Codacy| |Coverage| |License|


📌 支援的 Python 版本
*********************

**omni-json-db** 已在 Python 3.7+ 和 PyPy3 上通過測試。
|Python Version|
..

   如果您覺得 **omni-json-db** 對您有所幫助，請考慮給它一個⭐️！ 這能幫助專案成長並接觸到更多開發者。

👉 快速連結
***********

- `✨ 簡介`_
- `🛠️ 快速入門`_
- `📝 規格說明`_
- `📊 基準測試`_
- `📄 說明文檔 <https://omni-json-db.readthedocs.io>`_
- `👥 貢獻指南`_

✨ 簡介
*******
**omni-json-db** 是一款專為 Python 開發者設計的高效能嵌入式資料庫引擎。 它填補了極速鍵值（Key-Value）儲存與強大文件資料庫查詢功能之間的空白。   

**omni-json-db** 專為超高吞吐量和執行緒安全而構建，利用現代序列化技術（如 *JSON*、*MsgPack*、*marshal*、*pickle*、*YAML*）和壓縮算法，提供了一個在處理大量 *JSON* 工作負載時通常比 *SQLite* 快顯著許多的儲存層。 無論您是在構建本地快取、日誌聚合器還是分散式微服務，它都能以「零配置」的簡易性處理大規模資料。

與傳統的 *SQLite* 或 *NoSQL* 資料庫不同，**omni-json-db** 允許您使用原生的 Python 語法（切片、Lambdas、正則表達式、集合運算）來查詢和操作資料。 它還內建了「時光旅行」功能，支援狀態回滾（復原/重做）。   

* **無模式 (Schema-LESS)**：無需預先定義表格即可儲存複雜、嵌套的資料。   

* **無伺服器 (Server-LESS)**：直接存取磁碟，沒有資料庫伺服器的額外開銷。   

* **無SQL (SQL-LESS)**：使用原生 Python 語法、正則表達式和 Lambdas 進行資料操作。   

🚀 核心特性
***********

* **深度 Python 化**：告別 SQL！ 使用標準 Python ``dict`` 方法、切片甚至是 ``set`` 運算與資料庫互動。 [參考 `基本用法`_ + `運算子`_]  

* **動態序列化與進階壓縮**：混合搭配 JSON (*orjson*)、MsgPack (*ormsgpack*)、Marshal、Pickle 和 YAML，並結合 LZ4、Zstandard (z1/z2/zs)、Brotli 及 Bzip2 等壓縮算法，完美平衡 I/O 速度與磁碟佔用空間。[參考 `轉換格式`_ + `資料種類`_ + `壓縮種類`_]

* **強大的查詢引擎**：使用正則表達式 (Regex)、Lambda 過濾器（如 ``jdb[lambda k, v: v > 10]``）及豐富的條件運算子（``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``）輕鬆搜尋。 [參考 `查詢引擎`_]

* **記憶體快取**：可調整的 ``cache_limit`` 用以平衡記憶體使用率與 I/O 速度。 [參考 `快取種類`_]

* **網路模式 (``JNetFiles``)**：只需一個指令``run_files_server()``，即可將本地實例轉換為網路服務。 [參考 `網路模式`_]

* **記憶體模式 (``JMemFiles``)**：在記憶體內運行整個資料庫，實現極致效能（適用於即時快取或暫時性會話儲存）。 [參考 `記憶體模式`_]

* **時光旅行」與回滾**：資料庫會追蹤內部狀態，允許您復原修改 (``unmodify()``) 或救回刪除的資料 (``unremove()``)。 [參考 `救回`_ + `備份 / 復原`_]

* **分組與命名空間**：使用群組（Groups）輕鬆隔離並管理不同的資料模組。 [參考 `群組模式`_]

* **原生 CSV 支援**：內建 ``DictReader`` 和 ``DictWriter`` 接口，可從 *CSV* 匯入海量資料或匯出至 *Excel*/*Pandas* 進行分析。 [參考 `CSV 匯入 / 匯出`_]

* **無縫資料遷移**：一行代碼即可完成匯入匯出！ 內建引擎可將關聯式資料庫 (*SQLite*) 轉換為 *NoSQL* 群組結構，並支援 *INI*、*TOML* 配置解析。 [參考 `SQLite 匯入`_ + `INI / TOML 匯入`_]

* **時間序列支援**：每條記錄都帶有時間戳，支援強大的日期切片查詢。 例如使用 ``jdb[yesterday:now]`` 獲取自昨天以來修改的所有記錄。 [參考 `時間序列`_]

* **並行控制**：針對「多讀/單寫」環境優化，具備可靠的文件鎖定機制。 [參考 `進階用法`_]

🛠️ 快速入門
***********

安裝
----

.. code-block:: bash

   pip install omni-json-db

基本用法
-------

.. code-block:: python

   from omni_json_db import JDb
   
   # 初始化 Json+mSgpack，不壓縮，檔案模式
   jdb = JDb("example.jdb")

   # 儲存資料
   jdb["用家1"] = {"名字" : "小明", "職位": "程式員"}
   
   # 讀取資料
   user = jdb["用家1"]
   print(user["名字"], user["職位"]) # 輸出: 小明 程式員

   
支援所有標準 ``dict`` 方法: ``keys()``, ``values()``, ``items()``, ``get()``, ``set()``, ``pop()``, ``setdefault()``, ``update()``.

記憶體模式
---------

.. code-block:: python

   from omni_json_db import JDb
   # 初始化 Json+mSgpack，不壓縮，記憶體模式
   jdb1 = JDb()

   # 儲存資料
   jdb1 += {"用家1" : {"名字" : "小強", "職位": "老程式員"}}
   
   # 讀取資料
   print(jdb1["用家1"]["名字"], user["職位"]) # 輸出: 小強 老程式員

   # 建立共享同一塊記憶體的第二個 JDb
   jdb2 = JDb(jdb1)
   jdb2["用家2"] = {"名字" : "小美", "職位": "老闆"}

   # 透過第一個 JDb 讀取新插入的資料
   print(jdb1["用家2"]["名字"]) 輸出: 小美


查詢引擎
-------

.. code-block:: python

   from omni_json_db import JDb

   # 初始化 Json+Marshal，無壓縮，記憶體模式
   jdb = JDb(data_type="J+M")
   
   # 批量插入無鍵記錄
   jdb += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]
   
   # 獲取所有記錄
   print(jdb[:])

   # 使用 Lambda 函式搜尋名為 'John' 的記錄
   matches = jdb.find(FUNC=lambda key,val: val['name'] == 'John') 
   print(matches) # 輸出: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}}

   # 使用正則表達式搜尋 'John' 或 'Bob'
   matches = jdb.find(RE='John|Bob')
   print(matches) # 輸出: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}, '2': {'name': 'Bob', 'age': 42}} 


條件運算子包含: ``EQ``, ``NE``, ``GT``, ``LT``, ``GE``, ``LE``, ``HAS``, ``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOT``, ``SIZE``, ``ANY``.


救回
----

.. code-block:: python

   from omni_json_db import JDb
   
   # 初始化 Json+Pickle，ZStandard壓縮，檔案模式
   jdb = JDb("fruit.jdb", data_type="J+P", zip_type='zs')

   # 寫入
   jdb["apple"] = "red"

   # 修改
   jdb["apple"] = "blue" 

   # 還原 (相等於jdb.unmodify())
   jdb.revert("apple")
   assert jdb["apple"] == 'red'

   # 移除
   del jdb["apple"] 
   assert "apple" not in jdb

   # 還原 (相等於jdb.unremove())
   jdb.revert("apple")
   assert jdb["apple"] == "red"

備份 / 復原
----------------

.. code-block:: python

   from omni_json_db import JDb
   
   # 初始化 mSgpack+Json，Brotli壓縮，檔案模
   jdb = JDb("fruit.jdb", data_type="S+J", zip_type='bz')

   # 寫入水果到JDb
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits
   assert jdb == fruits

   # 備份至bak檔案夾 = ./bak/fruit.jdb
   jdb_bak = jdb.backup(folder='bak')
   assert jdb_bak == fruits
   
   # 移除所有資料
   del jdb[fruits]
   assert len(jdb) == 0

   # 從bak檔案夾還原jdb
   jdb.restore(folder='bak')
   assert jdb == fruits
   
群組模式
-----------

.. code-block:: python

   from omni_json_db import JDb
   
   # 初始化 Json+mSgpack，無壓縮，檔案模式
   jdb = JDb('fruit_group.jdb')

   # 新增 red 群組
   r_jdb = jdb.add_group('red')
   assert r_jdb is jdb['red']

   # 新增yellow群組
   y_jdb = jdb.add_group('yellow')
   assert y_jdb is jdb['yellow']

   # 批量增加水果至red群組
   r_jdb += {'apple': {'qty':1}, 'tomato': {'qty':2}}

   # 批量增加水果至yellow群組
   y_jdb += {'banana': {'qty':4}, 'lemon': {'qty':6}, 'mango': {'qty':8}}

   # 讀取red群組
   print(jdb['red']['apple']['qty'])   # 輸出: 1
   print(jdb['red:::apple'])           # 輸出: {'red:::apple': {'qty': 1}}
   print(jdb['yellow:::banana'])       # 輸出: {'yellow:::banana': {'qty': 4}}

   # 查詢所有群組的水果有'a'字
   matches = jdb.find(r':::a')
   print(matches) # 輸出: ['red:::apple', 'red:::tomato', 'yellow:::banana', 'yellow:::mango']

CSV 匯入 / 匯出
-------------------

.. code-block:: python

   from omni_json_db import JDb
   
   # 初始化 Json+Json，無壓縮，記憶體模式
   jdb1 = JDb(data_type="J+J")

   # 批量插入無鍵記錄
   jdb1 += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]
   
   # 將JDb的內容匯出至 example.csv
   jdb1.to_csv('example.csv')

   # 建立另一個JDb
   jdb2 = JDb()
   
   # 從CSV檔案匯入至JDb
   jdb2.from_csv('example.csv')
   print(jdb2.find(RE='Bob')) # 輸出: {'name': 'Bob', 'age': 42}

INI / TOML 匯入
-----------------

.. code-block:: python
   
   from omni_json_db import JDb
   import io

   jdb = JDb()

   # --- 準備 INI 格式 ---
   ini_data = """
   [server]
   host = 127.0.0.1
   port = 8080
   """

   jdb.from_ini(io.StringIO(ini_data)) # 除了IO外，還支援檔案路徑 (例如:'config.ini')
   print(jdb['server/host']) # 輸出: 127.0.0.1

   # --- 準備 TOML 格式 ---
   toml_data = """
   app_name = "Omni Test"
   [network]
   ip = "192.168.1.1"
   port = 8181
   """
   
   jdb.from_toml(io.StringIO(toml_data)) # 除了IO外，還支援檔案路徑 (例如:'config.toml')

   print(jdb['/app_name'])    # 輸出: Omni Test
   print(jdb['network/ip'])   # 輸出: 192.168.1.1

SQLite 匯入
-------------

Step 1: Prepare *sample.sql*

.. code-block:: python

   import sqlite3
   conn = sqlite3.connect('sample.sql')
   cursor = conn.cursor()

   cursor.execute('''
   CREATE TABLE IF NOT EXISTS projects (
     id INTEGER PRIMARY KEY, 
     name text NOT NULL, 
     begin_date DATE, 
     end_date DATE
   )
   ''')

   cursor.execute('''
   CREATE TABLE IF NOT EXISTS project_logs (
     project_id INTEGER,
     action TEXT NOT NULL,
     log_date DATE
   )
   ''')

   cursor.execute('DELETE FROM projects')
   cursor.execute('DELETE FROM project_logs')

   projects_data = [
     (1, 'cooking', '2000-01-02', '2003-01-13'),
     (2, 'reading', '2023-05-01', '2023-12-31'),
     (3, 'coding', '2024-01-01', '2024-06-30')
   ]
   cursor.executemany('INSERT INTO projects (id, name, begin_date, end_date) VALUES (?, ?, ?, ?)', projects_data)

   logs_data = [
     (1, 'bought ingredients', '2000-01-01'),
     (1, 'started cooking', '2000-01-02'),
     (2, 'bought books', '2023-04-20'),
     (3, 'setup environment', '2024-01-01')
   ]
   cursor.executemany('INSERT INTO project_logs (project_id, action, log_date) VALUES (?, ?, ?)', logs_data)

   conn.commit()
   conn.close()

Step 2: Import to ``JDb``

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb("migrated_data.jdb")

   # Load an entire SQLite database with one line of code
   jdb.from_sqlite('sample.sql')

   # SQLite tables (e.g., 'projects' and 'project_logs') automatically become groups
   projects = jdb['projects']
   logs = jdb['project_logs']

   # Query relational data using the NoSQL interface
   print(projects[3]['name'])  # Get the name of the project with ID 3
   print(len(logs))            # Get the total number of logs

   # Combine with powerful Lambda queries to find logs for a specific project
   project_3_logs = logs.find(FUNC=lambda val: val['project_id'] == 3)

網路模式
------------

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

轉換格式
-----------

.. code-block:: python

   from omni_json_db import JDb

   # Initialize the database in memory
   # Key-Value is Json+Json with no compression
   jdb = JDb(data_type='J+J')

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # add all fruits to database
   jdb += fruits
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: J+J no

   # change date_type to 'S+S' and zip_type to 'lz'
   jdb.upgrade(data_type='S+S', zip_type='lz')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: S+S lz

   # only change KEY type from 'S' to 'J'
   jdb.change_KEY('J')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # Output: J+S lz

時間序列
------------

.. code-block:: python

   from omni_json_db import JDb
   import datetime as dt

   # Initialize the database in memory
   # Key+Value is Json+Json with Brotli compression
   # using BTree as Key Table for better memory usage
   jdb = JDb(data_type="J+J(gz)", key_limit="bt")

   # insert data
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits 

   # datetime for create date, date for modify date
   now = dt.datetime.now()
   today = now.date()
   
   # find create date: date == now
   matches = jdb[now]
   assert matches == fruits

   # find create date: date >= now
   matches = jdb[now:]
   assert matches == fruits

   # find create date: date < now
   matches = jdb[:now]
   assert len(matches) == 0

   # find create date: now <= date <= now+1
   next_date = now + dt.timedelta(days=1)
   matches = jdb[now:next_date]
   assert matches == fruits

   prev_date = now - dt.timedelta(days=1)
   prev_week = now - dt.timedelta(days=7)
   
   # change key create date
   jdb.keys['apple', 'tomato'] = prev_date
   jdb.keys['mango'] = prev_week
   assert jdb[prev_date] == {'apple':'red', 'tomato':'red'}
   assert jdb[prev_week] == {'mango':'yellow'}

   # find create date: date == now
   matches = jdb[now]
   assert set(matches) == {'banana', 'lemon'}

   # find create date: date < now
   matches = jdb[:now]
   assert set(matches) == {'apple', 'mango', 'tomato'}

   # find modify date: date == today
   matches = jdb[today]
   assert matches == fruits

   # change key modify date + create date
   new_modify_date = prev_date.date()
   new_create_date = prev_week.date()
   assert new_modify_date >= new_create_date
   jdb.keys['lemon'] = f'{new_modify_date} {new_create_date}'
   
   # find modify date: date == today   
   matches = jdb[today]
   assert set(matches) == {'apple', 'banana', 'mango', 'tomato'}

   # find modify date: date == prev_date
   matches = jdb[prev_date.date()]
   assert set(matches) == {'lemon'}

   # change all keys create date
   jdb.keys[:] = today
   assert jdb[today] == fruits

運算子
--------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key+Value is mSgpack+mSgpack with lz4 compression
   jdb = JDb(data_type="S+S(lz)")

   # [1] KEY+VAL operators
   # <jdb += data> == jdb.update(data)
   data = {f'key{v}':v for v in range(100)}   
   jdb += data
   assert len(jdb) == 100

   # <jdb == data>
   assert jdb == data

   # <jdb |= ..> == jdb.insert(..)
   jdb |= {f'key{v}':v+1 for v in range(102)}
   assert jdb['key100'] == 101
   assert jdb[-2.:] == {'key100':101, 'key101':102} # get last two modified records
   assert jdb[(f'key{v}' for v in range(100))] == data # equivalent to jdb[data] == data

   # <jdb -= ..> == jdb.remove(..)
   jdb -= ['key100', 'key101', 'key102', 'key103']
   assert jdb == data

   # <jdb &= ..> == jdb.replace(..)
   jdb &= {f'key{v}':v+1 for v in range(200)}
   assert jdb == {f'key{v}':v+1 for v in range(100)}

   # <jdb ^= ..> == jdb.unmodify(..)
   jdb ^= {f'key{v}' for v in range(100)} # equivalent to jdb ^= data
   assert jdb == data

   # <jdb[:] = ..> == jdb.update(..)
   jdb[:] = 0 # set all records to zero
   assert jdb == {f'key{v}':0 for v in range(100)}
   assert jdb.find(NE=0) == {}

   # remove all records
   jdb -= jdb # equivalent to del jdb[:]
   assert len(jdb) == 0

   # <jdb ^= ..> == jdb.unremove(..)
   jdb ^= {f'key{v}' for v in range(100)} # equivalent to jdb ^= data
   assert all(val == 0 for key,val in jdb.items())

   # lambda VALUE operation
   jdb[:] = lambda key,val: int(key.replace('key', '')) + val
   assert jdb == data

   # <del jdb[..]> == jdb.remove_fast(..)
   del jdb[data] # equivalent to del jdb[:]

   # unremove all data
   jdb ^= data
   assert jdb == data

   # <jdb[..]> == jdb.get_n(..) or jdb.get_all()
   matches = jdb[('key2', 'key22', 'key44', 'key111')]
   assert matches == {'key2':2, 'key22':22, 'key44':44}

   # lambda KEY operation
   matches = jdb[lambda key:key.endswith('1')]
   assert set(matches) == {'key1', 'key11', 'key21', 'key31', 'key41', 'key51', 'key61', 'key71', 'key81', 'key91'}

   # set all matched records to -1
   jdb[matches] = -1
   matches_2 = jdb[lambda key,val: val == -1]
   assert set(matches) == set(matches_2)
   assert matches_2 == jdb.find(EQ=-1)
   assert matches_2 == jdb.find(FUNC=lambda val: val == -1)

   # RE search
   matches_3 = jdb[::r'1$']
   assert matches_2 == matches_3

   # unmodify
   jdb ^= matches
   assert jdb == data

   # [2] KEY operators
   # <jdb & {..}> == jdb.intersection(..)
   matches = jdb & {f'key{v}' for v in range(98, 120)}
   assert matches == {'key98', 'key99'}

   # <{..} & jdb> == {..}.intersection(jdb)
   matches_2 = {f'key{v}' for v in range(98, 120)} & jdb
   assert matches == matches_2
   
   # <jdb | {..}> == jdb.union(..)
   matches = jdb | {f'key{v}' for v in range(10, 120)}
   assert matches == {f'key{v}' for v in range(0, 120)}

   # <{..} | jdb> == {..}.union(jdb)
   matches_2 = {f'key{v}' for v in range(10, 120)} | jdb
   assert matches == matches_2
   
   # <jdb + {..}> == jdb.union(..)
   matches = jdb + {f'key{v}' for v in range(10, 120)}
   assert matches == matches_2

   # <{..} + jdb> == {..}.union(jdb)   
   matches_2 = {f'key{v}' for v in range(10, 120)} + jdb
   assert matches == matches_2
   
   # <jdb - {..}> == jdb.difference(..)
   matches = jdb - {f'key{v}' for v in range(0, 98)}
   assert matches == {'key98', 'key99'}

   # <{..} - jdb> == {..}.difference(jdb)
   matches = {f'key{v}' for v in range(2, 102)} - jdb
   assert matches == {'key100', 'key101'}

   # <jdb ^ {..}> == jdb.non_intersection(..)
   matches = jdb ^ {f'key{v}' for v in range(1, 101)}
   assert matches == {'key0', 'key100'}

   # <{..} ^ jdb> == {..}.non_intersection(jdb)
   matches_2 = {f'key{v}' for v in range(1, 101)} ^ jdb
   assert matches == matches_2

   # <.. in jdb> == jdb.has_all(..)
   assert 'key10' in jdb
   assert {'key10', 'key90'} in jdb
   assert {'key10', 'key90', 'key110', 'key190'} not in jdb
   assert jdb.has('key10')
   assert jdb.has_all('key10')
   assert jdb.has_any('key10')
   assert jdb.has_all({'key10', 'key90'})
   assert jdb.has_any({'key10', 'key90', 'key110', 'key190'})
   assert jdb.is_disjoint({'key110', 'key190'})

支援所有標準``set``: ``union()``, ``intersection()``, ``difference()``, ``isdisjoint()``, ``issubset()``, ``issuperset()``.

進階用法
--------

.. code-block:: python

   from omni_json_db import JDb
   # Initialize the database in memory
   # Key-Value is Json+mSgpack with no compression
   jdb = JDb()

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # insert records
   with jdb.open() as fp:
      for fruit,color in fruits.items():
         jdb.f_write(fp, fruit, color)

   assert jdb == fruits

   # modify records
   with jdb.open() as fp:
      for fruit in fruits:
         color = jdb.f_read(fp, fruit)
         jdb.f_write(fp, fruit, color.upper())

   assert jdb != fruits
   assert set(jdb) == set(fruits)
   
   # unmodify records
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_unwrite(fp, fruit)

   assert jdb == fruits
   
   # remove records
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_delete(fp, fruit)

   assert len(jdb) == 0

   # unremove records
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_undelete(fp, fruit)

   assert jdb == fruits
   
   #---------------------------------------
   with jdb.open() as fp:
      key_table = jdb.key_table

      # replace
      for fruit in key_table:
         color = jdb.f_read(fp, fruit)
         jdb.f_write(fp, fruit, color.upper())

      # unmodify
      for fruit in key_table:
         jdb.f_unwrite(fp, fruit)

      # remove
      for fruit in fruits:
         jdb.f_delete(fp, fruit)

      # unremove
      for fruit in fruits:
         jdb.f_undelete(fp, fruit)

   assert jdb == fruits
   
   #---------------------------------------
   # replace all
   jdb[:] = lambda k,v: v.upper()

   # unmodify all
   jdb ^= jdb

   # remove all
   jdb -= jdb

   # unremove all
   jdb ^= fruits

   assert jdb == fruits


📝 規格說明
*****************

資料種類
----------------------

可在初始化時配置``data_type``:

* ``J+J``: JSON 鍵 + JSON 值
* ``J+S``: JSON 鍵 + MsgPack 值 (預設)
* ``J+M``: JSON 鍵 + Marshal 值
* ``J+P``: JSON 鍵 + Pickle 值
* ``J+Y``: JSON 鍵 + YAML 值
* ``S+J``: MsgPack 鍵 + JSON 值
* ``S+S``: MsgPack 鍵 + MsgPack 值
* ``S+M``: MsgPack 鍵 + Marshal 值
* ``S+P``: MsgPack 鍵 + Pickle 值
* ``S+Y``: MsgPack 鍵 + YAML 值

*Data size = 70,840,580 (MB = 1,000,000B, no zip)*

+-------------------+------------+-------+----------+-----------+----------------+------------------+
| ``data_type``     | size       | ratio | read     | write     | GOODs          | BADs             |
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

.. [a] 用 ``list`` 取代
.. [b] 用 hex string 取代
.. [c] 只支援 string key
.. [d] 所有type = ``str``, ``bytes``, ``bool``, ``int``, ``float``, ``list``, ``tuple``, ``set``, ``dict``, ``None``

壓縮種類
---------------------

可在初始化時配置 ``zip_type``

* ``no``: 無壓縮（預設, 速度最快)
* ``gz``: Gzip (mode=9)
* ``bz``: Bzip2 (mode=9, 壓縮比佳，解壓最慢)
* ``xz``: LZMA
* ``zs``: Zstandard (mode=22, 最佳壓縮比)
* ``br``: Brotli (mode=6, 比``gz``更好)
* ``z1``: Zstandard (mode=6, 比``gz``更好)
* ``z2``: Zstandard (mode=11)
* ``lz``: LZ4 (mode=0, 壓縮/解壓最快，壓縮比最差)

**Data size = 70,840,580 (MB = 1,000,000B)**

+------------+------------+-------+----------+-----------+---------------+---------------+
|``zip_type``| size       | ratio | read     | write     | GOODs         | BADs          |
+============+============+=======+==========+===========+===============+===============+
| ``no``     | 70,840,580 | 1.00  | 75.3MB/s | 358.0MB/s |* fastest speed|* biggest size |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``gz``     | 16,915,844 | 4.18  | 65.5MB/s | 5.1MB/s   |               |* slower zip   |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``bz``     | 11,394,042 | 6.21  | 26.4MB/s | 10.8MB/s  |* better ratio |* slowest unzip|
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``xz``     | 11,340,548 | 6.24  | 54.9MB/s | 2.3MB/s   |* better ratio |* slower zip   |
|            |            |       |          |           |               |* slower unzip |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``zs``     | 11,119,665 | 6.37  | 73.0MB/s | 1.7MB/s   |* best ratio   |* slowest zip  |
|            |            |       |          |           |* faster unzip |               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``br``     | 13,700,696 | 5.17  | 65.8MB/s | 25.3MB/s  |* better ``gz``|               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``z1``     | 14,738,859 | 4.80  | 73.6MB/s | 70.8MB/s  |* faster zip   |               |
|            |            |       |          |           |* faster unzip |               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``z2``     | 13,799,407 | 5.13  | 72.7MB/s | 23.6MB/s  |* faster unzip |               |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``lz``     | 26,226,039 | 2.70  | 75.6MB/s | 202.4MB/s |* fastest zip  |* worst ratio  |
|            |            |       |          |           |* fastest unzip|               |
+------------+------------+-------+----------+-----------+---------------+---------------+

快取種類
---------

可在初始化時配置 ``key_limit``

* ``no``: ``dict`` 作為 key_table (預設)
* ``bt``: ``BTree`` 作為 key_table (減少 44.3% vs ``dict``)
* ``l0`` - ``l5``: ``LiteKeyTable`` 模式 (減少 60-75% vs ``dict``)

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

📊 基準測試
***************

測試環境
-------

.. code-block:: python

   >> from omni_json_db import JDb
   >> size = 1_000_000
   >> jdb = JDb(data_type='J+J')
   >> data = {f'key{k}':k for k in range(size)}
   
   >> jdb += data        # 新增 insert
   >> jdb[:]             # 讀取全部 get_all
   >> jdb -= data        # 刪除 remove
   >> jdb ^= data        # 復原刪除 revert=unremove
   >> jdb[data] = -1     # 更改 replace
   >> jdb ^= data        # 復原更改 revert=unmodify
   >> print(jdb == data) # 輸出: True

測試結果
-------

+-------+---------+---------+---------+----------+---------+----------+
| size  | insert  | get_all | remove  | unremove | replace | unmodify |
+=======+=========+=========+=========+==========+=========+==========+
| 1     | 132 μs  | 89 μs   | 111 μs  | 96 μs    | 91 μs   | 83 μs    |
+-------+---------+---------+---------+----------+---------+----------+
| 10    | 136 μs  | 93 μs   | 142 μs  | 145 μs   | 183 μs  | 177 μs   |
+-------+---------+---------+---------+----------+---------+----------+
| 100   | 442 μs  | 319 μs  | 594 μs  | 680 μs   | 876 μs  | 976 μs   |
+-------+---------+---------+---------+----------+---------+----------+
| 1K    | 3.37 ms | 2.71 ms | 5.24 ms | 5.9 ms   | 7.61 ms | 9.12 ms  |
+-------+---------+---------+---------+----------+---------+----------+
| 10K   | 32.2 ms | 26 ms   | 54.3 ms | 55.8 ms  | 77.5 ms | 91.1 ms  |
+-------+---------+---------+---------+----------+---------+----------+
| 100K  | 358 ms  | 262 ms  | 626 ms  | 583 ms   | 774 ms  | 930 ms   |
+-------+---------+---------+---------+----------+---------+----------+
| 1M    | 3.87 s  | 2.78 s  | 7 s     | 6.09 s   | 8.15 s  | 9.83 s   |
+-------+---------+---------+---------+----------+---------+----------+

👥 貢獻指南
***************

我們歡迎任何形式的貢獻，包括回報 Bug、討論改進想法或編寫擴展！   

1. 檢查現有的 Issue 或開設新的討論。
2. Fork GitHub `儲存庫 <https://github.com/lukatrum/omni-json-db/>`_ 並在新的分支上進行修改。   
3. 編寫測試以確保功能正常。   
4. 提交 Pull Request。

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

