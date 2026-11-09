"""Copie intégrale d'une base TAF WAREHOUSE SQLite vers PostgreSQL.

Usage : TAF_DATABASE_URL=postgresql://... python -m app.migrate_pg data/warehouse.sqlite3

- crée le schéma PostgreSQL (mêmes migrations additives que l'application) ;
- refuse une base cible non vide ;
- copie toutes les tables dans une seule transaction (tout ou rien) ;
- contrôle ensuite le nombre de lignes et une empreinte SHA-256 par table.
Les sessions ne sont pas copiées : tous les utilisateurs devront se reconnecter.
"""
import hashlib, json, os, sqlite3, sys

TABLES = ['users', 'login_security', 'mfa', 'mfa_recovery', 'idempotency', 'clients', 'locations', 'rack_rules',
          'receipts', 'units', 'unit_holds', 'label_prints', 'movements', 'transfers', 'transfer_refusals', 'counts', 'recounts', 'inventory_campaigns', 'campaign_items',
          'receipt_discrepancies', 'drivers', 'release_orders', 'releases', 'release_handovers', 'release_refusals', 'missions', 'mission_events', 'tasks', 'task_events', 'incidents', 'claims',
          'claim_actions', 'documents', 'notifications', 'notification_reads', 'mail_routes', 'mail_outbox', 'counters', 'location_internal', 'arrivals', 'tv_screens', 'audit']
SKIPPED = {'sessions'}


def fingerprint(rows, cols):
    h = hashlib.sha256()
    for r in sorted(json.dumps([r[c] for c in cols], default=str, ensure_ascii=False) for r in rows):
        h.update(r.encode())
    return h.hexdigest()


def migrate(sqlite_path):
    if not os.getenv('TAF_DATABASE_URL', '').startswith(('postgres://', 'postgresql://')):
        raise SystemExit('TAF_DATABASE_URL doit désigner la base PostgreSQL cible.')
    src = sqlite3.connect(f'file:{sqlite_path}?mode=ro', uri=True)
    src.row_factory = sqlite3.Row
    present = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    unknown = present - set(TABLES) - SKIPPED
    if unknown:
        raise SystemExit(f'Tables non prévues par la migration : {sorted(unknown)}')
    import importlib
    from app import server
    previous = os.environ.get('TAF_SKIP_BOOTSTRAP')
    os.environ['TAF_SKIP_BOOTSTRAP'] = '1'
    try:
        server = importlib.reload(server)  # crée/complète le schéma PostgreSQL sans compte initial
    finally:
        if previous is None:
            os.environ.pop('TAF_SKIP_BOOTSTRAP', None)
        else:
            os.environ['TAF_SKIP_BOOTSTRAP'] = previous
    report = {}
    with server.db() as c:
        c.execute('BEGIN IMMEDIATE')
        for t in TABLES:
            n = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
            if n:
                raise SystemExit(f'Base cible non vide (table {t} : {n} lignes). Migration annulée.')
        for t in TABLES:
            if t not in present:
                report[t] = 0
                continue
            target_cols = [r['name'] for r in c.execute(f'PRAGMA table_info({t})')]
            source_cols = [r[1] for r in src.execute(f'PRAGMA table_info({t})')]
            missing = set(source_cols) - set(target_cols)
            if missing:
                raise SystemExit(f'Colonnes absentes de la cible pour {t} : {sorted(missing)}')
            rows = src.execute(f'SELECT * FROM {t}').fetchall()
            marks = ','.join('?' for _ in source_cols)
            for r in rows:
                c.execute(f'INSERT INTO {t}({",".join(source_cols)}) VALUES({marks})', tuple(r[k] for k in source_cols))
            report[t] = len(rows)
        c.commit()
    # Contrôle après validation : mêmes lignes, même contenu.
    with server.db() as c:
        for t in TABLES:
            if t not in present:
                continue
            cols = [r[1] for r in src.execute(f'PRAGMA table_info({t})')]
            a = [dict(r) for r in src.execute(f'SELECT * FROM {t}')]
            b = [dict(r) for r in c.execute(f'SELECT {",".join(cols)} FROM {t}')]
            if len(a) != len(b) or fingerprint(a, cols) != fingerprint(b, cols):
                raise SystemExit(f'Contrôle en échec sur la table {t} : vérifier avant toute utilisation.')
    src.close()
    return report


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    result = migrate(sys.argv[1])
    for table, n in result.items():
        print(f'{table:24} {n:>7} ligne(s)')
    print('Migration terminée et contrôlée (nombre de lignes et empreintes identiques). Les sessions ne sont pas copiées.')
