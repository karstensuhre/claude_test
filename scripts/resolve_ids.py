#!/usr/bin/env python3
"""Resolve PMID + DOI for each existing row via Europe PMC.

Strategy per row (first Ref_URL):
  1. Derive an identifier from the URL: DOI (regex, URL-decoded), PMID (/pubmed/N),
     PMCID (PMC\\d+), or Nature article path -> 10.1038/<path>.
  2. If none in URL, fetch the page and read citation_doi / citation_pmid meta tags.
  3. Query Europe PMC with the best identifier -> canonical PMID, DOI, title, journal, year.
Outputs data/gwas_ids.csv. Network failures are tolerated and flagged.
"""
import csv, json, os, re, subprocess, time, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = os.path.join(ROOT, "data", "gwas_existing.csv")
OUT = os.path.join(ROOT, "data", "gwas_ids.csv")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

DOI_RE = re.compile(r'(10\.\d{4,9}/[^\s"\'<>]+)')


def curl(url, max_time=25):
    try:
        r = subprocess.run(["curl", "-sL", "--max-time", str(max_time), "-A", UA, url],
                           capture_output=True, text=True, timeout=max_time + 5)
        return r.stdout
    except Exception:
        return ""


def clean_doi(d):
    d = urllib.parse.unquote(d)
    d = re.split(r'[);]', d)[0]
    d = re.sub(r'(v\d+)$', '', d)                 # medrxiv/biorxiv version suffix
    d = re.sub(r'(\.long|\.full|/abstract|/fulltext|/meta)$', '', d, flags=re.I)
    d = d.rstrip('.').rstrip('/')
    return d


def id_from_url(u):
    ud = urllib.parse.unquote(u)
    m = re.search(r'/pubmed/(\d+)', ud) or re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', ud)
    if m:
        return ("pmid", m.group(1))
    m = re.search(r'(PMC\d+)', ud)
    if m:
        return ("pmcid", m.group(1))
    m = DOI_RE.search(ud)
    if m:
        return ("doi", clean_doi(m.group(1)))
    m = re.search(r'nature\.com/articles/([^/?#]+)', ud)
    if m:
        return ("doi", "10.1038/" + m.group(1))
    return (None, None)


def meta_from_page(u):
    html = curl(u)
    doi = pmid = None
    m = re.search(r'<meta[^>]+name=["\']citation_doi["\'][^>]+content=["\']([^"\']+)', html, re.I) \
        or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_doi["\']', html, re.I)
    if m:
        doi = clean_doi(m.group(1))
    m = re.search(r'<meta[^>]+name=["\']citation_pmid["\'][^>]+content=["\'](\d+)', html, re.I)
    if m:
        pmid = m.group(1)
    return doi, pmid


def epmc_query(q):
    url = f"{EPMC}?query={urllib.parse.quote(q)}&format=json&pageSize=1&resultType=lite"
    out = curl(url)
    try:
        res = json.loads(out)["resultList"]["result"]
        return res[0] if res else None
    except Exception:
        return None


def resolve(idtype, idval):
    if idtype == "doi":
        rec = epmc_query(f'DOI:"{idval}"')
    elif idtype == "pmid":
        rec = epmc_query(f'EXT_ID:{idval} AND SRC:MED')
    elif idtype == "pmcid":
        rec = epmc_query(f'PMCID:{idval}')
    else:
        rec = None
    return rec


def main():
    rows = list(csv.DictReader(open(INP)))
    out = []
    for r in rows:
        rid = r["row_id"]
        url = (r["Ref_URLs"].split(" ; ")[0]).strip()
        idtype, idval = id_from_url(url)
        method = idtype or "none"
        if idtype is None and url:
            doi, pmid = meta_from_page(url)
            if doi:
                idtype, idval, method = "doi", doi, "page-meta-doi"
            elif pmid:
                idtype, idval, method = "pmid", pmid, "page-meta-pmid"
            time.sleep(0.3)
        rec = resolve(idtype, idval) if idtype else None
        time.sleep(0.25)
        doi = pmid = title = journal = year = src = ""
        status = "unresolved"
        if rec:
            doi = rec.get("doi", "") or (idval if idtype == "doi" else "")
            pmid = rec.get("pmid", "")
            title = rec.get("title", "")
            journal = rec.get("journalTitle", "") or rec.get("bookOrReportDetails", "")
            year = rec.get("pubYear", "")
            src = rec.get("source", "")            # MED, PPR(preprint), PMC, etc.
            status = "resolved"
        else:
            # keep whatever we extracted even if EPMC had no record
            if idtype == "doi":
                doi = idval
            if idtype == "pmid":
                pmid = idval
            status = "partial" if (doi or pmid) else "unresolved"
        out.append(dict(row_id=rid, Reference=r["Reference"], orig_url=url,
                        method=method, DOI=doi, PMID=pmid, epmc_source=src,
                        resolved_title=title, resolved_journal=journal,
                        resolved_year=year, status=status))
        print(f'{rid:>3} {status:10} method={method:14} DOI={doi or "-":40} PMID={pmid or "-"}')
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    n_doi = sum(1 for o in out if o["DOI"])
    n_pmid = sum(1 for o in out if o["PMID"])
    print(f"\nDOI resolved: {n_doi}/98 | PMID resolved: {n_pmid}/98 | wrote {OUT}")


if __name__ == "__main__":
    main()
