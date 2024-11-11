import argparse
from collections import deque
from pathlib import Path
import random
from typing import List

from common.game_elements import Map, Pos
import common.tiles as tiles

FIRST_PREFFERENCE = 70 # percent

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

    return parser

def neighbors(maze: Map, cell: Pos, value: int, generate_maze: bool=False) -> List[Pos]:
    neighbors = []

    # Iterates through four neighbors in the order:
    # [i - 1][j] 
    # [i][j - 1] 
    # [i + 1][j]
    # [i][j + 1]
    for i in range(4):
        n = list(cell)
        n[i % 2] += ((i - i % 2) or -2) // (1 if generate_maze else 2)

        if n[0] < maze.shape[0] and n[1] < maze.shape[1] and n[0] > 0 and n[1] > 0:
            if maze[n[0]][n[1]] == value:
                neighbors.append(Pos(*n))

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
def generate_maze(width, height, seed=None, max_special_tiles=1, * , retry=False):
    if not retry:
        random.seed(seed)

    # Make them odd
    width  |= 1
    height |= 1

    maze, path_count = generate_walls(width, height)
    loop_order = maze_order(maze)

    # TODO remove
    tmp = maze.copy()
    for pos in loop_order:
        tmp[pos] = tiles.Fog.code
    tmp.write_to_file("temp.png")

    # Randomly choose entrance and exit locations with respect to the 50% rule
    entrance_idx = random.randint(0, len(loop_order) - path_count // 2 - 1)
    entrance = loop_order[entrance_idx]
    exit = random.choice(loop_order[entrance_idx + path_count // 2:])

    maze[entrance] = tiles.Entrance.code
    maze[exit] = tiles.Exit.code

    print("Entrance:", entrance)
    print("Exit:", exit)

    return maze

def main():
    parser = get_parser()
    args = parser.parse_args()

    maze = generate_maze(args.width, args.height, seed=args.seed)

    # Convert maze to image
    maze.write_to_file(args.output)

if __name__ == "__main__":
    main()
