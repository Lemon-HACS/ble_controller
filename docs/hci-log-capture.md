# BLE 프로토콜 파악 방법 (HCI 로그 캡처)

BLE Controller를 사용하려면 디바이스의 Service UUID, Characteristic UUID, 전송할 hex 데이터를 알아야 합니다. 이 문서는 Android 기기에서 BLE 통신을 캡처하여 프로토콜을 파악하는 방법을 설명합니다.

---

## 준비물

- **Android 기기** (제조사 앱이 설치된 것)
- **제어 대상 BLE 디바이스**
- **PC** (로그 분석용)

---

## 1단계: HCI 스눕 로그 활성화

1. Android 설정 → **개발자 옵션** 진입
   - 개발자 옵션이 없으면: 설정 → 휴대전화 정보 → 빌드 번호 7회 탭
2. **블루투스 HCI 스눕 로그** 활성화
3. Bluetooth를 껐다가 다시 켜기 (로그 캡처 시작)

---

## 2단계: BLE 통신 캡처

1. **제조사 앱**으로 디바이스에 연결
2. 파악하고 싶은 동작을 수행 (전원 ON/OFF, 모드 변경 등)
3. **각 동작 사이에 2-3초 간격**을 두면 나중에 분석할 때 구분이 쉬움
4. 같은 동작을 2-3회 반복하면 패턴을 확인하기 좋음

---

## 3단계: 로그 추출

### 버그 리포트 방식 (권장)

1. Android 개발자 옵션 → **버그 리포트 가져오기**
2. 생성된 ZIP 파일을 PC로 전송
3. ZIP 내부의 `FS/data/log/bt/btsnoop_hci.log` 파일 추출

### adb 방식

```bash
adb pull /data/log/bt/btsnoop_hci.log
```

> 기기에 따라 경로가 다를 수 있습니다. 버그 리포트 방식이 더 확실합니다.

---

## 4단계: 로그 분석

### 방법 A: AI에게 맡기기 (추천)

추출한 `btsnoop_hci.log` 파일을 AI(ChatGPT, Claude 등)에게 전달하고 다음과 같이 요청하세요:

> "이 BLE HCI 로그에서 GATT Write 커맨드를 분석해줘. 어떤 Service/Characteristic UUID에 어떤 데이터를 쓰는지 정리해줘."

AI가 다음을 정리해줍니다:
- Service UUID, Characteristic UUID
- 각 동작별 전송 데이터 (hex)
- Write 방식 (With/Without Response)
- Notify 응답 패턴 (있는 경우)

### 방법 B: Wireshark로 직접 분석

1. [Wireshark](https://www.wireshark.org/) 설치
2. `btsnoop_hci.log` 파일 열기
3. 필터 적용: `btatt.opcode == 0x52 || btatt.opcode == 0x12`
   - `0x52` = Write Without Response
   - `0x12` = Write With Response
4. ATT Write 패킷에서 다음을 확인:
   - **Handle** → 어떤 Characteristic에 쓰는지
   - **Value** → 전송 데이터 (hex)
5. Handle과 Characteristic UUID의 매핑은 GATT discovery 패킷에서 확인 가능

---

## 분석 팁

- **동일 동작을 여러 번 수행**했다면, 반복되는 패턴이 해당 동작의 커맨드입니다
- 매번 변하는 바이트가 있다면 시퀀스 번호일 가능성이 높습니다 (보통 무시해도 동작함)
- 연결 직후 앱이 보내는 초기화 시퀀스는 보통 무시해도 됩니다
- **Service UUID와 Characteristic UUID는 같은 모델이면 동일**하므로, 다른 사용자의 분석 결과를 참고할 수 있습니다
