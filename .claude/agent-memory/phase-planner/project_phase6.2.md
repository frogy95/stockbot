---
name: Phase 6.2 계획
description: 장전 수집 단순화 (KIS 주경로 + 포털 장후 보조), 전문가 4명 rev.2 검토, 1 Sprint, 18건 파라미터 확정 (08:00 KIS 직접 + 16:00 포털 보조 + 상태관리 전면 제거)
type: project
---

Phase 6.2: 장전 수집 단순화 — KIS 주경로 + 포털 장후 보조 (2026-04-14 계획 수립, rev.2 단순화)

**Why:** 공공데이터포털 08:00 호출은 구조적 실패(정책: T+1 13시 이후). 기존 설계(하이브리드 A+B)는 portal_fresh, streak 카운터 등 상태 관리가 과도하게 복잡. 사용자 지적: "08시에 KIS만 호출하면 된다" + "포털 필요 필드 2개뿐" + "장후 포털 수집이 가장 단순" — 코드 레벨 검증 완료.

**How to apply:**
- Sprint 1개 (기존 2개에서 축소): 상태 관리 제거로 작업량 대폭 감소
- 08:00 `_premarket_collect`: 포털 코드 제거 → KIS 일봉 직접 호출
- 08:30 `_premarket_retry`: 포털 재시도 → KIS 실패 시 KIS 재시도
- 16:00 `_portal_supplement_collect` 신규: 포털 market_cap + listed_shares 갱신 (전 종목)
- validate_premarket_db 소스 확장: data_go_kr → data_go_kr + kis_daily
- 제거: portal_fresh, validate_portal_freshness, KIS streak 카운터, 알림 승급, 14:00 cron, 백필 스크립트
- 4/4~4/10 백필: 기존 trigger_premarket_date API로 수동 실행
- 전원 합의: 단순화 채택 (rev.1 하이브리드 대비 복잡도 대폭 감소, 스크리닝 품질 동등)

**전문가 검토 주의사항 (rev.2):**
- 최리스크: KIS 성공이면 자동매매 정상 (streak 차단 불필요), 16:00 포털 5일+ 실패 시 WARNING
- 박퀀트: 3팩터 스코어링 포털 무관, 시총 필터만 listed_shares 보정 의존 (커버리지 99%+)
- 윤에이피: validate_premarket_db 소스 확장 필수 (미수정 시 DB 검증 항상 실패)
- 정프로: 08:30 KIS 재시도 유지 (KIS 간헐 실패 대비 저비용 보험)
