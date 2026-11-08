import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import time
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

TOKEN       = os.getenv("DISCORD_TOKEN")
GUILD_ID    = int(os.getenv("GUILD_ID"))
OWNER_ID    = int(os.getenv("OWNER_ID"))
ROLE_ID     = int(os.getenv("ROLE_ID"))
MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID"))
PORT        = int(os.getenv("PORT", 8080))

SPAM_LIMITE  = 5
SPAM_JANELA  = 3.0
SPAM_CASTIGO = 5

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)

antispam_ativo = False
historico: dict[int, deque] = defaultdict(lambda: deque())
punidos: set[int] = set()


def tem_permissao_limpar(interaction: discord.Interaction) -> bool:
    has_role = any(r.id == ROLE_ID for r in interaction.user.roles)
    return has_role or interaction.user.id == OWNER_ID

def tem_permissao_mod(interaction: discord.Interaction) -> bool:
    has_role = any(r.id == MOD_ROLE_ID for r in interaction.user.roles)
    return has_role or interaction.user.id == OWNER_ID


@bot.event
async def on_ready():
    try:
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"[✓] Bot online como {bot.user} — {len(synced)} comando(s) sincronizado(s).")
    except Exception as e:
        print(f"[✗] Erro ao sincronizar: {e}")


@bot.event
async def on_message(message: discord.Message):
    if not antispam_ativo:
        await bot.process_commands(message)
        return
    if message.author.bot:
        await bot.process_commands(message)
        return
    if not message.guild or message.guild.id != GUILD_ID:
        await bot.process_commands(message)
        return

    member = message.author
    if any(r.id in (ROLE_ID, MOD_ROLE_ID) for r in member.roles) or member.id == OWNER_ID:
        await bot.process_commands(message)
        return
    if member.id in punidos:
        await bot.process_commands(message)
        return

    agora = time.monotonic()
    fila = historico[member.id]
    fila.append(agora)
    while fila and agora - fila[0] > SPAM_JANELA:
        fila.popleft()

    if len(fila) >= SPAM_LIMITE:
        punidos.add(member.id)
        fila.clear()
        try:
            await member.timeout(
                __import__('datetime').timedelta(minutes=SPAM_CASTIGO),
                reason="Antispam — flood detectado"
            )
            try:
                await member.send(f"🚫 Você foi silenciado em **{message.guild.name}** por **{SPAM_CASTIGO} minutos** por flood.")
            except discord.HTTPException:
                pass
            await message.channel.send(
                f"⚠️ {member.mention} foi silenciado por **{SPAM_CASTIGO} min** por flood.",
                delete_after=5
            )
        except discord.Forbidden:
            pass

        async def liberar():
            await asyncio.sleep(SPAM_CASTIGO * 60)
            punidos.discard(member.id)
        asyncio.create_task(liberar())

    await bot.process_commands(message)


# ── /limpar ────────────────────────────────────────────────────
@bot.tree.command(name="limpar", description="Apaga mensagens do canal (padrão: 2000)", guild=guild_obj)
@app_commands.describe(quantidade="Número de mensagens a apagar (1–2000)")
async def limpar(interaction: discord.Interaction, quantidade: int = 2000):
    if not tem_permissao_limpar(interaction):
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


# ── /antispamativar ────────────────────────────────────────────
@bot.tree.command(name="antispamativar", description="Ativa o sistema antispam", guild=guild_obj)
async def antispamativar(interaction: discord.Interaction):
    global antispam_ativo
    if not tem_permissao_mod(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return
    if antispam_ativo:
        await interaction.response.send_message("⚠️ O antispam já está **ativo**.", ephemeral=True)
        return
    antispam_ativo = True
    await interaction.response.send_message(
        f"✅ Antispam **ativado** — {SPAM_LIMITE} mensagens em {SPAM_JANELA}s = {SPAM_CASTIGO} min de castigo.",
        ephemeral=True
    )


# ── /antispamdesativar ─────────────────────────────────────────
@bot.tree.command(name="antispamdesativar", description="Desativa o sistema antispam", guild=guild_obj)
async def antispamdesativar(interaction: discord.Interaction):
    global antispam_ativo
    if not tem_permissao_mod(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return
    if not antispam_ativo:
        await interaction.response.send_message("⚠️ O antispam já está **desativado**.", ephemeral=True)
        return
    antispam_ativo = False
    historico.clear()
    await interaction.response.send_message("🔕 Antispam **desativado**.", ephemeral=True)


# ── servidor HTTP no mesmo event loop ─────────────────────────
async def handle_http(reader, writer):
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
    await writer.drain()
    writer.close()

async def main():
    server = await asyncio.start_server(handle_http, "0.0.0.0", PORT)
    async with bot:
        await asyncio.gather(server.serve_forever(), bot.start(TOKEN))

asyncio.run(main())