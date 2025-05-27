import disnake
from disnake.ext import commands
import yt_dlp
import asyncio
import collections  # Dla deque


class MusicCog(commands.Cog, name="Muzyka"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # self.voice_clients = {} # Nie jest już potrzebne, disnake zarządza tym przez ctx.guild.voice_client
        self.queues = collections.defaultdict(collections.deque)  # Klucz: guild_id, Wartość: deque z piosenkami
        self.current_songs = {}  # Klucz: guild_id, Wartość: aktualnie grana piosenka (info)

        self.ffmpeg_path = getattr(bot.config, 'FFMPEG_EXECUTABLE', 'ffmpeg')  # Pobierz z config lub użyj 'ffmpeg'

        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -loglevel quiet'  # -vn = no video, -loglevel quiet = mniej logów z ffmpeg
        }
        # w pliku cogs/music_cog.py, w metodzie __init__ klasy MusicCog
        self.ydl_options = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0',  # To już masz, jest OK
            'cookiefile': 'cookies.txt'  # <-- DODAJ TĘ LINIĘ
        }

    async def _ensure_voice_client(self, ctx: commands.Context):
        """Upewnia się, że bot jest na kanale głosowym użytkownika."""
        if not ctx.author.voice:
            await ctx.send("Nie jesteś połączony z żadnym kanałem głosowym!")
            return None

        voice_channel = ctx.author.voice.channel
        if ctx.guild.voice_client is None:
            try:
                await voice_channel.connect()
            except Exception as e:
                await ctx.send(f"Nie mogłem dołączyć do kanału: {e}")
                return None
        elif ctx.guild.voice_client.channel != voice_channel:
            await ctx.guild.voice_client.move_to(voice_channel)

        return ctx.guild.voice_client

    def _song_finished_callback(self, guild_id: int, error=None):
        """Callback wywoływany po zakończeniu odtwarzania piosenki."""
        if error:
            print(f"Błąd odtwarzacza w gildii {guild_id}: {error}")

        # Usuń informację o aktualnie granej piosence
        if guild_id in self.current_songs:
            del self.current_songs[guild_id]

        # Sprawdź, czy jest następna piosenka w kolejce
        if guild_id in self.queues and self.queues[guild_id]:
            # Potrzebujemy kontekstu (lub przynajmniej obiektu gildii/kanału) aby wysłać wiadomość "Now playing"
            # Najlepiej stworzyć zadanie asyncio, które pobierze voice_client i odpali _play_next
            # Dla uproszczenia na razie tylko logika, bez wysyłania wiadomości z tego callbacku
            # Musimy mieć dostęp do obiektu bota, aby znaleźć voice_client dla guild_id
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                asyncio.run_coroutine_threadsafe(self._play_next(guild), self.bot.loop)
        elif guild_id in self.queues and not self.queues[guild_id]:
            # Można dodać logikę auto-rozłączania po jakimś czasie braku aktywności
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                # Można wysłać wiadomość, że kolejka jest pusta
                # asyncio.run_coroutine_threadsafe(guild.voice_client.send_message("Kolejka jest pusta."), self.bot.loop)
                pass

    async def _play_next(self, guild: disnake.Guild):
        """Odtwarza następną piosenkę z kolejki dla danej gildii."""
        if guild.id in self.queues and self.queues[guild.id]:
            song_info = self.queues[guild.id].popleft()
            self.current_songs[guild.id] = song_info

            voice_client = guild.voice_client
            if not voice_client:  # Bot został rozłączony
                if guild.id in self.current_songs: del self.current_songs[guild.id]
                self.queues[guild.id].clear()
                return

            try:
                audio_source = disnake.FFmpegPCMAudio(
                    song_info['url'],
                    executable=self.ffmpeg_path,
                    **self.ffmpeg_options
                )
                voice_client.play(audio_source, after=lambda e: self._song_finished_callback(guild.id, e))

                # Znajdźmy kanał, na którym bot został ostatnio aktywowany (trudne bez ctx)
                # Zamiast tego, bot mógłby mieć domyślny kanał lub zapamiętywać ostatni ctx.channel
                # Na razie pominiemy wysyłanie wiadomości "Now playing" z tego miejsca
                # await ctx.send(f"🎶 Teraz gram: **{song_info['title']}** (Poprosił: {song_info['requester']})")
            except Exception as e:
                print(f"Błąd podczas próby odtworzenia {song_info.get('title', 'piosenki')}: {e}")
                # await ctx.send(f"Nie udało się odtworzyć: {song_info.get('title', 'piosenki')}. Błąd: {e}")
                self._song_finished_callback(guild.id, e)  # Przejdź do następnej, jeśli błąd
        else:
            if guild.id in self.current_songs:
                del self.current_songs[guild.id]
            # await ctx.send("Kolejka jest pusta.")

    @commands.command(name="join", aliases=['j'], description="Bot dołącza do Twojego kanału głosowego.")
    async def join(self, ctx: commands.Context):
        vc = await self._ensure_voice_client(ctx)
        if vc:
            await ctx.send(f"Dołączyłem do kanału głosowego: {vc.channel.mention}!")

    @commands.command(name="leave", aliases=['disconnect', 'l', 'dc'], description="Bot opuszcza kanał głosowy.")
    async def leave(self, ctx: commands.Context):
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_connected():
            self.queues[ctx.guild.id].clear()
            if ctx.guild.id in self.current_songs:
                del self.current_songs[ctx.guild.id]
            await voice_client.disconnect()
            await ctx.send("Opuściłem kanał głosowy.")
        else:
            await ctx.send("Nie jestem połączony z żadnym kanałem głosowym.")

    @commands.command(name="play", aliases=['p'], description="Odtwarza piosenkę z YouTube (lub dodaje do kolejki).")
    async def play(self, ctx: commands.Context, *, query: str):
        voice_client = await self._ensure_voice_client(ctx)
        if not voice_client:
            return  # _ensure_voice_client już wysłał wiadomość

        async with ctx.typing():  # Pokaż "Bot is typing..."
            try:
                with yt_dlp.YoutubeDL(self.ydl_options) as ydl:
                    loop = asyncio.get_event_loop()
                    # Uruchom blokującą operację yt-dlp w osobnym wątku
                    info = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))

                if 'entries' in info:  # Wynik wyszukiwania lub playlista (bierzemy pierwszy)
                    song_info_dict = info['entries'][0]
                else:  # Pojedynczy film
                    song_info_dict = info

                if not song_info_dict.get('url'):
                    await ctx.send("Nie mogłem znaleźć URL dla tej piosenki.")
                    return

                song = {
                    'title': song_info_dict.get('title', 'Nieznany tytuł'),
                    'url': song_info_dict['url'],  # Bezpośredni URL do strumienia audio
                    'webpage_url': song_info_dict.get('webpage_url', query),
                    'duration': song_info_dict.get('duration_string', 'N/A'),
                    'thumbnail': song_info_dict.get('thumbnail'),
                    'requester': str(ctx.author)
                }

            except yt_dlp.utils.DownloadError as e:
                await ctx.send(f"Nie udało się pobrać informacji o piosence: `{str(e).splitlines()[-1]}`")
                return
            except Exception as e:
                await ctx.send(f"Wystąpił błąd podczas przetwarzania zapytania: {e}")
                print(f"Error in play command: {e}")
                return

        self.queues[ctx.guild.id].append(song)
        await ctx.send(f"✅ Dodano do kolejki: **{song['title']}**")

        if not voice_client.is_playing() and not voice_client.is_paused():
            await self._play_next(ctx.guild)

    @commands.command(name="skip", aliases=['s'], description="Pomija aktualnie grany utwór.")
    async def skip(self, ctx: commands.Context):
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()  # To wywoła callback _song_finished_callback
            await ctx.send("⏭️ Pominięto piosenkę.")
        elif voice_client and voice_client.is_paused():  # Jeśli spauzowane, też zatrzymaj i przejdź dalej
            voice_client.stop()
            await ctx.send("⏭️ Pominięto spauzowaną piosenkę.")
        else:
            await ctx.send("Nic aktualnie nie gram, więc nie ma czego pomijać.")

    @commands.command(name="pause", description="Pauzuje odtwarzanie.")
    async def pause(self, ctx: commands.Context):
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await ctx.send("⏸️ Odtwarzanie zapauzowane.")
        else:
            await ctx.send("Nic nie jest odtwarzane lub już jest zapauzowane.")

    @commands.command(name="resume", aliases=['unpause'], description="Wznawia odtwarzanie.")
    async def resume(self, ctx: commands.Context):
        voice_client = ctx.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await ctx.send("▶️ Odtwarzanie wznowione.")
        else:
            await ctx.send("Nic nie jest zapauzowane.")

    @commands.command(name="queue", aliases=['q', 'kolejka'], description="Wyświetla aktualną kolejkę piosenek.")
    async def queue(self, ctx: commands.Context):
        current_queue = self.queues[ctx.guild.id]

        if not current_queue and not (ctx.guild.id in self.current_songs):
            await ctx.send("Kolejka jest pusta i nic nie jest odtwarzane.")
            return

        embed = disnake.Embed(title="Kolejka Muzyczna", color=disnake.Color.blue())

        if ctx.guild.id in self.current_songs:
            song = self.current_songs[ctx.guild.id]
            embed.add_field(
                name="Teraz gram:",
                value=f"[{song['title']}]({song['webpage_url']}) | `Trwa: {song['duration']}` (Poprosił: {song['requester']})",
                inline=False
            )

        if current_queue:
            queue_list_str = ""
            for i, song in enumerate(current_queue):
                if i < 10:  # Pokaż tylko np. 10 pierwszych piosenek w kolejce
                    queue_list_str += f"{i + 1}. [{song['title']}]({song['webpage_url']}) | `Trwa: {song['duration']}` (Poprosił: {song['requester']})\n"
                else:
                    queue_list_str += f"\n... i {len(current_queue) - 10} więcej."
                    break
            if not queue_list_str:
                queue_list_str = "Kolejka jest pusta."
            embed.add_field(name="Następne w kolejce:", value=queue_list_str, inline=False)
        else:
            embed.add_field(name="Następne w kolejce:", value="Kolejka jest pusta.", inline=False)

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=['np', 'currentsong', 'teraz'],
                      description="Pokazuje co jest aktualnie odtwarzane.")
    async def nowplaying(self, ctx: commands.Context):
        if ctx.guild.id in self.current_songs:
            song = self.current_songs[ctx.guild.id]
            embed = disnake.Embed(
                title="🎶 Teraz gram:",
                description=f"**[{song['title']}]({song['webpage_url']})**",
                color=disnake.Color.green()
            )
            embed.add_field(name="Czas trwania", value=song['duration'], inline=True)
            embed.add_field(name="Poprosił/a", value=song['requester'], inline=True)
            if song.get('thumbnail'):
                embed.set_thumbnail(url=song['thumbnail'])
            await ctx.send(embed=embed)
        else:
            await ctx.send("Nic aktualnie nie jest odtwarzane.")

    @commands.command(name="stop", description="Zatrzymuje odtwarzanie i czyści kolejkę (podobne do leave).")
    async def stop(self, ctx: commands.Context):
        voice_client = ctx.guild.voice_client
        if voice_client:
            self.queues[ctx.guild.id].clear()
            if ctx.guild.id in self.current_songs:
                del self.current_songs[ctx.guild.id]
            if voice_client.is_playing() or voice_client.is_paused():
                voice_client.stop()  # To wywoła callback, który może próbować grać dalej, ale kolejka będzie pusta
            # Można też od razu rozłączyć: await voice_client.disconnect()
            await ctx.send("⏹️ Odtwarzanie zatrzymane i kolejka wyczyszczona.")
        else:
            await ctx.send("Nie jestem połączony z kanałem głosowym.")


def setup(bot: commands.Bot):
    bot.add_cog(MusicCog(bot))
    print("MusicCog (prefix commands) został załadowany.")