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

## Onglet Marché et alertes

- `outils/releve.py`, lancé chaque lundi par `.github/workflows/releve.yml` : cotations françaises du jour
  ([Web-agri](https://www.web-agri.fr/marches-agricoles/engrais), source citée, historique construit ici depuis le
  29/10/2026), cours mondiaux (Banque mondiale, Pink Sheet, en euros au taux BCE), indice IPAMPA des engrais azotés
  (INSEE). Résultat dans `donnees/cours.json`, lu par l'onglet Marché.
- Alertes : un cours dans le quart le plus bas de ses 3 ans, ou une forte baisse (5 % en 4 semaines pour une cotation
  française, 8 % en un mois pour un cours mondial). Envoyées en notification à l'appli du téléphone : le secret
  `NOTIFICATIONS_ENGRAIS` porte la clé copiée depuis l'appli (menu ⋯ › Alertes sur ce téléphone). Sans lui, ou si
  l'envoi échoue, une issue GitHub « alerte ».
- Essai : Actions › Relevé des cours des engrais › Run workflow, case « essai » cochée.
- Nouveau téléphone ou appli réinstallée : refaire l'activation dans l'appli et remplacer le secret.
