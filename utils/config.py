import json
import os

CONFIG_FILE = "config.json"

DOFUS_SERVERS = [
    "Brial",
    "Dakal",
    "Draconiros",
    "Hell Mina",
    "Imagiro",
    "Kourial",
    "Mikhal",
    "Ombre",
    "Orukam",
    "Rafal",
    "Salar",
    "Tal Kasha",
    "Tilezia",
]

DEFAULT_CONFIG = {
    "server": "Hell Mina",
    "api_url": "https://dofus-tracker-backend.vercel.app/api/ingest",
    "api_token": "", # Set in config.json
    "capture_interface": None,
    "min_price_threshold": 0,
    "max_price_threshold": 1000000000,
    "outlier_threshold_percent": 500, # 500% deviation
    "overlay_mode": "Auto"
}

class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()
        # Force save to ensure config file exists with defaults if it didn't exist
        if not os.path.exists(CONFIG_FILE):
            self.save()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self.config.update(loaded)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()

config_manager = ConfigManager()
