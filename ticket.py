import io
import discord
from discord import app_commands
from discord.ext import commands

from database import execute
from utils import make_embed, ok_embed, err_embed, now_ts
from views import TicketPanelView, TicketCloseView


class Ticket(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 봇 재시작 후에도 버튼이 동작하도록 영구 View 등록
        bot.add_view(TicketPanelView(self))
        bot.add_view(TicketCloseView(self))

    def _get_config(self, guild_id: int):
        return execute("SELECT * FROM ticket_config WHERE guild_id=?", (guild_id,), fetch="one")

    @commands.hybrid_command(name="티켓설정", description="티켓 시스템 카테고리/로그/관리자 역할을 설정합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(카테고리="티켓 채널이 생성될 카테고리", 로그채널="티켓 로그를 남길 채널", 관리자역할="티켓을 볼 수 있는 관리자 역할")
    async def ticket_setup(
        self,
        ctx: commands.Context,
        카테고리: discord.CategoryChannel,
        로그채널: discord.TextChannel,
        관리자역할: discord.Role,
    ):
        execute(
            "INSERT INTO ticket_config (guild_id, category_id, log_channel_id, admin_role_id) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id) DO UPDATE SET category_id=excluded.category_id, "
            "log_channel_id=excluded.log_channel_id, admin_role_id=excluded.admin_role_id",
            (ctx.guild.id, 카테고리.id, 로그채널.id, 관리자역할.id),
        )
        await ctx.reply(embed=ok_embed("티켓 설정을 완료했습니다."))

    @commands.hybrid_command(name="티켓패널", description="티켓 생성 패널을 표시합니다.")
    @commands.has_permissions(manage_guild=True)
    async def ticket_panel(self, ctx: commands.Context):
        embed = make_embed(title="🎫 문의 티켓", description="아래 버튼을 눌러 개인 문의 채널을 생성하세요.")
        await ctx.reply(embed=embed, view=TicketPanelView(self))

    async def create_ticket(self, interaction: discord.Interaction):
        config = self._get_config(interaction.guild.id)
        if not config:
            await interaction.response.send_message(embed=err_embed("먼저 관리자가 /티켓설정을 진행해야 합니다."), ephemeral=True)
            return

        existing = execute(
            "SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            (interaction.guild.id, interaction.user.id),
            fetch="one",
        )
        if existing:
            channel = interaction.guild.get_channel(existing["channel_id"])
            if channel:
                await interaction.response.send_message(
                    embed=err_embed(f"이미 열려있는 티켓이 있습니다: {channel.mention}"), ephemeral=True
                )
                return

        category = interaction.guild.get_channel(config["category_id"])
        admin_role = interaction.guild.get_role(config["admin_role_id"])

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        }
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        channel = await interaction.guild.create_text_channel(
            name=f"티켓-{interaction.user.name}", category=category, overwrites=overwrites
        )
        execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, status, created_at) VALUES (?,?,?,?,?)",
            (interaction.guild.id, channel.id, interaction.user.id, "open", now_ts()),
        )
        embed = make_embed(
            title="🎫 티켓이 생성되었습니다",
            description=f"{interaction.user.mention}님, 문의하실 내용을 남겨주세요.\n담당자가 확인 후 답변드립니다.",
        )
        await channel.send(embed=embed, view=TicketCloseView(self))
        await interaction.response.send_message(embed=ok_embed(f"티켓이 생성되었습니다: {channel.mention}"), ephemeral=True)

        log_channel = interaction.guild.get_channel(config["log_channel_id"])
        if log_channel:
            await log_channel.send(embed=make_embed(title="🎫 티켓 생성", description=f"{interaction.user.mention} - {channel.mention}"))

    async def close_ticket(self, interaction: discord.Interaction):
        ticket = execute(
            "SELECT * FROM tickets WHERE guild_id=? AND channel_id=? AND status='open'",
            (interaction.guild.id, interaction.channel.id),
            fetch="one",
        )
        if not ticket:
            await interaction.response.send_message(embed=err_embed("이 채널은 티켓 채널이 아닙니다."), ephemeral=True)
            return

        await interaction.response.send_message(embed=ok_embed("티켓을 닫는 중입니다... (5초 후 삭제)"))

        # 티켓 내용 저장(transcript)
        transcript_lines = []
        async for msg in interaction.channel.history(limit=None, oldest_first=True):
            transcript_lines.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
        transcript_text = "\n".join(transcript_lines) if transcript_lines else "(대화 내용 없음)"

        config = self._get_config(interaction.guild.id)
        execute("UPDATE tickets SET status='closed' WHERE id=?", (ticket["id"],))

        if config:
            log_channel = interaction.guild.get_channel(config["log_channel_id"])
            if log_channel:
                file = discord.File(io.BytesIO(transcript_text.encode("utf-8")), filename=f"ticket-{ticket['id']}.txt")
                await log_channel.send(
                    embed=make_embed(title="🎫 티켓 종료", description=f"티켓 #{ticket['id']} ({interaction.channel.name})"),
                    file=file,
                )

        import asyncio

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete()
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Ticket(bot))
