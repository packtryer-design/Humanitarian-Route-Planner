"""Run with python -m unittest -v. Tests exercise data failures and scenario behaviour."""
import copy
import unittest
from pathlib import Path
from member1_data import load_workbook, validate, prepare_edges, adjacency, scenario_actions

class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=load_workbook(Path(__file__).parent/'data/hrp_network_data.xlsx')
    def test_supplied_data(self):
        self.assertEqual(validate(self.data)['directed_legs'],36)
    def reject(self, change):
        d=copy.deepcopy(self.data); change(d)
        with self.assertRaises(ValueError): validate(d)
    def test_duplicate_node(self): self.reject(lambda d:d['locations'].append(d['locations'][0]))
    def test_unknown_endpoint(self): self.reject(lambda d:d['network_legs'][0].update(to_node='UNKNOWN'))
    def test_negative_cost(self): self.reject(lambda d:d['network_legs'][0].update(cost_usd_per_tonne=-1))
    def test_missing_time(self): self.reject(lambda d:d['network_legs'][0].update(transit_hours_typical=None))
    def test_invalid_risk(self): self.reject(lambda d:d['network_legs'][0].update(risk_score_1to5=6))
    def test_inconsistent_coordinates(self): self.reject(lambda d:d['network_legs'][0].update(from_lat=0))
    def test_invalid_p90(self): self.reject(lambda d:d['network_legs'][0].update(transit_hours_p90=0))
    def test_unknown_scenario_leg(self): self.reject(lambda d:d['disruption_scenarios'][1].update(leg_id='BAD'))
    def test_combination_cycle(self):
        self.reject(lambda d:d['disruption_scenarios'][-1].update(value='S9'))
    def test_risk_override(self):
        self.assertEqual(len(prepare_edges(self.data)),33)
        self.assertEqual(len(prepare_edges(self.data,allow_risk5=True)),36)
    def test_capacity_filter(self):
        self.assertTrue(all(r['capacity_tonnes_per_week']>=500 for r in prepare_edges(self.data,shipment_tonnes=500)))
        self.assertEqual(prepare_edges(self.data,shipment_tonnes=99999),[])
    def test_closures(self):
        closed={r['leg_id'] for r in scenario_actions(self.data,'S1')}
        self.assertFalse(closed & {r['leg_id'] for r in prepare_edges(self.data,'S1',allow_risk5=True)})
    def test_time_and_cost_multipliers(self):
        original={r['leg_id']:r for r in self.data['network_legs']}
        rainy={r['leg_id']:r for r in prepare_edges(self.data,'S6')}
        insurance={r['leg_id']:r for r in prepare_edges(self.data,'S8')}
        self.assertAlmostEqual(rainy['L25']['transit_hours_p90'],original['L25']['transit_hours_p90']*1.6)
        self.assertAlmostEqual(insurance['L14']['cost_usd_per_tonne'],original['L14']['cost_usd_per_tonne']*1.8)
    def test_compound_and_baseline_unchanged(self):
        before=copy.deepcopy(self.data)
        combined={r['leg_id'] for r in scenario_actions(self.data,'S9')}
        expected={r['leg_id'] for sid in ('S1','S2') for r in scenario_actions(self.data,sid)}
        self.assertEqual(combined,expected)
        prepare_edges(self.data,'S6'); prepare_edges(self.data,'S8'); prepare_edges(self.data,'S9')
        self.assertEqual(self.data,before)
    def test_direction_and_destination(self):
        g=adjacency(self.data,prepare_edges(self.data))
        self.assertEqual(g['ELO'],[])
        self.assertEqual({r['to_node'] for r in g['IHC']},{'DWC','DXB','JEA'})
    def test_bad_request(self):
        with self.assertRaises(ValueError): prepare_edges(self.data,shipment_tonnes=0)
        with self.assertRaises(ValueError): prepare_edges(self.data,'S99')

if __name__=='__main__': unittest.main()
