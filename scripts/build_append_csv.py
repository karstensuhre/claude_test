#!/usr/bin/env python3
"""Emit an append-ready CSV of new metabolomics-GWAS papers, shaped to the LIVE
TablePress metabolomics table (table id 7) for
  wp-admin -> TablePress -> Import -> "Append rows to existing table" -> table 7.

TablePress append is positional, so the file must have exactly the live table's
eight columns, in order, and NO header row (Reference is the LAST column there):

  Biofluid | Metabolic traits | Platform | Study population | # Traits | Cohort size | # Loci | Reference

Mapping from data/candidates.csv (its columns already match, so this is a
pass-through + a hyperlink on the Reference cell):
  Reference -> the Reference text hyperlinked (DOI, else PubMed), single-quoted
               attrs so the cell stays free of double quotes. Comma style is kept
               (e.g. "Landstra et al., Nat Commun 2026") to match table 7.

Row selection: rows with approve in {y,yes,x,1,true}; if NONE are approved yet,
ALL candidates are emitted with a notice. Stdlib-only; no header row written.
(Proteomics analogue: build_append_csv_prot.py -> table 4.)
"""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, "data", "candidates.csv")
OUT = os.path.join(ROOT, "data", "gwas_append.csv")
APPROVED = {"y", "yes", "x", "1", "true"}

# (live table 7 column  <-  candidates.csv field); Reference handled separately, placed last
COLMAP = [("Biofluid", "Biofluid"), ("Metabolic traits", "Metabolic_traits"),
          ("Platform", "Platform"), ("Study population", "Study_population"),
          ("# Traits", "N_Traits"), ("Cohort size", "Cohort_size"), ("# Loci", "N_Loci")]


def reference_cell(r):
    txt = r["Reference"].strip()
    url = (r["DOI_url"] or r["PubMed_url"]).strip()
    return f"<a href='{url}'>{txt}</a>" if url else txt


def main():
    rows = list(csv.DictReader(open(CAND)))
    approved = [r for r in rows if r["approve"].strip().lower() in APPROVED]
    if approved:
        sel, mode = approved, f"approve=y ({len(approved)} of {len(rows)})"
    else:
        sel, mode = rows, f"ALL {len(rows)} candidates (no approve=y set yet)"

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in sel:
            w.writerow([r[src] for _, src in COLMAP] + [reference_cell(r)])

    print(f"wrote {OUT}: {len(sel)} rows ({mode}), 8 cols, no header — append to TablePress table 7")
    print("columns: " + " | ".join(lbl for lbl, _ in COLMAP) + " | Reference")
    print("\npreview (first 3 rows):")
    for r in sel[:3]:
        print(f"  • {r['Biofluid']} | {r['Metabolic_traits'][:26]} | {r['Platform'][:22]} | "
              f"{r['Study_population'][:20]} | {r['N_Traits'][:14]} | {r['Cohort_size'][:16]} | "
              f"{r['N_Loci'][:14]} | {r['Reference']}")


if __name__ == "__main__":
    main()
