# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Interface web locale pour générer et modifier des images avec Qwen-Image 2.1, sur PC Windows (Vulkan, CUDA, CPU) ou Mac
Apple Silicon (Metal), sans droits administrateur. Un serveur Python en un seul fichier (`tools/launch.py`) lance
`sd-cli` une fois par génération ; l'interface est un seul fichier (`tools/ui/index.html`, sans dépendance ni build).

À lire selon le besoin :

- `README.md` : documentation utilisateur et technique de référence (comportements visibles, API locale) ;
- `docs/agents/carte-du-code.md` : où trouver quoi dans `launch.py` et `index.html`, et comment les mécanismes
  s'enchaînent (fichiers, lots, notifications, accès, incognito, espace privé) : à lire avant d'ouvrir ces fichiers ;
- `CODING_STANDARDS.md` : règles de code lues à la revue ;
- `docs/agents/session-deleguee.md` : ce qu'une session de groupe doit savoir dans ce dépôt ;
- `BRIEF.md` (cadrage), `DECISIONS.md` (décisions), `GLOSSARY.md` (vocabulaire), `ETAT_DU_PROJET.md` (état, journal).

Le dépôt GitHub est **public** : rien de propre à la machine du porteur dans les fichiers suivis ni dans les messages
de commit (nom réseau du Mac, adresses IP, noms Tailscale, chemins `/Users/…`, contenu de `tools/access_code.txt`),
y compris dans `travail/tasks/`.

## Commandes

Python du projet : `venv/bin/python` (Mac), `venv\Scripts\python.exe` (Windows). Exemples ci-dessous en version Mac.
Dans un worktree (pas de `venv/`, non suivi) : `python3 tests/check.py --link-venv` crée un lien relatif `venv` vers
le venv du dossier principal ; ensuite les commandes `venv/bin/python …` marchent telles quelles.

```bash
venv/bin/python -m pip install -r requirements.txt   # Pillow, NumPy, pywebpush, cryptography (+ pywin32 sous Windows)
venv/bin/python setup.py            # moteur sd.cpp + modèles (épinglés, SHA256), raccourci, calibration
venv/bin/python setup.py --check    # vérifie l'installation sans rien télécharger
# options de setup.py : --q8 (modèle Q8_0), --cuda / --no-cpu (Windows), --no-calibrate
venv/bin/python tools/launch.py [--model q4|q8] [--port 7860] [--lan] [--no-browser]
venv/bin/python tools/calibrate.py [--if-needed]   # 3 générations de calibration, sans passer par le serveur
venv/bin/python tools/make_service.py [--remove]   # Mac : LaunchAgent qui lance launch.py --no-browser --lan
```

## Vérifications

Aucun lint ni typage n'est déclaré. Après un changement, une seule commande (c'est aussi celle de la CI GitHub,
`.github/workflows/checks.yml`, sur chaque pull request vers `main` et chaque envoi sur `dev`) :

```bash
venv/bin/python tests/check.py [--no-bench] [--ui]
```

Elle compile chaque `.py` suivi, passe chaque bloc `<script>` de `tools/ui/index.html` et chaque `.js`/`.mjs` suivi
à `node --check`, refuse une ligne ajoutée depuis la base (`git merge-base HEAD origin/main`) de plus de 120
caractères (`CODING_STANDARDS.md`), lance le banc et recopie sa ligne « Ran N tests … » et son verdict (c'est elle
qu'on cite, jamais un compte de tête) ; code de sortie non nul au moindre échec. `tests/test_public_repo.py` y
échoue si un fichier suivi contient un chemin `/Users/<nom>`, une adresse IP privée ou un nom en `.ts.net` autre que
ceux du banc.

- **Banc** (sans GPU, ≈ 1 min) : `venv/bin/python -m unittest discover -s tests` ; un seul fichier :
  `venv/bin/python -m unittest discover -s tests -p test_x.py`. `tests/bench.py` sert `tools/launch.py` sur un port
  libre, tous ses dossiers repointés vers un dossier temporaire, avec le faux moteur `tests/fake_sdcli.py` (`FAIL`
  ou `SLOW[=s]` dans le prompt le font échouer ou ralentir, `FAILSEED=<n>` échouer pour la seule graine n, une image
  d'un lot, `HOLD[=nom]` attendre que le test le libère par `bench.release(nom)`, aussi offert par le banc du pilote
  d'interface : une génération reste en cours, les suivantes en file, sans dépendre du temps). Trois origines de
  requête : `call()` = le Mac, `remote=True` = HTTPS relayé par `tailscale serve` (`bench.HTTPS_HOST`),
  `wifi=True` = `http://` direct d'un autre appareil (`bench.WIFI_HOST`, `LOCAL_CLIENTS` vidé pendant l'appel).
  `bench.capture_push()` intercepte les notifications (`sent.decided` : celles que le serveur a décidées, complètes
  après `bench.wait_idle()`), `bench.wait_until(cond)` attend une condition observable, `bench.LOG` reçoit les
  sorties du serveur.
- **Interface** : `venv/bin/python tests/check.py --ui` (ou `node --test "tests/ui/*.test.mjs"`), en local seulement
  (Chrome installé ; pas en CI). `tests/ui/driver.mjs` lance le banc (`tests/ui/serve.py`) et Chrome sans écran
  (profil temporaire supprimé à la fin), piloté par le protocole DevTools depuis Node (WebSocket natif, sans
  Playwright), dans la vue du téléphone du porteur (367×760, densité 2,5, mobile, tactile : l'interface y passe en
  `html.lite`) ; `page.assertNoErrors()` échoue sur toute erreur de console. Tests : `smoke` (écrans principaux),
  `keep` (régression « Garder celle-ci »), `saisie` (photos choisies d'un coup, vidage après « Générer », saisie
  propre à chaque espace ; `page.setFiles` remplit un champ de fichiers), `file` (file et pastille propres à chaque
  espace), `entete` (cadenas de la galerie, pastille qui tient dans sa bulle), `prompts` (prompts enregistrés
  propres à chaque espace) et `reprise` (prompt complet d'une génération reprise, publique ou privée). Une
  vérification d'interface nouvelle y devient un test plutôt qu'un script jetable. Une vue plus grande cache des
  débordements : regarder aussi les captures (`page.screenshot`).
- La fermeture de la page (`pagehide`, envoi `keepalive`) se valide sur le téléphone : Chrome sans écran ne la rejoue
  pas de façon constante.
- `tests/run_tests.py --steps 8 [--only t2i|edit|mask|annot]` : bout en bout, serveur lancé sur 127.0.0.1:7860. Il
  lance de **vraies générations GPU** (plusieurs minutes), écrit dans `outputs/`, le journal et
  `tools/calibration.json` : ne le lancer que si l'utilisateur le demande.

## Service macOS sur le poste du porteur

L'interface tourne en LaunchAgent `com.matwi5.qwen-image-local` (journal `logs/service.log`), avec `--lan`, depuis le
dossier principal du dépôt, qui reste sur la branche `main` : le service ne fait tourner que ce qui est fusionné.
Après la fusion d'une PR, mettre ce dossier à jour (`git pull --ff-only` sur `main`) avant de relancer le service.
`tools/ui/index.html` est relu à chaque requête : un changement d'interface est en ligne dès l'enregistrement, donc
avant que le serveur qui va avec soit relancé. Un changement de `tools/launch.py` demande de relancer le service, et
seulement si aucune génération ne tourne :

```bash
venv/bin/python -c "import json,urllib.request as u; print(json.load(u.urlopen('http://127.0.0.1:7860/api/status'))['busy'])"
launchctl kickstart -k gui/$(id -u)/com.matwi5.qwen-image-local   # si False
```

Ne jamais afficher la réponse complète de `/api/status` venant de 127.0.0.1 ni `tools/access_code.txt` : ils
contiennent le code d'accès du téléphone. Ne jamais afficher `logs/service.log` : il contient les adresses du Mac.
Ne lancer aucune génération réelle et ne supprimer aucune image de `outputs/` sans accord.

## Pièges et invariants

- **Incognito et espace privé** : `secret(job)` désigne l'un ou l'autre mode ; chaque `print`, écriture de journal,
  de calibration ou de fichier hors du dossier de travail passe par lui. **Toute nouvelle écriture sur le disque ou
  dans les journaux doit respecter ces deux modes.** `log_message` tait `/api/private/` et aucun `print` ne parle de
  l'espace privé ; ni le titre ni le texte d'un prompt enregistré ne vont dans les journaux du serveur.
- **Verrous** : toute écriture de `outputs/journal.jsonl` passe sous `JOURNAL_LOCK` ; toute écriture ou suppression
  d'une image privée ou des prompts privés (`private/prompts`) passe sous `PRIVATE_LOCK`, après `finish_rekey()` ; un
  nouveau fichier de `private/` est aussi rechiffré par `rekey_space` et rangé par `finish_rekey`.
- **Contrôle d'accès** (dans cet ordre, dans `H`) : `_host_ok`, `_post_refused`, `_allowed`, et `_secure` pour
  l'espace privé (jamais les en-têtes de relais). Toute nouvelle route POST passe par ces contrôles : l'interface doit
  envoyer `Content-Type: application/json`, même sans corps. Seules les requêtes privées prolongent une session
  (`_private_session(touch=True)`), jamais `/api/status`. Toute route qui suit, prévisualise ou annule une génération
  ou un lot passe par `_hidden` : une génération privée y est « inconnue » (404) hors de l'espace privé. Le jeton de
  page (`PAGE_TOKEN`, champ `page`) n'ouvre aucune route : ne jamais s'en servir comme droit.
- **Formule dupliquée en JavaScript** : `parts()`, `refPx` et `inputsFor` de `index.html` recopient `predict()` et
  `ref_px()` de `estimate.py` (jetons de 16×16 px, arrondi à 32). Une modification de la formule ou d'un coefficient se
  fait des deux côtés. `PREVIEW_EVERY = 5` côté interface doit égaler le défaut `preview_interval` de `build_cmd`.
  La longueur minimale du code privé (`MIN_PRIVATE_CODE`, 8) est aussi vérifiée dans `index.html` (feuilles privées).
  L'estimation de chaque génération de la file (`job_estimate`, pour `queue_entry` et le travail caché `ahead`)
  appelle `estimate.predict` : pas de troisième copie.
- **Interface** : la visionneuse parcourt `vList`, jamais `histItems` directement (la galerie peut être rechargée
  pendant qu'elle est ouverte).
- **Saisie par espace** : tout ajout à la saisie qui attend (lecture d'image, envoi d'une demande) note son espace ou
  sa liste avant la première attente, sinon un changement d'espace pendant l'attente le fait tomber dans la saisie de
  l'autre espace (une image privée dans la saisie publique).
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
- **Banc** : un nouveau chemin calculé à l'import de `launch.py` doit être repointé dans `bench.start()`, sinon le banc
  écrit dans le dépôt. Le statut `cancelled` est posé avant que le moteur soit arrêté : un test attend
  `bench.wait_idle()` (`S.current` rendu, en dernier, par `worker()`) avant de regarder le disque. Les aperçus de
  moins de 1000 octets sont ignorés par `latest_preview`. Le banc n'exécute pas `main()`.
- **`tools/prompt_types.json`** (prompts types) : liste validée par le porteur, à changer seulement avec son accord.
- **`tools/config.json` est suivi par git** et contient les préférences du porteur (`"model": "q8"`) ; `setup.py` réécrit
  `backend` sous Windows. `sd_port` n'est lu nulle part.
- **Fichiers périmés** : `start-ui-sdcpp.cmd` (nom de modèle sans `UC-`, sd-server) et `workflows/*.json` (lus par
  aucun code) ne reflètent plus l'application.
- `setup.py` ne rehache pas un fichier qui a son marqueur `.sha256ok` et la bonne taille ; un fichier dont l'empreinte
  est fausse devient `.corrompu` et n'est jamais supprimé seul.

## Conventions

- Documentation, commentaires et interface en français ; messages de commit en anglais, une phrase à l'impératif sans
  préfixe (« Add an incognito mode that keeps generated images off the disk »), corps qui explique le pourquoi.
- Le README décrit chaque comportement visible et l'API locale : le mettre à jour dans le même commit que le code ;
  la carte du code suit un renommage ou un déplacement de fonction.
- Branches (décision du porteur du 15/10/2026) : on code toujours sur `dev`, dans le worktree `.claude/worktrees/dev`
  (le dossier principal reste sur `main` pour le service) ; les sessions de groupe se lancent depuis ce worktree, pour
  partir de `dev`, et leurs branches s'y fusionnent. `main` ne reçoit que des pull requests depuis `dev` (`/project:pr`)
  et est protégée sur GitHub (PR obligatoire, CI `checks` au vert exigée, ni push direct ni forcé, administrateur
  compris). `/project:push` se lance
  sur `dev` ; après la fusion d'une PR, `/project:sync main` remet `dev` à jour.
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
