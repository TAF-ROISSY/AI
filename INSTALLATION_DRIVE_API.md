# TAF VERICHECK - Installation Google Drive Storage

## 📋 Étape 1 : Créer l'Apps Script

1. Aller sur https://script.google.com
2. **Nouveau projet** → Nommer "TAF VERICHECK Drive API"
3. Copier tout le contenu de `TAF_VERICHECK_DriveAPI.gs`
4. Coller dans l'éditeur Apps Script

## 📁 Étape 2 : Créer structure de dossiers

1. Dans l'éditeur Apps Script, sélectionner la fonction `createFolderStructure`
2. Cliquer sur **Exécuter** ▶️
3. Autoriser l'accès Google Drive
4. Copier les IDs affichés dans les logs

**Exemple de logs :**
```
Structure créée !
ROOT: 1abc123def456ghi789
FACTURES: 1jkl012mno345pqr678
ANALYSES: 1stu901vwx234yza567
CONFIG: 1bcd890efg123hij456
LITIGES: 1klm789nop012qrs345

Copiez ces IDs dans FOLDER_IDS au début du script !
```

## 🔧 Étape 3 : Configurer les IDs

1. Copier les IDs des logs
2. Les coller dans `FOLDER_IDS` au début du script :

```javascript
const FOLDER_IDS = {
  ROOT: '1abc123def456ghi789',          // ← Votre ID ROOT
  FACTURES: '1jkl012mno345pqr678',      // ← Votre ID FACTURES
  ANALYSES: '1stu901vwx234yza567',      // ← Votre ID ANALYSES
  CONFIG: '1bcd890efg123hij456',        // ← Votre ID CONFIG
  LITIGES: '1klm789nop012qrs345'        // ← Votre ID LITIGES
};
```

3. **Enregistrer** le script (Ctrl+S)

## 🚀 Étape 4 : Déployer en Web App

1. Cliquer sur **Déployer** → **Nouveau déploiement**
2. Type : **Application Web**
3. Configuration :
   - Description : "TAF VERICHECK API v1"
   - Exécuter en tant que : **Moi** (votre compte)
   - Qui a accès : **Tout le monde**
4. Cliquer **Déployer**
5. **Copier l'URL du déploiement**

**Exemple URL :**
```
https://script.google.com/macros/s/AKfycby...XYZ/exec
```

## ✅ Étape 5 : Tester l'API

1. Sélectionner la fonction `testAPI`
2. Cliquer **Exécuter** ▶️
3. Vérifier les logs → Tout doit être "OK"

## 🔗 Étape 6 : Configurer TAF VERICHECK

1. Ouvrir `TAF_VERICHECK_v3.1.html`
2. Remplacer l'URL Apps Script ligne ~160 :

```javascript
const DRIVE_API_URL = 'https://script.google.com/macros/s/VOTRE_URL_ICI/exec';
```

3. Sauvegarder et déployer sur GitHub Pages

## 🎯 Vérification finale

1. Ouvrir TAF VERICHECK dans le navigateur
2. Uploader une facture → Vérifier dans Drive dossier "factures/"
3. Configurer un client → Vérifier dans Drive dossier "config/"
4. Tout doit être sauvegardé automatiquement !

## 📍 Localisation des dossiers Drive

Vous pouvez accéder à vos dossiers :
- Drive Web : https://drive.google.com
- Chercher "TAF VERICHECK" dans la recherche
- Tous vos fichiers seront là, synchronisés !

## 🔄 Accès multi-ordinateurs

Une fois configuré :
✅ Ouvrez TAF VERICHECK depuis n'importe quel ordinateur
✅ Toutes les données sont dans votre Drive
✅ Synchronisation automatique
✅ Historique complet sauvegardé

## ⚠️ Important

- **NE PAS** supprimer les dossiers dans Drive
- **NE PAS** modifier manuellement les fichiers JSON
- Les IDs de dossiers sont permanents (ne changent jamais)
