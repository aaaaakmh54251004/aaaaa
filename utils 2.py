import discord
import time
from config import COLOR_MAIN, COLOR_OK, COLOR_WARN, COLOR_ERR


def make_embed(title=None, description=None, color=COLOR_MAIN, fields=None, footer=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed


def ok_embed(description, title="완료"):
    return make_embed(title=f"✅ {title}", description=description, color=COLOR_OK)


def warn_embed(description, title="주의"):
    return make_embed(title=f"⚠ {title}", description=description, color=COLOR_WARN)


def err_embed(description, title="오류"):
    return make_embed(title=f"❌ {title}", description=description, color=COLOR_ERR)


def format_duration(seconds: int) -> str:
    if seconds is None:
        return "알 수 없음"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def now_ts() -> int:
    return int(time.time())


async def is_admin_or_manager(ctx_or_interaction, guild_id: int, user: discord.Member) -> bool:
    """서버 관리자 권한이 있거나 봇 자체 관리자 목록에 등록된 사용자인지 확인"""
    from database import execute

    if user.guild_permissions.administrator:
        return True
    row = execute(
        "SELECT 1 FROM admins WHERE guild_id=? AND user_id=?",
        (guild_id, user.id),
        fetch="one",
    )
    return row is not None
