# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: 2차 스크리닝 → 매매 엔진 연결 누락 수정 (2026-03-31)

PR: https://github.com/frogy95/stockbot/pull/50

- ✅ 자동 검증 완료 항목:
  - pytest: 539 passed, 0 failed
  - 관련 테스트(test_scheduler.py, test_trading_engine.py, test_engine_approval.py): 23 passed
  - 코드 리뷰: Critical/High 이슈 없음

- ✅ 배포 확인 (2026-03-31):
  - PR #51 (develop→main) 머지 완료
  - Railway 자동 배포 완료 (`Application startup complete`)
  - 스케줄러 11개 잡 등록 확인 (`railway logs` + `/api/v1/collector/status`)
  - `secondary_screen` next_run=null (장중 외 일시정지) 정상 확인

- ⬜ 아침 순차 체크 (`railway logs --tail 200`):

  **08:00 ~ 08:20 수집 단계**
  - ❌ `장전 수집 완료: N종목` (08:00) — **장애 발생**: Railway 컨테이너 2회 재시작으로 미완료
  - ✅ `ETF 마스터 수집 완료` (08:10) — 단, **sanity check 실패** (prev=277 → cur=878, 217% 변동) → 기존 DB ETF 유지
  - ❌ `1차 스크리닝 완료` (08:10) — 후보 0종목 (장전 수집 데이터 없음)
  - ⬜ `DART 재무 수집 완료: N건` (08:15)
  - ⬜ `ETF 수집 완료: N종목` (08:15)
  - ⬜ `네이버 센티멘트 수집 완료: N건` (08:20)

  **[장애 대응] 수동 복구 — 09:00 전에 완료 필요**
  ```bash
  # 1. 장전 수집 수동 트리거
  curl -X POST https://api.stockbot.choiji.kr/api/v1/collector/trigger/premarket

  # 2. 완료 확인 (null → timestamp 변경 시 완료, 약 2~5분 소요)
  curl https://api.stockbot.choiji.kr/api/v1/collector/status | jq '.last_premarket'

  # 3. 1차 스크리닝 수동 트리거
  curl -X POST https://api.stockbot.choiji.kr/api/v1/screening/trigger/primary

  # 4. 후보 종목 수 확인
  curl https://api.stockbot.choiji.kr/api/v1/screening/primary | jq '.total'
  ```
  - ⬜ 수동 장전 수집 완료 확인 (`last_premarket` timestamp 갱신)
  - ⬜ 1차 스크리닝 후보 N종목 (0 초과) 확인

  **09:00 ~ 09:10 장 시작 단계**
  - ⬜ `장중 시작: WS 연결` + `WS 연결 완료` (09:00)
  - ⬜ `2차 스크리닝 30초 주기 활성화` (09:00)
  - ⬜ ws_subscriptions > 0 확인:
    ```
    curl https://api.stockbot.choiji.kr/api/v1/collector/status
    ```
  - ⬜ 09:05 `market_open 복구 불필요: ws_subscriptions=N` 로그 (정상 시)

  **09:30 이후 매매 파이프라인 (이번 hotfix 핵심)**
  - ⬜ `2차 스크리닝 완료: N후보, N통과` 로그 30초마다 반복 확인
  - ⬜ 통과 종목 존재 시 `승인 요청: XXXXXX N주 @NNNNN` 로그 확인 (반자동 모드)
  - ⬜ 텔레그램 매매 신호 알림 수신 확인

  **이상 발생 시**
  - WS 미연결: `railway logs` 에서 에러 확인 후 텔레그램 복구 알림 대기
  - 수집 0종목: 공공데이터포털 API 키 만료 여부 확인 (`DATA_GO_KR_API_KEY`)
  - 1차 스크리닝 후보 0: 위 수동 복구 절차 재실행

- ⬜ **[장애 후속] 오늘 장 종료 후 Hotfix 검토**:
  - ETF sanity check 기준 재검토 (±10% → ±50% 또는 절대값 기준) — prev=277 vs cur=878 원인 확인
  - `last_premarket` 등 상태값 Redis 저장 전환 (재시작 시 초기화 방지)
  - Railway 재시작 원인 파악: `railway logs --tail 500 | grep -E "(ERROR|CRITICAL|OOM|crash)"`
  - backend health check 추가 (`/api/v1/health` — Railway 상태 감지용)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
