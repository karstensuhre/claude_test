#!/usr/bin/env python3
"""Build self-contained, dependency-free HTML:
   gwas_table.html  - homogenized catalog (98 rows) + PubMed/DOI columns, sort+filter
   candidates.html  - 15 auto-discovered candidates pending user approval
Styled to match index.html (no external CDN; vanilla-JS sort/filter).
"""
import csv, html, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOM = os.path.join(ROOT, "data", "gwas_homogenized.csv")
CAND = os.path.join(ROOT, "data", "candidates.csv")
TODAY = datetime.date.today().isoformat()

CSS = """
:root{--bg:#f7f8fa;--card:#fff;--ink:#1c2128;--muted:#6a737d;--accent:#6d5efc;--border:#e6e8eb;--hl:#fff7d6;--head:#efeefe}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--ink:#e6edf3;--muted:#8b949e;--accent:#8f7dff;--border:#30363d;--hl:#3a3514;--head:#1c2233}}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink);line-height:1.5}
header{background:linear-gradient(135deg,var(--accent),#b06dfc);color:#fff;padding:40px 24px 34px;text-align:center}
header h1{margin:0 0 6px;font-size:1.7rem;letter-spacing:-.02em}header p{margin:2px 0;opacity:.93;font-size:.95rem}
.wrap{max-width:1280px;margin:0 auto;padding:20px 18px 70px}
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


def page(title, subtitle, extra_head, body):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{esc(title)}</title>
<style>{CSS}</style><script>{SORT_JS}</script></head><body>
<header><h1>{esc(title)}</h1>{subtitle}</header>
<div class="wrap">{body}</div>
<footer>Built {TODAY} from <a href="http://www.metabolomix.com/list-of-all-published-gwas-with-metabolomics/" target="_blank" rel="noopener">metabolomix.com</a>
&middot; homogenized &amp; link-resolved with Claude &middot; <a href="https://github.com/karstensuhre/claude_test" target="_blank" rel="noopener">repo</a></footer>
</body></html>"""


def build_main():
    rows = list(csv.DictReader(open(HOM)))
    cols = [("Year", "Year", True), ("Biofluid", "Biofluid", False), ("Metabolic_traits", "Metabolic traits", False),
            ("Platform", "Platform", False), ("Study_population", "Study population", False),
            ("N_Traits", "# Traits", False), ("Cohort_size", "Cohort size", False),
            ("N_Loci", "# Loci", False), ("Reference", "Reference", False)]
    th = "".join(f'<th onclick="sortTable(this)">{esc(lbl)} <span class="ar"></span></th>' for _, lbl, _ in cols)
    th += '<th>PubMed</th><th>DOI</th>'
    trs = []
    for r in rows:
        tds = []
        for key, _, numeric in cols:
            v = r[key]
            cls = ' class="num"' if numeric or key in ("N_Traits", "Cohort_size", "N_Loci") else ""
            cell = esc(v)
            if key == "Reference" and r.get("flag"):
                cell += f' <span class="flag" title="{esc(r["notes"])}">&#9873;</span>'
            tds.append(f"<td{cls}>{cell}</td>")
        tds.append(f"<td>{link(r['PubMed_url'], 'PubMed')}</td>")
        tds.append(f"<td>{link(r['DOI_url'], 'DOI')}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    n = len(rows)
    body = f"""
<div class="note">Hand-curated catalog of published <b>GWAS with metabolomics in humans</b>, ordered by year.
Labels homogenized (biofluid/platform), with resolved <b>PubMed</b> and <b>DOI</b> links added (DOIs may be paywalled).
&#9873; marks {sum(1 for r in rows if r.get('flag'))} rows needing your review (hover for the reason). Click a header to sort; type to filter.</div>
<div class="bar"><input type="search" placeholder="Filter (author, platform, cohort, gene…)" oninput="filt(this.value)">
<span class="count" id="cnt">{n} rows</span></div>
<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"""
    sub = f'<p>{n} studies &middot; homogenized &amp; link-resolved &middot; source: metabolomix.com (last updated there 13 Feb 2025)</p>'
    open(os.path.join(ROOT, "gwas_table.html"), "w", encoding="utf-8").write(
        page("GWAS with metabolomics", sub, "", body))
    return n


def build_candidates():
    rows = list(csv.DictReader(open(CAND)))
    cols = [("confidence", "Conf."), ("Year", "Year"), ("Reference", "Reference"), ("Biofluid", "Biofluid"),
            ("Metabolic_traits", "Metabolic traits"), ("Platform", "Platform"), ("Study_population", "Study population"),
            ("N_Traits", "# Traits"), ("Cohort_size", "Cohort size"), ("N_Loci", "# Loci")]
    th = "".join(f'<th onclick="sortTable(this)">{esc(lbl)} <span class="ar"></span></th>' for _, lbl in cols)
    th += '<th>PubMed</th><th>DOI</th><th>Why / notes</th>'
    trs = []
    for r in rows:
        tds = []
        for key, _ in cols:
            if key == "confidence":
                c = r[key]
                tds.append(f'<td data-s="{ {"high":0,"medium":1,"low":2}.get(c,3) }"><span class="badge {esc(c)}">{esc(c)}</span></td>')
            else:
                cls = ' class="num"' if key in ("Year", "N_Traits", "Cohort_size", "N_Loci") else ""
                tds.append(f"<td{cls}>{esc(r[key])}</td>")
        tds.append(f"<td>{link(r['PubMed_url'], 'PubMed')}</td>")
        tds.append(f"<td>{link(r['DOI_url'], 'DOI')}</td>")
        why = esc(r["snippet"])
        if r["notes"]:
            why += f'<br><span class="dash">{esc(r["notes"])}</span>'
        tds.append(f"<td style='max-width:320px;font-size:.78rem'>{why}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    nflag = sum(1 for r in rows if "overlap" in r["notes"])
    body = f"""
<div class="note"><b>{len(rows)} candidate papers (2024–2026) auto-discovered and verified, pending your approval.</b>
Each was confirmed to be a human metabolite-panel GWAS with a resolving DOI/PMID and an abstract snippet.
<b>To accept any:</b> set <code>approve=y</code> in <code>data/candidates.csv</code> and I'll merge it into the main table.
{nflag} rows are flagged for <b>possible overlap</b> with existing UK-Biobank/NMR entries — verify before approving.
Confidence: high = unambiguous; medium = qualifies, some fields unclear; low = borderline.</div>
<div class="bar"><input type="search" placeholder="Filter candidates…" oninput="filt(this.value)">
<span class="count" id="cnt">{len(rows)} rows</span></div>
<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"""
    sub = f'<p>{len(rows)} candidates pending approval &middot; 8 high / 6 medium / 1 low confidence</p>'
    open(os.path.join(ROOT, "candidates.html"), "w", encoding="utf-8").write(
        page("mGWAS candidates — pending review", sub, "", body))
    return len(rows)


if __name__ == "__main__":
    a = build_main()
    b = build_candidates()
    print(f"wrote gwas_table.html ({a} rows) and candidates.html ({b} rows)")
