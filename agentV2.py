#!/usr/bin/env python3
import argparse
from collections import OrderedDict, deque
from copy import copy
import logging
from typing import List, Dict, Set, Any, TypeVar
import requests

from common.game_elements import Pos, GameState, Dir, State, VisitNode , Map
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
        "--wait-for-input", "-w",
        action="store_true",
        help="Makes the agent wait for ENTER to be pressed before sending commands to the server"
    )
    parser.add_argument(
        "--manual", "-m",
        action="store_true",
        help="Run in manual mode (the user plays as the agent)"
    )

    return parser

def visit_node(node: VisitNode, dir):
    match dir:
        case Dir.N: node.n_visited = True
        case Dir.S: node.s_visited = True
        case Dir.W: node.w_visited = True
        case Dir.E: node.e_visited = True
        case 'P':   node.p_visited = True

T = TypeVar('T')
def get_temp(map, dict: Dict[Pos, T], pos: Pos) -> T:
    if pos not in dict:
        dict[pos] = copy(map[pos])

    return dict[pos]

def check_path(map: Map, visited, temp_visited: Dict[Pos, VisitNode], pos: Pos, parent: Pos):
    if map[pos] == tiles.Exit.code:
        return True

    DISCOVERED = tiles.CODE_TO_TYPE.index(None) # use an unused value to mark discovered nodes
    discovered: Dict[Pos, int] = {}
    discovered[pos] = DISCOVERED
    discovered[parent] = DISCOVERED # deny going to the parent

    queue = deque([pos])

    while queue:
        pos = queue.popleft()

        for dir in [Dir.N, Dir.S, Dir.W, Dir.E]:
            neigh = Dir.move(pos, dir)

            if not map.in_map(neigh):
                continue

            neigh_code = get_temp(map, discovered, neigh)
            discovered[neigh] = DISCOVERED

            if get_temp(visited, temp_visited, pos).state == State.VISITED:
                neigh_code = DISCOVERED

            if neigh_code in [tiles.Exit.code, tiles.UnknownTile.code]:
                return True

            if neigh_code != DISCOVERED and tiles.CODE_TO_TYPE[neigh_code] not in [tiles.Wall, tiles.BackwardTrap, tiles.RewindTrap]:
                queue.append(neigh)

        if tiles.CODE_TO_TYPE[map[pos]] == tiles.Portal:
            portal_pair = map.portals[pos]
            if portal_pair is None:
                return True

            portal_pair_node = get_temp(visited, temp_visited, portal_pair)
            if portal_pair_node.state == State.NEW:
                return True

    return False


def dfs(game_state: GameState, temp_visited: Dict[Pos, VisitNode], visited_pos: List[Pos], pos: Pos):
    # If we just stepped on a trap (that is not a MovesTrap), don't make another move until we find out what just happened
    tile = tiles.from_code(game_state.current_map[pos])
    if isinstance(tile, tiles.Trap) and tile.type != tiles.MovesTrap:
        return None

    node: VisitNode = get_temp(game_state.visited, temp_visited, pos)
    dirs = []

    if not node.w_visited:
        dirs.append(Dir.W)
    if not node.e_visited:
        dirs.append(Dir.E)
    if not node.n_visited:
        dirs.append(Dir.N)
    if not node.s_visited:
        dirs.append(Dir.S)
    if not node.p_visited and tiles.CODE_TO_TYPE[game_state.current_map[pos]] == tiles.Portal:
        dirs.append('P')
    else:
        node.p_visited = True

    for dir in dirs:
        if dir == 'P':
            node.p_visited = True

            if game_state.current_map[game_state.current_map.anchor] == game_state.current_map[pos]:
                # found the same code portal that we originally entered in, avoid infinite teleport loop
                continue

            portal_pair = game_state.current_map.portals[pos]

            if portal_pair is not None and get_temp(game_state.visited, temp_visited, portal_pair).state != State.NEW:
                continue

            return dir

        new_pos = Dir.move(pos, dir)
        if new_pos != node.parent and game_state.current_map.in_map(new_pos):
            # Don't make another move if we find an UnknownTile, wait for more info from the server
            if game_state.current_map[new_pos] == tiles.UnknownTile.code:
                # if this is the last direction and it is unknown, wait for more info; otherwise, try another (possibly known) direction
                if dirs[-1] == dir or (dirs[-1] == 'P' and dirs[-2] == dir):
                    return None
                continue

            new_pos_node = get_temp(game_state.visited, temp_visited, new_pos)

            if tiles.CODE_TO_TYPE[game_state.current_map[new_pos]] in [tiles.BackwardTrap, tiles.RewindTrap]:
                new_pos_node.state = State.WALL

            if new_pos_node.state in [State.NEW, State.OPEN] and check_path(game_state.current_map, game_state.visited, temp_visited, new_pos, pos):
                visited_pos.append(new_pos)
                new_pos_node.state = State.OPEN

                if new_pos_node.parent is None:
                    new_pos_node.parent = pos

                print("Visiting", new_pos) # TODO remove
                return dir

        visit_node(node, dir)
        return dfs(game_state, temp_visited, visited_pos, pos)

    node.state = State.VISITED
    prev_pos: Pos = node.parent

    if prev_pos is None and tiles.CODE_TO_TYPE[game_state.current_map[pos]] == tiles.Portal:
        # We got here by this portal, so enter it again to return
        return 'P'

    undo_move = Dir.get_direction(pos, prev_pos)
    visited_pos.append(prev_pos)
    print("Visiting", prev_pos) # TODO remove
    return undo_move

def connect(game_state: GameState | None, url, uuid, discovered_forward_traps: Set[Pos]):
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
    else:
        game_state.add_view(resp.get(VIEW, None))

    if discovered_forward_traps is None:
        discovered_forward_traps: Set[Pos] = set()

    return game_state, uuid, discovered_forward_traps

def send_commands(url, uuid, commands: list) -> Dict[str, Any]:
    commands_str = ''.join(commands)
    logger.debug(f"Sending '{commands_str}'")
    commands_json = {INPUT : commands_str, UUID: uuid}

    response = requests.post(url + SEND_MOVES, json=commands_json)

    logger.debug(f"Received {response}")
    return response.json()

def run(game_state: GameState, url, uuid, discovered_forward_traps: Set[Pos], wait_for_input=False):
    commands = []
    pos = game_state.pos
    temp_visited: Dict[Pos, VisitNode] = OrderedDict()
    visited_pos: List[Pos] = []
    for _ in range(game_state.moves):
        direction = dfs(game_state, temp_visited, visited_pos, pos)
        if direction is None:
            break
        commands.append(direction)
        if direction == 'P':
            break
        pos = Dir.move(pos, direction)

    if len(commands) == 0:
        if game_state.xray_points > 0:
            commands = ['X']
        else:
            # Just try a random move and see what happens
            commands = [Dir.N]
            # TODO take into account the fact that the move might've actually taken place (didn't hit a wall)

    if wait_for_input:
        print("Sending", commands)
        input("Press Enter to continue...")

    response = send_commands(url, uuid, commands)

    if END in response:
        print("X-Ray points used:", game_state.START_XRAY_POINTS - game_state.xray_points)
        if int(response[END]):
            print("Maze Solved!")
        else:
            print("Maze Failed...")
        exit()

    commands = sorted([(int(key[len(COMMAND):]), val) for key, val in response.items() if key.startswith(COMMAND)])
    game_state.first_trap = None
    all_visited_pos = []
    prev_pos = game_state.pos

    # Save these in case we step in a portal
    current_map = game_state.current_map
    current_visited = game_state.visited
    for _, command_dict in commands:
        views = command_dict[VIEW]
        command = command_dict['name']

        if isinstance(views, str):
            views = [views]

        game_state.perform_command(command, views=views)
        all_visited_pos.extend(game_state.current_move_visited_pos)

    # Check if last command was entering a portal
    if command == 'P' and command_dict["successful"] == "1":
        entered_portal = True
        all_visited_pos.pop() # remove portal pos (will be treated separately)
    else:
        entered_portal = False

    visited_after_first_trap = []
    if game_state.first_trap is not None:
        # Extract positions visited/influenced by trap(s)
        index_of_first_trap = all_visited_pos.index(game_state.first_trap)
        visited_after_first_trap = all_visited_pos[index_of_first_trap:]

        # Only keep the positions visited before the trap(s), the other ones are no longer valid
        index_of_first_trap_in_temp_visited = visited_pos.index(game_state.first_trap)
        visited_pos = visited_pos[:index_of_first_trap_in_temp_visited]

        if visited_pos:
            prev_pos = visited_pos[-1] # previous position before the trap

    # Commit changes in temp_visited up until this point, due to them being accurate, before trap(s)
    for pos in visited_pos:
        if pos in temp_visited:
            current_visited[pos] = temp_visited[pos]

    # Commit changes for the positions after the first trap (if any)
    new_forward_traps: Set[Pos] = set()
    for pos in visited_after_first_trap:
        if current_visited[pos].state == State.NEW:
            current_visited[pos].state = State.OPEN
            current_visited[pos].parent = prev_pos

        # Special case for the forward trap: if going over it again and we end up on it's parent, it is visited
        if tiles.CODE_TO_TYPE[current_map[prev_pos]] == tiles.ForwardTrap:
            new_forward_traps.add(prev_pos)
            if prev_pos in discovered_forward_traps and pos == current_visited[prev_pos].parent and prev_pos == game_state.first_trap:
                current_visited[prev_pos].state = State.VISITED
                visit_node(current_visited[pos], Dir.get_direction(pos, prev_pos))

        prev_pos = pos

    # Add new forward traps to the discovered set
    discovered_forward_traps |= new_forward_traps

    if entered_portal:
        if game_state.visited[game_state.pos].parent is not None:
            # We went back through a portal - mark it as visited
            game_state.visited[game_state.pos].p_visited = True

    game_state.next_round_moves = int(response[MOVES])    
    game_state.new_round()

    if game_state.current_map.entrance is not None and game_state.visited[game_state.current_map.entrance].state == State.VISITED:
        print("Failed... Impossible Maze?")
        exit()

def run_manual(game_state: GameState, url, uuid):
    commands = list(input("Give the list of commands to be sent: "))
    commands = commands[:game_state.MAX_MOVES_PER_TURN]

    response = send_commands(url, uuid, commands)

    if END in response:
        if int(response[END]):
            print("Maze Solved!")
        else:
            print("Maze Failed...")
        exit()

def main(args=None):
    parser = get_parser()
    args = parser.parse_args(args)

    url = args.address
    if args.port:
        url += f":{args.port}"

    if not url.startswith('http://'):
        url = 'http://' + url

    game_state, uuid, discovered_forward_traps = connect(None, url, None, None)
    while True:
        # try:
        if args.manual:
            run_manual(game_state, url, uuid)
        else:
            run(game_state, url, uuid, discovered_forward_traps, args.wait_for_input)
        # except Exception as e: # TODO
        #     logger.exception(e)
        #     # print(e, trace)
        #     connect(game_state, stack, url, uuid)

if __name__ == '__main__':
    main()
