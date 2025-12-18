import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect

def get_refresh_token():
    print("--- Générateur de Refresh Token Dropbox ---")
    app_key = input("Entrez votre App Key : ").strip()
    app_secret = input("Entrez votre App Secret : ").strip()

    auth_flow = DropboxOAuth2FlowNoRedirect(app_key, app_secret, token_access_type='offline')

    authorize_url = auth_flow.start()
    print(f"\n1. Allez sur cette URL : \n{authorize_url}")
    print("2. Cliquez sur 'Autoriser' (Allow).")
    print("3. Copiez le code d'accès qui s'affiche.")
    
    auth_code = input("\nEntrez le code d'accès ici : ").strip()

    try:
        oauth_result = auth_flow.finish(auth_code)
        print("\n✅ Succès !")
        print(f"Votre Refresh Token est : {oauth_result.refresh_token}")
        print("\nAjoutez ces lignes à votre fichier .env :")
        print(f"DROPBOX_APP_KEY={app_key}")
        print(f"DROPBOX_APP_SECRET={app_secret}")
        print(f"DROPBOX_REFRESH_TOKEN={oauth_result.refresh_token}")
    except Exception as e:
        print(f"\n❌ Erreur : {e}")

if __name__ == "__main__":
    get_refresh_token()
