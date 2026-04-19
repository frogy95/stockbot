# 데이터 수집 흐름

StockBot의 데이터 수집은 장전/장중/장후 3단계로 구성된다. 자세한 구현은 `backend/modules/collector/` 참조.

## 전체 흐름

```
장전 (08:00)
  공공데이터포털 → 전 종목 2,880개 일괄 수집 (6회 호출 / 3.7초)
  DART → 재무 데이터 (분기 갱신 시)
  네이버 → 뉴스 센티멘트 배치
  → DB 저장 → 1차 스크리닝 → 후보 종목 수십 개 선정

장중 (09:00~15:30)
  한투 REST → 후보 종목 현재가/호가/분봉
  한투 WebSocket → 실시간 체결 스트림
  → Redis 저장 → 2차 스크리닝 → 매매 신호 → 주문 실행

장후 (15:30~)
  한투 REST → 체결 내역/잔고 정산
  → DB 저장 → 일일 리포트 → 텔레그램 발송
```

상세: [[kis-api]], [[websocket-management]], [[public-data-sources]]

## 장전 수집 (08:00)

### 공공데이터포털 일괄 수집
- 금융위원회_주식시세정보 API 사용
- 전 종목(약 2,880개) 종가/시가/고가/저가/거래량/시총/상장주식수
- 6회 API 호출로 일괄 처리 (페이지당 500개 기준)
- ETF는 별도 처리 필요 (공공데이터 API 미포함)

### DART 재무 데이터
- 분기 갱신 시에만 수집 (일상적 수집 아님)
- 매출/영업이익 등 기초 재무 지표
- [[screening-factors|스크리닝 팩터]]의 보조 소스

### 네이버 뉴스 센티멘트
- 일 1~2회 배치 수집
- 보조 팩터로만 활용 (속보 대형주만 유효, 1시간+ 지연)

## 장중 수집 (09:00~15:30)

### 실시간 시세 (REST)
- 1차 스크리닝 통과 종목만 대상
- 현재가, 호가(10단계), 분봉 데이터
- [[redis-usage|Redis]]에 최신 상태 캐시

### 실시간 체결 (WebSocket)
- KIS WebSocket으로 체결 스트림 수신
- 체결강도 실시간 계산 → Redis 저장
- 연결 관리: [[websocket-management]]

### 5분봉 집계
- `volume_aggregator.py`가 체결 틱 → 5분봉 변환
- Phase 7.1 이후 가속도 지표 계산에 활용

## 장후 처리 (15:30~)

- 보유 포지션 일괄 청산 (`eod_liquidator.py`)
- 체결 내역/잔고 REST API로 정산
- `analyzer` 모듈이 일일 성과 기록
- 텔레그램으로 일일 리포트 발송 — [[telegram-integration]]

## 수집 스케줄 구현

`collector/scheduler.py`에서 APScheduler로 관리:
```python
# 예시 크론 표현식
장전_수집: "0 8 * * 1-5"   # 월~금 08:00 KST
장중_수집: "0 9 * * 1-5"   # 월~금 09:00 KST (WebSocket 연결)
장후_정산: "30 15 * * 1-5" # 월~금 15:30 KST
```

스케줄 실행 여부는 [[trading-calendar|거래일 캘린더]]로 검증.

---

## 상세 다이어그램

> Phase 0.5 API 검증 결과 기반. 2단계 수집 전략(장전 일괄 + 장중 실시간).

### 전체 데이터 흐름

```mermaid
flowchart TB
    subgraph 외부API["외부 API"]
        DATA_GO["공공데이터포털<br/>금융위원회_주식시세정보"]
        DART["Open Dart API"]
        NAVER["네이버 검색 API"]
        KIS_REST["한투 REST API"]
        KIS_WS["한투 WebSocket"]
        TELEGRAM["Telegram Bot API"]
    end

    subgraph 장전["장전 (08:00)"]
        direction TB
        BULK["전 종목 일괄 수집<br/>2,880종목 / 6회 호출 / 3.7초"]
        FIN["재무 데이터 수집<br/>분기 갱신 시"]
        SENT["뉴스 센티멘트 배치<br/>일 1~2회"]
        SCR1["1차 스크리닝<br/>DB 기반 정적 필터"]
    end

    subgraph 장중["장중 (09:00~15:30)"]
        direction TB
        RT["실시간 시세/호가<br/>후보 종목만"]
        CS["체결강도 계산<br/>체결 데이터 누적"]
        SCR2["2차 스크리닝<br/>실시간 동적 필터"]
        SIG["매매 신호 생성<br/>신뢰도 + 근거"]
        APPROVE{"승인 방식"}
        ORDER["주문 실행"]
        POS["포지션 관리"]
    end

    subgraph 장후["장후 (15:30~)"]
        SETTLE["체결 내역/잔고 정산"]
        REPORT["일일 리포트"]
    end

    subgraph 저장소["저장소"]
        DB[(PostgreSQL)]
        REDIS[(Redis)]
    end

    %% 장전 흐름
    DATA_GO -->|종가/거래량/시총/상장주식수| BULK
    DART -->|매출/영업이익| FIN
    NAVER -->|뉴스 센티멘트| SENT
    BULK --> DB
    FIN --> DB
    SENT --> DB
    DB --> SCR1
    SCR1 -->|후보 종목 수십 개| RT

    %% 장중 흐름
    KIS_REST -->|현재가/호가/분봉| RT
    KIS_WS -->|실시간 체결| CS
    RT --> REDIS
    CS --> REDIS
    REDIS --> SCR2
    SCR2 --> SIG
    SIG --> APPROVE
    APPROVE -->|반자동| TELEGRAM
    TELEGRAM -->|승인/거부| ORDER
    APPROVE -->|완전자동| ORDER
    KIS_REST <-->|주문/체결| ORDER
    ORDER --> POS
    POS --> DB

    %% 장후 흐름
    KIS_REST --> SETTLE
    SETTLE --> DB
    DB --> REPORT
    REPORT --> TELEGRAM

    %% 스타일
    classDef api fill:#4a90d9,stroke:#2c5f8a,color:#fff
    classDef storage fill:#e8a838,stroke:#b07d1e,color:#fff
    classDef process fill:#50b050,stroke:#2d7a2d,color:#fff
    classDef decision fill:#d94a4a,stroke:#8a2c2c,color:#fff

    class DATA_GO,DART,NAVER,KIS_REST,KIS_WS,TELEGRAM api
    class DB,REDIS storage
    class BULK,FIN,SENT,SCR1,RT,CS,SCR2,SIG,ORDER,POS,SETTLE,REPORT process
    class APPROVE decision
```

### API별 데이터 흐름 상세

```mermaid
flowchart LR
    subgraph 공공데이터포털["공공데이터포털 (장전 1회)"]
        DG_IN["basDt 필터<br/>numOfRows=500<br/>6페이지"]
        DG_OUT["종가 clpr<br/>시가 mkp<br/>고가 hipr<br/>저가 lopr<br/>거래량 trqu<br/>시총 mrktTotAmt<br/>상장주식수 lstgStCnt<br/>시장구분 mrktCtg"]
    end

    subgraph 한투REST["한투 REST (장중 실시간)"]
        KR_PRICE["현재가 조회<br/>tr_id: FHKST01010100<br/>80개 필드"]
        KR_ORDER["호가 조회<br/>tr_id: FHKST01010200<br/>10단계 매수/매도"]
        KR_CHART["분봉 조회<br/>tr_id: FHKST03010200"]
        KR_TRADE["주문 실행<br/>tr_id: VTTC0802U(모의)"]
    end

    subgraph 한투WS["한투 WebSocket (장중 실시간)"]
        WS_TICK["실시간 체결<br/>tr_id: H0STCNT0<br/>체결가/체결량/시간"]
    end

    subgraph DART["DART (분기)"]
        DART_FIN["재무정보<br/>fnlttSinglAcntAll<br/>매출/영업이익/순이익"]
        DART_MAP["corp_code 매핑<br/>corpCode.xml<br/>종목코드→corp_code"]
    end

    subgraph 처리["내부 처리"]
        CALC["체결강도 계산<br/>매수체결 누적 ÷ 매도체결 누적 × 100"]
        FILTER1["1차 스크리닝<br/>거래량/시총/등락률/변동성"]
        FILTER2["2차 스크리닝<br/>호가잔량/체결강도/분봉패턴"]
    end

    DG_IN --> DG_OUT --> FILTER1
    DART_MAP --> DART_FIN --> FILTER1
    FILTER1 -->|후보 종목| KR_PRICE
    FILTER1 -->|후보 종목| KR_ORDER
    FILTER1 -->|후보 종목| WS_TICK
    KR_PRICE --> FILTER2
    KR_ORDER --> FILTER2
    WS_TICK --> CALC --> FILTER2
    KR_CHART --> FILTER2
    FILTER2 -->|매매 신호| KR_TRADE
```

### ETF 데이터 흐름 (예외 처리)

```mermaid
flowchart LR
    subgraph ETF예외["ETF 별도 처리"]
        ETF_LIST["ETF 종목 목록<br/>(사전 정의)"]
        KIS_ETF["한투 REST<br/>개별 조회"]
        ETF_SCORE["ETF 전용 스코어링<br/>재무 팩터 제외<br/>호가단위 5원 고정"]
    end

    NOTE["공공데이터포털: ETF 미포함<br/>DART: ETF 재무 미제공"]

    NOTE -.->|대안| ETF_LIST
    ETF_LIST --> KIS_ETF
    KIS_ETF -->|현재가/거래량| ETF_SCORE

    classDef note fill:#f5f5f5,stroke:#999,color:#666
    class NOTE note
```

### Rate Limit 관리

```mermaid
flowchart TB
    subgraph 한도["API별 한도 및 실측"]
        RL1["공공데이터포털<br/>일 1,000회<br/>사용: 6회/일 ✅"]
        RL2["한투 REST (모의)<br/>공식 초당 1건<br/>실측: 1.5초 간격 권장"]
        RL3["한투 REST (실전)<br/>공식 초당 20건<br/>설계: 70% = 14건/초"]
        RL4["한투 토큰 발급<br/>1분당 1회<br/>Redis 캐싱 필수"]
        RL5["DART<br/>일 10,000회<br/>사용: 수십 회/일"]
        RL6["네이버<br/>일 25,000회<br/>사용: 수십 회/일"]
        RL7["텔레그램<br/>초당 30건<br/>실측 지연: 0.5초"]
    end

    subgraph 스로틀링["적응형 스로틀링 전략"]
        BASE["기본 간격<br/>모의: 1.5초<br/>실전: 0.07초"]
        ERR["에러 감지<br/>Rate Limit 응답"]
        BACKOFF["지수 백오프<br/>간격 × 2"]
        RECOVER["점진 복구<br/>성공 시 간격 축소"]
    end

    BASE --> ERR
    ERR -->|초과| BACKOFF
    BACKOFF --> ERR
    ERR -->|성공| RECOVER
    RECOVER --> BASE
```
