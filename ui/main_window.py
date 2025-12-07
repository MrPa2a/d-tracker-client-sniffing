import customtkinter as ctk
import threading
import sys
import os
from tkinter import messagebox
from ui.overlay import OverlayWindow
from core.sniffer_service import SnifferService
from core.game_data import game_data
from network.uploader import BatchUploader
from utils.config import config_manager, DOFUS_SERVERS

class ConsoleRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str):
        try:
            self.text_widget.configure(state="normal")
            self.text_widget.insert("end", str)
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        except:
            pass

    def flush(self):
        pass

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Theme setup
        ctk.set_appearance_mode("Dark")
        # theme_path = os.path.join(os.path.dirname(__file__), "theme.json")
        # if os.path.exists(theme_path):
        #     ctk.set_default_color_theme(theme_path)
        ctk.set_default_color_theme("blue")

        self.title("Dofus Tracker Client V3")
        self.geometry("600x600")
        
        self.sniffer = None
        self.uploader = BatchUploader()
        self.overlay = None
        self.session_count = 0
        
        self.create_widgets()
        
        # Redirect stdout to log console
        sys.stdout = ConsoleRedirector(self.log_console)
        
        # Start uploader thread
        self.uploader.start()
        
        # Handle window closing
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # --- Header ---
        self.header_frame = ctk.CTkFrame(self, height=50)
        self.header_frame.pack(fill="x", padx=10, pady=10)
        
        self.title_label = ctk.CTkLabel(self.header_frame, text="Dofus Tracker", font=("Roboto", 20, "bold"))
        self.title_label.pack(side="left", padx=20)
        
        # --- Configuration ---
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Server
        self.server_label = ctk.CTkLabel(self.config_frame, text="Serveur:")
        self.server_label.grid(row=0, column=0, padx=10, pady=5, sticky="e")
        
        self.server_combo = ctk.CTkComboBox(self.config_frame, values=DOFUS_SERVERS, command=self.on_server_change, state="readonly")
        self.server_combo.set(config_manager.get("server", "Draconiros"))
        self.server_combo.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        # Overlay Mode
        self.overlay_label = ctk.CTkLabel(self.config_frame, text="Overlay:")
        self.overlay_label.grid(row=1, column=0, padx=10, pady=5, sticky="e")
        
        self.overlay_combo = ctk.CTkComboBox(self.config_frame, values=["Auto", "Oui", "Non"], command=self.on_overlay_change, state="readonly")
        self.overlay_combo.set(config_manager.get("overlay_mode", "Auto"))
        self.overlay_combo.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        # API Token (Hidden/Hardcoded)
        # self.token_label = ctk.CTkLabel(self.config_frame, text="API Token:")
        # self.token_label.grid(row=1, column=0, padx=10, pady=5, sticky="e")
        
        # self.token_entry = ctk.CTkEntry(self.config_frame, placeholder_text="Token d'ingestion", show="*")
        # self.token_entry.insert(0, config_manager.get("api_token", ""))
        # self.token_entry.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        # self.save_btn = ctk.CTkButton(self.config_frame, text="Sauvegarder", command=self.save_config, width=100)
        # self.save_btn.grid(row=0, column=2, rowspan=1, padx=10, pady=10)
        
        self.config_frame.columnconfigure(1, weight=1)

        # --- Controls ---
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.start_btn = ctk.CTkButton(self.control_frame, text="Démarrer Scraping", command=self.toggle_sniffer, fg_color="#2ea043", hover_color="#238636")
        self.start_btn.pack(side="left", padx=10, pady=10, expand=True, fill="x")
        
        # self.overlay_switch = ctk.CTkSwitch(self.control_frame, text="Afficher Overlay", command=self.toggle_overlay)
        # self.overlay_switch.select()
        # self.overlay_switch.pack(side="right", padx=20, pady=10)

        # --- Session Info ---
        self.info_frame = ctk.CTkFrame(self)
        self.info_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        self.info_frame.columnconfigure(0, weight=1)
        self.info_frame.columnconfigure(1, weight=1)
        self.info_frame.columnconfigure(2, weight=1)

        self.lbl_last_item = ctk.CTkLabel(self.info_frame, text="Dernier item: -", font=("Roboto", 12))
        self.lbl_last_item.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.lbl_last_price = ctk.CTkLabel(self.info_frame, text="Prix: -", font=("Roboto", 12))
        self.lbl_last_price.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.lbl_session_count = ctk.CTkLabel(self.info_frame, text="Total session: 0", font=("Roboto", 12))
        self.lbl_session_count.grid(row=0, column=2, padx=10, pady=5, sticky="e")

        # --- Logs ---
        self.log_frame = ctk.CTkFrame(self)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self.log_label = ctk.CTkLabel(self.log_frame, text="Logs", font=("Roboto", 12, "bold"))
        self.log_label.pack(anchor="w", padx=5, pady=5)
        
        self.log_console = ctk.CTkTextbox(self.log_frame, font=("Consolas", 12))
        self.log_console.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_console.configure(state="disabled")

    def on_server_change(self, choice):
        config_manager.set("server", choice)
        self.uploader.server = choice
        print(f"Serveur changé pour : {choice}")

    def on_overlay_change(self, choice):
        config_manager.set("overlay_mode", choice)
        self._update_overlay_visibility()
        print(f"Mode overlay changé pour : {choice}")

    def _update_overlay_visibility(self):
        mode = config_manager.get("overlay_mode", "Auto")
        should_show = False
        
        if mode == "Oui":
            should_show = True
        elif mode == "Non":
            should_show = False
        elif mode == "Auto":
            # Show only if sniffer is running
            should_show = (self.sniffer is not None and self.sniffer.running)
            
        if should_show:
            self.show_overlay()
            if self.overlay:
                self.overlay.set_running(True)
        else:
            self.hide_overlay()

    def toggle_sniffer(self):
        if self.sniffer and self.sniffer.running:
            self.stop_sniffer()
        else:
            self.start_sniffer()

    def start_sniffer(self):
        self.sniffer = SnifferService(callback=self.on_observation, on_error=self.on_sniffer_error, on_unknown_item=self.on_unknown_item)
        self.sniffer.start()
        self.start_btn.configure(text="Arrêter Scraping", fg_color="#da3633", hover_color="#b62324")
        print("Scraping démarré.")
        
        self._update_overlay_visibility()

    def on_unknown_item(self, gid):
        # This runs in sniffer thread. We need to ask main thread.
        self.unknown_item_gid = gid
        self.unknown_item_name = None
        self.unknown_item_event = threading.Event()
        
        # Schedule dialog on main thread
        self.after(0, self._ask_item_name)
        
        # Wait for result (blocking the sniffer thread)
        self.unknown_item_event.wait()
        
        return self.unknown_item_name

    def _ask_item_name(self):
        gid = self.unknown_item_gid
        # Show dialog
        dialog = ctk.CTkInputDialog(text=f"Item inconnu détecté (GID: {gid}).\nEntrez le nom de l'objet :", title="Item Inconnu")
        name = dialog.get_input()
        
        if name and name.strip():
            self.unknown_item_name = name.strip()
            # Save it immediately
            game_data.save_user_item(gid, name.strip())
            print(f"Item {gid} identifié comme : {name.strip()}")
            
        self.unknown_item_event.set()

    def on_sniffer_error(self, error_msg):
        self.stop_sniffer()
        print(f"ERREUR CRITIQUE: {error_msg}")
        
        msg = f"Le scraper a rencontré une erreur :\n{error_msg}\n\n"
        if "Npcap" in error_msg or "layer 2" in error_msg or "pcap" in error_msg.lower():
            msg += "Cela ressemble à un problème de pilote réseau.\n"
            msg += "Assurez-vous d'avoir installé Npcap (fichier 'npcap-installer.exe' inclus dans le dossier)."
            
        messagebox.showerror("Erreur Scraping", msg)

    def stop_sniffer(self):
        if self.sniffer:
            self.sniffer.stop()
            self.sniffer = None
        self.start_btn.configure(text="Démarrer Scraping", fg_color="#2ea043", hover_color="#238636")
        print("Scraping arrêté.")
        
        self._update_overlay_visibility()

    def toggle_overlay(self):
        # Deprecated, logic moved to _update_overlay_visibility
        pass

    def show_overlay(self):
        if not self.overlay:
            self.overlay = OverlayWindow(self)
        self.overlay.deiconify()

    def hide_overlay(self):
        if self.overlay:
            self.overlay.withdraw()

    def on_observation(self, obs):
        # This runs in the sniffer thread, so we need to schedule UI updates
        self.after(0, lambda: self._update_ui_with_obs(obs))
        
        # Add to upload queue
        self.uploader.add_observation(obs)

    def _update_ui_with_obs(self, obs):
        print(f"[OBS] {obs['name']} - Moy: {obs['average_price']} k")
        
        # Update Session Info
        self.session_count += 1
        self.lbl_last_item.configure(text=f"Dernier item: {obs['name']}")
        self.lbl_last_price.configure(text=f"Prix: {obs['average_price']:,} k".replace(",", " "))
        self.lbl_session_count.configure(text=f"Total session: {self.session_count}")

        if self.overlay:
            self.overlay.update_info(obs['name'], obs['average_price'])
    
    def on_close(self):
        queue_size = self.uploader.get_queue_size()
        if queue_size == 0:
            self.destroy()
            return
            
        # Show dialog
        self.show_closing_dialog(queue_size)

    def show_closing_dialog(self, initial_count):
        self.closing_dialog = ctk.CTkToplevel(self)
        self.closing_dialog.title("Fermeture")
        self.closing_dialog.geometry("300x150")
        self.closing_dialog.transient(self)
        self.closing_dialog.grab_set()
        
        # Center the dialog
        x = self.winfo_x() + (self.winfo_width() // 2) - 150
        y = self.winfo_y() + (self.winfo_height() // 2) - 75
        self.closing_dialog.geometry(f"+{x}+{y}")
        
        self.lbl_closing = ctk.CTkLabel(self.closing_dialog, text=f"Envoi des données en cours...\n{initial_count} éléments restants", font=("Roboto", 14))
        self.lbl_closing.pack(pady=20)
        
        self.btn_force_close = ctk.CTkButton(self.closing_dialog, text="Forcer la fermeture", command=self.force_close, fg_color="#da3633", hover_color="#b62324")
        self.btn_force_close.pack(pady=10)
        
        self.check_upload_status()

    def check_upload_status(self):
        if not self.closing_dialog.winfo_exists():
            return
            
        queue_size = self.uploader.get_queue_size()
        if queue_size == 0:
            self.closing_dialog.destroy()
            self.destroy()
        else:
            self.lbl_closing.configure(text=f"Envoi des données en cours...\n{queue_size} éléments restants")
            self.after(1000, self.check_upload_status)

    def force_close(self):
        self.closing_dialog.destroy()
        self.destroy()

    def destroy(self):
        # Clean shutdown
        if self.sniffer:
            self.sniffer.stop()
        if self.uploader:
            self.uploader.stop()
        super().destroy()
