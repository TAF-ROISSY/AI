# TAF WAREHOUSE V4.13 — Lot 9 : ordres de sortie multi-unités

Circuit conforme au cahier des charges, section 10 :

| Étape | Qui | Route | Contrôles |
|---|---|---|---|
| 1. Demande, vérification et réservation du stock | Exploitation, responsable, admin | `POST /api/release-orders` `{warehouse, reference, lines:[{unit_id, quantity}]}` | Unités rangées, disponibles et non bloquées, du même entrepôt. Pas de transfert ni d'inventaire en cours. Quantité disponible après réservations. Pas de doublon. Tout ou rien. Protection anti-doublon. |
| 2. Préparation et contrôle, unité par unité | Magasin (magasinier, chef d'équipe, responsable, admin) | `POST …/{id}/prepare` `{unit_id, note}` | Unité de l'ordre, non bloquée, contrôlée une seule fois. L'ordre passe « Préparé » quand tout est contrôlé. |
| 3. Autorisation de libération | Exploitation, responsable, admin | `POST …/{id}/authorize` | Seulement si tout est préparé. Blocages revérifiés. |
| 4 à 6. Remise, signature, mise à jour du stock | Magasin | `POST …/{id}/complete` `{driver_id, signature_name, signature_data, signature_consent, unit_ids?}` | Signature PNG et consentement exigés. Blocages revérifiés au moment de la remise. **Remise partielle** avec `unit_ids` : le reliquat reste réservé et identifié, l'ordre passe « Remise partielle ». Protection anti-doublon : une sortie ne peut pas être enregistrée deux fois. |
| Refus de signature | Magasin | `POST …/{id}/refuse-signature` `{driver_id?, reason}` | Tracé, sans aucun mouvement de stock. L'exploitation est notifiée. |
| Annulation, ou annulation du reliquat | Exploitation, responsable, admin | `POST …/{id}/cancel` `{reason}` | Libère les réservations non remises. Statut « Annulé », ou « Clôturé (reliquat annulé) » après une remise partielle. |
| Bon de remise PDF | Utilisateurs de l'entrepôt | `GET …/{id}/handovers/{hid}/pdf` | Un bon par remise : unités, poids, transporteur, immatriculation, reliquat éventuel, signature. Mise en page TAF. |

Les sorties unitaires de l'ancien circuit restent disponibles. Une ligne qui appartient à un ordre ne peut pas être traitée par l'ancien circuit (409).

## Interface (page Sorties)
- Création d'un ordre en cochant les unités disponibles, avec la quantité à sortir.
- Carte par ordre : boutons « Contrôlé ✓ » par unité, « Autoriser », « Faire signer le transporteur » (avec choix des unités qui partent), « Refus de signature », « Annuler » ou « Annuler le reliquat », « Bon de remise PDF ».

## Tests réellement exécutés
- **Avant développement :** 7 des 8 nouveaux tests échouaient sur la V4.12. Le huitième, celui de l'anti-doublon, passait « à vide » sur deux réponses « introuvable » identiques. Il a été renforcé.
- **Après développement :** SQLite **85** réussis, plus 2 réservés à PostgreSQL ; PostgreSQL **87/87**.
- **Essai dans Chromium :**
  - ordre de 2 palettes, contrôle de chacune, autorisation ;
  - remise partielle d'une palette, avec signature tracée à la souris ;
  - carte affichée « Remise partielle », avec le reliquat « Autorisée » ;
  - bon de remise PDF vérifié visuellement ;
  - aucune erreur JavaScript.
- **Défaut corrigé pendant l'essai :** la fonction commune des formulaires remplaçait celle du formulaire d'ordre, si bien que l'ordre n'était pas envoyé.
