# 2026-05-14 (목) — Phase 8.6 A안(real-momentum) 첫 검증 모니터링 계획

> 작성: 2026-05-13 16:50 KST
> 전제: 2026-05-13 A안 hotfix 배포 완료 + R3 차단 키 manual DEL 완료
> 한 줄 목표: **+7% 이상 모멘텀 종목이 1차 풀에 진입하고 2차까지 통과해 신호 ≥ 1건 발생하는지 검증**

---

## 1. 사전 상태 (2026-05-13 16:50 KST 시점)

| 항목 | 상태 |
|------|------|
| PR #233 (real-momentum hotfix) main 머지 | ✅ (c2037fe6, 16:25 KST) |
| Railway 자동 재배포 | ✅ 완료 |
| `change_rate_max` 7 → 30 | ✅ 코드 반영 |
| `trade_strength_min` 100 → 80 | ✅ 코드 반영 |
| Railway env `MIN_VOLUME_FLOOR_HARD=0.25` | ✅ 사용자 설정 완료 |
| Redis R3 차단 키 6개 DEL | ✅ 완료 |
| `phase86-status.rollback_active` | ✅ false |
| `phase86-status.circuit_breaker_active` | ✅ false |
| `override-status.is_active` | ✅ false |

**모든 차단 게이트 클린, 첫 검증 준비 완료.**

---

## 2. 모니터링 일정 (2026-05-14 KST)

### 09:00 — 장 개장 (자동 동작 관찰)

- 2차 스크리닝 30초 주기 시작
- momentum_breakout 직렬 모드 (`PARALLEL_OR_TIER_ENABLED=false`)
- 수동 액션 없음

### 09:30 — 1차 점검 (T+30분) — A안 효과 1차 검증

목적: **모멘텀 종목이 1차/2차 풀에 진입했는가**

| Endpoint | 검증 항목 |
|----------|----------|
| `/screening/primary` | 결과 종목들의 `change_rate` 분포 — +7% 이상 종목 ≥ 1개 존재 |
| `/screening/secondary` | 통과 종목 수 (어제 2개 → 오늘 ≥ 5 기대) |
| `/health/observation-daily` | signals.total 초기 추이 |
| `/metrics/phase86-status` | rollback/circuit_breaker 둘 다 false 유지 |
| `/health/sprint3-keys` | vol5m_count > 0, orderbook_count ≥ 10 |

**합격 기준**:
- 1차 풀에 +7% 초과 종목 1개 이상 진입 → A안 1차 필터 효과 입증
- 2차 통과 종목 수 ≥ 5 → A안 2차 필터 효과 입증
- 차단 게이트 모두 false 유지

**불합격 시**:
- 1차에 +7% 초과 종목 0개 → Railway 빌드 미반영 또는 다른 1차 필터 발견 필요 (트러블슈팅 §5.1)
- 2차 통과 2개 이하 → trade_strength_min 80 여전히 빡빡, 추가 trace 필요

### 12:00 — 2차 점검 (오전장 누적)

목적: **신호 ≥ 1건 발생 여부**

| Endpoint | 검증 항목 |
|----------|----------|
| `/health/observation-daily` | **signals.total ≥ 1** (가장 중요) |
| `/metrics/stage-heatmap?date=today` | reject 분포 — 단일 stage 50% 이하 |
| `/metrics/top-rejects` | 어떤 종목이 어디서 막혔는지 |
| `/metrics/virtual-signals?stock_code=014680` | 14680 같은 모멘텀 종목이 평가받았는지 |

**합격 기준**:
- `signals.total ≥ 1` (어떤 tier든)
- 단일 stage 점유 ≤ 50%

**신호 0건이면**:
- top-rejects + stage-heatmap top 1 stage 분석
- 추가 trace: 1차 통과 모멘텀 종목의 momentum_breakout 경로 추적

### 14:30 — 3차 점검 (eod_blocked 직전)

목적: 최종 신호 카운트 + 오후장 누적 패턴

- `signals.total` 최종 (장 종료 직전)
- 14:30 이후 `engine_block reason=eod_blocked` 로그 확인
- 어제 대비 fallback `triggered_count` 추세

### 16:10 — 4차 점검 (auto_rollback 자동 실행 후)

목적: **G2/G3 발동 여부 + unset 분기 작동 검증**

| 시나리오 | 결과 해석 |
|----------|----------|
| 오늘 신호 ≥ 1건 + 어제까지 0건 | R1 미발동 (3일 연속 0건 깨짐), R2 발동 가능성 (fallback 3일 연속) |
| 오늘 신호 0건 + 어제 0건 + 그제 0건 | **R1 3일 트리거 — 영구 차단 위험** |
| pass_rate ≥ 10% (오늘 신호 발생) | G3 미발동 또는 기존 활성 자동 해제 (PR #228 unset 분기 작동 검증 가능) |
| pass_rate < 10% | G3 발동 또는 유지 |

특히 16:10 시점 Redis 키 상태 확인:
- `phase86:rollback:active` (있으면 활성)
- `phase86:circuit_breaker:active`
- `settings:override:*`

### 16:30 — 종합 보고

- `docs/phase/phase8.6/sprint4/2026-05-14-monitoring-result.md` 작성
- 합격/불합격 5개 기준 결과
- 다음 액션 결정

---

## 3. 합격/불합격 판정 기준 (전체)

| # | 조건 | 합격 기준 | 측정 |
|---|------|----------|------|
| 1 | A안 1차 필터 효과 | 1차 풀에 +7% 이상 종목 ≥ 1 | `/screening/primary` |
| 2 | A안 2차 필터 효과 | 2차 통과 종목 ≥ 5 | `/screening/secondary` |
| 3 | 데이터 파이프라인 | vol5m ≥ 800, orderbook ≥ 15 | `/health/sprint3-keys` |
| 4 | **신호 생성** | **signals.total ≥ 1** | `/health/observation-daily` |
| 5 | 임계 통과 분포 | 단일 stage ≤ 50% | `/metrics/stage-heatmap` |
| 6 | 차단 게이트 안정성 | R1/R3/G3 모두 false 유지 (또는 unset 분기 정상 작동) | `/metrics/phase86-status`, `/metrics/override-status` |

**최우선 기준은 #4 신호 생성**. 다른 기준 미충족이어도 신호 ≥ 1건이면 A안 입증으로 평가.

---

## 4. 사용자 수동 액션 (오늘 밤 ~ 내일 개장 전)

| # | 작업 | 완료 |
|---|------|------|
| 1 | R3 Redis 키 6개 DEL (Claude가 실행) | ✅ 2026-05-13 16:48 KST |
| 2 | Railway 환경변수 `MIN_VOLUME_FLOOR_HARD=0.25` 유지 확인 | ✅ 사용자 |
| 3 | PR #235 docs 머지 (선택) | ⬜ |
| 4 | 내일 09:00 전 Claude 세션 띄우고 cron 5개 재등록 | ⬜ |

---

## 5. 트러블슈팅 플레이북

### 5.1 신호 0건 지속 시 — 추가 trace 단계

**1순위: A안이 실제 반영됐는지 검증**

```bash
# 1차 풀에 +7% 이상 종목 진입 여부 확인
curl -s -H "Authorization: Bearer <TOKEN>" \
  "https://api.stockbot.choiji.kr/api/v1/screening/primary" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); \
    print([r['stock_code'] for r in d['results'] if r.get('change_rate', 0) > 7])"
```

빈 리스트면:
- Railway 빌드가 새 코드 반영했는지 확인 (`/api/v1/health` 응답에 빌드 SHA 확인 시도)
- 또는 1차 스크리닝에 `change_rate_max` 외 다른 컷이 있는지 코드 재검토

**2순위: 2차 통과 종목 trace**

```bash
# 2차 통과 종목 + score 확인
curl -s -H "Authorization: Bearer <TOKEN>" \
  "https://api.stockbot.choiji.kr/api/v1/screening/secondary"
```

여전히 ≤ 2 종목이면:
- 2차 reject 통계는 Railway 로그에 `"2차 스크리닝 필터 탈락 통계"` 로그 grep
- `trade_strength_min=80`도 모자라면 60까지 추가 완화 hotfix

**3순위: 모멘텀 종목 개별 trace**

```bash
# 1차 풀에서 +7% 이상 종목 1개 선택 후 momentum_breakout 경로 추적
curl -s "https://api.stockbot.choiji.kr/api/v1/metrics/virtual-signals?stock_code=<CODE>"
curl -s "https://api.stockbot.choiji.kr/api/v1/collector/realtime/<CODE>"
```

`execution: null` 종목이면 KIS 실시간 데이터 수집 파이프라인 진단 필요.

### 5.2 R1 3일 트리거 위험 (오늘+내일도 0건이면)

- 2026-05-13(2일째), 2026-05-14(3일째) 0건이면 16:10에 R1 다시 SET
- 이때는 manual clear 반복하지 말고 시스템 자가치유 분기에 맡길 것 (unset 분기 검증 기회)
- 대신 trace 단계로 즉시 진입 — 임계 추가 완화는 마지막 옵션

### 5.3 R3 재발동 시 manual clear 명령 (어제 검증된 1줄)

```bash
CMD='python3 -c "import asyncio,os;from redis.asyncio import from_url as f;r=f(os.environ[\"REDIS_URL\"]);K=\"phase86:rollback:active phase86:circuit_breaker:active settings:override:SECONDARY_POOL_FALLBACK_ENABLED settings:override:MIN_VOLUME_FLOOR_MODE settings:override:triggered_at settings:override:reason\".split();print(asyncio.run(r.delete(*K)))"'
railway ssh --service stockbot "$CMD"
# 응답이 6이면 6키 모두 DEL 성공
```

### 5.4 Railway 자동 배포 미반영 의심 시

```bash
# 백엔드 빌드 시각 확인 (Railway 대시보드 또는 CLI)
railway status --service stockbot
railway logs --service stockbot | head -50

# health endpoint에서 응답 시각 비교
curl -i https://api.stockbot.choiji.kr/api/v1/health
```

---

## 6. 의미있는 데이터 축적 후 다음 액션

### 6.1 내일 신호 ≥ 1건 발생 시

A안 입증. 다음 단계:

| 우선순위 | 작업 | 비고 |
|---------|------|------|
| 1 | Sprint 3 dry_run 관찰 게이트 재개 — 2거래일 연속 ≥ 1건 충족 확인 | 추가 관찰일 필요 |
| 2 | stage-heatmap 분포 정상화 확인 (단일 stage ≤ 50%) | 임계 추가 완화 보류 |
| 3 | Phase 8.6 Sprint 4 walk-forward 백테스트 (`/admin/backtest`) — A안 임계로 과거 60일 신호 분포 | 임계 grid search |
| 4 | dry_run → LIVE 전환 검토 | Sprint 4 G-Bt1~3 게이트 통과 후만 |

### 6.2 내일도 신호 0건이면

본질이 1차 풀 진입 또는 2차 게이트가 아닐 가능성:
- momentum_breakout 자체의 게이트 (volume_threshold 1.8, prev_close_time_guard, breakout_pct 계산) 코드 검토
- 또는 실시간 데이터 수집 파이프라인 결함 (KIS WebSocket subscription 동기화)
- 또는 Phase 9급 전략 자체 재설계 검토

### 6.3 R1 3일 트리거 발동 시

- 시스템 자가치유 unset 분기 검증 기회로 활용 (수동 clear 금지)
- 다음날(05-15) 신호 ≥ 1건이면 R1 자동 해제 확인 — PR #228 효과 입증

---

## 7. 참고

- **오늘 결과 문서**: `docs/phase/phase8.6/sprint4/2026-05-13-monitoring-result.md` (PR #235)
- **본질 진단 핵심**: 014680 한솔케미칼 (+12%) trace
- **A안 코드 변경**:
  - `backend/modules/screening/filters.py:14` `change_rate_max` 7 → 30
  - `backend/modules/screening/filters.py:23` `trade_strength_min` 100 → 80
- **B hotfix 환경변수**: `MIN_VOLUME_FLOOR_HARD=0.25` (Railway)
- **R3 차단 키 manual clear 1줄 명령**: §5.3
- **인증 토큰**: `reference_admin_jwt_token.md` (만료 2026-05-14 15:45 KST)
- **개장까지 남은 시간 계산용 cron 5개** (내일 아침 재등록 필요):
  - `30 9 14 5 *` 1차 점검
  - `0 12 14 5 *` 2차 점검
  - `30 14 14 5 *` 3차 점검
  - `10 16 14 5 *` 4차 점검
  - `30 16 14 5 *` 종합 보고
