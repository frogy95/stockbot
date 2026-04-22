# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.5 Sprint 1 — 관측성 강화 (score 히스토그램 + stage heatmap + 탈락 상위 + 가상 신호 로깅)

PR: (생성 후 기입)

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

#### 배포 후 필수 수동 조치

- ⬜ `docker compose up --build` (코드 반영)
- ⬜ `docker compose exec backend alembic upgrade head` (3개 신규 테이블 생성: screening_metrics_daily, strategy_metrics_daily, virtual_signals)
- ⬜ 1.5거래일 관찰: `/diagnostics` 페이지 카드 1~3 메트릭 정상 수집 확인
- ⬜ 1.5거래일 관찰: 16:05 스케줄러 집계 job 실행 확인 (`metrics_rollup` job_id 로그 출력)
- ⬜ DB 조회로 집계 확인: `SELECT * FROM screening_metrics_daily ORDER BY metric_date DESC LIMIT 20;`
- ⬜ DB 조회로 가상 신호 확인: `SELECT * FROM virtual_signals ORDER BY observed_at DESC LIMIT 20;`
- ⬜ Stage heatmap에서 `prev_close_time_guard` 13:00~14:00 구간 카운트 증가 확인

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
