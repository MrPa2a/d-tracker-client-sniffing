import threading
import time
import requests
import json
from datetime import datetime, timezone
from utils.config import config_manager

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
            "server": self.server,
            "captured_at": captured_iso,
            "price_unit_avg": obs['average_price'],
            "nb_lots": nb_lots,
            "source_client": "dofus-tracker-client-v3",
            "client_version": "3.0.0",
            "raw_item_name": obs['name'] # Pour l'instant identique
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

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_token}"
            }
            
            # Si pas de token configuré, on tente sans (ou on log un warning)
            if not self.api_token:
                # print("[Uploader] Attention: Pas de token API configuré.")
                pass

            response = requests.post(self.api_url, json=batch, headers=headers, timeout=10)
            
            if response.status_code in [200, 201]:
                print(f"[Uploader] {len(batch)} observations envoyées avec succès.")
            else:
                print(f"[Uploader] Erreur envoi ({response.status_code}): {response.text}")
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
