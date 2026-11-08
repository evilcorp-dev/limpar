import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import os
import time
from datetime import timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv

load_dotenv()

TOKEN       = os.getenv("DISCORD_TOKEN")
GUILD_ID    = int(os.getenv("GUILD_ID"))
OWNER_ID    = int(os.getenv("OWNER_ID"))
ROLE_ID     = int(os.getenv("ROLE_ID"))
MOD_ROLE_ID = int(os.getenv("MOD_ROLE_ID"))
PORT        = int(os.getenv("PORT", 8080))

LOG_CHANNEL_ID = 1569096282767626450

SPAM_LIMITE  = 5
SPAM_JANELA  = 3.0
SPAM_CASTIGO = 5

intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.voice_states    = True

bot = commands.Bot(command_prefix="!", intents=intents)
guild_obj = discord.Object(id=GUILD_ID)

antispam_ativo = True
historico: dict[int, deque] = defaultdict(deque)
punidos: set[int] = set()


def tem_permissao_limpar(interaction: discord.Interaction) -> bool:
    return any(r.id == ROLE_ID for r in interaction.user.roles) or interaction.user.id == OWNER_ID

def tem_permissao_mod(interaction: discord.Interaction) -> bool:
    return any(r.id == MOD_ROLE_ID for r in interaction.user.roles) or interaction.user.id == OWNER_ID


async def enviar_log(guild: discord.Guild, embed: discord.Embed):
    canal = guild.get_channel(LOG_CHANNEL_ID)
    if canal is None:
        print(f"[log] canal {LOG_CHANNEL_ID} não encontrado")
        return
    try:
        await canal.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[log] erro ao enviar log: {e}")


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"[✓] Bot online como {bot.user} — {len(synced)} comando(s) — antispam {'ATIVO' if antispam_ativo else 'INATIVO'}")
    except Exception as e:
        print(f"[✗] Erro no sync: {e}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        await bot.process_commands(message)
        return

    if not antispam_ativo:
        await bot.process_commands(message)
        return

    if not message.guild or message.guild.id != GUILD_ID:
        await bot.process_commands(message)
        return

    # garante que é Member e não User parcial
    member = message.guild.get_member(message.author.id)
    if member is None:
        await bot.process_commands(message)
        return

    ids_isentos = {ROLE_ID, MOD_ROLE_ID}
    if any(r.id in ids_isentos for r in member.roles) or member.id == OWNER_ID:
        await bot.process_commands(message)
        return

    if member.id in punidos:
        await bot.process_commands(message)
        return

    agora = time.monotonic()
    fila  = historico[member.id]
    fila.append(agora)

    while fila and agora - fila[0] > SPAM_JANELA:
        fila.popleft()

    print(f"[antispam] {member} — {len(fila)} msgs na janela")  # debug — remove depois de confirmar

    if len(fila) >= SPAM_LIMITE:
        punidos.add(member.id)
        historico[member.id].clear()

        timeout_ok = False
        try:
            await member.timeout(timedelta(minutes=SPAM_CASTIGO), reason="Antispam — flood")
            timeout_ok = True
            print(f"[antispam] ✓ timeout aplicado em {member} ({member.id})")
        except discord.Forbidden:
            print(
                f"[antispam] ✗ FORBIDDEN ao tentar timeout em {member} ({member.id})\n"
                f"  → Verifique: 1) bot tem permissão 'Moderar Membros'\n"
                f"  → Verifique: 2) cargo do bot está ACIMA do cargo do membro na hierarquia"
            )
        except discord.HTTPException as e:
            print(f"[antispam] ✗ HTTPException ao timeout {member}: {e}")

        if timeout_ok:
            try:
                await member.send(
                    f"🚫 Você foi silenciado em **{message.guild.name}** por **{SPAM_CASTIGO} minutos** por enviar mensagens demais."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            try:
                await message.channel.send(
                    f"⚠️ {member.mention} foi silenciado por **{SPAM_CASTIGO} min** por flood.",
                    delete_after=5
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            embed = discord.Embed(
                title="🚫 Antispam — membro punido",
                color=discord.Color.dark_red(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Membro", value=f"{member.mention} (`{member}` — `{member.id}`)", inline=False)
            embed.add_field(name="Canal do flood", value=message.channel.mention, inline=True)
            embed.add_field(name="Duração", value=f"{SPAM_CASTIGO} min", inline=True)
            embed.set_footer(text=f"ID do membro: {member.id}")
            await enviar_log(message.guild, embed)

        async def liberar(uid: int = member.id):
            await asyncio.sleep(SPAM_CASTIGO * 60)
            punidos.discard(uid)
            print(f"[antispam] {uid} removido de punidos")

        asyncio.ensure_future(liberar())

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
            batch   = min(remaining, 100)
            deleted = await interaction.channel.purge(limit=batch)
            deleted_total += len(deleted)
            remaining     -= batch
            if len(deleted) < batch:
                break
        await interaction.followup.send(f"✅ **{deleted_total}** mensagem(ns) apagada(s).", ephemeral=True)

        embed = discord.Embed(title="🧹 /limpar usado", color=discord.Color.orange(),
                              timestamp=discord.utils.utcnow())
        embed.add_field(name="Usuário",    value=f"{interaction.user.mention} (`{interaction.user}` — `{interaction.user.id}`)", inline=False)
        embed.add_field(name="Canal",      value=interaction.channel.mention, inline=True)
        embed.add_field(name="Solicitado", value=str(quantidade),             inline=True)
        embed.add_field(name="Apagadas",   value=str(deleted_total),          inline=True)
        embed.set_footer(text=f"ID do executor: {interaction.user.id}")
        await enviar_log(interaction.guild, embed)

    except discord.Forbidden:
        await interaction.followup.send("❌ Sem permissão para apagar mensagens.", ephemeral=True)
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
        await interaction.response.send_message("⚠️ Antispam já está **ativo**.", ephemeral=True)
        return
    antispam_ativo = True
    await interaction.response.send_message(
        f"✅ Antispam **ativado** — {SPAM_LIMITE} msgs em {SPAM_JANELA}s = {SPAM_CASTIGO} min de castigo.",
        ephemeral=True
    )
    embed = discord.Embed(title="✅ Antispam ativado", color=discord.Color.green(),
                          timestamp=discord.utils.utcnow())
    embed.add_field(name="Ativado por", value=f"{interaction.user.mention} (`{interaction.user}` — `{interaction.user.id}`)", inline=False)
    embed.add_field(name="Limite",      value=f"{SPAM_LIMITE} msgs em {SPAM_JANELA}s", inline=True)
    embed.add_field(name="Castigo",     value=f"{SPAM_CASTIGO} min",                   inline=True)
    embed.set_footer(text=f"ID do executor: {interaction.user.id}")
    await enviar_log(interaction.guild, embed)


# ── /antispamdesativar ─────────────────────────────────────────
@bot.tree.command(name="antispamdesativar", description="Desativa o sistema antispam", guild=guild_obj)
async def antispamdesativar(interaction: discord.Interaction):
    global antispam_ativo
    if not tem_permissao_mod(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return
    if not antispam_ativo:
        await interaction.response.send_message("⚠️ Antispam já está **desativado**.", ephemeral=True)
        return
    antispam_ativo = False
    historico.clear()
    punidos.clear()
    await interaction.response.send_message("🔕 Antispam **desativado**.", ephemeral=True)
    embed = discord.Embed(title="🔕 Antispam desativado", color=discord.Color.red(),
                          timestamp=discord.utils.utcnow())
    embed.add_field(name="Desativado por", value=f"{interaction.user.mention} (`{interaction.user}` — `{interaction.user.id}`)", inline=False)
    embed.set_footer(text=f"ID do executor: {interaction.user.id}")
    await enviar_log(interaction.guild, embed)


# ── /conectar ──────────────────────────────────────────────────
@bot.tree.command(name="conectar", description="Conecta o bot em um canal de voz", guild=guild_obj)
@app_commands.describe(canal="Canal de voz para entrar (deixe vazio para entrar no seu canal atual)")
async def conectar(interaction: discord.Interaction, canal: discord.VoiceChannel = None):
    if not tem_permissao_mod(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    destino = canal

    if destino is None:
        if interaction.user.voice and interaction.user.voice.channel:
            destino = interaction.user.voice.channel
        else:
            await interaction.response.send_message(
                "❌ Entre em um canal de voz ou especifique um canal.", ephemeral=True
            )
            return

    # já conectado em outro canal — move
    if interaction.guild.voice_client:
        try:
            await interaction.guild.voice_client.move_to(destino)
            await interaction.response.send_message(f"🔀 Movido para **{destino.name}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para entrar nesse canal.", ephemeral=True)
            return
    else:
        try:
            await destino.connect()
            await interaction.response.send_message(f"🔊 Conectado em **{destino.name}**.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ Sem permissão para entrar nesse canal.", ephemeral=True)
            return
        except asyncio.TimeoutError:
            await interaction.response.send_message("❌ Tempo esgotado ao tentar conectar.", ephemeral=True)
            return

    embed = discord.Embed(title="🔊 Bot conectado em voz", color=discord.Color.blurple(),
                          timestamp=discord.utils.utcnow())
    embed.add_field(name="Solicitado por", value=f"{interaction.user.mention} (`{interaction.user}` — `{interaction.user.id}`)", inline=False)
    embed.add_field(name="Canal",          value=destino.name, inline=True)
    embed.add_field(name="ID do canal",    value=str(destino.id), inline=True)
    embed.set_footer(text=f"ID do executor: {interaction.user.id}")
    await enviar_log(interaction.guild, embed)


# ── /desconectar ───────────────────────────────────────────────
@bot.tree.command(name="desconectar", description="Desconecta o bot do canal de voz", guild=guild_obj)
async def desconectar(interaction: discord.Interaction):
    if not tem_permissao_mod(interaction):
        await interaction.response.send_message("❌ Você não tem permissão.", ephemeral=True)
        return

    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message("⚠️ Bot não está em nenhum canal de voz.", ephemeral=True)
        return

    nome_canal = vc.channel.name
    await vc.disconnect()
    await interaction.response.send_message(f"🔇 Desconectado de **{nome_canal}**.", ephemeral=True)

    embed = discord.Embed(title="🔇 Bot desconectado de voz", color=discord.Color.greyple(),
                          timestamp=discord.utils.utcnow())
    embed.add_field(name="Solicitado por", value=f"{interaction.user.mention} (`{interaction.user}` — `{interaction.user.id}`)", inline=False)
    embed.add_field(name="Canal",          value=nome_canal, inline=True)
    embed.set_footer(text=f"ID do executor: {interaction.user.id}")
    await enviar_log(interaction.guild, embed)


# ── servidor HTTP ──────────────────────────────────────────────
async def handle_http(reader, writer):
    writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
    await writer.drain()
    writer.close()

async def main():
    server = await asyncio.start_server(handle_http, "0.0.0.0", PORT)
    async with bot:
        await asyncio.gather(server.serve_forever(), bot.start(TOKEN))

asyncio.run(main())