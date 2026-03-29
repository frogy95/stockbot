#!/usr/bin/env bash
# hook 통합 테스트 스크립트
set -uo pipefail

GUARD=".claude/hooks/pretooluse-bash-guard.sh"
CHECKER=".claude/hooks/stop-doc-checker.sh"
PASS=0
FAIL=0

check() {
  local desc="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo "  ✅ $desc (exit $actual)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ $desc (expected exit $expected, got $actual)"
    FAIL=$((FAIL + 1))
  fi
}

echo "=== PreToolUse bash-guard: 차단 테스트 (exit 2) ==="

echo '{"tool_name":"Bash","tool_input":{"command":"cd /tmp && git status"}}' | bash "$GUARD" > /dev/null 2>&1
check "cd 체이닝" "2" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | bash "$GUARD" > /dev/null 2>&1
check "main push" "2" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git push origin develop"}}' | bash "$GUARD" > /dev/null 2>&1
check "develop push" "2" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin x"}}' | bash "$GUARD" > /dev/null 2>&1
check "force push" "2" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git reset --hard HEAD~1"}}' | bash "$GUARD" > /dev/null 2>&1
check "reset hard" "2" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git checkout -b feature/x"}}' | bash "$GUARD" > /dev/null 2>&1
check "잘못된 브랜치명" "2" "$?"

echo ""
echo "=== PreToolUse bash-guard: 허용 테스트 (exit 0) ==="

echo '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | bash "$GUARD" > /dev/null 2>&1
check "git status" "0" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git checkout -b phase1-sprint3"}}' | bash "$GUARD" > /dev/null 2>&1
check "정상 브랜치명 (phase)" "0" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git checkout -b hotfix/fix-login"}}' | bash "$GUARD" > /dev/null 2>&1
check "정상 브랜치명 (hotfix)" "0" "$?"

echo '{"tool_name":"Bash","tool_input":{"command":"git push origin phase1-sprint1"}}' | bash "$GUARD" > /dev/null 2>&1
check "다른 브랜치 push" "0" "$?"

echo '{"tool_name":"Write","tool_input":{"file_path":"test.txt"}}' | bash "$GUARD" > /dev/null 2>&1
check "Bash 아닌 도구" "0" "$?"

echo ""
echo "=== Stop doc-checker: 기본 동작 ==="

bash "$CHECKER" > /dev/null 2>&1
check "깨끗한 상태 → 빈 출력" "0" "$?"

echo ""
echo "=== doc-rules.json 검증 ==="

RULE_COUNT=$(jq '.rules | length' .claude/hooks/lib/doc-rules.json 2>/dev/null)
if [[ "$RULE_COUNT" == "7" ]]; then
  echo "  ✅ 규칙 7개 확인"
  PASS=$((PASS + 1))
else
  echo "  ❌ 규칙 수 불일치 (expected 7, got $RULE_COUNT)"
  FAIL=$((FAIL + 1))
fi

IDS=$(jq -r '[.rules[].id] | sort | join(",")' .claude/hooks/lib/doc-rules.json 2>/dev/null)
UIDS=$(jq -r '[.rules[].id] | unique | sort | join(",")' .claude/hooks/lib/doc-rules.json 2>/dev/null)
if [[ "$IDS" == "$UIDS" ]]; then UNIQUE="true"; else UNIQUE="false"; fi
if [[ "$UNIQUE" == "true" ]]; then
  echo "  ✅ 규칙 ID 유니크"
  PASS=$((PASS + 1))
else
  echo "  ❌ 규칙 ID 중복"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "=== 결과: ${PASS} passed, ${FAIL} failed ==="

if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
