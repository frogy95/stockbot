# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Hotfix: ETF 마스터 sanity check 데드락 수정 (2026-04-02)

PR: https://github.com/frogy95/stockbot/pull/60

- ✅ 자동 검증 완료 항목:
  - pytest: 603 passed, 0 failed
  - 코드 리뷰: Critical/High 이슈 없음

- ⬜ 수동 검증 필요 항목:
  - docker compose up --build (코드 반영)
  - 배포 후 ETF 마스터 수동 트리거 (POST /api/v1/collector/trigger/etf-master) → sanity check 통과 확인
  - ETF 시세 수동 트리거 (POST /api/v1/collector/trigger/etf) → 수집률 50%+ 확인
  - pipeline-status에서 etf_master status="success" 확인

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
