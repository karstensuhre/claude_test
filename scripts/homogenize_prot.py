#!/usr/bin/env python3
"""Homogenize the existing proteomics-GWAS rows (conservative, like the
metabolomics homogenize.py): only derive/normalize, never discard.

Merges data/pgwas_existing.csv + data/pgwas_ids.csv and adds:
  - Year                          (from resolved year, else parsed from Reference)
  - Platform_class                4-family taxonomy: Aptamer (SomaScan) / PEA (Olink) /
                                  Mass spec / Immunoassay / Multi-platform / Other
  - Platform_detail               original platform string, lightly trimmed
  - N_cis_pQTL / N_trans_pQTL / N_pQTL_total   parsed from the messy "#pQTLs" string
  - N_pQTL_raw                    kept verbatim (rendered when parsing is ambiguous)
  - Sample_type                   inferred (default plasma/serum); flagged when assumed
  - PubMed_url / DOI_url          from resolved IDs
  - notes / flag                  review reasons (assumed sample type, not-really-proteomics,
                                  conference abstract / unresolved ID, ambiguous pQTL count)
Original values are preserved; every derivation is logged to
data/pgwas_homogenize_changelog.csv.
"""
import csv, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EX = os.path.join(ROOT, "data", "pgwas_existing.csv")
IDS = os.path.join(ROOT, "data", "pgwas_ids.csv")
OUT = os.path.join(ROOT, "data", "pgwas_homogenized.csv")
LOG = os.path.join(ROOT, "data", "pgwas_homogenize_changelog.csv")

NUM = lambda s: int(s.replace(",", ""))


def parse_year(ref, resolved_year):
    if resolved_year and re.fullmatch(r"(19|20)\d{2}", resolved_year):
        return resolved_year
    m = re.findall(r"\b((?:19|20)\d{2})\b", ref)
    return m[0] if m else ""


def parse_pqtl(raw):
    """Return (cis, trans, total, ambiguous_bool). Always conservative; keep raw on doubt."""
    s = raw.strip()
    if not s or s.upper() in ("N/A", "NA", "-"):
        return "", "", "", False
    cis = trans = total = ""
    mc = re.search(r"([\d,]+)\s*cis", s, re.I)
    mt = re.search(r"([\d,]+)\s*trans", s, re.I)
    if mc:
        cis = NUM(mc.group(1))
    if mt:
        trans = NUM(mt.group(1))
    # explicit total: a leading "NUM (" or "NUM pQTL" where NUM is not itself the cis/trans count
    lead = re.match(r"\s*([\d,]+)\s*(?:\(|pQTL|protein-altering|associations|rQTL)", s, re.I)
    leadnum = NUM(lead.group(1)) if lead else None
    lead_is_cistrans = bool(re.match(r"\s*[\d,]+\s*(?:cis|trans)", s, re.I))
    if leadnum is not None and not lead_is_cistrans:
        total = leadnum
    elif cis != "" and trans != "":
        total = cis + trans
    elif lead and lead_is_cistrans:
        total = ""  # only cis or only trans reported; leave total blank
    else:
        m = re.match(r"\s*([\d,]+)", s)        # bare leading number, e.g. "8", "14,287"
        rest = s[m.end():].lower() if m else ""
        if m and not re.search(r"snp|variant|signal", rest):   # don't capture SNP/variant counts as pQTL totals
            total = NUM(m.group(1))
    # ambiguous if we extracted nothing numeric but the string has content, or multi-clause prose
    ambiguous = (cis == "" and trans == "" and total == "") and bool(re.search(r"\d", s))
    if re.search(r";|out of|first stage|at least", s, re.I) and not (cis or trans):
        ambiguous = True
    return cis, trans, total, ambiguous


# platform technology detectors (order/exclusivity handled in classify)
RE_SOMA = re.compile(r"soma(scan|logic)?|aptamer", re.I)
RE_OLINK = re.compile(r"olink|proximity extension|\bPEA\b", re.I)
RE_MS = re.compile(r"mass.?spectrom|tandem mass|isobaric|\bTMT\b|\bSWATH\b|\bDIA\b|DIA-|"
                   r"LC[-/]MS|MS/MS|proteograph|\bseer\b|reverse phase protein|micro-western|"
                   r"data.independent acquisition|\(MS\)|peptide labeling", re.I)
RE_IMMUNO = re.compile(r"luminex|milliplex|myriad|\bRBM\b|bead.based|bead array|suspension bead|"
                       r"meso scale|\bMSD\b|elisa|immuno|antibody|fluorescent bead|"
                       r"multiplex|cytokine", re.I)
RE_NOTPROT = re.compile(r"not really proteomics|cell surface marker|immune traits|mean fluorescence", re.I)


def classify_platform(raw):
    fams = []
    if RE_SOMA.search(raw):
        fams.append("Aptamer (SomaScan)")
    if RE_OLINK.search(raw):
        fams.append("PEA (Olink)")
    if RE_MS.search(raw):
        fams.append("Mass spec")
    # generic immunoassay only counts when it is NOT an Olink/PEA assay and NOT pure MS
    if RE_IMMUNO.search(raw) and not RE_OLINK.search(raw) and "Mass spec" not in fams and "Aptamer (SomaScan)" not in fams:
        fams.append("Immunoassay")
    notprot = bool(RE_NOTPROT.search(raw))
    if not fams:
        return "Other / unspecified", notprot
    if len(fams) >= 2:
        return "Multi-platform", notprot
    return fams[0], notprot


def infer_sample(study_pop, platform, title):
    blob = " ".join([study_pop, platform, title]).lower()
    for kw, label in [("cerebrospinal", "CSF"), ("csf", "CSF"),
                      ("brain", "Brain tissue"), ("cortex", "Brain tissue"),
                      ("cerebral", "Brain tissue"), ("urine", "Urine"), ("urinary", "Urine"),
                      ("plasma", "Plasma"), ("serum", "Serum")]:
        if kw in blob:
            return label, False          # explicit -> not assumed
    return "Plasma/serum (assumed)", True


def main():
    ex = list(csv.DictReader(open(EX)))
    ids = {r["row_id"]: r for r in csv.DictReader(open(IDS))}
    out, log = [], []

    def rec(col, rid, orig, new):
        if str(orig) != str(new):
            log.append(dict(column=col, row_id=rid, original=orig, homogenized=new))

    for r in ex:
        rid = r["row_id"]
        idr = ids.get(rid, {})
        year = parse_year(r["Reference"], idr.get("resolved_year", ""))
        cis, trans, total, ambiguous = parse_pqtl(r["N_pQTL_raw"])
        pclass, notprot = classify_platform(r["Platform_raw"])
        stype, assumed = infer_sample(r["Study_population"], r["Platform_raw"], idr.get("resolved_title", ""))
        pmid, doi = idr.get("PMID", ""), idr.get("DOI", "")
        pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
        doi_url = f"https://doi.org/{doi}" if doi else ""

        notes, flags = [], []
        if assumed:
            notes.append("sample type assumed plasma/serum (not stated in source)")
        if notprot:
            notes.append("source labels this as not strictly a protein-abundance GWAS")
            flags.append("not-really-proteomics")
        if ambiguous:
            notes.append("pQTL count not cleanly parseable; see raw string")
            flags.append("pqtl-ambiguous")
        if (idr.get("status") or "") != "resolved":
            st = idr.get("status", "missing")
            notes.append(f"ID {st} ({idr.get('method','')})")
            if "conf-abstract" in (idr.get("method") or ""):
                flags.append("conference-abstract")
            else:
                flags.append("id-unresolved")

        rec("Platform", rid, r["Platform_raw"], pclass)
        rec("Sample_type", rid, "(none in source)", stype)
        rec("pQTL", rid, r["N_pQTL_raw"], f"cis={cis} trans={trans} total={total}")

        out.append(dict(
            row_id=rid, Year=year, Reference=r["Reference"],
            Study_population=r["Study_population"], Sample_type=stype,
            Platform_class=pclass, Platform_detail=r["Platform_raw"],
            N_proteins=r["N_proteins"], N_cis_pQTL=cis, N_trans_pQTL=trans,
            N_pQTL_total=total, N_pQTL_raw=r["N_pQTL_raw"], N_samples=r["N_samples"],
            PMID=pmid, DOI=doi, PubMed_url=pubmed_url, DOI_url=doi_url,
            orig_url=idr.get("orig_url", ""), notes="; ".join(notes), flag=";".join(flags)))

    out.sort(key=lambda r: (r["Year"] or "0", r["row_id"].zfill(3)))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    with open(LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["column", "row_id", "original", "homogenized"])
        w.writeheader()
        w.writerows(log)

    import collections
    cc = collections.Counter(r["Platform_class"] for r in out)
    print(f"wrote {OUT} ({len(out)} rows), {LOG} ({len(log)} changes)")
    print("platform classes:", dict(cc))
    print("flagged rows:", sum(1 for r in out if r["flag"]))


if __name__ == "__main__":
    main()
