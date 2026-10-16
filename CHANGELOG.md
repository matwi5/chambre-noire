# Journal des versions

Les versions suivent [SemVer](https://semver.org/lang/fr/) ; tant que l'application est en 0.x, une version mineure
peut changer un comportement existant.

## 0.4.0 · 2026-10-17

### Ajouté

- **Zoom sur les images d'entrée** : pincement, molette et balayage, comme dans la visionneuse ; la première image
  d'entrée est chargée en avance et s'ouvre sans attente.
- **Version servie dans le panneau Moteur** : la ligne « Version » dit quel commit tourne, et « Serveur : à
  relancer » apparaît quand `tools/launch.py` ou `tools/estimate.py` a changé depuis le lancement du serveur.
- **Variante communautaire du modèle en option** : `setup.py --uc` l'installe (`uc-q4`, et `uc-q8` avec `--q8`),
  à choisir par `--model`.
- **Réglages propres à la machine** dans `tools/config.local.json`, non suivi par git, lu par-dessus
  `tools/config.json`.

### Modifié

- **Modèle par défaut** : `q4` et `q8` installent les quantifications GGUF des poids officiels de
  Qwen/Qwen-Image-2.1 (mêmes tailles qu'avant) ; une installation existante télécharge ces fichiers au prochain
  `setup.py`.
- **Une image reste dans son espace** : le bouton « Rendre privée » et la route `POST /api/private/adopt` sont
  retirés.
- **Affichage des images** : une image n'apparaît qu'une fois chargée, sans l'image d'avant ; une miniature
  d'entrée prend tout de suite la taille de l'image complète, sans saut à son arrivée.
- **Dépôt allégé** : `workflows/` et `start-ui-sdcpp.cmd`, périmés, sont retirés.

### Corrigé

- Une image d'entrée privée ou la galerie privée ne réapparaissent plus un instant dans l'espace public.
- Après la sortie de l'espace privé, la page ne garde plus rien de privé, même caché : visionneuse, images
  d'entrée, feuille d'un lot, liens de téléchargement, prompt, lignes du journal du panneau Moteur.

## 0.3.0 · 2026-10-15

### Ajouté

- **Prompts enregistrés privés** : enregistrés dans l'espace privé, ils sont chiffrés avec lui, visibles seulement
  dedans, rechiffrés quand le code change et supprimés avec l'espace.
- **Message quand l'espace privé se ferme seul** : le champ en cours de saisie perd le curseur et un message dit le
  retour dans l'espace public.
- **Contrôles en une commande** (`tests/check.py`), vérification GitHub sur les pull requests vers `main`, tests de
  l'interface dans un Chrome sans écran à la taille d'un téléphone.

### Modifié

- **Espaces public et privé étanches** : chaque espace a sa propre file d'attente, ses générations en cours, sa
  saisie (texte et images, onglet par onglet) et ses prompts enregistrés ; rien de l'un n'apparaît dans l'autre. Une
  génération qui attend derrière une génération de l'autre espace affiche une durée qui en tient compte.
- **Génération privée** : elle quitte l'écran à la sortie de l'espace et se retrouve au retour, même après un
  rechargement ou depuis un autre appareil, avec son prompt complet et l'annulation.
- **Après « Générer »** : le texte et les images de l'onglet sont vidés une fois la demande acceptée.
- **Cadenas de l'espace privé** aussi visible que le bouton Rafraîchir ; les onglets « marqués » disparaissent.

### Corrigé

- En Éditer, choisir plusieurs photos d'un coup les ajoute toutes, et non plus seulement la première.
- La pastille « +N en attente » ne dépasse plus de sa bulle sur un téléphone.
- Une génération reprise après un rechargement garde son prompt complet (« Reprendre le texte » le rendait coupé à
  80 caractères).

### Sécurité

- Suivi, aperçu et annulation d'une génération privée refusés hors de l'espace privé ; l'espace privé n'est reconnu
  que par une adresse sûre (HTTPS ou le Mac) ; l'annulation d'un lot n'est plus écrite dans le journal du serveur.

## 0.2.0 · 2026-10-15

### Ajouté

- **Mac Apple Silicon** : moteur Metal (sd.cpp `master-959`) avec l'encodeur GGUF et sa tour vision ; estimations de
  durée calibrées sur la machine.
- **Accès depuis le téléphone** : code d'accès, service macOS qui démarre seul, application installable en HTTPS par
  `tailscale serve`, notification de fin de génération (Web Push).
- **Galerie et visionneuse** : zoom au pincement, partage, copie, images d'entrée gardées avec chaque image.
- **Mode incognito** : l'image n'est gardée nulle part sur l'ordinateur ; elle est remise une fois, puis oubliée une
  fois vue et quittée.
- **File d'attente** : « Générer » reste actif pendant une génération ; les demandes attendent leur tour dans une file
  commune au Mac et au téléphone, avec annulation par génération.
- **Variantes** (mode Créer) : 1 à 4 images d'un même prompt, une grille pour choisir et « Garder celle-ci ».
- **Campagne** (mode Éditer) : le même prompt appliqué à chaque photo (10 au plus), une image par photo.
- **Lots dans la galerie** : badge, « Voir le lot », « Tout télécharger » ; une seule notification par lot.
- **Prompts enregistrés** partagés entre appareils, et 11 prompts types livrés avec l'application.
- **Espace privé** : une galerie chiffrée sur le disque, ouverte par un code distinct, par un cadenas discret de la
  Galerie ; on y entre et on en sort ; « Rendre privée » pour une image existante.
- **Banc de test** sans GPU : `venv/bin/python -m unittest discover -s tests`.

### Modifié

- Interface refaite (verre, barre d'onglets, panneau de réglages), niveaux de résolution nommés d'après le format
  vidéo le plus proche ; réglages par défaut 720p et 40 étapes.
- Une demande invalide est refusée tout de suite, et une génération qui échoue n'arrête plus la file.
- Une génération annulée ne laisse aucun fichier.

### Sécurité

- Liste blanche de `Host` contre le rebinding DNS et contrôle d'origine des requêtes POST.
- Espace privé : chiffrement à clé publique (X25519, scrypt, AES-256-GCM), ouverture seulement en HTTPS ou sur le Mac,
  nouvelles clés à chaque changement de code ; rien d'une génération privée ou incognito ne reste en clair dans le
  journal, la calibration ou `logs/`, et rien ne la trahit aux autres appareils.

## 0.1.0 · 2026-09-23

Première version : interface web locale, lanceur et installation pour Windows (Vulkan), moteur CUDA en option,
estimations de durée calibrées, licence MIT.
