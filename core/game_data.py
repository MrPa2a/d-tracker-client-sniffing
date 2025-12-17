import json
import os
import requests
import threading
from core.d2o_reader import D2OReader
from core.d2i_reader import D2IReader
from core.d2p_reader import D2PReader
from core.asset_worker import AssetWorker
from utils.paths import get_resource_path
from utils.config import config_manager

EQUIPMENT_CATEGORIES = {
    "Amulette", "Arc", "Baguette", "Bâton", "Dague", "Epée", "Épée", "Marteau", "Pelle", "Hache", "Faux", "Pioche", 
    "Anneau", "Ceinture", "Bottes", "Chapeau", "Cape", "Sac à dos", "Bouclier", "Dofus", "Trophée", "Prysmaradite",
    "Monture", "Familier", "Montilier", "Idole", "Compagnon"
}

class GameData:
    def __init__(self):
        self.items = {}
        self.i18n = {}
        self.user_items = {} # Mapping GID -> Name défini par l'utilisateur
        self.known_items = {} # Mapping GID -> Name récupéré du serveur (communauté)
        self.known_items_images = {} # Mapping GID -> bool (has_image)
        self.known_categories = {} # Mapping GID -> Category
        self.loaded = False
        self.d2o_reader = None
        self.item_types_reader = None
        self.d2i_reader = None
        self.d2p_reader = None
        self.asset_worker = None

    def load(self):
        try:
            print("Chargement des données de jeu...")
            
            d2o_path = get_resource_path("dofus_data/common/Items.d2o")
            item_types_path = get_resource_path("dofus_data/common/ItemTypes.d2o")
            d2i_path = get_resource_path("dofus_data/i18n/i18n_fr.d2i")
            json_path = get_resource_path("dofus_data/i18n_fr.json")
            items_json_path = get_resource_path("dofus_data/Items.json")
            user_items_path = get_resource_path("dofus_data/user_items.json")
            content_path = get_resource_path("dofus_data/content/items")

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

            if os.path.exists(content_path):
                self.d2p_reader = D2PReader(content_path)
                print("Lecteur D2P initialisé.")

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
            
            # Démarrage du worker d'assets
            self.asset_worker = AssetWorker(self)
            self.asset_worker.start()
            
            # Note: On ne vérifie plus les images manquantes au démarrage pour éviter de surcharger.
            # C'est le flux d'ingest (uploader) qui signalera les images manquantes au fur et à mesure.
            # self.check_missing_images()
                
            self.loaded = True
            print(f"Données chargées : {len(self.items)} items officiels (JSON), {len(self.user_items)} items appris, {len(self.known_items)} items communautaires.")
            
        except Exception as e:
            print(f"Erreur lors du chargement des données : {e}")

    def check_missing_images(self):
        """Vérifie les items connus qui n'ont pas d'image et les ajoute à la file."""
        count = 0
        for gid, has_image in self.known_items_images.items():
            if not has_image:
                self.queue_image_upload(gid)
                count += 1
        if count > 0:
            print(f"Planification de l'upload de {count} images manquantes.")

    def queue_image_upload(self, gid):
        """Ajoute un item à la file d'attente d'upload d'image."""
        if self.asset_worker:
            self.asset_worker.add_to_queue(gid)

    def fetch_remote_items(self):
        """Récupère les items connus du serveur."""
        try:
            api_url = config_manager.get("api_url")
            if not api_url: return
            
            # Hacky way to get base url if it includes endpoint
            base_url = api_url.replace("/ingest", "")
            url = f"{base_url}/known_items"
            
            print(f"Récupération des items connus depuis {url}...")
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                remote_items = response.json()
                for item in remote_items:
                    gid = str(item["gid"])
                    name = item["name"]
                    has_image = item.get("has_image", False)
                    category = item.get("category")
                    self.known_items[gid] = name
                    self.known_items_images[gid] = has_image
                    if category:
                        self.known_categories[gid] = category
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
            
            # Queue image upload immediately
            self.queue_image_upload(gid)
                
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
                
                # Update local cache
                self.known_categories[str(gid)] = category
        except Exception as e:
            print(f"Erreur envoi item serveur: {e}")

    def get_item_category(self, gid):
        if not self.loaded:
            self.load()
            
        # 1. Check known categories (from backend)
        if str(gid) in self.known_categories:
            return self.known_categories[str(gid)]

        # 2. Check D2O
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
        
        # 3. Fallback DofusDB
        category = self.fetch_category_from_dofusdb(gid)
        if category:
            self.known_categories[str(gid)] = category
            return category

        return None

    def is_equipment(self, gid):
        """Détermine si un item est un équipement (dont le prix varie selon les stats)."""
        category = self.get_item_category(gid)
        if category and category in EQUIPMENT_CATEGORIES:
            return True
        return False

    def get_item_icon_data(self, gid):
        """Returns the binary data of the item's icon (PNG)."""
        if not self.loaded:
            self.load()
            
        # 1. Try local extraction (D2O -> D2P)
        if self.d2o_reader and self.d2p_reader:
            try:
                details = self.d2o_reader.get_details(int(gid))
                if details and "icon_id" in details:
                    icon_id = details["icon_id"]
                    data = self.d2p_reader.get_image_data(icon_id)
                    if data:
                        return data
            except Exception as e:
                print(f"Erreur récupération icône locale pour {gid}: {e}")
        
        # 2. Fallback: DofusDB API
        return self.fetch_icon_from_dofusdb(gid)

    def fetch_icon_from_dofusdb(self, gid):
        """Fetches item icon from DofusDB API."""
        try:
            # print(f"Fetching icon for {gid} from DofusDB...")
            # 1. Get item details to find iconId
            api_url = f"https://api.dofusdb.fr/items?id={gid}"
            response = requests.get(api_url, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    item_data = data["data"][0]
                    
                    # Try direct img URL
                    img_url = item_data.get("img")
                    
                    # Or construct from iconId
                    if not img_url and "iconId" in item_data:
                        icon_id = item_data["iconId"]
                        img_url = f"https://api.dofusdb.fr/img/items/{icon_id}.png"
                        
                    if img_url:
                        # Download image
                        img_response = requests.get(img_url, timeout=5)
                        if img_response.status_code == 200:
                            return img_response.content
                            
        except Exception as e:
            print(f"Erreur récupération DofusDB pour {gid}: {e}")
            
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
        
        # Fallback DofusDB
        name = self.fetch_name_from_dofusdb(gid)
        if name:
            # Cache it in known_items to avoid re-fetching
            self.known_items[str(gid)] = name
            return name

        return None # Retourne None si inconnu pour déclencher l'apprentissage

    def fetch_name_from_dofusdb(self, gid):
        """Fetches item name from DofusDB API."""
        try:
            # print(f"Fetching name for {gid} from DofusDB...")
            api_url = f"https://api.dofusdb.fr/items?id={gid}"
            response = requests.get(api_url, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    item_data = data["data"][0]
                    if "name" in item_data and "fr" in item_data["name"]:
                        return item_data["name"]["fr"]
        except Exception as e:
            print(f"Erreur récupération nom DofusDB pour {gid}: {e}")
            
        return None

    def fetch_category_from_dofusdb(self, gid):
        """Fetches item category from DofusDB API."""
        try:
            # print(f"Fetching category for {gid} from DofusDB...")
            api_url = f"https://api.dofusdb.fr/items?id={gid}"
            response = requests.get(api_url, timeout=2)
            
            if response.status_code == 200:
                data = response.json()
                if "data" in data and len(data["data"]) > 0:
                    item_data = data["data"][0]
                    if "type" in item_data and "name" in item_data["type"] and "fr" in item_data["type"]["name"]:
                        return item_data["type"]["name"]["fr"]
        except Exception as e:
            print(f"Erreur récupération catégorie DofusDB pour {gid}: {e}")
            
        return None

# Singleton pour usage facile
game_data = GameData()
