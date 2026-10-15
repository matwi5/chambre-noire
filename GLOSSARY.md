# Qwen-Image local

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

**Variantes** :
Un lot du mode Créer : plusieurs images d'un même prompt, chacune avec sa propre graine, parmi lesquelles on garde la meilleure.
_À éviter_ : batch, multi-génération

**Campagne** :
Un lot du mode Éditer : le même prompt appliqué séparément à chaque photo, une image par photo.
_À éviter_ : édition en masse, traitement par lot

**Graine** :
Le nombre qui fixe le bruit de départ d'une génération ; deux graines différentes donnent deux images différentes du même prompt.
_À éviter_ : seed (sauf dans le code)

**Modèle** :
Le réseau de génération d'images utilisé (Q4_K_M ou Q8_0).
_À éviter_ : employer « modèle » pour un prompt réutilisable

## Prompts

**Prompt enregistré** :
Un prompt de l'utilisateur, avec un titre, qu'il peut réutiliser, modifier ou supprimer ; il appartient à l'espace où il a été enregistré.
_À éviter_ : favori, preset

**Prompt type** :
Un prompt prêt à l'emploi livré avec l'application, en lecture seule, que l'on peut dupliquer en prompt enregistré.
_À éviter_ : template, modèle de prompt

## Confidentialité

**Code d'accès** :
Le code qui ouvre l'application aux appareils autres que l'ordinateur.
_À éviter_ : mot de passe, code privé

**Incognito** :
Un mode où l'image produite n'est gardée nulle part sur l'ordinateur : elle est remise une fois à l'appareil, puis oubliée.
_À éviter_ : mode privé

**Espace public** :
L'espace où l'on arrive en ouvrant l'application : sa galerie, sa file, sa saisie et ses prompts enregistrés, protégés par le seul code d'accès.
_À éviter_ : galerie normale, mode normal

**Espace privé** :
Un espace étanche à l'espace public (galerie, file, saisie et prompts enregistrés propres) dont tout le contenu est chiffré sur l'ordinateur, lisible seulement dans l'application avec le code privé.
_À éviter_ : coffre, mode privé, galerie cachée

**Code privé** :
Le code qui déverrouille l'espace privé, distinct du code d'accès et demandé même sur l'ordinateur.
_À éviter_ : mot de passe, code d'accès
