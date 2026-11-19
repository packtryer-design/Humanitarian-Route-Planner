"""A* route search for the Humanitarian Route Planner. Educational purposes only.

Member 3 component. It works on the graph prepared by Member 1's data module:

    data  = load_workbook('data/hrp_network_data.xlsx')
    edges = prepare_edges(data, 'S1', shipment_tonnes=10, allow_risk5=False)
    graph = adjacency(data, edges)
    result = astar(graph, node_coordinates(data), 'IHC', 'ELO', objective='time')

prepare_edges has already removed closed legs, risk-5 legs (unless the override
is on) and legs without enough capacity, so A* and Dijkstra receive identical
data and settings. A* only decides the order in which locations are explored.

A* expands locations in order of f(n) = g(n) + h(n), where g(n) is the cost of
the best route found so far from the origin and h(n) estimates the cost still
to go. h(n) is the straight-line distance to the goal multiplied by the best
"cost per straight-line kilometre" of any leg in the prepared graph. It never
overestimates, so A* returns the same optimal cost as Dijkstra.
"""
import heapq
import itertools
import math
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

MEMBER1_DIR = Path(__file__).resolve().parent.parent / 'member1'
if str(MEMBER1_DIR) not in sys.path:
    sys.path.insert(0, str(MEMBER1_DIR))
from member1_data import adjacency, load_workbook, prepare_edges, validate  # noqa: E402

DEFAULT_WORKBOOK = MEMBER1_DIR / 'data' / 'hrp_network_data.xlsx'
ORIGIN = 'IHC'
DESTINATION = 'ELO'
EARTH_RADIUS_KM = 6371.0
COLD_CHAIN_HOURS = 72.0

# Risk-weighted cost: cost x (1 + RISK_WEIGHT x (risk - 1)).
# Risk 1 -> x1.00, 2 -> x1.25, 3 -> x1.50, 4 -> x1.75, 5 -> x2.00.
# Proposed value; the group still has to agree it (see Member 1's report).
RISK_WEIGHT = 0.25

TIME_FIELDS = {'typical': 'transit_hours_typical', 'p90': 'transit_hours_p90'}


# ---------------------------------------------------------------------------
# Objectives: the weight of one leg
# ---------------------------------------------------------------------------

def time_weight(edge):
    return edge['transit_hours_typical']


def p90_time_weight(edge):
    return edge['transit_hours_p90']


def cost_weight(edge):
    return edge['cost_usd_per_tonne']


def risk_cost_weight(edge):
    return edge['cost_usd_per_tonne'] * (1 + RISK_WEIGHT * (edge['risk_score_1to5'] - 1))


OBJECTIVES = {
    'time': time_weight,            # typical transit hours
    'p90_time': p90_time_weight,    # sum of leg P90 hours (planning margin)
    'cost': cost_weight,            # USD per tonne
    'risk_cost': risk_cost_weight,  # USD per tonne, inflated by risk
}


# ---------------------------------------------------------------------------
# Heuristic
# ---------------------------------------------------------------------------

def node_coordinates(data):
    """node_id -> (lat, lon) from the locations sheet."""
    return {r['node_id']: (r['lat'], r['lon']) for r in data['locations']}


def haversine_km(a, b):
    """Great-circle distance in km between two (lat, lon) points in degrees."""
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def best_rate_per_km(graph, coords, weight):
    """Smallest (leg weight / straight-line length of the leg) in the graph.

    No leg in this graph covers one straight-line kilometre for less. It is
    recomputed for every request, so it always matches the scenario, shipment
    and risk settings that produced the graph.
    """
    best = math.inf
    for edges in graph.values():
        for e in edges:
            span = haversine_km(coords[e['from_node']], coords[e['to_node']])
            if span > 0:
                best = min(best, weight(e) / span)
    return 0.0 if math.isinf(best) else best


def straight_line_heuristic(graph, coords, goal, weight):
    """h(n) = straight-line distance from n to the goal x best rate per km.

    Admissible: every leg costs at least `rate` per straight-line km, and the
    straight-line lengths of the legs on any route add up to at least the
    straight-line distance to the goal (triangle inequality). So no route can
    cost less than h(n). The same argument for one leg (u, v) gives
    h(u) <= w(u, v) + h(v), so the heuristic is also consistent.
    """
    rate = best_rate_per_km(graph, coords, weight)
    goal_xy = coords[goal]
    cache = {}

    def h(node):
        if node not in cache:
            cache[node] = rate * haversine_km(coords[node], goal_xy)
        return cache[node]

    h.rate = rate
    return h


def zero_heuristic(_node):
    """h = 0 turns A* into Dijkstra; used as the like-for-like baseline."""
    return 0.0


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class RouteResult:
    found: bool
    start: str
    goal: str
    objective: str
    cost: float                      # total of the chosen objective
    legs: list                       # edge dicts from Member 1's module, in order
    nodes_expanded: int
    labels_generated: int
    runtime_ms: float
    expansion_trace: list = field(default_factory=list)  # [{node, g, h, f}]
    reason: str = ''                 # why no route was found
    max_hours: float = None
    risk_cap: int = None

    @property
    def path(self):
        return [self.start] + [e['to_node'] for e in self.legs] if self.found else []

    @property
    def leg_ids(self):
        return [e['leg_id'] for e in self.legs]

    @property
    def expansion_order(self):
        return [step['node'] for step in self.expansion_trace]

    @property
    def total_hours(self):
        return sum(e['transit_hours_typical'] for e in self.legs)

    @property
    def total_p90_hours(self):
        """Sum of leg P90 times. Not the P90 of the whole route."""
        return sum(e['transit_hours_p90'] for e in self.legs)

    @property
    def total_cost_usd_per_tonne(self):
        return sum(e['cost_usd_per_tonne'] for e in self.legs)

    @property
    def total_risk_cost(self):
        return sum(risk_cost_weight(e) for e in self.legs)

    @property
    def max_risk(self):
        """Route risk = highest leg risk (the weakest link)."""
        return max((e['risk_score_1to5'] for e in self.legs), default=0)

    def meets_cold_chain(self, limit=COLD_CHAIN_HOURS, basis='typical'):
        return self.found and sum(e[TIME_FIELDS[basis]] for e in self.legs) <= limit + 1e-9

    def summary(self):
        """Flat dictionary for tables, CSV files and the interface."""
        return {
            'found': self.found, 'start': self.start, 'goal': self.goal,
            'objective': self.objective,
            'cost': round(self.cost, 3) if self.found else None,
            'route': ' > '.join(self.path), 'legs': ' '.join(self.leg_ids),
            'modes': ' '.join(e['mode'] for e in self.legs),
            'hours_typical': round(self.total_hours, 2),
            'hours_p90_sum': round(self.total_p90_hours, 2),
            'cost_usd_per_tonne': round(self.total_cost_usd_per_tonne, 2),
            'risk_cost': round(self.total_risk_cost, 2), 'max_risk': self.max_risk,
            'meets_72h': self.meets_cold_chain(), 'nodes_expanded': self.nodes_expanded,
            'labels_generated': self.labels_generated, 'runtime_ms': round(self.runtime_ms, 3),
            'max_hours': self.max_hours, 'risk_cap': self.risk_cap, 'reason': self.reason,
        }


# ---------------------------------------------------------------------------
# A* search
# ---------------------------------------------------------------------------

def astar(graph, coords, start, goal, objective='time', *, max_hours=None,
          time_basis='typical', max_risk=None, heuristic='straight_line', epsilon=1.0):
    """Best route from start to goal in a graph prepared by Member 1's module.

    objective   'time', 'p90_time', 'cost' or 'risk_cost'
    max_hours   whole-route time limit, e.g. 72 for cold chain. The search then
                looks for the best route that also fits the limit, instead of
                rejecting the unconstrained answer afterwards.
    time_basis  'typical' or 'p90': which time column max_hours applies to
    max_risk    highest leg risk score allowed (1-5); legs above it are never
                expanded. None keeps every leg in the prepared graph.
    heuristic   'straight_line', 'zero' (Dijkstra behaviour) or a function
    epsilon     weighted A*, f = g + epsilon * h. 1.0 keeps routes optimal;
                larger values explore less but may cost up to epsilon x optimum.
    """
    if start not in graph or goal not in graph:
        raise ValueError('Unknown start or goal location')
    if objective not in OBJECTIVES:
        raise ValueError('Unknown objective ' + str(objective))
    if not (isinstance(epsilon, (int, float)) and epsilon >= 1):
        raise ValueError('epsilon must be at least 1')
    if time_basis not in TIME_FIELDS:
        raise ValueError('time_basis must be typical or p90')
    if max_hours is not None and not max_hours > 0:
        raise ValueError('max_hours must be positive')
    if max_risk is not None:
        if max_risk not in (1, 2, 3, 4, 5):
            raise ValueError('max_risk must be an integer from 1 to 5')
        graph = {n: [e for e in edges if e['risk_score_1to5'] <= max_risk] for n, edges in graph.items()}

    weight = OBJECTIVES[objective]
    if heuristic == 'straight_line':
        h = straight_line_heuristic(graph, coords, goal, weight)
    elif heuristic == 'zero':
        h = zero_heuristic
    elif callable(heuristic):
        h = heuristic
    else:
        raise ValueError('Unknown heuristic')

    clock = time.perf_counter()
    if max_hours is None:
        result = _search(graph, start, goal, weight, h, epsilon)
    else:
        time_field = TIME_FIELDS[time_basis]
        h_time = straight_line_heuristic(graph, coords, goal, lambda e: e[time_field])
        result = _search_with_time_limit(graph, start, goal, weight, h, epsilon,
                                         max_hours, time_field, h_time)
    found, cost, legs, expanded, generated, trace, reason = result
    return RouteResult(found, start, goal, objective, cost, legs, expanded, generated,
                       (time.perf_counter() - clock) * 1000, trace, reason, max_hours, max_risk)


def _search(graph, start, goal, weight, h, epsilon):
    """Standard A* with a closed set (valid because h is consistent)."""
    g = {start: 0.0}
    came_by = {}           # node -> leg used to reach it on the best route so far
    closed = set()
    trace = []
    tie = itertools.count()
    generated = 1
    # Heap entries: (f, h, tie, node). Equal f: prefer the node nearer the goal.
    frontier = [(epsilon * h(start), h(start), next(tie), start)]

    while frontier:
        f, h_node, _, node = heapq.heappop(frontier)
        if node in closed:
            continue        # stale entry; a cheaper one was expanded already
        closed.add(node)
        trace.append({'node': node, 'g': g[node], 'h': h_node, 'f': f})
        if node == goal:
            return True, g[node], _rebuild(came_by, start, goal), len(trace), generated, trace, ''
        for e in graph[node]:
            nxt = e['to_node']
            if nxt in closed:
                continue
            step = weight(e)
            if step < 0:
                raise ValueError(e['leg_id'] + ': negative leg weight')
            new_g = g[node] + step
            if new_g < g.get(nxt, math.inf):
                g[nxt] = new_g
                came_by[nxt] = e
                h_next = h(nxt)
                heapq.heappush(frontier, (new_g + epsilon * h_next, h_next, next(tie), nxt))
                generated += 1
    return False, math.inf, [], len(trace), generated, trace, 'No feasible route with the current scenario and settings'


def _search_with_time_limit(graph, start, goal, weight, h, epsilon, max_hours, time_field, h_time):
    """A* over labels (location, cost so far, hours so far).

    One location can be reached by a cheap slow route and a dearer fast one,
    and only the fast one may fit the time limit, so one best cost per
    location is not enough. A label is kept unless another label at the same
    location is at least as cheap and at least as fast (dominance). A label is
    also dropped if hours so far + h_time(location) exceeds the limit, where
    h_time is the same straight-line bound for time, so it can never finish
    within the limit.
    """
    labels = [(start, 0.0, 0.0, None, None)]     # (node, g, hours, parent, leg)
    done = {}                                    # node -> [(g, hours)] expanded
    trace = []
    tie = itertools.count()
    generated = 1

    def dominated(node, g, hours):
        return any(g0 <= g + 1e-9 and t0 <= hours + 1e-9 for g0, t0 in done.get(node, ()))

    reason = 'No route within the time limit with the current scenario and settings'
    if h_time(start) > max_hours + 1e-9:
        return False, math.inf, [], 0, generated, trace, reason
    frontier = [(epsilon * h(start), h(start), next(tie), 0)]
    while frontier:
        f, h_node, _, i = heapq.heappop(frontier)
        node, g, hours, _, _ = labels[i]
        if dominated(node, g, hours):
            continue
        done.setdefault(node, []).append((g, hours))
        trace.append({'node': node, 'g': g, 'h': h_node, 'f': f, 'hours': hours})
        if node == goal:
            legs = []
            while labels[i][3] is not None:
                legs.append(labels[i][4])
                i = labels[i][3]
            return True, g, legs[::-1], len(trace), generated, trace, ''
        for e in graph[node]:
            nxt = e['to_node']
            new_hours = hours + e[time_field]
            if new_hours + h_time(nxt) > max_hours + 1e-9:
                continue
            step = weight(e)
            if step < 0:
                raise ValueError(e['leg_id'] + ': negative leg weight')
            new_g = g + step
            if dominated(nxt, new_g, new_hours):
                continue
            labels.append((nxt, new_g, new_hours, i, e))
            h_next = h(nxt)
            heapq.heappush(frontier, (new_g + epsilon * h_next, h_next, next(tie), len(labels) - 1))
            generated += 1
    return False, math.inf, [], len(trace), generated, trace, reason


def _rebuild(came_by, start, goal):
    legs, node = [], goal
    while node != start:
        legs.append(came_by[node])
        node = came_by[node]['from_node']
    return legs[::-1]


# ---------------------------------------------------------------------------
# Priority order: lowest risk first, then the objective
# ---------------------------------------------------------------------------

def lowest_risk_route(graph, coords, start, goal, objective='time', **options):
    """Usual priority from the brief: lowest risk subject to feasibility, then
    fastest (or the chosen objective).

    Route risk is the highest leg risk on the route. The search tries a risk
    cap of 1, then 2, and so on, and returns the first cap that has a route;
    within that cap A* picks the best route for the objective. Equal-time ties
    are not broken by cost.
    """
    limit = options.pop('max_risk', None) or 5
    caps = sorted({e['risk_score_1to5'] for edges in graph.values() for e in edges if e['risk_score_1to5'] <= limit})
    last = None
    for cap in caps:
        last = astar(graph, coords, start, goal, objective, max_risk=cap, **options)
        if last.found:
            return last
    if last is None:
        last = astar(graph, coords, start, goal, objective, max_risk=limit, **options)
    return last


# ---------------------------------------------------------------------------
# One call for the interface and the experiments
# ---------------------------------------------------------------------------

CARGO_POLICIES = {
    # cargo: (objective, use risk priority, whole-route hour limit)
    'cold_chain': ('time', False, COLD_CHAIN_HOURS),  # life-saving, fastest within 72 h
    'medical': ('time', False, None),                  # life-saving, fastest feasible
    'bulk_food': ('cost', False, None),                # cheapest acceptable
    'standard': ('time', True, None),                  # lowest risk, then fastest
}


def plan(data, scenario='S0', destination=DESTINATION, cargo='standard',
         shipment_tonnes=1, allow_risk5=False, origin=ORIGIN, objective=None, **options):
    """Prepare a fresh graph with Member 1's module and run A* for one request.

    cargo sets the rule from the brief; objective overrides it if given.
    Returns the RouteResult.
    """
    if cargo not in CARGO_POLICIES:
        raise ValueError('Unknown cargo type ' + str(cargo))
    default_objective, by_risk, max_hours = CARGO_POLICIES[cargo]
    edges = prepare_edges(data, scenario, shipment_tonnes, allow_risk5)
    graph = adjacency(data, edges)
    coords = node_coordinates(data)
    options.setdefault('max_hours', max_hours)
    search = lowest_risk_route if by_risk else astar
    return search(graph, coords, origin, destination, objective or default_objective, **options)


def destinations(data):
    """The main destination followed by the alternative destinations in the data."""
    main = [r['node_id'] for r in data['locations'] if r['role'] == 'Destination']
    other = [r['node_id'] for r in data['locations'] if r['role'] == 'Alternative destination']
    return main + sorted(other)


def main():
    data = load_workbook(DEFAULT_WORKBOOK)
    validate(data)
    print('A* routes from IHC to ELO, 1 tonne, risk-5 override off. Educational purposes only.\n')
    for sid in [f'S{i}' for i in range(10)]:
        for cargo in CARGO_POLICIES:
            r = plan(data, sid, cargo=cargo)
            text = (f"{r.total_hours:6.1f} h  ${r.total_cost_usd_per_tonne:6.0f}/t  risk {r.max_risk}  "
                    f"{' > '.join(r.path)}") if r.found else r.reason
            print(f'{sid}  {cargo:<10}  {text}')
        print()


if __name__ == '__main__':
    main()
