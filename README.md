# BLE Controller

Home Assistant용 범용 BLE(Bluetooth Low Energy) 커스텀 통합 구성요소입니다.
전용 통합이 없는 BLE 디바이스를 Service UUID, Characteristic UUID, 전송 데이터만 설정하면 HA에서 바로 제어할 수 있습니다.

---

## 기능

- **3가지 엔티티 타입 지원**
  - **스위치**: ON/OFF 토글 (예: 조명 전원)
  - **버튼**: 단발성 커맨드 (예: 리셋, 모드 전환)
  - **셀렉트**: 다중 선택 (예: 에어컨 모드 냉방/난방/제습)
- **범용 BLE 제어**: 디바이스 프로토콜에 의존하지 않는 범용 GATT Write
- **UI 기반 설정**: BLE 디바이스 스캔 → 엔티티 타입 선택 → UUID 및 데이터 입력
- **Write 방식 선택**: Write With Response / Write Without Response 옵션 제공
- **상태 확인**: Notify Characteristic 응답을 통한 실제 디바이스 상태 반영 (스위치, 선택)
- **앱 공존**: 커맨드 전송 시에만 BLE 연결하고 즉시 해제하여 제조사 앱과의 충돌 최소화
- **자동 재연결**: `bleak-retry-connector` 기반 연결 안정성 확보
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
3. **GATT 설정**: 엔티티 타입에 따라 UUID, 전송 데이터 입력
4. **Notify 설정** (스위치만, 선택): 상태 확인용 Notify Characteristic 설정

### 엔티티별 설정 항목

#### 스위치 (ON/OFF)

| 항목 | 필수 | 설명 |
|------|------|------|
| Service UUID | O | GATT Service UUID |
| Write Characteristic UUID | O | Write할 Characteristic UUID |
| ON 데이터 (hex) | O | 전원 ON 시 보낼 데이터 |
| OFF 데이터 (hex) | O | 전원 OFF 시 보낼 데이터 |
| Write With Response | X | Write 후 응답 대기 여부 (기본: OFF) |
| Notify Characteristic UUID | X | 상태 확인용 Notify UUID |
| ON/OFF 응답 패턴 (hex) | X | Notify 응답에서 상태를 판별할 패턴 |

#### 버튼 (단발성 커맨드)

| 항목 | 필수 | 설명 |
|------|------|------|
| Service UUID | O | GATT Service UUID |
| Write Characteristic UUID | O | Write할 Characteristic UUID |
| 전송 데이터 (hex) | O | 버튼 누를 때 보낼 데이터 |
| Write With Response | X | Write 후 응답 대기 여부 (기본: OFF) |

#### 셀렉트 (다중 선택)

| 항목 | 필수 | 설명 |
|------|------|------|
| Service UUID | O | GATT Service UUID |
| Write Characteristic UUID | O | Write할 Characteristic UUID |
| 옵션 목록 | O | `라벨=hex데이터` 형식, 줄바꿈 구분 |
| Write With Response | X | Write 후 응답 대기 여부 (기본: OFF) |

셀렉트 옵션 입력 형식:
```
냉방=0aa50201
난방=0aa50202
제습=0aa50203
```

> **재설정**: 설정 → 기기 및 서비스 → BLE Controller → 우측 메뉴 → **재설정** 에서 언제든 변경 가능합니다.

---

## 사용법

### 자동화 예시: 스위치

```yaml
automation:
  - alias: "TV 켜지면 백라이트 켜기"
    trigger:
      - platform: state
        entity_id: media_player.living_room_tv
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.ble_controller_uac088
```

### 자동화 예시: 버튼

```yaml
automation:
  - alias: "매일 아침 BLE 디바이스 리셋"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: button.press
        target:
          entity_id: button.ble_controller_reset
```

### 자동화 예시: 셀렉트

```yaml
automation:
  - alias: "실내 온도에 따라 에어컨 모드 변경"
    trigger:
      - platform: numeric_state
        entity_id: sensor.room_temperature
        above: 28
    action:
      - service: select.select_option
        target:
          entity_id: select.ble_controller_aircon_mode
        data:
          option: "냉방"
```

---

## 디바이스별 설정 예시

### uLamp TV 백라이트 (UAC088-YH-C0)

AliExpress에서 판매되는 카메라 연동 RGBIC TV 백라이트. uLamp 앱으로 제어.

**스위치 설정:**

| 항목 | 값 |
|------|-----|
| Service UUID | `0000ffb0-0000-1000-8000-00805f9b34fb` |
| Write Characteristic | `0000ffb1-0000-1000-8000-00805f9b34fb` |
| ON 데이터 | `0aa5010101` |
| OFF 데이터 | `0aa5010100` |
| Write With Response | OFF |

> 상세 BLE 프로토콜 분석은 [examples/ulamp-tv-backlight-analysis.md](./examples/ulamp-tv-backlight-analysis.md)를 참고하세요.

---

## BLE 프로토콜 파악 방법

이 통합은 BLE 프로토콜을 이미 알고 있는 디바이스에 사용합니다. 프로토콜을 모르는 경우:

1. Android **개발자 옵션**에서 **블루투스 HCI 스눕 로그** 활성화
2. 제조사 앱에서 디바이스를 몇 번 제어 (켜기/끄기, 모드 변경 등)
3. **버그 리포트** 추출 후 `btsnoop_hci.log`를 Wireshark로 분석
4. ATT Write Command/Request에서 각 동작에 해당하는 hex 데이터 확인
5. 이 통합에 해당 데이터 입력

---

## 주의사항

| 항목 | 설명 |
|------|------|
| **⚠️ 다른 BLE 통합과의 충돌** | **Passive BLE Monitor**, **Xiaomi BLE** 등 BLE를 사용하는 다른 통합이 활성화되어 있으면 연결 실패가 빈번하게 발생할 수 있습니다. 이러한 통합들은 Bluetooth 어댑터를 상시 점유(스캔/연결)하여 이 통합의 GATT Write 연결을 방해합니다. 충돌이 의심되면 다른 BLE 통합을 비활성화하거나, 별도의 Bluetooth 어댑터를 사용하세요. |
| **BLE 1:1 연결** | BLE 통신 중에는 제조사 앱에서 연결할 수 없습니다. 이 통합은 커맨드 전송 시에만 짧게 연결하여 충돌을 최소화합니다. |
| **Bluetooth 어댑터** | Home Assistant가 실행되는 기기에 Bluetooth 어댑터가 필요합니다. (RPi 내장 BT, USB BT 동글 등) |
| **도달 거리** | BLE 특성상 디바이스와의 거리가 가까워야 안정적으로 동작합니다. |
| **프로토콜 파악** | 이 통합은 BLE 프로토콜을 이미 알고 있는 디바이스에 사용합니다. 프로토콜 분석은 별도로 수행해야 합니다. |

---

## 요구 사항

- Home Assistant 2026.4 이상
- HACS (권장)
- Bluetooth 어댑터 (RPi 내장 BT 등)
- Python 패키지: `bleak-retry-connector>=4.6.0` (자동 설치)
