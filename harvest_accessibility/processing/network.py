"""Shortest distances along the road network, one search per landing.

Plain Python with no QGIS in it, so that it can be tested on its own.

QGIS's routing ties all the start points into the graph together, and where
they fall within the tolerance of each other or of a vertex they are merged.
The distance from one tree then depended on which other trees were in the
run: neighbouring trees came out with identical d2, and adding or removing
points moved the rest.  Here the network is built from the roads alone, each
landing is searched once, and a tree's distance is read off from where its
point lies on a segment -- so it depends on that tree and nothing else.
"""

import heapq
import math


class Location:
    """Where a point lies on the network: a segment, and how far along it."""

    __slots__ = ("seg", "along", "offset")

    def __init__(self, seg, along, offset):
        self.seg = seg          # index into Network.segments
        self.along = along      # distance from the segment's start
        self.offset = offset    # distance from the point to the segment


class Network:
    """An undirected graph of road segments, with gaps up to `tolerance` bridged.

    The tolerance is there to join lines that a hand-drawn network leaves
    not quite meeting, so a vertex joins the nearest node within it only if
    that node came from another line.  Within one line, vertices merge only
    where they coincide exactly (a loop closing on itself).  QGIS merges any
    vertices within the tolerance, which drops the length of every segment
    shorter than it: on a line surveyed at 1.5 m with a 2 m tolerance, half
    the line.

    Vertices are visited in a fixed order (line by line, vertex by vertex)
    and a node stays where its first vertex was, so the result does not
    depend on anything but the input.
    """

    def __init__(self, lines, tolerance, cell=None):
        self.tol = max(float(tolerance), 0.0)
        self.nodes = []        # (x, y) of each node
        self.adj = []          # node -> {neighbour: length}
        self.segments = []     # (node_a, node_b, (ax, ay), (bx, by), length)
        self._node_cell = max(self.tol, 1e-6)
        self._node_grid = {}
        self._node_lines = []  # node -> the lines that use it

        for k, line in enumerate(lines):
            prev_node, prev_pt = None, None
            for pt in line:
                pt = (float(pt[0]), float(pt[1]))
                node = self._node(pt, k)
                if prev_pt is not None:
                    length = math.dist(prev_pt, pt)
                    if length > 0:
                        self.segments.append((prev_node, node, prev_pt, pt, length))
                        if node != prev_node:
                            w = self.adj[prev_node].get(node)
                            if w is None or length < w:
                                self.adj[prev_node][node] = length
                                self.adj[node][prev_node] = length
                prev_node, prev_pt = node, pt

        self._build_segment_index(cell)

    # --- construction ------------------------------------------------------

    def _node(self, pt, line):
        cs = self._node_cell
        cx, cy = math.floor(pt[0] / cs), math.floor(pt[1] / cs)
        best, best_d = None, None
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for n in self._node_grid.get((gx, gy), ()):
                    d = math.dist(self.nodes[n], pt)
                    if d > self.tol or (d > 0 and line in self._node_lines[n]):
                        continue
                    if best_d is None or d < best_d or (d == best_d and n < best):
                        best, best_d = n, d
        if best is not None:
            self._node_lines[best].add(line)
            return best
        self.nodes.append(pt)
        self.adj.append({})
        self._node_lines.append({line})
        n = len(self.nodes) - 1
        self._node_grid.setdefault((cx, cy), []).append(n)
        return n

    def _build_segment_index(self, cell):
        if cell is None:
            lengths = sorted(s[4] for s in self.segments)
            cell = max(lengths[len(lengths) // 2], 1.0) if lengths else 1.0
        self._seg_cell = cell
        self._seg_grid = {}
        for i, (_, _, a, b, _) in enumerate(self.segments):
            x0, x1 = sorted((a[0], b[0]))
            y0, y1 = sorted((a[1], b[1]))
            for gx in range(math.floor(x0 / cell), math.floor(x1 / cell) + 1):
                for gy in range(math.floor(y0 / cell), math.floor(y1 / cell) + 1):
                    self._seg_grid.setdefault((gx, gy), []).append(i)
        if self._seg_grid:
            xs = [k[0] for k in self._seg_grid]
            ys = [k[1] for k in self._seg_grid]
            self._grid_bounds = (min(xs), max(xs), min(ys), max(ys))

    # --- queries -------------------------------------------------------------

    def locate(self, x, y):
        """The nearest point of the network to (x, y), as a Location.

        Ties go to the lower-numbered segment, so the answer does not depend
        on anything but the roads and the point.
        """
        if not self.segments:
            return None
        cs = self._seg_cell
        cx, cy = math.floor(x / cs), math.floor(y / cs)
        gx0, gx1, gy0, gy1 = self._grid_bounds
        max_r = max(abs(cx - gx0), abs(cx - gx1), abs(cy - gy0), abs(cy - gy1)) + 1
        best = None  # (offset, seg, along)
        seen = set()
        for r in range(max_r + 1):
            # Anything in ring r is at least (r - 1) cells away.
            if best is not None and best[0] < (r - 1) * cs:
                break
            for gx in range(cx - r, cx + r + 1):
                for gy in range(cy - r, cy + r + 1):
                    if max(abs(gx - cx), abs(gy - cy)) != r:
                        continue
                    for i in self._seg_grid.get((gx, gy), ()):
                        if i in seen:
                            continue
                        seen.add(i)
                        off, along = self._project(i, x, y)
                        if best is None or off < best[0] or (off == best[0] and i < best[1]):
                            best = (off, i, along)
        return Location(best[1], best[2], best[0])

    def _project(self, i, x, y):
        _, _, (ax, ay), (bx, by), length = self.segments[i]
        dx, dy = bx - ax, by - ay
        t = ((x - ax) * dx + (y - ay) * dy) / (length * length)
        t = min(1.0, max(0.0, t))
        px, py = ax + t * dx, ay + t * dy
        return math.hypot(x - px, y - py), t * length

    def distances_from(self, loc):
        """Network distance from a Location to every node (inf if unreachable)."""
        dist = [math.inf] * len(self.nodes)
        a, b, _, _, length = self.segments[loc.seg]
        heap = []
        for node, d in ((a, loc.along), (b, length - loc.along)):
            if d < dist[node]:
                dist[node] = d
                heapq.heappush(heap, (d, node))
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist[n]:
                continue
            for m, w in self.adj[n].items():
                nd = d + w
                if nd < dist[m]:
                    dist[m] = nd
                    heapq.heappush(heap, (nd, m))
        return dist

    def distance(self, dist, origin, loc):
        """Distance from the origin of `dist` to a Location, or None if unreachable."""
        a, b, _, _, length = self.segments[loc.seg]
        best = min(dist[a] + loc.along, dist[b] + length - loc.along)
        if loc.seg == origin.seg:
            best = min(best, abs(loc.along - origin.along))
        return None if math.isinf(best) else best
