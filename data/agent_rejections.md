# Candidate rejections (provenance)

From the 55-paper refined pool, 5 verification agents accepted 16 (→ 15 after
de-duplicating preprint/published twins) and rejected 39. Rejections, grouped by
reason, so the catalog's exclusions are defensible:

## Mendelian randomization / causal inference / genetic-correlation (use existing summary stats, not a primary mQTL scan)
- Zhao et al. — CSF metabolites & epilepsy (MR)
- Sun et al. — plasma/urinary metabolites & colorectal cancer (MR)
- "Genetic atlas of plasma metabolome across 40 diseases" (MR framing)
- Sarcopenia metabolite biomarkers (MR); Osteoporosis & lipidome (MR/mediation)
- PUFAs & brain disorders genetic overlap; metabolites & psychiatric conditions (genetic correlation)
- BCAA catabolism & T2D (MR, narrow panel); multi-omics gray-matter atrophy in AD (shared architecture)

## Methods / simulation / statistics (no primary GWAS results)
- Kodate et al. — "Simulating metabolic pathways to enhance MGWAS interpretation" (preprint + published twin)
- Lee et al. — "On the analysis of mQTL: impact of data transformations/designs"
- Latent-factor analysis of high-dimensional traits; DisCo P-ad multiple-testing method

## Single trait / narrow targeted panel (not a metabolomics-platform panel)
- GWAS of choline, betaine, dimethylglycine + 2 ratios (3 metabolites)
- Bile-acid levels & intrahepatic cholestasis of pregnancy (single trait)
- Sphingolipids/CERS2 & T2D (single pathway)
- Metabolite GWAS in Hispanics with obesity (13 pre-selected T2D metabolites)
- aMT6s (urinary 6-sulfatoxymelatonin) multi-ancestry GWAS — single metabolite (preprint + published twin)

## Not a metabolomics platform / wrong phenotype
- Ahmed et al. — MRI-derived adipose fatty-acid composition (imaging, not MS/NMR)
- Depression-subtypes GWAS (phenotype = depression, metabolomics only defines subtypes)
- CKD GWAS in Koreans (phenotype = kidney disease outcome)
- Genomic-SEM cardiovascular-kidney-metabolic syndrome (composite disease traits)
- Lipidomic-GWAS in stroke (n=483; no genome-wide scan of the lipidome)
- Diabetic-foot & colorectal-cancer multi-omics (SNP→metabolite lookup / DB integration, not GWAS)

## Animal / plant (not human)
- Cats (AGXT2 & stone formation); oysters (ω-3 fatty acids); shea tree, sweetpotato (plant metabolite GWAS)

## Reviews
- "Genetic determinants of plasma lipids in Greenlanders" (Curr. Opin. Lipidol. review)

## Duplicates of entries already in the catalog
- Liu et al. maternal plasma metabolites (published twin of existing Liu medRxiv 2023)
- Wang C et al. CSF/brain metabolites (preprint twin already listed)
- Tambets et al. Nature 2026 (published twin of existing Tambets medRxiv 2024)

Note: the Amish Ex/GWAS (Jallow et al., bioRxiv 2025) was initially rejected by an
agent **only** because the DOI returned HTTP 403 (publisher bot-block ≠ dead). It
clearly qualifies (1,015 serum metabolites, 5,981 Amish) and was rescued into the
candidate list.
