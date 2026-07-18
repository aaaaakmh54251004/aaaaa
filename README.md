# 🎵 Discord 통합 음악봇 + 관리봇

Python 3.12 / discord.py 2.x 기반, Prefix(`!`)와 Slash(`/`) 명령어를 동일하게 지원하는 통합 디스코드 봇입니다.

## 📁 프로젝트 구조

```
bot.py          # 메인 진입점, 코그 로드, 슬래시 동기화, 도움말
music.py        # 음악 재생/대기열/패널 (yt-dlp)
views.py        # 버튼 View (음악/상점/티켓 패널)
ticket.py        # 티켓 시스템
shop.py         # 경험치 상점
level.py        # 경험치/레벨/랭킹
admin.py        # 봇 관리자, 제재, 서버관리
welcome.py      # 환영 메시지
database.py     # SQLite 초기화/헬퍼
config.py       # 환경변수/설정값
utils.py        # 공용 임베드/유틸 함수
requirements.txt
.env.example
```

## 🚀 설치 방법

### 1. 필수 프로그램
- Python 3.12 이상
- **FFmpeg** (음악 재생 필수)
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: [ffmpeg.org](https://ffmpeg.org/download.html)에서 다운로드 후 PATH 등록
  - Railway/Render: `nixpacks.toml` 또는 `apt.txt`에 `ffmpeg` 추가 (아래 배포 섹션 참고)

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정
`.env.example`을 복사해 `.env` 파일을 만들고 값을 채웁니다.
```bash
cp .env.example .env
```
- `DISCORD_TOKEN`: [Discord Developer Portal](https://discord.com/developers/applications) > Bot > Token
- Bot 권한: **Message Content Intent**, **Server Members Intent** 를 반드시 켜야 합니다 (Bot 탭 > Privileged Gateway Intents).
- `SPOTIFY_CLIENT_ID`/`SECRET`: Spotify 링크 지원을 원할 때만 입력 (없어도 유튜브/검색/사운드클라우드는 정상 동작)

### 4. 실행
```bash
python bot.py
```

## 🎵 음악 기능 안내
- 노래 제목, 유튜브 링크/Shorts/재생목록, 사운드클라우드 링크, 스포티파이 링크 입력 지원
- 스포티파이는 **정식 스트리밍이 아닌** 트랙명 추출 후 유튜브 자동 검색으로 대체 재생됩니다 (Spotify 정책상 직접 스트리밍은 불가능).
- `/노래채널설정`으로 지정한 채널에서는 명령어 없이 텍스트만 입력해도 자동 재생됩니다.
- `/음악패널`로 버튼 컨트롤 패널을 띄울 수 있습니다.
- 혼자 남으면 15초 후 자동 퇴장, 대기열이 없으면 자동 퇴장합니다.

## 📖 명령어 확인
`!도움말` 또는 `/도움말` 입력 후, 카테고리명(음악/상점/경험치/관리자/티켓/서버관리)을 붙이면 세부 사용법을 볼 수 있습니다.
예: `!도움말 음악`

## ☁ 배포 가이드

### Railway / Render (Docker 없이 Nixpacks 사용 시)
루트에 아래 파일을 추가하면 FFmpeg가 자동 설치됩니다.

`nixpacks.toml`:
```toml
[phases.setup]
nixPkgs = ["ffmpeg", "python312"]
```

Start Command: `python bot.py`
환경변수는 Railway/Render 대시보드의 Environment Variables에 `.env`와 동일하게 등록하세요.

### Replit
1. `pyproject.toml` 또는 `replit.nix`에 ffmpeg 추가:
```nix
{ pkgs }: {
  deps = [ pkgs.ffmpeg ];
}
```
2. Secrets 탭에 `.env` 값들을 등록
3. Run 버튼 또는 `python bot.py` 실행
4. 24시간 구동을 위해 Replit의 Always On 또는 UptimeRobot 같은 핑 서비스 사용 권장

## ⚠ 알아두어야 할 제약사항
- YouTube/SoundCloud는 yt-dlp를 통해 동작하며, 각 플랫폼의 정책 변경에 따라 추출이 실패할 수 있습니다. 이 경우 `pip install -U yt-dlp`로 최신 버전을 유지해주세요.
- Spotify는 메타데이터(제목/아티스트)만 가져오며 실제 음원은 재생하지 않습니다.
- 봇 토큰, 클라이언트 시크릿 등은 절대 깃허브 등에 공개 저장소로 올리지 마세요 (`.env`는 `.gitignore`에 포함해야 합니다).
- 대규모 서버에서는 SQLite 대신 PostgreSQL 등으로 교체하는 것을 권장합니다.

## 🛠 문제 해결
- **슬래시 명령어가 안 보여요**: 전역 동기화는 최대 1시간 걸릴 수 있습니다. 빠른 테스트를 원하면 `.env`의 `GUILD_ID`에 테스트 서버 ID를 입력하세요 (즉시 반영).
- **음악이 재생 안 돼요**: FFmpeg 설치 여부와 PATH 등록을 확인하세요. `ffmpeg -version`으로 확인 가능합니다.
- **한글 슬래시 명령어가 안 떠요**: Discord 앱을 최신 버전으로 업데이트하고, 봇의 `applications.commands` 스코프가 초대 링크에 포함되어 있는지 확인하세요.
