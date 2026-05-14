# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Hotfix: virtual-signals-stock-code-filter (2026-05-14)

PR: (생성 후 기입)

**발견 경위**: 2026-05-14 09:30 Phase 8.6 A안(real-momentum) 첫 검증 모니터링 점검 trace 중 발견.
**원인**: `/api/v1/metrics/virtual-signals` 핸들러가 `stock_code` Query 파라미터를 선언하지 않아 단일 종목 필터링 불가. 기존 파라미터 미지정 호출 동작에는 영향 없음.

**변경 파일 (2개)**:
- `backend/api/routes/metrics.py` — `stock_code: str | None = Query(None)` 파라미터 추가 + 조건부 `where` 필터
- `backend/tests/test_metrics_routes.py` — stock_code 필터 동작 검증 테스트 1종 추가

- ✅ 자동 검증 완료 항목:
  - pytest `tests/test_metrics_routes.py`: 7 passed, 0 failed (신규 1종 포함)
  - pytest 전체 회귀: (검증 결과 기입 예정)
  - 타겟 API 검증 `GET /virtual-signals?stock_code=...`: (결과 기입 예정)
  - Playwright 타겟 검증: N/A (UI 변경 없음)
  - 코드 리뷰: Critical/High 이슈 0건

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영)
  - Railway 자동 배포 후 헬스체크 healthy 확인

---

### Hotfix: phase86-r3-unset-enum (2026-05-14)

PR: (생성 후 기입)

**발견 경위**: 2026-05-14 16:10 Phase 8.6 모니터링 발견 #7 결함.
**원인**: G3 단독 발동 시 `/override-status` `is_active` 판정 로직에서 해당 키가 누락. `affected_keys` 정적 계산으로 실제 활성 키와 불일치.

**변경 파일 (3개)**:
- `backend/core/override_keys.py` — SettingsOverrideKey Enum 신설 (오버라이드 키 단일화)
- `backend/api/routes/metrics.py` — `is_active` 판정 개선 + `affected_keys` 동적 계산
- `backend/tests/test_metrics_routes.py` — 오버라이드 상태 회귀 테스트 1종 추가

- ✅ 자동 검증 완료 항목:
  - pytest `tests/test_metrics_routes.py`: 로컬 8/8 통과 (Docker 컨테이너 미반영 — 빌드 후 재확인 필요)
  - 타겟 API `GET /override-status`: Docker 미빌드 상태로 미검증
  - Playwright 타겟 검증: N/A (UI 변경 없음)
  - 코드 리뷰: Critical/High 이슈 0건

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영 — core.override_keys 모듈 인식 확인)
  - Railway 자동 배포 후 `/api/v1/metrics/override-status` 응답 확인 (is_active 정확도)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
