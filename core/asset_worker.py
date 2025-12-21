import threading
import time
import requests
import io
from utils.config import config_manager

class AssetWorker(threading.Thread):
    def __init__(self, game_data_instance):
        super().__init__()
        self.game_data = game_data_instance
        self.queue = [] # List of GIDs to process
        self.lock = threading.Lock()
        self.running = False
        self.daemon = True
        self.processed_gids = set() # To avoid re-queueing same GID in same session

    def add_to_queue(self, gid):
        with self.lock:
            if gid not in self.processed_gids:
                if gid not in self.queue:
                    self.queue.append(gid)
                    print(f"[AssetWorker] Item {gid} ajouté à la file d'upload d'images.")

    def get_queue_size(self):
        with self.lock:
            return len(self.queue)

    def stop(self):
        self.running = False

    def run(self):
        self.running = True
        print("[AssetWorker] Service d'upload d'assets démarré.")
        
        while self.running:
            gid_to_process = None
            
            with self.lock:
                if self.queue:
                    gid_to_process = self.queue.pop(0)
            
            if gid_to_process:
                self.process_item(gid_to_process)
                # Small delay to be nice to the API/CPU
                time.sleep(0.5)
            else:
                time.sleep(1)

    def process_item(self, gid):
        try:
            # 1. Check if we have the image data locally (or via DofusDB fallback)
            # This call uses the existing logic in GameData (D2O -> D2P -> DofusDB)
            image_data = self.game_data.get_item_icon_data(gid)
            
            if not image_data:
                print(f"[AssetWorker] Impossible de récupérer l'image pour {gid}. Abandon.")
                with self.lock:
                    self.processed_gids.add(gid) # Mark as processed to avoid infinite retry loop
                return

            # 2. Upload to Backend
            self.upload_icon(gid, image_data)
            
            # 3. Mark as processed
            with self.lock:
                self.processed_gids.add(gid)
                
        except Exception as e:
            print(f"[AssetWorker] Erreur lors du traitement de {gid}: {e}")

    def upload_icon(self, gid, image_data):
        api_url = config_manager.get("api_url")
        if not api_url:
            return

        # Construct upload URL (assuming api_url is .../ingest)
        base_url = api_url.replace("/ingest", "")
        upload_url = f"{base_url}/data?resource=items&type=icon"
        
        try:
            files = {
                'file': (f'{gid}.png', io.BytesIO(image_data), 'image/png')
            }
            data = {
                'gid': str(gid)
            }
            
            # print(f"[AssetWorker] Upload de l'image {gid} vers {upload_url}...")
            response = requests.post(upload_url, data=data, files=files, timeout=30)
            
            if response.status_code == 200:
                print(f"[AssetWorker] Image {gid} uploadée avec succès.")
                # Update local knowledge
                if str(gid) in self.game_data.known_items_images:
                     self.game_data.known_items_images[str(gid)] = True
            else:
                print(f"[AssetWorker] Échec upload {gid}: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"[AssetWorker] Exception upload {gid}: {e}")

    def stop(self):
        self.running = False
