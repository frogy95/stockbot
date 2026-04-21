# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 핫픽스 배포 - risk-counter-reset (2026-04-21)

포함: `reset_daily_counters()` 자동 호출 누락 버그 수정 + 관리자 수동 리셋 API 추가
PR: https://github.com/frogy95/stockbot/pull/153 (hotfix/risk-counter-reset → main)

#### 자동 검증 결과

- ✅ Railway 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}` 확인
- ✅ 신규 엔드포인트 등록 확인: `POST /api/v1/trading/risk/reset` → HTTP 401 (인증 필요, 정상)
- ✅ pytest 회귀: `test_risk_daily_capital + test_scheduler_vol5m` 10 passed

#### 배포 후 필수 수동 조치

- ⬜ **즉시 필요**: `POST /api/v1/trading/risk/reset` JWT 인증으로 1회 호출 — 현재 연속 손절 카운터 3/쿨다운/비상정지 플래그 초기화
- ⬜ 2026-04-22 09:00 장 시작 시 `일일 리스크 카운터 초기화 완료` 로그 자동 출력 확인 (스케줄러 wiring 검증)
- ⬜ 리셋 후 장중 `momentum_breakout` 신호 생성 시 텔레그램 승인 요청 수신 확인

#### Phase 8 Sprint 1 잔여 관찰 항목 (A안 기준)

**Sprint 2 착수 필수 조건 (①②③)**

- ⬜ ① Redis `realtime:{code}:execution` JSON OHLC 3필드 존재 확인 (장마감 직후 직접 조회)
- ⬜ ② 1~2시간 장중 모니터링 — 파싱 경고 비율 < 1%
- ⬜ ③ snapshot open_price 실값 사용 로그 확인

**Sprint 2 내부 통합 검증으로 이관 (④⑤)**

- ✅ ④ `momentum_breakout` 신호 — 2026-04-21 10:00 036830 1건 관측 (gap_rate=0.0393, breakout_pct=8.83%)
- ✅ ⑤ 갭 3%+ 분기 `breakout_ref=open_price` — 동일 신호 reason에서 확인
- ⬜ 샘플 5종목 실시간 OHLC를 KIS 공식 시세와 대조 (김단타 권고, 참고 검증)
- ⬜ `docker compose up --build` 로컬 스테이징 검증

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
