"""What the bot says. Telegram HTML, in the call platform bot's style."""

HELP_TEXT = (
    "<b>AVORTYX CAREERS BOT · HELP</b>\n\n"
    "<b>LINK YOUR ACCOUNT</b>\n"
    "1. Open the Avortyx panel → <b>Settings</b>\n"
    "2. Press <b>Connect Telegram</b>\n"
    "3. Tap the link, or send:\n"
    "<code>/start yourcode</code>\n\n"
    "━━━━━━━━━━━━━━━\n\n"
    "<b>SENT TO YOU AUTOMATICALLY</b>\n\n"
    "<b>New applications</b>\n"
    "Every application from the careers page, with the CV\n\n"
    "━━━━━━━━━━━━━━━\n\n"
    "<b>REPLY TO AN APPLICANT</b>\n"
    "Reply to the application message, or send the reference, a space, then your message:\n\n"
    "<code>AVX-00012 Thanks, we'd like to book an interview</code>\n\n"
    "In a group, use <code>/reply AVX-00012 your message</code>.\n"
    "Your reply goes straight to the applicant by email.\n\n"
    "━━━━━━━━━━━━━━━\n\n"
    "/help — this message\n"
    "/stop — stop alerts and unlink this chat"
)

WELCOME_TEXT = (
    "\U0001F44B <b>Welcome to the Avortyx Careers Bot</b>\n\n"
    "To get started, link your panel account:\n\n"
    "1. Sign in to the Avortyx panel\n"
    "2. Go to <b>Settings</b> and press <b>Connect Telegram</b>\n"
    "3. Tap the link, or send <code>/start yourcode</code>\n\n"
    "Once linked, new applications arrive here automatically. "
    "There's nothing else to set up. Send /help any time."
)

LINKED_TEXT = (
    "✅ <b>Linked!</b> Your Avortyx panel account ({who}) is connected. "
    "New applications arrive here automatically — send /help to see everything I do."
)

EXPIRED_TEXT = (
    "⏰ That link has expired or was already used. "
    "Press <b>Connect Telegram</b> in Panel → Settings again for a fresh one."
)

PRIVATE_ONLY_TEXT = "Open me in a private chat to link your account — links only work there."

STOPPED_TEXT = (
    "\U0001F515 Unlinked. You won't get applications here any more. "
    "Connect again any time from Panel → Settings."
)

NOT_LINKED_TEXT = (
    "Only linked team members can do that. Link your account first: "
    "Panel → <b>Settings</b> → <b>Connect Telegram</b>."
)

UNKNOWN_TEXT = "I didn't catch that. Send /help to see what I can do."

REPLY_USAGE_TEXT = "Send <code>/reply AVX-00012 your message</code>, or reply to an application message."
