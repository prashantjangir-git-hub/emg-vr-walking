"""Builds Project9_Report.pdf in the structure required for the SSRP submission:
Cover, Contents, Objective, Experimental Design, Results (separate per member), Analysis, Conclusion (separate per member).
Run after the analysis scripts:  python make_report_pdf.py
Fonts (Inter + Bitstream Charter) are read from analysis/fonts; without them the script falls back to Helvetica / Times."""
import json, os, re
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, NextPageTemplate, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether, CondPageBreak)
from reportlab.platypus.flowables import HRFlowable
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, ".."); OUTPDF = os.path.join(ROOT, "docs", "Project9_Report.pdf")
M = os.path.join(HERE, "members"); C = os.path.join(HERE, "comparison"); FONTS = os.path.join(HERE, "fonts")
NAMES = ["Akshit", "Mehul", "Naveen", "Prashant"]
# Roll numbers are left out of the public repository; fill them in (e.g. {"Akshit": "..."}) to print them on the cover.
ROLL = {}
# individual contributions: own recording + own technique, plus one shared part of the project each (report sections in brackets)
CONTRIB = {
 "Akshit": ("Classical IIR chain (Butterworth band-pass + notch + rectify + low-pass), designed and analysed on own walking recording.",
            "Noise identification and clean-segment selection (8 s window scoring), and the labelled datasets of the supplementary material.",
            "2.2, 3.1, 4.1, 5.1"),
 "Mehul": ("FIR band-pass + adaptive LMS mains canceller + moving RMS, designed and analysed on own walking recording.",
           "Real-time BioRadio-to-Unity bridge: Python interface, live filtering, UDP streaming, calibration lock, logging and the CSV replay tool.",
           "3.2, 5.2 and the live bridge in 2.6 and 4.4"),
 "Naveen": ("Wavelet (db4) denoising + rectify + low-pass, designed and analysed on own walking recording.",
            "Synthetic ground-truth benchmark, comparison of the four techniques and the ranking used to choose the game pipeline.",
            "2.5, 3.3, 4.2, 4.3, 5.3"),
 "Prashant": ("Teager-Kaiser energy operator + low-pass (the technique used in the game), designed and analysed on own walking recording.",
              "Unity game: EMG walking controller, 50 m outdoor course, swinging-hammer obstacles and integration of the TKEO pipeline in the game.",
              "3.4, 5.4 and the game in 2.6 and 4.4")}
S ={n: json.load(open(f"{M}/{n}/summary.json")) for n in NAMES}; W = json.load(open(f"{C}/winner.json")); T = W["table"]
TECH = {"IIR": "Akshit", "ADFIR": "Mehul", "WAVE": "Naveen", "TKEO": "Prashant"}
TITLE_A, TITLE_B = "Real-Time EMG Signal Processing for VR Walking Control", "During Overground Walking Using Unity"
PAGE_W, PAGE_H = A4; MARGIN = 2.2*cm; TEXT_W = PAGE_W - 2*MARGIN

# ------------------------------------------------ fonts
def _fonts():
    try:
        for n, fn in [("Inter", "Inter-Regular"), ("Inter-Italic", "Inter-Italic"), ("Inter-Light", "Inter-Light"), ("Inter-Medium", "Inter-Medium"),
                      ("Inter-SemiBold", "Inter-SemiBold"), ("Inter-SemiBoldItalic", "Inter-SemiBoldItalic"), ("Inter-Bold", "Inter-Bold")]:
            pdfmetrics.registerFont(TTFont(n, os.path.join(FONTS, fn + ".ttf")))
        pdfmetrics.registerFontFamily("Inter", normal="Inter", bold="Inter-SemiBold", italic="Inter-Italic", boldItalic="Inter-SemiBoldItalic")
        for n, base in [("Charter", "bchr8a"), ("Charter-Bold", "bchb8a"), ("Charter-Italic", "bchri8a"), ("Charter-BoldItalic", "bchbi8a")]:
            face = pdfmetrics.EmbeddedType1Face(os.path.join(FONTS, base + ".afm"), os.path.join(FONTS, base + ".pfb")); pdfmetrics.registerTypeFace(face)
            pdfmetrics.registerFont(pdfmetrics.Font(n, face.name, "WinAnsiEncoding"))
        pdfmetrics.registerFontFamily("Charter", normal="Charter", bold="Charter-Bold", italic="Charter-Italic", boldItalic="Charter-BoldItalic")
        return dict(sans="Inter", light="Inter-Light", med="Inter-Medium", sb="Inter-SemiBold", bold="Inter-Bold", serif="Charter", serif_b="Charter-Bold")
    except Exception as e:
        print("fonts not found, using built-in fonts:", e)
        return dict(sans="Helvetica", light="Helvetica", med="Helvetica", sb="Helvetica-Bold", bold="Helvetica-Bold", serif="Times-Roman", serif_b="Times-Bold")
FN = _fonts()

# ------------------------------------------------ palette and styles
NAVY, INK, MUTED, TEAL = colors.HexColor("#12304f"), colors.HexColor("#1f2933"), colors.HexColor("#5f6f7f"), colors.HexColor("#0e7c86")
RULE, ZEBRA, TINT, TEAL_TINT = colors.HexColor("#d7dee6"), colors.HexColor("#f5f8fb"), colors.HexColor("#eef3f8"), colors.HexColor("#e5f3f3")
BODY = ParagraphStyle("BODY", fontName=FN["serif"], fontSize=10, leading=14.6, textColor=INK, alignment=TA_JUSTIFY, spaceAfter=6)
BUL = ParagraphStyle("BUL", parent=BODY, leftIndent=14, bulletIndent=2, spaceAfter=3, bulletFontName=FN["sb"], bulletColor=TEAL, bulletFontSize=9)
KICK = ParagraphStyle("KICK", fontName=FN["sb"], fontSize=8.5, leading=11, textColor=TEAL, spaceAfter=2)
H1 = ParagraphStyle("H1", fontName=FN["sb"], fontSize=23, leading=28, textColor=NAVY, spaceAfter=4)
H2 = ParagraphStyle("H2", fontName=FN["sb"], fontSize=12.5, leading=16.5, textColor=NAVY, spaceBefore=13, spaceAfter=6, keepWithNext=1)
H3 = ParagraphStyle("H3", fontName=FN["sb"], fontSize=7.8, leading=10, textColor=MUTED, spaceBefore=8, spaceAfter=4, keepWithNext=1)
CAP = ParagraphStyle("CAP", fontName=FN["sans"], fontSize=7.8, leading=10.8, textColor=MUTED, alignment=TA_CENTER, spaceBefore=4)
SMALL = ParagraphStyle("SMALL", fontName=FN["sans"], fontSize=7.8, leading=10.8, textColor=MUTED, spaceBefore=3, spaceAfter=4)
CELL = ParagraphStyle("CELL", fontName=FN["sans"], fontSize=8.2, leading=10.6, textColor=INK)
CELLC = ParagraphStyle("CELLC", parent=CELL, alignment=TA_CENTER)
CELLH = ParagraphStyle("CELLH", parent=CELL, fontName=FN["sb"], textColor=colors.white)
CELLHC = ParagraphStyle("CELLHC", parent=CELLH, alignment=TA_CENTER)
NOTE = ParagraphStyle("NOTE", parent=BODY, fontSize=9.2, leading=13.2, spaceAfter=0, textColor=colors.HexColor("#33414f"))
KPI_V = ParagraphStyle("KPI_V", fontName=FN["sb"], fontSize=15, leading=18, textColor=NAVY)
KPI_L = ParagraphStyle("KPI_L", fontName=FN["sans"], fontSize=7.2, leading=9.2, textColor=MUTED)

def P(t, st=BODY): return Paragraph(t, st)
def bullets(items, st=None): return [Paragraph(t, st or BUL, bulletText="•") for t in items]
BUL_LEFT = ParagraphStyle("BUL_LEFT", parent=BUL, alignment=TA_LEFT)       # for items with long file names
def f(x, d=2): return f"{x:.{d}f}"
def num(n): return f'<font color="#0e7c86">{n}</font>&nbsp;&nbsp;'

_key = [0]
def toc(par, level, text):
    _key[0] += 1; par._toc = (level, text, f"k{_key[0]}"); return par
def section(n, title, new_page=False, need=10*cm):
    # a section starts on a new page only when less than `need` is left (avoids near-empty pages); spaceBefore is dropped at a page top
    out = [PageBreak()] if new_page else [CondPageBreak(need)]
    return out + [P(f"SECTION {n:02d}", ParagraphStyle("k", parent=KICK, keepWithNext=1, spaceBefore=18)), toc(P(title, ParagraphStyle("h1k", parent=H1, keepWithNext=1)), 0, f"{n}&nbsp;&nbsp;&nbsp;{title}"),
                  HRFlowable(width=1.5*cm, thickness=2.4, color=TEAL, hAlign="LEFT", spaceBefore=3, spaceAfter=12)]
def h2(n, title, toc_text=None): return toc(P(num(n) + title if n else title, H2), 1, f"{n}&nbsp;&nbsp;&nbsp;{toc_text or title}" if n else (toc_text or title))
SUBT = ParagraphStyle("SUBT", fontName=FN["med"], fontSize=10, leading=13, textColor=TEAL, spaceBefore=-3, spaceAfter=7, keepWithNext=1)
def member_head(n, name, technique):          # "3.1  Akshit" with the technique as a subtitle; the contents page shows both
    return [h2(n, name, f"{name} – {technique}"), P(technique, SUBT)]
def h3(t): return P(t.upper(), H3)

def tbl(rows, widths, center_from=1, total_row=False):
    data = []
    for i, r in enumerate(rows):
        st = (CELLH, CELLHC) if i == 0 else (CELL, CELLC)
        data.append([Paragraph(str(c), st[0] if j < center_from else st[1]) for j, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1)
    sty = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 1), (-1, -1), 0.5, RULE),
           ("TOPPADDING", (0, 0), (-1, -1), 4.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.2), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]
    for i in range(2, len(rows), 2): sty.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    if total_row: sty += [("BACKGROUND", (0, -1), (-1, -1), TEAL_TINT), ("LINEABOVE", (0, -1), (-1, -1), 0.9, TEAL)]
    t.setStyle(TableStyle(sty)); return t

FIG = [0]
def fig(path, width_cm, cap):
    FIG[0] += 1; w, h = PILImage.open(path).size; wd = width_cm*cm
    return KeepTogether([Spacer(1, 4), Image(path, width=wd, height=wd*h/w), P(f'<font name="{FN["sb"]}" color="#12304f">Figure {FIG[0]}.</font>&nbsp; {cap}', CAP), Spacer(1, 8)])

def box(flowables, bg=TINT, bar=TEAL, pad=9):
    t = Table([[flowables]], colWidths=[TEXT_W])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), bg), ("LINEBEFORE", (0, 0), (0, -1), 2.6, bar), ("LEFTPADDING", (0, 0), (-1, -1), pad + 3),
                           ("RIGHTPADDING", (0, 0), (-1, -1), pad), ("TOPPADDING", (0, 0), (-1, -1), pad - 1), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]))
    return t

def kpi_strip(items):
    cells = [[P(v, KPI_V), P(l, KPI_L)] for v, l in items]; n = len(items)
    t = Table([cells], colWidths=[TEXT_W/n]*n)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT), ("LINEABOVE", (0, 0), (-1, 0), 2.2, TEAL), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("LINEBEFORE", (1, 0), (-1, -1), 0.6, RULE), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
    return t

# ------------------------------------------------ page decoration
def draw_cover(c, doc):
    c.saveState()
    try: c.linearGradient(0, PAGE_H, 0, 0, (colors.HexColor("#0a1a2c"), colors.HexColor("#143a5c")), extend=True)
    except Exception: c.setFillColor(NAVY); c.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    # walking calf EMG: bursts of activity once per stride, with the smoothed envelope and detected steps
    rng = np.random.default_rng(11); n = 2200; xs = np.linspace(0, PAGE_W, n); t = np.linspace(0, 7.4, n)
    centres = np.arange(0.55, 7.4, 1.06) + rng.normal(0, 0.035, len(np.arange(0.55, 7.4, 1.06)))
    env = 0.10 + sum(np.exp(-0.5*((t - cc)/0.12)**2) for cc in centres)
    y0 = PAGE_H*0.385; sig = env*rng.standard_normal(n)*22
    c.setStrokeColor(colors.white); c.setStrokeAlpha(0.18); c.setLineWidth(0.5); c.setDash(2, 3)
    for cc in centres:
        x = np.interp(cc - 0.17, t, xs); c.line(x, y0 - 62, x, y0 + 62)
    c.setDash(); c.setStrokeAlpha(0.12); c.line(0, y0, PAGE_W, y0)
    p = c.beginPath(); p.moveTo(xs[0], y0 + sig[0])
    for x, y in zip(xs[1:], sig[1:]): p.lineTo(x, y0 + y)
    c.setStrokeColor(colors.HexColor("#3cc7c2")); c.setStrokeAlpha(0.85); c.setLineWidth(0.45); c.drawPath(p, stroke=1, fill=0)
    e = c.beginPath(); ey = env*48; e.moveTo(xs[0], y0 + ey[0])
    for x, y in zip(xs[1:], ey[1:]): e.lineTo(x, y0 + y)
    c.setStrokeColor(colors.HexColor("#f2b544")); c.setStrokeAlpha(0.95); c.setLineWidth(1.5); c.drawPath(e, stroke=1, fill=0)
    c.setStrokeAlpha(1); c.setFillAlpha(1)
    # title
    c.setFillColor(colors.HexColor("#3cc7c2")); c.rect(MARGIN, PAGE_H - 5.0*cm, 1.6*cm, 3.2, stroke=0, fill=1)
    ta = Paragraph(TITLE_A, ParagraphStyle("ct", fontName=FN["bold"], fontSize=34, leading=40, textColor=colors.white))
    tb = Paragraph(TITLE_B, ParagraphStyle("cs", fontName=FN["light"], fontSize=22, leading=28, textColor=colors.HexColor("#9fe3df")))
    wa, ha = ta.wrap(TEXT_W, PAGE_H); top = PAGE_H - 5.6*cm; ta.drawOn(c, MARGIN, top - ha)
    wb, hb = tb.wrap(TEXT_W, PAGE_H); tb.drawOn(c, MARGIN, top - ha - 10 - hb)
    # team
    c.setStrokeColor(colors.white); c.setStrokeAlpha(0.22); c.setLineWidth(0.6); c.line(MARGIN, 4.7*cm, PAGE_W - MARGIN, 4.7*cm); c.setStrokeAlpha(1)
    c.setFillColor(colors.HexColor("#3cc7c2")); c.setFont(FN["sb"], 8); c.drawString(MARGIN, 3.95*cm, "TEAM")
    c.setFillColor(colors.white); c.setFont(FN["med"], 14.5); col = TEXT_W/4
    for i, n_ in enumerate(NAMES): c.drawString(MARGIN + i*col, 3.15*cm, n_)
    c.setFillColor(colors.HexColor("#9fe3df")); c.setFont(FN["sans"], 9.5)
    for i, n_ in enumerate(NAMES):
        if ROLL.get(n_): c.drawString(MARGIN + i*col, 2.55*cm, ROLL[n_])
    c.restoreState()

def _footer(c, show_header=True):
    c.saveState(); c.setFont(FN["sans"], 7.5); c.setFillColor(MUTED)
    if show_header:
        c.setFillColor(TEAL); c.rect(MARGIN, PAGE_H - 1.42*cm, 0.16*cm, 0.3*cm, stroke=0, fill=1); c.setFillColor(MUTED)
        c.drawString(MARGIN + 0.35*cm, PAGE_H - 1.35*cm, TITLE_A); c.drawRightString(PAGE_W - MARGIN, PAGE_H - 1.35*cm, "SSRP Project 9 · Project Report")
        c.setStrokeColor(RULE); c.setLineWidth(0.5); c.line(MARGIN, PAGE_H - 1.65*cm, PAGE_W - MARGIN, PAGE_H - 1.65*cm)
    c.setStrokeColor(RULE); c.setLineWidth(0.5); c.line(MARGIN, 1.55*cm, PAGE_W - MARGIN, 1.55*cm)
    c.drawString(MARGIN, 1.05*cm, "Akshit · Mehul · Naveen · Prashant")
    c.setFont(FN["sb"], 8.5); c.setFillColor(NAVY); c.drawRightString(PAGE_W - MARGIN, 1.03*cm, str(c.getPageNumber())); c.restoreState()

class ReportDoc(BaseDocTemplate):
    def __init__(self, fn, **kw):
        super().__init__(fn, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=2.35*cm, bottomMargin=2.1*cm, **kw)
        body = Frame(MARGIN, 2.1*cm, TEXT_W, PAGE_H - 2.35*cm - 2.1*cm, id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        self.addPageTemplates([PageTemplate("cover", [Frame(0, 0, PAGE_W, PAGE_H, id="cover")], onPage=draw_cover),
                               PageTemplate("plain", [body], onPage=lambda c, d: _footer(c, False)),
                               PageTemplate("body", [body], onPage=lambda c, d: _footer(c, True))])
    def afterFlowable(self, fl):
        if getattr(fl, "_toc", None):
            level, text, key = fl._toc
            self.canv.bookmarkPage(key); self.canv.addOutlineEntry(re.sub("<[^>]+>", "", text).replace("&nbsp;&nbsp;&nbsp;", "  "), key, level=level, closed=False)
            self.notify("TOCEntry", (level, text, self.page, key))

story = [Spacer(1, 1), NextPageTemplate("plain"), PageBreak()]

# ------------------------------------------------ CONTENTS
TOC = TableOfContents(dotsMinLevel=0, rightColumnWidth=1.2*cm)
TOC.levelStyles = [ParagraphStyle("t0", fontName=FN["sb"], fontSize=10.5, leading=13, textColor=NAVY, spaceBefore=7, leftIndent=0, firstLineIndent=0),
                   ParagraphStyle("t1", fontName=FN["sans"], fontSize=8.8, leading=11.2, textColor=INK, spaceBefore=0.5, leftIndent=0.9*cm, firstLineIndent=0)]
TOC.tableStyle = TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)])
story += [P("PROJECT REPORT", KICK), P("Contents", H1), HRFlowable(width=1.5*cm, thickness=2.4, color=TEAL, hAlign="LEFT", spaceBefore=3, spaceAfter=10),
          box([P(f'<font name="{FN["sb"]}" color="#12304f">SSRP Project 9</font> &nbsp;·&nbsp; {TITLE_A} {TITLE_B}', ParagraphStyle("m", parent=NOTE, fontName=FN["sans"], fontSize=8.6, leading=12.5, alignment=TA_LEFT)),
               P(f'<font name="{FN["sb"]}" color="#12304f">Team</font> &nbsp;{", ".join(f"{n} ({ROLL[n]})" if ROLL.get(n) else n for n in NAMES)} &nbsp;·&nbsp; <font name="{FN["sb"]}" color="#12304f">Date</font> &nbsp;November 2026', ParagraphStyle("m2", parent=NOTE, fontName=FN["sans"], fontSize=8.6, leading=12.5, alignment=TA_LEFT))], pad=8),
          Spacer(1, 6), TOC, NextPageTemplate("body")]

# ------------------------------------------------ INDIVIDUAL CONTRIBUTIONS (front matter, unnumbered)
CL = ParagraphStyle("CL", fontName=FN["sb"], fontSize=7.4, leading=9.5, textColor=TEAL, spaceBefore=7, spaceAfter=1.5)
CT = ParagraphStyle("CT", fontName=FN["sans"], fontSize=8.8, leading=12.2, textColor=INK)
def card(n):
    tech, shared, secs = CONTRIB[n]
    return [P(f'{n} <font name="{FN["sans"]}" size="10" color="#0e7c86">&nbsp;{ROLL[n]}</font>' if ROLL.get(n) else n, ParagraphStyle("cn", fontName=FN["sb"], fontSize=14, leading=17, textColor=NAVY)),
            P("INDIVIDUAL TECHNIQUE", CL), P(tech, CT), P("SHARED PROJECT PART", CL), P(shared, CT), P("REPORT SECTIONS", CL), P(secs, CT)]
grid = Table([[card("Akshit"), card("Mehul")], [card("Naveen"), card("Prashant")]], colWidths=[TEXT_W/2]*2)
grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, -1), TINT), ("LINEABOVE", (0, 0), (-1, -1), 2.2, TEAL),
                          ("LINEBELOW", (0, 0), (-1, 0), 6, colors.white), ("LINEAFTER", (0, 0), (0, -1), 6, colors.white),
                          ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 13)]))
story += [PageBreak(), P("TEAM", KICK), toc(P("Individual Contributions", H1), 0, "Individual Contributions"),
          HRFlowable(width=1.5*cm, thickness=2.4, color=TEAL, hAlign="LEFT", spaceBefore=3, spaceAfter=12),
          P("Each member recorded their own overground walking, designed one filtering technique and analysed it on their own recording; these individual results and conclusions are in Sections 3.1-3.4 and 5.1-5.4. The shared parts of the project were divided equally, one per member, as listed below."),
          Spacer(1, 6), grid, Spacer(1, 12),
          box([P(f'<font name="{FN["sb"]}" color="#12304f">Done jointly by all members:</font> Sections 1, 2.1, 2.3, 2.4, 4.5 and 5.5 of this report, and the demonstration video, in which each member presents their own technique and shared part.', NOTE)])]

# ------------------------------------------------ 1 OBJECTIVE
story += section(1, "Objective", new_page=True)
story += [P("The objective of this project is to acquire surface EMG from the calf (gastrocnemius) muscle of the dominant leg during overground walking, to identify the noise in the signal, to remove it with digital filtering, and to use the cleaned muscle activity to control a virtual character walking in a Unity environment. The specific goals are:"),
          *bullets(["acquire calf EMG during overground walking and analyse how the signal behaves;", "identify the noise sources (baseline drift, 50 Hz mains, motion artifacts);",
                    "design and implement digital filtering techniques, with <b>each team member analysing their own recording with their own technique</b>;",
                    "investigate how the filtering technique affects muscle-activation (step) detection, movement responsiveness and game performance;",
                    "compare the techniques and implement the best one in the Unity game, where the calf muscle activation makes the character step."])]

# ------------------------------------------------ 2 EXPERIMENTAL DESIGN
story += section(2, "Experimental Design", new_page=False)
story += [h2("2.1", "Recording setup"),
          P("EMG was recorded with a BioRadio wireless biosignal device. Channel 1 carried the calf EMG; channels 2-4 were unused and show only a constant DC level. The sampling rate was 1000 Hz. Each of the four members was recorded once while walking overground continuously (no separate conditions): Akshit 117 s, Mehul 243 s, Naveen 231 s and Prashant 101 s. The raw recordings are provided as labelled datasets in the supplementary material."),
          h2("2.2", "Selection of clean segments"),
          P("Whole recordings contain drift jumps and motion artifacts, so each recording was cut into 8 s windows and only good windows were analysed. A window was kept only if (a) it shows a clear stride rhythm (autocorrelation of the signal envelope at least 0.38 at a lag of 0.6-1.6 s), (b) its largest sample is at most 22 times the noise sigma and at most 0.7 % of samples are beyond 8 sigma (no spike), and (c) there is no fast baseline jump. Consecutive good windows were merged into segments."),
          tbl([["Member", "Recording (s)", "Clean signal used (s)", "Share used"]] + [[n, S[n]["recording_s"], S[n]["good_s"], f"{S[n]['good_pct']} %"] for n in NAMES], [4*cm, 3.6*cm, 4.6*cm, 4.4*cm]),
          fig(f"{M}/Prashant/1_data_quality.png", 15.8, "Example of clean-window selection (Prashant): green windows were used, red windows rejected."),
          h2("2.3", "Filtering techniques (one per member)"),
          tbl([["Member", "Technique", "Main steps"],
               ["Akshit", "Classical IIR chain", "Butterworth band-pass 20-450 Hz (4th order), 50 Hz IIR notch (Q = 30), full-wave rectification, 3 Hz low-pass"],
               ["Mehul", "FIR + adaptive LMS + RMS", "151-tap Hamming FIR band-pass 20-450 Hz, normalised LMS 50 Hz canceller (step size 0.01), 200 ms moving RMS"],
               ["Naveen", "Wavelet denoising", "50 Hz notch, Daubechies db4 wavelet (5 levels) on 512-sample blocks with soft thresholding, rectification, 3 Hz low-pass"],
               ["Prashant", "Teager-Kaiser energy operator (TKEO)", "Band-pass + notch as above, TKEO ψ[n] = x[n]<super>2</super> − x[n−1]·x[n+1], 3 Hz low-pass, square root"]], [2.2*cm, 4.3*cm, 10.1*cm], center_from=9),
          P("All techniques are causal (they use only past samples) so that they can run in real time in the game.", SMALL),
          h2("2.4", "Step detection"),
          P("The envelope is compared with thresholds learned from its lowest 30 % (on-threshold = mean + 3 SD, off-threshold = mean + 1.5 SD, giving hysteresis). Every rising edge, at least 0.45 s after the previous one, is counted as one step; one calf burst corresponds to one stride of the dominant leg. The same detector is used for every technique."),
          h2("2.5", "How the techniques were evaluated"),
          *bullets(["<b>Real recordings (no ground truth):</b> burst-to-baseline ratio (90th/10th percentile of the envelope), detected strides per minute, stride-interval variation (CV), residual 50 Hz power. The kit's unfiltered 50 ms RMS method serves as baseline.",
                    "<b>Synthetic benchmark with known ground truth:</b> 60 s walking-like EMG signals with known burst times plus drift, a 1 Hz motion ripple, 50 Hz mains, sensor noise and spikes, in four scenarios (S1 typical, S2 strong 50 Hz hum, S3 many spikes, S4 weak muscle), 5 random seeds each. Measured: step-detection F1, false steps per minute, correlation of the envelope with the true amplitude, and envelope lag."]),
          h2("2.6", "Game system"),
          P("The BioRadio data are read by a Python bridge, filtered in real time and sent over UDP to Unity. In Unity the character takes one stride (1.4 m) for every detected calf burst and plays a walking animation; it stops when the muscle is relaxed or if no data arrive for 0.5 s. The scene is a 50 m outdoor course. Three <b>swinging hammers</b> hang over the path (at 18 m, 30 m and 42 m, swing periods 5.6 s, 4.8 s and 4.4 s, 50 degree swing): the player must time the calf activation so as to cross under a hammer when it is at the side. If a hammer touches the character, the screen flashes red and the character is sent back to the start. Hits and times are logged.")]

# ------------------------------------------------ 3 RESULTS (per member)
story += section(3, "Results")
story += [P("Results are given separately for each member: the member's own technique applied to the member's own recording (clean segments only), compared with the kit's unfiltered baseline, followed by the synthetic ground-truth test of the same technique (the same 4 scenarios × 5 seeds that are used for the comparison in Section 4.2, so the averages below match Section 4.2)."),
          box([P("<b>Note:</b> the kit baseline's burst-to-baseline ratio and stride-interval CV are not good-quality indicators here: the unfiltered signal is dominated by slow baseline drift, which inflates the ratio, and the baseline detects only a few strides, which can give an artificially low CV. The strides detected per minute (expected about 55-65 for one leg) and the 50 Hz share are the more meaningful comparisons.", NOTE)])]
for i, n in enumerate(NAMES):
    s = S[n]; o, b = s["own"], s["baseline"]; syn = s["synthetic_mean"]; sc = list(syn.keys()); so = s["synthetic_overall"]
    own_tbl = tbl([["Measure", "Kit baseline (no filter)", f"{n}'s technique"],
                   ["50 Hz share of band power (%)", f(b["mains_residual_pct"], 1), f(o["mains_residual_pct"], 1)],
                   ["Burst-to-baseline ratio (P90/P10)", f(b["burst_to_baseline"]), f(o["burst_to_baseline"])],
                   ["Strides detected per minute", f(b["strides_per_min"], 1), f(o["strides_per_min"], 1)],
                   ["Stride-interval CV", f(b["stride_CV"]), f(o["stride_CV"])]], [4.1*cm, 2.05*cm, 2.05*cm])
    FIG[0] += 1; sw, sh = PILImage.open(f"{M}/{n}/2_spectrum.png").size; spw = 8.0*cm
    spec = [Image(f"{M}/{n}/2_spectrum.png", width=spw, height=spw*sh/sw), P(f'<font name="{FN["sb"]}" color="#12304f">Figure {FIG[0]}.</font>&nbsp; {n}: power spectrum before and after filtering.', CAP)]
    side = Table([[own_tbl, spec]], colWidths=[8.4*cm, TEXT_W - 8.4*cm])
    side.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story += [PageBreak(), *member_head(f"3.{i+1}", n, s["title"]),          # one page per member
              kpi_strip([(f"{s['good_s']} s", f"clean signal used: {s['good_pct']} % of the {s['recording_s']} s recorded"),
                         (f(o["strides_per_min"], 1), f"strides per minute (kit baseline {f(b['strides_per_min'], 1)})"),
                         (f"{f(o['mains_residual_pct'], 1)} %", f"50 Hz share of band power (kit baseline {f(b['mains_residual_pct'], 1)} %)"),
                         (f(so["F1"]), f"synthetic step F1 · envelope lag {f(so['lag_ms'], 0)} ms")]),
              h3("Result on own recording"), side, Spacer(1, 4),
              h3("Result on the synthetic ground-truth benchmark"),
              tbl([["Scenario", "Step F1", "False steps / min", "Envelope correlation", "Lag (ms)"]] + [[k, f(syn[k]["F1"]), f(syn[k]["FP_per_min"], 1), f(syn[k]["corr"]), f(syn[k]["lag_ms"], 0)] for k in sc]
                   + [["<b>Average</b>", f"<b>{f(so['F1'])}</b>", f"<b>{f(so['FP_per_min'], 1)}</b>", f"<b>{f(so['corr'])}</b>", f"<b>{f(so['lag_ms'], 0)}</b>"]], [5.2*cm, 2.4*cm, 3.2*cm, 3.2*cm, 2.6*cm], total_row=True),
              fig(f"{M}/{n}/3_envelope_and_steps.png", 14.6, f"{n}: raw signal, cleaned signal and envelope with detected steps (red dashes) inside a clean segment.")]

# ------------------------------------------------ 4 ANALYSIS
story += section(4, "Analysis")
story += [h2("4.1", "Noise in the recordings"),
          P("All four recordings show the same noise sources: (1) slow baseline drift of several mV (up to about 7 mV in Naveen's file), much larger than the EMG itself, caused by electrode, skin and cable movement; (2) 50 Hz mains interference, which holds a different share of the 20-450 Hz power in each recording (from 2.5 % for Naveen up to 52 % for Prashant); (3) isolated motion-artifact spikes; (4) a stride-synchronous ripple of about 1 Hz from leg movement; and (5) a small EMG amplitude (about 10-20 µV RMS). The unfiltered method fails because the drift and ripple dominate: it finds only about 10-30 strides per minute instead of 55-65."),
          h2("4.2", "Comparison of the four techniques"),
          P("All techniques were run through the same real-time code and the same tests (synthetic: 4 scenarios × 5 seeds; real: all four recordings, clean segments)."),
          tbl([["Measure", "IIR (Akshit)", "FIR+LMS (Mehul)", "Wavelet (Naveen)", "TKEO (Prashant)"],
               ["Step-detection F1 (synthetic)"] + [f(T[k]["F1"]) for k in TECH],
               ["False steps per minute"] + [f(T[k]["FP_per_min"], 1) for k in TECH],
               ["Worst-scenario F1"] + [f(T[k]["worst_scenario_F1"]) for k in TECH],
               ["Envelope correlation with truth"] + [f(T[k]["corr"]) for k in TECH],
               ["Envelope lag (ms)"] + [f(T[k]["lag_ms"], 0) for k in TECH],
               ["Real data: stride-interval CV"] + [f(T[k]["stride_CV"]) for k in TECH],
               ["Real data: gait-rhythm score"] + [f(T[k]["rhythm_score"]) for k in TECH],
               ["Real data: 50 Hz left (%)"] + [f(T[k]["mains_residual_pct"], 1) for k in TECH]], [5.2*cm, 2.85*cm, 2.85*cm, 2.85*cm, 2.85*cm]),
          fig(f"{C}/1_synthetic_benchmark.png", 16.6, "Synthetic benchmark by scenario: step-detection F1, envelope correlation, false steps per minute and envelope lag."),
          fig(f"{C}/3_synthetic_envelopes.png", 14.6, "Envelopes of the four techniques on a synthetic signal (grey = true muscle amplitude, red dashes = detected steps)."),
          fig(f"{C}/2_real_data_metrics.png", 16.0, "Metrics on the four real recordings."),
          h2("4.3", "Choice of the best technique"),
          P("The techniques were ranked in three categories that follow the project aims: <b>detection</b> (F1 and false steps; weight 50 %, because the game depends on correctly triggering steps), <b>responsiveness</b> (lag; 25 %) and <b>signal fidelity</b> (envelope correlation and rhythm score; 25 %). Differences smaller than a set tolerance count as ties. Mains removal and processing speed were not ranked: all four techniques leave about the same 50 Hz residual and run far faster than real time."),
          KeepTogether(tbl([["Category rank (1 = best)", "IIR", "FIR+LMS", "Wavelet", "TKEO"],
               ["Detection"] + [f(T[k]["cat_detection"], 1) for k in TECH], ["Responsiveness"] + [f(T[k]["cat_responsiveness"], 1) for k in TECH], ["Signal fidelity"] + [f(T[k]["cat_fidelity"], 1) for k in TECH],
               ["Equal-weight score"] + [f(T[k]["score_equal"]) for k in TECH],
               ["<b>Weighted score (lower is better)</b>"] + [f"<b>{f(T[k]['score_weighted'])}</b>" for k in TECH]], [5.8*cm, 2.7*cm, 2.7*cm, 2.7*cm, 2.7*cm], total_row=True)),
          Spacer(1, 10),
          box([P("SELECTED FOR THE GAME", ParagraphStyle("sel", parent=KICK, spaceAfter=3)),
               P(f"{W['title']} ({W['owner']})", ParagraphStyle("selt", fontName=FN["sb"], fontSize=12.5, leading=16, textColor=NAVY, spaceAfter=3)),
               P(f"Weighted score {f(T[W['winner']]['score_weighted'])} (lower is better) · also best with equal weights ({f(T[W['winner']]['score_equal'])})", ParagraphStyle("sels", fontName=FN["sans"], fontSize=8.4, leading=11, textColor=MUTED))],
              bg=TEAL_TINT, pad=10),
          Spacer(1, 10),
          P(f"The <b>{W['title']}</b> technique ({W['owner']}) obtained the best score and was implemented in the game. It also wins when all categories are weighted equally, so the choice does not depend on the weights. The IIR chain gives the most faithful amplitude and the wavelet the lowest lag, but both produce many false steps; the FIR + LMS technique is second in detection but has the largest delay."),
          P(f"On the real recordings, where the true steps are unknown, the four techniques are close: they detect {min(T[k]['strides_per_min'] for k in TECH):.0f}-{max(T[k]['strides_per_min'] for k in TECH):.0f} strides per minute with similar gait-rhythm scores ({f(min(T[k]['rhythm_score'] for k in TECH))}-{f(max(T[k]['rhythm_score'] for k in TECH))}), and TKEO has the least regular stride intervals (CV {f(T['TKEO']['stride_CV'])} against {f(min(T[k]['stride_CV'] for k in TECH if k != 'TKEO'))}-{f(max(T[k]['stride_CV'] for k in TECH if k != 'TKEO'))} for the others). Its first place therefore rests mainly on the synthetic benchmark, where the true step times are known."),
          h2("4.4", "Game implementation"),
          P("The TKEO pipeline runs in the live bridge (mode I), with adaptive thresholds learned from the last 30 s and a calibration lock. The Unity controller turns each detected step into one stride of the character (1.4 m) and the hammer obstacles require timed crossings."),
          h2("4.5", "Limitations"),
          *bullets(["The synthetic signals were generated by us. They test the techniques against a known truth but are not real muscle; the real recordings have no ground-truth step count (no video or foot switch).",
                    f"TKEO ranked first mainly because of the synthetic benchmark. On the real recordings its detected stride intervals were the least regular of the four (CV {f(T['TKEO']['stride_CV'])}), so its advantage on real walking still has to be confirmed with a real step count.",
                    "TKEO gains part of its advantage from squaring, which increases the contrast between bursts and baseline; its amplitude is less faithful than the IIR envelope, so for speed-proportional control the IIR envelope is more accurate.",
                    "The wavelet and LMS parameters were not tuned extensively; their ranking could change with tuning.",
                    "Only 17-55 % of each recording was clean enough to use; better electrode fixation and cable strain relief would improve all techniques.",
                    "The EMG amplitude was small (about 10-20 µV RMS), lower than is usually seen for the calf during walking. This may come from electrode contact or from the conversion of the device values to mV, which was not checked against a known calibration signal, so absolute amplitudes should be read with care. The comparison does not depend on them: all thresholds and measures are relative to each recording.",
                    "The thresholds for clean-window selection were chosen by the team."])]

# ------------------------------------------------ 5 CONCLUSION
CONC = {
 "Akshit": f"The classical IIR chain removed the drift and 50 Hz hum (50 Hz share on Akshit's data fell from {f(S['Akshit']['baseline']['mains_residual_pct'],1)} % to {f(S['Akshit']['own']['mains_residual_pct'],1)} %) and recovered a plausible {f(S['Akshit']['own']['strides_per_min'],1)} strides per minute, compared with {f(S['Akshit']['baseline']['strides_per_min'],1)} for the unfiltered method. It follows the muscle amplitude best (envelope correlation {f(S['Akshit']['synthetic_overall']['corr'])}) but its 3 Hz smoothing blurs neighbouring bursts, so step detection was only moderate (F1 {f(S['Akshit']['synthetic_overall']['F1'])}). It is a good choice for speed-proportional control but not for reliable step triggering.",
 "Mehul": f"The FIR band-pass with an adaptive LMS canceller cut the 50 Hz share from {f(S['Mehul']['baseline']['mains_residual_pct'],1)} % to {f(S['Mehul']['own']['mains_residual_pct'],1)} % and gave the second-best step detection (F1 {f(S['Mehul']['synthetic_overall']['F1'])}, {f(S['Mehul']['synthetic_overall']['FP_per_min'],1)} false steps per minute). Its drawback is the delay of about {f(S['Mehul']['synthetic_overall']['lag_ms'],0)} ms (FIR group delay plus the 200 ms RMS window), which would be noticeable in a game, and spikes reduce its amplitude accuracy.",
 "Naveen": f"The wavelet technique gave the highest contrast on the real recording (burst-to-baseline ratio {f(S['Naveen']['own']['burst_to_baseline'],1)}) and the lowest lag ({f(S['Naveen']['synthetic_overall']['lag_ms'],0)} ms), even though Naveen's recording had the most drift and artifacts (only {S['Naveen']['good_pct']} % usable). However, block-edge effects and thresholding created many false bursts, so step detection was the weakest (F1 {f(S['Naveen']['synthetic_overall']['F1'])}). With better tuning (longer blocks, overlap-add) it could improve, but with the current settings it is not suitable for step triggering.",
 "Prashant": f"The Teager-Kaiser energy operator removed the strong 50 Hz interference in Prashant's data (from {f(S['Prashant']['baseline']['mains_residual_pct'],1)} % to {f(S['Prashant']['own']['mains_residual_pct'],1)} % of the band power) and recovered {f(S['Prashant']['own']['strides_per_min'],1)} strides per minute against {f(S['Prashant']['baseline']['strides_per_min'],1)} for the unfiltered method. On the ground-truth benchmark it detected steps best (F1 {f(S['Prashant']['synthetic_overall']['F1'])}, {f(S['Prashant']['synthetic_overall']['FP_per_min'],1)} false steps per minute) at a lag of only {f(S['Prashant']['synthetic_overall']['lag_ms'],0)} ms. Its amplitude is less faithful than the IIR envelope, but for step-triggered control it scored best of the four in the ranking, so it was implemented in the game."}
story += section(5, "Conclusion")
story += [P("Conclusions are given separately for each member, followed by the overall conclusion of the team.")]
for i, n in enumerate(NAMES): story += [*member_head(f"5.{i+1}", n, S[n]["title"]), P(CONC[n])]
story += [h2("5.5", "Team conclusion"),
          box([P("Calf EMG recorded during overground walking is dominated by baseline drift, 50 Hz hum and motion artifacts, so unfiltered processing cannot detect steps reliably. All four filtering techniques removed the main noise and recovered a plausible stride rate of about 52-65 strides per minute, but they differ in what they do best: the IIR chain in amplitude fidelity, the wavelet in lag, the FIR + LMS technique in hum rejection, and the TKEO in step detection. For the step-triggered Unity game the TKEO technique was the best choice and was implemented, together with swinging-hammer obstacles that require the player to control the calf activation and time the crossings. Because the ranking rests mainly on the synthetic benchmark, it should be confirmed with real step counts (video or a foot switch) and timed runs in the game; a hybrid (TKEO for step triggering and the IIR envelope for speed) is a possible improvement.", ParagraphStyle("tc", parent=BODY, spaceAfter=0))], bg=TINT, pad=11),
          h2(None, "Supplementary material", "Supplementary material"),
          P("The labelled datasets and the code are attached to this PDF as two files:"),
          *bullets(["<b>Project9_Supplementary_Datasets.zip</b> \u2013 four labelled datasets (one per team member): Akshit_labelled.csv, Mehul_labelled.csv, Naveen_labelled.csv and Prashant_labelled.csv, each with the raw signal and labels for the activity, clean/rejected segments and detected steps (see README_datasets.md).",
                    "<b>Project9_Code.zip</b> \u2013 the analysis code, the real-time bridge and the Unity project (see README.md)."], BUL_LEFT),
          P("To open the attachments, download the PDF and use the attachments panel (paper-clip icon) in Adobe Acrobat Reader or Firefox.", SMALL)]

ReportDoc(OUTPDF, title=f"{TITLE_A} {TITLE_B}", author="Akshit, Mehul, Naveen, Prashant", subject="SSRP Project 9 - Project Report").multiBuild(story)

# ------------------------------------------------ attach the datasets and the code to the PDF (needs pypdf)
def _zip(name, paths):
    import io, zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in paths: z.write(p, os.path.relpath(p, ROOT))
    return name, buf.getvalue()
def _files(*rel, skip=()):
    out = []
    for r in rel:
        p = os.path.join(ROOT, r)
        if os.path.isfile(p): out.append(p)
        for d, dirs, fs in os.walk(p):
            dirs[:] = sorted(x for x in dirs if x != "__pycache__"); out += [os.path.join(d, x) for x in sorted(fs) if not x.endswith(".pyc") and x not in skip]
    return out
try:
    from pypdf import PdfReader, PdfWriter
    att = [_zip("Project9_Supplementary_Datasets.zip", _files("data")),
           _zip("Project9_Code.zip", _files("README.md", "requirements.txt", "analysis", "bridge", "unity"))]
    w = PdfWriter(clone_from=PdfReader(OUTPDF))
    for name, data in att: w.add_attachment(name, data)
    with open(OUTPDF, "wb") as fh: w.write(fh)
    print("attached:", ", ".join(f"{n} ({len(d)/1e6:.1f} MB)" for n, d in att))
except ImportError:
    print("pypdf not installed - PDF written without the attached datasets and code (pip install pypdf)")
print("wrote", OUTPDF)
