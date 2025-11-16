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

BOT_TOKEN = "8385717982:AAHhfJj9pWKTL6YG1WEEk8PPN2RKzYPwDzA"       # <-- এখানে তোমার BotFather টোকেন দাও
SUPER_ADMIN_USERNAME = "MinexxProo"         # <-- শুধু username ( @ ছাড়া )

# Rotating icon frames for animated title
ROTATE_FRAMES = ["✨", "✧", "✦", "✺"]

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
    CG_SPEED,
    CG_WINNERS,
    CG_VERIF_LINKS,
    CG_WINNER_MODE,
    CG_BAN_OLD_CHOICE,
    CG_OLD_WINNER_LIST,
    CG_RULES_CHOICE,
    CG_RULES_TEXT,
    CG_CHANNEL,
    CG_CONFIRM_POST,
) = range(13)

# ====================== HELPERS ======================

def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    প্রথমবার SUPER_ADMIN_USERNAME দিয়ে super admin set হয়।
    তার পর admins সেটে যাদের ID আছে, তারা সবাই admin।
    """
    user = update.effective_user
    if user is None:
        return False

    bot_data = context.bot_data
    admins: Set[int] = bot_data.setdefault("admins", set())
    super_admin_id = bot_data.get("super_admin_id")

    # আগেই admin লিস্টে থাকলে সরাসরি admin
    if user.id in admins:
        return True

    # এখনো super admin সেট হয়নি, আর username config এর সাথে মিলে গেলে → super admin বানাও
    if (
        super_admin_id is None
        and user.username
        and user.username.lower() == SUPER_ADMIN_USERNAME.lower()
    ):
        bot_data["super_admin_id"] = user.id
        admins.add(user.id)
        return True

    return False


def is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    admins = context.bot_data.get("admins", set())
    return user_id in admins


def bot_is_on(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.bot_data.get("bot_on", True)


def parse_duration_to_seconds(text: str) -> Optional[int]:
    """
    '10s', '10m', '10h', '1day', '3day' ইত্যাদি থেকে seconds বের করে।
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
    done = max(0.0, min(1.0, done))
    total_blocks = 10
    filled = int(round(done * total_blocks))
    return "▰" * filled + "▱" * (total_blocks - filled)


def build_giveaway_text(
    g: Dict[str, Any],
    participants: int,
    time_left: Optional[int],
    icon: Optional[str],
) -> str:
    title = g.get("title", "")
    prize = g.get("prize", "")
    total_winners = g.get("winner_count", 0)
    winner_mode = g.get("winner_mode", "AUTO")
    old_winners_count = len(g.get("old_winners", set()))
    rules = g.get("rules", "")

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

    lines: List[str] = []

    # ---- TOP BLOCK (with rotating icon) ----
    if icon:
        lines.append(f"{icon} POWER POINT BREAK — OFFICIAL GIVEAWAY {icon}")
    else:
        lines.append("POWER POINT BREAK — OFFICIAL GIVEAWAY")
    lines.append("")

    lines.append(f"📌 Title: {title}")
    lines.append("")
    lines.append(f"🎁 Prize: {prize}")
    lines.append("")
    lines.append(f"🏆 Total Winners: {total_winners}")
    lines.append(f"🤖 Winner Mode: {winner_mode}")
    lines.append(f"👥 Participate Count: {participants}")
    lines.append(f"🚫 Old Winners Blocked: {old_winners_count} user(s)")
    lines.append("")

    # ---- COUNTDOWN BLOCK ----
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⏳ LIVE COUNTDOWN & PROGRESS")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"⏱ Time Left: {time_str}")
    lines.append("")
    lines.append("🎁 POWER POINT BREAK — GIVEAWAY LOADING 💐")
    lines.append(f"{progress_bar} {progress_percent}%")
    lines.append("")

    # ---- RULES (optional) ----
    if rules:
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("📜 RULES")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("")
        lines.append(rules)
        lines.append("")

    # ---- FOOTER ----
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📢 Hosted By : Power Point Break")
    lines.append(f"👑 Admin     : @{SUPER_ADMIN_USERNAME}")
    lines.append("")
    lines.append("💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐")
    lines.append("[ 🎁 JOIN GIVEAWAY ]")

    return "\n".join(lines)


def build_winner_announcement_text(
    g: Dict[str, Any],
    winners: List[int],
    participants: Dict[int, Dict[str, Any]],
) -> str:
    title = g.get("title", "")
    lines: List[str] = []
    lines.append("┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    lines.append("🎉 POWERPOINTBREAK — GIVEAWAY WINNER ANNOUNCED 🎉")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    lines.append("")
    lines.append("📌 Giveaway Title:")
    lines.append(title or "N/A")
    lines.append("")
    if winners:
        lines.append("🏆 Official Winners List:")
        lines.append("")
        for i, uid in enumerate(winners, start=1):
            info = participants.get(uid, {})
            uname = info.get("username") or ""
            if uname:
                lines.append(f"{i}) @{uname} / {uid}")
            else:
                lines.append(f"{i}) ID: {uid}")
        lines.append("")
    else:
        lines.append("😔 No valid participants, no winners could be selected.")
        lines.append("")
    lines.append("📢 Hosted By : Power Point Break")
    lines.append(f"👑 Admin     : @{SUPER_ADMIN_USERNAME}")
    return "\n".join(lines)


def sanitize_channel_input(text: str) -> str:
    text = text.strip()
    if text.startswith("@"):
        return text
    if "t.me/" in text:
        username = text.split("/")[-1]
        if username:
            if not username.startswith("@"):
                username = "@" + username
            return username
    return text  # ধরে নিলাম ID বা username


def sanitize_verification_chat(text: str) -> str:
    """
    Verification link থেকে chat reference বানায়।
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
    return text


# ====================== HANDLERS: /start, /panel ======================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    # bot OFF থাকলে, admin ছাড়া কাউকে allow করবে না
    if not bot_is_on(context) and not is_admin(user.id, context):
        # admin ke notify korbo
        super_admin_id = context.bot_data.get("super_admin_id")
        if super_admin_id:
            try:
                await context.bot.send_message(
                    chat_id=super_admin_id,
                    text=(
                        "⚠️ BOT OFF MODE — USER TRIED TO START\n\n"
                        f"Username: @{user.username or 'N/A'}\n"
                        f"UserID: {user.id}"
                    ),
                )
            except Exception:
                logger.exception("Failed to notify admin about OFF-mode start")

        await update.message.reply_text(
            f"Hi Dear @{user.username or user.id}\n"
            f"UserID: {user.id}\n\n"
            "This is the Power Point Break Giveaway Bot.\n"
            "No one except the authorized admin can use this bot right now.\n\n"
            "For any concerns or support, please contact the admin:\n"
            f"👉 @{SUPER_ADMIN_USERNAME}"
        )
        return

    bot_data = context.bot_data
    admins: Set[int] = bot_data.setdefault("admins", set())
    super_admin_id = bot_data.get("super_admin_id")

    text_lines: List[str] = []

    if super_admin_id is None:
        # প্রথমবার setup
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
    text_lines.append("Use /panel to see all admin commands.")
    text_lines.append("Use /newgiveaway to create a new giveaway.")

    await update.message.reply_text("\n".join(text_lines))


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not ensure_admin(update, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    text = (
        "🛠 POWER POINT BREAK — ADMIN PANEL\n\n"
        "📜 ALL ADMIN COMMANDS:\n"
        "--------------------------------\n"
        "/start        - Open Admin Panel\n"
        "/panel        - Show this admin panel\n"
        "/newgiveaway  - Create a new giveaway\n"
        "/off          - Turn the bot OFF\n"
        "/on           - Turn the bot ON\n"
        "/addadmin ID  - Add a new admin\n"
        "/removeadmin ID - Remove an admin\n"
        "/realp        - Show real participants\n"
        "/approve      - Approve winners & publish\n"
        "/reject       - Reject winners & cancel\n"
        "/cancel       - Cancel current setup\n"
        "--------------------------------\n\n"
        "Shortcut buttons:\n👇"
    )

    keyboard = [
        [InlineKeyboardButton("➕ NEW GIVEAWAY", callback_data="panel_new")],
        [InlineKeyboardButton("🔄 BOT ON/OFF", callback_data="panel_toggle_bot")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not ensure_admin(update, context):
        await query.message.reply_text("⛔ You are not an admin.")
        return

    data = query.data
    if data == "panel_new":
        await query.message.reply_text(
            "📝 To start a new giveaway, please type:\n/newgiveaway"
        )
    elif data == "panel_toggle_bot":
        bot_on = bot_is_on(context)
        context.bot_data["bot_on"] = not bot_on
        status = "ON ✅" if context.bot_data["bot_on"] else "OFF ❌"
        await query.message.reply_text(f"Bot status changed to: {status}")

  # =================== NEW GIVEAWAY CONVERSATION ===================

async def new_giveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return ConversationHandler.END

    context.user_data["new_giveaway"] = {
        "title": "",
        "prize": "",
        "duration_seconds": 0,
        "interval_seconds": 3,
        "winner_count": 0,
        "verif_links": [],
        "verif_chats": [],
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
        "⏳ NOW SET YOUR GIVEAWAY TIME (BD TIME)\n\n"
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
    await update.message.reply_text(
        "⏳ Time Saved!\n\n"
        "Now choose countdown speed:\n"
        "FAST   = 1 second update\n"
        "NORMAL = 3 second update\n"
        "SLOW   = 5 second update\n\n"
        "Send: FAST / NORMAL / SLOW"
    )
    return CG_SPEED


async def cg_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    choice = update.message.text.strip().upper()
    if choice == "FAST":
        g["interval_seconds"] = 1
    elif choice == "NORMAL":
        g["interval_seconds"] = 3
    elif choice == "SLOW":
        g["interval_seconds"] = 5
    else:
        await update.message.reply_text(
            "❌ Invalid choice.\nSend FAST, NORMAL or SLOW."
        )
        return CG_SPEED

    await update.message.reply_text("🏆 NOW SET TOTAL WINNERS (1–100000):")
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
        "🔗 NOW SET YOUR VERIFICATION LINKS\n\n"
        "Send each link in a new message.\n"
        "Type DONE when finished.\n"
        "Type SKIP to disable verification."
    )
    g["verif_links"] = []
    g["verif_chats"] = []
    return CG_VERIF_LINKS


async def cg_verif_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    text = update.message.text.strip()
    if text.upper() == "DONE":
        await update.message.reply_text(
            "🤖 Winner mode? (This version supports only AUTO)\nSend: AUTO"
        )
        return CG_WINNER_MODE
    if text.upper() == "SKIP":
        g["verif_links"] = []
        g["verif_chats"] = []
        await update.message.reply_text(
            "🤖 Winner mode? (This version supports only AUTO)\nSend: AUTO"
        )
        return CG_WINNER_MODE

    g["verif_links"].append(text)
    g["verif_chats"].append(sanitize_verification_chat(text))
    await update.message.reply_text(
        "✔ Link saved. Send another, or DONE / SKIP."
    )
    return CG_VERIF_LINKS


async def cg_winner_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    mode = update.message.text.strip().upper()
    if mode != "AUTO":
        await update.message.reply_text(
            "❌ Only AUTO mode supported.\nPlease send: AUTO"
        )
        return CG_WINNER_MODE
    g["winner_mode"] = "AUTO"
    await update.message.reply_text(
        "🚫 Do you want to BAN OLD WINNERS?\nSend: BAN or SKIP."
    )
    return CG_BAN_OLD_CHOICE


async def cg_ban_old_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data["new_giveaway"]
    choice = update.message.text.strip().upper()
    if choice == "BAN":
        g["old_winners"] = set()
        await update.message.reply_text(
            "Send OLD winners list:\n\n"
            "Format:\n@Username/UserID\n\n"
            "Example:\n@User/123456\n\n"
            "Send ALL, then type: DONE"
        )
        return CG_OLD_WINNER_LIST
    elif choice == "SKIP":
        g["old_winners"] = set()
        await update.message.reply_text(
            "📜 Do you want to add RULES?\nSend: ADD or SKIP."
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
            "📜 Do you want to add RULES?\nSend: ADD or SKIP."
        )
        return CG_RULES_CHOICE

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
        await update.message.reply_text("✔ Saved. Send another or DONE.")
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
            "Example:\n"
            "Must be active.\n"
            "Fake accounts not allowed."
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
    preview_text = build_giveaway_text(
        g,
        participants=0,
        time_left=g["duration_seconds"],
        icon=ROTATE_FRAMES[0],
    )
    await update.message.reply_text(
        "Here is the preview of your Giveaway:\n\n" + preview_text
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

    app = context.application
    try:
        channel = g["channel"]
        giveaway_text = build_giveaway_text(
            g,
            participants=0,
            time_left=g["duration_seconds"],
            icon=ROTATE_FRAMES[0],
        )
        keyboard = [
            [InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]
        ]
        msg = await app.bot.send_message(
            chat_id=channel,
            text=giveaway_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        logger.exception("Failed to post giveaway")
        await update.message.reply_text(f"❌ Failed to post giveaway:\n{e}")
        return ConversationHandler.END

    bot_data = context.bot_data
    bot_data["current_giveaway"] = {
        "title": g["title"],
        "prize": g["prize"],
        "duration_seconds": g["duration_seconds"],
        "interval_seconds": g["interval_seconds"],
        "winner_count": g["winner_count"],
        "verif_links": g["verif_links"],
        "verif_chats": g["verif_chats"],
        "winner_mode": "AUTO",
        "old_winners": g["old_winners"],
        "rules": g["rules"],
        "channel": channel,
        "message_id": msg.message_id,
        "participants": {},  # user_id -> {"username": str}
        "start_time": datetime.now(timezone.utc),
        "end_time": datetime.now(timezone.utc) + timedelta(seconds=g["duration_seconds"]),
        "status": "running",
        "winners": [],
    }

    # reset rotating icon frame
    bot_data["frame_index"] = 0

    await update.message.reply_text("✅ Giveaway posted and started!")

    job_queue = app.job_queue
    job_queue.run_repeating(
        countdown_job,
        interval=g["interval_seconds"],
        first=g["interval_seconds"],
        name="giveaway_countdown",
    )

    context.user_data.pop("new_giveaway", None)
    return ConversationHandler.END


# =================== JOIN HANDLER ===================

async def join_giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if not bot_is_on(context):
        await query.reply_text(
            "🔴 Bot is currently OFF.\nPlease contact the admin: "
            f"@{SUPER_ADMIN_USERNAME}"
        )
        return

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
                "😔 Oops! You have already won a giveaway before,\n"
                "so you can no longer participate, dear member.\n\n"
                "🎉 Thanks for joining!\n\n"
                "🍀 Try again — more giveaways coming soon!\n"
                "💙 Stay with Power Point Break!\n\n"
                f"📞 For support:\n👉 @{SUPER_ADMIN_USERNAME}"
            )
            # admin alert for old winner
            super_admin_id = context.bot_data.get("super_admin_id")
            if super_admin_id:
                try:
                    await context.bot.send_message(
                        chat_id=super_admin_id,
                        text=(
                            "⚠️ Old Winner Tried to Join!\n\n"
                            f"Username: @{user.username or 'N/A'}\n"
                            f"UserID: {user.id}\n\n"
                            "Action Blocked Successfully."
                        ),
                    )
                except Exception:
                    logger.exception("Failed to notify admin about old winner join")
            return

    # verification check (best-effort)
    verif_chats = giveaway.get("verif_chats", [])
    verif_links = giveaway.get("verif_links", [])
    if verif_chats:
        not_joined: List[str] = []
        for link, chat_ref in zip(verif_links, verif_chats):
            try:
                member = await context.bot.get_chat_member(chat_ref, user.id)
                status = getattr(member, "status", "")
                if status in ("left", "kicked"):
                    not_joined.append(link)
            except Exception:
                not_joined.append(link)
        if not_joined:
            text_lines = []
            text_lines.append("⛔ ACCESS DENIED — VERIFICATION FAILED ⛔")
            text_lines.append("")
            text_lines.append("You must join ALL required channels before participating:")
            text_lines.append("")
            for i, link in enumerate(not_joined, start=1):
                text_lines.append(f"{i}) {link}")
            text_lines.append("")
            text_lines.append("✔️ After joining all channels, try again!")
            await query.reply_text("\n".join(text_lines))
            return

    participants: Dict[int, Dict[str, Any]] = giveaway.setdefault("participants", {})
    if user.id in participants:
        await query.reply_text(
            "⚠️❌ WARNING — DUPLICATE ENTRY ❌⚠️\n\n"
            "You already participated!\n"
            "Winner list will be published soon…"
        )
        return

    participants[user.id] = {"username": user.username or ""}

    await query.reply_text(
        "🎉 You successfully joined the giveaway!\n"
        "Good luck! 🍀"
    )

    # notify admin about new participant
    super_admin_id = context.bot_data.get("super_admin_id")
    if super_admin_id:
        try:
            await context.bot.send_message(
                chat_id=super_admin_id,
                text=(
                    "👤 NEW PARTICIPANT JOINED THE GIVEAWAY\n\n"
                    f"Username: @{user.username or 'N/A'}\n"
                    f"UserID: {user.id}"
                ),
            )
        except Exception:
            logger.exception("Failed to notify admin about new participant")

    # main post update
    try:
        channel = giveaway["channel"]
        msg_id = giveaway["message_id"]
        now = datetime.now(timezone.utc)
        time_left = int((giveaway["end_time"] - now).total_seconds())
        frame_index = context.bot_data.get("frame_index", 0)
        icon = ROTATE_FRAMES[frame_index % len(ROTATE_FRAMES)]
        new_text = build_giveaway_text(
            giveaway,
            participants=len(participants),
            time_left=time_left,
            icon=icon if time_left > 0 and giveaway.get("status") == "running" else None,
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

async def countdown_job(context: ContextTypes.DEFAULT_TYPE):
    bot_data = context.application.bot_data
    giveaway = bot_data.get("current_giveaway")
    if not giveaway or giveaway.get("status") != "running":
        job = context.job
        if job:
            job.schedule_removal()
        return

    channel = giveaway["channel"]
    msg_id = giveaway["message_id"]
    participants = giveaway.get("participants", {})

    now = datetime.now(timezone.utc)
    time_left = int((giveaway["end_time"] - now).total_seconds())

    if time_left <= 0:
        # stop rotating icon
        bot_data["frame_index"] = 0

        # select winners
        user_ids = list(participants.keys())
        winner_count = min(giveaway["winner_count"], len(user_ids))
        winners: List[int] = (
            random.sample(user_ids, winner_count) if winner_count > 0 else []
        )
        giveaway["winners"] = winners
        giveaway["status"] = "waiting_approval"

        # edit main post to show closed
        try:
            closed_text = build_giveaway_text(
                giveaway,
                participants=len(participants),
                time_left=0,
                icon=None,  # now static, no rotating icon
            )
            keyboard = [
                [InlineKeyboardButton("🎁 GIVEAWAY ENDED", callback_data="no_action")]
            ]
            await context.bot.edit_message_text(
                chat_id=channel,
                message_id=msg_id,
                text=closed_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception:
            logger.exception("Failed to edit message at end")

        # send approval request to super admin (if set)
        super_admin_id = bot_data.get("super_admin_id")
        if super_admin_id:
            try:
                preview = build_winner_announcement_text(
                    giveaway,
                    winners,
                    participants,
                )
                await context.bot.send_message(
                    chat_id=super_admin_id,
                    text=(
                        f"🔍 {len(winners)} Winners have been selected for:\n\n"
                        f"{giveaway.get('title','')}\n\n"
                        "Preview of Winner Post:\n\n"
                        f"{preview}\n\n"
                        "Do you want to publish this?\n\n"
                        "Send /approve to publish winners,\n"
                        "or /reject to cancel."
                    ),
                )
            except Exception:
                logger.exception("Failed to send approval request to admin")

        job = context.job
        if job:
            job.schedule_removal()
        return

    # still running → rotate icon and update message
    try:
        frame_index = bot_data.get("frame_index", 0)
        frame_index = (frame_index + 1) % len(ROTATE_FRAMES)
        bot_data["frame_index"] = frame_index
        icon = ROTATE_FRAMES[frame_index]

        text = build_giveaway_text(
            giveaway,
            participants=len(participants),
            time_left=time_left,
            icon=icon,
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


# =================== APPROVE / REJECT ===================

async def approve_winners_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or not is_admin(user.id, context):
        await update.message.reply_text("⛔ You are not allowed to approve winners.")
        return

    bot_data = context.bot_data
    giveaway = bot_data.get("current_giveaway")
    if not giveaway or giveaway.get("status") != "waiting_approval":
        await update.message.reply_text("⚠️ There is no giveaway waiting for approval.")
        return

    winners: List[int] = giveaway.get("winners", [])
    participants: Dict[int, Dict[str, Any]] = giveaway.get("participants", {})

    if not winners:
        await update.message.reply_text("😔 No winners to approve (no participants).")
        giveaway["status"] = "finished"
        return

    # 1) Post winner announcement to channel
    channel = giveaway["channel"]
    announcement = build_winner_announcement_text(giveaway, winners, participants)
    try:
        await context.bot.send_message(chat_id=channel, text=announcement)
    except Exception:
        logger.exception("Failed to send winner announcement")

    # 2) DM each winner
    for uid in winners:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "🎉 CONGRATULATIONS! 🎉\n"
                    "You are one of the WINNERS of our Giveaway! 🏆\n\n"
                    f"📩 Contact Admin to claim your reward:\n👉 @{SUPER_ADMIN_USERNAME}"
                ),
            )
        except Exception:
            logger.exception("Failed to DM winner")

    # 3) Optional closing message
    try:
        await context.bot.send_message(
            chat_id=channel,
            text=(
                "⛔️❌ GIVEAWAY CLOSED ❌⛔️\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "📩 Need assistance?\n"
                f"👉 @{SUPER_ADMIN_USERNAME}\n\n"
                "💫 Try your luck in the next giveaway!\n"
                "❤️ Best wishes ❤️\n"
                "━━━━━━━━━━━━━━━━━━━━━━━"
            ),
        )
    except Exception:
        logger.exception("Failed to send closing message")

    giveaway["status"] = "finished"
    await update.message.reply_text("✅ Winners approved and published.")


async def reject_winners_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or not is_admin(user.id, context):
        await update.message.reply_text("⛔ You are not allowed to reject winners.")
        return

    bot_data = context.bot_data
    giveaway = bot_data.get("current_giveaway")
    if not giveaway or giveaway.get("status") != "waiting_approval":
        await update.message.reply_text("⚠️ There is no giveaway waiting for approval.")
        return

    giveaway["status"] = "cancelled"

    channel = giveaway["channel"]
    try:
        await context.bot.send_message(
            chat_id=channel,
            text=(
                "❌ Giveaway winner announcement was cancelled by admin.\n"
                "The giveaway has been closed without published winners."
            ),
        )
    except Exception:
        logger.exception("Failed to send cancellation message to channel")

    await update.message.reply_text("❌ Winners rejected and announcement cancelled.")

# =================== EXTRA ADMIN COMMANDS ===================

async def turn_bot_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or not is_admin(user.id, context):
        await update.message.reply_text("⛔ You are not allowed to turn the bot OFF.")
        return
    context.bot_data["bot_on"] = False
    await update.message.reply_text(
        "🔴 Bot has been turned OFF.\nOnly admins can use commands now."
    )


async def turn_bot_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or not is_admin(user.id, context):
        await update.message.reply_text("⛔ You are not allowed to turn the bot ON.")
        return
    context.bot_data["bot_on"] = True
    await update.message.reply_text(
        "🟢 Bot is now ON.\nAll functions are active."
    )


async def add_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or not is_admin(user.id, context):
        await update.message.reply_text("⛔ Only admins can add another admin.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addadmin <user_id>\n\nExample:\n/addadmin 123456789"
        )
        return

    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Please send numeric user_id.")
        return

    admins: Set[int] = context.bot_data.setdefault("admins", set())
    admins.add(new_id)
    await update.message.reply_text(f"✅ Added new admin with ID: {new_id}")


async def remove_admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user is None or not is_admin(user.id, context):
        await update.message.reply_text("⛔ Only admins can remove another admin.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/removeadmin <user_id>\n\nExample:\n/removeadmin 123456789"
        )
        return

    try:
        rm_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Please send numeric user_id.")
        return

    admins: Set[int] = context.bot_data.setdefault("admins", set())
    if rm_id in admins:
        admins.remove(rm_id)
        await update.message.reply_text(f"✅ Removed admin with ID: {rm_id}")
    else:
        await update.message.reply_text("ID not found in admin list.")


async def real_participants_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    giveaway = context.bot_data.get("current_giveaway")
    if not giveaway:
        await update.message.reply_text("⚠️ No active giveaway.")
        return

    participants = giveaway.get("participants", {})
    if not participants:
        await update.message.reply_text("😔 No real participants yet.")
        return

    lines: List[str] = ["👥 REAL PARTICIPANTS:"]
    for uid, info in participants.items():
        uname = info.get("username") or "(no username)"
        if uname != "(no username)":
            lines.append(f"- @{uname} / {uid}")
        else:
            lines.append(f"- ID: {uid}")
    await update.message.reply_text("\n".join(lines))


async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END


async def no_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Giveaway ended.")


# ====================== MAIN ======================

def main() -> None:
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("off", turn_bot_off))
    app.add_handler(CommandHandler("on", turn_bot_on))
    app.add_handler(CommandHandler("addadmin", add_admin_cmd))
    app.add_handler(CommandHandler("removeadmin", remove_admin_cmd))
    app.add_handler(CommandHandler("realp", real_participants_cmd))
    app.add_handler(CommandHandler("approve", approve_winners_cmd))
    app.add_handler(CommandHandler("reject", reject_winners_cmd))

    # inline callbacks
    app.add_handler(CallbackQueryHandler(panel_callback, pattern="^panel_"))
    app.add_handler(CallbackQueryHandler(join_giveaway_callback, pattern="^join_giveaway$"))
    app.add_handler(CallbackQueryHandler(no_action_callback, pattern="^no_action$"))

    # new giveaway conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("newgiveaway", new_giveaway_command)],
        states={
            CG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_title)],
            CG_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_prize)],
            CG_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_time)],
            CG_SPEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_speed)],
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
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )
    app.add_handler(conv)

    logger.info("Bot starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
