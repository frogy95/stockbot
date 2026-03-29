---
name: Phase 1 계획 수립 완료
description: Phase 1 (개발 환경 + 한투 API 기반) 계획 수립 결과 — Sprint 2개, 전문가 5명 검토, 미확정 항목 6건 확정
type: project
---

Phase 1 계획 수립 완료 (2026-03-29).

**Why:** Docker Compose 개발 환경 + 한투 API 연동 기반이 Phase 2 이후 데이터 수집/매매 엔진의 전제.

**How to apply:**
- Sprint 1: Docker Compose 4컨테이너 + FastAPI 스켈레톤 + DB 3테이블(settings/stocks/market_data) + Redis + Alembic
- Sprint 2: KIS REST/WS 클라이언트(core/clients/) + 토큰 자동 갱신 + Rate Limit 스로틀러 + 모의/실전 전환
- 전문가 5명 검토: 정프로(PO), 최리스크(리스크), 김단타(단타), 윤에이피(API), 박퀀트(퀀트)

**확정된 핵심 파라미터:**
1. 데이트레이딩 전용 (당일 청산, 스윙은 Phase 5 이후)
2. 운영 시간: 07:30~16:00, 본매매 09:30~14:30, 시초가(09:00~09:30) 매매 금지
3. 사전 수집: 08:00 공공데이터포털 -> 08:05 스크리닝 -> 08:10 한투 REST
4. 백테스팅: MVP 제외, Phase 5 이후 (market_data 시계열 구조로 대비)
5. 손절 -2%, 익절 +3%, 트레일링 고점 -1%, 레버리지 손절 -1.5%
6. 승인 타임아웃: 장중 30초, 마감전 15초, 기본 60초

**Sprint 2 범위 축소 결정:**
- WS 데이터 파싱/구독관리 -> Phase 2로 이동
- 장상태 감지 iscd_stat_cls_code -> Phase 2로 이동
- 시장 어댑터 상세 구현 -> Phase 2로 이동

**settings 테이블:** key-value 구조 (key/value/value_type/category), 21개 초기 시드 데이터
**KIS 클라이언트 위치:** core/clients/kis_rest.py + kis_ws.py (collector뿐 아니라 주문에서도 사용)
