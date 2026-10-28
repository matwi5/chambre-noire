# Décisions de conception

Une entrée par décision, la plus récente en tête. Une décision remplacée garde son entrée, avec le statut
« remplacée le <date> ». Entrées antérieures au 13/10/2026 reconstituées depuis le README, les commentaires du code et
les messages de commit.

## 2026-10-27 · Interface pour PC et tablette ; bouton Avant pour comparer une édition à son image d'entrée

- **Contexte** : grilling de deux demandes du porteur : « Actuellement l'app est optimisé pour mobile. Je veux que tu
  l'optimises en plus pour pc et tablette. » et « Je veux que, quand on appui longtemps sur une image généré en mode
  edit avec une seul image en input, l'image d'origine s'affiche a la place avec les exacte dimension, ca permet de
  faire une comparaison avant/après hyper rapide et fluide. » Questions posées avec une réponse recommandée ; un
  « oui » accepte la recommandation.
- **Décision** (porteur, 27/10/2026). Premier tour, réponse « 1. mac, pc window et tablette andoid / oui pou le
  reste » :
  - Q1 « Appareils visés : sur quels appareils comptes-tu t'en servir ? (a) le Mac dans un navigateur (fenêtre large)
    et un iPad, à tenir dans les deux orientations ; (b) le Mac seulement ; (c) un autre appareil : PC Windows,
    tablette Android ou taille d'écran précise, à me dire. » → « mac, pc window et tablette andoid ».
  - Q2 « Le Labo en grand écran : sur un écran large (à partir d'environ 1024 px, soit un iPad en paysage ou un PC),
    on passe à deux colonnes : à gauche, la pile et la carte en cours, avec une image bien plus grande ; à droite, le
    champ de création, toujours déplié (on ne le replie plus sur grand écran). Sur tablette en portrait (entre 700 et
    1023 px), on garde une seule colonne, élargie à environ 760 px. » → oui : « Oui, deux colonnes à partir de
    1024 px, une colonne élargie entre les deux. »
  - Q3 « Les onglets en grand écran : la barre flottante du bas (Labo, Tirages) monte dans la barre du haut, à côté
    du nom, à partir de 1024 px. Sur tablette en portrait, elle reste en bas. » → oui : « Oui, dans la barre du haut
    à partir de 1024 px. »
  - Q4 « La visionneuse en grand écran : à partir de 1024 px, l'image occupe tout l'espace à gauche. Le panneau
    d'infos et d'actions (prompt, Garder/Jeter, Éditer, Relancer…) passe en colonne à droite, au lieu d'être sous
    l'image. » → oui : « Oui, panneau à droite à partir de 1024 px. »
  - Q5 « Raccourcis clavier (PC) : un petit jeu de raccourcis : dans la visionneuse, ← et → pour l'image précédente
    ou suivante, Échap pour fermer ; dans la pile, → pour Garder et ← pour Jeter (le bandeau Annuler reste) ;
    Ctrl/⌘ + Entrée pour Révéler depuis le champ. Aucun raccourci ne marche pendant la saisie de texte, sauf Ctrl/⌘ +
    Entrée. » → oui : « Oui, ce jeu-là, sans plus. »
  - Q6 « Grille des Tirages : sur grand écran, des vignettes plus grandes (environ 220 px au lieu de 150) et des
    marges plus larges. » → oui : « Oui, environ 220 px à partir de 1024 px. »
  - Q7 « Où marche l'appui long : dans la visionneuse, pour une image de la pile ou des Tirages ; sur la carte du
    dessus de la pile, dans le Labo. Ce ne serait pas le cas sur les petites vignettes de la grille des Tirages, trop
    petites pour comparer. » → oui : « Oui : visionneuse et carte du dessus de la pile. » (l'appui long est ensuite
    remplacé par le bouton Avant, Q13 et Q20).
  - Q8 « Quelles générations : toute image produite par une édition qui avait exactement une image d'entrée. Cela
    inclut chaque image d'un lot de variantes sur une photo, et chaque image d'une campagne, chacune comparée à sa
    propre photo. » → oui : « Oui, variantes et campagnes comprises. »
  - Q9 « Le geste : l'image d'origine apparaît après environ 250 ms d'appui immobile, d'un coup, sans fondu ; elle
    reste tant qu'on maintient le doigt ; au relâché, l'image générée revient instantanément ; une petite étiquette
    « Avant » s'affiche pendant l'appui. (…) Sur PC, maintenir le clic de la souris fait la même chose. » → oui
    (délai et seuils remplacés par Q21).
  - Q10 « Format différent : si la sortie a presque le même rapport largeur/hauteur que l'entrée (écart d'arrondi de
    quelques pixels), l'entrée est étirée exactement dans le cadre de l'image générée : la superposition est
    parfaite. Si le rapport est vraiment différent (par exemple une sortie en 1:1 depuis une photo 16:9), l'entrée
    s'affiche entière, sans déformation, centrée dans le même cadre. » → oui : « Oui : étirée quand l'écart est
    minime, entière et centrée sinon. »
  - Q11 « Avec le zoom : dans la visionneuse, si l'image est zoomée, l'image d'origine apparaît avec le même zoom et
    le même cadrage, pour comparer un détail. » → oui : « Oui, même zoom et même cadrage. »
  - Q12 « Menu de l'appui long sur iPhone : (…) On le désactive, seulement sur les images comparables. » → oui, puis
    sans objet (bouton Avant, Q13).
- **Deuxième tour**, réponse « Q13. Ajouter un bouton avec un appui long qui affiche le avant quand on reste appuyé,
  on ne fait plus l'appuien long sur l'image mais sur tel. Faire comme les app d'edit photo. / Oui pour le reste » :
  - Q13 « Menu de l'appui long sur Android et Windows : (…) On le bloque de la même façon, sur les images comparables
    et seulement pour un appui au doigt. » → remplacée par la réponse citée : un bouton à maintenir, comme les
    applications de retouche, et plus d'appui long sur l'image.
  - Q14 « Ajouter des images sur PC : (…) On permet donc de déposer une ou plusieurs images n'importe où sur la
    colonne du champ, avec un cadre en surbrillance pendant le survol. » → oui : « Oui, dépôt sur toute la colonne du
    champ, avec surbrillance. »
  - Q15 « Savoir qu'une image est comparable : (…) une petite marque discrète « ⇆ Avant » dans le coin des images
    comparables » → devenue le bouton Avant (Q20).
  - Q16 « Dessin avec masque : on le compare à la photo non peinte (init.png), qui a déjà la taille exacte de la
    sortie : la superposition est parfaite. La référence peinte est ignorée pour la comparaison. » → oui : « Oui,
    comparaison avec la photo non peinte. »
  - Q17 « Dessin avec annotation : la photo d'origine non peinte n'est pas gardée. Trois choix : (a) pas de
    comparaison pour une annotation ; (b) comparer avec la photo peinte en rouge, celle que le modèle a reçue ;
    (c) garder désormais aussi la photo non peinte (…) » → oui : « (a) : pas de comparaison pour une annotation. »
  - Q18 « Espace privé (confidentialité) : la comparaison marche aussi pour les images privées. Elle suit exactement
    les règles des images d'entrée privées d'aujourd'hui : l'image privée est seulement chargée en mémoire de la page,
    rien n'est écrit sur le disque ni dans les journaux ; elle est abandonnée et effacée de l'écran à « Sortir », à la
    fermeture de la page et au retour par « Retour » ; un test d'étanchéité vérifie qu'aucune image « avant » privée
    ne reste affichée ou en mémoire après « Sortir ». La réserve du sous-agent (image privée déjà décodée peut-être
    pas marquée comme abandonnée) serait vérifiée pendant ce travail et corrigée si elle se confirme. » → oui : « Oui,
    comparaison dans l'espace privé avec ces règles, et la réserve vérifiée au passage. »
  - Q19 « Préchargement : dès qu'une image comparable est affichée (carte du dessus de la pile, image courante de la
    visionneuse), sa photo d'entrée complète se charge en avance. Si l'appui arrive avant la fin du chargement, la
    miniature de l'entrée s'affiche dans le cadre, puis l'image complète la remplace. » → oui : « Oui, ce
    préchargement-là. »
- **Troisième tour**, réponse « ok » :
  - Q20 « Où placer le bouton : visionneuse : en bas à droite de l'image, posé dessus en surimpression, à portée de
    pouce. Il suit l'image quand elle est zoomée ou en mode immersif ; carte du dessus de la pile : même bouton, en
    bas à droite de l'image de la carte. Le toucher n'ouvre pas la visionneuse et ne lance pas de balayage. Il
    n'apparaît que sur les images comparables : édition à une seule photo, variantes ou campagne, Dessin avec
    masque. » → oui : « Oui, en bas à droite de l'image, dans la visionneuse et sur la carte du dessus. »
  - Q21 « Comportement du bouton : l'image d'origine apparaît dès l'appui, sans délai (le bouton ne sert qu'à ça) ;
    elle reste tant qu'on maintient le doigt ; au relâché, l'image générée revient, même si le doigt a glissé hors du
    bouton ; l'étiquette « Avant » s'affiche sur l'image pendant l'appui ; un second doigt peut pincer pour zoomer
    pendant l'appui (dans la visionneuse). » → oui : « Oui, ce comportement-là. »
  - Q22 « Au clavier (PC) : maintenir la touche Espace fait la même chose que le bouton (visionneuse ouverte, ou carte
    du dessus de la pile), sauf pendant une saisie de texte. » → oui : « Oui, Espace maintenue. »
- **Zones sensibles**, réponse « ok » :
  - Q23 « Jeter au clavier : (a) ← jette avec le même bandeau Annuler de 5 s qu'au doigt. Ctrl/⌘ + Z (ou la touche Z)
    annule tant que le bandeau est là. Aucun raccourci pour « Supprimer » un tirage ; (b) pas de raccourci pour
    Jeter, seulement → pour Garder ; (c) ← jette après une confirmation. » → oui : « (a) : même filet que le geste du
    doigt, une annulation au clavier, et jamais « Supprimer » au clavier. »
  - Q24 « Règle à ne jamais enfreindre (suppression) : « Aucune touche ne supprime un tirage, et aucune image de la
    pile n'est jetée au clavier sans le bandeau Annuler de 5 s. Une touche maintenue ou répétée ne jette jamais plus
    d'une image avant que la suivante soit affichée. » » → oui : « Oui, cette phrase. »
- **Spec** (`/to-spec`, 27/10/2026), réponses par boutons :
  - « Points de test : aucun changement côté serveur (les images d'entrée sont déjà servies), donc tout se teste par
    le pilote d'interface existant (Chrome sans écran). On lui ajoute seulement deux choses : des vues à la taille
    d'un PC (1280×800, souris) et d'une tablette Android (800×1280 et 1280×800, tactile), et l'appui et le relâché de
    touches du clavier (Espace maintenue, flèches). Ça te va ? » → « Oui (Recommandé) ».
  - « Zoom au doigt : dans la visionneuse, le zoom au pincement revient à la taille normale dès qu'on relâche les
    doigts (comportement actuel). Sur téléphone et tablette, on ne peut donc pas « être zoomé » puis appuyer sur
    Avant. Que faire ? » → « Pincer en tenant Avant (Recommandé) » : « On garde le zoom actuel : en tenant Avant
    d'un doigt, on peut pincer avec deux autres, et la photo d'entrée zoome pareil. Sur PC, molette et glisser
    marchent normalement avec Espace ou le bouton. » (précise Q11 et Q21).
  - « Rendu visuel de la version PC et tablette : maquettes à valider avant de coder, ou directement dans
    l'application avec une planche avant/après montrée à la fin de chaque ticket visuel ? » → « Directement
    (Recommandé) ».
  - « Jeter au clavier (suppression) : aujourd'hui, au doigt, un nouveau Jeter valide tout de suite le Jeter
    précédent, dont l'image est alors supprimée avant la fin de ses 5 s. Au clavier, ← ← ferait pareil. La règle
    acceptée disait « aucune image jetée au clavier sans le bandeau Annuler de 5 s », ce qui ne colle pas à la
    lettre. Que retenir ? » → « Comme au doigt (Recommandé) » : « ← se comporte comme le balayage : le bandeau
    s'affiche, un Jeter suivant valide le précédent. Règle reformulée : « Aucune touche ne supprime un tirage ; au
    clavier, Jeter passe toujours par le bandeau Annuler, comme au doigt ; une touche maintenue ou répétée ne jette
    jamais plus d'une image avant que la suivante soit affichée. » » (remplace la phrase de Q24).
- **Groupe A** (27/10/2026) : planche finale validée (« Je valide ») ; correctif `page.close` du pilote reclassé
  antérieur au lot (« Ca me va ») ; groupe « durcissement » des constats antérieurs après les groupes B et C (« le
  faire apres »).
- **Groupe B, visuel du bouton Avant** (27/10/2026), réponse par bouton : « Le bouton Avant est un nouveau visuel :
  une icône et un libellé courts, aux couleurs de la lumière inactinique (le rouge-orangé de l'app). Comment veux-tu
  valider son apparence ? » → « Planche au retour (Recommandé) » : « La session dessine 2 ou 3 variantes côte à côte
  sur une planche, intègre celle qu'elle juge la meilleure de façon facile à changer, et tu choisis au retour du
  groupe. Le groupe n'est pas bloqué. »
- **Groupe B, espace privé** (27/10/2026, réponses par boutons dans la session du groupe) :
  - « Réserve du cadrage (une image privée déjà décodée n'a pas de drapeau « gone ») : si le test montre qu'une image
    avant privée peut revenir après « Sortir », la fermeture de la page ou « Retour », comment la corriger ? » →
    « Marquer tout à l'oubli (Recommandé) » : « Dans forgetPrivateImages, marquer « gone » toute entrée privée de
    ready (pas seulement celles encore en chargement), avant de la retirer : une image qui l'attendait, même détachée
    de la page, ne reçoit plus rien. Correctif limité à l'oubli. Si le test ne confirme pas la réserve, rien n'est
    changé. » Issue : ni les tests ni la revue de sécurité ne confirment la réserve ; l'oubli n'est pas modifié.
  - « Pendant « Sortir » en attente de la réponse du Mac, que fait le bouton Avant d'une image privée encore affichée
    (carte du dessus ou visionneuse) ? » → « Masqué (Recommandé) » : « Le bouton disparaît dès l'appui sur « Sortir » ;
    l'image d'entrée privée n'est plus demandée. S'il y a refus de la sortie, il revient avec le nouveau dessin de la
    pile ou de la visionneuse. »
- **Visuel du bouton Avant** (28/10/2026), réponse par bouton : « Quel visuel pour le bouton Avant ? » (planche du
  groupe B : a plaque, icône et « Avant » ; b carré, icône seule ; c tampon pixel « Avant ») → « Garder a
  (plaque) » : « Je garde le visuel a (plaque, icône et « Avant ») : retire les variantes b et c du CSS. »
- **Groupe C, touche répétée sur ✓ et ✕** (28/10/2026), réponse par bouton : « Jeter au clavier par un bouton qui a
  le focus : après un clic sur ✕ (ou sur Jeter dans la visionneuse), le bouton garde le focus. Entrée maintenue le
  réactive à chaque répétition du système : une image jetée, puis la suivante dès qu'elle est affichée, et ainsi de
  suite (la pile se vide en passant par le bandeau, chaque Jeter validant le précédent). Espace sur ce bouton fait de
  même au relâché. C'est le comportement d'avant le lot, que la spec ne traite pas. Que faire ? » → « Bloquer la
  répétition (Recommandé) » : « Comme pour ←, une touche répétée par le système (repeat) n'active jamais ✓, ✕, ni
  Garder et Jeter de la visionneuse : Entrée maintenue ne jette qu'une image. Un appui volontaire d'Entrée sur ✕ marche
  toujours. Espace, sur la pile et dans la visionneuse, ne réactive jamais un bouton (ticket 2, preventDefault). »
- **Groupe C, flèches seules et carte visible** (28/10/2026), réponse par bouton : « J'ai restreint quand ← et →
  trient, au-delà de la spec : (1) seulement appuyées seules, sans Ctrl, ⌘, Alt ni Maj (⌘ + ← et Alt + ← sont la page
  précédente du navigateur : sinon elles jetteraient ET quitteraient la page) ; (2) rien quand le focus est dans
  n'importe quel champ (curseur de taille du pinceau compris, où ← → changent la valeur), pas seulement les champs de
  texte ; (3) rien si la carte du dessus n'est pas affichée (pile masquée pendant Dessiner sous 1024 px). Je garde ces
  trois restrictions ? » → « Garder les trois (Recommandé) » : « Les flèches ne trient que seules, hors de tout champ,
  et seulement une carte visible : on ne jette jamais une image qu'on ne voit pas ni en voulant faire autre chose. »
- **Groupe C, Espace sur un bouton qui a le focus** (28/10/2026), réponse par bouton : « Le choix laissé par le groupe
  C : Espace n'active plus aucun bouton qui a le focus (Annuler et Révéler compris). On le garde ? » → « Garder
  (Recommandé) » : « Espace ne sert qu'à comparer avec l'image d'avant ; Annuler et Révéler restent accessibles par
  Entrée, Z ou un clic. »
- **Groupe « durcissement »** (28/10/2026), réponses par bouton :
  - « Le découpage du durcissement (6 tickets, groupes D puis E) te va ? » → « Oui, tel quel (Recommandé) » : « Je
    crée les 6 tickets dans Asana sous la tâche mère, avec leurs blocages, puis je les mets au tableau de bord en deux
    groupes. »
  - « Pour E3, que faire d'une carte dont l'image n'est pas encore à l'écran ? » → « Aucun tri tant qu'elle n'est pas
    affichée (Recommandé) » : « Ni ✓, ni ✕, ni ← → ne la trient tant que son image n'est pas posée. Les 3 s ne servent
    plus qu'aux cartes d'échec. Invariant : aucun geste ne jette une image qui n'est pas affichée. »
  - « Pour E2, pendant « Sortir », une carte privée : » → « Ne bouge pas (Recommandé) » : « ✓, ✕ et les flèches ne
    font rien sur une carte privée pendant « Sortir » : elle reste à l'écran jusqu'à la fin de la sortie, sans tri.
    Invariant : aucune image privée n'est triée ni ne quitte l'écran sans tri. »
- **Groupe D, vignette non chargée et `page.close` dans l'espace privé** (28/10/2026), réponses par bouton dans la
  session du groupe :
  - « Ticket « Pilote : fermer l'onglet, pile.test.mjs indépendant » (zone confidentialité). Le test « pendant
    « Sortir » » de pile.test.mjs suppose une vignette privée des Tirages pas encore chargée. J'ai vérifié pourquoi il
    échoue seul : sa prémisse ne tenait que parce que la page de test était en arrière-plan (onglets laissés ouverts) ;
    au premier plan, Chrome sert la vignette depuis son cache (même adresse que la grille vient d'afficher), elle est
    donc déjà « chargée ». Comment le test doit-il préparer lui-même sa vignette non chargée ? » → « Adresse jamais
    servie (Recommandé) » : « Le test crée son propre tirage privé, puis pose une vignette différée (loading=lazy,
    Tirages cachés) sur la même route privée /api/private/thumb, avec un paramètre en plus (&zq=lazy) que la page n'a
    jamais chargé. La garde vérifiée (« Sortir » retire l'adresse des vignettes privées pas encore chargées) et les
    deux contrôles d'étanchéité (aucune requête privée, aucune adresse privée posée pendant la sortie) restent
    identiques. Essayé : passe seul. Je ferai aussi la preuve rouge (garde neutralisée → le test échoue). » Écartées :
    « Requête retenue », « Cache coupé ».
  - « Ticket 1 (pilote, zone confidentialité), constat de la passe « bogues » : maintenant que page.close ferme
    vraiment l'onglet, la page fermée fait son « pagehide » ; si elle voit l'espace privé ouvert (même cookie que la
    page principale), elle verrouille l'espace sur le Mac. C'est le vrai comportement d'un onglet fermé, et aucun test
    actuel ne ferme une page dans l'espace. Mais un futur test pourrait le faire sans attendre l'espace au repos
    (requêtes privées en route → 403 sous charge), ce que la règle mécanique « privateIdle avant de fermer l'espace »
    ne repère pas. Que faire ? » → « Attente dans page.close (Recommandé) » : « page.close attend lui-même l'espace
    privé au repos (page.privateIdle) avant de fermer un onglet qui est dans l'espace ; la fermeture verrouille
    toujours l'espace, comme un vrai onglet fermé, mais jamais avec une requête privée en route. Commentaire du pilote
    à jour. » Écartées : « Documenter seulement », « Règle mécanique ».
- **Groupe E, durcissement de la pile** (28/10/2026), réponses par bouton dans la session du groupe :
  - « E3 (ne jamais jeter une image non affichée) : une carte de la pile dont seule la miniature (320 px) est posée,
    l'image complète encore en chargement, compte-t-elle comme « affichée » (✓, ✕, ← → et balayage la trient) ? » →
    « Oui, miniature = affichée (Recommandé) » : « C'est ce que l'œil voit déjà sur la carte, et ce que le verrou entre
    deux tris mesure aujourd'hui. Seule une carte sans rien d'affiché (ni miniature ni image) ne se trie pas. »
  - « E3 : une image de la pile que le navigateur n'arrive pas à lire (fichier abîmé, ou effacé par un autre
    appareil : la carte montre son texte mais une image vide/cassée) peut-elle être triée ? » → « Oui, une fois
    l'échec constaté (Recommandé) » : « Quand le chargement est fini et a échoué, la carte (texte, réglages) devient
    triable : ✓, ✕ (toujours avec le bandeau Annuler de 5 s). Sinon une image abîmée bloquerait la pile pour toujours.
    Une image encore en chargement, elle, ne se trie jamais. »
  - « E2 (carte privée immobile pendant « Sortir ») : quels gestes bloquer pendant l'attente de la réponse du Mac ? »
    → « Tout tri, visionneuse comprise (Recommandé) » : « ✓, ✕, ← →, balayage (la carte revient en place) et
    Garder/Jeter de la visionneuse ne font rien sur une image privée : la visionneuse ne passe pas non plus à l'image
    suivante. Une carte d'échec privée reste aussi immobile (rien ne bouge pendant Sortir). »
  - « E2 : une carte privée déjà en train de partir (envol de 0,2 s lancé par ✓ ou ✕) quand on appuie sur
    « Sortir » : aujourd'hui elle quitte l'écran sans être triée. Que faire ? » → « Elle revient sur la pile
    (Recommandé) » : « L'envol s'annule : la carte reprend sa place avec son image, sans tri, et y reste jusqu'à la fin
    de la sortie. Respecte l'invariant « aucune image privée ne quitte l'écran sans tri ». »
  - « E3, image illisible : la passe « bogues » note qu'une coupure réseau passagère (Tailscale qui décroche une
    seconde) ressemble, pour la page, à une image abîmée. Aujourd'hui la carte fait déjà deux essais (chargement à
    part, puis l'image elle-même) ; si les deux échouent, elle devient triable alors que l'image est peut-être saine.
    Que faire ? » → « Garder tel quel (Recommandé) » : « Deux essais suffisent : après leur échec, la carte (texte,
    réglages) se trie, Jeter passe toujours par le bandeau Annuler de 5 s. Rien de plus à coder. »
- **Second groupe « durcissement »** (28/10/2026), réponses par bouton :
  - « Le découpage (6 tickets, groupes F et G) te va ? » → « Oui, tel quel (Recommandé) » : « Je crée les 6 tickets
    dans Asana sous la tâche mère, avec leurs blocages, et je les mets au tableau de bord en deux groupes. »
  - « F3 : pendant que l'image d'avant est affichée (Avant tenu ou Espace), que font ✓, ✕, ← →, le balayage et
    Garder/Jeter de la visionneuse ? » → « Rien (Recommandé) » : « Aucun tri tant que l'image d'avant est à l'écran ;
    il suffit de relâcher pour trier. Invariant : aucun geste ne jette une image qui n'est pas affichée. »
  - « F4 : une carte du dessus remplacée sans tri (nouvelle image, tri sur un autre appareil) : » → « Verrou court
    (Recommandé) » : « Comme entre deux tris : 300 ms après l'affichage de la nouvelle carte, pendant lesquelles ✓, ✕
    et ← → ne font rien. Un ✕ visé sur l'ancienne ne jette pas la nouvelle. »
  - « Dans quel ordre faire les deux groupes ? » → « F puis G (Recommandé) » : « D'abord les défauts visibles (F3
    contredit ton invariant), puis le ménage des tests. »
- **Groupe F, Relancer et Révéler pendant « Sortir »** (28/10/2026), réponse par bouton, question posée par la session
  du groupe : « Groupe F, ticket F2 : pendant « Sortir » (réponse du Mac attendue), que font « Relancer » de la
  visionneuse ouverte sur une image privée et « Révéler » sur une demande privée ? (la session n'a trouvé aucune garde
  sur « Révéler », à confirmer par un test) » → « Rien (Recommandé) » : « Comme la carte d'échec : « Relancer » de la
  visionneuse ne fait rien (elle reste ouverte, sans message), et « Révéler » ne part pas si le test confirme qu'il
  partait (la saisie reste telle quelle, effacée ensuite par la sortie). Aucune demande privée vers une session qui se
  ferme. »
- **Groupe F, aperçus privés détachés** (28/10/2026), réponse par bouton, question posée par la session du groupe :
  « Groupe F, ticket F1 : on vide aussi les aperçus d'une génération privée (/api/job/<id>/preview) qui restent en
  mémoire de la page, détachés, après « Sortir » ? Rien n'en est visible à l'écran : un aperçu arrivé trop tard, et
  celui que montrait la mosaïque de la carte en cours. » → « Oui, étendre F1 (Recommandé) » : « Ces deux cas sont vidés
  aussi (l'aperçu non montré passe par le même outil que les autres images préchargées, et clearReveal vide l'image
  qu'il lâche) ; le test d'étanchéité vérifie aussi les adresses /api/job/ d'une génération privée. Même défaut, même
  outil, risque faible. »
- **Groupe F, passe « bogues » de F2** (28/10/2026), réponses par bouton, questions posées par la session du groupe :
  - « F2, Q1 : un Jeter privé attend la fin de son bandeau quand on appuie sur « Sortir ». Il est abandonné (l'image
    reste sur le Mac). Pendant l'attente de la réponse du Mac, que devient la carte ? » → « Elle revient tout de suite
    (Recommandé) » : « Le Jeter est annulé juste avant que les images privées soient refusées ; la carte revient sur
    la pile avec son image (depuis la mémoire de la page ; dans le cas rare où elle n'y est plus, carte vide jusqu'à la
    réponse). Comme « Annuler » : l'œil voit que rien n'a été jeté. »
  - « F2, Q2 : pendant « Sortir », la visionneuse peut rester ouverte sur une image privée ; Éditer, Dessiner,
    Reprendre et Supprimer y envoient encore des requêtes privées (Supprimer, confirmé, peut supprimer l'image). Que
    faire ? » → « Dans F2 : tout bloqué (Recommandé) » : « Toutes les actions de la visionneuse ne font rien pendant
    « Sortir », comme Relancer (elle reste ouverte, sans message), et Supprimer revérifie « Sortir » après sa
    confirmation. »
  - « F2, Q3 : une génération privée en échec dont la réponse arrive pendant « Sortir » redessine la pile, et les
    cartes restent vides jusqu'à la réponse du Mac. Que faire ? » → « Dans F2 : aucun redessin (Recommandé) » : « La
    pile n'est plus redessinée du tout pendant « Sortir » ; elle l'est au refus ou à la sortie, comme aujourd'hui.
    Couvre ce cas et tout autre chemin du même genre. »
- **Groupe F, image d'avant pendant l'envol** (28/10/2026), réponse par bouton, question posée par la session du
  groupe : « F3 : on appuie sur ← ou ✕ alors que l'image produite est visible, puis on tient Avant (ou Espace) pendant
  l'envol de 0,22 s : la carte qui s'envole montre l'image d'avant, et c'est l'image produite qui est jetée (bandeau
  Annuler de 5 s). La règle « aucun geste ne jette une image qui n'est pas affichée » vaut-elle au moment du geste ou
  jusqu'au départ de la carte ? » → « Au moment du geste (Recommandé) » : « On ne change rien : l'image produite était
  à l'écran quand on a appuyé sur ←, et le bandeau Annuler reste là. Le geste visait une image vue, et le cas tient en
  0,22 s. »
- **Groupe F, portée du verrou court** (28/10/2026), réponse par bouton, question posée par la session du groupe :
  « F4 : le verrou court (0,3 s après l'affichage) s'applique à toute carte qui arrive sur le dessus sans tri sur cet
  appareil, donc aussi l'image remise par « Annuler », une carte d'échec qui arrive en tête et la première carte vue à
  l'ouverture ou au changement d'espace (la pile seulement, pas la visionneuse). On garde cette portée ? » → « Toute
  carte (Recommandé) » : « Toute carte qui arrive sur le dessus doit être vue 0,3 s avant qu'un geste la trie, quelle
  que soit la raison de son arrivée. Sans exception à retenir ; seul coût : un ✕ ignoré dans les 0,3 s qui suivent
  Annuler. »
- **Groupe F, verrou court et page en arrière-plan** (28/10/2026), réponse par bouton, question posée par la session
  du groupe : « F4 : quand l'application est en arrière-plan (autre appli, téléphone verrouillé, autre onglet), les
  0,3 s du verrou s'écoulent quand même : un ✕ tapé dans les 0,3 s qui suivent le retour peut jeter une image arrivée
  entre-temps, jamais vue. La règle (page cachée) fait échouer des tests tant que le pilote laisse parfois la page de
  test « cachée ». Que faire ? » → « Plus tard (Recommandé) » : « F4 part sans cette règle ; la limite et le travail
  sur le pilote vont au compte rendu, pour un durcissement (le groupe G touche déjà le pilote). Il faut un ✕ dans les
  0,3 s qui suivent le retour dans l'appli. »
- **Écarté** : l'appui long sur l'image elle-même (et donc le blocage du menu natif de l'appui long) ; garder la
  photo non peinte d'une annotation ; une marque « ⇆ Avant » distincte du bouton ; un zoom au doigt qui reste après
  le relâché ; des maquettes avant de coder ; un délai de 5 s propre à chaque image jetée.

## 2026-10-26 · Aperçu disparu : 204 au lieu de 404 ; textes des pistes de la rétro acceptés

- **Contexte** : compte rendu de la session des pistes de la rétro (R1 à R22) ; une piste en attente (R3, cause du
  test instable de saisie) et les textes proposés pour `CLAUDE.md` et `docs/agents/session-deleguee.md`.
- **Décision** (porteur, 26/10/2026, réponses à quatre questions) :
  - « R3 · Un aperçu demandé juste avant la fin de sa génération reçoit un 404, que Chrome écrit dans la console
    (cause du test instable de saisie). Que faire ? » → « 204 si l'aperçu n'existe plus (Recommandé) » : pour une
    génération visible dont l'aperçu a disparu (annulée, finie), le Mac répond 204 sans corps ; 404 reste pour une
    génération inconnue, cachée ou oubliée (espace privé inchangé) ; la page abandonne en plus ses aperçus en route à
    « Sortir » ;
  - « Textes proposés pour CLAUDE.md (…) : je les écris tels quels ? » → « Oui, tels quels (Recommandé) » ;
  - « Nouveau texte complet de docs/agents/session-deleguee.md (…) : je remplace le fichier ? » → « Oui, je remplace
    (Recommandé) » ;
  - « La session « Pistes » a fini : je l'arrête et je retire son worktree ? » → « Oui, après R3 (Recommandé) ».
- **Écarté** : corriger seulement côté page ; laisser le 404.

## 2026-10-25 · Pistes de la rétro du parcours de la refonte : avis par ticket, hook de longueur, second contrôle

- **Contexte** : rétro globale du parcours « Refonte UI et pile à trier » ; le porteur a retenu les 22 pistes de ce
  dépôt (R1 à R22) pour une session liée ; quatre choix posés avant son lancement.
- **Décision** (porteur, 25/10/2026, réponses à quatre questions) :
  - « R2 · L'avis « zone sensible » doit compter les lignes ajoutées depuis quand ? » → « Depuis le ticket
    (Recommandé) » : base = le dernier commit plus l'arbre de travail ; remplace la base « départ de la branche » du
    24/10 ;
  - « R14 · Ajouter au dépôt (public) un hook Claude Code qui lance check.py --lines après chaque Edit ou Write ? » →
    « Oui, dans .claude/settings.json (Recommandé) » ;
  - « R12 · Quand check.py voit un arbre identique à un contrôle complet déjà vert, il ne relance pas. La règle
    « deux contrôles complets par ticket » devient « le second seulement si l'arbre a changé » ? » → « Oui
    (Recommandé) » ;
  - « Textes soumis à ton accord : CLAUDE.md (R2, R5, R17, R20) n'est pas écrivable depuis un worktree, et
    CODING_STANDARDS.md (R16) change des règles de revue. Comment faire ? » → « Session écrit CODING_STANDARDS,
    propose CLAUDE.md (Recommandé) » : la session écrit les deux règles de R16 et met le texte proposé pour CLAUDE.md
    dans son compte rendu ; la discussion principale l'écrit après l'accord du porteur.
- **Écarté** : garder la base « départ de la branche » ; corriger les lignes sans hook ; toujours deux contrôles
  complets ; proposer aussi CODING_STANDARDS.md avant de l'écrire.

## 2026-10-25 · Constats de la revue de sécurité du groupe G

- **Contexte** : revue de sécurité du groupe G (lecture seule, `git diff 64d7a92..29a3a00`) : aucune faille critique
  ni haute ; constats posés au porteur avec une recommandation chacun.
- **Décision** (porteur, 25/10/2026, réponse « ok pour tes reco ») : « Trancher les constats de la revue de sécurité
  du groupe G. Elle n'a trouvé aucune faille critique ni haute, donc livrer sans les corriger reste défendable. Je
  n'ai rien corrigé : Moyenne : comme le cookie d'accès, le cookie de session de l'espace privé part aussi vers les
  autres ports de 127.0.0.1. Un autre compte du Mac qui y attirerait ton navigateur pendant que ton espace privé est
  ouvert pourrait s'en servir. Le texte du risque accepté ne parle que du cookie d'accès. ➡️ Je propose d'élargir ce
  texte dans le README et `DECISIONS.md` ; je l'écris sur ton oui. Faible : un refus 401 au moment de reverrouiller
  laisse la session privée ouverte jusqu'à 15 minutes. ➡️ Je recommande de corriger avant l'envoi : le verrouillage
  passerait sans cookie d'accès, toujours derrière le contrôle anti-autre-site. C'est un petit changement du serveur,
  avec un test et une passe « bogues ». Faible : si le service est arrêté, un autre compte qui prend le port 7860
  pourrait montrer une fausse page du code au raccourci. ➡️ Piste. Faible : un cookie posé par un autre port peut
  bloquer le Mac, sans fuite. ➡️ Piste. » → les quatre recommandations : risque accepté élargi au cookie de session
  privée (README) ; `POST /api/private/lock` admis sans cookie d'accès, après `_host_ok` et `_post_refused` ; les deux
  derniers constats restent des pistes (`ETAT_DU_PROJET.md`).
- **Écarté pour l'instant** : vérifier le propriétaire du port avant `--enter` ; accepter l'une quelconque des valeurs
  `qwen_access` présentes ; porter la session privée par un en-tête plutôt qu'un cookie.

## 2026-10-25 · Choix retenus par Claude pour l'entrée du Mac par jeton (délégation du porteur)

- **Contexte** : ticket G2 « Entrer depuis le Mac sans taper le code, par un jeton à usage unique », sa revue
  Standards/Spec et sa passe « bogues » ; choix faits par Claude sous la délégation du porteur (« Choix confiés à
  Claude jusqu'à la fin du parcours de la refonte », plus bas).
- **Choix retenus** (question → recommandation retenue) :
  - Réponse à une entrée refusée (Wi-Fi, relais, jeton mauvais, vieux ou déjà servi) ? → la page du code, pas un
    simple 403 ; un navigateur qui a déjà le cookie est renvoyé vers `/` sans toucher au jeton (historique,
    autocomplétion, second onglet) ;
  - Jeton de plus de 60 s ? → effacé quel que soit le jeton présenté, âge pris sur le fichier ouvert et en valeur
    absolue (un fichier daté dans le futur est refusé) ;
  - Deux requêtes simultanées ? → un verrou (`ENTRY_LOCK`) entoure l'écriture, la lecture, la vérification et
    l'effacement dans un même processus ; un jeton servi est retenu en mémoire (`ENTRY_USED`) et refusé ensuite, même
    si son fichier n'a pas pu être effacé ;
  - Fichiers du jeton et de la page ? → créés de façon exclusive en 0o600 sous un nom tiré au hasard, puis remplacés
    d'un coup ; ignorés par git, temporaires compris ;
  - Ce que reçoit le navigateur ? → l'adresse `file://` de la page de redirection, jamais l'adresse qui porte le
    jeton ; limite écrite dans le README : un ordinateur qui ouvre les `.html` dans un éditeur n'affiche aucun
    navigateur, recours par l'adresse et le code ;
  - Entrée impossible à écrire, ou `--enter` qui échoue ? → le lancement ouvre l'adresse simple (le code est alors
    demandé), le raccourci macOS aussi (`--enter || open http://127.0.0.1:7860/`) ;
  - Raccourci ? → `tools/make_shortcut.py` découpé en fonctions pour être testé ; le README dit de le relancer après
    une mise à jour (consigne pour tout utilisateur du dépôt).
- **Écarté** : donner au navigateur l'adresse qui porte le jeton ; laisser un navigateur déjà connecté sur la page du
  code ; laisser le porteur sans navigateur ouvert quand l'entrée échoue.

## 2026-10-25 · Choix retenus par Claude pour le code d'accès demandé au Mac (délégation du porteur)

- **Contexte** : ticket G1 « Demander le code d'accès sur le Mac aussi », sa revue Standards/Spec et sa passe
  « bogues » ; choix faits par Claude sous la délégation du porteur (« Choix confiés à Claude jusqu'à la fin du
  parcours de la refonte », plus bas).
- **Choix retenus** (question → recommandation retenue) :
  - Où la page du code dit-elle comment entrer depuis l'ordinateur ? → seulement pour une requête de l'ordinateur
    lui-même, en plus du paragraphe du téléphone : « Sur cet ordinateur : ouvrez Chambre noire par son raccourci, ou
    saisissez le code de `tools/access_code.txt`. » (« cet ordinateur » plutôt que « ce Mac » : juste sous Windows) ;
  - « Ouvrir depuis le téléphone » sans `--lan` ? → masqué (le champ `phone` de `/api/status` suit les adresses du
    Wi-Fi, sinon il montrerait une adresse vide) ;
  - Une requête quand aucun code n'est chargé ? → refusée partout (401), Wi-Fi compris ;
  - Au lancement sans `--lan` ? → le terminal dit où est le code (`tools/access_code.txt`), jamais le code ;
  - Fichier du code illisible (encodage, droits, dossier à sa place) ? → le lancement s'arrête avec un message qui
    dit quoi faire, sans jamais écraser le fichier ; un fichier lisible mais trop court est remplacé comme avant ;
  - Droits et création du fichier du code ? → resserrés à 0o600 à chaque lecture ; création exclusive, et un code
    créé entre-temps par un autre lancement est relu, pas écrasé ;
  - Lecture des cookies ? → par le serveur lui-même, tolérante aux paires mal formées d'autres applications locales
    (les cookies ne distinguent pas les ports), comparaison en octets sans jamais lever ;
  - Le cookie d'accès du Mac part aussi vers les autres ports de 127.0.0.1 ? → risque accepté et écrit dans le README
    (élargi le 25/10/2026 au cookie de session privée, entrée « Constats de la revue de sécurité du groupe G ») :
    il faut qu'un autre compte écoute sur un port local et y attire le navigateur du porteur ; pas de correction simple
    ;
  - Un onglet ouvert sans cookie valable (avant la mise en service, cookies effacés, code changé) ? → un 401 de
    `/api/status` recharge la page une fois, sur la page du code, sans boucle ;
  - Un 401 au reverrouillage de l'espace privé vaut-il « verrouillé » (décision du 24/10, « une erreur de la famille
    4xx (comme « accès refusé ») ») ? → non, c'est l'exception : depuis que le Mac demande le code d'accès, un 401 veut
    dire que la requête n'a pas atteint la session privée, qui peut rester ouverte ; la marque de l'onglet est gardée
    et l'espace reverrouillé une fois le code d'accès saisi. Les autres 4xx et le 503 « indisponible » restent des
    verrouillages ;
  - Tests d'interface ? → connectés à un seul endroit du pilote (`driver.mjs`) pour les bancs directs ; un banc relayé
    garde `bench.login(page)` ; le banc pose son propre code sans passer par `setup_access`.
- **Écarté** : écraser un fichier de code illisible ; prendre un 401 pour un verrouillage accepté ; laisser un onglet
  bloqué sur « Moteur indisponible ».

## 2026-10-24 · Choix retenus par Claude pour les suites du groupe E (délégation du porteur)

- **Contexte** : correctifs des suites du groupe E après la revue Standards/Spec et deux passes « bogues » ; choix
  faits par Claude, une partie avant la délégation (déclarés au tableau de bord), le reste sous la délégation du
  porteur (« Choix confiés à Claude jusqu'à la fin du parcours de la refonte », ci-dessous).
- **Choix retenus** (question → recommandation retenue) :
  - Une sortie de l'espace privé refusée par le Mac laisse-t-elle la pile privée telle quelle ? → non : elle est
    relue (sinon un « Sortir » appuyé avant la première lecture, puis refusé, la laissait vide) ;
  - Nom de la marque de l'onglet ? → `relock`, valeur `1`, sans aucune donnée privée ;
  - Qu'est-ce qu'une « saisie en cours » qu'une notification ne ferme pas ? → un champ de texte de la feuille où
    l'utilisateur a tapé (frappe, collage, dictée) depuis son ouverture ; un interrupteur ou un champ rempli par la
    page ne compte pas ;
  - Une fermeture de la page hors de l'espace oublie-t-elle la saisie privée mise de côté après une fermeture par le
    Mac ? → oui, comme au retour, plus tôt ;
  - Une fermeture de la page pendant l'envoi du code privé ? → traitée comme une fermeture dans l'espace : envoi du
    code annulé, verrouillage, marque, saisie privée oubliée, message au retour ; une page revenue avant la réponse
    refuse l'entrée (« Page fermée pendant l'envoi : retapez le code. ») ;
  - Une page fermée pendant le reverrouillage qui précède l'envoi du code ? → le code ne part pas, à retaper ;
  - « Sortir » refusé clairement par le Mac (4xx, 503 « espace privé indisponible ») ? → sortie appliquée, même règle
    que le reverrouillage ;
  - Une page marquée dont l'état n'a pas pu être relu ? → traitée à sa fermeture comme peut-être dans l'espace
    (verrouillage, marque) ;
  - Après un rechargement marqué dont le verrouillage échoue, la ligne « Espace privé » reste-t-elle visible ? → non :
    elle n'apparaît qu'une fois le verrouillage accepté (aucun état appliqué avant), comportement écrit dans le
    README ;
  - Regrouper les gardes de « Sortir » en une seule porte sur les adresses privées ? → pas dans ce parcours : piste
    notée.
- **Écarté** : rentrer dans l'espace sur une réponse arrivée après une fermeture ; appliquer une partie de l'état
  avant le reverrouillage accepté.

## 2026-10-24 · Choix confiés à Claude jusqu'à la fin du parcours de la refonte

- **Contexte** : suites du groupe E en cours, groupe G (code d'accès demandé aussi sur le Mac) restant ; chaque choix
  de confidentialité ou de conception était jusqu'ici posé au porteur.
- **Décision** (porteur, 24/10/2026) : « Continu de maniere autonome, tu choisi tes propres recommandations jusqu'a la
  fin de tout les tickets du parcours. » Jusqu'à la fin des tickets du parcours « Refonte UI et pile à trier »,
  Claude retient sa propre recommandation à chaque choix, zones sensibles comprises, l'écrit ici (question et
  recommandation retenue) et la déclare au tableau de bord. La délégation vaut dans la discussion principale où elle
  a été donnée : le groupe G s'y fait donc, pas dans une session liée (une session liée ne peut pas tenir un accord
  du porteur d'un message d'une autre session). Restent au porteur : pousser, ouvrir la pull request, fusionner vers
  `main`, le compte rendu du parcours et la livraison.
- **Écarté** : lancer G en session liée, qui buterait sur chaque choix à faire confirmer par le porteur.

## 2026-10-24 · Marque de l'onglet posée dès l'entrée dans l'espace, refus clair du verrouillage

_Précisée le 25/10/2026 (un 401 n'est pas un verrouillage depuis que le Mac demande le code d'accès) par « Choix
retenus par Claude pour le code d'accès demandé au Mac »._

- **Contexte** : revue Standards/Spec et passe « bogues » des suites du groupe E ; deux constats touchant l'espace
  privé posés au porteur avec une recommandation chacun.
- **Décision** (porteur, 24/10/2026, réponse « ok pour tes reco ») :
  - « La marque qui fait reverrouiller l'espace au chargement suivant n'est posée qu'au moment où la page se ferme
    (`pagehide`). Or un téléphone ferme souvent une application restée en arrière-plan sans prévenir la page. Dans ce
    cas, ni la marque ni le verrouillage ne partent, et l'onglet rechargé rentre dans l'espace sans code s'il le fait
    dans les 15 minutes. Chrome sur Android le fait par exemple pour libérer de la mémoire. A) (Recommandé) Poser la
    marque dès l'entrée dans l'espace, et la retirer quand tu sors ou quand le Mac accepte le verrouillage. Ça couvre
    aussi l'onglet fermé sans prévenir. Le coût est de même nature que ce que tu as déjà accepté : la marque, toujours
    sans donnée privée, est présente pendant tout le temps passé dans l'espace, pas seulement après la fermeture.
    B) La poser aussi quand l'application passe en arrière-plan (changement d'application, écran verrouillé), tant
    que tu es dans l'espace. Ça couvre presque les mêmes cas, avec une marque posée un peu plus tard. C) Garder la
    marque seulement à la fermeture, comme aujourd'hui. » → A ;
  - « Refus durable du verrouillage. Aujourd'hui, toute réponse du Mac qui n'est pas un « oui » vaut « pas encore » :
    la page réessaie et n'affiche rien. Comme la marque survit au rechargement, un refus qui dure bloque l'onglet
    (lampe rouge, rien d'affiché) jusqu'à sa fermeture. Le cas le plus probable est un serveur relancé sans le module
    de chiffrement : il répond « espace privé indisponible ». A) (Recommandé) Prendre comme « verrouillé » un refus
    clair venant du Mac lui-même : une erreur de la famille 4xx (comme « accès refusé »), ou « espace privé
    indisponible ». Dans les deux cas, l'espace ne peut de toute façon pas être ouvert. Continuer de réessayer sur
    une coupure réseau ou une panne sans réponse claire, par exemple celle du relais Tailscale, pour ne jamais
    rentrer dans une session peut-être encore ouverte. B) Garder le blocage tel quel. » → A.
- **Écarté** : la marque posée seulement à la fermeture ou au passage en arrière-plan ; un onglet bloqué par un refus
  durable ; toute réponse HTTP prise pour un verrouillage accepté.
- **Limite connue** : une application tuée puis relancée depuis l'écran d'accueil repart sans marque (mémoire de
  l'onglet vide) ; seule la fermeture de l'espace par le Mac au bout de 15 minutes protège ce cas, comme avant.

## 2026-10-24 · Suites du groupe E : verrouillage à la fermeture, lampe sans animation, notification et feuilles

- **Contexte** : compte rendu du groupe E (questions de confidentialité et d'ergonomie laissées ouvertes par sa
  session) ; questions posées au porteur avec une recommandation chacune.
- **Décision** (porteur, 24/10/2026, réponse « ok pour tes reco ») :
  - « Rechargement normal après un verrouillage perdu. Si le verrouillage envoyé à la fermeture n'arrive pas au Mac
    (réseau coupé), une page rechargée ou rouverte normalement dans les 15 minutes rentre encore dans l'espace sans
    code. Ce défaut existait avant le groupe E. A) Reverrouiller à tout chargement qui suit une fermeture dans
    l'espace. La page laisse une marque « cet onglet était dans l'espace privé » dans la mémoire de l'onglet du
    navigateur (`sessionStorage`, effacée à la fermeture de l'onglet, sans aucune donnée privée). Coût : quelqu'un qui
    ouvre les outils de développement du navigateur pourrait voir que l'espace a servi. B) Reverrouiller à chaque
    chargement, sans aucune marque. Coût : ouvrir l'application dans un deuxième onglet fait sortir le premier de
    l'espace privé. C) Laisser comme aujourd'hui. Je penche pour A : le cas B est plus gênant au quotidien, et la
    marque ne dit rien de ce qu'il y a dans l'espace. » → A ;
  - « Champ de code restauré. Une feuille privée restée ouverte à la fermeture revient par « Retour » avec son champ
    de code rempli. Je recommande de vider ces champs au retour. » → oui ;
  - « Course au reverrouillage. Si un verrouillage est encore en route quand tu retapes le code privé, il arrive après
    et referme l'espace que tu viens d'ouvrir. Il n'y a pas de fuite, mais l'espace paraît se refermer seul. Je
    recommande que l'entrée attende la fin du verrouillage. » → oui ;
  - « Effacer dès la fermeture plutôt qu'au retour. Tant que le navigateur garde la page en mémoire pour un éventuel
    « Retour », il garde aussi les images privées déchiffrées et la saisie. Effacer dès `pagehide` (l'événement de
    fermeture de la page), en gardant l'effacement au retour, change ta décision du 23/10 (« au retour »). Je
    recommande oui. » → oui : la décision du 23/10 est complétée (effacement à la fermeture, et encore au retour) ;
  - « Avec « réduire les animations » activé sur le téléphone, la lampe ne pulse plus : « Calcul en cours » et
    « Prêt » ont alors la même couleur. Je recommande un aspect fixe différent pendant le calcul (par exemple un
    anneau au lieu d'un point plein). » → oui ;
  - « Toucher une notification ferme n'importe quelle feuille ouverte, y compris une modification de prompt pas
    encore enregistrée. Je recommande de passer au Labo sans fermer une feuille qui a une saisie en cours. » → oui ;
  - « Elle a rendu son compte rendu mais apparaît encore dans la liste des sessions. Est-ce que je l'arrête et
    supprime son worktree ? Sa branche est fusionnée, rien ne serait perdu. » → oui.
  Faites dans la discussion principale, sur `dev`, avant le groupe G, avec une passe « bogues » (espace privé).
- **Écarté** : reverrouiller à chaque chargement sans marque (un deuxième onglet ferait sortir le premier) ; laisser
  le rechargement rentrer sans code ; effacer seulement au retour ; la même lampe pour « Prêt » et « Calcul » quand
  les animations sont réduites ; une notification qui ferme une saisie en cours.

## 2026-10-24 · Page restaurée par « Retour » : saisie privée effacée, espace reverrouillé

- **Contexte** : ticket « Trier dans l'espace privé en lumière verte » du groupe E (page restaurée depuis la mémoire
  du navigateur après le verrouillage, spec section 12, ajout du 23/10/2026) ; deux choix touchant la confidentialité
  posés au porteur dans la session du groupe.
- **Décision** (porteur, 24/10/2026) :
  - « Ticket E3, page restaurée par « Retour » après la fermeture de la page dans l'espace privé. À la fermeture, la
    page a verrouillé l'espace. Au retour, l'affichage privé est effacé tout de suite (c'est ta décision du 23/10).
    Que devient le texte et les images que tu avais tapés dans l'espace privé ? » Options : « Effacés, comme Sortir
    (Recommandé) : Fermer la page vaut « Sortir » : la saisie privée est effacée de la page. Un message dit « Espace
    privé verrouillé à la fermeture de la page ». Rien de privé ne reste en mémoire. » ; « Gardés en mémoire : Comme
    la fermeture par le Mac après 15 minutes : la saisie privée reste en mémoire de la page (jamais dans le
    navigateur), et revient si tu rentres dans l'espace depuis cette même page. » → « Effacés, comme Sortir
    (Recommandé) » ;
  - « Même cas. Le verrouillage envoyé à la fermeture de la page peut ne pas arriver au Mac (réseau coupé à ce
    moment-là). Au retour, la page redemande l'état au Mac : s'il dit l'espace encore ouvert, la page y rentrerait et
    réafficherait tout le privé. On fait quoi ? » Options : « Reverrouiller au retour (Recommandé) : Au retour, la
    page renvoie d'abord « verrouiller » au Mac, puis redemande l'état : l'espace reste fermé, il faut retaper le
    code privé. C'est ce que promet le README (« se verrouille à la fermeture de l'application »). » ; « Suivre le
    Mac : La page redemande seulement l'état : si le verrouillage n'est pas arrivé, elle rentre dans l'espace privé
    sans code. » → « Reverrouiller au retour (Recommandé) ».
- **Écarté** : garder la saisie privée en mémoire après la fermeture de la page ; rentrer dans l'espace au retour si
  le verrouillage de la fermeture n'est pas arrivé.

## 2026-10-24 · Cadrage réécrit pour le Labo et les Tirages, état vide des Tirages avec le logo

- **Contexte** : avant de lancer le groupe E, deux points qui demandaient le porteur : le texte de `BRIEF.md`
  (spec, section 13) et l'illustration de l'état vide des Tirages (spec, section 11), nouveau visuel.
- **Décision** (porteur, 24/10/2026, réponse « 1 oui, 2 a ») :
  - « Texte de `BRIEF.md` (ton accord est requis). Il parle encore des pages Créer, En cours et Galerie. Je
    l'écrirais moi-même ici, avant le lancement, pour que la session n'ait pas à t'attendre. » (changements proposés,
    écrits tels quels dans `BRIEF.md` : nom « Chambre noire », Labo, révélation en pixels, pile à trier, Tirages,
    espace privé en lumière verte avec l'entrée dans la feuille de la lampe ; ligne de l'accès par téléphone laissée
    au groupe G) → oui ;
  - « Illustration de l'état vide des Tirages (ticket 2). La spec demande « une illustration en pixels » au-dessus de
    « Aucun tirage pour l'instant ». C'est un nouveau visuel, et tu valides d'habitude un visuel avant qu'il soit
    intégré. a) (Recommandé) Reprendre le logo, le paysage en carrés que tu as déjà validé (`logo.svg`), agrandi et
    atténué. Aucun nouveau dessin, donc rien à valider, et la session ne s'arrête pas. b) La session dessine une
    illustration nouvelle et s'arrête pour te montrer ses rendus avant de l'intégrer. » → a.
- **Écarté** : un nouveau dessin pour l'état vide ; `BRIEF.md` laissé au groupe E.

## 2026-10-24 · Avis « zone sensible » limité au travail de la branche, notification qui ramène au Labo

- **Contexte** : ticket d'outillage fait sur `dev` (`237c7d6`) ; texte de `CLAUDE.md` (section « Vérifications ») et
  point du groupe E restés en suspens soumis au porteur.
- **Décision** (porteur, 24/10/2026, réponse « 1 oui, 2 oui ») :
  - « Texte de `CLAUDE.md` (section Vérifications) à remplacer. Ce paragraphe remplace celui qui commence par
    « `--quick` (en local, jamais en CI)… » » (paragraphe proposé, écrit tel quel dans `CLAUDE.md`) « Deux points à
    valider en connaissance de cause : La CI GitHub n'affichera plus jamais cet avis. La phrase « C'est un indice… »
    étend à tous les groupes la règle que tu as fixée pour E et G seulement : la passe « bogues » ne tourne que sur
    les tickets jugés sensibles au découpage. » → oui ;
  - « Notifications (ticket E1, groupe E). Toucher une notification devrait-il ramener au Labo même quand
    l'application est déjà ouverte ? Aujourd'hui, le fichier qui reçoit les notifications (`sw.js`) n'ouvre le Labo
    que si l'application est fermée. ➡️ Je recommande oui : je l'ajoute à E1 par un commentaire « mise à jour du
    porteur ». » → oui ; commentaire ajouté au ticket E1.
- **Écarté** : un avis « zone sensible » en CI ; une passe « bogues » décidée par l'avis plutôt qu'au découpage.

## 2026-10-24 · Suites du groupe D : deux cas de Jeter, méthode des groupes E et G

- **Contexte** : compte rendu du groupe D (revue de sécurité : deux constats sur Jeter) et enquête sur sa durée
  (≈ 6 h, dont 46 % d'attente des revues et 29 % de contrôles) ; questions posées au porteur avec une recommandation.
- **Décision** (porteur, 24/10/2026, réponse « ok pour tes reco ») :
  - « Double appui sur « Jeter » dans la visionneuse. Le second appui tombe sur l'image suivante et envoie tout de
    suite la suppression de la première, sans ses 5 s d'« Annuler ». Même risque sur ✓ et ✕ de la pile, entre 220 et
    300 ms. On bloque le bouton jusqu'à ce que l'image suivante soit affichée (300 ms au moins) ? » → oui ;
  - « Jeter privé pendant « Sortir ». Si tu sors de l'espace privé pendant les 5 s d'« Annuler », la suppression peut
    partir quand même. On l'abandonne dès le début de la sortie ? L'image resterait alors dans la pile privée, selon
    ton principe « le doute garde l'image ». » → oui ; les deux corrections faites dans la discussion principale, sur
    `dev`, avant le groupe E ;
  - « Passe « bogues » seulement sur les tickets sensibles par leur contenu (espace privé, suppression, contrôle
    d'accès) : E3, G1, G2, mais pas E1 ni E2. Et l'avis de `check.py` comparé à la base de la branche du groupe, pas
    à `main`. D'accord ? » → oui ;
  - « Corriger les constats Standards/Spec pendant que la passe « bogues » tourne, au lieu de l'attendre sans rien
    faire. Rien ne change dans les règles : le commit reste après les deux revues. D'accord ? » → oui ;
  - « Aller plus loin : commiter avant la revue et commencer le ticket suivant pendant qu'elle tourne, les correctifs
    arrivant dans un commit à part. Gain d'environ une heure de plus, mais c'est contraire à ta règle « un commit par
    ticket, après sa revue ». » → recommandation « Non, on garde la règle » acceptée ;
  - « Un petit ticket d'outillage fait ici, sur `dev`, avant de lancer E. `check.py --ui` lancerait les fichiers
    d'interface sur 2 ou 3 Chrome en parallèle : environ 40 % de temps en moins par contrôle complet, selon
    l'estimation de l'enquête. L'avis « zone sensible » serait comparé à la base de la branche du groupe. D'accord ? »
    → oui ;
  - « Est-ce que j'arrête les sessions A, B, C et F et que je supprime leurs worktrees ? Leurs branches sont
    fusionnées, rien ne serait perdu, et la liste de tes sessions serait plus lisible. » (et D, ajouté ensuite) →
    oui.
- **Écarté** : passe « bogues » sur tout ticket où `check.py` affiche l'avis ; attendre la passe « bogues » sans rien
  faire ; commit avant la revue ; garder les sessions terminées.

## 2026-10-24 · Code d'accès demandé aussi au Mac, entrée par un jeton à usage unique

- **Contexte** : le porteur a répondu « b » à la question reposée sur l'accès local (entrée du 23/10 ci-dessous) : le
  Mac demandera lui aussi le code d'accès. Trois choix de mise en œuvre lui ont été posés.
- **Décision** (porteur, 24/10/2026, réponse « ok pour tes reco ») :
  - « Un code même sans l'option Wi-Fi (`--lan`) ? Aujourd'hui, sans `--lan`, il n'y a aucun code, et le serveur
    n'écoute que l'adresse `127.0.0.1`. Mais les autres comptes du Mac y ont justement accès. » → recommandation
    acceptée : un code toujours, créé au premier lancement dans `tools/access_code.txt` ;
  - « Comment tu entres depuis le Mac ? (a) Sans rien taper. Le raccourci `Chambre noire.command` (et l'ouverture
    automatique du navigateur au lancement) ouvre une adresse de connexion à usage unique : un jeton valable une
    minute, utilisable une seule fois, jamais le code lui-même. Il ne sert donc à rien s'il reste dans l'historique du
    navigateur. Seul ton compte peut le créer, puisqu'il faut lire un fichier qui t'est réservé. Ensuite, le navigateur
    garde la connexion un an, comme sur le téléphone. (b) Taper le code, lu dans `tools/access_code.txt`, une fois par
    navigateur. » → « (a) » ;
  - « Quand le faire ? Il faut adapter le banc et une bonne part des tests d'interface, que le groupe D est en train de
    réécrire, et la page du code d'accès, que le groupe E modifie aussi. (a) Un groupe G à part, après le groupe E, en
    session liée (effort high), avec une revue de sécurité obligatoire. Je rédige d'abord la section de la spec et je
    te propose le ou les tickets. (b) Tout de suite, en parallèle du groupe D, au prix de conflits dans les tests. » →
    « (a) ».
- **Écarté** : garder le Mac sans code ; un code seulement avec `--lan` ; taper le code sur le Mac ; le faire en
  parallèle du groupe D.
- **Conséquences** : spec, section 14 ; groupe G après le groupe E.

## 2026-10-23 · Journal du service et dossiers d'avant fermés aux autres comptes, accès local sans code noté

- **Contexte** : passe « bogues » du ticket des droits des fichiers (`41dab97`) ; trois traces antérieures à la refonte
  qui concernent un autre compte du Mac.
- **Décision** (porteur, 23/10/2026, réponse « ok pour tes reco ») :
  - « Journal du service (`logs/service.log`). Il est créé par le système de lancement de macOS, avant le serveur,
    donc sans le masque : il est lisible par les autres comptes. Il contient le nom réseau du Mac et ses adresses
    Tailscale, mais aucun prompt. On ajoute le masque dans la définition du service (`make_service.py`) ? Il faudrait
    réinstaller le service. » → oui ;
  - « Dossiers déjà créés. `outputs/`, `jobs/` et `logs/` restent lisibles par les autres comptes : ils peuvent y
    lister les noms des images, et voir apparaître les dossiers `jobs/private_<id>`, donc quand tu génères en privé. Ils
    ne peuvent pas ouvrir les fichiers. On ferme une fois ces dossiers au lancement du serveur ? » → oui ;
  - « Accès par l'adresse locale du Mac. Le Mac lui-même n'a pas besoin du code d'accès. Un autre compte du Mac peut
    donc lire l'espace public par l'interface : prompts, tirages, images d'entrée. L'espace privé, lui, demande
    toujours son code. (a) Le noter dans la doc comme limite connue : ton Mac est mono-compte. (b) Demander le code
    d'accès aussi depuis le Mac. Ce serait plus contraignant pour toi. » → recommandation (a) acceptée.
- **Écarté** : laisser le journal du service et les dossiers d'avant lisibles ; demander le code d'accès sur le Mac.
- **Conséquences** : le service porte `Umask` 63 (0o077) et se réinstalle par `tools/make_service.py` ; au lancement,
  le serveur ferme ses dossiers (0o700) ; l'accès local sans code reste une limite écrite dans le README.
- **Réserve** : la question sur l'accès local sous-estimait l'exposition (relevé de la passe « bogues ») : un autre
  compte du Mac peut aussi lire le code d'accès du téléphone, lancer des générations, jeter ou supprimer des images et
  modifier les prompts enregistrés. Question reposée au porteur avec l'exposition réelle ; le README la décrit déjà.
- **Remplacée en partie le 24/10/2026** (accès local) : question reposée, « Y a-t-il, ou y aura-t-il, d'autres comptes
  que le tien sur ce Mac ? (a) Non, il est à moi seul. On garde l'accès sans code depuis le Mac, et la limite reste
  écrite. (b) Oui. Le Mac demanderait lui aussi le code d'accès, une seule fois par navigateur. Le code est dans
  `tools/access_code.txt`, que les autres comptes ne peuvent pas lire. Un autre compte devrait alors le connaître
  pour entrer. » → « b ». La mise en œuvre (code sans `--lan`, entrée du Mac) est à cadrer avec le porteur.

## 2026-10-23 · PNG renommé avant l'effacement, fichiers du serveur pour le seul porteur

- **Contexte** : passe « bogues » du durcissement de la pile (`e1f05d9`).
- **Décision** (porteur, 23/10/2026, réponse « ok pour tes reco ») :
  - « PNG verrouillé sous Windows. Windows refuse d'effacer un fichier ouvert, par exemple pendant le calcul de sa
    vignette. Le PNG étant effacé en dernier, il peut rester seul : le reste est déjà parti, y compris le prompt.
    Garder une telle image en ferait un tirage sans prompt. Sur le Mac, le cas n'arrive pas. (a) Renommer d'abord le
    PNG en nom caché : sous Windows, ce renommage échoue aussi sur un fichier ouvert, donc tout de suite, avant
    d'avoir rien effacé. Ensuite, tout effacer, et remettre le nom d'origine si une pièce résiste. (b) Laisser
    ainsi : la seule plateforme concernée n'est pas la tienne, et l'image se rejette. » → recommandation (a) acceptée ;
  - « Fichiers de travail lisibles par les autres comptes du Mac. Pendant le calcul d'une image privée, sd-cli écrit
    le PNG en clair dans `jobs/private_<id>/`, et ce PNG contient le prompt dans ses métadonnées. Le dossier et le
    fichier sont lisibles par les autres comptes du Mac jusqu'à la fin de la génération. Les vignettes, les copies
    d'images d'entrée et les anciens tirages le sont aussi. Ça existait avant la refonte. (a) Créer tout ce que le
    serveur et sd-cli écrivent en lecture pour ton seul compte (masque de création 0o077 au lancement du serveur),
    dans un petit ticket à part. (b) Laisser ainsi : ton Mac n'a sans doute qu'un compte. » → recommandation (a)
    acceptée.
- **Écarté** : laisser le PNG seul sous Windows ; garder les droits de création du système.
- **Conséquences** : un PNG caché resté après une panne reprend son nom au démarrage (l'image revient, on la rejette) ;
  les fichiers déjà créés gardent leurs droits, seuls les nouveaux sont pour le seul porteur.

## 2026-10-23 · Suites du groupe B : effacement PNG en dernier, annulation privée, droits des fichiers, page restaurée

_Complétée le 24/10/2026 (page restaurée) par « Suites du groupe E : verrouillage à la fermeture, lampe sans
animation, notification et feuilles » : l'affichage privé est aussi effacé dès la fermeture de la page (`pagehide`)._

- **Contexte** : compte rendu du groupe B (pile côté serveur) et passe « bogues » du ticket des couleurs ; questions
  posées au porteur avec une recommandation chacune.
- **Décision** (porteur, 23/10/2026, réponse « ok pour tes reco ») :
  - « Page restaurée par « Retour ». Une page restaurée depuis la mémoire du navigateur après le verrouillage réaffiche
    le contenu privé quelques secondes. On confie la correction au ticket « Trier dans l'espace privé en lumière
    verte » du groupe E ? » → oui ;
  - « Suppression privée durcie par la revue du groupe B. `/api/private/delete` reprend d'abord un éventuel changement
    de code interrompu, puis renomme le dossier avant de l'effacer. C'est ce qu'exige déjà le piège « Verrous » de
    `CLAUDE.md`. Le relecteur a voulu défaire ce changement, mais le contrôle de permissions l'a bloqué comme un
    affaiblissement de la sécurité. On garde ? » → oui ;
  - « Ordre d'effacement de Jeter et Supprimer. Aujourd'hui, le PNG est effacé d'abord, comme le dit la spec. Si une
    pièce suivante résiste, la ligne du journal, qui contient le prompt, peut rester sans plus rien pour la retirer.
    Faut-il effacer le PNG en dernier ? Un échec laisserait alors l'image visible, et on pourrait la rejeter. Je
    modifierais la spec en conséquence. » → oui ;
  - « Dates de la fiche privée. Garder une image privée ne réécrit que sa fiche chiffrée : ses dates de fichier
    changent, pas celles de l'image. Sur le disque ou dans une sauvegarde, on peut donc deviner quelles images
    privées ont été gardées, et combien attendent encore. C'est la fuite que ton choix de la marque chiffrée devait
    éviter. (a) L'accepter et l'écrire dans `DECISIONS.md` et la spec. Le README dit déjà que les dates, tailles et
    nombres de fichiers privés restent visibles sur le disque ; ce serait une limite de plus, de même nature. (b)
    Remettre les dates d'origine. Ce n'est que partiel : la date de changement du système de fichiers reste. (c)
    Réécrire toute l'image dans un dossier neuf. C'est la seule option qui ferme la fuite, mais elle coûte cher et ne
    doit pas risquer de perdre l'image. » → recommandation (a) acceptée ;
  - « Annulation pendant le rangement d'une génération privée. Une course existait avant la refonte : une annulation
    qui arrive pile pendant le rangement laisse l'image privée dans la pile, marquée « terminée ». Le côté public est
    déjà protégé. On corrige de la même façon ? Une annulation arrivée à ce moment-là ne laisserait alors aucune
    image. » → oui ;
  - « Droits des fichiers. Le journal des images (qui contient les prompts) et les PNG de la pile sont créés lisibles
    par les autres comptes de la Mac (0o644). Les passer en lecture par toi seul (0o600) ? Il faudrait un nouveau
    ticket Asana, qui couvrirait aussi les tests de refus d'accès de `/api/keep` et `/api/discard` » → oui ;
  - texte du piège « Verrous » de `CLAUDE.md` proposé par le groupe B → « D'accord pour l'écrire tel quel ? » → oui.
- **Écarté** : défaire le durcissement de `/api/private/delete` ; effacer le PNG d'abord ; remettre les dates de la
  fiche ou réécrire toute l'image privée ; laisser la course d'une annulation privée ; garder les droits 0o644.
- **Conséquences** : remplace, dans « Pile : emplacement des images à trier… » et la spec (section 2), l'ordre « PNG
  d'abord » : Jeter et Supprimer effacent vignettes, images d'entrée, dossier de travail et ligne du journal, puis le
  PNG en dernier, et seulement si tout le reste est parti ; le récit 74 de la spec (rien sur le disque ne dit combien
  d'images privées attendent) devient vrai au contenu près, pas aux dates.

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

_Remplacée en partie le 23/10/2026 (ordre d'effacement : PNG en dernier) par « Suites du groupe B : effacement PNG en
dernier, annulation privée, droits des fichiers, page restaurée »._

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
_Remplacée le 24/10/2026 par la même refonte : deux pages, le Labo (pile à trier, génération en cours, file dans une
feuille, champ de création) et les Tirages (mis à jour seuls, sans bouton Rafraîchir) ; la page En cours, ses
terminées et la Galerie disparaissent._

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
_Remplacée en partie le 24/10/2026 (emplacement du cadenas) par la même refonte : l'entrée est la ligne « Espace
privé » au cadenas de la feuille de la lampe d'état._

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

_Révisée le 23/10/2026 (couleur hors de la visionneuse) par « Refonte « Chambre noire » : lumière inactinique, pixel,
Labo et Tirages, pile à trier » (spec, section 4) : même but, mais hors de la visionneuse la couleur est celle, fixe,
du fond de l'espace (normal ou privé), puisque le fond ne montre plus d'image floutée ; la visionneuse garde son
calcul à partir de l'image, sauf dans l'espace privé (couleur du fond : aucune image privée n'est lue pour la
calculer). Hors de la visionneuse, une couleur fixe évite aussi le bug Chromium 559396686 cité plus
bas._

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

_Remplacée en partie le 24/10/2026 (le Mac passait sans code) par « Code d'accès demandé aussi au Mac, entrée par un
jeton à usage unique »._

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
