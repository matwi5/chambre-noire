# Qwen-Image 2.1 en local, sur PC Windows ou Mac Apple Silicon

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
git clone https://github.com/matwi5/qwen-image-local.git
cd qwen-image-local
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
- crée le raccourci **`Qwen-Image.lnk`** (Windows) ou **`Qwen-Image.command`** (Mac) dans le dossier ;
- lance trois courtes générations pour calibrer les estimations de durée sur votre machine
  (voir [Performances](#performances) ; `--no-calibrate` pour s'en passer).

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

Double-cliquer sur **`Qwen-Image.lnk`** sous Windows (on peut l'épingler à la barre des tâches ou au menu Démarrer),
ou sur **`Qwen-Image.command`** sur Mac (on peut le glisser dans le Dock).

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
`"model": "q8"` dans `tools/config.json`. La pastille d'état en haut à droite indique le modèle utilisé ; un appui ouvre
le panneau **Moteur** (moteur, modèle, calibration des estimations, journal).

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
- **Veille** : sur Mac, l'ordinateur ne se met pas en veille tant que l'interface tourne avec `--lan` (l'écran peut
  s'éteindre).
- **Toujours disponible (Mac)** : pour que l'interface démarre seule à l'ouverture de session, sans fenêtre,
  accessible depuis le Wi-Fi :

```bash
venv/bin/python tools/make_service.py
```

`venv/bin/python tools/make_service.py --remove` retire ce démarrage automatique. Le journal du service est dans
`logs/service.log`. Le raccourci `Qwen-Image.command` ouvre alors simplement l'interface déjà lancée.

## Utilisation

L'interface a quatre onglets, dans la barre du bas : **Créer** (texte → image), **Éditer**, **Dessiner** (dessin guidé)
et **Galerie**. Elle s'adapte au téléphone comme à l'ordinateur, en thème sombre ou clair selon le système.
Sur un écran tactile, elle allège ses effets de verre et d'animation pour rester fluide ; ajouter `?lite=1` ou
`?lite=0` à l'adresse force l'un ou l'autre rendu.

### Réglages communs

Sous le texte, trois pastilles résument le format, la résolution et les étapes ; un appui ouvre le panneau
**Réglages**. Tous les réglages sont à valeurs fixes :

| Réglage | Choix | Effet |
| --- | --- | --- |
| **Format** | 1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16, et « Image » (les proportions de l'image) quand une seule image est chargée | Proportions de l'image produite |
| **Résolution** | Low ≈512 px · Medium ≈768 px · **High ≈1024 px** (par défaut) · XHigh ≈1536 px · Max 2K natif | Nombre de pixels ; chaque option affiche les dimensions exactes |
| **Étapes** | Low 8 · Medium 12 · High 20 · XHigh 30 · **Max 40** (par défaut, réglage officiel du modèle) | Finesse des détails ; chaque option affiche le **temps estimé** |
| **Aperçu toutes les 5 étapes** | interrupteur, activé par défaut | Montre l'image en cours de formation ; coût affiché à côté |

Le bouton **Générer** affiche le temps estimé ; à sa droite, le bouton **Incognito** (icône de chapeau et lunettes)
active le [mode incognito](#mode-incognito) : l'interface passe alors en thème graphite sombre, sans couleurs ni image
en fond, comme la navigation privée des navigateurs. Le navigateur retient les réglages choisis,
le mode incognito et le texte en cours de chaque onglet (sauf en incognito).

Conseil : **Medium + 12 étapes** pour chercher la bonne formulation, puis montez la résolution et les étapes pour la version finale.
Les descriptions en **anglais, longues et précises** donnent les meilleurs résultats.

Pendant la génération, l'image en cours affiche l'étape, le temps restant et un bouton d'annulation ; le bouton
**Générer** se remplit au fil des étapes. La pastille d'état en haut suit aussi la progression, depuis n'importe quel
onglet : un appui ramène à l'image. On peut recharger la page sans rien perdre : elle se rattache à la génération en cours (sauf en incognito).
Chaque image est enregistrée en PNG dans **`outputs\`** ; les boutons **Éditer** et **Dessiner** sous le résultat
le réutilisent comme point de départ.

### Créer (texte → image)

Écrire la description, ajuster les réglages si besoin, appuyer sur **Générer**.

### Éditer

Ajouter 1 à 10 images (elles sont numérotées 1, 2, 3…), puis écrire une **instruction** :

- « Replace the sky with a dramatic orange sunset, keep everything else unchanged »
- « The woman in image 1 wears the jacket from image 2 »

Avec une seule image, le format « Image » est présélectionné pour garder ses proportions.
Les images trop grandes sont réduites automatiquement à 2048 px de côté.

### Dessiner (dessin guidé)

1. Choisir l'image.
2. Peindre en rouge la zone à modifier (taille du pinceau réglable, gomme, bouton pour tout effacer).
3. Choisir le mode :
   - **Masque** : seule la zone peinte est régénérée, tout le reste est conservé au pixel près ;
   - **Annotation** : le trait rouge est montré au modèle, qui s'en sert comme repère (méthode officielle de Qwen,
     pratique pour plusieurs zones à la fois).
4. Écrire une instruction : « Replace the object in the painted area with a small stone fountain ».

Formulez toujours une **instruction** (« Replace … with … »). Une simple description (« a fountain ») pousse souvent
le modèle à redessiner l'original.

### Galerie

L'onglet **Galerie** montre toutes les images de `outputs\`, la plus récente d'abord. Un appui sur une miniature
l'ouvre en plein écran avec ses réglages (date, usage, taille, étapes, modèle, durée, prompt). Glisser sur le côté passe
à l'image voisine (flèches du clavier sur ordinateur), glisser vers le bas ferme, un appui sur l'image masque les
commandes. Actions : **Télécharger**, **Éditer**, **Dessiner**, **Reprendre** (remet le texte de l'image dans l'onglet
correspondant) et **Supprimer** (définitif, après confirmation).

### Mode incognito

Avec le bouton **Incognito**, à droite de **Générer**, l'image produite peut être téléchargée mais n'est gardée nulle part sur
le Mac : ni dans `outputs\`, ni dans la galerie, ni dans le journal des générations, ni dans `logs\`. Elle est perdue
pour de bon dès la génération suivante, quand on la supprime, ou quand la page est rechargée ou fermée (y compris pendant
la génération, qui est alors arrêtée) : pensez à la **télécharger** avant. Le texte tapé n'est pas retenu par le
navigateur, et la génération n'entre pas dans les mesures de calibration. Les boutons **Éditer** et **Dessiner** la
réutilisent comme d'habitude.

Ce que cela garantit, et ses limites :

- sd-cli ne travaille que sur des fichiers : les images d'entrée, les aperçus et le PNG final passent par
  `jobs/incognito_<identifiant>/`, supprimé dès la fin de la génération (et au lancement suivant après un arrêt
  brutal). L'image finale n'existe ensuite que dans la mémoire du serveur, jusqu'à ce que la page la récupère, puis
  dans celle de la page ;
- un fichier supprimé n'est pas effacé physiquement du disque ; sur un SSD, il devient en pratique illisible peu après ;
- le fichier **téléchargé** est enregistré par le navigateur dans ses Téléchargements, comme tout téléchargement.

## Le modèle

Le modèle n'est pas inclus dans ce dépôt : GitHub refuse les fichiers de plus de 100 Mo et le modèle pèse près de 15 Go.
`setup.py` le télécharge depuis Hugging Face et le vérifie.

| Fichier | Rôle | Taille | Source |
| --- | --- | --- | --- |
| `qwen-image-2.1-UC-Q4_K_M.gguf` | Modèle de diffusion, 7 milliards de paramètres, quantifié 4 bits | 4,6 Go | [abenzerps/Qwen-Image-2.1-Uncensored-Quantized](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized) |
| `qwen-image-2.1-UC-Q8_0.gguf` (option `--q8`) | Même modèle quantifié 8 bits, plus fidèle | 7,6 Go | idem |
| `qwen3vl_8b_int8_convrot.safetensors` (Windows) | Encodeur texte et image Qwen3-VL-8B, int8 | 9,35 Go | [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1), dossier `text_encoders` |
| `qwen_image_2.1_vae_bf16.safetensors` | Décodeur d'image (VAE) | 676 Mo | idem, dossier `vae` |
| `Qwen3VL-8B-Instruct-Q8_0.gguf` (Mac) | Même encodeur Qwen3-VL-8B, GGUF quantifié 8 bits | 8,7 Go | [Qwen/Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF) |
| `mmproj-Qwen3VL-8B-Instruct-F16.gguf` (Mac) | Sa tour vision, qui lit les images de référence | 1,16 Go | idem |

**Encodeur sur Mac.** Le GPU d'un Mac (Metal) n'a pas de calcul int8 dans stable-diffusion.cpp : l'encodeur int8 de
Comfy-Org y tournerait sur le processeur, à ≈ 2 min 30 par image de référence en 512×512. Le Mac prend donc la
version GGUF officielle de Qwen, qui tourne sur le GPU : ≈ 3 s pour la même référence, pour une image quasi
identique. Sur une installation Mac antérieure, `setup.py` télécharge ces deux fichiers et signale que les fichiers
`qwen3vl_8b_int8_convrot*.safetensors` (≈ 18,7 Go) ne servent plus et peuvent être supprimés.

**Variante « UC » (Uncensored).** Le modèle de diffusion est la variante non censurée publiée par abenzerps :
elle n'a ni filtre de contenu ni refus de prompt, et produit ce que décrit le prompt, contenus adultes compris.
Ce dépôt Hugging Face s'appelait `abenzerps/Qwen-Image-2.1-GGUF` ; il a été renommé (constaté le 12 octobre 2026) et
garde les quantifications du modèle officiel sur sa branche `base`. Les téléchargements sont épinglés sur un commit précis de chaque dépôt :
un renommage ou une mise à jour ultérieure ne change pas les fichiers installés.

Empreintes SHA256 vérifiées par `setup.py` (identiques à celles des fichiers `SHA256SUMS` et des métadonnées des dépôts) :

```text
e79c8a009f2ecbdb6c70fd663d9aea9ee304a0d91f347e4169a756b8ad141b41  qwen-image-2.1-UC-Q4_K_M.gguf
cde456c72ea3ecebfc1be783300e972711d875e0c5f1bed33d42b66b156affa8  qwen-image-2.1-UC-Q8_0.gguf
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
L'interface applique ces réglages ; les presets Max correspondent exactement aux tailles officielles.

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
Le preset Max (2K, 40 étapes) prend plusieurs heures : l'interface demande confirmation au-delà d'une heure.
Sur une carte NVIDIA avec le moteur CUDA, comptez de l'ordre de 1 à 2 s par étape en 1024×1024 (estimation non mesurée,
RTX 4060/4070) : une image High de 20 étapes en moins d'une minute.

**Estimations de temps calibrées.** Les temps affichés à côté de chaque preset viennent d'un modèle de coût
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
utilisateur (stratégie AppLocker). Utilisez le raccourci `Qwen-Image.lnk`, qui lance directement `python.exe`.
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
pendant la génération. Fermez les applications gourmandes, ou restez en Medium/High.

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

**Mac : en résolution Max avec des références, la mémoire est juste.** Sur 32 Go, une édition 2048×2048 fonctionne :
le moteur libère l'encodeur après usage et décode l'image par tuiles (avertissements « retrying with spatial tiling »
dans `jobs/<identifiant>/sd-cli.log`, sans effet sur le résultat).

**Linux.** L'interface et le lanceur sont en Python pur, mais `setup.py` ne télécharge que les binaires Windows et
macOS. Il faut récupérer la version Linux de stable-diffusion.cpp dans ses
[releases](https://github.com/leejet/stable-diffusion.cpp/releases), la placer dans `sdcpp/vulkan/` et ajouter Linux
aux plateformes connues de `setup.py` et `tools/launch.py`.

## Fonctionnement technique

```text
navigateur ──HTTP──▶ tools/launch.py (127.0.0.1:7860) ──lance──▶ sdcpp/<moteur>/sd-cli ──▶ outputs/*.png
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
- API locale : `POST /api/generate`, `GET /api/job/<id>`, `GET /api/job/<id>/preview`, `POST /api/job/<id>/cancel`,
  `GET /api/status` ; incognito (`"incognito": true` dans `/api/generate`) : `GET /api/job/<id>/result` (image gardée en
  mémoire), `POST /api/job/<id>/forget` (l'oublier, ou arrêter la génération) ; historique : `GET /api/history`, `GET /api/thumb?name=…` (miniatures gardées dans
  `outputs/.thumbs/`), `GET /api/result?name=…&download=1`, `POST /api/delete` ; avec `--lan`, `POST /api/login`.
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
├── requirements.txt      Pillow, NumPy, pywin32
├── start.cmd             lancement alternatif (postes sans restriction de scripts)
├── start-ui-sdcpp.cmd    variante : interface web intégrée de sd-server, sans outil de dessin
├── tools/
│   ├── launch.py         serveur local + pilotage de sd-cli
│   ├── estimate.py       modèle de coût et calibration des estimations de durée
│   ├── calibrate.py      générations de calibration (lancées par setup.py)
│   ├── ui/index.html     l'interface
│   ├── ui/manifest.webmanifest, sw.js, icon-*.png   installation sur le téléphone (application)
│   ├── fix_int8_te.py    correctif de l'encodeur texte int8 (Windows)
│   ├── make_shortcut.py  crée Qwen-Image.lnk (Windows) ou Qwen-Image.command (Mac)
│   ├── make_service.py   Mac : démarrage automatique de l'interface, accessible depuis le Wi-Fi
│   ├── make_mask.py      génère un masque ou une annotation par script
│   ├── make_test_image.py
│   ├── config.json       moteur, modèle et port par défaut (moteur écrit par setup.py sous Windows)
│   ├── calibration.json  mesures de durée de la machine (créé à l'usage, non versionné)
│   └── access_code.txt   code d'accès des appareils du Wi-Fi (créé par --lan, non versionné)
├── tests/run_tests.py    tests de bout en bout des trois usages (interface lancée)
└── workflows/            paramètres de référence des trois usages (JSON)
```

Créés par l'installation et l'usage, ignorés par git : `venv/`, `sdcpp/`, `models/`, `outputs/`, `jobs/`, `logs/`,
`Qwen-Image.lnk`, `Qwen-Image.command`.

Tests de bout en bout, interface lancée :

```bat
venv\Scripts\python.exe tests\run_tests.py --steps 8
```

Sur Mac : `venv/bin/python tests/run_tests.py --steps 8`.

## Crédits et licences

- **Qwen-Image-2.1** : Alibaba Qwen, [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1),
  sous **Qwen Research License**. Lisez-la avant tout usage : elle encadre notamment l'usage commercial.
- **Variante non censurée et quantisation GGUF** : [abenzerps/Qwen-Image-2.1-Uncensored-Quantized](https://huggingface.co/abenzerps/Qwen-Image-2.1-Uncensored-Quantized)
  (ex-Qwen-Image-2.1-GGUF), sous la même Qwen Research License ; encodeur int8 (Windows) et VAE issus de
  [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1).
- **Encodeur GGUF (Mac)** : Alibaba Qwen, [Qwen/Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF),
  sous licence Apache 2.0.
- **Moteur** : [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) (licence MIT).

Le code de ce dépôt (interface, lanceur, scripts) est sous **licence MIT**, voir [LICENSE](LICENSE). Les poids du modèle restent soumis à leur
propre licence et sont téléchargés directement depuis leurs dépôts d'origine.
