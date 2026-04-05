# Write 방식 (With/Without Response)

BLE Controller 설정 시 **Write With Response** 옵션을 선택할 수 있습니다. 이 문서는 두 방식의 차이를 설명합니다.

---

## Write Without Response (기본값)

디바이스에 데이터를 보내고 **응답을 기다리지 않습니다**.

- BLE 프로토콜에서 ATT opcode `0x52` (Write Command)에 해당
- 더 빠르고 가벼움
- 대부분의 저가 BLE 디바이스가 이 방식을 사용
- 데이터가 도착했는지 확인할 수 없음 (BLE 링크 레이어에서 기본적인 전송 보장은 있음)

## Write With Response

디바이스에 데이터를 보내고 **디바이스의 확인 응답을 기다립니다**.

- BLE 프로토콜에서 ATT opcode `0x12` (Write Request)에 해당
- 디바이스가 데이터를 수신했음을 보장
- 약간 더 느림 (응답 대기 시간 추가)
- 디바이스가 Write Request를 요구하는 경우 이 옵션을 켜야 함

---

## 어떤 걸 선택해야 하나요?

**기본값(OFF, Write Without Response)으로 먼저 시도하세요.** 대부분의 디바이스에서 잘 동작합니다.

Write Without Response로 명령이 동작하지 않는 경우에만 Write With Response를 켜보세요. 디바이스의 Characteristic 속성에서 어떤 Write 방식을 지원하는지 확인할 수 있습니다:

- `Write Without Response` 속성만 있는 경우 → OFF (기본값)
- `Write` 속성만 있는 경우 → ON 필수
- 둘 다 있는 경우 → OFF로 시도, 안 되면 ON

> HCI 로그를 분석할 때 ATT opcode가 `0x52`이면 Write Without Response, `0x12`이면 Write With Response입니다.
