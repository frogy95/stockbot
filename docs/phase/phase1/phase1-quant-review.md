# Phase 1 검토 리포트 — 박퀀트 (퀀트 전문가)

**검토일**: 2026-03-29
**검토 대상**: Phase 1 아키텍처 초안 + PRD 미확정 항목 #4 (백테스팅 필요성/시점)

---

## 1. 요약

| 영역 | 판정 |
|------|------|
| 미확정 항목 #4: 백테스팅 필요성/시점 | ⚠️ 주의 — MVP에서 제외하되 데이터 구조는 대비 |
| DB 스키마 (market_data) | ⚠️ 주의 — 시계열 저장 구조 설계 중요 |
| settings 파라미터 구조 | ✅ 통과 |
| Phase 1 전체 범위 | ✅ 통과 |

## 2. 항목별 검증 결과

### 미확정 항목 #4: 백테스팅 필요성/시점

**권고: MVP(Phase 4)에서 제외, Phase 5 이후 도입**

근거:
1. **백테스팅 없이 시작하는 것이 위험하지만, 백테스팅에 매몰되는 것은 더 위험하다.** 1인 프로젝트에서 백테스팅 프레임워크 구축은 Phase 1개 분량의 작업이다.
2. 현재 전략이 확정되지 않은 상태에서 백테스팅 시스템을 만들면, 전략 변경 시 백테스팅 코드도 함께 변경해야 하는 이중 부담이 생�다.
3. **대안**: Phase 2~3에서 수집한 시세 데이터를 market_data 테이블에 축적하고, Phase 5에서 축적된 실제 데이터로 백테스팅. 이것이 가장 현실적이다.
4. **최소한의 대비**: market_data 테이블의 시계열 구조를 백테스팅 친화적으로 설계.

**Phase 1에서 할 것**:
- market_data 테이블에 OHLCV(시가/고가/저가/종가/거래량) 컬럼 포함
- 타임스탬프 인덱스 설계 (날짜 + 시간 복합)
- JSON 필드로 추가 메타데이터 저장 (확장성)

**Phase 1에서 하지 않을 것**:
- 백테스팅 엔진/프레임워크
- 히스토리컬 데이터 대량 수집
- 전략 시뮬레이션

### DB 스키마 — market_data 설계 권고

```sql
CREATE TABLE market_data (
    id BIGSERIAL PRIMARY KEY,
    stock_code VARCHAR(10) NOT NULL,
    market_type VARCHAR(10) NOT NULL,  -- KOSPI, KOSDAQ, ETF
    data_date DATE NOT NULL,

    -- OHLCV (일봉 기준, Phase 1에서는 장전 일괄 수집용)
    open_price DECIMAL(12, 0),
    high_price DECIMAL(12, 0),
    low_price DECIMAL(12, 0),
    close_price DECIMAL(12, 0),
    volume BIGINT,

    -- 추가 데이터
    market_cap BIGINT,              -- 시가총액
    listed_shares BIGINT,           -- 상장주식수
    change_rate DECIMAL(8, 4),      -- 등락률 (%)

    -- 확장용 JSON
    extra_data JSONB DEFAULT '{}',  -- 향후 추가 필드 (분봉, 호가 스냅샷 등)

    -- 메타
    source VARCHAR(20) NOT NULL,    -- data_go_kr, kis_rest, kis_ws
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 인덱스
    UNIQUE(stock_code, data_date, source)
);

CREATE INDEX idx_market_data_date ON market_data(data_date);
CREATE INDEX idx_market_data_stock_date ON market_data(stock_code, data_date);
```

**설계 원칙**:
- `data_date` + `stock_code` + `source` 복합 유니크: 같은 날 같은 종목이라도 소스별 데이터 공존 허용 (공공데이터포털 vs 한투 REST).
- `extra_data` JSONB: Phase 2에서 분봉/호가 데이터 추가 시 스키마 변경 없이 확장.
- **시계열 성능**: Phase 6에서 데이터 누적 시 파티셔닝(월별) 고려. Phase 1에서는 불필요.

### settings 파라미터 구조 의견

최리스크의 리스크 파라미터 + 김단타의 운영 시간 파라미터를 settings에 저장하는 구조에 동의한다. 추가로:

- **전략 파라미터도 settings에 포함** 권고. Phase 3에서 전략 로직 구현 시 하드코딩 방지.
- settings는 **key-value 구조보다 typed columns** 권고. 타입 안전성이 중요하다.

```sql
-- 전략 관련 (Phase 3에서 사용, Phase 1에서 컬럼만)
-- trailing_stop_pct: -1.0  (고점 대비 하락률)
-- min_volume_ratio: 200    (전일 대비 거래량 %)
-- min_market_cap: 1000     (최소 시가총액, 억원)
```

### Phase 1 전체 범위 의견

- Phase 1은 인프라 + API 기반이므로 퀀트 관점에서 직접적 검토 사항은 적다.
- **핵심 권고**: DB 스키마 설계가 이후 Phase의 분석 품질을 결정한다. **market_data, stocks 테이블의 컬럼과 인덱스를 신중하게 설계**해야 한다.
- stocks 테이블에 **시장유형(KOSPI/KOSDAQ), 종목유형(보통주/ETF/레버리지ETF/인버스ETF)** 구분 필드 필수. ETF와 주식의 스크리닝 팩터가 다르므로.

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 확정 권고 | 근거 |
|------|----------|----------|------|
| 백테스팅 | MVP에서 필요성 미정 | **MVP 제외, Phase 5 이후** | 전략 미확정 상태에서 프레임워크 선투자 비효율 |
| market_data 구조 | 미정 | **OHLCV + 시총 + JSON 확장** | 백테스팅 친화적 시계열 구조 |
| stocks 종목유형 | 미정 | **보통주/ETF/레버리지ETF/인버스ETF 구분** | 스크리닝/리스크 팩터 차등 적용의 기반 |
| extra_data JSONB | 미정 | **포함** | 분봉/호가 스냅샷 등 스키마 변경 없이 확장 |

## 4. 리스크 및 대안

- **리스크 1**: market_data에 일봉만 저장하면 Phase 2에서 분봉 데이터 저장 시 스키마 변경이 필요하다. **extra_data JSONB로 분봉 저장 또는 별도 테이블(intraday_data) Phase 2에서 추가**.
- **리스크 2**: 백테스팅 없이 실전 매매를 시작하면 전략 유효성을 검증할 수 없다. **대안**: Phase 3에서 모의거래 기간을 최소 2주로 설정하고, 모의거래 결과를 "간이 백테스팅"으로 활용.
- **리스크 3**: settings에 전략 파라미터를 typed columns로 저장하면 파라미터 추가 시마다 마이그레이션이 필요하다. **대안**: 핵심 파라미터는 typed, 실험적 파라미터는 JSONB 컬럼으로 이원화.
