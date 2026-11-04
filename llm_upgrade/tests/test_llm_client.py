import json
from types import SimpleNamespace

import anthropic
import pytest
from pydantic import ValidationError

import llm_client
from llm_client import Cache, LabelOutput, Tagger, cost_usd, load_prompt, quote_is_exact


class FakeMessages:
    """Stands in for client.messages. Plays back a list of responses or errors."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def reply(body, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking"), SimpleNamespace(type="text", text=body)],
        stop_reason=stop_reason, usage=SimpleNamespace(input_tokens=100, output_tokens=20))


GOOD = json.dumps({"labels": ["AP"], "evidence": [{"code": "AP", "quote": "keeps crashing"}]})


def make(tmp_path, replies):
    fake = FakeMessages(replies)
    tagger = Tagger("v_test", "system", client=SimpleNamespace(messages=fake),
                    cache=Cache(tmp_path), sleep=lambda s: None)
    return tagger, fake


def test_schema_accepts_good_and_empty():
    assert LabelOutput.model_validate_json(GOOD).evidence_dict() == {"AP": "keeps crashing"}
    assert LabelOutput.model_validate_json('{"labels": [], "evidence": []}').labels == []


@pytest.mark.parametrize("bad", [
    '{"labels": ["XX"], "evidence": [{"code": "XX", "quote": "a"}]}',  # unknown code
    '{"labels": ["AP"], "evidence": []}',                              # no quote
    '{"labels": [], "evidence": [{"code": "AP", "quote": "a"}]}',      # quote, no label
    '{"labels": ["AP", "AP"], "evidence": [{"code": "AP", "quote": "a"}, {"code": "AP", "quote": "b"}]}',
    '{"labels": [], "evidence": [], "extra": 1}',
    'not json',
])
def test_schema_rejects_bad(bad):
    with pytest.raises(ValidationError):
        LabelOutput.model_validate_json(bad)


def test_quote_check_is_exact():
    text = "The app keeps crashing."
    assert quote_is_exact("keeps crashing", text)
    assert not quote_is_exact("Keeps Crashing", text)
    assert not quote_is_exact("keeps  crashing", text)
    assert not quote_is_exact("", text)


def test_cache_miss_then_hit(tmp_path):
    tagger, fake = make(tmp_path, [reply(GOOD)])
    first = tagger.tag("r1", "keeps crashing")
    second = tagger.tag("r1", "keeps crashing")
    assert first["from_cache"] is False and second["from_cache"] is True
    assert second["labels"] == ["AP"] and len(fake.calls) == 1


def test_cache_key_uses_model_prompt_and_review(tmp_path):
    c = Cache(tmp_path)
    assert len({c.path("m", "v1", "a"), c.path("m", "v2", "a"), c.path("n", "v1", "a"),
                c.path("m", "v1", "b")}) == 4


def test_cache_refuses_changed_prompt_with_same_version(tmp_path):
    tagger, _ = make(tmp_path, [reply(GOOD)])
    tagger.tag("r1", "x")
    other, _ = make(tmp_path, [])
    other.prompt_sha = "different"
    with pytest.raises(ValueError):
        other.tag("r1", "x")


def test_invalid_output_is_retried_and_tokens_are_summed(tmp_path):
    tagger, fake = make(tmp_path, [reply("not json"), reply(GOOD)])
    out = tagger.tag("r1", "x")
    assert out["ok"] and out["attempts"] == 2
    assert out["input_tokens"] == 200 and len(fake.calls) == 2


def test_failure_is_returned_not_dropped_and_not_cached(tmp_path):
    tagger, _ = make(tmp_path, [reply("bad")] * llm_client.MAX_ATTEMPTS)
    out = tagger.tag("r1", "x")
    assert out["ok"] is False and out["labels"] == [] and out["error"]
    assert tagger.cache.get(tagger.model, "v_test", "r1") is None


def test_refusal_counts_as_failure(tmp_path):
    tagger, _ = make(tmp_path, [reply(GOOD, "refusal")] * llm_client.MAX_ATTEMPTS)
    assert tagger.tag("r1", "x")["ok"] is False


def test_rate_limit_is_retried(tmp_path):
    response = SimpleNamespace(request=None, status_code=429, headers={})
    err = anthropic.RateLimitError("slow down", response=response, body=None)
    tagger, _ = make(tmp_path, [err, reply(GOOD)])
    assert tagger.tag("r1", "x")["ok"]


def test_no_sampling_parameters_are_sent(tmp_path):
    tagger, fake = make(tmp_path, [reply(GOOD)])
    tagger.tag("r1", "x")
    assert not {"temperature", "top_p", "top_k"} & set(fake.calls[0])


def test_cost():
    assert cost_usd(1_000_000, 1_000_000) == pytest.approx(0.60)


def test_prompt_examples_must_come_from_dev(tmp_path, monkeypatch):
    (tmp_path / "p.md").write_text("Rules\n{{example:7|AP;PL}}\n", encoding="utf-8")
    monkeypatch.setattr(llm_client, "PROMPTS", tmp_path)
    assert "Review: slow\nLabels: AP;PL" in load_prompt("p", {7: "slow"})
    with pytest.raises(ValueError):
        load_prompt("p", {8: "other"})
    with pytest.raises(ValueError):
        load_prompt("p", None)
