# Online Grocery Customer Journey Analysis

An end-to-end analysis of the online grocery customer journey, built with **real, public data**.

**The story:**

1. What are customers complaining about? *(app reviews)*
2. Where do shoppers drop off online? *(web funnel)*
3. What drives loyalty and response to promotions? *(retail transactions)*
4. How would we test a fix? *(A/B test design)*

> **Data honesty note:** no dataset here is Tesco data. Each module states where its data comes from and what it can and cannot show.

**See the results:** [interactive dashboard](https://newnew-niu.github.io/online-grocery-customer-journey/) · [slide deck (PPTX)](slides/Online_Grocery_Customer_Journey.pptx) · [executive summary](reports/executive_summary.md)

---

## Key findings

| Module | Question | Main result |
|---|---|---|
| 1. Voice of Customer | What do app users complain about? | Across **2,091** reviews of the Tesco Ireland, Dunnes Stores and SuperValu apps, **app performance (34.0%)** and **pricing/loyalty (32.0%)** are the most common stages in negative reviews. Login complaints have the **lowest average rating (1.65 stars)**. Each retailer is different: SuperValu = app speed (65%), Dunnes = vouchers (51%), Tesco = speed, loyalty and login. |
| 2. Web funnel | Where do shoppers drop off? | In **360,129** real GA4 sessions: conversion **1.35%**, cart abandonment **81.2%**, AOV **$68.97**. The biggest drop is **view item -> add to cart (19.7% continue)**. Device makes almost no difference. **New users** are the weak segment (0.68% vs 3.10% conversion; only 48% go from checkout to payment). |
| 3. CRM & promotions | Who are the valuable customers? Do campaigns and coupons work? | **Champions are 21% of 2,467 households but 46% of spend.** Difference-in-differences on 3 large campaigns finds **no clear spend lift** (all 95% CIs include 0). Coupon users are **not** less loyal: after controls, more coupon use goes with slightly *more* loyalty (odds of lapsing x0.78 per +10 points). |
| 4. A/B test design | How would we test a checkout fix? | A **designed** test of one-tap wallet payment: baseline 76.8% payment -> purchase, MDE +3 points, **2,959 users per group** (80% power, alpha 0.05), with guardrails and decision rules. |
| 5. LLM & semantic search | Can an LLM tag reviews better than rules? Can search find them by meaning? | **The answer depends on the labels.** On 100 test reviews with AI-made labels, F1 is **0.85** for the LLM vs **0.80** for rules (paired 95% CI -0.01 to +0.11). On 30 reviews a person labelled blind, it is **0.65** vs **0.71** (CI -0.16 to +0.05). Person and AI labels agree at kappa **0.67**. Semantic search beats BM25 on precision@10 (**0.64 vs 0.52**, 10 queries). Total API cost **$0.56**. |

---

## Data sources and provenance

| Module | Data | Provenance and limits |
|---|---|---|
| 1 | **App reviews**: Google Play (`google-play-scraper`) and Apple's public RSS feed, Irish stores, 27 Oct 2024 - 25 Oct 2026, collected 26 Oct 2026. Apps: Tesco Ireland (`com.puca.tesco` / `648859363`), Dunnes Stores (`com.dunnes.valueclubcard` / `1539398657`), SuperValu (`com.ammeon.supervalu` / `538805121`). | Reviews are **self-selected and skew negative** (selection bias). They show *what kinds* of problems exist, not how many customers have them. Apple serves only the 500 most recent reviews per app. `com.tesco.grocery.view` is the UK app and was **not** used. Trustpilot was not scraped (its terms restrict it). |
| 2 | **GA4 public sample** in BigQuery: `bigquery-public-data.ga4_obfuscated_sample_ecommerce`, 1 Nov 2020 - 31 Jan 2021. | This is the **Google Merchandise Store**, a real online shop that sells Google-branded products. It is **real e-commerce web analytics data, not grocery data**. Google obfuscated some values. |
| 3 | **The Complete Journey (84.51° release)** from the open `completejourney` R package: 2,469 households, calendar year 2017, with transactions, products, campaigns, coupons, redemptions and demographics (801 households). | An **anonymised US grocery retailer. Not Tesco.** The project first planned to use dunnhumby's older release (about 2,500 households, two years), but the open package holds the 84.51° release, so we used that. This is observational data, not an experiment. |
| 4 | Baselines from Module 2. | The A/B test is **designed, not run**. The only "results" are a clearly labelled simulation. |

Context sources (cited, not scraped): Tesco Ireland help pages (https://www.tesco.ie/help) and the Baymard Institute online grocery UX research (https://baymard.com/research/online-grocery).

---

## Methods

**Module 1 - Voice of Customer** ([full write-up](reports/module1_voice_of_customer.md))

- Cleaned the reviews and checked language. Tagged 10 journey stages with keyword rules (`src/journey_rules.py`); one review can mention several stages.
- **Validation:** An AI assistant labelled a dev sample of 100 negative reviews, which was used to improve the rules. A separate test sample of 100 was never used to write rules. Against the AI-made labels on that test sample the rules score **precision 0.86, recall 0.74**. On 30 of those reviews labelled blind by a person they score **precision 0.68, recall 0.74** (see Module 5).
- Sentiment: star rating + VADER (correlation 0.71). Topic model (LDA) on untagged reviews to look for missed themes. 95% Wilson CIs for shares.

**Module 2 - Web funnel** ([full write-up](reports/module2_web_funnel.md))

- One SQL query (`sql/01_session_funnel.sql`, 1.16 GB scanned) builds one row per session. A session = `user_pseudo_id` + `ga_session_id`, taken from the nested `event_params`.
- Closed and open funnels; step conversion, cart abandonment and AOV.
- Segments: device, first-touch medium, new vs returning. Chi-square tests and Wilson CIs.

**Module 3 - CRM & promotions** ([full write-up](reports/module3_crm_promotions.md))

- KPIs: AOV, items per basket, frequency, days between trips. Monthly retention and cohorts.
- **RFM** quintile scores mapped to 7 segments, with profiles.
- **Difference-in-differences** with household and week fixed effects and clustered standard errors. Event-study check of parallel trends, two control groups and two outcomes.
- **Coupon dependency vs loyalty:** coupon use measured in Jan-Jun, loyalty in Jul-Dec, with regression controls for earlier shopping frequency and spend.

**Module 4 - A/B test design** ([full plan](reports/module4_ab_test_design.md))

- Hypothesis, primary/secondary/guardrail metrics, user-level randomisation and triggered analysis.
- Power calculation with `statsmodels` (`NormalIndPower`, Cohen's h).
- Duration, decision rules, risks, and a simulated analysis (SRM check, z-test, guardrail test, 2,000-run power check).

**Module 5 - LLM & semantic search** ([full write-up](llm_upgrade/reports/module5_llm_and_semantic_search.md))

- `claude-haiku-5-5` tags reviews with a versioned prompt, pydantic-checked JSON and a quote for every label. Each quote is checked as an exact substring of the review.
- The prompt was tuned on the dev sample and frozen before one test run. Results compare rules, LLM and a hybrid, with paired bootstrap 95% CIs.
- The dev and test labels were made by an AI assistant, so a person blind-labelled 30 test reviews to measure how far they can be trusted.
- Semantic search uses a local sentence-transformers model and ChromaDB, compared with BM25 using queries written before any results were seen.

---

## Limitations

- **Three different datasets.** The modules are linked by the *type* of customer problem, not by the same customers. Irish grocery apps, a US grocer's transactions and a merchandise website cannot be joined.
- **Reviews:** selection bias. The keyword rules miss about 1 in 4 mentions (recall 0.74). The labels were made by an AI assistant in one pass; a person's blind check of 30 reviews agreed at kappa 0.67. Small stages (delivery, basket) have too few cases to be reliable.
- **GA4 sample:** not grocery; obfuscated; a peak season (Nov-Jan); no page-speed data.
- **Complete Journey:** one US retailer in 2017; a panel of frequent shoppers; campaign targeting was not random, so DiD relies on parallel trends. Demographics are available for only 801 households.
- **A/B test:** designed, not run.

---

## How to run

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
cd src
```

Run the scripts in number order from the `src` folder:

| Step | Command | Output |
|---|---|---|
| Module 1 | `python 01_collect_reviews.py` | `data/raw/reviews/reviews_raw.csv` (results change over time, because new reviews appear) |
| | `python 02_clean_and_tag_reviews.py` | `data/processed/reviews_tagged.csv` |
| | `python 03_validate_tags.py` | `reports/tag_validation.csv` (needs the label files) |
| | `python 04_pain_point_ranking.py` | ranking + figures |
| | `python 05_untagged_topics.py` | missed-topic check |
| Module 3 | `python download_completejourney.py` | raw data files |
| | `python 10_prepare_completejourney.py` ... `python 14_coupon_vs_loyalty.py` | KPIs, RFM, DiD, coupon analysis |
| Module 2 | `python bq_auth.py` (one-time browser login) | - |
| | `python 20_run_ga4_query.py --project YOUR_GCP_PROJECT` | `data/raw/ga4/ga4_sessions.parquet` (free BigQuery sandbox is enough) |
| | `python 21_ga4_funnel.py` | funnel tables, baselines, figures |
| Module 4 | `python 30_ab_test_design.py`, `python 31_ab_test_simulated_analysis.py` | power table, simulated analysis |
| Dashboard | `python 40_dashboard_exports.py`, `python 41_build_static_dashboard.py` | `reports/dashboard_data/*.csv`, `docs/index.html` |
| Module 5 | See [llm_upgrade/README.md](llm_upgrade/README.md) | LLM tags, evaluation, search index (needs an Anthropic API key) |

**Notes**

- Review text is **not** stored in this repo (it is user-written content). The collection script rebuilds it, and the label files hold only label codes.
- No credentials are stored in the repo. The BigQuery login token is saved in your user folder.

## Project structure

```
data/raw/          original data (not edited; mostly git-ignored, rebuilt by scripts)
data/processed/    cleaned data made by scripts (+ label files)
sql/               BigQuery SQL
src/               numbered Python scripts (+ shared helpers)
reports/           module write-ups, result tables, executive summary
reports/figures/   all charts
reports/dashboard_data/  small summary tables used by the dashboard
dashboard/         dashboard layout and page shell
docs/              built dashboard page (served by GitHub Pages)
slides/            slide deck (PPTX)
llm_upgrade/       Module 5: LLM tagging and semantic search, kept in its own folder
```
