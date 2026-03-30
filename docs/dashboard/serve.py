#!/usr/bin/env python3
"""대시보드 서버 — sprint 브랜치의 최신 index.json을 자동 병합하여 제공."""

import http.server
import json
import os
import subprocess
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
DOCS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_active_sprint_branches():
    """로컬 + 리모트에서 phase*-sprint* 브랜치 목록 반환."""
    try:
        result = subprocess.run(
            ["git", "branch", "-a", "--list", "*phase*-sprint*"],
            capture_output=True, text=True, cwd=DOCS_DIR, timeout=5,
        )
        branches = []
        for line in result.stdout.strip().splitlines():
            name = line.strip().lstrip("* ").replace("remotes/origin/", "")
            if name and name not in branches:
                branches.append(name)
        return branches
    except Exception:
        return []


def get_index_from_branch(branch):
    """특정 브랜치의 docs/index.json을 git show로 읽기."""
    try:
        result = subprocess.run(
            ["git", "show", f"{branch}:docs/index.json"],
            capture_output=True, text=True, cwd=DOCS_DIR, timeout=5,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def get_working_tree_index():
    """워킹 트리의 index.json 읽기."""
    path = os.path.join(DOCS_DIR, "index.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def get_branch_commit_count(branch):
    """해당 브랜치가 main에서 분기된 이후 커밋 수."""
    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"main..{branch}"],
            capture_output=True, text=True, cwd=DOCS_DIR, timeout=5,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except Exception:
        pass
    return 0


def get_completed_tasks_from_commits(branch):
    """브랜치 커밋 메시지에서 완료된 task 번호 추출."""
    try:
        result = subprocess.run(
            ["git", "log", f"main..{branch}", "--format=%s"],
            capture_output=True, text=True, cwd=DOCS_DIR, timeout=5,
        )
        completed = set()
        import re
        for line in result.stdout.strip().splitlines():
            # "task1", "task2" 등 패턴 매칭
            matches = re.findall(r'task(\d+)', line.lower())
            for m in matches:
                completed.add(f"task{m}")
        return completed
    except Exception:
        return set()


def parse_branch_name(branch):
    """브랜치명에서 phase_id, sprint_id 추출."""
    import re
    m = re.match(r'(phase[0-9.]+)-(sprint[0-9]+)', branch)
    if m:
        return m.group(1), m.group(2)
    return None, None


def merge_sprint_status(base, branch_data, branch_name):
    """branch_data에서 in_progress인 sprint 정보를 base에 병합."""
    if not base or not branch_data:
        return base

    branch_phases = {p["id"]: p for p in branch_data.get("phases", [])}

    for phase in base.get("phases", []):
        bp = branch_phases.get(phase["id"])
        if not bp:
            continue

        branch_sprints = {s["id"]: s for s in bp.get("sprints", [])}
        for sprint in phase.get("sprints", []):
            bs = branch_sprints.get(sprint["id"])
            if not bs:
                continue

            # 브랜치에서 더 진행된 상태면 덮어쓰기
            if bs.get("status") == "in_progress" and sprint.get("status") == "planned":
                sprint["status"] = bs["status"]
                sprint["progress"] = bs.get("progress", sprint.get("progress", {}))
                sprint["tasks"] = bs.get("tasks", sprint.get("tasks", []))

            if bs.get("status") == "in_progress" and phase.get("status") == "planned":
                phase["status"] = "in_progress"

    # lastUpdated를 최신으로
    if branch_data.get("lastUpdated", "") > base.get("lastUpdated", ""):
        base["lastUpdated"] = branch_data["lastUpdated"]

    return base


def infer_status_from_branch(base, branch):
    """브랜치에 index.json 반영이 안 된 경우, 커밋 히스토리에서 상태 추론."""
    phase_id, sprint_id = parse_branch_name(branch)
    if not phase_id or not sprint_id:
        return base

    commit_count = get_branch_commit_count(branch)
    if commit_count == 0:
        return base  # 커밋이 없으면 아직 시작 안 한 것

    completed_tasks = get_completed_tasks_from_commits(branch)

    for phase in base.get("phases", []):
        if phase["id"] != phase_id:
            continue

        if phase.get("status") == "planned":
            phase["status"] = "in_progress"

        for sprint in phase.get("sprints", []):
            if sprint["id"] != sprint_id:
                continue

            if sprint.get("status") in ("planned", None):
                sprint["status"] = "in_progress"

            # task 상태 업데이트
            for task in sprint.get("tasks", []):
                if task["id"] in completed_tasks and task.get("status") != "completed":
                    task["status"] = "completed"

            # progress 재계산
            total = len(sprint.get("tasks", []))
            done = sum(1 for t in sprint.get("tasks", []) if t.get("status") == "completed")
            sprint["progress"] = {"total": total, "completed": done}

    return base


def build_merged_index():
    """워킹 트리 index.json + 활성 sprint 브랜치 병합."""
    base = get_working_tree_index()
    if not base:
        return None

    branches = get_active_sprint_branches()
    for branch in branches:
        # 완료된 브랜치(phase0.5-sprint1 등)는 건너뛰기
        phase_id, sprint_id = parse_branch_name(branch)
        if phase_id and sprint_id:
            for p in base.get("phases", []):
                if p["id"] == phase_id:
                    for s in p.get("sprints", []):
                        if s["id"] == sprint_id and s.get("status") == "completed":
                            continue

        branch_data = get_index_from_branch(branch)
        if branch_data:
            base = merge_sprint_status(base, branch_data, branch)

        # 브랜치의 index.json에 해당 phase가 없으면 커밋에서 추론
        base = infer_status_from_branch(base, branch)

    # git log에서 기여도 집계하여 task.assignee 주입
    inject_contributors(base)

    return base


def inject_contributors(data):
    """git log에서 커밋 author별 기여도를 집계하여 task.assignee에 주입."""
    try:
        result = subprocess.run(
            ["git", "log", "--all", "--format=%an|||%s"],
            capture_output=True, text=True, cwd=DOCS_DIR, timeout=5,
        )
        if result.returncode != 0:
            return
    except Exception:
        return

    import re
    # task 커밋 → author 매핑 (task{N} 패턴)
    task_authors = {}  # "phase2/sprint1/task3" → "author"
    for line in result.stdout.strip().splitlines():
        if "|||" not in line:
            continue
        author, msg = line.split("|||", 1)
        # 브랜치 정보는 커밋 메시지에서 추론: "feat(phase2-sprint1): task3 --"
        branch_match = re.search(r'phase[0-9.]+-sprint[0-9]+', msg)
        task_match = re.search(r'task(\d+)', msg.lower())
        if branch_match and task_match:
            key = f"{branch_match.group()}/task{task_match.group(1)}"
            task_authors[key] = author.strip()

    # assignee 주입
    for phase in data.get("phases", []):
        for sprint in phase.get("sprints", []):
            branch_key = f"{phase['id']}-{sprint['id']}"
            for task in sprint.get("tasks", []):
                key = f"{branch_key}/{task['id']}"
                if key in task_authors and not task.get("assignee"):
                    task["assignee"] = task_authors[key]


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DOCS_DIR, **kwargs)

    def do_GET(self):
        # /index.json 요청 시 병합된 데이터 반환
        if self.path == "/index.json" or self.path == "/../index.json":
            data = build_merged_index()
            if data:
                content = json.dumps(data, ensure_ascii=False, indent=2).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return

        # 나머지는 정적 파일 서빙
        super().do_GET()

    def log_message(self, format, *args):
        pass  # 로그 끄기


if __name__ == "__main__":
    server = http.server.HTTPServer(("", PORT), DashboardHandler)
    print(f"📊 대시보드 서버: http://localhost:{PORT}/dashboard/")
    print(f"   sprint 브랜치 자동 감지 + index.json 병합 활성")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")
