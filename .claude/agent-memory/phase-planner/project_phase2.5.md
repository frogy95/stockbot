---
name: Phase 2.5 계획
description: ETF 데이터 수집 파이프라인 완성 — KIS mst 파일 기반 ETF 마스터 적재, 전문가 3명 검토
type: project
---

Phase 2.5: ETF 데이터 수집 파이프라인 완성 (2026-03-30 계획 수립)

**Why:** 공공데이터포털이 ETF를 미포함하여 stocks 테이블에 ETF가 없고, KISCollector.collect_etf_prices()가 0건 수집하는 문제 해결

**How to apply:**
- 단일 Sprint (소규모 패치성 Phase)
- KIS mst 파일(.mst.zip) HTTP 다운로드 → CP949 파싱 → ETP 필드로 ETF/ETN 필터링
- mst URL: https://new.real.download.dws.co.kr/common/master/{kospi|kosdaq}_code.mst.zip
- KOSPI와 KOSDAQ mst 파일 포맷이 다름 → 파서 반드시 분리
- 3단계 폴백: mst 성공 → mst 실패시 기존DB유지+알림 → 최초설치시 시드50종목
- 스케줄: 08:10 마스터 갱신, 08:15 ETF 시세 수집 (기존 08:05에서 변경)
- leverage_ratio 필드 추가 (종목명 파싱: 레버리지=2, 인버스=-1, 인버스2X=-2)
- ETN은 stock_type='ETN'으로 별도 분류
- sanity check: 최소 200종목 + spot-check 5종목 + 전일대비 +-10%
- mst URL은 환경변수 KIS_MST_BASE_URL로 관리 (URL 변경 전례 있음)

전문가 검토: PO(정프로), 리스크(최리스크), API(윤에이피) 3명
핵심 파라미터 확정: 갱신시각 08:10, 시세수집 08:15, 타임아웃 60초, 재시도 3회/10초, 최소경고 200종목
