# Suivi des tickets : Asana

Les tickets de ce dépôt vivent dans le projet Asana « Hub · Suivi des tâches » du porteur, tenu par le skill
`asana-board:suivi-asana` (il fait foi pour le format et les règles d'écriture). Pas d'issues GitHub : le dépôt est
public.

## Repères

| Élément | Valeur |
|---|---|
| Projet | « Hub · Suivi des tâches », GID `1218848573432146` |
| Section du dépôt | « Qwen-Image local », GID `1219496223389136` |
| Tâche mère de Claude | « [code] Qwen-Image local : prochaines sessions Claude Code », GID `1219493010479174` |

Les outils Asana du connecteur sont différés : les charger par `ToolSearch` avant le premier appel.

## Accord avant écriture

La lecture est libre. Toute écriture (créer, modifier, cocher, déplacer, commenter, supprimer) se propose d'abord au
porteur en une liste, et ne part qu'après son oui, y compris après `/to-spec` ou `/to-tickets`. Seule exception :
pendant l'implémentation de tickets que le porteur a lancée, leur suivi s'écrit sans demander (ligne « Statut : »,
commentaire de résultat, cochage à la fin).

## Conventions

- **Un ticket** = une sous-tâche de la tâche mère de Claude (`create_tasks` avec `parent`, sans section). Un seul
  niveau de sous-tâches.
- **Nom** : `[code] Verbe + objet concret`, dans le vocabulaire de `GLOSSARY.md`.
- **Description** en texte brut, une information par ligne, sans puces ni Markdown, dans cet ordre :

  ```
  Statut : à faire
  Contexte : ce que le ticket livre, de bout en bout, du point de vue de l'utilisateur.
  Bloqué par : noms des tickets qui doivent être faits avant (ou « rien »).
  Fini quand : critères d'acceptation observables.
  Origine : docs/specs/<spec>.md, travail/tasks/<plan>.md
  ```

  La ligne « Statut : » est toujours la première (le panneau Asana range les tâches d'après elle).
- **Spécifications** : elles restent dans `docs/specs/` ; chaque ticket y renvoie par sa ligne « Origine ». Les plans
  de travail restent dans `travail/tasks/`.
- **Blocages** : les dépendances Asana sont payantes (plan gratuit) : un ticket écrit ses bloqueurs dans la ligne
  « Bloqué par ». Un ticket est débloqué quand tous les tickets qu'elle nomme sont cochés.
- **Pas de champs personnalisés ni de recherche** (`custom_fields` et `search_tasks` sont refusés au plan gratuit) :
  lister par `get_tasks` sur la section, puis `get_task` sur la tâche mère pour ses sous-tâches.

## Quand un skill dit « publier dans le tracker »

Proposer au porteur la liste des sous-tâches à créer (nom, contenu, bloqueurs), puis, après son accord, les créer
sous la tâche mère de Claude dans l'ordre des dépendances (bloqueurs d'abord), en un seul `create_tasks`.

## Quand un skill dit « lire le ticket »

`get_task` sur son GID (description et commentaires). Le porteur donne en général le nom ou le lien du ticket.

## Commenter, clore

- **Commenter** : `add_comment` sur la tâche.
- **Clore** : cocher la tâche (`update_tasks` avec `completed: true`) avec un commentaire qui dit le résultat et cite
  le hash du commit.
- **Abandonner** : cocher avec un commentaire « abandonné : raison », après accord du porteur.

## Cartographie (`/wayfinder`)

- **Carte** : une tâche mère dédiée, sous la section du dépôt, dont la description tient les notes, les décisions
  prises et le flou restant.
- **Ticket de la carte** : une sous-tâche de cette tâche mère, avec une ligne « Type : » (`research`, `prototype`,
  `grilling`, `task`) sous la ligne « Statut : ».
- **Blocage** : ligne « Bloqué par » ; **réservation** : « Statut : en cours » ; **résolution** : réponse en
  commentaire, tâche cochée, puis une ligne ajoutée aux décisions de la carte.
