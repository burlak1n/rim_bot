from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Клавиатура для обновления расписания (для всех)
update_schedule_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Обновить расписание", callback_data="upd_schedule"
            )
        ]
    ]
)

# Клавиатура для обновления расписания + кэша (для админов)
update_schedule_admin_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔄 Обновить расписание", callback_data="upd_schedule"
            )
        ],
        [InlineKeyboardButton(text="🔥 Обновить кэш", callback_data="refresh_cache")],
    ]
)
