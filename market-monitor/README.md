# Sentinel — Market Monitor

Dashboard de surveillance de marchés. Le module est séparé des applications TAF OPS et ne passe aucun ordre.

## MVP

- watchlist et graphiques de prix ;
- score de confluence explicable ;
- filtres tendance, RSI, volume et ratio rendement/risque ;
- calculateur de taille de position ;
- import local CSV/JSON ;
- avertissement explicite : outil de simulation, pas conseil financier.

## Structure

- `index.html` : écrans de l’application ;
- `styles.css` : design responsive ;
- `app.js` : orchestration de l’interface et calculateur de risque ;
- `data/` : contrat de fournisseur et données de démonstration ;
- `engine/` : contrat de sortie du moteur d’analyse ;
- `ARCHITECTURE.md` : flux et responsabilités de la V1.

## Lancer

Ouvrir `index.html` dans un navigateur ou servir le dossier avec un serveur statique local.

La prochaine itération doit ajouter une source de cotations choisie par l’utilisateur, sans exposer de clé API dans le navigateur.
