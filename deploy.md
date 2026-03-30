# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.4.0 (2026-03-30)

포함 스프린트: Phase 3 Sprint 1, Phase 3 Sprint 2, Phase 3 Sprint 3
PR: https://github.com/frogy95/stockbot/pull/35

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 배포 후 검증
- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 프론트엔드 접속 확인 (Vercel)
- ⬜ Railway 배포 후 실제 텔레그램 봇 동작 확인 (웹훅 등록, 승인/거부 버튼)
- ⬜ 주문 실행 지연 < 1초 실전 환경 측정
- ⬜ 알림 지연 < 3초 실전 환경 측정

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
