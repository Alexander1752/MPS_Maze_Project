import argparse
from queue import LifoQueue
from pathlib import Path
import random
from typing import List

from common.game_elements import Map, Pos
import common.tiles as tiles

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
    # [i - 2][j] 
    # [i][j - 2] 
    # [i + 2][j]
    # [i][j + 2]
    for i in range(4):
        n = list(cell)
        n[i % 2] += ((i - i % 2) or -2) // (1 if generate_maze else 2)

        if n[0] < maze.shape[0] and n[1] < maze.shape[1] and n[0] > 0 and n[1] > 0:
            if maze[n[0]][n[1]] == value:
                neighbors.append(Pos(*n))

    return neighbors

def valid_exits(maze: Map, entrance: Pos, min_dist_from_entrance: int):
    MIN_CHOICE_SIZE = 100

    visited = maze.copy()
    visited[entrance] = tiles.Entrance.code

    # The stack contains the node and the minimum distance to it
    stack = LifoQueue()
    stack.put((entrance, 0))
    max_dist = 0

    valid_exits = []
    while not stack.empty() and len(valid_exits) < MIN_CHOICE_SIZE:
        node, dist = stack.get()
        visited[node] = tiles.Wall.code
        max_dist = max(max_dist, dist)
        dist += 1

        # Explore the neighboring nodes
        for neighbor in neighbors(visited, node, tiles.Path.code):
            if dist >= min_dist_from_entrance:
                valid_exits.append(neighbor)
                print("Valid exit no.", len(valid_exits), "found")

            stack.put((neighbor, dist))

    print("Max dist:", max_dist)
    return valid_exits

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
        # Allows openCells.pop() at beginning of do while loop
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

        # Choose random neighbor and add it to open_cells
        choice = random.choice(n)
        open_cells.append(choice)

        # Set neighbor to path
        # Set connecting node between cell and choice to path
        maze[choice] = tiles.Path.code
        maze[(choice.x + cell.x) // 2, (choice.y + cell.y) // 2] = tiles.Path.code
        path_count += 2

    print("Path count:", path_count)
    return maze, path_count

def generate_maze(width, height, seed=None, max_special_tiles=1):
    random.seed(seed)

    # Make them odd
    width  |= 1
    height |= 1

    maze, path_count = generate_walls(width, height)

    potential_exits = []
    tries = 0
    while not potential_exits:
        tries += 1
        print("Try no.", tries)

        # Randomly choose entrance location
        entrance = (0, 0)
        while maze[entrance] == tiles.Wall.code:
            entrance = Pos(random.randint(1, height-2), random.randint(1, width-2))

        potential_exits = valid_exits(maze, entrance, path_count // 2)

    maze[entrance] = tiles.Entrance.code
    print("Candidates:", potential_exits) # TODO remove
    exit = random.choice(potential_exits)
    maze[exit] = tiles.Exit.code

    print("Entrance:", entrance)

    return maze

def main():
    parser = get_parser()
    args = parser.parse_args()

    maze = generate_maze(args.width, args.height, seed=args.seed)

    # Convert maze to image
    maze.write_to_file(args.output)

if __name__ == "__main__":
    main()
