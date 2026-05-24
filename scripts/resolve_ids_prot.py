#!/usr/bin/env python3
"""Resolve PMID + DOI for each existing proteomics row via Europe PMC.

Per row, in order, stopping at the first that resolves:
  1. Identifier from the Reference-cell URL: DOI (regex), PMID (/pubmed/N),
     PMCID, Nature path -> 10.1038/<path>, bioRxiv/medRxiv path -> 10.1101/...
  2. Page citation_doi / citation_pmid meta tags (for cell.com PII URLs etc.).
  3. Author+year(+journal token) fallback query, accepting only an unambiguous
     single hit; ambiguous/multi hits are left unresolved and flagged.
Conference-abstract hosts (eventpilot/ativ.me) have no DOI and stay unresolved.
Outputs data/pgwas_ids.csv. Network failures are tolerated and flagged.
"""
import csv, json, os, re, subprocess, time, unicodedata, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = os.path.join(ROOT, "data", "pgwas_existing.csv")
OUT = os.path.join(ROOT, "data", "pgwas_ids.csv")
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
    d = re.sub(r'(v\d+)$', '', d)
    d = re.sub(r'(\.long|\.full|/abstract|/fulltext|/meta)$', '', d, flags=re.I)
    return d.rstrip('.').rstrip('/')


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


def epmc(q, n=1):
    url = f"{EPMC}?query={urllib.parse.quote(q)}&format=json&pageSize={n}&resultType=lite"
    try:
        return json.loads(curl(url))["resultList"].get("result", [])
    except Exception:
        return []


def resolve_by_id(idtype, idval):
    if idtype == "doi":
        r = epmc(f'DOI:"{idval}"')
    elif idtype == "pmid":
        r = epmc(f'EXT_ID:{idval} AND SRC:MED')
    elif idtype == "pmcid":
        r = epmc(f'PMCID:{idval}')
    else:
        r = []
    return r[0] if r else None


def parse_ref(ref):
    """Extract (first-author surname, journal token, year) from a Reference string."""
    year = None
    ys = re.findall(r'\b(19|20)\d{2}\b', ref)
    if ys:
        year = re.findall(r'\b((?:19|20)\d{2})\b', ref)[0]
    auth = ref.split()[0].strip(",.") if ref.split() else ""
    auth = "".join(c for c in unicodedata.normalize("NFKD", auth) if not unicodedata.combining(c))
    # journal token: a distinctive word inside the first parenthesis (skip Nature/Nat which is ambiguous-ok)
    jr = ""
    m = re.search(r'\(([^)]+)\)', ref)
    if m:
        inside = re.sub(r'[,0-9]', ' ', m.group(1))
        toks = [t for t in inside.split() if len(t) > 3 and t.lower() not in ("preprint",)]
        jr = toks[0] if toks else ""
    return auth, jr, year


def fallback(ref):
    auth, jr, year = parse_ref(ref)
    if not auth or not year:
        return None, "no-author-year"
    q = f'AUTH:"{auth}" AND PUB_YEAR:{year}'
    hits = epmc(q, n=25)
    time.sleep(0.25)
    if jr:
        jl = jr.lower()
        narrowed = [h for h in hits if jl in (h.get("journalTitle", "") or "").lower()]
        if narrowed:
            hits = narrowed
    if len(hits) == 1:
        return hits[0], "fallback-unique"
    return None, f"fallback-ambiguous({len(hits)})"


SKIP_HOST = ("eventpilot", "ativ.me")


def main():
    rows = list(csv.DictReader(open(INP)))
    out = []
    for r in rows:
        rid = r["row_id"]
        url = (r["Ref_URLs"].split(" ; ")[0]).strip()
        idtype, idval = id_from_url(url)
        method = idtype or "none"
        rec = resolve_by_id(idtype, idval) if idtype else None
        time.sleep(0.25)
        if rec is None and idtype is None and url and not any(h in url for h in SKIP_HOST):
            doi, pmid = meta_from_page(url)
            time.sleep(0.3)
            if doi:
                idtype, idval, method = "doi", doi, "page-meta-doi"
            elif pmid:
                idtype, idval, method = "pmid", pmid, "page-meta-pmid"
            rec = resolve_by_id(idtype, idval) if idtype else None
            time.sleep(0.25)
        flag = ""
        if rec is None:
            rec, fmethod = fallback(r["Reference"])
            if rec:
                method = fmethod
                idtype = "doi" if rec.get("doi") else "pmid"
            elif any(h in url for h in SKIP_HOST):
                method = "conf-abstract"
            else:
                method = fmethod
                flag = "review"
        doi = pmid = title = journal = year = src = ""
        status = "unresolved"
        if rec:
            doi = rec.get("doi", "") or (idval if idtype == "doi" else "")
            pmid = rec.get("pmid", "")
            title = rec.get("title", "")
            journal = rec.get("journalTitle", "") or rec.get("bookOrReportDetails", "")
            year = rec.get("pubYear", "")
            src = rec.get("source", "")
            status = "resolved"
        else:
            if idtype == "doi":
                doi = idval
            if idtype == "pmid":
                pmid = idval
            status = "partial" if (doi or pmid) else "unresolved"
        out.append(dict(row_id=rid, Reference=r["Reference"], orig_url=url,
                        method=method, DOI=doi, PMID=pmid, epmc_source=src,
                        resolved_title=title, resolved_journal=journal,
                        resolved_year=year, status=status, flag=flag))
        print(f'{rid:>3} {status:10} {method:18} DOI={doi or "-":42} PMID={pmid or "-"}')
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    n = len(out)
    n_doi = sum(1 for o in out if o["DOI"])
    n_pmid = sum(1 for o in out if o["PMID"])
    n_un = sum(1 for o in out if o["status"] == "unresolved")
    print(f"\nDOI {n_doi}/{n} | PMID {n_pmid}/{n} | unresolved {n_un} | wrote {OUT}")


if __name__ == "__main__":
    main()
