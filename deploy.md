# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4.6 Sprint 1: 데이터 수집 파이프라인 근본 수리 (2026-04-02)

포함 스프린트: Phase 4.6 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/58

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

#### 수동 검증 필요 항목

- ⬜ Railway 배포 후 파이프라인 정상 동작 확인 — pipeline-status JSON에 collected_count, validation 키 포함 여부
- ⬜ 수동 파이프라인 트리거 후 premarket 1500건+ 수집 확인 (POST /api/v1/collector/trigger/premarket)
- ⬜ inquiry_client LIVE 환경으로 ETF 시세 수집 정상화 확인 (수집률 >= 50%)
- ⬜ Dockerfile --reload 제거 후 Railway 프로덕션 재시작 루프 미발생 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
