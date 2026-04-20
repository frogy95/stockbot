# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v2.3.0 (2026-04-20)

포함 스프린트: Phase 8 Sprint 1 (장중 실시간 OHLC 파싱 + 갭 분기 자기돌파 버그 수정)
PR: https://github.com/frogy95/stockbot/pull/150 (develop → main)

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 결과

- ✅ Railway 헬스체크: `{"status":"healthy","database":"connected","redis":"connected"}` 확인
- ✅ Railway 로그: 오류 없이 정상 시작 (Uvicorn, 스케줄러, 매매 엔진, 텔레그램 웹훅 모두 정상)
- ✅ Vercel 프론트엔드: HTTP 307 (정상 리다이렉트) 확인

#### 수동 검증 필요 항목

- ⬜ `docker compose up --build` 로컬 스테이징 검증
- ⬜ 배포 직후 Redis `realtime:{code}:execution` JSON OHLC 3필드 존재 확인
- ⬜ 1~2시간 장중 모니터링 — 파싱 경고 비율 < 1%
- ⬜ 샘플 5종목 실시간 OHLC를 KIS 공식 시세와 대조 (김단타 권고)
- ⬜ 2거래일 연속 `momentum_breakout` 신호 1건 이상 생성 확인

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
