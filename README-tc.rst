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
- `🤔 為什麼選 omni-json-db?`_
- `🚀 核心特性`_
- `🛠️ 快速入門`_
- `📝 規格說明`_
- `📊 基準測試`_
- `📄 說明文檔 <https://omni-json-db.readthedocs.io>`_
- `👥 貢獻指南`_
- `📄 授權條款`_

✨ 簡介
*******
**omni-json-db** 是一款專為 Python 開發者設計的高效能嵌入式資料庫引擎。 它填補了極速鍵值（Key-Value）儲存、強大文件資料庫查詢功能，以及圖形資料庫關聯性之間的空白。

**omni-json-db** 專為超高吞吐量和執行緒安全而構建，利用現代序列化技術（如 *JSON*\ 、\ *MsgPack*\ 、\ *marshal*\ 、\ *pickle*\ 、\ *YAML*\ ）和壓縮算法，提供了一個在處理大量 *JSON* 工作負載時通常比 *SQLite* 快顯著許多的儲存層。 無論您是在構建本地快取、日誌聚合器、分散式微服務，還是複雜的知識圖譜，它都能以「零配置」的簡易性處理大規模資料。

與傳統的 *SQLite* 或 *NoSQL* 資料庫不同，\ **omni-json-db** 允許您使用原生的 Python 語法（切片、Lambdas、正則表達式、集合運算）來查詢和操作資料。 它還內建了「時光旅行」功能，支援狀態回滾（復原/重做）以及原生的圖形操作。 

* **無模式 (Schema-LESS)**\ ：無需預先定義表格即可儲存複雜、嵌套的資料。   

* **無伺服器 (Server-LESS)**\ ：直接存取磁碟，沒有資料庫伺服器的額外開銷。   

* **無SQL (SQL-LESS)**\ ：使用原生 Python 語法、正則表達式和 Lambdas 進行資料操作。

* **無相依 (Dependency-LESS)**\ ：在乾淨的 Python 環境即可運行，\ **零必要第三方套件**\ ——C 加速器與額外格式只是一行 ``pip install "omni-json-db[full]"`` 的距離。

🤔 為什麼選 omni-json-db?
*************************

與傳統的 SQL 或 NoSQL 資料庫不同，\ **omni-json-db** 讓您用原生 Python 語法查詢與操作資料——包含切片、lambda、正則表達式與集合運算。它同時內建「時光旅行」（復原／重做）、屬性圖引擎，以及可插拔的序列化。

..

   **omni-json-db** 已在 Python 3.7+ 與 PyPy3 上通過測試。（測試覆蓋率約 100%）

.. list-table::
   :widths: 26 16 10 11 10 9 11 9 9
   :header-rows: 1

   * - 
     - **omni-json-db**
     - TinyDB
     - DiskCache
     - UnQLite
     - LMDB
     - RocksDict
     - SQLite
     - DuckDB
   * - 交易 / ACID
     - ⚠️ (原子操作)
     - ❌
     - ❌
     - ❌
     - ✅
     - ✅
     - ✅
     - ✅
   * - 執行緒安全並行
     - ✅ (多讀/單寫)
     - ❌
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
   * - 多行程存取
     - ✅ (檔案鎖)
     - ❌
     - ✅
     - ✅
     - ✅
     - ⚠️ (唯讀)
     - ✅
     - ✅
   * - 記憶體模式
     - ✅
     - ✅
     - ❌
     - ✅
     - ❌
     - ❌
     - ✅
     - ✅
   * - 內建 CSV / SQLite / Parquet
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ⚠️ (CLI)
     - ✅
   * - 內建壓縮
     - ✅
     - ❌
     - ✅
     - ❌
     - ❌
     - ✅
     - ❌
     - ✅
   * - 無模式 (Schema-less)
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ❌
     - ❌
   * - Dataclass 映射 [z]_
     - ✅
     - ❌
     - ⚠️
     - ❌
     - ❌
     - ⚠️
     - ❌
     - ❌
   * - 群組 / 命名空間
     - ✅
     - ✅
     - ⚠️
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
   * - 巢狀群組 + 扇出查詢
     - ✅
     - ⚠️ (扁平)
     - ❌
     - ⚠️
     - ⚠️ (扁平)
     - ⚠️ (CF)
     - ⚠️ (SQL)
     - ⚠️ (SQL)
   * - 純 Python (PyPy 友善)
     - ✅
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Python 化查詢 (Lambda/Regex)
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 深層巢狀搜尋
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 圖形資料庫引擎
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 復原 / 重做（時光旅行）
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 時間序列日期切片
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 網路模式（含群組）
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 50 萬筆相對速度 [x]_
     - 1.00x (基準)
     - 41.47x
     - 60.95x
     - 4.28x
     - 0.94x
     - 0.45x
     - 0.13x
     - 0.21x
   * - 1000 萬筆相對速度 [x]_
     - 1.00x (基準)
     - N/A [y]_
     - N/A [y]_
     - 24.07x
     - 1.31x
     - 0.55x
     - 0.16x
     - 0.05x

.. [x] 數字越小越快。（完整拆解與測試方法請見 `benchmark <https://github.com/lukatrum/omni-json-db/blob/main/benchmark/report.txt>`_）
.. [y] 慢到不具實用性
.. [z] 寫入一個 ``@dataclass``\ ，再以物件形式讀回。⚠️ = 物件\ *可以*\ 被儲存，但只是一團不透明的 ``pickle`` 位元組：欄位對查詢不可見，檔案也無法在 Python 之外讀取。


🚀 核心特性
***********

* **原生圖形引擎**\ ：把鍵值儲存變成屬性圖（Property Graph）。\ ``GraphDb`` 層提供 O(1) 鄰接索引與經典演算法（BFS、Dijkstra、DFS、循環偵測），且不犧牲效能。 [參考 `圖形資料庫`_]

* **深度 Python 化**\ ：用熟悉的 ``dict`` 方法、清單切片與集合運算操作資料，不必寫複雜的 SQL。 [參考 `基本用法`_ + `運算子`_]

* **Dataclass 物件**\ ：任何 ``@dataclass`` 都能直接讀寫——\ ``jdb += user``\ 、\ ``jdb['u1'] = user``\ 、\ ``del jdb[user]``\ 。物件會被攤平成普通 ``dict`` 而非 pickle，所以由物件寫入的記錄仍可查詢、可匯出、跨語言可讀。 [參考 `Dataclass 物件`_]

* **進階序列化與壓縮**\ ：自由組合格式（JSON、MsgPack、Pickle、YAML）與演算法（LZ4、Zstandard、Brotli），在 I/O 與磁碟空間之間取得平衡。 [參考 `轉換格式`_ + `資料種類`_ + `壓縮種類`_]

* **可插拔編碼與加密**\ ：透過簡單的 ``dumps``/``loads`` 介面帶入自己的序列化或加密邏輯，不必改原始碼。同時支援行程層級的預設編碼與個別實例編碼（例如每個租戶各自的金鑰）。 [參考 `使用者自訂編碼（U）`_]

* **強大的查詢引擎**\ ：以正則表達式、Lambda 過濾器與豐富運算子（\ ``EQ``\ 、\ ``GT``\ 、\ ``LT``\ 、\ ``IN``\ 、\ ``HAS``\ 、\ ``RE``\ …）進行搜尋。 [參考 `查詢引擎`_ + `更多查詢示範`_ + `Pythonic 查詢範例`_]

* **多種運行模式**\ ：記憶體模式（\ ``JMemFiles``\ ）追求極致效能，網路模式（\ ``JNetFiles``\ ）把資料庫變成網路服務。 [參考 `記憶體模式`_ + `網路模式`_]

* **狀態管理**\ ：內建「時光旅行」可追蹤狀態、復原修改（\ ``unmodify()``\ ）或救回已刪除的資料（\ ``unremove()``\ ）。\ ``history()`` 列出所有仍可觸及的版本，\ ``min_safe`` 決定其中有多少能存活。 [參考 `救回`_ + `記錄歷史`_ + `備份 / 復原`_]

* **批次寫入**\ ：大量插入走專用的追加路徑——每個 VAL 檔一次 ``write()``\ 、KEY 列編成單一區塊，而不是每筆一次系統呼叫——因此 ``jdb += rows``\ 、\ ``insert()`` 與所有匯入器都快上 1.4x–4.5x，且 API 完全不變。 [參考 `批次插入`_]

* **大規模快速開檔**\ ：可丟棄的鍵表快照（\ ``index_cache``\ ）讓冷開檔快約 4 倍，\ ``warm_up`` 再把剩下的成本移到背景執行緒。 [參考 `加速開檔`_]

* **資料遷移**\ ：從 SQLite 遷移，或透過 CSV、Parquet、INI、TOML 匯入匯出，都只要一行。Parquet 以 ``pyarrow`` 的 record batch 串流匯入，記憶體用量固定，多 GB 檔案也不成問題。 [參考 `CSV 匯入 / 匯出`_ + `Parquet 匯入`_ + `SQLite 匯入`_ + `INI / TOML 匯入`_]

* **時間序列就緒**\ ：原生時間戳讓日期切片變得輕鬆（例如 ``jdb[yesterday:now]``\ ）。 [參考 `時間序列`_]

* **記憶體快取**\ ：可調整的 ``cache_limit`` 在記憶體用量與 I/O 速度之間取得平衡。 [參考 `快取種類`_]

* **分組與命名空間**\ ：用群組輕鬆隔離並管理不同的資料模組。 [參考 `群組模式`_]

* **每筆記錄旗標**\ ：以 ``chmod`` 風格語法給任何記錄檔案系統般的屬性——唯讀、只可追加、隱藏、不快取、不留歷史——外加指向其他記錄或群組的符號連結，以及一分鐘到 511 天的個別 TTL。 [參考 `記錄旗標`_ + `符號連結`_ + `記錄過期 (TTL)`_]

* **並行控制**\ ：針對「多讀 / 單寫」環境優化，具備可靠的檔案鎖與 Lock 機制。 [參考 `進階用法`_]

🛠️ 快速入門
***********

安裝
----

**omni-json-db 沒有任何必要相依套件。** 它在乾淨的 Python 環境即可運行（內建純 Python 後備實作），所以這樣就夠了：

.. code-block:: bash

   pip install omni-json-db

若要最快、功能最完整的版本——C 加速的序列化器（\ ``orjson`` / ``ormsgpack`` / ``msgspec`` / ``msgpack`` / ``bitarray``\ ）、額外壓縮編碼（\ ``zstandard`` / ``lz4`` / ``brotli``\ ）、\ ``YAML`` 值格式，以及 ``BTrees`` 鍵索引後端——請安裝 ``full`` 附加項：

.. code-block:: bash

   pip install "omni-json-db[full]"

或只挑您需要的：

.. code-block:: bash

   pip install "omni-json-db[speed]"        # 只加速序列化（直接替換，不新增功能）
   pip install "omni-json-db[compression]"  # zstd / lz4 / brotli 值壓縮
   pip install "omni-json-db[yaml]"         # YAML
   pip install "omni-json-db[btree]"        # B-tree 鍵索引後端

.. note::

   ``[speed]`` 不新增任何功能，也不改變檔案格式——它只是把預設的程式路徑換成 C 實作：JSON 值用 ``orjson``\ 、MsgPack 值用 ``ormsgpack``\ 、KEY 索引列用 ``msgspec.msgpack``\ （輸出位元組完全相同，且是引擎中最熱的路徑）、值的擴充型別與串流解包器用 ``msgpack``\ 、死列點陣圖用 ``bitarray``\ 。缺少任何一個都會退回純 Python 實作，所以乾淨安裝的行為完全一致，只是比較慢。在 PyPy 上純 Python 路徑本來就夠快，因此會跳過 ``orjson`` / ``msgspec``\ 。

   套裝組合（\ ``[full]`` / ``[all]``\ ）使用自我參照的 extras，需要 ``pip >= 21.2``\ 。若 pip 版本較舊（例如原生的 Python 3.7），請先升級 pip（\ ``python -m pip install -U pip``\ ），或把細項一次裝齊，例如 ``pip install "omni-json-db[speed,compression,yaml,btree]"``\ 。

基本用法
--------

.. code-block:: python

   from omni_json_db import JDb
   
   # 初始化 Json+mSgpack，不壓縮，檔案模式
   jdb = JDb("example.jdb")

   # 儲存資料
   jdb["用家1"] = {"名字" : "小明", "職位": "程式員"}
   
   # 讀取資料
   user = jdb["用家1"]
   print(user["名字"], user["職位"]) # 輸出: 小明 程式員

   
支援所有標準 ``dict`` 方法: ``keys()``, ``values()``, ``items()``, ``get()``, ``pop()``, ``setdefault()``, ``update()``.

批次插入
--------

一次寫入大量記錄會走專用的追加路徑，不需要特別開啟——所有批次入口都已經在用它：

.. code-block:: python

   from omni_json_db import JDb

   jdb  = JDb('users.jdb')
   rows = {f'user{i}': {'age': i % 80} for i in range(100_000)}

   jdb += rows                 # __iadd__ -> add()
   jdb.insert(rows)            # 已存在的鍵一律不覆寫
   jdb.update(rows)            # 只更新已存在的鍵
   jdb.from_csv('users.csv')   # 所有匯入器都以 IMPORT_BATCH_ROWS 為單位串流

``add()`` 會依鍵拆分批次。已存在的鍵交給 ``f_write()`` 逐筆改寫，因此更新語意、DEAD 列回收與歷史行為完全不變。所有\ *新*\ 鍵則收集起來交給 ``f_extend()``\ ，一次追加完成：值會先序列化並補齊填充，填充後的位元組以單一 ``write()`` 送進每個 VAL 檔（而不是每筆一次），KEY 列也編成一個區塊一次寫出。

批次追加\ **絕不**\ 從 DEAD 區取回列：每筆新記錄讓 ``n_lines`` 剛好成長一列，\ ``f_delete()`` 空出的空間會留給日後的改寫，而不是被插入吃掉——這也是為什麼在已經刪過資料的資料庫上，效能差距會拉得更開。

.. list-table::
   :widths: 40 18 22
   :header-rows: 1

   * - 5 萬筆記錄，取 4 次最佳
     - v3.00.00
     - v3.00.10+
   * - 全新插入
     - 0.616 s
     - 0.366 s (1.7x)
   * - 插入到已有 1 萬筆 DEAD 列的資料庫
     - 1.892 s
     - 0.419 s (4.5x)
   * - 記憶體模式插入
     - 0.540 s
     - 0.324 s (1.7x)
   * - 內嵌（KEY 列）值
     - 0.305 s
     - 0.215 s (1.4x)
   * - 500 批 x 每批 20 筆
     - 0.167 s
     - 0.110 s (1.5x)

在明確的檔案 handle 之下，\ ``f_extend()`` 就是 ``f_write()`` 的批次版本——它會自己取得寫入鎖，呼叫端不必處理：

.. code-block:: python

   with jdb.open(read_only=False) as fp:
      new = {'a': 1, 'b': [2, 3]}
      jdb.f_extend(fp, new, ttl=7)              # 輸出: True
      # 回傳後，`new` 剛好只剩實際寫入的那些記錄
      jdb.f_extend(fp, {'a': 99}, replace=True) # 連已存在的鍵一起改寫：批次 upsert

``ttl=`` 與 ``key_flags=`` 由該次呼叫的所有記錄共用；工作以有界的批次分段進行，因此 ``records`` 再長，記憶體用量都是平的。

記憶體模式
----------

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
--------

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


條件運算子包含: ``EQ``, ``NE``, ``GT``, ``LT``, ``GTE``, ``LTE``, ``HAS``, ``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOR``, ``NOT``, ``NAND``, ``SIZE``, ``ANY``, ``ALL``, ``NONE``, ``IHAS``, ``NHAS``, ``EXISTS``, ``TYPE``, ``MOD``, ``BETWEEN``, ``NEAR``, ``MATCH``, ``SW``, ``EW``, ``IN``, ``NIN``, ``ANYIN``\ 。

轉換運算子包含: ``ABS``, ``CEIL``, ``FLOOR``, ``ROUND``, ``FLOAT``, ``INT``, ``NEG``, ``STR``, ``AVG``, ``STD``, ``MAX``, ``MID``, ``MIN``, ``SUM``, ``FIRST``, ``FLAT``, ``LAST``, ``LEN``, ``SORT``, ``UNIQUE``, ``LOWER``, ``UPPER``, ``STRIP``\ 。

了解 `更多查詢示範`_ 或 `Pythonic 查詢範例`_

Dataclass 物件
--------------

任何帶有 ``id`` 欄位的 ``@dataclass`` 都能直接讀寫。物件會被攤平成普通的 ``dict``\ ——\ ``id`` 被抽出來當作記錄的鍵——所以存下來的就是一筆普通記錄：仍可查詢、仍可匯出成 CSV、在每一種 ``data_type`` 下都讀得到。

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
       id: str                                       # 必要：會成為記錄的鍵
       name: str
       age: int = 0
       role: Role = Role.USER
       tags: List[str] = field(default_factory=list)
       address: Optional[Address] = None
       joined: Optional[date] = None
       balance: Decimal = Decimal('0')

   jdb = JDb('users.jdb')

   # --- 新增 ---
   jdb += User('u1', 'Alice', 30, Role.ADMIN, ['python'], Address('Taipei', '110'), date(2024, 5, 1), Decimal('12.50'))
   jdb += [User('u2', 'Bob', 25), User('u3', 'Charlie', 35)] # 批次：單一交易
   jdb |= User('u1', 'Ignored')                              # 只插入：u1 已存在，什麼都不會變
   jdb &= User('u2', 'Bobby', 26)                            # 只取代
   jdb['u4'] = User('u4', 'Diana', 28)                       # 指定鍵

   # --- 讀取：成員就地填入，因此同一個緩衝物件可以重複使用 ---
   user = User(id='', name='')
   jdb.get_dc('u1', user)
   print(user.role, user.address.city, user.balance) # 輸出: Role.ADMIN Taipei 12.50

   # --- 更新 ---
   user.age += 1
   jdb += user

   # --- 刪除 ---
   jdb -= user
   del jdb[User('u2', '')]
   del jdb[User('u3', ''), User('u4', '')] # 等同 del jdb['u3', 'u4']

   # --- 仍然是普通記錄：查詢直接作用在欄位上 ---
   jdb += [User('u5', 'Eve', 41, tags=['python']), User('u6', 'Frank', 22, address=Address('Taipei'))]
   print(jdb.find(Query().age > 28))                # 輸出: {'u5': {'name': 'Eve', 'age': 41, ...}}
   print(jdb.find(vals={'address.city': 'Taipei'})) # 輸出: {'u6': {'name': 'Frank', 'age': 22, ...}}

若要自行掌控檔案指標，\ ``f_write_dc`` / ``f_read_dc`` 就是 ``f_write`` / ``f_read`` 的低階對應：

.. code-block:: python

   with jdb.open(read_only=False) as fp:
      jdb.f_write_dc(fp, User('u9', 'Grace'), ttl=30)

   buf = User(id='', name='')
   with jdb.open() as fp:
      for key in jdb.key_table:
         jdb.f_read_dc(fp, key, buf) # 就地填入：每筆記錄不額外配置物件

支援的欄位型別：巢狀 dataclass、\ ``Optional`` / ``Union``\ 、\ ``Enum``\ 、\ ``date`` / ``time`` / ``datetime``\ 、\ ``Decimal``\ 、\ ``UUID``\ 、\ ``Path``\ 、\ ``List`` / ``Dict`` / ``Set`` / ``Tuple``\ 、\ ``frozen=True``\ ，以及 ``init=False`` 欄位。值會依照型別註記重建，所以即使 ``data_type`` 的編碼器沒有原生集合型別，\ ``Set[str]`` 讀回來仍然是 ``set``\ 。

.. note::
   ``id`` 只存成記錄的鍵，\ *不會*\ 在值裡重複一份，因此 ``jdb += user`` 與 ``jdb['u1'] = user`` 寫出的位元組完全相同。若把物件放在別的鍵下（\ ``jdb['alias'] = user``\ ），\ ``id`` 就會保留在值裡面，原本的身分因此能在往返後存活。

   這正是它與 ``data_type='J+P'`` 的差別：pickle 會把物件存成不透明的位元組，查詢、CSV 匯出與跨語言讀取全部失效。在這裡記錄仍然是普通的 dict，所以 ``find()``\ 、\ ``update_if()``\ 、\ ``show()`` 與 ``to_csv()`` 都能繼續作用在它的欄位上。

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

記錄歷史
^^^^^^^^

只要 ``JFlag.REVERT`` 仍然啟用，被覆蓋的舊版本就會停在索引的 dead 區。\ ``history()`` 列出目前還觸及得到的版本（最新的在前），並回傳 ``revert()``\ 、\ ``unmodify()``\ 、\ ``unremove()`` 可以用 ``version=`` 指定的 ``ver`` 編號：

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb('fruit.jdb')      # 是 JFlag.REVERT 讓舊列被保留下來
   jdb['apple'] = 'red'
   jdb['apple'] = 'green'
   jdb['apple'] = 'blue'

   versions = jdb.history('apple', with_value=True, show=True)
   #   history[apple]
   #   ╔═════╤═════╤══════╤════════════╤════════════╤═══════╤═════╤══════╤═══════╗
   #   ║ ver │ row │ live │ created    │ modified   │ flags │ TTL │ size │ value ║
   #   ╟─────┼─────┼──────┼────────────┼────────────┼───────┼─────┼──────┼───────╢
   #   ║ 2   │ 0   │ YES  │ 2026-08-20 │ 2026-08-20 │       │     │ 5    │ blue  ║
   #   ║ 2   │ 1   │ NO   │ 2026-08-20 │ 2026-08-20 │       │     │ 6    │ green ║
   #   ╚═════╧═════╧══════╧════════════╧════════════╧═══════╧═════╧══════╧═══════╝

   print([(v['live'], v['value']) for v in versions])
   # 輸出: [(True, 'blue'), (False, 'green')]

每一筆都是一個 dict，包含 ``row``\ 、\ ``key``\ 、\ ``file_id``\ 、\ ``offset``\ 、\ ``row_size``\ 、\ ``val_size``\ 、\ ``ver``\ 、\ ``cdays``\ 、\ ``mdays``\ 、\ ``ttl``\ 、\ ``key_flags`` 與 ``live``\ ——加上 ``with_value=True`` 時的 ``value``\ 。\ ``live`` 只有 ``jdb[key]`` 今天會讀到的那一筆為 True，其餘停放的版本都是 False，所以已刪除的鍵完全不會有 live 項目。

上面只回來兩個版本：\ ``'red'`` 那一列早已被回收，讓給後來的寫入。這是規則，不是故障——\ ``history()`` 是\ *盡力而為*\ 的稽核軌跡，不是 write-ahead log。版本消失是正常現象。

.. note::

   在預設的 ``min_safe=0`` 之下，對\ **任何**\ 鍵的寫入都可能回收掉另一個鍵的舊版本所在的列，所以在繁忙的資料庫上 ``history()`` 常常只回傳現行記錄。建立資料庫時傳入 ``min_safe=N``\ ，可保留 N 個索引列不被重用：

   .. code-block:: python

      jdb = JDb('fruit.jdb', min_safe=1000)   # 讓約 1000 列的歷史保持可觸及

   超出保留額度的列照舊回收，所以成本是常數，不會隨寫入次數成長。它只在 ``JFlag.REVERT`` 啟用時生效——沒有它就沒有歷史需要保護。

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

Parquet 匯入
------------

需要選用的 ``pyarrow`` 相依套件（\ ``pip install pyarrow``\ ）。

.. code-block:: python

   import pyarrow as pa
   import pyarrow.parquet as pq

   # 先寫一個範例 Parquet 檔
   table = pa.table({
       '_id':   ['p1', 'p2', 'p3'],
       'name':  ['Alice', 'Bob', 'Charlie'],
       'age':   [30, 25, 35],
   })
   pq.write_table(table, 'sample.parquet')


.. code-block:: python

   from omni_json_db import JDb
   jdb = JDb()

   # 預設由第一個欄位（'_id'）成為記錄的鍵
   jdb.from_parquet('sample.parquet')
   print(jdb['p1'])  # 輸出: {'name': 'Alice', 'age': 30}

   # 資料以 pyarrow 的 RecordBatch 串流進來，因此多 GB 的檔案
   # 也只需要很小且固定的記憶體
   jdb.from_parquet('sample.parquet', batch_size=65536)

   # 也可以指定別的鍵欄位，並只保留需要的欄位
   jdb.from_parquet('sample.parquet', key='_id', columns=['name'])

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

支援所有標準\ ``set``: ``union()``, ``intersection()``, ``difference()``, ``isdisjoint()``, ``issubset()``, ``issuperset()``.

更多查詢示範
------------
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
     - 從字串中去除 JSON 格式符號（\ ``[]{}""``\ ）後，再使用正規表達式進行比對。
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
------------------
對於偏好使用 Pythonic 及物件導向語法來過濾資料的開發者（類似 **TinyDB** 的體驗），\ ``omni-json-db`` 提供了 ``Query`` 物件。您可以優雅地使用原生的 Python 運算子（例如 ``==``, ``>``, ``&``, ``|``, ``~``\ ）以及串聯方法來建構複雜的搜尋條件。

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
^^^^^^^^^^^^^^^^^

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
     - ``Query().price.float() == 2.1``\ `
   * - ``.int()``
     - 將值轉換為整數(int)後，再進行比對。
     - ``Query().price.int() != 1``\ `
   * - ``.neg()``
     - 將數值取負值(-val)後，再進行比對。
     - ``Query().price.neg() == -1.2``
   * - ``.str()``
     - 將值轉換為字串(str)後，再進行比對。
     - ``Query().price.str() == '1.2'``
   * - ``.avg()``
     - 計算可迭代物件的算術平均值後，再進行比對。
     - ``Query().prices.avg() == 2.5``\ `
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

記錄旗標
--------

每筆記錄都在鍵索引裡帶著一組 ``JKeyFlag`` 位元，賦予它檔案系統般的屬性。以 ``chmod`` 風格的字串設定：單獨的字母或 ``+`` 表示設定該旗標，\ ``-`` 表示清除，沒有提到的旗標維持原值。

旗標分成三類。\ **儲存型**\ 旗標是記錄本身的屬性，會寫進磁碟。\ **衍生型**\ 旗標由引擎維護，無法用名稱設定。\ **暫時型**\ 旗標描述的是單次呼叫而非記錄——它們永遠不會寫進磁碟，傳入它們也不會改動記錄已儲存的旗標。

**儲存型——記錄本身的屬性**

.. list-table::
   :widths: 8 20 60
   :header-rows: 1

   * - 字母
     - 旗標
     - 效果
   * - ``r``
     - ``READ_ONLY``
     - 寫入與刪除一律被拒絕。
   * - ``a``
     - ``APPEND_ONLY``
     - 值只能成長；縮小、改寫與刪除都會被拒絕。
   * - ``p``
     - ``NO_DELETE``
     - 拒絕刪除，但更新照常通過——可編輯，永不消失。
   * - ``h``
     - ``HIDDEN``
     - ``find()`` / ``show()`` 會略過它；其餘 API 仍看得到。
   * - ``c``
     - ``NO_CACHE``
     - 永不進入 LRU 讀取快取——避免大物件把熱門記錄擠出快取。
   * - ``v``
     - ``NO_REVERT``
     - 不保留舊版本，因此高頻計數器不會撐大索引。
   * - ``0``
     - ``USER0``
     - 留給您的應用程式使用（\ ``0``\ –\ ``3``\ ）；引擎不賦予任何行為。

``READ_ONLY`` 與 ``APPEND_ONLY`` 連刪除也一併擋掉，因此 ``NO_DELETE`` 是唯一能表達「這筆記錄可以改，但絕不能消失」的方式——那正是設定列或帳號記錄想要的保留保證。

**衍生型——由引擎維護**

.. list-table::
   :widths: 8 20 60
   :header-rows: 1

   * - 字母
     - 旗標
     - 效果
   * - ``e``
     - ``EXPIRE``
     - 記錄帶有 TTL。請用 ``ttl=``\ （天數或 ``timedelta``\ ）設定，不能用名稱指定。
   * - ``g``
     - ``GROUP``
     - 記錄本身是一個群組。無法設定。
   * - ``l``
     - ``LINK``
     - 符號連結；請用 ``set_link()`` 設定。

**暫時型——單次呼叫的屬性**

.. list-table::
   :widths: 8 20 60
   :header-rows: 1

   * - 字母
     - 旗標
     - 效果
   * - ``u``
     - ``UNLOCK``
     - 本次呼叫豁免唯讀 / 只可追加 / 不可刪除的鎖，像 ``sudo``\ 。
   * - ``w``
     - ``EXCL``
     - 鍵若已存在就拒絕寫入——只建立。
   * - ``m``
     - ``MUST_EXIST``
     - 鍵若\ *不*\ 存在就拒絕寫入——只更新。\ ``EXCL`` 的鏡像。
   * - ``n``
     - ``NO_FOLLOW``
     - 把 ``LINK`` 當成自己的目標路徑來讀，而不是跟過去；寫入時則是改指向。
   * - ``y``
     - ``NO_ATIME``
     - 寫入但不更動修改日期，因此既有的 TTL 不會被續期。
   * - ``q``
     - ``QUIET``
     - 安靜失敗：遇到鎖時以回傳值表示拒絕，而不是丟出 ``JLockError``\ 。

暫時型旗標是傳給操作本身，而不是傳給 ``set_key_flags()``\ 。它們會被消耗而不被儲存，所以 ``jdb.set(k, v, key_flags='w+r')`` 會拒絕已存在的鍵，\ *並且*\ 在新鍵上存下 ``READ_ONLY``\ 。在 ``find()`` 的判斷式裡指定暫時型旗標會丟出 ``JValueError``\ ，而不是默默地符合所有記錄。

**拒絕是大聲的，打錯字更大聲**

指名一筆被鎖住的記錄會丟出 ``JLockError``\ （它是 ``JKeyError``\ ，也就是 ``KeyError``\ ）：對 ``READ_ONLY`` 記錄執行 ``jdb['config'] = x`` 不再看起來像寫入成功。有兩個旗標可以逐次退出：\ ``'u'``\ （\ ``UNLOCK``\ ）照做不誤，\ ``'q'``\ （\ ``QUIET``\ ）則用舊方式拒絕——\ ``set()`` 回傳 ``None``\ 、\ ``remove()`` 回傳 ``{}``\ 、\ ``f_write()`` 回傳 ``False``\ 、\ ``f_delete()`` 回傳 ``LOCKED``\ 。由選擇器驅動的批次操作（\ ``jdb[re.compile(...)] = v``\ 、\ ``update_if()``\ 、\ ``jdb -= jdb``\ 、CSV/INI/SQL 匯入器、\ ``insert()`` 與其他批次寫入者）仍然會略過不能碰的記錄——它們的設計本來就是盡力而為；只有明確\ *指名*\ 的鍵才會大聲拒絕。\ ``EXCL``\ （\ ``'w'``\ ）與 ``MUST_EXIST``\ （\ ``'m'``\ ）同樣保持安靜：那是\ *呼叫端*\ 自己提出的條件，不是記錄說不，而 ``setdefault()`` 正是建立在這之上。

格式錯誤的 ``key_flags`` 則是另一回事，無論有沒有 ``'q'`` 都會丟出 ``JValueError``\ ：未知的字母（\ ``key_flags='f'``\ ）與未定義的位元（\ ``key_flags=0x200``\ ，而 ``KEY_FLAG_MASK`` 寬到足以把它寫進磁碟）過去都是被默默丟棄的。

.. code-block:: python

   from omni_json_db import JDb, JKeyFlag, JLockError

   jdb = JDb()
   jdb['config']        = {'theme': 'dark'}
   jdb['audit/2026-08'] = ['created']

   # 唯讀：寫入被拒絕，而且會說出來
   jdb.set_key_flags('config', 'r')
   try:
       jdb['config'] = {'theme': 'light'}
   except JLockError as e:
       print(e)                            # write[config] refused: record is locked ...

   print(jdb.set('config', {'theme': 'light'}, key_flags='q'))
                                           # 輸出: None   （安靜地拒絕）
   print(jdb['config'])                    # 輸出: {'theme': 'dark'}

   # 只可追加 + 不留歷史：一份只能成長的稽核日誌
   jdb.set_key_flags('audit/2026-08', 'av')
   jdb['audit/2026-08'] = ['created', 'updated']   # 是延伸 -> 允許
   for bad in (['wiped'], 'not a list'):           # 不是延伸 -> 拒絕
       try:
           jdb['audit/2026-08'] = bad
       except JLockError:
           pass

   print(jdb.remove('audit/2026-08', key_flags='q'))   # 刪除同樣被拒絕
                                           # 輸出: {}
   print(jdb['audit/2026-08'])             # 輸出: ['created', 'updated']

   # 檢視，然後再解鎖（'-r' 只清除 READ_ONLY）
   # 每個旗標 API 都回傳 {key: (flags, ttl)}
   flags, ttl = jdb.get_key_flags('audit/2026-08')['audit/2026-08']
   print(str(JKeyFlag(flags)), ttl)        # 輸出: __a_v______________ 0
   jdb.set_key_flags('config', '-r')
   jdb['config'] = {'theme': 'light'}
   print(jdb['config'])                    # 輸出: {'theme': 'light'}

   # 隱藏：不出現在查詢結果，但不是機密——items() 仍然看得到
   jdb['_scratch'] = 'internal'
   jdb.set_key_flags('_scratch', 'h')
   print(list(jdb.find()))                 # 輸出: ['config', 'audit/2026-08']
   print(jdb['_scratch'])                  # 輸出: internal
   print(list(jdb.find(with_hidden=True))) # 輸出: ['config', 'audit/2026-08', '_scratch']

   # 標記給自己用，旗標也可以自由組合
   jdb.set_key_flags('config', '+0')       # USER0
   jdb.keys.set_flags('config', '+c-0')    # 加上 NO_CACHE，拿掉 USER0

   # 不可刪除：記錄仍可編輯，但什麼都刪不掉它
   jdb['account/42'] = {'plan': 'pro'}
   jdb.set_key_flags('account/42', '+p')
   jdb['account/42'] = {'plan': 'team'}    # 更新 -> 允許
   print(jdb['account/42'])                # 輸出: {'plan': 'team'}
   print(jdb.remove('account/42', key_flags='q'))
                                           # 輸出: {}
   print(jdb.remove('account/42', key_flags='u'))
                                           # 輸出: {'account/42': {'plan': 'team'}}

   # 只建立（'w'）與只更新（'m'），都在寫入 handle 之下判定，
   # 而不是先測試再寫入，所以都不會和其他寫入者競爭
   print(jdb.set('config', {'theme': 'dark'}, key_flags='w'))   # 已存在 -> 拒絕
                                           # 輸出: None
   print(jdb.set('session/abc', ['new'], key_flags='w'))
                                           # 輸出: ['new']
   print(jdb.set('session/xyz', ['nope'], key_flags='m'))       # 不存在 -> 拒絕
                                           # 輸出: None
   print(jdb.set('session/abc', ['touched'], key_flags='m'))
                                           # 輸出: ['touched']

   # 不跟隨：讀連結本身，而不是它指向的東西
   jdb.set_link('latest', 'config')
   print(jdb['latest'])                    # 輸出: {'theme': 'light'}
   print(jdb.get('latest', key_flags='n')) # 輸出: config

記錄過期 (TTL)
^^^^^^^^^^^^^^

可以用 ``ttl=`` 給記錄一段壽命，從它最後一次被修改的時刻起算。接受三種型別，而單位由一條規則決定：

.. list-table::
   :widths: 18 70
   :header-rows: 1

   * - ``ttl=``
     - 意義
   * - ``int``
     - 整天——\ ``ttl=7`` 就是一週。上限為 ``MAX_TTL_DAYS``\ （511）。
   * - ``float``
     - 天，因此小數會落到分鐘——\ ``0.25`` 是 6 小時。
   * - ``timedelta``
     - 照字面採用——\ ``timedelta(minutes=30)``\ 、\ ``timedelta(hours=6)``\ 。

**不到一天的一律進位成整分鐘；一天以上的一律進位成整天。** 所以 ``timedelta(hours=23)`` 是 1380 分鐘，\ ``timedelta(hours=24)`` 是 1 天，\ ``timedelta(hours=40)`` 是 2 天。正的壽命永遠不會被捨去成零：\ ``timedelta(seconds=1)`` 是一分鐘，而不是「沒有 TTL」。

``ttl`` 讀回來時是\ *剩餘天數*\ ，形式與 ``ttl=`` 接受的相同——整天的 TTL 是 ``int``\ ，分鐘級的則是小於 ``1.0`` 的 ``float``\ ——因此從 ``get_key_flags()`` 拿到的值可以直接寫回去。乘上 ``MIN_OF_DAY``\ （1440）就能把不到一天的 TTL 換算成分鐘。

**TTL 永遠不會提早到期。** 兩種單位都以粗粒度儲存——到日或到分——記錄在它最後一天或最後一分鐘結束前都還讀得到。今天以 ``ttl=1`` 寫入的記錄今天還在，明天才消失；一分鐘的 TTL 實際存活 61 到 120 秒。

``EXPIRE`` 是\ **衍生**\ 的：記錄有 TTL 時就被設定，沒有時就被清除。自己指定 ``'e'`` 不會有任何作用——請用 ``ttl=``\ 。

因為倒數是從修改日期起算，一般的寫入會讓它續期。傳入 ``key_flags='y'``\ （\ ``NO_ATIME``\ ）就能在\ *不*\ 延長壽命的情況下更新記錄——這正是「碰一下 session」與「延長 session」的差別。

.. code-block:: python

   import datetime as dt
   from omni_json_db import JDb, JKeyFlag, MIN_OF_DAY

   jdb = JDb()
   jdb['session/abc'] = {'user': 'ana'}

   # 給既有記錄一段以天為單位的壽命
   print(jdb.set_key_flags('session/abc', ttl=7))
                                           # 輸出: {'session/abc': (128, 7)}
   flags, ttl = jdb.get_key_flags('session/abc')['session/abc']
   print(str(JKeyFlag(flags)), ttl)        # 輸出: _______e___________ 7

   # TTL 可與其他旗標並存，也能在改寫後保留
   print(jdb.set_key_flags('session/abc', '+r'))
                                           # 輸出: {'session/abc': (129, 7)}

   # ttl=0 移除它；ttl=None（預設）則不動它
   print(jdb.set_key_flags('session/abc', ttl=0))
                                           # 輸出: {'session/abc': (1, 0)}

   # 不到一天的壽命：timedelta，或一天的小數
   jdb['cart/9'] = ['socks']
   print(jdb.set_key_flags('cart/9', ttl=dt.timedelta(minutes=30)))
                                           # 輸出: {'cart/9': (128, 0.020833333333333332)}
   ttl = jdb.get_key_flags('cart/9')['cart/9'][1]
   print(round(ttl * MIN_OF_DAY), 'minutes')
                                           # 輸出: 30 minutes

   # 0.25 天是 6 小時；一天以上會變成整天
   print(jdb.set_key_flags('cart/9', ttl=0.25))
                                           # 輸出: {'cart/9': (128, 0.25)}
   print(jdb.set_key_flags('cart/9', ttl=1.5))
                                           # 輸出: {'cart/9': (128, 2)}

   # 也可以在寫入記錄的當下設定
   with jdb.open() as fp:
       jdb.f_write(fp, 'otp/123', '558021', ttl=1)
       jdb.f_write(fp, 'otp/456', '331902', ttl=dt.timedelta(seconds=90))

   print(jdb.get_key_flags('otp/123'))     # 輸出: {'otp/123': (128, 1)}
   print(round(jdb.keys['otp/456'][8] * MIN_OF_DAY), 'minutes')
                                           # 輸出: 2 minutes

   # jdb.set() 也接受它，所以一行的快取項目不需要 open()
   jdb.set('tmp/quote', 41.2, ttl=dt.timedelta(minutes=10))

過期的記錄會從所有讀取介面消失——\ ``jdb[key]``\ 、\ ``in``\ 、\ ``items()``\ 、\ ``find()`` 與 ``show()`` 全都略過它——而那一列會在下一次需要空間的寫入時被延遲回收，因此過期機制不需要任何背景執行緒。

符號連結
^^^^^^^^

``set_link()`` 讓一個鍵指向另一筆記錄、一個群組，或群組裡的某個鍵。讀寫都會轉送到目標；刪除連結不會動到目標。

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb()
   reports = jdb.add_group('reports')
   reports['2026-08'] = {'rows': 12}

   # 連到群組裡的一筆記錄
   jdb.set_link('latest', 'reports:::2026-08')
   print(jdb['latest'])                    # 輸出: {'rows': 12}

   jdb['latest'] = {'rows': 13}            # 寫入會穿透到目標
   print(reports['2026-08'])               # 輸出: {'rows': 13}

   # 連到整個群組，像資料夾一樣
   jdb.set_link('current', 'reports')
   print(jdb['current']['2026-08'])        # 輸出: {'rows': 13}

   print(jdb.get_link('latest'))           # 輸出: reports:::2026-08
   del jdb['latest']                       # 只移除連結本身
   print(reports['2026-08'])               # 輸出: {'rows': 13}

   # 'n'（NO_FOLLOW）讀取或改寫連結本身，而不是它的目標
   jdb.set_link('newest', 'reports:::2026-08')
   print(jdb.get('newest', key_flags='n')) # 輸出: reports:::2026-08

   reports['2026-09'] = {'rows': 20}
   jdb.set('newest', 'reports:::2026-09', key_flags='n')   # 就地改指向
   print(jdb['newest'])                    # 輸出: {'rows': 20}

``NO_FOLLOW`` 比較像 ``open(O_NOFOLLOW)`` 而不是 ``readlink()``\ ：一筆\ *不是*\ 連結的記錄照常讀取，而 ``get_link()`` 則會回報它不是連結。

.. note::

   旗標由函式庫執行，而不是作業系統——用舊版本讀同一個檔案，並不會知道新的旗標。特別是 ``HIDDEN`` **不是**\ 存取控制：它只過濾 ``find()`` 與 ``show()``\ ，\ ``dict(jdb.items())`` 裡仍然有那筆記錄。\ ``EXPIRE`` 也不是存取控制——到期以整天為單位、對照本機時鐘計算，所以它是整理工具，不是安全期限。群組列上的旗標只作用於那一列，不會套用到群組裡的記錄。

加速開檔
--------

用 ``key_limit='no'`` 開啟資料庫時，鍵表是靠掃描整個 KEY 檔建立起來的。有兩個彼此獨立的選項可以把這個成本移出關鍵路徑；兩者預設都是關閉的。

**鍵表快照 —** ``index_cache=True``
   在資料庫旁保留一份可丟棄的鍵表副本——磁碟上是 ``<KEY>.KIX``\ 、\ ``JMemFiles`` 是共用緩衝區、\ ``JNetFiles`` 則是伺服器端的 sidecar——讓下一個 handle 直接快轉到快照，只掃描此後寫入的那些列。

**預熱 —** ``warm_up=True``
   在物件建立的當下就用背景執行緒建立鍵表，讓應用程式啟動與載入重疊，而不是由第一次 ``open()`` 承擔全部成本。

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb('data/app.KEY', key_limit='no', index_cache=True, warm_up=True)
   with jdb.open() as fp:       # 由快照還原，而且已經預熱過
      ...

   # 或者兩者都自己控制
   jdb = JDb('data/app.KEY', key_limit='no', index_cache=True)
   th  = jdb.warm_up()          # 回傳 Thread；沒有東西要預熱時回傳 None
   jdb.insert(rows)
   jdb.save_index()             # 自己決定快照何時落盤，例如批次匯入之後

在 30 萬筆記錄（16 位元組的鍵、\ ``key_limit='no'``\ ）上的實測：

.. list-table::
   :widths: 24 14 24
   :header-rows: 1

   * - 
     - 全掃
     - ``.KIX``
   * - 冷開檔（中位數）
     - 326 ms
     - 80 ms（\ **4.1x**\ ）
   * - ``save_index()``
     - —
     - 19.5 ms
   * - sidecar 大小
     - —
     - 7.5 MB（每鍵 25 B）

快照會在關檔時發現 sidecar 落後夠多時自行寫出，而在少於 ``JIo.min_kix_rows``\ （16,384 筆）時完全跳過——那種規模全掃本來就比維護快照便宜。與 KEY 檔對不上的快照——版面或 ``data_type`` 不同、資料庫比 sidecar 新、檔案被截斷、損毀或根本來自別的資料庫——一律被拒絕並改走全掃，所以它永遠不可能提供過時的鍵表。\ ``clear()``\ 、API 版本變更與 ``resize_index_size()`` 則會直接刪掉它。

.. note::

   兩個選項都只對 ``dict`` 後端的鍵表有效（\ ``key_limit='no'`` 與 ``'bt'``\ ）。\ ``LiteKeyTable``\ （\ ``'l0'``\ –\ ``'l5'``\ ）與 ``PartialKeyTable``\ （\ ``+ve``\ ）是延遲載入的，沒有東西可以快照或預熱，因此它們會安靜地什麼都不做。預熱是把延遲\ *藏起來*\ 而不是消除它：載入過程持有 GIL，所以呼叫端只有在自己也在等 I/O 時才會賺到；而同時發生的 ``open()`` 只會單純等到鍵表完成——它永遠不會看到半填滿的鍵表。

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

可在初始化時配置\ ``data_type``:

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

另有兩種舊版版面仍可讀取早期版本寫出的資料庫：\ ``L+J``\ （split 鍵 + JSON 值）與 ``M+M``\ （Marshal 鍵 + Marshal 值）。新建資料庫不建議採用。

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

``J+U``\ 、\ ``S+U`` 與 ``U+U`` 讓您使用自己的編碼取代內建格式。這是加密、自訂壓縮、
protobuf，或任何您想要完全掌控的序列化方式的擴充點。

* ``J+U`` / ``S+U``\ ：鍵（Key）維持 JSON/MsgPack 格式（可讀／體積小），只有值（Value）
  會經過您的自訂編碼。
* ``U+U``\ ：鍵（Key）與值（Value）皆會經過您自己的編碼。

有兩種方式可以註冊編碼：

1. **全域預設**\ ——只需註冊一次，所有以 ``U`` 開頭的 data_type 開啟的 ``JDb`` 都會
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

2. **個別實例**\ ——在 ``JDb()`` 傳入 ``val_codec=``\ （也可搭配 ``key_codec=``\ ），讓
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
* ``br``: Brotli (mode=6, 比\ ``gz``\ 更好)
* ``z1``: Zstandard (mode=6, 比\ ``gz``\ 更好)
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
* ``+ve``: ``PartialKeyTable``\ ——以整數上限決定常駐記憶體的鍵數量，其餘在需要時才從 KEY 檔讀取

``no`` 與 ``bt`` 會在開檔時載入整張表，這正是 ``index_cache`` 與 ``warm_up`` 的用武之地（見 `加速開檔`_）。\ ``l0``\ –\ ``l5`` 與 ``+ve`` 是延遲載入的，兩者都不需要。

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
--------

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
--------

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


📄 授權條款
***********

**omni-json-db** 依 `LICENSE <https://github.com/lukatrum/omni-json-db/blob/main/LICENSE>`_ 檔案的條款釋出。

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
