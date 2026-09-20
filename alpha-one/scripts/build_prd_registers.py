#!/usr/bin/env python3
"""Render the PRD workbook registers into the doc set.

The PRD workbook (`uploads/Alpha One PRD.pdf`) carries seven sheets that are
*not* the master backlog. They were missing from `docs/` until this script:
feature proposals, the version roadmap + gates, the change log, the backlog
audit, the workbook vocabularies, the open-questions register, and the
out-of-scope register. They are rendered here from `scripts/prd-workbook.json`
(the machine-readable mirror produced by `scripts/parse_prd_workbook.py`)
so the prose can never drift from the parsed source.

Generated:
  docs/36-prd-feature-proposals.md   PROP-0001..0014 + version roadmap/gates
  docs/37-prd-open-questions.md      the Open Questions sheet (grouped by module)
  docs/38-prd-out-of-scope.md        the Out Of Scope sheet (grouped by module)
  docs/39-prd-change-log.md          change log + backlog audit + vocabularies

Usage:
  python3 scripts/build_prd_registers.py            # write the docs
  python3 scripts/build_prd_registers.py --check    # verify they are current
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "prd-workbook.json"
DESIGN_Q = ROOT / "scripts" / "design-questions.json"
TRIAGE = ROOT / "scripts" / "prd-question-triage.json"
DOCS = ROOT / "docs"
EXTRACT_DATE = "2026-09-19"
TRIAGE_DATE = "2026-09-20"

HEADER = """# {num} — {title}

> Generated {date} by `scripts/build_prd_registers.py` from
> `scripts/prd-workbook.json` (parsed from `uploads/Alpha One PRD.pdf`,
> the *{sheet}* sheet). Do not edit by hand: re-run the script after a PRD
> change, exactly like `scripts/prd-backlog.json`.
>
> {blurb}
"""


def md_cell(text: str) -> str:
    """Escape a value for a markdown table cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip() or "—"


def slug(text: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in text]
    out = "".join(keep)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "section"


# --------------------------------------------------------------------------- #
# 36 — feature proposals + version roadmap
# --------------------------------------------------------------------------- #


def build_proposals(data: dict) -> str:
    props = data["feature_proposals"]
    roadmap = data["version_roadmap"]
    by_status: dict[str, int] = {}
    for p in props:
        by_status[p["status"]] = by_status.get(p["status"], 0) + 1

    out = [HEADER.format(
        num="36", title="PRD Feature Proposals & Release Roadmap", date=EXTRACT_DATE,
        sheet="Feature Proposals",
        blurb=("This document is the funnel between *ideas* and *the backlog*: §1 lists every "
               "proposal as submitted, §2 is the release roadmap with its gates. A proposal "
               "becomes buildable only when it is promoted into the backlog — the promoted "
               "Req ID is recorded in the PRD's `Promoted Req ID` column."),
    )]
    out.append(f"\nProposals: **{len(props)}** "
               f"({', '.join(f'{k} {v}' for k, v in sorted(by_status.items()))}). "
               "None are promoted into the backlog as of the workbook snapshot.\n")

    out.append("## 1. Proposals\n")
    out.append("| ID | Submitted | Domain | Module | Feature | Cx | Pri | Release | Status | Promoted Req |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for p in props:
        out.append("| `{id}` | {d} | {dom} | {mod} | {feat} | {cx} | {pri} | {rel} | {st} | {promoted} |".format(
            id=p["id"], d=md_cell(p.get("submitted_on")), dom=md_cell(p.get("domain")),
            mod=md_cell(p.get("module")), feat=md_cell(p.get("feature")),
            cx=md_cell(p.get("est_complexity")), pri=md_cell(p.get("est_priority")),
            rel=md_cell(p.get("suggested_release")), st=md_cell(p.get("status")),
            promoted=md_cell(p.get("promoted_req_id")),
        ))

    out.append("\n### 1.1 Why each was raised\n")
    for p in props:
        out.append(f"- **`{p['id']}` {p['feature']}** — {md_cell(p.get('why_it_matters'))}")
        if p.get("review_notes"):
            out.append(f"  - Review: {p['review_notes']}")

    out.append("\n## 2. Release roadmap and gates\n")
    out.append("| Release | Theme | Cashflow-critical gate | Gate status | P0 | P1 | P2 | Total | Status | Notes |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in roadmap:
        out.append("| **{rel}** | {theme} | {gate} | {gstatus} | {p0} | {p1} | {p2} | {total} | {st} | {notes} |".format(
            rel=r["release"], theme=md_cell(r.get("target_date")),
            gate=md_cell(r.get("cashflow_critical")), gstatus=md_cell(r.get("gate_status")),
            p0=r.get("p0", "—"), p1=r.get("p1", "—"), p2=r.get("p2", "—"),
            total=r.get("total", "—"), st=md_cell(r.get("status")), notes=md_cell(r.get("notes")),
        ))

    out.append("\n## 3. Reading the roadmap\n")
    out.append("- **A gate status of `Not Met` is the default until the release ships** — the PRD "
               "records the gate, not progress against it. The delivery order that satisfies the "
               "V1.0 gate is `docs/99-development-phases.md`.")
    out.append("- **V1.0 must ship every P0 money-path item** (take money → provision account → "
               "evaluate → pay out). P1 items inside a release are pulled in only when the P0 set "
               "is green; P2 items are opportunistic.")
    out.append("- Proposals (§1) do **not** count toward a release total until the `Promoted Req ID` "
               "column is filled and the row appears in the master backlog (`scripts/prd-backlog.json`).\n")

    out.append("## 4. Open items\n")
    out.append("- 14 proposals are un-reviewed for promotion (status `New`); the promotion board "
               "should either promote each into a release or reject it with a note.")
    out.append("- V1.0/V1.1 gates are `Not Met` and are re-evaluated at each release review "
               "(`docs/99-development-phases.md` §Gates).")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 37 — open questions
# --------------------------------------------------------------------------- #


def is_open(q: dict) -> bool:
    """A row is open when the answer cell is empty or the literal 'Open'.

    Leading markdown emphasis is stripped first: design-review rows record a default
    as ``**Open — default recorded:** …``, which must still count as open.
    """
    ans = (q.get("answer") or "").strip().lstrip("*_ ").strip()
    return not ans or ans.lower().startswith("open")


def design_questions() -> list[dict]:
    """Questions raised by the team in design review (not PRD workbook rows)."""
    if not DESIGN_Q.is_file():
        return []
    return json.loads(DESIGN_Q.read_text()).get("questions", [])


def build_open_questions(data: dict) -> str:
    qs = data["open_questions"]
    extra = design_questions()
    sections: dict[str, list[dict]] = {}
    for q in qs:
        sections.setdefault(q.get("section") or "Unfiled", []).append(q)
    answered = [q for q in qs if not is_open(q)]

    out = [HEADER.format(
        num="37", title="PRD Open Questions Register", date=EXTRACT_DATE,
        sheet="Open Questions",
        blurb=("Every question the PRD raised, grouped by the module it blocks. An empty "
               "**Answer** cell means the question is still open and must be closed before the "
               "owning module's contract freeze (docs/99 §12). Answers captured in the workbook "
               "are reproduced verbatim; they outrank prose elsewhere in the doc set."),
    )]
    out.append(f"\nQuestions: **{len(qs)}** in {len(sections)} sections — "
               f"**{len(answered)} answered**, {len(qs) - len(answered)} open.\n")
    if extra:
        open_extra = sum(1 for q in extra if is_open(q))
        out.append(f"Design-review questions (raised by the team, not the PRD workbook): "
                   f"**{len(extra)}** — **{open_extra} open** (§Design-review questions below).\n")
    out.append("| Section | Questions | Open |")
    out.append("|---|---|---|")
    for name, rows in sorted(sections.items(), key=lambda kv: -len(kv[1])):
        open_n = sum(1 for r in rows if is_open(r))
        out.append(f"| {md_cell(name)} | {len(rows)} | {open_n} |")

    for name, rows in sorted(sections.items(), key=lambda kv: -len(kv[1])):
        out.append(f"\n## {name}\n")
        out.append("| # | Question | Raised by | Owner | Deadline | Answer |")
        out.append("|---|---|---|---|---|---|")
        for i, q in enumerate(rows, 1):
            out.append("| {i} | {qn} | {by} | {own} | {dl} | {ans} |".format(
                i=i, qn=md_cell(q.get("question")), by=md_cell(q.get("raised_by")),
                own=md_cell(q.get("owner")), dl=md_cell(q.get("deadline")),
                ans=md_cell(q.get("answer")),
            ))

    out.append("\n## Design-review questions\n")
    out.append("Raised by the team during design review — they are **not** PRD workbook rows, so "
               "they are maintained in `scripts/design-questions.json` (the PRD rows above are "
               "generated from `scripts/prd-workbook.json`). Evidence for each is in "
               "`docs/41-auth-ten-open-source-evaluation.md`; an answer here must be applied to "
               "the owning module doc in the same change.\n")
    if extra:
        out.append("| ID | Question | Raised by | Owner | Deadline | Answer |")
        out.append("|---|---|---|---|---|---|")
        for q in extra:
            out.append("| {i} | {qn} | {by} | {own} | {dl} | {ans} |".format(
                i=q.get("id") or "—", qn=md_cell(q.get("question")),
                by=md_cell(q.get("raised_by")), own=md_cell(q.get("owner")),
                dl=md_cell(q.get("deadline")), ans=md_cell(q.get("answer")),
            ))
    else:
        out.append("*None recorded.*")

    out.append("\n## Using this register\n")
    out.append("- **An open question is a design risk, not a blocker to writing docs** — the "
               "owning doc states the default it assumes and cites the question row; the answer "
               "then updates both.")
    out.append("- **Answered rows are decisions.** They are binding for contract freeze; the "
               "`docs/99-development-phases.md` gate checklist re-reads this register at each phase exit.")
    out.append("- **New questions** belong in `scripts/prd-workbook.json` (PRD rows) or "
               "`scripts/design-questions.json` (design-review rows) so this script picks them up, "
               "not in ad-hoc comments.\n")
    out.append("- **Design-review rows carry an ID (`D1`, `D2`, …)** and are cited by that ID from "
               "the module docs; PRD rows are cited as `<Section> #<n>`.\n")
    out.extend(triage_section(data))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 37 (cont.) — question triage (who can answer) + 37a stakeholder hand-off
# --------------------------------------------------------------------------- #


def _norm(text: str) -> str:
    import re
    return re.sub(r"\s+", " ", text or "").strip()


def _load_triage() -> dict:
    if not TRIAGE.is_file():
        return {}
    return json.loads(TRIAGE.read_text())


def _triage_map(data: dict, triage: dict) -> dict:
    """(section, normalized question) -> triage row, for the OPEN rows only."""
    lookup = {(t["section"], _norm(t["q"])): t for t in triage.get("rows", [])}
    return lookup


def triage_section(data: dict) -> list[str]:
    triage = _load_triage()
    lookup = _triage_map(data, triage)
    if not lookup:
        return []
    buckets = triage.get("buckets", [])
    internal = triage.get("internal_bucket")

    # register numbering: every row of a section gets a # (as in the tables above)
    num: dict[str, int] = {}
    matched: list[dict] = []
    for q in data["open_questions"]:
        sec = q.get("section") or "Unfiled"
        num[sec] = num.get(sec, 0) + 1
        if is_open(q):
            key = (sec, _norm(q.get("question")))
            if key in lookup:
                matched.append({**lookup[key], "sec": sec, "n": num[sec]})

    if len(matched) != len(lookup):
        raise SystemExit(
            f"triage mismatch: {len(lookup)} triage rows but only {len(matched)} "
            f"matched open workbook rows — re-run scripts/build_triage_data.py")

    per_bucket: dict[str, list[dict]] = {b: [] for b in buckets}
    for m in matched:
        per_bucket[m["bucket"]].append(m)

    out = [f"\n## Question triage — who can answer (added {TRIAGE_DATE}, gap-closure pass)\n"]
    out.append("Source: `scripts/prd-question-triage.json` (written by "
               "`scripts/build_triage_data.py`). Every open question above is assigned to the "
               "stakeholder **who can answer it** — not the person who raised it. "
               f"**No row in this section is an answer**: the `{internal}` rows carry a "
               "proposed answer marked *Proposed — pending sign-off* (adopting the PRD's own "
               "'Recommended:' text where present, or the binding spec where it already decided "
               "the point); it becomes a decision only when the named owner signs off — the "
               "D-number convention (docs/62 register) applies. The flat hand-off for the "
               "stakeholders themselves is "
               "`docs/37a-stakeholder-questions-for-funderblu.md`.\n")
    out.append("| Bucket (who can answer) | Questions |")
    out.append("|---|---|")
    for b in buckets:
        out.append(f"| {md_cell(b)} | {len(per_bucket[b])} |")
    out.append(f"| **Total** | **{len(matched)}** |")
    for b in buckets:
        rows = sorted(per_bucket[b], key=lambda m: (m["sec"], m["n"]))
        out.append(f"\n### {b} ({len(rows)})\n")
        out.append("| Ref | Question | Note / proposal |")
        out.append("|---|---|---|")
        for m in rows:
            ref = f"{md_cell(m['sec'])} #{m['n']}"
            qtext = m["q"]
            if len(qtext) > 110:
                qtext = qtext[:107].rsplit(" ", 1)[0] + "…"
            out.append(f"| {ref} | {md_cell(qtext)} | {md_cell(m.get('note') or '—')} |")
    return out


def build_stakeholder_handoff(data: dict) -> str:
    triage = _load_triage()
    lookup = _triage_map(data, triage)
    buckets = triage.get("buckets", [])
    internal = triage.get("internal_bucket")
    num: dict[str, int] = {}
    matched: list[dict] = []
    for q in data["open_questions"]:
        sec = q.get("section") or "Unfiled"
        num[sec] = num.get(sec, 0) + 1
        if is_open(q):
            key = (sec, _norm(q.get("question")))
            if key in lookup:
                matched.append({**lookup[key], "sec": sec, "n": num[sec]})
    per_bucket: dict[str, list[dict]] = {b: [] for b in buckets}
    for m in matched:
        per_bucket[m["bucket"]].append(m)

    out = [
        "# 37a — Open Questions, grouped by who can answer (hand-off for FunderBlu)",
        "",
        f"> Generated {TRIAGE_DATE} by `scripts/build_prd_registers.py` from "
        "`scripts/prd-question-triage.json` + `scripts/prd-workbook.json` (the docs/37 open "
        "rows). Do not edit by hand — answers are captured in the PRD workbook and the "
        "design-question register (the D-number convention), then this file is regenerated.",
        ">",
        f"> **What this is:** the {len(matched)} open PRD questions from "
        "`docs/37-prd-open-questions.md`, regrouped by the stakeholder who can actually "
        "answer each one. **What it is not:** an answer sheet. Only the "
        f"\"{internal}\" section at the bottom carries proposed answers, each marked "
        "*Proposed — pending sign-off*; every other section needs the named stakeholder's "
        "decision. A question becomes *Answered* only when a real owner decision is "
        "recorded (workbook answer cell or a D-row in docs/37) — never by default.",
        ">",
        "**How to use it (suggested):** each stakeholder replies per question (copy the "
        "numbered list into a reply). When a decision lands: the Tech Lead writes it into "
        "`scripts/prd-workbook.json` (PRD rows) or `scripts/design-questions.json` "
        "(new D-row), re-runs `scripts/build_prd_registers.py`, and the owning module doc "
        "is updated in the same change.",
        "",
    ]
    for b in buckets:
        rows = sorted(per_bucket[b], key=lambda m: (m["sec"], m["n"]))
        out.append(f"## {b} — {len(rows)} questions\n")
        if b == internal:
            out.append("These are the questions the Tech Lead can decide now; each carries a "
                       "proposal marked *Proposed — pending sign-off*. Proposals adopt the "
                       "PRD's own 'Recommended:' text where present, or the binding spec where "
                       "it already decided the point. They are **not** decisions until "
                       "FunderBlu (the relevant owner) signs off.\n")
        out.append("| # | Section | Question | Note |")
        out.append("|---|---|---|---|")
        for i, m in enumerate(rows, 1):
            out.append(f"| {i} | {md_cell(m['sec'])} | {md_cell(m['q'])} | "
                       f"{md_cell(m.get('note') or '—')} |")
        out.append("")
    total = len(data["open_questions"])
    answered = total - sum(1 for q in data["open_questions"] if is_open(q))
    out.append("---")
    out.append(f"\nCounts by stakeholder: " +
               ", ".join(f"{b} {len(per_bucket[b])}" for b in buckets) +
               f". Total: **{len(matched)}** of {total} PRD questions are open "
               f"({answered} answered — in the docs/37 register; answers captured in the "
               "workbook outrank prose elsewhere).\n")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 38 — out of scope
# --------------------------------------------------------------------------- #


def build_out_of_scope(data: dict) -> str:
    items = data["out_of_scope"]
    by_module: dict[str, list[dict]] = {}
    for it in items:
        by_module.setdefault(it.get("module") or "Unfiled", []).append(it)

    out = [HEADER.format(
        num="38", title="PRD Out-Of-Scope Register", date=EXTRACT_DATE,
        sheet="Out Of Scope",
        blurb=("What the platform deliberately does **not** do, per module. Anything listed "
               "here needs an explicit scope change (a promoted proposal, PRD change-log entry "
               "and backlog row) before it can be built — a PR implementing one of these is "
               "rejected on sight."),
    )]
    out.append(f"\nItems: **{len(items)}** across {len(by_module)} modules.\n")
    out.append("| Module | Items |")
    out.append("|---|---|")
    for name, rows in sorted(by_module.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(f"| {md_cell(name)} | {len(rows)} |")

    for name, rows in sorted(by_module.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(f"\n## {name}\n")
        for it in rows:
            out.append(f"- {md_cell(it.get('item'))}")

    out.append("\n## Related\n")
    out.append("- Rejected tools and forbidden infrastructure live in "
               "`docs/34-tooling-registry.md` §3.5; this register is about *product* scope.")
    out.append("- Deferrals that are scheduled (not forbidden) appear as `V2`/`V3` phases in "
               "`scripts/prd-backlog.json`, never here.\n")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- #
# 39 — change log + audit + vocabularies
# --------------------------------------------------------------------------- #


def build_change_log(data: dict) -> str:
    log = data["change_log"]
    audit = data["backlog_audit"]
    dd = data["data_dictionary"]
    findings = audit.get("findings", [])

    vocab: dict[str, list[str]] = {}
    for row in dd:
        vocab.setdefault(row.get("section") or "Other", []).append(row.get("value", ""))

    out = [HEADER.format(
        num="39", title="PRD Change Log, Backlog Audit & Vocabularies", date=EXTRACT_DATE,
        sheet="Change Log",
        blurb=("The workbook's own history: every structural edit the PRD author made, the "
               "last automated backlog audit, and the controlled vocabularies the backlog "
               "columns draw from. Use §1 to date a requirement change, §2 to see what is "
               "still inconsistent, and §3 as the enum source for contracts."),
    )]

    out.append(f"\nChange-log entries: **{len(log)}**. "
               f"Audit findings: **{len(findings)}**. "
               f"Vocabulary sections: **{len(vocab)}**.\n")

    out.append("## 1. Change log\n")
    out.append("| Timestamp | Actor | Action | Req | Field | Old | New |")
    out.append("|---|---|---|---|---|---|---|")
    for c in sorted(log, key=lambda r: (r.get("timestamp") or "")):
        out.append("| {ts} | {ac} | `{act}` | {req} | {f} | {old} | {new} |".format(
            ts=md_cell(c.get("timestamp")), ac=md_cell(c.get("actor")),
            act=md_cell(c.get("action")), req=md_cell(c.get("req")), f=md_cell(c.get("field")),
            old=md_cell(c.get("old_value")), new=md_cell(c.get("new_value")),
        ))

    out.append("\n### 1.1 Actions you will meet\n")
    seen: set[str] = set()
    for c in log:
        act = c.get("action") or ""
        if act in seen:
            continue
        seen.add(act)
        if act.startswith("FIX_") or act.startswith("CLEANUP") or act.startswith("DELETE"):
            meaning = "Sheet-data repair: a column, enum or row was corrected after review."
        elif act in ("PROPOSAL_SUBMITTED",):
            meaning = "A feature proposal was filed (see `docs/36-prd-feature-proposals.md`)."
        elif act in ("RULE_ENGINE_GAP_FILL",):
            meaning = "Requirements added from the rule-engine review (`rule-engine-gap-fill@script`)."
        elif act in ("MOVE_FORWARD",):
            meaning = "A requirement was pulled into an earlier release."
        elif act in ("REGENERATE", "STEP8_IMPORT", "REFRESH_COUNTS", "BACKFILL_PROVENANCE"):
            meaning = "Bulk regeneration / import of the workbook."
        elif act in ("CLOSE_ANSWERED_OPEN_QUESTIONS",):
            meaning = "Answers were copied back into `docs/37-prd-open-questions.md`."
        else:
            meaning = "Workbook maintenance."
        out.append(f"- `{act}` — {meaning}")

    out.append("\n## 2. Backlog audit\n")
    out.append(f"Last run: `{audit.get('run_at', 'unknown')}` "
               f"({audit.get('errors', sum(1 for f in findings if f['severity'] == 'ERROR'))} error, "
               f"{audit.get('warnings', sum(1 for f in findings if f['severity'] == 'WARN'))} warnings).\n")
    out.append("| Severity | Sheet | Row | Rule | Detail |")
    out.append("|---|---|---|---|---|")
    for f in findings:
        out.append("| **{sev}** | {sheet} | {row} | {rule} | {detail} |".format(
            sev=f.get("severity"), sheet=md_cell(f.get("sheet")), row=md_cell(f.get("row")),
            rule=md_cell(f.get("rule")), detail=md_cell(f.get("detail")),
        ))

    out.append("\n### 2.1 What each finding means for us\n")
    out.append("- **`BRG-28` is still a placeholder** (`broker server time drift detection`). It "
               "has no release in the workbook and no contract surface; either define it or delete "
               "it before Phase 1 contract freeze (`docs/99 §12`). Tracked in "
               "`docs/08-trading-bridge.md` open items.")
    out.append("- **`Tool not in Integration Map` warnings** are documentation drift inside the "
               "PRD itself (PostgreSQL, Redis, Prometheus, Grafana, Loki, OpenTelemetry are "
               "self-hosted platform pieces rather than signup dependencies). `docs/34-tooling-registry.md` "
               "§3.2 lists them as platform infrastructure; no action needed beyond keeping the two "
               "sheets in step.")

    out.append("\n## 3. Workbook vocabularies\n")
    out.append("These are the PRD's own allowed values; module docs and contracts must use exactly "
               "these spellings.\n")
    for section, values in vocab.items():
        out.append(f"**{section}:** " + ", ".join(f"`{v}`" for v in values if v) + "\n")
    return "\n".join(out) + "\n"


BUILDERS = {
    "36-prd-feature-proposals.md": build_proposals,
    "37-prd-open-questions.md": build_open_questions,
    "37a-stakeholder-questions-for-funderblu.md": build_stakeholder_handoff,
    "38-prd-out-of-scope.md": build_out_of_scope,
    "39-prd-change-log.md": build_change_log,
}


def main() -> int:
    check = "--check" in sys.argv
    data = json.loads(SRC.read_text())
    stale: list[str] = []
    for name, builder in BUILDERS.items():
        text = builder(data)
        path = DOCS / name
        if check:
            if not path.is_file() or path.read_text() != text:
                stale.append(name)
            continue
        path.write_text(text)
        print(f"wrote docs/{name} ({len(text.splitlines())} lines)")
    if check:
        if stale:
            print("stale: " + ", ".join(stale))
            return 1
        print("OK: generated registers match scripts/prd-workbook.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
