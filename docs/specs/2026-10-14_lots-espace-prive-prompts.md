# File d'attente, lots, espace privé et prompts enregistrés

Spécification du 14/10/2026, issue d'une séance de questions avec le porteur (toutes les réponses validées). Décisions
de conception liées dans `DECISIONS.md` (« Pas de génération simultanée : une file d'attente », « Espace privé chiffré
à clé publique ») ; vocabulaire dans `GLOSSARY.md`. Statut : **prête pour l'implémentation** ; liste des prompts types
(fin du document) validée par le porteur le 14/10/2026.

## Problème

Aujourd'hui, l'application ne fait qu'une chose à la fois : pendant une génération (souvent plus de 10 minutes),
« Générer » est grisé, et pour obtenir plusieurs images il faut revenir lancer chacune à la main. Le porteur veut :

- lancer d'autres générations sans attendre la fin de la précédente ;
- en mode Créer, obtenir plusieurs images du même prompt pour garder la meilleure ;
- en mode Éditer, appliquer un même prompt à toute une série de photos (6 voitures rouges → 6 voitures bleues), sans
  relancer chaque photo à la main ;
- garder certaines images dans un espace à part, protégé par un code, illisible sur le Mac (Finder, sauvegarde Time
  Machine) et depuis le téléphone pour qui ne connaît que le code d'accès ;
- ne plus retaper les prompts qu'il réutilise, et partir de prompts prêts à l'emploi.

## Solution

- **File d'attente** : « Générer » reste actif ; chaque demande rejoint une file commune au Mac et au téléphone,
  calculée une génération après l'autre (jamais simultanément : le GPU est déjà saturé par une seule). La pastille du
  haut affiche « +N en attente » et ouvre la liste de la file, où l'on annule une génération ou un lot.
- **Lots** : une seule demande peut lancer plusieurs générations, suivies, annulées et notifiées ensemble :
  - **variantes** (mode Créer) : 1 à 4 images du même prompt, chacune avec sa graine, présentées en grille pour
    choisir ;
  - **campagne** (mode Éditer) : jusqu'à 10 photos, chacune éditée seule avec le même prompt, une image par photo, à la
    forme de sa photo.
- **Espace privé** : une galerie séparée, chiffrée sur le disque, ouverte par un code privé propre à chaque appareil.
  Le bouton « Privé » y envoie les générations ; « Rendre privée » y fait entrer une image existante.
- **Prompts enregistrés et prompts types** : une liste, gardée sur le Mac et partagée avec le téléphone, ouverte près
  du champ de texte : on y choisit un prompt, on enregistre le texte en cours, on modifie ou supprime. Des prompts
  types, livrés avec l'application, s'y ajoutent en lecture seule.

## Récits d'utilisation

« Je » désigne le porteur, sur le Mac ou sur son téléphone (application installée).

### File d'attente

1. Je veux pouvoir appuyer sur « Générer » pendant qu'une génération tourne, pour préparer la suivante sans attendre.
2. Je veux que ma nouvelle demande rejoigne la file et soit calculée dès que la précédente se termine, pour ne laisser
   aucun temps mort au Mac.
3. Je veux voir dans la pastille du haut la génération en cours et « +N en attente », pour savoir où en est la file.
4. Je veux toucher la pastille pour ouvrir la liste de la file (miniature de l'entrée ou début du prompt, durée
   estimée, position), pour savoir ce qui va passer et quand.
5. Je veux annuler une génération en attente sans toucher aux autres, pour retirer une demande dont je ne veux plus.
6. Je veux annuler la génération en cours sans perdre celles qui attendent, pour passer à la suivante.
7. Je veux que chaque génération garde les réglages du moment où je l'ai lancée, pour pouvoir changer format,
   résolution ou étapes pour la demande suivante sans modifier celles qui attendent.
8. Je veux voir sur le téléphone la file lancée depuis le Mac (et inversement), pour avoir une seule vue de ce que
   calcule le Mac.
9. Je veux que les générations incognito ou privées d'un autre appareil apparaissent dans la file sans prompt ni
   aperçu (« Génération incognito », « Génération privée »), pour que rien de confidentiel ne s'affiche ailleurs.
10. Je veux que seul l'appareil qui a lancé une génération incognito ou privée puisse la suivre ou l'annuler, pour
    qu'un autre appareil ne voie pas ses aperçus.
11. Je veux qu'une génération normale puisse être annulée depuis n'importe quel appareil, pour arrêter depuis le
    téléphone ce que j'ai lancé sur le Mac.
12. Je veux voir la position d'une génération dans la file se mettre à jour à mesure que la file avance, pour savoir
    combien il en reste devant.
13. Je veux que la durée estimée de la file tienne compte de tout ce qui attend devant ma demande, pour savoir quand
    mon image sera prête.
14. Je veux qu'une image illisible ou une demande invalide fasse échouer seulement sa génération, avec un message,
    pour que la file continue au lieu de rester bloquée jusqu'au redémarrage.
15. Je veux, après avoir rechargé l'application, retrouver le suivi de mes générations normales en cours et en
    attente, pour ne pas perdre le fil.
16. Je veux qu'annuler une génération déjà terminée ne change rien à son image, pour ne pas la perdre par un appui
    tardif.

### Lots (règles communes)

17. Je veux lancer plusieurs générations d'une seule demande, pour ne pas répéter les mêmes gestes.
18. Je veux voir avant de lancer la durée totale estimée du lot, pour décider si je le lance maintenant.
19. Je veux être prévenu par une seule notification à la fin du lot (« 6 images prêtes », « 5 images prêtes,
    1 en échec »), pour ne pas recevoir une notification par image.
20. Je veux qu'un échec sur une image n'arrête pas les autres images du lot, pour récupérer tout ce qui a réussi.
21. Je veux pouvoir annuler soit l'image en cours, soit tout le lot, pour garder la main sur un lot long.
22. Je veux voir pendant le lot quelle image est calculée (« image 3 sur 6 ») et suivre sa progression et son aperçu,
    pour savoir où il en est.
23. Je veux que chaque image du lot arrive dans la galerie comme une image ordinaire (téléchargement, partage, images
    d'entrée, Reprendre, Éditer, Dessiner, Supprimer), pour la traiter comme les autres.
24. Je veux un repère dans la galerie sur les images d'un même lot, et pouvoir les ouvrir ensemble, pour les retrouver
    et les comparer.
25. Je veux un bouton « Tout télécharger » sur un lot, pour récupérer toutes ses images d'un coup.

### Variantes (mode Créer)

26. Je veux choisir dans le mode Créer un nombre d'images de 1 à 4, pour obtenir plusieurs propositions du même
    prompt.
27. Je veux que chaque image ait une graine différente, pour que les propositions diffèrent vraiment.
28. Je veux voir à la fin du lot une grille des images, pour les comparer d'un coup d'œil.
29. Je veux toucher une image de la grille pour l'ouvrir en grand, pour juger les détails.
30. Je veux un bouton « Garder celle-ci » qui supprime les autres images du lot après confirmation, pour ne garder
    que la meilleure.
31. Je veux, si je ne choisis rien, que toutes les images restent dans la galerie, pour pouvoir choisir plus tard.
32. Je veux que la graine de chaque image soit notée avec elle, pour savoir laquelle a donné quoi.

### Campagne (mode Éditer)

33. Je veux activer un interrupteur « Campagne » dans le mode Éditer, pour appliquer le même prompt à chaque photo
    séparément au lieu de les combiner.
34. Je veux importer jusqu'à 10 photos dans une campagne, et être prévenu si j'en ajoute trop, pour savoir lesquelles
    sont prises.
35. Je veux que chaque photo donne une image, éditée avec le seul prompt de la campagne, pour obtenir « les 6 voitures
    en bleu ».
36. Je veux que chaque image suive la forme de sa photo (format pris en charge le plus proche, à la résolution choisie),
    pour qu'une photo en portrait reste en portrait.
37. Je veux que chaque image garde sa photo comme image d'entrée dans la galerie, pour comparer avant et après.
38. Je veux que l'estimation de durée d'une campagne se calcule photo par photo, pour qu'elle soit juste avec des
    photos de tailles différentes.
39. Je veux que l'interrupteur Campagne n'existe pas dans Créer ni dans Dessiner, pour éviter les combinaisons sans
    sens.
40. Je veux, l'interrupteur désactivé, retrouver l'édition actuelle (1 à 10 références combinées en une image), pour
    ne rien perdre de ce qui existe.

### Incognito avec la file et les lots

41. Je veux pouvoir lancer des générations incognito à la suite et des lots incognito, pour garder la même liberté
    qu'en mode normal.
42. Je veux que chaque image incognito me soit remise dès qu'elle est prête puis oubliée par le Mac, pour que rien ne
    reste en mémoire plus que nécessaire.
43. Je veux que recharger ou fermer l'application arrête toutes les générations incognito de cette page, en cours et
    en attente, comme aujourd'hui pour une seule.
44. Je veux voir la grille des variantes incognito sans « Garder celle-ci », et télécharger celles que je veux, puisque
    rien n'est gardé.
44 bis. Je veux qu'une image incognito ne disparaisse qu'après que je l'ai vue au moins une fois puis quittée dans
    l'application pour voir autre chose, et non parce qu'une autre génération démarre ou se termine (précisé par le
    porteur le 14/10/2026).

### Espace privé

45. Je veux créer un espace privé depuis l'application, sur n'importe quel appareil, en choisissant un code privé
    saisi deux fois, la première fois que je touche « Privé ».
46. Je veux que le code privé fasse au moins 8 caractères, lettres permises, pour qu'une copie du disque ne suffise pas
    à le deviner en quelques jours.
47. Je veux que le code privé soit distinct du code d'accès et demandé même sur le Mac, pour que l'accès à l'appli ne
    suffise pas.
48. Je veux déverrouiller l'espace privé sur un appareil sans l'ouvrir sur les autres, pour que le Mac resté allumé ne
    montre pas mes images privées.
49. Je veux qu'un code faux soit suivi d'une attente, pour freiner les essais au hasard.
50. Je veux verrouiller à la main, et que l'espace se verrouille seul après 15 minutes sans activité et à la fermeture
    de l'application, pour ne pas le laisser ouvert par oubli.
51. Je veux, l'espace déverrouillé, un bouton « Privé » à côté de « Générer », qui envoie mes générations dans l'espace
    privé, pour produire directement des images privées.
52. Je veux que « Privé » et « Incognito » s'excluent, pour qu'il n'y ait jamais de doute sur le sort d'une image.
53. Je veux que « Privé » se désactive quand l'espace se verrouille, pour ne pas lancer par erreur une génération
    privée sans le savoir.
54. Je veux voir clairement que le mode Privé est actif, pour ne pas confondre avec le mode normal.
55. Je veux qu'une génération privée lancée continue et soit gardée chiffrée même si l'espace se verrouille avant la
    fin, pour ne pas perdre une génération de 10 minutes.
56. Je veux une galerie privée séparée, ouverte seulement espace déverrouillé, avec la même visionneuse que la galerie
    normale.
57. Je veux que l'image, ses images d'entrée, sa miniature, son prompt et ses réglages soient chiffrés sur le Mac,
    pour que le Finder, une sauvegarde ou une copie du disque ne montrent rien.
58. Je veux qu'aucune trace d'une image privée n'existe en clair ailleurs (journal des images, mesures de
    calibration, journaux du serveur et du moteur), pour que rien ne la trahisse.
59. Je veux que la notification d'une génération privée dise seulement « Image privée prête », pour que rien ne passe
    par le service de notification.
60. Je veux que le prompt d'une génération privée ne soit pas gardé comme brouillon sur l'appareil, comme en
    incognito.
61. Je veux qu'Éditer, Dessiner ou Reprendre à partir d'une image privée force la génération suivante en privé, pour
    que rien ne ressorte en clair par ce chemin.
62. Je veux pouvoir télécharger, partager et copier une image privée, puisque c'est un choix volontaire de la sortir.
63. Je veux un bouton « Rendre privée » dans la visionneuse de la galerie normale, qui chiffre l'image et ses images
    d'entrée et efface les originaux et leur prompt du journal, pour mettre à l'abri une image déjà produite.
64. Je veux être averti en rendant une image privée que les copies déjà faites (Time Machine, téléchargements) ne
    disparaissent pas, pour ne pas me croire protégé à tort.
65. Je veux changer le code privé en donnant l'ancien, sans perdre mes images.
66. Je veux, si j'ai oublié le code, un bouton « Supprimer l'espace privé » qui efface toutes les images privées après
    que j'ai tapé « SUPPRIMER », puis pouvoir en recréer un, pour repartir de zéro.
67. Je veux supprimer une image privée, comme une image normale.
68. Je veux lancer des variantes et des campagnes en privé, pour ne pas renoncer aux lots dans l'espace privé.
69. Je veux que le dossier de travail du Mac soit exclu de Time Machine, pour qu'une sauvegarde qui tombe pendant une
    génération privée ou incognito ne capte pas les fichiers de passage.

### Prompts enregistrés et prompts types

70. Je veux un bouton près du champ de texte qui ouvre la liste de mes prompts, pour les retrouver sans quitter
    l'onglet.
71. Je veux enregistrer le texte en cours sous un titre, pour le réutiliser plus tard.
72. Je veux choisir un prompt de la liste pour qu'il remplace le texte du champ.
73. Je veux modifier le titre et le texte d'un prompt enregistré.
74. Je veux supprimer un prompt enregistré, après confirmation.
75. Je veux retrouver sur le téléphone les prompts enregistrés depuis le Mac (et inversement).
76. Je veux que la liste soit triée par dernière utilisation, pour avoir mes prompts courants en tête.
77. Je veux filtrer la liste par usage (Créer, Éditer, Dessiner), l'usage étant celui de l'onglet où le prompt a été
    enregistré, tout en pouvant utiliser n'importe quel prompt dans n'importe quel onglet.
78. Je veux une section de prompts types livrés avec l'application, en lecture seule, pour partir d'exemples qui
    marchent.
79. Je veux « Dupliquer » un prompt type en prompt enregistré modifiable, pour l'adapter.
80. Je veux qu'en insérant un prompt, le premier passage entre crochets soit sélectionné, pour le remplacer en tapant
    directement.
81. Je veux qu'un prompt enregistré ne garde que son titre et son texte, pas les réglages, pour qu'il serve à tous les
    formats.

## Décisions d'implémentation

### Générales

- Le serveur reste un seul fichier en bibliothèque standard, plus Pillow, NumPy et, pour l'espace privé,
  `cryptography` (déjà installée avec `pywebpush`). L'interface reste un seul fichier HTML sans build.
- Toute nouvelle route POST passe par les contrôles existants (liste blanche de `Host`, contrôle d'origine,
  `Content-Type: application/json`, cookie d'accès) ; l'interface envoie toujours `Content-Type: application/json`.
- Tout nouveau comportement visible et chaque nouvelle route sont décrits dans le README, dans le même commit.
- Ordre de livraison : (1) file d'attente et robustesse, (2) variantes, (3) campagne, (4) prompts enregistrés et
  types, (5) espace privé. Chaque étape se livre et se teste seule.

### 1. File d'attente et robustesse

- Le serveur garde un seul thread de calcul et une seule génération à la fois.
- **Robustesse** : toute exception pendant la préparation ou l'exécution d'une génération (construction de la ligne de
  commande, lecture d'une image, ouverture du journal du moteur) passe la génération en `failed` avec un message
  lisible, nettoie son dossier de travail si elle est incognito ou privée, et laisse le thread prendre la suivante.
  `/api/generate` valide aussi en entrée les champs numériques (largeur, hauteur, étapes, graine) et le type du prompt,
  et répond 400 avec un message plutôt que d'accepter une demande qui échouera.
- **Annulation** : annuler une génération terminée (`done`, `failed`, `cancelled`) ne change rien. Seules les
  générations `queued` et `running` passent à `cancelled`.
- **Position** : la position dans la file est calculée à chaque lecture d'une génération, et non figée à sa création.
- **Liste de la file** : `/api/status` renvoie `queue`, une liste ordonnée (en cours d'abord) dont chaque entrée
  porte : `status`, `position`, `mode`, `lot` (identifiant et rang « k sur N », ou rien), l'estimation de durée et,
  pour une génération normale seulement, son `id` et le début de son prompt. Pour une génération incognito ou privée,
  l'entrée ne porte que `status`, `position`, `lot` et un genre (`incognito` ou `private`) : ni `id`, ni prompt, ni
  aperçu. `current_job` cesse d'exposer l'identifiant d'une génération incognito ou privée (piste ouverte du
  13/10/2026 réglée par la même occasion).
- Une page suit les générations qu'elle a lancées par les identifiants reçus de `/api/generate` ; après un
  rechargement, elle se rattache aux seules générations normales qu'elle a lancées elle-même (identifiants gardés côté
  page ; décision du porteur du 14/10/2026 après la revue de groupe A) : celles d'un autre appareil restent visibles
  dans la feuille de la file sans être reprises. Les générations incognito et privées ne se rattachent pas
  (comportement actuel de l'incognito). Une entrée incognito ou privée de `queue` porte un jeton opaque propre à la
  page qui l'a lancée, pour que cette page reconnaisse ses lignes sans que la ligne identifie la génération.
- **Interface** : « Générer » n'est plus désactivé pendant une génération ; un appui lance une nouvelle demande, avec
  les réglages du moment. La zone de résultat suit la plus ancienne génération non terminée lancée par cette page,
  puis passe à la suivante ; les résultats arrivent au fur et à mesure. La pastille affiche la génération en cours et
  « +N en attente » ; la toucher ouvre une feuille listant la file, avec un bouton d'annulation par génération (et par
  lot), seulement là où l'appareil y a droit (récit 10 et 11).
- Le bouton Incognito n'est plus bloqué pendant une génération : il peut changer entre deux demandes, et chaque
  génération garde le mode de son lancement (comme les autres réglages).
- **Incognito et file** (précisé par le porteur le 14/10/2026) : une image incognito n'est perdue qu'une fois vue au
  moins une fois puis quittée dans l'application pour voir autre chose (ouvrir une autre image ou un autre résultat,
  changer de vue). Côté page : lancer une nouvelle demande, ou qu'une autre génération se termine, ne fait plus
  disparaître l'image incognito affichée ni celles pas encore vues ; elles restent dans la page (adresses `blob:`)
  jusqu'à ce que l'utilisateur les ait vues puis quittées. Côté serveur : la purge des générations incognito
  terminées à chaque nouvelle demande disparaît ; le serveur garde une image incognito en mémoire jusqu'à ce que la
  page qui l'a lancée la récupère puis la fasse oublier, ou jusqu'à la fermeture de cette page, ou au redémarrage, et
  au plus 24 h après la fin de sa génération si elle n'a jamais été récupérée (page tuée sans prévenir ; décision du
  porteur du 14/10/2026). L'identifiant d'une génération incognito (et privée) est long et tiré au hasard (au moins
  128 bits), pour qu'un appareil connecté ne puisse pas le deviner.
  À la fermeture ou au rechargement, la page annule et fait oublier, en un seul envoi `keepalive`, toutes ses
  générations incognito (et privées) non terminées ou non récupérées.
- L'estimation de la file additionne les estimations des générations qui précèdent ; l'interface la calcule avec ses
  coefficients habituels à partir des réglages de chaque entrée, renvoyés par `queue`.

### 2. Lots et variantes

- **Contrat** : `/api/generate` accepte, en plus des champs actuels, `count` (1 à 4, mode Créer seulement) et
  `campaign` (voir 3). Le serveur crée alors une génération par image, toutes reliées par un identifiant de lot,
  et renvoie le lot (`lot`, liste des générations publiques). Une demande sans `count` ni `campaign` reste une
  génération seule, sans lot. Les générations d'un lot passent dans la file à la suite, dans l'ordre.
- **Graines** : quand la graine demandée est aléatoire, le serveur la tire lui-même (au lieu de laisser sd-cli la
  tirer) et la passe à sd-cli, pour qu'elle soit connue et écrite dans le journal des images. Les variantes d'un lot
  reçoivent des graines distinctes.
- **Journal des images et galerie** : la ligne du journal porte l'identifiant du lot, son rang et la graine ;
  `/api/history` renvoie `lot` (identifiant, rang, taille) pour chaque image d'un lot.
- **Annuler le lot** : nouvelle route POST `/api/lot/<id>/cancel`, qui annule toutes les générations non terminées du
  lot (mêmes droits que l'annulation unitaire : une génération incognito ou privée seulement depuis la page qui
  connaît son lot).
- **Notification** : une seule par lot, envoyée quand sa dernière génération se termine : « N images prêtes »,
  « N images prêtes, M en échec », ou « Échec du lot » si aucune n'a réussi ; variantes incognito et privées :
  « N images incognito prêtes », « N images privées prêtes ». Aucune notification si tout le lot a été annulé. Une
  génération seule garde les messages actuels. Jamais de prompt ni de nom de fichier dans la notification.
- **Galerie** : un badge sur la miniature des images d'un lot (« 2/4 ») ; la visionneuse offre « Voir le lot » (les
  images du lot, côte à côte, puis en grand) et « Tout télécharger », qui enchaîne les téléchargements des images
  du lot (pas d'archive zip).
- **Variantes dans l'interface** : un sélecteur « Images : 1 2 3 4 » dans le mode Créer, retenu dans les réglages ;
  l'estimation affiche la durée totale. À la fin du lot, une grille des images remplace l'image unique dans la zone de
  résultat ; toucher une image l'ouvre dans la visionneuse avec « Garder celle-ci », qui demande confirmation puis
  supprime les autres images du lot par la route de suppression existante. En incognito, la grille n'a pas « Garder
  celle-ci » ; chaque image a son téléchargement.

### 3. Campagne

- **Contrat** : `campaign` est une liste de 1 à 10 entrées, chacune portant son image et ses dimensions de sortie ;
  elle n'est acceptée qu'en mode Éditer. Chaque entrée devient une génération du mode Éditer avec cette seule image en
  référence et le prompt commun. Les dimensions sont calculées par l'interface : format pris en charge le plus proche
  de la forme de la photo (la fonction qui choisit déjà le format le plus proche), à la résolution des Réglages,
  côtés multiples de 32.
- Chaque image produite garde sa photo comme image d'entrée, par le mécanisme de conservation existant.
- **Interface** : un interrupteur « Campagne » dans l'onglet Éditer. Activé : le compteur devient « n photos », la
  limite reste 10 et un dépassement est signalé (aujourd'hui l'import s'arrête sans message à 10), le choix du format
  disparaît des Réglages (chaque photo a le sien), et l'estimation additionne les photos une à une. L'interrupteur est
  retenu dans les réglages ; désactivé, l'édition actuelle est inchangée.

### 4. Prompts enregistrés et prompts types

- **Stockage** : les prompts enregistrés vivent dans un fichier JSON du Mac à côté de la configuration, non suivi par
  git (ajouté au `.gitignore`) ; écriture dans un fichier temporaire puis renommage, pour ne jamais laisser un fichier
  à moitié écrit. Les prompts types vivent dans un fichier JSON suivi par git, en lecture seule pour le serveur.
- **Forme d'un prompt enregistré** : identifiant, titre, texte, usage (`t2i`, `edit` ou `mask`, l'onglet
  d'enregistrement), date de dernière utilisation. Forme d'un prompt type : identifiant, titre, texte, usage.
- **Contrat** : `GET /api/prompts` renvoie `{saved, types}`, `saved` trié par dernière utilisation ; POST
  `/api/prompts` crée ou modifie (avec `id`) un prompt enregistré ; POST `/api/prompts/delete` le supprime ; POST
  `/api/prompts/used` met à jour sa dernière utilisation. Titre et texte non vides, longueurs bornées ; 400 sinon.
- **Interface** : un bouton à côté du champ de texte ouvre une feuille avec un filtre par usage (« Tous » par défaut),
  la liste des prompts enregistrés (titre, début du texte, Modifier, Supprimer), « Enregistrer le texte actuel », puis
  la section « Prompts types » (Dupliquer). Choisir un prompt remplace le texte du champ, sélectionne le premier
  passage entre crochets s'il y en a un, et met à jour la dernière utilisation. La suppression passe par la feuille de
  confirmation existante.
- Les prompts enregistrés restent hors de l'espace privé : enregistrer un prompt est un geste explicite, permis en
  incognito et en privé.

### 5. Espace privé

- **Chiffrement** (voir `DECISIONS.md`) : à la création, le serveur tire une paire de clés X25519. La clé publique est
  gardée en clair ; la clé privée est chiffrée en AES-256-GCM par une clé tirée du code privé par scrypt (paramètres
  coûteux, sel aléatoire). Chaque fichier privé est chiffré à part : clé éphémère X25519, accord avec la clé publique,
  dérivation HKDF, AES-256-GCM. Le serveur chiffre donc sans connaître le code ; seule la lecture demande la clé
  privée. Le code privé est pris tel que saisi (pas de passage en minuscules), 8 caractères au moins.
- **Stockage** : un dossier propre à l'espace privé, à la racine du projet, hors de `outputs/` (donc invisible pour la
  galerie normale), ajouté au `.gitignore`. Par image : l'image, ses images d'entrée, sa miniature et ses
  métadonnées (prompt, réglages, dimensions, graine, lot, date, durée) dans un fichier chiffré, sous un nom tiré au
  hasard qui ne révèle ni la date ni le mode. Rien d'autre sur le disque.
- **Sessions** : déverrouiller (POST `/api/private/unlock` avec le code) déchiffre la clé privée et ouvre une session
  propre à l'appareil : un cookie de session distinct du cookie d'accès (HttpOnly, sans durée de vie, donc perdu à la
  fermeture du navigateur), la clé privée restant en mémoire du serveur pour cette session seulement. La session
  expire après 15 minutes sans requête privée ; POST `/api/private/lock` la ferme, et l'interface l'envoie aussi à la
  fermeture de la page (`keepalive`). Un code faux attend 1 seconde, comme le code d'accès.
- **Autres routes** : POST `/api/private/create` (seulement s'il n'existe pas d'espace) ; POST `/api/private/code`
  (ancien et nouveau code : la clé privée est rechiffrée, les images ne sont pas touchées) ; POST
  `/api/private/reset` (exige le texte `SUPPRIMER`, efface tout l'espace et ferme toutes les sessions) ;
  `GET /api/private/history` (liste déchiffrée, session exigée) ; lecture d'une image privée, de sa miniature et de ses
  images d'entrée, avec téléchargement (session exigée) ; POST `/api/private/delete` ; POST `/api/private/adopt`
  (« Rendre privée », session exigée). `/api/status` indique si l'espace existe et s'il est déverrouillé pour cet
  appareil. Sans `cryptography`, ces routes répondent qu'elles ne sont pas disponibles et l'interface masque tout ce
  qui touche à l'espace privé.
- **Génération privée** : `/api/generate` avec `private: true` exige une session privée valide au lancement
  (sinon 403). Le dossier de travail est un dossier de travail privé, supprimé en fin de génération et au démarrage,
  comme pour l'incognito ; le journal du moteur va à la poubelle (`os.devnull`) ; aucune ligne dans le journal des
  images, aucune mesure de calibration, aucun détail dans `logs/`. En fin de génération réussie, l'image, la miniature
  (fabriquée en mémoire), les images d'entrée et les métadonnées sont chiffrées avec la clé publique, puis les fichiers
  en clair supprimés. Le résultat est lu ensuite par la galerie privée, avec la session. Toute nouvelle écriture sur le
  disque ou dans les journaux doit respecter cette règle, comme pour l'incognito.
- **Héritage** : quand Éditer, Dessiner ou Reprendre part d'une image privée, l'onglet est marqué « privé » jusqu'à la
  génération suivante, qui part forcément en privé ; si l'espace s'est verrouillé entre-temps, l'interface demande de
  le déverrouiller au lieu de lancer en clair.
- **Rendre privée** : l'image, ses images d'entrée et ses métadonnées (tirées de sa ligne du journal) sont chiffrées
  dans l'espace privé, puis le PNG, ses miniatures, ses images d'entrée et **sa ligne du journal** sont supprimés (le
  journal est réécrit sans elle). L'interface avertit avant que les copies déjà faites (Time Machine, téléchargements)
  restent. Pas de chemin inverse.
- **Interface** : un bouton « Privé » à côté de « Générer » (avec « Incognito »), exclusif de lui. Touché quand
  l'espace n'existe pas : feuille de création (code deux fois) ; quand il est verrouillé : feuille de déverrouillage,
  avec « Supprimer l'espace privé » (saisie de `SUPPRIMER`) et « Changer le code ». Mode Privé actif : bouton allumé et
  cadenas dans la pastille. La galerie a une entrée « Privé » (cadenas) qui ouvre la galerie privée après
  déverrouillage, avec un bouton « Verrouiller ». Brouillon du prompt non gardé en mode Privé. Le mode Privé
  n'est pas retenu d'une visite à l'autre (il exige de toute façon un déverrouillage).
- **Time Machine** : au lancement du serveur sur Mac, le dossier de travail est exclu de Time Machine par
  `tmutil addexclusion` (sans droits administrateur) ; un échec est noté dans le journal du serveur sans bloquer le
  démarrage.
- **Notifications** : « Image privée prête » ou, pour un lot, « N images privées prêtes ».

## Décisions de test

- **Un bon test** vérifie un comportement visible de l'extérieur : réponse d'une route, fichier présent ou absent sur
  le disque, contenu lisible ou non, message de notification. Il ne s'appuie pas sur les noms des fonctions internes.
- **Point d'entrée principal : l'API locale avec un faux moteur.** Un banc permanent dans `tests/`, en bibliothèque
  standard (`unittest`), sans GPU : il importe le serveur, repointe ses dossiers vers un dossier temporaire, installe
  un faux sd-cli (script Python qui imprime les lignes de progression et « … completed, taking x.xxs », écrit les
  aperçus et l'image demandée, et sait échouer ou durer sur commande), sert le serveur sur un port libre avec son
  thread de calcul, et l'interroge en HTTP avec les en-têtes qu'exige le contrôle d'accès. Les notifications sont
  vérifiées en interceptant l'envoi (sans réseau), comme pour la mise en place du Web Push. Il remplace le banc jetable
  décrit dans `CLAUDE.md`, mis à jour pour donner la commande. Prior art : le banc jetable décrit dans `CLAUDE.md`, et
  le style d'appel HTTP de `tests/run_tests.py` (qui reste le test de bout en bout sur le vrai GPU, lancé seulement sur
  demande).
- **Ce que le banc couvre**, par étape :
  1. file : plusieurs demandes à la suite, ordre de calcul, positions qui avancent, annulation en file et en cours,
     annulation d'une génération terminée sans effet, demande invalide refusée (400), image illisible qui échoue sans
     bloquer la suivante, `queue` sans `id` ni prompt pour l'incognito, `current_job` muet pour l'incognito ;
  2. variantes : N générations reliées par un lot, graines distinctes écrites au journal, une seule notification (et
     son texte avec un échec), annulation du lot, `count` refusé hors du mode Créer ;
  3. campagne : une génération par photo, chacune avec sa seule photo en entrée et ses dimensions, images d'entrée
     conservées, `campaign` refusée hors du mode Éditer et au-delà de 10 ;
  4. prompts : créer, modifier, supprimer, tri par dernière utilisation, prompts types en lecture seule, refus des
     entrées invalides, fichier jamais à moitié écrit ;
  5. espace privé : création, code trop court refusé, déverrouillage faux puis juste, session propre à un client,
     génération privée refusée sans session, après génération aucun fichier en clair ni dans `outputs/`, ni dans le
     journal, ni dans la calibration, ni dans `logs/`, ni dans le dossier de travail ; les octets de l'image n'existent
     nulle part en clair sur le disque ; image lisible avec la session et illisible sans ; génération terminée après
     verrouillage puis lue après un nouveau déverrouillage ; changement de code ; « Supprimer l'espace privé » ;
     « Rendre privée » qui retire aussi la ligne du journal ; expiration de session (horloge raccourcie dans le banc).
- **Interface** : à chaque étape, Chrome sans écran piloté par le protocole DevTools depuis Node, branché sur le
  serveur du banc, aux dimensions du téléphone du porteur (367×760, densité 2,5, mobile, tactile, mode allégé), avec
  captures regardées : feuille de la file, grille des variantes, interrupteur Campagne, feuille des prompts,
  création, déverrouillage et galerie de l'espace privé. Ces contrôles ne sont pas gardés dans le dépôt.
- Contrôles du projet après chaque changement : compilation Python des fichiers touchés et `node --check` sur les
  scripts extraits de l'interface (voir `CLAUDE.md`), plus le banc.

## Hors périmètre

- Calcul simultané de plusieurs générations, et production des variantes d'un seul lancement de sd-cli (`-b N`) :
  écartés dans `DECISIONS.md`.
- Variantes en mode Éditer ou Dessiner, campagne en mode Dessiner, image commune ajoutée à chaque photo d'une
  campagne, campagne de plus de 10 photos.
- Téléchargement d'un lot en archive zip.
- Formulaire de variables pour les prompts types (les crochets se remplacent à la main) ; prompts enregistrés dans
  l'espace privé ; prompts types modifiables.
- Sortie d'une image de l'espace privé vers la galerie normale (on la télécharge) ; récupération d'un code privé
  oublié ; disque en mémoire vive pour éviter le passage en clair des fichiers de travail.
- Survie de la file à un redémarrage du serveur (les générations ne survivent pas, comme aujourd'hui).
- Retrait des lignes du journal des images supprimées normalement (hors « Rendre privée ») : comportement actuel
  inchangé.

## Notes

- **Limite assumée** : sd-cli ne lit et n'écrit que des fichiers. Les entrées et l'image d'une génération privée ou
  incognito passent donc en clair dans le dossier de travail pendant le calcul (et ses aperçus), puis sont supprimées.
  Sur un SSD, un fichier supprimé n'est pas effacé de façon sûre. À écrire dans le README.
- **Supprimer l'espace privé** ne demande pas le code (c'est son but quand on l'a oublié) : quiconque a l'application
  peut donc effacer l'espace privé, sans pouvoir le lire. Confirmation par la saisie de `SUPPRIMER`.
- Un lot de N images dure N fois une image : une campagne de 10 photos à 720p et 40 étapes dure plus d'une heure et
  demie ; la confirmation au-delà d'une heure, qui existe déjà, s'applique à la durée totale du lot.
- Pièges de `CLAUDE.md` à revoir à la livraison : « Exception dans un job » (réglé par l'étape 1), banc jetable (devient
  le banc de `tests/`), mode incognito (la règle « toute nouvelle écriture » s'étend à l'espace privé).

## Prompts types (validés par le porteur le 14/10/2026)

| Titre | Usage | Texte |
|---|---|---|
| Repeindre | Éditer | Repeins [l'objet] en [couleur], en gardant les reflets, les ombres et tout le reste de l'image identique. |
| Changer l'arrière-plan | Éditer | Remplace l'arrière-plan par [nouveau décor], en gardant le sujet, sa position et son éclairage inchangés. |
| Retirer un élément | Éditer | Retire [l'élément] de l'image et reconstitue le fond de façon naturelle. |
| Fond blanc produit | Éditer | Place le produit sur un fond blanc uni de studio, avec une ombre douce au sol, sans changer le produit. |
| Style aquarelle | Éditer | Transforme l'image en peinture à l'aquarelle, couleurs douces, papier texturé, en gardant la composition. |
| Heure dorée | Éditer | Change la lumière pour une fin de journée dorée, ombres longues et chaudes, sans changer le contenu. |
| Ajouter un texte | Éditer | Ajoute le texte « [texte] » sur [l'emplacement], dans une typographie [style] lisible et bien intégrée. |
| Photo réaliste | Créer | Photo réaliste de [sujet], [lieu], lumière naturelle, objectif 50 mm, faible profondeur de champ, détails nets. |
| Portrait studio | Créer | Portrait studio de [personne], éclairage doux à trois points, fond [couleur] uni, regard vers l'objectif. |
| Illustration plate | Créer | Illustration vectorielle plate de [sujet], palette limitée de [couleurs], formes simples, sans texte. |
| Remplacer la zone | Dessiner | Remplace la zone peinte par [élément], en accordant la lumière et la perspective avec le reste de l'image. |
