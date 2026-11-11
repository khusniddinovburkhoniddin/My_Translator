import asyncio
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import ClientSession, web

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# ВСТАВЬ СЮДА ССЫЛКУ ИЗ GOOGLE APPS SCRIPT (между кавычек)
GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyJHFGhAOJi-TKQ4I1R-wWcei4cm6QohkaAN6RaMV5Kp1xFZq9lcDMSxbUeFxh7L0o1/exec"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

LANG_MAP = {
    "Русский": "ru",
    "Английский": "en",
    "Узбекский": "uz",
    "Корейский": "ko",
    "Немецкий": "de",
    "Французский": "fr",
    "Китайский (упр.)": "zh-CN",
    "Японский": "ja",
    "Турецкий": "tr",
    "Арабский": "ar",
}

user_settings = {}


def get_lang_name(code):
    if code == "auto":
        return "🔍 Авто"
    for name, c in LANG_MAP.items():
        if c == code:
            return name
    return code.upper()


def get_main_keyboard(user_id):
    settings = user_settings.get(user_id, {"src": "auto", "dest": "ru"})

    src_name = get_lang_name(settings["src"])
    dest_name = get_lang_name(settings["dest"])

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

    sorted_langs = sorted(LANG_MAP.items(), key=lambda x: x[0])
    row = []
    for name, code in sorted_langs:
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
        "Выбери языки в меню ниже и отправь текст!",
        reply_markup=get_main_keyboard(user_id),
    )


@dp.callback_query(F.data == "change_src")
async def process_change_src(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выбери язык, **С КОТОРОГО** переводить:",
        parse_mode="Markdown",
        reply_markup=get_languages_keyboard("set_src"),
    )


@dp.callback_query(F.data == "change_dest")
async def process_change_dest(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "Выбери язык, **НА КОТОРЫЙ** переводить:",
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
    await callback.answer("Исходный язык изменен!")
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
    await callback.answer("Целевой язык изменен!")
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
            "Нельзя поменять местами при автоопределении языка!", show_alert=True
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

    src_lang = settings["src"]
    dest_lang = settings["dest"]

    try:
        async with ClientSession() as session:
            params = {
                "text": message.text,
                "src": "auto" if src_lang == "auto" else src_lang,
                "dest": dest_lang,
            }
            async with session.get(
                GOOGLE_SCRIPT_URL, params=params
            ) as response:
                data = await response.json()
                translated = data.get("result", "Ошибка получения перевода")

        src_title = get_lang_name(src_lang)
        dest_title = get_lang_name(dest_lang)

        response_text = (
            f"🔠 *Перевод* ({src_title} ➔ {dest_title}):\n\n" f"{translated}"
        )

        await message.answer(
            response_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id),
        )

    except Exception as e:
        print(f"Ошибка перевода: {e}")
        await message.answer("Произошла ошибка при обращении к серверу.")


async def handle_ping(request):
    return web.Response(text="Bot is running!")


async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
