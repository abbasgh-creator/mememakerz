import os
import os
from dotenv import load_dotenv
load_dotenv()
import io
import random
import io
import random
import logging
from datetime import date

from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, PreCheckoutQueryHandler,
    filters, ContextTypes
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
FREE_FIRST = 5
FREE_DAILY = 1
COST_EXTRA = 10
WATERMARK = "@mememakerzbot"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

users_db = {}

def get_user(user_id, name="کاربر"):
    if user_id not in users_db:
        users_db[user_id] = {
            "name": name,
            "coins": 50,
            "free_left": FREE_FIRST,
            "daily_used": 0,
            "date": None,
        }
    u = users_db[user_id]
    today = str(date.today())
    if u["date"] != today:
        u["daily_used"] = 0
        u["date"] = today
    return u

def prepare_text(text):
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def load_font(size):
    try:
        return ImageFont.truetype("Vazirmatn-Bold.ttf", size, encoding="unic")
    except:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except:
            return ImageFont.load_default()

def create_meme(image_bytes, caption):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if max(img.size) > 1000:
        ratio = 1000 / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    
    draw = ImageDraw.Draw(img)
    font = load_font(max(int(img.width / 14), 24))
    display_text = prepare_text(caption)
    bbox = draw.textbbox((0, 0), display_text, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (img.width - w) // 2, img.height - h - 40
    
    pad = 15
    draw.rectangle([x - pad, y - pad, x + w + pad, y + h + pad], fill=(0, 0, 0))
    draw.text((x, y), display_text, font=font, fill="white")
    
    wm_font = load_font(18)
    draw.text((10, img.height - 25), WATERMARK, font=wm_font, fill="white")
    
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90)
    out.seek(0)
    return out

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 راهنما", callback_data="help")],
        [InlineKeyboardButton("👤 پروفایل", callback_data="profile")],
        [InlineKeyboardButton("🛒 خرید سکه", callback_data="buy_coins")],
    ])

def meme_keyboard(caption):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 ارسال به گروه", switch_inline_query=f"{caption}")],
        [InlineKeyboardButton("🏠 منوی اصلی", callback_data="back")],
    ])

CAPTIONS = [
    "وقتی میگی ۵ دقیقه دیگه میام 😂",
    "من و صبح‌ها ☕💀",
    "وقتی میفهمی فردا امتحان داری 📚😭",
    "این منم بعد از یه روز کاری 🛌",
    "دوستم که میگه پول قرضی پس میدم 💸",
    "من بعد از ۳ تا کافه ☕☕☕",
    "وقتی میگی آخرین قسمتشه 🎮",
    "فردا که یادم میاد امروز چیکار کردم 🤡",
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    user = get_user(u.id, u.first_name)
    await update.message.reply_text(
        f"سلام {u.first_name}! 👋\n\n"
        f"😂 من میم ساز خفنم!\n"
        f"فقط یه عکس بفرست تا برات میم بسازم.\n\n"
        f"🎁 {user['free_left']} میم رایگان داری!\n"
        f"💰 سکه: {user['coins']}",
        reply_markup=main_menu()
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    
    if user["free_left"] > 0:
        user["free_left"] -= 1
        status = f"🎁 رایگان (باقی: {user['free_left']})"
    elif user["daily_used"] < FREE_DAILY:
        user["daily_used"] += 1
        status = "🎁 رایگان روزانه"
    elif user["coins"] >= COST_EXTRA:
        user["coins"] -= COST_EXTRA
        status = f"💰 {COST_EXTRA} سکه کسر شد"
    else:
        await update.message.reply_text(
            "❌ محدودیتت تموم شد!\n"
            "🎁 فردا ۱ میم رایگان داری\n"
            "💰 یا از منو سکه بخر",
            reply_markup=main_menu()
        )
        return

    msg = await update.message.reply_text("🎨 دارم میم می‌سازم...")
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_bytes = await photo_file.download_as_bytearray()
        caption = random.choice(CAPTIONS)
        meme = create_meme(photo_bytes, caption)
        
        await msg.delete()
        await update.message.reply_photo(
            photo=meme,
            caption=f"😂 {caption}\n\n{status}",
            reply_markup=meme_keyboard(caption)
        )
    except Exception as e:
        logger.error(f"Error: {e}")
        await msg.edit_text("❌ یه مشکل پیش اومد. دوباره امتحان کن.")

async def buy_coins_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    keyboard = [
        [InlineKeyboardButton("💰 ۱۰۰ سکه - ۵۰ ⭐", callback_data="buy_100")],
        [InlineKeyboardButton("💰 ۳۰۰ سکه - ۱۲۰ ⭐", callback_data="buy_300")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back")],
    ]
    await q.edit_message_text(
        "⭐ *خرید سکه*\n\n"
        "با Telegram Stars سکه بخر.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def buy_coins_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    packages = {
        "buy_100": {"coins": 100, "stars": 50, "title": "۱۰۰ سکه"},
        "buy_300": {"coins": 300, "stars": 120, "title": "۳۰۰ سکه"},
    }
    pkg = packages.get(q.data)
    if not pkg:
        return
        
    await context.bot.send_invoice(
        chat_id=q.from_user.id,
        title=f"خرید {pkg['title']}",
        description=f"{pkg['coins']} سکه برای ربات میم‌ساز",
        payload=f"coins_{pkg['coins']}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=pkg["title"], amount=pkg["stars"])],
    )

async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    coins = int(payload.split("_")[1])
    user = get_user(update.effective_user.id, update.effective_user.first_name)
    user["coins"] += coins
    await update.message.reply_text(
        f"✅ پرداخت موفق!\n"
        f"💰 {coins} سکه به حسابت اضافه شد.\n"
        f"موجودی جدید: {user['coins']} سکه",
        reply_markup=main_menu()
    )

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user.id, q.from_user.first_name)
    await q.edit_message_text(
        f"👤 *{q.from_user.first_name}*\n\n"
        f"💰 سکه: {u['coins']}\n"
        f"🎁 رایگان: {u['free_left']}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "📸 *راهنما*\n\n"
        "۱. یه عکس بفرست\n"
        "۲. میم آماده میشه\n"
        "۳. دکمه ارسال به گروه رو بزن\n\n"
        "🎁 ۵ میم اول رایگانه!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )

async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user.id, q.from_user.first_name)
    await q.edit_message_text(
        f"منوی اصلی 👇\n\n🎁 {u['free_left']} میم رایگان داری",
        reply_markup=main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📸 یه عکس بفرست تا میم بسازم!",
        reply_markup=main_menu()
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(help_cmd, pattern="^help$"))
    app.add_handler(CallbackQueryHandler(back_main, pattern="^back$"))
    app.add_handler(CallbackQueryHandler(buy_coins_menu, pattern="^buy_coins$"))
    app.add_handler(CallbackQueryHandler(buy_coins_callback, pattern="^buy_"))
    
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🚀 MemeMakerZ روشن شد!")
    app.run_polling()

if __name__ == "__main__":
    main()