# État du projet

## État

Mis à jour le 14/10/2026.

- **Fonctionnel** sur Windows (Vulkan, CPU, CUDA en option ; sd.cpp `master-890`) et sur Mac Apple Silicon (Metal ;
  sd.cpp `master-959`, encodeur GGUF). Modèles Q4_K_M et Q8_0. Trois usages (texte → image, édition, dessin guidé),
  galerie avec visionneuse (zoom au pincement, partage, copie, images d'entrée), estimations calibrées, mode incognito,
  notification de fin de génération (Web Push).
- **Chez le porteur** : service macOS lancé avec `--lan`, utilisé depuis le téléphone par le Wi-Fi et par Tailscale
  (application installée en HTTPS via `tailscale serve`). Modèle Q8_0 par défaut (`tools/config.json`).
- **En cours** : file d'attente, lots (variantes, campagne), prompts enregistrés et espace privé chiffré. Spécification
  prête (`docs/specs/2026-10-14_lots-espace-prive-prompts.md`), liste des prompts types à valider par le porteur ;
  implémentation pas commencée, en cinq étapes dans l'ordre de la spécification.
- **À vérifier par le porteur**, sur le téléphone par l'application installée (testé seulement dans Chrome sur le Mac,
  en vue de téléphone) :
  - télécharger, partager et copier une image, dont une image incognito (adresse `blob:`) ;
  - la notification : autorisation à la première génération, réception application fermée, toucher pour la rouvrir ;
  - la barre d'état qui prend la couleur du haut de l'écran dans la visionneuse (un bug Chromium pourrait l'empêcher).
- **Pistes ouvertes** (aucune demandée) :
  - une exception dans `build_cmd` (prompt non textuel, image de référence illisible) tue le thread `worker()` et bloque
    la file jusqu'au redémarrage (réglé par l'étape 1 de la spécification du 14/10/2026) ;
  - un autre appareil connecté peut suivre les aperçus d'une génération incognito en cours (`current_job` est exposé
    par `/api/status`) (réglé par l'étape 1 de la même spécification) ;
  - annuler une génération déjà terminée la repasse en `cancelled` sans supprimer son image, et la position dans la
    file est figée à la création (trouvés le 14/10/2026 en lisant le code, non reproduits ; réglés par l'étape 1) ;
  - accepter toute adresse IP littérale dans la liste blanche de `Host`, pour qu'un changement d'IP du Mac ne coupe plus
    l'accès par IP (décision au porteur) ;
  - `start-ui-sdcpp.cmd` et `workflows/*.json` sont périmés (à mettre à jour ou à retirer) ; `sd_port` de
    `tools/config.json` n'est lu nulle part ;
  - incognito et notification : si Android a fermé l'application en arrière-plan, toucher « Image incognito prête »
    rouvre une page qui ne se rattache pas au job incognito ; l'image reste en mémoire jusqu'à la génération suivante
    sans pouvoir être affichée. Piste : laisser la page reprendre une fois un job incognito terminé et jamais récupéré
    (option écartée par le porteur le 13/10/2026, à lui reproposer avec cette raison) ;
  - `tests/run_tests.py --only edit` cherche `outputs/test_t2i_512.png`, que plus rien ne produit, et retombe sur
    `tests/test_scene.png` ;
- **Ménage local** (sur le poste, hors dépôt) : la branche `fix/server-host-origin` et les worktrees de
  `.claude/worktrees/` sont des restes de sessions passées, déjà intégrés à `main`. La branche contient des informations
  propres au réseau du porteur : la supprimer plutôt que la pousser.

## Journal

### 2026-10-14

- Cadrage (séance de questions, toutes les réponses validées par le porteur) de quatre fonctions : file d'attente
  visible avec « Générer » toujours actif, lots (variantes 1 à 4 en mode Créer, campagne de 10 photos au plus en mode
  Éditer), prompts enregistrés et prompts types, espace privé chiffré. Pas de calcul simultané : d'après les mesures de
  calibration, ≈ 95 % d'une génération est du calcul GPU (déduit, non mesuré en parallèle). Écrits :
  `docs/specs/2026-10-14_lots-espace-prive-prompts.md`, `GLOSSARY.md` (nouveau, vocabulaire de l'application) et deux
  entrées de `DECISIONS.md`. Le banc à faux moteur deviendra un banc permanent dans `tests/` (accord du porteur).

### 2026-10-13

- Annulation : le dossier de travail (images d'entrée, aperçus, journal du moteur) et une image finale déjà écrite sont
  supprimés, que la génération soit en cours ou en file d'attente. Banc avec un faux moteur : 9 contrôles, 4 passages
  (dont annulation juste après l'écriture de l'image, et génération menée au bout qui garde tout). Service relancé.
- Notification de fin de génération (Web Push, `pywebpush` ajouté à `requirements.txt` et installé dans le `venv` du
  Mac). Vérifié : banc serveur (17 contrôles : message déchiffré, signature VAPID, aucun prompt, incognito, échec,
  appareil désabonné retiré), puis vraie notification envoyée par Google à un Chrome de test en arrière-plan et affichée
  par le service worker. Service relancé. À vérifier sur le téléphone (autorisation à la première génération).
  Remise des notifications gardée 24 h si le téléphone est hors ligne ; interrupteur masqué si le serveur n'a pas
  `pywebpush`.
- Visionneuse sur le téléphone (dimensions du porteur, 367×760 à 2,5) : l'image dépassait sous le panneau des boutons
  (une grille CSS ne bornait pas `max-height:100%`, conteneur passé en flex) ; prompt retiré (Reprendre gardé) ; zoom
  au pincement temporaire, au-dessus de tout ; fenêtre des images d'entrée opaque ; couleur de la barre d'état calculée
  depuis le haut de l'écran. 21 contrôles ; à vérifier sur le téléphone : que Chrome suive bien `theme-color` changé en
  cours de route.
- Interface : glisser entre les onglets ; image zoomée tenue sous la barre du haut et le panneau ; Partager et Copier
  (visionneuse et résultat, masqués hors HTTPS) ; images d'entrée conservées dans `outputs/.inputs/` et visibles en
  grand depuis la visionneuse (glisser, Télécharger, Éditer, Dessiner) ; bouton incognito inactif pendant une
  génération. Génération incognito perdue à la fermeture : comportement confirmé par le porteur. 23 contrôles dans
  Chrome en mode tactile et contrôle de la route `/api/input` (noms piégés refusés) ; service relancé.
- Galerie : les miniatures manquaient parfois au premier affichage. Cause : la file d'attente des connexions du serveur
  (5 par défaut dans Python) débordait quand la galerie demandait toutes les miniatures pendant leur fabrication, d'où
  des connexions refusées (erreur relayée par Tailscale, absente de `logs/`). File portée à 128 (`Server`), miniatures
  écrites puis renommées, seconde tentative côté interface. Banc : 2 à 7 miniatures cassées par essai avant, 0 sur
  9 essais (jusqu'à 32 demandes simultanées) après. Zone de génération masquée dans la galerie ; visionneuse : zoom
  (pincer, double appui, molette), Télécharger en haut, quatre actions plus aérées en bas. 13 contrôles dans Chrome
  en mode tactile ; service relancé.
- Interface : niveaux de résolution renommés d'après le format vidéo au nombre de pixels le plus proche (360p, 540p,
  720p, 1080p, 1440p) ; la pastille sous le texte affiche ce libellé. Dans les Réglages, formats et résolutions
  n'affichent plus que leur libellé (ni « Carré », « Paysage »…, ni dimensions) ; les dimensions exactes restent en bas
  du panneau et au survol de la pastille.
- Interface : réglages par défaut 720p (≈1024 px), 40 étapes et aperçus toutes les 5 étapes ; l'incognito passe du
  panneau Réglages à un bouton à droite de Générer. Les réglages retenus avant ce changement sont remis une fois à ces
  défauts (format et incognito gardés). Vérifié par 11 contrôles dans Chrome sans écran.
- Incognito : l'interface passe en thème graphite sombre (couleur de la barre du navigateur comprise) tant que le mode
  est actif ; plus de message à l'activation. Vérifié par captures dans Chrome sans écran.
- Mise en place de la documentation de session : `CLAUDE.md`, `BRIEF.md`, `DECISIONS.md` et ce fichier, reconstitués
  depuis le README, le code et l'historique git.
- Mode incognito (`d5a745d`) : image gardée en mémoire et remise une fois, perdue à la génération suivante ou au
  rechargement. Vérifié par un banc avec un faux sd-cli et par 17 contrôles dans Chrome sans écran ; le service a été
  relancé. Poussé sur `main`.
- Vérification de ce qui est publié (le dépôt est public) : aucun secret ni donnée personnelle dans les fichiers suivis
  ni dans l'historique de `main`.
- Plus tôt dans la journée (commits `64c76b6` à `2e99704`) : prise en charge du Mac (Metal, encodeur GGUF, sd.cpp
  `master-959`), estimations calibrées sur la machine, accès depuis le téléphone (code d'accès, service macOS, galerie),
  refonte de l'interface (verre, barre d'onglets, panneau de réglages, visionneuse), correction du rebinding DNS et des
  requêtes forgées (plan dans `travail/tasks/2026-10-13_securite-serveur.md`), Tailscale et installation comme
  application, Q8_0 par défaut, allègement des effets sur écran tactile.

### 2026-09-23

- Première version : interface, lanceur et installation pour Windows (Vulkan), licence MIT, moteur CUDA en option et
  premières estimations de durée calibrées.
