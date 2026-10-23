# Chambre noire

Génération d'images privée, en local, sur PC Windows ou Mac Apple Silicon.

Une interface web locale pour générer et modifier des images avec **[Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1)**,
pensée pour les PC portables ordinaires (processeur graphique intégré AMD ou Intel, pas de carte NVIDIA,
pas de droits administrateur) et pour les Mac à puce Apple. Tout tourne sur la machine, rien n'est envoyé sur Internet.

Trois usages, une sortie PNG :

- **Texte → image** : décrire une image, la générer.
- **Édition** : 1 à 10 images de référence + une instruction (« remplace le ciel par un coucher de soleil »,
  « mets le chapeau de l'image 2 sur la personne de l'image 1 »).
- **Dessin guidé** : peindre au pinceau la zone à modifier directement sur l'image, puis décrire ce qu'on veut à la place.

Le moteur est [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) : sous Windows avec son backend
**Vulkan**, qui fonctionne sur quasiment tous les GPU intégrés récents avec le pilote graphique déjà installé ;
sur Mac avec son backend **Metal**, la technologie graphique d'Apple.

---

## Sommaire

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Lancement](#lancement)
4. [Depuis un téléphone](#depuis-un-téléphone)
5. [Utilisation](#utilisation)
6. [Le modèle](#le-modèle)
7. [Performances](#performances)
8. [Dépannage](#dépannage)
9. [Fonctionnement technique](#fonctionnement-technique)
10. [Crédits et licences](#crédits-et-licences)

---

## Prérequis

| | Minimum | Recommandé |
| --- | --- | --- |
| Système | Windows 10 ou 11, 64 bits, ou macOS 26 ou plus récent sur Mac à puce Apple (M1 et suivants) | Windows 11 ; macOS récent |
| Mémoire vive | 24 Go | 32 Go |
| Disque libre | 35 Go | 50 Go (60 Go avec le modèle Q8_0) |
| GPU | Windows : tout GPU compatible Vulkan 1.3 (Radeon intégré, Intel Iris Xe/Arc, NVIDIA, AMD) ; Mac : la puce Apple | GPU dédié (Windows) |
| Python | 3.10 ou plus récent | 3.12 à 3.14 |
| Connexion | ≈ 15 Go à télécharger une seule fois (≈ 22 Go avec Q8_0) | |

Aucun droit administrateur n'est nécessaire : tout s'installe dans le dossier du projet.

Python sous Windows : l'installer depuis [python.org](https://www.python.org/downloads/windows/) (cocher « Add python.exe to PATH »)
ou depuis le Microsoft Store. Sur Mac, le Python livré avec les outils Xcode est trop ancien (3.9) : installer un
Python récent avec [Homebrew](https://brew.sh) (`brew install python@3.13`) ou depuis [python.org](https://www.python.org/downloads/macos/).
Vérifier dans un terminal :

```bat
python --version
```

Sur Mac : `python3.13 --version`. Le moteur Mac publié par stable-diffusion.cpp exige macOS 26 ou plus récent ;
il a été testé sur une puce M6 sous macOS 27.

## Installation

**1. Récupérer le projet**

```bat
git clone https://github.com/matwi5/chambre-noire.git
cd chambre-noire
```

Sans git : bouton **Code → Download ZIP** sur GitHub, puis décompresser le dossier où vous voulez
(évitez les dossiers synchronisés OneDrive, le modèle est volumineux).

**2. Créer l'environnement Python isolé et installer les dépendances**

```bat
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Sur Mac :

```bash
python3.13 -m venv venv
venv/bin/python -m pip install -r requirements.txt
```

**3. Télécharger le moteur et le modèle**

```bat
venv\Scripts\python.exe setup.py
```

Sur Mac : `venv/bin/python setup.py`. Ce script, à lancer une seule fois :

- télécharge stable-diffusion.cpp (version épinglée et vérifiée par SHA256) dans `sdcpp\` : versions Vulkan et CPU
  sous Windows (release `master-890`), version Metal sur Mac (release `master-959`) ; relancé après une mise à jour de
  ce dépôt, il remplace un moteur dont la version épinglée a changé ;
- télécharge les fichiers du modèle depuis Hugging Face dans `models\` (≈ 14,6 Go sous Windows, ≈ 15,1 Go sur Mac)
  et vérifie chacun contre son empreinte SHA256 (voir [Le modèle](#le-modèle)) ;
- sous Windows, prépare l'encodeur de texte pour stable-diffusion.cpp ;
- crée le raccourci **`Chambre noire.lnk`** (Windows) ou **`Chambre noire.command`** (Mac) dans le dossier (et retire
  `Qwen-Image.lnk` ou `Qwen-Image.command`, raccourci de l'ancien nom de l'application, s'il reste) ;
- lance trois courtes générations pour calibrer les estimations de durée sur votre machine
  (voir [Performances](#performances) ; `--no-calibrate` pour s'en passer). Si elles échouent, l'erreur est affichée
  et l'installation continue sans calibration (rappel à la fin, avec la commande pour réessayer).

**Plus de fidélité ?** Ajoutez `--q8` : le modèle Q8_0 (≈ 7,6 Go de plus) est installé à côté du modèle Q4_K_M.
Il rend mieux les détails fins et le texte écrit dans l'image ; il demande ≈ 3 Go de mémoire de plus.
On choisit ensuite le modèle au lancement (voir [Lancement](#lancement)).

```bat
venv\Scripts\python.exe setup.py --q8
```

**Carte NVIDIA ?** Ajoutez `--cuda` : le moteur CUDA (≈ 900 Mo de plus) est installé et devient le moteur par défaut.
Tout le calcul passe alors sur la carte, encodeur compris, ce qui est bien plus rapide qu'avec Vulkan.

```bat
venv\Scripts\python.exe setup.py --cuda
```

Les téléchargements reprennent seuls si la connexion coupe (cinq tentatives), et là où ils s'étaient arrêtés si l'on
relance la commande. Pour vérifier une installation sans rien télécharger : `venv\Scripts\python.exe setup.py --check`
(sur Mac : `venv/bin/python setup.py --check`).

## Lancement

Double-cliquer sur **`Chambre noire.lnk`** sous Windows (on peut l'épingler à la barre des tâches ou au menu Démarrer),
ou sur **`Chambre noire.command`** sur Mac (on peut le glisser dans le Dock).

Une fenêtre noire (Windows) ou de Terminal (Mac) s'ouvre : c'est le moteur, **laissez-la ouverte**. Le navigateur
s'ouvre ensuite sur **http://127.0.0.1:7860/**. Pour arrêter, fermez cette fenêtre.

Équivalent en ligne de commande, depuis le dossier du projet :

```bat
venv\Scripts\python.exe tools\launch.py
```

Sur Mac : `venv/bin/python tools/launch.py`.

Options : `--port 7860` (changer de port), `--model q4|q8` (modèle Q4_K_M par défaut, Q8_0 s'il a été installé par
`setup.py --q8`), `--backend vulkan|cuda|cpu` (Windows : forcer un moteur ; par défaut CUDA s'il est installé, sinon
Vulkan ; sur Mac, le moteur est toujours Metal), `--no-browser`. Pour lancer Q8_0 par le raccourci, ajoutez
`"model": "q8"` dans `tools/config.local.json` (réglages propres à la machine, non suivis par git, lus par-dessus
`tools/config.json`). La pastille d'état en haut à droite indique le modèle utilisé ; un appui ouvre
le panneau **Moteur** (moteur, modèle, calibration des estimations, version du code servi, journal) : la ligne
**Version** dit quel commit tourne (utile pour savoir si un correctif est en ligne sur le téléphone), et **Serveur**
« à relancer » apparaît quand `tools/launch.py` ou `tools/estimate.py` a changé depuis le lancement du serveur (le
reste est en ligne sans relance).

Par défaut, l'interface n'écoute que sur `127.0.0.1` : elle n'est pas accessible depuis le réseau.

## Depuis un téléphone

Avec l'option `--lan`, l'interface est aussi accessible depuis un téléphone ou une tablette du même Wi-Fi. Tout le
calcul reste sur l'ordinateur : le téléphone n'affiche que l'interface.

- **Code d'accès** : au premier lancement avec `--lan`, un code est créé dans `tools/access_code.txt`. Sur
  l'ordinateur, le bouton **Téléphone** en haut de l'interface l'affiche avec l'adresse à taper sur le téléphone
  (par exemple `http://Nom-du-Mac.local:7860`). Le téléphone le demande une fois, puis le retient un an. Tout appareil
  autre que l'ordinateur lui-même doit le saisir. Pour en changer, supprimez le fichier et relancez.
- **Adresses acceptées** : l'interface ne répond qu'aux adresses `127.0.0.1`, `localhost` et à celles affichées par le
  bouton **Téléphone** (nom `.local` et adresse IP de l'ordinateur au démarrage) ; tout autre nom est refusé, même
  sans `--lan`. Si l'adresse IP de l'ordinateur change, l'ancienne est refusée jusqu'au redémarrage de l'interface :
  préférez l'adresse en `.local` sur le téléphone. Depuis l'ordinateur, ouvrir l'adresse du Wi-Fi demande aussi le code.
  Si [Tailscale](https://tailscale.com) est connecté sur l'ordinateur au démarrage, ses noms et son adresse `100.x`
  s'ajoutent à la liste : l'interface est alors joignable hors du Wi-Fi depuis un appareil du même compte Tailscale,
  avec le même code.
  Les envois venant d'une page d'un autre site (formulaire ou script) sont refusés : seule l'interface elle-même peut
  lancer une génération, annuler ou supprimer une image.
- **Installer comme une application (Android, Chrome)** : Chrome n'installe une page qu'en HTTPS. Tailscale le fournit
  avec un certificat valide : activez une fois **HTTPS Certificates** dans la console d'administration Tailscale (page
  DNS, MagicDNS doit être actif), puis publiez l'interface sur le réseau Tailscale :

  ```bash
  tailscale serve --bg 7860
  ```

  Après le redémarrage de l'interface, le bouton **Téléphone** affiche en premier l'adresse
  `https://<nom-du-mac>.<réseau>.ts.net/`. Ouverte sur le téléphone (Tailscale connecté), elle demande le code une fois,
  puis le menu de Chrome propose **Installer l'application** : icône sur l'écran d'accueil, plein écran, et une page
  « Ordinateur injoignable » quand le Mac ne répond pas. `tailscale serve --https=443 off` retire cette publication.
  Les requêtes relayées par Tailscale demandent toujours le code, même si elles arrivent sur le Mac par `127.0.0.1` ;
  sans `--lan`, elles sont refusées. Sur iPhone, Safari → Partager → **Sur l'écran d'accueil** fonctionne aussi en HTTP.
- **Notification de fin de génération** : à la fin de chaque génération (ou en cas d'échec), l'ordinateur envoie une
  notification au téléphone, même si l'application y est fermée ou en arrière-plan ; la toucher rouvre l'application.
  L'autorisation est demandée au premier appui sur **Générer** ; l'interrupteur **Notification en fin de génération**
  du panneau Réglages les coupe. Elles ne passent que par l'adresse HTTPS de Tailscale (pas par l'adresse `http://` du
  Wi-Fi), ou sur l'ordinateur lui-même. Le message transite chiffré par le service de notification du navigateur
  (Google pour Chrome) et ne contient ni le prompt ni le nom du fichier : « Image prête — Générée en 12 min 14 s ·
  1024×1024 » (dans l'espace privé, le même message qu'une image normale, pour que rien ne le trahisse). Un lot
  (plusieurs images d'une seule demande, voir [Créer une image](#créer-une-image-labo)) n'envoie qu'une notification, à
  la fin de
  sa dernière image : « 3 images prêtes », « 2 images prêtes, 1 en échec », « Échec du lot » si aucune n'a réussi
  (le même message qu'un lot normal dans l'espace privé), et rien si tout le
  lot a été annulé. Il faut la bibliothèque `pywebpush` (installée par `requirements.txt` ; sur une installation
  antérieure, relancer `pip install -r requirements.txt`). L'ordinateur garde
  sa clé d'envoi dans `tools/push_vapid.pem` et les appareils abonnés dans `tools/push_subscriptions.json` ; supprimer
  ces fichiers désabonne tous les appareils.
- **Barre d'état** : dans l'application installée, Chrome peint la barre d'état (heure, notifications) d'une couleur
  unie ; il ne laisse pas encore une application installée dessiner dessous. L'interface lui donne la couleur du fond de
  l'espace affiché (noir chaud, ou vert-noir dans l'espace privé), et dans la visionneuse celle du haut de l'image
  floutée, pour que l'application semble continuer jusqu'en haut ; jamais dans l'espace privé, où la visionneuse
  garde la couleur du fond, pour qu'aucune image privée ne soit lue pour la calculer.
- **Veille** : sur Mac, l'ordinateur ne se met pas en veille tant que l'interface tourne avec `--lan` (l'écran peut
  s'éteindre).
- **Toujours disponible (Mac)** : pour que l'interface démarre seule à l'ouverture de session, sans fenêtre,
  accessible depuis le Wi-Fi :

```bash
venv/bin/python tools/make_service.py
```

`venv/bin/python tools/make_service.py --remove` retire ce démarrage automatique. Les deux commandes retirent aussi
le service de l'ancien nom de l'application (`com.matwi5.qwen-image-local`), s'il est installé. Le journal du service
est dans `logs/service.log`. Le raccourci `Chambre noire.command` ouvre alors simplement l'interface déjà lancée.

## Utilisation

L'interface a deux onglets aux icônes en pixels, dans la barre du bas : **Labo** (en haut, la génération en cours, la
file d'attente et les images terminées de la page ; dessous, le champ de création : texte → image, édition avec des
images d'entrée, ou dessin guidé sur une image) et **Tirages** (les images gardées) ; elle s'ouvre sur le Labo. Sur un
grand écran, le Labo est une colonne centrée et les Tirages prennent toute la largeur. Sur un écran tactile, glisser le
doigt vers la gauche ou la droite passe à l'onglet voisin (sauf sur le champ de création). Elle s'adapte au téléphone
comme à l'ordinateur, toujours sombre, même quand le système est en mode clair :
lumière inactinique de chambre noire (noir chaud, halo rouge de la lampe, grain léger, textes couleur papier, accent
ambre, erreurs en rouge vif avec leur icône). Sur un écran tactile, elle allège ses animations pour rester fluide ;
ajouter `?lite=1` ou `?lite=0` à l'adresse force l'un ou l'autre rendu.

### Réglages communs

Sous le texte, trois pastilles résument le format, la résolution et les étapes ; un appui ouvre le panneau
**Réglages**. Tous les réglages sont à valeurs fixes :

| Réglage | Choix | Effet |
| --- | --- | --- |
| **Format** | 1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16, et « Image » (les proportions de l'image) quand une seule image est chargée | Proportions de l'image produite |
| **Résolution** | 360p (512×512) · 540p (768×768) · **720p** (1024×1024, par défaut) · 1080p (1536×1536) · 1440p (2048×2048, 2K natif du modèle) | Nombre de pixels, nommé d'après le format vidéo qui en compte autant (720p : ≈ 0,9 à 1 million de pixels) ; les dimensions exactes, qui dépendent du format, s'affichent en bas du panneau |
| **Étapes** | Low 8 · Medium 12 · High 20 · XHigh 30 · **Max 40** (par défaut, réglage officiel du modèle) | Finesse des détails ; chaque option affiche le **temps estimé** |
| **Images** (hors campagne) | **1**, 2, 3 ou 4 | Nombre de variantes du même prompt, chacune avec sa graine, avec ou sans images d'entrée, dessin compris (voir [Créer une image](#créer-une-image-labo)) ; le temps affiché est celui de toutes les images |
| **Aperçu toutes les 5 étapes** | interrupteur, activé par défaut | Montre l'image en cours de formation ; coût affiché à côté |

Le bouton **Générer** affiche le temps estimé. Le navigateur retient les réglages choisis et le texte en cours de
l'espace public (un seul brouillon).

Conseil : **540p + 12 étapes** pour chercher la bonne formulation, puis montez la résolution et les étapes pour la version finale.
Les descriptions en **anglais, longues et précises** donnent les meilleurs résultats.

**Générer** reste actif pendant une génération : chaque appui ajoute une demande à la **file d'attente**, avec les
réglages du moment, et remonte en haut du **Labo**. Dès que le Mac accepte la demande, la saisie est vidée pour la
suivante de ce qui est parti : texte et son brouillon, images d'entrée d'une édition (campagne comprise : l'interrupteur
**Campagne** reste tel quel), image et tracé d'un dessin ; ce qui a été tapé ou ajouté pendant l'envoi reste ; les
Réglages ne bougent pas (seul le format « Image », qui suit l'image, part avec elle). Si la demande est refusée (erreur
du Mac, Mac injoignable, génération longue non confirmée), rien n'est vidé et la page ne bouge pas. Le Mac calcule les
générations une à une, dans l'ordre d'arrivée (sauf celles passées en tête depuis la file d'attente), qu'elles viennent
de l'ordinateur ou du téléphone.

Le **Labo** montre en haut, en grand, la génération en cours. Lancée par la page : l'étape, le temps restant,
les aperçus et un bouton d'annulation (une génération annulée ne laisse aucun fichier : ni image, ni images d'entrée, ni
aperçus, ni journal du moteur) ; une génération de la page qui attend affiche sa place dans la file et le temps avant
son image. Lancée par un autre appareil : son texte, un cadre aux proportions demandées, ses réglages et une progression
estimée, sans aperçu, avec l'annulation là où l'appareil y a droit. Quand le Mac calcule une génération que l'espace où
l'on est ne voit pas, le haut de la page dit « En attente » et le temps avant le début de la première génération de
l'espace. Quand la file est vide et qu'il n'y a aucune terminée, il dit « Rien en cours », au-dessus du champ de
création.
Sous la génération en cours, la **file d'attente** de l'espace, en cartes, dans l'ordre de calcul, sous un en-tête qui
dit combien de générations attendent et à quelle heure la file sera vide (« 4 en attente · file vide vers 15 h 10 (≈ 60
min) »). Une carte par demande : une génération seule, ou tout un lot (« 3 variantes », « Campagne · 6 photos ») avec
une case par image, en attente, en cours, faite (avec sa vignette pour un lot de la page), en échec ou annulée (pour un
lot d'un autre appareil, « sortie » quand l'image n'est plus dans la file). Chaque carte montre une vignette (l'image
d'entrée pour une édition ou un dessin de la page, sinon un cadre aux proportions demandées), le début du prompt, la
ligne des réglages (« 16:9 · 720p · 40 étapes »), l'heure à laquelle la demande sera prête (« prête vers 14 h 32 ») et
sa durée, et « autre appareil » pour une génération normale lancée ailleurs (rien dans l'espace privé). La génération en
cours n'a pas de carte, sauf dans celle de son lot. Les boutons d'une carte annulent la génération ou tout ce qui reste
du lot, et **Passer en tête** la fait passer, avec tout le lot, juste après celle en cours (pour un essai rapide bloqué
derrière une campagne) ; la flèche d'une carte de lot la déplie, avec une ligne par image pour l'annuler ou la faire
passer en tête seule. Une génération normale s'annule ou passe en tête depuis n'importe quel appareil. La file et la
pastille ne montrent que les générations de l'espace où l'on est (public, ou espace privé) : rang et « +N en attente »
ne comptent qu'elles. La pastille d'état en haut suit la génération en cours depuis n'importe quel onglet et affiche
« +N en attente » (« +N » seul quand l'écran est trop étroit pour tout contenir) ; un appui mène au Labo (au
panneau Moteur quand rien de l'espace n'est en file). L'onglet **Labo** porte le nombre de générations de l'espace
en cours et en attente (rien à zéro), et son icône un anneau qui suit la génération en cours. Une génération qui attend
derrière une génération de l'autre espace affiche « en attente » et un temps qui compte ce travail caché, sans ligne
pour lui ; si rien de l'espace ne tourne, la pastille dit « En attente » et le temps avant le début de la première, et
si l'espace n'a rien en file, elle reste éteinte même quand le Mac calcule pour l'autre espace. On peut recharger la
page sans rien perdre : elle se rattache aux générations normales qu'elle avait lancées (retenues par le navigateur),
pas à celles des autres appareils, qui restent visibles dans la file ; dans l'espace privé, à toutes les générations
privées en cours (voir « Espace privé »). Une génération ainsi reprise garde son prompt complet (sous l'image, et pour
**Reprendre** depuis la visionneuse), pas seulement le début qu'en montre la file. Chaque image terminée est
enregistrée en PNG dans la pile, **`outputs\.pile\`**, où elle attend d'être triée : gardée, elle passe dans
`outputs\` (les Tirages) ; jetée, elle est effacée. Ses images d'entrée (références, image d'origine, zone peinte) sont
dans `outputs\.inputs\`.

Sous la file, les **terminées** : les générations finies de la page, la plus récente en premier. Une image a sa vignette
(un appui l'ouvre en grand, avec ses images d'entrée), son texte, ses réglages et ses actions : **Télécharger**,
**Partager** et **Copier** (dans le presse-papiers), **Éditer** et **Dessiner**, qui la réutilisent comme point de
départ, **Relancer** et **Supprimer**. Un lot fini s'y montre en grille, une case par image en échec avec son message,
et **Relancer** sur sa carte refait tout le lot ; une génération en échec garde son message et **Relancer** ; une
génération annulée n'y laisse rien. Une carte de lot ou d'échec reprise après un rechargement n'a pas **Relancer** (la
page n'a plus la demande). Le « × » d'une carte la retire de la liste sans la supprimer de la pile, **Tout retirer**
vide la liste. La liste garde au plus 12 générations (les deux espaces comptent ensemble) : au-delà, la plus ancienne en
sort d'elle-même, échecs compris. Elle repart vide après un rechargement de la page (les images sont dans la pile) ;
les générations reprises y arrivent à leur fin. Quand une génération de la page finit pendant qu'on est sur les
Tirages, un message le dit (« Image prête », « Lot prêt · 3 images », avec « , 1 en échec » s'il y en a, « Échec de la
génération », « Échec du lot ») et mène au Labo quand on le touche ; rien pour une génération annulée. Partager et
Copier ne sont proposés que là où le navigateur les permet : sur l'ordinateur lui-même, ou sur le téléphone par
l'adresse HTTPS de Tailscale (pas par l'adresse `http://` du Wi-Fi).

### Créer une image (Labo)

Sous la génération en cours, le Labo a un seul champ de texte et une seule liste d'**images d'entrée**. Sans image
d'entrée, la génération part du texte :
écrire la description, ajuster les réglages si besoin, appuyer sur **Générer**. Avec des images, c'est une
**édition** (voir plus bas). L'exemple affiché dans le champ vide suit la saisie : décrire l'image sans image
d'entrée, dire quoi changer avec des images.

Pour obtenir plusieurs propositions du même prompt, choisir 2, 3 ou 4 **Images** dans les Réglages (une pastille « 3
images » le rappelle sous le texte ; le choix est retenu). Une seule demande lance alors un **lot de variantes** : une
génération par image, à la suite dans la file (jamais en même temps), chacune avec sa propre graine. Le bouton
**Générer** affiche le temps de tout le lot. Pendant le calcul, l'image en cours porte « Image 2 sur 3 » et la file
d'attente montre tout le lot sur une seule carte, une case par image, dont l'annulation arrête tout le lot (le bouton de
l'image en cours n'annule que celle-ci, et une image en échec n'arrête pas les autres). À la fin, le lot entre dans les
terminées en **grille** : un appui ouvre une image en grand, avec sa graine, et **Garder celle-ci** supprime les autres
images du lot après confirmation. Sans choix, toutes les images restent dans les Tirages.
Les variantes marchent de la même façon avec des images d'entrée (hors campagne) et en dessin : plusieurs essais
de la même édition, chacun avec sa graine, à départager par **Garder celle-ci**.

**Édition** : ajouter 1 à 10 images d'entrée par **Ajouter des images**, au-dessus du texte (elles sont numérotées 1,
2, 3…, et un « × » retire une image ; PNG et JPEG partent tels quels, WebP, AVIF ou TIFF, que le moteur ne lit pas,
sont convertis en PNG par le serveur), une à une ou plusieurs d'un coup dans le sélecteur (elles sont ajoutées dans
l'ordre de sélection), en les déposant sur **Ajouter des images**, en collant une image copiée (Cmd+V sur le Mac,
« Coller » sur le téléphone ; un texte collé dans le champ reste un texte), ou par **Éditer** sur une image de la
Tirages, des terminées ou des images d'entrée, puis écrire une **instruction** :

- « Replace the sky with a dramatic orange sunset, keep everything else unchanged »
- « The woman in image 1 wears the jacket from image 2 »

Avec une seule image, le format « Image » est présélectionné pour garder ses proportions.
Les images trop grandes sont réduites automatiquement à 2048 px de côté. Au-delà de 10, les images en trop ne sont pas
ajoutées et un message le signale.

**Campagne** : pour appliquer la même instruction à toute une série de photos (« 6 voitures rouges → 6 voitures
bleues »), activer l'interrupteur **Campagne** sous les images (le choix est retenu ; il n'est proposé qu'à partir
de 2 images, et ignoré tant qu'il ne l'est pas : une seule photo est une édition simple).
Chaque photo est alors éditée seule, avec cette seule photo en référence : une image par photo, jusqu'à 10 photos, au
lieu d'une image qui les combine. Le compteur passe à « n photos », la pastille « Campagne · n photos » remplace celle
du format, et le choix du format disparaît des Réglages : chaque image prend la forme de sa photo (le format pris en
charge le plus proche, à la résolution choisie, côtés multiples de 32 ; une photo en portrait reste en portrait). Le
temps estimé additionne les photos une à une. La campagne est un lot comme les variantes : suivie image par image
(« Photo 2 sur 6 »), annulable en entier depuis la file d'attente, une seule notification à la fin, une grille des
images, et chaque image garde sa photo comme image d'entrée dans les Tirages ; elle n'a pas de variantes (le choix du
nombre d'images disparaît) ni de **Garder celle-ci**, chaque image venant d'une photo différente. Interrupteur
désactivé, l'édition reste celle d'avant (1 à 10 références combinées en une image).

### Dessiner (dessin guidé)

Le bouton **Dessiner**, sous les images d'entrée du Labo, transforme l'unique image d'entrée en dessin :

1. Avec une image, **Dessiner** active le dessin sur elle ; sans image, il fait choisir une image, puis active le
   dessin. À plusieurs images, il est grisé (« Dessiner se fait sur une seule image »).
2. Peindre en rouge la zone à modifier (taille du pinceau réglable, gomme, bouton pour tout effacer).
3. Choisir le mode :
   - **Masque** : seule la zone peinte est régénérée, tout le reste est conservé au pixel près ;
   - **Annotation** : le trait rouge est montré au modèle, qui s'en sert comme repère (méthode officielle de Qwen,
     pratique pour plusieurs zones à la fois).
4. Écrire une instruction : « Replace the object in the painted area with a small stone fountain ».

Pendant le dessin, aucune image ne s'ajoute (choix, dépôt, collage ou **Éditer** : « Désactivez Dessiner pour
ajouter d'autres images »), la campagne n'est pas proposée, et **Générer** refuse une demande sans zone peinte. Un
nouvel appui sur **Dessiner** l'éteint sans perdre le tracé, retrouvé en le rallumant tant que l'image reste ;
retirer l'image (« × ») éteint le dessin et efface le tracé. **Dessiner** sur une image des Tirages, des terminées ou
des images d'entrée la met seule dans la saisie, dessin actif et tracé vierge, après confirmation si la saisie
contenait déjà des images (« Remplacer les 2 images de la saisie par celle-ci ? »).

Formulez toujours une **instruction** (« Replace … with … »). Une simple description (« a fountain ») pousse souvent
le modèle à redessiner l'original.

### Tirages

L'onglet **Tirages** montre toutes les images de `outputs\`, la plus récente d'abord. Un appui sur une miniature
l'ouvre en plein écran avec ses réglages (date, usage, taille, étapes, modèle, durée, et la graine quand elle est connue). Glisser sur le côté passe
à l'image voisine (flèches du clavier sur ordinateur), glisser vers le bas ferme, un appui sur l'image masque les
commandes. Pour zoomer (jusqu'à ×6), pincer l'image : elle passe au-dessus de tout, peut couvrir tout l'écran, suit les
doigts, et revient à sa taille dès qu'on les relâche. Sur ordinateur, la molette zoome, glisser déplace l'image et un
clic la remet à sa taille. En haut à droite : **Partager**, **Copier** et **Télécharger** ; en bas : **Éditer** (ajoute
l'image aux images d'entrée du Labo), **Dessiner**, **Reprendre**, **Relancer** et **Supprimer** (définitif, après
confirmation : images d'entrée, dossier de travail et ligne du journal des générations compris). Le champ de création
n'est pas sur les Tirages.

**Reprendre** remet dans le Labo la saisie d'où vient l'image, à la place de la saisie en cours (après confirmation si
elle n'est pas vide) : son texte, ses réglages (format, résolution, étapes) et ses images d'entrée selon son usage.
Une édition revient avec ses références (Campagne éteinte : c'était une seule édition) ; un dessin en masque avec son
image de départ, Dessiner actif en masque et le tracé vide (la zone peinte n'est pas gardée) ; une annotation revient
en édition, avec sa référence où le trait rouge est déjà dessiné. Les images d'entrée se lisent dans les Tirages
(publique ou privée), ou, pour une image des terminées, dans la demande que la page a gardée. Si l'on tape ou ajoute une
image pendant la lecture des images, la confirmation est redemandée. Le geste est absent pour une édition ou un dessin
dont les Tirages n'ont pas gardé les images d'entrée (images anciennes).

**Relancer** refait la même demande avec une nouvelle graine, sans toucher la saisie du Labo, puis mène en haut du
**Labo**, comme **Générer** : dans l'espace où l'on est (dans l'espace privé, tout part en privé). Pour une image des
terminées, c'est la demande que la page a gardée (une image d'un lot : cette image seule ; la carte du lot : tout le
lot, mêmes variantes ou mêmes photos de campagne). Pour une image des Tirages, ou une image reprise après un
rechargement, la demande est refaite à partir de l'image : son texte, ses images d'entrée, ses dimensions, ses étapes
et son usage (une annotation repart en annotation), pour une seule image ; le geste est absent pour un dessin en masque
(le masque n'est pas gardé avec l'image) et pour une édition dont les images d'entrée ne sont pas connues.

Une image ne s'affiche qu'une fois chargée : sa miniature d'abord, puis l'image complète, sans jamais laisser voir un
instant l'image vue avant (ni celle d'une autre image, ni celle de l'autre espace). Les images voisines de la
visionneuse et des images d'entrée sont chargées en avance, pour que glisser de l'une à l'autre soit immédiat, comme
la première image d'entrée dès que l'image est affichée ; en revenant aux Tirages, celle de l'autre espace ne
réapparaît pas le temps du chargement. Pendant une génération, chaque aperçu reste à l'écran jusqu'à ce que le
suivant soit prêt.

Les images d'un même lot (variantes ou campagne) portent un repère « 2/4 » (leur rang dans le lot) tant qu'il en reste
au moins deux dans les Tirages. Dans la visionneuse, **Voir le lot** montre les images du lot côte à côte ; un appui en
ouvre une en grand, et l'on passe de l'une à l'autre en glissant. **Tout télécharger** enchaîne le téléchargement de
chaque image du lot (une par fichier, pas d'archive ; le navigateur peut demander d'autoriser plusieurs
téléchargements), et **Garder celle-ci** (variantes seulement) supprime les autres images du lot après confirmation.

Pour une édition ou un dessin guidé, le bouton **Image d'entrée** (ou **N images d'entrée**) ouvre les images de départ
en grand, une par une, avec les mêmes gestes que la visionneuse : pincer pour zoomer (molette sur ordinateur), glisser à
gauche ou à droite pour passer de l'une à l'autre, vers le bas pour fermer. Chacune peut être téléchargée, ou reprise
par **Éditer** (images d'entrée du Labo) ou **Dessiner** pour repartir d'elle. Les images d'entrée sont conservées
depuis le 13/10/2026 ; pour les images plus anciennes, elles ont été récupérées tant que leur dossier de travail
existait encore (les 20 derniers).

### Prompts enregistrés

Le bouton **Prompts**, sous le champ de texte du **Labo**, ouvre la liste des prompts
enregistrés, le dernier utilisé en tête. Elle est gardée sur le Mac (`tools/saved_prompts.json`) : on retrouve sur le
téléphone ce qui a été enregistré depuis le Mac, et inversement. Dans l'espace privé, la liste est celle des prompts
privés, chiffrés avec l'espace (voir [Espace privé](#espace-privé)) ; les prompts types restent les mêmes.

- **Enregistrer le texte actuel** demande un titre (80 caractères au plus) et garde le texte du champ (4 000
  caractères au plus), modifiable avant d'enregistrer. Seuls le titre et le texte sont gardés, pas les réglages
  (format, résolution, étapes) : un prompt sert à tous les formats. 500 prompts au plus.
- Un appui sur un prompt remplace le texte du champ, quelle que soit sa catégorie, sans toucher aux images ni au
  dessin.
  Le premier passage entre crochets (`[couleur]`, par exemple) est sélectionné : il suffit de taper pour le remplacer.
  Le prompt passe en tête de la liste.
- Le filtre **Tous**, **Créer**, **Éditer**, **Dessiner** ne montre que les prompts de cette catégorie. La feuille
  s'ouvre filtrée sur la catégorie de la saisie (Créer sans image d'entrée, Éditer avec, Dessiner quand le dessin est
  actif), **Tous** à un appui ; un prompt enregistré prend la catégorie de la saisie à ce moment.
- Le crayon modifie le titre et le texte ; la corbeille supprime le prompt, après confirmation.
- Sous la liste, **Prompts types** : onze prompts prêts à l'emploi livrés avec l'application (`tools/prompt_types.json`),
  en lecture seule : repeindre, changer l'arrière-plan, retirer un élément, fond blanc produit, style aquarelle, heure
  dorée, ajouter un texte (Éditer) ; photo réaliste, portrait studio, illustration plate (Créer) ; remplacer la zone
  (Dessiner). Un appui en insère le texte comme pour un prompt enregistré, avec le premier passage entre crochets
  sélectionné ; **Dupliquer** le copie dans vos prompts enregistrés, où il se modifie à volonté. Le filtre s'y applique
  aussi.

### Espace privé

Un espace à part, chiffrée sur le Mac, qui ne s'ouvre qu'avec un **code privé**. Ce code est distinct du code
d'accès du téléphone et demandé sur chaque appareil, le Mac compris : connaître le code d'accès, ou ouvrir les dossiers
du Mac, ne suffit pas pour voir les images privées. C'est le seul mode de confidentialité : l'ancien mode incognito
est retiré, et un appareil qui l'avait allumé voit une seule fois, au chargement, « L'incognito n'existe plus : vos
images sont enregistrées. Pour la confidentialité, passez par l'espace privé. »

- Rien ne le signale à l'arrivée sur l'application. Son entrée est le **cadenas** de l'en-tête des **Tirages**,
  à côté du bouton Rafraîchir et aussi visible que lui : la première fois, il crée l'espace (code de 8 caractères au moins, lettres, chiffres, signes ;
  majuscules et minuscules comptent ; saisi deux fois).
- **En HTTPS ou sur le Mac seulement** : l'espace privé ne s'ouvre (création, entrée, Tirages privés, Changer le
  code) que sur le Mac lui-même ou par l'adresse HTTPS de Tailscale (celle en `https://` du panneau
  Téléphone). Par l'adresse `http://` du Wi-Fi, le code et les images passeraient en clair sur le réseau : le cadenas
  le dit et ne demande pas le code. Le téléphone doit donc passer par l'adresse HTTPS, ce qu'il fait déjà s'il a
  installé l'application depuis elle.
- Ensuite, le cadenas demande le code pour **entrer** dans l'espace privé, sur l'appareil où on le touche et seulement
  sur lui. Un code faux est suivi d'une attente d'une seconde. Dans l'espace privé, toute l'application passe en
  lumière inactinique verte : on sait où l'on est.
- Le cadenas **Sortir**, en haut à droite, ramène à l'application normale en verrouillant l'espace. Il se verrouille
  aussi seul après 15 minutes sans activité privée sur cet appareil, et à la fermeture ou au rechargement de
  l'application.
- Dans l'espace privé, **toute génération est privée** (texte → image, édition, dessin) : son image, ses images
  d'entrée, sa miniature, son prompt et ses réglages sont chiffrés sur le Mac. Le texte tapé n'est pas retenu par le
  navigateur. Une génération privée lancée va jusqu'au bout et est rangée chiffrée même si l'espace se verrouille avant
  la fin, ou si l'application est fermée ; sa notification est celle d'une image normale (« Image prête »), sans rien
  qui trahisse l'espace privé. Hors de l'espace privé, la file n'en montre rien ; dedans, chaque génération privée y a
  sa ligne complète (début du prompt, mode, rang dans son lot, temps restant), annulable, ainsi que son lot, quel que
  soit l'appareil qui l'a lancée.
- Les **variantes** et les **campagnes** marchent aussi dans l'espace privé : chaque image du lot est chiffrée, la
  grille et « Garder celle-ci » restent, et la notification est celle d'un lot normal (« N images prêtes »).
- L'espace privé a sa propre **pile** : une image privée terminée y attend d'être triée (la marque « à trier » est
  dans sa fiche chiffrée, jamais en clair sur le disque) ; gardée, elle passe dans les
  Tirages privés ; jetée, ses fichiers chiffrés sont supprimés. Les images privées d'avant la pile sont dans les
  Tirages.
- Les **Tirages** de l'espace privé ne montrent que les images privées, avec la même visionneuse : télécharger,
  partager, copier, images d'entrée, Éditer, Dessiner, Reprendre, Supprimer. En sortant, elles quittent l'écran.
- **Chaque espace a sa propre saisie** : texte, images d'entrée, dessin (actif ou non, masque ou annotation) et son
  tracé. En
  entrant dans l'espace privé, la saisie publique est mise de côté et la saisie privée revient (vide
  la première fois) ; en sortant, la saisie publique revient intacte. La saisie privée n'est jamais retenue par le
  navigateur, brouillons compris : elle ne survit pas à la fermeture de l'application. L'interrupteur **Campagne** et
  les Réglages sont communs aux deux espaces.
- **Sortir vide l'écran** : la saisie privée est effacée, comme les images privées du Labo, de la grille,
  des Tirages, de la visionneuse, des images d'entrée et de la feuille « Voir le lot » (fermée), même cachées, et les
  lignes du journal du panneau Moteur écrites dans l'espace : la page ne les garde plus prêtes à l'affichage, et celles
  qui chargeaient encore sont abandonnées (si le Mac est injoignable, un message le dit et l'on reste dans l'espace).
  Les générations privées en file ou en cours quittent aussi l'écran et la page (progression, aperçu, prompt, vignette,
  ligne de la file) : elles continuent sur le Mac et sont rangées dans l'espace, mais une page sortie ne peut plus ni
  les suivre, ni les prévisualiser, ni les annuler. Les générations publiques de la page, cachées pendant qu'on était
  dans l'espace privé (elles y restent suivies, hors de l'écran), reviennent, avec leur image si elles ont fini
  entre-temps.
- **Retour dans l'espace privé** : la page suit toutes les générations privées encore en file ou en cours, avec leur
  prompt et leur progression, qu'elle les ait lancées ou non, aussi après un rechargement ou depuis un autre appareil
  (aucun identifiant privé n'est gardé par le navigateur).
- **Fermeture automatique** : si l'espace se ferme seul (15 minutes sans activité privée), la saisie privée quitte
  l'écran comme à la sortie, mais la page la garde en mémoire : elle revient si l'on rentre sans avoir fermé
  l'application (un long texte en cours n'est pas perdu). Si l'espace privé est supprimé, elle est effacée. Quand
  l'espace se ferme sans que l'appareil l'ait demandé (15 minutes sans activité privée, espace supprimé ou code changé
  depuis un autre appareil), le champ en cours de saisie perd le curseur et un message dit « Espace privé fermé :
  retour dans l'espace public », pour que la suite de la frappe ne parte pas dans la saisie publique sans qu'on le
  voie ; rien de tel après « Sortir ».
- **Une image reste dans son espace** : une image publique ne devient pas privée, ni l'inverse (le bouton « Rendre
  privée » a été retiré le 16/10/2026). Pour garder une image en privé, on la génère dans l'espace privé.
- **Prompts enregistrés privés** : dans l'espace privé, le bouton **Prompts** montre les prompts enregistrés de
  l'espace privé et les prompts types, jamais ceux de l'espace public (et inversement). Ils se créent, s'utilisent, se
  modifient, se suppriment et se filtrent comme les autres, et **Dupliquer** un prompt type en fait un prompt privé.
  Ils sont chiffrés sur le Mac comme les images (`private/prompts`), rechiffrés au changement de code et effacés
  avec l'espace. Les prompts enregistrés depuis l'espace privé avant le 15/10/2026 sont restés dans la liste publique :
  les supprimer à la main.
- **Changer le code** demande l'ancien. Le Mac tire alors de nouvelles clés et rechiffre toutes les images privées
  et les prompts privés : elles restent lisibles avec le nouveau code, et une ancienne copie de l'espace
  (sauvegarde Time Machine du dossier `private/`) ne s'ouvre plus avec l'ancien code sur les images d'aujourd'hui ; une sauvegarde complète d'avant le
  changement garde, elle, les images qu'elle contenait, lisibles avec l'ancien code. L'espace se ferme sur tous les
  appareils. Une génération privée en cours est rangée avec les nouvelles clés. Une panne au milieu (arrêt du Mac) ne
  perd aucune image : selon le moment, l'ancien ou le nouveau code ouvre l'espace, avec toutes ses images.
- **Code oublié** : il ne peut pas être retrouvé, et les images privées sont perdues. **Supprimer l'espace privé**
  (après avoir tapé `SUPPRIMER`) efface tout l'espace sans demander le code, pour pouvoir en recréer un. Ce bouton
  n'agit que sur le Mac lui-même : depuis le téléphone ou un autre appareil, la feuille dit d'ouvrir l'application sur
  le Mac. Quelqu'un qui a accès à la session du Mac peut donc effacer l'espace privé, sans pouvoir le lire.
- Sans la bibliothèque `cryptography` (installée avec `requirements.txt`), l'espace privé n'apparaît pas.

Ce que cela garantit, et ses limites :

- le dossier `private/` ne contient que la clé publique de l'espace, sa clé privée chiffrée par une clé tirée du code
  (dérivation volontairement lente : chaque essai coûte du temps et de la mémoire, même sur une copie du disque), et
  les images et les prompts privés chiffrés, les images sous des noms tirés au hasard qui ne disent ni la date ni le
  mode (la date de modification des fichiers, elle, reste visible, comme leur taille et leur nombre). Le code n'est
  écrit nulle part ; la clé privée déchiffrée ne reste qu'en mémoire du serveur, le temps de la session de l'appareil. Le Mac
  chiffre une image privée sans le code, avec la seule clé publique : c'est ce qui permet de la ranger même espace
  verrouillé ;
- rien d'une image privée ne va dans `outputs\`, dans le journal des générations ni dans les mesures de calibration,
  et dans `logs\` rien d'autre que la ligne commune à toutes les générations (« [job] génération terminée », ou celle
  d'un échec ; le journal du moteur part à la poubelle) ;
- sd-cli ne travaille que sur des fichiers : pendant le calcul, les images d'entrée, les aperçus et le PNG final passent
  **en clair** par `jobs/private_<identifiant>/`, supprimé dès la fin de la génération (et au lancement suivant après un
  arrêt brutal). Sur un SSD, un fichier supprimé n'est pas effacé de façon sûre. Sur Mac, le dossier `jobs/` est exclu
  de Time Machine au lancement de l'interface (`tmutil addexclusion`, sans droits administrateur ; un échec est noté
  dans le journal sans bloquer) ;
- une image **téléchargée** ou partagée sort de l'espace privé : elle est alors en clair là où elle est enregistrée.

## Le modèle

Le modèle n'est pas inclus dans ce dépôt : GitHub refuse les fichiers de plus de 100 Mo et le modèle pèse près de 15 Go.
`setup.py` le télécharge depuis Hugging Face et le vérifie.

| Fichier | Rôle | Taille | Source |
| --- | --- | --- | --- |
| `qwen-image-2.1-Q4_K_M.gguf` | Modèle de diffusion [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1), 7 milliards de paramètres, quantifié 4 bits | 4,6 Go | [abenzerps, branche `base`](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/tree/base) |
| `qwen-image-2.1-Q8_0.gguf` (option `--q8`) | Même modèle quantifié 8 bits, plus fidèle | 7,6 Go | idem |
| `qwen3vl_8b_int8_convrot.safetensors` (Windows) | Encodeur texte et image Qwen3-VL-8B, int8 | 9,35 Go | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1), dossier `text_encoders` |
| `qwen_image_2.1_vae_bf16.safetensors` | Décodeur d'image (VAE) | 676 Mo | idem, dossier `vae` |
| `Qwen3VL-8B-Instruct-Q8_0.gguf` (Mac) | Même encodeur Qwen3-VL-8B, GGUF quantifié 8 bits | 8,7 Go | [Qwen/Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF) |
| `mmproj-Qwen3VL-8B-Instruct-F16.gguf` (Mac) | Sa tour vision, qui lit les images de référence | 1,16 Go | idem |

**Encodeur sur Mac.** Le GPU d'un Mac (Metal) n'a pas de calcul int8 dans stable-diffusion.cpp : l'encodeur int8 de
Comfy-Org y tournerait sur le processeur, à ≈ 2 min 30 par image de référence en 512×512. Le Mac prend donc la
version GGUF officielle de Qwen, qui tourne sur le GPU : ≈ 3 s pour la même référence, pour une image quasi
identique. Sur une installation Mac antérieure, `setup.py` télécharge ces deux fichiers et signale que les fichiers
`qwen3vl_8b_int8_convrot*.safetensors` (≈ 18,7 Go) ne servent plus et peuvent être supprimés.

**Quantifications du modèle.** Le modèle de diffusion est le modèle officiel de Qwen, quantifié en GGUF par abenzerps à
partir des poids d'origine (branche `base` de son dépôt Hugging Face). Les téléchargements sont épinglés sur un commit
précis de chaque dépôt : un renommage ou une mise à jour ultérieure ne change pas les fichiers installés.

**Variante communautaire (option).** `setup.py --uc` installe aussi la variante affinée publiée sur la branche
principale du même dépôt (`uc-q4`, et `uc-q8` avec `--q8`), à choisir par `--model uc-q4` ou `--model uc-q8`. Elle
n'est ni installée ni utilisée par défaut.

Empreintes SHA256 vérifiées par `setup.py` (identiques à celles des fichiers `SHA256SUMS` et des métadonnées des dépôts) :

```text
833439e91bc1152d28f37aa198c7f6f4218b7de95754c2f7a318a2422ab4b2f8  qwen-image-2.1-Q4_K_M.gguf
9a7ec02f4c9d5cf5b78e8efa6ccd81ec0c35a898defbf8e77ac7c02a32fe0d7e  qwen-image-2.1-Q8_0.gguf
8bfd0f6e12abf2d2d697ecc888e5e90b0d6741d6708f05799f53afa560452e8f  text_encoders/qwen3vl_8b_int8_convrot.safetensors
bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9  vae/qwen_image_2.1_vae_bf16.safetensors
0d264b3941185d00a74f75c4245521dae088ff1efc90ab8d1754e83f5844adb0  text_encoders/Qwen3VL-8B-Instruct-Q8_0.gguf
ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38  text_encoders/mmproj-Qwen3VL-8B-Instruct-F16.gguf
```

**Q4_K_M ou Q8_0 ?** Q8_0 est quasiment indiscernable de la pleine précision ; Q4_K_M perd un peu sur les détails fins
et le texte écrit dans l'image (constat général sur les modèles de diffusion quantifiés, non mesuré sur celui-ci).
En mémoire, comptez ≈ 14,6 Go de fichiers chargés avec Q4_K_M et ≈ 17,6 Go avec Q8_0 (sur Mac, 0,5 Go de plus),
plus la mémoire de calcul.

**Correctif de l'encodeur (Windows).** Dans ce fichier int8 (format ComfyUI), la table d'embeddings est elle aussi
quantifiée, ce que stable-diffusion.cpp (version `master-890-74988b2`) interprète mal : il plante au chargement.
`tools/fix_int8_te.py` en crée une copie `qwen3vl_8b_int8_convrot_embfix.safetensors` où seule cette table repasse
en bf16 (dé-rotation Hadamard comprise) ; toutes les autres couches restent en int8. Même taille, même qualité.
La release `master-959` charge le fichier d'origine sans ce correctif (vérifié sur Mac) ; il deviendra inutile sous
Windows quand le moteur Windows passera à cette version.

**Réglages officiels du modèle** (fiche Qwen) : 40 étapes, guidance 1, sampler Euler, pas de prompt négatif,
résolution native 2048×2048 (4:3 2400×1792, 3:2 2528×1696, 16:9 2752×1536 et inverses), jusqu'à 10 images de référence.
L'interface applique ces réglages ; la résolution 1440p correspond exactement aux tailles officielles.

## Performances

Un GPU intégré est lent pour un modèle de cette taille. Mesures de référence sur un portable
**AMD Ryzen 5 Pro 7535U, Radeon intégré (RDNA2), 32 Go de RAM**, backend Vulkan :

| Génération | Durée mesurée |
| --- | --- |
| Texte → image 512×512, 8 étapes | ≈ 4 min |
| Édition 512×512 (1 référence), 12 étapes | ≈ 10 à 11 min |
| Dessin guidé 512×512, 12 étapes | ≈ 10 à 11 min |
| Même machine, moteur CPU seul | plus de 8× plus lent (non recommandé) |

Ordres de grandeur sur cette machine : ≈ 16 à 20 s par étape en 512×512, ≈ 2 min par étape estimée en 1024×1024
(non mesurée : extrapolée du rapport mesuré entre texte → image et édition) ; une étape d'édition coûte plus du double
d'une étape de texte → image (l'image de référence double la séquence à traiter).
La résolution 1440p (2K natif) avec 40 étapes prend plusieurs heures : l'interface demande confirmation au-delà d'une heure.
Sur une carte NVIDIA avec le moteur CUDA, comptez de l'ordre de 1 à 2 s par étape en 1024×1024 (estimation non mesurée,
RTX 4060/4070) : une image 720p de 20 étapes en moins d'une minute.

**Estimations de temps calibrées.** Les temps affichés à côté de chaque réglage viennent d'un modèle de coût
(`tools/estimate.py`) :

- une étape coûte a·n + b·n², où n est la longueur de la séquence traitée : l'image produite plus chaque image de
  référence, que le moteur ramène à la même surface. a couvre les couches ordinaires, b l'attention, qui croît au
  carré de la séquence. Avec le cache de préfixe du moteur Mac (release `master-903` et suivantes), les étapes ne
  recalculent plus le texte ni les références : une étape coûte a·nt + b·nt·n, où nt ne compte que l'image produite,
  et la première étape calcule une fois la part des références ;
- l'encodage coûte un temps fixe pour le texte, plus un temps par mégapixel de référence (lue aussi par l'encodeur
  Qwen3-VL) ;
- le décodage de l'image, et de chaque aperçu, est proportionnel au nombre de pixels ;
- s'y ajoute une part fixe : chargement du modèle, premier pas plus lent.

Les coefficients partent de valeurs propres au moteur (Vulkan, CUDA, CPU, Metal), puis sont ajustés sur les mesures de
votre machine : les 40 dernières générations par moteur et par modèle, résumées par des médianes, si bien qu'une
génération anormale (machine occupée, premier chargement du modèle) ne fausse pas l'estimation. Chaque mesure garde
la version de stable-diffusion.cpp qui l'a produite : après une mise à jour du moteur, les anciennes mesures sont
ignorées et `setup.py` refait la calibration. Dès que deux tailles
d'image assez différentes ont été mesurées, a et b sont ajustés séparément, ce qui fiabilise les estimations en haute
résolution. Pour que ce soit le cas dès la première image, `setup.py` finit par trois courtes générations de
calibration (texte → image en 512 et 768 px, édition en 512 px) ; `--no-calibrate` les saute et
`tools/calibrate.py` les relance. Tant qu'aucune mesure n'existe, l'état indique « estimations non calibrées ».
Pendant une génération, le temps restant se fonde sur la moyenne des derniers pas. Les mesures sont stockées dans
`tools/calibration.json` ; supprimez ce fichier pour repartir de zéro (l'ancien format est ignoré).

Pour gagner du temps sans perte de qualité : branchez le portable sur secteur et choisissez le mode d'alimentation
« Performances optimales » dans les paramètres Windows.

**Mac à puce Apple.** Mesures sur une puce **Apple M6, 32 Go de mémoire unifiée**, moteur Metal (release
`master-959`), encodeur GGUF, modèle Q4_K_M :

| Génération | Durée mesurée |
| --- | --- |
| Texte → image 512×512, 8 étapes | ≈ 30 s |
| Édition 512×512 (1 référence), 8 étapes | ≈ 40 s |
| Dessin guidé 512×512 (masque ou annotation), 8 étapes | ≈ 40 s |
| Édition 1024×1024 (1 référence), 3 étapes | ≈ 1 min 40 |

Ordres de grandeur : ≈ 3 s par étape en 512×512, 7,6 s en 768×768, 16,3 s en 1024×1024 (avec la version précédente
du moteur, Q8_0 n'était pas plus lent que Q4_K_M sur Metal ; non remesuré) ; décodage de l'image ≈ 3 s en 512×512,
6 s en 768×768, 12 s en 1024×1024 ; encodage du texte 1 à 2 s. Chaque image de référence ajoute 1 à 3 s d'encodage
en 512×512, ≈ 5 s en 1024×1024, et le dessin guidé envoie lui aussi l'image au modèle comme référence. Grâce au cache
de préfixe, une étape d'édition coûte presque autant qu'une étape de texte → image (3,3 s contre 2,9 s en 512×512,
19 s contre 16 s en 1024×1024) ; seule la première étape lit en plus la référence (≈ 7 s de plus en 512×512, 22 s en
1024×1024). Avant ces réglages (release `master-890`, encodeur int8 et VAE sur le processeur), une édition 512×512 de
8 étapes prenait ≈ 4 min 10, dont ≈ 2 min 20 d'encodage de la référence et ≈ 33 s de décodage.
En 2048×2048 avec une référence et le modèle Q8_0, la première étape a pris 6 min (mesurée) ; les suivantes
devraient prendre ≈ 3 min chacune selon le modèle de coût (non mesurées).

## Dépannage

**Double-cliquer sur un fichier `.cmd` ne fait rien.** Certaines entreprises bloquent les scripts dans les dossiers
utilisateur (stratégie AppLocker). Utilisez le raccourci `Chambre noire.lnk`, qui lance directement `python.exe`.
S'il manque : `venv\Scripts\python.exe tools\make_shortcut.py`.

**La pastille d'état en haut à droite indique « Non prêt ».** Le panneau Moteur (un appui sur la pastille) affiche
les fichiers manquants. L'installation est incomplète :
`venv\Scripts\python.exe setup.py --check` puis `venv\Scripts\python.exe setup.py` (sur Mac : `venv/bin/python`).

**La génération échoue immédiatement.** Le détail est dans `jobs\<identifiant>\sd-cli.log`. Sous Windows, vérifiez que
Vulkan fonctionne :

```bat
sdcpp\vulkan\sd-cli.exe --list-devices
```

La liste doit contenir une ligne `Vulkan0`. Sinon, mettez à jour le pilote graphique, ou lancez l'interface avec
`--backend cpu`. Sur Mac, `sdcpp/metal/sd-cli --list-devices` doit afficher une ligne `MTL0`.

**Le PC rame ou la génération s'arrête pendant les grandes résolutions.** Le modèle occupe environ 14 Go de mémoire
pendant la génération. Fermez les applications gourmandes, ou restez en 540p ou 720p.

**L'antivirus bloque `sd-cli.exe`.** Ce sont les binaires officiels de stable-diffusion.cpp, vérifiés par SHA256 à
l'installation ; demandez une exception à votre service informatique si nécessaire.

**Mac : macOS refuse d'ouvrir `sd-cli` (« développeur non identifié »).** Cela n'arrive que si l'archive du moteur a
été téléchargée avec un navigateur ; `setup.py` ne pose pas cette marque. Pour la retirer :

```bash
xattr -dr com.apple.quarantine sdcpp/metal
```

**Mac : l'image sort en bruit (taches colorées sans rapport avec le prompt).** C'est le symptôme d'un moteur antérieur
à `master-959` lancé avec `--mmap` (`buffer is nil` dans `jobs/<identifiant>/sd-cli.log`) : relancez
`venv/bin/python setup.py`, qui installe la version épinglée.

**Mac : l'édition est longue avant la première étape.** L'installation date d'avant l'encodeur GGUF : l'encodeur int8
tourne alors sur le processeur, à ≈ 2 min par référence. Relancez `venv/bin/python setup.py`, qui installe le moteur
`master-959` et l'encodeur GGUF.

**Mac : en résolution 1440p avec des références, la mémoire est juste.** Sur 32 Go, une édition 2048×2048 fonctionne :
le moteur libère l'encodeur après usage et décode l'image par tuiles (avertissements « retrying with spatial tiling »
dans `jobs/<identifiant>/sd-cli.log`, sans effet sur le résultat).

**Linux.** L'interface et le lanceur sont en Python pur, mais `setup.py` ne télécharge que les binaires Windows et
macOS. Il faut récupérer la version Linux de stable-diffusion.cpp dans ses
[releases](https://github.com/leejet/stable-diffusion.cpp/releases), la placer dans `sdcpp/vulkan/` et ajouter Linux
aux plateformes connues de `setup.py` et `tools/launch.py`.

## Fonctionnement technique

```text
navigateur ──HTTP──▶ tools/launch.py (127.0.0.1:7860) ──lance──▶ sdcpp/<moteur>/sd-cli ──▶ jobs/<id>/ ─▶ outputs/.pile/
   tools/ui/index.html        file d'attente, suivi des étapes,         Vulkan : diffusion + VAE   (Windows)
                              aperçus, annulation                       CPU    : encodeur texte    (Windows)
                                                                        Metal  : tout              (Mac)
```

- Chaque génération lance `sd-cli` (`sd-cli.exe` sous Windows). Avec `--mmap` : après la première fois, le modèle se
  recharge en moins d'une seconde grâce au cache disque.
- Répartition selon le moteur :
  - Vulkan : `--backend diffusion=vulkan0,vae=vulkan0,te=cpu --offload-to-cpu`. L'encodeur int8 n'a pas de noyau
    Vulkan dans stable-diffusion.cpp, il tourne donc sur le processeur ;
  - CUDA : `--backend cuda0 --offload-to-cpu --diffusion-fa`. Tout est sur la carte ; l'encodeur int8 profite du
    chemin CUDA natif (RTX 20xx et plus récentes) ; les poids restent en RAM et sont copiés à la demande, ce qui
    s'adapte aux cartes à 8 Go ;
  - CPU : `--backend cpu`, secours sans GPU ;
  - Metal (Mac) : `--backend MTL0 --fa --mmap --params-backend te=disk --llm_vision <mmproj>`, avec
    stable-diffusion.cpp `master-959` et l'encodeur GGUF. Choix mesurés sur une puce M6 : l'encodeur int8 n'a pas de
    noyau Metal (sd-cli plante s'il est placé sur le GPU), l'encodeur GGUF y lit une référence 512×512 en ≈ 3 s ; le VAE
    décode 11 fois plus vite sur Metal que sur le processeur (3 s contre 37 s en 512×512) ; `--fa` (flash attention
    partout, tour vision comprise) évite une faute mémoire du GPU sur une référence en 2048×2048 ;
    `--params-backend te=disk` libère les poids de l'encodeur après l'encodage, ce qui laisse la place au cache de
    préfixe en très grande résolution ; `--mmap` fonctionne depuis `master-959` (les versions antérieures sortaient une
    image en bruit).
- API locale : `POST /api/generate`, `GET /api/job/<id>` (`queue_position` : rang parmi les générations de son espace,
  public ou privé, 0 pour celle qui tourne, sinon les générations de l'espace en attente devant elle, plus une si une
  génération tourne ; recalculé à chaque lecture ; `seed` : graine utilisée ; `lot` ; `prompt` : le prompt complet, tant
  que la demande est en mémoire, `null` pour une privée une fois finie, rangée, en
  échec ou annulée ; `mode` ; `inputs` : noms des images d'entrée gardées avec l'image, `init.png` puis `ref_1.png`…,
  ceux qu'attend `/api/input`), `GET /api/job/<id>/preview`, `POST /api/job/<id>/cancel` (sans effet sur une génération
  déjà terminée, réussie, en échec ou annulée), `POST /api/job/<id>/first` (« Passer en tête » : la génération passe en
  tête des générations en attente, juste après celle en cours, tous espaces confondus ; 200 `{"ok": true}`, aussi quand
  elle y est déjà ; 404 pour un identifiant inconnu ou une génération privée hors de l'espace privé, comme l'annulation,
  avant tout test d'état ; 409 pour une génération qui n'attend plus : en cours, finie ou annulée), `POST
  /api/lot/<id>/first` (toutes les générations du lot encore en attente, en tête dans l'ordre du lot ; 409 quand plus
  rien n'en attend, 404 une fois le lot fini ou pour un lot privé hors de l'espace privé ; aucune ligne dans les
  journaux du serveur, comme l'annulation), `GET /api/status` (`queue` : la file de l'espace de l'appareil, génération
  en cours d'abord, puis l'ordre de calcul : dans l'espace privé, ses seules générations privées ; ailleurs, les
  générations normales ; l'appareil est dans l'espace privé quand sa session est ouverte et que la requête
  est sûre, comme pour `private.unlocked` ; chaque entrée porte `status`, `position` (rang dans l'espace, comme
  `queue_position`), `ahead` (durée restante estimée, en secondes, des générations de l'autre espace placées devant elle
  : ce qui reste de celle en cours, l'estimation des autres ; 0 sans travail caché), `lot`, `estimate` et `elapsed` en
  secondes, `kind` (`normal` ou `private`), `id`, `mode`, le début du `prompt`, et `width`, `height` et `steps` de la
  demande ; `queued` : générations en attente de l'espace ; `current_job` : la génération en cours si elle est
  de l'espace, sinon `null` ; `last_job` : dernière génération normale, `null` dans l'espace
  privé ; `busy` : le Mac calcule, quel que soit l'espace ; `version` : `commit`, `date` et `branch` du dernier commit
  du dossier servi (`null` hors git) et `server`, empreinte de `tools/launch.py` et `tools/estimate.py`, relus toutes
  les 30 s ; `server_version` : la même chose au lancement du serveur, `null` sans `main()` ; `rev` : compteur de la
  pile et des tirages de l'espace de l'appareil, qui change à chaque image arrivée dans la pile et à chaque Garder,
  Jeter et Supprimer, et part de l'heure du lancement du serveur : l'interface relit pile et tirages quand il change) ;
  lots : `"count"` de 2 à 4 dans `/api/generate` (tous les modes ; 1 : génération seule ; 400 « count : pas de variantes
  dans une campagne »
  au-delà de 1 avec `campaign`) crée autant de générations ; `"campaign": [{"image": <data URL>, "width", "height"}, …]`
  (1 à 10 photos, en édition, `"mode": "edit"`, sans `ref_images`) crée une édition par photo, avec cette seule photo
  en référence et à ses dimensions (une seule photo : génération seule) ; les générations d'un lot passent à la suite
  dans la file, et la réponse devient `{"lot": {"id", "size", "campaign"}, "jobs": [...]}` ; chaque génération porte
  `lot` (`id`, `rank`, `size` et `campaign` : vrai pour une campagne, faux pour des variantes, quel que soit le mode ;
  une image d'avant ce marqueur n'en a pas et un lot du mode `edit` y compte comme une campagne), aussi écrit dans
  `outputs/journal.jsonl`, dans les Tirages et dans les réglages d'une image privée ; `POST /api/lot/<id>/cancel` annule
  toutes ses générations non terminées (404 une fois le lot fini).
  Graine `-1` : le serveur la tire lui-même (distincte pour chaque image d'un lot) et l'écrit au journal ; graine
  choisie avec `count` : graine, graine + 1… ; pile et tirages : une image normale terminée arrive dans la pile,
  `outputs/.pile/`, à trier (elle s'écrit dans son dossier de travail `jobs/<id>/`, puis y passe avec sa ligne du
  journal) ; les tirages sont les images de `outputs/`, dont toutes celles d'avant la pile ; `GET /api/pile` et `GET
  /api/history` (une entrée par image, la plus récente d'abord, avec `name`, `time`, `size`, `mode`, `prompt`,
  `width`, `height`, `steps`, `seconds`, `model`, `seed`, `inputs` et `lot` : `id`, `rank`, `size`, `campaign`, ou
  `null` pour une image seule), `POST /api/keep {"name"}` (Garder : l'image passe de la pile aux tirages, d'un seul
  `os.replace` ; vignettes et images d'entrée restent où elles sont, rangées par nom d'image ; 409 si un tirage du
  même nom existe), `POST /api/discard {"name"}` (Jeter : seulement une image de la pile ; efface le PNG, ses
  vignettes, ses images d'entrée, son dossier de travail `jobs/<id>/` et ses lignes du journal, réécrit dans un
  fichier temporaire puis remplacé d'un coup, les lignes illisibles recopiées telles quelles ; une pièce déjà absente
  est sautée), `POST /api/delete {"name"}` (Supprimer : seulement un tirage, effacé aussi complètement que Jeter) ;
  Garder et Jeter répondent 404 « déjà triée » pour une image qui n'est pas (ou plus) dans la pile, Supprimer 404
  « fichier inconnu » pour un nom qui n'est pas un tirage ; chacun se fait d'un bloc, sous un seul verrou : quand deux
  appareils trient la même image, le premier geste arrivé l'emporte. `GET /api/thumb?name=…` (miniatures gardées dans
  `outputs/.thumbs/`), `GET /api/result?name=…&download=1` et les images d'entrée servent un tirage comme une image de
  la pile ; images d'entrée d'une image : `GET
  /api/input?name=…&file=init.png|ref_N.png[&thumb=1][&download=1]` (gardées dans `outputs/.inputs/<image>/`) ; prompts
  enregistrés : `GET /api/prompts` (`{"saved": [...], "types": [...]}`, `saved` le dernier utilisé d'abord ; chaque
  prompt : `id`, `title`, `text`, `usage` = `t2i`, `edit` ou `mask`, `used` = dernière utilisation en secondes ; `types`
  : les prompts types de `tools/prompt_types.json`, sans `used`, qu'aucune route ne modifie), `POST /api/prompts
  {"title", "text", "usage"}` (création) ou `{"id", "title", "text"}` (modification du titre et du texte), `POST
  /api/prompts/delete {"id"}`, `POST /api/prompts/used {"id"}` (le met en tête) ; 404 pour un `id` inconnu ; avec
  `--lan`, `POST /api/login` ; espace privé (`private/`, voir `DECISIONS.md` pour le format) : `POST /api/private/create
  {"code"}` (409 s'il existe déjà), `POST /api/private/unlock {"code"}` (403 après une seconde si le code est faux), qui
  ouvrent une session pour l'appareil (cookie `qwen_private`, HttpOnly, sans durée de vie, fermée par le serveur après
  15 minutes sans requête privée), `POST /api/private/lock`, `POST /api/private/code {"old", "new"}` (nouvelles clés,
  images et prompts privés rechiffrés, toutes les sessions fermées et le cookie de l'appareil effacé ; 500 si le
  rechiffrement échoue, sans perte : le message dit si le code a changé), `POST /api/private/reset {"confirm":
  "SUPPRIMER"}` (efface l'espace et ferme toutes les sessions ; 403 hors du Mac lui-même) ; `/api/status` porte
  `private` : `available` (bibliothèque `cryptography` présente), `exists`, `unlocked` (pour cet appareil, sans
  prolonger la session), `secure` (l'espace peut s'ouvrir par cette adresse) et `local` (le Mac lui-même, seul à pouvoir
  supprimer l'espace sans le code) ; sans `cryptography`, ces routes répondent 503. Toutes les routes de l'espace privé
  sauf `lock` et la génération privée répondent 403 hors du Mac lui-même et de l'adresse HTTPS de « tailscale serve »
  (jugé sur l'adresse source 127.0.0.1 et le nom d'hôte, jamais sur les en-têtes de relais) ; génération privée :
  `"private": true` dans `/api/generate` (403 sans session, 400 si `private` n'est pas un booléen, 503 sans
  `cryptography`), identifiant de 32 caractères hexadécimaux tirés au hasard (comme celui d'un lot privé), absente de
  `queue` hors de l'espace privé (rien
  n'y trahit l'espace privé aux autres appareils), entrée complète dedans (`kind` `private`, `id`, `mode`, `prompt`,
  `lot` avec son `id`) ; `GET /api/job/<id>` porte `private` et, une fois l'image rangée, `item` (son identifiant dans
  l'espace privé) ; `POST /api/job/<id>/forget` l'oublie (l'image reste dans l'espace ; sans cela, le serveur oublie
  une génération privée finie 24 h après sa fin) ; suivi (`GET /api/job/<id>`,
  `…/preview`), annulation, passage en tête et oubli (`POST /api/job/<id>/cancel`, `…/first`, `…/forget`) d'une
  génération privée, et `POST /api/lot/<id>/cancel` et `…/first` d'un lot privé : requête sûre et session exigées, sinon
  404 (« job inconnu », « lot inconnu »), comme un identifiant inconnu, avant tout test d'état ; l'annulation et le
  passage en tête prolongent la session, ni le suivi ni l'oubli ; la fermeture de la page ne l'arrête pas.
  Pile et tirages privés, session exigée (403 sinon), chaque requête prolongeant la session : une génération privée
  terminée arrive dans la pile privée, marquée `"pile": true` dans sa fiche chiffrée (`meta`) ; `GET
  /api/private/pile` (la pile) et `GET /api/private/history` (les tirages privés, fiches sans la marque, dont toutes
  les images privées d'avant la pile ; réglages déchiffrés de chaque image, avec `id`, sans la marque), `POST
  /api/private/keep {"id"}` (Garder : la fiche déchiffrée, sans la marque, rescellée avec la clé publique de l'espace
  et remplacée d'un coup, image, miniature et entrées intactes), `POST /api/private/discard {"id"}` (Jeter : seulement
  une image de la pile ; son dossier est supprimé) : 404 « déjà triée » pour une image qui n'est pas (ou plus) dans la
  pile, le premier geste arrivé l'emporte ; dans l'espace privé, `rev` de `/api/status` est le compteur de la pile et
  des tirages privés (arrivée, Garder, Jeter, Supprimer), jamais visible ailleurs ;
  `GET /api/private/image?id=…[&download=1]`, `GET
  /api/private/thumb?id=…`, `GET /api/private/input?id=…&file=init.png|ref_N.png[&thumb=1][&download=1]`, `POST
  /api/private/delete {"id"}` ; prompts enregistrés de l'espace privé, session exigée (403 sinon) et prolongée, mêmes
  champs, mêmes limites et mêmes réponses que `/api/prompts` : `GET /api/private/prompts` (avec les mêmes `types`),
  `POST /api/private/prompts`, `POST /api/private/prompts/delete`, `POST /api/private/prompts/used` (500 si
  `private/prompts` est illisible, sans l'écraser).
- `POST /api/prompts` refuse (400) un titre ou un texte vide ou qui n'est pas un texte, un titre de plus de 80
  caractères, un texte de plus de 4 000, un `usage` inconnu à la création, et une création au-delà de 500 prompts.
  `tools/saved_prompts.json` est écrit dans un fichier temporaire renommé ensuite : il n'est jamais à moitié écrit. Un
  fichier illisible (modifié à la main) n'est jamais écrasé : les routes répondent 500 tant qu'il n'est pas réparé.
- `POST /api/generate` refuse (code 400, avec un message) une demande dont le prompt n'est pas un texte non vide, dont
  la largeur ou la hauteur n'est pas un entier de 64 à 4096, les étapes un entier de 1 à 200, ou la graine un entier
  (-1 : au hasard), ou `count` qui n'est pas un entier de 1 à 4 ou qui dépasse 1 avec une `campaign`, ou une
  `campaign` hors du mode `edit`, de plus de 10 photos, ou dont une photo n'a pas d'image ou de dimensions valides ;
  les autres champs (`cfg`, `strength`, images, `negative_prompt`…) doivent avoir le bon type. Elle refuse aussi
  (400 « L'incognito n'existe plus : passez par l'espace privé. ») une demande `"incognito": true`, qu'enverrait une
  page d'avant le retrait de l'incognito restée ouverte : rien n'est écrit sur l'ordinateur, pas même au journal du
  serveur (les requêtes `/api/generate` n'y vont jamais) ; le champ `page` d'une
  telle page est ignoré. Une génération qui ne peut pas se préparer (image d'entrée illisible, par exemple) échoue
  seule, avec un message, et la file passe à la suivante.
- Le journal du serveur (`logs/service.log` pour le service Mac) écrit la même ligne pour tout échec, génération
  privée ou non : « [job] échec : génération, sd-cli code N » ou « [job] échec : génération, erreur de préparation » ;
  le détail, qui peut citer le prompt ou un fichier, reste en mémoire pour l'interface (`error` de `/api/job/<id>`).
  « [job] fin de génération incomplète » (image produite, journal des images en échec), « [job] images d'entrée non
  conservées », « [job] erreur du thread de calcul » et « [push] notification du lot impossible » n'ont pas non plus
  de détail. Toute réussite écrit la même ligne, « [job] génération terminée », sans chemin ni durée, et aucune mesure
  de calibration n'y figure, ni son échec (seul `tools/calibrate.py` affiche les siennes) ; seules les requêtes en
  erreur (4xx, 5xx) y sont écrites, d'après leur seul chemin, hors des routes du suivi, de l'espace privé et de
  `/api/generate` (ses refus propres, 403 et 503, ne viennent que de l'espace privé ; ses refus d'accès, 401, 403 et
  415, n'y sont donc pas non plus) : la suite des requêtes réussies (image et miniature lues après une génération
  normale seulement) trahirait sinon les générations privées. Une connexion coupée par l'appareil (page quittée pendant
  un chargement) donne la seule ligne « [ui] connexion interrompue », et un tri (Garder, Jeter) ou une suppression
  réussis n'écrivent rien.
- Pourquoi pas ComfyUI ? ComfyUI repose sur PyTorch, qui n'a pas de backend GPU utilisable sur les Radeon intégrés
  sous Windows (ROCm Windows ne couvre que les cartes RDNA3/RDNA4, DirectML est limité à d'anciennes versions) :
  il tournerait en CPU pur. Si vous avez une carte NVIDIA, les workflows officiels Comfy-Org
  ([texte → image](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_t2i.json),
  [édition](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_image_edit.json))
  avec [ComfyUI-GGUF](https://github.com/leejet/ComfyUI-GGUF) seront plus rapides.

```text
.
├── LICENSE               licence MIT (code du dépôt)
├── setup.py              installation : moteur (Vulkan, CPU, CUDA en option ; Metal sur Mac), modèle, correctif, raccourci
├── requirements.txt      Pillow, NumPy, pywebpush (notifications), cryptography (espace privé), pywin32
├── start.cmd             lancement alternatif (postes sans restriction de scripts)
├── tools/
│   ├── launch.py         serveur local + pilotage de sd-cli
│   ├── estimate.py       modèle de coût et calibration des estimations de durée
│   ├── calibrate.py      générations de calibration (lancées par setup.py)
│   ├── ui/index.html     l'interface
│   ├── ui/manifest.webmanifest, sw.js, icon-*.png   installation sur le téléphone (application)
│   ├── ui/PixelifySans.woff2, OFL.txt   police pixel du nom et des titres, et sa licence (servie sans code d'accès)
│   ├── fix_int8_te.py    correctif de l'encodeur texte int8 (Windows)
│   ├── make_shortcut.py  crée Chambre noire.lnk (Windows) ou Chambre noire.command (Mac)
│   ├── make_service.py   Mac : démarrage automatique de l'interface, accessible depuis le Wi-Fi
│   ├── make_mask.py      génère un masque ou une annotation par script
│   ├── make_test_image.py  génère une image de test (formes et texte) pour essayer l'édition
│   ├── config.json       moteur, modèle et port par défaut (moteur écrit par setup.py sous Windows)
│   ├── config.local.json réglages propres à la machine, lus par-dessus config.json (facultatif, non versionné)
│   ├── calibration.json  mesures de durée de la machine (créé à l'usage, non versionné)
│   ├── access_code.txt   code d'accès des appareils du Wi-Fi (créé par --lan, non versionné)
│   ├── push_vapid.pem, push_subscriptions.json   notifications : clé d'envoi et appareils abonnés (non versionnés)
│   ├── prompt_types.json    prompts types livrés avec l'application (lecture seule)
│   └── saved_prompts.json   prompts enregistrés, communs à tous les appareils (créé à l'usage, non versionné)
└── tests/
    ├── run_tests.py      tests de bout en bout des trois usages (interface lancée, vraies générations)
    ├── bench.py          banc de test du serveur, sans GPU : serveur sur un port libre, dossier temporaire
    ├── fake_sdcli.py     faux moteur du banc
    ├── check.py          tous les contrôles en une commande (compilation, JavaScript, banc, interface)
    ├── rewrap.py         recoupe les lignes trop longues d'un fichier Markdown
    ├── rules.py          règles mécaniques de CODING_STANDARDS.md et index de la carte du code (pour check.py)
    ├── test_*.py         tests du banc
    └── ui/               tests de l'interface dans Chrome sans écran (pilote driver.mjs, tests *.test.mjs)
```

Créés par l'installation et l'usage, ignorés par git : `venv/`, `sdcpp/`, `models/`, `outputs/`, `jobs/`, `logs/`,
`Chambre noire.lnk`, `Chambre noire.command`.

Banc de test du serveur, sans GPU ni modèle : il sert `tools/launch.py` sur un port libre avec un faux moteur, dans
un dossier temporaire (rien n'est écrit dans `outputs\`), et vérifie l'API (génération, annulation, espace privé,
notifications) en quelques secondes :

```bat
venv\Scripts\python.exe -m unittest discover -s tests
```

Sur Mac : `venv/bin/python -m unittest discover -s tests`. Le faux moteur n'a été vérifié que sur Mac.

Tous les contrôles en une commande : `venv/bin/python tests/check.py` compile les fichiers Python, vérifie la syntaxe
du JavaScript de l'interface avec Node.js (`node --check`), refuse une ligne ajoutée de plus de 120 caractères
depuis la séparation d'avec `origin/main`, lance le banc et affiche son résultat (`--no-bench` pour le sauter ;
`--quick` le saute si aucun fichier Python n'a changé depuis cette séparation). Il échoue aussi si un fichier du
dépôt contient un repère propre à une machine (chemin de dossier personnel, adresse IP privée, nom Tailscale) : le
dépôt est public. Un avis, sans échec, signale un changement de code qui touche l'espace privé. Sur
GitHub, la même commande, complète, tourne sur chaque pull request vers `main` et chaque envoi sur `dev`
(`.github/workflows/checks.yml`, sur macOS).

Il vérifie aussi, sur les lignes ajoutées, les règles de `CODING_STANDARDS.md` devenues mécaniques (`tests/rules.py`),
et que chaque nom cité par la carte du code existe encore ; `--map <nom>` imprime la ligne des fonctions de
`tools/launch.py` et `tools/ui/index.html` dont le nom le contient. Les contrôles rapides (compilation, JavaScript,
longueur des lignes, règles) passent d'abord : si l'un échoue, le banc et l'interface ne sont pas lancés. La dernière
ligne de la sortie nomme chaque faute (`fichier:ligne`, test du banc, fichier d'interface) et la sortie complète
va aussi dans un journal, dont le chemin est affiché ; le banc et chaque
fichier d'interface affichent leur durée. `python3 tests/check.py --lines` ne vérifie que la longueur des lignes
ajoutées, en moins d'une seconde ; le hook avant commit du dépôt (`.githooks/pre-commit`, activé par
`python3 tests/check.py --link-venv`) le lance sur ce qui va être enregistré et refuse le commit fautif.
`python3 tests/rewrap.py <fichier>.md` recoupe les lignes trop longues ajoutées à un fichier Markdown (toutes avec
`--all`) sans toucher aux titres, listes, tableaux, blocs de code ni lignes vides.

Tests de l'interface, sur Mac avec Google Chrome et Node.js : `venv/bin/python tests/check.py --ui` (en même temps que
le banc), ou `--ui tests/ui/<fichier>.test.mjs` pour un seul fichier, et `--name <motif>` pour les seuls tests dont le
nom correspond (échec immédiat si aucun ne correspond). Un test bloqué échoue au bout de 3 minutes (20 pour un
fichier), et Chrome et le banc sont arrêtés à la fin de chaque fichier. Les tests ouvrent l'interface servie par le
banc dans un Chrome sans écran, aux dimensions d'un téléphone, et échouent sur toute erreur de la console du
navigateur. Ils couvrent les écrans principaux, le Labo (deux onglets, pastilles, génération d'un autre appareil
ou cachée, rien qui dépasse à la largeur du téléphone), les terminées (cartes, grille d'un lot, échecs, « × » et « Tout
retirer », plafond, message
« Image prête »), « Garder celle-ci » après un rechargement des Tirages, la saisie (unique, dans le Labo, Dessiner,
collage, campagne à partir de 2 images, plusieurs photos d'un coup, vidage après « Générer », saisie propre à chaque
espace), l'en-tête (cadenas, pastille), la file cloisonnée par espace, les prompts enregistrés privés, la reprise d'une
génération, le suivi d'une génération privée devenue inconnue (sans faux « Échec »), le brouillon unique (reprise des
anciens, aucun brouillon privé dans le navigateur, ancien réglage incognito signalé une fois puis oublié) et le pilote
lui-même (recherche de données restées dans la page, fichiers écrits par le banc, délais).

Tests de bout en bout, interface lancée :

```bat
venv\Scripts\python.exe tests\run_tests.py --steps 8
```

Sur Mac : `venv/bin/python tests/run_tests.py --steps 8`.

## Crédits et licences

- **Qwen-Image-2.1** : Alibaba Qwen, [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1),
  sous **Qwen Research License**. Lisez-la avant tout usage : elle encadre notamment l'usage commercial.
- **Quantification GGUF** : abenzerps, branche `base` de
  [son dépôt Hugging Face](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized/tree/base), sous la
  même Qwen Research License ; encodeur int8 (Windows) et VAE issus de
  [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1).
- **Encodeur GGUF (Mac)** : Alibaba Qwen, [Qwen/Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF),
  sous licence Apache 2.0.
- **Moteur** : [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) (licence MIT).
- **Police pixel** : [Pixelify Sans](https://github.com/eifetx/Pixelify-Sans), © 2021 The Pixelify Sans Project
  Authors, sous **SIL Open Font License 1.1** ([tools/ui/OFL.txt](tools/ui/OFL.txt)) ; sous-ensemble latin en woff2
  tiré de Google Fonts, pour le nom de l'application et les titres.

Le code de ce dépôt (interface, lanceur, scripts) est sous **licence MIT**, voir [LICENSE](LICENSE). Les poids du modèle restent soumis à leur
propre licence et sont téléchargés directement depuis leurs dépôts d'origine.
