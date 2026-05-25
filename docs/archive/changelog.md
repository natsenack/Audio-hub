# Changelog Rules

Ce projet utilise un changelog central dans `CHANGELOG.md` avec le format Keep a Changelog.

## Regles

- Garder `Unreleased` en haut du fichier.
- Ajouter une entree seulement si le changement est visible pour l'utilisateur ou impacte le projet.
- Ecrire des lignes courtes, orientees resultat.
- Regrouper les changements dans les categories `Added`, `Changed`, `Fixed`, `Removed` et `Security` si besoin.
- A chaque release, deplacer les elements de `Unreleased` vers une section versionnee.

## Convention de version

- Utiliser une progression semver simple: `0.x` pendant la phase de prototype, puis `1.0.0` quand le produit est stable.
- Marquer chaque version avec sa date de publication.

## Processus de release

1. Completer la section `Unreleased`.
2. Deplacer les entrees vers une nouvelle version dans `CHANGELOG.md`.
3. Mettre a jour la version courante dans le code si elle est exposee.
4. Tagger la release et publier l'archive ou le paquet.