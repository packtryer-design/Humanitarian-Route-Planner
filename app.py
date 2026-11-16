import streamlit as st
import pandas as pd
from interface.map import display_map
from algorithms.dijkstra import HumanitarianNetwork
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
    "El Obeid" : "N07",
    "Port Sudan" : "N06"
}
selected_destination = destination_mapping[destination]

# Create humanitarian network
network = HumanitarianNetwork()
nodes = pd.read_csv("data/nodes.csv")
connections = pd.read_csv("data/connections.csv")
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

#Calculate button
if st.sidebar.button("Calculate Route"):
    st.success("Shipment configuration selected!")
    st.write("Destination:", destination)
    st.write("Cargo:", cargo)
    st.write("Objective:", objective)
    st.write("Scenario:", scenario)

#Main page
st.subheader("Transport Network")
display_map()
st.warning(
    "Route calculation will be connected "
    "to the Dijkstra and A* algorithms later."
)