# 임계 재조정 Hotfix 계획 (Sprint 4 후속)

> 작성일: 2026-05-11
> 입력: `threshold_recalibration_candidates.md`, Paper 1거래일 관찰(2026-05-11)
> 결정: 단일 hotfix 불가 → **3단계 순차 처리** (진단 → 백필 → 재조정)

---

## 1. 현황 진단 (Paper 관찰 2026-05-11 12:00 KST)

| 지표 | 값 | 비고 |
|------|-----|------|
| volume_surge dry_run (05-08, 05-11) | 0 / 0 | 게이트 ≥1 미달 |
| time_filter 차단 (morning/afternoon/gap) | 0 / 0 / 0 | 게이트 ≥1 미달 |
| /health/observation-daily 신호 (05-11) | prev_high 1건, 나머지 0건 | 전략 살아있음, 발생 희박 |
| **R3 auto_rollback** | **is_active=true** (2026-05-08 16:10 KST 발동) | 사유: `auto_rollback_2d_zero_signals` |

**롤백 부수효과** (`scheduler.py:1133-1148`):
- `settings:override:MIN_VOLUME_FLOOR_MODE = legacy` (7일 TTL)
- `settings:override:SECONDARY_POOL_FALLBACK_ENABLED = False` (7일 TTL)

→ 현재 스크리닝이 **legacy 모드**로 강제 전환된 상태. Phase 8.6 Sprint 1~3의 신규 임계 효과가 차폐됨.

---

## 2. 단일 Hotfix 불가 이유

`threshold_recalibration_candidates.md` 결론: **데이터 부족(18 거래일 < 60 거래일 요구)으로 grid search 미수행**, 거의 모든 임계값에 "현 값 유지" 권고. 즉 **현시점에서 임계값을 변경할 정량적 근거가 없음**.

따라서 "임계 재조정 hotfix" 하나로 끝나는 작업이 아니라, 아래 3단계가 필요합니다.

---

## 3. 권장 3단계 처리

### 단계 A — 진단 hotfix (선행, **즉시 가능**)

**목표**: 신호 0건의 진짜 원인 식별 (임계 vs 롤백 vs 데이터 vs 스크리닝)

작업 (관찰 전용, 코드 변경 없음 또는 최소):
1. R3 롤백이 차폐 중인 신규 로직 영향 측정
   - `MIN_VOLUME_FLOOR_MODE=legacy` 강제로 스크리닝 통과 종목 수 비교 (현재 vs Sprint 3 기본값)
2. volume_surge dry_run 0건 원인 분리
   - 후보: (a) 진입 종목 미통과, (b) vol5m 키 미적재, (c) time-filter 차단, (d) 우선순위 큐 누락
   - 로그 grep: `volume_surge`, `vol5m` 키 적재 카운트, `should_block_entry` 호출 빈도
3. orderbook/vol5m Redis 키 실제 적재 확인 (관찰 항목 #2, #3)
   - **차단된 SSH redis 접근을 대체할 진단 API** 추가 검토 (예: `/api/v1/health/sprint3-keys` 엔드포인트 1개)

산출물: 진단 보고서 `docs/phase/phase8.6/sprint4/zero_signal_diagnosis.md`
**hotfix 브랜치**: `hotfix/zero-signal-diagnosis-api` (최소 진단 엔드포인트 1개만 추가 시)

---

### 단계 B — 데이터 백필 (병행 가능)

**목표**: 60거래일 일봉 데이터 확보 → grid search 입력 마련

작업:
1. `POST /api/v1/backtest/backfill-daily` 호출 (hotfix #217로 동작 검증됨)
2. 적용 범위: 최근 90일, KOSPI200 200종목
3. KIS rate limit 고려: 일 500건 → **분산 호출 필요** (12,000건 ÷ 500 = ≥24 거래일 또는 1 거래일에 4초 간격 호출)
4. 백필 완료 후 `SELECT COUNT(*) FROM daily_ohlc WHERE date >= today - 90` 검증

이 단계는 **코드 변경 없음** — API 트리거만 필요. Hotfix 아닌 운영 작업.

---

### 단계 C — Grid Search + 재조정 hotfix (B 완료 후)

**목표**: 임계값 재조정 후 R3 롤백 해제 + Paper 관찰 재시작

작업:
1. 60일 데이터 확보 후 `WalkForwardRunner.run(n_days=60)` 실행
2. tier별 pass_rate simulated vs actual 격차 측정
3. 격차 > 10%p 임계 식별 → 환경변수 또는 default 변경
4. 재조정 적용 후:
   - R3 override 해제: `DEL settings:override:MIN_VOLUME_FLOOR_MODE`, `SECONDARY_POOL_FALLBACK_ENABLED`, `triggered_at`, `reason`
   - Paper 5거래일 관찰 재시작 (G-Bt3 측정)

**hotfix 브랜치**: `hotfix/volume-threshold-recalibration` (재조정 대상이 명확해진 후)

---

## 4. 의사결정 포인트 (사용자 확인 필요)

| # | 결정 사항 | 옵션 |
|---|----------|------|
| Q1 | 단계 A를 hotfix로 진행? | (i) hotfix로 진단 API 추가 (ii) Sprint 5 신규로 흡수 (iii) 진단 API 없이 로컬에서만 수동 분석 |
| Q2 | R3 롤백 즉시 해제? | (i) 임계 재조정 완료 후 자연 해제 (권장) (ii) 운영 판단으로 즉시 강제 해제 |
| Q3 | 단계 B 백필을 누가 트리거? | (i) 사용자 직접 (ii) 본 세션에서 토큰으로 API 호출 |
| Q4 | dry_run 0건이 임계 문제일 경우 환경변수 임시 완화 hotfix? | (i) 추후 grid search 결과 따라 결정 (ii) 즉시 임시 완화(위험) |

---

## 5. 즉시 실행 가능한 조치 (Quick Win)

데이터 백필이 비차단 작업이므로 우선 트리거 가능:

```bash
# 사용자 토큰 환경변수로 설정 후
curl -X POST "https://api.stockbot.choiji.kr/api/v1/backtest/backfill-daily" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"start_date":"2026-02-10","end_date":"2026-05-11"}'
```

백필 진행 중 단계 A(진단)를 병행하여 원인을 좁히고, 백필 완료 시 단계 C 착수 가능.

---

## 6. 산출물 체크리스트

- ⬜ Q1~Q4 결정
- ⬜ 단계 A 진단 보고서 작성
- ⬜ 단계 B 백필 트리거 및 검증
- ⬜ 단계 C grid search 결과 + 재조정 hotfix PR
- ⬜ R3 override 해제 및 Paper 5거래일 관찰 재시작
- ⬜ deploy.md 본 관찰 결과 기록
