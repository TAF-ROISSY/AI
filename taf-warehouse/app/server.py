"""TAF Warehouse - self-hosted pilot backend. SQLite is for one-server TEST only."""
import os, re, sqlite3, json, secrets, hashlib, hmac, time, uuid, io, csv, base64, binascii, threading, struct
from collections import defaultdict, deque
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Depends, Request, Query, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator
from typing import Optional, Literal, Annotated
from pydantic import StringConstraints
from cryptography.fernet import Fernet, InvalidToken

# --- Secrets (AWS Secrets Manager) ---------------------------------------------------
# TAF_SECRETS_ARN : secret JSON de l'application (clé MFA, mot de passe initial...).
# TAF_DB_SECRET_ARN : secret géré par RDS ({username,password}) + TAF_DB_HOST/PORT/NAME.
# Une variable déjà définie dans l'environnement n'est jamais écrasée.
APP_SECRET_KEYS={'TAF_MFA_ENCRYPTION_KEY','TAF_ADMIN_PASSWORD','TAF_DATABASE_URL'}
def _aws_region():return os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION') or 'eu-west-3'
def _read_secret(arn):
    import boto3
    return json.loads(boto3.client('secretsmanager',region_name=_aws_region()).get_secret_value(SecretId=arn)['SecretString'])
def database_url_from_rds_secret(arn,host,port='5432',name='warehouse'):
    from urllib.parse import quote
    data=_read_secret(arn)
    return f"postgresql://{quote(data['username'],safe='')}:{quote(data['password'],safe='')}@{host}:{port}/{name}?sslmode=require"
def load_secrets():
    arn=os.getenv('TAF_SECRETS_ARN','').strip()
    if arn:
        for k,v in _read_secret(arn).items():
            if k in APP_SECRET_KEYS and not os.getenv(k):os.environ[k]=str(v)
    db_arn=os.getenv('TAF_DB_SECRET_ARN','').strip()
    if db_arn and not os.getenv('TAF_DATABASE_URL'):
        os.environ['TAF_DATABASE_URL']=database_url_from_rds_secret(db_arn,os.environ['TAF_DB_HOST'],os.getenv('TAF_DB_PORT','5432'),os.getenv('TAF_DB_NAME','warehouse'))
load_secrets()

ROOT=Path(__file__).resolve().parent.parent
DATA=Path(os.getenv('TAF_DATA_DIR',ROOT/'data')); DATA.mkdir(parents=True,exist_ok=True)
UPLOAD=DATA/'uploads'; UPLOAD.mkdir(exist_ok=True)
DB=DATA/'warehouse.sqlite3'
PRODUCTION=os.getenv('TAF_ENV','test').lower()=='production'
STORAGE=os.getenv('TAF_STORAGE','local').strip().lower()
S3_BUCKET=os.getenv('TAF_S3_BUCKET','').strip()
S3_PREFIX=os.getenv('TAF_S3_PREFIX','documents/').strip()
# Double authentification obligatoire : par défaut en production pour les rôles sensibles.
# TAF_MFA_ENABLED=0 : double authentification désactivée par décision de TAF (connexion identifiant + code PIN).
MFA_ENABLED=os.getenv('TAF_MFA_ENABLED','1').strip().lower() not in ('0','false','non','off')
MFA_REQUIRED_ROLES={r.strip() for r in os.getenv('TAF_MFA_REQUIRED_ROLES','superadmin,admin,exploitation,manager' if PRODUCTION else '').split(',') if r.strip()} if MFA_ENABLED else set()
def production_problems():
    problems=[]
    if not os.getenv('TAF_DATABASE_URL','').startswith(('postgres://','postgresql://')):problems.append('base PostgreSQL requise (TAF_DATABASE_URL ou TAF_DB_SECRET_ARN)')
    if STORAGE!='s3' or not S3_BUCKET:problems.append('stockage S3 privé requis (TAF_STORAGE=s3, TAF_S3_BUCKET)')
    if not os.getenv('TAF_MFA_ENCRYPTION_KEY','').strip():problems.append('clé de chiffrement MFA requise (TAF_MFA_ENCRYPTION_KEY via Secrets Manager)')
    if MFA_ENABLED and not MFA_REQUIRED_ROLES:problems.append('double authentification obligatoire requise pour les rôles sensibles (TAF_MFA_REQUIRED_ROLES), ou désactivation explicite TAF_MFA_ENABLED=0')
    return problems
if PRODUCTION and production_problems():
    raise RuntimeError('Démarrage en production refusé : '+' ; '.join(production_problems()))
app=FastAPI(title='TAF WAREHOUSE API',version='4.29.0',**({'docs_url':None,'redoc_url':None,'openapi_url':None} if PRODUCTION else {}))

# --- Stockage des documents : disque local (poste de test) ou S3 privé (serveur) -------
_s3_client=None
def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        _s3_client=boto3.client('s3',region_name=_aws_region())
    return _s3_client
def store_ref(name):
    """Référence enregistrée dans documents.path : chemin local ou « s3:<clé> »."""
    return 's3:'+S3_PREFIX+name if STORAGE=='s3' else str(UPLOAD/name)
def store_put(ref,raw,content_type='application/octet-stream'):
    if ref.startswith('s3:'):
        _s3().put_object(Bucket=S3_BUCKET,Key=ref[3:],Body=raw,ContentType=content_type,ServerSideEncryption='AES256')
    else:Path(ref).write_bytes(raw)
def store_get(ref):
    if ref.startswith('s3:'):return _s3().get_object(Bucket=S3_BUCKET,Key=ref[3:])['Body'].read()
    return Path(ref).read_bytes()
def store_delete(ref):
    try:
        if ref.startswith('s3:'):_s3().delete_object(Bucket=S3_BUCKET,Key=ref[3:])
        else:Path(ref).unlink(missing_ok=True)
    except Exception:pass  # nettoyage au mieux ; l'échec d'origine est remonté
def store_erase(ref):
    """Effacement définitif (RGPD) : le compartiment S3 est versionné, toutes les versions sont supprimées. Lève en cas d'échec."""
    if ref.startswith('s3:'):
        key=ref[3:];s3=_s3()
        versions=s3.list_object_versions(Bucket=S3_BUCKET,Prefix=key)
        targets=[{'Key':v['Key'],'VersionId':v['VersionId']} for v in versions.get('Versions',[])+versions.get('DeleteMarkers',[]) if v['Key']==key]
        if targets:
            r=s3.delete_objects(Bucket=S3_BUCKET,Delete={'Objects':targets,'Quiet':True})
            if r.get('Errors'):raise RuntimeError('Effacement S3 incomplet : '+str(r['Errors'][0].get('Message','')))
    else:Path(ref).unlink(missing_ok=True)
# A stable 32-byte Fernet key is mandatory for new MFA enrollment.
# Store it outside the application/database and back it up securely.
def mfa_cipher():
    key=os.getenv('TAF_MFA_ENCRYPTION_KEY','').strip()
    require(bool(key),'Clé de chiffrement MFA non configurée sur le serveur',503)
    try:return Fernet(key.encode('ascii'))
    except (ValueError,TypeError):raise HTTPException(503,'Clé MFA invalide')

def seal_mfa(secret):return 'enc:v1:'+mfa_cipher().encrypt(secret.encode()).decode()
def reveal_mfa(value):
    if value.startswith('enc:v1:'):
        try:return mfa_cipher().decrypt(value[7:].encode()).decode()
        except InvalidToken:raise HTTPException(503,'Déchiffrement MFA impossible : vérifier la clé serveur')
    # Read-only compatibility with legacy V3.9 enrollments; migrate with the CLI.
    return value

def recovery_hash(user_id,code):
    normalized=code.strip().replace('-','').upper()
    return hashlib.sha256((user_id+':'+normalized).encode()).hexdigest()

# Adresse IP du client pour la limitation des tentatives. Derrière la passerelle AWS, l'en-tête
# TAF_CLIENT_IP_HEADER est toujours réécrit par la passerelle (non falsifiable) ; X-Forwarded-For,
# complété et non remplacé par AWS, ne l'est pas. Sans passerelle : adresse de la connexion.
CLIENT_IP_HEADER=os.getenv('TAF_CLIENT_IP_HEADER','').strip().lower()
def client_ip(request):
    if CLIENT_IP_HEADER:
        value=request.headers.get(CLIENT_IP_HEADER,'').strip()
        if value:return value[:64]
    return request.client.host if request.client else 'unknown'
_login_attempts=defaultdict(deque)
_login_lock=threading.Lock()

@app.middleware('http')
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Permissions-Policy']='camera=(self), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Resource-Policy']='same-origin'
    response.headers['X-Permitted-Cross-Domain-Policies']='none'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api/') else 'no-cache'
    response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; media-src 'self' blob:; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response

WAREHOUSES=['Afrique','Maritime','Moyen-Orient','TMS']
ROLES=['superadmin','admin','exploitation','manager','leader','worker']

def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def now_precise(): return datetime.now(timezone.utc).isoformat(timespec='microseconds')  # ordre des événements rapprochés
def uid(prefix): return f'{prefix}-{uuid.uuid4().hex[:10].upper()}'
def next_seq(c,name):
    """Compteur unique, appelé dans une transaction d'écriture (verrou global : pas de doublon)."""
    r=one(c,'SELECT value FROM counters WHERE name=?',(name,))
    if r:
        v=r['value']+1;c.execute('UPDATE counters SET value=? WHERE name=?',(v,name))
    else:
        v=1;c.execute('INSERT INTO counters(name,value) VALUES(?,?)',(name,v))
    return v
def password_hash(p,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),bytes.fromhex(salt),220000).hex()
def password_policy(value):
    require(len(value)>=12 and len(value)<=128 and any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value) and any(not c.isalnum() for c in value), 'Mot de passe : 12 à 128 caractères, majuscule, minuscule, chiffre et symbole')

# Connexion par code PIN (prénom + 6 chiffres) réservée au personnel d'entrepôt.
PIN_ROLES={r.strip() for r in os.getenv('TAF_PIN_ROLES','worker,leader').split(',') if r.strip()}
COMMON_PINS={'0000','1111','1234','4321','1212','2580','0852','1004','2000','1122','6969','1313','1010','2468','1357','0007','7777','000000','111111','121212','123123','112233','123321','159753','147258','258369','696969','101010','131313','999999','202020','200000','100000'}
def pin_policy(pin):
    """Code PIN de 4 à 6 chiffres (5 erreurs = blocage 15 min). Interdits : suites, répétitions, codes courants."""
    require(isinstance(pin,str) and re.fullmatch(r'[0-9]{4,6}',pin or ''),'Code PIN : 4 à 6 chiffres')
    digits=[int(d) for d in pin]
    steps={digits[i+1]-digits[i] for i in range(len(pin)-1)}
    half=len(pin)//2
    simple=len(set(pin))==1 or steps in ({1},{-1}) or pin in COMMON_PINS or (len(pin)%2==0 and pin[:half]==pin[half:]) or (len(pin)==6 and pin[:2]*3==pin)
    require(not simple,f'Code PIN « {pin} » trop simple : pas de suite (1234), de répétition (1111, 1212) ni de code courant')
def verify(p,encoded):
    try:
        salt,digest=encoded.split('$'); return hmac.compare_digest(password_hash(p,salt).split('$')[1],digest)
    except Exception: return False
# --- Accès base : SQLite (poste local, tests) ou PostgreSQL (serveur) -----------------
# TAF_DATABASE_URL=postgresql://... active PostgreSQL. Le code métier reste identique :
# paramètres « ? », lignes accessibles par nom ou par position, BEGIN IMMEDIATE.
DATABASE_URL=os.getenv('TAF_DATABASE_URL','').strip()
PG=DATABASE_URL.startswith(('postgres://','postgresql://'))
IntegrityErrors=(sqlite3.IntegrityError,)
if PG:
    import psycopg
    from decimal import Decimal
    IntegrityErrors=(sqlite3.IntegrityError,psycopg.IntegrityError)
    # Verrou transactionnel unique : reproduit la sérialisation des écritures de SQLite
    # (BEGIN IMMEDIATE), dont dépendent les contrôles anti-double réservation.
    WRITE_LOCK_KEY=7240001

    class _Row(dict):
        def __init__(self,cols,vals):
            vals=tuple((int(v) if v==v.to_integral_value() else float(v)) if isinstance(v,Decimal) else v for v in vals)
            super().__init__(zip(cols,vals));self._vals=vals
        def __getitem__(self,k):return self._vals[k] if isinstance(k,int) else dict.__getitem__(self,k)

    class _Result:
        def __init__(self,cur=None,rows=None):
            self.rowcount=cur.rowcount if cur is not None else 0
            if rows is not None:self._rows=rows
            elif cur is not None and cur.description:
                cols=[d.name for d in cur.description];self._rows=[_Row(cols,r) for r in cur.fetchall()]
            else:self._rows=[]
        def fetchone(self):return self._rows[0] if self._rows else None
        def fetchall(self):return list(self._rows)
        def __iter__(self):return iter(self._rows)

    def _ddl(sql):
        return re.sub(r'\bREAL\b','DOUBLE PRECISION',re.sub(r'\bINTEGER\b','BIGINT',sql))

    class PgConnection:
        def __init__(self):
            self.raw=psycopg.connect(DATABASE_URL,autocommit=True);self.in_tx=False
        def execute(self,sql,args=()):
            head=sql.lstrip().upper()
            if head.startswith('BEGIN'):
                self.raw.execute('BEGIN');self.in_tx=True
                self.raw.execute('SELECT pg_advisory_xact_lock(%s)',(WRITE_LOCK_KEY,));return _Result()
            if head.startswith('PRAGMA'):
                m=re.match(r'\s*PRAGMA\s+table_info\((\w+)\)',sql,re.I)
                if m:
                    cur=self.raw.execute('SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position',(m.group(1).lower(),))
                    return _Result(cur)
                if 'QUICK_CHECK' in head or 'INTEGRITY_CHECK' in head:
                    self.raw.execute('SELECT 1');return _Result(rows=[_Row(['quick_check'],('ok',))])
                return _Result()
            if head.startswith(('CREATE','ALTER')):sql=_ddl(sql)
            return _Result(self.raw.execute(sql.replace('%','%%').replace('?','%s'),tuple(args) if args else None))
        def executescript(self,script):
            for stmt in script.split(';'):
                if stmt.strip() and not stmt.strip().upper().startswith('PRAGMA'):self.execute(stmt)
        def commit(self):
            if self.in_tx:self.raw.execute('COMMIT');self.in_tx=False
        def rollback(self):
            if self.in_tx:self.raw.execute('ROLLBACK');self.in_tx=False
        def close(self):self.raw.close()

@contextmanager
def db():
    if PG:
        c=PgConnection()
        try: yield c
        finally:c.close()
        return
    c=sqlite3.connect(DB,timeout=20,isolation_level=None)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=20000')
    try: yield c
    finally:c.close()
@contextmanager
def tx():
    """Transaction unique : tout est validé ensemble ou rien ne l'est."""
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
def q(c,sql,args=()):return [dict(x) for x in c.execute(sql,args).fetchall()]
def one(c,sql,args=()):
    r=c.execute(sql,args).fetchone();return dict(r) if r else None
def require(cond,msg,code=400):
    if not cond:raise HTTPException(code,msg)
def audit(c,actor,action,kind,ref,details=None):
    c.execute('INSERT INTO audit(id,at,actor,action,kind,ref,details) VALUES(?,?,?,?,?,?,?)',(uid('AUD'),now(),actor,action,kind,ref,json.dumps(details or {},ensure_ascii=False)))
def notify(c,warehouse,kind,ref,title,message,actor):
    c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?,?)',(uid('NOT'),warehouse,kind,ref,title,message,now(),actor))

def replay_request(c, actor, operation, key, payload):
    """Must be called after BEGIN IMMEDIATE, before domain checks/mutations."""
    if key is None:return None, None
    require(8<=len(key)<=128 and key.isascii() and all(ch.isalnum() or ch in '-_.' for ch in key), 'Clé Idempotency-Key invalide')
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    saved=one(c,'SELECT request_hash,response FROM idempotency WHERE actor=? AND operation=? AND request_key=?',(actor,operation,key))
    if saved:
        require(hmac.compare_digest(saved['request_hash'],digest),'Clé de requête réutilisée avec un contenu différent',409)
        return json.loads(saved['response']),digest
    return None,digest

def save_request(c,actor,operation,key,digest,response):
    if key is not None:
        c.execute('INSERT INTO idempotency(actor,operation,request_key,request_hash,response,created) VALUES(?,?,?,?,?,?)',
                  (actor,operation,key,digest,json.dumps(response),now()))

def event(c,actor,unit,kind,src=None,dst=None,quantity=0,ref=None):
    c.execute('INSERT INTO movements(id,at,actor,unit_id,kind,source,destination,quantity,reference) VALUES(?,?,?,?,?,?,?,?,?)',(uid('MVT'),now(),actor,unit,kind,src,dst,quantity,ref))

def init():
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,username TEXT UNIQUE NOT NULL,passhash TEXT NOT NULL,role TEXT NOT NULL,warehouses TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(tokenhash TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS idempotency(actor TEXT NOT NULL,operation TEXT NOT NULL,request_key TEXT NOT NULL,request_hash TEXT NOT NULL,response TEXT NOT NULL,created TEXT NOT NULL,PRIMARY KEY(actor,operation,request_key));
        CREATE TABLE IF NOT EXISTS login_security(username TEXT PRIMARY KEY, failures INTEGER NOT NULL DEFAULT 0, locked_until INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS mfa(user_id TEXT PRIMARY KEY,secret TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,last_counter INTEGER NOT NULL DEFAULT -1,FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS mfa_recovery(user_id TEXT NOT NULL,code_hash TEXT NOT NULL,used_at TEXT,PRIMARY KEY(user_id,code_hash),FOREIGN KEY(user_id) REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS locations(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,zone TEXT NOT NULL,capacity_kg REAL,capacity_m3 REAL,verified INTEGER NOT NULL DEFAULT 0,blocked INTEGER NOT NULL DEFAULT 0,notes TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,client_id TEXT NOT NULL,awb TEXT,expected INTEGER,actual INTEGER,weight REAL,status TEXT NOT NULL,created TEXT NOT NULL,notes TEXT DEFAULT '',FOREIGN KEY(client_id) REFERENCES clients(id));
        CREATE TABLE IF NOT EXISTS units(id TEXT PRIMARY KEY,receipt_id TEXT,warehouse TEXT NOT NULL,location_id TEXT,description TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>=0),weight REAL NOT NULL DEFAULT 0,volume REAL,dimensions_ok INTEGER NOT NULL DEFAULT 0,status TEXT NOT NULL DEFAULT 'available',hold TEXT DEFAULT '',version INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(receipt_id) REFERENCES receipts(id));
        CREATE TABLE IF NOT EXISTS movements(id TEXT PRIMARY KEY,at TEXT NOT NULL,actor TEXT NOT NULL,unit_id TEXT NOT NULL,kind TEXT NOT NULL,source TEXT,destination TEXT,quantity INTEGER NOT NULL,reference TEXT);
        CREATE TABLE IF NOT EXISTS transfers(id TEXT PRIMARY KEY,unit_id TEXT NOT NULL,source TEXT NOT NULL,destination TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,actor TEXT NOT NULL,received_by TEXT,received_at TEXT);
        CREATE TABLE IF NOT EXISTS counts(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,location_id TEXT NOT NULL,unit_id TEXT NOT NULL,expected INTEGER NOT NULL,observed INTEGER NOT NULL,status TEXT NOT NULL,actor TEXT NOT NULL,created TEXT NOT NULL,reviewer TEXT,reason TEXT);
        CREATE TABLE IF NOT EXISTS drivers(id TEXT PRIMARY KEY,name TEXT NOT NULL,company TEXT,plate TEXT,phone TEXT,created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY,unit_id TEXT NOT NULL,quantity INTEGER NOT NULL,status TEXT NOT NULL,requested_by TEXT NOT NULL,authorized_by TEXT,driver_id TEXT,signature_name TEXT,signature_data TEXT,created TEXT NOT NULL,completed TEXT);
        CREATE TABLE IF NOT EXISTS missions(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,title TEXT NOT NULL,leader TEXT,status TEXT NOT NULL,created TEXT NOT NULL,closed TEXT);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,title TEXT NOT NULL,assignee TEXT,status TEXT NOT NULL DEFAULT 'open');
        CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,unit_id TEXT,location_id TEXT,category TEXT NOT NULL,severity TEXT NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,actor TEXT NOT NULL,owner TEXT,resolution TEXT);
        CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY,incident_id TEXT,warehouse TEXT NOT NULL,client_id TEXT,description TEXT NOT NULL,status TEXT NOT NULL,deadline TEXT,owner TEXT,decision TEXT,created TEXT NOT NULL,actor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,kind TEXT NOT NULL,ref TEXT NOT NULL,name TEXT NOT NULL,mime TEXT,sha256 TEXT NOT NULL,path TEXT NOT NULL,uploaded TEXT NOT NULL,actor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,kind TEXT NOT NULL,ref TEXT NOT NULL,title TEXT NOT NULL,message TEXT NOT NULL,created TEXT NOT NULL,actor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notification_reads(notification_id TEXT NOT NULL,user_id TEXT NOT NULL,read_at TEXT NOT NULL,PRIMARY KEY(notification_id,user_id));
        CREATE TABLE IF NOT EXISTS audit(id TEXT PRIMARY KEY,at TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,kind TEXT NOT NULL,ref TEXT NOT NULL,details TEXT);
        ''')
        c.executescript("""
        CREATE TABLE IF NOT EXISTS receipt_discrepancies(id TEXT PRIMARY KEY,receipt_id TEXT NOT NULL,warehouse TEXT NOT NULL,kind TEXT NOT NULL,expected INTEGER NOT NULL,observed INTEGER NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,reported_by TEXT NOT NULL,reviewed_by TEXT,reviewed_at TEXT,decision TEXT,FOREIGN KEY(receipt_id) REFERENCES receipts(id));
        CREATE TABLE IF NOT EXISTS recounts(id TEXT PRIMARY KEY,count_id TEXT NOT NULL UNIQUE,observed INTEGER NOT NULL,actor TEXT NOT NULL,created TEXT NOT NULL,FOREIGN KEY(count_id) REFERENCES counts(id));
        """)
        c.executescript("""
        CREATE TABLE IF NOT EXISTS rack_rules(location_id TEXT PRIMARY KEY, max_unit_kg REAL, max_unit_m3 REAL, max_units INTEGER, allowed_categories TEXT NOT NULL DEFAULT '[]', forbidden_categories TEXT NOT NULL DEFAULT '[]', verified_by TEXT NOT NULL, verified_at TEXT NOT NULL, FOREIGN KEY(location_id) REFERENCES locations(id));
        CREATE TABLE IF NOT EXISTS claim_actions(id TEXT PRIMARY KEY,claim_id TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL,FOREIGN KEY(claim_id) REFERENCES claims(id));
        CREATE TABLE IF NOT EXISTS task_events(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL,FOREIGN KEY(task_id) REFERENCES tasks(id));
        CREATE TABLE IF NOT EXISTS unit_holds(id TEXT PRIMARY KEY,unit_id TEXT NOT NULL,kind TEXT NOT NULL,reason TEXT NOT NULL,ref TEXT,created TEXT NOT NULL,created_by TEXT NOT NULL,lifted_at TEXT,lifted_by TEXT,lift_reason TEXT,FOREIGN KEY(unit_id) REFERENCES units(id));
        CREATE INDEX IF NOT EXISTS unit_holds_active ON unit_holds(unit_id) WHERE lifted_at IS NULL;
        CREATE TABLE IF NOT EXISTS release_orders(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,reference TEXT NOT NULL,status TEXT NOT NULL,requested_by TEXT NOT NULL,created TEXT NOT NULL,authorized_by TEXT,authorized_at TEXT,closed_by TEXT,closed_at TEXT,close_reason TEXT);
        CREATE TABLE IF NOT EXISTS release_handovers(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,driver_id TEXT NOT NULL,signature_name TEXT NOT NULL,signature_data TEXT NOT NULL,signed_at TEXT NOT NULL,actor TEXT NOT NULL,unit_ids TEXT NOT NULL,FOREIGN KEY(order_id) REFERENCES release_orders(id));
        CREATE TABLE IF NOT EXISTS release_refusals(id TEXT PRIMARY KEY,order_id TEXT NOT NULL,driver_id TEXT,reason TEXT NOT NULL,actor TEXT NOT NULL,created TEXT NOT NULL,FOREIGN KEY(order_id) REFERENCES release_orders(id));
        CREATE TABLE IF NOT EXISTS inventory_campaigns(id TEXT PRIMARY KEY,warehouse TEXT NOT NULL,scope TEXT NOT NULL,scope_value TEXT,title TEXT NOT NULL,assignee TEXT NOT NULL,status TEXT NOT NULL,created_by TEXT NOT NULL,created TEXT NOT NULL,closed_by TEXT,closed_at TEXT,close_note TEXT);
        CREATE TABLE IF NOT EXISTS campaign_items(campaign_id TEXT NOT NULL,unit_id TEXT NOT NULL,location_id TEXT,expected INTEGER NOT NULL,observed INTEGER,result TEXT,count_id TEXT,counted_by TEXT,counted_at TEXT,PRIMARY KEY(campaign_id,unit_id),FOREIGN KEY(campaign_id) REFERENCES inventory_campaigns(id));
        CREATE TABLE IF NOT EXISTS mission_events(id TEXT PRIMARY KEY,mission_id TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,note TEXT NOT NULL,created TEXT NOT NULL,FOREIGN KEY(mission_id) REFERENCES missions(id));
        CREATE TABLE IF NOT EXISTS label_prints(id TEXT PRIMARY KEY,unit_id TEXT NOT NULL,actor TEXT NOT NULL,printed_at TEXT NOT NULL,reprint INTEGER NOT NULL DEFAULT 0,batch TEXT,FOREIGN KEY(unit_id) REFERENCES units(id));
        CREATE TABLE IF NOT EXISTS transfer_refusals(id TEXT PRIMARY KEY,transfer_id TEXT NOT NULL,reason TEXT NOT NULL,created_by TEXT NOT NULL,created TEXT NOT NULL,status TEXT NOT NULL,reviewed_by TEXT,reviewed_at TEXT,review_note TEXT,report_document_id TEXT,FOREIGN KEY(transfer_id) REFERENCES transfers(id));
        CREATE TABLE IF NOT EXISTS location_internal(id TEXT PRIMARY KEY,location_id TEXT NOT NULL,description TEXT NOT NULL,service TEXT NOT NULL DEFAULT '',contact TEXT NOT NULL DEFAULT '',quantity TEXT NOT NULL DEFAULT '',since TEXT,until TEXT,notes TEXT NOT NULL DEFAULT '',created_by TEXT NOT NULL,created TEXT NOT NULL,released_at TEXT,released_by TEXT,release_note TEXT,FOREIGN KEY(location_id) REFERENCES locations(id));
        CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY,value INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS mail_routes(warehouse TEXT PRIMARY KEY,recipients TEXT NOT NULL DEFAULT '[]',updated TEXT,updated_by TEXT);
        CREATE TABLE IF NOT EXISTS mail_outbox(id TEXT PRIMARY KEY,kind TEXT NOT NULL,ref TEXT NOT NULL,warehouse TEXT NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL,created TEXT NOT NULL,created_by TEXT NOT NULL,not_before TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,recipients TEXT,subject TEXT,sent_at TEXT,last_error TEXT,provider_id TEXT);
        """)
        for table,fields in {
          'units': [('category',"TEXT NOT NULL DEFAULT 'general'"),('unit_type',"TEXT NOT NULL DEFAULT 'palette'"),('unit_index','INTEGER'),('unit_count','INTEGER'),('length_cm','REAL'),('width_cm','REAL'),('height_cm','REAL')],
          'receipts':[('driver_id','TEXT'),('pallets_expected','INTEGER'),('drums_expected','INTEGER'),('accepted','INTEGER NOT NULL DEFAULT 1'),('refusal_reason',"TEXT NOT NULL DEFAULT ''"),('shipper_address',"TEXT NOT NULL DEFAULT ''"),('consignee',"TEXT NOT NULL DEFAULT ''"),('consignee_address',"TEXT NOT NULL DEFAULT ''"),('stage',"TEXT NOT NULL DEFAULT 'pending'"),('validated_by','TEXT'),('validated_at','TEXT'),('revision','INTEGER NOT NULL DEFAULT 0'),('shipper','TEXT'),('carrier','TEXT'),('transport_ref','TEXT'),('folder_ref','TEXT'),('nature','TEXT'),('apparent_condition','TEXT'),('security_status','TEXT'),('volume_m3','REAL'),('volumetric_weight','REAL')],
          'users':[('can_lift_holds','INTEGER NOT NULL DEFAULT 0'),('deleted_at','TEXT'),('deleted_by','TEXT'),('auth_mode',"TEXT NOT NULL DEFAULT 'password'")],
          'missions':[('priority',"TEXT NOT NULL DEFAULT 'normal'"),('due_at','TEXT'),('description',"TEXT NOT NULL DEFAULT ''"),('type',"TEXT NOT NULL DEFAULT 'autre'"),('assignee','TEXT'),('created_by','TEXT'),('started_at','TEXT'),('completed_by','TEXT'),('completed_at','TEXT'),('receipt_id','TEXT'),('unit_ids','TEXT')],
          'tasks':[('priority',"TEXT NOT NULL DEFAULT 'normal'"),('due_at','TEXT'),('started_at','TEXT'),('completed_at','TEXT'),('completed_by','TEXT'),('notes',"TEXT NOT NULL DEFAULT ''")],
          'documents':[('category',"TEXT NOT NULL DEFAULT ''")],
          'drivers':[('id_type','TEXT'),('id_number','TEXT'),('identity_erased_at','TEXT')],
          'locations':[('status',"TEXT NOT NULL DEFAULT 'ok'"),('status_note',"TEXT NOT NULL DEFAULT ''"),('status_at','TEXT'),('status_by','TEXT'),('kind',"TEXT NOT NULL DEFAULT 'rack'"),('structure','TEXT'),('level','TEXT'),('position','INTEGER'),('active','INTEGER NOT NULL DEFAULT 1'),('created_by','TEXT'),('created','TEXT')],
          'releases':[('order_id','TEXT'),('prepared_by','TEXT'),('prepared_at','TEXT'),('prepare_note','TEXT'),('handover_id','TEXT'),('weight_out','REAL')],
          'transfers':[('received_quantity','INTEGER'),('received_condition','TEXT'),('received_note','TEXT'),('discrepancy_reviewed_by','TEXT'),('discrepancy_reviewed_at','TEXT'),('discrepancy_decision','TEXT'),('return_of','TEXT')],
          'claims':[('closed_by','TEXT'),('closed_at','TEXT'),('evidence_reviewed',"INTEGER NOT NULL DEFAULT 0")]
        }.items():
            present={r['name'] for r in c.execute(f'PRAGMA table_info({table})')}
            for col,definition in fields:
                if col not in present:c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {definition}')
        # Migration additive pour les installations de test existantes.
        columns={r['name'] for r in c.execute('PRAGMA table_info(transfers)')}
        for column in ('approved_by','dispatched_by','dispatched_at','dispatch_note','driver_id','signature_name','signature_data','signature_at'):
            if column not in columns:c.execute(f'ALTER TABLE transfers ADD COLUMN {column} TEXT')
        # Lot 17 : l'historique (journal d'audit) est inaltérable : ni modification ni suppression, même en base.
        if PG:
            c.execute("CREATE OR REPLACE FUNCTION taf_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'Historique inaltérable : modification ou suppression interdite'; END$$")
            c.execute('DROP TRIGGER IF EXISTS audit_immutable ON audit')
            c.execute('CREATE TRIGGER audit_immutable BEFORE UPDATE OR DELETE ON audit FOR EACH ROW EXECUTE FUNCTION taf_audit_immutable()')
        else:
            c.executescript("""CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'Historique inaltérable : modification interdite'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'Historique inaltérable : suppression interdite'); END;""")
        # Lot 15 : structure des emplacements créés avant le générateur.
        for l in q(c,'SELECT id FROM locations WHERE structure IS NULL'):
            mt=re.match(r'^[A-Z]+-(R\d+)-([A-Z])(\d+)$',l['id'])
            if mt:c.execute("UPDATE locations SET kind='rack',structure=?,level=?,position=? WHERE id=?",(mt.group(1),mt.group(2),int(mt.group(3)),l['id']))
            elif l['id'].endswith('-TEMP'):c.execute("UPDATE locations SET kind='temp',structure='TEMP',level='-',position=1 WHERE id=?",(l['id'],))
            else:c.execute("UPDATE locations SET kind='other',structure=?,level='-',position=1 WHERE id=?",(l['id'].split('-',1)[-1],l['id']))
        # Lot 3 : une unité disponible sans emplacement est en attente de rangement.
        c.execute("UPDATE units SET status='awaiting_putaway' WHERE status='available' AND location_id IS NULL")
        # Lot 1 : reprise des blocages texte V4.4 dans la table des blocages multiples.
        for legacy in q(c,"SELECT id,hold FROM units WHERE hold!='' AND NOT EXISTS (SELECT 1 FROM unit_holds h WHERE h.unit_id=units.id AND h.lifted_at IS NULL)"):
            c.execute('INSERT INTO unit_holds(id,unit_id,kind,reason,ref,created,created_by) VALUES(?,?,?,?,?,?,?)',(uid('HLD'),legacy['id'],'legacy',legacy['hold'],None,now(),'migration-lot1'))
        if not one(c,'SELECT id FROM users LIMIT 1') and not os.getenv('TAF_SKIP_BOOTSTRAP'):
            initial=os.getenv('TAF_ADMIN_PASSWORD')
            if not initial and PRODUCTION:
                raise RuntimeError('Premier démarrage en production : TAF_ADMIN_PASSWORD doit être fourni par Secrets Manager')
            if not initial:
                initial=secrets.token_urlsafe(14)
                (DATA/'INITIAL_ADMIN_PASSWORD.txt').write_text('Utilisateur: admin\nMot de passe initial: '+initial+'\nCHANGEZ-LE IMMÉDIATEMENT.\n')
                try:os.chmod(DATA/'INITIAL_ADMIN_PASSWORD.txt',0o600)
                except OSError:pass
            c.execute('INSERT INTO users(id,username,passhash,role,warehouses,active) VALUES(?,?,?,?,?,1)',(uid('USR'),'admin',password_hash(initial),'superadmin',json.dumps(WAREHOUSES)))
            for name in ['CLIENT DEMO','CLIENT TEST']:
                c.execute('INSERT INTO clients VALUES(?,?)',(uid('CLI'),name))
            for wh,code in zip(WAREHOUSES,['AFR','MAR','MO','TMS']):
                for rack in ((1,2) if os.getenv('TAF_DEMO_RACKS','1')=='1' else ()):
                    for level in ('A','B','C'):
                        for n in range(1,9):
                            c.execute("INSERT INTO locations(id,warehouse,zone,verified,kind,structure,level,position) VALUES(?,?,?,0,'rack',?,?,?)",(f'{code}-R{rack:02d}-{level}{n}',wh,f'Rack {rack:02d} / {level}',f'R{rack:02d}',level,n))
                c.execute("INSERT INTO locations(id,warehouse,zone,verified,kind,structure,level,position) VALUES(?,?,?,0,'temp','TEMP','-',1)",(f'{code}-TEMP',wh,'Zone temporaire'))
            audit(c,'system','bootstrap','system','initial',{'warning':'all rack capacities unverified'})
        default_to=[x.strip() for x in os.getenv('TAF_MAIL_DEFAULT_TO','').split(',') if x.strip()]
        for wh in (WAREHOUSES if one(c,'SELECT id FROM users LIMIT 1') else []):  # base vide (migration) : rien
            if not one(c,'SELECT warehouse FROM mail_routes WHERE warehouse=?',(wh,)):
                c.execute('INSERT INTO mail_routes(warehouse,recipients,updated,updated_by) VALUES(?,?,?,?)',(wh,json.dumps(default_to),now(),'system'))
init()

class Login(BaseModel):username:str;password:str;otp:Optional[str]=None;recovery_code:Optional[str]=None
class MFAConfirm(BaseModel):otp:str=Field(min_length=6,max_length=6)
class Password(BaseModel):old:str;new:str=Field(min_length=12)
class UserCreate(BaseModel):username:str;password:Optional[str]=None;pin:Optional[str]=None;role:str;warehouses:list[str]
class PinReset(BaseModel):pin:str
class PinChange(BaseModel):old:str;new:str
class ClientCreate(BaseModel):name:str
class LocationPatch(BaseModel):capacity_kg:Optional[float]=None;capacity_m3:Optional[float]=None;verified:bool=False;blocked:bool=False;notes:str=''
class PackageLine(BaseModel):
    """Une ligne de colisage = une unité logistique (palette ou colis), identifiée individuellement."""
    kind:Literal['palette','colis','fut']='palette'
    length_cm:float=Field(default=0,ge=0,le=2000);width_cm:float=Field(default=0,ge=0,le=2000);height_cm:float=Field(default=0,ge=0,le=1000)  # 0 = à compléter
    weight_kg:float=Field(ge=0,le=50000);packages:int=Field(ge=1,le=10000);notes:str=Field(default='',max_length=500)
class ReceiptCreate(BaseModel):
    warehouse:str;client_id:str;awb:str='';expected:int=Field(ge=0);actual:int=Field(ge=0);weight:float=Field(ge=0);notes:str=''
    shipper:str=Field(default='',max_length=200);carrier:str=Field(default='',max_length=200);transport_ref:str=Field(default='',max_length=100)
    folder_ref:str=Field(default='',max_length=100);nature:str=Field(default='',max_length=300)
    apparent_condition:Optional[Literal['conforme','endommage','a_verifier']]=None
    security_status:Optional[Literal['securise','non_securise','a_controler']]=None
    packages:list[PackageLine]=Field(default_factory=list,max_length=500)
    driver_id:Optional[str]=None;pallets_expected:Optional[int]=Field(default=None,ge=0,le=10000);drums_expected:Optional[int]=Field(default=None,ge=0,le=10000)
    shipper_address:str=Field(default='',max_length=200);consignee:str=Field(default='',max_length=200);consignee_address:str=Field(default='',max_length=200)
class UnitCreate(BaseModel):receipt_id:str;description:str;quantity:int=Field(gt=0);weight:float=Field(ge=0);volume:Optional[float]=Field(default=None,ge=0);dimensions_ok:bool=False;category:str='general';unit_type:Literal['colis','palette']='palette'
class Move(BaseModel):unit_id:str;destination:str;expected_version:int;reason:str='Rangement interne'
class Hold(BaseModel):hold:str;reason:str
class TransferCreate(BaseModel):unit_id:str;destination:str
class TransferDispatch(BaseModel):confirmation:bool=False;note:str=Field(min_length=5,max_length=500);driver_id:str="";signature_name:str="";signature_data:str="";signature_consent:bool=False
class CountCreate(BaseModel):unit_id:str;observed:int=Field(ge=0);reason:str=''
class CountReview(BaseModel):approve:bool;reason:str
class RecountCreate(BaseModel):observed:int=Field(ge=0)
class DiscrepancyCreate(BaseModel):kind:str;description:str=Field(min_length=5,max_length=2000)
class DiscrepancyReview(BaseModel):approve:bool;decision:str=Field(min_length=5,max_length=2000)
class DriverCreate(BaseModel):name:str;company:str='';plate:str='';phone:str='';id_type:Optional[Literal['CNI','passeport','permis','titre_sejour','autre']]=None;id_number:str=Field(default='',max_length=40)
class ReleaseCreate(BaseModel):unit_id:str;quantity:int=Field(gt=0)
class ReleaseComplete(BaseModel):driver_id:str;signature_name:str=Field(min_length=2,max_length=150);signature_data:str=Field(min_length=100,max_length=450000);signature_consent:bool=False
MISSION_OPEN=('open','to_assign','assigned','in_progress','suspended')  # 'open' : missions créées avant la V4.19
MISSION_TYPES=('reception','rangement','preparation','inventaire','transfert','controle','incident','autre')
class MissionCreate(BaseModel):
    warehouse:str;title:Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=200)];leader:str=''
    type:Literal['reception','rangement','preparation','inventaire','transfert','controle','incident','autre']='autre'
    assignee:str='';priority:Literal['low','normal','high','urgent']='normal';due_at:Optional[str]=None;description:str=Field(default='',max_length=2000)
class MissionCheck(BaseModel):unit_id:str=Field(min_length=3,max_length=60)
class MissionAction(BaseModel):action:Literal['take','start','suspend','resume','complete','cancel'];note:str=Field(default='',max_length=1000)
class MissionAssign(BaseModel):assignee:str
class TaskCreate(BaseModel):title:str;assignee:str=''
class IncidentCreate(BaseModel):warehouse:str;unit_id:Optional[str]=None;location_id:Optional[str]=None;category:str;severity:str;description:str
class IncidentUpdate(BaseModel):status:str;resolution:str='';owner:str=''
class ClaimCreate(BaseModel):warehouse:str;incident_id:Optional[str]=None;client_id:Optional[str]=None;description:str;deadline:Optional[str]=None;owner:str=''
class ClaimUpdate(BaseModel):status:str;decision:str='';owner:str=''
class RackRule(BaseModel):max_unit_kg:float=Field(gt=0);max_unit_m3:float=Field(gt=0);max_units:int=Field(gt=0);allowed_categories:list[str]=[];forbidden_categories:list[str]=[];technical_reference:str=Field(min_length=8)
class TaskPlan(BaseModel):assignee:str='';priority:str='normal';due_at:Optional[str]=None;notes:str=''
class TaskAction(BaseModel):note:str=Field(min_length=3)
class MissionPlan(BaseModel):priority:str='normal';due_at:Optional[str]=None;description:str=''
class ClaimAction(BaseModel):action:str;note:str=Field(min_length=5)
class UserStatus(BaseModel):active:bool
class UserReset(BaseModel):password:str=Field(min_length=12)
class UserPermissions(BaseModel):can_lift_holds:bool
class UserUpdate(BaseModel):role:str;warehouses:list[str]
class TransferReceive(BaseModel):
    observed_quantity:int=Field(ge=0)
    condition:Literal['conforme','avarie','manquant','excedent','erreur_identification']='conforme'
    note:Annotated[str,StringConstraints(strip_whitespace=True,max_length=1000)]=''
    @model_validator(mode='after')
    def note_on_discrepancy(self):
        if self.condition!='conforme' and len(self.note)<3:raise ValueError('Observation obligatoire en cas d’écart')
        return self
class CampaignCreate(BaseModel):
    warehouse:str;scope:Literal['warehouse','rack','location'];value:Optional[str]=None
    assignee:str;title:Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=150)]
class CampaignCount(BaseModel):unit_id:str;observed:int=Field(ge=0,le=100000)
class CampaignNote(BaseModel):note:Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=1000)]
class ReleaseLine(BaseModel):unit_id:str;quantity:int=Field(gt=0)
class ReleaseOrderCreate(BaseModel):warehouse:str;reference:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=100)];lines:list[ReleaseLine]=Field(min_length=1,max_length=200)
class OrderPrepare(BaseModel):unit_id:str;note:Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=500)]
class OrderHandover(BaseModel):driver_id:str;signature_name:str=Field(min_length=2,max_length=150);signature_data:str=Field(min_length=100,max_length=450000);signature_consent:bool=False;unit_ids:Optional[list[str]]=None
class OrderRefusal(BaseModel):driver_id:Optional[str]=None;reason:Annotated[str,StringConstraints(strip_whitespace=True,min_length=5,max_length=1000)]
class OrderCancel(BaseModel):reason:Annotated[str,StringConstraints(strip_whitespace=True,min_length=5,max_length=1000)]
class TransferRefusal(BaseModel):reason:Annotated[str,StringConstraints(strip_whitespace=True,min_length=10,max_length=3000)]
class RefusalDecision(BaseModel):decision:Literal['return','accept_with_reserves'];note:Annotated[str,StringConstraints(strip_whitespace=True,min_length=5,max_length=2000)]
class RefusalReview(BaseModel):approve:bool;note:Annotated[str,StringConstraints(strip_whitespace=True,min_length=5,max_length=2000)]
class TransferDiscrepancyReview(BaseModel):accept_observed:bool;decision:Annotated[str,StringConstraints(strip_whitespace=True,min_length=5,max_length=2000)]
class HoldLift(BaseModel):reason:Annotated[str,StringConstraints(strip_whitespace=True,min_length=3,max_length=1000)]

MFA_EXEMPT_PATHS={'/api/me','/api/logout','/api/password','/api/pin','/api/mfa/setup','/api/mfa/confirm','/api/mfa/status'}
def auth(request:Request,authorization:Optional[str]=Header(None)):
    require(authorization and authorization.startswith('Bearer '),'Connexion requise',401)
    digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
    with db() as c:
        u=one(c,'SELECT u.id,u.username,u.role,u.warehouses,u.active,u.can_lift_holds,u.auth_mode,COALESCE(m.enabled,0) mfa_enabled FROM sessions s JOIN users u ON u.id=s.user_id LEFT JOIN mfa m ON m.user_id=u.id WHERE s.tokenhash=? AND s.expires>?',(digest,int(time.time())))
    require(u and u['active'],'Session expirée',401)
    u['warehouses']=json.loads(u['warehouses']);u['mfa_enabled']=bool(u['mfa_enabled']) and MFA_ENABLED;u['mfa_required']=u['role'] in MFA_REQUIRED_ROLES;u['mfa_available']=MFA_ENABLED;u['pin_allowed']=u['role'] in PIN_ROLES
    if u['mfa_required'] and not u['mfa_enabled'] and request.url.path not in MFA_EXEMPT_PATHS:
        raise HTTPException(403,'Double authentification obligatoire pour votre rôle : activez-la avant de continuer')
    return u
def role(u,*allowed):require(u['role'] in allowed or u['role']=='superadmin','Habilitation insuffisante',403)
def access(u,wh):require(wh in u['warehouses'],'Accès entrepôt refusé',403)
def warehouse(wh):require(wh in WAREHOUSES,'Entrepôt inconnu')
def can_lift_holds(u):
    """Règle TAF : levée par l'exploitation ou par un utilisateur habilité par le Super Admin."""
    return u['role']=='exploitation' or bool(u.get('can_lift_holds'))
def sync_hold(c,unit_id):
    """Le champ units.hold reste le résumé des blocages actifs : tous les contrôles existants s'appuient dessus."""
    active=q(c,'SELECT reason FROM unit_holds WHERE unit_id=? AND lifted_at IS NULL ORDER BY created,id',(unit_id,))
    c.execute('UPDATE units SET hold=?,version=version+1 WHERE id=?',(' | '.join(x['reason'] for x in active)[:1000],unit_id))
def add_hold(c,actor,unit_id,kind,reason,ref=None):
    i=uid('HLD')
    c.execute('INSERT INTO unit_holds(id,unit_id,kind,reason,ref,created,created_by) VALUES(?,?,?,?,?,?,?)',(i,unit_id,kind,reason,ref,now(),actor))
    sync_hold(c,unit_id);audit(c,actor,'hold_add','unit',unit_id,{'hold_id':i,'kind':kind,'reason':reason,'ref':ref})
    return i
def lift_hold(c,u,hold,reason):
    require(can_lift_holds(u),'Levée réservée à l’exploitation ou à un utilisateur habilité',403)
    require(hold['lifted_at'] is None,'Blocage déjà levé',409)
    c.execute('UPDATE unit_holds SET lifted_at=?,lifted_by=?,lift_reason=? WHERE id=?',(now(),u['username'],reason,hold['id']))
    sync_hold(c,hold['unit_id']);audit(c,u['username'],'hold_lift','unit',hold['unit_id'],{'hold_id':hold['id'],'kind':hold['kind'],'reason':reason})
def unit_access(c,u,unit_id):
    x=one(c,'SELECT * FROM units WHERE id=?',(unit_id,));require(x,'Unité introuvable',404);access(u,x['warehouse']);return x

def capacity(c,location,extra_weight,extra_volume,exclude_unit=None):
    st=location.get('status') or 'ok' if location else 'ok'
    require(st in ('ok','reserve'),f"Emplacement {LOC_STATUS.get(st,st).lower()} : rangement interdit"+(f" ({location.get('status_note')})" if location and location.get('status_note') else ''),409)
    require(not (location and one(c,'SELECT id FROM location_internal WHERE location_id=? AND released_at IS NULL',(location['id'],))),'Emplacement occupé par un stockage interne TAF',409)
    require(location and location['verified'] and not location['blocked'],'Capacité non vérifiée ou emplacement bloqué')
    require(location['capacity_kg'] is not None and location['capacity_m3'] is not None,'Capacités techniques manquantes')
    vals=(location['id'],) if not exclude_unit else (location['id'],exclude_unit)
    cond="location_id=? AND status='available'"+(' AND id!=?' if exclude_unit else '')
    used=one(c,f'SELECT COALESCE(SUM(weight),0) kg, COALESCE(SUM(volume),0) m3, SUM(CASE WHEN volume IS NULL OR dimensions_ok=0 THEN 1 ELSE 0 END) missing FROM units WHERE {cond}',vals)
    require(not used['missing'],'Encombrement du stock existant inconnu')
    require(used['kg']+extra_weight<=location['capacity_kg'],'Surcharge de l’emplacement')
    require(used['m3']+extra_volume<=location['capacity_m3'],'Volume de l’emplacement dépassé')
    rules=one(c,'SELECT * FROM rack_rules WHERE location_id=?',(location['id'],))
    if rules:
        require(extra_weight<=rules['max_unit_kg'] and extra_volume<=rules['max_unit_m3'],'Unité hors gabarit individuel du rack')
        occupied=one(c,"SELECT COUNT(*) n FROM units WHERE location_id=? AND status='available'"+(' AND id!=?' if exclude_unit else ''), (location['id'],exclude_unit) if exclude_unit else (location['id'],))
        require(occupied['n']+1<=rules['max_units'],'Nombre maximal d’unités dépassé')

def totp(secret,counter):
    key=base64.b32decode(secret,casefold=True)
    mac=hmac.new(key,struct.pack('>Q',counter),hashlib.sha1).digest()
    offset=mac[-1]&15
    number=(int.from_bytes(mac[offset:offset+4],'big')&0x7fffffff)%1000000
    return f'{number:06d}'

def validate_otp(c,user_id,code,consume=True):
    record=one(c,'SELECT secret,enabled,last_counter FROM mfa WHERE user_id=?',(user_id,))
    if not record or not isinstance(code,str) or len(code)!=6 or not code.isascii() or not code.isdigit():return False
    counter=int(time.time())//30
    for step in (counter-1,counter,counter+1):
        if step<=record['last_counter']:continue
        if hmac.compare_digest(totp(reveal_mfa(record['secret']),step),code):
            if consume:c.execute('UPDATE mfa SET last_counter=? WHERE user_id=?',(step,user_id))
            return True
    return False

@app.post('/api/mfa/setup')
def mfa_setup(u=Depends(auth)):
    secret=base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        existing=one(c,'SELECT enabled FROM mfa WHERE user_id=?',(u['id'],))
        require(not existing or not existing['enabled'],'MFA déjà activée',409)
        c.execute('INSERT INTO mfa(user_id,secret,enabled,last_counter) VALUES(?,?,0,-1) ON CONFLICT(user_id) DO UPDATE SET secret=excluded.secret,enabled=0,last_counter=-1',(u['id'],seal_mfa(secret)))
        audit(c,u['username'],'mfa_setup','user',u['id'])
        c.commit()
    from urllib.parse import quote
    uri=f'otpauth://totp/{quote("TAF Warehouse:"+u["username"])}?secret={secret}&issuer=TAF%20Warehouse&algorithm=SHA1&digits=6&period=30'
    import qrcode
    qr=io.BytesIO();qrcode.make(uri).save(qr,format='PNG')
    return {'secret':secret,'otpauth_uri':uri,'qr_png':'data:image/png;base64,'+base64.b64encode(qr.getvalue()).decode(),'instruction':'Scanner le QR code avec votre application Authenticator, puis saisir le code à 6 chiffres.'}

@app.post('/api/mfa/confirm')
def mfa_confirm(x:MFAConfirm,u=Depends(auth)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        record=one(c,'SELECT enabled FROM mfa WHERE user_id=?',(u['id'],))
        require(record and not record['enabled'],'Configuration MFA absente ou déjà active',409)
        require(validate_otp(c,u['id'],x.otp),'Code invalide',403)
        c.execute('UPDATE mfa SET enabled=1 WHERE user_id=?',(u['id'],))
        c.execute('DELETE FROM mfa_recovery WHERE user_id=?',(u['id'],))
        recovery_codes=[secrets.token_hex(6).upper() for _ in range(10)]
        for code in recovery_codes:
            c.execute('INSERT INTO mfa_recovery(user_id,code_hash) VALUES(?,?)',(u['id'],recovery_hash(u['id'],code)))
        c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
        audit(c,u['username'],'mfa_enabled','user',u['id'])
        c.commit()
    return {'ok':True,'message':'MFA activée. Conservez ces codes de secours hors ligne : ils ne seront plus affichés.','recovery_codes':recovery_codes}

@app.get('/api/mfa/status')
def mfa_status(u=Depends(auth)):
    with db() as c:
        record=one(c,'SELECT enabled FROM mfa WHERE user_id=?',(u['id'],))
    return {'enabled':bool(record and record['enabled'])}

@app.post('/api/login')
def login(x:Login,request:Request):
    # Double limitation : IP locale en mémoire et compte persistant dans SQLite.
    # Le verrou compte survit au redémarrage du serveur pilote.
    key=client_ip(request)
    with _login_lock:
        attempts=_login_attempts[key]
        while attempts and attempts[0] < time.monotonic()-300:attempts.popleft()
        require(len(attempts)<15,'Trop de tentatives : réessayez plus tard',429)
    username=x.username.strip().lower()  # identifiant insensible à la casse (majuscule automatique des iPhone)
    current=int(time.time())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM sessions WHERE expires<=?',(current,))
        security=one(c,'SELECT failures,locked_until FROM login_security WHERE username=?',(username,))
        if security and security['locked_until']>current:
            c.commit()
            raise HTTPException(429,'Compte temporairement verrouillé. Réessayez plus tard.')
        u=one(c,'SELECT * FROM users WHERE lower(username)=?',(username,))
        if not (u and u['active'] and verify(x.password,u['passhash'])):
            failures=(security['failures'] if security else 0)+1
            # Après cinq échecs, verrou de 15 minutes; aucun secret journalisé.
            until=current+900 if failures>=5 else 0
            c.execute('INSERT INTO login_security(username,failures,locked_until) VALUES(?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until',(username,failures,until))
            audit(c,'system','login_failed','security',username,{'locked':bool(until)})
            c.commit()
            with _login_lock:_login_attempts[key].append(time.monotonic())
            raise HTTPException(401,'Identifiants invalides')
        mfa_record=one(c,'SELECT enabled FROM mfa WHERE user_id=?',(u['id'],))
        mfa_valid=True
        if not MFA_ENABLED:mfa_record=None  # double authentification désactivée : aucun code demandé
        if mfa_record and mfa_record['enabled'] and not (x.otp or '').strip() and not (x.recovery_code or '').strip():
            c.commit()  # mot de passe correct : on demande le code, sans compter d'échec
            raise HTTPException(401,'Code de double authentification requis')
        if mfa_record and mfa_record['enabled']:
            mfa_valid=validate_otp(c,u['id'],x.otp)
            if not mfa_valid and x.recovery_code:
                candidate=recovery_hash(u['id'],x.recovery_code)
                result=c.execute('UPDATE mfa_recovery SET used_at=? WHERE user_id=? AND code_hash=? AND used_at IS NULL',(now(),u['id'],candidate))
                mfa_valid=result.rowcount==1
                if mfa_valid:audit(c,u['username'],'mfa_recovery_used','security',u['id'])
        if not mfa_valid:
            failures=(security['failures'] if security else 0)+1
            until=current+900 if failures>=5 else 0
            c.execute('INSERT INTO login_security(username,failures,locked_until) VALUES(?,?,?) ON CONFLICT(username) DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until',(username,failures,until))
            audit(c,'system','mfa_failed','security',username,{'locked':bool(until)})
            c.commit()
            with _login_lock:_login_attempts[key].append(time.monotonic())
            raise HTTPException(401,'Code de connexion invalide ou manquant')
        c.execute('DELETE FROM login_security WHERE username=?',(username,))
        with _login_lock:_login_attempts.pop(key,None)
        # Limiter le nombre de sessions simultanées par compte.
        existing=q(c,'SELECT tokenhash FROM sessions WHERE user_id=? ORDER BY expires DESC',(u['id'],))
        for session in existing[4:]:c.execute('DELETE FROM sessions WHERE tokenhash=?',(session['tokenhash'],))
        token=secrets.token_urlsafe(36)
        c.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),u['id'],current+8*3600))
        audit(c,u['username'],'login','session',u['id'])
        c.commit()
    setup_required=u['role'] in MFA_REQUIRED_ROLES and not (mfa_record and mfa_record['enabled'])
    return {'token':token,'mfa_setup_required':setup_required,'user':{'username':u['username'],'role':u['role'],'warehouses':json.loads(u['warehouses'])}}
@app.post('/api/logout')
def logout(authorization:Optional[str]=Header(None),u=Depends(auth)):
    digest=hashlib.sha256(authorization[7:].encode()).hexdigest()
    with tx() as c:
        c.execute('DELETE FROM sessions WHERE tokenhash=?',(digest,))
        audit(c,u['username'],'logout','session',u['id'])
    return {'ok':True}

@app.get('/healthz')
def healthz():
    """Sonde publique minimale pour l'équilibreur / Docker : aucune information interne."""
    try:
        with db() as c:c.execute('SELECT 1').fetchone()
    except Exception:
        raise HTTPException(503,'indisponible')
    return {'status':'ok'}

@app.get('/api/health')
def health(u=Depends(auth)):
    with db() as c:
        integrity=c.execute('PRAGMA quick_check').fetchone()[0]
        require(integrity=='ok','Intégrité base non conforme',503)
        return {'status':'ok','database':'ok','engine':'postgresql' if PG else 'sqlite','server_time':now(),'mode':'local-test'}

@app.get('/api/me')
def me(u=Depends(auth)):return u
@app.post('/api/password')
def change_password(x:Password,u=Depends(auth)):
    with tx() as c:
        row=one(c,'SELECT passhash FROM users WHERE id=?',(u['id'],));require(verify(x.old,row['passhash']),'Ancien mot de passe incorrect',403)
        password_policy(x.new)
        require(not verify(x.new,row['passhash']),'Nouveau mot de passe identique',400)
        c.execute('UPDATE users SET passhash=? WHERE id=?',(password_hash(x.new),u['id']))
        c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],));audit(c,u['username'],'change_password','user',u['id'])
    return {'ok':True,'message':'Reconnectez-vous'}
@app.get('/api/users')
def users(include_deleted:bool=False,u=Depends(auth)):
    role(u,'admin')
    with db() as c:
        rows=q(c,'SELECT id,username,role,warehouses,active,can_lift_holds,deleted_at,deleted_by,auth_mode FROM users'+('' if include_deleted else ' WHERE deleted_at IS NULL')+' ORDER BY username')
    for r in rows:r['warehouses']=json.loads(r['warehouses'])
    return rows
@app.put('/api/users/{userid}')
def update_user(userid:str,x:UserUpdate,u=Depends(auth)):
    """Le Super Admin modifie le rôle et les entrepôts d'un compte ; ses sessions sont fermées."""
    role(u,'superadmin');require(x.role in ROLES,'Rôle invalide')
    require(x.warehouses and len(set(x.warehouses))==len(x.warehouses) and all(w in WAREHOUSES for w in x.warehouses),'Entrepôts invalides')
    with tx() as c:
        t=one(c,'SELECT * FROM users WHERE id=?',(userid,));require(t,'Utilisateur inconnu',404);require(not t['deleted_at'],'Compte supprimé',409)
        require(t['id']!=u['id'],'Un Super Admin ne peut pas modifier son propre rôle (demander à un autre Super Admin)')
        require(t.get('auth_mode')!='pin' or x.role in PIN_ROLES,'Ce compte se connecte par code PIN : rôle réservé aux comptes à mot de passe (créer un compte dédié)')
        c.execute('UPDATE users SET role=?,warehouses=? WHERE id=?',(x.role,json.dumps(x.warehouses),userid))
        c.execute('DELETE FROM sessions WHERE user_id=?',(userid,))
        audit(c,u['username'],'user_update','user',userid,{'username':t['username'],'before':{'role':t['role'],'warehouses':json.loads(t['warehouses'])},'after':x.model_dump()})
    return {'ok':True}
@app.delete('/api/users/{userid}')
def delete_user(userid:str,u=Depends(auth)):
    """Suppression = archivage : plus d'accès ni d'affichage, mais l'historique reste attribué au compte."""
    role(u,'superadmin')
    with tx() as c:
        t=one(c,'SELECT * FROM users WHERE id=?',(userid,));require(t,'Utilisateur inconnu',404);require(not t['deleted_at'],'Compte déjà supprimé',409)
        require(t['id']!=u['id'],'Impossible de supprimer son propre compte')
        c.execute('UPDATE users SET active=0,deleted_at=?,deleted_by=? WHERE id=?',(now(),u['username'],userid))
        c.execute('DELETE FROM sessions WHERE user_id=?',(userid,))
        audit(c,u['username'],'user_delete','user',userid,{'username':t['username'],'role':t['role']})
    return {'ok':True}
@app.post('/api/users')
def create_user(x:UserCreate,u=Depends(auth)):
    role(u,'superadmin');require(x.role in ROLES,'Rôle invalide');require(x.warehouses and all(w in WAREHOUSES for w in x.warehouses),'Entrepôts invalides')
    require((x.password is None)!=(x.pin is None),'Indiquer soit un mot de passe, soit un code PIN')
    if x.pin is not None:
        require(x.role in PIN_ROLES,'Code PIN réservé aux magasiniers et chefs d’équipe : utiliser un mot de passe pour ce rôle')
        pin_policy(x.pin);secret,mode=x.pin,'pin'
    else:
        password_policy(x.password);secret,mode=x.password,'password'
    with tx() as c:
        name=x.username.strip().lower()
        require(2<=len(name)<=60 and ' ' not in name,'Identifiant invalide (2 à 60 caractères, sans espace)')
        require(not one(c,'SELECT id FROM users WHERE lower(username)=?',(name,)),'Identifiant déjà utilisé',409)
        try:c.execute('INSERT INTO users(id,username,passhash,role,warehouses,active,auth_mode) VALUES(?,?,?,?,?,1,?)',(uid('USR'),name,password_hash(secret),x.role,json.dumps(x.warehouses),mode))
        except IntegrityErrors:raise HTTPException(409,'Identifiant déjà utilisé')
        audit(c,u['username'],'create_user','user',name,{'role':x.role,'auth_mode':mode})
    return {'ok':True}
@app.get('/api/clients')
def clients(u=Depends(auth)):
    with db() as c:return q(c,'SELECT * FROM clients ORDER BY name')
@app.post('/api/clients')
def create_client(x:ClientCreate,u=Depends(auth)):
    role(u,'admin','exploitation','manager')
    with tx() as c:
        i=uid('CLI');c.execute('INSERT INTO clients VALUES(?,?)',(i,x.name));audit(c,u['username'],'create','client',i)
    return {'id':i}
@app.get('/api/locations')
def locations(warehouse:Optional[str]=None,u=Depends(auth)):
    if warehouse:access(u,warehouse)
    with db() as c:return q(c,'SELECT * FROM locations WHERE active=1 AND warehouse IN ('+','.join('?' for _ in u['warehouses'])+')'+(' AND warehouse=?' if warehouse else '')+' ORDER BY warehouse,kind,structure,level,position,id',tuple(u['warehouses'])+((warehouse,) if warehouse else ()))
@app.put('/api/locations/{lid}')
def update_location(lid:str,x:LocationPatch,u=Depends(auth)):
    role(u,'admin','manager');
    with db() as c:
        c.execute('BEGIN IMMEDIATE');loc=one(c,'SELECT * FROM locations WHERE id=?',(lid,));require(loc,'Emplacement inconnu',404);access(u,loc['warehouse'])
        require(not x.verified or (x.capacity_kg is not None and x.capacity_m3 is not None),'Données de capacité manquantes')
        require(not x.verified or ('plaque' in x.notes.lower() or 'validation' in x.notes.lower()),'Indiquer la preuve de validation technique (plaque/validation)')
        c.execute('UPDATE locations SET capacity_kg=?,capacity_m3=?,verified=?,blocked=?,notes=? WHERE id=?',(x.capacity_kg,x.capacity_m3,int(x.verified),int(x.blocked),x.notes,lid))
        audit(c,u['username'],'capacity_update','location',lid,{'verified':x.verified,'notes':x.notes});c.commit()
    return {'ok':True}
@app.get('/api/receipts')
def receipts(u=Depends(auth)):
    with db() as c:
        rows=q(c,'SELECT r.*,c.name client FROM receipts r JOIN clients c ON c.id=r.client_id WHERE r.warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY created DESC LIMIT 500',u['warehouses'])
        for r in rows:r['missing']=receipt_missing(c,r['id']) if r.get('stage')!='validated' else []
        return rows
VOLUMETRIC_KG_PER_M3=1000/6  # convention fret aérien IATA 1:6000
@app.post('/api/receipts')
def create_receipt(x:ReceiptCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    warehouse(x.warehouse);access(u,x.warehouse)
    for line in x.packages:require(line.kind!='colis' or line.packages==1,'Une unité de type colis correspond à un seul colis')
    # Totaux et incohérences calculés par le serveur, jamais saisis.
    described=sum(l.packages for l in x.packages);weight_sum=sum(l.weight_kg for l in x.packages)
    volume=sum(l.length_cm*l.width_cm*l.height_cm/1e6 for l in x.packages)
    warnings=[]
    if x.packages and described!=x.actual:warnings.append(f'Colis décrits ({described}) différents des colis reçus ({x.actual})')
    if x.packages and abs(weight_sum-x.weight)>max(1,0.05*x.weight):warnings.append(f'Écart de poids : {round(weight_sum,1)} kg pesés pour {round(x.weight,1)} kg déclarés')
    if x.expected!=x.actual:warnings.append(f'Colis reçus ({x.actual}) différents des colis attendus ({x.expected})')
    status='discrepancy' if warnings else 'received'
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'receipt.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        dgac=(x.driver_id,x.pallets_expected,x.drums_expected,x.shipper_address.strip(),x.consignee.strip(),x.consignee_address.strip())
        require(one(c,'SELECT id FROM clients WHERE id=?',(x.client_id,)),'Client inconnu');require(not x.driver_id or one(c,'SELECT id FROM drivers WHERE id=?',(x.driver_id,)),'Remettant (chauffeur) inconnu');i=f"E-{next_seq(c,'receipt'):06d}"
        c.execute('INSERT INTO receipts(id,warehouse,client_id,awb,expected,actual,weight,status,created,notes,shipper,carrier,transport_ref,folder_ref,nature,apparent_condition,security_status,volume_m3,volumetric_weight) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (i,x.warehouse,x.client_id,x.awb,x.expected,x.actual,x.weight,status,now(),x.notes,x.shipper,x.carrier,x.transport_ref,x.folder_ref,x.nature,x.apparent_condition,x.security_status,round(volume,4) if x.packages else None,round(volume*VOLUMETRIC_KG_PER_M3,2) if x.packages else None))
        c.execute('UPDATE receipts SET driver_id=?,pallets_expected=?,drums_expected=?,shipper_address=?,consignee=?,consignee_address=? WHERE id=?',(*dgac,i))
        audit(c,u['username'],'receive','receipt',i,{'status':status,'warnings':warnings,'units':len(x.packages)})
        unit_ids=[];n=len(x.packages)
        for idx,line in enumerate(x.packages,1):
            uid_=uid('UNIT');unit_ids.append(uid_)
            label={'palette':'Palette','colis':'Colis','fut':'Fût'}[line.kind]+f' {idx}/{n}'
            c.execute('INSERT INTO units(id,receipt_id,warehouse,description,quantity,weight,volume,dimensions_ok,status,category,unit_type,unit_index,unit_count,length_cm,width_cm,height_cm) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (uid_,i,x.warehouse,(x.nature or 'Marchandise')+' — '+label+(' — '+line.notes if line.notes else ''),line.packages,line.weight_kg,round(line.length_cm*line.width_cm*line.height_cm/1e6,4) if dims_ok(line) else None,int(dims_ok(line)),'awaiting_putaway','general',line.kind,idx,n,line.length_cm,line.width_cm,line.height_cm))
            event(c,u['username'],uid_,'receive',None,None,line.packages,i)
            if status=='discrepancy':add_hold(c,u['username'],uid_,'ecart_reception','Écart réception '+i,i)
            if x.security_status in ('non_securise','a_controler'):add_hold(c,u['username'],uid_,'surete','Sûreté : '+('non sécurisé' if x.security_status=='non_securise' else 'à contrôler'),i)
            if x.apparent_condition=='endommage':add_hold(c,u['username'],uid_,'avarie','État apparent endommagé à réception',i)
            elif x.apparent_condition=='a_verifier':add_hold(c,u['username'],uid_,'controle','État apparent à vérifier',i)
        if status=='discrepancy':notify(c,x.warehouse,'receipt',i,'Écart de réception',' ; '.join(warnings)[:350],u['username'])
        totals={'units':n,'packages':described,'weight_kg':round(weight_sum,2),'volume_m3':round(volume,4),'volumetric_weight_kg':round(volume*VOLUMETRIC_KG_PER_M3,2)} if x.packages else None
        # La fiche part par e-mail à la validation finale (dimensions et documents de transport complets).
        response={'id':i,'status':status,'units':unit_ids,'totals':totals,'warnings':warnings};save_request(c,u['id'],'receipt.create',idempotency_key,digest,response)
    return response
@app.get('/api/units')
def units(u=Depends(auth)):
    with db() as c:return q(c,'SELECT u.*,r.awb,c.name client FROM units u LEFT JOIN receipts r ON r.id=u.receipt_id LEFT JOIN clients c ON c.id=r.client_id WHERE u.warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY u.id DESC',u['warehouses'])
@app.post('/api/units')
def create_unit(x:UnitCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    require(x.unit_type=='palette' or x.quantity==1,'Une unité de type colis correspond à un seul colis')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        replay,digest=replay_request(c,u['id'],'unit.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        r=one(c,'SELECT * FROM receipts WHERE id=?',(x.receipt_id,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        # Quantités initiales (mouvements de réception), indépendantes des sorties ultérieures.
        registered=one(c,"SELECT COALESCE(SUM(m.quantity),0) n FROM movements m JOIN units x ON x.id=m.unit_id WHERE m.kind='receive' AND x.receipt_id=?",(r['id'],))['n']
        require(registered+x.quantity<=r['actual'],f"Colis enregistrés ({registered}+{x.quantity}) supérieurs aux colis reçus ({r['actual']}) : signaler un écart de réception",409)
        i=uid('UNIT');c.execute('INSERT INTO units(id,receipt_id,warehouse,description,quantity,weight,volume,dimensions_ok,status,category,unit_type) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,r['id'],r['warehouse'],x.description,x.quantity,x.weight,x.volume,int(x.dimensions_ok),'awaiting_putaway',x.category.strip().lower() or 'general',x.unit_type))
        event(c,u['username'],i,'receive',None,None,x.quantity,r['id']);audit(c,u['username'],'create','unit',i,{'unit_type':x.unit_type,'quantity':x.quantity})
        if r['status']=='discrepancy':
            last=one(c,"SELECT id FROM receipt_discrepancies WHERE receipt_id=? ORDER BY created DESC,id DESC LIMIT 1",(r['id'],))
            add_hold(c,u['username'],i,'ecart_reception','Écart réception '+(last['id'] if last else r['id']),last['id'] if last else r['id'])
        response={'id':i};save_request(c,u['id'],'unit.create',idempotency_key,digest,response);c.commit()
    return response
@app.post('/api/move')
def move(x:Move,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    with db() as c:
        c.execute('BEGIN IMMEDIATE');replay,digest=replay_request(c,u['id'],'unit.move',idempotency_key,x.model_dump())
        if replay is not None:return replay
        unit=unit_access(c,u,x.unit_id);role(u,'worker','leader','manager','exploitation','admin')
        dest=one(c,'SELECT * FROM locations WHERE id=? AND active=1',(x.destination,));require(dest,'Destination inconnue',404);require(dest['warehouse']==unit['warehouse'],'Utiliser un transfert inter-entrepôts')
        require(unit['version']==x.expected_version,'Unité modifiée simultanément',409)
        require(unit['status'] in ('available','awaiting_putaway') and not unit['hold'] and unit['quantity']>0,'Unité indisponible ou bloquée')
        require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),'Transfert actif',409)
        require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Inventaire actif',409)
        require(not one(c,"SELECT id FROM releases WHERE unit_id=? AND status IN ('requested','authorized')",(unit['id'],)),'Sortie réservée',409)
        require(unit['dimensions_ok'] and unit['volume'] is not None,'Dimensions non validées')
        require(unit['location_id']!=dest['id'],'Déjà à destination')
        rules=one(c,'SELECT * FROM rack_rules WHERE location_id=?',(dest['id'],))
        if rules:
            cat=unit['category'] or 'general';allowed=json.loads(rules['allowed_categories']);forbidden=json.loads(rules['forbidden_categories'])
            require((not allowed or cat in allowed) and cat not in forbidden,'Catégorie de marchandise incompatible avec le rack')
            neighbors=q(c,"SELECT DISTINCT category FROM units WHERE location_id=? AND id!=? AND status='available'",(dest['id'],unit['id']))
            require(all((not allowed or n['category'] in allowed) and n['category'] not in forbidden for n in neighbors),'Marchandise déjà stockée incompatible')
        capacity(c,dest,unit['weight'],unit['volume'],unit['id'])
        c.execute("UPDATE units SET location_id=?,status='available',version=version+1 WHERE id=?",(dest['id'],unit['id']))
        event(c,u['username'],unit['id'],'move',unit['location_id'],dest['id'],unit['quantity'],x.reason)
        audit(c,u['username'],'move','unit',unit['id'],{'from':unit['location_id'],'to':dest['id']});save_request(c,u['id'],'unit.move',idempotency_key,digest,{'ok':True});c.commit()
    return {'ok':True}
@app.post('/api/units/{unit_id}/hold')
def hold_unit(unit_id:str,x:Hold,u=Depends(auth)):
    role(u,'manager','exploitation','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');unit_access(c,u,unit_id)
        require(x.reason.strip(),'Justification obligatoire')
        if x.hold.strip():
            add_hold(c,u['username'],unit_id,'manuel',x.hold.strip(),None)
        else:
            # Compatibilité V4.4 : levée sans identifiant seulement s'il n'existe qu'un blocage actif.
            require(can_lift_holds(u),'Levée réservée à l’exploitation ou à un utilisateur habilité',403)
            active=q(c,'SELECT * FROM unit_holds WHERE unit_id=? AND lifted_at IS NULL',(unit_id,))
            require(active,'Aucun blocage actif',409)
            require(len(active)==1,'Plusieurs blocages actifs : lever chacun individuellement',409)
            lift_hold(c,u,active[0],x.reason.strip())
        c.commit()
    return {'ok':True}

@app.get('/api/units/{unit_id}/holds')
def unit_holds(unit_id:str,u=Depends(auth)):
    with db() as c:
        unit_access(c,u,unit_id)
        return q(c,'SELECT * FROM unit_holds WHERE unit_id=? ORDER BY created,id',(unit_id,))

@app.post('/api/holds/{hold_id}/lift')
def lift_unit_hold(hold_id:str,x:HoldLift,u=Depends(auth)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        hold=one(c,'SELECT * FROM unit_holds WHERE id=?',(hold_id,));require(hold,'Blocage introuvable',404)
        unit_access(c,u,hold['unit_id'])
        lift_hold(c,u,hold,x.reason);c.commit()
    return {'ok':True}
@app.get('/api/movements')
def movements(u=Depends(auth)):
    with db() as c:return q(c,'SELECT m.* FROM movements m JOIN units u ON u.id=m.unit_id WHERE u.warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY m.at DESC LIMIT 500',u['warehouses'])
MOVEMENT_KINDS={'receive':'Réception','move':'Rangement / déplacement','exit':'Sortie','transfer_depart':'Départ transfert','transfer_receive':'Arrivée transfert','transfer_adjustment':'Ajustement transfert','refusal_return':'Retour après refus','inventory_adjustment':'Correction d’inventaire'}
@app.get('/api/movements/search')
def search_movements(date_from:Optional[str]=None,date_to:Optional[str]=None,warehouse:Optional[str]=None,kind:Optional[str]=None,actor:Optional[str]=None,
                     driver_id:Optional[str]=None,client_id:Optional[str]=None,unit_id:Optional[str]=None,text:Optional[str]=Query(None,alias='q'),
                     limit:int=100,offset:int=0,format:str='json',u=Depends(auth)):
    """Recherche des mouvements : dates, entrepôt, type, utilisateur, chauffeur, client, unité, texte libre ; export CSV."""
    whs=u['warehouses']
    if warehouse:access(u,warehouse);whs=[warehouse]
    require(not kind or kind in MOVEMENT_KINDS,'Type de mouvement inconnu')
    limit=max(1,min(limit,1000 if format=='csv' else 500));offset=max(0,offset)
    # Chauffeur : sortie unitaire (référence = sortie), ordre de sortie (référence = ordre) ou transfert.
    base=f"""FROM movements m JOIN units un ON un.id=m.unit_id
      LEFT JOIN receipts rc ON rc.id=un.receipt_id LEFT JOIN clients cl ON cl.id=rc.client_id
      LEFT JOIN releases rl ON rl.id=m.reference
      LEFT JOIN releases ro ON ro.order_id=m.reference AND ro.unit_id=m.unit_id AND ro.handover_id IS NOT NULL
      LEFT JOIN transfers tr ON tr.id=m.reference
      LEFT JOIN drivers dr ON dr.id=COALESCE(rl.driver_id,ro.driver_id,tr.driver_id)
      WHERE un.warehouse IN ({','.join('?' for _ in whs)})"""
    args=list(whs)
    def add(cond,*vals):
        nonlocal base;base+=' AND '+cond;args.extend(vals)
    if date_from:add('m.at>=?',date_from[:10])
    if date_to:add('m.at<?',date_to[:10]+'T99')
    if kind:add('m.kind=?',kind)
    if actor:add('lower(m.actor)=?',actor.strip().lower())
    if driver_id:add('dr.id=?',driver_id)
    if client_id:add('cl.id=?',client_id)
    if unit_id:add('m.unit_id=?',unit_id)
    if text and text.strip():
        like='%'+text.strip().lower().replace('%','').replace('_','')+'%'
        add('(lower(m.unit_id) LIKE ? OR lower(COALESCE(m.reference,\'\')) LIKE ? OR lower(COALESCE(rc.awb,\'\')) LIKE ? OR lower(COALESCE(rc.id,\'\')) LIKE ? OR lower(COALESCE(dr.name,\'\')) LIKE ? OR lower(COALESCE(dr.plate,\'\')) LIKE ? OR lower(COALESCE(dr.company,\'\')) LIKE ? OR lower(COALESCE(cl.name,\'\')) LIKE ?)',*([like]*8))
    cols="""m.id,m.at,m.kind,m.unit_id,m.source,m.destination,m.quantity,m.reference,m.actor,un.warehouse,un.unit_type,un.unit_index,un.unit_count,
      rc.id receipt_id,rc.awb,cl.name client,dr.id driver_id,dr.name driver_name,dr.company driver_company,dr.plate driver_plate"""
    with db() as c:
        total=c.execute('SELECT COUNT(*) '+base,tuple(args)).fetchone()[0]
        items=q(c,f'SELECT {cols} {base} ORDER BY m.at DESC,m.id DESC LIMIT {limit} OFFSET {offset}',tuple(args))
        audit(c,u['username'],'movement_search','security','search',{'filters':{k:v for k,v in dict(date_from=date_from,date_to=date_to,warehouse=warehouse,kind=kind,actor=actor,driver_id=driver_id,client_id=client_id,unit_id=unit_id,q=text).items() if v},'total':total,'format':format})
    for it in items:it['kind_label']=MOVEMENT_KINDS.get(it['kind'],it['kind'])
    if format=='csv':
        out=io.StringIO();w=csv.writer(out,delimiter=';')
        w.writerow(['Date','Type','Unité','Colis','Entrepôt','Départ','Arrivée','Référence','Réception','LTA','Client','Chauffeur','Société','Immatriculation','Utilisateur'])
        for it in items:w.writerow([it['at'],it['kind_label'],it['unit_id'],it['quantity'],it['warehouse'],it['source'] or '',it['destination'] or '',it['reference'] or '',it['receipt_id'] or '',it['awb'] or '',it['client'] or '',it['driver_name'] or '',it['driver_company'] or '',it['driver_plate'] or '',it['actor']])
        return Response(content='\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="mouvements-taf-warehouse.csv"'})
    return {'total':total,'items':items,'limit':limit,'offset':offset}

# --- Lot 12 : recherche universelle, chronologie, plan des racks ----------------------
@app.get('/api/search')
def universal_search(text:str=Query('',alias='q'),u=Depends(auth)):
    term=text.strip().lower().replace('%','').replace('_','')
    res={k:[] for k in ('units','receipts','clients','locations','release_orders','transfers','incidents','claims','drivers')}
    if len(term)<2:return {**res,'total':0}
    like='%'+term+'%';m=','.join('?' for _ in u['warehouses']);w=tuple(u['warehouses'])
    with db() as c:
        res['units']=q(c,f"SELECT u.id,u.warehouse,u.status,u.location_id,u.unit_type,u.unit_index,u.unit_count,u.description FROM units u WHERE u.warehouse IN ({m}) AND (lower(u.id) LIKE ? OR lower(u.description) LIKE ?) ORDER BY u.id DESC LIMIT 10",w+(like,like))
        res['receipts']=q(c,f"SELECT r.id,r.warehouse,r.awb,r.status,r.created,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.warehouse IN ({m}) AND (lower(r.id) LIKE ? OR lower(COALESCE(r.awb,'')) LIKE ? OR lower(COALESCE(r.folder_ref,'')) LIKE ? OR lower(COALESCE(r.transport_ref,'')) LIKE ? OR lower(COALESCE(r.shipper,'')) LIKE ?) ORDER BY r.created DESC LIMIT 10",w+(like,)*5)
        res['clients']=q(c,"SELECT id,name FROM clients WHERE lower(name) LIKE ? ORDER BY name LIMIT 10",(like,))
        res['locations']=q(c,f"SELECT id,warehouse,zone FROM locations WHERE warehouse IN ({m}) AND lower(id) LIKE ? ORDER BY id LIMIT 10",w+(like,))
        res['release_orders']=q(c,f"SELECT id,warehouse,reference,status,created FROM release_orders WHERE warehouse IN ({m}) AND (lower(id) LIKE ? OR lower(reference) LIKE ?) ORDER BY created DESC LIMIT 10",w+(like,like))
        res['transfers']=q(c,f"SELECT id,unit_id,source,destination,status FROM transfers WHERE (source IN ({m}) OR destination IN ({m})) AND (lower(id) LIKE ? OR lower(unit_id) LIKE ?) ORDER BY created DESC LIMIT 10",w+w+(like,like))
        res['incidents']=q(c,f"SELECT id,warehouse,severity,status,description FROM incidents WHERE warehouse IN ({m}) AND (lower(id) LIKE ? OR lower(description) LIKE ?) ORDER BY created DESC LIMIT 10",w+(like,like))
        res['claims']=q(c,f"SELECT id,warehouse,status,description FROM claims WHERE warehouse IN ({m}) AND (lower(id) LIKE ? OR lower(description) LIKE ?) ORDER BY created DESC LIMIT 10",w+(like,like))
        res['drivers']=q(c,"SELECT id,name,company,plate FROM drivers WHERE lower(name) LIKE ? OR lower(COALESCE(plate,'')) LIKE ? OR lower(COALESCE(company,'')) LIKE ? ORDER BY name LIMIT 10",(like,like,like))
    return {**res,'total':sum(len(v) for v in res.values())}

TIMELINE_RANK={'reception':0,'label':1,'move':2,'transfer_out':2,'transfer_in':2,'hold':3,'incident':3,'hold_lift':4,'count':5,'inventory':5,'release_order':6,'prepare':7,'authorize':8,'exit':9}
@app.get('/api/units/{unit_id}/timeline')
def unit_timeline(unit_id:str,u=Depends(auth)):
    """Historique complet d'une unité, du plus ancien au plus récent."""
    with db() as c:
        unit=unit_access(c,u,unit_id);ev=unit_events(c,unit)
    return {'unit':{k:unit[k] for k in ('id','warehouse','status','location_id','quantity','weight','unit_type','unit_index','unit_count','description','hold')},'events':ev}
def unit_events(c,unit):
        unit_id=unit['id'];ev=[]
        def add(at,kind,title,actor=None,detail='',ref=None):
            if at:ev.append({'at':at,'kind':kind,'title':title,'actor':actor,'detail':detail,'ref':ref})
        rc=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(unit['receipt_id'],)) if unit['receipt_id'] else None
        labels={'move':('move','Rangement / déplacement'),'transfer_depart':('transfer_out','Départ en transfert'),'transfer_receive':('transfer_in','Arrivée de transfert'),
                'inventory_adjustment':('inventory','Correction d’inventaire'),'transfer_adjustment':('inventory','Ajustement après écart de transfert'),'refusal_return':('transfer_out','Retour après refus')}
        for mv in q(c,'SELECT * FROM movements WHERE unit_id=? ORDER BY at,id',(unit_id,)):
            if mv['kind']=='receive':
                add(mv['at'],'reception','Réception',mv['actor'],f"{mv['quantity']} colis"+(f" · LTA {rc['awb']}" if rc and rc.get('awb') else '')+(f" · {rc['client']}" if rc else ''),mv['reference'])
            elif mv['kind']=='exit':
                d=one(c,"SELECT d.name,d.company,d.plate FROM drivers d WHERE d.id=COALESCE((SELECT driver_id FROM releases WHERE id=?),(SELECT driver_id FROM releases WHERE order_id=? AND unit_id=? AND handover_id IS NOT NULL LIMIT 1))",(mv['reference'],mv['reference'],unit_id))
                add(mv['at'],'exit','Sortie remise au transporteur',mv['actor'],f"{mv['quantity']} colis"+(f" · {d['name']}"+(f" ({d['company']})" if d.get('company') else '')+(f" · {d['plate']}" if d.get('plate') else '') if d else ''),mv['reference'])
            else:
                k,t=labels.get(mv['kind'],(mv['kind'],mv['kind']));add(mv['at'],k,t,mv['actor'],' → '.join(x for x in (mv['source'],mv['destination']) if x)+(f" · {mv['quantity']:+d} colis" if mv['kind'] in ('inventory_adjustment','transfer_adjustment') else ''),mv['reference'])
        for lp in q(c,'SELECT * FROM label_prints WHERE unit_id=?',(unit_id,)):add(lp['printed_at'],'label','Réimpression d’étiquette' if lp['reprint'] else 'Impression d’étiquette',lp['actor'])
        for hd in q(c,'SELECT * FROM unit_holds WHERE unit_id=?',(unit_id,)):
            add(hd['created'],'hold','Blocage : '+hd['reason'],hd['created_by'],hd['kind'],hd['ref'])
            add(hd['lifted_at'],'hold_lift','Levée du blocage : '+hd['reason'],hd['lifted_by'],hd['lift_reason'] or '',hd['ref'])
        for n in q(c,'SELECT * FROM counts WHERE unit_id=?',(unit_id,)):
            add(n['created'],'count','Comptage d’inventaire',n['actor'],f"{n['observed']} compté(s) pour {n['expected']} attendu(s) · {({'approved':'validé','pending':'en attente','rejected':'rejeté'}).get(n['status'],n['status'])}",n['id'])
        for r in q(c,'SELECT r.*,o.reference,o.authorized_at,o.authorized_by o_auth FROM releases r LEFT JOIN release_orders o ON o.id=r.order_id WHERE r.unit_id=?',(unit_id,)):
            add(r['created'],'release_order','Demande de sortie'+(f" {r['reference']}" if r.get('reference') else ''),r['requested_by'],f"{r['quantity']} colis",r.get('order_id') or r['id'])
            add(r.get('prepared_at'),'prepare','Préparation et contrôle',r.get('prepared_by'),r.get('prepare_note') or '',r.get('order_id'))
            if r['status'] in ('authorized','completed'):add(r.get('authorized_at'),'authorize','Sortie autorisée',r.get('o_auth') or r.get('authorized_by'),'',r.get('order_id'))
        for t in q(c,'SELECT * FROM transfers WHERE unit_id=?',(unit_id,)):add(t['created'],'transfer_out','Transfert demandé',t['actor'],f"{t['source']} → {t['destination']}",t['id'])
        for i in q(c,'SELECT * FROM incidents WHERE unit_id=?',(unit_id,)):add(i['created'],'incident','Incident '+i['severity'],i['actor'],i['description'][:200],i['id'])
        ev.sort(key=lambda e:(e['at'][:19],TIMELINE_RANK.get(e['kind'],5)))
        return ev

@app.get('/api/locations/plan')
def locations_plan(warehouse:str,u=Depends(auth)):
    """Plan des racks : niveaux du haut vers le bas, état et occupation de chaque emplacement."""
    access(u,warehouse)
    with db() as c:
        locs=q(c,'SELECT * FROM locations WHERE warehouse=? ORDER BY id',(warehouse,))
        occ={r['location_id']:r for r in q(c,"SELECT location_id,COUNT(*) units,COALESCE(SUM(weight),0) kg,COALESCE(SUM(volume),0) m3,SUM(CASE WHEN hold!='' THEN 1 ELSE 0 END) held FROM units WHERE warehouse=? AND status='available' AND location_id IS NOT NULL GROUP BY location_id",(warehouse,))}
        reserved={r['location_id'] for r in q(c,"SELECT DISTINCT un.location_id FROM releases r JOIN units un ON un.id=r.unit_id WHERE un.warehouse=? AND r.status IN ('requested','authorized')",(warehouse,))}
        internal={r['location_id']:r for r in q(c,'SELECT i.* FROM location_internal i JOIN locations l ON l.id=i.location_id WHERE l.warehouse=? AND i.released_at IS NULL',(warehouse,))}
    racks={};kinds={}
    for l in locs:
        if not l.get('active',1):continue
        rack,level,pos=l.get('structure') or l['id'],l.get('level') or '-',l.get('position') or 1
        kinds[rack]=l.get('kind') or 'rack'
        o=occ.get(l['id'],{})
        n=o.get('units',0)
        st=l.get('status') or 'ok'
        state='blocked' if l['blocked'] else 'out' if st in ('endommage','maintenance','inspection') else 'held' if o.get('held') else 'reserved' if l['id'] in reserved else 'occupied' if n else 'internal' if l['id'] in internal else 'booked' if st=='reserve' else 'unverified' if not l['verified'] else 'free'
        cell={'id':l['id'],'position':pos,'state':state,'units':n,'kg':round(o.get('kg',0),1),'m3':round(o.get('m3',0),3),
              'capacity_kg':l['capacity_kg'],'capacity_m3':l['capacity_m3'],'verified':bool(l['verified']),
              'load_pct':round(100*o.get('kg',0)/l['capacity_kg'],1) if l['capacity_kg'] else None,
              'status':st,'status_label':LOC_STATUS.get(st,st),'status_note':l.get('status_note') or '','status_by':l.get('status_by'),'status_at':l.get('status_at'),'internal':internal.get(l['id'])}
        racks.setdefault(rack,{}).setdefault(str(level),[]).append(cell)
    order={'rack':0,'shelf':1,'floor':2,'vault':3,'other':4,'temp':5}
    out=[]
    for rack in sorted(racks,key=lambda r:(order.get(kinds[r],4),r)):
        top_first=kinds[rack] in ('rack','shelf')   # racks et étagères : niveau du haut en premier ; sol : allée A en premier
        levels=[{'level':lv,'cells':sorted(cells,key=lambda x:x['position'])} for lv,cells in sorted(racks[rack].items(),reverse=top_first)]
        out.append({'rack':rack,'kind':kinds[rack],'label':STRUCTURE_LABEL(kinds[rack],rack),'levels':levels})
    states=[cell['state'] for r in out for lv in r['levels'] for cell in lv['cells']]
    return {'warehouse':warehouse,'racks':out,'summary':{s_:states.count(s_) for s_ in ('free','occupied','internal','booked','reserved','held','out','blocked','unverified')}}

@app.get('/api/transfers')
def transfers(u=Depends(auth)):
    cols="id,unit_id,source,destination,status,created,actor,received_by,received_at,approved_by,dispatched_by,dispatched_at,dispatch_note,driver_id,signature_name,signature_at,received_quantity,received_condition,received_note,discrepancy_reviewed_by,discrepancy_reviewed_at,discrepancy_decision,return_of"
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:return q(c,f"SELECT {cols},CASE WHEN COALESCE(signature_data,'')='' THEN 0 ELSE 1 END has_signature,(SELECT quantity FROM units WHERE units.id=transfers.unit_id) unit_quantity FROM transfers WHERE source IN ({marks}) OR destination IN ({marks}) ORDER BY created DESC",u['warehouses']*2)
@app.post('/api/transfers')
def transfer(x:TransferCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key")):
    role(u,'exploitation','manager','admin');warehouse(x.destination);access(u,x.destination)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        replay,digest=replay_request(c,u['id'],'transfer.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        unit=unit_access(c,u,x.unit_id)
        require(unit['warehouse']!=x.destination,'Entrepôts identiques')
        require(unit['status']=='available' and not unit['hold'] and unit['quantity']>0,'Unité bloquée ou vide')
        require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),'Transfert déjà actif',409)
        require(not one(c,"SELECT id FROM releases WHERE unit_id=? AND status IN ('requested','authorized')",(unit['id'],)),'Sortie en attente',409)
        require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Inventaire en attente',409)
        i=uid('TRF')
        c.execute('INSERT INTO transfers(id,unit_id,source,destination,status,created,actor) VALUES(?,?,?,?,?,?,?)',(i,unit['id'],unit['warehouse'],x.destination,'requested',now(),u['username']))
        audit(c,u['username'],'request','transfer',i);notify(c,unit['warehouse'],'transfer',i,'Transfert demandé','Validation exploitation requise avant expédition.',u['username'])
        save_request(c,u['id'],'transfer.create',idempotency_key,digest,{'id':i,'status':'requested'});c.commit()
    return {'id':i,'status':'requested'}
@app.post('/api/transfers/{tid}/cancel')
def cancel_transfer(tid:str,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,))
        require(t,'Transfert inconnu',404);access(u,t['source'])
        require(t['status'] in ('requested','approved'),'Annulation impossible après expédition',409)
        require(not t['return_of'],'Un retour décidé après refus ne peut pas être annulé',409)
        c.execute("UPDATE transfers SET status='cancelled' WHERE id=?",(tid,))
        audit(c,u['username'],'cancel','transfer',tid)
        notify(c,t['source'],'transfer',tid,'Transfert annulé','La réservation du stock est libérée.',u['username'])
        c.commit()
    return {'ok':True}

@app.post('/api/transfers/{tid}/approve')
def approve_transfer(tid:str,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404);access(u,t['source'])
        require(t['status']=='requested','Transfert non validable',409)
        require(t['actor']!=u['username'],'Validation indépendante requise',403)
        unit=one(c,'SELECT * FROM units WHERE id=?',(t['unit_id'],))
        require(unit and unit['warehouse']==t['source'] and unit['status']=='available' and not unit['hold'] and unit['quantity']>0,'Unité indisponible',409)
        c.execute("UPDATE transfers SET status='approved',approved_by=? WHERE id=?",(u['username'],tid))
        audit(c,u['username'],'approve','transfer',tid);c.commit()
    return {'ok':True}
@app.post('/api/transfers/{tid}/dispatch')
def dispatch_transfer(tid:str,x:TransferDispatch,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'worker','leader','manager','admin')
    require(x.confirmation,'Confirmer la remise physique au transporteur')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');replay,digest=replay_request(c,u['id'],'transfer.dispatch',idempotency_key,{'ref':tid,'payload':x.model_dump()});
        if replay is not None:return replay
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404);access(u,t['source'])
        require(t['status']=='approved','Validation préalable requise',409)
        unit=one(c,'SELECT * FROM units WHERE id=?',(t['unit_id'],))
        if t['return_of']:
            # Retour après refus : la marchandise n'a jamais été remise en stock et reste bloquée.
            require(unit and unit['warehouse']==t['source'] and unit['status']=='in_transit','Unité indisponible',409)
        else:
            require(unit and unit['warehouse']==t['source'] and unit['status']=='available' and not unit['hold'] and unit['quantity']>0,'Unité indisponible',409)
        require(x.signature_consent and len(x.signature_name.strip())>=2,'Confirmation et nom du signataire obligatoires')
        driver=one(c,'SELECT id FROM drivers WHERE id=?',(x.driver_id,));require(driver,'Transporteur non enregistré',404)
        require(x.signature_data.startswith('data:image/png;base64,'),'Signature PNG obligatoire')
        try: signed=base64.b64decode(x.signature_data.split(',',1)[1],validate=True)
        except (ValueError,binascii.Error):raise HTTPException(400,'Signature corrompue')
        require(signed.startswith(b'\x89PNG\r\n\x1a\n') and 300<len(signed)<320000,'Signature PNG invalide ou trop volumineuse')
        require(not one(c,"SELECT id FROM releases WHERE unit_id=? AND status IN ('requested','authorized')",(unit['id'],)),'Sortie en attente',409)
        require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Inventaire en attente',409)
        c.execute("UPDATE transfers SET status='in_transit',dispatched_by=?,dispatched_at=?,dispatch_note=?,driver_id=?,signature_name=?,signature_data=?,signature_at=? WHERE id=?",(u['username'],now(),x.note,x.driver_id,x.signature_name,x.signature_data,now(),tid))
        c.execute("UPDATE units SET status='in_transit',location_id=NULL,version=version+1 WHERE id=?",(unit['id'],))
        event(c,u['username'],unit['id'],'transfer_depart',t['source'],t['destination'],unit['quantity'],tid)
        audit(c,u['username'],'dispatch','transfer',tid,{'note':x.note});notify(c,t['destination'],'transfer',tid,'Transfert expédié','Réception physique à confirmer.',u['username']);save_request(c,u['id'],'transfer.dispatch',idempotency_key,digest,{'ok':True});c.commit()
    return {'ok':True}
@app.get('/api/transfers/{tid}/dispatch-pdf')
def transfer_dispatch_pdf(tid:str,u=Depends(auth)):
    with db() as c:
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404)
        require(t['source'] in u['warehouses'] or t['destination'] in u['warehouses'],'Accès refusé',403)
        require(t['signature_data'] and t['status'] in ('in_transit','received','discrepancy','refusal_pending','refused','returned','received_with_reserves'),'Transfert non signé',409)
        unit=one(c,'SELECT un.*,r.awb,cl.name client FROM units un LEFT JOIN receipts r ON r.id=un.receipt_id LEFT JOIN clients cl ON cl.id=r.client_id WHERE un.id=?',(t['unit_id'],))
        driver=one(c,'SELECT * FROM drivers WHERE id=?',(t['driver_id'],))
    from app.pdf_report import transfer_report
    raw=transfer_report(t,unit or {},driver,now())
    return Response(content=raw,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="transfert-{tid}.pdf"'})
@app.post('/api/transfers/{tid}/receive')
def receive_transfer(tid:str,x:Optional[TransferReceive]=None,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'worker','leader','exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');replay,digest=replay_request(c,u['id'],'transfer.receive',idempotency_key,{'ref':tid,'payload':x.model_dump() if x else {}});
        if replay is not None:return replay
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404);access(u,t['destination']);require(t['status']=='in_transit','Transfert non expédié ou déjà réceptionné',409)
        require(t['dispatched_by']!=u['username'],'Réception indépendante du départ obligatoire',403)
        unit=one(c,'SELECT * FROM units WHERE id=?',(t['unit_id'],));require(unit and unit['status']=='in_transit','Statut incohérent',409)
        observed=x.observed_quantity if x else unit['quantity'];condition=x.condition if x else 'conforme';note=x.note if x else ''
        gap=observed!=unit['quantity'] or condition!='conforme'
        status='discrepancy' if gap else 'received'
        c.execute('UPDATE transfers SET status=?,received_by=?,received_at=?,received_quantity=?,received_condition=?,received_note=? WHERE id=?',(status,u['username'],now(),observed,condition,note,tid))
        c.execute("UPDATE units SET warehouse=?,status='awaiting_putaway',location_id=NULL,version=version+1 WHERE id=?",(t['destination'],unit['id']))
        event(c,u['username'],unit['id'],'transfer_receive',t['source'],t['destination'],unit['quantity'],tid)
        audit(c,u['username'],'receive','transfer',tid,{'observed':observed,'dispatched':unit['quantity'],'condition':condition,'note':note})
        if gap:
            # Jamais de correction silencieuse : stock maintenu à la quantité expédiée et bloqué jusqu'à décision.
            add_hold(c,u['username'],unit['id'],'ecart_transfert',f"Écart transfert {tid} : {condition}, {observed}/{unit['quantity']}",tid)
            notify(c,t['destination'],'transfer',tid,'Écart à réception de transfert',f"{condition} : {observed} reçu(s) pour {unit['quantity']} expédié(s). Décision indépendante requise.",u['username'])
        response={'ok':True,'status':status};save_request(c,u['id'],'transfer.receive',idempotency_key,digest,response);c.commit()
    return response

@app.post('/api/transfers/{tid}/discrepancy-review')
def review_transfer_discrepancy(tid:str,x:TransferDiscrepancyReview,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'exploitation','manager','admin')
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'transfer.discrepancy_review',idempotency_key,{'ref':tid,'payload':x.model_dump()})
        if replay is not None:return replay
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404);access(u,t['destination'])
        require(t['status']=='discrepancy','Aucun écart en attente de décision',409)
        require(t['received_by']!=u['username'],'Décision indépendante de la réception obligatoire',403)
        unit=one(c,'SELECT * FROM units WHERE id=?',(t['unit_id'],));require(unit and unit['warehouse']==t['destination'],'Statut incohérent',409)
        if x.accept_observed and t['received_quantity']!=unit['quantity']:
            observed=t['received_quantity']
            new_weight=round(unit['weight']*observed/unit['quantity'],3) if unit['quantity'] else unit['weight']
            c.execute("UPDATE units SET quantity=?,weight=?,status=CASE WHEN ?=0 THEN 'depleted' ELSE status END,version=version+1 WHERE id=?",(observed,new_weight,observed,unit['id']))
            event(c,u['username'],unit['id'],'transfer_adjustment',t['destination'],t['destination'],observed-unit['quantity'],tid)
            audit(c,u['username'],'transfer_adjustment','unit',unit['id'],{'transfer':tid,'quantity_before':unit['quantity'],'quantity_after':observed,'weight_before':unit['weight'],'weight_after':new_weight,'decision':x.decision})
        c.execute("UPDATE transfers SET status='received',discrepancy_reviewed_by=?,discrepancy_reviewed_at=?,discrepancy_decision=? WHERE id=?",(u['username'],now(),('Quantité constatée retenue : ' if x.accept_observed else 'Quantité expédiée maintenue : ')+x.decision,tid))
        audit(c,u['username'],'discrepancy_review','transfer',tid,x.model_dump())
        notify(c,t['destination'],'transfer',tid,'Écart de transfert tranché','Le blocage reste en place jusqu’à levée autorisée.',u['username'])
        response={'ok':True,'hold_remains':True};save_request(c,u['id'],'transfer.discrepancy_review',idempotency_key,digest,response)
    return response
# Lot 3 : refus de transfert — rapport du magasinier, validation du responsable magasin.
@app.post('/api/transfers/{tid}/refuse')
def refuse_transfer(tid:str,x:TransferRefusal,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'worker','leader','manager','admin')
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'transfer.refuse',idempotency_key,{'ref':tid,'payload':x.model_dump()})
        if replay is not None:return replay
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404);access(u,t['destination'])
        require(t['status']=='in_transit','Refus possible uniquement pour un transfert en transit non réceptionné',409)
        require(t['dispatched_by']!=u['username'],'Le refus doit être constaté par une autre personne que l’expéditeur',403)
        i=uid('REFUS')
        c.execute('INSERT INTO transfer_refusals(id,transfer_id,reason,created_by,created,status) VALUES(?,?,?,?,?,?)',(i,tid,x.reason,u['username'],now(),'pending'))
        c.execute("UPDATE transfers SET status='refusal_pending' WHERE id=?",(tid,))
        add_hold(c,u['username'],t['unit_id'],'refus_transfert','Refus transfert '+tid,tid)
        audit(c,u['username'],'refuse','transfer',tid,{'refusal':i,'reason':x.reason})
        notify(c,t['destination'],'transfer',tid,'Rapport de refus à valider','Responsable magasin : joindre photo(s) et valider le rapport '+i+'.',u['username'])
        response={'id':i,'status':'pending'};save_request(c,u['id'],'transfer.refuse',idempotency_key,digest,response)
    return response

@app.get('/api/transfer-refusals')
def transfer_refusals(u=Depends(auth)):
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:return q(c,f'SELECT r.*,t.source,t.destination,t.unit_id FROM transfer_refusals r JOIN transfers t ON t.id=r.transfer_id WHERE t.source IN ({marks}) OR t.destination IN ({marks}) ORDER BY r.created DESC',u['warehouses']*2)

def refusal_report_pdf(refusal,t,unit,driver,docs):
    from app.pdf_report import refusal_report
    return refusal_report(refusal,t,unit,driver,docs,now())

@app.post('/api/transfer-refusals/{rid}/review')
def review_transfer_refusal(rid:str,x:RefusalReview,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'manager','admin')
    path=None
    try:
        with tx() as c:
            replay,digest=replay_request(c,u['id'],'transfer.refusal_review',idempotency_key,{'ref':rid,'payload':x.model_dump()})
            if replay is not None:return replay
            r=one(c,'SELECT * FROM transfer_refusals WHERE id=?',(rid,));require(r,'Rapport inconnu',404)
            t=one(c,'SELECT * FROM transfers WHERE id=?',(r['transfer_id'],));access(u,t['destination'])
            require(r['status']=='pending' and t['status']=='refusal_pending','Rapport déjà traité',409)
            require(r['created_by']!=u['username'],'Validation par une autre personne que l’auteur du rapport',403)
            c.execute('UPDATE transfer_refusals SET reviewed_by=?,reviewed_at=?,review_note=? WHERE id=?',(u['username'],now(),x.note,rid))
            if not x.approve:
                c.execute("UPDATE transfer_refusals SET status='rejected' WHERE id=?",(rid,))
                c.execute("UPDATE transfers SET status='in_transit' WHERE id=?",(t['id'],))
                audit(c,u['username'],'refusal_rejected','transfer',t['id'],{'refusal':rid,'note':x.note})
                notify(c,t['destination'],'transfer',t['id'],'Rapport de refus non validé',x.note[:300],u['username'])
                response={'ok':True,'status':'rejected'}
            else:
                docs=q(c,"SELECT * FROM documents WHERE kind='transfer' AND ref=? ORDER BY uploaded",(t['id'],))
                require(any(Path(d['path']).suffix in ('.png','.jpg') for d in docs),'Au moins une photo est obligatoire avant validation du refus',409)
                c.execute("UPDATE transfer_refusals SET status='validated' WHERE id=?",(rid,))
                c.execute("UPDATE transfers SET status='refused' WHERE id=?",(t['id'],))
                r=one(c,'SELECT * FROM transfer_refusals WHERE id=?',(rid,))
                unit=one(c,'SELECT * FROM units WHERE id=?',(t['unit_id'],));driver=one(c,'SELECT * FROM drivers WHERE id=?',(t['driver_id'],))
                for d in docs:
                    if Path(d['path']).suffix in ('.png','.jpg'):d['content']=store_get(d['path'])
                raw=refusal_report_pdf(r,t,unit,driver,docs)
                did=uid('DOC');path=store_ref(did+'.pdf')
                c.execute('INSERT INTO documents(id,kind,ref,name,mime,sha256,path,uploaded,actor) VALUES(?,?,?,?,?,?,?,?,?)',(did,'transfer',t['id'],f'rapport-refus-{rid}.pdf','application/pdf',hashlib.sha256(raw).hexdigest(),path,now(),u['username']))
                c.execute('UPDATE transfer_refusals SET report_document_id=? WHERE id=?',(did,rid))
                audit(c,u['username'],'refusal_validated','transfer',t['id'],{'refusal':rid,'document':did,'note':x.note})
                for wh in dict.fromkeys((t['source'],t['destination'])):
                    notify(c,wh,'transfer',t['id'],'Refus de transfert validé — exploitation',f"Rapport {rid} validé par {u['username']}. Marchandise bloquée : instruction exploitation requise.",u['username'])
                store_put(path,raw,'application/pdf')
                response={'ok':True,'status':'validated','report_document_id':did}
            save_request(c,u['id'],'transfer.refusal_review',idempotency_key,digest,response)
    except BaseException:
        if path:store_delete(path)
        raise
    return response

# Lot 4 : instruction de l'exploitation après un refus validé (retour ou acceptation sous réserves).
@app.post('/api/transfers/{tid}/refusal-decision')
def refusal_decision(tid:str,x:RefusalDecision,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'exploitation')
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'transfer.refusal_decision',idempotency_key,{'ref':tid,'payload':x.model_dump()})
        if replay is not None:return replay
        t=one(c,'SELECT * FROM transfers WHERE id=?',(tid,));require(t,'Transfert inconnu',404)
        require(t['source'] in u['warehouses'] or t['destination'] in u['warehouses'],'Accès entrepôt refusé',403)
        require(t['status']=='refused','Décision possible uniquement après validation du refus',409)
        unit=one(c,'SELECT * FROM units WHERE id=?',(t['unit_id'],));require(unit and unit['status']=='in_transit','Statut incohérent',409)
        if x.decision=='return':
            back=uid('TRF')
            c.execute('INSERT INTO transfers(id,unit_id,source,destination,status,created,actor,approved_by,return_of) VALUES(?,?,?,?,?,?,?,?,?)',(back,unit['id'],t['destination'],t['source'],'approved',now(),u['username'],u['username'],tid))
            c.execute("UPDATE transfers SET status='returned' WHERE id=?",(tid,))
            c.execute('UPDATE units SET warehouse=?,version=version+1 WHERE id=?',(t['destination'],unit['id']))
            event(c,u['username'],unit['id'],'refusal_return',t['destination'],t['source'],unit['quantity'],back)
            audit(c,u['username'],'refusal_return','transfer',tid,{'return_transfer':back,'note':x.note})
            audit(c,u['username'],'request','transfer',back,{'return_of':tid})
            for wh in dict.fromkeys((t['destination'],t['source'])):
                notify(c,wh,'transfer',back,'Retour après refus à expédier',f"Retour {t['destination']} → {t['source']} décidé par {u['username']} : nouvelle signature transporteur requise.",u['username'])
            response={'ok':True,'decision':'return','return_transfer_id':back}
        else:
            c.execute("UPDATE transfers SET status='received_with_reserves',received_by=?,received_at=?,received_quantity=?,received_condition='acceptation_sous_reserves',received_note=? WHERE id=?",(u['username'],now(),unit['quantity'],x.note,tid))
            c.execute("UPDATE units SET warehouse=?,status='awaiting_putaway',location_id=NULL,version=version+1 WHERE id=?",(t['destination'],unit['id']))
            event(c,u['username'],unit['id'],'transfer_receive',t['source'],t['destination'],unit['quantity'],tid)
            audit(c,u['username'],'accept_with_reserves','transfer',tid,{'note':x.note})
            for wh in dict.fromkeys((t['destination'],t['source'])):
                notify(c,wh,'transfer',tid,'Transfert accepté sous réserves',x.note[:300],u['username'])
            response={'ok':True,'decision':'accept_with_reserves'}
        save_request(c,u['id'],'transfer.refusal_decision',idempotency_key,digest,response)
    return response

@app.get('/api/counts')
def counts(u=Depends(auth)):
    with db() as c:return q(c,'SELECT * FROM counts WHERE warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY created DESC',u['warehouses'])
@app.post('/api/counts')
def create_count(x:CountCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        replay,digest=replay_request(c,u['id'],'inventory.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        unit=unit_access(c,u,x.unit_id);require(unit['status']=='available' and unit['quantity']>0,'Unité indisponible');require(unit['location_id'],'Unité sans emplacement')
        require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Comptage en attente',409)
        require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),'Transfert actif',409)
        require(not one(c,"SELECT id FROM releases WHERE unit_id=? AND status IN ('requested','authorized')",(unit['id'],)),'Sortie active',409)
        i=uid('INV');c.execute('INSERT INTO counts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,unit['warehouse'],unit['location_id'],unit['id'],unit['quantity'],x.observed,'pending',u['username'],now(),None,x.reason))
        audit(c,u['username'],'count','unit',unit['id'],{'observed':x.observed});save_request(c,u['id'],'inventory.create',idempotency_key,digest,{'id':i});c.commit()
    return {'id':i}
# --- Lot 12 : campagnes d'inventaire -------------------------------------------------
def _campaign(c,u,cid):
    k=one(c,'SELECT * FROM inventory_campaigns WHERE id=?',(cid,));require(k,'Campagne inconnue',404);access(u,k['warehouse']);return k
def _campaign_view(c,k):
    items=q(c,'SELECT i.*,u.unit_type,u.unit_index,u.unit_count,u.description,c2.status count_status FROM campaign_items i JOIN units u ON u.id=i.unit_id LEFT JOIN counts c2 ON c2.id=i.count_id WHERE i.campaign_id=? ORDER BY i.location_id,i.unit_id',(k['id'],))
    k['items']=items
    k['progress']={'total':len(items),'counted':sum(1 for i in items if i['result']),'discrepancies':sum(1 for i in items if i['result']=='ecart')}
    return k

@app.post('/api/inventory-campaigns')
def create_campaign(x:CampaignCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'exploitation','manager','admin');warehouse(x.warehouse);access(u,x.warehouse)
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'campaign.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        a=one(c,'SELECT * FROM users WHERE lower(username)=? AND active=1 AND deleted_at IS NULL',(x.assignee.strip().lower(),))
        require(a and x.warehouse in json.loads(a['warehouses']),'Collaborateur inconnu ou non habilité pour cet entrepôt')
        cond,args="u.warehouse=? AND u.status='available' AND u.quantity>0 AND u.location_id IS NOT NULL",[x.warehouse]
        if x.scope=='location':
            require(x.value,'Emplacement à préciser');cond+=' AND u.location_id=?';args.append(x.value)
        elif x.scope=='rack':
            require(x.value,'Rack à préciser');cond+=' AND u.location_id LIKE ?';args.append(x.value.replace('%','')+'-%')
        units=q(c,f'SELECT u.id,u.location_id,u.quantity FROM units u WHERE {cond} ORDER BY u.location_id,u.id',tuple(args))
        require(units,'Aucune unité rangée dans ce périmètre')
        busy=one(c,f"SELECT i.unit_id FROM campaign_items i JOIN inventory_campaigns k ON k.id=i.campaign_id WHERE k.status='open' AND i.unit_id IN ({','.join('?' for _ in units)})",tuple(x['id'] for x in units))
        require(not busy,f"Unité {busy['unit_id'] if busy else ''} déjà dans une campagne ouverte",409)
        cid=uid('CAMP')
        c.execute('INSERT INTO inventory_campaigns(id,warehouse,scope,scope_value,title,assignee,status,created_by,created) VALUES(?,?,?,?,?,?,?,?,?)',(cid,x.warehouse,x.scope,x.value,x.title,a['username'],'open',u['username'],now()))
        for un in units:c.execute('INSERT INTO campaign_items(campaign_id,unit_id,location_id,expected) VALUES(?,?,?,?)',(cid,un['id'],un['location_id'],un['quantity']))
        audit(c,u['username'],'campaign_create','campaign',cid,{'scope':x.scope,'value':x.value,'units':len(units),'assignee':a['username']})
        notify(c,x.warehouse,'campaign',cid,'Inventaire à réaliser',f"{x.title} : {len(units)} unité(s) à compter par {a['username']}.",u['username'])
        response={'id':cid,'units':len(units)};save_request(c,u['id'],'campaign.create',idempotency_key,digest,response)
    return response

@app.get('/api/inventory-campaigns')
def campaigns(u=Depends(auth)):
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:
        return [_campaign_view(c,k) for k in q(c,f'SELECT * FROM inventory_campaigns WHERE warehouse IN ({marks}) ORDER BY created DESC LIMIT 100',u['warehouses'])]

@app.post('/api/inventory-campaigns/{cid}/count')
def campaign_count(cid:str,x:CampaignCount,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'worker','leader','manager','exploitation','admin')
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'campaign.count',idempotency_key,{'ref':cid,'payload':x.model_dump()})
        if replay is not None:return replay
        k=_campaign(c,u,cid);require(k['status']=='open','Campagne clôturée',409)
        require(u['username']==k['assignee'] or u['role'] in ('superadmin','admin','manager','leader'),'Campagne affectée à un autre collaborateur',403)
        item=one(c,'SELECT * FROM campaign_items WHERE campaign_id=? AND unit_id=?',(cid,x.unit_id));require(item,'Unité hors de cette campagne',404)
        require(not item['result'],'Unité déjà comptée',409)
        unit=one(c,'SELECT * FROM units WHERE id=?',(x.unit_id,))
        if x.observed==unit['quantity']:
            # Conforme : aucun mouvement de stock, comptage enregistré et approuvé.
            i=uid('INV');c.execute('INSERT INTO counts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,unit['warehouse'],unit['location_id'],unit['id'],unit['quantity'],x.observed,'approved',u['username'],now(),'conforme',f'Campagne {cid}'))
            result='conforme'
        else:
            require(unit['status']=='available' and unit['location_id'],'Unité indisponible pour un comptage')
            require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Comptage en attente',409)
            # Écart : comptage en attente, recomptage et validation indépendants obligatoires.
            i=uid('INV');c.execute('INSERT INTO counts VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,unit['warehouse'],unit['location_id'],unit['id'],unit['quantity'],x.observed,'pending',u['username'],now(),None,f'Campagne {cid}'))
            result='ecart'
            notify(c,k['warehouse'],'count',i,'Écart d’inventaire',f"{k['title']} : {unit['id']} {x.observed} compté(s) pour {unit['quantity']} attendu(s). Recomptage requis.",u['username'])
        c.execute('UPDATE campaign_items SET observed=?,result=?,count_id=?,counted_by=?,counted_at=? WHERE campaign_id=? AND unit_id=?',(x.observed,result,i,u['username'],now(),cid,x.unit_id))
        audit(c,u['username'],'campaign_count','campaign',cid,{'unit':x.unit_id,'expected':unit['quantity'],'observed':x.observed,'result':result})
        response={'ok':True,'result':result,'count_id':i};save_request(c,u['id'],'campaign.count',idempotency_key,digest,response)
    return response

@app.post('/api/inventory-campaigns/{cid}/close')
def close_campaign(cid:str,x:CampaignNote,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with tx() as c:
        k=_campaign(c,u,cid);require(k['status']=='open','Campagne déjà clôturée',409)
        require(not one(c,'SELECT unit_id FROM campaign_items WHERE campaign_id=? AND result IS NULL',(cid,)),'Toutes les unités doivent être comptées',409)
        require(not one(c,"SELECT i.unit_id FROM campaign_items i JOIN counts n ON n.id=i.count_id WHERE i.campaign_id=? AND n.status='pending'",(cid,)),'Écarts en attente de recomptage ou de validation',409)
        c.execute("UPDATE inventory_campaigns SET status='closed',closed_by=?,closed_at=?,close_note=? WHERE id=?",(u['username'],now(),x.note,cid))
        audit(c,u['username'],'campaign_close','campaign',cid,{'note':x.note})
    return {'ok':True}

@app.post('/api/inventory-campaigns/{cid}/cancel')
def cancel_campaign(cid:str,x:CampaignNote,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with tx() as c:
        k=_campaign(c,u,cid);require(k['status']=='open','Campagne déjà clôturée',409)
        c.execute("UPDATE inventory_campaigns SET status='cancelled',closed_by=?,closed_at=?,close_note=? WHERE id=?",(u['username'],now(),x.note,cid))
        audit(c,u['username'],'campaign_cancel','campaign',cid,{'note':x.note})
    return {'ok':True}

@app.get('/api/inventory-campaigns/{cid}/report')
def campaign_report(cid:str,u=Depends(auth)):
    with db() as c:
        k=_campaign_view(c,_campaign(c,u,cid))
        for i in k['items']:
            n=one(c,'SELECT n.*,r.observed recount FROM counts n LEFT JOIN recounts r ON r.count_id=n.id WHERE n.id=?',(i['count_id'],)) if i['count_id'] else None
            i['decision']=None if not n else ({'approved':'Validé','rejected':'Rejeté','pending':'En attente'}.get(n['status'],n['status'])+(f" par {n['reviewer']}" if n['reviewer'] and n['reviewer']!='conforme' else ''))
            i['recount']=n['recount'] if n else None
    from app.pdf_report import campaign_report as render
    raw=render(k,now())
    return Response(content=raw,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="inventaire-{cid}.pdf"'})

@app.post('/api/counts/{cid}/review')
def review_count(cid:str,x:CountReview,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'manager','exploitation','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');replay,digest=replay_request(c,u['id'],'inventory.review',idempotency_key,{'ref':cid,'payload':x.model_dump()});
        if replay is not None:return replay
        count=one(c,'SELECT * FROM counts WHERE id=?',(cid,));require(count,'Comptage introuvable',404);access(u,count['warehouse']);require(count['status']=='pending','Déjà traité')
        require(count['actor']!=u['username'],'Relecture indépendante obligatoire',403)
        unit=one(c,'SELECT * FROM units WHERE id=?',(count['unit_id'],));require(unit['quantity']==count['expected'] and unit['location_id']==count['location_id'],'Stock modifié depuis le comptage',409)
        if x.approve:
            if count['expected']!=count['observed']:
                recount=one(c,'SELECT * FROM recounts WHERE count_id=?',(cid,))
                require(recount,'Recomptage indépendant obligatoire avant correction',409)
                require(recount['observed']==count['observed'],'Recomptage contradictoire : rejeter et ouvrir un nouveau comptage',409)
                require(recount['actor']!=u['username'],'Validation par un troisième intervenant obligatoire',403)
            require(bool(x.reason.strip()) if count['expected']!=count['observed'] else True,'Justification de correction obligatoire')
            new_weight=round(unit['weight']*count['observed']/count['expected'],3) if count['expected'] else unit['weight']
            c.execute("UPDATE units SET quantity=?,weight=?,status=CASE WHEN ?=0 THEN 'depleted' ELSE 'available' END,version=version+1 WHERE id=?",(count['observed'],new_weight,count['observed'],unit['id']))
            if new_weight!=unit['weight']:audit(c,u['username'],'weight_update','unit',unit['id'],{'count':cid,'weight_before':unit['weight'],'weight_after':new_weight,'method':'proportionnel'})
            event(c,u['username'],unit['id'],'inventory_adjustment',unit['location_id'],unit['location_id'],count['observed']-count['expected'],cid)
        c.execute('UPDATE counts SET status=?,reviewer=?,reason=? WHERE id=?',('approved' if x.approve else 'rejected',u['username'],x.reason,cid))
        audit(c,u['username'],'review','count',cid,{'approved':x.approve});save_request(c,u['id'],'inventory.review',idempotency_key,digest,{'ok':True});c.commit()
    return {'ok':True}
@app.post('/api/counts/{cid}/recount')
def recount_count(cid:str,x:RecountCreate,u=Depends(auth)):
    role(u,'worker','leader','manager','exploitation','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        count=one(c,'SELECT * FROM counts WHERE id=?',(cid,))
        require(count,'Comptage introuvable',404);access(u,count['warehouse'])
        require(count['status']=='pending','Comptage déjà traité',409)
        require(count['actor']!=u['username'],'Recomptage indépendant obligatoire',403)
        require(not one(c,'SELECT id FROM recounts WHERE count_id=?',(cid,)),'Recomptage déjà enregistré',409)
        i=uid('RECNT')
        c.execute('INSERT INTO recounts VALUES(?,?,?,?,?)',(i,cid,x.observed,u['username'],now()))
        audit(c,u['username'],'recount','count',cid,{'observed':x.observed})
        if x.observed!=count['observed']:
            notify(c,count['warehouse'],'count',cid,'Écart de recomptage','Comptages divergents : correction bloquée.',u['username'])
        c.commit()
    return {'id':i,'matches':x.observed==count['observed']}

@app.get('/api/recounts')
def recounts(u=Depends(auth)):
    with db() as c:
        return q(c,'SELECT r.* FROM recounts r JOIN counts c ON c.id=r.count_id WHERE c.warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY r.created DESC',u['warehouses'])

@app.get('/api/discrepancies')  # adresse utilisée par l'écran « Écarts de réception » depuis la V3.4
@app.get('/api/receipt-discrepancies')
def receipt_discrepancies(u=Depends(auth)):
    with db() as c:
        return q(c,'SELECT * FROM receipt_discrepancies WHERE warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY created DESC',u['warehouses'])

@app.post('/api/receipts/{rid}/discrepancy')
def report_discrepancy(rid:str,x:DiscrepancyCreate,u=Depends(auth)):
    require(x.kind in ('missing','excess','damage','documentation','other'),'Catégorie invalide')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,))
        require(r,'Réception introuvable',404);access(u,r['warehouse'])
        i=uid('ECART')
        c.execute('INSERT INTO receipt_discrepancies(id,receipt_id,warehouse,kind,expected,observed,description,status,created,reported_by) VALUES(?,?,?,?,?,?,?,?,?,?)',(i,rid,r['warehouse'],x.kind,r['expected'],r['actual'],x.description,'open',now(),u['username']))
        c.execute("UPDATE receipts SET status='discrepancy' WHERE id=?",(rid,))
        for held in q(c,"SELECT id FROM units WHERE receipt_id=? AND status NOT IN ('exited','depleted')",(rid,)):
            add_hold(c,u['username'],held['id'],'ecart_reception','Écart réception '+i,i)
        audit(c,u['username'],'report_discrepancy','receipt',rid,{'discrepancy_id':i,'kind':x.kind})
        notify(c,r['warehouse'],'receipt',rid,'Écart de réception','Contrôle exploitation obligatoire.',u['username'])
        queue_receipt_mail(c,rid,r['warehouse'],'discrepancy',u['username'])
        c.commit()
    return {'id':i,'status':'open'}

@app.post('/api/receipt-discrepancies/{did}/review')
def review_discrepancy(did:str,x:DiscrepancyReview,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        d=one(c,'SELECT * FROM receipt_discrepancies WHERE id=?',(did,))
        require(d,'Écart introuvable',404);access(u,d['warehouse'])
        require(d['status']=='open','Écart déjà traité',409)
        require(d['reported_by']!=u['username'],'Validation indépendante obligatoire',403)
        status='accepted' if x.approve else 'rejected'
        c.execute('UPDATE receipt_discrepancies SET status=?,reviewed_by=?,reviewed_at=?,decision=? WHERE id=?',(status,u['username'],now(),x.decision,did))
        audit(c,u['username'],'review_discrepancy','receipt',d['receipt_id'],{'id':did,'status':status,'decision':x.decision})
        notify(c,d['warehouse'],'receipt',d['receipt_id'],'Écart de réception traité',f'Décision : {status}. Le blocage reste en place jusqu’à levée autorisée.',u['username'])
        c.commit()
    return {'ok':True,'status':status,'hold_remains':True}

@app.get('/api/drivers')
def drivers(u=Depends(auth)):
    office=u['role'] in IDENTITY_ROLES
    with db() as c:
        rows=q(c,"SELECT d.id,d.name,d.company,d.plate,d.created,d.id_type,d.id_number,d.identity_erased_at,CASE WHEN EXISTS (SELECT 1 FROM documents x WHERE x.kind='driver' AND x.ref=d.id) THEN 1 ELSE 0 END has_identity FROM drivers d ORDER BY d.created DESC")
        for r in rows:
            if office and (r['has_identity'] or r.get('id_number')):
                r['last_seen']=driver_last_seen(c,r['id']);r['erase_on']=erase_date(r['last_seen'])
    for r in rows:
        if not office:r.pop('id_number',None)
    return rows
@app.post('/api/drivers')
def create_driver(x:DriverCreate,u=Depends(auth)):
    role(u,'worker','leader','manager','exploitation','admin')
    require(bool(x.name.strip()),'Nom du transporteur obligatoire')
    with tx() as c:
        i=uid('DRV');c.execute('INSERT INTO drivers(id,name,company,plate,phone,created,id_type,id_number) VALUES(?,?,?,?,?,?,?,?)',(i,x.name.strip(),x.company,x.plate.strip().upper(),x.phone,now(),x.id_type,x.id_number.strip()));audit(c,u['username'],'create','driver',i)
    return {'id':i}

# --- Lot 14 : pièces d'identité (notice, conservation 1 an) ---------------------------------------
PRIVACY_CONTACT=os.getenv('TAF_PRIVACY_CONTACT','christophe@taftrans.fr')
IDENTITY_RETENTION_DAYS=int(os.getenv('TAF_IDENTITY_RETENTION_DAYS','365'))
ID_LABELS={'CNI':'CNI','passeport':'Passeport','permis':'Permis de conduire','titre_sejour':'Titre de séjour','autre':'Autre pièce'}
def driver_last_seen(c,driver_id):
    """Dernier passage : création, remise signée, sortie, refus, transfert ou nouvelle photo de pièce."""
    d=one(c,'SELECT created FROM drivers WHERE id=?',(driver_id,));seen=[d['created']] if d else []
    for sql in ('SELECT MAX(signed_at) v FROM release_handovers WHERE driver_id=?',"SELECT MAX(completed) v FROM releases WHERE driver_id=? AND status='completed'",
                'SELECT MAX(created) v FROM release_refusals WHERE driver_id=?','SELECT MAX(dispatched_at) v FROM transfers WHERE driver_id=?',
                "SELECT MAX(uploaded) v FROM documents WHERE kind='driver' AND ref=?"):
        v=one(c,sql,(driver_id,))['v']
        if v:seen.append(v)
    return max(seen) if seen else None
def erase_date(last_seen):
    return (datetime.fromisoformat(last_seen)+timedelta(days=IDENTITY_RETENTION_DAYS)).isoformat(timespec='seconds') if last_seen else None
def purge_identities(actor='system'):
    """Efface photo, type et numéro de pièce des chauffeurs dont le dernier passage date de plus d'un an."""
    cutoff=(datetime.now(timezone.utc)-timedelta(days=IDENTITY_RETENTION_DAYS)).isoformat(timespec='seconds')
    with db() as c:
        candidates=[r['id'] for r in q(c,"SELECT d.id FROM drivers d WHERE COALESCE(d.id_number,'')!='' OR COALESCE(d.id_type,'')!='' OR EXISTS (SELECT 1 FROM documents x WHERE x.kind='driver' AND x.ref=d.id)")]
    purged=[]
    for did in candidates:
        with tx() as c:
            last=driver_last_seen(c,did)
            if last and last>=cutoff:continue
            docs=q(c,"SELECT id,path FROM documents WHERE kind='driver' AND ref=?",(did,))
            for d in docs:store_erase(d['path'])   # fichiers d'abord : un échec annule la transaction
            c.execute("DELETE FROM documents WHERE kind='driver' AND ref=?",(did,))
            c.execute("UPDATE drivers SET id_type=NULL,id_number='',identity_erased_at=? WHERE id=?",(now(),did))
            audit(c,actor,'purge_identity','driver',did,{'documents':len(docs),'last_seen':last,'retention_days':IDENTITY_RETENTION_DAYS})
        purged.append(did)
    return purged

def _notice_response(driver,ref,name):
    from app.pdf_report import driver_notice
    pdf=driver_notice(driver,PRIVACY_CONTACT,now(),ref)
    return Response(content=pdf,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="{name}"'})
@app.get('/api/drivers/notice')
def blank_driver_notice(u=Depends(auth)):
    """Notice vierge à imprimer et remettre au transporteur (français et anglais)."""
    return _notice_response(None,'NOTICE-SURETE','notice-transporteur.pdf')
@app.get('/api/drivers/{did}/notice')
def driver_notice_pdf(did:str,u=Depends(auth)):
    office=u['role'] in IDENTITY_ROLES
    with db() as c:
        d=one(c,'SELECT * FROM drivers WHERE id=?',(did,));require(d,'Chauffeur introuvable',404)
        last=driver_last_seen(c,did)
        has_photo=bool(one(c,"SELECT id FROM documents WHERE kind='driver' AND ref=? LIMIT 1",(did,)))
        audit(c,u['username'],'notice','driver',did)
    if d.get('identity_erased_at'):label='Effacée le '+d['identity_erased_at'][:10]
    else:
        label=ID_LABELS.get(d.get('id_type') or '','Non renseignée')
        if office and d.get('id_number'):label+=' n° ••••'+d['id_number'][-4:]
        if has_photo:label+=' · photo enregistrée'
    info={**d,'id_label':label,'last_seen':last,'erase_on':erase_date(last) if not d.get('identity_erased_at') else None}
    return _notice_response(info,did,f'notice-{did}.pdf')
@app.post('/api/admin/purge-identities')
def purge_identities_now(u=Depends(auth)):
    role(u,'superadmin')
    purged=purge_identities(u['username'])
    return {'purged':purged,'retention_days':IDENTITY_RETENTION_DAYS}

# --- Lot 14 : fiche de réception et envoi par e-mail -------------------------------------------------
MAIL_BACKEND=os.getenv('TAF_MAIL_BACKEND','off')      # off | ses | memory (tests)
MAIL_FROM=os.getenv('TAF_MAIL_FROM','')
PUBLIC_URL=os.getenv('TAF_PUBLIC_URL','').rstrip('/')  # adresse de l'application, pour les liens des e-mails
MAIL_DELAY=int(os.getenv('TAF_MAIL_DELAY_SECONDS','180'))  # laisse le temps d'ajouter les photos
MAIL_MAX_ATTEMPTS=5
MAIL_SENT=[]
EMAIL_RE=re.compile(r'^[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}$')
def mail_recipients(c,wh):
    r=one(c,'SELECT recipients FROM mail_routes WHERE warehouse=?',(wh,))
    return json.loads(r['recipients']) if r else []
def queue_receipt_mail(c,rec_id,wh,reason,actor,delay=None):
    """Programme l'envoi de la fiche ; un envoi déjà en attente pour la même réception est regroupé."""
    if MAIL_BACKEND=='off' or not mail_recipients(c,wh):return None
    at=(datetime.now(timezone.utc)+timedelta(seconds=MAIL_DELAY if delay is None else delay)).isoformat(timespec='seconds')
    pending=one(c,"SELECT id,not_before FROM mail_outbox WHERE kind='receipt' AND ref=? AND status='pending'",(rec_id,))
    if pending:
        c.execute('UPDATE mail_outbox SET reason=?,not_before=? WHERE id=?',(reason,min(at,pending['not_before']),pending['id']));return pending['id']
    i=uid('MAIL')
    c.execute("INSERT INTO mail_outbox(id,kind,ref,warehouse,reason,status,created,created_by,not_before) VALUES(?,?,?,?,?,'pending',?,?,?)",(i,'receipt',rec_id,wh,reason,now(),actor,at))
    return i
def receipt_problems(c,rec,units):
    p=[]
    if rec['expected']!=rec['actual']:p.append(f"Colis reçus ({rec['actual']}) différents des colis attendus ({rec['expected']})")
    described=sum(u['quantity'] for u in units if u.get('unit_index'));weighed=sum(u['weight'] or 0 for u in units)
    if units and any(u.get('unit_index') for u in units) and described!=rec['actual']:p.append(f"Colis décrits au colisage ({described}) différents des colis reçus ({rec['actual']})")
    if units and rec.get('weight') and abs(weighed-rec['weight'])>max(1,0.05*rec['weight']):p.append(f"Écart de poids : {round(weighed,1)} kg pesés pour {round(rec['weight'],1)} kg déclarés")
    if rec.get('apparent_condition')=='endommage':p.append('État apparent : marchandise endommagée')
    elif rec.get('apparent_condition')=='a_verifier':p.append('État apparent : à vérifier')
    if rec.get('security_status')=='non_securise':p.append('Sûreté : marchandise non sécurisée')
    elif rec.get('security_status')=='a_controler':p.append('Sûreté : marchandise à contrôler')
    kinds={'missing':'Colis manquants','excess':'Excédent','damage':'Avarie','documentation':'Documents','other':'Autre'}
    for d in q(c,"SELECT * FROM receipt_discrepancies WHERE receipt_id=? AND status!='rejected' ORDER BY created",(rec['id'],)):
        p.append(f"Écart déclaré {d['id']} ({kinds.get(d['kind'],d['kind'])}) : {d['description']}")
    if rec['status']=='discrepancy' and not p:p.append('Écart de réception signalé')
    return p
def receipt_dossier(c,rid):
    rec=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(rid,));require(rec,'Réception introuvable',404)
    units=q(c,'SELECT * FROM units WHERE receipt_id=? ORDER BY unit_index,id',(rid,))
    discrepancies=q(c,'SELECT * FROM receipt_discrepancies WHERE receipt_id=? ORDER BY created',(rid,))
    holds=q(c,'SELECT h.unit_id,h.reason FROM unit_holds h JOIN units x ON x.id=h.unit_id WHERE x.receipt_id=? AND h.lifted_at IS NULL ORDER BY h.created',(rid,))
    docs=q(c,"SELECT * FROM documents WHERE kind='receipt' AND ref=? ORDER BY uploaded",(rid,))
    who=one(c,"SELECT actor FROM audit WHERE action='receive' AND kind='receipt' AND ref=? ORDER BY at LIMIT 1",(rid,))
    rec['history']=receipt_history(c,rid);rec['missing']=receipt_missing(c,rid) if rec.get('stage')!='validated' else []
    return rec,units,discrepancies,holds,docs,(who or {}).get('actor'),receipt_problems(c,rec,units)
PARIS=None
def paris(iso):
    """Date et heure locales (Paris) d'un horodatage UTC."""
    global PARIS
    if PARIS is None:
        from zoneinfo import ZoneInfo
        PARIS=ZoneInfo('Europe/Paris')
    d=datetime.fromisoformat(iso)
    return d.astimezone(PARIS)
def _wrap(text,width):
    words=(text or '').split();lines=[];cur=''
    for w_ in words:
        if len(cur)+len(w_)+1>width and cur:lines.append(cur);cur=w_
        else:cur=(cur+' '+w_).strip()
    if cur:lines.append(cur)
    return lines
def _n(v,d=0):
    if v is None:return ''
    s_=f'{v:.{d}f}'.replace('.',',')
    return s_[:-2] if d and s_.endswith(',0') else s_
def bordereau_values(c,rid):
    """Valeurs du bordereau de réception DGAC (Regulated Agent, v2.5), à partir de la fiche validée."""
    r=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(rid,))
    units=q(c,'SELECT * FROM units WHERE receipt_id=? ORDER BY unit_index,id',(rid,))
    drv=one(c,'SELECT * FROM drivers WHERE id=?',(r['driver_id'],)) if r.get('driver_id') else None
    who=one(c,"SELECT actor FROM audit WHERE action='receive' AND kind='receipt' AND ref=? ORDER BY at LIMIT 1",(rid,))
    disc=q(c,"SELECT kind,description FROM receipt_discrepancies WHERE receipt_id=? AND status!='rejected' ORDER BY created",(rid,))
    when=paris(r['created'])
    cond=r.get('apparent_condition') or 'conforme'
    comment=[]
    if cond!='conforme':comment.append({'endommage':'Emballage endommagé','a_verifier':'Emballage à vérifier'}[cond])
    comment+=[d['description'] for d in disc if d['kind'] in ('damage','other')]
    comment_lines=_wrap(' ; '.join(comment),60)
    if len(comment_lines)>1:comment_lines=[comment_lines[0],' '.join(comment_lines[1:])]
    reason=_wrap(r.get('refusal_reason') or '',22) if not r.get('accepted',1) else []
    count=lambda k:sum(1 for x_ in units if x_.get('unit_type')==k)
    marks=' · '.join(x_ for x_ in (('LTA '+r['awb']) if r.get('awb') else '',('Réf. '+r['transport_ref']) if r.get('transport_ref') else '',f'Entrée {rid}') if x_)
    rows=[]
    for x_ in units:
        L,W_,H_=x_.get('length_cm'),x_.get('width_cm'),x_.get('height_cm')
        vol=L*W_*H_/6000 if (L and W_ and H_) else None
        rows.append((_n(L),_n(W_),_n(H_),_n(x_.get('weight'),1)+' kg' if x_.get('weight') is not None else '',_n(vol,1)+' kg' if vol else ''))
    id_type={'CNI':'CNI','titre_sejour':'CNI','permis':'permis','passeport':'passeport'}.get((drv or {}).get('id_type') or '')
    return {'reference':rid,'shipper':r.get('shipper'),'shipper2':r.get('shipper_address'),
            'consignee':r.get('consignee') or r['client'],'consignee2':r.get('consignee_address'),
            'driver_name':(drv or {}).get('name'),'driver_company':(drv or {}).get('company'),'id_type':id_type,
            'id_number':((drv or {}).get('id_number') or ('(effacé — conservation 1 an)' if (drv or {}).get('identity_erased_at') else '')),
            'nature_lines':_wrap(r.get('nature') or '',48)[:2],'marking_lines':[marks]+_wrap(r.get('notes') or '',48)[:1],
            'packages':(r.get('expected'),r.get('actual')),'drums':(r.get('drums_expected'),count('fut')),'pallets':(r.get('pallets_expected'),count('palette')),
            'packaging_ok':cond=='conforme','packaging_comment_lines':comment_lines,
            'accepted':bool(r.get('accepted',1)),'refusal_reason':reason[0] if reason else '','refusal_reason2':' '.join(reason[1:]),
            'agent':((who or {}).get('actor') or '').split('@')[0].replace('.',' ').title(),
            'date':when.strftime('%d/%m/%Y'),'time':when.strftime('%H:%M'),'rows':rows}
def receipt_pdf(c,rid):
    from app.pdf_report import receipt_report,bordereau_reception
    rec,units,disc,holds,docs,who,problems=receipt_dossier(c,rid)
    if rec.get('stage')=='validated':
        # Fiche validée : bordereau officiel DGAC, à l'identique du modèle.
        return rec,problems,who,bordereau_reception(bordereau_values(c,rid))
    for d in docs:
        if Path(d['path']).suffix in ('.png','.jpg'):d['content']=store_get(d['path'])
    return rec,problems,who,receipt_report(rec,units,disc,holds,problems,docs,who,now())
@app.get('/api/receipts/{rid}/report')
def receipt_report_pdf(rid:str,u=Depends(auth)):
    with db() as c:
        r=one(c,'SELECT warehouse FROM receipts WHERE id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        _,_,_,pdf=receipt_pdf(c,rid)
    return Response(content=pdf,media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="bordereau-reception-{rid}.pdf"'})
@app.post('/api/receipts/{rid}/email')
def receipt_email_now(rid:str,background:BackgroundTasks,u=Depends(auth)):
    role(u,'leader','manager','exploitation','admin')
    require(MAIL_BACKEND!='off','Envoi d’e-mails non activé sur ce serveur',409)
    with tx() as c:
        r=one(c,'SELECT warehouse FROM receipts WHERE id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        require(mail_recipients(c,r['warehouse']),'Aucun destinataire configuré pour cet entrepôt',409)
        mid=queue_receipt_mail(c,rid,r['warehouse'],'manual',u['username'],delay=0)
        audit(c,u['username'],'mail_request','receipt',rid,{'outbox':mid})
    background.add_task(process_mail_outbox)
    return {'id':mid,'status':'pending'}
def compose_receipt_mail(c,rid):
    rec,problems,who,pdf=receipt_pdf(c,rid)
    title=('PROBLÈME DE RÉCEPTION' if problems else 'Réception conforme')+(' (fiche modifiée)' if (rec.get('revision') or 0)>1 else '')
    subject=f"[TAF WAREHOUSE] {title} · {rec['warehouse']} · LTA {rec.get('awb') or '—'} · {rec['client']} · {rec['id']}"
    lines=[f"Réception {rec['id']} — entrepôt {rec['warehouse']}, le {rec['created'][:10]} à {rec['created'][11:16]} UTC",
           f"Client : {rec['client']}",f"LTA : {rec.get('awb') or '—'}",f"Colis : {rec['actual']} reçus / {rec['expected']} prévus — poids déclaré {rec.get('weight') or 0} kg",
           f"Réceptionné par : {who or '—'}"]
    if problems:body=lines+['','PROBLÈMES CONSTATÉS :']+['- '+p for p in problems]+['','La marchandise concernée reste bloquée jusqu’à sa levée par une personne habilitée.']
    else:body=lines+['','Réception conforme : quantités, poids, état apparent et sûreté sans réserve.']
    from urllib.parse import quote
    docs=q(c,"SELECT id,name,category FROM documents WHERE kind='receipt' AND ref=? ORDER BY uploaded",(rid,))
    cat={'transport':'document de transport','photo':'photo'}
    dossier=f"{PUBLIC_URL}/#entree={quote(rid)}" if PUBLIC_URL else ''
    links=[(f"{d['name']} ({cat.get(d['category'],'document')})",f"{dossier}&doc={quote(d['id'])}" if dossier else '') for d in docs]
    doc_txt=(['','Documents de l’expédition (connexion TAF WAREHOUSE requise) :']+([f'- Dossier complet : {dossier}'] if dossier else [])+[f'- {n} : {u}' if u else f'- {n}' for n,u in links]) if (docs or dossier) else []
    text='Bonjour,\n\n'+'\n'.join(body+doc_txt)+'\n\nLe bordereau de réception (PDF) est joint à ce message.\n\nTAF WAREHOUSE — message automatique, merci de ne pas répondre.\n'
    from html import escape as h
    doc_html=(f'<p style="margin:14px 0 6px;font-weight:bold">Documents de l’expédition</p>'
              +(f'<p style="margin:0 0 8px"><a href="{h(dossier)}" style="display:inline-block;background:#1F6FA8;color:#fff;padding:10px 16px;border-radius:8px;text-decoration:none;font-weight:bold">Ouvrir le dossier {h(rid)}</a></p>' if dossier else '')
              +'<ul style="margin:0">'+''.join(f'<li>{f"<a href={chr(34)}{h(u)}{chr(34)}>{h(n)}</a>" if u else h(n)}</li>' for n,u in links)+'</ul>'
              +'<p style="color:#5B6B7A;font-size:12px;margin:6px 0 0">Liens sécurisés : connexion TAF WAREHOUSE requise.</p>') if (docs or dossier) else ''
    color='#B42318' if problems else '#1E7A46'
    items=''.join(f'<li>{h(p)}</li>' for p in problems)
    html=(f'<div style="font-family:Arial,Helvetica,sans-serif;color:#1B2733;max-width:640px">'
          f'<div style="background:#0F2B47;color:#fff;padding:14px 18px"><b style="font-size:18px">TAF</b> <span style="font-size:11px;letter-spacing:2px">WAREHOUSE</span></div>'
          f'<div style="background:{color};color:#fff;padding:9px 18px;font-weight:bold">{h(title.upper())}</div><div style="padding:14px 18px;line-height:1.55">'
          +'<br>'.join(h(x) for x in lines)
          +(f'<p style="color:#B42318;font-weight:bold;margin:14px 0 4px">Problèmes constatés</p><ul style="margin:0">{items}</ul><p>La marchandise concernée reste bloquée jusqu’à sa levée par une personne habilitée.</p>' if problems else '<p>Réception conforme : quantités, poids, état apparent et sûreté sans réserve.</p>')
          +doc_html+'<p>Le bordereau de réception (PDF) est joint à ce message.</p></div>'
          '<div style="color:#5B6B7A;font-size:11px;padding:0 18px 14px">TAF WAREHOUSE — message automatique, merci de ne pas répondre.</div></div>')
    return subject,text,html,[((f"bordereau-reception-{rec['id']}.pdf" if rec.get('stage')=='validated' else f"fiche-reception-{rec['id']}.pdf"),pdf,'application/pdf')]
def send_mail(to,subject,text,html,attachments):
    from email.message import EmailMessage
    from email.utils import formataddr
    msg=EmailMessage();msg['From']=formataddr(('TAF WAREHOUSE',MAIL_FROM or 'noreply@localhost'));msg['To']=', '.join(to);msg['Subject']=subject
    msg.set_content(text);msg.add_alternative(html,subtype='html')
    for name,data,mime in attachments:
        main,sub=mime.split('/');msg.add_attachment(data,maintype=main,subtype=sub,filename=name)
    if MAIL_BACKEND=='memory':
        MAIL_SENT.append({'to':list(to),'subject':subject,'text':text,'attachments':[(n,d) for n,d,_ in attachments]});return 'memory-'+uuid.uuid4().hex[:8]
    if MAIL_BACKEND=='ses':
        require(MAIL_FROM,'TAF_MAIL_FROM manquant',500)
        import boto3
        r=boto3.client('sesv2',region_name=_aws_region()).send_email(FromEmailAddress=MAIL_FROM,Destination={'ToAddresses':list(to)},Content={'Raw':{'Data':msg.as_bytes()}})
        return r['MessageId']
    raise RuntimeError('Envoi d’e-mails désactivé')
_mail_lock=threading.Lock()
def process_mail_outbox(limit=20):
    """Envoie les e-mails arrivés à échéance. Un échec est retenté (5 essais), puis signalé en notification interne."""
    if MAIL_BACKEND=='off':return 0
    with _mail_lock:
        with db() as c:due=q(c,"SELECT id FROM mail_outbox WHERE status='pending' AND not_before<=? ORDER BY not_before LIMIT ?",(now(),limit))
        sent=0
        for m in due:
            with tx() as c:
                if c.execute("UPDATE mail_outbox SET status='sending',attempts=attempts+1 WHERE id=? AND status='pending'",(m['id'],)).rowcount!=1:continue
                row=one(c,'SELECT * FROM mail_outbox WHERE id=?',(m['id'],))
            try:
                with db() as c:
                    to=mail_recipients(c,row['warehouse'])
                    if not to:raise RuntimeError('Aucun destinataire configuré')
                    subject,text,html,att=compose_receipt_mail(c,row['ref'])
                pid=send_mail(to,subject,text,html,att)
                with tx() as c:
                    c.execute("UPDATE mail_outbox SET status='sent',sent_at=?,recipients=?,subject=?,provider_id=?,last_error=NULL WHERE id=?",(now(),json.dumps(to),subject,pid,row['id']))
                    audit(c,'system','mail_sent',row['kind'],row['ref'],{'outbox':row['id'],'to':to})
                sent+=1
            except Exception as e:
                err=(getattr(e,'detail',None) or str(e))[:300];final=row['attempts']>=MAIL_MAX_ATTEMPTS
                retry=(datetime.now(timezone.utc)+timedelta(minutes=5*row['attempts'])).isoformat(timespec='seconds')
                with tx() as c:
                    c.execute('UPDATE mail_outbox SET status=?,not_before=?,last_error=? WHERE id=?',('failed' if final else 'pending',retry,err,row['id']))
                    if final:notify(c,row['warehouse'],'receipt',row['ref'],'E-mail non envoyé',('Fiche de réception non transmise : '+err)[:350],'system')
        return sent
class MailRoute(BaseModel):recipients:list[str]=Field(max_length=10)
@app.get('/api/mail-routes')
def mail_routes(u=Depends(auth)):
    role(u,'admin','manager')
    with db() as c:rows=q(c,'SELECT * FROM mail_routes ORDER BY warehouse')
    for r in rows:r['recipients']=json.loads(r['recipients'])
    return {'enabled':MAIL_BACKEND!='off','sender':MAIL_FROM,'delay_seconds':MAIL_DELAY,'routes':rows}
@app.put('/api/mail-routes/{wh}')
def set_mail_route(wh:str,x:MailRoute,u=Depends(auth)):
    role(u,'superadmin');warehouse(wh)
    to=[]
    for a in x.recipients:
        a=a.strip().lower()
        if a:require(EMAIL_RE.match(a),f'Adresse e-mail invalide : {a}');to.append(a)
    with tx() as c:
        c.execute('UPDATE mail_routes SET recipients=?,updated=?,updated_by=? WHERE warehouse=?',(json.dumps(sorted(set(to),key=to.index)),now(),u['username'],wh))
        audit(c,u['username'],'mail_route','warehouse',wh,{'recipients':to})
    return {'ok':True}
@app.get('/api/mail-outbox')
def mail_outbox(u=Depends(auth)):
    role(u,'admin','manager','exploitation')
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:rows=q(c,f'SELECT id,kind,ref,warehouse,reason,status,created,created_by,not_before,attempts,recipients,subject,sent_at,last_error FROM mail_outbox WHERE warehouse IN ({marks}) ORDER BY created DESC LIMIT 100',u['warehouses'])
    for r in rows:r['recipients']=json.loads(r['recipients']) if r['recipients'] else []
    return rows

# Tâches de fond : envoi des e-mails (toutes les 30 s) et effacement des pièces d'identité (toutes les 6 h).
def _background_loop():
    try:
        with db() as c:c.execute("UPDATE mail_outbox SET status='pending' WHERE status='sending'")  # reprise après arrêt brutal
    except Exception as e:print('TAF WAREHOUSE tâches de fond :',e,flush=True)
    last_purge=0.0
    while True:
        try:process_mail_outbox()
        except Exception as e:print('TAF WAREHOUSE envoi e-mails :',e,flush=True)
        if time.time()-last_purge>6*3600:
            try:
                purged=purge_identities()
                if purged:print(f'TAF WAREHOUSE : {len(purged)} pièce(s) d’identité effacée(s)',flush=True)
            except Exception as e:print('TAF WAREHOUSE effacement pièces :',e,flush=True)
            last_purge=time.time()
        time.sleep(30)
@app.on_event('startup')
def _start_background():
    if os.getenv('TAF_BACKGROUND','1')=='1':threading.Thread(target=_background_loop,name='taf-background',daemon=True).start()


# --- Lot 15 : générateur de zones de stockage -------------------------------------------------------
WH_CODES={'Afrique':'AFR','Maritime':'MAR','Moyen-Orient':'MO','TMS':'TMS'}
def STRUCTURE_LABEL(kind,structure):
    if kind=='rack':return {'G':'Rack gauche','D':'Rack droite'}.get(structure,'Rack '+structure)
    if kind=='shelf':return 'Étagère '+structure[2:] if structure.startswith('ET') else 'Étagère '+structure
    if kind=='floor':return 'Sol (marquage au sol)'
    if kind=='vault':return 'Coffre objets de valeur'
    if kind=='temp':return 'Zone temporaire'
    return structure
CODE_RE=re.compile(r'^[A-Z0-9]{1,3}$')
class LocationGenerate(BaseModel):
    warehouse:str
    kind:Literal['rack','floor','shelf','vault']
    names:list[str]=Field(default_factory=list,max_length=26)   # racks : G, D… ; sol : allées A, B…
    count:int=Field(default=1,ge=1,le=26)                          # étagères : nombre de meubles
    start:int=Field(default=1,ge=1,le=99)                          # étagères : premier numéro
    levels:int=Field(default=1,ge=1,le=9)
    positions:int=Field(default=1,ge=1,le=99)                      # par niveau (rack, étagère), par allée (sol), cases du coffre
    capacity_kg:Optional[float]=Field(default=None,gt=0,le=20000)
    capacity_m3:Optional[float]=Field(default=None,gt=0,le=200)
    proof:str=Field(default='',max_length=300)
    dry_run:bool=False
def plan_locations(x):
    """Identifiants générés : AFR-G-2-05 (rack), AFR-SOL-A-03 (sol), AFR-ET1-2-03 (étagère), AFR-COFFRE-01 (coffre)."""
    code=WH_CODES[x.warehouse];out=[]
    if x.kind in ('rack','floor'):
        names=[n.strip().upper() for n in x.names if n.strip()]
        require(names,'Indiquer au moins un rack (ex. G, D) ou une allée (ex. A, B)')
        require(all(CODE_RE.match(n) for n in names) and len(set(names))==len(names),'Noms : 1 à 3 lettres ou chiffres, sans doublon')
    if x.kind=='rack':
        for n in names:
            for lv in range(1,x.levels+1):
                for pos in range(1,x.positions+1):out.append((f'{code}-{n}-{lv}-{pos:02d}',n,str(lv),pos,f'{STRUCTURE_LABEL("rack",n)} · étage {lv}'))
    elif x.kind=='floor':
        for n in names:
            for pos in range(1,x.positions+1):out.append((f'{code}-SOL-{n}-{pos:02d}','SOL',n,pos,f'Sol · allée {n}'))
    elif x.kind=='shelf':
        for k in range(x.start,x.start+x.count):
            for lv in range(1,x.levels+1):
                for pos in range(1,x.positions+1):out.append((f'{code}-ET{k}-{lv}-{pos:02d}',f'ET{k}',str(lv),pos,f'Étagère {k} · niveau {lv}'))
    else:
        if x.positions==1:out.append((f'{code}-COFFRE','COFFRE','-',1,'Coffre objets de valeur'))
        else:
            for pos in range(1,x.positions+1):out.append((f'{code}-COFFRE-{pos:02d}','COFFRE','-',pos,'Coffre objets de valeur'))
    require(len(out)<=2000,'Plus de 2 000 emplacements en une fois : découper la création')
    return out
@app.post('/api/locations/generate')
def generate_locations(x:LocationGenerate,u=Depends(auth)):
    role(u,'admin','manager');warehouse(x.warehouse);access(u,x.warehouse)
    verified=bool(x.capacity_kg and x.capacity_m3 and len(x.proof.strip())>=5)
    require(not x.proof.strip() or verified,'Preuve fournie : indiquer aussi la charge (kg) et le volume (m³) par emplacement')
    rows=plan_locations(x)
    with tx() as c:
        existing={r['id']:r for r in q(c,'SELECT id,active FROM locations WHERE id IN ('+','.join('?' for _ in rows)+')',[r[0] for r in rows])}
        fresh=[r for r in rows if r[0] not in existing]
        revived=[r for r in rows if r[0] in existing and not existing[r[0]]['active']]
        if x.dry_run:
            return {'dry_run':True,'total':len(rows),'new':len(fresh)+len(revived),'existing':len(rows)-len(fresh)-len(revived),'sample':[r[0] for r in rows[:6]]+(['…',rows[-1][0]] if len(rows)>6 else []),'verified':verified}
        require(fresh or revived,'Tous ces emplacements existent déjà',409)
        t=now()
        for lid,struct,lv,pos,zone in fresh:
            c.execute('INSERT INTO locations(id,warehouse,zone,capacity_kg,capacity_m3,verified,blocked,notes,kind,structure,level,position,active,created_by,created) VALUES(?,?,?,?,?,?,0,?,?,?,?,?,1,?,?)',
                      (lid,x.warehouse,zone,x.capacity_kg,x.capacity_m3,int(verified),x.proof.strip(),x.kind,struct,lv,pos,u['username'],t))
        for lid,*_ in revived:
            c.execute('UPDATE locations SET active=1,capacity_kg=COALESCE(?,capacity_kg),capacity_m3=COALESCE(?,capacity_m3),verified=CASE WHEN ?=1 THEN 1 ELSE verified END,notes=CASE WHEN ?=1 THEN ? ELSE notes END WHERE id=?',
                      (x.capacity_kg,x.capacity_m3,int(verified),int(verified),x.proof.strip(),lid))
        audit(c,u['username'],'generate_locations','warehouse',x.warehouse,{'kind':x.kind,'names':x.names,'count':x.count,'levels':x.levels,'positions':x.positions,'created':len(fresh),'reactivated':len(revived),'verified':verified})
    return {'created':len(fresh),'reactivated':len(revived),'skipped':len(rows)-len(fresh)-len(revived),'ids':[r[0] for r in fresh+revived]}
LOC_STATUS={'ok':'En service','reserve':'Réservé','inspection':'À inspecter','endommage':'Endommagé','maintenance':'En maintenance'}
class LocStatus(BaseModel):status:Literal['ok','reserve','inspection','endommage','maintenance'];note:str=Field(default='',max_length=300)
def _set_status(c,u,locs,x):
    # Tout le monde peut signaler un problème ; seuls le responsable et l'administration remettent en service.
    if x.status in ('ok','reserve'):role(u,'manager','admin')
    else:require(len(x.note.strip())>=3,'Décrire le problème constaté (au moins 3 caractères)')
    for l in locs:
        c.execute('UPDATE locations SET status=?,status_note=?,status_at=?,status_by=? WHERE id=?',(x.status,x.note.strip(),now(),u['username'],l['id']))
        audit(c,u['username'],'location_status','location',l['id'],{'from':l.get('status') or 'ok','to':x.status,'note':x.note.strip()})
@app.put('/api/locations/{lid}/status')
def location_status(lid:str,x:LocStatus,u=Depends(auth)):
    with tx() as c:
        l=one(c,'SELECT * FROM locations WHERE id=? AND active=1',(lid,));require(l,'Emplacement inconnu',404);access(u,l['warehouse'])
        _set_status(c,u,[l],x)
        if x.status in ('endommage','maintenance','inspection'):notify(c,l['warehouse'],'location',lid,f"Emplacement {lid} : {LOC_STATUS[x.status].lower()}",x.note.strip()[:300],u['username'])
    return {'ok':True,'status':x.status}
class StructureStatus(LocStatus):warehouse:str;structure:str=Field(min_length=1,max_length=20)
@app.post('/api/locations/structure-status')
def structure_status(x:StructureStatus,u=Depends(auth)):
    """Statut d'un rack entier (tous ses emplacements)."""
    access(u,x.warehouse)
    with tx() as c:
        locs=q(c,'SELECT * FROM locations WHERE warehouse=? AND structure=? AND active=1',(x.warehouse,x.structure));require(locs,'Structure introuvable',404)
        _set_status(c,u,locs,x)
        if x.status in ('endommage','maintenance','inspection'):notify(c,x.warehouse,'location',x.structure,f"{x.structure} : {LOC_STATUS[x.status].lower()}",x.note.strip()[:300],u['username'])
    return {'ok':True,'updated':len(locs)}
class InternalStock(BaseModel):
    description:str=Field(min_length=3,max_length=300);service:str=Field(default='',max_length=100);contact:str=Field(default='',max_length=100)
    quantity:str=Field(default='',max_length=60);since:Optional[str]=None;until:Optional[str]=None;notes:str=Field(default='',max_length=1000)
@app.post('/api/locations/{lid}/internal')
def internal_stock(lid:str,x:InternalStock,u=Depends(auth)):
    """Déclare l'emplacement occupé par un stockage interne TAF (matériel, consommables, archives…)."""
    role(u,'worker','leader','manager','exploitation','admin')
    with tx() as c:
        l=one(c,'SELECT * FROM locations WHERE id=? AND active=1',(lid,));require(l,'Emplacement inconnu',404);access(u,l['warehouse'])
        require(not one(c,"SELECT id FROM units WHERE location_id=? AND status NOT IN ('exited','depleted')",(lid,)),'Emplacement déjà occupé par de la marchandise',409)
        cur=one(c,'SELECT * FROM location_internal WHERE location_id=? AND released_at IS NULL',(lid,))
        vals=(x.description.strip(),x.service.strip(),x.contact.strip(),x.quantity.strip(),x.since or now()[:10],x.until,x.notes.strip())
        if cur:
            c.execute('UPDATE location_internal SET description=?,service=?,contact=?,quantity=?,since=?,until=?,notes=? WHERE id=?',(*vals,cur['id']));i=cur['id']
            audit(c,u['username'],'internal_update','location',lid,{'id':i,'before':{k:cur[k] for k in ('description','service','quantity','until')},'after':x.model_dump()})
        else:
            i=uid('INT');c.execute('INSERT INTO location_internal(id,location_id,description,service,contact,quantity,since,until,notes,created_by,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,lid,*vals,u['username'],now()))
            audit(c,u['username'],'internal_declare','location',lid,{'id':i,**x.model_dump()})
    return {'id':i}
class InternalRelease(BaseModel):note:str=Field(default='',max_length=300)
@app.post('/api/locations/{lid}/internal/release')
def internal_release(lid:str,x:InternalRelease,u=Depends(auth)):
    with tx() as c:
        l=one(c,'SELECT * FROM locations WHERE id=?',(lid,));require(l,'Emplacement inconnu',404);access(u,l['warehouse'])
        cur=one(c,'SELECT * FROM location_internal WHERE location_id=? AND released_at IS NULL',(lid,));require(cur,'Aucun stockage interne sur cet emplacement',404)
        c.execute('UPDATE location_internal SET released_at=?,released_by=?,release_note=? WHERE id=?',(now(),u['username'],x.note.strip(),cur['id']))
        audit(c,u['username'],'internal_release','location',lid,{'id':cur['id'],'description':cur['description'],'note':x.note.strip()})
    return {'ok':True}
@app.get('/api/locations/{lid}/detail')
def location_detail(lid:str,u=Depends(auth)):
    with db() as c:
        l=one(c,'SELECT * FROM locations WHERE id=?',(lid,));require(l,'Emplacement inconnu',404);access(u,l['warehouse'])
        units=q(c,"SELECT u.id,u.receipt_id,u.unit_type,u.unit_index,u.unit_count,u.quantity,u.weight,u.hold,u.status,cl.name client,r.awb FROM units u LEFT JOIN receipts r ON r.id=u.receipt_id LEFT JOIN clients cl ON cl.id=r.client_id WHERE u.location_id=? AND u.status NOT IN ('exited','depleted') ORDER BY u.receipt_id,u.unit_index",(lid,))
        internal=one(c,'SELECT * FROM location_internal WHERE location_id=? AND released_at IS NULL',(lid,))
        history=q(c,"SELECT at,actor,action,details FROM audit WHERE kind='location' AND ref=? ORDER BY at DESC,id DESC LIMIT 30",(lid,))
        candidates=q(c,"SELECT u.id,u.receipt_id,u.unit_type,u.unit_index,u.unit_count,u.quantity,u.weight,u.version,u.location_id,u.status FROM units u WHERE u.warehouse=? AND u.status IN ('awaiting_putaway','available') AND COALESCE(u.hold,'')='' AND COALESCE(u.location_id,'')!=? ORDER BY CASE WHEN u.status='awaiting_putaway' THEN 0 ELSE 1 END,u.receipt_id DESC LIMIT 200",(l['warehouse'],lid))
    for h in history:h['details']=json.loads(h['details'] or '{}')
    return {'location':{**l,'status_label':LOC_STATUS.get(l.get('status') or 'ok')},'units':units,'internal':internal,'history':history,'candidates':candidates}
class WarehouseClear(BaseModel):warehouse:str;scope:Literal['rack','all']='rack';reason:str=Field(min_length=5,max_length=300)
@app.post('/api/locations/remove-all')
def remove_all_locations(x:WarehouseClear,u=Depends(auth)):
    """Supprime en un bloc les emplacements VIDES d'un entrepôt (tous les racks, ou toutes les zones hors zone temporaire)."""
    role(u,'admin','manager');warehouse(x.warehouse);access(u,x.warehouse)
    with tx() as c:
        kinds="('rack')" if x.scope=='rack' else "('rack','shelf','floor','vault','other')"
        locs=[r['id'] for r in q(c,f"SELECT id FROM locations WHERE warehouse=? AND active=1 AND kind IN {kinds}",(x.warehouse,))]
        require(locs,'Aucun emplacement à supprimer',404)
        marks=','.join('?' for _ in locs)
        busy={r['location_id'] for r in q(c,f"SELECT DISTINCT location_id FROM units WHERE location_id IN ({marks}) AND status NOT IN ('exited','depleted')",locs)}
        busy|={r['location_id'] for r in q(c,f"SELECT location_id FROM location_internal WHERE location_id IN ({marks}) AND released_at IS NULL",locs)}
        used={r['l'] for r in q(c,f"SELECT DISTINCT destination l FROM movements WHERE destination IN ({marks})",locs)}|{r['l'] for r in q(c,f"SELECT DISTINCT location_id l FROM units WHERE location_id IN ({marks})",locs)}|{r['l'] for r in q(c,f"SELECT location_id l FROM rack_rules WHERE location_id IN ({marks})",locs)}|{r['l'] for r in q(c,f"SELECT DISTINCT location_id l FROM location_internal WHERE location_id IN ({marks})",locs)}
        removed=archived=0
        for lid in locs:
            if lid in busy:continue
            if lid in used:c.execute('UPDATE locations SET active=0 WHERE id=?',(lid,));archived+=1
            else:c.execute('DELETE FROM locations WHERE id=?',(lid,));removed+=1
        audit(c,u['username'],'remove_all_locations','warehouse',x.warehouse,{'scope':x.scope,'removed':removed,'archived':archived,'kept_busy':sorted(busy),'reason':x.reason})
    return {'removed':removed+archived,'archived':archived,'kept':sorted(busy)}
class StructureRemove(BaseModel):warehouse:str;structure:str=Field(min_length=1,max_length=20);reason:str=Field(min_length=5,max_length=300)
@app.post('/api/locations/remove-structure')
def remove_structure(x:StructureRemove,u=Depends(auth)):
    """Retire une structure (rack, allée au sol, étagère…). Refusé si un emplacement contient encore de la marchandise."""
    role(u,'admin','manager');access(u,x.warehouse)
    with tx() as c:
        locs=[r['id'] for r in q(c,'SELECT id FROM locations WHERE warehouse=? AND structure=? AND active=1',(x.warehouse,x.structure))]
        require(locs,'Structure introuvable',404)
        marks=','.join('?' for _ in locs)
        busy=q(c,f"SELECT DISTINCT location_id FROM units WHERE location_id IN ({marks}) AND status NOT IN ('exited','depleted') UNION SELECT location_id FROM location_internal WHERE location_id IN ({marks}) AND released_at IS NULL",locs+locs)
        require(not busy,'Emplacements encore occupés : '+', '.join(b['location_id'] for b in busy[:5]),409)
        used={r['location_id'] for r in q(c,f"SELECT DISTINCT destination location_id FROM movements WHERE destination IN ({marks})",locs)}
        used|={r['location_id'] for r in q(c,f"SELECT DISTINCT location_id FROM units WHERE location_id IN ({marks})",locs)}
        used|={r['location_id'] for r in q(c,f"SELECT DISTINCT location_id FROM location_internal WHERE location_id IN ({marks})",locs)}
        for lid in locs:
            if lid in used or one(c,'SELECT location_id FROM rack_rules WHERE location_id=?',(lid,)):c.execute('UPDATE locations SET active=0 WHERE id=?',(lid,))  # historique conservé
            else:c.execute('DELETE FROM locations WHERE id=?',(lid,))
        audit(c,u['username'],'remove_structure','warehouse',x.warehouse,{'structure':x.structure,'locations':len(locs),'archived':len(used),'reason':x.reason})
    return {'removed':len(locs),'archived':len(used)}
@app.get('/api/locations/labels')
def location_labels(ids:str='',warehouse:str='',structure:str='',u=Depends(auth)):
    """Panneaux A4 d'emplacements (6 par page) avec QR code : racks, étagères, marquage au sol, coffre."""
    with db() as c:
        if ids:rows=[one(c,'SELECT * FROM locations WHERE id=? AND active=1',(i.strip(),)) for i in ids.split(',') if i.strip()]
        else:
            access(u,warehouse);rows=q(c,'SELECT * FROM locations WHERE warehouse=? AND active=1'+(' AND structure=?' if structure else '')+' ORDER BY structure,level,position',(warehouse,structure) if structure else (warehouse,))
        rows=[r for r in rows if r];require(rows,'Aucun emplacement',404);require(len(rows)<=600,'600 panneaux maximum par impression')
        for r in rows:access(u,r['warehouse'])
    from app.pdf_report import location_signs
    for r in rows:r['label']=STRUCTURE_LABEL(r.get('kind') or 'rack',r.get('structure') or '')
    return Response(content=location_signs(rows),media_type='application/pdf',headers={'Content-Disposition':'inline; filename="panneaux-emplacements.pdf"'})

# --- Lot 15 : demandes au magasin depuis la fiche d'entrée -------------------------------------------
class ReceiptMission(BaseModel):
    type:Literal['preparation','rangement','controle','inventaire','transfert','autre']='preparation'
    title:str=Field(default='',max_length=200);description:str=Field(default='',max_length=2000)
    priority:Literal['low','normal','high','urgent']='normal';due_at:Optional[str]=None;assignee:str=''
    unit_ids:Optional[list[str]]=None
MISSION_TITLES={'preparation':'Préparer pour la sortie','rangement':'Ranger','controle':'Contrôler','inventaire':'Compter','transfert':'Préparer le transfert','autre':'Tâche'}
@app.post('/api/receipts/{rid}/missions')
def receipt_mission(rid:str,x:ReceiptMission,u=Depends(auth)):
    role(u,'exploitation','manager','admin','leader')
    with tx() as c:
        r=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        stock=[x_['id'] for x_ in q(c,"SELECT id FROM units WHERE receipt_id=? AND status NOT IN ('exited','depleted') ORDER BY unit_index,id",(rid,))]
        units=stock if x.unit_ids is None else x.unit_ids
        require(units,'Aucune unité en stock pour cette entrée',409)
        require(all(i in stock for i in units),'Unité hors de cette entrée ou déjà sortie')
        require(x.type!='autre' or len(x.description.strip())>=3,'Décrire la tâche demandée')
        who=_mission_assignee(c,r['warehouse'],x.assignee)
        title=x.title.strip() or f"{MISSION_TITLES[x.type]} — {rid} · {r['client']}"+(f" · LTA {r['awb']}" if r.get('awb') else '')+f" · {len(units)} unité(s)"
        i=uid('MIS')
        c.execute('INSERT INTO missions(id,warehouse,title,leader,status,created,closed,type,assignee,priority,due_at,description,created_by,receipt_id,unit_ids) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (i,r['warehouse'],title[:200],'','assigned' if who else 'to_assign',now(),None,x.type,who,x.priority,x.due_at,x.description.strip(),u['username'],rid,json.dumps(units)))
        audit(c,u['username'],'request_mission','receipt',rid,{'mission':i,'type':x.type,'units':len(units),'assignee':who})
        audit(c,u['username'],'create','mission',i,{'type':x.type,'receipt':rid})
        notify(c,r['warehouse'],'mission',i,'🔔 Nouvelle demande au magasin'+(f' pour {who}' if who else ''),title[:300],u['username'])
    return {'id':i,'status':'assigned' if who else 'to_assign'}
@app.get('/api/missions/feed')
def missions_feed(u=Depends(auth)):
    """Alertes des postes magasin : missions en attente de prise en charge et missions qui me sont affectées."""
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:
        rows=q(c,f"SELECT id,warehouse,title,type,priority,status,assignee,created,receipt_id,due_at FROM missions WHERE warehouse IN ({marks}) AND (status='to_assign' OR (status='assigned' AND assignee=?)) ORDER BY created DESC LIMIT 50",[*u['warehouses'],u['username']])
    return {'missions':rows,'count':len(rows),'at':now()}

def receipt_history(c,rid):
    """Historique complet d'une entrée : réception, unités, documents, écarts, demandes et missions, e-mails."""
    ev=[]
    def add(at,kind,title,actor=None,detail='',ref=None):
        if at:ev.append({'at':at,'kind':kind,'title':title,'actor':actor,'detail':detail or '','ref':ref})
    labels={'print_cover':'Récapitulatif à agrafer imprimé','edit':'Fiche modifiée','validate':'Validation définitive de la fiche','reopen':'Fiche rouverte pour modification','add_document':'Document ajouté','unit_dimensions':'Dimensions saisies','receive':'Réception enregistrée','report_discrepancy':'Écart déclaré','review_discrepancy':'Écart tranché','request_mission':'Demande au magasin','mail_request':'Envoi manuel de la fiche','mail_sent':'Fiche de réception envoyée par e-mail'}
    for a in q(c,"SELECT * FROM audit WHERE kind='receipt' AND ref=? ORDER BY at,id",(rid,)):
        d=json.loads(a['details'] or '{}') if a.get('details') else {}
        detail={'receive':lambda: f"{d.get('units',0)} unité(s)"+(' · '+' ; '.join(d.get('warnings',[])) if d.get('warnings') else ''),
                'edit':lambda: ' ; '.join(f"{RECEIPT_FIELDS.get(k,k)} : « {v[0] or '—'} » → « {v[1] or '—'} »" for k,v in d.get('changes',{}).items()),
                'unit_dimensions':lambda: f"{d.get('unit')} : "+' ; '.join(f"{DIM_LABELS.get(k,k)} {_num(v[0])} → {_num(v[1])} {'kg' if k=='weight' else 'cm'}" for k,v in d.get('changes',{}).items()),
                'validate':lambda: f"révision {d.get('revision')}"+(' · e-mail au service' if d.get('mail') else ''),
                'reopen':lambda: d.get('reason',''),
                'add_document':lambda: f"{d.get('name','')} ({ {'transport':'document de transport','photo':'photo'}.get(d.get('category'),'autre') })",
                'mail_sent':lambda: ', '.join(d.get('to',[])),'request_mission':lambda: f"{d.get('mission')} · {d.get('units')} unité(s)"}.get(a['action'],lambda:'')()
        add(a['at'],'receipt',labels.get(a['action'],a['action']),a['actor'],detail,rid)
    # Les documents ajoutés figurent dans le journal (« Document ajouté »).
    for m in q(c,'SELECT * FROM missions WHERE receipt_id=?',(rid,)):
        for e in q(c,'SELECT * FROM mission_events WHERE mission_id=? ORDER BY created,id',(m['id'],)):
            add(e['created'],'mission',{'take':'Mission prise en charge','start':'Mission démarrée','suspend':'Mission suspendue','resume':'Mission reprise','complete':'Mission terminée','cancel':'Mission annulée','assign':'Mission affectée'}.get(e['action'],e['action']),e['actor'],f"{m['title']}"+(f" · {e['note']}" if e['note'] else ''),m['id'])
    for un in q(c,'SELECT * FROM units WHERE receipt_id=?',(rid,)):
        tag=f"{(un.get('unit_type') or 'unité').capitalize()} {un['unit_index']}/{un['unit_count']}" if un.get('unit_index') else un['id']
        for e in unit_events(c,un):
            if e['kind']=='reception':continue
            add(e['at'],e['kind'],f"{tag} · {e['title']}",e['actor'],e['detail'],un['id'])
    ev.sort(key=lambda e:(e['at'][:19],-1 if e['title']=='Réception enregistrée' else TIMELINE_RANK.get(e['kind'],5)))
    return ev
DIM_LABELS={'length_cm':'longueur','width_cm':'largeur','height_cm':'hauteur','weight':'poids'}
def _num(v):
    return '—' if not v else (f'{v:g}' if isinstance(v,(int,float)) else str(v)).replace('.',',')
RECEIPT_FIELDS={'driver_id':'Remettant','pallets_expected':'Palettes annoncées','drums_expected':'Fûts annoncés','accepted':'Expédition acceptée','refusal_reason':'Raisons du refus','shipper_address':'Adresse expéditeur','consignee':'Destinataire','consignee_address':'Adresse destinataire','awb':'LTA','shipper':'Expéditeur','carrier':'Transporteur','transport_ref':'Référence transport','folder_ref':'Référence dossier','nature':'Nature','notes':'Observations','weight':'Poids déclaré (kg)','apparent_condition':'État apparent','security_status':'Statut sûreté'}
def dims_ok(x):
    g=(lambda k:getattr(x,k,None)) if not isinstance(x,dict) else x.get
    return all((g(k) or 0)>0 for k in ('length_cm','width_cm','height_cm'))
def receipt_missing(c,rid):
    """Ce qui manque pour la validation définitive."""
    r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,));out=[]
    units=q(c,"SELECT * FROM units WHERE receipt_id=? ORDER BY unit_index,id",(rid,))
    if not units:out.append('Aucune unité enregistrée')
    nodim=[u for u in units if not dims_ok(u)]
    if nodim:out.append(f"Dimensions manquantes : {len(nodim)} unité(s) ("+', '.join(((u.get('unit_type') or 'unité').capitalize()+(f" {u['unit_index']}/{u['unit_count']}" if u.get('unit_index') else '')) for u in nodim[:6])+(' …' if len(nodim)>6 else '')+')')
    if not one(c,"SELECT id FROM documents WHERE kind='receipt' AND ref=? AND category='transport' LIMIT 1",(rid,)):out.append('Document de transport manquant (LTA, CMR ou bon de livraison)')
    if not (r.get('awb') or '').strip() and not (r.get('transport_ref') or '').strip():out.append('Numéro de LTA ou référence transport manquant')
    if not r.get('driver_id'):out.append('Remettant (chauffeur et pièce d’identité) non renseigné')
    if not (r.get('shipper') or '').strip():out.append('Expéditeur non renseigné')
    if r.get('accepted') in (0,False) and not (r.get('refusal_reason') or '').strip():out.append('Expédition refusée : raisons à préciser')
    return out
def receipt_state(c,rid):
    r=one(c,'SELECT stage,validated_by,validated_at,revision FROM receipts WHERE id=?',(rid,))
    return {**r,'missing':receipt_missing(c,rid) if r['stage']!='validated' else []}
@app.get('/api/receipts/{rid}/dossier')
def receipt_dossier_api(rid:str,u=Depends(auth)):
    """Dossier complet de l'entrée : fiche, unités, documents, ce qui manque, historique."""
    with db() as c:
        r=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        units=q(c,'SELECT id,unit_type,unit_index,unit_count,quantity,weight,volume,length_cm,width_cm,height_cm,status,location_id,hold,version FROM units WHERE receipt_id=? ORDER BY unit_index,id',(rid,))
        docs=q(c,"SELECT id,name,mime,uploaded,actor,category FROM documents WHERE kind='receipt' AND ref=? ORDER BY uploaded",(rid,))
        return {'receipt':r,'state':receipt_state(c,rid),'units':units,'documents':docs,'history':receipt_history(c,rid),'mail_enabled':MAIL_BACKEND!='off' and bool(mail_recipients(c,r['warehouse']))}
class ReceiptEdit(BaseModel):
    awb:Optional[str]=Field(default=None,max_length=40);shipper:Optional[str]=Field(default=None,max_length=200);carrier:Optional[str]=Field(default=None,max_length=200)
    transport_ref:Optional[str]=Field(default=None,max_length=100);folder_ref:Optional[str]=Field(default=None,max_length=100);nature:Optional[str]=Field(default=None,max_length=300)
    notes:Optional[str]=Field(default=None,max_length=2000);weight:Optional[float]=Field(default=None,ge=0,le=500000)
    apparent_condition:Optional[Literal['conforme','endommage','a_verifier']]=None;security_status:Optional[Literal['securise','non_securise','a_controler']]=None
    driver_id:Optional[str]=Field(default=None,max_length=40);pallets_expected:Optional[int]=Field(default=None,ge=0,le=10000);drums_expected:Optional[int]=Field(default=None,ge=0,le=10000)
    accepted:Optional[bool]=None;refusal_reason:Optional[str]=Field(default=None,max_length=300)
    shipper_address:Optional[str]=Field(default=None,max_length=200);consignee:Optional[str]=Field(default=None,max_length=200);consignee_address:Optional[str]=Field(default=None,max_length=200)
def _editable(c,u,rid):
    r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
    require(r['stage']!='validated','Fiche validée : la rouvrir (exploitation) pour la modifier',409);return r
@app.put('/api/receipts/{rid}')
def edit_receipt(rid:str,x:ReceiptEdit,u=Depends(auth)):
    """Compléter ou corriger la fiche. Chaque changement est inscrit, avant → après, dans l'historique."""
    with tx() as c:
        r=_editable(c,u,rid);changes={}
        if x.driver_id:require(one(c,'SELECT id FROM drivers WHERE id=?',(x.driver_id,)),'Remettant (chauffeur) inconnu')
        for k,v in x.model_dump(exclude_none=True).items():
            if isinstance(v,bool):v=int(v)
            if isinstance(v,str):v=v.strip()
            if (r.get(k) if r.get(k) is not None else ('' if isinstance(v,str) else None))!=v:changes[k]=[r.get(k),v]
        require(changes,'Aucune modification')
        c.execute('UPDATE receipts SET '+','.join(f'{k}=?' for k in changes)+' WHERE id=?',[v[1] for v in changes.values()]+[rid])
        audit(c,u['username'],'edit','receipt',rid,{'changes':changes})
        # Un statut de sûreté ou un état apparent dégradé bloque la marchandise, comme à la réception.
        held={'non_securise':('surete','Sûreté : non sécurisé'),'a_controler':('surete','Sûreté : à contrôler'),'endommage':('avarie','État apparent endommagé'),'a_verifier':('controle','État apparent à vérifier')}
        for k in ('security_status','apparent_condition'):
            if k in changes and changes[k][1] in held:
                for un in q(c,"SELECT id FROM units WHERE receipt_id=? AND status NOT IN ('exited','depleted')",(rid,)):add_hold(c,u['username'],un['id'],held[changes[k][1]][0],held[changes[k][1]][1]+' (modification de la fiche)',rid)
    return {'ok':True,'changes':list(changes)}
class UnitDims(BaseModel):
    length_cm:float=Field(gt=0,le=2000);width_cm:float=Field(gt=0,le=2000);height_cm:float=Field(gt=0,le=1000);weight_kg:Optional[float]=Field(default=None,ge=0,le=50000)
@app.put('/api/units/{unit_id}/dimensions')
def unit_dimensions(unit_id:str,x:UnitDims,u=Depends(auth)):
    with tx() as c:
        unit=unit_access(c,u,unit_id);require(unit['receipt_id'],'Unité sans fiche d’entrée')
        _editable(c,u,unit['receipt_id'])
        new={'length_cm':x.length_cm,'width_cm':x.width_cm,'height_cm':x.height_cm,**({'weight':x.weight_kg} if x.weight_kg is not None else {})}
        changes={k:[unit.get(k),v] for k,v in new.items() if unit.get(k)!=v}
        require(changes,'Aucune modification')
        vol=round(x.length_cm*x.width_cm*x.height_cm/1e6,4)
        c.execute('UPDATE units SET length_cm=?,width_cm=?,height_cm=?,weight=COALESCE(?,weight),volume=?,dimensions_ok=1,version=version+1 WHERE id=?',(x.length_cm,x.width_cm,x.height_cm,x.weight_kg,vol,unit_id))
        tot=one(c,'SELECT COALESCE(SUM(volume),0) v FROM units WHERE receipt_id=?',(unit['receipt_id'],))['v']
        c.execute('UPDATE receipts SET volume_m3=?,volumetric_weight=? WHERE id=?',(round(tot,4),round(tot*VOLUMETRIC_KG_PER_M3,2),unit['receipt_id']))
        audit(c,u['username'],'unit_dimensions','receipt',unit['receipt_id'],{'unit':unit_id,'changes':changes})
    return {'ok':True,'volume_m3':vol}
@app.post('/api/receipts/{rid}/validate')
def validate_receipt(rid:str,u=Depends(auth)):
    """Validation définitive : refusée tant que dimensions et documents de transport manquent. Envoie la fiche au service."""
    with tx() as c:
        r=_editable(c,u,rid);missing=receipt_missing(c,rid)
        require(not missing,'Fiche incomplète : '+' ; '.join(missing),409)
        rev=(r.get('revision') or 0)+1
        c.execute("UPDATE receipts SET stage='validated',validated_by=?,validated_at=?,revision=? WHERE id=?",(u['username'],now(),rev,rid))
        mail=queue_receipt_mail(c,rid,r['warehouse'],'validation' if rev==1 else 'revalidation',u['username'],delay=0)
        audit(c,u['username'],'validate','receipt',rid,{'revision':rev,'mail':mail})
        notify(c,r['warehouse'],'receipt',rid,'Fiche d’entrée validée',f"{rid} validée par {u['username']}"+(' — envoyée au service' if mail else ''),u['username'])
    return {'ok':True,'stage':'validated','revision':rev,'mail':mail}
class ReceiptReopen(BaseModel):reason:str=Field(min_length=5,max_length=500)
@app.post('/api/receipts/{rid}/reopen')
def reopen_receipt(rid:str,x:ReceiptReopen,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with tx() as c:
        r=one(c,'SELECT * FROM receipts WHERE id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        require(r['stage']=='validated','Fiche non validée',409)
        c.execute("UPDATE receipts SET stage='pending' WHERE id=?",(rid,))
        audit(c,u['username'],'reopen','receipt',rid,{'reason':x.reason.strip()})
    return {'ok':True,'stage':'pending'}
@app.get('/api/receipts/{rid}/cover')
def receipt_cover(rid:str,u=Depends(auth)):
    """Récapitulatif A4 à imprimer à la validation, pour y agrafer les documents papier."""
    with db() as c:
        r=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        units=q(c,'SELECT * FROM units WHERE receipt_id=? ORDER BY unit_index,id',(rid,))
        docs=q(c,"SELECT name,category,uploaded,actor FROM documents WHERE kind='receipt' AND ref=? ORDER BY uploaded",(rid,))
        missing=receipt_missing(c,rid) if r['stage']!='validated' else []
        audit(c,u['username'],'print_cover','receipt',rid,{'revision':r.get('revision')})
    from app.pdf_report import receipt_cover as cover
    return Response(content=cover(r,units,docs,missing,now()),media_type='application/pdf',headers={'Content-Disposition':f'inline; filename="recapitulatif-{rid}.pdf"'})
@app.get('/api/receipts/{rid}/history')
def receipt_history_api(rid:str,u=Depends(auth)):
    with db() as c:
        r=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(rid,));require(r,'Réception introuvable',404);access(u,r['warehouse'])
        return {'receipt':{k:r[k] for k in ('id','warehouse','client','awb','expected','actual','status','created')},'events':receipt_history(c,rid)}

@app.get('/api/releases')
def releases(u=Depends(auth)):
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:return q(c,f"SELECT r.id,r.unit_id,r.quantity,r.status,r.requested_by,r.authorized_by,r.driver_id,r.signature_name,r.created,r.completed,r.order_id,CASE WHEN COALESCE(r.signature_data,'')='' THEN 0 ELSE 1 END has_signature,u.warehouse FROM releases r JOIN units u ON u.id=r.unit_id WHERE u.warehouse IN ({marks}) ORDER BY r.created DESC",u['warehouses'])
@app.post('/api/releases')
def create_release(x:ReleaseCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias="Idempotency-Key")):
    role(u,'exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        replay,digest=replay_request(c,u['id'],'release.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        unit=unit_access(c,u,x.unit_id);require(unit['status']=='available' and not unit['hold'] and unit['quantity']>0,'Unité bloquée');require(x.quantity<=unit['quantity'],'Quantité insuffisante')
        require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),'Transfert actif',409)
        require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Inventaire actif',409)
        reserved=one(c,"SELECT COALESCE(SUM(quantity),0) n FROM releases WHERE unit_id=? AND status IN ('requested','authorized')",(unit['id'],))['n']
        require(reserved+x.quantity<=unit['quantity'],'Stock déjà réservé pour sortie')
        i=uid('OUT');c.execute("INSERT INTO releases(id,unit_id,quantity,status,requested_by,created) VALUES(?,?,?,'requested',?,?)",(i,unit['id'],x.quantity,u['username'],now()));audit(c,u['username'],'request','release',i)
        save_request(c,u['id'],'release.create',idempotency_key,digest,{'id':i});c.commit()
    return {'id':i}
@app.post('/api/releases/{rid}/cancel')
def cancel_release(rid:str,u=Depends(auth)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        r=one(c,'SELECT * FROM releases WHERE id=?',(rid,))
        require(r,'Sortie inconnue',404)
        unit=unit_access(c,u,r['unit_id'])
        require(not r.get('order_id'),'Ligne gérée par un ordre de sortie : utiliser l’ordre',409)
        require(r['status'] in ('requested','authorized'),'Sortie déjà terminée ou annulée',409)
        require(u['role'] in ('superadmin','admin','manager','exploitation') or
                (r['status']=='requested' and r['requested_by']==u['username']),
                'Annulation réservée à l’exploitation ou au demandeur avant autorisation',403)
        c.execute("UPDATE releases SET status='cancelled' WHERE id=?",(rid,))
        audit(c,u['username'],'cancel','release',rid)
        notify(c,unit['warehouse'],'release',rid,'Sortie annulée','La quantité réservée est libérée.',u['username'])
        c.commit()
    return {'ok':True}

@app.post('/api/releases/{rid}/authorize')
def authorize_release(rid:str,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');r=one(c,'SELECT * FROM releases WHERE id=?',(rid,));require(r,'Sortie inconnue',404);require(not r.get('order_id'),'Ligne gérée par un ordre de sortie : utiliser l’ordre',409);unit=unit_access(c,u,r['unit_id']);require(r['status']=='requested','Statut invalide');require(not unit['hold'] and unit['status']=='available','Unité bloquée')
        require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),'Transfert actif',409)
        c.execute("UPDATE releases SET status='authorized',authorized_by=? WHERE id=?",(u['username'],rid));audit(c,u['username'],'authorize','release',rid);notify(c,unit['warehouse'],'release',rid,'Sortie autorisée','La sortie peut être remise après signature du chauffeur.',u['username']);c.commit()
    return {'ok':True}
@app.post('/api/releases/{rid}/complete')
def complete_release(rid:str,x:ReleaseComplete,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'worker','leader','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');replay,digest=replay_request(c,u['id'],'release.complete',idempotency_key,{'ref':rid,'payload':x.model_dump()});
        if replay is not None:return replay
        r=one(c,'SELECT * FROM releases WHERE id=?',(rid,));require(r,'Sortie inconnue',404);require(not r.get('order_id'),'Ligne gérée par un ordre de sortie : utiliser l’ordre',409);unit=unit_access(c,u,r['unit_id']);require(r['status']=='authorized','Autorisation exploitation requise')
        require(unit['status']=='available' and not unit['hold'],'Unité bloquée')
        require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),'Transfert actif',409)
        require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),'Inventaire actif',409)
        require(x.signature_consent,'Le transporteur doit confirmer la signature de la remise')
        require(x.signature_data.startswith('data:image/png;base64,'),'Signature manuscrite PNG requise')
        try:
            signature_bytes=base64.b64decode(x.signature_data.split(',',1)[1],validate=True)
        except (ValueError,binascii.Error):
            raise HTTPException(400,'Signature PNG invalide')
        require(signature_bytes.startswith(b'\x89PNG\r\n\x1a\n') and 300<len(signature_bytes)<320000,'Image de signature invalide ou trop volumineuse')
        require(one(c,'SELECT id FROM drivers WHERE id=?',(x.driver_id,)),'Chauffeur inconnu');require(unit['quantity']>=r['quantity'],'Quantité insuffisante')
        remaining=unit['quantity']-r['quantity']
        # Poids restant proportionnel au nombre de colis restants (volume conservé : estimation prudente).
        new_weight=round(unit['weight']*remaining/unit['quantity'],3) if unit['quantity'] else 0
        c.execute("UPDATE units SET quantity=?,weight=?,status=CASE WHEN ?=0 THEN 'exited' ELSE status END,version=version+1 WHERE id=?",(remaining,new_weight,remaining,unit['id']))
        audit(c,u['username'],'weight_update','unit',unit['id'],{'release':rid,'weight_before':unit['weight'],'weight_after':new_weight,'method':'proportionnel'})
        c.execute("UPDATE releases SET status='completed',driver_id=?,signature_name=?,signature_data=?,completed=? WHERE id=?",(x.driver_id,x.signature_name,x.signature_data,now(),rid))
        event(c,u['username'],unit['id'],'exit',unit['location_id'],None,r['quantity'],rid);audit(c,u['username'],'handover','release',rid,{'driver':x.driver_id});notify(c,unit['warehouse'],'release',rid,'Sortie remise','Remise signée enregistrée.',u['username']);save_request(c,u['id'],'release.complete',idempotency_key,digest,{'ok':True});c.commit()
    return {'ok':True}
# --- Lot 9 : ordres de sortie multi-unités -------------------------------------------
def check_signature_png(data):
    require(data.startswith('data:image/png;base64,'),'Signature manuscrite PNG requise')
    try:raw=base64.b64decode(data.split(',',1)[1],validate=True)
    except (ValueError,binascii.Error):raise HTTPException(400,'Signature PNG invalide')
    require(raw.startswith(b'\x89PNG\r\n\x1a\n') and 300<len(raw)<320000,'Image de signature invalide ou trop volumineuse')
def _order(c,u,oid):
    o=one(c,'SELECT * FROM release_orders WHERE id=?',(oid,));require(o,'Ordre de sortie inconnu',404);access(u,o['warehouse']);return o
def _order_lines(c,oid):return q(c,'SELECT * FROM releases WHERE order_id=? ORDER BY created,id',(oid,))
def _unit_releasable(c,unit):
    require(unit['status']=='available' and not unit['hold'] and unit['quantity']>0,f"Unité {unit['id']} bloquée ou indisponible")
    require(not one(c,"SELECT id FROM transfers WHERE unit_id=? AND status IN ('requested','approved','in_transit')",(unit['id'],)),f"Transfert actif sur {unit['id']}",409)
    require(not one(c,"SELECT id FROM counts WHERE unit_id=? AND status='pending'",(unit['id'],)),f"Inventaire en cours sur {unit['id']}",409)

@app.post('/api/release-orders')
def create_release_order(x:ReleaseOrderCreate,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'exploitation','manager','admin');warehouse(x.warehouse);access(u,x.warehouse)
    require(len({l.unit_id for l in x.lines})==len(x.lines),'Une unité ne peut figurer qu’une fois dans un ordre')
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'release_order.create',idempotency_key,x.model_dump())
        if replay is not None:return replay
        oid=uid('ORD');t=now()
        c.execute('INSERT INTO release_orders(id,warehouse,reference,status,requested_by,created) VALUES(?,?,?,?,?,?)',(oid,x.warehouse,x.reference,'requested',u['username'],t))
        for line in x.lines:
            unit=unit_access(c,u,line.unit_id);require(unit['warehouse']==x.warehouse,f"Unité {unit['id']} hors entrepôt {x.warehouse}")
            _unit_releasable(c,unit)
            reserved=one(c,"SELECT COALESCE(SUM(quantity),0) n FROM releases WHERE unit_id=? AND status IN ('requested','authorized')",(unit['id'],))['n']
            require(reserved+line.quantity<=unit['quantity'],f"Quantité insuffisante ou déjà réservée pour {unit['id']}")
            c.execute("INSERT INTO releases(id,unit_id,quantity,status,requested_by,created,order_id) VALUES(?,?,?,'requested',?,?,?)",(uid('OUT'),unit['id'],line.quantity,u['username'],t,oid))
        audit(c,u['username'],'request','release_order',oid,{'reference':x.reference,'lines':len(x.lines)})
        notify(c,x.warehouse,'release',oid,'Ordre de sortie à préparer',f"{x.reference} : {len(x.lines)} unité(s) à préparer et contrôler.",u['username'])
        response={'id':oid,'status':'requested'};save_request(c,u['id'],'release_order.create',idempotency_key,digest,response)
    return response

@app.get('/api/release-orders')
def release_orders(u=Depends(auth)):
    marks=','.join('?' for _ in u['warehouses'])
    with db() as c:
        orders=q(c,f'SELECT * FROM release_orders WHERE warehouse IN ({marks}) ORDER BY created DESC LIMIT 300',u['warehouses'])
        for o in orders:
            o['lines']=q(c,'SELECT r.id,r.unit_id,r.quantity,r.status,r.prepared_by,r.prepared_at,r.prepare_note,r.handover_id,r.weight_out,u.unit_type,u.unit_index,u.unit_count,u.description,u.location_id FROM releases r JOIN units u ON u.id=r.unit_id WHERE r.order_id=? ORDER BY r.created,r.id',(o['id'],))
            o['handovers']=q(c,'SELECT id,driver_id,signature_name,signed_at,actor,unit_ids FROM release_handovers WHERE order_id=? ORDER BY signed_at,id',(o['id'],))
            o['refusals']=q(c,'SELECT id,driver_id,reason,actor,created FROM release_refusals WHERE order_id=? ORDER BY created,id',(o['id'],))
        return orders

@app.post('/api/release-orders/{oid}/prepare')
def prepare_release_order(oid:str,x:OrderPrepare,u=Depends(auth)):
    role(u,'worker','leader','manager','admin')
    with tx() as c:
        o=_order(c,u,oid);require(o['status']=='requested','Préparation impossible à ce stade',409)
        line=one(c,"SELECT * FROM releases WHERE order_id=? AND unit_id=?",(oid,x.unit_id));require(line,'Unité absente de cet ordre',404)
        require(line['status']=='requested' and not line['prepared_at'],'Unité déjà préparée',409)
        unit=one(c,'SELECT * FROM units WHERE id=?',(x.unit_id,));require(not unit['hold'],f"Unité {unit['id']} bloquée : préparation interdite")
        c.execute('UPDATE releases SET prepared_by=?,prepared_at=?,prepare_note=? WHERE id=?',(u['username'],now(),x.note,line['id']))
        audit(c,u['username'],'prepare','release_order',oid,{'unit':x.unit_id,'note':x.note})
        if not one(c,"SELECT id FROM releases WHERE order_id=? AND status='requested' AND prepared_at IS NULL",(oid,)):
            c.execute("UPDATE release_orders SET status='prepared' WHERE id=?",(oid,))
            notify(c,o['warehouse'],'release',oid,'Ordre de sortie préparé',f"{o['reference']} : autorisation de libération requise.",u['username'])
    return {'ok':True}

@app.post('/api/release-orders/{oid}/authorize')
def authorize_release_order(oid:str,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with tx() as c:
        o=_order(c,u,oid);require(o['status']=='prepared','Préparation et contrôle de toutes les unités requis avant autorisation',409)
        for line in _order_lines(c,oid):
            if line['status']=='requested':_unit_releasable(c,one(c,'SELECT * FROM units WHERE id=?',(line['unit_id'],)))
        c.execute("UPDATE releases SET status='authorized',authorized_by=? WHERE order_id=? AND status='requested'",(u['username'],oid))
        c.execute("UPDATE release_orders SET status='authorized',authorized_by=?,authorized_at=? WHERE id=?",(u['username'],now(),oid))
        audit(c,u['username'],'authorize','release_order',oid)
        notify(c,o['warehouse'],'release',oid,'Sortie autorisée',f"{o['reference']} : remise au transporteur après signature.",u['username'])
    return {'ok':True}

@app.post('/api/release-orders/{oid}/complete')
def complete_release_order(oid:str,x:OrderHandover,u=Depends(auth),idempotency_key:Optional[str]=Header(None,alias='Idempotency-Key')):
    role(u,'worker','leader','manager','admin')
    require(x.signature_consent,'Le transporteur doit confirmer la signature de la remise');check_signature_png(x.signature_data)
    with tx() as c:
        replay,digest=replay_request(c,u['id'],'release_order.complete',idempotency_key,{'ref':oid,'payload':x.model_dump()})
        if replay is not None:return replay
        o=_order(c,u,oid);require(o['status'] in ('authorized','partial'),'Autorisation exploitation requise ou ordre déjà remis',409)
        require(one(c,'SELECT id FROM drivers WHERE id=?',(x.driver_id,)),'Transporteur inconnu')
        pending=[l for l in _order_lines(c,oid) if l['status']=='authorized']
        if x.unit_ids is not None:
            wanted=set(x.unit_ids);require(wanted and wanted<={l['unit_id'] for l in pending},'Unités à remettre absentes ou déjà remises')
            pending=[l for l in pending if l['unit_id'] in wanted]
        require(pending,'Aucune unité à remettre',409)
        hid=uid('REM');t=now()
        for line in pending:
            unit=one(c,'SELECT * FROM units WHERE id=?',(line['unit_id'],));_unit_releasable(c,unit)
            require(unit['quantity']>=line['quantity'],f"Quantité insuffisante pour {unit['id']}")
            remaining=unit['quantity']-line['quantity']
            new_weight=round(unit['weight']*remaining/unit['quantity'],3) if unit['quantity'] else 0
            c.execute("UPDATE units SET quantity=?,weight=?,status=CASE WHEN ?=0 THEN 'exited' ELSE status END,version=version+1 WHERE id=?",(remaining,new_weight,remaining,unit['id']))
            c.execute("UPDATE releases SET status='completed',driver_id=?,signature_name=?,completed=?,handover_id=?,weight_out=? WHERE id=?",(x.driver_id,x.signature_name,t,hid,round(unit['weight']-new_weight,3),line['id']))
            event(c,u['username'],unit['id'],'exit',unit['location_id'],None,line['quantity'],oid)
        c.execute('INSERT INTO release_handovers(id,order_id,driver_id,signature_name,signature_data,signed_at,actor,unit_ids) VALUES(?,?,?,?,?,?,?,?)',(hid,oid,x.driver_id,x.signature_name,x.signature_data,t,u['username'],json.dumps([l['unit_id'] for l in pending])))
        status='partial' if one(c,"SELECT id FROM releases WHERE order_id=? AND status='authorized'",(oid,)) else 'completed'
        c.execute('UPDATE release_orders SET status=? WHERE id=?',(status,oid))
        audit(c,u['username'],'handover','release_order',oid,{'handover':hid,'units':[l['unit_id'] for l in pending],'driver':x.driver_id})
        notify(c,o['warehouse'],'release',oid,'Sortie remise' if status=='completed' else 'Sortie partielle remise',f"{o['reference']} : {len(pending)} unité(s) remise(s) et signée(s)."+(' Reliquat en attente.' if status=='partial' else ''),u['username'])
        response={'ok':True,'status':status,'handover_id':hid};save_request(c,u['id'],'release_order.complete',idempotency_key,digest,response)
    return response

@app.post('/api/release-orders/{oid}/refuse-signature')
def refuse_release_signature(oid:str,x:OrderRefusal,u=Depends(auth)):
    role(u,'worker','leader','manager','admin')
    with tx() as c:
        o=_order(c,u,oid);require(o['status'] in ('authorized','partial'),'Aucune remise en cours',409)
        c.execute('INSERT INTO release_refusals(id,order_id,driver_id,reason,actor,created) VALUES(?,?,?,?,?,?)',(uid('RFS'),oid,x.driver_id,x.reason,u['username'],now()))
        audit(c,u['username'],'signature_refused','release_order',oid,{'reason':x.reason,'driver':x.driver_id})
        notify(c,o['warehouse'],'release',oid,'Refus de signature transporteur',f"{o['reference']} : {x.reason}"[:350],u['username'])
    return {'ok':True,'status':o['status']}

@app.post('/api/release-orders/{oid}/cancel')
def cancel_release_order(oid:str,x:OrderCancel,u=Depends(auth)):
    role(u,'exploitation','manager','admin')
    with tx() as c:
        o=_order(c,u,oid);require(o['status'] in ('requested','prepared','authorized','partial'),'Ordre déjà clôturé',409)
        c.execute("UPDATE releases SET status='cancelled' WHERE order_id=? AND status IN ('requested','authorized')",(oid,))
        status='closed_partial' if one(c,"SELECT id FROM releases WHERE order_id=? AND status='completed'",(oid,)) else 'cancelled'
        c.execute('UPDATE release_orders SET status=?,closed_by=?,closed_at=?,close_reason=? WHERE id=?',(status,u['username'],now(),x.reason,oid))
        audit(c,u['username'],'cancel','release_order',oid,{'reason':x.reason,'status':status})
        notify(c,o['warehouse'],'release',oid,'Ordre de sortie annulé' if status=='cancelled' else 'Reliquat de sortie annulé',f"{o['reference']} : {x.reason}"[:350],u['username'])
    return {'ok':True,'status':status}

@app.get('/api/release-orders/{oid}/handovers/{hid}/pdf')
def release_order_handover_pdf(oid:str,hid:str,u=Depends(auth)):
    with db() as c:
        o=_order(c,u,oid)
        h=one(c,'SELECT * FROM release_handovers WHERE id=? AND order_id=?',(hid,oid));require(h,'Remise inconnue',404)
        lines=q(c,'SELECT r.*,u.unit_type,u.unit_index,u.unit_count,u.description,r2.awb,cl.name client FROM releases r JOIN units u ON u.id=r.unit_id LEFT JOIN receipts r2 ON r2.id=u.receipt_id LEFT JOIN clients cl ON cl.id=r2.client_id WHERE r.handover_id=? ORDER BY r.created,r.id',(hid,))
        remaining=q(c,"SELECT unit_id,quantity FROM releases WHERE order_id=? AND status='authorized'",(oid,))
        driver=one(c,'SELECT * FROM drivers WHERE id=?',(h['driver_id'],))
    from app.pdf_report import handover_report
    raw=handover_report(o,h,lines,remaining,driver,now())
    return Response(content=raw,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="bon-remise-{oid}-{hid}.pdf"'})

@app.get('/api/releases/{rid}/handover-pdf')
def handover_pdf(rid:str,u=Depends(auth)):
    """Bon de remise d'une sortie unitaire (ancien circuit), au même format que les ordres de sortie."""
    with db() as c:
        r=one(c,'SELECT * FROM releases WHERE id=?',(rid,));require(r,'Sortie inconnue',404)
        unit=unit_access(c,u,r['unit_id'])
        require(r['status']=='completed' and (r['signature_data'] or r.get('handover_id')),'Remise non signée',409)
        line=one(c,'SELECT r.*,un.unit_type,un.unit_index,un.unit_count,un.description,rc.awb,cl.name client FROM releases r JOIN units un ON un.id=r.unit_id LEFT JOIN receipts rc ON rc.id=un.receipt_id LEFT JOIN clients cl ON cl.id=rc.client_id WHERE r.id=?',(rid,))
        driver=one(c,'SELECT * FROM drivers WHERE id=?',(r['driver_id'],))
    if line.get('weight_out') is None:line['weight_out']=None
    order={'id':rid,'reference':rid,'warehouse':unit['warehouse'],'authorized_by':r['authorized_by']}
    handover={'id':rid,'actor':r.get('requested_by'),'signed_at':r['completed'],'signature_name':r['signature_name'],'signature_data':r['signature_data']}
    from app.pdf_report import handover_report
    raw=handover_report(order,handover,[line],[],driver,now())
    return Response(content=raw,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="remise-{rid}.pdf"'})
@app.get('/api/missions')
def missions(u=Depends(auth)):
    t=now()
    with db() as c:
        rows=q(c,'SELECT * FROM missions WHERE warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY created DESC LIMIT 500',u['warehouses'])
        for m in rows:
            m['events']=q(c,'SELECT actor,action,note,created FROM mission_events WHERE mission_id=? ORDER BY created,id',(m['id'],))
            m['late']=bool(m.get('due_at') and m['status'] in ('to_assign','assigned','in_progress','suspended','open') and m['due_at']<t[:16])
            ids=json.loads(m.get('unit_ids') or '[]')
            if ids:
                done=[e['note'] for e in m['events'] if e['action']=='check']
                m['units']=sorted([dict(un,checked=un['id'] in done) for un in (one(c,'SELECT id,unit_type,unit_index,unit_count,quantity,weight,location_id,length_cm,width_cm,height_cm,status,hold FROM units WHERE id=?',(i,)) for i in ids) if un],key=lambda x:(x['checked'],x['location_id'] or 'ZZZ',x['id']))
                m['checked']=len(done)
    return rows
def _mission_assignee(c,warehouse_,name):
    if not name.strip():return None
    a=one(c,'SELECT username,warehouses FROM users WHERE lower(username)=? AND active=1 AND deleted_at IS NULL',(name.strip().lower(),))
    require(a and warehouse_ in json.loads(a['warehouses']),'Collaborateur inconnu ou non habilité pour cet entrepôt');return a['username']
@app.post('/api/missions')
def create_mission(x:MissionCreate,u=Depends(auth)):
    role(u,'exploitation','manager','admin','leader');warehouse(x.warehouse);access(u,x.warehouse)
    with tx() as c:
        who=_mission_assignee(c,x.warehouse,x.assignee)
        i=uid('MIS');c.execute('INSERT INTO missions(id,warehouse,title,leader,status,created,closed,type,assignee,priority,due_at,description,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                               (i,x.warehouse,x.title,x.leader,'assigned' if who else 'to_assign',now(),None,x.type,who,x.priority,x.due_at,x.description,u['username']))
        audit(c,u['username'],'create','mission',i,{'type':x.type,'assignee':who,'priority':x.priority,'due_at':x.due_at})
        notify(c,x.warehouse,'mission',i,'Nouvelle mission'+(f' pour {who}' if who else ' à affecter'),x.title,u['username'])
    return {'id':i}
MISSION_FLOW={'take':({'to_assign'},'in_progress'),'start':({'assigned'},'in_progress'),'suspend':({'in_progress'},'suspended'),'resume':({'suspended'},'in_progress'),
              'complete':({'in_progress'},'done'),'cancel':({'to_assign','assigned','in_progress','suspended','open'},'cancelled')}
@app.post('/api/missions/{mid}/status')
def mission_status(mid:str,x:MissionAction,u=Depends(auth)):
    with tx() as c:
        m=one(c,'SELECT * FROM missions WHERE id=?',(mid,));require(m,'Mission inconnue',404);access(u,m['warehouse'])
        allowed,target=MISSION_FLOW[x.action]
        require(m['status'] in allowed,'Action impossible dans l’état actuel de la mission',409)
        office=u['role'] in ('superadmin','admin','manager','exploitation')
        if x.action=='cancel':require(office,'Annulation réservée à l’exploitation et aux responsables',403)
        elif x.action=='take':pass  # toute personne habilitée sur l'entrepôt peut prendre en charge une mission en attente
        else:require(m['assignee']==u['username'] or u['role'] in ('superadmin','admin','manager','leader'),'Mission affectée à un autre collaborateur',403)
        if x.action in ('suspend','cancel'):require(len(x.note.strip())>=3,'Motif obligatoire')
        if x.action=='complete':
            todo=[i for i in json.loads(m.get('unit_ids') or '[]') if i not in mission_checked(c,mid)]
            require(not todo,f'{len(todo)} unité(s) restant à scanner : '+', '.join(todo[:5]),409)
            require(len(x.note.strip())>=3 or m.get('unit_ids'),'Compte rendu obligatoire')
        sets={'take':'assignee=?,started_at=COALESCE(started_at,?)','start':'started_at=COALESCE(started_at,?)','complete':'completed_at=?,completed_by=?','cancel':'closed=?'}.get(x.action)
        vals={'take':(u['username'],now()),'start':(now(),),'complete':(now(),u['username']),'cancel':(now(),)}.get(x.action,())
        c.execute(f"UPDATE missions SET status=?{','+sets if sets else ''} WHERE id=?",(target,*vals,mid))
        c.execute('INSERT INTO mission_events(id,mission_id,actor,action,note,created) VALUES(?,?,?,?,?,?)',(uid('MEV'),mid,u['username'],x.action,x.note.strip(),now_precise()))
        audit(c,u['username'],'mission_'+x.action,'mission',mid,{'note':x.note})
        if x.action in ('take','suspend','complete','cancel'):notify(c,m['warehouse'],'mission',mid,{'take':f"Mission prise en charge par {u['username']}",'suspend':'Mission suspendue','complete':'Mission terminée','cancel':'Mission annulée'}[x.action],(f"{m['title']} : {x.note}" if x.note else m['title'])[:300],u['username'])
    return {'ok':True,'status':target}
def mission_checked(c,mid):
    return [e['note'] for e in q(c,"SELECT note FROM mission_events WHERE mission_id=? AND action='check' ORDER BY created,id",(mid,))]
@app.post('/api/missions/{mid}/check')
def mission_check(mid:str,x:MissionCheck,u=Depends(auth)):
    """Le magasinier confirme chaque unité en scannant son étiquette."""
    uid_=x.unit_id.strip()
    if uid_.startswith('TAF:UNIT:'):uid_=uid_[9:]
    with tx() as c:
        m=one(c,'SELECT * FROM missions WHERE id=?',(mid,));require(m,'Mission inconnue',404);access(u,m['warehouse'])
        require(m['status']=='in_progress','Prendre la mission en charge d’abord',409)
        require(m['assignee']==u['username'] or u['role'] in ('superadmin','admin','manager','leader'),'Mission affectée à un autre collaborateur',403)
        ids=json.loads(m.get('unit_ids') or '[]');require(uid_ in ids,f'Cette étiquette ({uid_}) ne fait pas partie de la mission',400)
        done=mission_checked(c,mid);require(uid_ not in done,'Unité déjà scannée',409)
        c.execute('INSERT INTO mission_events(id,mission_id,actor,action,note,created) VALUES(?,?,?,?,?,?)',(uid('MEV'),mid,u['username'],'check',uid_,now_precise()))
        audit(c,u['username'],'mission_check','mission',mid,{'unit':uid_})
    return {'ok':True,'checked':len(done)+1,'total':len(ids)}
@app.post('/api/missions/{mid}/assign')
def mission_assign(mid:str,x:MissionAssign,u=Depends(auth)):
    role(u,'exploitation','manager','admin','leader')
    with tx() as c:
        m=one(c,'SELECT * FROM missions WHERE id=?',(mid,));require(m,'Mission inconnue',404);access(u,m['warehouse'])
        require(m['status'] in ('to_assign','assigned','suspended'),'Mission terminée ou annulée',409)
        who=_mission_assignee(c,m['warehouse'],x.assignee);require(who,'Collaborateur obligatoire')
        c.execute("UPDATE missions SET assignee=?,status=CASE WHEN status='to_assign' THEN 'assigned' ELSE status END WHERE id=?",(who,mid))
        c.execute('INSERT INTO mission_events(id,mission_id,actor,action,note,created) VALUES(?,?,?,?,?,?)',(uid('MEV'),mid,u['username'],'assign',who,now_precise()))
        audit(c,u['username'],'mission_assign','mission',mid,{'assignee':who});notify(c,m['warehouse'],'mission',mid,f'Mission affectée à {who}',m['title'],u['username'])
    return {'ok':True}
@app.post('/api/missions/{mid}/tasks')
def add_task(mid:str,x:TaskCreate,u=Depends(auth)):
    with tx() as c:
        m=one(c,'SELECT * FROM missions WHERE id=?',(mid,));require(m,'Mission inconnue',404);access(u,m['warehouse']);require(m['status'] in MISSION_OPEN,'Mission clôturée')
        i=uid('TSK');c.execute('INSERT INTO tasks(id,mission_id,title,assignee,status) VALUES(?,?,?,?,?)',(i,mid,x.title,x.assignee,'open'));audit(c,u['username'],'create','task',i)
    return {'id':i}
@app.get('/api/tasks')
def tasks(u=Depends(auth)):
    with db() as c:return q(c,'SELECT t.* FROM tasks t JOIN missions m ON m.id=t.mission_id WHERE m.warehouse IN ('+','.join('?' for _ in u['warehouses'])+')',u['warehouses'])
@app.post('/api/tasks/{tid}/done')
def task_done(tid:str,u=Depends(auth)):
    with tx() as c:
        t=one(c,'SELECT t.*,m.warehouse,m.status mission_status FROM tasks t JOIN missions m ON m.id=t.mission_id WHERE t.id=?',(tid,));require(t,'Tâche inconnue',404);access(u,t['warehouse']);require(t['mission_status'] in MISSION_OPEN,'Mission clôturée')
        require(not t['assignee'] or t['assignee']==u['username'] or u['role'] in ('superadmin','admin','manager','leader'),'Tâche attribuée à un autre utilisateur',403)
        c.execute("UPDATE tasks SET status='done',completed_at=?,completed_by=? WHERE id=?",(now(),u['username'],tid));audit(c,u['username'],'done','task',tid)
    return {'ok':True}
@app.post('/api/missions/{mid}/close')
def close_mission(mid:str,u=Depends(auth)):
    role(u,'leader','exploitation','manager','admin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');m=one(c,'SELECT * FROM missions WHERE id=?',(mid,));require(m,'Mission inconnue',404);access(u,m['warehouse']);require(m['status'] in MISSION_OPEN,'Mission déjà clôturée')
        require(not one(c,"SELECT id FROM tasks WHERE mission_id=? AND status!='done'",(mid,)),'Tâches non terminées')
        c.execute("UPDATE missions SET status='closed',closed=? WHERE id=?",(now(),mid));audit(c,u['username'],'close','mission',mid);c.commit()
    return {'ok':True}
@app.get('/api/incidents')
def incidents(u=Depends(auth)):
    with db() as c:return q(c,'SELECT * FROM incidents WHERE warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY created DESC',u['warehouses'])
@app.post('/api/incidents')
def create_incident(x:IncidentCreate,u=Depends(auth)):
    access(u,x.warehouse);require(x.severity in ['minor','major','critical'],'Gravité invalide')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if x.unit_id:
            unit=unit_access(c,u,x.unit_id);require(unit['warehouse']==x.warehouse,'Entrepôt incohérent')
        i=uid('INC');c.execute('INSERT INTO incidents(id,warehouse,unit_id,location_id,category,severity,description,status,created,actor) VALUES(?,?,?,?,?,?,?,?,?,?)',(i,x.warehouse,x.unit_id,x.location_id,x.category,x.severity,x.description,'open',now(),u['username']))
        if x.unit_id and x.severity in ('major','critical'):
            add_hold(c,u['username'],x.unit_id,'incident','Incident '+i,i)
        audit(c,u['username'],'declare','incident',i,{'severity':x.severity});notify(c,x.warehouse,'incident',i,'Incident '+x.severity,x.description[:350],u['username']);c.commit()
    return {'id':i}
@app.post('/api/incidents/{iid}/update')
def update_incident(iid:str,x:IncidentUpdate,u=Depends(auth)):
    role(u,'manager','exploitation','admin');require(x.status in ('open','investigating','resolved','closed'),'Statut invalide')
    with tx() as c:
        i=one(c,'SELECT * FROM incidents WHERE id=?',(iid,));require(i,'Incident inconnu',404);access(u,i['warehouse'])
        require(x.status not in ('resolved','closed') or x.resolution.strip(),'Résolution obligatoire')
        c.execute('UPDATE incidents SET status=?,resolution=?,owner=? WHERE id=?',(x.status,x.resolution,x.owner,iid));audit(c,u['username'],'update','incident',iid,{'status':x.status})
    return {'ok':True,'note':'Les blocages ne sont jamais levés automatiquement'}
@app.get('/api/claims')
def claims(u=Depends(auth)):
    with db() as c:return q(c,'SELECT * FROM claims WHERE warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY created DESC',u['warehouses'])
@app.post('/api/claims')
def create_claim(x:ClaimCreate,u=Depends(auth)):
    role(u,'exploitation','manager','admin');access(u,x.warehouse)
    with tx() as c:
        i=uid('LIT');c.execute('INSERT INTO claims(id,incident_id,warehouse,client_id,description,status,deadline,owner,decision,created,actor) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(i,x.incident_id,x.warehouse,x.client_id,x.description,'open',x.deadline,x.owner,None,now(),u['username']));audit(c,u['username'],'open','claim',i);notify(c,x.warehouse,'claim',i,'Nouveau litige',x.description[:350],u['username'])
    return {'id':i}
@app.post('/api/claims/{cid}/update')
def update_claim(cid:str,x:ClaimUpdate,u=Depends(auth)):
    role(u,'exploitation','manager','admin');require(x.status in ('open','investigating','pending','resolved','closed'),'Statut invalide')
    with tx() as c:
        cl=one(c,'SELECT * FROM claims WHERE id=?',(cid,));require(cl,'Litige inconnu',404);access(u,cl['warehouse'])
        require(x.status not in ('resolved','closed') or x.decision.strip(),'Décision motivée obligatoire')
        require(x.status!='closed','Utiliser la clôture contrôlée du litige')
        c.execute('UPDATE claims SET status=?,decision=?,owner=? WHERE id=?',(x.status,x.decision,x.owner,cid));audit(c,u['username'],'update','claim',cid,{'status':x.status})
    return {'ok':True}
DOC_TABLES={'receipt':'receipts','incident':'incidents','claim':'claims','mission':'missions','unit':'units'}
# Pièces d'identité des chauffeurs : donnée personnelle. Le magasin les dépose, seuls ces rôles les consultent.
IDENTITY_ROLES={'superadmin','admin','manager','exploitation'}
def doc_access(c,u,kind,ref,write=False):
    """Un document suit les habilitations de son dossier ; un transfert est visible au départ et à l'arrivée."""
    require(kind in DOC_TABLES or kind in ('transfer','driver'),'Type invalide')
    if kind=='driver':
        require(one(c,'SELECT id FROM drivers WHERE id=?',(ref,)),'Chauffeur introuvable',404)
        require(write or u['role'] in IDENTITY_ROLES,'Pièce d’identité réservée à l’exploitation et aux responsables',403)
    elif kind=='transfer':
        t=one(c,'SELECT source,destination FROM transfers WHERE id=?',(ref,));require(t,'Dossier introuvable',404)
        require(t['source'] in u['warehouses'] or t['destination'] in u['warehouses'],'Accès entrepôt refusé',403)
    else:
        row=one(c,f'SELECT warehouse FROM {DOC_TABLES[kind]} WHERE id=?',(ref,));require(row,'Dossier introuvable',404);access(u,row['warehouse'])

@app.post('/api/documents/{kind}/{ref}')
async def upload(kind:str,ref:str,file:UploadFile=File(...),category:str=Query('',max_length=20),u=Depends(auth)):
    require(category in ('','transport','photo','autre'),'Catégorie de document invalide')
    with db() as c:doc_access(c,u,kind,ref,write=True)
    # 9 Mo : la passerelle HTTPS d'AWS limite chaque requête à 10 Mo (fichier + enveloppe multipart).
    raw=await file.read(9*1024*1024+1);require(len(raw)<=9*1024*1024,'Fichier supérieur à 9 Mo : réduire la taille ou la résolution de la photo')
    require(raw[:4]==b'%PDF' or raw[:3]==b'\xff\xd8\xff' or raw[:8]==b'\x89PNG\r\n\x1a\n','PDF, JPG ou PNG uniquement')
    ext='.pdf' if raw[:4]==b'%PDF' else ('.png' if raw[:8]==b'\x89PNG\r\n\x1a\n' else '.jpg')
    i=uid('DOC');ref_path=store_ref(i+ext);mime={'.pdf':'application/pdf','.png':'image/png','.jpg':'image/jpeg'}[ext]
    try:
        with tx() as c:
            c.execute('INSERT INTO documents(id,kind,ref,name,mime,sha256,path,uploaded,actor,category) VALUES(?,?,?,?,?,?,?,?,?,?)',(i,kind,ref,Path(file.filename or 'document').name,mime,hashlib.sha256(raw).hexdigest(),ref_path,now(),u['username'],category))
            audit(c,u['username'],'upload','document',i,{'kind':kind,'ref':ref,'category':category,'name':Path(file.filename or 'document').name})
            if kind=='receipt':audit(c,u['username'],'add_document','receipt',ref,{'name':Path(file.filename or 'document').name,'category':category or 'autre'})
            store_put(ref_path,raw,mime)  # écrit avant validation : en cas d'échec, ligne annulée et fichier supprimé
    except BaseException:
        store_delete(ref_path);raise
    return {'id':i,'sha256':hashlib.sha256(raw).hexdigest()}
@app.get('/api/documents')
def documents(kind:str,ref:str,u=Depends(auth)):
    with db() as c:
        doc_access(c,u,kind,ref)
        return q(c,'SELECT id,kind,ref,name,mime,sha256,uploaded,actor,category FROM documents WHERE kind=? AND ref=?',(kind,ref))
@app.get('/api/documents/{did}/download')
def download(did:str,u=Depends(auth)):
    with db() as c:
        d=one(c,'SELECT * FROM documents WHERE id=?',(did,));require(d,'Document introuvable',404)
        doc_access(c,u,d['kind'],d['ref'])
    raw=store_get(d['path'])
    with tx() as c:audit(c,u['username'],'download','document',did,{'kind':d['kind'],'ref':d['ref']})
    return Response(content=raw,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{Path(d["path"]).name}"'})
def _label_rows(c,u,ids):
    rows=[]
    for unit_id in ids:
        unit=unit_access(c,u,unit_id)
        r=one(c,'SELECT r.id,r.awb,c.name client FROM receipts r JOIN clients c ON c.id=r.client_id WHERE r.id=?',(unit['receipt_id'],)) if unit['receipt_id'] else None
        rows.append((unit,r or {}))
    return rows
def _draw_label(pdf,unit,rec):
    """Étiquette thermique 80 x 130 mm. Le QR code ne contient que l'identifiant de l'unité."""
    import qrcode
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    W,H=80*mm,130*mm
    pdf.setFillColorRGB(.06,.17,.28);pdf.rect(0,H-16*mm,W,16*mm,fill=1,stroke=0)
    pdf.setFillColorRGB(1,1,1);pdf.setFont('Helvetica-Bold',17);pdf.drawString(6*mm,H-11*mm,'TAF')
    pdf.setFont('Helvetica',6.5);pdf.drawString(19*mm,H-10.5*mm,'TRANS AIR FREIGHT · WAREHOUSE')
    pdf.setFillColorRGB(0,0,0)
    if unit.get('unit_index') and unit.get('unit_count'):
        pdf.setFont('Helvetica-Bold',30);pdf.drawRightString(W-5*mm,H-30*mm,f"{unit['unit_index']}/{unit['unit_count']}")
        pdf.setFont('Helvetica',7);pdf.drawRightString(W-5*mm,H-34*mm,('PALETTE' if unit.get('unit_type')=='palette' else 'COLIS'))
    pdf.setFont('Helvetica-Bold',9);pdf.drawString(5*mm,H-23*mm,'Client');pdf.setFont('Helvetica-Bold',11);pdf.drawString(5*mm,H-28*mm,str(rec.get('client') or '—')[:24])
    pdf.setFont('Helvetica',8);pdf.drawString(5*mm,H-34*mm,'LTA : '+str(rec.get('awb') or '—')[:26])
    qr=qrcode.make(unit['id']);pdf.drawImage(ImageReader(qr.get_image().convert('RGB')),17*mm,40*mm,46*mm,46*mm)
    pdf.setFont('Helvetica-Bold',10);pdf.drawCentredString(W/2,36*mm,unit['id'])
    weight=f"{float(unit['weight'] or 0):.1f}".rstrip('0').rstrip('.').replace('.',',')
    lines=[('Réception',rec.get('id') or '—'),('Poids',f"{weight} kg · {unit['quantity']} colis"),('Entrepôt',unit['warehouse']),('Emplacement',unit.get('location_id') or 'À RANGER')]
    y=29
    for k,v in lines:
        pdf.setFont('Helvetica',7);pdf.drawString(5*mm,y*mm,k);pdf.setFont('Helvetica-Bold',8.5);pdf.drawString(24*mm,y*mm,str(v)[:30]);y-=6
def _record_prints(c,u,ids,batch=None):
    for unit_id in ids:
        reprint=1 if one(c,'SELECT 1 x FROM label_prints WHERE unit_id=? LIMIT 1',(unit_id,)) else 0
        c.execute('INSERT INTO label_prints(id,unit_id,actor,printed_at,reprint,batch) VALUES(?,?,?,?,?,?)',(uid('PRT'),unit_id,u['username'],now(),reprint,batch))
    audit(c,u['username'],'label_print','unit',ids[0] if len(ids)==1 else ','.join(ids)[:200],{'units':len(ids),'batch':batch})
@app.get('/api/labels/{unit_id}')
def label(unit_id:str,u=Depends(auth)):
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    with db() as c:rows=_label_rows(c,u,[unit_id])
    buff=io.BytesIO();p=canvas.Canvas(buff,pagesize=(80*mm,130*mm));_draw_label(p,*rows[0]);p.save()
    with tx() as c:_record_prints(c,u,[unit_id])
    buff.seek(0);return StreamingResponse(buff,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="etiquette-{unit_id}.pdf"'})
@app.get('/api/labels-batch')
def labels_batch(ids:str,u=Depends(auth)):
    """Planche d'etiquettes thermiques 80 x 130 mm, une page par unite."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    requested=[v.strip() for v in ids.split(',') if v.strip()]
    require(0<len(requested)<=40 and len(requested)==len(set(requested)),'Entre 1 et 40 identifiants distincts requis')
    with db() as c:rows=_label_rows(c,u,requested)
    out=io.BytesIO();pdf=canvas.Canvas(out,pagesize=(80*mm,130*mm))
    for unit,rec in rows:_draw_label(pdf,unit,rec);pdf.showPage()
    pdf.save()
    with tx() as c:_record_prints(c,u,requested,uid('LOT'))
    out.seek(0)
    return StreamingResponse(out,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="taf-etiquettes-80x130.pdf"'})
@app.get('/api/labels/{unit_id}/history')
def label_history(unit_id:str,u=Depends(auth)):
    with db() as c:
        unit_access(c,u,unit_id)
        return q(c,'SELECT actor,printed_at,reprint,batch FROM label_prints WHERE unit_id=? ORDER BY printed_at,reprint,id',(unit_id,))

@app.get('/api/reports/{kind}/{ref}')
def report(kind:str,ref:str,u=Depends(auth)):
    require(kind in ('incident','claim','mission'),'Rapport inconnu')
    table={'incident':'incidents','claim':'claims','mission':'missions'}[kind]
    with db() as c:
        item=one(c,f'SELECT * FROM {table} WHERE id=?',(ref,));require(item,'Dossier inconnu',404);access(u,item['warehouse'])
        logs=q(c,'SELECT at,actor,action,details FROM audit WHERE kind=? AND ref=? ORDER BY at,id',(kind,ref))
        docs=q(c,'SELECT name,sha256,uploaded,actor FROM documents WHERE kind=? AND ref=? ORDER BY uploaded',(kind,ref))
        extra=q(c,'SELECT actor,action,note,created FROM claim_actions WHERE claim_id=? ORDER BY created',(ref,)) if kind=='claim' else q(c,'SELECT actor,action,note,created FROM mission_events WHERE mission_id=? ORDER BY created',(ref,)) if kind=='mission' else []
    if kind=='mission':
        with db() as c:
            ids=json.loads(item.get('unit_ids') or '[]')
            units=[one(c,'SELECT * FROM units WHERE id=?',(i,)) for i in ids];units=[x for x in units if x]
            rec=one(c,'SELECT r.*,cl.name client FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.id=?',(item['receipt_id'],)) if item.get('receipt_id') else None
        from app.pdf_report import mission_report
        raw=mission_report(item,extra,units,rec,docs,now())
        return Response(content=raw,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="mission-{ref}.pdf"'})
    from app.pdf_report import dossier_report
    raw=dossier_report(kind,item,logs,docs,extra,now())
    return Response(content=raw,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="rapport-{ref}.pdf"'})
@app.get('/api/audit')
def audit_log(u=Depends(auth)):
    role(u,'admin','exploitation','manager')
    with db() as c:
        if u['role']=='superadmin':
            return q(c,'SELECT * FROM audit ORDER BY at DESC,id DESC LIMIT 300')
        permitted=u['warehouses']
        require(bool(permitted),'Aucun entrepôt autorisé',403)
        marks=','.join('?' for _ in permitted)
        mappings={'unit':'units','receipt':'receipts','incident':'incidents','claim':'claims','mission':'missions','count':'counts'}
        clauses=[];params=[]
        for kind,table in mappings.items():
            clauses.append(f'(a.kind=? AND EXISTS (SELECT 1 FROM {table} x WHERE x.id=a.ref AND x.warehouse IN ({marks})))')
            params.extend([kind,*permitted])
        clauses.append(f"(a.kind='transfer' AND EXISTS (SELECT 1 FROM transfers t WHERE t.id=a.ref AND (t.source IN ({marks}) OR t.destination IN ({marks}))))")
        params.extend([*permitted,*permitted])
        clauses.append(f"(a.kind='release' AND EXISTS (SELECT 1 FROM releases r JOIN units x ON x.id=r.unit_id WHERE r.id=a.ref AND x.warehouse IN ({marks})))")
        params.extend(permitted)
        return q(c,'SELECT a.* FROM audit a WHERE '+' OR '.join(clauses)+' ORDER BY a.at DESC,a.id DESC LIMIT 300',params)
@app.get('/api/notifications')
def notifications(u=Depends(auth)):
    with db() as c:
        marks=','.join('?' for _ in u['warehouses'])
        return q(c,f'''SELECT n.*,CASE WHEN r.notification_id IS NULL THEN 0 ELSE 1 END AS is_read
          FROM notifications n LEFT JOIN notification_reads r ON r.notification_id=n.id AND r.user_id=?
          WHERE n.warehouse IN ({marks}) ORDER BY n.created DESC LIMIT 200''',[u['id'],*u['warehouses']])

@app.post('/api/notifications/{nid}/read')
def mark_notification(nid:str,u=Depends(auth)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        n=one(c,'SELECT * FROM notifications WHERE id=?',(nid,))
        require(n,'Notification inconnue',404);access(u,n['warehouse'])
        c.execute('INSERT INTO notification_reads VALUES(?,?,?) ON CONFLICT DO NOTHING',(nid,u['id'],now()))
        c.commit()
    return {'ok':True}

@app.get('/api/dashboard/ops')
def dashboard_ops(warehouse:Optional[str]=None,u=Depends(auth)):
    """Indicateurs réels et situations à traiter, filtrés par entrepôt habilité."""
    whs=u['warehouses']
    if warehouse:access(u,warehouse);whs=[warehouse]
    m=','.join('?' for _ in whs);w=tuple(whs);t=now();day=t[:10]
    ago=lambda h:(datetime.now(timezone.utc)-timedelta(hours=h)).isoformat(timespec='seconds')
    with db() as c:
        n=lambda sql,args=():c.execute(sql,w+tuple(args)).fetchone()[0]
        present=one(c,f"SELECT COUNT(*) n,COALESCE(SUM(quantity),0) colis,COALESCE(SUM(weight),0) kg FROM units WHERE warehouse IN ({m}) AND status IN ('available','awaiting_putaway')",w)
        used=n(f"SELECT COUNT(DISTINCT location_id) FROM units WHERE warehouse IN ({m}) AND status='available' AND location_id IS NOT NULL")
        locs=n(f"SELECT COUNT(*) FROM locations WHERE warehouse IN ({m})")
        open_m=('to_assign','assigned','in_progress','suspended','open')
        kpis={'receipts_today':n(f"SELECT COUNT(*) FROM receipts WHERE warehouse IN ({m}) AND created>=?",(day,)),
              'units_present':present['n'],'packages_present':present['colis'],'weight_kg':round(present['kg'],1),
              'awaiting_putaway':n(f"SELECT COUNT(*) FROM units WHERE warehouse IN ({m}) AND status='awaiting_putaway'"),
              'held_units':n(f"SELECT COUNT(*) FROM units WHERE warehouse IN ({m}) AND hold!='' AND status NOT IN ('exited','depleted')"),
              'locations_used':used,'locations_total':locs,'occupancy_pct':round(100*used/locs,1) if locs else 0,
              'orders_to_prepare':n(f"SELECT COUNT(*) FROM release_orders WHERE warehouse IN ({m}) AND status='requested'"),
              'orders_to_authorize':n(f"SELECT COUNT(*) FROM release_orders WHERE warehouse IN ({m}) AND status='prepared'"),
              'orders_to_hand_over':n(f"SELECT COUNT(*) FROM release_orders WHERE warehouse IN ({m}) AND status IN ('authorized','partial')"),
              'transfers_in_transit':c.execute(f"SELECT COUNT(*) FROM transfers WHERE status IN ('in_transit','discrepancy','refusal_pending','refused') AND (source IN ({m}) OR destination IN ({m}))",w+w).fetchone()[0],
              'campaigns_open':n(f"SELECT COUNT(*) FROM inventory_campaigns WHERE warehouse IN ({m}) AND status='open'"),
              'discrepancies_open':n(f"SELECT COUNT(*) FROM receipt_discrepancies WHERE warehouse IN ({m}) AND status='open'")+n(f"SELECT COUNT(*) FROM counts WHERE warehouse IN ({m}) AND status='pending'"),
              'incidents_open':n(f"SELECT COUNT(*) FROM incidents WHERE warehouse IN ({m}) AND status NOT IN ('resolved','closed')"),
              'claims_open':n(f"SELECT COUNT(*) FROM claims WHERE warehouse IN ({m}) AND status!='closed'"),
              'missions_open':n(f"SELECT COUNT(*) FROM missions WHERE warehouse IN ({m}) AND status IN ({','.join('?'*len(open_m))})",open_m),
              'missions_late':n(f"SELECT COUNT(*) FROM missions WHERE warehouse IN ({m}) AND status IN ({','.join('?'*len(open_m))}) AND due_at IS NOT NULL AND due_at<?",open_m+(t[:16],))}
        alerts=[]
        def alert(code,level,title,rows):
            if rows:alerts.append({'code':code,'level':level,'title':title,'count':len(rows),'refs':[r['ref'] for r in rows][:50]})
        alert('putaway_late','warning','Marchandise à ranger depuis plus de 24 h',q(c,f"SELECT DISTINCT u.id ref FROM units u JOIN movements mv ON mv.unit_id=u.id AND mv.kind IN ('receive','transfer_receive') WHERE u.warehouse IN ({m}) AND u.status='awaiting_putaway' AND mv.at<?",w+(ago(24),)))
        alert('orders_waiting','warning','Ordres de sortie en attente depuis plus de 48 h',q(c,f"SELECT id ref FROM release_orders WHERE warehouse IN ({m}) AND status IN ('requested','prepared','authorized','partial') AND created<?",w+(ago(48),)))
        alert('transfer_late','danger','Transferts en transit depuis plus de 72 h',q(c,f"SELECT id ref FROM transfers WHERE status='in_transit' AND dispatched_at<? AND (source IN ({m}) OR destination IN ({m}))",(ago(72),)+w+w))
        alert('incident_no_owner','danger','Incidents ouverts sans responsable',q(c,f"SELECT id ref FROM incidents WHERE warehouse IN ({m}) AND status NOT IN ('resolved','closed') AND COALESCE(owner,'')=''",w))
        alert('discrepancy_open','warning','Écarts non résolus',q(c,f"SELECT id ref FROM receipt_discrepancies WHERE warehouse IN ({m}) AND status='open' UNION SELECT id ref FROM counts WHERE warehouse IN ({m}) AND status='pending'",w+w))
        alert('missions_late','danger','Missions en retard',q(c,f"SELECT id ref FROM missions WHERE warehouse IN ({m}) AND status IN ({','.join('?'*len(open_m))}) AND due_at IS NOT NULL AND due_at<?",w+open_m+(t[:16],)))
        alert('missions_unassigned','info','Missions à affecter',q(c,f"SELECT id ref FROM missions WHERE warehouse IN ({m}) AND status='to_assign'",w))
        workload=q(c,f"SELECT assignee,COUNT(*) open,SUM(CASE WHEN due_at IS NOT NULL AND due_at<? THEN 1 ELSE 0 END) late,SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) in_progress FROM missions WHERE warehouse IN ({m}) AND assignee IS NOT NULL AND status IN ({','.join('?'*len(open_m))}) GROUP BY assignee ORDER BY open DESC",(t[:16],)+w+open_m)
        activity=q(c,f"SELECT mv.actor,COUNT(*) movements,SUM(CASE WHEN mv.kind='receive' THEN 1 ELSE 0 END) receptions,SUM(CASE WHEN mv.kind='exit' THEN 1 ELSE 0 END) sorties FROM movements mv JOIN units un ON un.id=mv.unit_id WHERE un.warehouse IN ({m}) AND mv.at>=? GROUP BY mv.actor ORDER BY movements DESC",w+(day,))
        flow={'received':kpis['receipts_today'],'awaiting_putaway':kpis['awaiting_putaway'],
              'in_stock':n(f"SELECT COUNT(*) FROM units WHERE warehouse IN ({m}) AND status='available'"),
              'preparing':n(f"SELECT COUNT(*) FROM missions WHERE warehouse IN ({m}) AND type='preparation' AND status IN ({','.join('?'*len(open_m))})",open_m),
              'exited':n(f"SELECT COUNT(DISTINCT mv.unit_id) FROM movements mv JOIN units un ON un.id=mv.unit_id WHERE un.warehouse IN ({m}) AND mv.kind='exit' AND mv.at>=?",(day,))}
        live=q(c,f"SELECT id,title,assignee,status,type,started_at FROM missions WHERE warehouse IN ({m}) AND status IN ('in_progress','assigned','suspended') AND assignee IS NOT NULL ORDER BY started_at DESC LIMIT 12",w)
        waiting=q(c,f"SELECT id,title,priority,description,created,due_at FROM missions WHERE warehouse IN ({m}) AND status='to_assign' ORDER BY CASE priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,created LIMIT 5",w)
        recent=q(c,f"SELECT r.id,r.awb,r.expected,r.actual,r.weight,r.status,r.created,r.security_status,r.apparent_condition,cl.name client,(SELECT COUNT(*) FROM units x WHERE x.receipt_id=r.id) units,(SELECT COUNT(*) FROM missions mi WHERE mi.receipt_id=r.id AND mi.status IN ('to_assign','assigned','in_progress','suspended')) missions FROM receipts r JOIN clients cl ON cl.id=r.client_id WHERE r.warehouse IN ({m}) ORDER BY r.created DESC LIMIT 6",w)
        for r in recent:r['problem']=r['status']=='discrepancy' or r['expected']!=r['actual'] or r.get('security_status') in ('a_controler','non_securise') or r.get('apparent_condition') in ('endommage','a_verifier')
    return {'generated_at':t,'warehouses':whs,'kpis':kpis,'alerts':alerts,'workload':workload,'activity':activity,'flow':flow,'live':live,'waiting':waiting,'recent':recent}

@app.get('/api/dashboard')
def dashboard(u=Depends(auth)):
    with db() as c:
        where='('+','.join('?' for _ in u['warehouses'])+')';p=u['warehouses']
        return {'units':one(c,'SELECT COUNT(*) n,COALESCE(SUM(quantity),0) quantity FROM units WHERE warehouse IN '+where,p),
                'receipts':one(c,'SELECT COUNT(*) n FROM receipts WHERE warehouse IN '+where,p)['n'],
                'holds':one(c,'SELECT COUNT(*) n FROM units WHERE warehouse IN '+where+" AND hold!=''",p)['n'],
                'incidents':one(c,'SELECT COUNT(*) n FROM incidents WHERE warehouse IN '+where+" AND status!='closed'",p)['n'],
                'claims':one(c,'SELECT COUNT(*) n FROM claims WHERE warehouse IN '+where+" AND status!='closed'",p)['n'],
                'transfers':one(c,'SELECT COUNT(*) n FROM transfers WHERE source IN '+where+" AND status='in_transit'",p)['n'],
                'releases':one(c,'SELECT COUNT(*) n FROM releases r JOIN units u ON u.id=r.unit_id WHERE u.warehouse IN '+where+" AND r.status!='completed'",p)['n']}

# V3.5 : missions, litiges, règles techniques des racks et habilitations.
@app.get('/api/rack-rules')
def rack_rules(u=Depends(auth)):
    with db() as c:return q(c,'SELECT r.* FROM rack_rules r JOIN locations l ON l.id=r.location_id WHERE l.warehouse IN ('+','.join('?' for _ in u['warehouses'])+')',u['warehouses'])

@app.put('/api/rack-rules/{lid}')
def set_rack_rule(lid:str,x:RackRule,u=Depends(auth)):
    role(u,'manager','admin')
    require(not set(x.allowed_categories)&set(x.forbidden_categories),'Catégorie à la fois autorisée et interdite')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');loc=one(c,'SELECT * FROM locations WHERE id=?',(lid,));require(loc,'Emplacement inconnu',404);access(u,loc['warehouse'])
        require(loc['verified'] and loc['capacity_kg'] and loc['capacity_m3'],'Valider d’abord la capacité technique de l’emplacement')
        require(x.max_unit_kg<=loc['capacity_kg'] and x.max_unit_m3<=loc['capacity_m3'],'Gabarit supérieur à la capacité')
        c.execute('INSERT INTO rack_rules VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(location_id) DO UPDATE SET max_unit_kg=excluded.max_unit_kg,max_unit_m3=excluded.max_unit_m3,max_units=excluded.max_units,allowed_categories=excluded.allowed_categories,forbidden_categories=excluded.forbidden_categories,verified_by=excluded.verified_by,verified_at=excluded.verified_at',(lid,x.max_unit_kg,x.max_unit_m3,x.max_units,json.dumps(x.allowed_categories),json.dumps(x.forbidden_categories),u['username']+' · '+x.technical_reference,now()))
        audit(c,u['username'],'rack_rule','location',lid,x.model_dump());c.commit()
    return {'ok':True}

@app.post('/api/missions/{mid}/plan')
def plan_mission(mid:str,x:MissionPlan,u=Depends(auth)):
    role(u,'leader','manager','exploitation','admin');require(x.priority in ('low','normal','high','urgent'),'Priorité invalide')
    with tx() as c:
        m=one(c,'SELECT * FROM missions WHERE id=?',(mid,));require(m,'Mission inconnue',404);access(u,m['warehouse']);require(m['status'] in MISSION_OPEN,'Mission clôturée')
        c.execute('UPDATE missions SET priority=?,due_at=?,description=? WHERE id=?',(x.priority,x.due_at,x.description,mid));audit(c,u['username'],'plan','mission',mid,x.model_dump())
    return {'ok':True}

@app.post('/api/tasks/{tid}/plan')
def plan_task(tid:str,x:TaskPlan,u=Depends(auth)):
    role(u,'leader','manager','exploitation','admin');require(x.priority in ('low','normal','high','urgent'),'Priorité invalide')
    with tx() as c:
        t=one(c,'SELECT t.*,m.warehouse,m.status mission_status FROM tasks t JOIN missions m ON m.id=t.mission_id WHERE t.id=?',(tid,));require(t,'Tâche inconnue',404);access(u,t['warehouse']);require(t['mission_status'] in MISSION_OPEN and t['status']!='done','Tâche non modifiable')
        if x.assignee:
            user=one(c,'SELECT * FROM users WHERE username=? AND active=1',(x.assignee,));require(user and t['warehouse'] in json.loads(user['warehouses']),'Collaborateur non habilité pour cet entrepôt')
        c.execute('UPDATE tasks SET assignee=?,priority=?,due_at=?,notes=? WHERE id=?',(x.assignee,x.priority,x.due_at,x.notes,tid));audit(c,u['username'],'plan','task',tid,x.model_dump())
    return {'ok':True}

@app.post('/api/tasks/{tid}/start')
def start_task(tid:str,x:TaskAction,u=Depends(auth)):
    with db() as c:
        c.execute('BEGIN IMMEDIATE');t=one(c,'SELECT t.*,m.warehouse,m.status mission_status FROM tasks t JOIN missions m ON m.id=t.mission_id WHERE t.id=?',(tid,));require(t,'Tâche inconnue',404);access(u,t['warehouse'])
        require(t['mission_status'] in MISSION_OPEN and t['status']=='open','Tâche non démarrable')
        require(not t['assignee'] or t['assignee']==u['username'] or u['role'] in ('superadmin','admin','manager','leader'),'Tâche attribuée à un autre utilisateur',403)
        c.execute("UPDATE tasks SET status='in_progress',started_at=? WHERE id=?",(now(),tid));c.execute('INSERT INTO task_events VALUES(?,?,?,?,?,?)',(uid('EVT'),tid,u['username'],'start',x.note,now()));audit(c,u['username'],'start','task',tid);c.commit()
    return {'ok':True}

@app.get('/api/task-events')
def task_events(u=Depends(auth)):
    with db() as c:return q(c,'SELECT e.* FROM task_events e JOIN tasks t ON t.id=e.task_id JOIN missions m ON m.id=t.mission_id WHERE m.warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY e.created DESC',u['warehouses'])

@app.post('/api/claims/{cid}/action')
def claim_action(cid:str,x:ClaimAction,u=Depends(auth)):
    role(u,'exploitation','manager','admin');require(x.action in ('investigate','request_evidence','evidence_reviewed','decision','close'),'Action invalide')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');cl=one(c,'SELECT * FROM claims WHERE id=?',(cid,));require(cl,'Litige inconnu',404);access(u,cl['warehouse']);require(cl['status']!='closed','Litige clôturé')
        if x.action=='close':
            require(cl['evidence_reviewed'],'Pièces non contrôlées')
            require(cl['decision'] and len(cl['decision'].strip())>=5,'Décision motivée manquante')
            require(not cl['owner'] or cl['owner']!=u['username'] or u['role']=='superadmin','Clôture indépendante du responsable du litige')
            c.execute("UPDATE claims SET status='closed',closed_by=?,closed_at=? WHERE id=?",(u['username'],now(),cid))
        elif x.action=='evidence_reviewed':
            require(one(c,"SELECT id FROM documents WHERE kind='claim' AND ref=? LIMIT 1",(cid,)),'Aucune pièce jointe')
            c.execute('UPDATE claims SET evidence_reviewed=1 WHERE id=?',(cid,))
        elif x.action=='decision':c.execute("UPDATE claims SET decision=?,status='resolved' WHERE id=?",(x.note,cid))
        else:c.execute('UPDATE claims SET status=? WHERE id=?',('pending' if x.action=='request_evidence' else 'investigating',cid))
        c.execute('INSERT INTO claim_actions VALUES(?,?,?,?,?,?)',(uid('ACT'),cid,u['username'],x.action,x.note,now()));audit(c,u['username'],x.action,'claim',cid,{'note':x.note});notify(c,cl['warehouse'],'claim',cid,'Litige : '+x.action,x.note[:250],u['username']);c.commit()
    return {'ok':True}

@app.get('/api/claim-actions')
def claim_actions(u=Depends(auth)):
    with db() as c:return q(c,'SELECT a.* FROM claim_actions a JOIN claims cl ON cl.id=a.claim_id WHERE cl.warehouse IN ('+','.join('?' for _ in u['warehouses'])+') ORDER BY a.created DESC',u['warehouses'])

@app.post('/api/users/{userid}/status')
def user_status(userid:str,x:UserStatus,u=Depends(auth)):
    role(u,'superadmin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');target=one(c,'SELECT * FROM users WHERE id=?',(userid,));require(target,'Utilisateur inconnu',404);require(target['id']!=u['id'],'Impossible de désactiver son propre compte')
        require(not target.get('deleted_at'),'Compte supprimé : créer un nouveau compte',409)
        c.execute('UPDATE users SET active=? WHERE id=?',(int(x.active),userid))
        if not x.active:c.execute('DELETE FROM sessions WHERE user_id=?',(userid,))
        audit(c,u['username'],'user_status','user',userid,{'active':x.active});c.commit()
    return {'ok':True}

@app.post('/api/users/{userid}/permissions')
def user_permissions(userid:str,x:UserPermissions,u=Depends(auth)):
    require(u['role']=='superadmin','Réservé au Super Admin',403)
    with db() as c:
        c.execute('BEGIN IMMEDIATE');require(one(c,'SELECT id FROM users WHERE id=?',(userid,)),'Utilisateur inconnu',404)
        c.execute('UPDATE users SET can_lift_holds=? WHERE id=?',(int(x.can_lift_holds),userid))
        audit(c,u['username'],'user_permissions','user',userid,x.model_dump());c.commit()
    return {'ok':True}

@app.post('/api/users/{userid}/reset-pin')
def reset_user_pin(userid:str,x:PinReset,u=Depends(auth)):
    role(u,'superadmin');pin_policy(x.pin)
    with tx() as c:
        t=one(c,'SELECT * FROM users WHERE id=?',(userid,));require(t,'Utilisateur inconnu',404);require(not t['deleted_at'],'Compte supprimé',409)
        require(t.get('auth_mode')=='pin' or t['role'] in PIN_ROLES,'Ce rôle doit se connecter par mot de passe')
        c.execute("UPDATE users SET passhash=?,auth_mode='pin' WHERE id=?",(password_hash(x.pin),userid));c.execute('DELETE FROM sessions WHERE user_id=?',(userid,))
        c.execute('DELETE FROM login_security WHERE username=?',(t['username'],))
        audit(c,u['username'],'reset_pin','user',userid,{'username':t['username']})
    return {'ok':True}
@app.post('/api/pin')
def change_own_pin(x:PinChange,u=Depends(auth)):
    require(u.get('auth_mode')=='pin' or u['role'] in PIN_ROLES,'Votre rôle doit se connecter par mot de passe')
    with tx() as c:
        row=one(c,'SELECT passhash FROM users WHERE id=?',(u['id'],));require(verify(x.old,row['passhash']),'Code PIN ou mot de passe actuel incorrect',403)
        pin_policy(x.new);require(x.new!=x.old,'Nouveau code identique')
        c.execute("UPDATE users SET passhash=?,auth_mode='pin' WHERE id=?",(password_hash(x.new),u['id']));c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
        audit(c,u['username'],'change_pin','user',u['id'])
    return {'ok':True,'message':'Reconnectez-vous avec votre nouveau code'}
@app.post('/api/users/{userid}/reset-password')
def reset_user_password(userid:str,x:UserReset,u=Depends(auth)):
    role(u,'superadmin')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');t=one(c,'SELECT id,auth_mode FROM users WHERE id=?',(userid,));require(t,'Utilisateur inconnu',404)
        require(t.get('auth_mode')!='pin','Compte à code PIN : utiliser la réinitialisation du code PIN')
        password_policy(x.password)
        c.execute('UPDATE users SET passhash=? WHERE id=?',(password_hash(x.password),userid));c.execute('DELETE FROM sessions WHERE user_id=?',(userid,));audit(c,u['username'],'reset_password','user',userid);c.commit()
    return {'ok':True}

app.mount('/',StaticFiles(directory=str(ROOT/'web'),html=True),name='web')
