# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.7.0 (2026-04-01)

포함 스프린트: Phase 4.5 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/55

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 수동 검증 필요 항목

- ⬜ Railway 배포 후 아침 체크 — /health/readiness 응답, pipeline-status 응답
- ⬜ 수동 파이프라인 트리거 테스트 (POST premarket-pipeline — 실제 Railway 환경)
- ⬜ 텔레그램 장애 알림 수신 확인 (실제 프로덕션 환경)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
