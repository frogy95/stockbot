# Sprint 1: KIS mst 파서 재작성 + 검증 (Phase 2.6)

**Goal:** Phase 2.5에서 잘못 구현된 mst 파서를 실제 파일 구조(줄바꿈 분리, 증권구분 offset 61:63)에 맞게 재작성하여 sanity check 블로커를 해소한다.

**Architecture:** 기존 `KISMasterCollector` 클래스의 `_parse_mst()` 메서드를 고정길이 200바이트 방식에서 줄바꿈(`\n`) split 방식으로 전면 교체한다. `filter_etf()`의 ETP 판별 필드를 offset 121의 '1'/'2'에서 offset 61:63의 'EF'/'EN'으로 변경한다. 외부 인터페이스(`collect()`, `sanity_check()`, `sync_to_db()`)는 변경 없이 유지한다.

**Tech Stack:** Python 3.12, pytest, CP949 인코딩

**Sprint 기간:** 2026-03-30 ~ 2026-03-30
**상태:** ✅ 완료
**PR:** https://github.com/frogy95/stockbot/pull/27
**이전 스프린트:** Phase 2.5 Sprint 1 (pytest 통과, PR #26)
**브랜치명:** `phase2.6-sprint1`

---

## 제외 범위

- ISIN 등 추가 필드 파싱 (Phase 3에서 필요 시 추가)
- ETN 매매 로직 (파싱/분류까지만, 매매는 Phase 3 이후)
- `download_mst()`, `sanity_check()`, `enrich_etf_metadata()`, `sync_to_db()`, `collect()` 변경 없음
- Alembic 마이그레이션 (DB 스키마 변경 없음)

## 실행 플랜

모든 변경이 동일 파일 2개에 집중되어 병렬 불가. 단일 Phase 순차 실행.

### Phase 1 (순차)
| Task | 설명 | 대상 | skill |
|------|------|------|-------|
| Task 1 | 테스트 fixture + 테스트 재작성 (줄바꿈 기반) | 백엔드 | -- |
| Task 2 | 상수 교체 + `_parse_mst()` 재작성 + `filter_etf()` 수정 | 백엔드 | -- |
| Task 3 | 실제 mst 다운로드 검증 (KOSPI/KOSDAQ offset, ETN 구분값) | 백엔드 | -- |

---

### Task 1: 테스트 fixture + 테스트 재작성

**Files:**
- Modify: `backend/tests/test_kis_master.py` (fixture 함수 + parse/filter 테스트를 줄바꿈 기반으로 전면 재작성)

**Step 1: `_make_mst_record` -> `_make_mst_line` + `_make_mst_bytes` 재작성**
- `_make_mst_record()` 함수를 삭제하고 다음 2개 함수로 교체:
  - `_make_mst_line(stock_code, stock_name, sec_type="EF", total_len=288) -> str`: CP949 고정길이 라인 문자열 생성. offset 0:9 종목코드(ljust 9), 9:21 ISIN 더미(12자), 21:61 종목명(ljust 40, CP949 바이트 기준), 61:63 증권구분(ljust 2), 나머지 공백 패딩
  - `_make_mst_bytes(lines: list[str]) -> bytes`: `"\n".join(lines).encode("cp949")` 반환
- 검증: `docker compose exec backend pytest tests/test_kis_master.py::test_parse_kospi_mst_etf -v`
- 예상: FAIL (아직 프로덕션 코드 미변경, 파서가 고정길이 방식이므로 줄바꿈 fixture와 불일치)

**Step 2: parse 테스트 업데이트**
- `test_parse_kospi_mst_etf`: `_make_mst_line("069500", "KODEX 200", "EF")` 사용, `_make_mst_bytes()`로 감싸서 전달. assert 필드를 `etp_prod_type` -> `sec_type`으로 변경, 값을 `"EF"`로 변경
- `test_parse_kospi_mst_normal_stock`: sec_type을 `"  "` (공백 2자)로, assert를 `sec_type` strip 빈 문자열로 변경
- `test_parse_kosdaq_mst_etf`: 동일 패턴 적용
- stock_code 6자리 숫자 검증 테스트 추가: `test_parse_mst_skips_invalid_stock_code` -- stock_code가 "ABCDEF"인 라인과 빈 줄을 포함한 mst 바이트를 생성, 파싱 결과에서 제외되는지 확인
- 최소 라인 길이 미달 테스트 추가: `test_parse_mst_skips_short_line` -- 62바이트 짧은 라인이 스킵되는지 확인
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -k "test_parse" -v`
- 예상: FAIL (프로덕션 코드 미변경)

**Step 3: filter_etf 테스트 업데이트**
- `test_filter_etf_keeps_etf`: 레코드의 `etp_prod_type` -> `sec_type`, 값 `"1"` -> `"EF"`
- `test_filter_etf_keeps_etn`: `etp_prod_type` -> `sec_type`, 값 `"2"` -> `"EN"`
- `test_filter_etf_excludes_normal`: `etp_prod_type` -> `sec_type`, 값 `" "` / `""` 유지
- 알 수 없는 증권구분 스킵 테스트 추가: `test_filter_etf_skips_unknown_sec_type` -- sec_type이 "XX"인 레코드가 결과에서 제외되는지 확인
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -k "test_filter" -v`
- 예상: FAIL (프로덕션 코드 미변경)

**Step 4: collect 통합 테스트 업데이트**
- `test_collect_normal_flow`: `fake_download`가 반환하는 데이터를 `_make_mst_line` + `_make_mst_bytes` 기반으로 재작성. spot-check 5종목 + 250개 ETF 라인을 줄바꿈으로 결합하여 CP949 인코딩
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -k "test_collect" -v`
- 예상: FAIL (프로덕션 코드 미변경)

**Step 5: 커밋**
```
git add backend/tests/test_kis_master.py
git commit -m "feat(phase2.6-sprint1): task1 -- 테스트 fixture 줄바꿈 기반 재작성"
```

**완료 기준:**
- ✅ 테스트 파일 컴파일/임포트 정상 (SyntaxError 없음)
- ✅ 테스트 FAIL 사유가 "프로덕션 코드 불일치"인지 확인 (fixture 자체 오류가 아닌지)

---

### Task 2: 상수 교체 + _parse_mst 재작성 + filter_etf 수정

**Files:**
- Modify: `backend/modules/collector/sources/kis_master.py` (상수, `_parse_mst()`, `filter_etf()`, docstring 수정)

**Step 1: 상수 교체**
- 다음 상수를 삭제:
  ```
  _CODE_START, _CODE_LEN, _NAME_START, _NAME_LEN, _ETP_START, _ETP_LEN, _RECORD_LEN
  ETP_ETF, ETP_ETN
  ```
- 다음 상수를 추가:
  ```
  _CODE_SLICE = slice(0, 9)       # 종목코드 6자리 + 공백3
  _NAME_SLICE = slice(21, 61)     # 종목명 40바이트
  _SEC_TYPE_SLICE = slice(61, 63) # 증권구분 2바이트
  _MIN_LINE_LEN = 63              # 파싱 필수 최소 길이
  SEC_TYPE_ETF = "EF"
  SEC_TYPE_ETN = "EN"
  ```
- `import re` 추가 (상단 import 블록에)
- 검증: `docker compose exec backend python -c "from modules.collector.sources.kis_master import KISMasterCollector; print('import OK')"`
- 예상: import OK

**Step 2: `_parse_mst()` 재작성**
- 기존 고정길이 offset 방식 전체 삭제 후 줄바꿈 split 방식으로 교체:
  - `data.decode("cp949")`로 텍스트 변환
  - `text.split("\n")`으로 라인 분리
  - 각 라인에 `line.rstrip("\r")` 적용 (Windows 줄바꿈 대비)
  - `len(line) < _MIN_LINE_LEN` 이면 스킵
  - `line[_CODE_SLICE].strip()`으로 stock_code 추출, `re.match(r"^\d{6}$", stock_code)` 검증 실패 시 스킵
  - `line[_NAME_SLICE].strip()`으로 stock_name 추출
  - `line[_SEC_TYPE_SLICE]`로 sec_type 추출
  - 레코드 dict: `stock_code`, `stock_name`, `market_type`, `sec_type` (기존 `etp_prod_type` 키 -> `sec_type`으로 변경)
- 클래스 docstring에서 "CP949 고정길이 파싱" -> "CP949 줄바꿈 분리 파싱"으로 수정
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -k "test_parse" -v`
- 예상: PASS (Task 1에서 작성한 테스트와 일치)

**Step 3: `filter_etf()` 수정**
- `etp_prod_type` -> `sec_type` 키 참조
- `ETP_ETF` ("1") -> `SEC_TYPE_ETF` ("EF") 비교
- `ETP_ETN` ("2") -> `SEC_TYPE_ETN` ("EN") 비교
- 알 수 없는 sec_type은 `logger.debug("알 수 없는 증권구분: %s (종목=%s)", sec, r.get("stock_code"))` 후 스킵
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -k "test_filter" -v`
- 예상: PASS

**Step 4: 전체 테스트 실행**
- 검증: `docker compose exec backend pytest tests/test_kis_master.py -v`
- 예상: 전체 PASS
- 검증: `docker compose exec backend pytest -v`
- 예상: 전체 PASS (다른 모듈 영향 없음)

**Step 5: 커밋**
```
git add backend/modules/collector/sources/kis_master.py
git commit -m "feat(phase2.6-sprint1): task2 -- 상수 교체 + _parse_mst 줄바꿈 재작성 + filter_etf 수정"
```

**완료 기준:**
- ✅ `tests/test_kis_master.py` 전체 PASS (25 passed)
- ✅ `pytest -v` 전체 PASS (343 passed, 회귀 없음)
- ✅ `_parse_mst()`가 줄바꿈 split 방식 + 바이트 슬라이싱 기반
- ✅ `filter_etf()`가 sec_type 'EF'/'EN' 사용

---

### Task 3: 실제 mst 다운로드 검증

**Files:**
- 변경 파일 없음 (검증 전용 Task)
- 필요 시 Modify: `backend/modules/collector/sources/kis_master.py` (ETN 구분값이 'EN'이 아닌 경우)

**Step 1: mst 다운로드 URL 접근성 확인**
- 검증: `curl -sI "https://new.real.download.dws.co.kr/common/master/kospi_code.mst.zip" | head -5`
- 예상: HTTP 200 (SLA 미보장이므로 실패 가능 -- 실패 시 Task 3 전체를 "수동 검증 필요"로 표기)

**Step 2: Docker 환경에서 실제 mst 다운로드 + 파싱 검증**
- `docker compose exec backend python` 인터랙티브 또는 1회용 스크립트로 실행:
  ```python
  # 검증 스크립트 (실행 후 삭제)
  import asyncio
  from core.database import async_session_factory
  from modules.collector.sources.kis_master import KISMasterCollector

  async def verify():
      async with async_session_factory() as session:
          collector = KISMasterCollector(session)
          result = await collector.collect()
          print(f"결과: {result}")

  asyncio.run(verify())
  ```
- 검증: `result["sanity_passed"]` == True, `result["etf_count"]` >= 200
- 예상: sanity check 통과

**Step 3: KOSDAQ mst offset 61:63 검증**
- Docker 환경에서 KOSDAQ mst를 다운로드하여 ETF 종목의 offset 61:63이 'EF'인지 확인
  ```python
  # 검증 스크립트 (실행 후 삭제)
  import asyncio
  from modules.collector.sources.kis_master import KISMasterCollector, _SEC_TYPE_SLICE
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

  async def verify_kosdaq():
      # DB 세션 없이 파싱만 검증
      from unittest.mock import AsyncMock
      collector = KISMasterCollector(AsyncMock(spec=AsyncSession))
      data = await collector.download_mst("kosdaq")
      records = collector.parse_kosdaq_mst(data)
      etfs = [r for r in records if r["sec_type"].strip() == "EF"]
      print(f"KOSDAQ ETF 종목 수: {len(etfs)}")
      if etfs:
          print(f"첫 ETF: {etfs[0]}")

  asyncio.run(verify_kosdaq())
  ```
- 예상: KOSDAQ ETF 종목 1개 이상 존재

**Step 4: ETN 증권구분값 확인**
- 실제 mst에서 sec_type이 'EN'인 종목이 있는지 확인
  ```python
  # KOSPI + KOSDAQ 전체에서 sec_type 고유값 수집
  sec_types = set(r["sec_type"].strip() for r in all_records if r["sec_type"].strip())
  print(f"발견된 증권구분 값: {sec_types}")
  etns = [r for r in all_records if r["sec_type"].strip() == "EN"]
  print(f"ETN 종목 수: {len(etns)}")
  ```
- 예상: 'EN' 종목 존재 확인 또는 실제 ETN 구분값 발견
- **리스크**: 'EN'이 아닌 경우 -> `SEC_TYPE_ETN` 상수를 실제 값으로 교체하고 추가 커밋

**Step 5: 결과 기록 + 커밋 (코드 변경 시에만)**
- ETN 구분값이 'EN'이 아닌 경우에만 코드 수정 + 커밋:
  ```
  git add backend/modules/collector/sources/kis_master.py
  git commit -m "fix(phase2.6-sprint1): task3 -- ETN 증권구분값 {실제값}으로 수정"
  ```
- 코드 변경 없으면 커밋 생략

**완료 기준:**
- ✅ 실제 mst 다운로드 성공
- ✅ sanity_check 통과 (ETF=878종목, sanity_passed=True)
- ✅ KOSDAQ mst에 ETF 없음 확인 (KOSDAQ mst는 ETF 미포함)
- ✅ ETN 증권구분값 확인 (해당 URL mst에 ETN 미포함, 'EN' 종목 미발견)

---

## 최종 검증 계획

| 검증 항목 | 명령 | 예상 결과 |
|-----------|------|-----------|
| pytest 전체 | `docker compose exec backend pytest -v` | 전체 PASS (기존 테스트 포함) |
| kis_master 테스트 | `docker compose exec backend pytest tests/test_kis_master.py -v` | 전체 PASS |
| 실제 mst collect | Docker 내 1회용 스크립트 | sanity_passed=True, etf_count >= 200 |
| KOSDAQ ETF 존재 | Docker 내 스크립트 | KOSDAQ ETF 1종목 이상 |
| ETN 종목 확인 | Docker 내 스크립트 | ETN 종목 존재 또는 구분값 문서화 |
