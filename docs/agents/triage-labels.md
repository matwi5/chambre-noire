# Rôles de tri

Les skills parlent de cinq rôles de tri. Le Hub Asana est au plan gratuit, sans étiquettes ni champs personnalisés :
chaque rôle se traduit par la ligne « Statut : » de la description et par l'assignation (validé par le porteur le
14/10/2026).

| Rôle dans les skills | Dans Asana | Sens |
|---|---|---|
| `needs-triage` | `Statut : à trancher (tri)` | Le porteur doit évaluer le ticket |
| `needs-info` | `Statut : en attente (<qui>)` | Attend une information (de qui entre parenthèses, 40 caractères au plus) |
| `ready-for-agent` | `Statut : à faire`, non assignée | Spécifié, prêt pour Claude |
| `ready-for-human` | `Statut : à faire`, assignée au porteur | Le porteur doit le faire lui-même |
| `wontfix` | Cochée, avec un commentaire « abandonné : raison » | Ne sera pas fait |

Un ticket fait est coché, avec sa ligne passée à `Statut : fait` et un commentaire qui cite le hash du commit
(décision du porteur du 14/10/2026 : le cochage fait foi, la ligne suit).

Quand un skill demande d'appliquer un rôle (par exemple « apply the `ready-for-agent` label »), écrire la ligne
« Statut : » et l'assignation correspondantes.
