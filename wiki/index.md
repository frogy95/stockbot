# StockBot Wiki

StockBot — 한국 주식/ETF 단타 자동 매매 시스템의 지식 베이스.

이 위키는 시스템의 아키텍처, 데이터 흐름, 전략 로직, 인프라, 개발 프로세스를 문서화한다.

---

## 시스템 아키텍처

- [[system-overview]] — 전체 시스템 개요 및 구성 요소
- [[tech-stack]] — 기술 스택 선택 및 이유
- [[module-structure]] — 백엔드 모듈 구조 및 책임 분리

## 데이터 수집

- [[data-collection-flow]] — 장전/장중/장후 3단계 데이터 수집 흐름
- [[kis-api]] — 한국투자증권 REST/WebSocket API
- [[websocket-management]] — 실시간 WebSocket 연결 관리
- [[public-data-sources]] — 공공데이터포털/DART/네이버 API

## 스크리닝

- [[screening-pipeline]] — 1차(장전)/2차(장중) 스크리닝 파이프라인
- [[screening-factors]] — 5팩터(거래량/변동성/모멘텀/체결강도/호가잔량)
- [[scoring-system]] — 종목 스코어링 및 순위 결정

## 매매 실행

- [[trading-modes]] — 반자동/완전자동 매매 모드
- [[signal-generation]] — 매매 신호 생성 프로세스
- [[momentum-breakout-strategy]] — 모멘텀 돌파 전략 상세
- [[order-execution]] — 주문 실행 및 체결 관리
- [[position-management]] — 포지션 생명주기 관리

## 리스크 관리

- [[risk-management]] — 리스크 체크 시스템 및 비상 정지
- [[position-sizing]] — 포지션 사이징 및 자금 배분

## 인프라 및 배포

- [[deployment]] — Vercel + Railway 배포 환경
- [[database-schema]] — PostgreSQL 스키마 설계
- [[redis-usage]] — Redis 캐시 및 실시간 데이터 관리

## API 연동

- [[telegram-integration]] — 텔레그램 봇 알림 및 승인 처리
- [[external-apis]] — 외부 API 의존성 요약

## 개발 프로세스

- [[development-workflow]] — 스프린트/핫픽스 개발 워크플로우
- [[paper-vs-live]] — 모의거래/실전거래 전환
- [[trading-calendar]] — 한국 거래소 캘린더 및 장 시간
