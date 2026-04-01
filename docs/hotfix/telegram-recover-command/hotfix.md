# Hotfix: 텔레그램 /pipeline + /recover 커맨드 추가

**브랜치:** `hotfix/telegram-recover-command`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-01

---

## 문제 분석

### 증상
장전 파이프라인 장애 발생 시 텔레그램으로 단계별 상태를 확인하거나 수동으로 복구를 트리거할 수 있는 커맨드가 없었음. 텔레그램 `/help` 목록에도 해당 커맨드가 누락.

### 원인
Phase 4.5 Sprint 1에서 파이프라인 상태 Redis 영속화(`PIPELINE_HEALTHY_KEY`, `PIPELINE_RUNNING_KEY`, `PIPELINE_STATUS_KEY`) 및 수동 복구 REST API(`POST /api/v1/collector/premarket-pipeline`)가 구현되었으나, 텔레그램 커맨드 인터페이스에는 연동되지 않은 상태.

### 영향 범위
- 운영자가 텔레그램에서 파이프라인 장애를 즉각 인지/조치 불가
- `/recover` 커맨드 부재로 장전 수집 실패 시 REST API를 직접 호출하거나 Railway 콘솔에 접근해야 했음

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/notifier/commands.py` | `collector_scheduler` 파라미터 추가, `handle_pipeline()` 및 `handle_recover()` 구현, `handle_help()` 업데이트, `dispatch()` 라우팅 추가 |
| `backend/main.py` | `CommandHandler` 생성 시 `collector_scheduler` 주입 |
| `backend/tests/test_telegram_commands.py` | 5개 테스트 추가 (`/pipeline` 스케줄러 미주입, `/pipeline` 상태 조회, `/recover` 복구 시작, `/recover` 중복 방지, `/help` 새 커맨드 포함) |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `ba17957` | feat(telegram): /pipeline + /recover 커맨드 추가 — 장전 파이프라인 상태 조회 및 수동 복구 | 2026-04-01 |

---

## 검증

### 자동 검증
- pytest: 571 passed, 0 failed
- `/pipeline` 스케줄러 미주입 경고 응답 확인
- `/pipeline` 단계별 상태 + 타임스탬프 표시 확인
- `/recover` 락 선점 후 백그라운드 파이프라인 시작 확인
- `/recover` 이미 실행 중 시 중복 방지 확인
- `/help` 신규 커맨드 포함 확인

### 수동 검증
- ⬜ Railway 배포 후 텔레그램에서 `/pipeline` 커맨드 실제 응답 확인
- ⬜ 텔레그램에서 `/recover` 커맨드 실행 후 파이프라인 복구 진행 확인
- ⬜ `/help` 응답에서 `/pipeline`, `/recover` 항목 확인

---

## PR
- **URL:** (main PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
