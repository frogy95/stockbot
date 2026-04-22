from datetime import date, datetime

import pytest

from core.metrics_keys import (
    hour_min_bucket_for,
    score_bucket_for,
    score_histogram_key,
    stage_counter_key,
    stages,
)


def test_score_histogram_key():
    assert (
        score_histogram_key(date(2026, 4, 22), "70-80")
        == "metrics:secondary:score:2026-04-22:70-80"
    )
    assert (
        score_histogram_key("2026-04-22", ">=75")
        == "metrics:secondary:score:2026-04-22:>=75"
    )


def test_stage_counter_key():
    assert (
        stage_counter_key(date(2026, 4, 22), "min_volume_floor", "09:30")
        == "metrics:strategy:stage:2026-04-22:min_volume_floor:09:30"
    )


@pytest.mark.parametrize(
    "score,expected",
    [
        (0.0, ["0-10"]),
        (9.9, ["0-10"]),
        (10.0, ["10-20"]),
        (40.0, ["40-50"]),
        (74.9, ["70-80"]),
        (75.0, [">=75", "70-80"]),
        (82.5, [">=75", "80-90"]),
        (100.0, [">=75", "90-100"]),
    ],
)
def test_score_bucket_for(score, expected):
    assert score_bucket_for(score) == expected


def test_score_bucket_for_invalid():
    assert score_bucket_for(None) == []
    assert score_bucket_for("not a number") == []


@pytest.mark.parametrize(
    "dt,expected",
    [
        (datetime(2026, 4, 22, 9, 37), "09:30"),
        (datetime(2026, 4, 22, 9, 30), "09:30"),
        (datetime(2026, 4, 22, 15, 9), "15:00"),
        (datetime(2026, 4, 22, 13, 59), "13:50"),
    ],
)
def test_hour_min_bucket_for(dt, expected):
    assert hour_min_bucket_for(dt) == expected


def test_stages_contains_expected():
    s = stages()
    assert "pass" in s
    assert "prev_close_time_guard" in s
    assert "min_volume_floor" in s
