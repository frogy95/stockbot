# Phase 2 전문가 검토 — 윤에이피 (API 개발자)

**검토일**: 2026-03-29
**검토 대상**: Phase 2 데이터 수집 시스템 API 연동 설계

---

## 요약

| 항목 | 판정 |
|------|------|
| 공공데이터포털 연동 | ✅ 통과 — 6회 호출 검증 완료 |
| 한투 WS 파싱 | ⚠️ 주의 — tr_id별 필드 매핑 필요 |
| WS 구독 관리 | ⚠️ 주의 — 경쟁 조건 방지 필요 |
| DART corp_code | ⚠️ 주의 — 93MB XML 파싱 최적화 필요 |
| Phase 1 미해결 #13 | ❌ 재검토 — WS None 가드 반드시 해결 |
| APScheduler 설정 | ⚠️ 주의 — misfire_grace_time 필요 |

---

## 항목별 검증 결과

### 1. 공공데이터포털 연동 (✅)

Phase 0.5 검증 완료. 6회 호출(500건/페이지)로 ~2,880종목 수집, 3.7초 소요. 일 1,000건 한도 내 충분.

**주의점**:
- 페이지네이션: `totalCount` 변동 가능 → 동적 페이지 수 계산
- 응답 포맷: XML → `xmltodict` 또는 JSON 파라미터 (`resultType=json`)
- 공휴일: 전일 데이터 미갱신 → `basDt` 파라미터로 최신 영업일 조회

### 2. 한투 WS 데이터 파싱 (⚠️)

Phase 1에서 raw 데이터만 전달. Phase 2에서 파싱 구현:
- `H0STCNT0` (체결): 파이프(|) 구분 40개 필드
- `H0STASP0` (호가): 파이프(|) 구분 60개+ 필드
- 필드 순서는 한투 문서 기반으로 매핑 테이블 구축
- 파싱 실패 시 해당 메시지 스킵 + 로그 경고 (전체 중단 방지)

### 3. WS 구독 관리 (⚠️)

1차 스크리닝 결과 변경 시 동적 구독 추가/제거:
- asyncio.Lock으로 동시 구독 변경 방지
- 구독 추가 전 현재 구독 수 확인 (35종목 상한)
- 스크리닝 주기마다 diff 계산 → 최소 변경

### 4. DART corp_code 매핑 (⚠️)

corpCode.xml (~93MB, ~80,000개 법인):
- 서버 기동 시 1회 다운로드 + 파싱 → `corp_codes` 테이블 저장
- `stock_code` (종목코드) ↔ `corp_code` (법인코드) 매핑
- 분기 1회 갱신 (재무제표 발표 시기에 맞춤)
- zipfile 내 XML → `xml.etree.ElementTree` 파싱 (메모리 효율)

### 5. Phase 1 미해결 #13 (❌)

`kis_ws.py`의 `subscribe`/`unsubscribe`에서 `self._ws is None` 체크 미구현:
```python
async def subscribe(self, stock_code: str, tr_id: str = "H0STCNT0") -> None:
    if self._ws is None:
        raise ConnectionError("WebSocket 미연결. connect()를 먼저 호출하세요.")
    ...
```
**반드시 Sprint 1에서 해결**.

### 6. APScheduler 설정 (⚠️)

```python
scheduler = AsyncIOScheduler(
    job_defaults={
        'misfire_grace_time': 60,  # 60초 지연까지 허용
        'coalesce': True,          # 누적 실행 방지
        'max_instances': 1,        # 동시 실행 방지
    }
)
```

---

## 파라미터 조정 권고

| 항목 | 원래 설계 | 권고값 | 근거 |
|------|----------|--------|------|
| WS 구독 상한 | 40 (한투 제한) | 35 (운영 상한) | 후보 30 + 보유 5 |
| WS 파싱 우선 | 미정 | H0STCNT0, H0STASP0 | 체결/호가 2종 먼저 |
| misfire_grace_time | 미설정 | 60초 | 시스템 부하 대응 |
| corp_code 갱신 | 미설정 | 분기 1회 | 재무제표 시기 |
| 공공데이터 응답형식 | 미명시 | JSON (resultType=json) | 파싱 편의 |

---

## 리스크 및 대안

- 공공데이터포털 API 응답 지연(3초+) 시: 비동기 호출 + 전체 타임아웃 30초
- 한투 WS 필드 순서 변경 가능성: 하드코딩 대신 설정 파일에서 매핑 관리
- DART API 일 10,000건 한도: 전 종목 재무 조회 시 한도 초과 가능 → 1차 스크리닝 통과 종목만 조회 (최대 30건)
