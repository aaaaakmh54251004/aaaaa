import random
import discord
from discord import app_commands
from discord.ext import commands

from config import XP_MIN, XP_MAX, XP_COOLDOWN_SECONDS, LEVEL_UP_BASE
from database import execute
from utils import make_embed, ok_embed, now_ts


def xp_for_level(level: int) -> int:
    return LEVEL_UP_BASE * (level + 1)


class Level(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_user(self, guild_id: int, user_id: int):
        row = execute(
            "SELECT * FROM levels WHERE guild_id=? AND user_id=?", (guild_id, user_id), fetch="one"
        )
        if not row:
            execute(
                "INSERT INTO levels (guild_id, user_id, xp, level, coins, last_xp_time) VALUES (?,?,0,0,0,0)",
                (guild_id, user_id),
            )
            row = execute(
                "SELECT * FROM levels WHERE guild_id=? AND user_id=?", (guild_id, user_id), fetch="one"
            )
        return row

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        row = self._get_user(message.guild.id, message.author.id)
        ts = now_ts()
        if ts - row["last_xp_time"] < XP_COOLDOWN_SECONDS:
            return
        gained = random.randint(XP_MIN, XP_MAX)
        new_xp = row["xp"] + gained
        level = row["level"]
        need = xp_for_level(level)
        leveled_up = False
        while new_xp >= need:
            new_xp -= need
            level += 1
            need = xp_for_level(level)
            leveled_up = True
        execute(
            "UPDATE levels SET xp=?, level=?, coins=coins+?, last_xp_time=? WHERE guild_id=? AND user_id=?",
            (new_xp, level, gained, ts, message.guild.id, message.author.id),
        )
        if leveled_up:
            try:
                await message.channel.send(
                    embed=ok_embed(f"{message.author.mention}님이 레벨 **{level}**(으)로 레벨업했습니다! 🎉", title="레벨업")
                )
            except discord.Forbidden:
                pass

    @commands.hybrid_command(name="레벨", description="자신 또는 다른 사용자의 레벨을 확인합니다.")
    @app_commands.describe(대상="확인할 사용자 (비우면 본인)")
    async def level_cmd(self, ctx: commands.Context, 대상: discord.Member = None):
        member = 대상 or ctx.author
        row = self._get_user(ctx.guild.id, member.id)
        need = xp_for_level(row["level"])
        embed = make_embed(
            title=f"⭐ {member.display_name}님의 레벨 정보",
            fields=[
                ("레벨", str(row["level"]), True),
                ("경험치", f"{row['xp']} / {need}", True),
                ("코인", str(row["coins"]), True),
            ],
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="랭킹", description="서버 경험치 랭킹을 확인합니다.")
    async def rank_cmd(self, ctx: commands.Context):
        rows = execute(
            "SELECT * FROM levels WHERE guild_id=? ORDER BY level DESC, xp DESC LIMIT 10",
            (ctx.guild.id,),
            fetch="all",
        )
        if not rows:
            await ctx.reply(embed=make_embed(title="🏆 랭킹", description="아직 데이터가 없습니다."))
            return
        lines = []
        for i, row in enumerate(rows, 1):
            member = ctx.guild.get_member(row["user_id"])
            name = member.display_name if member else f"알수없음({row['user_id']})"
            lines.append(f"`{i}.` {name} - Lv.{row['level']} ({row['xp']} xp)")
        await ctx.reply(embed=make_embed(title="🏆 경험치 랭킹", description="\n".join(lines)))


async def setup(bot: commands.Bot):
    await bot.add_cog(Level(bot))
