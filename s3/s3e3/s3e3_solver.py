import copy
from collections import deque

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
    # Queue stores: (player_col, blocks, path_of_commands)
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
        
        # Possible moves
        moves = [('right', p_col + 1), ('wait', p_col), ('left', p_col - 1)]
        for cmd, new_col in moves:
            # Check bounds
            if new_col < 1 or new_col > goal_col:
                continue
            # Check danger
            if new_col in danger:
                continue
                
            state = (new_col, nxt_blks_tup)
            if state not in visited:
                visited.add(state)
                queue.append((new_col, nxt_blks, path + [cmd]))
                
    return None

if __name__ == "__main__":
    blocks = [{'col': 2, 'top_row': 1, 'bottom_row': 2, 'direction': 'down'}, {'col': 3, 'top_row': 3, 'bottom_row': 4, 'direction': 'down'}, {'col': 4, 'top_row': 2, 'bottom_row': 3, 'direction': 'down'}, {'col': 5, 'top_row': 2, 'bottom_row': 3, 'direction': 'down'}, {'col': 6, 'top_row': 3, 'bottom_row': 4, 'direction': 'up'}]
    path = solve_bfs(1, blocks, 7)
    print(path)
