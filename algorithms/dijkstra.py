import heapq

class HumanitarianNetwork:
    def __init__(self):
        # Graph structure: {node: {neighbor: {'time': float, 'cost': float, 'risk': int, 'capacity': float}}}
        self.graph = {}

    def add_leg(self, u, v, time, cost, risk, capacity):
        if u not in self.graph:
            self.graph[u] = {}
        self.graph[u][v] = {'time': time, 'cost': cost, 'risk': risk, 'capacity': capacity}

    def dijkstra(self, start, goal, objective='time', cargo_weight=0, is_cold_chain=False, risk_override=False):
        """
        objective: 'time', 'cost', or 'risk'
        """
        # Priority queue stores tuples of (cumulative_weight, current_node, path, cumulative_time)
        queue = [(0, start, [start], 0)]
        visited = {start: 0}

        while queue:
            current_weight, current_node, path, current_time = heapq.heappop(queue)

            if current_node == goal:
                return {"path": path, f"total_{objective}": current_weight, "total_time": current_time}

            if current_node not in self.graph:
                continue

            for neighbor, attributes in self.graph[current_node].items():
                # Hard Rule 1: Capacity check
                if attributes['capacity'] < cargo_weight:
                    continue
                
                # Hard Rule 2: Risk 5 check
                if attributes['risk'] == 5 and not risk_override:
                    continue

                # Hard Rule 3: Cold-chain 72-hour limit
                next_time = current_time + attributes['time']
                if is_cold_chain and next_time > 72:
                    continue

                # Determine edge weight based on the selected objective
                if objective == 'time':
                    edge_weight = attributes['time']
                elif objective == 'cost':
                    edge_weight = attributes['cost']
                elif objective == 'risk':
                    edge_weight = attributes['risk']

                next_weight = current_weight + edge_weight

                # Only proceed if we found a strictly better path to the neighbor
                if neighbor not in visited or next_weight < visited[neighbor]:
                    visited[neighbor] = next_weight
                    heapq.heappush(queue, (next_weight, neighbor, path + [neighbor], next_time))

        return {"path": None, "status": "Impossible Route - No feasible path found meeting all constraints."}