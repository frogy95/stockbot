# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 6.1 Sprint 1

PR: https://github.com/frogy95/stockbot/pull/125

#### 코드 리뷰 결과 (2026-04-13)

- ✅ 코드 리뷰 완료 — Critical/High 이슈 없음
- 보안: 하드코딩 시크릿 없음, SQL/XSS 해당 없음 (Redis 전용)
- 성능: N+1 없음, 불필요 API 호출 없음
- 에러 핸들링: try/except 격리로 집계 실패 시 실시간 처리 무중단 보장
- 테스트: 신규 38건 추가 (test_market_progress 9 + test_volume_aggregator 10 + test_momentum_breakout 16 + test_scheduler_vol5m 3)
- Medium 이슈 2건 (미해결 사항으로 기록, 운영 영향 없음):
  - effective_progress 이중 max() 적용 (무해한 중복 코드)
  - get_first_seen_date Redis 전체 SCAN (디버깅 전용 엔드포인트, 호출 빈도 낮음)

#### 자동 검증 결과 (2026-04-13)

- ✅ pytest -v: **798 passed, 0 failed** (610초)
- ✅ 신규 테스트 38건: 전부 통과
- ✅ API 검증: GET /api/v1/collector/vol5m/005930 → HTTP 200, 슬롯 12개, vol5m_first_seen_date 정상
- ✅ 헬스체크: GET /api/v1/health → {"status":"healthy","database":"connected","redis":"connected"}
- ✅ 프론트엔드: localhost:3000 접속 정상 (307 redirect → /login)
- ⬜ Playwright UI 검증: playwright.config 미설치 — 브라우저로 수동 확인 필요

#### Phase 문서 반영

- ✅ phase6.1.md: Status, Sprint 분할 테이블, Sprint 1 상세 제목, 완료 기준 테이블 업데이트
- ✅ Medium 이슈 2건 미해결 사항 테이블에 추가 (#8, #9)

#### 수동 검증 항목 (develop → main 머지 전)

- ⬜ /api/v1/health 헬스체크 확인 (프로덕션)
- ⬜ 주요 페이지 접속 확인
- ⬜ vol5m API 응답 확인: `curl -s https://api.stockbot.choiji.kr/api/v1/collector/vol5m/005930 | jq .`
- ⬜ 장중 adjusted_ratio/volume_threshold/breakout_pct/market_progress 필드 로그 확인
- ⬜ 5분봉 Redis 키 축적 확인 (3거래일 모니터링)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
