import json

import pytest
from pydantic import ValidationError

from pipeline.core import config
from pipeline.models import Storyboard


def test_storyboard_is_valid(raw_storyboard):
    sb = Storyboard.model_validate(raw_storyboard)
    assert 8 <= len(sb.shots) <= 12


def test_committed_schema_matches_models():
    committed = json.loads(config.SCHEMA.read_text())
    assert committed == Storyboard.model_json_schema(), "run `python -m pipeline schema`"


def test_too_few_shots_rejected(raw_storyboard):
    raw_storyboard["shots"] = raw_storyboard["shots"][:7]
    with pytest.raises(ValidationError):
        Storyboard.model_validate(raw_storyboard)


def test_unknown_character_rejected(raw_storyboard):
    raw_storyboard["shots"][0]["characters"] = ["nobody"]
    with pytest.raises(ValidationError, match="unknown characters"):
        Storyboard.model_validate(raw_storyboard)


def test_unknown_field_rejected(raw_storyboard):
    raw_storyboard["shots"][0]["colour_grade"] = "teal"
    with pytest.raises(ValidationError):
        Storyboard.model_validate(raw_storyboard)


def test_every_shot_states_a_reason(raw_storyboard):
    sb = Storyboard.model_validate(raw_storyboard)
    assert all(len(s.purpose) > 20 for s in sb.shots)


def test_chosen_music_seed_must_be_a_candidate(raw_storyboard):
    raw_storyboard["music"]["chosen_seed"] = 999
    with pytest.raises(ValidationError, match="chosen_seed"):
        Storyboard.model_validate(raw_storyboard)
