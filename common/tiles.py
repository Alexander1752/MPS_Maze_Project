#!/usr/bin/env python3
""" This module contains classes for all the different tiles in the game """
from abc import ABC, abstractmethod
from typing import List, Dict, Type, Union

import common.effects as effects

def from_code(code: int) -> 'Tile':
    """ Create a Tile entity from a tile code """
    entity_type = CODE_TO_TYPE[code]

    if entity_type is None:
        return None

    return entity_type(code)

class Tile:
    def __init__(self, code: int | None = None):
        # Checks if the code received is the same as the one expected one
        if code is not None:
            if getattr(self, "_code", None) != code: # only available if `_code` is defined in a subclass
                raise ValueError(f'"{type(self).__name__}" has code {self._code}, but code {code} was provided')
            self._code = code

    @property # this is a property; one accesses it by writing `wall.code`, not `wall.code()`
    def code(self):
        return self._code

    @property
    def type(self):
        return type(self)

    def visit(self, direction) -> effects.Effect:
        """ Returns the effect activated by visiting this tile """
        return effects.NoEffect

class UnknownTile(Tile):
    """ Not defined in the game specs, proposed value for a tile not known by an agent """
    _code = 1

    def visit(self, direction) -> effects.Effect:
        raise NotImplementedError("Tried visiting an UnknownTile")

class Wall(Tile):
    _code = 0
    def visit(self, direction) -> effects.Effect:
        return effects.WallEffect(direction)

class Path(Tile):
    _code = 255 # nothing special to do compared to a base Entity, no other methods

class Entrance(Tile):
    _code = 64

class Exit(Tile):
    _code = 182
    def visit(self, direction) -> effects.Effect:
        pass # TODO win game here

class Xray(Tile):
    _code = 16
    def visit(self, direction) -> effects.Effect:
        return effects.XrayEffect(direction)

class Fog(Tile):
    _code = 32

class Tower(Tile):
    _code = 224

class Trap(Tile, ABC):
    def __init__(self, code: int): # must supply a code to init a `Trap` object
        super().__init__(code)
        self._n = (code - 1) % 5 + 1

    @abstractmethod
    def visit(self, direction) -> effects.Effect:
        pass # must be implemented by inheritors

class MovesTrap(Trap):
    @property
    def moves(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.MovesDecreaseEffect(direction, self._n)

class RewindTrap(Trap):
    @property
    def rewind_no(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.RewindEffect(direction, self._n)

class ForwardTrap(Trap):
    @property
    def forward_no(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.PushForwardEffect(direction, self._n)

class BackwardTrap(Trap):
    @property
    def backward_no(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.PushBackwardEffect(direction, self._n)

class Portal(Tile):
    def __init__(self, code: int, pair: Union['Portal', None] = None):
        super().__init__(code)
        self._pair = pair

    @property
    def pair(self):
        return self._pair

    def visit(self, direction) -> effects.Effect:
        pass # TODO teleport to the other portal (if its position is known)


# This is a list connecting the code of a tile to its corresponding class (see project page)
CODE_TO_TYPE: List[Type[Tile] | None] = 256 * [None]
CODE_TO_TYPE[0]   = Wall
CODE_TO_TYPE[255] = Path
CODE_TO_TYPE[64]  = Entrance
CODE_TO_TYPE[182] = Exit
# CODE_TO_TYPE[16]  = Xray
# CODE_TO_TYPE[32]  = Fog
# CODE_TO_TYPE[224] = Tower

# CODE_TO_TYPE[96:101]  =  5 * [MovesTrap]
# CODE_TO_TYPE[101:106] =  5 * [RewindTrap]
# CODE_TO_TYPE[106:111] =  5 * [ForwardTrap]
# CODE_TO_TYPE[111:116] =  5 * [BackwardTrap]
# CODE_TO_TYPE[150:170] = 20 * [Portal]

# CODE_TO_TYPE[1] = UnknownTile
