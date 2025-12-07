import json
import os

class GameData:
    def __init__(self):
        self.items = {}
        self.i18n = {}
        self.user_items = {} # Mapping GID -> Name défini par l'utilisateur
        self.loaded = False

    def load(self):
        try:
            print("Chargement des données de jeu...")
            
            # Chargement des textes (i18n)
            if os.path.exists("dofus_data/i18n_fr.json"):
                with open("dofus_data/i18n_fr.json", "r", encoding="utf-8") as f:
                    self.i18n = json.load(f).get("texts", {})
            
            # Chargement des items officiels
            if os.path.exists("dofus_data/Items.json"):
                with open("dofus_data/Items.json", "r", encoding="utf-8") as f:
                    items_list = json.load(f)
                    for item in items_list:
                        self.items[item["id"]] = item

            # Chargement des items utilisateur (apprentissage)
            if os.path.exists("dofus_data/user_items.json"):
                with open("dofus_data/user_items.json", "r", encoding="utf-8") as f:
                    self.user_items = json.load(f)
                
            self.loaded = True
            print(f"Données chargées : {len(self.items)} items officiels, {len(self.user_items)} items appris.")
            
        except Exception as e:
            print(f"Erreur lors du chargement des données : {e}")

    def save_user_item(self, gid, name):
        """Enregistre un nouveau mapping GID -> Nom."""
        self.user_items[str(gid)] = name
        try:
            with open("dofus_data/user_items.json", "w", encoding="utf-8") as f:
                json.dump(self.user_items, f, indent=4, ensure_ascii=False)
            print(f"Item appris : {name} ({gid})")
        except Exception as e:
            print(f"Erreur sauvegarde item : {e}")

    def get_item_name(self, gid):
        if not self.loaded:
            self.load()
            
        # Priorité aux items appris par l'utilisateur
        if str(gid) in self.user_items:
            return self.user_items[str(gid)]
            
        item = self.items.get(gid)
        if item:
            name_id = item.get("nameId")
            if name_id:
                return self.i18n.get(str(name_id), f"Unknown Name ({name_id})")
        
        return None # Retourne None si inconnu pour déclencher l'apprentissage

# Singleton pour usage facile
game_data = GameData()
