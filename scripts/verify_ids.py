#!/usr/bin/env python3
"""Correct the fallback ID matches after manual verification.

The author+year EPMC fallback produced false matches for common surnames
(verified by comparing resolved journal/topic against the original URL):
  KEEP  (consistent)            : 17,21,24,28,40,51,52,58,73,92
  DEMOTE(wrong paper -> manual) : 10,34,35,39,62,72,80,83,91
  MDPI  (derive DOI from URL)   : 66,75   (deterministic mdpi.com pattern)
Primary URL-extracted DOIs (method in doi/page-meta/pmid/pmcid) are trusted as-is.
Each kept/derived DOI is re-checked against Europe PMC (author surname must appear).
"""
import csv, json, os, re, subprocess, time, unicodedata, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = os.path.join(ROOT, "data", "gwas_ids.csv")
EX = {r["row_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "gwas_existing.csv")))}
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

DEMOTE = {"10", "34", "35", "39", "62", "72", "80", "83", "91"}
# MDPI ISSN -> journal abbrev used in DOIs
MDPI_ABBR = {"2218-1989": "metabo", "2072-6643": "nu"}


def norm(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()


def curl(url, t=25):
    try:
        return subprocess.run(["curl", "-sL", "--max-time", str(t), "-A", UA, url],
                              capture_output=True, text=True, timeout=t + 5).stdout
    except Exception:
        return ""


def epmc_by_doi(doi):
    url = f'{EPMC}?query=DOI:"{urllib.parse.quote(doi)}"&format=json&pageSize=1&resultType=lite'
    try:
        res = json.loads(curl(url))["resultList"]["result"]
        return res[0] if res else None
    except Exception:
        return None


def mdpi_doi(url):
    m = re.search(r'mdpi\.com/(\d{4}-\d{3}[\dxX])/(\d+)/(\d+)/(\d+)', url)
    if not m:
        return ""
    issn, vol, iss, art = m.groups()
    ab = MDPI_ABBR.get(issn)
    if not ab:
        return ""
    return f"10.3390/{ab}{int(vol)}{int(iss):02d}{int(art):04d}"


def surname(ref):
    name = re.split(r'\bet al', ref)[0].strip(" ,.&(")
    return name.split()[-1] if name.split() else name


def main():
    rows = list(csv.DictReader(open(IDS)))
    fields = list(rows[0].keys())
    for r in rows:
        rid = r["row_id"]
        if rid in DEMOTE:
            r.update(DOI="", PMID="", resolved_title="", resolved_journal="",
                     epmc_source="", method="manual-flag", status="needs-manual")
            print(f"{rid:>3} DEMOTED -> needs-manual ({r['Reference']})")
            continue
        # MDPI deterministic derivation for the two reverted MDPI rows
        if rid in ("66", "75"):
            doi = mdpi_doi(EX[rid]["Ref_URLs"].split(" ; ")[0])
            rec = epmc_by_doi(doi) if doi else None
            time.sleep(0.25)
            if rec and norm(surname(r["Reference"])) in norm(rec.get("authorString", "")):
                r.update(DOI=doi, PMID=rec.get("pmid", ""), resolved_title=rec.get("title", ""),
                         resolved_journal=rec.get("journalTitle", ""), epmc_source=rec.get("source", ""),
                         resolved_year=rec.get("pubYear", ""), method="mdpi-url", status="resolved-mdpi")
                print(f"{rid:>3} MDPI    DOI={doi} PMID={r['PMID'] or '-'} | {rec.get('title','')[:50]}")
            else:
                r.update(DOI=doi, method="mdpi-url", status="needs-manual-check")
                print(f"{rid:>3} MDPI    DOI={doi} (EPMC unconfirmed -> flag)")
    # Re-verify the kept fallback DOIs resolve and match the author
    for r in rows:
        if r["method"] == "epmc-authyear" and r["DOI"]:
            rec = epmc_by_doi(r["DOI"]); time.sleep(0.2)
            ok = rec and norm(surname(r["Reference"])) in norm(rec.get("authorString", ""))
            print(f"{r['row_id']:>3} verify  {'OK ' if ok else 'WARN'} {r['DOI']}  ({r['Reference']})")

    with open(IDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    ndoi = sum(1 for r in rows if r["DOI"]); npmid = sum(1 for r in rows if r["PMID"])
    manual = [r["row_id"] for r in rows if "manual" in r["status"]]
    conf = [r["row_id"] for r in rows if "conference" in r["status"]]
    print(f"\nFINAL -> DOI: {ndoi}/98 | PMID: {npmid}/98")
    print("needs-manual:", manual, "| conference (no DOI):", conf)


if __name__ == "__main__":
    main()
