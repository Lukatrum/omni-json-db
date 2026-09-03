Graph Database
==============

**omni-json-db** natively supports Property Graph structures with the ``GraphDb`` class. You can easily manage nodes, edges, and run complex graph algorithms out of the box.

.. code-block:: python

   from omni_json_db import GraphDb, Query

   # Initialize the graph database in memory (or from a file)
   db = GraphDb()

   # 1. Add Nodes with Schema-less Properties
   db.add_node('Alice', age=25, role='admin')
   db.add_node('Bob', age=30, role='user')
   db.add_node('Charlie', age=35, role='user')

   # 2. Add Edges (Directed or Undirected) with Properties
   db.add_edge('Alice', 'Bob', directed=True, weight=1.5, relation='friend')
   db.add_edge('Bob', 'Charlie', directed=True, weight=2.0, relation='colleague')
   db.add_edge('Charlie', 'Alice', directed=False, weight=0.5) # Undirected edge

   # 3. Neighborhood & Adjacency queries (O(1) lookups)
   print(db.neighbors('Alice')) 
   # Output: {'Bob', 'Charlie'}
   
   print(db.degree('Alice'))
   # Output: {'in': 0, 'out': 1, 'undirected': 1, 'total': 2}

   # 4. Classic Graph Algorithms Built-in
   # Find the shortest path using Dijkstra based on edge weights
   dist, path = db.dijkstra_shortest_path('Alice', 'Charlie', weight_key='weight')
   print(f"Distance: {dist}, Path: {path}") 
   # Output: Distance: 0.5, Path: ['Alice', 'Charlie']

   # Detect cycles in the graph (Alice -> Bob -> Charlie -> Alice)
   print(db.is_cyclic()) 
   # Output: True 

   # 5. Seamless Query Engine Integration
   # You can still use the powerful Query object to filter nodes/edges!
   q = Query()
   admin_nodes = db.find_nodes(q.role == 'admin')
   print(list(admin_nodes)) 
   # Output: ['Alice']

   # 6. Cascade Deletion
   # Removing a node automatically cleans up all connected edges
   db.remove_node('Bob')
   print(db.has_node('Bob')) # Output: False
   print(db.get_edge('Alice', 'Bob', directed=True)) # Output: None
