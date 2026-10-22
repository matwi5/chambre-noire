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
  seconde) et le hook avant commit la vérifient seule ; `tests/rewrap.py` recoupe un Markdown sans le casser.
- **Un comportement qui change change partout où il est décrit** : chercher son ancienne formulation (`grep`) dans le
  README, les docstrings et commentaires, et la carte du code, et la reprendre dans le même commit.

## Données et disque

- **Supprimer « tous les autres » : par nom ou identifiant, jamais par identité d'objet.** Une liste rechargée entre
  l'ouverture et l'appui donne de nouveaux objets, et l'élément gardé partait avec les autres (« Garder celle-ci »,
  corrigé en `8ce12d4`). Un test prouve que l'élément gardé reste, y compris après un rechargement de la liste.
- **Écriture en plusieurs temps : la bascule atomique (`os.replace`) en dernier**, après `fsync` de chaque fichier
  écrit et de leur dossier ; sinon une coupure laisse une bascule vers des fichiers vides. Un test de panne à chaque
  point d'écriture, en `Exception` et en `BaseException` (interruption), montre qu'on retombe sur l'ancien état ou le
  nouveau, jamais un mélange (modèle : changement du code privé, `DECISIONS.md`).
- **Toute nouvelle écriture sur le disque ou dans un journal respecte l'incognito et l'espace privé** (`secret(job)` :
  rien en clair), se fait de façon atomique sous le verrou de ce qu'elle modifie, et un fichier qui contient une
  donnée de l'utilisateur est lisible par son seul propriétaire (`0o600`) : le Mac peut avoir d'autres comptes.

## Serveur et interface

- **Un champ nouveau de `/api/status` a une valeur par défaut tolérante dans l'interface** (`s.x || …`) :
  `index.html` est relu à chaque requête, donc servi avant que le serveur qui envoie le champ soit relancé.
- **Une constante ou une formule recopiée entre Python et JavaScript est notée dans les pièges de `CLAUDE.md`**,
  avec les deux emplacements : sinon l'un change sans l'autre et rien ne casse visiblement.
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
- **Le test d'une garde d'une zone sensible (incognito, espace privé, suppression) est prouvé rouge** sur le code
  sans la branche qu'il protège (retirée le temps de l'essai), puis vert ; le message du commit le dit.
- **Une assertion « rien ne change » attend d'abord la fin de l'action qui pourrait changer quelque chose** (réponse
  reçue, Mac au repos : `bench.idle()`) : vérifiée trop tôt, elle passe avant que le changement arrive.
- **Un fichier de test se termine par `if __name__ == "__main__": unittest.main()`**, pour se lancer seul.

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
