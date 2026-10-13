# État du projet

## État

Mis à jour le 13/10/2026.

- **Fonctionnel** sur Windows (Vulkan, CPU, CUDA en option ; sd.cpp `master-890`) et sur Mac Apple Silicon (Metal ;
  sd.cpp `master-959`, encodeur GGUF). Modèles Q4_K_M et Q8_0. Trois usages (texte → image, édition, dessin guidé),
  galerie, estimations calibrées, mode incognito.
- **Chez le porteur** : service macOS lancé avec `--lan`, utilisé depuis le téléphone par le Wi-Fi et par Tailscale
  (application installée en HTTPS via `tailscale serve`). Modèle Q8_0 par défaut (`tools/config.json`).
- **En cours** : rien.
- **À vérifier par le porteur** : télécharger une image incognito sur le téléphone, notamment depuis l'application
  installée. Le téléchargement depuis une adresse `blob:` n'a été testé que dans Chrome sur le Mac.
- **Pistes ouvertes** (aucune demandée) :
  - une exception dans `build_cmd` (prompt non textuel, image de référence illisible) tue le thread `worker()` et bloque
    la file jusqu'au redémarrage ;
  - un autre appareil connecté peut suivre les aperçus d'une génération incognito en cours (`current_job` est exposé
    par `/api/status`) ;
  - accepter toute adresse IP littérale dans la liste blanche de `Host`, pour qu'un changement d'IP du Mac ne coupe plus
    l'accès par IP (décision au porteur) ;
  - `start-ui-sdcpp.cmd` et `workflows/*.json` sont périmés (à mettre à jour ou à retirer) ; `sd_port` de
    `tools/config.json` n'est lu nulle part ;
  - `tests/run_tests.py --only edit` cherche `outputs/test_t2i_512.png`, que plus rien ne produit, et retombe sur
    `tests/test_scene.png` ;
  - l'interrupteur Incognito n'est visible qu'en ouvrant le panneau Réglages ; un bouton près de Générer a été proposé
    au porteur (sans réponse).
- **Ménage local** (sur le poste, hors dépôt) : la branche `fix/server-host-origin` et les worktrees de
  `.claude/worktrees/` sont des restes de sessions passées, déjà intégrés à `main`. La branche contient des informations
  propres au réseau du porteur : la supprimer plutôt que la pousser.

## Journal

### 2026-10-13

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
