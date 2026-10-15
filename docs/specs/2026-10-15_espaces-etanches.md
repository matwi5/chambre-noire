# Espaces public et privé étanches, et retouches de la saisie

Spécification du 15/10/2026, issue d'une séance de questions avec le porteur (toutes les réponses validées). Décision
de conception liée dans `DECISIONS.md` (« Espaces public et privé étanches », qui révise « Espace privé discret » et
« Espace privé durci après la revue de sécurité ») ; vocabulaire dans `GLOSSARY.md` (« Espace public », « Espace
privé », « Prompt enregistré »). Statut : **prête pour l'implémentation**. Elle complète la spécification du
14/10/2026 (`2026-10-14_lots-espace-prive-prompts.md`), dont elle remplace la règle « les prompts enregistrés restent
hors de l'espace privé ».

## Problème

En essayant l'espace privé sur son téléphone, le porteur voit passer d'un espace à l'autre ce qui devrait rester d'un
seul côté :

- un prompt enregistré dans l'espace privé apparaît dans la liste de l'espace public, en clair sur le Mac ;
- la file d'attente montre à chaque espace les générations de l'autre ; dans l'espace privé, sa propre génération
  privée y apparaît comme « Génération incognito » dès que la page a été rechargée, sans pouvoir la suivre ni
  l'annuler ;
- après la sortie de l'espace privé, la progression de la génération privée reste à l'écran jusqu'au rechargement ;
- le texte et les images saisis sont communs aux deux espaces : ce qui est tapé d'un côté se retrouve de l'autre.

Il relève aussi des défauts de la saisie et de l'en-tête :

- en Éditer, choisir plusieurs photos d'un coup sur le téléphone n'en ajoute que la première ;
- après « Générer », le texte et les images restent dans les champs ;
- le cadenas de l'espace privé est moins visible que le bouton Rafraîchir voisin ;
- la pastille « +1 en attente », en haut, dépasse de sa bulle.

## Solution

- **Deux espaces étanches** : l'espace public et l'espace privé ont chacun leur galerie (déjà le cas), leur file
  d'attente, leurs générations en cours, leur saisie et leurs prompts enregistrés. Restent communs : les prompts
  types, les Réglages et l'autorisation des notifications.
- **File cloisonnée** : chaque appareil ne voit que les générations de l'espace où il se trouve. Une génération qui
  attend derrière une génération cachée de l'autre espace affiche « en attente » et une durée estimée honnête, qui
  compte ce travail caché, sans ligne ni rang pour lui.
- **Sortie et retour** : à la sortie, la génération privée quitte l'écran tout de suite et continue sur le Mac ; tout
  appareil qui entre dans l'espace privé la retrouve avec son prompt et sa progression, et peut l'annuler.
- **Prompts enregistrés privés**, chiffrés avec l'espace privé, visibles seulement dedans.
- **Saisie propre à chaque espace**, onglet par onglet ; la saisie privée n'est jamais écrite dans le navigateur.
- **Vider après « Générer »** : texte et images quittent les champs une fois la demande acceptée.
- **Plusieurs photos d'un coup** en Éditer, jusqu'à la limite de 10.
- **Cadenas** aussi visible que Rafraîchir ; **pastille** qui tient dans sa bulle.

## Récits d'utilisation

« Je » désigne le porteur, sur le Mac ou sur son téléphone (application installée, adresse HTTPS de Tailscale pour
l'espace privé).

### Deux espaces étanches

1. Je veux que rien de ce que je fais dans l'espace privé (galerie, file, saisie, prompts enregistrés) n'apparaisse
   dans l'espace public, pour qu'une personne qui ne connaît que le code d'accès n'en voie aucune trace à l'écran.
2. Je veux que rien de l'espace public n'apparaisse dans l'espace privé, pour y travailler sans mélanger les deux.
3. Je veux garder dans les deux espaces les mêmes Réglages (modèle, étapes, taille…), pour ne pas les refaire en
   changeant d'espace.
4. Je veux retrouver les prompts types dans les deux espaces, pour partir d'un prompt prêt à l'emploi partout.
5. Je veux que l'autorisation des notifications soit la même dans les deux espaces, pour ne pas la redonner.

### File d'attente

6. Dans l'espace public, je veux que la liste de la file ne montre aucune génération privée, ni sous son prompt ni
   sous un libellé neutre, pour que rien ne trahisse l'espace privé.
7. Dans l'espace privé, je veux que la liste de la file ne montre aucune génération de l'espace public (normale ou
   incognito), pour ne voir que mon travail privé.
8. Dans l'espace privé, je veux voir chaque génération privée avec le début de son prompt, son mode, son rang dans
   son lot et le temps restant, comme une génération normale dans l'espace public, pour savoir ce qui va passer.
9. Je veux que « +N en attente », dans la pastille du haut, ne compte que les générations de l'espace où je suis.
10. Je veux que la pastille ne montre ni l'étape ni la durée d'une génération de l'autre espace ; si seule une
    génération de l'autre espace tourne et que rien de mon espace n'est en file, la pastille reste éteinte.
11. Quand ma génération attend derrière une génération cachée de l'autre espace, je veux qu'elle affiche « en
    attente » et une durée estimée qui compte ce travail caché, pour savoir honnêtement quand elle sera prête.
12. Je veux que le rang affiché (« 1re en attente », « 2e en attente ») ne compte que les générations de mon espace,
    pour qu'aucun numéro ne trahisse les générations cachées.
13. Dans l'espace public, je veux que les générations incognito des autres appareils restent visibles comme
    aujourd'hui (« Génération incognito », sans prompt ni aperçu), parce qu'elles appartiennent à l'espace public.
14. Dans l'espace privé, je veux annuler une génération privée ou tout un lot privé depuis la liste de la file, quel
    que soit l'appareil qui l'a lancé, comme on annule une génération normale dans l'espace public.
15. Je veux que le message « Ajoutée à la file · Ne en attente », après « Générer », compte seulement les générations
    de mon espace.

### Sortie de l'espace privé et retour

16. Quand je touche « Sortir », je veux que la génération privée en cours quitte l'écran tout de suite (progression,
    aperçu, prompt, vignette, ligne de la file), pour que l'espace public n'en garde rien, avant comme après un
    rechargement.
17. Quand l'espace privé se ferme seul (15 minutes sans requête privée), je veux le même effet que « Sortir » sur les
    générations privées, pour la même raison.
18. Je veux que la génération privée continue sur le Mac après ma sortie et soit rangée dans l'espace privé, pour ne
    pas perdre le calcul.
19. Quand je rentre dans l'espace privé, je veux retrouver les générations privées encore en file ou en cours, avec
    leur prompt et leur progression dans la zone de résultat, pour reprendre où j'en étais.
20. Je veux les retrouver aussi après avoir rechargé la page ou en entrant depuis un autre appareil, pour que le
    rechargement ne me fasse plus perdre le suivi (aujourd'hui : « Génération incognito », sans suivi ni annulation).
21. En entrant dans l'espace privé, je veux que les générations publiques lancées depuis cette page quittent l'écran
    et y reviennent quand je sors, pour retrouver l'espace public tel que je l'ai laissé.
22. Après un rechargement de la page dans l'espace privé, je ne veux pas voir la dernière image de l'espace public
    dans la zone de résultat.
23. Je veux qu'une page sortie de l'espace privé ne puisse plus suivre, prévisualiser ni annuler une génération
    privée, pour que l'étanchéité ne dépende pas seulement de l'écran.

### Prompts enregistrés

24. Dans l'espace privé, je veux enregistrer un prompt (titre et texte) qui ne soit visible que dans l'espace privé,
    pour garder privé ce que je prépare là.
25. Je veux que mes prompts privés soient chiffrés sur le Mac comme mes images privées, pour qu'ils ne se lisent pas
    dans les dossiers ou une sauvegarde Time Machine.
26. Dans l'espace privé, je veux utiliser, modifier et supprimer mes prompts privés, et les voir triés par dernière
    utilisation, comme les prompts de l'espace public.
27. Dans l'espace privé, je veux voir les prompts types et pouvoir en dupliquer un en prompt privé.
28. Dans l'espace privé, je ne veux pas voir les prompts enregistrés de l'espace public.
29. Dans l'espace public, je ne veux voir que les prompts enregistrés publics et les prompts types.
30. Quand je change le code privé, je veux que mes prompts privés restent lisibles avec le nouveau code et seulement
    avec lui, comme les images.
31. Quand je supprime l'espace privé, je veux que mes prompts privés disparaissent avec lui.
32. Je veux filtrer mes prompts privés par mode (Tous, Créer, Éditer, Dessiner) comme les prompts publics.

### Saisie

33. Je veux que chaque espace ait son propre texte et ses propres images, onglet par onglet (Créer, Éditer,
    Dessiner), pour que ce que je tape d'un côté n'apparaisse jamais de l'autre.
34. En entrant dans l'espace privé, je veux trouver la saisie privée que j'y avais laissée (vide la première fois),
    pour reprendre mon travail privé.
35. En sortant de l'espace privé, je veux retrouver ma saisie publique intacte (texte, images, image à retoucher et
    son masque), pour reprendre mon travail public.
36. Je veux que « Sortir » efface la saisie privée, pour que rien n'en reste dans la page.
37. Quand l'espace privé se ferme seul, je veux que la saisie privée quitte l'écran mais reste en mémoire de la page,
    pour la retrouver si je rentre sans avoir fermé l'application (un texte long en cours de saisie n'est pas perdu).
38. Je veux que la saisie privée ne soit jamais écrite dans le navigateur (brouillons compris), pour qu'elle ne
    survive pas à la fermeture de l'application.
39. Je veux que ma saisie publique reste gardée en brouillon comme aujourd'hui, pour la retrouver après un
    rechargement.
40. Je ne veux plus d'onglets « marqués » ni de demande du code privé en touchant « Générer » dans l'espace public,
    puisque rien de privé n'y reste affiché.
41. Quand l'espace privé est supprimé, je veux que la saisie privée gardée en mémoire soit effacée.
41 bis. Quand l'espace privé se ferme seul pendant que je tape, je veux que le champ perde le curseur et qu'un message
   me dise que je suis revenu dans l'espace public, pour que mes touches suivantes ne partent pas dans la saisie
   publique sans que je le voie (ajouté le 15/10/2026 après la revue de sécurité du groupe A).

### Vider après « Générer »

42. Quand le Mac accepte ma demande, je veux que le texte et les images de l'onglet courant soient vidés, pour
    préparer la demande suivante sur une page propre.
43. En Dessiner, je veux que l'image à retoucher et son masque soient vidés aussi.
44. En Éditer, avec la campagne, je veux que les photos soient vidées, l'interrupteur « Campagne » restant tel quel.
45. Si la demande est refusée (erreur du serveur, serveur injoignable, demande annulée avant l'envoi), je veux que
    rien ne soit vidé, pour corriger et relancer sans tout ressaisir.
46. Je veux que le brouillon gardé par le navigateur soit vidé avec le champ, pour qu'un rechargement ne ramène pas le
    prompt déjà lancé.
47. Je veux que les Réglages (modèle, étapes, taille, nombre de variantes, incognito) ne bougent pas.

### Plusieurs photos

48. En Éditer, sur le téléphone, je veux choisir plusieurs photos d'un coup dans le sélecteur et les voir toutes
    ajoutées, dans l'ordre de sélection, pour ne pas les ajouter une à une.
49. Si j'en choisis plus que la limite (10 images, ou 10 photos de campagne), je veux que les premières jusqu'à la
    limite soient ajoutées et que le message dise combien ne l'ont pas été, comme aujourd'hui.

### En-tête

50. Je veux que le cadenas de l'espace privé, dans l'en-tête de la galerie, soit exactement aussi visible que le
    bouton Rafraîchir (même taille d'icône, même couleur, pleine opacité), au même endroit.
51. Je veux que la bulle de la pastille du haut contienne tout son contenu (anneau, étape, durée, « +N en attente »).
52. Si l'écran est trop étroit pour tout contenir, je veux que la pastille affiche « +N » seul plutôt que de dépasser.

## Décisions d'implémentation

### Générales

- Les règles de `CLAUDE.md` valent ici : `secret(job)` pour toute écriture, contrôles d'accès de `H` dans l'ordre pour
  toute nouvelle route (et `Content-Type: application/json` côté interface), `PRIVATE_LOCK` après `finish_rekey()`
  pour toute écriture dans `private/`, rien de l'espace privé dans les journaux du serveur.
- L'« espace d'un appareil » est connu du serveur par la session privée de la requête (`_private_session()`, sans la
  prolonger pour les lectures répétées) : avec une session valide, l'appareil est dans l'espace privé ; sinon dans
  l'espace public. L'interface le sait déjà par `private.unlocked` de `/api/status`.
- L'espace d'une génération : privée (`private`) ou publique (normale ou incognito).

### 1. File d'attente et suivi des générations (serveur)

- `/api/status`, champ `queue` : seulement les générations de l'espace de l'appareil qui lit.
  - Espace public : entrées actuelles des générations normales et incognito (inchangées).
  - Espace privé : une génération privée a une entrée complète, comme une génération normale (identifiant, mode,
    début du prompt, lot complet avec son identifiant), avec le genre `private`.
  - `position` : rang parmi les entrées de cet espace seulement.
  - Nouveau champ par entrée, `ahead` : durée estimée restante (secondes) des générations de l'autre espace placées
    devant elle dans la file (0 s'il n'y en a pas). La génération en cours de l'autre espace compte pour son temps
    restant estimé, les autres pour leur estimation.
- `queued` : nombre de générations en attente de l'espace de l'appareil. `current_job` : identifiant de la génération
  en cours si elle est de cet espace et n'est pas incognito, sinon `null`. `last_job` : dans l'espace public comme
  aujourd'hui, `null` dans l'espace privé. `busy` reste global (le Mac calcule ou non).
- `queue_entry` reste la seule source de l'estimation (`estimate.predict`, pas de troisième copie de la formule).
- Suivi, aperçu et annulation d'une génération privée (`/api/job/<id>`, `/api/job/<id>/preview`,
  `/api/job/<id>/cancel`) et annulation d'un lot privé (`/api/lot/<id>/cancel`) : requête sûre (`_secure`) **et**
  session privée valide exigées ; sinon la réponse est celle d'un identifiant inconnu (404), qui ne révèle pas
  l'existence de la génération. Le suivi ne prolonge pas la session ; l'annulation, oui.
- `queue_position` de `/api/job/<id>` : rang parmi les générations de l'espace de la génération.
- Une génération privée ne passe plus pour incognito dans la file. Les journaux du serveur (`kind_of`) continuent de
  la dire « incognito » : rien de l'espace privé ne va dans `logs/`.
- Notifications : inchangées (neutres).

### 2. File d'attente et suivi des générations (interface)

- La liste de la file affiche les entrées reçues telles quelles ; le libellé « Génération privée » et la
  reconnaissance d'une génération privée par le jeton de la page disparaissent (une génération privée a désormais un
  identifiant dans l'espace privé). Les lignes « Génération incognito » restent pour l'incognito.
- Le temps d'attente d'une entrée et celui affiché dans la pastille ajoutent `ahead` au temps des entrées visibles
  devant elle.
- Pastille : si aucune génération de l'espace ne tourne mais qu'une est en attente, elle affiche « En attente » et la
  durée jusqu'à son début (travail caché compris) ; si l'espace n'a rien en file ni en cours, elle reste éteinte.
- Entrée dans l'espace privé (déverrouillage, ou chargement de la page déjà déverrouillée) : les générations
  publiques de la page quittent l'écran (zone de résultat, rangée de vignettes) mais restent suivies en mémoire de la
  page ; la page suit toutes les générations privées actives de la file (pas seulement celles qu'elle a lancées :
  l'espace privé n'a qu'un propriétaire, et aucun identifiant privé n'est écrit dans le navigateur pour les
  reconnaître après un rechargement).
- Sortie de l'espace privé (« Sortir », fermeture après 15 minutes, suppression de l'espace) : les générations
  privées de la page sont retirées de l'écran et de la mémoire de la page, sans exception pour celle qui tourne ; les
  générations publiques de la page reviennent à l'écran.
- Reprise après un rechargement : dans l'espace public, comme aujourd'hui (identifiants des générations normales
  gardés par le navigateur) ; dans l'espace privé, toutes les générations privées actives de la file, sans afficher
  la dernière image publique.

### 3. Prompts enregistrés privés

- Stockage : un seul fichier scellé dans l'espace privé, `private/prompts`, scellé par `seal()` avec la clé publique
  de l'espace et l'étiquette `prompts` (données associées, comme `<id>/<rôle>` pour les images), contenu JSON : la
  liste des prompts privés, même format qu'un prompt public (`id`, `title`, `text`, `usage`, `used`). Absent tant
  qu'aucun prompt privé n'existe. Écriture sous `PRIVATE_LOCK`, après `finish_rekey()`, dans un fichier temporaire
  puis remplacement atomique, droits 600. Lire ou modifier demande la clé privée de la session.
- Mêmes limites et mêmes validations que les prompts publics (titre 80, texte 4000, 500 prompts, `usage` parmi
  `t2i`, `edit`, `mask`) : `prompt_error` et la logique de `change_prompt` servent aux deux listes.
- Routes : `GET /api/private/prompts` (prompts privés triés par dernière utilisation, et prompts types),
  `POST /api/private/prompts` (création sans `id`, modification avec `id`), `POST /api/private/prompts/delete`,
  `POST /api/private/prompts/used`. Elles suivent les règles des routes privées : `_secure`, session exigée et
  prolongée, rien dans les journaux (le préfixe `/api/private/` est déjà tu).
- Les routes `/api/prompts` restent celles de l'espace public, inchangées : elles ne montrent jamais un prompt privé.
- Changement de code : `rekey_space` rechiffre aussi `prompts` (copie dans `private/.rekey/`, avant la bascule) et
  `finish_rekey` la met à la place de l'ancienne, comme les images ; un fichier déjà illisible est recopié tel quel.
- Suppression de l'espace : `prompts` part avec le reste de `private/`.
- Interface : la feuille des prompts utilise les routes privées quand l'appareil est dans l'espace privé, publiques
  sinon ; « Dupliquer » un prompt type crée un prompt de l'espace courant ; utiliser un prompt privé met à jour sa
  dernière utilisation (aujourd'hui sautée en privé). En incognito (espace public), le comportement actuel ne change
  pas.
- Les prompts enregistrés depuis l'espace privé avant ce changement restent dans la liste publique : pas de
  migration (ils ne se distinguent pas), le porteur les supprime à la main.

### 4. Saisie par espace (interface)

- La page garde deux jeux de saisie, public et privé ; chacun contient, par onglet, le texte, pour Éditer les
  images, pour Dessiner l'image à retoucher et le masque peint. L'interrupteur « Campagne » n'en fait pas partie :
  c'est un réglage, commun aux deux espaces.
- Entrée dans l'espace privé : le jeu public est mis de côté en mémoire, le jeu privé est affiché (vide la première
  fois). Sortie par « Sortir » ou suppression de l'espace : le jeu privé est effacé, le jeu public revient. Fermeture
  après 15 minutes : le jeu privé est mis de côté en mémoire de la page, le jeu public revient ; il réapparaît à la
  prochaine entrée dans la même page.
- Sortie que l'appareil n'a pas demandée (fermeture après 15 minutes, suppression de l'espace depuis le Mac) : le
  champ qui a le curseur le perd et un message dit le retour dans l'espace public ; rien de tel après « Sortir ».
- Brouillons du navigateur (`qwen-<onglet>_prompt`) : écrits seulement pour la saisie publique hors incognito, comme
  aujourd'hui ; jamais pour la saisie privée.
- Le mécanisme des onglets marqués disparaît : `privTabs`, `markTab`, `clearTab`, `renderMarks`, la classe
  `privmark`, `pendingGo` et la note de la feuille de déverrouillage qui en dépend.
- « Reprendre depuis une image » et « Garder celle-ci » remplissent la saisie de l'espace courant.

### 5. Vider après « Générer » (interface)

- Après une réponse acceptée de `/api/generate`, dans les trois modes et les deux espaces : le texte de l'onglet
  courant, ses images (Éditer) ou son image à retoucher et son masque (Dessiner), et son brouillon sont vidés ;
  l'estimation et les aperçus de saisie se mettent à jour comme après un vidage manuel. Les données nécessaires au
  suivi (prompt, vignette d'entrée, dimensions) sont prises avant le vidage.
- Refus (réponse en erreur, serveur injoignable, confirmation « Génération longue » refusée) : rien n'est vidé.

### 6. Plusieurs photos (interface)

- Cause : le gestionnaire `change` du champ de fichiers passe la liste du champ au traitement asynchrone, puis remet
  le champ à zéro, ce qui vide cette même liste ; après la première photo lue, la boucle la trouve vide. La liste des
  fichiers est copiée avant la remise à zéro du champ. Cause lue dans le code, à confirmer par le test.
- Limite inchangée : `MAX_REFS` (10) côté interface, `MAX_CAMPAIGN` (10) côté serveur ; message pour le surplus
  inchangé.

### 7. En-tête et pastille (interface)

- Cadenas `#privEntry` : même taille d'icône, même couleur et pleine opacité que le bouton Rafraîchir de l'en-tête de
  la galerie ; place inchangée.
- Pastille `#island` : la bulle s'adapte à son contenu dans sa largeur maximale ; quand le contenu ne tient pas, la
  pastille d'attente affiche « +N » seul ; rien ne dépasse de la bulle, en particulier dans la vue du téléphone
  (367 px de large).

### 8. Documentation

- `README.md` : file cloisonnée par espace, prompts privés, saisie par espace, vidage après « Générer », API
  (`/api/status` : `queue`, `ahead`, `queued`, `current_job`, `last_job` selon l'espace ; routes de suivi d'une
  génération privée ; routes `/api/private/prompts`) ; retirer la mention « Génération privée » vue par les autres
  appareils et celle des onglets marqués.
- `docs/agents/carte-du-code.md` : suivre les fonctions ajoutées, retirées ou renommées.
- `CLAUDE.md` : ajouter `private/prompts` à ce que couvre `PRIVATE_LOCK` et le rechiffrement, si la ligne
  existante ne suffit pas.

## Décisions de test

- Un bon test vérifie un comportement observable par l'API ou à l'écran, jamais un détail interne : ce que renvoie
  une route selon l'espace de l'appareil, ce qui est écrit sur le disque, ce que l'écran montre. Aucun nouveau point
  de test : on garde les deux qui existent (validé par le porteur le 15/10/2026).
- **Banc du serveur** (`tests/bench.py`, faux moteur, sans GPU), pour l'API :
  - file vue depuis l'espace public et depuis l'espace privé (session ouverte), avec un mélange de générations
    normales, incognito et privées : entrées présentes et absentes, rangs propres à l'espace, `ahead` non nul derrière
    une génération cachée, `queued`, `current_job`, `last_job` ;
  - suivi, aperçu et annulation d'une génération privée et d'un lot privé : 404 sans session, autorisés avec ;
  - prompts privés : création, modification, suppression, utilisation, tri ; absents de `/api/prompts` et inversement ;
    fichier présent et illisible sans la clé (aucun texte en clair dans `private/`) ; lisibles après un changement de
    code avec le nouveau code ; partis avec la suppression de l'espace ; refus sans session et sans requête sûre ;
    rien dans les journaux ;
  - précédents : `test_queue.py`, `test_private_gen.py`, `test_private_lots.py`, `test_private_rekey.py`,
    `test_private_https.py`, `test_prompts.py`.
- **Pilote d'interface** (`tests/ui/`, Chrome sans écran dans la vue du téléphone), pour l'écran :
  - sélection de plusieurs photos d'un coup en Éditer (toutes ajoutées, dans l'ordre ; surplus au-delà de 10 refusé
    avec le message) ;
  - vidage après « Générer » accepté, et pas après un refus ;
  - saisie propre à chaque espace : texte tapé dans l'espace privé absent après « Sortir », saisie publique
    retrouvée ;
  - génération privée qui quitte l'écran à la sortie (zone de résultat, file, pastille) et revient au retour, y
    compris après un rechargement de la page ;
  - cadenas aussi visible que Rafraîchir ; pastille dont le contenu tient dans la bulle (mesure des boîtes) ;
  - précédents : `smoke.test.mjs`, `keep.test.mjs` ; `page.assertNoErrors()` dans chaque test.
- Commande de vérification : `venv/bin/python tests/check.py --ui`.

## Hors périmètre

- Le texte des notifications et ce qu'ouvre le toucher d'une notification d'image privée (inchangés : neutres).
- Cacher que le Mac est occupé (`busy`, attente sans ligne devant) : accepté par le porteur.
- Migrer ou repérer les prompts enregistrés depuis l'espace privé avant ce changement.
- Sélection multiple dans la galerie, et plusieurs images en Dessiner.
- Changer les limites de 10 images et de 10 photos de campagne, ou plafonner la taille des requêtes.
- L'aperçu « Rendre privée » et le reste de la visionneuse.

## Notes

- La fermeture de la page (`pagehide`) et le comportement exact du sélecteur de photos du téléphone se valident sur le
  téléphone : Chrome sans écran ne les rejoue pas de façon fiable.
- Le fichier `private/prompts` est un nouveau fichier du format de l'espace privé (même en-tête `QPV1`, nouvelle
  étiquette) : son format est coûteux à changer une fois des prompts privés enregistrés.
