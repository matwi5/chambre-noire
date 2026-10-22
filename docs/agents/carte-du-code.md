# Carte du code

Où trouver quoi dans les deux gros fichiers, pour s'orienter sans les lire en entier (`tools/launch.py` ≈ 110 Ko,
`tools/ui/index.html` ≈ 170 Ko). Repères par noms de fonctions, de constantes et de sections, jamais par numéros de
ligne : `venv/bin/python tests/check.py --map worker` donne la ligne de chaque fonction, classe ou constante dont le
nom contient « worker » (`--map` seul : tout l'index des deux fichiers), puis lire autour. `check.py` échoue si un nom
cité ici entre accents graves n'existe plus dans le code : un renommage met la carte à jour dans le même commit.
L'API locale (routes, champs, codes d'erreur) est décrite dans le README, « Fonctionnement technique » ; les formats
et les raisons dans `DECISIONS.md`.

```text
navigateur ──HTTP──▶ tools/launch.py ──lance une fois par génération──▶ sdcpp/<moteur>/sd-cli ──▶ PNG
tools/ui/index.html   ThreadingHTTPServer, file + un seul thread worker      (pas de sd-server persistant)
```

## `tools/launch.py` : le serveur (bibliothèque standard + Pillow, `cryptography` pour l'espace privé)

Dans l'ordre du fichier :

- **Constantes et moteur** (en tête) : `ROOT`, `P()` (chemin sous la racine, relu à chaque appel : le banc repointe
  `ROOT`), `MODELS` et `DIFFUSION` (noms des fichiers de modèles, à garder égaux à ceux de `setup.py`), `BACKENDS`
  (options de sd-cli par moteur, réglages Metal justifiés en commentaire), `PLATFORM_BACKENDS`, `PROGRESS_RE` et
  `TAKING_RE` (lecture de la sortie de sd-cli), `MAX_VARIANTS`, `MAX_CAMPAIGN`, `PRIVATE_JOB_TTL`.
  `record_calib`, `load_config`, `code_version` (commit, date et branche du dossier servi, empreinte `server`
  de `launch.py` et `estimate.py`, relus toutes les `VERSION_TTL` s ; git seulement s'il y a un `.git`, jamais après un
  échec, sauf un délai dépassé ; `S.started` : la même chose au lancement, posé par `main()`), `engine_tag`,
  `default_backend`.
- **Accès** : `ACCESS_FILE`, `ACCESS_COOKIE`, `LOCAL_CLIENTS`, `PUBLIC_FILES` (manifeste, icônes, service worker,
  servis sans cookie), `LOGIN_PAGE`. Plus bas : `normalize_code`, `access_token`, `load_access_code`, `lan_address`,
  `tailscale_hosts`, `tailscale_serve_url`.
- **Notifications** (Web Push, `pywebpush`) : `push_vapid` (clé `tools/push_vapid.pem` créée au premier usage),
  `push_subscriptions` (`tools/push_subscriptions.json`, sous `PUSH_LOCK`), puis `notify_job` (génération hors lot,
  terminée ou en échec), `notify_lot` (une seule par lot) et `push_notify` (envoi dans un thread, à chaque abonnement ;
  appareil désabonné retiré). Jamais le prompt dans le message ; une génération privée notifie comme une normale.
  Sans `pywebpush`, le serveur tourne sans notifications.
- **Prompts enregistrés** : `prompt_list` (forme d'une liste lue), `saved_prompts()` (lecture et écriture de
  `tools/saved_prompts.json` sous `PROMPTS_LOCK`, fichier temporaire puis `os.replace` ; un fichier illisible lève une
  erreur et n'est jamais écrasé), `prompt_error` (400), `change_prompt` (sur `saved_prompts` ou, passée en `store`,
  la liste de l'espace privé `private_prompts`) ; `prompt_types()` relit `tools/prompt_types.json` à chaque appel, sans
  jamais l'écrire (ids `type-…`, que les routes d'écriture ne trouvent pas : 404).
- **Espace privé** (`private/`) : constantes `PRIVATE`, `PRIVATE_COOKIE`, `PRIVATE_IDLE`, `PRIVATE_LOCK` (un
  `RLock`), `REKEY`, `SCRYPT_N`, `HAVE_CRYPTO` ; clés : `read_space`, `code_key`, `write_space`, `open_space` ; mise
  sur disque : `sync_fd`, `write_synced`, `sync_dir`, avec les droits 600 et 700 de `open_private` et `private_dir` ;
  chiffrement par fichier : `file_key`, `seal`, `unseal` ; images : `store_private`, `read_private`,
  `private_history` ; prompts privés : `private_prompts` (`private/prompts`, scellé à l'étiquette `prompts`) ;
  changement de code : `rekey_space` (tout dans `private/.rekey/`, bascule par `os.replace` de `space.json`) et
  `finish_rekey` (termine ou abandonne un changement interrompu, au démarrage et sous `PRIVATE_LOCK` avant toute
  ouverture ou écriture) ; `private_code_error`.
- **Galerie et journal** : `input_files`, `save_inputs` (entrées copiées vers `outputs/.inputs/<image>/`),
  `output_path`, `JOURNAL_LOCK`, `journal_entries`, `append_journal` (fin de génération), `delete_output` et
  `delete_extras` (image et tout ce qui s'y rattache), `read_inputs`, `history()` (PNG de `outputs/` croisés avec le
  journal), `thumb_jpeg`, `thumbnail` (`outputs/.thumbs/`).
- **État** : `class State`, instance `S` (moteur, modèle, générations en mémoire `S.jobs`, file `S.pending` (liste des
  générations en attente dans l'ordre de calcul, seule source de l'ordre) protégée avec `S.current` par la condition
  `S.turn`, lots `S.lots`, génération en cours `S.current`, sessions privées `S.private_sessions`, noms `S.lan_hosts`
  et `S.https_hosts`).
- **Préparer et lancer une génération** : `data_url_bytes`, `write_data_url` (PNG ou JPEG écrit tel quel, autre
  format converti en PNG : sd-cli ne le lirait pas), `image_size`, `build_cmd` (ligne de commande de sd-cli ; aperçu
  tous les `preview_interval` pas), `latest_preview`, `start_job` (passage « en cours » : par `worker()` sous `S.turn`,
  et par `tools/calibrate.py`, qui appelle `run_job` hors de la file), `run_job` (lit
  la sortie ligne à ligne : étape, phase, durées pour la calibration ; écrit l'image, le journal, les entrées),
  `secret(job)` (génération privée : rien en clair), `keep_private` (chiffre une génération privée),
  `discard_cancelled`, `forget_files`, `fail_job` (tout échec écrit la même ligne neutre dans `logs/`).
- **File** : `ACTIVE`, `cancel_job` (statut changé sous `S.turn`), `forget_job`, `sweep()` (appelé en tête de chaque
  requête : oublie les générations privées terminées depuis `PRIVATE_JOB_TTL`, ferme les sessions privées
  inactives depuis `PRIVATE_IDLE`), `worker()` (thread de calcul : un job à la fois, pris en tête de `S.pending`,
  posé dans `S.current` et passé « en cours » sous `S.turn` en une seule opération ; une génération annulée en
  attente est sautée, une annulée après sa prise en tête ne lance pas le moteur (`run_job`) ; une exception fait
  échouer ce job seul ; dans son `finally`, fichiers d'une génération secrète supprimés, fin de lot, puis
  `S.current` rendu en dernier), `end_of_lot`.
- **Demandes** : `request_error` (400 pour tout champ que `build_cmd` utilise tel quel, et pour une demande incognito),
  `expand_request` (une demande par image d'un lot : variantes `count`, campagne `campaign`), `draw_seeds` (graines -1
  tirées par le serveur pour être écrites au journal), `active_jobs` (génération en cours puis `S.pending`, lus sous
  `S.turn`), `move_first` (« Passer en tête » : routes `/api/job/<id>/first` et `/api/lot/<id>/first`, réponse par
  `moved_first`), `in_space` (génération de l'espace public ou privé), `queue_ranks` (rang dans l'espace),
  `queue_position`, `request_inputs`, `job_estimate` (estimation par `estimate.predict`, seule source), `queue_entry`
  (ligne de `queue` dans `/api/status`), `queue_view` (file vue depuis un espace, `ahead` : travail caché de l'autre
  espace devant chaque entrée), `new_job` (`input_names` : noms des images d'entrée gardées), `public(job)` (ce que
  `/api/job/<id>` et `/api/generate` montrent, `mode` et `inputs` compris), `quiet_request`.
- **HTTP** : `class Server` (file de 128 connexions : la galerie en ouvre une par miniature), `class H` : `log_message`
  (tait `/api/private/`), `_send` ; contrôles dans l'ordre `_host_ok` (liste blanche de `Host`), `_post_refused`
  (POST : `Sec-Fetch-Site`, `Origin`, `Content-Type: application/json`), `_allowed` (le Mac passe, les autres
  présentent le cookie d'accès) ; `_proxied`, `_local`, `_secure` (espace privé : adresse source locale et `Host` local
  ou nom HTTPS de `tailscale serve`) ; sessions privées : `_private_token`, `_private_session`, `_in_private` (l'appareil est dans
  l'espace privé : session et requête sûre ; espace de `/api/status`), `_send_private`,
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
  bas », « compositeur », « panneau Réglages », « images d'entrée (Créer) et Dessiner », « visionneuse plein écran »,
  « résultat », « île », « liste de la file (page En cours) » (cartes de la file), « prompts enregistrés », « espace
  privé », « messages et confirmations », « téléphone (html.lite) ».
- **HTML** : onglets `#pane-run` (page En cours : zone de la page `#ownZone` avec `#stage` et « Rien en cours »
  `#resultEmpty` ; génération d'un autre appareil ou attente `#runNow` ; file `#runQueue` ; terminées `#runDone`, liste
  `#doneList`, « Tout retirer » `#doneClear`), `#pane-create` (page Créer : images d'entrée `#refs`, vignettes
  `#inThumbs`, ajout `#inDrop` et son champ `#inFiles`, bouton Dessiner `#drawBtn` (choix d'une image `#drawFile`,
  explication `#drawHint`), zone de dessin `#paintWrap` et `#paintCanvas`, masque ou annotation `#mask_mode`,
  interrupteur Campagne `#campSwitch` ; classe `drawing` quand le dessin est actif), `#pane-hist`
  (galerie `#histGrid`) ; compositeur `#composer` (champ unique `#prompt`, bouton `#go`) ; barre
  d'onglets `#tabbar` (onglet En cours : nombre `#runCount`, anneau `#runRing`) ; visionneuse `#viewer` (`#vKeep` :
  « Garder celle-ci ») ; images d'entrée `#iv` ; feuilles `.sheet` : `#askSheet`, `#setSheet`, `#engineSheet`,
  `#lotSheet`, `#promptSheet`, `#promptEditSheet` et celles de l'espace privé (`#privCreateSheet`, `#privUnlockSheet`,
  `#privCodeSheet`…).
- **JavaScript**, sections dans l'ordre :
  - « valeurs fixes » : `log` et `renderLog` (journal du panneau Moteur, `logLines` : une ligne écrite dans l'espace
    privé en sort à la sortie), `RATIOS`, `RES`, `STEPS`, `PREVIEW_EVERY`, `MAX_REFS` ; `applyEstimates` ; estimation
    (`refPx`, `inputsFor`, `parts` : copies de `estimate.py`) ; réglages `opt` (`localStorage` `qwen-opt`),
    `refreshChoices` (exemple du champ, `PLACEHOLDERS`) ; nature de la demande lue dans la saisie : `inputKind` (`t2i`
    sans image d'entrée, `edit` avec, `mask` dessin actif : `drawOn`), `singleImage`, `campaignShown` (interrupteur
    proposé à partir de 2 images), `inCampaign`, `variants` ; brouillon unique `qwen-prompt` (dans `init` : reprise une
    fois des anciens `qwen-<onglet>_prompt`).
  - « onglets & statut » : `TABS`, changement d'onglet (`mode`) ; « panneaux du bas » : `openSheet`, `closeSheet`
    (un seul ouvert, `openedSheet`) ; `refreshStatus()` (interroge `/api/status` toutes les 5 s, 2 s tant que la file
    n'est pas vide ; met à jour `queueState`, l'île, la page En cours et l'espace privé par `applyPrivate`, et le
    panneau Moteur, version servie comprise : `fmtVersion`, `staleServer`).
  - « images », « dessin » : `toEntry`, `addInputFiles` (choix, dépôt et collage, écouteur `paste` de la page Créer),
    `refuseWhileDrawing` (ajout refusé pendant le dessin, saisie affichée ou mise de côté), `noteInput` (saisie visée
    par un ajout, notée avant toute attente), `renderInputs` (images d'entrée de Créer, `inputImages`, puis
    `renderDrawing` : bouton Dessiner et zone de dessin, image du dessin `#paintImg` par `showImage`),
    `drawCanvasFor` (le tracé appartient à `drawFor`, l'image pour laquelle il a été commencé : gardé quand on éteint
    Dessiner, effacé avec son image), `drawWith` (une image seule dans la saisie, dessin actif, tracé vierge),
    `exportMask`, `paintedReference`.
  - « requête & loader » : `requestBase` (champs qu'aucun réglage ne fixe, communs avec « Relancer »), `buildRequest` ;
    « messages et confirmations » : `toast`, `ask` et `answer` (feuille `#askSheet`, jamais `confirm()`).
  - « affichage des images » : `showImage` (toute image qui change d'adresse : vidée, puis remplie une fois l'image
    chargée et décodée à part, miniature d'abord ; `img.want` : adresse attendue, une image arrivée trop tard est
    ignorée ; `keep` : l'aperçu d'avant reste jusqu'au suivant ; `once` : aperçu servi une fois ; `decoded` : image déjà
    décodée à part (image du dessin, lue par `toEntry`), posée tout de suite sans passer par `ready` ; `fit`, `dims` :
    miniature des visionneuses à la taille de l'image complète, par `fitThumb`, en unités de la scène `cqw`, `cqh`),
    `preload` et `ready` (les 10 dernières images décodées : miniatures des voisines de la visionneuse, image complète
    de la suivante dans le sens du parcours `vStep`, première image d'entrée),
    `clearImage`, `forgetPrivateImages` (sortie de l'espace privé : images privées et aperçus affichés, attendus ou
    chargés en avance, chargements en cours abandonnés, et tout lien vers une route privée avec son nom `prive_…`). Ne
    jamais réaffecter `src` d'une image visible à la main : elle garderait l'image d'avant à l'écran jusqu'au chargement
    de la nouvelle (`tests/check.py` refuse `$('vImg').src=…` et ses pareilles, `IMAGE_IDS`).
  - « générations de la page, page En cours, île et file » : `pageJobs` (générations lancées par cette page),
    `ownIds` et `saveOwn` (`localStorage` `qwen-own`), `isActive`, `isDone` (image prête ou échec),
    `isCampaignLot`, `lotOf`, `show` (`showOwn` : une génération active de la page, ou rien ; puis `renderRun`),
    `pageItem` (image de la page pour la visionneuse : vrai mode et images d'entrée, `mode` et `inputs` de son suivi),
    `spaceNow` (état de l'espace pour l'île et l'onglet ; `entryFrac`, `firstWait`, `ringOffset`), `renderIsland` (île)
    et `renderRunTab` (nombre et anneau de l'onglet En cours), `onIsland` (file non vide : page En cours, sinon
    `#engineSheet`), `renderRun` (haut de la page : génération de la page qui tourne, sinon d'un autre appareil, ou
    attente d'une génération cachée, classe `other` ; « Rien en cours » sans file ni terminée), terminées : `renderDone`
    (`doneEntries`, cartes `doneCard`, `failCard`, `lotCard` en grille ; `doneView` : leurs images pour la visionneuse),
    `evictDone` (`MAX_DONE`), `notifyDone` (message « Image prête », « Lot prêt » hors de la page En cours, `toast(…,
    go)`), `renderQueue` (file de la page en cartes : `queueCards` regroupe les entrées d'un lot, `queueCard` dessine
    une carte, `lotCases` ses cases (`lotCancels` : rangs annulés pendant la vie de la page), `lotSubs` ses lignes une
    fois dépliée (`openLots`) ; `lotLabel` : « N variantes » ou « Campagne · N photos » ; `qbtn` : bouton d'annulation
    ou de « Passer en tête », chemin fixé à l'affichage ; `hhmm` : heure de fin, `resLabel` : résolution), `ownOf`
    (ligne de `queue` → génération de la page, par identifiant), `ofSpace`, `spaceActive`, `firstActive` (celle qui
    tourne, sinon la prochaine dans l'ordre de calcul) et `nextActive` (la même, parmi les générations de l'espace
    affiché), `track` (suit une génération, avec sa demande `req` si la page l'a envoyée, un objet par lot, en mémoire
    de la page seulement ; `pollJobs` chaque seconde ; une privée « inconnue » quitte la page sans message), `finish`
    (fin d'une génération : terminée gardée, échec compris, ou annulée retirée), `drop` (retire une génération de la
    page) ; bouton `#go` ; reprise : `followQueue` (suit des entrées de la file), `resumeOwn` (générations normales de
    ce navigateur, après un rechargement et au retour dans l'espace public), `resume`, `adoptPrivate` (dans l'espace
    privé, toutes les générations privées actives de la file, `adopted` : pas lancées par la page, qui ne les fait pas
    oublier).
  - « notifications » : `pushSubscribe`, `askNotifications`.
  - « prompts enregistrés » : `promptsApi` (routes de l'espace affiché), `prompts`, `openPrompts` (ouverte par le
    bouton, filtre `promptUsage` sur la catégorie de la saisie, `inputKind`), `renderPrompts`, `usePrompt`,
    `savePrompt`.
  - « galerie et visionneuse » : `histItems`, `vList` (ce que parcourt la visionneuse : la galerie ou les terminées
    de la page), `loadHistory`, `renderGallery`, `openViewer`, `stepViewer`, `closeViewer` et `emptyViewer` (contenu
    vidé après le fondu de fermeture, ou tout de suite à la sortie de l'espace privé), gestes : `zoomable` (pincer,
    molette, glisser ; `resetZoom` pour la visionneuse, `resetInputZoom` pour les images d'entrée).
  - « partager et copier » ; « images d'entrée » : `openInputs`, `showInput`, `closeInputs` et `emptyInputs`,
    `inputAction`, `addEditImage` (« Éditer ») et `drawFrom` (« Dessiner », confirmation s'il y avait des images) ;
    « Reprendre » : `resumeFrom` (saisie remplacée, confirmation si elle n'est pas vide), `resumeImages` (images
    d'entrée selon le mode, `RESUME_FILES` : demande gardée `req`, sinon galerie), `canResume` (bouton `#vResume`),
    `settingsFor` (format, résolution et étapes qui redonnent l'image) ; « Relancer » (visionneuse `#vAgain`, terminées
    `data-again`) : `keptRequest` (demande gardée : l'image seule ou tout le lot), `againFrom` (reconstruite de l'image
    sinon), `canAgain`, `relaunch` (graine et espace du moment ; estimation), puis `launch` (envoi commun avec
    « Générer » : suivi, `accepted` (vidage de la saisie de « Générer »), message, page En cours), `again` (un geste à
    la fois) ;
    actions de la visionneuse : `viewerAction`, `removeFromViewer`, `lotMembers`, `keepThis` (« Garder celle-ci »),
    `deleteItem` (« Supprimer » : visionneuse et terminées), `forgetResult`.
  - « espace privé » : `privState`, `inPrivate()`, `applyPrivate`, `changedSpace` ; saisie propre à chaque espace :
    `asideInput` (saisie de l'autre espace, en mémoire de la page), `erasePrivate` (« Sortir » demandé), `readInput`,
    `putInput`, `swapInput`, `emptyInput` (vidage après « Générer », dans l'espace d'où la demande est partie) ; un
    ajout d'image asynchrone (Éditer, Dessiner) va dans la saisie de l'espace où il a commencé. `openPrivSheet`,
    `privCreate`, `privUnlock`, `privLock`, `privChangeCode`, `privReset`.

Libellés visibles et code (la spec et les tickets parlent avec les libellés de l'écran) : visionneuse « Éditer »,
« Dessiner », « Reprendre » (texte, images d'entrée, dessin et réglages : `resumeFrom`), « Relancer » (`againFrom`) et
« Supprimer » → `viewerAction('edit' | 'mask' | 'resume' | 'again' | 'delete')`, avec l'image décrite par `pageItem`
pour une image de la page ; carte d'une terminée → `doneCard`, ses boutons → `data-act` (« Relancer » : `data-again`,
aussi sur la carte d'un lot et d'un échec) dans l'écouteur de `#doneList` ; « Garder celle-ci » →
`keepThis` ; cadenas de la Galerie → `#privEntry`, « Sortir » → `privLock` ; pastille du haut → `#island`,
`renderIsland`.

Deux boucles suivent les générations sans se synchroniser : `pollJobs` (`/api/job/<id>`, chaque seconde) et
`refreshStatus` (`/api/status`, toutes les 2 à 5 s). Une réponse de l'une peut arriver avant celle de l'autre :
rapprocher une génération de la file par son identifiant, et traiter un 404 qui précède l'annonce de la fermeture de
l'espace (voir `CODING_STANDARDS.md`).

Fichiers voisins : `tools/ui/sw.js` (service worker : navigation seulement, jamais `/api/*`),
`tools/ui/manifest.webmanifest` et les icônes (installation sur le téléphone) ; `tools/ui/logo.svg` (logo de la barre
du haut, de la page du code d'accès et de l'onglet) est la source des icônes PNG, à régénérer depuis lui s'il change.

## Mécanismes

Le détail de ce que font ces zones ensemble ; les invariants à ne pas casser sont dans `CLAUDE.md`, « Pièges et
invariants ».

- **Une génération** : `worker()` exécute les jobs un par un via `run_job()`, qui construit la ligne de commande
  (`build_cmd`), lit la sortie de sd-cli ligne à ligne et en tire l'étape, la phase et les durées (`PROGRESS_RE`,
  lignes « … completed, taking x s ») qui alimentent la calibration. Les jobs vivent en mémoire (`S.jobs`) et ne
  survivent pas à un redémarrage.
- **Fichiers** : dossier de travail `jobs/<id>/` (images d'entrée, aperçus, `sd-cli.log` ; les 20 derniers gardés au
  lancement), image finale `outputs/<id>_<mode>.png`, une ligne par image dans `outputs/journal.jsonl`. La galerie
  (`/api/history`) est la liste des PNG de `outputs/` croisée avec le journal ; miniatures dans `outputs/.thumbs/`. Les
  images d'entrée (`init.png`, `ref_N.png`) sont copiées du dossier de travail vers `outputs/.inputs/<image>/` en fin de
  job (`save_inputs`, et au démarrage pour les dossiers encore présents) ; `/api/delete` les supprime avec l'image
  (`delete_output`). Toute écriture du journal passe sous `JOURNAL_LOCK` (`append_journal`, en fin de génération). Une
  génération annulée (en cours ou en file) ne laisse rien : `discard_cancelled` supprime son dossier de travail et une
  image finale déjà écrite. Le statut `cancelled` est posé avant que le moteur soit arrêté.
- **Lots** (variantes : `count` de 2 à 4, tous les modes, jamais avec une campagne ; campagne : `campaign`, 2 à 10
  photos avec leurs dimensions, en `edit`) : `expand_request` en tire une demande par image, `/api/generate` une
  génération par demande (`new_job`), reliées par `job["lot"]` (`id`, `rank`, `size`, et `campaign`, le marqueur qui
  distingue une campagne de variantes, posé par `/api/generate` : le mode ne le dit plus) et gardées dans `S.lots`
  même quand une génération privée quitte `S.jobs`. Côté interface, `isCampaignLot` lit le marqueur (un lot d'avant
  lui : campagne s'il est du mode `edit`) pour le titre d'un lot, son repère et « Garder celle-ci ». Les graines à -1
  sont tirées par le serveur (`draw_seeds`) pour être écrites au journal. Une seule notification par lot (`notify_lot`),
  envoyée par `end_of_lot` depuis le `finally` de `worker()` quand plus aucune génération du lot n'est active ; le lot
  quitte alors `S.lots`, ce qui empêche un doublon quand une génération annulée en file passe ensuite.
- **Notifications** : `notify_job` part de `worker()`, dans un thread, à la fin d'un job hors lot terminé ou en échec,
  vers chaque abonnement de `tools/push_subscriptions.json`. Le service worker (`tools/ui/sw.js`) n'affiche la
  notification que si aucune fenêtre de l'application n'est visible. Tester sans réseau : `bench.capture_push()`, ou
  intercepter `requests.post` et déchiffrer avec `http_ece`.
- **Prompts enregistrés** : titre et texte seulement, jamais de réglages ; `used` (secondes) ordonne la liste.
  Choisir un prompt enregistré met à jour son `used`, dans chaque espace. Le banc lit `tools/prompt_types.json` du dépôt
  (pas de repointage). Chaque espace a sa liste : dans l'espace privé, la feuille passe par `/api/private/prompts`
  (`private_prompts`, chiffrée) ; `changedSpace` ferme ses feuilles (confirmation comprise) et vide la liste de l'espace
  quitté ; une réponse reçue après un changement d'espace est ignorée.
- **Interface et serveur** : l'interface suit les générations qu'elle a lancées (`pageJobs`) en interrogeant chacune par
  `/api/job/<id>` chaque seconde, et la file de son espace (`queue` de `/api/status`, entrées produites par
  `queue_view`) toutes les 2 s tant qu'elle n'est pas vide ; la file et l'île ne parlent que des générations de l'espace
  affiché (`ofSpace`, `spaceActive`), le temps d'attente ajoute `ahead` ; après un rechargement, elle se rattache aux
  seules générations normales lancées depuis ce navigateur (identifiants dans `localStorage`, `qwen-own`), et dans
  l'espace privé à toutes les générations privées actives (`adoptPrivate`), avec le prompt complet que donne leur suivi
  (`followQueue`). À la sortie de l'espace privé, `changedSpace` retire de la
  page ses générations privées ; dans l'espace privé, les publiques restent suivies hors de l'écran. Les générations
  finies vont dans les terminées (`renderDone`, un lot fini en grille) ; la visionneuse parcourt `vList` (la galerie, ou
  les terminées de la page). Réglages, brouillons de la saisie publique et générations à reprendre dans `localStorage`
  (`qwen-opt`, `qwen-prompt`, `qwen-own`).
- **Contrôle d'accès** : `_host_ok` (liste blanche de `Host` contre le rebinding DNS, noms du Wi-Fi et de Tailscale
  figés au démarrage), `_post_refused` (tout POST : `Sec-Fetch-Site`, `Origin` égal à l'origine du `Host`,
  `Content-Type: application/json` exigé, sinon 403/415), puis `_allowed` (le Mac lui-même passe ; les autres
  appareils, et toute requête relayée par `tailscale serve`, présentent le cookie dérivé du code d'accès). L'espace
  privé ajoute `_secure` (toutes ses routes sauf `lock` et la génération privée) :
  adresse source 127.0.0.1/::1 et `Host` local ou nom HTTPS de `tailscale serve` (`S.https_hosts`), jamais les
  en-têtes de relais, qu'un appareil du Wi-Fi peut envoyer en `http://` ; `/api/private/reset` exige `_local`.
  Suivi, aperçu, annulation et oubli d'une génération privée, annulation d'un lot privé : `_hidden` (hors de
  l'espace privé, `_in_private`, réponse d'un identifiant inconnu, 404).
- **Espace privé** (format dans `DECISIONS.md`) : `space.json` garde la clé publique X25519 en clair et la clé privée
  chiffrée par scrypt + AES-GCM ; `/api/private/unlock` ouvre une session par appareil (`S.private_sessions`, cookie
  `qwen_private`, en plus du cookie d'accès, demandée même sur le Mac), fermée par `sweep()` après `PRIVATE_IDLE` sans
  requête privée. Sans `cryptography` (`HAVE_CRYPTO`), routes en 503 et interface masquée. Le banc repointe `PRIVATE`
  et abaisse `SCRYPT_N`. Changer le code rechiffre tout dans `private/.rekey/` ; la bascule est le `os.replace` de
  `space.json`. Côté interface, déverrouillé = « dans l'espace privé » (`inPrivate()`, classe `html.priv`) : aucun
  bouton ne le signale à l'arrivée (entrée : cadenas `#privEntry` de la galerie ; sortie : `#privExit`), décision du
  porteur.
- **Génération privée** (`"private": true`, session exigée) : pendant le calcul, dossier `jobs/private_<id>/`
  supprimé en fin de job (et au démarrage), `sd-cli.log` vers `os.devnull`, identifiant de 128 bits (comme celui de
  son lot), rien dans les journaux ; dans `queue`, une entrée complète vue depuis l'espace privé seulement,
  puis `keep_private` chiffre image, miniature (en mémoire), entrées et réglages avec la clé publique notée au
  lancement (`store_private`). Une génération privée ne s'arrête pas à la fermeture de la page ; finie, elle est
  oubliée par `/api/job/<id>/forget` (envoyé par sa page), sinon par `sweep()`, `PRIVATE_JOB_TTL` (24 h) après sa
  fin. Une demande `"incognito": true` (mode retiré, d'une page d'avant) est refusée (400) sans rien écrire. Au
  lancement sur Mac, `exclude_from_backup` exclut `jobs/` de Time Machine.
- **Estimation des durées** : `tools/estimate.py` (`predict`, priors par moteur, mesures par `"<moteur>/<modèle>"`
  dans `tools/calibration.json`, filtrées sur la release de sd.cpp installée lue dans `sdcpp/<moteur>/.installed`). Les
  coefficients partent vers l'interface par `/api/status`.

## Pièges de l'interface

- **Brouillon et mémoire de la page** : rien de l'espace privé dans `localStorage`, brouillon compris : une seule
  clé, `qwen-prompt` (`DRAFT_KEY`), où un texte privé n'est jamais écrit, même quand la demande est refusée
  (`tests/ui/brouillons.test.mjs`). La demande gardée par la page (`req` de `pageJobs`, images en data URL, privée
  comprise, pour « Reprendre » et « Relancer ») vit en mémoire de la page seulement, jamais dans `localStorage`
  (`saveOwn` n'écrit que des identifiants).
- **Visionneuse et images affichées** : la visionneuse parcourt `vList`, jamais `histItems` directement (la galerie
  peut être rechargée pendant qu'elle est ouverte). `#paintImg` (image du dessin) passe aussi par `showImage`, avec
  l'image décodée par `toEntry` (`decoded`) ; `tests/check.py` la surveille (`IMAGE_IDS`).
- **Saisie par espace** : la saisie de Créer (texte, images d'entrée, dessin et son tracé) est propre à chaque
  espace, et non plus à chaque onglet. Tout ajout à la saisie qui attend (lecture d'image, sélecteur de fichiers,
  collage, « Éditer », « Dessiner », « Reprendre », envoi d'une demande) note sa liste et son espace avant la
  première attente (`noteInput()`) ; « Relancer », qui ne touche pas la saisie, note l'espace avant de lire les images
  et ne part pas s'il a changé ; sinon un changement d'espace pendant l'attente le fait tomber dans la saisie de
  l'autre espace (une image privée dans la saisie publique) ; à l'arrivée de l'image, il revérifie le dessin
  (`refuseWhileDrawing(list)`).

## Copies entre Python et JavaScript

Registre des constantes et formules recopiées d'un côté à l'autre : une modification se fait des deux côtés
(`CODING_STANDARDS.md`).

- `parts()`, `refPx` et `inputsFor` de `index.html` recopient `predict()` et `ref_px()` de `estimate.py` (jetons de
  16×16 px, arrondi à 32) : formule et coefficients.
- `PREVIEW_EVERY = 5` côté interface égale le défaut `preview_interval` de `build_cmd`.
- La longueur minimale du code privé (`MIN_PRIVATE_CODE`, 8) est aussi vérifiée dans `index.html` (feuilles
  privées).
- Pas une copie : l'estimation de chaque génération de la file (`job_estimate`, pour `queue_entry` et le travail caché
  `ahead`) appelle `estimate.predict` ; l'estimation de « Relancer » (`relaunch`) est approchée (chaque référence
  comptée à la taille de la sortie, pas de `refPx`).

## Tests

`tests/bench.py` (banc : `start`, `call`, `generate`, `wait_job`, `wait_idle`, `wait_until`, `capture_push`),
`tests/fake_sdcli.py` (faux moteur), `tests/test_*.py`, `tests/check.py` (tous les contrôles), `tests/ui/`
(`driver.mjs`, `serve.py`, tests `*.test.mjs`). Commandes dans `CLAUDE.md`.
