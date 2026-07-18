import datetime
import discord
from discord import app_commands
from discord.ext import commands

from database import execute
from utils import make_embed, ok_embed, err_embed, warn_embed, now_ts, is_admin_or_manager


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _log(self, guild: discord.Guild, embed: discord.Embed):
        row = execute("SELECT channel_id FROM log_channels WHERE guild_id=?", (guild.id,), fetch="one")
        if row:
            channel = guild.get_channel(row["channel_id"])
            if channel:
                try:
                    await channel.send(embed=embed)
                except discord.Forbidden:
                    pass

    # ---------- 봇 관리자 목록 ----------

    @commands.hybrid_command(name="관리자추가", description="봇 관리자 권한을 부여합니다.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(대상="관리자로 등록할 사용자")
    async def add_admin(self, ctx: commands.Context, 대상: discord.Member):
        execute(
            "INSERT OR IGNORE INTO admins (guild_id, user_id) VALUES (?, ?)", (ctx.guild.id, 대상.id)
        )
        await ctx.reply(embed=ok_embed(f"{대상.mention}님을 봇 관리자로 추가했습니다."))

    @commands.hybrid_command(name="관리자제거", description="봇 관리자 권한을 제거합니다.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(대상="제거할 사용자")
    async def remove_admin(self, ctx: commands.Context, 대상: discord.Member):
        execute("DELETE FROM admins WHERE guild_id=? AND user_id=?", (ctx.guild.id, 대상.id))
        await ctx.reply(embed=ok_embed(f"{대상.mention}님을 봇 관리자에서 제거했습니다."))

    # ---------- 서버 관리 ----------

    @commands.hybrid_command(name="핑", description="봇의 응답 속도를 확인합니다.")
    async def ping_cmd(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        await ctx.reply(embed=make_embed(title="🏓 퐁!", description=f"지연시간: {latency}ms"))

    @commands.hybrid_command(name="유저정보", description="사용자 정보를 확인합니다.")
    @app_commands.describe(대상="확인할 사용자 (비우면 본인)")
    async def user_info(self, ctx: commands.Context, 대상: discord.Member = None):
        member = 대상 or ctx.author
        embed = make_embed(
            title=f"👤 {member.display_name}님의 정보",
            fields=[
                ("아이디", str(member.id), True),
                ("가입일", member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "알 수 없음", True),
                ("계정 생성일", member.created_at.strftime("%Y-%m-%d"), True),
                ("역할 수", str(len(member.roles) - 1), True),
            ],
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="서버정보", description="서버 정보를 확인합니다.")
    async def server_info(self, ctx: commands.Context):
        guild = ctx.guild
        embed = make_embed(
            title=f"🏠 {guild.name}",
            fields=[
                ("서버장", str(guild.owner), True),
                ("멤버 수", str(guild.member_count), True),
                ("생성일", guild.created_at.strftime("%Y-%m-%d"), True),
                ("채널 수", str(len(guild.channels)), True),
                ("역할 수", str(len(guild.roles)), True),
                ("부스트 레벨", str(guild.premium_tier), True),
            ],
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        await ctx.reply(embed=embed)

    @commands.hybrid_command(name="공지", description="공지사항을 전송합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(내용="공지 내용", 채널="전송할 채널 (비우면 현재 채널)")
    async def announce(self, ctx: commands.Context, 내용: str, 채널: discord.TextChannel = None):
        target = 채널 or ctx.channel
        embed = make_embed(title="📢 공지사항", description=내용)
        await target.send(embed=embed)
        if target.id != ctx.channel.id:
            await ctx.reply(embed=ok_embed(f"{target.mention}에 공지를 전송했습니다."))
        else:
            await ctx.reply(embed=ok_embed("공지를 전송했습니다."))

    @commands.hybrid_command(name="슬로우모드", description="채널 슬로우모드를 설정합니다.")
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(초="슬로우모드 대기시간(초), 0이면 해제")
    async def slowmode(self, ctx: commands.Context, 초: int):
        await ctx.channel.edit(slowmode_delay=초)
        await ctx.reply(embed=ok_embed(f"슬로우모드를 {초}초로 설정했습니다."))

    @commands.hybrid_command(name="잠금", description="현재 채널을 잠급니다.")
    @commands.has_permissions(manage_channels=True)
    async def lock_channel(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply(embed=ok_embed("채널을 잠갔습니다. 🔒"))

    @commands.hybrid_command(name="잠금해제", description="현재 채널의 잠금을 해제합니다.")
    @commands.has_permissions(manage_channels=True)
    async def unlock_channel(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply(embed=ok_embed("채널 잠금을 해제했습니다. 🔓"))

    @commands.hybrid_command(name="로그채널", description="관리 로그를 남길 채널을 설정합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(채널="로그를 남길 채널")
    async def set_log_channel(self, ctx: commands.Context, 채널: discord.TextChannel):
        execute(
            "INSERT INTO log_channels (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
            (ctx.guild.id, 채널.id),
        )
        await ctx.reply(embed=ok_embed(f"로그 채널을 {채널.mention}(으)로 설정했습니다."))

    # ---------- 제재 ----------

    @commands.hybrid_command(name="경고", description="사용자에게 경고를 부여합니다.")
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(대상="경고할 사용자", 사유="경고 사유")
    async def warn_user(self, ctx: commands.Context, 대상: discord.Member, *, 사유: str = "사유 없음"):
        execute(
            "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, created_at) VALUES (?,?,?,?,?)",
            (ctx.guild.id, 대상.id, ctx.author.id, 사유, now_ts()),
        )
        await ctx.reply(embed=ok_embed(f"{대상.mention}님에게 경고를 부여했습니다.\n사유: {사유}"))
        await self._log(ctx.guild, make_embed(title="⚠ 경고 부여", description=f"{대상.mention} - {사유} (by {ctx.author.mention})"))

    @commands.hybrid_command(name="경고확인", description="사용자의 경고 내역을 확인합니다.")
    @app_commands.describe(대상="확인할 사용자")
    async def check_warnings(self, ctx: commands.Context, 대상: discord.Member):
        rows = execute(
            "SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY created_at DESC",
            (ctx.guild.id, 대상.id),
            fetch="all",
        )
        if not rows:
            await ctx.reply(embed=warn_embed(f"{대상.mention}님은 경고 내역이 없습니다."))
            return
        lines = [f"`{i}.` {r['reason']} ({datetime.datetime.fromtimestamp(r['created_at']).strftime('%Y-%m-%d')})"
                 for i, r in enumerate(rows, 1)]
        await ctx.reply(embed=make_embed(title=f"⚠ {대상.display_name}님의 경고 내역", description="\n".join(lines)))

    @commands.hybrid_command(name="경고초기화", description="사용자의 경고 내역을 초기화합니다.")
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(대상="초기화할 사용자")
    async def reset_warnings(self, ctx: commands.Context, 대상: discord.Member):
        execute("DELETE FROM warnings WHERE guild_id=? AND user_id=?", (ctx.guild.id, 대상.id))
        await ctx.reply(embed=ok_embed(f"{대상.mention}님의 경고 내역을 초기화했습니다."))

    @commands.hybrid_command(name="킥", description="사용자를 서버에서 추방합니다.")
    @commands.has_permissions(kick_members=True)
    @app_commands.describe(대상="추방할 사용자", 사유="추방 사유")
    async def kick_user(self, ctx: commands.Context, 대상: discord.Member, *, 사유: str = "사유 없음"):
        await 대상.kick(reason=사유)
        await ctx.reply(embed=ok_embed(f"{대상}님을 추방했습니다.\n사유: {사유}"))
        await self._log(ctx.guild, make_embed(title="👢 추방", description=f"{대상} - {사유} (by {ctx.author.mention})"))

    @commands.hybrid_command(name="밴", description="사용자를 서버에서 차단합니다.")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(대상="차단할 사용자", 사유="차단 사유")
    async def ban_user(self, ctx: commands.Context, 대상: discord.Member, *, 사유: str = "사유 없음"):
        await 대상.ban(reason=사유)
        await ctx.reply(embed=ok_embed(f"{대상}님을 차단했습니다.\n사유: {사유}"))
        await self._log(ctx.guild, make_embed(title="🔨 차단", description=f"{대상} - {사유} (by {ctx.author.mention})"))

    @commands.hybrid_command(name="언밴", description="차단된 사용자를 해제합니다.")
    @commands.has_permissions(ban_members=True)
    @app_commands.describe(유저아이디="차단 해제할 사용자 ID")
    async def unban_user(self, ctx: commands.Context, 유저아이디: str):
        try:
            user = await self.bot.fetch_user(int(유저아이디))
            await ctx.guild.unban(user)
            await ctx.reply(embed=ok_embed(f"{user}님의 차단을 해제했습니다."))
        except (ValueError, discord.NotFound):
            await ctx.reply(embed=err_embed("해당 사용자를 찾을 수 없습니다."))

    @commands.hybrid_command(name="타임아웃", description="사용자를 일정 시간 동안 타임아웃합니다.")
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(대상="타임아웃할 사용자", 분="타임아웃 시간(분)", 사유="사유")
    async def timeout_user(self, ctx: commands.Context, 대상: discord.Member, 분: int, *, 사유: str = "사유 없음"):
        duration = datetime.timedelta(minutes=분)
        await 대상.timeout(duration, reason=사유)
        await ctx.reply(embed=ok_embed(f"{대상.mention}님을 {분}분 동안 타임아웃했습니다.\n사유: {사유}"))
        await self._log(ctx.guild, make_embed(title="⏱ 타임아웃", description=f"{대상.mention} - {분}분 - {사유}"))

    @commands.hybrid_command(name="타임아웃해제", description="타임아웃을 해제합니다.")
    @commands.has_permissions(moderate_members=True)
    @app_commands.describe(대상="타임아웃 해제할 사용자")
    async def remove_timeout(self, ctx: commands.Context, 대상: discord.Member):
        await 대상.timeout(None)
        await ctx.reply(embed=ok_embed(f"{대상.mention}님의 타임아웃을 해제했습니다."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
