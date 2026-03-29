# Phase 0.5 탐색 스크립트

외부 API 5종(한투, 텔레그램, 네이버, DART, 공공데이터포털)을 검증하는 탐색용 스크립트.
Phase 1에서 프로덕션 품질로 재작성 예정.

## 실행 방법

```bash
# 1. 의존성 설치
pip install -r exploration/requirements.txt

# 2. .env 설정 확인 (프로젝트 루트)
cat .env  # API 키가 설정되어 있어야 함

# 3. 스크립트 실행 (프로젝트 루트에서)
python exploration/kis/01_auth.py
python exploration/kis/02_stock_price.py
# ...
```

## 실행 순서

1. `kis/01_auth.py` — OAuth 토큰 발급 (다른 한투 스크립트의 전제)
2. `kis/02_stock_price.py` ~ `kis/09_misc.py` — 한투 REST API
3. `kis/06_websocket.py` — 한투 웹소켓 (**장중 09:00~15:30 필수**)
4. `telegram/01_send_message.py` ~ `telegram/04_latency.py`
5. `naver/01_news_search.py` ~ `naver/03_rate_limit.py`
6. `dart/01_financial.py` ~ `dart/03_realtime_check.py`
7. `data_go_kr/01_market_cap.py` ~ `data_go_kr/03_rate_limit.py`

## 주의사항

- `.env` 파일이 프로젝트 루트에 있어야 합니다
- **모의거래만 사용** (실전거래 API 호출 금지)
- 한투 웹소켓 테스트는 **장중(09:00~15:30)**에 실행해야 정확한 결과를 얻을 수 있습니다
- 테스트 종목: 삼성전자(005930), 에코프로비엠(247540), KODEX 200(069500)
