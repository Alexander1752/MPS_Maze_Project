#!/usr/bin/env python3
from collections import namedtuple
from enum import Enum
import numpy as np
import logging
from PIL import Image
from typing import List, Dict, Tuple, Union

import common.tiles as tiles

Pos = namedtuple("Pos", "x y")

class State(int, Enum):
    NEW     = 0
    OPEN    = 1
    VISITED = 2
    WALL    = 3

class VisitNode:
    def __init__(self, *, w_visited=False, e_visited=False, n_visited=False, s_visited=False, parent: Pos | None=None, state: State=State.NEW):
        self.w_visited = w_visited
        self.e_visited = e_visited
        self.n_visited = n_visited
        self.s_visited = s_visited

        self.parent = parent
        self.state = state

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
        nparr: np.ndarray | None = None, # harta, matrice care tine codurile de la 0-255
        prev_map: Union['Map', None] = None,
        prev_visited: Union[np.ndarray[VisitNode], None] = None,
        prev_pos: Pos | None = None,
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

        exit_tiles = list(np.argwhere(obj == tiles.Exit.code))
        if len(exit_tiles):
            obj.exit = Pos(*exit_tiles[0])

        obj.portal2maps = {}
        obj.prev_map = prev_map
        obj.prev_visited = prev_visited
        obj.prev_pos = prev_pos

        # return the newly created object:
        return obj

    def __array_finalize__(self, obj):
        if obj is None: return
        self.anchor:   Pos | None = getattr(obj, 'anchor', None)
        self.entrance: Pos | None = getattr(obj, 'entrance', None)
        self.exit:     Pos | None = getattr(obj, 'exit', None)

        self.portal2maps: Dict[Pos, Tuple[Map, np.ndarray[VisitNode]]] = getattr(obj, 'portal2map', {})
        self.prev_map: Map = getattr(obj, 'prev_map', None)
        self.prev_visited: np.ndarray[VisitNode] = getattr(obj, 'prev_visited', None)
        self.prev_pos: Pos = getattr(obj, 'prev_pos', None)

    def in_map(self, *args):
        if len(args) == 1:
            pos = args[0]
        else:
            pos = Pos(args[0], args[1])

        return pos.x >= 0 and pos.y >= 0 and pos.x < len(self) and pos.y < len(self[0])

    def write_to_file(self, path):
        img = Image.fromarray(self, mode="L")  # "L" mode is for 8-bit grayscale
        img.save(path)

    @property
    def traps(self):
        return list(map(lambda l: Pos(l[0], l[1]), np.argwhere((self >= 96) & (self < 116))))

    @property
    def portals(self):
        portals_pos = list(np.argwhere((self >= 150) & (self <= 169)))

        portal_codes: Dict[int, List[Pos]] = {}
        for portal in portals_pos:
            portal = Pos(portal[0], portal[1])
            if self[portal] not in portal_codes:
                portal_codes[self[portal]] = [portal]
            else:
                portal_codes[self[portal]].append(portal)

        portals_dict: Dict[Pos, Pos] = {}
        for portal_pair in portal_codes.values():
            if len(portal_pair) < 2:
                portals_dict[portal_pair[0]] = None
            else:
                portals_dict[portal_pair[0]] = portal_pair[1]
                portals_dict[portal_pair[1]] = portal_pair[0]

        return portals_dict

    def to_color_image(self):
        rgb = np.zeros((*self.shape, 3), dtype=np.uint8)

        for code, type in enumerate(tiles.CODE_TO_TYPE):
            if type:
                rgb[self == code] = tiles.from_code(code).color

        return Image.fromarray(rgb).convert("RGBA")

    @classmethod
    def load_from_file(cls, path):
        return cls.load_from_image(Image.open(path))

    @classmethod
    def load_from_image(cls, img: Image.Image):
        img = img.convert("L") # Ensure it's in grayscale mode ("L")
        return cls(nparr=np.array(img, dtype=np.uint8))

class GameState:
    MAX_MOVES_PER_TURN = 10
    START_XRAY_POINTS = 10
    MAX_NUM_PREV_MOVES = 100

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
            self.visited = np.array([VisitNode() for _ in range(np.prod(self.current_map.shape))]).reshape(self.current_map.shape)

        self.agent = agent

        self.moves = int(moves) if moves is not None else self.MAX_MOVES_PER_TURN # no. of turns for the current round
        self.next_round_moves = next_round_moves if next_round_moves is not None else self.MAX_MOVES_PER_TURN

        self.xray_points = xray_points if xray_points is not None else self.START_XRAY_POINTS

        self.portals: Dict[int, Tuple] = portals if portals else {}

        self._visibility = visibility
        self.xray_on = 0

        # List of previous moves (used for rewinding)
        self.prev_moves = []

        # List of visited positions in the last move (since the last perform_command() call)
        self.visited_pos = []

        # Used for disabling dropping moves when hitting a wall due to a trap
        self.reduce_moves_switch = True

        # Used for undoing a MovesDecreaseTrap when rewinding such trap
        self.in_rewind = False

        # Used to mark the first trap stepped on in a move
        self.first_trap: Pos | None = None

        self.add_view(view)

    def add_view(self, view: str, *, pos: Pos | None = None):
        if not view:
            return

        if pos is None:
            pos = self.pos

        view: List[List[int]] = deserialize_view(view)
        visibility = len(view) // 2
        view_i = 0
        view_j = 0
        for i in range(pos.x - visibility, pos.x + visibility + 1):
            for j in range(pos.y - visibility, pos.y + visibility + 1):
                if self.current_map.in_map(i, j):
                    old_val = tiles.from_code(self.current_map[i][j])
                    new_val = tiles.from_code(view[view_i][view_j])

                    if isinstance(new_val, tiles.Wall) or isinstance(old_val, tiles.Wall):
                        self.visited[i][j].state = State.WALL

                    if isinstance(old_val, tiles.Trap):
                        if isinstance(old_val, tiles.UnknownTrap) and new_val != tiles.Path.code:
                            # Only overwrite a Trap if it is with more information than what's already available
                            self.current_map[i][j] = new_val.code
                    else:
                        # if it's not a trap, write whatever we received
                        self.current_map[i][j] = new_val.code

                view_j += 1
            view_j = 0
            view_i += 1

    # TODO: this will need to be changed -- ar fi bine sa dea return la vizibilitate. Pot sa fac chestia asta pe
    # pe server si asta ar trebui sa dea macar un raspuns de ok sau nu.
    def perform_command(self, move: str, *, views: list=None, max_num_traps_redirect:int|None=None): # XXX maybe consider returning here the command result, visibility around agent etc.
        """ Applies a command on this game state """
        self.moves -= 1
        self.xray_on = 0
        self.prev_moves.append(move)
        self.prev_moves = self.prev_moves[-self.MAX_NUM_PREV_MOVES:] # limit to 100 prev moves
        self.visited_pos = []

        match move:
            case 'X': # TODO support greater size xray
                return self.use_xray(views)
            case 'N' | 'S' | 'E' | 'W':
                return self.move(move, views=views)
            case 'P':
                return self.enter_portal(views=views)
            case '': # empty command
                self.prev_moves.pop() # remove empty command if it was just added
                return
            case _:
                raise ValueError(f'"{move}" is not a valid move')

    def move(self, direction, *, views: list=None, max_num_traps_redirect:int|None=None):
        """ Applies a move command on this game state (not X-Ray) """

        if max_num_traps_redirect is not None and max_num_traps_redirect < 0:
            raise ValueError("Too many trap redirects")

        self.pos = Dir.move(self.pos, direction) # move into the tile, even if wall (its effect will move us back where we started from)

        if not self.visited_pos or self.visited_pos[-1] != self.pos:
            self.visited_pos.append(self.pos)

        if views and self.current_map[self.pos] != tiles.Wall.code:
            self.add_view(views.pop(0))

        logging.debug(f'Moved into tile {self.current_map[self.pos]}')
        effect = tiles.from_code(self.current_map[self.pos]).visit(direction)
        if effect.activate(self, views=views, max_num_traps_redirect=max_num_traps_redirect) is not None:
            return '0'
        return '1'

    def enter_portal(self, *, views: list=None):
        if tiles.CODE_TO_TYPE[self.current_map[self.pos]] != tiles.Portal:
            self.decrease_next_round_moves()
            return '0' # failure

        if self.agent:
            if self.current_map.anchor == self.pos: # going back in the origin portal
                self.pos = self.current_map.prev_pos
                self.visited = self.current_map.prev_visited
                self.current_map = self.current_map.prev_map
            else:
                if self.pos not in self.current_map.portal2maps:
                    new_map = Map(agent_map=True, prev_map=self.current_map, prev_visited=self.visited, prev_pos=self.pos)
                    new_map[new_map.anchor] = self.current_map[self.pos]

                    new_visited = np.array([VisitNode() for _ in range(np.prod(new_map.shape))]).reshape(new_map.shape)

                    self.current_map.portal2maps[self.pos] = (new_map, new_visited)

                self.current_map, self.visited = self.current_map.portal2maps[self.pos]
                self.pos = self.current_map.anchor
        else: # server
            pair = self.current_map.portals[self.pos]
            self.pos = pair

        self.visited_pos.append(self.pos)
        if views is not None:
            self.add_view(views.pop(0))
        return '1' # success

    def decrease_next_round_moves(self, amount: int = 1):
        self.next_round_moves -= amount
        if self.next_round_moves < 0:
            self.next_round_moves = 0

    def new_round(self):
        self.moves = self.next_round_moves
        self.next_round_moves = self.MAX_MOVES_PER_TURN

    def use_xray(self, views: list=None):
        if views is not None:
            self.add_view(views.pop(0))

        self.visited_pos.append(self.pos)
        if self.xray_points <= 0:
            self.decrease_next_round_moves()
            return '0'
            raise ValueError("No X-Ray points left to use!")
        self.xray_points -= 1
        self.xray_on += 1
        return '1'

    def visibility(self, pos: Pos | None = None):
        if pos is None:
            pos = self.pos

        visibility = self._visibility
        tile_type = tiles.CODE_TO_TYPE[self.current_map[pos]]

        if tile_type == tiles.Fog:
            visibility -= 1
        elif tile_type == tiles.Tower:
            visibility += 1

        visibility += self.xray_on

        return visibility

    def view(self, pos: Pos | None = None):
        """Returns a matrix that represents the visible area around the player"""
        if pos is None:
            pos = self.pos

        x = pos.x
        y = pos.y
        visibility = self.visibility(pos)

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

def serialize_view(view: List[List[int]]) -> str:
    return '[' + "; ".join([", ".join([str(i) for i in row]) for row in view]) + ']'

def deserialize_view(view: str) -> List[List[int]]:
    chars = "[],; "
    view = view.strip(chars)

    view_str = [row.strip(chars).split(",") for row in view.split(";")]
    view_int = [[int(s.strip(chars)) for s in row] for row in view_str]

    return view_int
