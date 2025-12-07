import json
import os
from d2o_reader import D2OReader
from d2i_reader import D2IReader

class GameData:
    def __init__(self):
        self.items = {}
        self.i18n = {}
        self.user_items = {} # Mapping GID -> Name défini par l'utilisateur
        self.loaded = False
        self.d2o_reader = None
        self.d2i_reader = None

    def load(self):
        try:
            print("Chargement des données de jeu...")
            
            # Chargement des lecteurs binaires si disponibles
            if os.path.exists("dofus_data/common/Items.d2o"):
                self.d2o_reader = D2OReader("dofus_data/common/Items.d2o")
                print("Lecteur D2O initialisé.")
                
            if os.path.exists("dofus_data/i18n/i18n_fr.d2i"):
                self.d2i_reader = D2IReader("dofus_data/i18n/i18n_fr.d2i")
                print("Lecteur D2I initialisé.")

            # Chargement des textes (i18n) - Fallback JSON
            if os.path.exists("dofus_data/i18n_fr.json"):
                with open("dofus_data/i18n_fr.json", "r", encoding="utf-8") as f:
                    self.i18n = json.load(f).get("texts", {})
            
            # Chargement des items officiels - Fallback JSON
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
            print(f"Données chargées : {len(self.items)} items officiels (JSON), {len(self.user_items)} items appris.")
            
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
