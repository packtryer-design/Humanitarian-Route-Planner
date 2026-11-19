"""Humanitarian Route Planner data preparation. Educational purposes only.

Run: python member1_data.py --workbook data/hrp_network_data.xlsx
No routing algorithm is implemented here; Members 2 and 3 consume adjacency().
"""
import argparse
import copy
import csv
import json
import math
from collections import Counter
from pathlib import Path
import openpyxl

NUMERIC = ('distance_km', 'transit_hours_typical', 'transit_hours_p90',
           'cost_usd_per_tonne', 'capacity_tonnes_per_week')

def load_workbook(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    result = {}
    try:
        for name in ('locations', 'network_legs', 'disruption_scenarios'):
            rows = list(wb[name].values)
            result[name] = [dict(zip(rows[0], r)) for r in rows[1:] if any(v is not None for v in r)]
    finally:
        wb.close()
    return result

def number(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'{label}: expected a finite number')
    if value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f'{label}: outside allowed range')

def unique(rows, key):
    values = [r[key] for r in rows]
    if any(not isinstance(v, str) or not v.strip() for v in values) or len(values) != len(set(values)):
        raise ValueError(f'{key}: missing or duplicate ID')
    return set(values)

def validate(data):
    nodes, edges, scenarios = (data[k] for k in ('locations','network_legs','disruption_scenarios'))
    ids = unique(nodes, 'node_id')
    leg_ids = unique(edges, 'leg_id')
    locations = {r['node_id']: r for r in nodes}
    for r in nodes:
        for k in ('name','node_type','country'):
            if not r.get(k): raise ValueError(f'{r["node_id"]}: missing {k}')
        number(r['lat'], 'latitude', -90, 90)
        number(r['lon'], 'longitude', -180, 180)
    for r in edges:
        label = r['leg_id']
        for side in ('from','to'):
            if r[f'{side}_node'] not in ids: raise ValueError(f'{label}: unknown endpoint')
            node = locations[r[f'{side}_node']]
            for field in ('name','country','lat','lon'):
                if r[f'{side}_{field}'] != node[field]: raise ValueError(f'{label}: inconsistent endpoint {field}')
            if r[f'{side}_type'] != node['node_type']: raise ValueError(f'{label}: inconsistent endpoint type')
        for k in NUMERIC: number(r[k], f'{label} {k}')
        number(r['risk_score_1to5'], label+' risk', 1, 5)
        if int(r['risk_score_1to5']) != r['risk_score_1to5']: raise ValueError('Risk must be an integer')
        number(r['reliability_pct'], label+' reliability', 0, 100)
        if r['transit_hours_p90'] < r['transit_hours_typical']: raise ValueError(label+': P90 below typical')
        if r['mode'] not in ('Air','Sea','Road','Road (transfer)'): raise ValueError(label+': unknown mode')
        if r['restriction_frequency'] not in ('Rare','Occasional','Frequent'): raise ValueError(label+': unknown restriction')
    outgoing, incoming = Counter(r['from_node'] for r in edges), Counter(r['to_node'] for r in edges)
    for r in nodes:
        if r['legs_out'] != outgoing[r['node_id']] or r['legs_in'] != incoming[r['node_id']]:
            raise ValueError(r['node_id']+': incorrect degree count')
    scenario_ids = {r['scenario_id'] for r in scenarios}
    if scenario_ids != {f'S{i}' for i in range(10)}: raise ValueError('Expected S0 through S9')
    for r in scenarios:
        if r['scenario_id'] == 'S0':
            if r['action'] is not None: raise ValueError('Baseline must have no action')
        elif r['action'] == 'COMBINE':
            refs = str(r['value']).split(';')
            if any(ref not in scenario_ids for ref in refs): raise ValueError('Unknown combined scenario')
        else:
            if r['leg_id'] not in leg_ids: raise ValueError('Unknown scenario leg')
            if r['action'] not in ('CLOSE','TIME_MULT','COST_MULT'): raise ValueError('Unknown action')
            if r['action'].endswith('_MULT'): number(float(r['value']), 'multiplier', 0)
    for sid in scenario_ids: scenario_actions(data, sid)
    return {'locations':len(nodes), 'directed_legs':len(edges), 'scenario_cases':len(scenario_ids),
            'scenario_action_rows':len(scenarios), 'risk_5_legs':[r['leg_id'] for r in edges if r['risk_score_1to5']==5],
            'status':'PASS', 'scope':'Structural and range validation; not operational verification'}

def scenario_actions(data, scenario_id, stack=()):
    if scenario_id in stack: raise ValueError('Cyclic scenario combination')
    rows = [r for r in data['disruption_scenarios'] if r['scenario_id'] == scenario_id]
    if not rows: raise ValueError('Unknown scenario '+scenario_id)
    result = []
    for r in rows:
        if r['action'] == 'COMBINE':
            for ref in str(r['value']).split(';'):
                result.extend(scenario_actions(data, ref, stack+(scenario_id,)))
        elif r['action'] is not None: result.append(r)
    return result

def prepare_edges(data, scenario_id='S0', shipment_tonnes=1, allow_risk5=False):
    """Return a fresh scenario graph; capacity assumes available weekly capacity.

    TIME_MULT scales both time columns as a documented prototype assumption.
    The whole-route cold-chain time limit must be enforced by the route solver.
    """
    number(shipment_tonnes, 'shipment tonnes')
    if shipment_tonnes <= 0: raise ValueError('Shipment must be positive')
    edges = copy.deepcopy(data['network_legs'])
    lookup = {r['leg_id']:r for r in edges}
    closed = set()
    for action in scenario_actions(data, scenario_id):
        leg = lookup[action['leg_id']]
        if action['action'] == 'CLOSE': closed.add(leg['leg_id'])
        elif action['action'] == 'TIME_MULT':
            for field in ('transit_hours_typical','transit_hours_p90'): leg[field] *= float(action['value'])
        elif action['action'] == 'COST_MULT': leg['cost_usd_per_tonne'] *= float(action['value'])
    return [r for r in edges if r['leg_id'] not in closed
            and (allow_risk5 or r['risk_score_1to5'] < 5)
            and r['capacity_tonnes_per_week'] >= shipment_tonnes]

def adjacency(data, edges):
    """Directed outgoing edges, including empty lists for sink locations."""
    graph = {r['node_id']:[] for r in data['locations']}
    for r in edges: graph[r['from_node']].append(r)
    return graph

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workbook', default=str(Path(__file__).parent/'data/hrp_network_data.xlsx'))
    p.add_argument('--output', default=str(Path(__file__).parent/'generated'))
    args = p.parse_args()
    data = load_workbook(args.workbook)
    summary = validate(data)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    for name, rows in data.items():
        with (out/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    summary['scenario_active_legs_1_tonne_no_risk5'] = {
        f'S{i}':len(prepare_edges(data,f'S{i}')) for i in range(10)}
    (out/'network.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    (out/'validation_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))

if __name__ == '__main__': main()
