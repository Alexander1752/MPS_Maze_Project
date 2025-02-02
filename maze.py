import argparse
from collections import deque
from pathlib import Path
import random
from typing import List

from common.game_elements import Map, Pos, GameState, Dir
import common.tiles as tiles

FIRST_PREFFERENCE = 70 # percent
MAX_NUM_TRAPS_REDIRECT = 4

def retry(times: int, first_different: bool=True):
    """
    Retry Decorator
    - times: The number of times to retry the wrapped function/method
    - first_different: if calls that are retries should have the `retry=True` arg sent to them
    """
    def decorator(func):
        def newfn(*args, **kwargs):
            attempt = 0
            while attempt < times:
                try:
                    return func(*args, **kwargs)
                except Exception:
                    print(
                        'Exception thrown when attempting to run %s, attempt '
                        '%d of %d' % (func, attempt, times)
                    )
                    attempt += 1
                    if first_different:
                        kwargs['retry'] = True
            return func(*args, **kwargs)
        return newfn
    return decorator

def get_parser():
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Create a maze with specified width and height and save it to the specified file.")

    # Add arguments
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Path where the maze will be saved."
    )
    parser.add_argument(
        "--width", "-W",
        type=int,
        required=True,
        help="Width of the maze."
    )
    parser.add_argument(
        "--height", "-H",
        type=int,
        required=True,
        help="Height of the maze."
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        help="Seed to be used."
    )
    parser.add_argument(
        "--max-traps",
        type=int,
        default=0,
        help="Max number of traps of each type."
    )
    parser.add_argument(
        "--portals", "-p",
        action="store_true",
        help="Enable the generation of portals. (note - does nothing when max-traps=0)"
    )

    return parser

def neighbors(maze: Map, cell: Pos, value: int, search=True, generate_maze: bool=False) -> List[Pos]:
    neighbors = []

    # Iterates through four neighbors in the order:
    # [i - 1][j] 
    # [i][j - 1] 
    # [i + 1][j]
    # [i][j + 1]
    for i in range(4):
        n = list(cell)
        n[i % 2] += ((i - i % 2) or -2) // (1 if generate_maze else 2)

        pos = Pos(*n)
        if maze.in_map(pos):
            if search and maze[pos] != value:
                continue
            neighbors.append(pos)

    return neighbors

def maze_order(maze: Map, start = Pos(1,1), first_try: bool=True):
    visited = maze.copy()
    visited[start] = tiles.Wall.code
    prev = {}

    max_dist = 0
    furthest = start

    # The queue contains the position and the minimum distance to it
    queue = deque()
    queue.append((start, 0))
    while queue:
        pos, dist = queue.popleft()
        dist += 1
        max_dist, furthest = max((max_dist, furthest), (dist, pos))

        # Explore the neighboring nodes
        for neighbor in neighbors(visited, pos, tiles.Path.code):
            visited[neighbor] = tiles.Wall.code
            queue.append((neighbor, dist))
            prev[neighbor] = pos

    if first_try:
        # Start from one of the furthest ends of the maze
        print("First try:", max_dist) # TODO remove
        return maze_order(maze, furthest, first_try=False)
    else:
        print("Second try:", max_dist) # TODO remove
        order = []
        pos = furthest

        while pos != start:
            order.append(pos)
            pos = prev[pos]

        order.append(start)
        return order

def generate_walls(width, height):
    # Fill maze with walls
    maze = Map(width=width, height=height)
    maze.fill(tiles.Wall.code)

    # Randomly choose start location
    start = Pos(random.randint(1, height-3) | 1, random.randint(1, width-3) | 1)
    path_count = 1

    maze[start] = tiles.Path.code

    open_cells = [start]

    while open_cells:
        # Needs to be empty for the first iteration of the loop
        n = []
        # Add unnecessary element for elegance of code
        # Allows open_cells.pop() at beginning of do while loop
        open_cells.append((-1, -1))

        # Define current cell as last element in open_cells
        # and get neighbors, discarding "locked" cells
        while len(n) == 0:
            open_cells.pop()
            if not open_cells:
                break

            cell = open_cells[-1]
            n = neighbors(maze, cell, value=tiles.Wall.code, generate_maze=True)

        # If we're done, don't bother continuing
        if len(n) == 0:
            break

        # Choose random neighbor and add it to open_cells, but...
        # ... simply vastly prefer the first neighbor to decrease branching
        rest_len = len(n) - 1
        if not rest_len:
            choice = n[0]
        else:
            choice = random.choices(n, [FIRST_PREFFERENCE] + rest_len * [(100 - FIRST_PREFFERENCE)/rest_len])[0]
        # choice = random.choice(n)
        open_cells.append(choice)

        # Set neighbor to path
        # Set connecting node between cell and choice to path
        maze[choice] = tiles.Path.code
        maze[(choice.x + cell.x) // 2, (choice.y + cell.y) // 2] = tiles.Path.code
        path_count += 2

    print("Path count:", path_count)
    return maze, path_count

@retry(times=3) # TODO subject to change
def generate_maze(width, height, seed=None, * , max_traps=0, retry=False, portals=True):
    if not retry:
        random.seed(seed)

    # Make them odd
    width  |= 1
    height |= 1

    maze, path_count = generate_walls(width, height)
    loop_order = maze_order(maze)

    # Randomly choose entrance and exit locations with respect to the 50% rule
    entrance_idx = random.randint(0, len(loop_order) - path_count // 2 - 1)
    entrance = loop_order[entrance_idx]
    exit_idx = entrance_idx + path_count // 2
    exit = loop_order[exit_idx]
    loop_order = loop_order[entrance_idx : exit_idx + 1]

    maze[entrance] = tiles.Entrance.code
    maze[exit] = tiles.Exit.code

    print("Entrance:", entrance)
    print("Exit:", exit)

    all_traps = [tiles.ForwardTrap, tiles.BackwardTrap, tiles.RewindTrap, tiles.MovesTrap]
    total_max_traps = (path_count - len(loop_order)) // 3 # TODO figure out if enough
    max_traps = min(total_max_traps // len(all_traps), max_traps)
    print("Max traps for current maze:", max_traps)

    generate_traps(maze, all_traps, max_traps, loop_order)

    generate_aux_tiles(maze, max_traps)

    if portals:
        generate_portals(maze, max_traps)

    return maze

def generate_traps(maze: Map, all_traps: List[tiles.Trap], max_traps: int, loop_order: list):
    height, width = maze.shape

    path_to_sol = Map(width=width, height=height)
    path_to_sol.fill(0)

    for pos in loop_order:
        path_to_sol[pos] = 1 # is part of the solution path

    total_max_traps = len(all_traps) * max_traps

    # generate traps
    for idx, trap_type in enumerate(all_traps):
        max_traps = min(total_max_traps // (len(all_traps) - idx), max_traps)
        num_trap = random.randint(0, max_traps)
        total_max_traps -= num_trap

        for _ in range(num_trap):
            while True:
                i = random.randint(0, height - 1)
                j = random.randint(0, width - 1)
                pos = Pos(i, j)

                if trap_type != tiles.MovesTrap and path_to_sol[pos]:
                    continue

                if maze[pos] != tiles.Path.code:
                    continue

                if trap_type == tiles.ForwardTrap:
                    left_right_neigh = [Dir.move(pos, Dir.W), Dir.move(pos, Dir.E)]
                    walls = [maze[neigh] == tiles.Wall.code for neigh in left_right_neigh]
                    if any(walls) and not all(walls):
                        continue

                    up_down_neigh = [Dir.move(pos, Dir.N), Dir.move(pos, Dir.S)]
                    walls = [maze[neigh] == tiles.Wall.code for neigh in up_down_neigh]
                    if any(walls) and not all(walls):
                        continue

                trap_powers = [1, 2, 3, 4, 5]
                random.shuffle(trap_powers)

                for n in trap_powers:
                    maze[pos] = trap_type(n).code
                    valid = True
                    for neigh in neighbors(maze, pos, tiles.Path.code, False):
                        if maze[neigh] != tiles.Path.code and maze[neigh] != tiles.Wall.code:
                            valid = False
                            break

                        # Only try visiting the trap when coming from a Path, can't start on a Wall
                        if maze[neigh] == tiles.Path.code:
                            try:
                                state = GameState(maps=[maze], pos=pos)
                                state.perform_command(Dir.get_direction(neigh, pos), max_num_traps_redirect=MAX_NUM_TRAPS_REDIRECT)
                            except:
                                valid = False
                                break           

                    if valid:
                        break

                if valid:
                    break

                maze[pos] = tiles.Path.code

def generate_aux_tiles(maze: Map, max_aux_tiles: int):
    height, width = maze.shape
    # generate X-RAY points, Towers and Fogs
    for tile_type in [tiles.Xray, tiles.Fog, tiles.Tower]:
        num_tiles = random.randint(0, max_aux_tiles)
        for _ in range(num_tiles):
            while True:
                i = random.randint(0, height - 1)
                j = random.randint(0, width - 1)
                pos = Pos(i, j)

                if maze[pos] != tiles.Path.code:
                    continue

                valid = True
                for neigh in neighbors(maze, pos, tiles.Path.code, False):
                    if maze[neigh] != tiles.Path.code and maze[neigh] != tiles.Wall.code:
                        valid = False
                        break

                if valid:
                    break
    
            maze[i][j] = tile_type.code

def generate_portals(maze: Map, max_portals: int):
    height, width = maze.shape

    first_portal = tiles.Portal.first_portal()
    max_portals = min(max_portals // 2, tiles.Portal.last_portal() - first_portal + 1)

    last_portal = random.randint(first_portal, first_portal + max_portals)
    # generate portals
    portal_codes = iter(range(first_portal, last_portal))
    pair_portal = None
    pair_code = None
    for _ in range(2 * first_portal, 2 * last_portal):
        while True:
            i = random.randint(0, height - 1)
            j = random.randint(0, width - 1)
            pos = Pos(i, j)

            if maze[pos] != tiles.Path.code:
                continue

            valid = True
            for neigh in neighbors(maze, pos, tiles.Path.code, False):
                if maze[neigh] != tiles.Path.code and maze[neigh] != tiles.Wall.code:
                    valid = False
                    break

            if valid:
                break

        if pair_portal is None:
            pair_portal = Pos(i, j)
            pair_code = next(portal_codes)
        else:
            maze[pair_portal] = pair_code
            maze[i][j] = pair_code
            pair_portal = None

def main(args=None):
    parser = get_parser()
    args = parser.parse_args(args)

    maze = generate_maze(args.width, args.height, max_traps=args.max_traps, seed=args.seed, portals=args.portals)

    # Convert maze to image
    maze.write_to_file(args.output)

    return maze

if __name__ == "__main__":
    main()
