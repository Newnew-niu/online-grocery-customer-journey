"""Step 6: Tag reviews with Claude, using a versioned prompt.

Examples (run from llm_upgrade/src):
  python 06_llm_tag_reviews.py --sample dev --prompt journey_stage_v1 --note "main errors"
  python 06_llm_tag_reviews.py --sample dev --prompt journey_stage_v2 --cache-tag rerun
  python 06_llm_tag_reviews.py --sample test --prompt journey_stage_v2
  python 06_llm_tag_reviews.py --sample all --prompt journey_stage_v2 --yes

Rules built in:
- Dev scores go to reports/llm_prompt_iterations.csv. Test scores are NOT printed
  here; script 07 makes them once, after the prompt is frozen.
- The test sample runs with one prompt. A second prompt needs --test-rerun-reason,
  and every test run is logged in reports/test_run_log.json.
- A run with a cost estimate over $2 stops unless --allow-over-budget is given.

Outputs:
- llm_upgrade/data/llm_tags_{sample}_{prompt}.csv (git-ignored: has quotes from reviews)
- reports/llm_run_{sample}_{prompt}.json
- reports/llm_failures.csv
"""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pandas as pd
from dotenv import load_dotenv

from common import CODE_LIST, DATA, REPORTS, ROOT, labels_to_matrix, load_sample
from eval_metrics import macro, micro, per_stage
from llm_client import EFFORT, MODEL, Tagger, cost_usd, load_prompt, quote_is_exact

BUDGET_USD = 2.0
GUESS_OUTPUT_TOKENS = 700  # upper guess, used only for the estimate before a run


def load_reviews(sample):
    if sample in ("dev", "test"):
        return load_sample(sample)
    df = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")
    return df[df["rating_group"] == "negative"] if sample == "negative" else df


def estimate(tagger, df):
    """Upper-end cost of the reviews that are not cached yet (about 4 characters per token)."""
    todo = df[[tagger.cache.get(tagger.model, tagger.prompt_version, r) is None
               for r in df["review_id"]]]
    chars = len(todo) * len(tagger.system_prompt) + todo["full_text"].str.len().sum()
    return len(todo), cost_usd(chars / 4, len(todo) * GUESS_OUTPUT_TOKENS)


def guard_test_run(prompt, reason):
    path = REPORTS / "test_run_log.json"
    log = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if any(x["prompt"] == prompt for x in log):
        return
    if log and not reason:
        raise SystemExit("The test sample already ran with another prompt. "
                         "Use --test-rerun-reason; both runs must then be reported.")
    log.append({"prompt": prompt, "date": str(date.today()), "reason": reason or "first test run"})
    path.write_text(json.dumps(log, indent=2), encoding="utf-8")


def summarise(df, results, sample, prompt):
    quotes = [(q, t) for r, t in zip(results, df["full_text"]) for q in r["evidence"].values()]
    ok = [r for r in results if r["ok"]]
    fresh_latency = [r["latency_s"] for r in ok if r["latency_s"] is not None]
    input_tokens = sum(r["input_tokens"] for r in results)
    output_tokens = sum(r["output_tokens"] for r in results)
    return {
        "sample": sample, "prompt": prompt, "model": MODEL, "effort": EFFORT,
        "date": str(date.today()), "reviews": len(results), "failures": len(results) - len(ok),
        "retries": sum(r["attempts"] - 1 for r in results),
        "evidence_quotes": len(quotes),
        "valid_quotes": sum(quote_is_exact(q, t) for q, t in quotes),
        "valid_quote_rate": sum(quote_is_exact(q, t) for q, t in quotes) / len(quotes) if quotes else None,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": cost_usd(input_tokens, output_tokens),
        "avg_latency_s": sum(fresh_latency) / len(fresh_latency) if fresh_latency else None,
    }


def log_dev_iteration(df, results, stats, note):
    """Keep one row per prompt version in reports/llm_prompt_iterations.csv."""
    truth = labels_to_matrix(df["labels"])
    pred = labels_to_matrix([r["labels"] for r in results])
    stages = per_stage(truth, pred, CODE_LIST)
    errors = sorted([(s["fn"], "FN " + c) for c, s in stages.items()]
                    + [(s["fp"], "FP " + c) for c, s in stages.items()], reverse=True)
    mi, ma = micro(truth, pred), macro(truth, pred)
    row = {
        "prompt": stats["prompt"], "model": MODEL, "date": stats["date"],
        "micro_precision": mi["precision"], "micro_recall": mi["recall"], "micro_f1": mi["f1"],
        "macro_f1": ma["f1"], "valid_quote_rate": stats["valid_quote_rate"],
        "failures": stats["failures"],
        "top_errors": "; ".join(f"{name}={n}" for n, name in errors[:4] if n), "note": note,
    }
    path = REPORTS / "llm_prompt_iterations.csv"
    old = pd.read_csv(path) if path.exists() else pd.DataFrame()
    if len(old):
        if note == "" and row["prompt"] in set(old["prompt"]):
            row["note"] = old.loc[old["prompt"] == row["prompt"], "note"].iloc[0]
        old = old[old["prompt"] != row["prompt"]]
    pd.concat([old, pd.DataFrame([row])], ignore_index=True).to_csv(path, index=False)
    print(pd.DataFrame([row]).T.to_string(header=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True, choices=["dev", "test", "negative", "all"])
    ap.add_argument("--prompt", required=True, help="file name in prompts/, without .md")
    ap.add_argument("--note", default="", help="dev only: main error types in plain words")
    ap.add_argument("--cache-tag", default="", help="separate cache, for a repeatability check")
    ap.add_argument("--test-rerun-reason", default="")
    ap.add_argument("--allow-over-budget", action="store_true")
    ap.add_argument("--yes", action="store_true", help="run after showing the estimate")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    df = load_reviews(args.sample).reset_index(drop=True)
    dev_examples = dict(zip(*[load_sample("dev")[c] for c in ("val_id", "full_text")]))
    system = load_prompt(args.prompt, dev_examples)
    version = f"{args.prompt}__{args.cache_tag}" if args.cache_tag else args.prompt
    tagger = Tagger(version, system)

    n_todo, est = estimate(tagger, df)
    print(f"{n_todo} of {len(df)} reviews need a call. Upper-end estimate: ${est:.2f}")
    if est > BUDGET_USD and not args.allow_over_budget:
        raise SystemExit(f"Estimate is over ${BUDGET_USD:.2f}. Ask the owner first.")
    if args.sample in ("negative", "all") and not args.yes:
        raise SystemExit("Check the estimate, then run again with --yes.")
    if args.sample == "test":
        guard_test_run(args.prompt, args.test_rerun_reason)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(tagger.tag, df["review_id"], df["full_text"]))

    stats = summarise(df, results, args.sample, version)
    name = f"{args.sample}_{version}"
    (REPORTS / f"llm_run_{name}.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    keep = [c for c in ("val_id", "review_id") if c in df]
    out = df[keep].copy()
    out["ok"] = [r["ok"] for r in results]
    out["llm_labels"] = [";".join(r["labels"]) for r in results]
    out["evidence"] = [json.dumps(r["evidence"], ensure_ascii=False) for r in results]
    out.to_csv(DATA / f"llm_tags_{name}.csv", index=False)

    failed = [r for r in results if not r["ok"]]
    if failed:
        path = REPORTS / "llm_failures.csv"
        f = pd.DataFrame(failed)[["model", "prompt_version", "review_id", "error", "attempts"]]
        f.to_csv(path, mode="a", header=not path.exists(), index=False)
    print({k: stats[k] for k in ("reviews", "failures", "retries", "valid_quote_rate", "cost_usd")})

    if args.cache_tag:
        base = pd.read_csv(DATA / f"llm_tags_{args.sample}_{args.prompt}.csv").fillna("")
        same = (base["llm_labels"].values == out["llm_labels"].fillna("").values).mean()
        stats["same_labels_as_first_run"] = float(same)
        (REPORTS / f"llm_run_{name}.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
        print(f"Same labels as the first run: {same:.1%}")
    elif args.sample == "dev":
        log_dev_iteration(df, results, stats, args.note)


if __name__ == "__main__":
    main()
