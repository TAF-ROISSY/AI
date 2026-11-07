# V4.2 — Mobile et étiquettes

- Interface mobile: cibles tactiles >=44 px, navigation horizontale, zone de signature et dialogues adaptés.
- Impression groupée: bouton dans Unités et stock, jusqu’à 40 QR distincts, PDF 80 × 130 mm, une page par unité.
- Scanner: conserve la lecture caméra via BarcodeDetector lorsque le navigateur le prend en charge, et la saisie manuelle. HTTPS ou localhost nécessaire pour la caméra.
- Signature: conserve la capture tactile existante.

## Tests physiques indispensables
Sur iPhone/iPad Safari, BarcodeDetector peut être absent: dans ce cas, utiliser la saisie manuelle en attendant l’intégration d’un décodeur QR compatible. Tester la permission caméra, la mise en veille, la rotation d’écran, les gants, les stylets et la perte réseau.
Imprimante: sélectionner 80 × 130 mm, échelle 100 %, sans marges automatiques; valider l’orientation, la lisibilité du QR et la résistance des étiquettes sur le matériel réel.

Cette version ne garantit pas une compatibilité matérielle universelle.
