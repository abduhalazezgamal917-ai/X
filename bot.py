import logging
import os
import uuid
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from yt_dlp import YoutubeDL

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("ZenoXBot")

TOKEN = "8548413224:AAGxpeH4E95UHG5s2qk80kxIgp63uLrPp-g"
CHANNEL = "@ZenoX_Tools"
ADMIN_ID = 6043858925

SEARCH_CACHE = {}
URL_CACHE = {} # لتخزين الروابط الطويلة وربطها بمعرف قصير للأزرار

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return

    if not await check_user_subscription(context.bot, user.id):
        channel_link = f"https://t.me/{CHANNEL.lstrip('@')}"
        text = "🚧┇عذراً، عليك الاشتراك في قناة البوت أولاً. 🚧\n🔍 ثم اضغط تحقق."
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("اشترك في القناة 📡", url=channel_link)],
            [InlineKeyboardButton("تحقق 🔍", callback_data="check_sub")]
        ])
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup)
        return

    welcome_text = (
        f"أهلاً بك يا <b>{user.first_name}</b> في بوت ZenoX للتحميل والبحث 🚀\n\n"
        "• أرسل أي رابط (يوتيوب، تيك توك، انستا، سناب، فيسبوك، بينترست) لتحميله فوراً.\n"
        "• أو أرسل أي نص للبحث المباشر في يوتيوب!"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await check_user_subscription(context.bot, query.from_user.id):
        await query.answer("❌ لم تقم بالاشتراك في القناة بعد!", show_alert=True)
        return
    await query.message.delete()
    await query.message.reply_text("✅ تم التحقق بنجاح! أرسل الآن رابطك أو كلمات البحث 🎬")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user: return

    if not await check_user_subscription(context.bot, user.id):
        await update.message.reply_text("🚧 عذراً، يجب الاشتراك في قناة البوت أولاً لاستخدامه.")
        return

    text = update.message.text.strip()

    if text.startswith("/dl_"):
        video_id = text.replace("/dl_", "")
        real_url = f"https://www.youtube.com/watch?v={video_id}"
        await process_link_info(update, context, real_url)
    elif text.startswith("http"):
        await process_link_info(update, context, text)
    else:
        await perform_youtube_search(update, context, text, page=0)

# ================== نظام البحث (نفس القديم) ==================
async def perform_youtube_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str, page: int = 0):
    status_msg = await update.message.reply_text(f"🔍 جاري البحث عن: <b>{query}</b>...", parse_mode="HTML")
    ydl_opts = {'extract_flat': True, 'quiet': True, 'default_search': 'ytsearch15'}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch15:{query}", download=False)
            entries = info.get('entries', [])
    except Exception:
        await status_msg.edit_text("❌ عذراً، حدث خطأ أثناء البحث.")
        return

    if not entries:
        await status_msg.edit_text("❌ عذراً، لا توجد نتائج.")
        return

    user_id = update.effective_user.id
    SEARCH_CACHE[user_id] = entries
    await send_search_page(status_msg, user_id, query, page)

async def send_search_page(message, user_id, query, page):
    entries = SEARCH_CACHE.get(user_id, [])
    start_idx = page * 5
    current_entries = entries[start_idx:start_idx + 5]

    if not current_entries: return

    text_lines = [f"🔍 نتائج بحث اليوتيوب لـ \"{query}\"\n"]
    for entry in current_entries:
        title = entry.get('title', 'بدون عنوان')
        uploader = entry.get('uploader', 'غير معروف')
        mins, secs = divmod(entry.get('duration', 0), 60)
        views = entry.get('view_count', 0)
        views_str = f"{views / 1000000:.1f}M" if views and views > 1000000 else str(views or 0)
        
        text_lines.append(f"🎬 {title}")
        text_lines.append(f"👤 {uploader}")
        text_lines.append(f"⏱ {mins}:{secs:02d} - 👁 {views_str}")
        text_lines.append(f"🔗 /dl_{entry.get('id')}\n")

    keyboard, nav_buttons = [], []
    if page > 0: nav_buttons.append(InlineKeyboardButton("« السابق", callback_data=f"search_page_{page-1}"))
    if start_idx + 5 < len(entries): nav_buttons.append(InlineKeyboardButton("التالي »", callback_data=f"search_page_{page+1}"))
    if nav_buttons: keyboard.append(nav_buttons)

    try:
        await message.edit_text("\n".join(text_lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)
    except Exception:
        await message.reply_text("\n".join(text_lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def search_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if user_id not in SEARCH_CACHE:
        await query.answer("انتهت صلاحية البحث، أرسل الكلمة من جديد.", show_alert=True)
        return
    await send_search_page(query.message, user_id, "نتائج البحث", int(query.data.split("_")[-1]))

# ================== النظام الجديد: جلب البيانات وعرض الأزرار ==================
async def process_link_info(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text("⏳ جاري فحص الرابط من قبل ZenoX...")
    
    ydl_opts_info = {'quiet': True}
    try:
        with YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        await msg.edit_text("❌ عذراً، لم أتمكن من التعرف على هذا الرابط.")
        return

    # إنشاء كود قصير للرابط عشان حجم الـ callback_data في تيليجرام محدود
    short_id = str(uuid.uuid4())[:8]
    URL_CACHE[short_id] = url

    title = info.get('title', 'بدون عنوان')
    uploader = info.get('uploader', info.get('extractor', 'غير معروف'))
    thumbnail = info.get('thumbnail', None)
    duration = info.get('duration', 0)
    mins, secs = divmod(duration, 60)
    views = info.get('view_count', 0)
    views_str = f"{views / 1000000:.1f}M" if views and views > 1000000 else str(views or 0)

    caption = (
        f"🎬 <b>{title}</b>\n\n"
        f"👤 {uploader}\n"
        f"⏱ {mins:02d}:{secs:02d} - 👁 {views_str}"
    )

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 مقطع فيديو", callback_data=f"down_vid_{short_id}")],
        [InlineKeyboardButton("🎵 ملف صوتي", callback_data=f"down_aud_{short_id}"),
         InlineKeyboardButton("🎙 بصمة صوتية", callback_data=f"down_voc_{short_id}")]
    ])

    await msg.delete()
    if thumbnail:
        await update.message.reply_photo(photo=thumbnail, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await update.message.reply_text(caption, parse_mode="HTML", reply_markup=markup)

# ================== نظام التحميل الفعلي بعد ضغط الزر ==================
async def download_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data.split("_")[1] # vid, aud, voc
    short_id = query.data.split("_")[2]
    
    url = URL_CACHE.get(short_id)
    if not url:
        await query.message.reply_text("❌ انتهت صلاحية الرابط، أرسله من جديد.")
        return

    status_msg = await query.message.reply_text("🚀 جاري التحميل والضغط... الرجاء الانتظار.")

    output_template = f"zenox_dl_{short_id}.%(ext)s"
    
    # إعدادات التقليص الذكية للـ Video
    if action == "vid":
        # يبحث عن جودة أقل من 45 ميجا، وإذا مافي يختار أسوأ جودة عشان يقلص الحجم اجباري
        ydl_opts = {
            'format': 'bestvideo[filesize<45M]+bestaudio/best[filesize<45M]/worst',
            'outtmpl': output_template,
            'quiet': True
        }
    elif action == "aud":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'quiet': True
        }
    elif action == "voc":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'vorbis'}], # صيغة البصمة
            'quiet': True
        }

    file_path = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            # استخراج اسم الملف النهائي
            file_path = ydl.prepare_filename(info_dict)
            if action == "aud": file_path = file_path.rsplit('.', 1)[0] + '.mp3'
            if action == "voc": file_path = file_path.rsplit('.', 1)[0] + '.ogg'

        if os.path.exists(file_path):
            await status_msg.edit_text("📤 جاري إرسال الملف...")
            with open(file_path, 'rb') as file:
                if action == "vid":
                    await query.message.reply_video(video=file, caption="🎬 تم التحميل بواسطة ZenoX", supports_streaming=True)
                elif action == "aud":
                    await query.message.reply_audio(audio=file, caption="🎵 تم التحميل بواسطة ZenoX")
                elif action == "voc":
                    await query.message.reply_voice(voice=file, caption="🎙 تم التحميل بواسطة ZenoX")
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ حدث خطأ أثناء تجهيز الملف.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text("❌ عذراً، فشل التحميل. قد يكون المقطع محمي أو كبير جداً.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r"^/dl_"), handle_message))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(search_pagination_callback, pattern="^search_page_"))
    
    # المعالج الجديد لخيارات التحميل الثلاثة
    app.add_handler(CallbackQueryHandler(download_action_callback, pattern="^down_"))
    
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("البوت يعمل بكامل طاقته (V2)...")
    app.run_polling()

if __name__ == "__main__":
    main()
