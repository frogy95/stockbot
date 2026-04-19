# 한국 거래소 캘린더

`core/trading_calendar.py` 구현. 장 운영일 여부와 장 시간을 관리.

## 장 시간

| 구분 | 시각 (KST) |
|------|-----------|
| 정규 거래 시작 | 09:00 |
| 정규 거래 종료 | 15:30 |
| 시간외 거래 | 15:40~18:00 |
| 타임존 | Asia/Seoul (UTC+9) |

StockBot은 정규 거래 시간(09:00~15:30)만 대상.

## 거래일 판별

- 한국 공휴일 제외
- 주말 제외
- 임시 휴장일 (KRX 공시) 별도 처리

```python
def is_trading_day(date: date) -> bool:
    # 주말 체크
    if date.weekday() >= 5:
        return False
    # 공휴일 체크
    if date in KRX_HOLIDAYS:
        return False
    return True
```

## [[data-collection-flow|스케줄러]] 연동

APScheduler 크론 작업 실행 전 거래일 체크:
```python
@scheduler.scheduled_job("cron", hour=8, minute=0)
async def morning_collection():
    if not is_trading_day(today()):
        return  # 비거래일 → 스킵
    await collect_all_stocks()
```

## 연간 휴장일

KRX(한국거래소)가 공시하는 연간 휴장일 목록 기반:
- 설날/추석 연휴
- 어린이날, 현충일 등 법정 공휴일
- 대통령 선거일 등 임시 공휴일

## 시장 진행도 계산

[[momentum-breakout-strategy]]에서 사용:

```python
def calc_market_progress(now_kst: datetime) -> float:
    """장중 시간 진행도 (0.15 ~ 1.0)"""
    # 09:00 이전: 0.15 (장 초반 보정)
    # 15:30 이후: 1.0
    # 장중: elapsed_minutes / 390
```

장 초반(09:00~약 09:35) 거래량이 자연히 적으므로 하한 0.15로 보정.

## 장 마감 처리

[[position-management|장 마감 청산]] 스케줄:
```python
# 15:20 (장 마감 10분 전) 전량 청산 시작
@scheduler.scheduled_job("cron", hour=15, minute=20)
async def eod_liquidation():
    if is_trading_day(today()):
        await liquidator.liquidate_all()
```
