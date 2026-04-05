# BLE GATT 기초

BLE Controller를 설정하려면 GATT 구조를 이해해야 합니다. 이 문서는 설정에 필요한 최소한의 개념만 설명합니다.

---

## BLE란?

**Bluetooth Low Energy**의 약자로, 저전력 블루투스 통신 규격입니다. 기존 Bluetooth Classic과 달리 적은 전력으로 간헐적인 데이터 전송에 최적화되어 있습니다. IoT 디바이스, 센서, 웨어러블 등에서 주로 사용됩니다.

---

## GATT란?

**Generic Attribute Profile**의 약자로, BLE 디바이스가 데이터를 주고받는 방식을 정의하는 프로토콜입니다. BLE 디바이스에 연결한 뒤 실제로 데이터를 읽고 쓰는 모든 동작은 GATT를 통해 이루어집니다.

GATT는 계층 구조로 되어 있습니다:

```
디바이스
└── Service (서비스)
    └── Characteristic (캐릭터리스틱)
        └── 실제 데이터 (Value)
```

---

## Service (서비스)

서비스는 관련된 기능을 묶어놓은 그룹입니다. 하나의 디바이스에 여러 서비스가 있을 수 있습니다.

예시:
- `0x1800` — Generic Access (디바이스 이름 등 기본 정보)
- `0xFFB0` — 제조사가 정의한 커스텀 서비스 (제어 명령용)

BLE Controller 설정 시 입력하는 **Service UUID**가 바로 이것입니다.

---

## Characteristic (캐릭터리스틱)

서비스 안에 있는 개별 데이터 채널입니다. 각 Characteristic은 고유한 UUID를 가지며, 읽기/쓰기/알림 등의 속성(Properties)을 가집니다.

| 속성 | 설명 |
|------|------|
| **Read** | 값을 읽을 수 있음 |
| **Write** | 값을 쓸 수 있음 (응답 있음) |
| **Write Without Response** | 값을 쓸 수 있음 (응답 없음, 더 빠름) |
| **Notify** | 디바이스가 값이 변경될 때 알려줌 |

BLE Controller에서는:
- **Write Characteristic** — 디바이스에 명령을 보내는 채널
- **Notify Characteristic** — 디바이스의 상태 변화를 수신하는 채널 (선택)

→ Write 방식의 차이에 대해서는 [Write 방식 (With/Without Response)](./write-modes.md)를 참고하세요.
→ Notify에 대해서는 [Notify와 상태 확인](./notify.md)를 참고하세요.

---

## UUID란?

**Universally Unique Identifier**의 약자로, 각 Service와 Characteristic을 식별하는 고유 ID입니다.

두 가지 형식이 있습니다:

| 형식 | 예시 | 설명 |
|------|------|------|
| **16비트 축약형** | `0xFFB0` | Bluetooth SIG 표준 또는 커스텀 서비스에서 사용하는 짧은 형식 |
| **128비트 전체형** | `0000ffb0-0000-1000-8000-00805f9b34fb` | 16비트 UUID를 확장한 전체 형식 |

BLE Controller 설정 시에는 **128비트 전체형**을 입력합니다. 16비트 UUID `0xFFB0`의 전체형은 `0000ffb0-0000-1000-8000-00805f9b34fb`입니다.

> 같은 모델의 디바이스는 동일한 Service/Characteristic UUID를 가집니다. UUID는 기기 고유 식별자가 아니라 프로토콜 스펙의 일부입니다.
