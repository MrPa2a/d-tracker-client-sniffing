import json
import os
import requests
import threading
from core.d2o_reader import D2OReader
from core.d2i_reader import D2IReader
from utils.paths import get_resource_path
from utils.config import config_manager

class GameData:
    def __init__(self):
        self.items = {}
        self.i18n = {}
        self.user_items = {} # Mapping GID -> Name défini par l'utilisateur
        self.known_items = {} # Mapping GID -> Name récupéré du serveur (communauté)
        self.loaded = False
        self.d2o_reader = None
        self.item_types_reader = None
        self.d2i_reader = None

    def load(self):
        try:
            print("Chargement des données de jeu...")
            
            d2o_path = get_resource_path("dofus_data/common/Items.d2o")
            item_types_path = get_resource_path("dofus_data/common/ItemTypes.d2o")
            d2i_path = get_resource_path("dofus_data/i18n/i18n_fr.d2i")
            json_path = get_resource_path("dofus_data/i18n_fr.json")
            items_json_path = get_resource_path("dofus_data/Items.json")
            user_items_path = get_resource_path("dofus_data/user_items.json")

            # Chargement des lecteurs binaires si disponibles
            if os.path.exists(d2o_path):
                self.d2o_reader = D2OReader(d2o_path)
                print("Lecteur D2O initialisé.")
            
            if os.path.exists(item_types_path):
                self.item_types_reader = D2OReader(item_types_path)
                print("Lecteur ItemTypes D2O initialisé.")
                
            if os.path.exists(d2i_path):
                self.d2i_reader = D2IReader(d2i_path)
                print("Lecteur D2I initialisé.")

            # Chargement des textes (i18n) - Fallback JSON
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    self.i18n = json.load(f).get("texts", {})
            
            # Chargement des items officiels - Fallback JSON
            if os.path.exists(items_json_path):
                with open(items_json_path, "r", encoding="utf-8") as f:
                    items_list = json.load(f)
                    for item in items_list:
                        self.items[item["id"]] = item

            # Chargement des items utilisateur (apprentissage)
            if os.path.exists(user_items_path):
                with open(user_items_path, "r", encoding="utf-8") as f:
                    self.user_items = json.load(f)
            
            # Chargement des items communautaires
            self.fetch_remote_items()
                
            self.loaded = True
            print(f"Données chargées : {len(self.items)} items officiels (JSON), {len(self.user_items)} items appris, {len(self.known_items)} items communautaires.")
            
        except Exception as e:
            print(f"Erreur lors du chargement des données : {e}")

    def fetch_remote_items(self):
        """Récupère les items connus du serveur."""
        try:
            api_url = config_manager.get("api_url")
            if not api_url: return
            
            # Hacky way to get base url if it includes endpoint
            base_url = api_url.replace("/ingest", "")
            url = f"{base_url}/known_items"
            
            print(f"Récupération des items connus depuis {url}...")
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                remote_items = response.json()
                for item in remote_items:
                    gid = str(item["gid"])
                    name = item["name"]
                    self.known_items[gid] = name
            else:
                print(f"Erreur récupération items: {response.status_code}")
        except Exception as e:
            print(f"Impossible de récupérer les items distants: {e}")

    def save_user_item(self, gid, name):
        """Enregistre un nouveau mapping GID -> Nom."""
        self.user_items[str(gid)] = name
        try:
            user_items_path = get_resource_path("dofus_data/user_items.json")
            with open(user_items_path, "w", encoding="utf-8") as f:
                json.dump(self.user_items, f, indent=4, ensure_ascii=False)
            print(f"Item appris : {name} ({gid})")
            
            # Récupération de la catégorie
            category = self.get_item_category(gid)
            if not category:
                category = "Catégorie Inconnue"
            
            # Push to server in background
            threading.Thread(target=self._push_item_to_server, args=(gid, name, category), daemon=True).start()
                
        except Exception as e:
            print(f"Erreur sauvegarde item : {e}")

    def _push_item_to_server(self, gid, name, category):
        try:
            api_url = config_manager.get("api_url")
            if api_url:
                base_url = api_url.replace("/ingest", "")
                url = f"{base_url}/known_items"
                payload = {"gid": int(gid), "name": name, "category": category}
                requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Erreur envoi item serveur: {e}")

    def get_item_category(self, gid):
        if not self.loaded:
            self.load()
            
        if self.d2o_reader and self.item_types_reader and self.d2i_reader:
            try:
                # Get Item details (including TypeID)
                item_details = self.d2o_reader.get_details(int(gid))
                if item_details:
                    type_id = item_details.get("type_id")
                    if type_id:
                        # Get Type details (including NameID)
                        type_details = self.item_types_reader.get_details(type_id)
                        if type_details:
                            type_name_id = type_details.get("name_id")
                            if type_name_id:
                                return self.d2i_reader.get_text(type_name_id)
            except Exception as e:
                print(f"Erreur lecture catégorie pour {gid}: {e}")
        
        return None

    def get_item_name(self, gid):
        if not self.loaded:
            self.load()
            
        # Priorité aux items appris par l'utilisateur
        if str(gid) in self.user_items:
            return self.user_items[str(gid)]
            
        # Ensuite les items communautaires
        if str(gid) in self.known_items:
            return self.known_items[str(gid)]
            
        # Essai via D2O/D2I
        if self.d2o_reader and self.d2i_reader:
            try:
                name_id = self.d2o_reader.get_name_id(int(gid))
                if name_id:
                    name = self.d2i_reader.get_text(name_id)
                    if name:
                        return name
            except Exception as e:
                print(f"Erreur lecture D2O/D2I pour {gid}: {e}")

        # Fallback JSON
        item = self.items.get(gid)
        if item:
            name_id = item.get("nameId")
            if name_id:
                return self.i18n.get(str(name_id), f"Unknown Name ({name_id})")
        
        return None # Retourne None si inconnu pour déclencher l'apprentissage

# Singleton pour usage facile
game_data = GameData()
