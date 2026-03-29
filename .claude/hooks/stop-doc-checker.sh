#!/usr/bin/env bash
# Stop hook: 에이전트 종료 시 문서 업데이트 누락 검증
# 변경 파일 패턴으로 에이전트 작업을 추론하고, 필수 파일 업데이트 여부를 체크한다.
# stdout 출력 → Claude가 읽고 보충 작업 수행

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RULES_FILE="$SCRIPT_DIR/lib/doc-rules.json"

if [[ ! -f "$RULES_FILE" ]]; then
  exit 0
fi

# --- 변경 파일 수집 ---
CHANGED_FILES=$(
  {
    git diff --name-only 2>/dev/null || true
    git diff --name-only --cached 2>/dev/null || true
    git diff --name-only HEAD~1..HEAD 2>/dev/null || true
  } | sort -u
)

if [[ -z "$CHANGED_FILES" ]]; then
  exit 0
fi

# --- 현재 브랜치 ---
BRANCH=$(git branch --show-current 2>/dev/null || echo "")

# --- 에이전트 추론 ---
DETECTED_AGENT=""

# 추론 1: prd-to-roadmap — ROADMAP.md 신규 생성
if echo "$CHANGED_FILES" | grep -qE '^ROADMAP\.md$'; then
  if ! git show HEAD~1:ROADMAP.md &>/dev/null 2>&1; then
    DETECTED_AGENT="prd-to-roadmap"
  fi
fi

# 추론 2: phase-planner — phase{N}.md 신규 생성
if [[ -z "$DETECTED_AGENT" ]]; then
  if echo "$CHANGED_FILES" | grep -qE 'docs/phase/phase[0-9]+/phase[0-9]+\.md$'; then
    PHASE_FILE=$(echo "$CHANGED_FILES" | grep -E 'docs/phase/phase[0-9]+/phase[0-9]+\.md$' | head -1)
    if ! git show "HEAD~1:$PHASE_FILE" &>/dev/null 2>&1; then
      DETECTED_AGENT="phase-planner"
    fi
  fi
fi

# 추론 3: sprint-planner — sprint{N}.md 신규 생성
if [[ -z "$DETECTED_AGENT" ]]; then
  if echo "$CHANGED_FILES" | grep -qE 'docs/phase/phase[0-9]+/sprint[0-9]+/sprint[0-9]+\.md$'; then
    SPRINT_FILE=$(echo "$CHANGED_FILES" | grep -E 'docs/phase/phase[0-9]+/sprint[0-9]+/sprint[0-9]+\.md$' | head -1)
    if ! git show "HEAD~1:$SPRINT_FILE" &>/dev/null 2>&1; then
      DETECTED_AGENT="sprint-planner"
    fi
  fi
fi

# 추론 4: sprint-close — ROADMAP.md 수정 + PR 존재
if [[ -z "$DETECTED_AGENT" ]]; then
  if echo "$CHANGED_FILES" | grep -qE '^ROADMAP\.md$'; then
    if [[ -n "$BRANCH" ]] && gh pr list --head "$BRANCH" --state open --json number --jq 'length' 2>/dev/null | grep -q '[1-9]'; then
      DETECTED_AGENT="sprint-close"
    fi
  fi
fi

# 추론 5: sprint-review — deploy.md에 검증 결과 키워드
if [[ -z "$DETECTED_AGENT" ]]; then
  if echo "$CHANGED_FILES" | grep -qE '^deploy\.md$'; then
    if git diff deploy.md 2>/dev/null | grep -qE '^\+.*(자동 검증|pytest|Playwright)'; then
      DETECTED_AGENT="sprint-review"
    elif git diff --cached deploy.md 2>/dev/null | grep -qE '^\+.*(자동 검증|pytest|Playwright)'; then
      DETECTED_AGENT="sprint-review"
    elif git diff HEAD~1..HEAD -- deploy.md 2>/dev/null | grep -qE '^\+.*(자동 검증|pytest|Playwright)'; then
      DETECTED_AGENT="sprint-review"
    fi
  fi
fi

# 추론 6: hotfix-close — hotfix/* 브랜치
if [[ -z "$DETECTED_AGENT" ]]; then
  if [[ "$BRANCH" == hotfix/* ]]; then
    DETECTED_AGENT="hotfix-close"
  fi
fi

# 추론 7: deploy-prod — develop→main PR 존재
if [[ -z "$DETECTED_AGENT" ]]; then
  if gh pr list --head develop --base main --state open --json number --jq 'length' 2>/dev/null | grep -q '[1-9]'; then
    DETECTED_AGENT="deploy-prod"
  fi
fi

# 에이전트 추론 실패 → 종료
if [[ -z "$DETECTED_AGENT" ]]; then
  exit 0
fi

# --- 규칙 체크 ---
RULE=$(jq -r --arg id "$DETECTED_AGENT" '.rules[] | select(.id == $id)' "$RULES_FILE")

if [[ -z "$RULE" ]]; then
  exit 0
fi

MISSING_COUNT=0
WARNINGS=""

add_warning() {
  MISSING_COUNT=$((MISSING_COUNT + 1))
  WARNINGS="${WARNINGS}${MISSING_COUNT}. $1\n"
}

# 필수 파일 체크
REQUIRED=$(echo "$RULE" | jq -r '.required[]? // empty')
for REQ in $REQUIRED; do
  if ! echo "$CHANGED_FILES" | grep -qF "$REQ"; then
    add_warning "$REQ — 이 파일이 업데이트되지 않았습니다"
  fi
done

# 추가 체크
CHECKS=$(echo "$RULE" | jq -c '.checks[]? // empty' 2>/dev/null)
while IFS= read -r CHECK; do
  [[ -z "$CHECK" ]] && continue

  CHECK_TYPE=$(echo "$CHECK" | jq -r '.type // empty')
  CHECK_MSG=$(echo "$CHECK" | jq -r '.msg // empty')

  case "$CHECK_TYPE" in
    "grep_content")
      FILE=$(echo "$CHECK" | jq -r '.file')
      PATTERN=$(echo "$CHECK" | jq -r '.pattern')
      if [[ -f "$FILE" ]] && ! grep -qE "$PATTERN" "$FILE" 2>/dev/null; then
        add_warning "$CHECK_MSG"
      fi
      ;;

    "glob_min")
      GLOB_PATTERN=$(echo "$CHECK" | jq -r '.glob')
      MIN=$(echo "$CHECK" | jq -r '.min')
      COUNT=$(find . -path "./$GLOB_PATTERN" 2>/dev/null | wc -l | tr -d ' ')
      if [[ "$COUNT" -lt "$MIN" ]]; then
        add_warning "$CHECK_MSG"
      fi
      ;;

    "archive")
      TODAY=$(date +%Y-%m-%d)
      if ! echo "$CHANGED_FILES" | grep -qE "docs/deploy-history/.*\.md$"; then
        if [[ ! -f "docs/deploy-history/${TODAY}.md" ]]; then
          add_warning "$CHECK_MSG"
        fi
      fi
      ;;

    "pr_target")
      EXPECT=$(echo "$CHECK" | jq -r '.expect')
      if [[ -n "$BRANCH" ]]; then
        PR_BASE=$(gh pr list --head "$BRANCH" --state open --json baseRefName --jq '.[0].baseRefName' 2>/dev/null || echo "")
        if [[ -n "$PR_BASE" && "$PR_BASE" != "$EXPECT" ]]; then
          add_warning "$CHECK_MSG (현재: $PR_BASE)"
        fi
      fi
      ;;

    "checkbox_remaining")
      PATTERN=$(echo "$CHECK" | jq -r '.pattern')
      SPRINT_FILES=$(echo "$CHANGED_FILES" | grep -E 'docs/phase/phase[0-9]+/sprint[0-9]+/sprint[0-9]+\.md$' || true)
      for SF in $SPRINT_FILES; do
        if [[ -f "$SF" ]] && grep -q "$PATTERN" "$SF" 2>/dev/null; then
          add_warning "$CHECK_MSG (파일: $SF)"
          break
        fi
      done
      ;;

    "phase_update")
      if ! echo "$CHANGED_FILES" | grep -qE 'docs/phase/phase[0-9]+/phase[0-9]+\.md$'; then
        add_warning "$CHECK_MSG"
      fi
      ;;

    "critical_unresolved")
      if [[ -f "deploy.md" ]] && grep -iE '(critical|high)' deploy.md 2>/dev/null | grep -q '⬜'; then
        add_warning "$CHECK_MSG"
      fi
      ;;

    "hotfix_scope")
      MAX_FILES=$(echo "$CHECK" | jq -r '.max_files')
      MAX_LINES=$(echo "$CHECK" | jq -r '.max_lines')
      SRC_FILES=$(echo "$CHANGED_FILES" | grep -v '^docs/' | grep -v '^\.' | grep -v '^deploy\.md$' | wc -l | tr -d ' ')
      if [[ "$SRC_FILES" -gt "$MAX_FILES" ]]; then
        add_warning "$CHECK_MSG (변경 소스 파일: ${SRC_FILES}개)"
      fi
      TOTAL_LINES=$(git diff --stat HEAD~1..HEAD 2>/dev/null | tail -1 | grep -oE '[0-9]+ insertion' | grep -oE '[0-9]+' || echo "0")
      if [[ "$TOTAL_LINES" -gt "$MAX_LINES" ]]; then
        add_warning "$CHECK_MSG (변경 줄 수: ${TOTAL_LINES}줄)"
      fi
      ;;
  esac
done <<< "$CHECKS"

# --- 결과 출력 ---
if [[ "$MISSING_COUNT" -gt 0 ]]; then
  echo ""
  echo "⚠️ 문서 업데이트 누락 감지 (${DETECTED_AGENT} 작업 추정):"
  echo ""
  echo -e "$WARNINGS"
  echo "완료 전에 위 파일들을 업데이트해주세요."
fi

exit 0
