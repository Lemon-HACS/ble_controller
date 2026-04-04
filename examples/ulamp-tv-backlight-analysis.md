# BLE TV 백라이트 (uLamp) 프로토콜 분석 및 Home Assistant 연동 가이드

## 배경

AliExpress에서 구매한 TV 뒤에 부착하는 RGBIC 카메라 연동 백라이트.
카메라가 TV 화면 색상을 인식하여 실시간으로 백라이트 색상을 변경하는 제품.
uLamp 앱(cn.com.uascent)을 통해 BLE로 제어되며, 전원은 TV USB 포트에서 공급.

**목표: Home Assistant에서 전원 ON/OFF만 제어** (밝기/색상 등은 uLamp 앱에서 제어)

---

## 디바이스 정보

| 항목 | 값 |
|------|-----|
| 디바이스 이름 | `UAC088-YH-C0_13E1` |
| MAC 주소 | `25:12:18:20:13:E1` |
| 칩 모델 | WS2811 RGBIC |
| 제조사 앱 | uLamp (cn.com.uascent) |
| Product ID | `5cff2e3a` |
| Product Name | `UAC088-YH-C0` |
| 카테고리 | `101` (light) |
| 네트워크 타입 | BLE |
| 전원 | USB (TV USB 포트에서 공급) |

---

## BLE GATT 구조

### Services

| Handle 범위 | UUID | 설명 |
|-------------|------|------|
| 0x0001 - 0x0007 | `0x1800` | Generic Access |
| 0x0008 - 0x0008 | `0x1801` | Generic Attribute |
| 0x0009 - 0x0013 | `0xFFB0` | **메인 컨트롤 서비스** |
| 0x0014 - 0x001C | `0xFFC0` | 커스텀 서비스 (용도 미확인) |

### 메인 서비스 (FFB0) Characteristics

| Handle | UUID | Properties | 용도 |
|--------|------|-----------|------|
| 0x000B | `0xFFB1` | Write Without Response | **명령 전송 (Write)** |
| 0x000D | `0xFFB2` | Notify | **응답 수신 (Notify)** |

Full UUID 형식:
- Service: `0000ffb0-0000-1000-8000-00805f9b34fb`
- Write Char: `0000ffb1-0000-1000-8000-00805f9b34fb`
- Notify Char: `0000ffb2-0000-1000-8000-00805f9b34fb`

---

## 프로토콜 상세

### 패킷 포맷

```
0A A5 <SEQ> <CMD> [<PARAMS...>]
```

- **`0A A5`**: 프로토콜 헤더 (고정)
- **`SEQ`**: 시퀀스 ID (매 커맨드마다 1씩 증가, 0x00~0xFF)
- **`CMD`**: 커맨드 타입
- **`PARAMS`**: 커맨드별 파라미터 (가변 길이)

### 커맨드 종류 (확인된 것)

#### 상태 조회 커맨드 (4바이트)
시퀀스 `FF`를 사용하는 조회 요청:

```
0A A5 <SEQ> FF
```

접속 직후 연속으로 4개의 상태 조회를 보냄:
| 전송 데이터 | 의미 |
|------------|------|
| `0A A5 0E FF` | 상태 조회 (타입 0E) |
| `0A A5 0F FF` | 상태 조회 (타입 0F) |
| `0A A5 10 FF` | 상태 조회 (타입 10) |
| `0A A5 11 FF` | 상태 조회 (타입 11) |

#### 전원 ON/OFF 커맨드 (5바이트)

```
0A A5 <SEQ> 01 <STATE>
```

- **`CMD = 0x01`**: 전원 제어
- **`STATE`**:
  - `0x00` = **OFF** (끄기)
  - `0x01` = **ON** (켜기)

### 전원 제어 실제 캡처 기록

시간순으로 기록된 4회 전원 토글 (앱 logcat + HCI 패킷 교차 검증):

| 시간 | 전송 데이터 | 동작 | 디바이스 Notify 응답 |
|------|-----------|------|---------------------|
| 08:34:42.007 | `0A A5 12 01 00` | **OFF** | `0AA5000A0000000000000000` (꺼진 상태) |
| 08:34:43.249 | `0A A5 13 01 01` | **ON** | `0AA554050000640001001F` (켜진 상태) |
| 08:34:44.068 | `0A A5 14 01 00` | **OFF** | `0AA5000A0000000000000000` (꺼진 상태) |
| 08:34:44.599 | `0A A5 15 01 01` | **ON** | `0AA554050000640001001F` (켜진 상태) |

### Notify 응답 분석

| 응답 | 의미 |
|------|------|
| `0A A5 00 0A 00 00 00 00 00 00 00 00` | OFF 상태 확인 |
| `0A A5 54 05 00 00 64 00 01 00 1F` | ON 상태 확인 (밝기=0x64=100% 등 상태 포함 추정) |

디바이스는 커맨드 에코도 보냄 (예: `0AA5120100` → Notify로 `0AA5120100` 에코)

---

## 접속 및 제어 순서

1. BLE 스캔으로 `25:12:18:20:13:E1` 디바이스 찾기
2. GATT 연결
3. Service `0xFFB0` 탐색
4. Notify Characteristic (`0xFFB2`, handle 0x000E)에 Notification 활성화 (CCCD에 `0x0100` 쓰기)
5. Write Characteristic (`0xFFB1`)에 커맨드 전송

### 초기 연결 시 앱이 보내는 시퀀스

```
1. CCCD 활성화: handle 0x000E에 WriteRequest(0x0100)  -- Notify 활성화
2. CCCD 활성화: handle 0x0013에 WriteRequest(0x0100)  -- 추가 Notify 활성화
3. 상태 조회: 0AA50EFF, 0AA50FFF, 0AA510FF, 0AA511FF
4. (디바이스 상태 수신 대기)
5. 이후 전원 ON/OFF 커맨드 전송
```

---

## Home Assistant 연동 방법

### 방법 1: Python bleak 스크립트 + shell_command

HA가 돌아가는 머신에 Bluetooth 어댑터가 있다면:

```python
# ble_tv_backlight.py
import asyncio
import sys
from bleak import BleakClient

DEVICE_MAC = "25:12:18:20:13:E1"
WRITE_CHAR_UUID = "0000ffb1-0000-1000-8000-00805f9b34fb"
NOTIFY_CHAR_UUID = "0000ffb2-0000-1000-8000-00805f9b34fb"
NOTIFY_CCCD_HANDLE = 0x000E  # FFB2의 CCCD

seq_counter = 0x01  # 시퀀스 카운터 (0x00~0xFF 순환)

async def power_control(on: bool):
    global seq_counter
    async with BleakClient(DEVICE_MAC) as client:
        # Notify 활성화
        await client.start_notify(NOTIFY_CHAR_UUID, lambda s, d: None)

        # 전원 커맨드 전송
        state = 0x01 if on else 0x00
        cmd = bytes([0x0A, 0xA5, seq_counter, 0x01, state])
        await client.write_gatt_char(WRITE_CHAR_UUID, cmd, response=False)
        seq_counter = (seq_counter + 1) & 0xFF

        await asyncio.sleep(0.5)  # 응답 대기

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "on"
    asyncio.run(power_control(action == "on"))
```

HA `configuration.yaml`:
```yaml
shell_command:
  tv_backlight_on: "python3 /config/scripts/ble_tv_backlight.py on"
  tv_backlight_off: "python3 /config/scripts/ble_tv_backlight.py off"

switch:
  - platform: template
    switches:
      tv_backlight:
        friendly_name: "TV 백라이트"
        turn_on:
          service: shell_command.tv_backlight_on
        turn_off:
          service: shell_command.tv_backlight_off
```

### 방법 2: ESPHome BLE Client

ESP32 보드가 있다면 ESPHome의 `ble_client` 컴포넌트 사용:

```yaml
ble_client:
  - mac_address: "25:12:18:20:13:E1"
    id: tv_backlight

switch:
  - platform: template
    name: "TV Backlight"
    id: tv_backlight_switch
    turn_on_action:
      - ble_client.ble_write:
          id: tv_backlight
          service_uuid: "0000ffb0-0000-1000-8000-00805f9b34fb"
          characteristic_uuid: "0000ffb1-0000-1000-8000-00805f9b34fb"
          value: [0x0A, 0xA5, 0x01, 0x01, 0x01]
    turn_off_action:
      - ble_client.ble_write:
          id: tv_backlight
          service_uuid: "0000ffb0-0000-1000-8000-00805f9b34fb"
          characteristic_uuid: "0000ffb1-0000-1000-8000-00805f9b34fb"
          value: [0x0A, 0xA5, 0x01, 0x01, 0x00]
```

---

## 디바이스 메타데이터 (앱에서 확인된 속성)

앱 로그에서 확인된 디바이스 프로퍼티:

| Property ID | 이름 | 타입 | DP | 값 범위 |
|-------------|------|------|-----|---------|
| `brightness` | 밝기 | int (percent) | 1 | 1~100 (step 25) |
| `color` | 색상 | enum | 2 | 黑色(0), 深青色(35723), 蓝色(255), 등 |
| `powerstate` | 전원 | boolean | 4 | 0=OFF, 1=ON |

---

## 주의사항

- **시퀀스 ID**: 매 커맨드마다 증가하지만, 저가 BLE 디바이스들은 보통 시퀀스 ID를 검증하지 않음. 고정값(예: 0x01)으로 테스트 먼저 해볼 것.
- **BLE 연결 유지**: BLE 특성상 연결이 끊어질 수 있음. 재연결 로직 필요.
- **TV USB 전원**: TV가 꺼지면 USB 전원도 끊어져서 디바이스 자체가 꺼짐. TV가 켜진 상태에서만 BLE 제어 가능.
- **uLamp 앱과 동시 사용**: BLE는 기본적으로 1:1 연결이므로, HA에서 연결 중이면 uLamp 앱에서 연결 불가. 사용 후 연결을 끊어주거나, 앱/HA 중 하나만 사용할 것.
- **Write 방식**: `Write Without Response` (ATT opcode 0x52)를 사용함. bleak에서는 `response=False` 옵션 필수.

---

## 분석 소스

- Android 버그 리포트 덤프 (2026-04-04)
  - `FS/data/log/bt/btsnoop_hci.log`: HCI 패킷 캡처
  - `dumpstate.txt`: 앱 logcat (cn.com.uascent BleWriteAop/LoggerAop)
- 교차 검증: HCI 패킷과 앱 로그의 타임스탬프 및 데이터 일치 확인 완료
