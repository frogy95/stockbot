# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 6 Sprint 1+2 (2026-04-12)

PR: https://github.com/frogy95/stockbot/pull/108

#### 코드 리뷰 결과
- ✅ 코드 리뷰 완료 (sprint-review 에이전트, 2026-04-12)
- kis_ws.py: _reconnect() cancel+await 패턴 정상, 좀비 방지 try/except 정상
- ws_manager.py: and→or 수정 정상
- scheduler.py: is_trading_day 가드 5개 핸들러 적용 완료, recovery 단계적 재시도 정상
- kis_daily_collector.py: _fetch_with_retry 재시도 로직 정상

#### 자동 검증 결과
- ✅ pytest 771 passed, 0 failed (2026-04-12)
- 신규 테스트 20건 + 기존 회귀 수정 10건 전체 통과

#### 수동 검증 항목
- ⬜ WS ConcurrencyError 미재현 확인 (장중 재연결 시 로그 감시)
- ⬜ recovery 단계적 재시도 동작 확인 (09:05/09:10/09:15)
- ⬜ 주말/공휴일 스케줄러 스킵 로그 확인 ("비거래일 스킵: step=...")

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
