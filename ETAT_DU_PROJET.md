# État du projet

## État

Mis à jour le 15/10/2026.

- **Fonctionnel** sur Windows (Vulkan, CPU, CUDA en option ; sd.cpp `master-890`) et sur Mac Apple Silicon (Metal ;
  sd.cpp `master-959`, encodeur GGUF). Modèles Q4_K_M et Q8_0. Trois usages (texte → image, édition, dessin guidé),
  galerie avec visionneuse (zoom au pincement, partage, copie, images d'entrée), estimations calibrées, mode incognito,
  notification de fin de génération (Web Push), file d'attente visible (« Générer » toujours actif), variantes (mode
  Créer) et campagnes (mode Éditer) avec lots dans la galerie, prompts enregistrés et prompts types, espace privé
  chiffré (entrée discrète par le cadenas de la Galerie). Banc de test permanent sans GPU :
  `venv/bin/python -m unittest discover -s tests` (129 tests, ≈ 1 min).
- **Chez le porteur** : service macOS lancé avec `--lan`, utilisé depuis le téléphone par le Wi-Fi et par Tailscale
  (application installée en HTTPS via `tailscale serve`). Modèle Q8_0 par défaut (`tools/config.json`).
- **En cours** : file d'attente, lots (variantes, campagne), prompts enregistrés et espace privé chiffré. Spécification
  prête (`docs/specs/2026-10-14_lots-espace-prive-prompts.md`), découpée en 13 tickets Asana (liste et ordre dans
  `travail/tasks/2026-10-14_lots-espace-prive-prompts.md`) ; liste des prompts types validée par le porteur. Groupes A (banc, robustesse, file visible, incognito dans la file) et
  B (variantes, lots dans la galerie, campagne), C (prompts) et D (durcissement de l'incognito, espace privé) faits,
  revus et fusionnés, puis E (durcissement de l'espace privé) : les 15 tickets sont faits. Restent les essais sur le
  téléphone et une vraie génération avec le nouveau code. L'espace privé ne s'ouvre plus que par l'adresse HTTPS
  (`tailscale serve`) ou sur le Mac.
- **À vérifier par le porteur**, sur le téléphone par l'application installée (testé seulement dans Chrome sur le Mac,
  en vue de téléphone) :
  - télécharger, partager et copier une image, dont une image incognito (adresse `blob:`) ;
  - la notification : autorisation à la première génération, réception application fermée, toucher pour la rouvrir ;
  - la barre d'état qui prend la couleur du haut de l'écran dans la visionneuse (un bug Chromium pourrait l'empêcher) ;
  - la file d'attente (pastille « +N en attente », feuille de la file, rangée de vignettes sous l'image) et l'incognito
    dans la file (deux images incognito gardées jusqu'à être vues puis quittées) ;
  - les variantes (grille, « Garder celle-ci »), les lots dans la galerie (badge, « Voir le lot », « Tout
    télécharger », qui peut demander d'autoriser plusieurs téléchargements) et la campagne ;
  - la feuille des prompts (bouton « Prompts » sous le champ de texte) ;
  - l'espace privé : entrée par le cadenas de la Galerie, thème, sortie, verrouillage à la fermeture (inconstant dans
    Chrome sans écran ; l'expiration après 15 min reste le filet), cookie `SameSite=Strict` avec l'application
    installée, « Rendre privée ».
- **Pistes ouvertes** (aucune demandée) :
  - `sd-cli.log` reste ouvert si la boucle de lecture de `run_job` lève une exception ; `queue_position` trie tout
    `S.jobs`, qui ne fait que grossir, à chaque lecture (trouvés par la revue de groupe A) ;
  - course entre la route d'annulation et `worker()` sur le statut d'une génération (sans verrou), et `open(...).read()`
    sans fermeture dans `launch.py` et `estimate.py` (avertissements masqués dans le banc) (trouvés le 14/10/2026) ;
  - une génération reprise après un rechargement n'a ni dimensions ni coefficients propres : le cadre ne prend sa forme
    qu'à la fin ;
  - le faux moteur du banc n'a pas été essayé sous Windows (lanceur `sd-cli.cmd`) ;
  - la galerie trie par `st_mtime` en secondes entières : les images d'un même lot peuvent ressortir dans le désordre ;
  - le résultat d'une génération incognito reste servi en `http://` sur le Wi-Fi (laissé tel quel par le porteur le
    15/10/2026 : l'incognito vise le disque, pas le réseau) ; `/api/status` dit à tout appareil connecté si un espace
    privé existe (`private.exists`, nécessaire pour proposer la création ou le code), ce qui révèle son existence ;
  - `do_POST` lit `Content-Length` sans plafond (une campagne de 10 photos en data URL pèse lourd) ;
  - `push_subscriptions()` écrit `tools/push_subscriptions.json` en place, de façon non atomique ; les messages 500
    des routes de prompts citent le texte de l'exception (chemin local possible, visible des seuls appareils admis) ;
  - accepter toute adresse IP littérale dans la liste blanche de `Host`, pour qu'un changement d'IP du Mac ne coupe plus
    l'accès par IP (décision au porteur) ;
  - `start-ui-sdcpp.cmd` et `workflows/*.json` sont périmés (à mettre à jour ou à retirer) ; `sd_port` de
    `tools/config.json` n'est lu nulle part ;
  - incognito et notification : si Android a fermé l'application en arrière-plan, toucher « Image incognito prête »
    rouvre une page qui ne se rattache pas au job incognito ; l'image reste en mémoire sans pouvoir être affichée, et
    depuis le 14/10/2026 (plus de purge à chaque nouvelle demande) jusqu'au redémarrage du serveur ; une expiration à
    24 h est prévue par le ticket « Durcir l'incognito et limiter la reprise à l'appareil ». Piste : laisser la page reprendre une fois un job incognito terminé et jamais récupéré
    (option écartée par le porteur le 13/10/2026, à lui reproposer avec cette raison) ;
  - `tests/run_tests.py --only edit` cherche `outputs/test_t2i_512.png`, que plus rien ne produit, et retombe sur
    `tests/test_scene.png` ;
- **Ménage local** (sur le poste, hors dépôt) : la branche `fix/server-host-origin` et les worktrees de
  `.claude/worktrees/` sont des restes de sessions passées, déjà intégrés à `main`. La branche contient des informations
  propres au réseau du porteur : la supprimer plutôt que la pousser.

## Journal

### 2026-10-15

- Version 0.2.0 (`a895086`, tag `v0.2.0`) : `CHANGELOG.md` créé, la version du 23/09/2026 comptée comme 0.1.0.
  Rapport du parcours validé par le porteur.
- Une génération privée apparaît dans la file des autres appareils exactement comme une génération incognito, et les
  messages d'échec de `logs/` disent « incognito » (`c6e968a`, ticket Asana `1219532320923400`, décision du porteur).
  CLAUDE.md complété avec la règle `_secure`, le rechiffrement et les trois origines du banc (`54a00d0`, validé par le
  porteur). 129 tests au vert, service relancé.
- Groupe E fait dans une session à part (worktree) et fusionné (`e30c75b` à `8178d8d`) : notification neutre pour le
  privé, « Sortir » vide l'écran, suppression de l'espace sans code seulement depuis le Mac, espace privé seulement en
  HTTPS ou sur le Mac (`_secure` : adresse source locale et nom d'hôte local ou HTTPS de `tailscale serve`, jamais les
  en-têtes de relais), nouvelle paire de clés et rechiffrement au changement de code par `private/.rekey/` et bascule
  atomique de `space.json` (pannes simulées à 7 étapes sans perte). Revue de groupe : 9 constats, 7 corrigés ; revue
  de sécurité : aucune faille. 129 tests au vert après fusion, service relancé (nom HTTPS repéré au démarrage).
### 2026-10-14

- Porteur, sur les notes de la revue de sécurité du groupe D : notification neutre pour le privé, onglets privés
  vidés à « Sortir », suppression de l'espace sans code seulement depuis le Mac, espace privé ouvert seulement en HTTPS
  ou sur le Mac, nouvelle paire de clés et rechiffrement au changement de code. Regroupé dans le ticket Asana
  `1219520417161822` et dans la spécification (section 5).
- Groupe D fait dans une session à part (worktree) et fusionné : durcissement de l'incognito (`df6896a` :
  identifiants de 128 bits, image non récupérée oubliée après 24 h, reprise limitée aux générations de l'appareil,
  jeton par page), espace privé (`429096e`), générations et galerie privées (`6421746`), lots privés et héritage
  (`f91e980`), « Rendre privée » (`9f4673f`), revue de groupe (`4bdd66f`, 9 constats, 8 corrigés dont un échec de
  « Rendre privée » qui pouvait perdre l'image). Revue de sécurité : aucune faille au seuil, quatre notes de
  conception soumises au porteur. Le porteur a revu l'interface en cours de route : espace discret, on y entre par le
  cadenas de la Galerie et on en sort par « Sortir » (DECISIONS.md) ; les trois tickets Asana concernés sont mis à
  jour. 117 tests au vert après fusion, service relancé, `jobs/` exclu de Time Machine (vérifié par `tmutil`).
- Groupe C fait dans une session à part (worktree), avec la nouvelle démarche par ticket (`/mattpocock-skills:tdd`,
  contrôles, `/mattpocock-skills:code-review`) : prompts enregistrés (`8e33bf1`, `tools/saved_prompts.json` non suivi,
  en 0o600) et prompts types (`cf8a254`, `tools/prompt_types.json`, les 11 validés, comparés mot pour mot à la
  spec). Revue de groupe (`/code-review --fix`) : 9 constats, 6 corrigés (`52466e1`). Revue de sécurité : aucune
  faille. Fusionné, 75 tests au vert, service relancé (11 prompts types servis). Choix de la session : titre de 80
  caractères, texte de 4 000, 500 prompts au plus ; choisir un prompt en incognito ne met pas à jour sa dernière
  utilisation (validé par le porteur) ; Dupliquer crée la copie sans ouvrir l'éditeur ; le filtre par usage
  s'applique aussi aux prompts types.
- Revue de groupe B (`/code-review --fix` puis `/security-review`, lancées par la session du groupe) : 4 corrections
  (`f1a478f`) : « Garder celle-ci » supprimait aussi l'image gardée quand la galerie avait été rechargée pendant que la
  visionneuse était ouverte (choix par nom de fichier désormais), la limite de suivi de la page épargne le lot affiché,
  limite des 10 références dans `MAX_REFS`, corps de la notification d'une campagne (« Campagne de N photos
  terminée »). Aucune faille de sécurité. Fusionné, 60 tests au vert, service relancé. Laissé : la page redessine N
  fois au lancement d'un lot (coût sans bug).
- Revue de groupe A (`/code-review --fix` puis `/security-review`, lancées par la session du groupe) : 8 constats,
  3 corrigés (`c934b9f` : génération annulée pendant la préparation arrêtée aussitôt, génération incognito en échec
  ou annulée oubliée par le serveur, lecture des dimensions unifiée), aucune faille de sécurité. Fusionné, 59 tests au
  vert, service relancé. Décisions du porteur sur les constats restants, regroupées dans un nouveau ticket Asana
  (`1219503935811144`) : expiration à 24 h d'une image incognito jamais récupérée, reprise après rechargement limitée
  aux générations de l'appareil, identifiant long pour l'incognito et le privé, jeton par page dans la file. Laissés
  en pistes : `sd-cli.log` resté ouvert si la lecture lève une exception, tri de `S.jobs` à chaque lecture.
- Porteur : la notification d'un lot en partie annulé garde son texte (« N images prêtes ») ; un ticket coché garde
  la ligne « Statut : fait » (écrit dans `docs/agents/triage-labels.md`).
- Groupe B fait dans une session à part (worktree), fusionné dans `main` (`abbd036`) et service relancé : variantes
  en mode Créer (`65b9cac`), lots dans la galerie (`ddbf2b5`), campagne en mode Éditer (`8715316`). 58 tests au vert
  après fusion, `py_compile` et `node --check` propres, contrôles dans Chrome sans écran en vue de téléphone.
- Liste des prompts types validée par le porteur (tâche Asana cochée) ; le ticket des prompts types est débloqué.
- Groupe A fait dans une session à part (worktree), fusionné dans `main` et service relancé : banc de test permanent
  à faux moteur (`5072ad5`), une erreur de préparation n'arrête plus la file et `/api/generate` valide la demande
  (`cf4f825`), file d'attente visible avec « Générer » toujours actif (`b9d58ca`), incognito dans la file (`db6342d`).
  36 tests au vert (relancés après fusion), `py_compile` et `node --check` propres, contrôles dans Chrome sans écran en
  vue de téléphone. Choix de la session : bornes de validation (64 à 4096 px, 1 à 200 étapes), estimation de chaque
  entrée de la file, incognito compris ; la zone de résultat garde l'image finie et la suite se suit dans une rangée
  de vignettes. Les 13 tickets Asana avaient été créés par erreur aussi dans la section « Orange · Cockpit EAS » (paramètre
  `default_project` avec `parent`) : retirés du projet avec l'accord du porteur, ils restent sous-tâches de la tâche
  mère.
- Découpage du chantier en 13 tickets Asana (sous-tâches de la tâche mère de Claude), chacun avec sa ligne
  « Bloqué par », et une tâche assignée au porteur pour valider la liste des prompts types.
- Suivi des tâches passé sur Asana (décision du porteur, revient sur le refus du 13/10/2026) : section « Qwen-Image
  local » et tâche mère de Claude créées dans le Hub. Configuration des skills mattpocock dans `docs/agents/`
  (tickets Asana, rôles de tri traduits en ligne « Statut : », glossaire et `DECISIONS.md`) et bloc « Agent skills »
  de `CLAUDE.md`.
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
