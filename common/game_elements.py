#!/usr/bin/env python3
from collections import namedtuple
from enum import Enum
import numpy as np
import json
import logging
from PIL import Image
from typing import List, Dict, Tuple

import common.tiles as tiles


Pos = namedtuple("Pos", "x y")

class Dir:
    N = 'N'
    S = 'S'
    E = 'E'
    W = 'W'

    OPPOSITE = {
        N : S,
        S : N,
        E : W,
        W : E
    }

    NEXT = {
        N : E,
        E : S,
        S : W,
        W : None,
        None: None
    }

    PREV = {
        None: W,
        W : S,
        S : E,
        E : N,
        N : None
    }

    @classmethod
    def move(cls, pos: Pos, direction):
        """ Gets a position and a direction and returns the position obtained by going in said direction. """
        match direction:
            case cls.N:
                return Pos(pos.x - 1, pos.y)
            case cls.S:
                return Pos(pos.x + 1, pos.y)
            case cls.E:
                return Pos(pos.x, pos.y + 1)
            case cls.W:
                return Pos(pos.x, pos.y - 1)
            case _:
                raise ValueError(f'"{direction}" is not a valid direction')

    @classmethod
    def get_direction(cls, src: Pos, dest: Pos):
        dir = cls.N
        while dir:
            result = cls.move(src, dir)
            if result.x == dest.x and result.y == dest.y:
                return dir
            dir = cls.NEXT[dir]

class State(int, Enum):
    NEW     = 0
    VISITED = 1
    WALL    = 2

class Map(np.ndarray):
    """ Class that extends a numpy matrix to add the anchor, it's weird because it needs to be; 
    just use it like `map[x][y]` and `map.anchor.x` and it all should be good """
    MAX_WIDTH, MAX_HEIGHT = 2000, 2000 # maximum map size limits, subject to change
    AGENT_ANCHOR = Pos(MAX_WIDTH // 2, MAX_HEIGHT // 2)
    ANCHOR = Pos(0, 0)

    def __new__(
        cls,
        # this `*` down below makes it so that one can only give arguments with their full name
        # e.g. Map(Pos(2,2)) is not allowed, use Map(anchor=Pos(2,2))
        *,
        anchor: Pos | None = None,
        agent_map: bool = False,
        width:  int = 0,
        height: int = 0,
        nparr: np.ndarray | None = None # harta, matrice care tine codurile de la 0-255
    ):
        if nparr is not None:
            obj = nparr.view(cls)
        else:
            size = (int(height) if height else cls.MAX_HEIGHT, int(width) if width else cls.MAX_WIDTH)
            obj = np.ones(size, dtype=np.uint8).view(cls) # init full of ones (unknown) -- might change based on feedback
        # add the new attribute to the created instance
        if anchor is not None:
            obj.anchor = anchor
        elif agent_map:
            obj.anchor = cls.AGENT_ANCHOR
            obj[obj.anchor.x][obj.anchor.y] = tiles.Entrance.code
        else:
            obj.anchor = cls.ANCHOR

        entrance_tiles = list(np.argwhere(obj == tiles.Entrance.code))
        if len(entrance_tiles):
            obj.entrance = Pos(*entrance_tiles[0])

        # return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.anchor: Pos | None = getattr(obj, 'anchor', None)
        self.entrance: Pos | None = getattr(obj, 'entrance', None)

    def in_map(self, *args):
        if len(args) == 1:
            pos = args[0]
        else:
            pos = Pos(args[0], args[1])

        return pos.x >= 0 and pos.y >= 0 and pos.x < len(self) and pos.y < len(self[0])

    def write_to_file(self, path):
        img = Image.fromarray(self, mode="L")  # "L" mode is for 8-bit grayscale
        img.save(path)

    @classmethod
    def load_from_file(cls, path):
        img = Image.open(path).convert("L")  # Ensure it's in grayscale mode ("L")
        return cls(nparr=np.array(img, dtype=np.uint8))


class GameState:
    MAX_MOVES_PER_TURN = 10
    START_XRAY_POINTS = 10


    #TODO: add visibility 
    def __init__(
        self,
        *,
        # these constructor args may or may not be used in the end, only here in case they're needed
        pos: Pos = None,
        maps: List[Map] | None = None,
        portals: Dict[int, Tuple] | None = None,
        moves: int | None = None,
        next_round_moves: int | None = None,
        xray_points: int | None = None,
        agent: bool = False,
        visibility: int = 2,
        width: int | None = None,
        height: int | None = None,
        view: str | None = None,
    ) -> None:
        self.maps = maps if maps else [Map(anchor=pos, agent_map=agent, width=width, height=height)] # list of maps; all parts except the agent will contain only one map, the current one
        self.current_map = self.maps[-1] # the only map actually used, except for the AI (might not get the chance to actually implement that after all)

        if pos is not None:
            self.pos = pos
        elif agent:
            self.pos = self.current_map.anchor
        else:
            # Extract the position of the entrance from the map
            self.pos = self.current_map.entrance

        if agent:
            self.visited = self.current_map.copy()
            self.visited.fill(State.VISITED)

        self.agent = agent

        self.moves = int(moves) if moves is not None else self.MAX_MOVES_PER_TURN # no. of turns for the current round
        self.next_round_moves = next_round_moves if next_round_moves is not None else self.MAX_MOVES_PER_TURN

        self.xray_points = xray_points if xray_points is not None else self.START_XRAY_POINTS

        self.portals: Dict[int, Tuple] = portals if portals else {}

        self._visibility = visibility
        self.xray_on = 0

        self.add_view(view)

    def add_view(self, view: str):
        if not view:
            return

        view: List[List[int]] = json.loads(view) # TODO change deserialization
        visibility = len(view) // 2
        view_i = 0
        view_j = 0
        for i in range(self.pos.x - visibility, self.pos.x + visibility + 1):
            for j in range(self.pos.y - visibility, self.pos.y + visibility + 1):
                if self.current_map.in_map(i, j):
                    old_val = tiles.from_code(self.current_map[i][j])
                    new_val = view[view_i][view_j]

                    if self.agent:
                        if new_val == tiles.Wall.code or old_val.code == tiles.Wall.code:
                            self.visited[i][j] = State.WALL

                    if isinstance(old_val, tiles.Trap):
                        if isinstance(old_val, tiles.UnknownTrap) and new_val != tiles.Path.code:
                            # Only overwrite a Trap if it is with more information than what's already available
                            self.current_map[i][j] = new_val
                    else:
                        # if it's not a trap, write whatever we received
                        self.current_map[i][j] = new_val

                view_j += 1
            view_j = 0
            view_i += 1

    # TODO: this will need to be changed -- ar fi bine sa dea return la vizibilitate. Pot sa fac chestia asta pe
    # pe server si asta ar trebui sa dea macar un raspuns de ok sau nu.
    def perform_command(self, move: str): # XXX maybe consider returning here the command result, visibility around agent etc.
        """ Applies a command on this game state """
        self.moves -= 1
        self.xray_on = 0
        match move:
            case 'X': # TODO support greater size xray
                return self.use_xray()
            case 'N' | 'S' | 'E' | 'W':
                return self.move(move)
            case '': # empty command
                return
            case _:
                raise ValueError(f'"{move}" is not a valid move')

    def move(self, direction):
        """ Applies a move command on this game state (not X-Ray) """
        self.pos = Dir.move(self.pos, direction) # move into the tile, even if wall (its effect will move us back where we started from)
        logging.debug(f'Moved into tile {self.current_map[self.pos.x][self.pos.y]}')
        effect = tiles.from_code(self.current_map[self.pos.x][self.pos.y]).visit(direction)
        if effect.activate(self) is not None:
            return '0'
        return '1'

    def decrease_next_round_moves(self, amount: int = 1):
        self.next_round_moves -= amount
        if self.next_round_moves < 0:
            self.next_round_moves = 0

    def new_round(self):
        self.moves = self.next_round_moves
        self.next_round_moves = self.MAX_MOVES_PER_TURN

    def use_xray(self):
        if self.xray_points <= 0:
            return '0'
            raise ValueError("No X-Ray points left to use!")
        self.xray_points -= 1
        self.xray_on += 1
        return '1'

    @property
    def visibility(self):
        visibility = self._visibility
        tile_type = tiles.CODE_TO_TYPE[self.current_map[self.pos]]

        if tile_type == tiles.Fog:
            visibility -= 1
        elif tile_type == tiles.Tower:
            visibility += 1

        visibility += self.xray_on

        return visibility

    def view(self):
        """Returns a matrix that represents the visible area around the player"""
        x = self.pos.x
        y = self.pos.y
        visibility = self.visibility

        current_visibility = [[0 for _ in range(2 * visibility + 1)] for _ in range(2 * visibility + 1)]

        # I want to avoid translation at matrix indexes, because of this, I will fill the
        # visibility matrix manually
        matrix_i, matrix_j = 0, 0
        for i in range(x - visibility, x + visibility + 1):
            for j in range(y - visibility, y + visibility + 1):
                if not self.current_map.in_map(i, j):
                    # If I go out-of-bounds, print a wall
                    current_visibility[matrix_i][matrix_j] = tiles.Wall.code
                else:
                    current_visibility[matrix_i][matrix_j] = int(self.current_map[i][j])
                matrix_j += 1
            matrix_i += 1
            matrix_j = 0

        return current_visibility

