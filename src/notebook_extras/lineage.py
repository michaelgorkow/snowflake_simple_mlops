import json
import networkx as nx
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import streamlit as st
import pandas as pd
import streamlit as st
import streamlit as st

class LineageHelper:
    def __init__(self):
        pass

    def visualize_lineage(self, df: pd.DataFrame, short_names: bool = False, initial_zoom: float = 1.0):
        """
        Visualize a lineage graph given a DataFrame with columns:
        - SOURCE_OBJECT (JSON string)
        - TARGET_OBJECT (JSON string)
        - DIRECTION (e.g. "Upstream")
        - DISTANCE (an integer: the number of steps from the ultimate target)
        
        The ultimate target is taken from row 0's TARGET_OBJECT and is assigned distance 0.
        
        Parameters:
        df: pandas DataFrame containing the lineage information.
        short_names: If True, node labels will be shortened (e.g. by taking the last dot‐separated part).
        initial_zoom: A scale factor for the initial zoom level (default 1.0). Values > 1 zoom in;
                        values < 1 zoom out.
        
        Nodes are arranged in vertical columns by distance (with nodes farthest from the target on the left).
        Each node is colored based on its domain, and a legend is added for the node colors.
        """
        # Create an empty directed graph.
        G = nx.DiGraph()

        # Parse the ultimate target from row 0's TARGET_OBJECT and add it with distance 0.
        ultimate_target = json.loads(df.iloc[0]["TARGET_OBJECT"])
        ultimate_target_id = ultimate_target["name"]
        G.add_node(ultimate_target_id, domain=ultimate_target.get("domain", "Unknown"), distance=0)

        # Loop through each row to add nodes and edges.
        # We assume that the "DISTANCE" column applies to the SOURCE_OBJECT.
        for idx, row in df.iterrows():
            # Parse the source object.
            try:
                src_obj = json.loads(row["SOURCE_OBJECT"])
            except Exception as e:
                print(f"Error parsing SOURCE_OBJECT at row {idx}: {e}")
                continue
            src_id = src_obj.get("name")
            src_domain = src_obj.get("domain", "Unknown")
            src_distance = row["DISTANCE"]  # distance from ultimate target

            # Add or update source node with its distance (keeping the smaller distance if node exists).
            if src_id in G.nodes:
                G.nodes[src_id]["distance"] = min(G.nodes[src_id]["distance"], src_distance)
            else:
                G.add_node(src_id, domain=src_domain, distance=src_distance)

            # Parse the target object.
            try:
                tgt_obj = json.loads(row["TARGET_OBJECT"])
            except Exception as e:
                print(f"Error parsing TARGET_OBJECT at row {idx}: {e}")
                continue
            tgt_id = tgt_obj.get("name")
            tgt_domain = tgt_obj.get("domain", "Unknown")
            # For non-ultimate targets we assign distance = (source distance - 1).
            # (This works as long as the lineage chain is consistent.)
            if tgt_id == ultimate_target_id:
                tgt_distance = 0
            else:
                tgt_distance = row["DISTANCE"] - 1

            if tgt_id in G.nodes:
                G.nodes[tgt_id]["distance"] = min(G.nodes[tgt_id]["distance"], tgt_distance)
            else:
                G.add_node(tgt_id, domain=tgt_domain, distance=tgt_distance)

            # Add an edge from source to target (i.e. upstream relationship).
            G.add_edge(src_id, tgt_id)

        # --- Compute layout positions ------------------------------------------------
        # Arrange nodes in vertical columns by distance.
        # Get the maximum distance (farthest from the ultimate target).
        distances = [data["distance"] for _, data in G.nodes(data=True)]
        max_distance = max(distances)

        # Group nodes by their distance value.
        distance_groups = {}  # distance -> list of node ids.
        for node, data in G.nodes(data=True):
            d = data["distance"]
            distance_groups.setdefault(d, []).append(node)

        # Assign positions:
        #   x-coordinate: use max_distance - d so that nodes with highest d appear on the left.
        #   y-coordinate: for nodes with the same d, spread them evenly vertically.
        pos = {}
        for d, nodes in distance_groups.items():
            nodes_sorted = sorted(nodes)  # sort alphabetically for stability.
            n = len(nodes_sorted)
            # Create y positions so that they are centered around 0.
            y_positions = np.linspace((n - 1) / 2, -(n - 1) / 2, n)
            x = max_distance - d  # ultimate target (d=0) gets the rightmost x value.
            for i, node in enumerate(nodes_sorted):
                pos[node] = (x, y_positions[i])

        # --- Determine axis ranges based on initial_zoom -----------------------------
        # Compute the min and max for x and y positions.
        xs = [p[0] for p in pos.values()]
        ys = [p[1] for p in pos.values()]
        if xs:
            x_min, x_max = min(xs), max(xs)
        else:
            x_min, x_max = -1, 1
        if ys:
            y_min, y_max = min(ys), max(ys)
        else:
            y_min, y_max = -1, 1

        # Compute center and half-width/half-height.
        x_center = (x_min + x_max) / 2
        y_center = (y_min + y_max) / 2
        # Add a margin factor (here 1.2) so nodes are not at the very edge.
        margin_factor = 1.2
        x_half = ((x_max - x_min) / 2) * margin_factor / initial_zoom
        y_half = ((y_max - y_min) / 2) * margin_factor / initial_zoom

        x_range = [x_center - x_half, x_center + x_half]
        y_range = [y_center - y_half, y_center + y_half]

        # --- Create Plotly traces for edges ------------------------------------------
        # Prepare a single trace for edges (drawn as line segments).
        edge_x = []
        edge_y = []
        for u, v in G.edges():
            x0, y0 = pos[u]
            x1, y1 = pos[v]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, 
            y=edge_y,
            line=dict(width=1, color='#888'),
            hoverinfo='none',
            mode='lines'
        )

        # --- Create Plotly traces for nodes ------------------------------------------
        # Define a color mapping for domains (customize as needed)
        color_map = {
            "MODEL": "#FF5733",         # reddish
            "DATASET": "#33C3FF",        # blueish
            "TABLE": "#33FF57",          # greenish
            "FEATURE_VIEW": "#FF33F6",   # magenta-ish
        }

        # Group nodes by domain so that a separate trace (and legend entry) is created per domain.
        domain_nodes = {}
        for node, data in G.nodes(data=True):
            domain = data.get("domain", "Unknown")
            # Shorten the label if required.
            label = node.split('.')[-1] if short_names else node
            domain_nodes.setdefault(domain, {"x": [], "y": [], "text": []})
            x, y = pos[node]
            domain_nodes[domain]["x"].append(x)
            domain_nodes[domain]["y"].append(y)
            domain_nodes[domain]["text"].append(label)

        node_traces = []
        for domain, values in domain_nodes.items():
            trace = go.Scatter(
                x=values["x"],
                y=values["y"],
                mode='markers+text',
                name=domain,  # legend entry will show the domain name.
                text=values["text"],
                textposition="bottom center",
                hoverinfo='text',
                marker=dict(
                    showscale=False,
                    color=color_map.get(domain, "#CCCCCC"),
                    size=30,
                    line_width=2
                )
            )
            node_traces.append(trace)

        # --- Create and show the figure ----------------------------------------------
        fig = go.Figure(
            data=[edge_trace] + node_traces,
            layout=go.Layout(
                title="Lineage Visualization",
                titlefont_size=16,
                showlegend=True,
                hovermode='closest',
                margin=dict(b=20, l=20, r=20, t=40),
                xaxis=dict(range=x_range, showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(range=y_range, showgrid=False, zeroline=False, showticklabels=False)
            )
        )
        st.plotly_chart(fig, use_container_width=True)