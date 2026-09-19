#!/usr/bin/env python3
"""Parse every sheet of `uploads/Alpha One PRD.pdf` into `scripts/prd-workbook.json`.

The PRD is a Google-Sheets workbook exported to PDF (79 pages, 17 sheets). The
older `scripts/prd-backlog.json` captured only the master backlog's planning
columns (phase/rel/pri/cx/own/story/feat). This script captures the *whole*
workbook, sheet by sheet, so nothing in the source of truth is lost:

  sheet (PDF pages)                     -> JSON key
  ---------------------------------------------------------------------------
  Domains and Modules (1-2)             -> domains_and_modules
  Master Backlog (3-29)                 -> master_backlog       (1012 rows)
  Cross-Sheet Audit (41)                -> backlog_audit
  Feature Proposals (42)                -> feature_proposals   (PROP-0001..0014)
  Version Roadmap (43)                  -> version_roadmap
  Change Log (44-46)                    -> change_log          (decision log)
  V1 Execution (47-48)                  -> v1_execution        (derived sheet)
  Integration Map (53)                  -> integration_map     (third parties)
  Future Backlog (54-63)                -> future_backlog      (derived sheet)
  Tooling Register (64-65)              -> tooling_register
  Build vs Buy Rules (66)               -> build_vs_buy_rules  (BVR-01..28)
  Data Dictionary (67-69)               -> data_dictionary     (closed enums)
  3. Open Questions (70-77)             -> open_questions
  Out Of Scope (78-79)                  -> out_of_scope

How the extraction works
------------------------
pypdf reports each text fragment with a text matrix (`tm`) inside a current
transformation matrix (`cm`); their product is the position on the page. Lines
are rebuilt by bucketing fragments on y, rows by anchoring on the sheet's first
column (every backlog row anchors on its `MOD-NN` id, every register row on its
first-column value). Column membership is resolved by nearest header x — exact
here, because the workbook left-aligns cells under their header — except for the
free-form sheets (Open Questions, Out Of Scope), whose columns are resolved by
fixed x-bands.

Requires: pypdf (dev-only tooling dependency — `pip install pypdf`).
Usage:    python3 scripts/parse_prd_workbook.py [--pdf PATH] [--out PATH] [--check]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import OrderedDict

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PDF = ROOT.parent / "uploads" / "Alpha One PRD.pdf"
DEFAULT_OUT = ROOT / "scripts" / "prd-workbook.json"

REQ_ID = re.compile(r"^[A-Z]{2,5}-\d{2,3}$")
MODULE_ID = re.compile(r"^([A-Z]{2,5})\s+(.+)$")
BVR_ID = re.compile(r"^BVR-\d{2}$")
PROP_ID = re.compile(r"^PROP-\d{4}$")
RELEASE_ID = re.compile(r"^V\d\.\d$")
LEGACY_TIMESTAMP = re.compile(r"^\d{1,2}/\d{1,2}/\d{4} \d{1,2}:\d{2}:\d{2}$|^\d{4}-\d{2}-\d{2} \d{1,2}:\d{2}:\d{2}$")


SPLIT_ID = re.compile(r"^([A-Z]{2,4}) ([A-Z])-(\d{2,3})$")


def unsplit_ids(text: str) -> str:
    """Repair PDF kerning artefacts such as 'PL T-01' -> 'PLT-01'."""
    return SPLIT_ID.sub(r"\1\2-\3", text)


def squash(text: str) -> str:
    """Join the wrap points the PDF introduces inside a cell.

    The PDF breaks words at line ends ("server- side"), inserts a space after a
    hyphen ("BRG- 10") and sometimes splits an id ("PL T-02") — undo all three.
    """
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=[A-Za-z0-9])- (?=[A-Za-z0-9])", "-", text)
    text = re.sub(r"\b([A-Z]{2,4}) ([A-Z])-(\d{2,3})\b", r"\1\2-\3", text)
    text = re.sub(r"\s+([,.;:!?%)])", r"\1", text)
    return text


# --------------------------------------------------------------------------- #
# PDF -> lines -> rows
# --------------------------------------------------------------------------- #


def page_lines(page, y_tolerance: float = 1.6):
    """[(y, [(x, text)])], top-to-bottom, in PDF user space (y up)."""
    frags = []

    def visitor(text, cm, tm, font_dict, font_size):
        t = unsplit_ids(text.strip())
        if not t:
            return
        x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        frags.append((round(y, 1), round(x, 1), t))

    page.extract_text(visitor_text=visitor)
    buckets: list[list] = []
    for y, x, t in sorted(frags, key=lambda f: (-f[0], f[1])):
        if buckets and abs(buckets[-1][0] - y) <= y_tolerance:
            buckets[-1][1].append((x, t))
        else:
            buckets.append([y, [(x, t)]])
    return [(y, sorted(fs)) for y, fs in buckets]


def header_columns(lines, names) -> list[tuple[str, float]]:
    found: dict[str, float] = {}
    for _y, frags in lines[:4]:
        for x, t in frags:
            if t in names and t not in found:
                found[t] = x
    return [(n, found[n]) for n in names if n in found]


STORY_HINT = re.compile(r"^(As (a|an|the|any|ops|risk|tenant|trader|client|platform|support)\b)")


def column_index(x: float, text: str, xs, names, tolerance: float = 45.0):
    """Nearest header column for a fragment, with a story-shape hint.

    Cells are centred, so a long story can start left of its own column; a
    fragment that reads like a user story therefore always lands in User Story.
    Returns None when the fragment is too far from every column.
    """
    i = min(range(len(xs)), key=lambda i: abs(x - xs[i]))
    if "User Story" in names and STORY_HINT.match(text):
        return names.index("User Story")
    if abs(x - xs[i]) > tolerance:
        return None
    return i


def bucket_to_columns(frags, columns, tolerance: float = 45.0) -> dict[str, str]:
    xs = [x for _, x in columns]
    names = [n for n, _ in columns]
    acc: dict[str, list[str]] = {n: [] for n, _ in columns}
    for x, t in frags:
        i = column_index(x, t, xs, names, tolerance)
        if i is None:
            continue
        acc[names[i]].append(t)
    return {n: squash(" ".join(v)) for n, v in acc.items() if v}


def bucket_to_bands(frags, bands) -> dict[str, str]:
    """bands = [(name, x_start, x_end)] — used by the free-form sheets."""
    acc: dict[str, list[str]] = {}
    for x, t in frags:
        for name, lo, hi in bands:
            if lo <= x < hi:
                acc.setdefault(name, []).append(t)
                break
    return {n: squash(" ".join(v)) for n, v in acc.items() if v}


def _align_runs(runs, anchors):
    """Order-preserving alignment of a column's text runs to the row anchors.

    Rows are pitch-spaced, but their wrapped cells extend both above and below
    the anchor line, so 'nearest anchor' alone mis-assigns the boundary lines.
    A monotone (sequence) alignment of runs to anchors in reading order fixes it:
    a run matching at cost |centre - anchor|, an anchor skipped because the cell
    is empty at cost 5, a run skipped at cost 30.
    """
    n, m = len(runs), len(anchors)
    INF = float("inf")
    dp = [[INF] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur == INF:
                continue
            if i < n and j < m:
                cost = abs(runs[i][0] - anchors[j])
                if cur + cost < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = cur + cost
            if j < m and cur + 5 < dp[i][j + 1]:
                dp[i][j + 1] = cur + 5
            if i < n and cur + 30 < dp[i + 1][j]:
                dp[i + 1][j] = cur + 30
    # backtrack
    pairs, i, j = [], n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + abs(runs[i - 1][0] - anchors[j - 1]):
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif j > 0 and dp[i][j] == dp[i][j - 1] + 5:
            j -= 1
        elif i > 0 and dp[i][j] == dp[i + 0][j] - 0 and dp[i][j] == dp[i - 1][j] + 30:
            i -= 1
        elif i > 0:
            i -= 1
        else:
            j -= 1
    return pairs


def anchor_rows(pages_lines, pages, columns, pattern=None, require_header=None,
                anchor_tolerance: float = 26.0, run_gap: float = 3.7, bands=None) -> list[dict]:
    """Rows for the tabular sheets, anchored on the sheet's first column.

    Every printed page repeats the sheet header, and the column offsets drift a
    little page to page, so the header x-positions are re-read per page.
    """
    all_names = [n for n, _ in columns]

    out: list[dict] = []
    for pno in pages:
        columns = header_columns(pages_lines[pno], all_names) or columns
        col_map = dict(columns)
        first_x = columns[0][1]
        header_x = col_map.get(require_header, first_x) if require_header else first_x
        header_names = set(col_map)
        xs = [x for _, x in columns]
        names_of_cols = [n for n, _ in columns]
        anchors: list[float] = []
        for y, frags in pages_lines[pno]:
            if not frags or all(t in header_names for _, t in frags):
                continue
            x0, t0 = frags[0]
            if pattern is not None:
                is_anchor = bool(pattern.match(t0)) and abs(x0 - header_x) <= anchor_tolerance
            else:
                is_anchor = abs(x0 - header_x) <= 8.0
            if is_anchor:
                anchors.append(y)
        if not anchors:
            continue
        anchors.sort(reverse=True)
        rows: "OrderedDict[float, dict]" = OrderedDict((ay, {}) for ay in anchors)

        # Column fragment lists: by x-band when the sheet's headers do not sit
        # over their cells (centred headers over left-aligned data), else by
        # nearest header column.
        by_band: dict[str, list[tuple[float, str]]] = {n: [] for n in names_of_cols}
        if bands is not None:
            for y, fr in pages_lines[pno]:
                if all(t2 in header_names for _, t2 in fr):
                    continue
                for bname, btext in bucket_to_bands(fr, bands).items():
                    by_band[bname].append((y, btext))
        for i, (name, _x) in enumerate(columns):
            if bands is not None:
                frags = by_band.get(name, [])
            else:
                frags = [(y, t) for y, fr in pages_lines[pno]
                         if not all(t2 in header_names for _, t2 in fr)
                         for x, t in fr
                         if column_index(x, t, xs, names_of_cols) == i]
            if not frags:
                continue
            frags.sort(key=lambda f: -f[0])
            runs: list[dict] = []
            for y, t in frags:
                if runs and runs[-1]["last"] - y <= run_gap:
                    runs[-1]["text"] += " " + t
                    runs[-1]["last"] = y
                else:
                    runs.append({"first": y, "last": y, "text": t})
            centres = [(r["first"] + r["last"]) / 2 for r in runs]
            for run_i, anchor_j in _align_runs([(c, i) for c, i in zip(centres, range(len(runs)))], anchors):
                ay = anchors[anchor_j]
                rows[ay][name] = squash(rows[ay].get(name, "") + " " + runs[run_i]["text"])
        for ay, row in rows.items():
            row["page"] = pno + 1
            out.append(row)
    return out


def norm_row(row: dict, mapping: dict[str, str]) -> dict:
    out = {}
    for src, dst in mapping.items():
        val = row.get(src, "")
        if val:
            parts = val.split()
            if len(parts) > 1 and len(set(parts)) == 1:  # PDF repeats a cell ('V1.0 V1.0')
                val = parts[0]
            out[dst] = val
    if "page" in row:
        out["page"] = row["page"]
    return out


# --------------------------------------------------------------------------- #
# Sheet-specific parsers for the two free-form sheets
# --------------------------------------------------------------------------- #

# Open Questions columns (x-bands). "Answer" starts at the header's x (~478).
QUESTION_BANDS = [("question", 90, 255), ("raised_by", 255, 318), ("owner", 318, 398),
                  ("deadline", 398, 472), ("answer", 472, 900)]
QUESTION_BANDS_DICT = {name: (lo, hi) for name, lo, hi in QUESTION_BANDS}


def _group_runs(frags, gap):
    """Group (y, text) fragments into runs of consecutive lines (same cell)."""
    frags = sorted(frags, key=lambda f: -f[0])
    runs: list[dict] = []
    for y, t in frags:
        if runs and runs[-1]["last"] - y <= gap:
            runs[-1]["text"] += " " + t
            runs[-1]["last"] = y
        else:
            runs.append({"first": y, "last": y, "text": t})
    return runs


def parse_open_questions(pages_lines, pages, module_names) -> list[dict]:
    """Open Questions sheet.

    The question cell is the row's identity: its lines are grouped into blocks
    (intra-cell leading ~5.7, gap between questions ~7.6), and every other column
    is aligned to those blocks with the monotone run alignment. That matters
    because a long answer or owner cell is vertically centred and therefore
    overflows into the neighbouring row's band — plain nearest-line attachment
    mixes rows up. Lone module names are section banners.
    """
    rows: list[dict] = []
    carry = ""
    for pno in pages:
        lines = [ln for ln in pages_lines[pno] if ln[1]]
        if not lines:
            continue
        body: list[tuple[float, list]] = []
        banners: list[tuple[float, str]] = []
        for y, frags in lines:
            joined = squash(" ".join(t for _, t in frags))
            if len(frags) == 1 and joined in module_names:
                banners.append((y, joined))
                continue
            if joined.startswith("3. Open Questions") or (
                    joined.startswith("Question") and "Deadline" in joined):
                continue
            body.append((y, frags))

        def band(name):
            lo, hi = QUESTION_BANDS_DICT[name]
            return [(y, t) for y, fr in body for x, t in fr if lo <= x < hi]

        q_runs = _group_runs(band("question"), gap=6.6)
        if not q_runs:
            continue
        anchors = sorted(((r["first"] + r["last"]) / 2 for r in q_runs), reverse=True)
        cells = [{"question": r["text"]} for r in q_runs]

        for name in ("raised_by", "owner", "deadline", "answer"):
            runs = _group_runs(band(name), gap=6.6 if name == "answer" else 4.5)
            if not runs:
                continue
            centres = [(r["first"] + r["last"]) / 2 for r in runs]
            for run_i, anchor_j in _align_runs([(c, i) for c, i in zip(centres, range(len(runs)))], anchors):
                cells[anchor_j][name] = squash(cells[anchor_j].get(name, "") + " " + runs[run_i]["text"])

        for i, anchor in enumerate(anchors):
            above = [name for y, name in banners if y >= anchor]
            cells[i]["section"] = above[-1] if above else carry
            cells[i]["page"] = pno + 1
            rows.append(cells[i])
        if banners:
            carry = banners[-1][1]
    for row in rows:
        row.setdefault("raised_by", "")
        row.setdefault("owner", "")
        row.setdefault("deadline", "")
        row.setdefault("answer", "")
    return [r for r in rows if r.get("question")]


def parse_out_of_scope(pages_lines, pages, module_names) -> list[dict]:
    """Out Of Scope sheet.

    A four-column flowing list. Every section header is one line carrying four
    module names; each body line belongs to the most recent header row *in
    reading order* (a section can run across a page break), and is assigned to
    the column whose header name is nearest in x. Inside a column a wrapped line
    sits ~4.2 below its predecessor while a new bullet starts ≥5.6 below, so a
    >4.9 y-jump starts a new item.
    """
    headers: list[tuple[int, float, list[tuple[float, str]]]] = []
    body: list[tuple[int, float, list]] = []
    for pno in pages:
        for y, frags in pages_lines[pno]:
            if not frags:
                continue
            names = sorted([(x, t) for x, t in frags if t in module_names])
            if len(names) >= 2:
                headers.append((pno, y, names))
            else:
                body.append((pno, y, frags))

    items: list[dict] = []
    for pno, y, frags in body:
        preceding = [(hp, hy, hc) for hp, hy, hc in headers
                     if hp < pno or (hp == pno and hy > y)]
        if not preceding:
            continue
        hp, hy, cols = max(preceding, key=lambda h: (h[0], -h[1]))
        by_col: dict[int, str] = {}
        for x, t in frags:
            i = min(range(len(cols)), key=lambda i: abs(x - cols[i][0]))
            by_col[i] = (by_col.get(i, "") + " " + t).strip()
        for i, text in by_col.items():
            name = cols[i][1]
            merge = None
            for cand in reversed(items):
                if cand["module"] == name and cand["_page"] == pno:
                    merge = cand
                    break
            if merge is not None and merge["_y"] - y <= 4.9:
                merge["item"] = squash(merge["item"] + " " + text)
                merge["_y"] = y
            else:
                items.append({"module": name, "item": text, "page": pno + 1, "_y": y, "_page": pno})

    for it in items:
        it.pop("_y", None)
        it.pop("_page", None)
    return [it for it in items if it["item"]]


# --------------------------------------------------------------------------- #
# Sheet definitions
# --------------------------------------------------------------------------- #

BACKLOG_NAMES = [
    "Req ID", "Domain ID", "Domain Name", "Module ID", "Module", "Feature Name",
    "User Story", "Complexity", "Priority", "Phase", "Status", "Owner",
    "Depends On", "Build Strategy", "Notes", "Proposed By", "Proposed On",
    "Team Comments", "Comment Status", "Last Reviewed By", "Last Reviewed On",
    "Release",
]
BACKLOG_KEYS = {
    "Req ID": "req", "Domain ID": "domain_id", "Domain Name": "domain_name",
    "Module ID": "module_id", "Module": "module", "Feature Name": "feature",
    "User Story": "story", "Complexity": "complexity", "Priority": "priority",
    "Phase": "phase", "Status": "status", "Owner": "owner",
    "Depends On": "depends_on", "Build Strategy": "build_strategy", "Notes": "notes",
    "Proposed By": "proposed_by", "Proposed On": "proposed_on",
    "Team Comments": "team_comments", "Comment Status": "comment_status",
    "Last Reviewed By": "last_reviewed_by", "Last Reviewed On": "last_reviewed_on",
    "Release": "release",
}
INTEGRATION_NAMES = ["Tool", "Category", "What it does", "Serves Req IDs", "Serves Release",
                     "Cost", "Cost model", "Signup status", "Owner", "Action needed"]
TOOLING_NAMES = ["Tool", "Category", "Type", "Licence", "Version / Plan", "Hosting",
                 "Replaces building", "Serves releases", "Serves Req IDs", "Why this one",
                 "Alternatives considered", "Why rejected", "Est. cost", "Cost model",
                 "Signup status", "Owner", "Exit path", "ADR link", "Notes"]
PROPOSAL_NAMES = ["Proposal ID", "Submitted On", "Submitted By", "Domain", "Module",
                  "Feature Name", "User Story", "Why It Matters", "Est. Complexity",
                  "Est. Priority", "Suggested Release", "Status", "Reviewer",
                  "Review Notes", "Promoted Req ID"]
ROADMAP_NAMES = ["Release", "Target Date", "Theme", "Cashflow Critical", "Gate Rule",
                 "Gate Status", "P0 Count", "P1 Count", "P2 Count", "Total Features",
                 "Status", "Notes"]
CHANGE_NAMES = ["Timestamp", "Actor", "Action", "Req ID", "Field", "Old Value", "New Value", "Reason"]
AUDIT_BANDS = [("severity", 0, 200), ("sheet", 200, 400), ("row", 400, 465),
               ("rule", 465, 520), ("detail", 520, 900)]
# The Change Log and Version Roadmap headers are centred over left-aligned
# cells, so their columns are read from these x-bands instead of header x.
CHANGE_BANDS = [("Timestamp", 0, 110), ("Actor", 110, 195), ("Action", 195, 275),
                ("Req ID", 275, 320), ("Field", 320, 373), ("Old Value", 373, 455),
                ("New Value", 455, 530), ("Reason", 530, 900)]
ROADMAP_BANDS = [("Release", 0, 60), ("Target Date", 60, 80), ("Theme", 80, 135),
                 ("Cashflow Critical", 135, 185), ("Gate Rule", 185, 240),
                 ("Gate Status", 240, 275), ("P0 Count", 275, 295), ("P1 Count", 295, 312),
                 ("P2 Count", 312, 330), ("Total Features", 330, 350), ("Status", 350, 366),
                 ("Notes", 366, 900)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(DEFAULT_PDF))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--check", action="store_true",
                    help="verify the extraction against scripts/prd-backlog.json and exit")
    ap.add_argument("--merge-legacy", action="store_true",
                    help="append requirements found in the PDF but absent from prd-backlog.json")
    args = ap.parse_args()

    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover
        sys.exit("pypdf is required for this dev tool: pip install pypdf")

    pdf_path = pathlib.Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"PRD not found: {pdf_path} (pass --pdf)")

    reader = PdfReader(str(pdf_path))
    L = [page_lines(p) for p in reader.pages]

    out: dict = {"_meta": {
        "source": str(pdf_path).replace(str(ROOT.parent) + "/", ""),
        "extractor": "scripts/parse_prd_workbook.py",
        "extracted": "2026-09-19",
        "pages": len(reader.pages),
        "note": ("Machine-readable mirror of every PRD workbook sheet. Complements "
                 "scripts/prd-backlog.json, which keeps only the planning columns used by "
                 "the contract pack's requirement-coverage check."),
    }}

    # ---- Domains and Modules (pages 1-2) ---------------------------------- #
    dom_cols = header_columns(L[0], ["Domain ID", "Domain Name", "Module ID", "Module Name"])
    doms = anchor_rows(L, [0, 1], dom_cols, pattern=re.compile(r"^D[1-5]$"), require_header="Domain ID")
    out["domains_and_modules"] = [
        norm_row(r, {"Domain ID": "domain_id", "Domain Name": "domain_name",
                     "Module ID": "module_id", "Module Name": "module_name"})
        for r in doms if r.get("Module ID")
    ]
    module_names = {m["module_name"] for m in out["domains_and_modules"]}

    # ---- Master Backlog (pages 3-29) -------------------------------------- #
    mb_cols = header_columns(L[2], BACKLOG_NAMES)
    master = anchor_rows(L, list(range(2, 29)), mb_cols, pattern=REQ_ID, require_header="Req ID")
    out["master_backlog"] = []
    for row in master:
        if not row.get("Req ID"):
            continue
        # on a few pages a wide module cell drifts into the Module ID column
        if " " in (row.get("Module ID") or ""):
            m = MODULE_ID.match(row["Module ID"])
            if m:
                row["Module ID"] = m.group(1)
                row["Module"] = squash(m.group(2) + " " + row.get("Module", ""))
        out["master_backlog"].append(norm_row(row, BACKLOG_KEYS))

    # ---- Derived sheets: V1 Execution (47-48), Future Backlog (54-63) ------ #
    for key, pages in (("v1_execution", [46, 47]), ("future_backlog", list(range(53, 63)))):
        cols = header_columns(L[pages[0]], BACKLOG_NAMES)
        rows = anchor_rows(L, pages, cols, pattern=REQ_ID, require_header="Req ID")
        out[key] = [norm_row(r, BACKLOG_KEYS) for r in rows if r.get("Req ID")]

    # ---- Cross-sheet audit (page 41) -------------------------------------- #
    audit: dict = {"run_at": "", "findings": []}
    for y, frags in L[40]:
        text = squash(" ".join(t for _, t in frags))
        if m := re.match(r"^Audit run: (\S+)$", text):
            audit["run_at"] = m.group(1)
        if m := re.match(r"^(Findings|Errors|Warnings): (\d+)$", text):
            audit[{"Findings": "findings_count", "Errors": "errors", "Warnings": "warnings"}[m.group(1)]] = int(m.group(2))
        vals = bucket_to_bands(frags, AUDIT_BANDS)
        if vals.get("severity") in ("ERROR", "WARN"):
            audit["findings"].append({"severity": vals["severity"], "sheet": vals.get("sheet", ""),
                                      "row": vals.get("row", ""), "rule": vals.get("rule", ""),
                                      "detail": vals.get("detail", "")})
    out["backlog_audit"] = audit

    # ---- Feature Proposals (page 42) -------------------------------------- #
    p_cols = header_columns(L[41], PROPOSAL_NAMES)
    props = anchor_rows(L, [41], p_cols, pattern=PROP_ID, require_header="Proposal ID")
    out["feature_proposals"] = [
        norm_row(r, {"Proposal ID": "id", "Submitted On": "submitted_on", "Submitted By": "submitted_by",
                     "Domain": "domain", "Module": "module", "Feature Name": "feature",
                     "User Story": "story", "Why It Matters": "why_it_matters",
                     "Est. Complexity": "est_complexity", "Est. Priority": "est_priority",
                     "Suggested Release": "suggested_release", "Status": "status",
                     "Reviewer": "reviewer", "Review Notes": "review_notes",
                     "Promoted Req ID": "promoted_req"})
        for r in props if r.get("Proposal ID")]

    # ---- Version Roadmap (page 43) ---------------------------------------- #
    r_cols = header_columns(L[42], ROADMAP_NAMES)
    roadmap = anchor_rows(L, [42], r_cols, pattern=RELEASE_ID, require_header="Release",
                          bands=ROADMAP_BANDS)
    out["version_roadmap"] = [
        norm_row(r, {"Release": "release", "Target Date": "target_date", "Theme": "theme",
                     "Cashflow Critical": "cashflow_critical", "Gate Rule": "gate_rule",
                     "Gate Status": "gate_status", "P0 Count": "p0", "P1 Count": "p1",
                     "P2 Count": "p2", "Total Features": "total", "Status": "status",
                     "Notes": "notes"})
        for r in roadmap if r.get("Release")]

    # ---- Change Log (pages 44-46) ----------------------------------------- #
    c_cols = header_columns(L[43], CHANGE_NAMES)
    changes = anchor_rows(L, [43, 44, 45], c_cols, pattern=LEGACY_TIMESTAMP,
                          require_header="Timestamp", bands=CHANGE_BANDS)
    out["change_log"] = [
        norm_row(r, {"Timestamp": "timestamp", "Actor": "actor", "Action": "action", "Req ID": "req",
                     "Field": "field", "Old Value": "old_value", "New Value": "new_value",
                     "Reason": "reason"})
        for r in changes if r.get("Action")]

    # ---- Integration Map (page 53) ---------------------------------------- #
    i_cols = header_columns(L[52], INTEGRATION_NAMES)
    integ = anchor_rows(L, [52], i_cols, require_header="Tool")
    out["integration_map"] = [
        norm_row(r, {"Tool": "tool", "Category": "category", "What it does": "what_it_does",
                     "Serves Req IDs": "serves_req_ids", "Serves Release": "serves_release",
                     "Cost": "cost", "Cost model": "cost_model", "Signup status": "signup_status",
                     "Owner": "owner", "Action needed": "action_needed"})
        for r in integ if r.get("Tool")]

    # ---- Tooling Register (pages 64-65) ----------------------------------- #
    t_cols = header_columns(L[63], TOOLING_NAMES)
    tools = anchor_rows(L, [63, 64], t_cols, require_header="Tool")
    out["tooling_register"] = [
        norm_row(r, {"Tool": "tool", "Category": "category", "Type": "type", "Licence": "licence",
                     "Version / Plan": "version_plan", "Hosting": "hosting",
                     "Replaces building": "replaces_building", "Serves releases": "serves_releases",
                     "Serves Req IDs": "serves_req_ids", "Why this one": "why_this_one",
                     "Alternatives considered": "alternatives_considered",
                     "Why rejected": "why_rejected", "Est. cost": "cost",
                     "Cost model": "cost_model", "Signup status": "signup_status",
                     "Owner": "owner", "Exit path": "exit_path", "ADR link": "adr_link",
                     "Notes": "notes"})
        for r in tools if r.get("Tool")]

    # ---- Build vs Buy Rules (page 66) ------------------------------------- #
    b_cols = header_columns(L[65], ["Rule ID", "Rule", "Applies to", "Enforced by", "Notes"])
    rules = anchor_rows(L, [65], b_cols, pattern=BVR_ID, require_header="Rule ID")
    out["build_vs_buy_rules"] = [
        norm_row(r, {"Rule ID": "id", "Rule": "rule", "Applies to": "applies_to",
                     "Enforced by": "enforced_by", "Notes": "notes"})
        for r in rules if r.get("Rule ID")]

    # ---- Data Dictionary (pages 67-69) ------------------------------------ #
    dd, seen = [], set()
    for pno in (66, 67, 68):
        for _y, frags in L[pno]:
            vals = bucket_to_bands(frags, [("section", 100, 300), ("value", 300, 700)])
            s, v = vals.get("section", ""), vals.get("value", "")
            if not s or s == "Section" or (s, v) in seen:
                continue
            seen.add((s, v))
            dd.append({"section": s, "value": v})
    out["data_dictionary"] = dd

    # ---- Open Questions (pages 70-77) ------------------------------------- #
    out["open_questions"] = parse_open_questions(L, list(range(69, 77)), module_names)

    # ---- Out Of Scope (pages 78-79) --------------------------------------- #
    out["out_of_scope"] = parse_out_of_scope(L, [77, 78], module_names)

    out["_meta"]["counts"] = {k: (len(v) if isinstance(v, list) else 1) for k, v in out.items() if k != "_meta"}

    if args.check:
        return check(out)
    if args.merge_legacy:
        merge_legacy(out)

    pathlib.Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {args.out}")
    for k, v in out["_meta"]["counts"].items():
        print(f"  {k:22s} {v}")
    return 0


def merge_legacy(out) -> None:
    """Synchronise scripts/prd-backlog.json with the parsed workbook.

    Adds requirements the legacy extraction missed and refreshes the seven
    planning fields (`feat`, `story`, `phase`, `rel`, `pri`, `cx`, `own`) where
    this extraction is more accurate. The legacy file had three systematic
    defects: module names leaked into `feat`, some cells lost their leading
    text, and 8 requirements were absent entirely.
    """
    path = ROOT / "scripts" / "prd-backlog.json"
    legacy = json.loads(path.read_text())
    added: list[str] = []
    changed = 0
    for row in out["master_backlog"]:
        req = row["req"]
        fresh = {"phase": row.get("phase", ""), "rel": row.get("release", ""),
                 "pri": row.get("priority", ""), "cx": row.get("complexity", ""),
                 "own": row.get("owner", ""), "story": row.get("story", ""),
                 "feat": row.get("feature", "")}
        old = legacy.get(req)
        if old is None:
            added.append(req)
        elif any(old.get(k, "") != v for k, v in fresh.items()):
            changed += 1
        legacy[req] = fresh
    path.write_text(json.dumps(dict(sorted(legacy.items())), indent=1, ensure_ascii=False) + "\n")
    print(f"prd-backlog.json: {len(legacy)} rows "
          f"({len(added)} added{': ' + ', '.join(added) if added else ''}; {changed} refreshed)")


def check(out) -> int:
    """Cross-check against scripts/prd-backlog.json (the contract pack's input)."""
    legacy = json.loads((ROOT / "scripts" / "prd-backlog.json").read_text())
    master = {r["req"]: r for r in out["master_backlog"]}
    problems = []
    if len(legacy) != len(master):
        problems.append(f"row count: prd-backlog.json={len(legacy)} vs parsed={len(master)}")
    for req, old in legacy.items():
        new = master.get(req)
        if not new:
            problems.append(f"{req}: missing from parsed backlog")
            continue
        for old_key, new_key in (("phase", "phase"), ("rel", "release"), ("pri", "priority"),
                                 ("cx", "complexity"), ("own", "owner"), ("feat", "feature"),
                                 ("story", "story")):
            if (old.get(old_key) or "").strip() != (new.get(new_key) or "").strip():
                problems.append(f"{req}.{new_key}: {old.get(old_key)!r} -> {new.get(new_key)!r}")
    if problems:
        print(f"MISMATCHES ({len(problems)}):")
        for p in problems[:40]:
            print("  ", p)
        return 1
    print(f"OK: {len(master)} rows; prd-backlog.json agrees with the parsed workbook.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
