# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v1.7.0 (2026-04-12)

포함 스프린트: Phase 6 Sprint 1, Sprint 2
PR: https://github.com/frogy95/stockbot/pull/109

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 수동 검증 항목
- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 주요 페이지 접속 확인
- ⬜ WS ConcurrencyError 미재현 확인 (장중 재연결 시 로그 감시)
- ⬜ recovery 단계적 재시도 동작 확인 (09:05/09:10/09:15)
- ⬜ 주말/공휴일 스케줄러 스킵 로그 확인 ("비거래일 스킵: step=...")

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
