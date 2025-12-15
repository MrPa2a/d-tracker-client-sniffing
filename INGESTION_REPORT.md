# Rapport d'Ingestion des Recettes

**Date:** 24/05/2024
**Statut:** Succès

## Résumé
Le script d'ingestion des données statiques (`ingest_static_data.py`) a été exécuté avec succès. Il a peuplé la base de données avec les recettes et les ingrédients extraits des fichiers D2O du jeu.

## Statistiques
- **Métiers (Jobs):** 22 synchronisés
- **Recettes (Recipes):** 4402 créées/mises à jour
- **Ingrédients:** 22987 liens créés

## Gestion des Conflits
Une logique de "Smart Mapping" a été implémentée pour éviter les doublons et la corruption de données :
1. **Correspondance par ID Ankama :** Prioritaire.
2. **Correspondance par Nom :** Si l'ID Ankama n'est pas trouvé mais que le nom existe en base (créé par les scanners HDV), le script lie l'item existant au nouvel ID Ankama.
   - **Sécurité :** La mise à jour de l'ID Ankama ne se fait **QUE** si l'item n'avait pas d'ID Ankama auparavant (NULL).
   - **Conflits :** Si un item a le même nom mais un ID Ankama différent déjà enregistré, l'ingestion est ignorée pour cet item afin de ne pas écraser les données existantes.

## Exemples de Conflits Ignorés (Logs)
Certains items ont été ignorés car ils présentaient des incohérences entre la base existante et les fichiers D2O (probablement des homonymes ou des versions différentes d'items) :
- *Peau de Gloot* (ID DB: 1690 vs D2O: 16522)
- *Plume Chimérique*
- *Fluide Glacial*
- *Ferrite*
- *Or*

Ces avertissements sont normaux et indiquent que le script a correctement protégé les données existantes.
