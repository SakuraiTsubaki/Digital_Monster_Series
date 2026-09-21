# 누락값과 예외 케이스

- 속성 미기재: 108개. `attribute_raw=null`로 보존.
- 실질 필살기 미기재: 9개. 공식 DOM의 원문 `・`는 `special_moves_raw`에 보존하고 배열은 빈 목록으로 기록.
- 추가 일러스트 보유: 14개.
- 일본어 이름 완전 중복: 5그룹. 각 그룹의 개체는 `directory_name`으로 분리.
- 콜론·모드명 등 공통 접두어 기반 유사 이름 그룹은 `exceptions.json`의 `similar_name_groups`에 보존.
- 일반 레벨 외 괄호 포함 표기와 `不明`은 `taxonomy/levels.json`에 별도 고유값으로 유지.

상세 개체 목록은 `exceptions.json`을 참조한다.
