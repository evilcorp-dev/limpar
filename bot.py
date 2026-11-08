import discord
from discord import app_commands
from discord.ext import commands
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

TOKEN    = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
OWNER_ID = int(os.getenv("OWNER_ID"))
ROLE_ID  = int(os.getenv("ROLE_ID"))
PORT     = int(os.getenv("PORT", 8080))

# ── servidor HTTP para o Render free ──
class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")
    def log_message(self, *args):
        pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever(),
    daemon=True
).start()
# ──────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)


def tem_permissao(interaction: discord.Interaction) -> bool:
    has_role = any(r.id == ROLE_ID for r in interaction.user.roles)
    is_owner = interaction.user.id == OWNER_ID
    return has_role or is_owner


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


# ── /limpar ────────────────────────────────────────────────────
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


# ── /kick ──────────────────────────────────────────────────────
@bot.tree.command(name="kick", description="Expulsa um membro do servidor", guild=guild_obj)
@app_commands.describe(membro="Membro a ser expulso", motivo="Motivo da expulsão")
async def kick(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo informado"):
    if not tem_permissao(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    if membro.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ Não consigo expulsar esse membro (cargo superior ao meu).", ephemeral=True)
        return

    try:
        await membro.send(f"👢 Você foi expulso de **{interaction.guild.name}**.\n📋 Motivo: {motivo}")
    except discord.HTTPException:
        pass

    await membro.kick(reason=f"{interaction.user} — {motivo}")
    await interaction.response.send_message(f"✅ **{membro}** foi expulso.\n📋 Motivo: {motivo}", ephemeral=True)


# ── /ban ───────────────────────────────────────────────────────
@bot.tree.command(name="ban", description="Bane um membro do servidor", guild=guild_obj)
@app_commands.describe(membro="Membro a ser banido", motivo="Motivo do banimento", deletar_mensagens="Dias de mensagens a deletar (0–7)")
async def ban(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo informado", deletar_mensagens: int = 0):
    if not tem_permissao(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    if membro.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ Não consigo banir esse membro (cargo superior ao meu).", ephemeral=True)
        return

    deletar_mensagens = max(0, min(7, deletar_mensagens))

    try:
        await membro.send(f"🔨 Você foi banido de **{interaction.guild.name}**.\n📋 Motivo: {motivo}")
    except discord.HTTPException:
        pass

    await membro.ban(reason=f"{interaction.user} — {motivo}", delete_message_days=deletar_mensagens)
    await interaction.response.send_message(f"✅ **{membro}** foi banido.\n📋 Motivo: {motivo}", ephemeral=True)


# ── /mute ──────────────────────────────────────────────────────
@bot.tree.command(name="mute", description="Silencia um membro por X minutos", guild=guild_obj)
@app_commands.describe(membro="Membro a ser silenciado", minutos="Duração em minutos (máx: 40320 / 28 dias)", motivo="Motivo")
async def mute(interaction: discord.Interaction, membro: discord.Member, minutos: int = 10, motivo: str = "Sem motivo informado"):
    if not tem_permissao(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    if membro.top_role >= interaction.guild.me.top_role:
        await interaction.response.send_message("❌ Não consigo silenciar esse membro (cargo superior ao meu).", ephemeral=True)
        return

    if minutos < 1 or minutos > 40320:
        await interaction.response.send_message("❌ Informe entre **1** e **40320** minutos (28 dias).", ephemeral=True)
        return

    duracao = timedelta(minutes=minutos)

    try:
        await membro.timeout(duracao, reason=f"{interaction.user} — {motivo}")
        await interaction.response.send_message(
            f"🔇 **{membro}** silenciado por **{minutos} minuto(s)**.\n📋 Motivo: {motivo}",
            ephemeral=True
        )
        try:
            await membro.send(f"🔇 Você foi silenciado em **{interaction.guild.name}** por **{minutos} minuto(s)**.\n📋 Motivo: {motivo}")
        except discord.HTTPException:
            pass
    except discord.Forbidden:
        await interaction.response.send_message("❌ Sem permissão para silenciar esse membro.", ephemeral=True)


# ── /warn ──────────────────────────────────────────────────────
@bot.tree.command(name="warn", description="Avisa um membro com uma advertência", guild=guild_obj)
@app_commands.describe(membro="Membro a ser advertido", motivo="Motivo da advertência")
async def warn(interaction: discord.Interaction, membro: discord.Member, motivo: str = "Sem motivo informado"):
    if not tem_permissao(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    try:
        await membro.send(f"⚠️ Você recebeu uma advertência em **{interaction.guild.name}**.\n📋 Motivo: {motivo}")
        dm_status = "DM enviada ao membro."
    except discord.HTTPException:
        dm_status = "Não foi possível enviar DM ao membro."

    await interaction.response.send_message(
        f"⚠️ **{membro}** foi advertido.\n📋 Motivo: {motivo}\n📨 {dm_status}",
        ephemeral=True
    )


bot.run(TOKEN)