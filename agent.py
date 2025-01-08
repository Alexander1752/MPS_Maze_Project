#!/usr/bin/env python3
import argparse
from collections import namedtuple
import logging
import time
from typing import List, Dict
import requests

from common.game_elements import Map, Pos, GameState, Dir, State
import common.tiles as tiles

logging.basicConfig(filename='log.txt',
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.DEBUG)
logger = logging.Logger(__name__, level = logging.DEBUG)

REGISTER = '/api/register_agent'
SEND_MOVES = '/api/receive_moves'
UUID = 'UUID'
X = 'x'
Y = 'y'
WIDTH = 'width'
HEIGH = 'height'
VIEW = 'view'
MOVES = 'moves'
INPUT = 'input'
COMMAND = 'command_'
END = 'end'

TOTAL_ROUNDS = 0
TOTAL_MOVES = 0
TOTAL_XRAY = 0
START_TIME = 0

Node = namedtuple("Node", "x y dir")

def get_parser():
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Start this agent.")

    # Add arguments
    parser.add_argument(
        "address",
        help="The address of the game server to connect to"
    )
    parser.add_argument(
        "port",
        nargs='?',
        help="The port of the game server to connect to"
    )

    return parser

def bfs(game_state: GameState, stack: List[Node]):
    node = stack.pop()
    stack.append(Node(node.x, node.y, Dir.NEXT[node.dir]))

    if node.dir:
        pos = Dir.move(node, node.dir)
        if game_state.current_map.in_map(pos):
            if game_state.current_map[pos] == tiles.UnknownTile.code:
                # Put back the same node to retry it if we find an UnknownTile
                stack.pop()
                stack.append(node)
                return None
            elif game_state.visited[pos].state == State.NEW:
                game_state.visited[pos].state = State.OPEN
                stack.append(Node(*pos, Dir.N))
                return node.dir
    else:
        game_state.visited[node.x][node.y].state = State.VISITED
        stack.pop()
        prev_node = stack[-1]
        undo_move = Dir.get_direction(node, prev_node)
        return undo_move

    return bfs(game_state, stack)

def connect(game_state: GameState | None, stack: List[Node] | None, url, uuid):
    response = requests.post(url + REGISTER, json={UUID: uuid} if uuid else {})
    resp: dict = response.json()

    if not uuid and UUID in resp:
        uuid = resp[UUID]

    resp.pop(UUID, None)

    if not game_state:
        if X in resp and Y in resp:
            pos = Pos(int(resp.pop(X)), int(resp.pop(Y)))
            resp['pos'] = pos

        game_state = GameState(**resp, agent=True)
        stack = [Node(game_state.pos.x, game_state.pos.y, Dir.N)]
    else:
        game_state.add_view(resp.get(VIEW, None))
    
    return game_state, uuid, stack

def send_commands(url, uuid, commands: list) -> Dict[str, str]:
    commands_str = ''.join(commands)
    logger.debug(f"Sending '{commands_str}'")
    commands_json = {INPUT : commands_str, UUID: uuid}
    response = requests.post(url + SEND_MOVES, json=commands_json)

    logger.debug(f"Received {response}")
    return response.json()

def run(game_state: GameState, stack: List[Node], url, uuid):
    global TOTAL_ROUNDS
    global TOTAL_MOVES
    global TOTAL_XRAY
    global START_TIME

    commands = []
    for _ in range(game_state.moves):
        direction = bfs(game_state, stack)
        if direction is None:
            break
        commands.append(direction)

    if len(commands) == 0 and game_state.xray_points > 0:
        commands = ['X']
        TOTAL_XRAY += 1

    TOTAL_MOVES += len(commands)
    TOTAL_ROUNDS += 1

    response = send_commands(url, uuid, commands)

    if END in response:
        end_time = time.time()
        if int(response[END]):
            print("Maze Solved!")
        else:
            print("Maze Failed...")

        print("X-Ray points used:", TOTAL_XRAY)
        print("Total moves made:", TOTAL_MOVES)
        print("Total turns:", TOTAL_ROUNDS)
        print("Time:", round(end_time - START_TIME, 2), "seconds")

        exit()

    commands = sorted([(int(key[len(COMMAND):]), val) for key, val in response.items() if key.startswith(COMMAND)])

    for _, command_dict in commands:
        command = command_dict['name']
        game_state.perform_command(command)
        game_state.add_view(command_dict[VIEW])

    game_state.next_round_moves = int(response[MOVES])    
    game_state.new_round()

def main(args=None):
    global TOTAL_ROUNDS
    global TOTAL_MOVES
    global TOTAL_XRAY
    global START_TIME

    parser = get_parser()
    args = parser.parse_args(args)

    url = args.address
    if args.port:
        url += f":{args.port}"

    if not url.startswith('http://'):
        url = 'http://' + url

    game_state, uuid, stack = connect(None, None, url, None)

    START_TIME = time.time()
    while True:
        # try:
            run(game_state, stack, url, uuid)
        # except Exception as e: # TODO
        #     logger.exception(e)
        #     # print(e, trace)
        #     connect(game_state, stack, url, uuid)

if __name__ == '__main__':
    main()
