import os

BOT_TOKEN = os.environ["8941315572:AAEjayQGmFnch0b-zK1srvd5-0n2_ZaveQA"]

# Comma-separated list of admin Telegram user IDs, e.g. "123456789,987654321"
ADMIN_IDS = [int(uid.strip()) for uid in os.environ.get("977205620, 8648725144", "").split(",") if uid.strip()]
