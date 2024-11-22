import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import requests

root = tk.Tk()
root.title("Maze Viewer")

DEFAULT_WIDTH_VALUE = 1920
DEFAULT_HEIGHT_VALUE = 1080

SCALE = 1.0
WIDTH_SCALE = 1.0
HEIGHT_SCALE = 1.0

img_tk = None  # To keep a reference to the image

# Variables for dragging
drag_data = {"x": 0, "y": 0, "item": None}

)
initial_character_position = [19, 9] 

path = []


def open_image():
    global img_tk, WIDTH_SCALE, HEIGHT_SCALE, SCALE, drag_data
    
    img = Image.open("maze.png")
    width, height = img.size
    
    # Update width and height scale only on the initial load
    if SCALE == 1.0:
        WIDTH_SCALE = DEFAULT_WIDTH_VALUE / width
        HEIGHT_SCALE = DEFAULT_HEIGHT_VALUE / height

    # Resize the image based on the current scale
    new_width = int(SCALE * width * WIDTH_SCALE)
    new_height = int(SCALE * height * HEIGHT_SCALE)
    img = img.resize((new_width, new_height), Image.Resampling.NEAREST)
    
    # Convert to a format suitable for Tkinter
    img_tk = ImageTk.PhotoImage(img)
    
    # Display the image on the canvas
    if not drag_data["item"]:
        drag_data["item"] = canvas.create_image(0, 0, anchor='nw', image=img_tk)
    else:
        canvas.itemconfig(drag_data["item"], image=img_tk)
    
    canvas.config(scrollregion=canvas.bbox('all'))
    
    # Move the character to its position scaled based on zoom
    new_x = int(initial_character_position[0] * SCALE * WIDTH_SCALE)
    new_y = int(initial_character_position[1] * SCALE * HEIGHT_SCALE)
    canvas.coords(character, new_x, new_y)
    canvas.tag_raise(character)

# Function to handle arrow key movements
def move_character(event):
    step = 10 
    
    if event.keysym == 'Up':
        initial_character_position[1] -= step / (SCALE * HEIGHT_SCALE)
    elif event.keysym == 'Down':
        initial_character_position[1] += step / (SCALE * HEIGHT_SCALE)
    elif event.keysym == 'Left':
        initial_character_position[0] -= step / (SCALE * WIDTH_SCALE)
    elif event.keysym == 'Right':
        initial_character_position[0] += step / (SCALE * WIDTH_SCALE)
    
    # Update the character's position on the canvas
    new_x = int(initial_character_position[0] * SCALE * WIDTH_SCALE)
    new_y = int(initial_character_position[1] * SCALE * HEIGHT_SCALE)
    canvas.coords(character, new_x, new_y)

    # Draw the path by coloring a rectangle at the current position
    draw_path(new_x, new_y)

# Function to draw the path
def draw_path(x, y):
    path_color = 'blue'
    path_size = 5 
    
    # Draw a small rectangle (or circle) at the character's position to mark the path
    canvas.create_rectangle(x - path_size, y - path_size, x + path_size, y + path_size, fill=path_color, outline='')

    # Store the position in the path list (for potential future use)
    path.append((x, y))

# Zoom event handler
def zoom(event):
    global SCALE
    if event.delta > 0 or event.num == 4:  # Scroll up (zoom in)
        SCALE *= 1.1
    elif event.delta < 0 or event.num == 5:  # Scroll down (zoom out)
        SCALE /= 1.1
    
    SCALE = max(0.1, min(SCALE, 10))
    open_image()

# Event handler for the start of dragging
def on_press(event):
    drag_data["x"] = event.x
    drag_data["y"] = event.y

# Event handler for dragging the image
def on_drag(event):
    dx = event.x - drag_data["x"]
    dy = event.y - drag_data["y"]
    canvas.move(drag_data["item"], dx, dy)
    canvas.move(character, dx, dy)
    drag_data["x"] = event.x
    drag_data["y"] = event.y

canvas = tk.Canvas(root, width=DEFAULT_WIDTH_VALUE, height=DEFAULT_HEIGHT_VALUE)
canvas.pack(expand=True, fill='both')

character_image = Image.open("character_model.png")
character_image = character_image.resize((35, 35), Image.Resampling.NEAREST)
character_photo = ImageTk.PhotoImage(character_image)

character = canvas.create_image(19, 9, anchor=tk.NW, image=character_photo)

canvas.bind('<MouseWheel>', zoom) 
canvas.bind('<Button-4>', zoom)
canvas.bind('<Button-5>', zoom)

canvas.bind('<ButtonPress-1>', on_press)
canvas.bind('<B1-Motion>', on_drag)

root.bind('<Up>', move_character)
root.bind('<Down>', move_character)
root.bind('<Left>', move_character)
root.bind('<Right>', move_character)

open_image()

root.mainloop()
