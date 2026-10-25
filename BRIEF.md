# Cadrage

## Objectif

Générer et modifier des images avec Qwen-Image 2.1 entièrement en local, sur un ordinateur ordinaire : un PC portable
Windows à processeur graphique intégré (AMD ou Intel, sans carte NVIDIA) ou un Mac à puce Apple. Rien n'est envoyé
sur Internet en dehors du téléchargement initial du moteur et du modèle. L'application s'appelle « Chambre noire ».

## Utilisateurs

- Le porteur du projet, sur son Mac, et depuis son téléphone par le Wi-Fi ou Tailscale (interface installée comme une
  application).
- Toute personne qui récupère le dépôt public et suit le README (Windows ou Mac). Profil visé : à confirmer.

## Périmètre

- Trois usages, une sortie PNG, depuis le Labo : texte → image (sans image d'entrée) ; édition à partir
  de 1 à 10 images de référence et d'une instruction ; dessin guidé (masque ou annotation peints sur l'image).
- Installation en une commande (`setup.py`) : moteur stable-diffusion.cpp et modèles épinglés, vérifiés par SHA256.
- Estimations de durée calibrées sur la machine, progression et aperçus pendant la génération, annulation.
- File d'attente commune aux appareils (générations calculées l'une après l'autre, jamais simultanément), suivie
  sur le Labo, où la génération en cours se révèle en pixels ; lots : variantes d'un même prompt (avec ou sans image
  d'entrée) et campagne d'édition, une image par photo.
- Chaque image terminée arrive dans une pile à trier : Garder l'envoie dans les Tirages, Jeter l'efface, avec quelques
  secondes pour annuler.
- Prompts enregistrés, partagés entre appareils, et prompts types livrés avec l'application.
- Tirages : les images gardées ; espace privé chiffré, ouvert par un code distinct, en lumière verte, avec sa propre
  pile et ses tirages, dont l'entrée est dans la feuille de la lampe d'état.
- Accès depuis un téléphone protégé par un code ; démarrage automatique en service sur Mac.

## Hors périmètre

- Linux : non pris en charge par `setup.py` (procédure manuelle décrite dans le README).
- ComfyUI et PyTorch (voir `DECISIONS.md`).
- Accès depuis Internet hors du Wi-Fi et du réseau Tailscale du porteur.

## Contraintes

- Aucun droit administrateur, aucune modification du système : tout s'installe dans le dossier du projet.
- Serveur en Python avec la bibliothèque standard, plus Pillow et NumPy ; interface en un seul fichier HTML sans build.
- 24 Go de mémoire vive au minimum, ≈ 35 Go de disque (≈ 50 à 60 Go avec le modèle Q8_0).
- Le dépôt est public : aucune donnée propre à la machine du porteur dans les fichiers suivis.
- Licence du modèle : Qwen Research License (usage commercial encadré) ; code du dépôt sous licence MIT.

## Critères de réussite

- L'installation et une première génération réussissent sur les deux plateformes en suivant le README.
- Les réglages officiels du modèle sont appliqués (Euler, guidance 1, tailles natives jusqu'à 2048 px).
- Les durées affichées avant la génération sont proches des durées mesurées. Écart acceptable : à confirmer.
