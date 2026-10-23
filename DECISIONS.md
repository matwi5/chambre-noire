# Décisions de conception

Une entrée par décision, la plus récente en tête. Une décision remplacée garde son entrée, avec le statut
« remplacée le <date> ». Entrées antérieures au 13/10/2026 reconstituées depuis le README, les commentaires du code et
les messages de commit.

## 2026-10-23 · Journal du serveur : connexions coupées, refus de génération et suppressions sans trace propre

- **Contexte** : la passe « bogues » des suites du groupe A relève trois traces antérieures à la refonte, dans le
  journal du serveur (`logs/service.log`), qui laissent encore deviner l'espace privé.
- **Décision** (porteur, 23/10/2026, réponse « ok pour tes reco » aux recommandations) :
  - « Erreurs de connexion coupée » (traceback de Python qui nomme `_private_get`, l'adresse du téléphone et un chemin
    `/Users/…`) → recommandation acceptée : toutes remplacées par une ligne neutre, « [ui] connexion interrompue » ;
  - « Refus que seul l'espace privé déclenche » (`POST /api/generate` refusé en 403 ou 503) → « (a) » : taire toutes
    les requêtes `/api/generate` dans le journal, même en erreur (ses 400 compris) ;
  - « La ligne [historique] supprimé : <nom> » (écrite pour la seule suppression d'une image normale) →
    recommandation acceptée : ligne supprimée.
- **Écarté** : ne taire que les refus propres au privé ; garder le détail des erreurs de connexion.
- **Conséquences** : les refus d'accès d'une demande de génération (401, 403, 415) ne sont plus suivis dans `logs/` ;
  une requête est tue d'après son chemin seul (une chaîne de requête ne fait rien taire) ; une erreur d'écriture que
  macOS rend en simple `OSError` (EPROTOTYPE, ENOTCONN) compte comme une connexion coupée.

## 2026-10-23 · Suites du groupe A : journal muet sur les réussites, ancien réglage incognito, page hors ligne

- **Contexte** : après la fusion du groupe A (retrait de l'incognito), sa session relève que le journal du serveur
  (`logs/`) distingue encore une génération privée d'une normale, et qu'un ancien réglage incognito du navigateur est
  ignoré sans message ; la session du groupe F relève que la page « Ordinateur injoignable » de `tools/ui/sw.js` garde
  les anciennes couleurs, hors du périmètre de la spec.
- **Décision** (porteur, 23/10/2026, réponse « ok pour tes reco » aux recommandations) :
  - « Page « Ordinateur injoignable » : on l'ajoute au ticket des couleurs du groupe C ? » → oui (recommandation :
    « Oui ») ;
  - « Le journal du serveur trahit encore les générations privées » (« [job] PNG enregistré : <chemin>… » et
    « [calibration] … » écrites pour une génération normale seulement ; `POST /api/generate` suivi de `/api/result`
    et `/api/thumb` pour une normale seulement) → « (b) » : une même ligne pour toutes les réussites (« [job]
    génération terminée », sans chemin ni durée), plus de ligne de calibration, et le journal du serveur ne garde plus
    que les requêtes en erreur (4xx, 5xx) ;
  - « Ancien réglage incognito resté dans le navigateur » → oui : un message affiché une seule fois au chargement
    (« L'incognito n'existe plus : vos images sont enregistrées. Pour la confidentialité, passez par l'espace
    privé. »), puis le réglage est effacé.
- **Écarté** : garder le détail des réussites ou la trace des requêtes réussies dans `logs/` ; ignorer l'ancien réglage
  sans message ; laisser la page hors ligne aux anciennes couleurs.
- **Conséquences** : la session du groupe A fait les deux changements du journal et du message comme mise à jour du
  ticket « Refuser l'incognito au serveur et rendre neutres les échecs du journal » ; la page hors ligne entre dans le
  ticket « Passer l'interface en lumière inactinique, sombre seulement » (groupe C).

## 2026-10-22 · Icône de l'application : le paysage en carrés sous la lumière inactinique

- **Contexte** : groupe F de la refonte (ticket « Choisir et intégrer la nouvelle icône pixel ») ; le porteur avait
  demandé au cadrage de garder le paysage en carrés « mais tester B et C (plusieurs versions) ». Choix fait dans la
  session du groupe, sur deux planches ; phrases du porteur relayées par le compte rendu de la session.
- **Décision** (porteur, 22/10/2026) : « Quelle icône retiens-tu pour Chambre noire ? »
  - première planche (A1 et A2 : paysage recoloré ; B1 lampe, B2 cuve, B3 film ; C1 tirage à marge, C2 tirage qui
    sèche) → « J'aime bien A1, A2 et C2. C2 n'est pas adapté pour la version ronde, modifie. Fait moi d'autre
    porpositions dans cette directement en gardant ces 3 là » ;
  - deuxième planche (A1, A2, C2 recentré, A3, A4, A5, C3, C4) → « A1 · paysage recoloré ».
  - Palette de l'icône : plaque mate `#0d0a08`, halo rouge `#be1c12`, grain léger, soleil ambre `#ffa53a`, montagnes
    papier `#f1e6d2` ; `tools/ui/logo.svg` reste la source des quatre PNG (192 et 512 à coins transparents, adaptable
    et Apple en plein cadre).
- **Écarté** : les motifs lampe, cuve et film ; le paysage dans un cadre de tirage ; les autres variantes du paysage.

## 2026-10-22 · Retrait de l'incognito : journaux sans détail, restes incognito supprimés au démarrage

- **Contexte** : session du groupe A de la refonte (retrait de l'incognito). La spec rend neutres les trois lignes
  d'échec d'une génération dans le journal du serveur et retire le ménage des dossiers `jobs/incognito_*` au démarrage ;
  la session relève deux autres lignes qui distinguent encore une génération privée, et un reste possible en clair.
- **Décision** (porteur, 22/10/2026, dans la session du groupe A) :
  - « Journal du serveur : la spec rend neutres les trois lignes d'échec d'une génération (fait). Deux autres lignes
    donnent encore un détail pour une génération normale et rien pour une privée, donc les distinguent : « [job] erreur
    du thread de calcul : <erreur> » et « [push] notification du lot impossible : <erreur> ». Les rendre neutres
    aussi, sans détail pour personne ? » → « Oui, neutres aussi (Recommandé) » ;
  - « La spec retire aussi le ménage au démarrage des dossiers jobs/incognito_*. Un tel dossier ne reste que si
    l'ancien serveur s'est arrêté brutalement pendant une génération incognito ; il contient alors images d'entrée et
    PNG en clair, et le nouveau serveur ne le supprimerait plus. Que faire ? » → « Garder ce ménage (Recommandé) ».
- **Écarté** : garder le détail de ces deux lignes pour les générations normales ; retirer le ménage de
  `jobs/incognito_*` comme la spec le prévoyait.
- **Conséquences** : `tools/launch.py` écrit « [job] erreur du thread de calcul » et « [push] notification du lot
  impossible » sans détail pour toutes les générations, et supprime toujours `jobs/incognito_*` au démarrage.

## 2026-10-22 · Refonte : groupes B et C en parallèle, icône à part

- **Contexte** : les cinq groupes de la refonte touchent tous `README.md`, et tous sauf l'icône `tools/ui/index.html`
  ou `tools/launch.py` ; la règle du tableau de bord les ferait tourner l'un après l'autre. B (pile côté serveur :
  journal, galerie, espace privé de `launch.py`) et C (CSS d'`index.html`, `LOGIN_PAGE` et `PUBLIC_FILES` de
  `launch.py`, section « Crédits et licences » du README) ne modifient pas les mêmes zones.
- **Décision** (porteur, 22/10/2026) : « Le meilleur enchaînement possible serait donc : A, puis B et C en même temps,
  puis D, puis E, avec l'icône à côté dès maintenant. » → « ok ». L'icône devient le groupe F, lançable tout de suite.
- **Conséquences** : B et C partent tous deux de `dev` après la fusion de A ; le second fusionné dans `dev` règle les
  conflits de texte de `launch.py`, `README.md` et `docs/agents/carte-du-code.md`, puis relance `tests/check.py --ui`
  avant le commit de fusion.

## 2026-10-22 · Pile : emplacement des images à trier, effacement complet, journaux neutres

- **Contexte** : rédaction de la spec de la refonte (`docs/specs/2026-10-22_refonte-chambre-noire.md`). Faits lus dans
  `tools/launch.py` : le journal ne fait que s'allonger ; « Supprimer » laisse la ligne du journal (avec le prompt) et
  le dossier de travail `jobs/<id>/` ; une image privée est un dossier de fichiers scellés chacun à part (`meta`,
  image, vignette, entrées) ; un échec privé s'écrit « génération incognito » dans `logs/`, déguisement qui ne tient
  plus sans l'incognito.
- **Décision** (porteur, 22/10/2026, réponse « 1 oui, 2 a, 3 a, 4 oui, 5 oui, 6 a ») :
  - « Points de test » (banc du serveur et pilote d'interface, plus une aide de balayage tactile dans le pilote) →
    « oui » ;
  - « Où vit une image publique à trier, et ce que Jeter efface » → « a » : dans `outputs/.pile/` ; Garder la déplace
    dans `outputs/` en une opération atomique ; Jeter efface PNG, vignette, images d'entrée, dossier de travail
    `jobs/<id>/` et ligne du journal (réécrit sous `JOURNAL_LOCK`, fichier temporaire puis remplacement) ; les images
    d'avant restent dans `outputs/`, tirages d'office ;
  - « La marque « à trier » d'une image privée » → « a » : dans sa fiche chiffrée (`meta`), que Garder déchiffre,
    modifie et rescelle sous `PRIVATE_LOCK` après `finish_rekey()`, sans toucher à l'image ni à la vignette ;
  - « « Supprimer » un tirage » (aussi complet que Jeter ?) → « oui » ;
  - « Deux appareils trient la même image » (premier arrivé l'emporte, le second reçoit 404 « déjà triée » ; Jeter ne
    vise que la pile ; bandeau Annuler dans la page seulement) → « oui » ;
  - « Lignes d'échec dans le journal du serveur » → « a » : tous les échecs écrivent la même ligne neutre (« échec :
    génération, sd-cli code N » ou « échec : génération, erreur de préparation »), le détail reste en mémoire pour
    l'interface.
- **Décision** (porteur, 22/10/2026, à la relecture de la spec, réponse « 1 oui, 2 oui, 3 oui ») :
  - « Si tu changes d'espace pendant le bandeau Annuler, la demande Jeter part dans l'espace où elle a commencé. Si
    cet espace s'est fermé entre-temps, elle est abandonnée et l'image reste dans la pile. D'accord ? » → « oui » ;
  - « Un seul bandeau à la fois : jeter une deuxième image envoie tout de suite la suppression de la première, dont le
    délai d'annulation s'arrête là. D'accord ? » → « oui » ;
  - « Une ancienne page restée ouverte qui demanderait une génération incognito est refusée avec un message
    (« L'incognito n'existe plus : passez par l'espace privé »), au lieu d'être acceptée en génération normale. […]
    D'accord ? » → « oui ».
- **Écarté** : marque « à trier » dans le journal ; fichier témoin en clair pour une image privée ; « Supprimer » qui
  garde la ligne du journal ; neutralité réservée aux échecs privés ; Jeter envoyé dans l'espace affiché après un
  changement d'espace ; plusieurs bandeaux Annuler empilés ; demande incognito acceptée en génération normale.

## 2026-10-22 · Refonte « Chambre noire » : lumière inactinique, pixel, Labo et Tirages, pile à trier

- **Contexte** : après le renommage, le porteur demande : « Je veux modifier complètement les couleurs de l'app, l'UI,
  l'UX, l'icon etc... pour refléter ce changement de nom. De plus reprendre garder et reprendre dans l'app le coté
  pixel de l'icon de l'app. » Cadrage par grilling, quatre tours ; réponses recopiées telles quelles.
- **Décision** (porteur, 22/10/2026) :
  - « Périmètre de « UX » » (a identité seule, b mise en page, c tout, parcours compris) → « C » ;
  - « Direction artistique » → « A » : **lumière inactinique** (noir chaud, accent de lampe de labo, textes papier
    photo, matières mates au lieu du verre liquide, grain léger) ;
  - « Place du pixel dans l'app » → « B » : touches (logo, icônes de navigation, révélation, états vides) + nom et
    titres en police pixel, texte courant en police normale ;
  - « Motif de l'icône » (garder le paysage en carrés recoloré ?) → « oui garder mais tester B et C (plusieurs
    versions) » (B : nouveau motif pixel, lampe, cuve ou film ; C : paysage dans un cadre de tirage) ;
  - « Mode clair » (le supprimer ?) → « oui » ;
  - « Pages et navigation » (deux pages « Labo » et « Tirages » ?) → « B. Un swip de la génération l'ajoute au
    tirages (enregistrer), un swip vers la gauche la supprime, les générations se superposent comme une pile » ;
  - « Ce qui te gêne aujourd'hui » (réglages qui débordent, en-tête chargé, bouton Rafraîchir, états vides) → « oui
    pour les 4 » ;
  - « Vocabulaire de labo » → « B » : bouton « Révéler », pages « Labo » et « Tirages », le reste en mots clairs ;
  - « Thèmes incognito et espace privé » (incognito noir et blanc, privé en lumière inactinique verte) → « oui » ;
  - « Accent et couleurs d'état » → « a » : accent orange-ambre, halo rouge dans l'ambiance, rouge vif réservé aux
    erreurs, toujours avec une icône ;
  - « Coins et formes » → « a » : petits arrondis (4 à 6 px), boutons rectangulaires ;
  - « Typographie » (police pixel libre OFL servie par le serveur, texte courant en police du téléphone, chiffres
    techniques en chasse fixe) → « oui » ;
  - « Animation de la génération » → « a » : carrés au hasard avant le premier aperçu, puis aperçu en mosaïque qui
    s'affine étape après étape ;
  - « Où vit une image pas encore triée ? » → « a » : sur le disque dès la fin du calcul, marquée « à trier », sans
    limite de temps ;
  - « Que se passe-t-il quand on balaie une image vers la gauche ? » → « a » : bandeau « Image jetée · Annuler »
    quelques secondes, suppression sur le disque à la fin du délai seulement ; si l'app se ferme pendant le délai,
    l'image reste dans la pile ;
  - « Images déjà dans la galerie » (deviennent des tirages ?) → « oui » ;
  - « Vocabulaire » (Pile, Tirage, Garder, Jeter ; Variantes : « on garde celles qu'on veut ») → « ok » ;
  - « Ordre de la pile » (dernière terminée sur le dessus, génération en cours derrière ou sur le dessus si la pile
    est vide, « +N en attente », notification qui ouvre la pile) → « oui » ;
  - « Carte en cours ou en attente » (pas balayable, bouton « Annuler » confirmé) → « oui » ;
  - « Lots, variantes et campagnes » (une carte par image, « 2/4 », « Garder celle-ci » retiré) → « oui » ;
  - « Pile en incognito » → « on retire le mode incognito puisque le fait de balayer la génération à gauche est comme
    le mode incognito, la confidentialité se passe dans l'espace privé » ; écarts montrés (prompt écrit en clair dans
    le journal et le dossier de travail pendant le calcul, mesure de calibration gardée, suppression non physique),
    puis « Retrait de l'incognito » → « a » : retiré, Jeter efface l'image, sa vignette, ses images d'entrée, son
    dossier de travail et sa ligne de journal ;
  - « Pile de l'espace privé » (pile propre et étanche, Garder vers les tirages privés, Jeter supprime le fichier
    chiffré avec le même bandeau) → « oui » ;
  - « Autres actions sur une carte » (toucher = visionneuse, boutons ✕ et ✓ sous la pile) → « oui » ;
  - « Disposition du Labo » (pile au centre, champ replié en bas, déplié quand la pile est vide, réglages en grille
    qui ne déborde pas) → « oui » ;
  - « En-tête » (logo, nom en pixel, lampe d'état qui ouvre la feuille Moteur et « Ouvrir depuis le téléphone ») →
    « oui » ;
  - « Page Tirages » (mise à jour seule, sans Rafraîchir, cadenas au même endroit) → « oui mais mettre dle cadenas de
    l'espace privé autre part », puis « Où mettre le cadenas de l'espace privé ? » → « a » : dans la feuille de la
    lampe d'état ; dans l'espace, « Sortir » reste en haut à droite ;
  - « Vue large sur le Mac » (une colonne centrée, Tirages plus larges) → « oui » ;
  - « Validation par maquettes » → « non tu fais directement » ;
  - « Livraison » (`/to-spec`, `/to-tickets`, groupes : retrait de l'incognito, pile côté serveur, identité, Labo et
    pile, Tirages-en-tête-espace privé) → « ok » ;
  - résumé final, avec deux points : rendus des icônes B et C sur une planche avant intégration, police pixel choisie
    par Claude et signalée → « ok ».
- **Écarté** : maquettes de l'interface avant le code ; corbeille « Rebuts » ; image non triée gardée en mémoire
  seulement ; garder la page « En cours » ; police pixel partout ; garder l'incognito en option.
- **Conséquences** : remplace « Une seule page Créer, une page En cours pour la file et les résultats » (19/10/2026)
  pour les pages, l'emplacement du cadenas de « Espaces public et privé étanches » (15/10/2026), et toutes les
  décisions sur l'incognito (dont « « Éditer » et « Dessiner » sur une image incognito allument aussi l'incognito »,
  21/10/2026), qui seront marquées « remplacées » par la spec. Tant que le retrait n'est pas livré, l'incognito reste
  dans le code et le glossaire.

## 2026-10-22 · Renommage en « Chambre noire »

- **Contexte** : « Qwen-Image 2.1 local » décrit le modèle, pas ce que l'app promet (génération d'images privée, sur
  la machine). « Darkroom AI », retenu d'abord, est abandonné : « il y en a trop qui existent déjà avec ce nom ».
- **Décision** (porteur, 22/10/2026, proposition validée par « Ok ») :
  - nom : « On va partir sur Chambre noir » ; orthographe « Chambre noire », n minuscule (usage français) ;
  - « Jusqu'où va le renommage ? » → « Tout, dépôt compris » ;
  - « Garde-t-on une mention du modèle sous le nom ? » → « « Darkroom AI » seul », repris pour « Chambre noire » ;
  - « Comment garder les stats du projet sous le nouveau nom ? » → « Dossier inchangé + nom d'affichage dans
    stats-board (Recommandé) » ;
  - « […] je crée le ticket Asana […] et je note la décision dans DECISIONS.md. D'accord ? » → « Oui, ticket +
    décision (Recommandé) ».
- **Conséquences** : le dossier local reste `qwen-image-local` (clé des discussions Claude et des stats) ; les chaînes
  « qwen-image-local » du chiffrement de l'espace privé et du code d'accès ne changent jamais (les changer rendrait
  les images privées illisibles et le code refusé) ; le dépôt GitHub devient `matwi5/chambre-noire` ; le service
  macOS devient `com.matwi5.chambre-noire`, et `make_service.py` retire l'ancien ; le raccourci devient
  `Chambre noire.command` (`.lnk` sous Windows), et `make_shortcut.py` retire l'ancien.

## 2026-10-22 · Rétro du parcours des pages : hook avant commit, notes reliées, pistes hors du dépôt

- **Contexte** : la rétro du parcours (discussion principale et quatre sessions de groupe) relève 18 pistes ; les
  plus coûteuses sont le contrôle des lignes de plus de 120 caractères, découvert seulement au bout d'un contrôle
  complet, et les notes non suivies par git, recopiées à la main entre le dossier principal et les worktrees.
- **Décision** (porteur, 22/10/2026 : « oui » aux quatre questions) : les pistes qui touchent `mathis-plugins` sont
  rendues en liste pour l'agent des plugins, pas appliquées ici ; un hook git versionné (`.githooks/pre-commit`,
  activé par `tests/check.py --link-venv`) refuse un commit qui ajoute une ligne trop longue ; les notes non suivies
  (`CLAUDE.md`, `ETAT_DU_PROJET.md`, `travail/`, `docs/specs/`, `docs/agents/` sauf la carte du code) ne sont plus
  copiées dans les worktrees mais reliées au dossier principal ; la session des pistes écrit directement
  `docs/agents/session-deleguee.md`, et propose le texte des pièges de `CLAUDE.md`, validé par le porteur avant
  d'être écrit.

## 2026-10-21 · « Éditer » et « Dessiner » sur une image incognito allument aussi l'incognito

_Remplacée le 22/10/2026 par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo et Tirages, pile à trier »
(incognito retiré)._

- **Contexte** : la passe « bogues » du ticket incognito du groupe D trouve un comportement antérieur au parcours :
  « Éditer » ou « Dessiner » sur une image incognito, interrupteur éteint, met l'image dans la saisie publique ; un
  « Générer » ensuite part en normal et le serveur copie l'image incognito dans `outputs/.inputs/` (image d'entrée de
  la nouvelle image, visible dans la galerie).
- **Décision** (porteur, 21/10/2026 : « oui et oui ») : « Éditer » et « Dessiner » sur une image incognito allument
  l'interrupteur incognito, comme « Reprendre » (ticket du groupe D). Le texte repris d'une image incognito n'est pas
  écrit comme brouillon tant que l'interrupteur reste allumé ; l'éteindre est un geste explicite du porteur, après
  lequel la frappe suivante l'écrit (formulation du README gardée).

## 2026-10-21 · Une image incognito reste incognito quand on la reprend ou la relance

_Remplacée le 22/10/2026 par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo et Tirages, pile à trier »
(incognito retiré)._

- **Contexte** : à la fin du groupe D, « Relancer » suivait l'interrupteur incognito du moment (choix de la
  rédaction de la spécification, pas du porteur) : relancer une image incognito interrupteur éteint enregistrait la
  nouvelle image sur le disque ; reprendre une image incognito mettait son texte dans la saisie publique, écrit comme
  brouillon à la première frappe.
- **Décision** (porteur, 21/10/2026 : « a, oui pour le ticket et oui pour les pièges ») : une image incognito reste
  incognito : « Relancer » la relance toujours en incognito ; « Reprendre » allume l'interrupteur incognito, de façon
  visible, donc son texte n'est jamais écrit comme brouillon. Les autres images suivent l'interrupteur comme
  « Générer ». Ticket du groupe D ; pièges de `CLAUDE.md` complétés (« Reprendre » et « Relancer », demande gardée en
  mémoire, estimation de « Relancer », image du dessin).
- **Écarté** : garder « Relancer » sur l'interrupteur du moment et seulement marquer le texte repris pour qu'il ne
  soit jamais écrit comme brouillon.

## 2026-10-21 · Suites du groupe C : adresse d'image échappée, image du dessin par `showImage`

- **Contexte** : la revue de sécurité du groupe C (page Créer) relève deux faiblesses non exploitables : l'adresse
  `data:` d'une image d'entrée insérée sans `esc()` dans la page, et l'image du dessin (`#paintImg`) affichée sans
  passer par `showImage`, qui peut laisser voir un instant l'image de l'espace quitté.
- **Décision** (porteur, 21/10/2026 : « oui et oui ») : l'adresse est échappée tout de suite ; l'image du dessin
  passe par `showImage` et rejoint les images que `tests/check.py` surveille, dans un ticket du groupe D. Pièges
  « Incognito et espace privé » (brouillon unique) et « Saisie par espace » de `CLAUDE.md` mis à jour.

## 2026-10-20 · Suites du groupe B : lot en tête, « Rien en cours », terminées incognito

_Révisée le 22/10/2026 (terminées incognito hors du plafond) par « Refonte « Chambre noire » : lumière inactinique,
pixel, Labo et Tirages, pile à trier » (incognito retiré)._

- **Contexte** : la session du groupe B (page En cours) remonte trois écarts entre la lettre des textes et ce qu'elle a
  fait.
- **Décision** (porteur, 20/10/2026 : « oui pour les points 1 à 4 ») : « Passer en tête » d'un lot n'est offert que si
  rien du lot ne tourne (spécification, section 8 ; la ligne de la décision du 19/10 est précisée) ; « Rien en cours »
  ne s'affiche que si rien ne tourne, rien n'attend et aucune terminée n'est là ; les images incognito ne comptent pas
  dans le plafond de 12 terminées et ne sortent jamais d'elles-mêmes (la liste peut dépasser 12 en incognito, dans la
  seule mémoire de la page). Piège « Verrous » de `CLAUDE.md` complété (`start_job`, `cancel_job` sous `S.turn`).
- **Écarté** : oublier d'elle-même la plus ancienne image incognito au-delà de 12 (avec un message).

## 2026-10-20 · Suites du groupe A : marqueur de campagne caché des lignes incognito, annulation au démarrage

_Révisée le 22/10/2026 (ligne incognito de la file) par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo
et Tirages, pile à trier » (incognito retiré)._

- **Contexte** : la revue de sécurité du groupe A (file réordonnable, variantes en édition) relève que le marqueur de
  campagne, posé aussi sur la ligne d'un lot incognito comme le demandait la spécification, dit aux autres appareils
  qu'il s'agit d'une campagne ; la session du groupe retrouve aussi une piste ouverte le 14/10/2026 : une annulation
  posée au démarrage d'une génération est écrasée et la génération va au bout.
- **Décision** (porteur, 20/10/2026 : « oui poue les points 1 à 4, mets dans le groupe B ») : la ligne de la file
  d'une génération incognito ne porte pas le marqueur de campagne (elle ne montre que son genre, comme avant) ; sa
  page le lit dans sa propre réponse de `/api/generate` (ticket « Présenter la file en cartes »). L'annulation écrasée
  devient un ticket du groupe B. Pièges de `CLAUDE.md` complétés (`S.turn`, étiquette `tag` qui n'ouvre aucune route).

## 2026-10-19 · Une seule page Créer, une page En cours pour la file et les résultats

_Révisée le 22/10/2026 (parties sur l'incognito : file, terminées, étiquette `tag`) par « Refonte « Chambre noire » :
lumière inactinique, pixel, Labo et Tirages, pile à trier » (incognito retiré)._

- **Contexte** : trois onglets (Créer, Éditer, Dessiner) font la même chose à une image d'entrée près ; l'image en
  cours et le résultat s'affichent sous le compositeur ; la file d'attente, dans une feuille ouverte par la pastille du
  haut, répète chaque image d'un lot sur sa propre ligne, donne des durées cumulées sans heure et une rangée de cercles
  « #1 #2… » sans contenu. Demandes du porteur : « Je veux regrouper les pages créer, editer et dessiner en un »,
  « Améliore la file d'attente sur la page En cours car avant c'était pas terrible », et « garder les promptes
  sauvegardé dans les gategorie editer, créer, dessiner... C'est utile ».
- **Décision** (porteur, 19/10/2026, toutes les recommandations du cadrage acceptées) : trois onglets, dans l'ordre
  « En cours », « Créer », « Galerie » ; l'application s'ouvre sur Créer.
  - **Créer** : un seul champ de texte (exemple selon la saisie) et un seul brouillon par espace (celui de Créer, à
    défaut le premier non vide d'Éditer puis de Dessiner). Sans image d'entrée, génération à partir du texte ; avec
    1 à 10, édition ; images ajoutées par le choix, le glisser-déposer ou le collage. Bouton « Dessiner » sur une seule
    image (sans image : choix d'une image ; à plusieurs : grisé et expliqué), masque et annotation inchangés.
    Campagne proposée dès 2 images, dessin éteint. Variantes avec ou sans image d'entrée, dessin compris, jamais en
    campagne (le serveur lève la restriction au mode t2i). Aucune image de résultat sur la page : « Générer » mène à
    En cours ; la saisie se vide comme avant.
  - **En cours** : la génération en cours en grand, une seule fois (aperçus, progression, annuler) ; la file en cartes,
    une par demande (un lot ou une campagne sur une carte, une case par image, annulation de la carte ou d'une image
    dépliée), « prête vers HH h MM » et l'heure de fin de la file, vignette (image d'entrée, cadre aux proportions
    demandées, icône incognito), ligne des réglages, seul « autre appareil » signalé ; « Passer en tête » (génération
    ou lot), offert à qui peut l'annuler, sur une carte dont rien ne tourne. Puis les terminées de la page (au plus
    12, lots en grille, « × » et « Tout retirer », échecs avec leur message et « Relancer », vidées au rechargement).
    Message « Image prête » ou « Lot prêt » quand on est ailleurs dans l'application.
  - **Navigation** : pastille sur l'onglet En cours (nombre en cours et en attente, anneau de progression) ; la
    pastille du haut mène à En cours quand une génération tourne, sinon au panneau Moteur ; la feuille « File
    d'attente » et la rangée « #1 #2… » disparaissent.
  - **Gestes** : « Éditer » ajoute l'image à la saisie ; « Dessiner » remplace les images de la saisie par la sienne,
    après confirmation s'il y en avait ; « Reprendre » (désormais texte, images d'entrée et dessin, sans le tracé, qui
    n'est pas gardé) remplace la saisie, après confirmation si elle n'est pas vide ; « Relancer » refait la même
    demande avec une nouvelle graine.
  - **Incognito dans les terminées** (porteur, 19/10/2026, réponse « oui » à la proposition) : une image incognito
    reste dans les terminées de la page jusqu'à son « × », « Tout retirer », « Supprimer » ou la fermeture de la
    page ; remplace la garde « jusqu'à ce qu'elle ait été vue puis quittée » de la modification du 14/10/2026 (elle
    l'aurait fait disparaître dès qu'on quitte En cours). Rien d'autre de l'incognito ne change.
  - **Prompts** : catégories « Créer », « Éditer », « Dessiner » gardées ; la feuille s'ouvre filtrée sur celle de la
    saisie (sans image, avec images, dessin actif), « Tous » à un geste ; un nouveau prompt prend la catégorie de la
    saisie ; choisir un prompt d'une autre catégorie ne remplit que le texte.
- **Écarté** : dessiner sur une image parmi plusieurs, les autres servant de références (jamais essayé avec le
  moteur) ; réordonner la file par glisser (« Passer en tête » couvre le cas utile, un essai rapide bloqué derrière
  une campagne) ; garder la saisie après « Générer » ; garder les terminées après un rechargement (la Galerie les a).
- **Conséquences** : la file du serveur (`queue.Queue`) devient réordonnable. Une génération publique peut passer
  devant une génération privée cachée : seule la durée d'attente de cette dernière change. La saisie n'est plus
  propre à chaque onglet mais à chaque espace : remplace, dans « Espaces public et privé étanches » (15/10/2026), la
  saisie « onglet par onglet » ; l'étanchéité, l'incognito (sauf sa garde dans les terminées) et le calcul d'une
  seule génération à la fois ne changent pas. Le serveur gagne aussi un marqueur de campagne dans les lots et une
  étiquette pour les entrées incognito de la file (spécification `docs/specs/2026-10-19_page-creer-en-cours.md`).

## 2026-10-16 · Modèle officiel par défaut, variante communautaire en option

- **Contexte** : le dépôt est public. Depuis le renommage du dépôt Hugging Face d'abenzerps (12/10/2026), `setup.py`
  installait par défaut la variante communautaire affinée de sa branche principale, et le README la présentait comme
  le modèle du projet. Les quantifications GGUF des poids officiels de Qwen/Qwen-Image-2.1 sont restées sur la branche
  `base` de ce même dépôt : c'est le fichier Q4_K_M (même taille, même empreinte) qu'installait le premier commit.
- **Décision** (porteur, 16/10/2026) : `q4` et `q8` installent les fichiers de la branche `base` (commit `4db8efd`),
  la variante communautaire devient les versions `uc-q4` et `uc-q8`, installées seulement par `setup.py --uc`. Le
  choix propre à une machine passe par `tools/config.local.json`, non suivi, lu par-dessus `tools/config.json`, qui
  ne garde plus de préférence personnelle.
- **Alternatives écartées** : le dépôt `Qwen/Qwen-Image-2.1` lui-même (poids bf16 en deux fichiers, 14,2 Go ; une
  quantification devrait se faire sur la machine par `sd-cli -M convert`, jamais essayée) ; les GGUF de
  `leejet/Qwen-Image-2.1-GGUF` (cités par la documentation de stable-diffusion.cpp, mais jamais exécutés dans ce
  projet) ; retirer la variante communautaire du code.
- **Conséquences** : mêmes quantifications et mêmes tailles qu'avant, donc mêmes durées (estimations et mesures du
  README inchangées). Une machine qui gardait la variante la choisit par `"model": "uc-q8"` (ou `uc-q4`) dans
  `tools/config.local.json` ; ses mesures de calibration, rangées sous `q8`, sont à déplacer sous `uc-q8` dans son
  `tools/calibration.json`, sinon `q8` part de mesures faites avec l'autre fichier. Les notes de travail (`CLAUDE.md`,
  `ETAT_DU_PROJET.md`, `travail/`, `docs/specs/`, `docs/agents/` sauf la carte du code) sortent du suivi git : un
  worktree neuf ne les contient plus.
## 2026-10-16 · Une image reste dans son espace : « Rendre privée » retiré

- **Contexte** : en essayant la livraison sur le téléphone, le porteur demande d'abord un « Rendre publique » en
  face de « Rendre privée », puis se ravise.
- **Décision** (porteur, 16/10/2026) : une image publique ne devient pas privée, ni l'inverse. Le bouton « Rendre
  privée », sa feuille et la route `/api/private/adopt` sont retirés (avec `adopt_output` et la réécriture du
  journal, `drop_from_journal`). Remplace « Rendre privée » dans « Espace privé discret » (14/10/2026) et dans
  « Espace privé durci après la revue de sécurité » (15/10/2026).

## 2026-10-16 · Images affichées sans l'image d'avant, page vide de tout privé après la sortie

- **Contexte** : sur le téléphone, une image d'entrée vue dans l'espace privé réapparaissait un instant dans l'espace
  public, la galerie privée aussi en revenant à la Galerie : une `<img>` qui reçoit une autre adresse garde l'image
  d'avant à l'écran jusqu'au chargement de la nouvelle, et la page gardait des images, textes et liens privés cachés.
- **Décision** (correction demandée par le porteur, approche choisie sans lui) : toute image affichée passe par
  `showImage` (vidée, puis remplie une fois l'image décodée à part ; `check.py` refuse l'affectation à la main) ; les
  dernières images décodées sont gardées **en mémoire de la page** (`ready`), pas en cache HTTP du navigateur, qui
  garderait sur le téléphone une copie des images vues (celles de l'espace privé comprises, après sa fermeture) ; les
  réponses restent en `no-store`. En attendant l'image, sa miniature prend déjà sa taille à l'écran (`fitThumb`, en
  unités de la scène : la taille suit le panneau et la rotation). À la
  sortie de l'espace privé, la page retire toute image, tout lien et toute ligne de journal privés, et les vues
  fermées se vident ; `tests/ui/etancheite.test.mjs` fouille la page entière après un parcours privé.
- **Version servie** : `/api/status` donne le commit du dossier servi et l'empreinte du code que le serveur charge au
  lancement (`launch.py`, `estimate.py`) ; le panneau Moteur dit « à relancer » seulement quand celle-ci a changé.

## 2026-10-15 · Espaces public et privé étanches

_Révisée le 22/10/2026 (« Génération incognito » dans la file) par « Refonte « Chambre noire » : lumière inactinique,
pixel, Labo et Tirages, pile à trier » (incognito retiré)._

- **Contexte** : en essayant l'espace privé sur le téléphone, le porteur voit passer d'un espace à l'autre ce qui
  devrait rester d'un seul côté : un prompt enregistré dans l'espace privé apparaît dans l'espace public (la spec du
  14/10/2026 laissait les prompts enregistrés hors de l'espace privé), la file d'attente montre à chaque espace les
  générations de l'autre (une génération privée y passe pour « Génération incognito », même pour la page qui l'a
  lancée après un rechargement), la progression d'une génération privée reste à l'écran après la sortie, et le texte
  et les images saisis sont communs aux deux espaces.
- **Décision** (porteur, 15/10/2026) : l'espace public et l'espace privé sont deux espaces étanches. Chacun a sa
  galerie, sa file d'attente, ses générations en cours, sa saisie (texte et images, onglet par onglet) et ses prompts
  enregistrés ; seuls les prompts types, les Réglages et l'autorisation des notifications sont communs.
  - **File** : chaque espace ne voit que ses générations (ni ligne, ni aperçu, ni vignette de l'autre ; « +N en
    attente » ne compte que l'espace courant). Une génération qui attend derrière une génération cachée de l'autre
    espace affiche « en attente » et une durée estimée qui compte ce travail, sans son rang. Les générations
    incognito, lancées depuis l'espace public, y restent visibles des autres appareils comme « Génération incognito ».
  - **Sortie et retour** : à la sortie (« Sortir » ou fermeture après 15 minutes), une génération privée quitte
    l'écran tout de suite et continue ; tout appareil déverrouillé la retrouve, même après un rechargement, avec son
    prompt et sa progression, et peut l'annuler.
  - **Prompts enregistrés privés** : chiffrés comme les images privées, visibles seulement dans l'espace privé,
    rechiffrés au changement de code, supprimés avec l'espace ; l'espace privé ne montre pas les prompts enregistrés
    publics. Les prompts enregistrés depuis l'espace privé avant ce changement restent en clair dans la liste
    publique : le porteur les supprime à la main.
  - **Saisie** : la saisie privée n'est jamais écrite dans le navigateur ; « Sortir » l'efface, la fermeture après
    15 minutes la garde en mémoire de la page jusqu'au retour. Les onglets marqués disparaissent.
  - **Cadenas** : aussi visible que le bouton Rafraîchir de l'en-tête de la galerie (même taille d'icône, même
    couleur, pleine opacité), au même endroit.
- **Écarté** : montrer les générations de l'autre espace sous un libellé neutre (le porteur ne veut rien voir de
  l'autre espace) ; cacher aussi le travail de l'autre espace dans la durée estimée (estimation fausse, sans rien
  cacher de plus : une attente sans ligne devant se remarque de toute façon) ; montrer les prompts enregistrés publics
  dans l'espace privé.
- **Conséquences** : la file d'attente et les prompts enregistrés dépendent désormais de l'espace de l'appareil qui
  les lit. Quelqu'un d'attentif devine, à une attente sans ligne devant, qu'une génération de l'autre espace tourne,
  comme il le devine déjà pour l'incognito des autres appareils. Remplace, dans « Espace privé discret », le cadenas
  « petit et discret » et l'héritage des onglets marqués, et, dans « Espace privé durci après la revue de sécurité »,
  les onglets marqués gardés à la fermeture de l'espace.
- **Mise en œuvre** (groupe B, sans le porteur) : pour le serveur, un appareil est « dans l'espace privé » s'il a une
  session **et** que sa requête est sûre (`_secure`, comme les routes privées) : le cookie de session n'a pas le
  drapeau `Secure` et pourrait suivre une adresse `http://` du même nom, qui recevrait sinon les prompts privés de la
  file en clair.

## 2026-10-15 · Espace privé durci après la revue de sécurité

_Révisée le 22/10/2026 (notification incognito) par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo et
Tirages, pile à trier » (incognito retiré)._

- **Contexte** : la revue de sécurité du groupe D a relevé ce qui trahit ou expose l'espace privé hors du chiffrement
  du disque : le texte des notifications, le contenu laissé à l'écran après la sortie, la suppression sans code depuis
  n'importe quel appareil, le code et les images en clair sur le Wi-Fi, et un changement de code qui laissait la même
  clé privée dans les anciennes copies de `space.json`.
- **Décision** (porteur, 14/10/2026 ; mise en œuvre, groupe E) :
  - **Notification neutre** : une génération ou un lot privé notifie exactement comme une génération normale
    (« Image prête », « N images prêtes », mêmes champs) ; l'incognito garde son mot.
  - **« Sortir » vide l'écran** : en plus des images privées (zone de résultat, grille, visionneuse), le texte et les
    images des onglets marqués sont effacés, et une génération privée en cours ne garde à l'écran que sa progression
    (ni aperçu, ni prompt, ni image d'entrée dans la file). Fermeture seule de l'espace (15 minutes sans requête
    privée) : les images privées quittent l'écran comme avant, mais les onglets marqués gardent leur contenu et leur
    marque (« Héritage » de l'entrée « Espace privé discret », inchangé dans ce cas), pour ne pas effacer un texte en
    cours de saisie ; choix du groupe E, la décision du porteur nommant « Sortir ».
  - **Supprimer sans le code, sur le Mac seulement** : `/api/private/reset` exige une requête du Mac lui-même (au sens
    du contrôle d'accès : adresse source et nom d'hôte locaux, non relayée par Tailscale) ; ailleurs 403, et la feuille
    de l'interface dit d'ouvrir l'application sur le Mac (`local` dans `/api/status`).
  - **En HTTPS ou sur le Mac seulement** : toutes les routes de l'espace privé sauf `lock` (création, déverrouillage,
    changement de code, « Rendre privée » (retiré le 16/10/2026), galerie et lectures déchiffrées, suppression d'une
    image), la génération privée et l'aperçu d'une génération privée (`/api/job/<id>/preview`, en clair) exigent une
    requête « sûre » (`_secure`) : adresse source 127.0.0.1 ou ::1 **et** nom d'hôte local ou nom HTTPS de « tailscale
    serve » (`S.https_hosts`, le relais arrivant de 127.0.0.1). Ailleurs 403 avec un message qui dit de passer par
    l'adresse HTTPS ; `secure` dans `/api/status` permet à l'interface de le dire avant toute saisie.
  - **Changer le code change les clés** : une nouvelle paire X25519 est tirée, chaque fichier de chaque image est
    déchiffré avec l'ancienne clé et rescellé avec la nouvelle (même identifiant d'image, mêmes rôles, même format),
    toutes les sessions sont fermées. Ordre d'écriture sûr : tout s'écrit d'abord à part dans `private/.rekey/`
    (fichier `public` avec la nouvelle clé publique, `items/<id>/<rôle>` rechiffrés, `space.json` scellé par le nouveau
    code), chaque fichier et dossier mis sur le disque (`fsync` pour chaque copie, puis un seul `F_FULLFSYNC` sur
    macOS, qui vide tout le cache du disque, avec le nouveau `space.json` et le dossier `private/`) pour qu'une coupure
    de courant ne bascule pas sur des copies vides ; **la bascule** est le remplacement atomique de
    `private/space.json` par le nouveau ; ensuite chaque image
    rechiffrée remplace l'ancienne (ancienne supprimée, puis nouvelle renommée à sa place) et `.rekey/` est supprimé.
    `finish_rekey`, appelé au démarrage et sous le verrou en tête de toute ouverture ou écriture de l'espace, répare
    une interruption : si `space.json` porte la clé de `.rekey/public`, la bascule a eu lieu et le rangement se
    termine ; sinon `.rekey/` est jeté et l'ancien espace est intact. À tout instant, exactement un des deux codes ouvre
    toutes les images. Un fichier déjà illisible avec l'ancienne clé est recopié tel quel. Les écritures d'images
    (`store_private`) et les suppressions passent sous le même verrou que le changement ; une génération privée lancée
    avant le changement est rangée avec la nouvelle clé (`S.rekeyed`, en mémoire : les générations ne survivent pas à
    un redémarrage).
- **Écarté** : « Image privée prête » (le service de notification et l'écran verrouillé du téléphone apprennent qu'un
  espace privé existe) ; suppression depuis un autre appareil avec le code (non demandée : avec le code, on entre et
  on supprime les images) ; juger le HTTPS sur les en-têtes `X-Forwarded-*` ou `Tailscale-User-Login` (un appareil du
  Wi-Fi peut les envoyer en `http://`) ; admettre l'adresse Tailscale directe en `http://` (chiffrée par WireGuard,
  mais la décision du porteur nomme le HTTPS et le Mac seulement) ; rechiffrer seulement la clé privée avec le nouveau
  code (choix du groupe D : une copie de l'ancien `space.json` s'ouvre encore avec l'ancien code et lit toutes les
  images) ; refuser le changement de code pendant une génération privée (inutile avec `S.rekeyed`) ; échanger le
  dossier `items/` entier (une image rangée entre une panne et la réparation aurait été déplacée avec l'ancien dossier).
- **Conséquences** : rien, dans une notification, ne distingue une image privée d'une image normale. Quelqu'un qui
  connaît le code d'accès du téléphone ne peut plus effacer l'espace privé à distance ; le porteur qui a oublié son
  code doit passer par le Mac. Le téléphone n'ouvre l'espace privé que par l'adresse HTTPS de Tailscale (« tailscale
  serve » actif) ; le Mac ouvert par son propre nom Wi-Fi (`http://<nom>.local:7860`) n'est pas « sûr » non plus : il
  passe par `127.0.0.1` ou `localhost`. Changer le code dure le temps de rechiffrer toutes les images (pendant ce
  temps, entrer dans l'espace et ranger une image attendent) ; une copie de `space.json` d'avant le changement ne lit
  plus les images d'après, mais une sauvegarde complète de `private/` d'avant le changement reste lisible avec l'ancien
  code, par nature.

## 2026-10-14 · Espace privé discret : on y entre, on en sort

_Révisée le 15/10/2026 (cadenas discret, héritage des onglets marqués) par « Espaces public et privé étanches »._

_Révisée le 22/10/2026 (bouton Incognito masqué dans l'espace) par « Refonte « Chambre noire » : lumière inactinique,
pixel, Labo et Tirages, pile à trier » (incognito retiré)._

- **Contexte** : la spécification prévoyait un bouton « Privé » à côté de « Générer » et un mode Privé à allumer.
  En voyant l'interface, le porteur ne veut rien qui signale l'espace privé à l'arrivée sur l'application.
- **Décision** (porteur, 14/10/2026) : l'entrée est un petit cadenas discret dans l'en-tête de la galerie (création ou
  code). Déverrouiller fait **entrer dans l'espace privé** : toute l'application prend un thème propre (nuit sarcelle,
  comme le graphite de l'incognito), le bouton Incognito disparaît, toute génération part en privé, la galerie montre
  les images privées. Une seule sortie, un cadenas « Sortir » en haut à droite, qui verrouille. « Rendre privée », dans
  la visionneuse normale, demande le code sans faire entrer dans l'espace privé (retiré le 16/10/2026). Fermer
  l'application n'annule pas les générations privées.
- **Écarté** : bouton « Privé » à côté de « Générer » (visible à l'arrivée) ; geste caché (appui long sur le logo) ;
  mode Privé dans la feuille Réglages ; galerie normale visible depuis l'espace privé.
- **Conséquences** : il n'y a plus de « mode Privé » distinct de l'état déverrouillé ; une génération privée est
  simplement une génération lancée depuis l'intérieur de l'espace. Héritage (récit 61) : un onglet dont le contenu a
  été saisi dans l'espace reste marqué après la sortie, non pas « jusqu'à la génération suivante » (toute génération
  faite dans l'espace est privée de toute façon) mais jusqu'à ce qu'il soit vidé hors de l'espace (groupe D, sans le
  porteur) ; hors de l'espace, Générer y demande le code et relance une fois entré. Les tickets Asana du groupe D décrivent encore le
  bouton « Privé » (à mettre à jour par le porteur).

## 2026-10-14 · Espace privé : format des clés, des fichiers et sessions

- **Contexte** : mise en œuvre de la décision « Espace privé chiffré à clé publique » (ci-dessous). Le format des clés
  est coûteux à changer une fois un espace créé : il est fixé ici.
- **Décision** (groupe D, choix techniques dans le cadre fixé par le porteur) :
  - `private/space.json` : `{"v": 1, "public": <clé publique X25519, 32 octets, base64>, "kdf": {"alg": "scrypt",
    "n", "r", "p", "salt": <16 octets, base64>}, "key": <base64 de nonce (12 octets) + AES-256-GCM(clé privée X25519
    brute, 32 octets)>}` ; clé AES = scrypt(code privé en UTF-8 tel que saisi, sel, n, r, p, 32 octets) ; données
    associées `qwen-image-local private key v1`. Paramètres à la création : n = 2¹⁸, r = 8, p = 1 (256 Mio et ≈ 0,3 s
    par essai sur le Mac) ; ils sont lus dans le fichier, donc modifiables pour un espace futur sans casser l'ancien.
    ~~Changer le code rechiffre la même clé privée avec un sel neuf : les images ne bougent pas.~~ Remplacé le
    15/10/2026 : changer le code tire une nouvelle paire et rechiffre les images (« Espace privé durci après la revue
    de sécurité »).
  - Images : `private/items/<id>/`, `<id>` = 128 bits tirés au hasard (32 caractères hexadécimaux), sans date ni
    mode. Un fichier par rôle, chacun chiffré à part : `meta` (JSON : mode, prompt, dimensions, étapes, graine, durée,
    modèle, lot, heure, noms des images d'entrée), `image` (PNG), `thumb` (JPEG de 320 px, fabriqué en mémoire),
    `input_<k>` (k-ième image d'entrée, nom dans `meta`). Format d'un fichier : `QPV1` (4 octets) + clé publique
    X25519 éphémère (32) + nonce (12) + AES-256-GCM(contenu) ; clé = HKDF-SHA256(accord X25519 éphémère × clé
    publique de l'espace, sel = clé éphémère + clé publique, info `qwen-image-local private file v1`, 32 octets) ;
    données associées = les 48 premiers octets + `<id>/<rôle>`, pour qu'un fichier ne passe pas pour un autre. Le
    serveur range une image avec la seule clé publique, notée au lancement de la génération (si l'espace a été
    supprimé ou recréé entre-temps, l'image est abandonnée). L'image est écrite dans `private/items/.<id>/` puis le
    dossier est renommé : la galerie privée ne voit jamais une image à moitié rangée.
  - Prompts enregistrés privés (ajouté le 15/10/2026, spécification « Espaces public et privé étanches ») : un seul
    fichier `private/prompts`, même format qu'un fichier d'image (`QPV1`, clé éphémère, nonce, AES-256-GCM), données
    associées = les 48 premiers octets + `prompts` (aucun nom d'image ne peut le valoir) ; contenu : JSON en UTF-8,
    la liste des prompts privés, même format qu'un prompt public (`id`, `title`, `text`, `usage`, `used`). Absent tant
    qu'aucun prompt privé n'existe. Écrit sous `PRIVATE_LOCK` après `finish_rekey()`, scellé avec la clé publique de
    `space.json`, dans `private/prompts.tmp` mis sur le disque puis remplacé d'un coup, droits 600 ; lu et modifié
    avec la clé privée d'une session (refusé si elle n'est plus celle de l'espace). Le changement de code le
    rechiffre dans `private/.rekey/prompts` avant la bascule, puis `finish_rekey()` le met à la place de l'ancien ; un
    fichier déjà illisible est recopié tel quel.
  - Droits (ajouté le 15/10/2026) : tout fichier écrit dans `private/` (images, prompts, `space.json`, copies de
    `.rekey/`, fichiers temporaires) est créé en 600 et tout dossier en 700 (`open_private`, `private_dir`), contrôlé
    par le banc à la fin des tests de l'espace privé ; les fichiers d'un espace créé avant gardent leurs droits
    jusqu'au prochain changement de code.
  - Sessions : une par appareil, en mémoire du serveur (`S.private_sessions`), jeton aléatoire de 256 bits dans le
    cookie `qwen_private` (HttpOnly, `SameSite=Strict`, sans `Max-Age`) ; fermée après 15 min sans requête privée
    (`/api/status` et le suivi des générations ne la prolongent pas), par `/api/private/lock`, et par
    `/api/private/reset` pour toutes. Les dérivations du code passent une à une (verrou) : un essai à la fois, et
    jamais plusieurs fois 256 Mio en mémoire.
- **Écarté** : `hashlib.scrypt` (plafond mémoire à régler à la main) ; PBKDF2 (moins coûteux à attaquer sur GPU) ;
  garder la clé privée déchiffrée sur le disque ou dans le cookie ; `SameSite=Lax` (le cookie n'a pas à suivre une
  ouverture de page venue d'un autre site : l'interface ne lit l'espace privé que par des `fetch` de même origine).
- **Conséquences** : redémarrer le serveur ferme toutes les sessions. Verrouillage à la fermeture de la page par un
  envoi `keepalive` dans `pagehide`, comme l'oubli des générations incognito ; l'expiration après 15 minutes reste le
  filet si cet envoi se perd.

## 2026-10-14 · Espace privé chiffré à clé publique

- **Contexte** : le porteur veut une galerie séparée, accessible seulement par un code, dont les images ne se lisent
  pas sur l'ordinateur sans passer par l'application. La menace visée : quelqu'un qui ouvre les dossiers du Mac, une
  sauvegarde Time Machine, ou une personne qui connaît le code d'accès du téléphone mais pas le code privé.
- **Décision** (porteur) : tout ce qui se rattache à une image privée (image, images d'entrée, miniature, prompt,
  réglages) est chiffré sur le disque, sans aucune trace en clair ailleurs (journal, calibration, `logs/`), comme en
  incognito. Le chiffrement est à clé publique : la clé publique de l'espace est en clair, la clé privée est chiffrée
  par une clé tirée du code privé (dérivation volontairement lente). Le serveur peut donc chiffrer une image en fin de
  génération sans connaître le code, même si l'espace a été verrouillé entre-temps ; seule la lecture demande le code.
  Code privé de 8 caractères au moins, distinct du code d'accès, demandé même sur le Mac ; déverrouillage propre à
  chaque appareil. Bibliothèque `cryptography`, déjà installée avec `pywebpush`.
- **Écarté** : chiffrement symétrique par le code seul (le serveur devrait garder la clé pendant toute la génération,
  ou l'image finirait en clair si l'espace est verrouillé avant la fin) ; disque en mémoire vive pour le passage en
  clair (propre à macOS, déjà écarté pour l'incognito) ; code court à chiffres (cassé hors ligne en quelques jours sur
  une copie du disque).
- **Conséquences** : sd-cli ne travaille que sur des fichiers en clair, donc les entrées et l'image passent brièvement
  en clair dans `jobs/`, exclu de Time Machine. Code oublié : les images privées sont perdues ; « Supprimer l'espace
  privé » permet de repartir de zéro. Le format des fichiers chiffrés est coûteux à changer une fois des images
  stockées.

## 2026-10-14 · Pas de génération simultanée : une file d'attente

- **Contexte** : le porteur veut lancer plusieurs générations en même temps (lots de variantes, campagnes), en
  parallèle si cela ne fait pas perdre de temps.
- **Décision** (porteur) : les générations restent calculées l'une après l'autre ; « Générer » reste actif pendant une
  génération et les demandes suivantes vont dans une file d'attente visible. Un lot lance sd-cli une fois par image,
  y compris pour les variantes.
- **Raison** : d'après les mesures de calibration du Mac (M6, 32 Go), une image 1024 px en 40 étapes passe ≈ 95 % de
  son temps dans les étapes sur le GPU (≈ 17 s par étape), contre ≈ 30 s pour l'encodage et le décodage. Deux sd-cli
  simultanés se partageraient le même GPU déjà saturé (aucun gain de débit, déduit et non mesuré) et doubleraient la
  mémoire, avec un risque d'échange sur le disque en Q8. Produire les variantes d'un seul lancement (`-b N`)
  n'économiserait que ≈ 7 s par image (≈ 1 %), au prix de l'annulation, de la progression et des aperçus image par
  image.
- **Écarté** : plusieurs sd-cli en parallèle ; `-b N` pour les variantes.
- **Conséquences** : un lot de N images dure N fois une image. À revoir si une mesure réelle de deux calculs
  simultanés montrait un gain, ou sur une machine à plusieurs GPU.

## 2026-10-13 · Notification de fin de génération par Web Push

_Révisée le 22/10/2026 (message « Image incognito prête ») par « Refonte « Chambre noire » : lumière inactinique, pixel,
Labo et Tirages, pile à trier » (incognito retiré)._

- **Contexte** : le porteur veut être prévenu à la fin d'une génération (souvent plus de 10 minutes) sur son téléphone,
  où Android met en pause une application en arrière-plan.
- **Décision** (porteur) : l'ordinateur envoie une notification Web Push (bibliothèque `pywebpush`, qui ajoute
  `cryptography`, `py-vapid`, `http-ece`, `requests` et `aiohttp`) à chaque appareil abonné, terminée ou en échec.
  Autorisation demandée au premier appui sur Générer, interrupteur dans Réglages pour les couper. Le message ne contient
  ni prompt ni nom de fichier, car il transite (chiffré) par le service du navigateur ; en incognito : « Image incognito
  prête ». Pas de notification quand l'application est à l'écran.
- **Écarté** : notification affichée par la page seule (aucune dépendance, mais rien n'arrive une fois l'application
  mise en pause en arrière-plan) ; service tiers comme ntfy (le message sortirait en clair vers un tiers).
- **Conséquences** : nouvelle dépendance ; fonctionne seulement en HTTPS (Tailscale) ou sur l'ordinateur ; l'ordinateur
  doit pouvoir joindre le service de notification (Internet).

## 2026-10-13 · Barre d'état du téléphone : couleur calculée plutôt que plein écran

- **Contexte** : le porteur veut que l'application installée « continue » sous la barre d'état d'Android, sans bande
  de couleur.
- **Décision** : rester en `display: standalone` et donner à `<meta name="theme-color">`, à chaque changement de vue
  ou d'image, la couleur du haut de l'écran calculée en JavaScript (`syncThemeColor` : moyenne du haut de la miniature
  floutée en fond, avec les voiles du CSS). Chrome peint la barre d'état de cette couleur.
- **Écarté** : dessiner sous la barre d'état (pas encore possible pour une application installée avec Chrome stable :
  bug Chromium 407420295, correctif désactivé par défaut) ; `display: fullscreen` (cache l'heure et les notifications) ;
  `theme-color` transparent (non documenté, ignoré).
- **Conséquences** : la bande reste unie (pas de dégradé ni d'image dessous). Un bug Chromium signalé en septembre 2026
  (559396686) dirait que les applications installées ne suivent plus un `theme-color` changé en cours de route : à
  vérifier sur le téléphone.

## 2026-10-13 · Zoom de la visionneuse temporaire, au pincement

- **Décision** (porteur) : pincer zoome l'image, qui passe au-dessus de tous les éléments et peut couvrir tout
  l'écran, puis revient à sa taille dès qu'on relâche les doigts. Plus de double appui pour zoomer ; sur ordinateur, la
  molette zoome et un clic remet à la taille.

## 2026-10-13 · Images d'entrée conservées avec chaque image

_Révisée le 22/10/2026 (exception de l'incognito) par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo et
Tirages, pile à trier » (incognito retiré)._

- **Contexte** : le porteur veut revoir depuis la galerie les images de départ d'une édition ou d'un dessin guidé, et
  repartir de l'une d'elles. Elles n'existaient que dans `jobs/<id>/`, dont seuls les 20 derniers sont gardés.
- **Décision** : en fin de job (hors incognito et calibration), copier `init.png` et `ref_N.png` dans
  `outputs/.inputs/<nom de l'image>/`, servis par `/api/input` et supprimés avec l'image. `mask.png` (masque noir et
  blanc) n'est pas gardé : la zone peinte (`ref_1.png`) montre la même chose de façon lisible. Au démarrage, les images
  plus anciennes récupèrent leurs entrées si leur dossier de travail existe encore.
- **Écarté** : lire les entrées dans `jobs/` (perdues après 20 générations).
- **Conséquences** : plus de place sur le disque (une ou plusieurs images PNG par édition).

## 2026-10-13 · Incognito : fermer l'application arrête la génération

_Remplacée le 22/10/2026 par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo et Tirages, pile à trier »
(incognito retiré)._

- **Contexte** : une génération incognito a été perdue après un redémarrage de l'application sur le téléphone. Sur
  Android, le système peut aussi libérer une application restée en arrière-plan.
- **Décision** (porteur) : garder le comportement initial. Fermer ou recharger l'application arrête la génération
  incognito et la perd.
- **Écarté** : se rattacher à la génération à la réouverture, en retenant seulement le numéro du job sur le téléphone.

## 2026-10-13 · Partager et Copier seulement là où le navigateur les permet

- **Décision** : les boutons utilisent l'API de partage (`navigator.share` avec un fichier) et le presse-papiers
  (`navigator.clipboard.write`). Ils sont masqués quand le navigateur ne les offre pas, en pratique hors HTTPS
  (adresse `http://` du Wi-Fi), au lieu d'afficher un bouton qui échoue.

## 2026-10-13 · Mode incognito : image gardée en mémoire, remise une seule fois

_Remplacée le 22/10/2026 par « Refonte « Chambre noire » : lumière inactinique, pixel, Labo et Tirages, pile à trier »
(incognito retiré)._

- **Contexte** : le porteur veut une image téléchargeable mais gardée nulle part sur l'ordinateur, perdue à la
  génération suivante ou au rechargement de l'application, avec tout ce qui s'y rattache (job, aperçus).
- **Décision** : sd-cli ne lit et n'écrit que des fichiers. Le travail se fait donc dans `jobs/incognito_<id>/`,
  supprimé dès la fin du job et au démarrage suivant. Le serveur garde le PNG en mémoire, le remet une fois à la page
  (`/api/job/<id>/result`), puis la page lui fait oublier le job (`/forget`). La page l'affiche depuis une adresse
  `blob:`. Une nouvelle génération purge les jobs incognito terminés, et un rechargement pendant la génération l'arrête
  (`pagehide` avec `keepalive`). Pas de ligne dans le journal, pas de mesure de calibration (elle note la taille et
  l'heure), aucun détail dans `logs/`. Le prompt n'est pas retenu comme brouillon. Le mode (bouton à droite de Générer, inactif pendant une génération), lui, reste actif d'une
  visite à l'autre, pour ne pas repasser en mode normal sans s'en rendre compte. Éditer et Dessiner restent possibles
  sur l'image incognito.
- **Écarté** : disque en mémoire vive (`hdiutil` sur Mac) : propre à macOS et plus complexe, pour un gain faible sur
  un SSD. Garder l'image côté serveur jusqu'à une expiration : elle survivrait au rechargement de la page.
- **Conséquences** : les fichiers touchent brièvement le disque (limite écrite dans le README). Une image qui n'a pas été
  téléchargée est perdue.
- **Modifiée le 14/10/2026** (porteur, avec la file d'attente) : plus de purge à chaque nouvelle génération ; la page
  garde une image incognito jusqu'à ce qu'elle ait été vue puis quittée, et le serveur jusqu'à ce que la page l'ait
  récupérée. Le bouton Incognito n'est plus bloqué pendant une génération : chaque génération garde le mode de son
  lancement. À la fermeture, la page fait oublier toutes ses générations incognito en un envoi (`/api/forget`).

## 2026-10-13 · Application installable via `tailscale serve`

- **Contexte** : Chrome n'installe une page comme application qu'en HTTPS, et le téléphone doit joindre le Mac hors du
  Wi-Fi.
- **Décision** : le HTTPS est fourni par `tailscale serve` (certificat valide), qui relaie vers 127.0.0.1. Une requête
  relayée (en-têtes `X-Forwarded-*` ou `Tailscale-User-Login`) n'est jamais traitée comme venant du Mac : elle demande le
  code. Le manifeste, les icônes et le service worker sont servis sans cookie, car le navigateur les demande sans. Le
  cookie d'accès est `SameSite=Lax` et non `Strict` : Chrome Android traite l'ouverture de l'application installée
  comme une arrivée d'un autre site, et redemandait le code à chaque ouverture. Les POST restent protégés par le contrôle
  d'origine.

## 2026-10-13 · Liste blanche de `Host` et contrôle d'origine des POST

- **Contexte** : une revue de sécurité a confirmé deux failles exploitables depuis une page web ouverte sur le Mac :
  rebinding DNS vers 127.0.0.1 (lecture du code d'accès, des prompts et des images) et requête forgée en `text/plain`
  (génération lancée à l'insu de l'utilisateur).
- **Décision** : n'accepter que les `Host` locaux et ceux du Wi-Fi et de Tailscale calculés au démarrage. Refuser tout
  POST `Sec-Fetch-Site: cross-site` ou dont l'`Origin` diffère de l'origine du `Host` (403), et exiger
  `Content-Type: application/json` (415). Le Mac n'est « local » que si son `Host` l'est aussi.
- **Écarté** : accepter toute adresse IP littérale (sûr face au rebinding, mais hors du plan ; à décider par le porteur) ;
  compter sur les protections des navigateurs (Safari n'en a pas) ou sur un filtrage DNS du routeur.
- **Conséquences** : si l'IP du Mac change, l'ancienne est refusée jusqu'au redémarrage (le nom `.local` reste valable).
  Toute requête de l'interface doit envoyer `Content-Type: application/json`.

## 2026-10-13 · Accès du téléphone par un code et un cookie

- **Décision** : avec `--lan`, tout appareil autre que le Mac saisit une fois un code de 8 caractères tiré au hasard
  (`tools/access_code.txt`, non versionné). Le cookie, valable un an, est l'empreinte SHA-256 du code, pas le code.
  Une seconde d'attente suit chaque code faux. L'adresse et le code ne sont montrés que sur le Mac lui-même.
- **Écarté** : chiffrement HTTP sur le Wi-Fi (intercepter le cookie revient à intercepter le code ; changer le code
  invalide le cookie).

## 2026-10-13 · Encodeur GGUF officiel et réglages Metal sur Mac

- **Contexte** : Metal n'a pas de calcul int8 dans stable-diffusion.cpp. L'encodeur int8 de Comfy-Org tournait sur le
  processeur, à ≈ 2 min 30 par référence 512×512.
- **Décision** : sur Mac, prendre l'encodeur GGUF Q8_0 de Qwen et sa tour vision (≈ 3 s pour la même référence), avec
  sd.cpp `master-959`, tout sur le GPU. Options : `--fa` (sans elle, la tour vision provoque une faute mémoire du GPU sur
  une référence 2048×2048), `--params-backend te=disk` (libère l'encodeur et laisse la place au cache de préfixe),
  `--mmap` (fiable depuis `master-959`).
- **Écarté** : encodeur int8 sur le processeur (trop lent) ; VAE sur le processeur (11 fois plus lent).

## 2026-10-13 · Estimations de durée calibrées sur la machine

- **Décision** : modèle de coût par étape `a·n + b·n²` (n = longueur de la séquence), remplacé par `a·nt + b·nt·n` avec
  le cache de préfixe (release ≥ 903). S'y ajoutent l'encodage, le décodage proportionnel aux pixels et une part fixe.
  Les coefficients partent de valeurs propres au moteur et sont ajustés sur les 40 dernières mesures par moteur et par
  modèle, résumées par des médianes. Chaque mesure garde la release de sd.cpp qui l'a produite. Trois générations de
  calibration terminent l'installation.
- **Conséquences** : la formule est dupliquée en JavaScript dans l'interface et doit rester alignée.

## 2026-10-13 · Téléchargements épinglés et vérifiés

- **Décision** : moteur et modèles épinglés sur une release ou un commit précis, vérifiés par SHA-256, avec reprise des
  téléchargements interrompus.
- **Contexte** : le dépôt Hugging Face du modèle a été renommé (constaté le 12/10/2026) ; épingler protège contre ce
  genre de changement.

## 2026-09-23 · stable-diffusion.cpp plutôt que ComfyUI

- **Contexte** : la machine visée est un portable Windows à Radeon intégré.
- **Décision** : moteur stable-diffusion.cpp (Vulkan sous Windows, Metal sur Mac), avec `sd-cli` lancé à chaque
  génération ; grâce à `--mmap` et au cache disque, le modèle se recharge presque instantanément.
- **Écarté** : ComfyUI, qui repose sur PyTorch : pas de backend GPU utilisable sur les Radeon intégrés sous Windows
  (ROCm Windows ne couvre que RDNA3/RDNA4, DirectML est limité à d'anciennes versions), donc calcul sur le seul
  processeur. Avec une carte NVIDIA, ComfyUI resterait plus rapide.

## 2026-09-23 · Correctif de l'encodeur int8 sous Windows

- **Contexte** : sd.cpp `master-890-74988b2` interprète mal la table d'embeddings quantifiée de l'encodeur int8 au
  format ComfyUI, et plante au chargement.
- **Décision** : `tools/fix_int8_te.py` crée une copie dont seule cette table repasse en bf16 (dé-rotation Hadamard
  comprise), le reste restant en int8.
- **Conséquences** : inutile avec `master-959` (vérifié sur Mac) ; à retirer quand le moteur Windows passera à cette
  version.
