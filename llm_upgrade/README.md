# LLM and semantic search upgrade (Module 5)

This folder adds an LLM tagger and semantic search on top of the original project. Everything new is here. The original analysis and result tables are not changed; only the wording about who made the labels was corrected in comments and documents.

**Full write-up:** [reports/module5_llm_and_semantic_search.md](reports/module5_llm_and_semantic_search.md)

## What is here

```
src/          numbered scripts and shared helpers
prompts/      versioned prompts (v2 is frozen)
tests/        pytest tests with no network
reports/      result tables, chart and write-up
data/         cache, vector store and tables with review text (git-ignored)
```

## How to run

This needs the local review files in `data/processed/`, which are not in the repo.

```bash
pip install -r requirements.txt
pip install -r llm_upgrade/requirements.txt
# copy .env.example to .env and add your Anthropic API key
cd llm_upgrade/src
```

| Step | Command | Output |
|---|---|---|
| Blind label check | `python 00_make_blind_worksheet.py`, then `python 00b_recheck_agreement.py` | worksheet, agreement scores |
| Dev prompt work | `python 06_llm_tag_reviews.py --sample dev --prompt journey_stage_v2` | `reports/llm_prompt_iterations.csv` |
| Test run (once) | `python 06_llm_tag_reviews.py --sample test --prompt journey_stage_v2` | test tags and run stats |
| Evaluate | `python 07_evaluate_llm_vs_rules.py` | `reports/llm_vs_rules.csv`, metrics, chart |
| Tag all reviews | `python 06_llm_tag_reviews.py --sample all --prompt journey_stage_v2 --yes` | tags for 2,091 reviews |
| Ranking | `python 07b_pain_point_ranking_llm.py`, then `python 07c_summary.py` | ranking and summary numbers |
| Build index | `python 08_build_review_index.py` | `data/chroma/` |
| Search | `python 09_search_reviews.py "login keeps failing" --retailer tesco --k 5` | matching reviews |
| Evaluate search | `python 09b_evaluate_retrieval.py` | `reports/retrieval_eval.csv` |
| Tests | `pytest llm_upgrade/tests -q` (from the repo root) | no API key needed |

Answers are cached by model, prompt version and review ID, so a rerun of the same prompt is free. Script 06 stops if a run is estimated to cost more than $2, and it refuses a second prompt on the test sample unless a reason is given.
