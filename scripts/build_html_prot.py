#!/usr/bin/env python3
"""Build self-contained, dependency-free HTML for the proteomics catalog:
   pgwas_table.html       - homogenized existing catalog (93 rows) + PubMed/DOI, sort+filter
   pgwas_candidates.html  - new pGWAS candidates (keep + borderline) pending user approval
Styled to match index.html / gwas_table.html (no external CDN; vanilla-JS sort/filter).
CSS + sort JS are copied from build_html.py so each page stays standalone.
"""
import csv, html, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOM = os.path.join(ROOT, "data", "pgwas_homogenized.csv")
CAND = os.path.join(ROOT, "data", "pgwas_candidates.csv")
TODAY = datetime.date.today().isoformat()

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#1c2128;--muted:#6a737d;--accent:#6d5efc;--border:#e6e8eb;--hl:#fff7d6;--head:#efeefe}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--muted:#8b949e;--accent:#8f7dff;--border:#30363d;--hl:#3a3514;--head:#1c2233}}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
header{background:linear-gradient(135deg,var(--accent),#b06dfc);color:#fff;padding:40px 24px 34px;text-align:center}
header h1{margin:0 0 6px;font-size:1.7rem;letter-spacing:-.02em}header p{margin:2px 0;opacity:.93;font-size:.95rem}
.wrap{max-width:1320px;margin:0 auto;padding:20px 18px 70px}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:14px 0}
input[type=search]{flex:1;min-width:220px;padding:9px 12px;border:1px solid var(--border);border-radius:9px;background:var(--card);color:var(--ink);font-size:.95rem}
.count{color:var(--muted);font-size:.85rem}
.note{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:8px;padding:12px 14px;margin:12px 0;font-size:.9rem;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.84rem;background:var(--card);border:1px solid var(--border);border-radius:10px;overflow:hidden}
th,td{padding:7px 9px;text-align:left;vertical-align:top;border-bottom:1px solid var(--border)}
th{background:var(--head);position:sticky;top:0;cursor:pointer;white-space:nowrap;font-size:.8rem}
th:hover{color:var(--accent)}th .ar{opacity:.4;font-size:.7rem}
tr:hover td{background:color-mix(in srgb,var(--accent) 6%,transparent)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
a.lnk{display:inline-block;padding:1px 7px;border-radius:6px;background:color-mix(in srgb,var(--accent) 15%,transparent);color:var(--accent);text-decoration:none;font-size:.78rem;font-weight:600}
a.lnk:hover{background:color-mix(in srgb,var(--accent) 28%,transparent)}
.dash{color:var(--muted)}
.flag{cursor:help;color:#d98b00}
.badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.72rem;font-weight:700}
.high{background:#1f9d5522;color:#1f9d55}.medium{background:#d9a40622;color:#b8860b}.low{background:#8884}
.keep{background:#1f9d5522;color:#1f9d55}.borderline{background:#d9a40622;color:#b8860b}
.pf{display:inline-block;padding:1px 7px;border-radius:6px;font-size:.74rem;font-weight:600;background:color-mix(in srgb,var(--accent) 13%,transparent);color:var(--accent);cursor:help}
footer{margin-top:30px;color:var(--muted);font-size:.82rem;text-align:center}
a{color:var(--accent)}
"""

SORT_JS = """
function _key(td){var s=td.getAttribute('data-s');if(s===null)s=td.textContent;var n=parseFloat(String(s).replace(/[^0-9.\\-]/g,''));return {n:isNaN(n)?null:n,t:String(s).toLowerCase()};}
function sortTable(th){var t=th.closest('table'),tb=t.tBodies[0],idx=Array.prototype.indexOf.call(th.parentNode.children,th);
 var dir=th.getAttribute('data-dir')==='asc'?-1:1;Array.prototype.forEach.call(t.tHead.rows[0].cells,function(c){c.removeAttribute('data-dir');var a=c.querySelector('.ar');if(a)a.textContent='';});
 th.setAttribute('data-dir',dir===1?'asc':'desc');var a=th.querySelector('.ar');if(a)a.textContent=dir===1?'\\u25B2':'\\u25BC';
 var rows=Array.prototype.slice.call(tb.rows);rows.sort(function(x,y){var A=_key(x.cells[idx]),B=_key(y.cells[idx]);
  if(A.n!==null&&B.n!==null)return (A.n-B.n)*dir;if(A.n!==null)return -1*dir;if(B.n!==null)return 1*dir;return A.t<B.t?-dir:A.t>B.t?dir:0;});
 rows.forEach(function(r){tb.appendChild(r);});}
function filt(q){q=q.toLowerCase();var rows=document.querySelectorAll('tbody tr'),n=0;
 rows.forEach(function(r){var hit=r.textContent.toLowerCase().indexOf(q)>=0;r.style.display=hit?'':'none';if(hit)n++;});
 var c=document.getElementById('cnt');if(c)c.textContent=n+' rows';}
"""


def esc(s):
    return html.escape(str(s or ""))


def link(url, label):
    if not url:
        return '<span class="dash">—</span>'
    return f'<a class="lnk" href="{esc(url)}" target="_blank" rel="noopener">{label}</a>'


def pf(cls, detail):
    if not cls:
        return '<span class="dash">—</span>'
    return f'<span class="pf" title="{esc(detail)}">{esc(cls)}</span>'


def page(title, subtitle, body):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{esc(title)}</title>
<style>{CSS}</style><script>{SORT_JS}</script></head><body>
<header><h1>{esc(title)}</h1>{subtitle}</header>
<div class="wrap">{body}</div>
<footer>Built {TODAY} from <a href="http://www.metabolomix.com/a-table-of-all-published-gwas-with-proteomics/" target="_blank" rel="noopener">metabolomix.com</a>
&middot; homogenized, ID- &amp; link-resolved with Claude &middot; <a href="https://github.com/karstensuhre/claude_test" target="_blank" rel="noopener">repo</a></footer>
</body></html>"""


def num_cell(v):
    return f'<td class="num">{esc(v) if v not in ("", None) else "—"}</td>'


def build_main():
    rows = list(csv.DictReader(open(HOM)))
    rows.sort(key=lambda r: (-int(r["Year"] or 0), r["row_id"].zfill(3)))
    cols = [("Year", "Year"), ("Reference", "Reference"), ("Study_population", "Study population"),
            ("Sample_type", "Sample"), ("Platform_class", "Platform"), ("N_proteins", "# Proteins"),
            ("N_cis_pQTL", "cis-pQTL"), ("N_trans_pQTL", "trans-pQTL"), ("N_pQTL_total", "Σ pQTL"),
            ("N_samples", "# Samples")]
    th = "".join(f'<th onclick="sortTable(this)">{esc(lbl)} <span class="ar"></span></th>' for _, lbl in cols)
    th += '<th>PubMed</th><th>DOI</th>'
    trs = []
    for r in rows:
        tds = [f'<td class="num">{esc(r["Year"])}</td>']
        ref = esc(r["Reference"])
        if r.get("flag"):
            ref += f' <span class="flag" title="{esc(r["notes"])}">&#9873;</span>'
        tds.append(f"<td>{ref}</td>")
        tds.append(f'<td>{esc(r["Study_population"])}</td>')
        sample = esc(r["Sample_type"]).replace(" (assumed)", ' <span class="dash" title="assumed; not stated in source">(assumed)</span>')
        tds.append(f"<td>{sample}</td>")
        tds.append(f'<td>{pf(r["Platform_class"], r["Platform_detail"])}</td>')
        tds.append(num_cell(r["N_proteins"]))
        tds.append(num_cell(r["N_cis_pQTL"]))
        tds.append(num_cell(r["N_trans_pQTL"]))
        # total cell carries the raw string as a tooltip
        tot = r["N_pQTL_total"]
        raw = r["N_pQTL_raw"]
        tcell = esc(tot) if tot not in ("", None) else "—"
        title = f' title="{esc(raw)}"' if raw and str(raw) != str(tot) else ""
        cls = "num flag" if "pqtl-ambiguous" in r.get("flag", "") else "num"
        tds.append(f'<td class="{cls}"{title}>{tcell}</td>')
        tds.append(num_cell(r["N_samples"]))
        tds.append(f"<td>{link(r['PubMed_url'], 'PubMed')}</td>")
        tds.append(f"<td>{link(r['DOI_url'], 'DOI')}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    n = len(rows)
    nflag = sum(1 for r in rows if r.get("flag"))
    body = f"""
<div class="note">Hand-curated catalog of published <b>GWAS with proteomics in humans</b> (pQTL studies), ordered by year.
Platform homogenized into <b>technology classes</b> (hover a platform chip for the original label); the <b>#pQTLs</b> column is split into
<b>cis</b> / <b>trans</b> / total where the source reported it (hover Σ for the original count string).
Resolved <b>PubMed</b> and <b>DOI</b> links added (DOIs may be paywalled). &#9873; marks {nflag} rows needing review
(conference abstracts without a DOI, ambiguous pQTL counts, or entries the source itself flags as not strictly proteomics).
Click a header to sort; type to filter.</div>
<div class="bar"><input type="search" placeholder="Filter (author, cohort, platform, ancestry…)" oninput="filt(this.value)">
<span class="count" id="cnt">{n} rows</span></div>
<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"""
    sub = f'<p>{n} studies &middot; homogenized &amp; link-resolved &middot; source: metabolomix.com (proteomics list)</p>'
    open(os.path.join(ROOT, "pgwas_table.html"), "w", encoding="utf-8").write(
        page("GWAS with proteomics", sub, body))
    return n


def build_candidates():
    rows = list(csv.DictReader(open(CAND)))
    rej_path = os.path.join(ROOT, "data", "pgwas_rejections.md")
    nrej = sum(1 for l in open(rej_path) if l.startswith("- ")) if os.path.exists(rej_path) else 0
    cols = [("decision", "Status"), ("confidence", "Conf."), ("Year", "Year"), ("Reference", "Reference"),
            ("Study_population", "Study population"), ("Sample_type", "Sample"), ("Platform_class", "Platform"),
            ("N_proteins", "# Proteins"), ("N_cis_pQTL", "cis"), ("N_trans_pQTL", "trans"),
            ("N_pQTL_total", "Σ pQTL"), ("N_samples", "# Samples")]
    th = "".join(f'<th onclick="sortTable(this)">{esc(lbl)} <span class="ar"></span></th>' for _, lbl in cols)
    th += '<th>PubMed</th><th>DOI</th><th>Why / notes</th>'
    trs = []
    for r in rows:
        d = r["decision"]
        tds = [f'<td data-s="{0 if d=="keep" else 1}"><span class="badge {esc(d)}">{esc(d)}</span></td>']
        c = r["confidence"]
        tds.append(f'<td data-s="{ {"high":0,"medium":1,"low":2}.get(c,3) }"><span class="badge {esc(c)}">{esc(c)}</span></td>')
        tds.append(f'<td class="num">{esc(r["Year"])}</td>')
        tds.append(f'<td>{esc(r["Reference"])}</td>')
        tds.append(f'<td>{esc(r["Study_population"])}</td>')
        tds.append(f'<td>{esc(r["Sample_type"])}</td>')
        tds.append(f'<td>{pf(r["Platform_class"], r["Platform"])}</td>')
        tds.append(num_cell(r["N_proteins"]))
        tds.append(num_cell(r["N_cis_pQTL"]))
        tds.append(num_cell(r["N_trans_pQTL"]))
        tds.append(num_cell(r["N_pQTL_total"]))
        tds.append(num_cell(r["N_samples"]))
        tds.append(f"<td>{link(r['PubMed_url'], 'PubMed')}</td>")
        tds.append(f"<td>{link(r['DOI_url'], 'DOI')}</td>")
        why = esc(r["snippet"])
        extra = []
        if r["category"] and r["category"] != "primary_pgwas":
            extra.append(esc(r["category"]))
        if r["notes"]:
            extra.append(esc(r["notes"]))
        if r["overlap_flag"]:
            extra.append("⚑ " + esc(r["overlap_flag"]))
        if extra:
            why += f'<br><span class="dash">{" · ".join(extra)}</span>'
        tds.append(f"<td style='max-width:340px;font-size:.78rem'>{why}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    nk = sum(1 for r in rows if r["decision"] == "keep")
    nb = sum(1 for r in rows if r["decision"] == "borderline")
    body = f"""
<div class="note"><b>{len(rows)} candidate protein-GWAS papers (2023–2026) auto-discovered and verified by multiple agents, pending your approval.</b>
Each was confirmed (from its abstract) to be a study that <b>measured the proteome de novo</b> (affinity: SomaScan/Olink, or mass spec)
and ran a <b>genome-wide pQTL discovery</b> — papers that merely reuse existing pQTLs (Mendelian randomization, PWAS, colocalization,
drug-target, PheWAS, meta-analysis) were excluded and logged in <code>data/pgwas_rejections.md</code> ({nrej} rejected).
<b>{nk}</b> are clean keeps, <b>{nb}</b> are <span class="badge borderline">borderline</span> (e.g. re-analyses of an existing cohort's measurements,
sub-genome-wide, or ratio/variance QTLs) — read the notes. <b>To accept any:</b> set <code>approve=y</code> in
<code>data/pgwas_candidates.csv</code>. Numbers are extracted from abstracts (NR = not reported); verify against full text before use.</div>
<div class="bar"><input type="search" placeholder="Filter candidates (cohort, platform, ancestry…)" oninput="filt(this.value)">
<span class="count" id="cnt">{len(rows)} rows</span></div>
<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"""
    sub = f'<p>{len(rows)} candidates pending approval &middot; {nk} keep / {nb} borderline &middot; {nrej} excluded (see rejections log)</p>'
    open(os.path.join(ROOT, "pgwas_candidates.html"), "w", encoding="utf-8").write(
        page("Proteomics-GWAS candidates — pending review", sub, body))
    return len(rows)


if __name__ == "__main__":
    a = build_main()
    b = build_candidates()
    print(f"wrote pgwas_table.html ({a} rows) and pgwas_candidates.html ({b} rows)")
