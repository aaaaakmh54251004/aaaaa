import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import DISCORD_TOKEN, PREFIX, GUILD_ID
from database import init_db
from utils import make_embed, err_embed, warn_embed

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

COGS = [
    "music",
    "level",
    "shop",
    "admin",
    "welcome",
    "ticket",
]

HELP_DATA = {
    "🎵 음악": [
        ("재생", "!재생 <검색어/링크>", "노래를 재생하거나 대기열에 추가합니다.", "!재생 아이유 밤편지"),
        ("일시정지", "!일시정지", "재생 중인 곡을 일시정지합니다.", "!일시정지"),
        ("다시재생", "!다시재생", "일시정지된 곡을 다시 재생합니다.", "!다시재생"),
        ("스킵", "!스킵", "현재 곡을 건너뜁니다.", "!스킵"),
        ("정지", "!정지", "재생을 멈추고 대기열을 비웁니다.", "!정지"),
        ("퇴장", "!퇴장", "음성채널에서 나갑니다.", "!퇴장"),
        ("셔플", "!셔플", "대기열을 무작위로 섞습니다.", "!셔플"),
        ("반복", "!반복", "현재 곡 반복 재생을 켜고 끕니다.", "!반복"),
        ("대기열", "!대기열", "대기중인 곡 목록을 봅니다.", "!대기열"),
        ("볼륨", "!볼륨 <0~200>", "재생 볼륨을 설정합니다.", "!볼륨 80"),
        ("음악패널", "!음악패널", "버튼이 있는 음악 제어 패널을 표시합니다.", "!음악패널"),
        ("노래채널설정", "!노래채널설정 <채널>", "자동재생 신청 채널을 설정합니다. (관리자)", "!노래채널설정 #음악신청"),
    ],
    "⭐ 경험치": [
        ("레벨", "!레벨 [사용자]", "레벨과 경험치를 확인합니다.", "!레벨 @사용자"),
        ("랭킹", "!랭킹", "서버 경험치 랭킹을 봅니다.", "!랭킹"),
    ],
    "🛒 상점": [
        ("상점패널", "!상점패널", "구매/보관함/순위표 버튼 패널을 표시합니다.", "!상점패널"),
        ("상품추가", "!상품추가 <이름> <가격> [역할]", "상점에 상품을 추가합니다. (관리자)", "!상품추가 VIP 500 @VIP"),
        ("상품삭제", "!상품삭제 <번호>", "상점 상품을 삭제합니다. (관리자)", "!상품삭제 1"),
        ("상품수정", "!상품수정 <번호> [이름] [가격]", "상품 정보를 수정합니다. (관리자)", "!상품수정 1 이름 300"),
        ("충전", "!충전 <사용자> <수량>", "사용자에게 코인을 지급합니다. (관리자)", "!충전 @사용자 100"),
    ],
    "👮 관리자": [
        ("관리자추가", "!관리자추가 <사용자>", "봇 관리자 권한을 부여합니다.", "!관리자추가 @사용자"),
        ("관리자제거", "!관리자제거 <사용자>", "봇 관리자 권한을 제거합니다.", "!관리자제거 @사용자"),
        ("경고", "!경고 <사용자> [사유]", "사용자에게 경고를 부여합니다.", "!경고 @사용자 욕설"),
        ("경고확인", "!경고확인 <사용자>", "경고 내역을 확인합니다.", "!경고확인 @사용자"),
        ("경고초기화", "!경고초기화 <사용자>", "경고 내역을 초기화합니다.", "!경고초기화 @사용자"),
        ("킥", "!킥 <사용자> [사유]", "사용자를 추방합니다.", "!킥 @사용자 규칙위반"),
        ("밴", "!밴 <사용자> [사유]", "사용자를 차단합니다.", "!밴 @사용자 도배"),
        ("언밴", "!언밴 <유저ID>", "차단을 해제합니다.", "!언밴 123456789012345678"),
        ("타임아웃", "!타임아웃 <사용자> <분> [사유]", "타임아웃을 부여합니다.", "!타임아웃 @사용자 10 도배"),
        ("타임아웃해제", "!타임아웃해제 <사용자>", "타임아웃을 해제합니다.", "!타임아웃해제 @사용자"),
    ],
    "🎫 티켓": [
        ("티켓설정", "!티켓설정 <카테고리> <로그채널> <관리자역할>", "티켓 시스템을 설정합니다. (관리자)", "!티켓설정 문의 #티켓로그 @스태프"),
        ("티켓패널", "!티켓패널", "티켓 생성 버튼 패널을 표시합니다. (관리자)", "!티켓패널"),
    ],
    "⚙ 서버관리": [
        ("핑", "!핑", "봇의 응답 속도를 확인합니다.", "!핑"),
        ("유저정보", "!유저정보 [사용자]", "사용자 정보를 확인합니다.", "!유저정보 @사용자"),
        ("서버정보", "!서버정보", "서버 정보를 확인합니다.", "!서버정보"),
        ("공지", "!공지 <내용> [채널]", "공지사항을 전송합니다.", "!공지 오늘 점검이 있습니다"),
        ("슬로우모드", "!슬로우모드 <초>", "채널 슬로우모드를 설정합니다.", "!슬로우모드 10"),
        ("잠금", "!잠금", "현재 채널을 잠급니다.", "!잠금"),
        ("잠금해제", "!잠금해제", "채널 잠금을 해제합니다.", "!잠금해제"),
        ("로그채널", "!로그채널 <채널>", "관리 로그 채널을 설정합니다.", "!로그채널 #관리로그"),
    ],
    "👋 환영/도움말": [
        ("환영", "!환영 <채널> [메시지]", "환영 메시지를 설정합니다.", "!환영 #환영 안녕하세요 {mention}님!"),
        ("도움말", "!도움말 [카테고리]", "명령어 도움말을 봅니다.", "!도움말 음악"),
    ],
}


@bot.event
async def on_ready():
    init_db()
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            log.info(f"코그 로드 완료: {cog}")
        except commands.ExtensionAlreadyLoaded:
            pass
        except Exception as e:
            log.exception(f"코그 로드 실패: {cog} - {e}")

    try:
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
        else:
            synced = await bot.tree.sync()
        log.info(f"슬래시 명령어 {len(synced)}개 동기화 완료")
    except Exception as e:
        log.exception(f"슬래시 명령어 동기화 실패: {e}")

    await bot.change_presence(activity=discord.Game(name="김초아님 도와주는중"))
    log.info(f"{bot.user} 로그인 완료 (ID: {bot.user.id})")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.reply(embed=err_embed("이 명령어를 사용할 권한이 없습니다."))
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply(embed=warn_embed(f"필수 입력값이 빠졌습니다: `{error.param.name}`"))
        return
    if isinstance(error, commands.BadArgument):
        await ctx.reply(embed=warn_embed("입력값 형식이 올바르지 않습니다."))
        return
    log.exception("명령어 처리 중 오류", exc_info=error)
    await ctx.reply(embed=err_embed(f"오류가 발생했습니다: `{error}`"))


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = err_embed("이 명령어를 사용할 권한이 없습니다.")
    else:
        log.exception("슬래시 명령어 처리 중 오류", exc_info=error)
        msg = err_embed(f"오류가 발생했습니다: `{error}`")
    if interaction.response.is_done():
        await interaction.followup.send(embed=msg, ephemeral=True)
    else:
        await interaction.response.send_message(embed=msg, ephemeral=True)


@bot.hybrid_command(name="도움말", description="명령어 도움말을 확인합니다.")
@app_commands.describe(카테고리="확인할 카테고리 (비우면 전체 목록)")
async def help_cmd(ctx: commands.Context, 카테고리: str = None):
    if not 카테고리:
        desc = "\n".join(f"**{cat}** - {len(cmds)}개 명령어" for cat, cmds in HELP_DATA.items())
        embed = make_embed(
            title="📖 도움말",
            description=f"{desc}\n\n`!도움말 <카테고리>` 로 세부 명령어를 확인하세요.\n예: `!도움말 음악`",
        )
        await ctx.reply(embed=embed)
        return

    matched = None
    for cat in HELP_DATA:
        if 카테고리 in cat:
            matched = cat
            break
    if not matched:
        await ctx.reply(embed=warn_embed("해당 카테고리를 찾을 수 없습니다."))
        return

    embed = make_embed(title=f"📖 {matched} 명령어")
    for name, usage, desc, example in HELP_DATA[matched]:
        embed.add_field(
            name=f"✔ {name}",
            value=f"**설명:** {desc}\n**사용법:** `{usage}`\n**예시:** `{example}`",
            inline=False,
        )
    await ctx.reply(embed=embed)


@bot.hybrid_command(name="명령어", description="도움말과 동일한 명령어 전체 목록을 표시합니다.")
async def commands_cmd(ctx: commands.Context):
    await help_cmd(ctx)


async def main():
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN이 .env에 설정되어 있지 않습니다. .env.example을 참고해 .env 파일을 만들어주세요.")
    asyncio.run(main())
