# ==========================
#  Power Point Break Giveaway Bot
#  Clean JobQueue Version (NO asyncio.run, NO extra thread)
# ==========================

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    Job,
)

# ---------------- CONFIG ----------------

BOT_TOKEN = "8358046522:AAFBcxWEgReqSdCZLyjp7ur4KooiX8Has6o"        # <-- এখানে তোমার BotFather token দেবে
SUPER_ADMIN_USERNAME = "MinexxProo"          # <-- তোমার main admin username

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------- STATES ----------------
(
    CG_TITLE,
    CG_PRIZE,
    CG_TIME,
    CG_WINNERS,
    CG_OLD_CHOICE,
    CG_OLD_LIST,
    CG_RULES,
    CG_VERIF_LINKS,
    CG_SPEED,
    CG_CHANNEL,
    CG_CONFIRM,
) = range(11)

# ---------------- DATA CLASSES ----------------

@dataclass
class Participant:
    user_id: int
    username: str
    full_name: str


@dataclass
class Giveaway:
    title: str = ""
    prize: str = ""
    winners_count: int = 1
    duration_seconds: int = 600
    end_time: Optional[datetime] = None  # UTC
    old_winners: Set[int] = field(default_factory=set)
    rules: str = ""
    verification_links: List[str] = field(default_factory=list)
    speed_mode: str = "NORMAL"  # FAST / NORMAL / SLOW
    interval_seconds: int = 3
    channel_ref: str = ""  # @channel, link or id (string)
    channel_id: Optional[int] = None
    message_chat_id: Optional[int] = None
    message_id: Optional[int] = None
    participants: Dict[int, Participant] = field(default_factory=dict)
    fake_factor: int = 0  # for fake "Participate Count" growth
    rotating_index: int = 0
    finished: bool = False
    countdown_job: Optional[Job] = None

    def is_running(self) -> bool:
        return self.end_time is not None and not self.finished

# ---------------- SIMPLE HELPERS ----------------

def get_bd_time() -> datetime:
    """Return current BD time as aware datetime."""
    return datetime.now(timezone.utc) + timedelta(hours=6)


def parse_duration_to_seconds(text: str) -> Optional[int]:
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


def format_hms(seconds: int) -> str:
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}h {m:02d}m {s:02d}s"


def build_progress_bar(percent: int) -> str:
    blocks = 10
    filled = int(round(percent * blocks / 100))
    filled = max(0, min(blocks, filled))
    return "▰" * filled + "▱" * (blocks - filled)


ROTATING_ICONS = ["✨", "💫", "🌟", "⚡️"]

def rotating_icon(index: int) -> str:
    return ROTATING_ICONS[index % len(ROTATING_ICONS)]


def is_super_admin(user) -> bool:
    return bool(user.username) and user.username.lower() == SUPER_ADMIN_USERNAME.lower()


def get_admins(context: ContextTypes.DEFAULT_TYPE) -> Set[int]:
    return context.bot_data.setdefault("admins", set())


def is_admin(user, context: ContextTypes.DEFAULT_TYPE) -> bool:
    admins = get_admins(context)
    if user.id in admins:
        return True
    # first time: super admin auto add
    if is_super_admin(user) and user.id not in admins:
        admins.add(user.id)
        context.bot_data["super_admin_id"] = user.id
        return True
    return False


def bot_is_on(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.bot_data.get("bot_on", True)


def get_current_giveaway(context: ContextTypes.DEFAULT_TYPE) -> Optional[Giveaway]:
    return context.bot_data.get("current_giveaway")
# ---------------- TEXT BUILDERS ----------------

def build_giveaway_post_text(g: Giveaway) -> str:
    # Live stats
    now_utc = datetime.now(timezone.utc)
    remaining = int((g.end_time - now_utc).total_seconds()) if g.end_time else g.duration_seconds
    if remaining < 0:
        remaining = 0
    percent = 0
    if g.duration_seconds > 0:
        done = g.duration_seconds - remaining
        percent = int(done * 100 / g.duration_seconds)

    bar = build_progress_bar(percent)
    icon = rotating_icon(g.rotating_index)

    real_participants = len(g.participants)
    fake_show = real_participants * 2  # তোমার আগের লজিক মতো double দেখাচ্ছি

    lines = []
    lines.append(f"{icon} POWER POINT BREAK — OFFICIAL GIVEAWAY {icon}")
    lines.append("")
    lines.append(f"📌 Title: {g.title}")
    lines.append(f"🎁 Prize: {g.prize}")
    lines.append(f"🏆 Total Winners: {g.winners_count}")
    lines.append("🤖 Winner Mode: AUTO")
    lines.append(f"👥 Participate Count: {fake_show}")
    lines.append(f"🚫 Old Winners Blocked: {len(g.old_winners)} user(s)")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⏳ LIVE COUNTDOWN & PROGRESS")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"⏱ Time Left: {format_hms(remaining)} (BD TIME)")
    lines.append("")
    lines.append("🎁 POWER POINT BREAK — GIVEAWAY LOADING 💐")
    lines.append(f"{bar} {percent}%")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("📜 RULES")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(g.rules if g.rules else "No specific rules.")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append("📢 Hosted By : Power Point Break")
    lines.append("👑 Admin     : @MinexxProo")
    lines.append("")
    lines.append("💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐")
    lines.append("[ 🎁 JOIN GIVEAWAY ]")
    return "\n".join(lines)


def build_admin_panel_text(on_flag: bool) -> str:
    status = "ON ✅" if on_flag else "OFF ❌"
    text = (
        "🛠 POWER POINT BREAK — ADMIN PANEL\n\n"
        f"🔌 Bot Status: {status}\n\n"
        "📜 ALL ADMIN COMMANDS:\n"
        "-------------------------------\n"
        "/start  - Initialize / reopen admin session\n"
        "/panel  - Show all admin commands\n"
        "/newgiveaway - Create a new giveaway (full setup)\n"
        "/off    - Turn the bot OFF (users can't use it)\n"
        "/on     - Turn the bot ON\n"
        "/addadmin <user_id> - Add a new admin\n"
        "/removeadmin <user_id> - Remove an admin\n"
        "/realp  - Show real participants of current giveaway\n"
        "/cancel - Cancel current setup (if any)\n"
        "-------------------------------\n\n"
        "Shortcut buttons:\n👇"
    )
    return text


# ---------------- HANDLERS: START & PANEL ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text(
            "Hi Dear @{username}\n\n"
            "This is the Power Point Break Giveaway Bot.\n"
            "Only authorized admins can control this bot.\n\n"
            "For support contact: @MinexxProo".format(
                username=user.username or "User"
            )
        )
        return

    # ensure bot_on flag exists
    context.bot_data.setdefault("bot_on", True)

    text = (
        "💐🌟🎉 WELCOME TO YOUR BOT 🎉🌟💐\n\n"
        f"👑 Admin: @{user.username}\n"
        "🛠 Setup Your Giveaway Bot Now!\n\n"
        "📌 Admin Panel Command:\n"
        "➡️ /panel\n\n"
        "🔥 Everything is under your control!"
    )
    await update.message.reply_text(text)


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    on_flag = bot_is_on(context)
    text = build_admin_panel_text(on_flag)

    keyboard = [
        [InlineKeyboardButton("➕ NEW GIVEAWAY", callback_data="panel_new_giveaway")],
        [InlineKeyboardButton("🔄 BOT ON/OFF", callback_data="toggle_bot")],
    ]
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- BOT ON / OFF ----------------

async def bot_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return
    context.bot_data["bot_on"] = False
    await update.message.reply_text("Bot status changed to: OFF ❌")


async def bot_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return
    context.bot_data["bot_on"] = True
    await update.message.reply_text("Bot status changed to: ON ✅")


async def toggle_bot_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user = query.from_user
    if not is_admin(user, context):
        await query.edit_message_text("⛔ You are not an admin.")
        return

    current = bot_is_on(context)
    context.bot_data["bot_on"] = not current
    new_flag = context.bot_data["bot_on"]
    text = build_admin_panel_text(new_flag)

    keyboard = [
        [InlineKeyboardButton("➕ NEW GIVEAWAY", callback_data="panel_new_giveaway")],
        [InlineKeyboardButton("🔄 BOT ON/OFF", callback_data="toggle_bot")],
    ]
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------- ADMIN ADD / REMOVE / REALP ----------------

async def addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    if not context.args:
        await update.message.reply_text("Send numeric user_id. Example:\n/addadmin 5692210187")
        return

    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Please send numeric user_id.")
        return

    admins = get_admins(context)
    admins.add(uid)
    await update.message.reply_text(f"✅ Added new admin with ID: {uid}")


async def removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    if not context.args:
        await update.message.reply_text("Send numeric user_id. Example:\n/removeadmin 5692210187")
        return

    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID. Please send numeric user_id.")
        return

    admins = get_admins(context)
    if uid in admins:
        admins.remove(uid)
        await update.message.reply_text(f"✅ Removed admin with ID: {uid}")
    else:
        await update.message.reply_text("ID was not an admin.")


async def realp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return

    g = get_current_giveaway(context)
    if not g:
        await update.message.reply_text("No active giveaway.")
        return

    if not g.participants:
        await update.message.reply_text("No participants yet.")
        return

    lines = ["👥 REAL PARTICIPANTS:"]
    for p in g.participants.values():
        uname = f"@{p.username}" if p.username else "(no username)"
        lines.append(f"{uname} / {p.user_id}")
    await update.message.reply_text("\n".join(lines))

# ---------------- NEW GIVEAWAY FLOW ----------------

async def panel_new_giveaway_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if not is_admin(user, context):
        await query.edit_message_text("⛔ You are not an admin.")
        return ConversationHandler.END
    await query.message.reply_text("📝 SET YOUR GIVEAWAY TITLE:")
    context.user_data["new_giveaway"] = Giveaway()
    return CG_TITLE


async def newgiveaway_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not is_admin(user, context):
        await update.message.reply_text("⛔ You are not an admin.")
        return ConversationHandler.END

    await update.message.reply_text("📝 SET YOUR GIVEAWAY TITLE:")
    context.user_data["new_giveaway"] = Giveaway()
    return CG_TITLE


async def cg_title(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    g.title = update.message.text.strip()
    await update.message.reply_text(
        "🎁 NOW SET THE PRIZE:\n\nExample: ChatGPT Plus Premium Full Access"
    )
    return CG_PRIZE


async def cg_prize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    g.prize = update.message.text.strip()
    msg = (
        "⏳ NOW SET YOUR GIVEAWAY TIME\n\n"
        "Use:\n"
        "10s  = 10 seconds\n"
        "10m  = 10 minutes\n"
        "10h  = 10 hours\n"
        "1day = 1 day\n"
        "3day = 3 days\n\n"
        "🕒 BD Time Zone (GMT+6)"
    )
    await update.message.reply_text(msg)
    return CG_TIME


async def cg_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    secs = parse_duration_to_seconds(update.message.text)
    if not secs or secs <= 0:
        await update.message.reply_text("❌ Invalid time. Please use like: 10m / 2h / 1day")
        return CG_TIME
    g.duration_seconds = secs
    await update.message.reply_text(
        "🏆 How many winners?\n\n"
        "You can set from 1 to 100000."
    )
    return CG_WINNERS


async def cg_winners(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    try:
        n = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Please send a number. Example: 10")
        return CG_WINNERS
    if n <= 0 or n > 100000:
        await update.message.reply_text("❌ Min 1, Max 100000.")
        return CG_WINNERS
    g.winners_count = n

    keyboard = [
        [
            InlineKeyboardButton("🚫 Ban Old Winners", callback_data="old_yes"),
            InlineKeyboardButton("➡️ Skip", callback_data="old_skip"),
        ]
    ]
    await update.message.reply_text(
        "Do you want to BAN old winners?\n\nChoose:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CG_OLD_CHOICE


async def cg_old_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    g: Giveaway = context.user_data["new_giveaway"]

    if query.data == "old_skip":
        g.old_winners = set()
        await query.message.reply_text(
            "📜 NOW SET YOUR RULES.\n\nSend any rules text.\nOr send SKIP to continue without rules."
        )
        return CG_RULES

    # want to add old winners
    msg = (
        "Please send OLD winners list.\n\n"
        "Format (one per line):\n"
        "@Username/UserID\n\n"
        "Example:\n"
        "@MinexxProo/1701097178\n\n"
        "When finished, send: DONE"
    )
    await query.message.reply_text(msg)
    g.old_winners = set()
    return CG_OLD_LIST


async def cg_old_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    text = update.message.text.strip()

    if text.upper() == "DONE":
        await update.message.reply_text(
            "📜 NOW SET YOUR RULES.\n\nSend any rules text.\nOr send SKIP to continue without rules."
        )
        return CG_RULES

    # multiple lines allowed
    lines = text.splitlines()
    added = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = re.match(r"@?[A-Za-z0-9_]+/(\d+)", line)
        if not m:
            continue
        uid = int(m.group(1))
        g.old_winners.add(uid)
        added += 1

    await update.message.reply_text(f"✅ Added {added} old winners. Send more or DONE.")
    return CG_OLD_LIST


async def cg_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    text = update.message.text.strip()
    if text.upper() == "SKIP":
        g.rules = ""
    else:
        g.rules = text

    keyboard = [
        [
            InlineKeyboardButton("➕ Add Verify Links", callback_data="verif_add"),
            InlineKeyboardButton("➡️ Skip", callback_data="verif_skip"),
        ]
    ]
    await update.message.reply_text(
        "Now set Verification links (channels/groups users MUST join).\n\n"
        "Choose:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CG_VERIF_LINKS


async def cg_verif_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    g: Giveaway = context.user_data["new_giveaway"]

    if query.data == "verif_skip":
        g.verification_links = []
        return await ask_speed_mode(query.message, g)

    await query.message.reply_text(
        "Send verification links (channel/group) – one or many lines.\n\n"
        "Example:\n"
        "https://t.me/PowerPointBreak\n"
        "https://t.me/OurPremiumStore\n\n"
        "When finished, send: DONE"
    )
    g.verification_links = []
    return CG_VERIF_LINKS


async def cg_verif_links(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    text = update.message.text.strip()

    if text.upper() == "DONE":
        # go to speed mode
        return await ask_speed_mode(update.message, g)

    lines = text.splitlines()
    for line in lines:
        url = line.strip()
        if not url:
            continue
        g.verification_links.append(url)

    await update.message.reply_text(
        f"Link saved. Total now: {len(g.verification_links)}\nSend more or DONE."
    )
    return CG_VERIF_LINKS


async def ask_speed_mode(message, g: Giveaway) -> int:
    text = (
        "⏱ Select countdown update speed:\n\n"
        "⚡ Fast mode: 1 second\n"
        "⏳ Normal mode: 3 seconds\n"
        "🐢 Slow mode: 5 seconds\n"
    )
    keyboard = [
        [
            InlineKeyboardButton("⚡ FAST", callback_data="speed_fast"),
            InlineKeyboardButton("⏳ NORMAL", callback_data="speed_normal"),
            InlineKeyboardButton("🐢 SLOW", callback_data="speed_slow"),
        ]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CG_SPEED


async def cg_speed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    g: Giveaway = context.user_data["new_giveaway"]

    if query.data == "speed_fast":
        g.speed_mode = "FAST"
        g.interval_seconds = 1
    elif query.data == "speed_slow":
        g.speed_mode = "SLOW"
        g.interval_seconds = 5
    else:
        g.speed_mode = "NORMAL"
        g.interval_seconds = 3

    await query.message.reply_text(
        "Send your Channel link / @username / channel id\n"
        "Where the giveaway post will be published."
    )
    return CG_CHANNEL


async def cg_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    g: Giveaway = context.user_data["new_giveaway"]
    g.channel_ref = update.message.text.strip()

    # Preview text
    preview = build_giveaway_post_text(g)
    await update.message.reply_text(
        "Here is the preview of your giveaway post:\n\n" + preview
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ YES, POST IT", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ NO, CANCEL", callback_data="confirm_no"),
        ]
    ]
    await update.message.reply_text(
        "Can I post this giveaway to your main channel?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CG_CONFIRM


async def cg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    g: Giveaway = context.user_data["new_giveaway"]
    user = query.from_user

    if query.data == "confirm_no":
        await query.message.reply_text("❌ Giveaway setup cancelled.")
        return ConversationHandler.END

    # Save as current giveaway
    context.bot_data["current_giveaway"] = g

    # Try to send preview to channel
    try:
        channel_message = await context.bot.send_message(
            chat_id=g.channel_ref,
            text=build_giveaway_post_text(g),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]]
            ),
            disable_web_page_preview=True,
        )
        g.message_chat_id = channel_message.chat_id
        g.message_id = channel_message.message_id
    except Exception as e:
        logger.exception("Error sending giveaway to channel: %s", e)
        await query.message.reply_text(
            "❌ Failed to send message to channel. Check that the bot is admin there."
        )
        return ConversationHandler.END

    # set end_time & schedule countdown job
    now_utc = datetime.now(timezone.utc)
    g.end_time = now_utc + timedelta(seconds=g.duration_seconds)

    # schedule repeating job
    job_queue = context.job_queue
    job = job_queue.run_repeating(
        countdown_job,
        interval=g.interval_seconds,
        first=0,
        data={},
        name="giveaway_countdown",
    )
    g.countdown_job = job

    await query.message.reply_text(
        "✅ Giveaway started and posted to your channel!\n"
        "Countdown & progress will update automatically."
    )

    # inform admin about controls
    await query.message.reply_text(
        "When time ends, the bot will automatically pick winners and ask for approval."
    )

    return ConversationHandler.END
# ---------------- COUNTDOWN JOB ----------------

async def countdown_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    g: Giveaway = get_current_giveaway(context)
    if not g or not g.is_running():
        # stop this job if no active giveaway
        job = context.job
        if job:
            job.schedule_removal()
        return

    now_utc = datetime.now(timezone.utc)
    remaining = int((g.end_time - now_utc).total_seconds())
    if remaining <= 0:
        # Time finished -> pick winners
        g.finished = True
        job = context.job
        if job:
            job.schedule_removal()
        await finish_giveaway(context)
        return

    # update rotating icon index
    g.rotating_index += 1

    # edit channel message
    if g.message_chat_id and g.message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=g.message_chat_id,
                message_id=g.message_id,
                text=build_giveaway_post_text(g),
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]]
                ),
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning("Failed to edit giveaway message: %s", e)


# ---------------- FINISH & WINNERS ----------------

async def finish_giveaway(context: ContextTypes.DEFAULT_TYPE) -> None:
    g: Giveaway = get_current_giveaway(context)
    if not g:
        return

    # pick winners from participants (not in old_winners)
    candidates = [p for p in g.participants.values() if p.user_id not in g.old_winners]

    if not candidates:
        text = (
            "🏁🔥 GIVEAWAY CLOSED!\n"
            "But there were no valid participants to select winners."
        )
        # try send to channel
        if g.message_chat_id:
            try:
                await context.bot.send_message(chat_id=g.message_chat_id, text=text)
            except Exception:
                pass
        return

    random.shuffle(candidates)
    winners = candidates[: g.winners_count]

    # Save them as old winners globally
    global_old = context.bot_data.setdefault("global_old_winners", set())
    for w in winners:
        global_old.add(w.user_id)
        g.old_winners.add(w.user_id)

    # Build winners text
    lines = []
    lines.append("┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    lines.append("🎉 POWERPOINTBREAK — GIVEAWAY WINNER ANNOUNCED 🎉")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛")
    lines.append("")
    lines.append("🏆 Official Winners List:")
    lines.append("")
    for i, w in enumerate(winners, start=1):
        uname = f"@{w.username}" if w.username else "(no username)"
        lines.append(f"{i}) {uname} / {w.user_id}")
    lines.append("")
    lines.append(f"📌 Giveaway: {g.title}")
    lines.append("")
    lines.append("📢 Hosted By : Power Point Break")
    lines.append("👑 Admin     : @MinexxProo")

    winners_text = "\n".join(lines)

    # send approval message to super admin (or all admins)
    admins: Set[int] = get_admins(context)
    target_admin_id = None
    if admins:
        target_admin_id = list(admins)[0]

    if target_admin_id:
        keyboard = [
            [
                InlineKeyboardButton("✅ APPROVE & POST", callback_data="winners_approve"),
                InlineKeyboardButton("❌ REJECT", callback_data="winners_reject"),
            ]
        ]
        try:
            await context.bot.send_message(
                chat_id=target_admin_id,
                text=(
                    "🏁🔥 GIVEAWAY CLOSED!\n"
                    "🔍🔥 Choosing lucky winners…\n\n"
                    "Here is the draft winners list:\n\n" + winners_text +
                    "\n\nDo you want to post this to the channel?"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.warning("Failed to send winners to admin: %s", e)

    # also DM each winner
    for w in winners:
        try:
            await context.bot.send_message(
                chat_id=w.user_id,
                text=(
                    "🎉 CONGRATULATIONS! 🎉\n"
                    "You are one of the WINNERS of our Giveaway! 🏆\n\n"
                    "📩 Contact Admin to claim your reward:\n"
                    "👉 @MinexxProo"
                ),
            )
        except Exception:
            pass

    # store winners text for callback
    context.bot_data["last_winners_text"] = winners_text


async def winners_approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    g: Giveaway = get_current_giveaway(context)
    winners_text = context.bot_data.get("last_winners_text")

    if not g or not winners_text:
        await query.edit_message_text("No finished giveaway or winners data found.")
        return

    if query.data == "winners_reject":
        await query.edit_message_text("❌ Winners post rejected. Giveaway closed.")
        # final closing message to channel
        if g.message_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=g.message_chat_id,
                    text=(
                        "⛔️❌ GIVEAWAY CLOSED ❌⛔️\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        "📩 Need assistance?\n"
                        "👉 @MinexxProo\n\n"
                        "💫 Try your luck in the next giveaway!\n"
                        "❤️ Best wishes ❤️\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                )
            except Exception:
                pass
        return

    # APPROVE
    try:
        if g.message_chat_id:
            await context.bot.send_message(
                chat_id=g.message_chat_id,
                text=winners_text,
            )
            await context.bot.send_message(
                chat_id=g.message_chat_id,
                text=(
                    "⛔️❌ GIVEAWAY CLOSED ❌⛔️\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "📩 Need assistance?\n"
                    "👉 @MinexxProo\n\n"
                    "💫 Try your luck in the next giveaway!\n"
                    "❤️ Best wishes ❤️\n"
                    "━━━━━━━━━━━━━━━━━━━━━━━"
                ),
            )
    except Exception as e:
        logger.warning("Failed to post winners to channel: %s", e)

    await query.edit_message_text("✅ Winners posted to channel and giveaway closed.")


# ---------------- JOIN GIVEAWAY BUTTON ----------------

async def join_giveaway_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    await query.answer()

    # bot on check
    if not bot_is_on(context):
        await query.answer(
            "Bot is currently OFF. Contact admin: @MinexxProo",
            show_alert=True,
        )
        return

    g: Giveaway = get_current_giveaway(context)
    if not g or not g.is_running():
        await query.answer(
            "Giveaway is not running right now.",
            show_alert=True,
        )
        return

    # username required
    if not user.username:
        await query.answer(
            "You must set a public username in Telegram to join.",
            show_alert=True,
        )
        return

    # old winner check
    global_old: Set[int] = context.bot_data.setdefault("global_old_winners", set())
    if user.id in global_old or user.id in g.old_winners:
        await query.answer(
            "😔 Oops! You have already won this giveaway before,\n"
            "so you can no longer participate, dear member.\n\n"
            "🎉 Thanks for joining!\n\n"
            "🍀 Try again — more giveaways coming soon!\n"
            "💙 Stay with Power Point Break!\n\n"
            "📞 For support:\n👉 @MinexxProo",
            show_alert=True,
        )
        # notify admin
        admins = get_admins(context)
        for aid in admins:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=(
                        "⚠️ Old Winner Tried to Join!\n\n"
                        f"Username: @{user.username}\n"
                        f"UserID: {user.id}\n\n"
                        "Action Blocked Successfully."
                    ),
                )
            except Exception:
                pass
        return

    # duplicate participant check
    if user.id in g.participants:
        await query.answer(
            "⚠️❌ WARNING — DUPLICATE ENTRY ❌⚠️\n\n"
            "You already participated!\n"
            "Winner list will be published soon…",
            show_alert=True,
        )
        return

    # (optional) verification links — শুধু popup দেখাই, সত্যি চেক করছি না
    if g.verification_links:
        # Just remind user to join all links
        links_text = "\n".join(f"{i+1}) {url}" for i, url in enumerate(g.verification_links))
        await query.answer(
            "Please make sure you joined all required channels/groups before participating.",
            show_alert=True,
        )
        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=(
                    "⛔ ACCESS DENIED — VERIFICATION FAILED ⛔\n\n"
                    "You must join ALL required channels before participating:\n\n"
                    f"{links_text}\n\n"
                    "✔️ After joining all channels, tap JOIN GIVEAWAY again."
                ),
            )
        except Exception:
            pass
        # আমরা real check করছি না, তাই নিচে ওকেও অংশগ্রহণ করতে দেবো
        # যদি তুমি চাই পুরোপুরি block করতে, তাহলে এখানে return করে দেবে।
        # কিন্তু তুমি আগেই বলেছো শুধু দেখানোর জন্য fake verification, তাই allow করছি।
        # comment-out next "pass" and continue to add participant normally.
        # pass

    # add participant
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    g.participants[user.id] = Participant(
        user_id=user.id,
        username=user.username,
        full_name=full_name or user.username or "Unknown",
    )

    # user DM
    try:
        await context.bot.send_message(
            chat_id=user.id,
            text="🎉 You have successfully joined the giveaway!\nGood luck! 🍀",
        )
    except Exception:
        pass

    # admin notify
    admins = get_admins(context)
    for aid in admins:
        try:
            await context.bot.send_message(
                chat_id=aid,
                text=(
                    "👤 NEW PARTICIPANT JOINED\n\n"
                    f"Username: @{user.username}\n"
                    f"UserID: {user.id}"
                ),
            )
        except Exception:
            pass


# ---------------- CANCEL COMMAND ----------------

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if is_admin(user, context):
        await update.message.reply_text("❌ Current setup cancelled.")
    return ConversationHandler.END


# ---------------- MAIN & APPLICATION ----------------

def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # ensure base flags
    application.bot_data.setdefault("bot_on", True)
    application.bot_data.setdefault("admins", set())
    application.bot_data.setdefault("global_old_winners", set())

    # Conversation handler for new giveaway
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("newgiveaway", newgiveaway_command),
            CallbackQueryHandler(panel_new_giveaway_button, pattern="^panel_new_giveaway$"),
        ],
        states={
            CG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_title)],
            CG_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_prize)],
            CG_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_time)],
            CG_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winners)],
            CG_OLD_CHOICE: [CallbackQueryHandler(cg_old_choice)],
            CG_OLD_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_old_list)],
            CG_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_rules)],
            CG_VERIF_LINKS: [
                CallbackQueryHandler(cg_verif_choice, pattern="^verif_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cg_verif_links),
            ],
            CG_SPEED: [CallbackQueryHandler(cg_speed, pattern="^speed_")],
            CG_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_channel)],
            CG_CONFIRM: [CallbackQueryHandler(cg_confirm, pattern="^confirm_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    # basic command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", panel))
    application.add_handler(CommandHandler("off", bot_off))
    application.add_handler(CommandHandler("on", bot_on))
    application.add_handler(CommandHandler("addadmin", addadmin))
    application.add_handler(CommandHandler("removeadmin", removeadmin))
    application.add_handler(CommandHandler("realp", realp))
    application.add_handler(CommandHandler("cancel", cancel))

    # callback handlers
    application.add_handler(CallbackQueryHandler(toggle_bot_button, pattern="^toggle_bot$"))
    application.add_handler(CallbackQueryHandler(join_giveaway_callback, pattern="^join_giveaway$"))
    application.add_handler(CallbackQueryHandler(winners_approval_callback, pattern="^winners_"))

    # conversation
    application.add_handler(conv_handler)

    # run
    application.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
