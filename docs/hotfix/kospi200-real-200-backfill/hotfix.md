# Hotfix: kospi200-real-200-backfill

**브랜치:** `hotfix/kospi200-real-200-backfill` (착수 시 main 기반 생성)
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** 📋 대기 — 2026-05-07 ATR 잡 관찰 결과 확인 후 착수 결정
**등재일:** 2026-05-06

---

## 배경

선행 핫픽스 [`hotfix-kospi200-master-backfill`](../kospi200-master-backfill/hotfix.md) (2026-05-06 배포)에서 다음 부채가 남았다.

1. **정적 백업 200종 중 148종이 stocks 부재**: `backend/data/kospi200_static_backup.json`은 파일 자체 주석에 `"sample top 50 + placeholder pad to 200"`이라 명시. 실제 KRX KOSPI200 200종이 아닌 상위 50종 + 합성 pad 150종으로 구성. 마이그레이션 `e5a7c91d4f08`이 적용되어도 `stocks.is_kospi200=true` 마킹은 매칭 가능한 52종에 그침 (production 확인: 5/6 KST 09:50).
2. **148종 `market_data` 일봉 미적재**: 위 정적 백업의 비매칭 코드가 일봉 적재 대상에서 누락.
3. **`ATR_COVERAGE_GAP_MAX=200` 일시 상향 잔존**: 선행 핫픽스 hotfix.md L64가 "일봉 백필 완료 후 30 원복"을 명시했으나, 그 일봉 백필 작업 자체는 어떤 Sprint·hotfix·backlog에도 등재되지 않음 → 본 핫픽스로 정식 등재.

---

## 문제 분석

### 증상
- ATR 분위수 캘리브레이션이 IQR P80을 산출하지만 표본이 52종으로 제한 → KOSPI200 단면 통계 신뢰성 저하 (본 의도: 200종 단면).
- `ATR_COVERAGE_GAP_MAX=200`가 임시값으로 유지되어 향후 실제 coverage_gap 모니터링 의미 상실 (148종이 누락되어도 임계 미발동).

### 원인
1. `static_backup.json`이 KRX 분기 리밸런싱 실데이터로 갱신된 적 없음 (sprint2.md Task 1 작성 시 placeholder pad 200으로 생성).
2. KOSPI200 종목 마스터를 일일·분기 단위로 자동 갱신하는 파이프라인 부재.
3. 일봉 수집기는 `stocks.is_listed=true`만 대상으로 하므로 `stocks` 미존재 종목은 자동 백필 대상 외.

### 영향 범위
- ATR 캘리브레이션 잡 (`08:35 KST`) — 표본 크기 52종 → 200종으로 정상화
- `ATR_COVERAGE_GAP_MAX` 환경변수 — 200 → 30 원복
- 신호 발행에는 직접 영향 없음 (ATR ceil 자체는 산출 가능). 분위수 정확도만 개선.

---

## 수정 계획

### 변경 예정 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/data/kospi200_static_backup.json` | KRX KOSPI200 실제 200종 코드로 갱신 (placeholder pad 제거). `_source` 필드에 갱신 일자·출처 명시 |
| `backend/alembic/versions/{rev}_kospi200_real_200_backfill.py` | 신규 마이그레이션: `UPDATE stocks SET is_kospi200=false; UPDATE stocks SET is_kospi200=true WHERE stock_code IN (...)` |
| `backend/scripts/backfill_kospi200_market_data.py` (신규) | 마킹된 200종 중 `market_data` 부재 종목의 일봉 30거래일 백필 (KIS REST `/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice`) |
| `backend/tests/test_kospi200_real_200_migration.py` (신규) | revision 체인 + 200종 백필 적용 + 매칭 카운트 검증 |
| Railway 환경변수 | `ATR_COVERAGE_GAP_MAX`: `200 → 30` 원복 |
| `.env.example` | 주석에서 "일시 상향" 문구 제거 |

### KOSPI200 200종 코드 확보 경로 (택1)
- **A안**: KRX 정보데이터시스템 (`data.krx.co.kr`) → 지수 → KOSPI200 구성종목 → CSV 다운로드 → 코드 추출 (수동, 분기 1회)
- **B안**: 한투 API `/uapi/domestic-stock/v1/quotations/inquire-index-component` 호출 (자동, 일일 갱신 가능)

본 핫픽스는 A안으로 1회 갱신 → 중기 개선(C단계, Sprint 3 이후)에서 B안 자동화 잡 도입.

---

## 검증 계획

### 자동 검증 (착수 시)
- ⬜ pytest 전체 통과 (1060+ tests)
- ⬜ `pytest tests/test_kospi200_real_200_migration.py -v`
- ⬜ alembic upgrade head 정상 적용
- ⬜ 일봉 백필 스크립트 dry-run 로그 확인

### 수동 검증 (배포 후)
- ⬜ Railway alembic 자동 적용 (`stocks.is_kospi200=true` ≥ 200건)
- ⬜ 일봉 백필 스크립트 실행 (`railway run backfill_kospi200_market_data.py`) — 누락 종목 0건 도달
- ⬜ Railway 환경변수 `ATR_COVERAGE_GAP_MAX=30` 원복
- ⬜ 다음 거래일 ATR 잡 결과: `metrics:atr:dist:{date}.sample_n ≈ 200`, `coverage_gap < 30`, `safe_mode:active = None`
- ⬜ `metrics:atr:ceil:fallback_count = '0'` 유지

---

## 착수 게이트

다음 조건 중 하나 충족 시 본 핫픽스를 main 기반 브랜치로 즉시 착수:

1. **2026-05-07 KST 16:00**: ATR 잡(KST 08:35) 결과가 G1 PARTIAL 지속 (sample_n < 100, coverage_gap > 50) — 본 부채 해소 우선순위 상승
2. **Sprint 3 착수 직전**: G1 PASS여도 `ATR_COVERAGE_GAP_MAX=200` 임시 운영을 정상화하기 위해 Sprint 3 GO 직전 1일 내 마무리
3. **사용자 명시 지시**: "B 핫픽스 착수해" 등 직접 트리거

---

## PR
- **URL:** (착수 후 생성)
- **대상:** main
- **역머지:** ⬜ 착수 후 develop에 역머지 필요
