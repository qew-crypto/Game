import logging
import json
import os
import asyncio
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = '8622928719:AAFLghk9Fo36m_bY56wGqogFJEgDUeKBtCE'
ADMIN_IDS = [1842295433]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния для FSM
class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_user_id = State()
    waiting_for_amount = State()
    waiting_for_energy_amount = State()
    waiting_for_fanfiki_amount = State()
    waiting_for_ban_time = State()
    waiting_for_ban_reason = State()

# Файл данных
DATA_FILE = 'users_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

users = load_data()

# Структура данных
DEFAULT_USER_DATA = {
    "balance": 0,
    "fanfiki": 0,
    "total_clicks": 0,
    "click_power": 1,
    "energy": 100,
    "max_energy": 100,
    "banned": False,
    "ban_reason": None,
    "ban_until": None,
    "vip": False,
    "vip_until": None,
    "referrer": None,
    "referrals": 0,
    "daily_streak": 0,
    "last_daily": None,
    "boosters": {
        "double_click": 0,
        "crit_chance": 0
    },
    "upgrades": {
        "click_level": 1,
        "auto_level": 0,
        "energy_level": 1
    },
    "last_passive": None,
    "last_energy_restore": None,
    "username": None,
    "registered_at": None,
    "total_earned": 0,
    "achievements": []
}

def get_user(user_id, username=None):
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = DEFAULT_USER_DATA.copy()
        users[user_id_str]["last_passive"] = datetime.now().isoformat()
        users[user_id_str]["last_energy_restore"] = datetime.now().isoformat()
        users[user_id_str]["registered_at"] = datetime.now().isoformat()
        users[user_id_str]["username"] = username
        save_data(users)
    
    return users[user_id_str]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_ref_link(user_id):
    return f"https://t.me/AxoraParserBot?start=ref_{user_id}"

async def restore_energy(user_id):
    user = get_user(user_id)
    if user.get("last_energy_restore"):
        last = datetime.fromisoformat(user["last_energy_restore"])
        now = datetime.now()
        minutes_passed = (now - last).total_seconds() / 60
        
        if minutes_passed >= 1:
            restore_amount = int(10 * minutes_passed)
            user["energy"] = min(user["max_energy"], user["energy"] + restore_amount)
            user["last_energy_restore"] = now.isoformat()
            save_data(users)
            return restore_amount
    return 0

async def apply_passive_income(user_id):
    user = get_user(user_id)
    if user.get("last_passive"):
        last = datetime.fromisoformat(user["last_passive"])
        now = datetime.now()
        minutes_passed = (now - last).total_seconds() / 60
        
        if minutes_passed >= 1:
            income = int(user["upgrades"]["auto_level"] * 5 * minutes_passed)
            if income > 0:
                user["balance"] += income
                user["total_earned"] += income
                user["last_passive"] = now.isoformat()
                save_data(users)
                return income
    return 0

# ГЛАВНАЯ КЛАВИАТУРА
def main_keyboard(user_id):
    kb = InlineKeyboardBuilder()
    user = get_user(user_id)
    
    if user.get("banned"):
        kb.button(text="⚠️ ВЫ ЗАБАНЕНЫ ⚠️", callback_data="noop")
        return kb.as_markup()
    
    click_power = user.get("click_power", 1)
    if user.get("boosters", {}).get("double_click", 0) > 0:
        click_power *= 2
    
    kb.button(text=f"🖱️ КЛИК! (+{click_power}🪙)", callback_data="click")
    kb.button(text=f"⚡ {user['energy']}/{user['max_energy']}", callback_data="energy_info")
    kb.button(text="🎯 ЦЕЛЬ", callback_data="goal")
    kb.button(text="🏪 МАГАЗИН", callback_data="shop")
    kb.button(text="💎 ДОНАТ", callback_data="donate_menu")
    kb.button(text="🎰 СЛОТЫ", callback_data="slots_menu")
    kb.button(text="📊 ПРОФИЛЬ", callback_data="profile")
    kb.button(text="🏆 ДОСТИЖЕНИЯ", callback_data="achievements")
    kb.button(text="👥 РЕФЕРАЛЫ", callback_data="referrals")
    kb.button(text="🏆 ТОП", callback_data="top")
    kb.button(text="🎁 ЕЖЕДНЕВНЫЙ", callback_data="daily")
    kb.adjust(1, 2, 2, 2, 2, 1)
    
    if is_admin(user_id):
        kb.button(text="👑 АДМИН", callback_data="admin_panel")
        kb.adjust(1, 2, 2, 2, 2, 1, 1)
    
    return kb.as_markup()

# МАГАЗИН
def shop_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬆️ Улучшить клик (100🪙)", callback_data="buy_click")
    kb.button(text="🤖 Автокликер (500🪙)", callback_data="buy_auto")
    kb.button(text="🔋 Улучшить энергию (300🪙)", callback_data="buy_energy")
    kb.button(text="⚡ Восстановить энергию (50🪙)", callback_data="restore_energy")
    kb.button(text="💫 Бустер x2 (200🪙)", callback_data="buy_double")
    kb.button(text="🎯 Крит шанс +5% (1000🪙)", callback_data="buy_crit")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

# ДОНАТ МЕНЮ
def donate_menu_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🌟 VIP СТАТУС (500💎)", callback_data="buy_vip")
    kb.button(text="💰 1000 монет (10💎)", callback_data="donate_money")
    kb.button(text="⚡ Полная энергия (20💎)", callback_data="donate_energy")
    kb.button(text="⬆️ Клик +5 (50💎)", callback_data="donate_click")
    kb.button(text="🤖 Автокликер +5 (100💎)", callback_data="donate_auto")
    kb.button(text="🛒 ПОПОЛНИТЬ 💎", callback_data="donate_buy")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

# ПОПОЛНЕНИЕ
def donate_buy_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="100 💎 — 99₽", callback_data="donate_100")
    kb.button(text="500 💎 — 399₽", callback_data="donate_500")
    kb.button(text="1000 💎 — 699₽", callback_data="donate_1000")
    kb.button(text="5000 💎 — 2999₽", callback_data="donate_5000")
    kb.button(text="10000 💎 — 4999₽", callback_data="donate_10000")
    kb.button(text="🔙 Назад", callback_data="donate_menu")
    kb.adjust(1)
    return kb.as_markup()

# СЛОТЫ
def slots_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎰 100 🪙", callback_data="slot_100")
    kb.button(text="🎰 500 🪙", callback_data="slot_500")
    kb.button(text="🎰 1000 🪙", callback_data="slot_1000")
    kb.button(text="🎰 5000 🪙", callback_data="slot_5000")
    kb.button(text="🎰 10000 🪙", callback_data="slot_10000")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

# АДМИН МЕНЮ
def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="🔨 Бан игрока", callback_data="admin_ban")
    kb.button(text="🔓 Разбан", callback_data="admin_unban")
    kb.button(text="💰 Установить монеты", callback_data="admin_set_money")
    kb.button(text="💎 Установить Фанфики", callback_data="admin_set_fanfiki")
    kb.button(text="⚡ Установить энергию", callback_data="admin_set_energy")
    kb.button(text="🌟 Выдать VIP", callback_data="admin_give_vip")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

# START
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].replace("ref_", ""))
        if str(referrer_id) in users and referrer_id != user_id:
            referrer = get_user(referrer_id)
            referrer["referrals"] += 1
            referrer["fanfiki"] += 50
            referrer["balance"] += 1000
            save_data(users)
            try:
                await bot.send_message(referrer_id, f"🎉 Новый реферал! +1000🪙 +50💎")
            except:
                pass
    
    get_user(user_id, username)
    
    text = "🌟 *CLICKER EMPIRE* 🌟\n\nКликай, зарабатывай, становись богатым!\n\n👇 Нажми на кнопку чтобы начать!"
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

# КЛИК
@dp.callback_query(F.data == "click")
async def click_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user.get("banned"):
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    await restore_energy(user_id)
    await apply_passive_income(user_id)
    user = get_user(user_id)
    
    if user["energy"] <= 0:
        await callback.answer("😴 Нет энергии!", show_alert=True)
        return
    
    reward = user["click_power"]
    
    if user.get("vip"):
        reward = int(reward * 1.5)
    
    if user.get("boosters", {}).get("crit_chance", 0) > random.randint(1, 100):
        reward *= 2
        await callback.answer("✨ КРИТИЧЕСКИЙ УДАР! ✨", show_alert=True)
    
    user["balance"] += reward
    user["total_clicks"] += 1
    user["energy"] -= 1
    
    if user.get("boosters", {}).get("double_click", 0) > 0:
        user["boosters"]["double_click"] -= 1
    
    save_data(users)
    
    await callback.answer(f"+{reward}🪙")
    await callback.message.edit_text(
        f"🖱️ *Клик!*\n\n💰 Баланс: {user['balance']:,}🪙\n💎 Фанфики: {user['fanfiki']}\n⚡ Энергия: {user['energy']}/{user['max_energy']}",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user_id)
    )

# ЭНЕРГИЯ
@dp.callback_query(F.data == "energy_info")
async def energy_info(callback: CallbackQuery):
    await callback.answer("⚡ Энергия восстанавливается по 10 ед/мин!", show_alert=True)

# ЦЕЛЬ
@dp.callback_query(F.data == "goal")
async def goal_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    balance = user["balance"]
    
    if balance < 1000000:
        goal = "1 млн монет"
        progress = balance / 1000000 * 100
        reward = "100 💎"
    elif balance < 10000000:
        goal = "10 млн монет"
        progress = (balance - 1000000) / 9000000 * 100
        reward = "500 💎"
    elif balance < 100000000:
        goal = "100 млн монет"
        progress = (balance - 10000000) / 90000000 * 100
        reward = "2000 💎"
    else:
        goal = "1 млрд монет"
        progress = min(100, (balance - 100000000) / 900000000 * 100)
        reward = "10000 💎"
    
    text = f"🎯 *ЦЕЛЬ*\n\n💰 {balance:,}🪙\n🎯 {goal}\n📈 {progress:.1f}%\n🎁 {reward}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

# МАГАЗИН
@dp.callback_query(F.data == "shop")
async def shop_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    text = f"🏪 *МАГАЗИН*\n\n💰 Баланс: {user['balance']:,}🪙\n💎 Фанфики: {user['fanfiki']}"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=shop_keyboard())

# ПОКУПКИ
@dp.callback_query(F.data == "buy_click")
async def buy_click(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["balance"] >= 100:
        user["balance"] -= 100
        user["click_power"] += 1
        save_data(users)
        await callback.answer("✅ Сила клика +1!", show_alert=True)
        await shop_handler(callback)
    else:
        await callback.answer("❌ Не хватает монет!", show_alert=True)

@dp.callback_query(F.data == "buy_auto")
async def buy_auto(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["balance"] >= 500:
        user["balance"] -= 500
        user["upgrades"]["auto_level"] += 1
        save_data(users)
        await callback.answer("✅ Автокликер +1 ур!", show_alert=True)
        await shop_handler(callback)
    else:
        await callback.answer("❌ Не хватает монет!", show_alert=True)

@dp.callback_query(F.data == "buy_energy")
async def buy_energy(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["balance"] >= 300:
        user["balance"] -= 300
        user["max_energy"] += 25
        save_data(users)
        await callback.answer(f"✅ Макс. энергия +25! Теперь {user['max_energy']}", show_alert=True)
        await shop_handler(callback)
    else:
        await callback.answer("❌ Не хватает монет!", show_alert=True)

@dp.callback_query(F.data == "restore_energy")
async def restore_energy_shop(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["balance"] >= 50:
        user["balance"] -= 50
        user["energy"] = user["max_energy"]
        save_data(users)
        await callback.answer("✅ Энергия восстановлена!", show_alert=True)
        await shop_handler(callback)
    else:
        await callback.answer("❌ Не хватает монет!", show_alert=True)

@dp.callback_query(F.data == "buy_double")
async def buy_double(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["balance"] >= 200:
        user["balance"] -= 200
        user["boosters"]["double_click"] = 10
        save_data(users)
        await callback.answer("✅ Бустер x2 на 10 кликов!", show_alert=True)
        await shop_handler(callback)
    else:
        await callback.answer("❌ Не хватает монет!", show_alert=True)

@dp.callback_query(F.data == "buy_crit")
async def buy_crit(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["balance"] >= 1000:
        user["balance"] -= 1000
        user["boosters"]["crit_chance"] = min(50, user["boosters"].get("crit_chance", 0) + 5)
        save_data(users)
        await callback.answer(f"✅ Крит шанс +5%! Теперь {user['boosters']['crit_chance']}%", show_alert=True)
        await shop_handler(callback)
    else:
        await callback.answer("❌ Не хватает монет!", show_alert=True)

# ДОНАТ МЕНЮ
@dp.callback_query(F.data == "donate_menu")
async def donate_menu_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    text = f"💎 *ДОНАТ МАГАЗИН*\n\n💰 Твои Фанфики: {user['fanfiki']} 💎"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=donate_menu_keyboard())

@dp.callback_query(F.data == "donate_buy")
async def donate_buy_handler(callback: CallbackQuery):
    text = "💳 *ПОПОЛНЕНИЕ*\n\n🚧 В разработке!\n\nСкоро здесь будет доступна оплата."
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=donate_buy_keyboard())

@dp.callback_query(F.data == "buy_vip")
async def buy_vip(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user.get("vip"):
        await callback.answer("🌟 У вас уже есть VIP!", show_alert=True)
        return
    
    if user["fanfiki"] >= 500:
        user["fanfiki"] -= 500
        user["vip"] = True
        user["vip_until"] = (datetime.now() + timedelta(days=30)).isoformat()
        save_data(users)
        await callback.answer("🌟 VIP статус активирован на 30 дней!", show_alert=True)
        await donate_menu_handler(callback)
    else:
        await callback.answer(f"❌ Нужно 500💎", show_alert=True)

@dp.callback_query(F.data == "donate_money")
async def donate_money(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["fanfiki"] >= 10:
        user["fanfiki"] -= 10
        user["balance"] += 1000
        save_data(users)
        await callback.answer("✅ +1000 монет!", show_alert=True)
        await donate_menu_handler(callback)
    else:
        await callback.answer("❌ Не хватает Фанфиков!", show_alert=True)

@dp.callback_query(F.data == "donate_energy")
async def donate_energy(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["fanfiki"] >= 20:
        user["fanfiki"] -= 20
        user["energy"] = user["max_energy"]
        save_data(users)
        await callback.answer("✅ Энергия восстановлена!", show_alert=True)
        await donate_menu_handler(callback)
    else:
        await callback.answer("❌ Не хватает Фанфиков!", show_alert=True)

@dp.callback_query(F.data == "donate_click")
async def donate_click(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["fanfiki"] >= 50:
        user["fanfiki"] -= 50
        user["click_power"] += 5
        save_data(users)
        await callback.answer("✅ Сила клика +5!", show_alert=True)
        await donate_menu_handler(callback)
    else:
        await callback.answer("❌ Не хватает Фанфиков!", show_alert=True)

@dp.callback_query(F.data == "donate_auto")
async def donate_auto(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if user["fanfiki"] >= 100:
        user["fanfiki"] -= 100
        user["upgrades"]["auto_level"] += 5
        save_data(users)
        await callback.answer("✅ Автокликер +5 ур!", show_alert=True)
        await donate_menu_handler(callback)
    else:
        await callback.answer("❌ Не хватает Фанфиков!", show_alert=True)

@dp.callback_query(F.data.startswith("donate_") and F.data not in ["donate_menu", "donate_buy", "donate_money", "donate_energy", "donate_click", "donate_auto"])
async def donate_payment(callback: CallbackQuery):
    await callback.answer("🚧 Оплата в разработке! Скоро появится.", show_alert=True)

# СЛОТЫ
@dp.callback_query(F.data == "slots_menu")
async def slots_menu_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    text = f"🎰 *СЛОТ-МАШИНА*\n\n💰 Баланс: {user['balance']:,}🪙\n\nВыбери ставку:"
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=slots_keyboard())

@dp.callback_query(F.data.startswith("slot_"))
async def play_slot(callback: CallbackQuery):
    user_id = callback.from_user.id
    bet = int(callback.data.split("_")[1])
    user = get_user(user_id)
    
    if user["balance"] < bet:
        await callback.answer("❌ Не хватает монет!", show_alert=True)
        return
    
    user["balance"] -= bet
    
    symbols = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎", "7️⃣"]
    results = [random.choice(symbols) for _ in range(3)]
    
    win = 0
    if results[0] == results[1] == results[2]:
        if results[0] == "7️⃣":
            win = bet * 20
        elif results[0] == "💎":
            win = bet * 15
        elif results[0] == "⭐":
            win = bet * 10
        else:
            win = bet * 5
    elif results[0] == results[1] or results[1] == results[2]:
        win = bet * 2
    
    if win > 0:
        user["balance"] += win
        save_data(users)
        text = f"🎰 *СЛОТЫ*\n\n{results[0]} | {results[1]} | {results[2]}\n\n🎉 *ПОБЕДА!* +{win}🪙\n💰 Баланс: {user['balance']:,}🪙"
        await callback.answer(f"🎉 +{win}🪙", show_alert=True)
    else:
        save_data(users)
        text = f"🎰 *СЛОТЫ*\n\n{results[0]} | {results[1]} | {results[2]}\n\n😔 *ПРОИГРЫШ* -{bet}🪙\n💰 Баланс: {user['balance']:,}🪙"
        await callback.answer(f"😔 -{bet}🪙", show_alert=True)
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=slots_keyboard())

# ПРОФИЛЬ
@dp.callback_query(F.data == "profile")
async def profile_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    await restore_energy(user_id)
    await apply_passive_income(user_id)
    user = get_user(user_id)
    
    balance = user["balance"]
    if balance >= 1000000000:
        title = "👑 ИМПЕРАТОР"
    elif balance >= 100000000:
        title = "🌟 ЛЕГЕНДА"
    elif balance >= 10000000:
        title = "⚡ МАСТЕР"
    elif balance >= 1000000:
        title = "📈 НОВИЧОК"
    else:
        title = "🌱 НАЧИНАЮЩИЙ"
    
    vip = "🌟 VIP " if user.get("vip") else ""
    
    text = (
        f"📊 *ПРОФИЛЬ* {vip}\n\n"
        f"👤 {callback.from_user.first_name}\n"
        f"🏅 {title}\n\n"
        f"💰 Баланс: {user['balance']:,}🪙\n"
        f"💎 Фанфики: {user['fanfiki']}\n"
        f"🖱️ Кликов: {user['total_clicks']}\n"
        f"💪 Сила клика: +{user['click_power']}\n"
        f"⚡ Энергия: {user['energy']}/{user['max_energy']}\n"
        f"🤖 Автокликер: {user['upgrades']['auto_level']} ур.\n"
        f"🎯 Крит шанс: {user['boosters']['crit_chance']}%\n"
        f"👥 Рефералов: {user['referrals']}\n"
        f"🏆 Достижений: {len(user['achievements'])}"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

# ДОСТИЖЕНИЯ
@dp.callback_query(F.data == "achievements")
async def achievements_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    achievements_list = [
        ("🖱️ 100 кликов", user["total_clicks"] >= 100, 50),
        ("🖱️ 1000 кликов", user["total_clicks"] >= 1000, 100),
        ("🖱️ 10000 кликов", user["total_clicks"] >= 10000, 500),
        ("💰 1 млн монет", user["balance"] >= 1000000, 100),
        ("💰 10 млн монет", user["balance"] >= 10000000, 500),
        ("👥 1 реферал", user["referrals"] >= 1, 50),
        ("👥 5 рефералов", user["referrals"] >= 5, 100),
        ("🤖 Автокликер 5 ур", user["upgrades"]["auto_level"] >= 5, 100),
        ("⚡ Энергия 200", user["max_energy"] >= 200, 100),
        ("📅 7 дней серии", user["daily_streak"] >= 7, 100),
    ]
    
    completed = sum(1 for _, done, _ in achievements_list if done)
    
    text = f"🏆 *ДОСТИЖЕНИЯ*\n\n📊 {completed}/{len(achievements_list)}\n\n"
    for name, done, reward in achievements_list:
        status = "✅" if done else "🔒"
        text += f"{status} {name} — {reward}💎\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back")
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.as_markup())

# РЕФЕРАЛЫ
@dp.callback_query(F.data == "referrals")
async def referrals_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    ref_link = get_ref_link(user_id)
    
    text = (
        f"👥 *РЕФЕРАЛЫ*\n\n"
        f"👥 Приглашено: {user['referrals']}\n"
        f"🎁 За каждого: 1000🪙 + 50💎\n\n"
        f"🔗 Твоя ссылка:\n`{ref_link}`"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Копировать", callback_data="copy_link")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "copy_link")
async def copy_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    ref_link = get_ref_link(user_id)
    await callback.answer(f"Ссылка: {ref_link}", show_alert=True)

# ТОП
@dp.callback_query(F.data == "top")
async def top_handler(callback: CallbackQuery):
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
    
    text = "🏆 *ТОП 10*\n\n"
    for i, (uid, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.get_chat(int(uid))
            name = user.first_name
        except:
            name = f"User_{uid[:5]}"
        
        text += f"{i}. {name} — {data.get('balance', 0):,}🪙\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back")
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.as_markup())

# ЕЖЕДНЕВНЫЙ
@dp.callback_query(F.data == "daily")
async def daily_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    if user.get("last_daily") == today:
        await callback.answer("🎁 Бонус уже получен!", show_alert=True)
        return
    
    if user.get("last_daily") == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"):
        user["daily_streak"] = user.get("daily_streak", 0) + 1
    else:
        user["daily_streak"] = 1
    
    streak = user["daily_streak"]
    bonus = 100 + (streak * 10)
    fanfiki_bonus = 1 + (streak // 7)
    
    user["balance"] += bonus
    user["fanfiki"] += fanfiki_bonus
    user["last_daily"] = today
    save_data(users)
    
    await callback.answer(f"+{bonus}🪙 +{fanfiki_bonus}💎!", show_alert=True)
    await callback.message.edit_text(
        f"🎁 *ЕЖЕДНЕВНЫЙ БОНУС!*\n\n🔥 Серия: {streak} дней\n💰 +{bonus}🪙\n💎 +{fanfiki_bonus}💎",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user_id)
    )

# АДМИН ПАНЕЛЬ
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    await callback.message.edit_text("👑 *АДМИН ПАНЕЛЬ*", parse_mode="Markdown", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("📢 Введите текст рассылки:")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.finish()
        return
    
    text = message.text
    success = 0
    
    for uid in users:
        try:
            await bot.send_message(int(uid), f"📢 *РАССЫЛКА*\n\n{text}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
        except:
            pass
    
    await message.answer(f"✅ Отправлено {success} пользователям")
    await state.finish()

@dp.callback_query(F.data == "admin_set_money")
async def admin_set_money(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("💰 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_money")
    await callback.answer()

@dp.callback_query(F.data == "admin_set_fanfiki")
async def admin_set_fanfiki(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("💎 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_fanfiki")
    await callback.answer()

@dp.callback_query(F.data == "admin_set_energy")
async def admin_set_energy(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("⚡ Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_energy")
    await callback.answer()

@dp.callback_query(F.data == "admin_give_vip")
async def admin_give_vip(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("🌟 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_vip")
    await callback.answer()

@dp.callback_query(F.data == "admin_ban")
async def admin_ban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("🔨 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="ban")
    await callback.answer()

@dp.callback_query(F.data == "admin_unban")
async def admin_unban(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    
    await callback.message.answer("🔓 Введите ID пользователя:")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="unban")
    await callback.answer()

@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.finish()
        return
    
    try:
        target_id = int(message.text)
    except:
        await message.answer("❌ Неверный ID!")
        await state.finish()
        return
    
    data = await state.get_data()
    action = data.get("action")
    
    if action == "set_money":
        await state.update_data(target_id=target_id)
        await message.answer("💰 Введите сумму монет:")
        await state.set_state(AdminStates.waiting_for_amount)
    
    elif action == "set_fanfiki":
        await state.update_data(target_id=target_id)
        await message.answer("💎 Введите количество Фанфиков:")
        await state.set_state(AdminStates.waiting_for_fanfiki_amount)
    
    elif action == "set_energy":
        await state.update_data(target_id=target_id)
        await message.answer("⚡ Введите количество энергии:")
        await state.set_state(AdminStates.waiting_for_energy_amount)
    
    elif action == "give_vip":
        if str(target_id) in users:
            users[str(target_id)]["vip"] = True
            users[str(target_id)]["vip_until"] = (datetime.now() + timedelta(days=30)).isoformat()
            save_data(users)
            await message.answer(f"✅ VIP выдан {target_id}")
        else:
            await message.answer("❌ Пользователь не найден")
        await state.finish()
    
    elif action == "ban":
        await state.update_data(target_id=target_id)
        await message.answer("⏱️ Введите время бана в часах (0 = навсегда):")
        await state.set_state(AdminStates.waiting_for_ban_time)
    
    elif action == "unban":
        if str(target_id) in users:
            users[str(target_id)]["banned"] = False
            users[str(target_id)]["ban_reason"] = None
            users[str(target_id)]["ban_until"] = None
            save_data(users)
            await message.answer(f"✅ {target_id} разбанен")
        else:
            await message.answer("❌ Пользователь не найден")
        await state.finish()

@dp.message(AdminStates.waiting_for_ban_time)
async def process_ban_time(message: Message, state: FSMContext):
    try:
        hours = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if hours > 0:
        ban_until = (datetime.now() + timedelta(hours=hours)).isoformat()
        ban_text = f"{hours} часов"
    else:
        ban_until = None
        ban_text = "навсегда"
    
    await state.update_data(ban_until=ban_until)
    await message.answer("📝 Введите причину бана:")
    await state.set_state(AdminStates.waiting_for_ban_reason)

@dp.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: Message, state: FSMContext):
    reason = message.text
    data = await state.get_data()
    target_id = data.get("target_id")
    ban_until = data.get("ban_until")
    
    if str(target_id) in users:
        users[str(target_id)]["banned"] = True
        users[str(target_id)]["ban_reason"] = reason
        users[str(target_id)]["ban_until"] = ban_until
        save_data(users)
        await message.answer(f"✅ {target_id} забанен\nПричина: {reason}")
    else:
        await message.answer("❌ Пользователь не найден")
    
    await state.finish()

@dp.message(AdminStates.waiting_for_amount)
async def process_set_money(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if str(target_id) in users:
        users[str(target_id)]["balance"] = amount
        save_data(users)
        await message.answer(f"✅ Баланс {target_id} = {amount}🪙")
    else:
        await message.answer("❌ Пользователь не найден")
    
    await state.finish()

@dp.message(AdminStates.waiting_for_fanfiki_amount)
async def process_set_fanfiki(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if str(target_id) in users:
        users[str(target_id)]["fanfiki"] = amount
        save_data(users)
        await message.answer(f"✅ Фанфики {target_id} = {amount}💎")
    else:
        await message.answer("❌ Пользователь не найден")
    
    await state.finish()

@dp.message(AdminStates.waiting_for_energy_amount)
async def process_set_energy(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if str(target_id) in users:
        max_energy = users[str(target_id)]["max_energy"]
        if amount > max_energy:
            amount = max_energy
        users[str(target_id)]["energy"] = amount
        save_data(users)
        await message.answer(f"✅ Энергия {target_id} = {amount}⚡")
    else:
        await message.answer("❌ Пользователь не найден")
    
    await state.finish()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    total = len(users)
    banned = sum(1 for u in users.values() if u.get("banned"))
    vip = sum(1 for u in users.values() if u.get("vip"))
    total_balance = sum(u.get("balance", 0) for u in users.values())
    total_fanfiki = sum(u.get("fanfiki", 0) for u in users.values())
    
    text = (
        f"📊 *СТАТИСТИКА*\n\n"
        f"👥 Всего: {total}\n"
        f"🔨 Забанено: {banned}\n"
        f"🌟 VIP: {vip}\n"
        f"💰 Монет: {total_balance:,}\n"
        f"💎 Фанфиков: {total_fanfiki}"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=admin_keyboard())

# НАЗАД
@dp.callback_query(F.data == "back")
async def back_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.callback_query(F.data == "noop")
async def noop_handler(callback: CallbackQuery):
    await callback.answer()

async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
