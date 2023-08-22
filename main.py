import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import discord
import threading
from io import BytesIO
import keyboard
import os
import json

class App:
    def __init__(self, root, config_path="config.json"):
        with open(config_path, "r") as file:
            self.config = json.load(file)

        # Set the PATH
        gs_path = self.config.get('gs_path', '')
        if gs_path:
            os.environ['PATH'] += os.pathsep + gs_path

        # Variables to store values
        self.next_destination = tk.StringVar()
        self.current_position = tk.StringVar()
        self.dropdown_selection = tk.StringVar(value="Nothing")

        # References to dots for next destination and current position
        self.next_dest_dot = None
        self.current_position_dot = None

        # Reference to the arrow
        self.arrow = None

        intents = discord.Intents.default()  # Get the default Intents
        intents.messages = True  # Subscribe to the messages event
        intents.guilds = True  # Subscribe to the guilds event

        self.bot = discord.Client(intents=intents)
        self.bot_ready = False
        self.token = self.config["BOT_TOKEN"]

        threading.Thread(target=self.run_bot).start()
        self.set_root_background_to_match_theme(root)

        # Wait for the bot to be ready
        @self.bot.event
        async def on_ready():
            print(f"We have logged in as {self.bot.user}")
            self.bot_ready = True

        # Set up UI elements
        self.setup_ui(root)

    def setup_ui(self, root):
        # Frame for Destination actions
        dest_frame = ttk.Frame(root)
        dest_frame.pack(pady=15)

        self.hotkeys_active = tk.BooleanVar(value=True)
        self.hotkey_checkbutton = ttk.Checkbutton(dest_frame, text="Activate Hotkey\n[ crl + q ]", style='Switch', variable=self.hotkeys_active)
        self.hotkey_checkbutton.pack(side=tk.LEFT, padx=100)

        self.discord_push_btn = ttk.Button(dest_frame, text="Discord Notification",style='Accent.TButton', command=self.send_discord_message)
        self.discord_push_btn.pack(side=tk.RIGHT, padx=100)



        # Map
        self.image = Image.open("game_map.png").convert('RGB')
        new_width = int(self.image.width * 0.8)
        new_height = int(self.image.height * 0.8)
        self.image = self.image.resize((new_width, new_height))

        self.tk_image = ImageTk.PhotoImage(self.image)
        self.canvas = tk.Canvas(root, width=new_width, height=new_height)
        self.canvas.pack(pady=4)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # Grid layout below the map
        grid_frame = ttk.Frame(root)
        grid_frame.pack(pady=3)


        # 1st Column (Left)

        self.quick_set_btn = ttk.Button(grid_frame, text="Quick set Position",style='Accent.TButton', command=self.quick_set_position)
        self.quick_set_btn.grid(row=0, column=0, padx=50, pady=3)

        # Current Position input and button
        self.position_entry = ttk.Entry(grid_frame, textvariable=self.current_position)
        self.position_entry.grid(row=1, column=0, padx=50, pady=3)

        self.set_position_btn = ttk.Button(grid_frame, text="Set Current Position", command=self.set_current_position)
        self.set_position_btn.grid(row=2, column=0, padx=50, pady=3)


        # 2nd Column (Middle)

        # Server Dropdown
        self.server_values = self.config["server_values"]
        self.server_name = tk.StringVar()
        self.server_dropdown = ttk.Combobox(grid_frame, values=self.server_values, textvariable=self.server_name)
        self.server_dropdown.grid(row=0, column=1, padx=50, pady=3)  # Adjust row and column as necessary
        self.server_dropdown.bind("<<ComboboxSelected>>", self.update_display_from_dropdown)

        # Dino Dropdown
        self.dino_values = self.config["dino_values"]
        self.selected_dino = tk.StringVar()
        self.dino_dropdown = ttk.Combobox(grid_frame, values=self.dino_values, textvariable=self.selected_dino)
        self.dino_dropdown.grid(row=1, column=1, padx=50, pady=3)  # Adjust row and column as necessary
        self.dino_dropdown.bind("<<ComboboxSelected>>", self.update_display_from_dropdown)

        # Action Dropdown
        self.dropdown_selection = tk.StringVar()
        self.dropdown = ttk.Combobox(grid_frame, values=self.config["actions"],textvariable=self.dropdown_selection)
        self.dropdown.grid(row=2, column=1, padx=50, pady=3)
        self.dropdown.bind("<<ComboboxSelected>>", self.update_display_from_dropdown)

        # 3rd Column (Right)
        self.next_dest_btn = ttk.Button(grid_frame, text=" Set Next Destination ",style='Accent.TButton', command=self.set_next_destination)
        self.next_dest_btn.grid(row=0, column=2, padx=50, pady=3)

        self.delete_dest_btn = ttk.Button(grid_frame, text="Delete Next Destination", command=self.delete_next_destination)
        self.delete_dest_btn.grid(row=1, column=2, padx=50, pady=3)

        self.display_label = ttk.Label(grid_frame, text="")
        self.display_label.grid(row=2, column=2, padx=50, pady=3)

        self.setup_global_hotkeys()
        self.update_display()

    def set_next_destination(self):
        if not self.next_dest_dot:
            self.canvas.bind("<Button-1>", self.on_map_click)

    def delete_next_destination(self):
        if self.next_dest_dot:
            dot, circle = self.next_dest_dot  # Unpack the tuple
            self.canvas.delete(dot)
            self.canvas.delete(circle)
            self.next_dest_dot = None
            self.next_destination.set("")
            self.update_display()
        if self.arrow:
            self.canvas.delete(self.arrow)
            self.arrow = None

    def set_root_background_to_match_theme(self, root):
        style = ttk.Style()
        bg_color = style.lookup('TFrame', 'background')
        root.configure(background=bg_color)

    def set_current_position(self):
        # Delete old current position dot
        if self.current_position_dot:
            self.canvas.delete(self.current_position_dot)

        x, y = App.parse_coords(self.current_position.get())
        self.current_position.set(f"{int(x)},{int(y)}")  # Update the StringVar

        self.current_position_dot = self.draw_dot((x, y), color="blue")
        self.update_display()
        self.draw_if_both_dots_present()

    def on_map_click(self, event):
        if self.next_dest_dot:
            # If there is a dot for the next destination, remove it
            self.canvas.delete(self.next_dest_dot)

        # Translate image pixel coordinates to map coordinates
        x_ratio = (140 + 960) / self.image.width
        y_ratio = (101 + 805) / self.image.height

        x = event.y * y_ratio - 805
        y = event.x * x_ratio - 960

        self.next_destination.set(f"{int(x)},{int(y)}")

        self.next_dest_dot = self.draw_dot((x, y), color="red")
        self.canvas.unbind("<Button-1>")  # Unbind after placing the dot
        self.update_display()
        self.draw_if_both_dots_present()

    def draw_dot(self, coords, color="red", outer_circle_radius=15, outer_circle_width=3):
        # Convert map coordinates back to pixel coordinates
        x_ratio = self.image.width / (140 + 960)
        y_ratio = self.image.height / (101 + 805)

        x_pixel = (coords[1] + 960) * x_ratio
        y_pixel = (coords[0] + 805) * y_ratio

        # Draw the central dot
        radius = 2
        dot = self.canvas.create_oval(x_pixel - radius, y_pixel - radius, x_pixel + radius, y_pixel + radius,
                                      fill=color)

        # Draw the outer circle
        x1 = x_pixel - outer_circle_radius
        y1 = y_pixel - outer_circle_radius
        x2 = x_pixel + outer_circle_radius
        y2 = y_pixel + outer_circle_radius
        circle = self.canvas.create_oval(x1, y1, x2, y2, width=outer_circle_width, outline=color)

        return dot, circle
    def update_display(self):
        self.display_label.config(
            text=f"Next Destination: \n{self.next_destination.get()}")

    def update_display_from_dropdown(self, event=None):
        self.update_display()

    def quick_set_position(self):
        # Fetch value from clipboard and set it as current position
        clipboard_content = root.clipboard_get()
        try:
            x, y = App.parse_coords(clipboard_content)
            self.current_position.set(f"{int(x)},{int(y)}")
            self.set_current_position()
        except Exception as e:
            print(f"Clipboard content not in the expected format: {e}")

    def draw_arrow(self, start_coords, end_coords):
        # Convert map coordinates back to pixel coordinates for start and end points
        x_ratio = self.image.width / (140 + 960)
        y_ratio = self.image.height / (101 + 805)

        x_start_pixel = (start_coords[1] + 960) * x_ratio
        y_start_pixel = (start_coords[0] + 805) * y_ratio

        x_end_pixel = (end_coords[1] + 960) * x_ratio
        y_end_pixel = (end_coords[0] + 805) * y_ratio

        if self.arrow:
            self.canvas.delete(self.arrow)
        self.arrow = self.canvas.create_line(x_start_pixel, y_start_pixel, x_end_pixel, y_end_pixel, arrow=tk.LAST)

    def draw_if_both_dots_present(self):
        if self.next_dest_dot and self.current_position_dot:
            next_coords = self.parse_coords(self.next_destination.get())
            current_coords = self.parse_coords(self.current_position.get())
            self.draw_arrow(current_coords, next_coords)

    def send_discord_message(self):
        if not self.bot_ready:
            print("Bot is not ready yet.")
            return

        # Convert canvas contents to Postscript
        ps = self.canvas.postscript(colormode='color')

        # Convert Postscript to an Image object
        img = Image.open(BytesIO(ps.encode('utf-8')))

        # Crop the image to remove the white borders
        img = img.crop((1, 1, img.width - 4, img.height - 4))

        buffered = BytesIO()
        img.save(buffered, format="PNG")
        buffered.seek(0)

        async def send_image():
            guild = discord.utils.get(self.bot.guilds, name=self.config["discord_server_name"])
            if not guild:
                print("Server not found!")
                return

            channel = discord.utils.get(guild.text_channels, name=self.config["discord_channel"])
            if not channel:
                print("Channel not found!")
                return

            await channel.send(
                f"╔═══════════════════  new Update  ═══════════════════╗\n\n"
                f"🔵 **Current Location:** {self.current_position.get()}\n"
                f"🔴 **Next Destination:** {self.next_destination.get()}\n\n"
                f"✅ **Activity:** {self.dropdown_selection.get()}\n\n"
                f"🦖 **Dinosaur:** {self.selected_dino.get()}\n"
                f"🌍 **Server:** {self.server_name.get()}\n"
                f"||<@&1143090321396351047>||", file=discord.File(buffered, "screenshot.png")
            )
            await channel.send(
                f"╚══════════════════════════════════════════════╝"
            )


        # Use the bot loop to schedule the coroutine
        self.bot.loop.create_task(send_image())

    def run_bot(self):
        self.bot.run(self.token)

    def setup_global_hotkeys(self):
        def hotkey_action():
            # Check if the hotkeys are active
            if self.hotkeys_active.get():
                self.quick_set_position()
                self.send_discord_message()
                print("Sending Location Update")

                # Cooldown to prevent accidental triggers
                time.sleep(1)

        # Bind the hotkey directly to the function
        keyboard.add_hotkey('ctrl+q', hotkey_action)

    @staticmethod
    def parse_coords(s):
        # Remove any spaces and split by commas
        coords = s.replace(" ", "").split(",")

        # If we have more than 3 parts, assume the input is in the format x,xxx.xxx, y,yyy.yyy
        if len(coords) > 3:
            x = float(coords[0] + '.' + coords[1].split('.')[0])
            y = float(coords[2] + '.' + coords[3].split('.')[0])
        else:
            x, y = float(coords[0]), float(coords[1])

        return x, y


root = tk.Tk()
root.option_add("*tearOff", False)

# Create a style
style = ttk.Style(root)

# Import the tcl file
root.tk.call("source", "forest-dark.tcl")

# Set the theme with the theme_use method
style.theme_use("forest-dark")

root.title("Pack - Manager")
root.iconbitmap('pack_icon.ico')

app = App(root)
root.mainloop()