# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 0.5 Sprint 1: 외부 API 5종 탐색/검증 (2026-03-29)

PR: https://github.com/frogy95/stockbot/pull/1 (phase0.5-sprint1 → develop)

#### 코드 리뷰 결과
- ✅ Critical/High 이슈: 없음
- ✅ Medium 이슈: 없음 (탐색용 코드 특성 감안)
- ✅ 보안: .env 및 .token_cache.json 모두 .gitignore 적용 확인
- ✅ CLAUDE.md 준수 확인

#### 자동 검증 결과
- ✅ pytest: 해당 없음 (탐색 스크립트, pytest 미사용)
- ✅ API 엔드포인트 검증: 해당 없음 (탐색 Phase, 서버 코드 없음)
- ✅ Playwright 검증: 해당 없음 (UI 변경 없음)

#### Phase 문서 반영 상태
- ✅ Sprint 분할 계획 테이블: Sprint 1 `✅` 표시 완료
- ✅ Sprint 상세 섹션: `✅ 완료` + PR 번호/날짜 추가
- ✅ 미해결 사항 테이블: 해결된 항목 4건 `~~취소선~~` + `✅ 해결` 표시
- ✅ 완료 기준 테이블: 완료 항목 `⬜` → `✅` 변경

#### 수동 검증 필요 항목
- ⬜ 🕐 **장중 전용** 한투 모의 주문 실행/취소 왕복 (평일 09:00~15:30)
  - 실행: `python exploration/kis/05_order_test.py`
- ⬜ 🕐 **장중 전용** 한투 웹소켓 30분 연결 유지 (평일 09:00~15:30)
  - 실행: `python exploration/kis/06_websocket.py --duration 1800`
- ⬜ 🕐 **평일 전용** DART 당일 공시 실시간성 확인
  - 실행: `python exploration/dart/03_realtime_check.py`
- ⬜ 배포 후 develop → main PR 생성 (sprint-review 완료 후)

---

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
