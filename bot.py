import random
import time
import asyncio
import os
import threading

from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import BOT_TOKEN, ADMIN_IDS  # ADMIN_IDS: list of Telegram user IDs allowed to reset data
from database import load_users, save_users

REWARDS = [50, 25, 10, 5, 0]
COOLDOWN = 86400  # 24 hours


# --- Keep-alive web server for Render's free tier ---
# Render's free plan only allows Web Services, which sleep after 15 minutes
# with no incoming HTTP traffic. This tiny server gives an external pinger
# (like UptimeRobot) something to hit every few minutes to keep the bot awake.
keep_alive_app = Flask(__name__)


@keep_alive_app.route("/")
def health_check():
    return "Titan Spin Bot is alive!"


def run_keep_alive_server():
    port = int(os.environ.get("PORT", 10000))
    keep_alive_app.run(host="0.0.0.0", port=port)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🎡 Spin Now", callback_data="spin")]]

    await update.message.reply_text(
        "🎉 Welcome to Titan Spin Bot!\n\nPress the button below to spin.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()

    uid = str(update.effective_user.id)

    if uid not in users:
        users[uid] = {
            "name": update.effective_user.first_name,
            "points": 0,
            "spins": 0,
            "last_spin": 0,
        }
        save_users(users)

    user = users[uid]

    if user["last_spin"] == 0:
        next_spin = "Ready ✅"
    else:
        left = COOLDOWN - (time.time() - user["last_spin"])
        if left <= 0:
            next_spin = "Ready ✅"
        else:
            h = int(left // 3600)
            m = int((left % 3600) // 60)
            next_spin = f"{h}h {m}m"

    text = f"""
👤 {user['name']}

💰 Points: {user['points']}
🎡 Spins: {user['spins']}
⏰ Next Spin: {next_spin}
"""

    await update.message.reply_text(text)


async def spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    users = load_users()

    uid = str(query.from_user.id)

    if uid not in users:
        users[uid] = {
            "name": query.from_user.first_name,
            "points": 0,
            "spins": 0,
            "last_spin": 0,
        }

    user = users[uid]

    now = time.time()

    if now - user["last_spin"] < COOLDOWN:
        left = COOLDOWN - (now - user["last_spin"])
        h = int(left // 3600)
        m = int((left % 3600) // 60)

        await query.edit_message_text(
            f"⏰ You already spun today!\n\nNext spin in {h}h {m}m."
        )
        return

    reward = random.choice(REWARDS)

    # 🎡 Spin animation (~4 seconds)
    frames = ["🎰 | ❓ | ❓ | ❓", "🎰 | 🍒 | ❓ | ❓", "🎰 | 🍒 | 🍋 | ❓", "🎰 | 🍒 | 🍋 | 🔔"]

    for frame in frames:
        await query.edit_message_text(f"🎡 Spinning...\n\n{frame}")
        await asyncio.sleep(1)

    user["points"] += reward
    user["spins"] += 1
    user["last_spin"] = now

    save_users(users)

    if reward == 0:
        text = "😢 Bad luck!\n\nYou received 0 Points."
    else:
        text = f"🎉 Congratulations!\n\nYou won {reward} Points!"

    await query.edit_message_text(text)


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = load_users()

    if not users:
        await update.message.reply_text("📊 No players yet. Be the first to spin!")
        return

    ranked = sorted(users.values(), key=lambda u: u.get("points", 0), reverse=True)

    top = ranked[:10]

    medals = ["🥇", "🥈", "🥉"]

    lines = ["🏆 Leaderboard — Top Players\n"]

    for i, user in enumerate(top):
        prefix = medals[i] if i < 3 else f"{i + 1}."
        lines.append(
            f"{prefix} {user.get('name', 'Unknown')} — {user.get('points', 0)} pts"
        )

    # Show requesting user's own rank if they're outside the top 10
    uid = str(update.effective_user.id)
    if uid in users:
        rank = next(
            (i for i, u in enumerate(ranked) if u is users[uid]), None
        )
        if rank is not None and rank >= 10:
            lines.append(f"\nYou: #{rank + 1} — {users[uid].get('points', 0)} pts")

    await update.message.reply_text("\n".join(lines))


async def resetspins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: reset everyone's cooldown so all users can spin again immediately.
    Points and spin counts are kept."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 You don't have permission to do that.")
        return

    users = load_users()

    for user in users.values():
        user["last_spin"] = 0

    save_users(users)

    await update.message.reply_text(
        f"✅ Spin cooldown reset for {len(users)} user(s). Everyone can spin again now."
    )


async def resetdata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: wipe ALL user data (points, spins, cooldowns) for everyone.
    Shows a Yes/No confirmation popup before actually deleting anything."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("🚫 You don't have permission to do that.")
        return

    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, wipe everything", callback_data="resetdata_yes"),
            InlineKeyboardButton("❌ Cancel", callback_data="resetdata_no"),
        ]
    ]

    await update.message.reply_text(
        "⚠️ This will permanently wipe ALL user data (points, spins, everything).\n\n"
        "Are you sure?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def resetdata_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        await query.edit_message_text("🚫 You don't have permission to do that.")
        return

    if query.data == "resetdata_yes":
        save_users({})
        await query.edit_message_text("🗑️ All user data has been wiped.")
    else:
        await query.edit_message_text("❎ Reset cancelled. No data was changed.")


def main():
    # Start the keep-alive web server in a background thread so Render
    # sees this as an active "web service" and doesn't put it to sleep.
    threading.Thread(target=run_keep_alive_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("resetspins", resetspins))
    app.add_handler(CommandHandler("resetdata", resetdata))
    app.add_handler(CallbackQueryHandler(resetdata_callback, pattern="^resetdata_"))
    app.add_handler(CallbackQueryHandler(spin, pattern="^spin$"))

    print("✅ Titan Spin Bot Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
