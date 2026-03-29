프로젝트 대시보드를 브라우저에서 엽니다.

## 실행

```bash
open docs/dashboard/index.html
```

대시보드가 열리면 `docs/index.json`의 데이터를 기반으로 프로젝트 상태를 확인할 수 있습니다.

> **참고**: 대시보드는 `fetch('../index.json')`으로 데이터를 로드합니다.
> `file://` 프로토콜에서는 CORS로 인해 로드가 실패할 수 있습니다.
> 이 경우 로컬 서버를 사용하세요: `cd docs && python3 -m http.server 8080` → `http://localhost:8080/dashboard/`
