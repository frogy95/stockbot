# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 - v2.6.1 (2026-04-23)

포함 스프린트: Phase 8.5 Sprint 2.5 — 인프라 보강 + 관측성·문서 정합성
PR: https://github.com/frogy95/stockbot/pull/173 (develop → main)

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 신규 환경변수 (Railway 수동 설정 필요)

- ⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway에 추가 (기본값 True, 미설정 시에도 동작하나 명시 권장)

#### 수동 검증 필요 항목 (Railway 프로덕션 배포 후)

- ⬜ `SETTINGS_OVERRIDE_ENABLED=True` Railway 반영 확인
- ⬜ Sprint 2 env 8종(`MIN_VOLUME_FLOOR_MODE` 외) Railway에 존재 확인 (재확인 목적)
- ⬜ Playwright `/diagnostics` 스크린샷 — 배너 미렌더 정상 상태
- ⬜ 5거래일 관찰 종료 후 의사결정 트리(A~E) 판정: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` 하단 참조
- ⬜ DB 마이그레이션 불필요 (Redis + env + 문서만 변경, 스키마 변경 없음)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
