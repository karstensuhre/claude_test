#!/usr/bin/env python3
"""Refine the 959-record harvest into a high-precision candidate pool.

A true 'GWAS with metabolomics' = genome-wide association / mQTL where the
PHENOTYPE is a panel of metabolites/lipids measured by MS or NMR in humans.
We tighten by requiring GWAS + metabolome signals (title-weighted) and excluding
the big false-positive classes: Mendelian randomization, polygenic scores,
reviews, single-omics that aren't metabolomics, and single-trait biochemical GWAS.
Writes data/pool_refined.csv (sorted by score) for agent verification.
"""
import csv, os, re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = os.path.join(ROOT, "data", "harvest_candidates.csv")
OUT = os.path.join(ROOT, "data", "pool_refined.csv")

GWAS_T = re.compile(r"genome-wide association|genome wide association|\bGWAS\b|\bmGWAS\b|\bmQTL\b|metabolite quantitative trait loc|genetic architecture|genetic determinants|genetic basis|genetic control|genetic landscape|fine-mapping", re.I)
METAB_T = re.compile(r"metabolom|metabonom|metabolite|metabolic trait|lipidom|lipid species|lipid-?related|sphingolipid|acylcarnitine|bile acid|fatty acid|amino acid|biochemical trait|circulating metabol", re.I)
PLATFORM = re.compile(r"metabolon|nightingale|biocrates|brainshake|chenomx|mass spectrometry|\bLC-?MS\b|\bGC-?MS\b|\bNMR\b|UPLC|HILIC|untargeted metabolom|targeted metabolom", re.I)
# exclusions
EXCL = re.compile(r"mendelian random|\bMR\b analysis|two-sample MR|polygenic (risk|score)|\bPRS\b|systematic review|scoping review|narrative review|meta-research|proteome-wide|\bpQTL\b|proteomic|transcriptom|\beQTL\b|methylation|epigenom|\bEWAS\b|microbiom|metagenom|gut microbi|drug-target MR|phenome-wide|\bPheWAS\b", re.I)
SINGLE = re.compile(r"\bGWAS of (serum |plasma |urinary |circulating )?(urate|uric acid|homocysteine|creatinine|bilirubin|glucose|cholesterol|vitamin d|c-reactive|ferritin|albumin)\b", re.I)
NONHUMAN = re.compile(r"\b(pig|piglet|porcine|swine|plant|root|leaf|maize|rice|wheat|barley|sorghum|soybean|rapeseed|brassica|cotton|pepper|tomato|potato|grape|grapevine|apple|citrus|tea|cassava|cattle|bovine|chicken|broiler|poultry|mouse|mice|murine|\brat\b|rats|zebrafish|duck|sheep|goat|drosophila|yeast|arabidopsis|\bfish\b|\bcow\b|equine|horse|insect|seed|seedling|grain|kernel|fruit|fiber length|drought|cultivar|germplasm|agronomic|pangenome|horticultur|foliar|rhizospher|tuber)", re.I)
JOURNAL_EXCL = re.compile(r"plant|phytolog|horticultur|agronom|\bcrop\b|botan|new phytol|molecular plant|tree genet|forestry|aquacultur|animal|veterinary|livestock|poultry", re.I)


def score(title, ab, journal):
    s = 0
    if GWAS_T.search(title): s += 3
    if METAB_T.search(title): s += 3
    if PLATFORM.search(abto := (title + " " + ab)): s += 2
    if re.search(r"\b\d{2,}\s+(metabolit|lipid|trait)", ab, re.I): s += 1
    if re.search(r"\b\d+\s+(loci|associat|signals|genom)", ab, re.I): s += 1
    if re.search(r"\b(UK Biobank|biobank|cohort|participants|individuals|ancestr|multi-ethnic)\b", ab, re.I): s += 1
    if re.search(r"meta-analysis|multi-ancestry", abto): s += 1
    return s


def main():
    rows = list(csv.DictReader(open(INP)))
    kept = []
    drop = Counter()
    for r in rows:
        title, ab, j = r["title"], r["abstract"], r["journal"]
        blob = f"{title} {ab}"
        if NONHUMAN.search(blob):
            drop["nonhuman/plant (text)"] += 1; continue
        if JOURNAL_EXCL.search(j):
            drop["nonhuman/plant (journal)"] += 1; continue
        if EXCL.search(blob):
            drop["excluded-class (MR/PRS/review/other-omics)"] += 1; continue
        if SINGLE.search(title):
            drop["single-trait biochemical"] += 1; continue
        # must have GWAS signal AND metabolome signal, with at least one in the TITLE
        if not (GWAS_T.search(blob) and METAB_T.search(blob)):
            drop["no GWAS+metab signal"] += 1; continue
        if not (GWAS_T.search(title) or METAB_T.search(title)):
            drop["signals only in abstract (weak)"] += 1; continue
        # require it to read as a primary association study (loci/associations mentioned)
        if not re.search(r"loci|associat|signal|variant|SNP|genetic|heritab|mQTL", ab, re.I):
            drop["no association language in abstract"] += 1; continue
        r["score"] = score(title, ab, j)
        kept.append(r)
    kept.sort(key=lambda x: -int(x["score"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        cols = list(kept[0].keys())
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(kept)
    print(f"refined pool: {len(kept)} (from {len(rows)})  -> {OUT}")
    print("dropped reasons:", dict(drop))
    print("score distribution:", dict(sorted(Counter(int(r['score']) for r in kept).items(), reverse=True)))
    print("by year:", dict(sorted(Counter(r["year"] for r in kept).items())))
    print("\n--- top 25 by score (title | journal | year) ---")
    for r in kept[:25]:
        print(f'  [{r["score"]}] {r["year"]} {r["title"][:72]}  ::{r["journal"][:22]}')


if __name__ == "__main__":
    main()
