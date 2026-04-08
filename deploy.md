# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 5.2 Sprint 1 (2026-04-08)

PR: https://github.com/frogy95/stockbot/pull/106

#### 코드 리뷰 결과 (2026-04-08)
- ⬜ Critical/High 이슈: 0건
- ⬜ Medium 이슈: 1건 — `_reconnect()` 구독 복원 중 예외 발생 시 수신 루프 미시작(연결 누수). Phase 문서 미해결 사항 #6에 기록. 다음 Sprint에서 개선 권장.
- PR 코멘트 게시 완료: https://github.com/frogy95/stockbot/pull/106#issuecomment-4203336929

#### 자동 검증 결과 (2026-04-08)
- ✅ pytest 751 passed, 0 failed (test_kis_ws.py 19건 + test_ws_stability.py 6건 포함)
- ✅ Phase 5.2 신규 테스트 25건 전체 통과

#### 수동 검증 필요 항목 (프로덕션 배포 후)
- ⬜ 모의 환경 WS 연속 1시간 안정 연결 확인 (장중)
- ⬜ 2차 스크리닝 30초 주기 10회 연속 실행 확인 (Railway 로그)
- ⬜ WS 재연결 시 종목 간 딜레이 로그 확인 ("구독 복원 중: N/M 종목")

#### Phase 문서 반영 상태
- ✅ docs/phase/phase5.2/phase5.2.md Sprint 1 완료 표시, 완료 기준 업데이트, 미해결 사항 #6 추가

---

### 프로덕션 배포 - v1.5.0 (2026-04-08)

포함 스프린트: Phase 5 Sprint 1+2, Phase 5.1 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/104

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 완료 항목
- ✅ pytest 742 passed, 0 failed
- ✅ 코드 리뷰 완료 — Critical/High 이슈 없음
- ✅ 신규 환경변수 없음 (Railway 설정 변경 불필요)

#### 수동 검증 필요 항목
- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 프론트엔드 메인 페이지 접속 확인
- ⬜ 프로덕션 1차 스크리닝 통과 >0건 확인 (장중)
- ⬜ Railway 로그에서 "1차 필터 통계" WARNING 로그 출력 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
