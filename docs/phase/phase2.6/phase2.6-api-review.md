# Phase 2.6 검토 리포트 — 윤에이피 (API 개발자)

> **검토일**: 2026-03-30
> **검토 대상**: KIS mst 파서 올바른 구현 — 아키텍처 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| mst 파일 구조 이해 | ✅ 통과 — 줄바꿈 분리 + CP949 인코딩 확인됨 |
| 파싱 로직 설계 | ✅ 통과 — 줄바꿈 split 방식이 고정길이보다 견고 |
| KOSPI/KOSDAQ 차이 처리 | ⚠️ 주의 — 라인 길이 차이(288 vs 282)에 따른 offset 검증 필요 |
| 기존 인터페이스 호환성 | ✅ 통과 — collect() 반환값, filter_etf() 시그니처 유지 |

## 2. 항목별 검증 결과

### mst 파일 구조 분석
실제 KOSPI mst 라인 예시에서 확인된 구조:
- 0:9 = 종목코드 (6자리 + 공백 3)
- 9:21 = ISIN (12자리)
- 21:61 = 종목명 (40바이트, CP949)
- 61:63 = 증권구분 (2바이트: 'EF'=ETF, 'ST'=주식, 'EN'=ETN 추정)

**핵심 변경점**:
- `data.decode("cp949").split("\n")` → 줄 단위 순회
- 각 줄에서 `line[0:9].strip()` = stock_code, `line[21:61].strip()` = stock_name, `line[61:63]` = 증권구분
- KOSPI/KOSDAQ 모두 동일한 offset (0:9, 21:61, 61:63) 사용 가능 — 라인 길이 차이는 뒷부분 필드에서 발생

### 파싱 로직 권고
```python
# 권고 구조 (의사코드)
text = data.decode("cp949")
for line in text.split("\n"):
    line = line.rstrip("\r")  # Windows 줄바꿈 대비
    if len(line) < 63:  # 최소 필수 길이
        continue
    stock_code = line[0:9].strip()
    stock_name = line[21:61].strip()
    sec_type = line[61:63]
    ...
```

### KOSPI/KOSDAQ offset 차이
- 두 시장의 앞부분 필드(0:63)는 동일한 구조로 추정
- 라인 길이 차이(288 vs 282)는 63 이후 필드에서 발생
- **판단**: 0:63 범위만 파싱하므로 시장별 분기 불필요. 단, 실제 KOSDAQ mst로 검증 필수

### 기존 인터페이스 호환성
- `parse_kospi_mst(data)` / `parse_kosdaq_mst(data)` → 동일 시그니처 유지
- `filter_etf(records)` → `etp_prod_type` 필드명은 `sec_type` 또는 동일 이름으로 변경 가능
- `collect()` 반환값 구조 변경 없음
- **판단**: 필드명을 `sec_type`으로 변경하면 의미가 더 명확하지만, 내부 필드이므로 결정은 자유

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 권고값 | 근거 |
|------|----------|--------|------|
| 최소 라인 길이 검증 | _RECORD_LEN=200 | **63바이트** | 파싱에 필요한 최소 길이 (offset 61:63까지) |
| 줄바꿈 처리 | 고정길이 offset | **`\n` split + `\r` strip** | mst 파일이 Windows 줄바꿈(\r\n)일 가능성 대비 |
| 빈 줄 처리 | (없음) | **빈 줄/짧은 줄 스킵** | 파일 끝 빈 줄 등 |
| 내부 필드명 | etp_prod_type | **sec_type 권고** (선택) | 증권구분이 더 정확한 의미, 하지만 기존 호환성 고려 시 유지도 가능 |

## 4. 리스크 및 대안

- **리스크 1**: mst 파일이 BOM(Byte Order Mark) 포함 가능성
  - **대안**: decode 후 첫 문자가 BOM이면 strip
  - **심각도**: 낮 (CP949는 일반적으로 BOM 미포함)

- **리스크 2**: KIS 서버에서 mst 파일 포맷 변경 시 무결성 검증
  - **대안**: sanity check(기존 로직) + stock_code 패턴 검증으로 이중 방어
  - **심각도**: 중 (발생 빈도 낮으나 발생 시 영향 큼)

- **리스크 3**: 실제 KOSDAQ mst의 증권구분 offset이 KOSPI와 다를 가능성
  - **대안**: Phase 2.6 Sprint 1에서 실제 다운로드 검증을 Task로 포함
  - **심각도**: 중 (다를 경우 시장별 파서 분기 필요)
