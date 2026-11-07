"""Sauvegarde SQLite cohérente pour la recette locale; n'est PAS une sauvegarde AWS."""
import os, sqlite3, datetime, pathlib, hashlib, json, sys
root=pathlib.Path(__file__).resolve().parent
source=pathlib.Path(os.getenv('TAF_DATA_DIR',str(root/'data')))
db=source/'warehouse.sqlite3'
if not db.is_file():sys.exit('Base introuvable : démarrez l’application une première fois.')
backup=root/'sauvegardes';backup.mkdir(exist_ok=True)
name='warehouse-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.sqlite3'
destination=backup/name
with sqlite3.connect(db) as src,sqlite3.connect(destination) as dst:
    src.backup(dst)
    result=dst.execute('PRAGMA integrity_check').fetchone()[0]
if result!='ok':
    destination.unlink(missing_ok=True)
    sys.exit('Sauvegarde invalide')
checksum=hashlib.sha256(destination.read_bytes()).hexdigest()
(destination.with_suffix('.sha256')).write_text(checksum+'  '+name+'\n')
print('Sauvegarde cohérente :',destination,'SHA256 :',checksum)
print('Attention : documents et signatures stockés dans data/uploads doivent être sauvegardés séparément.')
