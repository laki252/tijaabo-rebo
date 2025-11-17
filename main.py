import uuid
import logging
import telebot
from flask import Flask, request, abort
from datetime import datetime
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import threading
import time
import os
import edge_tts
from edge_tts import VoicesManager
from pymongo import MongoClient
import random
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

TOKEN = "8281896922:AAEocj0Hy7nJ7jrtR5ew6772E22fsu0leCo"
WEBHOOK_URL = "https://tijaabo-rebo.onrender.com"
REQUIRED_CHANNEL = "@norshub"

DB_USER = "lakicalinuur"
DB_PASSWORD = "DjReFoWZGbwjry8K"
DB_APPNAME = "SpeechBot"
MONGO_URI = f"mongodb+srv://{DB_USER}:{DB_PASSWORD}@cluster0.n4hdlxk.mongodb.net/?retryWrites=true&w=majority&appName={DB_APPNAME}"

client = MongoClient(MONGO_URI)
db = client[DB_APPNAME]
users_collection = db.users
tts_settings_collection = db.tts_settings
logging.info("Connected to MongoDB successfully.")

bot = telebot.TeleBot(TOKEN, threaded=True)
app = Flask(__name__)

user_tts_mode = {}
user_pitch_input_mode = {}
user_rate_input_mode = {}

raw_multilingual_ids = {
    "de-DE-SeraphinaMultilingualNeural",
    "de-DE-FlorianMultilingualNeural",
    "en-AU-WilliamMultilingualNeural",
    "en-GB-AdaMultilingualNeural",
    "en-GB-OllieMultilingualNeural",
    "en-US-AvaMultilingualNeural",
    "en-US-AndrewMultilingualNeural",
    "en-US-AmandaMultilingualNeural",
    "en-US-AdamMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-PhoebeMultilingualNeural",
    "en-US-AlloyTurboMultilingualNeural",
    "en-US-EchoTurboMultilingualNeural",
    "en-US-FableTurboMultilingualNeural",
    "en-US-OnyxTurboMultilingualNeural",
    "en-US-NovaTurboMultilingualNeural",
    "en-US-ShimmerTurboMultilingualNeural",
    "en-US-BrianMultilingualNeural",
    "en-US-CoraMultilingualNeural",
    "en-US-ChristopherMultilingualNeural",
    "en-US-BrandonMultilingualNeural",
    "en-US-DavisMultilingualNeural",
    "en-US-DerekMultilingualNeural",
    "en-US-DustinMultilingualNeural",
    "en-US-JennyMultilingualNeural",
    "en-US-LewisMultilingualNeural",
    "en-US-LolaMultilingualNeural",
    "en-US-NancyMultilingualNeural",
    "en-US-RyanMultilingualNeural",
    "en-US-SamuelMultilingualNeural",
    "en-US-SerenaMultilingualNeural",
    "es-ES-ArabellaMultilingualNeural",
    "es-ES-IsidoraMultilingualNeural",
    "es-ES-TristanMultilingualNeural",
    "es-ES-XimenaMultilingualNeural",
    "es-MX-DaliaMultilingualNeural",
    "es-MX-JorgeMultilingualNeural",
    "fr-FR-VivienneMultilingualNeural",
    "fr-FR-RemyMultilingualNeural",
    "fr-FR-LucienMultilingualNeural",
    "it-IT-AlessioMultilingualNeural",
    "it-IT-IsabellaMultilingualNeural",
    "it-IT-GiuseppeMultilingualNeural",
    "it-IT-MarcelloMultilingualNeural",
    "ko-KR-HyunsuMultilingualNeural",
    "pt-BR-MacerioMultilingualNeural",
    "pt-BR-ThalitaMultilingualNeural",
    "zh-CN-XiaochenMultilingualNeural",
    "zh-CN-XiaoxiaoMultilingualNeural",
    "zh-CN-XiaoyuMultilingualNeural",
    "zh-CN-YunxiaoMultilingualNeural",
    "zh-CN-YunyiMultilingualNeural",
    "zh-CN-YunfanMultilingualNeural",
    "en-US-SteffanMultilingualNeural"
}

country_map = {
    "DE": "Germany",
    "AU": "Australia",
    "GB": "United Kingdom",
    "US": "United States",
    "ES": "Spain",
    "MX": "Mexico",
    "FR": "France",
    "IT": "Italy",
    "KR": "Korea",
    "BR": "Brazil",
    "CN": "China"
}

def short_name_from_id(vid):
    parts = vid.split("-")
    last = parts[-1]
    name = re.sub(r"(MultilingualNeural|TurboMultilingualNeural|Neural|Turbo)$", "", last)
    name = re.sub(r"([A-Z])", r"\1", name)
    return name

MULTILINGUAL_VOICES = {}
for vid in raw_multilingual_ids:
    locale = "-".join(vid.split("-")[:2])
    country_code = vid.split("-")[1] if len(vid.split("-")) >= 2 else vid.split("-")[0]
    country_name = country_map.get(country_code, country_code)
    short = short_name_from_id(vid)
    display = f"{short} - Multilingual ({country_name})"
    MULTILINGUAL_VOICES[vid] = display

VOICE_MAPPING = {
    "af-ZA-AdriNeural": "Adri - Afrikaans (South Africa)",
    "af-ZA-WillemNeural": "Willem - Afrikaans (South Africa)",
    "am-ET-AmehaNeural": "Ameha - Amharic (Ethiopia)",
    "am-ET-MekdesNeural": "Mekdes - Amharic (Ethiopia)",
    "ar-DZ-AminaNeural": "Amina - Arabic (Algeria)",
    "ar-DZ-IsmaelNeural": "Ismael - Arabic (Algeria)",
    "ar-BH-AliNeural": "Ali - Arabic (Bahrain)",
    "ar-BH-LailaNeural": "Laila - Arabic (Bahrain)",
    "ar-EG-SalmaNeural": "Salma - Arabic (Egypt)",
    "ar-EG-ShakirNeural": "Shakir - Arabic (Egypt)",
    "ar-IQ-BasselNeural": "Bassel - Arabic (Iraq)",
    "ar-IQ-RanaNeural": "Rana - Arabic (Iraq)",
    "ar-JO-SanaNeural": "Sana - Arabic (Jordan)",
    "ar-JO-TaimNeural": "Taim - Arabic (Jordan)",
    "ar-KW-FahedNeural": "Fahed - Arabic (Kuwait)",
    "ar-KW-NouraNeural": "Noura - Arabic (Kuwait)",
    "ar-LB-LaylaNeural": "Layla - Arabic (Lebanon)",
    "ar-LB-RamiNeural": "Rami - Arabic (Lebanon)",
    "ar-LY-ImanNeural": "Iman - Arabic (Libya)",
    "ar-LY-OmarNeural": "Omar - Arabic (Libya)",
    "ar-MA-JamalNeural": "Jamal - Arabic (Morocco)",
    "ar-MA-MounaNeural": "Mouna - Arabic (Morocco)",
    "ar-OM-AbdullahNeural": "Abdullah - Arabic (Oman)",
    "ar-OM-AyshaNeural": "Aysha - Arabic (Oman)",
    "ar-QA-AmalNeural": "Amal - Arabic (Qatar)",
    "ar-QA-MoazNeural": "Moaz - Arabic (Qatar)",
    "ar-SA-HamedNeural": "Hamed - Arabic (Saudi Arabia)",
    "ar-SA-ZariyahNeural": "Zariyah - Arabic (Saudi Arabia)",
    "ar-SY-AmanyNeural": "Amany - Arabic (Syria)",
    "ar-SY-LaithNeural": "Laith - Arabic (Syria)",
    "ar-TN-HediNeural": "Hedi - Arabic (Tunisia)",
    "ar-TN-ReemNeural": "Reem - Arabic (Tunisia)",
    "ar-AE-FatimaNeural": "Fatima - Arabic (UAE)",
    "ar-AE-HamdanNeural": "Hamdan - Arabic (UAE)",
    "ar-YE-MaryamNeural": "Maryam - Arabic (Yemen)",
    "ar-YE-SalehNeural": "Saleh - Arabic (Yemen)",
    "as-IN-PriyomNeural": "Priyom - Assamese (India)",
    "as-IN-YashicaNeural": "Yashica - Assamese (India)",
    "az-AZ-BabekNeural": "Babek - Azerbaijani (Azerbaijan)",
    "az-AZ-BanuNeural": "Banu - Azerbaijani (Azerbaijan)",
    "bg-BG-BorislavNeural": "Borislav - Bulgarian (Bulgaria)",
    "bg-BG-KalinaNeural": "Kalina - Bulgarian (Bulgaria)",
    "bn-BD-NabanitaNeural": "Nabanita - Bengali (Bangladesh)",
    "bn-BD-PradeepNeural": "Pradeep - Bengali (Bangladesh)",
    "bn-IN-BashkarNeural": "Bashkar - Bengali (India)",
    "bn-IN-TanishaaNeural": "Tanishaa - Bengali (India)",
    "bs-BA-VesnaNeural": "Vesna - Bosnian (Bosnia and Herzegovina)",
    "bs-BA-GoranNeural": "Goran - Bosnian (Bosnia and Herzegovina)",
    "ca-ES-AlbaNeural": "Alba - Catalan (Spain)",
    "ca-ES-EnricNeural": "Enric - Catalan (Spain)",
    "ca-ES-JoanaNeural": "Joana - Catalan (Spain)",
    "cs-CZ-AntoninNeural": "Antonin - Czech (Czech Republic)",
    "cs-CZ-VlastaNeural": "Vlasta - Czech (Czech Republic)",
    "cy-GB-AledNeural": "Aled - Welsh (United Kingdom)",
    "cy-GB-NiaNeural": "Nia - Welsh (United Kingdom)",
    "da-DK-ChristelNeural": "Christel - Danish (Denmark)",
    "da-DK-JeppeNeural": "Jeppe - Danish (Denmark)",
    "de-AT-IngridNeural": "Ingrid - German (Austria)",
    "de-AT-JonasNeural": "Jonas - German (Austria)",
    "de-DE-AmalaNeural": "Amala - German (Germany)",
    "de-DE-ConradNeural": "Conrad - German (Germany)",
    "de-DE-KatjaNeural": "Katja - German (Germany)",
    "de-DE-KillianNeural": "Killian - German (Germany)",
    "de-DE-BerndNeural": "Bernd - German (Germany)",
    "de-DE-ChristophNeural": "Christoph - German (Germany)",
    "de-DE-ElkeNeural": "Elke - German (Germany)",
    "de-DE-GiselaNeural": "Gisela - German (Germany)",
    "de-DE-KasperNeural": "Kasper - German (Germany)",
    "de-DE-KlarissaNeural": "Klarissa - German (Germany)",
    "de-DE-KlausNeural": "Klaus - German (Germany)",
    "de-DE-LouisaNeural": "Louisa - German (Germany)",
    "de-DE-MajaNeural": "Maja - German (Germany)",
    "de-DE-RalfNeural": "Ralf - German (Germany)",
    "de-DE-TanjaNeural": "Tanja - German (Germany)",
    "de-CH-JanNeural": "Jan - German (Switzerland)",
    "de-CH-LeniNeural": "Leni - German (Switzerland)",
    "el-GR-AthinaNeural": "Athina - Greek (Greece)",
    "el-GR-NestorasNeural": "Nestoras - Greek (Greece)",
    "en-AU-AnnetteNeural": "Annette - English (Australia)",
    "en-AU-CarlyNeural": "Carly - English (Australia)",
    "en-AU-DarrenNeural": "Darren - English (Australia)",
    "en-AU-DuncanNeural": "Duncan - English (Australia)",
    "en-AU-ElsieNeural": "Elsie - English (Australia)",
    "en-AU-FreyaNeural": "Freya - English (Australia)",
    "en-AU-JoanneNeural": "Joanne - English (Australia)",
    "en-AU-KenNeural": "Ken - English (Australia)",
    "en-AU-KimNeural": "Kim - English (Australia)",
    "en-AU-NeilNeural": "Neil - English (Australia)",
    "en-AU-NatashaNeural": "Natasha - English (Australia)",
    "en-AU-TimNeural": "Tim - English (Australia)",
    "en-AU-TinaNeural": "Tina - English (Australia)",
    "en-AU-WilliamNeural": "William - English (Australia)",
    "en-CA-ClaraNeural": "Clara - English (Canada)",
    "en-CA-LiamNeural": "Liam - English (Canada)",
    "en-HK-YanNeural": "Yan - English (Hong Kong)",
    "en-HK-SamNeural": "Sam - English (Hong Kong)",
    "en-IN-AaravNeural": "Aarav - English (India)",
    "en-IN-AartiIndicNeural": "AartiIndic - English (India)",
    "en-IN-AartiNeural": "Aarti - English (India)",
    "en-IN-AashiNeural": "Aashi - English (India)",
    "en-IN-AnanyaNeural": "Ananya - English (India)",
    "en-IN-ArjunIndicNeural": "ArjunIndic - English (India)",
    "en-IN-ArjunNeural": "Arjun - English (India)",
    "en-IN-KavyaNeural": "Kavya - English (India)",
    "en-IN-KunalNeural": "Kunal - English (India)",
    "en-IN-NeerjaExpressiveNeural": "Neerja - English (India) - Expressive",
    "en-IN-NeerjaIndicNeural": "NeerjaIndic - English (India)",
    "en-IN-NeerjaNeural": "Neerja - English (India)",
    "en-IN-PrabhatIndicNeural": "PrabhatIndic - English (India)",
    "en-IN-PrabhatNeural": "Prabhat - English (India)",
    "en-IN-RehaanNeural": "Rehaan - English (India)",
    "en-IE-ConnorNeural": "Connor - English (Ireland)",
    "en-IE-EmilyNeural": "Emily - English (Ireland)",
    "en-KE-AsiliaNeural": "Asilia - English (Kenya)",
    "en-KE-ChilembaNeural": "Chilemba - English (Kenya)",
    "en-NZ-MitchellNeural": "Mitchell - English (New Zealand)",
    "en-NZ-MollyNeural": "Molly - English (New Zealand)",
    "en-NG-AbeoNeural": "Abeo - English (Nigeria)",
    "en-NG-EzinneNeural": "Ezinne - English (Nigeria)",
    "en-PH-JamesNeural": "James - English (Philippines)",
    "en-PH-RosaNeural": "Rosa - English (Philippines)",
    "en-SG-LunaNeural": "Luna - English (Singapore)",
    "en-SG-WayneNeural": "Wayne - English (Singapore)",
    "en-ZA-LeahNeural": "Leah - English (South Africa)",
    "en-ZA-LukeNeural": "Luke - English (South Africa)",
    "en-TZ-ElimuNeural": "Elimu - English (Tanzania)",
    "en-TZ-ImaniNeural": "Imani - English (Tanzania)",
    "en-GB-AbbiNeural": "Abbi - English (United Kingdom)",
    "en-GB-AlfieNeural": "Alfie - English (United Kingdom)",
    "en-GB-BellaNeural": "Bella - English (United Kingdom)",
    "en-GB-ElliotNeural": "Elliot - English (United Kingdom)",
    "en-GB-EthanNeural": "Ethan - English (United Kingdom)",
    "en-GB-HollieNeural": "Hollie - English (United Kingdom)",
    "en-GB-LibbyNeural": "Libby - English (United Kingdom)",
    "en-GB-MaisieNeural": "Maisie - English (United Kingdom)",
    "en-GB-MiaNeural": "Mia - English (United Kingdom)",
    "en-GB-NoahNeural": "Noah - English (United Kingdom)",
    "en-GB-OliverNeural": "Oliver - English (United Kingdom)",
    "en-GB-OliviaNeural": "Olivia - English (United Kingdom)",
    "en-GB-RyanNeural": "Ryan - English (United Kingdom)",
    "en-GB-SoniaNeural": "Sonia - English (United Kingdom)",
    "en-GB-ThomasNeural": "Thomas - English (United Kingdom)",
    "en-US-AmberNeural": "Amber - English (United States)",
    "en-US-AnaNeural": "Ana - English (United States)",
    "en-US-AndrewNeural": "Andrew - English (United States)",
    "en-US-AriaNeural": "Aria - English (United States)",
    "en-US-AshleyNeural": "Ashley - English (United States)",
    "en-US-AvaNeural": "Ava - English (United States)",
    "en-US-BrandonNeural": "Brandon - English (United States)",
    "en-US-BrianNeural": "Brian - English (United States)",
    "en-US-ChristopherNeural": "Christopher - English (United States)",
    "en-US-CoraNeural": "Cora - English (United States)",
    "en-US-DavisNeural": "Davis - English (United States)",
    "en-US-ElizabethNeural": "Elizabeth - English (United States)",
    "en-US-EmmaNeural": "Emma - English (United States)",
    "en-US-EricNeural": "Eric - English (United States)",
    "en-US-GuyNeural": "Guy - English (United States)",
    "en-US-JacobNeural": "Jacob - English (United States)",
    "en-US-JaneNeural": "Jane - English (United States)",
    "en-US-JasonNeural": "Jason - English (United States)",
    "en-US-JennyNeural": "Jenny - English (United States)",
    "en-US-KaiNeural": "Kai - English (United States)",
    "en-US-LunaNeural": "Luna - English (United States)",
    "en-US-MichelleNeural": "Michelle - English (United States)",
    "en-US-MonicaNeural": "Monica - English (United States)",
    "en-US-NancyNeural": "Nancy - English (United States)",
    "en-US-RogerNeural": "Roger - English (United States)",
    "en-US-SaraNeural": "Sara - English (United States)",
    "en-US-SteffanMultilingualNeural": "Steffan - English (United States) - Multilingual",
    "en-US-SteffanNeural": "Steffan - English (United States)",
    "en-US-TonyNeural": "Tony - English (United States)",
    "es-AR-ElenaNeural": "Elena - Spanish (Argentina)",
    "es-AR-TomasNeural": "Tomas - Spanish (Argentina)",
    "es-BO-MarceloNeural": "Marcelo - Spanish (Bolivia)",
    "es-BO-SofiaNeural": "Sofia - Spanish (Bolivia)",
    "es-CL-CatalinaNeural": "Catalina - Spanish (Chile)",
    "es-CL-LorenzoNeural": "Lorenzo - Spanish (Chile)",
    "es-CO-GonzaloNeural": "Gonzalo - Spanish (Colombia)",
    "es-CO-SalomeNeural": "Salome - Spanish (Colombia)",
    "es-ES-AbrilNeural": "Abril - Spanish (Spain)",
    "es-ES-AlvaroNeural": "Alvaro - Spanish (Spain)",
    "es-ES-ArnauNeural": "Arnau - Spanish (Spain)",
    "es-ES-DarioNeural": "Dario - Spanish (Spain)",
    "es-ES-EliasNeural": "Elias - Spanish (Spain)",
    "es-ES-ElviraNeural": "Elvira - Spanish (Spain)",
    "es-ES-EstrellaNeural": "Estrella - Spanish (Spain)",
    "es-ES-IreneNeural": "Irene - Spanish (Spain)",
    "es-ES-LaiaNeural": "Laia - Spanish (Spain)",
    "es-ES-LiaNeural": "Lia - Spanish (Spain)",
    "es-ES-NilNeural": "Nil - Spanish (Spain)",
    "es-ES-SaulNeural": "Saul - Spanish (Spain)",
    "es-ES-TeoNeural": "Teo - Spanish (Spain)",
    "es-ES-TrianaNeural": "Triana - Spanish (Spain)",
    "es-ES-VeraNeural": "Vera - Spanish (Spain)",
    "es-ES-XimenaNeural": "Ximena - Spanish (Spain)",
    "es-CR-JuanNeural": "Juan - Spanish (Costa Rica)",
    "es-CR-MariaNeural": "Maria - Spanish (Costa Rica)",
    "es-CU-BelkysNeural": "Belkys - Spanish (Cuba)",
    "es-CU-ManuelNeural": "Manuel - Spanish (Cuba)",
    "es-DO-EmilioNeural": "Emilio - Spanish (Dominican Republic)",
    "es-DO-RamonaNeural": "Ramona - Spanish (Dominican Republic)",
    "es-EC-AndreaNeural": "Andrea - Spanish (Ecuador)",
    "es-EC-LuisNeural": "Luis - Spanish (Ecuador)",
    "es-SV-LorenaNeural": "Lorena - Spanish (El Salvador)",
    "es-SV-RodrigoNeural": "Rodrigo - Spanish (El Salvador)",
    "es-GQ-JavierNeural": "Javier - Spanish (Equatorial Guinea)",
    "es-GQ-TeresaNeural": "Teresa - Spanish (Equatorial Guinea)",
    "es-GT-AndresNeural": "Andres - Spanish (Guatemala)",
    "es-GT-MartaNeural": "Marta - Spanish (Guatemala)",
    "es-HN-CarlosNeural": "Carlos - Spanish (Honduras)",
    "es-HN-KarlaNeural": "Karla - Spanish (Honduras)",
    "es-MX-BeatrizNeural": "Beatriz - Spanish (Mexico)",
    "es-MX-CandelaNeural": "Candela - Spanish (Mexico)",
    "es-MX-CarlotaNeural": "Carlota - Spanish (Mexico)",
    "es-MX-CecilioNeural": "Cecilio - Spanish (Mexico)",
    "es-MX-DaliaNeural": "Dalia - Spanish (Mexico)",
    "es-MX-GerardoNeural": "Gerardo - Spanish (Mexico)",
    "es-MX-JorgeNeural": "Jorge - Spanish (Mexico)",
    "es-MX-LarissaNeural": "Larissa - Spanish (Mexico)",
    "es-MX-LibertoNeural": "Liberto - Spanish (Mexico)",
    "es-MX-LucianoNeural": "Luciano - Spanish (Mexico)",
    "es-MX-MarinaNeural": "Marina - Spanish (Mexico)",
    "es-MX-NuriaNeural": "Nuria - Spanish (Mexico)",
    "es-MX-PelayoNeural": "Pelayo - Spanish (Mexico)",
    "es-MX-RenataNeural": "Renata - Spanish (Mexico)",
    "es-MX-YagoNeural": "Yago - Spanish (Mexico)",
    "es-NI-FedericoNeural": "Federico - Spanish (Nicaragua)",
    "es-NI-YolandaNeural": "Yolanda - Spanish (Nicaragua)",
    "es-PA-MargaritaNeural": "Margarita - Spanish (Panama)",
    "es-PA-RobertoNeural": "Roberto - Spanish (Panama)",
    "es-PY-MarioNeural": "Mario - Spanish (Paraguay)",
    "es-PY-TaniaNeural": "Tania - Spanish (Paraguay)",
    "es-PE-AlexNeural": "Alex - Spanish (Peru)",
    "es-PE-CamilaNeural": "Camila - Spanish (Peru)",
    "es-PR-KarinaNeural": "Karina - Spanish (Puerto Rico)",
    "es-PR-VictorNeural": "Victor - Spanish (Puerto Rico)",
    "es-US-AlonsoNeural": "Alonso - Spanish (United States)",
    "es-US-PalomaNeural": "Paloma - Spanish (United States)",
    "es-UY-MateoNeural": "Mateo - Spanish (Uruguay)",
    "es-UY-ValentinaNeural": "Valentina - Spanish (Uruguay)",
    "es-VE-PaolaNeural": "Paola - Spanish (Venezuela)",
    "es-VE-SebastianNeural": "Sebastian - Spanish (Venezuela)",
    "et-EE-AnuNeural": "Anu - Estonian (Estonia)",
    "et-EE-KertNeural": "Kert - Estonian (Estonia)",
    "eu-ES-AinhoaNeural": "Ainhoa - Basque (Spain)",
    "eu-ES-AnderNeural": "Ander - Basque (Spain)",
    "fa-IR-DilaraNeural": "Dilara - Persian (Iran)",
    "fa-IR-FaridNeural": "Farid - Persian (Iran)",
    "fi-FI-HarriNeural": "Harri - Finnish (Finland)",
    "fi-FI-NooraNeural": "Noora - Finnish (Finland)",
    "fi-FI-SelmaNeural": "Selma - Finnish (Finland)",
    "fil-PH-AngeloNeural": "Angelo - Filipino (Philippines)",
    "fil-PH-BlessicaNeural": "Blessica - Filipino (Philippines)",
    "fr-BE-CharlineNeural": "Charline - French (Belgium)",
    "fr-BE-GerardNeural": "Gerard - French (Belgium)",
    "fr-CA-ThierryNeural": "Thierry - French (Canada)",
    "fr-CA-AntoineNeural": "Antoine - French (Canada)",
    "fr-CA-JeanNeural": "Jean - French (Canada)",
    "fr-CA-SylvieNeural": "Sylvie - French (Canada)",
    "fr-FR-AlainNeural": "Alain - French (France)",
    "fr-FR-BrigitteNeural": "Brigitte - French (France)",
    "fr-FR-CelesteNeural": "Celeste - French (France)",
    "fr-FR-ClaudeNeural": "Claude - French (France)",
    "fr-FR-CoralieNeural": "Coralie - French (France)",
    "fr-FR-DeniseNeural": "Denise - French (France)",
    "fr-FR-EloiseNeural": "Eloise - French (France)",
    "fr-FR-HenriNeural": "Henri - French (France)",
    "fr-FR-JacquelineNeural": "Jacqueline - French (France)",
    "fr-FR-JeromeNeural": "Jerome - French (France)",
    "fr-FR-JosephineNeural": "Josephine - French (France)",
    "fr-FR-MauriceNeural": "Maurice - French (France)",
    "fr-FR-YvesNeural": "Yves - French (France)",
    "fr-FR-YvetteNeural": "Yvette - French (France)",
    "fr-CH-ArianeNeural": "Ariane - French (Switzerland)",
    "fr-CH-FabriceNeural": "Fabrice - French (Switzerland)",
    "ga-IE-ColmNeural": "Colm - Irish (Ireland)",
    "ga-IE-OrlaNeural": "Orla - Irish (Ireland)",
    "gl-ES-RoiNeural": "Roi - Galician (Spain)",
    "gl-ES-SabelaNeural": "Sabela - Galician (Spain)",
    "gu-IN-DhwaniNeural": "Dhwani - Gujarati (India)",
    "gu-IN-NiranjanNeural": "Niranjan - Gujarati (India)",
    "he-IL-AvriNeural": "Avri - Hebrew (Israel)",
    "he-IL-HilaNeural": "Hila - Hebrew (Israel)",
    "hi-IN-AaravNeural": "Aarav - Hindi (India)",
    "hi-IN-AartiNeural": "Aarti - Hindi (India)",
    "hi-IN-AashiNeural": "Aashi - Hindi (India)",
    "hi-IN-AnanyaNeural": "Ananya - Hindi (India)",
    "hi-IN-ArjunNeural": "Arjun - Hindi (India)",
    "hi-IN-KavyaNeural": "Kavya - Hindi (India)",
    "hi-IN-KunalNeural": "Kunal - Hindi (India)",
    "hi-IN-MadhurNeural": "Madhur - Hindi (India)",
    "hi-IN-RehaanNeural": "Rehaan - Hindi (India)",
    "hi-IN-SwaraNeural": "Swara - Hindi (India)",
    "hr-HR-GabrijelaNeural": "Gabrijela - Croatian (Croatia)",
    "hr-HR-SreckoNeural": "Srecko - Croatian (Croatia)",
    "hu-HU-NoemiNeural": "Noemi - Hungarian (Hungary)",
    "hu-HU-TamasNeural": "Tamas - Hungarian (Hungary)",
    "id-ID-ArdiNeural": "Ardi - Indonesian (Indonesia)",
    "id-ID-GadisNeural": "Gadis - Indonesian (Indonesia)",
    "is-IS-GudrunNeural": "Gudrun - Icelandic (Iceland)",
    "is-IS-GunnarNeural": "Gunnar - Icelandic (Iceland)",
    "it-IT-BenignoNeural": "Benigno - Italian (Italy)",
    "it-IT-CalimeroNeural": "Calimero - Italian (Italy)",
    "it-IT-CataldoNeural": "Cataldo - Italian (Italy)",
    "it-IT-CosimoNeural": "Cosimo - Italian (Italy)",
    "it-IT-DiegoNeural": "Diego - Italian (Italy)",
    "it-IT-ElsaNeural": "Elsa - Italian (Italy)",
    "it-IT-FabiolaNeural": "Fabiola - Italian (Italy)",
    "it-IT-ImeldaNeural": "Imelda - Italian (Italy)",
    "it-IT-IrmaNeural": "Irma - Italian (Italy)",
    "it-IT-IsabellaNeural": "Isabella - Italian (Italy)",
    "it-IT-LisandroNeural": "Lisandro - Italian (Italy)",
    "it-IT-MarcelloNeural": "Marcello - Italian (Italy)",
    "it-IT-PierinaNeural": "Pierina - Italian (Italy)",
    "it-IT-RiccardoNeural": "Riccardo - Italian (Italy)",
    "it-IT-SilvanoNeural": "Silvano - Italian (Italy)",
    "iu-Latn-CA-SiqiniqNeural": "Siqiniq - Inuktitut (Canada) - Latin",
    "iu-Latn-CA-TaqqiqNeural": "Taqqiq - Inuktitut (Canada) - Latin",
    "iu-Cans-CA-SiqiniqNeural": "Siqiniq - Inuktitut (Canada) - Syllabics",
    "iu-Cans-CA-TaqqiqNeural": "Taqqiq - Inuktitut (Canada) - Syllabics",
    "ja-JP-KeitaNeural": "Keita - Japanese (Japan)",
    "ja-JP-MasaruNeural": "Masaru - Japanese (Japan)",
    "ja-JP-MayuNeural": "Mayu - Japanese (Japan)",
    "ja-JP-NanamiNeural": "Nanami - Japanese (Japan)",
    "ja-JP-RisaNeural": "Risa - Japanese (Japan)",
    "ja-JP-ShioriNeural": "Shiori - Japanese (Japan)",
    "jv-ID-DimasNeural": "Dimas - Javanese (Indonesia)",
    "jv-ID-SitiNeural": "Siti - Javanese (Indonesia)",
    "ka-GE-EkaNeural": "Eka - Georgian (Georgia)",
    "ka-GE-GiorgiNeural": "Giorgi - Georgian (Georgia)",
    "kk-KZ-AigulNeural": "Aigul - Kazakh (Kazakhstan)",
    "kk-KZ-DauletNeural": "Daulet - Kazakh (Kazakhstan)",
    "km-KH-PisethNeural": "Piseth - Khmer (Cambodia)",
    "km-KH-SreymomNeural": "Sreymom - Khmer (Cambodia)",
    "kn-IN-GaganNeural": "Gagan - Kannada (India)",
    "kn-IN-SapnaNeural": "Sapna - Kannada (India)",
    "ko-KR-BongJinNeural": "BongJin - Korean (Korea)",
    "ko-KR-GookMinNeural": "GookMin - Korean (Korea)",
    "ko-KR-InJoonNeural": "InJoon - Korean (Korea)",
    "ko-KR-JiMinNeural": "JiMin - Korean (Korea)",
    "ko-KR-SeungHwanNeural": "SeungHwan - Korean (Korea)",
    "ko-KR-SunHiNeural": "SunHi - Korean (Korea)",
    "lo-LA-ChanthavongNeural": "Chanthavong - Lao (Laos)",
    "lo-LA-KeomanyNeural": "Keomany - Lao (Laos)",
    "lt-LT-LeonaNeural": "Leona - Lithuanian (Lithuania)",
    "lt-LT-LeonasNeural": "Leonas - Lithuanian (Lithuania)",
    "lt-LT-OnaNeural": "Ona - Lithuanian (Lithuania)",
    "lv-LV-EveritaNeural": "Everita - Latvian (Latvia)",
    "lv-LV-NilsNeural": "Nils - Latvian (Latvia)",
    "mk-MK-AleksandarNeural": "Aleksandar - Macedonian (North Macedonia)",
    "mk-MK-MarijaNeural": "Marija - Macedonian (North Macedonia)",
    "ml-IN-MidhunNeural": "Midhun - Malayalam (India)",
    "ml-IN-SobhanaNeural": "Sobhana - Malayalam (India)",
    "mn-MN-BataaNeural": "Bataa - Mongolian (Mongolia)",
    "mn-MN-YesuiNeural": "Yesui - Mongolian (Mongolia)",
    "mr-IN-AarohiNeural": "Aarohi - Marathi (India)",
    "mr-IN-ManoharNeural": "Manohar - Marathi (India)",
    "ms-MY-OsmanNeural": "Osman - Malay (Malaysia)",
    "ms-MY-YasminNeural": "Yasmin - Malay (Malaysia)",
    "mt-MT-GraceNeural": "Grace - Maltese (Malta)",
    "mt-MT-JosephNeural": "Joseph - Maltese (Malta)",
    "my-MM-NilarNeural": "Nilar - Burmese (Myanmar)",
    "my-MM-ThihaNeural": "Thiha - Burmese (Myanmar)",
    "nb-NO-FinnNeural": "Finn - Norwegian Bokmål (Norway)",
    "nb-NO-PernilleNeural": "Pernille - Norwegian Bokmål (Norway)",
    "ne-NP-HemkalaNeural": "Hemkala - Nepali (Nepal)",
    "ne-NP-SagarNeural": "Sagar - Nepali (Nepal)",
    "nl-BE-ArnaudNeural": "Arnaud - Dutch (Belgium)",
    "nl-BE-DenaNeural": "Dena - Dutch (Belgium)",
    "nl-NL-ColetteNeural": "Colette - Dutch (Netherlands)",
    "nl-NL-FennaNeural": "Fenna - Dutch (Netherlands)",
    "nl-NL-MaartenNeural": "Maarten - Dutch (Netherlands)",
    "pl-PL-AgnieszkaNeural": "Agnieszka - Polish (Poland)",
    "pl-PL-MarekNeural": "Marek - Polish (Poland)",
    "pl-PL-ZofiaNeural": "Zofia - Polish (Poland)",
    "ps-AF-GulNawazNeural": "Gul Nawaz - Pashto (Afghanistan)",
    "ps-AF-LatifaNeural": "Latifa - Pashto (Afghanistan)",
    "pt-BR-AntonioNeural": "Antonio - Portuguese (Brazil)",
    "pt-BR-BrendaNeural": "Brenda - Portuguese (Brazil)",
    "pt-BR-FabioNeural": "Fabio - Portuguese (Brazil)",
    "pt-BR-FranciscaNeural": "Francisca - Portuguese (Brazil)",
    "pt-BR-ThalitaNeural": "Thalita - Portuguese (Brazil)",
    "pt-PT-DuarteNeural": "Duarte - Portuguese (Portugal)",
    "pt-PT-RaquelNeural": "Raquel - Portuguese (Portugal)",
    "ro-RO-AlinaNeural": "Alina - Romanian (Romania)",
    "ro-RO-EmilNeural": "Emil - Romanian (Romania)",
    "ru-RU-DmitryNeural": "Dmitry - Russian (Russia)",
    "ru-RU-SvetlanaNeural": "Svetlana - Russian (Russia)",
    "si-LK-SameeraNeural": "Sameera - Sinhala (Sri Lanka)",
    "si-LK-ThiliniNeural": "Thilini - Sinhala (Sri Lanka)",
    "sk-SK-LukasNeural": "Lukas - Slovak (Slovakia)",
    "sk-SK-ViktoriaNeural": "Viktoria - Slovak (Slovakia)",
    "sl-SI-PetraNeural": "Petra - Slovenian (Slovenia)",
    "sl-SI-RokNeural": "Rok - Slovenian (Slovenia)",
    "so-SO-MuuseNeural": "Muuse - Somali (Somalia)",
    "so-SO-UbaxNeural": "Ubax - Somali (Somalia)",
    "sq-AL-AnilaNeural": "Anila - Albanian (Albania)",
    "sq-AL-IlirNeural": "Ilir - Albanian (Albania)",
    "sr-RS-NicholasNeural": "Nicholas - Serbian (Serbia)",
    "sr-RS-SophieNeural": "Sophie - Serbian (Serbia)",
    "su-ID-JajangNeural": "Jajang - Sundanese (Indonesia)",
    "su-ID-TutiNeural": "Tuti - Sundanese (Indonesia)",
    "sv-SE-MattiasNeural": "Mattias - Swedish (Sweden)",
    "sv-SE-SofieNeural": "Sofie - Swedish (Sweden)",
    "sw-KE-RafikiNeural": "Rafiki - Swahili (Kenya)",
    "sw-KE-ZuriNeural": "Zuri - Swahili (Kenya)",
    "sw-TZ-DaudiNeural": "Daudi - Swahili (Tanzania)",
    "sw-TZ-RehemaNeural": "Rehema - Swahili (Tanzania)",
    "ta-IN-PallaviNeural": "Pallavi - Tamil (India)",
    "ta-IN-ValluvarNeural": "Valluvar - Tamil (India)",
    "ta-MY-KaniNeural": "Kani - Tamil (Malaysia)",
    "ta-MY-SuryaNeural": "Surya - Tamil (Malaysia)",
    "ta-SG-AnbuNeural": "Anbu - Tamil (Singapore)",
    "ta-SG-VenbaNeural": "Venba - Tamil (Singapore)",
    "ta-LK-KumarNeural": "Kumar - Tamil (Sri Lanka)",
    "ta-LK-SaranyaNeural": "Saranya - Tamil (Sri Lanka)",
    "te-IN-MohanNeural": "Mohan - Telugu (India)",
    "te-IN-ShrutiNeural": "Shruti - Telugu (India)",
    "th-TH-NiwatNeural": "Niwat - Thai (Thailand)",
    "th-TH-PremwadeeNeural": "Premwadee - Thai (Thailand)",
    "tr-TR-AhmetNeural": "Ahmet - Turkish (Turkey)",
    "tr-TR-EmelNeural": "Emel - Turkish (Turkey)",
    "uk-UA-OstapNeural": "Ostap - Ukrainian (Ukraine)",
    "uk-UA-PolinaNeural": "Polina - Ukrainian (Ukraine)",
    "ur-IN-GulNeural": "Gul - Urdu (India)",
    "ur-IN-SalmanNeural": "Salman - Urdu (India)",
    "ur-PK-AsadNeural": "Asad - Urdu (Pakistan)",
    "ur-PK-UzmaNeural": "Uzma - Urdu (Pakistan)",
    "uz-UZ-MadinaNeural": "Madina - Uzbek (Uzbekistan)",
    "uz-UZ-SardorNeural": "Sardor - Uzbek (Uzbekistan)",
    "vi-VN-HoaiMyNeural": "HoaiMy - Vietnamese (Vietnam)",
    "vi-VN-NamMinhNeural": "NamMinh - Vietnamese (Vietnam)",
    "zh-CN-XiaochenNeural": "Xiaochen - Chinese (Mandarin, Simplified)",
    "zh-CN-XiaoxiaoNeural": "Xiaoxiao - Chinese (Mandarin, Simplified)",
    "zh-CN-XiaoyiNeural": "Xiaoyi - Chinese (Mandarin, Simplified)",
    "zh-CN-XiaoyuNeural": "Xiaoyu - Chinese (Mandarin, Simplified)",
    "zh-CN-YunjianNeural": "Yunjian - Chinese (Mandarin, Simplified)",
    "zh-CN-YunxiNeural": "Yunxi - Chinese (Mandarin, Simplified)",
    "zh-CN-YunxiaNeural": "Yunxia - Chinese (Mandarin, Simplified)",
    "zh-CN-YunyangNeural": "Yunyang - Chinese (Mandarin, Simplified)",
    "zh-CN-liaoning-XiaobeiNeural": "Xiaobei - Chinese (Northeastern Mandarin, Simplified)",
    "zh-HK-HiuGaaiNeural": "Hiu Gaai - Chinese (Cantonese, Hong Kong)",
    "zh-HK-HiuMaanNeural": "Hiu Maan - Chinese (Cantonese, Hong Kong)",
    "zh-HK-WanLungNeural": "Wan Lung - Chinese (Cantonese, Hong Kong)",
    "zh-TW-HsiaoChenNeural": "HsiaoChen - Chinese (Taiwanese Mandarin)",
    "zh-TW-HsiaoYuNeural": "HsiaoYu - Chinese (Taiwanese Mandarin)",
    "zh-TW-YunJheNeural": "YunJhe - Chinese (Taiwanese Mandarin)",
    "zh-CN-shaanxi-XiaoniNeural": "Xiaoni - Chinese (Shaanxi Mandarin, Simplified)",
    "zu-ZA-ThandoNeural": "Thando - Zulu (South Africa)",
    "zu-ZA-ThembaNeural": "Themba - Zulu (South Africa)"
}

for k, v in MULTILINGUAL_VOICES.items():
    VOICE_MAPPING[k] = v

TTS_VOICES_BY_LANGUAGE = {
    "Afrikaans": ["af-ZA-AdriNeural", "af-ZA-WillemNeural"],
    "Amharic": ["am-ET-AmehaNeural", "am-ET-MekdesNeural"],
    "Arabic": ["ar-DZ-AminaNeural", "ar-DZ-IsmaelNeural", "ar-BH-AliNeural", "ar-BH-LailaNeural", "ar-EG-SalmaNeural", "ar-EG-ShakirNeural", "ar-IQ-BasselNeural", "ar-IQ-RanaNeural", "ar-JO-SanaNeural", "ar-JO-TaimNeural", "ar-KW-FahedNeural", "ar-KW-NouraNeural", "ar-LB-LaylaNeural", "ar-LB-RamiNeural", "ar-LY-ImanNeural", "ar-LY-OmarNeural", "ar-MA-JamalNeural", "ar-MA-MounaNeural", "ar-OM-AbdullahNeural", "ar-OM-AyshaNeural", "ar-QA-AmalNeural", "ar-QA-MoazNeural", "ar-SA-HamedNeural", "ar-SA-ZariyahNeural", "ar-SY-AmanyNeural", "ar-SY-LaithNeural", "ar-TN-HediNeural", "ar-TN-ReemNeural", "ar-AE-FatimaNeural", "ar-AE-HamdanNeural", "ar-AE-HamdanNeural", "ar-YE-MaryamNeural", "ar-YE-SalehNeural"],
    "Assamese": ["as-IN-PriyomNeural", "as-IN-YashicaNeural"],
    "Azerbaijani": ["az-AZ-BabekNeural", "az-AZ-BanuNeural"],
    "Bulgarian": ["bg-BG-BorislavNeural", "bg-BG-KalinaNeural"],
    "Bengali": ["bn-BD-NabanitaNeural", "bn-BD-PradeepNeural", "bn-IN-BashkarNeural", "bn-IN-TanishaaNeural"],
    "Bosnian": ["bs-BA-VesnaNeural", "bs-BA-GoranNeural"],
    "Catalan": ["ca-ES-AlbaNeural", "ca-ES-EnricNeural", "ca-ES-JoanaNeural"],
    "Czech": ["cs-CZ-AntoninNeural", "cs-CZ-VlastaNeural"],
    "Welsh": ["cy-GB-AledNeural", "cy-GB-NiaNeural"],
    "Danish": ["da-DK-ChristelNeural", "da-DK-JeppeNeural"],
    "German": ["de-AT-IngridNeural", "de-AT-JonasNeural", "de-DE-AmalaNeural", "de-DE-ConradNeural", "de-DE-KatjaNeural", "de-DE-KillianNeural", "de-CH-JanNeural", "de-CH-LeniNeural", "de-DE-BerndNeural", "de-DE-ChristophNeural", "de-DE-ElkeNeural", "de-DE-GiselaNeural", "de-DE-KasperNeural", "de-DE-KlarissaNeural", "de-DE-KlausNeural", "de-DE-LouisaNeural", "de-DE-MajaNeural", "de-DE-RalfNeural", "de-DE-TanjaNeural"],
    "Greek": ["el-GR-AthinaNeural", "el-GR-NestorasNeural"],
    "English": ["en-AU-NatashaNeural", "en-CA-ClaraNeural", "en-CA-LiamNeural", "en-HK-YanNeural", "en-HK-SamNeural", "en-IN-NeerjaExpressiveNeural", "en-IN-NeerjaNeural", "en-IN-PrabhatNeural", "en-IE-ConnorNeural", "en-IE-EmilyNeural", "en-KE-AsiliaNeural", "en-KE-ChilembaNeural", "en-NZ-MitchellNeural", "en-NZ-MollyNeural", "en-NG-AbeoNeural", "en-NG-EzinneNeural", "en-PH-JamesNeural", "en-PH-RosaNeural", "en-US-AvaNeural", "en-US-AndrewNeural", "en-US-EmmaNeural", "en-US-BrianNeural", "en-SG-LunaNeural", "en-SG-WayneNeural", "en-ZA-LeahNeural", "en-ZA-LukeNeural", "en-TZ-ElimuNeural", "en-TZ-ImaniNeural", "en-GB-LibbyNeural", "en-GB-MaisieNeural", "en-GB-RyanNeural", "en-GB-SoniaNeural", "en-GB-ThomasNeural", "en-US-AnaNeural", "en-US-AriaNeural", "en-US-ChristopherNeural", "en-US-EricNeural", "en-US-GuyNeural", "en-US-JennyNeural", "en-US-MichelleNeural", "en-US-RogerNeural", "en-US-SteffanNeural", "en-AU-AnnetteNeural", "en-AU-CarlyNeural", "en-AU-DarrenNeural", "en-AU-DuncanNeural", "en-AU-ElsieNeural", "en-AU-FreyaNeural", "en-AU-JoanneNeural", "en-AU-KenNeural", "en-AU-KimNeural", "en-AU-NeilNeural", "en-AU-TimNeural", "en-AU-TinaNeural", "en-AU-WilliamNeural", "en-GB-AbbiNeural", "en-GB-AlfieNeural", "en-GB-BellaNeural", "en-GB-ElliotNeural", "en-GB-EthanNeural", "en-GB-HollieNeural", "en-GB-MiaNeural", "en-GB-NoahNeural", "en-GB-OliverNeural", "en-GB-OliviaNeural", "en-IN-AaravNeural", "en-IN-AartiIndicNeural", "en-IN-AartiNeural", "en-IN-AashiNeural", "en-IN-AnanyaNeural", "en-IN-ArjunIndicNeural", "en-IN-ArjunNeural", "en-IN-KavyaNeural", "en-IN-KunalNeural", "en-IN-NeerjaIndicNeural", "en-IN-PrabhatIndicNeural", "en-IN-RehaanNeural", "en-US-AmberNeural", "en-US-AshleyNeural", "en-US-BrandonNeural", "en-US-CoraNeural", "en-US-DavisNeural", "en-US-ElizabethNeural", "en-US-JacobNeural", "en-US-JaneNeural", "en-US-JasonNeural", "en-US-JennyNeural", "en-US-KaiNeural", "en-US-LunaNeural", "en-US-MonicaNeural", "en-US-NancyNeural", "en-US-SaraNeural", "en-US-TonyNeural"],
    "Spanish": ["es-AR-ElenaNeural", "es-AR-TomasNeural", "es-BO-MarceloNeural", "es-BO-SofiaNeural", "es-CL-CatalinaNeural", "es-CL-LorenzoNeural", "es-CO-GonzaloNeural", "es-CO-SalomeNeural", "es-ES-XimenaNeural", "es-CR-JuanNeural", "es-CR-MariaNeural", "es-CU-BelkysNeural", "es-CU-ManuelNeural", "es-DO-EmilioNeural", "es-DO-RamonaNeural", "es-EC-AndreaNeural", "es-EC-LuisNeural", "es-SV-LorenaNeural", "es-SV-RodrigoNeural", "es-GQ-JavierNeural", "es-GQ-TeresaNeural", "es-GT-AndresNeural", "es-GT-MartaNeural", "es-HN-CarlosNeural", "es-HN-KarlaNeural", "es-MX-DaliaNeural", "es-MX-JorgeNeural", "es-NI-FedericoNeural", "es-NI-YolandaNeural", "es-PA-MargaritaNeural", "es-PA-RobertoNeural", "es-PY-MarioNeural", "es-PY-TaniaNeural", "es-PE-AlexNeural", "es-PE-CamilaNeural", "es-PR-KarinaNeural", "es-PR-VictorNeural", "es-ES-AlvaroNeural", "es-ES-ElviraNeural", "es-US-AlonsoNeural", "es-US-PalomaNeural", "es-UY-MateoNeural", "es-UY-ValentinaNeural", "es-VE-PaolaNeural", "es-VE-SebastianNeural", "es-ES-AbrilNeural", "es-ES-ArnauNeural", "es-ES-DarioNeural", "es-ES-EliasNeural", "es-ES-EstrellaNeural", "es-ES-IreneNeural", "es-ES-LaiaNeural", "es-ES-LiaNeural", "es-ES-NilNeural", "es-ES-SaulNeural", "es-ES-TeoNeural", "es-ES-TrianaNeural", "es-ES-VeraNeural", "es-MX-BeatrizNeural", "es-MX-CandelaNeural", "es-MX-CarlotaNeural", "es-MX-CecilioNeural", "es-MX-GerardoNeural", "es-MX-LarissaNeural", "es-MX-LibertoNeural", "es-MX-LucianoNeural", "es-MX-MarinaNeural", "es-MX-NuriaNeural", "es-MX-PelayoNeural", "es-MX-RenataNeural", "es-MX-YagoNeural"],
    "Estonian": ["et-EE-AnuNeural", "et-EE-KertNeural"],
    "Basque": ["eu-ES-AinhoaNeural", "eu-ES-AnderNeural"],
    "Persian": ["fa-IR-DilaraNeural", "fa-IR-FaridNeural"],
    "Finnish": ["fi-FI-HarriNeural", "fi-FI-NooraNeural", "fi-FI-SelmaNeural"],
    "Filipino": ["fil-PH-AngeloNeural", "fil-PH-BlessicaNeural"],
    "French": ["fr-BE-CharlineNeural", "fr-BE-GerardNeural", "fr-CA-ThierryNeural", "fr-CA-AntoineNeural", "fr-CA-JeanNeural", "fr-CA-SylvieNeural", "fr-FR-DeniseNeural", "fr-FR-EloiseNeural", "fr-FR-HenriNeural", "fr-CH-ArianeNeural", "fr-CH-FabriceNeural", "fr-FR-AlainNeural", "fr-FR-BrigitteNeural", "fr-FR-CelesteNeural", "fr-FR-ClaudeNeural", "fr-FR-CoralieNeural", "fr-FR-JacquelineNeural", "fr-FR-JeromeNeural", "fr-FR-JosephineNeural", "fr-FR-MauriceNeural", "fr-FR-YvesNeural", "fr-FR-YvetteNeural"],
    "Irish": ["ga-IE-ColmNeural", "ga-IE-OrlaNeural"],
    "Galician": ["gl-ES-RoiNeural", "gl-ES-SabelaNeural"],
    "Gujarati": ["gu-IN-DhwaniNeural", "gu-IN-NiranjanNeural"],
    "Hebrew": ["he-IL-AvriNeural", "he-IL-HilaNeural"],
    "Hindi": ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural", "hi-IN-AaravNeural", "hi-IN-AartiNeural", "hi-IN-AashiNeural", "hi-IN-AnanyaNeural", "hi-IN-ArjunNeural", "hi-IN-KavyaNeural", "hi-IN-KunalNeural", "hi-IN-RehaanNeural"],
    "Croatian": ["hr-HR-GabrijelaNeural", "hr-HR-SreckoNeural"],
    "Hungarian": ["hu-HU-NoemiNeural", "hu-HU-TamasNeural"],
    "Indonesian": ["id-ID-ArdiNeural", "id-ID-GadisNeural"],
    "Icelandic": ["is-IS-GudrunNeural", "is-IS-GunnarNeural"],
    "Italian": ["it-IT-DiegoNeural", "it-IT-ElsaNeural", "it-IT-IsabellaNeural", "it-IT-BenignoNeural", "it-IT-CalimeroNeural", "it-IT-CataldoNeural", "it-IT-CosimoNeural", "it-IT-FabiolaNeural", "it-IT-ImeldaNeural", "it-IT-IrmaNeural", "it-IT-LisandroNeural", "it-IT-MarcelloNeural", "it-IT-PierinaNeural", "it-IT-RiccardoNeural", "it-IT-SilvanoNeural"],
    "Inuktitut": ["iu-Latn-CA-SiqiniqNeural", "iu-Latn-CA-TaqqiqNeural", "iu-Cans-CA-SiqiniqNeural", "iu-Cans-CA-TaqqiqNeural"],
    "Japanese": ["ja-JP-KeitaNeural", "ja-JP-NanamiNeural", "ja-JP-MasaruNeural", "ja-JP-MayuNeural", "ja-JP-RisaNeural", "ja-JP-ShioriNeural"],
    "Javanese": ["jv-ID-DimasNeural", "jv-ID-SitiNeural"],
    "Georgian": ["ka-GE-EkaNeural", "ka-GE-GiorgiNeural"],
    "Kazakh": ["kk-KZ-AigulNeural", "kk-KZ-DauletNeural"],
    "Khmer": ["km-KH-PisethNeural", "km-KH-SreymomNeural"],
    "Kannada": ["kn-IN-GaganNeural", "kn-IN-SapnaNeural"],
    "Korean": ["ko-KR-InJoonNeural", "ko-KR-SunHiNeural", "ko-KR-BongJinNeural", "ko-KR-GookMinNeural", "ko-KR-JiMinNeural", "ko-KR-SeungHwanNeural"],
    "Lao": ["lo-LA-ChanthavongNeural", "lo-LA-KeomanyNeural"],
    "Lithuanian": ["lt-LT-LeonasNeural", "lt-LT-OnaNeural", "lt-LT-LeonaNeural"],
    "Latvian": ["lv-LV-EveritaNeural", "lv-LV-NilsNeural"],
    "Macedonian": ["mk-MK-AleksandarNeural", "mk-MK-MarijaNeural"],
    "Malayalam": ["ml-IN-MidhunNeural", "ml-IN-SobhanaNeural"],
    "Mongolian": ["mn-MN-BataaNeural", "mn-MN-YesuiNeural"],
    "Marathi": ["mr-IN-AarohiNeural", "mr-IN-ManoharNeural"],
    "Malay": ["ms-MY-OsmanNeural", "ms-MY-YasminNeural"],
    "Maltese": ["mt-MT-GraceNeural", "mt-MT-JosephNeural"],
    "Myanmar": ["my-MM-NilarNeural", "my-MM-ThihaNeural"],
    "Norwegian": ["nb-NO-FinnNeural", "nb-NO-PernilleNeural"],
    "Nepali": ["ne-NP-HemkalaNeural", "ne-NP-SagarNeural"],
    "Dutch": ["nl-BE-ArnaudNeural", "nl-BE-DenaNeural", "nl-NL-ColetteNeural", "nl-NL-FennaNeural", "nl-NL-MaartenNeural"],
    "Polish": ["pl-PL-MarekNeural", "pl-PL-ZofiaNeural", "pl-PL-AgnieszkaNeural"],
    "Pashto": ["ps-AF-GulNawazNeural", "ps-AF-LatifaNeural"],
    "Portuguese": ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", "pt-PT-DuarteNeural", "pt-PT-RaquelNeural", "pt-BR-BrendaNeural", "pt-BR-FabioNeural", "pt-BR-ThalitaNeural"],
    "Romanian": ["ro-RO-AlinaNeural", "ro-RO-EmilNeural"],
    "Russian": ["ru-RU-DmitryNeural", "ru-RU-SvetlanaNeural"],
    "Sinhala": ["si-LK-SameeraNeural", "si-LK-ThiliniNeural"],
    "Slovak": ["sk-SK-LukasNeural", "sk-SK-ViktoriaNeural"],
    "Slovenian": ["sl-SI-PetraNeural", "sl-SI-RokNeural"],
    "Somali": ["so-SO-MuuseNeural", "so-SO-UbaxNeural"],
    "Albanian": ["sq-AL-AnilaNeural", "sq-AL-IlirNeural"],
    "Serbian": ["sr-RS-NicholasNeural", "sr-RS-SophieNeural"],
    "Sundanese": ["su-ID-JajangNeural", "su-ID-TutiNeural"],
    "Swedish": ["sv-SE-MattiasNeural", "sv-SE-SofieNeural"],
    "Swahili": ["sw-KE-RafikiNeural", "sw-KE-ZuriNeural", "sw-TZ-DaudiNeural", "sw-TZ-RehemaNeural"],
    "Tamil": ["ta-IN-PallaviNeural", "ta-IN-ValluvarNeural", "ta-MY-KaniNeural", "ta-MY-SuryaNeural", "ta-SG-AnbuNeural", "ta-SG-VenbaNeural", "ta-LK-KumarNeural", "ta-LK-SaranyaNeural"],
    "Telugu": ["te-IN-MohanNeural", "te-IN-ShrutiNeural"],
    "Thai": ["th-TH-NiwatNeural", "th-TH-PremwadeeNeural"],
    "Turkish": ["tr-TR-EmelNeural", "tr-TR-AhmetNeural"],
    "Ukrainian": ["uk-UA-OstapNeural", "uk-UA-PolinaNeural"],
    "Urdu": ["ur-IN-GulNeural", "ur-IN-SalmanNeural", "ur-PK-AsadNeural", "ur-PK-UzmaNeural"],
    "Uzbek": ["uz-UZ-MadinaNeural", "uz-UZ-SardorNeural"],
    "Vietnamese": ["vi-VN-HoaiMyNeural", "vi-VN-NamMinhNeural"],
    "Chinese": ["zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural", "zh-CN-XiaoxiaoNeural", "zh-CN-XiaoyiNeural", "zh-CN-YunjianNeural", "zh-CN-YunxiNeural", "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural", "zh-CN-liaoning-XiaobeiNeural", "zh-TW-HsiaoChenNeural", "zh-TW-YunJheNeural", "zh-TW-HsiaoYuNeural", "zh-CN-shaanxi-XiaoniNeural", "zh-CN-XiaochenNeural", "zh-CN-XiaoyiNeural", "zh-CN-XiaoyuNeural", "zh-CN-YunjianNeural", "zh-CN-YunxiNeural", "zh-CN-YunxiaNeural", "zh-CN-YunyangNeural", "zh-HK-HiuGaaiNeural", "zh-HK-HiuMaanNeural", "zh-HK-WanLungNeural", "zh-TW-HsiaoChenNeural", "zh-TW-HsiaoYuNeural", "zh-TW-YunJheNeural"],
    "Zulu": ["zu-ZA-ThandoNeural", "zu-ZA-ThembaNeural"]
}

multilingual_en_voices = [k for k in MULTILINGUAL_VOICES.keys() if "English" in MULTILINGUAL_VOICES[k]]

if "en-US-SteffanMultilingualNeural" in TTS_VOICES_BY_LANGUAGE.get("English", []):
    TTS_VOICES_BY_LANGUAGE["English"].remove("en-US-SteffanMultilingualNeural")

for k in multilingual_en_voices:
    if k not in TTS_VOICES_BY_LANGUAGE.get("English", []):
        TTS_VOICES_BY_LANGUAGE["English"].append(k)

MOST_USED = [
    "English", "Chinese", "Spanish", "Arabic", "Portuguese", "Indonesian", "French", "Russian",
    "Japanese", "German", "Vietnamese", "Turkish", "Korean", "Italian", "Polish", "Dutch",
    "Persian", "Hindi", "Urdu", "Bengali", "Filipino", "Malay", "Thai", "Romanian", "Ukrainian"
]

ORDERED_TTS_LANGUAGES = [l for l in MOST_USED if l in TTS_VOICES_BY_LANGUAGE] + sorted([l for l in TTS_VOICES_BY_LANGUAGE.keys() if l not in MOST_USED])

def update_user_activity(user_id: int):
    user_id_str = str(user_id)
    now_iso = datetime.now().isoformat()
    users_collection.update_one(
        {"_id": user_id_str},
        {"$set": {"last_active": now_iso}, "$setOnInsert": {"_id": user_id_str, "tts_conversion_count": 0}},
        upsert=True
    )

def increment_processing_count(user_id: str):
    user_id_str = str(user_id)
    users_collection.update_one(
        {"_id": user_id_str},
        {"$inc": {"tts_conversion_count": 1}, "$set": {"last_active": datetime.now().isoformat()}},
        upsert=True
    )

def get_tts_user_voice(user_id: str) -> str:
    settings = tts_settings_collection.find_one({"_id": user_id})
    return settings.get("voice", "en-US-PhoebeMultilingualNeural") if settings else "en-US-PhoebeMultilingualNeural"

def set_tts_user_voice(user_id: str, voice: str):
    tts_settings_collection.update_one(
        {"_id": user_id},
        {"$set": {"voice": voice}},
        upsert=True
    )

def get_tts_user_pitch(user_id: str) -> int:
    settings = tts_settings_collection.find_one({"_id": user_id})
    return settings.get("pitch", 0) if settings else 0

def set_tts_user_pitch(user_id: str, pitch: int):
    tts_settings_collection.update_one(
        {"_id": user_id},
        {"$set": {"pitch": pitch}},
        upsert=True
    )

def get_tts_user_rate(user_id: str) -> int:
    settings = tts_settings_collection.find_one({"_id": user_id})
    return settings.get("rate", 0) if settings else 0

def set_tts_user_rate(user_id: str, rate: int):
    tts_settings_collection.update_one(
        {"_id": user_id},
        {"$set": {"rate": rate}},
        upsert=True
    )

def keep_recording(chat_id, stop_event, target_bot):
    while not stop_event.is_set():
        try:
            target_bot.send_chat_action(chat_id, 'record_audio')
            time.sleep(4)
        except Exception:
            break

def check_subscription(user_id: int) -> bool:
    if not REQUIRED_CHANNEL or not REQUIRED_CHANNEL.strip():
        return True
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except telebot.apihelper.ApiTelegramException:
        return False

def send_subscription_message(chat_id: int):
    if not REQUIRED_CHANNEL or not REQUIRED_CHANNEL.strip():
        return
    try:
        chat = bot.get_chat(chat_id)
        if chat.type != 'private':
            return
    except Exception:
        return
    try:
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton(
                "🔗 join Channel",
                url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"
            )
        )
        bot.send_message(
            chat_id,
            "🚫 First join the channel @ejbots to use this bot",
            reply_markup=markup
        )
    except Exception:
        pass

def make_language_selection_keyboard():
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(InlineKeyboardButton("Multilingual", callback_data="tts_multilingual"))
    buttons = []
    for lang_name in ORDERED_TTS_LANGUAGES:
        if lang_name in TTS_VOICES_BY_LANGUAGE:
            buttons.append(InlineKeyboardButton(lang_name, callback_data=f"tts_lang|{lang_name}"))
    for i in range(0, len(buttons), 3):
        markup.add(*buttons[i:i+3])
    return markup

def make_tts_multilingual_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    for voice_id, display_name in MULTILINGUAL_VOICES.items():
        if "Steffan" in voice_id:
            continue
        markup.add(InlineKeyboardButton(display_name, callback_data=f"tts_voice|{voice_id}"))
    steffan_id = "en-US-SteffanMultilingualNeural"
    steffan_display = MULTILINGUAL_VOICES.get(steffan_id, "Steffan - Multilingual (United States)")
    markup.add(InlineKeyboardButton(steffan_display, callback_data=f"tts_voice|{steffan_id}"))
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="tts_back_to_languages"))
    return markup

def make_tts_voice_keyboard_for_language(lang_name: str):
    markup = InlineKeyboardMarkup(row_width=2)
    voices = TTS_VOICES_BY_LANGUAGE.get(lang_name, [])
    for voice in voices:
        display_name = VOICE_MAPPING.get(voice, voice)
        markup.add(InlineKeyboardButton(display_name, callback_data=f"tts_voice|{voice}"))
    markup.add(InlineKeyboardButton("⬅️ Back", callback_data="tts_back_to_languages"))
    return markup

def make_pitch_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⬆️ High", callback_data="pitch_set|+50"),
        InlineKeyboardButton("⬇️ Lower", callback_data="pitch_set|-50"),
        InlineKeyboardButton("🔄 Reset", callback_data="pitch_set|0")
    )
    return markup

def make_rate_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⚡️ Speed", callback_data="rate_set|+50"),
        InlineKeyboardButton("🐢 Slow down", callback_data="rate_set|-50"),
        InlineKeyboardButton("🔄 Reset", callback_data="rate_set|0")
    )
    return markup

def handle_rate_command(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    user_tts_mode[user_id] = None
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = "awaiting_rate_input"
    bot.send_message(
        chat_id,
        "How fast or slow should I speak? Choose one or send a number from -100 (slow) to +100 (fast), 0 is normal:",
        reply_markup=make_rate_keyboard()
    )

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id_str = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    user_tts_mode[user_id_str] = None
    user_pitch_input_mode[user_id_str] = None
    user_rate_input_mode[user_id_str] = None
    markup = make_language_selection_keyboard()
    bot.send_message(
        message.chat.id,
        "Choose Multilingual or a language:",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['help'])
def help_handler(message):
    user_id = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    user_tts_mode[user_id] = None
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    help_text = "Not available ❌"
    bot.send_message(message.chat.id, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['privacy'])
def privacy_notice_handler(message):
    user_id = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    user_tts_mode[user_id] = None
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    privacy_text = "Not available ❌"
    bot.send_message(message.chat.id, privacy_text, parse_mode="Markdown")

@bot.message_handler(commands=['voices_list'])
def voices_list_handler(message):
    update_user_activity(message.from_user.id)
    bot.send_message(message.chat.id, "🔄 Generating the voice list, please wait...")
    threading.Thread(
        target=lambda: asyncio.run(generate_and_send_voice_list(message.chat.id))
    ).start()

async def generate_and_send_voice_list(chat_id: int):
    try:
        voices_manager = await VoicesManager.create()
        voices = voices_manager.find()
        voices_by_language = {}
        for voice in voices:
            lang_code = voice['Locale'].split('-')[0] if '-' in voice['Locale'] else voice['Locale']
            lang_name = lang_code.capitalize()
            if lang_name not in voices_by_language:
                voices_by_language[lang_name] = []
            styles = voice.get('StyleList', ['default'])
            if not isinstance(styles, list):
                styles = ['default']
            voices_by_language[lang_name].append({
                'name': voice['ShortName'],
                'gender': voice.get('Gender', 'Unknown'),
                'styles': styles
            })
        sorted_languages = sorted(voices_by_language.keys())
        output_lines = ["Microsoft Text-to-Speech Voices and Styles by Language\n"]
        output_lines.append("=" * 50 + "\n")
        for lang in sorted_languages:
            output_lines.append(f"Language: {lang}\n")
            output_lines.append("-" * 30 + "\n")
            for voice in voices_by_language[lang]:
                output_lines.append(f"Voice Name: {voice['name']}\n")
                output_lines.append(f"Gender: {voice['gender']}\n")
                output_lines.append(f"Styles: {', '.join(voice['styles'])}\n")
                output_lines.append("\n")
            output_lines.append("\n")
        filename = f"voices_list_{uuid.uuid4()}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.writelines(output_lines)
        with open(filename, 'rb') as f:
            bot.send_document(
                chat_id,
                f,
                caption="📋 List of Microsoft Text-to-Speech voices and their styles by language."
            )
        try:
            os.remove(filename)
        except Exception:
            pass
    except Exception as e:
        logging.error(f"Error generating voice list: {e}")
        bot.send_message(chat_id, f"❌ Failed to generate voice list: {str(e)}")

@bot.callback_query_handler(lambda c: c.data == "tts_multilingual")
def on_tts_multilingual_select(call):
    user_id = str(call.from_user.id)
    update_user_activity(call.from_user.id)
    if call.message.chat.type == 'private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id)
        bot.answer_callback_query(call.id)
        return
    chat_id = call.message.chat.id
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="Okay! Now choose a specific voice from Multilingual.👇",
        reply_markup=make_tts_multilingual_keyboard()
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(lambda c: c.data.startswith("tts_lang|"))
def on_tts_language_select(call):
    user_id = str(call.from_user.id)
    update_user_activity(call.from_user.id)
    if call.message.chat.type == 'private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id)
        bot.answer_callback_query(call.id)
        return
    chat_id = call.message.chat.id
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    _, lang_name = call.data.split("|", 1)
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text=f"Okay! Now choose a specific *voice* from {lang_name}.👇",
        reply_markup=make_tts_voice_keyboard_for_language(lang_name),
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(lambda c: c.data.startswith("tts_voice|"))
def on_tts_voice_change(call):
    user_id = str(call.from_user.id)
    update_user_activity(call.from_user.id)
    if call.message.chat.type == 'private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id)
        bot.answer_callback_query(call.id)
        return
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    _, voice = call.data.split("|", 1)
    set_tts_user_voice(user_id, voice)
    user_tts_mode[user_id] = voice
    voice_display_name = VOICE_MAPPING.get(voice, voice)
    
    bot.answer_callback_query(call.id, f"✔️ You are using: {voice_display_name}", show_alert=False)
    
    # Kani waa hagaajinta: Tirtir fariinta keyboard-ka inline-ka ah.
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e:
        logging.error(f"Failed to delete message after voice selection: {e}")

@bot.callback_query_handler(lambda c: c.data == "tts_back_to_languages")
def on_tts_back_to_languages(call):
    user_id = str(call.from_user.id)
    update_user_activity(call.from_user.id)
    if call.message.chat.type == 'private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id)
        bot.answer_callback_query(call.id)
        return
    chat_id = call.message.chat.id
    user_tts_mode[user_id] = None
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    markup = make_language_selection_keyboard()
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=call.message.message_id,
        text="Choose Multilingual or a language:",
        reply_markup=markup,
        parse_mode="Markdown"
    )
    bot.answer_callback_query(call.id)

def handle_pitch_command(message):
    chat_id = message.chat.id
    user_id = str(message.from_user.id)
    user_tts_mode[user_id] = None
    user_pitch_input_mode[user_id] = "awaiting_pitch_input"
    user_rate_input_mode[user_id] = None
    bot.send_message(
        chat_id,
        "Let's adjust the pitch! Choose one or send a number from -100 (low) to +100 (high), 0 is normal:",
        reply_markup=make_pitch_keyboard()
    )

@bot.message_handler(commands=['rate'])
def cmd_voice_rate(message):
    user_id = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    handle_rate_command(message)

@bot.callback_query_handler(lambda c: c.data.startswith("rate_set|"))
def on_rate_set_callback(call):
    user_id = str(call.from_user.id)
    update_user_activity(call.from_user.id)
    if call.message.chat.type == 'private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id)
        bot.answer_callback_query(call.id)
        return
    user_rate_input_mode[user_id] = None
    try:
        _, rate_value_str = call.data.split("|", 1)
        rate_value = int(rate_value_str)
        set_tts_user_rate(user_id, rate_value)
        
        bot.answer_callback_query(call.id, f"✔️ Speech rate is {rate_value}!", show_alert=False)
        
        # Kani waa hagaajinta: Tirtir fariinta keyboard-ka inline-ka ah.
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            logging.error(f"Failed to delete message after rate selection: {e}")
            
    except Exception:
        bot.answer_callback_query(call.id, "Invalid rate.")

@bot.message_handler(commands=['pitch'])
def cmd_voice_pitch(message):
    user_id = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    handle_pitch_command(message)

@bot.callback_query_handler(lambda c: c.data.startswith("pitch_set|"))
def on_pitch_set_callback(call):
    user_id = str(call.from_user.id)
    update_user_activity(call.from_user.id)
    if call.message.chat.type == 'private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id)
        bot.answer_callback_query(call.id)
        return
    user_pitch_input_mode[user_id] = None
    try:
        _, pitch_value_str = call.data.split("|", 1)
        pitch_value = int(pitch_value_str)
        set_tts_user_pitch(user_id, pitch_value)
        
        bot.answer_callback_query(call.id, f"✔️ The pitch is {pitch_value}!", show_alert=False)
        
        # Kani waa hagaajinta: Tirtir fariinta keyboard-ka inline-ka ah.
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            logging.error(f"Failed to delete message after pitch selection: {e}")
            
    except Exception:
        bot.answer_callback_query(call.id, "Invalid pitch.")

async def synth_and_send_tts(chat_id: int, user_id: str, text: str, reply_to_message_id: int = None):
    voice = get_tts_user_voice(user_id)
    if voice.startswith("so-"):
        text = text.replace('.', ',')
    pitch_val = get_tts_user_pitch(user_id)
    rate_val = get_tts_user_rate(user_id)
    digits_len = random.randint(6, 8)
    digits = "".join(str(random.randint(0, 9)) for _ in range(digits_len))
    voice_display_name = VOICE_MAPPING.get(voice, voice)
    safe_name = re.sub(r"[^\w\-]", "_", voice_display_name)
    filename = f"{safe_name}_{digits}.mp3"
    stop_recording = threading.Event()
    recording_thread = threading.Thread(target=keep_recording, args=(chat_id, stop_recording, bot))
    recording_thread.daemon = True
    recording_thread.start()

    try:
        pitch = f"+{pitch_val}Hz" if pitch_val >= 0 else f"{pitch_val}Hz"
        rate = f"+{rate_val}%" if rate_val >= 0 else f"{rate_val}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(filename)

        if not os.path.exists(filename) or os.path.getsize(filename) == 0:
            bot.send_message(chat_id, "❌ Failed to create the audio. The text may be invalid. Please try a different text.")
            return

        #caption_text = (
           #"🎧 Here is your voice\n\n"
    #f"Voice: *{voice_display_name}*\n"
    #f"Pitch: *{pitch}*\n"
   # f"Rate: *{rate}*\n\n"
   # "Bot Supports Commands:\n"
    #"/start - Change the voice actor\n"
    #"/rate - Change voice speed\n"
    #"/pitch - Change voice pitch\n\n"
   # "Save to your phone 💗"
        #)

        with open(filename, "rb") as f:
            try:
                bot.send_audio(
                    chat_id,
                    f,
                    caption=caption_text,
                    parse_mode="Markdown",
                    reply_to_message_id=reply_to_message_id
                )
            except Exception:
                bot.send_audio(
                    chat_id,
                    f
                )

        increment_processing_count(user_id)

    except Exception as e:
        logging.exception("TTS error")
        bot.send_message(chat_id, f"❌ Unexpected error: {str(e)}.")
    finally:
        stop_recording.set()
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass

@bot.message_handler(content_types=['text'])
def handle_text_for_tts_or_mode_input(message):
    user_id = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    if message.text.startswith('/'):
        return
    if user_rate_input_mode.get(user_id) == "awaiting_rate_input":
        # Tirtir fariinta la soo diray si loogu jawaabo message-ka keyboard-ka ee /rate
        if message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
            try:
                bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            except Exception:
                pass

        try:
            rate_val = int(message.text)
            if -100 <= rate_val <= 100:
                set_tts_user_rate(user_id, rate_val)
                bot.send_message(message.chat.id, f"🔊 The speech rate is *{rate_val}*.", parse_mode="Markdown")
                user_rate_input_mode[user_id] = None
            else:
                bot.send_message(message.chat.id, "❌ Invalid rate. Send a number from -100 to +100 or 0. Try again:")
            return
        except ValueError:
            bot.send_message(message.chat.id, "That is not a valid number. Send a number from -100 to +100 or 0. Try again:")
            return
            
    if user_pitch_input_mode.get(user_id) == "awaiting_pitch_input":
        # Tirtir fariinta la soo diray si loogu jawaabo message-ka keyboard-ka ee /pitch
        if message.reply_to_message and message.reply_to_message.from_user.id == bot.get_me().id:
            try:
                bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            except Exception:
                pass
                
        try:
            pitch_val = int(message.text)
            if -100 <= pitch_val <= 100:
                set_tts_user_pitch(user_id, pitch_val)
                bot.send_message(message.chat.id, f"🔊 The pitch is *{pitch_val}*.", parse_mode="Markdown")
                user_pitch_input_mode[user_id] = None
            else:
                bot.send_message(message.chat.id, "❌ Invalid pitch. Send a number from -100 to +100 or 0. Try again:")
            return
        except ValueError:
            bot.send_message(message.chat.id, "That is not a valid number. Send a number from -100 to +100 or 0. Try again:")
            return
            
    current_voice = get_tts_user_voice(user_id)
    threading.Thread(
        target=lambda: asyncio.run(synth_and_send_tts(message.chat.id, user_id, message.text, message.message_id))
    ).start()

@bot.message_handler(content_types=['voice', 'audio', 'video', 'document', 'sticker', 'photo'])
def handle_unsupported_media_types(message):
    user_id = str(message.from_user.id)
    update_user_activity(message.from_user.id)
    if message.chat.type == 'private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id)
        return
    user_tts_mode[user_id] = None
    user_pitch_input_mode[user_id] = None
    user_rate_input_mode[user_id] = None
    bot.send_message(
        message.chat.id,
        "For Audio to Text use: @MediaToTextBot"
    )

@app.route("/", methods=["GET", "POST", "HEAD"])
def webhook():
    if request.method in ("GET", "HEAD"):
        return "OK", 200
    if request.method == "POST":
        content_type = request.headers.get("Content-Type", "")
        if content_type and content_type.startswith("application/json"):
            update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
            bot.process_new_updates([update])
            return "", 200
    return abort(403)

@app.route("/set_webhook", methods=["GET", "POST"])
def set_webhook_route():
    try:
        bot.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}")
        return f"Failed to set webhook: {e}", 500

@app.route("/delete_webhook", methods=["GET", "POST"])
def delete_webhook_route():
    try:
        bot.delete_webhook()
        return "Webhook deleted.", 200
    except Exception as e:
        logging.error(f"Failed to delete webhook: {e}")
        return f"Failed to delete webhook: {e}", 500

def set_webhook_on_startup():
    try:
        bot.delete_webhook()
        time.sleep(1)
        bot.set_webhook(url=WEBHOOK_URL)
        logging.info(f"Main bot webhook set successfully to {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"Failed to set main bot webhook on startup: {e}")

def set_bot_info_and_startup():
    set_webhook_on_startup()

if __name__ == "__main__":
    set_bot_info_and_startup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
