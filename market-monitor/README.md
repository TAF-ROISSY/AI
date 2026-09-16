# Sentinel — Market Monitor

Dashboard local de surveillance de marchés. Le module est séparé des applications TAF OPS et ne passe aucun ordre.

## MVP

- watchlist et graphiques de prix ;
- score de confluence explicable ;
- filtres tendance, RSI, volume et ratio rendement/risque ;
- calculateur de taille de position ;
- import local CSV/JSON ;
- avertissement explicite : outil de simulation, pas conseil financier.

## Lancer

Ouvrir `index.html` dans un navigateur ou servir le dossier avec un serveur statique local.

La prochaine itération doit parser réellement l’export historique et ajouter une source de cotations choisie par l’utilisateur, sans exposer de clé API dans le navigateur.
