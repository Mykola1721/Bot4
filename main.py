
import discord
from discord.ext import commands
import json
import aiohttp
from bs4 import BeautifulSoup
import re
import asyncio
import os
from dotenv import load_dotenv

# Завантаження .env (важливо для Render і локального запуску!)
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.messages = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

DB_FILE = "games_db.json"
SELECT_MENU_FILE = "select_menu_ids.json"

def load_json(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(file_name, data):
    with open(file_name, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def search_game_on_steam(game_name):
    query = f"site:store.steampowered.com {game_name}"
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": "Mozilla/5.0"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()
                soup = BeautifulSoup(text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    match = re.search(r"https://store\.steampowered\.com/app/\d+/.+?/", href)
                    if match:
                        title = link.get_text()
                        return title.strip()
        except Exception as e:
            print(f"❌ Помилка при пошуку: {e}")
    return None

def parse_game_names(message):
    return [part.strip() for part in re.split(r"[,\\n]+|\s{2,}", message) if part.strip()]

@bot.event
async def on_ready():
    print(f"✅ Бот запущено як {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.name == "запропонувати-гру":
        content = message.content.strip()
        game_names = parse_game_names(content)
        db = load_json(DB_FILE)

        for game in game_names:
            if game in db:
                continue

            steam_title = await search_game_on_steam(game)
            if not steam_title:
                await message.channel.send(f"❌ Не вдалося знайти гру **{game}** в Steam.")
                continue

            await message.channel.send(
                f"❓ Можливо ти мав на увазі: **{steam_title}**?\nВідповідай 'так' або 'ні' (30 секунд)"
            )

            def check(m):
                return m.author == message.author and m.channel == message.channel and m.content.lower() in ["так", "ні"]

            try:
                reply = await bot.wait_for("message", check=check, timeout=30.0)
            except asyncio.TimeoutError:
                await message.channel.send("⏰ Час вичерпано.")
                return

            if reply.content.lower() != "так":
                await message.channel.send("🚫 Гру скасовано.")
                return

            guild = message.guild
            role = await guild.create_role(name=steam_title)
            await message.author.add_roles(role)
            await message.channel.send(f"✅ Роль **{steam_title}** створено та додано тобі!")

            db[steam_title] = {"role_id": role.id, "group": 1}
            save_json(DB_FILE, db)

# Запуск бота
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("❌ DISCORD_TOKEN не знайдено! Додай токен до .env або Render Environment Variables.")
else:
    bot.run(TOKEN)
