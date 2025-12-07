# Dofus Tracker Client v3 (POC Sniffing)

Ce projet est un Proof of Concept (POC) pour la récupération des prix HDV de Dofus via l'analyse de paquets réseaux (Sniffing).

## Installation

1.  Créer un environnement virtuel :
    ```powershell
    python -m venv venv
    ```
2.  Activer l'environnement :
    ```powershell
    .\venv\Scripts\Activate
    ```
3.  Installer les dépendances :
    ```powershell
    pip install -r requirements.txt
    ```

## Pré-requis Windows

*   **Npcap** doit être installé sur votre machine pour que Scapy fonctionne.
    *   Télécharger : https://npcap.com/
    *   Lors de l'installation, cochez l'option **"Install Npcap in WinPcap API-compatible Mode"**.
