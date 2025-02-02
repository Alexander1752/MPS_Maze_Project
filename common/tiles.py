#!/usr/bin/env python3
""" This module contains classes for all the different tiles in the game """
from abc import ABC, abstractmethod
from typing import List, Dict, Type, Union

import common.effects as effects
import colorsys

def from_code(code: int) -> 'Tile':
    """ Create a Tile entity from a tile code """
    entity_type = CODE_TO_TYPE[code]

    if entity_type is None:
        return None

    return entity_type(code)

class Tile:
    @property
    @abstractmethod
    def color():
        pass

    def __init__(self, code: int | None = None):
        # Checks if the code received is the same as the one expected
        if code is not None:
            class_code = getattr(self, "code", None) # only available if `code` is defined in a subclass
            if class_code is not None and class_code != code:
                raise ValueError(f'"{type(self).__name__}" has code {class_code}, but code {code} was provided')
            self.code = code

    @property
    def type(self): # this is a property; one accesses it by writing `wall.type`, not `wall.type()`
        return type(self)

    def visit(self, direction) -> effects.Effect:
        """ Returns the effect activated by visiting this tile """
        return effects.NoEffect(direction)

class UnknownTile(Tile):
    """ Not defined in the game specs, proposed value for a tile not known by an agent """
    code = 1
    color = (0, 0, 0) # placeholder

    def visit(self, direction) -> effects.Effect:
        raise NotImplementedError("Tried visiting an UnknownTile")

class Wall(Tile):
    code = 0
    color = (0, 0, 0)

    def visit(self, direction) -> effects.Effect:
        return effects.WallEffect(direction)

class Path(Tile):
    code = 255 # nothing special to do compared to a base Entity, no other methods
    color = (255, 255, 255)

class Entrance(Tile):
    code = 64
    color = (40, 90, 43)

class Exit(Tile):
    code = 182
    color = (80, 180, 86)
    def visit(self, direction) -> effects.Effect:
        return effects.NoEffect(direction) # TODO maybe change later

class Xray(Tile):
    code = 16
    color = Path.color
    def visit(self, direction) -> effects.Effect:
        return effects.XrayEffect(direction)

class Fog(Tile):
    code = 32
    color = (128, 128, 128)

class Tower(Tile):
    code = 224
    color = (0, 255, 255)

class Trap(Tile, ABC):
    @property
    @abstractmethod
    def base_code():
        pass

    def __init__(self, code: int): # must supply a code to init a `Trap` object
        if code in list(range(1, 6)):
            code = code + self.base_code

        super().__init__(code)
        self._n = (code - 1) % 5 + 1

    @property
    def n(self):
        return self._n

    @abstractmethod
    def visit(self, direction) -> effects.Effect:
        pass # must be implemented by inheritors

class UnknownTrap(Trap):
    base_code = code = 90
    color = (32, 32, 32)

    def visit(self, direction) -> effects.Effect:
        raise NotImplementedError("Tried visiting an UnknownTrap")

class MovesTrap(Trap):
    base_code = 95
    color = (255, 0, 255)
    @property
    def moves(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.MovesDecreaseEffect(direction, self._n)

class RewindTrap(Trap):
    base_code = 100
    color = (255, 0, 0)
    @property
    def rewind_no(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.RewindEffect(direction, self._n)

class ForwardTrap(Trap):
    base_code = 105
    color = (9, 255, 20)
    @property
    def forward_no(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.PushForwardEffect(direction, self._n)

class BackwardTrap(Trap):
    base_code = 110
    color = (0, 0, 255)
    @property
    def backward_no(self):
        return self._n

    def visit(self, direction) -> effects.Effect:
        return effects.PushBackwardEffect(direction, self._n)

def hsv2rgb(h,s,v):
    return tuple(round(i * 255) for i in colorsys.hsv_to_rgb(h,s,v))

class Portal(Tile):
    color = (54, 192, 241)
    _first_portal = None
    _last_portal = None

    @staticmethod
    def first_portal():
        if Portal._first_portal is None:
            Portal._first_portal = CODE_TO_TYPE.index(Portal)
        return Portal._first_portal

    @staticmethod
    def last_portal():
        if Portal._last_portal is None:
            Portal._last_portal = len(CODE_TO_TYPE) - 1 - CODE_TO_TYPE[::-1].index(Portal)
        return Portal._last_portal

    def __init__(self, code: int, pair: Union['Portal', None] = None):
        super().__init__(code)
        self._pair = pair

        if code > Portal.last_portal() or code < Portal.first_portal():
            raise ValueError(f'"Portal" should have code between {Portal.first_portal()} and {Portal.last_portal()}, but code {code} was provided')

        self.color = hsv2rgb((code - Portal.first_portal()) / (Portal.last_portal() - Portal.first_portal() + 1), 1, 1)

    @property
    def pair(self):
        return self._pair

# This is a list connecting the code of a tile to its corresponding class (see project page)
CODE_TO_TYPE: List[Type[Tile] | None] = 256 * [None]
CODE_TO_TYPE[0]   = Wall
CODE_TO_TYPE[255] = Path
CODE_TO_TYPE[64]  = Entrance
CODE_TO_TYPE[182] = Exit

CODE_TO_TYPE[16]  = Xray
CODE_TO_TYPE[32]  = Fog
CODE_TO_TYPE[224] = Tower

CODE_TO_TYPE[90] = UnknownTrap
CODE_TO_TYPE[96:101]  =  5 * [MovesTrap]
CODE_TO_TYPE[101:106] =  5 * [RewindTrap]
CODE_TO_TYPE[106:111] =  5 * [ForwardTrap]
CODE_TO_TYPE[111:116] =  5 * [BackwardTrap]
CODE_TO_TYPE[150:170] = 20 * [Portal]

CODE_TO_TYPE[1] = UnknownTile
