"""Caching, retries and logging: the properties the walkthrough demonstrates live."""

import pytest

from pipeline.core import calls, runlog
from pipeline.models import Storyboard
from pipeline.stages import narration


def _fake_tts(counter):
    def run(tmp):
        counter.append(1)
        tmp.write_bytes(b"RIFF-fake-audio")
        return {"est_cost_usd": 0.0}

    return run


def _narrate_all(sb, counter):
    for shot in sb.shots:
        _, inputs = narration.inputs_for(sb, shot)
        calls.call_model(
            stage="narration",
            item=shot.id,
            provider="fake",
            model="fake-tts",
            inputs=inputs,
            ext="wav",
            run=_fake_tts(counter),
        )


def test_changing_one_line_regenerates_only_that_shot(raw_storyboard, isolated_outputs):
    sb = Storyboard.model_validate(raw_storyboard)
    counter: list[int] = []
    _narrate_all(sb, counter)
    assert len(counter) == len(sb.shots)

    raw_storyboard["shots"][2]["narration"]["text"] = "A different line for shot three."
    sb2 = Storyboard.model_validate(raw_storyboard)
    counter.clear()
    _narrate_all(sb2, counter)
    assert len(counter) == 1, "only s03 should be regenerated"

    ok = [r for r in runlog.read() if r["status"] == "ok"]
    assert len(ok) == len(sb.shots) + 1
    assert ok[-1]["shot_id"] == "s03"


def test_dry_run_reports_changed_field(raw_storyboard, isolated_outputs):
    sb = Storyboard.model_validate(raw_storyboard)
    _narrate_all(sb, [])
    raw_storyboard["shots"][2]["narration"]["speed"] = 0.9
    sb2 = Storyboard.model_validate(raw_storyboard)
    calls.CTX.dry_run = True
    _narrate_all(sb2, [])
    plan = calls.CTX.plan
    gen = [p for p in plan if p["action"] == "generate"]
    assert [p["item"] for p in gen] == ["s03"]
    assert gen[0]["changed"] == ["speed"]
    assert sum(p["action"] == "reuse" for p in plan) == len(sb.shots) - 1


def test_retry_then_success_logs_every_attempt(isolated_outputs):
    attempts = []

    def flaky(tmp):
        attempts.append(1)
        if len(attempts) < 3:
            raise calls.ProviderError("HTTP 429", retryable=True, retry_after=0.0)
        tmp.write_bytes(b"ok")
        return {}

    out = calls.call_model(
        stage="t",
        item="x",
        provider="p",
        model="m",
        inputs={"prompt": "hi", "seed": 1},
        ext="bin",
        run=flaky,
    )
    assert out and out.exists()
    statuses = [r["status"] for r in runlog.read()]
    assert statuses == ["error", "error", "ok"]
    assert all(
        {"model", "seed", "latency_s", "attempt", "params"} <= r.keys() for r in runlog.read()
    )


def test_non_retryable_error_fails_fast(isolated_outputs):
    def bad(tmp):
        raise calls.ProviderError("HTTP 400 bad request", retryable=False)

    with pytest.raises(calls.ProviderError):
        calls.call_model(
            stage="t",
            item="x",
            provider="p",
            model="m",
            inputs={"prompt": "hi"},
            ext="bin",
            run=bad,
        )
    assert len(runlog.read()) == 1


def test_missing_credentials_message(monkeypatch):
    from pipeline.core.config import MissingCredentials, secret

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(MissingCredentials, match=".env.example"):
        secret("GEMINI_API_KEY")
