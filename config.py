import os

BOT_TOKEN = os.environ["BOT_TOKEN"]

# Comma-separated list of admin Telegram user IDs, e.g. "123456789,987654321"
ADMIN_IDS = [int(uid.strip()) for uid in os.environ.get("ADMIN_IDS", "").split(",") if uid.strip()]
