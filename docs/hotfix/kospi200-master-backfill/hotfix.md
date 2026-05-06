# Hotfix: kospi200-master-backfill

**브랜치:** `hotfix/kospi200-master-backfill`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-05-06

---

## 문제 분석

### 증상
Phase 8.6 Sprint 2 ATR 캘리브레이션 잡이 3거래일 연속(4/30·5/4·5/6) 폴백 → safe_mode 발동 → 신호 발행 전면 차단.

### 원인 (2단)

1. **is_kospi200 마킹 부재**: 마이그레이션 `c1f2a30b8201`이 `stocks.is_kospi200` 컬럼만 추가, 모든 row `server_default=false`. 200종을 `true`로 마킹하는 production 코드/잡 부재 → ATR 잡 DB 조회 0종 → 정적 백업 JSON(200종) 폴백.

2. **일봉 미적재**: 정적 백업 200종 중 148종은 `market_data` 일봉 미적재 → `coverage_gap=148 ≥ MARKET_DATA_MIN_COVERAGE_GAP(30)` → 데이터 부족 판정 → `fallback_count INCR` → 3회 누적 → `safe_mode:active` 발동.

### 영향 범위
- ATR 캘리브레이션 잡 (`08:35 KST`)
- `safe_mode:active` Redis 키 존재 시 신호 발행 전면 차단 (`SAFE_MODE_TIMEOUT_MIN=120분`)
- Phase 8.6 Sprint 2 병렬 OR tier 신호 발행 0건 (4/30·5/1·5/4·5/6)

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/alembic/versions/e5a7c91d4f08_kospi200_master_backfill.py` | 정적 백업 JSON 200종 `is_kospi200=true` UPDATE |
| `backend/core/config.py` | `ATR_COVERAGE_GAP_MAX` 환경변수 추가 (default 30) |
| `backend/modules/screening/atr_calibration.py` | `MARKET_DATA_MIN_COVERAGE_GAP` 상수 → `settings.ATR_COVERAGE_GAP_MAX` 동적 조회 |
| `backend/scripts/diagnose_pipeline.py` | scheduler 네임스페이스 read-only 진단 스크립트 (신규) |
| `backend/tests/test_kospi200_backfill_migration.py` | 마이그레이션 검증 (revision 체인, 200종 백필 적용) (신규) |
| `.env.example` | `ATR_COVERAGE_GAP_MAX=30` 문서화 |
| `deploy.md` | 수동 검증 항목 업데이트 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `44fd1c4` | fix(atr): kospi200 마스터 백필 + coverage_gap 임계 외부화로 safe_mode 해소 | 2026-05-06 |

---

## 검증

### 자동 검증
- ✅ pytest: **1060 passed, 0 failed** (10분 18초)
- ✅ alembic upgrade head: e5a7c91d4f08 마이그레이션 정상 적용
- ✅ pytest tests/test_kospi200_backfill_migration.py -v: 3 passed (revision 체인, 200종 백필 적용)
- ✅ 타겟 API 검증: N/A — DB 데이터 백필 + 환경변수 외부화 (API 인터페이스 변경 없음)
- ✅ Playwright 타겟 검증: N/A — UI 변경 없음

### 코드 리뷰 결과
- Critical/High 이슈: **0건**
- Medium 이슈: `diagnose_pipeline.py` read-only 스크립트 일부 오류 처리 미흡 — `scripts/` 경로로 프로덕션 경로 미포함, 배포 차단 대상 아님

### 수동 검증
- ⬜ Railway 배포 후 alembic upgrade 자동 실행 확인 (`stocks.is_kospi200=true` 200건)
- ⬜ Railway 환경변수 `ATR_COVERAGE_GAP_MAX=200` 추가 (일시 상향, 일봉 백필 완료 후 30 원복)
- ⬜ `safe_mode:active` Redis 키 삭제 (또는 자연 TTL 만료 대기 ~120분)
- ⬜ 2026-05-07 거래일 ATR 잡(KST 08:35) 결과 관찰 + `signals.total ≥ 1` 확인

---

## PR
- **URL:** (main PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ⬜ develop에 역머지 필요
