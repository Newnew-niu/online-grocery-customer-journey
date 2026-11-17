# Operations view - facts inventory (Phase 0)

This file lists the facts that already exist in the repo. Each number has its source next to it.
Paths are relative to `llm_upgrade/` unless they start with `../`.
"NOT AVAILABLE" means no file in the repo holds the number.
Nothing was rerun, and no API calls were made, to write this file.

## 1. Human-verified set and agreement

| Fact | Value | Source |
|---|---|---|
| Reviews blind-labelled by a person | 30 (all from the 100 test reviews) | `reports/label_recheck_agreement.json` (`reviews`) |
| Review x stage cells compared | 300 | `reports/label_recheck_agreement.json` (`cells`) |
| Cohen's kappa, person vs AI-made labels | 0.67 (95% CI 0.50-0.83) | `reports/label_recheck_agreement.json` (`kappa`, `kappa_ci95`) |
| Same full label set on a review | 63% (19 of 30) | `reports/label_recheck_agreement.json` (`same_full_label_set` = 0.633) |
| Labels given | person 31, AI 34 | `reports/label_recheck_agreement.json` (`labels_given`) |
| Reviews with no stage | person 7, AI 6 | `reports/label_recheck_agreement.json` (`reviews_with_no_stage`) |
| Person's labels per review | `reports/test_recheck_labels.csv` | 30 rows, no review text |

**Pending:** the person is blind-labelling the other 70 test reviews (worksheet made by `src/00c_make_blind_worksheet_rest.py`). This section will be updated when they are back. The first 30 were labelled before the test run. The 70 are labelled after the test results were published, so they will be reported separately as well as together.

Kappa between the person and each vendor (rules, LLM) is NOT AVAILABLE yet. Phase 1 can compute it from files already in the repo.

## 2. Journey-stage categories

10 stages. Source: `../src/03_validate_tags.py` (`CODES`), names from `reports/llm_vs_rules.csv` (`level`).

| Code | Name |
|---|---|
| AL | Account & login |
| SB | Search & browse |
| BA | Basket / add to cart |
| SL | Delivery slot booking |
| CP | Checkout & payment |
| SM | Substitutions & missing items |
| DC | Delivery / collection |
| RS | Refunds & customer service |
| AP | App performance (crashes, speed) |
| PL | Pricing, promotions & loyalty |

Labels count problems only. Praise gets no stage. The rules count any mention. Source: `reports/module5_llm_and_semantic_search.md` ("Data and labels"), `prompts/journey_stage_v2.md`.

## 3. Samples and prompt iterations

| Fact | Value | Source |
|---|---|---|
| All reviews tagged by the LLM | 2,091 | `reports/llm_run_all_journey_stage_v2.json` (`reviews`) |
| Negative reviews (1-2 stars) | 609 | `reports/pain_point_ranking_llm.csv` (`negative_reviews`, "All three") |
| Dev sample | 100 negative reviews | `reports/llm_run_dev_journey_stage_v2.json` (`reviews`) |
| Test sample | 100 negative reviews | `reports/llm_run_test_journey_stage_v2.json` (`reviews`) |
| Prompt versions tried on dev | 3 (v1, v2, v3) | `reports/llm_prompt_iterations.csv` |
| Repeat runs on dev (repeatability check) | 2 (v2, v3) | `reports/llm_run_dev_journey_stage_v2__rerun.json`, `..._v3__rerun.json` |
| Same labels on repeat run | v2 88%, v3 85% | `reports/frozen_prompt.json` (`same_labels_on_rerun`) |
| Frozen prompt | `journey_stage_v2`, frozen 2026-11-04, before any test run | `reports/frozen_prompt.json` |
| Test runs | 1 | `reports/test_run_log.json` |
| Model, effort | `claude-haiku-5-5`, `low` | `reports/llm_run_all_journey_stage_v2.json` |

Dev scores by prompt (AI-made labels, n=100). Source: `reports/llm_prompt_iterations.csv`.

| Prompt | Precision | Recall | Micro F1 | Macro F1 | Exact quotes |
|---|---|---|---|---|---|
| v1 | 0.76 | 0.98 | 0.86 | 0.85 | 98.8% |
| v2 (frozen) | 0.94 | 0.91 | 0.93 | 0.81 | 100% |
| v3 | 0.91 | 0.93 | 0.92 | 0.91 | 98.5% |

## 4. LLM vs rules on the test sample

Source for all rows: `reports/llm_eval_metrics.json` (micro and macro) and `reports/llm_vs_rules.csv` (per stage).

| Labels | Method | Precision | Recall | Micro F1 (95% CI) | Macro F1 |
|---|---|---|---|---|---|
| Person's blind, n=30 | Rules | 0.68 | 0.74 | 0.71 (0.56-0.83) | 0.54 |
| Person's blind, n=30 | LLM | 0.59 | 0.71 | 0.65 (0.50-0.78) | 0.46 |
| AI-made, n=100 | Rules | 0.86 | 0.74 | 0.80 (0.74-0.85) | 0.66 |
| AI-made, n=100 | LLM | 0.88 | 0.82 | 0.85 (0.80-0.90) | 0.83 |

- Paired F1 difference, LLM minus rules: person labels -0.06 (CI -0.16 to +0.05); AI labels +0.05 (CI -0.01 to +0.11). Both CIs include zero. Source: `reports/llm_eval_metrics.json` (`diff_vs_rules`), `reports/llm_summary.json` (`f1_difference`).
- Counts on the person's 30 reviews: rules TP 23 / FP 11 / FN 8; LLM TP 22 / FP 15 / FN 9. Source: `reports/llm_vs_rules.csv` ("ALL STAGES (micro)").
- Main cause of the gap on the person's labels: the LLM gave Refunds & customer service (RS) 6 false tags, the rules 2. The person gave RS to 0 of 30. Source: `reports/llm_vs_rules.csv`, `reports/llm_summary.json` (`person_RS_labels_in_30`).
- Without RS: LLM F1 0.71, rules F1 0.73. Source: `reports/llm_summary.json` (`person_labels_without_RS`).
- Per-stage scores on the person's labels (F1, LLM / rules): AL 0.75 / 0.67, AP 0.80 / 0.70, PL 0.78 / 0.89, CP 0.50 / 0.67, SB 0.50 / 0.67, SM 0.80 / 0.80, DC 0.00 / 0.50, RS 0.00 / 0.00, BA 0.00 / 0.00, SL no cases. Most stages have 1-3 cases, so these are not reliable alone. Source: `reports/llm_vs_rules.csv`.
- Rules and LLM disagreed on 41 of 100 test reviews. Source: `reports/llm_eval_metrics.json` (`disagreements_rules_vs_llm`), `reports/llm_disagreements.csv`.

## 5. The "who made the labels" correction

- **What it was:** older documents said the dev and test labels were "hand-labelled". They were made by an AI assistant in one pass. The wording was corrected on 4 Nov 2026 in comments and documents only. File and column names (`dev_labels_manual.csv`, `hand_labelled`) were kept so scripts still run. Source: `reports/module5_llm_and_semantic_search.md` ("Label source"), commit `34a8842` message.
- **Effect of the correction itself on reported numbers:** none. The commit changed text only: "no analysis logic or result table changes". Source: commit `34a8842` message.
- **What the follow-up check showed:** scored against the person's blind labels instead of the AI-made labels, the reported accuracy drops:
  - Rules: precision 0.86 -> 0.68, recall 0.74 -> 0.74, micro F1 0.80 -> 0.71.
  - LLM: precision 0.88 -> 0.59, recall 0.82 -> 0.71, micro F1 0.85 -> 0.65.
  - Source: `reports/llm_eval_metrics.json`. Note the two label sets cover different reviews (100 vs 30 of them), so this is not a paired comparison.
- The Module 1 report now quotes the rules at precision 0.68 / recall 0.74 on the person's labels next to the original 0.86 / 0.74. Source: `../reports/module1_voice_of_customer.md`.

## 6. Run stats: cost, tokens, time, failures

| Run | Reviews | Input tokens | Output tokens | Cost (USD) | Failures | Retries | Avg latency (s) | Source |
|---|---|---|---|---|---|---|---|---|
| dev v1 | 100 | 133,359 | 17,243 | 0.0220 | 0 | 0 | 1.75 | `reports/llm_run_dev_journey_stage_v1.json` |
| dev v2 | 100 | 164,959 | 19,754 | 0.0264 | 0 | 0 | 1.76 | `reports/llm_run_dev_journey_stage_v2.json` |
| dev v2 rerun | 100 | 164,959 | 20,577 | 0.0268 | 0 | 0 | 1.73 | `reports/llm_run_dev_journey_stage_v2__rerun.json` |
| dev v3 | 100 | 173,259 | 21,053 | 0.0279 | 0 | 0 | 1.84 | `reports/llm_run_dev_journey_stage_v3.json` |
| dev v3 rerun | 100 | 173,259 | 20,501 | 0.0276 | 0 | 0 | 1.81 | `reports/llm_run_dev_journey_stage_v3__rerun.json` |
| test v2 | 100 | 164,808 | 21,560 | 0.0273 | 0 | 0 | 1.85 | `reports/llm_run_test_journey_stage_v2.json` |
| all v2 | 2,091 | 3,418,440 | 224,898 | 0.4543 | 0 | 2 | 1.36 | `reports/llm_run_all_journey_stage_v2.json` |

- The "all" run reused the cached dev v2 and test v2 answers. Their tokens are included in the "all" row, so they must not be added twice.
- Total API spend by our token counts: **$0.5585** = dev prompt work $0.1305 + test $0.0273 + new calls in the full run $0.4007. Source: `reports/llm_summary.json` (`api_spend`).
- Prices used: $0.10 input / $0.50 output per million tokens for `claude-haiku-5-5`, from a table cached on 2026-10-06. Source: `src/llm_client.py` line 26 (`PRICES`). **VERIFY:** not yet checked against Anthropic's pricing page or the console bill. The owner will check both.
- Actual billed cost from the Anthropic console: NOT AVAILABLE (you need to enter it in Phase 2).
- Per-review tokens, latency and attempts are stored in the cache: `data/llm_cache/claude-haiku-5-5/journey_stage_v2/*.json` (2,091 files, git-ignored). Their token totals match the "all" row: 3,418,440 in / 224,898 out. 2,089 reviews took 1 attempt and 2 took 2 attempts.
- Sum of per-review latency in the cache: 2,843.5 s (mean 1.36 s). Calls ran on 8 parallel workers (`src/06_llm_tag_reviews.py`, `max_workers=8`). Cached dev/test entries keep their latency from the first run.
- **Wall-clock run time:** NOT AVAILABLE. No start or end time was logged.
- **Parse errors:** NOT AVAILABLE as a separate count. Failures (reviews that still failed after 4 attempts) = 0 in every run. The 2 retries in the full run are logged without a reason, so it is unknown whether they were parse errors, refusals or rate limits. Source: `reports/llm_run_all_journey_stage_v2.json`; `src/llm_client.py` (reasons are not saved in the cache).
- **Refusals:** NOT AVAILABLE as a separate count. A refusal is treated as a failed attempt and retried (`src/llm_client.py`, `stop_reason` check). So refusals in the final output = 0, and at most 2 attempts could have been refusals.
- `reports/llm_failures.csv` does not exist, which is consistent with 0 failures (script 06 writes it only when a review fails).
- Rules timing (reviews per minute): NOT AVAILABLE. Phase 1 can time it locally.

## 7. Quote verification (hallucination check)

Each label must come with a quote. The check is that the quote is an exact substring of the review (`src/llm_client.py`, `quote_is_exact`).

| Run | Quotes | Exact | Rate | Source |
|---|---|---|---|---|
| dev v1 | 167 | 165 | 98.8% | `reports/llm_run_dev_journey_stage_v1.json` |
| dev v2 | 126 | 126 | 100% | `reports/llm_run_dev_journey_stage_v2.json` |
| dev v2 rerun | 121 | 121 | 100% | `reports/llm_run_dev_journey_stage_v2__rerun.json` |
| dev v3 | 132 | 130 | 98.5% | `reports/llm_run_dev_journey_stage_v3.json` |
| dev v3 rerun | 122 | 121 | 99.2% | `reports/llm_run_dev_journey_stage_v3__rerun.json` |
| test v2 | 125 | 125 | 100% | `reports/llm_run_test_journey_stage_v2.json` |
| all v2 | 1,138 | 1,138 | 100% | `reports/llm_run_all_journey_stage_v2.json` |

The frozen prompt (v2) had 0 inexact quotes in every run. v1's two inexact quotes changed capital letters (`reports/llm_prompt_iterations.csv`, `note`).
The check shows that the quote exists. It does not show that the quote supports the label.

## 8. Gaps that matter for Phases 1-4

- The human-verified set is small: 30 reviews, all negative, all in the test sample. Each stage has 0-11 cases. Any per-stage or per-batch quality figure on it is very noisy.
- Spread over simulated daily batches, the 30 reviews give about 4 QA items per batch for 7 batches, or about 2 per batch for 14.
- No wall-clock time, so LLM throughput can only be stated per worker (from mean latency) or as a stated assumption about workers.
- Retry reasons were not logged. The parse-error and refusal rates can only be given as "0 failures, 2 retries (cause unknown)".
- Review text is git-ignored on purpose (`../.gitignore`: "privacy / store terms"). New documents should quote review IDs, not review text.
