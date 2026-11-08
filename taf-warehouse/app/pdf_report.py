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


# --- Notice d'information transporteur (sûreté du fret aérien et données personnelles) -------------

NOTICE_TEXT = {
    'fr': {
        'kicker': 'NOTICE D’INFORMATION AUX TRANSPORTEURS',
        'title': 'Pourquoi nous vous demandons votre pièce d’identité',
        'lead': ('Nos entrepôts traitent du fret destiné au transport aérien. La réglementation de sûreté nous impose de vérifier '
                 'l’identité de chaque personne qui dépose ou enlève de la marchandise, et de pouvoir le prouver. '
                 'Cette notice vous explique ce que nous enregistrons, comment vos données sont protégées et quand elles sont effacées.'),
        'cards': [
            ('1', 'Une obligation de sûreté',
             'Le fret aérien est soumis à la réglementation européenne de sûreté de l’aviation civile '
             '(règlement d’exécution (UE) 2015/1998) et au programme de sûreté de TAF. Nous devons pouvoir établir, '
             'à tout moment et lors des contrôles des autorités, qui a remis ou pris en charge chaque marchandise.'),
            ('2', 'Ce que nous enregistrons',
             'Votre nom, votre société, l’immatriculation du véhicule, le type et le numéro de votre pièce d’identité, '
             'une photo de cette pièce, ainsi que les dates de vos passages et les bons de remise que vous signez. Rien d’autre.'),
            ('3', 'Un hébergement sécurisé en France',
             'Les données sont hébergées dans le centre de données Amazon Web Services de Paris. Fichiers et base de données '
             'sont chiffrés, les échanges passent par une connexion chiffrée (HTTPS). Seuls l’exploitation et les responsables '
             'habilités y ont accès, avec un compte personnel, et chaque consultation est enregistrée.'),
            ('4', 'Effacement automatique',
             'La photo et le numéro de votre pièce d’identité sont effacés automatiquement un an après votre dernier passage '
             'dans nos entrepôts. Votre nom reste uniquement sur les bons de remise signés, conservés pour la traçabilité des marchandises.'),
        ],
        'banner': 'EFFACEMENT AUTOMATIQUE 1 AN APRÈS VOTRE DERNIER PASSAGE',
        'never': 'Vos données ne sont ni vendues, ni cédées, ni utilisées à des fins commerciales.',
        'rights_title': 'Vos droits',
        'rights': ('Vous pouvez demander à accéder à vos données, les faire corriger, en demander l’effacement ou la limitation, '
                   'en écrivant à {contact}. Vous pouvez aussi adresser une réclamation à la CNIL (www.cnil.fr). '
                   'Le contrôle d’identité étant une obligation de sûreté, sans pièce d’identité la marchandise ne peut être ni remise ni enlevée.'),
        'controller': 'Responsable du traitement : TAF — Trans Air Freight · Finalité : sûreté du fret aérien et traçabilité des remises · '
                      'Base légale : obligation légale (article 6.1.c du RGPD).',
        'yours': 'Vos informations enregistrées',
        'f_name': 'Nom', 'f_company': 'Société', 'f_plate': 'Immatriculation', 'f_id': 'Pièce d’identité',
        'f_last': 'Dernier passage', 'f_erase': 'Effacement prévu au plus tard le',
        'ack_title': 'Accusé de lecture',
        'ack': 'Je reconnais avoir reçu et lu cette notice d’information.',
        'sig_name': 'Nom et prénom', 'sig_date': 'Date', 'sig_sign': 'Signature',
    },
    'en': {
        'kicker': 'INFORMATION NOTICE FOR CARRIERS AND DRIVERS',
        'title': 'Why we ask for your identity document',
        'lead': ('Our warehouses handle air cargo. Aviation security rules require us to check the identity of every person who '
                 'delivers or collects goods, and to be able to prove it. This notice explains what we record, how your data '
                 'is protected and when it is deleted.'),
        'cards': [
            ('1', 'A security requirement',
             'Air cargo is subject to the European civil aviation security rules (Commission Implementing Regulation (EU) 2015/1998) '
             'and to TAF’s security programme. We must be able to show, at any time and during inspections by the authorities, '
             'who delivered or collected each consignment.'),
            ('2', 'What we record',
             'Your name, your company, the vehicle registration, the type and number of your identity document, a photo of this '
             'document, the dates of your visits and the delivery notes you sign. Nothing else.'),
            ('3', 'Secure hosting in France',
             'Data is hosted in the Amazon Web Services data centre in Paris. Files and database are encrypted and all exchanges '
             'use an encrypted connection (HTTPS). Only authorised operations staff and managers can access it, each with a '
             'personal account, and every access is logged.'),
            ('4', 'Automatic deletion',
             'The photo and number of your identity document are automatically deleted one year after your last visit to our '
             'warehouses. Your name only remains on the signed delivery notes, kept for cargo traceability.'),
        ],
        'banner': 'AUTOMATICALLY DELETED 1 YEAR AFTER YOUR LAST VISIT',
        'never': 'Your data is never sold, transferred to third parties or used for marketing.',
        'rights_title': 'Your rights',
        'rights': ('You may request access to your data, its correction, deletion or restriction by writing to {contact}. '
                   'You may also lodge a complaint with the French data protection authority, CNIL (www.cnil.fr). '
                   'As identity checks are a security requirement, goods cannot be released or collected without an identity document.'),
        'controller': 'Data controller: TAF — Trans Air Freight · Purpose: air cargo security and traceability of handovers · '
                      'Legal basis: legal obligation (Article 6(1)(c) GDPR).',
        'yours': 'Your recorded information',
        'f_name': 'Name', 'f_company': 'Company', 'f_plate': 'Vehicle registration', 'f_id': 'Identity document',
        'f_last': 'Last visit', 'f_erase': 'Deletion no later than',
        'ack_title': 'Acknowledgement',
        'ack': 'I acknowledge that I have received and read this information notice.',
        'sig_name': 'Full name', 'sig_date': 'Date', 'sig_sign': 'Signature',
    },
}


def _fr_day(value):
    try:
        return datetime.fromisoformat(str(value)).strftime('%d/%m/%Y')
    except (TypeError, ValueError):
        return '—'


def _notice_page(lang, driver, contact):
    from reportlab.platypus import PageBreak  # noqa: F401  (import local : utilisé par l'appelant)
    T = NOTICE_TEXT[lang]
    kicker = ParagraphStyle('nk', parent=S['label'], fontName='Helvetica-Bold', textColor=BLUE, fontSize=8, leading=10)
    title = ParagraphStyle('nt', fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=NAVY, spaceAfter=2)
    lead = ParagraphStyle('nl', parent=S['body'], fontSize=9.6, leading=13.6)
    card_t = ParagraphStyle('nct', fontName='Helvetica-Bold', fontSize=10.5, leading=13, textColor=NAVY)
    card_b = ParagraphStyle('ncb', parent=S['body'], fontSize=8.5, leading=11.6)
    num = ParagraphStyle('nn', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.white, alignment=1)
    story = [Paragraph(T['kicker'], kicker), Spacer(1, 3), Paragraph(escape(T['title']), title), Spacer(1, 4),
             Paragraph(escape(T['lead']), lead), Spacer(1, 7)]

    def card(n, head, body):
        badge = Table([[Paragraph(n, num)]], colWidths=[9 * mm], rowHeights=[9 * mm])
        badge.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), NAVY), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                   ('TOPPADDING', (0, 0), (-1, -1), 0), ('BOTTOMPADDING', (0, 0), (-1, -1), 1)]))
        inner = Table([[badge, Paragraph(escape(head), card_t)], ['', Paragraph(escape(body), card_b)]],
                      colWidths=[12 * mm, CONTENT / 2 - 12 * mm - 14])
        inner.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('SPAN', (0, 0), (0, 1)),
                                   ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 0),
                                   ('TOPPADDING', (1, 0), (1, 0), 1), ('BOTTOMPADDING', (1, 0), (1, 0), 3)]))
        return inner

    cards = [card(*x) for x in T['cards']]
    grid = Table([[cards[0], cards[1]], [cards[2], cards[3]]], colWidths=[CONTENT / 2] * 2)
    grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BACKGROUND', (0, 0), (-1, -1), SOFT),
                              ('LINEAFTER', (0, 0), (0, -1), 4, colors.white), ('LINEBELOW', (0, 0), (-1, 0), 4, colors.white),
                              ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
                              ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
    banner = Table([[Paragraph(escape(T['banner']), ParagraphStyle('nb', fontName='Helvetica-Bold', fontSize=10.5, leading=13,
                                                                 textColor=colors.white, alignment=1))]], colWidths=[CONTENT])
    banner.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), GREEN), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 8)]))
    story += [grid, Spacer(1, 6), banner, Spacer(1, 4),
              Paragraph(escape(T['never']), ParagraphStyle('nv', parent=S['small'], alignment=1, textColor=INK)), Spacer(1, 2)]
    story += [section(T['rights_title']), Spacer(1, 3), Paragraph(escape(T['rights'].format(contact=contact)), card_b), Spacer(1, 3),
              Paragraph(escape(T['controller']), S['small'])]
    if driver:
        story += [Spacer(1, 2), section(T['yours']), Spacer(1, 3),
                  field_grid([(T['f_name'], driver.get('name')), (T['f_company'], driver.get('company')), (T['f_plate'], driver.get('plate')),
                              (T['f_id'], driver.get('id_label')), (T['f_last'], _fr_day(driver.get('last_seen'))),
                              (T['f_erase'], _fr_day(driver.get('erase_on')))])]
    line = lambda label: [Paragraph(escape(label.upper()), S['label']), Spacer(1, 13),
                          Table([['']], colWidths=[CONTENT / 3 - 14], style=[('LINEBELOW', (0, 0), (-1, -1), 0.6, MUTED)])]
    ack = Table([[Paragraph(escape(T['ack']), S['body']), '', ''],
                 [line(T['sig_name']), line(T['sig_date']), line(T['sig_sign'])]], colWidths=[CONTENT / 3] * 3)
    ack.setStyle(TableStyle([('SPAN', (0, 0), (-1, 0)), ('BOX', (0, 0), (-1, -1), 0.6, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                             ('LEFTPADDING', (0, 0), (-1, -1), 8), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]))
    story += [Spacer(1, 2), KeepTogether([section(T['ack_title']), Spacer(1, 3), ack])]
    return story


def driver_notice(driver, contact, generated_at, ref='NOTICE-SURETE'):
    """Notice d'information remise au transporteur : page française puis page anglaise."""
    from reportlab.platypus import PageBreak
    story = _notice_page('fr', driver, contact) + [PageBreak()] + _notice_page('en', driver, contact)
    return build('Contrôle d’identité · Identity check', ref, 'SÛRETÉ FRET AÉRIEN', 'blue', story, generated_at,
                 'Information RGPD — à remettre au transporteur')


# --- Fiche de réception ---------------------------------------------------------------------------

def receipt_report(rec, units, discrepancies, holds, problems, docs, received_by, generated_at):
    """Fiche de réception : conforme (verte) ou problème de réception (rouge)."""
    photos = [d for d in docs if Path(d['path']).suffix in ('.png', '.jpg')]
    cond = {'conforme': 'Conforme', 'endommage': 'Endommagé', 'a_verifier': 'À vérifier'}
    sec = {'securise': 'Sécurisé', 'a_controler': 'À contrôler', 'non_securise': 'Non sécurisé'}
    weighed = sum(u.get('weight') or 0 for u in units)
    story = [section('Réception'), Spacer(1, 4),
             field_grid([('Réception', rec['id']), ('Entrepôt', rec['warehouse']), ('Date', fr_date(rec['created'])),
                         ('Client', rec.get('client')), ('LTA', rec.get('awb')), ('Référence dossier', rec.get('folder_ref')),
                         ('Expéditeur', rec.get('shipper')), ('Transporteur', rec.get('carrier')), ('Référence transport', rec.get('transport_ref')),
                         ('Nature', rec.get('nature')), ('État apparent', cond.get(rec.get('apparent_condition'), rec.get('apparent_condition'))),
                         ('Statut sûreté', sec.get(rec.get('security_status'), rec.get('security_status')))]),
             Spacer(1, 10), section('Quantités et poids'), Spacer(1, 4),
             field_grid([('Colis prévus', rec.get('expected')), ('Colis reçus', rec.get('actual')), ('Unités créées', len(units)),
                         ('Poids déclaré', f"{fr_number(rec.get('weight'))} kg"), ('Poids pesé', f"{fr_number(weighed)} kg" if units else '—'),
                         ('Volume', f"{fr_number(rec.get('volume_m3'), 3)} m³" if rec.get('volume_m3') else '—'),
                         ('Poids volumétrique (1:6000)', f"{fr_number(rec.get('volumetric_weight'))} kg" if rec.get('volumetric_weight') else '—'),
                         ('Réceptionné par', received_by), ('Observations', rec.get('notes'))])]
    if problems:
        story += [Spacer(1, 10), callout('Problèmes constatés', '\n'.join('• ' + p for p in problems), 'red')]
    else:
        story += [Spacer(1, 10), callout('Contrôle de réception', 'Quantités, poids, état apparent et sûreté conformes. Aucune réserve.', 'navy')]
    head = [Paragraph(h, S['cellhead']) for h in ('UNITÉ', 'TYPE', 'DIMENSIONS (CM)', 'COLIS', 'POIDS', 'EMPLACEMENT')]
    rows = [head] + [[txt(u['id'], 'cell'),
                      txt(f"{(u.get('unit_type') or '').capitalize()} {u['unit_index']}/{u['unit_count']}" if u.get('unit_index') else (u.get('unit_type') or '').capitalize(), 'cell'),
                      txt(f"{fr_number(u.get('length_cm'), 0)} × {fr_number(u.get('width_cm'), 0)} × {fr_number(u.get('height_cm'), 0)}" if u.get('length_cm') else '—', 'cell'),
                      txt(u['quantity'], 'cell'), txt(f"{fr_number(u.get('weight'))} kg", 'cell'),
                      txt(u.get('location_id') or 'À ranger', 'cell')] for u in units]
    if units:
        rows.append([txt('Total', 'cellhead'), '', '', txt(sum(u['quantity'] for u in units), 'cellhead'), txt(f'{fr_number(weighed)} kg', 'cellhead'), ''])
        t = Table(rows, colWidths=[CONTENT * .25, CONTENT * .15, CONTENT * .2, CONTENT * .1, CONTENT * .13, CONTENT * .17], repeatRows=1)
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -2), 0.3, LINE), ('LINEABOVE', (0, -1), (-1, -1), 0.8, NAVY),
                               ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    else:
        t = txt('Aucune unité enregistrée.', 'small')
    story += [Spacer(1, 10), section(f'Colisage ({len(units)} unité(s))'), Spacer(1, 4), t]
    if discrepancies:
        kinds = {'missing': 'Colis manquants', 'excess': 'Excédent', 'damage': 'Avarie', 'documentation': 'Documents', 'other': 'Autre'}
        st = {'open': 'Ouvert', 'accepted': 'Accepté', 'rejected': 'Refusé'}
        head = [Paragraph(h, S['cellhead']) for h in ('ÉCART', 'NATURE', 'DESCRIPTION', 'DÉCLARÉ PAR', 'STATUT')]
        drows = [head] + [[txt(d['id'], 'cell'), txt(kinds.get(d['kind'], d['kind']), 'cell'), txt(d['description'], 'cell'),
                           txt(f"{d['reported_by']} · {fr_date(d['created'])}", 'cell'), txt(st.get(d['status'], d['status']), 'cell')] for d in discrepancies]
        dt = Table(drows, colWidths=[CONTENT * .2, CONTENT * .14, CONTENT * .34, CONTENT * .2, CONTENT * .12], repeatRows=1)
        dt.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE),
                                ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        story += [Spacer(1, 10), KeepTogether([section('Écarts déclarés'), Spacer(1, 4), dt])]
    grouped = {}
    for h_ in holds:
        grouped.setdefault(h_['reason'], []).append(h_['unit_id'])
    if holds:
        story += [Spacer(1, 10), KeepTogether([section('Blocages en cours'), Spacer(1, 4),
                  txt('\n'.join(f"• {reason} — {len(ids)} unité(s) : {', '.join(ids)}" for reason, ids in grouped.items()), 'body')])]
    story += [Spacer(1, 10), KeepTogether([section(f'Photos ({len(photos)})'), Spacer(1, 5), photo_grid(photos)])]
    if len(photos) > 6:
        story.append(txt(f'{len(photos) - 6} photo(s) supplémentaire(s) dans le dossier de réception.', 'small'))
    story += [Spacer(1, 8), KeepTogether([section('Pièces jointes'), Spacer(1, 4), attachments_table(docs)])]
    story += history_table(rec.get('history') or [])
    story += [Spacer(1, 10), txt('Fiche établie à partir des saisies du magasin dans TAF WAREHOUSE. Les blocages éventuels restent en place '
                                 'jusqu’à leur levée par une personne habilitée.', 'small')]
    ok = not problems
    return build('Fiche de réception', rec['id'], 'RÉCEPTION CONFORME' if ok else 'PROBLÈME DE RÉCEPTION', 'green' if ok else 'red',
                 story, generated_at, rec['warehouse'] + (' · LTA ' + rec['awb'] if rec.get('awb') else ''))


def history_table(events, title='Historique complet'):
    if not events:
        return []
    head = [Paragraph(h, S['cellhead']) for h in ('DATE', 'PAR', 'ÉVÉNEMENT', 'DÉTAIL')]
    rows = [head] + [[txt(fr_date(e['at'][:19]), 'cell'), txt(e.get('actor'), 'cell'), txt(e['title'], 'cell'), txt(e.get('detail'), 'cell')] for e in events]
    t = Table(rows, colWidths=[CONTENT * .2, CONTENT * .13, CONTENT * .32, CONTENT * .35], repeatRows=1)
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
    return [Spacer(1, 10), section(f'{title} ({len(events)} événement(s))'), Spacer(1, 4), t]


MISSION_STATUS = {'to_assign': ('EN ATTENTE', 'red'), 'assigned': ('AFFECTÉE', 'blue'), 'in_progress': ('EN COURS', 'blue'), 'suspended': ('SUSPENDUE', 'red'),
                  'done': ('TERMINÉE', 'green'), 'closed': ('CLÔTURÉE', 'green'), 'cancelled': ('ANNULÉE', 'red'), 'open': ('EN COURS', 'blue')}
MISSION_EVENTS = {'check': 'Unité scannée', 'take': 'Prise en charge', 'start': 'Démarrage', 'suspend': 'Suspension', 'resume': 'Reprise', 'complete': 'Fin de mission', 'cancel': 'Annulation', 'assign': 'Affectation'}


def mission_report(m, events, units, rec, docs, generated_at):
    """Récapitulatif de mission à imprimer : consignes, unités à traiter et emplacements, suivi."""
    taken = next((e for e in events if e['action'] in ('take', 'start')), None)
    story = [section('Mission'), Spacer(1, 4),
             field_grid([('Mission', m['id']), ('Type', fr(m.get('type'))), ('Priorité', fr(m.get('priority'))),
                         ('Entrepôt', m['warehouse']), ('Demandée par', m.get('created_by')), ('Le', fr_date(m.get('created'))),
                         ('Échéance', (m.get('due_at') or '—').replace('T', ' à ')), ('Pris en charge par', m.get('assignee')),
                         ('Terminée le', fr_date(m.get('completed_at')) if m.get('completed_at') else '—')]),
             Spacer(1, 8), callout('Objet', m['title'], 'navy')]
    if (m.get('description') or '').strip():
        story += [Spacer(1, 6), callout('Consignes de l’exploitation', m['description'], 'red' if m.get('priority') in ('high', 'urgent') else 'navy')]
    if rec:
        story += [Spacer(1, 10), section('Entrée concernée'), Spacer(1, 4),
                  field_grid([('Entrée', rec['id']), ('Client', rec.get('client')), ('LTA', rec.get('awb')),
                              ('Colis reçus', rec.get('actual')), ('Poids déclaré', f"{fr_number(rec.get('weight'))} kg"), ('Reçue le', fr_date(rec.get('created')))])]
    if units:
        head = [Paragraph(h, S['cellhead']) for h in ('OK', 'UNITÉ', 'TYPE', 'COLIS', 'POIDS', 'EMPLACEMENT', 'ÉTAT')]
        st = {'available': 'En stock', 'awaiting_putaway': 'À ranger', 'exited': 'Sortie', 'in_transit': 'En transit', 'depleted': 'Épuisée'}
        rows = [head] + [['', txt(u['id'], 'cell'),
                          txt(f"{(u.get('unit_type') or '').capitalize()} {u['unit_index']}/{u['unit_count']}" if u.get('unit_index') else (u.get('unit_type') or '').capitalize(), 'cell'),
                          txt(u['quantity'], 'cell'), txt(f"{fr_number(u.get('weight'))} kg", 'cell'),
                          Paragraph('<b>' + escape(u.get('location_id') or 'À ranger') + '</b>', S['cell']),
                          txt(st.get(u.get('status'), u.get('status')) + (' · bloquée' if u.get('hold') else ''), 'cell')] for u in units]
        rows.append(['', txt('Total', 'cellhead'), '', txt(sum(u['quantity'] for u in units), 'cellhead'), txt(f"{fr_number(sum(u.get('weight') or 0 for u in units))} kg", 'cellhead'), '', ''])
        t = Table(rows, colWidths=[CONTENT * .05, CONTENT * .22, CONTENT * .14, CONTENT * .08, CONTENT * .12, CONTENT * .2, CONTENT * .19], repeatRows=1)
        t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -2), 0.3, LINE), ('LINEABOVE', (0, -1), (-1, -1), 0.8, NAVY),
                               ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]
                              + [('BOX', (0, r), (0, r), 0.9, MUTED) for r in range(1, len(rows) - 1)]))
        story += [Spacer(1, 10), section(f'Unités à traiter ({len(units)})'), Spacer(1, 4), t]
    head = [Paragraph(h, S['cellhead']) for h in ('DATE', 'PAR', 'ÉTAPE', 'COMMENTAIRE')]
    rows = [head] + [[txt(fr_date(e['created'][:19]), 'cell'), txt(e['actor'], 'cell'), txt(MISSION_EVENTS.get(e['action'], e['action']), 'cell'), txt(e.get('note'), 'cell')] for e in events]
    if len(rows) == 1:
        rows.append([txt('—', 'cell'), '', txt('En attente de prise en charge', 'cell'), ''])
    t = Table(rows, colWidths=[CONTENT * .22, CONTENT * .15, CONTENT * .2, CONTENT * .43], repeatRows=1)
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 0.8, NAVY), ('LINEBELOW', (0, 1), (-1, -1), 0.3, LINE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                           ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
    story += [Spacer(1, 10), KeepTogether([section('Suivi'), Spacer(1, 4), t])]
    story += [Spacer(1, 12), KeepTogether([section('Validation'), Spacer(1, 5),
              signatures_block(('Pris en charge par (magasin)', (taken or {}).get('actor') or m.get('assignee') or '', fr_date(taken['created'][:19]) if taken else 'Date :'),
                               ('Terminé par', m.get('completed_by') or '', fr_date(m['completed_at']) if m.get('completed_at') else 'Date :'))])]
    if docs:
        story += [Spacer(1, 8), KeepTogether([section('Pièces jointes'), Spacer(1, 4), attachments_table(docs)])]
    label, tone = MISSION_STATUS.get(m.get('status'), ('EN COURS', 'blue'))
    return build('Récapitulatif de mission', m['id'], label, tone, story, generated_at, m['warehouse'] + (f" · entrée {rec['id']}" if rec else ''))


def location_signs(rows):
    """Panneaux d'emplacement A4 : 6 par page (2 × 3), identifiant en très gros et QR code."""
    import qrcode
    out = io.BytesIO()
    c = rl_canvas.Canvas(out, pagesize=A4)
    c.setTitle('Panneaux d’emplacement TAF WAREHOUSE')
    cols, lines = 2, 3
    cw, ch = (W - 2 * 10 * mm) / cols, (H - 2 * 10 * mm) / lines
    for i, r in enumerate(rows):
        if i and i % (cols * lines) == 0:
            c.showPage()
        k = i % (cols * lines)
        x0 = 10 * mm + (k % cols) * cw
        y0 = H - 10 * mm - (k // cols + 1) * ch
        c.setStrokeColor(LINE); c.setDash(2, 3); c.rect(x0, y0, cw, ch); c.setDash()
        c.setFillColor(NAVY); c.rect(x0 + 4 * mm, y0 + ch - 16 * mm, cw - 8 * mm, 12 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 11); c.drawString(x0 + 8 * mm, y0 + ch - 11.5 * mm, 'TAF WAREHOUSE')
        c.setFont('Helvetica', 9); c.drawRightString(x0 + cw - 8 * mm, y0 + ch - 11.5 * mm, r['warehouse'])
        c.setFillColor(INK)
        size = 30
        while c.stringWidth(r['id'], 'Helvetica-Bold', size) > cw - 12 * mm and size > 12:
            size -= 1
        c.setFont('Helvetica-Bold', size); c.drawCentredString(x0 + cw / 2, y0 + ch - 32 * mm, r['id'])
        c.setFont('Helvetica', 10); c.setFillColor(MUTED); c.drawCentredString(x0 + cw / 2, y0 + ch - 39 * mm, r.get('zone') or r.get('label') or '')
        img = qrcode.make(r['id'], box_size=8, border=1)
        bio = io.BytesIO(); img.save(bio, format='PNG'); bio.seek(0)
        q = min(cw, ch) - 52 * mm
        c.drawImage(ImageReader(bio), x0 + (cw - q) / 2, y0 + 6 * mm, q, q)
    c.save()
    return out.getvalue()
