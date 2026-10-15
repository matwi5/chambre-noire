# Carte du code

Où trouver quoi dans les deux gros fichiers, pour s'orienter sans les lire en entier (`tools/launch.py` ≈ 110 Ko,
`tools/ui/index.html` ≈ 170 Ko). Repères par noms de fonctions, de constantes et de sections, jamais par numéros de
ligne : chercher le nom (`grep -n "def worker" tools/launch.py`), puis lire autour. L'API locale (routes, champs,
codes d'erreur) est décrite dans le README, « Fonctionnement technique » ; les formats et les raisons dans
`DECISIONS.md`.

```text
navigateur ──HTTP──▶ tools/launch.py ──lance une fois par génération──▶ sdcpp/<moteur>/sd-cli ──▶ PNG
tools/ui/index.html   ThreadingHTTPServer, file + un seul thread worker      (pas de sd-server persistant)
```

## `tools/launch.py` : le serveur (bibliothèque standard + Pillow, `cryptography` pour l'espace privé)

Dans l'ordre du fichier :

- **Constantes et moteur** (en tête) : `ROOT`, `P()` (chemin sous la racine, relu à chaque appel : le banc repointe
  `ROOT`), `MODELS` et `DIFFUSION` (noms des fichiers de modèles, à garder égaux à ceux de `setup.py`), `BACKENDS`
  (options de sd-cli par moteur, réglages Metal justifiés en commentaire), `PLATFORM_BACKENDS`, `PROGRESS_RE` et
  `TAKING_RE` (lecture de la sortie de sd-cli), `MAX_VARIANTS`, `MAX_CAMPAIGN`, `INCOGNITO_TTL`, `PAGE_TOKEN_RE`.
  `record_calib`, `load_config`, `engine_tag`, `default_backend`.
- **Accès** : `ACCESS_FILE`, `ACCESS_COOKIE`, `LOCAL_CLIENTS`, `PUBLIC_FILES` (manifeste, icônes, service worker,
  servis sans cookie), `LOGIN_PAGE`. Plus bas : `normalize_code`, `access_token`, `load_access_code`, `lan_address`,
  `tailscale_hosts`, `tailscale_serve_url`.
- **Notifications** (Web Push, `pywebpush`) : `push_vapid` (clé `tools/push_vapid.pem` créée au premier usage),
  `push_subscriptions` (`tools/push_subscriptions.json`, sous `PUSH_LOCK`), puis `notify_job` (génération hors lot,
  terminée ou en échec), `notify_lot` (une seule par lot) et `push_notify` (envoi dans un thread, à chaque abonnement ;
  appareil désabonné retiré). Jamais le prompt dans le message ; une génération privée notifie comme une normale.
  Sans `pywebpush`, le serveur tourne sans notifications.
- **Prompts enregistrés** : `saved_prompts()` (lecture et écriture de `tools/saved_prompts.json` sous `PROMPTS_LOCK`,
  fichier temporaire puis `os.replace` ; un fichier illisible lève une erreur et n'est jamais écrasé),
  `prompt_error` (400), `change_prompt` ; `prompt_types()` relit `tools/prompt_types.json` à chaque appel, sans
  jamais l'écrire (ids `type-…`, que les routes d'écriture ne trouvent pas : 404).
- **Espace privé** (`private/`) : constantes `PRIVATE`, `PRIVATE_COOKIE`, `PRIVATE_IDLE`, `PRIVATE_LOCK` (un `RLock`),
  `REKEY`, `SCRYPT_N`, `HAVE_CRYPTO` ; clés : `read_space`, `code_key`, `write_space`, `open_space` ; mise sur disque :
  `sync_fd`, `write_synced`, `sync_dir` ; chiffrement par fichier : `file_key`, `seal`, `unseal` ; images :
  `store_private`, `read_private`, `private_history` ; changement de code : `rekey_space` (tout dans
  `private/.rekey/`, bascule par `os.replace` de `space.json`) et `finish_rekey` (termine ou abandonne un changement
  interrompu, au démarrage et sous `PRIVATE_LOCK` avant toute ouverture ou écriture) ; `private_code_error`.
- **Galerie et journal** : `input_files`, `save_inputs` (entrées copiées vers `outputs/.inputs/<image>/`),
  `output_path`, `JOURNAL_LOCK`, `journal_entries`, `append_journal` (fin de génération), `write_journal`,
  `drop_from_journal` (« Rendre privée »), `delete_output` et `delete_extras` (image et tout ce qui s'y rattache),
  `read_inputs`, `adopt_output` (« Rendre privée »), `history()` (PNG de `outputs/` croisés avec le journal),
  `thumb_jpeg`, `thumbnail` (`outputs/.thumbs/`).
- **État** : `class State`, instance `S` (moteur, modèle, générations en mémoire `S.jobs`, file `S.q`, lots `S.lots`,
  génération en cours `S.current`, sessions privées `S.private_sessions`, noms `S.lan_hosts` et `S.https_hosts`).
- **Préparer et lancer une génération** : `data_url_bytes`, `write_data_url`, `image_size`, `build_cmd` (ligne de
  commande de sd-cli ; aperçu tous les `preview_interval` pas), `latest_preview`, `run_job` (lit la sortie ligne à
  ligne : étape, phase, durées pour la calibration ; écrit l'image, le journal, les entrées), `secret(job)` (incognito
  ou privée : rien en clair), `kind_of`, `keep_private` (chiffre une génération privée), `discard_cancelled`,
  `forget_files`, `fail_job`.
- **File** : `ACTIVE`, `cancel_job`, `forget_job`, `sweep()` (appelé en tête de chaque requête : oublie les générations
  incognito ou privées terminées depuis `INCOGNITO_TTL`, ferme les sessions privées inactives depuis `PRIVATE_IDLE`),
  `worker()` (thread de calcul : un job à la fois ; une exception fait échouer ce job seul ; dans son `finally`,
  fichiers d'une génération secrète supprimés, fin de lot, puis `S.current` rendu en dernier), `end_of_lot`.
- **Demandes** : `request_error` (400 pour tout champ que `build_cmd` utilise tel quel), `expand_request` (une
  demande par image d'un lot : variantes `count`, campagne `campaign`), `draw_seeds` (graines -1 tirées par le serveur
  pour être écrites au journal), `active_jobs`, `queue_position`, `request_inputs`, `queue_entry` (ligne de `queue`
  dans `/api/status`, estimation par `estimate.predict`), `new_job`, `public(job)` (ce que `/api/job/<id>` montre),
  `quiet_request`.
- **HTTP** : `class Server` (file de 128 connexions : la galerie en ouvre une par miniature), `class H` : `log_message`
  (tait `/api/private/`), `_send` ; contrôles dans l'ordre `_host_ok` (liste blanche de `Host`), `_post_refused`
  (POST : `Sec-Fetch-Site`, `Origin`, `Content-Type: application/json`), `_allowed` (le Mac passe, les autres
  présentent le cookie d'accès) ; `_proxied`, `_local`, `_secure` (espace privé : adresse source locale et `Host` local
  ou nom HTTPS de `tailscale serve`) ; sessions privées : `_private_token`, `_private_session`, `_send_private`,
  `_open_session` ; routes privées : `_private_get`, `_private_post` ; toutes les autres routes : `do_GET`, `do_POST`
  (une suite de `if path == …`).
- **Démarrage** : `exclude_from_backup` (Mac : `jobs/` hors de Time Machine), `setup_state`, `main()` (options,
  `--lan`, Tailscale, ménage de `jobs/`, threads). Le banc n'exécute pas `main()`.

`tools/estimate.py` : modèle de coût des durées (`predict`, `ref_px`, `prefix_cache`, `make_sample`, `class Store`
pour `tools/calibration.json`).

## `tools/ui/index.html` : l'interface (HTML, CSS et JavaScript, sans dépendance ni build)

Le fichier se lit par ses commentaires d'en-tête `/* ---…` (CSS) et `// ---…` (JavaScript). Un petit premier bloc
`<script>` dans `<head>` pose `html.lite` (téléphone : effets allégés) ; tout le reste du JavaScript est dans le
dernier bloc, après le HTML.

- **CSS** : sections « jetons », « fond », « verre liquide », « barre du haut », « barre d'onglets », « panneaux du
  bas », « compositeur », « panneau Réglages », « Éditer et Dessiner », « visionneuse plein écran », « résultat »,
  « île », « pellicule … liste de la file », « prompts enregistrés », « espace privé », « messages et
  confirmations », « téléphone (html.lite) ».
- **HTML** : onglets `#pane-t2i`, `#pane-edit`, `#pane-mask`, `#pane-hist` (galerie `#histGrid`) ; compositeur
  `#composer` (prompts `#t2i_prompt`, `#edit_prompt`, `#mask_prompt`, bouton `#go`) ; zone de résultat `#result` ;
  barre d'onglets `#tabbar` ; visionneuse `#viewer` (`#vKeep` : « Garder celle-ci ») ; images d'entrée `#iv` ;
  feuilles `.sheet` : `#askSheet`, `#setSheet`, `#engineSheet`, `#lotSheet`, `#queueSheet`, `#promptSheet`,
  `#promptEditSheet` et celles de l'espace privé (`#privCreateSheet`, `#privUnlockSheet`, `#adoptSheet`…).
- **JavaScript**, sections dans l'ordre :
  - « valeurs fixes » : `RATIOS`, `RES`, `STEPS`, `PREVIEW_EVERY`, `MAX_REFS` ; `applyEstimates` ; estimation
    (`refPx`, `inputsFor`, `parts` : copies de `estimate.py`) ; réglages `opt` (`localStorage` `qwen-opt`),
    `refreshChoices`, `setIncog`.
  - « onglets & statut » : `TABS`, changement d'onglet (`mode`) ; « panneaux du bas » : `openSheet`, `closeSheet`
    (un seul ouvert, `openedSheet`) ; `refreshStatus()` (interroge `/api/status` toutes les 5 s, 2 s tant que la file
    n'est pas vide ; met à jour `queueState`, l'île, la file et l'espace privé par `applyPrivate`).
  - « images », « dessin » : `toEntry`, `renderEditThumbs`, `setMaskImage`, `showMaskImage`, `dropMaskImage`,
    `exportMask`.
  - « requête & loader » : `buildRequest` ; « messages et confirmations » : `toast`, `ask` et `answer` (feuille
    `#askSheet`, jamais `confirm()`).
  - « générations de la page, zone de résultat, île et file » : `pageJobs` (générations lancées par cette page),
    `PAGE_TOKEN`, `ownIds` et `saveOwn` (`localStorage` `qwen-own`), `isActive`, `lotOf`, `gridOf`, `show`,
    `showGrid`, `renderStrip`, `renderIsland`, `onIsland` (file non vide : `#queueSheet`, sinon `#engineSheet`),
    `renderQueue`, `ownOf` (ligne de `queue` → génération de la page), `track` (suit une génération, `pollJobs` chaque
    seconde), `finish` (image terminée : dans la page, ou recharge la galerie), `drop` ; bouton `#go` et reprise après
    rechargement (fonction `resume`).
  - « notifications » : `pushSubscribe`, `askNotifications`.
  - « prompts enregistrés » : `prompts`, `openPrompts`, `renderPrompts`, `usePrompt`, `savePrompt`.
  - « galerie et visionneuse » : `histItems`, `vList` (ce que parcourt la visionneuse : la galerie ou les images d'un
    lot de la page), `loadHistory`, `renderGallery`, `openViewer`, `stepViewer`, `closeViewer`, gestes (`resetZoom`).
  - « partager et copier » ; « images d'entrée » : `openInputs`, `inputAction`, `addEditImage` ; actions de la
    visionneuse : `viewerAction`, `removeFromViewer`, `lotMembers`, `keepThis` (« Garder celle-ci »), `deleteCurrent`.
  - « espace privé » : `privState`, `inPrivate()`, `applyPrivate`, `changedSpace` ; saisie propre à chaque espace :
    `asideInput` (saisie de l'autre espace, en mémoire de la page), `erasePrivate` (« Sortir » demandé), `readInput`,
    `putInput`, `swapInput`, `emptyTab` (vidage après « Générer », dans l'espace d'où la demande est partie) ; un ajout
    d'image asynchrone (Éditer, Dessiner) va dans la saisie de l'espace où il a commencé. `openPrivSheet`,
    `privCreate`, `privUnlock`, `privLock`, `privChangeCode`, `privReset`, `adoptImage`.

Fichiers voisins : `tools/ui/sw.js` (service worker : navigation seulement, jamais `/api/*`),
`tools/ui/manifest.webmanifest` et les icônes (installation sur le téléphone).

## Mécanismes

Le détail de ce que font ces zones ensemble ; les invariants à ne pas casser sont dans `CLAUDE.md`, « Pièges et
invariants ».

- **Une génération** : `worker()` exécute les jobs un par un via `run_job()`, qui construit la ligne de commande
  (`build_cmd`), lit la sortie de sd-cli ligne à ligne et en tire l'étape, la phase et les durées (`PROGRESS_RE`,
  lignes « … completed, taking x s ») qui alimentent la calibration. Les jobs vivent en mémoire (`S.jobs`) et ne
  survivent pas à un redémarrage.
- **Fichiers** : dossier de travail `jobs/<id>/` (images d'entrée, aperçus, `sd-cli.log` ; les 20 derniers gardés au
  lancement), image finale `outputs/<id>_<mode>.png`, une ligne par image dans `outputs/journal.jsonl`. La galerie
  (`/api/history`) est la liste des PNG de `outputs/` croisée avec le journal ; miniatures dans `outputs/.thumbs/`.
  Les images d'entrée (`init.png`, `ref_N.png`) sont copiées du dossier de travail vers `outputs/.inputs/<image>/` en
  fin de job (`save_inputs`, et au démarrage pour les dossiers encore présents) ; `/api/delete` les supprime avec
  l'image (`delete_output`). Toute écriture du journal passe sous `JOURNAL_LOCK` : l'ajout de fin de génération
  (`append_journal`) et la réécriture de « Rendre privée » (`drop_from_journal`, qui retire la ligne d'une image).
  Une génération annulée (en cours ou en file) ne laisse rien : `discard_cancelled` supprime son dossier de travail et
  une image finale déjà écrite. Le statut `cancelled` est posé avant que le moteur soit arrêté.
- **Lots** (variantes : `count` de 2 à 4, mode Créer ; campagne : `campaign`, 2 à 10 photos avec leurs dimensions,
  mode Éditer) : `expand_request` en tire une demande par image, `/api/generate` une génération par demande
  (`new_job`), reliées par `job["lot"]` (`id`, `rank`, `size`) et gardées dans `S.lots` même quand une génération
  incognito quitte `S.jobs`. Les graines à -1 sont tirées par le serveur (`draw_seeds`) pour être écrites au journal.
  Une seule notification par lot (`notify_lot`), envoyée par `end_of_lot` depuis le `finally` de `worker()` quand plus
  aucune génération du lot n'est active ; le lot quitte alors `S.lots`, ce qui empêche un doublon quand une génération
  annulée en file passe ensuite.
- **Notifications** : `notify_job` part de `worker()`, dans un thread, à la fin d'un job hors lot terminé ou en échec,
  vers chaque abonnement de `tools/push_subscriptions.json`. Le service worker (`tools/ui/sw.js`) n'affiche la
  notification que si aucune fenêtre de l'application n'est visible. Tester sans réseau : `bench.capture_push()`, ou
  intercepter `requests.post` et déchiffrer avec `http_ece`.
- **Prompts enregistrés** : titre et texte seulement, jamais de réglages ; `used` (secondes) ordonne la liste.
  Enregistrer un prompt est un geste explicite, permis aussi en incognito (décision de la spec) ; choisir un prompt en
  incognito ne met pas à jour `used`. Le banc lit `tools/prompt_types.json` du dépôt (pas de repointage).
- **Interface et serveur** : l'interface suit les générations qu'elle a lancées (`pageJobs`) en interrogeant chacune
  par `/api/job/<id>` chaque seconde, et la file commune (`queue` de `/api/status`, entrées produites par
  `queue_entry`) toutes les 2 s tant qu'elle n'est pas vide ; après un rechargement, elle se rattache aux seules
  générations normales lancées depuis ce navigateur (identifiants dans `localStorage`, `qwen-own`). Ses lignes
  incognito de `queue` se reconnaissent au jeton de la page (`PAGE_TOKEN`, champ `page` de `/api/generate`). Un lot
  terminé s'affiche en grille (`gridOf`) ; la visionneuse parcourt `vList` (la galerie, ou les images d'un lot de la
  page, incognito comprises par leur adresse `blob:`). Réglages, brouillons de la saisie publique et générations à
  reprendre dans `localStorage` (`qwen-opt`, `qwen-<onglet>_prompt`, `qwen-own`).
- **Contrôle d'accès** : `_host_ok` (liste blanche de `Host` contre le rebinding DNS, noms du Wi-Fi et de Tailscale
  figés au démarrage), `_post_refused` (tout POST : `Sec-Fetch-Site`, `Origin` égal à l'origine du `Host`,
  `Content-Type: application/json` exigé, sinon 403/415), puis `_allowed` (le Mac lui-même passe ; les autres
  appareils, et toute requête relayée par `tailscale serve`, présentent le cookie dérivé du code d'accès). L'espace
  privé ajoute `_secure` (toutes ses routes sauf `lock`, la génération privée et l'aperçu d'une génération privée) :
  adresse source 127.0.0.1/::1 et `Host` local ou nom HTTPS de `tailscale serve` (`S.https_hosts`), jamais les
  en-têtes de relais, qu'un appareil du Wi-Fi peut envoyer en `http://` ; `/api/private/reset` exige `_local`.
- **Espace privé** (format dans `DECISIONS.md`) : `space.json` garde la clé publique X25519 en clair et la clé privée
  chiffrée par scrypt + AES-GCM ; `/api/private/unlock` ouvre une session par appareil (`S.private_sessions`, cookie
  `qwen_private`, en plus du cookie d'accès, demandée même sur le Mac), fermée par `sweep()` après `PRIVATE_IDLE` sans
  requête privée. Sans `cryptography` (`HAVE_CRYPTO`), routes en 503 et interface masquée. Le banc repointe `PRIVATE`
  et abaisse `SCRYPT_N`. Changer le code rechiffre tout dans `private/.rekey/` ; la bascule est le `os.replace` de
  `space.json`. Côté interface, déverrouillé = « dans l'espace privé » (`inPrivate()`, classe `html.priv`) : aucun
  bouton ne le signale à l'arrivée (entrée : cadenas `#privEntry` de la galerie ; sortie : `#privExit`), décision du
  porteur.
- **Mode incognito** (`"incognito": true` dans `/api/generate`) : dossier `jobs/incognito_<id>/` supprimé en fin de
  job (et au démarrage), PNG gardé en mémoire (`job["png"]`) et servi une fois par `/api/job/<id>/result`, puis oublié
  par `/api/job/<id>/forget` (ou `/api/forget` avec toutes celles de la page, envoyé à sa fermeture) ; ni `outputs/`,
  ni journal, ni calibration, ni détail dans `logs/`. Son identifiant (et celui de son lot) fait 128 bits tirés au
  hasard et n'est connu que de sa page : ni `queue`, ni `current_job` ne le montrent. Une génération incognito
  terminée que sa page n'a jamais fait oublier l'est par `sweep()`, `INCOGNITO_TTL` (24 h) après sa fin.
- **Génération privée** (`"private": true`, session exigée) : même chemin que l'incognito pendant le calcul
  (`jobs/private_<id>/`, `sd-cli.log` vers `os.devnull`, identifiant de 128 bits, rien dans `queue` ni les journaux),
  puis `keep_private` chiffre image, miniature (en mémoire), entrées et réglages avec la clé publique notée au
  lancement (`store_private`). Une génération privée ne s'arrête pas à la fermeture de la page (`/api/forget` ne vise
  que l'incognito, décision du porteur). Au lancement sur Mac, `exclude_from_backup` exclut `jobs/` de Time Machine.
- **Estimation des durées** : `tools/estimate.py` (`predict`, priors par moteur, mesures par `"<moteur>/<modèle>"`
  dans `tools/calibration.json`, filtrées sur la release de sd.cpp installée lue dans `sdcpp/<moteur>/.installed`). Les
  coefficients partent vers l'interface par `/api/status`.

## Tests

`tests/bench.py` (banc : `start`, `call`, `generate`, `wait_job`, `wait_idle`, `wait_until`, `capture_push`),
`tests/fake_sdcli.py` (faux moteur), `tests/test_*.py`, `tests/check.py` (tous les contrôles), `tests/ui/`
(`driver.mjs`, `serve.py`, tests `*.test.mjs`). Commandes dans `CLAUDE.md`.
