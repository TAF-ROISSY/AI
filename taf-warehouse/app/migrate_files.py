"""Transfert des documents du disque local (data/uploads) vers le stockage S3 privé.

Usage : TAF_STORAGE=s3 TAF_S3_BUCKET=... [TAF_DATABASE_URL=...] python -m app.migrate_files

- vérifie l'empreinte SHA-256 de chaque fichier avant envoi (arrêt si altération) ;
- envoie l'objet chiffré (SSE-S3), relit et revérifie l'empreinte ;
- met à jour la référence en base document par document ;
- rejouable : les documents déjà sur S3 sont ignorés. Les fichiers locaux ne sont pas supprimés.
"""
import hashlib
from pathlib import Path


def migrate():
    from app import server
    if server.STORAGE != 's3' or not server.S3_BUCKET:
        raise SystemExit('Configurer TAF_STORAGE=s3 et TAF_S3_BUCKET.')
    with server.db() as c:
        docs = server.q(c, 'SELECT id,path,sha256,mime FROM documents ORDER BY uploaded,id')
    pending = [d for d in docs if not d['path'].startswith('s3:')]
    for d in pending:  # contrôle complet avant tout envoi
        p = Path(d['path'])
        if not p.is_file():
            raise SystemExit(f"Fichier manquant pour {d['id']} : {p}")
        if hashlib.sha256(p.read_bytes()).hexdigest() != d['sha256']:
            raise SystemExit(f"Empreinte SHA-256 différente pour {d['id']} : fichier altéré, migration arrêtée.")
    for d in pending:
        raw = Path(d['path']).read_bytes()
        ref = server.store_ref(Path(d['path']).name)
        server.store_put(ref, raw, d['mime'] or 'application/octet-stream')
        if hashlib.sha256(server.store_get(ref)).hexdigest() != d['sha256']:
            raise SystemExit(f"Relecture S3 non conforme pour {d['id']}.")
        with server.tx() as c:
            c.execute('UPDATE documents SET path=? WHERE id=?', (ref, d['id']))
            server.audit(c, 'migration', 'storage_migrated', 'document', d['id'], {'to': ref})
    return {'migrated': len(pending), 'already_s3': len(docs) - len(pending)}


if __name__ == '__main__':
    r = migrate()
    print(f"{r['migrated']} document(s) transféré(s) vers S3, {r['already_s3']} déjà présent(s). Fichiers locaux conservés.")
