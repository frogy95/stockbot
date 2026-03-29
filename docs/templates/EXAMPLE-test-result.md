> **이 파일은 예제입니다.** sprint-dev 커맨드가 Task 검증 후 결과를 기록합니다.
> 위치: `docs/phase/phase{N}/sprint{N}/task{N}/test-result.md`

# 테스트 결과 — Task {N}: {컴포넌트명}

**Sprint:** Phase {P} - Sprint {S}
**실행일:** {YYYY-MM-DD}
**실행자:** {assignee}

---

## 요약

| 항목 | 결과 |
|------|------|
| 단위 테스트 | ✅ {N} passed / ❌ {N} failed |
| 통합 테스트 | ✅ {N} passed / ❌ {N} failed |
| API 검증 | ✅ 통과 / ❌ 실패 |
| 전체 결과 | ✅ PASS / ❌ FAIL |

---

## 상세 결과

### 단위 테스트

```
{pytest 출력 또는 테스트 로그}
```

### 통합 테스트

```
{통합 테스트 출력}
```

### API 검증

```
{curl 응답}
```

---

## 실패 항목 (있는 경우)

| # | 테스트명 | 실패 원인 | 조치 |
|---|---------|----------|------|
| 1 | {test_name} | {failure_reason} | {action_taken} |
