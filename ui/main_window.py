import customtkinter as ctk
import threading
import sys
import os
import time
import webbrowser
from tkinter import messagebox
from PIL import Image, ImageTk
from ui.overlay import OverlayWindow
from core.sniffer_service import SnifferService
from core.game_data import game_data
from network.uploader import BatchUploader
from network.profiles_client import profiles_client
from utils.config import config_manager, DOFUS_SERVERS
from core.updater import UpdateManager
from core.constants import APP_NAME, VERSION, UPDATE_URL

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

class CenteredInputDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, text, prices=None, strict_mode=False):
        super().__init__(parent)
        self.title(title)
        
        # Dimensions
        width = 350
        height = 240 if prices else 180
        
        # Center on parent
        try:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
            # Ensure it's not off-screen (basic check)
            x = max(0, x)
            y = max(0, y)
        except:
            x = 100
            y = 100
            
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.resizable(False, False)
        
        self.result = None
        
        if strict_mode:
            self.attributes("-topmost", True)
            self.protocol("WM_DELETE_WINDOW", lambda: None)
        else:
            self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        self.label = ctk.CTkLabel(self, text=text, wraplength=300)
        self.label.pack(pady=(20, 10))
        
        if prices:
            price_text = "Prix détectés :\n"
            labels = ["x1", "x10", "x100", "x1000"]
            
            # Take first 4 values (one line)
            current_prices = prices[:4]
            while len(current_prices) < 4:
                current_prices.append(0)
                
            parts = []
            for i, p in enumerate(current_prices):
                if p > 0:
                    parts.append(f"{labels[i]}: {p:,}")
            
            price_text += " | ".join(parts)
            
            self.price_label = ctk.CTkLabel(self, text=price_text, wraplength=300, text_color=("gray50", "gray70"))
            self.price_label.pack(pady=(0, 10))
        
        self.entry = ctk.CTkEntry(self)
        self.entry.pack(pady=5, padx=20, fill="x")
        self.entry.bind("<Return>", self.on_ok)
        self.entry.focus_set()
        
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=10)
        
        self.ok_btn = ctk.CTkButton(self.btn_frame, text="OK", command=self.on_ok, width=100)
        self.ok_btn.pack(side="left", padx=5)
        
        self.cancel_btn = ctk.CTkButton(self.btn_frame, text="Ignorer" if strict_mode else "Annuler", command=self.on_cancel, width=100, fg_color="transparent", border_width=1)
        self.cancel_btn.pack(side="left", padx=5)
        
        self.transient(parent)
        self.grab_set()
        self.wait_window(self)
        
    def on_ok(self, event=None):
        self.result = self.entry.get()
        self.destroy()
        
    def on_cancel(self):
        self.result = None
        self.destroy()

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Theme setup
        ctk.set_appearance_mode("Dark")
        # theme_path = os.path.join(os.path.dirname(__file__), "theme.json")
        # if os.path.exists(theme_path):
        #     ctk.set_default_color_theme(theme_path)
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("600x600")
        
        # Set window icon
        try:
            # Gestion des chemins (Dev vs PyInstaller)
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            icon_ico = os.path.join(base_path, "icon.ico")
            icon_png = os.path.join(base_path, "icon.png")
            
            # Priorité au .ico pour Windows (Taskbar + Titlebar)
            if os.path.exists(icon_ico):
                self.iconbitmap(icon_ico)
            elif os.path.exists(icon_png):
                img = Image.open(icon_png)
                photo = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, photo)
        except Exception as e:
            print(f"Could not load icon: {e}")
        
        self.sniffer = None
        self.uploader = BatchUploader()
        self.overlay = None
        self.session_count = 0
        
        # Update Manager
        # On utilise l'URL définie dans constants.py
        self.updater = UpdateManager(api_url=UPDATE_URL)
        
        # Lancer la vérification des mises à jour après 1 seconde
        self.after(1000, self.check_updates)
        
        # Queue for unknown items
        self.unknown_items_queue = []
        self.is_asking_name = False
        
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
        
        # Profile selector
        self.profile_label = ctk.CTkLabel(self.config_frame, text="Profil:")
        self.profile_label.grid(row=0, column=2, padx=(20, 10), pady=5, sticky="e")
        
        self.profile_names = ["(Aucun)"]
        self.profile_combo = ctk.CTkComboBox(self.config_frame, values=self.profile_names, command=self.on_profile_change, state="readonly", width=150)
        saved_profile = config_manager.get("profile_name")
        if saved_profile:
            self.profile_combo.set(saved_profile)
        else:
            self.profile_combo.set("(Aucun)")
        self.profile_combo.grid(row=0, column=3, padx=10, pady=5, sticky="ew")
        
        # Refresh profiles button
        self.refresh_profiles_btn = ctk.CTkButton(self.config_frame, text="↻", width=30, command=self.refresh_profiles)
        self.refresh_profiles_btn.grid(row=0, column=4, padx=(0, 10), pady=5)
        
        # Load profiles in background
        threading.Thread(target=self._load_profiles_async, daemon=True).start()
        
        # Overlay Mode
        self.overlay_label = ctk.CTkLabel(self.config_frame, text="Overlay:")
        self.overlay_label.grid(row=1, column=0, padx=10, pady=5, sticky="e")
        
        self.overlay_combo = ctk.CTkComboBox(self.config_frame, values=["Auto", "Oui", "Non"], command=self.on_overlay_change, state="readonly")
        self.overlay_combo.set(config_manager.get("overlay_mode", "Auto"))
        self.overlay_combo.grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        # Strict Popup Mode
        self.strict_popup_var = ctk.BooleanVar(value=config_manager.get("strict_popup", False))
        self.strict_popup_check = ctk.CTkCheckBox(self.config_frame, text="Popup Strict (Premier plan)", variable=self.strict_popup_var, command=self.on_strict_popup_change)
        self.strict_popup_check.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        
        # Debug Mode
        self.debug_mode_var = ctk.BooleanVar(value=config_manager.get("debug_mode", False))
        self.debug_mode_check = ctk.CTkCheckBox(self.config_frame, text="Mode Debug (Logs)", variable=self.debug_mode_var, command=self.on_debug_mode_change)
        self.debug_mode_check.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        
        # Disable Upload
        self.disable_upload_var = ctk.BooleanVar(value=config_manager.get("disable_upload", False))
        self.disable_upload_check = ctk.CTkCheckBox(self.config_frame, text="Désactiver l'envoi (Debug)", variable=self.disable_upload_var, command=self.on_disable_upload_change)
        self.disable_upload_check.grid(row=4, column=1, padx=10, pady=5, sticky="w")
        
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

    def on_profile_change(self, choice):
        """Gère le changement de profil sélectionné."""
        if choice == "(Aucun)":
            config_manager.set("profile_id", None)
            config_manager.set("profile_name", None)
            print("Profil: Aucun (mode anonyme)")
        else:
            # Récupérer l'ID du profil
            profile_id = profiles_client.get_profile_id_by_name(choice)
            if profile_id:
                config_manager.set("profile_id", profile_id)
                config_manager.set("profile_name", choice)
                print(f"Profil sélectionné: {choice} ({profile_id[:8]}...)")
            else:
                print(f"⚠️ Profil '{choice}' non trouvé, ID non enregistré.")
                config_manager.set("profile_name", choice)
    
    def refresh_profiles(self):
        """Rafraîchit la liste des profils depuis le backend."""
        print("Rafraîchissement des profils...")
        threading.Thread(target=self._load_profiles_async, daemon=True).start()
    
    def _load_profiles_async(self):
        """Charge les profils de manière asynchrone."""
        try:
            names = profiles_client.get_profile_names()
            if names:
                self.profile_names = ["(Aucun)"] + names
                # Mettre à jour le combo dans le thread principal
                self.after(0, self._update_profile_combo)
                print(f"Profils chargés: {len(names)} disponibles")
            else:
                print("Aucun profil trouvé ou erreur de connexion")
        except Exception as e:
            print(f"Erreur chargement profils: {e}")
    
    def _update_profile_combo(self):
        """Met à jour le combo des profils (appelé depuis le thread principal)."""
        current = self.profile_combo.get()
        self.profile_combo.configure(values=self.profile_names)
        # Restaurer la sélection si elle existe toujours
        if current in self.profile_names:
            self.profile_combo.set(current)
        elif config_manager.get("profile_name") in self.profile_names:
            self.profile_combo.set(config_manager.get("profile_name"))
        else:
            self.profile_combo.set("(Aucun)")

    def on_overlay_change(self, choice):
        config_manager.set("overlay_mode", choice)
        self._update_overlay_visibility()
        print(f"Mode overlay changé pour : {choice}")

    def on_strict_popup_change(self):
        val = self.strict_popup_var.get()
        config_manager.set("strict_popup", val)
        print(f"Mode popup strict changé pour : {val}")

    def on_debug_mode_change(self):
        val = self.debug_mode_var.get()
        config_manager.set("debug_mode", val)
        print(f"Mode debug changé pour : {val}")

    def on_disable_upload_change(self):
        val = self.disable_upload_var.get()
        config_manager.set("disable_upload", val)
        print(f"Désactivation upload changée pour : {val}")

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
                is_running = (self.sniffer is not None and self.sniffer.running)
                self.overlay.set_running(is_running)
        else:
            self.hide_overlay()

    def toggle_sniffer(self):
        if self.sniffer and self.sniffer.running:
            self.stop_sniffer()
        else:
            self.start_sniffer()

    def start_sniffer(self):
        self.sniffer = SnifferService(
            callback=self.on_observation, 
            on_error=self.on_sniffer_error, 
            on_unknown_item=self.on_unknown_item,
            on_bank_content=self.on_bank_content
        )
        self.sniffer.start()
        self.start_btn.configure(text="Arrêter Scraping", fg_color="#da3633", hover_color="#b62324")
        print("Scraping démarré.")
        
        self._update_overlay_visibility()

    def on_bank_content(self, bank_items):
        """
        Callback appelé quand le contenu de la banque est reçu (paquet hzm).
        Envoie le contenu au serveur via l'uploader.
        """
        if not bank_items:
            return
        
        item_count = len(bank_items)
        print(f"[Banque] Contenu reçu: {item_count} items")
        
        # Afficher la notification sur l'overlay (thread-safe)
        self.after(0, lambda: self._show_bank_overlay(item_count))
        
        # Upload async via le BatchUploader
        if self.uploader:
            # Run in a separate thread to avoid blocking sniffer
            import threading
            threading.Thread(
                target=self.uploader.upload_bank_content, 
                args=(bank_items,),
                daemon=True
            ).start()
    
    def _show_bank_overlay(self, item_count):
        """Affiche la notification banque sur l'overlay (appelé depuis le thread principal)."""
        if self.overlay:
            self.overlay.show_bank_notification(item_count)

    def on_unknown_item(self, gid, prices):
        # This runs in sniffer thread. We need to ask main thread.
        # Add to queue and schedule processing
        self.unknown_items_queue.append((gid, prices))
        self.after(0, self._process_unknown_item_queue)
        
        # Return None immediately to unblock sniffer
        return None

    def _process_unknown_item_queue(self):
        if self.is_asking_name:
            return
            
        if not self.unknown_items_queue:
            return
            
        self.is_asking_name = True
        gid, prices = self.unknown_items_queue.pop(0)
        self._ask_item_name(gid, prices)

    def _ask_item_name(self, gid, prices):
        # Show dialog
        strict_mode = self.strict_popup_var.get()
        dialog = CenteredInputDialog(self, text=f"Item inconnu détecté (GID: {gid}).\nEntrez le nom de l'objet :", title="Item Inconnu", prices=prices, strict_mode=strict_mode)
        name = dialog.result
        
        if name and name.strip():
            clean_name = name.strip()
            # Save it immediately
            game_data.save_user_item(gid, clean_name)
            print(f"Item {gid} identifié comme : {clean_name}")
            
            # Process the observation now that we have the name
            try:
                # Re-use filter logic from sniffer (accessing via self.sniffer if available)
                if self.sniffer:
                    # Determine processing strategy based on item type
                    is_equipment = game_data.is_equipment(gid)
                    category = game_data.get_item_category(gid)
                    if not category:
                        category = "Catégorie Inconnue"

                    if is_equipment:
                        average = min(prices)
                    else:
                        filtered_prices, average = self.sniffer.filter.filter_prices(prices)
                    
                    if average > 0:
                        observation = {
                            "gid": gid,
                            "name": clean_name,
                            "category": category,
                            "prices": prices,
                            "average_price": average,
                            "timestamp": int(time.time() * 1000)
                        }
                        
                        self.on_observation(observation)
            except Exception as e:
                print(f"Erreur lors du traitement post-identification : {e}")
            
        self.is_asking_name = False
        # Process next item if any
        self.after(100, self._process_unknown_item_queue)

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
        
        # Add to upload queue if not disabled
        if not config_manager.get("disable_upload", False):
            self.uploader.add_observation(obs)
        else:
            print(f"[DEBUG] Upload désactivé, observation ignorée : {obs['name']} (GID: {obs['gid']})")

    def _update_ui_with_obs(self, obs):
        category = obs.get('category', 'Inconnue')
        print(f"[OBS] {obs['name']} (GID: {obs['gid']}) ({category}) - Moy: {obs['average_price']} k")
        
        # Update Session Info
        self.session_count += 1
        self.lbl_last_item.configure(text=f"Dernier item: {obs['name']}")
        self.lbl_last_price.configure(text=f"Prix: {obs['average_price']:,} k".replace(",", " "))
        self.lbl_session_count.configure(text=f"Total session: {self.session_count}")

        if self.overlay:
            self.overlay.update_info(obs['name'], obs['average_price'])
    
    def on_close(self):
        upload_queue = self.uploader.get_queue_size()
        asset_queue = game_data.asset_worker.get_queue_size() if game_data.asset_worker else 0
        total_queue = upload_queue + asset_queue

        if total_queue == 0:
            self.destroy()
            return
            
        # Show dialog
        self.show_closing_dialog(total_queue)

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
            
        upload_queue = self.uploader.get_queue_size()
        asset_queue = game_data.asset_worker.get_queue_size() if game_data.asset_worker else 0
        total_queue = upload_queue + asset_queue

        if total_queue == 0:
            self.closing_dialog.destroy()
            self.destroy()
        else:
            self.lbl_closing.configure(text=f"Envoi des données en cours...\n{total_queue} éléments restants")
            self.after(1000, self.check_upload_status)

    def force_close(self):
        self.closing_dialog.destroy()
        self.destroy()

    def check_updates(self):
        """Vérifie les mises à jour en arrière-plan"""
        def _check():
            try:
                available, remote_version = self.updater.check_for_updates()
                if available:
                    self.after(0, lambda: self.show_update_dialog(remote_version))
            except Exception as e:
                print(f"Erreur update: {e}")

        threading.Thread(target=_check, daemon=True).start()

    def show_update_dialog(self, remote_version):
        """Affiche une popup proposant la mise à jour"""
        msg = f"Une nouvelle version ({remote_version}) est disponible.\nVoulez-vous la télécharger et l'installer maintenant ?"
        if messagebox.askyesno("Mise à jour disponible", msg):
            self.start_update_process()

    def start_update_process(self):
        """Lance le téléchargement avec une barre de progression"""
        # Créer une fenêtre de progression
        progress_window = ctk.CTkToplevel(self)
        progress_window.title("Mise à jour")
        progress_window.geometry("300x150")
        progress_window.resizable(False, False)
        progress_window.transient(self)
        progress_window.grab_set()
        
        # Centrer
        try:
            x = self.winfo_x() + (self.winfo_width() // 2) - 150
            y = self.winfo_y() + (self.winfo_height() // 2) - 75
            progress_window.geometry(f"+{x}+{y}")
        except:
            pass

        lbl = ctk.CTkLabel(progress_window, text="Téléchargement en cours...")
        lbl.pack(pady=20)

        progress_bar = ctk.CTkProgressBar(progress_window)
        progress_bar.pack(pady=10, padx=20, fill="x")
        progress_bar.set(0)

        def _download():
            def update_progress(p):
                self.after(0, lambda: progress_bar.set(p))

            success = self.updater.download_and_install(progress_callback=update_progress)
            
            if not success:
                self.after(0, lambda: messagebox.showerror("Erreur", "Échec du téléchargement de la mise à jour."))
                self.after(0, progress_window.destroy)

        threading.Thread(target=_download, daemon=True).start()


    def destroy(self):
        # Clean shutdown
        if self.sniffer:
            self.sniffer.stop()
        if self.uploader:
            self.uploader.stop()
        if game_data.asset_worker:
            game_data.asset_worker.stop()
        super().destroy()
