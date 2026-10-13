# Fermer le rebinding DNS et le CSRF du serveur

Passation écrite le 13/10/2026 à la fin de la session « refonte de l'interface + revue de sécurité globale ».

- **Tickets** : aucun pour l'instant. Le projet n'a pas de tâche mère dans Asana « Hub · Suivi des tâches » ; proposer à
  l'utilisateur d'en créer une (règle 7, aucune écriture Asana sans son accord).
- **Objectif** : qu'aucune page web ouverte sur le Mac ne puisse lire ni piloter l'application, et que le code d'accès du
  téléphone ne sorte plus que vers l'interface locale légitime.
- **Critère de fin** : les deux requêtes d'attaque de l'étape 1 sont refusées après correctif (403), l'interface marche
  depuis `http://127.0.0.1:7860/` et depuis l'adresse du Wi-Fi (téléphone), `tests/run_tests.py` n'est pas cassé
  (lecture du code, pas d'exécution : il lance de vraies générations), un commit par correctif, README à jour.
- **S'arrêter et demander** : si un correctif oblige à changer le code d'accès ou le cookie existants (le téléphone de
  l'utilisateur est déjà connecté) ; si une génération tourne au moment de relancer le service ; si une vérification
  demande de lancer une vraie génération ou de supprimer une image.

## Contraintes

- Ne jamais lire ni afficher `tools/access_code.txt`, ni la réponse complète de `GET /api/status` venant de 127.0.0.1
  (elle contient le code dans `phone.code`). Pour tester, n'afficher que le code HTTP (`curl -s -o /dev/null -w "%{http_code}"`).
- Ne lancer aucune génération réelle : pour `/api/generate`, envoyer un prompt vide, que le serveur refuse (400) avant la
  file d'attente (`tools/launch.py:562-563`).
- Ne supprimer aucune image de `outputs/` : pour `/api/delete`, utiliser un nom inexistant.
- Ne pas pousser : demander à l'utilisateur de lancer `/project:push`.
- Le serveur tourne en service macOS (LaunchAgent `com.matwi5.qwen-image-local`, `launch.py --no-browser --lan`). Il relit
  `tools/ui/index.html` à chaque requête, mais un changement de `tools/launch.py` demande de relancer le service :
  `launchctl kickstart -k gui/$(id -u)/com.matwi5.qwen-image-local`, seulement si `/api/status` indique `busy: false`.
- Laisser `tools/config.json` tel quel (modification locale de l'utilisateur, hors sujet).

## Faits vérifiés

| Fait | Référence |
| --- | --- |
| Clients de confiance : adresse source seulement, sans regarder `Host` | `tools/launch.py:102` (`LOCAL_CLIENTS = ("127.0.0.1", "::1")`), `tools/launch.py:462-463` (`_local`) |
| `_allowed()` laisse tout passer sans `--lan` ou pour un client local, sinon compare le cookie | `tools/launch.py:465-470` |
| Aucun en-tête `Host`, `Origin` ni `Sec-Fetch-*` n'est lu ; seuls `Cookie` et `Content-Length` le sont | `tools/launch.py:469`, `tools/launch.py:524` |
| `do_GET` contrôle l'accès avant toute route ; page de connexion servie aux non-autorisés | `tools/launch.py:472-476` |
| `/api/status` renvoie `phone: {urls, code}` à tout client local | `tools/launch.py:489` |
| `do_POST` lit le corps brut, sans contrôle de `Content-Type` ni `Origin` | `tools/launch.py:522-525` |
| `/api/login` : JSON, sinon repli sur un corps de formulaire (`parse_qs`) ; cookie `HttpOnly; SameSite=Strict`, un an | `tools/launch.py:526-540` |
| Contrôle d'accès des autres POST | `tools/launch.py:542` |
| `/api/delete` passe par `output_path` (pas de traversée de chemin) | `tools/launch.py:544-556` |
| `/api/generate` : `json.loads(raw)` puis refus 400 si le prompt est vide, avant la file | `tools/launch.py:557-563` |
| Annulation : `POST /api/job/<id>/cancel` | `tools/launch.py:573` |
| Jeton du cookie = `sha256("qwen-image-local:" + code)` | `tools/launch.py:625` |
| Hôtes du Wi-Fi déjà calculés : `S.lan_urls` (nom `.local` et IP, avec le port) | `tools/launch.py:217` (`lan_address`), `tools/launch.py:627` |
| Écoute sur `0.0.0.0` avec `--lan`, sinon `127.0.0.1` (IPv4 seulement : `::1` n'arrive jamais) | `tools/launch.py:631` |
| Page de connexion : `fetch('/api/login')` avec `Content-Type: application/json` | `tools/launch.py:144` |
| Interface : `/api/generate` et `/api/delete` envoient `Content-Type: application/json` | `tools/ui/index.html:780`, `:855`, `:865` |
| Interface : l'annulation n'envoie **aucun** `Content-Type` | `tools/ui/index.html:792` |
| Tests de bout en bout : tous les appels envoient `Content-Type: application/json`, base `http://127.0.0.1:7860` | `tests/run_tests.py:21-23` |

## Les deux failles à corriger (revue du 13/10/2026, vérification indépendante, confiance 7/10 chacune)

### 1. Rebinding DNS vers 127.0.0.1 (sévérité moyenne)

Une page web ouverte sur le Mac, servie sur le port 7860, fait ensuite pointer son nom de domaine vers 127.0.0.1. Ses
requêtes arrivent alors depuis l'adresse locale avec `Host: <domaine de l'attaquant>:7860`, sont acceptées sans code, et
elle lit la réponse comme si elle était l'application : code d'accès (`/api/status`), prompts (`/api/history`), images
(`/api/result`), et suppression de chaque image (`/api/delete`). Vaut aussi sans `--lan`.

- Safari sur macOS : exploitable aujourd'hui (pas encore de protection de l'accès au réseau local ; WebKit
  https://www2.webkit.org/show_bug.cgi?id=319907).
- Chrome 142+ : bloqué par Local Network Access (https://developer.chrome.com/blog/local-network-access).
- Firefox 151+ : protégé, déploiement progressif.
- Ne pas compter sur un filtrage DNS du routeur (https://github.com/nccgroup/singularity/wiki/Preventing-DNS-Rebinding-Attacks).

### 2. Requête forgée vers le serveur local, CSRF (sévérité moyenne, à la limite de faible)

N'importe quel site ouvert sur le Mac soumet un formulaire `enctype="text/plain"` dont le corps est du JSON valide
(`{"prompt":"…","width":512,"height":512,"steps":4,"init_image":"data:…","strength":0.05,"pad":"="}` suivi de CRLF :
`json.loads` l'accepte). Une génération part, et une quasi-copie d'une image choisie par l'attaquant arrive dans la
galerie du Mac et du téléphone. Chrome ne bloque pas une soumission de formulaire en navigation de premier niveau
(https://github.com/WICG/local-network-access/blob/main/explainer.md) ; Safari ne bloque rien. Le téléphone n'est pas
concerné (cookie `SameSite=Strict`). Suppression et annulation ne sont pas atteignables à l'aveugle (nom ou identifiant
non devinable).

## Étapes

1. **Confirmer les failles avant de toucher au code** (serveur en marche, code HTTP seulement) :
   - rebinding : `curl -s -o /dev/null -w "%{http_code}" -H "Host: evil.example:7860" http://127.0.0.1:7860/api/history` → aujourd'hui 200 ;
   - CSRF : `curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: text/plain" -H "Origin: https://evil.example" --data '{"prompt":""}' http://127.0.0.1:7860/api/generate`
     → aujourd'hui 400 « prompt vide » : le corps a été lu et interprété, sans génération lancée.
2. **Liste blanche de l'en-tête `Host`** dans `tools/launch.py` : `127.0.0.1:<port>`, `localhost:<port>`, `[::1]:<port>`,
   plus en `--lan` les hôtes de `S.lan_urls` (comparer sans tenir compte de la casse : le nom `.local` peut arriver en
   minuscules).
   Vérifier `Host` au début de `do_GET` et `do_POST`, réponse 403 sinon, page de connexion comprise. Ne faire confiance à
   un client local (`_local()`) que si son `Host` est local ; `phone.code` n'est alors renvoyé que dans ce cas.
3. **Contrôle d'origine des POST** : refuser (403) tout POST dont l'en-tête `Origin`, s'il est présent, ne correspond pas
   à `http://<hôte autorisé>`, ou dont `Sec-Fetch-Site` vaut `cross-site`. Exiger `Content-Type: application/json` sur
   `/api/generate`, `/api/delete` et `/api/login` (le repli `parse_qs` de la connexion devient inutile : le retirer).
   Pour l'annulation (`tools/ui/index.html:792`), ajouter l'en-tête côté interface plutôt que d'exempter la route.
4. **Rejouer les requêtes de l'étape 1** → 403 toutes les deux. Vérifier aussi qu'une requête légitime passe :
   `GET /api/history` avec `Host: 127.0.0.1:7860` → 200, et le même avec l'hôte du Wi-Fi depuis le Mac → page de
   connexion (pas d'accès sans cookie, comportement inchangé).
5. **Relancer le service** si `busy: false`, puis demander à l'utilisateur de rafraîchir son téléphone pour confirmer que
   l'interface marche toujours depuis le Wi-Fi (le cookie existant reste valable : ne pas changer le jeton).
6. **README** : section « Depuis un téléphone », ajouter une phrase sur ce qui est refusé (requêtes venant d'un autre
   site ou d'un autre nom d'hôte) si le comportement visible change (par exemple accès par un nom d'hôte non prévu).
7. **Commits** : un par correctif (Host, puis origine des POST), en anglais, au format du `git log` du dépôt. Pas de push.

## Déjà examiné et écarté par la revue (ne pas refaire)

- Cookie dérivé du code et HTTP non chiffré sur le Wi-Fi (`tools/launch.py:538`, `:625`) : durcissement, pas une faille
  (intercepter le cookie revient à intercepter le code ; changer le code invalide le cookie).
- Balise `<lora:chemin>` dans le prompt (`tools/launch.py:273`) : sd-cli charge bien le fichier désigné, mais rien ne
  revient à l'attaquant, déjà authentifié, et un fichier illisible est ignoré. Filtrer la balise reste un durcissement possible.
- Installation : binaires et modèles épinglés et contrôlés par SHA256, extraction sûre, TLS vérifié.
- Aucun XSS dans l'interface, aucune injection de commande, aucune traversée de chemin, code d'accès jamais commité.
- Robustesse hors périmètre sécurité : un `prompt` non chaîne ou une image de référence illisible fait lever une
  exception dans `build_cmd`, que `worker()` (`tools/launch.py:418-428`) n'attrape pas : le thread meurt et la file se
  bloque jusqu'au redémarrage. À signaler à l'utilisateur comme piste séparée, pas à corriger ici sans son accord.

## Suivi

- Fait : —
- En cours : —
- À faire : étapes 1 à 7.
