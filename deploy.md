# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4.5 Sprint 1: 백엔드 안정화 (2026-04-01)

PR: https://github.com/frogy95/stockbot/pull/54

#### 코드 리뷰 (2026-04-01)

- ✅ 코드 리뷰 완료 — PR 코멘트: https://github.com/frogy95/stockbot/pull/54#issuecomment-4166754495
- Critical/High 이슈: 없음
- Medium 이슈 (1건): 수동 트리거 API BackgroundTask Race condition — 무음 실패 가능성. Phase 4.5 미해결 사항 #6 등록

#### 자동 검증 (2026-04-01)

- ✅ pytest 566 passed, 0 failed (docker compose exec backend pytest -v)
- ✅ GET /health 응답 정상 (status: healthy)
- ✅ GET /health/readiness 응답 정상 (status: ready, DB+Redis+스케줄러+pipeline 모두 확인)
- ✅ GET /collector/pipeline-status 응답 정상 (pipeline_status + pipeline_healthy 포함)
- ✅ POST /collector/trigger/premarket-pipeline 응답 정상 (202 + triggered: true)

#### Phase 문서 반영

- ✅ phase4.5/phase4.5.md Sprint 분할 계획 Sprint 1에 ✅ 표시
- ✅ Sprint 1 상세 섹션 제목에 ✅ 완료 추가 (PR #54, 2026-04-01)
- ✅ 완료 기준 테이블 Sprint 1 항목 8건 → ✅ 완료
- ✅ 미해결 사항 1~3번, 5번 ✅ 해결 표시
- ✅ Medium 이슈(Race condition) 미해결 사항 #6으로 추가

#### 재리뷰 (2026-04-01) — race condition 수정 후

- ✅ 재리뷰 완료 — PR 코멘트: https://github.com/frogy95/stockbot/pull/54#issuecomment-4166805504
- ✅ Medium 이슈(race condition) 수정 확인 — 락 즉시 선점 방식으로 올바르게 수정됨
- High 이슈 (1건): `/health/readiness`의 `pipeline_healthy` 조건이 장전/장후 Railway 재시작 루프 유발 가능
  - **조치**: Railway health check path는 반드시 `/health`(DB+Redis만)로 설정. `/health/readiness`는 거래 준비 상태 모니터링 전용으로 사용 (코드 수정 불필요)

#### 수동 검증 필요 항목

- ✅ Railway health check path 확인: 미설정 (TCP 기본 체크) — 문제없음
- ⬜ Railway 배포 후 아침 체크 — /health/readiness 응답, pipeline-status 응답
- ⬜ 수동 파이프라인 트리거 테스트 (POST premarket-pipeline — 실제 Railway 환경)
- ⬜ 텔레그램 장애 알림 수신 확인 (실제 프로덕션 환경)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
