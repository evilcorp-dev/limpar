import discord
from discord import app_commands
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# ── IDs ──────────────────────────────────────────────
GUILD_ID  = 1542578484289740922
OWNER_ID  = 1392646068868747305
ROLE_ID   = 1568407635001081957
# ─────────────────────────────────────────────────────

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


@bot.tree.command(
    name="limpar",
    description="Apaga mensagens do canal (padrão: 100)",
    guild=guild_obj,
)
@app_commands.describe(quantidade="Número de mensagens a apagar (1–1000)")
async def limpar(interaction: discord.Interaction, quantidade: int = 1000):
    # ── verificação de cargo / dono ──
    has_role  = any(r.id == ROLE_ID for r in interaction.user.roles)
    is_owner  = interaction.user.id == OWNER_ID

    if not has_role and not is_owner:
        await interaction.response.send_message(
            "❌ Você não tem permissão para usar este comando.",
            ephemeral=True,
        )
        return

    # ── validação de range ──
    if quantidade < 1 or quantidade > 1000:
        await interaction.response.send_message(
            "❌ Informe um valor entre **1** e **1000**.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(ephemeral=True)

    # Discord limita bulk_delete a 100 por chamada — fazemos em lotes
    deleted_total = 0
    remaining = quantidade

    try:
        while remaining > 0:
            batch = min(remaining, 100)
            deleted = await interaction.channel.purge(limit=batch)
            deleted_total += len(deleted)
            remaining -= batch
            if len(deleted) < batch:
                break  # canal ficou vazio antes do limite

        await interaction.followup.send(
            f"✅ **{deleted_total}** mensagem(ns) apagada(s).",
            ephemeral=True,
        )
    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Sem permissão para apagar mensagens neste canal.",
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.followup.send(
            f"❌ Erro ao apagar mensagens: `{e}`",
            ephemeral=True,
        )


bot.run(TOKEN)
