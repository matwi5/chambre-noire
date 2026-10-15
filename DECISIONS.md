# Décisions de conception

Une entrée par décision, la plus récente en tête. Une décision remplacée garde son entrée, avec le statut
« remplacée le <date> ». Entrées antérieures au 13/10/2026 reconstituées depuis le README, les commentaires du code et
les messages de commit.

## 2026-10-15 · Espaces public et privé étanches

- **Contexte** : en essayant l'espace privé sur le téléphone, le porteur voit passer d'un espace à l'autre ce qui
  devrait rester d'un seul côté : un prompt enregistré dans l'espace privé apparaît dans l'espace public (la spec du
  14/10/2026 laissait les prompts enregistrés hors de l'espace privé), la file d'attente montre à chaque espace les
  générations de l'autre (une génération privée y passe pour « Génération incognito », même pour la page qui l'a
  lancée après un rechargement), la progression d'une génération privée reste à l'écran après la sortie, et le texte
  et les images saisis sont communs aux deux espaces.
- **Décision** (porteur, 15/10/2026) : l'espace public et l'espace privé sont deux espaces étanches. Chacun a sa
  galerie, sa file d'attente, ses générations en cours, sa saisie (texte et images, onglet par onglet) et ses prompts
  enregistrés ; seuls les prompts types, les Réglages et l'autorisation des notifications sont communs.
  - **File** : chaque espace ne voit que ses générations (ni ligne, ni aperçu, ni vignette de l'autre ; « +N en
    attente » ne compte que l'espace courant). Une génération qui attend derrière une génération cachée de l'autre
    espace affiche « en attente » et une durée estimée qui compte ce travail, sans son rang. Les générations
    incognito, lancées depuis l'espace public, y restent visibles des autres appareils comme « Génération incognito ».
  - **Sortie et retour** : à la sortie (« Sortir » ou fermeture après 15 minutes), une génération privée quitte
    l'écran tout de suite et continue ; tout appareil déverrouillé la retrouve, même après un rechargement, avec son
    prompt et sa progression, et peut l'annuler.
  - **Prompts enregistrés privés** : chiffrés comme les images privées, visibles seulement dans l'espace privé,
    rechiffrés au changement de code, supprimés avec l'espace ; l'espace privé ne montre pas les prompts enregistrés
    publics. Les prompts enregistrés depuis l'espace privé avant ce changement restent en clair dans la liste
    publique : le porteur les supprime à la main.
  - **Saisie** : la saisie privée n'est jamais écrite dans le navigateur ; « Sortir » l'efface, la fermeture après
    15 minutes la garde en mémoire de la page jusqu'au retour. Les onglets marqués disparaissent.
  - **Cadenas** : aussi visible que le bouton Rafraîchir de l'en-tête de la galerie (même taille d'icône, même
    couleur, pleine opacité), au même endroit.
- **Écarté** : montrer les générations de l'autre espace sous un libellé neutre (le porteur ne veut rien voir de
  l'autre espace) ; cacher aussi le travail de l'autre espace dans la durée estimée (estimation fausse, sans rien
  cacher de plus : une attente sans ligne devant se remarque de toute façon) ; montrer les prompts enregistrés publics
  dans l'espace privé.
- **Conséquences** : la file d'attente et les prompts enregistrés dépendent désormais de l'espace de l'appareil qui
  les lit. Quelqu'un d'attentif devine, à une attente sans ligne devant, qu'une génération de l'autre espace tourne,
  comme il le devine déjà pour l'incognito des autres appareils. Remplace, dans « Espace privé discret », le cadenas
  « petit et discret » et l'héritage des onglets marqués, et, dans « Espace privé durci après la revue de sécurité »,
  les onglets marqués gardés à la fermeture de l'espace.
- **Mise en œuvre** (groupe B, sans le porteur) : pour le serveur, un appareil est « dans l'espace privé » s'il a une
  session **et** que sa requête est sûre (`_secure`, comme les routes privées) : le cookie de session n'a pas le
  drapeau `Secure` et pourrait suivre une adresse `http://` du même nom, qui recevrait sinon les prompts privés de la
  file en clair.

## 2026-10-15 · Espace privé durci après la revue de sécurité

- **Contexte** : la revue de sécurité du groupe D a relevé ce qui trahit ou expose l'espace privé hors du chiffrement
  du disque : le texte des notifications, le contenu laissé à l'écran après la sortie, la suppression sans code depuis
  n'importe quel appareil, le code et les images en clair sur le Wi-Fi, et un changement de code qui laissait la même
  clé privée dans les anciennes copies de `space.json`.
- **Décision** (porteur, 14/10/2026 ; mise en œuvre, groupe E) :
  - **Notification neutre** : une génération ou un lot privé notifie exactement comme une génération normale
    (« Image prête », « N images prêtes », mêmes champs) ; l'incognito garde son mot.
  - **« Sortir » vide l'écran** : en plus des images privées (zone de résultat, grille, visionneuse), le texte et les
    images des onglets marqués sont effacés, et une génération privée en cours ne garde à l'écran que sa progression
    (ni aperçu, ni prompt, ni image d'entrée dans la file). Fermeture seule de l'espace (15 minutes sans requête
    privée) : les images privées quittent l'écran comme avant, mais les onglets marqués gardent leur contenu et leur
    marque (« Héritage » de l'entrée « Espace privé discret », inchangé dans ce cas), pour ne pas effacer un texte en
    cours de saisie ; choix du groupe E, la décision du porteur nommant « Sortir ».
  - **Supprimer sans le code, sur le Mac seulement** : `/api/private/reset` exige une requête du Mac lui-même (au sens
    du contrôle d'accès : adresse source et nom d'hôte locaux, non relayée par Tailscale) ; ailleurs 403, et la feuille
    de l'interface dit d'ouvrir l'application sur le Mac (`local` dans `/api/status`).
  - **En HTTPS ou sur le Mac seulement** : toutes les routes de l'espace privé sauf `lock` (création, déverrouillage,
    changement de code, « Rendre privée », galerie et lectures déchiffrées, suppression d'une image), la génération
    privée et l'aperçu d'une génération privée (`/api/job/<id>/preview`, en clair) exigent une requête « sûre » (`_secure`) : adresse source 127.0.0.1 ou ::1 **et** nom d'hôte local ou nom
    HTTPS de « tailscale serve » (`S.https_hosts`, le relais arrivant de 127.0.0.1). Ailleurs 403 avec un message qui
    dit de passer par l'adresse HTTPS ; `secure` dans `/api/status` permet à l'interface de le dire avant toute saisie.
  - **Changer le code change les clés** : une nouvelle paire X25519 est tirée, chaque fichier de chaque image est
    déchiffré avec l'ancienne clé et rescellé avec la nouvelle (même identifiant d'image, mêmes rôles, même format),
    toutes les sessions sont fermées. Ordre d'écriture sûr : tout s'écrit d'abord à part dans `private/.rekey/`
    (fichier `public` avec la nouvelle clé publique, `items/<id>/<rôle>` rechiffrés, `space.json` scellé par le nouveau
    code), chaque fichier et dossier mis sur le disque (`fsync` pour chaque copie, puis un seul `F_FULLFSYNC` sur
    macOS, qui vide tout le cache du disque, avec le nouveau `space.json` et le dossier `private/`) pour qu'une coupure
    de courant ne bascule pas sur des copies vides ; **la bascule** est le remplacement atomique de
    `private/space.json` par le nouveau ; ensuite chaque image
    rechiffrée remplace l'ancienne (ancienne supprimée, puis nouvelle renommée à sa place) et `.rekey/` est supprimé.
    `finish_rekey`, appelé au démarrage et sous le verrou en tête de toute ouverture ou écriture de l'espace, répare
    une interruption : si `space.json` porte la clé de `.rekey/public`, la bascule a eu lieu et le rangement se
    termine ; sinon `.rekey/` est jeté et l'ancien espace est intact. À tout instant, exactement un des deux codes ouvre
    toutes les images. Un fichier déjà illisible avec l'ancienne clé est recopié tel quel. Les écritures d'images
    (`store_private`) et les suppressions passent sous le même verrou que le changement ; une génération privée lancée
    avant le changement est rangée avec la nouvelle clé (`S.rekeyed`, en mémoire : les générations ne survivent pas à
    un redémarrage).
- **Écarté** : « Image privée prête » (le service de notification et l'écran verrouillé du téléphone apprennent qu'un
  espace privé existe) ; suppression depuis un autre appareil avec le code (non demandée : avec le code, on entre et
  on supprime les images) ; juger le HTTPS sur les en-têtes `X-Forwarded-*` ou `Tailscale-User-Login` (un appareil du
  Wi-Fi peut les envoyer en `http://`) ; admettre l'adresse Tailscale directe en `http://` (chiffrée par WireGuard,
  mais la décision du porteur nomme le HTTPS et le Mac seulement) ; rechiffrer seulement la clé privée avec le nouveau
  code (choix du groupe D : une copie de l'ancien `space.json` s'ouvre encore avec l'ancien code et lit toutes les
  images) ; refuser le changement de code pendant une génération privée (inutile avec `S.rekeyed`) ; échanger le
  dossier `items/` entier (une image rangée entre une panne et la réparation aurait été déplacée avec l'ancien dossier).
- **Conséquences** : rien, dans une notification, ne distingue une image privée d'une image normale. Quelqu'un qui
  connaît le code d'accès du téléphone ne peut plus effacer l'espace privé à distance ; le porteur qui a oublié son
  code doit passer par le Mac. Le téléphone n'ouvre l'espace privé que par l'adresse HTTPS de Tailscale (« tailscale
  serve » actif) ; le Mac ouvert par son propre nom Wi-Fi (`http://<nom>.local:7860`) n'est pas « sûr » non plus : il
  passe par `127.0.0.1` ou `localhost`. Changer le code dure le temps de rechiffrer toutes les images (pendant ce
  temps, entrer dans l'espace et ranger une image attendent) ; une copie de `space.json` d'avant le changement ne lit
  plus les images d'après, mais une sauvegarde complète de `private/` d'avant le changement reste lisible avec l'ancien
  code, par nature.

## 2026-10-14 · Espace privé discret : on y entre, on en sort

_Révisée le 15/10/2026 (cadenas discret, héritage des onglets marqués) par « Espaces public et privé étanches »._

- **Contexte** : la spécification prévoyait un bouton « Privé » à côté de « Générer » et un mode Privé à allumer.
  En voyant l'interface, le porteur ne veut rien qui signale l'espace privé à l'arrivée sur l'application.
- **Décision** (porteur, 14/10/2026) : l'entrée est un petit cadenas discret dans l'en-tête de la galerie (création ou
  code). Déverrouiller fait **entrer dans l'espace privé** : toute l'application prend un thème propre (nuit sarcelle,
  comme le graphite de l'incognito), le bouton Incognito disparaît, toute génération part en privé, la galerie montre
  les images privées. Une seule sortie, un cadenas « Sortir » en haut à droite, qui verrouille. « Rendre privée », dans
  la visionneuse normale, demande le code sans faire entrer dans l'espace privé. Fermer l'application n'annule pas les
  générations privées.
- **Écarté** : bouton « Privé » à côté de « Générer » (visible à l'arrivée) ; geste caché (appui long sur le logo) ;
  mode Privé dans la feuille Réglages ; galerie normale visible depuis l'espace privé.
- **Conséquences** : il n'y a plus de « mode Privé » distinct de l'état déverrouillé ; une génération privée est
  simplement une génération lancée depuis l'intérieur de l'espace. Héritage (récit 61) : un onglet dont le contenu a
  été saisi dans l'espace reste marqué après la sortie, non pas « jusqu'à la génération suivante » (toute génération
  faite dans l'espace est privée de toute façon) mais jusqu'à ce qu'il soit vidé hors de l'espace (groupe D, sans le
  porteur) ; hors de l'espace, Générer y demande le code et relance une fois entré. Les tickets Asana du groupe D décrivent encore le
  bouton « Privé » (à mettre à jour par le porteur).

## 2026-10-14 · Espace privé : format des clés, des fichiers et sessions

- **Contexte** : mise en œuvre de la décision « Espace privé chiffré à clé publique » (ci-dessous). Le format des clés
  est coûteux à changer une fois un espace créé : il est fixé ici.
- **Décision** (groupe D, choix techniques dans le cadre fixé par le porteur) :
  - `private/space.json` : `{"v": 1, "public": <clé publique X25519, 32 octets, base64>, "kdf": {"alg": "scrypt",
    "n", "r", "p", "salt": <16 octets, base64>}, "key": <base64 de nonce (12 octets) + AES-256-GCM(clé privée X25519
    brute, 32 octets)>}` ; clé AES = scrypt(code privé en UTF-8 tel que saisi, sel, n, r, p, 32 octets) ; données
    associées `qwen-image-local private key v1`. Paramètres à la création : n = 2¹⁸, r = 8, p = 1 (256 Mio et ≈ 0,3 s
    par essai sur le Mac) ; ils sont lus dans le fichier, donc modifiables pour un espace futur sans casser l'ancien.
    ~~Changer le code rechiffre la même clé privée avec un sel neuf : les images ne bougent pas.~~ Remplacé le
    15/10/2026 : changer le code tire une nouvelle paire et rechiffre les images (« Espace privé durci après la revue
    de sécurité »).
  - Images : `private/items/<id>/`, `<id>` = 128 bits tirés au hasard (32 caractères hexadécimaux), sans date ni
    mode. Un fichier par rôle, chacun chiffré à part : `meta` (JSON : mode, prompt, dimensions, étapes, graine, durée,
    modèle, lot, heure, noms des images d'entrée), `image` (PNG), `thumb` (JPEG de 320 px, fabriqué en mémoire),
    `input_<k>` (k-ième image d'entrée, nom dans `meta`). Format d'un fichier : `QPV1` (4 octets) + clé publique
    X25519 éphémère (32) + nonce (12) + AES-256-GCM(contenu) ; clé = HKDF-SHA256(accord X25519 éphémère × clé
    publique de l'espace, sel = clé éphémère + clé publique, info `qwen-image-local private file v1`, 32 octets) ;
    données associées = les 48 premiers octets + `<id>/<rôle>`, pour qu'un fichier ne passe pas pour un autre. Le
    serveur range une image avec la seule clé publique, notée au lancement de la génération (si l'espace a été
    supprimé ou recréé entre-temps, l'image est abandonnée). L'image est écrite dans `private/items/.<id>/` puis le
    dossier est renommé : la galerie privée ne voit jamais une image à moitié rangée.
  - Prompts enregistrés privés (ajouté le 15/10/2026, spécification « Espaces public et privé étanches ») : un seul
    fichier `private/prompts`, même format qu'un fichier d'image (`QPV1`, clé éphémère, nonce, AES-256-GCM), données
    associées = les 48 premiers octets + `prompts` (aucun nom d'image ne peut le valoir) ; contenu : JSON en UTF-8,
    la liste des prompts privés, même format qu'un prompt public (`id`, `title`, `text`, `usage`, `used`). Absent tant
    qu'aucun prompt privé n'existe. Écrit sous `PRIVATE_LOCK` après `finish_rekey()`, scellé avec la clé publique de
    `space.json`, dans `private/prompts.tmp` mis sur le disque puis remplacé d'un coup, droits 600 ; lu et modifié
    avec la clé privée d'une session (refusé si elle n'est plus celle de l'espace). Le changement de code le
    rechiffre dans `private/.rekey/prompts` avant la bascule, puis `finish_rekey()` le met à la place de l'ancien ; un
    fichier déjà illisible est recopié tel quel.
  - Droits (ajouté le 15/10/2026) : tout fichier écrit dans `private/` (images, prompts, `space.json`, copies de
    `.rekey/`, fichiers temporaires) est créé en 600 et tout dossier en 700 (`open_private`, `private_dir`), contrôlé
    par le banc à la fin des tests de l'espace privé ; les fichiers d'un espace créé avant gardent leurs droits
    jusqu'au prochain changement de code.
  - Sessions : une par appareil, en mémoire du serveur (`S.private_sessions`), jeton aléatoire de 256 bits dans le
    cookie `qwen_private` (HttpOnly, `SameSite=Strict`, sans `Max-Age`) ; fermée après 15 min sans requête privée
    (`/api/status` et le suivi des générations ne la prolongent pas), par `/api/private/lock`, et par
    `/api/private/reset` pour toutes. Les dérivations du code passent une à une (verrou) : un essai à la fois, et
    jamais plusieurs fois 256 Mio en mémoire.
- **Écarté** : `hashlib.scrypt` (plafond mémoire à régler à la main) ; PBKDF2 (moins coûteux à attaquer sur GPU) ;
  garder la clé privée déchiffrée sur le disque ou dans le cookie ; `SameSite=Lax` (le cookie n'a pas à suivre une
  ouverture de page venue d'un autre site : l'interface ne lit l'espace privé que par des `fetch` de même origine).
- **Conséquences** : redémarrer le serveur ferme toutes les sessions. Verrouillage à la fermeture de la page par un
  envoi `keepalive` dans `pagehide`, comme l'oubli des générations incognito ; l'expiration après 15 minutes reste le
  filet si cet envoi se perd.

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
