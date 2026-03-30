# Phase 4 전문가 검토 -- 윤에이피 (API 개발자)

> **검토일**: 2026-03-31
> **검토 대상**: Phase 4 웹 대시보드 (MVP) 아키텍처 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| 기존 API 재활용 | ✅ 통과 |
| 신규 API 필요 목록 | ⚠️ 주의 |
| CORS 설정 | ❌ 재검토 |
| 인증 미들웨어 | ⚠️ 주의 |
| 실시간 업데이트 | ✅ 통과 |
| API 응답 시간 | ✅ 통과 |

---

## 2. 항목별 검증 결과

### 기존 API 재활용 (✅ 통과)
Phase 3까지 구현된 API가 대시보드 백엔드의 대부분을 커버한다:

| 대시보드 페이지 | 기존 API | 상태 |
|----------------|---------|------|
| 메인 대시보드 | `/trading/risk-status`, `/trading/engine-status`, `/trading/positions`, `/trading/history` | ✅ 조합 사용 |
| 포지션 | `/trading/positions` | ✅ 그대로 사용 |
| 주문 현황 | `/trading/orders` | ✅ 그대로 사용 |
| 매매 신호 | `/trading/signals` | ✅ 그대로 사용 |
| 스크리닝 | `/screening/primary`, `/screening/secondary` | ✅ 그대로 사용 |
| 매매 이력 | `/trading/history` | ✅ 그대로 사용 |
| 설정 | `/settings` | ✅ 그대로 사용 |
| 수집 상태 | `/collector/status` | ✅ 그대로 사용 |

### 신규 API 필요 목록 (⚠️ 주의)
기존 API만으로는 부족한 부분이 있다. **신규 구현 필요**:

1. **인증 API** (신규):
   - `POST /api/v1/auth/login` -- 로그인 (JWT 발급)
   - `POST /api/v1/auth/refresh` -- 토큰 갱신
   - `GET /api/v1/auth/me` -- 현재 사용자 정보 + 환경 정보

2. **대시보드 집계 API** (신규):
   - `GET /api/v1/dashboard/summary` -- 메인 대시보드용 집계 (오늘 손익, 거래 건수, 보유 종목 수, 엔진 상태, 리스크 상태를 한번에)
   - 기존 API 4~5개를 개별 호출하면 초기 로딩이 느려진다. 집계 API 1개로 통합 권고.

3. **웹 매매 승인 API** (신규):
   - `POST /api/v1/trading/signals/{signal_id}/approve` -- 웹 승인
   - `POST /api/v1/trading/signals/{signal_id}/reject` -- 웹 거부
   - 텔레그램 승인과 동일한 `trading_engine.approve_signal()` / `reject_signal()` 호출
   - 승인 토큰 검증 포함

4. **모드 전환 API** (신규):
   - `POST /api/v1/settings/mode/trading-env` -- 모의/실전 전환 (이중 확인 필요)
   - `POST /api/v1/settings/mode/trading-mode` -- 반자동/완전자동 전환
   - 장중 차단 + 포지션 체크 로직 포함

5. **설정 변경 이력 API** (신규):
   - `GET /api/v1/settings/audit-log` -- 설정 변경 이력 조회

### CORS 설정 (❌ 재검토)
현재 `allow_origins=["http://localhost:3000"]`만 설정. **프로덕션 배포 시 반드시 추가**:

```python
allow_origins=[
    "http://localhost:3000",           # 로컬 개발
    "https://stockbot.choiji.kr",      # 프로덕션 Vercel
    f"https://{VERCEL_PREVIEW_URL}",   # Vercel 프리뷰 (선택)
]
```

환경변수 `ALLOWED_ORIGINS`로 관리하고 `.env`에서 설정하도록 변경 권고.

### 인증 미들웨어 (⚠️ 주의)
현재 모든 API가 인증 없이 접근 가능하다. 인증 미들웨어 추가 시:
- `/api/v1/auth/login`은 인증 제외
- `/api/v1/health`는 인증 제외 (헬스체크)
- `/api/v1/telegram/webhook`은 인증 제외 (텔레그램 서버에서 호출)
- 나머지 모든 API는 JWT 인증 필수

`api/deps.py`에 `get_current_user` 의존성 추가 권고.

### 실시간 업데이트 (✅ 통과)
폴링 5초 방식 적절. 구현 시 주의:
- 프론트엔드에서 `setInterval` 대신 React Query/SWR의 `refetchInterval` 사용 권고
- 탭 비활성화 시 폴링 중단 (불필요한 서버 부하 방지)
- 에러 시 백오프 (연속 실패 시 폴링 간격 증가)

### API 응답 시간 (✅ 통과)
현재 API는 DB 단순 조회가 대부분이라 95th < 500ms 충족 가능. 주의 사항:
- `dashboard/summary` 집계 API는 여러 테이블을 조회하므로 Redis 캐싱 고려 (TTL 5초)
- 스크리닝 결과는 이미 Redis 캐시 적용

---

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 권고값 | 근거 |
|------|----------|--------|------|
| CORS origins | localhost만 | **환경변수 기반 다중 origin** | 프로덕션 필수 |
| 대시보드 API | 개별 호출 | **집계 API 1개 추가** | 초기 로딩 최적화 |
| 인증 제외 경로 | 없음 | **health, login, telegram/webhook** | 필수 접근 허용 |
| 폴링 라이브러리 | 미지정 | **SWR 또는 React Query** | 캐시/재검증/탭 비활성화 관리 |
| 신호 페이지 폴링 | 5초 | **3초** (승인 대기 시) | UX 반응성 (한유엑 권고 동의) |

---

## 4. 리스크 및 대안

1. **신규 API 5건이 Sprint 1에 집중**: 인증 + 대시보드 집계 + CORS가 Sprint 1에서 해결되어야 Sprint 2가 원활하다. Sprint 1 초반 Task로 배치 권고.
2. **텔레그램 웹훅과 웹 승인 경쟁 조건**: 동일 신호에 대해 텔레그램과 웹에서 동시 승인할 수 있다. Redis 기반 일회용 토큰으로 중복 승인 방지 필요 (기존 ApprovalManager 활용).
3. **환경변수 추가**: `ALLOWED_ORIGINS`, `JWT_EXPIRY_HOURS` 등 새 환경변수가 필요하다. `.env.example` 업데이트 필수.
