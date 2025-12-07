import customtkinter as ctk
import tkinter as tk

class OverlayWindow(ctk.CTkToplevel):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.master_window = master
        
        self.title("Dofus Tracker Overlay")
        self.geometry("300x130+20+20") # Increased height for new controls
        self.overrideredirect(True) # Remove window decorations
        self.attributes("-topmost", True) # Always on top
        self.attributes("-alpha", 0.85) # Slightly less transparent
        
        # Make it draggable
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<ButtonRelease-1>", self.stop_move)
        self.bind("<B1-Motion>", self.do_move)
        
        self.frame = ctk.CTkFrame(self, fg_color="#1a1a1a", corner_radius=10)
        self.frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Header Row: Title + Count
        self.header_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=10, pady=(5, 0))
        
        self.label_title = ctk.CTkLabel(self.header_frame, text="Dofus Tracker", font=("Roboto", 10, "bold"), text_color="gray")
        self.label_title.pack(side="left")
        
        self.count = 0
        self.label_count = ctk.CTkLabel(self.header_frame, text="Items: 0", font=("Roboto", 10), text_color="gray")
        self.label_count.pack(side="right")
        
        # Main Info: Item Name + Price
        self.info_frame = ctk.CTkFrame(self.frame, fg_color="transparent")
        self.info_frame.pack(fill="x", padx=5, pady=2)
        
        self.label_item = ctk.CTkLabel(self.info_frame, text="En attente...", font=("Roboto", 14, "bold"))
        self.label_item.pack(pady=0)
        
        self.label_price = ctk.CTkLabel(self.info_frame, text="-", font=("Roboto", 12), text_color="#4ade80")
        self.label_price.pack(pady=(0, 5))
        
        # Controls: Start/Stop Button
        self.btn_toggle = ctk.CTkButton(
            self.frame, 
            text="Démarrer", 
            command=self.toggle_scraping,
            height=24,
            font=("Roboto", 11, "bold"),
            fg_color="#2ea043", 
            hover_color="#238636"
        )
        self.btn_toggle.pack(fill="x", padx=10, pady=(0, 10))

    def update_info(self, item_name, price):
        self.label_item.configure(text=item_name)
        self.label_price.configure(text=f"{price:,} k/u".replace(",", " "))
        self.count += 1
        self.label_count.configure(text=f"Items: {self.count}")

    def toggle_scraping(self):
        # Call the main window's toggle method
        if hasattr(self.master_window, 'toggle_sniffer'):
            self.master_window.toggle_sniffer()

    def set_running(self, is_running):
        if is_running:
            self.btn_toggle.configure(text="Arrêter", fg_color="#da3633", hover_color="#b62324")
        else:
            self.btn_toggle.configure(text="Démarrer", fg_color="#2ea043", hover_color="#238636")

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
