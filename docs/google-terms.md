# Google Maps Platform 약관 요약 (dongseon용)

> **결정 (2026-11-04)**: 사용자가 아래 "dongseon 설계 결론 (제안)"의 보수적 방향을 채택했습니다. 반영 내용은 `docs/PLAN.md` 6절과 `.claude/rules/domain-rules.md`에 있습니다.

- 확인일: 2026-11-04 (모든 인용은 이 날짜에 원문 페이지에서 직접 받아 확인함)
- 대상: 비EEA 청구 주소 고객 기준 약관. 청구 주소가 EEA이면 별도 EEA 약관이 적용되므로 이 문서를 그대로 쓰면 안 됨.
- 이 문서는 법률 자문이 아니다. 원문이 애매한 부분은 애매하다고 적었고, 보수적으로 해석했다.

## 확인한 원문

| 문서 | URL | 원문에 표시된 버전 |
| --- | --- | --- |
| Google Maps Platform Terms of Service (ToS) | <https://cloud.google.com/maps-platform/terms> | Last modified August 26, 2026 |
| Google Maps Platform Service Specific Terms (SST) | <https://cloud.google.com/maps-platform/terms/maps-service-terms> | Last modified October 28, 2026 |
| Places API (New) Policies and attributions | <https://developers.google.com/maps/documentation/places/web-service/policies> | 날짜 표기 없음 |
| Routes API Policies | <https://developers.google.com/maps/documentation/routes/policies> | 날짜 표기 없음 |
| Place IDs 가이드 | <https://developers.google.com/maps/documentation/places/web-service/place-id> | 날짜 표기 없음 |
| Places API (New) Place 리소스 레퍼런스 | <https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places> | 날짜 표기 없음 |
| Place data fields (SKU별 필드) | <https://developers.google.com/maps/documentation/places/web-service/data-fields> | 날짜 표기 없음 |
| 가격표 (global) | <https://developers.google.com/maps/billing-and-pricing/pricing> | 날짜 표기 없음 |
| Maps Experience agent tools (구 Maps Grounding Lite) | <https://developers.google.com/maps/ai/grounding-lite> | 날짜 표기 없음 |
| Maps Experience agent tools 출처 표시 | <https://developers.google.com/maps/ai/maps-experience-agent-tools/attribution> | 날짜 표기 없음 |

## Q1. 무엇을, 얼마나 오래 저장할 수 있나

### 기본 원칙: 캐싱 금지, 예외는 SST에 명시된 것만

ToS 3.2.3(b):

> "Customer will not cache Google Maps Content except as expressly permitted under the Maps Service Specific Terms."

ToS 3.2.3(a) No Scraping 예시:

> "(i) pre-fetch, index, store, reshare, or rehost Google Maps Content outside the services; (ii) bulk download ... directions, distance matrix results, ... places information ...; (iii) copy and save business names, addresses, or user reviews"

"Google Maps Content" 정의(ToS 20):

> "any content provided through the Services ... including map and terrain data, imagery, traffic data, and places data (including business listings)."

결론적으로 SST에 허용 문구가 없는 콘텐츠는 저장하면 안 된다. 이름, 주소, 영업시간, 이동시간이 모두 여기에 해당한다.

### Place ID: 무기한 저장 가능

SST A.3 Google ID Caching:

> "Customer may cache the Google ID values from the Services that return such field and allow caching ... For example, Customer may cache (a) place_id from Places API, Directions API, Geolocation API and Routes API"

Places/Routes Policies (같은 문구):

> "the **place ID** ... is **exempt from** the caching restrictions ... You can therefore store place ID values indefinitely."

Place IDs 가이드:

> "Google recommends refreshing place IDs if they are more than 12 months old. You can refresh Place IDs **at no charge** by making a Place Details request ... specifying only the place ID field"

12개월 갱신은 의무가 아니라 권고다. `NOT_FOUND`가 오면 해당 ID는 폐기된 것이다.

### Places 콘텐츠 (Places API Legacy/New)

SST B.14.3:

> "Customer may temporarily cache latitude and longitude values from the Places API for up to 30 consecutive calendar days, after which Customer must delete the cached latitude and longitude values."

- 위도/경도: 최대 30일 연속 캐시 후 삭제.
- `displayName`, `formattedAddress`, `types`, `primaryType`, `regularOpeningHours`, `currentOpeningHours`, `googleMapsUri` 등: SST에 캐싱 허용 문구가 **없다**. 따라서 3.2.3(b)에 따라 캐싱이 금지된다고 읽는 것이 원문에 맞다. 특히 상호명과 주소는 3.2.3(a)(iii)에 예시로 명시되어 있다.
- 지오코딩 API(SST B.6.3.2)에는 주소·좌표를 "indefinitely" 캐시할 수 있는 예외가 있지만, 이 예외는 Geocoding API와 Android Geocoder SDK 응답에만 적용되고 Places API에는 적용되지 않는다.

### Routes 콘텐츠 (Routes API: computeRoutes / computeRouteMatrix)

SST B.19.3:

> "Customer may temporarily cache latitude (lat) and longitude (lng) values from the Routes API for up to 30 consecutive calendar days, after which Customer must delete the cached latitude and longitude values."

- 위도/경도(폴리라인 좌표 포함으로 해석): 최대 30일.
- 소요시간(duration), 거리, 경로 단계, 대중교통 상세: 허용 문구가 **없다**. 따라서 캐싱 금지다. ToS 3.2.3(a)(ii)가 "directions, distance matrix results"의 대량 다운로드를 예시로 금지한다.
- 참고: Navigation Connect API(SST B.11.8)에는 "distance, duration, time, and estimated time of arrival values for up to 30 consecutive calendar days"라는 허용 문구가 있다. 이 문구가 Routes API 조항에는 없으므로, Routes API의 소요시간에는 30일 캐시가 허용되지 않는다고 읽는 것이 보수적이다.

### 애매한 지점

- "cache"의 범위: 요청 처리 중 메모리에 잠깐 두는 것까지 금지하는 것은 아니라고 보는 것이 상식적이다. 하지만 원문에는 허용 시간 기준이 없다. 디스크/DB/IndexedDB에 남기는 것은 "store"에 해당하므로 금지로 보는 것이 안전하다.
- 사용자가 직접 입력한 값(예: 사용자가 붙인 장소 라벨, 사용자가 직접 적은 영업시간)은 Google Maps Content가 아니다. 다만 Google 응답값을 UI에서 자동으로 채워 넣은 경우는 사실상 "copy and save business names"에 가까워 애매하다.

## Q2. 비Google LLM/AI 모델에 입력으로 보내도 되나 (학습 아님)

### ToS의 관련 조항

ToS 3.2.3(c) No Creating Content From Google Maps Content:

> "Customer will not create content based on Google Maps Content. For example, ... (vi) convert text-based driving times into synthesized speech results; or (vii) use Google Maps Content to improve machine learning and artificial intelligence models, including to train, test, validate or fine-tune the models."

ToS 3.2.3(a) No Scraping:

> "Customer will not export, extract, or otherwise scrape Google Maps Content for use outside the Services."

ToS에서 "LLM", "Gemini", "generative"를 검색했지만 해당 조항은 없었다. 명시적으로 금지된 것은 (vii)의 학습·테스트·검증·파인튜닝뿐이다.

### SST가 보여 주는 Google의 해석 (중요)

SST B.10 Maps Experience Agent Tools:

> "'Grounded Output' means output created when Google Maps Content is combined with the output of any LLM."
>
> "As a limited exception: 10.2.1 to the prohibition on using Google Maps Content to create content, Customer may use Maps Experience Agent Tools to ground a LLM to generate and display Grounded Output to End Users if (i) Customer complies with the Generative AI Prohibited Use Policy ... and (ii) Customer includes associated Google Maps source links with the Grounded Output"

Google은 Google Maps Content를 LLM 출력과 결합하는 것을 "create content" 금지 조항(3.2.3(c))의 대상으로 본다. 그리고 그 예외를 **Maps Experience Agent Tools를 통한 경우에만** 명시적으로 준다. 이 예외는 Places API나 Routes API 응답을 직접 LLM에 넣는 경우에는 적용되지 않는다.

Maps Experience agent tools 문서의 "Requirements for Compatible LLMs":

> "You may only use Maps Experience agent tools with an LLM that is compliant with the Google Maps Platform Terms of Service. ... you are responsible for ensuring that Google Maps Content is not cached by, stored by, or used to improve the LLM that you choose to use. ... You must not use Maps Experience agent tools with any models that use the data input into the model for any model training or improvement."

같은 문서는 비Gemini 모델을 위한 경로도 명시한다. "Choose Maps Experience agent tools for other models or agent frameworks"

### 보수적 해석

- Places API/Routes API로 받은 영업시간, 소요시간을 비Google LLM(Claude) 프롬프트에 넣어 일정 검토문을 생성하는 것은 **3.2.3(c)의 "create content based on Google Maps Content"에 해당할 수 있다.** SST B.10이 바로 이 행위를 예외 대상으로 다루고 있기 때문이다. "학습이 아니니 괜찮다"는 계획의 가정은 원문만으로는 뒷받침되지 않는다.
- 3.2.3(a)의 "for use outside the Services"(제3자 시스템으로 내보내기)에도 걸릴 수 있다.
- 원문이 직접 금지하는 것은 아니므로 회색지대다. 다만 Google이 별도 예외 조항을 만들어 둔 것은 "기본은 금지"라는 해석을 강하게 시사한다.
- 비교적 안전한 경로는 세 가지다. (1) LLM에는 사용자 자신의 데이터만 보낸다. (2) Claude를 Maps Experience agent tools MCP에 연결해 Grounded Output으로 처리하고, 출처 링크를 표시하고, 학습에 쓰이지 않는 모델 설정을 확인한다. (3) Gemini의 Grounding with Google Maps를 쓴다.
- 경로 (2)를 쓰면 Grounded Output 캐시가 SST 10.2.2에 따라 "up to thirty (30) consecutive days"(평가·최적화 목적) 또는 사용자 채팅 기록으로 최대 2년까지 허용된다. 반면 "attempt to extract or otherwise separate Google Maps Content from the Grounded Output"(10.3.1)은 금지된다.

## Q3. 비Google 지도와 함께 쓰는 것에 대한 제한

ToS 3.2.3(e):

> "Customer will not use the Google Maps Core Services with or near a non-Google Map in a Customer Application. For example, Customer will not (i) display or use Places content on a non-Google Map, ... or (iii) link a Google Map to non-Google Maps Content or a non-Google Map."

SST B.14.1–14.2 (Places), B.19.1–19.2 (Routes):

> "Customer may use Google Maps Content from the Places API in Customer Applications without a corresponding Google Map."
>
> "Customer must not use Google Maps Content from the Places API in conjunction with a non-Google map."

Routes API도 같은 문구를 쓴다.

정리하면:

- 지도 없이 목록·표·텍스트로 보여 주는 것은 허용된다.
- 지도를 띄울 때는 Google Maps JavaScript API만 쓴다. Leaflet/OSM/Mapbox 등은 같은 화면은 물론 "near"(근처)에도 두지 않는다.
- Places UI Kit은 예외적으로 비Google 지도와 함께 쓸 수 있다(SST B.15.1). dongseon은 이 예외에 해당하지 않는다.
- Google Maps URLs 딥링크로 Google Maps 앱을 여는 것은 비Google 지도와 연결하는 것이 아니므로 이 제한과 충돌하지 않는다(해석).

## Q4. Google 지도 없이 Places 데이터를 보여 줄 때 출처 표시 의무

### 일반 의무

ToS 3.2.2(b):

> "Customer will display all attribution that (i) Google provides through the Services (including branding, logos, and copyright and trademark notices); or (ii) is specified in the Maps Service Specific Terms. Customer will not modify, obscure, or delete such attribution."

Places/Routes Policies:

> "You must follow Google Maps attribution requirements when displaying Content from Google Maps Platform APIs in your app or website. You don't need to add extra attribution if the Content is shown on a Google Map where the attribution is already visible."
>
> "Attribution should take the form of the Google Maps logo whenever possible. In cases where space is limited, the text **Google Maps** is acceptable."

### 로고/텍스트 규격 (Places/Routes Policies)

- 로고: 공식 파일 사용, 변형 금지, 높이 16–19dp, 여백 좌·우·상 10dp, 하 5dp. 접근성 라벨은 "Google Maps".
- 텍스트: "Google Maps"를 대소문자 변경, 줄바꿈, 현지화 없이 그대로 쓴다. 원문은 "Prevent browsers from translating **Google Maps** by using the HTML attribute `translate="no"`"라고 요구한다. 서체는 Roboto(로딩은 선택) 또는 sans-serif, weight 400, 12–16sp. 색은 흰색, #1F1F1F, #5E5E5E 중 하나이고 대비 4.5:1 이상이어야 한다.
- 배치: "Position attribution near the top or bottom of the content, and within the same visual container." Google 콘텐츠를 테두리·배경색·여백으로 다른 콘텐츠와 구분해야 한다. 원문은 또 "Don't misrepresent Google Maps by attributing it with non-Google Maps Platform content."라고 적고 있다.
- 기존 구현은 "Google"만 표기해도 당분간 허용되지만, 신규 구현은 "Google Maps"를 쓴다.

### 데이터 제공자 표시

Place 레퍼런스 `attributions[]`:

> "A set of data provider that must be shown with this result."

응답에 `attributions`가 있으면 함께 표시해야 한다. 이 필드는 Place Details Essentials (IDs Only) 등급이다.

### 작성자 표시와 googleMapsUri

Places Policies "Photos and reviews":

> "You must always credit the author when displaying photos or reviews."
>
> "For each photo and review, end-users must always have access to view the individual source photo or review on Google Maps using the provided `googleMapsUri`."

- 작성자 표시와 `googleMapsUri` 링크 의무는 **사진·리뷰를 보여 줄 때** 적용된다. dongseon은 사진·리뷰를 쓰지 않으므로 직접 의무는 없다.
- 일반 장소 정보(이름, 영업시간)에 `googleMapsUri` 링크를 다는 것은 의무가 아니다. 다만 Maps Experience agent tools 결과를 보여 줄 때는 `googleMapsLinks.placeUrl` 링크가 의무다.
- AI 요약(`generativeSummary`, `reviewSummary` 등)을 쓰면 `disclosureText` 등을 표시할 의무가 추가된다. dongseon은 쓰지 않는다.

### 앱 이용약관 고지

ToS 3.2.2(a)(i): 앱의 이용약관에 Google Maps 기능 사용 사실을 알리고, Google Maps End User Additional Terms(<https://maps.google.com/help/terms_maps/>)와 Google Privacy Policy를 링크해야 한다. 개인용 앱이라도 문구상 면제는 없다.

## SKU 표 (Places API New 필드 → 등급)

출처: <https://developers.google.com/maps/documentation/places/web-service/data-fields> (2026-11-04 확인). 요청 하나의 요금은 필드 마스크에 포함된 필드 중 가장 높은 등급으로 매겨진다.

| 필드 | Place Details | Text Search |
| --- | --- | --- |
| `id` | Essentials (IDs Only) | Essentials (IDs Only) |
| `attributions` | Essentials (IDs Only) | (확인 안 함) |
| `location` | Essentials | Pro |
| `types` | Essentials | Pro |
| `formattedAddress` | Essentials | Pro |
| `displayName` | **Pro** | Pro |
| `primaryType` | **Pro** | Pro |
| `googleMapsUri` | Pro | Pro |
| `utcOffsetMinutes`, `timeZone`, `businessStatus` | Pro | Pro |
| `regularOpeningHours` | Enterprise | Enterprise |
| `currentOpeningHours` | Enterprise | Enterprise |

- `displayName`과 `primaryType`은 Place Details에서도 Essentials가 아니라 **Pro**다. `types`만 Essentials다.
- "Text Search Essentials (IDs Only)"는 존재하며 무료 한도가 "Unlimited"다. Text Search에는 그 밖의 Essentials 등급이 없고, `id` 외 필드를 하나라도 요청하면 Pro 이상이 된다.
- `currentOpeningHours`: 레퍼런스 원문은 "The hours of operation for the next seven days (including today) incorporating any special opening hours. The time period starts at midnight on the date of the request and ends at 11:59 pm six days later."이다. 오늘부터 7일만 다루므로 여행일이 7일 이후면 특별 휴무가 반영되지 않는다. 이때는 `regularOpeningHours`로 판단해야 한다.

### 월 무료 한도 (가격표, 2026-11-04 확인)

출처: <https://developers.google.com/maps/billing-and-pricing/pricing>

| SKU | 무료 한도/월 | 이후 1,000건당 (첫 구간) |
| --- | --- | --- |
| Places API Place Details Essentials (IDs Only) | Unlimited | - |
| Places API Text Search Essentials (IDs Only) | Unlimited | - |
| Places API Place Details Essentials | 10,000 | $5.00 |
| Places API Place Details Pro | 5,000 | $17.00 |
| Places API Text Search Pro | 5,000 | $32.00 |
| Places API Place Details Enterprise | 1,000 | $20.00 |
| Places API Text Search Enterprise | 1,000 | $35.00 |
| Routes: Compute Routes Essentials | 10,000 | $5.00 |
| Routes: Compute Route Matrix Essentials | 10,000 | $5.00 |
| Routes: Compute Routes / Route Matrix Pro | 5,000 | $10.00 |
| Dynamic Maps (Maps JavaScript API) | 10,000 | $7.00 |
| Maps Grounding Essentials (agent tools) | 10,000 | $7.00 |

Route Matrix의 과금 단위(요소 수)와 transit 요청의 등급은 SKU 상세 페이지(<https://developers.google.com/maps/billing-and-pricing/sku-details/routes>)에서 따로 확인해야 한다. 이번에는 정밀 확인하지 않았다.

## dongseon 설계 결론 (제안)

표기: [원문 근거 있음] / [해석(사용자 확인 필요)]

### 영구 DB

1. Google 응답에서 영구 저장하는 값은 `place_id`(Places `id`)만 둔다. [원문 근거 있음: SST A.3, Places/Routes Policies]
2. `place_id`는 12개월마다 IDs Only 요청(무료)으로 갱신하고, `NOT_FOUND`이면 사용자에게 재선택을 요청한다. [원문 근거 있음: Place IDs 가이드 (권고)]
3. 장소 라벨은 사용자가 직접 입력한 문자열로 저장한다. Google `displayName`을 자동 복사해 영구 저장하지 않는다. 자동 채움 후 사용자가 편집하는 UX라면 Google 값 원문을 그대로 저장하는 것과 구분이 애매하다. [해석(사용자 확인 필요)]
4. 사용자 지정 카테고리(앱 카테고리)는 사용자 데이터로 저장해도 된다. 단, Google `types`/`primaryType`에서 자동 매핑한 값을 저장하는 것은 3번과 같은 회색지대다. [해석(사용자 확인 필요)]

### TTL 캐시

1. 좌표(Places `location`, Routes 좌표/폴리라인): 최대 30일 후 삭제한다. [원문 근거 있음: SST B.14.3, B.19.3]
2. 장소 상세(이름, 주소, 유형, `googleMapsUri`), 영업시간(`regularOpeningHours`, `currentOpeningHours`): SST에 허용 문구가 없으므로 **영속 캐시를 두지 않는다.** 화면을 렌더링할 때 조회하고, 서버 메모리의 요청 범위(또는 수 분 이하의 프로세스 메모리)에서만 쓴다. "TTL 캐시라면 괜찮다"는 계획의 가정과 충돌한다. [원문 근거 있음: ToS 3.2.3(a)(b) / 허용 시간 기준은 해석(사용자 확인 필요)]
3. 경로 행렬(소요시간·거리): 2번과 같다. 영속 캐시를 두지 않는다. [원문 근거 있음: ToS 3.2.3(a)(ii), SST B.19.3에 duration 허용 문구 없음]
4. 비용 대책: 캐시 대신 필드 마스크를 최소화한다(IDs Only, Essentials 우선). 영업시간이 필요할 때만 Enterprise를 호출한다. [해석]

### LLM 페이로드

1. 보내도 되는 것(보수적): 사용자가 입력한 라벨, 사용자 정의 카테고리, 사용자가 정한 일정 순서와 체류 시간, 사용자가 직접 입력한 메모나 영업시간. [해석(사용자 확인 필요)]
2. 보내지 않는 것: Places/Routes API로 받은 영업시간, 개폐 여부, 분 단위 이동시간, 상호명, 주소, 좌표. 이 데이터를 LLM에 넣어 검토문을 생성하는 것은 ToS 3.2.3(c) "create content"에 해당할 수 있고, Google은 그 예외를 Maps Experience Agent Tools에만 명시했다. 계획의 "LLM에는 hours/minutes만" 가정은 **보수적 해석과 충돌한다.** [원문 근거 있음: ToS 3.2.3(c), SST B.10.2.1 / 적용 범위는 해석(사용자 확인 필요)]
3. 대안 A: 영업시간 충돌, 이동시간 초과 같은 판정은 앱 코드에서 결정적으로 계산해 화면에만 표시한다. LLM에는 Google 값을 빼고 "3번째 일정이 영업시간 밖" 같은 추상 플래그만 보낸다. 다만 파생값도 "based on Google Maps Content"로 볼 여지가 있어 완전히 안전하지는 않다. [해석(사용자 확인 필요)]
4. 대안 B: Claude에 Maps Experience agent tools MCP를 연결해 LLM이 직접 조회하게 한다. 이 경우 출처 링크(`placeUrl`)를 결과 바로 아래에 표시하고, Generative AI Prohibited Use Policy를 준수하고, 사용하는 Claude 플랜이 입력 데이터를 학습에 쓰지 않는지 확인해야 한다. transit 경로 조회는 지원되지만 중간 경유지는 지원되지 않는다. [원문 근거 있음: SST B.10, agent tools 문서 / Claude 측 데이터 정책은 사용자 확인 필요]
5. 어떤 경우든 Google 데이터를 학습·평가·파인튜닝에 쓰는 설정(예: 학습 동의 옵션)은 꺼 둔다. [원문 근거 있음: ToS 3.2.3(c)(vii)]

### 오프라인 PWA 캐시

1. IndexedDB/Cache Storage에 넣어도 되는 것: 사용자 데이터(라벨, 일정, 메모), `place_id`, Google Maps URLs 딥링크(사용자 데이터와 `place_id`로 조립한 것), 그리고 좌표(30일 이내, 만료 시 삭제 로직 포함). [원문 근거 있음 (좌표·ID) / 딥링크는 해석]
2. 넣으면 안 되는 것: Places 이름·주소·영업시간, Routes 소요시간·경로. 여행 중 오프라인으로 영업시간과 이동시간을 보여 주려는 계획은 원문 기준으로 허용되지 않는다. 필요하면 사용자가 직접 확인해 입력한 값(사용자 데이터)으로 대체한다. [원문 근거 있음: ToS 3.2.3(a)(b)]
3. Maps JavaScript API 타일을 서비스워커로 캐시하지 않는다. [원문 근거 있음: ToS 3.2.3(a)(i) "pre-fetch ... store"]
4. 이용자가 단일 가구라 Google이 실제로 문제 삼을 가능성은 낮다. 하지만 약관에는 개인용 예외가 없다. [해석]

### 출처 표시 UI

1. Google 지도가 없는 화면(목록, 일정표, 장소 카드)에서 Places/Routes 콘텐츠를 보여 줄 때는 같은 컨테이너의 상단 또는 하단에 Google Maps 로고(16–19dp)를 둔다. 공간이 부족하면 `<span translate="no">Google Maps</span>` 텍스트로 대체한다(Roboto/sans-serif, 400, 12–16px, #5E5E5E). [원문 근거 있음: Places/Routes Policies]
2. Google 콘텐츠와 사용자 콘텐츠(라벨, 메모)를 테두리나 배경으로 시각적으로 구분하고, 사용자 콘텐츠에 Google Maps 표시가 붙지 않게 한다. [원문 근거 있음]
3. Place 응답에 `attributions[]`가 있으면 해당 데이터 제공자를 표시한다. [원문 근거 있음: Place 레퍼런스]
4. 사진·리뷰는 쓰지 않으므로 작성자 표시와 `googleMapsUri` 의무는 해당하지 않는다. 그래도 장소 카드에 Google Maps로 여는 링크를 두는 것을 권장한다. [원문 근거 있음 (적용 범위) / 권장은 해석]
5. Google 지도 위에 표시할 때는 지도 자체의 표시로 충분하다. 비Google 지도는 쓰지 않는다. [원문 근거 있음]
6. 앱 내 "정보/약관" 화면에 Google Maps 기능 사용 고지와 Google Maps End User Additional Terms, Google Privacy Policy 링크를 둔다. [원문 근거 있음: ToS 3.2.2(a)]
7. 도보 경로를 표시하는 경우 Routes API 응답의 경고(warnings)를 함께 보여 주는 것을 권장한다. agent tools 문서는 WALK 경로가 beta이므로 경고 표시가 의무라고 적고 있다. Routes API에 대해서는 이번에 확인하지 않았다. [해석(사용자 확인 필요)]
