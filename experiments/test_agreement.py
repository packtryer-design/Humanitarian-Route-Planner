"""Automated tests comparing Dijkstra (Person 2) and A* (Person 3). Run from repo root:
    python -m unittest experiments.test_agreement -v   (or: python experiments/test_agreement.py)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_experiments as ex  # noqa: E402
from run_experiments import (ORIGIN, SCENARIOS, adjacency, astar, build_network, load_workbook,
                             node_coordinates, prepare_edges, run_dijkstra, destinations)
from algorithms.astar import DEFAULT_WORKBOOK


class Agreement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_workbook(DEFAULT_WORKBOOK)
        cls.coords = node_coordinates(cls.data)

    def setup(self, sid, tonnes=1, risk5=False):
        edges = prepare_edges(self.data, sid, tonnes, risk5)
        return edges, adjacency(self.data, edges), build_network(edges)

    def test_same_optimal_cost_everywhere(self):
        rows = ex.core_grid(self.data, repeats=1)
        self.assertEqual(len(rows), 480)
        bad = [r for r in rows if not r['agree_dijkstra_astar'] or not r['agree_astar_h0']]
        self.assertEqual(bad, [])

    def test_heuristic_admissible_and_consistent(self):
        res = ex.heuristic_checks(self.data)
        self.assertEqual(res['not_admissible'], 0)
        self.assertEqual(res['not_consistent'], 0)

    def test_impossible_capacity(self):
        edges, graph, net = self.setup('S0', tonnes=1e7)
        d = run_dijkstra(net, ORIGIN, 'ELO', 'time', 1e7, False)
        a = astar(graph, self.coords, ORIGIN, 'ELO', 'time')
        self.assertIsNone(d['path'])
        self.assertFalse(a.found)

    def test_closed_legs_not_used(self):
        edges, graph, net = self.setup('S1')
        ids = {e['leg_id'] for e in edges}
        a = astar(graph, self.coords, ORIGIN, 'ELO', 'time')
        used = {leg['leg_id'] for leg in a.legs}
        self.assertTrue(used <= ids)
        for closed in ('L04', 'L05', 'L10', 'L11', 'L12', 'L27'):
            self.assertNotIn(closed, ids)

    def test_cold_chain_agreement(self):
        rows = ex.cold_chain_grid(self.data)
        self.assertTrue(all(r['agree'] for r in rows))
        for r in rows:
            if r['astar_found']:
                self.assertLessEqual(r['astar_hours'], 72 + 1e-9)

    def test_synthetic_agreement(self):
        rows = ex.scaling_study((25, 50), 3, 3, 1)
        self.assertTrue(all(r['agree'] for r in rows))

    def test_weighted_astar_never_cheaper_than_optimal(self):
        for sid in SCENARIOS:
            _, graph, _ = self.setup(sid)
            for dest in destinations(self.data):
                best = astar(graph, self.coords, ORIGIN, dest, 'cost')
                w = astar(graph, self.coords, ORIGIN, dest, 'cost', epsilon=3)
                self.assertGreaterEqual(w.cost + 1e-9, best.cost)


if __name__ == '__main__':
    unittest.main(verbosity=2)
