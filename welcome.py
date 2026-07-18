import discord
from discord import app_commands
from discord.ext import commands

from database import execute
from utils import make_embed, ok_embed

DEFAULT_WELCOME = "안녕하세요 {mention}님!\n{server} 서버에 오신 것을 환영합니다!\n현재 서버 인원: {membercount}명"


def render_welcome(template: str, member: discord.Member) -> str:
    return (
        template.replace("{user}", member.name)
        .replace("{mention}", member.mention)
        .replace("{server}", member.guild.name)
        .replace("{membercount}", str(member.guild.member_count))
    )


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        row = execute(
            "SELECT channel_id, message FROM welcome_config WHERE guild_id=?", (member.guild.id,), fetch="one"
        )
        if not row:
            return
        channel = member.guild.get_channel(row["channel_id"])
        if not channel:
            return
        template = row["message"] or DEFAULT_WELCOME
        text = render_welcome(template, member)
        embed = make_embed(title="👋 환영합니다!", description=text)
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.hybrid_command(name="환영", description="환영 메시지를 설정합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        채널="환영 메시지를 보낼 채널",
        메시지="환영 메시지 (변수: {user} {mention} {server} {membercount})",
    )
    async def set_welcome(self, ctx: commands.Context, 채널: discord.TextChannel, *, 메시지: str = None):
        template = 메시지 or DEFAULT_WELCOME
        execute(
            "INSERT INTO welcome_config (guild_id, channel_id, message) VALUES (?, ?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id, message=excluded.message",
            (ctx.guild.id, 채널.id, template),
        )
        preview = render_welcome(template, ctx.author)
        await ctx.reply(embed=ok_embed(f"환영 메시지를 {채널.mention}(으)로 설정했습니다.\n\n**미리보기:**\n{preview}"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
