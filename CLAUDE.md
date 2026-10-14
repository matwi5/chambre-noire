# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Interface web locale pour générer et modifier des images avec Qwen-Image 2.1, sur PC Windows (Vulkan, CUDA, CPU) ou Mac
Apple Silicon (Metal), sans droits administrateur. Le README est la documentation utilisateur et technique de référence ;
cadrage dans `BRIEF.md`, décisions dans `DECISIONS.md`, état et journal dans `ETAT_DU_PROJET.md`.

Le dépôt GitHub est **public** : rien de propre à la machine du porteur dans les fichiers suivis (nom réseau du Mac,
adresses IP, noms Tailscale, chemins `/Users/…`, contenu de `tools/access_code.txt`), y compris dans `travail/tasks/`.

## Commandes

Python du projet : `venv/bin/python` (Mac), `venv\Scripts\python.exe` (Windows). Exemples ci-dessous en version Mac.

```bash
venv/bin/python -m pip install -r requirements.txt   # Pillow, NumPy (+ pywin32 sous Windows)
venv/bin/python setup.py            # moteur sd.cpp + modèles (épinglés, SHA256), raccourci, calibration
venv/bin/python setup.py --check    # vérifie l'installation sans rien télécharger
# options de setup.py : --q8 (modèle Q8_0), --cuda / --no-cpu (Windows), --no-calibrate
venv/bin/python tools/launch.py [--model q4|q8] [--port 7860] [--lan] [--no-browser]
venv/bin/python tools/calibrate.py [--if-needed]   # 3 générations de calibration, sans passer par le serveur
venv/bin/python tools/make_service.py [--remove]   # Mac : LaunchAgent qui lance launch.py --no-browser --lan
```

Vérifications : aucun lint ni typage n'est déclaré. Après un changement :

- Python : `venv/bin/python -m py_compile tools/launch.py` (et les fichiers touchés) ;
- JavaScript de `tools/ui/index.html` : extraire les blocs `<script>` et lancer `node --check` dessus ;
- comportement du serveur sans GPU : banc de test `venv/bin/python -m unittest discover -s tests` (quelques secondes).
  `tests/bench.py` sert `tools/launch.py` sur un port libre, tous ses dossiers repointés vers un dossier temporaire,
  avec le faux moteur `tests/fake_sdcli.py` (`FAIL` ou `SLOW[=s]` dans le prompt le font échouer ou ralentir) ;
  `bench.capture_push()` intercepte les notifications, `bench.LOG` reçoit les sorties du serveur. Un nouveau chemin
  calculé à l'import de `launch.py` doit être repointé dans `bench.start()`, sinon le banc écrit dans le dépôt. Les
  aperçus de moins de 1000 octets sont ignorés par `latest_preview`. Pour l'interface : servir le banc (`bench.start()`
  dans un script) et le piloter dans Chrome sans écran par le protocole DevTools depuis Node (WebSocket natif), sans
  installer Playwright. Tester dans les dimensions du téléphone du porteur (Android, application installée) :
  `Emulation.setDeviceMetricsOverride` 367×760 à une densité de 2,5, `mobile: true`, tactile activé ; l'interface
  y passe en mode allégé (`html.lite`). Une vue plus grande cache des débordements, et regarder les captures ;
- `tests/run_tests.py --steps 8 [--only t2i|edit|mask|annot]` : bout en bout, serveur lancé sur 127.0.0.1:7860. Il
  lance de **vraies générations GPU** (plusieurs minutes), écrit dans `outputs/`, le journal et `tools/calibration.json` :
  ne le lancer que si l'utilisateur le demande.

## Service macOS sur le poste du porteur

L'interface tourne en LaunchAgent `com.matwi5.qwen-image-local` (journal `logs/service.log`), avec `--lan`.
`tools/ui/index.html` est relu à chaque requête : un changement d'interface est en ligne dès l'enregistrement, donc
avant que le serveur qui va avec soit relancé. Un changement de `tools/launch.py` demande de relancer le service, et
seulement si aucune génération ne tourne :

```bash
venv/bin/python -c "import json,urllib.request as u; print(json.load(u.urlopen('http://127.0.0.1:7860/api/status'))['busy'])"
launchctl kickstart -k gui/$(id -u)/com.matwi5.qwen-image-local   # si False
```

Ne jamais afficher la réponse complète de `/api/status` venant de 127.0.0.1 ni `tools/access_code.txt` : ils contiennent
le code d'accès du téléphone. Ne lancer aucune génération réelle et ne supprimer aucune image de `outputs/` sans accord.

## Architecture

```text
navigateur ──HTTP──▶ tools/launch.py ──lance une fois par génération──▶ sdcpp/<moteur>/sd-cli ──▶ PNG
tools/ui/index.html   ThreadingHTTPServer, file + un seul thread worker      (pas de sd-server persistant)
```

- **Un seul fichier serveur** (`tools/launch.py`, bibliothèque standard + Pillow ; `Server` garde une file de 128 connexions, la galerie en ouvre une par miniature) : état global `S` (moteur, modèle,
  jobs en mémoire dans `S.jobs`, file `S.q`), un thread `worker()` qui exécute les jobs un par un via `run_job()`. Celui-ci
  construit la ligne de commande (`build_cmd`), lit la sortie de sd-cli ligne à ligne et en tire l'étape, la phase et les
  durées (`PROGRESS_RE`, lignes « … completed, taking x s ») qui alimentent la calibration. Les jobs ne survivent pas à un
  redémarrage.
- **Fichiers** : dossier de travail `jobs/<id>/` (images d'entrée, aperçus, `sd-cli.log`, 20 derniers gardés au
  lancement), image finale `outputs/<id>_<mode>.png`, une ligne par image dans `outputs/journal.jsonl`. La galerie
  (`/api/history`) est la liste des PNG de `outputs/` croisée avec le journal ; miniatures dans `outputs/.thumbs/`.
  Les images d'entrée (`init.png`, `ref_N.png`) sont copiées du dossier de travail vers `outputs/.inputs/<image>/` en
  fin de job (`save_inputs`, et au démarrage pour les dossiers encore présents) ; `/api/delete` les supprime avec l'image.
  Une génération annulée (en cours ou en file) ne laisse rien : `discard_cancelled` supprime son dossier de travail et
  une image finale déjà écrite. Le statut `cancelled` est posé avant que le moteur soit arrêté : un test doit attendre
  que `S.current` ait changé avant de regarder le disque.
- **Notifications** (Web Push, `pywebpush`) : `notify_job` envoie depuis `worker()`, dans un thread, à la fin d'un job
  terminé ou en échec, à chaque abonnement de `tools/push_subscriptions.json` ; clé VAPID `tools/push_vapid.pem` créée au
  premier usage. Le service worker (`tools/ui/sw.js`) affiche la notification seulement si aucune fenêtre de
  l'application n'est visible. Le message ne contient jamais le prompt. Sans `pywebpush`, le serveur tourne, sans
  notifications. Tester sans réseau : intercepter `requests.post` et déchiffrer avec `http_ece`.
- **Interface** : un seul fichier `tools/ui/index.html` (HTML, CSS et JS sans dépendance ni build). Elle suit les
  générations qu'elle a lancées (`pageJobs`) en interrogeant chacune par `/api/job/<id>` chaque seconde, et la file
  commune (`queue` de `/api/status`, entrées produites par `queue_entry`) toutes les 2 s tant qu'elle n'est pas vide ;
  après un rechargement, elle se rattache aux générations normales de `queue`. Réglages et
  brouillons dans `localStorage` (`qwen-opt`, `qwen-<onglet>_prompt`). `manifest.webmanifest`, `sw.js` et les icônes
  servent à l'installation sur le téléphone ; le service worker ne touche qu'à la navigation, jamais à `/api/*`.
- **Contrôle d'accès** (dans cet ordre, dans `H`) : `_host_ok` (liste blanche de `Host` contre le rebinding DNS, noms du
  Wi-Fi et de Tailscale figés au démarrage), `_post_refused` (tout POST : `Sec-Fetch-Site`, `Origin` égal à l'origine du
  `Host`, `Content-Type: application/json` exigé, sinon 403/415), puis `_allowed` (le Mac lui-même passe ; les autres
  appareils, et toute requête relayée par `tailscale serve`, présentent le cookie dérivé du code d'accès). Toute
  nouvelle route POST passe par ces contrôles : l'interface doit envoyer `Content-Type: application/json`, même sans corps.
- **Mode incognito** (`"incognito": true` dans `/api/generate`) : dossier `jobs/incognito_<id>/` supprimé en fin de job
  (et au démarrage), PNG gardé en mémoire (`job["png"]`) et servi une fois par `/api/job/<id>/result`, puis oublié par
  `/api/job/<id>/forget` ; ni `outputs/`, ni journal, ni calibration, ni détail dans `logs/`. Toute nouvelle écriture
  sur le disque ou dans les journaux doit respecter ce mode.
- **Estimation des durées** : modèle de coût dans `tools/estimate.py` (`predict`, priors par moteur, mesures par
  `"<moteur>/<modèle>"` dans `tools/calibration.json`, filtrées sur la release de sd.cpp installée lue dans
  `sdcpp/<moteur>/.installed`). Les coefficients partent vers l'interface par `/api/status`.

## Pièges et invariants

- **Formule dupliquée en JavaScript** : `parts()`, `refPx` et `inputsFor` de `index.html` recopient `predict()` et
  `ref_px()` de `estimate.py` (jetons de 16×16 px, arrondi à 32). Une modification de la formule ou d'un coefficient se
  fait des deux côtés. `PREVIEW_EVERY = 5` côté interface doit égaler le défaut `preview_interval` de `build_cmd`.
  L'estimation de chaque entrée de la file (`queue_entry`) appelle `estimate.predict` : pas de troisième copie.
- **Noms des modèles** : ceux de `setup.py` doivent correspondre à `MODELS` et `DIFFUSION` en tête de `tools/launch.py`.
- **Release de sd.cpp** : `.installed` doit garder le format `master-NNN-hash` ; `estimate.prefix_cache` en lit le numéro
  (cache de préfixe à partir de 903). Si sd-cli change le texte de ses lignes « completed », `make_sample` renvoie
  `None` et les mesures cessent sans erreur visible.
- **Moteurs** : Windows `master-890` (Vulkan, CPU, CUDA) avec l'encodeur int8 corrigé par `tools/fix_int8_te.py` ;
  Mac `master-959` avec l'encodeur GGUF et sa tour vision. Les réglages Metal (`--fa`, `--params-backend te=disk`,
  `--mmap`) sont justifiés dans le commentaire de `BACKENDS` : ne pas les retirer sans remesurer.
- **Une génération qui lève une exception échoue seule** : `worker()` la passe en `failed` par `fail_job` et prend la
  suivante. Un champ que `build_cmd` utilise tel quel se valide d'abord dans `request_error` (400), pour qu'une demande
  invalide soit refusée tout de suite plutôt que d'échouer dans la file.
- **`tools/config.json` est suivi par git** et contient les préférences du porteur (`"model": "q8"`) ; `setup.py` réécrit
  `backend` sous Windows. `sd_port` n'est lu nulle part.
- **Fichiers périmés** : `start-ui-sdcpp.cmd` (nom de modèle sans `UC-`, sd-server) et `workflows/*.json` (lus par
  aucun code) ne reflètent plus l'application.
- `setup.py` ne rehache pas un fichier qui a son marqueur `.sha256ok` et la bonne taille ; un fichier dont l'empreinte
  est fausse devient `.corrompu` et n'est jamais supprimé seul.

## Conventions

- Documentation, commentaires et interface en français ; messages de commit en anglais, une phrase à l'impératif sans
  préfixe (« Add an incognito mode that keeps generated images off the disk »), corps qui explique le pourquoi.
- Le README décrit chaque comportement visible et l'API locale : le mettre à jour dans le même commit que le code.
- Suivi des tâches : Asana « Hub · Suivi des tâches », section « Qwen-Image local » (GID `1219496223389136`), tâche
  mère de Claude « [code] Qwen-Image local : prochaines sessions Claude Code » (GID `1219493010479174`), tenus par
  `asana-board:suivi-asana` (adopté le 14/10/2026). Specs dans `docs/specs/`, plans des gros travaux dans
  `travail/tasks/` ; l'état et les pistes restent dans `ETAT_DU_PROJET.md`.
- Au démarrage d'une session : lire la section « État » et les 5 premières entrées du « Journal » de
  `ETAT_DU_PROJET.md`. Avant de proposer un changement de conception, vérifier qu'il n'est pas déjà tranché dans
  `DECISIONS.md`.

## Agent skills

### Issue tracker

Tickets dans Asana (« Hub · Suivi des tâches », section « Qwen-Image local »), un ticket par sous-tâche de la tâche
mère de Claude. Voir `docs/agents/issue-tracker.md`.

### Triage labels

Rôles de tri traduits en ligne « Statut : » et assignation (plan gratuit, pas d'étiquettes). Voir
`docs/agents/triage-labels.md`.

### Domain docs

Un seul contexte : `GLOSSARY.md` à la racine, décisions dans `DECISIONS.md`. Voir `docs/agents/domain.md`.
