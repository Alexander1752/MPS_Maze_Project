from pathlib import Path
import pytest

from common.game_elements import Map
import common.tiles as tiles
import maze

args = [
    (10, 20, 42),
    (200, 50, 12),
    (192, 108, 55)
]

@pytest.mark.parametrize("width,height,seed", args)
def test_generate_requirements(tmp_path,  width, height, seed):
    tmp_path = Path(tmp_path) / 'output.png'
    gen_maze = maze.generate_maze(width, height, seed)

    assert len(gen_maze) - height in [0, 1]
    assert len(gen_maze[0]) - width in [0, 1]
    assert int((gen_maze == tiles.Entrance.code).sum()) == 1
    assert int((gen_maze == tiles.Exit.code).sum()) == 1

    path_tiles = int((gen_maze != tiles.Wall.code).sum())
    # TODO check minimum 50% distance
    
@pytest.mark.parametrize("width,height,seed", args)
def test_save_load(tmp_path,  width, height, seed):
    tmp_path = Path(tmp_path) / 'output.png'
    gen_maze = maze.generate_maze(width, height, seed)

    gen_maze.write_to_file(tmp_path)
    saved_maze = Map.load_from_file(tmp_path)

    same_maze(gen_maze, saved_maze)

def same_maze(maze1, maze2):
    height = len(maze1)
    width  = len(maze1[0])
    assert len(maze2) == height
    assert len(maze2[0]) == width

    for i in range(height):
        for j in range(width):
            assert maze1[i][j] == maze2[i][j]
