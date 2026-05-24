#!/usr/bin/env python3
"""Discovery harvest: pull candidate proteomics-GWAS papers (2023-07 .. 2026) from
Europe PMC, dedupe against the existing rows (by PMID/DOI/normalized title), and
write a raw candidate pool for refinement + agent verification.

Casts a wide net on purpose (recall over precision); refine_pool_prot.py and the
verification agents do the precision filtering. Includes published (SRC:MED) and
preprints (SRC:PPR). Stdlib-only; Europe PMC via curl, paged with cursorMark.
"""
import csv, json, os, re, subprocess, time, unicodedata, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = os.path.join(ROOT, "data", "pgwas_ids.csv")
OUT = os.path.join(ROOT, "data", "pgwas_harvest_candidates.csv")   # gitignored
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

DATEF = 'FIRST_PDATE:[2023-07-01 TO 2026-12-31]'
QUERIES = [
    '(pQTL OR pQTLs OR "protein quantitative trait loci" OR "protein quantitative trait locus")',
    '("plasma proteome" OR "serum proteome" OR "plasma proteomic" OR "proteogenomic" OR "proteo-genomic") AND ("genome-wide" OR GWAS OR pQTL)',
    '(SomaScan OR SomaLogic OR Olink OR "proximity extension assay" OR Proteograph OR "aptamer-based") AND ("genome-wide association" OR pQTL OR "quantitative trait loci")',
    '("mass spectrometry" OR "data-independent acquisition" OR DIA-MS OR "tandem mass tag") AND proteom* AND ("genome-wide association" OR pQTL)',
    '("genetic architecture" OR "genetic determinants" OR "genome-wide association") AND ("plasma protein" OR "circulating protein" OR "blood protein" OR "protein levels")',
]


def curl(url, max_time=30):
    try:
        return subprocess.run(["curl", "-sL", "--max-time", str(max_time), "-A", UA, url],
                              capture_output=True, text=True, timeout=max_time + 5).stdout
    except Exception:
        return ""


def norm_title(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def search(q, cap=900):
    """Page through Europe PMC for one query, return list of result dicts."""
    out, cursor, seen = [], "*", 0
    full = f"({q}) AND {DATEF} AND (SRC:MED OR SRC:PPR) AND HAS_ABSTRACT:Y"
    while True:
        url = (f"{EPMC}?query={urllib.parse.quote(full)}&format=json&pageSize=100"
               f"&resultType=core&cursorMark={urllib.parse.quote(cursor)}")
        try:
            data = json.loads(curl(url))
        except Exception:
            break
        res = data.get("resultList", {}).get("result", [])
        if not res:
            break
        out.extend(res)
        seen += len(res)
        nxt = data.get("nextCursorMark")
        if not nxt or nxt == cursor or seen >= cap:
            break
        cursor = nxt
        time.sleep(0.4)
    return out


def main():
    # build dedup keys from existing rows
    existing = list(csv.DictReader(open(IDS)))
    ex_pmid = {r["PMID"] for r in existing if r["PMID"]}
    ex_doi = {r["DOI"].lower() for r in existing if r["DOI"]}
    ex_title = {norm_title(r["resolved_title"]) for r in existing if r.get("resolved_title")}

    pool = {}                      # dedup key -> record
    for i, q in enumerate(QUERIES, 1):
        hits = search(q)
        print(f"query {i}: {len(hits)} hits")
        for h in hits:
            pmid = h.get("pmid", "")
            doi = (h.get("doi", "") or "").lower()
            title = h.get("title", "")
            nt = norm_title(title)
            key = ("pmid:" + pmid) if pmid else ("doi:" + doi) if doi else ("t:" + nt)
            if key in pool:
                continue
            pool[key] = dict(
                pmid=pmid, doi=h.get("doi", ""), title=title,
                authors=h.get("authorString", ""), year=h.get("pubYear", ""),
                journal=h.get("journalInfo", {}).get("journal", {}).get("title", "")
                        or h.get("bookOrReportDetails", "") or h.get("source", ""),
                source=h.get("source", ""), pubtype=";".join(h.get("pubTypeList", {}).get("pubType", [])),
                first_pdate=h.get("firstPublicationDate", ""),
                abstract=(h.get("abstractText", "") or "").replace("\n", " "))
        time.sleep(0.4)

    # drop ones already in the existing table
    rows, dropped = [], 0
    for rec in pool.values():
        if (rec["pmid"] and rec["pmid"] in ex_pmid) or \
           (rec["doi"] and rec["doi"].lower() in ex_doi) or \
           (norm_title(rec["title"]) in ex_title and norm_title(rec["title"])):
            dropped += 1
            continue
        rows.append(rec)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\nunique harvested: {len(pool)} | dropped as existing: {dropped} | "
          f"candidate pool: {len(rows)} -> {OUT}")


if __name__ == "__main__":
    main()
