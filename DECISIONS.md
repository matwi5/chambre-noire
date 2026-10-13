# Décisions de conception

Une entrée par décision, la plus récente en tête. Une décision remplacée garde son entrée, avec le statut
« remplacée le <date> ». Entrées antérieures au 13/10/2026 reconstituées depuis le README, les commentaires du code et
les messages de commit.

## 2026-10-13 · Mode incognito : image gardée en mémoire, remise une seule fois

- **Contexte** : le porteur veut une image téléchargeable mais gardée nulle part sur l'ordinateur, perdue à la
  génération suivante ou au rechargement de l'application, avec tout ce qui s'y rattache (job, aperçus).
- **Décision** : sd-cli ne lit et n'écrit que des fichiers. Le travail se fait donc dans `jobs/incognito_<id>/`,
  supprimé dès la fin du job et au démarrage suivant. Le serveur garde le PNG en mémoire, le remet une fois à la page
  (`/api/job/<id>/result`), puis la page lui fait oublier le job (`/forget`). La page l'affiche depuis une adresse
  `blob:`. Une nouvelle génération purge les jobs incognito terminés, et un rechargement pendant la génération l'arrête
  (`pagehide` avec `keepalive`). Pas de ligne dans le journal, pas de mesure de calibration (elle note la taille et
  l'heure), aucun détail dans `logs/`. Le prompt n'est pas retenu comme brouillon. L'interrupteur, lui, reste actif d'une
  visite à l'autre, pour ne pas repasser en mode normal sans s'en rendre compte. Éditer et Dessiner restent possibles
  sur l'image incognito.
- **Écarté** : disque en mémoire vive (`hdiutil` sur Mac) : propre à macOS et plus complexe, pour un gain faible sur
  un SSD. Garder l'image côté serveur jusqu'à une expiration : elle survivrait au rechargement de la page.
- **Conséquences** : les fichiers touchent brièvement le disque (limite écrite dans le README). Une image qui n'a pas été
  téléchargée est perdue.

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
