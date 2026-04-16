---
name: Phase 7.0.1 계획
description: KIS LIVE WebSocket 연결 복구 — ws_url /tryitout 경로 누락 + Railway Static IP, 전문가 4명 검토, 단일 Sprint
type: project
---

## Phase 7.0.1 계획 수립 완료 (2026-04-16)

**목표**: KIS LIVE WS 연결 전면 실패 복구 (2026-04-16 발생)

**근본 원인**:
- 원인 B (확정): ws_url에 `/tryitout` 경로 누락 — KIS 공식 예제 100% `/tryitout` 사용 확인
- 원인 A (유력): Railway 동적 IP가 KIS LIVE WS 서버에 미등록

**핵심 결정사항**:
1. LIVE ws_url: `ws://ops.koreainvestment.com:21000/tryitout` (공식 예제 일치)
2. PAPER ws_url: LIVE 검증 후 별도 수정 (4명 전원 합의 — 기존 PAPER 동작 보호)
3. Railway Static IP: 무조건 활성화 (최리스크: LIVE 운영 필수)
4. diagnose_ws.py 선행 필수 (원인 확정 후 코드 배포)

**Sprint 구조**: 단일 Sprint (4 Task)
- Task 1: diagnose_ws.py Railway 실행 (원인 확정)
- Task 2: kis_config.py LIVE ws_url 수정
- Task 3: Railway Static IP + KIS IP 등록
- Task 4: 검증 (ws_connected=True)

**전문가**: 정프로(PO), 최리스크(리스크), 윤에이피(API), 김단타(단타) — 4명

**Why:** Phase 7.0 Sprint 3 (E2E + LIVE 전환 게이트)의 선행 조건. LIVE WS 미연결 상태에서는 실시간 시세 수신 불가 → 매매 불가.

**How to apply:** Phase 7.0.1 완료 후 Phase 7.0 Sprint 3 진행. PAPER ws_url 수정은 Sprint 3에서.

**주의사항**:
- PAPER에 `/tryitout` 추가 시 기존 동작 깨질 가능성 (사전 테스트 필수)
- KIS IP 등록 반영 시간 미확인 (즉시가 아닐 수 있음)
- Phase 번호 7.0.1은 신규 관례 (기존은 소수점 1자리까지)
