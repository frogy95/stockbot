# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

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
