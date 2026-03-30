# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.2.0 (2026-03-30)

포함 스프린트: Phase 2 Sprint 1, Phase 2 Sprint 2, Phase 2 Sprint 3
PR: https://github.com/frogy95/stockbot/pull/8

- ✅ Vercel 프론트엔드 자동 배포 (main 머지 시 자동 시작)
- ✅ Railway 백엔드 자동 배포 (main 머지 시 자동 시작)

#### 배포 후 자동 검증 필요 항목

- ✅ /api/v1/health 헬스체크 확인
- ✅ /api/v1/screening/status 스크리닝 상태 확인
- ✅ /api/v1/collector/status 수집기 상태 확인
- ✅ 프론트엔드 접속 확인 (https://stockbot-blush.vercel.app)
- ✅ Railway 배포 로그 확인 (alembic 신규 마이그레이션 3종 적용 확인)

#### 수동 검증 필요 항목

- ⬜ KIS API 실거래 확인: 평일 장중 수동 검증 필요 (모의거래 시세 조회 + 주문 체결 테스트)
- ✅ 공공데이터포털 수집기 실데이터 확인: 2,913 종목 수집 완료 (basDt=20260327)
- ✅ DART 재무 수집기 실데이터 확인: corp_code 115,603건 초기화 + 재무 22건 수집 완료
- ✅ 네이버 센티멘트 수집기 실데이터 확인: 300건 수집 완료 (1차 스크리닝 30종목 대상)

---

### 프로덕션 배포 - v0.1.0 (2026-03-29) ✅ 완료

포함 스프린트: Phase 0.5 Sprint 1, Phase 1 Sprint 1, Phase 1 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/4

#### 프로덕션 URL

| 서비스 | URL | 상태 |
|--------|-----|------|
| 프론트엔드 (Vercel) | https://stockbot-blush.vercel.app | ✅ 200 |
| 백엔드 (Railway) | https://stockbot-production-6a39.up.railway.app | ✅ healthy |
| Swagger UI | https://stockbot-production-6a39.up.railway.app/docs | ✅ 200 |

#### 배포 전 체크리스트

- ✅ pytest 95개 전체 통과 (0 failed)
- ✅ Docker 4컨테이너 정상 가동 확인
- ✅ 로컬 API 검증 완료 (/api/v1/health, /api/v1/settings, /api/v1/kis/status)
- ✅ develop → main PR #4 생성 및 머지 완료

#### 배포 후 검증

- ✅ GET https://stockbot-production-6a39.up.railway.app/api/v1/health → {"status":"healthy","database":"connected","redis":"connected"}
- ✅ GET https://stockbot-production-6a39.up.railway.app/api/v1/settings/trading_env → {"key":"trading_env","value":"paper"}
- ✅ GET https://stockbot-production-6a39.up.railway.app/api/v1/kis/status → {"environment":"paper","token_valid":true}
- ✅ GET https://stockbot-blush.vercel.app → 200
- ✅ Swagger UI https://stockbot-production-6a39.up.railway.app/docs → 200
- ⬜ KIS API 실거래 확인: 평일 장중 수동 검증 필요 (모의거래 시세 조회 + 주문 체결 테스트)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
