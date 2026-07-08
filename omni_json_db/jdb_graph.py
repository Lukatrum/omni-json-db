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

EDGE_RE = re_compile(r'^E:(.+?):([->]):(.+?):$')
NODE_RE = re_compile(r'^N:(.+?):$')
# adjacency index key:  X:{node}:{dir}:{neighbor}:  where dir in > (out) / < (in) / - (undirected)
ADJ_RE  = re_compile(r'^X:(.+?):([-><]):(.+?):$')
MAX_RECURSION = 500


class GraphDb(JDb):
    """Graph database layer built on top of the JDb key-value store.

    Storage schema (edge records are the single source of truth; adjacency is
    a derived, rebuildable index):

    * ``N:{node_id}:``                  -> node properties (dict)
    * ``E:{u}:>:{v}:``                  -> directed edge properties (dict)
    * ``E:{u}:-:{v}:``                  -> undirected edge properties (dict,
      endpoints sorted lexicographically)
    * ``X:{node}:>:{neighbor}:``        -> '' : outgoing directed adjacency
    * ``X:{node}:<:{neighbor}:``        -> '' : incoming directed adjacency
    * ``X:{node}:-:{neighbor}:``        -> '' : undirected adjacency

    The adjacency index stores one tiny key per (node, direction, neighbor)
    triple, so a node's neighbours form a contiguous key range ``X:{node}:``.
    Reading neighbours is an ordered prefix scan (O(degree)); adding or
    removing an edge inserts/deletes two index keys (O(log n) each) with no
    read-modify-write of a per-node blob, so even very high-degree ("super")
    nodes stay cheap to update. This trades extra keys/storage for scalable
    writes and low, bounded traversal memory.

    Note:
        Efficient ``X:`` prefix scans require an *ordered* key table backend
        (e.g. a B-tree). On an unordered (hash) backend the prefix scan falls
        back to a full key-table scan and loses its asymptotic advantage.
    """
    def __init__(self,\
            KEY_file:Union[str,bytearray,JFilesBase,JDbReader,None]=None,\
            data_type:Union[str,int,None]='J+S',\
            zip_type:Union[str,int,None]='no',\
            key_limit:Union[str,int,None]='no',\
            cache_limit:int=0,\
            **kwargs):
        """Initialize the transactional GraphDb controller.

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

    # =====================================================================
    # low-level prefix / range scan
    # =====================================================================
    def f_iter_prefix(self, fp:Dict[int,IO], prefix:str) -> Generator[Tuple[str,int], None, None]:
        """Yield ``(key, row_id)`` for every key starting with ``prefix``.

        Uses an ordered range scan (``key_table.keys(min, max)``) when the
        backend supports it, so the cost is proportional to the number of
        matching keys rather than the whole table. Falls back to a filtered
        full scan on unordered backends. Must be called inside an ``open()``
        context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            prefix (str): Key prefix to match.

        Yields:
            Tuple[str, int]: ``(key, row_id)`` for each matching key.
        """
        io, fp, _key_fp = self.f_get_fp(fp)
        key_table = io.key_table
        range_keys = getattr(key_table, 'keys', None)
        # ordered backends (e.g. BTrees.OLBTree) accept keys(min, max)
        if range_keys is not None:
            try:
                # upper bound: prefix with last char incremented -> excludes siblings
                hi = prefix[:-1] + chr(ord(prefix[-1]) + 1) if prefix else None
                scanned = range_keys(prefix, hi) if hi is not None else range_keys()
                ordered = True

            except TypeError: # pragma: no cover
                scanned = None
                ordered = False

            if ordered and scanned is not None:
                for key in scanned:
                    if key.startswith(prefix):
                        yield key, key_table[key]
                    else: # pragma: no cover
                        break
                return

        # fallback: full scan (unordered backend)
        for key, row_id in key_table.items():
            if key.startswith(prefix):
                yield key, row_id

    # =====================================================================
    # node CRUD
    # =====================================================================
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
        with self.open() as fp:
            io, fp, _key_fp = self.f_get_fp(fp)
            key_table = io.key_table
            node_key = f'N:{node_id}:'
            if node_key not in key_table:
                return self.f_write(fp, node_key, properties)

            old_props = self.f_read(fp, node_key, copy=False)
            if isinstance(old_props, dict):
                new_props = {**old_props, **properties}
                if new_props != old_props:
                    return self.f_write(fp, node_key, new_props)
            else:
                return self.f_write(fp, node_key, properties)

        return False

    def get_node(self, node_id:str) -> Dict[str,Any]:
        """Get the properties of a node.

        Args:
            node_id (str): Node identifier.

        Returns:
            Dict[str, Any]: Node properties, or None if the node does not exist.
        """
        return self.get(f'N:{node_id}:', None)

    def has_node(self, node_id:str) -> bool:
        """Check whether a node exists.

        Args:
            node_id (str): Node identifier.

        Returns:
            bool: True if the node exists, otherwise False.
        """
        with self.open() as _fp:
            return f'N:{node_id}:' in self.io.key_table

    def remove_node(self, node_id:str) -> Dict[str,Any]:
        """Remove a node together with all edges connected to it.

        Scans the node's adjacency range ``X:{node_id}:`` to find every
        incident edge, then deletes each edge record, both adjacency index
        keys (this node's and the mirror on the neighbour), and finally the
        node itself.

        Args:
            node_id (str): Node identifier.

        Returns:
            Dict[str, Any]: Mapping of every deleted key to its stored value.
                Empty if the node does not exist.
        """
        ret = {}
        with self.open() as fp:
            io, fp, _key_fp = self.f_get_fp(fp)
            key_table = io.key_table
            node_key = f'N:{node_id}:'
            matched_keys = {}

            row_id = key_table.get(node_key, -1)
            if row_id >= 0:
                matched_keys[node_key] = row_id

            _generate_edge_key = self._generate_edge_key
            # every adjacency key of this node -> its edge + both index sides
            for adj_key, adj_row in self.f_iter_prefix(fp, f'X:{node_id}:'):
                matched = ADJ_RE.match(adj_key)
                if matched:
                    _n, direction, neighbor = matched.groups()
                    matched_keys[adj_key] = adj_row

                    if direction == '>':
                        edge_key = _generate_edge_key(node_id, neighbor, True)
                        mirror = f'X:{neighbor}:<:{node_id}:'
                    elif direction == '<':
                        edge_key = _generate_edge_key(neighbor, node_id, True)
                        mirror = f'X:{neighbor}:>:{node_id}:'
                    else:
                        edge_key = _generate_edge_key(node_id, neighbor, False)
                        mirror = f'X:{neighbor}:-:{node_id}:'

                    edge_row = key_table.get(edge_key, -1)
                    if edge_row >= 0:
                        matched_keys[edge_key] = edge_row

                    mirror_row = key_table.get(mirror, -1)
                    if mirror_row >= 0:
                        matched_keys[mirror] = mirror_row

            if matched_keys:
                io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
                f_delete = self.f_delete
                # delete high row-ids first (stable under row compaction)
                for key, _row in sorted(matched_keys.items(), key=lambda kv: -kv[1]):
                    ret[key] = f_delete(fp, key)

        return ret

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
        node_match = NODE_RE.match
        for key, val in self.find_iter(NODE_RE, vals=condition, date=date, limit=limit, skip=skip, with_value=True, **kwargs):
            matched = node_match(key)
            if matched:
                ret[matched.groups()[0]] = val

        return ret

    def iter_nodes(self) -> Generator[Tuple[int,str], None, None]:
        """Iterate over all nodes in the graph.

        Yields:
            Tuple[int, str]: ``(row_id, node_id)`` for each node.
        """
        with self.open() as fp: # pylint: disable=W0135
            yield from self.f_iter_nodes(fp)

    # =====================================================================
    # edge CRUD
    # =====================================================================
    def add_edge(self, u:str, v:str, directed:bool=True, **properties) -> bool:
        """Add an edge between two nodes, creating missing endpoint nodes.

        Writes the edge record plus the two adjacency index keys (one on each
        endpoint). If the edge already exists, ``properties`` are merged over
        the stored properties.

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
            raise ValueError('u cannot be v')

        edge_key = self._generate_edge_key(u, v, directed)
        with self.open() as fp:
            key_table = self.io.key_table
            if edge_key not in key_table:
                _io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
                f_write = self.f_write
                u_key = f'N:{u}:'
                if u_key not in key_table:
                    f_write(fp, u_key, {}, compare=False)

                v_key = f'N:{v}:'
                if v_key not in key_table:
                    f_write(fp, v_key, {}, compare=False)

                f_write(fp, f'X:{u}:{">" if directed else "-"}:{v}:', '', compare=False)
                f_write(fp, f'X:{v}:{"<" if directed else "-"}:{u}:', '', compare=False)

            return self.f_add_edge(fp, edge_key, **properties)

    def add_temporal_edge(self, u:str, v:str, directed:bool, expire_days:Union[int,float,str,dt_date,datetime]):
        """Add (or renew) an edge that expires after ``expire_days``.

        Args:
            u (str): Source node identifier.
            v (str): Target node identifier.
            directed (bool): True for a directed edge ``u -> v``, False for
                an undirected edge.
            expire_days (Union[int, float, str, dt_date, datetime]): Expiry,
                forwarded to ``f_change_days`` (int days, 'YYYY-MM-DD'
                string, date/datetime, or timestamp float).

        Returns:
            bool: True on success.
        """
        if u == v: # pragma: no cover
            raise ValueError('u cannot be v')

        edge_key = self._generate_edge_key(u, v, directed)
        with self.open() as fp:
            key_table = self.io.key_table
            if edge_key not in key_table:
                _io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
                f_write = self.f_write
                u_key = f'N:{u}:'
                if u_key not in key_table:
                    f_write(fp, u_key, {}, compare=False)

                v_key = f'N:{v}:'
                if v_key not in key_table:
                    f_write(fp, v_key, {}, compare=False)

                f_write(fp, f'X:{u}:{">" if directed else "-"}:{v}:', '', compare=False)
                f_write(fp, f'X:{v}:{"<" if directed else "-"}:{u}:', '', compare=False)

            self.f_add_edge(fp, edge_key, relation="temporary_access")
            return self.f_change_days(fp, edge_key, expire_days)

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
        return self.get(self._generate_edge_key(u, v, directed), None)

    def remove_edge(self, u:str, v:str, directed:bool=True) -> Dict[str,Any]:
        """Remove an edge and its two adjacency index keys.

        Args:
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
        with self.open() as fp:
            key_table = self.io.key_table
            if edge_key in key_table:
                _io, fp, _key_fp, _sync_chg = self.f_get_write_fp(fp)
                f_delete = self.f_delete
                ret[edge_key] = f_delete(fp, edge_key)

                f_delete(fp, f'X:{u}:{">" if directed else "-"}:{v}:')
                f_delete(fp, f'X:{v}:{"<" if directed else "-"}:{u}:')

        return ret

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
            Dict[Tuple[str,str,str], Any]: Mapping of ``(src, edge_type, dst)``
                to edge properties for every match.
        """
        ret = {}
        edge_match = EDGE_RE.match
        for key, val in self.find_iter(EDGE_RE, vals=condition, date=date, limit=limit, skip=skip, with_value=True, **kwargs):
            matched = edge_match(key)
            if matched:
                ret[matched.groups()] = val

        return ret

    def iter_edges(self) -> Generator[Tuple[int,str,str,str], None, None]:
        """Iterate over all edges in the graph.

        Yields:
            Tuple[int, str, str, str]: ``(row_id, src, edge_type, dst)`` for
                each edge, where ``edge_type`` is ``'>'`` (directed) or
                ``'-'`` (undirected).
        """
        with self.open() as fp: # pylint: disable=W0135
            yield from self.f_iter_edges(fp)

    # =====================================================================
    # neighbourhood queries (O(degree) via adjacency prefix scan)
    # =====================================================================
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
        adj_match = ADJ_RE.match
        with self.open() as fp:
            for key, _row_id in self.f_iter_prefix(fp, f'X:{node_id}:'):
                matched = adj_match(key)
                if matched:
                    direction = matched.groups()[1]
                    if direction == '>':
                        o_deg += 1
                    elif direction == '<':
                        i_deg += 1
                    else:
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
        self.update_if(Edge._id.startswith('E:') & (Edge.relation == relation_type), \
                patch=lambda edge,props: {'weight' : props.get('weight', 1) + boost_value})

    # =====================================================================
    # graph algorithms (on-demand adjacency prefix scan; bounded memory)
    # =====================================================================
    def bfs_shortest_path(self, start:str, end:str) -> List[str]:
        """Find a shortest path (fewest hops) between two nodes using BFS.

        Directed edges are followed forward only; undirected edges are
        traversed in both directions. Each visited node's neighbours are read
        on demand via an adjacency prefix scan, so peak memory is bounded by
        the BFS frontier rather than the whole graph.

        Args:
            start (str): Start node identifier.
            end (str): End node identifier.

        Returns:
            List[str]: Node ids along a shortest path from ``start`` to
                ``end`` inclusive, or an empty list if either node is missing
                or no path exists.
        """
        with self.open() as fp:
            io, fp, _key_fp = self.f_get_fp(fp)
            key_table = io.key_table
            if f'N:{start}:' not in key_table or f'N:{end}:' not in key_table:
                return []

            previous_nodes = {start: None}
            queue = deque([start])
            visited = {start}
            f_iter_prefix = self.f_iter_prefix
            adj_match = ADJ_RE.match

            while queue:
                current_node = queue.popleft()
                if current_node == end:
                    path = []
                    while current_node is not None:
                        path.append(current_node)
                        current_node = previous_nodes[current_node]
                    return path[::-1]

                for key, _row_id in f_iter_prefix(fp, f'X:{current_node}:'):
                    matched = adj_match(key)
                    if matched:
                        _n, direction, neighbor = matched.groups()
                        if direction == '<':
                            continue
                        if neighbor not in visited:
                            visited.add(neighbor)
                            previous_nodes[neighbor] = current_node
                            queue.append(neighbor)

        return []

    def dijkstra_shortest_path(self, start:str, end:str, weight_key:str="weight") -> Tuple[float,List[str]]:
        """Find the minimum-weight path between two nodes using Dijkstra.

        Edge weights are read from each edge's ``weight_key`` property and
        default to 1 when missing. Weights must be non-negative for the
        result to be correct. Directed edges are followed forward only;
        undirected edges are traversed in both directions. Adjacency and edge
        properties are read on demand.

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
            io, fp, _key_fp = self.f_get_fp(fp)
            key_table = io.key_table
            if f'N:{start}:' not in key_table or f'N:{end}:' not in key_table:
                return float('inf'), []

            distances = {start: 0}
            previous_nodes = {start: None}
            queue = [(0, start)]
            f_read = self.f_read
            f_iter_prefix = self.f_iter_prefix
            _generate_edge_key = self._generate_edge_key
            adj_match = ADJ_RE.match

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

                for key, _row_id in f_iter_prefix(fp, f'X:{current_node}:'):
                    matched = adj_match(key)
                    if matched:
                        _n, direction, neighbor = matched.groups()
                        if direction == '<':
                            continue

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
        followed in both directions. Adjacency is read on demand per node.

        Args:
            start (str): Start node identifier.
            visited (Optional[Set[str]], optional): Pre-populated visited set,
                allowing traversal state to be shared across calls. Mutated
                in place. Defaults to a new empty set.

        Returns:
            list: Node ids in DFS pre-order starting from ``start``, or an
                empty list if ``start`` does not exist.
        """
        f_iter_prefix = self.f_iter_prefix
        adj_match = ADJ_RE.match

        def dfs(fp, node_id, visited, level=0) -> list:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            path = []
            if node_id not in visited:
                visited.add(node_id)
                path.append(node_id)
                for key, _row_id in f_iter_prefix(fp, f'X:{node_id}:'):
                    matched = adj_match(key)
                    if matched:
                        _n, direction, successor = matched.groups()
                        if direction == '<':
                            continue
                        path.extend(dfs(fp, successor, visited, level+1))

            return path

        if visited is None: visited = set()
        with self.open() as fp:
            if f'N:{start}:' in self.io.key_table:
                return dfs(fp, start, visited)

        return []

    def is_cyclic(self) -> bool:
        """Detect whether the graph contains a cycle.

        Uses DFS with a recursion stack. Directed edges are followed forward
        only; undirected edges are treated as bidirectional but the edge just
        traversed is not immediately walked back over, so a lone undirected
        edge is not a cycle while a genuine undirected loop is.

        Note:
            Implemented recursively; very deep graphs may hit Python's
            recursion limit.

        Returns:
            bool: True if any cycle is reachable, otherwise False.
        """
        f_iter_prefix = self.f_iter_prefix
        _generate_edge_key = self._generate_edge_key
        adj_match = ADJ_RE.match

        def dfs(fp, node_id, visited, stack, parent_key=None, level=0) -> bool:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            stack.add(node_id)
            is_fully_explored = True
            for key, _row_id in f_iter_prefix(fp, f'X:{node_id}:'):
                matched = adj_match(key)
                if matched:
                    _n, direction, successor = matched.groups()
                    if direction == '<':
                        continue

                    edge_key = _generate_edge_key(node_id, successor, direction == '>')
                    if edge_key == parent_key:
                        # same edge we arrived through: not a cycle back over itself
                        is_fully_explored = False
                        continue

                    if successor in stack:
                        return True

                    if successor not in visited:
                        if dfs(fp, successor, visited, stack, edge_key, level+1):
                            return True

            stack.remove(node_id)
            if is_fully_explored:
                visited.add(node_id)
            return False

        visited = set()
        stack = set()
        with self.open() as fp:
            for _row_id, node_id in self.f_iter_nodes(fp):
                if node_id not in visited:
                    if dfs(fp, node_id, visited, stack):
                        return True

        return False

    def topological_sort(self) -> List[str]:
        """Topologically sort the graph in a single DFS pass.

        Cycle detection is folded into the same traversal (via a recursion
        stack). Nodes are pushed in post-order and the reversed stack is
        returned. Undirected edges use the same cycle rule as ``is_cyclic``.

        Note:
            Implemented recursively; very deep graphs may hit Python's
            recursion limit.

        Returns:
            List[str]: Node ids in a valid topological order.

        Raises:
            ValueError: If the graph contains a cycle (not a DAG).
        """
        f_iter_prefix = self.f_iter_prefix
        _generate_edge_key = self._generate_edge_key
        adj_match = ADJ_RE.match

        def dfs(fp, node_id, visited, rec_stack, stack, parent_key=None, level=0) -> bool:
            if level >= MAX_RECURSION: # pragma: no cover
                raise RecursionError

            visited.add(node_id)
            rec_stack.add(node_id)
            for key, _row_id in f_iter_prefix(fp, f'X:{node_id}:'):
                matched = adj_match(key)
                if matched:
                    _n, direction, successor = matched.groups()
                    if direction == '<':
                        continue

                    edge_key = _generate_edge_key(node_id, successor, direction == '>')
                    if not (direction == '-' and edge_key == parent_key):
                        if successor not in visited:
                            if dfs(fp, successor, visited, rec_stack, stack, edge_key, level+1):
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
            for _row_id, node_id in self.f_iter_nodes(fp):
                if node_id not in visited:
                    if dfs(fp, node_id, visited, rec_stack, stack):
                        raise ValueError("Must be a Directed Acyclic Graph.")

        return stack[::-1]

    def connected_components(self) -> list:
        """Find the weakly connected components of the graph.

        Edge direction is intentionally ignored (weak connectivity): two
        nodes belong to the same component if any chain of edges links them.
        Adjacency is read on demand per node.

        Returns:
            list: A list of components, each a list of node ids discovered
                by BFS. Isolated nodes form single-element components.
        """
        visited = set()
        components = []
        adj_match = ADJ_RE.match
        with self.open() as fp:
            f_iter_prefix = self.f_iter_prefix
            for _row_id, node_id in self.f_iter_nodes(fp):
                if node_id not in visited:
                    component = []
                    queue = deque([node_id])
                    visited.add(node_id)
                    while queue:
                        current_node = queue.popleft()
                        component.append(current_node)
                        for key, _r in f_iter_prefix(fp, f'X:{current_node}:'):
                            matched = adj_match(key)
                            if matched:
                                neighbor = matched.groups()[2]
                                if neighbor not in visited:
                                    visited.add(neighbor)
                                    queue.append(neighbor)

                    components.append(component)

        return components

    # =====================================================================
    # low-level iterators
    # =====================================================================
    def f_iter_edges(self, fp:Dict[int,IO]) -> Generator[Tuple[int,str,str,str], None, None]:
        """Iterate over all edges from the key table.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.

        Yields:
            Tuple[int, str, str, str]: ``(row_id, src, edge_type, dst)`` for
                each edge.
        """
        edge_match = EDGE_RE.match
        for key, row_id in self.f_iter_prefix(fp, 'E:'):
            matched = edge_match(key)
            if matched:
                src, edge_type, dst = matched.groups()
                yield row_id, src, edge_type, dst

    def f_iter_nodes(self, fp:Dict[int,IO]) -> Generator[Tuple[int,str], None, None]:
        """Iterate over all nodes from the key table.

        Low-level helper; must be called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.

        Yields:
            Tuple[int, str]: ``(row_id, node_id)`` for each node.
        """
        node_match = NODE_RE.match
        for key, row_id in self.f_iter_prefix(fp, 'N:'):
            matched = node_match(key)
            if matched:
                yield row_id, matched.groups()[0]

    def f_iter_neighbors(self, fp:Dict[int,IO], node_id:str) -> Generator[Tuple[str,str,int], None, None]:
        """Iterate over all edges incident to a node, ignoring direction.

        Reads the node's adjacency index range (``X:{node_id}:``) so the work
        is proportional to the node's degree. Low-level helper; must be
        called inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Yields:
            Tuple[str, str, int]: ``(neighbor_id, edge_key, row_id)`` for each
                edge touching ``node_id``.
        """
        key_table = self.io.key_table
        _generate_edge_key = self._generate_edge_key
        adj_match = ADJ_RE.match
        for key, _row_id in self.f_iter_prefix(fp, f'X:{node_id}:'):
            matched = adj_match(key)
            if matched:
                _n, direction, neighbor = matched.groups()
                edge_key = _generate_edge_key(node_id, neighbor, True) if direction == '>' else \
                        _generate_edge_key(neighbor, node_id, True) if direction == '<' else \
                        _generate_edge_key(node_id, neighbor, False)

                yield neighbor, edge_key, key_table.get(edge_key, -1)

    def f_iter_successors(self, fp:Dict[int,IO], node_id:str) -> Generator[Tuple[str,str,int], None, None]:
        """Iterate over one-hop successors of a node, respecting direction.

        Follows outgoing directed edges (index ``'>'``) and undirected edges
        (index ``'-'``); incoming directed edges (``'<'``) are skipped. Reads
        the node's adjacency index range. Low-level helper; must be called
        inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Yields:
            Tuple[str, str, int]: ``(successor_id, edge_key, row_id)`` for
                each qualifying edge.
        """
        key_table = self.io.key_table
        _generate_edge_key = self._generate_edge_key
        adj_match = ADJ_RE.match
        for key, _row_id in self.f_iter_prefix(fp, f'X:{node_id}:'):
            matched = adj_match(key)
            if matched:
                _n, direction, successor = matched.groups()
                if direction == '<':
                    continue

                edge_key = _generate_edge_key(node_id, successor, direction == '>')
                yield successor, edge_key, key_table.get(edge_key, -1)

    def f_iter_predecessors(self, fp:Dict[int,IO], node_id:str) -> Generator[Tuple[str,str,int], None, None]:
        """Iterate over one-hop predecessors of a node, respecting direction.

        Follows incoming directed edges (index ``'<'``) and undirected edges
        (index ``'-'``); outgoing directed edges (``'>'``) are skipped. Reads
        the node's adjacency index range. Low-level helper; must be called
        inside an ``open()`` context.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            node_id (str): Node identifier.

        Yields:
            Tuple[str, str, int]: ``(predecessor_id, edge_key, row_id)`` for
                each qualifying edge.
        """
        key_table = self.io.key_table
        _generate_edge_key = self._generate_edge_key
        adj_match = ADJ_RE.match
        for key, _row_id in self.f_iter_prefix(fp, f'X:{node_id}:'):
            matched = adj_match(key)
            if not matched:
                continue
            _n, direction, predecessor = matched.groups()
            if direction == '>':
                continue

            if direction == '<':
                edge_key = _generate_edge_key(predecessor, node_id, True)
            else:
                edge_key = _generate_edge_key(node_id, predecessor, False)

            yield predecessor, edge_key, key_table.get(edge_key, -1)

    def f_add_edge(self, fp:Dict[int,IO], edge_key:str, **properties) -> bool:
        """Write or merge an edge record by its raw key.

        Low-level helper; must be called inside an ``open()`` context. Does
        NOT maintain the adjacency index (callers that create edges must do
        that); intended for updating an existing edge's properties.

        Args:
            fp (Dict[int, IO]): File-pointer dict from ``open()``/``f_get_fp``.
            edge_key (str): Full edge key, e.g. ``'E:u:>:v:'``.
            **properties: Edge properties to store.

        Returns:
            bool: True if a write occurred, False if nothing changed.
        """
        if edge_key not in self.io.key_table:
            return self.f_write(fp, edge_key, properties)

        old_props = self.f_read(fp, edge_key, copy=False)
        if isinstance(old_props, dict):
            new_props = {**old_props, **properties}
            if new_props != old_props:
                return self.f_write(fp, edge_key, new_props)
        else:
            return self.f_write(fp, edge_key, properties)

        return False

    # =====================================================================
    # consistency: rebuild / verify the derived adjacency index
    # =====================================================================
    def reindex(self) -> Dict[str,int]:
        """Rebuild the adjacency index from the edge records (source of truth).

        Drops every ``X:`` adjacency key and regenerates it from the ``E:``
        edge records. Use to recover from a corrupted or drifted index, or
        after bulk-loading edges written without index maintenance.

        Returns:
            Dict[str, int]: Counters ``{'removed': n_old, 'added': n_new}``.
        """
        removed = added = 0
        with self.open(read_only=False) as fp:
            f_delete = self.f_delete
            f_write = self.f_write

            old_keys = [k for k, _r in self.f_iter_prefix(fp, 'X:')]
            for k in old_keys:
                f_delete(fp, k)
                removed += 1

            for _row_id, src, edge_type, dst in list(self.f_iter_edges(fp)):
                f_write(fp, f'X:{src}:{">" if edge_type == ">" else "-"}:{dst}:', '', compare=False)
                f_write(fp, f'X:{dst}:{"<" if edge_type == ">" else "-"}:{src}:', '', compare=False)
                added += 2

        return {'removed': removed, 'added': added}

    def verify_index(self) -> Dict[str,list]:
        """Check the adjacency index against the edge records.

        Compares the set of adjacency keys implied by the ``E:`` edge records
        (the source of truth) with the ``X:`` keys actually stored, without
        modifying anything.

        Returns:
            Dict[str, list]: ``{'missing': [...], 'orphan': [...]}`` — index
                keys that should exist but do not, and index keys that exist
                but have no backing edge. Both empty means the index is
                consistent.
        """
        with self.open() as fp:
            expected = set()
            for _row_id, src, edge_type, dst in self.f_iter_edges(fp):
                expected.add(f'X:{src}:{">" if edge_type == ">" else "-"}:{dst}:')
                expected.add(f'X:{dst}:{"<" if edge_type == ">" else "-"}:{src}:')

            actual = {k for k, _r in self.f_iter_prefix(fp, 'X:')}

        return {
            'missing': sorted(expected - actual),
            'orphan': sorted(actual - expected),
        }

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
