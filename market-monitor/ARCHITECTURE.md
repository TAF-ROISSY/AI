# Sentinel — structure de la V1

## Principes

- Le produit ne passe aucun ordre.
- Les données de démonstration sont signalées comme `DEMO`.
- Le moteur doit expliquer chaque signal et conserver sa qualité de donnée.
- Le fournisseur de données est interchangeable.

## Flux prévu

```text
Fournisseur de données
        ↓
MarketDataProvider
        ↓
Normalisation symboles / devises / fuseaux / séances
        ↓
Moteur d’analyse
        ↓
Alertes + scénarios + gestion du risque
        ↓
Interface Sentinel
```

## Écrans

1. **Surveillance** : watchlist, prix, variation, état du marché, alertes et graphique.
2. **Analyse** : tendance, momentum, volatilité, volume, scénarios et invalidation.
3. **Risque** : capital, risque maximal, taille de position, stop, objectif et ratio R/R.
4. **Données** : état du flux, source, horodatage, qualité et import local.

## Données non branchées

Le dossier `data/` contient le contrat de fournisseur et le provider de démonstration. Il sera possible d’ajouter un connecteur Twelve Data, Alpaca ou une autre source sans refaire l’interface.
