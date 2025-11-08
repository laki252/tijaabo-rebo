import os
import asyncio
import threading
import json
import requests
import io
import logging
import subprocess
import speech_recognition as sr
from flask import Flask, request
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction, ChatMemberStatus
from pydub import AudioSegment, silence
import math

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
if FFMPEG_BINARY is None:
    logging.warning("ffmpeg binary not found. Set FFMPEG_BINARY env var or place ffmpeg in ./ffmpeg or /usr/bin/ffmpeg")

flask_app = Flask(__name__)
@flask_app.route("/", methods=["GET", "POST", "HEAD"])
def keep_alive():
    return "Bot is alive ✅", 200
def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

API_ID = int(os.environ.get("API_ID", "29169428"))
API_HASH = os.environ.get("API_HASH", "55742b16a85aac494c7944568b5507e5")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7188814271:AAFdGogN_HID7Cqs__TPccM8e9OmtcGK7w")
REQUEST_TIMEOUT_GEMINI = int(os.environ.get("REQUEST_TIMEOUT_GEMINI", "300"))

DEFAULT_GEMINI_KEYS = "AIzaSyADfan-yL9WdrlVd3vzbCdJM7tXbA72dG,AIzaSyAKrnVxMMPIqSzovoUggXy5CQ_4Hi7I_NU,AIzaSyD0sYw4zzlXhbSV3HLY9wM4zCqX8ytR8zQ"
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", DEFAULT_GEMINI_KEYS)

PREPEND_SILENCE_MS = 10000
MAX_CHUNK_MS = 45000
MAX_UPLOAD_SIZE_MB = 250

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
("🇹🇭 ไทย","th"), ("🇻🇳 Tiếng Việt","vi"), ("🇯🇵 日本語","ja"), ("🇰🇷 한국어","ko"),
("🇨🇳 中文","zh"), ("🇳🇱 Nederlands:nl","nl"), ("🇸🇪 Svenska","sv"), ("🇳🇴 Norsk","no"),
("🇮🇱 עברית","he"), ("🇩🇰 Dansk","da"), ("🇪🇹 አማርኛ","am"), ("🇫🇮 Suomi","fi"),
("🇧🇩 বাংলা","bn"), ("🇰🇪 Kiswahili","sw"), ("🇪🇹 Oromoo","om"), ("🇳🇵 नेपाली","ne"),
("🇵🇱 Polski","pl"), ("🇬🇷 Ελληνικά","el"), ("🇨🇿 Čeština","cs"), ("🇮🇸 Íslenska","is"),
("🇱🇹 Lietuvių","lt"), ("🇱🇻 Latviešu","lv"), ("🇭🇷 Hrvatski","hr"), ("🇷 🇸 Bosanski","bs"),
("🇭🇺 Magyar","hu"), ("🇷🇴 Română","ro"), ("🇸🇴 Somali","so"), ("🇲🇾 Melayu","ms"),
("🇺🇿 O'zbekcha","uz"), ("🇵🇭 Tagalog","tl"), ("🇵🇹 Português","pt")
]

LABELS = [label for label,code in LANGS]
LABEL_TO_CODE = {label: code for label,code in LANGS}
user_lang = {}
user_mode = {}
user_transcriptions = {}
action_usage = {}
user_usage_count = {}

app = Client("media_transcriber", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

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
        raise RuntimeError("FFMPEG binary not found. Cannot process media.")
    output_file = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(input_file)}.wav")
    command = [
        FFMPEG_BINARY,
        "-y",
        "-i", input_file,
        "-ac", "1",
        "-ar", "8000",
        "-vn",
        output_file
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=120)
        return output_file
    except subprocess.CalledProcessError as e:
        logging.error(f"FFMPEG conversion failed: {e}")
        raise RuntimeError(f"FFMPEG failed to convert file: {e}")
    except subprocess.TimeoutExpired:
        logging.error("FFMPEG conversion timed out.")
        raise RuntimeError("Media conversion timed out.")
    except Exception as e:
        logging.error(f"FFMPEG unknown error: {e}")
        raise RuntimeError(f"Media conversion failed: {e}")

def transcribe_file(file_path: str, lang_code: str = "en") -> str:
    r = sr.Recognizer()
    wav_path = None
    silence_segment = AudioSegment.silent(duration=PREPEND_SILENCE_MS)
    try:
        wav_path = convert_to_wav(file_path)
        sound = AudioSegment.from_wav(wav_path)
        chunks = silence.split_on_silence(
            sound,
            min_silence_len=700,
            silence_thresh=sound.dBFS - 14,
            keep_silence=400
        )
        if not chunks:
            chunks = [sound]
        full_text = ""
        max_chunk_ms = MAX_CHUNK_MS
        overlap_ms = 1000
        tmp_files = []
        chunk_index = 0
        for chunk in chunks:
            length_ms = len(chunk)
            if length_ms <= max_chunk_ms:
                chunk_index += 1
                chunk_file = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(wav_path)}_chunk{chunk_index}.wav")
                final_chunk = silence_segment + chunk
                final_chunk.export(chunk_file, format="wav")
                tmp_files.append(chunk_file)
            else:
                start = 0
                part = 0
                step = max_chunk_ms - overlap_ms
                if step <= 0:
                    step = max_chunk_ms
                while start < length_ms:
                    end = min(start + max_chunk_ms, length_ms)
                    sub = chunk[start:end]
                    chunk_index += 1
                    part += 1
                    chunk_file = os.path.join(DOWNLOADS_DIR, f"{os.path.basename(wav_path)}_chunk{chunk_index}.wav")
                    final_sub = silence_segment + sub
                    final_sub.export(chunk_file, format="wav")
                    tmp_files.append(chunk_file)
                    start += step
        for i, chunk_file in enumerate(tmp_files, 1):
            with sr.AudioFile(chunk_file) as source:
                audio_data = r.record(source)
                try:
                    text_part = r.recognize_google(audio_data, language=lang_code)
                    full_text += text_part.strip() + " "
                except sr.UnknownValueError:
                    logging.info("Chunk %d lama aqoonsan", i)
                except sr.RequestError as e:
                    logging.error("Chunk %d request error: %s", i, e)
            try:
                os.remove(chunk_file)
            except Exception:
                pass
        if not full_text:
            raise sr.UnknownValueError("No audio recognized from chunks")
        return full_text.strip()
    except sr.UnknownValueError:
        logging.warning("Google Speech Recognition don't understand the voice.")
        return "⚠️ Warning Make sure the voice is clear or speaking in the language you Choosed."
    except sr.RequestError as e:
        logging.error(f"Google Speech Recognition request error: {e}")
        return f"Error: Could not request results from Google; {e}"
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        raise e
    finally:
        if wav_path and os.path.exists(wav_path):
            os.remove(wav_path)

WELCOME_MESSAGE = """👋 **Salaam!**
• Send me
• **voice message**
• **audio file**
• **video**
• to transcribe for free
"""

HELP_MESSAGE = """Commands supported:
/start - Show welcome message
/lang  - Change language
/mode  - Change result delivery mode
/help  - This help message

Send a voice/audio/video (up to {max_size}MB) and I will transcribe it Need help? Contact: @lakigithub
""".format(max_size=MAX_UPLOAD_SIZE_MB)

async def is_user_in_channel(client, user_id: int) -> bool:
    try:
        member = await client.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER, ChatMemberStatus.RESTRICTED)
    except Exception:
        return False

async def ensure_joined(client, obj) -> bool:
    if isinstance(obj, CallbackQuery):
        uid = obj.from_user.id
        reply_target = obj.message
    else:
        uid = obj.from_user.id
        reply_target = obj
    count = user_usage_count.get(uid, 0)
    if count < 3:
        user_usage_count[uid] = count + 1
        return True
    try:
        if await is_user_in_channel(client, uid):
            return True
    except Exception:
        pass
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.strip('@')}")]])
    text = f"🚫 First join the channel {REQUIRED_CHANNEL} to use this bot"
    try:
        if isinstance(obj, CallbackQuery):
            try:
                await obj.answer("🚫 First join the channel", show_alert=True)
            except Exception:
                pass
        await reply_target.reply_text(text, reply_markup=kb)
    except Exception:
        try:
            await client.send_message(uid, text, reply_markup=kb)
        except Exception:
            pass
    return False

@app.on_message(filters.command("start") & filters.private)
async def start(client, message: Message):
    if not await ensure_joined(client, message):
        return
    buttons, row = [], []
    for i, (label, code) in enumerate(LANGS, 1):
        row.append(InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|start"))
        if i % 3 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply_text("**Choose your file language for transcription using the below buttons:**", reply_markup=keyboard)

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message: Message):
    if not await ensure_joined(client, message):
        return
    await message.reply_text(HELP_MESSAGE)

@app.on_message(filters.command("lang") & filters.private)
async def lang_command(client, message: Message):
    if not await ensure_joined(client, message):
        return
    buttons, row = [], []
    for i, (label, code) in enumerate(LANGS, 1):
        row.append(InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|lang"))
        if i % 3 == 0:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    keyboard = InlineKeyboardMarkup(buttons)
    await message.reply_text("**Choose your file language for transcription using the below buttons:**", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^lang\|"))
async def language_callback_query(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query):
        return
    try:
        parts = callback_query.data.split("|")
        _, code, label = parts[:3]
        origin = parts[3] if len(parts) > 3 else "unknown"
    except Exception:
        await callback_query.answer("Invalid language selection data.", show_alert=True)
        return
    uid = callback_query.from_user.id
    user_lang[uid] = code
    if origin == "start":
        await callback_query.message.edit_text(WELCOME_MESSAGE, reply_markup=None)
    elif origin == "lang":
        await callback_query.message.delete()
    await callback_query.answer(f"Language set to: {label}", show_alert=False)

@app.on_message(filters.command("mode") & filters.private)
async def choose_mode(client, message: Message):
    if not await ensure_joined(client, message):
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Split messages", callback_data="mode|Split messages")],
        [InlineKeyboardButton("📄 Text File", callback_data="mode|Text File")]
    ])
    await message.reply_text("Choose **output mode**:", reply_markup=keyboard)

@app.on_callback_query(filters.regex(r"^mode\|"))
async def mode_callback_query(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query):
        return
    try:
        _, mode_name = callback_query.data.split("|")
    except Exception:
        await callback_query.answer("Invalid mode selection data.", show_alert=True)
        return
    uid = callback_query.from_user.id
    user_mode[uid] = mode_name
    await callback_query.answer(f"Mode set to: {mode_name}", show_alert=False)
    try:
        await callback_query.message.delete()
    except Exception:
        pass

@app.on_message(filters.private & filters.text)
async def handle_text(client, message: Message):
    if not await ensure_joined(client, message):
        return
    uid = message.from_user.id
    text = message.text
    if text in ["💬 Split messages", "📄 Text File"]:
        user_mode[uid] = text
        await message.reply_text(f"Output mode set to: **{text}**")
        return

@app.on_message(filters.private & (filters.audio | filters.voice | filters.video | filters.document))
async def handle_media(client, message: Message):
    if not await ensure_joined(client, message):
        return
    file = message.document or message.video or message.audio or message.voice
    if file and hasattr(file, "file_size") and file.file_size:
        size_mb = file.file_size / (1024 * 1024)
        if size_mb > MAX_UPLOAD_SIZE_MB:
            await message.reply_text(f"⚠️ File size {size_mb:.1f} MB exceeds limit of {MAX_UPLOAD_SIZE_MB} MB")
            return
    uid = message.from_user.id
    if uid not in user_lang:
        buttons, row = [], []
        for i, (label, code) in enumerate(LANGS, 1):
            row.append(InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|start"))
            if i % 3 == 0:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        keyboard = InlineKeyboardMarkup(buttons)
        await message.reply_text("**Please choose your file language first:**", reply_markup=keyboard)
        return
    lang = user_lang[uid]
    mode = user_mode.get(uid, "📄 Text File")
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        file_path = await download_media(message)
    except Exception as e:
        await message.reply_text(f"⚠️ Download error: {e}")
        return
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, transcribe_file, file_path, lang)
    except Exception as e:
        await message.reply_text(f"❌ Transcription error: {e}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    if not text or text.startswith("Error:") or text.startswith("⚠️ Warning"):
        await message.reply_text(text or "⚠️ Warning Make sure the voice is clear or speaking in the language you Choosed.", reply_to_message_id=message.id)
        return
    reply_msg_id = message.id
    sent_message = None
    if len(text) > 4095:
        if mode == "💬 Split messages":
            for part in [text[i:i+4095] for i in range(0, len(text), 4095)]:
                await client.send_chat_action(message.chat.id, ChatAction.TYPING)
                sent_message = await message.reply_text(part, reply_to_message_id=reply_msg_id)
        else:
            file_name = os.path.join(DOWNLOADS_DIR, "Transcript.txt")
            with open(file_name, "w", encoding="utf-8") as f:
                f.write(text)
            await client.send_chat_action(message.chat.id, ChatAction.UPLOAD_DOCUMENT)
            sent_message = await client.send_document(message.chat.id, file_name, caption="Open this file and copy the text inside 👍", reply_to_message_id=reply_msg_id)
            os.remove(file_name)
    else:
        await client.send_chat_action(message.chat.id, ChatAction.TYPING)
        sent_message = await message.reply_text(text, reply_to_message_id=reply_msg_id)
    if sent_message:
        try:
            keyboard = build_action_keyboard(sent_message.chat.id, sent_message.id, len(text))
            user_transcriptions.setdefault(sent_message.chat.id, {})[sent_message.id] = {"text": text, "origin": reply_msg_id}
            action_usage[f"{sent_message.chat.id}|{sent_message.id}|clean"] = 0
            if len(text) > 1000:
                action_usage[f"{sent_message.chat.id}|{sent_message.id}|summarize"] = 0
            await sent_message.edit_reply_markup(keyboard)
        except Exception as e:
            logging.error(f"Failed to attach keyboard or init usage: {e}")

@app.on_callback_query(filters.regex(r"^clean\|"))
async def clean_up_callback(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query):
        return
    try:
        _, chat_id_str, msg_id_str = callback_query.data.split("|")
        chat_id = int(chat_id_str)
        msg_id = int(msg_id_str)
    except Exception:
        await callback_query.answer("Invalid callback data.", show_alert=True)
        return
    usage_key = f"{chat_id}|{msg_id}|clean"
    usage = action_usage.get(usage_key, 0)
    if usage >= 1:
        await callback_query.answer("Clean up unavailable (maybe expired or not found).", show_alert=True)
        return
    action_usage[usage_key] = usage + 1
    stored = user_transcriptions.get(chat_id, {}).get(msg_id)
    if not stored:
        await callback_query.answer("Clean up unavailable (maybe expired or not found).", show_alert=True)
        return
    stored_text = stored.get("text")
    orig_msg_id = stored.get("origin")
    await callback_query.answer("Cleaning up...", show_alert=False)
    await client.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        loop = asyncio.get_event_loop()
        uid = callback_query.from_user.id
        lang = user_lang.get(uid, "en")
        mode = user_mode.get(uid, "📄 Text File")
        instruction = f"Clean and normalize this transcription (lang={lang}). Remove ASR artifacts like [inaudible], repeated words, filler noises, timestamps, and incorrect punctuation. Produce a clean, well‑punctuated, readable text in the same language. Do not add introductions or explanations."
        cleaned_text = await loop.run_in_executor(None, ask_gemini, stored_text, instruction)
        if not cleaned_text:
            await client.send_message(chat_id, "No cleaned text returned.", reply_to_message_id=orig_msg_id)
            return
        if len(cleaned_text) > 4095:
            if mode == "💬 Split messages":
                for part in [cleaned_text[i:i+4095] for i in range(0, len(cleaned_text), 4095)]:
                    await client.send_message(chat_id, part, reply_to_message_id=orig_msg_id)
            else:
                file_name = os.path.join(DOWNLOADS_DIR, "Cleaned.txt")
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(cleaned_text)
                await client.send_chat_action(chat_id, ChatAction.UPLOAD_DOCUMENT)
                await client.send_document(chat_id, file_name, caption="Cleaned Transcript", reply_to_message_id=orig_msg_id)
                os.remove(file_name)
        else:
            await client.send_message(chat_id, cleaned_text, reply_to_message_id=orig_msg_id)
    except Exception as e:
        logging.exception("Error in clean_up_callback")
        await client.send_message(chat_id, f"❌ Error during cleanup: {e}", reply_to_message_id=orig_msg_id)

@app.on_callback_query(filters.regex(r"^summarize\|"))
async def get_key_points_callback(client, callback_query: CallbackQuery):
    if not await ensure_joined(client, callback_query):
        return
    try:
        _, chat_id_str, msg_id_str = callback_query.data.split("|")
        chat_id = int(chat_id_str)
        msg_id = int(msg_id_str)
    except Exception:
        await callback_query.answer("Invalid callback data.", show_alert=True)
        return
    usage_key = f"{chat_id}|{msg_id}|summarize"
    usage = action_usage.get(usage_key, 0)
    if usage >= 1:
        await callback_query.answer("Summarize unavailable (maybe expired or not found).", show_alert=True)
        return
    action_usage[usage_key] = usage + 1
    stored = user_transcriptions.get(chat_id, {}).get(msg_id)
    if not stored:
        await callback_query.answer("Summarize unavailable (maybe expired or not found).", show_alert=True)
        return
    stored_text = stored.get("text")
    orig_msg_id = stored.get("origin")
    await callback_query.answer("Generating summary...", show_alert=False)
    await client.send_chat_action(chat_id, ChatAction.TYPING)
    try:
        loop = asyncio.get_event_loop()
        uid = callback_query.from_user.id
        lang = user_lang.get(uid, "en")
        mode = user_mode.get(uid, "📄 Text File")
        instruction = f"What is this report and what is it about? Please summarize them for me into (lang={lang}) without adding any introductions, notes, or extra phrases."
        summary = await loop.run_in_executor(None, ask_gemini, stored_text, instruction)
        if not summary:
            await client.send_message(chat_id, "No Summary returned.", reply_to_message_id=orig_msg_id)
            return
        if len(summary) > 4095:
            if mode == "💬 Split messages":
                for part in [summary[i:i+4095] for i in range(0, len(summary), 4095)]:
                    await client.send_message(chat_id, part, reply_to_message_id=orig_msg_id)
            else:
                file_name = os.path.join(DOWNLOADS_DIR, "Summary.txt")
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(summary)
                await client.send_chat_action(chat_id, ChatAction.UPLOAD_DOCUMENT)
                await client.send_document(chat_id, file_name, caption="Summary", reply_to_message_id=orig_msg_id)
                os.remove(file_name)
        else:
            await client.send_message(chat_id, summary, reply_to_message_id=orig_msg_id)
    except Exception as e:
        logging.exception("Error in get_key_points_callback")
        await client.send_message(chat_id, f"❌ Error during summary: {e}", reply_to_message_id=orig_msg_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run()
