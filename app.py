import streamlit as st
import pandas as pd
from interface.map import display_map
from algorithms.dijkstra import HumanitarianNetwork
from algorithms.astar import astar, node_coordinates, lowest_risk_route
from member1 import member1_data 
# Page configuration
st.set_page_config(
    page_title = "Dubai Humanitarian Route Planner",
    page_icon = "🗺️",
    layout = "wide",
)

#Application Heading
st.title("🗺️ Dubai Humanitarian Route Planner")
st.write(
    "Humanitarian cargo route planning "
    "from Dubai to Sudan"
)
st.info(
    "Educational purposes only."
    "All network information and travel estimates are hypothetical."
)

#Sidebar
st.sidebar.title("Shipment Configuration")

#Shipment settings
algorithm = st.sidebar.selectbox(
    "Route Finding Algorithm",
    ["Dijkstra", "A*"]
)
destination = st.sidebar.selectbox(
    "Destination",
    ["El Obeid", "Port Sudan"]
)
cargo = st.sidebar.selectbox(
    "Cargo Type",
    ["Medical Supplies", "Cold Chain", "Bulk Food"]
)
cargo_weight = st.sidebar.number_input(
    "Shipment weight (tons)",
    min_value = 1.0,
    max_value = 1000.0,
    value = 10.0,
    step = 1.0
)
risk_override = st.sidebar.checkbox(
    "Allow high-risk routes (Risk 5)",
    value = False
)
is_cold_chain = cargo == "Cold Chain"
objective = st.sidebar.selectbox(
    "Optimization Objective",
    ["Fastest", "Cheapest", "Lowest Risk"]
)
objective_mapping = {
    "Fastest" : "time",
    "Cheapest" : "cost",
    "Lowest Risk" : "risk"
}
selected_objective = objective_mapping[objective]
destination_mapping = {
    "El Obeid" : "ELO",
    "Port Sudan" : "PSD_PORT"
}
selected_destination = destination_mapping[destination]

# Load and validate member 1's data
data_path = "member1/data/hrp_network_data.xlsx"
data = member1_data.load_workbook(data_path)
validation = member1_data.validate(data)
scenario = st.sidebar.selectbox(
    "Disruption scenario",
    [
        "S0 - No Disruption",
        "S1 - Port Sudan Airport Closed",
        "S2 - Red Sea Transit Suspended",
        "S3 - Metema Crossing Closed",
        "S4 - Omdurman Road Blocked",
        "S5 - El Obeid Airport Closed",
        "S6 - Rainy Season",
        "S7 - Argeen Congestion",
        "S8 - Insurance Spike",
        "S9 - Compound Disruption"
    ]
)
selected_scenario = scenario.split(" - ")[0]
#Track shipment settings to detect changes
current_settings = (
    algorithm,
    destination,
    cargo,
    cargo_weight,
    risk_override,
    objective,
    selected_scenario
)
if "previous_settings" not in st.session_state:
    st.session_state.previous_settings = current_settings
elif st.session_state.previous_settings != current_settings:
    st.session_state.route_result = None
    st.session_state.selected_path = None
    st.session_state.result_algorithm = None
    st.session_state.previous_settings = current_settings

# Prepare edges based on member 1's data and the selected scenario
edges = member1_data.prepare_edges(
    data,
    scenario_id = selected_scenario,
    shipment_tonnes = cargo_weight,
    allow_risk5 = risk_override
)
# Prepare the graph and coordinates for A*
astar_graph = member1_data.adjacency(data,edges)
coordinates = node_coordinates(data)
# Convert member 1's network into member 2's format
network = HumanitarianNetwork()
for edge in edges:
    network.add_leg(
        edge["from_node"],
        edge["to_node"],
        edge["transit_hours_typical"],
        edge["cost_usd_per_tonne"],
        edge["risk_score_1to5"],
        edge["capacity_tonnes_per_week"]
    )
if "selected_path" not in st.session_state:
    st.session_state.selected_path = None
if "route_result" not in st.session_state:
    st.session_state.route_result = None
if "result_algorithm" not in st.session_state:
    st.session_state.result_algorithm = None

# Calculate button
if st.sidebar.button("Calculate Route"):
    if algorithm == "Dijkstra":
        result = network.dijkstra(
            start = "IHC",
            goal = selected_destination,
            objective = selected_objective,
            cargo_weight = cargo_weight,
            is_cold_chain = is_cold_chain,
            risk_override = risk_override
        )
        st.session_state.route_result = result
        st.session_state.selected_path = result["path"]
        st.session_state.result_algorithm = algorithm
    else:
        if selected_objective == "risk":
            astar_result = lowest_risk_route(
                astar_graph,
                coordinates,
                "IHC",
                selected_destination,
                max_hours = 72 if is_cold_chain else None 
            )
        else:
            astar_result = astar(
                astar_graph,
                coordinates,
                "IHC",
                selected_destination,
                objective = selected_objective,
                max_hours = 72 if is_cold_chain else None
            )
        st.session_state.route_result = astar_result
        st.session_state.selected_path = astar_result.path
        st.session_state.result_algorithm = algorithm

# Display saved route results
if st.session_state.route_result is not None:
    result = st.session_state.route_result
    if st.session_state.result_algorithm == "Dijkstra":
        if result["path"] is not None:
            st.success("Route found!")
            st.write("Destination:", destination)
            st.write("Cargo:", cargo)
            st.write("Algorithm:", algorithm)
            st.write("Objective:", objective)
            st.write("Scenario:", scenario)
            st.write("Selected route:")
            st.write(" → ".join(result["path"]))
            # Calculate metrics for the selected route
            route_legs = []
            for i in range(len(result["path"]) - 1):
                start_node = result["path"] [i]
                end_node = result["path"][i + 1]
                matching_edges = [
                    edge for edge in edges
                    if edge["from_node"] == start_node
                    and edge["to_node"] == end_node
                ]
                if matching_edges:
                    route_legs.append(matching_edges[0])
            total_time = sum(
                edge["transit_hours_typical"] for edge in route_legs
            )
            total_cost = sum(
                edge["cost_usd_per_tonne"] for edge in route_legs
            )
            total_risk = sum(
                edge["risk_score_1to5"] for edge in route_legs
            )
            maximum_risk = max(
                edge["risk_score_1to5"] for edge in route_legs
            )
            # Display metrics
            st.write("Total travel time:", round(total_time, 2), "hours")
            st.write("Total cost:", round(total_cost, 2), "USD per tonne")
            st.write("Maximum risk level:", maximum_risk)
            st.write("Total risk score:", total_risk)
        else:
            st.error(result["status"])
    else:
        if result.found:
            st.success("Route found!")
            st.write("Destination:", destination)
            st.write("Cargo:", cargo)
            st.write("Algorithm:", algorithm)
            st.write("Objective:", objective)
            st.write("Scenario:", scenario)
            st.write("Selected route:")
            st.write(" → ".join(result.path))
            st.write("Total travel time:", result.total_hours, "hours")
            st.write("Total cost:", result.total_cost_usd_per_tonne, "USD per tonne")
            st.write("Maximum risk level:", result.max_risk)
        else:
            st.error(result.reason)
#Main page
st.subheader("Transport Network")
display_map(
    locations = pd.DataFrame(data["locations"]),
    connections = pd.DataFrame(edges),
    highlighted_path = st.session_state.selected_path
)