#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Optional, Dict, Any, Set, List
import logging
import random
import re
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ====================== CONFIG ======================

BOT_TOKEN = "8385717982:AAEQRbakA7kpY7vg1j9rNbzbRf_j-9Cm-XU"       # <-- এখানে তোমার বট টোকেন দাও
SUPER_ADMIN_USERNAME = "MinexxProo"         # <-- শুধু username ( @ ছাড়া )

# ==================== LOGGING =======================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ================== CONVERSATION STATES ==================

(
    CG_TITLE,
    CG_PRIZE,
    CG_TIME,
    CG_WINNERS,
    CG_VERIF_LINKS,
    CG_WINNER_MODE,
    CG_BAN_OLD_CHOICE,
    CG_OLD_WINNER_LIST,
    CG_RULES_CHOICE,
    CG_RULES_TEXT,
    CG_CHANNEL,
    CG_CONFIRM_POST,
) = range(12)


# ====================== HELPERS ======================

def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    প্রথমবার /start দিলে super admin auto set হবে।
    তারপর থেকে admin list থেকে চেক করবে।
    """
    user = update.effective_user
    bot_data = context.bot_data
    admins: Set[int] = bot_data.setdefault("admins", set())
    super_admin_id = bot_data.get("super_admin_id")

    if super_admin_id is None:
        # প্রথমবার বট চালু হচ্ছে, super admin set করব
        if user.username and user.username.lower() == SUPER_ADMIN_USERNAME.lower():
            bot_data["super_admin_id"] = user.id
            admins.add(user.id)
            return True
        else:
            return False

    # super admin already set, শুধু admin কিনা চেক
    return user.id in admins


def parse_duration_to_seconds(text: str) -> Optional[int]:
    """
    '10s', '10m', '10h', '1day', '3day' এই ফরম্যাট থেকে seconds বের করবে।
    """
    text = text.strip().lower()
    m = re.fullmatch(r"(\d+)(s|m|h|day|days)", text)
    if not m:
        return None
    value = int(m.group(1))
    unit = m.group(2)
    if unit == "s":
        return value
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    if unit in ("day", "days"):
        return value * 86400
    return None


def build_progress_bar(done: float) -> str:
    """
    0.0–1.0 থেকে 10টা block progress bar বানাবে।
    """
    done = max(0.0, min(1.0, done))
    total_blocks = 10
    filled = int(round(done * total_blocks))
    return "▰" * filled + "▱" * (total_blocks - filled)


def build_giveaway_text(g: Dict[str, Any], participants: int, time_left: Optional[int]) -> str:
    """
    Main giveaway post এর টেক্সট বানায়।
    """
    title = g.get("title", "")
    prize = g.get("prize", "")
    total_winners = g.get("winner_count", 0)
    winner_mode = g.get("winner_mode", "AUTO")
    old_winners_count = len(g.get("old_winners", set()))
    rules = g.get("rules")

    # time left string
    if time_left is None or time_left < 0:
        time_str = "Finished"
        progress = 1.0
    else:
        h = time_left // 3600
        m = (time_left % 3600) // 60
        s = time_left % 60
        time_str = f"{h:02d}h {m:02d}m {s:02d}s (BD TIME)"

        duration = g.get("duration_seconds", 1)
        progress = 1.0 - (time_left / float(duration))

    progress_bar = build_progress_bar(progress)
    progress_percent = int(progress * 100)

    lines = []

    lines.append("🎉 POWER POINT BREAK — OFFICIAL GIVEAWAY 🎉")
    lines.append("")
    lines.append(f"📌 Title: {title}")
    lines.append(f"🎁 Prize: {prize}")
    lines.append("")
    lines.append(f"🏆 Total Winners: {total_winners}")
    lines.append(f"🤖 Winner Mode: {winner_mode}")
    lines.append(f"👥 Participate Count: {participants}")
    lines.append("")
    lines.append(f"🚫 Old Winners Blocked: {old_winners_count} user(s)")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⏳ LIVE COUNTDOWN & PROGRESS")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"⏱ Time Left: {time_str}")
    lines.append("")
    lines.append("🎁 GIVEAWAY LOADING 💐")
    lines.append(f"{progress_bar} {progress_percent}%")
    lines.append("")
    if rules:
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("📜 GIVEAWAY RULES")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(rules)
        lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"📢 Hosted By: @PowerPointBreak")
    lines.append(f"👑 Admin: @{SUPER_ADMIN_USERNAME}")
    lines.append("")
    lines.append("💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐")

    return "\n".join(lines)


def sanitize_channel_input(text: str) -> str:
    """
    Channel link/username/id থেকে chat target বানায়।
    """
    text = text.strip()
    if text.startswith("@"):
        return text
    if "t.me/" in text:
        username = text.split("/")[-1]
        if username:
            if not username.startswith("@"):
                username = "@" + username
            return username
    # ধরি এটা ID
    return text


# ====================== HANDLERS ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_data = context.bot_data
    admins: Set[int] = bot_data.setdefault("admins", set())
    super_admin_id = bot_data.get("super_admin_id")

    text_lines = []

    if super_admin_id is None:
        # প্রথমবার super admin সেট করার চেষ্টা
        if user.username and user.username.lower() == SUPER_ADMIN_USERNAME.lower():
            bot_data["super_admin_id"] = user.id
            admins.add(user.id)
            text_lines.append("👑 You are set as SUPER ADMIN of this bot.")
        else:
            text_lines.append(
                f"⚠ This bot is not initialized.\n"
                f"Only @{SUPER_ADMIN_USERNAME} can initialize it by sending /start."
            )
            await update.message.reply_text("\n".join(text_lines))
            return
    else:
        if user.id in admins:
            text_lines.append("👋 Welcome back, Admin!")
        else:
            text_lines.append("👋 Hello!")
            text_lines.append("This is a private giveaway bot.")
            await update.message.reply_text("\n".join(text_lines))
            return

    text_lines.append("")
    text_lines.append("Use /newgiveaway to create a new giveaway.")
    text_lines.append("Use /panel for admin options (simple).")

    await update.message.reply_text("\n".join(text_lines))


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_admin(update, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ NEW GIVEAWAY", callback_data="panel_new")],
        [InlineKeyboardButton("🔄 BOT ON/OFF", callback_data="panel_toggle_bot")],
    ]
    await update.message.reply_text(
        "🛠️ SIMPLE ADMIN PANEL\n\n"
        "➕ New giveaway create করতে নিচের বাটন চাপুন।\n"
        "🔄 Bot ON/OFF control এখান থেকে করুন।",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not ensure_admin(update, context):
        await query.reply_text("⛔ You are not an admin.")
        return

    data = query.data
    if data == "panel_new":
        # panel থেকে newgiveaway শুরু
        await query.message.reply_text("Starting new giveaway setup…")
        return await new_giveaway_command(update, context)
    elif data == "panel_toggle_bot":
        bot_on = context.bot_data.get("bot_on", True)
        context.bot_data["bot_on"] = not bot_on
        status = "ON ✅" if context.bot_data["bot_on"] else "OFF ❌"
        await query.message.reply_text(f"Bot status changed to: {status}")


# ================= NEW GIVEAWAY CONVERSATION =================

async def new_giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return ConversationHandler.END

    context.user_data["new_giveaway"] = {
        "title": "",
        "prize": "",
        "duration_seconds": 0,
        "winner_count": 0,
        "verif_links": [],
        "winner_mode": "AUTO",
        "old_winners": set(),
        "rules": "",
        "channel": "",
    }

    await update.message.reply_text("📝 SET YOUR GIVEAWAY TITLE:")
    return CG_TITLE


async def cg_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    g["title"] = update.message.text.strip()
    await update.message.reply_text(
        "🎁 NOW SET THE PRIZE:\n\nExample: ChatGPT Plus Premium Full Access"
    )
    return CG_PRIZE


async def cg_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    g["prize"] = update.message.text.strip()
    await update.message.reply_text(
        "⏳ NOW SET THE TIME (BD TIME ZONE)\n\n"
        "Use:\n10s / 10m / 10h / 1day / 3day"
    )
    return CG_TIME


async def cg_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    seconds = parse_duration_to_seconds(update.message.text)
    if seconds is None or seconds <= 0:
        await update.message.reply_text(
            "❌ Invalid time format.\nUse like: 10m / 2h / 1day"
        )
        return CG_TIME
    g["duration_seconds"] = seconds
    await update.message.reply_text("🏆 Send total winners (1–100000):")
    return CG_WINNERS


async def cg_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    try:
        count = int(update.message.text.strip())
        if count < 1 or count > 100000:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Please send a number between 1 and 100000.")
        return CG_WINNERS
    g["winner_count"] = count
    await update.message.reply_text(
        "🔗 Send verification links (one per message).\n"
        "Send DONE when finished.\nSend SKIP to disable."
    )
    g["verif_links"] = []
    return CG_VERIF_LINKS


async def cg_verif_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    text = update.message.text.strip()
    if text.upper() == "DONE":
        await update.message.reply_text("🤖 Winner mode? (Only AUTO supported)\nSend: AUTO")
        return CG_WINNER_MODE
    if text.upper() == "SKIP":
        g["verif_links"] = []
        await update.message.reply_text("🤖 Winner mode? (Only AUTO supported)\nSend: AUTO")
        return CG_WINNER_MODE

    g["verif_links"].append(text)
    await update.message.reply_text(
        "Link saved. Send another, or DONE / SKIP."
    )
    return CG_VERIF_LINKS


async def cg_winner_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    mode = update.message.text.strip().upper()
    if mode != "AUTO":
        await update.message.reply_text(
            "❌ This version only supports AUTO mode.\nPlease send: AUTO"
        )
        return CG_WINNER_MODE
    g["winner_mode"] = "AUTO"
    await update.message.reply_text(
        "🚫 Do you want to block OLD winners?\nSend BAN or SKIP."
    )
    return CG_BAN_OLD_CHOICE


async def cg_ban_old_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    choice = update.message.text.strip().upper()
    if choice == "BAN":
        g["old_winners"] = set()
        await update.message.reply_text(
            "Send old winner list in format:\n@Username/UserID\n"
            "One per line. Send DONE when finished."
        )
        return CG_OLD_WINNER_LIST
    elif choice == "SKIP":
        g["old_winners"] = set()
        # go to rules
        await update.message.reply_text(
            "📜 Do you want to add giveaway rules?\nSend ADD or SKIP."
        )
        return CG_RULES_CHOICE
    else:
        await update.message.reply_text("❌ Send BAN or SKIP.")
        return CG_BAN_OLD_CHOICE


async def cg_old_winner_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    text = update.message.text.strip()
    if text.upper() == "DONE":
        await update.message.reply_text(
            "📜 Do you want to add giveaway rules?\nSend ADD or SKIP."
        )
        return CG_RULES_CHOICE

    # format: @User/12345  (username optional)
    parts = text.split("/")
    if len(parts) == 2:
        username = parts[0].strip().lstrip("@").lower()
        try:
            uid = int(parts[1].strip())
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid format. Use: @Username/UserID\nor send DONE."
            )
            return CG_OLD_WINNER_LIST
        g["old_winners"].add((username, uid))
        await update.message.reply_text("Saved. Send another or DONE.")
    else:
        await update.message.reply_text(
            "❌ Invalid format. Use: @Username/UserID\nor send DONE."
        )
    return CG_OLD_WINNER_LIST


async def cg_rules_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    choice = update.message.text.strip().upper()
    if choice == "ADD":
        await update.message.reply_text(
            "Send your giveaway rules as ONE message.\n"
            "Example:\n1) Must join channels\n2) No fake users\n3) Contact admin within 24 hours"
        )
        return CG_RULES_TEXT
    elif choice == "SKIP":
        g["rules"] = ""
        await update.message.reply_text(
            "📌 FINAL STEP: SEND YOUR MAIN CHANNEL link / @username / id"
        )
        return CG_CHANNEL
    else:
        await update.message.reply_text("❌ Send ADD or SKIP.")
        return CG_RULES_CHOICE


async def cg_rules_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    g["rules"] = update.message.text.strip()
    await update.message.reply_text(
        "📌 FINAL STEP: SEND YOUR MAIN CHANNEL link / @username / id"
    )
    return CG_CHANNEL


async def cg_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    g["channel"] = sanitize_channel_input(update.message.text)
    # show final preview
    preview_text = build_giveaway_text(g, participants=0, time_left=g["duration_seconds"])
    await update.message.reply_text(
        "Here is the preview of your giveaway:\n\n" + preview_text
    )
    await update.message.reply_text(
        f"Channel set to: {g['channel']}\n\n"
        "Send YES to post the giveaway.\n"
        "Or send CANCEL to abort."
    )
    return CG_CONFIRM_POST


async def cg_confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    g = context.user_data["new_giveaway"]

    if text == "CANCEL":
        await update.message.reply_text("❌ Giveaway creation cancelled.")
        context.user_data.pop("new_giveaway", None)
        return ConversationHandler.END

    if text != "YES":
        await update.message.reply_text("Please send YES to post or CANCEL to abort.")
        return CG_CONFIRM_POST

    # post to channel
    application = context.application
    try:
        channel = g["channel"]
        giveaway_text = build_giveaway_text(g, participants=0, time_left=g["duration_seconds"])
        keyboard = [
            [InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]
        ]
        msg = await application.bot.send_message(
            chat_id=channel,
            text=giveaway_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.exception("Failed to post giveaway")
        await update.message.reply_text(f"❌ Failed to post giveaway:\n{e}")
        return ConversationHandler.END

    # save current giveaway globally
    bot_data = context.bot_data
    bot_data["current_giveaway"] = {
        "title": g["title"],
        "prize": g["prize"],
        "duration_seconds": g["duration_seconds"],
        "winner_count": g["winner_count"],
        "verif_links": g["verif_links"],
        "winner_mode": "AUTO",
        "old_winners": g["old_winners"],
        "rules": g["rules"],
        "channel": channel,
        "message_id": msg.message_id,
        "participants": {},  # user_id -> {"username": str}
        "start_time": datetime.now(timezone.utc),
        "end_time": datetime.now(timezone.utc) + timedelta(seconds=g["duration_seconds"]),
        "status": "running",
    }

    await update.message.reply_text("✅ Giveaway posted and started!")

    # schedule countdown job (update every 5 seconds)
    job_queue = application.job_queue
    job_queue.run_repeating(
        countdown_job,
        interval=5,
        first=5,
        name="giveaway_countdown",
    )

    context.user_data.pop("new_giveaway", None)
    return ConversationHandler.END


# =================== JOIN HANDLER ===================

async def join_giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    bot_data = context.bot_data

    giveaway = bot_data.get("current_giveaway")
    if not giveaway or giveaway.get("status") != "running":
        await query.reply_text("⚠️ No active giveaway right now.")
        return

    # old winner check
    old_winners = giveaway.get("old_winners", set())
    username_key = (user.username or "").lower()
    for uname, uid in old_winners:
        if uid == user.id or (uname and uname == username_key):
            await query.reply_text(
                "😔 Oops! You have already won a previous giveaway.\n"
                "You cannot participate again."
            )
            return

    # verification links check (simple: just info; real join-check করা risky, তাই skip করছি)
    # চাইলে এখানে get_chat_member দিয়ে বাস্তব join check যোগ করা যাবে।

    participants: Dict[int, Dict[str, Any]] = giveaway.setdefault("participants", {})
    if user.id in participants:
        await query.reply_text("⚠️ You have already joined this giveaway.")
        return

    participants[user.id] = {"username": user.username or ""}

    await query.reply_text("🎉 You successfully joined the giveaway!\nGood luck! 🍀")

    # update main post participate count
    try:
        channel = giveaway["channel"]
        msg_id = giveaway["message_id"]
        duration = giveaway["duration_seconds"]
        now = datetime.now(timezone.utc)
        time_left = int((giveaway["end_time"] - now).total_seconds())
        new_text = build_giveaway_text(
            giveaway,
            participants=len(participants),
            time_left=time_left,
        )
        keyboard = [
            [InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]
        ]
        await context.bot.edit_message_text(
            chat_id=channel,
            message_id=msg_id,
            text=new_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        logger.exception("Failed to update message after join")


# =================== COUNTDOWN JOB ===================

async def countdown_job(context):
    bot_data = context.application.bot_data
    giveaway = bot_data.get("current_giveaway")
    if not giveaway or giveaway.get("status") != "running":
        job = context.job
        if job:
            job.schedule_removal()
        return

    channel = giveaway["channel"]
    msg_id = giveaway["message_id"]
    duration = giveaway["duration_seconds"]
    participants = giveaway.get("participants", {})

    now = datetime.now(timezone.utc)
    time_left = int((giveaway["end_time"] - now).total_seconds())

    if time_left <= 0:
        # time over -> choose winners and close
        giveaway["status"] = "finished"

        # pick winners
        user_ids = list(participants.keys())
        winner_count = min(giveaway["winner_count"], len(user_ids))
        winners: List[int] = random.sample(user_ids, winner_count) if winner_count > 0 else []

        # edit main post final time
        final_text = build_giveaway_text(
            giveaway,
            participants=len(participants),
            time_left=0,
        )
        keyboard = [
            [InlineKeyboardButton("🎁 GIVEAWAY ENDED", callback_data="no_action")]
        ]
        try:
            await context.bot.edit_message_text(
                chat_id=channel,
                message_id=msg_id,
                text=final_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception:
            logger.exception("Failed to edit message at end")

        # announce winners in channel
        if winners:
            lines = []
            lines.append("🏆 WINNER ANNOUNCEMENT 🎉")
            lines.append("")
            lines.append(f"🎁 Prize: {giveaway['prize']}")
            lines.append(f"🏆 Total Winners: {len(winners)}")
            lines.append("")
            for i, uid in enumerate(winners, start=1):
                uname = participants[uid].get("username") or "(no username)"
                if uname != "(no username)":
                    lines.append(f"{i}) @{uname}")
                else:
                    lines.append(f"{i}) ID: {uid}")
            lines.append("")
            lines.append(f"👑 Admin: @{SUPER_ADMIN_USERNAME}")
            try:
                await context.bot.send_message(chat_id=channel, text="\n".join(lines))
            except Exception:
                logger.exception("Failed to send winner announcement")

            # DM winners
            for uid in winners:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=(
                            "🎉 CONGRATULATIONS! 🎉\n"
                            "You are one of the winners of our giveaway! 🏆\n\n"
                            f"📩 Contact Admin: @{SUPER_ADMIN_USERNAME}"
                        ),
                    )
                except Exception:
                    logger.exception("Failed to DM winner")

        # end job
        job = context.job
        if job:
            job.schedule_removal()
        return

    # still running -> update message
    try:
        text = build_giveaway_text(
            giveaway,
            participants=len(participants),
            time_left=time_left,
        )
        keyboard = [
            [InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]
        ]
        await context.bot.edit_message_text(
            chat_id=channel,
            message_id=msg_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception:
        logger.exception("Failed to update countdown message")


# =================== MISC HANDLERS ===================

async def no_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # just to handle old button presses
    await update.callback_query.answer("Giveaway ended.")


# ====================== MAIN ======================

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))

    # simple panel callbacks
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel_"))

    # join button
    app.add_handler(CallbackQueryHandler(join_giveaway_callback, pattern="^join_giveaway$"))
    app.add_handler(CallbackQueryHandler(no_action_callback, pattern="^no_action$"))

    # new giveaway conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("newgiveaway", new_giveaway_command)],
        states={
            CG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_title)],
            CG_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_prize)],
            CG_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_time)],
            CG_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winners)],
            CG_VERIF_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_verif_links)],
            CG_WINNER_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winner_mode)],
            CG_BAN_OLD_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_ban_old_choice)],
            CG_OLD_WINNER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_old_winner_list)],
            CG_RULES_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_rules_choice)],
            CG_RULES_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_rules_text)],
            CG_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_channel)],
            CG_CONFIRM_POST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_confirm_post)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    app.add_handler(conv)

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
