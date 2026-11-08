"""Mise en page des documents PDF TAF WAREHOUSE (charte commune)."""
import io
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Frame, Image, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

NAVY = colors.HexColor('#0F2B47')
BLUE = colors.HexColor('#1F6FA8')
INK = colors.HexColor('#1B2733')
MUTED = colors.HexColor('#5B6B7A')
LINE = colors.HexColor('#D6DEE6')
SOFT = colors.HexColor('#F3F6F9')
RED = colors.HexColor('#B42318')
RED_SOFT = colors.HexColor('#FDECEA')
GREEN = colors.HexColor('#1E7A46')

W, H = A4
MARGIN = 16 * mm
CONTENT = W - 2 * MARGIN

S = {
    'label': ParagraphStyle('label', fontName='Helvetica', fontSize=7.5, leading=9, textColor=MUTED),
    'value': ParagraphStyle('value', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=INK),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=INK),
    'section': ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=4),
    'caption': ParagraphStyle('caption', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=MUTED),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=10.5, textColor=MUTED),
    'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8, leading=10, textColor=INK),
    'cellhead': ParagraphStyle('cellhead', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=MUTED),
}


def fr_number(value, digits=1):
    try:
        n = float(value)
    except (TypeError, ValueError):
        return '—'
    out = f'{n:,.{digits}f}'.replace(',', ' ').replace('.', ',')
    return out[:-2] if out.endswith(',0') else out


def fr_date(value):
    """ISO UTC -> « 07/11/2026 à 18:52 UTC »."""
    if not value:
        return '—'
    try:
        d = datetime.fromisoformat(str(value))
        return d.strftime('%d/%m/%Y à %H:%M') + ' UTC'
    except ValueError:
        return str(value)


def txt(value, style='body'):
    shown = '—' if value in (None, '') else str(value)
    return Paragraph(escape(shown).replace('\n', '<br/>'), S[style])


def field(label, value):
    return [Paragraph(escape(label.upper()), S['label']), txt(value, 'value')]


def section(title):
    return Table([[Paragraph(escape(title), S['section'])]], colWidths=[CONTENT],
                 style=[('LINEBELOW', (0, 0), (-1, -1), 0.8, NAVY), ('LEFTPADDING', (0, 0), (-1, -1), 0),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('TOPPADDING', (0, 0), (-1, -1), 8)])


def field_grid(pairs, columns=3):
    """Grille de champs « libellé / valeur » sur fond clair."""
    width = CONTENT / columns
    rows, row = [], []
    for label, value in pairs:
        row.append(field(label, value))
        if len(row) == columns:
            rows.append(row); row = []
    if row:
        rows.append(row + [''] * (columns - len(row)))
    t = Table(rows, colWidths=[width] * columns)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), SOFT), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                           ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                           ('LINEBELOW', (0, 0), (-1, -2), 0.4, colors.white)]))
    return t


def callout(title, text, tone='red'):
    fg, bg = (RED, RED_SOFT) if tone == 'red' else (NAVY, SOFT)
    t = Table([[Paragraph(escape(title.upper()), ParagraphStyle('ct', parent=S['label'], textColor=fg, fontName='Helvetica-Bold'))],
               [txt(text)]], colWidths=[CONTENT])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), bg), ('LINEBEFORE', (0, 0), (0, -1), 3, fg),
                           ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                           ('TOPPADDING', (0, 0), (-1, 0), 7), ('BOTTOMPADDING', (0, -1), (-1, -1), 8)]))
    return t


def photo_grid(photos, max_photos=6):
    cell_w = (CONTENT - 8 * mm) / 2
    cell_h = 50 * mm
    cells = []
    for d in photos[:max_photos]:
        try:
            source = (lambda: io.BytesIO(d['content'])) if d.get('content') else (lambda: d['path'])
            iw, ih = ImageReader(source()).getSize()
            scale = min(cell_w / iw, cell_h / ih)
            img = Image(source(), width=iw * scale, height=ih * scale)
        except Exception:
            img = txt('Photo illisible', 'small')
        cells.append([img, Paragraph(escape(d['name']) + ' · ' + escape(fr_date(d['uploaded'])) + ' · ' + escape(d['actor']), S['caption'])])
    rows = []
    for i in range(0, len(cells), 2):
        pair = cells[i:i + 2] + ([['', '']] if len(cells[i:i + 2]) == 1 else [])
        rows.append([pair[0][0], pair[1][0]])
        rows.append([pair[0][1], pair[1][1]])
    if not rows:
        return txt('Aucune photo.', 'small')
    t = Table(rows, colWidths=[cell_w + 4 * mm] * 2)
    style = [('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 2), ('RIGHTPADDING', (0, 0), (-1, -1), 2)]
    for r in range(0, len(rows), 2):
        style += [('BOTTOMPADDING', (0, r + 1), (-1, r + 1), 9), ('TOPPADDING', (0, r), (-1, r), 4),
                  ('BACKGROUND', (0, r), (-1, r), SOFT), ('ROWBACKGROUNDS', (0, r), (-1, r), [SOFT]),
                  ('LINEBELOW', (0, r), (-1, r), 0.4, LINE)]
        style += [('BACKGROUND', (1, r), (1, r + 1), colors.white)] if len(cells) % 2 and r == len(rows) - 2 else []
    t.setStyle(TableStyle(style))
    return t


def attachments_table(docs):
    head = [Paragraph(h, S['cellhead']) for h in ('PIÈCE', 'AJOUTÉE PAR', 'DATE', 'EMPREINTE SHA-256')]
    rows = [head] + [[txt(d['name'], 'cell'), txt(d['actor'], 'cell'), txt(fr_date(d['uploaded']), 'cell'),
                      Paragraph(escape(d['sha256'][:16] + '…'), ParagraphStyle('mono', parent=S['cell'], fontName='Courier'))] for d in docs]
    if len(rows) == 1:
        return txt('Aucune pièce jointe.', 'small')
    t = Table(rows, colWidths=[CONTENT * .38, CONTENT * .17, CONTENT * .22, CONTENT * .23], repeatRows=1)
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4),
                           ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('LEFTPADDING', (0, 0), (-1, -1), 3)]))
    return t


def signatures_block(left, right):
    """Deux cartouches « rôle / nom / date »."""
    def box(role, name, date):
        return [Paragraph(escape(role.upper()), S['label']), txt(name, 'value'), txt(date, 'small')]
    t = Table([[box(*left), box(*right)]], colWidths=[CONTENT / 2, CONTENT / 2])
    t.setStyle(TableStyle([('BOX', (0, 0), (0, 0), 0.6, LINE), ('BOX', (1, 0), (1, 0), 0.6, LINE),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 9),
                           ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]))
    return t


class _NumberedCanvas(rl_canvas.Canvas):
    """Ajoute « Page x / y » après composition complète."""
    def __init__(self, *args, footer_text='', **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []
        self._footer_text = footer_text

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.setFont('Helvetica', 7.5)
            self.setFillColor(MUTED)
            self.drawRightString(W - MARGIN, 10 * mm, f'Page {self._pageNumber} / {total}')
            super().showPage()
        super().save()


def build(title, reference, status_label, status_tone, story, generated_at, footer_note):
    """Compose un document A4 avec bandeau TAF, badge de statut et pied de page."""
    out = io.BytesIO()
    status_color = {'red': RED, 'green': GREEN, 'blue': BLUE}.get(status_tone, NAVY)

    def decorate(c, doc):
        c.saveState()
        band = 30 * mm
        c.setFillColor(NAVY); c.rect(0, H - band, W, band, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 17); c.drawString(MARGIN, H - 13.5 * mm, 'TAF')
        c.setFont('Helvetica', 7.5); c.drawString(MARGIN + 13.5 * mm, H - 13.5 * mm, 'TRANS AIR FREIGHT · WAREHOUSE')
        c.setFont('Helvetica-Bold', 12.5); c.drawString(MARGIN, H - 22.5 * mm, title)
        c.setFont('Helvetica', 8); c.drawRightString(W - MARGIN, H - 13.5 * mm, reference)
        c.drawRightString(W - MARGIN, H - 18.5 * mm, 'Émis le ' + fr_date(generated_at))
        # Badge de statut
        c.setFont('Helvetica-Bold', 8)
        bw = c.stringWidth(status_label, 'Helvetica-Bold', 8) + 7 * mm
        c.setFillColor(status_color); c.roundRect(W - MARGIN - bw, H - 26 * mm, bw, 6 * mm, 1.5 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.drawCentredString(W - MARGIN - bw / 2, H - 24 * mm, status_label)
        # Pied de page
        c.setStrokeColor(LINE); c.setLineWidth(0.5); c.line(MARGIN, 14 * mm, W - MARGIN, 14 * mm)
        c.setFont('Helvetica', 7.5); c.setFillColor(MUTED)
        c.drawString(MARGIN, 10 * mm, f'TAF WAREHOUSE · {reference} · {footer_note}')
        c.restoreState()

    doc = BaseDocTemplate(out, pagesize=A4, title=f'{title} {reference}', author='TAF WAREHOUSE',
                          leftMargin=MARGIN, rightMargin=MARGIN, topMargin=38 * mm, bottomMargin=20 * mm)
    frame = Frame(MARGIN, 20 * mm, CONTENT, H - 58 * mm, id='main', leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id='page', frames=[frame], onPage=decorate)])
    doc.build(story, canvasmaker=_NumberedCanvas)
    return out.getvalue()


def refusal_report(refusal, transfer, unit, driver, docs, generated_at):
    photos = [d for d in docs if Path(d['path']).suffix in ('.png', '.jpg')]
    others = [d for d in docs if d not in photos and not d['name'].startswith('rapport-refus-')]
    validated = refusal.get('status') == 'validated' or refusal.get('reviewed_by')
    carrier = ' · '.join(x for x in ((driver or {}).get('company'), (driver or {}).get('name')) if x)
    story = [
        section('Transfert concerné'),
        Spacer(1, 4),
        field_grid([
            ('Trajet', f"{transfer['source']}  →  {transfer['destination']}"),
            ('Transfert', transfer['id']),
            ('Unité', unit['id'] if unit else transfer['unit_id']),
            ('Type / quantité', f"{str((unit or {}).get('unit_type', '—')).capitalize()} · {(unit or {}).get('quantity', '—')} colis"),
            ('Poids', f"{fr_number((unit or {}).get('weight'))} kg"),
            ('Expédié par', transfer['dispatched_by']),
            ('Date d’expédition', fr_date(transfer['dispatched_at'])),
            ('Transporteur', carrier),
            ('Immatriculation', (driver or {}).get('plate')),
        ]),
        Spacer(1, 10),
        section('Constat à l’arrivée'),
        Spacer(1, 4),
        callout('Motif du refus', refusal['reason'], 'red'),
        Spacer(1, 6),
        callout('Avis du responsable magasin', refusal.get('review_note') or '—', 'navy'),
        Spacer(1, 10),
        KeepTogether([section('Validation'), Spacer(1, 5),
                      signatures_block(('Constaté par (magasin)', refusal['created_by'], fr_date(refusal['created'])),
                                       ('Validé par (responsable magasin)', refusal.get('reviewed_by'), fr_date(refusal.get('reviewed_at'))))]),
        Spacer(1, 10),
        section(f'Photos ({len(photos)})'),
        Spacer(1, 5),
        photo_grid(photos),
    ]
    if len(photos) > 6:
        story.append(txt(f'{len(photos) - 6} photo(s) supplémentaire(s) dans le dossier du transfert.', 'small'))
    story += [Spacer(1, 8), KeepTogether([section('Pièces jointes'), Spacer(1, 4), attachments_table(photos + others)])]
    story += [Spacer(1, 10), txt('Transmis à l’exploitation par notification interne TAF WAREHOUSE. Aucun envoi externe automatique. '
                                 'Signature électronique simple : identités déclarées par les comptes utilisateurs, non qualifiée.', 'small')]
    return build('Rapport de refus de transfert', refusal['id'], 'REFUS VALIDÉ' if validated else 'REFUS À VALIDER',
                 'red' if validated else 'blue', story, generated_at, 'Document généré automatiquement')


def signature_image(data_url, max_w=70 * mm, max_h=28 * mm):
    import base64
    raw = base64.b64decode(data_url.split(',', 1)[1])
    iw, ih = ImageReader(io.BytesIO(raw)).getSize()
    scale = min(max_w / iw, max_h / ih)
    return Image(io.BytesIO(raw), width=iw * scale, height=ih * scale)


def handover_report(order, handover, lines, remaining, driver, generated_at):
    """Bon de remise signé d'un ordre de sortie (une remise = un bon)."""
    driver = driver or {}
    first = lines[0] if lines else {}
    story = [
        section('Sortie'), Spacer(1, 4),
        field_grid([
            ('Ordre de sortie', order['id']), ('Référence', order['reference']), ('Entrepôt', order['warehouse']),
            ('Client', first.get('client')), ('LTA', first.get('awb')), ('Remise n°', handover['id']),
            ('Autorisé par', order.get('authorized_by')), ('Remis par', handover['actor']), ('Date de remise', fr_date(handover['signed_at'])),
        ]),
        Spacer(1, 10), section('Transporteur'), Spacer(1, 4),
        field_grid([('Société', driver.get('company')), ('Chauffeur', driver.get('name')), ('Immatriculation', driver.get('plate'))]),
        Spacer(1, 10), section(f'Unités remises ({len(lines)})'), Spacer(1, 4),
    ]
    head = [Paragraph(h, S['cellhead']) for h in ('UNITÉ', 'TYPE', 'DESCRIPTION', 'COLIS', 'POIDS')]
    rows = [head] + [[txt(l['unit_id'], 'cell'),
                      txt(f"{(l.get('unit_type') or '').capitalize()} {l['unit_index']}/{l['unit_count']}" if l.get('unit_index') else (l.get('unit_type') or '').capitalize(), 'cell'),
                      txt(l.get('description'), 'cell'), txt(l['quantity'], 'cell'), txt(f"{fr_number(l.get('weight_out'))} kg", 'cell')] for l in lines]
    rows.append([txt('Total', 'cellhead'), '', '', txt(sum(l['quantity'] for l in lines), 'cellhead'), txt(f"{fr_number(sum(l.get('weight_out') or 0 for l in lines))} kg", 'cellhead')])
    t = Table(rows, colWidths=[CONTENT * .22, CONTENT * .14, CONTENT * .38, CONTENT * .1, CONTENT * .16], repeatRows=1)
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -2), 0.3, LINE), ('LINEABOVE', (0, -1), (-1, -1), 0.8, NAVY),
                           ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story.append(t)
    if remaining:
        story += [Spacer(1, 8), callout('Reliquat restant en entrepôt', ', '.join(f"{r['unit_id']} ({r['quantity']} colis)" for r in remaining), 'navy')]
    sig = Table([[[Paragraph('SIGNATURE DU TRANSPORTEUR', S['label']), txt(handover['signature_name'], 'value'), txt(fr_date(handover['signed_at']), 'small')],
                  signature_image(handover['signature_data'])]], colWidths=[CONTENT * .45, CONTENT * .55])
    sig.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 9),
                             ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    story += [Spacer(1, 12), KeepTogether([section('Remise et signature'), Spacer(1, 5), sig]),
              Spacer(1, 10), txt('Le transporteur reconnaît avoir pris en charge les unités ci-dessus. Signature électronique simple : identité déclarée '
                                 'par le signataire, non qualifiée. Toute réserve doit être portée sur le document de transport.', 'small')]
    return build('Bon de remise', handover['id'], 'REMIS ET SIGNÉ', 'green', story, generated_at, f"Ordre {order['id']}")


def campaign_report(k, generated_at):
    """Rapport de campagne d'inventaire."""
    scope = {'warehouse': 'Entrepôt complet', 'rack': f"Rack {k.get('scope_value')}", 'location': f"Emplacement {k.get('scope_value')}"}.get(k['scope'], k['scope'])
    p = k['progress']
    story = [section('Campagne'), Spacer(1, 4),
             field_grid([('Campagne', k['id']), ('Titre', k['title']), ('Entrepôt', k['warehouse']),
                         ('Périmètre', scope), ('Compteur', k['assignee']), ('Créée par', k['created_by']),
                         ('Créée le', fr_date(k['created'])), ('Clôturée par', k.get('closed_by')), ('Clôturée le', fr_date(k.get('closed_at')))]),
             Spacer(1, 8),
             field_grid([('Unités', p['total']), ('Comptées', p['counted']), ('Écarts', p['discrepancies'])]),
             Spacer(1, 10), section('Résultats'), Spacer(1, 4)]
    head = [Paragraph(h, S['cellhead']) for h in ('EMPLACEMENT', 'UNITÉ', 'ATTENDU', 'COMPTÉ', 'RECOMPTE', 'RÉSULTAT', 'DÉCISION')]
    rows = [head] + [[txt(i['location_id'], 'cell'), txt(i['unit_id'], 'cell'), txt(i['expected'], 'cell'), txt(i['observed'], 'cell'),
                      txt(i.get('recount'), 'cell'), txt({'conforme': 'Conforme', 'ecart': 'Écart'}.get(i['result'], 'Non compté'), 'cell'), txt(i.get('decision'), 'cell')] for i in k['items']]
    t = Table(rows, colWidths=[CONTENT * w for w in (.15, .21, .1, .1, .11, .13, .2)], repeatRows=1)
    style = [('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]
    for r, i in enumerate(k['items'], 1):
        if i['result'] == 'ecart':
            style.append(('BACKGROUND', (0, r), (-1, r), RED_SOFT))
    t.setStyle(TableStyle(style))
    story.append(t)
    if k.get('close_note'):
        story += [Spacer(1, 10), callout('Observation de clôture', k['close_note'], 'navy')]
    story += [Spacer(1, 10), txt('Les écarts ne modifient le stock qu’après recomptage indépendant et validation par une troisième personne habilitée. '
                                 'Valeurs avant et après correction conservées dans le journal d’audit.', 'small')]
    status = {'open': ('EN COURS', 'blue'), 'closed': ('CLÔTURÉE', 'green'), 'cancelled': ('ANNULÉE', 'red')}.get(k['status'], (k['status'].upper(), 'blue'))
    return build('Rapport d\'inventaire', k['id'], status[0], status[1], story, generated_at, k['title'])


def transfer_report(t, unit, driver, generated_at):
    """Bon de transfert signé entre entrepôts."""
    driver = driver or {}
    status = {'in_transit': ('EN TRANSIT', 'blue'), 'received': ('RÉCEPTIONNÉ', 'green'), 'discrepancy': ('ÉCART À TRANCHER', 'red'),
              'refusal_pending': ('REFUS À VALIDER', 'red'), 'refused': ('REFUSÉ', 'red'), 'returned': ('RETOURNÉ', 'blue'),
              'received_with_reserves': ('ACCEPTÉ SOUS RÉSERVES', 'blue')}.get(t['status'], (t['status'].upper(), 'blue'))
    story = [section('Transfert'), Spacer(1, 4),
             field_grid([('Trajet', f"{t['source']}  →  {t['destination']}"), ('Transfert', t['id']), ('Retour de', t.get('return_of')),
                         ('Demandé par', t['actor']), ('Validé par', t.get('approved_by')), ('Expédié par', t.get('dispatched_by')),
                         ('Expédié le', fr_date(t.get('dispatched_at'))), ('Référence transport', t.get('dispatch_note')), ('', '')]),
             Spacer(1, 10), section('Marchandise'), Spacer(1, 4),
             field_grid([('Unité', unit.get('id') or t['unit_id']),
                         ('Type', f"{str(unit.get('unit_type') or '').capitalize()} {unit.get('unit_index')}/{unit.get('unit_count')}" if unit.get('unit_index') else str(unit.get('unit_type') or '').capitalize()),
                         ('Colis', unit.get('quantity')), ('Poids', f"{fr_number(unit.get('weight'))} kg"), ('Client', unit.get('client')), ('LTA', unit.get('awb'))]),
             Spacer(1, 10), section('Transporteur'), Spacer(1, 4),
             field_grid([('Société', driver.get('company')), ('Chauffeur', driver.get('name')), ('Immatriculation', driver.get('plate'))])]
    if t.get('received_at'):
        story += [Spacer(1, 10), section('Réception à destination'), Spacer(1, 4),
                  field_grid([('Réceptionné par', t.get('received_by')), ('Le', fr_date(t.get('received_at'))), ('Colis reçus', t.get('received_quantity')),
                              ('État constaté', t.get('received_condition')), ('Observations', t.get('received_note')), ('Décision', t.get('discrepancy_decision'))])]
    sig = Table([[[Paragraph('SIGNATURE DU TRANSPORTEUR AU DÉPART', S['label']), txt(t.get('signature_name'), 'value'), txt(fr_date(t.get('signature_at')), 'small')],
                  signature_image(t['signature_data'])]], colWidths=[CONTENT * .45, CONTENT * .55])
    sig.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 0.6, LINE), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 9),
                             ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    story += [Spacer(1, 12), KeepTogether([section('Remise au transporteur'), Spacer(1, 5), sig]), Spacer(1, 10),
              txt('Signature électronique simple : identité déclarée par le signataire, non qualifiée.', 'small')]
    return build('Bon de transfert', t['id'], status[0], status[1], story, generated_at, f"{t['source']} → {t['destination']}")


ACTION_LABELS = {'declare': 'Déclaration', 'update': 'Mise à jour', 'open': 'Ouverture', 'create': 'Création', 'plan': 'Planification', 'close': 'Clôture',
                 'investigate': 'Enquête', 'request_evidence': 'Demande de pièces', 'evidence_reviewed': 'Pièces contrôlées', 'decision': 'Décision',
                 'start': 'Démarrage', 'suspend': 'Suspension', 'resume': 'Reprise', 'complete': 'Fin', 'cancel': 'Annulation', 'assign': 'Affectation'}


FR = {'minor': 'Mineure', 'major': 'Majeure', 'critical': 'Critique', 'damage': 'Avarie', 'missing': 'Manquant', 'security': 'Sûreté', 'handling': 'Manutention',
      'location': 'Emplacement', 'carrier': 'Transporteur', 'weight': 'Écart de poids', 'other': 'Autre', 'low': 'Basse', 'normal': 'Normale', 'high': 'Haute', 'urgent': 'Urgente',
      'reception': 'Réception', 'rangement': 'Rangement', 'preparation': 'Préparation', 'inventaire': 'Inventaire', 'transfert': 'Transfert', 'controle': 'Contrôle', 'incident': 'Traitement d’incident', 'autre': 'Autre'}
def fr(v):
    return FR.get(v, v) if isinstance(v, str) else v


def dossier_report(kind, item, logs, docs, extra, generated_at):
    """Rapport d'incident, de litige ou de mission."""
    title = {'incident': "Rapport d'incident", 'claim': 'Dossier de litige', 'mission': 'Rapport de mission'}[kind]
    if kind == 'incident':
        fields = [('Incident', item['id']), ('Entrepôt', item['warehouse']), ('Gravité', fr(item.get('severity'))), ('Catégorie', fr(item.get('category'))),
                  ('Unité', item.get('unit_id')), ('Emplacement', item.get('location_id')), ('Déclaré par', item.get('actor')), ('Le', fr_date(item.get('created'))), ('Responsable', item.get('owner'))]
        body, conclusion = item.get('description'), item.get('resolution')
    elif kind == 'claim':
        fields = [('Litige', item['id']), ('Entrepôt', item['warehouse']), ('Client', item.get('client_id')), ('Incident lié', item.get('incident_id')),
                  ('Ouvert par', item.get('actor')), ('Le', fr_date(item.get('created'))), ('Responsable', item.get('owner')), ('Échéance', item.get('deadline')), ('Clôturé par', item.get('closed_by'))]
        body, conclusion = item.get('description'), item.get('decision')
    else:
        fields = [('Mission', item['id']), ('Entrepôt', item['warehouse']), ('Type', fr(item.get('type'))), ('Collaborateur', item.get('assignee')),
                  ('Priorité', fr(item.get('priority'))), ('Échéance', item.get('due_at')), ('Créée par', item.get('created_by')), ('Terminée par', item.get('completed_by')), ('Le', fr_date(item.get('completed_at')))]
        body, conclusion = item.get('title') + (' — ' + item['description'] if item.get('description') else ''), None
    story = [section('Dossier'), Spacer(1, 4), field_grid(fields), Spacer(1, 10), callout('Description', body, 'navy')]
    if conclusion:
        story += [Spacer(1, 6), callout('Résolution / décision', conclusion, 'navy')]
    rows = [(e['created'], e['actor'], ACTION_LABELS.get(e['action'], e['action']), e.get('note')) for e in extra] or \
           [(l['at'], l['actor'], ACTION_LABELS.get(l['action'], l['action']), '') for l in logs]
    head = [Paragraph(h, S['cellhead']) for h in ('DATE', 'PAR', 'ACTION', 'DÉTAIL')]
    t = Table([head] + [[txt(fr_date(a), 'cell'), txt(b, 'cell'), txt(c_, 'cell'), txt(d, 'cell')] for a, b, c_, d in rows],
              colWidths=[CONTENT * .24, CONTENT * .16, CONTENT * .2, CONTENT * .4], repeatRows=1)
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story += [Spacer(1, 10), section('Historique'), Spacer(1, 4), t, Spacer(1, 10), KeepTogether([section('Pièces jointes'), Spacer(1, 4), attachments_table(docs)])]
    st = str(item.get('status') or '').lower()
    badge = ('CLÔTURÉ', 'green') if st in ('closed', 'done', 'resolved') else ('ANNULÉ', 'red') if st == 'cancelled' else ('EN COURS', 'blue')
    return build(title, item['id'], badge[0], badge[1], story, generated_at, item['warehouse'])
