import os
import json
import requests
from dotenv import load_dotenv

# Load env from root
load_dotenv(dotenv_path="../../.env")

API_KEY = os.getenv("AIDEVSKEY") or "9b2b37d3-dfab-42e0-a4b2-d84454981394"
VERIFY_URL = "https://hub.ag3nts.org/verify"

MAP = [
    [".", ".", ".", ".", ".", ".", ".", ".", "W", "W"],
    [".", ".", ".", ".", ".", ".", ".", "W", "W", "."],
    [".", "T", ".", ".", ".", ".", "W", "W", ".", "."],
    [".", ".", ".", ".", ".", ".", "W", ".", ".", "."],
    [".", ".", "T", ".", ".", ".", "W", ".", "G", "."],
    [".", ".", ".", ".", "R", ".", "W", ".", ".", "."],
    [".", ".", ".", "R", "R", ".", "W", "W", ".", "."],
    ["S", "R", ".", ".", ".", ".", ".", "W", ".", "."],
    [".", ".", ".", ".", ".", ".", "W", "W", ".", "."],
    [".", ".", ".", ".", ".", "W", "W", ".", ".", "."]
]

START_ROW, START_COL = 7, 0
GOAL_ROW, GOAL_COL = 4, 8

# Vehicle stats multiplied by 10 (to use integers)
# Format: {vehicle_name: {fuel_cost, food_cost, can_water}}
# Note: we will run two cases for 'car' food cost: 15 (1.5) and 10 (1.0)
def get_vehicle_configs(car_food):
    return {
        "rocket": {"fuel": 10, "food": 1, "water": False},
        "car": {"fuel": 7, "food": car_food, "water": False},
        "horse": {"fuel": 0, "food": 16, "water": True},
        "walk": {"fuel": 0, "food": 25, "water": True}
    }

DIRECTIONS = {
    "up": (-1, 0),
    "down": (1, 0),
    "left": (0, -1),
    "right": (0, 1)
}

def solve(car_food=15):
    configs = get_vehicle_configs(car_food)
    
    # We want to find a path from START to GOAL
    # State representation for BFS/Dijkstra:
    # State: (r, c, vehicle)
    # We want to keep track of the maximum (food, fuel) at each state to prune paths.
    # best_resources[(r, c, vehicle)] = list of (food, fuel) which are Pareto-optimal.
    # Since we want to find any valid path, we can do a queue-based search.
    # Queue element: (r, c, vehicle, food, fuel, path_actions)
    
    from collections import deque
    
    solutions = []
    
    for start_veh in ["rocket", "car", "horse", "walk"]:
        # Check start tile restrictions (Start tile is 'S', which is not water or rock)
        queue = deque([(START_ROW, START_COL, start_veh, 100, 100, [start_veh])])
        
        # To avoid infinite loops and prune suboptimal states, we keep track of the maximum (food, fuel) for each (r, c, vehicle)
        # visited[(r, c, vehicle)] = list of tuples (food, fuel)
        visited = {}
        
        while queue:
            r, c, veh, food, fuel, path = queue.popleft()
            
            # Pruning: check if we have visited this state with equal or better resources
            if (r, c, veh) in visited:
                dominated = False
                for v_food, v_fuel in visited[(r, c, veh)]:
                    if v_food >= food and v_fuel >= fuel:
                        dominated = True
                        break
                if dominated:
                    continue
                # Add to visited and filter out any existing states that this one dominates
                visited[(r, c, veh)] = [p for p in visited[(r, c, veh)] if not (food >= p[0] and fuel >= p[1])]
                visited[(r, c, veh)].append((food, fuel))
            else:
                visited[(r, c, veh)] = [(food, fuel)]
                
            # If we reached the goal
            if r == GOAL_ROW and c == GOAL_COL:
                solutions.append({
                    "vehicle": start_veh,
                    "car_food_config": car_food,
                    "food_left": food / 10.0,
                    "fuel_left": fuel / 10.0,
                    "path": path,
                    "length": len(path)
                })
                continue
                
            # Try movement actions: up, down, left, right
            for dir_name, (dr, dc) in DIRECTIONS.items():
                nr, nc = r + dr, c + dc
                if 0 <= nr < 10 and 0 <= nc < 10:
                    tile = MAP[nr][nc]
                    if tile == "R":
                        continue  # Rocks block everything
                        
                    # Check water restrictions
                    if tile == "W" and not configs[veh]["water"]:
                        continue  # Rocket/Car cannot enter water
                        
                    # Calculate cost
                    food_cost = configs[veh]["food"]
                    fuel_cost = configs[veh]["fuel"]
                    if tile == "T" and veh in ["rocket", "car"]:
                        fuel_cost += 2  # Tree penalty +0.2 fuel
                        
                    if food - food_cost >= 0 and fuel - fuel_cost >= 0:
                        queue.append((nr, nc, veh, food - food_cost, fuel - fuel_cost, path + [dir_name]))
                        
            # Try dismount action
            if veh != "walk":
                # We can dismount on the current tile (no movement)
                queue.append((r, c, "walk", food, fuel, path + ["dismount"]))
                
    return solutions

def main():
    print("--- Searching for solution with car food cost = 1.5 ---")
    solutions_15 = solve(car_food=15)
    print(f"Found {len(solutions_15)} solutions.")
    for idx, sol in enumerate(solutions_15):
        print(f"Sol #{idx+1}: Start={sol['vehicle']}, Steps={sol['length']}, FoodLeft={sol['food_left']}, FuelLeft={sol['fuel_left']}")
        print(f"Path: {sol['path']}\n")
        
    print("--- Searching for solution with car food cost = 1.0 ---")
    solutions_10 = solve(car_food=10)
    print(f"Found {len(solutions_10)} solutions.")
    for idx, sol in enumerate(solutions_10):
        print(f"Sol #{idx+1}: Start={sol['vehicle']}, Steps={sol['length']}, FoodLeft={sol['food_left']}, FuelLeft={sol['fuel_left']}")
        print(f"Path: {sol['path']}\n")

    # Select the best solution (maximizing food_left or fuel_left, or general valid)
    all_sols = solutions_15 + solutions_10
    if not all_sols:
        print("No solutions found at all!")
        return

    # Let's pick one of the solutions from solutions_15 (or solutions_10 if 15 doesn't find any).
    # Prefer solutions_15 since that's what was in the API body response.
    chosen_sol = None
    if solutions_15:
        # Sort by remaining food (since food is usually the bottleneck for dismounted walk)
        chosen_sol = sorted(solutions_15, key=lambda x: (x["food_left"], x["fuel_left"]), reverse=True)[0]
    else:
        chosen_sol = sorted(solutions_10, key=lambda x: (x["food_left"], x["fuel_left"]), reverse=True)[0]

    print(f"Chosen solution to submit: {chosen_sol}")

    # Ask the user if they want to submit
    payload = {
        "apikey": API_KEY,
        "task": "savethem",
        "answer": chosen_sol["path"]
    }
    
    print("\nPayload to submit:")
    print(json.dumps(payload, indent=2))
    
    # Save the payload locally to a file so we can run a submission script
    with open("submission_payload.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print("Saved submission_payload.json")

if __name__ == "__main__":
    main()
