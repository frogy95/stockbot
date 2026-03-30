"""리스크 파라미터 시드 검증 테스트"""

import pytest

from scripts.seed_settings import SEED_DATA


def _seed_dict():
    """SEED_DATA를 {key: value} 딕셔너리로 변환"""
    return {row[0]: row[1] for row in SEED_DATA}


# --- 기존 값 수정 확인 ---

def test_leverage_etf_size_pct_updated():
    d = _seed_dict()
    assert d["leverage_etf_size_pct"] == "5.0"


def test_force_close_start_updated():
    d = _seed_dict()
    assert d["force_close_start"] == "14:50"


def test_force_close_end_updated():
    d = _seed_dict()
    assert d["force_close_end"] == "15:00"


def test_leverage_etf_loss_pct_maintained():
    d = _seed_dict()
    assert d["leverage_etf_loss_pct"] == "-1.5"


# --- 신규 항목 존재 + 값 검증 ---

@pytest.mark.parametrize("key,expected_value", [
    ("leverage_position_size_pct", "5.0"),
    ("max_leverage_position_count", "2"),
    ("leverage_take_profit_pct", "3.0"),
    ("trailing_activation_pct", "2.0"),
    ("emergency_stop_pct", "-4.0"),
    ("consecutive_loss_stop", "3"),
    ("cooldown_trigger_count", "2"),
    ("cooldown_duration_min", "60"),
    ("eod_force_close_time", "14:50"),
    ("no_new_entry_time", "14:30"),
    ("risk_lock_during_trading", "true"),
])
def test_new_risk_param(key, expected_value):
    d = _seed_dict()
    assert key in d, f"시드에 {key} 키가 없음"
    assert d[key] == expected_value


def test_seed_data_count_minimum():
    assert len(SEED_DATA) >= 32
