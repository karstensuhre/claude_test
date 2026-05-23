#!/usr/bin/env python3
"""Consolidate agent-accepted candidates -> data/candidates.csv (for user approval).

- merge the 5 slice_*.jsonl
- drop preprint twins whose published version is also present
- rescue the Amish preprint (rejected by an agent only due to a 403 bot-block)
- flag candidates that may overlap existing UK-Biobank/NMR entries
- add PubMed/DOI links + an `approve` column the user toggles to y
"""
import csv, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "candidates.csv")

# preprint DOIs superseded by a published twin that is also in the accepted set
TWIN_DROP = {
    "10.1101/2024.11.11.24317110",   # Sun medRxiv -> HGG Adv 2025 (10.1016/j.xhgg.2025.100470)
    "10.1101/2024.12.04.24318368",   # Landstra medRxiv -> Nat Commun 2026 (10.1038/s41467-026-72542-1)
}
# overlap flags (possible duplicate of an existing UKB/NMR 249-metabolite study)
OVERLAP = {
    "10.1101/2024.07.30.24311254": "possible overlap with existing UKB-NMR entries (Karjalainen 2024 / Tambets / Zoodsma) — verify distinct",
    "10.1038/s41467-025-62126-w": "possible overlap with existing UKB-NMR entries (Zoodsma / Tambets) — verify distinct",
}

# Amish preprint rescued from a 403-only rejection (bot-block != dead)
AMISH = dict(
    pmid="", doi="10.1101/2025.08.04.667775", doi_http="403 (bot-blocked; resolves in browser)",
    year="2025", journal="bioRxiv (preprint)", reference="Jallow et al., bioRxiv 2025",
    biofluid="Serum", metabolic_traits="1,015 metabolites (Ex/GWAS)", platform="?",
    study_population="Amish (Old Order Amish), USA", n_traits="1,015", cohort_size="5,981",
    n_loci="149 functional variants assoc. with 519 metabolites",
    snippet="\"exome and genome-wide association study (Ex/GWAS) of 1,015 metabolites in serum samples from 5,981 Amish adults\"",
    confidence="medium",
    notes="rescued: agent rejected only for DOI 403 (bot-block); preprint; platform not stated in abstract")

COLS = ["approve", "confidence", "Year", "Reference", "Biofluid", "Metabolic_traits",
        "Platform", "Study_population", "N_Traits", "Cohort_size", "N_Loci",
        "PMID", "DOI", "PubMed_url", "DOI_url", "doi_http", "journal", "snippet", "notes"]


def conv(r):
    doi = r.get("doi", "") or ""
    pmid = r.get("pmid", "") or ""
    notes = r.get("notes", "") or ""
    if doi in OVERLAP:
        notes = (notes + "; " if notes else "") + OVERLAP[doi]
    return {
        "approve": "", "confidence": r.get("confidence", ""),
        "Year": str(r.get("year", "")), "Reference": r.get("reference", ""),
        "Biofluid": r.get("biofluid", ""), "Metabolic_traits": r.get("metabolic_traits", ""),
        "Platform": r.get("platform", ""), "Study_population": r.get("study_population", ""),
        "N_Traits": r.get("n_traits", ""), "Cohort_size": r.get("cohort_size", ""),
        "N_Loci": r.get("n_loci", ""), "PMID": pmid, "DOI": doi,
        "PubMed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
        "DOI_url": f"https://doi.org/{doi}" if doi else "",
        "doi_http": r.get("doi_http", ""), "journal": r.get("journal", ""),
        "snippet": r.get("snippet", ""), "notes": notes,
    }


def main():
    rows = []
    for fp in sorted(glob.glob(os.path.join(ROOT, "data", "agent_out", "slice_*.jsonl"))):
        for ln in open(fp):
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    rows = [r for r in rows if (r.get("doi", "") or "") not in TWIN_DROP]
    rows.append(AMISH)
    out = [conv(r) for r in rows]
    rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda x: (rank.get(x["confidence"], 3), -(int(x["Year"]) if str(x["Year"]).isdigit() else 0)))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(out)
    from collections import Counter
    print(f"wrote {len(out)} candidates -> {OUT}")
    print("by confidence:", dict(Counter(x["confidence"] for x in out)))
    print("by year:", dict(sorted(Counter(x["Year"] for x in out).items())))
    print("\nfinal candidate list:")
    for x in out:
        print(f'  [{x["confidence"]:6}] {x["Reference"]:34} {x["N_Traits"]:>8} traits, N={x["Cohort_size"]}  {("** "+x["notes"]) if "overlap" in x["notes"] else ""}')


if __name__ == "__main__":
    main()
