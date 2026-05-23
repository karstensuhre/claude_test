#!/usr/bin/env python3
"""Phase 3 discovery harvest: pull candidate metabolomics-GWAS papers (2024-2026)
from Europe PMC, dedupe against the existing 98, pre-filter, and write a pool
(data/harvest_candidates.csv) for the verification agents.

Inclusion mirrors the page's loose criterion: GWAS / mQTL of metabolite or lipid
PANELS (MS or NMR) in humans. Excludes single-trait biochemical GWAS, pure
proteomics, and non-human organisms.
"""
import csv, json, os, re, subprocess, time, unicodedata, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = os.path.join(ROOT, "data", "gwas_ids.csv")
OUT = os.path.join(ROOT, "data", "harvest_candidates.csv")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

DATE = "(FIRST_PDATE:[2024-06-01 TO 2026-12-31])"
QUERIES = [
    f'(metabolome OR metabolomic* OR "metabolite levels" OR "metabolite traits") AND ("genome-wide association" OR GWAS OR mGWAS) AND {DATE}',
    f'(mQTL OR "metabolite quantitative trait loc*" OR "genetics of the metabolome") AND {DATE}',
    f'(lipidom* OR "lipid species" OR sphingolipid* OR "fatty acid") AND ("genome-wide association" OR GWAS) AND {DATE}',
    f'(Nightingale OR Metabolon OR Biocrates OR "NMR metabolomics") AND ("genome-wide association" OR GWAS) AND metabol* AND {DATE}',
    f'(metabol* AND ("genome-wide association study" OR "GWAS")) AND ("UK Biobank" OR biobank OR multi-ancestry OR meta-analysis) AND {DATE}',
]
METAB = re.compile(r"metabolom|metabolite|metabol\w*|lipidom|lipid|sphingolip|fatty acid|amino acid|biochemical|acylcarnitine|bile acid|eicosanoid", re.I)
GWASKW = re.compile(r"genome-wide|genome wide|\bGWAS\b|mQTL|mGWAS|quantitative trait loc|genetic determinants|genetic architecture|genetic associat|loci|fine-mapping", re.I)
NONHUMAN = re.compile(r"\b(pig|piglet|porcine|swine|plant|root|leaf|maize|rice|wheat|barley|soybean|cattle|bovine|chicken|broiler|poultry|mouse|mice|murine|\brat\b|rats|zebrafish|duck|sheep|goat|drosophila|yeast|arabidopsis|fish|cow|equine|horse|insect|microbiom)", re.I)


def norm(s):
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9 ]", " ", s)


def curl(url, t=30):
    try:
        return subprocess.run(["curl", "-sL", "--max-time", str(t), "-A", UA, url],
                              capture_output=True, text=True, timeout=t + 5).stdout
    except Exception:
        return ""


def epmc_all(query, max_pages=8):
    out, cursor = [], "*"
    for _ in range(max_pages):
        url = (f"{EPMC}?query={urllib.parse.quote(query)}&format=json&pageSize=100"
               f"&resultType=core&cursorMark={urllib.parse.quote(cursor)}")
        try:
            j = json.loads(curl(url))
        except Exception:
            break
        res = j.get("resultList", {}).get("result", [])
        out += res
        nxt = j.get("nextCursorMark")
        if not nxt or nxt == cursor or not res:
            break
        cursor = nxt
        time.sleep(0.4)
    return out


def main():
    existing = list(csv.DictReader(open(IDS)))
    ex_doi = {r["DOI"].lower() for r in existing if r["DOI"]}
    ex_pmid = {r["PMID"] for r in existing if r["PMID"]}
    ex_titles = {norm(r["resolved_title"]) for r in existing if r["resolved_title"]}

    pool = {}
    for q in QUERIES:
        recs = epmc_all(q)
        print(f"query -> {len(recs):4d} records :: {q[:70]}...")
        for r in recs:
            doi = (r.get("doi") or "").lower()
            pmid = r.get("pmid") or ""
            key = doi or pmid or r.get("id") or norm(r.get("title", ""))[:60]
            if key and key not in pool:
                pool[key] = r

    print(f"\nunique harvested: {len(pool)}")
    rows = []
    seen_dupe = kept = 0
    for r in pool.values():
        doi = (r.get("doi") or "")
        pmid = r.get("pmid") or ""
        title = r.get("title", "") or ""
        abstract = r.get("abstractText", "") or ""
        blob = f"{title} {abstract}"
        # dedupe vs existing
        if doi.lower() in ex_doi or (pmid and pmid in ex_pmid) or norm(title) in ex_titles:
            seen_dupe += 1
            continue
        # topical pre-filter
        if not (METAB.search(blob) and GWASKW.search(blob)):
            continue
        if NONHUMAN.search(title):
            continue
        kept += 1
        rows.append(dict(
            pmid=pmid, doi=doi, year=r.get("pubYear", ""),
            journal=(r.get("journalInfo", {}) or {}).get("journal", {}).get("title", "")
                    or r.get("journalTitle", "") or r.get("source", ""),
            source=r.get("source", ""), title=title,
            authors=(r.get("authorString", "") or "")[:160],
            abstract=re.sub(r"\s+", " ", abstract)[:600],
        ))
    rows.sort(key=lambda x: (x["year"], x["journal"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"dropped as duplicates of existing 98: {seen_dupe}")
    print(f"kept candidate pool (pre-verification): {kept}  -> {OUT}")
    from collections import Counter
    print("by year:", dict(sorted(Counter(r["year"] for r in rows).items())))


if __name__ == "__main__":
    main()
