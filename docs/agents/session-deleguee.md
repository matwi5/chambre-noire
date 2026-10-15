# Session déléguée : ce qu'une session de groupe doit savoir dans ce dépôt

Une session déléguée (session de groupe lancée depuis le tableau de bord, ou session à qui la discussion principale
confie une partie du travail) lit ce fichier, puis ses tickets et les décisions propres à son groupe. Son brief n'a
pas à répéter ce qui suit. Lire aussi `CLAUDE.md` (commandes, pièges), `GLOSSARY.md`, `CODING_STANDARDS.md` et, pour
s'orienter dans le code, `docs/agents/carte-du-code.md`.

## Point de départ

- On code sur `dev` : la session se lance depuis le worktree `.claude/worktrees/dev` et travaille dans son propre
  worktree, sur sa propre branche, partie de `dev`. `main` ne reçoit que des pull requests depuis `dev` et est
  protégée.
- Pas de `venv/` dans un worktree (non suivi) : `python3 tests/check.py --link-venv` crée un lien relatif vers celui
  du dossier principal, après quoi `venv/bin/python …` marche partout. N'écrire nulle part le chemin absolu d'un
  Python ni d'un dossier.

## Contrôles

- Après chaque changement : `venv/bin/python tests/check.py` (compilation, JavaScript de l'interface, banc,
  dépôt public). Citer sa ligne « Ran N tests … » telle quelle, jamais un nombre de tête. Un seul fichier de test :
  `venv/bin/python -m unittest discover -s tests -p test_x.py`.
- Changement d'interface : `venv/bin/python tests/check.py --ui` (Chrome sans écran, vue du téléphone). Une
  vérification d'interface nouvelle devient un test de `tests/ui/` (pilote `driver.mjs`), pas un script jetable ;
  une vérification ponctuelle passe par la sonde (`node tests/ui/probe.mjs --eval '<expression>'`, options en tête
  du fichier), pas par un script jetable.
- La fermeture de la page (`pagehide`, `keepalive`) se valide sur le téléphone : Chrome sans écran ne la rejoue pas
  de façon constante.
- Aucune vraie génération GPU : `tests/run_tests.py` est interdit sans accord du porteur.

## Intouchable

- Le service du porteur (LaunchAgent `com.matwi5.qwen-image-local`, port 7860) tourne depuis le dossier principal,
  sur `main` : ne pas le relancer, ne pas utiliser le port 7860, ne pas interroger son `/api/status`.
- Ne jamais lire ni afficher `logs/` (dont `logs/service.log`, qui contient les adresses du Mac) ni
  `tools/access_code.txt` ; ne toucher ni à `private/`, ni à `jobs/`, ni à `outputs/` du dossier principal, ni au
  worktree `.claude/worktrees/dev`.
- Le dépôt GitHub est public : rien de propre à la machine du porteur dans un fichier suivi ni dans un message de
  commit (nom réseau du Mac, adresse IP, nom Tailscale, chemin `/Users/…`). `tests/test_public_repo.py` en attrape les
  motifs génériques, pas tout.

## Écritures permises

- Commits sur sa branche, un par ticket, au format du projet (une phrase anglaise à l'impératif sans préfixe, corps
  qui explique le pourquoi, lignes d'attribution). Le README et `CLAUDE.md` changent dans le commit qui change ce
  qu'ils décrivent.
- Asana : seulement le suivi de ses propres tickets (ligne « Statut : », commentaire de résultat avec le hash du
  commit, cochage à la fin). Quand le porteur change d'avis en cours de route, l'écrire en commentaire daté
  « mise à jour du porteur (JJ/MM/AAAA) : … » sur le ticket concerné ; tout autre changement de ticket (création,
  contenu, périmètre) passe par la discussion principale.

## Réservé à la discussion principale et au porteur

- `ETAT_DU_PROJET.md` (état et journal), la fusion des branches de groupe dans `dev`.
- Pousser, ouvrir une pull request, fusionner vers `main`, modifier les réglages GitHub (protection de `main`
  comprise) : gestes du porteur.

Le reste (compte rendu de fin, questions au porteur, tableau de bord) suit la partie commune du brief des
sessions déléguées, tenue hors de ce dépôt.
