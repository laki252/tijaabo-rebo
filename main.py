import os, re, uuid, time, random, threading, logging, asyncio
from datetime import datetime
from flask import Flask, request, abort
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import edge_tts
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

TOKEN = "8281896922:AAF5KBeSbSmfA2gb9R_9mLwepM50R-k37GY"
WEBHOOK_URL = "https://you-tube-save-bot-5tbw.onrender.com"
REQUIRED_CHANNEL = ""

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
"de-DE-SeraphinaMultilingualNeural","de-DE-FlorianMultilingualNeural","en-AU-WilliamMultilingualNeural",
"en-GB-AdaMultilingualNeural","en-GB-OllieMultilingualNeural","en-US-AvaMultilingualNeural","en-US-AndrewMultilingualNeural",
"en-US-AmandaMultilingualNeural","en-US-AdamMultilingualNeural","en-US-EmmaMultilingualNeural","en-US-PhoebeMultilingualNeural",
"en-US-AlloyTurboMultilingualNeural","en-US-EchoTurboMultilingualNeural","en-US-FableTurboMultilingualNeural","en-US-OnyxTurboMultilingualNeural",
"en-US-NovaTurboMultilingualNeural","en-US-ShimmerTurboMultilingualNeural","en-US-BrianMultilingualNeural","en-US-CoraMultilingualNeural",
"en-US-ChristopherMultilingualNeural","en-US-BrandonMultilingualNeural","en-US-DavisMultilingualNeural","en-US-DerekMultilingualNeural",
"en-US-DustinMultilingualNeural","en-US-JennyMultilingualNeural","en-US-LewisMultilingualNeural","en-US-LolaMultilingualNeural",
"en-US-NancyMultilingualNeural","en-US-RyanMultilingualNeural","en-US-SamuelMultilingualNeural","en-US-SerenaMultilingualNeural",
"es-ES-ArabellaMultilingualNeural","es-ES-IsidoraMultilingualNeural","es-ES-TristanMultilingualNeural","es-ES-XimenaMultilingualNeural",
"es-MX-DaliaMultilingualNeural","es-MX-JorgeMultilingualNeural","fr-FR-VivienneMultilingualNeural","fr-FR-RemyMultilingualNeural",
"fr-FR-LucienMultilingualNeural","it-IT-AlessioMultilingualNeural","it-IT-IsabellaMultilingualNeural","it-IT-GiuseppeMultilingualNeural",
"it-IT-MarcelloMultilingualNeural","ko-KR-HyunsuMultilingualNeural","pt-BR-MacerioMultilingualNeural","pt-BR-ThalitaMultilingualNeural",
"zh-CN-XiaochenMultilingualNeural","zh-CN-XiaoxiaoMultilingualNeural","zh-CN-XiaoyuMultilingualNeural","zh-CN-YunxiaoMultilingualNeural",
"zh-CN-YunyiMultilingualNeural","zh-CN-YunfanMultilingualNeural","en-US-SteffanMultilingualNeural"
}

country_map = {"DE":"Germany","AU":"Australia","GB":"United Kingdom","US":"United States","ES":"Spain","MX":"Mexico","FR":"France","IT":"Italy","KR":"Korea","BR":"Brazil","CN":"China"}

def short_name_from_id(vid):
    last = vid.split("-")[-1]
    name = re.sub(r"(MultilingualNeural|TurboMultilingualNeural|Neural|Turbo)$", "", last)
    return name

MULTILINGUAL_VOICES = {vid: f"{short_name_from_id(vid)} - Multilingual ({country_map.get(vid.split('-')[1] if len(vid.split('-'))>1 else '', vid.split('-')[1] if len(vid.split('-'))>1 else '')})" for vid in raw_multilingual_ids}

VOICE_LINES = """af-ZA-AdriNeural|Adri - Afrikaans (South Africa)
af-ZA-WillemNeural|Willem - Afrikaans (South Africa)
am-ET-AmehaNeural|Ameha - Amharic (Ethiopia)
am-ET-MekdesNeural|Mekdes - Amharic (Ethiopia)
ar-DZ-AminaNeural|Amina - Arabic (Algeria)
ar-DZ-IsmaelNeural|Ismael - Arabic (Algeria)
ar-BH-AliNeural|Ali - Arabic (Bahrain)
ar-BH-LailaNeural|Laila - Arabic (Bahrain)
ar-EG-SalmaNeural|Salma - Arabic (Egypt)
ar-EG-ShakirNeural|Shakir - Arabic (Egypt)
ar-IQ-BasselNeural|Bassel - Arabic (Iraq)
ar-IQ-RanaNeural|Rana - Arabic (Iraq)
ar-JO-SanaNeural|Sana - Arabic (Jordan)
ar-JO-TaimNeural|Taim - Arabic (Jordan)
ar-KW-FahedNeural|Fahed - Arabic (Kuwait)
ar-KW-NouraNeural|Noura - Arabic (Kuwait)
ar-LB-LaylaNeural|Layla - Arabic (Lebanon)
ar-LB-RamiNeural|Rami - Arabic (Lebanon)
ar-LY-ImanNeural|Iman - Arabic (Libya)
ar-LY-OmarNeural|Omar - Arabic (Libya)
ar-MA-JamalNeural|Jamal - Arabic (Morocco)
ar-MA-MounaNeural|Mouna - Arabic (Morocco)
ar-OM-AbdullahNeural|Abdullah - Arabic (Oman)
ar-OM-AyshaNeural|Aysha - Arabic (Oman)
ar-QA-AmalNeural|Amal - Arabic (Qatar)
ar-QA-MoazNeural|Moaz - Arabic (Qatar)
ar-SA-HamedNeural|Hamed - Arabic (Saudi Arabia)
ar-SA-ZariyahNeural|Zariyah - Arabic (Saudi Arabia)
ar-SY-AmanyNeural|Amany - Arabic (Syria)
ar-SY-LaithNeural|Laith - Arabic (Syria)
ar-TN-HediNeural|Hedi - Arabic (Tunisia)
ar-TN-ReemNeural|Reem - Arabic (Tunisia)
ar-AE-FatimaNeural|Fatima - Arabic (UAE)
ar-AE-HamdanNeural|Hamdan - Arabic (UAE)
ar-YE-MaryamNeural|Maryam - Arabic (Yemen)
ar-YE-SalehNeural|Saleh - Arabic (Yemen)
as-IN-PriyomNeural|Priyom - Assamese (India)
as-IN-YashicaNeural|Yashica - Assamese (India)
az-AZ-BabekNeural|Babek - Azerbaijani (Azerbaijan)
az-AZ-BanuNeural|Banu - Azerbaijani (Azerbaijan)
bg-BG-BorislavNeural|Borislav - Bulgarian (Bulgaria)
bg-BG-KalinaNeural|Kalina - Bulgarian (Bulgaria)
bn-BD-NabanitaNeural|Nabanita - Bengali (Bangladesh)
bn-BD-PradeepNeural|Pradeep - Bengali (Bangladesh)
bn-IN-BashkarNeural|Bashkar - Bengali (India)
bn-IN-TanishaaNeural|Tanishaa - Bengali (India)
bs-BA-VesnaNeural|Vesna - Bosnian (Bosnia and Herzegovina)
bs-BA-GoranNeural|Goran - Bosnian (Bosnia and Herzegovina)
ca-ES-AlbaNeural|Alba - Catalan (Spain)
ca-ES-EnricNeural|Enric - Catalan (Spain)
ca-ES-JoanaNeural|Joana - Catalan (Spain)
cs-CZ-AntoninNeural|Antonin - Czech (Czech Republic)
cs-CZ-VlastaNeural|Vlasta - Czech (Czech Republic)
cy-GB-AledNeural|Aled - Welsh (United Kingdom)
cy-GB-NiaNeural|Nia - Welsh (United Kingdom)
da-DK-ChristelNeural|Christel - Danish (Denmark)
da-DK-JeppeNeural|Jeppe - Danish (Denmark)
de-AT-IngridNeural|Ingrid - German (Austria)
de-AT-JonasNeural|Jonas - German (Austria)
de-DE-AmalaNeural|Amala - German (Germany)
de-DE-ConradNeural|Conrad - German (Germany)
de-DE-KatjaNeural|Katja - German (Germany)
de-DE-KillianNeural|Killian - German (Germany)
de-DE-BerndNeural|Bernd - German (Germany)
de-DE-ChristophNeural|Christoph - German (Germany)
de-DE-ElkeNeural|Elke - German (Germany)
de-DE-GiselaNeural|Gisela - German (Germany)
de-DE-KasperNeural|Kasper - German (Germany)
de-DE-KlarissaNeural|Klarissa - German (Germany)
de-DE-KlausNeural|Klaus - German (Germany)
de-DE-LouisaNeural|Louisa - German (Germany)
de-DE-MajaNeural|Maja - German (Germany)
de-DE-RalfNeural|Ralf - German (Germany)
de-DE-TanjaNeural|Tanja - German (Germany)
de-CH-JanNeural|Jan - German (Switzerland)
de-CH-LeniNeural|Leni - German (Switzerland)
el-GR-AthinaNeural|Athina - Greek (Greece)
el-GR-NestorasNeural|Nestoras - Greek (Greece)
en-AU-AnnetteNeural|Annette - English (Australia)
en-AU-CarlyNeural|Carly - English (Australia)
en-AU-DarrenNeural|Darren - English (Australia)
en-AU-DuncanNeural|Duncan - English (Australia)
en-AU-ElsieNeural|Elsie - English (Australia)
en-AU-FreyaNeural|Freya - English (Australia)
en-AU-JoanneNeural|Joanne - English (Australia)
en-AU-KenNeural|Ken - English (Australia)
en-AU-KimNeural|Kim - English (Australia)
en-AU-NeilNeural|Neil - English (Australia)
en-AU-NatashaNeural|Natasha - English (Australia)
en-AU-TimNeural|Tim - English (Australia)
en-AU-TinaNeural|Tina - English (Australia)
en-AU-WilliamNeural|William - English (Australia)
en-CA-ClaraNeural|Clara - English (Canada)
en-CA-LiamNeural|Liam - English (Canada)
en-HK-YanNeural|Yan - English (Hong Kong)
en-HK-SamNeural|Sam - English (Hong Kong)
en-IN-AaravNeural|Aarav - English (India)
en-IN-AartiIndicNeural|AartiIndic - English (India)
en-IN-AartiNeural|Aarti - English (India)
en-IN-AashiNeural|Aashi - English (India)
en-IN-AnanyaNeural|Ananya - English (India)
en-IN-ArjunIndicNeural|ArjunIndic - English (India)
en-IN-ArjunNeural|Arjun - English (India)
en-IN-KavyaNeural|Kavya - English (India)
en-IN-KunalNeural|Kunal - English (India)
en-IN-NeerjaExpressiveNeural|Neerja - English (India) - Expressive
en-IN-NeerjaIndicNeural|NeerjaIndic - English (India)
en-IN-NeerjaNeural|Neerja - English (India)
en-IN-PrabhatIndicNeural|PrabhatIndic - English (India)
en-IN-PrabhatNeural|Prabhat - English (India)
en-IN-RehaanNeural|Rehaan - English (India)
en-IE-ConnorNeural|Connor - English (Ireland)
en-IE-EmilyNeural|Emily - English (Ireland)
en-KE-AsiliaNeural|Asilia - English (Kenya)
en-KE-ChilembaNeural|Chilemba - English (Kenya)
en-NZ-MitchellNeural|Mitchell - English (New Zealand)
en-NZ-MollyNeural|Molly - English (New Zealand)
en-NG-AbeoNeural|Abeo - English (Nigeria)
en-NG-EzinneNeural|Ezinne - English (Nigeria)
en-PH-JamesNeural|James - English (Philippines)
en-PH-RosaNeural|Rosa - English (Philippines)
en-SG-LunaNeural|Luna - English (Singapore)
en-SG-WayneNeural|Wayne - English (Singapore)
en-ZA-LeahNeural|Leah - English (South Africa)
en-ZA-LukeNeural|Luke - English (South Africa)
en-TZ-ElimuNeural|Elimu - English (Tanzania)
en-TZ-ImaniNeural|Imani - English (Tanzania)
en-GB-AbbiNeural|Abbi - English (United Kingdom)
en-GB-AlfieNeural|Alfie - English (United Kingdom)
en-GB-BellaNeural|Bella - English (United Kingdom)
en-GB-ElliotNeural|Elliot - English (United Kingdom)
en-GB-EthanNeural|Ethan - English (United Kingdom)
en-GB-HollieNeural|Hollie - English (United Kingdom)
en-GB-LibbyNeural|Libby - English (United Kingdom)
en-GB-MaisieNeural|Maisie - English (United Kingdom)
en-GB-MiaNeural|Mia - English (United Kingdom)
en-GB-NoahNeural|Noah - English (United Kingdom)
en-GB-OliverNeural|Oliver - English (United Kingdom)
en-GB-OliviaNeural|Olivia - English (United Kingdom)
en-GB-RyanNeural|Ryan - English (United Kingdom)
en-GB-SoniaNeural|Sonia - English (United Kingdom)
en-GB-ThomasNeural|Thomas - English (United Kingdom)
en-US-AmberNeural|Amber - English (United States)
en-US-AnaNeural|Ana - English (United States)
en-US-AndrewNeural|Andrew - English (United States)
en-US-AriaNeural|Aria - English (United States)
en-US-AshleyNeural|Ashley - English (United States)
en-US-AvaNeural|Ava - English (United States)
en-US-BrandonNeural|Brandon - English (United States)
en-US-BrianNeural|Brian - English (United States)
en-US-ChristopherNeural|Christopher - English (United States)
en-US-CoraNeural|Cora - English (United States)
en-US-DavisNeural|Davis - English (United States)
en-US-ElizabethNeural|Elizabeth - English (United States)
en-US-EmmaNeural|Emma - English (United States)
en-US-EricNeural|Eric - English (United States)
en-US-GuyNeural|Guy - English (United States)
en-US-JacobNeural|Jacob - English (United States)
en-US-JaneNeural|Jane - English (United States)
en-US-JasonNeural|Jason - English (United States)
en-US-JennyNeural|Jenny - English (United States)
en-US-KaiNeural|Kai - English (United States)
en-US-LunaNeural|Luna - English (United States)
en-US-MichelleNeural|Michelle - English (United States)
en-US-MonicaNeural|Monica - English (United States)
en-US-NancyNeural|Nancy - English (United States)
en-US-RogerNeural|Roger - English (United States)
en-US-SaraNeural|Sara - English (United States)
en-US-SteffanNeural|Steffan - English (United States)
en-US-TonyNeural|Tony - English (United States)
es-AR-ElenaNeural|Elena - Spanish (Argentina)
es-AR-TomasNeural|Tomas - Spanish (Argentina)
es-BO-MarceloNeural|Marcelo - Spanish (Bolivia)
es-BO-SofiaNeural|Sofia - Spanish (Bolivia)
es-CL-CatalinaNeural|Catalina - Spanish (Chile)
es-CL-LorenzoNeural|Lorenzo - Spanish (Chile)
es-CO-GonzaloNeural|Gonzalo - Spanish (Colombia)
es-CO-SalomeNeural|Salome - Spanish (Colombia)
es-ES-AbrilNeural|Abril - Spanish (Spain)
es-ES-AlvaroNeural|Alvaro - Spanish (Spain)
es-ES-ArnauNeural|Arnau - Spanish (Spain)
es-ES-DarioNeural|Dario - Spanish (Spain)
es-ES-EliasNeural|Elias - Spanish (Spain)
es-ES-ElviraNeural|Elvira - Spanish (Spain)
es-ES-EstrellaNeural|Estrella - Spanish (Spain)
es-ES-IreneNeural|Irene - Spanish (Spain)
es-ES-LaiaNeural|Laia - Spanish (Spain)
es-ES-LiaNeural|Lia - Spanish (Spain)
es-ES-NilNeural|Nil - Spanish (Spain)
es-ES-SaulNeural|Saul - Spanish (Spain)
es-ES-TeoNeural|Teo - Spanish (Spain)
es-ES-TrianaNeural|Triana - Spanish (Spain)
es-ES-VeraNeural|Vera - Spanish (Spain)
es-ES-XimenaNeural|Ximena - Spanish (Spain)
es-CR-JuanNeural|Juan - Spanish (Costa Rica)
es-CR-MariaNeural|Maria - Spanish (Costa Rica)
es-CU-BelkysNeural|Belkys - Spanish (Cuba)
es-CU-ManuelNeural|Manuel - Spanish (Cuba)
es-DO-EmilioNeural|Emilio - Spanish (Dominican Republic)
es-DO-RamonaNeural|Ramona - Spanish (Dominican Republic)
es-EC-AndreaNeural|Andrea - Spanish (Ecuador)
es-EC-LuisNeural|Luis - Spanish (Ecuador)
es-SV-LorenaNeural|Lorena - Spanish (El Salvador)
es-SV-RodrigoNeural|Rodrigo - Spanish (El Salvador)
es-GQ-JavierNeural|Javier - Spanish (Equatorial Guinea)
es-GQ-TeresaNeural|Teresa - Spanish (Equatorial Guinea)
es-GT-AndresNeural|Andres - Spanish (Guatemala)
es-GT-MartaNeural|Marta - Spanish (Guatemala)
es-HN-CarlosNeural|Carlos - Spanish (Honduras)
es-HN-KarlaNeural|Karla - Spanish (Honduras)
es-MX-BeatrizNeural|Beatriz - Spanish (Mexico)
es-MX-CandelaNeural|Candela - Spanish (Mexico)
es-MX-CarlotaNeural|Carlota - Spanish (Mexico)
es-MX-CecilioNeural|Cecilio - Spanish (Mexico)
es-MX-DaliaNeural|Dalia - Spanish (Mexico)
es-MX-GerardoNeural|Gerardo - Spanish (Mexico)
es-MX-JorgeNeural|Jorge - Spanish (Mexico)
es-MX-LarissaNeural|Larissa - Spanish (Mexico)
es-MX-LibertoNeural|Liberto - Spanish (Mexico)
es-MX-LucianoNeural|Luciano - Spanish (Mexico)
es-MX-MarinaNeural|Marina - Spanish (Mexico)
es-MX-NuriaNeural|Nuria - Spanish (Mexico)
es-MX-PelayoNeural|Pelayo - Spanish (Mexico)
es-MX-RenataNeural|Renata - Spanish (Mexico)
es-MX-YagoNeural|Yago - Spanish (Mexico)
es-NI-FedericoNeural|Federico - Spanish (Nicaragua)
es-NI-YolandaNeural|Yolanda - Spanish (Nicaragua)
es-PA-MargaritaNeural|Margarita - Spanish (Panama)
es-PA-RobertoNeural|Roberto - Spanish (Panama)
es-PY-MarioNeural|Mario - Spanish (Paraguay)
es-PY-TaniaNeural|Tania - Spanish (Paraguay)
es-PE-AlexNeural|Alex - Spanish (Peru)
es-PE-CamilaNeural|Camila - Spanish (Peru)
es-PR-KarinaNeural|Karina - Spanish (Puerto Rico)
es-PR-VictorNeural|Victor - Spanish (Puerto Rico)
es-US-AlonsoNeural|Alonso - Spanish (United States)
es-US-PalomaNeural|Paloma - Spanish (United States)
es-UY-MateoNeural|Mateo - Spanish (Uruguay)
es-UY-ValentinaNeural|Valentina - Spanish (Uruguay)
es-VE-PaolaNeural|Paola - Spanish (Venezuela)
es-VE-SebastianNeural|Sebastian - Spanish (Venezuela)
et-EE-AnuNeural|Anu - Estonian (Estonia)
et-EE-KertNeural|Kert - Estonian (Estonia)
eu-ES-AinhoaNeural|Ainhoa - Basque (Spain)
eu-ES-AnderNeural|Ander - Basque (Spain)
fa-IR-DilaraNeural|Dilara - Persian (Iran)
fa-IR-FaridNeural|Farid - Persian (Iran)
fi-FI-HarriNeural|Harri - Finnish (Finland)
fi-FI-NooraNeural|Noora - Finnish (Finland)
fi-FI-SelmaNeural|Selma - Finnish (Finland)
fil-PH-AngeloNeural|Angelo - Filipino (Philippines)
fil-PH-BlessicaNeural|Blessica - Filipino (Philippines)
fr-BE-CharlineNeural|Charline - French (Belgium)
fr-BE-GerardNeural|Gerard - French (Belgium)
fr-CA-ThierryNeural|Thierry - French (Canada)
fr-CA-AntoineNeural|Antoine - French (Canada)
fr-CA-JeanNeural|Jean - French (Canada)
fr-CA-SylvieNeural|Sylvie - French (Canada)
fr-FR-AlainNeural|Alain - French (France)
fr-FR-BrigitteNeural|Brigitte - French (France)
fr-FR-CelesteNeural|Celeste - French (France)
fr-FR-ClaudeNeural|Claude - French (France)
fr-FR-CoralieNeural|Coralie - French (France)
fr-FR-DeniseNeural|Denise - French (France)
fr-FR-EloiseNeural|Eloise - French (France)
fr-FR-HenriNeural|Henri - French (France)
fr-FR-JacquelineNeural|Jacqueline - French (France)
fr-FR-JeromeNeural|Jerome - French (France)
fr-FR-JosephineNeural|Josephine - French (France)
fr-FR-MauriceNeural|Maurice - French (France)
fr-FR-YvesNeural|Yves - French (France)
fr-FR-YvetteNeural|Yvette - French (France)
fr-CH-ArianeNeural|Ariane - French (Switzerland)
fr-CH-FabriceNeural|Fabrice - French (Switzerland)
ga-IE-ColmNeural|Colm - Irish (Ireland)
ga-IE-OrlaNeural|Orla - Irish (Ireland)
gl-ES-RoiNeural|Roi - Galician (Spain)
gl-ES-SabelaNeural|Sabela - Galician (Spain)
gu-IN-DhwaniNeural|Dhwani - Gujarati (India)
gu-IN-NiranjanNeural|Niranjan - Gujarati (India)
he-IL-AvriNeural|Avri - Hebrew (Israel)
he-IL-HilaNeural|Hila - Hebrew (Israel)
hi-IN-AaravNeural|Aarav - Hindi (India)
hi-IN-AartiNeural|Aarti - Hindi (India)
hi-IN-AashiNeural|Aashi - Hindi (India)
hi-IN-AnanyaNeural|Ananya - Hindi (India)
hi-IN-ArjunNeural|Arjun - Hindi (India)
hi-IN-KavyaNeural|Kavya - Hindi (India)
hi-IN-KunalNeural|Kunal - Hindi (India)
hi-IN-MadhurNeural|Madhur - Hindi (India)
hi-IN-RehaanNeural|Rehaan - Hindi (India)
hi-IN-SwaraNeural|Swara - Hindi (India)
hr-HR-GabrijelaNeural|Gabrijela - Croatian (Croatia)
hr-HR-SreckoNeural|Srecko - Croatian (Croatia)
hu-HU-NoemiNeural|Noemi - Hungarian (Hungary)
hu-HU-TamasNeural|Tamas - Hungarian (Hungary)
id-ID-ArdiNeural|Ardi - Indonesian (Indonesia)
id-ID-GadisNeural|Gadis - Indonesian (Indonesia)
is-IS-GudrunNeural|Gudrun - Icelandic (Iceland)
is-IS-GunnarNeural|Gunnar - Icelandic (Iceland)
it-IT-BenignoNeural|Benigno - Italian (Italy)
it-IT-CalimeroNeural|Calimero - Italian (Italy)
it-IT-CataldoNeural|Cataldo - Italian (Italy)
it-IT-CosimoNeural|Cosimo - Italian (Italy)
it-IT-DiegoNeural|Diego - Italian (Italy)
it-IT-ElsaNeural|Elsa - Italian (Italy)
it-IT-FabiolaNeural|Fabiola - Italian (Italy)
it-IT-ImeldaNeural|Imelda - Italian (Italy)
it-IT-IrmaNeural|Irma - Italian (Italy)
it-IT-IsabellaNeural|Isabella - Italian (Italy)
it-IT-LisandroNeural|Lisandro - Italian (Italy)
it-IT-MarcelloNeural|Marcello - Italian (Italy)
it-IT-PierinaNeural|Pierina - Italian (Italy)
it-IT-RiccardoNeural|Riccardo - Italian (Italy)
it-IT-SilvanoNeural|Silvano - Italian (Italy)
iu-Latn-CA-SiqiniqNeural|Siqiniq - Inuktitut (Canada) - Latin
iu-Latn-CA-TaqqiqNeural|Taqqiq - Inuktitut (Canada) - Latin
iu-Cans-CA-SiqiniqNeural|Siqiniq - Inuktitut (Canada) - Syllabics
iu-Cans-CA-TaqqiqNeural|Taqqiq - Inuktitut (Canada) - Syllabics
ja-JP-KeitaNeural|Keita - Japanese (Japan)
ja-JP-MasaruNeural|Masaru - Japanese (Japan)
ja-JP-MayuNeural|Mayu - Japanese (Japan)
ja-JP-NanamiNeural|Nanami - Japanese (Japan)
ja-JP-RisaNeural|Risa - Japanese (Japan)
ja-JP-ShioriNeural|Shiori - Japanese (Japan)
jv-ID-DimasNeural|Dimas - Javanese (Indonesia)
jv-ID-SitiNeural|Siti - Javanese (Indonesia)
ka-GE-EkaNeural|Eka - Georgian (Georgia)
ka-GE-GiorgiNeural|Giorgi - Georgian (Georgia)
kk-KZ-AigulNeural|Aigul - Kazakh (Kazakhstan)
kk-KZ-DauletNeural|Daulet - Kazakh (Kazakhstan)
km-KH-PisethNeural|Piseth - Khmer (Cambodia)
km-KH-SreymomNeural|Sreymom - Khmer (Cambodia)
kn-IN-GaganNeural|Gagan - Kannada (India)
kn-IN-SapnaNeural|Sapna - Kannada (India)
ko-KR-BongJinNeural|BongJin - Korean (Korea)
ko-KR-GookMinNeural|GookMin - Korean (Korea)
ko-KR-InJoonNeural|InJoon - Korean (Korea)
ko-KR-JiMinNeural|JiMin - Korean (Korea)
ko-KR-SeungHwanNeural|SeungHwan - Korean (Korea)
ko-KR-SunHiNeural|SunHi - Korean (Korea)
lo-LA-ChanthavongNeural|Chanthavong - Lao (Laos)
lo-LA-KeomanyNeural|Keomany - Lao (Laos)
lt-LT-LeonaNeural|Leona - Lithuanian (Lithuania)
lt-LT-LeonasNeural|Leonas - Lithuanian (Lithuania)
lt-LT-OnaNeural|Ona - Lithuanian (Lithuania)
lv-LV-EveritaNeural|Everita - Latvian (Latvia)
lv-LV-NilsNeural|Nils - Latvian (Latvia)
mk-MK-AleksandarNeural|Aleksandar - Macedonian (North Macedonia)
mk-MK-MarijaNeural|Marija - Macedonian (North Macedonia)
ml-IN-MidhunNeural|Midhun - Malayalam (India)
ml-IN-SobhanaNeural|Sobhana - Malayalam (India)
mn-MN-BataaNeural|Bataa - Mongolian (Mongolia)
mn-MN-YesuiNeural|Yesui - Mongolian (Mongolia)
mr-IN-AarohiNeural|Aarohi - Marathi (India)
mr-IN-ManoharNeural|Manohar - Marathi (India)
ms-MY-OsmanNeural|Osman - Malay (Malaysia)
ms-MY-YasminNeural|Yasmin - Malay (Malaysia)
mt-MT-GraceNeural|Grace - Maltese (Malta)
mt-MT-JosephNeural|Joseph - Maltese (Malta)
my-MM-NilarNeural|Nilar - Burmese (Myanmar)
my-MM-ThihaNeural|Thiha - Burmese (Myanmar)
nb-NO-FinnNeural|Finn - Norwegian Bokmål (Norway)
nb-NO-PernilleNeural|Pernille - Norwegian Bokmål (Norway)
ne-NP-HemkalaNeural|Hemkala - Nepali (Nepal)
ne-NP-SagarNeural|Sagar - Nepali (Nepal)
nl-BE-ArnaudNeural|Arnaud - Dutch (Belgium)
nl-BE-DenaNeural|Dena - Dutch (Belgium)
nl-NL-ColetteNeural|Colette - Dutch (Netherlands)
nl-NL-FennaNeural|Fenna - Dutch (Netherlands)
nl-NL-MaartenNeural|Maarten - Dutch (Netherlands)
pl-PL-AgnieszkaNeural|Agnieszka - Polish (Poland)
pl-PL-MarekNeural|Marek - Polish (Poland)
pl-PL-ZofiaNeural|Zofia - Polish (Poland)
ps-AF-GulNawazNeural|Gul Nawaz - Pashto (Afghanistan)
ps-AF-LatifaNeural|Latifa - Pashto (Afghanistan)
pt-BR-AntonioNeural|Antonio - Portuguese (Brazil)
pt-BR-BrendaNeural|Brenda - Portuguese (Brazil)
pt-BR-FabioNeural|Fabio - Portuguese (Brazil)
pt-BR-FranciscaNeural|Francisca - Portuguese (Brazil)
pt-BR-ThalitaNeural|Thalita - Portuguese (Brazil)
pt-PT-DuarteNeural|Duarte - Portuguese (Portugal)
pt-PT-RaquelNeural|Raquel - Portuguese (Portugal)
ro-RO-AlinaNeural|Alina - Romanian (Romania)
ro-RO-EmilNeural|Emil - Romanian (Romania)
ru-RU-DmitryNeural|Dmitry - Russian (Russia)
ru-RU-SvetlanaNeural|Svetlana - Russian (Russia)
si-LK-SameeraNeural|Sameera - Sinhala (Sri Lanka)
si-LK-ThiliniNeural|Thilini - Sinhala (Sri Lanka)
sk-SK-LukasNeural|Lukas - Slovak (Slovakia)
sk-SK-ViktoriaNeural|Viktoria - Slovak (Slovakia)
sl-SI-PetraNeural|Petra - Slovenian (Slovenia)
sl-SI-RokNeural|Rok - Slovenian (Slovenia)
so-SO-MuuseNeural|Muuse - Somali (Somalia)
so-SO-UbaxNeural|Ubax - Somali (Somalia)
sq-AL-AnilaNeural|Anila - Albanian (Albania)
sq-AL-IlirNeural|Ilir - Albanian (Albania)
sr-RS-NicholasNeural|Nicholas - Serbian (Serbia)
sr-RS-SophieNeural|Sophie - Serbian (Serbia)
su-ID-JajangNeural|Jajang - Sundanese (Indonesia)
su-ID-TutiNeural|Tuti - Sundanese (Indonesia)
sv-SE-MattiasNeural|Mattias - Swedish (Sweden)
sv-SE-SofieNeural|Sofie - Swedish (Sweden)
sw-KE-RafikiNeural|Rafiki - Swahili (Kenya)
sw-KE-ZuriNeural|Zuri - Swahili (Kenya)
sw-TZ-DaudiNeural|Daudi - Swahili (Tanzania)
sw-TZ-RehemaNeural|Rehema - Swahili (Tanzania)
ta-IN-PallaviNeural|Pallavi - Tamil (India)
ta-IN-ValluvarNeural|Valluvar - Tamil (India)
ta-MY-KaniNeural|Kani - Tamil (Malaysia)
ta-MY-SuryaNeural|Surya - Tamil (Malaysia)
ta-SG-AnbuNeural|Anbu - Tamil (Singapore)
ta-SG-VenbaNeural|Venba - Tamil (Singapore)
ta-LK-KumarNeural|Kumar - Tamil (Sri Lanka)
ta-LK-SaranyaNeural|Saranya - Tamil (Sri Lanka)
te-IN-MohanNeural|Mohan - Telugu (India)
te-IN-ShrutiNeural|Shruti - Telugu (India)
th-TH-NiwatNeural|Niwat - Thai (Thailand)
th-TH-PremwadeeNeural|Premwadee - Thai (Thailand)
tr-TR-AhmetNeural|Ahmet - Turkish (Turkey)
tr-TR-EmelNeural|Emel - Turkish (Turkey)
uk-UA-OstapNeural|Ostap - Ukrainian (Ukraine)
uk-UA-PolinaNeural|Polina - Ukrainian (Ukraine)
ur-IN-GulNeural|Gul - Urdu (India)
ur-IN-SalmanNeural|Salman - Urdu (India)
ur-PK-AsadNeural|Asad - Urdu (Pakistan)
ur-PK-UzmaNeural|Uzma - Urdu (Pakistan)
uz-UZ-MadinaNeural|Madina - Uzbek (Uzbekistan)
uz-UZ-SardorNeural|Sardor - Uzbek (Uzbekistan)
vi-VN-HoaiMyNeural|HoaiMy - Vietnamese (Vietnam)
vi-VN-NamMinhNeural|NamMinh - Vietnamese (Vietnam)
zh-CN-XiaochenNeural|Xiaochen - Chinese (Mandarin, Simplified)
zh-CN-XiaoxiaoNeural|Xiaoxiao - Chinese (Mandarin, Simplified)
zh-CN-XiaoyiNeural|Xiaoyi - Chinese (Mandarin, Simplified)
zh-CN-XiaoyuNeural|Xiaoyu - Chinese (Mandarin, Simplified)
zh-CN-YunjianNeural|Yunjian - Chinese (Mandarin, Simplified)
zh-CN-YunxiNeural|Yunxi - Chinese (Mandarin, Simplified)
zh-CN-YunxiaNeural|Yunxia - Chinese (Mandarin, Simplified)
zh-CN-YunyangNeural|Yunyang - Chinese (Mandarin, Simplified)
zh-CN-liaoning-XiaobeiNeural|Xiaobei - Chinese (Northeastern Mandarin, Simplified)
zh-HK-HiuGaaiNeural|Hiu Gaai - Chinese (Cantonese, Hong Kong)
zh-HK-HiuMaanNeural|Hiu Maan - Chinese (Cantonese, Hong Kong)
zh-HK-WanLungNeural|Wan Lung - Chinese (Cantonese, Hong Kong)
zh-TW-HsiaoChenNeural|HsiaoChen - Chinese (Taiwanese Mandarin)
zh-TW-HsiaoYuNeural|HsiaoYu - Chinese (Taiwanese Mandarin)
zh-TW-YunJheNeural|YunJhe - Chinese (Taiwanese Mandarin)
zh-CN-shaanxi-XiaoniNeural|Xiaoni - Chinese (Shaanxi Mandarin, Simplified)
zh-CN-liaoning-XiaobeiNeural|Xiaobei - Chinese (Northeastern Mandarin, Simplified)
zu-ZA-ThandoNeural|Thando - Zulu (South Africa)
zu-ZA-ThembaNeural|Themba - Zulu (South Africa)
"""

VOICE_MAPPING = {k:v for k,v in (line.split("|",1) for line in VOICE_LINES.splitlines() if line.strip())}
VOICE_MAPPING.update(MULTILINGUAL_VOICES)

TTS_VOICES_BY_LANGUAGE = {}
for vid, display in VOICE_MAPPING.items():
    parts = display.split(" - ",1)
    if len(parts) < 2:
        lang = "Other"
    else:
        after = parts[1]
        lang = after.split("(")[0].strip().split(" - ")[0].strip()
    TTS_VOICES_BY_LANGUAGE.setdefault(lang, []).append(vid)

multilingual_en_voices = [k for k,v in MULTILINGUAL_VOICES.items() if "English" in v]
if "English" in TTS_VOICES_BY_LANGUAGE:
    for k in multilingual_en_voices:
        if k not in TTS_VOICES_BY_LANGUAGE["English"]:
            TTS_VOICES_BY_LANGUAGE["English"].append(k)

MOST_USED = ["English","Chinese","Spanish","Arabic","Portuguese","Indonesian","French","Russian","Japanese","German","Vietnamese","Turkish","Korean","Italian","Polish","Dutch","Persian","Hindi","Urdu","Bengali","Filipino","Malay","Thai","Romanian","Ukrainian"]
ORDERED_TTS_LANGUAGES = [l for l in MOST_USED if l in TTS_VOICES_BY_LANGUAGE] + sorted([l for l in TTS_VOICES_BY_LANGUAGE.keys() if l not in MOST_USED])

def update_user_activity(user_id:int):
    users_collection.update_one({"_id":str(user_id)}, {"$set":{"last_active":datetime.now().isoformat()}, "$setOnInsert":{"_id":str(user_id),"tts_conversion_count":0}}, upsert=True)

def increment_processing_count(user_id):
    users_collection.update_one({"_id":str(user_id)}, {"$inc":{"tts_conversion_count":1}, "$set":{"last_active":datetime.now().isoformat()}}, upsert=True)

def get_tts_user_voice(user_id):
    s = tts_settings_collection.find_one({"_id":str(user_id)})
    return s.get("voice","en-US-PhoebeMultilingualNeural") if s else "en-US-PhoebeMultilingualNeural"

def set_tts_user_voice(user_id, voice):
    tts_settings_collection.update_one({"_id":str(user_id)}, {"$set":{"voice":voice}}, upsert=True)

def get_tts_user_pitch(user_id):
    s = tts_settings_collection.find_one({"_id":str(user_id)})
    return s.get("pitch",0) if s else 0

def set_tts_user_pitch(user_id, pitch):
    tts_settings_collection.update_one({"_id":str(user_id)}, {"$set":{"pitch":pitch}}, upsert=True)

def get_tts_user_rate(user_id):
    s = tts_settings_collection.find_one({"_id":str(user_id)})
    return s.get("rate",0) if s else 0

def set_tts_user_rate(user_id, rate):
    tts_settings_collection.update_one({"_id":str(user_id)}, {"$set":{"rate":rate}}, upsert=True)

def keep_recording(chat_id, stop_event, target_bot):
    while not stop_event.is_set():
        try:
            target_bot.send_chat_action(chat_id, 'record_audio'); time.sleep(4)
        except Exception:
            break

def check_subscription(user_id:int)->bool:
    if not REQUIRED_CHANNEL or not REQUIRED_CHANNEL.strip(): return True
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member','administrator','creator']
    except telebot.apihelper.ApiTelegramException:
        return False

def send_subscription_message(chat_id:int):
    if not REQUIRED_CHANNEL or not REQUIRED_CHANNEL.strip(): return
    try:
        chat = bot.get_chat(chat_id)
        if chat.type != 'private': return
    except Exception:
        return
    try:
        m = InlineKeyboardMarkup(); m.add(InlineKeyboardButton("Click here to join the group", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"))
        bot.send_message(chat_id, "🔒 Access Locked You cannot use this bot until you join the group.", reply_markup=m)
    except Exception:
        pass

def make_language_selection_keyboard():
    m=InlineKeyboardMarkup(row_width=3); m.add(InlineKeyboardButton("Multilingual", callback_data="tts_multilingual"))
    buttons=[InlineKeyboardButton(lang, callback_data=f"tts_lang|{lang}") for lang in ORDERED_TTS_LANGUAGES if lang in TTS_VOICES_BY_LANGUAGE]
    for i in range(0,len(buttons),3): m.add(*buttons[i:i+3])
    return m

def make_tts_multilingual_keyboard():
    m=InlineKeyboardMarkup(row_width=1)
    for vid,display in MULTILINGUAL_VOICES.items():
        if "Steffan" in vid: continue
        m.add(InlineKeyboardButton(display, callback_data=f"tts_voice|{vid}"))
    steffan_id="en-US-SteffanMultilingualNeural"; steffan_display=MULTILINGUAL_VOICES.get(steffan_id, "Steffan - Multilingual (United States)")
    m.add(InlineKeyboardButton(steffan_display, callback_data=f"tts_voice|{steffan_id}")); m.add(InlineKeyboardButton("⬅️ Back", callback_data="tts_back_to_languages"))
    return m

def make_tts_voice_keyboard_for_language(lang_name:str):
    m=InlineKeyboardMarkup(row_width=2)
    for voice in TTS_VOICES_BY_LANGUAGE.get(lang_name,[]):
        m.add(InlineKeyboardButton(VOICE_MAPPING.get(voice,voice), callback_data=f"tts_voice|{voice}"))
    m.add(InlineKeyboardButton("⬅️ Back", callback_data="tts_back_to_languages"))
    return m

def make_pitch_keyboard():
    m=InlineKeyboardMarkup(row_width=2); m.add(InlineKeyboardButton("⬆️ High", callback_data="pitch_set|+50"), InlineKeyboardButton("⬇️ Lower", callback_data="pitch_set|-50"), InlineKeyboardButton("🔄 Reset", callback_data="pitch_set|0")); return m

def make_rate_keyboard():
    m=InlineKeyboardMarkup(row_width=2); m.add(InlineKeyboardButton("⚡️ Speed", callback_data="rate_set|+50"), InlineKeyboardButton("🐢 Slow down", callback_data="rate_set|-50"), InlineKeyboardButton("🔄 Reset", callback_data="rate_set|0")); return m

def reset_user_modes(uid):
    user_tts_mode[uid]=None; user_pitch_input_mode[uid]=None; user_rate_input_mode[uid]=None

def handle_rate_command(message):
    cid=message.chat.id; uid=str(message.from_user.id)
    reset_user_modes(uid); user_rate_input_mode[uid]="awaiting_rate_input"
    bot.send_message(cid, "How fast or slow should I speak? Choose one or send a number from -100 (slow) to +100 (fast), 0 is normal:", reply_markup=make_rate_keyboard())

@bot.message_handler(commands=['start'])
def start_handler(message):
    uid=str(message.from_user.id); update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    reset_user_modes(uid)
    bot.send_message(message.chat.id, "Choose Multilingual or a language:", reply_markup=make_language_selection_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_handler(message):
    update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    reset_user_modes(str(message.from_user.id))
    bot.send_message(message.chat.id, "Need help? Contact: @lakigithub", parse_mode="Markdown")

@bot.message_handler(commands=['privacy'])
def privacy_notice_handler(message):
    update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    reset_user_modes(str(message.from_user.id))
    bot.send_message(message.chat.id, "Not available ❌", parse_mode="Markdown")

@bot.callback_query_handler(lambda c: c.data == "tts_multilingual")
def on_tts_multilingual_select(call):
    uid=str(call.from_user.id); update_user_activity(call.from_user.id)
    if call.message.chat.type=='private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id); bot.answer_callback_query(call.id); return
    user_pitch_input_mode[uid]=None; user_rate_input_mode[uid]=None
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Okay! Now choose a specific voice from Multilingual. 👇", reply_markup=make_tts_multilingual_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(lambda c: c.data.startswith("tts_lang|"))
def on_tts_language_select(call):
    uid=str(call.from_user.id); update_user_activity(call.from_user.id)
    if call.message.chat.type=='private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id); bot.answer_callback_query(call.id); return
    user_pitch_input_mode[uid]=None; user_rate_input_mode[uid]=None
    _,lang=call.data.split("|",1)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Okay! Now choose a specific *voice* from {lang}. 👇", reply_markup=make_tts_voice_keyboard_for_language(lang), parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(lambda c: c.data.startswith("tts_voice|"))
def on_tts_voice_change(call):
    uid=str(call.from_user.id); update_user_activity(call.from_user.id)
    if call.message.chat.type=='private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id); bot.answer_callback_query(call.id); return
    user_pitch_input_mode[uid]=None; user_rate_input_mode[uid]=None
    _,voice = call.data.split("|",1); set_tts_user_voice(uid, voice); user_tts_mode[uid]=voice
    voice_display_name = VOICE_MAPPING.get(voice, voice)
    bot.answer_callback_query(call.id, f"✔️ You are using: {voice_display_name}", show_alert=False)
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception as e: logging.error(f"Failed to delete message after voice selection: {e}")

@bot.callback_query_handler(lambda c: c.data == "tts_back_to_languages")
def on_tts_back_to_languages(call):
    uid=str(call.from_user.id); update_user_activity(call.from_user.id)
    if call.message.chat.type=='private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id); bot.answer_callback_query(call.id); return
    reset_user_modes(uid)
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Choose Multilingual or a language:", reply_markup=make_language_selection_keyboard(), parse_mode="Markdown")
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['rate'])
def cmd_voice_rate(message):
    update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    handle_rate_command(message)

@bot.callback_query_handler(lambda c: c.data.startswith("rate_set|"))
def on_rate_set_callback(call):
    uid=str(call.from_user.id); update_user_activity(call.from_user.id)
    if call.message.chat.type=='private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id); bot.answer_callback_query(call.id); return
    user_rate_input_mode[uid]=None
    try:
        _,sv=call.data.split("|",1); rv=int(sv); set_tts_user_rate(uid, rv)
        bot.answer_callback_query(call.id, f"✔️ Speech rate is {rv}!", show_alert=False)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e: logging.error(f"Failed to delete message after rate selection: {e}")
    except Exception:
        bot.answer_callback_query(call.id, "Invalid rate.")

@bot.message_handler(commands=['pitch'])
def cmd_voice_pitch(message):
    update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    uid=str(message.from_user.id); reset_user_modes(uid); user_pitch_input_mode[uid]="awaiting_pitch_input"
    bot.send_message(message.chat.id, "Let's adjust the pitch! Choose one or send a number from -100 (low) to +100 (high), 0 is normal:", reply_markup=make_pitch_keyboard())

@bot.callback_query_handler(lambda c: c.data.startswith("pitch_set|"))
def on_pitch_set_callback(call):
    uid=str(call.from_user.id); update_user_activity(call.from_user.id)
    if call.message.chat.type=='private' and not check_subscription(call.from_user.id):
        send_subscription_message(call.message.chat.id); bot.answer_callback_query(call.id); return
    user_pitch_input_mode[uid]=None
    try:
        _,pv=call.data.split("|",1); pv=int(pv); set_tts_user_pitch(uid,pv)
        bot.answer_callback_query(call.id, f"✔️ The pitch is {pv}!", show_alert=False)
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e: logging.error(f"Failed to delete message after pitch selection: {e}")
    except Exception:
        bot.answer_callback_query(call.id, "Invalid pitch.")

async def synth_and_send_tts(chat_id:int, user_id:str, text:str, reply_to_message_id:int=None):
    voice=get_tts_user_voice(user_id)
    # Get chat type to check if it's a private chat
    try:
        chat = bot.get_chat(chat_id)
        is_private_chat = chat.type == 'private'
    except Exception:
        is_private_chat = False # Assume it's not a private chat if we can't get the info

    if voice.startswith("so-"): text=text.replace('.',',')
    pitch_val=get_tts_user_pitch(user_id); rate_val=get_tts_user_rate(user_id)
    digits="".join(str(random.randint(0,9)) for _ in range(random.randint(6,8)))
    voice_display_name = VOICE_MAPPING.get(voice, voice)
    safe_name = re.sub(r"[^\w\-]", "_", voice_display_name)
    filename = f"{safe_name}_{digits}.mp3"
    stop_recording=threading.Event()
    rthread=threading.Thread(target=keep_recording, args=(chat_id, stop_recording, bot)); rthread.daemon=True; rthread.start()
    try:
        pitch = f"+{pitch_val}Hz" if pitch_val>=0 else f"{pitch_val}Hz"
        rate = f"+{rate_val}%" if rate_val>=0 else f"{rate_val}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(filename)
        if not os.path.exists(filename) or os.path.getsize(filename)==0:
            if is_private_chat: # Only send error message in private chat
                bot.send_message(chat_id, "❌ Failed to create the audio. The text may be invalid. Please try a different text."); 
            return
        caption_text = ("🎧 Here is your voice\n\n" f"Voice: *{voice_display_name}*\n" f"Pitch: *{pitch}*\n" f"Rate: *{rate}*\n\n" "Bot Supports Commands:\n" "/start - Change the voice actor\n" "/rate - Change voice speed\n" "/pitch - Change voice pitch\n\n" "Save to your phone 💗")
        with open(filename,"rb") as f:
            try:
                bot.send_audio(chat_id, f, caption=caption_text, parse_mode="Markdown", reply_to_message_id=reply_to_message_id)
            except Exception:
                bot.send_audio(chat_id, f)
        increment_processing_count(user_id)
    except Exception as e:
        logging.exception("TTS error")
        if is_private_chat: # Only send error message in private chat
            bot.send_message(chat_id, "😞 there was a problem with this bot server, so I can’t generate audio right now. Please keep using this bot, https://t.me/msspeechbot for the time being.")
    finally:
        stop_recording.set()
        if os.path.exists(filename):
            try: os.remove(filename)
            except Exception: pass

@bot.message_handler(content_types=['text'])
def handle_text_for_tts_or_mode_input(message):
    uid=str(message.from_user.id); update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    if message.text.startswith('/'): return
    if user_rate_input_mode.get(uid)=="awaiting_rate_input":
        if message.reply_to_message and message.reply_to_message.from_user.id==bot.get_me().id:
            try: bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            except Exception: pass
        try:
            rv=int(message.text)
            if -100<=rv<=100:
                set_tts_user_rate(uid, rv); bot.send_message(message.chat.id, f"🔊 The speech rate is *{rv}*.", parse_mode="Markdown"); user_rate_input_mode[uid]=None
            else:
                bot.send_message(message.chat.id, "❌ Invalid rate. Send a number from -100 to +100 or 0. Try again:")
        except ValueError:
            bot.send_message(message.chat.id, "That is not a valid number. Send a number from -100 to +100 or 0. Try again:")
        return
    if user_pitch_input_mode.get(uid)=="awaiting_pitch_input":
        if message.reply_to_message and message.reply_to_message.from_user.id==bot.get_me().id:
            try: bot.delete_message(message.chat.id, message.reply_to_message.message_id)
            except Exception: pass
        try:
            pv=int(message.text)
            if -100<=pv<=100:
                set_tts_user_pitch(uid,pv); bot.send_message(message.chat.id, f"🔊 The pitch is *{pv}*.", parse_mode="Markdown"); user_pitch_input_mode[uid]=None
            else:
                bot.send_message(message.chat.id, "❌ Invalid pitch. Send a number from -100 to +100 or 0. Try again:")
        except ValueError:
            bot.send_message(message.chat.id, "That is not a valid number. Send a number from -100 to +100 or 0. Try again:")
        return
    threading.Thread(target=lambda: asyncio.run(synth_and_send_tts(message.chat.id, uid, message.text, message.message_id))).start()

@bot.message_handler(content_types=['voice','audio','video','document','sticker','photo'])
def handle_unsupported_media_types(message):
    uid=str(message.from_user.id); update_user_activity(message.from_user.id)
    if message.chat.type=='private' and not check_subscription(message.from_user.id):
        send_subscription_message(message.chat.id); return
    reset_user_modes(uid)
    if message.chat.type == 'private': # Only send error message in private chat
        bot.send_message(message.chat.id, "For Audio to Text use: @MediaToTextBot")

@app.route("/", methods=["GET","POST","HEAD"])
def webhook():
    if request.method in ("GET","HEAD"): return "OK", 200
    if request.method=="POST":
        ct=request.headers.get("Content-Type","")
        if ct and ct.startswith("application/json"):
            update = telebot.types.Update.de_json(request.get_data().decode("utf-8"))
            bot.process_new_updates([update]); return "", 200
    return abort(403)

@app.route("/set_webhook", methods=["GET","POST"])
def set_webhook_route():
    try:
        bot.set_webhook(url=WEBHOOK_URL); return f"Webhook set to {WEBHOOK_URL}", 200
    except Exception as e:
        logging.error(f"Failed to set webhook: {e}"); return f"Failed to set webhook: {e}", 500

@app.route("/delete_webhook", methods=["GET","POST"])
def delete_webhook_route():
    try:
        bot.delete_webhook(); return "Webhook deleted.", 200
    except Exception as e:
        logging.error(f"Failed to delete webhook: {e}"); return f"Failed to delete webhook: {e}", 500

def set_webhook_on_startup():
    try:
        bot.delete_webhook(); time.sleep(1); bot.set_webhook(url=WEBHOOK_URL); logging.info(f"Main bot webhook set successfully to {WEBHOOK_URL}")
    except Exception as e:
        logging.error(f"Failed to set main bot webhook on startup: {e}")

def set_bot_info_and_startup():
    set_webhook_on_startup()

if __name__ == "__main__":
    set_bot_info_and_startup()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
