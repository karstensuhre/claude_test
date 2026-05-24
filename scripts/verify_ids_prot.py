#!/usr/bin/env python3
"""Apply manually-verified ID corrections to data/pgwas_ids.csv.

resolve_ids_prot.py leaves a handful of rows unresolved because their publisher
pages bot-block citation-meta scraping (cell.com PII URLs, OUP/BMJ) and the
journal-abbreviation fallback can't match Europe PMC's full journal titles.
Each correction below was confirmed against Europe PMC by author+full-journal+year
(and the title was eyeballed to be the right proteomics paper). Also strips an
OUP article-id suffix from one DOI and canonicalises a Research Square preprint DOI.
Writes data/pgwas_ids.csv in place (backup: pgwas_ids.csv.bak).
"""
import csv, os, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDS = os.path.join(ROOT, "data", "pgwas_ids.csv")

# row_id -> (doi, pmid, year, journal, title)
CORRECTIONS = {
    "5":  ("10.1016/j.cell.2013.08.041",   "24074872", "2013", "Cell",
           "Genetic variants regulating immune cell levels in health and disease."),
    "18": ("10.1093/hmg/ddx266",           "28854705", "2017", "Human molecular genetics",
           "Whole-genome sequencing study of serum peptide levels: the Atherosclerosis Risk in Communities study."),
    "26": ("10.1136/jmedgenet-2018-105965", "31217265", "2019", "Journal of medical genetics",
           "Genome-wide association study identifies seven novel loci associating with circulating cytokines and cell adhesion molecules in Finns."),
    "35": ("10.1016/j.ajhg.2021.01.012",   "33571421", "2021", "American journal of human genetics",
           "Genetic control of the human brain proteome."),
    "37": ("10.1016/j.ajhg.2019.10.001",   "31679650", "2019", "American journal of human genetics",
           "Multivariate Genome-wide Association Analysis of a Cytokine Network Reveals Variants with Widespread Immune, Haematological, and Cardiometabolic Pleiotropy."),
    "39": ("10.1016/j.ajhg.2020.01.016",   "32059761", "2020", "American journal of human genetics",
           "Influence of Genetic Ancestry on Human Serum Proteome."),
    "58": ("10.21203/rs.3.rs-1633422/v1",  "",         "2022", "Research Square (preprint)",
           ""),
    "61": ("10.1093/hmg/ddac243",          "36168886", "2023", "Human molecular genetics",
           "Differences and commonalities in the genetic architecture of protein quantitative trait loci."),
    "74": ("10.1016/j.kint.2022.07.005",   "35870639", "2022", "Kidney international",
           "Identification of 969 protein quantitative trait loci in an African American population with kidney disease attributed to hypertension."),
    # row 91: the AUTH:"Suhre"+2024+"Cell" fallback wrongly matched a Cell Reports metabolomics
    # paper ("The HuMet Repository"). Correct paper is the Cell Genomics rQTL study.
    "91": ("10.1016/j.xgen.2024.100506",   "38412862", "2024", "Cell Genomics",
           "Genetic associations with ratios between protein levels detect new pQTLs and reveal protein-protein interactions."),
}


def main():
    shutil.copyfile(IDS, IDS + ".bak")
    rows = list(csv.DictReader(open(IDS)))
    changed = 0
    for r in rows:
        c = CORRECTIONS.get(r["row_id"])
        if not c:
            continue
        doi, pmid, year, journal, title = c
        r["DOI"], r["PMID"] = doi, pmid
        if year:
            r["resolved_year"] = year
        if journal:
            r["resolved_journal"] = journal
        if title:
            r["resolved_title"] = title
        r["method"] = "verified-manual"
        r["status"] = "resolved" if pmid else "partial"
        r["flag"] = ""
        changed += 1
    with open(IDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    n_doi = sum(1 for r in rows if r["DOI"])
    n_pmid = sum(1 for r in rows if r["PMID"])
    n_un = sum(1 for r in rows if r["status"] == "unresolved")
    print(f"applied {changed} corrections | DOI {n_doi}/{n} | PMID {n_pmid}/{n} | unresolved {n_un}")


if __name__ == "__main__":
    main()
