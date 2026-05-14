# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### Phase 8.6 Sprint 5 (2026-05-15)

PR: (생성 후 기입)

**Sprint 목표**: 진단·측정 Sprint — T1 코드 즉답 + T2 DB/백테스트 + T3 라이브 WS trace 인프라 구축. DoD 6/9 달성, 잔여 3건(T3 trace 1주 누적, G-Bt1/G-Bt2 백필) Sprint 6 대기.

**신규 환경변수 (Railway 수동 설정)**:
- ✅ `WS_TRACE_ENABLED=true` — Railway 설정 완료 (2026-05-15). Paper 1주 trace 수집용 (5/22까지).
- ⬜ `WS_TRACE_ENABLED=false` 복귀 — 5/22 Paper 1주 trace 수집 완료 후 Railway에서 `false`로 변경 필요.

**검증 항목**:
- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

**후속 결정 필요 항목** (sprint-review 또는 사용자 직접):
- ⬜ Sprint 6 신설 여부 결정 (우선순위 후보: KIS 일봉 60일 백필 + #16 fallback 0% + #11 stage OR 구조 + #14 hysteresis)
- ⬜ T3 WS trace 1주(5/22) 후 #6 root cause 채택 + 후속 fix 결정
- ⬜ Phase 8.7 entry gate 재평가 (백필 완료 + E1/G-Bt1/G-Bt2 측정 후)

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
