---
name: M-F2 측정 불가 이슈
description: observation-daily API 응답에 폴백 풀 종목수/신호수 필드가 없어 M-F2 직접 계산 불가
type: project
---

## 이슈

`GET /api/v1/health/observation-daily?date=YYYY-MM-DD` 응답 스키마:
```json
{
  "date": "...",
  "signals": {"gap_open": 0, "prev_high": 1, "prev_close": 0, "other": 0, "total": 1},
  "fallback": {"triggered_count": 253, "codes": ["006340", ...]},
  "rollback": {"is_active": false, "triggered_at": null, "reason": null}
}
```

폴백 풀 전체 종목 수가 없어 `M-F2 = 폴백 풀 신호 발생 수 / 폴백 풀 종목 수` 계산 불가.

## 대응 방침

스펙 §M-F2 지시: "산출 불가 시 deploy.md에 '측정 불가 — 분기 E 자동 진입 금지, 전문가 검토 요청'으로 기록"

→ 종료일(04-29) 판정 시 M-F2 항목을 해당 문구로 deploy.md에 기록할 것.

**Why:** 분기 E는 폴백 비활성 override를 발동시키므로 측정 불가 상태에서 자동 진입 금지.
**How to apply:** 04-29 종료일 판정 시 M-F2는 "측정 불가" 처리, 분기 E 체크에서 제외.
