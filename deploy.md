# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Sprint 1 완료 — Phase 8 장중 OHLC 파싱 + 갭 분기 수정 (2026-04-20)

PR: https://github.com/frogy95/stockbot/pull/149 (→ develop)

#### 코드 리뷰 결과

- ✅ Critical/High 이슈: 0건
- ⬜ Medium 이슈 1건: `signal_generator.py` `_build_snapshot()` 독스트링(123줄)이 구 동작("Redis 체결 데이터에 intraday open/high/low가 없어 current_price로 대체한다") 설명으로 남아 있음. 실제 코드(139~141줄)는 실시간 값 우선 사용. 기능 버그 없음, 혼란 방지용 수정 권장 (Sprint 2에서 개선 가능).

#### 자동 검증 결과

- ✅ pytest -v: **854 passed**, 1 failed (pre-existing: `test_ws_manager_env_max_subscriptions` — Sprint 1 범위 아님)
- ✅ API 엔드포인트: Docker 실행 중 (backend:running, frontend:running, postgres:healthy, redis:healthy)

#### 수동 검증 필요 항목

- ⬜ `docker compose up --build` 로컬 스테이징 검증
- ⬜ 배포 직후 Redis `realtime:{code}:execution` JSON OHLC 3필드 존재 확인
- ⬜ 1~2시간 장중 모니터링 — 파싱 경고 비율 < 1%
- ⬜ 샘플 5종목 실시간 OHLC를 KIS 공식 시세와 대조 (김단타 권고)
- ⬜ 2거래일 연속 `momentum_breakout` 신호 1건 이상 생성 확인

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
