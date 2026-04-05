# BLE Controller

Home Assistant용 범용 BLE(Bluetooth Low Energy) 커스텀 통합 구성요소입니다.
전용 통합이 없는 BLE 디바이스를 Service UUID, Characteristic UUID, 전송 데이터만 설정하면 HA에서 바로 제어할 수 있습니다.

---

## 시작하기 전에

> **다른 BLE 통합과의 충돌**: **Passive BLE Monitor**, **Xiaomi BLE** 등 BLE를 사용하는 다른 통합이 활성화되어 있으면 연결 실패가 빈번하게 발생할 수 있습니다. 이러한 통합들은 Bluetooth 어댑터를 상시 점유(스캔/연결)하여 이 통합의 GATT Write 연결을 방해합니다. 충돌이 의심되면 다른 BLE 통합을 비활성화하거나, 별도의 Bluetooth 어댑터를 사용하세요.

> **BLE 프로토콜을 알아야 합니다**: 이 통합은 디바이스의 GATT Service UUID, Characteristic UUID, 전송할 hex 데이터를 직접 입력하는 방식입니다. 제조사 앱의 BLE 통신을 캡처하여 프로토콜을 먼저 파악해야 합니다. 방법은 [BLE 프로토콜 파악 방법](#ble-프로토콜-파악-방법)을 참고하세요.

> **BLE는 실패할 수 있습니다**: BLE 특성상 연결이 한 번에 성공하지 않을 수 있습니다. 이 통합은 `bleak-retry-connector` 기반 자동 재시도를 내장하고 있으므로 일시적인 연결 실패는 자동으로 복구됩니다. 다만 반복적으로 실패한다면 어댑터 거리, 다른 BLE 통합 충돌 등을 점검하세요.

---

## 기능

- **3가지 엔티티 타입 지원**
  - **스위치**: ON/OFF 토글 (예: 조명 전원)
  - **버튼**: 단발성 커맨드 (예: 리셋, 모드 전환)
  - **셀렉트**: 다중 선택 (예: 에어컨 모드 냉방/난방/제습)
- **범용 BLE 제어**: 디바이스 프로토콜에 의존하지 않는 범용 GATT Write
- **UI 기반 설정**: BLE 디바이스 스캔 → 엔티티 타입 선택 → UUID 및 데이터 입력
- **상태 확인**: Notify Characteristic 응답을 통한 실제 디바이스 상태 반영 (스위치, 셀렉트)
- **앱 공존**: 커맨드 전송 시에만 BLE 연결하고 즉시 해제하여 제조사 앱과의 충돌 최소화
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
4. **Notify 설정** (선택): 상태 확인용 Notify Characteristic 설정

### 공통 설정 항목

모든 엔티티 타입에서 공통으로 입력하는 항목입니다.

| 항목 | 필수 | 설명 |
|------|------|------|
| **Service UUID** | O | 디바이스의 GATT Service UUID |
| **Write Characteristic UUID** | O | 데이터를 보낼 Characteristic UUID |
| **Write With Response** | X | Write 후 디바이스의 응답을 기다릴지 여부 (기본: OFF). 디바이스가 Write Response를 요구하는 경우 ON으로 설정하세요. |

### 엔티티 타입별 추가 항목

**스위치** — ON/OFF 각각에 보낼 hex 데이터를 입력합니다. 선택적으로 Notify Characteristic을 설정하면 디바이스가 보내는 응답을 통해 실제 ON/OFF 상태를 확인할 수 있습니다.

**버튼** — 버튼을 누를 때 보낼 hex 데이터를 하나 입력합니다.

**셀렉트** — 여러 옵션을 `라벨=hex데이터` 형식으로 줄바꿈 구분하여 입력합니다.
```
냉방=0aa50201
난방=0aa50202
제습=0aa50203
```

> **재설정**: 설정 → 기기 및 서비스 → BLE Controller → 우측 메뉴 → **재설정** 에서 언제든 변경 가능합니다.

---

## BLE 프로토콜 파악 방법

이 통합은 BLE 프로토콜을 이미 알고 있는 디바이스에 사용합니다. 프로토콜을 모르는 경우:

1. Android **개발자 옵션**에서 **블루투스 HCI 스눕 로그** 활성화
2. 제조사 앱에서 디바이스를 몇 번 제어 (켜기/끄기, 모드 변경 등)
3. **버그 리포트** 추출 후 `btsnoop_hci.log` 파일 확보
4. Wireshark로 열어 ATT Write Command/Request에서 각 동작에 해당하는 hex 데이터 확인
5. 이 통합에 해당 데이터 입력

> **Tip**: Wireshark 분석이 어렵다면, 추출한 `btsnoop_hci.log`를 AI(ChatGPT, Claude 등)에게 전달하고 "이 BLE 로그에서 GATT Write 커맨드를 분석해줘"라고 요청하면 훨씬 쉽게 프로토콜을 파악할 수 있습니다.

---

## 디바이스별 설정 예시

구체적인 디바이스별 설정 예시와 프로토콜 분석 자료는 [examples/](./examples/) 폴더를 참고하세요.

---

## 요구 사항

- Home Assistant 2026.4 이상
- HACS (권장)
- Bluetooth 어댑터 (RPi 내장 BT, USB BT 동글 등)
- Python 패키지: `bleak-retry-connector>=4.6.0` (자동 설치)
