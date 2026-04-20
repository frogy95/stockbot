# Phase 8 Sprint 1 — 배포 후 모니터링 가이드

장중 OHLC 파싱 + 갭 분기 수정 배포 후 수동 검증 체크리스트.

---

## 배포 직후 (장중 09:05~09:30)

```bash
# 백엔드 로그에서 parse_execution 경고 없는지 확인
railway logs --service backend | grep -i "체결 데이터"

# Redis에서 OHLC 필드 존재 확인 (삼성전자 샘플)
# Railway 내부 Redis CLI 또는 로컬 Docker:
docker compose exec backend python -c "
import asyncio, json
from core.redis import get_redis
async def check():
    r = await get_redis()
    raw = await r.get('realtime:005930:execution')
    if raw:
        d = json.loads(raw)
        print('open_price:', d.get('open_price'))
        print('high:', d.get('high'))
        print('low:', d.get('low'))
    else:
        print('데이터 없음')
asyncio.run(check())
"
```

**기대값**: `open_price`, `high`, `low` 키가 모두 0이 아닌 정수로 존재.

---

## 1~2시간 모니터링 (김단타 권고)

KIS WS 메시지의 실제 필드 인덱스(7/8/9)가 STCK_OPRC/STCK_HGPR/STCK_LWPR와 일치하는지 샘플 대조:

| 종목 | Redis open_price | KIS HTS 시가 | 일치여부 |
|------|-----------------|-------------|---------|
| 005930 삼성전자 | — | — | — |
| 000660 SK하이닉스 | — | — | — |
| 035720 카카오 | — | — | — |
| 035420 NAVER | — | — | — |
| 105560 KB금융 | — | — | — |

> **인덱스 오매핑 시**: 즉시 롤백 후 KIS 공식 문서 재확인.

---

## 신호 관찰 (2거래일)

```sql
-- trade_signals 테이블에서 momentum_breakout 신호 확인
SELECT strategy_name, signal_type, stock_code, confidence, created_at
FROM trade_signals
WHERE strategy_name = 'momentum_breakout'
  AND created_at > now() - interval '2 days'
ORDER BY created_at DESC
LIMIT 20;
```

**기대**: 1건 이상 `pending` 신호 존재.
**신호 미생성 시**: Sprint 2(다층 진입 조건) 착수 전 원인 재진단 필요.

---

## Redis JSON 스키마 비교

### 이전 구조 (Phase 7 이하)
```json
{
  "stock_code": "005930",
  "time": "100000",
  "price": 70000,
  "volume": 1000,
  "acml_volume": 5000000,
  "change_rate": 1.45,
  "trade_strength": 125.0,
  "sell_or_buy": "1"
}
```

### 이후 구조 (Phase 8 Sprint 1~)
```json
{
  "stock_code": "005930",
  "time": "100000",
  "price": 70000,
  "volume": 1000,
  "acml_volume": 5000000,
  "change_rate": 1.45,
  "trade_strength": 125.0,
  "sell_or_buy": "1",
  "open_price": 69500,
  "high": 70200,
  "low": 69000
}
```

> 구버전 Redis 캐시(OHLC 없음)는 `open_price=0` 폴백으로 자동 처리됨 — 하위 호환.

---

## 롤백 조건

- OHLC 파싱 경고 비율 10%+ (parse_execution 경고가 전체 메시지의 10% 초과)
- Redis `open_price`가 KIS HTS 시가와 10%+ 차이 (인덱스 오매핑)
- `momentum_breakout` 신호가 3거래일 연속 0건 (신호 생성 회로 자체 문제)

```bash
# 롤백 명령
git revert HEAD~5..HEAD  # task1~5 커밋 되돌리기
```
