# ADR 0002: 미성년자 데이터의 비식별 수집 경계

- **상태:** Accepted
- **날짜:** 2026-07-11

## Decision

미성년자가 관련될 수 있는 공개 자료는 원문을 보존하지 않는 일회성(raw ephemeral) 처리 경계에서만 다룬다. HTTP(S) 정책에 맞게 가져온 응답 bytes는 메모리의 단일 처리 단계에서 최소 사실을 추출하고, 허용된 타입별 필드 allowlist와 sanitizer를 통과한 값만 제어 평면에 전달한 뒤 즉시 폐기한다. raw body, 원문 텍스트, 발췌문, 스크린샷 및 이들의 재구성 가능한 bytes는 로그·데이터베이스·큐·테스트 fixture·백업·오류 보고에 보존하지 않는다.

허용 대상은 공개적으로 검증 가능한 기관 또는 집계 수준의 사실뿐이다. 미성년자의 이름, 닉네임/계정, 연락처, 정확한 위치, 개인을 식별하는 일정, 이미지 및 다른 식별 가능 개인 정보는 허용하지 않는다. sanitizer는 값뿐 아니라 URL, 경로, 제목, locator와 예외 메시지를 검사·정규화한다. URL은 공개 HTTP(S)와 승인된 host만 허용하며 query/fragment/path 또는 title/locator/예외가 PII 또는 비허용 원문을 포함하면 안전한 reason code와 opaque ID로 치환하고 해당 항목을 거부한다.

저장은 typed allowlist와 sanitizer 뒤의 writer가 **독립적으로 다시 검사**할 때만 가능하다. writer는 예상 타입 밖 필드, 비공개 URL, PII 탐지, 안전하지 않은 diagnostic을 fail-closed로 거부한다. 탐지기는 직접 식별자, 형식 기반 식별자 및 문맥 결합 신호를 검사하지만, 합성 탐지는 알려진 패턴·사전·규칙으로 검출 가능한 조합에만 보장된다. 탐지 실패가 비식별성을 증명하지 않으며, 불확실한 값은 허용하지 않는다.

의심·오류·정책 모호·PII 가능 자료는 opaque quarantine으로만 기록한다. quarantine에는 case ID, reason code, 시각 및 PII 없는 안전한 진단 메타데이터만 둘 수 있고, body·text·발췌·PII는 둘 수 없다. quarantine은 공개 또는 정상 저장으로 승격될 수 없으며, 새로 준수하는 수집과 검토만 별도 후보를 만들 수 있다.

공개 누출은 removal-only 절차로 대응한다. 현재 공개본에서 영향을 받은 레코드만 삭제한 검증된 대체 snapshot을 만들며, 살아남는 레코드는 byte-for-byte 변경하지 않고 추가·수정도 하지 않는다. 그것도 안전하지 않으면 `current.json` 포인터를 제거한다. Git history, Issue/PR·댓글, CI/배포 artifact, 로그, GitHub Pages 및 캐시를 조사·삭제 또는 무효화하고, 노출 가능성이 있는 token·deploy key·webhook·credential을 회전/폐기한다. 티켓과 incident 기록에는 PII 대신 opaque ID와 안전한 메타데이터만 남긴다.

보존 경계는 명시적이다. raw bytes와 PII는 보존 기간 0으로 처리 종료 시 폐기한다. 제어 평면에는 sanitize된 claim/evidence, 정책·검토·감사 결정 및 opaque quarantine 메타데이터만 보존한다. 공개 snapshot은 immutable이므로 수정하지 않으며, 유해 자료는 삭제된 replacement 또는 포인터 제거로 철회한다. 제어 평면의 영향을 받은 sanitize된 값과 quarantine 메타데이터도 incident 검증 후 삭제하며, 보존 대상 감사 기록은 PII 없는 결정을 유지한다.

## Drivers

- 학교 e스포츠 자료에는 미성년자 식별 정보가 섞일 위험이 높다.
- 공개 데이터는 재현 가능해야 하지만 raw 원문 보존은 필요하지 않으며 위험만 늘린다.
- 한 단계의 필터 실패가 private SQLite, immutable snapshot 또는 GitHub Pages로 전파되어서는 안 된다.
- `docs/source-policy.md`, 운영 stop/withdrawal 및 recovery 절차의 PII 0 gate를 구현 가능한 경계로 고정해야 한다.

## Alternatives

1. **암호화한 원문 저장:** 복호화 권한·백업·키 회전·사고 범위를 늘리므로 거부한다.
2. **수집 후 비동기 sanitizer:** raw가 큐·로그·오류 경로에 남을 수 있으므로 거부한다.
3. **값만 검사하고 URL/title/locator/exception을 신뢰:** 식별자가 metadata와 diagnostic으로 누출될 수 있으므로 거부한다.
4. **quarantine에 원문을 보관:** 검토 편의보다 미성년자 PII 보존 위험이 크므로 거부한다.
5. **누출 시 기존 snapshot 수정 또는 일반 업데이트:** immutable 검증과 removal-only 안전성을 깨므로 거부한다.

## Consequences

- 수집기, 변환기, writer 및 출판 gate는 각각 타입과 PII 검사를 수행해야 한다.
- 검토자는 원문을 열람하지 않고 safe metadata와 새 준수 수집을 기반으로 판단한다.
- 허용되지 않거나 불확실한 정보는 데이터 완전성보다 안전을 우선해 누락·격리된다.
- 공개 PII finding은 0이어야 하며, 누출 대응은 Git·Issue·artifact·token·Pages까지 포함하는 운영 작업이 된다.

## Verification

- 각 typed allowlist에 대해 허용 기관/집계 claim과 미허용 미성년자 식별자, URL query/path, title, locator, exception payload를 주입해 sanitizer와 writer 모두 거부하는지 확인한다.
- raw body와 발췌가 database, 로그, quarantine, fixture, artifact 및 backup 후보에 남지 않는지 저장 경계를 검사한다.
- PII 의심 항목이 opaque case ID와 reason code만 가진 quarantine으로 가고, publication 경로에 참조되지 않는지 확인한다.
- 합성 탐지의 보장 패턴과 보장하지 않는 불확실 조합을 fixture로 고정하고, 후자는 fail-closed인지 확인한다.
- PII incident drill에서 removal-only snapshot의 생존 bytes 불변성 또는 포인터 제거, Git/Issue/artifact 정리, token 회전, Pages URL·cache 무노출을 검증한다.

## Revisit triggers

PII 법령 또는 미성년자 보호 요구가 바뀌는 경우, 새 source 형식·수집 경로·저장소·관찰 가능성 도구가 raw 또는 diagnostic을 보존할 수 있는 경우, sanitizer/탐지기의 false negative가 발견되는 경우, 공개 철회·GitHub Pages cache 무효화가 이 경계를 충족하지 못하는 경우 재검토한다.
