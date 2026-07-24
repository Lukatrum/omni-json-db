|Version| |License| |Language1| |Language2| |Language3|

|Logo|

..

   靈巧的小松鼠迅速地收集森林的金色橡子！

|Build Status| |readthedocs| |Pylint| |Codacy| |Coverage|


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
**omni-json-db** 是一款專為 Python 開發者設計的高效能嵌入式資料庫引擎。 它填補了極速鍵值（Key-Value）儲存、強大文件資料庫查詢功能，以及圖形資料庫關聯性之間的空白。

**omni-json-db** 專為超高吞吐量和執行緒安全而構建，利用現代序列化技術（如 *JSON*、*MsgPack*、*marshal*、*pickle*、*YAML*）和壓縮算法，提供了一個在處理大量 *JSON* 工作負載時通常比 *SQLite* 快顯著許多的儲存層。 無論您是在構建本地快取、日誌聚合器、分散式微服務，還是複雜的知識圖譜，它都能以「零配置」的簡易性處理大規模資料。

與傳統的 *SQLite* 或 *NoSQL* 資料庫不同，**omni-json-db** 允許您使用原生的 Python 語法（切片、Lambdas、正則表達式、集合運算）來查詢和操作資料。 它還內建了「時光旅行」功能，支援狀態回滾（復原/重做）以及原生的圖形操作。 

* **無模式 (Schema-LESS)**：無需預先定義表格即可儲存複雜、嵌套的資料。   

* **無伺服器 (Server-LESS)**：直接存取磁碟，沒有資料庫伺服器的額外開銷。   

* **無SQL (SQL-LESS)**：使用原生 Python 語法、正則表達式和 Lambdas 進行資料操作。   

🚀 核心特性
***********

* **原生圖形資料庫引擎 (Native Graph Database Engine)**：將您的鍵值儲存轉換為強大的屬性圖（Property Graph）！全新的 ``GraphDb`` 層提供無縫的節點與邊緣管理、$O(1)$ 鄰接索引，並內建經典圖形演算法（BFS/Dijkstra 最短路徑、DFS 遍歷、循環偵測、拓撲排序及連通分量），同時維持底層引擎的極致速度。 [參考 `圖形資料庫`_]

* **深度 Python 化**：告別 SQL！ 使用標準 Python ``dict`` 方法、切片甚至是 ``set`` 運算與資料庫互動。 [參考 `基本用法`_ + `運算子`_]

* **動態序列化與進階壓縮**：混合搭配 JSON (*orjson*)、MsgPack (*ormsgpack*)、Marshal、Pickle 和 YAML，並結合 LZ4、Zstandard (z1/z2/zs)、Brotli 及 Bzip2 等壓縮算法，完美平衡 I/O 速度與磁碟佔用空間。[參考 `轉換格式`_ + `資料種類`_ + `壓縮種類`_]

* **可插拔編碼與加密**：透過簡單的 ``dumps``/``loads`` 介面，帶入您自己的序列化或加密邏輯——無需修改函式庫原始碼。同時支援全域預設編碼與個別實例編碼（例如每個租戶各自使用不同的加密金鑰）。[參考 `使用者自訂編碼（U）`_]

* **強大的查詢引擎**：使用正則表達式 (Regex)、Lambda 過濾器（如 ``jdb[lambda k, v: v > 10]``）及豐富的條件運算子（``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``）輕鬆搜尋。 [參考 `查詢引擎`_ + `更多查詢示範`_ + `Pythonic 查詢範例`_]

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
   
   # 顯示表格
   jdb.show();

   # 使用 Lambda 函式搜尋名為 'John' 的記錄
   matches = jdb.find(FUNC=lambda key,val: val['name'] == 'John') 
   print(matches) # 輸出: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}}

   # 使用正則表達式搜尋 'John' 或 'Bob'
   matches = jdb.find(RE='John|Bob')
   print(matches) # 輸出: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}, '2': {'name': 'Bob', 'age': 42}} 


條件運算子包含: ``EQ``, ``NE``, ``GT``, ``LT``, ``GTE``, ``LTE``, ``HAS``, ``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOR``, ``NOT``, ``NAND``, ``SIZE``, ``ANY``, ``ALL``, ``NONE``, ``IHAS``, ``NHAS``,  ``EXISTS``, ``TYPE``, ``MOD``, ``BETWEEN``, ``NEAR``, ``MATCH``, ``SW``, ``EW``, ``NIN``, ``ANYIN``。

Transform operators: ``ABS``, ``CEIL``, ``FLOOR``, ``ROUND``, ``FLOAT``, ``INT``, ``NEG``, ``STR``, ``AVG``, ``STD``, ``MAX``, ``MID``, ``MIN``, ``SUM``, ``FIRST``, ``LAST``, ``LEN``, ``SORT``, ``UNIQUE``, ``LOWER``, ``UPPER``, ``STRIP``。

了解 `更多查詢示範`_ 或 `Pythonic 查詢範例`_

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

圖形資料庫
----------
**omni-json-db** 透過 ``GraphDb`` 類別原生支援屬性圖（Property Graph）結構。您可以輕鬆管理節點、邊緣，並開箱即用地執行複雜的圖形演算法。

.. code-block:: python

   from omni_json_db import GraphDb, Query

   # 初始化圖形資料庫（記憶體模式或檔案模式）
   db = GraphDb()

   # 1. 新增具備無模式（Schema-less）屬性的節點
   db.add_node('Alice', age=25, role='admin')
   db.add_node('Bob', age=30, role='user')
   db.add_node('Charlie', age=35, role='user')

   # 2. 新增具備屬性的邊緣（有向或無向）
   db.add_edge('Alice', 'Bob', directed=True, weight=1.5, relation='friend')
   db.add_edge('Bob', 'Charlie', directed=True, weight=2.0, relation='colleague')
   db.add_edge('Charlie', 'Alice', directed=False, weight=0.5) # 無向邊緣

   # 3. 鄰居與鄰接查詢（$O(1)$ 尋找）
   print(db.neighbors('Alice')) 
   # 輸出: {'Bob', 'Charlie'}
   
   print(db.degree('Alice'))
   # 輸出: {'in': 0, 'out': 1, 'undirected': 1, 'total': 2}

   # 4. 內建經典圖形演算法
   # 基於邊緣權重，使用 Dijkstra 尋找最短路徑
   dist, path = db.dijkstra_shortest_path('Alice', 'Charlie', weight_key='weight')
   print(f"距離: {dist}, 路徑: {path}") 
   # 輸出: 距離: 3.5, 路徑: ['Alice', 'Bob', 'Charlie']

   # 偵測圖形中的循環 (Alice -> Bob -> Charlie - Alice)
   print(db.is_cyclic()) 
   # 輸出: True 

   # 5. 無縫整合查詢引擎
   # 您仍然可以使用強大的 Query 物件來過濾節點與邊緣！
   q = Query()
   admin_nodes = db.find_nodes(q.role == 'admin')
   print(list(admin_nodes)) 
   # 輸出: ['Alice']

   # 6. 級聯刪除
   # 刪除節點會自動清理所有連接的邊緣
   db.remove_node('Bob')
   print(db.has_node('Bob')) # 輸出: False
   print(db.get_edge('Alice', 'Bob', directed=True)) # 輸出: None

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

   # 顯示表格
   jdb1.show();

   # 建立另一個JDb
   jdb2 = JDb()
   
   # 從CSV檔案匯入至JDb
   jdb2.from_csv('example.csv')
   print(jdb2.find(RE='Bob')) # 輸出: {'name': 'Bob', 'age': 42}

   # 顯示表格
   jdb2.show(RE='Bob');

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

更多查詢示範
-----------
Below are examples of how to utilize the various parameters and NoSQL syntax.

.. code-block:: python

   from omni_json_db import JDb
   import re

   # Initialize an in-memory database
   jdb = JDb()

   # Sample user records
   users = {
      'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
      'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
      'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
      'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # Insert data 
   jdb += users

   # 1. Exact Match & Global Search (ANY, RE, RE2)
   #----------------------------------------------------------
   # Find users where any attribute exactly matches 'Alice'
   res = jdb.find(ANY='Alice')
   assert list(res) == ['user_1']

   # RE/RE2 convert value into JSON string format for searching.
   # Find any record that has the string 'designer' inside it
   res = jdb.find(RE=r'designer')
   assert list(res) == ['user_4']
   
   # RE2 remove some JSON symbol (,[]{}") before searching
   res = jdb.find(RE2=r'role:designer')
   assert list(res) == ['user_4']
   
   # 2. Relational & Conditional Operators (vals)
   #----------------------------------------------------------
   # Age is greater than or equal to 30
   res = jdb.find(vals={'age': {'$gte': 30}}) # find(ANY={'$gte': 30})
   assert list(res) == ['user_1', 'user_3']

   # Age is strictly less than 30
   res = jdb.find(vals={'age': {'$lt': 30}}) # find(ANY={'$lt': 30})
   assert list(res) == ['user_2', 'user_4']

   # Role is either 'admin' or 'designer'
   res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
   assert list(res) == ['user_1', 'user_4']

   # tags contains 'python'
   res = jdb.find(vals={'tags': {'$has': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   # Age is NOT 30
   res = jdb.find(vals={'age': {'$ne': 30}}) # find(ANY={'$ne': 30})
   assert list(res) == ['user_2', 'user_3', 'user_4']

   # Age is 28
   res = jdb.find(vals={'age': {'$eq': 28}}) # find(ANY={'$eq': 28})
   assert list(res) == ['user_4']

   # 40 >= Age > 25
   res = jdb.find(vals={'age': {'$gt': 25, '$lte': 40}})
   assert list(res) == ['user_1', 'user_3', 'user_4']

   # 3. Logical Grouping (AND, OR, NOR, NOT)
   #----------------------------------------------------------
   # Age >= 25 AND Age <= 30
   res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}])
   assert list(res) == ['user_1', 'user_2', 'user_4']
   
   # Role is 'admin' OR Age > 30
   res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
   assert list(res) == ['user_1', 'user_3']

   # Role is not 'admin' AND Age <= 30
   res = jdb.find(NOR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
   assert list(res) == ['user_2', 'user_4']

   # User is NOT a developer
   res = jdb.find(NOT={'role': 'developer'})
   assert list(res) == ['user_1', 'user_4']

   # (Role is 'admin' OR Age > 30) AND 'linux' not in tags
   res = jdb.find(AND=[
      {'$or': [
         {'role': 'admin'},
         {'age': {'$gt': 30}}
      ]},
      {'$not': {'tags': {'$has': 'linux'}}}
   ])
   assert list(res) == ['user_1']

   # 4. Regular Expressions (RE, RE2, re.compile)
   #----------------------------------------------------------
   # Values matching an email domain regex
   res = jdb.find(vals={'email': re.compile(r'.@example.com')})
   assert list(res) == ['user_1']

   # Find users where any attribute exactly matches regex
   res = jdb.find(ANY=re.complie(r'.@example.com'))
   assert list(res) == ['user_1']

   # Global regex search for strings containing 'li' (matches 'Alice', 'Charlie', 'linux')
   res = jdb.find(RE=r'li[a-z]')
   assert list(res) == ['user_1', 'user_3']

   # Match specific Database Keys using compiled regex (e.g., matching 'user_1', 'user_2')
   res = jdb.find(re.compile(r'^user_[1-2]$'))
   assert list(res) == ['user_1', 'user_2']

   # 5. Array / List Operations
   #----------------------------------------------------------
   # Users with exactly 2 tags in their list
   res = jdb.find(vals={'tags': {'$size': 2}})
   assert list(res) == ['user_1', 'user_2', 'user_4']

   # Users whose FIRST tag (index 0) is 'python'
   res = jdb.find(vals={'tags': {'$0': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   # 6. Lambda / Custom Functions (FUNC) & Pagination (limit)
   #----------------------------------------------------------
   # Pass a lambda to evaluate both the key and the value dynamically
   # Example: Find the first users whose age is an even number
   res = jdb.find(
       FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0, 
      limit=1
   )
   assert list(res) == ['user_1']

   # Users has email
   res = jdb.find(vals={'email': lambda v: v != ''})
   assert list(res) == ['user_1', 'user_4']

   # Users don't have email
   res = jdb.find(NOT={'email': lambda v: v != ''})
   assert list(res) == ['user_2', 'user_3']

   # For primitive stored values (non-nested), you can use quick keyword arguments:
   jdb['simple_counter'] = 50
   res = jdb.find(EQ=50)       # Equals 50
   assert list(res) == ['simple_counter']

   res = jdb.find(IN=[40, 50]) # Value in list
   assert list(res) == ['simple_counter']

Operators Reference
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 30 30
   :header-rows: 1

   * - 運算符 (Operator)
     - 說明 (Description)
     - 範例用法 (Example Usage)
   * - ``.``  ``|``  ``/``
     - 透過深度路徑存取文檔內的巢狀深層欄位。
     - ``{'user.profile.age': {'$gt': 20}}``, ``{'user|tags|0': 'db'}``
   * - ``?``
     - 「單一字元萬用字元」比對鍵值名稱中的任何「單一」字元。
     - ``{'user?.prof???.?ge': {'$gt': 20}}``, ``{'user?.tags.?': 'db'}``
   * - ``*``
     - 「萬用字元」在文檔結構中，比對當前層級的任何鍵（Key）。 
     - ``{'users.*.role': 'admin'}``, ``{'user*|ad*r|city': 'HK'}``
   * - ``**``
     - 「遞迴萬用字元」遞迴搜尋，無視層級深度，比對文檔內任何深度的指定欄位或鍵值。
     - ``{'**.role': 'admin'}``, ``{'meta.**': 'database'}``
   * -
     -
     -
   * - ``$0``, ``$1``...
     - 精確比對陣列中指定索引（0, 1...）的元素。
     - ``{'$0': 'python'}``
   * - ``$date`` / ``_date``
     - 將資料庫紀錄的內部日期作為條件比對的目標。
     - ``{'$date': {'$lt': date(2001, 1, 1)}}``, ``{'_date': date(2011,12,1)}``
   * - ``$key`` / ``_id``
     - 將資料庫紀錄的字典鍵值（Key/ID）作為條件比對的目標。
     - ``{'$key': 'user_1'}``, ``{'_id': 'user_1'}``  
   * -
     -
     -
   * - ``$not`` / ``!``
     - 反轉查詢表達式的效果（邏輯 NOT）。
     - ``{'$not': {'tags': {'$has': 'linux'}}}``, ``{'!tags': {'$has': 'linux'}}``, ``{'tags': {'!$has': 'linux'}}``
   * - ``$and``
     - 使用邏輯 AND 結合多個查詢子句。
     - ``{'$and': [{'$has':'python'}, {'$has':'linux'}]}``
   * - ``$nand`` / ``!$and``
     - 使用邏輯 NAND（反及）結合多個查詢子句。
     - ``{'$nand': [{'$has':'python'}, {'$has':'linux'}]}``
   * - ``$or``
     - 使用邏輯 OR 結合多個查詢子句。
     - ``{'$or': [{'$eq': 2000}, {'$eq': 2010}]}``
   * - ``$nor`` / ``!$or``
     - 使用邏輯 NOR（反或）結合多個查詢子句。
     - ``{'$nor': [{'$eq': 2000}, {'$eq': 2010}]}``
   * -
     -
     -      
   * - ``$all``
     - 當值陣列/可迭代物件中的「所有」元素皆符合條件時即成立。
     - ``{'$all': {'$ne': 0}}``
   * - ``$any``
     - 當值陣列/可迭代物件中有「任何」元素符合條件時即成立。
     - ``{'$any': 'python'}``
   * - ``$none`` / ``!$any``
     - 當值陣列/可迭代物件中「沒有任何」元素符合條件時即成立。
     - ``{'$none': {'age': 30}}``
   * - ``$func``
     - 對欄位執行自訂的 lambda 函式來決定是否符合。
     - ``{'$func': lambda x: x > 0}``  
   * -
     -
     -
   * - ``$eq``
     - 比對與指定值完全相等的資料。
     - ``{'$eq': 28}``
   * - ``!$eq`` / ``$ne``
     - 比對與指定值不相等的資料。
     - ``{'$ne': 30}``,  ``{'!$eq': 30}``
   * - ``$gt``
     - 比對嚴格大於指定值的資料。
     - ``{'$gt': 25}``
   * - ``$gte`` / ``$ge``
     - 比對大於或等於指定值的資料。
     - ``{'$gte': 30}``
   * - ``$lt``
     - 比對嚴格小於指定值的資料。
     - ``{'$lt': 30}``
   * - ``$lte`` / ``$le``
     - 比對小於或等於指定值的資料。
     - ``{'$lte': 40}``
   * -
     -
     -
   * - ``$in``
     - 當值存在於指定的陣列/集合中時即成立。
     - ``{'$in': ['admin', 'designer']}``
   * - ``!$in`` / ``$nin``
     - 當值「不」存在於指定的陣列/集合中時即成立。
     - ``{'$nin': ['python', 'db']}``, ``{'!$in': ['python', 'db']}``
   * - ``$anyin``
     - 當值陣列/可迭代物件中有「任何」元素存在於指定的陣列/集合中時即成立。
     - ``{'$anyin': ['admin', 'manager']}``
   * - ``$between``
     - 比對落在指定包含範圍（最小值, 最大值）內的值。
     - ``{'$between': (26, 40)}``
   * - ``!$between``
     - 比對嚴格落在指定範圍之外的值。
     - ``{'!$between': (26, 40)}``
   * - ``$near``
     - 比對在容許誤差範圍內的數值或日期（目標值, 誤差值）。
     - ``{'$near': (20, 9)}``
   * - ``$mod``
     - 比對符合「值 % 除數 == 餘數」條件的資料（以元組形式傳入）。
     - ``{'$mod': (10, 5)}``
   * -
     -
     -
   * - ``$has``
     - 比對包含指定元素或子字串的陣列或字串。
     - ``{'$has': 'python'}``
   * - ``!$has`` / ``$nhas``
     - 當「不」包含指定元素或子字串時即成立。
     - ``{'$nhas': 'r_1'}``, ``{'!$has': 'r_1'}``
   * - ``$ihas``
     - 不區分大小寫，比對包含指定元素/子字串的陣列或字串。
     - ``{'$ihas': 'UseR_'}``  
   * - ``$re`` / ``$regex``
     - 使用正規表達式（Regular Expression）比對字串值。
     - ``{'$re': r'li[a-z]'}``, ``{'$re': re.compile(r'li[a-z]')}``
   * - ``$re2``
     - 從字串中去除 JSON 格式符號（``[]{}""``）後，再使用正規表達式進行比對。
     - ``{'$re2': r'role:admin'}``
   * - ``$ew``
     - 比對以指定子字串結尾的字串。
     - ``{'$ew': '_suffix'}``
   * - ``$sw``
     - 比對以指定子字串開頭的字串。
     - ``{'$sw': 'prefix_'}``
   * - 
     -
     -
   * - ``$exists``
     - 比對擁有指定欄位/鍵的文檔（Document）。
     - ``{'$exists': ['age', 'tags']}``
   * - ``!$exists``
     - 比對缺少指定欄位/鍵的文檔。
     - ``{'!$exists': ['age']}``
   * - ``$size``
     - 當陣列/字串的長度等於指定值時即成立。
     - ``{'$size': [1,2,3]}``
   * - ``!$size``
     - 當陣列/字串的長度「不」等於指定值時即成立。
     - ``{'!$size': [1,2,3]}``
   * - ``$type``
     - 當值屬於指定的 Python 變數型別時即成立。
     - ``{'$type': list}``
   * - 
     -
     -   
   * - ``$abs``
     - 取數值的絕對值後，再進行比對。
     - ``{'$abs': 3.14}``
   * - ``$ceil``
     - 將數值無條件進位(math.ceil)後，再進行比對。
     - ``{'$ceil': 2}``
   * - ``$floor``
     - 將數值無條件捨去(math.floor)後，再進行比對。
     - ``{'$floor': 2}``
   * - ``$round``
     - 將數值四捨五入後，再進行比對。
     - ``{'$round': 2}``
   * - 
     -
     -
   * - ``$float``
     - 將值轉換為浮點數(float)後，再進行比對。
     - ``{'$float': 1.0}``
   * - ``$int``
     - 將值轉換為整數(int)後，再進行比對。
     - ``{'$int': 1.0}``
   * - ``$neg``
     - 將數值取負值(-val)後，再進行比對。
     - ``{'$neg': -1.2}``
   * - ``$str``
     - 將值轉換為字串(str)後，再進行比對。
     - ``{'$str': '1.2'}``
   * - 
     -
     -
   * - ``$avg``
     - 計算可迭代物件的算術平均值後，再進行比對。
     - ``{'$avg': 2.0}``
   * - ``$std``
     - 計算可迭代物件的母體標準差(population std-dev)後，再進行比對。
     - ``{'$std': 2.0}``
   * - ``$max``
     - 取出可迭代物件中的最大值後，再進行比對。
     - ``{'$max': 4}``
   * - ``$mid``
     - 取出陣列或字串正中間的元素/字元（`len//2`）後，再進行比對。
     - ``{'$mid': 4}``
   * - ``$min``
     - 取出可迭代物件中的最小值後，再進行比對。
     - ``{'$min': 1}``
   * - ``$sum``
     - 計算可迭代物件的總和後，再進行比對。
     - ``{'$sum': 8}``
   * - 
     -
     -
   * - ``$first``
     - 取出陣列或字串的第一個元素/字元後，再進行比對。
     - ``{'$first': 1}``
   * - ``$flat``
     - 將巢狀可迭代物件攤平(flatten)後，再進行比對。
     - ``{'$flat': [1,2,2,3]}``
   * - ``$last``
     - 取出陣列或字串的最後一個元素/字元後，再進行比對。
     - ``{'$last': 3}``
   * - ``$len``
     - 計算陣列或字串的長度後，再進行比對。
     - ``{'$len': 3}``
   * - ``$sort``
     - 將可迭代物件排序(sorted)後，再進行比對。
     - ``{'$sort': [1,2,3]}``
   * - ``$unique``
     - 保留原有順序去除重複項目(dedup)後，再進行比對。
     - ``{'$unique': [2,3,1]}``
   * - 
     -
     -
   * - ``$lower``
     - 將字串轉換為小寫後，再進行比對。
     - ``{'$lower': 'alice'}``
   * - ``$upper``
     - 將字串轉換為大寫後，再進行比對。
     - ``{'$upper': 'ALICE'}``
   * - ``$strip``
     - 移除字串前後空白字元後，再進行比對。
     - ``{'$strip': 'hi'}``

Pythonic 查詢範例 
-----------------
對於偏好使用 Pythonic 及物件導向語法來過濾資料的開發者（類似 **TinyDB** 的體驗），``omni-json-db`` 提供了 ``Query`` 物件。您可以優雅地使用原生的 Python 運算子（例如 ``==``, ``>``, ``&``, ``|``, ``~``）以及串聯方法來建構複雜的搜尋條件。

.. code-block:: python

   from omni_json_db import JDb, Query

   # 1. 初始化資料庫並加入測試資料
   jdb = JDb()
   jdb += {
       'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
       'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
       'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
       'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # 2. 建立一個 Query 實例
   User = Query()

   # 基礎比較：尋找年齡大於 28 的用戶
   res = jdb.find(User.age > 28)
   assert set(res) == {'user_1', 'user_3'}

   # 邏輯組合 (AND & OR)：尋找 30 歲以下的開發者或管理員
   res = jdb.find((User.role == 'developer') & (User.age < 30) | (User.role == 'admin'))
   assert set(res) == {'user_1', 'user_2'}

   # 陣列查詢：尋找標籤中包含 'python' 的用戶
   res = jdb.find(User.tags.has('python'))
   assert set(res) == {'user_1', 'user_3'}

   # 路徑萬用字元：在所有欄位中遞迴執行正規表達式搜尋 (尋找包含 example.com 的電子郵件)
   res = jdb.find(User['**'].matches(r'.@example\.com'))
   assert set(res) == {'user_1'}

   # 進階過濾：尋找「沒有」'email' 欄位的用戶 (~ 為 NOT 運算子)
   res = jdb.find(~User.exists('email'))
   assert set(res) == {'user_2', 'user_3'}

   # Lambda 測試：尋找年齡為偶數的用戶
   res = jdb.find(User.age.test(lambda age: age % 2 == 0))
   assert set(res) == {'user_1', 'user_4'}

   # 修改 admin 為 Administrator
   res = jdb.update_if(User.role == 'admin', {'role': 'Administrator'})
   assert res == 1 and (User.role == 'Administrator') in jdb
   
   jdb.show();

方法與運算子參考 
^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 30 30
   :header-rows: 1

   * - 語法 / 運算子
     - 說明
     - 範例用法     
   * - ``==``, ``!=``
     - 等於 / 不等於
     - ``User.name != 'Bob'``
   * - ``>``, ``>=``, ``<``, ``<=``
     - 數值比較
     - ``User.age > 30``, ``User.age < 30``
   * - ``&``
     - 邏輯 AND (且)
     - ``(User.age > 20) & (User.role == 'admin')``
   * - ``|``
     - 邏輯 OR (或)
     - ``(User.name == 'Alice') | (User.age < 30)``
   * - ``~``
     - 邏輯 NOT (非)
     - ``~ User.exists('email')``
   * - ``.has(val)``
     - 包含特定字串或陣列元素
     - ``User.tags.has('database')``
   * - ``.not_has(val)``
     - 不包含特定字串或陣列元素
     - ``User.name.not_has('ice')``
   * - ``.ihas(val)``
     - 忽略大小寫包含
     - ``User.name.ihas('alice')``
   * - ``.startswith(val)``
     - 字串以前綴開頭
     - ``User.city.startswith(('L', 'H'))``
   * - ``.endswith(val)``
     - 字串以後綴結尾
     - ``User.name.endswith('b')``
   * - ``.matches(pattern)``
     - 正規表達式搜尋 (等同於 ``re.search``)
     - ``User.name.matches(r'[bB]ob')``
   * - ``.fullmatch(pattern)``
     - 正規表達式完全匹配 (等同於 ``re.fullmatch``)
     - ``User.name.fullmatch(r'.lic.')``
   * - ``.one_of(col)``
     - 數值包含於指定的集合中
     - ``User.role.one_of(['admin', 'dev'])``
   * - ``.not_in(col)``
     - 數值不包含於指定的集合中
     - ``User.role.not_in(['admin', 'dev'])``
   * - ``.any_in(col)``
     - 陣列中的任一元素包含於指定的集合中
     - ``User.role.any_in(['admin', 'ceo'])``
   * - ``.between(low, high)``
     - 數值或字串在指定範圍內
     - ``User.age.between(20, 30)``
   * - ``.size_of(size)``     
     - 陣列或字串長度匹配
     - ``User.tags.size_of(2)``
   * - ``.exists(fields)``
     - 檢查指定的欄位是否存在
     - ``User.exists('email')``
   * - ``.type_of(type)``
     - 檢查資料型態
     - ``User.age.type_of(int)``
   * - ``.mod(div, rem)``
     - 取餘數條件 (除以 ``div`` 時餘數為 ``rem``)
     - ``User._date.mod(7, 5)``
   * - ``.near(target, tol)``
     - 數值接近目標值，且在容差 ``tol`` 範圍內
     - ``User._date.near(today, 1)``
   * - ``.test(func)``
     - 傳遞自訂的 Lambda 函數以進行條件評估
     - ``User.age.test(lambda v: 40 >= v > 18)``
   * - ``.abs()``
     - 取數值的絕對值後，再進行比對。
     - ``Query().price.abs() == 3.14``
   * - ``.ceil()``
     - 將數值無條件進位(math.ceil)後，再進行比對。
     - ``Query().price.ceil() > 3``
   * - ``.floor()``
     - 將數值無條件捨去(math.floor)後，再進行比對。
     - ``Query().price.floor() <= 2``
   * - ``.round()``
     - 將數值四捨五入後，再進行比對。
     - ``Query().price.round() == 2``
   * - ``.float()``
     - 將值轉換為浮點數(float)後，再進行比對。
     - ``Query().price.float() == 2.1```
   * - ``.int()``
     - 將值轉換為整數(int)後，再進行比對。
     - ``Query().price.int() != 1```
   * - ``.neg()``
     - 將數值取負值(-val)後，再進行比對。
     - ``Query().price.neg() == -1.2``
   * - ``.str()``
     - 將值轉換為字串(str)後，再進行比對。
     - ``Query().price.str() == '1.2'``
   * - ``.avg()``
     - 計算可迭代物件的算術平均值後，再進行比對。
     - ``Query().prices.avg() == 2.5```
   * - ``.std()``
     - 計算可迭代物件的母體標準差(population std-dev)後，再進行比對。
     - ``Query().prices.std() >= 2.0``
   * - ``.max()``
     - 取出可迭代物件中的最大值後，再進行比對。
     - ``Query().prices.max() == 4``
   * - ``.mid()``
     - 取出陣列或字串正中間的元素/字元（`len//2`）後，再進行比對。
     - ``Query().prices.mid() == 4``
   * - ``.min()``
     - 取出可迭代物件中的最小值後，再進行比對。
     - ``Query().prices.min() == 1``
   * - ``.sum()``
     - 計算可迭代物件的總和後，再進行比對。
     - ``Query().prices.sum() == 8``
   * - ``.first()``
     - 取出陣列或字串的第一個元素/字元後，再進行比對。
     - ``Query().prices.first() == 1``
   * - ``.flat()``
     - 將巢狀可迭代物件攤平(flatten)後，再進行比對。
     - ``Query().prices.flat().max() == 4``
   * - ``.last()``
     - 取出陣列或字串的最後一個元素/字元後，再進行比對。
     - ``Query().prices.last() == 3``
   * - ``.len()``
     - 計算陣列或字串的長度後，再進行比對。
     - ``Query().prices.len() == 3``
   * - ``.sort()``
     - 將可迭代物件排序(sorted)後，再進行比對。
     - ``Query().prices.sort().mid() == 2``
   * - ``.unique()``
     - 保留原有順序去除重複項目(dedup)後，再進行比對。
     - ``Query().prices.unique().first() == 1``
   * - ``.lower()``
     - 將字串轉換為小寫後，再進行比對。
     - ``Query().name.lower() == 'alice'``
   * - ``.upper()``
     - 將字串轉換為大寫後，再進行比對。
     - ``Query().name.upper() == 'ALICE'``
   * - ``.strip()``
     - 移除字串前後空白字元後，再進行比對。
     - ``Query().name.strip() == 'Hi'``
   * - ``field['field']``
     - 存取特定欄位
     - ``User['addr'].city``, ``User.addr.city``
   * - ``.field[0]`` 
     - 陣列的特定索引 (支援如 ``User.tags[-1]`` 的負數索引)
     - ``User.tags[1].has('db')``
   * - ``'*'`` / ``'**'`` / ``'?'``
     - 第一層萬用字元 / 遞迴多層萬用字元 / 單一字元萬用字元路徑搜尋
     - ``User['*']``, ``User['**']``, ``User['ci?y']``, ``User['c*y']``
   * - ``._id`` / ``._date``
     - 系統保留鍵：分別存取文件 ID (主鍵) 與時間戳記
     - ``User._id``, ``User._date``

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
* ``J+U``: JSON 鍵 + 使用者自訂值（可插拔編碼，例如加密）
* ``S+U``: MsgPack 鍵 + 使用者自訂值（可插拔編碼，例如加密）
* ``U+U``: 使用者自訂鍵 + 使用者自訂值（鍵與值皆可插拔）

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

使用者自訂編碼（U）
----------------------------------

``J+U``、``S+U`` 與 ``U+U`` 讓您使用自己的編碼取代內建格式。這是加密、自訂壓縮、
protobuf，或任何您想要完全掌控的序列化方式的擴充點。

* ``J+U`` / ``S+U``：鍵（Key）維持 JSON/MsgPack 格式（可讀／體積小），只有值（Value）
  會經過您的自訂編碼。
* ``U+U``：鍵（Key）與值（Value）皆會經過您自己的編碼。

有兩種方式可以註冊編碼：

1. **全域預設**——只需註冊一次，所有以 ``U`` 開頭的 data_type 開啟的 ``JDb`` 都會
   使用它。

.. code-block:: python

   from marshal import loads as marshal_loads, dumps as marshal_dumps
   from omni_json_db import JDb, register_user_val_codec

   # --- 全域預設：使用 Fernet 加密每一筆 Value ---
   from cryptography.fernet import Fernet
   fernet = Fernet(Fernet.generate_key())

   register_user_val_codec(
       dumps=lambda data: fernet.encrypt(marshal_dumps(data)),
       loads=lambda raw: marshal_loads(fernet.decrypt(raw)),
   )

   # Key=JSON（可讀）, Value=已加密
   jdb = JDb("secure.jdb", data_type="J+U")
   jdb["alice"] = {"ssn": "123-45-6789", "balance": 42.5}

   # 重新開啟資料庫，會自動解密
   jdb2 = JDb("secure.jdb", data_type="J+U")
   assert jdb2["alice"] == {"ssn": "123-45-6789", "balance": 42.5}

2. **個別實例**——在 ``JDb()`` 傳入 ``val_codec=``（也可搭配 ``key_codec=``），讓
   不同的實例（例如不同租戶）可以同時使用各自不同的編碼／金鑰。

.. code-block:: python

   from marshal import loads as marshal_loads, dumps as marshal_dumps
   from omni_json_db import JDb, JIoVAL_U
   from cryptography.fernet import Fernet

   # --- 個別實例編碼：每個租戶擁有各自的加密金鑰 ---
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

壓縮種類
---------------------

可在初始化時配置 ``zip_type``

* ``no``: 無壓縮（預設, 速度最快)
* ``gz``: Gzip (mode=1)
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
| ``gz``     | 16,915,844 | 4.18  | 65.5MB/s | 5.1MB/s   |* built-in     |* slower zip   |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``bz``     | 11,394,042 | 6.21  | 26.4MB/s | 10.8MB/s  |* better ratio |* slowest unzip|
|            |            |       |          |           |* built-in     |* slower unzip |
+------------+------------+-------+----------+-----------+---------------+---------------+
| ``xz``     | 11,340,548 | 6.24  | 54.9MB/s | 2.3MB/s   |* better ratio |* slower zip   |
|            |            |       |          |           |* built-in     |* slower unzip |
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

.. |readthedocs| image:: https://img.shields.io/badge/docs-passing-brightgreen?logo=readthedocs
   :target: https://omni-json-db.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

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

.. |Language1| image:: https://img.shields.io/badge/-ENG-d3d3d3?logo=googletranslate&logoColor=white
   :target: https://github.com/lukatrum/omni-json-db/

.. |Language2| image:: https://img.shields.io/badge/-%E4%B8%AD%E6%96%87-d3d3d3?logo=googletranslate&logoColor=white
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/README-tc.rst

.. |Language3| image:: https://img.shields.io/badge/-%E6%97%A5%E6%96%87-d3d3d3?logo=googletranslate&logoColor=white
   :target: https://github.com/Lukatrum/omni-json-db/blob/main/README-jp.rst
