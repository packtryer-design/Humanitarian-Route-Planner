# Humanitarian Route Planner data module

All information and data are for educational purposes only.

## Requirements and execution
Use Python 3.10 or newer. From the extracted member1 folder, run:

```bash
python -m pip install -r requirements.txt
python member1_data.py
python -m unittest -v
```

The script reads data/hrp_network_data.xlsx and writes CSV and JSON files to
generated/. It does not modify the supplied workbook.

## Files
- Member1_Report.docx: introduction, requirements, data model, validation and assumptions.
- member1_data.py: loading, validation, scenario preparation and directed adjacency.
- test_member1_data.py: automated data and scenario tests.
- test_results.txt: recorded results from 17 passing tests.
- requirements.txt: Python dependency.
- data/hrp_network_data.xlsx: supplied educational network.
- generated/: CSV exports, network JSON and validation summary.

## Integration
```python
from member1_data import load_workbook, validate, prepare_edges, adjacency

data = load_workbook('data/hrp_network_data.xlsx')
validate(data)
edges = prepare_edges(data, 'S1', shipment_tonnes=10, allow_risk5=False)
graph = adjacency(data, edges)
```

Pass graph to the routing algorithm. Each outgoing edge contains its destination
in to_node and the supplied time, cost and risk fields. Both algorithms should
receive identical data and settings. Each scenario starts from a fresh baseline.

## Model boundaries
Capacity filtering assumes that the supplied weekly capacity is available for
the shipment. TIME_MULT affects both time columns. The route solver must enforce
the whole-route cold-chain limit. The time basis, risk-weighted cost formula and
route risk aggregation require agreement before final integration.
The checks validate the educational data module, not real-world availability or
safety. Dijkstra, A* and the interface are separate components.
