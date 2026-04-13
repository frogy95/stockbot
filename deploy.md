# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 6.1 Sprint 1

PR: (PR 생성 후 기입)

- ⬜ 코드 리뷰 미수행 (sprint-review 에이전트로 실행 필요)
- ⬜ 자동 검증 미수행 (sprint-review 에이전트로 실행 필요)

#### 수동 검증 항목 (develop → main 머지 전)

- ⬜ /api/v1/health 헬스체크 확인
- ⬜ 주요 페이지 접속 확인
- ⬜ vol5m API 응답 확인: `curl -s https://api.stockbot.choiji.kr/api/v1/collector/vol5m/005930 | jq .`
- ⬜ 장중 adjusted_ratio/volume_threshold/breakout_pct/market_progress 필드 로그 확인
- ⬜ 5분봉 Redis 키 축적 확인 (3거래일 모니터링)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
