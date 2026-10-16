# État du projet

## État

Mis à jour le 16/10/2026.

- **Fonctionnel** sur Windows (Vulkan, CPU, CUDA en option ; sd.cpp `master-890`) et sur Mac Apple Silicon (Metal ;
  sd.cpp `master-959`, encodeur GGUF). Modèles Q4_K_M et Q8_0. Trois usages (texte → image, édition, dessin guidé),
  galerie avec visionneuse (zoom au pincement, partage, copie, images d'entrée), estimations calibrées, mode incognito,
  notification de fin de génération (Web Push), file d'attente visible (« Générer » toujours actif), variantes (mode
  Créer) et campagnes (mode Éditer) avec lots dans la galerie, prompts enregistrés et prompts types, espace privé
  chiffré (entrée par le cadenas de la Galerie), étanche à l'espace public (galerie, file, saisie et prompts
  enregistrés propres à chaque espace). Banc de test permanent sans GPU :
  `venv/bin/python -m unittest discover -s tests` (168 tests, ≈ 1 min 20) ; tests d'interface `tests/check.py --ui`
  (41 tests).
- **Chez le porteur** : service macOS lancé avec `--lan`, utilisé depuis le téléphone par le Wi-Fi et par Tailscale
  (application installée en HTTPS via `tailscale serve`). Modèle Q8_0 par défaut (`tools/config.json`).
- **En cours** : livraison de la miniature des visionneuses à la taille de l'image complète et du retrait de
  « Rendre privée » (`1664321`, `fd94cbd`) : PR de `dev` vers `main`, `git pull --ff-only` dans le dossier principal,
  relance du service (`tools/launch.py` a changé), puis essai sur le téléphone de l'arrivée des images d'entrée
  privées. Livrés avant : la correction de la fuite et des glitchs d'affichage et la rétrospective qui a suivi (PR #5,
  essais du porteur bons), le parcours « Cloisonnement espace privé, file et saisie » (PR #4).
- **Fait avant** : file d'attente, lots (variantes, campagne), prompts enregistrés et espace privé chiffré. Spécification
  prête (`docs/specs/2026-10-14_lots-espace-prive-prompts.md`), découpée en 13 tickets Asana (liste et ordre dans
  `travail/tasks/2026-10-14_lots-espace-prive-prompts.md`) ; liste des prompts types validée par le porteur. Groupes A (banc, robustesse, file visible, incognito dans la file) et
  B (variantes, lots dans la galerie, campagne), C (prompts) et D (durcissement de l'incognito, espace privé) faits,
  revus et fusionnés, puis E (durcissement de l'espace privé) : les 15 tickets sont faits. Restent les essais sur le
  téléphone et une vraie génération avec le nouveau code. L'espace privé ne s'ouvre plus que par l'adresse HTTPS
  (`tailscale serve`) ou sur le Mac.
- **À vérifier par le porteur**, sur le téléphone par l'application installée (testé seulement dans Chrome sur le Mac,
  en vue de téléphone) :
  - télécharger, partager et copier une image, dont une image incognito (adresse `blob:`) ;
  - la notification : autorisation à la première génération, réception application fermée, toucher pour la rouvrir ;
  - la barre d'état qui prend la couleur du haut de l'écran dans la visionneuse (un bug Chromium pourrait l'empêcher) ;
  - la file d'attente (pastille « +N en attente », feuille de la file, rangée de vignettes sous l'image) et l'incognito
    dans la file (deux images incognito gardées jusqu'à être vues puis quittées) ;
  - les variantes (grille, « Garder celle-ci »), les lots dans la galerie (badge, « Voir le lot », « Tout
    télécharger », qui peut demander d'autoriser plusieurs téléchargements) et la campagne ;
  - la feuille des prompts (bouton « Prompts » sous le champ de texte) ;
  - l'espace privé : entrée par le cadenas de la Galerie, thème, sortie, verrouillage à la fermeture (inconstant dans
    Chrome sans écran ; l'expiration après 15 min reste le filet), cookie `SameSite=Strict` avec l'application
    installée ;
  - après la livraison du parcours des espaces étanches : plusieurs photos d'un coup avec le sélecteur Google Photos,
    vidage après « Générer », saisie propre à chaque espace, message quand l'espace se ferme seul, file sans les
    générations de l'autre espace, génération privée retrouvée après un rechargement (cas « page rechargée espace
    encore ouvert », lié à `pagehide`), prompts privés, cadenas et pastille.
- **Pistes ouvertes** (aucune demandée) :
  - `sd-cli.log` reste ouvert si la boucle de lecture de `run_job` lève une exception ; `queue_position` trie tout
    `S.jobs`, qui ne fait que grossir, à chaque lecture (trouvés par la revue de groupe A) ;
  - course entre la route d'annulation et `worker()` sur le statut d'une génération (sans verrou), et `open(...).read()`
    sans fermeture dans `launch.py` et `estimate.py` (avertissements masqués dans le banc) (trouvés le 14/10/2026) ;
  - une génération reprise après un rechargement n'a ni dimensions ni coefficients propres : le cadre ne prend sa forme
    qu'à la fin ;
  - le faux moteur du banc n'a pas été essayé sous Windows (lanceur `sd-cli.cmd`) ;
  - un passage du banc a échoué une fois pendant la session des pistes, sans que la sortie ait été gardée, puis plus
    jamais en 13 passages (test instable possible, à surveiller) ; `tests/test_private_rekey.py` garde un compteur en
    liste à un élément, contraire à `CODING_STANDARDS.md` ;
  - la galerie trie par `st_mtime` en secondes entières : les images d'un même lot peuvent ressortir dans le désordre ;
  - le résultat d'une génération incognito reste servi en `http://` sur le Wi-Fi (laissé tel quel par le porteur le
    15/10/2026 : l'incognito vise le disque, pas le réseau) ; `/api/status` dit à tout appareil connecté si un espace
    privé existe (`private.exists`, nécessaire pour proposer la création ou le code), ce qui révèle son existence ;
  - `do_POST` lit `Content-Length` sans plafond (une campagne de 10 photos en data URL pèse lourd) ;
  - `push_subscriptions()` écrit `tools/push_subscriptions.json` en place, de façon non atomique ; les messages 500
    des routes de prompts citent le texte de l'exception (chemin local possible, visible des seuls appareils admis) ;
  - accepter toute adresse IP littérale dans la liste blanche de `Host`, pour qu'un changement d'IP du Mac ne coupe plus
    l'accès par IP (décision au porteur) ;
  - `start-ui-sdcpp.cmd` et `workflows/*.json` sont périmés (à mettre à jour ou à retirer) ; `sd_port` de
    `tools/config.json` n'est lu nulle part ;
  - incognito et notification : si Android a fermé l'application en arrière-plan, toucher « Image incognito prête »
    rouvre une page qui ne se rattache pas au job incognito ; l'image reste en mémoire sans pouvoir être affichée, et
    depuis le 14/10/2026 (plus de purge à chaque nouvelle demande) jusqu'au redémarrage du serveur ; une expiration à
    24 h est prévue par le ticket « Durcir l'incognito et limiter la reprise à l'appareil ». Piste : laisser la page reprendre une fois un job incognito terminé et jamais récupéré
    (option écartée par le porteur le 13/10/2026, à lui reproposer avec cette raison) ;
  - `tests/run_tests.py --only edit` cherche `outputs/test_t2i_512.png`, que plus rien ne produit, et retombe sur
    `tests/test_scene.png` ;
- **Ménage local** : fait le 15/10/2026. Il ne reste que le dossier principal (`main`) et le worktree
  `.claude/worktrees/dev`.

## Journal

### 2026-10-16

- Après la livraison (PR #5, `abbb3ec`, service relancé), essais du porteur sur le téléphone : version servie, plus de
  fuite des images d'entrée ni de la galerie privée, zoom des images d'entrée : bons. Restait un saut des images
  d'entrée privées à leur arrivée : la miniature (320 px) s'affichait à sa taille avant l'image complète ; elle prend
  maintenant la taille de l'image complète, en unités de la scène pour suivre le panneau et la rotation (`showImage`,
  `fit`, `fitThumb` ; revue : une première version en pixels figés déformait la miniature), tests ajoutés. « Rendre
  privée » retiré à la demande du porteur (bouton, feuille, route `/api/private/adopt`, `adopt_output`,
  `drop_from_journal`, `tests/test_adopt.py`) : une image reste dans son espace (`DECISIONS.md`).

- Rétrospective de la session (fuite et affichage des images), appliquée en entier à la demande du porteur :
  `check.py` contrôle aussi les fichiers nouveaux pas encore ajoutés à git et refuse une adresse donnée à la main à une
  image affichée (`d77e1aa`) ; relais façon `tailscale serve` dans le pilote des tests d'interface et test
  `relais.test.mjs` (`fe25f85`) ; version du code servi et serveur « à relancer » dans le panneau Moteur, et règle du
  compte rendu « en ligne ou seulement sur `dev` » (`a4f5e62`) ; contrôle rapide pendant les corrections
  (`7c81c9b`) ; test d'étanchéité `etancheite.test.mjs` (parcours privé complet, sortie par « Sortir » et par le Mac,
  fouille de toute la page), qui a trouvé un reste de plus : le journal du panneau Moteur gardait le nom `prive_…`
  d'une image privée supprimée (ses lignes écrites dans l'espace en sortent maintenant avec lui). Revue de ces commits
  (sous-agent Opus, effort xhigh) : ligne du journal rattachée à l'espace où l'action a commencé, « rendue privée »
  sans nom d'image, git appelé seulement dans un dépôt et jamais après un échec (Mac sans outils de développement),
  « à relancer » seulement quand `tools/launch.py` a changé, délai maximal du relais (`2361c10`) ; puis, après la revue
  de ce commit : une ligne privée finie hors de l'espace n'entre plus du tout au journal, les lignes de la demande et
  de fin de génération portent leur espace, l'empreinte compte aussi `estimate.py`, un délai dépassé de git est
  retenté, test d'étanchéité sur le nombre exact d'images.

- Retours du porteur sur le téléphone, qui tourne encore sur `main` (sans `d3169f8`) : image d'entrée privée revue un
  instant dans l'espace public, et galerie privée revue un instant en revenant à la galerie publique après une sortie
  faite depuis un autre onglet (même cause que la fuite : la grille gardait ses images, corrigée par `d3169f8`, test
  ajouté, rouge sur `main`). Ajouté : zoom au pincement (et à la molette) sur les images d'entrée, par les gestes de la
  visionneuse mis en commun (`zoomable`) ; première image d'entrée chargée en avance dès l'image affichée, pour
  qu'elle s'ouvre sans attente. Aperçus privés : le Mac écrit bien `preview_000.png` pendant une génération privée
  (observé dans son dossier de travail) et le porteur les a vus s'afficher à ce dernier essai ; problème non reproduit,
  laissé ouvert s'il revient. Revue de sécurité du diff (`b547a4f..3591b85`) : rien de bloquant ; corrigés aussi, à
  la sortie, un geste des images d'entrée qui pouvait rouvrir une entrée privée cachée, et le prompt, les réglages,
  la liste et les liens de téléchargement privés restés dans la page cachée (antérieurs au diff ; `9f9e269`), puis,
  après la revue de ce commit, la feuille « Voir le lot » d'un lot privé fermée et vidée à la sortie, tout lien vers
  une route privée retiré de la page (nom `prive_<id>` compris) et le geste en cours abandonné à la fermeture
  (`d5334b2`) ; puis visionneuse et images d'entrée vidées par leur propre fermeture, après le fondu (`emptyViewer`,
  `emptyInputs`), sans erreur sur un appui pendant ce fondu (`a4f49ac`) ; puis vidage annulé si la vue se rouvre pendant
  le fondu, geste abandonné à chaque changement d'image, tests du vidage immédiat à la sortie et du lien de la zone
  de résultat (revues en sous-agent Opus, effort xhigh, à la demande du porteur) ; fond flouté de la visionneuse de
  nouveau vidé à la fermeture (sinon une image incognito effacée, ou une publique dans l'espace privé, restait en
  fond). Dernière revue (`8d81b13`) : aucun vrai bogue ; vidage des vues à l'entrée dans l'espace privé retiré (il
  coupait le fondu sans rien protéger), test et commentaires précisés.
  À reporter dans Asana (accord du porteur) : un ticket pour la fuite et les glitchs d'affichage (`d3169f8`,
  `9f9e269`), un pour le zoom et le préchargement des images d'entrée (`3591b85`).
- Fuite de l'espace privé à l'écran corrigée (signalée par le porteur) : une `<img>` qui reçoit une autre adresse garde
  l'image d'avant à l'écran jusqu'au chargement de la nouvelle, donc l'image d'entrée privée vue avant réapparaissait
  un instant dans l'espace public (et les « glitchs » entre deux images). Toute image passe désormais par
  `showImage` (vidée, puis remplie une fois l'image décodée, miniature d'abord, voisines chargées en avance) ; la
  sortie de l'espace retire de la page toute image privée, même cachée (galerie, vignettes des entrées, grille d'un lot)
  ou encore en chargement ; une galerie privée reçue après la sortie est ignorée. Aperçu suivant affiché seulement une
  fois chargé (plus d'image cassée ni de cadre vide). Test d'interface `tests/ui/images.test.mjs`, rouge avant le
  correctif. Aperçus de l'espace privé « qui ne marchent pas » : non reproduits au banc (ils s'affichent, en vue du
  téléphone, depuis le Mac) ; à observer sur le téléphone (suite dans l'entrée ci-dessus).

### 2026-10-15

- Rétrospective du parcours « Cloisonnement espace privé, file et saisie » (session mère et trois sessions de
  groupe, 21 pistes), appliquée : règles de revue (écriture asynchrone liée à un espace, génération rapprochée par
  identifiant, trois autres) et repères de la carte du code (`46f9713`) ; banc qui échoue tout de suite sur un suivi
  refusé, commande `HOLD` du faux moteur, droits 600/700 de tout `private/` (ticket coché), limite de 120 caractères
  vérifiée sur les lignes ajoutées, `check.py` plus rapide (`--quick`, `--ui <fichiers>`, banc et interface en
  parallèle : 186 s → 96 s), avis « zone sensible », tests d'interface `suivi` et `brouillons`, sonde
  `tests/ui/probe.mjs` (fusion de `retro-controles`) ; avis limité à `tools/`, consigne des contrôles complets
  (`8203f18`). Dossiers de l'espace privé réel passés en 700 à la main. Côté mathis-plugins : brief des sessions
  liées (adresse stable de la mère, revues), skills `pr` et `push`, `CLAUDE.global.md` allégé.
- Version 0.3.0 (`94ac860`, tag `v0.3.0`) : espaces public et privé étanches, prompts privés chiffrés, retouches de
  la saisie ; compte rendu du parcours validé par le porteur. Reste la livraison (`/project:push`, `/project:pr`).
- Groupe C (prompts privés et prompt repris) fait par une session liée et fusionné dans `dev` (`1a712d0` à
  `eeca134`) : prompts enregistrés de l'espace privé chiffrés dans `private/prompts` (routes `/api/private/prompts`,
  rechiffrés au changement de code, format noté dans `DECISIONS.md`) ; prompt complet donné à la page qui reprend une
  génération de son espace. Revue du groupe (2 constats corrigés, 4 laissés), revue de sécurité sans constat. Vérifié
  après fusion : `tests/check.py --ui` → Ran 162 tests OK, interface 26/26 OK. Trouvé : les fichiers de
  `private/items/` n'ont pas les droits 600 (antérieur) ; le README dit encore que les tests d'interface ne couvrent
  que les écrans principaux et « Garder celle-ci ». Question au porteur : un `private/prompts` illisible bloque toute
  la liste privée (gardé ainsi, ou mis de côté en `.corrompu`).
- Groupe B (file cloisonnée) fait par une session liée et fusionné dans `dev` (`190ce1c` à `c9a452b`) : curseur
  retiré et message quand l'espace privé se ferme seul ; file, pastille, génération en cours et dernière image
  propres à l'espace de l'appareil (durée `ahead` pour le travail caché) ; suivi, aperçu et annulation d'une
  génération privée refusés hors de l'espace (404) ; génération privée retirée de l'écran à la sortie et suivie de
  nouveau au retour. « Dans l'espace privé » exige aussi une requête sûre. Revue du groupe (4 constats corrigés, 4
  laissés), revue de sécurité sans constat. Vérifié après fusion : `tests/check.py --ui` → Ran 139 tests OK,
  interface 23/23 OK. Points ouverts remontés au porteur : oubli d'une génération privée par sa seule page, génération
  privée finie après la sortie gardée 24 h en mémoire, génération publique annulée pendant l'espace privé retirée sans
  message, prompt d'une génération privée reprise limité à 80 caractères.
- Groupe A (saisie et en-tête) fait par une session liée et fusionné dans `dev` (`d1d42b3` à `4a5a55c`) : photos
  choisies d'un coup toutes ajoutées (cause confirmée par le test), onglet vidé après une demande acceptée, saisie
  propre à chaque espace (onglets marqués retirés), cadenas aussi visible que Rafraîchir, pastille dans sa bulle.
  Revue du groupe faite (3 constats corrigés, 4 laissés), revue de sécurité sans constat au-dessus du seuil.
  Vérifié après fusion : `tests/check.py --ui` → Ran 131 tests OK, interface 18/18 OK. Restent au porteur : le vrai
  sélecteur de photos sur le téléphone, et une remarque de sécurité à trancher (fermeture automatique de l'espace
  pendant une frappe : les touches suivantes vont dans la saisie publique).
- Demandes du porteur après essai sur le téléphone, cadrées par un grilling (décision « Espaces public et privé
  étanches » dans `DECISIONS.md`, termes « Espace public » et « Espace privé » dans `GLOSSARY.md`) : prompts
  enregistrés privés chiffrés et cloisonnés ; file d'attente et générations en cours cloisonnées par espace (dont le
  faux « Génération incognito » d'une génération privée, et la progression privée visible après la sortie jusqu'au
  rechargement) ; saisie propre à chaque espace ; texte et images vidés après « Générer » ; cadenas aussi visible que
  Rafraîchir ; pastille « +N en attente » qui dépasse de l'île. Bug trouvé : en Éditer, une sélection de plusieurs
  photos n'en ajoute que la première (le gestionnaire `change` vide le champ avant d'avoir lu tous les fichiers ;
  cause lue dans le code, à confirmer par un test). Spécification `docs/specs/2026-10-15_espaces-etanches.md`, découpée en 7 tickets Asana (groupes A saisie et en-tête, B file cloisonnée, C prompts privés).
- PR #2 (`dev` → `main`, suites de la rétrospective) fusionnée (`72f19ad`) après un premier passage rouge de la CI :
  `test_running_or_waiting_incognito_is_not_expired` était instable sur la machine GitHub, plus lente (délai d'oubli
  de 0,1 s gardé pendant l'attente de la fin), corrigé par `14b031b`. La vérification `checks` est désormais exigée
  par la protection de `main`. Service relancé sur `main`.
- Rétrospective du parcours (session principale et 5 sessions de groupe, d'après leurs journaux) : 16 pistes. Les 11
  propres au dépôt, faites par une session liée et fusionnées dans `dev` (`e8e3e1c` à `04140c0`) : `tests/check.py`
  (tous les contrôles en une commande, `--link-venv` pour un worktree, `--ui`), test « dépôt public », banc plus sûr
  (messages courts, SIGTERM, plus de `sleep` de synchronisation), pilote d'interface et tests dans `tests/ui/`, CI
  « Contrôles » (job `checks`) sur les PR vers `main` et les push sur `dev`, `CODING_STANDARDS.md`,
  `docs/agents/carte-du-code.md`, `docs/agents/session-deleguee.md`, `CLAUDE.md` allégé (18,8 → 12,9 Ko), tickets
  qui renvoient à la spec. Vérifié après fusion : `tests/check.py --ui` → Ran 131 tests OK, interface 5/5 OK. Les 5
  pistes communes (règles de revue, `/project:push`, `suivi-asana`, flow-board en mode délégué) faites dans
  mathis-plugins.
- Ménage : worktrees et branches des groupes A à E supprimés (contenu vérifié identique à `main`), ainsi que
  `securite-serveur` (branche `fix/server-host-origin`, un commit de notes du 13/10/2026 jamais poussé, avec des
  informations propres au réseau du porteur) et `youthful-bell-35c6b0` (déjà dans `main`).
- Branches : `dev` créée (depuis `36d3a70`) avec son worktree `.claude/worktrees/dev`, où l'on code désormais ;
  `main` protégée sur GitHub (PR obligatoire, ni push direct ni forcé) et ne reçoit plus que des PR depuis `dev` ; le
  dossier principal reste sur `main` pour le service (décisions du porteur, règle dans `CLAUDE.md`).
- Push de la version 0.2.0 : le `git pull --rebase` de `/project:push` a aplati l'historique local (deux commits de
  fusion du groupe B) alors que le dépôt distant n'avait rien de nouveau, et 39 commits ont changé de hash. Le porteur
  a choisi de garder l'historique aplati : hash corrigés dans ce fichier et dans le plan, tag `v0.2.0` déplacé sur le
  nouveau commit de version, correspondance ancien → nouveau notée dans Asana (tâche mère). Les commentaires Asana des
  tickets et les branches `worktree-groupe-*` gardent les anciens hash.
- Version 0.2.0 (`059c342`, tag `v0.2.0`) : `CHANGELOG.md` créé, la version du 23/09/2026 comptée comme 0.1.0.
  Rapport du parcours validé par le porteur.
- Une génération privée apparaît dans la file des autres appareils exactement comme une génération incognito, et les
  messages d'échec de `logs/` disent « incognito » (`c813e52`, ticket Asana `1219532320923400`, décision du porteur).
  CLAUDE.md complété avec la règle `_secure`, le rechiffrement et les trois origines du banc (`c516a64`, validé par le
  porteur). 129 tests au vert, service relancé.
- Groupe E fait dans une session à part (worktree) et fusionné (`2d08157` à `0129251`) : notification neutre pour le
  privé, « Sortir » vide l'écran, suppression de l'espace sans code seulement depuis le Mac, espace privé seulement en
  HTTPS ou sur le Mac (`_secure` : adresse source locale et nom d'hôte local ou HTTPS de `tailscale serve`, jamais les
  en-têtes de relais), nouvelle paire de clés et rechiffrement au changement de code par `private/.rekey/` et bascule
  atomique de `space.json` (pannes simulées à 7 étapes sans perte). Revue de groupe : 9 constats, 7 corrigés ; revue
  de sécurité : aucune faille. 129 tests au vert après fusion, service relancé (nom HTTPS repéré au démarrage).
### 2026-10-14

- Porteur, sur les notes de la revue de sécurité du groupe D : notification neutre pour le privé, onglets privés
  vidés à « Sortir », suppression de l'espace sans code seulement depuis le Mac, espace privé ouvert seulement en HTTPS
  ou sur le Mac, nouvelle paire de clés et rechiffrement au changement de code. Regroupé dans le ticket Asana
  `1219520417161822` et dans la spécification (section 5).
- Groupe D fait dans une session à part (worktree) et fusionné : durcissement de l'incognito (`fed5f40` :
  identifiants de 128 bits, image non récupérée oubliée après 24 h, reprise limitée aux générations de l'appareil,
  jeton par page), espace privé (`28a6bc0`), générations et galerie privées (`5e1a504`), lots privés et héritage
  (`d5ce057`), « Rendre privée » (`864aef1`), revue de groupe (`39ebad8`, 9 constats, 8 corrigés dont un échec de
  « Rendre privée » qui pouvait perdre l'image). Revue de sécurité : aucune faille au seuil, quatre notes de
  conception soumises au porteur. Le porteur a revu l'interface en cours de route : espace discret, on y entre par le
  cadenas de la Galerie et on en sort par « Sortir » (DECISIONS.md) ; les trois tickets Asana concernés sont mis à
  jour. 117 tests au vert après fusion, service relancé, `jobs/` exclu de Time Machine (vérifié par `tmutil`).
- Groupe C fait dans une session à part (worktree), avec la nouvelle démarche par ticket (`/mattpocock-skills:tdd`,
  contrôles, `/mattpocock-skills:code-review`) : prompts enregistrés (`c80b875`, `tools/saved_prompts.json` non suivi,
  en 0o600) et prompts types (`19a832c`, `tools/prompt_types.json`, les 11 validés, comparés mot pour mot à la
  spec). Revue de groupe (`/code-review --fix`) : 9 constats, 6 corrigés (`511269e`). Revue de sécurité : aucune
  faille. Fusionné, 75 tests au vert, service relancé (11 prompts types servis). Choix de la session : titre de 80
  caractères, texte de 4 000, 500 prompts au plus ; choisir un prompt en incognito ne met pas à jour sa dernière
  utilisation (validé par le porteur) ; Dupliquer crée la copie sans ouvrir l'éditeur ; le filtre par usage
  s'applique aussi aux prompts types.
- Revue de groupe B (`/code-review --fix` puis `/security-review`, lancées par la session du groupe) : 4 corrections
  (`8ce12d4`) : « Garder celle-ci » supprimait aussi l'image gardée quand la galerie avait été rechargée pendant que la
  visionneuse était ouverte (choix par nom de fichier désormais), la limite de suivi de la page épargne le lot affiché,
  limite des 10 références dans `MAX_REFS`, corps de la notification d'une campagne (« Campagne de N photos
  terminée »). Aucune faille de sécurité. Fusionné, 60 tests au vert, service relancé. Laissé : la page redessine N
  fois au lancement d'un lot (coût sans bug).
- Revue de groupe A (`/code-review --fix` puis `/security-review`, lancées par la session du groupe) : 8 constats,
  3 corrigés (`8693a60` : génération annulée pendant la préparation arrêtée aussitôt, génération incognito en échec
  ou annulée oubliée par le serveur, lecture des dimensions unifiée), aucune faille de sécurité. Fusionné, 59 tests au
  vert, service relancé. Décisions du porteur sur les constats restants, regroupées dans un nouveau ticket Asana
  (`1219503935811144`) : expiration à 24 h d'une image incognito jamais récupérée, reprise après rechargement limitée
  aux générations de l'appareil, identifiant long pour l'incognito et le privé, jeton par page dans la file. Laissés
  en pistes : `sd-cli.log` resté ouvert si la lecture lève une exception, tri de `S.jobs` à chaque lecture.
- Porteur : la notification d'un lot en partie annulé garde son texte (« N images prêtes ») ; un ticket coché garde
  la ligne « Statut : fait » (écrit dans `docs/agents/triage-labels.md`).
- Groupe B fait dans une session à part (worktree), fusionné dans `main` (`2598994`) et service relancé : variantes
  en mode Créer (`63c3c99`), lots dans la galerie (`71713cd`), campagne en mode Éditer (`2598994`). 58 tests au vert
  après fusion, `py_compile` et `node --check` propres, contrôles dans Chrome sans écran en vue de téléphone.
- Liste des prompts types validée par le porteur (tâche Asana cochée) ; le ticket des prompts types est débloqué.
- Groupe A fait dans une session à part (worktree), fusionné dans `main` et service relancé : banc de test permanent
  à faux moteur (`5072ad5`), une erreur de préparation n'arrête plus la file et `/api/generate` valide la demande
  (`cf4f825`), file d'attente visible avec « Générer » toujours actif (`b9d58ca`), incognito dans la file (`db6342d`).
  36 tests au vert (relancés après fusion), `py_compile` et `node --check` propres, contrôles dans Chrome sans écran en
  vue de téléphone. Choix de la session : bornes de validation (64 à 4096 px, 1 à 200 étapes), estimation de chaque
  entrée de la file, incognito compris ; la zone de résultat garde l'image finie et la suite se suit dans une rangée
  de vignettes. Les 13 tickets Asana avaient été créés par erreur aussi dans la section « Orange · Cockpit EAS » (paramètre
  `default_project` avec `parent`) : retirés du projet avec l'accord du porteur, ils restent sous-tâches de la tâche
  mère.
- Découpage du chantier en 13 tickets Asana (sous-tâches de la tâche mère de Claude), chacun avec sa ligne
  « Bloqué par », et une tâche assignée au porteur pour valider la liste des prompts types.
- Suivi des tâches passé sur Asana (décision du porteur, revient sur le refus du 13/10/2026) : section « Qwen-Image
  local » et tâche mère de Claude créées dans le Hub. Configuration des skills mattpocock dans `docs/agents/`
  (tickets Asana, rôles de tri traduits en ligne « Statut : », glossaire et `DECISIONS.md`) et bloc « Agent skills »
  de `CLAUDE.md`.
- Cadrage (séance de questions, toutes les réponses validées par le porteur) de quatre fonctions : file d'attente
  visible avec « Générer » toujours actif, lots (variantes 1 à 4 en mode Créer, campagne de 10 photos au plus en mode
  Éditer), prompts enregistrés et prompts types, espace privé chiffré. Pas de calcul simultané : d'après les mesures de
  calibration, ≈ 95 % d'une génération est du calcul GPU (déduit, non mesuré en parallèle). Écrits :
  `docs/specs/2026-10-14_lots-espace-prive-prompts.md`, `GLOSSARY.md` (nouveau, vocabulaire de l'application) et deux
  entrées de `DECISIONS.md`. Le banc à faux moteur deviendra un banc permanent dans `tests/` (accord du porteur).

### 2026-10-13

- Annulation : le dossier de travail (images d'entrée, aperçus, journal du moteur) et une image finale déjà écrite sont
  supprimés, que la génération soit en cours ou en file d'attente. Banc avec un faux moteur : 9 contrôles, 4 passages
  (dont annulation juste après l'écriture de l'image, et génération menée au bout qui garde tout). Service relancé.
- Notification de fin de génération (Web Push, `pywebpush` ajouté à `requirements.txt` et installé dans le `venv` du
  Mac). Vérifié : banc serveur (17 contrôles : message déchiffré, signature VAPID, aucun prompt, incognito, échec,
  appareil désabonné retiré), puis vraie notification envoyée par Google à un Chrome de test en arrière-plan et affichée
  par le service worker. Service relancé. À vérifier sur le téléphone (autorisation à la première génération).
  Remise des notifications gardée 24 h si le téléphone est hors ligne ; interrupteur masqué si le serveur n'a pas
  `pywebpush`.
- Visionneuse sur le téléphone (dimensions du porteur, 367×760 à 2,5) : l'image dépassait sous le panneau des boutons
  (une grille CSS ne bornait pas `max-height:100%`, conteneur passé en flex) ; prompt retiré (Reprendre gardé) ; zoom
  au pincement temporaire, au-dessus de tout ; fenêtre des images d'entrée opaque ; couleur de la barre d'état calculée
  depuis le haut de l'écran. 21 contrôles ; à vérifier sur le téléphone : que Chrome suive bien `theme-color` changé en
  cours de route.
- Interface : glisser entre les onglets ; image zoomée tenue sous la barre du haut et le panneau ; Partager et Copier
  (visionneuse et résultat, masqués hors HTTPS) ; images d'entrée conservées dans `outputs/.inputs/` et visibles en
  grand depuis la visionneuse (glisser, Télécharger, Éditer, Dessiner) ; bouton incognito inactif pendant une
  génération. Génération incognito perdue à la fermeture : comportement confirmé par le porteur. 23 contrôles dans
  Chrome en mode tactile et contrôle de la route `/api/input` (noms piégés refusés) ; service relancé.
- Galerie : les miniatures manquaient parfois au premier affichage. Cause : la file d'attente des connexions du serveur
  (5 par défaut dans Python) débordait quand la galerie demandait toutes les miniatures pendant leur fabrication, d'où
  des connexions refusées (erreur relayée par Tailscale, absente de `logs/`). File portée à 128 (`Server`), miniatures
  écrites puis renommées, seconde tentative côté interface. Banc : 2 à 7 miniatures cassées par essai avant, 0 sur
  9 essais (jusqu'à 32 demandes simultanées) après. Zone de génération masquée dans la galerie ; visionneuse : zoom
  (pincer, double appui, molette), Télécharger en haut, quatre actions plus aérées en bas. 13 contrôles dans Chrome
  en mode tactile ; service relancé.
- Interface : niveaux de résolution renommés d'après le format vidéo au nombre de pixels le plus proche (360p, 540p,
  720p, 1080p, 1440p) ; la pastille sous le texte affiche ce libellé. Dans les Réglages, formats et résolutions
  n'affichent plus que leur libellé (ni « Carré », « Paysage »…, ni dimensions) ; les dimensions exactes restent en bas
  du panneau et au survol de la pastille.
- Interface : réglages par défaut 720p (≈1024 px), 40 étapes et aperçus toutes les 5 étapes ; l'incognito passe du
  panneau Réglages à un bouton à droite de Générer. Les réglages retenus avant ce changement sont remis une fois à ces
  défauts (format et incognito gardés). Vérifié par 11 contrôles dans Chrome sans écran.
- Incognito : l'interface passe en thème graphite sombre (couleur de la barre du navigateur comprise) tant que le mode
  est actif ; plus de message à l'activation. Vérifié par captures dans Chrome sans écran.
- Mise en place de la documentation de session : `CLAUDE.md`, `BRIEF.md`, `DECISIONS.md` et ce fichier, reconstitués
  depuis le README, le code et l'historique git.
- Mode incognito (`d5a745d`) : image gardée en mémoire et remise une fois, perdue à la génération suivante ou au
  rechargement. Vérifié par un banc avec un faux sd-cli et par 17 contrôles dans Chrome sans écran ; le service a été
  relancé. Poussé sur `main`.
- Vérification de ce qui est publié (le dépôt est public) : aucun secret ni donnée personnelle dans les fichiers suivis
  ni dans l'historique de `main`.
- Plus tôt dans la journée (commits `64c76b6` à `2e99704`) : prise en charge du Mac (Metal, encodeur GGUF, sd.cpp
  `master-959`), estimations calibrées sur la machine, accès depuis le téléphone (code d'accès, service macOS, galerie),
  refonte de l'interface (verre, barre d'onglets, panneau de réglages, visionneuse), correction du rebinding DNS et des
  requêtes forgées (plan dans `travail/tasks/2026-10-13_securite-serveur.md`), Tailscale et installation comme
  application, Q8_0 par défaut, allègement des effets sur écran tactile.

### 2026-09-23

- Première version : interface, lanceur et installation pour Windows (Vulkan), licence MIT, moteur CUDA en option et
  premières estimations de durée calibrées.
