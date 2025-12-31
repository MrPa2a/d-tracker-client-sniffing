"""
Client API pour les profils utilisateurs.
Permet de récupérer la liste des profils depuis le backend.
"""
import requests
from utils.config import config_manager


class ProfilesClient:
    def __init__(self):
        self.base_url = "https://dofus-tracker-backend.vercel.app/api/user"
    
    def get_profiles(self) -> list:
        """
        Récupère la liste de tous les profils depuis le backend.
        
        Returns:
            Liste de profils: [{"id": "uuid", "name": "MonProfil", "created_at": "..."}, ...]
        """
        try:
            response = requests.get(
                f"{self.base_url}?resource=profiles",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                # L'API retourne directement une liste de profils
                if isinstance(data, list):
                    return data
                # Ou peut-être un objet avec une clé 'profiles'
                return data.get('profiles', data.get('data', []))
            else:
                print(f"[ProfilesClient] Erreur {response.status_code}: {response.text}")
                return []
                
        except requests.exceptions.Timeout:
            print("[ProfilesClient] Timeout lors de la récupération des profils")
            return []
        except requests.exceptions.ConnectionError:
            print("[ProfilesClient] Erreur de connexion")
            return []
        except Exception as e:
            print(f"[ProfilesClient] Erreur inattendue: {e}")
            return []
    
    def get_profile_names(self) -> list:
        """
        Récupère uniquement les noms des profils.
        
        Returns:
            Liste de noms: ["Profil1", "Profil2", ...]
        """
        profiles = self.get_profiles()
        return [p.get('name', '') for p in profiles if p.get('name')]
    
    def get_profile_id_by_name(self, name: str) -> str:
        """
        Récupère l'UUID d'un profil par son nom.
        
        Returns:
            UUID du profil ou None si non trouvé
        """
        profiles = self.get_profiles()
        for p in profiles:
            if p.get('name') == name:
                return p.get('id')
        return None


# Instance singleton
profiles_client = ProfilesClient()
