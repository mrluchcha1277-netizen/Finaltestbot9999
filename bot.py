import logging
import random
import re
from datetime import timedelta

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
)

# ----------------- CONFIG -----------------
BOT_TOKEN = "8385717982:AAEQRbakA7kpY7vg1j9rNbzbRf_j-9Cm-XU"   # <-- এখানে নিজের Bot Token বসাও
SUPER_ADMIN_USERNAME = "MinexxProo"     # @ ছাড়া শুধু ইউজারনেম
# -----------------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Conversation states
(
    CG_TITLE,
    CG_PRIZE,
    CG_TIME,
    CG_WINNERS,
    CG_VERIF_LINKS,
    CG_WINNER_MODE,
    CG_BAN_OLD_CHOICE,
    CG_OLD_WINNER_LIST,
    CG_CONFIRM_POST,
    MANUAL_WINNER_WAIT_LIST,
) = range(10)

# Helpers ---------------------------------------------------


def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is in admin list."""
    user = update.effective_user
    bot_data = context.bot_data
    admins = bot_data.setdefault("admins", set())
    super_admin = bot_data.get("super_admin_id")

    if super_admin is None:
        # প্রথমবার start এ super admin সেট করা হবে
        if user.username and user.username.lower() == SUPER_ADMIN_USERNAME.lower():
            bot_data["super_admin_id"] = user.id
            admins.add(user.id)
            return True

    return user.id in admins


def bot_is_on(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return context.bot_data.get("bot_on", False)


def get_current_giveaway(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data.get("current_giveaway")


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


# ----------------- COMMAND HANDLERS -----------------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    bot_data = context.bot_data
    admins = bot_data.setdefault("admins", set())

    # Super admin প্রথমবার সেট
    if (
        bot_data.get("super_admin_id") is None
        and user.username
        and user.username.lower() == SUPER_ADMIN_USERNAME.lower()
    ):
        bot_data["super_admin_id"] = user.id
        admins.add(user.id)

    if user.id in admins:
        # Admin panel view
        status = "ON ✅" if bot_is_on(context) else "OFF ❌"
        text = (
            "💐🌟🎉 WELCOME TO YOUR BOT 🎉🌟💐\n\n"
            f"👑 Admin: @{user.username}\n"
            "🛠 Setup Your Giveaway Bot Now!\n\n"
            f"Current Status: {status}\n\n"
            "🔹 /on - Turn bot ON\n"
            "🔹 /off - Turn bot OFF\n"
            "🔹 /newgiveaway - Create new giveaway\n"
            "🔹 /realp - Show real participants\n"
            "🔹 /choosewinner - (Manual mode) set winners\n"
            "🔹 /addadmin @user - Add new admin\n"
            "🔹 /removeadmin @user - Remove admin\n"
        )
        await update.effective_message.reply_text(text)
    else:
        # Non-admin response
        text = (
            f"Hi Dear @{user.username}\n"
            f"UserID: {user.id}\n\n"
            "This is the Power Point Break Giveaway Bot.\n"
            "No one except the authorized admin can use this bot.\n\n"
            "For any concerns or support, please contact the admin:\n"
            "👉 @MinexxProo"
        )
        await update.effective_message.reply_text(text)
        # Optional log to super admin
        super_admin_id = context.bot_data.get("super_admin_id")
        if super_admin_id:
            await context.bot.send_message(
                super_admin_id,
                f"⚠️ Non-admin tried to use /start\n\n"
                f"Username: @{user.username}\nUserID: {user.id}",
            )


async def cmd_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    context.bot_data["bot_on"] = True
    await update.effective_message.reply_text(
        "✅ Bot has been turned ON.\nAll giveaway features are now active."
    )


async def cmd_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    context.bot_data["bot_on"] = False
    await update.effective_message.reply_text(
        "⛔ Bot has been turned OFF.\nUse /on to enable it again."
    )


async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(
            "Usage:\n/addadmin @username\nঅথবা কাওকে reply করে /addadmin লিখুন।"
        )
        return

    target_user = None

    if context.args:
        username = context.args[0].lstrip("@")
        chat = await context.bot.get_chat(username)
        target_user = chat
    else:
        target_user = update.message.reply_to_message.from_user

    admins = context.bot_data.setdefault("admins", set())
    admins.add(target_user.id)

    await update.message.reply_text(
        f"✅ New admin added successfully!\n\nUsername: @{target_user.username}"
    )
    # Notify new admin
    try:
        await context.bot.send_message(
            target_user.id,
            "🎉 You have been added as an ADMIN of Power Point Break Giveaway Bot!\n\n"
            "You can now manage giveaways and control the bot.\nUse /start to begin.",
        )
    except Exception as e:
        logger.warning("Could not DM new admin: %s", e)


async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    super_admin_id = context.bot_data.get("super_admin_id")
    if super_admin_id is None or update.effective_user.id != super_admin_id:
        await update.message.reply_text(
            "Only the main admin can remove other admins."
        )
        return

    if not context.args and not update.message.reply_to_message:
        await update.message.reply_text(
            "Usage:\n/removeadmin @username\nঅথবা কাওকে reply করে /removeadmin লিখুন।"
        )
        return

    target_user = None

    if context.args:
        username = context.args[0].lstrip("@")
        chat = await context.bot.get_chat(username)
        target_user = chat
    else:
        target_user = update.message.reply_to_message.from_user

    admins = context.bot_data.setdefault("admins", set())
    if target_user.id == super_admin_id:
        await update.message.reply_text("❌ You cannot remove the main super admin.")
        return

    if target_user.id in admins:
        admins.remove(target_user.id)
        await update.message.reply_text(
            f"✅ Admin removed successfully!\n\nUsername: @{target_user.username}"
        )
        try:
            await context.bot.send_message(
                target_user.id,
                "⚠️ Your admin access to Power Point Break Giveaway Bot has been removed.",
            )
        except Exception as e:
            logger.warning("Could not DM removed admin: %s", e)
    else:
        await update.message.reply_text("User is not an admin.")


# ------------- NEW GIVEAWAY CONVERSATION -----------------


async def newgiveaway_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return ConversationHandler.END
    if not bot_is_on(context):
        await update.message.reply_text("⚠️ Bot is currently OFF. Use /on first.")
        return ConversationHandler.END

    context.user_data["cg"] = {}
    await update.message.reply_text(
        "📝 SET YOUR GIVEAWAY TITLE\n\nPlease enter your giveaway title."
    )
    return CG_TITLE


async def cg_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cg"]["title"] = update.message.text.strip()
    await update.message.reply_text(
        "🎉 Title Saved Successfully!\n\n"
        "🎁 NOW SET YOUR GIVEAWAY PRIZE\nPlease enter the prize name."
    )
    return CG_PRIZE


async def cg_prize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cg"]["prize"] = update.message.text.strip()
    await update.message.reply_text(
        "🎁 Prize Saved Successfully!\n\n"
        "⏳ NOW SET YOUR GIVEAWAY TIME\n\n"
        "Use:\n10s = 10 seconds\n10m = 10 minutes\n10h = 10 hours\n1day = 1 day\n3day = 3 days\n\n"
        "🕒 BD Time Zone (GMT+6)"
    )
    return CG_TIME


async def cg_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    seconds = parse_duration_to_seconds(txt)
    if seconds is None:
        await update.message.reply_text(
            "⛔ Invalid time format.\nExample: 10s, 10m, 1day\nTry again:"
        )
        return CG_TIME
    context.user_data["cg"]["duration"] = seconds
    await update.message.reply_text(
        "⏳ Time Saved Successfully!\n\n"
        "Now tell me how many winners should be selected.\n"
        "Enter a number between 1 and 100000."
    )
    return CG_WINNERS


async def cg_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n = int(update.message.text.strip())
        if n < 1 or n > 100000:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⛔ Invalid number.\nPlease send a number between 1 and 100000."
        )
        return CG_WINNERS

    context.user_data["cg"]["winner_count"] = n
    await update.message.reply_text(
        "🎉 Winner Count Saved!\n"
        f"Total Winners: {n}\n\n"
        "🔗 NOW SET YOUR VERIFICATION LINKS\n\n"
        "Send channel/group links that users MUST join before participating.\n"
        "You can send multiple links, one per message.\n\n"
        "✅ When you are done, send: DONE\n"
        "⏭ If you don't want any verification, send: SKIP"
    )
    context.user_data["cg"]["verification_links"] = []
    return CG_VERIF_LINKS


async def cg_verif_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.upper() == "SKIP":
        context.user_data["cg"]["verification_links"] = []
        await update.message.reply_text(
            "⏭ Verification skipped!\n\nNow choose winner mode:\n"
            "🤖 Auto Winner (bot will select random winners)\n"
            "🧑‍🏫 Manual Winner (you choose winners manually)\n\n"
            "Send: AUTO or MANUAL"
        )
        return CG_WINNER_MODE

    if txt.upper() == "DONE":
        if not context.user_data["cg"]["verification_links"]:
            await update.message.reply_text(
                "You didn't send any links.\nIf you don't want verification, send: SKIP.\n"
                "Otherwise send at least one link."
            )
            return CG_VERIF_LINKS
        await update.message.reply_text(
            "🔗 All verification links saved.\n\n"
            "Now choose winner mode:\n"
            "🤖 Auto Winner (bot will select random winners)\n"
            "🧑‍🏫 Manual Winner (you choose winners manually)\n\n"
            "Send: AUTO or MANUAL"
        )
        return CG_WINNER_MODE

    # Normal link
    context.user_data["cg"]["verification_links"].append(txt)
    await update.message.reply_text(
        f"✅ Link added:\n{txt}\n\n"
        "Send more, or send DONE/ SKIP."
    )
    return CG_VERIF_LINKS


async def cg_winner_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt not in ("auto", "manual"):
        await update.message.reply_text("Please send: AUTO or MANUAL")
        return CG_WINNER_MODE

    context.user_data["cg"]["winner_mode"] = "auto" if txt == "auto" else "manual"

    await update.message.reply_text(
        "Do you want to block old giveaway winners from joining this giveaway?\n\n"
        "Send:\nBAN  = Ban Old Winners\nSKIP = Let everyone join (no old winner filter)"
    )
    return CG_BAN_OLD_CHOICE


async def cg_ban_old_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt == "ban":
        context.user_data["cg"]["ban_old"] = True
        context.user_data["cg"]["old_winners"] = {}
        await update.message.reply_text(
            "Please send me the list of OLD giveaway winners.\n\n"
            "Format (one per line):\n@Username/UserID\n\n"
            "Example:\n@MinexxProo/83766867\n\n"
            "When finished, send: DONE"
        )
        return CG_OLD_WINNER_LIST
    elif txt == "skip":
        context.user_data["cg"]["ban_old"] = False
        context.user_data["cg"]["old_winners"] = {}
        return await cg_confirm_preview(update, context)
    else:
        await update.message.reply_text("Please send BAN or SKIP")
        return CG_BAN_OLD_CHOICE


async def cg_old_winner_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    if txt.upper() == "DONE":
        # Done with list
        return await cg_confirm_preview(update, context)

    # Parse @username/userid
    try:
        uname, uid = txt.split("/", 1)
        uname = uname.strip().lstrip("@")
        uid = int(uid.strip())
        context.user_data["cg"]["old_winners"][uid] = uname
        await update.message.reply_text(
            f"✅ Saved old winner: @{uname} (ID: {uid})\n"
            "Send more, or send DONE."
        )
    except Exception:
        await update.message.reply_text(
            "❌ Invalid format.\nCorrect example: @MinexxProo/83766867"
        )
    return CG_OLD_WINNER_LIST


async def cg_confirm_preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data["cg"]
    title = data["title"]
    prize = data["prize"]
    duration_sec = data["duration"]
    winner_count = data["winner_count"]
    verif = data["verification_links"]
    winner_mode = data["winner_mode"]
    ban_old = data["ban_old"]
    old_winners = data.get("old_winners", {})

    mode_text = (
        "🤖 WINNER SELECT: AUTO BOT" if winner_mode == "auto"
        else "🧑‍🏫 WINNER SELECT: MANUAL (ADMIN)"
    )

    # Simple duration display
    mins = duration_sec // 60
    duration_text = f"{mins} Minutes" if mins else f"{duration_sec} Seconds"

    verif_text = ""
    if verif:
        lines = [f"{i+1}) {link}" for i, link in enumerate(verif)]
        verif_text = "🔗 Must Join (All):\n" + "\n".join(lines) + "\n"
    else:
        verif_text = "🔗 No verification required.\n"

    if ban_old and old_winners:
        old_lines = [
            f"@{uname}/{uid}" for uid, uname in old_winners.items()
        ]
        old_text = "🚫 Old Winners Banned:\n" + "\n".join(old_lines) + "\n"
    elif ban_old:
        old_text = "🚫 Old Winners Banned: (no list provided)\n"
    else:
        old_text = "⏭ Old winner filter SKIPPED.\n"

    preview = (
        "🎉 POWER POINT BREAK — OFFICIAL GIVEAWAY 🎉\n\n"
        f"📌 Title: {title}\n"
        f"🎁 Prize: {prize}\n"
        f"⏰ Duration: {duration_text} (BD TIME)\n"
        f"🏆 Total Winners: {winner_count}\n"
        f"{mode_text}\n"
        f"👥 Participate Count: 0\n\n"
        f"{verif_text}\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⏱ Time Left: (will start after posting)\n\n"
        "🎁 POWER POINT BREAK — GIVEAWAY LOADING💐\n"
        "▱▱▱▱▱▱▱▱▱▱ 0%\n"
        "Please wait...\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📢 Hosted By: @PowerPointBreak\n"
        "👑 Admin: @MinexxProo\n\n"
        "💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐"
    )

    await update.message.reply_text(preview)
    await update.message.reply_text(
        "Can I post this giveaway in your main channel?\n\n"
        "Send YES to post, or CANCEL to abort."
    )

    return CG_CONFIRM_POST


async def cg_confirm_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip().lower()
    if txt == "cancel":
        await update.message.reply_text("❌ Giveaway creation cancelled.")
        context.user_data.pop("cg", None)
        return ConversationHandler.END
    if txt != "yes":
        await update.message.reply_text("Please send YES or CANCEL.")
        return CG_CONFIRM_POST

    # Save giveaway to bot_data
    data = context.user_data["cg"]
    giveaway = {
        "title": data["title"],
        "prize": data["prize"],
        "duration": data["duration"],
        "winner_count": data["winner_count"],
        "verification_links": data["verification_links"],
        "winner_mode": data["winner_mode"],  # auto/manual
        "ban_old": data["ban_old"],
        "old_winners": data.get("old_winners", {}),
        "participants": {},  # user_id -> username
        "status": "running",
        "main_chat_id": None,
        "main_message_id": None,
        "pending_winners": None,
        "approve_job": None,
    }
    context.bot_data["current_giveaway"] = giveaway

    # Where to post? For demo: post in same chat as admin
    msg = await update.message.reply_text(
        build_giveaway_post_text(giveaway, participate_count=0),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎁 JOIN GIVEAWAY", callback_data="join_giveaway")]]
        ),
    )

    giveaway["main_chat_id"] = msg.chat_id
    giveaway["main_message_id"] = msg.message_id

    # Schedule end of giveaway
    context.job_queue.run_once(
        job_end_giveaway,
        when=timedelta(seconds=giveaway["duration"]),
        data={},
        name="end_giveaway",
    )

    await update.message.reply_text("✅ Giveaway posted and started!")
    context.user_data.pop("cg", None)
    return ConversationHandler.END


def build_giveaway_post_text(giveaway: dict, participate_count: int) -> str:
    title = giveaway["title"]
    prize = giveaway["prize"]
    duration = giveaway["duration"]
    winner_count = giveaway["winner_count"]
    verif = giveaway["verification_links"]
    mode = giveaway["winner_mode"]

    mode_text = (
        "🤖 WINNER SELECT: AUTO BOT" if mode == "auto"
        else "🧑‍🏫 WINNER SELECT: MANUAL (ADMIN)"
    )

    mins = duration // 60
    duration_text = f"{mins} Minutes" if mins else f"{duration} Seconds"

    if verif:
        lines = [f"{i+1}) {link}" for i, link in enumerate(verif)]
        verif_text = "🔗 Must Join (All):\n" + "\n".join(lines)
    else:
        verif_text = "🔗 No verification required."

    text = (
        "🎉 POWER POINT BREAK — OFFICIAL GIVEAWAY 🎉\n\n"
        f"📌 Title: {title}\n"
        f"🎁 Prize: {prize}\n"
        f"⏰ Duration: {duration_text} (BD Time)\n"
        f"🏆 Total Winners: {winner_count}\n"
        f"{mode_text}\n"
        f"👥 Participate Count: {participate_count}\n\n"
        f"{verif_text}\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "⏱ Time Left: Running…\n\n"
        "🎁 POWER POINT BREAK — GIVEAWAY LOADING💐\n"
        "▱▱▱▱▱▱▱▱▱▱ 0%\n"
        "Please wait...\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "📢 Hosted By: @PowerPointBreak\n"
        "👑 Admin: @MinexxProo\n\n"
        "💐✨🎉 JOIN GIVEAWAY NOW 🎉✨💐"
    )
    return text


# ------------- JOIN BUTTON HANDLER -----------------


async def join_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    giveaway = get_current_giveaway(context)

    if not giveaway or giveaway.get("status") != "running":
        await query.reply_text("⛔ No active giveaway right now.")
        return

    # 1) old winner check (if enabled)
    if giveaway.get("ban_old"):
        old_winners = giveaway.get("old_winners", {})
        if user.id in old_winners:
            # User side
            await query.reply_text(
                "😔 Oops! You have already won this giveaway before,\n"
                "so you can no longer participate, dear member.\n\n"
                "🎉 Thanks for joining!\n\n"
                "🍀 Try again — more giveaways coming soon!\n"
                "💙 Stay with Power Point Break!\n\n"
                "📞 For support:\n"
                "👉 @MinexxProo\n"
                "━━━━━━━━━━━━━━━━━━━━━━"
            )
            # Admin log
            super_admin_id = context.bot_data.get("super_admin_id")
            if super_admin_id:
                await context.bot.send_message(
                    super_admin_id,
                    "⚠️ Old Winner Tried to Join!\n\n"
                    f"Username: @{user.username}\nUserID: {user.id}\n\n"
                    "Action Blocked Successfully."
                )
            return

    # 2) duplicate check
    participants = giveaway.setdefault("participants", {})
    if user.id in participants:
        await query.reply_text(
            "⚠️❌ WARNING — DUPLICATE ENTRY ❌⚠️\n\n"
            "You already participated!\n"
            "⏳ Winner list will be published soon…\n\n"
            "👉 Contact Admin: @MinexxProo\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        return

    # (Real verification check — এখানে আসলে Telegram API দিয়ে membership চেক করা লাগত,
    # সেটা এখানে skip রাখছি। ধরে নিচ্ছি সব time pass = success.)

    # 3) success join
    participants[user.id] = user.username or ""
    await query.reply_text(
        "🎉 You have successfully joined the giveaway!\nGood luck! 🍀"
    )

    # Update main message's participate count
    main_chat_id = giveaway.get("main_chat_id")
    main_msg_id = giveaway.get("main_message_id")
    if main_chat_id and main_msg_id:
        count = len(participants)
        try:
            await context.bot.edit_message_text(
                chat_id=main_chat_id,
                message_id=main_msg_id,
                text=build_giveaway_post_text(giveaway, participate_count=count),
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🎁 JOIN GIVEAWAY", callback_data="join_giveaway"
                            )
                        ]
                    ]
                ),
            )
        except Exception as e:
            logger.warning("Edit message failed: %s", e)


# ------------- JOB WHEN GIVEAWAY ENDS -----------------


async def job_end_giveaway(context: ContextTypes.DEFAULT_TYPE):
    giveaway = get_current_giveaway(context)
    if not giveaway or giveaway.get("status") != "running":
        return

    giveaway["status"] = "ended"

    main_chat_id = giveaway.get("main_chat_id")
    if main_chat_id:
        await context.bot.send_message(
            main_chat_id,
            "🏁🔥 GIVEAWAY CLOSED!\n🔍🔥 Choosing winners…"
        )

    # Winner handling depends on mode
    mode = giveaway.get("winner_mode")
    if mode == "auto":
        await auto_select_winners(context)
    else:
        await manual_winner_prompt(context)


async def auto_select_winners(context: ContextTypes.DEFAULT_TYPE):
    giveaway = get_current_giveaway(context)
    participants = list(giveaway.get("participants", {}).items())  # list[(id, uname)]
    winner_count = giveaway.get("winner_count", 1)

    # Filter: only those with username
    valid_participants = [(uid, uname) for uid, uname in participants if uname]

    if len(valid_participants) == 0:
        # no winners
        return

    winners = random.sample(valid_participants, min(winner_count, len(valid_participants)))
    giveaway["pending_winners"] = winners

    preview_lines = []
    for i, (uid, uname) in enumerate(winners, start=1):
        preview_lines.append(f"{i}) @{uname}  (ID: {uid})")

    text = (
        "🏆 WINNER PREVIEW (AUTO BOT)\n\n"
        f"Total Winners: {len(winners)}\n\n" + "\n".join(preview_lines) +
        "\n\nYou have 38 seconds to approve or reject this winner list.\n\n"
        "✅ /approve_winners\n❌ /reject_winners\n\n"
        "⏳ Auto-posting in: 38s"
    )

    # Send to all admins (at least to super admin)
    admins = context.bot_data.get("admins", set())
    for admin_id in admins:
        try:
            await context.bot.send_message(admin_id, text)
        except Exception:
            pass

    # Schedule auto-approve after 38s
    job = context.job_queue.run_once(
        job_auto_approve_winners,
        when=timedelta(seconds=38),
        data={},
        name="auto_approve_winners",
    )
    giveaway["approve_job"] = job


async def manual_winner_prompt(context: ContextTypes.DEFAULT_TYPE):
    giveaway = get_current_giveaway(context)
    winner_count = giveaway.get("winner_count", 1)

    text = (
        "🏁🔥 GIVEAWAY CLOSED!\n"
        "🔍🔥 Manual winner selection required…\n\n"
        "Manual Winner mode is active.\n"
        f"Now you must choose {winner_count} winners manually.\n\n"
        "Use:\n"
        "1️⃣ /realp – to see all real participants\n"
        "2️⃣ /choosewinner – to submit your selected winners"
    )

    admins = context.bot_data.get("admins", set())
    for admin_id in admins:
        try:
            await context.bot.send_message(admin_id, text)
        except Exception:
            pass


async def job_auto_approve_winners(context: ContextTypes.DEFAULT_TYPE):
    giveaway = get_current_giveaway(context)
    if not giveaway:
        return
    if giveaway.get("pending_winners") is None:
        # Already approved/rejected
        return

    admins = context.bot_data.get("admins", set())
    for admin_id in admins:
        try:
            await context.bot.send_message(
                admin_id,
                "⏳ Time is over!\nAuto-approving and posting winners…"
            )
        except Exception:
            pass

    await post_winners_and_close(context)


# ------------- ADMIN CMDS: /approve_winners /reject_winners -------------


async def approve_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    giveaway = get_current_giveaway(context)
    if not giveaway or giveaway.get("pending_winners") is None:
        await update.message.reply_text("No pending winners to approve.")
        return

    # Cancel auto job if exists
    job = giveaway.get("approve_job")
    if job:
        job.schedule_removal()
        giveaway["approve_job"] = None

    await update.message.reply_text("✅ Winners approved! Posting to main channel…")
    await post_winners_and_close(context)


async def reject_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    giveaway = get_current_giveaway(context)
    if not giveaway or giveaway.get("pending_winners") is None:
        await update.message.reply_text("No pending winners to reject.")
        return

    # Cancel job
    job = giveaway.get("approve_job")
    if job:
        job.schedule_removal()
        giveaway["approve_job"] = None
    giveaway["pending_winners"] = None

    await update.message.reply_text(
        "❌ Winner list has been rejected.\nYou can rerun /choosewinner (manual) "
        "or create a new giveaway."
    )


async def post_winners_and_close(context: ContextTypes.DEFAULT_TYPE):
    giveaway = get_current_giveaway(context)
    if not giveaway:
        return

    winners = giveaway.get("pending_winners") or []
    giveaway["pending_winners"] = None

    if not winners:
        return

    title = giveaway["title"]
    prize = giveaway["prize"]
    main_chat_id = giveaway.get("main_chat_id")

    lines = []
    for i, (uid, uname) in enumerate(winners, start=1):
        lines.append(f"{i}) @{uname}")

    text = (
        "🏆 WINNER ANNOUNCEMENT 🎉\n\n"
        f"🎉 POWER POINT BREAK — OFFICIAL GIVEAWAY 🎉\n\n"
        f"🏅 Total Winners: {len(winners)}\n\n" +
        "\n".join(lines) +
        f"\n\n🎁 Prize: {prize}\n\n"
        "📢 Hosted By: @PowerPointBreak\n"
        "👑 Admin: @MinexxProo\n\n"
        "🎉 Congratulations to all winners!"
    )

    if main_chat_id:
        await context.bot.send_message(main_chat_id, text)
        # Close post
        await context.bot.send_message(
            main_chat_id,
            "⛔️❌ GIVEAWAY CLOSED ❌⛔️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📩 Need assistance?\n👉 @MinexxProo\n\n"
            "💫 Try your luck in the next giveaway!\n"
            "❤️ Best wishes ❤️\n"
            "━━━━━━━━━━━━━━━━━━━━━━━"
        )

    # DM winners
    for uid, uname in winners:
        try:
            await context.bot.send_message(
                uid,
                "🎉 CONGRATULATIONS! 🎉\n"
                "You are one of the WINNERS of our Giveaway! 🏆\n\n"
                "📩 Contact Admin to claim your reward:\n"
                "👉 @MinexxProo\n\n"
                "👍👍👍"
            )
        except Exception as e:
            logger.warning("Could not DM winner %s: %s", uid, e)

    # Reset current giveaway
    context.bot_data["current_giveaway"] = None


# ------------- /realp & /choosewinner (Manual Mode) -------------


async def cmd_realp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return
    giveaway = get_current_giveaway(context)
    if not giveaway:
        await update.message.reply_text("No active/last giveaway data found.")
        return
    participants = giveaway.get("participants", {})
    if not participants:
        await update.message.reply_text("No real participants yet.")
        return

    lines = []
    for uid, uname in participants.items():
        lines.append(f"@{uname} — {uid}")
    text = "📜 REAL PARTICIPANTS LIST\n\n" + "\n".join(lines)
    await update.message.reply_text(text)


async def choosewinner_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update, context):
        return ConversationHandler.END
    giveaway = get_current_giveaway(context)
    if not giveaway:
        await update.message.reply_text("No active/ended giveaway to choose winners for.")
        return ConversationHandler.END
    if giveaway.get("winner_mode") != "manual":
        await update.message.reply_text(
            "Winner mode is not MANUAL. Use Auto or switch mode next time."
        )
        return ConversationHandler.END

    winner_count = giveaway.get("winner_count", 1)
    await update.message.reply_text(
        "Please send the list of winners.\n\n"
        "Format (one per line):\n"
        "@user1\n@user2\n...\n\n"
        f"Required total winners: {winner_count}"
    )
    return MANUAL_WINNER_WAIT_LIST


async def choosewinner_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    giveaway = get_current_giveaway(context)
    participants = giveaway.get("participants", {})
    winner_count = giveaway.get("winner_count", 1)

    lines = [l.strip() for l in update.message.text.splitlines() if l.strip()]
    if len(lines) != winner_count:
        await update.message.reply_text(
            f"❌ You must send exactly {winner_count} usernames, one per line."
        )
        return MANUAL_WINNER_WAIT_LIST

    username_to_uid = {uname.lower(): uid for uid, uname in participants.items()}
    winners: list[tuple[int, str]] = []

    for line in lines:
        uname = line.lstrip("@").lower()
        if uname not in username_to_uid:
            await update.message.reply_text(
                f"❌ @{uname} is not a real participant.\nPlease check /realp and try again."
            )
            return MANUAL_WINNER_WAIT_LIST
        uid = username_to_uid[uname]
        winners.append((uid, participants[uid]))

    giveaway["pending_winners"] = winners

    preview_lines = []
    for i, (uid, uname) in enumerate(winners, start=1):
        preview_lines.append(f"{i}) @{uname}  (ID: {uid})")

    text = (
        "🏆 WINNER PREVIEW (MANUAL)\n\n"
        f"Total Winners: {len(winners)}\n\n" + "\n".join(preview_lines) +
        "\n\nYou have 38 seconds to approve or reject this winner list.\n\n"
        "✅ /approve_winners\n❌ /reject_winners\n\n"
        "⏳ Auto-posting in: 38s"
    )

    admins = context.bot_data.get("admins", set())
    for admin_id in admins:
        try:
            await context.bot.send_message(admin_id, text)
        except Exception:
            pass

    job = context.job_queue.run_once(
        job_auto_approve_winners,
        when=timedelta(seconds=38),
        data={},
        name="auto_approve_winners_manual",
    )
    giveaway["approve_job"] = job

    return ConversationHandler.END


# ----------------- MAIN APP -----------------


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Basic commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("on", cmd_on))
    app.add_handler(CommandHandler("off", cmd_off))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("removeadmin", cmd_removeadmin))
    app.add_handler(CommandHandler("realp", cmd_realp))
    app.add_handler(CommandHandler("approve_winners", approve_winners))
    app.add_handler(CommandHandler("reject_winners", reject_winners))

    # New giveaway conversation
    cg_handler = ConversationHandler(
        entry_points=[CommandHandler("newgiveaway", newgiveaway_entry)],
        states={
            CG_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_title)],
            CG_PRIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_prize)],
            CG_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_time)],
            CG_WINNERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winners)],
            CG_VERIF_LINKS: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_verif_links)],
            CG_WINNER_MODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_winner_mode)],
            CG_BAN_OLD_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_ban_old_choice)],
            CG_OLD_WINNER_LIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_old_winner_list)],
            CG_CONFIRM_POST: [MessageHandler(filters.TEXT & ~filters.COMMAND, cg_confirm_post)],
        },
        fallbacks=[],
    )
    app.add_handler(cg_handler)

    # Manual winner choice conversation
    manual_handler = ConversationHandler(
        entry_points=[CommandHandler("choosewinner", choosewinner_entry)],
        states={
            MANUAL_WINNER_WAIT_LIST: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, choosewinner_receive)
            ],
        },
        fallbacks=[],
    )
    app.add_handler(manual_handler)

    # Join button
    app.add_handler(CallbackQueryHandler(join_button_handler, pattern="^join_giveaway$"))

    app.run_polling()


if __name__ == "__main__":
    main()
