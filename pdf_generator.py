"""Hardened ReportLab PDF briefing generator with strict XML escaping and path sandboxing."""

import html
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.pdfgen import canvas

from config import config
from security.sandbox import validate_safe_path
from security.sanitizer import safe_escape_xml


def safe_xml(val: Any) -> str:
    """Sanitize text for ReportLab XML parser to prevent syntax crashes or tag escapes."""
    return safe_escape_xml(str(val) if val is not None else "")


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print total page numbers ('Page X of Y')."""
    recipient_title: str = "MUHAMMAD TALHA & KASHMALA TARIQ"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            safe_title = re.sub(r"[^\w\s\.\-&]", "", self.recipient_title)[:80]
            header_text = f"DAILY AI & TECH INTELLIGENCE BRIEF — PREPARED FOR {safe_title}"
            self.drawString(
                42,
                letter[1] - 26,
                header_text,
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(42, letter[1] - 30, letter[0] - 42, letter[1] - 30)

        # Running Footer (all pages)
        self.setFont("Helvetica", 7.5)
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 42, 20, page_str)
        self.drawString(
            42, 20, "CONFIDENTIAL & PROPRIETARY | ZERO-FLUFF INTELLIGENCE | DELIVERY: 07:00 AM"
        )
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(46, 34, letter[0] - 46, 34)
        self.restoreState()


def build_brief_pdf(
    report_data: Dict[str, Any],
    output_path: Path,
    recipient_name: Optional[str] = None,
    allowed_dirs: Optional[List[Path]] = None,
) -> Path:
    """Generate a clean, high-contrast, publication-grade PDF briefing document inside sandboxed boundaries."""
    # Enforce safe path containment
    valid_allowed = allowed_dirs or config.get_allowed_directories()
    safe_target_path = validate_safe_path(output_path, valid_allowed)

    raw_title = recipient_name or "MUHAMMAD TALHA & KASHMALA TARIQ"
    target_title = re.sub(r"[^\w\s\.\-&]", "", raw_title).upper().strip()

    doc = SimpleDocTemplate(
        str(safe_target_path),
        pagesize=letter,
        leftMargin=42,
        rightMargin=42,
        topMargin=38,
        bottomMargin=38,
    )

    styles = getSampleStyleSheet()

    # Color Palette
    primary_color = colors.HexColor("#0f172a")    # Slate 900
    accent_blue = colors.HexColor("#1d4ed8")      # Deep Blue 700
    text_dark = colors.HexColor("#1e293b")        # Slate 800
    bg_box = colors.HexColor("#f8fafc")           # Slate 50
    border_color = colors.HexColor("#cbd5e1")     # Slate 300

    # Custom Typography Styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=primary_color,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=accent_blue,
        spaceAfter=8,
    )

    exec_title_style = ParagraphStyle(
        "ExecBoxTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        textColor=primary_color,
        spaceAfter=5,
    )

    exec_item_style = ParagraphStyle(
        "ExecBoxItem",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=text_dark,
        spaceAfter=3,
    )

    h2_style = ParagraphStyle(
        "PillarHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    )

    body_bullet_style = ParagraphStyle(
        "PillarBullet",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=text_dark,
        spaceAfter=4,
    )

    story = []

    # 1. Document Title & Subtitle
    date_str = safe_xml(report_data.get("date", datetime.now().strftime("%Y-%m-%d")))
    story.append(Paragraph("DAILY AI &amp; TECH INTELLIGENCE BRIEF", title_style))
    story.append(
        Paragraph(
            f"DATE: {date_str} &nbsp;|&nbsp; PREPARED FOR: {safe_xml(target_title)} &nbsp;|&nbsp; DELIVERY: 07:00 AM DAILY",
            subtitle_style,
        )
    )
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=primary_color,
            spaceBefore=0,
            spaceAfter=8,
        )
    )

    # 2. Executive Summary Box (Top Highlights)
    exec_highlights = report_data.get("highlights", [])
    exec_content = [
        Paragraph("<b>EXECUTIVE SUMMARY // TOP 3 HEADLINES OF THE DAY</b>", exec_title_style)
    ]
    for idx, h in enumerate(exec_highlights[:3], 1):
        exec_content.append(
            Paragraph(f"<b>{idx}.</b> {safe_xml(h)}", exec_item_style)
        )

    exec_table = Table(
        [[exec_content]],
        colWidths=[letter[0] - 84],
    )
    exec_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_box),
            ("BOX", (0, 0), (-1, -1), 0.75, border_color),
            ("LINEBEFORE", (0, 0), (0, -1), 3.5, accent_blue),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(exec_table)
    story.append(Spacer(1, 8))

    # 3. The 5 Pillars
    pillars = [
        ("1. New Model Launches & Research Breakthroughs", "pillar_1"),
        ("2. Developer Tools, Frameworks & SDK Updates", "pillar_2"),
        ("3. Major Tech & Industry Moves", "pillar_3"),
        ("4. High-Level Practitioner & Thought Leader Insights", "pillar_4"),
        ("5. Top 3 \"Must-Try\" Repos / Tools of the Day", "pillar_5"),
    ]

    for pillar_title, pillar_key in pillars:
        items = report_data.get(pillar_key, [])

        story.append(Paragraph(pillar_title, h2_style))
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#e2e8f0"),
                spaceBefore=1,
                spaceAfter=4,
            )
        )

        if not items:
            story.append(
                Paragraph(
                    "<i>No high-signal updates meeting zero-fluff criteria in the last 24h.</i>",
                    body_bullet_style,
                )
            )
        else:
            for item in items:
                name = safe_xml(item.get("name", "Update"))
                creator = safe_xml(item.get("creator", ""))
                creator_str = f" ({creator})" if creator else ""
                summary = safe_xml(item.get("summary", ""))
                source_url = item.get("source_url", "")

                source_link = ""
                # Only construct link if URL starts with http(s)://
                if source_url and source_url.startswith(("http://", "https://")):
                    clean_url = html.escape(source_url, quote=True)
                    source_link = f' <font color="#1d4ed8"><u><a href="{clean_url}">(Source)</a></u></font>'

                bullet_text = f"&bull; <b>{name}{creator_str}:</b> {summary}{source_link}"
                story.append(KeepTogether([Paragraph(bullet_text, body_bullet_style)]))

        story.append(Spacer(1, 3))

    class DynamicNumberedCanvas(NumberedCanvas):
        recipient_title = target_title

    doc.build(story, canvasmaker=DynamicNumberedCanvas)
    return safe_target_path
