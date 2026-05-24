#!/usr/bin/env python3
"""Consolidate the agent verdicts into the user-facing candidate list.

Merges data/pgwas_agent_out/slice_*.jsonl (verdicts) with slice_*.in.jsonl
(metadata) by idx. Keeps decisions "keep" + "borderline" -> data/pgwas_candidates.csv
(with an empty `approve` column for the curator). Records every "exclude" with its
reason in data/pgwas_rejections.md so the filtering is auditable.

Two extra dedup safety nets (the harvest-time dedup can miss these):
  - drop any kept candidate that is **already in the existing catalog** — matched by
    DOI/PMID against data/pgwas_ids.csv, or by title-Jaccard vs the existing
    resolved_title (logged as `already_in_catalog`);
  - fold **preprint -> published twins** among candidates (same first author,
    title-Jaccard >= 0.55, exactly when one of the pair lacks a PMID), keeping the
    published version and noting the folded preprint DOI.
Stdlib-only.
"""
import csv, glob, json, os, re, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AG = os.path.join(ROOT, "data", "pgwas_agent_out")
IDS = os.path.join(ROOT, "data", "pgwas_ids.csv")
OUT = os.path.join(ROOT, "data", "pgwas_candidates.csv")
REJ = os.path.join(ROOT, "data", "pgwas_rejections.md")
TWIN_J = 0.55

FIELDS = ["approve", "decision", "category", "confidence", "Year", "Reference",
          "Sample_type", "Platform", "Platform_class", "Study_population", "N_proteins",
          "N_samples", "N_cis_pQTL", "N_trans_pQTL", "N_pQTL_total", "PMID", "DOI",
          "PubMed_url", "DOI_url", "journal", "snippet", "notes", "overlap_flag"]
ORDER = {"high": 0, "medium": 1, "low": 2}


def nt(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def jacc(a, b):
    a, b = set(a.split()), set(b.split())
    return len(a & b) / len(a | b) if (a and b) else 0.0


def g(d, *keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return ""


def first_author(ref):
    m = re.match(r"\s*([A-Za-z'\-]+)", ref or "")
    return m.group(1).lower() if m else ""


def main():
    meta = {}
    for fn in glob.glob(os.path.join(AG, "slice_*.in.jsonl")):
        for line in open(fn):
            if line.strip():
                r = json.loads(line)
                meta[r["idx"]] = r
    verdicts = {}
    for fn in glob.glob(os.path.join(AG, "slice_[0-9].jsonl")):
        for line in open(fn):
            if line.strip():
                r = json.loads(line)
                verdicts[r["idx"]] = r
    print(f"meta {len(meta)} | verdicts {len(verdicts)}")

    # existing catalog, from resolved IDs (DOI/PMID exact + resolved_title for fuzzy match)
    exrows = list(csv.DictReader(open(IDS)))
    ex_doi = {r["DOI"].lower(): r["Reference"] for r in exrows if r["DOI"]}
    ex_pmid = {r["PMID"]: r["Reference"] for r in exrows if r["PMID"]}
    ex_titles = [(r["Reference"], nt(r["resolved_title"])) for r in exrows if r.get("resolved_title")]

    rejected = []
    # pass 1: split verdicts; drop excludes and candidates already in the catalog
    keep_raw = []
    for idx, v in sorted(verdicts.items()):
        m = meta.get(idx, {})
        title = m.get("title", "")
        doi = (g(v, "doi") or m.get("doi", "")).strip()
        pmid = (g(v, "pmid") or m.get("pmid", "")).strip()
        decision = v.get("decision", "exclude")
        ref = g(v, "Reference") or (m.get("authors", "").split(",")[0] + f", {m.get('year','')}")
        if decision == "exclude":
            rejected.append((v.get("category", "exclude"), ref, title, g(v, "notes"), pmid, doi))
            continue
        # already in the existing catalog?
        ov = None
        if doi and doi.lower() in ex_doi:
            ov = ex_doi[doi.lower()]
        elif pmid and pmid in ex_pmid:
            ov = ex_pmid[pmid]
        else:
            nti = nt(title)
            for eref, ent in ex_titles:
                if nti and ent and jacc(nti, ent) >= TWIN_J:
                    ov = eref
                    break
        if ov:
            rejected.append(("already_in_catalog", ref, title, f"already in catalog as: {ov}", pmid, doi))
            continue
        keep_raw.append(dict(idx=idx, v=v, m=m, title=title, doi=doi, pmid=pmid, ref=ref,
                             source=m.get("source", "")))

    # pass 2: fold preprint -> published twins among candidates (published first)
    keep_raw.sort(key=lambda k: (0 if k["pmid"] else 1, 0 if k["source"] == "MED" else 1))
    groups = []
    for k in keep_raw:
        fa, nti = first_author(k["ref"]), nt(k["title"])
        placed = False
        for grp in groups:
            r0 = grp[0]
            # only fold when at least one of the pair is a preprint (no PMID) -> avoids merging two distinct published papers
            if fa and fa == first_author(r0["ref"]) and nti and jacc(nti, nt(r0["title"])) >= TWIN_J \
               and (not k["pmid"] or not r0["pmid"]):
                grp.append(k)
                placed = True
                break
        if not placed:
            groups.append([k])

    kept = []
    for grp in groups:
        k = grp[0]
        v, m = k["v"], k["m"]
        folded = grp[1:]
        twin_note = ""
        if folded:
            twin_note = "folds preprint/twin: " + "; ".join(x["doi"] or x["title"][:30] for x in folded)
            for x in folded:
                rejected.append(("twin_of_kept", x["ref"], x["title"],
                                 f"preprint/twin of kept: {k['ref']} ({k['doi']})", x["pmid"], x["doi"]))
        notes = g(v, "notes")
        if twin_note:
            notes = (notes + " · " + twin_note).strip(" ·")
        pmid, doi = k["pmid"], k["doi"]
        kept.append(dict(
            approve="", decision=v.get("decision"), category=g(v, "category"),
            confidence=g(v, "confidence") or "medium", Year=g(v, "Year") or m.get("year", ""),
            Reference=k["ref"], Sample_type=g(v, "Sample_type"), Platform=g(v, "Platform"),
            Platform_class=g(v, "Platform_class"), Study_population=g(v, "Study_population"),
            N_proteins=g(v, "N_proteins"), N_samples=g(v, "N_samples"),
            N_cis_pQTL=g(v, "N_cis_pQTL"), N_trans_pQTL=g(v, "N_trans_pQTL"),
            N_pQTL_total=g(v, "N_pQTL_total"), PMID=pmid, DOI=doi,
            PubMed_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            DOI_url=f"https://doi.org/{doi}" if doi else "",
            journal=m.get("journal", ""), snippet=g(v, "snippet"),
            notes=notes, overlap_flag=""))

    # sort: keep before borderline, then confidence, then year desc
    kept.sort(key=lambda r: (0 if r["decision"] == "keep" else 1,
                             ORDER.get(r["confidence"], 3), -int(r["Year"] or 0)))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(kept)

    # rejections markdown, grouped by category
    rejected.sort()
    with open(REJ, "w", encoding="utf-8") as f:
        f.write("# pGWAS candidate rejections (auditable)\n\n")
        f.write(f"{len(rejected)} of {len(verdicts)} verified candidates were dropped: most are "
                "*not* new primary protein-GWAS (they reuse existing pQTLs, are non-human, reviews, "
                "methods/databases, or do no genome-wide pQTL discovery); a few were already in the "
                "existing catalog (`already_in_catalog`) or are preprint/version twins of a kept "
                "paper (`twin_of_kept`). Grouped by reason; each links its PMID/DOI.\n\n")
        cur = None
        for cat, ref, title, notes, pmid, doi in rejected:
            if cat != cur:
                f.write(f"\n## {cat}\n\n")
                cur = cat
            link = f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "")
            f.write(f"- **{ref or title[:60]}** — {title} {('['+link+']') if link else ''}"
                    f"{(' — ' + notes) if notes else ''}\n")

    nkeep = sum(1 for r in kept if r["decision"] == "keep")
    nbord = sum(1 for r in kept if r["decision"] == "borderline")
    nov = sum(1 for r in kept if r["overlap_flag"])
    print(f"candidates: {len(kept)} ({nkeep} keep / {nbord} borderline), {nov} overlap-flagged -> {OUT}")
    print(f"rejections: {len(rejected)} -> {REJ}")
    import collections
    print("kept platform classes:", dict(collections.Counter(r["Platform_class"] for r in kept)))


if __name__ == "__main__":
    main()
