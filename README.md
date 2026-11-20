# Dubai Humanitarian Route Planner

CSCI218 Foundations of AI (Autumn 2026) group project. Compares Dijkstra and A* for routing humanitarian cargo from the Dubai Humanitarian warehouse (IHC) to El Obeid, Sudan (ELO) under ten disruption scenarios.

All information and data are for educational purposes only.

## Contents
| Path | Purpose |
|---|---|
| `app.py` | Streamlit interface (run with `streamlit run app.py`) |
| `interface/map.py` | Folium map of the network and the selected route |
| `algorithms/dijkstra.py` | Dijkstra implementation |
| `algorithms/astar.py` | A* implementation, heuristic, 72-hour label search, cargo rules |
| `member1/` | Data module, network workbook (23 locations, 36 legs), generated files, 17 tests |
| `experiments/run_experiments.py` | Experiments comparing Dijkstra and A* |
| `experiments/test_agreement.py` | Agreement tests (7 tests) |
| `experiments/results/` | CSV tables, `summary.json`, charts and test output |
| `docs/` | Member reports and `Final_Report.docx` |

## Running
Python 3.10 or newer.

```bash
pip install -r requirements.txt
streamlit run app.py
python -m unittest -v                      # inside member1/
python experiments/test_agreement.py       # Dijkstra and A* agreement
python experiments/run_experiments.py      # full run (about 20 s); add --quick for a short run
```
