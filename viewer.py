import tkinter as tk
from PIL import Image, ImageTk
import requests
import threading
import keyboard
from sseclient import SSEClient

root = tk.Tk()
root.title("Maze Viewer")

DEFAULT_WIDTH_VALUE = 1920
DEFAULT_HEIGHT_VALUE = 1080

SCALE = 1.0
WIDTH_SCALE = 1.0
HEIGHT_SCALE = 1.0

img_tk = None

drag_data = {"x": 0, "y": 0, "item": None}

initial_character_position = [0, 0]

path = []

POSITION_TO_ARROW = {
    'N': 'Up',
    'S': 'Down',
    'E': 'Right',
    'W': 'Left'
}

MAZE_FILE = None

def get_character_position():

    character_pos_response = requests.get('http://127.0.0.1:5000/character_position')
    print(character_pos_response.json())
    
    global initial_character_position

    # Invert positions, not sure why
    initial_character_position[0] = int(character_pos_response.json()['entrance_y'])
    initial_character_position[1] = int(character_pos_response.json()['entrance_x'])
    global MAZE_FILE
    MAZE_FILE = str(character_pos_response.json()['maze_file'])


def listen_to_server():
    server_url = "http://127.0.0.1:5000/events"
    response = requests.get(server_url, stream=True)

    client = SSEClient(response)

    for event in client.events():
        move_character(POSITION_TO_ARROW[str(event.data)])
        print(f"Received event: {event.event}, data: {event.data}")

# Function to open and display the image
def open_image():
    global img_tk, MAZE_FILE, WIDTH_SCALE, HEIGHT_SCALE, SCALE, drag_data
    
    # Load the image
    img = Image.open(MAZE_FILE)
    width, height = img.size
    
    # Update width and height scale only on the initial load
    if SCALE == 1.0:
        WIDTH_SCALE = DEFAULT_WIDTH_VALUE / width
        HEIGHT_SCALE = DEFAULT_HEIGHT_VALUE / height

    # Resize the image based on the current scale
    new_width = int(SCALE * width * WIDTH_SCALE)
    new_height = int(SCALE * height * HEIGHT_SCALE)
    img = img.resize((new_width, new_height), Image.Resampling.NEAREST)
    
    img_tk = ImageTk.PhotoImage(img)
    
    if not drag_data["item"]:
        drag_data["item"] = canvas.create_image(0, 0, anchor='nw', image=img_tk)
    else:
        canvas.itemconfig(drag_data["item"], image=img_tk)
    
    canvas.config(scrollregion=canvas.bbox("all"))
    
    # Move the character to its position scaled based on zoom
    new_x = int(initial_character_position[0] * SCALE * WIDTH_SCALE)
    new_y = int(initial_character_position[1] * SCALE * HEIGHT_SCALE)
    canvas.coords(character, new_x, new_y)
    canvas.tag_raise(character)

def scroll(event):
    if event.keysym == "W":
        canvas.yview_scroll(-1, "units")
    elif event.keysym == "S":
        canvas.yview_scroll(1, "units")
    elif event.keysym == "A":
        canvas.xview_scroll(-1, "units")
    elif event.keysym == "D":
        canvas.xview_scroll(1, "units")

# Function to handle arrow key movements
def move_character(position):
    step = 40  # Number of pixels to move per key press
    
    if position == 'Up':
        initial_character_position[1] -= step / (SCALE * HEIGHT_SCALE)
    elif position == 'Down':
        initial_character_position[1] += step / (SCALE * HEIGHT_SCALE)
    elif position == 'Left':
        initial_character_position[0] -= step / (SCALE * WIDTH_SCALE)
    elif position == 'Right':
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

# Create a canvas widget
frame = tk.Frame(root)
frame.pack(fill='both', expand=True)

# Scrollbars
x_scroll = tk.Scrollbar(frame, orient="horizontal", command=lambda *args: canvas.xview(*args))
y_scroll = tk.Scrollbar(frame, orient="vertical", command=lambda *args: canvas.yview(*args))
x_scroll.pack(side="bottom", fill="x")
y_scroll.pack(side="right", fill="y")

canvas = tk.Canvas(frame, width=DEFAULT_WIDTH_VALUE, height=DEFAULT_HEIGHT_VALUE, 
                   xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
canvas.pack(side="left", fill="both", expand=True)

# Attach scrollbars to the canvas
x_scroll.config(command=canvas.xview)
y_scroll.config(command=canvas.yview)

# Load and resize the character image to 35x35 pixels
character_image = Image.open("character_model.png")
# Hardcoded sizes
character_image = character_image.resize((35, 35), Image.Resampling.NEAREST)
character_photo = ImageTk.PhotoImage(character_image)

get_character_position()

# Add the resized character to the canvas
character = canvas.create_image(initial_character_position[0], initial_character_position[1], anchor=tk.NW, image=character_photo)

# Bind arrow keys for scrolling
root.bind('<W>', scroll)
root.bind('<A>', scroll)
root.bind('<S>', scroll)
root.bind('<D >', scroll)

# Bind mouse scroll events for cross-platform compatibility
canvas.bind('<MouseWheel>', zoom)
canvas.bind('<Button-4>', zoom)
canvas.bind('<Button-5>', zoom)

# Bind mouse events for dragging
canvas.bind('<ButtonPress-1>', on_press)
canvas.bind('<B1-Motion>', on_drag)

# Bind arrow keys for character movement
root.bind('<Up>', move_character)
root.bind('<Down>', move_character)
root.bind('<Left>', move_character)
root.bind('<Right>', move_character)
# Display the initial image
open_image()

threading.Thread(target=listen_to_server, daemon=True).start()
root.mainloop()
