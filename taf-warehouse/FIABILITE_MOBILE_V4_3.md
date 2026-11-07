# V4.3 — Fiabilité et mobilité

- Idempotence serveur sur création de sortie, transfert, déplacement et ouverture d’inventaire.
- L’interface utilise une clé UUID par requête et empreinte SHA-256 du contenu, sans stocker le contenu sensible. En cas de perte réseau, recommencer **avec les mêmes données** réutilise la clé.
- En cas de réponse HTTP 4xx, la clé est abandonnée ; en cas d’erreur réseau ou 5xx elle est conservée.
- Impression groupée 80 × 130 mm, scanner QR caméra et signature tactile déjà présents en V4.2.

## Limites à ne pas masquer

Les opérations de validation/confirmation (expédition, remise signée, recomptage, clôture) ne disposent pas encore toutes de clés d’idempotence serveur. Le fonctionnement hors-ligne n'est pas pris en charge. Les essais Safari iOS et les tests sur imprimante physique exigent les appareils réels. Le serveur SQLite reste mono-instance et ne convient pas à un déploiement AWS multi-instance.
