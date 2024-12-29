"""This file contains the implementation of the server"""
import argparse
from flask import Flask, Response, request, jsonify
from pathlib import Path
from typing import List, Dict
import time
import queue

from common.game_elements import Map, GameState, Pos, serialize_view, deserialize_view
import common.tiles as tiles


def get_parser():
    # Create the argument parser
    parser = argparse.ArgumentParser(description="Create a maze with specified width and height and save it to the specified file.")

    # Add arguments
    parser.add_argument(
        "--maze", "-m",
        type=Path,
        required=True,
        help="Path of the maze to be loaded."
    )

    return parser

server = Flask(__name__)

MAX_COMMANDS_NO = 10
COMMAND_NAME_FIELD = 'name'
COMMAND_RESULT_FIELD = 'successful'
VIEW_FIELD = 'view'
MOVES_FIELD = 'moves'
UUID_CURRENT = 0 # TODO change to a more suitable, random UUID scheme
AGENTS : Dict[str, GameState] = {} # dict to identify agents using uuid
AGENTS_TIME : Dict[str, float] = {} # dict to identify the agent and the connection time
FRIENDLY_MODE = False
MAZE = None
ARGS = None
EVENT_QUEUE = queue.Queue()

# Maximum time allowed for a client in seconds. It will take in account the time of
# the client's first request until a request that comes after this value.
MAX_TIME_ALLOWED = int(300)

# Default game state of the client. Used only a variable because it will
# be harder to manage multiple cleints connected to the same server, beucause
# of the project restrictions => It will need additional info sent by the client
# of to initiate sockets which work differently from the @server.route.
CLIENT_GAME_STATE = None

@server.route('/api/register_agent', methods=['POST'])
def register_agent():
    global UUID_CURRENT
    global MAZE
    global FRIENDLY_MODE

    if request.is_json:
        if not request.get_json(): # Request is empty
            UUID_CURRENT += 1
            # Suppose we have maximum number of next_round_moves available
            AGENTS[str(UUID_CURRENT)] = GameState(maps=[MAZE], moves=10, next_round_moves=10, xray_points=10)

            # Register the first time the client contacted the server
            AGENTS_TIME[str(UUID_CURRENT)] = int(time.time())
            
            if FRIENDLY_MODE:
                return jsonify(create_friendly_response()), 200
            else:
                return jsonify({'UUID': str(UUID_CURRENT)}), 200

    return jsonify({}), 400

def create_friendly_response():
    global MAZE
    global UUID_CURRENT
    global AGENTS

    response = {
        'UUID': str(UUID_CURRENT),
        'x': '',
        'y': '',
        'width': '',
        'height': '',
        'view': '',
        'moves': '10' # default number of moves
    }
    current_game_state = AGENTS[str(UUID_CURRENT)]

    response['x'] = str(int(current_game_state.pos.x))
    response['y'] = str(int(current_game_state.pos.y))

    current_map = current_game_state.current_map

    response['width'] = str(len(current_map[0]))
    response['height'] = str(len(current_map))

    response['view'] = disguise_traps(current_game_state)

    return response


@server.route('/api/receive_moves', methods=['POST'])
def receive_client_moves():
    """ 
        This method will receive the moves from the agent, parse the JSON
        and create an array with the moves.
    """
    if request.is_json:
        print(request.remote_addr)
        agent_uuid = request.get_json()['UUID']

        if time.time() - AGENTS_TIME[agent_uuid] > MAX_TIME_ALLOWED:
            # TODO: when a client gets over the allowed time limit, maybe remove the UUID and reset the connection
            return jsonify({'end':'0'}), 200

        AGENTS_TIME[agent_uuid] = time.time()

        moves = request.get_json()['input']

        if len(moves) > 10:
            return jsonify({"error": "Invalid number of moves"}), 400

        return jsonify(check_moves(agent_uuid, moves)), 200

def create_response_json(moves: List[str]):
    """ Will create the response json, empty for now"""
    response = {}

    for i in range(MAX_COMMANDS_NO):
        command_no = f"command_{i+1}"
        response[command_no] = {
            COMMAND_NAME_FIELD: "",
            COMMAND_RESULT_FIELD: "",
            VIEW_FIELD: "",
        }

        if i < len(moves):
            response[command_no][COMMAND_NAME_FIELD] = moves[i]

    return response


def check_neigh(curr_i: int, curr_j: int, searched_i: int, searched_j: int):
    """Check if a position is one tile away from the current tile"""
    neighs = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]

    for (i, j) in neighs:
        ni, nj = i + curr_i, j + curr_j
        if searched_i == ni and searched_j == nj:
            return True

    return False

def disguise_traps(game_state: GameState):
    global FRIENDLY_MODE

    view = game_state.view()
    # Assume we receive a square matrix with an odd length
    agent_pos = Pos(len(view) // 2, len(view) // 2)

    if FRIENDLY_MODE:
        return serialize_view(view)

    for i in range(len(view)):
        for j in range(len(view)):
            # Trap tile, no idea how to do it otherwise
            if isinstance(tiles.from_code(view[i][j]), tiles.Trap):
                if check_neigh(agent_pos.x, agent_pos.y, i, j) is True:
                    # The tile is adjacent to the player pos
                    view[i][j] = tiles.UnknownTrap.code

    return serialize_view(view)

def check_moves(agent_uuid: str, moves: List[str]):
    """"""
    global AGENTS

    response = create_response_json(moves)
    end_reached = False

    for i, move in enumerate(moves):
        command_no = f"command_{i + 1}"

        command_result = AGENTS[agent_uuid].perform_command(move)
        response[command_no][COMMAND_RESULT_FIELD] = str(1 if command_result is None else command_result)

        # # check if the command
        # if command_result == '1' and move in ['N', 'S', 'E', 'W']:
        #     EVENT_QUEUE.put(move)

        EVENT_QUEUE.put(AGENTS[agent_uuid].pos)

        # Check if after the previous move, the agent reached the exit
        agent_pos = AGENTS[agent_uuid].pos
        if AGENTS[agent_uuid].current_map[agent_pos] == tiles.Exit.code:
            end_reached = True
            break

        response[command_no][VIEW_FIELD] = disguise_traps(AGENTS[agent_uuid])

    response[MOVES_FIELD] = str(AGENTS[agent_uuid].next_round_moves)
    AGENTS[agent_uuid].new_round()

    if end_reached:
        return {"end":"1"}

    return response

@server.route('/character_position')
def initial_data():
    response = {}

    response["entrance_x"] = str(MAZE.entrance[0])
    response["entrance_y"] = str(MAZE.entrance[1])
    response["maze_file"] = str(ARGS.maze)

    return jsonify(response)

def generate_events():
    while True:
        pos: Pos = EVENT_QUEUE.get()
        time.sleep(0.1)
        yield f"data: {pos.x},{pos.y}\n\n"

@server.route('/events')
def stream():
    return Response(generate_events(), content_type='text/event-stream')

def main(args=None):
    global ARGS
    global MAZE

    parser = get_parser()
    ARGS = parser.parse_args(args)

    # TODO add the possibility to generate a new maze when no maze argument is provided
    print(ARGS.maze)
    MAZE = Map.load_from_file(ARGS.maze)

    server.run(debug=True, threaded=True) # TODO add port arg

if __name__ == '__main__':
    main()