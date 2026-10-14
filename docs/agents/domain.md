# Documents du domaine

Comment les skills lisent le vocabulaire et les décisions de ce dépôt. Un seul contexte.

## Avant d'explorer, lire

- **`GLOSSARY.md`** à la racine : le vocabulaire de l'application.
- **`DECISIONS.md`** à la racine : les décisions de conception, une entrée par décision, la plus récente en tête. Ce
  dépôt n'a pas de dossier `docs/adr/` : quand un skill parle d'ADR, il s'agit d'une entrée de `DECISIONS.md` (même
  format que les entrées existantes : Contexte, Décision, Écarté, Conséquences ; une décision remplacée garde son
  entrée avec le statut « remplacée le <date> »).

## Employer le vocabulaire du glossaire

Quand un texte nomme un concept du domaine (titre de ticket, proposition, hypothèse, nom de test), employer le terme
de `GLOSSARY.md`, jamais un synonyme qu'il range sous « À éviter ». Un concept absent du glossaire signale soit un
mot inventé (à reconsidérer), soit un manque (à noter pour `/domain-modeling`).

## Signaler les contradictions avec une décision

Si un texte contredit une entrée de `DECISIONS.md`, le dire explicitement plutôt que de passer outre :

> _Contredit « Pas de génération simultanée : une file d'attente » (14/10/2026), mais mérite d'être rouvert parce que…_
