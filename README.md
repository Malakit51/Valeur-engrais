# Valeur des engrais

Appli web installable (téléphone Android, Chrome) : la valeur réelle des engrais minéraux et organiques, et le prix
plancher de la paille exportée, d'après le prix de l'unité de tes engrais de référence. Tout se calcule dans le
navigateur ; tes engrais restent sur le téléphone (bouton ⋯ › « Enregistrer dans un fichier » pour les garder).

Méthode tirée du module Engrais de Tournière.

## Publication

GitHub Pages, branche `main`, dossier racine (Settings › Pages › Deploy from a branch). Fichiers :

| Fichier | Rôle |
|---|---|
| `index.html` | toute l'appli (page, styles, calcul) |
| `manifest.webmanifest` | nom, icône, couleurs : ce qui la rend installable |
| `sw.js` | garde la page sur le téléphone pour l'ouvrir sans réseau |
| `icone.svg`, `icone-*.png` | icône de l'écran d'accueil |

Une mise à jour = remplacer `index.html` et pousser sur `main` ; l'appli installée la prend à la prochaine ouverture
avec du réseau. Si les fichiers mis en cache changent de liste, changer `CACHE` dans `sw.js`.
