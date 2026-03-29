프로젝트 대시보드를 로컬 HTTP 서버로 띄워 브라우저에서 엽니다.

## 실행

1. 기존 대시보드 서버가 떠 있으면 종료한다:
```bash
lsof -ti:8080 | xargs kill -9 2>/dev/null; echo "기존 서버 정리 완료"
```

2. 대시보드 서버를 백그라운드로 띄운다:
```bash
python3 docs/dashboard/serve.py 8080 &>/dev/null &
echo "대시보드 서버 시작: http://localhost:8080/dashboard/"
```

3. 브라우저에서 대시보드를 연다:
```bash
open http://localhost:8080/dashboard/
```

대시보드는 `docs/index.json`의 데이터를 기반으로 프로젝트 상태를 표시합니다.
sprint 브랜치가 활성 상태면 해당 브랜치의 index.json을 자동 병합하여 최신 진행 상황을 표시합니다.

> 서버를 종료하려면: `lsof -ti:8080 | xargs kill -9`
