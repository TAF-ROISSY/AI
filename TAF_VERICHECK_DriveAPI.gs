/**
 * TAF VERICHECK - Google Drive Storage API
 * 
 * Gère tous les uploads et stockage de données dans Google Drive
 * - Upload factures (CSV, XLS)
 * - Sauvegarde résultats analyse
 * - Configuration (clients, tarifs)
 * - Validations et litiges
 * 
 * Déployer en Web App avec accès "Anyone" pour utilisation depuis TAF VERICHECK
 */

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

// IDs des dossiers Google Drive (à créer et remplir)
const FOLDER_IDS = {
  ROOT: '1YOUR_ROOT_FOLDER_ID',          // Dossier racine TAF VERICHECK
  FACTURES: '1YOUR_FACTURES_FOLDER_ID',  // Sous-dossier factures/
  ANALYSES: '1YOUR_ANALYSES_FOLDER_ID',  // Sous-dossier analyses/
  CONFIG: '1YOUR_CONFIG_FOLDER_ID',      // Sous-dossier config/
  LITIGES: '1YOUR_LITIGES_FOLDER_ID'     // Sous-dossier litiges/
};

// ═══════════════════════════════════════════════════════════════════════════
// ENDPOINT PRINCIPAL
// ═══════════════════════════════════════════════════════════════════════════

function doPost(e) {
  try {
    const params = JSON.parse(e.postData.contents);
    const action = params.action;
    
    let result;
    
    switch (action) {
      case 'uploadFile':
        result = uploadFile(params.name, params.data, params.folderId);
        break;
        
      case 'readJSON':
        result = readJSON(params.fileId);
        break;
        
      case 'writeJSON':
        result = writeJSON(params.name, params.data, params.folderId);
        break;
        
      case 'listFiles':
        result = listFiles(params.folderId, params.query);
        break;
        
      case 'deleteFile':
        result = deleteFile(params.fileId);
        break;
        
      case 'saveAnalysis':
        result = saveAnalysis(params.data);
        break;
        
      case 'loadLatestAnalysis':
        result = loadLatestAnalysis(params.handler);
        break;
        
      case 'saveConfig':
        result = saveConfig(params.type, params.data);
        break;
        
      case 'loadConfig':
        result = loadConfig(params.type);
        break;
        
      default:
        throw new Error('Action inconnue: ' + action);
    }
    
    return ContentService
      .createTextOutput(JSON.stringify({ success: true, data: result }))
      .setMimeType(ContentService.MimeType.JSON);
      
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({ success: false, error: error.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  return ContentService
    .createTextOutput('TAF VERICHECK Drive API - Use POST requests only')
    .setMimeType(ContentService.MimeType.TEXT);
}

// ═══════════════════════════════════════════════════════════════════════════
// FONCTIONS BASIQUES
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Upload un fichier dans Drive
 * @param {string} name - Nom du fichier
 * @param {string} data - Données base64 ou texte
 * @param {string} folderId - ID du dossier destination
 */
function uploadFile(name, data, folderId) {
  const folder = DriveApp.getFolderById(folderId || FOLDER_IDS.FACTURES);
  
  // Détecter si base64
  let blob;
  if (data.startsWith('data:')) {
    // Data URL (ex: data:text/csv;base64,...)
    const parts = data.split(',');
    const contentType = parts[0].split(':')[1].split(';')[0];
    const base64Data = parts[1];
    blob = Utilities.newBlob(Utilities.base64Decode(base64Data), contentType, name);
  } else {
    // Texte brut
    blob = Utilities.newBlob(data, 'text/plain', name);
  }
  
  // Supprimer ancien fichier même nom (éviter doublons)
  const existing = folder.getFilesByName(name);
  while (existing.hasNext()) {
    existing.next().setTrashed(true);
  }
  
  const file = folder.createFile(blob);
  
  return {
    fileId: file.getId(),
    name: file.getName(),
    url: file.getUrl(),
    size: file.getSize()
  };
}

/**
 * Lit un fichier JSON depuis Drive
 * @param {string} fileId - ID du fichier
 */
function readJSON(fileId) {
  const file = DriveApp.getFileById(fileId);
  const content = file.getBlob().getDataAsString();
  return JSON.parse(content);
}

/**
 * Écrit ou met à jour un fichier JSON dans Drive
 * @param {string} name - Nom du fichier
 * @param {object} data - Données à sauvegarder
 * @param {string} folderId - ID du dossier destination
 */
function writeJSON(name, data, folderId) {
  const folder = DriveApp.getFolderById(folderId || FOLDER_IDS.CONFIG);
  
  // Chercher fichier existant
  const existing = folder.getFilesByName(name);
  
  const jsonString = JSON.stringify(data, null, 2);
  const blob = Utilities.newBlob(jsonString, 'application/json', name);
  
  let file;
  if (existing.hasNext()) {
    // Mettre à jour
    file = existing.next();
    file.setContent(jsonString);
  } else {
    // Créer nouveau
    file = folder.createFile(blob);
  }
  
  return {
    fileId: file.getId(),
    name: file.getName(),
    url: file.getUrl()
  };
}

/**
 * Liste fichiers dans un dossier
 * @param {string} folderId - ID du dossier
 * @param {string} query - Filtre optionnel (nom contient)
 */
function listFiles(folderId, query) {
  const folder = DriveApp.getFolderById(folderId || FOLDER_IDS.ROOT);
  const files = folder.getFiles();
  
  const result = [];
  while (files.hasNext()) {
    const file = files.next();
    const name = file.getName();
    
    if (!query || name.toLowerCase().includes(query.toLowerCase())) {
      result.push({
        fileId: file.getId(),
        name: name,
        mimeType: file.getMimeType(),
        size: file.getSize(),
        dateCreated: file.getDateCreated(),
        lastUpdated: file.getLastUpdated(),
        url: file.getUrl()
      });
    }
  }
  
  return result;
}

/**
 * Supprime un fichier
 * @param {string} fileId - ID du fichier
 */
function deleteFile(fileId) {
  const file = DriveApp.getFileById(fileId);
  file.setTrashed(true);
  return { success: true };
}

// ═══════════════════════════════════════════════════════════════════════════
// FONCTIONS MÉTIER TAF VERICHECK
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Sauvegarde résultat complet d'une analyse
 * @param {object} data - Résultats analyse (data, stats, handler, etc.)
 */
function saveAnalysis(data) {
  const now = new Date();
  const dateStr = Utilities.formatDate(now, 'Europe/Paris', 'yyyy-MM-dd_HHmmss');
  const filename = `${dateStr}_${data.handler}_analyse.json`;
  
  const analysisData = {
    date: now.toISOString(),
    handler: data.handler,
    stats: data.stats,
    results: data.results,
    factureFileName: data.factureFileName,
    dossiersFileName: data.dossiersFileName
  };
  
  return writeJSON(filename, analysisData, FOLDER_IDS.ANALYSES);
}

/**
 * Charge la dernière analyse pour un handler
 * @param {string} handler - Handler (wfs, air_france, etc.)
 */
function loadLatestAnalysis(handler) {
  const files = listFiles(FOLDER_IDS.ANALYSES, handler);
  
  if (files.length === 0) {
    return null;
  }
  
  // Trier par date décroissante
  files.sort((a, b) => b.lastUpdated - a.lastUpdated);
  
  return readJSON(files[0].fileId);
}

/**
 * Sauvegarde configuration (clients, tarifs, validations, litiges)
 * @param {string} type - Type de config (clients, tarifs, validations, litiges)
 * @param {object} data - Données
 */
function saveConfig(type, data) {
  const filename = `${type}.json`;
  const folderId = type === 'litiges' ? FOLDER_IDS.LITIGES : FOLDER_IDS.CONFIG;
  
  return writeJSON(filename, data, folderId);
}

/**
 * Charge configuration
 * @param {string} type - Type de config
 */
function loadConfig(type) {
  const filename = `${type}.json`;
  const folderId = type === 'litiges' ? FOLDER_IDS.LITIGES : FOLDER_IDS.CONFIG;
  
  const folder = DriveApp.getFolderById(folderId);
  const files = folder.getFilesByName(filename);
  
  if (!files.hasNext()) {
    // Pas encore de fichier, retourner objet vide
    return {};
  }
  
  return readJSON(files.next().getId());
}

// ═══════════════════════════════════════════════════════════════════════════
// INITIALISATION STRUCTURE DOSSIERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Crée la structure de dossiers dans Drive
 * À exécuter UNE FOIS manuellement depuis l'éditeur Apps Script
 */
function createFolderStructure() {
  const root = DriveApp.createFolder('TAF VERICHECK');
  const factures = root.createFolder('factures');
  const analyses = root.createFolder('analyses');
  const config = root.createFolder('config');
  const litiges = root.createFolder('litiges');
  
  Logger.log('Structure créée !');
  Logger.log('ROOT: ' + root.getId());
  Logger.log('FACTURES: ' + factures.getId());
  Logger.log('ANALYSES: ' + analyses.getId());
  Logger.log('CONFIG: ' + config.getId());
  Logger.log('LITIGES: ' + litiges.getId());
  Logger.log('');
  Logger.log('Copiez ces IDs dans FOLDER_IDS au début du script !');
}

/**
 * Test des fonctions
 */
function testAPI() {
  // Test upload
  const testData = { test: 'data', timestamp: new Date().toISOString() };
  const upload = writeJSON('test.json', testData, FOLDER_IDS.CONFIG);
  Logger.log('Upload OK: ' + upload.fileId);
  
  // Test read
  const read = readJSON(upload.fileId);
  Logger.log('Read OK: ' + JSON.stringify(read));
  
  // Test list
  const files = listFiles(FOLDER_IDS.CONFIG);
  Logger.log('List OK: ' + files.length + ' fichiers');
  
  // Test delete
  deleteFile(upload.fileId);
  Logger.log('Delete OK');
}
