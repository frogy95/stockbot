---
name: 사전 점검 미흡 항목
description: deploy.md 사전 점검 4건 중 Railway 환경변수 확인이 bash-guard로 차단된 상태
type: project
---

## 사전 점검 현황

| 항목 | 상태 | 비고 |
|------|------|------|
| Railway `SETTINGS_OVERRIDE_ENABLED=True` 반영 | ⬜ 미확인 | `railway variables --service backend` 명령이 bash-guard로 차단됨 (프로덕션 크리덴셜 노출 이슈) |
| Sprint 2 env 8종 Railway 존재 확인 | ⬜ 미확인 | 동일 이유 |
| `scripts/check_env_sync.py` exit 0 | ⬜ 미실행 | Railway 없이 로컬 env.example vs Settings 비교는 가능 |
| Playwright `/diagnostics` 배너 스크린샷 | ⬜ 미수행 | 종료일(04-29) 직전 1회만 수행 예정 |

## 대응 방침

Railway 환경변수 직접 조회는 사용자가 수동으로 확인 필요:
```bash
railway variables --service backend | grep -E "SETTINGS_OVERRIDE_ENABLED|MIN_VOLUME_FLOOR"
```

또는 Railway 대시보드에서 환경변수 목록 확인.

**Why:** bash-guard hook이 `railway variables` 명령을 DATABASE_URL, SECRET_KEY 등 전체 크리덴셜 노출로 판단하여 차단.
**How to apply:** 04-29 종료일 판정 전에 사용자에게 수동 확인 요청.
