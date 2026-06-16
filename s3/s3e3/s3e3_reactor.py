import os
import requests
import time
from collections import deque
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("AIDEVSKEY")
URL = "https://hub.ag3nts.org/verify"

def send_command(command):
    payload = {
        "apikey": API_KEY,
        "task": "reactor",
        "answer": {
            "command": command
        }
    }
    response = requests.post(URL, json=payload)
    response.raise_for_status()
    return response.json()

def next_blocks(blocks):
    new_blocks = []
    for b in blocks:
        tr = b['top_row']
        br = b['bottom_row']
        d = b['direction']
        
        if d == 'down':
            if br == 4:
                new_blocks.append({'col': b['col'], 'top_row': tr + 1, 'bottom_row': br + 1, 'direction': 'up'})
            else:
                new_blocks.append({'col': b['col'], 'top_row': tr + 1, 'bottom_row': br + 1, 'direction': 'down'})
        else:
            if tr == 2:
                new_blocks.append({'col': b['col'], 'top_row': tr - 1, 'bottom_row': br - 1, 'direction': 'down'})
            else:
                new_blocks.append({'col': b['col'], 'top_row': tr - 1, 'bottom_row': br - 1, 'direction': 'up'})
    return new_blocks

def get_danger_cols(blocks):
    return [b['col'] for b in blocks if b['bottom_row'] == 5]

def blocks_to_tuple(blocks):
    return tuple((b['col'], b['bottom_row'], b['direction']) for b in blocks)

def solve_bfs(start_col, start_blocks, goal_col):
    queue = deque([(start_col, start_blocks, [])])
    visited = set()
    visited.add((start_col, blocks_to_tuple(start_blocks)))
    
    while queue:
        p_col, blks, path = queue.popleft()
        
        if p_col == goal_col:
            return path
            
        nxt_blks = next_blocks(blks)
        danger = get_danger_cols(nxt_blks)
        nxt_blks_tup = blocks_to_tuple(nxt_blks)
        
        moves = [('right', p_col + 1), ('wait', p_col), ('left', p_col - 1)]
        for cmd, new_col in moves:
            if new_col < 1 or new_col > goal_col:
                continue
            if new_col in danger:
                continue
                
            state = (new_col, nxt_blks_tup)
            if state not in visited:
                visited.add(state)
                queue.append((new_col, nxt_blks, path + [cmd]))
                
    return None

def main():
    print("Sending START...")
    state = send_command("start")
    
    p_col = state['player']['col']
    goal_col = state['goal']['col']
    blocks = state['blocks']
    
    print(f"Start player: {p_col}, goal: {goal_col}")
    
    path = solve_bfs(p_col, blocks, goal_col)
    if not path:
        print("No safe path found!")
        return
        
    print(f"Found safe path: {path}")
    
    for cmd in path:
        print(f"Sending command: {cmd}")
        time.sleep(0.5)
        state = send_command(cmd)
        print(f"Message: {state.get('message')}")
        
        if '{FLG:' in str(state) or state.get('reached_goal'):
            print("WE WON!")
            print(state)
            break

if __name__ == "__main__":
    main()
