# ADR 0003: 권위 기반 identity와 claim lineage

- **상태:** Accepted
- **날짜:** 2026-07-11

## Decision

정규화 subject는 정확히 하나의 kind와 안정적인 opaque `subject_id`를 가진다. 허용 kind는 `school`, `region`, `organization`, `venue`, `program`, `university`의 여섯 가지다. `subject_id`는 kind와 권위 있는 공식 key를 canonical name으로 하는 UUIDv5로 생성한다. 공식 key가 없는 후보는 UUIDv5를 만들거나 기존 subject와 병합하지 않으며 `unknown`/review 상태로 fail-closed 처리한다. 표시명, 별칭, URL slug, 주소, 좌표 또는 이름 유사도는 공식 key의 대체·fallback·병합 근거가 될 수 없다.

권위 키는 kind별로 그 기관 또는 운영자가 발행·관리하고 출처 evidence가 확인한 식별자여야 한다. 어떤 key가 어느 authority namespace에 속하는지와 canonicalization 규칙은 정책 버전에 묶는다. kind와 namespace, canonical 공식 key가 모두 일치할 때만 같은 identity로 해석한다. 충돌·변경·폐기된 key, kind 불일치, authority 불명, 복수 후보는 자동 병합하지 않고 별도 후보와 검토 대상으로 남긴다.

source-to-subject 관계는 `primary`와 `related`를 구분한다. primary는 source가 직접 다루는 subject 또는 그 subject의 권위 있는 공식 발표이며, related는 맥락·공동 주최·참조 관계일 뿐 identity 또는 claim의 주 근거가 아니다. related proposal은 primary review를 대체하거나 status를 올릴 수 없다.

`venue`는 학교·교육청·팀·프로그램과 별개의 operator-managed 장소 subject다. venue identity는 venue operator의 공식 key로만 만들며, 행사 페이지에 보이는 장소명, 학교명 또는 주소로 venue를 추정하지 않는다. operator가 확인되지 않으면 venue는 unknown/review로 남긴다.

`event`는 subject kind가 아니라 namespaced event key로 식별되는 claim/resource이다. event key는 승인된 event authority namespace와 그 namespace 안의 공식 event key를 함께 사용한다. 같은 namespace/key라도 제목·날짜·주최·공식 URL 등 정책이 정한 canonical event fingerprint가 정확히 일치해야 동일 event로 연결한다. 제목 유사도, 지역, 날짜 근접성 또는 이름만으로 event를 연결하거나 deduplicate하지 않는다.

모든 publishable claim은 claim 단위로 evidence와 source를 가진다. evidence에는 public URL, observed time, checksum 및 source가 있고, claim은 자신의 `evidence_id`와 `source_id`를 참조한다. corroboration이 필요한 claim은 evidence별 publisher-control cluster와 reporting/original-information cluster를 기록하여 두 축 모두 독립임을 입증한다. URL·도메인·재게시·번역·wire copy가 다르더라도 한 축을 공유하면 독립 근거가 아니다.

identity, source relationship, evidence, lineage cluster 및 claim validity는 policy version/hash에 종속된다. authority registry, canonicalization, independence 또는 privacy/source 정책이 바뀌면 영향을 받은 claim을 policy invalidation으로 표시하고 재검토 전에는 verified/publication에 사용할 수 없다. 필수 authority key, 정확한 fingerprint, evidence, 두 축 lineage 또는 정책 유효성이 unknown이면 publication은 fail-closed다.

## Drivers

- 데이터 계약은 여섯 kind, 보수적 병합, primary/related 관계, claim별 evidence와 source를 요구한다.
- 학교·장소·행사 이름은 중복·변경·재사용되므로 이름 기반 identity는 오귀속을 만든다.
- 서로 다른 URL만으로는 독립 보도를 증명할 수 없고, 자동 mismerge 0이 publication gate다.
- 정책 변경 뒤 과거의 identity 및 evidence 결정을 묵시적으로 신뢰해서는 안 된다.

## Alternatives

1. **표시명 또는 fuzzy matching으로 UUIDv5 생성:** 공식 key가 없는 엔터티를 만들어 오귀속을 영구화하므로 거부한다.
2. **kind와 namespace를 무시한 전역 key:** 같은 문자열의 이종 기관을 합칠 수 있으므로 거부한다.
3. **event를 제목·일자·지역으로 deduplicate:** 공식 event key와 exact fingerprint 없이 서로 다른 행사를 합칠 수 있으므로 거부한다.
4. **related source로 primary review 충족:** 맥락 자료를 직접 권위 evidence로 오인하므로 거부한다.
5. **URL/domain 다양성만으로 corroboration 판정:** syndication과 공통 origin을 놓치므로 거부한다.
6. **정책 변경 후 기존 claim을 자동 유지:** 과거 결정의 유효성을 검증할 수 없으므로 거부한다.

## Consequences

- 공식 key가 없는 유용해 보이는 후보도 공개 identity가 아니라 unknown/review로 남는다.
- 각 identity·event·claim에는 namespace, canonical key/fingerprint, policy version, evidence 및 두 lineage cluster를 감사 가능하게 기록해야 한다.
- reviewer는 primary evidence와 관련 proposal을 분리해 판단하고, venue operator와 event authority를 확인해야 한다.
- 정책 hash 변경은 영향 분석과 재검토 비용을 만들지만, stale authority 결정을 공개하는 것을 막는다.

## Verification

- 여섯 kind 각각에 대해 동일 kind/namespace/canonical 공식 key는 같은 UUIDv5, 하나라도 다른 경우는 다른 identity인지 확인한다.
- 이름·별칭·URL slug·주소·좌표만 있는 후보와 unknown authority/key는 UUID 생성·병합·publication 모두 거부되는지 확인한다.
- primary와 related source fixture에서 related만으로 verified review 또는 claim 승격이 되지 않는지 확인한다.
- venue operator 부재와 event key 부재, event fingerprint의 한 필드 불일치, 제목만 같은 event를 각각 fail-closed하는지 확인한다.
- claim별 evidence/source 참조와 control/origin cluster를 검증하고, 한 축이라도 같은 재게시 자료가 corroboration으로 통과하지 않는지 확인한다.
- authority registry, canonicalization, lineage 또는 source/privacy policy hash 변경 fixture에서 영향 claim이 invalidated되어 재검토 전 publication gate가 실패하는지 확인한다.

## Revisit triggers

새 kind 또는 권위 registry가 승인되는 경우, 공식 key 형식·namespace ownership·event fingerprint 정책이 바뀌는 경우, UUIDv5 namespace 교체 또는 migration이 필요한 경우, lineage 독립성 모델의 오류가 발견되는 경우, policy invalidation의 영향 범위가 정확히 재현되지 않는 경우 재검토한다.
