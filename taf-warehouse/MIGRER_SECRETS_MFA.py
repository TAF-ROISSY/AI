"""One-time migration for legacy V3.9 plaintext TOTP seeds. Backup DB first."""
import os, sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
root=Path(__file__).resolve().parent
path=Path(os.getenv('TAF_DATA_DIR',root/'data'))/'warehouse.sqlite3'
key=os.getenv('TAF_MFA_ENCRYPTION_KEY','')
if not key:raise SystemExit('TAF_MFA_ENCRYPTION_KEY obligatoire. Sauvegardez la clé hors du serveur.')
cipher=Fernet(key.encode())
with sqlite3.connect(path) as db:
    db.execute('BEGIN IMMEDIATE')
    count=0
    for user_id,secret in db.execute('SELECT user_id,secret FROM mfa').fetchall():
        if secret.startswith('enc:v1:'):
            cipher.decrypt(secret[7:].encode())
            continue
        db.execute('UPDATE mfa SET secret=? WHERE user_id=?',('enc:v1:'+cipher.encrypt(secret.encode()).decode(),user_id))
        count+=1
    db.commit()
print(f'{count} secret(s) MFA migré(s). Conservez la clé : sa perte empêche la connexion MFA.')
