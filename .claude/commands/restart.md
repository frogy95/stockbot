Docker Compose로 실행 중인 서비스를 재시작한다.

## 사용 방법

`$ARGUMENTS`를 기준으로 재시작할 서비스를 결정한다:

- 인수 없음 또는 `all`: 전체 스택 재시작 (`backend`, `frontend`)
- `backend`: 백엔드만 재시작
- `frontend`: 프론트엔드만 재시작
- `db`: postgres + redis 재시작
- 그 외 서비스명: 해당 서비스만 재시작

## 실행 절차

1. 아래 로직에 따라 Bash로 docker compose 명령을 실행한다. (프로젝트 루트에서 실행)

### 인수별 실행 명령

**인수 없음 또는 `all`:**
```bash
docker compose restart backend frontend
```

**`backend`:**
```bash
docker compose restart backend
```

**`frontend`:**
```bash
docker compose restart frontend
```

**`db`:**
```bash
docker compose restart postgres redis
```

**그 외 서비스명 (예: `redis`):**
```bash
docker compose restart <서비스명>
```

2. 재시작 후 컨테이너 상태를 확인한다:
```bash
docker compose ps
```

3. 결과를 사용자에게 간결하게 보고한다.
