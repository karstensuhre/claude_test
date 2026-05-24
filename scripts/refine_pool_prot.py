#!/usr/bin/env python3
"""Refine the wide harvest into a high-precision, ranked candidate pool for agent
verification.

The user wants NEW protein-GWAS papers that DE-NOVO MEASURE the proteome (affinity:
SomaScan/Olink, or mass spec) in a genotyped cohort and map pQTLs. They explicitly
want to EXCLUDE papers that merely reuse published pQTLs: Mendelian randomization,
proteome-wide association studies (PWAS, uses precomputed weights), colocalization-
only, drug-target prioritization, PheWAS, and meta-analyses of existing summary stats.

Strategy: require a proteomics-measurement signal AND a genetics/GWAS signal; drop
non-human and reviews; score (title-weighted) with bonuses for de-novo pQTL mapping
and known proteomics platforms/cohorts, penalties for the reuse-of-pQTL classes.
Tags a provisional category + the matched signals so the agents (and the user) can
audit. Keeps recall deliberately generous — agents make the final call.
Input data/pgwas_harvest_candidates.csv -> data/pgwas_pool_refined.csv (sorted).
"""
import csv, os, re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = os.path.join(ROOT, "data", "pgwas_harvest_candidates.csv")
OUT = os.path.join(ROOT, "data", "pgwas_pool_refined.csv")


def rx(*words):
    return re.compile("|".join(words), re.I)

# --- proteomics measurement signal (affinity or MS) ---
PROT = rx(r"\bpqtls?\b", r"protein quantitative trait loc", r"proteogenomic",
          r"somascan", r"somalogic", r"\bolink\b", r"proximity extension",
          r"proteograph", r"aptamer", r"\bseer\b",
          r"plasma proteome", r"serum proteome", r"circulating proteome", r"blood proteome",
          r"plasma proteomic", r"proteomic profiling", r"protein abundance",
          r"mass spectrometr\w* .{0,40}prote", r"prote\w* .{0,20}mass spectrometr",
          r"\bproteome\b", r"protein levels?", r"circulating proteins?", r"plasma proteins?")
# --- genetics / GWAS signal ---
GWAS = rx(r"genome-wide association", r"\bgwas\b", r"\bpqtls?\b", r"quantitative trait loc",
          r"genetic architecture", r"genetic determinant", r"genome-wide significant",
          r"genetic regulation", r"genetic control", r"genetic basis", r"\bcis-? ?pqtl",
          r"\btrans-? ?pqtl", r"genetic variants? .{0,30}protein")
# --- de-novo pQTL mapping bonus ---
DENOVO = rx(r"\bcis-? ?pqtl", r"\btrans-? ?pqtl", r"novel pqtl", r"identif\w+ .{0,30}pqtl",
            r"map\w+ .{0,20}pqtl", r"genetic .{0,20}determinants of .{0,20}protein",
            r"protein quantitative trait loc")
PLATFORM = rx(r"somascan", r"somalogic", r"\bolink\b", r"proximity extension",
              r"proteograph", r"explore (ht|3072|1536|384)", r"\b(v4|v4\.1|7k|5k|11k)\b",
              r"data-independent acquisition", r"\bdia-?ms\b", r"tandem mass tag", r"\btmt\b")
COHORT = rx(r"uk biobank", r"\bukb-?ppp\b", r"decode", r"fenland", r"interval study",
            r"ages-reykjavik", r"aric", r"finngen", r"china kadoorie", r"rhineland",
            r"estonian biobank", r"\bgtex\b", r"scallop", r"qatar biobank", r"\bkora\b")

# --- exclude / penalty classes (reuse of existing pQTLs) ---
MR = rx(r"mendelian randomi[sz]ation", r"two-sample mr\b", r"\bmr analys", r"instrumental variable",
        r"causal effect", r"causal relationship", r"causal association")
PWAS = rx(r"proteome-wide association stud", r"\bpwas\b", r"imputed protein", r"genetically predicted protein",
          r"genetically determined protein levels")
COLOC = rx(r"colocali[sz]ation", r"\bcoloc\b")
DRUG = rx(r"drug target", r"druggable", r"therapeutic target", r"target prioriti[sz]ation",
          r"drug repurposing")
META = rx(r"meta-analysis of .{0,30}(pqtl|gwas|summary)", r"summary statistics", r"published pqtl",
          r"existing pqtl", r"previously reported pqtl")
PHEWAS = rx(r"phenome-wide", r"\bphewas\b")
REVIEW = rx(r"\breview\b", r"systematic review", r"narrative review", r"meta-analysis\b",
            r"a survey of", r"perspectives?\b")
NONHUMAN = rx(r"\bmice\b", r"\bmouse\b", r"murine", r"\brats?\b", r"drosophila", r"zebrafish",
              r"\byeast\b", r"arabidopsis", r"\bplants?\b", r"cattle", r"bovine", r"porcine",
              r"\bpigs?\b", r"chicken", r"maize", r"wheat", r"\bcrop\b", r"\bswine\b")


def main():
    rows = list(csv.DictReader(open(INP)))
    out = []
    for r in rows:
        title = r["title"] or ""
        abs = r["abstract"] or ""
        T, A = title.lower(), abs.lower()
        blob = title + " " + abs

        has_prot = bool(PROT.search(blob))
        has_gwas = bool(GWAS.search(blob))
        nonhuman = bool(NONHUMAN.search(title)) or bool(NONHUMAN.search(A[:400]))
        review = bool(REVIEW.search(title))
        # hard gate
        if not (has_prot and has_gwas) or nonhuman or review:
            continue

        score = 0
        sig = []
        # title-weighted core signals (title matches worth ~3x)
        if PROT.search(title): score += 6; sig.append("prot:title")
        elif has_prot: score += 2; sig.append("prot:abs")
        if GWAS.search(title): score += 6; sig.append("gwas:title")
        elif has_gwas: score += 2; sig.append("gwas:abs")
        if DENOVO.search(blob): score += 5; sig.append("denovo-pqtl")
        if re.search(r"\bpqtls?\b", T): score += 4; sig.append("pqtl:title")
        if PLATFORM.search(blob): score += 4; sig.append("platform")
        if COHORT.search(blob): score += 2; sig.append("cohort")
        if re.search(r"\d[\d,]{2,}\s+(plasma |serum |circulating )?proteins?", blob, re.I):
            score += 3; sig.append("nproteins")

        # penalties for reuse-of-pQTL classes
        cat = "primary_pgwas?"
        pen = []
        if MR.search(blob): score -= 6; pen.append("MR")
        if PWAS.search(blob): score -= 7; pen.append("PWAS")
        if COLOC.search(blob) and not DENOVO.search(blob): score -= 2; pen.append("coloc")
        if DRUG.search(title): score -= 4; pen.append("drug-target")
        if META.search(blob) and not DENOVO.search(blob): score -= 4; pen.append("meta")
        if PHEWAS.search(title): score -= 3; pen.append("phewas")

        # provisional category guess (agents decide finally)
        if "PWAS" in pen and "denovo-pqtl" not in sig:
            cat = "likely_pwas"
        elif "MR" in pen and "pqtl:title" not in sig and "denovo-pqtl" not in sig:
            cat = "likely_mr"
        elif "drug-target" in pen and "denovo-pqtl" not in sig:
            cat = "likely_drug_target"
        elif "denovo-pqtl" in sig or "pqtl:title" in sig or ("platform" in sig and "gwas:title" in sig):
            cat = "likely_primary"

        out.append(dict(score=score, cat=cat, signals="|".join(sig), penalties="|".join(pen),
                        year=r["year"], source=r["source"], pmid=r["pmid"], doi=r["doi"],
                        journal=r["journal"], title=title, authors=r["authors"],
                        first_pdate=r["first_pdate"], abstract=abs[:600]))

    out.sort(key=lambda r: -r["score"])
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print(f"refined pool: {len(out)} (from {len(rows)}) -> {OUT}")
    print("score histogram:")
    h = Counter(min(r["score"], 25) // 5 * 5 for r in out)
    for b in sorted(h, reverse=True):
        print(f"  >={b:>3}: {h[b]}")
    print("category guess:", dict(Counter(r["cat"] for r in out)))
    print("score>=12:", sum(1 for r in out if r["score"] >= 12),
          "| >=15:", sum(1 for r in out if r["score"] >= 15),
          "| >=18:", sum(1 for r in out if r["score"] >= 18))


if __name__ == "__main__":
    main()
