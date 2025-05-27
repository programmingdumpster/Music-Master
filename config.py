import os
from dotenv import load_dotenv

print("--- Debug config.py ---") # Dodajemy, żeby było wiadomo, skąd są logi
print(f"Aktualny katalog roboczy: {os.getcwd()}") # Sprawdźmy, gdzie Python myśli, że jest

# Ładuje zmienne z pliku .env do zmiennych środowiskowych
print("Próba załadowania pliku .env...")
dotenv_found_and_loaded = load_dotenv() # load_dotenv() zwraca True jeśli znalazł i załadował plik .env
print(f"Czy plik .env został znaleziony i załadowany? {dotenv_found_and_loaded}")

# Sprawdźmy bezpośrednio, co zwraca os.getenv
bot_token_value_from_env = os.getenv("DISCORD_BOT_TOKEN")
ffmpeg_path_from_env = os.getenv("FFMPEG_PATH")

print(f"Wartość odczytana dla DISCORD_BOT_TOKEN: '{bot_token_value_from_env}'") # Używamy apostrofów, aby zobaczyć, czy to nie jest np. pusty string
print(f"Wartość odczytana dla FFMPEG_PATH: '{ffmpeg_path_from_env}'")
print("--- Koniec debug config.py ---")

BOT_TOKEN = bot_token_value_from_env # To jest to, co było wcześniej
FFMPEG_EXECUTABLE = ffmpeg_path_from_env # To jest to, co było wcześniej
DEFAULT_PREFIX = "&"