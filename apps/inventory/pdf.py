"""
Génération du Rapport Global d'Inventaire en PDF.

Structure :
  En-tête : magasin, inventaire, responsable, dates
  Résumé   : nb articles, nb écarts, valeur totale
  Tableau  : article, stock système, compté, écart, note
  Pied de page : mention + numéro de page
"""
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# ── Palette ───────────────────────────────────────────────────────────────────
DARK   = colors.HexColor("#1E293B")
NAVY   = colors.HexColor("#0D1B4B")
GRAY   = colors.HexColor("#F5F7FA")
BORDER = colors.HexColor("#CBD5E1")
GREEN  = colors.HexColor("#15803D")
RED    = colors.HexColor("#B91C1C")
ORANGE = colors.HexColor("#B45309")
WHITE  = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

_MOIS_FR = ["", "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def _date_fr(dt):
    if dt is None:
        return "—"
    return f"{dt.day} {_MOIS_FR[dt.month]} {dt.year}  ·  {dt.strftime('%H:%M')}"


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("inv_title", parent=base["Heading1"], fontSize=18, textColor=NAVY,
                                fontName="Helvetica-Bold", spaceAfter=2),
        "sub":   ParagraphStyle("inv_sub", parent=base["Normal"], fontSize=10, textColor=DARK,
                                fontName="Helvetica"),
        "eyebrow": ParagraphStyle("inv_eyebrow", parent=base["Normal"], fontSize=8, textColor=colors.HexColor("#64748B"),
                                  fontName="Helvetica-Bold", spaceAfter=1),
        "section": ParagraphStyle("inv_section", parent=base["Normal"], fontSize=10, textColor=DARK,
                                  fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=4),
        "footer": ParagraphStyle("inv_footer", parent=base["Normal"], fontSize=7, textColor=colors.HexColor("#94A3B8"),
                                 fontName="Helvetica", alignment=TA_CENTER),
    }


def _footer(canvas, doc, store_name):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    footer_text = f"Rapport d'inventaire — {store_name}    ·    Page {doc.page}"
    canvas.drawCentredString(PAGE_W / 2, 1.1 * cm, footer_text)
    canvas.restoreState()


def _header_separator(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, PAGE_H - 2.2 * cm, PAGE_W - MARGIN, PAGE_H - 2.2 * cm)
    canvas.restoreState()


def generate_inventory_pdf(count, store_name="Supermarché") -> bytes:
    """
    Génère le PDF du rapport d'inventaire pour un InventoryCount.
    Retourne les bytes du PDF.
    """
    buf = BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=2.8 * cm, bottomMargin=2.2 * cm,
    )

    def on_page(canvas, d):
        _footer(canvas, d, store_name)

    frame = Frame(MARGIN, 2.2 * cm, PAGE_W - 2 * MARGIN, PAGE_H - 5 * cm, id="main")
    doc.addPageTemplates([PageTemplate(id="default", frames=[frame], onPage=on_page)])

    s = _styles()
    story = []

    # ── En-tête ────────────────────────────────────────────────────────────────
    story.append(Paragraph("RAPPORT D'INVENTAIRE", s["eyebrow"]))
    story.append(Paragraph(f"Inventaire {count.reference}", s["title"]))
    story.append(Paragraph(
        f"{store_name}  ·  "
        f"Démarré le {_date_fr(count.started_at)}  ·  "
        f"Clôturé le {_date_fr(count.completed_at)}",
        s["sub"]
    ))
    story.append(Paragraph(
        f"Responsable ouverture : {count.created_by.username}   |   "
        f"Clôturé par : {count.completed_by.username if count.completed_by else '—'}",
        s["sub"]
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ── Résumé ─────────────────────────────────────────────────────────────────
    lines = list(count.lines.select_related("variant__product").all())
    total_lines = len(lines)
    with_diff  = sum(1 for l in lines if l.difference != 0)
    surplus    = sum(1 for l in lines if l.difference > 0)
    manquant   = sum(1 for l in lines if l.difference < 0)

    summary_data = [
        ["Articles inventoriés", "Avec écart", "Surplus", "Manquant"],
        [str(total_lines), str(with_diff), f"+{surplus}", f"−{manquant}"],
    ]
    summary_table = Table(summary_data, colWidths=[(PAGE_W - 2 * MARGIN) / 4] * 4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GRAY),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 8),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.HexColor("#64748B")),
        ("FONTNAME",   (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 1), (-1, 1), 14),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, 1), [WHITE]),
        ("GRID",       (0, 0), (-1, -1), 0.5, BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.4 * cm))

    # ── Note ───────────────────────────────────────────────────────────────────
    if count.note:
        story.append(Paragraph(f"Note : {count.note}", s["sub"]))
        story.append(Spacer(1, 0.3 * cm))

    # ── Tableau des lignes ─────────────────────────────────────────────────────
    story.append(Paragraph("Détail par article", s["section"]))

    col_w = PAGE_W - 2 * MARGIN
    col_widths = [col_w * 0.40, col_w * 0.15, col_w * 0.15, col_w * 0.14, col_w * 0.16]
    header_row = ["Article", "Système", "Compté", "Écart", "Note"]
    rows = [header_row]

    for line in lines:
        diff = line.difference
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        rows.append([
            f"{line.variant.product.name} / {line.variant.name}",
            str(line.system_quantity),
            str(line.counted_quantity) if line.counted_quantity is not None else "—",
            diff_str,
            (line.note or "")[:40],
        ])

    table = Table(rows, colWidths=col_widths, repeatRows=1)

    # Style de base
    style = [
        ("BACKGROUND",    (0, 0), (-1, 0),  GRAY),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  8),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  DARK),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.4, BORDER),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("ALIGN",         (0, 0), (0, -1),  "LEFT"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (0, -1),  6),
    ]

    # Coloration des lignes avec écart
    for i, line in enumerate(lines, start=1):
        if line.difference > 0:
            style.append(("TEXTCOLOR", (3, i), (3, i), GREEN))
            style.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))
        elif line.difference < 0:
            style.append(("TEXTCOLOR", (3, i), (3, i), RED))
            style.append(("FONTNAME",  (3, i), (3, i), "Helvetica-Bold"))

    table.setStyle(TableStyle(style))
    story.append(table)

    doc.build(story)
    return buf.getvalue()
