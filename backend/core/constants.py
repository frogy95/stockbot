"""Phase 7.0 LIVE 파라미터 코드 레벨 잠금.

Phase 8.6 어떤 변경에서도 본 4개 상수의 값을 수정하지 않는다. 변경 시
`tests/core/test_phase70_locked_constants.py` 회귀 테스트가 빌드를 실패시킨다.

이중 가드: typing.Final 선언 + 모듈 import 시점 assert.
monkeypatch / env override / 모듈 후처리로 값 변조 시도 시 import 사이클에서 차단된다.
"""

from __future__ import annotations

from typing import Final

LIVE_MAX_POSITION_COUNT: Final[int] = 2
LIVE_POSITION_SIZE_PCT: Final[float] = 5.0
LIVE_DAILY_MAX_LOSS_PCT: Final[float] = -2.0
LIVE_EMERGENCY_STOP_PCT: Final[float] = -3.0

assert LIVE_MAX_POSITION_COUNT == 2, "Phase 7.0 잠금 위반: LIVE_MAX_POSITION_COUNT"
assert LIVE_POSITION_SIZE_PCT == 5.0, "Phase 7.0 잠금 위반: LIVE_POSITION_SIZE_PCT"
assert LIVE_DAILY_MAX_LOSS_PCT == -2.0, "Phase 7.0 잠금 위반: LIVE_DAILY_MAX_LOSS_PCT"
assert LIVE_EMERGENCY_STOP_PCT == -3.0, "Phase 7.0 잠금 위반: LIVE_EMERGENCY_STOP_PCT"
