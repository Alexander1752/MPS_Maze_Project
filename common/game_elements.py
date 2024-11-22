#!/usr/bin/env python3
from collections import namedtuple
import numpy as np
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
            obj.entrance = Pos(*np.argwhere(obj == tiles.Entrance.code)[0])
        else:
            size = (height if height else cls.MAX_HEIGHT, width if width else cls.MAX_WIDTH)
            obj = np.ones(size, dtype=np.uint8).view(cls) # init full of ones (unknown) -- might change based on feedback
        # add the new attribute to the created instance
        if anchor is not None:
            obj.anchor = anchor
        elif agent_map:
            obj.anchor = cls.AGENT_ANCHOR
            obj[obj.anchor.x][obj.anchor.y] = tiles.Entrance.code
        else:
            obj.anchor = cls.ANCHOR
        # return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.anchor = getattr(obj, 'anchor', None)
        self.entrance = getattr(obj, 'entrance', None)

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
        anchor: Pos | None = None,
        turns: int | None = None,
        next_round_turns: int | None = None,
        xray_points: int | None = None,
        agent: bool = False,
        visibility: int = 2,
    ) -> None:
        self.maps = maps if maps else [Map(anchor=anchor, agent_map=agent)] # list of maps; all parts except the agent will contain only one map, the current one
        self.current_map = self.maps[-1] # the only map actually used, except for the AI (might not get the chance to actually implement that after all)

        if pos is not None:
            self.pos = pos
        elif agent:
            self.pos = self.current_map.anchor
        else:
            # Extract the position of the entrance from the map
            self.pos = self.current_map.entrance

        self.turns = turns if turns is not None else self.MAX_MOVES_PER_TURN # no. of turns for the current round
        self.next_round_turns = next_round_turns if next_round_turns is not None else self.MAX_MOVES_PER_TURN

        self.xray_points = xray_points if xray_points is not None else self.START_XRAY_POINTS

        self.portals: Dict[int, Tuple] = portals if portals else {}
        self.visibility = visibility

    # TODO: this will need to be changed -- ar fi bine sa dea return la vizibilitate. Pot sa fac chestia asta pe
    # pe server si asta ar trebui sa dea macar un raspuns de ok sau nu.
    def perform_command(self, move: str): # XXX maybe consider returning here the command result, visibility around agent etc.
        """ Applies a command on this game state """
        self.turns -= 1
        match move:
            case 'X':
                return self.use_xray()
            case 'N' | 'S' | 'E' | 'W':
                return self.move(move)
            case _:
                raise ValueError(f'"{move}" is not a valid move')

    def move(self, direction):
        """ Applies a move command on this game state (not X-Ray) """
        self.pos = Dir.move(self.pos, direction) # move into the tile, even if wall (its effect will move us back where we started from)
        effect = tiles.from_code(self.current_map[self.pos.x][self.pos.y]).visit(direction)
        if effect.activate(self) is not None:
            return '0'
        return '1'

    def decrease_next_round_turns(self, amount: int = 1):
        self.next_round_turns -= amount
        if self.next_round_turns < 0:
            self.next_round_turns = 0

    def new_round(self):
        self.turns = self.next_round_turns
        self.next_round_turns = self.MAX_MOVES_PER_TURN

    def use_xray(self):
        if self.xray_points <= 0:
            raise ValueError("No X-Ray points left to use!")
        self.xray_points -= 1
