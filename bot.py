import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from yt_dlp import YoutubeDL

# إعداد السجلات
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("ZenoXBot")

# البيانات الأساسية المطلوبة
TOKEN = "8548413224:AAGxpeH4E95UHG5s2qk80kxIgp63uLrPp-g"
CHANNEL = "@ZenoX_Tools"
ADMIN_ID = 6043858925

# ذاكرة مؤقتة لنتائج البحث (لكل المستخدمين)
SEARCH_CACHE = {}

# دالة التحقق من الاشتراك الإجباري
async def check_user_subscription(bot, user_id: int) -> bool:
    if user_id == ADMIN_ID:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        if member.status in ["member", "administrator", "creator"]:
            return True
    except Exception:
        pass
    return False

# رسالة /start والاشتراك الإجباري
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    is_sub = await check_user_subscription(context.bot, user.id)
    if not is_sub:
        channel_username = CHANNEL.lstrip("@")
        channel_link = f"https://t.me/{channel_username}"
        
        text = (
            "🚧┇عذراً، عليك الاشتراك في قناة البوت أولاً. 🚧\n"
            "🔍 ثم اضغط تحقق."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("اشترك في القناة 📡", url=channel_link)],
            [InlineKeyboardButton("تحقق 🔍", callback_data="check_sub")]
        ])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
        return

    welcome_text = (
        f"أهلاً بك يا <b>{user.first_name}</b> في بوت التحميل والبحث الاحترافي 🚀\n\n"
        "• أرسل أي رابط لتحميله (يوتيوب، تيك توك، تويتر).\n"
        "• أو أرسل أي نص للبحث المباشر في يوتيوب وعرض النتائج!"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

# معالجة زر التحقق
async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user

    is_sub = await check_user_subscription(context.bot, user.id)
    if not is_sub:
        await query.answer("❌ لم تقم بالاشتراك في القناة بعد!", show_alert=True)
        return

    await query.message.delete()
    await query.message.reply_text("✅ تم التحقق بنجاح! أرسل الآن رابطك أو كلمات البحث 🎬")

# معالجة الرسائل النصية والروابط والبحث
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    if not await check_user_subscription(context.bot, user.id):
        await update.message.reply_text("🚧 عذراً, يجب الاشتراك في قناة البوت أولاً لاستخدامه.")
        return

    text = update.message.text.strip()

    # إذا كان رابطاً
    if text.startswith("http"):
        await process_download(update, context, text)
    elif text.startswith("/dl_"):
        # التعامل مع الروابط المختصرة للبحث
        video_id = text.replace("/dl_", "")
        real_url = f"https://www.youtube.com/watch?v={video_id}"
        await process_download(update, context, real_url)
    else:
        # عملية البحث في يوتيوب (15 نتيجة مقسمة على 3 صفحات)
        await perform_youtube_search(update, context, text, page=0)

# تنفيذ البحث في يوتيوب
async def perform_youtube_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    status_msg = await update.message.reply_text(f"🔍 جاري البحث عن: <b>{query}</b>...", parse_mode="HTML")
    
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
        'default_search': 'ytsearch15'
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch15:{query}", download=False)
            entries = info.get('entries', [])
    except Exception:
        await status_msg.edit_text("❌ عذراَ، حدث خطأ أثناء البحث.")
        return

    if not entries:
        await status_msg.edit_text("❌ عذراً، لا توجد نتائج.")
        return

    # تخزين النتائج في الذاكرة المؤقتة للمستخدم
    user_id = update.effective_user.id
    SEARCH_CACHE[user_id] = entries

    await send_search_page(status_msg, user_id, query, page)

async def send_search_page(message, user_id, query, page):
    entries = SEARCH_CACHE.get(user_id, [])
    start_idx = page * 5
    end_idx = start_idx + 5
    current_entries = entries[start_idx:end_idx]

    if not current_entries:
        return

    text_lines = [f"🔍 نتائج بحث اليوتيوب لـ \"{query}\"\n"]
    
    for entry in current_entries:
        title = entry.get('title', 'بدون عنوان')
        uploader = entry.get('uploader', 'غير معروف')
        duration_sec = entry.get('duration', 0)
        
        # تنسيق الوقت
        mins = duration_sec // 60
        secs = duration_sec % 60
        duration_str = f"{mins}:{secs:02d}"
        
        views = entry.get('view_count', 0)
        if views > 1000000:
            views_str = f"{views / 1000000:.1f}M"
        elif views > 1000:
            views_str = f"{views / 1000:.1f}K"
        else:
            views_str = str(views)

        v_id = entry.get('id')
        
        text_lines.append(f"🎬 {title}")
        text_lines.append(f"👤 {uploader}")
        text_lines.append(f"⏱ {duration_str} - 👁 {views_str}")
        text_lines.append(f"🔗 /dl_{v_id}\n")

    response_text = "\n".join(text_lines)

    # أزرار التنقل (السابق / التالي)
    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("« السابق", callback_data=f"search_page_{page-1}"))
    if end_idx < len(entries):
        nav_buttons.append(InlineKeyboardButton("التالي »", callback_data=f"search_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)

    markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    try:
        await message.edit_text(response_text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await message.reply_text(response_text, parse_mode="HTML", reply_markup=markup)

# معالجة أزرار التنقل بالبحث
async def search_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    page = int(data.split("_")[-1])
    user_id = query.from_user.id

    if user_id not in SEARCH_CACHE:
        await query.answer("انتهت صلاحية البحث، أرسل الكلمة من جديد.", show_alert=True)
        return

    # استخراج الاستعلام القديم إن أمكن أو تحديث الصفحة
    entries = SEARCH_CACHE[user_id]
    start_idx = page * 5
    end_idx = start_idx + 5
    current_entries = entries[start_idx:end_idx]

    text_lines = ["🔍 نتائج بحث اليوتيوب:\n"]
    for entry in current_entries:
        title = entry.get('title', 'بدون عنوان')
        uploader = entry.get('uploader', 'غير معروف')
        duration_sec = entry.get('duration', 0)
        mins = duration_sec // 60
        secs = duration_sec % 60
        duration_str = f"{mins}:{secs:02d}"
        
        views = entry.get('view_count', 0)
        views_str = f"{views / 1000000:.1f}M" if views > 1000000 else str(views)
        v_id = entry.get('id')
        
        text_lines.append(f"🎬 {title}")
        text_lines.append(f"👤 {uploader}")
        text_lines.append(f"⏱ {duration_str} - 👁 {views_str}")
        text_lines.append(f"🔗 /dl_{v_id}\n")

    response_text = "\n".join(text_lines)

    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("« السابق", callback_data=f"search_page_{page-1}"))
    if end_idx < len(entries):
        nav_buttons.append(InlineKeyboardButton("التالي »", callback_data=f"search_page_{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    await query.message.edit_text(response_text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

# نظام التحميل والتحقق من المدة (10 دقائق)
async def process_download(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text("⏳ جاري فحص الرابط ومعلومات المقطع...")

    ydl_opts = {'quiet': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration_sec = info.get('duration', 0)
            duration_mins = duration_sec / 60
            title = info.get('title', 'مقطع فيديو')
    except Exception:
        await msg.edit_text("❌ عذراً، لم أتمكن من جلب بيانات هذا الرابط أو أنه غير داعم.")
        return

    # الشرط: إذا كان المقطع أكثر من 10 دقائق
    if duration_mins > 10:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⭐ ارسل نجمة", callback_data="send_star")]
        ])
        await msg.edit_text(
            f"⚠️ <b>هذا المقطع حجمه أكبر من 10 دقائق للتحميل!</b>\n"
            f"مدة الفيديو: {duration_mins:.1f} دقائق.\n"
            "للاستمرار والتحميل، يرجى إرسال نجمة ⭐",
            parse_mode="HTML",
            reply_markup=markup
        )
        return

    await msg.edit_text(f"🚀 تم فحص المقطع بنجاح ({duration_mins:.1f} دقيقة).\nجاري التحميل والإرسال...")
    # هنا يتم استكمال كود التحميل الفعلي وإرسال الفيديو للمستخدم

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(search_pagination_callback, pattern="^search_page_"))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("البوت يعمل الآن على تريمكس...")
    app.run_polling()

if __name__ == "__main__":
    main()

