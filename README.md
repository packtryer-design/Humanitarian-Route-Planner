# Humanitarian-Route-Planner
Humanitarian Route Planner: Comparing Dijkstra and A* for Multimodal Aid Routing from Dubai Humanitarian

## 1. Technologies Used

- Python — Main programming language
- Streamlit — Web application interface
- Pandas — CSV data processing
- Folium — Interactive map
- GitHub — Version control and collaboration

## 2. Project Structure
```
Humanitarian Route Planner/
├── app.py
├── requirements.txt
├── algorithms/
│   ├── dijkstra.py
│   └── astar.py
├── data/
│   ├── nodes.csv
│   └── connections.csv
├── experiments/
│   └── scenarios.py
└── interface/
    ├── map.py
    └── display.py
```
## 3. Current Network

The prototype currently contains:
- **18 locations (nodes)**
- **26 directed connections (edges)**

The locations cover Dubai, Jeddah, Port Sudan, Djibouti, Ethiopia, Egypt and Sudanese transfer points.
The project brief requires 23 nodes and 36 directed connections. Five nodes and ten connections are still outstanding.
**Important:** Some connections are provisional assumptions because the brief does not provide all the required network details. The coordinates are approximate.

## 4. Implemented Features

### Interface and Map
- Streamlit application with shipment configuration.
- Interactive Folium map.
- Location markers with names and categories.
- Different line colours for air, sea and road.
- Automatic map zoom.
- Corridor selection: Direct Air, Saudi, Ethiopian, Egyptian and All Corridors.
- Corridor filtering and overview metrics.

### Algorithms and Scenarios
The project structure includes files for Dijkstra, A*, and disruption scenarios. These still need to be completed and integrated with the interface.

## 5. How to Run

Install dependencies:

```
pip install -r requirements.txt
```

Run the application:

```
streamlit run app.py
```

## 6. Important Notes

- Connections represent directed routes.
- Map lines are straight visual representations, not actual road or flight paths.
- Provisional connections must be verified before final calculations.
- All network information and estimates are for educational purposes only.
