import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from googletrans import LANGUAGES, Translator

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
translator = Translator()

# База данных пользователей в памяти
# user_id: {"src": "auto", "dest": "ru"}
user_settings = {}

# Список доступных языков, отсортированный по названию
LANG_LIST = sorted(
    [(code, name.title()) for code, name in LANGUAGES.items()],
    key=lambda x: x[1],
)


class Form(StatesGroup):
    waiting_for_src = State()
    waiting_for_dest = State()


def get_main_keyboard(user_id):
    settings = user_settings.get(user_id, {"src": "auto", "dest": "ru"})

    src_name = (
        "🔍 Авто"
        if settings["src"] == "auto"
        else LANGUAGES.get(settings["src"], settings["src"]).title()
    )
    dest_name = LANGUAGES.get(settings["dest"], settings["dest"]).title()

    kb = [
        [
            types.InlineKeyboardButton(
                text=f"С: {src_name}", callback_data="change_src"
            ),
            types.InlineKeyboardButton(
                text=f"На: {dest_name}", callback_data="change_dest"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="🔄 Поменять местами", callback_data="swap_languages"
            )
        ],
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=kb)


def get_languages_keyboard(prefix):
    buttons = []
    if prefix == "set_src":
        buttons.append(
            [
                types.InlineKeyboardButton(
                    text="🔍 Определить язык (Авто)",
                    callback_data=f"{prefix}:auto",
                )
            ]
        )

    row = []
    for code, name in LANG_LIST:
        row.append(
            types.InlineKeyboardButton(
                text=name, callback_data=f"{prefix}:{code}"
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_settings:
        user_settings[user_id] = {"src": "auto", "dest": "ru"}

    await message.answer(
        "Привет! Я твой личный переводчик.\n\n"
        "Выбери языки перевода в меню ниже или просто отправь мне текст!",
        reply_markup=get_main_keyboard(user_id),
    )


@dp.callback_query(F.data == "change_src")
async def process_change_src(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выбери язык, **С КОТОРОГО** переводить (по алфавиту):",
        parse_mode="Markdown",
        reply_markup=get_languages_keyboard("set_src"),
    )


@dp.callback_query(F.data == "change_dest")
async def process_change_dest(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выбери язык, **НА КОТОРЫЙ** переводить (по алфавиту):",
        parse_mode="Markdown",
        reply_markup=get_languages_keyboard("set_dest"),
    )


@dp.callback_query(F.data.startswith("set_src:"))
async def set_src_lang(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split(":")[1]

    if user_id not in user_settings:
        user_settings[user_id] = {"src": "auto", "dest": "ru"}

    user_settings[user_id]["src"] = lang_code
    await callback.answer("Язык источника изменен!")
    await callback.message.edit_text(
        "Настройки обновлены:", reply_markup=get_main_keyboard(user_id)
    )


@dp.callback_query(F.data.startswith("set_dest:"))
async def set_dest_lang(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang_code = callback.data.split(":")[1]

    if lang_code == "auto":
        await callback.answer(
            "Нельзя выбрать 'Авто' для целевого языка!", show_alert=True
        )
        return

    if user_id not in user_settings:
        user_settings[user_id] = {"src": "auto", "dest": "ru"}

    user_settings[user_id]["dest"] = lang_code
    await callback.answer("Язык назначения изменен!")
    await callback.message.edit_text(
        "Настройки обновлены:", reply_markup=get_main_keyboard(user_id)
    )


@dp.callback_query(F.data == "swap_languages")
async def swap_languages(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_settings:
        user_settings[user_id] = {"src": "auto", "dest": "ru"}

    curr_src = user_settings[user_id]["src"]
    curr_dest = user_settings[user_id]["dest"]

    if curr_src == "auto":
        await callback.answer(
            "Нельзя поменять местами, когда включено 'Автоопределение'!",
            show_alert=True,
        )
        return

    user_settings[user_id]["src"] = curr_dest
    user_settings[user_id]["dest"] = curr_src

    await callback.answer("Языки поменялись местами!")
    await callback.message.edit_text(
        "Настройки обновлены:", reply_markup=get_main_keyboard(user_id)
    )


@dp.message(F.text)
async def translate_text(message: types.Message):
    user_id = message.from_user.id
    settings = user_settings.get(user_id, {"src": "auto", "dest": "ru"})

    try:
        if settings["src"] == "auto":
            result = translator.translate(
                message.text, dest=settings["dest"]
            )
            detected_src = (
                LANGUAGES.get(result.src, result.src).title()
                if hasattr(result, "src")
                else "Неизвестный"
            )
            response_text = (
                f"🔠 *Перевод* (определен: {detected_src} ➔ {LANGUAGES.get(settings['dest']).title()}):\n\n"
                f"{result.text}"
            )
        else:
            result = translator.translate(
                message.text, src=settings["src"], dest=settings["dest"]
            )
            response_text = f"🔠 *Перевод*:\n\n{result.text}"

        await message.answer(
            response_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id),
        )

    except Exception as e:
        await message.answer(
            "Произошла ошибка при переводе. Попробуйте еще раз."
        )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
