
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


def display_map(locations, connections, highlighted_path=None):

    # Load location and connection data
    nodes = locations.copy()
    all_connections = connections.copy()

    # Display all active connections
    selected_connections = all_connections.copy()
    connections = selected_connections
    corridor = "All Corridors"

    # Corridor heading
    st.subheader(f"🌍 {corridor} Route Map")
    st.subheader("Corridor Overview")

    # Identify transport modes
    modes = set(connections["mode"].dropna())
    display_modes = set()
    for mode in modes:
        if "Air" in mode:
            display_modes.add("Air")
        elif "Sea" in mode:
            display_modes.add("Sea")
        elif "Road" in mode:
            display_modes.add("Road")
    mode_order = ["Air", "Road", "Sea"]
    mode_text = ", ".join(
        mode for mode in mode_order if mode in display_modes
    ) if display_modes else "None"

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
        row["node_id"]: [row["lat"], row["lon"]]
        for _, row in nodes.iterrows()
    }

    # Transport colours
    mode_colours = {
        "Air": "#8B78C6",
        "Sea": "#45A6A0",
        "Road": "#D69A62",
        "Road (transfer)": "#D69A62"
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
                    connection["mode"],
                    "gray"
                ),
                weight=2.5,
                opacity=0.75,
                tooltip=(
                    f'{connection["leg_id"]}: '
                    f'{connection["mode"]}'
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
            leg_id = matching_connection.iloc[0]["leg_id"]

            # Draw highlighted route
            folium.PolyLine(
                locations=[
                    node_coordinates[start],
                    node_coordinates[end]
                ],
                color="#E63946",
                weight=6,
                opacity=1,
                tooltip=f"Calculated Route: {leg_id}"
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
                node["lat"],
                node["lon"]
            ],
            tooltip=node["name"],
            popup=f"""
                <b>{node['name']}</b><br>
                node_type: {node['node_type']}
            """,
            icon=folium.Icon(
                color={
                    "Warehouse": "purple",
                    "Airport": "cadetblue",
                    "Seaport": "green",
                    "Destination": "orange",
                    "Border crossing": "red",
                    "Hub" : "darkpurple"
                }.get(node["node_type"], "gray"),
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