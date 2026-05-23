#!/usr/bin/env python3
"""Homogenize the 98 existing rows (conservative: normalize labels/format only).

Merges data/gwas_existing.csv + data/gwas_ids.csv ->
  data/gwas_homogenized.csv   (display rows + PubMed/DOI links + Year + notes + flag)
  data/homogenize_changelog.csv (every label change, for the user to skim)

Original information is never discarded: when a canonical label drops detail, the
verbatim original is preserved in the `notes` column. Ambiguous cells are flagged,
never guessed.
"""
import csv, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "data", "gwas_existing.csv")
IDS = os.path.join(ROOT, "data", "gwas_ids.csv")
OUT = os.path.join(ROOT, "data", "gwas_homogenized.csv")
LOG = os.path.join(ROOT, "data", "homogenize_changelog.csv")

# --- Biofluid canonicalization -------------------------------------------------
BIOFLUID = {
    "Plasma": "Plasma", "Serum": "Serum", "Urine": "Urine", "Blood": "Blood",
    "Red blood cells (RBC)": "RBC", "RBC": "RBC",
    "Plasma and Serum": "Plasma + Serum", "Plasma + serum": "Plasma + Serum",
    "Plasma + RBCs": "Plasma + RBC",
    "Urine and Plasma": "Urine + Plasma", "Urine & Plasma": "Urine + Plasma",
    "Cerebrospinal fluid (CSF)": "CSF",
    "Cerebrospinal fluid (CSF) and brain": "CSF + brain",
    "Saliva": "Saliva", "Skeletal muscle (duck)": "Skeletal muscle (duck)",
    "Predominantly plasma": "Plasma",
    "Plasma, mitochondrial DNA": "Plasma",
    "Plasma, before/after liquid meal": "Plasma",
    "NA": "?", "?": "?",
}
# --- Platform canonicalization (Tech (Vendor/platform)) ------------------------
PLATFORM = {
    "Metabolon HD4": "MS (Metabolon HD4)",
    "MS (Metabolon)": "MS (Metabolon)",
    "LC-MS (Metabolon)": "LC-MS (Metabolon)",
    "Metabolon HD2/HD4": "MS (Metabolon HD2/HD4)",
    "Metabolon/Broad platform": "MS (Metabolon, Broad)",
    "MS (Biocrates)": "MS (Biocrates)",
    "Biocrates p150": "MS (Biocrates p150)",
    "Biocrates p180": "MS (Biocrates p180)",
    "NMR": "NMR",
    "NMR (Nightingale)": "NMR (Nightingale)",
    "NMR (Brainshake)": "NMR (Nightingale)",       # Brainshake = former Nightingale
    "Nightingale": "NMR (Nightingale)",
    "NMR (Chenomx)": "NMR (Chenomx)", "Chenomx": "NMR (Chenomx)",
    "GC": "GC", "Gas chromatography": "GC",
    "gas chromatography or gas-liquid chromatography": "GC",
    "GC-MS": "GC-MS",
    "MS": "MS", "LC-MS": "LC-MS", "HPLC-MS/MS": "LC-MS/MS",
    "UPLC- MS/MS or UPLC- ESI-MS/MS": "LC-MS/MS",
    "Targeted Lipidomics using UPLC/ESI-MS/MS": "LC-MS/MS (lipidomics)",
    "in-house LC-MS/MS platform for polar lipophilic metabolites": "LC-MS/MS (in-house)",
    "in-house": "in-house", "in-house platform described here": "in-house",
    "NMR + MS": "NMR + MS",
    "MS (Metabolon & Biocrates)": "MS (Metabolon + Biocrates)",
    "Biocrates + Metabolon": "MS (Biocrates + Metabolon)",
    "Biocrates p180, Nightingale NMR, Metabolon HD4": "Multiple (Biocrates p180 + Nightingale + Metabolon HD4)",
    "Metabolon HD4 + Biocrates p180 + Nightingale": "Multiple (Metabolon HD4 + Biocrates p180 + Nightingale)",
    "Biocrates p150 & Metabolon HD2": "MS (Biocrates p150 + Metabolon HD2)",
    "Lipid-related metabolites from Metabolon platform": "MS (Metabolon)",
    "Lipotype platform": "MS (Lipotype)", "Lipotype GmbH": "MS (Lipotype)",
    "Diverse": "Multiple",
    "Broad institute": "MS (Broad)",
    "Nightingale platform (limited to 16 selected metabolites)": "NMR (Nightingale)",
    "Nightingale Health urine NMR platform": "NMR (Nightingale)",
    "Metabolon HD4, limited to acetaminophen metabolites": "MS (Metabolon HD4)",
    "600 MHz Bruker AVANCE III HD NMR spectrometer": "NMR",
    "Uses two LC-MS methods on an Agilent system & whole genome sequencing": "LC-MS",
    "LC–MS/MS and SPME-GC-HRMS": "LC-MS/MS + GC-HRMS",
    "West Coast Metabolomics Center at University of California Davis": "?",
    "amino acids, hormones, water-soluble vitamins (WSV), fat-soluble vitamins (FSV), and metal elements": "?",
    "plasma eicosanoids and related metabolites, including PUFAs": "?",
    "NA": "?", "?": "?", "not specified": "?", "": "?",
}
# Platform cells that actually describe traits, not a platform -> flag for user
PLATFORM_FLAG = {
    "amino acids, hormones, water-soluble vitamins (WSV), fat-soluble vitamins (FSV), and metal elements",
    "plasma eicosanoids and related metabolites, including PUFAs",
    "West Coast Metabolomics Center at University of California Davis",
}


def main():
    ex = {r["row_id"]: r for r in csv.DictReader(open(EX))}
    ids = {r["row_id"]: r for r in csv.DictReader(open(IDS))}
    changelog = []
    out = []
    for rid, r in ex.items():
        idr = ids.get(rid, {})
        notes = []
        flag = ""

        # Biofluid
        bf0 = r["Biofluid"]
        bf = BIOFLUID.get(bf0, bf0)
        if bf != bf0:
            changelog.append(("Biofluid", rid, bf0, bf))
            if bf0 not in ("NA", "?") and bf0.lower() not in (bf.lower(),):
                notes.append(f"biofluid orig: '{bf0}'")
        if bf == "?":
            notes.append("biofluid not specified in source"); flag = "review"

        # Platform
        pf0 = r["Platform"]
        pf = PLATFORM.get(pf0, pf0)
        if pf != pf0:
            changelog.append(("Platform", rid, pf0, pf))
            notes.append(f"platform orig: '{pf0}'")
        if pf0 in PLATFORM_FLAG:
            flag = "review"; notes.append("platform field looks mislabeled in source")
        if pf == "?":
            flag = flag or "review"

        # IDs / links
        doi = idr.get("DOI", "").strip()
        pmid = idr.get("PMID", "").strip()
        src = idr.get("epmc_source", "")
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        doi_url = f"https://doi.org/{doi}" if doi else ""
        # preprint?
        is_pre = src == "PPR" or any(x in r["Ref_URLs"].lower() for x in ("medrxiv", "biorxiv"))
        if not pmid:
            notes.append("preprint/not in PubMed" if is_pre else "PMID unresolved")
        if not doi:
            notes.append("DOI unresolved"); flag = flag or "review"

        # Year
        m = re.search(r"\b(20\d{2}|19\d{2})\b", r["Reference"])
        year = idr.get("resolved_year") or (m.group(1) if m else "")

        out.append(dict(
            row_id=rid, Year=year, Biofluid=bf,
            Metabolic_traits=r["Metabolic_traits"], Platform=pf,
            Study_population=r["Study_population"], N_Traits=r["N_Traits"],
            Cohort_size=r["Cohort_size"], N_Loci=r["N_Loci"],
            Reference=r["Reference"], PMID=pmid, DOI=doi,
            PubMed_url=pubmed_url, DOI_url=doi_url,
            orig_url=r["Ref_URLs"], notes="; ".join(notes), flag=flag))

    out.sort(key=lambda x: (int(x["Year"]) if x["Year"].isdigit() else 0, int(x["row_id"])))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    with open(LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["column", "row_id", "original", "homogenized"]); w.writerows(changelog)

    nflag = sum(1 for o in out if o["flag"])
    npub = sum(1 for o in out if o["PMID"])
    ndoi = sum(1 for o in out if o["DOI"])
    print(f"rows: {len(out)} | PubMed links: {npub} | DOI links: {ndoi} | flagged for review: {nflag}")
    print(f"label changes logged: {len(changelog)}  -> {LOG}")
    print(f"wrote {OUT}")
    print("\nflagged rows:")
    for o in out:
        if o["flag"]:
            print(f'  row {o["row_id"]:>3} ({o["Reference"]}): {o["notes"]}')


if __name__ == "__main__":
    main()
