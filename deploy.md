# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

---

### 프로덕션 배포 - v2.7.0 (2026-04-29)

포함 스프린트: Phase 8.6 Sprint 1 — LIVE 보호 가드레일 (G1+G2+G3 + Phase 7.0 잠금)
PR: https://github.com/frogy95/stockbot/pull/182 (develop → main)

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 결과 (배포 완료 후)

- ✅ 백엔드 헬스체크 (Railway): `{"status":"healthy","database":"connected","redis":"connected"}`
- ✅ 프론트엔드 접속 (Vercel): HTTP 200 (https://stockbot.choiji.kr)
- ✅ Alembic 마이그레이션: `upgrade a430a1c931b2 -> b8f1c2a30201, Phase 8.6 Sprint 1 — fallback 컬럼 추가 (TradeSignal·Order)` 성공
- ✅ 서버 기동: KIS 클라이언트, APScheduler, WS 연결 20개 정상 (Railway 로그 확인)
- ✅ 로그인 페이지 렌더 (Playwright): 정상 표시
- ✅ Playwright `/diagnostics` 페이지 (수동 로그인 후 확인) — `FallbackSignalRateCard`, `AutoRollbackMultiTrigger`(R1~R4+G3), 자동 롤백 배너 모두 정상 렌더 (스크린샷: `docs/phase/phase8.6/sprint1/diagnostics-prod-2026-04-29.png`)
  - 자동 롤백 배너 표시: `auto_rollback_2d_zero_signals` (2026-04-28 16:10 KST 발동 = Phase 8.5 분기 D 기존 발동, Sprint 1 가드레일이 정확히 시각화 중)
  - R3은 `AUTO_ROLLBACK_R3_ENABLED=False` 정상 표시 (Sprint 2까지 의도된 비활성)

#### 수동 검증 필요 항목

- ⬜ Paper 모드 1거래일 회귀: `signals.fallback=true` 1건 이상 DB 기록 + M-F2 API 응답 정상 (다음 거래일 2026-04-30 장 마감 후 확인 — 단, 현재 자동 롤백 발동 중이므로 폴백 비활성 상태. 수동으로 Redis override 해제 후 검증 필요)
- ⬜ G2/G3 가드레일 실 동작 확인: 16:10 자동 롤백 잡 + 회로차단기 counter 정상 적재 (다음 거래일 장 후 Railway 로그 확인)

배포 모드: Paper/dry_run — LIVE 전환은 Sprint 2 DoR 4종 통과 후

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
