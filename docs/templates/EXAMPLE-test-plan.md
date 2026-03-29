> **이 파일은 예제입니다.** sprint-planner 에이전트가 Task별 테스트 계획을 생성할 때 참조합니다.
> 위치: `docs/phase/phase{N}/sprint{N}/task{N}/test-plan.md`

# 테스트 계획 — Task {N}: {컴포넌트명}

**Sprint:** Phase {P} - Sprint {S}
**작성일:** {YYYY-MM-DD}

---

## 테스트 범위

### 포함
- {테스트할 기능/동작}

### 제외
- {이 Task에서 테스트하지 않는 항목}

---

## 단위 테스트

| # | 테스트명 | 입력 | 예상 결과 | 우선순위 |
|---|---------|------|----------|---------|
| 1 | {test_name} | {input} | {expected} | High |

---

## 통합 테스트

| # | 시나리오 | 전제 조건 | 실행 단계 | 예상 결과 |
|---|---------|----------|----------|----------|
| 1 | {scenario} | {precondition} | {steps} | {expected} |

---

## 검증 명령

```bash
# 단위 테스트
{test_command}

# 통합 테스트
{integration_test_command}

# API 검증
{curl_command}
```

---

## 엣지 케이스

- {빈 입력, null 값, 경계값 등}
