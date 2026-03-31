#!/usr/bin/env bash
# PreToolUse hook: Bash 위험 명령 차단
# stdin: {"tool_name":"Bash","tool_input":{"command":"..."}}
# exit 0 = 허용, exit 2 = 차단 (stdout 메시지가 Claude에 전달)

set -euo pipefail

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$CMD" ]]; then
  exit 0
fi

# 패턴 1: cd ... && 체이닝
if echo "$CMD" | grep -qE '^cd\s+.+\s*&&'; then
  echo '❌ CLAUDE.md 규칙 위반: "cd /path && ..." 형식은 금지됩니다.'
  echo '프로젝트 루트에서 직접 실행하세요.'
  exit 2
fi

# 패턴 2: git push origin main
if echo "$CMD" | grep -qE 'git\s+push\s+origin\s+main(\s|$)'; then
  echo '❌ main 브랜치 직접 push 금지. PR을 통해 merge하세요.'
  exit 2
fi

# 패턴 3: git push origin develop — docs 전용 커밋은 예외 허용
if echo "$CMD" | grep -qE 'git\s+push\s+origin\s+develop(\s|$)'; then
  # 원격 develop 대비 변경된 파일 목록 확인
  CHANGED=$(git diff origin/develop..HEAD --name-only 2>/dev/null || echo "")
  if [[ -z "$CHANGED" ]]; then
    echo '❌ develop 브랜치 직접 push 금지. PR을 통해 merge하세요.'
    exit 2
  fi
  # docs/, deploy.md, MEMORY.md 외 코드/설정 파일이 있으면 차단
  NON_DOCS=$(echo "$CHANGED" | grep -vE '^(docs/|deploy\.md$|MEMORY\.md$)' || true)
  if [[ -n "$NON_DOCS" ]]; then
    echo '❌ develop 브랜치 직접 push 금지. PR을 통해 merge하세요.'
    echo "코드/설정 변경 파일 감지: $(echo "$NON_DOCS" | head -5)"
    exit 2
  fi
  # docs 전용 커밋 → 허용
  exit 0
fi

# 패턴 4: git push --force
if echo "$CMD" | grep -qE 'git\s+push\s+.*--force'; then
  echo '❌ force push 금지. 이력이 파괴될 수 있습니다.'
  exit 2
fi

# 패턴 5: git reset --hard
if echo "$CMD" | grep -qE 'git\s+reset\s+--hard'; then
  echo '❌ git reset --hard 금지. 변경사항이 소실될 수 있습니다.'
  exit 2
fi

# 패턴 6: git checkout -b 잘못된 브랜치명
if echo "$CMD" | grep -qE 'git\s+checkout\s+-b\s+'; then
  BRANCH=$(echo "$CMD" | grep -oE 'git\s+checkout\s+-b\s+(\S+)' | awk '{print $NF}')
  if [[ -n "$BRANCH" ]]; then
    if ! echo "$BRANCH" | grep -qE '^phase[0-9]+(\.[0-9]+)?-sprint[0-9]+$' && \
       ! echo "$BRANCH" | grep -qE '^hotfix/'; then
      echo "❌ 브랜치명 규칙 위반: \"$BRANCH\""
      echo '허용 형식: phase{P}-sprint{N} (예: phase1-sprint3, phase2.5-sprint1) 또는 hotfix/* (예: hotfix/fix-login)'
      exit 2
    fi
  fi
fi

# 패턴 7: develop/main 브랜치에서 sprint 관련 커밋 차단
if echo "$CMD" | grep -qE 'git\s+commit\s'; then
  CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
  if [[ "$CURRENT_BRANCH" == "develop" || "$CURRENT_BRANCH" == "main" ]]; then
    # 커밋 메시지에서 sprint/phase 키워드 감지 (-m "..." 또는 -m '...' 또는 heredoc)
    if echo "$CMD" | grep -qiE '(sprint|phase[0-9])'; then
      echo "❌ $CURRENT_BRANCH 브랜치에서 sprint/phase 관련 커밋 금지."
      echo "먼저 sprint 브랜치를 생성하세요: git checkout -b phase{P}-sprint{N}"
      exit 2
    fi
  fi
fi

exit 0
