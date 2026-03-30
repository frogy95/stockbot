---
name: Phase 2.6 계획
description: KIS mst 파서 올바른 구현 — Phase 2.5 파서 버그 수정, 단일 Sprint, 전문가 3명 검토
type: project
---

Phase 2.6: KIS mst 파서 올바른 구현 계획 수립 완료 (2026-03-30)

**Why:** Phase 2.5에서 구현한 mst 파서가 실제 파일 구조와 불일치하여 sanity check 항상 실패. Phase 3 진입 블로커.

**How to apply:**
- 단일 Sprint 구성, 수정 파일 2개 (kis_master.py + test_kis_master.py)
- 핵심 변경: 고정길이(200B) -> 줄바꿈 split, offset 121 -> 61:63, 값 '1'/'2' -> 'EF'/'EN'
- 전문가 3명 검토: PO(정프로) + 리스크(최리스크) + API(윤에이피)
- 확정 파라미터: sec_type 필드명 변경 권고, stock_code 6자리 검증 추가, ETN 'EN' 값 실제 확인 필요
- 미해결: KOSDAQ offset 61:63 동일 여부, ETN 증권구분값 실제 확인
