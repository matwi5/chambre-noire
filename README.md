# Qwen-Image 2.1 en local sur un PC Windows sans carte graphique

Une interface web locale pour générer et modifier des images avec **[Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1)**,
pensée pour les PC portables ordinaires : processeur graphique intégré (AMD, Intel), pas de carte NVIDIA,
pas de droits administrateur. Tout tourne sur la machine, rien n'est envoyé sur Internet.

Trois usages, une sortie PNG :

- **Texte → image** : décrire une image, la générer.
- **Édition** : 1 à 10 images de référence + une instruction (« remplace le ciel par un coucher de soleil »,
  « mets le chapeau de l'image 2 sur la personne de l'image 1 »).
- **Dessin guidé** : peindre au pinceau la zone à modifier directement sur l'image, puis décrire ce qu'on veut à la place.

Le moteur est [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) avec son backend **Vulkan**,
qui fonctionne sur quasiment tous les GPU intégrés récents avec le pilote graphique déjà installé.

---

## Sommaire

1. [Prérequis](#prérequis)
2. [Installation](#installation)
3. [Lancement](#lancement)
4. [Utilisation](#utilisation)
5. [Le modèle](#le-modèle)
6. [Performances](#performances)
7. [Dépannage](#dépannage)
8. [Fonctionnement technique](#fonctionnement-technique)
9. [Crédits et licences](#crédits-et-licences)

---

## Prérequis

| | Minimum | Recommandé |
| --- | --- | --- |
| Système | Windows 10 ou 11, 64 bits | Windows 11 |
| Mémoire vive | 24 Go | 32 Go |
| Disque libre | 35 Go | 50 Go |
| GPU | Tout GPU compatible Vulkan 1.3 (Radeon intégré, Intel Iris Xe/Arc, NVIDIA, AMD) | GPU dédié |
| Python | 3.10 ou plus récent | 3.12 à 3.14 |
| Connexion | ≈ 15 Go à télécharger une seule fois | |

Aucun droit administrateur n'est nécessaire : tout s'installe dans le dossier du projet.

Python : l'installer depuis [python.org](https://www.python.org/downloads/windows/) (cocher « Add python.exe to PATH »)
ou depuis le Microsoft Store. Vérifier dans un terminal :

```bat
python --version
```

## Installation

**1. Récupérer le projet**

```bat
git clone https://github.com/matwi5/qwen-image-local.git
cd qwen-image-local
```

Sans git : bouton **Code → Download ZIP** sur GitHub, puis décompresser le dossier où vous voulez
(évitez les dossiers synchronisés OneDrive, le modèle est volumineux).

**2. Créer l'environnement Python isolé et installer les trois dépendances**

```bat
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

**3. Télécharger le moteur et le modèle**

```bat
venv\Scripts\python.exe setup.py
```

Ce script, à lancer une seule fois :

- télécharge stable-diffusion.cpp (versions Vulkan et CPU, version épinglée et vérifiée par SHA256) dans `sdcpp\` ;
- télécharge les trois fichiers du modèle depuis Hugging Face dans `models\` (≈ 14,6 Go) et vérifie chacun contre
  les empreintes SHA256 publiées par le dépôt ;
- prépare l'encodeur de texte pour stable-diffusion.cpp (voir [Le modèle](#le-modèle)) ;
- crée le raccourci **`Qwen-Image.lnk`** dans le dossier.

Les téléchargements reprennent là où ils s'étaient arrêtés si la connexion coupe : il suffit de relancer la commande.
Pour vérifier une installation sans rien télécharger : `venv\Scripts\python.exe setup.py --check`.

## Lancement

Double-cliquer sur **`Qwen-Image.lnk`** (on peut l'épingler à la barre des tâches ou au menu Démarrer).

Une fenêtre noire s'ouvre : c'est le moteur, **laissez-la ouverte**. Le navigateur s'ouvre ensuite sur
**http://127.0.0.1:7860/**. Pour arrêter, fermez la fenêtre noire.

Équivalent en ligne de commande, depuis le dossier du projet :

```bat
venv\Scripts\python.exe tools\launch.py
```

Options : `--port 7860` (changer de port), `--backend cpu` (sans GPU, beaucoup plus lent), `--no-browser`.

L'interface n'écoute que sur `127.0.0.1` : elle n'est pas accessible depuis le réseau.

## Utilisation

### Réglages communs

Tous les réglages sont des listes à valeurs fixes :

| Réglage | Choix | Effet |
| --- | --- | --- |
| **Format** | 1:1, 4:3, 3:4, 3:2, 2:3, 16:9, 9:16, et « ★ Ratio de l'image » quand une seule image est chargée | Proportions de l'image produite |
| **Résolution** | Low ≈512 px · Medium ≈768 px · High ≈1024 px · XHigh ≈1536 px · Max 2K natif | Nombre de pixels ; chaque option affiche les dimensions exactes |
| **Étapes** | Low 8 · Medium 12 · High 20 · XHigh 30 · Max 40 | Finesse des détails ; chaque option affiche le **temps estimé** |
| **Aperçu toutes les 5 étapes** | case à cocher | Montre l'image en cours de formation ; coût affiché à côté |

Conseil : **Medium + 12 étapes** pour chercher la bonne formulation, puis montez la résolution et les étapes pour la version finale.
Les descriptions en **anglais, longues et précises** donnent les meilleurs résultats.

Pendant la génération, le panneau de droite affiche l'étape en cours, le temps restant et un bouton **Annuler**.
On peut recharger la page sans rien perdre : elle se rattache à la génération en cours.
Chaque image est enregistrée en PNG dans **`outputs\`** ; les boutons « → Édition » et « → Dessin guidé »
réutilisent le résultat comme point de départ.

### Texte → image

Écrire la description, choisir format, résolution et étapes, cliquer sur **Générer**.

### Édition

Déposer 1 à 10 images (elles sont numérotées 1, 2, 3…), puis écrire une **instruction** :

- « Replace the sky with a dramatic orange sunset, keep everything else unchanged »
- « The woman in image 1 wears the jacket from image 2 »

Avec une seule image, le format « ★ Ratio de l'image » est présélectionné pour garder ses proportions.
Les images trop grandes sont réduites automatiquement à 2048 px de côté.

### Dessin guidé

1. Déposer l'image.
2. Peindre en rouge la zone à modifier (taille du pinceau réglable, gomme, bouton Effacer).
3. Choisir le mode :
   - **Masque** : seule la zone peinte est régénérée, tout le reste est conservé au pixel près ;
   - **Annotation** : le trait rouge est montré au modèle, qui s'en sert comme repère (méthode officielle de Qwen,
     pratique pour plusieurs zones à la fois).
4. Écrire une instruction : « Replace the object in the painted area with a small stone fountain ».

Formulez toujours une **instruction** (« Replace … with … »). Une simple description (« a fountain ») pousse souvent
le modèle à redessiner l'original.

## Le modèle

Le modèle n'est pas inclus dans ce dépôt : GitHub refuse les fichiers de plus de 100 Mo et le modèle pèse près de 15 Go.
`setup.py` le télécharge depuis Hugging Face et le vérifie.

| Fichier | Rôle | Taille | Source |
| --- | --- | --- | --- |
| `qwen-image-2.1-Q4_K_M.gguf` | Modèle de diffusion, 7 milliards de paramètres, quantifié 4 bits | 4,6 Go | [abenzerps/Qwen-Image-2.1-GGUF](https://huggingface.co/abenzerps/Qwen-Image-2.1-GGUF) |
| `qwen3vl_8b_int8_convrot.safetensors` | Encodeur texte et image Qwen3-VL-8B, int8 | 9,35 Go | idem, dossier `text_encoders` |
| `qwen_image_2.1_vae_bf16.safetensors` | Décodeur d'image (VAE) | 676 Mo | idem, dossier `vae` |

Empreintes SHA256 vérifiées par `setup.py` (issues du fichier `SHA256SUMS` du dépôt) :

```text
833439e91bc1152d28f37aa198c7f6f4218b7de95754c2f7a318a2422ab4b2f8  qwen-image-2.1-Q4_K_M.gguf
8bfd0f6e12abf2d2d697ecc888e5e90b0d6741d6708f05799f53afa560452e8f  text_encoders/qwen3vl_8b_int8_convrot.safetensors
bb21f7473051e1ac368515dd3f2e15cd44d7a11748ee8823e1ddca3e4876b7c9  vae/qwen_image_2.1_vae_bf16.safetensors
```

**Correctif de l'encodeur.** Dans ce fichier int8 (format ComfyUI), la table d'embeddings est elle aussi quantifiée,
ce que stable-diffusion.cpp (version `master-890-74988b2`) interprète mal : il plante au chargement.
`tools/fix_int8_te.py` en crée une copie `qwen3vl_8b_int8_convrot_embfix.safetensors` où seule cette table repasse
en bf16 (dé-rotation Hadamard comprise) ; toutes les autres couches restent en int8. Même taille, même qualité.
Une version future de stable-diffusion.cpp rendra probablement ce correctif inutile.

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

Ordres de grandeur sur cette machine : ≈ 16 à 20 s par étape en 512×512, ≈ 1,5 min par étape estimée en 1024×1024 ;
l'édition coûte environ le double du texte → image (l'image de référence double la séquence à traiter).
Le preset Max (2K, 40 étapes) prend plusieurs heures : l'interface demande confirmation au-delà d'une heure.
Les estimations affichées dans l'interface sont calibrées sur cette machine ; un GPU plus récent ira nettement plus vite.

Pour gagner du temps sans perte de qualité : branchez le portable sur secteur et choisissez le mode d'alimentation
« Performances optimales » dans les paramètres Windows.

## Dépannage

**Double-cliquer sur un fichier `.cmd` ne fait rien.** Certaines entreprises bloquent les scripts dans les dossiers
utilisateur (stratégie AppLocker). Utilisez le raccourci `Qwen-Image.lnk`, qui lance directement `python.exe`.
S'il manque : `venv\Scripts\python.exe tools\make_shortcut.py`.

**L'état en haut à droite indique « fichiers manquants ».** L'installation est incomplète :
`venv\Scripts\python.exe setup.py --check` puis `venv\Scripts\python.exe setup.py`.

**La génération échoue immédiatement.** Le détail est dans `jobs\<identifiant>\sd-cli.log`. Vérifiez que Vulkan
fonctionne :

```bat
sdcpp\vulkan\sd-cli.exe --list-devices
```

La liste doit contenir une ligne `Vulkan0`. Sinon, mettez à jour le pilote graphique, ou lancez l'interface avec
`--backend cpu`.

**Le PC rame ou la génération s'arrête pendant les grandes résolutions.** Le modèle occupe environ 14 Go de mémoire
pendant la génération. Fermez les applications gourmandes, ou restez en Medium/High.

**L'antivirus bloque `sd-cli.exe`.** Ce sont les binaires officiels de stable-diffusion.cpp, vérifiés par SHA256 à
l'installation ; demandez une exception à votre service informatique si nécessaire.

**Autres systèmes (Linux, macOS).** L'interface et le lanceur sont en Python pur, mais `setup.py` télécharge des binaires
Windows. Il faut récupérer la version Linux ou macOS de stable-diffusion.cpp dans ses
[releases](https://github.com/leejet/stable-diffusion.cpp/releases), la placer dans `sdcpp/vulkan/` en renommant
`sd-cli` si besoin, et adapter le nom de l'exécutable dans `tools/launch.py`.

## Fonctionnement technique

```text
navigateur ──HTTP──▶ tools/launch.py (127.0.0.1:7860) ──lance──▶ sdcpp/vulkan/sd-cli.exe ──▶ outputs/*.png
   tools/ui/index.html        file d'attente, suivi des étapes,         Vulkan : diffusion + VAE
                              aperçus, annulation                       CPU    : encodeur texte
```

- Chaque génération lance `sd-cli.exe` avec `--mmap` : après la première fois, le modèle se recharge en moins d'une
  seconde grâce au cache disque de Windows.
- Répartition : `--backend diffusion=vulkan0,vae=vulkan0,te=cpu --offload-to-cpu`. L'encodeur int8 n'a pas de noyau
  Vulkan dans stable-diffusion.cpp, il tourne donc sur le processeur.
- API locale : `POST /api/generate`, `GET /api/job/<id>`, `GET /api/job/<id>/preview`, `POST /api/job/<id>/cancel`,
  `GET /api/status`.
- Pourquoi pas ComfyUI ? ComfyUI repose sur PyTorch, qui n'a pas de backend GPU utilisable sur les Radeon intégrés
  sous Windows (ROCm Windows ne couvre que les cartes RDNA3/RDNA4, DirectML est limité à d'anciennes versions) :
  il tournerait en CPU pur. Si vous avez une carte NVIDIA, les workflows officiels Comfy-Org
  ([texte → image](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_t2i.json),
  [édition](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_image_edit.json))
  avec [ComfyUI-GGUF](https://github.com/leejet/ComfyUI-GGUF) seront plus rapides.

```text
.
├── setup.py              installation : moteur, modèle, correctif, raccourci
├── requirements.txt      Pillow, NumPy, pywin32
├── start.cmd             lancement alternatif (postes sans restriction de scripts)
├── start-ui-sdcpp.cmd    variante : interface web intégrée de sd-server, sans outil de dessin
├── tools/
│   ├── launch.py         serveur local + pilotage de sd-cli
│   ├── ui/index.html     l'interface
│   ├── fix_int8_te.py    correctif de l'encodeur texte
│   ├── make_shortcut.py  crée Qwen-Image.lnk
│   ├── make_mask.py      génère un masque ou une annotation par script
│   ├── make_test_image.py
│   └── config.json       backend et port par défaut
├── tests/run_tests.py    tests de bout en bout des trois usages (interface lancée)
└── workflows/            paramètres de référence des trois usages (JSON)
```

Créés par l'installation et l'usage, ignorés par git : `venv/`, `sdcpp/`, `models/`, `outputs/`, `jobs/`, `logs/`.

Tests de bout en bout, interface lancée :

```bat
venv\Scripts\python.exe tests\run_tests.py --steps 8
```

## Crédits et licences

- **Qwen-Image-2.1** : Alibaba Qwen, [Qwen/Qwen-Image-2.1](https://huggingface.co/Qwen/Qwen-Image-2.1),
  sous **Qwen Research License**. Lisez-la avant tout usage : elle encadre notamment l'usage commercial.
- **Quantisation GGUF** : [abenzerps/Qwen-Image-2.1-GGUF](https://huggingface.co/abenzerps/Qwen-Image-2.1-GGUF) ;
  encodeur et VAE issus de [Comfy-Org/Qwen-Image-2.1](https://huggingface.co/Comfy-Org/Qwen-Image-2.1).
- **Moteur** : [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp) (licence MIT).

Ce dépôt ne contient que le code de l'interface, du lanceur et des scripts ; les poids du modèle restent soumis à leur
propre licence et sont téléchargés directement depuis leurs dépôts d'origine.
