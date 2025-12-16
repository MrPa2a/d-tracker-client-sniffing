# Analyse du Protocole Dofus (Décembre 2025)

Ce document résume les découvertes techniques réalisées lors de la mise à jour du sniffer pour la version de Dofus de Décembre 2025 (Unity / Protocol Update).

## Contexte Général
*   **Protocole** : Protobuf sur TCP.
*   **Port** : 5555 (Serveur de jeu).
*   **Encodage** : VarInt pour les entiers, structures imbriquées (Wire Type 2).

## Identification des Paquets
Les paquets Protobuf de Dofus sont identifiables dans le flux TCP brut par la présence de la chaîne de caractères :
`type.ankama.com/`

Cette chaîne est immédiatement suivie d'un **suffixe** de 3 lettres qui identifie le type de message (ex: `jet`, `jeu`, `hyp`).

### Paquets Clés

#### 1. `jet` (et `jeu`) - Item Information & Prices
C'est le paquet le plus important pour le tracking des prix. Contrairement aux versions précédentes où les prix et les infos de l'item pouvaient être séparés, ce paquet contient **tout**.

*   **Suffixe** : `jet` (parfois `jeu`).
*   **Contenu** :
    *   **GID (Item ID)** : Généralement situé dans le **Champ 4** (Wire Type 0 - VarInt).
    *   **Prix HDV** : La structure diffère selon le type d'item (Ressource vs Équipement).

**Structure observée (Pseudo-Protobuf) :**

**Cas A : Ressources (Items empilables)**
Pour les ressources, tous les prix (lots de 1, 10, 100) sont souvent regroupés dans une seule occurrence du `Field 1`.
```protobuf
message JetPacketResource {
    optional SubMessage field1 = 1; // Une seule occurrence
    optional int32 gid = 4;
}

message SubMessage {
    repeated int32 prices = 2 [packed=true]; // Liste de TOUS les prix compressés
}
```

**Cas B : Équipements (Items uniques)**
Pour les équipements (Dofus, Coiffes, etc.), chaque item en vente est unique (stats différentes). Le serveur envoie donc une liste d'objets, ce qui se traduit par **plusieurs occurrences du `Field 1`** (Repeated Field).
```protobuf
message JetPacketEquipment {
    repeated SubMessage field1 = 1; // Répété N fois (une fois par offre)
    optional int32 gid = 4;
}

message SubMessage {
    optional int32 price = 2; // Le prix de CETTE offre spécifique
    // D'autres champs ici contiennent probablement les stats/effets
}
```

**Implémentation Critique :**
Le parser doit itérer sur **toutes** les occurrences de `Field 1` (`get_all_field_data`) et extraire le `Field 2` de chacune pour reconstituer la liste complète des prix.
*   Pour les **Ressources** : On calcule une moyenne pondérée.
*   Pour les **Équipements** : On ne retient que le `min()` de la liste (le prix le plus bas).

#### 2. `hyp` - Historique / Liste (Obsolète/Unreliable)
Nous avons observé des paquets `hyp` contenant des listes de prix, mais ils semblaient souvent désynchronisés ou contenir des moyennes incohérentes par rapport à l'affichage en jeu.
*   **Statut** : Ignoré au profit de `jet` qui contient les données "live".

#### 3. `jpi`, `jgf`, etc. - Paquets "Echo"
Lorsqu'on clique plusieurs fois sur le même item ou que le client a les données en cache, le serveur peut renvoyer de très petits paquets (taille < 10 octets) avec ces suffixes.
*   **Comportement** : Ils ne contiennent pas de prix. Le sniffer doit les ignorer ou gérer le cache pour ne pas dupliquer les observations.

## Méthodologie de Reverse-Engineering (Si ça casse encore)

Si le protocole change à nouveau, voici la méthode qui a fonctionné pour retrouver les données :

1.  **Capture Brute** : Dumper le contenu brut (`packet[Raw].load`) des paquets TCP port 5555.
2.  **Recherche Heuristique (Ground Truth)** :
    *   Identifier un item en jeu avec des prix très spécifiques (ex: `4897998` kamas).
    *   Convertir ce prix en **VarInt** (encodage binaire utilisé par Protobuf).
    *   Scanner le flux brut pour trouver cette séquence d'octets exacte.
3.  **Identification du Paquet** :
    *   Une fois la valeur trouvée, remonter dans le buffer pour trouver le préfixe `type.ankama.com/` le plus proche.
    *   Noter le suffixe (ex: `jet`).
4.  **Analyse de Structure** :
    *   Isoler le corps du message (après le suffixe et la longueur VarInt).
    *   Utiliser un décodeur Protobuf générique (ou `protoc --decode_raw`) pour comprendre l'imbrication des champs (Field X -> Field Y).

## Problèmes Courants
*   **Cache Client** : Si le client Dofus a déjà les prix, il ne redemande pas au serveur. Il faut parfois changer de map ou relancer le jeu pour forcer l'envoi des paquets.
*   **VarInt** : Les entiers sont de taille variable. Un prix de 100k prend moins d'octets qu'un prix de 10M. Toujours utiliser un décodeur VarInt robuste.
