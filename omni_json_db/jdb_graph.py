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
from .utils import JKeyError

MAX_RECURSION = 500

class GraphDb(JDb):
    """Graph database layer built on top of the JDb key-value store.

    Nodes are stored under keys of the form ``N:{node_id}:`` with a dict of
    properties as the value. Edges are stored under ``E:{u}:>:{v}:`` for
    directed edges and ``E:{u}:-:{v}:`` for undirected edges (endpoints
    sorted lexicographically), also with a dict of properties as the value.
    Edge records are the single source of truth; each node additionally has
    a derived adjacency blob under ``X:{node_id}:`` (a list of
    direction-prefixed neighbor ids) that traversals read on demand instead
    of scanning every edge. ``verify_index()``/``reindex()`` detect and
    repair drift between the two if an edge key is ever created or deleted
    outside ``add_edge``/``remove_edge``.

    Provides node/edge CRUD, neighborhood queries (including k-hop and ego
    subgraphs), direction- and property-filtered traversal, classic graph
    algorithms (BFS/Dijkstra shortest path, all shortest paths, DFS
    traversal, cycle detection, topological sort, weakly/strongly connected
    components), and centrality measures (degree, PageRank, betweenness)
    executed directly over the underlying key table.
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
        """Initialize the GraphDb controller over a JDb key-value store.

        Args:
            KEY_file (Union[str, bytearray, JFilesBase, JDbReader, None], optional): File path, memory buffer, or network host.
            data_type (Union[str, int, None], optional): Serialization format.
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

        Raises:
            KeyError: If ``node_id`` is empty or contains ``':'``.
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
        for key, val in self.find_iter(node_re, vals=condition, date=date, limit=limit, skip=skip, with_value=True, with_date=False, **kwargs):
            matched = node_match(key)
            ret[matched.groups()[0]] = val
        return ret

    def nodes(self) -> Generator[Tuple[str,int],None,None]:
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
            KeyError: If ``u`` equals ``v`` (self-loops are not allowed), or if
                either id is empty or contains ``':'``.
        """
        if u == v:
            raise KeyError('u cannot be v')

        if not u or not v or u.find(':') >= 0 or v.find(':') >= 0:
            raise KeyError('invalid u or v')

        with self.open() as fp:
            return self.f_add_edge(fp, u, v, directed, **properties)

    def add_temporal_edge(self, u:str, v:str, directed:bool, expire_days:Union[int,float,str,dt_date,datetime]):
        """Add a temporal edge that expires after the given number of days.

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
            bool: True if the edge was added or its expiry updated, False otherwise.

        Raises:
            KeyError: If ``u`` equals ``v`` (self-loops are not allowed), or if
                either id is empty or contains ``':'``.
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

    def add_nodes_from(self, nodes:Any) -> int:
        """Add multiple nodes in a single transaction.

        Writes directly via ``f_add_node`` inside one write transaction
        (a single ``open()``/lock acquisition for the whole batch), rather
        than one ``open()`` per node through ``add_node`` in a loop. Still
        applies the same id validation as ``add_node`` (enforced by
        ``f_add_node``).

        Args:
            nodes (Any): Iterable of items, each either a plain node id, or a
                ``(node_id, properties_dict)`` 2-tuple. A ``dict`` of
                ``{node_id: properties_dict}`` is also accepted (its
                ``.items()`` are used).

        Returns:
            int: Count of nodes that resulted in a write (new node, or an
                existing node whose properties changed).

        Raises:
            KeyError: If any node id is empty or contains ``':'``.
        """
        n = 0
        items = nodes.items() if isinstance(nodes, dict) else nodes
        with self.open(read_only=False) as fp:
            f_add_node = self.f_add_node
            for item in items:
                if isinstance(item, tuple) and len(item) == 2 and isinstance(item[1], dict):
                    node_id, props = item
                else:
                    node_id, props = item, {}
                if f_add_node(fp, node_id, **props):
                    n += 1

        return n

    def add_edges_from(self, edges:Any) -> int:
        """Add multiple edges in a single transaction.

        Writes directly via ``f_add_edge`` inside one write transaction
        (a single ``open()``/lock acquisition for the whole batch), rather
        than one ``open()`` per edge through ``add_edge`` in a loop. Still
        applies the same id/self-loop validation as ``add_edge`` (enforced
        by ``f_add_edge``).

        Args:
            edges (Any): Iterable of ``(u, v)``, ``(u, v, directed)``, or
                ``(u, v, directed, properties_dict)`` tuples. ``directed``
                defaults to True and ``properties_dict`` defaults to empty
                when omitted.

        Returns:
            int: Count of edges that resulted in a write (new edge, or an
                existing edge whose properties changed).

        Raises:
            KeyError: If any edge is a self-loop (``u == v``), or if either
                id is empty or contains ``':'``.
        """
        n = 0
        with self.open(read_only=False) as fp:
            f_add_edge = self.f_add_edge
            for spec in edges:
                u, v = spec[0], spec[1]
                directed = spec[2] if len(spec) > 2 else True
                props = spec[3] if len(spec) > 3 else {}
                if f_add_edge(fp, u, v, directed, **props):
                    n += 1

        return n

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
        for key,val in self.find_iter(edge_re, vals=condition, date=date, limit=limit, skip=skip, with_value=True, with_date=False, **kwargs):
            matched = edge_match(key)
            ret[matched.groups()] = val

        return ret

    def edges(self) -> Generator[Tuple[Tuple[str,str,str],int],None,None]:
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

    def neighbors(self, node_id: str) -> Set[str]:
        """Get all neighbors of a node, ignoring edge direction.

        Reads the node's adjacency directly via ``f_get_adj`` (only the
        neighbor ids are needed here, so no edge-key reconstruction happens).

        Args:
            node_id (str): Node identifier.

        Returns:
            Set[str]: Identifiers of every node connected to ``node_id`` by
                any edge (directed or undirected, either endpoint).
        """
        with self.open() as fp:
            neighbors = {entry[1:] for entry in self.f_get_adj(fp, node_id)}

        return neighbors

    def common_neighbors(self, u:str, v:str) -> Set[str]:
        """Find nodes that are neighbors of both ``u`` and ``v``.

        Uses the same direction-agnostic notion of "neighbor" as
        ``neighbors`` (any edge, directed or undirected, either
        endpoint). Reads each node's adjacency directly via ``f_get_adj``, so
        the cost is proportional to ``degree(u) + degree(v)`` rather than the
        total node/edge count.

        Args:
            u (str): First node identifier.
            v (str): Second node identifier.

        Returns:
            Set[str]: Node ids adjacent to both ``u`` and ``v``. Empty if
                either node is missing or they share no neighbors.
        """
        with self.open() as fp:
            f_get_adj = self.f_get_adj
            neighbors_u = {entry[1:] for entry in f_get_adj(fp, u)}
            neighbors_v = {entry[1:] for entry in f_get_adj(fp, v)}

        return neighbors_u & neighbors_v

    def jaccard_coefficient(self, u:str, v:str) -> float:
        """Compute the Jaccard similarity between two nodes' neighbor sets.

        Defined as ``|common neighbors| / |union of neighbors|``, using the
        same direction-agnostic notion of "neighbor" as ``neighbors``.
        A value of 1.0 means ``u`` and ``v`` have identical neighbor sets; 0.0
        means they share none (including the case where both have no
        neighbors at all, by convention). Reads each node's adjacency
        directly via ``f_get_adj``, same as ``common_neighbors``.

        Args:
            u (str): First node identifier.
            v (str): Second node identifier.

        Returns:
            float: Jaccard similarity in ``[0, 1]``.
        """
        with self.open() as fp:
            f_get_adj = self.f_get_adj
            neighbors_u = {entry[1:] for entry in f_get_adj(fp, u)}
            neighbors_v = {entry[1:] for entry in f_get_adj(fp, v)}

        union = neighbors_u | neighbors_v
        if not union:
            return 0.0

        return len(neighbors_u & neighbors_v) / len(union)

    def successors(self, node_id:str) -> Dict[str,Dict[str,Any]]:
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

    def predecessors(self, node_id:str) -> Dict[str,Dict[str,Any]]:
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
            if self.f_has_node(fp, node_id):
                for entry in self.f_get_adj(fp, node_id):
                    d = entry[0]
                    if d == '<':
                        i_deg += 1
                    elif d == '>':
                        o_deg += 1
                    elif d == '-':
                        u_deg += 1

        return {'in': i_deg, 'out': o_deg, 'undirected': u_deg, 'total': i_deg + o_deg + u_deg}

    def weighted_degree(self, node_id:str, weight_key:str='weight', default:float=1.0) -> Dict[str,float]:
        """Sum edge weights incident to a node, grouped by direction.

        Like ``degree``, but sums a numeric edge property instead of just
        counting edges. Reads the node's adjacency plus one edge record per
        incident edge, so the cost is proportional to the node's degree
        rather than the total edge count.

        Args:
            node_id (str): Node identifier.
            weight_key (str, optional): Edge property to sum. Defaults to
                ``'weight'``.
            default (float, optional): Value used for edges missing
                ``weight_key``. Defaults to 1.0.

        Returns:
            Dict[str, float]: Sums with keys ``'in'`` (incoming directed),
                ``'out'`` (outgoing directed), ``'undirected'``, and
                ``'total'`` (sum of the three). All zero if the node is
                missing or has no incident edges.
        """
        i_wt = o_wt = u_wt = 0.0
        with self.open() as fp:
            if self.f_has_node(fp, node_id):
                f_read = self.f_read
                _generate_edge_key = self._generate_edge_key
                for entry in self.f_get_adj(fp, node_id):
                    d, other = entry[0], entry[1:]
                    if d == '>':
                        edge_key = _generate_edge_key(node_id, other, True)
                        o_wt += (f_read(fp, edge_key, copy=False) or {}).get(weight_key, default)
                    elif d == '<':
                        edge_key = _generate_edge_key(other, node_id, True)
                        i_wt += (f_read(fp, edge_key, copy=False) or {}).get(weight_key, default)
                    else:
                        edge_key = _generate_edge_key(node_id, other, False)
                        u_wt += (f_read(fp, edge_key, copy=False) or {}).get(weight_key, default)

        return {'in': i_wt, 'out': o_wt, 'undirected': u_wt, 'total': i_wt + o_wt + u_wt}

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

    def bfs_shortest_path(self, source:str, target:str, direction:str='out', edge_filter:Optional[Any]=None) -> List[str]:
        """Find a shortest path (fewest hops) between two nodes using BFS.

        By default directed edges are followed forward only and undirected
        edges are traversed in both directions.

        Args:
            source (str): Start node identifier.
            target (str): End node identifier.
            direction (str, optional): Edge direction to follow from each
                node — ``'out'`` (default) follows outgoing directed and
                undirected edges, ``'in'`` follows incoming directed and
                undirected edges, ``'both'`` follows every incident edge.
            edge_filter (Optional[Callable[[dict], bool]], optional): If
                given, only cross an edge when ``edge_filter(props)`` is
                truthy for that edge's properties. Defaults to None (no
                filtering).

        Returns:
            List[str]: Node ids along a shortest path from ``source`` to
                ``target`` inclusive, or an empty list if either node is missing
                or no path exists.
        """
        with self.open() as fp:
            if not self.f_has_node(fp, source) or not self.f_has_node(fp, target):
                return []

            previous_nodes = {source: None}
            queue = deque([source])
            visited = {source}
            f_get_adj = self.f_get_adj
            f_read = self.f_read
            _generate_edge_key = self._generate_edge_key
            while queue:
                current_node = queue.popleft()
                if current_node == target:
                    path = []
                    while current_node is not None:
                        path.append(current_node)
                        current_node = previous_nodes[current_node]
                    return path[::-1]

                for entry in f_get_adj(fp, current_node):
                    d, neighbor = entry[0], entry[1:]
                    if direction == 'out' and d == '<': continue
                    if direction == 'in' and d == '>': continue
                    if neighbor not in visited:
                        if edge_filter is not None:
                            edge_key = _generate_edge_key(neighbor, current_node, True) if d == '<' else \
                                        _generate_edge_key(current_node, neighbor, d == '>')
                            props = f_read(fp, edge_key, copy=False)
                            if not edge_filter(props if isinstance(props, dict) else {}):
                                continue

                        visited.add(neighbor)
                        previous_nodes[neighbor] = current_node
                        queue.append(neighbor)
        return []

    def dijkstra_shortest_path(self, source:str, target:str, weight_key:str="weight") -> Tuple[float,List[str]]:
        """Find the minimum-weight path between two nodes using Dijkstra.
 
        Edge weights are read from each edge's ``weight_key`` property and
        default to 1 when missing. Weights must be non-negative for the
        result to be correct (a Dijkstra precondition).
 
        Directed edges are followed forward only; undirected edges are
        traversed in both directions.
 
        Args:
            source (str): Start node identifier.
            target (str): End node identifier.
            weight_key (str, optional): Edge property holding the weight.
                Defaults to ``"weight"``.
 
        Returns:
            Tuple[float, List[str]]: Total path weight and the node ids along
                the path. Returns ``(float('inf'), [])`` if either node is
                missing or no path exists.
        """
        with self.open() as fp:
            if not self.f_has_node(fp, source) or not self.f_has_node(fp, target):
                return float('inf'), []

            f_read = self.f_read
            f_get_adj = self.f_get_adj
            _generate_edge_key = self._generate_edge_key

            distances = {source: 0}
            previous_nodes = {source: None}
            queue = [(0, source)]
            while queue:
                current_dist, current_node = heappop(queue)
                if current_node == target:
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

    def dfs_traverse(self, source:str, visited:Optional[Set[str]]=None, direction:str='out', edge_filter:Optional[Any]=None) -> list:
        """Depth-first traversal from a source node, following edge direction.

        By default directed edges are followed forward only and undirected
        edges are followed in both directions.

        Args:
            source (str): Start node identifier.
            visited (Optional[Set[str]], optional): Pre-populated visited set,
                allowing traversal state to be shared across calls. Mutated
                in place. Defaults to a new empty set.
            direction (str, optional): Edge direction to follow from each
                node — ``'out'`` (default) follows outgoing directed and
                undirected edges, ``'in'`` follows incoming directed and
                undirected edges, ``'both'`` follows every incident edge.
            edge_filter (Optional[Callable[[dict], bool]], optional): If
                given, only follow an edge when ``edge_filter(props)`` is
                truthy for that edge's properties. Defaults to None (no
                filtering).

        Returns:
            list: Node ids in DFS pre-order starting from ``source``.
        """
        f_get_adj = self.f_get_adj
        f_read = self.f_read
        _generate_edge_key = self._generate_edge_key
        def dfs(fp, node_id, visited, level=0) -> list:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            path = []
            if node_id not in visited:
                visited.add(node_id)
                path.append(node_id)
                for entry in f_get_adj(fp, node_id):
                    d, successor = entry[0], entry[1:]
                    if direction == 'out' and d == '<': continue
                    if direction == 'in' and d == '>': continue
                    if edge_filter is not None:
                        edge_key = _generate_edge_key(successor, node_id, True) if d == '<' else \
                                    _generate_edge_key(node_id, successor, d == '>')
                        props = f_read(fp, edge_key, copy=False)
                        if not edge_filter(props if isinstance(props, dict) else {}):
                            continue

                    path.extend(dfs(fp, successor, visited, level+1))

            return path

        if visited is None: visited = set()
        with self.open() as fp:
            if self.f_has_node(fp, source):
                return dfs(fp, source, visited)

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

    def k_hop_neighbors(self, node_id:str, k:int, direction:str='out') -> Dict[str,int]:
        """Find all nodes within ``k`` hops of a node (BFS with depth limit).

        Args:
            node_id (str): Center node identifier.
            k (int): Maximum number of hops (``k >= 1``).
            direction (str, optional): Edge direction to follow from each
                node — ``'out'`` (default) follows outgoing directed and
                undirected edges, ``'in'`` follows incoming directed and
                undirected edges, ``'both'`` follows every incident edge.

        Returns:
            Dict[str, int]: Mapping of reachable node id to its hop distance
                from ``node_id`` (1..k). Excludes ``node_id`` itself. Empty if
                the node is missing, ``k < 1``, or it has no qualifying
                neighbours.
        """
        result = {}
        with self.open() as fp:
            if not self.f_has_node(fp, node_id) or k < 1:
                return result

            f_get_adj = self.f_get_adj
            visited = {node_id}
            frontier = [node_id]
            for depth in range(1, k + 1):
                nxt = []
                for cur in frontier:
                    for entry in f_get_adj(fp, cur):
                        d, neighbor = entry[0], entry[1:]
                        if direction == 'out' and d == '<': continue
                        if direction == 'in' and d == '>': continue
                        if neighbor not in visited:
                            visited.add(neighbor)
                            result[neighbor] = depth
                            nxt.append(neighbor)
                if not nxt:
                    break
                frontier = nxt

        return result

    def ego_graph(self, node_id:str, k:int=1, direction:str='both') -> Dict[str,Any]:
        """Extract the ``k``-hop ego subgraph centered on a node.

        The subgraph contains ``node_id`` plus every node within ``k`` hops
        (using ``direction`` for reachability), and every edge of the graph
        whose endpoints are both inside that node set.

        Args:
            node_id (str): Center node identifier.
            k (int, optional): Neighbourhood radius in hops. Defaults to 1.
            direction (str, optional): Edge direction used to decide
                reachability of the node set — ``'out'``, ``'in'`` or
                ``'both'`` (default). See ``k_hop_neighbors``.

        Returns:
            Dict[str, Any]: ``{'nodes': {id: props}, 'edges': {(src, type,
                dst): props}}`` for the induced subgraph. Empty node/edge maps
                if ``node_id`` is missing.
        """
        result = {'nodes': {}, 'edges': {}}
        with self.open() as fp:
            if not self.f_has_node(fp, node_id):
                return result

            node_set = {node_id}
            if k >= 1:
                node_set.update(self.k_hop_neighbors(node_id, k, direction))

            f_get_node = self.f_get_node
            for nid in node_set:
                result['nodes'][nid] = f_get_node(fp, nid)

            # collect induced edges: for every node in the set, walk its
            # outgoing/undirected adjacency and keep edges whose other
            # endpoint is also in the set (each edge counted once)
            f_read = self.f_read
            f_get_adj = self.f_get_adj
            _generate_edge_key = self._generate_edge_key
            edge_re = self.EDGE_RE
            seen = set()
            for nid in node_set:
                for entry in f_get_adj(fp, nid):
                    d, other = entry[0], entry[1:]
                    if other in node_set:
                        edge_key = _generate_edge_key(nid, other, d == '>') if d != '<' else None
                        if edge_key is not None and edge_key not in seen:
                            seen.add(edge_key)
                            matched = edge_re.match(edge_key)
                            if matched:
                                result['edges'][matched.groups()] = f_read(fp, edge_key, copy=False)

        return result

    def subgraph(self, nodes:Any) -> Dict[str,Any]:
        """Extract the induced subgraph over an explicit set of nodes.

        Unlike ``ego_graph`` (which derives its node set from a BFS radius),
        the node set here is supplied directly by the caller. Node ids that
        do not exist in the graph are silently skipped.

        Args:
            nodes (Any): Iterable of node identifiers to include.

        Returns:
            Dict[str, Any]: ``{'nodes': {id: props}, 'edges': {(src, type,
                dst): props}}`` for the induced subgraph — every edge of the
                graph whose endpoints are both in ``nodes``. Empty node/edge
                maps if none of the given ids exist.
        """
        result = {'nodes': {}, 'edges': {}}
        with self.open() as fp:
            f_has_node = self.f_has_node
            node_set = {nid for nid in nodes if f_has_node(fp, nid)}
            if not node_set:
                return result

            f_get_node = self.f_get_node
            for nid in node_set:
                result['nodes'][nid] = f_get_node(fp, nid)

            # collect induced edges: for every node in the set, walk its
            # outgoing/undirected adjacency and keep edges whose other
            # endpoint is also in the set (each edge counted once)
            f_read = self.f_read
            f_get_adj = self.f_get_adj
            _generate_edge_key = self._generate_edge_key
            edge_re = self.EDGE_RE
            seen = set()
            for nid in node_set:
                for entry in f_get_adj(fp, nid):
                    d, other = entry[0], entry[1:]
                    if other in node_set:
                        edge_key = _generate_edge_key(nid, other, d == '>') if d != '<' else None
                        if edge_key is not None and edge_key not in seen:
                            seen.add(edge_key)
                            matched = edge_re.match(edge_key)
                            if matched:
                                result['edges'][matched.groups()] = f_read(fp, edge_key, copy=False)

        return result

    def export_graph(self, nodes:Optional[Any]=None) -> Dict[str,Any]:
        """Export the graph (or an induced subgraph) to a portable format.

        The result is plain dicts/lists of JSON-serializable values, suitable
        for ``json.dump``, backup, migration to another store, or conversion
        to a third-party graph library (e.g. build a ``networkx`` graph by
        adding each entry in ``'nodes'`` via ``G.add_node(id, **props)`` and
        each entry in ``'edges'`` via ``G.add_edge(u, v, **properties)``,
        adding both directions for ``directed=False`` entries if the target
        is a directed graph type).

        Args:
            nodes (Optional[Any], optional): If given, export only the
                induced subgraph over these node ids (see ``subgraph``).
                Defaults to None (export the whole graph).

        Returns:
            Dict[str, Any]: ``{'nodes': {id: props}, 'edges': [{'u': src,
                'v': dst, 'directed': bool, 'properties': props}, ...]}``.
        """
        if nodes is not None:
            sub = self.subgraph(nodes)
            edges = [
                {'u': src, 'v': dst, 'directed': edge_type == '>', 'properties': props}
                for (src, edge_type, dst), props in sub['edges'].items()
            ]
            return {'nodes': sub['nodes'], 'edges': edges}

        with self.open() as fp:
            out_nodes = {nid: self.f_get_node(fp, nid) for nid, _row in self.f_iter_nodes(fp)}
            out_edges = [
                {'u': src, 'v': dst, 'directed': edge_type == '>', 'properties': props}
                for (src, edge_type, dst), _row in self.f_iter_edges(fp)
                for props in [self.f_get_edge(fp, src, dst, edge_type == '>')]
            ]

        return {'nodes': out_nodes, 'edges': out_edges}

    def import_graph(self, data:Dict[str,Any]) -> Dict[str,int]:
        """Load a graph previously produced by ``export_graph`` into this graph.

        Adds every node and edge from ``data`` via ``add_node``/``add_edge``,
        so nodes/edges that already exist have their properties merged rather
        than duplicated or overwritten wholesale. Does not clear any existing
        data first — call ``clear()`` beforehand for a full replace.

        Args:
            data (Dict[str, Any]): Export data in the format produced by
                ``export_graph`` — ``{'nodes': {id: props}, 'edges': [{'u':
                src, 'v': dst, 'directed': bool, 'properties': props}, ...]}``.

        Returns:
            Dict[str, int]: ``{'nodes': n_nodes_written, 'edges':
                n_edges_written}`` — counts of add calls that actually wrote
                (new or changed), per the return value of ``add_node``/
                ``add_edge``.
        """
        add_node = self.add_node
        add_edge = self.add_edge
        n_nodes = sum(1 for nid, props in data.get('nodes', {}).items() if add_node(nid, **(props or {})))
        n_edges = sum(1 for e in data.get('edges', [])
                      if add_edge(e['u'], e['v'], directed=e.get('directed', True), **(e.get('properties') or {})))

        return {'nodes': n_nodes, 'edges': n_edges}

    def to_networkx(self, nodes:Optional[Any]=None) -> Any:
        """Convert this graph, or an induced subgraph, to a networkx graph.

        Requires the optional ``networkx`` package (imported lazily). Reads
        directly via ``f_iter_nodes``/``f_get_node``/``f_iter_edges``/
        ``f_get_edge`` inside a single transaction, rather than building an
        intermediate ``export_graph()`` dict.

        A networkx graph is homogeneous — fully directed or fully undirected
        — while GraphDb allows directed and undirected edges to coexist. If
        every included edge has the same direction, the matching networkx
        type is returned (``nx.Graph`` if all undirected, ``nx.DiGraph`` if
        all directed). Otherwise a ``nx.DiGraph`` is returned with each
        undirected edge added as a reciprocal pair of directed edges (the
        standard way to represent an undirected edge in a directed graph),
        so no edge is lost.

        Args:
            nodes (Optional[Any], optional): If given, include only these
                node ids and the edges between them (an induced subgraph,
                found by filtering the full node/edge scan — not an
                adjacency walk). Defaults to None (the whole graph).

        Returns:
            networkx.Graph or networkx.DiGraph: The converted graph, with
                node/edge properties carried over as networkx attributes.

        Raises:
            ImportError: If the ``networkx`` package is not installed.
        """
        try:
            import networkx as nx # pylint: disable=import-outside-toplevel
        except ImportError as e:
            raise ImportError("to_networkx() requires the 'networkx' package (pip install networkx)") from e

        node_filter = set(nodes) if nodes is not None else None
        with self.open() as fp:
            f_get_node = self.f_get_node
            node_items = [
                (nid, dict(f_get_node(fp, nid) or {}))
                for nid, _row in self.f_iter_nodes(fp)
                if node_filter is None or nid in node_filter
            ]

            f_get_edge = self.f_get_edge
            edges = []
            for (src, edge_type, dst), _row in self.f_iter_edges(fp):
                if node_filter is not None and (src not in node_filter or dst not in node_filter):
                    continue
                props = dict(f_get_edge(fp, src, dst, edge_type == '>') or {})
                edges.append((src, dst, edge_type == '>', props))

        if edges and all(not directed for _u, _v, directed, _p in edges):
            G = nx.Graph()
            G.add_nodes_from(node_items)
            for u, v, _directed, props in edges:
                G.add_edge(u, v, **props)
            return G

        G = nx.DiGraph()
        G.add_nodes_from(node_items)
        for u, v, directed, props in edges:
            G.add_edge(u, v, **props)
            if not directed:
                G.add_edge(v, u, **props)

        return G

    def from_networkx(self, G:Any) -> Dict[str,int]:
        """Import nodes and edges from a networkx graph object.

        A ``Graph``/``MultiGraph`` is treated as fully undirected; a
        ``DiGraph``/``MultiDiGraph`` as fully directed. For a multigraph,
        only the last parallel edge between a given pair is kept, since
        GraphDb stores a single record per ``(u, v, direction)``. Writes
        directly via ``f_add_node``/``f_add_edge`` inside a single write
        transaction (rather than one ``open()`` per node/edge through
        ``add_node``/``add_edge``), while still applying the same id and
        self-loop validation those public methods perform, so nodes/edges
        that already exist have their properties merged rather than
        duplicated.

        Args:
            G (Any): A networkx graph object (duck-typed: only ``is_directed()``,
                ``nodes(data=True)``, and ``edges(data=True)`` are used, so no
                import of ``networkx`` is required by this method itself).

        Returns:
            Dict[str, int]: ``{'nodes': n_nodes_written, 'edges':
                n_edges_written}``.

        Raises:
            KeyError: If a node id is empty or contains ``':'``, or if an
                edge is a self-loop (``u == v``) — the same validation
                ``add_node``/``add_edge`` perform.
        """
        directed = G.is_directed()
        n_nodes = n_edges = 0
        with self.open(read_only=False) as fp:
            f_add_node = self.f_add_node
            f_add_edge = self.f_add_edge

            for nid, attrs in G.nodes(data=True):
                if f_add_node(fp, nid, **dict(attrs)):
                    n_nodes += 1

            for u, v, attrs in G.edges(data=True):
                if f_add_edge(fp, u, v, directed, **dict(attrs)):
                    n_edges += 1

        return {'nodes': n_nodes, 'edges': n_edges}

    def degree_centrality(self) -> Dict[str,float]:
        """Compute degree centrality for every node.

        Degree centrality is a node's total degree (in + out + undirected)
        normalized by ``N - 1`` (the maximum possible), where ``N`` is the
        node count.

        Returns:
            Dict[str, float]: Mapping of node id to degree centrality in
                ``[0, 1]``. All zeros when there is only one node.
        """
        with self.open() as fp:
            nodes = [nid for nid, _row in self.f_iter_nodes(fp)]
            n = len(nodes)
            norm = (n - 1) if n > 1 else 1
            f_get_adj = self.f_get_adj
            return {nid: len(f_get_adj(fp, nid)) / norm for nid in nodes}

    def clustering(self, node_id:str) -> float:
        """Compute the local clustering coefficient of a node.

        Measures how connected a node's neighbors are to each other: the
        fraction of neighbor pairs that are themselves connected, out of all
        possible neighbor pairs. Uses the same direction-agnostic notion of
        "neighbor" as ``neighbors``. Computed purely from adjacency sets
        (no edge-key lookups needed), costing ``O(degree(node_id) +
        sum(degree(neighbor) for neighbor in neighbors))``.

        Args:
            node_id (str): Node identifier.

        Returns:
            float: Clustering coefficient in ``[0, 1]``. 0.0 if the node is
                missing or has fewer than 2 neighbors (no possible pairs).
        """
        with self.open() as fp:
            if not self.f_has_node(fp, node_id):
                return 0.0

            f_get_adj = self.f_get_adj
            neighbors = {entry[1:] for entry in f_get_adj(fp, node_id)}
            k = len(neighbors)
            if k < 2:
                return 0.0

            links = sum(len({entry[1:] for entry in f_get_adj(fp, nb)} & neighbors) for nb in neighbors)

        return links / (k * (k - 1))

    def average_clustering(self) -> float:
        """Compute the average local clustering coefficient over all nodes.

        Reads every node's adjacency in a single transaction (rather than
        calling ``clustering`` once per node, which would open a
        fresh transaction each time), then reduces to the mean.

        Returns:
            float: Mean clustering coefficient in ``[0, 1]``. 0.0 for an
                empty graph.
        """
        with self.open() as fp:
            f_get_adj = self.f_get_adj
            nodes = [nid for nid, _row in self.f_iter_nodes(fp)]
            if not nodes:
                return 0.0
            adj = {nid: {entry[1:] for entry in f_get_adj(fp, nid)} for nid in nodes}

        total = 0.0
        for nid in nodes:
            neighbors = adj[nid]
            k = len(neighbors)
            if k >= 2:
                links = sum(len(adj.get(nb, set()) & neighbors) for nb in neighbors)
                total += links / (k * (k - 1))

        return total / len(nodes)

    def density(self) -> float:
        """Compute the density of the graph.

        Ratio of actual edges to the maximum possible number of edges. An
        undirected edge is counted as contributing to both of its endpoints
        (equivalent to two directed edges), matching how ``degree`` and
        ``degree_centrality`` already treat undirected edges, so the result
        is the standard directed-density formula when the graph is fully
        directed and the standard undirected-density formula when it is
        fully undirected.

        Returns:
            float: Density in ``[0, 1]``. 0.0 for a graph with fewer than 2
                nodes.
        """
        with self.open() as fp:
            n = sum(1 for _nid, _row in self.f_iter_nodes(fp))
            if n < 2:
                return 0.0

            directed_count = undirected_count = 0
            for (_src, edge_type, _dst), _row in self.f_iter_edges(fp):
                if edge_type == '>':
                    directed_count += 1
                else:
                    undirected_count += 1

        return (directed_count + 2 * undirected_count) / (n * (n - 1))

    def pagerank(self, alpha:float=0.85, max_iter:int=100, tol:float=1e-6) -> Dict[str,float]:
        """Rank nodes by PageRank over the directed graph.

        Outgoing directed edges and undirected edges (both directions) define
        the link structure. Dangling nodes (no out-links) redistribute their
        rank uniformly. Iteration stops when the total change falls below
        ``tol`` or after ``max_iter`` iterations.

        Args:
            alpha (float, optional): Damping factor. Defaults to 0.85.
            max_iter (int, optional): Maximum iterations. Defaults to 100.
            tol (float, optional): L1 convergence threshold. Defaults to 1e-6.

        Returns:
            Dict[str, float]: Mapping of node id to PageRank score; scores sum
                to approximately 1. Empty for an empty graph.
        """
        with self.open() as fp:
            nodes = [nid for nid, _row in self.f_iter_nodes(fp)]
            n = len(nodes)
            if n == 0:
                return {}

            out = {}
            f_get_adj = self.f_get_adj
            for nid in nodes:
                # dedupe: a neighbor linked by both a directed and an
                # undirected edge must only count as one out-link
                out[nid] = list(dict.fromkeys(
                    entry[1:] for entry in f_get_adj(fp, nid) if entry[0] != '<'))

        rank = {nid: 1.0 / n for nid in nodes}
        base = (1.0 - alpha) / n
        for _ in range(max_iter):
            dangling = alpha * sum(rank[nid] for nid in nodes if not out[nid]) / n
            new_rank = {nid: base + dangling for nid in nodes}
            for nid in nodes:
                targets = out[nid]
                if targets:
                    share = alpha * rank[nid] / len(targets)
                    for t in targets:
                        new_rank[t] += share

            delta = sum(abs(new_rank[nid] - rank[nid]) for nid in nodes)
            rank = new_rank
            if delta < tol:
                break

        return rank

    def betweenness_centrality(self, normalized:bool=True) -> Dict[str,float]:
        """Compute (shortest-path) betweenness centrality via Brandes.

        Betweenness of a node is the sum over all node pairs of the fraction
        of shortest paths passing through it. Uses outgoing directed and
        undirected edges. Runs an unweighted (BFS) Brandes algorithm in
        O(V*E) time.

        Args:
            normalized (bool, optional): If True, divide by the number of
                ordered pairs ``(N-1)(N-2)`` (directed convention). Defaults
                to True.

        Returns:
            Dict[str, float]: Mapping of node id to betweenness centrality.
        """
        with self.open() as fp:
            nodes = [nid for nid, _row in self.f_iter_nodes(fp)]
            adj = {}
            f_get_adj = self.f_get_adj
            for nid in nodes:
                # dedupe: a neighbor linked by both a directed and an
                # undirected edge must only be traversed once
                adj[nid] = list(dict.fromkeys(\
                        entry[1:] for entry in f_get_adj(fp, nid) if entry[0] != '<'))

        cb = {nid: 0.0 for nid in nodes}
        for s in nodes:
            stack = []
            preds = {w: [] for w in nodes}
            sigma = {w: 0.0 for w in nodes}
            sigma[s] = 1.0
            dist = {w: -1 for w in nodes}
            dist[s] = 0
            queue = deque([s])
            while queue:
                v = queue.popleft()
                stack.append(v)
                for w in adj[v]:
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)

            delta = {w: 0.0 for w in nodes}
            while stack:
                w = stack.pop()
                for v in preds[w]:
                    if sigma[w]:
                        delta[v] += (sigma[v] / sigma[w]) * (1.0 + delta[w])
                if w != s:
                    cb[w] += delta[w]

        if normalized and len(nodes) > 2:
            scale = 1.0 / ((len(nodes) - 1) * (len(nodes) - 2))
            cb = {nid: val * scale for nid, val in cb.items()}

        return cb

    def edge_betweenness_centrality(self, normalized:bool=True) -> Dict[Tuple[str,str,str],float]:
        """Compute (shortest-path) edge betweenness centrality via Brandes.

        Betweenness of an edge is the sum over all node pairs of the
        fraction of shortest paths that cross it. Uses the same reachability
        graph as ``betweenness_centrality`` (outgoing directed and undirected
        edges, deduped so a pair linked by both counts once for path
        purposes), then attributes each Brandes accumulation step to the
        specific edge it crosses instead of to the intermediate node.

        Args:
            normalized (bool, optional): If True, scale by ``1 / (N*(N-1))``
                when every edge is directed, or ``2 / (N*(N-1))`` if any
                undirected edge is present — matching the directed/undirected
                normalization convention networkx uses for ``nx.DiGraph`` vs
                ``nx.Graph``. Defaults to True.

        Returns:
            Dict[Tuple[str, str, str], float]: Mapping of ``(src, edge_type,
                dst)`` (the same edge-key tuple shape used by ``subgraph``/
                ``export_graph``) to its betweenness score.
        """
        with self.open() as fp:
            nodes = [nid for nid, _row in self.f_iter_nodes(fp)]
            adj = {}
            f_get_adj = self.f_get_adj
            for nid in nodes:
                # dedupe: a neighbor linked by both a directed and an
                # undirected edge must only be traversed once
                adj[nid] = list(dict.fromkeys(\
                        entry[1:] for entry in f_get_adj(fp, nid) if entry[0] != '<'))

            # resolve each (v, w) reachability pair to its real edge-key
            # tuple once, up front: prefer the directed edge if both a
            # directed and an undirected edge exist between the same pair
            _generate_edge_key = self._generate_edge_key
            edge_match = self.EDGE_RE.match
            key_table = self.io.key_table
            pair_to_edge = {}
            all_directed = True
            for v in nodes:
                for w in adj[v]:
                    if (v, w) not in pair_to_edge:
                        directed_key = _generate_edge_key(v, w, True)
                        all_directed, edge_key = (all_directed, directed_key) if directed_key in key_table else \
                                                (False, _generate_edge_key(v, w, False))
                        matched = edge_match(edge_key)
                        if matched:
                            pair_to_edge[(v, w)] = matched.groups()

        cb_pair = {}
        for s in nodes:
            stack = []
            preds = {w: [] for w in nodes}
            sigma = {w: 0.0 for w in nodes}
            sigma[s] = 1.0
            dist = {w: -1 for w in nodes}
            dist[s] = 0
            queue = deque([s])
            while queue:
                v = queue.popleft()
                stack.append(v)
                for w in adj[v]:
                    if dist[w] < 0:
                        dist[w] = dist[v] + 1
                        queue.append(w)
                    if dist[w] == dist[v] + 1:
                        sigma[w] += sigma[v]
                        preds[w].append(v)

            delta = {w: 0.0 for w in nodes}
            while stack:
                w = stack.pop()
                for v in preds[w]:
                    if sigma[w]:
                        c = (sigma[v] / sigma[w]) * (1.0 + delta[w])
                        cb_pair[(v, w)] = cb_pair.get((v, w), 0.0) + c
                        delta[v] += c

        result = {pair_to_edge[pair]: score for pair, score in cb_pair.items() if pair in pair_to_edge}

        if normalized and len(nodes) > 1:
            scale = (1.0 if all_directed else 2.0) / (len(nodes) * (len(nodes) - 1))
            result = {k: v * scale for k, v in result.items()}

        return result

    def all_shortest_paths(self, source:str, target:str, direction:str='out', edge_filter:Optional[Any]=None) -> List[List[str]]:
        """Find every shortest (fewest-hop) path between two nodes.

        Runs a BFS that records all predecessors at the shortest distance,
        then enumerates every path through that predecessor DAG.

        Args:
            source (str): source node identifier.
            target (str): target node identifier.
            direction (str, optional): Edge direction to follow from each
                node — ``'out'`` (default) follows outgoing directed and
                undirected edges, ``'in'`` follows incoming directed and
                undirected edges, ``'both'`` follows every incident edge.
            edge_filter (Optional[Callable[[dict], bool]], optional): If
                given, only cross an edge when ``edge_filter(props)`` is
                truthy for that edge's properties. Defaults to None (no
                filtering).

        Returns:
            List[List[str]]: All shortest paths (each a node-id list from
                ``source`` to ``target`` inclusive), or an empty list if either
                node is missing or no path exists. For ``source == target``
                returns ``[[source]]``.
        """
        with self.open() as fp:
            if not self.f_has_node(fp, source) or not self.f_has_node(fp, target):
                return []

            if source == target:
                return [[source]]

            f_get_adj = self.f_get_adj
            f_read = self.f_read
            _generate_edge_key = self._generate_edge_key
            dist = {source: 0}
            preds = {source: []}
            queue = deque([source])
            found_depth = None
            while queue:
                cur = queue.popleft()
                if found_depth is None or dist[cur] < found_depth:
                    for entry in f_get_adj(fp, cur):
                        d, neighbor = entry[0], entry[1:]
                        if direction == 'out' and d == '<': continue
                        if direction == 'in' and d == '>': continue
                        if edge_filter is not None:
                            edge_key = _generate_edge_key(neighbor, cur, True) if d == '<' else \
                                    _generate_edge_key(cur, neighbor, d == '>')
                            props = f_read(fp, edge_key, copy=False)
                            if not edge_filter(props if isinstance(props, dict) else {}):
                                continue

                        nd = dist[cur] + 1
                        if neighbor not in dist:
                            dist[neighbor] = nd
                            preds[neighbor] = [cur]
                            if neighbor == target:
                                found_depth = nd
                            else:
                                queue.append(neighbor)
                        elif dist[neighbor] == nd:
                            preds[neighbor].append(cur)

            if target not in dist:
                return []

            # backtrack every path from target to source through preds
            paths = []
            def build(node, acc):
                if node == source:
                    paths.append([source] + acc[::-1])
                    return
                for p in preds[node]:
                    build(p, acc + [node])

            build(target, [])
            return paths

    def strongly_connected_components(self) -> List[List[str]]:
        """Find the strongly connected components of the directed graph.

        Two nodes are in the same component iff each is reachable from the
        other following edge direction (outgoing directed and undirected
        edges). Uses an iterative Tarjan algorithm, so it is safe on deep
        graphs.

        Returns:
            List[List[str]]: Components as lists of node ids. Every node
                appears in exactly one component (singletons for nodes not in
                any directed cycle).
        """
        with self.open() as fp:
            nodes = [nid for nid, _row in self.f_iter_nodes(fp)]
            adj = {}
            f_get_adj = self.f_get_adj
            for nid in nodes:
                # dedupe: a neighbor linked by both a directed and an
                # undirected edge must only be traversed once
                adj[nid] = list(dict.fromkeys(\
                    entry[1:] for entry in f_get_adj(fp, nid) if entry[0] != '<'))

        index_counter = [0]
        indices = {}
        lowlink = {}
        on_stack = {}
        stack = []
        components = []

        for root in nodes:
            if root in indices:
                continue
            # iterative DFS: work items are (node, neighbor_iterator_position)
            work = [(root, 0)]
            while work:
                node, pi = work[-1]
                if pi == 0:
                    indices[node] = lowlink[node] = index_counter[0]
                    index_counter[0] += 1
                    stack.append(node)
                    on_stack[node] = True

                recursed = False
                neighbors = adj[node]
                while pi < len(neighbors):
                    w = neighbors[pi]
                    if w not in indices:
                        work[-1] = (node, pi + 1)
                        work.append((w, 0))
                        recursed = True
                        break
                    if on_stack.get(w):
                        if indices[w] < lowlink[node]:
                            lowlink[node] = indices[w]
                    pi += 1
                else:
                    work[-1] = (node, pi)

                if recursed:
                    continue

                # done exploring node's neighbours
                if lowlink[node] == indices[node]:
                    comp = []
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        comp.append(w)
                        if w == node:
                            break
                    components.append(comp)

                work.pop()
                if work:
                    parent = work[-1][0]
                    if lowlink[node] < lowlink[parent]:
                        lowlink[parent] = lowlink[node]

        return components

    def verify_index(self) -> Dict[str,list]:
        """Check the persisted adjacency blobs against the edge records.
 
        Compares the adjacency entries implied by the ``E:`` edge records
        (the source of truth) against what is actually stored in each node's
        ``X:`` blob, without modifying anything. This detects drift caused by
        an edge key being deleted (or otherwise written) directly, bypassing
        ``remove_edge``/``f_remove_edge``, which would leave a stale entry in
        the surviving endpoint's adjacency and never touch the deleted edge's
        own endpoint.
 
        Returns:
            Dict[str, list]: ``{'missing': [(node_id, entry), ...], 'orphan':
                [(node_id, entry), ...]}`` sorted for stable output.
                ``missing`` entries should exist (a backing edge is present)
                but do not. ``orphan`` entries exist in a node's adjacency but
                have no backing edge — the symptom of an edge deleted outside
                ``remove_edge``. Both empty means the index is consistent.
        """
        with self.open() as fp:
            expected = {}
            for (src, edge_type, dst), _row_id in self.f_iter_edges(fp):
                if edge_type == '>':
                    expected.setdefault(src, set()).add(f'>{dst}')
                    expected.setdefault(dst, set()).add(f'<{src}')
                else:
                    expected.setdefault(src, set()).add(f'-{dst}')
                    expected.setdefault(dst, set()).add(f'-{src}')

            actual = {}
            for adj_id, (_row_id, adj) in self.f_iter_adjs(fp):
                actual[adj_id] = set(adj)

        missing = []
        orphan = []
        for node_id in sorted(set(expected) | set(actual)):
            exp = expected.get(node_id, set())
            act = actual.get(node_id, set())
            for entry in sorted(exp - act):
                missing.append((node_id, entry))
            for entry in sorted(act - exp):
                orphan.append((node_id, entry))

        return {'missing': missing, 'orphan': orphan}

    def reindex(self) -> Dict[str,int]:
        """Rebuild every adjacency blob from the edge records (source of truth).
 
        Drops every ``X:`` adjacency key and regenerates it from the ``E:``
        edge records. Use to repair adjacency drift — most commonly after an
        edge key was deleted directly (e.g. via a raw key delete or an
        external process) instead of through ``remove_edge``/
        ``f_remove_edge``, which leaves the other endpoint's adjacency
        pointing at a now-nonexistent edge.
 
        Returns:
            Dict[str, int]: ``{'removed': n_old_adjacency_keys, 'rebuilt':
                n_new_adjacency_keys}``.
        """
        with self.open() as fp:
            io, fp, _key_fp = self.f_get_fp(fp)
            key_table = io.key_table
            adj_match = self.ADJ_RE.match
            old_keys = [(row_id, key) for key, row_id in key_table.items() if adj_match(key)]

            new_adj = {}
            for (src, edge_type, dst), _row_id in self.f_iter_edges(fp):
                if edge_type == '>':
                    new_adj.setdefault(src, []).append(f'>{dst}')
                    new_adj.setdefault(dst, []).append(f'<{src}')
                else:
                    new_adj.setdefault(src, []).append(f'-{dst}')
                    new_adj.setdefault(dst, []).append(f'-{src}')

            io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
            f_delete = self.f_delete
            for row_id, key in sorted(old_keys, reverse=True):
                f_delete(fp, key, row=row_id)

            f_write = self.f_write
            for node_id, entries in new_adj.items():
                f_write(fp, f'X:{node_id}:', entries, overwrite=True, max_wsize=0)

        return {'removed': len(old_keys), 'rebuilt': len(new_adj)}

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
 
        Each node with at least one edge has an adjacency stored under
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
        ``open()`` context. 

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Unique node identifier.
            **properties: Arbitrary node properties to store.

        Returns:
            bool: True if a write occurred, False if nothing changed.
        """
        if not node_id or node_id.find(':') >= 0:
            raise JKeyError('invalid node_id')

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
        matched_keys = []
        io, fp, _key_fp = self.f_get_fp(fp)
        key_table = io.key_table
        row_id = key_table.get(node_key, -1)
        if row_id >= 0:
            matched_keys.append((row_id, node_key))

        adj_key = f'X:{node_id}:'
        row_id = key_table.get(adj_key, -1)
        if row_id >= 0:
            matched_keys.append((row_id, adj_key))
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
                    matched_keys.append((edge_row, edge_key))

                # clean the neighbor once (drops every entry
                # that points back at node_id, directed or undirected)
                adj_key = f'X:{neighbor}:'
                adj_row = key_table.get(adj_key, -1)
                if adj_row >= 0 \
                        and adj_key not in cleaned_adjs \
                        and (adj_row, adj_key) not in matched_keys:
                    cleaned_adjs.add(adj_key)
                    new_adj = []
                    old_adj = f_read(fp, adj_key, default_val=[], copy=False)
                    for _adj_id in old_adj:
                        if _adj_id[1:] != node_id:
                            new_adj.append(_adj_id)

                    if not new_adj:
                        matched_keys.append((adj_row, adj_key))

                    elif new_adj != old_adj:
                        f_write(fp, adj_key, new_adj, overwrite=True, max_wsize=0)

        if matched_keys:
            io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
            f_delete = self.f_delete
            matched_keys.sort(reverse=True)
            for row_id,key in matched_keys:
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
        must be called inside an ``open()`` context.

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
        if u == v:
            raise JKeyError('u cannot be v')

        if not u or not v or u.find(':') >= 0 or v.find(':') >= 0:
            raise JKeyError('invalid u or v')

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
