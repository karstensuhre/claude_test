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
