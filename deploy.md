# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.5 Sprint 1.5 — 전략 필터 shadow evaluation (2026-04-23)

브랜치: `chore/phase8.5-shadow-evaluation` (sprint1.5 브랜치명은 bash-guard self-mod 차단으로 chore/ prefix 사용)
PR: https://github.com/frogy95/stockbot/pull/168 (chore/phase8.5-shadow-evaluation → develop)
계획 문서: `docs/phase/phase8.5/sprint1.5/sprint1.5.md`

- ✅ 자동 검증 완료 항목:
  - pytest: shadow 관련 테스트 4개 + 기존 회귀 전체 GREEN (기존 플레이크 `test_ws_manager_env_max_subscriptions` 1건은 Sprint 1.5 무관)
  - `/api/v1/metrics/shadow-heatmap` API 200 응답 확인 (JWT 인증 포함)
  - 프론트엔드 타입 체크 `npx tsc --noEmit` 통과
  - 로컬 Docker 실시간 shadow 관찰: min_volume_floor가 가리고 있던 volume_threshold/atr_filter/confidence 모두 0% pass 확인 — Sprint 2 튜닝 의사결정에 직접 활용 가능한 실측 데이터 확보

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

- ⬜ 수동 검증 필요 항목:
  - `/diagnostics` 페이지 브라우저 접속하여 Shadow 필터 카드 시각 확인
  - 프로덕션 배포 후 1거래일 관찰: Shadow 카드 8개 stage 모두 의미 있는 표본(≥10건) 누적되는지
  - DB 마이그레이션 불필요 (Redis 전용, 스키마 변경 없음)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
