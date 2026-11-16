
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


def display_map(highlighted_path=None):

    # Load location and connection data
    nodes = pd.read_csv("data/nodes.csv")
    all_connections = pd.read_csv("data/connections.csv")

    # Corridor selection
    st.subheader("Select Humanitarian Corridor")
    corridor = st.selectbox(
        "Choose a corridor to display:",
        [
            "All Corridors",
            "Direct Air",
            "Saudi Corridor",
            "Ethiopian Corridor",
            "Egyptian Corridor"
        ]
    )

    # Connection IDs belonging to each corridor
    corridor_connections = {
        "Direct Air": [
            "C01", "C02", "C04", "C05", "C06", "C07",
            "C18", "C19", "C20", "C21", "C22"
        ],
        "Saudi Corridor": [
            "C01", "C02", "C08", "C09", "C10",
            "C18", "C19", "C20", "C21", "C22",
            "C25", "C26"
        ],
        "Ethiopian Corridor": [
            "C03", "C11", "C12", "C13", "C23",
            "C18", "C19", "C20", "C21", "C22"
        ],
        "Egyptian Corridor": [
            "C01", "C02", "C14", "C15", "C16", "C17",
            "C18", "C19", "C20", "C21", "C22", "C24"
        ]
    }

    # Filter connections for the selected corridor
    if corridor != "All Corridors":
        selected_ids = corridor_connections[corridor]
        connections = all_connections[
            all_connections["connection_id"].isin(selected_ids)
        ].copy()

    else:
        connections = all_connections.copy()

    # Corridor heading
    st.subheader(f"🌍 {corridor} Route Map")
    st.subheader("Corridor Overview")

    # Identify transport modes
    modes = sorted(
        connections["transport_mode"].dropna().unique()
    )
    mode_text = ", ".join(modes) if modes else "None"

    # Display summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Selected Corridor", corridor)
    col2.metric("Connections", len(connections))
    col3.metric("Locations", len(nodes))
    col4.metric("Transport Modes", mode_text)
    st.caption(
        "All network locations remain visible, "
        "while connection lines change according to your selection."
    )

    # Create map
    route_map = folium.Map(
        location=[20, 35],
        zoom_start=4,
        tiles="OpenStreetMap"
    )

    # Location coordinates
    node_coordinates = {
        row["node_id"]: [row["latitude"], row["longitude"]]
        for _, row in nodes.iterrows()
    }

    # Transport colours
    mode_colours = {
        "Air": "#8B78C6",
        "Sea": "#45A6A0",
        "Road": "#D69A62"
    }

    # Draw selected corridor connections
    for _, connection in connections.iterrows():
        start = connection["from_node"]
        end = connection["to_node"]

        if start in node_coordinates and end in node_coordinates:
            folium.PolyLine(
                locations=[
                    node_coordinates[start],
                    node_coordinates[end]
                ],
                color=mode_colours.get(
                    connection["transport_mode"],
                    "gray"
                ),
                weight=2.5,
                opacity=0.75,
                tooltip=(
                    f'{connection["connection_id"]}: '
                    f'{connection["transport_mode"]}'
                )
            ).add_to(route_map)

    # Highlight the calculated route
    missing_segments = []
    if highlighted_path and len(highlighted_path) > 1:
        for i in range(len(highlighted_path) - 1):
            start = highlighted_path[i]
            end = highlighted_path[i + 1]
            # Check that both locations exist
            if start not in node_coordinates or end not in node_coordinates:
                missing_segments.append(f"{start} → {end}")
                continue
            # Check that the connection exists in the network
            matching_connection = all_connections[
                (all_connections["from_node"] == start) &
                (all_connections["to_node"] == end)
            ]
            if matching_connection.empty:
                missing_segments.append(f"{start} → {end}")
                continue
            connection_id = matching_connection.iloc[0]["connection_id"]

            # Draw highlighted route
            folium.PolyLine(
                locations=[
                    node_coordinates[start],
                    node_coordinates[end]
                ],
                color="#E63946",
                weight=6,
                opacity=1,
                tooltip=f"Calculated Route: {connection_id}"
            ).add_to(route_map)

    if missing_segments:
        st.warning(
            "Some calculated route connections could not be found: "
            + ", ".join(missing_segments)
        )

    # Automatically fit all locations
    route_map.fit_bounds(
        list(node_coordinates.values()),
        padding=(30, 30)
    )

    # Add all location markers
    for _, node in nodes.iterrows():
        folium.Marker(
            location=[
                node["latitude"],
                node["longitude"]
            ],
            tooltip=node["node_name"],
            popup=f"""
                <b>{node['node_name']}</b><br>
                Category: {node['category']}
            """,
            icon=folium.Icon(
                color={
                    "Warehouse": "purple",
                    "Airport": "cadetblue",
                    "Port": "green",
                    "City": "orange",
                    "Border Crossing": "red"
                }.get(node["category"], "gray"),
                icon="info-sign"
            )
        ).add_to(route_map)

    # Map legend
    st.markdown("""
    <div style="
        display: flex;
        gap: 25px;
        flex-wrap: wrap;
        padding: 10px;
        background-color: #f8f7fb;
        border-radius: 10px;
        margin-bottom: 10px;
        color: #333333;
    ">
    <span>🟣 <b>Air transport</b></span>
    <span>🟢 <b>Sea transport</b></span>
    <span>🟠 <b>Road transport</b></span>
    <span>🔴 <b>Calculated route</b></span>
    </div>
    """, unsafe_allow_html=True)
    # Display map
    st_folium(
        route_map,
        width=None,
        height=550,
        key="humanitarian_route_map"
    )