# 미완료 배포 항목

> 이 파일은 현재 미완료된 수동 검증/배포 항목만 유지합니다.
> - **sprint-close** 에이전트가 스프린트 마무리 시 새 항목을 추가하고, 기존 완료 기록을 `docs/deploy-history/YYYY-MM-DD.md`로 아카이빙합니다.
> - **sprint-review** 에이전트가 코드 리뷰와 자동 검증 결과를 이 파일에 기록합니다.
> - 완료된 항목은 `✅`, 미완료 항목은 `⬜`로 표시합니다.

### 프로덕션 배포 - v1.0.0 (2026-04-02)

포함 스프린트: Phase 4.7 Sprint 1
PR: https://github.com/frogy95/stockbot/pull/73

- ✅ Vercel 프론트엔드 자동 배포
- ✅ Railway 백엔드 자동 배포

#### 자동 검증 결과

자동 검증 및 수동 검증 필요 항목은 5단계 실행 후 업데이트합니다.

#### 수동 검증 필요 항목

- ⬜ 프로덕션 배포 후 다음 거래일 primary_screen passed > 0 확인 (장중 확인 필요)

---

### Phase 4.7 Sprint 1: 1차 스크리닝 3팩터 분리 + 임계값 조정 (2026-04-02)

PR: https://github.com/frogy95/stockbot/pull/72

#### 코드 리뷰 결과 (2026-04-02)

- ✅ 코드 리뷰 완료 — Critical/High 이슈 없음
- Medium 이슈 1건: FactorScorer factors 파라미터에 부분 키만 전달 시 KeyError 발생 가능 (현재 호출부는 모두 안전, Phase 문서 미해결 사항 #7에 기록)

#### 자동 검증 결과 (2026-04-02)

- ✅ pytest 638 passed (0 failed, 53 warnings)
- ✅ API health check: 200 OK (database: connected, redis: connected)
- ✅ 데모 모드 API 검증: 1차 스크리닝 3팩터만 반환 확인 (volume_factor, momentum_factor, volatility_factor)
- ✅ PrimaryScreener pass_threshold=60.0 확인
- ✅ RealtimeScreener pass_threshold=75.0 확인
- ✅ FactorScorer 하위 호환 확인 (기본값 STOCK_FACTORS/ETF_FACTORS 사용)
- ✅ PRIMARY_FACTORS len=3, PRIMARY_WEIGHTS sum=1.0 확인

#### 수동 검증 필요 항목

- ⬜ 프로덕션 배포 후 다음 거래일 primary_screen passed > 0 확인 (장중 확인 필요)

---

## 참고

- 검증 원칙: `docs/dev-process.md` 섹션 5
- 배포 이력: `docs/deploy-history/`
- 롤백 방법: `docs/dev-process.md` 섹션 6.4
