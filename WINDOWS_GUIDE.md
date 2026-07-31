# Windows에서 실행하기 (초보자용 가이드)

이 문서는 `onsite_main.py` (현장형 숏폼 생성기) 를 윈도우 PC에서 처음부터 끝까지
실행하는 방법을 설명합니다. 명령어는 그대로 복사해서 붙여넣으면 됩니다.

---

## 1. 프로그램 실행 전에 설치해야 할 것

### 1-1. Python 설치

1. https://www.python.org/downloads/ 접속 → "Download Python 3.x.x" 클릭
2. 설치 시작 화면 맨 아래 **"Add python.exe to PATH"에 반드시 체크** (이걸 안 하면 나중에 `python` 명령이 안 먹습니다)
3. "Install Now" 클릭
4. 설치가 끝나면 확인:

```powershell
python --version
```

`Python 3.x.x`가 출력되면 성공입니다. `python`이 안 먹으면 `py --version`으로 시도해보세요
(이 경우 아래 모든 `python` 명령을 `py`로 바꿔서 실행하면 됩니다).

### 1-2. ffmpeg 설치 (영상 합성에 필수)

1. https://www.gyan.dev/ffmpeg/builds/ 접속
2. **"release builds"** 항목의 `ffmpeg-release-essentials.zip` 다운로드
3. 압축을 풀어서 원하는 위치에 둡니다 (예: `C:\ffmpeg`)
4. 환경변수 PATH에 `bin` 폴더 추가:
   - 시작 메뉴에서 "환경 변수" 검색 → "시스템 환경 변수 편집" 클릭
   - "환경 변수" 버튼 → 아래쪽 "시스템 변수"에서 `Path` 선택 → "편집"
   - "새로 만들기" → `C:\ffmpeg\bin` 입력 (압축 푼 경로 + `\bin`) → 확인 → 확인 → 확인
5. **새 PowerShell 창을 열어서** 확인 (기존 창은 PATH 변경이 반영 안 됨):

```powershell
ffmpeg -version
```

버전 정보가 나오면 성공입니다.

### 1-3. (선택) Git for Windows

레포를 zip으로 받을 거면 필요 없습니다. git으로 관리하고 싶으면
https://git-scm.com/download/win 에서 설치하세요.

---

## 2. 터미널을 어디서 여는지

**방법 A (가장 쉬움) — 프로젝트 폴더에서 바로 열기**

1. 파일 탐색기(Explorer)에서 `giftclean-content-engine` 폴더로 이동
2. 폴더 안의 빈 공간에서 **Shift + 마우스 우클릭**
3. Windows 10: "여기에 PowerShell 창 열기" 클릭
   Windows 11: "터미널에서 열기" 클릭

**방법 B — 시작 메뉴에서 열기**

1. 시작 메뉴에서 "PowerShell" 검색 → "Windows PowerShell" 클릭
2. 아래 3번 항목의 `cd` 명령으로 프로젝트 폴더까지 직접 이동

---

## 3. 프로젝트 폴더로 이동하는 명령어

방법 B로 열었거나, 폴더 위치가 다르면 아래처럼 이동합니다 (본인 경로에 맞게 수정):

```powershell
cd C:\Users\사용자이름\Downloads\giftclean-content-engine
```

방법 A로 열었다면 이미 그 폴더 안에 있으므로 이 단계는 건너뛰어도 됩니다.

이동한 뒤 필요한 패키지를 한 번만 설치합니다:

```powershell
pip install -r requirements.txt
```

---

## 4. 테스트용 프로젝트 생성 명령어

사진을 아직 준비하지 못했다면, 우선 명령어 구조만 확인하는 용도로 프로젝트 이름을 정합니다.
프로젝트 ID는 영문/숫자/하이픈만 쓰는 것을 권장합니다 (한글 X).

```powershell
python onsite_main.py init --project test-001 --photo "C:\Users\사용자이름\Pictures\before.jpg:before" --photo "C:\Users\사용자이름\Pictures\during.jpg:during" --photo "C:\Users\사용자이름\Pictures\after.jpg:after"
```

성공하면 아래처럼 출력됩니다:

```
✅ 프로젝트 'test-001' 생성 완료 — 사진 3장 등록됨
   [1] 작업 전(Before) 00_before.jpg  (원본: before.jpg)
   [2] 작업 중         01_during.jpg  (원본: during.jpg)
   [3] 작업 후(After)  02_after.jpg  (원본: after.jpg)

📝 다음 단계: projects\test-001\script.txt 파일을 열어 각 사진에 대한 실제 현장 대본을 작성하세요.
```

---

## 5. Before / 작업 중 / After 사진을 넣는 실제 명령어 예시

먼저 휴대폰 사진을 PC로 옮겨야 합니다 (카카오톡 "나에게 보내기", 구글 포토, USB 케이블 등 편한 방법 사용).
예를 들어 사진을 `C:\Users\사용자이름\Desktop\현장사진\` 폴더에 옮겼다고 하면:

```powershell
python onsite_main.py init --project site-0731 --photo "C:\Users\사용자이름\Desktop\현장사진\before1.jpg:before" --photo "C:\Users\사용자이름\Desktop\현장사진\work1.jpg:during" --photo "C:\Users\사용자이름\Desktop\현장사진\work2.jpg:during" --photo "C:\Users\사용자이름\Desktop\현장사진\after1.jpg:after"
```

- `--photo`는 사진마다 반복해서 씁니다.
- **경로:phase** 형식이며, phase는 `before` / `during` / `after` 셋 중 하나만 가능합니다.
- 경로에 공백이나 한글이 있으면 반드시 큰따옴표(`" "`)로 감싸세요 (위 예시처럼).
- 입력한 **순서 그대로** 영상 순서가 됩니다.

나중에 순서를 확인하거나 바꾸려면:

```powershell
python onsite_main.py list --project site-0731
python onsite_main.py reorder --project site-0731 --order 01_during.jpg 00_before.jpg 03_after.jpg 02_during.jpg
```

(`reorder`의 파일명은 `list` 명령으로 확인한 이름을 그대로 씁니다)

---

## 6. script.txt에 대본을 작성하는 예시

메모장으로 바로 엽니다:

```powershell
notepad projects\site-0731\script.txt
```

열어보면 이런 템플릿이 있습니다:

```
# [1] before - 00_before.jpg
(이 사진에 대한 실제 현장 설명을 여기에 작성하세요)

# [2] during - 01_during.jpg
(이 사진에 대한 실제 현장 설명을 여기에 작성하세요)
```

`#`으로 시작하는 줄은 건드리지 말고, 그 **아래 줄의 괄호 문장을 지우고** 실제 현장
내용으로 바꿔 씁니다. 예:

```
# [1] before - 00_before.jpg
이곳은 3년 이상 방치된 원룸 현장입니다. 바닥이 보이지 않을 정도로 쓰레기가 쌓여 있었습니다.

# [2] during - 01_during.jpg
방역과 분리수거를 동시에 진행하며 하나씩 정리했습니다.

# [3] during - 02_during.jpg
폐기물은 종류별로 나눠 지정된 방식으로 처리했습니다.

# [4] after - 03_after.jpg
작업 후 바닥과 벽면까지 깨끗하게 정리됐습니다. 기프트클린 쓰레기집청소팀이었습니다.
```

작성 후 **저장(Ctrl+S)** 하고 메모장을 닫습니다.

TTS 나레이션 + 자막을 만듭니다:

```powershell
python onsite_main.py audio --project site-0731
```

---

## 7. 개인정보 체크와 승인 화면을 여는 명령어

먼저 `list`로 파일명을 확인합니다:

```powershell
python onsite_main.py list --project site-0731
```

사진마다 개인정보(얼굴/주소/명패/우편물)가 없는지 확인 후 체크 (모두 `yes`인 경우 예시):

```powershell
python onsite_main.py check --project site-0731 --photo 00_before.jpg --face yes --address yes --nameplate yes --mail yes
python onsite_main.py check --project site-0731 --photo 01_during.jpg --face yes --address yes --nameplate yes --mail yes
python onsite_main.py check --project site-0731 --photo 02_during.jpg --face yes --address yes --nameplate yes --mail yes
python onsite_main.py check --project site-0731 --photo 03_after.jpg --face yes --address yes --nameplate yes --mail yes
```

**사진에 얼굴/주소/명패/우편물이 실제로 보인다면 `no`로 체크하고, 모자이크 처리 후 다시
사진을 등록하세요.** 승인 화면(로컬 웹페이지)을 엽니다:

```powershell
python review_server.py
```

터미널에 `http://127.0.0.1:5000 접속하세요`라고 뜨면, 웹 브라우저(엣지/크롬)를 열고 주소창에
`http://127.0.0.1:5000` 을 입력해서 접속합니다. 프로젝트를 클릭하면 대본/사진순서/개인정보
체크 상태가 보이고, 맨 아래 "승인자 이름"을 입력한 뒤 **"승인하고 렌더링 허용"** 버튼을 누릅니다.

화면을 닫지 않고 그대로 두면(터미널 창도 유지) 다음 8번 렌더링 단계를 진행할 수 있습니다.
렌더링만 할 거면 이 터미널은 그대로 두고 **새 PowerShell 창을 하나 더 열어서** 8번 명령을
실행하세요 (`Ctrl+C`로 끄면 웹 화면이 꺼집니다).

승인 화면 없이 터미널에서 바로 승인해도 됩니다:

```powershell
python onsite_main.py approve --project site-0731 --by "본인이름"
```

---

## 8. 최종 영상 생성 명령어

```powershell
python onsite_main.py render --project site-0731
```

승인이 안 되어 있으면 여기서 오류 메시지와 함께 멈추고 영상이 만들어지지 않습니다
(정상 동작입니다 — 승인 전 렌더링 차단).

로고/CTA/배경음악까지 넣고 싶다면 (모두 선택 사항):

```powershell
python onsite_main.py render --project site-0731 --logo "assets\logo.png" --bgm auto --cta-text "저장하고 필요할 때 찾아보세요" --cta-subtext "프로필 링크에서 무료 견적 확인"
```

(로고를 쓰려면 `assets\logo.png` 자리에 기프트클린 로고 PNG 파일을 미리 넣어두세요.
BGM을 쓰려면 `assets\bgm\` 폴더에 저작권 프리 mp3 파일을 넣어두고 `--bgm auto`를 쓰면 됩니다.)

---

## 9. 완성된 MP4를 찾는 위치

```
giftclean-content-engine\output\onsite_site-0731_20260731.mp4
```

(`site-0731`은 프로젝트 이름, 날짜는 렌더링한 날짜로 자동으로 붙습니다)

폴더를 파일 탐색기로 바로 열려면:

```powershell
explorer output
```

---

## 10. edge-tts가 내 PC에서도 실패할 경우 대체 TTS 방식

`audio` 명령을 실행했는데 아래처럼 에러가 나거나 멈추면:

```
❌ Cannot connect to host speech.platform.bing.com ...
```

**원인은 대부분 인터넷 연결/방화벽/회사망 차단**입니다 (edge-tts는 온라인 전용).
아래 순서로 확인하세요.

1. **인터넷 연결 확인** — 브라우저로 아무 사이트나 접속되는지 확인
2. **회사/공용 와이파이라면** 개인 핫스팟(휴대폰 테더링)으로 한 번 시도
3. 그래도 안 되면 프로그램이 **자동으로 오프라인 음성(pyttsx3, Windows 내장 SAPI5)으로 대체**합니다.
   추가 설치가 필요할 수 있습니다:

   ```powershell
   pip install pyttsx3
   ```

   Windows에 한국어 음성이 설치되어 있어야 자연스럽게 읽습니다. 없다면:
   - 시작 메뉴 → "설정" → "시간 및 언어" → "언어 및 지역"
   - "언어 추가" → 한국어 검색 → 설치 (음성 합성 포함 옵션 체크)
   - 설정 → "접근성" → "내레이터" 또는 "음성 인식" 메뉴에서 한국어 음성(예: Heami) 확인

4. 그래도 음질이 마음에 안 들거나 전혀 안 될 경우, **직접 녹음한 음성 파일**을 넣을 수 있습니다:
   - 휴대폰 녹음 앱이나 Windows "음성 녹음기"로 각 사진 대본을 읽어서 녹음 (mp3/m4a/wav 다 가능)
   - 아래 명령으로 해당 사진 자리에 넣기:

   ```powershell
   python onsite_main.py import-audio --project site-0731 --photo 00_before.jpg --audio "C:\Users\사용자이름\Desktop\내녹음.m4a"
   ```

   사진마다 반복하면 됩니다. 이후 7~8번 단계(체크/승인/렌더링)를 그대로 진행하면 됩니다.

---

## 자주 겪는 문제

| 증상 | 해결 |
|---|---|
| `python`이 안 먹음 | `py`로 대신 실행하거나, Python 재설치 시 "Add to PATH" 체크 확인 |
| `ffmpeg`가 안 먹음 | 새 PowerShell 창을 열었는지 확인 (PATH는 새 창부터 적용됨) |
| 한글 경로 사진이 안 잡힘 | 경로를 큰따옴표로 감쌌는지 확인 |
| `pip install`이 느리거나 실패 | 인터넷 연결 확인 후 재시도 |
| 승인했는데도 render가 차단됨 | `python onsite_main.py review --project 이름` 으로 어떤 항목이 남았는지 확인 |
