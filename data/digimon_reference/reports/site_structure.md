# 사이트 구조 조사 보고서

## 목록과 로딩

- 시작 URL: `https://digimon.net/reference/`
- 초기 HTML에는 등록 수와 필터 UI가 있으나 전체 카드 목록은 없다.
- 브라우저는 `GET ./request.php`를 XHR로 호출한다.
- 파라미터: `digimon_name`, `name`, `digimon_level`, `attribute`, `type`, `next`, 선택적으로 `view_more`.
- 빈 필터 전수 수집 결과: 96행씩 13회 + 마지막 72행, 총 14회. `next=-1`에서 종료.
- 목록 응답의 공식 내부 키: `directory_name`, `name`, `level`, `level_2`, `level_order`, `relate_word6`, `icon_new`, `icon_20th`.

## 상세와 이미지

- 상세 URL: `https://digimon.net/reference/detail.php?directory_name={directory_name}`
- 기본 이미지 관찰 규칙: `https://digimon.net/cimages/digimon/{directory_name}.jpg`.
- 실제 데이터는 상세 DOM의 `.p-ref__piclist .p-ref__picitem img`를 기준으로 기록했다.
- 첫 이미지가 메인, 두 번째 이후가 추가 공식 일러스트다.
- 관련 개체는 상세 페이지의 관련 목록에서 별도 `directory_name`과 URL로 기록했다.

## 언어 구조

| 언어 | 경로 |
|---|---|
| 일본어(마스터) | `/reference/` |
| 영어 | `/reference_en/` |
| 중국어 간체 | `/reference_zh-CHS/` |
| 중국어 번체 | `/reference_zh-CHT/` |
| 한국어 | `/reference_ko/` |

언어별 상세 페이지도 동일한 `directory_name` 쿼리를 사용한다. 공식 사이트 자체가 일본어 기본 및 다른 언어의 기계 번역 가능성을 고지하므로 일본어만 Master Reference로 사용했다.

## 필터 값과 원문 보존

필터 UI의 실제 값은 `taxonomy/*.json`의 `index_filter_values`에, 상세 페이지에서 실제 관찰된 고유값은 `detail_page_values`에 분리했다. 괄호가 포함된 크로스워즈 레벨은 DOM 줄바꿈까지 원문으로 보존하며 임의 통합하지 않는다.
