---
name: Phase 6.2 계획
description: 포털 수집 타이밍 정합성 + 재시도 정책 수정 계획 수립 완료, 전문가 4명 검토, 2 Sprint, 17건 파라미터 확정 (portal_fresh 기반 retry + 14:00 cron + KIS streak 3일 차단)
type: project
---

Phase 6.2: 포털 수집 타이밍 정합성 + 재시도 정책 수정 (2026-04-14 계획 수립)

**Why:** 공공데이터포털 공식 갱신 정책(T+1 영업일 13시 이후)과 08:00 스케줄 충돌 + _premarket_retry 스킵 조건 결함으로 포털 데이터 11일 갭 발생. KIS 폴백만으로 운영되면서 market_cap 미갱신 → 1차 스크리닝 품질 저하(통과 2종목/평소 ~30).

**How to apply:** 
- Sprint 2개: Sprint 1(retry 조건 + 14:00 cron + 알림 승급), Sprint 2(백필 + 관찰성)
- 핵심 수정: _premarket_retry 조건을 `portal_fresh` (DB 직접 확인) 기반으로 변경
- 14:00 보조 cron 추가 (포털 정책 T+1 13시 + 1시간 마진)
- KIS 폴백 streak 3일+ 시 pipeline_healthy=false (자동매매 차단, 반자동은 허용)
- validate_premarket_db 소스 확장: data_go_kr → data_go_kr + kis_daily
- 4/4~4/10 포털 백필 (기존 trigger_premarket_date API 활용)
- 하이브리드 방식(A+B) 채택: 전원 합의

**전문가 검토 주의사항:**
- 최리스크: market_cap=0 종목 시총 필터 탈락은 유지 (부정확한 0값 통과보다 안전)
- 박퀀트: stocks.listed_shares 보정으로 대부분 커버, 신규 IPO만 예외 (극소수)
- 윤에이피: 포털 실제로 T+1 09~11시 조기 배포 잦음 → 08:00 호출 유지 가치 있음
- 정프로: 알림 승급(3거래일) Sprint 1 필수 포함
