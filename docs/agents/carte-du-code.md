# Carte du code

Où trouver quoi dans les deux gros fichiers, pour s'orienter sans les lire en entier (`tools/launch.py` ≈ 110 Ko,
`tools/ui/index.html` ≈ 170 Ko). Repères par noms de fonctions, de constantes et de sections, jamais par numéros de
ligne : `venv/bin/python tests/check.py --map worker` donne la ligne de chaque fonction, classe ou constante dont le
nom contient « worker » (`--map` seul : tout l'index des deux fichiers), puis lire autour. `check.py` échoue si un nom
cité ici entre accents graves n'existe plus dans le code : un renommage met la carte à jour dans le même commit.
L'API locale (routes, champs, codes d'erreur) est décrite dans le README, « Fonctionnement technique » ; les formats
et les raisons dans `DECISIONS.md`.

Sommaire : `tools/launch.py` (le serveur) ; `tools/ui/index.html` (l'interface) ; Mécanismes ; Pièges de
l'interface ; Copies entre Python et JavaScript ; Tests. Pour lire sans `grep` : `check.py --map <nom>` situe une
fonction, `check.py --show <nom>` imprime son corps, `check.py --uses <mot>` liste ses usages dans `tools/`,
`tests/`, le README et cette carte.

```text
navigateur ──HTTP──▶ tools/launch.py ──lance une fois par génération──▶ sdcpp/<moteur>/sd-cli ──▶ PNG
tools/ui/index.html   ThreadingHTTPServer, file + un seul thread worker      (pas de sd-server persistant)
```

## `tools/launch.py` : le serveur (bibliothèque standard + Pillow, `cryptography` pour l'espace privé)

Dans l'ordre du fichier :

- **Constantes et moteur** (en tête) : `ROOT`, `P()` (chemin sous la racine, relu à chaque appel : le banc repointe
  `ROOT`), `MODELS` et `DIFFUSION` (noms des fichiers de modèles, à garder égaux à ceux de `setup.py`), `BACKENDS`
  (options de sd-cli par moteur, réglages Metal justifiés en commentaire), `PLATFORM_BACKENDS`, `PROGRESS_RE` et
  `TAKING_RE` (lecture de la sortie de sd-cli), `MAX_VARIANTS`, `MAX_CAMPAIGN`, `PRIVATE_JOB_TTL`,
  `DONE_LINE` (ligne de fin commune à toutes les générations réussies).
  `record_calib`, `load_config`, `code_version` (commit, date et branche du dossier servi, empreinte `server`
  de `launch.py` et `estimate.py`, relus toutes les `VERSION_TTL` s ; git seulement s'il y a un `.git`, jamais après un
  échec, sauf un délai dépassé ; `S.started` : la même chose au lancement, posé par `main()`), `engine_tag`,
  `default_backend`.
- **Accès** : `ACCESS_FILE`, `ACCESS_COOKIE`, `ENTRY_TOKEN`, `ENTRY_PAGE`, `ENTRY_TTL`, `ENTRY_LOCK`, `ENTRY_USED`
  (entrée à usage unique de `--enter`), `LOCAL_CLIENTS`, `PUBLIC_FILES` (manifeste, icônes, logo, police pixel, service
  worker, servis sans cookie), `LOGIN_PAGE`, `LOGIN_MAC` (phrase de l'ordinateur, à la place de `<!--mac-->` pour une
  requête `_local`). Plus bas : `normalize_code`, `access_token`, `read_access_code` (lecture et validation, sans
  création ; aussi pour `tests/run_tests.py`), `load_access_code` (création exclusive en 0o600 ; un fichier illisible
  n'est jamais écrasé ; un fichier vide ou trop court relu 2 s par `wait_access_code` avant d'être remplacé : un autre
  lancement l'écrit peut-être), `setup_access` (code et empreinte posés dans `S` par `main()`, avec ou sans `--lan` ;
  arrêt sur un fichier illisible, ou encore vide sous un autre lancement : `AccessPending`), `access_cookie_header`
  (cookie posé par `/api/login` et `/entrer`), `write_owner_only` (fichier en 0o600 dès sa création, remplacement
  atomique), `make_entry` (jeton de 128 bits et page de redirection),
  `open_entry` (le navigateur ouvre le chemin de la page, jamais l'adresse au jeton), `open_browser` (au lancement :
  `open_entry`, ou l'adresse simple si la page ne s'écrit pas), `remove_entry` (un fichier qui résiste reste, sans
  erreur), `use_entry_token` (sous `ENTRY_LOCK` : bon jeton de moins de `ENTRY_TTL` s effacé avec sa page, jeton périmé
  effacé, mauvais jeton sans effet ; jeton servi refusé même si son fichier reste, `ENTRY_USED` ; âge lu sur le fichier
  ouvert), `cookie_value` (un cookie de l'en-tête, découpé à la main, pour `_allowed` et `_private_token`),
  `lan_address`, `tailscale_hosts`, `tailscale_serve_url`.
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
- **Espace privé** (`private/`) : constantes `PRIVATE`, `PRIVATE_COOKIE`, `PRIVATE_IDLE`, `PRIVATE_LOCK` (un `RLock`),
  `REKEY`, `META_TMP`, `SCRYPT_N`, `HAVE_CRYPTO` ; clés : `read_space`, `code_key`, `write_space`, `open_space` ; mise
  sur disque : `sync_fd`, `write_synced`, `sync_dir`, avec les droits 600 et 700 de `open_private` et `private_dir` ;
  chiffrement par fichier : `file_key`, `seal`, `unseal` ; images : `store_private`, `read_private`, `private_items`
  (fiches déchiffrées de la pile ou des tirages privés, séparés par la marque « pile » de la fiche, la plus récente
  d'abord), `space_public` (clé de la session encore celle de l'espace, sinon `StaleKey`), `replace_synced` (fichier
  temporaire mis sur le disque puis `os.replace`), `sort_private` (Garder : fiche rescellée sans la marque par
  `META_TMP` puis `os.replace` ; Jeter : `remove_private_item`, dossier renommé en dossier caché, puis supprimé, comme
  `/api/private/delete` ; sous `PRIVATE_LOCK` après `finish_rekey()`) ; prompts privés : `private_prompts`
  (`private/prompts`, scellé à l'étiquette `prompts`) ;
  changement de code : `rekey_space` (tout dans `private/.rekey/`, bascule par `os.replace` de `space.json` ; restes
  `prompts.tmp` et `META_TMP` d'une panne supprimés d'abord, scellés avec l'ancienne clé) et `finish_rekey` (termine ou
  abandonne un changement interrompu, au démarrage et sous `PRIVATE_LOCK` avant toute ouverture ou écriture) ;
  `private_code_error`.
- **Galerie, pile et journal** : `input_files`, `save_inputs` (entrées copiées vers `outputs/.inputs/<image>/`),
  `PILE` (`outputs/.pile/`, images à trier), `JOB_ID_RE`, `image_in` (nom validé dans un dossier), `output_path` (un
  tirage), `pile_path` (une image de la pile), `image_path` (l'un ou l'autre : image, vignette et entrées servies),
  `on_image` (lecture d'une image par `image_path`, cherchée une seconde fois si elle vient d'être gardée),
  `JOURNAL_LOCK` (un `RLock` : journal, tri, lecture des tirages et de la pile), `journal_line` (une ligne lue, ou
  illisible : même jugement à la lecture et à la réécriture), `journal_entries`, `append_journal`, `to_pile` (fin
  d'une génération normale : PNG du dossier de travail vers la pile, sous `S.turn` contre une annulation, puis ligne
  du journal et entrées, d'un bloc sous `JOURNAL_LOCK` ; PNG et journal en 0o600), `delete_output` (effacement complet
  : `delete_extras` (miniatures et entrées), dossier de travail et lignes du journal par `drop_from_journal`, réécrit
  dans un fichier temporaire puis remplacé, et le PNG en dernier, seulement si tout le reste est parti, renommé en nom
  caché avant tout effacement et rendu à son nom si une pièce résiste ; `restore_hidden_images` au démarrage ; une
  pièce qui résiste n'arrête pas les suivantes), `SORTS` et `sort_image` (Garder, Jeter, Supprimer, d'un bloc sous
  `JOURNAL_LOCK` : le premier geste arrivé l'emporte), `read_inputs`, `images_in` (PNG d'un dossier croisés avec le
  journal), `history()` (les tirages), `pile()`, `thumb_jpeg`, `thumbnail` (`outputs/.thumbs/` ; mise en place sous
  `JOURNAL_LOCK`, jamais pour une image déjà jetée).
- **État** : `class State`, instance `S` (moteur, modèle, générations en mémoire `S.jobs`, file `S.pending` (liste des
  générations en attente dans l'ordre de calcul, seule source de l'ordre) protégée avec `S.current` par la condition
  `S.turn`, lots `S.lots`, génération en cours `S.current`, sessions privées `S.private_sessions`, noms `S.lan_hosts`
  et `S.https_hosts`, compteurs `S.rev` de la pile et des tirages de chaque espace, `rev` de `/api/status`).
- **Préparer et lancer une génération** : `data_url_bytes`, `write_data_url` (PNG ou JPEG écrit tel quel, autre
  format converti en PNG : sd-cli ne le lirait pas), `image_size`, `build_cmd` (ligne de commande de sd-cli ; aperçu
  tous les `preview_interval` pas), `latest_preview`, `start_job` (passage « en cours » : par `worker()` sous `S.turn`,
  et par `tools/calibrate.py`, qui appelle `run_job` hors de la file), `run_job` (lit
  la sortie ligne à ligne : étape, phase, durées pour la calibration ; range l'image dans la pile par `to_pile`),
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
- **HTTP** : `class Server` (file de 128 connexions : la galerie en ouvre une par miniature ; `handle_error` : une
  connexion coupée, `cut_connection`, donne une ligne neutre, sans pile d'appels), `class H` : `log_request` (n'écrit
  que les requêtes en erreur), `log_message` (tait les routes de `QUIET_ROUTES` d'après leur chemin, par
  `quiet_request`), `_send` ; contrôles dans l'ordre `_host_ok` (liste blanche de `Host`), `_post_refused` (POST :
  `Sec-Fetch-Site`, `Origin`, `Content-Type: application/json`), `_allowed` (tout appareil, le Mac compris, présente le
  cookie d'accès) ; `_proxied`, `_local`, `_secure` (espace privé : adresse source locale et `Host` local ou nom HTTPS
  de `tailscale serve`) ; sessions privées : `_private_token`, `_private_session`, `_in_private` (l'appareil est dans
  l'espace privé : session et requête sûre ; espace de `/api/status`), `_send_private`, `_open_session` ; routes
  privées : `_private_get`, `_private_post` ; `_send_login` (page du code), `_enter` (`GET /entrer`, après `_host_ok` et
  avant `_allowed`, `_local` seulement ; refusée, un navigateur déjà connecté est renvoyé vers `/`) ; toutes les autres
  routes : `do_GET`, `do_POST` (une suite de `if path == …`).
- **Démarrage** : `exclude_from_backup` (Mac : `jobs/` hors de Time Machine), `setup_state`, `restrict_new_files`
  (masque 0o077 posé en tête de `main()` et de `tools/calibrate.py` : tout fichier créé ensuite, sd-cli compris, pour le
  seul compte du serveur), `close_folders` (dossiers du serveur créés avant le masque, fermés en 0o700 au lancement),
  `main()` (options ; `--enter` : `open_entry` puis sortie, sans serveur ; code d'accès par `setup_access` à chaque
  lancement, `--lan`, Tailscale, ménage de `jobs/`, PNG cachés rendus par `restore_hidden_images`, threads ; navigateur
  ouvert par `open_browser`, hors `--no-browser`). Le banc n'exécute pas `main()` : il pose lui-même `S.access_code`
  (`ACCESS_CODE`), et `call()` envoie le cookie d'accès pour le Mac aussi ; le pilote d'interface connecte chaque page
  de `chrome.phonePage()` au banc direct (un banc relayé : `bench.login(page)`) ; `bench.enter()` du pilote demande à
  `tests/ui/serve.py` un jeton et sa page, comme `--enter`. `tools/make_shortcut.py` :
  `mac_command` (texte de `Chambre noire.command` : interface déjà lancée, `launch.py --enter`), `mac`, `windows`.

`tools/estimate.py` : modèle de coût des durées (`predict`, `ref_px`, `prefix_cache`, `make_sample`, `class Store`
pour `tools/calibration.json`).

## `tools/ui/index.html` : l'interface (HTML, CSS et JavaScript, sans dépendance ni build)

Le fichier se lit par ses commentaires d'en-tête `/* ---…` (CSS) et `// ---…` (JavaScript). Un petit premier bloc
`<script>` dans `<head>` pose `html.lite` (téléphone : effets allégés) ; tout le reste du JavaScript est dans le
dernier bloc, après le HTML.

- **CSS** : sections « jetons » (lumière inactinique ; `html.priv` : lumière verte), « fond », « surfaces mates »
  (classe `mat`), « barre du haut », « barre d'onglets », « panneaux du bas », « compositeur » (champ replié, grille des
  réglages `setgrid`), « panneau Réglages », « images d'entrée (Labo) et Dessiner », « visionneuse plein écran »,
  « bouton Avant » (cadre `.bfr`, bouton `.bbtn`),
  « carte en cours » (`runcard`, classe `behind` derrière une pile non vide), « pile du Labo » (cartes `pcard`,
  bandeau Annuler `undo`), « liste de la file (feuille de la file du Labo) » (cartes de la file), « prompts
  enregistrés », « espace privé », « messages et confirmations »,
  « typographie » (police pixel `--pixel`, chasse fixe `--mono`, déclaration `@font-face`), « téléphone (html.lite) ».
- **HTML** : en-tête (logo, nom, lampe d'état `#lamp`, qui ouvre `#engineSheet`, puis « Sortir » `#privExit` dans
  l'espace privé) ; onglets `#pane-labo` (Labo : la
  pastille « +N en attente » `#queueChip`, la carte en cours `#runCard` (cadre `#runFrame` et son canevas
  `#revealCanvas`, rang dans un lot `#lotBadge`, étape `#runStep`, phase `#runPhase`, fin prévue `#runEta`, annulation
  `#runCancel`, prompt `#runPrompt`, avancement `#runBar`), la pile `#pile`, ses boutons ✕ `#pileNo` et ✓ `#pileYes`,
  son compte `#pileCount`, l'état vide `#pileEmpty` ; dessous, le compositeur `#composer` (classe `folded` : replié
  en sa ligne `#composerLine`, nombre d'images `#lineCount` ; déplié : poignée `#composerGrab`) : images d'entrée
  `#refs`, vignettes `#inThumbs`, ajout `#inDrop` et son champ `#inFiles`, bouton Dessiner `#drawBtn` (choix d'une image
  `#drawFile`, explication `#drawHint`), zone de dessin `#paintWrap` et `#paintCanvas`, masque ou annotation
  `#mask_mode`, interrupteur Campagne `#campSwitch`, champ unique `#prompt`, grille des réglages `#setGrid` (une case
  `data-set` par réglage, qui ouvre `#setSheet`), Prompts `#promptsBtn`, bouton « Révéler » `#go` (`#goLabel`,
  estimation `#goEta`) ; classe `drawing` quand le dessin est actif : le champ prend toute la hauteur, la pile
  s'efface, sauf à partir de 1024 px ; classe `dropping` pendant le survol d'un fichier), `#pane-tirages` (Tirages,
  grille `#histGrid`) ; barre d'onglets `#tabbar` (icônes en pixels ;
  onglet Labo : nombre `#runCount`, anneau `#runRing` ; en bas, dans la barre du haut à partir de 1024 px) ; visionneuse
  `#viewer` (`#vSort` : Garder et Jeter une image de la pile ; cadre du bouton Avant `#vBefore` et son image
  `#vBeforeImg`, sur l'image `#vImg` ; à partir de 1024 px, une grille : image à gauche,
  panneau `.v-panel` en colonne à droite) ; bandeau Annuler `#undoBar` ; images d'entrée `#iv` ; feuilles `.sheet` :
  `#askSheet`, `#setSheet`,
  `#engineSheet` (feuille de la lampe : état `#engineFacts`, « Ouvrir depuis le téléphone » `#phone` sur le Mac
  seulement, ligne « Espace privé » au cadenas `#privEntry`, journal `#log`), `#lotSheet`, la file `#fileSheet`
  (`#queueNote`, `#queueList`), `#promptSheet`, `#promptEditSheet` et
  celles de l'espace privé (`#privCreateSheet`, `#privUnlockSheet`, `#privCodeSheet`…).
- **JavaScript**, sections dans l'ordre :
  - « valeurs fixes » : `log` et `renderLog` (journal du panneau Moteur, `logLines` : une ligne écrite dans l'espace
    privé en sort à la sortie), `RATIOS`, `RES`, `STEPS`, `PREVIEW_EVERY`, `MAX_REFS` ; `applyEstimates` ; estimation
    (`refPx`, `inputsFor`, `parts` : copies de `estimate.py`) ; réglages `opt` (`localStorage` `qwen-opt`),
    `refreshChoices` (exemple du champ, `PLACEHOLDERS`, grille `#setGrid`) ; nature de la demande lue dans la saisie :
    `inputKind` (`t2i` sans image d'entrée, `edit` avec, `mask` dessin actif : `drawOn`), `singleImage`, `campaignShown`
    (interrupteur proposé à partir de 2 images), `inCampaign`, `variants` ; brouillon unique `qwen-prompt` (dans
    `init` : reprise une fois des anciens `qwen-<onglet>_prompt`).
  - « onglets & statut » : `TABS`, changement d'onglet (`mode`, `goTab`, `showLabo`), `tabSwipe` (glissement
    d'onglet, jamais depuis le champ de création déplié ni la pile) ; « panneaux du bas » : `openSheet`, `closeSheet`
    (un seul ouvert, `openedSheet`) ; `refreshStatus()` (interroge `/api/status` toutes les 5 s, 2 s tant que la file
    n'est pas vide ; met à jour `queueState`, la lampe par `setLamp` (classes `ok`, `busy`, `err`, aucune pendant la
    connexion), l'onglet Labo, la carte en cours, la file et l'espace privé par `applyPrivate`, et le panneau Moteur,
    version servie comprise : `fmtVersion`, `staleServer`) ; sur un 401 (code d'accès redemandé), `reauth` recharge
    une fois la page sur `/?reauth`, la page du code (`reauthing`, et l'adresse empêchent une boucle ; `dropReauth`
    retire `?reauth` par `history.replaceState` au premier état lu, pour qu'un 401 plus tard recharge de nouveau).
  - « champ de création replié ou déplié » : la règle du téléphone ci-dessous tient l'état voulu (`composerOpen`) ;
    `applyComposer` le montre, sauf à partir de 1024 px (`WIDE`, deux colonnes) où le champ reste toujours déplié, et
    le reprend quand la fenêtre repasse sous 1024 px. `setComposer`, `openComposer`, `foldComposer`, `followLabIdle`
    (appelé par `renderRunCard` : déplié d'office quand le Labo n'a plus rien à trier ni en cours ; replié quand il a de
    nouveau quelque chose si on n'y a pas touché depuis, `autoOpen` ; `labIdle`, remis à `null` par `changedSpace`),
    `foldGesture` (poignée), toucher sur la pile (`.pilezone`, image comprise, hors ✓, ✕ et autres boutons), dépôt
    d'une image sur le champ, replié compris (`dragover`, `drop` ; surbrillance `dropping`, dessinée à partir de
    1024 px, où le champ est toute la colonne de droite ; un fichier lâché ailleurs est ignoré par les écouteurs
    `dragover` et `drop` de la fenêtre, pour que le navigateur ne l'ouvre pas à la place de l'interface) ; replié aussi
    après « Révéler » ; `showLabo('composer')` le déplie. Hauteur de l'image de pile `--pimg-h` : ✓ et ✕ restent
    au-dessus de la ligne repliée ; à partir de 1024 px, la hauteur de la colonne de gauche (`--col-h`), section CSS
    « grand écran ».
  - « images », « dessin » : `toEntry`, `addInputFiles` (choix, dépôt et collage, écouteur `paste` du Labo),
    `refuseWhileDrawing` (ajout refusé pendant le dessin, saisie affichée ou mise de côté), `noteInput` (saisie visée
    par un ajout, notée avant toute attente), `renderInputs` (images d'entrée de la saisie, `inputImages`, puis
    `renderDrawing` : bouton Dessiner et zone de dessin, image du dessin `#paintImg` par `showImage`),
    `drawCanvasFor` (le tracé appartient à `drawFor`, l'image pour laquelle il a été commencé : gardé quand on éteint
    Dessiner, effacé avec son image), `drawWith` (une image seule dans la saisie, dessin actif, tracé vierge),
    `exportMask`, `paintedReference`.
  - « requête & loader » : `requestBase` (champs qu'aucun réglage ne fixe, communs avec « Relancer »), `buildRequest` ;
    « messages et confirmations » : `toast` (un message `go` touché mène au Labo par `toLabo`, comme une notification
    touchée, application ouverte ; `toLabo` laisse ouverte une feuille qui a une saisie en cours, `sheetTyped` : un
    événement `input` de l'utilisateur dans un champ de texte (`TEXT_FIELD`, pas un interrupteur) de la feuille depuis
    son ouverture, remis à faux par `closeSheet`), `ask` et `answer` (feuille `#askSheet`, jamais `confirm()`).
  - « affichage des images » : `showImage` (toute image qui change d'adresse : vidée, puis remplie une fois l'image
    chargée et décodée à part, miniature d'abord ; `img.want` : adresse attendue, une image arrivée trop tard est
    ignorée ; `keep` : l'aperçu d'avant reste jusqu'au suivant ; `once` : aperçu servi une fois ; `decoded` : image déjà
    décodée à part (image du dessin, lue par `toEntry`), posée tout de suite sans passer par `ready` ; `fit`, `dims` :
    miniature des visionneuses à la taille de l'image complète, par `fitThumb`, en unités de la scène `cqw`, `cqh`),
    `preload` et `ready` (les 10 dernières images décodées : miniatures des voisines de la visionneuse, image complète
    de la suivante dans le sens du parcours `vStep`, première image d'entrée ; `refused` : adresse refusée, entrée
    `gone`, pendant « Sortir » et, pour une adresse `/api/private/`, hors de l'espace privé ; `unready` : entrée
    retirée de `ready`, évincée, illisible ou oubliée, son image vidée, à son arrivée si elle chargeait encore ; un
    aperçu de la carte en cours quitte `ready` dès sa demande, voir `revealPreview`),
    `clearImage`, `clearImages` (images d'un contenu vidées avant qu'il soit remplacé ou vidé : pile, Tirages, « Voir
    le lot », file, miniatures d'entrée de la visionneuse et de la saisie ; une image détachée ne garde pas son adresse
    privée jusqu'au ramasse-miettes), `abortPrivateLoads` (chargements privés en route abandonnés, aussi avant la
    fermeture de la session
    par « Sortir », et ceux d'une génération finie avec un préfixe d'adresse : `secretLoads`, même évincés de `ready`,
    marqués `gone` : une image qui en attendait un, même détachée, ne reçoit rien), `forgetPrivateImages` (sortie de
    l'espace privé : images privées et aperçus affichés, attendus ou chargés en avance, chargements en cours
    abandonnés, et tout lien vers une route privée avec son nom `prive_…`). Ne
    jamais réaffecter `src` d'une image visible à la main : elle garderait l'image d'avant à l'écran jusqu'au chargement
    de la nouvelle (`tests/check.py` refuse `$('vImg').src=…` et ses pareilles, `IMAGE_IDS`).
  - « bouton Avant » : `beforeFile` (règle de l'image comparable, seule source : `edit` à une image d'entrée, `mask` →
    `init.png`), `beforeShown` (bouton montré, image privée comprise, masqué sur une image privée pendant « Sortir » :
    `leavingPrivate`), `reaimBefore` (cadres revisés : « Sortir » demandé ou refusé, dans `privLock`), `aimBefore`
    (cadre visé sur une image : visionneuse dans `openViewer`,
    carte du dessus dans `renderPile`, son entrée chargée en avance), `placeBefore` (cadre posé sur le contenu affiché
    de l'image produite, étirée ou entière selon `BEFORE_STRETCH`), `holdBefore` et `dropBefore` (appui et relâché,
    `beforeHeld`, `blur` de la fenêtre ; aussi Espace tenue, raccourcis du PC plus bas), `armBefore` (bouton
    `BEFORE_KNOBS`, Pointer Events), `beforeSizes` (cadres recalés quand une taille change).
  - « générations de la page, carte en cours et file » : `pageJobs` (générations lancées par cette page), `ownIds` et
    `saveOwn` (`localStorage` `qwen-own`), `isActive`, `isCampaignLot`, `lotOf`, `progress` (étape, phase, temps
    restant d'une génération de la page), `pageItem` (image d'une génération finie de la page : vrai mode et images
    d'entrée de son suivi ; cases d'un lot), `spaceNow` (état de l'espace pour l'onglet ; `entryFrac`, `firstWait`,
    `ringOffset`), `renderRunTab` (nombre de la pile et anneau de l'onglet Labo), pile : voir plus bas ; carte en
    cours : `runNow` (ce qu'elle montre : génération de la page qui tourne, sinon d'un autre appareil, sinon la
    prochaine de la page, sinon l'attente d'une génération cachée de l'autre espace), `renderRunCard` (sur le dessus
    pile vide, sinon `behind` ; `shown` : la génération de la page montrée ; `lotRankLabel` ; annulation confirmée par
    `ask`, de la génération de la question, rien pendant « Sortir » ; « Déjà terminée » selon le statut que rend le
    Mac, « Mac injoignable » ou l'erreur sinon), `openQueue` (feuille
    de la file, pastille `#queueChip`), révélation en pixels sur le canevas : `reveal`
    (génération révélée, couleurs des carrés lues par `cssRgb`, dernier aperçu ; `blankReveal`), `startReveal` et
    `drawNoise` (carrés au hasard avant le premier aperçu,
    allégés en `html.lite`, immobiles en `prefers-reduced-motion`), `revealPreview` (aperçu décodé par `preload`,
    servi une fois : retiré de `ready` dès sa demande, rien ne l'évince ; pas montré, il passe par `unready`, et
    l'aperçu que la mosaïque lâche, remplacé ou à
    `clearReveal`, est vidé) et `drawMosaic` (blocs de `REVEAL_COARSE` à `REVEAL_FINE` px selon step / total, sans
    lissage),
    `sizeReveal`, `redrawReveal`, `clearReveal`, `lite` (canevas vidé : fin, changement de génération, sortie de
    l'espace par `forgetPrivateImages`) ; `notifyDone` (message « Image prête »,
    « Lot prêt » hors du Labo, `toast(…, go)`), `renderQueue` (file de l'espace en cartes, feuille ouverte seulement :
    `queueCards` regroupe les entrées d'un lot, `queueCard` dessine
    une carte, `lotCases` ses cases (`lotCancels` : rangs annulés pendant la vie de la page), `lotSubs` ses lignes une
    fois dépliée (`openLots`) ; `lotLabel` : « N variantes » ou « Campagne · N photos » ; `qbtn` : bouton d'annulation
    ou de « Passer en tête », chemin fixé à l'affichage ; `hhmm` : heure de fin, `resLabel` : résolution), `ownOf`
    (ligne de `queue` → génération de la page, par identifiant), `ofSpace`, `firstActive` (celle qui
    tourne, sinon la prochaine dans l'ordre de calcul) et `nextActive` (la même, parmi les générations de l'espace
    affiché), `track` (suit une génération, avec sa demande `req` si la page l'a envoyée, un objet par lot, en mémoire
    de la page seulement ; `pollJobs` chaque seconde ; une privée « inconnue » quitte la page sans message), `finish`
    (fin d'une génération : ses aperçus en route abandonnés, publique ou privée, avant l'oubli d'une privée, la pile
    relue, l'échec gardé pour sa carte, l'annulée retirée), `drop` (retire une
    génération de la page) ; bouton `#go` ; reprise : `followQueue` (suit des entrées de la file), `resumeOwn`
    (générations normales de
    ce navigateur, après un rechargement et au retour dans l'espace public), `resume`, `adoptPrivate` (dans l'espace
    privé, toutes les générations privées actives de la file, `adopted` : pas lancées par la page, qui ne les fait pas
    oublier).
  - « pile du Labo » : `pileItems` (la pile lue de l'espace, `pileApi` : routes de l'espace où le geste commence ;
    images marquées `pile`), `loadPile` (au chargement, au changement d'espace, quand `rev` change : `pileRev`, retenu
    après une lecture réussie, et à la fin d'une génération de la page ; `pileSeq` : une réponse dépassée est ignorée ;
    `pileRead` : l'état vide n'est montré qu'une fois la pile lue ; oublie les générations finies de la page dont
    l'image a quitté la pile, sauf pendant leur lot), `pileView` et `pileSize` (sans les images dont le tri est en
    cours, `sorting`, avec leur génération de la page `pageOf`), `pileFails` (échecs de la page, en tête),
    `renderPile` (rien pendant « Sortir », `exiting()` ; carte du dessus et deux devinées dessous : `pileCard`,
    `failCard`, chacune marquée par `pileTag` ;
    état vide, compte, pastille de l'onglet ; redessinée seulement si elle change, `pileShown`, les images des cartes
    retirées vidées par `clearImages`), `topEntry` (ce que montre la carte du dessus, retrouvé par son nom), `posed`
    (image de la pile triable : miniature ou image à l'écran, ou chargement fini en échec ; jamais pendant le
    chargement), `sortTop` (✓, ✕ et balayage ; rien pendant « Sortir », `exiting()`, ni tant que l'image d'avant est à
    l'écran, `beforeHeld`, ni sur une carte masquée, `shownTop`, ni sur une image pas `posed` ;
    `flyOut`, un départ à la fois : `flying`, vrai jusqu'au tri ou au retour de la carte, même si la pile est
    redessinée entre-temps, `flight` le départ en cours, que `landFlight` annule à l'appui sur « Sortir » et à la sortie
    de l'espace (`changedSpace`) ; verrou de tri qui suit ce que l'œil voit : toute carte arrivée sur
    le dessus (tri d'ici, nouvelle image, tri ailleurs, Annuler, carte d'échec : `pileTop` change dans `renderPile`)
    attend d'être vue `SORT_GAP` ms, `holdTop`, `topHeld` (pile seulement, `sortBusy`) ; dans la visionneuse, toute
    image de la pile de même (ouverture, pas, tri : `openViewer`), `holdSort`, `sortHeld` ; l'attente commune,
    `afterSeen`, suit ce que
    montre la vue (`topView` : Labo sans visionneuse ni feuille, carte pas masquée, image posée ; ou l'image
    de la visionneuse) et repart de zéro quand elle change ; `releaseSort` les lève à l'appui sur « Sortir » et à la
    sortie de l'espace), `pileSwipe`
    (balayage de
    la carte du dessus par Pointer Events, doigt et souris : seuil au tiers de la largeur ou geste vif ; `swiped` :
    la fin d'un balayage n'ouvre pas la visionneuse, oublié au prochain appui dans la zone de la pile),
    `sendSort` (envoi de Garder ou Jeter, « Déjà triée » sur un 404 de Garder), `keepItem`, `discardItem` (Jeter :
    bandeau `#undoBar`, `discarding`), `commitDiscard` (à la fin du bandeau, `DISCARD_MS`, ou au Jeter suivant ;
    abandonné si l'espace où il a commencé est fermé ou en train de l'être, `leavingPrivate` ; `privLock` annule
    un Jeter privé en attente dès l'appui sur « Sortir », avant que les images privées soient refusées : la carte
    revient avec son image), `undoDiscard`, `sortFromViewer` (Garder et Jeter de la
    visionneuse, puis l'image suivante ; rien pendant « Sortir », ni tant que l'image d'avant est à l'écran,
    `beforeHeld`, ni sur une image pas `posed`). Garder et Jeter visent
    une image par `pileKey` (nom, identifiant d'une privée), jamais par l'objet affiché.
  - « notifications » : `pushSubscribe`, `askNotifications`.
  - « prompts enregistrés » : `promptsApi` (routes de l'espace affiché), `prompts`, `openPrompts` (ouverte par le
    bouton, filtre `promptUsage` sur la catégorie de la saisie, `inputKind`), `renderPrompts`, `usePrompt`,
    `savePrompt`.
  - « galerie et visionneuse » : `histItems`, `vList` (ce que parcourt la visionneuse : les Tirages ou la pile),
    `loadHistory` (à l'affichage des Tirages, et quand `rev` change pendant qu'ils sont affichés : `histRev`, retenu
    après une lecture réussie ; `histAsk` : rev de la lecture en cours, pas relancée pour le même ; `histSeq` : une
    réponse dépassée est ignorée ; rien pendant « Sortir » ; visionneuse ouverte recalée sur la liste relue),
    `renderGallery` (redessinée seulement si les tirages changent, `histShown` ; état vide avec le logo et « Aller au
    Labo »), `openViewer`, `stepViewer`,
    `closeViewer` et `emptyViewer` (contenu vidé après le fondu de fermeture, ou tout de suite à la sortie de l'espace
    privé), raccourcis du PC (écouteur `keydown` juste avant celui de la visionneuse : → et ← sur la pile par
    `sortTop`, Z et Ctrl/⌘ + Z par `undoDiscard`, Ctrl/⌘ + Entrée dans `#prompt` par `#go` ; rien pendant une saisie,
    une feuille, la visionneuse (sauf Espace) ou les images d'entrée, ni sur une carte d'échec ; une touche répétée ne
    trie rien, Entrée répétée sur un bouton marqué `data-sort` comprise ; carte du dessus affichée : `shownTop` ; Espace
    tenue :
    `holdBefore` du cadre de la visionneuse ou de la carte du dessus, `holder` à `'key'` (pas sur un appui du pointeur
    en cours), et `keyup` par `dropBefore`,
    sans défilement ni bouton activé ; champs : `FORM_FIELDS`), gestes : `zoomable` (pincer, molette, glisser ; son
    image avant reçoit la même transformation, `twin` ; `resetZoom` pour la visionneuse, `resetInputZoom` pour les
    images d'entrée).
  - « partager et copier » ; « images d'entrée » : `openInputs`, `showInput`, `closeInputs` et `emptyInputs`,
    `inputAction`, `addEditImage` (« Éditer ») et `drawFrom` (« Dessiner », confirmation s'il y avait des images) ;
    « Reprendre » : `resumeFrom` (saisie remplacée, confirmation si elle n'est pas vide), `resumeImages` (images
    d'entrée selon le mode, `RESUME_FILES` : demande gardée `req`, sinon galerie), `canResume` (bouton `#vResume`),
    `settingsFor` (format, résolution et étapes qui redonnent l'image) ; « Relancer » (visionneuse `#vAgain`, carte
    d'échec `data-again`) : `keptRequest` (demande gardée : l'image seule), `againFrom` (reconstruite de
    l'image sinon), `canAgain`, `relaunch` (graine et espace du moment ; estimation), puis `launch` (envoi commun, rien
    d'une demande privée pendant « Sortir », avec
    « Révéler » : suivi, `accepted` (vidage de la saisie de « Révéler », champ replié), message, haut du Labo), `again`
    (un geste à la fois ; rien pendant « Sortir », `exiting()`, comme « Révéler » `#go`) ;
    actions de la visionneuse : `viewerAction` (comme `inputAction`, `viewerShare`, `viewerCopy`, `downloadLot` et les
    liens `#vDl`, `#ivDl` : rien pendant « Sortir »), `removeFromViewer`, `lotMembers`, `deleteItem` (« Supprimer » un
    tirage ; « Sortir » revérifié après la confirmation), `forgetResult`.
  - « espace privé » : `privState`, `inPrivate()`, `applyPrivate`, `changedSpace` ; saisie propre à chaque espace :
    `asideInput` (saisie de l'autre espace, en mémoire de la page), `erasePrivate` (« Sortir » demandé), `readInput`,
    `putInput`, `swapInput`, `emptyInput` (vidage après « Révéler », dans l'espace d'où la demande est partie) ; un
    ajout d'image asynchrone (Éditer, Dessiner) va dans la saisie de l'espace où il a commencé. `openPrivSheet`,
    `privCreate`, `privUnlock`, `privLock` (un second appui pendant l'attente ne fait rien ; vignettes privées des
    Tirages pas encore chargées vidées avant l'envoi ; sortie appliquée dès la réponse du Mac, ou son refus clair,
    `lockAccepted`, rien de redessiné ni d'annoncé si la page a été fermée entre-temps : `spaceEpoch` écarte une réponse
    de `/api/status` demandée avant ; `leavingPrivate` (`exiting()` : dans l'espace, sortie en attente) : aucune image
    privée ni aperçu demandés ou posés, quel que soit le chemin qui redessine (`preload` les refuse : entrée `gone` ;
    `renderQueue`, `renderGallery`, `openLot`, `openViewer` ne redessinent rien, la seconde tentative d'une vignette
    privée des Tirages est abandonnée, aussi après la sortie, comme celle de toute vignette retirée de la grille
    entre-temps), aucune pile ni Tirages privés lus ou dessinés
    (`loadPile`, `loadHistory`), même partis avant l'appui, ni pile redessinée à la réponse d'un tri (`sendSort`),
    aucune génération privée de la page interrogée (`pollJobs`) ni suivie ou adoptée, même par un suivi parti avant
    l'appui (`followQueue`, `adopted`), ni Jeter privé envoyé pendant la fermeture), `privChangeCode`, `privReset` ;
    marque de l'onglet (`RELOCK_MARK`, `markRelock`) posée dès que la page sait l'espace ouvert (code accepté par
    `privPost`, état lu qui le dit ouvert dans `refreshStatus`), copiée en mémoire (`marked`) et levée par `liftRelock`
    quand l'état lu le dit fermé (fermeture par le Mac, espace supprimé), quand « Sortir » est accepté ou quand le Mac
    accepte le reverrouillage ; fermeture de la page (`pagehide` : `pageHidden` jusqu'à `pageshow`, `hides` compté) dans
    l'espace, pendant une entrée (`entering`) ou marquée (`marked`) : code en route annulé (`entryAbort`), verrouillage
    envoyé (`keepalive`), puis tout le privé effacé comme à « Sortir » (`closePrivateHere` : `erasePrivate`, `relock`,
    `applyPrivate` ; `hiding` : sans relecture publique, refaite par `pageshow`), `hidInPrivate` noté, champs de code
    vidés (`clearPrivCodes`, champs `PRIV_CODES`, aussi à `pageshow`) et marque reposée (filet) ; page restaurée par «
    Retour » (`pageshow`, `persisted`) : même sortie si elle n'a pas eu lieu, message, puis `relock` : `refreshStatus`
    reverrouille d'abord par `relockSpace` (une seule promesse en route, `relocking` ; `LOCK_POST`, `fetch` et non
    `postJson`, encore indéfini à la première interrogation ; `lockAccepted` : oui du Mac, 4xx sauf 401, ou 503 « espace
    privé indisponible » ; une coupure, un autre 5xx ou un 500 font réessayer ; 401, d'un ancien serveur pas encore
    relancé seulement (le Mac admet le verrouillage sans le code d'accès) : `reauth`, et `LOGIN_PAGE` renvoie le
    verrouillage d'un onglet marqué) et n'applique aucun état
    tant que le Mac ne l'a pas accepté (un état reçu alors que `relock` est devenu vrai est relu) ; page rechargée
    (onglet tué compris) : `relock` lu dans la marque au chargement, même parcours (la reprise du chargement, `resume`,
    attend aussi le reverrouillage, et reprend après le premier accepté : `resumeLater`). `relock` et la marque ne se
    lèvent que par `liftRelock`, jamais pendant une fermeture (`pageHidden`). Un code retapé (`privPost`, création ou
    entrée) attend d'abord le reverrouillage restant, puis `entering`, du départ du code jusqu'à l'état relu, empêche
    d'en lancer un ; il lève `relock` ; la page fermée depuis (`hides`), il renvoie faux et demande de retaper le code.

Libellés visibles et code (la spec et les tickets parlent avec les libellés de l'écran) : visionneuse « Éditer »,
« Dessiner », « Reprendre » (texte, images d'entrée, dessin et réglages : `resumeFrom`), « Relancer » (`againFrom`) et
« Supprimer » → `viewerAction('edit' | 'mask' | 'resume' | 'again' | 'delete')` ; « Garder » et « Jeter » → ✓
`#pileYes` et ✕ `#pileNo`, ou balayage de la carte (`pileSwipe`), puis `sortTop` ; dans la visionneuse, `sortFromViewer`
; « Annuler » → `undoDiscard` ; carte d'échec, « Relancer » → `data-again` dans l'écouteur de `#pile` ; « Annuler » de
la carte en cours → `#runCancel` ; « +N en attente » → `openQueue` ; ligne « Espace privé » de la feuille de la lampe
→ `#privEntry`, « Sortir » → `privLock` ; lampe d'état du haut → `#lamp`.

Deux boucles suivent les générations sans se synchroniser : `pollJobs` (`/api/job/<id>`, chaque seconde) et
`refreshStatus` (`/api/status`, toutes les 2 à 5 s). Une réponse de l'une peut arriver avant celle de l'autre :
rapprocher une génération de la file par son identifiant, et traiter un 404 qui précède l'annonce de la fermeture de
l'espace (voir `CODING_STANDARDS.md`).

Fichiers voisins : `tools/ui/sw.js` (service worker : navigation seulement, jamais `/api/*`),
`tools/ui/manifest.webmanifest` et les icônes (installation sur le téléphone) ; `tools/ui/PixelifySans.woff2` (police
pixel du nom et des titres, licence `tools/ui/OFL.txt`), servie sans code d'accès par `PUBLIC_FILES` comme eux ;
`tools/ui/logo.svg` (logo de la barre du haut, de la page du code d'accès et de l'onglet) est la source des icônes PNG,
à régénérer depuis lui s'il change, par Chrome sans écran : `icon-192.png` et `icon-512.png` tels quels (coins
transparents), `icon-maskable-512.png` et `apple-touch-icon.png` (180 px) plein cadre, sans le `clip-path` arrondi ni le
liseré du bord, sans transparence.

## Mécanismes

Le détail de ce que font ces zones ensemble ; les invariants à ne pas casser sont dans `CLAUDE.md`, « Pièges et
invariants ».

- **Une génération** : `worker()` exécute les jobs un par un via `run_job()`, qui construit la ligne de commande
  (`build_cmd`), lit la sortie de sd-cli ligne à ligne et en tire l'étape, la phase et les durées (`PROGRESS_RE`,
  lignes « … completed, taking x s ») qui alimentent la calibration. Les jobs vivent en mémoire (`S.jobs`) et ne
  survivent pas à un redémarrage.
- **Fichiers** : dossier de travail `jobs/<id>/` (images d'entrée, aperçus, `sd-cli.log`, et l'image tant qu'elle se
  calcule ; les 20 derniers gardés au lancement), image finale `outputs/.pile/<id>_<mode>.png` (la pile, à trier),
  une ligne par image dans `outputs/journal.jsonl`. Garder (`/api/keep`) déplace le seul PNG vers `outputs/` (les
  tirages, dont toutes les images d'avant la pile) ; miniatures (`outputs/.thumbs/`) et images d'entrée
  (`outputs/.inputs/<image>/`) sont rangées par nom d'image et ne bougent pas. Les tirages (`/api/history`) et la pile
  (`/api/pile`) sont les PNG de leur dossier croisés avec le journal (`images_in`). Les images d'entrée (`init.png`,
  `ref_N.png`) sont copiées du dossier de travail en fin de job (`save_inputs`, et au démarrage pour les dossiers
  encore présents). Jeter (`/api/discard`, une image de la pile) et Supprimer (`/api/delete`, un tirage) effacent tout
  (`delete_output`), ligne du journal comprise. Toute écriture du journal et tout tri passent sous `JOURNAL_LOCK`
  (`to_pile`, `sort_image`), et chacun augmente `S.rev`. Une génération annulée (en cours ou en file) ne laisse
  rien : `discard_cancelled` supprime son dossier de travail, image commencée comprise. Le statut `cancelled` est posé
  avant que le moteur soit arrêté.
- **Lots** (variantes : `count` de 2 à 4, tous les modes, jamais avec une campagne ; campagne : `campaign`, 2 à 10
  photos avec leurs dimensions, en `edit`) : `expand_request` en tire une demande par image, `/api/generate` une
  génération par demande (`new_job`), reliées par `job["lot"]` (`id`, `rank`, `size`, et `campaign`, le marqueur qui
  distingue une campagne de variantes, posé par `/api/generate` : le mode ne le dit plus) et gardées dans `S.lots`
  même quand une génération privée quitte `S.jobs`. Côté interface, `isCampaignLot` lit le marqueur (un lot d'avant
  lui : campagne s'il est du mode `edit`) pour le titre d'un lot et son repère. Les graines à -1
  sont tirées par le serveur (`draw_seeds`) pour être écrites au journal. Une seule notification par lot (`notify_lot`),
  envoyée par `end_of_lot` depuis le `finally` de `worker()` quand plus aucune génération du lot n'est active ; le lot
  quitte alors `S.lots`, ce qui empêche un doublon quand une génération annulée en file passe ensuite.
- **Notifications** : `notify_job` part de `worker()`, dans un thread, à la fin d'un job hors lot terminé ou en échec,
  vers chaque abonnement de `tools/push_subscriptions.json`. Le service worker (`tools/ui/sw.js`) n'affiche la
  notification que si aucune fenêtre de l'application n'est visible ; touchée, elle ouvre l'application à son adresse
  (le Labo), ou, déjà ouverte, ramène sa fenêtre et lui envoie le message `{go: 'labo'}`, que la page applique par
  `toLabo` sans se recharger (`tests/ui/notifications.test.mjs`). Tester sans réseau : `bench.capture_push()`, ou
  intercepter `requests.post` et déchiffrer avec `http_ece`.
- **Prompts enregistrés** : titre et texte seulement, jamais de réglages ; `used` (secondes) ordonne la liste.
  Choisir un prompt enregistré met à jour son `used`, dans chaque espace. Le banc lit `tools/prompt_types.json` du dépôt
  (pas de repointage). Chaque espace a sa liste : dans l'espace privé, la feuille passe par `/api/private/prompts`
  (`private_prompts`, chiffrée) ; `changedSpace` ferme ses feuilles (confirmation comprise) et vide la liste de l'espace
  quitté ; une réponse reçue après un changement d'espace est ignorée.
- **Interface et serveur** : l'interface suit les générations qu'elle a lancées (`pageJobs`) en interrogeant chacune par
  `/api/job/<id>` chaque seconde, et la file de son espace (`queue` de `/api/status`, entrées produites par
  `queue_view`) toutes les 2 s tant qu'elle n'est pas vide ; la file, la carte en cours et l'onglet ne parlent que des
  générations de l'espace
  affiché (`ofSpace`), le temps d'attente ajoute `ahead` ; après un rechargement, elle se rattache aux
  seules générations normales lancées depuis ce navigateur (identifiants dans `localStorage`, `qwen-own`), et dans
  l'espace privé à toutes les générations privées actives (`adoptPrivate`), avec le prompt complet que donne leur suivi
  (`followQueue`). À la sortie de l'espace privé, `changedSpace` retire de la
  page ses générations privées ; dans l'espace privé, les publiques restent suivies hors de l'écran. Les générations
  finies arrivent dans la pile du serveur (`loadPile`), chaque image d'un lot sur sa carte ; la visionneuse parcourt
  `vList` (les Tirages, ou la pile). Réglages, brouillons de la saisie publique et générations à reprendre dans
  `localStorage` (`qwen-opt`, `qwen-prompt`, `qwen-own`).
- **Contrôle d'accès** : `_host_ok` (liste blanche de `Host` contre le rebinding DNS, noms du Wi-Fi et de Tailscale
  figés au démarrage), `_post_refused` (tout POST : `Sec-Fetch-Site`, `Origin` égal à l'origine du `Host`,
  `Content-Type: application/json` exigé, sinon 403/415), puis `_allowed` (tout appareil, le Mac lui-même et toute
  requête relayée par `tailscale serve` compris, présente le cookie dérivé du code d'accès ; sans lui, 401, et `/`
  sert `LOGIN_PAGE` ; seuls les `PUBLIC_FILES` passent avant ; sans code chargé, rien ne passe ; exception dans
  `do_POST` : `POST /api/private/lock` passe sans le cookie d'accès, après `_host_ok` et `_post_refused`, et ne ferme
  que la session du cookie privé de l'appareil). L'espace
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
  bouton ne le signale à l'arrivée (entrée : ligne au cadenas `#privEntry` de la feuille de la lampe ; sortie :
  `#privExit`), décision du porteur.
- **Génération privée** (`"private": true`, session exigée) : pendant le calcul, dossier `jobs/private_<id>/`
  supprimé en fin de job (et au démarrage), `sd-cli.log` vers `os.devnull`, identifiant de 128 bits (comme celui de
  son lot), dans les journaux rien que les lignes communes à toutes les générations (`DONE_LINE`, échecs neutres) ;
  dans `queue`, une entrée complète vue depuis l'espace privé seulement,
  puis `keep_private` chiffre image, miniature (en mémoire), entrées et réglages avec la clé publique notée au
  lancement (`store_private`), dans la pile privée : marque « pile » dans la fiche chiffrée, `S.rev` de l'espace
  privé augmenté ; annulée ou oubliée pendant ce rangement, elle passe « cancelled » sous `S.turn` et l'image rangée
  est supprimée (`remove_private_item`). Une génération privée ne s'arrête pas à la fermeture de la page ; finie, elle
  est oubliée par `/api/job/<id>/forget` (envoyé par sa page), sinon par `sweep()`, `PRIVATE_JOB_TTL` (24 h) après sa
  fin. Une demande `"incognito": true` (mode retiré, d'une page d'avant) est refusée (400) sans rien écrire, journal
  du serveur compris (`/api/generate` est tue). Au lancement sur Mac, `exclude_from_backup` exclut `jobs/` de Time
  Machine.
- **Estimation des durées** : `tools/estimate.py` (`predict`, priors par moteur, mesures par `"<moteur>/<modèle>"`
  dans `tools/calibration.json`, filtrées sur la release de sd.cpp installée lue dans `sdcpp/<moteur>/.installed`). Les
  coefficients partent vers l'interface par `/api/status`.

## Pièges de l'interface

- **Brouillon et mémoire de la page** : rien de l'espace privé dans `localStorage`, brouillon compris : une seule
  clé, `qwen-prompt` (`DRAFT_KEY`), où un texte privé n'est jamais écrit, même quand la demande est refusée
  (`tests/ui/brouillons.test.mjs`). La demande gardée par la page (`req` de `pageJobs`, images en data URL, privée
  comprise, pour « Reprendre » et « Relancer ») vit en mémoire de la page seulement, jamais dans `localStorage`
  (`saveOwn` n'écrit que des identifiants). La seule écriture du navigateur liée à l'espace privé est la marque de
  l'onglet dans `sessionStorage` (`RELOCK_MARK`, valeur `1`, sans aucune donnée privée : « dans l'espace, à
  reverrouiller au chargement suivant », posée dès l'entrée), toujours dans un `try` (stockage refusé : la page se
  charge sans marque) ; n'y ajouter rien d'autre (`tests/ui/etancheite.test.mjs`).
- **Visionneuse et images affichées** : la visionneuse parcourt `vList`, jamais `histItems` directement (la galerie
  peut être rechargée pendant qu'elle est ouverte). `#paintImg` (image du dessin) passe aussi par `showImage`, avec
  l'image décodée par `toEntry` (`decoded`) ; `tests/check.py` la surveille (`IMAGE_IDS`). La couleur de la barre
  d'état tirée de l'image de la visionneuse (`syncThemeColor`, cache `tints`) : `tintOf` refuse toute adresse privée
  (`secretUrl`), que le cache garderait après la sortie de l'espace (`tests/ui/etancheite.test.mjs`).
- **Saisie par espace** : la saisie du Labo (texte, images d'entrée, dessin et son tracé) est propre à chaque
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
- Palette de la lumière inactinique (fond, surface, filets, texte papier, accent ambre, halo, erreur, grain, icône
  d'erreur `--ico-err`) : jetons du `:root` de `index.html`, recopiés dans `LOGIN_PAGE` de `launch.py` ; la page hors
  ligne `OFFLINE` de `tools/ui/sw.js` n'en reprend que le fond, le texte, le texte atténué, le halo, l'accent et le
  texte sur l'accent, et `manifest.webmanifest` le fond ; le grain de l'espace privé (`html.priv`) est le même bruit
  teinté de vert ; la déclaration `@font-face` de
  la police pixel est dans `index.html` et dans `LOGIN_PAGE`. Gardée par `tests/test_palette.py` : valeurs partagées
  des trois copies (`palette_faults`), `theme-color` des trois pages et `theme_color`, `background_color` du manifeste
  égaux à `--void` ; icônes à leur taille, coins transparents (`any`) ou opaques (`maskable`, icône d'Apple), chaque
  icône du manifeste dans `PUBLIC_FILES`.
- Pas une copie : l'estimation de chaque génération de la file (`job_estimate`, pour `queue_entry` et le travail caché
  `ahead`) appelle `estimate.predict` ; l'estimation de « Relancer » (`relaunch`) est approchée (chaque référence
  comptée à la taille de la sortie, pas de `refPx`).

## Tests

`tests/bench.py` (banc : `start`, `call`, `generate`, `wait_job`, `wait_idle`, `wait_until`, `capture_push`),
`tests/fake_sdcli.py` (faux moteur), `tests/test_*.py`, `tests/check.py` (tous les contrôles), `tests/ui/`
(`driver.mjs`, `serve.py`, tests `*.test.mjs`). Commandes dans `CLAUDE.md`. Vues du pilote : `PHONE` (celle de
`phonePage`), `PC` (souris), `TABLET` et `TABLET_WIDE` (tactile), ouvertes par `newPage` et changées sans
rechargement par `setView` (`applyView`) ; clavier par `keyDown`, `keyUp` et `press`, appui maintenu par `hold`.

Recettes visuelles (pas de script jetable) :

- Planche avant/après d'un ticket visuel : `PLANCHE_AVANT=<commit> node tests/ui/probe.mjs --script
  tests/ui/planche.mjs` dessine en une image les vues de `VIEWS` (Labo, pile, Tirages, visionneuse, espace privé) aux
  tailles de `SIZES` (téléphone, tablette en hauteur et en largeur, PC ; la page redimensionnée sans rechargement), une
  rangée par taille et par version ; la rangée « avant » est jouée par la sonde de ce commit dans un worktree
  temporaire (supprimé à la fin). `PLANCHE_SORTIE` choisit le fichier, `PLANCHE_VUES` les vues, `PLANCHE_TAILLES` les
  tailles. Chaque capture attend la fin des transitions (`SETTLED`).
- PNG d'une icône depuis son SVG : `node tests/ui/probe.mjs --svg tools/ui/logo.svg --size 512 --shot
  /tmp/icone.png`. Piège de Chrome sans écran : sa fenêtre est plus haute que la zone affichée, une capture sans coupe
  sort plus haute que demandé ; la sonde fixe la vue à la taille voulue (densité 1, fond transparent) et coupe la
  capture (`clip`) à cette taille. Les coins d'une icône « maskable » ou de l'icône d'Apple restent opaques
  (`tests/test_palette.py`).
