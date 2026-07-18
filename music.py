import asyncio
import random
import re
import discord
from discord import app_commands
from discord.ext import commands
import yt_dlp

from config import FFMPEG_PATH, DEFAULT_VOLUME, MAX_QUEUE_DISPLAY, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
from database import execute
from utils import make_embed, ok_embed, err_embed, warn_embed, format_duration
from views import MusicPanelView

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "extract_flat": False,
}

FFMPEG_BEFORE_OPTS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
FFMPEG_OPTS = "-vn"

SPOTIFY_TRACK_RE = re.compile(r"open\.spotify\.com/track/([A-Za-z0-9]+)")
SPOTIFY_PLAYLIST_RE = re.compile(r"open\.spotify\.com/playlist/([A-Za-z0-9]+)")
SPOTIFY_ALBUM_RE = re.compile(r"open\.spotify\.com/album/([A-Za-z0-9]+)")


class Track:
    def __init__(self, title, url, webpage_url, duration, requester, thumbnail=None):
        self.title = title
        self.url = url  # 실제 스트림 URL
        self.webpage_url = webpage_url
        self.duration = duration
        self.requester = requester
        self.thumbnail = thumbnail


class GuildMusicState:
    def __init__(self, guild_id: int):
        self.guild_id = guild_id
        self.queue: list[Track] = []
        self.history: list[Track] = []
        self.current: Track | None = None
        self.voice_client: discord.VoiceClient | None = None
        self.volume: float = DEFAULT_VOLUME
        self.loop: bool = False
        self.text_channel: discord.abc.Messageable | None = None
        self.panel_message: discord.Message | None = None
        self.play_next_lock = asyncio.Lock()


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}
        # 봇 재시작 후에도 이전에 전송된 패널의 버튼이 동작하도록 영구 View 등록
        bot.add_view(MusicPanelView(self, 0, admin_only=False))
        self._spotify = None
        if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
            try:
                import spotipy
                from spotipy.oauth2 import SpotifyClientCredentials

                self._spotify = spotipy.Spotify(
                    auth_manager=SpotifyClientCredentials(
                        client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET
                    )
                )
            except Exception:
                self._spotify = None

    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState(guild_id)
        return self.states[guild_id]

    # ---------- 검색/추출 ----------

    async def _extract(self, query: str) -> list[dict]:
        """query가 URL이든 검색어든 처리 후 yt-dlp entry dict 리스트 반환"""
        loop = asyncio.get_event_loop()

        # Spotify 링크 처리 -> 트랙명으로 변환 후 유튜브 검색
        if "open.spotify.com" in query:
            titles = await self._resolve_spotify(query)
            if not titles:
                return []
            results = []
            for t in titles:
                entry = await self._ytdlp_search(f"ytsearch1:{t}")
                if entry:
                    results.extend(entry)
            return results

        return await self._ytdlp_search(query)

    async def _ytdlp_search(self, query: str) -> list[dict]:
        loop = asyncio.get_event_loop()

        def run():
            with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
                info = ydl.extract_info(query, download=False)
                if "entries" in info:
                    return [e for e in info["entries"] if e]
                return [info]

        try:
            return await loop.run_in_executor(None, run)
        except Exception:
            return []

    async def _resolve_spotify(self, url: str) -> list[str]:
        if not self._spotify:
            return []
        loop = asyncio.get_event_loop()

        def run():
            titles = []
            m = SPOTIFY_TRACK_RE.search(url)
            if m:
                tr = self._spotify.track(m.group(1))
                titles.append(f"{tr['name']} {tr['artists'][0]['name']}")
                return titles
            m = SPOTIFY_PLAYLIST_RE.search(url)
            if m:
                pl = self._spotify.playlist_items(m.group(1))
                for item in pl["items"]:
                    tr = item.get("track")
                    if tr:
                        titles.append(f"{tr['name']} {tr['artists'][0]['name']}")
                return titles
            m = SPOTIFY_ALBUM_RE.search(url)
            if m:
                al = self._spotify.album_tracks(m.group(1))
                for tr in al["items"]:
                    titles.append(f"{tr['name']} {tr['artists'][0]['name']}")
                return titles
            return titles

        try:
            return await loop.run_in_executor(None, run)
        except Exception:
            return []

    # ---------- 재생 제어 ----------

    async def _ensure_voice(self, interaction_or_ctx, state: GuildMusicState) -> bool:
        user = interaction_or_ctx.user if isinstance(interaction_or_ctx, discord.Interaction) else interaction_or_ctx.author
        if not user.voice or not user.voice.channel:
            return False
        channel = user.voice.channel
        if state.voice_client and state.voice_client.is_connected():
            if state.voice_client.channel.id != channel.id:
                await state.voice_client.move_to(channel)
        else:
            state.voice_client = await channel.connect()
        return True

    async def add_to_queue(self, guild: discord.Guild, requester: discord.Member, query: str,
                            channel: discord.abc.Messageable) -> tuple[int, str | None]:
        state = self.get_state(guild.id)
        state.text_channel = channel
        entries = await self._extract(query)
        if not entries:
            return 0, None

        added_title = None
        for e in entries:
            track = Track(
                title=e.get("title", "알 수 없는 제목"),
                url=e.get("url") or e.get("webpage_url"),
                webpage_url=e.get("webpage_url", ""),
                duration=e.get("duration"),
                requester=requester,
                thumbnail=e.get("thumbnail"),
            )
            state.queue.append(track)
            if added_title is None:
                added_title = track.title

        if not state.voice_client or not state.voice_client.is_playing():
            await self._play_next(guild)

        return len(entries), added_title

    async def _play_next(self, guild: discord.Guild):
        state = self.get_state(guild.id)
        async with state.play_next_lock:
            if state.loop and state.current:
                state.queue.insert(0, state.current)

            if not state.queue:
                state.current = None
                await self._maybe_disconnect(guild)
                return

            if not state.voice_client or not state.voice_client.is_connected():
                return

            track = state.queue.pop(0)
            state.current = track
            if state.current in state.history:
                pass
            state.history.append(track)
            if len(state.history) > 20:
                state.history.pop(0)

            try:
                source = discord.FFmpegPCMAudio(
                    track.url, executable=FFMPEG_PATH, before_options=FFMPEG_BEFORE_OPTS, options=FFMPEG_OPTS
                )
                source = discord.PCMVolumeTransformer(source, volume=state.volume)
            except Exception:
                if state.text_channel:
                    await state.text_channel.send(embed=err_embed(f"재생 실패: {track.title}"))
                await self._play_next(guild)
                return

            def _after(err):
                fut = asyncio.run_coroutine_threadsafe(self._play_next(guild), self.bot.loop)
                try:
                    fut.result()
                except Exception:
                    pass

            state.voice_client.play(source, after=_after)
            if state.text_channel:
                await state.text_channel.send(embed=self._now_playing_embed(state))

    def _now_playing_embed(self, state: GuildMusicState) -> discord.Embed:
        track = state.current
        if not track:
            return make_embed(title="🎵 재생 중인 곡 없음")
        embed = make_embed(
            title="🎵 현재 재생 중",
            description=f"[{track.title}]({track.webpage_url})" if track.webpage_url else track.title,
            fields=[
                ("재생시간", format_duration(track.duration), True),
                ("신청자", track.requester.mention, True),
                ("대기열", f"{len(state.queue)}곡", True),
            ],
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        return embed

    async def _maybe_disconnect(self, guild: discord.Guild):
        state = self.get_state(guild.id)
        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.disconnect()
        state.voice_client = None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        state = self.states.get(guild.id)
        if not state or not state.voice_client:
            return
        channel = state.voice_client.channel
        if channel and len([m for m in channel.members if not m.bot]) == 0:
            await asyncio.sleep(15)
            if channel and len([m for m in channel.members if not m.bot]) == 0:
                state.queue.clear()
                await self._maybe_disconnect(guild)

    # ---------- 패널에서 호출되는 함수들 ----------

    async def resume_playback(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await interaction.response.send_message(embed=ok_embed("재생을 다시 시작했습니다."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=warn_embed("일시정지된 곡이 없습니다."), ephemeral=True)

    async def pause_playback(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await interaction.response.send_message(embed=ok_embed("일시정지했습니다."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=warn_embed("재생 중인 곡이 없습니다."), ephemeral=True)

    async def skip_playback(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()
            await interaction.response.send_message(embed=ok_embed("다음 곡으로 넘어갑니다."), ephemeral=True)
        else:
            await interaction.response.send_message(embed=warn_embed("재생 중인 곡이 없습니다."), ephemeral=True)

    async def previous_playback(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if len(state.history) < 2:
            await interaction.response.send_message(embed=warn_embed("이전 곡이 없습니다."), ephemeral=True)
            return
        state.history.pop()  # 현재곡 제거
        prev_track = state.history.pop()
        state.queue.insert(0, prev_track)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()
        await interaction.response.send_message(embed=ok_embed("이전 곡을 재생합니다."), ephemeral=True)

    async def shuffle_queue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        random.shuffle(state.queue)
        await interaction.response.send_message(embed=ok_embed("대기열을 섞었습니다."), ephemeral=True)

    async def toggle_loop(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        state.loop = not state.loop
        await interaction.response.send_message(
            embed=ok_embed(f"반복 재생을 {'켰습니다' if state.loop else '껐습니다'}."), ephemeral=True
        )

    async def show_queue(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        if not state.queue:
            await interaction.response.send_message(embed=warn_embed("대기열이 비어 있습니다."), ephemeral=True)
            return
        lines = []
        for i, t in enumerate(state.queue[:MAX_QUEUE_DISPLAY], 1):
            lines.append(f"`{i}.` {t.title} - {t.requester.mention}")
        extra = len(state.queue) - MAX_QUEUE_DISPLAY
        desc = "\n".join(lines)
        if extra > 0:
            desc += f"\n...외 {extra}곡"
        await interaction.response.send_message(embed=make_embed(title="📄 대기열", description=desc), ephemeral=True)

    async def change_volume(self, interaction: discord.Interaction, delta: float):
        state = self.get_state(interaction.guild.id)
        state.volume = max(0.0, min(2.0, state.volume + delta))
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await interaction.response.send_message(
            embed=ok_embed(f"볼륨: {int(state.volume * 100)}%"), ephemeral=True
        )

    async def stop_playback(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        state.queue.clear()
        if state.voice_client:
            state.voice_client.stop()
        await interaction.response.send_message(embed=ok_embed("재생을 정지하고 대기열을 비웠습니다."), ephemeral=True)

    async def leave_voice(self, interaction: discord.Interaction):
        state = self.get_state(interaction.guild.id)
        state.queue.clear()
        await self._maybe_disconnect(interaction.guild)
        await interaction.response.send_message(embed=ok_embed("음성채널에서 퇴장했습니다."), ephemeral=True)

    # ---------- 명령어 ----------

    @commands.hybrid_command(name="재생", description="노래 제목이나 링크로 곡을 재생합니다.")
    @app_commands.describe(검색어="노래 제목, 유튜브/사운드클라우드/스포티파이 링크")
    async def play(self, ctx: commands.Context, *, 검색어: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.reply(embed=err_embed("먼저 음성채널에 입장해주세요."))
            return
        state = self.get_state(ctx.guild.id)
        await self._ensure_voice(ctx, state)
        msg = await ctx.reply(embed=make_embed(title="🔎 검색 중...", description=검색어))
        count, title = await self.add_to_queue(ctx.guild, ctx.author, 검색어, ctx.channel)
        if count == 0:
            await msg.edit(embed=err_embed("결과를 찾을 수 없습니다."))
            return
        if count == 1:
            await msg.edit(embed=ok_embed(f"대기열에 추가됨: **{title}**"))
        else:
            await msg.edit(embed=ok_embed(f"플레이리스트에서 **{count}곡**을 대기열에 추가했습니다."))

    @commands.hybrid_command(name="일시정지", description="재생을 일시정지합니다.")
    async def pause_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_playing():
            state.voice_client.pause()
            await ctx.reply(embed=ok_embed("일시정지했습니다."))
        else:
            await ctx.reply(embed=warn_embed("재생 중인 곡이 없습니다."))

    @commands.hybrid_command(name="다시재생", description="일시정지된 재생을 다시 시작합니다.")
    async def resume_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.voice_client and state.voice_client.is_paused():
            state.voice_client.resume()
            await ctx.reply(embed=ok_embed("다시 재생합니다."))
        else:
            await ctx.reply(embed=warn_embed("일시정지된 곡이 없습니다."))

    @commands.hybrid_command(name="스킵", description="현재 곡을 건너뜁니다.")
    async def skip_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if state.voice_client and (state.voice_client.is_playing() or state.voice_client.is_paused()):
            state.voice_client.stop()
            await ctx.reply(embed=ok_embed("스킵했습니다."))
        else:
            await ctx.reply(embed=warn_embed("재생 중인 곡이 없습니다."))

    @commands.hybrid_command(name="정지", description="재생을 멈추고 대기열을 비웁니다.")
    async def stop_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.queue.clear()
        if state.voice_client:
            state.voice_client.stop()
        await ctx.reply(embed=ok_embed("정지했습니다."))

    @commands.hybrid_command(name="퇴장", description="음성채널에서 봇을 내보냅니다.")
    async def leave_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.queue.clear()
        await self._maybe_disconnect(ctx.guild)
        await ctx.reply(embed=ok_embed("퇴장했습니다."))

    @commands.hybrid_command(name="셔플", description="대기열을 무작위로 섞습니다.")
    async def shuffle_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        random.shuffle(state.queue)
        await ctx.reply(embed=ok_embed("대기열을 섞었습니다."))

    @commands.hybrid_command(name="반복", description="현재 곡 반복 재생을 켜거나 끕니다.")
    async def loop_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        state.loop = not state.loop
        await ctx.reply(embed=ok_embed(f"반복 재생 {'켬' if state.loop else '끔'}"))

    @commands.hybrid_command(name="대기열", description="현재 대기열을 확인합니다.")
    async def queue_cmd(self, ctx: commands.Context):
        state = self.get_state(ctx.guild.id)
        if not state.queue:
            await ctx.reply(embed=warn_embed("대기열이 비어 있습니다."))
            return
        lines = [f"`{i}.` {t.title} - {t.requester.mention}" for i, t in enumerate(state.queue[:MAX_QUEUE_DISPLAY], 1)]
        await ctx.reply(embed=make_embed(title="📄 대기열", description="\n".join(lines)))

    @commands.hybrid_command(name="볼륨", description="재생 볼륨을 설정합니다. (0~200)")
    @app_commands.describe(퍼센트="0에서 200 사이의 볼륨 값")
    async def volume_cmd(self, ctx: commands.Context, 퍼센트: int):
        state = self.get_state(ctx.guild.id)
        state.volume = max(0.0, min(2.0, 퍼센트 / 100))
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        await ctx.reply(embed=ok_embed(f"볼륨을 {퍼센트}%로 설정했습니다."))

    @commands.hybrid_command(name="음악패널", description="음악 제어 패널을 표시합니다.")
    @commands.has_permissions(manage_guild=True)
    async def panel_cmd(self, ctx: commands.Context, 관리자전용: bool = False):
        state = self.get_state(ctx.guild.id)
        embed = self._now_playing_embed(state)
        view = MusicPanelView(self, ctx.guild.id, admin_only=관리자전용)
        msg = await ctx.reply(embed=embed, view=view)
        state.panel_message = msg

    @commands.hybrid_command(name="노래채널설정", description="자동 재생 신청을 받을 채널을 설정합니다.")
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(채널="음악 신청을 받을 텍스트 채널")
    async def set_music_channel(self, ctx: commands.Context, 채널: discord.TextChannel):
        execute(
            "INSERT INTO music_channels (guild_id, channel_id) VALUES (?, ?) "
            "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
            (ctx.guild.id, 채널.id),
        )
        await ctx.reply(embed=ok_embed(f"{채널.mention}이(가) 음악 신청 채널로 설정되었습니다."))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        row = execute(
            "SELECT channel_id FROM music_channels WHERE guild_id=?", (message.guild.id,), fetch="one"
        )
        if not row or row["channel_id"] != message.channel.id:
            return
        if message.content.startswith(("!", "/")):
            return
        if not message.author.voice or not message.author.voice.channel:
            await message.channel.send(embed=err_embed("먼저 음성채널에 입장해주세요."), delete_after=5)
            return
        state = self.get_state(message.guild.id)
        await self._ensure_voice(message, state)
        msg = await message.channel.send(embed=make_embed(title="🔎 검색 중...", description=message.content))
        count, title = await self.add_to_queue(message.guild, message.author, message.content, message.channel)
        if count == 0:
            await msg.edit(embed=err_embed("결과를 찾을 수 없습니다."))
            return
        if count == 1:
            await msg.edit(embed=ok_embed(f"대기열에 추가됨: **{title}**"))
        else:
            await msg.edit(embed=ok_embed(f"플레이리스트에서 **{count}곡**을 대기열에 추가했습니다."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
