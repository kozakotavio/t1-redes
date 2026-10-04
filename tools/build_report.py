"""Gera o PDF do relatorio a partir de RELATORIO_TECNICO.md.

Ferramenta de autoria local: requer ReportLab. O servidor e os testes nao
dependem dela e continuam usando apenas a biblioteca padrao do Python.
"""

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT_ROOT / "RELATORIO_TECNICO.md"
OUTPUT = PROJECT_ROOT / "output" / "pdf" / "relatorio_tecnico_grupo7.pdf"
BLUE = colors.HexColor("#123B5D")
CYAN = colors.HexColor("#087EA4")
PALE = colors.HexColor("#EAF4F8")
TEXT = colors.HexColor("#172B3A")


def register_fonts():
    fonts = Path(reportlab.__file__).resolve().parent / "fonts"
    pdfmetrics.registerFont(TTFont("VeraReport", str(fonts / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("VeraReport-Bold", str(fonts / "VeraBd.ttf")))
    pdfmetrics.registerFont(TTFont("VeraReport-Italic", str(fonts / "VeraIt.ttf")))
    pdfmetrics.registerFontFamily(
        "VeraReport",
        normal="VeraReport",
        bold="VeraReport-Bold",
        italic="VeraReport-Italic",
        boldItalic="VeraReport-Bold",
    )


def make_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="VeraReport-Bold",
            fontSize=17, leading=21, textColor=BLUE, alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "section": ParagraphStyle(
            "ReportSection", parent=base["Heading2"], fontName="VeraReport-Bold",
            fontSize=10.6, leading=13, textColor=BLUE, spaceBefore=9,
            spaceAfter=4, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=base["BodyText"], fontName="VeraReport",
            fontSize=8.5, leading=11.4, textColor=TEXT, spaceAfter=4,
            allowWidows=0, allowOrphans=0,
        ),
        "note": ParagraphStyle(
            "ReportNote", parent=base["BodyText"], fontName="VeraReport",
            fontSize=8.2, leading=11, textColor=BLUE, leftIndent=10,
            rightIndent=8, spaceBefore=3, spaceAfter=6,
        ),
        "table": ParagraphStyle(
            "ReportTable", parent=base["BodyText"], fontName="VeraReport",
            fontSize=7.1, leading=9, textColor=TEXT,
        ),
        "table_header": ParagraphStyle(
            "ReportTableHeader", parent=base["BodyText"], fontName="VeraReport-Bold",
            fontSize=7.2, leading=9.1, textColor=BLUE,
        ),
        "bullet": ParagraphStyle(
            "ReportBullet", parent=base["BodyText"], fontName="VeraReport",
            fontSize=8.1, leading=10.8, textColor=TEXT, leftIndent=10,
            firstLineIndent=-6, spaceAfter=2,
        ),
    }


def inline_markdown(value):
    value = html.escape(value.strip())
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    return value


def make_table(lines, styles, width):
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    columns = len(rows[0])
    compact = rows[0][0] == "Caso"
    if columns == 2:
        col_widths = [width * 0.32, width * 0.68]
    elif columns == 3:
        col_widths = [width * 0.48, width * 0.26, width * 0.26]
    else:
        col_widths = [width / columns] * columns
    body_style = styles["table"]
    header_style = styles["table_header"]
    if compact:
        body_style = ParagraphStyle(
            "CompactTable", parent=body_style, fontSize=6.7, leading=8.2
        )
        header_style = ParagraphStyle(
            "CompactTableHeader", parent=header_style, fontSize=6.7, leading=8.2
        )
    data = [
        [
            Paragraph(inline_markdown(cell), header_style if row_num == 0 else body_style)
            for cell in row
        ]
        for row_num, row in enumerate(rows)
    ]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), PALE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFC")]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, CYAN),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6E3EA")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2 if compact else 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 if compact else 3),
            ]
        )
    )
    return table


def build_story(styles, width):
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    story = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline_markdown(line[2:]), styles["title"]))
            index += 1
            continue
        if line.startswith("## "):
            if line.startswith("## 10."):
                story.append(PageBreak())
            story.append(Paragraph(inline_markdown(line[3:]), styles["section"]))
            index += 1
            continue
        if line.startswith("| "):
            block = []
            while index < len(lines) and lines[index].startswith("|"):
                block.append(lines[index])
                index += 1
            story.extend((make_table(block, styles, width), Spacer(1, 5)))
            continue
        if line.startswith("- "):
            story.append(Paragraph("- " + inline_markdown(line[2:]), styles["bullet"]))
            index += 1
            continue
        if line.startswith("> "):
            block = []
            while index < len(lines) and lines[index].startswith("> "):
                block.append(lines[index][2:].strip())
                index += 1
            story.append(Paragraph(inline_markdown(" ".join(block)), styles["note"]))
            continue

        block = []
        while index < len(lines) and lines[index].strip() and not lines[index].startswith(
            ("# ", "## ", "| ", "- ", "> ")
        ):
            block.append(lines[index].strip())
            index += 1
        story.append(Paragraph(inline_markdown(" ".join(block)), styles["body"]))
    return story


def draw_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#C7DCE7"))
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 17 * mm, A4[0] - 18 * mm, 17 * mm)
    canvas.setFont("VeraReport", 7.5)
    canvas.setFillColor(BLUE)
    canvas.drawString(18 * mm, 12 * mm, "Grupo 7 | Laboratorio de Redes de Computadores")
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def main():
    register_fonts()
    styles = make_styles()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page_width, page_height = A4
    margin_x = 18 * mm
    frame = Frame(
        margin_x,
        22 * mm,
        page_width - 2 * margin_x,
        page_height - 40 * mm,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4, title="Relatorio tecnico - Servidor HTTP/1.1 - Grupo 7",
        author="Grupo 7", subject="Laboratorio de Redes de Computadores - T1",
    )
    doc.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=draw_page))
    doc.build(build_story(styles, page_width - 2 * margin_x))
    print(OUTPUT)


if __name__ == "__main__":
    main()
