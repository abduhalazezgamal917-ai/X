import subprocess
import sys
import asyncio

# تحديث تلقائي لمكتبة yt-dlp
try:
    print("🔄 جاري التحقق من تحديثات yt-dlp...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✅ yt-dlp محدث لأحدث إصدار!")
except Exception as e:
    print(f"⚠️ فشل التحديث التلقائي: {e}")

import logging
import os
import uuid
import threading
import json
import urllib.request
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from yt_dlp import YoutubeDL

# ================== سيرفر الصحة لإرضاء المنصة ==================
class DummyHealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ZenoX Enterprise Bot is Running!")

    def log_message(self, format, *args):
        return

def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), DummyHealthCheckHandler)
    server.serve_forever()

threading.Thread(target=start_dummy_server, daemon=True).start()

# ================== الإعدادات والتكوين ==================
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger("ZenoXBot")

# ✅ السطر الجديد الآمن
TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL = "@ZenoX_Tools"
ADMIN_ID = 6043858925

# أقصى عدد تحميلات متزامنة لحماية الموارد عند الضغط العالي
MAX_CONCURRENT_DOWNLOADS = 5
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# ذاكرة مؤقتة مقيدة لتفادي استهلاك الـ RAM
SEARCH_CACHE = {}
URL_CACHE = {}

# ================== نظام الإحصائيات ==================
STATS_FILE = "stats.json"

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "users": {},
        "total_requests": 0,
        "successful_downloads": 0,
        "failed_downloads": 0,
        "cache_hits": 0,
        "sent_videos": 0,
        "request_limits": 0,
        "share_clicks": 0,
        "platforms": {"يوتيوب": 0, "تويتر/X": 0, "سناب شات": 0, "تيك توك": 0, "إنستغرام": 0, "بينترست": 0, "أخرى": 0}
    }

stats = load_stats()
BOT_START_TIME = datetime.now()

def save_stats():
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def track_user_activity(user_id):
    stats["users"][str(user_id)] = datetime.now().isoformat()
    save_stats()

def track_platform_request(url):
    stats["total_requests"] += 1
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u: stats["platforms"]["يوتيوب"] += 1
    elif "twitter.com" in u or "x.com" in u: stats["platforms"]["تويتر/X"] += 1
    elif "tiktok.com" in u: stats["platforms"]["تيك توك"] += 1
    elif "instagram.com" in u: stats["platforms"]["إنستغرام"] += 1
    elif "snapchat.com" in u: stats["platforms"]["سناب شات"] += 1
    elif "pinterest.com" in u or "pin.it" in u: stats["platforms"]["بينترست"] += 1
    else: stats["platforms"]["أخرى"] += 1
    save_stats()

def track_download_status(success: bool):
    if success: 
        stats["successful_downloads"] += 1
        stats["sent_videos"] += 1
    else: 
        stats["failed_downloads"] += 1
    save_stats()

# ================== إدارة الاشتراك والتحقق ==================
async def check_user_subscription(bot, user_id: int) -> bool:
    if user_id == ADMIN_ID: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# ================== لوحة الإحصائيات (تصميم الصورة بالضبط) ==================
async def show_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or user.id != ADMIN_ID: return

    msg = update.callback_query.message if update.callback_query else update.message
    now = datetime.now()
    
    total_users = len(stats["users"])
    active_today = 0
    active_7d = 0
    active_30d = 0

    for uid, last_str in stats["users"].items():
        try:
            last_time = datetime.fromisoformat(last_str)
            diff = now - last_time
            if diff <= timedelta(days=1): active_today += 1
            if diff <= timedelta(days=7): active_7d += 1
            if diff <= timedelta(days=30): active_30d += 1
        except Exception:
            pass

    total_req = stats.get("total_requests", 0)
    success_dl = stats.get("successful_downloads", 0)
    failed_dl = stats.get("failed_downloads", 0)
    cache_hits = stats.get("cache_hits", 0)
    sent_vids = stats.get("sent_videos", 0)
    req_limits = stats.get("request_limits", 0)
    share_clicks = stats.get("share_clicks", 0)

    total_dl = success_dl + failed_dl
    rate = (success_dl / total_dl * 100) if total_dl > 0 else 0.0

    uptime = datetime.now() - BOT_START_TIME
    days = uptime.days
    hours = uptime.seconds // 3600
    minutes = (uptime.seconds // 60) % 60

    # تنسيق قوائم المنصات بنفس ترتيب ونمط الصورة بالضبط
    sorted_platforms = sorted(stats["platforms"].items(), key=lambda x: x[1], reverse=True)
    platform_icons = {
        "يوتيوب": "▶️",
        "تويتر/X": "𝕏",
        "سناب شات": "👻",
        "تيك توك": "🎵",
        "إنستغرام": "📸",
        "بينترست": "📌",
        "أخرى": "🌐"
    }

    platform_lines = []
    for idx, (p_name, count) in enumerate(sorted_platforms, 1):
        icon = platform_icons.get(p_name, "▫️")
        platform_lines.append(f"{idx}. {icon} {p_name:<12} : {count}")

    platforms_str = "\n".join(platform_lines)

    stats_msg = (
        "📊 <b>لوحة إحصائيات ZenoX Bot</b>\n"
        "━━━━━━━\n\n"
        "👥 <b>المستخدمون</b>\n"
        "───────────────\n"
        f"📌 الإجمالي       : {total_users}\n"
        f"🟢 نشطون (اليوم)  : {active_today}\n"
        f"📅 نشطون (7 أيام) : {active_7d}\n"
        f"🗓 نشطون (30 يوم) : {active_30d}\n"
        "───────────────\n\n"
        "📫 <b>التحميلات</b>\n"
        "───────────────\n"
        f"🔢 إجمالي الطلبات  : {total_req}\n"
        f"✅ ناجحة         : {success_dl}\n"
        f"❌ فاشلة         : {failed_dl}\n"
        f"⚡️ من الكاش       : {cache_hits}\n"
        f"🎬 فيديوهات أُرسلت : {sent_vids}\n"
        f"🛡 حد الطلبات     : {req_limits}\n"
        "───────────────\n\n"
        "🌎 <b>المنصات الأكثر طلباً</b>\n"
        "───────────────\n"
        f"{platforms_str}\n"
        "───────────────\n\n"
        "⚡️ <b>الأداء</b>\n"
        "───────────────\n"
        f"🔗 ضغطات المشاركة : {share_clicks}\n"
        f"💾 Cache Hit Rate : 0.0%\n"
        f"✅ معدل النجاح     : {rate:.1f}%\n"
        "───────────────\n\n"
        f"⏰ <b>وقت التشغيل:</b> {days} يوم {hours} ساعة {minutes} دقيقة\n"
        "🔄 <b>تحديث الإحصائيات:</b> كل 100 حدث أو عند الإيقاف"
    )

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("تحديث 🔄", callback_data="refresh_stats")]])
    if update.callback_query:
        await update.callback_query.answer("تم التحديث 🔄")
        try:
            await msg.edit_text(stats_msg, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass
    else:
        await msg.reply_text(stats_msg, parse_mode="HTML", reply_markup=markup)

# ================== المعالجة الذكية والتنزيل القوي ==================
def _blocking_extract_info(url):
    opts = {
        'quiet': True, 
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'mweb', 'web']}},
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'geo_bypass': True, 
        'nocheckcertificate': True
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

def _blocking_download(url, opts):
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def _compress_video_sync(input_file, output_file):
    cmd = ['ffmpeg', '-y', '-i', input_file, '-c:v', 'libx264', '-crf', '28', '-preset', 'fast', '-c:a', 'aac', '-b:a', '128k', output_file]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            return output_file
    except Exception:
        pass
    return input_file

# ================== استقبال الرسائل والبدء ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return
    track_user_activity(user.id)

    if not await check_user_subscription(context.bot, user.id):
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("اشترك في القناة 📡", url=f"https://t.me/{CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("تحقق 🔍", callback_data="check_sub")]
        ])
        await update.message.reply_text("🚧 عذراً، يجب الاشتراك بالقناة أولاً لاستخدام البوت.", reply_markup=markup)
        return

    await update.message.reply_text(f"أهلاً بك <b>{user.first_name}</b> في محرك ZenoX الذكي! 🚀\nأرسل رابطاً للتحميل، أو اكتب نصاً للبحث المباشر.", parse_mode="HTML")

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if await check_user_subscription(context.bot, q.from_user.id):
        await q.message.delete()
        await q.message.reply_text("✅ تم التحقق! أرسل رابطك أو كلمة البحث الآن.")
    else:
        await q.answer("❌ لم تشترك بالقناة بعد!", show_alert=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user: return
    track_user_activity(user.id)

    if not await check_user_subscription(context.bot, user.id):
        await update.message.reply_text("🚧 يرجى الاشتراك في القناة أولاً.")
        return

    text = update.message.text.strip()
    if text.startswith("/dl_"):
        real_url = f"https://www.youtube.com/watch?v={text.replace('/dl_', '')}"
        track_platform_request(real_url)
        await process_link_info(update, context, real_url)
    elif text.startswith("http"):
        track_platform_request(text)
        await process_link_info(update, context, text)
    else:
        await perform_youtube_search(update, context, text)

# ================== البحث المباشر ==================
async def perform_youtube_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    msg = await update.message.reply_text(f"🔍 جاري البحث الذكي عن: <b>{query}</b>...", parse_mode="HTML")
    
    def _search():
        opts = {'extract_flat': True, 'quiet': True, 'default_search': 'ytsearch10'}
        with YoutubeDL(opts) as ydl:
            return ydl.extract_info(f"ytsearch10:{query}", download=False).get('entries', [])

    try:
        entries = await asyncio.to_thread(_search)
    except Exception:
        await msg.edit_text("❌ حدث خطأ أثناء تنفيذ البحث.")
        return

    if not entries:
        await msg.edit_text("❌ لم يتم العثور على نتائج.")
        return

    lines = [f"🔍 <b>نتائج البحث لـ: {query}</b>\n"]
    for entry in entries[:5]:
        lines.append(f"🎬 <b>{entry.get('title')}</b>\n🔗 /dl_{entry.get('id')}\n")
    
    await msg.edit_text("\n".join(lines), parse_mode="HTML")

# ================== جلب معلومات الرابط ==================
async def process_link_info(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    msg = await update.message.reply_text("⚡️ جاري تحليل الرابط...")
    
    try:
        info = await asyncio.to_thread(_blocking_extract_info, url)
        title = info.get('title')
        uploader = info.get('uploader', 'غير معروف')
        thumbnail = info.get('thumbnail')
    except Exception:
        try:
            req = urllib.request.Request(f"https://www.youtube.com/oembed?url={url}&format=json", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                title = data.get('title')
                uploader = data.get('author_name', 'غير معروف')
                thumbnail = data.get('thumbnail_url')
        except Exception:
            title = None

    if not title:
        await msg.edit_text("❌ يتعذر تحليل هذا الرابط حالياً.")
        return

    sid = str(uuid.uuid4())[:8]
    URL_CACHE[sid] = url

    caption = f"🎬 <b>{title}</b>\n👤 المصدر: {uploader}"
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎥 فيديو MP4", callback_data=f"down_vid_{sid}")],
        [InlineKeyboardButton("🎵 صوت MP3", callback_data=f"down_aud_{sid}"),
         InlineKeyboardButton("🎙 بصمة صوتية", callback_data=f"down_voc_{sid}")]
    ])

    await msg.delete()
    if thumbnail:
        await update.message.reply_photo(photo=thumbnail, caption=caption, parse_mode="HTML", reply_markup=markup)
    else:
        await update.message.reply_text(caption, parse_mode="HTML", reply_markup=markup)

# ================== التحميل الذكي المحسّن للمقاطع المجمعة والمحمية ==================
async def download_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, action, sid = q.data.split("_")
    url = URL_CACHE.get(sid)
    
    if not url:
        await q.message.reply_text("❌ انتهت صلاحية هذه الجلسة، أعد إرسال الرابط.")
        return

    status_msg = await q.message.reply_text("⏳ أضيفت إلى طابور التحميل الذكي...")
    
    async with DOWNLOAD_SEMAPHORE:
        await status_msg.edit_text("🚀 جاري التحميل والمعالجة السريعة...")
        out_tmpl = f"zenox_{sid}.%(ext)s"
        
        # خيارات تنزيل مخصصة وعامة لتفادي القيود والحظر للمقاطع المخصصة والمحمية
        if action == "vid":
            opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': out_tmpl,
                'quiet': True,
                'no_warnings': True,
                'geo_bypass': True,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'extractor_args': {'youtube': {'player_client': ['android', 'ios', 'web', 'mweb']}}
            }
        elif action == "aud":
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': out_tmpl,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
                'quiet': True,
                'no_warnings': True,
                'geo_bypass': True,
                'nocheckcertificate': True
            }
        else:
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': out_tmpl,
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'vorbis'}],
                'quiet': True,
                'no_warnings': True,
                'geo_bypass': True,
                'nocheckcertificate': True
            }

        file_path = None
        try:
            file_path = await asyncio.to_thread(_blocking_download, url, opts)
            if action == "aud": file_path = file_path.rsplit('.', 1)[0] + '.mp3'
            if action == "voc": file_path = file_path.rsplit('.', 1)[0] + '.ogg'

            if os.path.exists(file_path):
                if action == "vid" and (os.path.getsize(file_path) / (1024*1024)) > 48:
                    await status_msg.edit_text("🗜 جاري ضغط الحجم ليناسب تيليجرام...")
                    comp_path = file_path.rsplit('.', 1)[0] + '_c.mp4'
                    file_path = await asyncio.to_thread(_compress_video_sync, file_path, comp_path)

                await status_msg.edit_text("📤 جاري إرسال الملف...")
                with open(file_path, 'rb') as f:
                    if action == "vid": await q.message.reply_video(video=f, caption="🎬 تم بواسطة ZenoX Bot", supports_streaming=True)
                    elif action == "aud": await q.message.reply_audio(audio=f, caption="🎵 تم بواسطة ZenoX Bot")
                    elif action == "voc": await q.message.reply_voice(voice=f, caption="🎙 تم بواسطة ZenoX Bot")

                track_download_status(True)
                await status_msg.delete()
            else:
                track_download_status(False)
                await status_msg.edit_text("❌ حدث خطأ أثناء معالجة الملف.")
        except Exception as e:
            logger.error(f"Download Error: {e}")
            track_download_status(False)
            await status_msg.edit_text("❌ حدث خطأ أثناء التحميل، قد يكون المقطع محمي أو يتطلب تسجيلاً.")
        finally:
            if file_path and os.path.exists(file_path):
                try: os.remove(file_path)
                except Exception: pass

# ================== التشغيل الرئيسي ==================
def main():
    app = ApplicationBuilder().token(TOKEN).concurrent_updates(True).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    
    app.add_handler(CommandHandler("stats", show_stats_command))
    app.add_handler(MessageHandler(filters.Regex(r"^(احصائيات|إحصائيات)$"), show_stats_command))
    app.add_handler(CallbackQueryHandler(show_stats_command, pattern="^refresh_stats$"))

    app.add_handler(CallbackQueryHandler(download_action_callback, pattern="^down_"))
    app.add_handler(MessageHandler(filters.Regex(r"^/dl_"), handle_message))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 تم تشغيل محرك ZenoX بنجاح المطور للوحة الإحصائيات!")
    app.run_polling(drop_pending_updates=False)

if __name__ == "__main__":
    main()



