# File d'attente, lots, prompts enregistrés et espace privé

Plan de travail écrit le 14/10/2026, à la fin de la séance de cadrage. Spécification :
`docs/specs/2026-10-14_lots-espace-prive-prompts.md` (elle fait foi pour le comportement attendu) ; vocabulaire :
`GLOSSARY.md` ; décisions : `DECISIONS.md` (entrées du 14/10/2026).

- **Tickets** : aucun (pas d'Asana pour ce projet, refusé le 13/10/2026). Le suivi vit ici et dans
  `ETAT_DU_PROJET.md`.
- **Objectif** : livrer les cinq étapes de la spécification, dans l'ordre, chacune utilisable et testée seule.
- **Critère de fin d'une étape** : contrôles du banc de l'étape au vert, contrôles de l'interface dans Chrome sans écran
  aux dimensions du téléphone (captures regardées), `py_compile` et `node --check` propres, README et `CLAUDE.md` à
  jour, un commit, service relancé si `tools/launch.py` a changé et qu'aucune génération ne tourne.
- **S'arrêter et demander** :
  - si une vérification demande une vraie génération GPU ou la suppression d'une image de `outputs/` ;
  - si une génération tourne au moment de relancer le service ;
  - avant l'étape 4, si la liste des prompts types n'a pas été validée par le porteur ;
  - si le schéma de chiffrement de l'étape 5 doit s'écarter de la spécification (le format des fichiers chiffrés est
    coûteux à changer une fois des images stockées) ;
  - « Rendre privée » réécrit `outputs/journal.jsonl` pendant que `worker()` peut y ajouter une ligne : prévoir un
    verrou commun aux deux écritures ; si ce n'est pas faisable simplement, demander ;
  - si un comportement de la spécification se révèle impossible ou contradictoire avec le code.

## Contraintes

- Dépôt public : aucun chemin absolu, nom réseau, IP ou nom Tailscale dans les fichiers suivis, y compris ici.
- Ne jamais lire ni afficher `tools/access_code.txt` ni la réponse complète de `/api/status` venant de 127.0.0.1.
- Ne pas pousser : demander au porteur de lancer `/project:push`.
- `tools/ui/index.html` est relu à chaque requête par le service : un changement d'interface est en ligne dès
  l'enregistrement, avant que le serveur qui va avec soit relancé. Pour une étape qui touche les deux, enregistrer
  l'interface au moment de relancer le service, ou garder l'interface compatible avec l'ancien serveur.

## Faits vérifiés

Lus le 14/10/2026 dans le code (`main` à `95f96de`). Les numéros de ligne bougeront pendant le travail.

| Fait | Référence |
|---|---|
| État global : `class State`, `jobs` (dict), `q` (`queue.Queue`), `current` (id du job en cours ou `None`) | `tools/launch.py:393`, `:404`, `:405` |
| `/api/generate` : seule validation = JSON valide et prompt non vide ; aucun contrôle de largeur, hauteur, étapes | `tools/launch.py:848-854` |
| Purge des jobs incognito non `queued`/`running` à chaque nouvelle demande | `tools/launch.py:856-857` |
| Identifiant de job = `AAAAMMJJ_HHMMSS_<6 hex>` ; mode nettoyé `[^a-z0-9]` (jamais de `_`) | `tools/launch.py:858-859` |
| `queue_position` figé à la création | `tools/launch.py:866` |
| `build_cmd` appelé hors de tout `try` dans `run_job` ; `worker()` n'a qu'un `finally` : une exception tue le thread | `tools/launch.py:473`, `:607-622` |
| Graine passée telle quelle à sd-cli (`-s`, défaut -1) ; le journal écrit la graine demandée, donc -1 | `tools/launch.py:434`, `:569` |
| Clés écrites dans `journal.jsonl` : mode, prompt, width, height, steps, seed, seconds, encode_seconds, sec_per_it, file, size, backend, model | `tools/launch.py:567-572` |
| Incognito réussi : PNG gardé en mémoire, ni journal, ni `save_inputs`, ni calibration | `tools/launch.py:559-564` |
| `record_calib` appelé pour tout job réussi non incognito | `tools/launch.py:78`, `:578-581` |
| Journal du moteur : `os.devnull` en incognito, sinon `jobs/<id>/sd-cli.log` | `tools/launch.py:475` |
| `discard_cancelled` supprime le dossier de travail et l'image ; `forget_files` vide le job incognito | `tools/launch.py:589`, `:599` |
| Annuler : la route repasse tout job en `cancelled`, même terminé | `tools/launch.py:870-882` (condition `:877`) |
| `public(job)` : liste des clés exposées, plus `elapsed`, `incognito`, `path`, `name` | `tools/launch.py:625-633` |
| `/api/status` : `current_job` = id brut, incognito compris ; `last_job` filtre l'incognito | `tools/launch.py:723`, `:727` |
| `notify_job` : messages « Image prête », « Image incognito prête », « Échec de la génération » ; sauté pour la calibration | `tools/launch.py:217-253` |
| Contrôles d'accès : `_host_ok`, `_post_refused`, `_allowed` ; cookie `qwen_access` ; code faux → 1 s d'attente | `tools/launch.py:670`, `:684`, `:697`, `:112`, `:799` |
| `history()` croise `outputs/*.png` et `journal.jsonl` ; `/api/delete` ne retire pas la ligne du journal | `tools/launch.py:284-305`, `:815-829` |
| Miniatures JPEG 320 px dans `outputs/.thumbs/`, écrites puis renommées | `tools/launch.py:171`, `:308-320` |
| Images d'entrée : `outputs/.inputs/<nom>/` (`init.png`, `ref_N.png`), `save_inputs` | `tools/launch.py:255-272` |
| `output_path` refuse les noms commençant par `.` et exige `.png` | `tools/launch.py:275-281` |
| Démarrage : purge `jobs/incognito_*`, reprise des entrées, garde les 20 derniers `jobs/*` | `tools/launch.py:922-934` |
| Interface : globales `mode`, `editImages`, `currentJob`, `currentIncog`, `lastResult` | `tools/ui/index.html:622` |
| Réglages `qwen-opt` : `opt = {ratio, res, steps}`, `saveOpt` ajoute `v:2`, preview, incognito, notify | `tools/ui/index.html:634-640` |
| Formats `RATIOS`, résolutions `RES`, étapes `STEPS`, `PREVIEW_EVERY = 5` | `tools/ui/index.html:607-612` |
| `closestRatio` (format le plus proche d'une forme) et `dimsExact` (option « Image ») | `tools/ui/index.html:627-632` |
| Estimation : `inputsFor`, `parts` (copie de `estimate.predict`) | `tools/ui/index.html:647-658` |
| Bouton Incognito bloqué pendant un job | `tools/ui/index.html:689` |
| Import Éditer : arrêt silencieux à 10 images | `tools/ui/index.html:797` |
| `buildRequest`, `setRunning` (grise Générer), `followJob`, clic Générer, reprise `resumeIfRunning` | `tools/ui/index.html:832`, `:874`, `:895`, `:916`, `:931` |
| `pagehide` : `forgetJob` du job incognito en cours (`keepalive`) | `tools/ui/index.html:971` |
| Galerie et visionneuse : `renderGallery`, `openViewer`, `viewerAction` (edit, mask, prompt, delete) | `tools/ui/index.html:981`, `:993`, `:1105` |
| Feuilles : `openSheet`, `ask()` (confirmation) | `tools/ui/index.html:762`, `:848` |
| `cryptography` 50.0.2 installée dans le `venv` du Mac (dépendance de `pywebpush`) | `requirements.txt`, vérifié par import |
| `.gitignore` : ignore `outputs/`, `jobs/`, `logs/`, `tools/access_code.txt`, `tools/push_*` ; rien encore pour les prompts ni l'espace privé | `.gitignore` |

## Étapes

1. **Banc permanent et file d'attente.** Créer le banc de `tests/` (faux sd-cli paramétrable, serveur sur port libre,
   appels HTTP avec les en-têtes du contrôle d'accès, interception des notifications), puis : robustesse du thread de
   calcul, validation de `/api/generate`, annulation sans effet sur un job terminé, position recalculée, `queue` dans
   `/api/status`, `current_job` muet pour l'incognito, purge incognito différée de 60 s ; interface : Générer toujours
   actif, suivi de plusieurs générations, pastille « +N », feuille de la file, `pagehide` pour toutes les générations
   incognito de la page. Mettre à jour `CLAUDE.md` (banc, piège « Exception dans un job ») et le README.
2. **Variantes.** `count`, identifiant de lot, graines tirées par le serveur et écrites au journal, `/api/lot/<id>/cancel`,
   notification unique par lot, `lot` dans `/api/history` ; interface : sélecteur 1–4, grille, « Garder celle-ci »,
   badge et « Voir le lot », « Tout télécharger ».
3. **Campagne.** `campaign` (1 à 10, mode Éditer), dimensions par photo ; interface : interrupteur, compteur, message
   au-delà de 10, estimation photo par photo.
4. **Prompts.** Fichier des prompts enregistrés (non suivi), fichier des prompts types (suivi, liste validée), routes,
   feuille de l'interface.
5. **Espace privé.** Chiffrement, stockage, sessions, routes, génération privée, héritage, « Rendre privée » (avec
   verrou sur le journal), exclusion Time Machine, interface ; README (limite du passage en clair) et `CLAUDE.md`
   (la règle de l'incognito s'étend à l'espace privé).

## Suivi

- **Fait** : cadrage, spécification, glossaire, décisions (`77c38c5`).
- **En cours** : rien.
- **À faire** : étapes 1 à 5 ; validation des prompts types par le porteur avant l'étape 4.
- **Décidé en route** (sans demande explicite du porteur, à lui signaler) : bouton Incognito libre entre deux
  demandes ; purge incognito différée de 60 s ; envoi `keepalive` à la fermeture pour toutes les générations
  incognito et privées de la page ; mode Privé non retenu d'une visite à l'autre ; schéma X25519, scrypt, HKDF,
  AES-256-GCM ; format masqué des Réglages en campagne.
