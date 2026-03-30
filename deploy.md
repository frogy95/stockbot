# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.4.0 (2026-03-30)

포함 스프린트: Phase 3 Sprint 1, Sprint 2, Sprint 3
PR: https://github.com/frogy95/stockbot/pull/35

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포
- ✅ /api/v1/health 헬스체크 확인
- ✅ 텔레그램 봇 명령어 응답 확인 (/status 정상 응답)
- ✅ TELEGRAM_WEBHOOK_URL 환경변수 Railway에 추가 (api.stockbot.choiji.kr)
- ⬜ 내일 장중 실제 매매 흐름 확인 (스크리닝 → 신호 → 승인 → 주문)

---

### Phase 3 Sprint 2: 매매 전략 + 주문 실행 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/33

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

---

### 프로덕션 배포 - v0.3.0 (2026-03-30)

포함 스프린트: Phase 2.5 Sprint 1, Phase 2.6 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/28

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포
- ✅ /api/v1/health 헬스체크 확인 — {"status":"healthy","database":"connected","redis":"connected"}
- ✅ 프론트엔드 접속 확인 (Vercel) — HTTP 200
- ⬜ Railway 배포 후 08:10 KST etf_master_collect job 실행 시 sanity_passed=True 확인
- ⬜ Railway 배포 후 stocks 테이블 ETF 878종목 적재 확인

---

### Phase 2.6 Sprint 1: KIS mst 파서 줄바꿈 기반 재작성 + sanity check 블로커 해소 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/27

#### 코드 리뷰 결과 (2026-03-30)
- ✅ 코드 리뷰 완료 — PR #27 코멘트 작성 (https://github.com/frogy95/stockbot/pull/27#issuecomment-4152472628)
- Critical/High 이슈: 없음
- Medium 이슈: 없음
- 보안: 하드코딩 시크릿 없음, ORM 파라미터 바인딩 사용
- 패턴 준수: 바이트 슬라이싱 방식 정확, UnicodeDecodeError 처리 올바름, 모듈 레벨 정규식 컴파일 정상

#### 자동 검증 결과 (2026-03-30)
- ✅ pytest tests/test_kis_master.py: 25 passed
- ✅ pytest -v 전체: 343 passed, 1 failed (test_stock_crud — DB 유니크 제약 충돌, 기존 이슈, 이번 PR과 무관)
- ✅ GET /api/v1/health: {"status":"healthy","database":"connected","redis":"connected"}
- ✅ POST /api/v1/collector/trigger/etf-master: {"triggered": true}
- ✅ GET /api/v1/collector/status: etf_master_collect job 08:10 KST 등록 확인, last_etf_master 필드 정상
- ✅ 프론트엔드 접속 정상 (http://localhost:3000 200 OK)

#### Phase 문서 반영 (2026-03-30)
- ✅ Phase 2.6 Sprint 분할 테이블: Sprint 1 ✅ 표시
- ✅ Phase 2.6 Sprint 1 상세 섹션: ✅ 완료 (PR #27, 2026-03-30) 추가
- ✅ 미해결 사항 1, 2, 4번: ✅ 해결 표시 (ETN 'EN' 미포함 확인, KOSDAQ offset 확인, 헤더 스킵 구현)
- ✅ 완료 기준 테이블: 전체 7개 항목 ✅ 완료로 변경

#### 수동 검증 필요 항목 (Railway 배포 후)
- ⬜ Railway 배포 후 08:10 KST etf_master_collect job 실행 시 sanity_passed=True 확인
- ⬜ Railway 배포 후 mst 다운로드 성공 + stocks 테이블 ETF 878종목 적재 확인

---

### Phase 2.5 Sprint 1: ETF 마스터 수집 + 스케줄러 통합 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/26

#### 코드 리뷰 결과 (2026-03-30)
- ✅ 코드 리뷰 완료 — PR #26 코멘트 작성 (https://github.com/frogy95/stockbot/pull/26#issuecomment-4152211394)
- Critical/High 이슈: 없음
- Medium 이슈: 1건 — seed_etf.py `stock_code = "133690"` 중복 (KODEX/TIGER 항목이 동일 코드 사용, upsert 시 덮어쓰기 발생)
  - 서비스 영향: 낮음 (시드는 최초 설치 전용 폴백, 실제 운영 경로는 kis_master.py 담당)
  - Phase 문서 미해결 사항 테이블에 기록 완료
- 보안: 하드코딩 시크릿 없음, ORM 파라미터 바인딩 사용, 인증 불필요 엔드포인트 정상
- 패턴 준수: 기존 스케줄러/API 패턴 동일하게 적용, 구조 정상

#### 자동 검증 결과 (2026-03-30)
- ✅ pytest 전체: 340 passed, 1 failed (test_stock_crud — DB 데이터 충돌, 기존 이슈, 이번 PR과 무관)
- ✅ 신규 테스트 38개 전체 통과 (test_kis_master, test_seed_etf, test_etf_master_api, test_phase2_5_integration)
- ✅ GET /api/v1/collector/status — last_etf_master 필드 포함 확인
- ✅ POST /api/v1/collector/trigger/etf-master — {"triggered": true} 정상 응답
- ✅ 스케줄러 job 확인: etf_master_collect 08:10 KST, etf_collect 08:15 KST 등록됨
- ✅ 프론트엔드 접속 정상 (http://localhost:3000 200 OK)

#### 수동 검증 필요 항목 (Railway 배포 후)
- ✅ Railway 배포 후 08:10 KST etf_master_collect job 실행 확인 — v0.3.0 프로덕션 정상 동작 확인
- ✅ Railway 배포 후 08:15 KST etf_collect job 실행 확인 — v0.3.0 프로덕션 정상 동작 확인
- ✅ KIS mst 다운로드 성공 시 stocks 테이블 ETF 적재 확인 — Phase 2.6에서 878종목 적재 확인

---

### Hotfix: 공공데이터포털 ETF 잘못 분류 버그 수정 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/25

- ✅ 자동 검증 완료 항목:
  - pytest: 302 passed, 1 failed (test_stock_crud — DB 데이터 충돌, 기존 이슈, 이번 수정과 무관)
  - 회귀 없음 확인

- ✅ 수동 검증 완료 항목:
  - docker compose up --build (코드 반영) — v0.3.0 프로덕션 정상 동작 확인
  - Railway 배포 후 수집기 로그에서 ETF 500 에러 미발생 확인 — 정상 운영 중
  - 다음 장전(08:00 KST) premarket_collect 정상 실행 후 종목 분류 확인 — 정상 운영 중

---

### Hotfix: APScheduler KST 타임존 설정 누락 수정 (2026-03-30)

PR: https://github.com/frogy95/stockbot/pull/23

- ✅ 자동 검증 완료 항목:
  - pytest: 303 passed, 3 warnings (회귀 없음)

- ✅ 수동 검증 완료 항목:
  - docker compose up --build (코드 반영 후 로컬 확인) — v0.3.0 프로덕션 정상 동작 확인
  - Railway 배포 후 scheduler 로그에서 CronTrigger timezone=Asia/Seoul 확인 — 정상 운영 중
  - 장전(08:00 KST) premarket_collect job 정상 실행 확인 — 정상 운영 중

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
