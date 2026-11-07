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
            iw, ih = ImageReader(d['path']).getSize()
            scale = min(cell_w / iw, cell_h / ih)
            img = Image(d['path'], width=iw * scale, height=ih * scale)
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
