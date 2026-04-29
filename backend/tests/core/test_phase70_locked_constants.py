"""Phase 7.0 LIVE 파라미터 코드 잠금 회귀 방지 테스트.

본 테스트는 `backend/core/constants.py`의 4개 상수가 변경되거나, 런타임에서
변조 시도가 발생할 경우 빌드를 실패시키는 안전망이다.
"""

from __future__ import annotations

import importlib
import re
import sys
import typing
from pathlib import Path

import pytest

CONSTANTS_MODULE = "core.constants"
EXPECTED = {
    "LIVE_MAX_POSITION_COUNT": 2,
    "LIVE_POSITION_SIZE_PCT": 5.0,
    "LIVE_DAILY_MAX_LOSS_PCT": -2.0,
    "LIVE_EMERGENCY_STOP_PCT": -3.0,
}


def _import_constants():
    if CONSTANTS_MODULE in sys.modules:
        del sys.modules[CONSTANTS_MODULE]
    return importlib.import_module(CONSTANTS_MODULE)


def test_constants_importable_with_locked_values() -> None:
    mod = _import_constants()
    for name, expected in EXPECTED.items():
        assert hasattr(mod, name), f"missing constant: {name}"
        assert getattr(mod, name) == expected, f"{name} != {expected}"


def test_constants_have_final_type_hints() -> None:
    mod = _import_constants()
    hints = typing.get_type_hints(mod, include_extras=True)
    for name in EXPECTED:
        assert name in hints, f"missing Final hint: {name}"
        # typing.Final[int] / Final[float] 의 origin은 Final 자체.
        origin = typing.get_origin(hints[name])
        assert origin is typing.Final, f"{name} is not Final[...]"


def test_no_reassignment_of_locked_constants_in_module_text() -> None:
    """모듈 텍스트에서 상수에 = 로 값을 재할당하는 라인이 1개(원시 선언)뿐인지 확인."""
    module_path = Path(__file__).resolve().parents[2] / "core" / "constants.py"
    text = module_path.read_text(encoding="utf-8")
    for name in EXPECTED:
        # 선언 라인(타입 힌트 포함) 단 1줄만 허용
        pattern = rf"^{name}\s*[:=]"
        matches = [ln for ln in text.splitlines() if re.match(pattern, ln)]
        assert len(matches) == 1, f"{name} 재할당 의심 라인 {len(matches)}개: {matches}"


def test_phase7_constants_immutable_at_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """런타임 attr 변조 후 모듈 재로드 시 잠금 값이 원본으로 복원됨을 검증."""
    mod = _import_constants()
    monkeypatch.setattr(mod, "LIVE_MAX_POSITION_COUNT", 99, raising=True)
    reloaded = importlib.reload(mod)
    assert reloaded.LIVE_MAX_POSITION_COUNT == 2, "재임포트 후 잠금 상수가 복원되지 않음"


def test_runtime_assert_triggers_on_tampered_module(tmp_path: Path) -> None:
    """위조된 constants 모듈 텍스트로 import 시 AssertionError 발생을 검증."""
    fake_src = (
        "from typing import Final\n"
        "LIVE_MAX_POSITION_COUNT: Final[int] = 99\n"
        "LIVE_POSITION_SIZE_PCT: Final[float] = 5.0\n"
        "LIVE_DAILY_MAX_LOSS_PCT: Final[float] = -2.0\n"
        "LIVE_EMERGENCY_STOP_PCT: Final[float] = -3.0\n"
        'assert LIVE_MAX_POSITION_COUNT == 2, "Phase 7.0 잠금 위반"\n'
    )
    fake_file = tmp_path / "fake_constants.py"
    fake_file.write_text(fake_src, encoding="utf-8")
    sys.path.insert(0, str(tmp_path))
    try:
        if "fake_constants" in sys.modules:
            del sys.modules["fake_constants"]
        with pytest.raises(AssertionError, match="Phase 7.0 잠금 위반"):
            importlib.import_module("fake_constants")
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("fake_constants", None)
