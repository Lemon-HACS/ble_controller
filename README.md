# BLE Controller

Home Assistant용 범용 BLE(Bluetooth Low Energy) 커스텀 통합 구성요소입니다.
전용 통합이 없는 BLE 디바이스를 Service UUID, Characteristic UUID, 전송 데이터만 설정하면 HA에서 바로 제어할 수 있습니다.

---

## 시작하기 전에

> **BLE 프로토콜을 알아야 합니다**: 이 통합은 디바이스의 GATT Service UUID, Characteristic UUID, 전송할 hex 데이터를 직접 입력하는 방식입니다. 이 용어들이 생소하다면 [BLE GATT 기초](./docs/gatt-basics.md)를 먼저 읽어보세요. 프로토콜 파악 방법은 [HCI 로그 캡처 가이드](./docs/hci-log-capture.md)를 참고하세요.

> **BLE는 실패할 수 있습니다**: BLE 특성상 연결이 한 번에 성공하지 않을 수 있습니다. 이 통합은 `bleak-retry-connector` 기반 자동 재시도를 내장하고 있으므로 일시적인 연결 실패는 자동으로 복구됩니다. 다만 반복적으로 실패한다면 어댑터 거리 등을 점검하세요.

---

## 기능

- **3가지 엔티티 타입 지원**
  - **스위치**: ON/OFF 토글 (예: 조명 전원)
  - **버튼**: 단발성 커맨드 (예: 리셋, 모드 전환)
  - **셀렉트**: 다중 선택 (예: 에어컨 모드 냉방/난방/제습)
- **범용 BLE 제어**: 디바이스 프로토콜에 의존하지 않는 범용 GATT Write
- **UI 기반 설정**: BLE 디바이스 스캔 → 엔티티 타입 선택 → UUID 및 데이터 입력
- **상태 확인**: Notify Characteristic 응답을 통한 실제 디바이스 상태 반영 (스위치)
- **연결 유지 (Keep Alive)**: 백그라운드 자동 연결 + 주기적 상태 조회로 연결 끊김 방지
- **Keepalive 주기 설정**: 디바이스별로 keepalive 간격 조절 가능 (기본 10초, 연결 불안정 시 5~7초 권장)
- **GATT 타임아웃 보호**: 모든 BLE Write에 3초 타임아웃 적용, 무한 hang 방지
- **HACS 지원**: HACS를 통해 간단하게 설치 및 업데이트 가능

---

## 설치

### HACS를 통한 설치 (권장)

1. HACS → 통합 구성요소 → 우측 상단 메뉴 → **사용자 지정 저장소 추가**
2. URL: `https://github.com/Lemon-HACS/ble_controller`, 카테고리: `통합 구성요소`
3. **BLE Controller** 검색 후 다운로드
4. Home Assistant 재시작

### 수동 설치

1. 이 저장소를 클론하거나 ZIP으로 다운로드
2. `custom_components/ble_controller/` 폴더를 Home Assistant의 `config/custom_components/` 경로에 복사
3. Home Assistant 재시작

---

## 설정

설치 후 Home Assistant UI에서 설정합니다.

**설정 → 기기 및 서비스 → 통합 구성요소 추가 → BLE Controller**

### 설정 순서

1. **BLE 디바이스 선택**: 주변 BLE 디바이스를 스캔하여 목록에서 선택
2. **엔티티 타입 선택**: 스위치 / 버튼 / 셀렉트 중 선택
3. **GATT 설정**: UUID 및 전송 데이터 입력
4. **Notify 설정** (스위치만, 선택): 상태 확인용 Notify Characteristic 설정

### 공통 설정 항목

모든 엔티티 타입에서 공통으로 입력하는 항목입니다.

| 항목 | 필수 | 설명 |
|------|------|------|
| **Service UUID** | O | 디바이스의 GATT Service UUID |
| **Write Characteristic UUID** | O | 데이터를 보낼 Characteristic UUID |
| **Write With Response** | X | Write 후 디바이스의 ACK를 기다릴지 여부 (기본: OFF). nRF Connect에서 Write 속성이 `Write Without Response`(0x04)만 있으면 반드시 OFF. ON으로 설정했는데 디바이스가 ACK를 지원하지 않으면 명령이 타임아웃됩니다. |
| **Keep Alive** | X | 체크 시 백그라운드에서 BLE 연결을 유지하고 끊어지면 자동 재연결. 해제 시 명령을 보낼 때만 연결하고 15초 후 자동 해제. |
| **Keepalive 주기** | X | Keep Alive 활성화 시 이 간격(초)마다 상태 조회를 보내 연결을 유지 (기본: 10초). 연결이 자주 끊기면 5~7초로 줄이세요. |

### 엔티티 타입별 추가 항목

**스위치** — ON/OFF 각각에 보낼 hex 데이터를 입력합니다. 선택적으로 Notify Characteristic을 설정하면 디바이스가 보내는 응답을 통해 실제 ON/OFF 상태를 확인할 수 있습니다. ([Notify 상세 설명](./docs/notify.md))

**버튼** — 버튼을 누를 때 보낼 hex 데이터를 하나 입력합니다.

**셀렉트** — 여러 옵션을 `라벨=hex데이터` 형식으로 줄바꿈 구분하여 입력합니다.
```
냉방=0aa50201
난방=0aa50202
제습=0aa50203
```

### Notify 설정 (스위치)

스위치 엔티티에서 디바이스의 실제 ON/OFF 상태를 확인하려면 Notify를 설정합니다. 모르면 건너뛰어도 됩니다.

| 항목 | 설명 |
|------|------|
| **Notify Characteristic UUID** | 디바이스가 상태 변경을 알려줄 때 사용하는 Notify 속성의 UUID. nRF Connect에서 같은 서비스 내 Notify 속성이 있는 항목 |
| **ON 상태 응답 패턴** | Notify 응답에 이 hex 패턴이 포함되면 ON으로 판단 |
| **OFF 상태 응답 패턴** | Notify 응답에 이 hex 패턴이 포함되면 OFF로 판단 |
| **상태 조회 커맨드** | BLE 연결 직후 디바이스에 보내는 "지금 상태가 뭐야?" 명령 (hex). Keep Alive 활성화 시 재연결할 때마다 자동 전송되어 HA 재시작 후에도 상태를 바로 반영 |

> **참고**: Notify 패턴이나 상태 조회 커맨드를 입력하려면 Notify UUID가 반드시 필요합니다.

### 설정 변경

**설정 → 기기 및 서비스 → BLE Controller → 옵션** 에서 설정 후에도 ON/OFF 데이터, Notify 설정, Keep Alive, Keepalive 주기 등을 변경할 수 있습니다.

---

## Keep Alive 동작 방식

Keep Alive를 활성화하면 다음과 같이 동작합니다.

1. **HA 시작 시**: 즉시 디바이스에 BLE 연결 시도
2. **연결 성공 후**: Notify 구독 + 상태 조회 커맨드 자동 전송 (설정된 경우)
3. **주기적 ping**: 설정된 간격(기본 10초)마다 상태 조회를 보내 연결 유지
4. **연결 끊김 감지**: 끊어지면 다음 주기에 자동 재연결

Keep Alive를 끄면 명령을 보낼 때만 연결하고, 15초간 명령이 없으면 자동으로 연결을 해제합니다. 제조사 앱과 병행해야 하는 경우 끄는 것이 좋습니다.

---

## BLE 프로토콜 파악 방법

이 통합은 BLE 프로토콜을 이미 알고 있는 디바이스에 사용합니다. 프로토콜을 모르는 경우 Android의 HCI 스눕 로그를 캡처하여 분석할 수 있습니다.

자세한 단계별 가이드는 [HCI 로그 캡처 가이드](./docs/hci-log-capture.md)를 참고하세요.

---

## 디바이스별 설정 예시

구체적인 디바이스별 설정 예시와 프로토콜 분석 자료는 [examples/](./examples/) 폴더를 참고하세요.

---

## 참고 문서

BLE 개념이 생소하다면 다음 문서를 참고하세요.

- [BLE GATT 기초](./docs/gatt-basics.md) — Service, Characteristic, UUID란?
- [Write 방식 (With/Without Response)](./docs/write-modes.md) — 두 Write 방식의 차이
- [Notify와 상태 확인](./docs/notify.md) — Notify로 디바이스 상태를 확인하는 방법
- [HCI 로그 캡처 가이드](./docs/hci-log-capture.md) — BLE 프로토콜을 파악하는 방법

---

## 요구 사항

- Home Assistant 2026.4 이상
- HACS (권장)
- Bluetooth 어댑터 (RPi 내장 BT, USB BT 동글 등)
- Python 패키지: `bleak-retry-connector>=4.6.0` (자동 설치)
