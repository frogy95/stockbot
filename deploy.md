# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.9.0 (2026-04-02)

포함 스프린트: Phase 4.6 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/63

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 수동 검증 필요 항목

- ⬜ Railway 배포 후 KODEX ETF 시세 수집 확인 — 장중 로그에서 "KODEX ETF 수집 대상: ~280종목" 확인
- ⬜ scheduler 상세 로깅 확인 — 수집 완료 로그에 step/collected/failed/total/validation 포함 여부
- ⬜ DB 후검증 경고 로그 미발생 확인 (정상 수집 시 WARNING 없음)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
