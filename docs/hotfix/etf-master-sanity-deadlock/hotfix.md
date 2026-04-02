# Hotfix: ETF 마스터 sanity check 데드락 수정

**브랜치:** `hotfix/etf-master-sanity-deadlock`
**담당자:** frogy95
**리뷰어:** hotfix-close agent
**상태:** ✅ 배포 완료
**배포일:** 2026-04-02

---

## 문제 분석

### 증상
- ETF 마스터 수집이 반복 실패하면서 ETF 시세 수집도 skip되고, 텔레그램 실패 알림 반복

### 원인
프로덕션 DB에 ETF/ETN이 277개(비정상 상태)인 상황에서 mst 파일에서 878개가 파싱되면,
`|878-277|/277 = 217% > 30%`로 sanity check 실패 → fallback(기존 DB 유지) → 다음 실행에서도 동일 조건 반복 → **데드락 구조**

### 영향 범위
- ETF 마스터 수집 전면 실패 (08:10 스케줄 매번 skip)
- ETF 시세 수집 skipped (etf_master status="failed" 의존)
- 텔레그램 실패 알림 반복 발생

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_master.py` | sanity_check의 ±30% 변동 비교를 prev_count >= 500일 때만 적용. prev_count < 500이면 "복구 모드"로 간주하여 최소 200 + spot-check만 통과하면 적재 허용 |
| `backend/tests/test_kis_master.py` | 기존 테스트 prev_count 기준 업데이트 + 데드락 복구 시나리오 테스트 추가 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `5d1837c` | fix(collector): ETF 마스터 sanity check 데드락 복구 모드 추가 | 2026-04-02 |

---

## 검증

### 자동 검증
- ✅ pytest 603 passed, 0 failed

### 수동 검증
- ⬜ 배포 후 ETF 마스터 수동 트리거 (POST /api/v1/collector/trigger/etf-master) → sanity check 통과 확인
- ⬜ ETF 시세 수동 트리거 (POST /api/v1/collector/trigger/etf) → 수집률 50%+ 확인
- ⬜ pipeline-status에서 etf_master status="success" 확인

---

## PR
- **URL:** https://github.com/frogy95/stockbot/pull/60
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
