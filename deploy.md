# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### Phase 4.6 Sprint 2: 데이터 품질 + KODEX 필터 + 통합 검증 (2026-04-02)

포함 스프린트: Phase 4.6 Sprint 2
PR: https://github.com/frogy95/stockbot/pull/62

#### 코드 리뷰 결과 (2026-04-02)

- ✅ 코드 리뷰 완료 — Critical/High 이슈 없음
- Medium 이슈 1건: `trading_calendar.py` 2026년 공휴일 하드코딩 — 2027년 이후 날짜 유입 시 공휴일 미인식. Phase 5에서 개선 예정. phase4.6.md 미해결 사항 테이블에 기록됨.

#### 자동 검증 결과 (2026-04-02)

- ✅ Docker 환경: backend/frontend/postgres/redis 모두 실행 중
- ✅ health check: http://localhost:8000/docs 200, http://localhost:3000 307
- ✅ pytest 전체: **631 passed**, 0 failed (54 warnings — 기존 RuntimeWarning, 버그 아님)
- ✅ Sprint 2 관련 테스트 25개 전체 PASS:
  - trading_calendar 단위 (12개)
  - DB 후검증 단위 (5개)
  - 통합 테스트 6개 시나리오 (7개)
  - KODEX 필터 통합 (1개)
- ✅ /api/v1/health: `{"status": "healthy", "database": "connected", "redis": "connected"}`
- ✅ /api/v1/collector/status: scheduler 실행 중, 11개 job 등록 확인

#### 수동 검증 필요 항목

- ✅ /api/v1/health 헬스체크 확인 — 로컬 Docker 기준 통과
- ⬜ Railway 배포 후 KODEX ETF 시세 수집 확인 — 장중 로그에서 "KODEX ETF 수집 대상: ~280종목" 확인
- ⬜ scheduler 상세 로깅 확인 — 수집 완료 로그에 step/collected/failed/total/validation 포함 여부
- ⬜ DB 후검증 경고 로그 미발생 확인 (정상 수집 시 WARNING 없음)

#### Phase 문서 반영 상태

- ✅ phase4.6/phase4.6.md Sprint 분할 테이블: Sprint 1/2 ✅ 표시 추가
- ✅ phase4.6/phase4.6.md Sprint 2 상세 섹션 제목: ✅ 완료 표시 추가
- ✅ phase4.6/phase4.6.md 완료 기준 테이블: Sprint 1/2 완료 항목 상태 업데이트
- ✅ phase4.6/phase4.6.md 미해결 사항 테이블: 항목 6 (휴장일 하드코딩) 해결 표시, 항목 13 신규 추가 (trading_calendar 2027년 미대응)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
