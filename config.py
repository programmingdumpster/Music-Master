import os
from dotenv import load_dotenv

# Ładuje zmienne z pliku .env do zmiennych środowiskowych
load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
FFMPEG_EXECUTABLE = os.getenv("FFMPEG_PATH") # Jeśli ustawiłeś w .env
# Możesz tu dodać inne ustawienia
DEFAULT_PREFIX = "!"