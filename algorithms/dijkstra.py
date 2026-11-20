import heapq
import pandas as pd

class HumanitarianNetwork:
    def __init__(self, excel_path='hrp_network_data.xlsx'):
        # Load sheets
        self.legs_df = pd.read_excel(excel_path, sheet_name='network_legs')
        self.scenarios_df = pd.read_excel(excel_path, sheet_name='disruption_scenarios')
        self.locations_df = pd.read_excel(excel_path, sheet_name='locations')
        
        self.graph = {}
        self._build_graph()

    def _build_graph(self):
        self.graph = {}
        for _, row in self.legs_df.iterrows():
            u = row['from_node']
            v = row['to_node']
            if u not in self.graph:
                self.graph[u] = {}
            self.graph[u][v] = {
                'leg_id': row['leg_id'],
                'time': float(row['transit_hours_typical']),
                'cost': float(row['cost_usd_per_tonne']),
                'risk': int(row['risk_score_1to5']),
                'capacity': float(row['capacity_tonnes_per_week']),
                'mode': row['mode'],
                'corridor': row['corridor_group']
            }

    def dijkstra(self, start='IHC', goal='ELO', objective='time', cargo_weight=0, is_cold_chain=False, risk_override=False, scenario_id='S0'):
        """
        Calculates optimal path from start to goal.
        Objectives: 'time', 'cost', 'risk_weighted_cost'
        """
        # Parse Disruption Scenario actions
        closed_legs = set()
        time_mult = {}
        cost_mult = {}

        if scenario_id != 'S0':
            scenario_rows = self.scenarios_df[self.scenarios_df['scenario_id'] == scenario_id]
            # Handle S9 compound scenario
            if scenario_id == 'S9':
                scenario_rows = self.scenarios_df[self.scenarios_df['scenario_id'].isin(['S1', 'S2'])]
            
            for _, s_row in scenario_rows.iterrows():
                action = s_row['action']
                leg = s_row['leg_id']
                if action == 'CLOSE':
                    closed_legs.add(leg)
                elif action == 'TIME_MULT':
                    time_mult[leg] = float(s_row['value'])
                elif action == 'COST_MULT':
                    cost_mult[leg] = float(s_row['value'])

        # Priority Queue: (cumulative_objective_cost, current_node, path, cumulative_time, cumulative_cost)
        queue = [(0, start, [start], 0, 0)]
        visited = {}

        while queue:
            current_obj, current_node, path, current_time, current_cost = heapq.heappop(queue)

            if current_node == goal:
                return {
                    "path": path,
                    "total_objective_val": round(current_obj, 2),
                    "total_time_hours": round(current_time, 2),
                    "total_cost_usd": round(current_cost, 2),
                    "feasible": True
                }

            if current_node in visited and visited[current_node] <= current_obj:
                continue
            visited[current_node] = current_obj

            if current_node not in self.graph:
                continue

            for neighbor, attrs in self.graph[current_node].items():
                leg_id = attrs['leg_id']

                # Rule 0: Skip closed legs from disruption scenarios
                if leg_id in closed_legs:
                    continue

                # Hard Rule 1: Capacity check
                if attrs['capacity'] < cargo_weight:
                    continue
                
                # Hard Rule 2: Risk 5 check
                if attrs['risk'] >= 5 and not risk_override:
                    continue

                # Multipliers
                leg_time = attrs['time'] * time_mult.get(leg_id, 1.0)
                leg_cost = attrs['cost'] * cost_mult.get(leg_id, 1.0)
                leg_risk = attrs['risk']

                # Hard Rule 3: Cold-chain 72-hour limit
                next_time = current_time + leg_time
                if is_cold_chain and next_time > 72:
                    continue

                # Objective weight calculation
                if objective == 'time':
                    edge_weight = leg_time
                elif objective == 'cost':
                    edge_weight = leg_cost
                elif objective == 'risk_weighted_cost':
                    # Risk-Weighted Cost = Cost * Risk Score
                    edge_weight = leg_cost * leg_risk
                else:
                    edge_weight = leg_time

                next_obj = current_obj + edge_weight
                next_cost = current_cost + leg_cost

                heapq.heappush(queue, (next_obj, neighbor, path + [neighbor], next_time, next_cost))

        return {"path": None, "status": "Impossible Route - No feasible path found", "feasible": False}

# --- Execution Example ---
if __name__ == "__main__":
    net = HumanitarianNetwork('hrp_network_data.xlsx')

    print("=== BASELINE (S0) ROUTE COMPUTATIONS ===")
    print("1. Fastest Route (Time):", net.dijkstra(start='IHC', goal='ELO', objective='time'))
    print("2. Cheapest Route (Cost):", net.dijkstra(start='IHC', goal='ELO', objective='cost'))
    print("3. Risk-Weighted Cost Route:", net.dijkstra(start='IHC', goal='ELO', objective='risk_weighted_cost'))
    
    print("\n=== DISRUPTION SCENARIO S2 (Red Sea Suspended) ===")
    print("Cheapest Route under S2:", net.dijkstra(start='IHC', goal='ELO', objective='cost', scenario_id='S2'))