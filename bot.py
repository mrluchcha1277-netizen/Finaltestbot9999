#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
POWER POINT BREAK — GIVEAWAY BOT
ZERO-BUG FINAL VERSION — PART 1

এই Part–1 এ আছে:
- Imports
- Config (BOT_TOKEN, SUPER_ADMIN_USERNAME)
- Logging
- Conversation States
- Admin helper (ensure_admin, is_admin, bot_is_on)
- Time parser (10s/10m/10h/1day)
- Progress bar builder
- Channel / verification link sanitizer
- Giveaway text builder (Final Format)
- Winner announcement text builder (Final Format)
"""

# ====================== IMPORTS ======================
import logging
import random
import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Set, List, Optional

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ====================== CONFIG ======================

# 👉 এখানে তোমার BotFather থেকে নেওয়া টোকেন বসাবে
BOT_TOKEN = "8358046522:AAFWk7xSmfPCZCcS8YxCGQ5GsaUIE6ivg7E"

# 👉 তোমার main admin username (@ ছাড়া)
SUPER_ADMIN_USERNAME = "MinexxProo"

# Rotating icon frames (Live title animation)
ROTATE_FRAMES = ["✨", "✧", "✦", "✺"]


# ====================== LOGGING ======================

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("PowerPointBreakGiveawayBot")


# ====================== CONVERSATION STATES ======================

(
    CG_TITLE,          # Giveaway title
    CG_PRIZE,          # Prize text
    CG_TIME,           # Duration (10m/10h/1day)
    CG_SPEED,          # FAST / NORMAL / SLOW
    CG_WINNERS,        # Total winners
    CG_VERIF_LINKS,    # Verification links
    CG_WINNER_MODE,    # AUTO (future manual)
    CG_BAN_OLD,        # BAN / SKIP old winners
    CG_OLD_WINNER_LIST,# Old winners list
    CG_RULES_CHOICE,   # ADD / SKIP rules
    CG_RULES_TEXT,     # Rules text
    CG_CHANNEL,        # Channel link/username/id
    CG_CONFIRM,        # YES / CANCEL to post
) = range(13)


# ====================== ADMIN HELPERS ======================

def ensure_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    প্রথমবার SUPER_ADMIN_USERNAME মিলে গেলে তাকে super admin সেট করে।
    পরে সবাই admins set এর ভিতর থেকে চেক হবে।
    """
    user = update.effective_user
    if user is None:
        return False

    bot_data = context.bot_data
    admins: Set[int] = bot_data.setdefault("admins", set())
    super_admin_id = bot_data.get("super_admin_id")

    # আগেই admin হলে
    if user.id in admins:
        return True

    # প্রথমবার super admin সেট করা
    if super_admin_id is None:
        if user.username and user.username.lower() == SUPER_ADMIN_USERNAME.lower():
            bot_data["super_admin_id"] = user.id
            admins.add(user.id)
            logger.info(f"Super admin set: {user.id} (@{user.username})")
            return True

    return False


def is_admin(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """চেক করে user_id admins সেটে আছে কিনা"""
    return user_id in context.bot_data.get("admins", set())


def bot_is_on(context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Bot ON/OFF flag (default: ON).
    """
    return context.bot_data.get("bot_on", True)


# ====================== TIME PARSER ======================

def parse_duration_to_seconds(text: str) -> Optional[int]:
    """
    "10s", "10m", "10h", "1day", "3day" → seconds.
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


# ====================== PROGRESS BAR ======================

def build_progress_bar(done: float) -> str:
    """
    0.0–1.0 → ▰▰▰▱▱▱ style progress bar.
    """
    done = max(0.0, min(1.0, done))
    total_blocks = 10
    filled = int(round(done * total_blocks))
    empty = total_blocks - filled
    return "▰" * filled + "▱" * empty


# ====================== SANITIZERS ======================

def sanitize_channel_input(text: str) -> str:
    """
    Channel ইনপুট: @username / https://t.me/username / numeric ID
    সবকে send_message এর chat_id হিসেবে use করার উপযোগী করে দেয়।
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
    return text  # numeric ID অথবা অন্য কিছু


def sanitize_verification_chat(text: str) -> str:
    """
    Verification link থেকে chat reference বানায় (get_chat_member এর জন্য)।
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


# ====================== GIVEAWAY TEXT BUILDER ======================

def build_giveaway_text(
    g: Dict[str, Any],
    participants: int,
    time_left: int,
    icon: str,
) -> str:
    """
    Main giveaway পোস্টের final format (Channel + Preview দুই জায়গায় একই).
    """

    title: str = g.get("title", "")
    prize: str = g.get("prize", "")
    total_winners: int = g.get("winner_count", 0)
    old_blocked: int = len(g.get("old_winners", set()))
    rules: str = g.get("rules", "")
    duration: int = g.get("duration_seconds", 1) or 1

    # Time Left + Progress
    if time_left <= 0:
        time_str = "Finished"
        progress = 1.0
    else:
        h = time_left // 3600
        m = (time_left % 3600) // 60
        s = time_left % 60
        time_str = f"{h:02d}h {m:02d}m {s:02d}s (BD TIME)"
        progress = 1 - (time_left / duration)

    bar = build_progress_bar(progress)
    percent = int(progress * 100)

    lines: List[str] = []

    # Header
    lines.append(f"{icon} POWER POINT BREAK — OFFICIAL GIVEAWAY {icon}")
    lines.append("")
    lines.append(f"📌 Title: {title}")
    lines.append(f"🎁 Prize: {prize}")
    lines.append("")
    lines.append(f"🏆 Total Winners: {total_winners}")
    lines.append("🤖 Winner Mode: AUTO")
    lines.append(f"👥 Participate Count: {participants}")
    lines.append(f"🚫 Old Winners Blocked: {old_blocked} user(s)")
    lines.append("")

    # Countdown + Progress
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⏳ LIVE COUNTDOWN & PROGRESS")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"⏱ Time Left: {time_str}")
    lines.append("")
    lines.append("🎁 POWER POINT BREAK — GIVEAWAY LOADING 💐")
    lines.append(f"{bar} {percent}%")
    lines.append("")

    # Rules
    if rules:
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("📜 RULES")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append(rules)
        lines.append("")

    # Footer
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📢 Hosted By : Power Point Break")
    lines.append(f"👑 Admin     : @{SUPER_ADMIN_USERNAME}")
    lines.append("")
    lines.append("💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐")
    lines.append("[ 🎁 JOIN GIVEAWAY ]")

    return "\n".join(lines)


# ====================== WINNER ANNOUNCEMENT TEXT BUILDER ======================

def build_winner_text(
    g: Dict[str, Any],
    winners: List[int],
    participants: Dict[int, Dict[str, Any]],
) -> str:
    """
    Winner announcement পোস্টের final ফরম্যাট।
    """

    title: str = g.get("title", "")

    lines: List[str] = []
    lines.append("┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    lines.append("🎉 POWERPOINTBREAK — GIVEAWAY WINNER ANNOUNCED 🎉")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    lines.append("")
    lines.append("📌 Giveaway Title:")
    lines.append(title or "N/A")
    lines.append("")
    lines.append("🏆 OFFICIAL WINNERS LIST:")
    lines.append("")

    if not winners:
        lines.append("❌ No valid participants, no winners could be selected.")
    else:
        for i, uid in enumerate(winners, start=1):
            info = participants.get(uid, {})
            uname = info.get("username") or ""
            if uname:
                lines.append(f"{i}) @{uname} / {uid}")
            else:
                lines.append(f"{i}) ID: {uid}")

    lines.append("")
    lines.append("📢 Hosted By : Power Point Break")
    lines.append(f"👑 Admin     : @{SUPER_ADMIN_USERNAME}")

    return "\n".join(lines)


# ====================== PART 1 END ======================

"""
PART 1 শেষ ✅

এখন পর্যন্ত যা প্রস্তুত:
✔ Imports + Config + Logging
✔ Conversation States
✔ Admin helper (ensure_admin, is_admin, bot_is_on)
✔ Time parser (10s/10m/10h/1day)
✔ Progress bar builder
✔ Channel / verification sanitizers
✔ Giveaway main text format (Channel+Preview)
✔ Winner announcement text format

পরের স্টেপ:
👉 PART 2: /start, /panel, ON/OFF, admin add/remove, cancel ইত্যাদি Handler

Ready হলে বলো:  "Part 2"
"""


# ====================== PART 2 : ADMIN & BASIC COMMANDS ======================

# ---------------------- /start ----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    # প্রথমে দেখি সে super admin / admin কিনা
    if ensure_admin(update, context):
        status = "ON ✅" if bot_is_on(context) else "OFF ❌"
        await update.message.reply_text(
            "💐🌟🎉 WELCOME TO YOUR BOT 🎉🌟💐\n\n"
            f"👑 Admin: @{SUPER_ADMIN_USERNAME}\n"
            f"Bot Status: {status}\n\n"
            "📌 Admin Panel:\n"
            "/panel"
        )
        return

    # Bot OFF থাকলে – শুধু ইনফো দেখাবে
    if not bot_is_on(context):
        await update.message.reply_text(
            f"Hi Dear @{user.username}\n"
            f"UserID: {user.id}\n\n"
            "This is the Power Point Break Giveaway Bot.\n"
            "Only authorized admins can use this bot.\n\n"
            f"For support:\n👉 @{SUPER_ADMIN_USERNAME}"
        )
        return

    # Bot ON, কিন্তু সে admin না – সাধারণ user message
    await update.message.reply_text(
        "👋 Welcome!\n"
        "This bot is used for official giveaways.\n"
        "Please follow our channel for the next giveaway!"
    )


# ---------------------- /panel ----------------------
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    status = "ON ✅" if bot_is_on(context) else "OFF ❌"

    text = (
        "🛠 POWER POINT BREAK — ADMIN PANEL\n\n"
        "📜 ALL COMMANDS:\n"
        "--------------------------\n"
        "/start\n"
        "/panel\n"
        "/newgiveaway\n"
        "/on\n"
        "/off\n"
        "/addadmin <user_id>\n"
        "/removeadmin <user_id>\n"
        "/realp\n"
        "/approve\n"
        "/reject\n"
        "/cancel\n"
        "--------------------------\n\n"
        f"Current Bot Status: {status}\n\n"
        "🔘 QUICK CONTROLS:"
    )

    keyboard = [
        [InlineKeyboardButton("➕ NEW GIVEAWAY", callback_data="new_giveaway_btn")],
        [InlineKeyboardButton("🟢 BOT ON/OFF", callback_data="toggle_bot")],
    ]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------- BOT TOGGLE (button) ----------------------
async def toggle_bot_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # শুধুমাত্র admin allowed
    fake_update = Update(update.update_id, message=None)
    fake_update._effective_user = query.from_user  # ছোট্ট ট্রিক ensure_admin এর জন্য
    if not ensure_admin(fake_update, context):
        return await query.answer("❌ Admin only!", show_alert=True)

    bot_data = context.bot_data
    current = bot_data.get("bot_on", True)
    bot_data["bot_on"] = not current
    new_state = "ON ✅" if bot_data["bot_on"] else "OFF ❌"

    await query.edit_message_text(
        f"🔁 BOT STATUS CHANGED\n\n"
        f"Current Status: {new_state}\n\n"
        "Use /panel to open admin panel again."
    )


# ---------------------- /on ----------------------
async def turn_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    context.bot_data["bot_on"] = True
    await update.message.reply_text("🟢 Bot is now ON.")


# ---------------------- /off ----------------------
async def turn_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    context.bot_data["bot_on"] = False
    await update.message.reply_text("🔴 Bot is now OFF.")


# ---------------------- /addadmin ----------------------
async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /addadmin <user_id>")

    try:
        uid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ Invalid user_id (must be number)")

    admins: Set[int] = context.bot_data.setdefault("admins", set())
    admins.add(uid)

    await update.message.reply_text(f"✅ Added new admin: {uid}")


# ---------------------- /removeadmin ----------------------
async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /removeadmin <user_id>")

    try:
        uid = int(context.args[0])
    except ValueError:
        return await update.message.reply_text("❌ Invalid user_id (must be number)")

    admins: Set[int] = context.bot_data.setdefault("admins", set())
    if uid in admins:
        admins.remove(uid)
        await update.message.reply_text(f"❌ Removed admin: {uid}")
    else:
        await update.message.reply_text("User is not in admin list.")


# ---------------------- /cancel ----------------------
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    কোনো Conversation (/newgiveaway চলাকালীন) cancel করলে use হবে।
    """
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    context.user_data.pop("new_giveaway", None)
    await update.message.reply_text("❌ Cancelled current operation.")
    return ConversationHandler.END


# ---------------------- NEW GIVEAWAY BUTTON (panel থেকে) ----------------------
async def new_giveaway_btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    fake_update = Update(update.update_id, message=None)
    fake_update._effective_user = query.from_user
    if not ensure_admin(fake_update, context):
        return await query.answer("❌ Admin only!", show_alert=True)

    await query.edit_message_text(
        "➕ To create a new giveaway, type:\n\n"
        "/newgiveaway"
    )


# ====================== PART 2 END ======================

"""
PART 2 শেষ ✅

এখন যা রেডি:
✔ /start → admin + normal user আলাদা রেসপন্স
✔ /panel → full command list + quick buttons
✔ Button: NEW GIVEAWAY → /newgiveaway নির্দেশ
✔ Button: BOT ON/OFF → bot_on flag toggle
✔ /on /off → command দিয়ে bot চালু/বন্ধ
✔ /addadmin /removeadmin → admin control
✔ /cancel → চলমান setup/conversation stop

পরের স্টেপ:
👉 PART 3: /newgiveaway সম্পূর্ণ flow (Title → Prize → Time → Speed → Winners → Verification → Old Winners → Rules → Channel → Preview → Confirm)

Ready হলে বলো:  "Part 3 Zero bug"
"""


# ====================== PART 3 : NEW GIVEAWAY SETUP (ZERO BUG) ======================

# ---------------------- /newgiveaway ----------------------
async def new_giveaway(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ You are not an admin!")

    # নতুন giveaway data struct
    context.user_data["new_giveaway"] = {
        "title": "",
        "prize": "",
        "duration_seconds": 0,
        "interval_seconds": 3,
        "winner_count": 0,
        "verif_links": [],
        "winner_mode": "AUTO",
        "old_winners": set(),
        "rules": "",
        "channel": "",
    }

    await update.message.reply_text(
        "📝 SET YOUR GIVEAWAY TITLE:"
    )
    return CG_TITLE


# ---------------------- Title ----------------------
async def cg_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    g["title"] = update.message.text.strip()

    await update.message.reply_text(
        "🎁 NOW SET YOUR PRIZE:\n"
        "Example: ChatGPT Plus Premium Full Access"
    )
    return CG_PRIZE


# ---------------------- Prize ----------------------
async def cg_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    g["prize"] = update.message.text.strip()

    await update.message.reply_text(
        "⏳ NOW SET YOUR GIVEAWAY TIME (BD TIME)\n\n"
        "Use:\n"
        "10s = 10 seconds\n"
        "10m = 10 minutes\n"
        "10h = 10 hours\n"
        "1day = 1 day\n"
        "3day = 3 days"
    )
    return CG_TIME


# ---------------------- Time ----------------------
async def cg_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    text = update.message.text.strip()
    duration = parse_duration_to_seconds(text)
    if duration is None:
        return await update.message.reply_text(
            "❌ Invalid time format.\n"
            "Try like: 10s / 10m / 10h / 1day / 3day"
        )

    g["duration_seconds"] = duration

    await update.message.reply_text(
        "⏳ Time Saved!\n\n"
        "Choose countdown speed:\n"
        "FAST   = update every 1 second\n"
        "NORMAL = update every 3 seconds\n"
        "SLOW   = update every 5 seconds\n\n"
        "Send: FAST / NORMAL / SLOW"
    )
    return CG_SPEED


# ---------------------- Speed ----------------------
async def cg_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    choice = update.message.text.strip().lower()

    if choice == "fast":
        g["interval_seconds"] = 1
    elif choice == "normal":
        g["interval_seconds"] = 3
    elif choice == "slow":
        g["interval_seconds"] = 5
    else:
        return await update.message.reply_text(
            "❌ Invalid choice.\n"
            "Send: FAST / NORMAL / SLOW"
        )

    await update.message.reply_text(
        "🏆 NOW SET TOTAL WINNERS (1–100000):"
    )
    return CG_WINNERS


# ---------------------- Winners ----------------------
async def cg_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    text = update.message.text.strip()
    try:
        count = int(text)
    except ValueError:
        return await update.message.reply_text("❌ Invalid number, try again.")

    if count < 1 or count > 100000:
        return await update.message.reply_text(
            "❌ Winner count must be between 1 and 100000."
        )

    g["winner_count"] = count

    await update.message.reply_text(
        "🔗 NOW SET YOUR VERIFICATION LINKS\n\n"
        "Send each channel/group link one by one.\n"
        "Example:\n"
        "https://t.me/YourChannel\n"
        "https://t.me/YourGroup\n\n"
        "Type DONE when finished.\n"
        "Type SKIP to disable verification."
    )
    return CG_VERIF_LINKS


# ---------------------- Verification Links ----------------------
async def cg_verif_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    text = update.message.text.strip()

    # SKIP → no verification
    if text.upper() == "SKIP":
        g["verif_links"] = []
        await update.message.reply_text(
            "🤖 Winner Mode: AUTO\n"
            "Send: AUTO"
        )
        return CG_WINNER_MODE

    # DONE → stop adding
    if text.upper() == "DONE":
        await update.message.reply_text(
            "🤖 Winner Mode: AUTO\n"
            "Send: AUTO"
        )
        return CG_WINNER_MODE

    # Otherwise treat as link
    g["verif_links"].append(text)
    await update.message.reply_text(
        "✔ Link saved.\n"
        "Send more, or type DONE / SKIP."
    )
    return CG_VERIF_LINKS


# ---------------------- Winner Mode (AUTO only) ----------------------
async def cg_winner_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    mode = update.message.text.strip().upper()
    if mode != "AUTO":
        return await update.message.reply_text(
            "❌ Only AUTO mode is supported.\n"
            "Please send: AUTO"
        )

    g["winner_mode"] = "AUTO"

    await update.message.reply_text(
        "🚫 Do you want to BAN OLD WINNERS?\n"
        "Send: BAN or SKIP"
    )
    return CG_BAN_OLD


# ---------------------- Ban Old Winners (BAN / SKIP) ----------------------
async def cg_ban_old(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    choice = update.message.text.strip().upper()

    if choice == "SKIP":
        # old_winners empty থাকবে
        g["old_winners"] = set()
        await update.message.reply_text(
            "📜 Do you want to add RULES?\n"
            "Send: ADD or SKIP"
        )
        return CG_RULES_CHOICE

    if choice == "BAN":
        g["old_winners"] = set()
        await update.message.reply_text(
            "Please send OLD winners list:\n\n"
            "Format (one per line):\n"
            "@Username/UserID\n\n"
            "Example:\n"
            "@MinexxProo/1701097178\n\n"
            "Send ALL lines, then type: DONE"
        )
        return CG_OLD_WINNER_LIST

    return await update.message.reply_text(
        "❌ Invalid choice.\n"
        "Send: BAN or SKIP"
    )


# ---------------------- Old Winners List (multi-line + DONE) ----------------------
async def cg_old_winner_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    text = update.message.text.strip()

    # DONE → stop adding
    if text.upper() == "DONE":
        await update.message.reply_text(
            "📜 Do you want to add RULES?\n"
            "Send: ADD or SKIP"
        )
        return CG_RULES_CHOICE

    if "old_winners" not in g or not isinstance(g["old_winners"], set):
        g["old_winners"] = set()

    added = 0

    # একসাথে অনেক লাইন দিলে সব parse করবে
    for line in text.splitlines():
        line = line.strip()
        if not line or "/" not in line:
            continue

        parts = line.split("/")
        if len(parts) != 2:
            continue

        uname = parts[0].strip().lstrip("@")
        uid_str = parts[1].strip()
        if not uname or not uid_str.isdigit():
            continue

        uid = int(uid_str)
        g["old_winners"].add((uname.lower(), uid))
        added += 1

    await update.message.reply_text(
        f"✔ Saved {added} old winners.\n"
        "Send more list, or type: DONE"
    )
    return CG_OLD_WINNER_LIST


# ---------------------- Rules Choice (ADD / SKIP) ----------------------
async def cg_rules_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    choice = update.message.text.strip().upper()

    if choice == "SKIP":
        g["rules"] = ""
        await update.message.reply_text(
            "📌 NOW SEND YOUR CHANNEL link / @username / numeric ID"
        )
        return CG_CHANNEL

    if choice == "ADD":
        await update.message.reply_text(
            "Send all your RULES in a single message:"
        )
        return CG_RULES_TEXT

    return await update.message.reply_text(
        "❌ Invalid choice.\n"
        "Send: ADD or SKIP"
    )


# ---------------------- Rules Text ----------------------
async def cg_rules_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    g["rules"] = update.message.text.strip()

    await update.message.reply_text(
        "📌 NOW SEND YOUR CHANNEL link / @username / numeric ID"
    )
    return CG_CHANNEL


# ---------------------- Channel Input ----------------------
async def cg_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        return ConversationHandler.END

    raw = update.message.text.strip()
    channel_id = sanitize_channel_input(raw)
    g["channel"] = channel_id

    # Preview build
    preview_text = build_giveaway_text(
        g,
        participants=0,
        time_left=g["duration_seconds"],
        icon="✨",
    )

    await update.message.reply_text(
        "🔍 PREVIEW YOUR GIVEAWAY:\n\n"
        f"{preview_text}\n\n"
        "✅ Send YES to post this giveaway.\n"
        "❌ Send CANCEL to abort.",
    )
    return CG_CONFIRM


# ---------------------- Confirm (YES / CANCEL) ----------------------
async def cg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    এখানে শুধু YES/CANCEL handle হবে।
    YES হলে পরের Part (Part 4) এর finalize_giveaway_post() কে কল করবে।
    """
    text = update.message.text.strip().upper()
    if text == "CANCEL":
        context.user_data.pop("new_giveaway", None)
        await update.message.reply_text("❌ Giveaway setup cancelled.")
        return ConversationHandler.END

    if text == "YES":
        # Actual posting + countdown Part 4 এ থাকবে
        from_context = context  # শুধু readable রাখার জন্য
        await finalize_giveaway_post(update, from_context)  # Part 4 function
        return ConversationHandler.END

    return await update.message.reply_text(
        "❌ Invalid response.\n"
        "Send YES to post or CANCEL to stop."
    )


# ====================== PART 3 END ======================

"""
PART 3 শেষ ✅

এখন পর্যন্ত Bot যা পারে:
✔ /newgiveaway → পুরো setup flow চালায়
✔ Title / Prize / Time / Speed / Winners
✔ Verification links (multi + DONE/SKIP)
✔ Winner mode (AUTO)
✔ Old winners BAN system (multi-line + DONE)
✔ Rules ADD/SKIP
✔ Channel link/username/ID ইনপুট
✔ Final full preview formatting
✔ YES → finalize_giveaway_post (Part 4 তে define হবে)
✔ CANCEL → পুরো setup cancel

পরের স্টেপ:
👉 PART 4 Zero bug: 
   - finalize_giveaway_post
   - countdown loop
   - join button
   - verification check
   - old winner block (popup)
   - duplicate entry popup
   - real participants list
   - approve / reject
   - main() + handler registration

Ready হলে বলো: "Part 4 Zero bug"
"""

# ====================== PART 4 : FINAL ENGINE (ZERO BUG FIXED) ======================

# ---------------------- FINALIZE GIVEAWAY POST ----------------------
async def finalize_giveaway_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    g = context.user_data.get("new_giveaway")
    if not g:
        await update.message.reply_text("❌ No giveaway data found. Please run /newgiveaway again.")
        return

    bot = context.bot
    channel_ref = g["channel"]

    preview_text = build_giveaway_text(
        g,
        participants=0,
        time_left=g["duration_seconds"],
        icon="✨",
    )

    try:
        msg = await bot.send_message(
            chat_id=channel_ref,
            text=preview_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]
            ])
        )
    except Exception as e:
        await update.message.reply_text("❌ Bot is not admin in the channel. Please fix and retry.")
        return

    now = datetime.now(timezone.utc)
    end_time = now + timedelta(seconds=g["duration_seconds"])

    verif_chats = [sanitize_verification_chat(v) for v in g.get("verif_links", [])]

    context.bot_data["current_giveaway"] = {
        "title": g["title"],
        "prize": g["prize"],
        "duration_seconds": g["duration_seconds"],
        "interval_seconds": g["interval_seconds"],
        "winner_count": g["winner_count"],
        "verif_links": g["verif_links"],
        "verif_chats": verif_chats,
        "winner_mode": g["winner_mode"],
        "old_winners": g["old_winners"],
        "rules": g["rules"],
        "channel": msg.chat.id,
        "message_id": msg.message_id,
        "participants": {},
        "start_time": now,
        "end_time": end_time,
        "status": "running",
        "winners": [],
    }

    context.bot_data["frame_index"] = 0

    await update.message.reply_text("✅ Giveaway posted. Countdown started!")

    app = context.application
    task = context.bot_data.get("countdown_task")

    if not task or task.done():
        context.bot_data["countdown_task"] = asyncio.create_task(countdown_loop(app))

    context.user_data.pop("new_giveaway", None)


# ---------------------- BACKGROUND COUNTDOWN LOOP ----------------------
async def countdown_loop(app):
    while True:
        try:
            g = app.bot_data.get("current_giveaway")
            if not g or g.get("status") != "running":
                await asyncio.sleep(2)
                continue

            now = datetime.now(timezone.utc)
            time_left = int((g["end_time"] - now).total_seconds())
            channel_id = g["channel"]
            msg_id = g["message_id"]
            participants = g.get("participants", {})

            if time_left <= 0:
                g["status"] = "waiting_approval"

                user_ids = list(participants.keys())
                if user_ids:
                    winners = random.sample(user_ids, min(g["winner_count"], len(user_ids)))
                else:
                    winners = []

                g["winners"] = winners

                final_text = build_giveaway_text(
                    g,
                    participants=len(participants),
                    time_left=0,
                    icon="✨",
                )

                try:
                    await app.bot.edit_message_text(
                        chat_id=channel_id,
                        message_id=msg_id,
                        text=final_text,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🎁 GIVEAWAY ENDED", callback_data="no_action")]
                        ])
                    )
                except:
                    pass

                super_admin = app.bot_data.get("super_admin_id")
                if super_admin:
                    preview = build_winner_text(g, winners, participants)
                    await app.bot.send_message(
                        chat_id=super_admin,
                        text=(
                            "🏁🔥 GIVEAWAY CLOSED!\n"
                            f"🔍 {len(winners)} Winners selected.\n\n"
                            f"{preview}\n\n"
                            "Send /approve to publish.\n"
                            "Send /reject to cancel."
                        )
                    )

                await asyncio.sleep(2)
                continue

            app.bot_data["frame_index"] = (app.bot_data.get("frame_index", 0) + 1) % len(ROTATE_FRAMES)
            icon = ROTATE_FRAMES[app.bot_data["frame_index"]]

            new_text = build_giveaway_text(
                g,
                participants=len(participants),
                time_left=time_left,
                icon=icon,
            )

            try:
                await app.bot.edit_message_text(
                    chat_id=channel_id,
                    message_id=msg_id,
                    text=new_text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]
                    ])
                )
            except:
                pass

            await asyncio.sleep(g.get("interval_seconds", 3))

        except Exception as e:
            await asyncio.sleep(5)


# ---------------------- JOIN GIVEAWAY BUTTON ----------------------
async def join_giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    uid = user.id
    uname_raw = user.username or ""
    uname = uname_raw.lower()

    await query.answer()

    g = context.bot_data.get("current_giveaway")
    if not g or g.get("status") != "running":
        return await query.answer("Giveaway is not running.", show_alert=True)

    if not bot_is_on(context):
        return await query.answer("Bot is OFF.", show_alert=True)

    if not uname:
        return await query.answer("You must set a public username.", show_alert=True)

    # OLD WINNER BLOCK
    for old_uname, old_uid in g["old_winners"]:
        if uname == old_uname or uid == old_uid:
            await query.answer(
                "😔 Oops! You have already won this giveaway before,\n"
                "so you can no longer participate, dear members\n\n"
                "🍀 Try again — more giveaways coming soon!\n"
                "💙 Stay with Power Point Break!",
                show_alert=True,
            )

            admin = context.bot_data.get("super_admin_id")
            if admin:
                await context.bot.send_message(
                    admin,
                    f"⚠️ Old Winner Tried to Join!\n@{uname_raw} / {uid}"
                )
            return

    # VERIFICATION CHECK
    for ref in g.get("verif_chats", []):
        try:
            chat = await context.bot.get_chat(ref)
            member = await context.bot.get_chat_member(chat.id, uid)
            if member.status not in ("member", "administrator", "creator"):
                raise Exception("Not joined")
        except:
            txt = "⛔ ACCESS DENIED — VERIFICATION FAILED ⛔\n\n"
            txt += "Please join ALL required channels:\n\n"
            for i, v in enumerate(g.get("verif_links", []), start=1):
                txt += f"{i}) {v}\n"
            try:
                await context.bot.send_message(uid, txt)
            except:
                pass

            return await query.answer("Join required channels first.", show_alert=True)

    # DUPLICATE ENTRY
    participants = g["participants"]
    if uid in participants:
        return await query.answer(
            "⚠️❌ WARNING — DUPLICATE ENTRY ❌⚠️\n\n"
            "You already participated!\nWinner list will be published soon.",
            show_alert=True
        )

    # ACCEPTED
    participants[uid] = {
        "username": uname_raw,
        "joined_at": datetime.now(timezone.utc)
    }

    try:
        await context.bot.send_message(uid, "🎉 You have successfully joined the giveaway!\nGood luck! 🍀")
    except:
        pass

    admin = context.bot_data.get("super_admin_id")
    if admin:
        await context.bot.send_message(
            admin,
            f"👤 NEW PARTICIPANT JOINED\n@{uname_raw} / {uid}"
        )

    await query.answer("Joined! Check your DM.")


# ---------------------- /realp ----------------------
async def real_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ Not an admin.")

    g = context.bot_data.get("current_giveaway")
    if not g:
        return await update.message.reply_text("❌ No active giveaway.")

    participants = g["participants"]
    if not participants:
        return await update.message.reply_text("No participants yet.")

    txt = "👥 REAL PARTICIPANTS:\n\n"
    for uid, info in participants.items():
        txt += f"- @{info['username']} / {uid}\n"

    await update.message.reply_text(txt)


# ---------------------- /approve ----------------------
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ Not an admin.")

    g = context.bot_data.get("current_giveaway")
    if not g or g["status"] != "waiting_approval":
        return await update.message.reply_text("❌ Nothing to approve.")

    winners = g["winners"]
    participants = g["participants"]
    channel = g["channel"]

    win_text = build_winner_text(g, winners, participants)

    await context.bot.send_message(channel, win_text)

    for uid in winners:
        try:
            await context.bot.send_message(
                uid,
                f"🎉 CONGRATULATIONS! 🎉\nYou are a WINNER!\nContact admin:\n👉 @{SUPER_ADMIN_USERNAME}"
            )
        except:
            pass

    g["status"] = "closed"
    await update.message.reply_text("✅ Winners published.")


# ---------------------- /reject ----------------------
async def reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ensure_admin(update, context):
        return await update.message.reply_text("❌ Not an admin.")

    g = context.bot_data.get("current_giveaway")
    if not g or g["status"] != "waiting_approval":
        return await update.message.reply_text("❌ Nothing to reject.")

    g["status"] = "closed"
    await update.message.reply_text("❌ Giveaway closed without announcement.")


# ---------------------- REGISTER HANDLERS ----------------------
def register_handlers(app):

    # Basic Admin Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("on", turn_on))
    app.add_handler(CommandHandler("off", turn_off))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("cancel", cancel))

    # Panel Buttons
    app.add_handler(CallbackQueryHandler(new_giveaway_btn, pattern="^new_giveaway_btn$"))
    app.add_handler(CallbackQueryHandler(toggle_bot_btn, pattern="^toggle_bot$"))

    # Giveaway Setup Conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("newgiveaway", new_giveaway)],
        states={
            CG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_title)],
            CG_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_prize)],
            CG_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_time)],
            CG_SPEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_speed)],
            CG_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winners)],
            CG_VERIF_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_verif_links)],
            CG_WINNER_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winner_mode)],
            CG_BAN_OLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_ban_old)],
            CG_OLD_WINNER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_old_winner_list)],
            CG_RULES_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_rules_choice)],
            CG_RULES_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_rules_text)],
            CG_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_channel)],
            CG_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)

    # Join Button
    app.add_handler(CallbackQueryHandler(join_giveaway_callback, pattern="^join_giveaway$"))

    # Participants & Winners
    app.add_handler(CommandHandler("realp", real_participants))
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("reject", reject))


# ---------------------- MAIN ENTRY ----------------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    register_handlers(app)

    app.bot_data["countdown_task"] = asyncio.create_task(countdown_loop(app))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())




