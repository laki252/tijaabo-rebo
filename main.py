import os
import asyncio
import threading
import json
import requests
import logging
import subprocess
import speech_recognition as sr
import telebot
from flask import Flask, request, abort
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction, ChatMemberStatus
from pydub import AudioSegment, silence

API_ID = int(os.environ.get("API_ID", "29169428"))
API_HASH = os.environ.get("API_HASH", "55742b16a85aac494c7944568b5507e5")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8303813448:AAEVDY4a5fzP7pT-Yq-yPfdkzU0EsO87Z1c")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://midkayga-2-baad-1ggd.onrender.com")
PORT = int(os.environ.get("PORT", 8080))

tele_bot = telebot.TeleBot(BOT_TOKEN)
flask_app = Flask(__name__)

app = Client("media_transcriber", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@flask_app.route("/", methods=["GET", "POST", "HEAD"])
def root_route():
    if request.method == 'POST' and request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        tele_bot.process_new_updates([update])
        return '', 200
    return "Bot is alive ✅", 200

@flask_app.route('/set_webhook', methods=['GET'])
def set_wh():
    tele_bot.set_webhook(url=WEBHOOK_URL)
    return f"Webhook set to {WEBHOOK_URL}"

@flask_app.route('/delete_webhook', methods=['GET'])
def del_wh():
    tele_bot.delete_webhook()
    return "Webhook deleted"

@tele_bot.message_handler(commands=['admin'])
def handle_online_telebot(message):
    tele_bot.send_message(message.chat.id, "🤡")

FFMPEG_ENV = os.environ.get("FFMPEG_BINARY", "")
POSSIBLE_FFMPEG_PATHS = [FFMPEG_ENV, "./ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]
FFMPEG_BINARY = None
for p in POSSIBLE_FFMPEG_PATHS:
    if not p:
        continue
    try:
        subprocess.run([p, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
        FFMPEG_BINARY = p
        break
    except Exception:
        continue

REQUEST_TIMEOUT_GEMINI = int(os.environ.get("REQUEST_TIMEOUT_GEMINI", "300"))
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "250"))
MAX_UPLOAD_SIZE = MAX_UPLOAD_MB * 1024 * 1024
DEFAULT_GEMINI_KEYS = "AIzaSyADfan-yL9WdrlVd3vzbCdJM7tXbA72dG,AIzaSyAKrnVxMMPIqSzovoUggXy5CQ_4Hi7I_NU,AIzaSyD0sYw4zzlXhbSV3HLY9wM4zCqX8ytR8zQ"
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", DEFAULT_GEMINI_KEYS)
PREPEND_SILENCE_MS = 10000
MAX_CHUNK_MS = 45000

def parse_keys(s):
    if not s:
        return []
    parts = [p.strip() for p in s.split(",")]
    return [p for p in parts if p]

class KeyRotator:
    def __init__(self, keys):
        self.keys = list(keys)
        self.pos = 0
        self.lock = threading.Lock()
    def get_order(self):
        with self.lock:
            n = len(self.keys)
            if n == 0:
                return []
            return [self.keys[(self.pos + i) % n] for i in range(n)]
    def mark_success(self, key):
        with self.lock:
            try:
                i = self.keys.index(key)
                self.pos = i
            except Exception:
                pass
    def mark_failure(self, key):
        with self.lock:
            n = len(self.keys)
            if n == 0:
                return
            try:
                i = self.keys.index(key)
                self.pos = (i + 1) % n
            except Exception:
                self.pos = (self.pos + 1) % n

gemini_keys_list = parse_keys(GEMINI_API_KEYS)
gemini_rotator = KeyRotator(gemini_keys_list)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DOWNLOADS_DIR = "./downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

REQUIRED_CHANNEL = os.environ.get("REQUIRED_CHANNEL", "@laaaaaaaaalaaaaaa")
LANGS = [
("🇬🇧 English","en"), ("🇸🇦 العربية","ar"), ("🇪🇸 Español","es"), ("🇫🇷 Français","fr"),
("🇷🇺 Русский","ru"), ("🇩🇪 Deutsch","de"), ("🇮🇳 हिन्दी","hi"), ("🇮🇷 فارسی","fa"),
("🇮🇩 Indonesia","id"), ("🇺🇦 Українська","uk"), ("🇦🇿 Azərbaycan","az"), ("🇮🇹 Italiano","it"),
("🇹🇷 Türkçe","tr"), ("🇧🇬 Български","bg"), ("🇷🇸 Srpski","sr"), ("🇵🇰 اردو","ur"),
("🇹🇭 ไทย","th"), ("🇻🇳 Tiếng Việt","vi"), ("🇯🇵 日本語","ja"), ("🇰🇷 한국어","ko"),
("🇨🇳 中文","zh"), ("🇳🇱 Nederlands:nl", "nl"), ("🇸🇪 Svenska","sv"), ("🇳🇴 Norsk","no"),
("🇮🇱 עברית","he"), ("🇩🇰 Dansk","da"), ("🇪🇹 አማርኛ","am"), ("🇫🇮 Suomi","fi"),
("🇧🇩 বাংলা","bn"), ("🇰🇪 Kiswahili","sw"), ("🇪🇹 Oromoo","om"), ("🇳🇵 नेपाली","ne"),
("🇵🇱 Polski","pl"), ("🇬🇷 Ελληνικά","el"), ("🇨🇿 Čeština","cs"), ("🇮🇸 Íslenska","is"),
("🇱🇹 Lietuvių","lt"), ("🇱🇻 Latviešu","lv"), ("🇭🇷 Hrvatski","hr"), ("🇷🇸 Bosanski","bs"),
("🇭🇺 Magyar","hu"), ("🇷🇴 Română","ro"), ("🇸🇴 Somali","so"), ("🇲🇾 Melayu","ms"),
("🇺🇿 O'zbekcha","uz"), ("🇵🇭 Tagalog","tl"), ("🇵🇹 Português","pt")
]

user_lang = {}
user_mode = {}
user_transcriptions = {}
action_usage = {}
user_usage_count = {}

def ask_gemini(text, instruction, timeout=REQUEST_TIMEOUT_GEMINI):
    if not gemini_rotator.keys:
        raise RuntimeError("No GEMINI keys available")
    last_exc = None
    for key in gemini_rotator.get_order():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": instruction}, {"text": text}]}]}
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            if "candidates" in result and isinstance(result["candidates"], list) and len(result["candidates"]) > 0:
                try:
                    gemini_rotator.mark_success(key)
                    return result['candidates'][0]['content']['parts'][0]['text']
                except Exception:
                    gemini_rotator.mark_success(key)
                    return json.dumps(result['candidates'][0])
            gemini_rotator.mark_success(key)
            raise RuntimeError(f"Gemini response lacks candidates: {json.dumps(result)}")
        except Exception as e:
            logging.warning("Gemini key failed, rotating to next key: %s", str(e))
            gemini_rotator.mark_failure(key)
            last_exc = e
            continue
    raise RuntimeError(f"All Gemini keys failed. Last error: {last_exc}")

def build_action_keyboard(chat_id, message_id, text_length):
    buttons = []
    buttons.append([InlineKeyboardButton("⭐️Clean transcript", callback_data=f"clean|{chat_id}|{message_id}")])
    if text_length > 1000:
        buttons.append([InlineKeyboardButton("Get Summarize", callback_data=f"summarize|{chat_id}|{message_id}")])
    return InlineKeyboardMarkup(buttons)

async def download_media(message: Message) -> str:
    file_path = await message.download(file_name=os.path.join(DOWNLOADS_DIR, ""))
    return file_path

def convert_to_wav(input_file: str) -> str:
    if not FFMPEG_BINARY:
        raise RuntimeError("FFMPEG binary not found.")
    output_file = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(input_file)}.wav")
    command = [
        FFMPEG_BINARY, "-y", "-i", input_file,
        "-ac", "1", "-ar", "8000", "-vn", output_file
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=120)
        return output_file
    except Exception as e:
        raise RuntimeError(f"Media conversion failed: {e}")

def transcribe_file(file_path: str, lang_code: str = "en") -> str:
    r = sr.Recognizer()
    wav_path = None
    silence_segment = AudioSegment.silent(duration=PREPEND_SILENCE_MS)
    try:
        wav_path = convert_to_wav(file_path)
        sound = AudioSegment.from_wav(wav_path)
        chunks = silence.split_on_silence(sound, min_silence_len=700, silence_thresh=sound.dBFS - 14, keep_silence=400)
        if not chunks: chunks = [sound]
        full_text = ""
        max_chunk_ms = MAX_CHUNK_MS
        chunk_index = 0
        for chunk in chunks:
            length_ms = len(chunk)
            if length_ms <= max_chunk_ms:
                chunk_index += 1
                chunk_file = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(wav_path)}_chunk{chunk_index}.wav")
                final_chunk = silence_segment + chunk
                final_chunk.export(chunk_file, format="wav")
                with sr.AudioFile(chunk_file) as source:
                    audio_data = r.record(source)
                    try:
                        text_part = r.recognize_google(audio_data, language=lang_code)
                        full_text += text_part.strip() + " "
                    except: pass
                try: os.remove(chunk_file)
                except: pass
            else:
                start = 0
                step = max_chunk_ms - 1000
                if step <= 0: step = max_chunk_ms
                while start < length_ms:
                    end = min(start + max_chunk_ms, length_ms)
                    sub = chunk[start:end]
                    chunk_index += 1
                    chunk_file = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(wav_path)}_chunk{chunk_index}.wav")
                    final_sub = silence_segment + sub
                    final_sub.export(chunk_file, format="wav")
                    with sr.AudioFile(chunk_file) as source:
                        audio_data = r.record(source)
                        try:
                            text_part = r.recognize_google(audio_data, language=lang_code)
                            full_text += text_part.strip() + " "
                        except: pass
                    try: os.remove(chunk_file)
                    except: pass
                    start += step
        if not full_text: raise sr.UnknownValueError("No audio recognized")
        return full_text.strip()
    except sr.UnknownValueError: return "⚠️ Warning Make sure the voice is clear."
    except Exception as e: raise e
    finally:
        if wav_path and os.path.exists(wav_path): os.remove(wav_path)

WELCOME_MESSAGE = """👋 **Salaam!**\n• Send me\n• **voice message**\n• **audio file**\n• **video**\n• to transcribe for free"""
HELP_MESSAGE = f"""Commands supported:\n/start - Welcome\n/lang - Change language\n/mode - Output mode\n/help - Help\nMax size: {MAX_UPLOAD_MB}MB"""

async def is_user_in_channel(client, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, ChatMemberStatus.RESTRICTED)
    except: return False

async def ensure_joined(client, obj) -> bool:
    if isinstance(obj, CallbackQuery):
        uid, reply_target = obj.from_user.id, obj.message
    else:
        uid, reply_target = obj.from_user.id, obj
    count = user_usage_count.get(uid, 0)
    if count < 3:
        user_usage_count[uid] = count + 1
        return True
    try:
        if await is_user_in_channel(client, uid): return True
    except: pass
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.strip('@')}")]])
    text = f"🚫 First join {REQUIRED_CHANNEL} to use this bot"
    try: await reply_target.reply_text(text, reply_markup=kb)
    except:
        try: await client.send_message(uid, text, reply_markup=kb)
        except: pass
    return False

@app.on_message(filters.command("online"))
async def online_pyro(client, message: Message):
    await message.reply("yes Im alive ✅ (Pyrogram)")

@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    if not await ensure_joined(client, message): return
    buttons, row = [], []
    for i, (label, code) in enumerate(LANGS, 1):
        row.append(InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|start"))
        if i % 3 == 0: buttons.append(row); row = []
    if row: buttons.append(row)
    await message.reply_text("**Choose your file language:**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message: Message):
    if not await ensure_joined(client, message): return
    await message.reply_text(HELP_MESSAGE)

@app.on_message(filters.command("lang") & filters.private)
async def lang_command(client, message: Message):
    if not await ensure_joined(client, message): return
    buttons, row = [], []
    for i, (label, code) in enumerate(LANGS, 1):
        row.append(InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|lang"))
        if i % 3 == 0: buttons.append(row); row = []
    if row: buttons.append(row)
    await message.reply_text("**Choose language:**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex(r"^lang\|"))
async def language_callback_query(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query): return
    try:
        parts = callback_query.data.split("|")
        _, code, label = parts[:3]
        origin = parts[3] if len(parts) > 3 else "unknown"
    except: return
    user_lang[callback_query.from_user.id] = code
    if origin == "start": await callback_query.message.edit_text(WELCOME_MESSAGE, reply_markup=None)
    elif origin == "lang": await callback_query.message.delete()
    await callback_query.answer(f"Language set to: {label}", show_alert=False)

@app.on_message(filters.command("mode") & filters.private)
async def choose_mode(client, message: Message):
    if not await ensure_joined(client, message): return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("💬 Split messages", callback_data="mode|Split messages"), InlineKeyboardButton("📄 Text File", callback_data="mode|Text File")]])
    await message.reply_text("Choose output mode:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^mode\|"))
async def mode_callback_query(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query): return
    _, mode_name = callback_query.data.split("|")
    user_mode[callback_query.from_user.id] = mode_name
    await callback_query.answer(f"Mode set to: {mode_name}", show_alert=False)
    try: await callback_query.message.delete()
    except: pass

@app.on_message(filters.private & filters.text)
async def handle_text(client, message: Message):
    if not await ensure_joined(client, message): return
    if message.text in ["💬 Split messages", "📄 Text File"]:
        user_mode[message.from_user.id] = message.text
        await message.reply_text(f"Output mode set to: **{message.text}**")

@app.on_message(filters.private & (filters.audio | filters.voice | filters.video | filters.document))
async def handle_media(client, message: Message):
    if not await ensure_joined(client, message): return
    uid = message.from_user.id
    if uid not in user_lang:
        buttons, row = [], []
        for i, (label, code) in enumerate(LANGS, 1):
            row.append(InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|start"))
            if i % 3 == 0: buttons.append(row); row = []
        if row: buttons.append(row)
        await message.reply_text("**Please choose language first:**", reply_markup=InlineKeyboardMarkup(buttons))
        return
    size = None
    try:
        if getattr(message, "document", None): size = message.document.file_size
        elif getattr(message, "audio", None): size = message.audio.file_size
        elif getattr(message, "video", None): size = message.video.file_size
        elif getattr(message, "voice", None): size = message.voice.file_size
    except: pass
    if size and size > MAX_UPLOAD_SIZE:
        await message.reply_text(f"File too big. Max {MAX_UPLOAD_MB}MB")
        return
    lang = user_lang[uid]
    mode = user_mode.get(uid, "📄 Text File")
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    try: file_path = await download_media(message)
    except Exception as e: await message.reply_text(f"Download error: {e}"); return
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, transcribe_file, file_path, lang)
    except Exception as e:
        await message.reply_text(f"Transcription error: {e}")
        if file_path and os.path.exists(file_path): os.remove(file_path)
        return
    if file_path and os.path.exists(file_path): os.remove(file_path)
    if not text or text.startswith("⚠️"):
        await message.reply_text(text or "⚠️ Unrecognized.", reply_to_message_id=message.id)
        return
    sent_message = None
    if len(text) > 4095:
        if mode == "💬 Split messages":
            for part in [text[i:i+4095] for i in range(0, len(text), 4095)]:
                await client.send_chat_action(message.chat.id, ChatAction.TYPING)
                sent_message = await message.reply_text(part, reply_to_message_id=message.id)
        else:
            file_name = os.path.join(DOWNLOADS_DIR, "Transcript.txt")
            with open(file_name, "w", encoding="utf-8") as f: f.write(text)
            await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
            sent_message = await client.send_document(message.chat.id, file_name, caption="Transcript", reply_to_message_id=message.id)
            os.remove(file_name)
    else:
        await client.send_chat_action(message.chat.id, ChatAction.TYPING)
        sent_message = await message.reply_text(text, reply_to_message_id=message.id)
    if sent_message:
        try:
            keyboard = build_action_keyboard(sent_message.chat.id, sent_message.id, len(text))
            user_transcriptions.setdefault(sent_message.chat.id, {})[sent_message.id] = {"text": text, "origin": message.id}
            action_usage[f"{sent_message.chat.id}|{sent_message.id}|clean"] = 0
            if len(text) > 1000: action_usage[f"{sent_message.chat.id}|{sent_message.id}|summarize"] = 0
            await sent_message.edit_reply_markup(keyboard)
        except: pass

@app.on_callback_query(filters.regex(r"^clean\|"))
async def clean_up_callback(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query): return
    try: _, chat_id, msg_id = callback_query.data.split("|"); chat_id, msg_id = int(chat_id), int(msg_id)
    except: return
    if action_usage.get(f"{chat_id}|{msg_id}|clean", 0) >= 1:
        await callback_query.answer("Expired.", show_alert=True); return
    action_usage[f"{chat_id}|{msg_id}|clean"] += 1
    stored = user_transcriptions.get(chat_id, {}).get(msg_id)
    if not stored: return
    await callback_query.answer("Cleaning...", show_alert=False)
    await client.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        loop = asyncio.get_event_loop()
        instruction = f"Clean and normalize (lang={user_lang.get(callback_query.from_user.id, 'en')}). Remove artifacts."
        cleaned_text = await loop.run_in_executor(None, ask_gemini, stored['text'], instruction)
        if len(cleaned_text) > 4095:
            file_name = os.path.join(DOWNLOADS_DIR, "Cleaned.txt")
            with open(file_name, "w", encoding="utf-8") as f: f.write(cleaned_text)
            await client.send_document(chat_id, file_name, caption="Cleaned", reply_to_message_id=stored['origin'])
            os.remove(file_name)
        else: await client.send_message(chat_id, cleaned_text, reply_to_message_id=stored['origin'])
    except Exception as e: await client.send_message(chat_id, f"Error: {e}", reply_to_message_id=stored['origin'])

@app.on_callback_query(filters.regex(r"^summarize\|"))
async def summarize_callback(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query): return
    try: _, chat_id, msg_id = callback_query.data.split("|"); chat_id, msg_id = int(chat_id), int(msg_id)
    except: return
    if action_usage.get(f"{chat_id}|{msg_id}|summarize", 0) >= 1:
        await callback_query.answer("Expired.", show_alert=True); return
    action_usage[f"{chat_id}|{msg_id}|summarize"] += 1
    stored = user_transcriptions.get(chat_id, {}).get(msg_id)
    if not stored: return
    await callback_query.answer("Summarizing...", show_alert=False)
    await client.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        loop = asyncio.get_event_loop()
        instruction = f"Summarize this text (lang={user_lang.get(callback_query.from_user.id, 'en')})."
        summary = await loop.run_in_executor(None, ask_gemini, stored['text'], instruction)
        if len(summary) > 4095:
            file_name = os.path.join(DOWNLOADS_DIR, "Summary.txt")
            with open(file_name, "w", encoding="utf-8") as f: f.write(summary)
            await client.send_document(chat_id, file_name, caption="Summary", reply_to_message_id=stored['origin'])
            os.remove(file_name)
        else: await client.send_message(chat_id, summary, reply_to_message_id=stored['origin'])
    except Exception as e: await client.send_message(chat_id, f"Error: {e}", reply_to_message_id=stored['origin'])

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run()
