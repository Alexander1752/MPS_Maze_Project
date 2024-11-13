"""This file contains the implementation of the server"""
import argparse
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, send, emit
from pathlib import Path
from typing import List

from common.game_elements import Map, GameState


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

# Will be used to determine the socket connection in order to identify the clients
socketio = SocketIO(server) 

MAX_COMMANDS_NO = 10
COMMAND_NAME_FIELD = 'name'
COMMAND_RESULT_FIELD = 'successful'
VIEW_FIELD = 'view'


# Default game state of the client. Used only a variable because it will
# be harder to manage multiple cleints connected to the same server, beucause
# of the project restrictions => It will need additional info sent by the client
# of to initiate sockets which work differently from the @server.route.
CLIENT_GAME_STATE = None

@server.route('/api/receive_moves', methods=['POST'])
def receive_client_moves():
    """ 
        This method will receive the moves from the agent, parse the JSON
        and create an array with the moves.
    """
    if request.is_json:
        print(request.remote_addr)
        moves = request.get_json()['input']

        if len(moves) > 10:
            return jsonify({"error": "Invalid number of moves"}), 400

        return jsonify(check_moves(moves)), 200

def create_response_json(moves: List[str]):
    """ Will create the response json, empty for now"""
    response = {}

    for i in range(MAX_COMMANDS_NO):
        command_no = f"command{i+1}"
        response[command_no] = {
            COMMAND_NAME_FIELD: "",
            COMMAND_RESULT_FIELD: "",
            VIEW_FIELD: "" # TODO: implement in GameState visibility return -- dupa ce vorbim cu baiatu la laborator
        }

        if i < len(moves):
            response[command_no][COMMAND_NAME_FIELD] = moves[i]

    return response

def check_moves(moves: List[str]):
    """"""
    response = create_response_json(moves)

    for i, move in enumerate(moves):
        command_no = f"command{i + 1}"
        response[command_no][COMMAND_RESULT_FIELD] = CLIENT_GAME_STATE.perform_command(move)
        response[command_no][VIEW_FIELD] = 'VIZIBILITATEA'

    print(CLIENT_GAME_STATE.pos)
    return response

if __name__ == '__main__':
    parser = get_parser()
    args = parser.parse_args()
    maze = Map.load_from_file(args.maze)
    CLIENT_GAME_STATE = GameState(maps=[maze])

    server.run(debug=True)
