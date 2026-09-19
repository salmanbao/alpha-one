// Builds:
//  1. docs/prop-firm-trading-bridge.md  — full doc with inline mermaid blocks
//  2. site/report.html                  — self-contained HTML (inline SVG diagrams, pre-highlighted code)
const fs = require('fs');
const path = require('path');
const { Marked } = require('marked');
const hljs = require('highlight.js');

const ROOT = path.resolve(__dirname, '..');
const SRC = path.join(ROOT, 'docs', 'src');
const DIAGS = path.join(ROOT, 'diagrams');
const RENDERED = path.join(ROOT, 'rendered');

const sectionOrder = [
  '00-title', '01-executive-summary', '02-domain', '03-integration-targets',
  '04-architecture', '05-bridge-protocol', '06-rules-engine',
  '07-consistency-reliability', '08-security', '09-scalability-performance',
  '10-language-assignment', '11-tech-choices', '12-operations-observability',
  '13-testing-simulation', '14-roadmap-cost-risk', '15-glossary-references',
];

// ---------- 1. assemble markdown (mermaid inline) ----------
let md = '';
for (const name of sectionOrder) {
  let text = fs.readFileSync(path.join(SRC, name + '.md'), 'utf8').trim() + '\n\n';
  text = text.replace(/\{\{DIAG:([\w-]+)\}\}/g, (_, d) => {
    const src = fs.readFileSync(path.join(DIAGS, d + '.mmd'), 'utf8').trim();
    return '```mermaid\n' + src + '\n```\n\n*« ' + d.replace(/-/g, ' ') + ' »*\n';
  });
  md += text;
}
fs.writeFileSync(path.join(ROOT, 'docs', 'prop-firm-trading-bridge.md'), md);
console.log('markdown written:', md.length, 'chars');

// ---------- 2. HTML ----------
const svgBySource = new Map();
for (const f of fs.readdirSync(DIAGS).filter(f => f.endsWith('.mmd')).sort()) {
  const src = fs.readFileSync(path.join(DIAGS, f), 'utf8').trim();
  const svg = fs.readFileSync(path.join(RENDERED, f.replace('.mmd', '.svg')), 'utf8')
    .replace(/^<\?xml[^>]*\?>\s*/m, '');
  svgBySource.set(src, svg);
}

// Replace mermaid blocks with index placeholders that survive markdown parsing
const diagOrder = []; // {src, name}
let mdHtml = md.replace(/```mermaid\n([\s\S]*?)\n```\n\n\*«([^»]*)»\*/g,
  (m, src, name) => { diagOrder.push({ src, name }); return '@@DIAG_' + (diagOrder.length - 1) + '@@'; });
console.log('mermaid blocks found:', diagOrder.length);

function codeHtml(token) {
  const raw = token.text || token;
  let lang = (token.lang || '').trim();
  let code = raw.replace(/\n$/, '');
  if (lang === 'jsonc') { code = code.replace(/^\s*\/\/[^\n]*$/gm, ''); lang = 'json'; }
  if (lang === 'mql5' || lang === 'mql') lang = 'cpp';
  if (lang && hljs.getLanguage(lang)) {
    try { return hljs.highlight(code, { language: lang }).value; } catch (e) { }
  }
  try { return hljs.highlightAuto(code).value; } catch (e) { return code; }
}

const marked = new Marked();
marked.use({
  renderer: {
    heading(token) {
      const inline = this.parser.parseInline(token.tokens);
      const slug = token.raw.replace(/^#+\s*/, '').toLowerCase()
        .replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '-');
      return `<h${token.depth} id="${slug}">${inline}</h${token.depth}>\n`;
    },
    code(token) {
      const html = codeHtml(token);
      const lang = (token.lang || '').trim();
      return '<pre><code class="hljs language-' + (lang || 'plaintext') + '">' + html + '</code></pre>\n';
    },
  },
});

let html = marked.parse(mdHtml);

// wrap the TOC list for styling
html = html.replace(/(<h2[^>]*>[^<]*Table of Contents[^<]*<\/h2>)\s*<ul>([\s\S]*?)<\/ul>/,
  '$1\n<div class="toc-list"><ul>$2</ul></div>');

let n = 0;
html = html.replace(/@@DIAG_(\d+)@@/g, (m, i) => {
  const d = diagOrder[Number(i)];
  const svg = svgBySource.get(d.src.trim());
  if (!svg) throw new Error('no svg for: ' + d.src.trim().slice(0, 60));
  n++;
  return '<figure class="diagram">' + svg +
    '<figcaption>' + d.name.replace(/-/g, ' ') + '</figcaption></figure>';
});
console.log('diagrams inlined:', n);

// highlight.js github-dark css (inline)
const hlCss = fs.readFileSync(path.join(ROOT, 'node_modules', 'highlight.js', 'styles', 'github-dark.css'), 'utf8');

const page = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prop Firm Bridge — A–Z Architecture &amp; Implementation</title>
<style>
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;--code:#151b23}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:32px 24px 96px}
header.hero{border-bottom:1px solid var(--border);padding:8px 0 20px;margin-bottom:8px}
header.hero h1{font-size:29px;line-height:1.25;margin:0 0 10px}
header.hero p.sub{color:var(--muted);font-size:15px;margin:4px 0}
nav.toc{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px 22px;margin:24px 0;font-size:14.5px;columns:2;column-gap:40px}
nav.toc a{color:var(--accent);text-decoration:none}
nav.toc a:hover{text-decoration:underline}
nav.toc ol{margin:6px 0;padding-left:22px}
h2{font-size:24px;margin:52px 0 14px;padding-top:18px;border-top:1px solid var(--border)}
h3{font-size:19px;margin:32px 0 10px}
h4{font-size:16.5px;margin:24px 0 8px}
a{color:var(--accent)}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;display:block;overflow-x:auto;max-width:100%}
th,td{border:1px solid var(--border);padding:8px 10px;text-align:left;vertical-align:top}
th{background:var(--panel)}
tr:nth-child(even) td{background:rgba(255,255,255,.02)}
code{background:var(--code);border:1px solid var(--border);border-radius:5px;padding:1.5px 5px;font:13px/1.5 ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace}
pre{background:var(--code);border:1px solid var(--border);border-radius:10px;padding:16px;overflow-x:auto;line-height:1.55}
pre code{background:none;border:none;padding:0;font-size:13px}
blockquote{border-left:3px solid var(--accent);margin:16px 0;padding:6px 16px;color:var(--muted);background:var(--panel);border-radius:0 8px 8px 0}
figure.diagram{margin:26px 0;background:#fff;border:1px solid var(--border);border-radius:12px;padding:18px;overflow-x:auto}
figure.diagram svg{max-width:100%;height:auto;display:block;margin:0 auto}
figure.diagram figcaption{color:#57606a;font-size:13px;text-align:center;margin-top:10px;font-style:italic}
hr{border:none;border-top:1px solid var(--border);margin:40px 0}
ul,ol{padding-left:26px}
li{margin:4px 0}
strong{color:#fff}
[id]{scroll-margin-top:16px}
/* wrap the TOC list: it's inside a <ul> from markdown; style via the first nav-ish container */
ul:has(> li > a[href^="#1-"]) , .toc-list{columns:2;column-gap:40px;font-size:14.5px}
.toc-list{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px 22px;margin:24px 0}
.toc-list a{color:var(--accent);text-decoration:none}
</style>
<style>${hlCss}</style>
</head><body><div class="wrap">
${html}
</div></body></html>`;

fs.mkdirSync(path.join(ROOT, 'site'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'site', 'report.html'), page);
console.log('html written:', page.length, 'chars');
