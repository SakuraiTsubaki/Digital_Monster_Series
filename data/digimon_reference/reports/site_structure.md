# デジモン図鑑 사이트 구조 조사

- 기준 URL: https://digimon.net/reference/
- 수집 시각(UTC): 2026-10-01T13:57:36.887645+00:00
- 공식 표시 등록 수: 1321
- 목록 방식: 초기 HTML 이후 `./request.php`에 XHR GET 요청. `next` 오프셋으로 추가 로딩.
- 한 요청의 기본 반환량: 첫 응답 96개
- 상세 URL: `detail.php?directory_name={directory_name}`
- 메인 이미지: `/cimages/digimon/{directory_name}.jpg`가 기본 규칙이나 실제 상세 DOM의 URL을 기록함.
- 추가 일러스트: 상세 페이지 `.p-ref__piclist .p-ref__picitem img`의 두 번째 이후 이미지.
- 언어 경로: 일본어 `/reference/`, 영어 `/reference_en/`, 간체 `/reference_zh-CHS/`, 번체 `/reference_zh-CHT/`, 한국어 `/reference_ko/`; 상세 페이지는 같은 `directory_name` 쿼리를 사용.
- 검색: `digimon_name`, 오십음 `name`, `digimon_level`, `attribute`, `type`; 목록 응답은 JSON.
- 마스터 기준: 일본어 페이지 원문. 정규화 필드는 현재 원문과 동일하게 두어 변환/추측을 하지 않음.
- 재현: 저장된 `scrape_digimon_reference.py` 실행 결과이며 `raw/index.html`, `raw/details/*.html`, SHA-256을 검증 근거로 포함.
