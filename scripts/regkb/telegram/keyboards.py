"""
Telegram inline keyboard builders for interactive actions.
"""

from typing import Optional


def pending_item_keyboard(item_id: int):
    """Build approve/reject inline keyboard for a pending download item."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{item_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{item_id}"),
            ]
        ]
    )


def pending_list_keyboard(page: int = 0, has_next: bool = False, has_prev: bool = False):
    """Build pagination keyboard for pending items list."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = []
    if has_prev:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"page_{page - 1}"))
    if has_next:
        buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"page_{page + 1}"))

    rows = []
    if buttons:
        rows.append(buttons)
    rows.append([InlineKeyboardButton("✅ Approve All", callback_data="approve_all")])
    return InlineKeyboardMarkup(rows)


def digest_action_keyboard():
    """Build action keyboard for digest results."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📥 View Pending", callback_data="show_pending"),
                InlineKeyboardButton("📧 Send Email", callback_data="send_email"),
            ],
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_digest"),
            ],
        ]
    )


def confirm_keyboard(action: str, item_id: Optional[int] = None):
    """Build a yes/no confirmation keyboard."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    suffix = f"_{item_id}" if item_id else ""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Yes", callback_data=f"confirm_{action}{suffix}"),
                InlineKeyboardButton("No", callback_data="cancel"),
            ]
        ]
    )
