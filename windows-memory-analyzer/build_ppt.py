"""
build_ppt.py
Generates the 12-slide PowerPoint for:
  Windows Memory Behavior and Page-Fault Analyzer
Run:  python build_ppt.py
Out:  Windows_Memory_Behavior_Page_Fault_Analyzer.pptx
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

# ─── Palette ──────────────────────────────────────────────────────────────────
NAVY   = RGBColor(0x0D, 0x1B, 0x3E)
BLUE   = RGBColor(0x1F, 0x77, 0xB4)
CYAN   = RGBColor(0x17, 0xBE, 0xCF)
ORANGE = RGBColor(0xFF, 0x7F, 0x0E)
GREEN  = RGBColor(0x2C, 0xA0, 0x2C)
PURPLE = RGBColor(0x94, 0x67, 0xBD)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
LGRAY  = RGBColor(0xD0, 0xE4, 0xF4)
YELLOW = RGBColor(0xFF, 0xD7, 0x00)
RED    = RGBColor(0xCC, 0x22, 0x22)
DK_BLUE = RGBColor(0x10, 0x25, 0x55)
DK_RED  = RGBColor(0x1A, 0x00, 0x00)

MSO_RECT       = 1   # rectangle
MSO_ROUND_RECT = 5   # rounded rectangle

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]   # blank layout

# ─── Helpers ──────────────────────────────────────────────────────────────────

def set_bg(slide, color=NAVY):
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_shape(slide, kind, l, t, w, h, fill_rgb, line_rgb=None, line_w=Pt(1)):
    sh = slide.shapes.add_shape(kind,
                                Inches(l), Inches(t), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill_rgb
    if line_rgb:
        sh.line.color.rgb = line_rgb
        sh.line.width     = line_w
    else:
        sh.line.fill.background()
    return sh


def rect(slide, l, t, w, h, fill=NAVY, line=None, lw=Pt(1)):
    return _add_shape(slide, MSO_RECT, l, t, w, h, fill, line, lw)


def rrect(slide, l, t, w, h, fill=BLUE, line=None, lw=Pt(1.5)):
    """Rounded rectangle — uses MSO shape 5."""
    sh = _add_shape(slide, MSO_ROUND_RECT, l, t, w, h, fill, line, lw)
    # Adjust corner radius (adj value 0–50000 maps to 0–50% of min(w,h))
    sp_elem = sh._element
    prstGeom = sp_elem.find('.//' + qn('a:prstGeom'))
    if prstGeom is not None:
        avLst = prstGeom.find(qn('a:avLst'))
        if avLst is not None:
            for gd in avLst.findall(qn('a:gd')):
                if gd.get('name') == 'adj':
                    gd.set('fmla', 'val 8000')   # ~16% corner radius
    return sh


def txb(slide, l, t, w, h, text, size=Pt(12), bold=False,
        color=WHITE, align=PP_ALIGN.LEFT, wrap=True):
    """Add a text box."""
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tb.word_wrap = wrap
    tf = tb.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text  = text
    run.font.size  = size
    run.font.bold  = bold
    run.font.color.rgb = color
    return tb


def label(shape, text, size=Pt(11), bold=False, color=WHITE, align=PP_ALIGN.CENTER):
    """Write centred text into a shape's text frame."""
    tf = shape.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = size
    run.font.bold = bold
    run.font.color.rgb = color


def title_bar(slide, heading, sub=None):
    rect(slide, 0, 0, 13.33, 1.0, fill=BLUE)
    txb(slide, 0.3, 0.1, 12.5, 0.78, heading,
        size=Pt(27), bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    if sub:
        rect(slide, 0, 1.0, 13.33, 0.28, fill=CYAN)
        txb(slide, 0.3, 1.02, 12.5, 0.24, sub,
            size=Pt(11.5), color=NAVY, align=PP_ALIGN.LEFT)


def divider(slide, y, color=CYAN, h=0.025):
    rect(slide, 0.3, y, 12.73, h, fill=color)


def sec_hdr(slide, l, t, w, text, fill=BLUE):
    sh = rrect(slide, l, t, w, 0.36, fill=fill)
    label(sh, text, size=Pt(12), bold=True, color=WHITE)
    return t + 0.40


def bullets(slide, l, t, w, items, size=Pt(12), gap=0.30, color=WHITE):
    y = t
    for item in items:
        indent = 0.0
        if item.startswith("  "):
            indent = 0.22
            item = item.lstrip()
            pfx = "  –  "
        elif item == "":
            y += gap * 0.4
            continue
        else:
            pfx = "▸  "
        txb(slide, l + indent, y, w - indent, gap, pfx + item,
            size=size, color=color)
        y += gap
    return y


def arrow_dn(slide, x, y, length=0.35, color=CYAN):
    rect(slide, x - 0.018, y, 0.036, length - 0.10, fill=color)
    # arrowhead
    rect(slide, x - 0.065, y + length - 0.10, 0.13, 0.025, fill=color)
    rect(slide, x - 0.048, y + length - 0.075, 0.096, 0.025, fill=color)
    rect(slide, x - 0.032, y + length - 0.05, 0.064, 0.025, fill=color)
    rect(slide, x - 0.018, y + length - 0.025, 0.036, 0.025, fill=color)


def arrow_rt(slide, x, y, length=0.35, color=CYAN):
    rect(slide, x, y - 0.018, length - 0.08, 0.036, fill=color)
    rect(slide, x + length - 0.08, y - 0.065, 0.025, 0.13, fill=color)
    rect(slide, x + length - 0.055, y - 0.048, 0.025, 0.096, fill=color)
    rect(slide, x + length - 0.03, y - 0.032, 0.025, 0.064, fill=color)
    rect(slide, x + length - 0.005, y - 0.018, 0.025, 0.036, fill=color)


def note(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 – Title
# ══════════════════════════════════════════════════════════════════════════════
s1 = prs.slides.add_slide(blank)
set_bg(s1, NAVY)
rect(s1, 0, 0, 13.33, 0.07, fill=CYAN)
rect(s1, 0, 7.43, 13.33, 0.07, fill=CYAN)

# centre panel
panel = rrect(s1, 0.9, 0.65, 11.53, 4.8, fill=DK_BLUE, line=BLUE, lw=Pt(2.5))

txb(s1, 1.1, 0.9, 11.13, 1.55,
    "Windows Memory Behavior\nand Page-Fault Analyzer",
    size=Pt(38), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

rect(s1, 3.4, 2.55, 6.53, 0.06, fill=CYAN)

txb(s1, 1.1, 2.7, 11.13, 0.42,
    "Subject: Windows and Linux Internals",
    size=Pt(17), color=LGRAY, align=PP_ALIGN.CENTER)

txb(s1, 1.1, 3.18, 11.13, 0.38,
    "SRM Institute of Science and Technology",
    size=Pt(13), color=LGRAY, align=PP_ALIGN.CENTER)

auth = rrect(s1, 1.9, 3.72, 9.53, 1.45, fill=BLUE, line=CYAN, lw=Pt(1.5))
txb(s1, 2.1, 3.80, 9.13, 0.32, "Presented By",
    size=Pt(12), bold=True, color=CYAN, align=PP_ALIGN.CENTER)
txb(s1, 2.1, 4.16, 9.13, 0.9,
    "Akash S  –  RA2312703010006\n"
    "Homesh Krishnan U  –  RA2312703010022\n"
    "Mohammed Yasir  –  RA2312703010032",
    size=Pt(12.5), color=WHITE, align=PP_ALIGN.CENTER)

rect(s1, 0, 7.22, 13.33, 0.21, fill=BLUE)
txb(s1, 0, 7.25, 13.33, 0.2,
    "Department of Computing Technologies  |  Academic Year 2025–2026",
    size=Pt(9), color=LGRAY, align=PP_ALIGN.CENTER)

note(s1, "Introduce the project title, subject, and all three team members. "
         "State that this is a Windows-only implementation despite the course covering both OS.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 – Introduction
# ══════════════════════════════════════════════════════════════════════════════
s2 = prs.slides.add_slide(blank)
set_bg(s2, NAVY)
rect(s2, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s2, "Introduction",
          "Memory Management in Modern Operating Systems")

# col 1 — Physical vs Virtual
txb(s2, 0.35, 1.42, 4.15, 0.3, "Physical vs Virtual Memory",
    size=Pt(13), bold=True, color=CYAN)
divider(s2, 1.73, color=BLUE, h=0.022)
bullets(s2, 0.35, 1.8, 4.15, [
    "Every process gets its own isolated virtual address space",
    "Physical RAM is shared across ALL processes by the OS",
    "Virtual pages are mapped to physical frames on demand",
    "  Not all virtual pages need to be RAM-resident at once",
    "Windows demand-paging: pages brought in only on first access",
    "  This first-access event is the fundamental page fault",
], size=Pt(11), gap=0.27, color=LGRAY)

# col 2 — Page fault mechanism
txb(s2, 4.75, 1.42, 4.15, 0.3, "The Page Fault Mechanism",
    size=Pt(13), bold=True, color=CYAN)
divider(s2, 1.73, color=BLUE, h=0.022)
bullets(s2, 4.75, 1.8, 4.15, [
    "CPU accesses address not mapped → hardware exception raised",
    "Windows Memory Manager intercepts and resolves the fault",
    "Resolution may be disk-free (soft) or need disk I/O (hard)",
    "  Soft: zero-fill, standby list, copy-on-write — no disk",
    "  Hard: page read from pagefile — actual disk I/O occurs",
    "Windows PageFaultCount counts ALL types together",
], size=Pt(11), gap=0.27, color=LGRAY)

# col 3 — Why it matters
motiv = rrect(s2, 9.1, 1.42, 3.98, 5.45, fill=DK_BLUE, line=CYAN, lw=Pt(1.5))
txb(s2, 9.22, 1.52, 3.74, 0.32, "Why This Matters",
    size=Pt(13), bold=True, color=ORANGE, align=PP_ALIGN.CENTER)
bullets(s2, 9.22, 1.92, 3.74, [
    "Memory is the #1 performance bottleneck in most workloads",
    "Different access patterns cause measurably different fault activity",
    "Task Manager shows totals — not behavior over time",
    "Controlled experiments reveal OS memory decisions",
    "Critical for optimizing real-world software",
    "Pagefile activity is invisible to most developers",
], size=Pt(11), gap=0.4, color=LGRAY)

note(s2, "Emphasise that PageFaultCount on Windows is cumulative and does NOT separate "
         "soft faults (no disk) from hard faults (disk I/O). This distinction is tested by faculty.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 – Problem Statement & Objectives
# ══════════════════════════════════════════════════════════════════════════════
s3 = prs.slides.add_slide(blank)
set_bg(s3, NAVY)
rect(s3, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s3, "Problem Statement & Objectives",
          "Research question: How do memory allocation and access patterns affect page-fault activity on Windows?")

# problem box
pb = rrect(s3, 0.3, 1.42, 12.73, 1.18,
           fill=RGBColor(0x3A, 0x0A, 0x0A), line=ORANGE, lw=Pt(2))
txb(s3, 0.5, 1.50, 12.3, 0.3, "⚠  The Problem",
    size=Pt(13), bold=True, color=ORANGE)
txb(s3, 0.5, 1.82, 12.3, 0.72,
    "Standard monitoring tools (Task Manager, Resource Monitor) report instantaneous totals but do not "
    "reveal how different memory allocation strategies influence working-set growth, page-fault accumulation, "
    "or physical RAM pressure over time.  No built-in tool runs controlled workloads to isolate these effects.",
    size=Pt(11.5), color=LGRAY)

# 4 objective tiles
obj = [
    ("🔬 Experiment",         BLUE,
     "Run 5 controlled workloads:\nAllocation · Sequential · Repeated\nRandom · Release"),
    ("📊 Measure",            RGBColor(0x0A, 0x5A, 0x4A),
     "Per-interval capture of:\nWorking Set · Private Bytes\nPageFaultCount · Available RAM"),
    ("📉 Analyse",            RGBColor(0x4A, 0x10, 0x6A),
     "Compute fault Δ and fault rate\nPlotly charts: trend, bar, overlay\nSide-by-side comparison"),
    ("💾 Persist & Export",   RGBColor(0x3A, 0x3A, 0x00),
     "SQLite (WAL mode) for all data\nCSV export: summaries + samples\nDelete history with confirmation"),
]
tw = 3.05
for i, (title, color, desc) in enumerate(obj):
    lx = 0.3 + i * (tw + 0.09)
    sh = rrect(s3, lx, 2.75, tw, 3.1, fill=color, line=CYAN, lw=Pt(1.2))
    txb(s3, lx+0.12, 2.84, tw-0.22, 0.35, title, size=Pt(13), bold=True, color=WHITE)
    rect(s3, lx+0.12, 3.2, tw-0.24, 0.025, fill=CYAN)
    txb(s3, lx+0.12, 3.28, tw-0.22, 2.5, desc, size=Pt(11.5), color=LGRAY)

note(s3, "The four objectives map directly to the four layers of the app: "
         "experiment engine, metric collectors, analysis module, and storage/export.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 – OS Concepts
# ══════════════════════════════════════════════════════════════════════════════
s4 = prs.slides.add_slide(blank)
set_bg(s4, NAVY)
rect(s4, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s4, "Operating System Memory Concepts",
          "Key Windows internals underpinning the application's measurements")

defs = [
    ("Working Set",      BLUE,
     "Physical pages currently mapped into the process. Reported by GetProcessMemoryInfo "
     "as WorkingSetSize. Evicted pages leave the working set; re-accessing them causes a fault."),
    ("Private Bytes",    GREEN,
     "Virtual memory committed exclusively to this process (PagefileUsage). Backed by pagefile "
     "or physical RAM. A process can have large private bytes but a small working set."),
    ("Virtual Size",     PURPLE,
     "Total user-mode virtual address space reserved/committed. Can exceed RAM; only accessed "
     "pages consume physical memory via demand-paging."),
    ("Page Fault Count", ORANGE,
     "Cumulative DWORD counter (PageFaultCount). Incremented on every page access not currently "
     "in the working set. Counts soft faults AND hard faults — cannot distinguish them."),
]

y = 1.42
for name, color, desc in defs:
    sh = rrect(s4, 0.3, y, 2.45, 0.36, fill=color)
    label(sh, name, size=Pt(12), bold=True, color=WHITE)
    txb(s4, 2.85, y, 6.25, 0.82, desc, size=Pt(11), color=LGRAY)
    y += 1.02

# Right panel — fault type table
fp = rrect(s4, 9.45, 1.42, 3.65, 4.82, fill=DK_BLUE, line=BLUE, lw=Pt(1.5))
txb(s4, 9.55, 1.52, 3.45, 0.32, "Page Fault Resolution Types",
    size=Pt(12), bold=True, color=CYAN, align=PP_ALIGN.CENTER)

hdr = rect(s4, 9.52, 1.90, 3.52, 0.3, fill=BLUE)
txb(s4, 9.56, 1.93, 1.4, 0.24, "Type", size=Pt(10), bold=True, color=WHITE)
txb(s4, 11.0, 1.93, 0.9, 0.24, "Disk I/O?", size=Pt(10), bold=True, color=WHITE)

fault_rows = [
    ("Zero-demand",    "❌  No", GREEN,
     "New private page; OS zero-fills without reading disk"),
    ("Soft fault",     "❌  No", CYAN,
     "Page on standby list; re-mapped into working set"),
    ("Copy-on-write",  "❌  No", PURPLE,
     "Shared page copied to private — no disk read"),
    ("Hard fault",     "✅  Yes", ORANGE,
     "Page read from pagefile or mapped file — disk I/O"),
]

fy = 2.22
for i, (name, disk, color, desc) in enumerate(fault_rows):
    bg = RGBColor(0x12, 0x28, 0x58) if i % 2 == 0 else RGBColor(0x0D, 0x1F, 0x48)
    rect(s4, 9.52, fy, 3.52, 0.78, fill=bg)
    txb(s4, 9.57, fy+0.04, 1.3, 0.24, name, size=Pt(10), bold=True, color=color)
    dc = GREEN if "No" in disk else ORANGE
    txb(s4, 11.0, fy+0.04, 0.9, 0.24, disk, size=Pt(10), bold=True, color=dc)
    txb(s4, 9.57, fy+0.30, 3.35, 0.44, desc, size=Pt(9.5), color=LGRAY)
    fy += 0.80

txb(s4, 9.52, fy+0.06, 3.52, 0.52,
    "⚠ PageFaultCount counts ALL types — cannot separate hard from soft faults",
    size=Pt(9.5), bold=True, color=ORANGE)

note(s4, "Most important conceptual slide. Faculty will ask: Does every page fault cause disk I/O? "
         "Answer: NO. Only hard faults do. Windows PageFaultCount includes all types combined.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 – Proposed System & Features
# ══════════════════════════════════════════════════════════════════════════════
s5 = prs.slides.add_slide(blank)
set_bg(s5, NAVY)
rect(s5, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s5, "Proposed System & Features",
          "A controlled-experiment platform — goes beyond passive monitoring")

txb(s5, 0.3, 1.40, 12.73, 0.34,
    "The application deliberately induces measurable memory-management activity and records the "
    "Windows OS response at every configurable sampling interval (0.5 s – 60 s).",
    size=Pt(11.5), color=LGRAY)

tiles = [
    ("🖥️ System Dashboard",    BLUE,
     "RAM · CPU · pagefile gauges\nVirtual memory · kernel counters\nRolling trend charts (120 pts)\nGlobalMemoryStatusEx + GetPerformanceInfo"),
    ("🔍 Process Inspector",   RGBColor(0x0A, 0x55, 0x5A),
     "Search & select any running PID\nWorking set · private bytes\nPageFaultCount · pool usage\nGetProcessMemoryInfo (PMCEX)"),
    ("🧪 Memory Experiments",  RGBColor(0x4A, 0x10, 0x6A),
     "5 workloads (A–E) in subprocess\nUI stays responsive during run\nStart · Stop · Reset · Save\nAlloc 4–256 MiB · 3–300 s"),
    ("📉 PF Analysis",         RGBColor(0x5A, 0x30, 0x00),
     "Initial / final / delta / rate\nDual-axis: working set + faults\nPer-interval Δ bar chart\nCounter limitations panel"),
    ("⚖️ Comparison",          RGBColor(0x1A, 0x40, 0x20),
     "Multi-select 2+ experiments\nSide-by-side table + bar charts\nWorking-set overlay plots\nPage-fault Δ overlay"),
    ("💾 History & Export",    RGBColor(0x3A, 0x3A, 0x00),
     "SQLite: metadata + samples\nExport summaries CSV\nExport raw samples CSV\nDelete with confirmation"),
]

tw = 4.08
for i, (title, color, desc) in enumerate(tiles):
    col = i % 3
    row = i // 3
    lx = 0.3 + col * (tw + 0.13)
    ty = 1.90 + row * 2.52
    sh = rrect(s5, lx, ty, tw, 2.38, fill=color, line=CYAN, lw=Pt(1))
    txb(s5, lx+0.12, ty+0.1, tw-0.22, 0.35, title, size=Pt(13), bold=True, color=WHITE)
    rect(s5, lx+0.12, ty+0.47, tw-0.24, 0.022, fill=CYAN)
    txb(s5, lx+0.12, ty+0.54, tw-0.22, 1.78, desc, size=Pt(11), color=LGRAY)

note(s5, "Key point: experiments run in a SEPARATE OS PROCESS (subprocess). "
         "Max allocation is min(256 MiB, 10% total RAM). No admin rights needed.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 6 – Architecture Diagram
# ══════════════════════════════════════════════════════════════════════════════
s6 = prs.slides.add_slide(blank)
set_bg(s6, NAVY)
rect(s6, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s6, "System Architecture",
          "Layer diagram derived from actual source code — real modules, real data flows")

# ── Layer labels helper
def layer_box(slide, l, t, w, h, label_text, label_color, border_color):
    rrect(slide, l, t, w, h, fill=RGBColor(0x08, 0x18, 0x3A), line=border_color, lw=Pt(1.5))
    txb(slide, l+0.07, t+0.04, 1.7, 0.24, label_text,
        size=Pt(8.5), bold=True, color=label_color)

# LAYER 1 — Presentation (Streamlit pages)
layer_box(s6, 0.2, 1.35, 12.93, 1.05, "① PRESENTATION LAYER", BLUE, BLUE)

page_boxes = [
    ("app.py\nEntry Point", BLUE),
    ("Dashboard\ndashboard.py", RGBColor(0x15, 0x55, 0x95)),
    ("Process\nInspector", RGBColor(0x15, 0x55, 0x95)),
    ("Experiments\nPage", RGBColor(0x15, 0x55, 0x95)),
    ("PF Analysis\nPage", RGBColor(0x15, 0x55, 0x95)),
    ("Comparison\nPage", RGBColor(0x15, 0x55, 0x95)),
    ("History\nPage", RGBColor(0x15, 0x55, 0x95)),
]
pw = 1.60
px0 = 1.55
for j, (lbl, col) in enumerate(page_boxes):
    sh = rrect(s6, px0 + j*(pw+0.06), 1.44, pw, 0.84, fill=col, line=CYAN, lw=Pt(1))
    label(sh, lbl, size=Pt(9), bold=(j==0), color=WHITE)

# LAYER 2 — Control
layer_box(s6, 0.2, 2.53, 12.93, 0.82, "② APPLICATION CONTROL", PURPLE, PURPLE)

ctrl = [
    ("ExperimentManager\nexperiment_manager.py", PURPLE),
    ("WorkloadRunner\nworkload_runner.py", RGBColor(0x60, 0x30, 0x90)),
    ("validate_config()\nInput guard", RGBColor(0x45, 0x18, 0x75)),
    ("ExperimentDB\ndatabase.py", RGBColor(0x35, 0x10, 0x65)),
]
cw = 2.85
cx0 = 1.55
for j, (lbl, col) in enumerate(ctrl):
    sh = rrect(s6, cx0 + j*(cw+0.13), 2.63, cw, 0.62, fill=col, line=PURPLE, lw=Pt(1))
    label(sh, lbl, size=Pt(9), color=WHITE)

# arrows 1→2
for ax in [3.5, 6.7, 9.0]:
    arrow_dn(s6, ax, 2.40, length=0.13, color=CYAN)

# LAYER 3a — Collectors
layer_box(s6, 0.2, 3.47, 6.0, 1.28, "③ COLLECTORS (Windows APIs)", GREEN, GREEN)

coll_items = [
    ("system_memory.py\nGlobalMemoryStatusEx\nGetPerformanceInfo", RGBColor(0x10, 0x50, 0x20)),
    ("process_memory.py\nGetProcessMemoryInfo\nPMCEX structure", RGBColor(0x10, 0x50, 0x20)),
    ("page_faults.py\nPageFaultMonitor\ninterpret_delta()", RGBColor(0x10, 0x50, 0x20)),
]
for j, (lbl, col) in enumerate(coll_items):
    sh = rrect(s6, 1.45 + j*1.85, 3.58, 1.70, 1.05, fill=col, line=GREEN, lw=Pt(1))
    label(sh, lbl, size=Pt(8.5), color=WHITE)

# LAYER 3b — Worker process
layer_box(s6, 6.42, 3.47, 6.71, 1.28, "③ WORKER PROCESS (subprocess)", ORANGE, ORANGE)

wl_items = [
    "allocation()\nbytearray alloc",
    "sequential()\npage-by-page",
    "repeated()\nmulti-pass XOR",
    "random()\nshuffled pages",
    "release()\nalloc→touch→del",
]
wlw = 1.17
for j, lbl in enumerate(wl_items):
    sh = rrect(s6, 6.55 + j*(wlw+0.06), 3.58, wlw, 1.05,
               fill=RGBColor(0x55, 0x28, 0x00), line=ORANGE, lw=Pt(1))
    label(sh, lbl, size=Pt(8), color=WHITE)

# Queue label (between worker and control)
txb(s6, 10.55, 3.1, 1.6, 0.32, "← Queue\n(samples)", size=Pt(8.5), color=ORANGE)
arrow_dn(s6, 9.55, 3.07, length=0.40, color=ORANGE)

# arrows 2→3
arrow_dn(s6, 3.0, 3.37, length=0.10, color=GREEN)
arrow_dn(s6, 8.5, 3.37, length=0.10, color=ORANGE)

# LAYER 4a — Analysis
layer_box(s6, 0.2, 4.86, 6.0, 0.92, "④ ANALYSIS", CYAN, CYAN)

anal_items = [
    ("metrics.py\ncounter_delta · rate\nformat helpers", RGBColor(0x10, 0x35, 0x70)),
    ("comparison.py\ncompare_experiments\ndiff_summary", RGBColor(0x10, 0x35, 0x70)),
    ("Plotly Charts\nWorking Set · Avail\nFault Δ bar · Overlay", RGBColor(0x10, 0x35, 0x70)),
]
for j, (lbl, col) in enumerate(anal_items):
    sh = rrect(s6, 1.45 + j*1.85, 4.96, 1.70, 0.72, fill=col, line=CYAN, lw=Pt(1))
    label(sh, lbl, size=Pt(8.5), color=WHITE)

# LAYER 4b — Storage
layer_box(s6, 6.42, 4.86, 6.71, 0.92, "④ STORAGE & EXPORT", YELLOW, YELLOW)

stor_items = [
    ("database.py\nSQLite WAL\nexperiments table + samples", RGBColor(0x3A, 0x38, 0x05)),
    ("export.py\nsamples_to_csv\nsummaries_to_csv", RGBColor(0x3A, 0x38, 0x05)),
    ("memory_analyzer.db\nCSV downloads\n(Streamlit button)", RGBColor(0x3A, 0x38, 0x05)),
]
for j, (lbl, col) in enumerate(stor_items):
    sh = rrect(s6, 6.55 + j*1.97, 4.96, 1.88, 0.72, fill=col, line=YELLOW, lw=Pt(1))
    label(sh, lbl, size=Pt(8.5), color=WHITE)

# arrows 3→4
arrow_dn(s6, 3.0, 4.76, length=0.10, color=CYAN)
arrow_dn(s6, 9.55, 4.76, length=0.10, color=YELLOW)

# LAYER 5 — Windows OS boundary
rrect(s6, 0.2, 5.88, 12.93, 0.9,
      fill=DK_RED, line=RED, lw=Pt(2))
txb(s6, 0.3, 5.90, 2.5, 0.26, "WINDOWS 10/11 KERNEL",
    size=Pt(9), bold=True, color=RGBColor(0xFF, 0x55, 0x55))

win_items = [
    "kernel32.dll\nGlobalMemoryStatusEx\nGetSystemInfo",
    "psapi.dll\nGetPerformanceInfo\nGetProcessMemoryInfo",
    "Memory Manager\nDemand-paging\nWorking-set trimming",
    "Pagefile\nStandby list\nZero-page list",
    "ctypes bridge\nPython→WinAPI\n(no admin needed)",
]
waw = 2.22
for j, lbl in enumerate(win_items):
    sh = rrect(s6, 2.4 + j*(waw+0.1), 5.97, waw, 0.70,
               fill=RGBColor(0x33, 0x00, 0x00), line=RED, lw=Pt(1))
    label(sh, lbl, size=Pt(8), color=RGBColor(0xFF, 0xCC, 0xCC))

arrow_dn(s6, 3.5, 5.80, length=0.08, color=RED)

note(s6, "Walk top-to-bottom. Presentation → Control (ExperimentManager) → "
         "Collectors (Windows API via ctypes) + Worker subprocess (multiprocessing.Queue) → "
         "Analysis + Storage → Windows kernel at bottom. No admin needed.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 7 – Application Workflow
# ══════════════════════════════════════════════════════════════════════════════
s7 = prs.slides.add_slide(blank)
set_bg(s7, NAVY)
rect(s7, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s7, "Application Workflow",
          "Step-by-step flow: launch → data collection → experiment → analysis → export")

steps = [
    ("1", "Launch",        BLUE,
     "streamlit run app.py\nlocalhost:8501\nExperimentManager\ninitialised"),
    ("2", "Dashboard",     CYAN,
     "collect_system_memory()\nGlobalMemoryStatusEx\nGetPerformanceInfo\nGauges + charts"),
    ("3", "Inspect\nPID",  GREEN,
     "User selects PID\ncollect_process_memory()\nGetProcessMemoryInfo\nWorking set shown"),
    ("4", "Config",        ORANGE,
     "Pick workload A–E\nSet alloc · duration\ninterval · seed\nvalidate_config()"),
    ("5", "Run\nWorkload", PURPLE,
     "WorkloadRunner.start()\nSpawns subprocess\nQueue drainer thread\nsamples→session_state"),
    ("6", "Monitor",       RGBColor(0x40, 0x00, 0x88),
     "_snapshot() per tick\npage_fault_count\nworking_set_mb\nPlotly rerun"),
    ("7", "Finalise",      RGBColor(0x00, 0x55, 0x55),
     "finalise() called\nSummary→SQLite\nFault Δ computed\nInterpretation shown"),
    ("8", "Export",        YELLOW,
     "Comparison page\nOverlay charts\nCSV download\nst.download_button()"),
]

bw = 1.40
g  = 0.09
sx = 0.25
sy = 1.44

for j, (num, title, color, detail) in enumerate(steps):
    bx = sx + j * (bw + g)
    # number badge
    nb = rrect(s7, bx + bw/2 - 0.20, sy-0.28, 0.40, 0.34,
               fill=color, line=WHITE, lw=Pt(1))
    label(nb, num, size=Pt(14), bold=True, color=WHITE)
    # step box
    sb = rrect(s7, bx, sy+0.08, bw, 1.0, fill=color, line=WHITE, lw=Pt(1))
    label(sb, title, size=Pt(12), bold=True, color=WHITE)
    # detail below
    txb(s7, bx, sy+1.14, bw, 2.1, detail, size=Pt(9.5), color=LGRAY)
    # arrow to next
    if j < len(steps) - 1:
        arrow_rt(s7, bx + bw + 0.01, sy + 0.62, length=g + 0.01, color=CYAN)

# subprocess detail
sp = rrect(s7, 0.25, 4.88, 12.83, 1.05,
           fill=RGBColor(0x10, 0x10, 0x40), line=PURPLE, lw=Pt(1.5))
txb(s7, 0.42, 4.96, 3.5, 0.28, "🔧 Subprocess Architecture (Steps 5–6):",
    size=Pt(11), bold=True, color=PURPLE)
txb(s7, 0.42, 5.26, 12.5, 0.6,
    "WorkloadRunner spawns multiprocessing.Process(daemon=True)  →  Workload function runs independently  "
    "→  Samples emitted via multiprocessing.Queue  →  Background reader thread drains queue into session_state  "
    "→  stop() calls process.terminate() + join(timeout=5)  →  Cancelled experiments marked in SQLite",
    size=Pt(10.5), color=LGRAY)

note(s7, "Key: workload runs in a SEPARATE OS PROCESS, not a thread. "
         "multiprocessing.Queue is the IPC mechanism. Reader thread in main process drains it continuously.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 8 – Modules & Technologies
# ══════════════════════════════════════════════════════════════════════════════
s8 = prs.slides.add_slide(blank)
set_bg(s8, NAVY)
rect(s8, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s8, "Modules & Technologies",
          "Complete module inventory with responsibilities and technology mapping")

# table header
rect(s8, 0.22, 1.40, 8.9, 0.36, fill=BLUE)
for i, (hdr, lx) in enumerate([("Module / File", 0.32), ("Responsibility", 3.10), ("Key API / Library", 6.35)]):
    txb(s8, lx, 1.44, 2.65, 0.28, hdr, size=Pt(10.5), bold=True, color=WHITE)

rows = [
    ("collectors/system_memory.py",   "Collects RAM, pagefile, virtual memory, CPU, process/thread counts",   "ctypes · GlobalMemoryStatusEx · GetPerformanceInfo"),
    ("collectors/process_memory.py",  "Per-process working set, private bytes, PageFaultCount, pool quota",   "ctypes · GetProcessMemoryInfo · PROCESS_MEMORY_COUNTERS_EX"),
    ("collectors/page_faults.py",     "PageFaultMonitor class, PageFaultSeries, interpret_page_fault_delta()", "Python dataclasses · process_memory"),
    ("experiments/memory_workloads.py","5 workload functions running in worker process, emitting Queue samples","multiprocessing.Queue · bytearray · ctypes"),
    ("experiments/workload_runner.py", "WorkloadRunner: subprocess lifecycle, queue drain thread, cancellation","multiprocessing.Process · threading.Thread · threading.Event"),
    ("experiments/experiment_manager.py","Facade: start/stop/finalise/persist, page-fault interpretation",    "WorkloadRunner · ExperimentDB · interpret_page_fault_delta()"),
    ("analysis/metrics.py",            "Unit conversion, counter_delta, counter_rate, counter catalogue",     "Pure Python (no OS deps) — fully unit-testable"),
    ("analysis/comparison.py",         "compare_experiments(), diff_summary(), compatibility warnings",       "Pure Python"),
    ("storage/database.py",            "SQLite schema, experiment CRUD, sample insert, cascade delete",       "sqlite3 WAL mode · json · contextmanager"),
    ("storage/export.py",              "samples_to_csv(), summaries_to_csv() for download buttons",          "csv.DictWriter · io.StringIO"),
    ("ui/*.py  (7 pages)",             "Streamlit pages: dashboard · inspector · experiments · PF · compare · history · about", "Streamlit · Plotly · pandas"),
    ("config.py",                      "Global constants: alloc limits, workload names, colours, DB path",   "os.path"),
]

rh = 0.315
for i, (mod, resp, tech) in enumerate(rows):
    ty = 1.78 + i * rh
    bg = RGBColor(0x10, 0x22, 0x45) if i % 2 == 0 else RGBColor(0x0D, 0x1B, 0x3E)
    rect(s8, 0.22, ty, 8.9, rh, fill=bg)
    txb(s8, 0.30, ty+0.03, 2.7, rh-0.04, mod, size=Pt(8.8), bold=True, color=CYAN)
    txb(s8, 3.10, ty+0.03, 3.15, rh-0.04, resp, size=Pt(8.8), color=LGRAY)
    txb(s8, 6.35, ty+0.03, 2.65, rh-0.04, tech, size=Pt(8.8), color=ORANGE)

# tech stack panel (right)
rrect(s8, 9.30, 1.40, 3.80, 5.86, fill=DK_BLUE, line=CYAN, lw=Pt(1.5))
txb(s8, 9.40, 1.50, 3.60, 0.30, "Technology Stack", size=Pt(13), bold=True,
    color=CYAN, align=PP_ALIGN.CENTER)

tech_stack = [
    ("Python 3.12",       BLUE,   "Language"),
    ("Streamlit ≥ 1.32",  GREEN,  "Web UI"),
    ("Plotly ≥ 5.19",     ORANGE, "Interactive charts"),
    ("psutil ≥ 5.9",      PURPLE, "Portable metrics"),
    ("ctypes (stdlib)",   CYAN,   "Windows API bridge"),
    ("sqlite3 (stdlib)",  YELLOW, "Persistence"),
    ("csv (stdlib)",      WHITE,  "Data export"),
    ("pytest ≥ 8.0",      RGBColor(0xFF, 0x88, 0x88), "97 tests"),
    ("pandas ≥ 2.0",      RGBColor(0x88, 0xFF, 0x88), "UI DataFrames"),
]

ty = 1.90
for name, color, role in tech_stack:
    rect(s8, 9.40, ty, 3.60, 0.50, fill=RGBColor(0x14, 0x2C, 0x5A))
    txb(s8, 9.50, ty+0.07, 2.1, 0.34, name, size=Pt(11), bold=True, color=color)
    txb(s8, 11.65, ty+0.10, 1.2, 0.28, role, size=Pt(10), color=LGRAY)
    ty += 0.55

note(s8, "No admin privileges needed. ctypes bridges Python to Windows native DLLs. "
         "sqlite3 and csv are Python stdlib — zero extra dependencies for storage and export.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 9 – Memory Experiments & Analysis
# ══════════════════════════════════════════════════════════════════════════════
s9 = prs.slides.add_slide(blank)
set_bg(s9, NAVY)
rect(s9, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s9, "Memory Experiments & Analysis",
          "5 controlled workloads — implementation, mechanisms, and expected observations")

exp_rows = [
    ("A", "Allocation",  BLUE,
     "bytearray(N) — commits virtual memory without deliberately accessing every page",
     "Zero-demand faults from OS initialising allocator metadata; virtual size > working set",
     "Fault Δ small; working set grows slowly; large gap between virtual size and WS"),
    ("B", "Sequential",  GREEN,
     "Writes one byte to each page in address order, stride = page_size (4096 B)",
     "First touch of each page triggers a demand-zero fault; working set rises linearly",
     "Expected Δ ≈ alloc_bytes / page_size (64 MiB → ~16 384 faults); largest Δ of all workloads"),
    ("C", "Repeated",    PURPLE,
     "Touches all pages once (first pass), then XOR-reads the buffer multiple times",
     "Pass 1 generates max faults; subsequent passes: pages already resident → near-zero extra faults",
     "Fault rate drops sharply after pass 1; working set stabilises at full allocation size"),
    ("D", "Random",      ORANGE,
     "Shuffled page index list (configurable seed) — accesses pages in pseudorandom order",
     "Same total pages touched as sequential → similar fault Δ on uncongested RAM machine",
     "On low-RAM systems TLB/cache miss difference observable; seed makes run reproducible"),
    ("E", "Release",     YELLOW,
     "Allocate → touch all pages → hold → del buf → monitor post-release for remaining duration",
     "Working set drops after release; system RAM may stay elevated (standby list effect)",
     "Demonstrates that freeing memory ≠ immediate return to OS physical pool"),
]

rh = 1.10
ey = 1.40
for i, (lid, name, color, method, mech, obs) in enumerate(exp_rows):
    ry = ey + i * rh
    # ID
    sh = rrect(s9, 0.18, ry+0.06, 0.44, 0.84, fill=color)
    label(sh, lid, size=Pt(18), bold=True, color=WHITE)
    # name
    txb(s9, 0.70, ry+0.04, 1.55, 0.28, name, size=Pt(12), bold=True, color=color)
    # method + mechanism
    txb(s9, 0.70, ry+0.33, 4.1, 0.26, "Method:  " + method, size=Pt(9.5), color=LGRAY)
    txb(s9, 0.70, ry+0.58, 4.1, 0.26, "Why:  " + mech, size=Pt(9.5), color=LGRAY)
    # observation panel
    op = rrect(s9, 4.88, ry+0.06, 8.22, 0.84, fill=RGBColor(0x08, 0x1E, 0x42))
    txb(s9, 5.00, ry+0.10, 2.0, 0.24, "Expected observation:", size=Pt(9), bold=True, color=CYAN)
    txb(s9, 5.00, ry+0.34, 8.0, 0.52, obs, size=Pt(10), color=LGRAY)

# footer
rect(s9, 0.18, 7.00, 12.97, 0.32, fill=RGBColor(0x10, 0x2A, 0x58))
txb(s9, 0.30, 7.04, 12.8, 0.24,
    "Each experiment records per interval:  page_fault_count (cumulative) · working_set_mb · "
    "virtual_mem_mb · available_ram_mb · system_memory_pct  — stored in SQLite, visualised in Plotly",
    size=Pt(9.5), color=LGRAY)

note(s9, "Exp B: 64 MiB / 4096 = 16,384 expected fault increments during first pass. "
         "Exp C: second+ passes should show near-zero additional faults. "
         "Exp E: after del buf, working set drops but Available RAM may stay low due to standby list.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 10 – GUI & Live Demonstration
# ══════════════════════════════════════════════════════════════════════════════
s10 = prs.slides.add_slide(blank)
set_bg(s10, NAVY)
rect(s10, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s10, "GUI & Live Demonstration",
          "7 Streamlit pages at http://localhost:8501  —  runs without admin privileges")

pages_list = [
    ("🖥️ Dashboard",        BLUE,
     "RAM/CPU/Pagefile gauges · virtual memory metrics · kernel counters · rolling trend charts"),
    ("🔍 Process Inspector", GREEN,
     "Search by name · bar chart of WS/private bytes · PageFaultCount · counter definition panel"),
    ("🧪 Memory Experiments",PURPLE,
     "Sidebar config (workload, size, duration) · Start/Stop/Reset · live Plotly charts during run"),
    ("📉 PF Analysis",       ORANGE,
     "Fault Δ/rate metrics · dual-axis (WS + cumulative PF) · per-interval Δ bar · limitations panel"),
    ("⚖️ Comparison",        CYAN,
     "Multi-select experiments · side-by-side table · bar charts · WS overlay · PF-Δ overlay"),
    ("📚 History",           YELLOW,
     "Summary table (pandas) · individual detail view · CSV download · delete with confirmation"),
    ("ℹ️ About & Metrics",   LGRAY,
     "Windows concepts · page fault type table · full counter catalogue · tech stack table"),
]

for i, (title, color, desc) in enumerate(pages_list):
    ty = 1.42 + i * 0.73
    sh = rrect(s10, 0.22, ty, 2.18, 0.59, fill=color)
    label(sh, title, size=Pt(10), bold=True,
          color=NAVY if color in (YELLOW, LGRAY, CYAN) else WHITE)
    txb(s10, 2.50, ty+0.12, 4.55, 0.46, desc, size=Pt(10.5), color=LGRAY)

# Demo sequence box
db = rrect(s10, 7.18, 1.42, 5.92, 5.18, fill=DK_BLUE, line=CYAN, lw=Pt(1.5))
txb(s10, 7.30, 1.52, 5.68, 0.30, "Live Demo Sequence  (~6 minutes)",
    size=Pt(13), bold=True, color=CYAN, align=PP_ALIGN.CENTER)

demo = [
    ("Step 1", BLUE,   "Open Dashboard → observe RAM %, pagefile gauge, trend chart"),
    ("Step 2", GREEN,  "Process Inspector → select python.exe → note PageFaultCount value"),
    ("Step 3", PURPLE, "Experiments → B Sequential, 64 MiB, 12 s → click Start"),
    ("Step 4", ORANGE, "Watch live working-set chart rise as pages are faulted in"),
    ("Step 5", CYAN,   "After completion → PF Analysis → review fault Δ, rate, interpretation"),
    ("Step 6", YELLOW, "Experiments → D Random, same settings → Start and complete"),
    ("Step 7", GREEN,  "Comparison → select both → overlay charts + fault Δ bar"),
    ("Step 8", LGRAY,  "History → Export All Summaries CSV → verify download"),
]

sy = 1.93
for step, color, action in demo:
    sh = rrect(s10, 7.30, sy, 1.0, 0.40, fill=color)
    label(sh, step, size=Pt(9), bold=True,
          color=NAVY if color in (YELLOW, LGRAY, CYAN) else WHITE)
    txb(s10, 8.38, sy+0.07, 4.6, 0.32, action, size=Pt(10.5), color=LGRAY)
    sy += 0.58

# launch command
lc = rrect(s10, 0.22, 6.73, 6.82, 0.60, fill=RGBColor(0x05, 0x10, 0x25), line=GREEN, lw=Pt(1.5))
txb(s10, 0.35, 6.83, 6.6, 0.40,
    "cd windows-memory-analyzer    →    streamlit run app.py",
    size=Pt(13), bold=True, color=GREEN, align=PP_ALIGN.CENTER)

note(s10, "Keep workload small for demo: 64 MiB, 12 s. Browser should already be open at localhost:8501. "
          "The app is running live — no screenshots needed; show the actual browser.")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 11 – Testing, Results & Limitations
# ══════════════════════════════════════════════════════════════════════════════
s11 = prs.slides.add_slide(blank)
set_bg(s11, NAVY)
rect(s11, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s11, "Testing, Results & Limitations",
          "Verified on Windows 11 Home Build 26200 · Python 3.12.1 · 15.4 GiB RAM")

# Tests column
sec_hdr(s11, 0.22, 1.40, 4.55, "Automated Tests — 97 / 97 Passed  ✅", fill=GREEN)

test_groups = [
    ("test_metrics.py  (44 tests)",
     ["bytes_to_mb/gb conversions, format helpers",
      "counter_delta with DWORD wrap-around",
      "counter_rate with zero/None guards",
      "fault_deltas_from_samples: empty, single, None"]),
    ("test_workloads.py  (15 tests)",
     ["validate_config — all 5 workload types valid",
      "Boundaries: max alloc, min duration, min interval",
      "Reject: zero/negative alloc, unknown workload, non-numeric"]),
    ("test_storage.py  (22 tests)",
     ["create/get/list/delete experiment",
      "Sample add, count, cascade delete on exp delete",
      "update_summary, update_status, multi-exp isolation",
      "samples_to_csv / summaries_to_csv output"]),
    ("test_comparison.py  (16 tests)",
     ["Requires ≥ 2 experiments to compare",
      "Compatibility warnings for alloc/duration mismatch",
      "Row/chart structure, fault_rate computed from delta"]),
]

ty = 1.84
for grp, cases in test_groups:
    txb(s11, 0.32, ty, 4.38, 0.26, "▸  " + grp, size=Pt(10), bold=True, color=CYAN)
    ty += 0.26
    for c in cases:
        txb(s11, 0.52, ty, 4.18, 0.22, "  –  " + c, size=Pt(9.5), color=LGRAY)
        ty += 0.22
    ty += 0.04

# Verified results column
sec_hdr(s11, 5.0, 1.40, 3.85, "Verified Runtime Results  ✅", fill=BLUE)

obs = [
    "Windows API smoke test (live):",
    "  Total RAM: 15 775 MiB (15.4 GiB)",
    "  Available RAM: ~7 048 MiB at idle",
    "  Page size: 4 096 B (confirmed)",
    "  Process count: ~280 processes",
    "  System cache: ~7 430 MiB",
    "  Commit total: ~13 019 MiB",
    "",
    "Self-process (python.exe) test:",
    "  Working Set: 22.44 MiB",
    "  PageFaultCount: 20 408",
    "  Private Bytes: 14.78 MiB",
    "  Error field: None ✅",
    "",
    "App health check:",
    "  HTTP GET /healthz → 200 OK",
    "  Streamlit localhost:8501 ✅",
]
bullets(s11, 5.0, 1.84, 3.85, obs, size=Pt(10), gap=0.228, color=LGRAY)

# Limitations column
sec_hdr(s11, 9.10, 1.40, 4.0, "Known Limitations  ⚠", fill=ORANGE)

limits = [
    "PageFaultCount does NOT split soft vs hard faults — Windows only via heavier Perf Counters API",
    "Counter is 32-bit DWORD — wraps at 2³² faults; handled in code, unlikely in short runs",
    "Dashboard auto-refresh sleeps in main thread — avoid during live experiments",
    "First subprocess spawn ~1 s overhead on Windows (spawn start method, no fork)",
    "Protected system processes return access-denied — handled gracefully with error field",
    "Polling-based UI refresh — charts update only on each st.rerun() call",
    "Allocation capped at min(256 MiB, 10% RAM) — intentionally conservative",
]

ty_l = 1.84
for lim in limits:
    txb(s11, 9.10, ty_l, 3.98, 0.60, "⚠  " + lim, size=Pt(9.5), color=ORANGE)
    ty_l += 0.68

note(s11, "97/97 tests actually run and passed — not claimed. "
          "Smoke test values are real numbers from the build machine (Windows 11, 15.4 GiB). "
          "Faculty ask: why no hard/soft split? Explain it requires Windows Perf Counters (heavier API).")

# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 12 – Conclusion & Future Scope
# ══════════════════════════════════════════════════════════════════════════════
s12 = prs.slides.add_slide(blank)
set_bg(s12, NAVY)
rect(s12, 0, 0, 13.33, 0.07, fill=CYAN)
title_bar(s12, "Conclusion & Future Scope",
          "What was achieved — and what can be extended next")

sec_hdr(s12, 0.22, 1.40, 6.22, "What Was Achieved  ✅", fill=GREEN)

achieved = [
    "Complete, running Windows memory analysis app — not a prototype",
    "3 native Windows APIs integrated via ctypes without admin privileges",
    "5 controlled workloads (A–E) in isolated subprocesses — UI stays responsive",
    "Per-interval capture: PageFaultCount · Working Set · Private Bytes · Available RAM",
    "Page-fault Δ and fault rate with DWORD wrap-around handling",
    "7 Plotly visualisations: gauges · trends · dual-axis · bar · overlay",
    "SQLite persistence (WAL) + CSV export for summaries and raw samples",
    "Comparison page with compatibility warnings and time-series overlays",
    "97 unit tests — 100% pass — metrics, validation, storage, comparison",
    "Accurate documentation: PageFaultCount ≠ disk reads, throughout UI and tests",
]

ty = 1.84
for item in achieved:
    txb(s12, 0.32, ty, 6.0, 0.36, "✅  " + item, size=Pt(10.5), color=LGRAY)
    ty += 0.38

sec_hdr(s12, 6.65, 1.40, 6.46, "Future Scope  🔮  (Not Implemented)", fill=PURPLE)

future = [
    ("Hard Fault Separation",
     "Integrate Windows Performance Counters API to separately count hard vs soft faults — the key limitation"),
    ("ETW Kernel Tracing",
     "Event Tracing for Windows: capture memory events at kernel resolution, sub-millisecond granularity"),
    ("Working-Set Breakdown",
     "QueryWorkingSet / NtQueryVirtualMemory to categorise pages by type (private, shared, mapped file)"),
    ("Multi-Process Experiments",
     "Concurrent workloads across multiple PIDs to study inter-process memory pressure and eviction"),
    ("Statistical Baselines",
     "Record 'golden runs'; flag statistically significant deviations across repeated experiments"),
    ("Linux Parity Module",
     "/proc/self/status + perf_event_open() collectors for full cross-OS comparison (complete course scope)"),
]

ty = 1.84
for title, desc in future:
    txb(s12, 6.78, ty, 6.2, 0.26, "🔮  " + title, size=Pt(11), bold=True, color=PURPLE)
    txb(s12, 6.78, ty+0.27, 6.2, 0.40, desc, size=Pt(10.5), color=LGRAY)
    ty += 0.75

# Thank you bar
rect(s12, 0, 6.90, 13.33, 0.60, fill=BLUE)
txb(s12, 0, 6.97, 13.33, 0.46,
    "Thank You!   |   Questions Welcome   |   Source: windows-memory-analyzer/   |   streamlit run app.py",
    size=Pt(14), bold=True, color=WHITE, align=PP_ALIGN.CENTER)

note(s12, "Summarise: fully functional application, every feature implemented and tested. "
          "Most impactful future addition: hard-fault separation via Windows Perf Counters. "
          "Linux module would satisfy the full course requirement.")

# ── Save ──────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "Windows_Memory_Behavior_Page_Fault_Analyzer.pptx")
prs.save(out)
print(f"Saved:  {out}")
print(f"Slides: {len(prs.slides)}")
