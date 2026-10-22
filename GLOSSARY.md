# Chambre noire

Vocabulaire de l'application : ce que l'utilisateur lance, ce qu'il obtient et où ses images sont gardées.

## Générer

**Génération** :
Le calcul d'une image par le moteur, du lancement à l'image produite (ou à l'échec, ou à l'annulation).
_À éviter_ : rendu, tâche

**File d'attente** :
Les générations demandées qui attendent leur tour ; elles sont calculées l'une après l'autre, jamais simultanément.
_À éviter_ : générations parallèles

**Lot** :
Un ensemble de générations lancées d'une seule demande, suivies, annulées et notifiées ensemble.
_À éviter_ : batch, série

**Image d'entrée** :
Une image fournie avec la demande ; sans image d'entrée, la génération part du seul texte, avec une ou plusieurs elle
devient une édition.
_À éviter_ : upload, image source

**Édition** :
Une génération qui part d'une ou plusieurs images d'entrée et d'un texte qui dit quoi changer.
_À éviter_ : mode Éditer

**Dessin** :
Une édition d'une seule image d'entrée sur laquelle on peint la zone à changer (masque) ou un repère pour le modèle
(annotation).
_À éviter_ : inpainting, mode Dessiner

**Variantes** :
Un lot de plusieurs images d'une même demande, chacune avec sa propre graine, parmi lesquelles on garde celles qu'on
veut ; avec ou sans image d'entrée, jamais en campagne.
_À éviter_ : batch, multi-génération

**Campagne** :
Un lot d'édition : le même prompt appliqué séparément à chaque photo, une image par photo.
_À éviter_ : édition en masse, traitement par lot

**Graine** :
Le nombre qui fixe le bruit de départ d'une génération ; deux graines différentes donnent deux images différentes du même prompt.
_À éviter_ : seed (sauf dans le code)

**Modèle** :
Le réseau de génération d'images utilisé (Q4_K_M ou Q8_0).
_À éviter_ : employer « modèle » pour un prompt réutilisable

## Trier

**Pile** :
Les images terminées qui attendent d'être triées, la dernière arrivée sur le dessus ; chaque espace a la sienne.
_À éviter_ : file (réservé aux générations qui attendent leur calcul), brouillons, à valider

**Tirage** :
Une image gardée ; les tirages d'un espace forment sa page Tirages.
_À éviter_ : galerie, image enregistrée

**Garder** :
Faire passer une image de la pile aux tirages (balayage vers la droite).
_À éviter_ : enregistrer, valider

**Jeter** :
Retirer une image de la pile et la supprimer de l'ordinateur (balayage vers la gauche).
_À éviter_ : supprimer (réservé à un tirage), rejeter

## Prompts

**Prompt enregistré** :
Un prompt de l'utilisateur, avec un titre, qu'il peut réutiliser, modifier ou supprimer ; il appartient à l'espace où il a été enregistré.
_À éviter_ : favori, preset

**Catégorie d'un prompt** :
Ce à quoi sert un prompt enregistré ou un prompt type : Créer (sans image d'entrée), Éditer (avec des images d'entrée)
ou Dessiner (dessin) ; elle trie la liste des prompts.
_À éviter_ : usage (sauf dans le code), mode

**Prompt type** :
Un prompt prêt à l'emploi livré avec l'application, en lecture seule, que l'on peut dupliquer en prompt enregistré.
_À éviter_ : template, modèle de prompt

## Confidentialité

**Code d'accès** :
Le code qui ouvre l'application aux appareils autres que l'ordinateur.
_À éviter_ : mot de passe, code privé

**Espace public** :
L'espace où l'on arrive en ouvrant l'application : ses tirages, sa pile, sa file, sa saisie et ses prompts enregistrés,
protégés par le seul code d'accès.
_À éviter_ : galerie normale, mode normal

**Espace privé** :
Un espace étanche à l'espace public (tirages, pile, file, saisie et prompts enregistrés propres) dont tout le contenu
est chiffré sur l'ordinateur, lisible seulement dans l'application avec le code privé.
_À éviter_ : coffre, mode privé, galerie cachée

**Code privé** :
Le code qui déverrouille l'espace privé, distinct du code d'accès et demandé même sur l'ordinateur.
_À éviter_ : mot de passe, code d'accès
