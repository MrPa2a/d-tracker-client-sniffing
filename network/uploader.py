import threading
import time
import requests
import json
from datetime import datetime, timezone
from utils.config import config_manager
from core.game_data import game_data

class BatchUploader(threading.Thread):
    def __init__(self, batch_size=50, interval=10):
        super().__init__()
        self.queue = []
        self.lock = threading.Lock()
        self.running = False
        self.batch_size = batch_size
        self.interval = interval
        self.daemon = True
        
        self.api_url = config_manager.get("api_url")
        self.api_token = config_manager.get("api_token")
        self.server = config_manager.get("server")

    def add_observation(self, obs):
        """
        Transforme l'observation brute du sniffer vers le format attendu par l'API
        et l'ajoute à la file d'attente.
        """
        # Re-fetch config in case it changed
        self.server = config_manager.get("server")
        
        if not self.server:
            print("[Uploader] Serveur non configuré, observation ignorée.")
            return

        # Calcul du nombre de lots (prix non nuls)
        nb_lots = len([p for p in obs['prices'] if p > 0])
        
        # Formatage de la date en ISO 8601 UTC (ex: 2023-10-27T10:00:00Z)
        captured_dt = datetime.fromtimestamp(obs['timestamp'] / 1000.0, tz=timezone.utc)
        captured_iso = captured_dt.isoformat().replace("+00:00", "Z")

        payload = {
            "item_name": obs['name'],
            "ankama_id": obs.get('gid'),
            "server": self.server,
            "captured_at": captured_iso,
            "price_unit_avg": obs['average_price'],
            "nb_lots": nb_lots,
            "source_client": "dofus-tracker-client-v3",
            "client_version": "3.0.0",
            "raw_item_name": obs['name'], # Pour l'instant identique
            "category": obs.get('category')
        }
        
        with self.lock:
            self.queue.append(payload)

    def run(self):
        self.running = True
        print("[Uploader] Service de téléversement démarré.")
        
        last_upload_time = time.time()
        
        while self.running:
            time.sleep(1)
            
            should_upload = False
            with self.lock:
                queue_len = len(self.queue)
                time_since_last = time.time() - last_upload_time
                
                if queue_len >= self.batch_size or (queue_len > 0 and time_since_last >= self.interval):
                    should_upload = True
            
            if should_upload:
                self.upload_batch()
                last_upload_time = time.time()

    def stop(self):
        self.running = False

    def get_queue_size(self):
        with self.lock:
            return len(self.queue)

    def upload_batch(self):
        batch = []
        with self.lock:
            # On prend tout ce qu'il y a (ou limité au batch_size si on veut être strict)
            batch = self.queue[:]
            self.queue = []
            
        if not batch:
            return

        # Force reload config from disk to pick up changes
        try:
            config_manager.load()
        except Exception as e:
            print(f"[Uploader] Erreur rechargement config: {e}")

        # Refresh token from config
        self.api_token = config_manager.get("api_token")

        if not self.api_token:
            print(f"[Uploader] ⚠️ Erreur: Token API manquant dans config.json. Envoi annulé.")
            # Debug: print current config keys/values to understand why
            # print(f"[Debug] Config actuelle: {config_manager.config}")
            return

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }
            
            # Debug (à retirer plus tard)
            # print(f"[Uploader] Token utilisé: {self.api_token[:5]}...{self.api_token[-5:]}")

            # print(f"[Uploader] Envoi vers {self.api_url}")
            response = requests.post(self.api_url, json=batch, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"[Uploader] {len(batch)} observations envoyées avec succès.")
                
                # Traitement des images manquantes demandées par le serveur
                try:
                    resp_json = response.json()
                    if "missing_images" in resp_json and isinstance(resp_json["missing_images"], list):
                        missing_gids = resp_json["missing_images"]
                        if missing_gids:
                            print(f"[Uploader] Le serveur demande {len(missing_gids)} images manquantes.")
                            for gid in missing_gids:
                                game_data.queue_image_upload(gid)
                except Exception as e:
                    print(f"[Uploader] Erreur lecture réponse JSON: {e}")
                    
            else:
                print(f"[Uploader] Erreur envoi ({response.status_code}): {response.text}")
                if response.status_code == 401:
                     print(f"[Uploader] Vérifiez que votre token dans config.json correspond à celui du backend.")
                # En cas d'erreur, on pourrait remettre dans la queue, mais attention aux boucles infinies
                # Pour l'instant on perd les données (ou on pourrait les dumper dans un fichier fail)
                
        except Exception as e:
            print(f"[Uploader] Exception réseau: {e}")
            # Remettre dans la queue ?
            # with self.lock:
            #    self.queue.extend(batch)

    def stop(self):
        self.running = False
        # Tenter un dernier upload ?
        self.upload_batch()

    def upload_bank_content(self, bank_items):
        """
        Envoie le contenu de la banque au serveur.
        
        Args:
            bank_items: Liste de {gid: int, quantity: int, uid: int}
        """
        if not bank_items:
            print("[Uploader] Contenu banque vide, envoi annulé.")
            return False
        
        # Vérifier si l'upload est désactivé
        if config_manager.get("disable_upload", False):
            print(f"[Uploader] Upload désactivé, banque non envoyée ({len(bank_items)} items)")
            return False
            
        # Refresh config
        try:
            config_manager.load()
        except Exception as e:
            print(f"[Uploader] Erreur rechargement config: {e}")
            
        self.api_token = config_manager.get("api_token")
        self.server = config_manager.get("server")
        profile_id = config_manager.get("profile_id")
        profile_name = config_manager.get("profile_name")
        
        if not profile_id:
            print(f"[Uploader] ⚠️ Aucun profil sélectionné. La banque sera stockée sans profil.")
        else:
            print(f"[Uploader] Profil: {profile_name} ({profile_id[:8]}...)")
        
        if not self.api_token:
            print("[Uploader] ⚠️ Token API manquant. Banque non envoyée.")
            return False
            
        if not self.server:
            print("[Uploader] ⚠️ Serveur non configuré. Banque non envoyée.")
            return False
        
        # Préparer le payload (camelCase pour le backend)
        captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        payload = {
            "server": self.server,
            "profileId": profile_id,  # Peut être None si non configuré
            "items": [
                {"gid": item["gid"], "quantity": item["quantity"]}
                for item in bank_items
            ],
            "capturedAt": captured_at
        }
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }
            
            # Endpoint /api/user?resource=bank
            bank_url = self.api_url.replace("/ingest", "/user?resource=bank")
            
            print(f"[Uploader] Envoi banque: {len(bank_items)} items vers {bank_url}")
            response = requests.post(bank_url, json=payload, headers=headers, timeout=30)
            
            if response.status_code in [200, 201]:
                print(f"[Uploader] ✅ Banque envoyée: {len(bank_items)} items.")
                return True
            else:
                print(f"[Uploader] ❌ Erreur envoi banque ({response.status_code}): {response.text}")
                return False
                
        except Exception as e:
            print(f"[Uploader] Exception réseau (banque): {e}")
            return False
