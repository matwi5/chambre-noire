# Règles de code

Lues à la revue (axe Standards de `/code-review`) : des jugements qu'aucun contrôle ne fait. Ce que `tests/check.py`
vérifie (compilation, syntaxe du JavaScript, banc, dépôt public) n'est pas répété ici. Les règles sur les données
et les tests viennent de bugs passés à travers les revues par ticket.

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
