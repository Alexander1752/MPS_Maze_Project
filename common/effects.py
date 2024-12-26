#!/usr/bin/env python3
from abc import ABC, abstractmethod

import common.game_elements as ge

class Effect(ABC):
    def __init__(self, direction) -> None:
        # the direction from which the agent comes is needed in many effects, so it is a parameter
        self._direction = direction

    @abstractmethod
    def activate(self, game_state: 'ge.GameState', max_num_traps_redirect:int|None=None):
        """ Activates this effect on the supplied GameState """
        pass

class NoEffect(Effect):
    def activate(self, game_state: 'ge.GameState', max_num_traps_redirect:int|None=None):
        pass

class WallEffect(Effect):
    reduce_moves_switch = True
    
    def activate(self, game_state: 'ge.GameState', max_num_traps_redirect:int|None=None):
        game_state.move(ge.Dir.OPPOSITE[self._direction])

        if self.reduce_moves_switch:
            game_state.decrease_next_round_moves()

        return '0' # Hit a wall => unsuccessful

class TrapEffect(Effect, ABC):
    def __init__(self, direction, n: int) -> None:
        super().__init__(direction)
        self._n = n # this memorizes the strength of the effect [1-5]

class MovesDecreaseEffect(TrapEffect):
    def activate(self, game_state: 'ge.GameState', max_num_traps_redirect:int|None=None):
        game_state.decrease_next_round_moves(self._n)

class XrayEffect(Effect):
    def activate(self, game_state: 'ge.GameState', max_num_traps_redirect:int|None=None):
        game_state.xray_points += 1

class RewindEffect(TrapEffect):
    pass # TODO implement RewindEffect

class PushForwardEffect(TrapEffect):
    def activate(self, game_state: 'ge.GameState', max_num_traps_redirect:int|None=None):
        max_num_traps_redirect = None if max_num_traps_redirect is None else max_num_traps_redirect - 1
    
        # Keeps it from dropping the number of moves of the agent for hitting walls due to trap
        WallEffect.reduce_moves_switch = False

        for _ in range(self._n):
            game_state.move(self._direction, max_num_traps_redirect)

        WallEffect.reduce_moves_switch = True

class PushBackwardEffect(PushForwardEffect):
    def __init__(self, direction, n: int) -> None:
        # simply changed the direction of the previous class to implement this one
        super().__init__(ge.Dir.OPPOSITE[direction], n)
