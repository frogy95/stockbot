# Hotfix: ETF 수집 실패 시 이전 커밋 유실 방지

**브랜치:** `hotfix/etf-per-item-commit`
**담당자:** ChoiJiSeon
**리뷰어:** ChoiJiSeon
**상태:** ✅ 배포 완료
**배포일:** 2026-04-02

---

## 문제 분석

### 증상
`collect_etf_prices`에서 280개 ETF 수집 중 3개 항목이 DB 저장에 실패할 경우, 성공한 277개까지 모두 DB에 반영되지 않는 문제.

### 원인
루프 내에서 각 항목의 `_save_etf_price` 호출 후 커밋 없이 계속 진행하다가, 마지막에 `if collected > 0: await self._db.commit()` 한 번만 호출하는 구조였음. 중간에 예외 발생 시 `rollback()`이 그 시점까지의 모든 미커밋 데이터를 취소하여 이전 성공 항목도 손실됨.

### 영향 범위
- ETF 시세 수집 전체 (최대 280개 항목)
- 소수 종목 API 오류 발생 시 전체 수집 결과가 DB에 미반영되어 스크리닝/매매 데이터 부재

---

## 수정 내용

### 변경 파일
| 파일 | 변경 내용 |
|------|----------|
| `backend/modules/collector/sources/kis_collector.py` | 각 항목 저장 성공 후 즉시 `await self._db.commit()` 호출, 마지막 일괄 커밋 제거 |
| `backend/tests/test_kis_collector.py` | commit 횟수 검증을 1회→아이템 수로 수정 |
| `backend/tests/test_phase2_sprint1_integration.py` | commit 횟수 검증을 1회→아이템 수로 수정 |

### 커밋 이력
| 해시 | 메시지 | 날짜 |
|------|--------|------|
| `284f3d5` | fix(etf-collector): ETF 수집 실패 시 이전 커밋 유실 방지 — 아이템당 개별 커밋으로 변경 | 2026-04-02 |

---

## 검증

### 자동 검증
- ETF 관련 테스트 54개 통과
- 아이템당 commit 횟수 검증 (call_count == 아이템 수) 통과

### 수동 검증
- ⬜ Railway 배포 후 ETF 시세 수집 로그에서 개별 커밋 동작 확인

---

## PR
- **URL:** (PR 생성 후 업데이트)
- **대상:** main
- **역머지:** ✅ develop에 역머지 완료
