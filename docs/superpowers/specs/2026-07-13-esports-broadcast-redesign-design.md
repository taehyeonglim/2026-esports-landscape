# 리그 방송 그래픽 리디자인 — 디자인 스펙

- 날짜: 2026-07-13
- 상태: 사용자 승인 대기
- 대상: `index.html`, `research/index.html`, `styles/`, `src/app.js`(통계 리본 한정), `scripts/build.mjs`, `scripts/hash-dist.mjs`

## 목표

전국 학교 e스포츠 인덱스의 시각 디자인을 "리그 방송 그래픽"(딥네이비 + 골드/일렉트릭 블루, 사선 컷, 대형 타이포) 무드로 전면 교체한다. 데이터 계약·DOM 구조·접근성 기준은 그대로 유지한다.

## 확정된 요구사항

| 항목 | 결정 |
| --- | --- |
| 디자인 무드 | 리그 방송 그래픽 (롤드컵/LCK 방송 오버레이 느낌) |
| 변경 범위 | CSS 전면 재작성 + HTML은 기존 ID/구조 유지한 장식 요소만 추가 |
| 타이포 | 자기 호스팅 웹폰트 (외부 CDN 금지 — 릴리스 매니페스트가 모든 게시 바이트를 해시) |
| 모션 | 절제된 모션 + `prefers-reduced-motion: reduce` 시 전부 비활성 |
| 대상 페이지 | 메인 인덱스 + research/ 통일 |
| 아키텍처 | A안: 공유 디자인 토큰 파일 + 페이지별 CSS |

## 1. 디자인 시스템 (`styles/tokens.css` 신설)

### 1.1 색상 팔레트 — "리그 방송 나이트"

| 토큰 | 값 | 용도 |
| --- | --- | --- |
| `--bg-0` | `#0a1220` | 페이지 배경 (네이비 블랙) |
| `--bg-1` | `#0e1a2e` | 패널 배경 |
| `--bg-2` | `#14243c` | 카드/상승 표면 |
| `--line` | `#26415f` | 경계선 |
| `--ink` | `#e8eef7` | 본문 텍스트 |
| `--muted` | `#9fb2c8` | 보조 텍스트 |
| `--gold` | `#e3b341` | 시그니처 액센트 — 사선 컷, 상태 바, 활성 탭 |
| `--blue` | `#4da3ff` | 일렉트릭 블루 — 링크, 포커스, 보조 액센트 |
| `--verified` | `#35d6a7` | verified 상태 배지 |
| `--provisional` | `#f0a35e` | provisional 상태 배지 |

값은 시작점이며, 구현 중 WCAG AA(일반 텍스트 4.5:1, 대형 텍스트 3:1) 미달 조합이 발견되면 명도를 조정한다. 최종 판정 기준은 axe 브라우저 테스트(serious/critical 0건)다.

### 1.2 타이포그래피

- **본문(한글)**: Pretendard Std Variable 서브셋(현대 한글 2,780자, 단일 woff2 약 1MB) 자기 호스팅. `font-display: swap`, 폴백은 기존 시스템 폰트 체인(`system-ui, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif`).
- **디스플레이(영문 라벨·숫자)**: Rajdhani SemiBold/Bold latin 서브셋 woff2(합계 약 30KB). 아이브로우, 통계 숫자, 상태 배지, 카드 메타 라벨에 대문자 + 넓은 자간으로 사용.
- **헤드라인**: 한글이므로 Pretendard Black(900)으로 방송 타이틀 스타일.
- 두 폰트 모두 SIL OFL 라이선스 — 재배포 허용, 라이선스 파일을 `styles/fonts/`에 동봉한다.

### 1.3 질감·장식 (방송 그래픽 시그니처)

- **사선 컷**: 헤더 하단, 활성 탭, 카드 코너에 `clip-path` 사선 — 방송 로워서드(lower-third) 모티프.
- **골드 더블 라인**: 헤더/패널 제목 아래 굵은 골드 + 가는 블루 이중선.
- **배경 텍스처**: 딥네이비 그라디언트 + 저채도 사선 스트라이프(`repeating-linear-gradient`), 카드 뒤 미세 글로우.
- **상태 바**: 각 결과 카드 왼쪽 4px 세로 컬러 바(verified=`--verified`, provisional=`--provisional`).
- 장식은 최대한 CSS pseudo-element로 구현하고, 불가피할 때만 장식용 요소를 추가한다.

### 1.4 모션 (절제)

- 카드 호버: 골드 테두리 라이트업 + 미세 상승(150ms).
- 패널 진입: fade + 8px 상승(240ms).
- 포커스: 블루 글로우 아웃라인(`:focus-visible` 유지).
- `@media (prefers-reduced-motion: reduce)`에서 전환·변형 전부 비활성.

## 2. 페이지별 적용

### 2.1 메인 인덱스 (`index.html` + `styles/main.css` 재작성)

- **헤더**: 풀블리드 딥네이비 그라디언트 + 사선 스트라이프 텍스처. 아이브로우는 Rajdhani 골드 대문자, H1은 Pretendard Black 대형, 골드+블루 더블 라인, 헤더 하단 사선 컷.
- **통계 리본**(신규 장식 요소 1개): 헤더에 `230 ENTRIES · 17 REGIONS · 230 SOURCES` 방송 스코어보드 스타일 배지 줄. 숫자는 하드코딩하지 않고 `src/app.js`가 로드된 `site.v3.json`의 entries/regions/sources 배열 길이에서 채운다. 데이터 로드 실패 시 리본은 숨긴 채 유지한다(오류를 만들지 않는다). *(수정 2026-07-13: 원안의 `VERIFIED n`은 현재 데이터 전수가 `needs_review`라 "VERIFIED 0"으로 표시되어 오해를 유발하므로 `SOURCES`로 교체.)*
- **지역 선택 + 학교/대회/시설 버튼**: 방송 탭 스타일. 사선 컷 모서리, `aria-pressed=true` 시 골드 채움 + 네이비 글자.
- **결과 카드**: `--bg-2` 표면 + 좌측 상태 바, 메타 라벨(지역·분류) Rajdhani 대문자, 호버 시 골드 테두리 + 상승, `aria-current=true` 시 골드 강조 유지. 상태 바 색은 엔트리의 실제 어휘인 `operational_status`(current=민트, ended=회색, needs_review=앰버)를 따르며, 이를 위해 `src/cards.js`의 `createEntryCard`에 `card.dataset.status = entry.operational_status` 1줄을 추가한다. *(수정 2026-07-13: 원안의 verified/provisional은 파이프라인 어휘로 공개 엔트리에 없는 필드이며, 카드 DOM에 상태 속성이 없어 CSS만으로 구분 불가.)*
- **상세 패널**: 로워서드 스타일 제목 블록, 출처 링크는 `--blue`, dt/dd 라벨 그리드.
- **지도 패널**: 다크 배경 위 경계선 블루 글로우 스트로크, 선택 지역 골드 하이라이트. (SVG 스트로크 색이 JS/CSS 어디서 정의되는지 구현 시 확인하고, JS 하드코딩이면 CSS 변수로 옮기는 최소 수정 허용.)
- **푸터**: 다크 배경, 가는 라인, research 링크는 `--blue`.

### 2.2 research 페이지 (`research/index.html` + `styles/research.css` 재작성)

- 동일 토큰 사용, 헤더 모티프 공유.
- "해석의 전제" notice는 골드 보더 강조 패널.
- `fact-grid` 숫자는 Rajdhani 대형 스코어 스타일.

### 2.3 HTML 변경 목록 (기존 ID·data 속성·문서 구조 전부 유지)

1. 두 HTML에 `styles/tokens.css` `<link>` 추가 (기존 페이지 CSS보다 앞).
2. `index.html` 헤더에 통계 리본 요소 1개 추가.
3. `index.html` `<head>`에 디스플레이 폰트 preload 추가.
4. 그 외 마크업 변경 없음. e2e 계약 테스트가 참조하는 셀렉터(`#region-select`, `[data-type]`, `[data-entry-id]`, `#detail-panel`, `#detail-heading`, `#detail-content` 등)는 불변.

## 3. 폰트 자산과 빌드 파이프라인

- `styles/fonts/` 신설: `PretendardStd-Variable.woff2`, `Rajdhani-SemiBold.woff2`, `Rajdhani-Bold.woff2`, OFL 라이선스 파일.
- `scripts/build.mjs`: `publicFiles`의 styles 필터를 `.css`만 → `.css`/`.woff2`/`.txt`로 확장한다. OFL은 폰트 재배포 시 라이선스 동봉을 요구하므로 라이선스 텍스트도 게시 자산에 포함한다.
- `scripts/hash-dist.mjs`: MIME 맵에 `'.woff2': 'font/woff2'` 추가.
- 폰트 파일은 공식 배포처(GitHub 릴리스)에서 받아 체크섬을 기록한다.

## 4. 테스트·검증 (완료 기준)

| 검증 | 기준 |
| --- | --- |
| `npm run test:unit` | 16개 전부 통과 (테스트 수정 없이) |
| `npm run test:e2e` | 계약 테스트 통과 (DOM 구조 불변) |
| `npm run test:browser` | Playwright 통과 + axe serious/critical 위반 0건 |
| Python 테스트 114개 | 회귀 확인용 1회 실행, 전부 통과 |
| 비주얼 | 데스크톱/모바일 뷰포트 스크린샷으로 직접 확인 |

- JS 수정은 `src/app.js`의 통계 리본 연결 몇 줄, 통계 리본 전용 신규 모듈 `src/stat-ribbon.js`, `src/cards.js`의 dataset 1줄로 한정한다.
- 기존 테스트 파일은 수정하지 않는다. 통계 리본 동작 검증이 필요하면 테스트를 추가만 한다.

## 범위 밖 (하지 않는 것)

- 데이터 계약·스키마·파이프라인(Python) 변경.
- e2e 테스트가 참조하는 DOM 구조 변경.
- 라이트 테마/테마 토글 (다크 단일 테마).
- 외부 CDN 의존 추가.
- 게시(Pages 배포) — 이 스펙은 로컬 구현·검증까지만 다루며 배포는 기존 릴리스 절차를 따른다.
