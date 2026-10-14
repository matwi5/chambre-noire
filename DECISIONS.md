# Décisions de conception

Une entrée par décision, la plus récente en tête. Une décision remplacée garde son entrée, avec le statut
« remplacée le <date> ». Entrées antérieures au 13/10/2026 reconstituées depuis le README, les commentaires du code et
les messages de commit.

## 2026-10-14 · Espace privé chiffré à clé publique

- **Contexte** : le porteur veut une galerie séparée, accessible seulement par un code, dont les images ne se lisent
  pas sur l'ordinateur sans passer par l'application. La menace visée : quelqu'un qui ouvre les dossiers du Mac, une
  sauvegarde Time Machine, ou une personne qui connaît le code d'accès du téléphone mais pas le code privé.
- **Décision** (porteur) : tout ce qui se rattache à une image privée (image, images d'entrée, miniature, prompt,
  réglages) est chiffré sur le disque, sans aucune trace en clair ailleurs (journal, calibration, `logs/`), comme en
  incognito. Le chiffrement est à clé publique : la clé publique de l'espace est en clair, la clé privée est chiffrée
  par une clé tirée du code privé (dérivation volontairement lente). Le serveur peut donc chiffrer une image en fin de
  génération sans connaître le code, même si l'espace a été verrouillé entre-temps ; seule la lecture demande le code.
  Code privé de 8 caractères au moins, distinct du code d'accès, demandé même sur le Mac ; déverrouillage propre à
  chaque appareil. Bibliothèque `cryptography`, déjà installée avec `pywebpush`.
- **Écarté** : chiffrement symétrique par le code seul (le serveur devrait garder la clé pendant toute la génération,
  ou l'image finirait en clair si l'espace est verrouillé avant la fin) ; disque en mémoire vive pour le passage en
  clair (propre à macOS, déjà écarté pour l'incognito) ; code court à chiffres (cassé hors ligne en quelques jours sur
  une copie du disque).
- **Conséquences** : sd-cli ne travaille que sur des fichiers en clair, donc les entrées et l'image passent brièvement
  en clair dans `jobs/`, exclu de Time Machine. Code oublié : les images privées sont perdues ; « Supprimer l'espace
  privé » permet de repartir de zéro. Le format des fichiers chiffrés est coûteux à changer une fois des images
  stockées.

## 2026-10-14 · Pas de génération simultanée : une file d'attente

- **Contexte** : le porteur veut lancer plusieurs générations en même temps (lots de variantes, campagnes), en
  parallèle si cela ne fait pas perdre de temps.
- **Décision** (porteur) : les générations restent calculées l'une après l'autre ; « Générer » reste actif pendant une
  génération et les demandes suivantes vont dans une file d'attente visible. Un lot lance sd-cli une fois par image,
  y compris pour les variantes.
- **Raison** : d'après les mesures de calibration du Mac (M6, 32 Go), une image 1024 px en 40 étapes passe ≈ 95 % de
  son temps dans les étapes sur le GPU (≈ 17 s par étape), contre ≈ 30 s pour l'encodage et le décodage. Deux sd-cli
  simultanés se partageraient le même GPU déjà saturé (aucun gain de débit, déduit et non mesuré) et doubleraient la
  mémoire, avec un risque d'échange sur le disque en Q8. Produire les variantes d'un seul lancement (`-b N`)
  n'économiserait que ≈ 7 s par image (≈ 1 %), au prix de l'annulation, de la progression et des aperçus image par
  image.
- **Écarté** : plusieurs sd-cli en parallèle ; `-b N` pour les variantes.
- **Conséquences** : un lot de N images dure N fois une image. À revoir si une mesure réelle de deux calculs
  simultanés montrait un gain, ou sur une machine à plusieurs GPU.

## 2026-10-13 · Notification de fin de génération par Web Push

- **Contexte** : le porteur veut être prévenu à la fin d'une génération (souvent plus de 10 minutes) sur son téléphone,
  où Android met en pause une application en arrière-plan.
- **Décision** (porteur) : l'ordinateur envoie une notification Web Push (bibliothèque `pywebpush`, qui ajoute
  `cryptography`, `py-vapid`, `http-ece`, `requests` et `aiohttp`) à chaque appareil abonné, terminée ou en échec.
  Autorisation demandée au premier appui sur Générer, interrupteur dans Réglages pour les couper. Le message ne contient
  ni prompt ni nom de fichier, car il transite (chiffré) par le service du navigateur ; en incognito : « Image incognito
  prête ». Pas de notification quand l'application est à l'écran.
- **Écarté** : notification affichée par la page seule (aucune dépendance, mais rien n'arrive une fois l'application
  mise en pause en arrière-plan) ; service tiers comme ntfy (le message sortirait en clair vers un tiers).
- **Conséquences** : nouvelle dépendance ; fonctionne seulement en HTTPS (Tailscale) ou sur l'ordinateur ; l'ordinateur
  doit pouvoir joindre le service de notification (Internet).

## 2026-10-13 · Barre d'état du téléphone : couleur calculée plutôt que plein écran

- **Contexte** : le porteur veut que l'application installée « continue » sous la barre d'état d'Android, sans bande
  de couleur.
- **Décision** : rester en `display: standalone` et donner à `<meta name="theme-color">`, à chaque changement de vue
  ou d'image, la couleur du haut de l'écran calculée en JavaScript (`syncThemeColor` : moyenne du haut de la miniature
  floutée en fond, avec les voiles du CSS). Chrome peint la barre d'état de cette couleur.
- **Écarté** : dessiner sous la barre d'état (pas encore possible pour une application installée avec Chrome stable :
  bug Chromium 407420295, correctif désactivé par défaut) ; `display: fullscreen` (cache l'heure et les notifications) ;
  `theme-color` transparent (non documenté, ignoré).
- **Conséquences** : la bande reste unie (pas de dégradé ni d'image dessous). Un bug Chromium signalé en septembre 2026
  (559396686) dirait que les applications installées ne suivent plus un `theme-color` changé en cours de route : à
  vérifier sur le téléphone.

## 2026-10-13 · Zoom de la visionneuse temporaire, au pincement

- **Décision** (porteur) : pincer zoome l'image, qui passe au-dessus de tous les éléments et peut couvrir tout
  l'écran, puis revient à sa taille dès qu'on relâche les doigts. Plus de double appui pour zoomer ; sur ordinateur, la
  molette zoome et un clic remet à la taille.

## 2026-10-13 · Images d'entrée conservées avec chaque image

- **Contexte** : le porteur veut revoir depuis la galerie les images de départ d'une édition ou d'un dessin guidé, et
  repartir de l'une d'elles. Elles n'existaient que dans `jobs/<id>/`, dont seuls les 20 derniers sont gardés.
- **Décision** : en fin de job (hors incognito et calibration), copier `init.png` et `ref_N.png` dans
  `outputs/.inputs/<nom de l'image>/`, servis par `/api/input` et supprimés avec l'image. `mask.png` (masque noir et
  blanc) n'est pas gardé : la zone peinte (`ref_1.png`) montre la même chose de façon lisible. Au démarrage, les images
  plus anciennes récupèrent leurs entrées si leur dossier de travail existe encore.
- **Écarté** : lire les entrées dans `jobs/` (perdues après 20 générations).
- **Conséquences** : plus de place sur le disque (une ou plusieurs images PNG par édition).

## 2026-10-13 · Incognito : fermer l'application arrête la génération

- **Contexte** : une génération incognito a été perdue après un redémarrage de l'application sur le téléphone. Sur
  Android, le système peut aussi libérer une application restée en arrière-plan.
- **Décision** (porteur) : garder le comportement initial. Fermer ou recharger l'application arrête la génération
  incognito et la perd.
- **Écarté** : se rattacher à la génération à la réouverture, en retenant seulement le numéro du job sur le téléphone.

## 2026-10-13 · Partager et Copier seulement là où le navigateur les permet

- **Décision** : les boutons utilisent l'API de partage (`navigator.share` avec un fichier) et le presse-papiers
  (`navigator.clipboard.write`). Ils sont masqués quand le navigateur ne les offre pas, en pratique hors HTTPS
  (adresse `http://` du Wi-Fi), au lieu d'afficher un bouton qui échoue.

## 2026-10-13 · Mode incognito : image gardée en mémoire, remise une seule fois

- **Contexte** : le porteur veut une image téléchargeable mais gardée nulle part sur l'ordinateur, perdue à la
  génération suivante ou au rechargement de l'application, avec tout ce qui s'y rattache (job, aperçus).
- **Décision** : sd-cli ne lit et n'écrit que des fichiers. Le travail se fait donc dans `jobs/incognito_<id>/`,
  supprimé dès la fin du job et au démarrage suivant. Le serveur garde le PNG en mémoire, le remet une fois à la page
  (`/api/job/<id>/result`), puis la page lui fait oublier le job (`/forget`). La page l'affiche depuis une adresse
  `blob:`. Une nouvelle génération purge les jobs incognito terminés, et un rechargement pendant la génération l'arrête
  (`pagehide` avec `keepalive`). Pas de ligne dans le journal, pas de mesure de calibration (elle note la taille et
  l'heure), aucun détail dans `logs/`. Le prompt n'est pas retenu comme brouillon. Le mode (bouton à droite de Générer, inactif pendant une génération), lui, reste actif d'une
  visite à l'autre, pour ne pas repasser en mode normal sans s'en rendre compte. Éditer et Dessiner restent possibles
  sur l'image incognito.
- **Écarté** : disque en mémoire vive (`hdiutil` sur Mac) : propre à macOS et plus complexe, pour un gain faible sur
  un SSD. Garder l'image côté serveur jusqu'à une expiration : elle survivrait au rechargement de la page.
- **Conséquences** : les fichiers touchent brièvement le disque (limite écrite dans le README). Une image qui n'a pas été
  téléchargée est perdue.
- **Modifiée le 14/10/2026** (porteur, avec la file d'attente) : plus de purge à chaque nouvelle génération ; la page
  garde une image incognito jusqu'à ce qu'elle ait été vue puis quittée, et le serveur jusqu'à ce que la page l'ait
  récupérée. Le bouton Incognito n'est plus bloqué pendant une génération : chaque génération garde le mode de son
  lancement. À la fermeture, la page fait oublier toutes ses générations incognito en un envoi (`/api/forget`).

## 2026-10-13 · Application installable via `tailscale serve`

- **Contexte** : Chrome n'installe une page comme application qu'en HTTPS, et le téléphone doit joindre le Mac hors du
  Wi-Fi.
- **Décision** : le HTTPS est fourni par `tailscale serve` (certificat valide), qui relaie vers 127.0.0.1. Une requête
  relayée (en-têtes `X-Forwarded-*` ou `Tailscale-User-Login`) n'est jamais traitée comme venant du Mac : elle demande le
  code. Le manifeste, les icônes et le service worker sont servis sans cookie, car le navigateur les demande sans. Le
  cookie d'accès est `SameSite=Lax` et non `Strict` : Chrome Android traite l'ouverture de l'application installée
  comme une arrivée d'un autre site, et redemandait le code à chaque ouverture. Les POST restent protégés par le contrôle
  d'origine.

## 2026-10-13 · Liste blanche de `Host` et contrôle d'origine des POST

- **Contexte** : une revue de sécurité a confirmé deux failles exploitables depuis une page web ouverte sur le Mac :
  rebinding DNS vers 127.0.0.1 (lecture du code d'accès, des prompts et des images) et requête forgée en `text/plain`
  (génération lancée à l'insu de l'utilisateur).
- **Décision** : n'accepter que les `Host` locaux et ceux du Wi-Fi et de Tailscale calculés au démarrage. Refuser tout
  POST `Sec-Fetch-Site: cross-site` ou dont l'`Origin` diffère de l'origine du `Host` (403), et exiger
  `Content-Type: application/json` (415). Le Mac n'est « local » que si son `Host` l'est aussi.
- **Écarté** : accepter toute adresse IP littérale (sûr face au rebinding, mais hors du plan ; à décider par le porteur) ;
  compter sur les protections des navigateurs (Safari n'en a pas) ou sur un filtrage DNS du routeur.
- **Conséquences** : si l'IP du Mac change, l'ancienne est refusée jusqu'au redémarrage (le nom `.local` reste valable).
  Toute requête de l'interface doit envoyer `Content-Type: application/json`.

## 2026-10-13 · Accès du téléphone par un code et un cookie

- **Décision** : avec `--lan`, tout appareil autre que le Mac saisit une fois un code de 8 caractères tiré au hasard
  (`tools/access_code.txt`, non versionné). Le cookie, valable un an, est l'empreinte SHA-256 du code, pas le code.
  Une seconde d'attente suit chaque code faux. L'adresse et le code ne sont montrés que sur le Mac lui-même.
- **Écarté** : chiffrement HTTP sur le Wi-Fi (intercepter le cookie revient à intercepter le code ; changer le code
  invalide le cookie).

## 2026-10-13 · Encodeur GGUF officiel et réglages Metal sur Mac

- **Contexte** : Metal n'a pas de calcul int8 dans stable-diffusion.cpp. L'encodeur int8 de Comfy-Org tournait sur le
  processeur, à ≈ 2 min 30 par référence 512×512.
- **Décision** : sur Mac, prendre l'encodeur GGUF Q8_0 de Qwen et sa tour vision (≈ 3 s pour la même référence), avec
  sd.cpp `master-959`, tout sur le GPU. Options : `--fa` (sans elle, la tour vision provoque une faute mémoire du GPU sur
  une référence 2048×2048), `--params-backend te=disk` (libère l'encodeur et laisse la place au cache de préfixe),
  `--mmap` (fiable depuis `master-959`).
- **Écarté** : encodeur int8 sur le processeur (trop lent) ; VAE sur le processeur (11 fois plus lent).

## 2026-10-13 · Estimations de durée calibrées sur la machine

- **Décision** : modèle de coût par étape `a·n + b·n²` (n = longueur de la séquence), remplacé par `a·nt + b·nt·n` avec
  le cache de préfixe (release ≥ 903). S'y ajoutent l'encodage, le décodage proportionnel aux pixels et une part fixe.
  Les coefficients partent de valeurs propres au moteur et sont ajustés sur les 40 dernières mesures par moteur et par
  modèle, résumées par des médianes. Chaque mesure garde la release de sd.cpp qui l'a produite. Trois générations de
  calibration terminent l'installation.
- **Conséquences** : la formule est dupliquée en JavaScript dans l'interface et doit rester alignée.

## 2026-10-13 · Téléchargements épinglés et vérifiés

- **Décision** : moteur et modèles épinglés sur une release ou un commit précis, vérifiés par SHA-256, avec reprise des
  téléchargements interrompus.
- **Contexte** : le dépôt Hugging Face du modèle a été renommé (constaté le 12/10/2026) ; épingler protège contre ce
  genre de changement.

## 2026-09-23 · stable-diffusion.cpp plutôt que ComfyUI

- **Contexte** : la machine visée est un portable Windows à Radeon intégré.
- **Décision** : moteur stable-diffusion.cpp (Vulkan sous Windows, Metal sur Mac), avec `sd-cli` lancé à chaque
  génération ; grâce à `--mmap` et au cache disque, le modèle se recharge presque instantanément.
- **Écarté** : ComfyUI, qui repose sur PyTorch : pas de backend GPU utilisable sur les Radeon intégrés sous Windows
  (ROCm Windows ne couvre que RDNA3/RDNA4, DirectML est limité à d'anciennes versions), donc calcul sur le seul
  processeur. Avec une carte NVIDIA, ComfyUI resterait plus rapide.

## 2026-09-23 · Correctif de l'encodeur int8 sous Windows

- **Contexte** : sd.cpp `master-890-74988b2` interprète mal la table d'embeddings quantifiée de l'encodeur int8 au
  format ComfyUI, et plante au chargement.
- **Décision** : `tools/fix_int8_te.py` crée une copie dont seule cette table repasse en bf16 (dé-rotation Hadamard
  comprise), le reste restant en int8.
- **Conséquences** : inutile avec `master-959` (vérifié sur Mac) ; à retirer quand le moteur Windows passera à cette
  version.
