#!/usr/bin/env python3
"""Emit an append-ready CSV of new pGWAS papers, shaped to the LIVE TablePress
proteomics table (table id 4) so it can be uploaded via
  wp-admin -> TablePress -> Import -> "Append rows to existing table" -> table 4
(or imported from the raw file URL).

TablePress append is positional, so the file must have exactly the live table's
six columns, in order, and NO header row:

  Reference | #Samples in study | Study population | #Proteins assayed | #pQTLs reported | Platform type

Mapping from data/pgwas_candidates.csv:
  Reference          -> "<Author et al. (Journal Year)>" hyperlinked (DOI, else PubMed).
                        TablePress renders HTML in cells; single-quoted attrs keep the
                        cell free of double quotes for clean CSV.
  #Samples in study  -> N_samples         (blank if only "NR" in the abstract)
  Study population   -> Study_population
  #Proteins assayed  -> N_proteins        (blank if "NR")
  #pQTLs reported    -> composed from N_cis/N_trans/N_pQTL_total in the source's style
  Platform type      -> Platform detail   (falls back to Platform_class if unstated)

Row selection: rows with approve in {y,yes,x,1,true}. If NONE are approved yet,
ALL candidates are emitted with a notice — set approve=y in pgwas_candidates.csv
and re-run to get just your accepted subset. Stdlib-only; no header row written.
"""
import csv, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, "data", "pgwas_candidates.csv")
OUT = os.path.join(ROOT, "data", "pgwas_append.csv")
APPROVED = {"y", "yes", "x", "1", "true"}


def val(x):
    """Treat empty / 'NR' (not reported in abstract) as blank."""
    x = (x or "").strip()
    return "" if x.upper() in ("", "NR", "N/A", "NA") else x


def fmt_ref(ref):
    """'Soremekun et al., Nat Genet 2026' -> 'Soremekun et al. (Nat Genet 2026)' (source style)."""
    ref = ref.strip()
    m = re.match(r"^(.*?),\s*(.+)$", ref)
    return f"{m.group(1)} ({m.group(2)})" if m else ref


def compose_pqtl(r):
    cis, trans, total = val(r["N_cis_pQTL"]), val(r["N_trans_pQTL"]), val(r["N_pQTL_total"])
    nz = lambda x: x if re.fullmatch(r"[\d,]+", x) else ""   # keep only bare counts
    ncis, ntrans, ntot = nz(cis), nz(trans), nz(total)
    paren = f" ({ncis} cis, {ntrans} trans)" if (ncis and ntrans) else ""
    if ntot:
        return f"{ntot} pQTLs{paren}"
    if total:                       # non-numeric total text, e.g. "399 independent associations"
        return f"{total}{paren}"
    if ncis and ntrans:
        return f"{ncis} cis, {ntrans} trans pQTLs"
    if ncis:
        return f"{ncis} cis-pQTLs"
    if ntrans:
        return f"{ntrans} trans-pQTLs"
    return cis or trans             # last-resort free text from the abstract


def reference_cell(r):
    txt = fmt_ref(r["Reference"])
    url = (r["DOI_url"] or r["PubMed_url"]).strip()
    return f"<a href='{url}'>{txt}</a>" if url else txt


def platform_cell(r):
    p = r["Platform"].strip()
    if not p or p.upper().startswith("NR"):
        p = r["Platform_class"].strip()
    return p


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
            w.writerow([reference_cell(r), val(r["N_samples"]), r["Study_population"],
                        val(r["N_proteins"]), compose_pqtl(r), platform_cell(r)])

    print(f"wrote {OUT}: {len(sel)} rows ({mode}), 6 cols, no header — append to TablePress table 4")
    print("columns: Reference | #Samples | Study population | #Proteins | #pQTLs reported | Platform type")
    print("\npreview (first 3 rows):")
    for r in sel[:3]:
        print(f"  • {fmt_ref(r['Reference'])} | {val(r['N_samples']) or '—'} | "
              f"{(r['Study_population'] or '—')[:34]} | {val(r['N_proteins']) or '—'} | "
              f"{compose_pqtl(r) or '—'} | {platform_cell(r)[:28]}")


if __name__ == "__main__":
    main()
