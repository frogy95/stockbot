# Sprint 1: 외부 API 5종 탐색/검증 (Phase 0.5)

**Goal:** 한투/텔레그램/네이버/DART/공공데이터포털 API를 실제 호출하여 응답 구조, Rate Limit, 에러 시나리오를 검증하고 Go/No-Go 판단을 내린다.

**Architecture:** exploration/ 디렉토리에 API별 독립 Python 스크립트를 생성하여 순차 검증한다. 각 스크립트는 .env에서 키를 로드하고, 응답을 콘솔에 출력하며, 검증 결과를 api-test-report.md에 기록한다. 프로덕션 품질이 아닌 탐색용 코드이며 Phase 1에서 재작성한다.

**Tech Stack:** Python 3.12, requests, websockets, python-telegram-bot, python-dotenv

**Sprint 기간:** 2026-03-29 ~ 2026-03-29
**상태:** ✅ 완료 (2026-03-29)
**이전 스프린트:** Sprint 0 (사용자 수동 — API 키 발급 완료)
**브랜치명:** `phase0.5-sprint1`
**PR:** https://github.com/frogy95/stockbot/pull/1

---

## 제외 범위

- 프로덕션 품질 코드 (에러 핸들링, 로깅, 타입 힌트 등 최소화)
- Docker 컨테이너 내 실행 (로컬 Python 직접 실행)
- 테스트 코드 (pytest 없음 — 스크립트 실행 결과로 검증)
- 백엔드/프론트엔드 코드 (exploration/ 디렉토리만 사용)
- 실전거래 API 호출 (모의거래만 사용)
- Jupyter Notebook (Python 스크립트 기본, 필요시 별도 생성)

---

## 실행 플랜

의존성: Task 1(공통 설정)이 선행. Task 2~6은 독립적이나, Phase 문서의 검증 순서(한투 > 텔레그램 > 네이버 > DART > 공공데이터포털)를 따른다.

### Phase 1 (순차 — 기반 설정)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 탐색 환경 설정 (디렉토리, requirements.txt, config.py) | 환경 | — |

### Phase 2 (순차 — 핵심 API 검증, 검증 순서 준수)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 2 | 한투 API REST 검증 (토큰, 시세, 주문, Rate Limit, 에러) | 백엔드 | — |
| Task 3 | 한투 API 웹소켓 검증 (실시간 시세, 30분 유지, 지연 측정) | 백엔드 | — |
| Task 4 | 텔레그램 Bot API 검증 (메시지, 버튼, 웹훅, 지연) | 백엔드 | — |
| Task 5 | 네이버 검색 API 검증 (뉴스 검색, 속보 반영, Rate Limit) | 백엔드 | — |

### Phase 3 (병렬 가능 — 보조 API)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 6 | DART API 검증 (재무정보, 공시, 실시간성) | 백엔드 | — |
| Task 7 | 공공데이터포털 API 검증 (시가총액, 갱신 주기, Rate Limit) | 백엔드 | — |

### Phase 4 (순차 — 산출물 정리)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 8 | 검증 결과 종합 보고서 + Go/No-Go 판단 | 문서 | — |

> **Phase 3 병렬 실행**: "Phase 3를 팀으로 실행해줘"라고 요청하면 DART/공공데이터포털을 병렬 검증합니다.

---

### Task 1: 탐색 환경 설정

**Files:**
- Create: `exploration/requirements.txt`
- Create: `exploration/common/__init__.py`
- Create: `exploration/common/config.py`
- Create: `exploration/README.md`
- Modify: `.gitignore` (exploration/ 내 캐시/임시 파일 제외 추가)

**Step 1: exploration 디렉토리 구조 생성**
- `exploration/` 루트 및 하위 디렉토리 생성: `common/`, `kis/`, `telegram/`, `naver/`, `dart/`, `data_go_kr/`
- 각 디렉토리에 `__init__.py` 생성 (빈 파일)

**Step 2: requirements.txt 작성**
- `exploration/requirements.txt` 생성
- 의존성 목록:
  - `requests` — REST API 호출
  - `websockets` — 한투 웹소켓
  - `python-dotenv` — .env 로드
  - `python-telegram-bot` — 텔레그램 봇 API
  - `pycryptodome` — 한투 웹소켓 AES 복호화
- 검증: `pip install -r exploration/requirements.txt`
- 예상: 정상 설치

**Step 3: 공통 설정 모듈 작성**
- `exploration/common/config.py` 생성
- 프로젝트 루트의 `.env` 파일 로드 (python-dotenv)
- 환경변수를 딕셔너리 또는 변수로 노출:
  - `KIS_MOCK_APP_KEY`, `KIS_MOCK_APP_SECRET`, `KIS_MOCK_ACCOUNT_NO`
  - `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`
  - `DART_API_KEY`
  - `DATA_GO_KR_API_KEY`
  - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- 키 누락 시 경고 메시지 출력 (에러가 아닌 경고)

**Step 4: README.md 작성**
- `exploration/README.md` 생성
- 실행 방법: `cd exploration && pip install -r requirements.txt && python kis/01_auth.py`
- 주의사항: .env 파일 필요, 모의거래만 사용, 장중 테스트 필수 항목 안내
- 스크립트 실행 순서 안내

**Step 5: .gitignore 확인/수정**
- `.gitignore`에 `exploration/*.json` (응답 덤프 파일) 추가 — 이미 `.env`는 포함됨

**Step 6: 커밋**
```
git add exploration/ .gitignore
git commit -m "feat(phase0.5-sprint1): 탐색 환경 설정 — 디렉토리 구조, 의존성, 공통 설정"
```

**완료 기준:**
- ✅ `pip install -r exploration/requirements.txt` 성공
- ✅ `python -c "from exploration.common.config import *"` 에러 없음
- ✅ .env 키 로드 확인

> **테스트 종목 (전 Task 공통)**: 모든 API 테스트는 시장 유형별 3종목을 사용한다.
> config.py에 상수로 정의하여 전체 스크립트에서 import.
>
> | 구분 | 종목코드 | 종목명 | 비고 |
> |------|---------|--------|------|
> | KOSPI | 005930 | 삼성전자 | 대형주, 거래량 최다 |
> | KOSDAQ | 247540 | 에코프로비엠 | 중형주, 변동성 |
> | ETF | 069500 | KODEX 200 | ETF, `FID_COND_MRKT_DIV_CODE` 차이 확인 |

---

### Task 2: 한투 API REST 검증

**Files:**
- Create: `exploration/kis/01_auth.py`
- Create: `exploration/kis/02_stock_price.py`
- Create: `exploration/kis/03_orderbook.py`
- Create: `exploration/kis/04_trade_volume.py`
- Create: `exploration/kis/05_order_test.py`
- Create: `exploration/kis/07_rate_limit.py`
- Create: `exploration/kis/08_error_scenarios.py`
- Create: `exploration/kis/09_misc.py`

**Step 1: OAuth 토큰 발급 (01_auth.py)**
- 한투 모의거래 OAuth 토큰 발급 REST API 호출
  - URL: `https://openapivts.koreainvestment.com:29443/oauth2/tokenP`
  - Method: POST
  - Body: `{"grant_type": "client_credentials", "appkey": KIS_MOCK_APP_KEY, "appsecret": KIS_MOCK_APP_SECRET}`
- 응답에서 `access_token`, `token_token_expired` 추출 및 출력
- 토큰을 반환하는 함수로 작성 (다른 스크립트에서 import 가능)
- 검증: `python exploration/kis/01_auth.py`
- 예상: access_token 문자열 출력, 유효기간(약 24시간) 확인

**Step 2: 현재가 조회 (02_stock_price.py)**
- 테스트 종목 3개(KOSPI/KOSDAQ/ETF) 각각 현재가 조회
  - URL: `https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-price`
  - Header: `authorization: Bearer {token}`, `appkey`, `appsecret`, `tr_id: FHKST01010100`
  - KOSPI/KOSDAQ: `FID_COND_MRKT_DIV_CODE=J` / ETF: `FID_COND_MRKT_DIV_CODE=J` (ETF도 J인지 확인, 다르면 기록)
- 출력 항목: 현재가(stck_prpr), 전일대비(prdy_vrss), 거래량(acml_vol), 등락률(prdy_ctrt)
- 3종목 응답 구조 비교: 필드 차이 여부 확인 (특히 ETF)
- 검증: `python exploration/kis/02_stock_price.py`
- 예상: 3종목(삼성전자/에코프로비엠/KODEX200) 현재가 출력

**Step 3: 호가(10단계) 조회 (03_orderbook.py)**
- 테스트 종목 3개 각각 호가 조회
  - URL: `/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn`
  - tr_id: `FHKST01010200`
- 출력: 매수/매도 각 10단계 호가 + 잔량 + 총잔량
- 3종목 호가단위 차이 확인 (KOSPI 대형주 vs KOSDAQ vs ETF)
- 호가 갱신 빈도 확인 (2회 연속 호출 간 변화 여부)
- 검증: `python exploration/kis/03_orderbook.py`
- 예상: 3종목 각각 10단계 매수/매도 호가+잔량 테이블 형식 출력

**Step 4: 체결강도/거래량 조회 (04_trade_volume.py)**
- 체결강도, 전일대비 거래량 비율 조회
  - 체결강도: 현재가 API 응답 내 `seln_cntg_smtn`(매도체결합계), `shnu_cntg_smtn`(매수체결합계) 활용
  - 거래량비율: `acml_vol`(누적거래량), `prdy_vol`(전일거래량) 비교
- 분봉 데이터 조회 (가능한 경우)
  - URL: `/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice`
  - tr_id: `FHKST03010200`
- 검증: `python exploration/kis/04_trade_volume.py`
- 예상: 체결강도 수치, 거래량 비율, 분봉 데이터 출력

**Step 5: 모의 주문 실행/취소 (05_order_test.py)**
- 테스트 종목 3개 각각 시장가 매수 주문 (1주) 실행
  - URL: `/uapi/domestic-stock/v1/trading/order-cash`
  - tr_id: `VTTC0802U` (모의투자 매수)
  - Body: 계좌번호, 종목코드, 주문수량, 주문단가(0=시장가), 주문구분(01=시장가)
- 각 주문번호 확인 후 즉시 취소
  - tr_id: `VTTC0803U` (모의투자 취소)
- 주문 체결 여부 조회
  - URL: `/uapi/domestic-stock/v1/trading/inquire-daily-ccld`
  - tr_id: `VTTC8001R` (모의투자 체결내역)
- KOSPI/KOSDAQ/ETF 간 주문 요청/응답 차이 확인 (tr_id, 파라미터 등)
- 검증: `python exploration/kis/05_order_test.py`
- 예상: 3종목 각각 주문번호 출력 → 취소 확인 → 체결내역 출력

**Step 6: Rate Limit 실측 (07_rate_limit.py)**
- 모의거래 Rate Limit 실측
  - 현재가 API를 연속 호출 (0.5초, 1초, 2초 간격)
  - 초당 1건(공식)과 비교하여 실제 허용치 측정
  - 초과 시 HTTP 상태 코드, 에러 메시지 기록
  - 초과 후 복구까지 대기 시간 측정
- 검증: `python exploration/kis/07_rate_limit.py`
- 예상: 초당 허용 건수, 초과 시 응답 코드(예: 429), 복구 시간 출력

**Step 7: 에러 시나리오 5가지 검증 (08_error_scenarios.py)**
- 시나리오 1: 잘못된 종목 코드(999999)로 현재가 조회 → 응답 코드, 에러 메시지 구조
- 시나리오 2: 만료/잘못된 토큰으로 API 호출 → 응답 코드, 자동 갱신 트리거 가능 여부
- 시나리오 3: Rate Limit 초과 시 응답 → (Step 6에서 측정한 값 활용)
- 시나리오 4: 장 외 시간 시세 조회 → 응답 차이 기록 (장중/장외 비교)
- 시나리오 5: 장 외 시간 주문 → 응답 차이 기록
- 각 시나리오별 요청/응답 JSON 전체를 출력
- 검증: `python exploration/kis/08_error_scenarios.py`
- 예상: 5개 시나리오 각각의 응답 코드 + 에러 메시지 출력

**Step 8: 기타 검증 (09_misc.py)**
- hashkey 발급 및 활용 확인 (주문 시 필요한 해시키)
  - URL: `/uapi/hashkey`
  - POST Body로 주문 데이터 전송 → hash 값 반환
- tr_id 매핑 확인: 모의(VTTC) vs 실전(TTTC) 접두사 차이
- 호가단위 확인: 가격대별 호가 단위 (한투 API 응답 or 수동 테이블)
- 장상태 확인: 현재 장 상태(장전, 장중, 장후, 휴일) 조회 가능 여부
- 웹소켓 암호화 키 발급: `/oauth2/Approval` 엔드포인트에서 approval_key 발급
- 응답 인코딩: UTF-8 vs EUC-KR 확인 (한글 종목명)
- 검증: `python exploration/kis/09_misc.py`
- 예상: 각 항목별 결과 출력

**Step 9: 커밋**
```
git add exploration/kis/
git commit -m "feat(phase0.5-sprint1): 한투 API REST 검증 — 토큰/시세/주문/Rate Limit/에러 시나리오"
```

**완료 기준:**
- ✅ OAuth 토큰 발급 성공
- ✅ 현재가 + 호가(10단계) + 체결강도/거래량 조회 성공
- ⬜ 모의 주문 실행 → 취소 왕복 성공 (주말 비영업일 — 평일 재테스트 필요)
- ✅ Rate Limit 실측값 기록 (초당 허용, 초과 응답, 복구 시간)
- ✅ 에러 시나리오 5가지 응답 구조 기록
- ✅ hashkey, tr_id, 호가단위, 장상태, WS암호화키, 인코딩 확인

---

### Task 3: 한투 API 웹소켓 검증

**Files:**
- Create: `exploration/kis/06_websocket.py`

> **주의: 장중(09:00~15:30) 테스트 필수.** 장외 시간에는 실시간 데이터가 수신되지 않을 수 있음. 시초가(09:00~09:30), 장마감(15:20~15:30) 시점 포함하여 테스트.

**Step 1: 웹소켓 기본 연결 + 실시간 시세 수신**
- Task 2의 09_misc.py에서 발급한 approval_key 활용
- 웹소켓 URL: `ws://ops.koreainvestment.com:21000/tryitout/H0STCNT0` (모의)
  - 또는 `ws://ops.koreainvestment.com:31000` (실전 — 사용하지 않음)
- 테스트 종목 3개(KOSPI/KOSDAQ/ETF) 실시간 체결가 구독
  - 구독 메시지 예: `{"header":{"approval_key":"...", "custtype":"P", "tr_type":"1", "content-type":"utf-8"}, "body":{"input":{"tr_id":"H0STCNT0", "tr_key":"005930"}}}`
  - 3종목 동시 구독하여 시장 유형별 데이터 수신 차이 확인
- 수신 데이터 파싱 (AES-256-CBC 암호화 여부 확인 — pycryptodome 활용)
- 수신 데이터 필드: 체결가, 체결량, 체결시간, 전일대비 등

**Step 2: 30분 연결 유지 테스트**
- 연결 후 30분간 데이터 수신 유지
- 매 1분마다 수신 건수, 최근 체결가, 지연 시간 출력
- 지연 측정: 체결 시간(API 제공) vs 로컬 수신 시간 차이
- 30분 동안의 통계: 총 수신 건수, 평균/최대 지연, 끊김 횟수

**Step 3: 끊김 재연결 테스트**
- 의도적으로 연결을 끊고 재연결 시도
- 재연결 후 구독 복원 필요 여부 확인 (자동 복원 vs 재구독 필요)
- 재연결까지 소요 시간 측정

**Step 4: 시초가/장마감 시점 테스트 (장중 필수)**
- 09:00~09:30: 데이터 폭주 시 지연 변화 측정
- 15:20~15:30: 장마감 시점 동작 확인 (데이터 중단 시점, 마지막 데이터)
- 이 Step은 장중에만 실행 가능 — 별도 시간 확보 필요

**Step 5: 커밋**
```
git add exploration/kis/06_websocket.py
git commit -m "feat(phase0.5-sprint1): 한투 웹소켓 검증 — 30분 유지/지연 측정/재연결"
```

**완료 기준:**
- ✅ 웹소켓 연결 + 실시간 체결가 수신 성공
- ⬜ 30분 연속 수신 완료 (장중 필요 — 평일 재테스트 필요)
- ✅ 데이터 지연 < 1초 확인 (평균/최대)
- ✅ 끊김 후 재연결 + 구독 복원 방법 확인 (재연결 성공)
- ✅ AES 복호화 동작 확인 (암호화 적용 시)
- ⬜ (장중) 시초가/장마감 시점 지연 측정 (장중 필요)

---

### Task 4: 텔레그램 Bot API 검증

**Files:**
- Create: `exploration/telegram/01_send_message.py`
- Create: `exploration/telegram/02_inline_button.py`
- Create: `exploration/telegram/03_webhook.py`
- Create: `exploration/telegram/04_latency.py`

**Step 1: 메시지 발송 (01_send_message.py)**
- python-telegram-bot 라이브러리 사용
- 텍스트 메시지 발송: "StockBot 테스트 메시지"
- 마크다운 V2 형식 메시지 발송:
  ```
  *삼성전자 매수 신호*
  종목: 005930
  현재가: 72,000원
  신뢰도: 0.85
  근거: 거래량 급등 + 호가 우세
  ```
- HTML 형식 메시지도 테스트
- 검증: `python exploration/telegram/01_send_message.py`
- 예상: 텔레그램 앱에서 메시지 수신 확인

**Step 2: 인라인 버튼 (02_inline_button.py)**
- 매매 승인/거부 인라인 키보드 버튼 메시지 발송
  - 버튼: [승인] [거부] [보류]
  - 콜백 데이터: `approve_001`, `reject_001`, `hold_001`
- 콜백 수신 대기 (폴링 모드로 10초간)
  - 버튼 클릭 시 콜백 데이터 출력
  - 메시지 수정 (버튼 제거 + "승인됨" 텍스트)
- 검증: `python exploration/telegram/02_inline_button.py`
- 예상: 버튼 표시, 클릭 시 콜백 수신 + 메시지 업데이트

**Step 3: 웹훅 수신 (03_webhook.py)**
- ngrok 또는 Cloudflare Tunnel로 로컬 서버 노출
  - 사전 조건: `ngrok http 5000` 실행 중
- Flask/http.server로 간단한 웹훅 수신 서버 (포트 5000)
- 텔레그램 setWebhook API 호출하여 웹훅 URL 등록
- 메시지/콜백 수신 확인
- 테스트 후 deleteWebhook으로 정리
- 검증: `python exploration/telegram/03_webhook.py` (별도 터미널에서 ngrok 실행 필요)
- 예상: 웹훅으로 메시지/콜백 수신, JSON 페이로드 출력

**Step 4: 응답 지연 측정 (04_latency.py)**
- 메시지 발송 시각 ~ API 응답 시각 간 지연 측정 (10회)
- 평균, 최소, 최대 지연 출력
- 목표: < 1초, 허용: < 3초
- 검증: `python exploration/telegram/04_latency.py`
- 예상: 평균 지연 수백 ms 수준

**Step 5: 커밋**
```
git add exploration/telegram/
git commit -m "feat(phase0.5-sprint1): 텔레그램 Bot API 검증 — 메시지/버튼/웹훅/지연 측정"
```

**완료 기준:**
- ✅ 텍스트 + 마크다운 메시지 발송 성공
- ✅ 인라인 버튼 표시 + 콜백 수신 성공
- ✅ 웹훅 수신 성공 (ngrok 경유)
- ✅ 응답 지연 < 3초 확인 (실측 0.49초)

---

### Task 5: 네이버 검색 API 검증

**Files:**
- Create: `exploration/naver/01_news_search.py`
- Create: `exploration/naver/02_freshness.py`
- Create: `exploration/naver/03_rate_limit.py`

**Step 1: 뉴스 검색 (01_news_search.py)**
- 네이버 검색 API (뉴스)
  - URL: `https://openapi.naver.com/v1/search/news.json`
  - Header: `X-Naver-Client-Id`, `X-Naver-Client-Secret`
  - Query: `query=삼성전자`, `display=10`, `sort=date`
- 테스트 종목 3개 + 추가 종목으로 검색: "삼성전자", "에코프로비엠", "KODEX 200", "카카오", "NAVER"
- 종목코드 검색: "005930", "247540" — 코드 vs 이름 관련성 비교
- 출력: 제목, 링크, 발행일, 설명
- 관련성 평가: 종목과 직접 관련된 뉴스 비율 (10건 중 관련 건수)
- 검증: `python exploration/naver/01_news_search.py`
- 예상: 뉴스 10건 제목/링크/날짜 출력

**Step 2: 속보 반영 속도 측정 (02_freshness.py)**
- 최신 뉴스의 발행 시간과 API 검색 노출 시간 비교
  - `sort=date`로 최신순 정렬
  - 가장 최근 뉴스의 `pubDate`와 현재 시간 차이 출력
- 다양한 검색어로 최신 뉴스 시간 차이 측정 (5개 종목)
- Go/No-Go 기준: 속보 반영 1시간 이내면 Go
- 검증: `python exploration/naver/02_freshness.py`
- 예상: 최신 뉴스 ~ 현재 시간 차이 출력

**Step 3: Rate Limit 실측 (03_rate_limit.py)**
- 연속 API 호출하여 실제 Rate Limit 확인
  - 공식: 일 25,000건
  - 초당 호출 한도 확인 (빠른 연속 호출 20회)
  - 초과 시 응답 코드/메시지 기록
- 검증: `python exploration/naver/03_rate_limit.py`
- 예상: 초당 허용 건수, 일일 한도 대비 현황

**Step 4: 커밋**
```
git add exploration/naver/
git commit -m "feat(phase0.5-sprint1): 네이버 검색 API 검증 — 뉴스 검색/속보 반영/Rate Limit"
```

**완료 기준:**
- ✅ 종목명/코드 뉴스 검색 성공 + 관련성 평가
- ✅ 속보 반영 속도 측정 (1시간 이내 여부 확인)
- ✅ Rate Limit 실측값 기록

---

### Task 6: DART API 검증

**Files:**
- Create: `exploration/dart/01_financial.py`
- Create: `exploration/dart/02_disclosure.py`
- Create: `exploration/dart/03_realtime_check.py`

**Step 1: 재무정보 조회 (01_financial.py)**
- Open Dart API 재무정보 조회
  - URL: `https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json`
  - Params: `crtfc_key`, `corp_code`, `bsns_year`, `reprt_code`
  - corp_code 조회: `/api/corpCode.xml` 또는 기업 고유번호 API
- 테스트 종목 3개(삼성전자/에코프로비엠/KODEX200) 재무 데이터: 매출, 영업이익, 당기순이익
- ETF(KODEX200)는 재무 데이터 제공 여부 확인 (미제공 시 기록)
- 검증: `python exploration/dart/01_financial.py`
- 예상: KOSPI/KOSDAQ 종목 재무 데이터 출력, ETF 응답 차이 기록

**Step 2: 공시 검색 (02_disclosure.py)**
- 최근 공시 목록 조회
  - URL: `https://opendart.fss.or.kr/api/list.json`
  - Params: `crtfc_key`, `bgn_de`(시작일), `end_de`(종료일), `corp_code`(선택)
- 당일 공시 필터링
- 유증, 자사주, 실적 관련 공시 키워드 검색
- 출력: 공시명, 기업명, 접수일시, 공시 유형
- 검증: `python exploration/dart/02_disclosure.py`
- 예상: 최근 공시 목록 출력

**Step 3: 실시간성 확인 (03_realtime_check.py)**
- 당일 공시가 API에 반영되는 지연 시간 추정
  - 당일 공시 중 가장 최근 접수 건의 접수 시간과 현재 시간 비교
  - DART 웹사이트의 최신 공시와 API 결과 비교 (수동 확인 안내)
- Go/No-Go 기준: 당일 공시 1시간 이내 반영 시 Go
- 검증: `python exploration/dart/03_realtime_check.py`
- 예상: 최근 공시 접수~API 반영 지연 시간 출력

**Step 4: 커밋**
```
git add exploration/dart/
git commit -m "feat(phase0.5-sprint1): DART API 검증 — 재무정보/공시 검색/실시간성"
```

**완료 기준:**
- ✅ 재무정보 (매출/영업이익) 조회 성공
- ✅ 당일 공시 검색 + 키워드 필터 성공
- ⬜ 실시간성 측정 (1시간 이내 반영 여부) (주말 0건 — 평일 재확인 필요)

---

### Task 7: 공공데이터포털 API 검증

**Files:**
- Create: `exploration/data_go_kr/01_market_cap.py`
- Create: `exploration/data_go_kr/02_update_cycle.py`
- Create: `exploration/data_go_kr/03_rate_limit.py`

**Step 1: 시가총액/상장주식수 조회 (01_market_cap.py)**
- 금융위원회_주식시세정보 API
  - URL: `http://apis.data.go.kr/1160100/service/GetStockSecuritiesInfoService/getStockPriceInfo`
  - Params: `serviceKey`, `numOfRows`, `pageNo`, `resultType=json`, `likeSrtnCd=005930`
- 테스트 종목 3개(KOSPI/KOSDAQ/ETF) 각각 시가총액, 상장주식수 조회
- ETF의 시가총액/상장주식수 제공 여부 확인 (미제공 시 기록)
- 출력: 종목코드, 종목명, 시가총액, 상장주식수, 기준일자
- 검증: `python exploration/data_go_kr/01_market_cap.py`
- 예상: 3종목 시가총액/주식수 출력, ETF 응답 차이 기록

**Step 2: 데이터 갱신 주기 확인 (02_update_cycle.py)**
- 가장 최근 데이터의 기준일자 확인
  - 오늘 날짜 vs 데이터 기준일자 차이
  - 일 단위 갱신인지, 실시간인지 확인
- 여러 번 호출하여 데이터 변화 여부 확인
- 검증: `python exploration/data_go_kr/02_update_cycle.py`
- 예상: 기준일자(보통 전일), 갱신 주기 추정

**Step 3: Rate Limit 실측 (03_rate_limit.py)**
- 연속 API 호출하여 실제 Rate Limit 확인
  - 공식: 일 1,000건
  - 빠른 연속 호출 10회 → 초당 허용 건수 확인
  - 초과 시 응답 확인 (주의: 일 1,000건이므로 대량 호출 자제)
- 검증: `python exploration/data_go_kr/03_rate_limit.py`
- 예상: 초당 허용 건수, 일일 잔여 건수

**Step 4: 커밋**
```
git add exploration/data_go_kr/
git commit -m "feat(phase0.5-sprint1): 공공데이터포털 API 검증 — 시가총액/갱신 주기/Rate Limit"
```

**완료 기준:**
- ✅ 시가총액/상장주식수 조회 성공
- ✅ 데이터 갱신 주기 확인 (일 단위 추정)
- ✅ Rate Limit 실측값 기록

---

### Task 8: 검증 결과 종합 보고서 + Go/No-Go 판단

**Files:**
- Create: `docs/phase/phase0.5/api-test-report.md`
- Create: `docs/phase/phase0.5/architecture-decisions.md`

**Step 1: api-test-report.md 작성**
- Task 2~7의 실행 결과를 종합하여 작성
- API별 섹션:
  - 검증 결과 요약 (성공/실패 항목)
  - 응답 구조 샘플 (주요 필드 설명)
  - Rate Limit 실측값 (공식 vs 실제)
  - 에러 응답 구조 (한투 5가지 에러 시나리오)
  - 데이터 지연 측정값 (웹소켓, 텔레그램)
  - **Go/No-Go 판단** + 근거
- Go/No-Go 기준 (Phase 문서 확정값):
  - 한투: REST + WS 모두 성공 → Go / WS 불안정 → Conditional (REST 폴링)
  - 텔레그램: 메시지 + 버튼 + 웹훅 성공 → Go
  - 네이버: 속보 반영 1시간 이내 → Go / 초과 → 센티멘트만
  - DART: 당일 공시 1시간 이내 → Go / 초과 → 재무 데이터만
  - 공공데이터포털: 전일 기준 안정적 → Go / 불안정 → 한투에서 직접 계산

**Step 2: architecture-decisions.md 작성**
- 검증 결과에 따른 아키텍처 조정 사항
- Phase 1 설계에 반영할 사항:
  - 한투 웹소켓 안정성 → REST/WS 혼합 전략 여부
  - Rate Limit 실측 → 스로틀링 설정값
  - 에러 응답 구조 → 에러 핸들링 전략
  - 모의거래 체결 로직 차이 → Phase 3 보정 방안
- 조정 시나리오 실현 여부 및 대응

**Step 3: 커밋**
```
git add docs/phase/phase0.5/api-test-report.md docs/phase/phase0.5/architecture-decisions.md
git commit -m "docs(phase0.5-sprint1): API 검증 결과 보고서 + 아키텍처 조정 결정"
```

**완료 기준:**
- ✅ api-test-report.md 완성 (5개 API 모두 기록)
- ✅ Go/No-Go 판단 5건 완료 (한투: Go, 텔레그램: Go, 네이버: Conditional Go, DART: Conditional Go, 공공데이터포털: Go)
- ✅ architecture-decisions.md 완성 (Phase 1 반영 사항)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| 환경 설정 | `pip install -r exploration/requirements.txt` | 의존성 설치 성공 |
| 한투 토큰 | `python exploration/kis/01_auth.py` | access_token 출력 |
| 한투 시세 | `python exploration/kis/02_stock_price.py` | 3종목(KOSPI/KOSDAQ/ETF) 현재가 출력 |
| 한투 주문 | `python exploration/kis/05_order_test.py` | 3종목 주문→취소 왕복 성공 |
| 한투 WS | `python exploration/kis/06_websocket.py` | 30분 수신 + 지연 통계 |
| 한투 에러 | `python exploration/kis/08_error_scenarios.py` | 5개 에러 응답 기록 |
| 텔레그램 | `python exploration/telegram/01_send_message.py` | 앱에서 메시지 확인 |
| 텔레그램 버튼 | `python exploration/telegram/02_inline_button.py` | 버튼+콜백 동작 |
| 네이버 | `python exploration/naver/01_news_search.py` | 뉴스 10건 출력 |
| DART | `python exploration/dart/01_financial.py` | 3종목 재무 데이터 (ETF 차이 기록) |
| 공공데이터 | `python exploration/data_go_kr/01_market_cap.py` | 3종목 시가총액 데이터 |
| 보고서 | `cat docs/phase/phase0.5/api-test-report.md` | Go/No-Go 5건 기록 |
