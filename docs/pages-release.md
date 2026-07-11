# GitHub Pages 릴리스 운영

공식 Pages 주소의 base path는 `/2026-esports-landscape/`이며, 연구 페이지의 직접 주소는 `/2026-esports-landscape/research/`이다. `pages.yml`은 선택한 ref를 다시 빌드하고 `dist/` 전체를 하나의 Pages artifact로 업로드한다. `deploy-pages`가 이 artifact를 승격하는 지점이 atomic release 경계다.

## 배포 전 확인

워크플로의 human gate는 기본적으로 fail-closed다. `data/resource-map.v1.json`의 owner 승인과 AC01, 사용성 5명(각 4/5), 디자인 검토자 2명(R1–R5 각 5/5), repository owner, browser matrix 기록이 모두 `approved`이고 필요한 승인자·시각이 있어야 production deployment가 진행된다. 현재 승인 fixture는 `pending`이며, 이를 승인으로 간주하거나 수동으로 우회하지 않는다. GitHub의 `github-pages` environment에도 필요한 보호 규칙을 유지한다.

승인 후 배포 결과에서 다음 smoke check를 수행한다.

- `/2026-esports-landscape/` 및 `/2026-esports-landscape/research/`가 직접 열리는지 확인한다.
- 존재하지 않는 `/2026-esports-landscape/not-found-check`가 Pages의 404 응답인지 확인한다.
- `release-manifest.json`의 HTML, JavaScript, CSS, JSON/GeoJSON 자산에 선언된 MIME type과 응답 `Content-Type`을 대조하고, Pages cache 응답 헤더를 기록한다.

## 롤백

정상으로 확인된 최근 3개 commit SHA/ref를 보존한다. 문제가 생기면 **Run workflow**에서 그중 이전 정상 ref를 `source_ref`로 입력한다. 이 경로도 동일한 검증, human gate, 단일 artifact 승격을 거쳐 이전 소스를 재빌드·재배포하므로 artifact 일부만 교체하지 않는다.
