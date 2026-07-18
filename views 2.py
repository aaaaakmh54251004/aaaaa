import discord
from discord import ui
from utils import err_embed, ok_embed


class MusicPanelView(ui.View):
    """음악 제어 패널 버튼"""

    def __init__(self, cog, guild_id: int, admin_only: bool = False):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.admin_only = admin_only

    async def _check(self, interaction: discord.Interaction) -> bool:
        if self.admin_only and not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                embed=err_embed("이 버튼은 관리자만 사용할 수 있습니다."), ephemeral=True
            )
            return False
        return True

    @ui.button(emoji="▶", style=discord.ButtonStyle.success, custom_id="music:play", row=0)
    async def play_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.resume_playback(interaction)

    @ui.button(emoji="⏸", style=discord.ButtonStyle.secondary, custom_id="music:pause", row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.pause_playback(interaction)

    @ui.button(emoji="⏭", style=discord.ButtonStyle.primary, custom_id="music:skip", row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.skip_playback(interaction)

    @ui.button(emoji="⏮", style=discord.ButtonStyle.primary, custom_id="music:prev", row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.previous_playback(interaction)

    @ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle", row=1)
    async def shuffle_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.shuffle_queue(interaction)

    @ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:loop", row=1)
    async def loop_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.toggle_loop(interaction)

    @ui.button(emoji="📄", style=discord.ButtonStyle.secondary, custom_id="music:queue", row=1)
    async def queue_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.show_queue(interaction)

    @ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="music:volup", row=2)
    async def volup_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.change_volume(interaction, 0.1)

    @ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, custom_id="music:voldown", row=2)
    async def voldown_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.change_volume(interaction, -0.1)

    @ui.button(emoji="⏹", style=discord.ButtonStyle.danger, custom_id="music:stop", row=2)
    async def stop_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.stop_playback(interaction)

    @ui.button(emoji="❌", style=discord.ButtonStyle.danger, custom_id="music:leave", row=2)
    async def leave_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check(interaction):
            return
        await self.cog.leave_voice(interaction)


class ShopBuyModal(ui.Modal, title="상점 구매"):
    item_id = ui.TextInput(label="구매할 상품 번호(ID)", placeholder="예: 1")

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        try:
            iid = int(self.item_id.value)
        except ValueError:
            await interaction.response.send_message(embed=err_embed("숫자로 입력해주세요."), ephemeral=True)
            return
        await self.cog.buy_item(interaction, iid)


class ShopPanelView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(label="구매하기", emoji="🛒", style=discord.ButtonStyle.success, custom_id="shop:buy")
    async def buy_btn(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ShopBuyModal(self.cog))

    @ui.button(label="보관함", emoji="🎒", style=discord.ButtonStyle.secondary, custom_id="shop:inventory")
    async def inv_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.show_inventory(interaction)

    @ui.button(label="순위표", emoji="🏆", style=discord.ButtonStyle.secondary, custom_id="shop:leaderboard")
    async def rank_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.show_leaderboard(interaction)

    @ui.button(label="상품목록", emoji="📦", style=discord.ButtonStyle.primary, custom_id="shop:list")
    async def list_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.show_shop_list(interaction)


class TicketPanelView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(label="티켓 생성", emoji="🎫", style=discord.ButtonStyle.success, custom_id="ticket:create")
    async def create_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.create_ticket(interaction)


class TicketCloseView(ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(label="티켓 닫기", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="ticket:close")
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        await self.cog.close_ticket(interaction)
