"""Claude client for journey-stage tagging: schema check, disk cache, retries.

Every response is cached by (model, prompt_version, review_id), so reruns are free.
Reviews that still fail after all retries are returned and counted, never dropped.
Current Claude models reject `temperature`, so none is sent. Script 06 measures
how repeatable the answers are instead.
"""
import hashlib
import json
import random
import re
import time
from pathlib import Path
from typing import List, Literal, get_args

import anthropic
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from common import CODE_LIST, DATA, PROMPTS

MODEL = "claude-haiku-5-5"
EFFORT = "low"
MAX_TOKENS = 1024
MAX_ATTEMPTS = 4
# US dollars per million tokens, from the price table cached on 2026-10-06.
PRICES = {"claude-haiku-5-5": {"input": 0.10, "output": 0.50}}

StageCode = Literal["AL", "SB", "BA", "SL", "CP", "SM", "DC", "RS", "AP", "PL"]
assert list(get_args(StageCode)) == CODE_LIST


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: StageCode
    quote: str


class LabelOutput(BaseModel):
    """What the model must return. `evidence` is a list on the wire because
    structured outputs need fixed keys; evidence_dict() gives {code: quote}."""
    model_config = ConfigDict(extra="forbid")
    labels: List[StageCode]
    evidence: List[Evidence]

    @model_validator(mode="after")
    def one_quote_per_label(self):
        if len(set(self.labels)) != len(self.labels):
            raise ValueError("repeated label")
        if sorted(e.code for e in self.evidence) != sorted(self.labels):
            raise ValueError("labels and evidence codes differ")
        return self

    def evidence_dict(self):
        return {e.code: e.quote for e in self.evidence}


def quote_is_exact(quote, text):
    """Hallucination check: the quote must be an exact substring of the review."""
    return bool(quote) and quote in text


def cost_usd(input_tokens, output_tokens, model=MODEL):
    p = PRICES[model]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def load_prompt(version, dev_examples=None):
    """Read prompts/{version}.md. Markers like {{example:12|AP;PL}} are filled in from
    the dev sample at run time, so no review text is stored in the prompt files."""
    text = (PROMPTS / f"{version}.md").read_text(encoding="utf-8")

    def fill(match):
        val_id, labels = int(match.group(1)), match.group(2)
        if dev_examples is None or val_id not in dev_examples:
            raise ValueError(f"Few-shot example {val_id} is not in the dev sample")
        return f"Review: {dev_examples[val_id]}\nLabels: {labels}"

    return re.sub(r"\{\{example:(\d+)\|([A-Z;]*)\}\}", fill, text)


class Cache:
    def __init__(self, root=None):
        self.root = Path(root) if root else DATA / "llm_cache"

    def path(self, model, prompt_version, review_id):
        name = hashlib.sha256(str(review_id).encode("utf-8")).hexdigest()[:32]
        return self.root / model / prompt_version / f"{name}.json"

    def get(self, model, prompt_version, review_id):
        p = self.path(model, prompt_version, review_id)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def put(self, model, prompt_version, review_id, entry):
        p = self.path(model, prompt_version, review_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(entry, ensure_ascii=False), encoding="utf-8")


class Tagger:
    def __init__(self, prompt_version, system_prompt, client=None, cache=None, model=MODEL,
                 sleep=time.sleep):
        self.prompt_version = prompt_version
        self.system_prompt = system_prompt
        self.prompt_sha = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
        self.client = client if client is not None else anthropic.Anthropic(max_retries=2)
        self.cache = cache or Cache()
        self.model = model
        self.sleep = sleep

    def _call(self, text):
        return self.client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system_prompt,
            output_config={
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": LabelOutput.model_json_schema()},
            },
            messages=[{"role": "user", "content": f"<review>\n{text}\n</review>"}],
        )

    def tag(self, review_id, text):
        """Return a result dict with ok=True/False. Only successes are cached.
        Auth and bad-request errors are raised, because retrying cannot help."""
        hit = self.cache.get(self.model, self.prompt_version, review_id)
        if hit is not None:
            if hit["prompt_sha"] != self.prompt_sha:
                raise ValueError(f"Prompt {self.prompt_version} changed. Make a new version file.")
            return {**hit, "from_cache": True}

        input_tokens = output_tokens = 0
        error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                resp = self._call(text)
            except (anthropic.RateLimitError, anthropic.APIConnectionError,
                    anthropic.InternalServerError) as e:
                error = type(e).__name__
                self.sleep(2 ** attempt + random.random())
                continue
            latency = time.perf_counter() - started
            input_tokens += resp.usage.input_tokens
            output_tokens += resp.usage.output_tokens
            try:
                if resp.stop_reason != "end_turn":
                    raise ValueError(f"stop_reason={resp.stop_reason}")
                body = next(b.text for b in resp.content if b.type == "text")
                out = LabelOutput.model_validate_json(body)
            except (ValueError, StopIteration) as e:  # pydantic's ValidationError is a ValueError
                error = str(e).splitlines()[0][:200] if str(e) else type(e).__name__
                self.sleep(2 ** attempt + random.random())
                continue
            entry = {
                "ok": True, "model": self.model, "prompt_version": self.prompt_version,
                "prompt_sha": self.prompt_sha, "review_id": str(review_id),
                "labels": out.labels, "evidence": out.evidence_dict(),
                "attempts": attempt, "input_tokens": input_tokens,
                "output_tokens": output_tokens, "latency_s": latency,
            }
            self.cache.put(self.model, self.prompt_version, review_id, entry)
            return {**entry, "from_cache": False}

        return {"ok": False, "model": self.model, "prompt_version": self.prompt_version,
                "review_id": str(review_id), "labels": [], "evidence": {}, "error": error,
                "attempts": MAX_ATTEMPTS, "input_tokens": input_tokens,
                "output_tokens": output_tokens, "latency_s": None, "from_cache": False}
