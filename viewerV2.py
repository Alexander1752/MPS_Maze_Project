from functools import reduce
import json
import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk, ImageDraw
import requests
import threading
from sseclient_local import SSEClient
import sys

from typing import List, Tuple

from common.game_elements import Map
import common.tiles as tiles

PIXELS_PER_SQUARE = 5
PAN_SPEED = 0.05
REFRESH_INTERVAL = 200 # ms

IMG_LAYER = 0
PATH_LAYER = 1
TRAP_LAYER = 2
FOG_LAYER = -1 # last layer, indexing a Python list

PATH_COLOR = (127, 121, 0)
AGENT_COLOR = (255, 242, 0)
TRAP_VALUE_COLOR = (0, 0, 0)
TRANSPARENT = (0, 0, 0, 0)
OPAQUE_FOG = (63, 63, 63, 255)

POSITION_TO_ARROW = {
    'N': 'Up',
    'S': 'Down',
    'E': 'Right',
    'W': 'Left'
}

class ViewerApp:
    def __init__(self, root: tk.Tk, await_for_input, fog=False):
        self.root = root
        self.root.title("Viewer")
        self.fog = fog

        # Initialize canvas and scrollbars
        self.canvas = Canvas(self.root, bg="black")
        self.h_scroll = tk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.v_scroll = tk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.canvas.yview)

        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        # Place canvas and scrollbars
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.h_scroll.grid(row=1, column=0, sticky="ew")
        self.v_scroll.grid(row=0, column=1, sticky="ns")

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Variables for images
        self.images: List[Image.ImageFile.ImageFile] = []
        self.modified: List[bool] = []
        self.pixels: List[ImageDraw.ImageDraw] = []

        self.character_image = Image.open("character_model.png").convert("RGBA")
        self.character_tk_img = None

        self.composite_image = None
        self.composed_tk_image = None
        self.image_container = None

        # Track zoom scale
        self.scale = 1.0

        # Bind events
        self.root.bind("<MouseWheel>",  self.zoom)
        self.canvas.bind('<Button-4>',  self.zoom)
        self.canvas.bind('<Button-5>',  self.zoom)
        self.root.bind("<Button-1>",    self.start_pan)
        self.root.bind("<B1-Motion>",   self.pan)
        self.root.bind("<KP_Add>",      self.zoom_in)
        self.root.bind("<KP_Subtract>", self.zoom_out)

        # Bind arrow keys for scrolling
        self.root.bind('<W>', self.scroll)
        self.root.bind('<A>', self.scroll)
        self.root.bind('<S>', self.scroll)
        self.root.bind('<D>', self.scroll)

        # Bind arrow keys for character movement
        self.root.bind('<Up>', self.move_character)
        self.root.bind('<Down>', self.move_character)
        self.root.bind('<Left>', self.move_character)
        self.root.bind('<Right>', self.move_character)

        if await_for_input:
            self.button = tk.Button(self.root, text="Input", command=self.on_click_button)
            self.button.grid(row=2, column=0, columnspan=2, pady=5)

        # Pan position
        self.pan_start_x = 0
        self.pan_start_y = 0

        self.character_position = [0, 0]
        self.uuid = ""
        self.maze = None

    def load_maze(self, image_path):
        self.maze = Map.load_from_file(image_path)

        color_maze = self.maze.to_color_image()
        color_maze = color_maze.resize((color_maze.width * PIXELS_PER_SQUARE, color_maze.height * PIXELS_PER_SQUARE), resample=Image.Resampling.NEAREST).convert("RGBA")
        self.images.append(color_maze)
        self.modified.append(True)

        self.pixels.append(ImageDraw.Draw(color_maze))

        self.update_images(rescale=False, auto_refresh=True)

    def update_images(self, rescale=False, auto_refresh=False):
        # Resize images
        if not self.images:
            return

        self.modified.extend([True] * (len(self.images) - len(self.modified)))

        if any(self.modified) or self.composite_image is None:
            self.composite_image = reduce(Image.alpha_composite, self.images)

        if rescale or any(self.modified):
            self.modified = [False] * len(self.modified)
            resized_composite = self.composite_image.resize(
                (int(self.composite_image.width * self.scale), int(self.composite_image.height * self.scale)),
                resample=Image.Resampling.NEAREST
            )

            self.composed_tk_image = ImageTk.PhotoImage(resized_composite)

            if self.image_container is None:
                self.image_container = self.canvas.create_image(0, 0, image=self.composed_tk_image, anchor="nw", tags="overlay")
            else:
                self.canvas.itemconfig(self.image_container, image=self.composed_tk_image)

            # Update scroll region
            self.canvas.config(scrollregion=(0, 0, resized_composite.width, resized_composite.height))

        if auto_refresh:
            self.root.after(REFRESH_INTERVAL, self.update_images, False, True)

    def zoom(self, event):
        # Adjust scale
        num = 0
        if not isinstance(event, (int, float)):
            num = event.num
            event = event.delta

        if event > 0 or num == 4:
            self.scale *= 1.1
        elif event < 0 or num == 5:
            self.scale /= 1.1

        self.update_images(rescale=True)

    def zoom_in(self, event=None):
        self.zoom(1)

    def zoom_out(self, event=None):
        self.zoom(-1)

    def start_pan(self, event):
        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def pan(self, event):
        dx = (self.pan_start_x - event.x) * PAN_SPEED
        dy = (self.pan_start_y - event.y) * PAN_SPEED

        self.canvas.xview_scroll(int(dx), "units")
        self.canvas.yview_scroll(int(dy), "units")

        self.pan_start_x = event.x
        self.pan_start_y = event.y

    def scroll(self, event):
        if event.keysym == "W":
            self.canvas.yview_scroll(-1, "units")
        elif event.keysym == "S":
            self.canvas.yview_scroll(1, "units")
        elif event.keysym == "A":
            self.canvas.xview_scroll(-1, "units")
        elif event.keysym == "D":
            self.canvas.xview_scroll(1, "units")
        
    # Function to handle arrow key movements
    def move_character(self, x_or_pos, y=None):
        # Draw the path by coloring a rectangle at the current position
        self.draw_path(self.character_position[0], self.character_position[1])
        if y == None:
            position = x_or_pos
            if position == 'Up':
                self.character_position[1] -= 1
            elif position == 'Down':
                self.character_position[1] += 1
            elif position == 'Left':
                self.character_position[0] -= 1
            elif position == 'Right':
                self.character_position[0] += 1
        else:
            self.character_position[1] = int(x_or_pos)
            self.character_position[0] = int(y)

        # TODO replace with agent image
        self.draw_path(self.character_position[0], self.character_position[1], color=AGENT_COLOR)

        # update xray points
        x = self.character_position[1]
        y = self.character_position[0]

        if self.maze[x, y] == tiles.Xray.code:
            self.draw_xray_points([(x, y)], tiles.Xray.color)
            self.maze[x, y] = tiles.Path.code

    def new_layer(self, color=TRANSPARENT):
        # Create fully transparent image
        new_img = Image.new("RGBA", (self.images[0].width, self.images[0].height), color)
        self.images.append(new_img)
        self.pixels.append(ImageDraw.Draw(new_img))
        self.modified.append(True)

    # Function to draw the path
    def draw_path(self, x, y, color=PATH_COLOR):
        self.pixels[PATH_LAYER].rectangle([
            (x * PIXELS_PER_SQUARE + 1, y * PIXELS_PER_SQUARE + 1),
            ((x + 1) * PIXELS_PER_SQUARE - 2, (y + 1) * PIXELS_PER_SQUARE - 2),
        ], color)

        self.modified[PATH_LAYER] = True

    def draw_traps(self):
        traps = self.maze.traps
        if len(traps) == 0:
            return

        coords = [(1, 1), (3, 1), (1, 3), (3, 3), (2, 2)]
        points = []

        self.new_layer()
        for (y, x) in traps:
            n = tiles.from_code(self.maze[y, x]).n
            points.extend([(x * PIXELS_PER_SQUARE + i, y * PIXELS_PER_SQUARE + j) for i, j in coords[:n]])

        self.pixels[TRAP_LAYER].point(points, TRAP_VALUE_COLOR)
        self.modified[TRAP_LAYER] = True
    
    def draw_portals(self):
        portals = list(self.maze.portals.keys())
        if len(portals) == 0:
            return

        coords = [(1, 0), (2, 0), (3, 0), (0, 1), (0, 2), (0, 3), (4, 1), (4, 2), (4, 3), (1, 4), (2, 4), (3, 4)]

        for (y, x) in portals:
            color = tiles.from_code(self.maze[y, x]).color
            points = [(x * PIXELS_PER_SQUARE + i, y * PIXELS_PER_SQUARE + j) for i, j in coords]
            self.pixels[PATH_LAYER].point(points, (255 - color[0], 255 - color[1], 255 - color[2]))
        
        self.modified[PATH_LAYER] = True

    def draw_xray_points(self, xray_points = None, color = (255, 0, 0)):
        if xray_points is None:
            xray_points = self.maze.xrays_on_map

        if len(xray_points) == 0:
            return

        coords = [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (0, 4), (1, 3), (3, 1), (4, 0)]
        points = []

        for (y, x) in xray_points:
            points.extend([(x * PIXELS_PER_SQUARE + i, y * PIXELS_PER_SQUARE + j) for i, j in coords])

        self.pixels[IMG_LAYER].point(points, color)
        self.modified[IMG_LAYER] = True

    def draw_fog(self):
        self.new_layer(color=OPAQUE_FOG)

    def erase_fog(self, tiles: List[Tuple[int, int]]):
        first_pos = (tiles[1] * PIXELS_PER_SQUARE, tiles[0] * PIXELS_PER_SQUARE)
        second_pos = ((tiles[3] + 1) * PIXELS_PER_SQUARE - 1, (tiles[2] + 1) * PIXELS_PER_SQUARE - 1)
        self.pixels[FOG_LAYER].rectangle([first_pos, second_pos], TRANSPARENT)

    def on_click_button(self):
        print("GATA")
        requests.get(f'http://127.0.0.1:5000/wait_for_input/{self.uuid}')

def get_character_position(app: ViewerApp):
    character_pos_response = requests.get('http://127.0.0.1:5000/character_position')
    # print(character_pos_response.json())

    # Invert positions, not sure why
    app.character_position[0] = int(character_pos_response.json()['entrance_y'])
    app.character_position[1] = int(character_pos_response.json()['entrance_x'])

    maze_file = str(character_pos_response.json()['maze_file'])
    app.uuid = str(character_pos_response.json()['agent_uuid'])

    # Maze layer
    app.load_maze(maze_file)

    # Paths + agent layer
    app.new_layer()
    app.draw_path(app.character_position[0], app.character_position[1], AGENT_COLOR)
    app.draw_path(app.maze.exit.y, app.maze.exit.x, (0, 255, 0))

    # Traps layer
    app.draw_traps()

    # Portals layer
    app.draw_portals()

    # Xray points
    app.draw_xray_points()

    if app.fog:
        app.draw_fog()

def listen_to_server(app: ViewerApp):
    # print(app)

    server_url = f"http://127.0.0.1:5000/events/{app.uuid}"

    events = SSEClient(server_url)

    for event in events:
        event = json.loads(event.data)

        if 'pos' in event:
            # Format is {"pos": [x, y]}
            app.move_character(event['pos'][0], event['pos'][1])
        
        if app.fog and 'view' in event:
            # Format is {"view": [x1, y1, x2, y2]}
            app.erase_fog(event['view'])

        # print(f"Received event: {event.event}, data: {event.data}") TODO: uncomment

main_root = None

def create_viewer(await_for_input=False, fog=False):
    global main_root
    is_first = False

    if main_root is None:
        is_first = True
        main_root = tk.Tk()
        # Hides tk window
        main_root.withdraw()

    # Create a new Toplevel window for the viewer
    root = tk.Toplevel(main_root)
    app = ViewerApp(root, await_for_input, fog)
    get_character_position(app)

    if is_first:
        threading.Thread(target=listen_to_server, args=(app,), daemon=True).start()
        root.mainloop()
    else:
        listen_to_server(app)

if __name__ == "__main__":
    # Simple running, either run with 1 argument, which loads a maze and shows it, or 2 arguments, which saves the maze in color
    root = tk.Tk()
    app = ViewerApp(root, False)

    app.load_maze(sys.argv[1])
    app.draw_xray_points()
    app.new_layer()
    app.draw_path(app.maze.entrance.y, app.maze.entrance.x, AGENT_COLOR)
    app.draw_path(app.maze.exit.y, app.maze.exit.x, (0, 255, 0))
    app.draw_traps()
    app.draw_portals()

    if len(sys.argv) == 3:
        app.update_images(rescale=True)
        app.composite_image.save(sys.argv[2])
    else:
        app.root.mainloop()
