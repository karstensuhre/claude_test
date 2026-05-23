#!/usr/bin/env python3
"""Check liveness of every link in the homogenized table.

Sources: original reference URL(s) + resolved PubMed URL + resolved DOI URL.
Real-browser UA, HEAD then GET fallback, parallel. Classify:
  alive  : final HTTP 2xx (a paywalled journal landing page is alive)
  blocked: 403/429 -> bot-blocked, unverifiable (NOT dead)
  dead   : 404/410, DNS failure, timeout, or no response
"""
import csv, os, subprocess
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = os.path.join(ROOT, "data", "gwas_homogenized.csv")
OUT = os.path.join(ROOT, "data", "linkcheck.csv")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def probe(url):
    def run(method):
        cmd = ["curl", "-s", "-o", "/dev/null", "-A", UA, "--max-time", "25",
               "-w", "%{http_code} %{url_effective}", "-L"]
        if method == "HEAD":
            cmd.append("-I")
        cmd.append(url)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            parts = r.stdout.strip().split(" ", 1)
            return parts[0], (parts[1] if len(parts) > 1 else "")
        except Exception:
            return "000", ""
    code, final = run("HEAD")
    if code in ("000", "403", "405", "429", "501"):   # retry with GET
        code2, final2 = run("GET")
        if code2 not in ("000",):
            code, final = code2, final2
    try:
        c = int(code)
    except ValueError:
        c = 0
    if 200 <= c < 300:
        cls = "alive"
    elif c in (403, 429):
        cls = "blocked"
    elif c in (401,):
        cls = "alive"          # auth wall = page exists
    elif c in (404, 410) or c == 0:
        cls = "dead"
    else:
        cls = f"other-{c}"
    return code, cls, final


def main():
    rows = list(csv.DictReader(open(INP)))
    jobs = []   # (row_id, type, url)
    for r in rows:
        for u in r["orig_url"].split(" ; "):
            if u.strip():
                jobs.append((r["row_id"], "orig", u.strip()))
        if r["PubMed_url"]:
            jobs.append((r["row_id"], "pubmed", r["PubMed_url"]))
        if r["DOI_url"]:
            jobs.append((r["row_id"], "doi", r["DOI_url"]))

    results = [None] * len(jobs)

    def work(i):
        rid, typ, url = jobs[i]
        code, cls, final = probe(url)
        results[i] = dict(row_id=rid, link_type=typ, url=url, http=code, status=cls, final_url=final)

    with ThreadPoolExecutor(max_workers=10) as ex:
        list(ex.map(work, range(len(jobs))))

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["row_id", "link_type", "url", "http", "status", "final_url"])
        w.writeheader(); w.writerows(results)

    from collections import Counter
    by_status = Counter(r["status"] for r in results)
    print(f"checked {len(results)} links across {len(rows)} rows -> {OUT}")
    for s, c in by_status.most_common():
        print(f"  {c:4d}  {s}")
    print("\nDEAD links (need attention):")
    for r in results:
        if r["status"] == "dead":
            print(f'  row {r["row_id"]:>3} [{r["link_type"]}] http={r["http"]} {r["url"]}')


if __name__ == "__main__":
    main()
