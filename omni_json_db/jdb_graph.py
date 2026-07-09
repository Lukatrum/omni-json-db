# pylint: disable=too-many-lines
from __future__ import annotations
from datetime import date as dt_date, datetime
from collections import deque
from heapq import heappop, heappush
from re import compile as re_compile
from typing import Any, Union, Dict, List, Set, Tuple, Optional, Generator, IO
# --------------------------------
from .jdb_lite import JDbReader
from .jdb_file import JFilesBase
from .jdb import JDb
from .jdb_query import Condition, Query

MAX_RECURSION = 500

class GraphDb(JDb):
    """Graph database layer built on top of the JDb key-value store.
 
    Nodes are stored under keys of the form ``N:{node_id}:`` with a dict of
    properties as the value. Edges are stored under ``E:{u}:>:{v}:`` for
    directed edges and ``E:{u}:-:{v}:`` for undirected edges (endpoints
    sorted lexicographically), also with a dict of properties as the value.
 
    Provides node/edge CRUD, neighborhood queries, and classic graph
    algorithms (BFS/Dijkstra shortest path, DFS traversal, cycle detection,
    topological sort, connected components) executed directly over the
    underlying key table.
    """
    __slots__ = ()

    ADJ_RE = re_compile(r'^X:(.+?):$')
    EDGE_RE = re_compile(r'^E:(.+?):([->]):(.+?):$')
    NODE_RE = re_compile(r'^N:(.+?):$')

    def __init__(self,\
            KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None]=None,\
            data_type:Union[str,int,None]='J+S',\
            zip_type:Union[str,int,None]='no',\
            key_limit:Union[str,int,None]='no',\
            cache_limit:int=0,\
            **kwargs):
        """
        Initialize the transactional JDb controller object mapping configurations sheets models.
 
        Args:
            KEY_file (Union[str, bytearray, JFilesBase, JDbReader, None], optional): File path, memory buffer, or network host.
            data_type (Union[str, int, None], optional): Serialization format
            zip_type (Union[str, int, None], optional): Compression algorithm to use.
            key_limit (Union[str, int, None], optional): Key table limitation constraint.
            cache_limit (int, optional): In-memory object cache limit.
            **kwargs: Extra arguments passed to internal components.
        
        Raises:
            TypeError: Raised if provided arguments are of the incorrect type.
 
        """
        super().__init__(KEY_file=KEY_file,
            cache_limit=cache_limit,
            key_limit=key_limit,
            data_type=data_type,
            zip_type=zip_type,
            **kwargs)

    def add_node(self, node_id:str, **properties) -> bool:
        """Add a node, or merge new properties into an existing node.
 
        If the node already exists, ``properties`` are merged over the stored
        properties (shallow update); nothing is written when the merge does
        not change anything.
 
        Args:
            node_id (str): Unique node identifier.
            **properties: Arbitrary node properties to store.
 
        Returns:
            bool: True if a write occurred, False if nothing changed.
        """
        if not node_id or node_id.find(':') >= 0:
            raise KeyError('invalid node_id')

        with self.open() as fp:
            return self.f_add_node(fp, node_id, **properties)

    def get_node(self, node_id:str) -> Dict[str,Any]:
        """Get the properties of a node.
 
        Args:
            node_id (str): Node identifier.
 
        Returns:
            Dict[str, Any]: Node properties, or None if the node does not exist.
        """
        with self.open() as fp:
            return self.f_get_node(fp, node_id)

    def remove_node(self, node_id:str) -> Dict[str,Any]:
        """Remove a node together with all edges connected to it.
 
        Args:
            node_id (str): Node identifier.
 
        Returns:
            Dict[str, Any]: Mapping of every deleted key (the node key and all
                incident edge keys) to its stored value. Empty if the node
                does not exist.
        """
        with self.open() as fp:
            return self.f_remove_node(fp, node_id)

    def has_node(self, node_id:str) -> bool:
        """Check whether a node exists.
 
        Args:
            node_id (str): Node identifier.
 
        Returns:
            bool: True if the node exists, otherwise False.
        """
        with self.open() as fp:
            return self.f_has_node(fp, node_id)

    def find_nodes(self, condition:Union[Dict[str,Any],Condition], date:Optional[Any]=None, limit:int=0, skip:int=0, **kwargs) -> Dict[str,Any]:
        """Find nodes whose properties match a query condition.
 
        Args:
            condition (Union[Dict[str, Any], Condition]): Query condition or
                property-equality dict passed through to ``find_iter``.
            date (Optional[Any], optional): Temporal filter forwarded to ``find_iter``.
            limit (int, optional): Maximum number of results. 0 means no limit.
            skip (int, optional): Number of matches to skip.
            **kwargs: Extra arguments forwarded to ``find_iter``.
 
        Returns:
            Dict[str, Any]: Mapping of ``node_id`` to node properties for every match.
        """
        ret = {}
        node_re = self.NODE_RE
        node_match = node_re.match
        for key, val in self.find_iter(node_re, vals=condition, date=date, limit=limit, skip=skip, with_value=True, **kwargs):
            matched = node_match(key)
            ret[matched.groups()[0]] = val
        return ret

    def iter_nodes(self) -> Generator[Tuple[str,int],None,None]:
        """Iterate over all nodes in the graph.
 
        Yields:
            str, int: ``node_id, row_id`` for each node.
        """
        with self.open() as fp: # pylint: disable=W0135
            yield from self.f_iter_nodes(fp)

    def add_edge(self, u:str, v:str, directed:bool=True, **properties) -> bool:
        """Add an edge between two nodes, creating missing endpoint nodes.
 
        If the edge already exists, ``properties`` are merged over the stored
        properties; nothing is written when the merge does not change anything.
 
        Args:
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): True for a directed edge ``u -> v``,
                False for an undirected edge. Defaults to True.
            **properties: Arbitrary edge properties to store.
 
        Returns:
            bool: True if a write occurred, False if nothing changed.
 
        Raises:
            ValueError: If ``u`` equals ``v`` (self-loops are not allowed).
        """
        if u == v:
            raise KeyError('u cannot be v')

        if not u or not v or u.find(':') >= 0 or v.find(':') >= 0:
            raise KeyError('invalid u or v')

        with self.open() as fp:
            return self.f_add_edge(fp, u, v, directed, **properties)

    def add_temporal_edge(self, u:str, v:str, directed:bool, expire_days:Union[int,float,str,dt_date,datetime]):
        """Add temporal Edge with expire days.

        Args:
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): True for a directed edge ``u -> v``,
                False for an undirected edge. Defaults to True.            
            expire_days (Union[int, float, str, dt_date, datetime]): 
                
                - int : days since 1-1-1
                    
                    >>> jdb.set_days('key', 1)

                - str : 'YYYY-MM-DD' or 'YYYY-MM-DD YYYY-MM-DD'

                    >>> jdb.set_days('key', "2000-01-01")
                    >>> jdb.set_days('key', "2000-01-01 2001-12-31")

                - date | datetime 

                    >>> jdb.set_days('key', date(2000, 1, 1))
                    >>> jdb.set_days('key', datetime(2000, 1, 1))

                - float : timestamp

        Returns:
            bool: True if add edge successfully, Otherwise return False.
        """
        if u == v:
            raise KeyError('u cannot be v')

        if not u or not v or u.find(':') >= 0 or v.find(':') >= 0:
            raise KeyError('invalid u or v')

        edge_key = self._generate_edge_key(u, v, directed)
        with self.open() as fp:
            self.f_add_edge(fp, u, v, directed, relation="temporary_access")
            return self.f_change_days(fp, edge_key, expire_days)

        return False

    def get_edge(self, u:str, v:str, directed:bool=True) -> Dict[str,Any]:
        """Get the properties of an edge.
 
        Args:
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): Edge direction flag matching how the
                edge was created. Defaults to True.
 
        Returns:
            Dict[str, Any]: Edge properties, or None if the edge does not exist.
        """
        with self.open() as fp:
            return self.f_get_edge(fp, u, v, directed)

    def remove_edge(self, u:str, v:str, directed:bool=True) -> Dict[str,Any]:
        """Remove an edge between two nodes.
 
        Args:
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): Edge direction flag matching how the
                edge was created. Defaults to True.
 
        Returns:
            Dict[str, Any]: Mapping of the deleted edge key to its stored
                properties, or an empty dict if the edge does not exist.
        """
        with self.open() as fp:
            return self.f_remove_edge(fp, u, v, directed)

    def find_edges(self, condition:Union[Dict[str,Any],Condition], date:Optional[Any]=None, limit:int=0, skip:int=0, **kwargs) -> Dict[Tuple[str,str,str], Any]:
        """Find edges whose properties match a query condition.
 
        Args:
            condition (Union[Dict[str, Any], Condition]): Query condition or
                property-equality dict passed through to ``find_iter``.
            date (Optional[Any], optional): Temporal filter forwarded to ``find_iter``.
            limit (int, optional): Maximum number of results. 0 means no limit.
            skip (int, optional): Number of matches to skip.
            **kwargs: Extra arguments forwarded to ``find_iter``.
 
        Returns:
            Dict[Tuple[str,str,str], Any]: Mapping of ``(src,edge_type,dst)`` to edges properties for every match.
        """
        ret = {}
        edge_re = self.EDGE_RE
        edge_match = edge_re.match
        for key,val in self.find_iter(edge_re, vals=condition, date=date, limit=limit, skip=skip, with_value=True, **kwargs):
            matched = edge_match(key)
            ret[matched.groups()] = val

        return ret

    def iter_edges(self) -> Generator[Tuple[Tuple[str,str,str],int],None,None]:
        """Iterate over all edges in the graph.
 
        Yields:
            (str,str,str), int: ``(src_id, edge_type, dst_id), row_id`` for
                each edge, where ``edge_type`` is ``'>'`` (directed) or
                ``'-'`` (undirected).
        """
        with self.open() as fp: # pylint: disable=W0135
            yield from self.f_iter_edges(fp)

    def iter_adjs(self) ->  Generator[Tuple[str,Tuple[int,List[str]]],None,None]:
        """Iterate over all adjacencies in the graph.
 
        Yields:
            str, (int, [str]): ``adj_id, (row_id, adj)`` where ``adj``
                is the list of direction-prefixed neighbor ids for that node.
        """
        with self.open() as fp: # pylint: disable=W0135
            yield from self.f_iter_adjs(fp)

    def get_neighbors(self, node_id: str) -> Set[str]:
        """Get all neighbors of a node, ignoring edge direction.

        Args:
            node_id (str): Node identifier.

        Returns:
            Set[str]: Identifiers of every node connected to ``node_id`` by
                any edge (directed or undirected, either endpoint).
        """
        neighbors = set()
        with self.open() as fp:
            for neighbor, _key, _row_id in self.f_iter_neighbors(fp, node_id):
                neighbors.add(neighbor)

        return neighbors

    def get_successors(self, node_id:str) -> Dict[str,Dict[str,Any]]:
        """Get nodes reachable from a node in one hop, with edge properties.

        Follows outgoing directed edges and undirected edges from ``node_id``.

        Args:
            node_id (str): Node identifier.

        Returns:
            Dict[str, Dict[str, Any]]: Mapping of successor node id to the
                properties of the connecting edge.
        """
        successors = {}
        with self.open() as fp:
            f_read = self.f_read
            for successor, edge_key, _row_id in self.f_iter_successors(fp, node_id):
                successors[successor] = f_read(fp, edge_key, copy=False)

        return successors

    def get_predecessors(self, node_id:str) -> Dict[str,Dict[str,Any]]:
        """Get nodes that can reach a node in one hop, with edge properties.

        Follows incoming directed edges and undirected edges of ``node_id``.

        Args:
            node_id (str): Node identifier.

        Returns:
            Dict[str, Dict[str, Any]]: Mapping of predecessor node id to the
                properties of the connecting edge.
        """
        predecessors = {}
        with self.open() as fp:
            f_read = self.f_read
            for predecessor, edge_key, _row_id in self.f_iter_predecessors(fp, node_id):
                predecessors[predecessor] = f_read(fp, edge_key, copy=False)

        return predecessors

    def degree(self, node_id:str) -> Dict[str,int]:
        """Count the edges incident to a node, grouped by direction.

        Counts the node's adjacency index range, so the cost is proportional
        to the node's degree rather than the total edge count.

        Args:
            node_id (str): Node identifier.

        Returns:
            Dict[str, int]: Counters with keys ``'in'`` (incoming directed),
                ``'out'`` (outgoing directed), ``'undirected'``, and
                ``'total'`` (sum of the three).
        """
        i_deg = o_deg = u_deg = 0
        with self.open() as fp:
            for (src,edge_type,dst),_row_id in self.f_iter_edges(fp):
                if edge_type == '>':
                    if dst == node_id:
                        i_deg += 1
                    elif src == node_id:
                        o_deg += 1
                elif dst == node_id or src == node_id:
                    u_deg += 1

        return {
            'in': i_deg,
            'out': o_deg,
            'undirected': u_deg,
            'total': i_deg + o_deg + u_deg,
        }

    def boost_edge_weights(self, relation_type:str, boost_value:float):
        """Increase the ``weight`` property of all edges with a given relation.

        Edges without a ``weight`` property are treated as having weight 1
        before the boost is applied.

        Args:
            relation_type (str): Value of the edge ``relation`` property to match.
            boost_value (float): Amount added to each matching edge's weight.
        """
        Edge = Query()
        self.update_if(Edge._id.matches(self.EDGE_RE) & (Edge.relation == relation_type), \
                patch=lambda edge,props: {'weight' : props.get('weight', 1) + boost_value})

    def bfs_shortest_path(self, start:str, end:str) -> List[str]:
        """Find a shortest path (fewest hops) between two nodes using BFS.
 
        Directed edges are followed forward only; undirected edges are
        traversed in both directions.
 
        Args:
            start (str): Start node identifier.
            end (str): End node identifier.

        Returns:
            List[str]: Node ids along a shortest path from ``start`` to
                ``end`` inclusive, or an empty list if either node is missing
                or no path exists.
        """
        with self.open() as fp:
            if not self.f_has_node(fp, start) or not self.f_has_node(fp, end):
                return []

            previous_nodes = {start: None}
            queue = deque([start])
            visited = {start}
            f_get_adj = self.f_get_adj
            while queue:
                current_node = queue.popleft()
                if current_node == end:
                    path = []
                    while current_node is not None:
                        path.append(current_node)
                        current_node = previous_nodes[current_node]
                    return path[::-1]

                for entry in f_get_adj(fp, current_node):
                    direction, neighbor = entry[0], entry[1:]
                    if direction == '<': continue
                    if neighbor not in visited:
                        visited.add(neighbor)
                        previous_nodes[neighbor] = current_node
                        queue.append(neighbor)
        return []

    def dijkstra_shortest_path(self, start:str, end:str, weight_key:str="weight") -> Tuple[float,List[str]]:
        """Find the minimum-weight path between two nodes using Dijkstra.
 
        Edge weights are read from each edge's ``weight_key`` property and
        default to 1 when missing. Weights must be non-negative for the
        result to be correct (a Dijkstra precondition).
 
        Directed edges are followed forward only; undirected edges are
        traversed in both directions.
 
        Args:
            start (str): Start node identifier.
            end (str): End node identifier.
            weight_key (str, optional): Edge property holding the weight.
                Defaults to ``"weight"``.
 
        Returns:
            Tuple[float, List[str]]: Total path weight and the node ids along
                the path. Returns ``(float('inf'), [])`` if either node is
                missing or no path exists.
        """
        with self.open() as fp:
            if not self.f_has_node(fp, start) or not self.f_has_node(fp, end):
                return float('inf'), []

            f_read = self.f_read
            f_get_adj = self.f_get_adj
            _generate_edge_key = self._generate_edge_key

            distances = {start: 0}
            previous_nodes = {start: None}
            queue = [(0, start)]
            while queue:
                current_dist, current_node = heappop(queue)
                if current_node == end:
                    path = []
                    while current_node is not None:
                        path.append(current_node)
                        current_node = previous_nodes[current_node]
                    return current_dist, path[::-1]

                if current_dist > distances.get(current_node, float('inf')):
                    continue

                for entry in f_get_adj(fp, current_node):
                    direction, neighbor = entry[0], entry[1:]
                    if direction == '<': continue
                    edge_key = _generate_edge_key(current_node, neighbor, direction == '>')
                    edge_props = f_read(fp, edge_key, copy=False)
                    weight = edge_props.get(weight_key, 1) if isinstance(edge_props, dict) else 1
                    distance = current_dist + weight
                    if distance < distances.get(neighbor, float('inf')):
                        distances[neighbor] = distance
                        previous_nodes[neighbor] = current_node
                        heappush(queue, (distance, neighbor))

        return float('inf'), []

    def dfs_traverse(self, start:str, visited:Optional[Set[str]]=None) -> list:
        """Depth-first traversal from a start node, following edge direction.
 
        Directed edges are followed forward only; undirected edges are
        followed in both directions.
 
        Args:
            start (str): Start node identifier.
            visited (Optional[Set[str]], optional): Pre-populated visited set,
                allowing traversal state to be shared across calls. Mutated
                in place. Defaults to a new empty set.
 
        Returns:
            list: Node ids in DFS pre-order starting from ``start``.
        """
        f_get_adj = self.f_get_adj
        def dfs(fp, key_table, node_id, visited, level=0) -> list:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            path = []
            if node_id not in visited:
                visited.add(node_id)
                path.append(node_id)
                for entry in f_get_adj(fp, node_id):
                    direction, successor = entry[0], entry[1:]
                    if direction == '<': continue
                    path.extend(dfs(fp, key_table, successor, visited, level+1))

            return path

        if visited is None: visited = set()
        with self.open() as fp:
            key_table = self.io.key_table
            if self.f_has_node(fp, start):
                return dfs(fp, key_table, start, visited)

        return []

    def is_cyclic(self) -> bool:
        """Detect whether the graph contains a cycle.
 
        Uses DFS with a recursion stack. Directed edges are followed forward
        only; undirected edges are followed in both directions.
 
        Note:
            Implemented recursively; very deep graphs may hit Python's
            recursion limit.
 
        Returns:
            bool: True if any cycle is reachable, otherwise False.
        """
        f_get_adj = self.f_get_adj
        _generate_edge_key = self._generate_edge_key

        def dfs(fp, key_table, node_id, visited, stack, parent_key=None, level=0) -> bool:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            stack.add(node_id)
            is_fully_explored = True
            for entry in f_get_adj(fp, node_id):
                direction, successor = entry[0], entry[1:]
                if direction == '<': continue
                edge_key = _generate_edge_key(node_id, successor, direction == '>')
                if edge_key == parent_key:
                    # same edge we arrived through: not a cycle back over itself
                    is_fully_explored = False
                    continue

                if successor in stack:
                    return True

                if successor not in visited:
                    if dfs(fp, key_table, successor, visited, stack, edge_key, level+1):
                        return True

            stack.remove(node_id)
            if is_fully_explored:
                visited.add(node_id)
            return False

        visited = set()
        stack = set()
        with self.open() as fp:
            key_table = self.io.key_table
            for node_id, _row_id in self.f_iter_nodes(fp):
                if node_id not in visited:
                    if dfs(fp, key_table, node_id, visited, stack):
                        return True

        return False

    def topological_sort(self) -> List[str]:
        """Topologically sort the graph in a single DFS pass.
 
        Cycle detection is folded into the same traversal (via a recursion
        stack), so the graph is only scanned once. Nodes are pushed in
        post-order and the reversed stack is returned.
 
        Note:
            Implemented recursively; very deep graphs may hit Python's
            recursion limit.
 
        Returns:
            List[str]: Node ids in a valid topological order.
 
        Raises:
            ValueError: If the graph contains a cycle (not a DAG).
        """
        f_get_adj = self.f_get_adj
        _generate_edge_key = self._generate_edge_key

        def dfs(fp, key_table, node_id, visited, rec_stack, stack, parent_key=None, level=0) -> bool:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            visited.add(node_id)
            rec_stack.add(node_id)
            for entry in f_get_adj(fp, node_id):
                direction, successor = entry[0], entry[1:]
                if direction == '<': continue
                edge_key = _generate_edge_key(node_id, successor, direction == '>')
                if not (direction == '-' and edge_key == parent_key):
                    if successor not in visited:
                        if dfs(fp, key_table, successor, visited, rec_stack, stack, edge_key, level+1):
                            return True

                    elif successor in rec_stack:
                        return True

            rec_stack.remove(node_id)
            stack.append(node_id)
            return False

        visited = set()
        rec_stack = set()
        stack = []
        with self.open() as fp:
            key_table = self.io.key_table
            for node_id, _row_id in self.f_iter_nodes(fp):
                if node_id not in visited:
                    if dfs(fp, key_table, node_id, visited, rec_stack, stack):
                        raise ValueError("Must be a Directed Acyclic Graph.")

        return stack[::-1]

    def connected_components(self) -> list:
        """Find the weakly connected components of the graph.
 
        Edge direction is intentionally ignored (weak connectivity): two
        nodes belong to the same component if any chain of edges links them.
 
        Returns:
            list: A list of components, each a list of node ids discovered
                by BFS. Isolated nodes form single-element components.
        """
        visited = set()
        components = []
        with self.open() as fp:
            f_get_adj = self.f_get_adj
            for node_id, _row_id in self.f_iter_nodes(fp):
                if node_id not in visited:
                    component = []
                    queue = deque([node_id])
                    visited.add(node_id)
                    while queue:
                        current_node = queue.popleft()
                        component.append(current_node)
                        for entry in f_get_adj(fp, current_node):
                            _direction, neighbor = entry[0], entry[1:]
                            if neighbor not in visited:
                                visited.add(neighbor)
                                queue.append(neighbor)

                    components.append(component)
        return components

    def f_iter_edges(self, fp:Dict[int,IO]) -> Generator[Tuple[Tuple[str,str,str],int],None,None]:
        """Iterate over all edges from the key table.
 
        Low-level helper; must be called inside an ``open()`` context.
 
        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
 
        Yields:
            (str,str,str), int: ``(src_id, edge_type, dst_id), row_id`` for
                each edge.
        """
        edge_match = self.EDGE_RE.match
        io, fp, _key_fp = self.f_get_fp(fp)
        for key,row_id in io.key_table.items():
            matched = edge_match(key)
            if matched:
                src, edge_type, dst = matched.groups()
                yield (src, edge_type, dst), row_id

    def f_iter_nodes(self, fp:Dict[int,IO]) -> Generator[Tuple[str,int],None,None]:
        """Iterate over all nodes from the key table.
 
        Low-level helper; must be called inside an ``open()`` context.
 
        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
 
        Yields:
            str, int: ``node_id, row_id`` for each node.
        """
        node_match = self.NODE_RE.match
        io, fp, _key_fp = self.f_get_fp(fp)
        for key,row_id in io.key_table.items():
            matched = node_match(key)
            if matched:
                node_id, = matched.groups()
                yield node_id, row_id

    def f_iter_adjs(self, fp:Dict[int,IO]) -> Generator[Tuple[str,Tuple[int,List[str]]],None,None]:
        """Iterate over all adjacencies (persisted per-node adjacency lists).
 
        Each node with at least one edge has a adjacency stored under
        ``X:{node_id}:`` whose value is a list of direction-prefixed neighbor
        ids: ``'>v'`` (outgoing directed edge to ``v``), ``'<u'`` (incoming
        directed edge from ``u``), or ``'-x'`` (undirected edge with ``x``).
        Iterating adjacencies lets graph algorithms build an adjacency map in
        a single pass without scanning every edge key.
 
        Low-level helper; must be called inside an ``open()`` context.
 
        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
 
        Yields:
            str, (int, [str]): ``adj_id, (row_id, adj)`` where ``adj``
                is the list of direction-prefixed neighbor ids for that node.
        """
        adj_match = self.ADJ_RE.match
        f_read_row = self.f_read_row
        for key,row_id in self.io.key_table.items():
            matched = adj_match(key)
            if matched:
                adj_id, = matched.groups()
                adj = f_read_row(fp, row_id, with_value=True)[-1] or []
                yield adj_id, (row_id, adj)

    def f_iter_neighbors(self, fp:Dict[int,IO], node_id:str) -> Generator[Tuple[str,str,int],None,None]:
        """Iterate over all edges incident to a node, ignoring direction.

        Reads the node's persisted adjacency (``X:{node_id}:``) so the work is
        proportional to the node's degree rather than the total edge count.
        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Yields:
            (str, str, int): ``(neighbor_id, edge_key, row_id)`` for each
                edge touching ``node_id``.
        """
        key_table = self.io.key_table
        _generate_edge_key = self._generate_edge_key
        for entry in self.f_get_adj(fp, node_id):
            direction, neighbor = entry[0], entry[1:]
            edge_key = _generate_edge_key(neighbor, node_id, True) if direction == '<' else \
                        _generate_edge_key(node_id, neighbor, direction == '>')

            yield neighbor, edge_key, key_table.get(edge_key, -1)

    def f_iter_successors(self, fp:Dict[int,IO], node_id:str) -> Generator[Tuple[str,str,int],None,None]:
        """Iterate over one-hop successors of a node, respecting direction.

        Follows outgoing directed edges (adjacency ``'>'``) and undirected
        edges (adjacency ``'-'``); incoming directed edges (``'<'``) are
        skipped. Reads the node's persisted adjacency so the work is
        proportional to the node's degree. Low-level helper; must be called
        inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Yields:
            (str, str, int): ``(successor_id, edge_key, row_id)`` for
                each qualifying edge.
        """
        key_table = self.io.key_table
        _generate_edge_key = self._generate_edge_key
        for entry in self.f_get_adj(fp, node_id):
            direction, successor = entry[0], entry[1:]
            if direction != '<':
                edge_key = _generate_edge_key(node_id, successor, direction == '>')
                yield successor, edge_key, key_table.get(edge_key, -1)

    def f_iter_predecessors(self, fp:Dict[int,IO], node_id:str) -> Generator[Tuple[str,str,int],None,None]:
        """Iterate over one-hop predecessors of a node, respecting direction.

        Follows incoming directed edges (adjacency ``'<'``) and undirected
        edges (adjacency ``'-'``); outgoing directed edges (``'>'``) are
        skipped. Reads the node's persisted adjacency so the work is
        proportional to the node's degree. Low-level helper; must be called
        inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Yields:
            (str, str, int): ``(predecessor_id, edge_key, row_id)`` for
                each qualifying edge.
        """
        key_table = self.io.key_table
        _generate_edge_key = self._generate_edge_key
        for entry in self.f_get_adj(fp, node_id):
            direction, predecessor = entry[0], entry[1:]
            if direction != '>':
                edge_key = _generate_edge_key(predecessor, node_id, True) if direction == '<' else \
                            _generate_edge_key(node_id, predecessor, False)

                yield predecessor, edge_key, key_table.get(edge_key, -1)

    def f_has_node(self, _fp:Dict[int,IO], node_id:str) -> bool:
        """Check whether a node exists.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            _fp (Dict[int, IO]): File-pointer dict from ``open()`` (unused).
            node_id (str): Node identifier.

        Returns:
            bool: True if the node exists, otherwise False.
        """
        node_key = f'N:{node_id}:'
        return node_key in self.io.key_table

    def f_get_node(self, fp:Dict[int,IO], node_id:str) -> Dict[str,Any]:
        """Get the properties of a node.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Returns:
            Dict[str, Any]: Node properties, or None if the node does not exist.
        """
        node_key = f'N:{node_id}:'
        return self.f_read(fp, node_key, default_val=None)

    def f_add_node(self, fp:Dict[int,IO], node_id:str, **properties) -> bool:
        """Add a node, or merge new properties into an existing node.

        If the node already exists, ``properties`` are merged over the stored
        properties (shallow update); nothing is written when the merge does
        not change anything. Low-level helper; must be called inside an
        ``open()`` context. Callers are responsible for validating ``node_id``.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Unique node identifier.
            **properties: Arbitrary node properties to store.

        Returns:
            bool: True if a write occurred, False if nothing changed.
        """
        node_key = f'N:{node_id}:'
        if node_key not in self.io.key_table:
            return self.f_write(fp, node_key, properties)

        old_props = self.f_read(fp, node_key, copy=False)
        if isinstance(old_props, dict):
            new_props = {**old_props, **properties}
            if new_props != old_props:
                return self.f_write(fp, node_key, new_props)
            else:
                return False

        return self.f_write(fp, node_key, properties)

    def f_remove_node(self, fp:Dict[int,IO], node_id:str) -> Dict[str,Any]:
        """Remove a node together with all edges connected to it.

        Reads the node's adjacency (``X:{node_id}:``) to find every incident
        edge, then deletes each edge record, this node's adjacency, the node
        itself, and cleans the mirror entry on each neighbour's adjacency.
        A neighbour linked by both a directed and an undirected edge has each
        edge collected separately. Low-level helper; must be called inside an
        ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Returns:
            Dict[str, Any]: Mapping of every deleted key to its stored value.
                Empty if the node does not exist.
        """
        node_key = f'N:{node_id}:'
        ret = {}
        matched_keys = set()
        io, fp, _key_fp = self.f_get_fp(fp)
        key_table = io.key_table
        row_id = key_table.get(node_key, -1)
        if row_id >= 0:
            matched_keys.add((node_key, row_id))

        adj_key = f'X:{node_id}:'
        row_id = key_table.get(adj_key, -1)
        if row_id >= 0:
            matched_keys.add((adj_key, row_id))
            _generate_edge_key = self._generate_edge_key
            f_read = self.f_read
            f_write = self.f_write
            cleaned_adjs = set()
            for adj_id in self.f_get_adj(fp, node_id):
                neighbor = adj_id[1:]
                edge_type = adj_id[0]
                # every adjacency entry maps to a distinct incident edge:
                # a neighbor may be linked by both a directed and an
                # undirected edge, so collect each edge separately.
                edge_key = _generate_edge_key(neighbor, node_id, True) if edge_type == '<' else \
                            _generate_edge_key(node_id, neighbor, edge_type == '>')
                edge_row = key_table.get(edge_key, -1)
                if edge_row >= 0:
                    matched_keys.add((edge_key, edge_row))

                # clean the neighbor once (drops every entry
                # that points back at node_id, directed or undirected)
                adj_key = f'X:{neighbor}:'
                adj_row = key_table.get(adj_key, -1)
                if adj_row >= 0 \
                        and adj_key not in cleaned_adjs \
                        and (adj_key, adj_row) not in matched_keys:
                    cleaned_adjs.add(adj_key)
                    new_adj = []
                    old_adj = f_read(fp, adj_key, copy=False)
                    if old_adj:
                        for _adj_id in old_adj:
                            if _adj_id[1:] != node_id:
                                new_adj.append(_adj_id)

                    if not new_adj:
                        matched_keys.add((adj_key, adj_row))

                    elif new_adj != old_adj:
                        f_write(fp, adj_key, new_adj, overwrite=True, max_wsize=0)

        if matched_keys:
            io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
            f_delete = self.f_delete
            matched_list = sorted(matched_keys, key=lambda vv: -vv[1])
            for key,row_id in matched_list:
                val = f_delete(fp, key, row=row_id)
                ret[key] = val

        return ret

    def f_has_edge(self, _fp:Dict[int,IO], u:str, v:str, directed:bool=True) -> bool:
        """Check whether an edge exists.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            _fp (Dict[int, IO]): File-pointer dict from ``open()`` (unused).
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): Edge direction flag matching how the
                edge was created. Defaults to True.

        Returns:
            bool: True if the edge exists, otherwise False.
        """
        edge_key = self._generate_edge_key(u, v, directed)
        return edge_key in self.io.key_table

    def f_get_edge(self, fp:Dict[int,IO], u:str, v:str, directed:bool=True) -> Dict[str,Any]:
        """Get the properties of an edge.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): Edge direction flag matching how the
                edge was created. Defaults to True.

        Returns:
            Dict[str, Any]: Edge properties, or None if the edge does not exist.
        """
        edge_key = self._generate_edge_key(u, v, directed)
        return self.f_read(fp, edge_key, default_val=None)

    def f_add_edge(self, fp:Dict[int,IO], u:str, v:str, directed:bool=True, **properties) -> bool:
        """Add an edge, creating missing endpoint nodes and adjacency entries.

        Writes the edge record plus the two adjacency entries (one on each
        endpoint) when the edge is new. If the edge already exists,
        ``properties`` are merged over the stored properties and nothing is
        written when the merge does not change anything. Low-level helper;
        must be called inside an ``open()`` context. Callers are responsible
        for validating ``u``/``v`` and rejecting self-loops.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): True for a directed edge ``u -> v``,
                False for an undirected edge. Defaults to True.
            **properties: Edge properties to store.
 
        Returns:
            bool: True if a write occurred, False if nothing changed.
        """
        edge_key = self._generate_edge_key(u, v, directed)
        key_table = self.io.key_table
        if edge_key not in key_table:
            _io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
            u_key = f'N:{u}:'
            if u_key not in key_table:
                self.f_write(fp, u_key, {}, overwrite=True, max_wsize=0)

            v_key = f'N:{v}:'
            if v_key not in key_table:
                self.f_write(fp, v_key, {}, overwrite=True, max_wsize=0)

            xu_key = f'X:{u}:'
            xu_val = f'>{v}' if directed else f'-{v}'
            adj = self.f_read(fp, xu_key, copy=False) if xu_key in key_table else []
            if xu_val not in adj:
                adj.append(xu_val)
                self.f_write(fp, xu_key, adj, overwrite=True, max_wsize=0)

            xv_key = f'X:{v}:'
            xv_val = f'<{u}' if directed else f'-{u}'
            adj = self.f_read(fp, xv_key, copy=False) if xv_key in key_table else []
            if xv_val not in adj:
                adj.append(xv_val)
                self.f_write(fp, xv_key, adj, overwrite=True, max_wsize=0)

            return self.f_write(fp, edge_key, properties)

        old_props = self.f_read(fp, edge_key, copy=False)
        if not isinstance(old_props, dict): # pragma: no cover
            return self.f_write(fp, edge_key, properties)

        new_props = {**old_props, **properties}
        return self.f_write(fp, edge_key, new_props) if new_props != old_props else False

    def f_remove_edge(self, fp:Dict[int,IO], u:str, v:str, directed:bool=True) -> Dict[str,Any]:
        """Remove an edge and clean both endpoints' adjacency entries.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool, optional): Edge direction flag matching how the
                edge was created. Defaults to True.

        Returns:
            Dict[str, Any]: Mapping of the deleted edge key to its stored
                properties, or an empty dict if the edge does not exist.
        """
        edge_key = self._generate_edge_key(u, v, directed)
        ret = {}
        key_table = self.io.key_table
        if edge_key in key_table:
            _io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
            props = self.f_delete(fp, edge_key)
            ret[edge_key] = props

            xu_key = f'X:{u}:'
            xu_val = f'>{v}' if directed else f'-{v}'
            adj = self.f_read(fp, xu_key, copy=False) if xu_key in key_table else []
            if xu_val in adj:
                adj.remove(xu_val)
                self.f_write(fp, xu_key, adj, overwrite=True, max_wsize=0)

            xv_key = f'X:{v}:'
            xv_val = f'<{u}' if directed else f'-{u}'
            adj = self.f_read(fp, xv_key, copy=False) if xv_key in key_table else []
            if xv_val in adj:
                adj.remove(xv_val)
                self.f_write(fp, xv_key, adj, overwrite=True, max_wsize=0)

        return ret

    def f_get_adj(self, fp:Dict[int,IO], node_id:str) -> List[str]:
        """Read a node's persisted adjacency list.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Returns:
            List[str]: Direction-prefixed neighbor ids (``'>v'`` outgoing
                directed, ``'<u'`` incoming directed, ``'-x'`` undirected),
                or an empty list if the node has no adjacency entry.
        """
        adj_key = f'X:{node_id}:'
        return self.f_read(fp, adj_key, default_val=[], copy=False)

    def _generate_edge_key(self, u:str, v:str, directed:bool) -> str:
        """Build the canonical storage key for an edge.

        For undirected edges the endpoints are sorted lexicographically so
        that ``(u, v)`` and ``(v, u)`` map to the same key.

        Args:
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool): True for ``E:u:>:v:``, False for ``E:min:-:max:``.

        Returns:
            str: The edge key.
        """
        if directed:
            return f'E:{u}:>:{v}:'
        u, v = (v, u) if u > v else (u, v)
        return f'E:{u}:-:{v}:'

#
