import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
PREFIX = os.getenv("PREFIX", "!")
GUILD_ID = os.getenv("GUILD_ID")  # 선택: 특정 서버에만 즉시 슬래시 동기화하고 싶을 때 사용
DB_PATH = os.getenv("DB_PATH", "bot.db")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

# 임베드 공통 색상
COLOR_MAIN = 0x2F3136
COLOR_OK = 0x57F287
COLOR_WARN = 0xFEE75C
COLOR_ERR = 0xED4245

# 경험치 관련
XP_MIN = 5
XP_MAX = 15
XP_COOLDOWN_SECONDS = 60
LEVEL_UP_BASE = 100  # 레벨업 필요 경험치 = LEVEL_UP_BASE * level

# 음악 관련
MAX_QUEUE_DISPLAY = 10
DEFAULT_VOLUME = 0.5
