"""
Génération du Rapport Journalier de Clôture en PDF.

Structure du rapport :
  En-tête : nom du magasin, titre, caissier / caisse / session, date
  1 — VENTES DU JOUR
  2 — MOUVEMENTS DE CASH
  3 — BILAN GÉNÉRAL
  Pied de page : mention automatique + numéro de page

Bibliothèque : ReportLab (rlPDF) — aucune dépendance système requise.
"""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


# ── Palette de couleurs ────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0D1B4B")
BLUE   = colors.HexColor("#1A56DB")
LIGHT  = colors.HexColor("#EBF0FF")
GRAY   = colors.HexColor("#F5F7FA")
DARK   = colors.HexColor("#1E293B")
GREEN  = colors.HexColor("#15803D")
RED    = colors.HexColor("#B91C1C")
WHITE  = colors.white
BORDER = colors.HexColor("#CBD5E1")

PAGE_W, PAGE_H = A4
MARGIN = 1.8 * cm

ZERO = Decimal("0.00")

# Mois en français (le conteneur Docker n'a pas de locale fr_FR)
_MOIS_FR = [
    "", "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _date_fr(dt):
    """Formatte une date en français : '20 août 2026  ·  10:31'."""
    return f"{dt.day} {_MOIS_FR[dt.month]} {dt.year}  ·  {dt.strftime('%H:%M')}"


# ── Helpers ────────────────────────────────────────────────────────────────────

def _money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt(value):
    """Format monétaire : 1.500.000 (pas de décimales si entier)."""
    amount = _money(value)
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", ".")
    return f"{amount:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _fc_usd(fc, usd):
    return f"{_fmt(fc)} FC  &  {_fmt(usd)} USD"


# ── Styles ─────────────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    return {
        "store":    ParagraphStyle("store",    fontSize=8,  textColor=NAVY,  leading=11),
        "title":    ParagraphStyle("title",    fontSize=18, textColor=NAVY,  leading=22, fontName="Helvetica-Bold"),
        "subtitle": ParagraphStyle("subtitle", fontSize=9,  textColor=DARK,  leading=13),
        "section":  ParagraphStyle("section",  fontSize=11, textColor=NAVY,  leading=15, fontName="Helvetica-Bold"),
        "body":     ParagraphStyle("body",     fontSize=9,  textColor=DARK,  leading=13),
        "footer":   ParagraphStyle("footer",   fontSize=7,  textColor=colors.gray, leading=10, alignment=TA_CENTER),
        "obs_ok":   ParagraphStyle("obs_ok",   fontSize=9,  textColor=GREEN, fontName="Helvetica-Bold"),
        "obs_err":  ParagraphStyle("obs_err",  fontSize=9,  textColor=RED,   fontName="Helvetica-Bold"),
        "obs_neu":  ParagraphStyle("obs_neu",  fontSize=9,  textColor=DARK,  fontName="Helvetica-Bold"),
    }


# ── Table helpers ──────────────────────────────────────────────────────────────

def _header_row(label):
    """Ligne de titre de section dans un tableau."""
    return [label, "", ""]


def _table_style_base():
    return [
        # En-tête colonne : fond sombre, texte blanc
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        # Données : fond blanc, texte sombre
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, WHITE]),
        # Alignement
        ("ALIGN",         (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN",         (0, 0), (0, -1), "LEFT"),
        # Grille fine
        ("GRID",          (0, 0), (-1, -1), 0.25, BORDER),
        # Padding
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (0, -1), 6),
    ]


def _total_style(row_index):
    """Ligne de total : gras + encadré haut/bas, fond blanc."""
    return [
        ("FONTNAME",  (0, row_index), (-1, row_index), "Helvetica-Bold"),
        ("LINEABOVE", (0, row_index), (-1, row_index), 0.75, DARK),
        ("LINEBELOW", (0, row_index), (-1, row_index), 0.75, DARK),
    ]


def _balance_style(row_index):
    """Ligne de solde : gras + fond gris clair + encadré."""
    return [
        ("FONTNAME",   (0, row_index), (-1, row_index), "Helvetica-Bold"),
        ("BACKGROUND", (0, row_index), (-1, row_index), GRAY),
        ("LINEABOVE",  (0, row_index), (-1, row_index), 1.0, DARK),
        ("LINEBELOW",  (0, row_index), (-1, row_index), 1.0, DARK),
    ]


def _subheader_style(row_index):
    """Sous-titre SORTIES/ENTRÉES : fond gris, gras, pas de couleur vive."""
    return [
        ("BACKGROUND", (0, row_index), (-1, row_index), GRAY),
        ("FONTNAME",   (0, row_index), (-1, row_index), "Helvetica-Bold"),
        ("FONTSIZE",   (0, row_index), (-1, row_index), 8),
    ]


# ── Page template (header + footer) ───────────────────────────────────────────

class _ReportDoc(BaseDocTemplate):
    def __init__(self, buf, store_name, session_info, date_str, **kw):
        super().__init__(buf, pagesize=A4, **kw)
        self._store_name = store_name
        self._session_info = session_info
        self._date_str = date_str
        self._styles = _styles()
        frame = Frame(MARGIN, MARGIN + 0.8 * cm, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN - 3.5 * cm, id="main")
        self.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=self._draw_page)])

    def _draw_page(self, canvas, doc):
        canvas.saveState()
        s = self._styles

        # ── En-tête ────────────────────────────────────────────────────────────
        canvas.setFillColor(NAVY)
        canvas.rect(MARGIN, PAGE_H - MARGIN - 2.4 * cm, PAGE_W - 2 * MARGIN, 2.4 * cm, fill=1, stroke=0)

        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 15)
        canvas.drawString(MARGIN + 0.4 * cm, PAGE_H - MARGIN - 1.2 * cm, "RAPPORT JOURNALIER DE CLÔTURE")
        canvas.setFont("Helvetica", 8)
        canvas.drawString(MARGIN + 0.4 * cm, PAGE_H - MARGIN - 1.9 * cm, self._session_info)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(PAGE_W - MARGIN - 0.2 * cm, PAGE_H - MARGIN - 1.2 * cm, self._store_name)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MARGIN - 0.2 * cm, PAGE_H - MARGIN - 1.9 * cm, self._date_str)

        # Ligne de séparation simple
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, PAGE_H - MARGIN - 2.6 * cm, PAGE_W - MARGIN, PAGE_H - MARGIN - 2.6 * cm)

        # ── Pied de page ───────────────────────────────────────────────────────
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.gray)
        canvas.drawCentredString(PAGE_W / 2, MARGIN + 0.3 * cm,
            f"Rapport généré automatiquement — GSM Gestion Commerciale     |     Page {doc.page}")
        canvas.setStrokeColor(BORDER)
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, MARGIN + 0.9 * cm, PAGE_W - MARGIN, MARGIN + 0.9 * cm)

        canvas.restoreState()


# ── Construction du PDF ────────────────────────────────────────────────────────

def generate_session_pdf(session, report, expenses, rate) -> bytes:
    """
    Génère le PDF du rapport de clôture pour une session donnée.

    Args:
        session:  CashSession (clôturée)
        report:   CashReport (depuis selectors.cash_report_for)
        expenses: QuerySet[Expense] — dépenses approuvées de la session
        rate:     Decimal — taux de change (FC / USD)

    Returns:
        bytes — le PDF prêt à être sauvegardé ou envoyé en pièce jointe.
    """
    from django.utils import timezone
    rate = _money(rate)
    buf = BytesIO()
    s = _styles()

    # ── Métadonnées de l'en-tête ───────────────────────────────────────────────
    store_name = _get_store_name()
    closed_at = session.closed_at or session.opened_at
    local_dt = timezone.localtime(closed_at)
    date_str = _date_fr(local_dt)
    session_info = (
        f"Caissier : {session.cashier.get_full_name() or session.cashier.username}   ·   "
        f"Caisse : {session.register.name}   ·   Session #{session.pk}"
    )

    doc = _ReportDoc(buf, store_name, session_info, date_str,
                     leftMargin=MARGIN, rightMargin=MARGIN,
                     topMargin=MARGIN + 3 * cm, bottomMargin=MARGIN + 1.2 * cm)

    col_w = PAGE_W - 2 * MARGIN
    c1 = col_w * 0.55
    c2 = col_w * 0.225
    c3 = col_w * 0.225
    col3 = [c1, c2, c3]
    col2 = [c1 + c2, c3]

    story = []

    # ════════════════════════════════════════════════════════════════════════════
    # 1 — VENTES DU JOUR
    # ════════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("1 — VENTES DU JOUR", s["section"]))
    story.append(Spacer(1, 0.2 * cm))

    sales_data = [
        ["Désignation", "FC", "USD"],
        ["Total vendu", _fmt(report.total_sales), "—"],
    ]
    for exp in expenses:
        sales_data.append([f"    {exp.category} — {exp.description or ''}"[:70], _fmt(exp.amount), "—"])
    total_exp = _money(sum(e.amount for e in expenses))
    sales_data.append(["Total dépenses", _fmt(total_exp), "—"])
    sales_data.append(["Solde vente", _fmt(report.sales_balance), "—"])

    sales_deposit_fc  = _money(session.sales_deposit_local_amount)
    sales_deposit_usd = _money(session.sales_deposit_foreign_amount)
    sales_data.append(["Versement vente", _fmt(sales_deposit_fc), _fmt(sales_deposit_usd)])

    versement_total_fc = _money(sales_deposit_fc + sales_deposit_usd * rate)
    obs_vente_diff     = _money(versement_total_fc - report.sales_balance)

    ts = TableStyle(_table_style_base())
    total_exp_row = 2 + len(list(expenses))
    for cmd in _total_style(total_exp_row):          # Total dépenses
        ts.add(*cmd)
    solde_row = total_exp_row + 1
    for cmd in _balance_style(solde_row):            # Solde vente
        ts.add(*cmd)
    ts.add("FONTNAME", (0, solde_row + 1), (-1, solde_row + 1), "Helvetica-Bold")  # Versement

    tbl = Table(sales_data, colWidths=col3, repeatRows=1)
    tbl.setStyle(ts)
    story.append(tbl)
    story.append(Spacer(1, 0.3 * cm))

    # ════════════════════════════════════════════════════════════════════════════
    # 2 — MOUVEMENTS DE CASH
    # ════════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2 — MOUVEMENTS DE CASH", s["section"]))
    story.append(Spacer(1, 0.2 * cm))

    cash_data = [
        ["Désignation", "FC", "USD"],
        ["Cash initial", _fmt(report.opening_float), _fmt(report.opening_foreign)],
        ["", "", ""],
        ["SORTIES", "FC", "USD"],
    ]

    from apps.pos.models import CashTransaction
    outings = session.cash_transactions.filter(
        direction=CashTransaction.Direction.OUT,
        voided_at__isnull=True,
    ).exclude(category__in=[CashTransaction.Category.EXPENSE, CashTransaction.Category.OPENING_FLOAT])

    outings_row_start = len(cash_data)
    for mv in outings:
        cash_data.append([
            f"  {mv.label or mv.description}"[:65],
            _fmt(mv.amount),
            _fmt(mv.foreign_amount or ZERO),
        ])
    cash_data.append(["Total sorties", _fmt(report.total_out_local), _fmt(report.total_out_foreign)])

    cash_data.append(["", "", ""])
    cash_data.append(["ENTRÉES", "FC", "USD"])
    entries_row_start = len(cash_data)
    entries = session.cash_transactions.filter(
        direction=CashTransaction.Direction.IN,
        voided_at__isnull=True,
    ).exclude(category__in=[CashTransaction.Category.OPENING_FLOAT])

    for mv in entries:
        cash_data.append([
            f"  {mv.label or mv.description}"[:65],
            _fmt(mv.amount),
            _fmt(mv.foreign_amount or ZERO),
        ])
    cash_data.append(["Total entrées", _fmt(report.total_in_local), _fmt(report.total_in_foreign)])

    cash_data.append(["", "", ""])
    cash_data.append(["Solde cash", _fmt(report.expected_local), _fmt(report.expected_foreign)])

    counted_fc  = _money(session.counted_local_amount)
    counted_usd = _money(session.counted_foreign_amount)
    cash_data.append(["Versement cash", _fmt(counted_fc), _fmt(counted_usd)])

    ts2 = TableStyle(_table_style_base())
    # Sous-titres SORTIES / ENTRÉES : gris, pas de couleur vive
    for sub_row in [3, entries_row_start - 1]:
        for cmd in _subheader_style(sub_row):
            ts2.add(*cmd)
    # Totaux sorties / entrées : gras + encadré
    for total_row_idx in [outings_row_start + len(list(outings)), entries_row_start + len(list(entries))]:
        for cmd in _total_style(total_row_idx):
            ts2.add(*cmd)
    # Solde cash : gris clair + gras
    solde_cash_row = len(cash_data) - 2
    for cmd in _balance_style(solde_cash_row):
        ts2.add(*cmd)
    # Versement cash : gras
    ts2.add("FONTNAME", (0, solde_cash_row + 1), (-1, solde_cash_row + 1), "Helvetica-Bold")

    tbl2 = Table(cash_data, colWidths=col3, repeatRows=1)
    tbl2.setStyle(ts2)
    story.append(tbl2)
    story.append(Spacer(1, 0.3 * cm))

    # ════════════════════════════════════════════════════════════════════════════
    # 3 — BILAN GÉNÉRAL
    # ════════════════════════════════════════════════════════════════════════════
    story.append(Paragraph("3 — BILAN GÉNÉRAL", s["section"]))
    story.append(Spacer(1, 0.2 * cm))

    solde_general_fc  = _money(report.sales_balance + report.expected_local)
    solde_general_usd = report.expected_foreign

    total_versement_fc  = _money(sales_deposit_fc + counted_fc)
    total_versement_usd = _money(sales_deposit_usd + counted_usd)

    total_versement_eq_fc = _money(total_versement_fc + total_versement_usd * rate)
    solde_general_eq_fc   = _money(solde_general_fc  + solde_general_usd  * rate)
    diff_fc = _money(total_versement_eq_fc - solde_general_eq_fc)

    if diff_fc == ZERO:
        obs_text  = "RAS — Versement conforme au solde général"
        obs_style = s["obs_ok"]
    elif diff_fc > ZERO:
        obs_text  = f"Surplus de {_fmt(diff_fc)} FC (taux {_fmt(rate)} FC/USD)"
        obs_style = s["obs_ok"]
    else:
        obs_text  = f"Manquant de {_fmt(abs(diff_fc))} FC (taux {_fmt(rate)} FC/USD)"
        obs_style = s["obs_err"]

    bilan_data = [
        ["Désignation", "FC", "USD"],
        ["Solde général  (solde vente + solde cash)", _fmt(solde_general_fc),  _fmt(solde_general_usd)],
        ["Total versement  (versement vente + versement cash)", _fmt(total_versement_fc), _fmt(total_versement_usd)],
        ["Équivalent FC  (USD × taux)", _fmt(solde_general_eq_fc), "→ " + _fmt(total_versement_eq_fc) + " FC"],
    ]

    ts3 = TableStyle(_table_style_base())
    for cmd in _balance_style(1):   # Solde général : gris + gras
        ts3.add(*cmd)
    for cmd in _total_style(2):     # Total versement : gras + encadré
        ts3.add(*cmd)
    # Ligne équivalent FC : simple gras
    ts3.add("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold")

    tbl3 = Table(bilan_data, colWidths=col3, repeatRows=1)
    tbl3.setStyle(ts3)
    story.append(tbl3)
    story.append(Spacer(1, 0.35 * cm))

    # Observation
    obs_data = [["OBSERVATION", obs_text]]
    obs_bg = colors.HexColor("#FEF9C3") if diff_fc > ZERO else (WHITE if diff_fc == ZERO else colors.HexColor("#FEE2E2"))
    obs_ts = TableStyle([
        ("BACKGROUND",    (0, 0), (0, 0), DARK),
        ("TEXTCOLOR",     (0, 0), (0, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 0), (-1, 0), 6),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("LEFTPADDING",   (0, 0), (-1, 0), 8),
        ("GRID",          (0, 0), (-1, 0), 0.5, BORDER),
        ("BACKGROUND",    (1, 0), (1, 0), obs_bg),
        ("TEXTCOLOR",     (1, 0), (1, 0), GREEN if diff_fc >= ZERO else RED),
    ])
    obs_tbl = Table(obs_data, colWidths=[c1 * 0.5, c1 * 0.5 + c2 + c3])
    obs_tbl.setStyle(obs_ts)
    story.append(obs_tbl)

    # Note taux de change
    story.append(Spacer(1, 0.25 * cm))
    story.append(Paragraph(f"<i>Taux de change utilisé : 1 USD = {_fmt(rate)} FC</i>", s["body"]))

    doc.build(story)
    return buf.getvalue()


def _get_store_name():
    try:
        from apps.core.models import StoreSettings
        return StoreSettings.get_solo().name or "GSM"
    except Exception:
        return "GSM"
