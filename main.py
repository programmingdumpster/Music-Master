import disnake
from disnake.ext import commands
import os
import config
# Ustawienie uprawnień (Intents) - ważne dla funkcji bota
intents = disnake.Intents.default()
intents.message_content = True # Jeśli chcesz używać komend z prefiksem i czytać treść wiadomości
intents.voice_states = True    # Niezbędne dla bota muzycznego do śledzenia stanu kanałów głosowych

# Możesz użyć `commands.Bot` dla tradycyjnych komend i slash,
# lub `disnake.InteractionBot` jeśli chcesz tylko komendy slash.
bot = commands.Bot(command_prefix="!", intents=intents) # Możesz zmienić prefix
bot.config = config

@bot.event
async def on_ready():
    print(f'Zalogowano jako {bot.user} (ID: {bot.user.id})')
    print('Bot jest gotowy do działania!')
    print('------')

# Funkcja do ładowania cogów
def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and filename != '__init__.py':
            try:
                bot.load_extension(f'cogs.{filename[:-3]}')
            except Exception as e:
                print(f'Nie udało się załadować coga {filename[:-3]}: [{type(e).__name__}] {e}')

if __name__ == '__main__':
    if  bot.run(bot.config.BOT_TOKEN):
        load_cogs()
        bot.run(bot.config.BOT_TOKEN)
    else:
        print("BŁĄD: Token bota nie został znaleziony. Upewnij się, że ustawiłeś DISCORD_BOT_TOKEN w pliku .env")