#!/usr/bin/env python3
import argparse
from collections import namedtuple
import logging
from typing import List, Dict
import requests
import zmq
import threading

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

AWAIT_FOR_INPUT = ''

Node = namedtuple("Node", "x y dir")

# This event will trigger when a 'Enter' is pressed in viewer
key_event = threading.Event()

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
    parser.add_argument(
        "wait_for_input",
        nargs="?",
        help="Client needs to wait for user input in order to move (Yes/ No)"
    )

    return parser

def bfs(game_state: GameState, stack: List[Node]):
    node = stack.pop()
    stack.append(Node(node.x, node.y, Dir.NEXT[node.dir]))

    if node.dir:
        pos = Dir.move(node, node.dir)
        if game_state.visited.in_map(pos):
            if game_state.current_map[pos] == tiles.UnknownTile.code:
                # Put back the same node to retry it if we find an UnknownTile
                stack.pop()
                stack.append(node)
                return None
            elif game_state.visited[pos] == State.VISITED:
                game_state.visited[pos] = State.NEW
                stack.append(Node(*pos, Dir.N))
                # print("Visiting", pos) # TODO remove
                return node.dir
    else:
        game_state.visited[node.x][node.y] = State.VISITED
        stack.pop()
        prev_node = stack[-1]
        undo_move = Dir.get_direction(node, prev_node)
        # prev_pos = Dir.move(node, undo_move) # TODO remove
        # print("Visiting", prev_pos) # TODO remove
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
    commands = []
    for _ in range(game_state.moves):
        direction = bfs(game_state, stack)
        if direction is None:
            break
        commands.append(direction)

    if len(commands) == 0 and game_state.xray_points > 0:
        commands = ['X']

    # print("Sending", commands) # TODO remove

    response = send_commands(url, uuid, commands)

    if END in response:
        print("X-Ray points used:", game_state.START_XRAY_POINTS - game_state.xray_points)
        if int(response[END]):
            print("Maze Solved!")
        else:
            print("Maze Failed...")
        exit()

    commands = sorted([(int(key[len(COMMAND):]), val) for key, val in response.items() if key.startswith(COMMAND)])

    for _, command_dict in commands:
        command = command_dict['name']
        game_state.perform_command(command)
        game_state.add_view(command_dict[VIEW])

    game_state.next_round_moves = int(response[MOVES])    
    game_state.new_round()

def main(args=None):
    global AWAIT_FOR_INPUT

    parser = get_parser()
    args = parser.parse_args(args)

    url = args.address
    if args.port:
        url += f":{args.port}"

    if not url.startswith('http://'):
        url = 'http://' + url

    AWAIT_FOR_INPUT = args.wait_for_input
    print(AWAIT_FOR_INPUT)

    game_state, uuid, stack = connect(None, None, url, None)

    while True:
        # try:
            run(game_state, stack, url, uuid)
        # except Exception as e: # TODO
        #     logger.exception(e)
        #     # print(e, trace)
        #     connect(game_state, stack, url, uuid)

if __name__ == '__main__':
    main()
