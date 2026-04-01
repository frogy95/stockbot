# Phase 4.6 API 개발자 검토 리포트 — 윤에이피

> **검토일**: 2026-04-02
> **대상**: 데이터 수집 파이프라인 근본 수리 계획 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| Dockerfile --reload 문제 | ❌ 재검토 — 프로덕션에서 --reload는 심각한 결함, 즉시 수정 |
| data_go_kr 수집일 로직 | ⚠️ 주의 — 논리적으로 맞지만 공휴일/임시공휴일 미처리 |
| ETF HTTP 500 | ⚠️ 주의 — 모의투자 서버 한계, 코드 문제 아닌 환경 문제 |
| on_conflict_do_nothing | ⚠️ 주의 — 동일 날짜 재수집 시 건수=0 but "새 데이터 없음" ≠ "수집 실패" |
| stocks 테이블 주식 0건 | ❌ 재검토 — premarket이 한 번도 성공적으로 실행되지 않은 증거 |

## 2. 항목별 검증 결과

### Dockerfile --reload 분석

`backend/Dockerfile` 라인 13:
```
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

`--reload` 옵션은 uvicorn이 WatchFiles(기본) 또는 watchdog를 사용하여 파일 변경을 감지하고 프로세스를 재시작한다. Railway에서는:
1. 배포 시 코드가 변경되면 watchfiles가 트리거
2. 로그 파일, __pycache__, .pyc 파일 생성도 트리거 가능
3. APScheduler가 실행 중인 job을 갖고 있는 상태에서 SIGTERM → 비정상 종료
4. 재시작 후 lifespan이 다시 실행되면서 스케줄러 재등록 → 이전 job 상태 유실

**AttributeError: 'CollectorScheduler' object has no attribute '_market_open_recovery'** 는 reload 과정에서 모듈 로드가 불완전한 상태에서 접근했을 가능성이 높다. 정상 로드에서는 메서드가 존재하지만, reload 중간에 클래스가 부분적으로 재정의되는 타이밍 이슈.

해결: `--reload` 제거. 프로덕션 Dockerfile과 개발용 docker-compose에서 분리.

### data_go_kr _latest_trading_date() 분석

```python
today_kst = datetime.now(ZoneInfo(settings.MARKET_TIMEZONE)).date()
target = today_kst - timedelta(days=1)  # 항상 전일
```

**문제 1**: 공공데이터포털은 당일 데이터를 T+1(또는 T+2)에 제공한다. 4/1(화)에 수집하면 3/31(월) 데이터를 요청하는데, 3/31 데이터가 아직 API에 올라오지 않았을 수 있다. API가 빈 응답을 주면 0건 수집 → success.

**문제 2**: 공휴일 처리 없음. 토/일만 건너뛰지만, 대체공휴일/임시공휴일은 미처리. 공휴일에 해당하는 날짜 데이터를 요청하면 0건 반환.

**문제 3**: `on_conflict_do_nothing`으로 이미 수집된 날짜는 0건 INSERT. collect_all()이 total_collected=0을 반환해도 "이미 있는 데이터"와 "없는 데이터"를 구분할 수 없다.

해결:
1. 수집 전에 DB에서 해당 날짜 데이터 존재 여부 확인
2. 0건 수집이되 DB에도 해당 날짜가 없으면 → warning + 2일 전, 3일 전 순차 시도
3. 공휴일 캘린더(한국거래소 휴장일) 도입 (Nice-to-have, Sprint 2)

### ETF HTTP 500 분석

모의투자 서버(`openapivts.koreainvestment.com`)에서 ETF 시세 조회 시 HTTP 500은 **알려진 한계**다.
- 모의투자 서버는 실전 대비 기능 제한이 있음
- 일부 ETF 종목(특히 신규 상장, 해외 지수 연동)은 모의에서 시세 미제공
- 전체 881개가 전부 500이면 모의 서버 자체 장애일 가능성

해결:
1. `TRADING_ENV=paper`일 때 ETF 시세 수집을 **optional**로 처리 (실패해도 pipeline_healthy에 영향 없음)
2. 실전 전환 시 ETF 시세 수집을 필수로 전환
3. KISCollector에 수집 성공률 반환 + 임계값 검증

### stocks 테이블 주식 0건 분석

`_upsert_stock`에서 `stock_type="STOCK"`으로 설정하는데, stocks에 주식이 0건이라는 것은:
1. premarket(`data_go_kr.collect_all()`)이 **한 번도 데이터를 성공적으로 가져오지 못했거나**
2. 가져왔지만 upsert가 실패했거나 (FK 제약 등)
3. 또는 가져온 데이터의 `srtnCd` 파싱이 실패했거나

가장 가능성 높은 원인: WatchFiles 재시작 루프로 08:00 스케줄이 실행 도중 중단되어 commit이 안 됨.

## 3. 파라미터 조정 권고

| 항목 | 원래 | 권고 | 근거 |
|------|------|------|------|
| Dockerfile CMD | --reload 포함 | **`--reload` 제거, `--workers 1`** | 프로덕션 안정성 |
| docker-compose.yml backend | Dockerfile 공유 | **command override로 --reload 추가** (개발만) | 개발 편의 유지 |
| data_go_kr 날짜 폴백 | 전일만 시도 | **전일 → 2일 전 → 3일 전 순차 시도** (최대 7일) | 공휴일/데이터 지연 대응 |
| collect_all 반환값 | 수집 건수만 | **{collected: int, skipped: int, date: str}** | 수집 품질 판단 근거 |
| KIS ETF 수집 | paper/live 동일 | **paper 환경 optional, live 환경 required** | 모의 서버 한계 인정 |
| updated_at 컬럼 | onupdate=func.now() (ORM 레벨) | **on_conflict_do_update에서 명시적 설정** | pg_insert는 ORM onupdate 무시 |

## 4. 리스크 및 대안

### 즉시 해결 (Sprint 1)
1. Dockerfile --reload 제거 → Railway 재배포만으로 WatchFiles 무한루프 해결
2. data_go_kr 수집 건수 검증 + 날짜 폴백
3. ETF 수집 에러 전파 수정 (0건 = failed)
4. stocks.updated_at NULL 수정 (upsert 시 명시적 타임스탬프)

### 구조적 개선 (Sprint 2)
1. 한국거래소 휴장일 캘린더 (공공API 또는 하드코딩 2026년)
2. 수집 결과 상세 로깅 (건수, 날짜, 소스별)
3. 모의/실전 환경별 파이프라인 단계 활성화 분리
