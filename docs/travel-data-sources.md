# 항공권·숙소 데이터 소스 조사 (dongseon용)

- 조사일: 2026-11-05
- 목적: 서울(ICN/GMP) → 도쿄(HND/NRT), 2026년 12월 말~2027년 1월 초, 5일, 2인 여행의 항공권과 숙소 후보를 매일 자동으로 뽑는 기능에 쓸 데이터 소스를 고른다.
- 전제(앱 규칙): 예약 사이트와 Google 페이지 스크래핑 금지, 연동 전 약관 확인, 무료 우선, 유료는 사용자 명시 승인 시에만.
- 이 문서는 법률 자문이 아니다. 공식 페이지를 직접 받아 본 내용과 검색 결과 요약(2차 출처)을 구분해 적었다. "미확인"이라고 적은 항목은 원문을 직접 확인하지 못한 것이다.

## 한눈에 보기

### 항공권

| 서비스 | 데이터 | 개인 개발자 가입 | 비용 | 판정 |
| --- | --- | --- | --- | --- |
| Ignav | 실시간에 가까운 운임 검색 + 예약 링크 (결과 재사용 30분) | 가능 (셀프 가입, 카드 없이 시작) | 1,000회 무료(1회성), 이후 $2/1,000회 | 1순위 |
| Travelpayouts Aviasales Data API | 캐시 가격 (사용자 검색 이력 기반, 2~7일) | 가능 (제휴 계정 토큰) | 무료 | 보조 (가격 추세용) |
| Duffel | 항공사 실시간 오퍼 (NDC/GDS) | 사실상 사업자 (KYC, 사업 정보 요구) | 주문당 $3, 검색 1,500:1 초과분 $0.005 | 약관상 위험 |
| SerpApi Google Flights | Google Flights 결과 스크래핑 | 가능 | 무료 250회/월, $25/월 1,000회 | 규칙 위반 (Google 스크래핑) |
| FlightAPI.io | 가격 추적용 운임 | 가능 | 무료 20회, $49/월~ | 출처 불명, 비쌈 |
| Kiwi.com Tequila | 운임 검색 | 불가 (2024-05부터 초대제) | - | 사용 불가 |
| Skyscanner Travel API | 실시간 가격 | 불가 (월 10만 트래픽 이상 기업만) | - | 사용 불가 |
| Travelpayouts Search API (실시간) | 실시간 | 불가 (MAU 5만 이상) | - | 사용 불가 |
| KAYAK Flights Price Insights | 캐시/예측 최저가 | 제휴사 전용으로 보임 | 미기재 | 사용 불가에 가까움 |
| LiteAPI Flights | 운임 검색 (matrix는 별도 활성화) | 가능 | 항공은 발권 수수료 등 | 참고 (항공 커버리지 미확인) |
| Google 공식 Flights API | 없음 (QPX Express 2018 종료) | - | - | 없음 |
| Amadeus Self-Service | 2026-07-17 종료 | - | - | 없음 |
| 네이버 항공권 | 공식 오픈 API 없음 | - | - | 없음 |
| 항공사 NDC 직접 | 항공사별 계약/IATA 인증 필요 | 불가 | - | 개인용 비현실적 |
| AeroDataBox | 스케줄·운항 정보만 (운임 없음) | 가능 (RapidAPI) | 유·무료 티어 | 운임 용도 아님 |

### 숙소

| 서비스 | 데이터 | 개인 개발자 가입 | 비용 | 판정 |
| --- | --- | --- | --- | --- |
| 楽天トラベル API (VacantHotelSearch) | 일본 숙소 실시간 공실·요금, 예약 URL | 가능 (楽天会員 + 앱 등록) | 무료 | 1순위 (도쿄) |
| LiteAPI (Nuitée) | 전 세계 호텔 요금·예약 | 가능 (셀프 가입, 프로덕션은 카드 등록) | Rates/Book 무료, 일부 엔드포인트 유료 | 2순위 (약관 제약 있음) |
| Hotelbeds APItude | 호텔 요금 (평가 환경) | 평가 키는 셀프 가입 | 평가 키 무료 (하루 50회), 운영은 상업 계약 | 평가 키는 실사용 부적합 |
| SerpApi Google Hotels | Google Hotels 스크래핑 (OTA별 가격, 민박 포함) | 가능 | 무료 250회/월 | 규칙 위반 (Google 스크래핑) |
| Booking.com Demand API | 실시간 요금 | 불가 (Managed Affiliate Partner 계약) | - | 사용 불가 |
| Expedia Rapid | 실시간 요금, Vrbo 포함 | 불가 (파트너 신청 + 사이트 리뷰) | - | 사용 불가 |
| Agoda API | 실시간 요금 | 제휴/계약 필요로 보임 | - | 미확인, 현실성 낮음 |
| Travelpayouts Hotellook | 2025-10-20 종료 | - | - | 없음 |
| Google Hotels 공식 API | 소비자용 없음 | - | - | 없음 |
| Amadeus Hotel (Self-Service) | 2026-07-17 종료, Enterprise만 | 불가 | - | 없음 |
| Airbnb | 신규 API 접근 받지 않음 | 불가 | - | 없음 |
| じゃらん Webサービス | 현재 상태 미확인 | 미확인 | - | 미확인 |

## 항공권 상세

### Ignav

- 데이터: 편도/왕복/다구간 운임 검색, 최저가 날짜 검색(출발일 최대 31일), 예약 링크(항공사·OTA URL), 공항 검색. 87개 마켓 지원, 한국(KR, KRW)과 일본(JP, JPY) 포함.
- 신선도: FAQ에 "fare-search와 cheapest-dates 결과는 최대 30분 재사용될 수 있다"고 적혀 있고 `observed_at`으로 조회 시각을 준다. 표시는 "from $299"처럼 대략적인 가격으로 하고 최종 가격은 예약 링크에서 확인하라고 권한다.
- 접근: 무료 계정으로 API 키 발급. 가입 자격 제한 문구 없음. 카드 없이 시작.
- 가격: 1,000회 무료(1회성), 이후 성공 요청(HTTP 200) 1,000회당 $2, 월 청구, 최소 금액 없음.
- 데이터 출처: 공식 문서에 상류 출처(항공사 직접, OTA, 메타서치 등)를 밝히지 않는다. Google 스크래핑 레이어가 아니라고 스스로 설명하지만 독립 확인은 못 했다.
- 약관: 이용약관 페이지(<https://ignav.com/terms>)가 자바스크립트로 렌더링돼 본문을 받지 못했다. 저장·재배포·AI 사용 조항은 미확인.
- 위험: 신생 서비스(1인 운영으로 보이는 문의 메일)라 지속성 위험. 데이터 출처가 불투명. 연동 전 약관 원문을 브라우저로 직접 읽어야 한다.
- 출처: <https://ignav.com/pricing>, <https://ignav.com/docs/faq>, <https://ignav.com/docs/markets>, <https://ignav.com/docs/booking-com-flights-api>, <https://ignav.com/docs/kiwi-tequila-alternative>

### Travelpayouts Aviasales Data API

- 데이터: Aviasales 사용자의 검색 이력에서 만든 캐시 가격. v3 `prices_for_dates`는 "지난 48시간 동안 사용자들이 찾은 특정 날짜 최저가"를 준다. 저장 기간은 쿼리 종류에 따라 2~7일. 실시간이 아니고, 아무도 검색하지 않은 노선·날짜는 비어 있을 수 있다. 마켓별 캐시라 KR 마켓 데이터가 있는지 실제 호출로 확인해야 한다.
- 접근: Travelpayouts 가입 후 토큰만 있으면 제한 없이 사용 가능(지원 문서 요약). 실시간 Search API는 MAU 5만 이상만 신청 가능.
- 가격: 무료.
- 약관: 공식 지원 문서는 "사이트에서 사용자에게 정보를 주고 콘텐츠 페이지를 만드는 용도"를 권장. 개인용 금지 조항은 찾지 못했다. 제휴 약관상 예약 링크는 제휴 마커가 붙은 링크를 쓰는 것이 원칙으로 보인다(미확인). 가입 시 웹사이트/프로젝트 등록이 필요한지 미확인.
- 확인 한계: support.travelpayouts.com 페이지가 403을 반환해 원문을 직접 받지 못했다. 위 내용은 검색 결과에 노출된 공식 지원 문서 문구 기준.
- 위험: 캐시라 "오늘 실제로 살 수 있는 가격"이 아니다. 가격 추세나 날짜 비교 보조용으로만 적합.
- 출처: <https://support.travelpayouts.com/hc/en-us/articles/203956163>, <https://support.travelpayouts.com/hc/en-us/articles/203956083-Requirements-for-Aviasales-data-API-access>, <https://support.travelpayouts.com/hc/en-us/articles/210995808-How-to-get-access-to-the-Aviasales-Search-API>

### Duffel

- 데이터: 항공사 실시간 오퍼(300개 이상 항공사, NDC와 GDS). 대한항공은 Travelport(GDS) 경유로 제공. 아시아나 페이지도 있음. 오퍼는 빨리 만료된다.
- 접근: 셀프 가입 + 테스트 토큰. 라이브 전환에는 KYC 검증과 사업 정보 제출이 필요. 서비스 약관 1.1은 "solely for your business operations"로 접근을 허용한다. 개인(비사업자) 가능 여부는 명시 없음.
- 가격: 주문당 $3, Managed Content 주문가의 1%, 유료 부가서비스 $2, 환전 2%. 검색:주문 비율 1,500:1 초과분 검색당 $0.005. 약관 2.3상 주문 0건은 1건으로 계산하므로 월 1,500회까지는 무료.
- 약관 핵심: 2.5(d) 메타서치 용도 금지, 2.5(k) 공급사 데이터로 마케팅 금지, 10.1 운임을 기밀정보로 취급, 2.3/9.2 검색 과다 시 상한·정지 가능.
- 위험: 예약 없이 가격만 매일 조회하는 용도는 "여행 상품 판매" 목적과 맞지 않고, 메타서치 금지 조항에 걸릴 소지가 있다. 개인이 KYC를 통과할 수 있는지도 미확인. 비용은 거의 0이지만 약관 위험 때문에 추천하지 않는다.
- 출처: <https://duffel.com/pricing>, <https://duffel.com/services-agreement>, <https://duffel.com/flights/airlines/korean-air>, <https://duffel.com/docs/guides/getting-started-with-flights>, <https://help.duffel.com/hc/en-gb/articles/360019685959-Why-do-I-have-to-provide-business-information-when-activating-my-account>

### SerpApi Google Flights

- 데이터: Google Flights 결과(최적/기타 항공편, 구간 정보, 가격, `price_insights` 가격 수준·가격 이력). 왕복은 첫 응답에 가는 편만 오고, `departure_token`으로 두 번째 요청을 해야 오는 편을 받는다(왕복 1건 = 검색 2회).
- 가격: Free $0/250회/월(시간당 50회), Starter $25/1,000회, Developer $75/5,000회. 캐시된 검색(1시간 이내 동일 쿼리)은 차감 안 됨. Legal Shield는 Production($150) 이상만.
- 약관: SerpApi는 검색 결과를 31일 보관 후 삭제. Google 약관에 대한 언급은 없음. 사용자의 불법 사용은 사용자 책임(면책 조항).
- 법적 상황: Google이 2025-12 SerpApi를 DMCA 우회 혐의로 제소, 2026-07 주요 DMCA 청구가 기각됐으나 Google이 소장을 수정해 계속 진행 중(2차 보도 기준, 법원 기록 미확인).
- 위험: 본질이 Google 페이지 스크래핑이다. dongseon의 "Google 페이지 스크래핑 금지" 규칙을 대행사를 통해 우회하는 셈이라 채택하지 않는 것이 맞다.
- 출처: <https://serpapi.com/pricing>, <https://serpapi.com/google-flights-api>, <https://serpapi.com/legal>, <https://seroundtable.com/google-lawsuit-serpapi-dismissed-41731.html>, <https://www.theregister.com/2026/02/21/serpapi_google_scraping_lawsuit/>

### FlightAPI.io

- 데이터: 700개 이상 항공사·판매처 가격(가격 추적 전용, 예약 불가). 데이터 수집 방식은 공개하지 않음.
- 가격: 무료 20회, Lite $49/월(30,000 크레딧), Standard $99/월, Plus $199/월. 왕복 1회당 크레딧 소모량은 페이지에 없음(미확인).
- 위험: 출처 불명(OTA 스크래핑 가능성 배제 못 함), 월 $49부터라 1일 1회 용도로는 과하다. 약관 원문 미확인.
- 출처: <https://www.flightapi.io/>

### Kiwi.com Tequila

- 2024-05-30 파트너십 공지 이후 B2B API 공개 접근 중단, 신규는 초대제. 2025~2026 재개 소식은 찾지 못했다.
- 출처: <https://ignav.com/docs/kiwi-tequila-alternative> (Kiwi 공지 인용), Kiwi 원문 공지는 직접 확인 못 함

### Skyscanner Travel API

- 공식 수락 기준: 월 10만 이상 트래픽의 기성 기업, 브랜드 적합성. "학생과 비상업 개인", 저트래픽 사이트, 웹 에이전시는 명시적으로 제외. 상업 계약 필요.
- 출처: <https://skyscannerpartnersupport.zendesk.com/hc/en-us/articles/10881149122717-What-is-the-acceptance-criteria-for-the-Travel-API>

### Google 공식 옵션

- QPX Express는 2018-04 종료됐고 후속 공개 API는 없다. Google 개발자 제품 목록에 항공 검색 API가 없다(2차 출처). Google Flights 데이터를 얻는 방법은 스크래핑뿐이라 규칙상 제외.
- 출처: <https://airlabs.co/google-flights-api-alternatives>, <https://ignav.com/docs/qpx-express-alternative>

### Amadeus Self-Service

- 2026-07-17 키 비활성화로 종료. 대체 경로는 영업 계약이 필요한 Enterprise뿐.
- 출처: <https://www.phocuswire.com/amadeus-shut-down-self-service-apis-portal-developers>, <https://ignav.com/docs/amadeus-self-service-shutdown>

### 네이버 항공권

- 네이버 개발자센터 오픈 API 목록에 항공권 항목이 없다. 커뮤니티 MCP 서버가 `flight-api.naver.com` 비공개 엔드포인트를 호출하지만, 이는 비공식 사용이라 스크래핑 금지 규칙에 걸린다.
- 출처: <https://naver.github.io/naver-openapi-guide/apilist.html>, <https://glama.ai/mcp/servers/InSIkHwang/Naver-Flight-MCP>

### 항공사 NDC 직접 연동

- 대한항공·아시아나·ANA·JAL 등의 NDC는 여행사(IATA 인증 또는 애그리게이터 계약) 대상이다. Duffel의 NDC 인증 목록에 ANA, JAL이 있으나 이는 애그리게이터 경유다. 개인이 항공사와 직접 계약하는 경로는 확인되지 않았다(개별 항공사 개발자 포털은 직접 확인 못 함).
- 출처: <https://duffel.com/ndc/airlines-and-ndc>

### KAYAK Flights Price Insights API

- 여행자 검색 캐시 기반 노선별·날짜별 최저가와 예측 가격. 요청마다 `apiKey`, `userTrackId`, 클라이언트 IP 헤더가 필요하고 제휴 네트워크 문의로 연결돼 제휴사 전용으로 보인다. 가격·자격 미기재.
- 출처: <https://developers.kayak.com/flights-price-insights-api>

### LiteAPI Flights

- 같은 LiteAPI 계정으로 항공 운임 API가 있다. 날짜 매트릭스(`/flights/rates/matrix`)는 기본 비활성이라 지원팀 요청 필요. 항공 수수료는 발권 1%(최소 2유로), 검색:예약 1,500:1 초과 시 검색당 0.005유로. 한국·일본 노선 커버리지는 미확인.
- 출처: <https://docs.liteapi.travel/reference/searchflightsmatrix>, <https://docs.liteapi.travel/reference/api-pricing-usage-costs>

### AeroDataBox

- 항공편 스케줄, 운항 상태, 공항 정보만 제공하고 운임은 없다. RapidAPI 등 마켓플레이스에서만 판매. 가격을 직접 확인하지 못했다. 이미 쓰는 비행편 비교 기능의 시간표 보강용으로는 의미가 있을 수 있다.
- 출처: <https://rapidapi.com/aedbx-aedbx/api/aerodatabox/pricing>

## 숙소 상세

### 楽天トラベル 空室検索 API (Rakuten Travel VacantHotelSearch)

- 데이터: 지정 체크인·체크아웃 날짜에 빈 방이 있는 일본 숙소, 숙소 기본 정보(이름, 주소, 교통, 이미지, 리뷰 수·평균), 최저 요금(세금·서비스료 포함 1박 1실 기준), 플랜별 요금(`dailyCharge`, `total`), 예약 URL(`reserveUrl`). 위경도+반경(0.1~3km) 또는 지역 코드로 검색, 요금순 정렬, 인원·객실 수 지정 가능. 실시간 공실 기준. 엔화.
- 엔드포인트(2026년 이전 후): `https://openapi.rakuten.co.jp/engine/api/Travel/VacantHotelSearch/20170426`. `applicationId`와 `accessKey` 필수. `affiliateId`는 선택.
- 2026 변경: 2026-02 플랫폼 개편, 구 숫자형 앱 ID 폐지, 신규 앱 등록(UUID + Access Key) 필요, 기존 앱 이행 기한 2026-05-13(2차 출처). 앱 설정의 웹사이트 URL 등록과 Referer 헤더 확인이 필수가 됐다는 블로그 보고가 있다(공식 문서로는 미확인).
- 접근: 楽天会員이면 앱 등록으로 무료 발급. 약관상 국가·개인/사업자 제한 없음. 한국 거주자의 楽天会員 가입 가능 여부는 직접 확인 못 함.
- 약관 핵심: 13조 출처(크레딧) 표시 요구 가능, 10조 1항 9호 불특정 다수가 공유하는 형태로 데이터 저장 금지, 7호 지정 범위 밖 복제·변경 제한, 4호 楽天アフィリエイト 외 방식의 수익화 금지, 6호 楽天 그룹과 경쟁하는 서비스 금지, 7조 3항 접근 횟수 제한 가능. 공식 문서에 숫자 제한은 없고 짧은 시간 동일 요청 반복 시 일시 차단, 429 반환. AI 관련 조항 없음.
- dongseon 적합성: 가정 내 개인 앱이라 "불특정 다수 공유"에 해당하지 않고, 수익화도 없다. 화면에 楽天 출처 크레딧을 표시하고, 하루 몇 회만 호출하면 된다.
- 위험: 웹사이트 URL/Referer 요구가 사실이면, 공개 도메인이 없는 홈 Mac 앱에서 어떻게 등록할지 확인해야 한다(서버측 호출에 Referer 헤더를 넣는 방식이 허용되는지). 楽天トラベル만의 재고라 Booking·Agoda 가격과 비교는 안 된다. 민박/아파트형 숙소 포함 범위는 미확인.
- 출처: <https://webservice.rakuten.co.jp/documentation/vacant-hotel-search>, <https://webservice.rakuten.co.jp/guide/rule>, <https://library.libecity.com/articles/01KKA2KW1NJPG6638FVW556P5Q>, <https://qiita.com/StreamSolty/items/2a2a203cbc37fefdc115>

### LiteAPI (Nuitée)

- 데이터: 전 세계 호텔 요금(Rates → Prebook → Book), 호텔 콘텐츠. 도시·국가·위경도 검색.
- 접근: 셀프 가입, 샌드박스 무료(카드 불필요, 초당 5회). 프로덕션 키는 결제 수단(카드) 등록 후 해제. 개인 가입 가능 여부는 명시 없음(호텔 업계 경력 불필요라고만 함).
- 가격: Rates/Prebook/Book 및 콘텐츠 엔드포인트 무료(약관 준수와 "합리적인 look-to-book" 조건, 숫자 기준 없음). 가격 지수 $0.05/회, Places $0.01/회.
- 약관 핵심: 라이선스는 "최종 사용자에게 여행 서비스를 제공하기 위해서만". 허용 범위 밖 저장·복제·DB 구축 금지, 스크래핑·대량 다운로드 금지, 경쟁 분석·벤치마킹 금지, 제3자 데이터셋·머신러닝 모델 학습/보강에 사용 금지.
- 위험: 예약 없이 조회만 하면 look-to-book 기준 위반으로 볼 수 있다(기준 불명). LLM에 결과를 넣어 요약하는 것이 "모델 학습/보강"에 해당하는지 애매하다. 샌드박스 요금이 실제 요금인지 미확인. 민박/아파트 포함 여부는 FAQ에 언급 없음.
- 출처: <https://docs.liteapi.travel/reference/api-pricing-usage-costs>, <https://docs.liteapi.travel/docs/faq>, <https://www.liteapi.travel/terms>, <https://docs.liteapi.travel/docs/getting-a-sandbox-key>

### Hotelbeds APItude

- 개발자 포털에서 셀프 가입하면 평가 환경 키를 받는다. 하루 50회 제한, 초과 시 403. 평가 키는 특정 요금·커미션 규칙이 없는 일반 키라 실제 판매가와 다를 수 있다. 운영(프로덕션)은 인증 절차와 상업 계약이 필요.
- 위험: 평가 환경 데이터를 실제 의사결정에 쓰는 것은 용도에 맞지 않는다. 운영 계약은 개인 불가로 보는 것이 맞다.
- 출처: <https://developer.hotelbeds.com/documentation/>

### SerpApi Google Hotels

- 데이터: Google Hotels 결과(1박·총액, OTA별 가격 배열, 평점, 편의시설, 좌표). `vacation_rentals` 파라미터로 민박·별장형 숙소도 검색 가능. 캐시 1시간.
- 가격·위험: 항공편과 같다. Google 스크래핑이라 규칙상 제외. Airbnb류 숙소를 다루는 유일한 셀프 가입 경로이지만 같은 이유로 쓰지 않는다.
- 출처: <https://serpapi.com/google-hotels-api>

### Booking.com Demand API

- 공식 전제조건: Managed Affiliate Partner 등록, 계약 체결 후 계정 매니저가 Partner Centre 접근 제공, 거기서 API 키와 `X-Affiliate-Id` 발급. 일반 제휴 네트워크 가입으로는 안 된다. 2차 출처에 따르면 일반 파트너 약관 v5가 AI 사용에 사전 서면 승인을 요구한다(원문 미확인).
- 출처: <https://developers.booking.com/demand/docs/getting-started/prerequisites>, <https://supergood.ai/api-report-card/booking-com>

### Expedia Rapid

- Expedia 파트너여야 하고 partner.expediagroup.com에서 신청. 승인 후에도 사이트 리뷰 통과 전까지 개발 모드. 숙소·Vrbo(휴가용 임대)를 포함하지만 개인 앱은 대상이 아니다.
- 출처: <https://developers.expediagroup.com/rapid/setup>

### Agoda

- 제휴 프로그램(partners.agoda.com)과 Affiliate Search API, JSON Booking API가 있다는 개발자 FAQ 언급은 있으나, 자격 요건 원문을 받지 못했다(partners.agoda.com 본문 렌더링 실패). B2B API는 직접 계약이 필요하다는 2차 출처가 있다.
- 출처: <https://developer.pps.agoda.com/docs/faq>, <https://www.zentrumhub.com/blog/agoda-hotel-api-guide/>

### Travelpayouts 호텔 (Hotellook)

- Hotellook 프로그램은 2025-10-20 종료, API는 오류를 반환한다. 대체 호텔 API는 FAQ 원문을 받지 못해 미확인(지원 사이트 403).
- 출처: <https://support.travelpayouts.com/hc/en-us/articles/29534131568530-FAQ-on-the-closure-of-Hotellook>

### Google Hotels 공식 API

- Google의 호텔 관련 API(Hotel Center/가격 피드)는 숙소·OTA가 Google에 데이터를 넣는 공급자용이다. 소비자가 가격을 조회하는 공개 API는 찾지 못했다.

### Airbnb

- 2026-10 기준 파트너 페이지에 "현재 API 신규 접근 요청을 받지 않는다"고 되어 있다는 2차 출처. 승인 파트너는 숙소 관리·채널 매니저 소프트웨어 위주. 약관상 봇·크롤러 등 자동 수집 금지. Airbnb 원문은 직접 확인 못 함.
- Airbnb류(민박·아파트) 숙소를 합법적으로 받는 개인용 경로는 이번 조사에서 찾지 못했다. Expedia Rapid(Vrbo)와 Booking.com(아파트 포함)은 계약 전용이다.
- 출처: <https://www.bnbcalc.com/help/articles/does-airbnb-have-an-api>, <https://blog.apify.com/what-you-should-know-about-the-airbnb-api-and-free-alternatives/>

### じゃらん Webサービス

- 2006년 리쿠르트가 시작한 숙소 정보 API다. 현재 신규 등록 가능 여부와 종료 여부를 공식 페이지에서 확인하지 못했다. 쓰려면 리쿠르트 공식 페이지를 직접 확인해야 한다.
- 출처: <https://internet.watch.impress.co.jp/cda/news/2006/06/16/12369.html>

## 확인하지 못한 것

- Ignav 이용약관 본문(저장·AI 사용·재배포 조항)과 데이터 상류 출처
- Travelpayouts 지원 문서 원문(403), 가입 시 웹사이트 등록 필요 여부, Data API의 KR 마켓 ICN/GMP→TYO 캐시 존재 여부
- Duffel이 개인(비사업자) KYC를 받는지
- 楽天 웹사이트 URL/Referer 필수 여부의 공식 근거, 한국 거주자 楽天会員 가입 가능 여부, 楽天トラベル 민박 포함 범위
- LiteAPI 샌드박스 요금이 실제 요금인지, look-to-book 숫자 기준
- Agoda 제휴 API 자격 요건, じゃらん API 현재 상태, Airbnb 파트너 페이지 원문
- 이 문서의 비용 추정은 각 사 공개 가격표 기준이며 환율·세금은 반영하지 않았다.

## 추천

호출량 가정: 항공은 공항 조합 4개(ICN-HND, ICN-NRT, GMP-HND, GMP-NRT) 왕복을 하루 1회씩, 월 약 120회. 숙소는 도쿄 2~3개 후보 지역을 하루 1회씩, 월 60~90회.

### 항공권 추천

1. **Ignav (1순위)**
    - 이유: 개인이 셀프 가입 가능, KRW 마켓 지원, 최근 30분 이내 운임, 예약 링크 제공, Google 스크래핑이 아니라고 밝힘.
    - 예상 비용: 월 120회면 무료 1,000회로 약 8개월(이번 여행 기간 전체) 무료. 이후에도 월 약 $0.24. 무료 한도를 넘는 시점부터는 유료라 사용자 승인 필요.
    - 가입: ignav.com 계정 생성으로 API 키 발급(카드 불필요). 연동 전에 이용약관 원문을 브라우저로 읽고 저장·AI 사용 조항 확인이 선행 조건.
2. **Travelpayouts Aviasales Data API (보조)**
    - 이유: 무료, 개인 토큰으로 사용 가능. 다만 2~7일 캐시라 "가격 추세·날짜 비교" 참고용으로만 쓰고 후보 확정은 Ignav나 예약 링크로 한다.
    - 예상 비용: 무료.
    - 가입: travelpayouts.com 가입 후 API 토큰 발급(웹사이트/프로젝트 등록이 요구될 수 있음, 미확인).

Duffel은 비용은 사실상 0이지만 메타서치 금지·사업자 KYC 조항 때문에, SerpApi는 Google 스크래핑이라 제외했다.

### 숙소 추천

1. **楽天トラベル 空室検索 API (1순위)**
    - 이유: 무료, 공식 API, 도쿄 숙소 실시간 공실·요금과 예약 URL 제공. 개인 비수익 앱에 맞는 약관.
    - 예상 비용: 무료(월 60~90회는 제한 걱정 없음, 호출 간격을 두고 동일 요청 반복을 피할 것).
    - 가입: 楽天会員 가입 → 楽天ウェブサービス에서 앱 등록(applicationId + accessKey). 앱 설정의 웹사이트 URL과 Referer 요구 사항을 등록 화면에서 확인해야 한다. 화면에 楽天 출처 크레딧 표시.
2. **LiteAPI (2순위, 楽天 외 OTA 재고가 필요할 때만)**
    - 이유: 셀프 가입, 요금 조회 무료, 전 세계 호텔.
    - 예상 비용: Rates 엔드포인트만 쓰면 $0. 가격 지수($0.05/회)나 Places($0.01/회)를 쓰면 월 $1~5 수준.
    - 가입: liteapi.travel 가입(샌드박스 무료), 실제 요금은 카드 등록 후 프로덕션 키. 예약 없이 조회만 하는 것이 look-to-book 조건에 맞는지, LLM 요약이 "모델 보강" 금지에 걸리지 않는지 Nuitée에 서면 확인하고 쓰는 것을 권한다.

Airbnb류 숙소는 합법적인 개인용 API가 없다. 이 부분은 지금처럼 사용자가 링크를 붙여넣는 방식을 유지하는 것이 맞다.
