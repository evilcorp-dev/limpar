# Discord Limpar Bot

## Pré-requisitos
- Python 3.10+
- Conta de bot no [Discord Developer Portal](https://discord.com/developers/applications)

---

## Setup

### 1. Instalar dependências
```bash
pip install -r requirements.txt
```

### 2. Colocar o token
Abra o arquivo `.env` e substitua `cole_seu_token_aqui` pelo token do seu bot:
```
DISCORD_TOKEN=MeuTokenAqui123...
```

### 3. Permissões necessárias no bot (Developer Portal)
Ative em **Bot → Privileged Gateway Intents**:
- ✅ SERVER MEMBERS INTENT
- ✅ MESSAGE CONTENT INTENT

Permissões do bot no servidor (OAuth2 → bot scope):
- `Manage Messages` (para apagar mensagens)
- `Send Messages`
- `Use Slash Commands`

### 4. Rodar
```bash
python bot.py
```

---

## Uso

| Comando | Descrição |
|---|---|
| `/limpar` | Apaga 100 mensagens (padrão) |
| `/limpar quantidade:50` | Apaga 50 mensagens |

Só quem tem o cargo `1568407635001081957` (ou o dono do bot) consegue usar.  
A resposta de confirmação aparece só pra quem usou o comando (ephemeral).

---

## Notas
- Mensagens com mais de **14 dias** não podem ser apagadas em bulk (limitação da API do Discord).
- Lotes de até 1000 mensagens são processados em batches de 100 automaticamente.
