#!/usr/bin/env python3
# scripts/make_pdf_report.py — builds docs/FolderGuardian_Project_Report.pdf
#
# Usage:
#   .venv/bin/python scripts/make_pdf_report.py

import math
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.graphics.shapes import Drawing, Line, Polygon, Rect, String

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "FolderGuardian_Project_Report.pdf",
)

PAGE_W, PAGE_H = A4
MARGIN = 2.2 * cm
CONTENT_W = PAGE_W - 2 * MARGIN

PRIMARY = colors.HexColor("#1F3A5F")
ACCENT = colors.HexColor("#2E86AB")
LIGHT = colors.HexColor("#EAF2F8")
LIGHT2 = colors.HexColor("#FDF2E9")
GREY = colors.HexColor("#5A6B7B")
RED = colors.HexColor("#B03A2E")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleMain", fontName="Helvetica-Bold", fontSize=25,
                          leading=31, textColor=PRIMARY, spaceAfter=4))
styles.add(ParagraphStyle(name="Subtitle", fontName="Helvetica", fontSize=12.5,
                          leading=17, textColor=GREY, spaceAfter=6))
styles.add(ParagraphStyle(name="H1Blue", fontName="Helvetica-Bold", fontSize=15.5,
                          leading=20, textColor=PRIMARY, spaceBefore=14, spaceAfter=8))
styles.add(ParagraphStyle(name="H2Blue", fontName="Helvetica-Bold", fontSize=12,
                          leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=4))
styles.add(ParagraphStyle(name="Body", fontName="Helvetica", fontSize=10.5,
                          leading=15.5, textColor=colors.HexColor("#222222"),
                          spaceAfter=6))
styles.add(ParagraphStyle(name="BulletItem", fontName="Helvetica", fontSize=10.5,
                          leading=15, leftIndent=14, bulletIndent=4,
                          textColor=colors.HexColor("#222222"), spaceAfter=3))
styles.add(ParagraphStyle(name="Caption", fontName="Helvetica-Oblique", fontSize=9,
                          leading=12, alignment=1, textColor=GREY))


# ─────────────────────────────────────────────────────────────
# Diagram helpers (pure reportlab graphics — no extra deps)
# ─────────────────────────────────────────────────────────────
def _box(d, x, y, w, h, label, fill=LIGHT, stroke=ACCENT, fs=8):
    d.add(Rect(x, y, w, h, rx=6, ry=6, fillColor=fill, strokeColor=stroke,
               strokeWidth=1.4))
    cx = x + w / 2
    lines = label.split("\n")
    total = len(lines) * fs * 1.25
    top = y + h / 2 + total / 2 - fs * 0.4
    for i, ln in enumerate(lines):
        d.add(String(cx, top - i * fs * 1.25, ln, fontName="Helvetica-Bold",
                     fontSize=fs, fillColor=PRIMARY, textAnchor="middle"))


def _arrowhead(d, x2, y2, ang, color, L=8, spread=0.45):
    d.add(Polygon(
        [x2, y2,
         x2 - L * math.cos(ang - spread), y2 - L * math.sin(ang - spread),
         x2 - L * math.cos(ang + spread), y2 - L * math.sin(ang + spread)],
        fillColor=color, strokeColor=color))


def _arrow(d, x1, y1, x2, y2, color=ACCENT, width=1.4):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=width))
    _arrowhead(d, x2, y2, math.atan2(y2 - y1, x2 - x1), color)


# ─────────────────────────────────────────────────────────────
# Architecture diagram — three dashed stage frames
# All box y-coordinates are BOTTOM edges, in cm.
# ─────────────────────────────────────────────────────────────
def build_architecture_drawing() -> Drawing:
    W = CONTENT_W          # ≈ 16.6 cm
    H = 17.0 * cm
    d = Drawing(W, H)
    m = 0.4 * cm           # outer margin inside the drawing

    # Stage frame x-layout (cm): s1 | gap | s2 | gap | s3
    s1_x, s1_w = 0.4, 4.6          # right edge 5.0
    s2_x, s2_w = 5.8, 6.0          # right edge 11.8
    s3_x, s3_w = 12.6, W / cm - 12.6 - 0.4   # right edge W - 0.4

    def _frame(x_cm, w_cm, title):
        x, w = x_cm * cm, w_cm * cm
        d.add(Rect(x, m, w, H - 2 * m, fillColor=colors.white,
                   strokeColor=PRIMARY, strokeWidth=1.2, strokeDashArray=[4, 3]))
        d.add(String(x + w / 2, H - m - 12, title, fontName="Helvetica-Bold",
                     fontSize=7.5, fillColor=PRIMARY, textAnchor="middle"))

    _frame(s1_x, s1_w, "MONITORING & GATEKEEPING")
    _frame(s2_x, s2_w, "LANGGRAPH AI PIPELINE (GROQ LLM)")
    _frame(s3_x, s3_w, "ARTIFACTS & STORAGE")

    # ── Stage 1 boxes ──
    bw1 = (s1_w - 0.6) * cm
    s1_boxes = [
        ("Watchdog Observer\n(up to 4 folders)", 13.6),
        ("Debounce Window\nresolves create/move race", 11.3),
        ("Batch Collector\n2 s window → one popup", 9.0),
        ("Guardian Popup\nAllow / Deny", 6.7),
        ("Step Choice\n2-step / 4-step", 4.4),
    ]
    for label, y in s1_boxes:
        _box(d, (s1_x + 0.3) * cm, y * cm, bw1, 1.8 * cm, label, fs=7.5)
    # flow arrows: each box bottom → next box top (0.5 cm gaps)
    for _, y in s1_boxes[:-1]:
        _arrow(d, (s1_x + s1_w / 2) * cm, y * cm, (s1_x + s1_w / 2) * cm,
               (y - 0.5) * cm, width=1.2)
    # deny annotation (empty area below Step Choice box)
    d.add(String((s1_x + s1_w / 2) * cm, 2.9 * cm, "Deny → returned",
                 fontName="Helvetica-Oblique", fontSize=6.5, fillColor=RED,
                 textAnchor="middle"))
    d.add(String((s1_x + s1_w / 2) * cm, 2.4 * cm, "to origin / deleted",
                 fontName="Helvetica-Oblique", fontSize=6.5, fillColor=RED,
                 textAnchor="middle"))

    # ── Stage 2 boxes ──
    bw2 = (s2_w - 0.6) * cm
    bx2 = (s2_x + 0.3) * cm
    s2_boxes = [
        ("1 · INGEST\nloaders · chunk · embed · summarize", 13.6),
        ("2 · ANALYZE   (4-step only)\nentities · risks · recommendations", 10.8),
        ("3 · GENERATE\nRAG retrieval per section", 8.0),
        ("4 · REVIEW   (4-step only)\nQA pass + review notes", 5.2),
    ]
    for label, y in s2_boxes:
        _box(d, bx2, y * cm, bw2, 1.9 * cm, label, fs=7.5)

    bxc = bx2 + bw2 / 2
    # Ingest bottom → fork junction
    fork_y = 13.3 * cm
    d.add(Line(bxc, 13.6 * cm, bxc, fork_y, strokeColor=ACCENT, strokeWidth=1.2))
    # 4-step: fork → Analyze top
    _arrow(d, bxc, fork_y, bxc, 12.7 * cm, width=1.2)
    d.add(String(bxc + 0.12 * cm, 12.9 * cm, "4-step", fontName="Helvetica",
                 fontSize=6.5, fillColor=GREY))
    # 2-step: bypass Analyze through the right corridor into Generate
    corr_x = (s2_x + s2_w - 0.15) * cm
    gen_mid_y = 8.95 * cm
    d.add(Line(bxc, fork_y, corr_x, fork_y, strokeColor=ACCENT, strokeWidth=1.2))
    d.add(Line(corr_x, fork_y, corr_x, gen_mid_y, strokeColor=ACCENT, strokeWidth=1.2))
    _arrow(d, corr_x, gen_mid_y, bx2 + bw2, gen_mid_y, width=1.2)
    d.add(String(10.3 * cm, 13.42 * cm, "2-step", fontName="Helvetica",
                 fontSize=6.5, fillColor=GREY, textAnchor="middle"))
    # Analyze → Generate, Generate → Review
    _arrow(d, bxc, 10.8 * cm, bxc, 9.9 * cm, width=1.2)
    _arrow(d, bxc, 8.0 * cm, bxc, 7.1 * cm, width=1.2)

    # ── Stage 3 boxes ──
    bw3 = (s3_w - 0.6) * cm
    s3_boxes = [
        ("Chroma Vector Store\nknowledge/…/chroma", 13.6),
        ("JSON Summaries\nknowledge/…/summaries", 11.3),
        ("Step Folders\n01_Ingest … 04_Review", 9.0),
        ("Generated Report\n<title>.docx", 6.7),
        ("Archived Originals\nsource/", 4.4),
    ]
    for label, y in s3_boxes:
        _box(d, (s3_x + 0.3) * cm, y * cm, bw3, 1.8 * cm, label, fill=LIGHT2, fs=7)

    # ── Cross-stage arrows ──
    # allow: stage 1 → Ingest (top lane)
    _arrow(d, 5.0 * cm, 14.5 * cm, (s2_x + 0.3) * cm - 2, 14.5 * cm, width=1.5)
    d.add(String(5.4 * cm, 14.62 * cm, "allow", fontName="Helvetica",
                 fontSize=6.5, fillColor=GREY, textAnchor="middle"))
    # ingest writes artifacts: stage 2 → stage 3 (top lane)
    _arrow(d, (s2_x + s2_w) * cm, 14.5 * cm, (s3_x + 0.3) * cm - 2, 14.5 * cm,
           width=1.5)
    d.add(String(12.2 * cm, 14.62 * cm, "writes", fontName="Helvetica",
                 fontSize=6.5, fillColor=GREY, textAnchor="middle"))

    return d


# ─────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────
def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN, 1.3 * cm, "FolderGuardian — Capstone Project Report")
    canvas.drawRightString(PAGE_W - MARGIN, 1.3 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#CCCCCC"))
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 1.55 * cm, PAGE_W - MARGIN, 1.55 * cm)
    canvas.restoreState()


# ─────────────────────────────────────────────────────────────
# Story
# ─────────────────────────────────────────────────────────────
def build_story():
    S = styles
    story = []

    # ── Intro / what the project is ──
    story.append(Paragraph("FolderGuardian", S["TitleMain"]))
    story.append(Paragraph(
        "A real-time file monitoring and AI document automation system built with "
        "Python, LangChain, LangGraph, and RAG.", S["Subtitle"]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("1. What the Project Is", S["H1Blue"]))
    story.append(Paragraph(
        "FolderGuardian is a desktop application that watches up to four folders for "
        "incoming documents and turns them into finished, structured reports with no "
        "manual writing involved. It combines three ideas in one tool:", S["Body"]))
    for b in [
        "<b>Real-time monitoring</b> — a Watchdog observer detects new files the moment "
        "they appear, resolves copy-vs-move races, and batches files that arrive together.",
        "<b>Human gatekeeping</b> — a desktop popup shows each incoming file's metadata "
        "(type, size, word count) and lets the user <b>Allow</b> or <b>Deny</b> it before "
        "any processing happens. Denied files are returned to their origin or deleted.",
        "<b>Agentic AI processing</b> — allowed files enter a LangGraph state-machine "
        "pipeline that ingests the document, builds a searchable vector knowledge base "
        "(RAG), and generates a professional DOCX report via a Groq-hosted LLM "
        "(llama-3.1-8b-instant by default).",
    ]:
        story.append(Paragraph(b, S["BulletItem"], bulletText="•"))

    story.append(Paragraph(
        "The user chooses a <b>2-step</b> (Ingest → Generate) or <b>4-step</b> "
        "(Ingest → Analyze → Generate → Review) workflow per file. All pipeline work "
        "runs on a background thread while a live Tkinter popup streams progress, and "
        "every artifact — the original file, JSON summaries, the vector index, and the "
        "final DOCX — is filed into organized per-document folders.", S["Body"]))

    # ── Architecture ──
    story.append(Paragraph("2. Architecture", S["H1Blue"]))
    story.append(Paragraph(
        "FolderGuardian follows a three-stage design: <b>monitoring &amp; gatekeeping</b> "
        "(main.py), an <b>agentic LangGraph pipeline</b> (v3/), and a local "
        "<b>artifact store</b> (knowledge/, per-document step folders).", S["Body"]))

    diagram = build_architecture_drawing()
    img_h = CONTENT_W * diagram.height / diagram.width
    story.append(Image(diagram, width=CONTENT_W, height=img_h))
    story.append(Paragraph("Figure 1 — FolderGuardian end-to-end architecture",
                           S["Caption"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("2.1 Key Components", S["H2Blue"]))
    comp_rows = [
        ["Component", "File(s)", "Responsibility"],
        ["Watchdog observer & debouncer", "main.py",
         "Watches folders, resolves macOS create→move races with a 1 s pending "
         "window, queues files."],
        ["Batch collector & dispatcher", "main.py",
         "Groups files arriving within 2 s into one popup; sequences all Tkinter "
         "popups."],
        ["Guardian UI", "popup.py, step_choice_popup.py, processing_popup.py",
         "Allow/Deny gate, 2-step/4-step chooser, live processing progress popup."],
        ["LangGraph pipeline", "v3/graph.py, v3/pipeline.py",
         "Compiles a 2- or 4-node state graph; runs it on a background thread with a "
         "180 s timeout."],
        ["Ingest node", "v3/nodes/ingest.py",
         "Parses 15+ formats, chunks + embeds into Chroma (docs > 12 000 chars), LLM "
         "JSON summary, archives source."],
        ["Analyze node (4-step)", "v3/nodes/analyze.py",
         "Extracts key entities, risks, and recommendations as JSON."],
        ["Generate node", "v3/nodes/generate.py",
         "Retrieves per-section context from RAG, writes each section, builds the "
         "DOCX."],
        ["Review node (4-step)", "v3/nodes/review.py",
         "LLM QA pass; saves review notes and the final reviewed DOCX."],
        ["RAG store", "v3/rag/store.py, v3/rag/summaries.py",
         "Chroma + HuggingFace all-MiniLM-L6-v2 embeddings, persisted per watched "
         "folder."],
        ["File tools", "file_info.py, v3/tools/",
         "Metadata extraction (rows, words, pages), document readers, DOCX writer."],
    ]
    comp_table = Table(comp_rows,
                       colWidths=[4.3 * cm, 4.6 * cm, CONTENT_W - 8.9 * cm])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C4D0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(comp_table)

    story.append(Paragraph("2.2 Data Flow of One Document", S["H2Blue"]))
    for i, step in enumerate([
        "A file lands in a watched folder; Watchdog fires and the debouncer commits "
        "it to the queue once the create/move race is resolved.",
        "Files arriving within 2 s are batched; one Guardian popup lists them with "
        "metadata. The user allows or denies each.",
        "For an allowed file, the user picks a 2-step or 4-step workflow, and the "
        "processing popup starts streaming live progress.",
        "Ingest: the document is parsed (TXT, MD, CSV, JSON, XML, HTML, PDF, DOCX, "
        "XLSX), chunked (1 000 chars, 150 overlap), embedded, indexed into a "
        "per-folder Chroma store, and summarized into structured JSON by the LLM.",
        "Analyze (optional): the LLM extracts entities, risks, and recommendations.",
        "Generate: for every configured section (Overview, Key Procedures, Important "
        "Details, Action Items by default), the pipeline retrieves the top-4 relevant "
        "chunks and the LLM writes the section grounded in that context.",
        "Review (optional): an LLM QA pass writes review notes and copies the "
        "finished DOCX into the Review folder.",
        "The original file is archived under source/; the finished report and all "
        "intermediates are filed in per-document workflow folders.",
    ], start=1):
        story.append(Paragraph(f"<b>Step {i}.</b> {step}", S["BulletItem"],
                               bulletText="•"))

    story.append(Paragraph(
        "Small documents (≤ 12 000 characters) skip the vector store and are passed "
        "directly to the LLM context window — an optimization that avoids unnecessary "
        "embedding work. The pipeline thread has a 180-second timeout and reports "
        "every error back through the UI popup.", S["Body"]))

    # ── Use cases ──
    story.append(PageBreak())
    story.append(Paragraph("3. Real-World Use Cases", S["H1Blue"]))
    story.append(Paragraph(
        "Because FolderGuardian is format-agnostic and folder-driven, it slots into "
        "any workflow where documents arrive continuously and someone has to read, "
        "summarize, and report on them.", S["Body"]))

    use_cases = [
        ("Accounts Payable — Invoice Processing",
         "Invoices dropped by email or scanner into a shared Accounting/Inbox folder "
         "are summarized (vendor, amounts, due dates), analyzed for risks such as "
         "duplicate charges, and turned into a standardized approval report. The "
         "Allow/Deny gate keeps personal files that were copied to the wrong place "
         "out of the financial pipeline."),
        ("Legal & Compliance — Contract Intake",
         "Incoming NDAs and vendor contracts are ingested into a searchable knowledge "
         "base so the team can ask 'which contracts mention indemnification?' The "
         "4-step workflow adds a risk analysis (unusual liability clauses) and a QA "
         "review note for the paralegal before the summary report is circulated."),
        ("IT Operations — Report Triage",
         "Nightly exports (CSV logs, JSON metrics, XLSX reports) from monitoring "
         "tools are dropped into a watched folder. FolderGuardian summarizes each "
         "one, flags anomalies in the Analyze step, and produces a morning briefing "
         "DOCX for the ops stand-up — no human has to open 20 spreadsheets."),
        ("Research & Academia — Literature Intake",
         "PDFs of papers collected by a research group are automatically summarized "
         "into overview/key-topics JSON artifacts and indexed for RAG, letting "
         "students generate literature-review drafts grounded in the actual papers "
         "rather than guesswork."),
        ("HR — Candidate Document Handling",
         "Resumes and portfolio DOCX/PDF files arriving from a job-board drop folder "
         "are reviewed (denied files never touch the pipeline), summarized into a "
         "consistent candidate profile, and generated into a shortlist report for "
         "the hiring manager."),
        ("Field Services — Equipment Manual Digitization",
         "Scanned or downloaded equipment manuals (like the bundled "
         "sample_pump_manual.txt) are ingested once into the knowledge base; the "
         "Generate step then produces maintenance quick-reference cards and "
         "action-item lists that technicians can keep on a tablet."),
        ("Small Business — Knowledge Base Builder",
         "Every SOP, policy, or how-to document a team saves into a shared folder "
         "quietly becomes part of a growing, searchable knowledge base with a "
         "generated summary — turning a messy shared drive into an onboarding "
         "asset."),
    ]
    for title, body in use_cases:
        story.append(KeepTogether([
            Paragraph(title, S["H2Blue"]),
            Paragraph(body, S["Body"]),
        ]))

    # ── Tech stack ──
    story.append(Paragraph("4. Technology Stack", S["H1Blue"]))
    stack_rows = [
        ["Layer", "Technology"],
        ["Monitoring", "Watchdog (cross-platform filesystem observer)"],
        ["UI", "Tkinter desktop popups (allow/deny, workflow choice, live progress)"],
        ["Agent orchestration", "LangGraph StateGraph with conditional edges"],
        ["LLM", "Groq API — llama-3.1-8b-instant (configurable via GROQ_MODEL)"],
        ["Framework", "LangChain + langchain-groq + community loaders"],
        ["RAG", "Chroma vector store, HuggingFace all-MiniLM-L6-v2 embeddings"],
        ["Documents", "pypdf, python-docx, openpyxl (PDF / DOCX / XLSX)"],
        ["Runtime", "Python 3.13+; API key supplied via GROQ_API_KEY environment "
                    "variable"],
    ]
    stack_table = Table(stack_rows, colWidths=[4.5 * cm, CONTENT_W - 4.5 * cm])
    stack_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B7C4D0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(stack_table)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Repository: github.com/Karthi-64/Capstone_Project — report generated "
        "September 2026 from the V3 codebase.", S["Caption"]))
    return story


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(
        OUT,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=1.8 * cm,
        bottomMargin=2.0 * cm,
        title="FolderGuardian — Capstone Project Report",
        author="FolderGuardian",
    )
    doc.build(build_story(), onFirstPage=_footer, onLaterPages=_footer)
    print(f"PDF written → {OUT}")


if __name__ == "__main__":
    main()
