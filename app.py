"""This file contains the implementation of the server"""
import argparse
from flask import Flask, Response, request, jsonify
from pathlib import Path
from typing import List, Dict
import time
import queue

from common.game_elements import Map, GameState
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
UUID_CURRENT = 0
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
            # Suppose we have maximum number of next_round_turns available
            AGENTS[str(UUID_CURRENT)] = GameState(maps=[MAZE], turns=10, next_round_turns=10, xray_points=10)

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

    response['view'] = get_visibility(current_game_state)

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

        moves = request.get_json()['input']

        if len(moves) > 10:
            return jsonify({"error": "Invalid number of moves"}), 400

        return jsonify(check_moves(agent_uuid, moves)), 200

def create_response_json(moves: List[str]):
    """ Will create the response json, empty for now"""
    response = {}

    for i in range(MAX_COMMANDS_NO):
        command_no = f"command{i+1}"
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

def disguise_trap(agent_pos_x: int, agent_pos_y: int, tile_pos_x: int, tile_pos_y : int, tile: int):
    # Trap tile, no idea how to do it otherwise
    if isinstance(tiles.from_code(tile), tiles.Trap):
        if check_neigh(agent_pos_x, agent_pos_y, tile_pos_x, tile_pos_y) is True:
            return tiles.UnknownTrap.code
        return tiles.Path.code # act as path if not close enough

    return tile

def get_visibility(current_game_state: GameState):
    """Returns a matrix that represents the visible area around the player"""
    global FRIENDLY_MODE

    x = current_game_state.pos.x
    y = current_game_state.pos.y
    visibility = current_game_state.visibility

    current_visibility = [[0 for i in range(2 * visibility + 1)] for j in range(2 * visibility + 1)]

    # I want to avoid translation at matrix indexes, because of this, I will fill the
    # visibility matrix manually
    matrix_i, matrix_j = 0, 0
    for i in range(x - visibility, x + visibility + 1):
        for j in range(y - visibility, y + visibility + 1):
            if i < 0 or i >= len(current_game_state.maps[0]):
                # If I go out-of-bounds, print a wall
                current_visibility[matrix_i][matrix_j] = tiles.Wall.code
            elif j < 0 or j >= len(current_game_state.maps[0][0]):
                current_visibility[matrix_i][matrix_j] = tiles.Wall.code
            else:
                if FRIENDLY_MODE:
                    # Send the visibility as it is
                    current_visibility[matrix_i][matrix_j] = int(current_game_state.current_map[i][j])
                else:
                    # The tile is adjacent to the player pos
                    current_visibility[matrix_i][matrix_j] = int(disguise_trap(x, y, i, j, current_game_state.current_map[i][j]))
            matrix_j += 1
        matrix_i += 1
        matrix_j = 0

    return current_visibility


def check_moves(agent_uuid: str, moves: List[str]):
    """"""
    global AGENTS

    response = create_response_json(moves)
    end_reached = False

    for i, move in enumerate(moves):
        command_no = f"command{i + 1}"

        command_result = AGENTS[agent_uuid].perform_command(move)
        response[command_no][COMMAND_RESULT_FIELD] = command_result

        # check if the command 
        if command_result == '1':
            EVENT_QUEUE.put(move)

        # Check if after the previous move, the agent reached the exit
        agent_pos = AGENTS[agent_uuid].pos
        if AGENTS[agent_uuid].current_map[agent_pos] == tiles.Exit.code:
            end_reached = True
            break

        response[command_no][VIEW_FIELD] = str(get_visibility(AGENTS[agent_uuid]))

    response[MOVES_FIELD] = str(AGENTS[agent_uuid].next_round_turns)

    if end_reached:
        return {"end":"1"}

    return response

@server.route('/character_position')
def initial_data():
    response = {}

    response["enterance_x"] = str(MAZE.entrance[0])
    response["enterance_y"] = str(MAZE.entrance[1])
    response["maze_file"] = str(ARGS.maze)

    return jsonify(response)

def generate_events():
    while True:
        valid_move = EVENT_QUEUE.get()
        time.sleep(1)
        yield f"data: {valid_move}\n\n"

@server.route('/events')
def stream():
    return Response(generate_events(), content_type='text/event-stream')

if __name__ == '__main__':
    parser = get_parser()
    ARGS = parser.parse_args()
    print(ARGS.maze)
    MAZE = Map.load_from_file(ARGS.maze)

    server.run(debug=True, threaded=True)
