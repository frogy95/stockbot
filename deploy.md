# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Hotfix: prev-close-volume-confirm-integration (2026-04-30)

Phase 8.6 Sprint 2 NO-GO(2026-04-30)의 근본 원인 수정 — `_check_prev_close_volume_confirm` 게이트가 `vol_5m:{code}` 단일 JSON 배열 키를 기대했으나 collector(`VolumeAggregator`)는 `vol5m:{code}:{date}:{slot}` 슬롯 키 형식으로 적재 → 항상 fail-safe로 prev_close 후보 전체가 거부됨.

브랜치: `hotfix/prev-close-volume-confirm-integration` → main → develop
커밋: `14356df fix(strategy): prev_close_volume_confirm 게이트를 collector vol5m 슬롯 키와 통합`

변경 파일:
- `backend/modules/trading/strategies/momentum_breakout.py` — 슬롯 키 5개 직접 조회, buy_vol>sell_vol 양봉 근사 로직으로 교체
- `backend/tests/strategies/test_prev_close_volume_confirm.py` — 신규 슬롯 키 형식으로 테스트 재작성 (V1~V6)
- `backend/tests/test_momentum_breakout_metrics.py` — vol_5m 주입을 vol5m 슬롯 키로 갱신

변경 범위: 파일 3개, 코드 153줄 (전략 순수 변경 67줄 + 테스트 86줄 — 테스트 포함 시 50줄 기준 초과이나 프로덕션 로직 변경은 67줄)

- ✅ 자동 검증 완료 항목:
  - pytest: **1057 passed, 0 failed** (10분 9초, 사전 확인 완료)
  - 타겟 API 검증: **N/A** — 변경 범위가 백엔드 전략 게이트 내부 (API 인터페이스 변경 없음)
  - Playwright 타겟 검증: **N/A** — UI 변경 없음
  - 코드 리뷰: Critical/High 이슈 0건 (Medium 1건 — fail-safe False 반환 시 로그 없음, 아래 기록)

- ⬜ 수동 검증 필요 항목:
  - `docker compose up --build` (코드 반영 확인)
  - **Sprint 3 착수 전 1거래일 재관찰 필요 (2026-05-04 월)**: 신호 발생 여부, `matched_tiers` DB 저장 건수, Redis `vol5m:{code}:{date}:{slot}` 키 실 적재 여부 확인
  - Railway 환경변수 변경 없음 (MIN_VOLUME_FLOOR_HARD=0.3, MIN_VOLUME_FLOOR_MODE=dynamic, PARALLEL_OR_TIER_ENABLED=true 유지)

#### 코드 리뷰 결과 (2026-04-30)

- Critical/High 이슈: **0건**
- Medium 이슈 (1건): `_check_prev_close_volume_confirm`에서 redis.get 실패(`except Exception`) 시 경고 로그 없이 False 반환 — 진단 시 원인 파악 난이도 증가. 향후 Sprint에서 `logger.warning` 추가 권장.

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
