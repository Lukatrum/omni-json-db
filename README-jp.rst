|Version| |License| |Language1| |Language2| |Language3|

|Logo|

..

   素早いリスが、森中の黄金のどんぐりをあっという間に集めます！

|Build Status| |readthedocs| |Pylint| |Codacy| |Coverage|


📌 対応 Python バージョン
*************************

**omni-json-db** は Python 3.7+ および PyPy3 でテストされています。

|Python Version|

..

   **omni-json-db** が役に立つと思ったら、ぜひ ⭐️ をお願いします！プロジェクトの成長と、より多くの開発者に届くための大きな力になります。

👉 クイックリンク
*****************

- `✨ はじめに`_
- `🤔 なぜ omni-json-db なのか?`_
- `🚀 主な機能`_
- `🛠️ クイックスタート`_
- `📝 仕様説明`_
- `📊 ベンチマーク`_
- `📄 ドキュメント <https://omni-json-db.readthedocs.io>`_
- `👥 コントリビューションガイド`_
- `📄 ライセンス`_

✨ はじめに
***********
**omni-json-db** は、Python 開発者のために設計された高性能な組み込みデータベースエンジンです。超高速なキー・バリュー（Key-Value）ストア、強力なドキュメントデータベースのクエリ機能、そしてグラフデータベースのリレーションシップの間のギャップを埋めるツールです。

超高スループットとスレッドセーフを考慮して構築された **omni-json-db** は、最新のシリアライズ技術（\ *JSON*\ 、\ *MsgPack*\ 、\ *marshal*\ 、\ *pickle*\ 、\ *YAML*\ ）と圧縮アルゴリズムを活用し、大量の *JSON* ワークロードを処理する際に、通常 *SQLite* よりも大幅に高速なストレージレイヤーを提供します。ローカルキャッシュ、ログアグリゲーター、分散マイクロサービス、あるいは複雑なナレッジグラフのいずれを構築する場合でも、「ゼロコンフィギュレーション」のシンプルさで大規模なデータを処理できます。

従来の *SQLite* や *NoSQL* データベースとは異なり、\ **omni-json-db** ではネイティブな Python 構文（スライス、Lambda、正規表現、集合演算）を使用してデータのクエリと操作を行うことができます。また、状態のロールバック（元に戻す / やり直し）をサポートする「タイムトラベル」機能や、ネイティブなグラフ操作も組み込まれています。  

* **スキーマレス (Schema-LESS)**: 事前にテーブルを定義することなく、複雑でネストされたデータを保存できます。

* **サーバーレス (Server-LESS)**: データベースサーバーのオーバーヘッドなしに、ディスクへ直接アクセスします。

* **SQLレス (SQL-LESS)**: ネイティブな Python 構文、正規表現、Lambda を使用してデータ操作を行います。

* **依存レス (Dependency-LESS)**: クリーンな Python 環境でそのまま動作し、\ **必須のサードパーティパッケージはゼロ**\ です——C アクセラレータや追加フォーマットは ``pip install "omni-json-db[full]"`` の 1 行で足せます。

🤔 なぜ omni-json-db なのか?
****************************

従来の SQL / NoSQL データベースと違い、\ **omni-json-db** はスライス、lambda、正規表現、集合演算といったネイティブな Python 構文でデータを検索・操作できます。さらに「タイムトラベル」（元に戻す / やり直し）、プロパティグラフエンジン、プラガブルなシリアライズを標準で備えています。

..

   **omni-json-db** は Python 3.7+ および PyPy3 でテスト済みです。（テストカバレッジ約 100%）

.. list-table::
   :widths: 30 16 10 11 10 9 11 9 9
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
   * - トランザクション / ACID
     - ⚠️ (アトミック操作)
     - ❌
     - ❌
     - ❌
     - ✅
     - ✅
     - ✅
     - ✅
   * - スレッドセーフな並行性
     - ✅ (MR/SW)
     - ❌
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
   * - マルチプロセスアクセス
     - ✅ (ファイルロック)
     - ❌
     - ✅
     - ✅
     - ✅
     - ⚠️ (読取専用)
     - ✅
     - ✅
   * - インメモリモード
     - ✅
     - ✅
     - ❌
     - ✅
     - ❌
     - ❌
     - ✅
     - ✅
   * - CSV / SQLite / Parquet 組み込み
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ⚠️ (CLI)
     - ✅
   * - 圧縮の組み込み
     - ✅
     - ❌
     - ✅
     - ❌
     - ❌
     - ✅
     - ❌
     - ✅
   * - スキーマレス
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
     - ❌
     - ❌
   * - Dataclass マッピング [z]_
     - ✅
     - ❌
     - ⚠️
     - ❌
     - ❌
     - ⚠️
     - ❌
     - ❌
   * - グループ / 名前空間
     - ✅
     - ✅
     - ⚠️
     - ✅
     - ✅
     - ✅
     - ✅
     - ✅
   * - ネストしたグループ + ファンアウト検索
     - ✅
     - ⚠️ (フラット)
     - ❌
     - ⚠️
     - ⚠️ (フラット)
     - ⚠️ (CF)
     - ⚠️ (SQL)
     - ⚠️ (SQL)
   * - 純 Python (PyPy フレンドリー)
     - ✅
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - Pythonic なクエリ (Lambda/Regex)
     - ✅
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 深いネスト検索
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - グラフデータベースエンジン
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 元に戻す / やり直し（タイムトラベル）
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 時系列の日付スライス
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - ネットワークモード（グループ対応）
     - ✅
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
     - ❌
   * - 50 万件での相対速度 [x]_
     - 1.00x (基準)
     - 41.47x
     - 60.95x
     - 4.28x
     - 0.94x
     - 0.45x
     - 0.13x
     - 0.21x
   * - 1000 万件での相対速度 [x]_
     - 1.00x (基準)
     - N/A [y]_
     - N/A [y]_
     - 24.07x
     - 1.31x
     - 0.55x
     - 0.16x
     - 0.05x

.. [x] 数値が小さいほど高速です。（詳細な内訳と計測方法は `benchmark <https://github.com/lukatrum/omni-json-db/blob/main/benchmark/report.txt>`_ を参照）
.. [y] 実用にならないほど低速
.. [z] ``@dataclass`` を書いて、そのままオブジェクトとして読み戻せること。⚠️ = オブジェクトを\ *保存*\ はできるが不透明な ``pickle`` バイト列としてのみで、フィールドはクエリから見えず、ファイルは Python 以外から読めません。


🚀 主な機能
***********

* **ネイティブグラフエンジン**: キー・バリューストアをプロパティグラフに変えます。\ ``GraphDb`` レイヤーは O(1) の隣接インデックスと古典的なアルゴリズム（BFS、Dijkstra、DFS、閉路検出）を、性能を犠牲にせずに提供します。[参照: `グラフデータベース`_]

* **Pythonic な操作**: 使い慣れた ``dict`` メソッド、リストのスライス、集合演算でデータを扱えます。複雑な SQL は不要です。[参照: `基本的な使い方`_ + `演算子`_]

* **Dataclass オブジェクト**: 任意の ``@dataclass`` をそのまま読み書きできます——\ ``jdb += user``\ 、\ ``jdb['u1'] = user``\ 、\ ``del jdb[user]``\ 。オブジェクトは pickle ではなくプレーンな ``dict`` に平坦化されるため、オブジェクトから書いたレコードもクエリ・エクスポート・言語非依存の読み取りが可能なままです。[参照: `Dataclass オブジェクト`_]

* **高度なシリアライズと圧縮**: フォーマット（JSON、MsgPack、Pickle、YAML）と圧縮アルゴリズム（LZ4、Zstandard、Brotli）を組み合わせ、I/O とディスク使用量を最適化します。[参照: `フォーマットの変換`_ + `データタイプ`_ + `圧縮タイプ`_]

* **プラガブルなコーデックと暗号化**: シンプルな ``dumps``/``loads`` インターフェースで独自のシリアライズや暗号化を持ち込めます——フォークは不要です。プロセス全体のデフォルトと、インスタンスごとのコーデック（テナントごとの鍵など）の両方に対応します。[参照: `プラガブルなユーザー定義コーデック（U）`_]

* **強力なクエリエンジン**: 正規表現、Lambda フィルター、豊富な演算子（\ ``EQ``\ 、\ ``GT``\ 、\ ``LT``\ 、\ ``IN``\ 、\ ``HAS``\ 、\ ``RE`` …）で検索できます。[参照: `クエリエンジン`_ + `その他のクエリ例`_ + `Pythonic なクエリの例`_]

* **動作モード**: 高性能なインメモリモード（\ ``JMemFiles``\ ）と、データをネットワーク越しに提供するネットワークモード（\ ``JNetFiles``\ ）に対応します。[参照: `インメモリモード`_ + `ネットワークモード`_]

* **状態管理**: 組み込みの「タイムトラベル」で状態を追跡し、変更を元に戻し（\ ``unmodify()``\ ）、削除したデータを復元（\ ``unremove()``\ ）できます。\ ``history()`` は到達可能なすべてのバージョンを一覧し、\ ``min_safe`` がそのうち何件を残すかを決めます。[参照: `復元 / ロールバック`_ + `レコード履歴`_ + `バックアップ / リストア`_]

* **バッチ書き込み**: 一括挿入は専用の追記パスを通ります——VAL ファイルごとに 1 回の ``write()``\ 、KEY 行はひとつのブロックにまとめて書き出し——レコードごとのシステムコールがなくなるため、\ ``jdb += rows``\ 、\ ``insert()``\ 、各種インポーターが API を変えずに 1.4x〜4.5x 高速になります。[参照: `バルクインサート`_]

* **大規模でも速いオープン**: 使い捨てのキーテーブルスナップショット（\ ``index_cache``\ ）でコールドオープンが約 4 倍速くなり、\ ``warm_up`` が残りをバックグラウンドスレッドへ移します。[参照: `オープンの高速化`_]

* **データ移行**: SQLite からの移行や、CSV / Parquet / INI / TOML の入出力がコマンド 1 つで完了します。Parquet は ``pyarrow`` の RecordBatch でストリーミングされるためメモリ使用量は一定で、数 GB のファイルでも問題ありません。[参照: `CSV インポート / エクスポート`_ + `Parquet インポート`_ + `SQLite インポート`_ + `INI / TOML インポート`_]

* **時系列対応**: ネイティブなタイムスタンプにより日付スライス（\ ``jdb[yesterday:now]`` など）が効率的に行えます。[参照: `時系列`_]

* **メモリキャッシュ**: 調整可能な ``cache_limit`` で RAM 使用量と I/O 速度のバランスを取れます。[参照: `キャッシュタイプ`_]

* **グループ化と名前空間**: グループを使ってデータモジュールを簡単に分離・管理できます。[参照: `グループモード`_]

* **レコード単位のフラグ**: ``chmod`` 風の構文で、任意のレコードにファイルシステムのような属性を与えられます——読取専用、追記専用、隠し、キャッシュしない、履歴を残さない——さらに他のレコードやグループへのシンボリックリンクと、1 分から 511 日までのレコード単位の TTL も使えます。[参照: `レコードフラグ`_ + `シンボリックリンク`_ + `レコードの有効期限 (TTL)`_]

* **並行性制御**: 「複数読み込み / 単一書き込み」環境向けに最適化され、堅牢なファイルロックと Lock メカニズムを備えています。[参照: `高度な使い方`_]


🛠️ クイックスタート
*******************

インストール
------------

**omni-json-db に必須の依存パッケージはありません。** 組み込みの純 Python 実装により、クリーンな Python 環境でそのまま動作するので、これだけで十分です:

.. code-block:: bash

   pip install omni-json-db

最速・全機能のビルド——C アクセラレータ付きシリアライザ（\ ``orjson`` / ``ormsgpack`` / ``msgspec`` / ``msgpack`` / ``bitarray``\ ）、追加の圧縮コーデック（\ ``zstandard`` / ``lz4`` / ``brotli``\ ）、\ ``YAML`` 値フォーマット、\ ``BTrees`` キーインデックスバックエンド——が必要なら ``full`` エクストラをインストールしてください:

.. code-block:: bash

   pip install "omni-json-db[full]"

必要なものだけを選ぶこともできます:

.. code-block:: bash

   pip install "omni-json-db[speed]"        # シリアライザの高速化のみ（差し替えるだけ、機能追加なし）
   pip install "omni-json-db[compression]"  # zstd / lz4 / brotli による値の圧縮
   pip install "omni-json-db[yaml]"         # YAML
   pip install "omni-json-db[btree]"        # B-tree キーインデックスバックエンド

.. note::

   ``[speed]`` は機能を追加せず、ファイルフォーマットも変えません。既定のコードパスを C 実装に差し替えるだけです: JSON 値は ``orjson``\ 、MsgPack 値は ``ormsgpack``\ 、KEY インデックス行は ``msgspec.msgpack``\ （出力はバイト単位で同一、エンジン内で最もホットなパス）、値の拡張型とストリーミングアンパッカーは ``msgpack``\ 、デッド行のビットマップは ``bitarray``\ 。いずれかが無ければ純 Python 実装にフォールバックするため、クリーンな環境でも挙動は同じで、単に遅くなるだけです。PyPy では純 Python パスが十分に速いため ``orjson`` / ``msgspec`` はスキップされます。

   バンドル（\ ``[full]`` / ``[all]``\ ）は自己参照エクストラを使うため ``pip >= 21.2`` が必要です。古い pip（素の Python 3.7 など）では pip を更新する（\ ``python -m pip install -U pip``\ ）か、個別のエクストラをまとめて指定してください: ``pip install "omni-json-db[speed,compression,yaml,btree]"``\ 。

基本的な使い方
--------------

.. code-block:: python

   from omni_json_db import JDb
   
   # Json+mSgpack で初期化、圧縮なし、ファイルモード
   jdb = JDb("example.jdb")

   # データを保存
   jdb["ユーザー1"] = {"名前" : "太郎", "役職": "プログラマー"}
   
   # データを読み出し
   user = jdb["ユーザー1"]
   print(user["名前"], user["役職"]) # 出力: 太郎 プログラマー

   
すべての標準的な ``dict`` メソッドをサポートしています: ``keys()``, ``values()``, ``items()``, ``get()``, ``pop()``, ``setdefault()``, ``update()``.

バルクインサート
----------------

大量のレコードをまとめて書くと専用の追記パスが使われます。特別な指定は不要で、バッチ系の入口はすべてすでにこれを使っています:

.. code-block:: python

   from omni_json_db import JDb

   jdb  = JDb('users.jdb')
   rows = {f'user{i}': {'age': i % 80} for i in range(100_000)}

   jdb += rows                 # __iadd__ -> add()
   jdb.insert(rows)            # 既存のキーは決して上書きしない
   jdb.update(rows)            # 既に存在するキーだけを更新する
   jdb.from_csv('users.csv')   # インポーターはすべて IMPORT_BATCH_ROWS 単位でストリーミング

``add()`` はバッチをキーで振り分けます。既存のキーは ``f_write()`` が 1 件ずつ書き換えるので、更新のセマンティクス、DEAD 行の再利用、履歴の挙動は従来どおりです。\ *新しい*\ キーはまとめて ``f_extend()`` に渡され、1 パスで追記されます: 値は事前にシリアライズしてパディングし、パディング済みのバイト列は VAL ファイルごとに 1 回の ``write()`` で書き出し、KEY 行もひとつのブロックにまとめて一度だけ書き込みます。

バッチ追記が DEAD 領域から行を取り戻すことはありません。新規レコード 1 件につき ``n_lines`` はちょうど 1 行だけ増え、\ ``f_delete()`` が空けた領域はインサートに消費されず後の書き換えのために残ります——すでに削除を経験した DB ほど差が開くのはこのためです。

.. list-table::
   :widths: 40 18 22
   :header-rows: 1

   * - 5 万件、4 回中のベスト
     - v3.00.00
     - v3.00.10+
   * - 新規インサート
     - 0.616 s
     - 0.366 s (1.7x)
   * - DEAD 行が 1 万ある DB へのインサート
     - 1.892 s
     - 0.419 s (4.5x)
   * - インメモリでのインサート
     - 0.540 s
     - 0.324 s (1.7x)
   * - インライン（KEY 行）値
     - 0.305 s
     - 0.215 s (1.4x)
   * - 20 件 x 500 バッチ
     - 0.167 s
     - 0.110 s (1.5x)

明示的なファイルハンドルの下では、\ ``f_extend()`` が ``f_write()`` のバッチ版になります。書き込みロックは自分で取得するので、呼び出し側が用意する必要はありません:

.. code-block:: python

   with jdb.open(read_only=False) as fp:
      new = {'a': 1, 'b': [2, 3]}
      jdb.f_extend(fp, new, ttl=7)              # 出力: True
      # 戻ったとき、`new` には実際に書き込まれたレコードだけが残る
      jdb.f_extend(fp, {'a': 99}, replace=True) # 既存キーも書き換える: 一括アップサート

``ttl=`` と ``key_flags=`` はその呼び出し内のすべてのレコードで共有されます。処理は有界のパスに分割されるため、\ ``records`` がどれだけ長くてもメモリ使用量は一定です。

インメモリモード
----------------

.. code-block:: python

   from omni_json_db import JDb
   # Json+mSgpack で初期化、圧縮なし、インメモリモード
   jdb1 = JDb()

   # データを保存
   jdb1 += {"ユーザー1" : {"名前" : "太郎", "役職": "シニアプログラマー"}}

   # データを読み出し
   print(jdb1["ユーザー1"]["名前"]) # 出力: 太郎

   # 同じメモリを共有する 2 つ目の JDb を作成
   jdb2 = JDb(jdb1)
   jdb2["ユーザー2"] = {"名前" : "花子", "役職": "CEO"}

   # 2 つ目の JDb が入れたデータを 1 つ目から読む
   print(jdb1["ユーザー2"]["名前"]) # 出力: 花子


クエリエンジン
--------------

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


条件演算子には以下のものが含まれます: ``EQ``, ``NE``, ``GT``, ``LT``, ``GTE``, ``LTE``, ``HAS``, ``RE``, ``RE2``, ``FUNC``, ``AND``, ``OR``, ``NOR``, ``NOT``, ``NAND``, ``SIZE``, ``ANY``, ``ALL``, ``NONE``, ``IHAS``, ``NHAS``, ``EXISTS``, ``TYPE``, ``MOD``, ``BETWEEN``, ``NEAR``, ``MATCH``, ``SW``, ``EW``, ``IN``, ``NIN``, ``ANYIN``\ 。

変換演算子には以下のものが含まれます: ``ABS``, ``CEIL``, ``FLOOR``, ``ROUND``, ``FLOAT``, ``INT``, ``NEG``, ``STR``, ``AVG``, ``STD``, ``MAX``, ``MID``, ``MIN``, ``SUM``, ``FIRST``, ``FLAT``, ``LAST``, ``LEN``, ``SORT``, ``UNIQUE``, ``LOWER``, ``UPPER``, ``STRIP``\ 。

`その他のクエリ例`_ + `Pythonic なクエリの例`_ もご覧ください。

Dataclass オブジェクト
----------------------

``id`` フィールドを持つ ``@dataclass`` はそのまま読み書きできます。オブジェクトはプレーンな ``dict`` に平坦化され——\ ``id`` は取り出されてレコードのキーになります——保存されるのは普通のレコードです。つまりクエリ可能で、CSV にエクスポートでき、どの ``data_type`` でも読めます。

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
       id: str                                       # 必須: レコードのキーになる
       name: str
       age: int = 0
       role: Role = Role.USER
       tags: List[str] = field(default_factory=list)
       address: Optional[Address] = None
       joined: Optional[date] = None
       balance: Decimal = Decimal('0')

   jdb = JDb('users.jdb')

   # --- 作成 ---
   jdb += User('u1', 'Alice', 30, Role.ADMIN, ['python'], Address('Taipei', '110'), date(2024, 5, 1), Decimal('12.50'))
   jdb += [User('u2', 'Bob', 25), User('u3', 'Charlie', 35)] # バッチ: 単一トランザクション
   jdb |= User('u1', 'Ignored')                              # 挿入のみ: u1 は存在するので何も変わらない
   jdb &= User('u2', 'Bobby', 26)                            # 置換のみ
   jdb['u4'] = User('u4', 'Diana', 28)                       # キーを明示

   # --- 読み取り: メンバーはその場で埋められるのでバッファを使い回せる ---
   user = User(id='', name='')
   jdb.get_dc('u1', user)
   print(user.role, user.address.city, user.balance) # 出力: Role.ADMIN Taipei 12.50

   # --- 更新 ---
   user.age += 1
   jdb += user

   # --- 削除 ---
   jdb -= user
   del jdb[User('u2', '')]
   del jdb[User('u3', ''), User('u4', '')] # del jdb['u3', 'u4'] と同じ

   # --- あくまで普通のレコード: クエリはフィールドに対して効く ---
   jdb += [User('u5', 'Eve', 41, tags=['python']), User('u6', 'Frank', 22, address=Address('Taipei'))]
   print(jdb.find(Query().age > 28))                # 出力: {'u5': {'name': 'Eve', 'age': 41, ...}}
   print(jdb.find(vals={'address.city': 'Taipei'})) # 出力: {'u6': {'name': 'Frank', 'age': 22, ...}}

ファイルポインタを明示的に扱いたい場合、\ ``f_write_dc`` / ``f_read_dc`` が ``f_write`` / ``f_read`` の低レベル版になります:

.. code-block:: python

   with jdb.open(read_only=False) as fp:
      jdb.f_write_dc(fp, User('u9', 'Grace'), ttl=30)

   buf = User(id='', name='')
   with jdb.open() as fp:
      for key in jdb.key_table:
         jdb.f_read_dc(fp, key, buf) # その場で埋めるのでレコードごとの確保がない

対応するフィールド型: ネストした dataclass、\ ``Optional`` / ``Union``\ 、\ ``Enum``\ 、\ ``date`` / ``time`` / ``datetime``\ 、\ ``Decimal``\ 、\ ``UUID``\ 、\ ``Path``\ 、\ ``List`` / ``Dict`` / ``Set`` / ``Tuple``\ 、\ ``frozen=True``\ 、\ ``init=False`` フィールド。値は型注釈から再構築されるため、コーデックにネイティブな集合型がない ``data_type`` でも ``Set[str]`` は ``set`` として戻ってきます。

.. note::
   ``id`` はレコードのキーとして保存され、値の中に重複して持ちません。したがって ``jdb += user`` と ``jdb['u1'] = user`` はまったく同じバイト列を書きます。別のキーに置いた場合（\ ``jdb['alias'] = user``\ ）は ``id`` が値の中に残るので、元の識別子はラウンドトリップしても失われません。

   これが ``data_type='J+P'`` との決定的な違いです。pickle はオブジェクトを不透明なバイト列として保存するため、クエリ、CSV エクスポート、他言語からの読み取りがすべて失われます。ここではレコードは普通の dict のままなので、\ ``find()``\ 、\ ``update_if()``\ 、\ ``show()``\ 、\ ``to_csv()`` がそのフィールドに対して働き続けます。

復元 / ロールバック
-------------------

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

レコード履歴
^^^^^^^^^^^^

``JFlag.REVERT`` が有効な間、上書きされた古いバージョンはインデックスの dead 領域に残ります。\ ``history()`` はまだ到達できるバージョンを新しい順に一覧し、\ ``revert()`` / ``unmodify()`` / ``unremove()`` が ``version=`` として受け取る ``ver`` 番号を返します:

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb('fruit.jdb')      # 古い行を残すのは JFlag.REVERT
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
   # 出力: [(True, 'blue'), (False, 'green')]

各要素は ``row``\ 、\ ``key``\ 、\ ``file_id``\ 、\ ``offset``\ 、\ ``row_size``\ 、\ ``val_size``\ 、\ ``ver``\ 、\ ``cdays``\ 、\ ``mdays``\ 、\ ``ttl``\ 、\ ``key_flags``\ 、\ ``live`` を持つ dict です（\ ``with_value=True`` のときは ``value`` も付きます）。\ ``live`` が True になるのは ``jdb[key]`` が今読むレコードだけで、残っている過去バージョンはすべて False です。したがって削除済みのキーには live の要素がまったくありません。

上の例で戻ってくるのは 2 バージョンだけです。\ ``'red'`` の行は後の書き込みのためにすでに回収されていました。これは不具合ではなく仕様です——\ ``history()`` は\ *ベストエフォート*\ の監査証跡であり、ライトアヘッドログではありません。バージョンが欠けているのは想定内と考えてください。

.. note::

   既定の ``min_safe=0`` では、\ **どの**\ キーへの書き込みでも別のキーの過去バージョンが載っている行を回収し得るため、書き込みの多い DB では ``history()`` が現行レコードだけを返すことがよくあります。DB 構築時に ``min_safe=N`` を渡すと、N 行を再利用の対象から外して保持できます:

   .. code-block:: python

      jdb = JDb('fruit.jdb', min_safe=1000)   # 約 1000 行分の履歴を到達可能に保つ

   予約を超えた行は従来どおり回収されるので、コストは書き込み回数に比例せず一定です。\ ``JFlag.REVERT`` が有効なときにのみ効きます——無効なら守るべき履歴がそもそもありません。

バックアップ / リストア
-----------------------

.. code-block:: python

   from omni_json_db import JDb

   # mSgpack+Json で初期化、Bzip2 圧縮、ファイルモード
   jdb = JDb("fruit.jdb", data_type="S+J", zip_type='bz')

   # フルーツを JDb に追加
   fruits = {'apple':'red', 'banana':'yellow', 'mango':'yellow', 'lemon':'yellow', 'tomato':'red'}
   jdb += fruits
   assert jdb == fruits

   # bak フォルダーへバックアップ = ./bak/fruit.jdb
   jdb_bak = jdb.backup(folder='bak')
   assert jdb_bak == jdb

   # すべてのデータを削除
   del jdb[fruits]
   assert len(jdb) == 0

   # bak フォルダーから復元
   jdb.restore(folder='bak')
   assert jdb == fruits

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

グラフデータベース
------------------
**omni-json-db** は、\ ``GraphDb`` クラスを通じてプロパティグラフ（Property Graph）構造をネイティブにサポートします。ノードやエッジを簡単に管理し、複雑なグラフアルゴリズムをすぐに実行できます。

.. code-block:: python

   from omni_json_db import GraphDb, Query

   # メモリ上でグラフデータベースを初期化（またはファイルから）
   db = GraphDb()

   # 1. スキーマレスなプロパティを持つノードを追加する
   db.add_node('Alice', age=25, role='admin')
   db.add_node('Bob', age=30, role='user')
   db.add_node('Charlie', age=35, role='user')

   # 2. プロパティを持つエッジを追加する（有向または無向）
   db.add_edge('Alice', 'Bob', directed=True, weight=1.5, relation='friend')
   db.add_edge('Bob', 'Charlie', directed=True, weight=2.0, relation='colleague')
   db.add_edge('Charlie', 'Alice', directed=False, weight=0.5) # 無向エッジ

   # 3. 近傍および隣接クエリ（$O(1)$ 検索）
   print(db.neighbors('Alice')) 
   # 出力: {'Bob', 'Charlie'}
   
   print(db.degree('Alice'))
   # 出力: {'in': 0, 'out': 1, 'undirected': 1, 'total': 2}

   # 4. 組み込みの古典的なグラフアルゴリズム
   # エッジの重みに基づいて Dijkstra 法で最短経路を検索する
   dist, path = db.dijkstra_shortest_path('Alice', 'Charlie', weight_key='weight')
   print(f"距離: {dist}, 経路: {path}") 
   # 出力: 距離: 3.5, 経路: ['Alice', 'Bob', 'Charlie']

   # グラフ内の閉路を検出する (Alice -> Bob -> Charlie - Alice)
   print(db.is_cyclic()) 
   # 出力: True 

   # 5. クエリエンジンとのシームレスな統合
   # 強力な Query オブジェクトを使用してノードやエッジをフィルタリングできます！
   q = Query()
   admin_nodes = db.find_nodes(q.role == 'admin')
   print(list(admin_nodes)) 
   # 出力: ['Alice']

   # 6. カスケード削除
   # ノードを削除すると、接続されているすべてのエッジが自動的にクリーンアップされます
   db.remove_node('Bob')
   print(db.has_node('Bob')) # 出力: False
   print(db.get_edge('Alice', 'Bob', directed=True)) # 出力: None

CSV インポート / エクスポート
-----------------------------

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
---------------------

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


Parquet インポート
------------------

オプション依存の ``pyarrow`` が必要です（\ ``pip install pyarrow``\ ）。

.. code-block:: python

   import pyarrow as pa
   import pyarrow.parquet as pq

   # サンプルの Parquet ファイルを書き出す
   table = pa.table({
       '_id':   ['p1', 'p2', 'p3'],
       'name':  ['Alice', 'Bob', 'Charlie'],
       'age':   [30, 25, 35],
   })
   pq.write_table(table, 'sample.parquet')


.. code-block:: python

   from omni_json_db import JDb
   jdb = JDb()

   # 既定では最初の列（'_id'）がレコードのキーになる
   jdb.from_parquet('sample.parquet')
   print(jdb['p1'])  # 出力: {'name': 'Alice', 'age': 30}

   # 行は pyarrow の RecordBatch でストリーミングされるため、
   # 数 GB のファイルでもメモリ使用量は小さく一定
   jdb.from_parquet('sample.parquet', batch_size=65536)

   # キー列を変えたり、必要な列だけに絞ることもできる
   jdb.from_parquet('sample.parquet', key='_id', columns=['name'])

ネットワークモード
------------------

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
------------------

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


すべての標準的な set メソッドをサポートしています: ``union()``, ``intersection()``, ``difference()``, ``isdisjoint()``, ``issubset()``, ``issuperset()``\ 。

その他のクエリ例
----------------

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
     - 文字列から JSON フォーマット記号（\ ``[]{}""``\ ）を取り除いた後、正規表現を使用して一致させます。
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
   * -
     -
     -   
   * - ``$abs``
     - 数値の絶対値を取得してから比較します。
     - ``{'$abs': 3.14}``
   * - ``$ceil``
     - 数値を切り上げ (math.ceil) てから比較します。
     - ``{'$ceil': 2}``
   * - ``$floor``
     - 数値を切り捨て (math.floor) てから比較します。
     - ``{'$floor': 2}``
   * - ``$round``
     - 数値を四捨五入してから比較します。
     - ``{'$round': 2}``
   * - 
     -
     -
   * - ``$float``
     - 値を浮動小数点数 (float) に変換してから比較します。
     - ``{'$float': 1.0}``
   * - ``$int``
     - 値を整数 (int) に変換してから比較します。
     - ``{'$int': 1.0}``
   * - ``$neg``
     - 数値を負の値 (-val) にしてから比較します。
     - ``{'$neg': -1.2}``
   * - ``$str``
     - 値を文字列 (str) に変換してから比較します。
     - ``{'$str': '1.2'}``
   * - 
     -
     -
   * - ``$avg``
     - 反復可能オブジェクトの算術平均を計算してから比較します。
     - ``{'$avg': 2.0}``
   * - ``$std``
     - 反復可能オブジェクトの母集団の標準偏差を計算してから比較します。
     - ``{'$std': 2.0}``
   * - ``$max``
     - 反復可能オブジェクト内の最大値を取得してから比較します。
     - ``{'$max': 4}``
   * - ``$mid``
     - 配列や文字列の中央の要素/文字（インデックス `len//2`）を取得してから比較します。
     - ``{'$mid': 4}``
   * - ``$min``
     - 反復可能オブジェクト内の最小値を取得してから比較します。
     - ``{'$min': 1}``
   * - ``$sum``
     - 反復可能オブジェクトの合計を計算してから比較します。
     - ``{'$sum': 8}``
   * - 
     -
     -
   * - ``$first``
     - 配列や文字列の最初の要素/文字を取得してから比較します。
     - ``{'$first': 1}``
   * - ``$flat``
     - ネストされた反復可能オブジェクトを平坦化 (flatten) してから比較します。
     - ``{'$flat': [1,2,2,3]}``
   * - ``$last``
     - 配列や文字列の最後の要素/文字を取得してから比較します。
     - ``{'$last': 3}``
   * - ``$len``
     - 配列や文字列の長さを計算してから比較します。
     - ``{'$len': 3}``
   * - ``$sort``
     - 反復可能オブジェクトをソートしてから比較します。
     - ``{'$sort': [1,2,3]}``
   * - ``$unique``
     - 順序を保持して重複を排除してから比較します。
     - ``{'$unique': [2,3,1]}``
   * - 
     -
     -
   * - ``$lower``
     - 文字列を小文字に変換してから比較します。
     - ``{'$lower': 'alice'}``
   * - ``$upper``
     - 文字列を大文字に変換してから比較します。
     - ``{'$upper': 'ALICE'}``
   * - ``$strip``
     - 文字列の前後の空白文字を削除してから比較します。
     - ``{'$strip': 'hi'}``


Pythonic なクエリの例
---------------------
Pythonic でオブジェクト指向な構文によるデータフィルタリングを好む開発者のために（\ **TinyDB** のような使用感）、\ ``omni-json-db`` は ``Query`` オブジェクトを提供しています。Python ネイティブの演算子（例: ``==``, ``>``, ``&``, ``|``, ``~``\ ）やメソッドチェーンをエレガントに使用して、複雑な検索条件を構築できます。

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
   assert set(res) == {'user_1', 'user_3'}

   # 論理結合 (AND & OR)：30歳未満の developer、または admin のユーザーを検索
   res = jdb.find((User.role == 'developer') & (User.age < 30) | (User.role == 'admin'))
   assert set(res) == {'user_1', 'user_2'}

   # 配列クエリ：tags に 'python' が含まれるユーザーを検索
   res = jdb.find(User.tags.has('python'))
   assert set(res) == {'user_1', 'user_3'}

   # パスワイルドカード：すべてのフィールドを再帰的に正規表現検索 (example.com を含む email を検索)
   res = jdb.find(User['**'].matches(r'.@example\.com'))
   assert set(res) == {'user_1'}

   # 高度なフィルター：'email' フィールドを「持たない」ユーザーを検索 (~ は NOT 演算子)
   res = jdb.find(~User.exists('email'))
   assert set(res) == {'user_2', 'user_3'}

   # Lambda テスト：年齢が偶数のユーザーを検索
   res = jdb.find(User.age.test(lambda age: age % 2 == 0))
   assert set(res) == {'user_1', 'user_4'}

   # admin -> Administrator
   res = jdb.update_if(User.role == 'admin', {'role': 'Administrator'})
   assert res == 1 and (User.role == 'Administrator') in jdb
   
   jdb.show();

メソッドと演算子のリファレンス
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
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
   * - ``.abs()``
     - 数値の絶対値を取得してから比較します。
     - ``Query().price.abs() == 3.14``
   * - ``.ceil()``
     - 数値を切り上げ (math.ceil) てから比較します。
     - ``Query().price.ceil() > 3``
   * - ``.floor()``
     - 数値を切り捨て (math.floor) てから比較します。
     - ``Query().price.floor() <= 2``
   * - ``.round()``
     - 数値を四捨五入してから比較します。
     - ``Query().price.round() == 2``
   * - ``.float()``
     - 値を浮動小数点数 (float) に変換してから比較します。
     - ``Query().price.float() == 2.1``\ `
   * - ``.int()``
     - 値を整数 (int) に変換してから比較します。
     - ``Query().price.int() != 1``\ `
   * - ``.neg()``
     - 数値を負の値 (-val) にしてから比較します。
     - ``Query().price.neg() == -1.2``
   * - ``.str()``
     - 値を文字列 (str) に変換してから比較します。
     - ``Query().price.str() == '1.2'``
   * - ``.avg()``
     - 反復可能オブジェクトの算術平均を計算してから比較します。
     - ``Query().prices.avg() == 2.5``\ `
   * - ``.std()``
     - 反復可能オブジェクトの母集団の標準偏差を計算してから比較します。
     - ``Query().prices.std() >= 2.0``
   * - ``.max()``
     - 反復可能オブジェクト内の最大値を取得してから比較します。
     - ``Query().prices.max() == 4``
   * - ``.mid()``
     - 配列や文字列の中央の要素/文字（インデックス `len//2`）を取得してから比較します。 |
     - ``Query().prices.mid() == 4``
   * - ``.min()``
     - 反復可能オブジェクト内の最小値を取得してから比較します。
     - ``Query().prices.min() == 1``
   * - ``.sum()``
     - 反復可能オブジェクトの合計を計算してから比較します。
     - ``Query().prices.sum() == 8``
   * - ``.first()``
     - 配列や文字列の最初の要素/文字を取得してから比較します。
     - ``Query().prices.first() == 1``
   * - ``.flat()``
     - ネストされた反復可能オブジェクトを平坦化 (flatten) してから比較します。
     - ``Query().prices.flat().max() == 4``
   * - ``.last()``
     - 配列や文字列の最後の要素/文字を取得してから比較します。
     - ``Query().prices.last() == 3``
   * - ``.len()``
     - 配列や文字列の長さを計算してから比較します。
     - ``Query().prices.len() == 3``
   * - ``.sort()``
     - 反復可能オブジェクトをソートしてから比較します。
     - ``Query().prices.sort().mid() == 2``
   * - ``.unique()``
     - 順序を保持して重複を排除してから比較します。
     - ``Query().prices.unique().first() == 1``
   * - ``.lower()``
     - 文字列を小文字に変換してから比較します。
     - ``Query().name.lower() == 'alice'``
   * - ``.upper()``
     - 文字列を大文字に変換してから比較します。
     - ``Query().name.upper() == 'ALICE'``
   * - ``.strip()``
     - 文字列の前後の空白文字を削除してから比較します。
     - ``Query().name.strip() == 'Hi'``
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

レコードフラグ
--------------

すべてのレコードはキーインデックスの中に ``JKeyFlag`` のビット列を持ち、ファイルシステムのような属性が与えられます。\ ``chmod`` 風の文字列で設定します: 文字そのもの、または ``+`` で立て、\ ``-`` で降ろし、指定しなかったものは現在値のままです。

フラグは 3 種類あります。\ **保存型**\ はレコード自身の属性でディスクに残ります。\ **派生型**\ はエンジンが管理し、名前では設定できません。\ **一時型**\ はレコードではなく 1 回の呼び出しを表し、ディスクには決して書かれず、渡してもレコードの保存フラグは変わりません。

**保存型——レコード自身の属性**

.. list-table::
   :widths: 8 20 60
   :header-rows: 1

   * - 文字
     - フラグ
     - 効果
   * - ``r``
     - ``READ_ONLY``
     - 書き込みと削除を拒否します。
   * - ``a``
     - ``APPEND_ONLY``
     - 値は伸びることしかできません。縮小・書き換え・削除は拒否されます。
   * - ``p``
     - ``NO_DELETE``
     - 削除は拒否しますが更新は通ります——編集可能、しかし決して消えません。
   * - ``h``
     - ``HIDDEN``
     - ``find()`` / ``show()`` がスキップします。それ以外の API からは見えます。
   * - ``c``
     - ``NO_CACHE``
     - LRU 読み取りキャッシュに入りません——大きな値がホットなレコードを追い出すのを防ぎます。
   * - ``v``
     - ``NO_REVERT``
     - 過去バージョンを残さないので、高頻度カウンターがインデックスを膨らませません。
   * - ``0``
     - ``USER0``
     - アプリケーション用の自由枠（\ ``0``\ –\ ``3``\ ）。エンジンは何の意味も与えません。

``READ_ONLY`` と ``APPEND_ONLY`` は書き込みだけでなく削除も塞ぎます。したがって「このレコードは変更してよいが、決して消えてはいけない」と言えるのは ``NO_DELETE`` だけで、設定行やアカウントレコードが欲しい保持保証はこれです。

**派生型——エンジンが管理**

.. list-table::
   :widths: 8 20 60
   :header-rows: 1

   * - 文字
     - フラグ
     - 効果
   * - ``e``
     - ``EXPIRE``
     - レコードが TTL を持つことを示します。\ ``ttl=``\ （日数または ``timedelta``\ ）で設定し、名前では指定できません。
   * - ``g``
     - ``GROUP``
     - レコードがグループを保持しています。設定はできません。
   * - ``l``
     - ``LINK``
     - シンボリックリンク。\ ``set_link()`` で設定します。

**一時型——1 回の呼び出しの属性**

.. list-table::
   :widths: 8 20 60
   :header-rows: 1

   * - 文字
     - フラグ
     - 効果
   * - ``u``
     - ``UNLOCK``
     - この呼び出しに限り読取専用 / 追記専用 / 削除禁止のロックを免除します（\ ``sudo`` のように）。
   * - ``w``
     - ``EXCL``
     - キーが既に存在する場合は書き込みを拒否——作成専用。
   * - ``m``
     - ``MUST_EXIST``
     - キーが存在\ *しない*\ 場合は書き込みを拒否——更新専用。\ ``EXCL`` の対。
   * - ``n``
     - ``NO_FOLLOW``
     - ``LINK`` を辿らずリンク自身のパスとして読みます。書き込み時は参照先を張り替えます。
   * - ``y``
     - ``NO_ATIME``
     - 更新日時を動かさずに書き込むので、既存の TTL は延長されません。
   * - ``q``
     - ``QUIET``
     - 静かに失敗します。ロックに当たっても ``JLockError`` を投げず戻り値で拒否を示します。

一時型フラグは ``set_key_flags()`` ではなく操作そのものに渡します。保存されず消費されるので、\ ``jdb.set(k, v, key_flags='w+r')`` は既存キーを拒否し、\ *かつ*\ 新規キーには ``READ_ONLY`` を保存します。\ ``find()`` の述語で一時型フラグを指定すると、黙って全件にマッチするのではなく ``JValueError`` が送出されます。

**拒否は明示的に、タイプミスはさらに明示的に**

ロックされたレコードを名指しすると ``JLockError``\ （\ ``JKeyError``\ 、つまり ``KeyError``\ ）が送出されます。\ ``READ_ONLY`` の行に ``jdb['config'] = x`` を実行しても、もう書き込み成功のようには見えません。呼び出しごとに外す方法が 2 つあります: ``'u'``\ （\ ``UNLOCK``\ ）は構わず実行し、\ ``'q'``\ （\ ``QUIET``\ ）は従来どおりの拒否——\ ``set()`` は ``None``\ 、\ ``remove()`` は ``{}``\ 、\ ``f_write()`` は ``False``\ 、\ ``f_delete()`` は ``LOCKED`` を返します。セレクタ駆動の一括操作（\ ``jdb[re.compile(...)] = v``\ 、\ ``update_if()``\ 、\ ``jdb -= jdb``\ 、CSV/INI/SQL インポーター、\ ``insert()`` などのバッチ書き込み）は触れないものをスキップし続けます——設計上ベストエフォートだからです。明示的に\ *名指し*\ されたキーだけが声を上げて拒否します。\ ``EXCL``\ （\ ``'w'``\ ）と ``MUST_EXIST``\ （\ ``'m'``\ ）も静かなままです。それらはレコードの拒否ではなく\ *呼び出し側*\ が求めた条件であり、\ ``setdefault()`` はまさにその上に成り立っています。

不正な ``key_flags`` はこれとは別で、\ ``'q'`` の有無にかかわらず必ず ``JValueError`` を送出します: 未知の文字（\ ``key_flags='f'``\ ）と未定義のビット（\ ``key_flags=0x200``\ 。\ ``KEY_FLAG_MASK`` が広すぎてディスクに書けてしまっていました）は、以前は黙って捨てられていました。

.. code-block:: python

   from omni_json_db import JDb, JKeyFlag, JLockError

   jdb = JDb()
   jdb['config']        = {'theme': 'dark'}
   jdb['audit/2026-08'] = ['created']

   # 読取専用: 書き込みは拒否され、しかもそう言う
   jdb.set_key_flags('config', 'r')
   try:
       jdb['config'] = {'theme': 'light'}
   except JLockError as e:
       print(e)                            # write[config] refused: record is locked ...

   print(jdb.set('config', {'theme': 'light'}, key_flags='q'))
                                           # 出力: None   （静かに拒否）
   print(jdb['config'])                    # 出力: {'theme': 'dark'}

   # 追記専用 + 履歴なし: 伸びることしかできない監査ログ
   jdb.set_key_flags('audit/2026-08', 'av')
   jdb['audit/2026-08'] = ['created', 'updated']   # 拡張 -> 許可
   for bad in (['wiped'], 'not a list'):           # 拡張でない -> 拒否
       try:
           jdb['audit/2026-08'] = bad
       except JLockError:
           pass

   print(jdb.remove('audit/2026-08', key_flags='q'))   # 削除も拒否される
                                           # 出力: {}
   print(jdb['audit/2026-08'])             # 出力: ['created', 'updated']

   # 確認してから解除（'-r' は READ_ONLY だけを降ろす）
   # フラグ系 API はすべて {key: (flags, ttl)} を返す
   flags, ttl = jdb.get_key_flags('audit/2026-08')['audit/2026-08']
   print(str(JKeyFlag(flags)), ttl)        # 出力: __a_v______________ 0
   jdb.set_key_flags('config', '-r')
   jdb['config'] = {'theme': 'light'}
   print(jdb['config'])                    # 出力: {'theme': 'light'}

   # 隠し: クエリ結果には出ないが秘密ではない——items() からは見える
   jdb['_scratch'] = 'internal'
   jdb.set_key_flags('_scratch', 'h')
   print(list(jdb.find()))                 # 出力: ['config', 'audit/2026-08']
   print(jdb['_scratch'])                  # 出力: internal
   print(list(jdb.find(with_hidden=True))) # 出力: ['config', 'audit/2026-08', '_scratch']

   # 自分用のタグ付け。フラグは自由に組み合わせられる
   jdb.set_key_flags('config', '+0')       # USER0
   jdb.keys.set_flags('config', '+c-0')    # NO_CACHE を追加し USER0 を外す

   # 削除禁止: 編集はできるが、何をしても消せない
   jdb['account/42'] = {'plan': 'pro'}
   jdb.set_key_flags('account/42', '+p')
   jdb['account/42'] = {'plan': 'team'}    # 更新 -> 許可
   print(jdb['account/42'])                # 出力: {'plan': 'team'}
   print(jdb.remove('account/42', key_flags='q'))
                                           # 出力: {}
   print(jdb.remove('account/42', key_flags='u'))
                                           # 出力: {'account/42': {'plan': 'team'}}

   # 作成専用（'w'）と更新専用（'m'）。テスト後に書くのではなく
   # 書き込みハンドルの下で判定されるので、他の書き手と競合しない
   print(jdb.set('config', {'theme': 'dark'}, key_flags='w'))   # 存在する -> 拒否
                                           # 出力: None
   print(jdb.set('session/abc', ['new'], key_flags='w'))
                                           # 出力: ['new']
   print(jdb.set('session/xyz', ['nope'], key_flags='m'))       # 存在しない -> 拒否
                                           # 出力: None
   print(jdb.set('session/abc', ['touched'], key_flags='m'))
                                           # 出力: ['touched']

   # 追わない: 参照先ではなくリンク自身を読む
   jdb.set_link('latest', 'config')
   print(jdb['latest'])                    # 出力: {'theme': 'light'}
   print(jdb.get('latest', key_flags='n')) # 出力: config

レコードの有効期限 (TTL)
^^^^^^^^^^^^^^^^^^^^^^^^

``ttl=`` でレコードに寿命を与えられます。起点は最後に更新された時刻です。受け付ける型は 3 つで、単位は 1 つのルールで決まります:

.. list-table::
   :widths: 18 70
   :header-rows: 1

   * - ``ttl=``
     - 意味
   * - ``int``
     - 日単位——\ ``ttl=7`` は 1 週間。\ ``MAX_TTL_DAYS``\ （511）で頭打ちになります。
   * - ``float``
     - 日単位。小数部は分に落ちます——\ ``0.25`` は 6 時間。
   * - ``timedelta``
     - そのまま解釈されます——\ ``timedelta(minutes=30)``\ 、\ ``timedelta(hours=6)``\ 。

**1 日未満はすべて分単位に切り上げ、1 日以上はすべて日単位に切り上げます。** したがって ``timedelta(hours=23)`` は 1380 分、\ ``timedelta(hours=24)`` は 1 日、\ ``timedelta(hours=40)`` は 2 日です。正の寿命がゼロに切り捨てられることはありません: ``timedelta(seconds=1)`` は「TTL なし」ではなく 1 分です。

``ttl`` は\ *残り日数*\ として、\ ``ttl=`` が受け取るのと同じ形で読み戻せます——日単位の TTL は ``int``\ 、分単位は ``1.0`` 未満の ``float``\ ——なので ``get_key_flags()`` から得た値をそのまま書き戻せます。\ ``MIN_OF_DAY``\ （1440）を掛ければ 1 日未満の TTL を分として読めます。

**TTL が早く切れることはありません。** どちらの単位も粗く（日または分に）保存され、レコードは最後の 1 日または 1 分が終わるまで読めます。今日 ``ttl=1`` で書いたレコードは今日はまだあり、明日には消えます。1 分の TTL は 61〜120 秒生きます。

``EXPIRE`` は\ **派生**\ です: レコードが TTL を持てば立ち、持たなければ降ります。\ ``'e'`` を自分で指定しても何も起きません——\ ``ttl=`` を使ってください。

カウントダウンは更新日時から始まるので、通常の書き込みは寿命を延長します。\ ``key_flags='y'``\ （\ ``NO_ATIME``\ ）を渡すと、寿命を\ *延ばさずに*\ レコードを更新できます——セッションに触るのと、セッションを延長するのとの違いです。

.. code-block:: python

   import datetime as dt
   from omni_json_db import JDb, JKeyFlag, MIN_OF_DAY

   jdb = JDb()
   jdb['session/abc'] = {'user': 'ana'}

   # 既存のレコードに日単位の寿命を与える
   print(jdb.set_key_flags('session/abc', ttl=7))
                                           # 出力: {'session/abc': (128, 7)}
   flags, ttl = jdb.get_key_flags('session/abc')['session/abc']
   print(str(JKeyFlag(flags)), ttl)        # 出力: _______e___________ 7

   # TTL は他のフラグと共存し、書き換えても残る
   print(jdb.set_key_flags('session/abc', '+r'))
                                           # 出力: {'session/abc': (129, 7)}

   # ttl=0 で解除。ttl=None（既定）は触らない
   print(jdb.set_key_flags('session/abc', ttl=0))
                                           # 出力: {'session/abc': (1, 0)}

   # 1 日未満の寿命: timedelta か、日の小数
   jdb['cart/9'] = ['socks']
   print(jdb.set_key_flags('cart/9', ttl=dt.timedelta(minutes=30)))
                                           # 出力: {'cart/9': (128, 0.020833333333333332)}
   ttl = jdb.get_key_flags('cart/9')['cart/9'][1]
   print(round(ttl * MIN_OF_DAY), 'minutes')
                                           # 出力: 30 minutes

   # 0.25 日は 6 時間。1 日以上は日単位になる
   print(jdb.set_key_flags('cart/9', ttl=0.25))
                                           # 出力: {'cart/9': (128, 0.25)}
   print(jdb.set_key_flags('cart/9', ttl=1.5))
                                           # 出力: {'cart/9': (128, 2)}

   # 書き込みと同時に設定することもできる
   with jdb.open() as fp:
       jdb.f_write(fp, 'otp/123', '558021', ttl=1)
       jdb.f_write(fp, 'otp/456', '331902', ttl=dt.timedelta(seconds=90))

   print(jdb.get_key_flags('otp/123'))     # 出力: {'otp/123': (128, 1)}
   print(round(jdb.keys['otp/456'][8] * MIN_OF_DAY), 'minutes')
                                           # 出力: 2 minutes

   # jdb.set() も受け取るので、1 行のキャッシュ登録に open() は要らない
   jdb.set('tmp/quote', 41.2, ttl=dt.timedelta(minutes=10))

期限切れのレコードはすべての読み取り面から消えます——\ ``jdb[key]``\ 、\ ``in``\ 、\ ``items()``\ 、\ ``find()``\ 、\ ``show()`` はいずれもスキップします——そしてその行は次に領域を必要とする書き込みで遅延回収されるため、有効期限の管理にバックグラウンドスレッドは不要です。

シンボリックリンク
^^^^^^^^^^^^^^^^^^

``set_link()`` はあるキーを別のレコード、グループ、あるいはグループ内のキーへ向けます。読み書きは参照先に転送され、リンクを削除しても参照先はそのままです。

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb()
   reports = jdb.add_group('reports')
   reports['2026-08'] = {'rows': 12}

   # グループ内のレコードへリンクする
   jdb.set_link('latest', 'reports:::2026-08')
   print(jdb['latest'])                    # 出力: {'rows': 12}

   jdb['latest'] = {'rows': 13}            # 書き込みは参照先に届く
   print(reports['2026-08'])               # 出力: {'rows': 13}

   # フォルダーのようにグループ全体へリンクする
   jdb.set_link('current', 'reports')
   print(jdb['current']['2026-08'])        # 出力: {'rows': 13}

   print(jdb.get_link('latest'))           # 出力: reports:::2026-08
   del jdb['latest']                       # リンクだけを削除する
   print(reports['2026-08'])               # 出力: {'rows': 13}

   # 'n'（NO_FOLLOW）は参照先ではなくリンク自身を読み書きする
   jdb.set_link('newest', 'reports:::2026-08')
   print(jdb.get('newest', key_flags='n')) # 出力: reports:::2026-08

   reports['2026-09'] = {'rows': 20}
   jdb.set('newest', 'reports:::2026-09', key_flags='n')   # その場で張り替え
   print(jdb['newest'])                    # 出力: {'rows': 20}

``NO_FOLLOW`` は ``readlink()`` というより ``open(O_NOFOLLOW)`` に近い挙動です: リンク\ *ではない*\ レコードは普通に読めますが、\ ``get_link()`` はリンクでないと報告します。

.. note::

   フラグを強制するのはライブラリであって OS ではありません——古いリリースが同じファイルを読んでも、新しいフラグのことは知りません。特に ``HIDDEN`` はアクセス制御では\ **ありません**: ``find()`` と ``show()`` を絞り込むだけなので、\ ``dict(jdb.items())`` にはそのレコードが含まれます。\ ``EXPIRE`` もアクセス制御ではありません——有効期限はローカル時計に対して日単位で測られるため、これは整理のための道具であってセキュリティ上の期限ではありません。グループ行に付けたフラグはその行だけに効き、グループの中のレコードには及びません。

オープンの高速化
----------------

``key_limit='no'`` でデータベースを開くと、KEY ファイル全体を走査してキーテーブルを構築します。このコストをクリティカルパスから外す、独立した 2 つの選択肢があります。どちらも既定では無効です。

**キーテーブルのスナップショット —** ``index_cache=True``
   使い捨てのキーテーブルのコピーをデータベースの隣に置きます——ディスクなら ``<KEY>.KIX``\ 、\ ``JMemFiles`` なら共有バッファ、\ ``JNetFiles`` ならサーバー側の sidecar——次に開くハンドルはスナップショットまで早送りし、その後に書かれた行だけを走査します。

**ウォームアップ —** ``warm_up=True``
   インスタンス生成の時点でバックグラウンドスレッドがキーテーブルを構築するので、最初の ``open()`` がすべてを負担するのではなく、アプリの起動処理と重ねられます。

.. code-block:: python

   from omni_json_db import JDb

   jdb = JDb('data/app.KEY', key_limit='no', index_cache=True, warm_up=True)
   with jdb.open() as fp:       # スナップショットから復元され、ウォームアップ済み
      ...

   # 手動で制御することもできる
   jdb = JDb('data/app.KEY', key_limit='no', index_cache=True)
   th  = jdb.warm_up()          # Thread を返す。温めるものが無ければ None
   jdb.insert(rows)
   jdb.save_index()             # スナップショットを書く時機を自分で決める（一括取り込み直後など）

30 万件（16 バイトのキー、\ ``key_limit='no'``\ ）での実測:

.. list-table::
   :widths: 26 16 26
   :header-rows: 1

   * - 
     - フルスキャン
     - ``.KIX``
   * - コールドオープン（中央値）
     - 326 ms
     - 80 ms（\ **4.1x**\ ）
   * - ``save_index()``
     - —
     - 19.5 ms
   * - sidecar のサイズ
     - —
     - 7.5 MB（キーあたり 25 B）

スナップショットは、クローズ時に sidecar が十分に遅れていれば自動で書かれ、\ ``JIo.min_kix_rows``\ （16,384 件）未満では完全にスキップされます——その規模ではフルスキャンの方が安上がりだからです。KEY ファイルと一致しないスナップショット——レイアウトや ``data_type`` の相違、sidecar より新しいデータベース、切り詰め・破損・他所のファイル——は拒否されフルスキャンに戻るため、古いテーブルを提供してしまうことはありません。\ ``clear()``\ 、API バージョンの変更、\ ``resize_index_size()`` は sidecar を削除します。

.. note::

   どちらの選択肢も ``dict`` ベースのキーテーブル（\ ``key_limit='no'`` と ``'bt'``\ ）にのみ適用されます。\ ``LiteKeyTable``\ （\ ``'l0'``\ –\ ``'l5'``\ ）と ``PartialKeyTable``\ （\ ``+ve``\ ）は遅延ロードでスナップショットも予熱も不要なため、静かに何もしません。ウォームアップはレイテンシを取り除くのではなく\ *隠す*\ ものです: ロードは GIL を保持するので、呼び出し側が自分でも I/O を待っている間だけ得をします。また同時の ``open()`` は単純にテーブルが揃うまで待つので、途中まで埋まったテーブルを見ることは決してありません。

高度な使い方
------------

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
* ``J+U``: JSON キー + ユーザー定義値 (プラガブルなコーデック、例: 暗号化)
* ``S+U``: MsgPack キー + ユーザー定義値 (プラガブルなコーデック、例: 暗号化)
* ``U+U``: ユーザー定義キー + ユーザー定義値 (キー・値の両方がプラガブル)

初期のリリースが書いたデータベースを読むために、レガシーな 2 つのレイアウトも受け付けます: ``L+J``\ （split キー + JSON 値）と ``M+M``\ （Marshal キー + Marshal 値）。新規のデータベースにはどちらも推奨しません。

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
.. [d] すべての型 =\ ``str``, ``bytes``, ``bool``, ``int``, ``float``, ``list``, ``tuple``, ``set``, ``dict``, ``None``

プラガブルなユーザー定義コーデック（U）
---------------------------------------

``J+U``\ 、\ ``S+U``\ 、\ ``U+U`` を使うと、組み込みフォーマットの代わりに独自のコーデックを
組み込めます。暗号化、カスタム圧縮、protobuf など、完全に制御したい任意のシリアライズ
方式のための拡張ポイントです。

* ``J+U`` / ``S+U``: キー（Key）は JSON/MsgPack のまま（読みやすい／小さいサイズ）で、
  バリュー（Value）だけが独自のコーデックを通ります。
* ``U+U``: キー行（Key row）とバリュー（Value）の両方が独自のコーデックを通ります。

コーデックを登録する方法は2つあります：

1. **プロセス全体のデフォルト** — 一度登録すれば、\ ``U`` 系の data_type で開いた
   すべての ``JDb`` がそれを使用します。

.. code-block:: python

   from marshal import loads as marshal_loads, dumps as marshal_dumps
   from omni_json_db import JDb, register_user_val_codec

   # --- プロセス全体のデフォルト: Fernet で全ての Value を暗号化 ---
   from cryptography.fernet import Fernet
   fernet = Fernet(Fernet.generate_key())

   register_user_val_codec(
       dumps=lambda data: fernet.encrypt(marshal_dumps(data)),
       loads=lambda raw: marshal_loads(fernet.decrypt(raw)),
   )

   # Key=JSON（読みやすい）, Value=暗号化済み
   jdb = JDb("secure.jdb", data_type="J+U")
   jdb["alice"] = {"ssn": "123-45-6789", "balance": 42.5}
   
   # 再度開くと、自動的に復号される
   jdb2 = JDb("secure.jdb", data_type="J+U")
   assert jdb2["alice"] == {"ssn": "123-45-6789", "balance": 42.5}

2. **インスタンスごと** — ``JDb()`` に ``val_codec=``\ （および必要に応じて
   ``key_codec=``\ ）を渡すことで、異なるインスタンス（例：テナントごと）が同時に
   異なるコーデック／キーを使用できます。

.. code-block:: python

   from marshal import loads as marshal_loads, dumps as marshal_dumps
   from omni_json_db import JDb, JIoVAL_U
   from cryptography.fernet import Fernet

   # --- インスタンスごとのコーデック: テナントごとに独自の暗号化キーを持つ ---
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

圧縮タイプ
---------------------

初期化時に zip_type を設定できます:

* ``no``: 圧縮なし (デフォルト、最速)
* ``gz``: Gzip (mode=1)
* ``bz``: Bzip2 (mode=9, 圧縮率は良いが解凍が最も遅い)
* ``xz``: LZMA
* ``zs``: Zstandard (mode=22, 最高の圧縮率)
* ``br``: Brotli (mode=6, ``gz``\ よりも優れている)
* ``z1``: Zstandard (mode=6, ``gz``\ よりも優れている)
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
----------------

初期化時に ``key_limit`` を設定できます:

* ``no``: ``dict`` を key_table として使用 (デフォルト)
* ``bt``: ``BTree`` を key_table として使用 (``dict`` と比較して 44.3% 削減)
* ``l0`` - ``l5``: ``LiteKeyTable`` モード (``dict`` と比較して 60-75% 削減)
* ``+ve``: ``PartialKeyTable``\ ——常駐させるキー数を整数で上限指定し、残りは必要になった時点で KEY ファイルから読み出します

``no`` と ``bt`` はオープン時にテーブル全体をロードします。\ ``index_cache`` と ``warm_up`` はそのためのものです（`オープンの高速化`_ を参照）。\ ``l0``\ –\ ``l5`` と ``+ve`` は遅延ロードなので、どちらも必要ありません。

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
----------

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

👥 コントリビューションガイド
*****************************

バグ報告、改善や新しいアイデアの議論、拡張機能の作成など、\ **omni-json-db** へのあらゆる形でのコントリビューションを歓迎します！参加方法は以下の通りです：

1. 既存の Issue を確認するか、機能のアイデアやバグについての議論を始めるために新しい Issue を作成します。
2. Github 上の リポジトリ を Fork し、master ブランチから新しいブランチを作成して変更を加えます（いわゆる GitHub Flow です）。
3. バグが修正されたこと、または機能が期待通りに動作することを示すテストを作成します。
4. Pull Request を送信し、マージされて公開されるまでメンテナーに知らせてください ☺


📄 ライセンス
*************

**omni-json-db** は `LICENSE <https://github.com/lukatrum/omni-json-db/blob/main/LICENSE>`_ ファイルの条項に基づいて公開されています。

`English <https://github.com/lukatrum/omni-json-db/blob/main/README.rst>`_ | `中文 <https://github.com/lukatrum/omni-json-db/blob/main/README-tc.rst>`_ | `日本語 <https://github.com/lukatrum/omni-json-db/blob/main/README-jp.rst>`_

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
