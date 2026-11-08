import discord
from discord import app_commands
from discord.ext import commands
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN    = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))
ROLE_ID  = int(os.getenv("ROLE_ID"))
PORT     = int(os.getenv("PORT", 8080))

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever(), daemon=True).start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"[✓] Bot online como {bot.user} — {len(synced)} comando(s) sincronizado(s).")
    except Exception as e:
        print(f"[✗] Erro ao sincronizar comandos: {e}")

@bot.tree.command(name="limpar", description="Apaga mensagens do canal (padrão: 1000)", guild=guild_obj)
@app_commands.describe(quantidade="Número de mensagens a apagar (1–1000)")
async def limpar(interaction: discord.Interaction, quantidade: int = 1000):
    has_role = any(r.id == ROLE_ID for r in interaction.user.roles)
    is_owner = interaction.user.id == OWNER_ID

    if not has_role and not is_owner:
        await interaction.response.send_message("❌ Você não tem permissão para usar este comando.", ephemeral=True)
        return

    if quantidade < 1 or quantidade > 1000:
        await interaction.response.send_message("❌ Informe um valor entre **1** e **1000**.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    deleted_total = 0
    remaining = quantidade

    try:
        while remaining > 0:
            batch = min(remaining, 100)
            deleted = await interaction.channel.purge(limit=batch)
            deleted_total += len(deleted)
            remaining -= batch
            if len(deleted) < batch:
                break
        await interaction.followup.send(f"✅ **{deleted_total}** mensagem(ns) apagada(s).", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Sem permissão para apagar mensagens neste canal.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.followup.send(f"❌ Erro ao apagar mensagens: `{e}`", ephemeral=True)

bot.run(TOKEN)