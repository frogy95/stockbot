# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v2.1.0 (2026-04-16)

포함 스프린트: Phase 7.0 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/136

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 코드 리뷰 결과 (2026-04-16)

- ✅ 코드 리뷰 완료 — Critical/High/Medium 이슈 0건
  - risk_manager.py: daily_loss 분모를 당일 시작 잔고(Redis `risk:daily_capital`) 기반으로 수정
  - position_manager.py: record_loss 확장 (realized_pnl < 0 전체), trailing_highs Redis 이관
  - eod_liquidator.py: liquidate_all 시 Redis trailing_highs 전체 삭제 추가
  - engine.py / main.py: 배선 업데이트

#### 자동 검증 결과 (2026-04-16)

- ✅ pytest: 837 passed / 5 failed (기존 무관 결함)
- ⬜ /api/v1/health 헬스체크 확인 (프로덕션 Railway)
- ⬜ /api/v1/kis/status 확인 (프로덕션 Railway)

#### 수동 작업 필수 항목 (머지 후 즉시 실행)

- DB 스키마 변경 없음 — Alembic 마이그레이션 불필요
- 신규 환경변수 없음 — Railway 환경변수 변경 불필요
- Redis 키 변경 사항: `risk:daily_capital`, `trailing_highs`, `exit:inflight:{stock_code}` (신규 키, 자동 생성)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
