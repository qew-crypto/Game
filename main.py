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
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
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
    waiting_for_slots_bet = State()

# Файлы данных
DATA_FILE = 'users_data.json'
REF_LINKS_FILE = 'ref_links.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def load_ref_links():
    if os.path.exists(REF_LINKS_FILE):
        with open(REF_LINKS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def save_ref_links(data):
    with open(REF_LINKS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

users = load_data()
ref_links = load_ref_links()

# Полная структура данных
DEFAULT_USER_DATA = {
    "balance": 0,
    "fanfiki": 0,
    "total_clicks": 0,
    "click_power": 1,
    "passive_income": 0,
    "energy": 100,
    "max_energy": 100,
    "banned": False,
    "ban_reason": None,
    "ban_until": None,
    "vip": False,
    "vip_until": None,
    "referrer": None,
    "referrals": 0,
    "referral_earnings": 0,
    "daily_streak": 0,
    "last_daily": None,
    "boosters": {
        "double_click": 0,
        "crit_chance": 0,
        "click_bonus": 0
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
    "achievements": [],
    "slots_wins": 0,
    "slots_losses": 0
}

def migrate_user_data(user_data):
    migrated = DEFAULT_USER_DATA.copy()
    
    for key, value in user_data.items():
        if key in migrated:
            if isinstance(value, dict) and isinstance(migrated[key], dict):
                migrated[key].update(value)
            else:
                migrated[key] = value
    
    if migrated["last_passive"] is None:
        migrated["last_passive"] = datetime.now().isoformat()
    if migrated["last_energy_restore"] is None:
        migrated["last_energy_restore"] = datetime.now().isoformat()
    if migrated["registered_at"] is None:
        migrated["registered_at"] = datetime.now().isoformat()
    
    return migrated

def get_user(user_id, username=None):
    user_id_str = str(user_id)
    
    if user_id_str not in users:
        users[user_id_str] = DEFAULT_USER_DATA.copy()
        users[user_id_str]["last_passive"] = datetime.now().isoformat()
        users[user_id_str]["last_energy_restore"] = datetime.now().isoformat()
        users[user_id_str]["registered_at"] = datetime.now().isoformat()
        users[user_id_str]["username"] = username
        save_data(users)
    else:
        users[user_id_str] = migrate_user_data(users[user_id_str])
        save_data(users)
    
    if username and users[user_id_str]["username"] != username:
        users[user_id_str]["username"] = username
        save_data(users)
    
    return users[user_id_str]

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_banned(user):
    if not user.get("banned", False):
        return False
    
    ban_until = user.get("ban_until")
    if ban_until:
        ban_time = datetime.fromisoformat(ban_until)
        if datetime.now() > ban_time:
            user["banned"] = False
            user["ban_reason"] = None
            user["ban_until"] = None
            save_data(users)
            return False
    
    return True

def get_ref_link(user_id):
    bot_username = "AxoraParserBot"
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

async def process_referral(new_user_id, referrer_id):
    if str(referrer_id) in users and referrer_id != new_user_id:
        referrer = get_user(referrer_id)
        referrer["referrals"] += 1
        referrer["fanfiki"] += 50
        referrer["balance"] += 1000
        save_data(users)
        
        try:
            await bot.send_message(referrer_id, 
                f"🎉 *НОВЫЙ РЕФЕРАЛ!*\n\n"
                f"По вашей ссылке зарегистрировался новый игрок!\n"
                f"💰 +1000 монет\n"
                f"💎 +50 Фанфиков\n"
                f"👥 Всего: {referrer['referrals']}",
                parse_mode="Markdown")
        except:
            pass

async def restore_energy(user_id):
    user = get_user(user_id)
    if is_banned(user):
        return 0
        
    if user["last_energy_restore"]:
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
    if is_banned(user):
        return 0
    
    if user["last_passive"]:
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

def check_achievements(user):
    achievements = []
    
    # Достижения за клики
    if user["total_clicks"] >= 100 and "100_clicks" not in user["achievements"]:
        achievements.append(("100_clicks", "🖱️ Первые сто", 50, 500))
    if user["total_clicks"] >= 1000 and "1000_clicks" not in user["achievements"]:
        achievements.append(("1000_clicks", "🖱️ Мастер клика", 100, 1000))
    if user["total_clicks"] >= 10000 and "10000_clicks" not in user["achievements"]:
        achievements.append(("10000_clicks", "🖱️ Легенда клика", 500, 5000))
    if user["total_clicks"] >= 100000 and "100000_clicks" not in user["achievements"]:
        achievements.append(("100000_clicks", "👑 Бог клика", 2000, 50000))
    
    # Достижения за баланс
    if user["balance"] >= 1000000 and "millionaire" not in user["achievements"]:
        achievements.append(("millionaire", "💰 Миллионер", 100, 10000))
    if user["balance"] >= 10000000 and "ten_million" not in user["achievements"]:
        achievements.append(("ten_million", "💎 Десятимиллионник", 500, 50000))
    if user["balance"] >= 100000000 and "hundred_million" not in user["achievements"]:
        achievements.append(("hundred_million", "🌟 Сотнимиллионник", 2000, 200000))
    
    # Достижения за рефералов
    if user["referrals"] >= 1 and "first_ref" not in user["achievements"]:
        achievements.append(("first_ref", "👥 Первый друг", 25, 500))
    if user["referrals"] >= 5 and "five_refs" not in user["achievements"]:
        achievements.append(("five_refs", "👥 Лидер", 100, 2000))
    if user["referrals"] >= 25 and "twenty_five_refs" not in user["achievements"]:
        achievements.append(("twenty_five_refs", "👥 Популярность", 500, 10000))
    
    # Достижения за апгрейды
    if user["upgrades"]["auto_level"] >= 5 and "auto_5" not in user["achievements"]:
        achievements.append(("auto_5", "🤖 Начинающий автокликер", 50, 1000))
    if user["upgrades"]["auto_level"] >= 20 and "auto_20" not in user["achievements"]:
        achievements.append(("auto_20", "🤖 Король автокликеров", 500, 10000))
    
    # Достижения за энергию
    if user["max_energy"] >= 250 and "energy_250" not in user["achievements"]:
        achievements.append(("energy_250", "⚡ Энерджайзер", 100, 2000))
    if user["max_energy"] >= 500 and "energy_500" not in user["achievements"]:
        achievements.append(("energy_500", "⚡ Энергетический гигант", 300, 5000))
    
    # Достижения за серию
    if user["daily_streak"] >= 7 and "streak_7" not in user["achievements"]:
        achievements.append(("streak_7", "📅 Неделя успеха", 100, 2000))
    if user["daily_streak"] >= 30 and "streak_30" not in user["achievements"]:
        achievements.append(("streak_30", "📅 Месяц в игре", 500, 10000))
    
    # Достижения за слоты
    if user["slots_wins"] >= 10 and "slots_10" not in user["achievements"]:
        achievements.append(("slots_10", "🎰 Удачливый игрок", 100, 2000))
    if user["slots_wins"] >= 50 and "slots_50" not in user["achievements"]:
        achievements.append(("slots_50", "🎰 Король слотов", 500, 10000))
    
    for ach_id, ach_name, fanfiki_reward, money_reward in achievements:
        user["achievements"].append(ach_id)
        user["fanfiki"] += fanfiki_reward
        user["balance"] += money_reward
        
    return achievements

# Слот-машина
async def play_slots(user_id, bet):
    user = get_user(user_id)
    
    if user.get("balance", 0) < bet:
        return None, "❌ Не хватает монет!"
    
    user["balance"] -= bet
    
    # Эмодзи для слотов
    symbols = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎", "7️⃣"]
    results = [random.choice(symbols) for _ in range(3)]
    
    # Выигрышные комбинации
    win_multiplier = 0
    
    if results[0] == results[1] == results[2]:
        if results[0] == "7️⃣":
            win_multiplier = 20
        elif results[0] == "💎":
            win_multiplier = 15
        elif results[0] == "⭐":
            win_multiplier = 10
        else:
            win_multiplier = 5
    elif results[0] == results[1] or results[1] == results[2]:
        if results[1] == "7️⃣":
            win_multiplier = 3
        elif results[1] == "💎":
            win_multiplier = 2.5
        else:
            win_multiplier = 2
    
    if win_multiplier > 0:
        win_amount = int(bet * win_multiplier)
        user["balance"] += win_amount
        user["slots_wins"] += 1
        save_data(users)
        return results, f"🎉 *ПОБЕДА!* x{win_multiplier}\nВыигрыш: +{win_amount}🪙"
    else:
        user["slots_losses"] += 1
        save_data(users)
        return results, f"😔 *ПРОИГРЫШ*\nПотеряно: -{bet}🪙"

def main_keyboard(user_id):
    kb = InlineKeyboardBuilder()
    user = get_user(user_id)
    
    if is_banned(user):
        ban_reason = user.get("ban_reason", "Не указана")
        ban_until = user.get("ban_until", "Навсегда")
        if ban_until != "Навсегда":
            ban_until = datetime.fromisoformat(ban_until).strftime("%d.%m.%Y %H:%M")
        kb.button(text=f"⚠️ ЗАБАНЕН ⚠️", callback_data="noop")
        return kb.as_markup()
    
    click_power = user.get("click_power", 1)
    if user.get("boosters", {}).get("double_click", 0) > 0:
        click_power *= 2
    
    energy = user.get("energy", 100)
    max_energy = user.get("max_energy", 100)
    
    vip_tag = "🌟 " if user.get("vip", False) else ""
    
    kb.button(text=f"{vip_tag}🖱️ КЛИК! (+{click_power}🪙)", callback_data="click")
    kb.button(text=f"⚡ {energy}/{max_energy}", callback_data="energy_info")
    kb.button(text="🎯 ЦЕЛЬ", callback_data="goal")
    kb.button(text="🏪 Магазин", callback_data="shop")
    kb.button(text="💎 ДОНАТ", callback_data="donate_menu")
    kb.button(text="🎰 СЛОТЫ", callback_data="slots")
    kb.button(text="📊 Профиль", callback_data="profile")
    kb.button(text="🏆 Достижения", callback_data="achievements")
    kb.button(text="👥 Рефералы", callback_data="referrals")
    kb.button(text="🏆 Топ", callback_data="top")
    kb.button(text="🎁 Ежедневный", callback_data="daily")
    kb.adjust(1, 2, 2, 2, 2, 1)
    
    if is_admin(user_id):
        kb.button(text="👑 Админ-панель", callback_data="admin_panel")
        kb.adjust(1, 2, 2, 2, 2, 1, 1)
    
    return kb.as_markup()

def shop_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬆️ Улучшить клик (100🪙)", callback_data="buy_click")
    kb.button(text="🤖 Автокликер (500🪙)", callback_data="buy_auto")
    kb.button(text="🔋 Улучшить энергию (300🪙)", callback_data="buy_energy")
    kb.button(text="⚡ Восстановить энергию (50🪙)", callback_data="restore_energy")
    kb.button(text="💫 Бустер x2 клик (200🪙)", callback_data="buy_double")
    kb.button(text="🎯 Крит шанс +5% (1000🪙)", callback_data="buy_crit")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

def donate_menu_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="💎 VIP СТАТУС", callback_data="donate_vip")
    kb.button(text="💰 1000 монет (10💎)", callback_data="donate_money")
    kb.button(text="⚡ Энерго-бустер (20💎)", callback_data="donate_energy")
    kb.button(text="⬆️ Апгрейд клика +5 (50💎)", callback_data="donate_click")
    kb.button(text="🤖 Мега-автокликер +5 (100💎)", callback_data="donate_auto")
    kb.button(text="🛒 ПОПОЛНИТЬ ФАНФИКИ", callback_data="donate_buy")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    return kb.as_markup()

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

def slots_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎰 100 🪙", callback_data="slots_100")
    kb.button(text="🎰 500 🪙", callback_data="slots_500")
    kb.button(text="🎰 1000 🪙", callback_data="slots_1000")
    kb.button(text="🎰 5000 🪙", callback_data="slots_5000")
    kb.button(text="🎰 10000 🪙", callback_data="slots_10000")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Рассылка", callback_data="admin_broadcast")
    kb.button(text="🔨 Бан/Разбан", callback_data="admin_ban_menu")
    kb.button(text="💰 Изменить монеты", callback_data="admin_set_money")
    kb.button(text="💎 Изменить Фанфики", callback_data="admin_set_fanfiki")
    kb.button(text="⚡ Изменить энергию", callback_data="admin_set_energy")
    kb.button(text="🌟 Выдать VIP", callback_data="admin_give_vip")
    kb.button(text="📊 Статистика", callback_data="admin_stats")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(2)
    return kb.as_markup()

def admin_ban_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔨 Забанить", callback_data="admin_ban")
    kb.button(text="🔓 Разбанить", callback_data="admin_unban")
    kb.button(text="🔙 Назад", callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()

@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        referrer_id = int(args[1].replace("ref_", ""))
        await process_referral(user_id, referrer_id)
    
    user = get_user(user_id, username)
    
    welcome_text = (
        "🌟 *CLICKER EMPIRE* 🌟\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎯 *ГЛАВНАЯ ЦЕЛЬ:*\n"
        "Стать самым богатым игроком во вселенной!\n\n"
        "🏆 *РАНГИ:*\n"
        "🌱 0 — Начинающий\n"
        "📈 1 млн — Новичок\n"
        "⚡ 10 млн — Мастер\n"
        "🌟 100 млн — Легенда\n"
        "👑 1 млрд — Император\n\n"
        "💎 *ЧТО НОВОГО:*\n"
        "• VIP статус с бонусами\n"
        "• Слот-машина 🎰\n"
        "• Реферальные отчисления\n"
        "• Система достижений\n\n"
        "👇 *НАЧНИ СВОЙ ПУТЬ!*"
    )
    
    await message.answer(welcome_text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.callback_query(F.data == "click")
async def handle_click(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if is_banned(user):
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    await restore_energy(user_id)
    await apply_passive_income(user_id)
    user = get_user(user_id)
    
    if user.get("energy", 0) <= 0:
        await callback.answer("😴 Нет энергии! Жди 5 мин или купи восстановление!", show_alert=True)
        return
    
    reward = user.get("click_power", 1)
    
    if user.get("vip", False):
        reward = int(reward * 1.5)
    
    crit_chance = user.get("boosters", {}).get("crit_chance", 0)
    if random.randint(1, 100) <= crit_chance:
        reward *= 2
        crit_text = "✨ КРИТ! ✨"
    else:
        crit_text = ""
    
    user["balance"] += reward
    user["total_clicks"] += 1
    user["total_earned"] += reward
    user["energy"] -= 1
    
    if user.get("boosters", {}).get("double_click", 0) > 0:
        user["boosters"]["double_click"] -= 1
    
    save_data(users)
    
    achievements = check_achievements(user)
    save_data(users)
    
    response = f"+{reward}🪙! ⚡{user['energy']}/{user['max_energy']}"
    if crit_text:
        response = f"{crit_text}\n{response}"
    
    await callback.answer(response)
    
    try:
        await callback.message.edit_text(
            f"🖱️ *Клик!*\n\n"
            f"💰 Баланс: {user['balance']:,}🪙\n"
            f"💎 Фанфики: {user['fanfiki']}\n"
            f"⚡ Энергия: {user['energy']}/{user['max_energy']}\n"
            f"📊 Кликов: {user['total_clicks']}",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    except:
        pass
    
    if achievements:
        for _, ach_name, fan_reward, mon_reward in achievements:
            await callback.message.answer(
                f"🏆 *ДОСТИЖЕНИЕ!*\n\n{ach_name}\n🎁 +{fan_reward}💎 +{mon_reward}🪙",
                parse_mode="Markdown"
            )

@dp.callback_query(F.data == "achievements")
async def show_achievements(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    all_achievements = [
        ("🖱️ Первые сто", "100 кликов", 50, user["total_clicks"] >= 100),
        ("🖱️ Мастер клика", "1000 кликов", 100, user["total_clicks"] >= 1000),
        ("🖱️ Легенда клика", "10000 кликов", 500, user["total_clicks"] >= 10000),
        ("👑 Бог клика", "100000 кликов", 2000, user["total_clicks"] >= 100000),
        ("💰 Миллионер", "1 млн монет", 100, user["balance"] >= 1000000),
        ("💎 Десятимиллионник", "10 млн монет", 500, user["balance"] >= 10000000),
        ("🌟 Сотнимиллионник", "100 млн монет", 2000, user["balance"] >= 100000000),
        ("👥 Первый друг", "1 реферал", 25, user["referrals"] >= 1),
        ("👥 Лидер", "5 рефералов", 100, user["referrals"] >= 5),
        ("👥 Популярность", "25 рефералов", 500, user["referrals"] >= 25),
        ("🤖 Начинающий автокликер", "5 ур. автокликера", 50, user["upgrades"]["auto_level"] >= 5),
        ("🤖 Король автокликеров", "20 ур. автокликера", 500, user["upgrades"]["auto_level"] >= 20),
        ("⚡ Энерджайзер", "250 макс. энергии", 100, user["max_energy"] >= 250),
        ("⚡ Энергетический гигант", "500 макс. энергии", 300, user["max_energy"] >= 500),
        ("📅 Неделя успеха", "7 дней серии", 100, user["daily_streak"] >= 7),
        ("📅 Месяц в игре", "30 дней серии", 500, user["daily_streak"] >= 30),
        ("🎰 Удачливый игрок", "10 побед в слотах", 100, user["slots_wins"] >= 10),
        ("🎰 Король слотов", "50 побед в слотах", 500, user["slots_wins"] >= 50),
    ]
    
    completed = [a for a in all_achievements if a[3]]
    total_reward = sum(a[2] for a in completed)
    
    text = "🏆 *ДОСТИЖЕНИЯ*\n\n"
    text += f"📊 Выполнено: {len(completed)}/{len(all_achievements)}\n"
    text += f"💎 Получено Фанфиков: {total_reward}\n\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"
    
    for name, desc, reward, done in all_achievements[:10]:
        status = "✅" if done else "🔒"
        text += f"{status} *{name}*\n"
        text += f"   └ {desc} — {reward}💎\n\n"
    
    if len(all_achievements) > 10:
        text += f"... и еще {len(all_achievements) - 10} достижений"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back")
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "slots")
async def show_slots(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if is_banned(user):
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    text = (
        f"🎰 *СЛОТ-МАШИНА*\n\n"
        f"💰 Твой баланс: {user['balance']:,}🪙\n"
        f"🏆 Побед: {user['slots_wins']}\n"
        f"😔 Поражений: {user['slots_losses']}\n\n"
        f"🎲 *ВЫИГРЫШИ:*\n"
        f"• 🍒🍒🍒 — x5\n"
        f"• 💎💎💎 — x15\n"
        f"• 7️⃣7️⃣7️⃣ — x20\n\n"
        f"Выбери ставку:"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=slots_keyboard())

@dp.callback_query(F.data.startswith("slots_"))
async def play_slots_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    bet = int(callback.data.split("_")[1])
    
    user = get_user(user_id)
    
    if is_banned(user):
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    results, message = await play_slots(user_id, bet)
    
    if results is None:
        await callback.answer(message, show_alert=True)
        return
    
    text = (
        f"🎰 *СЛОТ-МАШИНА*\n\n"
        f"{results[0]} | {results[1]} | {results[2]}\n\n"
        f"{message}\n\n"
        f"💰 Новый баланс: {get_user(user_id)['balance']:,}🪙"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=slots_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "referrals")
async def show_referrals(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    ref_link = get_ref_link(user_id)
    
    ref_text = (
        f"👥 *РЕФЕРАЛЬНАЯ СИСТЕМА*\n\n"
        f"🎁 *БОНУСЫ ЗА ПРИГЛАШЕНИЕ:*\n"
        f"• За регистрацию: 1000🪙 + 50💎\n"
        f"• 5% от донатов друга 💎\n\n"
        f"📊 *ТВОЯ СТАТИСТИКА:*\n"
        f"Приглашено: {user.get('referrals', 0)} чел.\n"
        f"Заработано с донатов: {user.get('referral_earnings', 0)}💎\n\n"
        f"🔗 *ТВОЯ ССЫЛКА:*\n"
        f"`{ref_link}`\n\n"
        f"✨ Приглашай друзей и получай % от их донатов!"
    )
    
    kb = InlineKeyboardBuilder()
    kb.button(text="📋 Скопировать", callback_data="copy_link")
    kb.button(text="🔙 Назад", callback_data="back")
    kb.adjust(1)
    
    await callback.message.edit_text(ref_text, parse_mode="Markdown", reply_markup=kb.as_markup())

@dp.callback_query(F.data == "copy_link")
async def copy_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    ref_link = get_ref_link(user_id)
    await callback.answer(f"Ссылка скопирована!\n{ref_link}", show_alert=True)

@dp.callback_query(F.data == "donate_menu")
async def show_donate_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    text = (
        f"💎 *ДОНАТ МАГАЗИН*\n\n"
        f"💰 Твои Фанфики: {user.get('fanfiki', 0)} 💎\n\n"
        f"Выбери категорию:"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=donate_menu_keyboard())

@dp.callback_query(F.data == "donate_buy")
async def show_donate_buy(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    text = (
        f"💳 *ПОПОЛНЕНИЕ ФАНФИКОВ*\n\n"
        f"Выбери количество Фанфиков:\n\n"
        f"🚧 *В РАЗРАБОТКЕ*\n\n"
        f"Скоро здесь появится возможность\n"
        f"пополнения через:\n"
        f"• ЮKassa\n"
        f"• CryptoBot\n"
        f"• Золотая Корона\n\n"
        f"А пока зарабатывай Фанфики\n"
        f"бесплатными способами! 🎁"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=donate_buy_keyboard())

@dp.callback_query(F.data == "donate_vip")
async def donate_vip(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 500
    
    if user.get("vip", False):
        await callback.answer("🌟 У вас уже есть VIP статус!", show_alert=True)
        return
    
    if user.get("fanfiki", 0) >= cost:
        user["fanfiki"] -= cost
        user["vip"] = True
        user["vip_until"] = (datetime.now() + timedelta(days=30)).isoformat()
        save_data(users)
        
        await callback.answer("🌟 Вы купили VIP статус на 30 дней!", show_alert=True)
        await callback.message.edit_text(
            f"🌟 *VIP СТАТУС АКТИВИРОВАН!*\n\n"
            f"Бонусы VIP:\n"
            f"• +50% к доходу с кликов\n"
            f"• +25% к пассивному доходу\n"
            f"• Эксклюзивный значок\n"
            f"• Приоритет в поддержке\n\n"
            f"VIP активен до: {(datetime.now() + timedelta(days=30)).strftime('%d.%m.%Y')}",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id)
        )
    else:
        await callback.answer(f"❌ Нужно {cost}💎", show_alert=True)

@dp.callback_query(F.data.startswith("donate_") and F.data not in ["donate_menu", "donate_buy", "donate_vip", "donate_money", "donate_energy", "donate_click", "donate_auto"])
async def donate_payment(callback: CallbackQuery):
    amount = callback.data.split("_")[1]
    await callback.answer(
        f"💎 Пополнение {amount} Фанфиков\n\n"
        f"🚧 Функция в разработке!\n\n"
        f"Скоро здесь появится возможность оплаты.\n"
        f"Следите за обновлениями!",
        show_alert=True
    )

@dp.callback_query(F.data == "donate_money")
async def donate_money(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 10
    if user.get("fanfiki", 0) >= cost:
        user["fanfiki"] -= cost
        user["balance"] += 1000
        save_data(users)
        await callback.answer("✅ +1000 монет!", show_alert=True)
        await show_donate_menu(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}💎", show_alert=True)

@dp.callback_query(F.data == "donate_energy")
async def donate_energy(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 20
    if user.get("fanfiki", 0) >= cost:
        user["fanfiki"] -= cost
        user["energy"] = user["max_energy"]
        save_data(users)
        await callback.answer("✅ Энергия восстановлена!", show_alert=True)
        await show_donate_menu(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}💎", show_alert=True)

@dp.callback_query(F.data == "donate_click")
async def donate_click(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 50
    if user.get("fanfiki", 0) >= cost:
        user["fanfiki"] -= cost
        user["click_power"] += 5
        user["upgrades"]["click_level"] += 5
        save_data(users)
        await callback.answer("✅ Сила клика +5!", show_alert=True)
        await show_donate_menu(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}💎", show_alert=True)

@dp.callback_query(F.data == "donate_auto")
async def donate_auto(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 100
    if user.get("fanfiki", 0) >= cost:
        user["fanfiki"] -= cost
        user["upgrades"]["auto_level"] += 5
        save_data(users)
        await callback.answer("✅ Автокликер +5 ур!", show_alert=True)
        await show_donate_menu(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}💎", show_alert=True)

@dp.callback_query(F.data == "shop")
async def show_shop(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if is_banned(user):
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    text = (
        f"🏪 *МАГАЗИН*\n\n"
        f"💰 Баланс: {user['balance']:,}🪙\n"
        f"💎 Фанфики: {user['fanfiki']}\n\n"
        f"⬆️ Улучшить клик — 100🪙\n"
        f"🤖 Автокликер — 500🪙\n"
        f"🔋 Улучшить энергию — 300🪙\n"
        f"⚡ Восстановить энергию — 50🪙\n"
        f"💫 Бустер x2 клик — 200🪙\n"
        f"🎯 Крит шанс +5% — 1000🪙"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=shop_keyboard())

@dp.callback_query(F.data == "buy_crit")
async def buy_crit(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 1000
    if user.get("balance", 0) >= cost:
        user["balance"] -= cost
        if "boosters" not in user:
            user["boosters"] = {}
        user["boosters"]["crit_chance"] = min(50, user["boosters"].get("crit_chance", 0) + 5)
        save_data(users)
        await callback.answer(f"✅ Крит шанс +5%! Теперь {user['boosters']['crit_chance']}%", show_alert=True)
        await show_shop(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}🪙", show_alert=True)

@dp.callback_query(F.data == "goal")
async def show_goal(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    balance = user.get("balance", 0)
    
    if balance < 1000000:
        progress = balance / 1000000 * 100
        next_goal = "1 млн монет"
        reward = "100 💎"
    elif balance < 10000000:
        progress = (balance - 1000000) / 9000000 * 100
        next_goal = "10 млн монет"
        reward = "500 💎"
    elif balance < 100000000:
        progress = (balance - 10000000) / 90000000 * 100
        next_goal = "100 млн монет"
        reward = "2000 💎"
    elif balance < 1000000000:
        progress = (balance - 100000000) / 900000000 * 100
        next_goal = "1 млрд монет"
        reward = "10000 💎"
    else:
        progress = 100
        next_goal = "Поздравляем! Вы Император!"
        reward = "Вы выполнили главную цель!"
    
    goal_text = (
        f"🎯 *ЦЕЛЬ*\n\n"
        f"💰 Баланс: {balance:,}🪙\n"
        f"🎯 Цель: {next_goal}\n"
        f"📈 Прогресс: {progress:.1f}%\n"
        f"🎁 Награда: {reward}\n\n"
        f"✨ Приглашай друзей и получай % от их донатов!"
    )
    
    await callback.message.edit_text(goal_text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    await restore_energy(user_id)
    await apply_passive_income(user_id)
    user = get_user(user_id)
    
    balance = user.get("balance", 0)
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
    
    vip = "🌟 VIP " if user.get("vip", False) else ""
    
    text = (
        f"📊 *ПРОФИЛЬ* {vip}\n\n"
        f"👤 {callback.from_user.first_name}\n"
        f"🏅 {title}\n\n"
        f"💰 Баланс: {balance:,}🪙\n"
        f"💎 Фанфики: {user.get('fanfiki', 0)}\n"
        f"🖱️ Кликов: {user.get('total_clicks', 0)}\n"
        f"💪 Сила клика: +{user.get('click_power', 1)}\n"
        f"⚡ Энергия: {user.get('energy', 100)}/{user.get('max_energy', 100)}\n"
        f"🤖 Автокликер: {user.get('upgrades', {}).get('auto_level', 0)} ур.\n"
        f"🎯 Крит шанс: {user.get('boosters', {}).get('crit_chance', 0)}%\n"
        f"👥 Рефералов: {user.get('referrals', 0)}\n"
        f"🏆 Достижений: {len(user.get('achievements', []))}\n"
        f"🎰 Слоты: {user.get('slots_wins', 0)}W/{user.get('slots_losses', 0)}L"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.callback_query(F.data == "daily")
async def daily_bonus(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    if is_banned(user):
        await callback.answer("❌ Вы забанены!", show_alert=True)
        return
    
    today = datetime.now().strftime("%Y-%m-%d")
    last_daily = user.get("last_daily")
    
    if last_daily == today:
        await callback.answer("🎁 Бонус уже получен!", show_alert=True)
        return
    
    if last_daily == (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"):
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
    
    text = (
        f"🎁 *ЕЖЕДНЕВНЫЙ БОНУС!*\n\n"
        f"🔥 Серия: {streak} дней\n"
        f"💰 +{bonus} монет\n"
        f"💎 +{fanfiki_bonus} Фанфиков\n\n"
        f"Заходи завтра и получи больше!"
    )
    
    await callback.answer(f"+{bonus}🪙 +{fanfiki_bonus}💎!", show_alert=True)
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.callback_query(F.data == "top")
async def show_top(callback: CallbackQuery):
    sorted_users = sorted(users.items(), key=lambda x: x[1].get("balance", 0), reverse=True)[:10]
    
    text = "🏆 *ТОП ИГРОКОВ*\n\n"
    
    for i, (uid, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.get_chat(int(uid))
            name = user.first_name
        except:
            name = f"User_{uid[:5]}"
        
        balance = data.get("balance", 0)
        if balance >= 1000000000:
            medal = "👑"
        elif balance >= 100000000:
            medal = "🌟"
        elif balance >= 10000000:
            medal = "⚡"
        elif balance >= 1000000:
            medal = "📈"
        else:
            medal = "🌱"
        
        text += f"{i}. {medal} {name} — {balance:,}🪙\n"
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔙 Назад", callback_data="back")
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=kb.as_markup())

# АДМИН ПАНЕЛЬ
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("⛔ Доступ запрещен!", show_alert=True)
        return
    
    await callback.message.edit_text("👑 *АДМИН-ПАНЕЛЬ*", parse_mode="Markdown", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "admin_ban_menu")
async def admin_ban_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.edit_text("👑 *Управление банами*", parse_mode="Markdown", reply_markup=admin_ban_keyboard())

@dp.callback_query(F.data == "admin_set_money")
async def admin_set_money(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("💰 *Введите ID пользователя:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_money")
    await callback.answer()

@dp.callback_query(F.data == "admin_set_fanfiki")
async def admin_set_fanfiki(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("💎 *Введите ID пользователя:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_fanfiki")
    await callback.answer()

@dp.callback_query(F.data == "admin_set_energy")
async def admin_set_energy(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("⚡ *Введите ID пользователя:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="set_energy")
    await callback.answer()

@dp.callback_query(F.data == "admin_give_vip")
async def admin_give_vip(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("🌟 *Введите ID пользователя для выдачи VIP:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="give_vip")
    await callback.answer()

@dp.callback_query(F.data == "admin_ban")
async def admin_ban(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("🔨 *Введите ID пользователя для бана:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="ban")
    await callback.answer()

@dp.callback_query(F.data == "admin_unban")
async def admin_unban(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("🔓 *Введите ID пользователя для разбана:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_user_id)
    await state.update_data(action="unban")
    await callback.answer()

@dp.message(AdminStates.waiting_for_user_id)
async def process_user_id(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    try:
        target_id = int(message.text)
    except:
        await message.answer("❌ Неверный ID!")
        return
    
    data = await state.get_data()
    action = data.get("action")
    
    if target_id in ADMIN_IDS and action not in ["set_money", "set_fanfiki", "set_energy", "give_vip"]:
        await message.answer("⚠️ Нельзя банить другого администратора!")
        await state.finish()
        return
    
    if action == "set_money":
        await state.update_data(target_id=target_id)
        await message.answer("💰 *Введите новое количество монет:*", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_amount)
    
    elif action == "set_fanfiki":
        await state.update_data(target_id=target_id)
        await message.answer("💎 *Введите новое количество Фанфиков:*", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_fanfiki_amount)
    
    elif action == "set_energy":
        await state.update_data(target_id=target_id)
        await message.answer("⚡ *Введите новое количество энергии:*", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_energy_amount)
    
    elif action == "give_vip":
        if str(target_id) in users:
            users[str(target_id)]["vip"] = True
            users[str(target_id)]["vip_until"] = (datetime.now() + timedelta(days=30)).isoformat()
            save_data(users)
            await message.answer(f"✅ VIP статус выдан пользователю {target_id} на 30 дней!")
            try:
                await bot.send_message(target_id, "🌟 *Вам выдан VIP статус на 30 дней от администрации!*", parse_mode="Markdown")
            except:
                pass
        else:
            await message.answer("❌ Пользователь не найден!")
        await state.finish()
    
    elif action == "ban":
        await state.update_data(target_id=target_id)
        await message.answer("⏱️ *Введите время бана (в часах, 0 = навсегда):*", parse_mode="Markdown")
        await state.set_state(AdminStates.waiting_for_ban_time)
    
    elif action == "unban":
        if str(target_id) in users:
            users[str(target_id)]["banned"] = False
            users[str(target_id)]["ban_reason"] = None
            users[str(target_id)]["ban_until"] = None
            save_data(users)
            await message.answer(f"✅ Пользователь {target_id} разбанен!")
            try:
                await bot.send_message(target_id, "✅ *Вы были разбанены!*", parse_mode="Markdown")
            except:
                pass
        else:
            await message.answer("❌ Пользователь не найден!")
        await state.finish()

@dp.message(AdminStates.waiting_for_ban_time)
async def process_ban_time(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    try:
        hours = int(message.text)
    except:
        await message.answer("❌ Введите число часов!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if hours > 0:
        ban_until = (datetime.now() + timedelta(hours=hours)).isoformat()
        ban_text = f"на {hours} часов"
    else:
        ban_until = None
        ban_text = "навсегда"
    
    await state.update_data(ban_until=ban_until)
    await message.answer(f"📝 *Введите причину бана:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_ban_reason)

@dp.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    reason = message.text
    data = await state.get_data()
    target_id = data.get("target_id")
    ban_until = data.get("ban_until")
    
    if str(target_id) in users:
        users[str(target_id)]["banned"] = True
        users[str(target_id)]["ban_reason"] = reason
        users[str(target_id)]["ban_until"] = ban_until
        save_data(users)
        
        ban_text = "навсегда" if not ban_until else f"до {datetime.fromisoformat(ban_until).strftime('%d.%m.%Y %H:%M')}"
        
        await message.answer(f"✅ Пользователь {target_id} забанен!\nПричина: {reason}\nСрок: {ban_text}")
        
        try:
            await bot.send_message(
                target_id,
                f"⚠️ *ВЫ ЗАБАНЕНЫ!*\n\n"
                f"Причина: {reason}\n"
                f"Срок: {ban_text}\n\n"
                f"По вопросам разбана обращайтесь к администрации.",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден!")
    
    await state.finish()

@dp.message(AdminStates.waiting_for_amount)
async def process_set_money(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if str(target_id) in users:
        old_balance = users[str(target_id)].get("balance", 0)
        users[str(target_id)]["balance"] = amount
        save_data(users)
        await message.answer(f"✅ Баланс пользователя {target_id} изменен!\nБыло: {old_balance:,}🪙\nСтало: {amount:,}🪙")
        
        try:
            await bot.send_message(
                target_id,
                f"💰 *Баланс изменен администратором!*\n\n"
                f"Новый баланс: {amount:,}🪙",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден!")
    
    await state.finish()

@dp.message(AdminStates.waiting_for_fanfiki_amount)
async def process_set_fanfiki(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if str(target_id) in users:
        old_fanfiki = users[str(target_id)].get("fanfiki", 0)
        users[str(target_id)]["fanfiki"] = amount
        save_data(users)
        await message.answer(f"✅ Фанфики пользователя {target_id} изменены!\nБыло: {old_fanfiki}💎\nСтало: {amount}💎")
        
        try:
            await bot.send_message(
                target_id,
                f"💎 *Фанфики изменены администратором!*\n\n"
                f"Новое количество: {amount}💎",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден!")
    
    await state.finish()

@dp.message(AdminStates.waiting_for_energy_amount)
async def process_set_energy(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if str(target_id) in users:
        max_energy = users[str(target_id)].get("max_energy", 100)
        if amount > max_energy:
            amount = max_energy
        
        old_energy = users[str(target_id)].get("energy", 100)
        users[str(target_id)]["energy"] = amount
        save_data(users)
        await message.answer(f"✅ Энергия пользователя {target_id} изменена!\nБыло: {old_energy}⚡\nСтало: {amount}⚡")
        
        try:
            await bot.send_message(
                target_id,
                f"⚡ *Энергия изменена администратором!*\n\n"
                f"Новое количество: {amount}⚡",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        await message.answer("❌ Пользователь не найден!")
    
    await state.finish()

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    await callback.message.answer("📢 *Введите текст рассылки:*", parse_mode="Markdown")
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(AdminStates.waiting_for_broadcast)
async def send_broadcast(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        await state.finish()
        return
    
    broadcast_text = message.text
    success = 0
    fail = 0
    
    status_msg = await message.answer("🔄 Рассылка начата...")
    
    for uid in users:
        try:
            await bot.send_message(
                int(uid),
                f"📢 *РАССЫЛКА АДМИНИСТРАЦИИ*\n\n{broadcast_text}",
                parse_mode="Markdown"
            )
            success += 1
            await asyncio.sleep(0.05)
        except:
            fail += 1
    
    await status_msg.edit_text(f"✅ Рассылка завершена!\n📨 Доставлено: {success}\n❌ Ошибок: {fail}")
    await state.finish()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        return
    
    total_users = len(users)
    banned_users = sum(1 for u in users.values() if u.get("banned", False))
    vip_users = sum(1 for u in users.values() if u.get("vip", False))
    total_clicks = sum(u.get("total_clicks", 0) for u in users.values())
    total_balance = sum(u.get("balance", 0) for u in users.values())
    total_fanfiki = sum(u.get("fanfiki", 0) for u in users.values())
    total_referrals = sum(u.get("referrals", 0) for u in users.values())
    
    text = (
        f"📊 *СТАТИСТИКА*\n\n"
        f"👥 Всего: {total_users}\n"
        f"🔨 Забанено: {banned_users}\n"
        f"🌟 VIP: {vip_users}\n"
        f"🖱️ Кликов: {total_clicks:,}\n"
        f"💰 Монет: {total_balance:,}\n"
        f"💎 Фанфиков: {total_fanfiki}\n"
        f"👥 Рефералов: {total_referrals}"
    )
    
    await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "back")
async def back_to_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text("🏠 *Главное меню*", parse_mode="Markdown", reply_markup=main_keyboard(user_id))

@dp.callback_query(F.data == "energy_info")
async def energy_info(callback: CallbackQuery):
    await callback.answer("⚡ Энергия восстанавливается по 10 ед/мин! Купи улучшения в магазине!", show_alert=True)

@dp.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()

@dp.callback_query(F.data == "buy_click")
async def buy_click(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 100
    if user.get("balance", 0) >= cost:
        user["balance"] -= cost
        user["click_power"] += 1
        user["upgrades"]["click_level"] += 1
        save_data(users)
        await callback.answer(f"✅ Сила клика +1! Теперь +{user['click_power']}🪙", show_alert=True)
        await show_shop(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}🪙", show_alert=True)

@dp.callback_query(F.data == "buy_auto")
async def buy_auto(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 500
    if user.get("balance", 0) >= cost:
        user["balance"] -= cost
        user["upgrades"]["auto_level"] += 1
        save_data(users)
        await callback.answer(f"✅ Автокликер +1 ур! +{user['upgrades']['auto_level'] * 5}🪙/мин", show_alert=True)
        await show_shop(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}🪙", show_alert=True)

@dp.callback_query(F.data == "buy_energy")
async def buy_energy(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 300
    if user.get("balance", 0) >= cost:
        user["balance"] -= cost
        user["max_energy"] += 25
        save_data(users)
        await callback.answer(f"✅ Макс. энергия +25! Теперь {user['max_energy']}", show_alert=True)
        await show_shop(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}🪙", show_alert=True)

@dp.callback_query(F.data == "restore_energy")
async def restore_energy_shop(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 50
    if user.get("balance", 0) >= cost:
        user["balance"] -= cost
        user["energy"] = user.get("max_energy", 100)
        save_data(users)
        await callback.answer(f"✅ Энергия восстановлена!", show_alert=True)
        await show_shop(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}🪙", show_alert=True)

@dp.callback_query(F.data == "buy_double")
async def buy_double(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    
    cost = 200
    if user.get("balance", 0) >= cost:
        user["balance"] -= cost
        if "boosters" not in user:
            user["boosters"] = {}
        user["boosters"]["double_click"] = 10
        save_data(users)
        await callback.answer(f"✅ Бустер x2 активирован на 10 кликов!", show_alert=True)
        await show_shop(callback)
    else:
        await callback.answer(f"❌ Нужно {cost}🪙", show_alert=True)

async def main():
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
