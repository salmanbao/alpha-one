#!/usr/bin/env python3
"""Build the Alpha One static documentation site.

Renders the project's markdown docs into a self-contained, interlinked HTML
site with a grouped sidebar navigation, prev/next page links, and rewritten
internal cross-links. No third-party dependencies (stdlib only); the built-in
renderer covers the markdown subset these docs actually use:

  * ATX headings (with slugged anchors)
  * fenced code blocks (``` with optional language tag)
  * GFM pipe tables (with :---: alignment)
  * blockquotes, horizontal rules
  * nested ordered/unordered lists (with continuation lines)
  * inline code, **bold**, *italic*, ~~strikethrough~~, links, images

Document set (rendered in sidebar order):

    README.md                ->  index.html
    docs/*.md                ->  docs/<name>.html
    contracts/README.md      ->  contracts/index.html
    contracts/api/*.md       ->  contracts/api/<name>.html

Interlinking: relative links to rendered pages are rewritten to site URLs
(fragment preserved); links to any other repo file (yaml, sql, png, ...) are
mirrored into the output tree so nothing 404s; links to directories get an
auto-generated index.html page (a browsable file/directory listing) for that
directory, recursively for its subdirectories. After the build, every href
in the generated pages is verified to resolve.

Usage:
    python3 scripts/build_docs_site.py [--root PATH] [--out PATH] [--clean]

Output goes to <root>/docs-site by default. The site is a build artifact:
open docs-site/index.html directly or serve it (python3 -m http.server).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import urllib.parse
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

GENERATOR = "scripts/build_docs_site.py"
MARKER = ".docs-site.json"

# ---------------------------------------------------------------------------
# Doc discovery
# ---------------------------------------------------------------------------


@dataclass
class DocSpec:
    site_path: str  # posix path of the HTML file relative to the output root
    src: Path  # absolute source markdown path
    group: str  # sidebar group name
    title: str  # sidebar label / page title


def _first_heading(src: Path) -> str:
    try:
        for line in src.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^ {0,3}#{1,6}\s+(.*\S)", line)
            if m:
                return m.group(1).strip()
    except OSError:
        pass
    return ""


def _prettify(name: str) -> str:
    stem = re.sub(r"\.md$", "", name)
    stem = re.sub(r"^\d{2}-", "", stem)
    return re.sub(r"[-_]+", " ", stem).strip().title() or name


def _api_label(src: Path, heading: str) -> str:
    if heading:
        m = re.search(r"\(([A-Z]{2,4}(?:/[A-Z]{2,4})*)\)\s*$", heading)
        if m:
            return m.group(1)
        return re.sub(r"\s+(API )?Contract$", "", heading, flags=re.I).strip() or _prettify(src.name)
    return _prettify(src.name)


# Which PRD domain each module doc belongs to (docs/00 §3; the PRD's own
# Domains & Modules sheet). Keeps the sidebar in product order rather than
# file order, so a reader follows D1 → D5 like the PRD does.
MODULE_DOC_DOMAIN = {
    "02": "D4", "03": "D4", "04": "D4", "05": "D4", "06": "D4", "21": "D4",
    "07": "D1", "08": "D1", "09": "D1", "10": "D1", "11": "D1",
    "12": "D2", "13": "D2", "14": "D2", "15": "D2", "16": "D2", "26": "D2",
    "17": "D3", "18": "D3", "19": "D3", "20": "D3", "25": "D3",
    "22": "D5", "23": "D5", "24": "D5", "27": "D5",
}
DOMAIN_TITLES = {
    "D1": "D1 · Core Trading Engine (BRG · EVL · LCC · PAY · RSK)",
    "D2": "D2 · Trader Experience (TD · CHK · KYC · NOT · DOC · EDU · JRN · MOB · CHT)",
    "D3": "D3 · Tenant Operations (ADM · SUP · ANA · CRM · MIG)",
    "D4": "D4 · Platform Infrastructure (AUTH · TEN · EVT · GW · LED · AUD · OPS · CON)",
    "D5": "D5 · Ecosystem & Growth (AFF · CMS · CMP · BIL · SDK · DVP · PLT · CS · TRD)",
}


def _doc_group(name: str) -> str:
    m = re.match(r"^(\d{2})-", name)
    if not m:
        return "Documentation"
    num = m.group(1)
    if num in ("00", "01"):
        return "Start here"
    if num in MODULE_DOC_DOMAIN:
        return DOMAIN_TITLES[MODULE_DOC_DOMAIN[num]]
    n = int(num)
    if n <= 35:
        return "Cross-cutting (28–35)"
    if n <= 40:
        return "PRD registers (36–40)"
    if n <= 47:
        return "Design decisions (41–47)"
    return "Development plan"


def collect_docs(root: Path) -> list[DocSpec]:
    docs: list[DocSpec] = []

    def add(src: Path, group: str, label: str | None = None):
        site_path = src.relative_to(root).as_posix()
        assert site_path.endswith(".md")
        site_path = site_path[:-3] + ".html"
        if site_path == "README.html" or site_path.endswith("/README.html"):
            parent, _, _ = site_path.rpartition("/")
            site_path = f"{parent}/index.html" if parent else "index.html"
        heading = _first_heading(src)
        if label is None:
            label = _api_label(src, heading) if src.parent.name == "api" else (
                heading or _prettify(src.name))
        docs.append(DocSpec(site_path=site_path, src=src, group=group, title=label))

    readme = root / "README.md"
    if readme.is_file():
        add(readme, "Overview", label="Overview")

    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for src in sorted(docs_dir.glob("*.md")):
            add(src, _doc_group(src.name))

    contracts_readme = root / "contracts" / "README.md"
    if contracts_readme.is_file():
        add(contracts_readme, "Contracts", label="Contracts pack")

    api_dir = root / "contracts" / "api"
    if api_dir.is_dir():
        for src in sorted(api_dir.glob("*.md")):
            add(src, "API contracts")

    return docs


# ---------------------------------------------------------------------------
# Site model (link rewriting + asset mirroring)
# ---------------------------------------------------------------------------


class Site:
    def __init__(self, root: Path, out: Path, docs: list[DocSpec]):
        self.root = root
        self.out = out
        self.md_map: dict[Path, str] = {d.src.resolve(): d.site_path for d in docs}
        self.asset_map: dict[Path, Path] = {}
        self.linked_dirs: set[Path] = set()
        self.warnings: list[str] = []

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def rewrite(self, src_file: Path, page_site_dir: Path, target: str) -> str:
        """Rewrite a raw link target for the rendered site.

        Returns the new href; unresolvable/external targets are returned
        unchanged (with a warning when a repo file is clearly missing).
        """
        target = target.strip()
        if (
            not target
            or re.match(r"^[a-z][a-z0-9+.\-]*:", target, re.I)  # http:, mailto:, ...
            or target.startswith(("#", "//", "/"))
        ):
            return target

        path_part, _, frag = target.partition("#")
        frag = f"#{frag}" if frag else ""
        path_part = urllib.parse.unquote(path_part)
        if not path_part:
            return target

        dest = (src_file.parent / path_part).resolve()

        if dest.is_dir():
            readme_key = (dest / "README.md").resolve()
            if readme_key in self.md_map:
                return rel_url(page_site_dir, Path(self.md_map[readme_key])) + frag
            try:
                dest.relative_to(self.root)
            except ValueError:
                self.warn(f"{src_file.name}: directory link escapes the repo root: {target}")
                return target
            # No rendered README: generate a directory index page for it.
            self.linked_dirs.add(dest)
            dir_url = path_part if path_part.endswith("/") else path_part + "/index.html"
            return dir_url + frag
        elif not dest.exists():
            # Tolerate a trailing ".md" vs ".html" mismatch in the source.
            alt = dest.with_suffix(".md") if dest.suffix != ".md" else dest
            if alt.exists():
                dest = alt
            else:
                self.warn(f"{src_file.name}: unresolved link '{target}'")
                return target

        if dest.suffix.lower() == ".md":
            if dest in self.md_map:
                return rel_url(page_site_dir, Path(self.md_map[dest])) + frag
            self.warn(f"{src_file.name}: link to md file outside the rendered set: {target}")
            return target

        # Non-markdown file: mirror it into the output tree (repo-relative path).
        try:
            repo_rel = dest.relative_to(self.root)
        except ValueError:
            self.warn(f"{src_file.name}: link escapes the repo root: {target}")
            return target
        self.asset_map[dest] = repo_rel
        return rel_url(page_site_dir, repo_rel) + frag


def rel_url(page_site_dir: str | Path, target_site_path: str | Path) -> str:
    """Site-relative URL from a page's directory to a site file."""
    pdir = Path(page_site_dir)
    pdir = pdir if pdir != Path(".") else Path("")
    return os.path.relpath(str(target_site_path), start=str(pdir))


# ---------------------------------------------------------------------------
# Markdown rendering (the subset the docs use)
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([A-Za-z0-9_+\-]*)")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})\s+(.*\S)\s*#*\s*$")
HR_RE = re.compile(r"^ {0,3}((?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
LI_RE = re.compile(r"^(\s*)([-*+]|\d{1,3}[.)])\s+(.*)$")
TABLE_SEP_CELL = re.compile(r"^:?-+:?$")
BLOCKQUOTE_RE = re.compile(r"^ {0,3}>")
BSLASH_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!~|<>])")
CODE_RE = re.compile(r"(`+)(.+?)\1", re.S)
IMG_RE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")


def slugify(text: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    s = re.sub(r"[`*_~]", "", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


@dataclass
class RenderCtx:
    site: Site
    src_file: Path
    page_site_dir: str  # e.g. "docs" or "contracts/api"
    used_slugs: set[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.used_slugs is None:
            self.used_slugs = set()

    def slug(self, text: str) -> str:
        base = slugify(text)
        slug = base
        n = 2
        while slug in self.used_slugs:
            slug = f"{base}-{n}"
            n += 1
        self.used_slugs.add(slug)
        return slug

    def inline(self, text: str) -> str:
        return render_inline(text, self)


def render_inline(text: str, ctx: RenderCtx) -> str:
    stashed: list[tuple[str, str]] = []

    def stash(kind: str, value: str) -> str:
        stashed.append((kind, value))
        return f"\x00{len(stashed) - 1}\x00"

    # 1. protect backslash escapes and code spans
    text = BSLASH_RE.sub(lambda m: stash("lit", m.group(1)), text)
    text = CODE_RE.sub(lambda m: stash("code", m.group(2)), text)
    # 2. escape everything else
    text = html.escape(text, quote=False)
    # 3. images, then links
    text = IMG_RE.sub(
        lambda m: f'<img src="{ctx.site.rewrite(ctx.src_file, ctx.page_site_dir, m.group(2))}" '
        f'alt="{html.escape(m.group(1), quote=True)}" loading="lazy">',
        text,
    )
    text = LINK_RE.sub(
        lambda m: f'<a href="{ctx.site.rewrite(ctx.src_file, ctx.page_site_dir, m.group(2))}">'
        f"{m.group(1)}</a>",
        text,
    )
    # 4. emphasis (bold before italic; underscores left alone — the docs use
    #    _ in identifiers, and all emphasis in the corpus uses asterisks)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"~~([^~\n]+)~~", r"<del>\1</del>", text)
    # 5. restore protected spans
    def restore(m: re.Match) -> str:
        kind, value = stashed[int(m.group(1))]
        return f"<code>{html.escape(value)}</code>" if kind == "code" else html.escape(value)

    return re.sub(r"\x00(\d+)\x00", restore, text)


def split_row(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    s = s.replace("\\|", "\x01")
    return [c.replace("\x01", "|").strip() for c in s.split("|")]


def _align(cell: str) -> str:
    left, right = cell.startswith(":"), cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    if left:
        return "left"
    return ""


def _is_table_start(lines: list[str], i: int) -> bool:
    if i + 1 >= len(lines):
        return False
    if not lines[i].strip().startswith("|"):
        return False
    sep = lines[i + 1].strip()
    if not sep.startswith("|") or sep.count("|") < 2:
        return False
    cells = split_row(sep)
    return bool(cells) and all(TABLE_SEP_CELL.match(c) for c in cells)


def _render_table(header: list[str], aligns: list[str], rows: list[list[str]], ctx: RenderCtx) -> str:
    def style(idx: int) -> str:
        a = aligns[idx] if idx < len(aligns) else ""
        return f' style="text-align:{a}"' if a else ""

    thead = "".join(
        f"<th{style(i)}>{ctx.inline(c)}</th>" for i, c in enumerate(header))
    body = []
    for row in rows:
        tds = "".join(
            f"<td{style(i)}>{ctx.inline(row[i] if i < len(row) else '')}</td>"
            for i in range(len(header)))
        body.append(f"<tr>{tds}</tr>")
    return (
        '<div class="tablewrap"><table><thead><tr>'
        f"{thead}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def _render_items(items: list[list], start: int, indent: int, ctx: RenderCtx) -> tuple[str, int]:
    tag = "ol" if items[start][1] else "ul"
    start_attr = ""
    if items[start][1] and items[start][2] not in (None, 1):
        start_attr = f' start="{items[start][2]}"'
    parts = [f"<{tag}{start_attr}>"]
    i = start
    while i < len(items):
        item_indent, ordered, start_num, text = items[i]
        if item_indent < indent:
            break
        parts.append(f"<li>{ctx.inline(text)}")
        i += 1
        if i < len(items) and items[i][0] > indent:
            child, i = _render_items(items, i, items[i][0], ctx)
            parts.append(child)
        parts.append("</li>")
    parts.append(f"</{tag}>")
    return "".join(parts), i


def _indent_width(line: str) -> int:
    e = line.expandtabs(4)
    return len(e) - len(e.lstrip(" "))


def _render_list(lines: list[str], i: int, ctx: RenderCtx) -> tuple[str, int]:
    items: list[list] = []
    m0 = LI_RE.match(lines[i])
    first_indent = _indent_width(lines[i])
    while i < len(lines):
        cur = lines[i]
        m = LI_RE.match(cur)
        if m:
            ind = _indent_width(cur)
            if ind < first_indent:
                break
            marker = m.group(2)
            ordered = marker[0].isdigit()
            start_num = int(re.match(r"\d+", marker).group()) if ordered else None
            items.append([ind, ordered, start_num, m.group(3)])
            i += 1
        elif not cur.strip():
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and LI_RE.match(lines[j]) and _indent_width(lines[j]) >= first_indent:
                i = j  # blank line inside the list
                continue
            break
        else:
            if items and _indent_width(cur) > first_indent:
                items[-1][3] += " " + cur.strip()  # wrapped continuation line
                i += 1
            else:
                break
    html_out, _ = _render_items(items, 0, first_indent, ctx)
    return html_out, i


def render_markdown(text: str, ctx: RenderCtx) -> str:
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    i, n = 0, len(lines)

    def flush_para() -> None:
        if para:
            out.append(f"<p>{ctx.inline(' '.join(para))}</p>")
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        m = FENCE_RE.match(line)
        if m:
            flush_para()
            fence_char = m.group(1)[0]
            fence_len = len(m.group(1))
            lang = m.group(2)
            buf: list[str] = []
            i += 1
            while i < n and not (
                lines[i].strip().startswith(fence_char * fence_len)
                and set(lines[i].strip()) <= {fence_char}
            ):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence (or run past EOF)
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
            continue

        hm = HEADING_RE.match(line)
        if hm:
            flush_para()
            level = len(hm.group(1))
            heading = hm.group(2)
            out.append(f'<h{level} id="{ctx.slug(heading)}">{ctx.inline(heading)}</h{level}>')
            i += 1
            continue

        if HR_RE.match(line):
            flush_para()
            out.append("<hr>")
            i += 1
            continue

        if BLOCKQUOTE_RE.match(line):
            flush_para()
            buf = []
            while i < n and BLOCKQUOTE_RE.match(lines[i]):
                buf.append(re.sub(r"^ {0,3}>\s?", "", lines[i]))
                i += 1
            out.append(f"<blockquote>{render_markdown(chr(10).join(buf), ctx)}</blockquote>")
            continue

        if _is_table_start(lines, i):
            flush_para()
            header = split_row(lines[i])
            aligns = [_align(c) for c in split_row(lines[i + 1])]
            i += 2
            rows = []
            while i < n and lines[i].strip().startswith("|") and lines[i].strip() != "|":
                rows.append(split_row(lines[i]))
                i += 1
            out.append(_render_table(header, aligns, rows, ctx))
            continue

        lm = LI_RE.match(line)
        if lm and _indent_width(line) <= 3:
            flush_para()
            list_html, i = _render_list(lines, i, ctx)
            out.append(list_html)
            continue

        para.append(stripped)
        i += 1

    flush_para()
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Page template
# ---------------------------------------------------------------------------

CSS = """
:root {
  --bg: #ffffff; --fg: #1f2328; --muted: #656d76; --border: #d0d7de;
  --accent: #0969da; --accent-soft: #ddf4ff; --code-bg: #f6f8fa;
  --stripe: #f8fafc; --sidebar-w: 292px; --header-h: 56px;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --fg: #e6edf3; --muted: #8b949e; --border: #30363d;
    --accent: #58a6ff; --accent-soft: #1f2a3d; --code-bg: #161b22; --stripe: #12161d;
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.skip { position: absolute; left: -9999px; }
.skip:focus { left: 12px; top: 8px; z-index: 99; padding: 6px 12px; background: var(--accent-soft); border-radius: 6px; }

.topbar {
  position: fixed; inset: 0 0 auto 0; height: var(--header-h); z-index: 50;
  display: flex; align-items: center; gap: 14px; padding: 0 20px;
  background: var(--bg); border-bottom: 1px solid var(--border);
}
.brand { font-weight: 650; font-size: 17px; color: var(--fg); }
.brand:hover { text-decoration: none; }
.brand span { color: var(--muted); font-weight: 500; }
.crumb { margin-left: auto; color: var(--muted); font-size: 13px; }
#nav-toggle {
  display: none; border: 1px solid var(--border); background: var(--bg); color: var(--fg);
  border-radius: 6px; font-size: 18px; line-height: 1; padding: 6px 10px; cursor: pointer;
}

#sidebar {
  position: fixed; top: var(--header-h); bottom: 0; left: 0; width: var(--sidebar-w);
  overflow-y: auto; padding: 20px 14px 48px; background: var(--bg);
  border-right: 1px solid var(--border);
}
.nav-group { margin-bottom: 22px; }
.nav-group-title {
  font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
  color: var(--muted); margin: 0 8px 8px;
}
.nav-group a {
  display: block; padding: 5px 10px; border-radius: 6px;
  color: var(--fg); font-size: 14px; line-height: 1.45;
}
.nav-group a:hover { background: var(--code-bg); text-decoration: none; }
.nav-search { margin: 0 8px 14px; }
.nav-search input {
  width: 100%; padding: 6px 9px; font: inherit; font-size: 13px; color: var(--fg);
  background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px;
}
.nav-group-title .count { color: var(--muted); font-weight: 400; }
#toc {
  background: var(--stripe); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 14px; margin: 0 0 26px; font-size: 14px;
}
#toc summary { cursor: pointer; font-weight: 600; }
#toc ul { margin: 8px 0 2px; padding-left: 18px; }
#toc li { margin: 2px 0; }
#toc li.toc-h3 { margin-left: 14px; list-style: circle; }
.hub { margin: 0 0 34px; }
.hub h2 { margin-top: 30px; }
.hub-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.hub-card {
  display: block; padding: 12px 14px; border: 1px solid var(--border);
  border-radius: 8px; background: var(--stripe); color: var(--fg);
}
.hub-card:hover { border-color: var(--accent); text-decoration: none; }
.hub-card b { color: var(--accent); display: block; margin-bottom: 4px; }
.hub-card span { color: var(--muted); font-size: 13px; }
.hub-stats { display: flex; flex-wrap: wrap; gap: 10px; margin: 14px 0 4px; padding: 0; list-style: none; }
.hub-stats li {
  border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px;
  font-size: 13px; color: var(--muted);
}
.hub-stats b { color: var(--fg); }
.hub-domains { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; }
.hub-domain { border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; }
.hub-domain h3 { margin: 0 0 8px; font-size: 15px; }
.hub-domain ul { margin: 0; padding-left: 18px; }
.hub-divider { margin: 40px 0 26px; border: 0; border-top: 1px solid var(--border); }
.nav-group a.active { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
#scrim { display: none; }

#content { margin-left: var(--sidebar-w); padding: 36px 48px 80px; }
article, .pager, .page-footer { max-width: 860px; }

article h1 { font-size: 2em; margin: 0 0 .6em; padding-bottom: .3em; border-bottom: 1px solid var(--border); }
article h2 { font-size: 1.5em; margin: 1.8em 0 .6em; padding-bottom: .25em; border-bottom: 1px solid var(--border); }
article h3 { font-size: 1.2em; margin: 1.5em 0 .5em; }
article h4, article h5, article h6 { margin: 1.3em 0 .5em; }
article :is(h1,h2,h3,h4,h5,h6) { scroll-margin-top: calc(var(--header-h) + 20px); }
article p { margin: .8em 0; }
article > :first-child { margin-top: 0; }
article ul, article ol { padding-left: 1.6em; margin: .8em 0; }
article li { margin: .25em 0; }
article hr { border: 0; border-top: 1px solid var(--border); margin: 2em 0; }
article blockquote {
  margin: 1em 0; padding: 10px 16px; border-left: 4px solid var(--accent);
  background: var(--code-bg); border-radius: 0 8px 8px 0; color: var(--muted);
}
article blockquote p { margin: .4em 0; }
code {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: .88em; background: var(--code-bg); border: 1px solid var(--border);
  border-radius: 6px; padding: .1em .35em;
}
pre {
  background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px;
  padding: 16px; overflow-x: auto; line-height: 1.5;
}
pre code { background: none; border: 0; padding: 0; font-size: .85em; }
.tablewrap { overflow-x: auto; margin: 16px 0; }
table { border-collapse: collapse; width: 100%; font-size: .95em; }
th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; vertical-align: top; }
th { background: var(--code-bg); font-weight: 650; }
tbody tr:nth-child(even) { background: var(--stripe); }
img { max-width: 100%; }
.dir-note { color: var(--muted); font-size: 14px; }
ul.dirlist { list-style: none; padding: 0; margin: 16px 0; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
ul.dirlist li { border-bottom: 1px solid var(--border); font-size: 14px; }
ul.dirlist li:last-child { border-bottom: 0; }
ul.dirlist li a, ul.dirlist li code { display: block; padding: 8px 14px; color: var(--fg); }
ul.dirlist li a:hover { background: var(--code-bg); text-decoration: none; }
ul.dirlist li.dir a { font-weight: 650; }

.pager { display: flex; gap: 16px; margin-top: 48px; }
.pager > * { flex: 1; }
.pager a { display: block; border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; }
.pager a:hover { text-decoration: none; border-color: var(--accent); }
.pager .dir { display: block; font-size: 12px; letter-spacing: .05em; text-transform: uppercase; color: var(--muted); }
.pager .label { display: block; font-weight: 650; margin-top: 2px; color: var(--fg); }
.pager .next { text-align: right; }
.page-footer {
  margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 13px;
}

@media (max-width: 960px) {
  #sidebar { transform: translateX(-100%); transition: transform .2s ease; z-index: 45; box-shadow: 0 0 32px rgba(0,0,0,.25); }
  body.nav-open #sidebar { transform: none; }
  #nav-toggle { display: inline-flex; }
  .crumb { display: none; }
  #content { margin-left: 0; padding: 24px 18px 64px; }
  #scrim { display: block; position: fixed; inset: var(--header-h) 0 0 0; background: rgba(0,0,0,.4); opacity: 0; pointer-events: none; transition: opacity .2s; z-index: 40; }
  body.nav-open #scrim { opacity: 1; pointer-events: auto; }
}
"""

JS = """
(function () {
  var btn = document.getElementById('nav-toggle');
  var scrim = document.getElementById('scrim');
  function close() { document.body.classList.remove('nav-open'); }
  if (btn) btn.addEventListener('click', function () {
    document.body.classList.toggle('nav-open');
  });
  if (scrim) scrim.addEventListener('click', close);
  document.querySelectorAll('#sidebar a').forEach(function (a) {
    a.addEventListener('click', close);
  });
  var filter = document.getElementById('nav-filter');
  if (filter) filter.addEventListener('input', function () {
    var q = filter.value.trim().toLowerCase();
    document.querySelectorAll('#sidebar .nav-group').forEach(function (group) {
      var shown = 0;
      group.querySelectorAll('a').forEach(function (a) {
        var hit = !q || a.textContent.toLowerCase().indexOf(q) !== -1;
        a.style.display = hit ? '' : 'none';
        if (hit) shown++;
      });
      group.style.display = shown ? '' : 'none';
    });
  });
})();
"""


GROUP_ORDER = ("Overview", "Start here", "D1 ", "D2 ", "D3 ", "D4 ", "D5 ",
               "Cross-cutting", "PRD registers", "Design decisions", "Development plan",
               "Contracts", "Contracts · API")


def _group_rank(name: str) -> tuple[int, str]:
    for i, prefix in enumerate(GROUP_ORDER):
        if name.startswith(prefix.strip()) or name == prefix:
            return (i, name)
    return (len(GROUP_ORDER), name)


def _sidebar(doc: DocSpec, docs: list[DocSpec]) -> str:
    groups: "OrderedDict[str, list[DocSpec]]" = OrderedDict()
    for d in sorted(docs, key=lambda x: x.group):
        groups.setdefault(d.group, []).append(d)
    groups = OrderedDict(sorted(groups.items(), key=lambda kv: _group_rank(kv[0])))
    parts = ['<div class="nav-search"><input id="nav-filter" type="search" '
             'placeholder="Filter docs…" aria-label="Filter documentation"></div>']
    for group, items in groups.items():
        links = []
        for d in items:
            cls = ' class="active" aria-current="page"' if d is doc else ""
            href = rel_url(Path(doc.site_path).parent, d.site_path)
            links.append(f'<a href="{href}"{cls}>{html.escape(d.title, quote=True)}</a>')
        parts.append(
            f'<div class="nav-group"><div class="nav-group-title">'
            f"{html.escape(group, quote=True)} <span class=\"count\">{len(items)}</span></div>"
            f"{''.join(links)}</div>"
        )
    return "".join(parts)


def _toc(body: str) -> str:
    """'On this page' list from the rendered body's h2/h3 headings."""
    items = []
    for m in re.finditer(r"<h([23]) id=\"([^\"]+)\"[^>]*>(.*?)</h\1>", body, re.S):
        level, anchor, text = m.group(1), m.group(2), re.sub(r"<[^>]+>", "", m.group(3))
        text = html.unescape(text).strip()
        if not text:
            continue
        cls = "toc-h3" if level == "3" else "toc-h2"
        items.append(f'<li class="{cls}"><a href="#{html.escape(anchor, quote=True)}">'
                     f"{html.escape(text, quote=True)}</a></li>")
    if len(items) < 3:
        return ""
    return ('<details id="toc" open><summary>On this page</summary>'
            f'<ul>{"".join(items)}</ul></details>')


def _pager(doc: DocSpec, docs: list[DocSpec]) -> str:
    try:
        idx = next(i for i, d in enumerate(docs) if d is doc)
    except StopIteration:  # auxiliary pages (directory indexes) have no pager
        return ""
    prev = docs[idx - 1] if idx > 0 else None
    nxt = docs[idx + 1] if idx + 1 < len(docs) else None

    def slot(label: str, d: DocSpec | None, cls: str) -> str:
        if d is None:
            return f'<div class="slot {cls}"></div>'
        href = rel_url(Path(doc.site_path).parent, d.site_path)
        return (
            f'<a class="{cls}" href="{href}"><span class="dir">{label}</span>'
            f'<span class="label">{html.escape(d.title, quote=True)}</span></a>'
        )

    if prev is None and nxt is None:
        return ""
    return f'<nav class="pager" aria-label="Adjacent pages">{slot("← Previous", prev, "prev")}{slot("Next →", nxt, "next")}</nav>'


def page_html(doc: DocSpec, body: str, docs: list[DocSpec], site: Site,
              dir_index: bool = False) -> str:
    root_href = rel_url(Path(doc.site_path).parent, "index.html")
    src_rel = doc.src.relative_to(site.root).as_posix()
    if dir_index:
        footer = (
            f"Auto-generated directory index for <code>{html.escape(src_rel, quote=True)}/</code> "
            f"by <code>{GENERATOR}</code>."
        )
    else:
        footer = (
            f"Rendered from <code>{html.escape(src_rel, quote=True)}</code> by "
            f"<code>{GENERATOR}</code>. Regenerate with <code>python3 {GENERATOR}</code>."
        )
    title = html.escape(doc.title, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="alpha-one {GENERATOR}">
<title>{title} · Alpha One Docs</title>
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="topbar">
  <button id="nav-toggle" aria-label="Toggle navigation" aria-expanded="false">☰</button>
  <a class="brand" href="{root_href}">Alpha One <span>Docs</span></a>
  <span class="crumb">{html.escape(doc.group, quote=True)} &rsaquo; {title}</span>
</header>
<div id="scrim" aria-hidden="true"></div>
<nav id="sidebar" aria-label="Documentation">{_sidebar(doc, docs)}</nav>
<main id="content">
<article>
{_toc(body)}
{body}
</article>
{_pager(doc, docs)}
<footer class="page-footer">
  {footer}
</footer>
</main>
<script>{JS}</script>
</body>
</html>
"""




# ---------------------------------------------------------------------------
# Landing hub (structured entry page)
# ---------------------------------------------------------------------------


def _readme_notes(root: Path) -> dict[str, str]:
    """Descriptions from the README doc-map table: link target -> note."""
    notes: dict[str, str] = {}
    readme = root / "README.md"
    if not readme.is_file():
        return notes
    for line in readme.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|\s*(.+?)\s*\|\s*$", line)
        if not m:
            continue
        target = m.group(2).split("#")[0].strip()
        note = re.sub(r"\s+", " ", m.group(3))
        notes[target] = note
    return notes


def _registry_stats(root: Path) -> list[tuple[str, str]]:
    """Headline numbers for the hub, from the parsed PRD workbook."""
    path = root / "scripts" / "prd-workbook.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    backlog = data.get("master_backlog", [])
    releases: dict[str, int] = {}
    for row in backlog:
        rel = row.get("release") or "unassigned"
        releases[rel] = releases.get(rel, 0) + 1
    out = [("requirements", f"{len(backlog)}")]
    for rel in ("V1.0", "V1.1", "V2.0", "V3.0"):
        if rel in releases:
            out.append((rel, str(releases[rel])))
    if "unassigned" in releases:
        out.append(("unassigned", str(releases["unassigned"])))
    for key, label in (("feature_proposals", "proposals"), ("open_questions", "open questions"),
                       ("out_of_scope", "out-of-scope items"), ("integration_map", "integrations"),
                       ("tooling_register", "tools"), ("build_vs_buy_rules", "BVR rules")):
        if isinstance(data.get(key), list):
            out.append((label, str(len(data[key]))))
    return out


def build_hub(root: Path, docs: list[DocSpec], doc: DocSpec) -> str:
    """Structured landing content placed above the README on index.html."""
    notes = _readme_notes(root)
    by_group: "OrderedDict[str, list[DocSpec]]" = OrderedDict()
    for d in sorted(docs, key=lambda x: x.site_path):
        if d.group in ("Start here",) or d.group.startswith(("D1", "D2", "D3", "D4", "D5")):
            by_group.setdefault(d.group, []).append(d)
    by_group = OrderedDict(sorted(by_group.items(),
                                  key=lambda kv: _group_rank(kv[0]) if kv[0] != "Start here" else (0, kv[0])))

    def link(d: DocSpec) -> str:
        href = rel_url(Path(doc.site_path).parent, d.site_path)
        note = notes.get(d.src.relative_to(root).as_posix(), "")
        note_html = f"<span>{html.escape(note, quote=True)}</span>" if note else ""
        return (f'<li><a href="{href}">{html.escape(d.title, quote=True)}</a> '
                f"{note_html}</li>")

    parts = ['<section class="hub">']
    parts.append("<h1>Alpha One — documentation</h1>")
    parts.append("<p>Three entry points: <b>module docs</b> (how each module is designed), "
                 "<b>PRD registers</b> (what the workbook says), and the <b>contracts pack</b> "
                 "(what the code must implement). Everything below is generated from this "
                 "repository.</p>")
    stats = _registry_stats(root)
    if stats:
        parts.append('<ul class="hub-stats">' + "".join(
            f"<li><b>{html.escape(value, quote=True)}</b> {html.escape(label, quote=True)}</li>"
            for label, value in stats) + "</ul>")

    regs = [d for d in docs if d.group.startswith(("PRD registers", "Design decisions"))]
    if regs:
        parts.append("<h2>PRD registers</h2>")
        parts.append('<div class="hub-cards">')
        for d in regs:
            href = rel_url(Path(doc.site_path).parent, d.site_path)
            note = notes.get(d.src.relative_to(root).as_posix(), "")
            parts.append(f'<a class="hub-card" href="{href}"><b>{html.escape(d.title, quote=True)}</b>'
                         f"<span>{html.escape(note, quote=True)}</span></a>")
        parts.append("</div>")

    if by_group:
        parts.append("<h2>Modules by domain</h2>")
        parts.append('<div class="hub-domains">')
        for group, items in by_group.items():
            if group == "Start here":
                continue
            parts.append(f'<div class="hub-domain"><h3>{html.escape(group, quote=True)}</h3><ul>')
            parts.extend(link(d) for d in items)
            parts.append("</ul></div>")
        parts.append("</div>")

    cross = [d for d in docs if d.group.startswith("Cross-cutting")]
    if cross:
        parts.append("<h2>Cross-cutting</h2>")
        parts.append('<div class="hub-cards">')
        for d in cross:
            href = rel_url(Path(doc.site_path).parent, d.site_path)
            note = notes.get(d.src.relative_to(root).as_posix(), "")
            parts.append(f'<a class="hub-card" href="{href}"><b>{html.escape(d.title, quote=True)}</b>'
                         f"<span>{html.escape(note, quote=True)}</span></a>")
        parts.append("</div>")

    parts.append("<h2>Contracts &amp; API</h2>")
    parts.append('<div class="hub-cards">')
    for label, rel, note in (
        ("Contracts pack", "contracts/index.html", "OpenAPI specs, data dictionary, schemas, events, errors, permissions"),
        ("API contracts (36 modules)", "contracts/api/", "Per-module HTTP contracts with scope tables"),
        ("OpenAPI specs (26 modules)", "contracts/", "Machine-readable specs and shared components"),
    ):
        href = rel_url(Path(doc.site_path).parent, rel)
        parts.append(f'<a class="hub-card" href="{href}"><b>{html.escape(label, quote=True)}</b>'
                     f"<span>{html.escape(note, quote=True)}</span></a>")
    parts.append("</div>")
    parts.append('<hr class="hub-divider">')
    parts.append("</section>")
    return "".join(parts)


def _strip_first_h1(body: str) -> str:
    return re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.S)


# ---------------------------------------------------------------------------
# Directory index pages (for links to repo directories)
# ---------------------------------------------------------------------------

MAX_DIR_DEPTH = 3


def _dir_index_body(site: Site, d: Path, rel: Path, all_dirs: set[Path]) -> str:
    try:
        subs = [s for s in sorted(d.iterdir()) if s.is_dir()]
        files = [f for f in sorted(d.iterdir()) if f.is_file() and f.name != MARKER]
    except OSError:
        subs, files = [], []

    items = []
    for s in subs:
        if s in all_dirs:
            items.append(f'<li class="dir"><a href="{html.escape(s.name, quote=True)}/">'
                         f"{html.escape(s.name, quote=True)}/</a></li>")
        else:
            items.append(f'<li class="dir"><code>{html.escape(s.name, quote=True)}/</code></li>')
    for f in files:
        key = f.resolve()
        if key in site.md_map:
            href = rel_url(rel, Path(site.md_map[key]))
            items.append(f'<li><a href="{href}">{html.escape(f.name, quote=True)}</a></li>')
        elif key in site.asset_map:
            href = rel_url(rel, site.asset_map[key])
            items.append(f'<li><a href="{href}">{html.escape(f.name, quote=True)}</a></li>')
        else:
            items.append(f'<li class="plain"><code>{html.escape(f.name, quote=True)}</code></li>')

    return (
        f"<h1>{html.escape(rel.as_posix(), quote=True)}</h1>"
        '<p class="dir-note">Auto-generated directory listing &mdash; the source directory '
        'has no rendered index document. Files without a link are not part of the rendered '
        'documentation set.</p>'
        f'<ul class="dirlist">{"".join(items) if items else "<li>(empty)</li>"}</ul>'
    )


def generate_dir_indexes(site: Site, docs: list[DocSpec], out: Path) -> int:
    """Create <dir>/index.html for every linked repo directory (and its
    subdirectories, up to MAX_DIR_DEPTH) so directory links resolve."""
    if not site.linked_dirs:
        return 0
    all_dirs = set(site.linked_dirs)
    frontier, depth = list(all_dirs), 0
    while frontier and depth < MAX_DIR_DEPTH:
        more = []
        for d in frontier:
            if not d.is_dir():
                continue
            for sub in sorted(d.iterdir()):
                if sub.is_dir() and sub not in all_dirs:
                    all_dirs.add(sub)
                    more.append(sub)
        frontier, depth = more, depth + 1

    count = 0
    for d in sorted(all_dirs):
        rel = d.relative_to(site.root)
        spec = DocSpec(site_path=f"{rel.as_posix()}/index.html", src=d,
                       group="Directory index", title=rel.as_posix())
        body = _dir_index_body(site, d, rel, all_dirs)
        page = page_html(spec, body, docs, site, dir_index=True)
        dest = out / spec.site_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")
        count += 1
    return count


# ---------------------------------------------------------------------------
# Build + verification
# ---------------------------------------------------------------------------

HREF_RE = re.compile(r'<a [^>]*href="([^"]+)"')


def verify_links(out: Path) -> list[str]:
    broken = []
    for f in sorted(out.rglob("*.html")):
        text = f.read_text(encoding="utf-8")
        for m in HREF_RE.finditer(text):
            url = html.unescape(m.group(1))
            if re.match(r"^[a-z][a-z0-9+.\-]*:", url, re.I) or url.startswith("#"):
                continue
            path_part = url.partition("#")[0]
            if not path_part:
                continue
            if not (f.parent / path_part).resolve().exists():
                broken.append(f"{f.relative_to(out)}: {url}")
    return broken


def build(root: Path, out: Path, clean: bool) -> int:
    docs = collect_docs(root)
    if not docs:
        print(f"error: no markdown docs found under {root}", file=sys.stderr)
        return 1

    site = Site(root, out, docs)
    marker = out / MARKER
    if out.exists():
        if clean or marker.is_file():
            shutil.rmtree(out)
        else:
            print(f"error: {out} exists and is not a previous build; pass --clean to overwrite",
                  file=sys.stderr)
            return 1
    out.mkdir(parents=True)

    rendered = []
    for d in docs:
        text = d.src.read_text(encoding="utf-8")
        ctx = RenderCtx(site=site, src_file=d.src, page_site_dir=Path(d.site_path).parent)
        rendered.append((d, render_markdown(text, ctx), ctx))

    readme_src = (root / "README.md").resolve()
    for d, body, ctx in rendered:
        if d.src.resolve() == readme_src:
            hub = build_hub(root, docs, d)
            body = hub + _strip_first_h1(body)
        page = page_html(d, body, docs, site)
        dest = out / d.site_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(page, encoding="utf-8")

    dir_pages = generate_dir_indexes(site, docs, out)

    for src, repo_rel in site.asset_map.items():
        dest = out / repo_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    broken = verify_links(out)

    groups = OrderedDict()
    for d in docs:
        groups.setdefault(d.group, 0)
        groups[d.group] += 1
    for w in site.warnings:
        print(f"  warning: {w}", file=sys.stderr)
    if broken:
        for b in broken:
            print(f"  broken link: {b}", file=sys.stderr)

    print("Alpha One docs site")
    print(f"  root:     {root}")
    print(f"  output:   {out}")
    print(f"  pages:    {len(docs)}  " + ", ".join(f"{g}: {c}" for g, c in groups.items()))
    print(f"  dir idx:  {dir_pages} auto-generated directory listings")
    print(f"  assets:   {len(site.asset_map)} copied")
    print(f"  warnings: {len(site.warnings)}")
    print(f"  broken links: {len(broken)}")
    if (out / "index.html").is_file():
        print(f"Open {out / 'index.html'} (or serve the directory with python3 -m http.server).")
    if broken:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    default_root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="Render the Alpha One markdown docs into a static HTML site.")
    ap.add_argument("--root", type=Path, default=default_root,
                    help=f"project root containing README.md, docs/, contracts/ (default: {default_root})")
    ap.add_argument("--out", type=Path, default=None,
                    help="output directory (default: <root>/docs-site)")
    ap.add_argument("--clean", action="store_true",
                    help="overwrite the output directory even if it is not a previous build")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    out = (args.out.resolve() if args.out else root / "docs-site")
    rc = build(root, out, args.clean)
    marker = out / MARKER
    if rc == 0 and marker.parent.exists():
        marker.write_text(json.dumps({
            "generator": GENERATOR,
            "root": str(root),
            "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, indent=2) + "\n", encoding="utf-8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
