# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v0.6.0 (2026-03-31)

포함 스프린트: Phase 4 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/45

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 완료 항목 (배포 후 업데이트 예정)

- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 프론트엔드 접속 확인 (stockbot.choiji.kr)

#### 수동 검증 필요 항목 (Railway 배포 후)

- ⬜ 8개 페이지 전체 접속 확인 (대시보드/포지션/주문/신호/스크리닝/이력/분석/설정)
- ⬜ 웹 승인 API 동작 확인 (POST /signals/{token}/approve|reject)
- ⬜ 모드 전환 보호 API 동작 확인 — 장중 차단 + 비밀번호 재확인
- ⬜ 감사 로그 조회 확인 (GET /audit/logs)
- ⬜ Railway alembic 마이그레이션 실행 확인 (`audit_logs` 테이블 생성)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
