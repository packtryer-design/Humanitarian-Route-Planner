"""Experiments for the Humanitarian Route Planner (Person 5).

Educational purposes only. All network data is hypothetical.

Compares the group's own implementations, unmodified:
    Dijkstra  = algorithms/dijkstra.py  (Person 2)
    A*        = algorithms/astar.py     (Person 3), straight-line heuristic
    A* (h=0)  = the same A* code with a zero heuristic, i.e. Dijkstra with a
                closed set, used as a like-for-like baseline

Person 2's Dijkstra does not report how many nodes it explored, so its heap is
wrapped with a counter (see _CountingHeap). Its code is not changed.

Run from the repository root:
    python experiments/run_experiments.py            # full run
    python experiments/run_experiments.py --quick    # fewer repeats, for testing

Outputs are written to experiments/results/ (CSV, JSON and PNG charts).
"""
import argparse
import csv
import heapq
import itertools
import json
import math
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'member1'))

from member1_data import adjacency, load_workbook, prepare_edges, validate  # noqa: E402
from algorithms import dijkstra as dijkstra_module  # noqa: E402
from algorithms.dijkstra import HumanitarianNetwork  # noqa: E402
from algorithms.astar import (  # noqa: E402
    DEFAULT_WORKBOOK, OBJECTIVES, ORIGIN, astar, destinations, haversine_km,
    lowest_risk_route, node_coordinates, plan, straight_line_heuristic)

RESULTS = Path(__file__).resolve().parent / 'results'
SCENARIOS = [f'S{i}' for i in range(10)]
SCENARIO_NAMES = {
    'S0': 'Baseline', 'S1': 'Port Sudan airport closed', 'S2': 'Red Sea transit suspended',
    'S3': 'Metema crossing closed', 'S4': 'Omdurman road blocked', 'S5': 'El Obeid airport closed',
    'S6': 'Rainy season', 'S7': 'Argeen congestion', 'S8': 'Insurance spike', 'S9': 'Compound disruption',
}
SHIPMENTS = (1, 10, 100)          # tonnes
TOL = 1e-6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _CountingHeap:
    """Stands in for the heapq module inside algorithms/dijkstra.py and counts
    every push and pop. Every pop in Person 2's Dijkstra expands a node (there
    is no closed set), so pops = node expansions, including re-expansions."""

    def __init__(self):
        self.pushes = 0
        self.pops = 0
        self.popped = []

    def heappush(self, queue, item):
        self.pushes += 1
        heapq.heappush(queue, item)

    def heappop(self, queue):
        item = heapq.heappop(queue)
        self.pops += 1
        self.popped.append(item[1])
        return item


def build_network(edges):
    """Person 2's graph class, filled the same way app.py fills it."""
    net = HumanitarianNetwork()
    for e in edges:
        net.add_leg(e['from_node'], e['to_node'], e['transit_hours_typical'],
                    e['cost_usd_per_tonne'], e['risk_score_1to5'], e['capacity_tonnes_per_week'])
    return net


def run_dijkstra(net, start, goal, objective, tonnes, risk5, cold=False):
    return net.dijkstra(start, goal, objective, cargo_weight=tonnes,
                        is_cold_chain=cold, risk_override=risk5)


def count_dijkstra(net, start, goal, objective, tonnes, risk5, cold=False):
    real = dijkstra_module.heapq
    heap = _CountingHeap()
    dijkstra_module.heapq = heap
    try:
        result = run_dijkstra(net, start, goal, objective, tonnes, risk5, cold)
    finally:
        dijkstra_module.heapq = real
    return result, heap


def dijkstra_cost(result, objective):
    return result[f'total_{objective}'] if result['path'] else None


def median_ms(fn, repeats):
    samples = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t) * 1000)
    return statistics.median(samples)


def same_cost(found_a, cost_a, found_b, cost_b):
    if found_a != found_b:
        return False
    return (not found_a) or abs(cost_a - cost_b) <= TOL


def mean_sd(values):
    values = list(values)
    if not values:
        return (float('nan'), float('nan'))
    return (statistics.mean(values), statistics.stdev(values) if len(values) > 1 else 0.0)


def write_csv(name, rows):
    RESULTS.mkdir(exist_ok=True)
    if not rows:
        return
    with open(RESULTS / name, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def legs_of(path, edges):
    index = {(e['from_node'], e['to_node']): e for e in edges}
    return [index[(a, b)] for a, b in zip(path, path[1:])]


# ---------------------------------------------------------------------------
# Experiment 1: do the algorithms agree, and how much does each explore?
# ---------------------------------------------------------------------------

def core_grid(data, repeats):
    """Every scenario x destination x objective x shipment size x risk-5 setting."""
    coords = node_coordinates(data)
    dests = destinations(data)
    rows = []
    for sid, tonnes, risk5 in itertools.product(SCENARIOS, SHIPMENTS, (False, True)):
        edges = prepare_edges(data, sid, tonnes, risk5)
        graph = adjacency(data, edges)
        net = build_network(edges)
        for dest, obj in itertools.product(dests, ('time', 'cost')):
            d_res, heap = count_dijkstra(net, ORIGIN, dest, obj, tonnes, risk5)
            a = astar(graph, coords, ORIGIN, dest, obj)
            z = astar(graph, coords, ORIGIN, dest, obj, heuristic='zero')
            d_found = d_res['path'] is not None
            d_cost = dijkstra_cost(d_res, obj)
            rows.append({
                'scenario': sid, 'tonnes': tonnes, 'risk5_allowed': risk5,
                'destination': dest, 'objective': obj,
                'dijkstra_found': d_found, 'astar_found': a.found, 'astar_h0_found': z.found,
                'dijkstra_cost': d_cost, 'astar_cost': a.cost if a.found else None,
                'astar_h0_cost': z.cost if z.found else None,
                'agree_dijkstra_astar': same_cost(d_found, d_cost, a.found, a.cost),
                'agree_astar_h0': same_cost(z.found, z.cost, a.found, a.cost),
                'same_route': d_res['path'] == a.path if d_found and a.found else (not d_found and not a.found),
                'dijkstra_expansions': heap.pops, 'dijkstra_unique_nodes': len(set(heap.popped)),
                'dijkstra_pushes': heap.pushes,
                'astar_expansions': a.nodes_expanded, 'astar_generated': a.labels_generated,
                'astar_h0_expansions': z.nodes_expanded, 'astar_h0_generated': z.labels_generated,
                'dijkstra_ms': median_ms(lambda: run_dijkstra(net, ORIGIN, dest, obj, tonnes, risk5), repeats),
                'astar_ms': median_ms(lambda: astar(graph, coords, ORIGIN, dest, obj), repeats),
                'astar_h0_ms': median_ms(lambda: astar(graph, coords, ORIGIN, dest, obj, heuristic='zero'), repeats),
            })
    return rows


# ---------------------------------------------------------------------------
# Experiment 2: whole-route 72-hour cold-chain limit
# ---------------------------------------------------------------------------

def cold_chain_grid(data):
    coords = node_coordinates(data)
    dests = destinations(data)
    rows = []
    for sid, tonnes, risk5, dest, obj in itertools.product(
            SCENARIOS, (1, 10), (False, True), dests, ('time', 'cost')):
        edges = prepare_edges(data, sid, tonnes, risk5)
        graph = adjacency(data, edges)
        net = build_network(edges)
        d_res = run_dijkstra(net, ORIGIN, dest, obj, tonnes, risk5, cold=True)
        a = astar(graph, coords, ORIGIN, dest, obj, max_hours=72)
        d_found = d_res['path'] is not None
        rows.append({
            'scenario': sid, 'tonnes': tonnes, 'risk5_allowed': risk5, 'destination': dest,
            'objective': obj, 'dijkstra_found': d_found, 'astar_found': a.found,
            'dijkstra_cost': dijkstra_cost(d_res, obj), 'astar_cost': a.cost if a.found else None,
            'dijkstra_hours': d_res.get('total_time') if d_found else None,
            'astar_hours': round(a.total_hours, 3) if a.found else None,
            'agree': same_cost(d_found, dijkstra_cost(d_res, obj), a.found, a.cost),
        })
    return rows


# ---------------------------------------------------------------------------
# Experiment 3: the "lowest risk" objective is defined differently
# ---------------------------------------------------------------------------

def risk_comparison(data):
    coords = node_coordinates(data)
    rows = []
    for sid in SCENARIOS:
        edges = prepare_edges(data, sid, 1, False)
        graph = adjacency(data, edges)
        net = build_network(edges)
        d_res = run_dijkstra(net, ORIGIN, 'ELO', 'risk', 1, False)
        a = lowest_risk_route(graph, coords, ORIGIN, 'ELO', 'time')
        row = {'scenario': sid}
        if d_res['path']:
            legs = legs_of(d_res['path'], edges)
            row.update({
                'dijkstra_route': ' > '.join(d_res['path']),
                'dijkstra_sum_risk': sum(e['risk_score_1to5'] for e in legs),
                'dijkstra_max_risk': max(e['risk_score_1to5'] for e in legs),
                'dijkstra_hours': round(sum(e['transit_hours_typical'] for e in legs), 1),
                'dijkstra_usd_per_t': round(sum(e['cost_usd_per_tonne'] for e in legs)),
            })
        if a.found:
            row.update({
                'astar_route': ' > '.join(a.path),
                'astar_sum_risk': sum(e['risk_score_1to5'] for e in a.legs),
                'astar_max_risk': a.max_risk,
                'astar_hours': round(a.total_hours, 1),
                'astar_usd_per_t': round(a.total_cost_usd_per_tonne),
            })
        row['same_route'] = d_res['path'] == a.path
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Experiment 4: heuristic study (optimal A*, zero heuristic, weighted A*)
# ---------------------------------------------------------------------------

HEURISTICS = [
    ('Dijkstra-equivalent (h=0)', {'heuristic': 'zero'}),
    ('A* straight-line (e=1.0)', {}),
    ('Weighted A* (e=1.5)', {'epsilon': 1.5}),
    ('Weighted A* (e=2)', {'epsilon': 2}),
    ('Weighted A* (e=3)', {'epsilon': 3}),
]


def heuristic_study(data):
    coords = node_coordinates(data)
    dests = destinations(data)
    out = {name: {'exp': [], 'ratio': []} for name, _ in HEURISTICS}
    for sid, dest, obj in itertools.product(SCENARIOS, dests, ('time', 'cost')):
        edges = prepare_edges(data, sid, 1, False)
        graph = adjacency(data, edges)
        best = astar(graph, coords, ORIGIN, dest, obj)
        if not best.found:
            continue
        for name, opts in HEURISTICS:
            r = astar(graph, coords, ORIGIN, dest, obj, **opts)
            out[name]['exp'].append(r.nodes_expanded)
            out[name]['ratio'].append(r.cost / best.cost if best.cost else 1.0)
    rows = []
    for name, _ in HEURISTICS:
        m, s = mean_sd(out[name]['exp'])
        rows.append({'method': name, 'queries': len(out[name]['exp']),
                     'mean_expansions': round(m, 2), 'sd_expansions': round(s, 2),
                     'mean_cost_ratio': round(statistics.mean(out[name]['ratio']), 4),
                     'worst_cost_ratio': round(max(out[name]['ratio']), 4)})
    return rows


# ---------------------------------------------------------------------------
# Experiment 5: effect of each disruption on the fastest and cheapest route
# ---------------------------------------------------------------------------

def disruption_impact(data):
    rows = []
    base = {}
    for sid in SCENARIOS:
        row = {'scenario': sid, 'name': SCENARIO_NAMES[sid]}
        for label, cargo in (('fastest', 'medical'), ('cheapest', 'bulk_food')):
            r = plan(data, sid, cargo=cargo, shipment_tonnes=1)
            if sid == 'S0':
                base[label] = r
            row[f'{label}_route'] = ' > '.join(r.path) if r.found else 'NO ROUTE'
            row[f'{label}_hours'] = round(r.total_hours, 1) if r.found else None
            row[f'{label}_usd_per_t'] = round(r.total_cost_usd_per_tonne) if r.found else None
            row[f'{label}_changed'] = r.path != base[label].path
            row[f'{label}_delta_hours'] = round(r.total_hours - base[label].total_hours, 1) if r.found else None
            row[f'{label}_delta_usd'] = round(r.total_cost_usd_per_tonne - base[label].total_cost_usd_per_tonne) if r.found else None
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Experiment 6: heuristic is admissible and consistent (checked, not assumed)
# ---------------------------------------------------------------------------

def cost_to_go(graph, goal, weight):
    """Exact cheapest cost from every location to the goal (reverse Dijkstra)."""
    rev = {n: [] for n in graph}
    for u, es in graph.items():
        for e in es:
            rev[e['to_node']].append((u, weight(e)))
    dist = {goal: 0.0}
    queue = [(0.0, goal)]
    while queue:
        d, node = heapq.heappop(queue)
        if d > dist.get(node, math.inf):
            continue
        for u, w in rev[node]:
            if d + w < dist.get(u, math.inf):
                dist[u] = d + w
                heapq.heappush(queue, (d + w, u))
    return dist


def check_heuristic(graph, coords, goal, objective):
    weight = OBJECTIVES[objective]
    h = straight_line_heuristic(graph, coords, goal, weight)
    dist = cost_to_go(graph, goal, weight)
    admissible = all(h(n) <= d + 1e-9 for n, d in dist.items())
    consistent = all(h(u) <= weight(e) + h(e['to_node']) + 1e-9
                     for u, es in graph.items() for e in es)
    return admissible, consistent


def heuristic_checks(data):
    coords = node_coordinates(data)
    checked = failed_adm = failed_con = 0
    for sid, tonnes, dest, obj in itertools.product(
            SCENARIOS, SHIPMENTS, destinations(data), tuple(OBJECTIVES)):
        graph = adjacency(data, prepare_edges(data, sid, tonnes, False))
        adm, con = check_heuristic(graph, coords, dest, obj)
        checked += 1
        failed_adm += not adm
        failed_con += not con
    return {'combinations_checked': checked, 'not_admissible': failed_adm, 'not_consistent': failed_con}


# ---------------------------------------------------------------------------
# Experiment 7: scaling on synthetic networks
# ---------------------------------------------------------------------------

MODE_SPECS = {'Road': (55.0, 0.9), 'Sea': (30.0, 0.35), 'Air': (700.0, 2.4)}   # km/h, USD per tonne-km


def synthetic_graph(n, seed, k=3):
    """Random connected transport network inside a lat/lon box, with the same
    fields as the real legs. Hypothetical; used only to study scaling."""
    rng = random.Random(seed)
    ids = [f'N{i:04d}' for i in range(n)]
    coords = {x: (rng.uniform(5, 35), rng.uniform(30, 60)) for x in ids}

    def flat(i, j):
        a, b = coords[ids[i]], coords[ids[j]]
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    pairs = set()
    for i in range(1, n):
        j = min(range(i), key=lambda j: flat(i, j))
        pairs.add((j, i))
    for i in range(n):
        near = sorted((j for j in range(n) if j != i), key=lambda j: flat(i, j))[:k]
        for j in near:
            pairs.add((min(i, j), max(i, j)))
    graph = {x: [] for x in ids}
    legs = 0
    for i, j in sorted(pairs):
        a, b = ids[i], ids[j]
        d = haversine_km(coords[a], coords[b])
        mode = 'Road' if d < 150 else rng.choices(['Road', 'Sea', 'Air'], [0.5, 0.2, 0.3])[0]
        speed, rate = MODE_SPECS[mode]
        hours = d / speed + rng.uniform(0.5, 3.0)
        cost = d * rate * rng.uniform(0.8, 1.2) + 5
        risk = rng.randint(1, 4)
        for u, v in ((a, b), (b, a)):
            legs += 1
            graph[u].append({'leg_id': f'X{legs}', 'from_node': u, 'to_node': v, 'mode': mode,
                             'transit_hours_typical': hours, 'transit_hours_p90': hours * 1.2,
                             'cost_usd_per_tonne': cost, 'risk_score_1to5': risk,
                             'capacity_tonnes_per_week': 1e9})
    return graph, coords


def synthetic_network(graph):
    net = HumanitarianNetwork()
    for es in graph.values():
        for e in es:
            net.add_leg(e['from_node'], e['to_node'], e['transit_hours_typical'],
                        e['cost_usd_per_tonne'], e['risk_score_1to5'], e['capacity_tonnes_per_week'])
    return net


def scaling_study(sizes, graphs_per_size, queries_per_graph, repeats):
    rows = []
    for n in sizes:
        for g in range(graphs_per_size):
            graph, coords = synthetic_graph(n, seed=1000 * n + g)
            net = synthetic_network(graph)
            rng = random.Random(7000 * n + g)
            ids = list(graph)
            for _ in range(queries_per_graph):
                start, goal = rng.sample(ids, 2)
                for obj in ('time', 'cost'):
                    d_res, heap = count_dijkstra(net, start, goal, obj, 1, False)
                    a = astar(graph, coords, start, goal, obj)
                    z = astar(graph, coords, start, goal, obj, heuristic='zero')
                    d_cost = dijkstra_cost(d_res, obj)
                    rows.append({
                        'nodes': n, 'graph_seed': g, 'objective': obj, 'start': start, 'goal': goal,
                        'agree': same_cost(d_res['path'] is not None, d_cost, a.found, a.cost),
                        'dijkstra_expansions': heap.pops, 'astar_expansions': a.nodes_expanded,
                        'astar_h0_expansions': z.nodes_expanded,
                        'dijkstra_ms': median_ms(lambda: run_dijkstra(net, start, goal, obj, 1, False), repeats),
                        'astar_ms': median_ms(lambda: astar(graph, coords, start, goal, obj), repeats),
                        'astar_h0_ms': median_ms(lambda: astar(graph, coords, start, goal, obj, heuristic='zero'), repeats),
                    })
    return rows


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def summarise_core(rows):
    found = [r for r in rows if r['dijkstra_found'] and r['astar_found']]
    out = {
        'queries': len(rows),
        'both_found': len(found),
        'neither_found': sum(1 for r in rows if not r['dijkstra_found'] and not r['astar_found']),
        'dijkstra_astar_agree': sum(r['agree_dijkstra_astar'] for r in rows),
        'astar_vs_h0_agree': sum(r['agree_astar_h0'] for r in rows),
        'same_route': sum(r['same_route'] for r in rows),
    }
    for obj in ('time', 'cost'):
        sub = [r for r in found if r['objective'] == obj]
        entry = {}
        for key, label in (('dijkstra_expansions', 'dijkstra'), ('astar_expansions', 'astar'),
                           ('astar_h0_expansions', 'astar_h0')):
            m, s = mean_sd(r[key] for r in sub)
            entry[label] = {'mean_expansions': round(m, 2), 'sd': round(s, 2)}
        for key, label in (('dijkstra_ms', 'dijkstra'), ('astar_ms', 'astar'), ('astar_h0_ms', 'astar_h0')):
            m, s = mean_sd(r[key] for r in sub)
            entry[label]['mean_ms'] = round(m, 4)
            entry[label]['sd_ms'] = round(s, 4)
        entry['queries'] = len(sub)
        entry['astar_reduction_vs_dijkstra_pct'] = round(
            100 * (1 - statistics.mean(r['astar_expansions'] for r in sub)
                   / statistics.mean(r['dijkstra_expansions'] for r in sub)), 1)
        out[obj] = entry
    return out


def summarise_scaling(rows):
    out = []
    for n in sorted({r['nodes'] for r in rows}):
        for obj in ('time', 'cost'):
            sub = [r for r in rows if r['nodes'] == n and r['objective'] == obj]
            entry = {'nodes': n, 'objective': obj, 'queries': len(sub),
                     'all_agree': all(r['agree'] for r in sub)}
            for key, label in (('dijkstra_expansions', 'dijkstra'), ('astar_expansions', 'astar'),
                               ('astar_h0_expansions', 'astar_h0')):
                m, s = mean_sd(r[key] for r in sub)
                entry[f'{label}_mean_exp'] = round(m, 1)
                entry[f'{label}_sd_exp'] = round(s, 1)
            for key, label in (('dijkstra_ms', 'dijkstra'), ('astar_ms', 'astar'), ('astar_h0_ms', 'astar_h0')):
                m, s = mean_sd(r[key] for r in sub)
                entry[f'{label}_mean_ms'] = round(m, 3)
                entry[f'{label}_sd_ms'] = round(s, 3)
            entry['astar_reduction_pct'] = round(
                100 * (1 - entry['astar_mean_exp'] / entry['dijkstra_mean_exp']), 1)
            out.append(entry)
    return out


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

BLUE, ORANGE, AQUA = '#2a78d6', '#eb6834', '#1baf7a'     # validated categorical slots 1-3
INK, INK2, MUTED, GRID = '#0b0b0b', '#52514e', '#898781', '#e1e0d9'


def _style(ax, xlabel=None, ylabel=None, title=None):
    ax.set_facecolor('white')
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color('#c3c2b7')
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis='y', color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=10)
    if title:
        ax.set_title(title, color=INK, fontsize=11, loc='left', fontweight='bold')


def make_charts(core, scaling_summary, heur, impact):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    plt.rcParams['font.family'] = 'DejaVu Sans'
    RESULTS.mkdir(exist_ok=True)

    # 1. Real network: expansions per scenario (fastest route to El Obeid, 1 tonne)
    fig, ax = plt.subplots(figsize=(8, 4), dpi=160, facecolor='white')
    rows = [r for r in core if r['destination'] == 'ELO' and r['objective'] == 'time'
            and r['tonnes'] == 1 and not r['risk5_allowed']]
    x = list(range(len(rows)))
    w = 0.27
    ax.bar([i - w for i in x], [r['dijkstra_expansions'] for r in rows], w, color=BLUE, label='Dijkstra (Person 2)')
    ax.bar(x, [r['astar_h0_expansions'] for r in rows], w, color=AQUA, label='A* with h = 0')
    ax.bar([i + w for i in x], [r['astar_expansions'] for r in rows], w, color=ORANGE, label='A* straight-line')
    ax.set_xticks(x)
    ax.set_xticklabels([r['scenario'] for r in rows])
    _style(ax, 'Disruption scenario', 'Nodes expanded', 'Fastest route to El Obeid, 1 tonne: nodes expanded')
    ax.legend(frameon=False, fontsize=9, ncol=3, loc='upper center', bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    fig.savefig(RESULTS / 'fig1_real_network_expansions.png', facecolor='white')
    plt.close(fig)

    # 2 + 3. Scaling: expansions and runtime vs network size
    for obj in ('time', 'cost'):
        sub = [r for r in scaling_summary if r['objective'] == obj]
        ns = [r['nodes'] for r in sub]
        for metric, ylabel, fname, title in (
                ('exp', 'Nodes expanded (mean, error bars = 1 sd)', f'fig2_scaling_expansions_{obj}.png',
                 f'Nodes expanded vs network size ({obj} objective)'),
                ('ms', 'Search time, ms (mean, error bars = 1 sd)', f'fig3_scaling_runtime_{obj}.png',
                 f'Search time vs network size ({obj} objective)')):
            fig, ax = plt.subplots(figsize=(7, 4), dpi=160, facecolor='white')
            for label, key, colour, name in (('dijkstra', 'dijkstra', BLUE, 'Dijkstra (Person 2)'),
                                             ('astar_h0', 'astar_h0', AQUA, 'A* with h = 0'),
                                             ('astar', 'astar', ORANGE, 'A* straight-line')):
                ys = [r[f'{key}_mean_{metric}'] for r in sub]
                es = [r[f'{key}_sd_{metric}'] for r in sub]
                ax.errorbar(ns, ys, yerr=es, color=colour, marker='o', markersize=5, linewidth=2,
                            capsize=3, label=name)
            ax.set_xscale('log')
            ax.set_yscale('log')
            ax.set_xticks(ns)
            ax.set_xticklabels([str(n) for n in ns])
            ax.minorticks_off()
            _style(ax, 'Locations in network (log scale)', ylabel, title)
            ax.legend(frameon=False, fontsize=9, loc='upper left')
            fig.tight_layout()
            fig.savefig(RESULTS / fname, facecolor='white')
            plt.close(fig)

    # 4. Heuristic study
    fig, ax = plt.subplots(figsize=(8, 4), dpi=160, facecolor='white')
    names = [r['method'] for r in heur]
    ax.barh(range(len(heur)), [r['mean_expansions'] for r in heur], color=BLUE, height=0.55)
    ax.set_yticks(range(len(heur)))
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    for i, r in enumerate(heur):
        ax.text(r['mean_expansions'] + 0.15, i, f"{r['mean_expansions']:.1f}   (cost x{r['mean_cost_ratio']:.3f})",
                va='center', fontsize=8.5, color=INK2)
    _style(ax, 'Mean nodes expanded (real network, 10 scenarios, 4 destinations, 2 objectives)', None,
           'Effect of the heuristic on search effort and route cost')
    ax.grid(axis='y', visible=False)
    ax.grid(axis='x', color=GRID, linewidth=0.8)
    ax.set_xlim(0, max(r['mean_expansions'] for r in heur) * 1.35)
    fig.tight_layout()
    fig.savefig(RESULTS / 'fig4_heuristics.png', facecolor='white')
    plt.close(fig)

    # 5. Disruption impact on the fastest route
    fig, ax = plt.subplots(figsize=(8, 4), dpi=160, facecolor='white')
    xs = list(range(len(impact)))
    vals = [r['fastest_hours'] if r['fastest_hours'] is not None else 0 for r in impact]
    ax.bar(xs, vals, 0.6, color=BLUE)
    for i, r in enumerate(impact):
        ax.text(i, vals[i] + 1.5, f"{vals[i]:.0f}", ha='center', fontsize=8.5, color=INK2)
    ax.set_xticks(xs)
    ax.set_xticklabels([r['scenario'] for r in impact])
    _style(ax, 'Disruption scenario', 'Fastest route to El Obeid (hours)', 'Disruption impact on the fastest route (1 tonne)')
    fig.tight_layout()
    fig.savefig(RESULTS / 'fig5_disruption_impact.png', facecolor='white')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quick', action='store_true', help='fewer repeats and smaller scaling study')
    args = parser.parse_args()
    repeats = 5 if args.quick else 30
    sizes = (25, 50, 100, 200) if args.quick else (25, 50, 100, 200, 400, 800)
    graphs, queries = (5, 3) if args.quick else (20, 5)

    data = load_workbook(DEFAULT_WORKBOOK)
    validate(data)
    RESULTS.mkdir(exist_ok=True)
    summary = {}

    print('1/7 real network: agreement and search effort ...')
    core = core_grid(data, repeats)
    write_csv('exp1_core_grid.csv', core)
    summary['exp1_core'] = summarise_core(core)

    print('2/7 cold-chain 72 h limit ...')
    cold = cold_chain_grid(data)
    write_csv('exp2_cold_chain.csv', cold)
    summary['exp2_cold_chain'] = {
        'queries': len(cold),
        'agree': sum(r['agree'] for r in cold),
        'dijkstra_feasible': sum(r['dijkstra_found'] for r in cold),
        'astar_feasible': sum(r['astar_found'] for r in cold),
        'feasible_destinations': sorted({r['destination'] for r in cold if r['astar_found']}),
        'infeasible_to_ELO': all(not r['astar_found'] for r in cold if r['destination'] == 'ELO'),
    }

    print('3/7 risk objective definitions ...')
    risk = risk_comparison(data)
    write_csv('exp3_risk_objective.csv', risk)
    summary['exp3_risk_routes_identical'] = sum(r['same_route'] for r in risk)

    print('4/7 heuristic study ...')
    heur = heuristic_study(data)
    write_csv('exp4_heuristics.csv', heur)
    summary['exp4_heuristics'] = heur

    print('5/7 disruption impact ...')
    impact = disruption_impact(data)
    write_csv('exp5_disruption_impact.csv', impact)

    print('6/7 heuristic admissibility and consistency ...')
    summary['exp6_heuristic_checks'] = heuristic_checks(data)

    print('7/7 scaling on synthetic networks ...')
    scaling = scaling_study(sizes, graphs, queries, 3)
    write_csv('exp7_scaling_raw.csv', scaling)
    scaling_summary = summarise_scaling(scaling)
    write_csv('exp7_scaling_summary.csv', scaling_summary)
    summary['exp7_scaling'] = scaling_summary
    summary['settings'] = {'timing_repeats_real': repeats, 'scaling_sizes': list(sizes),
                           'graphs_per_size': graphs, 'queries_per_graph': queries,
                           'real_network': {'locations': len(data['locations']),
                                            'legs': len(data['network_legs'])}}

    with open(RESULTS / 'summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    make_charts(core, scaling_summary, heur, impact)
    print('Done. Results in', RESULTS)


if __name__ == '__main__':
    main()
