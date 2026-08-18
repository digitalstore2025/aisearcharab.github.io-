from __future__ import annotations

import pytest

from aisearcharab_api.geo.scoring import ScoreComponent, calculate_geo_score


def test_geo_score_is_deterministic_and_weighted() -> None:
    score = calculate_geo_score(
        [
            ScoreComponent("citation_rate", 80, 0.5, 20),
            ScoreComponent("mention_share", 60, 0.3, 20),
            ScoreComponent("source_authority", 90, 0.2, 20),
        ]
    )

    assert score.status == "scored"
    assert score.sample_size == 20
    assert score.score == 76.0


def test_geo_score_refuses_small_samples() -> None:
    score = calculate_geo_score(
        [
            ScoreComponent("citation_rate", 100, 0.5, 5),
            ScoreComponent("mention_share", 100, 0.5, 5),
        ]
    )

    assert score.status == "insufficient_data"
    assert score.score is None
    assert score.sample_size == 5


def test_geo_score_refuses_missing_evidence() -> None:
    score = calculate_geo_score([])

    assert score.status == "insufficient_data"
    assert score.score is None
    assert score.sample_size == 0


@pytest.mark.parametrize("value", [-0.01, 100.01])
def test_component_rejects_out_of_range_values(value: float) -> None:
    with pytest.raises(ValueError):
        ScoreComponent("bad", value, 1.0, 10)


def test_component_rejects_invalid_weight() -> None:
    with pytest.raises(ValueError):
        ScoreComponent("bad", 50, 0.0, 10)


def test_component_rejects_negative_sample_size() -> None:
    with pytest.raises(ValueError):
        ScoreComponent("bad", 50, 1.0, -1)
