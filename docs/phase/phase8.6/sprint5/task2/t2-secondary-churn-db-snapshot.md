# T2 Step 3 — #14 secondary 4h 교체율 DB 측정 스냅샷

> Phase 8.6 Sprint 5 Task 2 Step 3 — `screening_results` 테이블을 직접 쿼리해 secondary 풀의 4시간 윈도우 교체율을 정량 측정한다.
> **임계 변경 0건, 코드 변경 0건(스크립트 추가만)**.

## 데이터 소스

- 테이블: `screening_results` (Sprint 1 이전 도입 모델)
- 필터: `screening_type = 'secondary'`
- 기간: 로컬 stockbot DB 최근 14일 (2026-05-01 ~ 2026-05-14 KST)
- 적재 분포: 일별 secondary 행 수
  | 날짜 (KST) | secondary 행 수 |
  |------------|------|
  | 2026-05-06 | 582 |
  | 2026-05-07 | 265 |
  | 2026-05-08 | 614 |
  | 2026-05-11 | 49 |
  | 2026-05-12 | 1,375 |
  | 2026-05-13 | 553 |
  | 2026-05-14 | 2,806 |
- 시간대 분포(KST hour, 전체 14일 합):
  | 시 | 행 수 | 시 | 행 수 |
  |---|---|---|---|
  | 09 | 1,078 | 13 | 2,332 |
  | 10 | 2,596 | 14 | 2,218 |
  | 11 | 2,252 | 15 | 644 |
  | 12 | 2,163 | | |

→ KST 10~14시에 균등 적재되어 있어 4h 윈도우 분석 가능.

## 측정 1 — 점검 시각별 4h × 4h 윈도우 jaccard

**스크립트:** `backend/scripts/diagnostic/secondary_churn.py`

**검증 명령:**
```
docker compose exec backend python -c "import asyncio; from scripts.diagnostic.secondary_churn import compute_churn_4h; asyncio.run(compute_churn_4h(days=5))"
```

**점검 시각:** KST 09:30 / 11:30 / 13:30 — 각 시점에 대해 직전 4h vs 그 이전 4h.

| date | check (KST) | current pool | prev pool | inter | union | jaccard | churn |
|------|-------------|--------------|-----------|-------|-------|---------|-------|
| 2026-05-15 | 09:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-15 | 11:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-15 | 13:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-14 | 09:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-14 | 11:30 | 14 | 0 | 0 | 14 | 0.0 | 1.0 |
| 2026-05-14 | 13:30 | 16 | 0 | 0 | 16 | 0.0 | 1.0 |
| 2026-05-13 | 09:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-13 | 11:30 | 6 | 0 | 0 | 6 | 0.0 | 1.0 |
| 2026-05-13 | 13:30 | 6 | 0 | 0 | 6 | 0.0 | 1.0 |
| 2026-05-12 | 09:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-12 | 11:30 | 9 | 0 | 0 | 9 | 0.0 | 1.0 |
| 2026-05-12 | 13:30 | 9 | 0 | 0 | 9 | 0.0 | 1.0 |
| 2026-05-11 | 09:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-11 | 11:30 | 0 | 0 | 0 | 0 | null | null |
| 2026-05-11 | 13:30 | 1 | 0 | 0 | 1 | 0.0 | 1.0 |

**한계 — 측정 1의 prev_pool=0 원인:**
점검 시각 09:30의 prev 윈도우는 KST 01:30~05:30(휴장)으로 항상 0이 정상. 11:30/13:30 시점의 prev 4h 윈도우(07:30~11:30, 09:30~13:30)에서 0이 나오는 이유는 **secondary 적재가 점검 시각 직전 4h에 거의 집중 발생하기 때문**으로 보임 — current pool은 작지만 그 직전 4h에는 동일 종목이 아예 없음. 이 자체가 hysteresis 부재 + 풀 회전 빠름 증거.

## 측정 2 — 일별 13:30 전/후 4h 윈도우 직접 비교 (SQL)

원천 SQL:
```sql
WITH win AS (
  SELECT date(screened_at AT TIME ZONE 'Asia/Seoul') AS d,
         CASE WHEN (screened_at AT TIME ZONE 'Asia/Seoul')::time < time '13:30'
              THEN 'A' ELSE 'B' END AS bucket,
         stock_code
  FROM screening_results
  WHERE screening_type='secondary' AND screened_at > now() - interval '14 days'
),
pa AS (SELECT d, stock_code FROM win WHERE bucket='A' GROUP BY d, stock_code),
pb AS (SELECT d, stock_code FROM win WHERE bucket='B' GROUP BY d, stock_code)
SELECT COALESCE(pa.d, pb.d) AS d,
       COUNT(DISTINCT pa.stock_code) AS pool_A_pre1330,
       COUNT(DISTINCT pb.stock_code) AS pool_B_post1330,
       COUNT(DISTINCT CASE WHEN pa.stock_code=pb.stock_code THEN pa.stock_code END) AS intersect_cnt
FROM pa FULL OUTER JOIN pb ON pa.d=pb.d AND pa.stock_code=pb.stock_code
GROUP BY COALESCE(pa.d, pb.d) ORDER BY 1;
```

| date | pool A (09:00~13:30) | pool B (13:30~17:30) | intersect | jaccard | churn |
|------|---------------------:|---------------------:|----------:|--------:|------:|
| 2026-05-06 | 6  | 6  | 3  | 0.33 | 0.67 |
| 2026-05-07 | 4  | 2  | 2  | 0.50 | 0.50 |
| 2026-05-08 | 7  | 2  | 2  | 0.29 | 0.71 |
| 2026-05-11 | 1  | 1  | 1  | 1.00 | 0.00 |
| 2026-05-12 | 9  | 5  | 4  | 0.40 | 0.60 |
| 2026-05-13 | 6  | 7  | 5  | 0.63 | 0.38 |
| 2026-05-14 | 14 | 14 | 14 | 1.00 | 0.00 |

**평균 churn:** 0.41 (7일 단순 평균, 표본 적음)
**최대:** 0.71 (5/08), **최소:** 0.00 (5/11, 5/14)

## 판정

> 임계 변경 0건. 결론은 raw 측정치 그대로 제공하고, 후속 Task 5(종합 보고)에서 통합 판정한다.

1. **"4h 100% 교체율" 주장은 raw에서 부분적으로 재현됨** — 측정 1의 11:30/13:30 점검 시각 churn은 1.0 (즉시 직전 4h에는 동일 secondary 종목이 없음). 그러나 이는 적재 패턴(secondary 행이 점검 시각 직전 4h에 집중) 때문에 발생하는 산물일 가능성 큼.
2. **일별 13:30 분할 측정(측정 2)에서는 평균 churn 0.41** — 100% 교체와는 거리가 있음. 일자별 0.0 ~ 0.71 범위로 변동.
3. **단일 결론 불가**: 두 측정이 다른 그림을 보여줌. 데이터 부족 가설 vs 구조 결함(hysteresis 부재) 가설 중 어느 쪽인지 단정 불가.

### 후속 Task 5에서 통합 판정에 필요한 추가 분석

- **프로덕션 DB 동일 SQL 재실행** — 로컬 stockbot DB는 secondary 적재 일관성이 불확실(5/11 = 49행, 5/14 = 2806행 편차).
- **secondary 게이트 코드의 hysteresis(이력 잔존) 로직 존재 여부 라인 확인** — Task 1 진단서(`t1-diagnosis.md`)의 #11 분석과 연계.
- **점검 시각을 거래 시작/종료 시각(09:00, 15:30)으로 고정**하여 윈도우 분할 일관성 확보.

## 한계 (보고서 명시 필수)

- `screening_results.screened_at` 적재 분포가 시간대별로 균등하지 않음. 점검 시각 09:30의 prev 윈도우는 휴장 → 항상 null.
- 로컬 stockbot DB 표본 7거래일 × 시간대 3종 = 21 샘플 (중 9개 null). 프로덕션 재실행 필요.
- hysteresis 부재가 구조 결함이라는 단정은 코드 라인 인용 없이 본 스냅샷만으로는 부적절(Task 1 진단서 §3 #11 결과와 교차 검증).
