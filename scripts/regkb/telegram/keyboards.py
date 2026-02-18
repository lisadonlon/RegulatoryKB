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


def _build_search_keyboard(page: int = 0, has_more: bool = False, total: int = 0):
    """Build search results keyboard with pagination and detail buttons."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    rows = []

    # Detail buttons for first few results
    detail_buttons = []
    start = page * 5  # Assumes page_size of 5
    for i in range(min(total - start, 5)):
        detail_buttons.append(
            InlineKeyboardButton(f"#{i + 1}", callback_data=f"search_detail_{start + i}")
        )
    if detail_buttons:
        rows.append(detail_buttons)

    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"search_page_{page - 1}"))
    if has_more:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"search_page_{page + 1}"))
    if nav_buttons:
        rows.append(nav_buttons)

    return InlineKeyboardMarkup(rows) if rows else None


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
