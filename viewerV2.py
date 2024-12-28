from functools import reduce
import tkinter as tk
from tkinter import Canvas
from PIL import Image, ImageTk
import requests
import threading
import time
from sseclient import SSEClient

from typing import List, Tuple

PIXELS_PER_SQUARE = 5
PAN_SPEED = 0.05
PATH_COLOR = (0, 0, 255)

POSITION_TO_ARROW = {
    'N': 'Up',
    'S': 'Down',
    'E': 'Right',
    'W': 'Left'
}

def get_character_position():
    character_pos_response = requests.get('http://127.0.0.1:5000/character_position')
    print(character_pos_response.json())

    # Invert positions, not sure why
    app.character_position[0] = int(character_pos_response.json()['entrance_y'])
    app.character_position[1] = int(character_pos_response.json()['entrance_x'])

    maze_file = str(character_pos_response.json()['maze_file'])

    app.load_base_image(maze_file)
    app.draw_path(app.character_position[0], app.character_position[1], (255, 33, 44))

def listen_to_server():
    server_url = "http://127.0.0.1:5000/events"
    response = requests.get(server_url, stream=True)

    client = SSEClient(response)

    for event in client.events():
        app.move_character(POSITION_TO_ARROW[str(event.data)])
        print(f"Received event: {event.event}, data: {event.data}")

class ImageOverlayApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Overlay Viewer")

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
        self.pixels = []

        self.character_image = Image.open("character_model.png").convert("RGBA")
        self.character_tk_img = None

        self.composite_image = None
        self.composed_tk_image = None
        self.image_container = None

        # Track zoom scale
        self.scale = 1.0

        # Bind events
        self.root.bind("<MouseWheel>",  self.zoom)
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

        # Pan position
        self.pan_start_x = 0
        self.pan_start_y = 0

        self.character_position = [0, 0]

    def load_base_image(self, image_path):
        base_image = Image.open(image_path)
        base_image = base_image.resize((base_image.width * PIXELS_PER_SQUARE, base_image.height * PIXELS_PER_SQUARE), resample=Image.Resampling.NEAREST).convert("RGBA")

        self.images.append(base_image)
        self.modified.append(True)

        self.pixels.append(base_image.load())

        self.update_images()

    def update_images(self, rescale=False):
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

    def zoom(self, event):
        # Adjust scale
        if not isinstance(event, (int, float)):
            event = event.delta

        if event > 0:
            self.scale *= 1.1
        elif event < 0:
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
    def move_character(self, position):
        if position == 'Up':
            self.character_position[1] -= 1
        elif position == 'Down':
            self.character_position[1] += 1
        elif position == 'Left':
            self.character_position[0] -= 1
        elif position == 'Right':
            self.character_position[0] += 1
        
        # Update the character's position on the canvas
        new_x = int(self.character_position[0] * self.scale)
        new_y = int(self.character_position[1] * self.scale)
        # self.canvas.coords(character, new_x, new_y) TODO move character

        # Draw the path by coloring a rectangle at the current position
        self.draw_path(self.character_position[0], self.character_position[1])

    # Function to draw the path
    def draw_path(self, x, y, color=PATH_COLOR):
        for i in range(PIXELS_PER_SQUARE - 2):
            for j in range(PIXELS_PER_SQUARE - 2):
                self.draw_pixel(1, x * PIXELS_PER_SQUARE + 1 + i, y * PIXELS_PER_SQUARE + 1 + j, color)

        self.update_images()

    def draw_pixel(self, layer: int, x: int, y: int, color: Tuple[int, int, int], update=False):
        if len(self.images) - 1 < layer:
            # Create fully transparent image
            new_img = Image.new("RGBA", (self.images[0].width, self.images[0].height), (0, 0, 0, 0))
            self.images.append(new_img)
            self.pixels.append(new_img.load())
            self.modified.append(True)

        self.pixels[layer][x, y] = color
        
        self.modified[layer] = True

        if update:
            self.update_images()

    # def draw_square(self, layer: int, x: int, y: int)

def change_pixel():
    colors = [(255,0,0), (0,255,0), (0,0,255),(255,255,0),(255,0,255),(0,255,255)]
    while True:
        time.sleep(1)
        app.draw_pixel(1, 0, 1, colors[0], update=True)

        colors.insert(0, colors.pop())

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageOverlayApp(root)

    get_character_position()

    threading.Thread(target=listen_to_server, daemon=True).start()

    root.mainloop()
