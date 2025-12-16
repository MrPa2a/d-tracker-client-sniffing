import requests
import os
import sys
import zipfile
import tempfile
import subprocess
import threading
import logging
from packaging import version
from core.constants import VERSION

logger = logging.getLogger(__name__)

class UpdateManager:
    def __init__(self, api_url=None):
        self.current_version = VERSION
        # Si pas d'URL fournie, on utilisera celle des constantes plus tard
        self.api_url = api_url 
        self.update_available = False
        self.latest_version = None
        self.download_url = None
        self.release_notes = ""

    def check_for_updates(self):
        """
        Vérifie si une mise à jour est disponible.
        Retourne (bool, str): (disponible, version_distante)
        """
        if not self.api_url:
            logger.warning("Aucune URL de mise à jour configurée.")
            return False, None

        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            # Adaptation selon le format de réponse (GitHub Releases ou API perso)
            # Supporte le format GitHub Release (tag_name) ET le format simple JSON (version)
            remote_version_str = data.get("tag_name", "").replace("v", "")
            if not remote_version_str:
                remote_version_str = data.get("version", "")

            if not remote_version_str:
                return False, None

            remote_version = version.parse(remote_version_str)
            local_version = version.parse(self.current_version)
            
            print(f"[Updater] Check: Local={local_version} vs Remote={remote_version}")

            if remote_version > local_version:
                self.update_available = True
                self.latest_version = remote_version_str
                # GitHub: assets[0].browser_download_url
                # API Perso: data.get("url")
                raw_url = self._get_download_url(data)
                
                # Sanitization des URLs pour téléchargement direct
                if "drive.google.com" in raw_url:
                    self.download_url = self._sanitize_google_drive_url(raw_url)
                elif "dropbox.com" in raw_url:
                    # Gère ?dl=0 et &dl=0
                    self.download_url = raw_url.replace("?dl=0", "?dl=1").replace("&dl=0", "&dl=1")
                else:
                    self.download_url = raw_url

                self.release_notes = data.get("body", "")
                return True, remote_version_str
            
            return False, None

        except Exception as e:
            logger.error(f"Erreur lors de la vérification des mises à jour: {e}")
            return False, None

    def _sanitize_google_drive_url(self, url):
        """Convertit un lien de visualisation Google Drive en lien de téléchargement direct."""
        if not url:
            return url
            
        # Cas 1: https://drive.google.com/file/d/FILE_ID/view...
        if "drive.google.com/file/d/" in url:
            try:
                file_id = url.split("/d/")[1].split("/")[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            except:
                return url
                
        # Cas 2: https://drive.google.com/open?id=FILE_ID
        if "drive.google.com/open?id=" in url:
            try:
                file_id = url.split("id=")[1].split("&")[0]
                return f"https://drive.google.com/uc?export=download&id={file_id}"
            except:
                return url
                
        return url

    def _get_download_url(self, data):
        # Logique d'extraction de l'URL selon le provider
        # Pour GitHub :
        if "assets" in data and len(data["assets"]) > 0:
            return data["assets"][0]["browser_download_url"]
        return data.get("url")

    def _download_from_google_drive(self, url, destination_file, progress_callback=None):
        session = requests.Session()
        response = session.get(url, stream=True)
        token = self._get_confirm_token(response)

        if token:
            # Extract ID from URL
            try:
                file_id = url.split('id=')[1].split('&')[0]
                params = {'id': file_id, 'confirm': token}
                response = session.get("https://drive.google.com/uc?export=download", params=params, stream=True)
            except:
                pass # Fallback to original response if ID extraction fails

        self._write_response_to_file(response, destination_file, progress_callback)

    def _get_confirm_token(self, response):
        for key, value in response.cookies.items():
            if key.startswith('download_warning'):
                return value
        return None

    def _write_response_to_file(self, response, destination_file, progress_callback=None):
        total_length = response.headers.get('content-length')

        if total_length is None: 
            destination_file.write(response.content)
        else:
            dl = 0
            total_length = int(total_length)
            for data in response.iter_content(chunk_size=4096):
                dl += len(data)
                destination_file.write(data)
                if progress_callback:
                    progress_callback(dl / total_length)

    def download_and_install(self, progress_callback=None):
        """
        Télécharge la mise à jour et lance le script d'installation.
        """
        if not self.download_url:
            return False

        try:
            print(f"[Updater] Downloading from: {self.download_url}")
            
            # 1. Télécharger le ZIP
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
                # Gestion spécifique Google Drive (Virus Scan Warning)
                if "drive.google.com" in self.download_url:
                    self._download_from_google_drive(self.download_url, tmp_file, progress_callback)
                else:
                    response = requests.get(self.download_url, stream=True)
                    response.raise_for_status()
                    self._write_response_to_file(response, tmp_file, progress_callback)
                
                zip_path = tmp_file.name

            print(f"[Updater] File downloaded to: {zip_path}")

            # 2. Extraire dans un dossier temporaire
            extract_dir = os.path.join(tempfile.gettempdir(), "dofus_tracker_update")
            if os.path.exists(extract_dir):
                import shutil
                shutil.rmtree(extract_dir)
            
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            except zipfile.BadZipFile:
                logger.error("Le fichier téléchargé n'est pas un ZIP valide.")
                print("[Updater] Error: Downloaded file is not a valid ZIP.")
                return False

            # 3. Créer le script de mise à jour (BAT)
            # Ce script va :
            # - Attendre que l'application actuelle se ferme
            # - Copier les nouveaux fichiers
            # - Relancer l'application
            
            current_exe = sys.executable
            current_dir = os.path.dirname(current_exe)
            
            # Si on est en dev (python main.py), current_exe est python.exe
            # Si on est build (exe), current_exe est DofusTracker.exe
            
            is_frozen = getattr(sys, 'frozen', False)
            
            if not is_frozen:
                logger.info("Mode développement détecté, simulation de mise à jour.")
                return True

            # Nom de l'exécutable à relancer
            exe_name = os.path.basename(current_exe)
            
            # Le dossier extrait contient probablement un dossier racine (ex: DofusTracker/)
            # Il faut trouver où sont les fichiers
            source_dir = extract_dir
            # Si le zip contient un dossier unique, on descend dedans
            items = os.listdir(extract_dir)
            if len(items) == 1 and os.path.isdir(os.path.join(extract_dir, items[0])):
                source_dir = os.path.join(extract_dir, items[0])

            bat_script = f"""
@echo off
timeout /t 2 /nobreak > NUL
echo Mise a jour en cours...
xcopy "{source_dir}" "{current_dir}" /E /H /Y /Q
start "" "{os.path.join(current_dir, exe_name)}"
del "%~f0"
            """
            
            bat_path = os.path.join(tempfile.gettempdir(), "update_tracker.bat")
            with open(bat_path, "w") as f:
                f.write(bat_script)

            # 4. Lancer le script et quitter
            subprocess.Popen([bat_path], shell=True)
            
            # Force exit of the entire process (sys.exit only kills the thread)
            os._exit(0)

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour: {e}")
            return False
