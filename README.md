# Digital Monster Series

**Pokemon Emerald / pokeemerald-expansion 엔진 위에서 Digital Monster Series를 플레이할 수 있도록 구현하는 프로젝트입니다.**

일본어 공식 자료를 최우선 기준으로 디지털 몬스터 시리즈의 공식 데이터를 조사·검증·구조화하고, 그 데이터를 Emerald 엔진의 전투·성장·기술·아이템·진화·맵·세이브 시스템에 연결합니다.

## Emerald 엔진 기준선

엔진 파라미터 위치: [`engine/emerald/`](engine/emerald/)

현재 기준:

- 일본판 Emerald(BPEJ)를 ROM 기준선으로 우선 사용
- 일본/영문/독문/불문/이문/서문 6개 원본 Emerald ROM+SAVE 쌍 검증
- 원본 ROM 16 MiB
- 표준 GBA 선형 확장 프로필 32 MiB
- SAVE 128 KiB Flash / 32 sectors / 2 slots
- Digimon/Appmon 엔티티 ID는 Emerald의 species 저장 필드를 백엔드로 사용
- 기술은 move 저장 필드를 백엔드로 사용하며, 공식 일본어 기술 2,557개가 확인되어 11비트(2,047)를 넘으므로 12비트(4,095) 저장 패치를 적용
- 공식 Digimon 타입·속성·Appmon 등급/앱 종류는 Pokémon 전투 타입과 섞지 않고 별도 메타데이터로 유지
- ROM 바이너리는 저장소에 커밋하지 않고 해시·구조·파라미터만 보존

현재 공식 데이터 1,320 Digimon + 148 Appmon = 1,468 엔티티는 11비트 species ID 범위(최대 2,047)에 들어갑니다.

## 현재 데이터셋

### 디지몬 공식 도감 / デジモン図鑑

- 원본: <https://digimon.net/reference/>
- 기준 언어: 일본어
- 조사 시점: 2026-09-21 UTC
- 사이트 표시 등록 수: 1,320
- 목록 및 상세 페이지 확인: 1,320
- 실패 및 누락: 0

데이터 위치: [`data/digimon_reference/`](data/digimon_reference/)

주요 결과물:

- 전체 Master CSV
- 분할 Master JSON과 파트 매니페스트
- 레벨·타입·속성 고유값
- 필살기 목록
- 공식 이미지 및 추가 일러스트 URL 목록
- 누락값·예외·중복 이름 검증
- 사이트 구조 및 전수 수집 검증 보고서
- 재현 가능한 수집 스크립트

일본어 이름과 공식 분류 표기는 원문을 유지합니다. 임의 번역이나 추측으로 누락값을 채우지 않습니다.

### Appmon 공식 도감 / アプモン図鑑

- 원본: <https://digimon.net/appmon/>
- 기준 언어: 일본어
- 공식 언어 대조: 한국어·영어·중국어 간체·번체
- 사이트 표시 등록 수: 148
- ID 및 언어별 상세 페이지 확인: 148개, 총 740페이지
- 실패·누락·중복 ID: 0

데이터 위치: [`appmon/`](appmon/)

주요 결과물:

- 전체 Master CSV·JSON
- 다국어 명칭 대응표
- 그레이드·속성·앱 종류별 목록
- 필살기 279건의 다국어 대응
- 번역·표기·이미지 예외 목록
- 동적 관련 Appmon 추천 스냅샷
- 통합 XLSX와 전체 결과물 ZIP
- SHA-256 검증 자료

Appmon 자료도 일본어 원문을 정본으로 보존하며, 비일본어 페이지의 기계번역 가능성과 확인된 번역 문제를 별도로 기록합니다.
