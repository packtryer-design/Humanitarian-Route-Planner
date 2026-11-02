import streamlit as st
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
objective = st.sidebar.selectbox(
    "Optimization Objective",
    ["Fastest", "Cheapest", "Lowest Risk"]
)
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
st.write(
    "The interactive geographical map "
    "will appear here."
)
st.warning(
    "Route calculation will be connected "
    "to the Dijkstra and A* algorithms later."
)