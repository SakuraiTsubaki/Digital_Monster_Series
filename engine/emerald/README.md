# Emerald Engine Profile

Digital_Monster_Series는 디지몬 공식 데이터를 보존하는 것에 그치지 않고, **Pokemon Emerald / pokeemerald-expansion 엔진에서 Digital Monster Series를 플레이할 수 있는 구현**을 목표로 한다.

## 기준선

- 일본판 Emerald(BPEJ)를 ROM 기준선으로 우선 사용한다.
- 제공된 일본/영문/독문/불문/이문/서문 ROM+SAVE 6쌍을 함께 검증한다.
- 원본 ROM은 저장소에 커밋하지 않고 해시와 구조 파라미터만 보존한다.
- 런타임/확장 기준은 SakuraiTsubaki/EMERALD에서 검증한 Emerald 프로필을 따른다.
- 확장 엔진 기준은 rh-hideout/pokeemerald-expansion 고정 리비전 75b806a3ab57a81ff1eb6179288981f0b3cc3050이다.

## 핵심

원본 Emerald ROM은 16 MiB이며 정상 GBA 선형 ROM 프로필의 목표/상한은 32 MiB다. SAVE는 128 KiB Flash, 32섹터, 2슬롯 구조를 유지한다.

현재 디지몬 도감 1,320개와 Appmon 148개를 독립 엔티티로 합치면 1,468개다. Emerald 확장 프로필의 11비트 species 저장 범위(1..2047)에 들어가므로 엔티티 ID 폭은 당장 넓히지 않는다.

기술은 먼저 고유 기술 카탈로그를 만들어야 한다. 현재 소스 데이터에는 Digimon 필살기 행 2,593개와 Appmon 필살기 행 279개가 있으나 이는 '배정 행'이지 고유 기술 수가 아니다. 중복을 정규화한 고유 기술 수가 2,047을 넘는지 확인한 뒤 move ID 폭 확장 여부를 결정한다.

공식 Digimon의 '타입/型' 분류는 현재 142개 고유값이 있으므로 Emerald의 전투 타입 슬롯에 일대일 대응시키지 않는다. 공식 타입/속성/등급은 별도 메타데이터로 보존하고 전투 상성은 별도 어댑터 계층에서 설계한다.

## 파일

- game-parameters.json — Emerald 런타임의 ROM/SAVE/엔티티/게임플레이 파라미터
- digital-monster-mapping.json — Emerald 데이터 모델 ↔ Digimon 데이터 모델 대응
- emerald-binary-baseline.csv — 제공된 6개 Emerald ROM/SAVE 식별 기준선

이 디렉터리가 이후 전투, 진화, 기술, 아이템, 맵, 조우, 세이브, UI를 Digital Monster Series 방식으로 교체하는 기준점이다.
