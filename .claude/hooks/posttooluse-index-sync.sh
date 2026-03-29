#!/usr/bin/env bash
# PostToolUse hook: git 명령 감지 → index.json 상태 자동 동기화
#
# 감지 1: git checkout -b phase{P}-sprint{N}
#   → sprint.status를 "in_progress"로, 모든 task에 status 필드가 없으면 "planned" 추가
#
# 감지 2: git commit (sprint 브랜치에서)
#   → 커밋 메시지에서 task 제목을 매칭하여 task.status → "completed", progress 갱신
#
# stdin: {"tool_name":"Bash","tool_input":{"command":"..."},"tool_result":{"stdout":"...","stderr":"...","exit_code":0}}

set -euo pipefail

INDEX_FILE="docs/index.json"

# index.json 없으면 종료
if [[ ! -f "$INDEX_FILE" ]]; then
  exit 0
fi

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')

if [[ "$TOOL_NAME" != "Bash" ]]; then
  exit 0
fi

CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
EXIT_CODE=$(echo "$INPUT" | jq -r '.tool_result.exit_code // "1"')

# 실패한 명령은 무시
if [[ "$EXIT_CODE" != "0" ]]; then
  exit 0
fi

# ============================================================
# 감지 1: git checkout -b phase{P}-sprint{N}
# ============================================================
if echo "$CMD" | grep -qE 'git\s+checkout\s+-b\s+phase[0-9.]+-sprint[0-9]+'; then
  BRANCH=$(echo "$CMD" | grep -oE 'phase[0-9.]+-sprint[0-9]+')
  PHASE_ID=$(echo "$BRANCH" | grep -oE 'phase[0-9.]+')
  SPRINT_ID=$(echo "$BRANCH" | grep -oE 'sprint[0-9]+')

  # sprint status → in_progress, task에 status 필드 보장
  UPDATED=$(jq --arg pid "$PHASE_ID" --arg sid "$SPRINT_ID" '
    .phases |= map(
      if .id == $pid then
        .status = "in_progress" |
        .sprints |= map(
          if .id == $sid then
            .status = "in_progress" |
            .tasks |= map(
              if .status == null then .status = "planned" else . end
            )
          else . end
        )
      else . end
    ) |
    .lastUpdated = (now | strftime("%Y-%m-%d"))
  ' "$INDEX_FILE")

  echo "$UPDATED" > "$INDEX_FILE"
  echo "📊 index.json 동기화: $PHASE_ID/$SPRINT_ID → in_progress"
  exit 0
fi

# ============================================================
# 감지 2: git commit (sprint 브랜치에서)
# ============================================================
if echo "$CMD" | grep -qE 'git\s+commit\s'; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "")

  # sprint 브랜치가 아니면 무시
  if ! echo "$BRANCH" | grep -qE '^phase[0-9.]+-sprint[0-9]+$'; then
    exit 0
  fi

  PHASE_ID=$(echo "$BRANCH" | grep -oE 'phase[0-9.]+')
  SPRINT_ID=$(echo "$BRANCH" | grep -oE 'sprint[0-9]+')

  # 최신 커밋 정보
  COMMIT_HASH=$(git log -1 --format="%h" 2>/dev/null || echo "")
  COMMIT_MSG=$(git log -1 --format="%s" 2>/dev/null || echo "")
  COMMIT_DATE=$(date +%Y-%m-%d)

  # chore 커밋은 task 매칭 대상 아님
  if echo "$COMMIT_MSG" | grep -qE '^chore:'; then
    exit 0
  fi

  # index.json에서 해당 sprint의 task 제목들을 가져와 매칭
  UPDATED=$(jq --arg pid "$PHASE_ID" --arg sid "$SPRINT_ID" \
    --arg hash "$COMMIT_HASH" --arg msg "$COMMIT_MSG" --arg date "$COMMIT_DATE" '
    .phases |= map(
      if .id == $pid then
        .sprints |= map(
          if .id == $sid then
            # task 매칭: 커밋 메시지에 task 제목이 포함되면 completed 처리
            .tasks |= map(
              if (.status != "completed") and ($msg | ascii_downcase | contains(.title | ascii_downcase)) then
                .status = "completed" |
                .commits = ((.commits // []) + [{"hash": $hash, "message": $msg, "date": $date}])
              elif (.status != "completed") and ($msg | ascii_downcase | contains(.id | ascii_downcase)) then
                .status = "completed" |
                .commits = ((.commits // []) + [{"hash": $hash, "message": $msg, "date": $date}])
              else . end
            ) |
            # progress 재계산
            .progress.completed = ([.tasks[] | select(.status == "completed")] | length) |
            .progress.total = (.tasks | length)
          else . end
        )
      else . end
    ) |
    .lastUpdated = (now | strftime("%Y-%m-%d"))
  ' "$INDEX_FILE")

  # 변경이 있었는지 확인
  OLD_COMPLETED=$(jq --arg pid "$PHASE_ID" --arg sid "$SPRINT_ID" '
    [.phases[] | select(.id == $pid) | .sprints[] | select(.id == $sid) | .tasks[] | select(.status == "completed")] | length
  ' "$INDEX_FILE")

  echo "$UPDATED" > "$INDEX_FILE"

  NEW_COMPLETED=$(jq --arg pid "$PHASE_ID" --arg sid "$SPRINT_ID" '
    [.phases[] | select(.id == $pid) | .sprints[] | select(.id == $sid) | .tasks[] | select(.status == "completed")] | length
  ' "$INDEX_FILE")

  if [[ "$NEW_COMPLETED" != "$OLD_COMPLETED" ]]; then
    TOTAL=$(jq --arg pid "$PHASE_ID" --arg sid "$SPRINT_ID" '
      .phases[] | select(.id == $pid) | .sprints[] | select(.id == $sid) | .progress.total
    ' "$INDEX_FILE")
    echo "📊 index.json 동기화: task 완료 ($NEW_COMPLETED/$TOTAL)"
  fi

  exit 0
fi

exit 0
