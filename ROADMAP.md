# 프로젝트 로드맵 - StockBot (한국 주식/ETF 단타 자동 매매 시스템)

> 이 파일은 프로젝트 전체 진행 상황의 Single Source of Truth입니다.
> - **prd-to-roadmap** 에이전트가 PRD를 기반으로 초기 로드맵을 생성합니다.
> - **sprint-close** 에이전트가 스프린트 완료 시 상태를 업데이트합니다.
> - Phase/Sprint 구조는 `docs/phase/phase{N}/phase{N}.md`, `docs/phase/phase{P}/sprint{N}/sprint{N}.md`와 연동됩니다.

## Phase 데이터 의존성 관리 원칙

> **경고**: 이 원칙은 Phase 7.0 이후 모든 계획/착수 시 반드시 준수해야 합니다.

1. **선행 데이터 수집 의무**: 후속 Phase가 역사적/누적 데이터를 필요로 하면, **이전 Phase에서 해당 수집 파이프라인을 선행 구축**하여 착수 시점에 이미 데이터가 충분히 축적되어 있어야 한다.
2. **명시적 축적 기간**: 각 Phase 문서에 "필요 선행 데이터"와 "최소 축적 기간"을 명시한다.
3. **착수 경고 의무**: 데이터 축적이 미완인 상태에서 Phase 착수 지시를 받으면 AI가 **반드시** 다음을 경고한다:
   - 현재 축적 데이터 수준
   - 최소 필요 수준
   - 착수 시 예상 리스크 (과적합, 통계 유의성 부족, 실전 손실)
   - 권장 대기 기간
4. **명시적 Override**: 경고 후 사용자가 "그래도 진행"을 명시하면 진행하되, **제약 조건을 Phase 문서에 기록**한다.

### 데이터 의존성 맵

```
Phase 6.2 ──(코드)──> Phase 7.0 (데이터 축적 불필요, 즉시 착수)
Phase 6.1 ──(5분봉 Redis 수집 시작)──> Phase 7.1 (min 20거래일)
Phase 7.1 ──(시간대별 DB + VWAP 수집 시작)──> Phase 8 (min 20거래일)
Phase 8 ──(VWAP 엔진 + 백테스트 데이터셋)──> Phase 9 (min 3~6개월)
```

| Phase | 필요 선행 데이터 | 최소 축적 | 수집 시작 Phase | 경고 기준 |
|-------|-----------------|----------|---------------|----------|
| 7.0 | 없음 (코드 결함 수정) | 즉시 착수 | - | - |
| 7.1 | 5분봉 거래량 (Redis) | 20거래일 | 6.1 | <20거래일 |
| 8 | 시간대별 거래량 DB + VWAP 틱 | 20거래일 | 7.1 | <20거래일 |
| 9 | 실전 운영 데이터 전체 | 3~6개월 | 7.1 (DB), 8 (VWAP) | <3개월 |

---

## 개요

- **목표**: 한국 주식/ETF 시장에서 자동 종목 스크리닝, 매매 신호 분석, 주문 실행을 수행하는 단타 자동 매매 시스템 구축
- **기술 스택**: Python 3.12(FastAPI) + Next.js(App Router) + PostgreSQL 16 + Redis 7 + Docker Compose
- **인프라**: Vercel (프론트엔드) + Railway (백엔드 + DB + Redis) + Cloudflare (도메인)
- **팀 규모**: 1인 개발

## 진행 상태 범례

- ✅ 완료
- 🔄 진행 중
- 📋 예정
- ⏸️ 보류

## 프로젝트 현황 대시보드

- 전체 진행률: Phase 0~7.0.1 Sprint 1 완료
- 현재 Phase: Phase 8 (즉시 착수 개선 통합) — Phase 7.0 Sprint 3 선행 조건
- 현재 Sprint: Phase 8 Sprint 1 🔄 진행 중 — 장중 OHLC 데이터 파싱 수정 + 갭 분기 버그 수정 (구 Phase 7.2 Sprint 1 흡수, 계획 수립 2026-04-20)
- 완료된 스프린트: Phase 0.5 Sprint 1 (2026-03-29), Phase 1 Sprint 1 (2026-03-29), Phase 1 Sprint 2 (2026-03-29), Phase 2 Sprint 1 (2026-03-29), Phase 2 Sprint 2 (2026-03-29), Phase 2 Sprint 3 (2026-03-30), Phase 2.5 Sprint 1 (2026-03-30), Phase 2.6 Sprint 1 (2026-03-30), Phase 3 Sprint 1 (2026-03-30), Phase 3 Sprint 2 (2026-03-30), Phase 3 Sprint 3 (2026-03-31), Phase 4 Sprint 1 (2026-03-31), Phase 4 Sprint 2 (2026-03-31), Phase 4.5 Sprint 1 (2026-04-01), Phase 4.6 Sprint 1 (2026-04-02), Phase 4.6 Sprint 2 (2026-04-02), Phase 4.7 Sprint 1 (2026-04-02), Phase 4.8 Sprint 1 (2026-04-03), Phase 4.8 Sprint 2 (2026-04-05), Phase 4.8 Sprint 3 (2026-04-05), Phase 4.9 Sprint 1 (2026-04-06), Phase 5 Sprint 1 (2026-04-07), Phase 5 Sprint 2 (2026-04-07), Phase 5.1 Sprint 1 (2026-04-08), Phase 5.2 Sprint 1 (2026-04-08), Phase 6 Sprint 1 (2026-04-12), Phase 6 Sprint 2 (2026-04-12), Phase 6.1 Sprint 1 (2026-04-13), Phase 6.2 Sprint 1 (2026-04-14), Phase 7.0 Sprint 1 (2026-04-15), Phase 7.0 Sprint 2 (2026-04-16), Phase 7.0.1 Sprint 1 (2026-04-16)
- 프로덕션 배포: v0.5.0 (2026-03-31) — Vercel + Railway
- 다음 마일스톤: Phase 8 Sprint 1 — 장중 OHLC 파싱 수정 + 갭 분기 버그 수정
- 후속 마일스톤: Phase 7.0 Sprint 3 — E2E 검증 + LIVE 전환 게이트 (Phase 8 Sprint 1 완료 후)
- 이후 마일스톤: Phase 9 Sprint 0 — 데이터 수집 인프라 + KIS 백필 + 5분봉 가속도 (Phase 8 Sprint 1·2 완료 후 착수 가능)
- 장기 마일스톤: Phase 10 — U자형 비선형 보정 (Phase 9 Sprint 3 완료 + 2개월 축적 시 의무 착수)

### 2026-04-20 Phase 재편성
- 사용자 지시(A안 + 3개 Phase 분할)로 기존 Phase 7.1/7.2/8/9를 Phase 8/9/10으로 재편성
- Phase 7.2 확정 계획 → **Phase 8 Sprint 1·2로 흡수** (파라미터 그대로 승계)
- 기존 Phase 7.1(5분봉 가속도), 8(Z-score/VWAP) 초안 → **Phase 9로 통합** (박퀀트 권고: 지표 상관관계 관리)
- 기존 Phase 9(U자형 비선형) 초안 → **Phase 10**으로 재편 + 백로그는 Phase 10.1로 분리
- 기존 초안 파일은 `docs/phase/archive/`로 이동하여 이력 보존

## 기술 아키텍처 결정 사항

| 결정 | 선택 | 이유 |
|------|------|------|
| 아키텍처 | 모놀리식 + 모듈 경계 | Vercel/Railway 분리 배포, 코드는 모듈로 분리하여 확장 대비 |
| 백엔드 | Python 3.12 + FastAPI | 비동기 지원, 금융 라이브러리 풍부 |
| 프론트엔드 | Next.js (App Router) | React 기반 SSR, 실시간 업데이트 |
| DB | PostgreSQL 16 | 시계열 + 관계형 데이터 통합 |
| 캐시 | Redis 7 | 실시간 시세, 세션, 승인 대기 큐 |
| ORM | SQLAlchemy 2.0 + Alembic | 비동기 지원, 마이그레이션 |
| 스케줄러 | APScheduler | FastAPI 내장, 크론 표현식 |
| 텔레그램 | python-telegram-bot | 웹훅, 비동기 지원 |
| 컨테이너 | Docker Compose | 로컬/서버 동일 환경 (4컨테이너: FastAPI, Next.js, PostgreSQL, Redis) |

## 의존성 맵

```
Phase 0 (완료)
  └─> Phase 0.5: 외부 API 탐색/검증
        └─> Phase 1: 개발 환경 + 한투 API 기반
              └─> Phase 2: 데이터 수집 + 종목 스크리닝
                    └─> Phase 2.5: ETF 데이터 수집 파이프라인 완성
                          └─> Phase 2.6: KIS mst 파서 올바른 구현
                                └─> Phase 3: 매매 엔진 + 기본 알림
                          ├─> Phase 4: 웹 대시보드 (MVP)
                          │     └─> Phase 4.5: 스케줄러 안정화 + 장애 복구
                          │           └─> Phase 4.6: 데이터 수집 파이프라인 근본 수리
                          │                 └─> Phase 4.7: 1차 스크리닝 스코어링 구조 수정
                          │                       └─> Phase 4.8: EOD 데이터 수집 내결함성 강화
                          │                             └─> Phase 4.9: 장전 파이프라인 복원력 강화
                          └─> Phase 5: 스크리닝 안정화 + 완전 자동 + 성과 분석
                                └─> Phase 5.1: change_rate 필터 수정
                                      └─> Phase 5.2: WS 모의 환경 안정화
                                            └─> Phase 6: 스케줄러 + WS 복원력 강화
                                                  └─> Phase 6.1: 거래량 시간가중 보정 + 5분봉 수집 구축
                                                        └─> Phase 6.2: 장전 수집 단순화 (KIS 주경로 + 포털 장후 보조)
                                                              └─(코드)─> Phase 7.0: 매매 엔진 결함 수정 + LIVE 전환
                                                                    └─(코드)─> Phase 8: 즉시 착수 개선 통합 (구 7.2 S1·S2 + 4.5 S2 + 5 S3)
                                                                          └─> Phase 7.0 Sprint 3: E2E 검증 + LIVE 전환 게이트
                                                                                └─(코드)─> Phase 9: Z-score + VWAP + 5분봉 가속도 통합
                                                                                └─(데이터 부분 완화, KIS 백필 + 점진 활성화)─> Phase 9
                                                                                      └─(코드)─> Phase 10: U자형 비선형 보정
                                                                                      └─(데이터: 2~6개월)─> Phase 10
                                                                                            └─> Phase 10.1: 누적 백로그 통합 (피라미딩, 2차 스크리닝 N=1 등)
```

> **범례**: `(코드)` = 코드 의존성 (이전 모듈/인프라 필요), `(데이터: N)` = 데이터 의존성 (최소 N 축적 필요)

- Phase 0 -> 0.5: API 검증 결과가 Phase 1 이후 아키텍처/전략 결정의 전제
- Phase 0.5 -> 1: 검증된 API 스펙 + 데이터 수집 전략(공공데이터포털 일괄 + 한투 실시간) 기반 설계
- Phase 1 -> 2: 한투 API 연동 + 공공데이터포털 수집이 스크리닝의 전제
- Phase 2 -> 2.5: 공공데이터포털 ETF 미포함 → KIS mst 파일로 ETF 마스터 적재
- Phase 2.5 -> 2.6: mst 파서 구현 오류 수정 (sanity check 항상 실패 블로커)
- Phase 2.6 -> 3: ETF 포함 완전한 수집 파이프라인이 매매 전략의 전제. 리스크 선행 -> 매매 전략 -> 텔레그램 알림 순서
- Phase 3 -> 4: 매매 데이터(포지션, 주문, 신호)가 대시보드 표시 대상
- Phase 4.6 -> 4.7: 수집 파이프라인 정상화 후 스크리닝 스코어링 구조 수정
- Phase 4.7 -> 4.8: 스크리닝 정상화 후 데이터 수집 SPOF 해소 (공공데이터포털 단일 의존 → KIS 일봉 보조)
- Phase 4.8 -> 4.9: KIS 폴백 구현 후 남은 복원력 결함 해소 (DB 기반 스크리닝 의존성 + 재시도 후 재실행)
- Phase 3 -> 5: 반자동 매매 흐름이 완전 자동의 기반
- Phase 5 -> 5.1: 1차 스크리닝 통과 0건 재발 → change_rate 필터 과도 엄격성 수정
- Phase 5.1 -> 5.2: WS 재연결 반복으로 장중 실시간 파이프라인 마비 -> 구독 수 제한 + 재연결 안정화
- Phase 4, 5, 5.1, 5.2 -> 6: MVP 기능 완성 후 고도화 (네이버 센티멘트 본격화, DART 공시 모니터링)
- Phase 6 -> 6.1: 전략 volume_ratio 단위 불일치 수정 (장중 누적 vs 전일 마감 누적 → 시간가중 보정) + 5분봉 수집 파이프라인 선행 구축
- Phase 6.1 -> 6.2: 포털 수집 타이밍 불일치(08:00 vs 정책 T+1 13시) 진단 → 재시도 조건 강화 + 14:00 보조 cron + KIS 폴백 streak 관리
- Phase 6.2 -> 7.0: **(긴급)** 매매 엔진 치명적 결함 3건 (가격 갱신 미연결, 포지션 미생성, 청산 미실행) + LIVE 전환 준비. 데이터 축적 불필요, 즉시 착수.
- Phase 7.0 Sprint 2 -> 7.0.1: **(긴급)** KIS LIVE WS 연결 실패 — ws_url 경로 누락 + Railway Static IP. Phase 7.0 Sprint 3(LIVE 전환 게이트)의 선행 조건.
- Phase 7.0 -> 8: 매매 엔진 수정 완료 후, 전략 진입 조건 개선 (구 7.2 흡수) + 관리 UI + 성과 분석 통합. Phase 7.0 Sprint 3 "신호 생성 1건+" 조건의 전제.
- Phase 8 -> 7.0 Sprint 3: Phase 8 Sprint 1(OHLC 수정) 완료 후 E2E 검증 재개 가능.
- Phase 6.1 + Phase 8 -> 9: **(코드)** 5분봉 수집 인프라 + 매매 신호 복구 완료 후 Z-score/VWAP/5분봉 가속도 통합 설계. **(데이터 완화)** 사용자 지시 재검토 결과 KIS 과거 분봉 백필 + 점진 활성화로 20거래일 대기 우회 가능.
- Phase 9 -> 10: **(코드)** 실시간 VWAP + 백테스트 데이터셋, **(데이터)** U자형 함수 피팅은 완화 불가 — 최소 2개월(대안 C), 3~6개월(본격 피팅) 필수.
- Phase 10 -> 10.1: U자형 보정 배포 + 안정 운영 3개월 이상 축적 후 백로그(피라미딩, 2차 스크리닝 하이브리드 등) 통합 처리.

## MVP 범위 (Must)

- 자동 종목 스크리닝
- 매매 신호 생성 (신뢰도 + 근거)
- 반자동 승인 (텔레그램 + 웹)
- 주문 실행 (한투 API)
- 포지션 관리
- 모의/실전 전환
- 기본 웹 대시보드

**MVP 완료 시점**: Phase 4 완료

---

## Phase 0: 프로젝트 초기 설정 (Sprint 0) ✅

### 목표
프로젝트 저장소, 에이전트 시스템, CI/CD 파이프라인, 개발 프로세스 문서화 완료.

### 작업 목록
#### Sprint 0: 프로젝트 부트스트랩
- ✅ 저장소 생성 및 브랜치 전략 설정
- ✅ Claude Code 에이전트 설정 (7개 에이전트 + 훅 시스템)
- ✅ CI/CD 파이프라인 구성
- ✅ 개발 프로세스 문서화
- ✅ 전문가 프로필 7명 정의

### 완료 기준 (Definition of Done)
- ✅ 에이전트 시스템 동작 확인
- ✅ 개발 프로세스 문서 완성

---

## Phase 0.5: 외부 API 탐색/검증 (Sprint 0~1) ✅

### 목표
프로젝트에서 사용할 외부 API 5종(한국투자증권, 네이버 검색, Open Dart, 공공데이터포털, Telegram Bot)을 실제 호출하여 검증하고, 결과에 따라 아키텍처/전략을 조정한다. 코드 품질보다 **빠른 검증과 학습**에 집중하는 탐색 Phase.

### 작업 목록
#### Sprint 1: 외부 API 5종 탐색/검증 ✅ (2026-03-29 완료)

> Sprint 계획: `docs/phase/phase0.5/sprint1/sprint1.md` (2026-03-29)

**한국투자증권 API**
- 모의거래 계정 발급 및 APP_KEY/SECRET 확보
- REST API: OAuth 토큰 발급 → 시세 조회(현재가, 호가) → 모의 주문 실행/취소
- 웹소켓: 실시간 시세 구독, 연결 안정성 테스트 (최소 30분 유지)
- Rate Limit 실측 (모의: 공식 초당 1건 vs 실제 허용치)
- 응답 구조/지연 시간 기록

**네이버 검색 API**
- 애플리케이션 등록 및 Client ID/Secret 확보
- 뉴스 검색 (종목명/코드 검색 정확도, 결과 품질)
- 응답 구조 분석 (센티멘트 분석에 활용 가능한 필드 확인)
- Rate Limit 실측 (일 25,000건 vs 실제)

**Open Dart API**
- API 키 발급
- 기업 재무정보 조회 (매출, 영업이익 등)
- 공시 검색 (최근 공시, 키워드 검색)
- 단타 매매에서의 실제 유용성 평가 (실시간성, 데이터 지연)

**공공데이터포털 API (금융위원회_주식시세정보)**
- API 키 발급 (https://www.data.go.kr)
- 시가총액, 상장주식수 데이터 조회
- 응답 구조 분석, 데이터 갱신 주기 확인
- Rate Limit 실측 (일 1,000건 vs 실제)

**Telegram Bot API**
- BotFather로 봇 생성, 토큰 확보
- 메시지 발송 + 인라인 버튼(승인/거부) 테스트
- 웹훅 수신 테스트
- 응답 지연 측정

### 산출물
- `docs/phase/phase0.5/api-test-report.md`: API별 검증 결과, 응답 구조, 제약사항, 문제점
- `docs/phase/phase0.5/architecture-decisions.md`: 검증 결과에 따른 아키텍처 조정 사항

### 완료 기준 (Definition of Done)
- 5개 API 모두 실제 호출 성공 및 응답 구조 기록
- 한투 API 모의거래 환경에서 시세 조회 + 주문 왕복 확인
- 한투 웹소켓 30분 연결 유지 테스트 완료
- API별 Rate Limit 실측값 기록
- 검증 결과 기반 아키텍처 조정 사항 문서화 (필요 시)
- **Go/No-Go 판단**: 각 API가 프로젝트 요구사항을 충족하는지 결론

### 조정 시나리오
| 발견 사항 | 조정 방안 |
|----------|----------|
| 한투 웹소켓 불안정 | REST 폴링 전략으로 전환, Phase 1 설계 변경 |
| 네이버 API 뉴스 품질 미흡 | 대체 소스 탐색 또는 센티멘트 분석 스코프 축소 |
| Dart API 단타 무관 | Phase 2에서 Dart 연동 제외, 스크리닝 팩터 재설계 |
| 모의거래 Rate Limit 너무 낮음 | 개발/테스트 전략 조정 (캐싱, 목 데이터 활용) |

### 기술 고려사항
- 이 Phase의 코드는 탐색용 스크립트 — Phase 1에서 프로덕션 품질로 재작성
- Python 스크립트 또는 Jupyter Notebook으로 빠르게 검증
- API 키/시크릿은 `.env`로 관리, 커밋 금지

> Phase 상세 계획: `docs/phase/phase0.5/phase0.5.md` ✅ 생성 완료 (2026-03-29)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) — 4명 검토 완료

---

## Phase 1: 개발 환경 + 한투 API 기반 (Sprint 1~2) ✅

### 목표
Docker Compose 기반 개발 환경 구축, 한투 API(REST + 웹소켓) 연동 기반 확립, 모의/실전 전환 구조 설계. 전문가 확정 항목(매매 정책) 6건 확정 완료.

### 작업 목록
#### Sprint 1: Docker Compose + DB/Redis + 백엔드 스켈레톤 ✅ (2026-03-29 완료)
> Sprint 계획: `docs/phase/phase1/sprint1/sprint1.md` (2026-03-29)

- Docker Compose 설정 (FastAPI, Next.js, PostgreSQL, Redis 4컨테이너)
- FastAPI 프로젝트 구조 (modules/, core/, api/ 디렉토리)
- DB 스키마 초기 마이그레이션 (Alembic)
- Redis 연결 및 기본 캐시 구조
- 환경변수 관리 (.env, 모의/실전 분리)
- 기본 헬스체크 API

#### Sprint 2: 한투 API 연동 + 토큰 관리 + 모의/실전 전환 ✅ (2026-03-29 완료)
> Sprint 계획: `docs/phase/phase1/sprint2/sprint2.md` (2026-03-29)

- 한투 API REST 클라이언트 (인증, 시세 조회, 주문)
- 한투 API 웹소켓 클라이언트 (실시간 시세, 호가, 체결) + 자동 재연결/재구독
- Access Token 자동 발급/갱신 (Redis 저장, 스케줄러, 1분당 1회 발급 제한 대응)
- 모의/실전 전환 (`TRADING_ENV` 플래그)
- Rate Limit 적응형 스로틀링 (기본 1.5초 + 에러 시 지수 백오프)
- 종목 코드 유효성 검증 (HTTP 200 빈 데이터 반환 대응)
- 장상태 감지 이중 체계 (시간 기반 스케줄 + `iscd_stat_cls_code` 간접 확인)
- 시장 어댑터 패턴 (base.py + korea.py)

### 완료 기준 (Definition of Done)
- Docker Compose로 4컨테이너 정상 기동
- 한투 API 모의거래 환경에서 시세 조회 + 주문 전체 라이프사이클(실행/체결/취소) 테스트 성공
- 웹소켓으로 실시간 시세 수신 확인 + 재연결/재구독 자동화
- `TRADING_ENV` 전환 시 도메인/키/tr_id/WS포트 일괄 변경 확인
- Rate Limit 적응형 스로틀링 동작 확인
- ✅ 전문가 확정 항목 6건 phase-planner에서 확정 완료 (2026-03-29)

### 전문가 확정 항목 결과 (6건, 2026-03-29)

| # | 항목 | 확정값 | 담당 |
|---|------|--------|------|
| 1 | 데이트레이딩 vs 스윙 | 데이트레이딩 전용 (당일 청산) | 김단타+최리스크 |
| 2 | 운영 시간대 | 07:30~16:00, 본매매 09:30~14:30 | 김단타 |
| 3 | 사전 정보수집 타이밍 | 08:00 공공데이터→08:05 스크리닝→08:10 한투 | 김단타+윤에이피 |
| 4 | 백테스팅 | MVP 제외, Phase 5 이후 | 박퀀트 |
| 5 | 손절/익절 | 손절 -2%, 익절 +3%, 트레일링 -1% | 최리스크+김단타 |
| 6 | 승인 타임아웃 | 장중 30초, 마감전 15초 | 김단타 |

### 기술 고려사항
- 한투 API 모의거래 체결 로직은 실전과 다름 (김단타 조언)
- 토큰 유효기간 ~24시간, 발급 Rate Limit 1분당 1회 → Redis 캐싱 필수 (Phase 0.5 검증)
- Rate Limit: 모의 기본 1.5초, 실전 공식 한도 70% (Phase 0.5 실측 근거)
- 잘못된 종목도 HTTP 200 반환 → 데이터 값 검증 필수 (Phase 0.5 에러 시나리오)
- 웹소켓 재연결 0.016초, 재구독 필요 (Phase 0.5 검증)
- KIS 클라이언트는 core/clients/에 배치 (수집+주문 모두 사용)
- WS 데이터 파싱/구독 관리는 Phase 2로 이동 (Sprint 2 범위 축소)

> Phase 상세 계획: `docs/phase/phase1/phase1.md` ✅ 생성 완료 (2026-03-29)
> 전문가 검토: 정프로(PO), 최리스크(리스크), 김단타(단타), 윤에이피(API), 박퀀트(퀀트) — 5명 검토 완료

---

## Phase 2: 데이터 수집 + 종목 스크리닝 (Sprint 1~3) ✅

### 목표
장전 전 종목 일괄 수집(공공데이터포털) + 장중 실시간 수집(한투 API) 2단계 수집 체계 구축. 체결강도 직접 계산 모듈 구현. 종목 스크리닝 엔진 및 스코어링. 보조 데이터(DART 재무, 네이버 센티멘트) 연동.

### 작업 목록
#### Sprint 1: 핵심 데이터 수집 ✅ (2026-03-29 완료)
> Sprint 계획: `docs/phase/phase2/sprint1/sprint1.md` (2026-03-29)

- 수집 스케줄러 (APScheduler, 장전/장중/장후)
- **장전 일괄 수집**: 공공데이터포털 → 전 종목(~2,880개) 종가/거래량/시총 DB 저장 (6회 API 호출)
- 한투 WS 데이터 파싱 (H0STCNT0 체결, H0STASP0 호가)
- **체결강도 계산 모듈**: 웹소켓 체결 데이터 기반 직접 계산 (5분 윈도우)
- WS 구독 매니저: 동적 추가/제거, 35종목 상한
- 한투 REST ETF 개별 시세 수집
- 수집 데이터 Redis 캐싱 (실시간 시세 TTL 5초)
- screening_results 테이블 추가
- 수집 실패 폴백 (3회 재시도 + 전일 데이터 + 경고)

#### Sprint 2: 종목 스크리닝 엔진 ✅ (2026-03-29 완료)
> Sprint 계획: `docs/phase/phase2/sprint2/sprint2.md` (2026-03-29)

- 1차 스크리닝 (장전, DB 기반): 거래량 200%+, 시총 500억+, 등락률 +1~+7%, 후보 30종목 상한
- 2차 스크리닝 (장중, 실시간): 체결강도 70+, 호가잔량 비율 1.2+, 3분봉 기준, 30초 주기
- 종목 스코어링 (순위 기반 백분위, 5팩터 동일 가중 20%, 상위 20% 통과)
- ETF 전용 팩터 (괴리율)
- 스크리닝 결과 DB + Redis 캐싱
- stocks 마스터 관리 + 스크리닝/수집 API

#### Sprint 3: 보조 데이터 + 통합 테스트 ✅ (2026-03-30 완료)
> Sprint 계획: `docs/phase/phase2/sprint3/sprint3.md` (2026-03-30)

- DART 재무 기초 데이터 연동 (corp_code 매핑 + 매출/영업이익)
- 네이버 뉴스 센티멘트 배치 수집 (보조 팩터, 일 1~2회)
- 전체 파이프라인 통합 테스트 (수집 → 1차 → WS → 2차 → 스코어링)

### 전문가 확정 파라미터 (2026-03-29, 5명 검토)

| # | 항목 | 확정값 | 담당 |
|---|------|--------|------|
| 1 | 1차 거래량 기준 | 전일 대비 200%+ (절대값: 주식 5만주, ETF 1만주) | 김단타 |
| 2 | 등락률 범위 | +1% ~ +7% | 김단타 |
| 3 | 후보 종목 상한 | 30종목 (스코어 상위) | 최리스크 |
| 4 | 체결강도 최소 누적 | 5분(300초), 미달 시 중립(50) | 최리스크+박퀀트 |
| 5 | 호가 잔량 비율 | 매수/매도 > 1.2 | 김단타 |
| 6 | 스코어링 정규화 | 순위 기반 백분위 | 박퀀트 |
| 7 | 모멘텀/변동성 | 3일 수익률 / ATR 5일 | 박퀀트 |
| 8 | WS 구독 상한 | 35종목 | 윤에이피+최리스크 |
| 9 | 수집 실패 폴백 | 3회 재시도 + 전일 데이터 + 경고 | 최리스크 |
| 10 | Sprint 분할 | 2 → 3 Sprint (보조 데이터 분리) | 정프로 |

### 완료 기준 (Definition of Done)
- 장전 08:00 전 종목 일괄 수집 동작 (공공데이터포털 6회 / 5초 이내)
- 장중 스케줄에 따라 후보 종목 실시간 수집 동작
- 체결강도 직접 계산 모듈 동작 확인 (5분 윈도우)
- 1차 + 2차 스크리닝 엔진이 후보 종목 리스트 + 점수 반환
- 수집 지연 < 30초 (스케줄 대비)
- Redis 캐시 적중률 확인
- Phase 1 미해결 사항 #9~#13 전부 해소

### 기술 고려사항
- **핵심 변경**: 장전 스크리닝은 공공데이터포털 일괄 수집 기반 (한투 REST 개별 호출 아님)
- 공공데이터포털 일 1,000건 한도 → 전 종목 6회로 충분 (Phase 0.5 검증)
- 체결강도: 현재가 API에서 N/A → 웹소켓 체결 누적으로 직접 계산 (Phase 0.5 발견)
- DART: 재무 데이터만 활용, 실시간 공시는 후속 Phase로 이동 (Phase 0.5 Conditional)
- 네이버: 센티멘트 배치만, 속보 용도 부적합 (대형주 외 1시간+ 지연, Phase 0.5 검증)
- ETF: 공공데이터포털 미제공 → 한투 REST 개별 조회 + 재무 팩터 제외 (괴리율만 포함)
- 스코어링 알고리즘은 단순 팩터 모델로 시작, 과적합 방지 (박퀀트 원칙)
- WS None 가드 (Phase 1 #13) 반드시 해결
- DART/네이버는 Sprint 3에 분리하여 Sprint 1~2 독립 배포 가능 (정프로 결정)

> Phase 상세 계획: `docs/phase/phase2/phase2.md` ✅ 생성 완료 (2026-03-29)
> 전문가 검토: 정프로(PO), 최리스크(리스크), 김단타(단타), 윤에이피(API), 박퀀트(퀀트) — 5명 검토 완료

---

## Phase 2.5: ETF 데이터 수집 파이프라인 완성 (Sprint 1) ✅

### 목표
공공데이터포털 ETF 미포함 문제를 해결하여 Phase 2 데이터 수집 파이프라인을 완성한다. KIS 종목 마스터파일(.mst)로 ETF/ETN 종목을 stocks 테이블에 적재하고, 기존 ETF 시세 수집 파이프라인이 정상 동작하도록 연결한다.

### 작업 목록
#### Sprint 1: ETF 마스터 수집 + 스케줄러 통합 ✅ (2026-03-30 완료)
- ✅ KIS_MST_BASE_URL 환경변수 추가
- ✅ KIS mst 파일 다운로드 + CP949 파싱 + ETF/ETN 필터링 + DB upsert + sanity check
- ✅ 시드 ETF 50종목 (최초 설치용)
- ✅ 스케줄러 통합 (08:10 마스터 갱신, 08:15 시세 수집) + 수동 트리거 API
- ✅ 통합 테스트 + 전체 회귀 검증

> Phase 문서: `docs/phase/phase2.5/phase2.5.md`
> Sprint 계획: `docs/phase/phase2.5/sprint1/sprint1.md`
> 전문가 검토: 정프로(PO), 최리스크(리스크), 윤에이피(API) — 3명 검토 완료

---

## Phase 2.6: KIS mst 파서 올바른 구현 (Sprint 1) ✅

### 목표
Phase 2.5에서 구현한 KIS 종목 마스터파일(.mst) 파서가 실제 mst 파일 구조와 다르게 구현되어 sanity check가 항상 실패하는 문제를 수정한다. 고정길이(200바이트) offset 방식을 줄바꿈 분리 방식으로, ETF 판별 필드를 offset 121 -> 61:63('EF')으로 전면 재작성한다.

### 작업 목록
#### Sprint 1: mst 파서 재작성 + 검증 ✅ (2026-03-30 완료)
- ✅ _parse_mst() 줄바꿈 분리 방식 재작성 + 상수 전체 교체
- ✅ filter_etf() 증권구분 61:63 / 'EF'/'EN' 적용
- ✅ stock_code 6자리 숫자 패턴 검증 추가
- ✅ test_kis_master.py fixture 줄바꿈 기반 재작성
- ✅ 실제 KIS mst 다운로드 sanity check 통과 검증 (sanity_passed=True, ETF=878종목)
- ✅ KOSDAQ mst offset 검증 (ETF 없음 확인) + ETN 구분값 확인 (해당 URL mst에 ETN 미포함)

> Phase 문서: `docs/phase/phase2.6/phase2.6.md`
> 전문가 검토: 정프로(PO), 최리스크(리스크), 윤에이피(API) — 3명 검토 완료

---

## Phase 3: 매매 엔진 + 기본 알림 (Sprint 1~3) ✅

### 목표
리스크/자금 관리 규칙 구현, 모멘텀 브레이크아웃 전략 기반 매매 신호 생성, 주문 실행(반자동), 포지션 관리, 텔레그램 기본 알림 및 매매 승인. 데이트레이딩 전용 당일 청산 강제.

### 작업 목록
#### Sprint 1: 리스크/자금 관리 모듈 ✅ (2026-03-30 완료)
> Sprint 계획: `docs/phase/phase3/sprint1/sprint1.md` (2026-03-30)

- 리스크 매니저 (일일 손실 한도 -3%, 비상 정지 -4%, 연속 3회 손절, 쿨다운)
- 포지션 사이저 (일반 10%, 레버리지 5%, 레버리지 최대 2개)
- 손절/익절 적용 (일반: -2%/+3%, 레버리지: -1.5%/+3%, 트레일링 -1% +2% 활성화)
- 당일 청산 강제 (14:50 시장가 매도, 14:30 이후 진입 차단)
- 시간대별 매매 정책 (09:00~09:30 관망, 골든타임, 마감 정책)
- DB 모델 생성 (trade_signals, orders, positions, trade_history)
- settings 리스크 파라미터 시드
- 리스크 설정 장중 잠금

#### Sprint 2: 매매 전략 + 주문 실행 ✅ (2026-03-30 완료)
> Sprint 계획: `docs/phase/phase3/sprint2/sprint2.md` (2026-03-30)

- Strategy ABC 인터페이스 + 모멘텀 브레이크아웃 전략
- 신호 생성 (5분봉 전일 고가 돌파 + 거래량 200%+ + 체결강도 70+)
- 신뢰도 다팩터 가중 평균 (모멘텀30/거래량30/체결강도20/호가20), 최소 0.6
- ATR 5일 필터 (상위 20% 제외)
- 최우선 지정가 주문 -> 3초 후 시장가 폴백 + 체결 폴링(2초x15회)
- 포지션 매니저 (손절/익절/트레일링/보합 30분 청산)
- 매매 엔진 오케스트레이터 (스크리닝 -> 전략 -> 리스크 체크 -> 주문)
- 주문 큐(asyncio.Queue) 순차 실행 + 스로틀러 주문 bypass

#### Sprint 3: 텔레그램 봇 + 반자동 승인 ✅ (2026-03-31 완료)
> Sprint 계획: `docs/phase/phase3/sprint3/sprint3.md` (2026-03-31)

- ✅ 텔레그램 웹훅 (FastAPI 엔드포인트 직접 처리)
- ✅ 인라인 버튼 승인/거부 + Redis 승인 키(TTL 30초/15초) + 일회용 토큰
- ✅ 알림 발송 (신호 알림, 체결 완료, 일일 마감 리포트) — HTML 형식
- ✅ 조회 명령어 (/status, /today, /mode, /help)
- ✅ Chat ID 화이트리스트 + 앱 시작 시 setWebhook 자동 호출

### 전문가 확정 파라미터 (2026-03-30, 5명 검토)

| # | 항목 | 확정값 | 담당 |
|---|------|--------|------|
| 1 | 건당 투자비율 (레버리지) | 5% (일반 10%의 절반) | 최리스크 |
| 2 | 최대 레버리지 포지션 | 2개 | 최리스크 |
| 3 | 레버리지 손절/익절 | -1.5%/+3% | 최리스크+사용자 조정 |
| 4 | 트레일링 활성화 | +2% 이상 시 | 최리스크+사용자 조정 |
| 5 | 비상 정지 한도 | -4% (초안 -5%에서 하향) | 최리스크 |
| 6 | 쿨다운 | 30분 내 2연속 손절 시 1시간 | 최리스크 |
| 7 | 당일 청산 강제 | 14:50 시장가, 14:30 이후 진입 차단 | 최리스크+김단타 |
| 8 | 매매 전략 | 모멘텀 브레이크아웃 (5분봉) | 김단타+박퀀트 |
| 9 | 신뢰도 가중치 | 모멘텀30/거래량30/체결강도20/호가20 | 박퀀트 |
| 10 | 주문 방식 | 최우선 지정가 -> 3초 후 시장가 | 김단타+정프로 |
| 11 | 체결 폴링 | 2초 간격, 최대 15회(30초) | 윤에이피 |
| 12 | ATR 필터 | ATR 5일 상위 20% 제외 | 박퀀트 |
| 13 | 보합 청산 | 진입 30분 후 +1% 미달 시 | 김단타 |
| 14 | 관망 시간 | 09:00~09:30 신호 차단 | 김단타 |
| 15 | 골든타임 타임아웃 | 20초 (09:30~10:30) | 김단타 |

### 완료 기준 (Definition of Done)
- 리스크 한도(일일 손실 -3%, 포지션 5개) 초과 시 매매 자동 차단
- 비상 정지(-4%, 연속 3회 손절, 쿨다운) 동작 확인
- 당일 청산 강제(14:50) 동작 확인
- 레버리지 ETF 별도 한도(5%, -1%, +2%) 적용 확인
- 스크리닝 결과 -> 매매 신호 -> 승인 -> 주문 실행 전체 흐름 동작
- 텔레그램에서 승인/거부 시 주문 실행/취소 확인
- 승인 타임아웃(30초/15초) 시 자동 만료 확인
- 주문 실행 지연 < 1초 (한투 API 호출까지)
- 알림 지연 < 3초 (신호 발생 -> 텔레그램 수신)
- 모의거래 환경에서 전체 매매 사이클 테스트 완료

### 기술 고려사항
- 리스크 관리 모듈이 매매 엔진보다 먼저 구현되어야 함 (최리스크 원칙: "리스크 관리가 선행")
- 손절/익절 기준, 포지션 한도는 Phase 1에서 전문가 확정한 값 + Phase 3 추가 확정값 사용
- 레버리지/인버스 ETF는 별도 리스크 한도 적용 (변동성 2~3배)
- 텔레그램 메시지: **HTML 형식 통일** (MarkdownV2 이스케이프 복잡, Phase 0.5 검증)
- 텔레그램 지연 0.5초 (Phase 0.5 실측) — 실시간 알림에 충분
- 텔레그램 승인 일회용 토큰으로 보안 강화
- 주문: 최우선 지정가 -> 3초 후 시장가 폴백 (모의에서는 시장가만, 실전 전환 시 전환)
- ATR 필터 등 팩터 계산은 Phase 2 modules/screening/factors.py 재활용

> Phase 상세 계획: `docs/phase/phase3/phase3.md` ✅ 생성 완료 (2026-03-30)
> 전문가 검토: 정프로(PO), 최리스크(리스크), 김단타(단타), 박퀀트(퀀트), 윤에이피(API) — 5명 검토 완료
> Sprint 문서: `docs/phase/phase3/sprint{N}/sprint{N}.md` (sprint-planner가 생성)

---

## Phase 4: 웹 대시보드 (MVP) (Sprint 1~2) ✅

### 목표
Next.js 기반 웹 대시보드 구현. 메인 대시보드, 포지션/주문/신호/스크리닝 페이지, 설정 페이지, 웹 매매 승인 기능 포함. MVP 완성.

### 작업 목록
#### Sprint 1: 대시보드 기본 구조 + 핵심 페이지 ✅ (2026-03-31 완료)
> Sprint 계획: `docs/phase/phase4/sprint1/sprint1.md` (2026-03-31)

- ✅ JWT 인증 API + CORS 환경변수화 + 로그인 실패 잠금 (PyJWT)
- ✅ 대시보드 집계 API (/dashboard/summary)
- ✅ shadcn/ui + SWR + API 클라이언트 + 색상 상수
- ✅ 로그인 페이지 + AuthProvider + proxy.ts (Next.js 16)
- ✅ 사이드바 + 모드배너
- ✅ 메인 대시보드 페이지 (손익/포지션/거래/리스크 카드)
- ✅ 포지션 페이지 (보유 종목 테이블 + 5초 폴링)
- ✅ 주문 현황 페이지 (상태별 필터 탭)
- ✅ 통합 테스트 + 회귀 검증 (pytest 522 passed, tsc 에러 없음, 프로덕션 빌드 성공)

#### Sprint 2: 신호/스크리닝/설정 + 웹 매매 승인 ✅ (2026-03-31 완료)
> Sprint 계획: `docs/phase/phase4/sprint2/sprint2.md` (2026-03-31)

- ✅ 감사 로그 모델 + Alembic 마이그레이션 (audit_logs 테이블)
- ✅ 웹 승인/거부 API + 대기 신호 조회 (기존 ApprovalManager 활용)
- ✅ 모드 전환 보호 API (이중 확인 + 장중 차단 + 포지션 체크 + 감사 로그)
- ✅ 매매 신호 페이지 (승인 카드 + 카운트다운 + 3초/5초 동적 폴링)
- ✅ 스크리닝 페이지 (1차/2차 탭 + 수동 트리거)
- ✅ 매매 이력 페이지 (날짜 필터 + 손익 색상)
- ✅ 성과 분석 페이지 (기본 일별 손익 테이블)
- ✅ 설정 페이지 (모드 전환 이중 확인 모달 + 리스크 장중 잠금 + 감사 로그)
- ✅ 통합 테스트 + 회귀 검증 (pytest 536 passed, tsc 에러 없음, npm run build 성공)

### 완료 기준 (Definition of Done)
- 모든 Must 페이지 (8개) 접근 가능 및 데이터 표시
- 웹에서 매매 승인/거부 동작
- 실전/모의 모드 시각적 구분 명확 (한유엑 원칙: "과할 정도로")
- 모드 전환(모의<->실전, 자동<->반자동)이 웹에서만 가능
- API 응답 시간 95th < 500ms
- 인증 없이 접근 불가 확인

### 기술 고려사항
- 한국 증시 색상 관례: 빨강=손실, 파랑=수익 (한유엑 조언)
- 정보 과부하 방지: 핵심 -> 상세 흐름 (한유엑 원칙)
- HTTPS 적용 (Cloudflare SSL + Vercel 자동 SSL)
- 모바일 반응형은 후속 Phase에서 고도화

> Phase 상세 계획: `docs/phase/phase4/phase4.md` ✅ 생성 완료 (2026-03-31)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 한유엑(UX), 윤에이피(API) -- 4명 검토 완료
> Sprint 문서: `docs/phase/phase4/sprint{N}/sprint{N}.md` (sprint-planner가 생성)

---

## Phase 4.5: 스케줄러 안정화 + 장애 복구 (Sprint 1~2) 🔄

### 목표
2026-04-01 장전 테스트 장애 근본 해결. 스케줄 의존성 체인(선행 실패 시 후속 중지 + 매매 엔진 차단), 상태값 Redis 영속화, 수동 파이프라인 재실행 API + 대시보드 UI, ETF sanity check 조건부 완화, health/readiness 강화.

### 작업 목록
#### Sprint 1: 백엔드 안정화 ✅ (2026-04-01 완료)
> Sprint 계획: `docs/phase/phase4.5/sprint1/sprint1.md` (2026-04-01)

- ✅ Redis 상태 영속화 (scheduler:* 키, TTL 24h)
- ✅ 스케줄 의존성 가드 (선행 단계 상태 확인 → 실패 시 스킵)
- ✅ pipeline_healthy 플래그 (장전 시 false 초기화 → 핵심 완료 시 true)
- ✅ 매매 엔진 차단 (pipeline_healthy=false 시 신호 처리 스킵)
- ✅ ETF sanity check 조건부 완화 (prev<200 스킵, ±30%)
- ✅ health/readiness 엔드포인트 (DB+Redis+스케줄러+pipeline)
- ✅ 수동 파이프라인 API (POST premarket-pipeline + GET pipeline-status)
- ✅ 텔레그램 장애 알림 (실패 단계 + 에러 요약 + 복구 방법)

#### Sprint 2: 프론트엔드 시스템 관리 📋
- ⬜ 시스템 페이지 (사이드바 "시스템" 탭)
- ⬜ 파이프라인 스테퍼 (6단계 상태 시각화)
- ⬜ 수동 트리거 버튼 (전체 재실행 + 개별, 확인 다이얼로그)
- ⬜ 상태 폴링 (5초/30초 적응형)

### 완료 기준 (Definition of Done)
- 선행 실패 시 후속 job 자동 스킵 + 매매 엔진 차단
- 컨테이너 재시작 후에도 상태값 유지
- 대시보드에서 수동 파이프라인 재실행 가능
- ETF 마스터 최초 적재 시 sanity check 정상 통과

### 기술 고려사항
- Redis `scheduler:` prefix 사용 (기존 키와 충돌 없음)
- pipeline_healthy 기본값 false (보수적, Redis 장애 시 매매 차단이 안전)
- 파이프라인 API는 BackgroundTasks + 폴링 패턴 (Railway 타임아웃 대응)

> Phase 상세 계획: `docs/phase/phase4.5/phase4.5.md` ✅ 생성 완료 (2026-04-01)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 한유엑(UX) -- 4명 검토 완료

---

## Phase 4.6: 데이터 수집 파이프라인 근본 수리 (Sprint 1~2) 🔄 진행 중

### 목표
며칠째 지속되는 데이터 수집 파이프라인 장애의 근본 원인 8건을 체계적으로 해결하고, **수집 유효성 검증 체계**를 구축한다. Dockerfile --reload 제거, **KIS 조회/매매 도메인 분리**, **CollectionValidator + CollectionResult 기반 유효성 검증** (premarket >= 1,500건, ETF >= 50%, null < 5%, data_date T-2 이내), 에러 전파 수정, 실패 유형 분류(retryable/permanent), data_go_kr 날짜 폴백, pipeline_healthy 거짓 양성 방지.

### 작업 목록
#### Sprint 1: 근본 수리 + 도메인 분리 + 유효성 검증 ✅

> Sprint 계획: `docs/phase/phase4.6/sprint1/sprint1.md` (2026-04-02)
> 완료: 2026-04-02 / pytest 602 passed
- ✅ Dockerfile --reload 제거 + docker-compose 개발 분리
- ✅ KIS 조회/매매 도메인 분리 (inquiry_client=LIVE, trading_client=TRADING_ENV)
- ✅ **CollectionResult dataclass + CollectionValidator 클래스 도입** (rev.3)
- ✅ **수집기 반환값 CollectionResult 전환** (data_go_kr, kis_collector, dart, naver) (rev.3)
- ✅ **유효성 검증 적용** (premarket>=1500, ETF>=50%, null<5%, date T-2) (rev.3)
- ✅ **실패 유형 분류** (retryable/permanent) + Redis 구조화 저장 (rev.3)
- ✅ data_go_kr 날짜 폴백 (전일->2일전->3일전, 최대 7일)
- ✅ stocks.updated_at upsert 시 명시적 설정
- ✅ pipeline_healthy 판정 강화 (status + 건수 + validation 동시 확인)

#### Sprint 2: 데이터 품질 + KODEX 필터 + 통합 검증 ✅ (2026-04-02)
- ✅ 한국거래소 2026년 휴장일 캘린더
- ✅ **KODEX ETF 필터링** (시세 수집 대상 878 -> ~280 축소)
- ✅ data_go_kr + validator 공휴일 통합
- ✅ **DB 후검증 쿼리** (SELECT COUNT + null 비율 재확인) (rev.3)
- ✅ scheduler 상세 로깅 + market_data 신선도 검증 (T-2 거래일 이내)
- ✅ 통합 테스트
- ✅ **CollectionValidator unit test** (임계값별 pass/fail 시나리오) (rev.3)
- ✅ 통합 테스트 (수동+자동 파이프라인 + 도메인 분리 + 유효성 검증)

### 전문가 확정 파라미터 (2026-04-02, rev.3 — 4명 검토)

| # | 항목 | 확정값 | 담당 |
|---|------|--------|------|
| 1 | Dockerfile CMD | --reload 제거, --workers 1 유지 | 윤에이피 |
| 2 | premarket 최소 수집 건수 | **1,500건 미만 시 failed** (rev.3: 100->1500) | 최리스크 |
| 3 | ETF 시세 최소 수집률 | **50% 미만 시 failed** (rev.3: 10%->50%) | 최리스크 |
| 4 | 모의 환경 ETF 시세 | required (rev.2: 도메인 분리로 해결) | 전원 합의 |
| 5 | data_go_kr 날짜 폴백 | 전일->2일전->3일전 (최대 7일) | 윤에이피 |
| 6 | pipeline_healthy 판정 | **status + 건수 + validation 동시 확인** (rev.3 강화) | 최리스크 |
| 7 | market_data 신선도 | T-2 거래일 이내 | 김단타 |
| 8 | 한국거래소 휴장일 | 2026년 하드코딩 + 향후 API 전환 | 윤에이피 |
| 9 | KIS 조회 환경 | 항상 LIVE 도메인 + 실전 앱키 (rev.2) | 윤에이피 |
| 10 | inquiry Throttler | 독립 Throttler, LIVE 기준 0.07초 (rev.2) | 윤에이피 |
| 11 | 실전 앱키 필수 검증 | 서버 시작 시 KIS_APP_KEY 존재 검증 (rev.2) | 최리스크 |
| 12 | **close_price null 비율** | **< 5%** (rev.3 신규) | 최리스크 |
| 13 | **volume null 비율** | **< 5%** (rev.3 신규) | 최리스크 |
| 14 | **data_date 유효 범위** | **T-2 거래일 이내** (rev.3 신규) | 김단타 |
| 15 | **primary_screen 0건** | **warning (failed 아님)** (rev.3 신규) | 정프로 |
| 16 | **dart/sentiment 0건** | **warning (failed 아님)** (rev.3 신규) | 정프로 |
| 17 | **수집기 반환값** | **CollectionResult dataclass** (rev.3 신규) | 윤에이피 |
| 18 | **검증 로직** | **CollectionValidator 별도 클래스** (rev.3 신규) | 윤에이피 |
| 19 | **실패 유형 분류** | **retryable / permanent** (rev.3 신규) | 최리스크 |

### 완료 기준 (Definition of Done)
- Dockerfile --reload 제거 완료, 프로덕션 정상 기동
- KIS 조회/매매 도메인 분리 동작 확인 (inquiry_client LIVE, trading_client TRADING_ENV)
- **CollectionValidator가 각 수집 단계의 유효성을 검증** (rev.3)
- **모든 수집기가 CollectionResult 반환** (rev.3)
- market_data에 최근 거래일 데이터 존재 (T-2 이내)
- stocks 테이블에 주식(STOCK) 포함 (1,500건+)
- ETF 시세 수집 정상 (모의/실전 무관, LIVE 도메인 조회, 수집률 >= 50%)
- 건수 미달/null 초과 시 failed 기록 + pipeline_healthy=false
- **pipeline_status JSON에 validation 상세 정보 포함** (rev.3)
- 자동 파이프라인 정상 실행 확인 (다음 거래일 08:00)

### 기술 고려사항
- --reload 제거가 가장 영향 큰 단일 수정 (WatchFiles 무한루프 -> 스케줄러 정상화)
- ETF 시세 전량 실패는 "도메인 라우팅 설계 결함" — inquiry_client(LIVE)로 근본 해결
- **유효성 검증은 에러 전파 수정의 자연스러운 확장** — 동일 코드 영역에서 작업 (rev.3)
- **ETN 시세 수집 공백**: 마스터만 있고 시세 없음. 매매 대상 아니므로 Phase 5 범위 (rev.3)
- **수집 범위 이원화**: 주식=T+1, ETF=당일, ETN=없음. Phase 5에서 통합 검토 (rev.3)

> Phase 상세 계획: `docs/phase/phase4.6/phase4.6.md` ✅ rev.3 수정 완료 (2026-04-02)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) — 4명 rev.3 검토 완료

---

## Phase 4.7: 1차 스크리닝 스코어링 구조 수정 (Sprint 1) ✅

### 목표
1차 스크리닝(primary_screen)이 배포 첫날부터 후보 종목을 통과시키지 못하는 치명적 설계 버그 수정. 실시간 데이터 없는 팩터(체결강도/호가잔량)를 1차에서 제외하고, 3팩터(거래량/변동성/모멘텀) 전용 스코어링 구조로 분리.

### 작업 목록
#### Sprint 1: 스코어링 구조 수정 + 임계값 조정
- scorer.py: PRIMARY_STOCK_FACTORS / PRIMARY_ETF_FACTORS 분리, FactorScorer에 factors 파라미터 추가
- screener.py: _build_candidates 3팩터만 빌드, PrimaryScreener 1차 전용 스코어러 생성
- 1차 pass_threshold 80.0 -> 60.0, 2차 pass_threshold 80.0 -> 75.0
- 최소 후보 경고 (5개 미만 시 warning)
- 테스트 전면 수정 + 버그 재현 방지 회귀 테스트

### 미확정 사항
- 가중치 비대칭 (volume 우선) 여부는 2주 운영 후 IC 기반 조정 (Phase 5)

### 기술 고려사항
- 버그 근본 원인: 분산=0인 팩터가 rank percentile에서 ~2%로 고정 → 이론적 최대 60.91 < 임계값 80.0
- A안(3팩터 분리) 전문가 전원 합의, B안(고정 percentile=50) 기각
- FactorScorer 클래스는 변경 최소화, factors 파라미터만 추가 (하위 호환)

> Phase 상세 계획: `docs/phase/phase4.7/phase4.7.md` (2026-04-02)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명 검토 완료

---

## Phase 4.8: EOD 데이터 수집 내결함성 강화 (Sprint 1~3) ✅

#### Sprint 1: KIS 일봉 보조 수집기 + 스케줄러 폴백 ✅ (2026-04-03)

### 목표
공공데이터포털 전일 OHLCV 미게시 시 1차 스크리닝이 0건 후보를 생성하는 구조적 SPOF 해소. KIS REST 일봉 API 보조 수집, 스케줄러 자동 폴백, 재시도 메커니즘 구현.

### 작업 목록
#### Sprint 1: KIS 일봉 보조 수집기 + 스케줄러 폴백
- KISRestClient에 get_daily_price() 메서드 추가 (FHKST03010100)
- KISDailyCollector 신규 클래스 (배치 수집, source="kis_daily")
- scheduler._premarket_collect() 폴백: 포털 실패 시 KIS 보조 수집 자동 전환
- screener._fetch_today_and_prev() source 필터 확장 (data_go_kr OR kis_daily)
- CollectionValidator.validate_kis_daily() 보조 수집 검증

#### Sprint 2: 재시도 스케줄 + 알림 + 모니터링 ✅ (2026-04-05)
- 08:30 포털 재시도 CronTrigger job
- 텔레그램 알림 (보조 수집 전환/이중 실패 긴급)
- 포털 vs KIS 데이터 cross-check (종가 1% 괴리 warning)
- 재시도 성공 시 포털 데이터 우선 로직

#### Sprint 3: 장전 파이프라인 체인 구조 전환 ✅ (2026-04-05)
- 개별 CronTrigger 6개 제거 (premarket_collect, etf_master_collect, primary_screen, etf_collect, dart_collect, sentiment_collect)
- `_run_scheduled_pipeline()` 래퍼 추가 (락 선점 + 체인 실행)
- 08:00 단일 CronTrigger 등록
- 체인 파이프라인 테스트 추가

### 미확정 사항
- KIS 일봉 API(FHKST03010100) 모의거래 지원 여부 → Sprint 1에서 사전 테스트
- KIS 일봉에 시가총액 미포함 시 대체 전략 최종 확정

### 기술 고려사항
- 모의거래 Rate Limit(초당 1건)으로 전 종목 수집 시 ~42분 → inquiry_client(실전) 사용 또는 범위 축소
- 실전 환경에서는 초당 20건, ~2분 내 완료 가능
- market_data.source 필드로 "kis_daily" 구분 (ETF용 "kis_rest"와 별도)

> Phase 상세 계획: `docs/phase/phase4.8/phase4.8.md` (2026-04-02)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 윤에이피(API 개발자) — 4명 검토 완료

---

## Phase 4.9: 장전 파이프라인 복원력 강화 (Sprint 1) ✅

### 목표
2026-04-06 프로덕션 장애 대응. 이중 실패(포털+KIS) 시에도 DB에 유효 데이터가 있으면 스크리닝을 진행하도록 의존성 체크를 DB 기반으로 전환. 08:30 재시도 성공 시 스크리닝 + 후속 단계 자동 재실행.

### 작업 목록
#### Sprint 1: DB 기반 스크리닝 의존성 + 재시도 후 재실행
- CollectionValidator.validate_screening_readiness() 추가 (DB 데이터 충분성 검증)
- _primary_screen() 의존성 체크: pipeline_status 우선 + DB 폴백
- _premarket_retry() 성공 후 primary_screen + dart + sentiment 재실행
- pipeline_healthy=false 유지 원칙 (DB 폴백 스크리닝이 성공해도)
- 텔레그램 알림 (DB 폴백 경고, T-2 데이터 경고)
- 단위 테스트 + 통합 테스트

### 미확정 사항
- 없음 (전문가 4명 검토 완료, 11건 파라미터 확정)

### 기술 고려사항
- validate_screening_readiness의 소스 필터를 screener의 date_subq와 반드시 동일하게 유지
- pipeline_healthy와 screening_ready는 분리 개념 — 수집 실패 시 healthy=false 유지 필수
- _premarket_retry 후 재실행 시 PIPELINE_RUNNING_KEY 락 확인

> Phase 상세 계획: `docs/phase/phase4.9/phase4.9.md` (2026-04-06)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 윤에이피(API 개발자) — 4명 검토 완료

---

## Phase 5: 1차 스크리닝 안정화 + 완전 자동 모드 + 성과 분석 (Sprint 1~3) 🔄 진행 중

### 목표
프로덕션 모니터링 이슈(1차 스크리닝 통과 0건) 해결 후, 완전 자동 매매 모드 구현, 성과 분석 차트 및 일일 리포트 생성. Should 기능 완성.

### 배경 (2026-04-07 프로덕션 이슈)
- volume_ratio >= 2.0 필터에 88% 탈락 → 통과 0건 → 매매 전체 불능
- prev_volume=0으로 319건 추가 탈락 (T-2 데이터 부재)
- date.today() 잔존 사용처 5개 파일 (risk_manager.py 포함)
- 핫픽스 3건 선 처리 완료 (PR #93, #95~#99)

### 작업 목록
#### Sprint 1: 1차 스크리닝 안정화 ✅ (2026-04-07 완료)
- ✅ volume_ratio 임계값 완화 (2.0 → 1.5)
- ✅ 적응형 필터 ([1.5, 1.2] 단계적 완화, 최소 10개 후보)
- ✅ prev_volume=0 폴백 (최근 5일 평균, 유효 3일+ 조건)
- ✅ 0건 시 기본 후보 (거래량 상위 15개, 시총 500억+, 2차 직접 투입)
- ✅ date.today() → KST 전환 (5개 파일, risk_manager.py 최우선)

#### Sprint 2: 완전 자동 모드 + 텔레그램 고도화 ✅ 완료 (2026-04-07)
> Sprint 1 배포 후 5거래일 관찰 후 착수 (검토팀 확정)
- ✅ 완전 자동 모드 (신호 -> 즉시 주문, 알림만 발송)
- ✅ 반자동/자동 모드 전환 (웹 설정에서만, 확인 절차)
- ✅ 기본 후보/적응형 후보 자동 매매 금지 (반자동만, 50% 사이징)
- ✅ 일일 마감 리포트 (텔레그램 손익 요약)
- ✅ 시스템 오류/경고 알림 강화

#### Sprint 3: 성과 분석
- 수익률 차트 (기간별)
- 전략별 성과 비교
- 매매 이력 상세 분석 (trade_history 비정규화 활용)
- 성과 분석 대시보드 페이지
- [UX개선] 스크리닝 페이지 데이터 신선도 표시

### 완료 기준 (Definition of Done)
- 1차 스크리닝 0건 방지 (적응형 + 기본 후보로 최소 10건)
- volume_ratio 1.5 기준, 평시 장에서 후보 10건+
- 완전 자동 모드에서 신호 -> 주문 자동 실행 확인
- 모드 전환 시 기존 대기 주문 처리 정책 동작
- 일일 리포트 텔레그램 자동 발송
- 수익률 차트 정상 렌더링 (일/주/월 기간)
- date.today() 잔존 제거 (프로덕션 코드 전체 KST)

### 기술 고려사항
- 검토팀 확정: volume_ratio 1.5, 적응형 [1.5, 1.2] (1.0 금지), 기본 후보 15개 (거래량 상위)
- 기본 후보는 1차 스코어링 skip, 2차 직접 투입 (박퀀트: 1차 스코어 무의미)
- 기본 후보 안전장치: 반자동만, 50% 사이징, 플래그 표시 (최리스크 확정)
- 완전 자동 모드에서도 리스크 한도(일일 손실, 포지션 수)는 반드시 적용
- 성과 지표: 수익률, 샤프 비율, MDD (박퀀트 조언)
- 장세 판별 모듈: 후속 Phase 이관 (전원 동의)

> Phase 상세 계획: `docs/phase/phase5/phase5.md` ✅ 계획 수립 완료 (2026-04-07)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명 검토 완료
> Sprint 문서: `docs/phase/phase5/sprint{N}/sprint{N}.md` (sprint-planner가 생성)

---

## Phase 5.1: 1차 스크리닝 change_rate 필터 수정 (Sprint 1) ✅ 완료

### 목표
Phase 5 Sprint 1에서 volume_ratio를 완화했으나, change_rate 필터(+1%~+7%)가 여전히 과도하게 엄격하여 평시 장에서 1차 스크리닝 통과 0건 문제 재발. change_rate_min 완화 + 적응형 필터 확장 + 하락 종목 안전장치 도입.

### 배경 (2026-04-08 프로덕션 이슈)
- change_rate_min=1.0이 전체 종목의 ~70-75%를 즉시 탈락시킴
- 적응형 필터가 volume_ratio만 완화, change_rate는 고정 → 병목 미해소
- 전일 하락/횡보 종목 전량 탈락 → 단타 기회 절반 누락

### 작업 목록
#### Sprint 1: change_rate 필터 수정 + 적응형 확장
- change_rate_min 완화 (1.0 -> -2.0)
- 적응형 필터에 change_rate 포함 (volume_ratio -> change_rate 순차 완화)
- 하락 종목(change_rate < 0) 안전장치 (auto_trade_blocked + 포지션 50%)
- 필터별 탈락 통계 로깅
- 테스트 업데이트

### 완료 기준 (Definition of Done)
- change_rate_min = -2.0 적용, 적응형 [-2.0, -3.0] 동작
- 하락 종목 자동매매 차단 + 포지션 사이징 50% 정상 동작
- 평시 장 기준 1차 스크리닝 통과 10건+ 목표
- pytest 전체 통과

### 기술 고려사항
- 검토팀 확정: change_rate_min=-2.0, 적응형 [-2.0, -3.0], 최저 하한 -5.0, change_rate_max=7.0 유지
- 하락 종목 자동매매 금지 (최리스크+김단타+정프로 전원 합의)
- 절대값 필터(|change_rate| >= 0.3) → 후속 Phase 이관 (박퀀트: 백테스팅 후 도입)

> Phase 상세 계획: `docs/phase/phase5.1/phase5.1.md` ✅ 계획 수립 완료 (2026-04-08)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명 검토 완료

---

## Phase 5.2: KIS WebSocket 모의 환경 안정화 (Sprint 1) ✅

### 목표
모의 환경(paper)에서 KIS WebSocket이 구독 수 초과로 재연결을 반복하여 장중 실시간 파이프라인(2차 스크리닝 + 매매 신호)이 마비되는 문제를 수정한다. 환경별 구독 제한 + 재연결 로직 안정화 + 2차 스크리닝 WS 연동.

### 배경 (2026-04-08 프로덕션 이슈)
- WSSubscriptionManager.max=35 -> 30종목 x 2 tr_id = 60 WS 구독 > 모의 한도 ~40
- 재연결 시 전체 구독 한번에 복원 -> 서버 과부하 -> 즉시 재해제 -> 무한 루프
- 2차 스크리닝 10:14 이후 실질 중단 (Redis TTL=5초 만료)

### 작업 목록
#### Sprint 1: WS 구독 제한 + 재연결 안정화 ✅ 완료 (2026-04-08)
> Sprint 계획: `docs/phase/phase5.2/sprint1/sprint1.md` (2026-04-08)

- 환경별 max_ws_subscriptions (paper=25, live=35)
- 재연결 구독 복원 딜레이 (0.5초/종목)
- 재연결 파라미터 조정 (최대 7회, 백오프 2초, ping_timeout=10초)
- ConnectionClosed close code/reason 로깅
- 재연결 실패 시 텔레그램 긴급 알림
- 2차 스크리닝 WS 미연결 시 스킵 + 연속 3회 텔레그램 경고
- REALTIME_CACHE_TTL 5초 -> 10초
- 재연결 후 체결강도 5초 웜업 구간
- 테스트

### 완료 기준 (Definition of Done)
- 모의 환경 WS 연속 1시간 안정 연결
- 2차 스크리닝 30초 주기 정상 실행 (10회 연속)
- pytest 전체 통과

### 기술 고려사항
- KIS 모의 WS(port 31000)는 tr_id 단위로 구독 카운트 (비공식 ~40건 한도)
- 모의 서버 10~30분 간격 자체 불안정 -> 재연결 견고성이 핵심
- 실전 전환 시 live=35 자동 적용, 별도 검증 Sprint 불필요

> Phase 상세 계획: `docs/phase/phase5.2/phase5.2.md` ✅ 계획 수립 완료 (2026-04-08)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) — 4명 검토 완료

---

## Phase 6: 스케줄러 + WS 복원력 강화 (Sprint 1~2) ✅

### 목표
2026-04-10 프로덕션 장애(장전 수집 -> 스크리닝 -> WS 구독 전체 파이프라인 실패) 분석 결과를 바탕으로, 치명적 버그 수정 + 복원력 강화 + 불필요 실행 방지를 수행한다.

### 작업 목록
#### Sprint 1: 치명적 버그 수정 + 최소 방어
- `_reconnect()` ConcurrencyError 수정 (기존 `_receive_task` cancel+await)
- `_reconnect()` 좀비 연결 수정 (구독 복원 실패해도 수신 루프 시작, Phase 5.2 미해결 #6)
- WS 가드 조건 `and` -> `or` (ws_manager.py subscribe/unsubscribe)
- `_market_open()` bare exception -> 텔레그램 알림 + 상태 기록
- `_market_open_recovery()` 판단 기준: `ws_manager.count` -> `_ws_client.connected`
- `is_trading_day()` 가드: `_run_scheduled_pipeline`, `_market_open`에 추가
- WS `open_timeout=10` + `subscribe()` `_ws None` 가드

#### Sprint 2: 복원력 강화 + 불필요 실행 방지
- KIS REST 재시도/백오프 (kis_daily_collector.py, 최대 3회, HTTP 500/502/503/429)
- `_market_open_recovery()` 단계적 재시도 (09:05/09:10/09:15, 3회)
- `_premarket_collect()` 예외 경로 KIS 폴백 트리거
- 나머지 핸들러에 `is_trading_day()` 가드 추가

### 완료 기준 (Definition of Done)
- `_reconnect()` ConcurrencyError 및 좀비 연결 해소
- WS 가드 조건 `or` 적용
- `_market_open()` 실패 시 텔레그램 알림 수신
- recovery 3단계 재시도 동작 확인
- KIS REST 500 에러 재시도 동작 확인
- 주말/공휴일 스케줄러 스킵 확인
- pytest 전체 통과

### 기술 고려사항
- 검토팀 확정: 15건 파라미터 (전문가 4명 검토 완료, 2026-04-12)
- Phase 5.2 미해결 #6 (좀비 연결) Sprint 1에서 해결 (최리스크 강력 요구)
- KIS REST 재시도는 kis_daily_collector.py에만 적용, 주문 API 제외 (윤에이피 권고)
- ROADMAP 기존 Phase 6 범위(모바일, 센티멘트, DART)는 후속 Phase로 이관

> Phase 상세 계획: `docs/phase/phase6/phase6.md` ✅ 계획 수립 완료 (2026-04-12)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 윤에이피(API), 김단타(단타) — 4명 검토 완료
> Sprint 1: `docs/phase/phase6/sprint1/sprint1.md` ✅ 완료 (2026-04-12)
> Sprint 2: `docs/phase/phase6/sprint2/sprint2.md` ✅ 완료 (2026-04-12)

---

## Phase 6.1: 거래량 시간가중 보정 + 5분봉 수집 구축 (Sprint 1) ✅

### 목표
momentum_breakout 전략의 volume_ratio 조건이 "장중 누적 vs 전일 마감 누적"을 직접 비교하는 단위 불일치 오류를 시간가중 보정으로 해결. 돌파 강도 연동 임계값 도입. Phase 7.1용 5분봉 거래량 수집 파이프라인을 선행 구축하여 데이터 축적 시작.

### 작업 목록
#### Sprint 1: 거래량 시간가중 보정 + 돌파 강도 연동 + 5분봉 수집
- calc_market_progress() 함수: 장 경과 비율(0.0~1.0) 계산
- 시간가중 보정 공식: adjusted_ratio = volume / (prev_volume * progress)
- **돌파 강도 연동 임계값**: 5%+→1.5, 3~5%→1.8, <3%→2.0
- 안전장치: MIN_MARKET_PROGRESS=0.15, **MIN_VOLUME_FLOOR=0.5** (2차 검토 상향)
- **5분봉 거래량 집계**: volume_aggregator 모듈 → Redis `vol5m:*` 키에 슬롯별 누적 (Phase 7.1용)
- 기존 테스트 수정 + 시간대별/돌파 강도별/5분봉 집계 테스트 추가

### 완료 기준 (Definition of Done)
- 시간가중 보정 적용 후 장 전반부에서도 거래량 급증 종목 감지 가능
- 돌파 강도 연동 임계값 동작 (062040 역산 검증 통과)
- 안전장치(min_progress=0.15, MIN_VOLUME_FLOOR=0.5) 동작 확인
- 5분봉 거래량 수집 Redis 적재 확인
- 단위 테스트 통과 (기존 수정 + 신규 10건 이상)
- 프로덕션 배포 후 3거래일 모니터링 (adjusted_ratio 분포 + 5분봉 키 축적)

### 기술 고려사항
- 선형 보정은 장 중반에 ~10-20% 보수적 (리스크 관리에 유리, Phase 9에서 비선형 검토)
- 5분봉 수집은 이 Phase에서 축적만, 전략에서 사용은 Phase 7.1부터
- Redis 메모리: 30종목 x 78슬롯 x 30일 = ~7MB (Railway Redis 용량 내)
- 의존성: Phase 6 (스케줄러 + WS 안정화 완료 전제)
- **데이터 축적 시작 시점**: 이 Phase 배포 즉시 → Phase 7.1 착수 가능 시점 예상: 배포 + 20거래일

> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 박퀀트(퀀트) — 4명 검토 (1차 + 2차) 완료
> Phase 상세 계획: `docs/phase/phase6.1/phase6.1.md`
> Sprint 1: `docs/phase/phase6.1/sprint1/sprint1.md` ✅ 완료 (2026-04-13)

---

## Phase 6.2: 장전 수집 단순화 — KIS 주경로 + 포털 장후 보조 (Sprint 1) ✅

### 목표
공공데이터포털 08:00 호출의 구조적 실패(정책: T+1 13시 이후)를 근본적으로 해결. 08:00 수집을 KIS 일봉 직접 호출로 전환하고, 포털은 16:00 장후 보조 수집으로 market_cap/listed_shares만 갱신. 상태 관리(portal_fresh, streak 카운터) 전면 제거로 복잡도 대폭 감소.

### 작업 목록
#### Sprint 1: 장전 수집 단순화 + 포털 장후 보조
- `_premarket_collect`: 포털 제거 -> KIS 일봉 직접 호출
- `_premarket_retry`: 포털 재시도 -> KIS 실패 시 KIS 재시도로 전환
- `_portal_supplement_collect`: 16:00 포털 보조 cron 신규
- `validate_premarket_db`: 소스 확장 (data_go_kr + kis_daily)
- 불필요 코드 제거: portal_fresh, streak 카운터, 알림 승급, 14:00 cron
- 4/4~4/10 포털 백필 (기존 trigger_premarket_date API 활용)

### 완료 기준 (Definition of Done)
- 08:00 KIS 일봉 직접 수집 동작
- 08:30 KIS 실패 시 KIS 재시도 동작
- 16:00 포털 보조 수집으로 market_cap/listed_shares 갱신
- validate_premarket_db가 kis_daily 소스 포함
- 4/4~4/10 백필 완료
- 기존 테스트 전부 통과

### 기술 고려사항
- KIS 일봉은 market_cap=None → stocks.listed_shares * close_price 보정 (이미 screener.py에 구현됨)
- 포털 필요 필드 = 2개뿐 (market_cap, listed_shares) → 장후 1회 수집으로 충분
- 16:00 수집 = 전 종목 (스크리닝 모수 왜곡 방지)
- 공공데이터포털 Rate Limit: 일 1,000건 → 정규 수집 ~10건 + 백필 시 하루 2거래일 한도

> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 윤에이피(API 개발자), 박퀀트(퀀트) — 4명 rev.2 검토 완료 (전원 합의)
> Phase 상세 계획: `docs/phase/phase6.2/phase6.2.md`
> Sprint 1: `docs/phase/phase6.2/sprint1/sprint1.md` ✅ 완료 (2026-04-14)

---

## Phase 7.0: 매매 엔진 치명적 결함 수정 + LIVE 전환 준비 (Sprint 1~3) 🔄

### 목표
2026-04-15 평가에서 발견된 매매 엔진 치명적 결함 3건(가격 갱신 미연결, 포지션 미생성, 청산 미실행) 수정. 파라미터 오보정 교정. 리스크 관리 개선. Paper E2E 검증 후 LIVE 전환 게이트 통과.

### 필요 선행 데이터
- 없음 (코드 결함 수정 — 데이터 축적 불필요, 즉시 착수 가능)

### 작업 목록
#### Sprint 1: P0 치명적 결함 + P1 수정 ✅ 완료 (2026-04-15)
- engine._monitor_positions_loop: update_prices() + 청산 매도 실행 연결
- order_manager._execute_order: on_filled_callback으로 포지션 생성 연결
- Order 모델 signal_json 컬럼 추가 (Alembic)
- cancel 실패 시 return (이중 주문 방지)
- 체결가 역산 (tot_ccld_amt / tot_ccld_qty)
- trade_strength_min 100.0 (CTTR 통일), max_candidates 30→20
> Sprint 계획: `docs/phase/phase7.0/sprint1/sprint1.md`

#### Sprint 2: P2 리스크 개선 ✅ (2026-04-16 완료)
- daily_loss_pct 분모: 당일 시작 잔고 기반으로 변경
- record_loss 트리거: realized_pnl < 0 전체로 확장
- trailing_highs: 인메모리 → Redis HSET 이관
- in-flight 중복 매도 방지 (미해결 #7 대응)
> Sprint 계획: `docs/phase/phase7.0/sprint2/sprint2.md` (2026-04-16)

#### Sprint 3: E2E 검증 + LIVE 전환 게이트
- Paper 모드 E2E 1사이클 완전 성공 확인
- 5거래일 핫픽스 0건 + 신호 발생 3거래일 연속
- LIVE 초기 운영 파라미터 적용

### 전문가 확정 파라미터 (2026-04-15 — 4명 검토)

| # | 항목 | 확정값 | 담당 |
|---|------|--------|------|
| 1 | 가격 갱신 소스 | WS Redis 우선 + REST 폴백 | 윤에이피 |
| 2 | 가격 갱신 시간대 | 09:00~15:30만 | 김단타 |
| 3 | 체결→포지션 연결 | 콜백 패턴 (on_filled_callback) | 윤에이피 |
| 4 | signal 정보 전달 | Order.signal_json 컬럼 | 윤에이피 |
| 5 | 청산 매도 방식 | 시장가 + 3회 폴링 | 김단타 |
| 6 | cancel 실패 처리 | return (시장가 중단) | 최리스크+윤에이피 |
| 7 | 체결가 역산 | tot_ccld_amt / tot_ccld_qty | 윤에이피 |
| 8 | trade_strength_min (2차+전략) | 100.0 (CTTR 기준 통일) | 전원 동의 |
| 9 | max_candidates | 20 | 전원 동의 |
| 10 | daily_loss_pct 분모 | 당일 시작 잔고 기반 | 최리스크 |
| 11 | record_loss 트리거 | realized_pnl < 0 전체 | 최리스크 |
| 12 | trailing_highs | Redis HSET | 전원 동의 |
| 13 | LIVE 초기 max_position | 2 | 최리스크+김단타 |
| 14 | LIVE 초기 position_size | 5% | 최리스크+김단타 |
| 15 | LIVE 초기 daily_max_loss | -2% | 최리스크 |
| 16 | LIVE 초기 emergency_stop | -3% | 최리스크 |
| 17 | LIVE 초기 거래 모드 | semi-auto | 전원 동의 |
| 18 | LIVE 초기 자본금 | 50만원 이하 | 최리스크 |

### 완료 기준 (Definition of Done)
- P0 3건 + P1 2건 수정 + 테스트 통과
- P2 3건 리스크 개선 + 테스트 통과
- Paper E2E 1사이클 완전 성공 (주문→체결→포지션→가격갱신→청산)
- Paper 5거래일 핫픽스 0건 + 신호 발생 3거래일 연속
- LIVE 전환 게이트 전 조건 충족

### 기술 고려사항
- 기존 Phase 7(5분봉 가속도)은 Phase 7.1로 리넘버링. 데이터 축적은 계속 진행 중.
- Phase 7.0은 데이터 축적과 무관하므로 즉시 착수 가능.
- engine↔order_manager 순환 참조는 콜백 패턴으로 해결.
- LIVE 전환 시 tr_id 접두사 자동 전환 (settings.TRADING_ENV 기반) 확인 필요.

> Phase 상세 계획: `docs/phase/phase7.0/phase7.0.md` ✅ 계획 수립 완료 (2026-04-15)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 윤에이피(API) — 4명 검토 완료

---

## Phase 7.0.1: KIS LIVE WebSocket 연결 복구 (Sprint 1) ✅

### 목표
2026-04-16 발생한 KIS LIVE WebSocket 전면 연결 실패 진단 및 수정. WS URL 경로 누락(`/tryitout`) 수정 + Railway Static IP 활성화로 내일 장 전 ws_connected=True 달성.

### 필요 선행 데이터
- 없음 (인프라/설정 수정 — 즉시 착수 가능)

### 작업 목록
#### Sprint 1: WS 연결 진단 + 수정 + 검증 ✅ (2026-04-16 완료)
- ✅ diagnose_ws.py Railway 실행 (원인 B 확정: LIVE 경로 누락)
- ✅ kis_config.py LIVE ws_url `/tryitout` 경로 추가
- N/A Railway Static Outbound IP 등록 — KIS WebSocket IP 등록 정책 없음 (KIS 공식 확인)
- ⬜ 검증: ws_connected=True + subscriptions > 0 (배포 후 확인 필요)

### 전문가 확정 파라미터 (2026-04-16 — 4명 검토)

| # | 항목 | 확정값 | 근거 |
|---|------|--------|------|
| 1 | LIVE ws_url | `ws://ops.koreainvestment.com:21000/tryitout` | KIS 공식 예제 100% 일치 |
| 2 | PAPER ws_url 수정 | LIVE 검증 후 별도 수정 | 4명 전원 합의 |
| 3 | Railway Static IP | 무조건 활성화 | 최리스크: LIVE 운영 필수 |
| 4 | 복구 확인 시점 | 배포 후 즉시 + 내일 08:55 | 김단타: 장 시작 전 5분 여유 |

### 완료 기준 (Definition of Done)
- LIVE WS 연결 성공 (ws_connected=True)
- 1종목 이상 구독 성공 (subscriptions > 0)
- 내일 09:00 자동 연결 성공

> Phase 상세 계획: `docs/phase/phase7.0.1/phase7.0.1.md` 계획 수립 완료 (2026-04-16)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 윤에이피(API) — 4명 검토 완료

---

## Phase 7.2: 매매 전략 진입 조건 개선 (구 계획, Phase 8로 흡수) 🔀

2026-04-20 재편성 — 기존 Phase 7.2 확정 계획(2026-04-17)은 파라미터 그대로 **Phase 8 Sprint 1·2로 흡수**. 검토 리포트는 `docs/phase/phase7.2/` 경로에 그대로 유지.

> 흡수 결과: `docs/phase/phase8/phase8.md` 참조

---

## Phase 8: 즉시 착수 개선 사항 통합 (Sprint 1~4) 📋

### 목표
데이터 축적 대기 없이 즉시 착수 가능한 개선 사항을 단일 Phase로 통합. (1) 매매 신호 0건 근본 원인 해결 (구 Phase 7.2 Sprint 1·2 흡수), (2) 시스템 관리 UI (구 Phase 4.5 Sprint 2), (3) 성과 분석 보강 (구 Phase 5 Sprint 3). Phase 7.0 Sprint 3 LIVE 게이트의 선행 조건.

### 필요 선행 데이터
- 없음 (코드 수정 — 데이터 축적 불필요, 즉시 착수 가능)

### 작업 목록
#### Sprint 1: 장중 OHLC 파싱 + 갭 분기 수정 (구 Phase 7.2 Sprint 1) 🔄 진행 중
- H0STCNT0 파서에 STCK_OPRC/STCK_HGPR/STCK_LWPR 3필드 추가
- Redis 캐싱 + snapshot 조립 수정
- 갭 3%+ 분기 버그 수정 (breakout_ref = high → open_price)
- Sprint 1 배포 당일 Redis idx 매핑 검증 (김단타 권고)
- 계획 문서: `docs/phase/phase8/sprint1/sprint1.md` ✅ 계획 수립 완료 (2026-04-20)

#### Sprint 2: 다층 진입 조건 + 리스크 안전장치 (구 Phase 7.2 Sprint 2)
- prev_close(1단계) + prev_high(2단계) 다층 진입
- prev_close: confidence 상한 0.75, 반 포지션(50%), volume_threshold 2.5
- 일일 최대 거래 10건 (Sprint 2 전 LIVE 초기엔 3건/일, 포지션 1건 상한 — 최리스크 R2)
- 13:00 이후 prev_close 돌파 비활성화

#### Sprint 3: 시스템 관리 UI
- 스케줄러 상태 + pipeline_healthy + 수동 트리거(2단계 확인 + LIVE/PAPER 명시 + 이력 로깅 — 최리스크 R1)
- 보유 포지션 실시간 카드 + 청산 카운트다운 + 장 단계 배지 (김단타 D1)
- 장중 수동 트리거 비활성화 가드

#### Sprint 4: 성과 분석 보강
- 일간/주간 PnL, 승률, MDD(peak-to-trough 박퀀트 Q2), Sharpe(KOFR 3.5% 박퀀트 Q3)
- 평균 보유 시간 + 시간대별 진입 분포 (김단타 D2)
- 표본 < 30거래일 시 "참고용" 표시 (박퀀트 Q4)

### 전문가 확정 파라미터 (2026-04-20 — 4명 검토, 기존 Phase 7.2 확정 승계 + 추가)

Sprint 1·2는 기존 Phase 7.2 확정(2026-04-17) 10개 파라미터 그대로 승계 + Sprint 3·4 추가 파라미터는 `docs/phase/phase8/phase8.md` 참조.

### 완료 기준 (Definition of Done)
- H0STCNT0 OHLC 파싱 정상 동작 (Redis 저장 확인)
- 매매 신호 장중 1건 이상 발생 (2거래일 연속, 노이즈 필터 후)
- 다층 진입 + 반 포지션 + confidence 상한 + 일일 거래 한도 동작
- 시스템 관리 UI (수동 트리거 2단계 가드 + 포지션/카운트다운/장 단계)
- 성과 분석 대시보드 (PnL/승률/MDD/Sharpe/보유시간/시간대 분포)
- pytest 전체 통과

### 기술 고려사항
- Sprint 1은 Phase 7.0 Sprint 3의 선행 조건.
- Sprint 2 전 LIVE 전환 시 거래 한도 축소(3건/일, 포지션 1건) 환경변수 가드.
- Sprint 3·4는 Sprint 1 배포 후 순차 (정프로 P1 — 1명 개발자 컨텍스트 분산 방지).
- 5분봉 가속도 지표는 Phase 9 Sprint 0으로 이관 (박퀀트 Q1 — 지표 상관관계 관리).

> Phase 상세 계획: `docs/phase/phase8/phase8.md` ✅ 계획 수립 완료 (2026-04-20)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 김단타(단타), 박퀀트(퀀트) — 4명

---

## Phase 9: 동시간대 Z-score + VWAP + 5분봉 가속도 지표 (Sprint 0~3) 📋

### 목표
"동시간대 N일 거래량 Z-score" + "VWAP 대비 가격 포지션" + "5분봉 거래량 가속도 지표"를 매매 전략의 confidence 프레임워크에 통합 편입. 박퀀트 권고로 Phase 8(구) Sprint 5(5분봉 가속도)를 Phase 9 Sprint 0으로 이관하여 지표 상관관계 관리 + 통합 설계 이익.

### 🔑 사용자 지시 데이터 의존성 재검토 결과 (2026-04-20)
사용자 지시 "진짜 데이터가 쌓인 상태에서 하는 게 맞는지 재검토해"에 따라:
- **VWAP**: 당일 장중 누적만 필요 → 과거 축적 **불필요, 즉시 착수 가능**
- **Z-score (total_vol)**: 대안 A(KIS 과거 분봉 백필) + 대안 C(점진 활성화 10/15/20/30 거래일 단계) 병행
- **Z-score (buy/sell 분리)**: 실시간 축적만 가능 (자연 축적)

### 필요 선행 데이터 (완화 후)
- **Phase 8 Sprint 1·2 완료** (매매 신호 복구)
- Z-score 가중치 100% 활성화는 30거래일+ 축적 시점 (착수 조건과 분리)
- KIS 과거 분봉 API 스펙 재확인 (Sprint 0 초반 MCP 조사)

### 작업 목록
#### Sprint 0: 데이터 수집 인프라 + KIS 백필 + 5분봉 가속도 (구 Phase 8 Sprint 5 통합)
- `volume_5min_history` 테이블 마이그레이션 + EOD 이관 배치
- VWAP Redis 슬롯별 누적 (`vwap:{code}:{date}:pv`, `:v`, TTL 2일)
- KIS 과거 분봉 백필 (18:00~23:00 한정, 16req/s, 최대 30거래일, 분할/증자 제외)
- 5분봉 가속도 지표 (시간대 스케일링 + 유동성 50만 주 미만 제외 — 김단타 D3·D4)

#### Sprint 1: Z-score 엔진 (점진 활성화)
- 점진 가중치: <10일 0%, 10-15일 10%, 15-20일 30%, 20-30일 60%, 30일+ 100% (최리스크 R1)
- 백필 데이터 정합성 사전 검증 (실시간 수집 대비 차이 10%+ 시 백필 제외)
- 비모수(분위수) 대체 경로

#### Sprint 2: VWAP 엔진 + 가격 포지션 (Sprint 0 완료 후 병행 가능)
- 실시간 VWAP O(1) Redis 조회
- 가격 포지션: `price > VWAP * 1.005` 매수 우위 (+0.05), `< VWAP * 0.995` 매도 우위 (-0.05)
- 09:30 이전 VWAP 지표 비활성화 (최리스크 R3)

#### Sprint 3: 백테스트 데이터셋 + REST API
- TimeSeriesSplit 기반 분할 (look-ahead bias 제거 — 박퀀트 Q2)
- `/api/v1/indicators/vwap/{code}`, `/api/v1/indicators/zscore/{code}`
- **지표 상관관계 의무 점검** (가속도/Z-score/VWAP 상관계수 > 0.7 시 가중치 축소/통합)

### 완료 기준 (Definition of Done)
- volume_5min_history 테이블 + EOD 이관 + VWAP 누적 동작
- KIS 백필 20종목 × 5거래일+ 성공, 정합성 검증 통과
- 5분봉 가속도 + Z-score 점진 활성화 + VWAP 전략 반영
- 지표 상관관계 점검 + REST API 동작
- pytest 전체 통과

### 기술 고려사항
- KIS 과거 분봉: 최대 30거래일, 18:00+ 실행, 수정주가 주의 (윤에이피 A1~A6)
- 점진 활성화 로깅 전용 구간을 10거래일로 연장 (최리스크 R1)
- VWAP 실시간 계산은 O(1) Redis `INCRBYFLOAT` 2회로 처리

> Phase 상세 계획: `docs/phase/phase9/phase9.md` ✅ 계획 수립 완료 (2026-04-20)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 윤에이피(API) — 4명

---

## Phase 10: U자형 비선형 보정 (Sprint 1~3) 📋

### 목표
Phase 6.1의 선형 시간가중 보정을 **실제 관측 기반 U자형 비선형 함수 f(t)**로 교체. 장 중반부 보수적 편향(~10-20%) 해소. 사용자 지시 재검토에서 **"완화 불가"**로 확인 — 함수 피팅은 단일 통계량이 아니므로 장기 축적 필수.

### 필요 선행 데이터
- Phase 9 Sprint 3 완료 (백테스트 데이터셋)
- **Phase 9 Sprint 3 완료 + 2개월(40거래일) 축적 시 의무 착수** (대안 C만 가능)
- 본격 Cubic Spline 피팅은 3개월+ 축적 필요
- 이상적 운영 6개월+ (계절성 검증)
- 착수 경고: 2개월 미만 시 강행 금지

### 작업 목록
#### Sprint 1: U자형 함수 피팅 (초기)
- 축적 데이터 EDA
- **Cubic Spline** (knot 5개: 09:00/10:00/11:30/13:30/14:30 — 박퀀트 Q1)
- **TimeSeriesSplit, n=5** (look-ahead bias 제거 — 박퀀트 Q2)
- R² 기준: 대안 C(N/A) / Cubic Spline 0.85(3개월)·0.90(6개월)
- R² 미달 시 Cubic Spline 강행 금지, 대안 C(슬롯별 상수 보정)만 유지

#### Sprint 2: 비선형 보정 적용 + A/B (점진 전환)
- A/B 분할: **10:90 (1주) → 30:70 (2주) → 50:50 (1개월)** — 최리스크 R1
- 다층 롤백: **-5%(경고) / -10%(1차) / -15%(2차) / -20%(전면)** — 최리스크 R2
- A/B 기간 VIX/코스피 변동성 로깅 (김단타 D4)
- 통계 유의성 검정: t-test/Mann-Whitney p<0.05 (박퀀트 Q4)
- 진입/청산 f(t) 분리 적용 (14:30 급증 구간 특성 — 김단타 D1)
- Phase 9 Sprint 3 데이터셋으로 사전 백테스트 (박퀀트 Q5)

#### Sprint 3: 실증 검증 + 안정성
- 재피팅 시 계수 변화 < 20% 확인
- 분기별 자동 재피팅 스케줄러 (계절성 대응 — 최리스크·박퀀트 Q6)
- 주간 R² + 계수 변화율 + MDD 트렌드 모니터링

### 완료 기준 (Definition of Done)
- 축적 데이터 EDA + Cubic Spline 또는 대안 C 피팅, R² 기준 달성
- TimeSeriesSplit 교차 검증 validation R² 하락 < 10%
- A/B 점진 전환 동작 + 다층 롤백 트리거 동작
- 통계 유의성 p<0.05 검증
- 선형 대비 장 중반부 편향 50% 이상 감소
- pytest 전체 통과

### 기술 고려사항
- 데이터 부족 상태의 강행 금지 (대안 C만 적용)
- 분기별 재피팅으로 계절성 대응
- 피라미딩(당일 고가 갱신 진입) + 2차 스크리닝 하이브리드는 **Phase 10.1**로 분리 (정프로 P1)

> Phase 상세 계획: `docs/phase/phase10/phase10.md` ✅ 계획 수립 완료 (2026-04-20)
> 전문가 검토: 정프로(PO), 최리스크(리스크관리), 박퀀트(퀀트), 김단타(단타) — 4명

---

## Phase 10.1: 누적 백로그 통합 (Sprint 1~2, 예정) 📋

### 목표
Phase 10 완료 + 3개월 안정 운영 후 착수. Phase 4~10 리뷰에서 의도적으로 보류했던 장기 고도화 항목 일괄 처리.

### 범위
- **당일 고가 갱신 진입 (피라미딩)** — position_size 30%, +3% 이상 이익 조건, 14:00 비활성, 호가 매수/매도 잔량 비율 0.5+ (김단타+최리스크 강력 권고)
- **2차 스크리닝 하이브리드** — 상대 백분위 70% + 절대 점수 30%, 절대 70점 하한, 전일 대비 -5% 이하 제외 (Phase 7.0 미해결 #10 근본 해결)
- **기타 ⚠️ 백로그** — Phase 4~10 리뷰 리포트 ⚠️ 항목 점검

### 필요 선행 데이터
- Phase 10 Sprint 3 완료 + 3개월 이상 안정 운영

### 완료 기준 (Definition of Done)
- 피라미딩 로직 + 1주 모의 검증 + LIVE 배포
- 하이브리드 스크리닝 동작
- 누적 백로그 전원 처리 또는 Won't 결정

> Phase 상세: Phase 10 완료 후 계획 수립
> 향후 phase-planner 재호출 예정

---

## 리스크 및 완화 전략

| 리스크 | 영향도 | 완화 방안 | Phase 0.5 검증 |
|--------|--------|----------|---------------|
| 한투 API 장애/변경 | 높음 | 에러 핸들링, 재시도, 폴백 설계. API 버전 모니터링 | 에러 5건 응답 구조 파악 완료 |
| 한투 API 잘못된 종목 HTTP 200 | 중간 | 데이터 값 검증(stck_prpr==0 등) + 종목 마스터 이중 체크 | Phase 0.5 에서 발견 |
| 모의/실전 환경 차이 | 높음 | 모의거래 충분 테스트, 실전 전환 체크리스트, 소액 테스트 | 도메인/tr_id/WS포트 차이 문서화 |
| Rate Limit 초과 | 중간 | 적응형 백오프 (기본 1.5초 + 에러 시 지수 증가) | 모의 실측: 공식보다 관대하나 연속 시 차단 |
| 공공데이터포털 일 한도 | 낮음 | 전 종목 6회 호출로 충분, 페이징 배치 | Phase 0.5 검증: 2,880종목/3.7초 |
| Railway 서비스 장애 | 중간 | 헬스체크, Railway 자동 재시작, 장중 가동률 99% 목표 | — |
| 과적합된 매매 전략 | 중간 | 단순 전략 우선, 표본 외 검증, 점진적 고도화 | — |
| 실전 매매 손실 | 높음 | 리스크 한도 엄격 적용, 일일 손실 한도, 비상 정지 | — |

## 전문가 확정 완료 항목 (Phase 1 계획에서 확정, 2026-03-29)

| # | 항목 | 확정값 | 담당 전문가 |
|---|------|--------|------------|
| 1 | 데이트레이딩 vs 스윙 | ✅ **데이트레이딩 전용** (당일 청산 원칙) | 김단타 + 최리스크 |
| 2 | 운영 시간대 | ✅ **07:30~16:00** (본매매 09:30~14:30, 시초가 금지) | 김단타 |
| 3 | 사전 정보수집 타이밍 | ✅ **08:00** 공공데이터포털 → 08:05 스크리닝 → 08:10 한투 | 김단타 + 윤에이피 |
| 4 | 백테스팅 필요성/시점 | ✅ **MVP 제외**, Phase 5 이후 도입 | 박퀀트 |
| 5 | 손절/익절 기준값 | ✅ **손절 -2%, 익절 +3%**, 트레일링 -1%, 레버리지 -1.5% | 최리스크 + 김단타 |
| 6 | 승인 타임아웃 시간 | ✅ **장중 30초, 마감전 15초**, 기본 60초 | 김단타 |

## 향후 확장 (Backlog, Won't in MVP)

- 미국 주식/ETF 시장 지원 (market 어댑터 추가, 아키텍처만 Phase 1에서 대비)
- 백테스팅 시스템 (전문가 자문 결과에 따라)
- 추가 정보소스 연동 (전문가 추천 시)
- 매매 전략 다양화
- 알림 채널 추가 (카카오톡 등)
- 신용거래, 선물/옵션
