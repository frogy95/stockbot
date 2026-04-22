# Phase 8 Sprint 2 — 배포 후 수동 검증 체크리스트

> sprint2.md의 "최종 검증 계획" 중 배포 후 실증(로그/Redis/텔레그램)이 필요한 항목을 모아둔다.
> sprint-review가 자동 검증을 끝낸 후, 운영 환경(프로덕션/스테이징)에서 실제로 동작하는지 확인하는 절차.

## 1. Redis 키 검증

```bash
# 백엔드 Docker / Railway에서 실행
redis-cli KEYS 'risk:daily_trade_count'
redis-cli KEYS 'scheduler:daily_report:sent:*'
redis-cli KEYS 'ws:reconnect:notified'
redis-cli KEYS 'engine:block:dedup:*'
```

- ⬜ `risk:daily_trade_count` — 매수 체결 1회 이상 발생 후 존재 (TTL > 0)
- ⬜ `scheduler:daily_report:sent:YYYYMMDD` — 15:30 이후 1회만 생성 (TTL 86400)
- ⬜ `ws:reconnect:notified` — WS 재연결 발생 시 60초간 존재
- ⬜ `engine:block:dedup:{code}:{reason}` — risk_blocked/pipeline_unhealthy 차단 시 5분간 존재

## 2. seed_settings 신규 키

```bash
docker compose exec backend python -m scripts.seed_settings
# → "33개 설정 시드 완료" (이전 32 + daily_max_trade_count)

# 또는 DB 직접 조회
SELECT key, value FROM settings WHERE key = 'daily_max_trade_count';
```

- ⬜ `daily_max_trade_count` row 존재, value='10'

## 3. 다층 tier 관찰 (2거래일 연속)

```sql
SELECT reason->>'breakout_tier' AS tier, COUNT(*)
FROM trade_signals
WHERE created_at >= CURRENT_DATE - INTERVAL '2 days'
GROUP BY 1;
```

- ⬜ gap_open / prev_high / prev_close 3개 tier 모두 1건 이상 관찰 목표

## 4. 13:00 가드 (prev_close tier 비활성)

- ⬜ Railway 백엔드 로그에 `prev_close_time_guard` stage 로그 1건 이상
  ```bash
  railway logs --service backend | grep prev_close_time_guard
  ```

## 5. 일일 거래 한도 (10건/일)

- ⬜ 당일 매수 체결 10건 도달 시 `engine_block ... reason=risk_blocked` + "일일 거래 횟수" 사유
- ⬜ Sprint 3 LIVE 초기 진입 전에 Railway에 `DAILY_MAX_TRADE_COUNT_OVERRIDE=3` 환경변수 추가
  - Sprint 3 E2E Paper 1사이클 통과 후 이 환경변수 제거 → 10건/일 복귀

## 6. 동시호가 가드 (15:10~15:30)

- ⬜ 2거래일 연속 15:10~15:30 구간에서 `_reconnect_ws` 미호출 확인
- ⬜ 동 구간 WS 재연결 텔레그램 알림 0건

## 7. 재연결 알림 dedup

- ⬜ 장중 WS 재연결 발생 시 텔레그램 `[자동 복구] WS 재연결 완료 ...` 알림 1통 (2통 아님)
- ⬜ 60초 이내 재연결 재시도가 발생해도 추가 알림 없음

## 8. 일일 리포트 dedup

- ⬜ 15:30 이후 `일일 마감 리포트` 텔레그램 1건만 수신
- ⬜ 다음 날 정상 발송 확인

## 9. 프론트 리스크 리셋 버튼

- ⬜ 대시보드 접속 → "리스크 상태" 카드 우상단에 `일일 리스크 카운터 리셋` 버튼 노출
- ⬜ 버튼 클릭 → 다이얼로그 오픈 → LIVE/PAPER 배지 정상
- ⬜ "위험을 이해했습니다" 체크 없이 "리셋 실행" 버튼 비활성
- ⬜ 체크 후 실행 → 토스트/완료 메시지 → `redis-cli GET risk:consecutive_loss_count` 결과 null

## 10. 차단 사유 구조화 로그

- ⬜ 일일 한도 초과/리스크 차단/파이프라인 미정상 등 6개 지점에서 `engine_block stock=... reason=...` 로그 기록
- ⬜ risk_blocked / pipeline_unhealthy만 텔레그램 `risk_warning` 알림 발송
- ⬜ 동일 (stock_code, reason) 조합 5분 내 재알림 없음

---

## 다음 Sprint 착수 전 필수

- Sprint 3 (E2E Paper 1사이클 + LIVE 전환 게이트) 시작 전:
  1. 본 문서 모든 ⬜ 항목을 ✅로 전환
  2. `DAILY_MAX_TRADE_COUNT_OVERRIDE=3` 환경변수 Railway 프로덕션에 반영
  3. breakout_tier 3종 모두 실거래 관찰 로그 확인 (최소 2거래일)
