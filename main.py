import os
import threading
import json
import requests
import io
import logging
import time
import uuid
from flask import Flask, request
import telebot
from telebot import types
import assemblyai as aai

flask_app = Flask(__name__)
@flask_app.route("/", methods=["GET", "POST", "HEAD"])
def keep_alive():
    return "Bot is alive ✅", 200
def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

API_ID = int(os.environ.get("API_ID", "29169428"))
API_HASH = os.environ.get("API_HASH", "55742b16a85aac494c7944568b5507e5")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7188814271:AAFdGogN_HID7Cqs__TPccM8e9OmtcGK7Yw")
REQUEST_TIMEOUT_GEMINI = int(os.environ.get("REQUEST_TIMEOUT_GEMINI", "300"))

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "250"))
MAX_UPLOAD_SIZE = MAX_UPLOAD_MB * 1024 * 1024

DEFAULT_ASSEMBLY_KEYS = "e27f99e6c34e44a4af5e0934b34b3e6f,a6d887c307044ee4a918b868a770e8ef,0272c2f92b1e4b1a96fcec55975c5c2e,b77044ed989546c9ab3a064df4a46d8c,2b7533db7ec84966871600cb64a9235,defa21f626764d71a1373437f6300d80,26293b7d8dbf43d883ce8a43d3c06f63"
DEFAULT_GEMINI_KEYS = "AIzaSyADfan-yL9WdrlVd3vzbCdJM7tXbA72dG,AIzaSyAKrnVxMMPIqSzovoUggXy5CQ_4Hi7I_NU,AIzaSyD0sYw4zzlXhbSV3HLY9wM4zCqX8ytR8zQ"

ASSEMBLYAI_API_KEYS = os.environ.get("ASSEMBLYAI_API_KEYS", DEFAULT_ASSEMBLY_KEYS)
GEMINI_API_KEYS = os.environ.get("GEMINI_API_KEYS", DEFAULT_GEMINI_KEYS)

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

assembly_keys_list = parse_keys(ASSEMBLYAI_API_KEYS)
gemini_keys_list = parse_keys(GEMINI_API_KEYS)

assembly_rotator = KeyRotator(assembly_keys_list)
gemini_rotator = KeyRotator(gemini_keys_list)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

if assembly_rotator.keys:
    aai.settings.api_key = assembly_rotator.keys[0]

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

LABELS = [label for label,code in LANGS]
LABEL_TO_CODE = {label: code for label,code in LANGS}
user_lang = {}
user_mode = {}
user_transcriptions = {}
action_usage = {}

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

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
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⭐️Clean transcript", callback_data=f"clean|{chat_id}|{message_id}"))
    if text_length > 1000:
        markup.add(types.InlineKeyboardButton("Get Summarize", callback_data=f"summarize|{chat_id}|{message_id}"))
    return markup

def download_media_file(file_id):
    file_info = bot.get_file(file_id)
    downloaded = bot.download_file(file_info.file_path)
    fname = f"{uuid.uuid4().hex}_{os.path.basename(file_info.file_path)}"
    path = os.path.join(DOWNLOADS_DIR, fname)
    with open(path, "wb") as f:
        f.write(downloaded)
    return path

def transcribe_file(file_path: str, lang_code: str = "en") -> str:
    if not assembly_rotator.keys:
        raise RuntimeError("No AssemblyAI keys available")
    last_exc = None
    for key in assembly_rotator.get_order():
        try:
            aai.settings.api_key = key
            transcriber = aai.Transcriber()
            config = aai.TranscriptionConfig(language_code=lang_code)
            transcript = transcriber.transcribe(file_path, config)
            if transcript.error:
                raise RuntimeError(transcript.error)
            assembly_rotator.mark_success(key)
            return transcript.text
        except Exception as e:
            logging.warning("AssemblyAI key failed, rotating to next key: %s", str(e))
            assembly_rotator.mark_failure(key)
            last_exc = e
            continue
    raise RuntimeError(f"All AssemblyAI keys failed. Last error: {last_exc}")

WELCOME_MESSAGE = """👋 **Salaam!**
• Send me
• **voice message**
• **audio file**
• **video**
• to transcribe for free
"""

HELP_MESSAGE = f"""/start - Show welcome message
/lang  - Change language
/mode  - Change result delivery mode
/help  - This help message

Send a voice/audio/video (up to {MAX_UPLOAD_MB}MB) and I will transcribe it Need help? Contact: @lakigithub
"""

def is_user_in_channel(user_id: int):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return getattr(member, "status", "") in ("member", "administrator", "creator", "restricted")
    except Exception:
        return False

def ensure_joined(user_id: int, reply_target_chat_id: int, reply_target_message_id: int = None):
    try:
        if is_user_in_channel(user_id):
            return True
    except Exception:
        pass
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL.strip('@')}"))
    text = f"🚫 First join the channel {REQUIRED_CHANNEL} to use this bot"
    try:
        if reply_target_message_id:
            bot.send_message(reply_target_chat_id, text, reply_markup=kb, reply_to_message_id=reply_target_message_id)
        else:
            bot.send_message(reply_target_chat_id, text, reply_markup=kb)
    except Exception:
        try:
            bot.send_message(user_id, text, reply_markup=kb)
        except Exception:
            pass
    return False

def make_lang_keyboard(origin):
    markup = types.InlineKeyboardMarkup()
    row = []
    i = 0
    for label, code in LANGS:
        row.append(types.InlineKeyboardButton(label, callback_data=f"lang|{code}|{label}|{origin}"))
        i += 1
        if i % 3 == 0:
            markup.add(*row)
            row = []
    if row:
        markup.add(*row)
    return markup

@bot.message_handler(commands=["start"])
def start(message):
    if not ensure_joined(message.from_user.id, message.chat.id, message.message_id):
        return
    markup = make_lang_keyboard("start")
    bot.send_message(message.chat.id, "**Choose your file language for transcription using the below buttons:**", reply_markup=markup)

@bot.message_handler(commands=["help"])
def help_command(message):
    if not ensure_joined(message.from_user.id, message.chat.id, message.message_id):
        return
    bot.send_message(message.chat.id, HELP_MESSAGE)

@bot.message_handler(commands=["lang"])
def lang_command(message):
    if not ensure_joined(message.from_user.id, message.chat.id, message.message_id):
        return
    markup = make_lang_keyboard("lang")
    bot.send_message(message.chat.id, "**Choose your file language for transcription using the below buttons:**", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("lang|"))
def language_callback_query(call):
    parts = call.data.split("|")
    if len(parts) < 4:
        bot.answer_callback_query(call.id, "Invalid language selection data.", show_alert=True)
        return
    _, code, label, origin = parts[:4]
    uid = call.from_user.id
    user_lang[uid] = code
    if origin == "start":
        try:
            bot.edit_message_text(WELCOME_MESSAGE, call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
    elif origin == "lang":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
    bot.answer_callback_query(call.id, f"Language set to: {label}", show_alert=False)

@bot.message_handler(commands=["mode"])
def choose_mode(message):
    if not ensure_joined(message.from_user.id, message.chat.id, message.message_id):
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💬 Split messages", callback_data="mode|Split messages"))
    markup.add(types.InlineKeyboardButton("📄 Text File", callback_data="mode|Text File"))
    bot.send_message(message.chat.id, "Choose **output mode**:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("mode|"))
def mode_callback_query(call):
    parts = call.data.split("|", 1)
    if len(parts) < 2:
        bot.answer_callback_query(call.id, "Invalid mode selection data.", show_alert=True)
        return
    _, mode_name = parts
    uid = call.from_user.id
    user_mode[uid] = mode_name
    bot.answer_callback_query(call.id, f"Mode set to: {mode_name}", show_alert=False)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass

@bot.message_handler(func=lambda m: m.content_type == "text" and m.chat.type == "private")
def handle_text(message):
    if not ensure_joined(message.from_user.id, message.chat.id, message.message_id):
        return
    uid = message.from_user.id
    text = message.text
    if text in ["💬 Split messages", "📄 Text File"]:
        user_mode[uid] = text
        bot.send_message(message.chat.id, f"Output mode set to: **{text}**")

def send_chunks_or_file(chat_id, orig_msg_id, text, mode):
    chunk_size = 4095
    sent_message_id = None
    if len(text) > chunk_size:
        if mode == "💬 Split messages":
            for part in [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]:
                bot.send_chat_action(chat_id, "typing")
                sent = bot.send_message(chat_id, part, reply_to_message_id=orig_msg_id)
                sent_message_id = sent.message_id
        else:
            fname = os.path.join(DOWNLOADS_DIR, f"Transcript_{uuid.uuid4().hex}.txt")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)
            bot.send_chat_action(chat_id, "upload_document")
            sent = bot.send_document(chat_id, open(fname, "rb"), caption="Open this file and copy the text inside 👍", reply_to_message_id=orig_msg_id)
            sent_message_id = sent.message_id
            try:
                os.remove(fname)
            except Exception:
                pass
    else:
        bot.send_chat_action(chat_id, "typing")
        sent = bot.send_message(chat_id, text, reply_to_message_id=orig_msg_id)
        sent_message_id = sent.message_id
    return sent_message_id

def process_media(message):
    if not ensure_joined(message.from_user.id, message.chat.id, message.message_id):
        return
    uid = message.from_user.id
    if uid not in user_lang:
        markup = make_lang_keyboard("start")
        bot.send_message(message.chat.id, "**Please choose your file language first:**", reply_markup=markup)
        return
    size = None
    try:
        if hasattr(message, "document") and getattr(message.document, "file_size", None):
            size = message.document.file_size
        elif hasattr(message, "audio") and getattr(message.audio, "file_size", None):
            size = message.audio.file_size
        elif hasattr(message, "video") and getattr(message.video, "file_size", None):
            size = message.video.file_size
        elif hasattr(message, "voice") and getattr(message.voice, "file_size", None):
            size = message.voice.file_size
    except Exception:
        size = None
    if size is not None and size > MAX_UPLOAD_SIZE:
        bot.send_message(message.chat.id, f"Just Send me a file less than {MAX_UPLOAD_MB}MB 😎")
        return
    lang = user_lang[uid]
    mode = user_mode.get(uid, "📄 Text File")
    bot.send_chat_action(message.chat.id, "typing")
    file_path = None
    file_id = None
    try:
        if hasattr(message, "document") and getattr(message.document, "file_id", None):
            file_id = message.document.file_id
        elif hasattr(message, "audio") and getattr(message.audio, "file_id", None):
            file_id = message.audio.file_id
        elif hasattr(message, "video") and getattr(message.video, "file_id", None):
            file_id = message.video.file_id
        elif hasattr(message, "voice") and getattr(message.voice, "file_id", None):
            file_id = message.voice.file_id
        if not file_id:
            bot.send_message(message.chat.id, "⚠️ No media file found.")
            return
        file_path = download_media_file(file_id)
    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Download error: {e}")
        return
    bot.send_chat_action(message.chat.id, "typing")
    try:
        text = transcribe_file(file_path, lang)
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Transcription error: {e}")
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
        return
    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
    if not text or str(text).startswith("Error:"):
        bot.send_message(message.chat.id, text or "⚠️ Warning Make sure the voice is clear or speaking in the language you Choosed.", reply_to_message_id=message.message_id)
        return
    reply_msg_id = message.message_id
    sent_message_id = send_chunks_or_file(message.chat.id, reply_msg_id, text, mode)
    if sent_message_id:
        try:
            keyboard = build_action_keyboard(message.chat.id, sent_message_id, len(text))
            user_transcriptions.setdefault(message.chat.id, {})[sent_message_id] = {"text": text, "origin": reply_msg_id}
            action_usage[f"{message.chat.id}|{sent_message_id}|clean"] = 0
            if len(text) > 1000:
                action_usage[f"{message.chat.id}|{sent_message_id}|summarize"] = 0
            bot.edit_message_reply_markup(message.chat.id, sent_message_id, reply_markup=keyboard)
        except Exception as e:
            logging.error(f"Failed to attach keyboard or init usage: {e}")

@bot.message_handler(content_types=['audio', 'voice', 'video', 'document'])
def handle_media(message):
    threading.Thread(target=process_media, args=(message,)).start()

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("clean|"))
def clean_up_callback(call):
    parts = call.data.split("|")
    if len(parts) < 3:
        bot.answer_callback_query(call.id, "Invalid callback data.", show_alert=True)
        return
    _, chat_id_str, msg_id_str = parts[:3]
    try:
        chat_id = int(chat_id_str)
        msg_id = int(msg_id_str)
    except Exception:
        bot.answer_callback_query(call.id, "Invalid callback data.", show_alert=True)
        return
    usage_key = f"{chat_id}|{msg_id}|clean"
    usage = action_usage.get(usage_key, 0)
    if usage >= 1:
        bot.answer_callback_query(call.id, "Clean up unavailable (maybe expired or not found).", show_alert=True)
        return
    action_usage[usage_key] = usage + 1
    stored = user_transcriptions.get(chat_id, {}).get(msg_id)
    if not stored:
        bot.answer_callback_query(call.id, "Clean up unavailable (maybe expired or not found).", show_alert=True)
        return
    stored_text = stored.get("text")
    orig_msg_id = stored.get("origin")
    bot.answer_callback_query(call.id, "Cleaning up...", show_alert=False)
    bot.send_chat_action(chat_id, "typing")
    try:
        uid = call.from_user.id
        lang = user_lang.get(uid, "en")
        mode = user_mode.get(uid, "📄 Text File")
        instruction = f"Clean and normalize this transcription (lang={lang}). Remove ASR artifacts like [inaudible], repeated words, filler noises, timestamps, and incorrect punctuation. Produce a clean, well-punctuated, readable text in the same language. Do not add introductions or explanations."
        cleaned_text = ask_gemini(stored_text, instruction)
        if not cleaned_text:
            bot.send_message(chat_id, "No cleaned text returned.", reply_to_message_id=orig_msg_id)
            return
        chunk_size = 4095
        if len(cleaned_text) > chunk_size:
            if mode == "💬 Split messages":
                for part in [cleaned_text[i:i+chunk_size] for i in range(0, len(cleaned_text), chunk_size)]:
                    bot.send_message(chat_id, part, reply_to_message_id=orig_msg_id)
            else:
                fname = os.path.join(DOWNLOADS_DIR, f"Cleaned_{uuid.uuid4().hex}.txt")
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(cleaned_text)
                bot.send_chat_action(chat_id, "upload_document")
                bot.send_document(chat_id, open(fname, "rb"), caption="Cleaned Transcript", reply_to_message_id=orig_msg_id)
                try:
                    os.remove(fname)
                except Exception:
                    pass
        else:
            bot.send_message(chat_id, cleaned_text, reply_to_message_id=orig_msg_id)
    except Exception as e:
        logging.exception("Error in clean_up_callback")
        bot.send_message(chat_id, f"❌ Error during cleanup: {e}", reply_to_message_id=orig_msg_id)

@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("summarize|"))
def get_key_points_callback(call):
    parts = call.data.split("|")
    if len(parts) < 3:
        bot.answer_callback_query(call.id, "Invalid callback data.", show_alert=True)
        return
    _, chat_id_str, msg_id_str = parts[:3]
    try:
        chat_id = int(chat_id_str)
        msg_id = int(msg_id_str)
    except Exception:
        bot.answer_callback_query(call.id, "Invalid callback data.", show_alert=True)
        return
    usage_key = f"{chat_id}|{msg_id}|summarize"
    usage = action_usage.get(usage_key, 0)
    if usage >= 1:
        bot.answer_callback_query(call.id, "Summarize unavailable (maybe expired or not found).", show_alert=True)
        return
    action_usage[usage_key] = usage + 1
    stored = user_transcriptions.get(chat_id, {}).get(msg_id)
    if not stored:
        bot.answer_callback_query(call.id, "Summarize unavailable (maybe expired or not found).", show_alert=True)
        return
    stored_text = stored.get("text")
    orig_msg_id = stored.get("origin")
    bot.answer_callback_query(call.id, "Generating summary...", show_alert=False)
    bot.send_chat_action(chat_id, "typing")
    try:
        uid = call.from_user.id
        lang = user_lang.get(uid, "en")
        mode = user_mode.get(uid, "📄 Text File")
        instruction = f"What is this report and what is it about? Please summarize them for me into (lang={lang}) without adding any introductions, notes, or extra phrases."
        summary = ask_gemini(stored_text, instruction)
        if not summary:
            bot.send_message(chat_id, "No Summary returned.", reply_to_message_id=orig_msg_id)
            return
        chunk_size = 4095
        if len(summary) > chunk_size:
            if mode == "💬 Split messages":
                for part in [summary[i:i+chunk_size] for i in range(0, len(summary), chunk_size)]:
                    bot.send_message(chat_id, part, reply_to_message_id=orig_msg_id)
            else:
                fname = os.path.join(DOWNLOADS_DIR, f"Summary_{uuid.uuid4().hex}.txt")
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(summary)
                bot.send_chat_action(chat_id, "upload_document")
                bot.send_document(chat_id, open(fname, "rb"), caption="Summary", reply_to_message_id=orig_msg_id)
                try:
                    os.remove(fname)
                except Exception:
                    pass
        else:
            bot.send_message(chat_id, summary, reply_to_message_id=orig_msg_id)
    except Exception as e:
        logging.exception("Error in get_key_points_callback")
        bot.send_message(chat_id, f"❌ Error during summary: {e}", reply_to_message_id=orig_msg_id)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling(timeout=60, long_polling_timeout=60)
