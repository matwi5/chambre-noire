# Règles de code

Lues à la revue (axe Standards de `/code-review`) : des jugements qu'aucun contrôle ne fait. Ce que `tests/check.py`
vérifie (compilation, syntaxe du JavaScript, banc, dépôt public) n'est pas répété ici, sauf la longueur des lignes,
que la revue lit aussi. Les règles sur les données et les tests viennent de bugs passés à travers les revues par
ticket.

## Forme

- **120 caractères au plus par ligne** (caractères, pas octets) dans les `.py`, `.md`, `.mjs` et `.js`, hors
  `tools/ui/index.html`, tableaux Markdown et blocs de code : une ligne plus longue se lit mal dans un diff et sur un
  écran étroit. Vérifiée par `tests/check.py` sur les seules lignes ajoutées depuis la base (`git merge-base HEAD
  origin/main`) : les lignes existantes ne sont reprises que quand on les touche. `check.py --lines` (moins d'une
  seconde) et le hook avant commit la vérifient seule ; `tests/rewrap.py` recoupe un Markdown sans le casser.

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
- **Un nom de variable JavaScript ne reprend pas l'`id` d'un élément du DOM** : chaque `id` est aussi une globale de
  `window` : une variable du même nom la masque, et le code lit l'une en croyant lire l'autre.
- **Une action asynchrone de l'interface liée à un espace note ce qu'elle vise avant sa première attente** (`await`,
  `fetch`, lecture d'un fichier) : l'espace (`inPrivate()`), la liste, l'onglet ou la route ; après l'attente, elle
  écrit dans ce qu'elle a noté, ou abandonne si l'espace a changé, sans relire l'état global. Sinon une image privée
  tombe dans la saisie publique, une confirmation montre un titre privé dans l'espace public (groupes A et C du
  15/10/2026). `changedSpace` ferme toute feuille qui montre une donnée de l'espace quitté.
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
- **Une assertion sur tous les éléments d'une liste vérifie d'abord que la liste n'est pas vide** (`[].every(...)`,
  `all([])` sont toujours vrais) : `excerpts.length > 0 && excerpts.every(...)`. Sinon une file déjà vide (génération
  finie plus tôt que prévu) fait passer le test sans rien vérifier.
- **Une correction de l'interface reçoit un test dans `tests/ui/`** quand le banc ne peut pas la voir : deux bugs
  d'interface ne sont apparus que dans Chrome, banc au vert.
- **Un fichier de test se termine par `if __name__ == "__main__": unittest.main()`**, pour se lancer seul.
