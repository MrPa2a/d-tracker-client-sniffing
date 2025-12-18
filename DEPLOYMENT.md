# Guide de Déploiement Automatisé

Ce document explique comment utiliser le script de déploiement `scripts/release.py` pour publier de nouvelles versions du client Dofus Tracker.

## 1. Pré-requis

### Dépendances Python
Assurez-vous d'avoir installé les paquets nécessaires :
```bash
pip install dropbox python-dotenv requests
```

### Tokens d'API
Pour que le script puisse uploader le fichier et mettre à jour la version, vous avez besoin de configurer l'accès à Dropbox et GitHub.

#### 1. Dropbox (Recommandé : Refresh Token)
Dropbox utilise désormais des tokens d'accès à courte durée de vie par défaut. Pour une automatisation durable, nous utilisons un **Refresh Token**.

1.  Allez sur [Dropbox App Console](https://www.dropbox.com/developers/apps).
2.  Créez une app (Scoped access, App folder).
3.  Dans l'onglet "Permissions", cochez `files.content.write` et `sharing.write`. Cliquez sur "Submit".
4.  Notez votre **App Key** et **App Secret** (onglet Settings).
5.  Lancez le script utilitaire pour générer votre Refresh Token :
    ```bash
    python scripts/get_dropbox_token.py
    ```
6.  Suivez les instructions à l'écran. Le script vous donnera les lignes à copier dans votre `.env`.

#### 2. GitHub Personal Access Token
1.  Allez sur [GitHub Settings > Tokens](https://github.com/settings/tokens).
2.  Générez un nouveau token (Classic).
3.  Cochez la permission `gist`.

## 2. Configuration

Créez un fichier `.env` à la racine du dossier `dofus-tracker-client-v3` (vous pouvez copier `.env.example`) :

```ini
# Dropbox (Méthode recommandée)
DROPBOX_APP_KEY=votre_app_key
DROPBOX_APP_SECRET=votre_app_secret
DROPBOX_REFRESH_TOKEN=votre_refresh_token_genere

# GitHub
GITHUB_TOKEN=votre_token_github_ici
```

> ⚠️ **Attention** : Ne committez jamais ce fichier `.env` sur Git !

## 3. Utilisation

Le script s'occupe de tout : incrémentation de version, compilation, upload et mise à jour du Gist.

Ouvrez un terminal dans `dofus-tracker-client-v3` et lancez l'une des commandes suivantes :

### Pour une correction de bug (Patch)
*Exemple : 3.1.3 -> 3.1.4*
```bash
python scripts/release.py --bump patch
```

### Pour une nouvelle fonctionnalité (Minor)
*Exemple : 3.1.3 -> 3.2.0*
```bash
python scripts/release.py --bump minor
```

### Pour une refonte majeure (Major)
*Exemple : 3.1.3 -> 4.0.0*
```bash
python scripts/release.py --bump major
```

### Tester sans uploader
Pour vérifier que la compilation et l'incrémentation fonctionnent sans rien envoyer en ligne :
```bash
python scripts/release.py --bump patch --skip-upload
```

## 4. Fonctionnement du script

Le script `scripts/release.py` effectue les actions suivantes :

1.  **Vérification** : Charge les variables d'environnement depuis `.env`.
2.  **Bump Version** : Lit `core/constants.py`, incrémente la version selon le type demandé, et sauvegarde le fichier.
3.  **Build** : Lance `build_exe.bat` avec l'option `--no-pause` pour générer l'exécutable et le ZIP.
4.  **Upload** : Envoie le fichier `dist/DofusTracker.zip` sur Dropbox.
5.  **Lien** : Récupère un lien de partage direct (modifié pour le téléchargement direct).
6.  **Publication** : Met à jour le Gist `version.json` avec le nouveau numéro de version et le nouveau lien.

Une fois terminé, les clients des utilisateurs détecteront la mise à jour au prochain lancement.
