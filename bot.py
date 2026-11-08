import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN    = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))
ROLE_ID  = int(os.getenv("ROLE_ID"))
PORT     = int(os.getenv("PORT", 8080))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)


def tem_permissao(interaction: discord.Interaction) -> bool:
    has_role = any(r.id == ROLE_ID for r in interaction.user.roles)
    return has_role or interaction.user.id == OWNER_ID


@bot.event
async def on_ready():
    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        bot.tree.clear_commands(guild=guild_obj)
        await bot.tree.sync(guild=guild_obj)
        print(f"[✓] Bot online como {bot.user} — comandos sincronizados.")
    except Exception as e:
        print(f"[✗] Erro ao sincronizar comandos: {e}")


@bot.tree.command(name="limpar", description="Apaga mensagens do canal (padrão: 2000)", guild=guild_obj)
@app_commands.describe(quantidade="Número de mensagens a apagar (1–2000)")
async def limpar(interaction: discord.Interaction, quantidade: int = 2000):
    if not tem_permissao(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return
    if quantidade < 1 or quantidade > 2000:
        await interaction.response.send_message("❌ Informe um valor entre **1** e **2000**.", ephemeral=True)
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
        await interaction.followup.send(f"❌ Erro: `{e}`", ephemeral=True)


async def handle_http(reader, writer):
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
    await writer.drain()
    writer.close()

async def main():
    server = await asyncio.start_server(handle_http, "0.0.0.0", PORT)
    async with bot:
        await asyncio.gather(server.serve_forever(), bot.start(TOKEN))

asyncio.run(main())