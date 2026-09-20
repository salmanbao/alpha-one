/* Alpha One spec site — app.js (2026-09-20) */
(function () {
  "use strict";
  var DATA = null, DATA_READY = null;

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;"); }

  DATA_READY = fetch("data/site-data.json").then(function (r) { return r.json(); }).then(function (d) { DATA = d; });

  marked.use({ gfm: true, breaks: false });

  /* ---------- markdown rendering ---------- */
  function slugify(t) {
    return t.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  function renderMd(md) {
    var html = marked.parse(md);
    return html;
  }
  function postProcess(scope) {
    /* heading ids + anchor links */
    var used = {};
    $$("h1,h2,h3,h4", scope).forEach(function (h) {
      var base = slugify(h.textContent.replace(/\s*¶\s*$/, "")) || "section";
      var id = base, i = 2;
      while (used[id]) id = base + "-" + i++;
      used[id] = 1;
      h.id = id;
      var a = document.createElement("a");
      a.className = "hlink";
      a.href = currentRoute().replace(/\/+$/, "") + "/h=" + id;
      a.textContent = "¶";
      a.setAttribute("aria-label", "Link to this section");
      h.appendChild(a);
    });
    /* code blocks: tablewrap + copy */
    $$("pre", scope).forEach(function (pre) {
      if (pre.parentElement.classList.contains("codeblock")) return;
      var wrap = document.createElement("div"); wrap.className = "codeblock";
      var head = document.createElement("div"); head.className = "codehead";
      var code = pre.querySelector("code");
      var lang = "text";
      if (code) {
        var cm = code.className.match(/language-([\w+-]+)/);
        if (cm) lang = cm[1];
      }
      var fname = "";
      if (code) {
        var fm = (code.textContent || "").match(/^\s*\/\/\s*([\w./-]+\.\w{1,4})\b/);
        if (fm) fname = fm[1];
      }
      head.innerHTML = '<span class="lang"></span><span class="fname"></span><button class="copybtn" type="button">copy</button>';
      head.querySelector(".lang").textContent = lang;
      head.querySelector(".fname").textContent = fname;
      pre.parentNode.insertBefore(wrap, pre);
      wrap.appendChild(head); wrap.appendChild(pre);
      wrap.querySelector(".copybtn").addEventListener("click", function () { copyText(pre.innerText, this); });
    });
    /* tables: wrap */
    $$("table", scope).forEach(function (t) {
      if (t.parentElement.classList.contains("tablewrap")) return;
      var w = document.createElement("div"); w.className = "tablewrap";
      t.parentNode.insertBefore(w, t); w.appendChild(t);
    });
    /* links: intra-doc NN-name.md cross-refs become SPA routes; relative file refs open in a new tab */
    $$("a", scope).forEach(function (a) {
      var href = a.getAttribute("href");
      if (!href || /^https?:/.test(href) || href.charAt(0) === "#") return;
      var bare = href.replace(/^docs\//, "");
      if (/^\d{1,3}[a-z]?-[\w-]+\.md$/.test(bare)) {
        var doc = DATA.docs.filter(function (d) { return d.id === bare.replace(/\.md$/, ""); })[0];
        if (doc) { a.setAttribute("href", "#/doc/" + doc.id); return; }
      }
      if (/^\.\.\//.test(href) || /^contracts\//.test(href)) a.setAttribute("target", "_blank");
    });
    /* anchor links: copy url */
    $$(".hlink", scope).forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        var url = location.href.split("#")[0] + a.getAttribute("href");
        copyText(url, a, "✓");
      });
    });
  }
  function copyText(text, btn, doneMark) {
    var done = function () {
      if (btn.classList) { btn.textContent = doneMark || "copied ✓"; btn.classList.add("done"); }
      setTimeout(function () { btn.textContent = btn.getAttribute("data-orig") || "copy"; btn.classList.remove("done"); }, 1400);
    };
    if (!btn.getAttribute("data-orig")) btn.setAttribute("data-orig", btn.textContent);
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
  }

  /* ---------- route helpers ---------- */
  function parseHash() {
    var h = location.hash.replace(/^#\/?/, "");
    var parts = h.split("/").filter(Boolean);
    return { route: parts[0] || "home", arg: parts[1] || "", sub: parts[2] || "" };
  }
  function currentRoute() {
    return location.hash ? location.hash : "#/";
  }
  function setCrumb(t) { var c = $("#crumb"); if (c) c.textContent = t; }

  /* ---------- sidebar ---------- */
  var GROUPS = [
    ["start", "Start here"],
    ["modules", "Module specs (V1 core)"],
    ["surfaces", "Surfaces & integrations"],
    ["crosscutting", "Cross-cutting"],
    ["prd", "PRD & registers"],
    ["reviews", "Reviews & audits"],
    ["contracts", "Contract pack"],
    ["registers", "Decision registers"],
  ];
  function buildSidebar() {
    var nav = $("#sb-nav");
    nav.innerHTML = "";
    GROUPS.forEach(function (g) {
      var div = document.createElement("div"); div.className = "sb-group";
      div.innerHTML = "<h4>" + g[1] + "</h4><ol></ol>";
      var ol = div.querySelector("ol");
      if (g[0] === "contracts" || g[0] === "registers") {
        var links = g[0] === "contracts" ? [
          ["contracts", "", "Contracts — overview"],
          ["contracts", "events", "Event catalog & payloads"],
          ["contracts", "errors", "Error taxonomy"],
          ["contracts", "api", "API contracts"],
          ["contracts", "diagrams", "Diagrams"],
        ] : [
          ["registers", "", "Decisions & open questions"],
          ["registers", "d", "Design decisions D1–D" + DATA.project.stats.d_rows],
          ["registers", "prd", "PRD open questions (205)"],
          ["registers", "triage", "Triage — who answers what"],
        ];
        links.forEach(function (l) {
          var a = document.createElement("a");
          a.href = "#/" + l[0] + (l[1] ? "/" + l[1] : "");
          a.innerHTML = '<span class="t"></span>';
          a.querySelector(".t").textContent = l[2];
          ol.appendChild(a);
        });
      } else {
        DATA.docs.filter(function (d) { return d.group === g[0]; }).forEach(function (d) {
          var a = document.createElement("a");
          a.href = "#/doc/" + d.id;
          a.dataset.doc = d.id;
          a.innerHTML = '<span class="sb-num"></span><span class="t"></span>';
          a.querySelector(".sb-num").textContent = d.num;
          a.querySelector(".t").textContent = d.title;
          ol.appendChild(a);
        });
      }
      nav.appendChild(div);
    });
    /* search filter */
    var search = $("#nav-search");
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      $$("#sb-nav .sb-group a").forEach(function (a) {
        var txt = (a.textContent || "").toLowerCase();
        a.style.display = !q || txt.indexOf(q) !== -1 ? "" : "none";
      });
      $$("#sb-nav .sb-group").forEach(function (g) {
        var any = $$("a", g).some(function (a) { return a.style.display !== "none"; });
        g.style.display = any ? "" : "none";
      });
    });
  }

  /* ---------- rail (on this page) ---------- */
  function buildRail(scope) {
    var list = $("#rail-list");
    list.innerHTML = "";
    $$("h2,h3", scope).forEach(function (h) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = currentRoute().replace(/\/+$/, "") + "/h=" + h.id;
      a.textContent = h.textContent.replace(/\s*¶\s*$/, "").trim();
      if (h.tagName === "H3") li.className = "l3";
      li.appendChild(a); list.appendChild(li);
    });
  }

  /* ---------- scroll-spy + progress ---------- */
  function initScroll(scope) {
    var heads = $$("h2[id],h3[id]", scope);
    var railLinks = $$("#rail-list a");
    var sbLinks = $$("#sb-nav a[data-doc]");
    var cur = parseHash();
    var docLink = sbLinks.filter(function (a) { return a.dataset.doc === cur.arg; })[0];
    if (docLink && cur.route === "doc") docLink.classList.add("active");
    if (window._a1scroll) window.removeEventListener("scroll", window._a1scroll);
    var ticking = false;
    var onScroll = function () {
      if (ticking) return; ticking = true;
      requestAnimationFrame(function () {
        ticking = false;
        var line = 90, act = null;
        for (var i = heads.length - 1; i >= 0; i--) {
          if (heads[i].getBoundingClientRect().top - line <= 1) { act = heads[i]; break; }
        }
        railLinks.forEach(function (a) { a.classList.toggle("active", act && a.textContent === act.textContent.replace(/\s*¶\s*$/, "").trim()); });
        var doc = document.documentElement;
        var max = doc.scrollHeight - window.innerHeight;
        $("#progress").style.width = (max > 0 ? Math.min(100, window.scrollY / max * 100) : 0) + "%";
        $("#totop").classList.toggle("show", window.scrollY > 700);
      });
    };
    window._a1scroll = onScroll;
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  /* ---------- page builders ---------- */
  function pageDoc(id) {
    var d = DATA.docs.filter(function (x) { return x.id === id; })[0];
    if (!d) return pageNotFound();
    var v = $("#view");
    var idx = DATA.docs.indexOf(d);
    v.innerHTML = '<article class="doc"><div id="doc-body"></div>' +
      '<nav class="pn" id="prevnext"></nav>' +
      '<footer class="page-foot"><p>Source: <a href="' + d.file + '" target="_blank">' + esc(d.file.replace("../", "")) + "</a> · generated " + esc(DATA.generated) +
      ' · re-render after doc changes with <code>python3 site/build_site.py</code></p></footer></article>';
    var body = $("#doc-body");
    body.innerHTML = renderMd(d.content);
    postProcess(body);
    buildRail(body);
    /* prev/next */
    var pn = $("#prevnext");
    if (idx > 0) {
      var p = DATA.docs[idx - 1];
      var ap = document.createElement("a"); ap.href = "#/doc/" + p.id;
      ap.innerHTML = '<span class="pn-label">← Previous</span><span class="pn-title"></span>';
      ap.querySelector(".pn-title").textContent = p.num + " — " + p.title;
      pn.appendChild(ap);
    }
    if (idx < DATA.docs.length - 1) {
      var nx = DATA.docs[idx + 1];
      var an = document.createElement("a"); an.href = "#/doc/" + nx.id; an.style.textAlign = "right";
      an.innerHTML = '<span class="pn-label">Next →</span><span class="pn-title"></span>';
      an.querySelector(".pn-title").textContent = nx.num + " — " + nx.title;
      pn.appendChild(an);
    }
    setCrumb("Doc " + d.num + " — " + d.title);
    /* deep link to heading */
    var h = parseHash().sub;
    if (h && h.indexOf("h=") === 0) {
      var hid = h.slice(2), el = document.getElementById(hid);
      if (el) setTimeout(function () { el.scrollIntoView(); }, 30);
    }
    initScroll(v);
  }

  function pageHome() {
    var v = $("#view");
    var s = DATA.project.stats;
    v.innerHTML =
      '<header class="hero">' +
      '<p class="hero-kicker">Alpha One · platform specification</p>' +
      '<h1>Prop Firm as a Service — the complete specification</h1>' +
      '<p class="hero-sub">' + esc(DATA.project.tagline) + " — 65 spec docs, the frozen contract pack, and the decision registers. Everything a developer needs to build V1, in one place.</p>" +
      '<div class="hero-meta">' +
      '<span class="chip"><b>' + s.docs + '</b> spec docs</span>' +
      '<span class="chip"><b>' + s.v1_events + '</b> V1 events · ' + s.payloads + ' payload schemas</span>' +
      '<span class="chip"><b>' + s.api_specs + '</b> API contracts</span>' +
      '<span class="chip"><b>' + s.d_rows + '</b> design decisions (D1–D' + s.d_rows + ")</span>" +
      '<span class="chip"><b>' + s.prd_total + '</b> PRD questions</span>' +
      "</div></header>" +
      '<div class="callout info"><strong>What "frozen" means here:</strong> ' + esc(DATA.project.status.frozen) +
      " " + esc(DATA.project.status.open) + "</div>" +
      '<h2>Start here</h2><div class="cards">' +
      card("#/doc/00-executive-brief", "Executive Brief", "What we are building, the non-negotiables, the 12 ADRs in one read.") +
      card("#/doc/01-platform-architecture", "Platform Architecture", "Deployables, tech stack, ADRs, event backbone, request lifecycle.") +
      card("#/doc/99-development-phases", "Development Phases", "The task-level build plan with exit criteria — the program's operating document.") +
      card("#/contracts", "Contract Pack", "Frozen V0 contracts: events, payload schemas, error taxonomy, API specs.") +
      card("#/registers", "Decisions & Questions", "D1–D" + s.d_rows + " design decisions, the 205 PRD questions, triage by owner.") +
      card("#/contracts/diagrams", "Diagrams", "8 committed architecture diagrams (state machines, flows, build order).") +
      "</div>" +
      "<h2>Browse the specification</h2>" +
      "<div id='browse'></div>";
    var browse = $("#browse");
    GROUPS.filter(function (g) { return g[0] !== "contracts" && g[0] !== "registers"; }).forEach(function (g) {
      var docs = DATA.docs.filter(function (d) { return d.group === g[0]; });
      if (!docs.length) return;
      browse.innerHTML += "<div class='doclist' style='margin-top:14px'><h4></h4><ol></ol></div>";
      var dl = browse.lastElementChild;
      dl.querySelector("h4").textContent = g[1] + " (" + docs.length + ")";
      docs.forEach(function (d) {
        var li = document.createElement("li");
        li.innerHTML = "<a href='#/doc/" + d.id + "'><span class='n'></span><span class='t'></span></a>";
        li.querySelector(".n").textContent = d.num;
        li.querySelector(".t").textContent = d.title;
        dl.querySelector("ol").appendChild(li);
      });
    });
    setCrumb("Alpha One — Platform Specification");
    initScroll(v);
  }
  function card(href, title, sub, tag) {
    return "<a class='card' href='" + href + "'><div class='card-tag'>" + esc(tag || title.split(" ")[0]) + "</div><h3>" + esc(title) + "</h3><p>" + esc(sub) + "</p></a>";
  }

  function pageContractsHub() {
    var v = $("#view");
    v.innerHTML =
      "<h1>Contract Pack</h1>" +
      "<p>The frozen V0 contracts (<a href='#/doc/99-development-phases'>docs/99 task 0.10</a>): the machine-readable source of truth for every module. " +
      "CI gates fail the build on drift (error registry, catalog, schema, and payload gates). Generated from <code>contracts/</code> — <a href='../contracts/README.md' target='_blank'>pack README</a>.</p>" +
      "<div class='cards'>" +
      card("#/contracts/events", "Event catalog & payloads", DATA.project.stats.v1_events + " V1 catalog events (39 schemas incl. 2 risk.*) — every payload derived from its owning module doc, with the source cited.") +
      card("#/contracts/errors", "Error taxonomy", "The V1 baseline error codes (dotted domain.action) with owner-rationale resolutions + the extended post-V1 registry.") +
      card("#/contracts/api", "API contracts", DATA.project.stats.api_specs + " module API specs (endpoints, permissions, error codes). 19 are V1-surface; the rest are extended/provisional.") +
      card("#/contracts/diagrams", "Diagrams", "8 committed PNGs: state machines, purchase/payout flows, event bus, build order.") +
      "</div>" +
      "<h2>Event catalog (quick reference)</h2>" +
      "<p>Jump straight to a payload schema — each page shows the derived-from citation, consumers, and the full field table.</p>" +
      "<div id='event-quick'></div>";
    var q = $("#event-quick");
    q.innerHTML = "<div class='doclist'><ol></ol></div>";
    var ol = q.querySelector("ol");
    DATA.contracts.payloads.forEach(function (p) {
      var a = document.createElement("a");
      a.href = "#/contracts/payloads/" + encodeURIComponent(p.event);
      a.innerHTML = "<span class='n'></span><span class='t'></span>";
      a.querySelector(".n").textContent = p.v1 ? "V1" : "ext";
      a.querySelector(".t").textContent = p.event;
      ol.appendChild(a);
    });
    setCrumb("Contract pack");
    initScroll(v);
  }

  function pageCatalog() {
    var v = $("#view");
    v.innerHTML = "<article id='cat-body'></article>";
    var body = $("#cat-body");
    body.innerHTML = renderMd(DATA.contracts.catalog);
    postProcess(body);
    buildRail(body);
    setCrumb("Contracts — event catalog");
    initScroll(v);
  }

  function pagePayload(event) {
    var v = $("#view");
    var p = DATA.contracts.payloads.filter(function (x) { return x.event === decodeURIComponent(event); })[0];
    if (!p) return pageNotFound();
    var rows = p.fields.map(function (f) {
      return "<tr class='" + (f.required ? "req" : "") + "'><td><code>" + esc(f.name) + "</code></td><td>" + esc(f.type) +
        "</td><td>" + (f.required ? "required" : "optional") + "</td><td>" + esc(f.desc || "—") + "</td></tr>";
    }).join("");
    v.innerHTML =
      "<p class='schema-note'>Contract pack → <a href='#/contracts/events'>event catalog</a> → " + esc(p.event) + "</p>" +
      "<h1>" + esc(p.event) + "</h1>" +
      "<div class='hero-meta'><span class='chip'>" + (p.v1 ? "<b>V1 catalog</b>" : "extended") + " · " + esc(p.file) + "</span>" +
      (p.consumers ? "<span class='chip'>consumers: " + esc(p.consumers) + "</span>" : "") + "</div>" +
      (p.source ? "<div class='callout info'><strong>Derived from:</strong> " + esc(p.source) +
        " — field names per docs/32 DDL; money is integer minor units (docs/00 non-negotiable #3).</div>" : "") +
      "<h2>Envelope</h2><p>Every event carries the <code>EVT-03</code> envelope: <code>id</code> (ULID), <code>type</code> (const = event name), <code>version</code> (1), <code>tenant_id</code>, <code>occurred_at</code>, <code>payload</code> (below). See <a href='../contracts/events/payloads/envelope.schema.json' target='_blank'>envelope.schema.json</a>.</p>" +
      "<h2>payload fields</h2>" +
      "<table><thead><tr><th>Field</th><th>Type</th><th>Cardinality</th><th>Description</th></tr></thead><tbody>" + rows + "</tbody></table>" +
      "<h2>Raw schema (JSON Schema 2020-12)</h2><div id='rawjson'></div>" +
      "<footer class='page-foot'><p>Source: <a href='../contracts/events/" + esc(p.file) + "' target='_blank'>contracts/events/" + esc(p.file) + "</a> · enforced by <code>scripts/check_event_payloads.py</code></p></footer>";
    var raw = $("#rawjson");
    raw.innerHTML = "<div class='codeblock'><div class='codehead'><span class='lang'>json</span><span class='fname'></span><button class='copybtn' type='button'>copy</button></div><pre><code></code></pre></div>";
    raw.querySelector(".fname").textContent = p.file;
    raw.querySelector("code").textContent = p.json;
    raw.querySelector(".copybtn").addEventListener("click", function () { copyText(p.json, this); });
    setCrumb("Payload — " + p.event);
    initScroll(v);
  }

  function pageTaxonomy() {
    var v = $("#view");
    v.innerHTML = "<article id='tax-body'></article>";
    var body = $("#tax-body");
    body.innerHTML = renderMd(DATA.contracts.taxonomy);
    postProcess(body);
    buildRail(body);
    setCrumb("Contracts — error taxonomy");
    initScroll(v);
  }

  function pageApiIndex() {
    var v = $("#view");
    v.innerHTML = "<h1>API contracts</h1>" +
      "<p>" + DATA.contracts.api.length + " module API specs. <span class='badge v1'>V1</span> = V1-surface contracts (frozen at 0.10); " +
      "<span class='badge ext'>ext</span> = extended (post-V1) design-level, provisional until that phase's freeze (docs/99 §12).</p>" +
      "<div class='doclist' style='max-height:640px;overflow-y:auto'><ol></ol></div>";
    var ol = v.querySelector("ol");
    DATA.contracts.api.forEach(function (a) {
      var row = document.createElement("a");
      row.className = "eventrow";
      row.href = "#/contracts/api/" + a.name;
      row.innerHTML = "<span class='ename'></span><span class='emeta'></span><span>" +
        (a.v1 ? "<span class='badge v1'>V1</span>" : "<span class='badge ext'>ext</span>") + "</span>";
      row.querySelector(".ename").textContent = a.name;
      row.querySelector(".emeta").textContent = a.label;
      ol.appendChild(row);
    });
    setCrumb("Contracts — API contracts");
    initScroll(v);
  }

  function pageApi(name) {
    var v = $("#view");
    var a = DATA.contracts.api.filter(function (x) { return x.name === name; })[0];
    if (!a) return pageNotFound();
    v.innerHTML = "<article id='api-body'></article>";
    var body = $("#api-body");
    body.innerHTML = renderMd(a.content);
    postProcess(body);
    buildRail(body);
    setCrumb("API contract — " + a.label);
    initScroll(v);
  }

  function pageDiagrams() {
    var v = $("#view");
    var cards = DATA.contracts.diagrams.map(function (d) {
      return "<a class='dia' href='../contracts/diagrams/" + d.png + "' target='_blank'><img src='../contracts/diagrams/" + d.png +
        "' alt='" + esc(d.name) + "' loading='lazy'><div class='dia-cap'></div><div class='dia-cites'></div></a>";
    }).join("");
    v.innerHTML = "<h1>Diagrams</h1>" +
      "<p>8 committed architecture diagrams (Mermaid sources in <code>contracts/diagrams/*.md</code>, rendered PNGs committed in-repo — " +
      "re-render with mermaid-cli when a source changes; a PNG that contradicts its source is a contract defect). Click to open full-size.</p>" +
      "<div class='diagrid'>" + cards + "</div>" +
      "<footer class='page-foot'><p><a href='../contracts/diagrams/README.md' target='_blank'>contracts/diagrams/README.md</a> — rendering tool, PNG strategy, staleness rules.</p></footer>";
    $$(".dia", v).forEach(function (d) {
      var data = DATA.contracts.diagrams.filter(function (x) {
        return d.querySelector("img").getAttribute("src").indexOf(x.png) !== -1;
      })[0];
      d.querySelector(".dia-cap").textContent = data.name;
      d.querySelector(".dia-cites").textContent = data.cites;
    });
    setCrumb("Contracts — diagrams");
    initScroll(v);
  }

  function pageRegisters(tab) {
    var v = $("#view");
    var r = DATA.registers;
    var dqOpen = r.design_questions.filter(function (q) { return openAns(q.answer); }).length;
    var prdOpen = r.prd_questions.filter(function (q) { return openAns(q.answer); }).length;
    var tabs = ["", "d", "prd", "triage"];
    var tabLabel = ["Overview", "Design decisions", "PRD questions", "Triage"];
    var i = Math.max(0, tabs.indexOf(tab || ""));
    v.innerHTML = "<h1>Decisions & open questions</h1>" +
      "<div class='filterbar' style='border:none'>" +
      tabs.map(function (t, j) {
        return "<a class='tbtn" + (j === i ? "' style='border-color:var(--accent);color:var(--accent)'" : "") + "' href='#/registers" + (t ? "/" + t : "") + "'>" + tabLabel[j] + "</a>";
      }).join("") + "</div><div id='reg-body'></div>";
    var body = $("#reg-body");
    if (i === 0) pageRegOverview(body, r, dqOpen, prdOpen);
    else if (i === 1) pageRegDecisions(body, r);
    else if (i === 2) pageRegPrd(body, r);
    else pageRegTriage(body, r);
    postProcess(body);
    setCrumb("Registers — " + tabLabel[i]);
    initScroll(v);
  }
  function openAns(a) { var t = (a || "").trim().replace(/^[\*_\s]+/, ""); return !t || t.toLowerCase().indexOf("open") === 0; }

  function pageRegOverview(body, r, dqOpen, prdOpen) {
    var s = DATA.project.stats;
    body.innerHTML =
      "<div class='callout info'><strong>Register state (" + esc(DATA.generated) + "):</strong> " +
      "<b>" + s.d_rows + "</b> design-review questions (D1–D" + s.d_rows + ") — <span class='badge ok'>" + (s.d_rows - dqOpen) + " answered</span> <span class='badge open'>" + dqOpen + " open</span>; " +
      "<b>" + s.prd_total + "</b> PRD questions — <span class='badge ok'>" + (s.prd_total - prdOpen) + " answered</span> <span class='badge open'>" + prdOpen + " open</span>.</div>" +
      "<div class='cards'>" +
      card("#/registers/d", "Design decisions (D1–D" + s.d_rows + ")", "Team decisions from design review — answered rows are binding for contract freeze (the D-number convention).") +
      card("#/registers/prd", "PRD open questions (205)", "Every question the PRD raised, grouped by module. Open rows must close before the owning module's freeze (docs/99 §12).") +
      card("#/registers/triage", "Triage — who can answer", "All " + prdOpen + " open PRD questions assigned to the stakeholder who can answer them; 43 carry 'Proposed — pending sign-off'.") +
      card("#/doc/37a-stakeholder-questions-for-funderblu", "Stakeholder hand-off (docs/37a)", "The flat hand-off document for FunderBlu's owners — reply per question; decisions land as workbook answers or D-rows.") +
      "</div>" +
      "<p>Rule of the register (docs/62): <em>an answer is a decision</em> — it lands only with a real owner decision, then the owning module doc is updated in the same change. Nothing is marked answered by default.</p>";
  }

  function pageRegDecisions(body, r) {
    var openN = r.design_questions.filter(function (q) { return openAns(q.answer); }).length;
    var html = "<div class='filterbar'><input type='search' id='dq-q' placeholder='Filter decisions…'> " +
      "<select id='dq-f'><option value='all'>All (" + r.design_questions.length + ")</option><option value='open'>Open (" + openN + ")</option><option value='answered'>Answered</option></select></div>" +
      "<div class='countline' id='dq-count'></div><div id='dq-list'></div>";
    body.innerHTML = html;
    function draw() {
      var q = $("#dq-q").value.trim().toLowerCase();
      var f = $("#dq-f").value;
      var list = $("#dq-list");
      var n = 0;
      list.innerHTML = "";
      r.design_questions.forEach(function (d) {
        var isOpen = openAns(d.answer);
        if (f === "open" && !isOpen) return;
        if (f === "answered" && isOpen) return;
        var hay = (d.id + " " + d.section + " " + d.question + " " + (d.answer || "")).toLowerCase();
        if (q && hay.indexOf(q) === -1) return;
        n++;
        var el = document.createElement("details");
        el.className = "drow";
        var summary = (d.question || "").length > 150 ? d.question.slice(0, 147) + "…" : (d.question || "");
        el.innerHTML = "<summary><span class='did'></span><span class='dsum'></span><span>" +
          (isOpen ? "<span class='badge open'>open</span>" : "<span class='badge ok'>answered</span>") + "</span></summary>" +
          "<div class='dbody'><p class='meta'></p><p class='dquest'></p>" +
          (d.answer ? "<p class='danswer'></p>" : "") + "</div>";
        el.querySelector(".did").textContent = d.id;
        el.querySelector(".dsum").textContent = summary;
        el.querySelector(".meta").textContent = "source doc " + d.source_doc + " · " + (d.section || "") + " · owner: " + (d.owner || "—") + " · deadline: " + (d.deadline || "—");
        el.querySelector(".dquest").textContent = d.question;
        if (d.answer) el.querySelector(".danswer").textContent = d.answer;
        list.appendChild(el);
      });
      $("#dq-count").textContent = n + " of " + r.design_questions.length + " decisions";
    }
    $("#dq-q").addEventListener("input", draw);
    $("#dq-f").addEventListener("change", draw);
    draw();
  }

  function pageRegPrd(body, r) {
    var openN = r.prd_questions.filter(function (q) { return openAns(q.answer); }).length;
    var sections = {};
    r.prd_questions.forEach(function (q) {
      (sections[q.section || "Unfiled"] = sections[q.section || "Unfiled"] || []).push(q);
    });
    body.innerHTML = "<div class='filterbar'><input type='search' id='pq-q' placeholder='Filter questions…'> " +
      "<select id='pq-f'><option value='all'>All (" + r.prd_questions.length + ")</option><option value='open'>Open (" + openN + ")</option><option value='answered'>Answered</option></select>" +
      "<select id='pq-s'><option value=''>All sections</option>" +
      Object.keys(sections).sort().map(function (s) { return "<option>" + esc(s) + "</option>"; }).join("") +
      "</select></div><div class='countline' id='pq-count'></div><div id='pq-list'></div>";
    function draw() {
      var q = $("#pq-q").value.trim().toLowerCase();
      var f = $("#pq-f").value;
      var sec = $("#pq-s").value;
      var list = $("#pq-list");
      var n = 0;
      list.innerHTML = "";
      Object.keys(sections).sort().forEach(function (s) {
        if (sec && s !== sec) return;
        var rows = sections[s].filter(function (row) {
          var isOpen = openAns(row.answer);
          if (f === "open" && !isOpen) return false;
          if (f === "answered" && isOpen) return false;
          if (q && (row.question + " " + (row.answer || "")).toLowerCase().indexOf(q) === -1) return false;
          return true;
        });
        if (!rows.length) return;
        n += rows.length;
        var div = document.createElement("div");
        div.innerHTML = "<h3 style='margin-top:26px'></h3><table><thead><tr><th style='width:36px'>#</th><th>Question</th><th style='width:110px'>Owner</th><th style='width:110px'>Deadline</th><th>Answer</th></tr></thead><tbody></tbody></table>";
        div.querySelector("h3").textContent = s + " (" + rows.length + ")";
        var tb = div.querySelector("tbody");
        rows.forEach(function (row, i) {
          var tr = document.createElement("tr");
          tr.innerHTML = "<td>" + (i + 1) + "</td><td></td><td></td><td></td><td></td>";
          tr.children[1].textContent = row.question;
          tr.children[2].textContent = row.owner || "—";
          tr.children[3].textContent = row.deadline || "—";
          var ans = (row.answer || "").trim();
          tr.children[4].innerHTML = openAns(ans) ? "<span class='badge open'>open</span>" : "<span class='badge ok'>answered</span><br><span style='font-size:12.5px'>" + esc(ans) + "</span>";
          tb.appendChild(tr);
        });
        list.appendChild(div);
      });
      $("#pq-count").textContent = n + " of " + r.prd_questions.length + " questions";
    }
    $("#pq-q").addEventListener("input", draw);
    $("#pq-f").addEventListener("change", draw);
    $("#pq-s").addEventListener("change", draw);
    draw();
  }

  function pageRegTriage(body, r) {
    var t = r.triage;
    var rows = t.rows || [];
    var counts = {};
    rows.forEach(function (x) { counts[x.bucket] = (counts[x.bucket] || 0) + 1; });
    var internal = t.internal_bucket;
    body.innerHTML = "<p>" + esc(t.note || "") + "</p><div class='countline'></div><div class='cards' id='tri-cards'></div>" +
      "<h2>Internal — Tech-Lead can decide now (" + (counts[internal] || 0) + ")</h2><div class='countline'>Each carries a proposed answer marked <em>Proposed — pending sign-off</em> — it becomes a decision only when the owner signs off (D-number convention).</div>" +
      "<div id='tri-list'></div>";
    body.querySelector(".countline").textContent = rows.length + " open PRD questions → " + Object.keys(counts).length + " stakeholder buckets. Full hand-off: ";
    var al = document.createElement("a");
    al.href = "#/doc/37a-stakeholder-questions-for-funderblu";
    al.textContent = "docs/37a (flat, grouped by stakeholder)";
    body.querySelector(".countline").appendChild(al);
    var cards = $("#tri-cards");
    (t.buckets || []).forEach(function (b) {
      var c = document.createElement("a");
      c.className = "card"; c.href = "#/registers/prd";
      c.innerHTML = "<div class='card-tag'></div><h3></h3><p></p>";
      c.querySelector(".card-tag").textContent = b === internal ? "internal" : "stakeholder";
      c.querySelector("h3").textContent = (counts[b] || 0) + " questions";
      c.querySelector("p").textContent = b;
      cards.appendChild(c);
    });
    var list = $("#tri-list");
    rows.filter(function (x) { return x.bucket === internal; }).forEach(function (x) {
      var el = document.createElement("details");
      el.className = "drow";
      el.innerHTML = "<summary><span class='did'></span><span class='dsum'></span></summary><div class='dbody'><p class='meta'></p><p class='dquest'></p><p class='danswer'></p></div>";
      el.querySelector(".did").textContent = x.section.replace(/ .*/, "").slice(0, 12);
      el.querySelector(".dsum").textContent = x.q.length > 150 ? x.q.slice(0, 147) + "…" : x.q;
      el.querySelector(".meta").textContent = x.section;
      el.querySelector(".dquest").textContent = x.q;
      el.querySelector(".danswer").textContent = x.note;
      list.appendChild(el);
    });
  }

  function pageNotFound() {
    $("#view").innerHTML = "<h1>Not found</h1><p>That page does not exist. <a href='#/'>Back to the overview</a>.</p>";
  }

  /* ---------- router ---------- */
  function route() {
    var h = parseHash();
    if (!DATA) return;
    window.scrollTo(0, 0);
    /* reset doc highlight */
    $$("#sb-nav a[data-doc]").forEach(function (a) { a.classList.remove("active"); });
    if (h.route === "doc" && h.arg) pageDoc(h.arg);
    else if (h.route === "contracts" && h.arg === "events") pageCatalog();
    else if (h.route === "contracts" && h.arg === "payloads" && h.sub) pagePayload(h.sub);
    else if (h.route === "contracts" && h.arg === "errors") pageTaxonomy();
    else if (h.route === "contracts" && h.arg === "api" && h.sub) pageApi(h.sub);
    else if (h.route === "contracts" && h.arg === "api") pageApiIndex();
    else if (h.route === "contracts" && h.arg === "diagrams") pageDiagrams();
    else if (h.route === "contracts") pageContractsHub();
    else if (h.route === "registers") pageRegisters(h.arg);
    else pageHome();
  }

  /* ---------- boot ---------- */
  function boot() {
    buildSidebar();
    /* theme */
    $("#theme-toggle").addEventListener("click", function () {
      var cur = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      document.documentElement.dataset.theme = cur;
      try { localStorage.setItem("a1-theme", cur); } catch (e) {}
    });
    /* drawer */
    var ham = $("#hamburger");
    ham.addEventListener("click", function () {
      var open = !document.body.classList.contains("nav-open");
      document.body.classList.toggle("nav-open", open);
      ham.setAttribute("aria-expanded", open ? "true" : "false");
    });
    $("#overlay").addEventListener("click", function () { document.body.classList.remove("nav-open"); });
    $$("#sb-nav a").forEach(function (a) {
      a.addEventListener("click", function () { if (window.innerWidth <= 900) document.body.classList.remove("nav-open"); });
    });
    /* totop */
    $("#totop").addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
    /* keyboard */
    window.addEventListener("keydown", function (e) {
      var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement && document.activeElement.tagName);
      if (typing) return;
      if (e.key === "/") { e.preventDefault(); $("#nav-search").focus(); }
      else if (e.key === "t") { $("#theme-toggle").click(); }
    });
    window.addEventListener("hashchange", route);
    route();
  }
  DATA_READY.then(boot);
})();
