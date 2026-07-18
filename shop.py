import discord
from discord import app_commands
from discord.ext import commands

from database import execute
from utils import make_embed, ok_embed, err_embed, warn_embed, now_ts
from views import ShopPanelView


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 봇 재시작 후에도 이전에 전송된 패널의 버튼이 동작하도록 영구 View 등록
        bot.add_view(ShopPanelView(self))

    def _get_coins(self, guild_id: int, user_id: int) -> int:
        row = execute(
            "SELECT coins FROM levels WHERE guild_id=? AND user_id=?", (guild_id, user_id), fetch="one"
        )
        return row["coins"] if row else 0

    async def show_shop_list(self, interaction: discord.Interaction):
        rows = execute("SELECT * FROM shop_items WHERE guild_id=?", (interaction.guild.id,), fetch="all")
        if not rows:
            await interaction.response.send_message(embed=warn_embed("등록된 상품이 없습니다."), ephemeral=True)
            return
        lines = [f"`{r['id']}.` {r['name']} - {r['price']} 코인\n　{r['description'] or ''}" for r in rows]
        await interaction.response.send_message(
            embed=make_embed(title="🛒 상점 상품 목록", description="\n".join(lines)), ephemeral=True
        )

    async def buy_item(self, interaction: discord.Interaction, item_id: int):
        item = execute(
            "SELECT * FROM shop_items WHERE id=? AND guild_id=?", (item_id, interaction.guild.id), fetch="one"
        )
        if not item:
            await interaction.response.send_message(embed=err_embed("존재하지 않는 상품입니다."), ephemeral=True)
            return
        coins = self._get_coins(interaction.guild.id, interaction.user.id)
        if coins < item["price"]:
            await interaction.response.send_message(embed=err_embed("코인이 부족합니다."), ephemeral=True)
            return
        execute(
            "UPDATE levels SET coins = coins - ? WHERE guild_id=? AND user_id=?",
            (item["price"], interaction.guild.id, interaction.user.id),
        )
        execute(
            "INSERT INTO inventory (guild_id, user_id, item_id, purchased_at) VALUES (?,?,?,?)",
            (interaction.guild.id, interaction.user.id, item_id, now_ts()),
        )
        if item["role_id"]:
            role = interaction.guild.get_role(item["role_id"])
            if role:
                try:
                    await interaction.user.add_roles(role)
                except discord.Forbidden:
                    pass
        await interaction.response.send_message(embed=ok_embed(f"**{item['name']}** 구매 완료!"), ephemeral=True)

    async def show_inventory(self, interaction: discord.Interaction):
        rows = execute(
            """SELECT shop_items.name as name, inventory.purchased_at as purchased_at
               FROM inventory JOIN shop_items ON inventory.item_id = shop_items.id
               WHERE inventory.guild_id=? AND inventory.user_id=?""",
            (interaction.guild.id, interaction.user.id),
            fetch="all",
        )
        if not rows:
            await interaction.response.send_message(embed=warn_embed("보관함이 비어 있습니다."), ephemeral=True)
            return
        lines = [f"- {r['name']}" for r in rows]
        await interaction.response.send_message(
            embed=make_embed(title="🎒 내 보관함", description="\n".join(lines)), ephemeral=True
        )

    async def show_leaderboard(self, interaction: discord.Interaction):
        rows = execute(
            "SELECT * FROM levels WHERE guild_id=? ORDER BY coins DESC LIMIT 10", (interaction.guild.id,), fetch="all"
        )
        if not rows:
            await interaction.response.send_message(embed=warn_embed("데이터가 없습니다."), ephemeral=True)
            return
        lines = []
        for i, row in enumerate(rows, 1):
            member = interaction.guild.get_member(row["user_id"])
            name = member.display_name if member else f"알수없음({row['user_id']})"
            lines.append(f"`{i}.` {name} - {row['coins']} 코인")
        await interaction.response.send_message(
            embed=make_embed(title="🏆 코인 순위표", description="\n".join(lines)), ephemeral=True
        )

    @commands.hybrid_command(name="상점패널", description="상점 패널을 표시합니다.")
    async def shop_panel(self, ctx: commands.Context):
        embed = make_embed(title="🛒 경험치 상점", description="아래 버튼으로 상품을 구매하거나 확인할 수 있습니다.")
        await ctx.reply(embed=embed, view=ShopPanelView(self))

    @commands.hybrid_command(name="상품추가", description="상점에 상품을 추가합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(이름="상품 이름", 가격="필요 코인", 역할="지급할 역할(선택)", 설명="상품 설명(선택)")
    async def add_item(self, ctx: commands.Context, 이름: str, 가격: int, 역할: discord.Role = None, 설명: str = ""):
        execute(
            "INSERT INTO shop_items (guild_id, name, price, role_id, description) VALUES (?,?,?,?,?)",
            (ctx.guild.id, 이름, 가격, 역할.id if 역할 else None, 설명),
        )
        await ctx.reply(embed=ok_embed(f"상품 **{이름}**을(를) 추가했습니다."))

    @commands.hybrid_command(name="상품삭제", description="상점 상품을 삭제합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(상품번호="삭제할 상품 ID")
    async def remove_item(self, ctx: commands.Context, 상품번호: int):
        execute("DELETE FROM shop_items WHERE id=? AND guild_id=?", (상품번호, ctx.guild.id))
        await ctx.reply(embed=ok_embed("상품을 삭제했습니다."))

    @commands.hybrid_command(name="상품수정", description="상점 상품 가격/이름을 수정합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(상품번호="수정할 상품 ID", 이름="새 이름", 가격="새 가격")
    async def edit_item(self, ctx: commands.Context, 상품번호: int, 이름: str = None, 가격: int = None):
        item = execute("SELECT * FROM shop_items WHERE id=? AND guild_id=?", (상품번호, ctx.guild.id), fetch="one")
        if not item:
            await ctx.reply(embed=err_embed("존재하지 않는 상품입니다."))
            return
        new_name = 이름 or item["name"]
        new_price = 가격 if 가격 is not None else item["price"]
        execute("UPDATE shop_items SET name=?, price=? WHERE id=?", (new_name, new_price, 상품번호))
        await ctx.reply(embed=ok_embed("상품 정보를 수정했습니다."))

    @commands.hybrid_command(name="충전", description="관리자가 사용자에게 코인을 지급합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(대상="코인을 받을 사용자", 수량="지급할 코인 수")
    async def charge_coins(self, ctx: commands.Context, 대상: discord.Member, 수량: int):
        execute(
            "INSERT INTO levels (guild_id, user_id, coins) VALUES (?,?,?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET coins = coins + excluded.coins",
            (ctx.guild.id, 대상.id, 수량),
        )
        await ctx.reply(embed=ok_embed(f"{대상.mention}님에게 {수량} 코인을 지급했습니다."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
