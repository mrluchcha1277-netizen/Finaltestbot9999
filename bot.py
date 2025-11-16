from typing import Optional, Dict, Set, List
import logging
import random
import re
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# ---------------- CONFIG ----------------
BOT_TOKEN = "8358046522:AAFBcxWEgReqSdCZLyjp7ur4KooiX8Has6o"   # <-- এখানে তোমার BotFather token বসাবে
SUPER_ADMIN_USERNAME = "MinexxProo"     # @ ছাড়া ইউজারনেম, যেমন "MinexxProo"

BD_TZ = timezone(timedelta(hours=6))    # BD time

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# -------------- CONVERSATION STATES --------------
(
    CG_TITLE,
    CG_PRIZE,
    CG_WINNERS,
    CG_DURATION,
    CG_SPEED,
    CG_VERIF_LINKS,
    CG_WINNER_MODE,
    CG_BAN_OLD_CHOICE,
    CG_OLD_WINNER_LIST,
    CG_RULES,
    CG_TARGET_CHANNEL,
    CG_CONFIRM_POST,
) = range(12)

# -------------- HELPERS & STORAGE --------------

def parse_duration_to_seconds(text: str) -> Optional[int]:
    """
    10s / 10m / 10h / 1day / 3day => seconds
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


def build_progress_bar(percent: int) -> str:
    blocks = 10
    filled = int(blocks * percent / 100)
    empty = blocks - filled
    return "▰" * filled + "▱" * empty


def format_giveaway_post(g: dict, remaining: int, percent: int) -> str:
    # remaining -> seconds
    if remaining < 0:
        remaining = 0
    h = remaining // 3600
    m = (remaining % 3600) // 60
    s = remaining % 60
    time_str = f"{h:02d}h {m:02d}m {s:02d}s"

    progress_bar = build_progress_bar(percent)

    lines = []
    lines.append("✨ POWER POINT BREAK — OFFICIAL GIVEAWAY ✨\n")
    lines.append(f"📌 Title: {g['title']}")
    lines.append(f"🎁 Prize: {g['prize']}\n")
    lines.append(f"🏆 Total Winners: {g['total_winners']}")
    lines.append(f"🤖 Winner Mode: {g['winner_mode']}")
    lines.append(f"👥 Participate Count: {len(g['participants'])}")
    lines.append(f"🚫 Old Winners Blocked: {len(g['old_winners'])} user(s)\n")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("⏳ LIVE COUNTDOWN & PROGRESS")
    lines.append("━━━━━━━━━━━━━━━━━━\n")
    lines.append(f"🕒 Time Left: {time_str} (BD TIME)\n")
    lines.append("🎁 POWER POINT BREAK — GIVEAWAY LOADING 💐")
    lines.append(f"{progress_bar} {percent}%\n")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("📜 RULES")
    lines.append("━━━━━━━━━━━━━━━━━━")
    if g["rules"]:
        lines.append(g["rules"])
    else:
        lines.append("No specific rules.\n")
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append(f"📢 Hosted By : Power Point Break")
    lines.append(f"👑 Admin     : @{g['admin_username']}\n")
    lines.append("💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐")
    lines.append("[ 🎁 JOIN GIVEAWAY ]")

    return "\n".join(lines)


def get_admins(context: ContextTypes.DEFAULT_TYPE) -> Set[int]:
    bot_data = context.application.bot_data
    return bot_data.setdefault("admins", set())


def is_super_admin(user) -> bool:
    return bool(user.username) and user.username.lower() == SUPER_ADMIN_USERNAME.lower()


def bot_is_on(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.application.bot_data.get("bot_on", True)


def get_current_giveaway(context: ContextTypes.DEFAULT_TYPE) -> Optional[dict]:
    return context.application.bot_data.get("current_giveaway")


# -------------- COMMAND HANDLERS --------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_data = context.application.bot_data
    admins = get_admins(context)

    # প্রথমবার /start এ সুপার অ্যাডমিন সেট
    if bot_data.get("super_admin_id") is None and is_super_admin(user):
        bot_data["super_admin_id"] = user.id
        admins.add(user.id)

    if user.id in admins:
        status = "ON ✅" if bot_is_on(context) else "OFF ❌"
        text = (
            "🛠️✨ WELCOME TO YOUR BOT ✨🛠️\n\n"
            f"👑 Admin: @{user.username}\n"
            "⚙️ Setup Your Giveaway Bot Now!\n\n"
            f"Current Status: {status}\n\n"
            "/panel - Show full admin command list\n"
        )
        await update.message.reply_text(text)
    else:
        await update.message.reply_text(
            "Hi Dear!\n\n"
            "This is POWER POINT BREAK — GIVEAWAY BOT.\n"
            "Only authorized admins can control this bot.\n\n"
            "For any support, contact:\n"
            f"👉 @{SUPER_ADMIN_USERNAME}"
        )


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return

    text = (
        "🛠 POWER POINT BREAK — ADMIN PANEL\n\n"
        "📜 ALL ADMIN COMMANDS:\n"
        "------------------------------\n"
        "/start - Initialize / reopen admin\n"
        "/panel - Show this command list\n"
        "/newgiveaway - Create a new giveaway\n"
        "/on - Turn the bot ON\n"
        "/off - Turn the bot OFF\n"
        "/reset - Reset current giveaway & data\n"
        "/addadmin <user_id> - Add new admin\n"
        "/removeadmin <user_id> - Remove admin\n"
        "------------------------------\n"
        "Shortcut buttons coming from client app only.\n"
    )
    await update.message.reply_text(text)


async def cmd_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return

    context.application.bot_data["bot_on"] = True
    await update.message.reply_text("Bot status changed to: ON ✅")


async def cmd_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return

    context.application.bot_data["bot_on"] = False
    await update.message.reply_text("Bot status changed to: OFF ❌")


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return

    # বেসিক ক্লিন
    bd = context.application.bot_data
    bd.pop("current_giveaway", None)
    bd.pop("duplicate_clicks", None)
    bd.pop("old_winner_clicks", None)
    bd.pop("join_success_clicks", None)
    bd.pop("winner_job", None)

    await update.message.reply_text("✅ All giveaway data reset. You can start a new one with /newgiveaway")


async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Invalid ID. Please send numeric user_id.\nExample: /addadmin 5692210187")
        return

    new_id = int(context.args[0])
    admins.add(new_id)
    await update.message.reply_text(f"✅ Added new admin with ID: {new_id}")


async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("❌ Invalid ID. Use: /removeadmin 123456789")
        return

    rem_id = int(context.args[0])
    if rem_id in admins:
        admins.remove(rem_id)
        await update.message.reply_text(f"✅ Removed admin with ID: {rem_id}")
    else:
        await update.message.reply_text("⚠ This ID is not in admin list.")


# -------------- NEW GIVEAWAY FLOW --------------

async def new_giveaway_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admins = get_admins(context)
    if user.id not in admins:
        await update.message.reply_text("⛔ You are not an admin.")
        return ConversationHandler.END

    if not bot_is_on(context):
        await update.message.reply_text("⚠ Bot is currently OFF. Turn ON first with /on")
        return ConversationHandler.END

    context.user_data["cg"] = {
        "admin_id": user.id,
        "admin_username": user.username or "UnknownAdmin",
    }

    await update.message.reply_text("📝 SET YOUR GIVEAWAY TITLE:")
    return CG_TITLE


async def cg_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cg"]["title"] = update.message.text.strip()
    await update.message.reply_text("🎁 NOW SET THE PRIZE:\n\nExample: ChatGPT Plus Premium Full Access")
    return CG_PRIZE


async def cg_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cg"]["prize"] = update.message.text.strip()
    await update.message.reply_text("🏆 Enter total winners (number):")
    return CG_WINNERS


async def cg_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Please send a valid positive number, e.g. 10")
        return CG_WINNERS
    context.user_data["cg"]["total_winners"] = int(text)

    msg = (
        "⏳ NOW SET YOUR GIVEAWAY TIME\n\n"
        "Use:\n"
        "10s  = 10 seconds\n"
        "10m  = 10 minutes\n"
        "10h  = 10 hours\n"
        "1day = 1 day\n"
        "3day = 3 days\n\n"
        "🕒 BD Time Zone (GMT+6)\n"
    )
    await update.message.reply_text(msg)
    return CG_DURATION


async def cg_duration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    seconds = parse_duration_to_seconds(text)
    if seconds is None or seconds < 10:
        await update.message.reply_text("❌ Invalid format. Example: 10m, 2h, 1day. Minimum 10s.")
        return CG_DURATION

    context.user_data["cg"]["duration_seconds"] = seconds

    msg = (
        "⚡ Select countdown update speed:\n\n"
        "1) Fast mode: 1 second\n"
        "2) Normal mode: 3 seconds\n"
        "3) Slow mode: 5 seconds\n\n"
        "Send: FAST / NORMAL / SLOW"
    )
    await update.message.reply_text(msg)
    return CG_SPEED


async def cg_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text == "FAST":
        interval = 1
    elif text == "NORMAL":
        interval = 3
    elif text == "SLOW":
        interval = 5
    else:
        await update.message.reply_text("❌ Send FAST / NORMAL / SLOW")
        return CG_SPEED

    context.user_data["cg"]["speed_seconds"] = interval

    msg = (
        "🔗 NOW SET YOUR VERIFICATION LINK(S)\n\n"
        "Send channel/group links or @username one per message.\n"
        "Type DONE when finished, or SKIP to skip verification."
    )
    context.user_data["cg"]["verification_links"] = []
    await update.message.reply_text(msg)
    return CG_VERIF_LINKS


async def cg_verif_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    cg = context.user_data["cg"]

    if text.upper() == "SKIP":
        cg["verification_links"] = []
        await update.message.reply_text("🤖 Winner mode? (This version supports only AUTO)\nSend: AUTO")
        return CG_WINNER_MODE

    if text.upper() == "DONE":
        if not cg["verification_links"]:
            await update.message.reply_text("No links saved. Using no verification.\nSend: AUTO")
        else:
            await update.message.reply_text("Links saved.\nSend winner mode: AUTO")
        return CG_WINNER_MODE

    cg["verification_links"].append(text)
    await update.message.reply_text("Link saved. Send another, or DONE / SKIP.")
    return CG_VERIF_LINKS


async def cg_winner_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    if text != "AUTO":
        await update.message.reply_text("Only AUTO supported now. Please send: AUTO")
        return CG_WINNER_MODE

    context.user_data["cg"]["winner_mode"] = "AUTO"

    kb = [
        [
            InlineKeyboardButton("🚫 Ban old winners", callback_data="ban_old_yes"),
            InlineKeyboardButton("Skip", callback_data="ban_old_no"),
        ]
    ]
    await update.message.reply_text(
        "Do you want to **BAN OLD WINNERS** from this giveaway?",
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return CG_BAN_OLD_CHOICE


async def cg_ban_old_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cg = context.user_data["cg"]

    if query.data == "ban_old_yes":
        cg["ban_old"] = True
        cg["old_winners_raw"] = []
        await query.message.reply_text(
            "Please send OLD winners list.\n\n"
            "Format (one per line):\n"
            "@Username/UserID\n\n"
            "Example:\n"
            "@MinexxProo/1701097178\n\n"
            "Send ALL, then type: DONE"
        )
        return CG_OLD_WINNER_LIST
    else:
        cg["ban_old"] = False
        cg["old_winners_raw"] = []
        cg["old_winners"] = set()
        await query.message.reply_text(
            "Now send your RULES text.\nType SKIP to skip."
        )
        return CG_RULES


async def cg_old_winner_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    cg = context.user_data["cg"]

    if text.upper() == "DONE":
        old_set: Set[int] = set()
        for line in cg["old_winners_raw"]:
            line = line.strip()
            if not line:
                continue
            if "/" in line:
                try:
                    _, uid = line.split("/", 1)
                    uid = uid.strip()
                    if uid.isdigit():
                        old_set.add(int(uid))
                except ValueError:
                    continue
        cg["old_winners"] = old_set
        await update.message.reply_text(
            f"Saved {len(old_set)} old winners.\n\nNow send your RULES text.\nType SKIP to skip."
        )
        return CG_RULES

    cg["old_winners_raw"].append(text)
    await update.message.reply_text("Line saved. Send next, or DONE.")
    return CG_OLD_WINNER_LIST


async def cg_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.upper() == "SKIP":
        context.user_data["cg"]["rules"] = ""
    else:
        context.user_data["cg"]["rules"] = text

    await update.message.reply_text(
        "Send your MAIN CHANNEL username or link.\nExample: @PowerPointBreak"
    )
    return CG_TARGET_CHANNEL


async def cg_target_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["cg"]["target_channel"] = text

    cg = context.user_data["cg"]
    cg.setdefault("old_winners", set())

    # temporary giveaway object to preview
    g = {
        "title": cg["title"],
        "prize": cg["prize"],
        "total_winners": cg["total_winners"],
        "winner_mode": cg["winner_mode"],
        "participants": set(),
        "old_winners": cg["old_winners"],
        "rules": cg["rules"],
        "admin_username": cg["admin_username"],
    }

    preview = format_giveaway_post(g, cg["duration_seconds"], 0)

    kb = [
        [
            InlineKeyboardButton("✅ YES, POST IT", callback_data="confirm_post_yes"),
            InlineKeyboardButton("❌ NO, CANCEL", callback_data="confirm_post_no"),
        ]
    ]
    await update.message.reply_text(
        "Here is the PREVIEW of your giveaway post:\n\n" + preview,
        reply_markup=InlineKeyboardMarkup(kb),
    )
    return CG_CONFIRM_POST


async def cg_confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cg = context.user_data.get("cg")
    if not cg:
        await query.message.reply_text("❌ Setup data lost. Please start again with /newgiveaway")
        return ConversationHandler.END

    if query.data == "confirm_post_no":
        await query.message.reply_text("❌ Giveaway creation cancelled.")
        context.user_data.pop("cg", None)
        return ConversationHandler.END

    # YES: create real giveaway and post to channel
    try:
        target = cg["target_channel"]
        chat = await context.bot.get_chat(target)
        channel_id = chat.id
    except Exception as e:
        logger.exception("Channel fetch error: %s", e)
        await query.message.reply_text(
            "❌ Failed to access the channel. Make sure the bot is admin there."
        )
        return ConversationHandler.END

    now = datetime.now(BD_TZ)
    duration = cg["duration_seconds"]
    end_time = now + timedelta(seconds=duration)

    giveaway = {
        "title": cg["title"],
        "prize": cg["prize"],
        "total_winners": cg["total_winners"],
        "winner_mode": cg["winner_mode"],
        "participants": set(),              # user_id set
        "old_winners": cg["old_winners"],
        "rules": cg["rules"],
        "admin_username": cg["admin_username"],
        "admin_id": cg["admin_id"],
        "verification_links": cg["verification_links"],
        "duration_seconds": duration,
        "start_time": now,
        "end_time": end_time,
        "speed_seconds": cg["speed_seconds"],
        "channel_id": channel_id,
        "message_id": None,                 # পরে সেট হবে
    }

    text = format_giveaway_post(giveaway, duration, 0)
    join_button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]]
    )

    try:
        msg = await context.bot.send_message(
            chat_id=channel_id,
            text=text,
            reply_markup=join_button,
        )
        giveaway["message_id"] = msg.message_id
    except Exception as e:
        logger.exception("Channel send error: %s", e)
        await query.message.reply_text(
            "❌ Failed to send message to channel.\nCheck that the bot is admin there."
        )
        return ConversationHandler.END

    # save current giveaway
    bd = context.application.bot_data
    bd["current_giveaway"] = giveaway
    bd["duplicate_clicks"] = {}
    bd["old_winner_clicks"] = {}
    bd["join_success_clicks"] = {}

    # schedule countdown updater
    job = context.job_queue.run_repeating(
        countdown_job,
        interval=cg["speed_seconds"],
        first= cg["speed_seconds"],
    )
    bd["winner_job"] = job

    await query.message.reply_text("✅ Giveaway started and posted to your channel!")
    context.user_data.pop("cg", None)
    return ConversationHandler.END


async def countdown_job(context: ContextTypes.DEFAULT_TYPE):
    bd = context.application.bot_data
    g = bd.get("current_giveaway")
    if not g:
        return

    now = datetime.now(BD_TZ)
    total = g["duration_seconds"]
    remaining = int((g["end_time"] - now).total_seconds())
    elapsed = total - remaining
    if elapsed < 0:
        elapsed = 0
    if remaining < 0:
        remaining = 0
    percent = int(elapsed * 100 / total) if total > 0 else 100
    if percent > 100:
        percent = 100

    try:
        text = format_giveaway_post(g, remaining, percent)
        join_button = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]]
        )
        await context.bot.edit_message_text(
            chat_id=g["channel_id"],
            message_id=g["message_id"],
            text=text,
            reply_markup=join_button,
        )
    except Exception:
        # ignore edit errors (e.g., message changed manually)
        pass

    # time finished -> stop job & pick winners
    if remaining <= 0:
        job = bd.get("winner_job")
        if job:
            job.schedule_removal()
            bd["winner_job"] = None
        await finish_giveaway_and_choose_winners(context)


async def finish_giveaway_and_choose_winners(context: ContextTypes.DEFAULT_TYPE):
    bd = context.application.bot_data
    g = bd.get("current_giveaway")
    if not g:
        return

    participants = list(g["participants"])
    random.shuffle(participants)

    # old winners remove if needed
    if g["old_winners"]:
        participants = [uid for uid in participants if uid not in g["old_winners"]]

    winners = participants[: g["total_winners"]]
    if not winners:
        await context.bot.send_message(
            chat_id=g["channel_id"],
            text="🏁🔥 GIVEAWAY CLOSED!\nBut no valid participants were found.",
        )
        bd["current_giveaway"] = None
        return

    # winner text
    lines = []
    lines.append("┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓")
    lines.append("🎉 POWERPOINTBREAK — GIVEAWAY WINNER ANNOUNCED 🎉")
    lines.append("┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n")
    lines.append("🏆 Official Winners List:\n")
    for i, uid in enumerate(winners, start=1):
        try:
            user = await context.bot.get_chat(uid)
            uname = f"@{user.username}" if user.username else user.full_name
        except Exception:
            uname = f"User {uid}"
        lines.append(f"{i}) {uname} / {uid}")
    lines.append("\n📢 Hosted By : Power Point Break")
    lines.append(f"👑 Admin     : @{g['admin_username']}")

    await context.bot.send_message(
        chat_id=g["channel_id"],
        text="\n".join(lines),
    )

    # DM winners
    for uid in winners:
        try:
            await context.bot.send_message(
                chat_id=uid,
                text=(
                    "🎉 CONGRATULATIONS! 🎉\n"
                    "You are one of the WINNERS of our Giveaway! 🏆\n\n"
                    f"📩 Contact Admin to claim your reward:\n👉 @{g['admin_username']}"
                ),
            )
        except Exception:
            pass

    bd["current_giveaway"] = None


# ---------- POPUP / ALERT HELPERS ----------

async def send_temporary_channel_message(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    seconds: int = 6,
):
    msg = await context.bot.send_message(chat_id=chat_id, text=text)
    context.job_queue.run_once(
        delete_message_job,
        when=seconds,
        data={"chat_id": chat_id, "message_id": msg.message_id},
    )


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data
    try:
        await context.bot.delete_message(
            chat_id=data["chat_id"],
            message_id=data["message_id"],
        )
    except Exception:
        pass


# -------------- JOIN GIVEAWAY HANDLER --------------

async def handle_join_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()  # basic ack

    bd = context.application.bot_data
    if not bot_is_on(context):
        return

    g = get_current_giveaway(context)
    if not g:
        return

    user_id = user.id
    channel_id = g["channel_id"]

    # ----- duplicate entry limit (2 times popup) -----
    duplicate_clicks: Dict[int, int] = bd.setdefault("duplicate_clicks", {})
    old_winner_clicks: Dict[int, int] = bd.setdefault("old_winner_clicks", {})
    join_success_clicks: Dict[int, int] = bd.setdefault("join_success_clicks", {})

    # already joined
    if user_id in g["participants"]:
        count = duplicate_clicks.get(user_id, 0)
        if count < 2:
            duplicate_clicks[user_id] = count + 1
            text = (
                "⚠️❌ WARNING — DUPLICATE ENTRY ❌⚠️\n\n"
                "You already participated!\n"
                "Winner list will be published soon…"
            )
            await send_temporary_channel_message(context, channel_id, text, seconds=7)
        return

    # old winner blocked
    if user_id in g["old_winners"]:
        count = old_winner_clicks.get(user_id, 0)
        if count < 2:
            old_winner_clicks[user_id] = count + 1
            text = (
                "😔 Oops! You have already won this giveaway before,\n"
                "so you can no longer participate, dear member.\n\n"
                "🍀 Try Next — giveaways coming soon!\n"
                "💙 Stay with Power Point Break!"
            )
            await send_temporary_channel_message(context, channel_id, text, seconds=8)
        return

    # verification channels
    if g["verification_links"]:
        not_joined = []
        for link in g["verification_links"]:
            try:
                if link.startswith("@"):
                    chat = await context.bot.get_chat(link)
                    vchat_id = chat.id
                else:
                    vchat_id = link
                member = await context.bot.get_chat_member(vchat_id, user_id)
                if member.status not in ("member", "administrator", "creator"):
                    not_joined.append(link)
            except Exception:
                not_joined.append(link)

        if not_joined:
            lines = ["⛔ ACCESS DENIED — VERIFICATION FAILED ⛔", ""]
            lines.append("You must join ALL required channels before participating:\n")
            for i, lnk in enumerate(g["verification_links"], start=1):
                lines.append(f"{i}) {lnk}")
            lines.append("\n✔️ After joining all channels, try again!")
            await send_temporary_channel_message(
                context, channel_id, "\n".join(lines), seconds=8
            )
            return

    # success join
    g["participants"].add(user_id)

    count = join_success_clicks.get(user_id, 0)
    if count < 2:
        join_success_clicks[user_id] = count + 1
        uname = f"@{user.username}" if user.username else user.full_name
        text = (
            "━━━━━━━━━━━━━━━\n"
            "✅ GIVEAWAY JOIN SUCCESSFUL!\n"
            "━━━━━━━━━━━━━━━\n\n"
            f"🎉 {uname}\n"
            f"🆔 User ID: {user_id}\n\n"
            "You have successfully joined the giveaway! 🎁\n"
            "The winner list will be announced soon.\n\n"
            "📢 Stay active & good luck! 🍀 Stay Power Point Break\n"
            "━━━━━━━━━━━━━━━"
        )
        await send_temporary_channel_message(context, channel_id, text, seconds=6)


# -------------- MAIN ENTRY --------------

def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    # basic command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("panel", panel))
    application.add_handler(CommandHandler("on", cmd_on))
    application.add_handler(CommandHandler("off", cmd_off))
    application.add_handler(CommandHandler("reset", cmd_reset))
    application.add_handler(CommandHandler("addadmin", cmd_addadmin))
    application.add_handler(CommandHandler("removeadmin", cmd_removeadmin))

    # new giveaway conversation
    conv = ConversationHandler(
        entry_points=[CommandHandler("newgiveaway", new_giveaway_entry)],
        states={
            CG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_title)],
            CG_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_prize)],
            CG_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winners)],
            CG_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_duration)],
            CG_SPEED: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_speed)],
            CG_VERIF_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_verif_links)],
            CG_WINNER_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winner_mode)],
            CG_BAN_OLD_CHOICE: [CallbackQueryHandler(cg_ban_old_choice, pattern="^ban_old_")],
            CG_OLD_WINNER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_old_winner_list)],
            CG_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_rules)],
            CG_TARGET_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_target_channel)],
            CG_CONFIRM_POST: [CallbackQueryHandler(cg_confirm_post, pattern="^confirm_post_")],
        },
        fallbacks=[CommandHandler("reset", cmd_reset)],
        allow_reentry=True,
    )

    application.add_handler(conv)

    # join button handler
    application.add_handler(CallbackQueryHandler(handle_join_button, pattern="^join_giveaway$"))

    # RUN (GSM app শুধু python bot.py চালাবে)
    application.run_polling()


if __name__ == "__main__":
    main()
