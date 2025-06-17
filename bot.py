# -*- coding: utf-8 -*-
# -------------------------------------------------------------
#   AI-man – тегін 3-сабақ және толық курсқа апаратын Telegram-бот
#   ©2025  (Aiogram v3)
# -------------------------------------------------------------
import asyncio
import logging
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import gspread
from google.oauth2.service_account import Credentials

# -------------------------------------------------------------
# 🔐  Конфигурация (ENV арқылы; локальда – placeholder-лар OK)
# -------------------------------------------------------------
BOT_TOKEN        = os.getenv("BOT_TOKEN")
ADMIN_ID         = int(os.getenv("ADMIN_ID"))
GSPREAD_JSON     = os.getenv("GSPREAD_JSON")
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME")

WELCOME_VIDEO_NOTE = os.getenv("WELCOME_VIDEO_NOTE")          # video-note file_id
FIRST_AUDIO_ID     = os.getenv("FIRST_AUDIO_ID")            # 🔥-тен кейінгі аудио

# YouTube / file_id – қалай ыңғайлы, тек placeholder-ды ауыстырыңыз
LESSON_VIDEOS = [
    os.getenv("LESSON_URL_1", "https://youtu.be/AJWZDQPwzrY"),
    os.getenv("LESSON_URL_2", "https://youtu.be/AJWZDQPwzrY"),
    os.getenv("LESSON_URL_3", "https://youtu.be/AJWZDQPwzrY")
]

KASPI_PAY_LINK = os.getenv("KASPI_PAY_LINK", "https://pay.kaspi.kz/pay/oiur02gn")

# -------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)8s | %(name)s | %(message)s"
)
logger = logging.getLogger("AI-MAN-BOT")

bot      = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage  = MemoryStorage()
dp       = Dispatcher(storage=storage)

# -------------------------------------------------------------
# Google Sheets (міндетті емес – жоқ болса, бот жұмыс істей береді)
# -------------------------------------------------------------
try:
    scopes = ["https://www.googleapis.com/auth/spreadsheets",
              "https://www.googleapis.com/auth/drive"]
    creds  = Credentials.from_service_account_file(GSPREAD_JSON, scopes=scopes)
    gc     = gspread.authorize(creds)
    sh     = gc.open(SPREADSHEET_NAME)
    try:
        users_sheet = sh.worksheet("Users")
    except gspread.WorksheetNotFound:
        users_sheet = sh.add_worksheet("Users", rows="1000", cols="10")
        users_sheet.append_row(
            ["ChatID", "Name", "Job", "Phone", "Username", "RegAt"]
        )
    logger.info("Google Sheets қосылды: %s", SPREADSHEET_NAME)
except Exception as e:
    logger.warning("Google Sheets қосылмады: %s – деректер файлға жазылмайды", e)
    users_sheet = None

# -------------------------------------------------------------
# FSM States
# -------------------------------------------------------------
class Flow(StatesGroup):
    name          = State()   # 1 – есім
    job           = State()   # 2 – сала
    phone         = State()   # 3 – телефон
    wait_word1    = State()   # “🐣” – 2-сабақ
    wait_fire     = State()   # “🔥” – аудио
    wait_word2    = State()   # қайта “🐣” – 3-сабақ
    wait_finish   = State()   # “осындамын” – бітті
    wait_receipt  = State()   # чек

class BC(StatesGroup):
    material = State()        # админ тарату

# -------------------------------------------------------------
# UI helpers
# -------------------------------------------------------------
def kb_next_egg() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ «🐣» жібердім", callback_data="egg1")]
    ])

def kb_next_egg2() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ «🐣» жібердім", callback_data="egg2")]
    ])

def kb_buy() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Курсты сатып алу", callback_data="buy")]
    ])

# -------------------------------------------------------------
# /start  – бастау
# -------------------------------------------------------------
@dp.message(Command("start"))
async def start(m: types.Message, state: FSMContext):
    await state.clear()

    if WELCOME_VIDEO_NOTE:
        try:
            await bot.send_video_note(m.chat.id, WELCOME_VIDEO_NOTE)
            await asyncio.sleep(1.5)  # кішкене пауза — табиғи көріну үшін
        except Exception:
            pass

    await m.answer(
        "🚀 Сәлем! Мен — Шыңғыс, AI-man негізін қалаушымын 👨🏻‍💻\n\n"
        "Бұл — жасанды интеллект арқылы табыс табуды үйренетін курс.\n"
        "✅ Тегін сабақтарды көру үшін атыңызды жазыңыз 👇"
    )
    await state.set_state(Flow.name)

@dp.message(F.video_note)
async def get_video_note_file_id(msg: types.Message):
    file_id = msg.video_note.file_id
    await msg.answer(f"✅ Мынау сенің video_note file_id-ің:\n<code>{file_id}</code>")


# @dp.message(F.voice)
# async def get_voice_file_id(msg: types.Message):
#     file_id = msg.voice.file_id
#     await msg.answer(f"✅ Мынау сенің voice file_id-ің:\n<code>{file_id}</code>")


# -------------------------------------------------------------
# 1 → 2
# -------------------------------------------------------------
@dp.message(StateFilter(Flow.name))
async def got_name(m: types.Message, state: FSMContext):
    name = m.text.strip()
    if len(name) < 2:
        await m.answer("Есіміңіз тым қысқа, қайта жазыңыз 🙂")
        return
    await state.update_data(name=name)
    await m.answer("2) Окейй, қуаныштымын🫰🏼\n\nНемен айналысасыз? Қай сала?")
    await state.set_state(Flow.job)

# -------------------------------------------------------------
# 2 → 3
# -------------------------------------------------------------
@dp.message(StateFilter(Flow.job))
async def got_job(m: types.Message, state: FSMContext):
    await state.update_data(job=m.text.strip())
    await m.answer("3) Нөмеріңізбен бөлісіп кетіңіз и бастайық 📲")
    await state.set_state(Flow.phone)

# -------------------------------------------------------------
# 3 → алғашқы сабақ
# -------------------------------------------------------------
@dp.message(StateFilter(Flow.phone))
async def got_phone(m: types.Message, state: FSMContext):
    phone = m.contact.phone_number if m.contact else m.text.strip()
    await state.update_data(phone=phone)

    # Sheets-ке сақтау
    if users_sheet:
        data = await state.get_data()
        try:
            users_sheet.append_row([
                m.chat.id, data["name"], data["job"], phone,
                m.from_user.username or "", datetime.now().strftime("%Y-%m-%d %H:%M")
            ])
        except Exception as e:
            logger.error("Sheets append: %s", e)

    # админу
    try:
        d = await state.get_data()
        await bot.send_message(
            ADMIN_ID,
            f"🆕 <b>Жаңа клиент</b>\n👤 {d['name']}\n💼 {d['job']}\n📞 {phone}\n🔗 @{m.from_user.username or '—'}"
        )
    except Exception:
        pass

    # Сабақ 1
    await m.answer(
        "4) Керемет!\nМіне алғашқы сабақ және сабақты соңына дейін көріңіз🤫\n\n"
        "Жасырын сөз бар📌  видеоны көру үшін “🐣” жібер"
    )
    await m.answer(LESSON_VIDEOS[0], disable_web_page_preview=True)
    await m.answer("2-сабақты көру үшін төменге жасырын сөзді енгіз👇🏼", reply_markup=kb_next_egg())
    await state.set_state(Flow.wait_word1)

# -------------------------------------------------------------
# «🐣» → Lesson 2
# -------------------------------------------------------------
@dp.callback_query(F.data == "egg1", StateFilter(Flow.wait_word1))
async def need_egg_text(cb: types.CallbackQuery):
    await cb.answer("Жасырын сөзді чатқа жазыңыз 😉", show_alert=True)

@dp.message(StateFilter(Flow.wait_word1))
async def check_egg(m: types.Message, state: FSMContext):
    if m.text.strip() != "🐣":
        await m.answer("Жасырын сөз дұрыс емес. Қайтадан «тырысып» жіберіңіз.")
        return

    # Сабақ 2
    await m.answer(
        "Кеттік екінші сабаққа! 🚀\n"
        "Бұл сабақта өз тәжірибеммен бөлісемін."
    )
    await m.answer(LESSON_VIDEOS[1], disable_web_page_preview=True)
    await m.answer("Қалай 2-ші сабақ ұнады ма?\nЖалғастырамын десең «видеодағы құпия сөзді» жібер 😉")
    await state.set_state(Flow.wait_fire)

# -------------------------------------------------------------
# «🔥» → аудио + egg2
# -------------------------------------------------------------
@dp.message(StateFilter(Flow.wait_fire))
async def after_fire(m: types.Message, state: FSMContext):
    if m.text.strip() != "от":
        await m.answer("«құпия сөз» жіберсеңіз ғана жалғастырамын 🙂")
        return

    if FIRST_AUDIO_ID:
        try:
            await bot.send_audio(m.chat.id, FIRST_AUDIO_ID)
        except Exception:
            await m.answer("🔊 Аудио қосу қателігі 😅 – placeholder-ды тексеріңіз.")

    await m.answer("3-сабақты көру үшін «🐣» жібер және қағаз + қалам алып ал ✍🏼")
    await state.set_state(Flow.wait_word2)

# -------------------------------------------------------------
# «🐣» → Lesson 3
# -------------------------------------------------------------
@dp.message(StateFilter(Flow.wait_word2))
async def check_egg2(m: types.Message, state: FSMContext):
    if m.text.strip() != "қант":
        await m.answer("Дұрыс құпия сөз «қант». Тағы бір рет жіберіп көріңіз.")
        return

    await m.answer("Ал, соңғы сабақ 👇")
    await m.answer(LESSON_VIDEOS[2], disable_web_page_preview=True)
    await m.answer("Көріп болған соң «осындамын» деп жаза сал👇🏼")
    await state.set_state(Flow.wait_finish)

# -------------------------------------------------------------
# finish → buy
# -------------------------------------------------------------
@dp.message(StateFilter(Flow.wait_finish))
async def finish(m: types.Message, state: FSMContext):
    if m.text.lower().strip() not in ["осындамын", "осындамын!"]:
        await m.answer("«осындамын» деп жазыңыз, сабақты көріп болсаңыз 🙂")
        return

    if WELCOME_VIDEO_NOTE:
        try:
            await bot.send_video_note(m.chat.id, WELCOME_VIDEO_NOTE)
        except Exception:
            pass

    await m.answer(
        "🔥 Керемет! Толық курсқа дайын болсаңыз – төмендегі батырманы басыңыз.",
        reply_markup=kb_buy()
    )
    await state.set_state(Flow.wait_receipt)

# -------------------------------------------------------------
# buy → Kaspi link
# -------------------------------------------------------------
@dp.callback_query(F.data == "buy", StateFilter(Flow.wait_receipt))
async def send_pay_info(cb: types.CallbackQuery):
    await cb.message.answer(
        f"💳 Толық курс үшін Kaspi арқылы төлеңіз:\n{KASPI_PAY_LINK}\n\n"
        "Төлеген соң чек (фото/PDF) жіберіңіз, біз тез тексереміз!"
    )
    await cb.answer()

@dp.message(StateFilter(Flow.wait_receipt), F.photo | F.document)
async def got_receipt(m: types.Message, state: FSMContext):
    await m.forward(ADMIN_ID)
    await bot.send_message(ADMIN_ID, f"✅ Чек келді: @{m.from_user.username or '—'}")
    await m.answer("Чек қабылданды, менеджер жақын арада сізбен байланысады!")
    await state.clear()

# -------------------------------------------------------------
# 📢 Админ – тарату
# -------------------------------------------------------------
@dp.message(Command("broadcast"))
async def bc_start(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    await m.answer("📢 Материал жіберіңіз – барлық клиенттерге жолдаймын.")
    await state.set_state(BC.material)

@dp.message(StateFilter(BC.material))
async def bc_send(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID:
        return
    if not users_sheet:
        await m.answer("Sheets жоқ – тарата алмаймын.")
        await state.clear()
        return

    ids = users_sheet.col_values(1)[1:]
    ok = err = 0
    for cid in ids:
        try:
            await m.copy_to(int(cid))
            ok += 1
        except Exception as e:
            err += 1
            logger.error("Broadcast %s: %s", cid, e)
        await asyncio.sleep(0.05)
    await m.answer(f"✅ Таратылды: {ok}, қатесі: {err}")
    await state.clear()

# -------------------------------------------------------------
async def main():
    logger.info("🤖 AI-man bot іске қосылды")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            asyncio.run(bot.session.close())
        except RuntimeError:
            pass

