# Phase 4.5 API 개발자 검토 리포트 — 윤에이피

> **검토일**: 2026-04-01
> **검토 대상**: 장전 수집 장애 안정화 Phase 4.5 아키텍처 초안

---

## 1. 요약

| 항목 | 판정 |
|------|------|
| Redis 상태 영속화 | ✅ 통과 — 키 설계 명확히 정의 필요 |
| 수동 파이프라인 API | ✅ 통과 — 기존 개별 trigger 재활용 가능 |
| health check 강화 | ⚠️ 주의 — Railway 자체 health check와 연동 필요 |
| 스케줄 의존성 구현 방식 | ⚠️ 주의 — 직접 호출 체인 방식 권장 |

## 2. 항목별 검증 결과

### Redis 상태 영속화
- **키 설계 권고**:
  - `scheduler:last_premarket` → ISO 형식 타임스탬프
  - `scheduler:last_etf` → ISO 형식 타임스탬프
  - `scheduler:last_primary_screen` → ISO 형식 타임스탬프
  - `scheduler:pipeline_healthy` → `"true"` / `"false"`
  - `scheduler:pipeline_status` → JSON (각 단계별 성공/실패/미실행 상태)
- **TTL**: 상태값은 24시간 TTL 설정 (다음 날 장전에 자동 만료 → 기본값 false로 시작)
- **기존 Redis 키**와의 충돌 없음 확인 (`scheduler:` prefix 사용)

### 스케줄 의존성 구현
- **권고 방식**: APScheduler의 listener가 아닌, **선행 확인 가드** 방식 권장
  - 이유: 기존 CronTrigger job을 유지하면서 최소 변경으로 구현 가능
  - 각 job 시작 시 `scheduler:pipeline_status`에서 선행 단계 상태 확인
  - 선행 실패 → 현재 job 스킵 + 로그 + 텔레그램 알림
- **장전 파이프라인 오케스트레이터**: 별도의 `_premarket_pipeline` 메서드로 순차 실행
  - 수동 트리거 시에만 사용, 자동 스케줄은 기존 CronTrigger 유지

### health check 강화
- **현재**: `/health`는 DB + Redis만 체크
- **권고**: `/health/readiness` 추가 — DB + Redis + 스케줄러 running + pipeline_healthy
  - Railway health check URL을 `/health/readiness`로 설정
  - 기존 `/health`는 liveness 용도로 유지

### 수동 파이프라인 API
- **기존 재활용**: `trigger_premarket`, `trigger_primary_screening`, `trigger_etf_master`, `trigger_etf` 등 이미 존재
- **신규 추가**: `POST /collector/trigger/premarket-pipeline` — 순차 실행 오케스트레이터
  - 실행 순서: premarket → etf_master → primary_screen → etf → dart → sentiment
  - 각 단계 결과를 응답에 포함
  - BackgroundTasks로 비동기 실행 + 상태 폴링 방식 (긴 실행 시간 대응)

## 3. 파라미터 조정 권고

| 항목 | 원래 설계 | 권고값 | 근거 |
|------|----------|--------|------|
| Redis 상태 TTL | 미지정 | **24시간 (86400초)** | 매일 장전에 갱신, 전일 상태 자동 만료 |
| health readiness 엔드포인트 | 없음 | **`/health/readiness`** | Railway health check 연동 |
| pipeline_status JSON 구조 | 없음 | **단계별 {status, timestamp, error}** | 프론트엔드 스테퍼 UI 데이터 |

## 4. 리스크

- 파이프라인 순차 실행은 긴 실행 시간 → BackgroundTasks + 폴링 패턴 필수
- Railway의 기본 요청 타임아웃 확인 필요
