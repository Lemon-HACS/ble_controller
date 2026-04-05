# uLamp TV 백라이트 (UAC088-YH-C0)

AliExpress에서 판매되는 카메라 연동 RGBIC TV 백라이트입니다. 카메라가 TV 화면 색상을 인식하여 실시간으로 백라이트 색상을 변경합니다. uLamp 앱(cn.com.uascent)으로 BLE 제어되며, 전원은 TV USB 포트에서 공급됩니다.

![uLamp TV 백라이트 제품 이미지](./ulamp-tv-backlight.webp)

**구매 링크**: [AliExpress](https://ko.aliexpress.com/item/1005008810337204.html)

---

## BLE Controller 설정 (빠른 시작)

이 디바이스를 BLE Controller에서 제어하려면 다음 값을 입력하세요.

### 스위치 (전원 ON/OFF)

| 항목 | 값 |
|------|-----|
| Service UUID | `0000ffb0-0000-1000-8000-00805f9b34fb` |
| Write Characteristic UUID | `0000ffb1-0000-1000-8000-00805f9b34fb` |
| ON 데이터 | `0aa5010101` |
| OFF 데이터 | `0aa5010100` |
| Write With Response | OFF |

> 시퀀스 바이트(3번째 바이트)가 고정값 `01`로 되어 있지만, 이 디바이스는 시퀀스를 검증하지 않으므로 정상 동작합니다.

### Notify 설정 (선택)

상태 확인을 원하면 추가로 설정하세요.

| 항목 | 값 |
|------|-----|
| Notify Characteristic UUID | `0000ffb2-0000-1000-8000-00805f9b34fb` |
| ON 응답 패턴 | `0aa554` |
| OFF 응답 패턴 | `0aa5000a` |

---

## 디바이스 정보

| 항목 | 값 |
|------|-----|
| 디바이스 이름 | `UAC088-YH-C0` (뒤에 MAC 일부 붙음) |
| 칩 모델 | WS2811 RGBIC |
| 제조사 앱 | uLamp (cn.com.uascent) |
| 네트워크 타입 | BLE |
| 전원 | USB (TV USB 포트에서 공급) |

---

## 주의사항

- **TV USB 전원**: TV가 꺼지면 USB 전원도 끊어져서 디바이스 자체가 꺼집니다. TV가 켜진 상태에서만 BLE 제어가 가능합니다.
- **Write 방식**: Write Without Response를 사용합니다. BLE Controller 설정에서 Write With Response를 OFF로 두세요.

---

## BLE GATT 구조 (상세)

이 디바이스의 전체 GATT 구조입니다. 프로토콜을 더 깊게 이해하고 싶은 분들을 위한 참고 자료입니다.

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

---

## 프로토콜 상세

### 패킷 포맷

```
0A A5 <SEQ> <CMD> [<PARAMS...>]
```

- **`0A A5`**: 프로토콜 헤더 (고정)
- **`SEQ`**: 시퀀스 ID (매 커맨드마다 1씩 증가, 0x00~0xFF 순환)
- **`CMD`**: 커맨드 타입
- **`PARAMS`**: 커맨드별 파라미터 (가변 길이)

> 이 디바이스는 시퀀스 ID를 검증하지 않습니다. 고정값을 사용해도 동작합니다.

### 확인된 커맨드

#### 전원 ON/OFF (CMD = 0x01)

```
0A A5 <SEQ> 01 <STATE>
```

| STATE | 동작 |
|-------|------|
| `0x01` | ON (켜기) |
| `0x00` | OFF (끄기) |

#### 상태 조회 (CMD = 0xFF)

앱이 접속 직후 연속으로 보내는 조회 요청:

```
0A A5 <SEQ> FF
```

| 전송 데이터 | 의미 |
|------------|------|
| `0A A5 0E FF` | 상태 조회 (타입 0E) |
| `0A A5 0F FF` | 상태 조회 (타입 0F) |
| `0A A5 10 FF` | 상태 조회 (타입 10) |
| `0A A5 11 FF` | 상태 조회 (타입 11) |

### Notify 응답

| 응답 | 의미 |
|------|------|
| `0A A5 00 0A 00 00 00 00 00 00 00 00` | OFF 상태 |
| `0A A5 54 05 00 00 64 00 01 00 1F` | ON 상태 (밝기=0x64=100% 등 포함 추정) |

디바이스는 커맨드 에코도 보냅니다 (예: Write `0AA5120100` → Notify `0AA5120100` 에코).

### 전원 제어 캡처 기록

HCI 로그에서 캡처한 4회 전원 토글 기록:

| 시간 | 전송 데이터 | 동작 | Notify 응답 |
|------|-----------|------|-------------|
| 08:34:42.007 | `0A A5 12 01 00` | OFF | `0AA5000A0000000000000000` |
| 08:34:43.249 | `0A A5 13 01 01` | ON | `0AA554050000640001001F` |
| 08:34:44.068 | `0A A5 14 01 00` | OFF | `0AA5000A0000000000000000` |
| 08:34:44.599 | `0A A5 15 01 01` | ON | `0AA554050000640001001F` |

---

## 디바이스 메타데이터

앱 로그에서 확인된 디바이스 프로퍼티:

| Property ID | 이름 | 타입 | 값 범위 |
|-------------|------|------|---------|
| `brightness` | 밝기 | int (percent) | 1~100 (step 25) |
| `color` | 색상 | enum | 다수 프리셋 색상 |
| `powerstate` | 전원 | boolean | 0=OFF, 1=ON |

---

## 분석 소스

- Android 버그 리포트 덤프 (2026-04-04)
  - `FS/data/log/bt/btsnoop_hci.log`: HCI 패킷 캡처
  - `dumpstate.txt`: 앱 logcat (cn.com.uascent BleWriteAop/LoggerAop)
- 교차 검증: HCI 패킷과 앱 로그의 타임스탬프 및 데이터 일치 확인 완료
