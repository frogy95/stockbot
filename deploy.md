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

#### Phase 8.5 5거래일 관찰 누적 (2026-04-23 ~ 2026-04-29)

> 관찰 기준: Phase 8.5 Sprint 2 배포(v2.6.1, 2026-04-23) 이후 5거래일.
> 거래일: 04-23(목), 04-24(금), 04-27(월), 04-28(화), 04-29(수).
> 수집 방법: `curl -s "https://api.stockbot.choiji.kr/api/v1/health/observation-daily?date=YYYY-MM-DD"` (관측 전용 unauth API).

| 거래일 | 신호 수(M-S1) | tier(M-S3) | 폴백 발동(M-F1) | 자동 롤백(M-R) | 비고 |
|--------|--------------|------------|----------------|--------------|------|
| 04-23 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | 배포일 |
| 04-24 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | |
| 04-27 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | |
| 04-28 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | |
| 04-29 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | ⬜ 미수집 | |
| **합계** | M-S1= | M-S3= | M-F1= 일 | M-R= | |

**부수 관찰**

- ✅ Paper 핫픽스 0건 — `git log --since=2026-04-23 --oneline | grep hotfix` 결과 0건 (로컬 기준)
- ⬜ 09:00 일일 리스크 카운터 초기화 로그 5일 연속 — 로그 조회 필요
- ⬜ 장중 OHLC 파싱 경고율 < 1% — 로그 조회 필요
- ⬜ WS 재연결/일일 리포트 중복 발송 재발 없음 — 로그 조회 필요

**수집 방법**

hotfix `observation-daily-api` 배포 후 단일 호출로 6개 지표 수집:

```bash
curl -s "https://api.stockbot.choiji.kr/api/v1/health/observation-daily?date=2026-04-24"
```

응답 예시:
```json
{
  "date": "2026-04-24",
  "signals": {"gap_open": 0, "prev_high": 0, "prev_close": 0, "other": 0, "total": 0},
  "fallback": {"triggered_count": 0, "codes": []},
  "rollback": {"is_active": false, "triggered_at": null, "reason": null}
}
```

---

## 참고

- 검증 원칙: `.claude/rules/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `.claude/rules/dev-process.md` 섹션 6.4
- 5거래일 관찰 의사결정 트리: `docs/phase/phase8.5/sprint2.5/sprint2.5.md` § 5거래일 관찰 종료 후 의사결정 트리
