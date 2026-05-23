#!/usr/bin/env python3
"""Fallback ID resolution for rows still missing a DOI after resolve_ids.py.

Avoids publisher pages (which bot-block). Instead:
  - fix DOIs with trailing junk (/full, /abstract...) already captured from URL,
  - for the rest, parse first-author + year (+ journal hint) from the Reference
    text and query Europe PMC; auto-accept only a STRONG single match
    (author surname in authorString AND year matches AND title looks like a
    metabolomics/GWAS paper); otherwise flag for user review.
Updates data/gwas_ids.csv in place (backup written first).
"""
import csv, json, os, re, shutil, subprocess, time, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = os.path.join(ROOT, "data", "gwas_ids.csv")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
KW = re.compile(r"metabol|metabolite|lipid|GWAS|genome-wide|genome wide|loci|mGWAS|mQTL|amino acid|biomarker", re.I)


def curl(url, t=25):
    try:
        return subprocess.run(["curl", "-sL", "--max-time", str(t), "-A", UA, url],
                              capture_output=True, text=True, timeout=t + 5).stdout
    except Exception:
        return ""


def epmc(q, n=6):
    url = f"{EPMC}?query={urllib.parse.quote(q)}&format=json&pageSize={n}&resultType=lite"
    try:
        return json.loads(curl(url))["resultList"]["result"]
    except Exception:
        return []


def fix_doi(d):
    d = re.sub(r'(/full|/abstract|/fulltext|/meta|\.long)$', '', d, flags=re.I)
    return d.rstrip('/').rstrip('.')


def parse_ref(ref):
    # author chunk = text before 'et al'
    m = re.split(r'\bet al', ref)
    name = m[0].strip(" ,.&") if m else ref
    surname = name.split()[-1] if name.split() else name
    yr = re.search(r'\b(20\d{2}|19\d{2})\b', ref)
    year = yr.group(1) if yr else ""
    is_conf = bool(re.search(r'ASHG|abstract|conference', ref, re.I))
    return surname, name, year, is_conf


def main():
    shutil.copy(IDS, IDS + ".bak")
    rows = list(csv.DictReader(open(IDS)))
    fields = rows[0].keys()
    for r in rows:
        if r["DOI"]:
            r["DOI"] = fix_doi(r["DOI"])
        if r["DOI"]:
            continue                      # already has a DOI
        surname, name, year, is_conf = parse_ref(r["Reference"])
        if is_conf:
            r["status"] = "conference-abstract (no DOI)"
            print(f'{r["row_id"]:>3} CONF   {r["Reference"]}')
            continue
        q = f'AUTH:"{surname}" AND PUB_YEAR:{year}' if year else f'AUTH:"{surname}"'
        res = epmc(q + ' AND (metabol* OR lipid* OR GWAS OR "genome-wide")')
        if not res:
            res = epmc(q)
        time.sleep(0.3)
        pick = None
        for x in res:
            au = (x.get("authorString", "") or "")
            ti = (x.get("title", "") or "")
            if surname.lower() in au.lower() and (not year or x.get("pubYear") == year) and KW.search(ti):
                pick = x
                break
        if pick:
            r["DOI"] = fix_doi(pick.get("doi", "") or "")
            r["PMID"] = pick.get("pmid", "") or r["PMID"]
            r["epmc_source"] = pick.get("source", "")
            r["resolved_title"] = pick.get("title", "")
            r["resolved_journal"] = pick.get("journalTitle", "")
            r["resolved_year"] = pick.get("pubYear", "")
            r["status"] = "resolved-fallback"
            r["method"] = "epmc-authyear"
            print(f'{r["row_id"]:>3} OK     DOI={r["DOI"] or "-":34} PMID={r["PMID"] or "-":9} | {pick.get("title","")[:55]}')
        else:
            r["status"] = "needs-manual"
            print(f'{r["row_id"]:>3} FLAG   no confident match for "{r["Reference"]}" ({len(res)} candidates)')

    with open(IDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    ndoi = sum(1 for r in rows if r["DOI"])
    npmid = sum(1 for r in rows if r["PMID"])
    print(f"\nAfter fallback -> DOI: {ndoi}/98 | PMID: {npmid}/98")
    print("still needing manual:", [r["row_id"] for r in rows if r["status"] in ("needs-manual",)])
    print("conference abstracts:", [r["row_id"] for r in rows if "conference" in r["status"]])


if __name__ == "__main__":
    main()
