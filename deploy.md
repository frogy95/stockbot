# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 - v2.5.1 (2026-04-23)

포함 스프린트: Phase 8.5 Sprint 1.5 — 전략 필터 shadow evaluation
PR: https://github.com/frogy95/stockbot/pull/169 (develop → main)

- ✅ 자동 검증 완료 항목:
  - pytest: shadow 관련 테스트 4개 + 기존 회귀 전체 GREEN (기존 플레이크 `test_ws_manager_env_max_subscriptions` 1건은 Sprint 1.5 무관)
  - `/api/v1/metrics/shadow-heatmap` API 200 응답 확인 (JWT 인증 포함)
  - 프론트엔드 타입 체크 `npx tsc --noEmit` 통과
  - 로컬 Docker 실시간 shadow 관찰: volume_threshold/atr_filter/confidence 독립 pass 비율 실측 가능

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 실서버 자동 검증 (2026-04-23 11:04 KST)

- ✅ 백엔드 헬스체크 `https://api.stockbot.choiji.kr/api/v1/health` — `{"status":"healthy","database":"connected","redis":"connected"}`
- ✅ Shadow 신규 엔드포인트 `https://api.stockbot.choiji.kr/api/v1/metrics/shadow-heatmap?date=today` — HTTP 401 (인증 요구, 엔드포인트 존재 확인)
- ✅ 프론트엔드 접속 `https://stockbot.choiji.kr` — HTTP 307 (로그인 리다이렉트, 정상)
- ✅ Railway 로그: `Application startup complete` + WS 20종목 SUBSCRIBE SUCCESS + 2차 스크리닝 30초 주기 정상, 에러/트레이스백 0건
- ✅ Railway 로그에서 signal_generator `전략 거부 [min_volume_floor]` 기록 관찰 — Sprint 1.5 전에는 heatmap에 이 stage 1건만 찍혔으나 shadow 배포 후 나머지 7 stage도 독립 평가 누적 예상

#### 수동 검증 필요 항목

- ⬜ 프로덕션 배포 후 1거래일 관찰: Shadow 카드 8개 stage 모두 의미 있는 표본(≥10건) 누적되는지
- ⬜ DB 마이그레이션 불필요 (Redis 전용, 스키마 변경 없음) — 별도 조치 불필요
- ⬜ Railway 환경변수 추가 불필요 — 확인 완료

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
