# Règles de code

Lues à la revue (axe Standards de `/code-review`) : des jugements qu'aucun contrôle ne fait. Ce que `tests/check.py`
vérifie (compilation, syntaxe du JavaScript, banc, dépôt public) n'est pas répété ici, sauf la longueur des lignes,
que la revue lit aussi, et les règles devenues contrôles, rappelées en une ligne à la fin. Les règles sur les données et
les tests viennent de bugs passés à travers les revues par ticket.

## Forme

- **120 caractères au plus par ligne** (caractères, pas octets) dans les `.py`, `.md`, `.mjs` et `.js`, hors
  `tools/ui/index.html`, tableaux Markdown et blocs de code : une ligne plus longue se lit mal dans un diff et sur un
  écran étroit. Vérifiée par `tests/check.py` sur les seules lignes ajoutées depuis la base (`git merge-base HEAD
  origin/main`) : les lignes existantes ne sont reprises que quand on les touche. `check.py --lines` (moins d'une
  seconde) et le hook avant commit la vérifient seule ; celui de Claude Code (`check.py --hook`), après chaque
  écriture par Edit ou Write et après chaque commande Bash (les fichiers qu'elle a écrits), recoupe seul la prose trop
  longue et signale le code ; `check.py --lines --fix` recoupe les seules lignes fautives (Markdown, commentaires,
  docstrings).
- **Un comportement qui change change partout où il est décrit** : chercher son ancienne formulation par `git grep`
  sur tout le dépôt suivi (README, docstrings et commentaires, carte du code, et textes de l'interface :
  `tools/ui/index.html`, `LOGIN_PAGE` de `tools/launch.py`, page hors ligne de `tools/ui/sw.js`), et la reprendre dans
  le même commit. Un ancien libellé était resté dans l'interface après un renommage.

## Données et disque

- **Supprimer « tous les autres » : par nom ou identifiant, jamais par identité d'objet.** Une liste rechargée entre
  l'ouverture et l'appui donne de nouveaux objets, et l'élément gardé partait avec les autres (« Garder celle-ci »,
  corrigé en `8ce12d4`). Un test prouve que l'élément gardé reste, y compris après un rechargement de la liste.
- **Écriture en plusieurs temps : la bascule atomique (`os.replace`) en dernier**, après `fsync` de chaque fichier
  écrit et de leur dossier ; sinon une coupure laisse une bascule vers des fichiers vides. Un test de panne à chaque
  point d'écriture, en `Exception` et en `BaseException` (interruption), montre qu'on retombe sur l'ancien état ou le
  nouveau, jamais un mélange (modèle : changement du code privé, `DECISIONS.md`).
- **Toute nouvelle écriture sur le disque ou dans un journal respecte l'espace privé** (`secret(job)` :
  rien en clair), se fait de façon atomique sous le verrou de ce qu'elle modifie, et un fichier qui contient une
  donnée de l'utilisateur est lisible par son seul propriétaire (`0o600`) : le Mac peut avoir d'autres comptes.

## Serveur et interface

- **Un champ nouveau de `/api/status` a une valeur par défaut tolérante dans l'interface** (`s.x || …`) :
  `index.html` est relu à chaque requête, donc servi avant que le serveur qui envoie le champ soit relancé.
- **Une constante ou une formule recopiée entre Python et JavaScript est notée dans la carte du code** (« Copies entre
  Python et JavaScript »), avec les deux emplacements : sinon l'un change sans l'autre et rien ne casse visiblement.
- **Une action asynchrone de l'interface liée à un espace note ce qu'elle vise avant sa première attente** (`await`,
  `fetch`, lecture d'un fichier) : l'espace (`inPrivate()`), la liste, l'onglet ou la route ; après l'attente, elle
  écrit dans ce qu'elle a noté, ou abandonne si l'espace a changé, sans relire l'état global. Sinon une image privée
  tombe dans la saisie publique, une confirmation montre un titre privé dans l'espace public (groupes A et C du
  15/10/2026). `changedSpace` ferme toute feuille qui montre une donnée de l'espace quitté. Une garde (plafond,
  dessin, confirmation) se refait à l'arrivée sur la liste notée, et une question au porteur ne porte que sur la
  saisie affichée.
- **Un élément montré ou caché par `hidden` dont le CSS fixe `display` a sa règle `[hidden]{display:none}`** : sinon
  le `display` du CSS l'emporte et l'élément reste visible.
- **Une génération suivie se rapproche de la file par son identifiant, jamais par son rang** : la page interroge
  `/api/job/<id>` chaque seconde et `/api/status` toutes les 2 à 5 s ; entre les deux, la file a pu avancer, et un
  404 peut arriver avant que `applyPrivate` sache l'espace fermé (groupe B du 15/10/2026).
- **Une demande lue par une autre requête se lit une seule fois, par `.get`** (`job.get("req")`) : `forget_files`
  retire `req` d'une génération secrète à tout moment, et un `job["req"]` lu deux fois répond 500.
- **Une erreur de programmation ne devient pas un statut métier** : on lève une exception dédiée (`StaleKey`) plutôt
  que de convertir une classe large (`KeyError`, `LookupError`, `Exception`) en « espace verrouillé » ou en 404.
- **L'interface n'affiche rien pour seulement servir de repère à un test** : le test lit l'état (`pageJobs`,
  `queueState`) ou le pilote fournit l'accès voulu.
- **`nonlocal` plutôt qu'une liste à un élément** pour qu'une fonction intérieure modifie une variable : l'intention se
  lit, et l'astuce de la liste cache une affectation.

## Tests

- **Un test se synchronise sur une condition observable, jamais sur un `time.sleep`** (`bench.wait_until`,
  `wait_job`, `wait_idle`, `sent.decided`, `threading.Event`) : un `sleep` est trop court sur une machine chargée et
  rend le test instable, ou trop long partout. Seul un faux qui simule une lenteur (faux moteur) peut dormir. Pour
  garder une génération en cours ou en file, `HOLD` dans le prompt plutôt que `SLOW` (voir `tests/fake_sdcli.py`).
- **Une correction de l'interface reçoit un test dans `tests/ui/`** quand le banc ne peut pas la voir : deux bugs
  d'interface ne sont apparus que dans Chrome, banc au vert.
- **Le test d'une garde d'une zone sensible (espace privé, suppression) est prouvé rouge** sur le code
  sans la branche qu'il protège (retirée le temps de l'essai), puis vert ; le message du commit le dit. L'essai passe
  par `tests/mutate.py <fichier> --old <texte> --new <texte> -- <commande>`, qui rend toujours le fichier (échec,
  interruption), pas par un script jetable qui modifie l'arbre.
- **Une assertion « rien ne change » attend d'abord la fin de l'action qui pourrait changer quelque chose** (réponse
  reçue, Mac au repos : `bench.idle()`) : vérifiée trop tôt, elle passe avant que le changement arrive.
- **Un fichier de test se termine par `if __name__ == "__main__": unittest.main()`**, pour se lancer seul.
- **Réécrire un test garde l'assertion qui porte son titre ; un échec se diagnostique, il ne se supprime pas** : un
  test réécrit avait perdu l'assertion qui prouvait ce que dit son nom, et passait sans plus rien vérifier. Un test
  qui échoue se comprend d'abord (`check.py --repeat`, journal gardé) ; l'affaiblir ou le retirer se dit dans le
  commit, avec la raison.

## Vérifiées par `tests/check.py`

Règles devenues des contrôles (`tests/rules.py`, sur les lignes ajoutées depuis la base) : la revue n'a plus à les
relire, un échec dit la ligne et la raison.

- Un nom de variable ou de fonction JavaScript de `index.html` ne reprend pas l'`id` d'un élément (chaque `id` est
  aussi une globale de `window`, que la variable masque).
- Une assertion sur tous les éléments d'une liste (`.every(`, `all(`) vérifie d'abord sa longueur, sur la même ligne ou
  la précédente : `[].every(...)` et `all([])` sont toujours vrais.
- Une promesse n'est pas prise pour un booléen (`.then(…) &&`, `.then(…) ||`).
- Un nom `HOLD=<nom>` n'est employé que dans un seul fichier de test.
- `wait_job(…, ("running",))` attend une génération dont le prompt porte `HOLD` ou `SLOW` : sinon elle peut finir
  avant d'être vue en cours (CI rouge du 21/10/2026).
- Chaque nom cité entre accents graves dans `docs/agents/carte-du-code.md` existe dans le code.
- `index.html` : une couleur (`#hex`, `rgb(`, `rgba(`) ne s'écrit que dans le bloc des jetons (ligne qui déclare un
  `--jeton`), pas ailleurs ; une `@keyframes` est nommée par une `animation` ; une adresse d'image peut-être privée
  (`privImage`, `privThumb`, `thumbOf`, `srcOf`, `/api/private/`) n'est posée sur une image (`.src=`, `src="${…}"`)
  que par `showImage` ou `preload`, qui la refusent pendant « Sortir » (listes connues : `PRIVATE_SRC_KNOWN` de
  `tests/rules.py`) ; chaque id de `IMAGE_IDS` (`tests/check.py`) existe.
- Tests d'interface (`tests/ui/*.test.mjs`) : pas d'attente fixe (`new Promise(r => setTimeout(r, N))`) : une condition
  (`page.waitFor`), ou `elapse(ms)` du pilote pour un délai voulu ; une aide de premier niveau (`function`, `const … =
  (…) =>`) ou une attente `page.waitFor` d'au moins 30 caractères déjà écrite dans un autre fichier va dans
  `driver.mjs` ; l'espace privé se ferme (`/api/private/lock`, `pagehide` ou `pageshow` simulés, `closedByMac()` qui
  n'attend pas le repos lui-même) juste après `await page.privateIdle()` (ligne de code précédente) ; on y entre par
  `page.enterPrivate(code)`, pas par `/api/private/create` ou `/unlock`. Un cas voulu porte `// règle levée : <raison>`
  sur sa ligne ou celle d'avant.
- Sur des fichiers entiers, avant le banc : aucun `print` de `tools/launch.py` ne dépend de `secret(…)` ; chaque route
  `/api/…` du serveur est dans sa docstring ; un bloc `with PRIVATE_LOCK:` qui appelle quelque chose passe par
  `finish_rekey()` (sauf `store_private` et la suppression de tout l'espace) ; un import interne (`from bench import
  x`, `launch.x`) nomme un nom qui existe.
