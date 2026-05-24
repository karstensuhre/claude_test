# claude_test

A playground for things tried out with Claude. See the [homepage](index.html).

## GWAS × metabolomics catalog

A homogenized, link-checked rebuild of the [list of all published GWAS with
metabolomics](http://www.metabolomix.com/list-of-all-published-gwas-with-metabolomics/)
from metabolomix.com (which was last updated there 13 Feb 2025).

- **[`gwas_table.html`](gwas_table.html)** — the **98 existing studies**, with biofluid/platform
  labels homogenized and resolved **PubMed + DOI** link columns added (DOIs may be
  paywalled). Self-contained, sortable, filterable; 17 rows flagged for review.
- **[`candidates.html`](candidates.html)** — **15 recent (2024–2026) mGWAS** auto-discovered
  via Europe PMC and verified by multiple agents, **pending review**. To accept a
  candidate, set `approve=y` in `data/candidates.csv`; `scripts/merge_candidates.py`
  then merges it into the main table.

### How it was built (reproducible from `source/gwas_original.html`)
| step | script | output |
|------|--------|--------|
| parse the source table | `scripts/parse.py` | `data/gwas_existing.csv` |
| resolve PMID/DOI per row | `scripts/resolve_ids.py`, `resolve_fallback.py`, `verify_ids.py` | `data/gwas_ids.csv` |
| homogenize labels (conservative) | `scripts/homogenize.py` | `data/gwas_homogenized.csv`, `homogenize_changelog.csv` |
| check every link | `scripts/linkcheck.py` | `data/linkcheck.csv` |
| harvest + refine candidates | `scripts/harvest.py`, `refine_pool.py` | `data/pool_refined.csv` |
| verify candidates (5 agents) | → | `data/candidates.csv`, `agent_rejections.md` |
| render HTML | `scripts/build_html.py` | `gwas_table.html`, `candidates.html` |

### Status notes
- PMID resolved for 70/98, DOI for 86/98. The 12 without a DOI keep their original
  reference URL and are flagged (10 need a manual ID; 2 are conference abstracts).
- Link check: 188 alive, 71 bot-blocked (publisher pages — alive for humans), **2 dead**
  (row 56 conference-abstract viewer; row 90 Research Square DOI 404).
- Homogenization is conservative: only labels/formatting changed; original values
  preserved in the `notes` column and in untouched `source/gwas_original.html`.

## GWAS × proteomics catalog

The same treatment applied to the [table of all published GWAS with
proteomics](http://www.metabolomix.com/a-table-of-all-published-gwas-with-proteomics/)
from metabolomix.com, adapted for pQTLs (cis/trans) and proteomics platforms.

- **[`pgwas_table.html`](pgwas_table.html)** — the **93 existing studies**, with platform
  homogenized into technology classes (**aptamer/SomaScan**, **PEA/Olink**, **mass spec**,
  immunoassay, multi-platform), **cis-/trans-pQTL** counts split out where reported, an
  inferred sample type, and resolved **PubMed + DOI** columns. Sortable, filterable; 19 rows
  flagged for review.
- **[`pgwas_candidates.html`](pgwas_candidates.html)** — **49 new pGWAS (2023–2026)**
  (25 clean keeps + 24 borderline) auto-discovered via Europe PMC and verified by 6 parallel
  agents, **pending review**. The hard filter the user asked for is enforced at the agent step:
  keep only papers that **measure the proteome de novo** (affinity or MS) and run a **genome-wide
  pQTL discovery**; **exclude** papers that merely reuse published pQTLs (Mendelian randomization,
  PWAS, colocalization, drug-target, PheWAS, meta-analysis). To accept a candidate, set
  `approve=y` in `data/pgwas_candidates.csv`.

### How it was built (reproducible from `source/pgwas_original.html`)
| step | script | output |
|------|--------|--------|
| parse the source table (6 cols) | `scripts/parse_prot.py` | `data/pgwas_existing.csv` |
| resolve PMID/DOI per row (+ fallback) | `scripts/resolve_ids_prot.py` | `data/pgwas_ids.csv` |
| apply verified ID corrections | `scripts/verify_ids_prot.py` | `data/pgwas_ids.csv` (in place) |
| homogenize platform/pQTL/sample (conservative) | `scripts/homogenize_prot.py` | `data/pgwas_homogenized.csv`, `pgwas_homogenize_changelog.csv` |
| harvest candidates (2023-07…2026) | `scripts/harvest_prot.py` | `data/pgwas_harvest_candidates.csv` |
| refine + rank, drop reuse/MR/non-human | `scripts/refine_pool_prot.py` | `data/pgwas_pool_refined.csv` |
| verify candidates (6 agents, by abstract) | → | `data/pgwas_agent_out/slice_*.jsonl` |
| consolidate keeps + log rejections | `scripts/consolidate_candidates_prot.py` | `data/pgwas_candidates.csv`, `pgwas_rejections.md` |
| render HTML | `scripts/build_html_prot.py` | `pgwas_table.html`, `pgwas_candidates.html` |

### Status notes
- PMID resolved for 73/93, DOI for 80/93. The 13 unresolved are 12 ASHG conference abstracts
  (no DOI exists) + 1 Research Square preprint (has its DOI); all are flagged.
- Candidate filtering is auditable: **87 of 136** verified candidates were rejected with a
  reason, grouped by category in [`data/pgwas_rejections.md`](data/pgwas_rejections.md)
  (mostly Mendelian-randomization / drug-target / disease-GWAS papers that reuse existing pQTLs,
  plus a few already in the catalog or preprint twins of a kept paper).
- Source had no biofluid column, so `Sample_type` is **inferred** (default plasma/serum) and
  flagged when assumed. Platform classes and split pQTL counts are derived; the original
  platform label and raw pQTL string are preserved (hover the platform chip / Σ column).
