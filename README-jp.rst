|Version| |License| |Language1| |Language2| |Language3|

|Logo|

..

	素早いリスが、森中の黄金のどんぐりをあっという間に集めます！

|Build Status| |readthedocs| |Pylint| |Codacy| |Coverage|


📌 支援的 Python 版本
*********************

**omni-json-db** は Python 3.7+ および PyPy3 でテストされています。

|Python Version|

..

   **omni-json-db** が役に立つと思ったら、ぜひ ⭐️ をお願いします！プロジェクトの成長と、より多くの開発者に届くための大きな力になります。

👉 クイックリンク
***************

- `✨ はじめに`_
- `🛠️ クイックスタート`_
- `📝 仕様説明`_
- `📊 ベンチマーク`_
- `📄 ドキュメント <https://omni-json-db.readthedocs.io>`_
- `👥 コントリビューションガイド`_

✨ はじめに
**********
**omni-json-db** は、Python 開発者のために設計された高性能な組み込みデータベースエンジンです。超高速なキー・バリュー（Key-Value）ストアと、強力なドキュメントデータベースのクエリ機能との間のギャップを埋めるツールです。

超高スループットとスレッドセーフを考慮して構築された **omni-json-db** は、最新のシリアライズ技術（*JSON*、*MsgPack*、*marshal*、*pickle*、*YAML*）と圧縮アルゴリズムを活用し、大量の *JSON* ワークロードを処理する際に、通常 *SQLite* よりも大幅に高速なストレージレイヤーを提供します。ローカルキャッシュ、ログアグリゲーター、分散マイクロサービスのいずれを構築する場合でも、「ゼロコンフィギュレーション」のシンプルさで大規模なデータを処理できます。

従来の *SQLite* や *NoSQL* データベースとは異なり、**omni-json-db** ではネイティブな Python 構文（スライス、Lambda、正規表現、集合演算）を使用してデータのクエリと操作を行うことができます。また、状態のロールバック（元に戻す / やり直し）をサポートする「タイムトラベル」機能も組み込まれています。

**omni-json-db** 是一款專為 Python 開發者設計的高效能嵌入式資料庫引擎。 它填補了極速鍵值（Key-Value）儲存與強大文件資料庫查詢功能之間的空白。   

**omni-json-db** 專為超高吞吐量和執行緒安全而構建，利用現代序列化技術（如 *JSON*、*MsgPack*、*marshal*、*pickle*、*YAML*）和壓縮算法，提供了一個在處理大量 *JSON* 工作負載時通常比 *SQLite* 快顯著許多的儲存層。 無論您是在構建本地快取、日誌聚合器還是分散式微服務，它都能以「零配置」的簡易性處理大規模資料。

與傳統的 *SQLite* 或 *NoSQL* 資料庫不同，**omni-json-db** 允許您使用原生的 Python 語法（切片、Lambdas、正則表達式、集合運算）來查詢和操作資料。 它還內建了「時光旅行」功能，支援狀態回滾（復原/重做）。   

* **スキーマレス (Schema-LESS)**: 事前にテーブルを定義することなく、複雑でネストされたデータを保存できます。

* **サーバーレス (Server-LESS)**: データベースサーバーのオーバーヘッドなしに、ディスクへ直接アクセスします。

* **SQLレス (SQL-LESS)**: ネイティブな Python 構文、正規表現、Lambda を使用してデータ操作を行います。

🚀 主な機能
***********

* **ディープな Python 化**: SQL に別れを告げましょう！標準的な Python の ``dict`` メソッド、スライス、さらには ``set`` 演算を使用してデータベースと対話します。[参照: `基本的な使い方`_ + `演算子`_]

* **動的シリアライズと高度な圧縮**: JSON (*orjson*)、MsgPack (*ormsgpack*)、Marshal、Pickle、YAML を自由に組み合わせ、LZ4、Zstandard (z1/z2/zs)、Brotli、Bzip2 などの高度な圧縮アルゴリズムと統合して、I/O 速度とディスク使用量の完璧なバランスを実現します。[参照: `フォーマットの変換`_ + `データタイプ`_ + `圧縮タイプ`_]

* **強力なクエリエンジン**: 正規表現 (Regex)、Lambda フィルター（例: ``jdb[lambda k, v: v > 10]``）、および豊富な条件演算子（``EQ``, ``GT``, ``LT``, ``IN``, ``HAS``, ``RE``）を使用して簡単に検索できます。[参照: `クエリエンジン`_ + `その他のクエリ例`_ + `Pythonic なクエリの例`_ ]

* **メモリキャッシュ**: メモリ使用量と I/O 速度のバランスを調整できる ``cache_limit`` （または ``key_limit``）。[参照: `キャッシュタイプ`_]

* **ネットワークモード (JNetFiles)**: コマンド一つ ``run_files_server()`` だけで、ローカルインスタンスをネットワークサービスに変換します。[参照: `ネットワークモード`_]

* **インメモリモード (JMemFiles)**: データベース全体を RAM 上で実行し、最高のパフォーマンスを実現します（リアルタイムキャッシュや一時的なセッションストレージに最適）。[参照: `インメモリモード`_]

* **「タイムトラベル」とロールバック**: データベースは内部状態を追跡しており、変更を元に戻したり (``unmodify()``)、削除したデータを復元したり (``unremove()``) できます。[参照: `復元 / ロールバック`_ + `フォーマットの変換`_ ]

* **グループ化と名前空間**: グループ（Groups）を使用して、異なるデータモジュールを簡単に分離し、管理できます。[参照: `グループモード`_]

* **ネイティブな CSV サポート**: 組み込みの ``DictReader`` および ``DictWriter`` インターフェースにより、*CSV* から膨大なデータをインポートしたり、*Excel* や *Pandas* で分析するためにエクスポートしたりできます。[参照: `CSV インポート / エクスポート`_]

* **シームレスなデータ移行**: たった1行のコードでインポートとエクスポートが完了！組み込みエンジンは、リレーショナルデータベース (*SQLite*) を *NoSQL* のグループ構造に変換でき、*INI* や *TOML* 構成の解析もサポートします。[参照: `SQLite インポート`_ + `INI / TOML インポート`_]

* **時系列のサポート**: すべてのレコードにタイムスタンプが付与され、強力な日付ベースのスライスクエリをサポートします。例えば、``jdb[yesterday:now]`` を使用して昨日から変更されたすべてのレコードを取得できます。[参照: `時系列`_]

* **並行性制御 (Concurrency Control)**: 「複数読み込み/単一書き込み (Many-Read / Single-Write)」環境向けに最適化されており、堅牢なファイルロックおよび Lock メカニズムを備えています。[参照: `高度な使い方`_]


🛠️ クイックスタート
*****************

インストール
-----------

.. code-block:: bash

   pip install omni-json-db

基本的な使い方
------------

.. code-block:: python

   from omni_json_db import JDb
   
   # Json+mSgpack で初期化、圧縮なし、ファイルモード
   jdb = JDb("example.jdb")

   # データを保存
   jdb["ユーザー1"] = {"名前" : "太郎", "役職": "プログラマー"}
   
   # データを読み出し
   user = jdb["ユーザー1"]
   print(user["名前"], user["役職"]) # 出力: 太郎 プログラマー

   
すべての標準的な ``dict`` メソッドをサポートしています: ``keys()``, ``values()``, ``items()``, ``get()``, ``set()``, ``pop()``, ``setdefault()``, ``update()``.

インメモリモード
--------------

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


クエリエンジン
------------

.. code-block:: python

   from omni_json_db import JDb

   # Json+Marshal で初期化、圧縮なし、インメモリモード
   jdb = JDb(data_type="J+M")

   # キーなしのレコードをまとめて挿入
   jdb += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
           {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]

   # テーブルを表示
   jdb.show()

   # Lambda 関数を使用して 'John' という名前のレコードを検索
   matches = jdb.find(FUNC=lambda key,val: val['name'] == 'John') 
   print(matches) # 出力: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}}

   # 正規表現を使用して 'John' または 'Bob' を検索
   matches = jdb.find(RE='John|Bob')
   print(matches) # 出力: {'0': {'name': 'John', 'age': 22}, '1': {'name': 'John', 'age': 37}, '2': {'name': 'Bob', 'age': 42}} 


条件演算子には以下のものが含まれます: ``EQ``, ``NE``, ``GT``, ``LT``, ``GTE``, ``LTE``, ``HAS``, ``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOR``, ``NOT``, ``NAND``, ``SIZE``, ``ANY``, ``ALL``, ``NONE``, ``IHAS``, ``NHAS``,  ``EXISTS``, ``TYPE``, ``MOD``, ``BETWEEN``, ``NEAR``, ``MATCH``, ``SW``, ``EW``, ``NIN``, ``ANYIN``。 

`その他のクエリ例`_ + `Pythonic なクエリの例`_ もご覧ください。

復元 / ロールバック
-----------------

.. code-block:: python

   from omni_json_db import JDb

   # Json+Pickle で初期化、ZStandard 圧縮、ファイルモード
   jdb = JDb("fruit.jdb", data_type="J+P", zip_type='zs')

   # 書き込み
   jdb["apple"] = "red"

   # 変更
   jdb["apple"] = "blue" 

   # 元に戻す (jdb.unmodify() と同等)
   jdb.revert("apple")
   assert jdb["apple"] == 'red'

   # 削除
   del jdb["apple"] 
   assert "apple" not in jdb

   # 削除を取り消す (jdb.unremove() と同等)
   jdb.revert("apple")
   assert jdb["apple"] == "red"


グループモード
----------------

.. code-block:: python

   from omni_json_db import JDb
   
   # Json+mSgpack で初期化、圧縮なし、ファイルモード
   jdb = JDb('fruit_group.jdb')

   # red グループを追加
   r_jdb = jdb.add_group('red')
   assert r_jdb is jdb['red']

   # yellow グループを追加
   y_jdb = jdb.add_group('yellow')
   assert y_jdb is jdb['yellow']

   # red グループへフルーツをまとめて追加
   r_jdb += {'apple': {'qty':1}, 'tomato': {'qty':2}}

   # yellow グループへフルーツをまとめて追加
   y_jdb += {'banana': {'qty':4}, 'lemon': {'qty':6}, 'mango': {'qty':8}}

   # red グループを読み出し
   print(jdb['red']['apple']['qty'])   # 出力: 1
   print(jdb['red:::apple'])           # 出力: {'red:::apple': {'qty': 1}}
   print(jdb['yellow:::banana'])       # 出力: {'yellow:::banana': {'qty': 4}}

   # すべてのグループから名前に 'a' が含まれるフルーツを検索
   matches = jdb.find(r':::a')
   print(matches) # 出力: ['red:::apple', 'red:::tomato', 'yellow:::banana', 'yellow:::mango']


CSV インポート / エクスポート
--------------------------

.. code-block:: python

   from omni_json_db import JDb

   # Json+Json で初期化、圧縮なし、インメモリモード
   jdb1 = JDb(data_type="J+J")

   # キーなしのレコードをまとめて挿入
   jdb1 += [{'name': 'John', 'age': 22}, {'name': 'John', 'age': 37}, \
            {'name': 'Bob', 'age': 42}, {'name': 'Megan', 'age': 27}]

   # JDb の内容を example.csv にエクスポート
   jdb1.to_csv('example.csv')

   # テーブルを表示
   jdb1.show();

   # 別の JDb を作成
   jdb2 = JDb()

   # CSV ファイルから JDb にインポート
   jdb2.from_csv('example.csv')
   print(jdb2.find(RE='Bob')) # 出力: {'name': 'Bob', 'age': 42}

   # テーブルを表示
   jdb2.show(RE='Bob');


INI / TOML インポート
--------------------

.. code-block:: python
   
   from omni_json_db import JDb
   import io

   jdb = JDb()

   # --- INI フォーマットの準備 ---
   ini_data = """
   [server]
   host = 127.0.0.1
   port = 8080
   """

   jdb.from_ini(io.StringIO(ini_data)) # IOだけでなく、ファイルパスもサポート (例: 'config.ini')
   print(jdb['server/host']) # 出力: 127.0.0.1

   # --- TOML フォーマットの準備 ---
   toml_data = """
   app_name = "Omni Test"
   [network]
   ip = "192.168.1.1"
   port = 8181
   """

   jdb.from_toml(io.StringIO(toml_data)) # IOだけでなく、ファイルパスもサポート (例: 'config.toml')

   print(jdb['/app_name'])    # 出力: Omni Test
   print(jdb['network/ip'])   # 出力: 192.168.1.1


SQLite インポート
-----------------

ステップ 1: *sample.sql* の準備

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

ステップ 2: ``JDb`` へのインポート

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb("migrated_data.jdb")

   # 1行のコードで SQLite データベース全体をロード
   jdb.from_sqlite('sample.sql')

   # SQLite のテーブル (例: 'projects' や 'project_logs') は自動的にグループになります
   projects = jdb['projects']
   logs = jdb['project_logs']

   # NoSQL インターフェースを使用してリレーショナルデータをクエリ
   print(projects[3]['name'])  # ID 3 のプロジェクト名を取得
   print(len(logs))            # ログの総数を取得

   # 強力な Lambda クエリと組み合わせて、特定のプロジェクトのログを検索
   project_3_logs = logs.find(FUNC=lambda val: val['project_id'] == 3)


ネットワークモード
----------------

**サーバーサイド**

.. code-block:: python
   
   from omni_json_db import JDb, run_files_server   
   
   jdb = JDb('storage.jdb')

   # 次と同等です: files='storage.jdb'
   run_files_server(host='127.0.0.1', port=59898, files=jdb)

   # JDb にキーを書き込み
   jdb['remote-key'] = 'secret'

**クライアントサイド**

.. code-block:: python

   from omni_json_db import JDb

   # ファイルサーバーに接続
   jdb = JDb('127.0.0.1:59898')

   # JDb からリモートのキーを読み出し
   print(jdb['remote-key']) # 出力: secret

フォーマットの変換
-----------------

.. code-block:: python

   from omni_json_db import JDb

   # インメモリでデータベースを初期化
   # Key-Value は Json+Json で圧縮なし
   jdb = JDb(data_type='J+J')

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # すべてのフルーツをデータベースに追加
   jdb += fruits
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # 出力: J+J no

   # date_type を 'S+S' に、zip_type を 'lz' に変更
   jdb.upgrade(data_type='S+S', zip_type='lz')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # 出力: S+S lz

   # KEY のタイプのみ 'S' から 'J' に変更
   jdb.change_KEY('J')
   assert jdb == fruits
   print(jdb.data_type, jdb.zip_type) # 出力: J+S lz

時系列
------------

.. code-block:: python

   from omni_json_db import JDb
   import datetime as dt

   # インメモリでデータベースを初期化
   # Key+Value は Json+Json で Brotli(またはGzip) 圧縮
   # メモリ使用量を改善するため Key Table として BTree を使用
   jdb = JDb(data_type="J+J(gz)", key_limit="bt")

   # データを挿入
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits 

   # datetime は作成日時、date は変更日時用
   now = dt.datetime.now()
   today = now.date()

   # 作成日時で検索: date == now
   matches = jdb[now]
   assert matches == fruits

   # 作成日時で検索: date >= now
   matches = jdb[now:]
   assert matches == fruits

   # 作成日時で検索: date < now
   matches = jdb[:now]
   assert len(matches) == 0

   # 作成日時で検索: now <= date <= now+1
   next_date = now + dt.timedelta(days=1)
   matches = jdb[now:next_date]
   assert matches == fruits

   prev_date = now - dt.timedelta(days=1)
   prev_week = now - dt.timedelta(days=7)

   # キーの作成日時を変更
   jdb.keys['apple', 'tomato'] = prev_date
   jdb.keys['mango'] = prev_week
   assert jdb[prev_date] == {'apple':'red', 'tomato':'red'}
   assert jdb[prev_week] == {'mango':'yellow'}

   # 作成日時で検索: date == now
   matches = jdb[now]
   assert set(matches) == {'banana', 'lemon'}

   # 作成日時で検索: date < now
   matches = jdb[:now]
   assert set(matches) == {'apple', 'mango', 'tomato'}

   # 変更日時で検索: date == today
   matches = jdb[today]
   assert matches == fruits

   # キーの変更日時 + 作成日時を変更
   new_modify_date = prev_date.date()
   new_create_date = prev_week.date()
   assert new_modify_date >= new_create_date

   jdb.keys['lemon'] = f'{new_modify_date} {new_create_date}'

   # 変更日時で検索: date == today   
   matches = jdb[today]
   assert set(matches) == {'apple', 'banana', 'mango', 'tomato'}

   # 変更日時で検索: date == prev_date
   matches = jdb[prev_date.date()]
   assert set(matches) == {'lemon'}

   # すべてのキーの作成日時を変更
   jdb.keys[:] = today
   assert jdb[today] == fruits

演算子
--------

.. code-block:: python

   from omni_json_db import JDb

   # インメモリでデータベースを初期化
   # Key+Value は mSgpack+mSgpack で lz4 圧縮
   jdb = JDb(data_type="S+S(lz)")

   # [1] KEY+VAL 演算子
   # <jdb += data> == jdb.update(data)
   data = {f'key{v}':v for v in range(100)}   
   jdb += data
   assert len(jdb) == 100

   # <jdb == data>
   assert jdb == data

   # <jdb |= ..> == jdb.insert(..)
   jdb |= {f'key{v}':v+1 for v in range(102)}
   assert jdb['key100'] == 101
   assert jdb[-2.:] == {'key100':101, 'key101':102} # 最後に変更された2つのレコードを取得
   assert jdb[(f'key{v}' for v in range(100))] == data # jdb[data] == data と同等

   # <jdb -= ..> == jdb.remove(..)
   jdb -= ['key100', 'key101', 'key102', 'key103']
   assert jdb == data

   # <jdb &= ..> == jdb.replace(..)
   jdb &= {f'key{v}':v+1 for v in range(200)}
   assert jdb == {f'key{v}':v+1 for v in range(100)}

   # <jdb ^= ..> == jdb.unmodify(..)
   jdb ^= {f'key{v}' for v in range(100)} # jdb ^= data と同等
   assert jdb == data

   # <jdb[:] = ..> == jdb.update(..)
   jdb[:] = 0 # すべてのレコードを 0 に設定
   assert jdb == {f'key{v}':0 for v in range(100)}
   assert jdb.find(NE=0) == {}

   # すべてのレコードを削除
   jdb -= jdb # del jdb[:] と同等
   assert len(jdb) == 0

   # <jdb ^= ..> == jdb.unremove(..)
   jdb ^= {f'key{v}' for v in range(100)} # jdb ^= data と同等
   assert all(val == 0 for key,val in jdb.items())

   # Lambda VALUE 操作
   jdb[:] = lambda key,val: int(key.replace('key', '')) + val
   assert jdb == data

   # <del jdb[..]> == jdb.remove_fast(..)
   del jdb[data] # del jdb[:] と同等

   # すべてのデータを復元
   jdb ^= data
   assert jdb == data

   # <jdb[..]> == jdb.get_n(..) or jdb.get_all()
   matches = jdb[('key2', 'key22', 'key44', 'key111')]
   assert matches == {'key2':2, 'key22':22, 'key44':44}

   # Lambda KEY 操作
   matches = jdb[lambda key:key.endswith('1')]
   assert set(matches) == {'key1', 'key11', 'key21', 'key31', 'key41', 'key51', 'key61', 'key71', 'key81', 'key91'}

   # マッチしたすべてのレコードを -1 に設定
   jdb[matches] = -1
   matches_2 = jdb[lambda key,val: val == -1]
   assert set(matches) == set(matches_2)
   assert matches_2 == jdb.find(EQ=-1)
   assert matches_2 == jdb.find(FUNC=lambda val: val == -1)

   # RE (正規表現) 検索
   matches_3 = jdb[::r'1$']
   assert matches_2 == matches_3

   # 元に戻す (unmodify)
   jdb ^= matches
   assert jdb == data

   # [2] KEY 演算子
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


すべての標準的な set メソッドをサポートしています: ``union()``, ``intersection()``, ``difference()``, ``isdisjoint()``, ``issubset()``, ``issuperset()``。

その他のクエリ例
--------------

以下は、様々なパラメータと NoSQL 構文を活用する方法の例です。

.. code-block:: python

   from omni_json_db import JDb
   import re

   # インメモリデータベースを初期化
   jdb = JDb()

   # サンプルユーザーレコード
   users = {
      'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
      'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
      'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
      'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # データを挿入
   jdb += users

   # 1. 完全一致 & グローバル検索 (ANY, RE, RE2)
   #----------------------------------------------------------
   # いずれかの属性が 'Alice' と完全に一致するユーザーを検索
   res = jdb.find(ANY='Alice')
   assert list(res) == ['user_1']

   # RE/RE2 は検索のために値を JSON 文字列フォーマットに変換します。
   # 'designer' という文字列を内部に含む任意のレコードを検索
   res = jdb.find(RE=r'designer')
   assert list(res) == ['user_4']

   # RE2 は検索前に一部の JSON 記号 (,[]{}") を削除します
   res = jdb.find(RE2=r'role:designer')
   assert list(res) == ['user_4']

   # 2. リレーショナル & 条件演算子 (vals)
   #----------------------------------------------------------
   # Age (年齢) が 30 以上
   res = jdb.find(vals={'age': {'$gte': 30}}) # find(ANY={'$gte': 30})
   assert list(res) == ['user_1', 'user_3']

   # Age が 30 未満
   res = jdb.find(vals={'age': {'$lt': 30}}) # find(ANY={'$lt': 30})
   assert list(res) == ['user_2', 'user_4']

   # Role (役職) が 'admin' または 'designer'
   res = jdb.find(vals={'role': {'$in': ['admin', 'designer']}})
   assert list(res) == ['user_1', 'user_4']

   # tags に 'python' が含まれる
   res = jdb.find(vals={'tags': {'$has': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   # Age が 30 ではない
   res = jdb.find(vals={'age': {'$ne': 30}}) # find(ANY={'$ne': 30})
   assert list(res) == ['user_2', 'user_3', 'user_4']

   # Age が 28
   res = jdb.find(vals={'age': {'$eq': 28}}) # find(ANY={'$eq': 28})
   assert list(res) == ['user_4']

   # 40 >= Age > 25
   res = jdb.find(vals={'age': {'$gt': 25, '$lte': 40}})
   assert list(res) == ['user_1', 'user_3', 'user_4']

   # 3. 論理グループ化 (AND, OR, NOR, NOT)
   #----------------------------------------------------------
   # Age >= 25 AND Age <= 30
   res = jdb.find(AND=[{'age': {'$gte': 25}}, {'age': {'$lte': 30}}])
   assert list(res) == ['user_1', 'user_2', 'user_4']

   # Role が 'admin' OR Age > 30
   res = jdb.find(OR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
   assert list(res) == ['user_1', 'user_3']

   # Role が 'admin' ではない AND Age <= 30
   res = jdb.find(NOR=[{'role': 'admin'}, {'age': {'$gt': 30}}])
   assert list(res) == ['user_2', 'user_4']

   # ユーザーが developer ではない
   res = jdb.find(NOT={'role': 'developer'})
   assert list(res) == ['user_1', 'user_4']

   # (Role が 'admin' OR Age > 30) AND 'linux' が tags に含まれない
   res = jdb.find(AND=[
      {'$or': [
         {'role': 'admin'},
         {'age': {'$gt': 30}}
      ]},
      {'$not': {'tags': {'$has': 'linux'}}}
   ])
   assert list(res) == ['user_1']

   # 4. 正規表現 (RE, RE2, re.compile)
   #----------------------------------------------------------
   # Eメールドメインの正規表現に一致する値
   res = jdb.find(vals={'email': re.compile(r'.@example.com')})
   assert list(res) == ['user_1']

   # いずれかの属性が正規表現と完全に一致するユーザーを検索
   res = jdb.find(ANY=re.compile(r'.@example.com'))
   assert list(res) == ['user_1']

   # 'li' を含む文字列のグローバルな正規表現検索 ('Alice', 'Charlie', 'linux' にマッチ)
   res = jdb.find(RE=r'li[a-z]')
   assert list(res) == ['user_1', 'user_3']

   # コンパイル済みの正規表現を使用して特定のデータベースキーをマッチング (例: 'user_1', 'user_2' にマッチ)
   res = jdb.find(re.compile(r'^user_[1-2]$'))
   assert list(res) == ['user_1', 'user_2']

   # 5. 配列 / リスト操作
   #----------------------------------------------------------
   # リスト内に tags がちょうど 2 つあるユーザー
   res = jdb.find(vals={'tags': {'$size': 2}})
   assert list(res) == ['user_1', 'user_2', 'user_4']

   # 最初 (インデックス 0) の tag が 'python' であるユーザー
   res = jdb.find(vals={'tags': {'$0': 'python'}})
   assert list(res) == ['user_1', 'user_3']

   # 6. Lambda / カスタム関数 (FUNC) & ページネーション (limit)
   #----------------------------------------------------------
   # Lambda を渡してキーと値を動的に評価する
   # 例: 年齢が偶数である最初のユーザーを検索
   res = jdb.find(
       FUNC=lambda k, v: isinstance(v, dict) and v.get('age', 1) % 2 == 0, 
      limit=1
   )
   assert list(res) == ['user_1']

   # email を持っているユーザー
   res = jdb.find(vals={'email': lambda v: v != ''})
   assert list(res) == ['user_1', 'user_4']

   # email を持っていないユーザー
   res = jdb.find(NOT={'email': lambda v: v != ''})
   assert list(res) == ['user_2', 'user_3']

   # プリミティブな保存値 (ネストされていない) の場合、迅速なキーワード引数を使用できます:
   jdb['simple_counter'] = 50
   res = jdb.find(EQ=50)       # 50 と等しい
   assert list(res) == ['simple_counter']

   res = jdb.find(IN=[40, 50]) # リスト内の値
   assert list(res) == ['simple_counter']

Operators Reference
^^^^^^^^^^^^^^^^^^^^^

.. list-table::
   :widths: 20 30 30
   :header-rows: 1

   * - 演算子 (Operator)
     - 説明 (Description)
     - 使用例 (Example Usage)
   * - ``.``  ``|``  ``/``
     - 深いパス（ディープパス）を使用してドキュメント内のネストされたフィールドにアクセスします。
     - ``{'user.profile.age': {'$gt': 20}}``, ``{'user|tags|0': 'db'}``
   * - ``?``
     - 「単一文字ワイルドカード」キー名の任意の「1文字」に一致します。
     - ``{'user?.prof???.?ge': {'$gt': 20}}``, ``{'user?.tags.?': 'db'}``
   * - ``*`` 
     - 「ワイルドカード」ドキュメント構造内の現在のレベルにある任意のキーに一致します。 
     - ``{'users.*.role': 'admin'}``, ``{'user*|ad*r|city': 'HK'}``
   * - ``**``
     - 「再帰的ワイルドカード」階層の深さを問わず、ドキュメント内の任意の深さにある指定フィールドやキーを再帰的に検索します。
     - ``{'**.role': 'admin'}``, ``{'meta.**': 'database'}``
   * -
     -
     -
   * - ``$0``, ``$1``...
     - 配列の指定したインデックス（0、1...）の要素と正確に一致させます。
     - ``{'$0': 'python'}``
   * - ``$date`` / ``_date``
     - 条件一致の対象として、データベースレコードの内部日付を指定します。
     - ``{'$date': {'$lt': date(2001, 1, 1)}}``, ``{'_date': date(2011,12,1)}``
   * - ``$key`` / ``_id``
     - 条件一致の対象として、データベースレコードの辞書キー（Key/ID）を指定します。
     - ``{'$key': 'user_1'}``, ``{'_id': 'user_1'}``  
   * -
     -
     -
   * - ``$not`` / ``!``
     - クエリ式の結果を反転させます（論理 NOT）。
     - ``{'$not': {'tags': {'$has': 'linux'}}}``, ``{'!tags': {'$has': 'linux'}}``, ``{'tags': {'!$has': 'linux'}}``
   * - ``$and``
     - 複数のクエリ条件を論理 AND（論理積）で結合します。
     - ``{'$and': [{'$has':'python'}, {'$has':'linux'}]}``
   * - ``$nand`` / ``!$and``
     - 複数のクエリ条件を論理 NAND（否定論理積）で結合します。
     - ``{'$nand': [{'$has':'python'}, {'$has':'linux'}]}``
   * - ``$or``
     - 複数のクエリ条件を論理 OR（論理和）で結合します。
     - ``{'$or': [{'$eq': 2000}, {'$eq': 2010}]}``
   * - ``$nor`` / ``!$or``
     - 複数のクエリ条件を論理 NOR（否定論理和）で結合します。
     - ``{'$nor': [{'$eq': 2000}, {'$eq': 2010}]}``
   * -
     -
     -      
   * - ``$all``
     - 値の配列/反復可能オブジェクト内の「すべて」の要素が条件を満たす場合に一致します。
     - ``{'$all': {'$ne': 0}}``
   * - ``$any``
     - 値の配列/反復可能オブジェクト内の「いずれか」の要素が条件を満たす場合に一致します。
     - ``{'$any': 'python'}``
   * - ``$none`` / ``!$any``
     - 値の配列/反復可能オブジェクト内の「どの要素も」条件を満たさない場合に一致します。
     - ``{'$none': {'age': 30}}``
   * - ``$func``
     - フィールドに対してカスタムのラムダ関数（lambda）を評価して一致を判定します。
     - ``{'$func': lambda x: x > 0}``  
   * -
     -
     -
   * - ``$eq``
     - 指定した値と完全に等しい値に一致します。
     - ``{'$eq': 28}``
   * - ``!$eq`` / ``$ne``
     - 指定した値と等しくない値に一致します。
     - ``{'$ne': 30}``,  ``{'!$eq': 30}``
   * - ``$gt``
     - 指定した値より大きい（超過）値に一致します。
     - ``{'$gt': 25}``
   * - ``$gte`` / ``$ge``
     - 指定した値以上の値に一致します。
     - ``{'$gte': 30}``
   * - ``$lt``
     - 指定した値より小さい（未満）値に一致します。
     - ``{'$lt': 30}``
   * - ``$lte`` / ``$le``
     - 指定した値以下の値に一致します。
     - ``{'$lte': 40}``
   * -
     -
     -
   * - ``$in``
     - 指定した配列/セット（集合）内に値が存在する場合に一致します。
     - ``{'$in': ['admin', 'designer']}``
   * - ``!$in`` / ``$nin``
     - 指定した配列/セット（集合）内に値が存在「しない」場合に一致します。
     - ``{'$nin': ['python', 'db']}``, ``{'!$in': ['python', 'db']}``
   * - ``$anyin``
     - 値の配列/反復可能オブジェクト内の「いずれか」の要素が、指定された配列/セット（集合）内に存在する場合に一致します。
     - ``{'$anyin': ['admin', 'manager']}``   
   * - ``$between``
     - 指定した範囲内（最小値と最大値を含む）の値に一致します。
     - ``{'$between': (26, 40)}``
   * - ``!$between``
     - 指定した範囲外の値に一致します。
     - ``{'!$between': (26, 40)}``
   * - ``$near``
     - 許容範囲内（ターゲット値、オフセット）の数値または日付値に一致します。
     - ``{'$near': (20, 9)}``
   * - ``$mod``
     - 「値 % 除数 == 余り」の条件を満たす値に一致します（タプルとして渡されます）。
     - ``{'$mod': (10, 5)}``
   * -
     -
     -
   * - ``$has``
     - 指定した要素または部分文字列を含む配列や文字列に一致します。
     - ``{'$has': 'python'}``
   * - ``!$has`` / ``$nhas``
     - 指定した要素または部分文字列が含まれて「いない」場合に一致します。
     - ``{'$nhas': 'r_1'}``, ``{'!$has': 'r_1'}``
   * - ``$ihas``
     - 大文字と小文字を区別せずに、指定した要素/部分文字列を含む配列や文字列に一致します。
     - ``{'$ihas': 'UseR_'}``  
   * - ``$re`` / ``$regex``
     - 正規表現（Regular Expression）を使用して文字列値に一致させます。
     - ``{'$re': r'li[a-z]'}``, ``{'$re': re.compile(r'li[a-z]')}``
   * - ``$re2``
     - 文字列から JSON フォーマット記号（``[]{}""``）を取り除いた後、正規表現を使用して一致させます。
     - ``{'$re2': r'role:admin'}``
   * - ``$ew``
     - 指定した部分文字列で終わる文字列に一致します。
     - ``{'$ew': '_suffix'}``
   * - ``$sw``
     - 指定した部分文字列で始まる文字列に一致します。
     - ``{'$sw': 'prefix_'}``
   * - 
     -
     -
   * - ``$exists``
     - 指定したフィールド/キーを持つドキュメントに一致します。
     - ``{'$exists': ['age', 'tags']}``
   * - ``!$exists``
     - 指定したフィールド/キーを持たないドキュメントに一致します。
     - ``{'!$exists': ['age']}``
   * - ``$size``
     - 配列/文字列のサイズ/長さが指定した値と等しい場合に一致します。
     - ``{'$size': [1,2,3]}``
   * - ``!$size``
     - 配列/文字列のサイズ/長さが指定した値と等しく「ない」場合に一致します。
     - ``{'!$size': [1,2,3]}``
   * - ``$type``
     - 値が指定された Python 変数の型である場合に一致します。
     - ``{'$type': list}``

Pythonic なクエリの例
--------------------
Pythonic でオブジェクト指向な構文によるデータフィルタリングを好む開発者のために（**TinyDB** のような使用感）、``omni-json-db`` は ``Query`` オブジェクトを提供しています。Python ネイティブの演算子（例: ``==``, ``>``, ``&``, ``|``, ``~``）やメソッドチェーンをエレガントに使用して、複雑な検索条件を構築できます。

.. code-block:: python

   from omni_json_db import JDb, Query

   # 1. データベースを初期化し、テストデータを追加する
   jdb = JDb()
   jdb += {
       'user_1': {'name': 'Alice', 'age': 30, 'email': 'alice@example.com', 'role': 'admin', 'tags': ['python', 'database']},
       'user_2': {'name': 'Bob', 'age': 25, 'role': 'developer', 'tags': ['javascript', 'web']},
       'user_3': {'name': 'Charlie', 'age': 35, 'role': 'developer', 'tags': ['python', 'linux', 'aws']},
       'user_4': {'name': 'Diana', 'age': 28, 'email': 'diana@test.com', 'role': 'designer', 'tags': ['ui', 'ux']}
   }

   # 2. Query インスタンスを作成する
   User = Query()

   # 基本的な比較：年齢が 28 より上のユーザーを検索
   res = jdb.find(User.age > 28)
   # 出力: {'user_1', 'user_3'}

   # 論理結合 (AND & OR)：30歳未満の developer、または admin のユーザーを検索
   res = jdb.find((User.role == 'developer') & (User.age < 30) | (User.role == 'admin'))
   # 出力: {'user_1', 'user_2'}

   # 配列クエリ：tags に 'python' が含まれるユーザーを検索
   res = jdb.find(User.tags.has('python'))
   # 出力: {'user_1', 'user_3'}

   # パスワイルドカード：すべてのフィールドを再帰的に正規表現検索 (example.com を含む email を検索)
   res = jdb.find(User['**'].matches(r'.@example\.com'))
   # 出力: {'user_1'}

   # 高度なフィルター：'email' フィールドを「持たない」ユーザーを検索 (~ は NOT 演算子)
   res = jdb.find(~User.exists('email'))
   # 出力: {'user_2', 'user_3'}

   # Lambda テスト：年齢が偶数のユーザーを検索
   res = jdb.find(User.age.test(lambda age: age % 2 == 0))
   # 出力: {'user_1', 'user_4'}

メソッドと演算子のリファレンス
^^^^^^^^^^^^^^^^^^^^^^^^^^
.. list-table::
   :widths: 20 30 30
   :header-rows: 1

   * - 構文 / 演算子
     - 説明
     - 使用例     
   * - ``==``, ``!=``
     - 一致 / 不一致
     - ``User.name != 'Bob'``
   * - ``>``, ``>=``, ``<``, ``<=``
     - 数値の大小比較
     - ``User.age > 30``, ``User.age < 30``
   * - ``&``
     - 論理積 AND
     - ``(User.age > 20) & (User.role == 'admin')``
   * - ``|``
     - 論理和 OR
     - ``(User.name == 'Alice') | (User.age < 30)``
   * - ``~``
     - 否定 NOT
     - ``~ User.exists('email')``
   * - ``.has(val)``
     - 特定の文字列または配列要素を含む
     - ``User.tags.has('database')``
   * - ``.not_has(val)``
     - 特定の文字列または配列要素を含まない
     - ``User.name.not_has('ice')``
   * - ``.ihas(val)``
     - 大文字小文字を区別せずに含む
     - ``User.name.ihas('alice')``
   * - ``.startswith(val)``
     - 文字列が指定のプレフィックスで始まる
     - ``User.city.startswith(('L', 'H'))``
   * - ``.endswith(val)``
     - 文字列が指定のサフィックスで終わる
     - ``User.name.endswith('b')``
   * - ``.matches(pattern)``
     - 正規表現検索 (``re.search`` に相当)
     - ``User.name.matches(r'[bB]ob')``
   * - ``.fullmatch(pattern)``
     - 正規表現の完全一致 (``re.fullmatch`` に相当)
     - ``User.name.fullmatch(r'.lic.')``
   * - ``.one_of(col)``
     - 値が指定されたコレクションに含まれる
     - ``User.role.one_of(['admin', 'dev'])``
   * - ``.not_in(col)``
     - 値が指定されたコレクションに含まれない
     - ``User.role.not_in(['admin', 'dev'])``
   * - ``.any_in(col)``
     - 配列内のいずれかの要素が指定されたコレクションに含まれる
     - ``User.role.any_in(['admin', 'ceo'])``
   * - ``.between(low, high)``
     - 値または文字列が指定された範囲内にある
     - ``User.age.between(20, 30)``
   * - ``.size_of(size)``     
     - 配列または文字列の長さが一致する
     - ``User.tags.size_of(2)``
   * - ``.exists(fields)``
     - 指定されたフィールドが存在するか確認する
     - ``User.exists('email')``
   * - ``.type_of(type)``
     - データ型を確認する
     - ``User.age.type_of(int)``
   * - ``.mod(div, rem)``
     - 剰余条件 (``div`` で割った余りが ``rem`` となる)
     - ``User._date.mod(7, 5)``
   * - ``.near(target, tol)``
     - 数値が許容誤差 ``tol`` の範囲内で目標値に近い
     - ``User._date.near(today, 1)``
   * - ``.test(func)``
     - 条件判定のためにカスタムの Lambda 関数を渡す
     - ``User.age.test(lambda v: 40 >= v > 18)``
   * - ``field['field']``
     - 特定のフィールドにアクセスする
     - ``User['addr'].city``, ``User.addr.city``
   * - ``.field[0]`` 
     - 配列の特定のインデックス (``User.tags[-1]`` のような負のインデックスもサポート)
     - ``User.tags[1].has('db')``
   * - ``'*'`` / ``'**'`` / ``'?'``
     - 第1階層ワイルドカード / 再帰的な複数階層ワイルドカード / 単一文字ワイルドカードのパス検索
     - ``User['*']``, ``User['**']``, ``User['ci?y']``, ``User['c*y']``
   * - ``._id`` / ``._date``
     - システム予約キー：それぞれドキュメントID (主キー) とタイムスタンプにアクセスする
     - ``User._id``, ``User._date``

高度な使い方
----------

.. code-block:: python

   from omni_json_db import JDb

   # インメモリでデータベースを初期化
   # Key-Value は Json+mSgpack で圧縮なし
   jdb = JDb()

   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}

   # レコードの挿入
   with jdb.open() as fp:
      for fruit,color in fruits.items():
         jdb.f_write(fp, fruit, color)

   assert jdb == fruits

   # レコードの変更
   with jdb.open() as fp:
      for fruit in fruits:
         color = jdb.f_read(fp, fruit)
         jdb.f_write(fp, fruit, color.upper())

   assert jdb != fruits
   assert set(jdb) == set(fruits)

   # レコードを元に戻す (unmodify)
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_unwrite(fp, fruit)

   assert jdb == fruits

   # レコードの削除
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_delete(fp, fruit)

   assert len(jdb) == 0

   # 削除されたレコードの復元
   with jdb.open() as fp:
      for fruit in fruits:
         jdb.f_undelete(fp, fruit)

   assert jdb == fruits

   #---------------------------------------
   with jdb.open() as fp:
      key_table = jdb.key_table

      # 置き換え
      for fruit in key_table:
         color = jdb.f_read(fp, fruit)
         jdb.f_write(fp, fruit, color.upper())

      # 元に戻す
      for fruit in key_table:
         jdb.f_unwrite(fp, fruit)

      # 削除
      for fruit in fruits:
         jdb.f_delete(fp, fruit)

      # 復元
      for fruit in fruits:
         jdb.f_undelete(fp, fruit)

   assert jdb == fruits

   #---------------------------------------
   # すべてを置き換え
   jdb[:] = lambda k,v: v.upper()

   # すべてを元に戻す (unmodify)
   jdb ^= jdb

   # すべてを削除
   jdb -= jdb

   # すべての削除を復元
   jdb ^= fruits

   assert jdb == fruits


📝 仕様説明
*****************

データタイプ
----------------------

初期化時に ``data_type`` を設定できます:

* ``J+J``: JSON キー + JSON 値
* ``J+S``: JSON キー + MsgPack 値 (デフォルト)
* ``J+M``: JSON キー + Marshal 値
* ``J+P``: JSON キー + Pickle 値
* ``J+Y``: JSON キー + YAML 値
* ``S+J``: MsgPack キー + JSON 値
* ``S+S``: MsgPack キー + MsgPack 値
* ``S+M``: MsgPack キー + Marshal 値
* ``S+P``: MsgPack キー + Pickle 値
* ``S+Y``: MsgPack キー + YAML 値

*データサイズ = 70,840,580 (MB = 1,000,000B, 圧縮なし)*

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

.. [a] ``list`` に変換して対応
.. [b] 16進数文字列 (hex string) に変換して対応
.. [c] 文字列キーのみサポート
.. [d] すべての型 =``str``, ``bytes``, ``bool``, ``int``, ``float``, ``list``, ``tuple``, ``set``, ``dict``, ``None``

圧縮タイプ
---------------------

初期化時に zip_type を設定できます:

* ``no``: 圧縮なし (デフォルト、最速)
* ``gz``: Gzip (mode=1)
* ``bz``: Bzip2 (mode=9, 圧縮率は良いが解凍が最も遅い)
* ``xz``: LZMA
* ``zs``: Zstandard (mode=22, 最高の圧縮率)
* ``br``: Brotli (mode=6, ``gz``よりも優れている)
* ``z1``: Zstandard (mode=6, ``gz``よりも優れている)
* ``z2``: Zstandard (mode=11)
* ``lz``: LZ4 (mode=0, 圧縮/解凍が最速だが、圧縮率は最も悪い)

**データサイズ = 70,840,580 (MB = 1,000,000B)**

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

キャッシュタイプ
--------------

初期化時に ``key_limit`` を設定できます:

* ``no``: ``dict`` を key_table として使用 (デフォルト)
* ``bt``: ``BTree`` を key_table として使用 (``dict`` と比較して 44.3% 削減)
* ``l0`` - ``l5``: ``LiteKeyTable`` モード (``dict`` と比較して 60-75% 削減)

**テーブルサイズ = 3,241,854 キー**

+---------------+--------+--------------+------------+--------------+
| ``key_limit`` | memory | key search   | HIT > get()| MISS > get() |
+===============+========+==============+============+==============+
| ``no``        | 519MB  | 48.59Mo/s    | 29.28Mo/s  | 18.3Mo/s     |
+---------------+--------+--------------+------------+--------------+
| ``bt``        | 289MB  | 3.46Mo/s     | 3.07Mo/s   | 8.04Mo/s     |
+---------------+--------+--------------+------------+--------------+
| ``l3``        | 85MB   | 2.01Mo/s     | 2.01Mo/s   | 1.59Mo/s     |
+---------------+--------+--------------+------------+--------------+

📊 ベンチマーク
***************

テスト環境
-------

.. code-block:: python

   >> from omni_json_db import JDb
   >> size = 1_000_000
   >> jdb = JDb(data_type='J+J')
   >> data = {f'key{k}':k for k in range(size)}
   
   >> # ベンチマーク操作
   >> jdb += data        # 挿入 (insert)
   >> jdb[:]             # 全取得 (get_all)
   >> jdb -= data        # 削除 (remove)
   >> jdb ^= data        # 削除復元 (revert=unremove)
   >> jdb[data] = -1     # 変更 (replace)
   >> jdb ^= data        # 変更復元 (revert=unmodify)
   >> print(jdb == data) # 出力: True

測定結果
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

👥 コントリビューションガイド
***************************

バグ報告、改善や新しいアイデアの議論、拡張機能の作成など、**omni-json-db** へのあらゆる形でのコントリビューションを歓迎します！参加方法は以下の通りです：

1. 既存の Issue を確認するか、機能のアイデアやバグについての議論を始めるために新しい Issue を作成します。
2. Github 上の リポジトリ を Fork し、master ブランチから新しいブランチを作成して変更を加えます（いわゆる GitHub Flow です）。
3. バグが修正されたこと、または機能が期待通りに動作することを示すテストを作成します。
4. Pull Request を送信し、マージされて公開されるまでメンテナーに知らせてください ☺

English_ | 中文_ | 日本語_

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


