# Hotfix: kospi200-real-200-backfill

**브랜치:** `hotfix/kospi200-real-200-backfill`
**담당자:** ChoiJiSeon
**리뷰어:** hotfix-close agent
**상태:** 🟡 구현 완료, 머지·배포 대기 (Kill switch 기본 비활성)
**등재일:** 2026-05-06

---

## 배경

선행 핫픽스 [`hotfix-kospi200-master-backfill`](../kospi200-master-backfill/hotfix.md) (2026-05-06 배포)에서 다음 부채가 남았다.

1. **정적 백업 200종 중 production 매칭 52종 그침**: `backend/data/kospi200_static_backup.json`은 파일 자체 주석에 `"sample top 50 + placeholder pad to 200"`이라 명시. 마이그레이션 `e5a7c91d4f08` 적용 후 `stocks.is_kospi200=true`는 52종에 그침 (production 확인: 5/6 KST 09:50).
2. **`ATR_COVERAGE_GAP_MAX=200` 일시 상향 잔존**: 선행 핫픽스가 "일봉 백필 완료 후 30 원복"을 명시했으나, 그 일봉 백필 작업이 어떤 Sprint·hotfix·backlog에도 등재되지 않음.

---

## 검증으로 도출된 해결 경로 변화

당초 계획(B안: 한투 API 호출)은 검증 결과 **부적합** 판정:
- `/uapi/etfetn/v1/quotations/inquire-component-stock-price` (TR `FHKST121600C0`)는 KODEX 200 ETF 구성종목을 1회 30종만 반환, 페이지네이션 미지원 → KOSPI200 200종 전체 조회 불가.

**채택안 = D안 (KIS kospi_code.mst 파싱)** 검증 결과:
| 항목 | 결과 |
|------|------|
| KOSPI200 멤버십 위치 | Part2(`line[-228:]`, CP949 디코딩 후) char position **162** |
| 'Y' 카운트 (production mst) | **226종** (공식 200 + 보통주 ~26) |
| 잘 알려진 KOSPI200 적중 | 15/15 (정밀도 100%) |
| 비KOSPI200 false positive | 0/4 |
| 우선주 비중 | 0종 (보통주 226종) |
| `stocks` 매칭률 | **226/226 = 100%** → 일봉 백필 불필요 |
| CP949 디코딩 실패 | 0/1798 lines |

**핵심 발견**: 226종 모두 production stocks 테이블에 이미 존재 → 별도 일봉 백필 작업 불필요. 일봉은 일일 수집 잡으로 자연 적재.

---

## 수정 내용

### 변경 파일
| 파일 | 변경 |
|------|------|
| `backend/core/config.py` | `KOSPI200_MST_SYNC_ENABLED: bool = False` 환경변수 추가 (kill switch) |
| `backend/modules/collector/sources/kis_master.py` | `parse_kospi200_codes()`, `kospi200_sanity_check()`, `sync_kospi200_membership()`, `_maybe_sync_kospi200()` 신설. `collect()` 메서드 끝에서 게이트 후 호출. ETF mst 다운로드 1회로 양 작업 처리 |
| `backend/tests/test_kis_master.py` | KOSPI200 파싱 + sanity + 게이트 동작 + 마킹 카운트 검증 10종 추가 |
| `.env.example` | `KOSPI200_MST_SYNC_ENABLED=false` 문서화 |

### Kill switch 설계 이유

5/7 ATR 잡(KST 08:35) 관찰의 가설 = **"5/6 운영 조치(is_kospi200=52, ATR_COVERAGE_GAP_MAX=200, fallback_count=0)만으로 ATR 잡이 정상화되는가?"**. 본 핫픽스 구현이 5/7 잡 이전에 활성화되면 stocks.is_kospi200이 52→226으로 변동, 관찰 신호 격리 불가.

→ 코드는 머지·배포하되 `KOSPI200_MST_SYNC_ENABLED=false` (default)로 잡이 no-op. 5/7 16:00 관찰 종료 후 Railway env를 `true`로 토글 → 5/8 08:35 ETF mst 잡(08:10)이 KOSPI200 sync 동시 수행.

### Sanity 게이트 (회귀 안전장치)

WebFetch로 받은 KIS 공식 컬럼 매핑이 부정확했고, pos 162의 정식 명칭은 미확인 (실증으로만 KOSPI200 멤버십 확정). KIS가 mst 스키마 변경 시 pos 162 의미 변동 가능 → 매 sync 전:
1. **카운트 범위**: 150 ≤ count ≤ 280
2. **Spot check**: {005930, 000660, 005380, 035420, 035720} 모두 포함

실패 시 sync 차단(직전 상태 유지, 텔레그램 알림은 후속 작업으로). `is_kospi200`은 직전 값 그대로 유지.

### 정적 백업 JSON

`backend/data/kospi200_static_backup.json`은 mst 다운로드 장애 폴백 용도로만 유지. 별도 갱신 작업 없음.

---

## 검증

### 자동 검증
- ✅ pytest tests/test_kis_master.py: 39 passed (10 신규, 29 기존, 0.13초)
- ⬜ pytest 전체 회귀 (실행 중, 결과는 deploy.md에 기록 예정)
- ✅ 변경 파일 라인 수: ~80줄 (Hotfix 기준 50줄 초과하나 50% 신규 테스트 + 단일 모듈 변경, hotfix 적합)
- ✅ DB 스키마 변경 없음 (`is_kospi200` 컬럼은 선행 핫픽스에서 추가됨)
- ✅ 새 의존성 없음

### 수동 검증 (배포 후, 5/7 16:00 이후 활성화 시)
- ⬜ Railway 환경변수 `KOSPI200_MST_SYNC_ENABLED=true` 설정
- ⬜ 다음 영업일 08:10 ETF mst 잡 로그: `KOSPI200 sync 완료: codes=226, marked=226`
- ⬜ production DB: `SELECT COUNT(*) FROM stocks WHERE is_kospi200` ≈ 226
- ⬜ 후속 ATR 잡(08:35) 결과: `metrics:atr:dist:{date}.sample_n ≈ 200+`, `safe_mode:active = None`
- ⬜ Railway 환경변수 `ATR_COVERAGE_GAP_MAX=30` 원복 (KOSPI200 sync 검증 후)

---

## 운영 절차 (5/7 이후)

```bash
# 1) 5/7 16:00 — ATR 잡 관찰 결과 확인 (observation 에이전트)
# 2) Sprint 3 GO/NO-GO 판정 후 본 hotfix kill switch 활성화
railway variables set KOSPI200_MST_SYNC_ENABLED=true --service stockbot
# 3) 다음 영업일 08:10 ETF mst 잡에서 자동 동작 (별도 cron 등록 불필요)
# 4) 08:35 ATR 잡에서 226종 표본으로 정상 캘리브레이션 확인
# 5) 1~2영업일 정상 동작 후:
railway variables set ATR_COVERAGE_GAP_MAX=30 --service stockbot  # 임시 상향 원복
```

---

## PR
- **URL:** (push 후 업데이트)
- **대상:** main
- **역머지:** ⬜ develop 역머지 필요
