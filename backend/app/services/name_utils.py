"""Name helpers — splitting, composing, sanitising, and addressing a member.

`full_name` stays the single source of truth for display: it is used in 20+
places across the codebase (emails, chat, DMs, the team dashboard, admin), so
splitting the signup form into two inputs must NOT remove it. Instead the two
new columns feed it — full_name is always recomposed from first + last.

The Arabic-name resolution below (`_AR_FIRST_NAMES`, `arabize_first_name`,
`arabic_first_name`) lived in `email_service.py` until 2026-09-04. It MOVED
here — it was not copied — because announcements needs it too, and two
implementations of "what do we call this member" would drift the moment one
side added a name to its map. `email_service` re-exports what it used to own,
so nothing about the live email path changed on the day of the move.

Nothing here reads or writes the database. Resolution happens in memory, at
send time, from whatever `full_name` already holds — being addressed by name
never alters a stored one.
"""
import re
import unicodedata


def split_full_name(full_name: str | None) -> tuple[str, str]:
    """Split a display name into (first, last).

    Where the first name ends is `first_name_token`'s call, not this function's
    — compound names are two words. Splitting on the first space unconditionally
    is what stored `عبد الله محمد` as first name `عبد`, and every Google signup
    is named by this function.

    "محمد أحمد علي"  -> ("محمد", "أحمد علي")
    "عبد الرحمن علي" -> ("عبد الرحمن", "علي")
    "Mohamed"        -> ("Mohamed", "")
    """
    clean = " ".join((full_name or "").split())
    if not clean:
        return "", ""
    first = first_name_token(clean)
    return first, clean[len(first):].strip()


def compose_full_name(first_name: str | None, last_name: str | None) -> str:
    """Build the display name the rest of the app reads.

    Sanitizes as it composes: every path that sets a name goes through here, so
    this is the one place that has to be right.
    """
    joined = f"{(first_name or '').strip()} {(last_name or '').strip()}".strip()
    return clean_display_name(joined)

# Characters a spreadsheet reads as the start of a formula. A name is exported
# to CSV by the admin payments report, so one beginning with any of these is
# code in the admin's spreadsheet rather than text. See also the escaping in
# routers/admin.py — this stops it being stored, that stops it being emitted.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Everything below U+0020 plus the C1 range and the bidi/zero-width tricks.
# None of these belong in a display name, and several of them exist purely to
# make one string look like another.
_CONTROL_CHARS = dict.fromkeys(
    list(range(0x00, 0x20)) + [0x7F]
    + list(range(0x80, 0xA0))
    + [0x200B, 0x200C, 0x200D, 0x200E, 0x200F,
       0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
       0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF]
)


def clean_display_name(value: str | None, limit: int = 80) -> str:
    """Make a client-supplied name safe to store and cheap to render.

    Display names reach innerHTML on pages all over the site (notification
    bodies, DM previews, member lists, the admin payments queue) and a CSV in
    the admin's spreadsheet. Registration used to store them raw — the only
    check was len >= 2 — while PUT /profile/me already stripped markup, so
    signing up was simply the unguarded door into the same field.

    The rendering side escapes now, which is the real fix; this means a single
    missed escape anywhere is no longer a working payload. Angle brackets go,
    because they are what turns text into markup and no name needs them.
    Apostrophes stay: "Mu'men" and "MOH'D" are real members' names.
    """
    cleaned = (value or "").translate(_CONTROL_CHARS).replace("<", "").replace(">", "")
    cleaned = " ".join(cleaned.split())
    while cleaned[:1] in FORMULA_PREFIXES:
        cleaned = cleaned[1:].lstrip()
    return cleaned[:limit]


# ───────────────────────────────────────────────────────
#  تعريب الأسماء الأولى — الغالبية العظمى من الأعضاء مسجّلين
#  باسم لاتيني (Mohamed / Ahmed / Omar ...). عشان الإيميلات
#  تبان عربي فعلاً (مش "Mohamed" وسط نص عربي)، بنترجم أشهر
#  الأسماء لصيغتها العربية. أي اسم مش معروف بيرجع None (بيرجع
#  المنادي للـ fallback).
# ───────────────────────────────────────────────────────

_AR_FIRST_NAMES = {
    # محمد وتنويعاته
    "mohamed": "محمد", "mohammed": "محمد", "mohamad": "محمد", "mohammad": "محمد",
    "muhammad": "محمد", "muhamed": "محمد", "mohammd": "محمد", "mhmd": "محمد",
    "mohab": "محمد", "med": "محمد", "moh": "محمد",
    # أحمد
    "ahmed": "أحمد", "ahmad": "أحمد", "ahmd": "أحمد",
    # محمود
    "mahmoud": "محمود", "mahmood": "محمود", "mahmoed": "محمود", "mahmud": "محمود",
    # مصطفى
    "mostafa": "مصطفى", "mustafa": "مصطفى", "moustafa": "مصطفى", "moustapha": "مصطفى",
    "mostapha": "مصطفى",
    # عمر / عمرو
    "omar": "عمر", "omer": "عمر", "umar": "عمر",
    "amr": "عمرو", "amro": "عمرو",
    # يوسف
    "youssef": "يوسف", "yousef": "يوسف", "yusuf": "يوسف", "yosef": "يوسف",
    "yousief": "يوسف", "youseff": "يوسف", "yousuf": "يوسف", "yosuf": "يوسف",
    "youssuf": "يوسف",
    # عبد الرحمن / عبد الله / عبد العزيز / عبد المجيد
    "abdelrahman": "عبد الرحمن", "abdulrahman": "عبد الرحمن", "abdurrahman": "عبد الرحمن",
    "abdelrhman": "عبد الرحمن", "abdalrahman": "عبد الرحمن", "abdorahman": "عبد الرحمن",
    "abdallah": "عبد الله", "abdullah": "عبد الله", "abdalla": "عبد الله",
    "abdulla": "عبد الله", "abdellah": "عبد الله",
    "abdelaziz": "عبد العزيز", "abdulaziz": "عبد العزيز", "abdualaziz": "عبد العزيز",
    "abdulmajeed": "عبد المجيد", "abdulmajid": "عبد المجيد",
    "abdelfattah": "عبد الفتاح", "abdo": "عبده", "abdu": "عبده", "abdel": "عبد الرحمن",
    # باقي أسماء «عبد الـ» و«الله» و«الدين». مالهمش تهجئة لاتينية كتير في
    # الروستر، بس مكانهم هنا مش في ليستة جنبية: `_COMPOUND_FIRST_NAMES` تحت
    # مشتقّة من قيم الماب دي، فاسم مركّب مش مكتوب هنا بيتقسم نصين عند المناداة.
    "abdelhakim": "عبد الحكيم", "abdulhakim": "عبد الحكيم", "abdelhakeem": "عبد الحكيم",
    "abdelwahab": "عبد الوهاب", "abdulwahab": "عبد الوهاب", "abdelwahhab": "عبد الوهاب",
    "abdelsattar": "عبد الستار", "abdulsattar": "عبد الستار", "abdelsatar": "عبد الستار",
    "abdellatif": "عبد اللطيف", "abdullatif": "عبد اللطيف", "abdelatif": "عبد اللطيف",
    "abdelhaq": "عبد الحق", "abdelhak": "عبد الحق",
    "abdelnour": "عبد النور", "abdelnoor": "عبد النور",
    "abdelsalam": "عبد السلام", "abdulsalam": "عبد السلام", "abdessalam": "عبد السلام",
    "daifallah": "ضيف الله", "deifallah": "ضيف الله",
    "nasrallah": "نصر الله", "nasrullah": "نصر الله",
    "saadeldin": "سعد الدين", "saadeddine": "سعد الدين",
    "salaheldin": "صلاح الدين", "salaheddine": "صلاح الدين",
    # تهجئات تانية لنفس الأسماء — الضم بيدوّر على الشكل الملزوق («Abd El
    # Hameed» → `abdelhameed`)، فاللي مش هنا بيقع على البادئة `abdel`.
    "abdelhameed": "عبد الحميد", "abdulhameed": "عبد الحميد",
    "abdelraheem": "عبد الرحيم", "abdulrahim": "عبد الرحيم",
    "abdelazeez": "عبد العزيز", "abdelmageed": "عبد المجيد", "abdelmagid": "عبد المجيد",
    "abdelmohsen": "عبد المحسن", "abdelraoof": "عبد الرؤوف",
    "abdelmonem": "عبد المنعم", "abdelmoneem": "عبد المنعم",
    "abdelghany": "عبد الغني", "abdelfatah": "عبد الفتاح", "abdelnasser": "عبد الناصر",
    "abdelhalim": "عبد الحليم", "abdelhaleem": "عبد الحليم",
    "abdelkader": "عبد القادر", "abdelqader": "عبد القادر",
    "abdelbaset": "عبد الباسط", "abdelbasit": "عبد الباسط",
    "abdelkhalek": "عبد الخالق", "abdelkhaleq": "عبد الخالق",
    "seifeldin": "سيف الدين", "saifeldin": "سيف الدين", "seifeddine": "سيف الدين",
    "alaaeldin": "علاء الدين", "alaaeddine": "علاء الدين",
    "gamaleldin": "جمال الدين", "gamaleddine": "جمال الدين",
    # نفس الأسماء، بباقي التهجئات اللي إخواتها بتستعملها. `Nour Eldin Hany` كان
    # بيرجع «نور» وحده لأن الماب كان فيها noureddine/noureddin/noureldeen وناقصها
    # noureldin بالظبط — واللي بعده «الدين» فمفيش لبس، الناقص كان تهجئة وخلاص.
    # اتعملت مسحة واحدة: كل قيمة مركّبة × الأشكال اللي إخواتها مكتوبين بيها.
    "gamaleddin": "جمال الدين", "gamaleldeen": "جمال الدين",
    "saadeddin": "سعد الدين", "saadeldeen": "سعد الدين",
    "saifeddin": "سيف الدين", "saifeddine": "سيف الدين", "saifeldeen": "سيف الدين",
    "sayfeddin": "سيف الدين", "sayfeddine": "سيف الدين", "sayfeldeen": "سيف الدين",
    "sayfeldin": "سيف الدين", "seifeddin": "سيف الدين", "seifeldeen": "سيف الدين",
    "salaheddin": "صلاح الدين", "salaheldeen": "صلاح الدين",
    "alaaeddin": "علاء الدين", "alaaeldeen": "علاء الدين", "alaeddin": "علاء الدين",
    "alaeddine": "علاء الدين", "alaeldeen": "علاء الدين", "alaeldin": "علاء الدين",
    "nooreddin": "نور الدين", "nooreddine": "نور الدين", "nooreldeen": "نور الدين",
    "nooreldin": "نور الدين", "noureldin": "نور الدين",
    "abdalbaset": "عبد الباسط", "abdalbasit": "عبد الباسط", "abdulbaset": "عبد الباسط",
    "abdulbasit": "عبد الباسط",
    "abdalhak": "عبد الحق", "abdalhaq": "عبد الحق", "abdulhak": "عبد الحق",
    "abdulhaq": "عبد الحق",
    "abdalhakeem": "عبد الحكيم", "abdalhakim": "عبد الحكيم", "abdulhakeem": "عبد الحكيم",
    "abdalhaleem": "عبد الحليم", "abdalhalim": "عبد الحليم", "abdulhaleem": "عبد الحليم",
    "abdulhalim": "عبد الحليم",
    "abdalhameed": "عبد الحميد", "abdalhamid": "عبد الحميد", "abdulhamid": "عبد الحميد",
    "abdalkhalek": "عبد الخالق", "abdalkhaleq": "عبد الخالق", "abdulkhalek": "عبد الخالق",
    "abdulkhaleq": "عبد الخالق",
    "abdalraoof": "عبد الرؤوف", "abdalraouf": "عبد الرؤوف", "abdulraoof": "عبد الرؤوف",
    "abdulraouf": "عبد الرؤوف",
    "abdalraheem": "عبد الرحيم", "abdalrahim": "عبد الرحيم", "abdulraheem": "عبد الرحيم",
    "abdalsatar": "عبد الستار", "abdalsattar": "عبد الستار", "abdulsatar": "عبد الستار",
    "abdalsalam": "عبد السلام",
    "abdalazeez": "عبد العزيز", "abdalaziz": "عبد العزيز", "abdulazeez": "عبد العزيز",
    "abdalghani": "عبد الغني", "abdalghany": "عبد الغني", "abdulghani": "عبد الغني",
    "abdulghany": "عبد الغني",
    "abdalfatah": "عبد الفتاح", "abdalfattah": "عبد الفتاح", "abdulfatah": "عبد الفتاح",
    "abdulfattah": "عبد الفتاح",
    "abdalkader": "عبد القادر", "abdalqader": "عبد القادر", "abdulkader": "عبد القادر",
    "abdulqader": "عبد القادر",
    "abdallateef": "عبد اللطيف", "abdallatif": "عبد اللطيف", "abdellateef": "عبد اللطيف",
    "abdullateef": "عبد اللطيف",
    "abdalmageed": "عبد المجيد", "abdalmagid": "عبد المجيد", "abdalmajeed": "عبد المجيد",
    "abdalmajid": "عبد المجيد", "abdelmajeed": "عبد المجيد", "abdelmajid": "عبد المجيد",
    "abdulmageed": "عبد المجيد", "abdulmagid": "عبد المجيد",
    "abdalmuhsen": "عبد المحسن", "abdelmuhsen": "عبد المحسن", "abdulmohsen": "عبد المحسن",
    "abdulmuhsen": "عبد المحسن",
    "abdalmoneem": "عبد المنعم", "abdalmoneim": "عبد المنعم", "abdalmonem": "عبد المنعم",
    "abdulmoneem": "عبد المنعم", "abdulmoneim": "عبد المنعم", "abdulmonem": "عبد المنعم",
    "abdalnaser": "عبد الناصر", "abdalnasser": "عبد الناصر", "abdelnaser": "عبد الناصر",
    "abdulnaser": "عبد الناصر", "abdulnasser": "عبد الناصر",
    "abdalnoor": "عبد النور", "abdalnour": "عبد النور", "abdulnoor": "عبد النور",
    "abdulnour": "عبد النور",
    "abdalwahab": "عبد الوهاب", "abdalwahhab": "عبد الوهاب", "abdulwahhab": "عبد الوهاب",
    # علي / علاء / عمار / أنس
    "ali": "علي", "aly": "علي",
    "alaa": "علاء", "aalaa": "علاء", "ala": "علاء",
    "ammar": "عمار", "anas": "أنس",
    # حمزة / حسن / حسين / حسام / حازم / هاشم
    "hamza": "حمزة", "hamzah": "حمزة",
    "hassan": "حسن", "hasan": "حسن",
    "hussein": "حسين", "hussain": "حسين", "husein": "حسين", "hosein": "حسين",
    "hossam": "حسام", "hosam": "حسام", "hussam": "حسام",
    "hazem": "حازم", "hazim": "حازم",
    "hashem": "هاشم", "hashim": "هاشم",
    # زياد / مازن / معاذ / معتز / أدهم / سيف / ياسين
    "ziad": "زياد", "zeyad": "زياد", "zyad": "زياد", "ziyad": "زياد",
    "mazen": "مازن", "mazin": "مازن",
    "moaz": "معاذ", "muadh": "معاذ",
    "moataz": "معتز", "muataz": "معتز", "motaz": "معتز",
    "adham": "أدهم",
    "seif": "سيف", "saif": "سيف", "saef": "سيف", "sayf": "سيف",
    "yassin": "ياسين", "yassine": "ياسين", "yasin": "ياسين", "yassen": "ياسين",
    "yaseen": "ياسين",
    # خالد / كريم / وليد / طارق / شريف / عمر
    "khaled": "خالد", "khalid": "خالد",
    "karim": "كريم", "kareem": "كريم", "karem": "كريم",
    "walid": "وليد", "waleed": "وليد", "waled": "وليد",
    "tarek": "طارق", "tareq": "طارق", "tarik": "طارق", "tariq": "طارق",
    "sherif": "شريف", "shrief": "شريف", "sharif": "شريف",
    # أسامة / نبيل / مؤمن / إياد / إسلام / إبراهيم / آدم / أمير
    "osama": "أسامة", "usama": "أسامة",
    "nabil": "نبيل",
    "momen": "مؤمن", "moamen": "مؤمن", "moemen": "مؤمن", "mumen": "مؤمن", "momin": "مؤمن",
    "eyad": "إياد", "iyad": "إياد",
    "eslam": "إسلام", "islam": "إسلام",
    "ibrahim": "إبراهيم", "ebrahim": "إبراهيم", "ebrahem": "إبراهيم", "ibrahem": "إبراهيم",
    "adam": "آدم",
    "amir": "أمير", "ameer": "أمير",
    # مالك / مروان / بلال / نصر / صلاح / عثمان / يحيى / إيهاب / فارس
    "malek": "مالك", "malik": "مالك",
    "marwan": "مروان",
    "belal": "بلال", "bilal": "بلال",
    "nasr": "نصر",
    "salah": "صلاح",
    "othman": "عثمان", "osman": "عثمان", "othmane": "عثمان",
    "yehia": "يحيى", "yahia": "يحيى", "yehya": "يحيى", "yahya": "يحيى",
    "ehab": "إيهاب",
    "fares": "فارس", "faris": "فارس",
    # ماجد / أمجد / سعد / سامي / هاني / زكريا / وائل / تامر / عماد / أشرف
    "maged": "ماجد", "majed": "ماجد",
    "amgad": "أمجد", "amjad": "أمجد",
    "saad": "سعد", "sa3d": "سعد",
    "samy": "سامي", "sami": "سامي",
    "hani": "هاني", "hany": "هاني",
    "zakarya": "زكريا", "zakaria": "زكريا",
    "wael": "وائل",
    "tamer": "تامر",
    "emad": "عماد", "imad": "عماد",
    "ashraf": "أشرف",
    # أيمن / بهاء / ربيع / يونس / جهاد / نعيم / زين / تيم / أيهم / رامي / فادي / سامح / باسل
    "ayman": "أيمن",
    "bahaa": "بهاء", "baha": "بهاء",
    "rabie": "ربيع", "rabea": "ربيع",
    "younis": "يونس", "younes": "يونس", "yunus": "يونس",
    "gihad": "جهاد", "jihad": "جهاد",
    "naim": "نعيم", "naeem": "نعيم",
    "zain": "زين", "zayn": "زين", "zein": "زين",
    "tayem": "تيم", "taim": "تيم", "teem": "تيم",
    "ayham": "أيهم",
    "ramy": "رامي", "rami": "رامي",
    "fady": "فادي", "fadi": "فادي",
    "sameh": "سامح",
    "bassel": "باسل", "basel": "باسل", "basil": "باسل",
    "ezz": "عز", "moheb": "محب", "anis": "أنيس",
    # أسماء قبطية شائعة
    "mina": "مينا", "mena": "مينا",
    "kerollos": "كيرلس", "kirollos": "كيرلس", "kerolous": "كيرلس", "kirolos": "كيرلس",
    "bavly": "بافلي", "filopater": "فيلوباتير", "eriny": "إيريني", "irini": "إيريني",
    "gerges": "جرجس", "george": "جورج", "beshoy": "بيشوي", "boula": "بولا",
    # أسماء بنات
    "fatma": "فاطمة", "fatima": "فاطمة", "fatimah": "فاطمة",
    "aya": "آية", "aia": "آية",
    "mariam": "مريم", "maryam": "مريم", "marim": "مريم",
    "sara": "سارة", "sarah": "سارة", "sarra": "سارة",
    "nour": "نور", "noor": "نور", "nor": "نور",
    "nourhan": "نورهان", "nurhan": "نورهان",
    "salma": "سلمى",
    "yasmin": "ياسمين", "yasmine": "ياسمين", "yasmeen": "ياسمين", "jasmine": "ياسمين",
    "habiba": "حبيبة", "habeba": "حبيبة",
    "menna": "منة", "mennah": "منة",
    "nada": "ندى",
    "dina": "دينا",
    "rana": "رنا",
    "reham": "ريهام", "riham": "ريهام",
    "heba": "هبة", "hiba": "هبة",
    "mona": "منى", "mouna": "منى",
    "esraa": "إسراء", "israa": "إسراء", "esra": "إسراء",
    "doaa": "دعاء", "doa": "دعاء",
    "amira": "أميرة", "ameera": "أميرة",
    "aisha": "عائشة", "aicha": "عائشة",
    "malak": "ملك",
    "farah": "فرح",
    "rania": "رانية", "raneem": "رنيم", "raneen": "رنين",
    "shaimaa": "شيماء", "shimaa": "شيماء", "shaima": "شيماء",
    "asmaa": "أسماء", "asma": "أسماء",
    "hana": "هنا", "hanaa": "هناء", "hannah": "هناء",
    "rahma": "رحمة", "rahmah": "رحمة",
    "toka": "تقى", "tuqa": "تقى",
    "rawan": "روان", "rewan": "روان", "rowan": "روان",
    "jana": "جنى", "jannah": "جنة", "janna": "جنة",
    "sama": "سما", "samaa": "سماء",
    "eman": "إيمان", "iman": "إيمان",
    "nadia": "نادية",
    "radwa": "رضوى", "radwan": "رضوان",
    "sherouk": "شروق", "shrouk": "شروق", "shorouk": "شروق",
    "manar": "منار", "dana": "دانة", "dania": "دانية",
    "kholoud": "خلود", "khouloud": "خلود",
    "safaa": "صفاء", "wafaa": "وفاء", "sana": "سناء", "soha": "سها",
    "sahar": "سحر", "farida": "فريدة", "basant": "بسنت",
    "sumaya": "سمية", "somaya": "سمية",
    "rahaf": "رهف", "lujain": "لجين", "lojain": "لجين",
    "jood": "جود", "joud": "جود", "judy": "جودي", "jodi": "جودي",
    "layla": "ليلى", "laila": "ليلى", "lilas": "ليلى",
    "kenzy": "كنزي", "kenzi": "كنزي", "kenza": "كنزة",
    "talia": "تاليا", "lian": "ليان", "lien": "ليان",
    "sondos": "سندس", "sandra": "ساندرا", "maria": "ماريا",
    "aml": "أمل", "amal": "أمل", "amany": "أماني", "amani": "أماني",
    "logina": "لوجينا", "rodina": "رودينا", "haidy": "هايدي",
    "joumana": "جمانة", "gomana": "جمانة", "jumana": "جمانة",
    # إضافات من بيانات الأعضاء الحقيقية + أسماء خليجية/شامية شائعة
    "anouar": "أنور", "anwar": "أنور",
    "mohanad": "مهند", "mohaned": "مهند", "mohanned": "مهند", "muhannad": "مهند",
    "fathy": "فتحي", "fathi": "فتحي",
    "abdalrhman": "عبد الرحمن", "abdelrahim": "عبد الرحيم", "abderrahmane": "عبد الرحمن",
    "amed": "أحمد",
    "oussama": "أسامة",
    "faiz": "فايز", "fayez": "فايز", "fayes": "فايز",
    "badr": "بدر", "bader": "بدر",
    "reem": "ريم", "rim": "ريم",
    "david": "داود", "dawood": "داود", "dawoud": "داود",
    "yasser": "ياسر", "yaser": "ياسر", "yassir": "ياسر",
    "samir": "سمير", "sameer": "سمير", "munir": "منير", "mounir": "منير",
    "adel": "عادل", "gamal": "جمال", "kamal": "كمال", "galal": "جلال",
    "magdy": "مجدي", "hamdy": "حمدي", "sabry": "صبري", "lotfy": "لطفي",
    "shawky": "شوقي", "shawki": "شوقي", "refaat": "رفعت",
    "taha": "طه", "ismail": "إسماعيل", "esmail": "إسماعيل", "ismael": "إسماعيل",
    "idris": "إدريس", "sohaib": "صهيب", "suhaib": "صهيب",
    "obada": "عبادة", "ubada": "عبادة", "qusai": "قصي", "qusay": "قصي",
    "wassim": "وسيم", "waseem": "وسيم", "nizar": "نزار", "ghaith": "غيث",
    "noureddine": "نور الدين", "noureddin": "نور الدين", "noureldeen": "نور الدين",
    "abdelhamid": "عبد الحميد", "abdelghani": "عبد الغني", "abdelmoneim": "عبد المنعم",
    "fahd": "فهد", "faisal": "فيصل", "faysal": "فيصل", "sultan": "سلطان",
    "turki": "تركي", "nayef": "نايف", "saud": "سعود", "rakan": "راكان",
    "rayan": "ريان", "rayyan": "ريان", "laith": "ليث", "layth": "ليث",
    "hamad": "حمد", "khalifa": "خليفة", "rashed": "راشد", "rashid": "راشد",
    # أسماء بنات إضافية
    "yousra": "يسرا", "yosra": "يسرا", "shahd": "شهد", "retaj": "ريتاج",
    "remas": "ريماس", "retal": "ريتال", "rital": "ريتال",
    "joury": "جوري", "jory": "جوري", "sham": "شام", "mayar": "ميار",
    "lamar": "لمار", "lara": "لارا", "tia": "تيا", "mila": "ميلا",
    "raghad": "رغد", "danya": "دانيا", "jouri": "جوري",
    "hala": "هالة", "ghala": "غلا", "wateen": "وتين",
    "batoul": "بتول", "batool": "بتول", "sedra": "سدرة", "sidra": "سدرة",
    "leen": "لين", "lin": "لين", "elin": "إلين", "celine": "سيلين",
    # ── إضافة ٢٠٢٦-٠٩-٠٤: من مسح تغطية الروستر الحقيقي (١٩٣٤ عضو).
    # دول الأسامي اللي ظهرت فعلاً في `users.full_name` ومكانتش في الماب. اللي
    # اتضاف هنا هو الواضح بس: أسامي عربية معروفة، وتنويعات لأسامي موجودة أصلاً.
    # اللي **ما**اتضافش عن عمد: الدلع (bebo/koko/memo/mero)، والمدخلات
    # الخردة (the/abc/admin)، والأسامي اللاتينية الحقيقية (steven) — دي
    # بتفضل تتعرض زي ما العضو كاتبها، وده أصح من تخمين ترجمة ليها.
    "muhammed": "محمد", "mohammedd": "محمد",
    "moaaz": "معاذ", "yasseen": "ياسين",
    "abdallh": "عبد الله", "abdall": "عبد الله", "abdulrhman": "عبد الرحمن",
    "abdelraouf": "عبد الرؤوف", "abdalmohsen": "عبد المحسن",
    "abbas": "عباس", "akram": "أكرم",
    "amin": "أمين", "ameen": "أمين",
    "amna": "آمنة", "fahmy": "فهمي", "fahmi": "فهمي",
    "omnia": "أمنية", "ramadan": "رمضان",
    "rokaya": "رقية", "ruqaya": "رقية",
    "said": "سعيد", "saeed": "سعيد",
    "salem": "سالم", "sayed": "سيد",
    "yara": "يارا", "yomna": "يمنى",
    "zahra": "زهراء", "alzahraa": "الزهراء",
    "basmala": "بسملة", "bakr": "بكر",
    "assem": "عاصم", "asem": "عاصم", "bassem": "باسم", "basem": "باسم",
    "albaraa": "البراء", "baraa": "البراء",
    "abanoub": "أبانوب", "mariana": "ماريانا",
}


def is_arabic_text(s: str) -> bool:
    """صح لو النص فيه **أي** حرف عربي. ده كاشف، مش مدقّق.

    `Mohamed محمد` بيعدّي من هنا. الفرق ده مقصود: `arabize_first_name` عايزة
    تعرف «أستنى، ده عربي أصلاً؟» عشان ماتدوّرش في ماب اللاتيني. لو عايز تسأل
    «هل الاسم ده مكتوب بالعربي؟» فدي `is_arabic_name` تحت، وهي حاجة تانية خالص.
    """
    return bool(s) and any("؀" <= ch <= "ۿ" for ch in s)


#: القاعدة نفسها بالحرف للواجهة. الواجهة مش حدود أمان — الباك إند هو اللي
#: بيرفض — بس الرسالة الفورية لازم تقول نفس كلام السيرفر، وقاعدتين بتفرقوا
#: يعني عضو الفورم بتقوله «تمام» والسيرفر بيرفضه. النمط متكتوب هنا مرة واحدة،
#: و`src/js/arabic-name.js` بياخد نفس السطر بالحرف — وفيه اختبار بيقارنهم.
#:
#: النطاقات: حروف عربية أساسية وممتدة + التشكيل + التطويل + المسافة. الأرقام
#: (اللاتيني والعربي-الهندي ٠-٩ و ۰-۹) برّه النطاقات دي عن قصد.
ARABIC_NAME_PATTERN = (
    r"^[\u0621-\u063A\u0641-\u064A\u066E-\u06D3"
    r"\u0750-\u077F\u08A0-\u08BF\u064B-\u0652\u0640 ]+$"
)
#: الحروف اللي بتتعدّ — من غير مسافة ولا تطويل ولا تشكيل. حرف واحد مش اسم.
ARABIC_LETTER_PATTERN = (
    r"[\u0621-\u063A\u0641-\u064A\u066E-\u06D3\u0750-\u077F\u08A0-\u08BF]"
)

_ARABIC_NAME_RE = re.compile(ARABIC_NAME_PATTERN)
_ARABIC_LETTER_RE = re.compile(ARABIC_LETTER_PATTERN)

#: اللي بيتقال للعضو لما الاسم مش بالعربي. رسالة واحدة لكل الأبواب — العضو
#: لازم يقرا نفس الجملة سواء اتكلم مع الفورم أو مع السيرفر.
#:
#: الصيغة رسمية من غير إيموچي بقرار المالك: ده نص بيظهر وقت رفض، والموقع
#: بيتكلم بصيغة رسمية. أي تعديل هنا لازم يتعمل في `arabic-name.js` كمان —
#: `test_the_js_rule_is_the_python_rule` بيقرا الملف ده وبيقع لو اتفرقوا.
ARABIC_NAME_MESSAGE = "برجاء كتابة الاسم باللغة العربية"


def is_arabic_name(value: str | None) -> bool:
    """هل ده اسم **مكتوب بالعربي**؟ — كل حرف فيه عربي، مش حرف واحد بس.

    مش `is_arabic_text`: دي بترجّع True لـ `Mohamed محمد`، وده اسم نص نص. هنا
    القاعدة إن كل حرف عربي؛ المسافة والتطويل والتشكيل ماشيين، والحروف اللاتينية
    والأرقام مرفوضة.

    حرفين على الأقل: `م` مش اسم، والفورم أصلاً بيطلب حرفين لكل خانة.
    """
    s = " ".join((value or "").split())
    if not s:
        return False
    if not _ARABIC_NAME_RE.match(s):
        return False
    return len(_ARABIC_LETTER_RE.findall(s)) >= 2


def arabic_name_suggestion(full_name: str | None) -> str:
    """اقتراح اسم عربي للعرض في خانة الأونبوردنج — عربي بالكامل أو ولا حاجة.

    الاقتراح ده قيمة الخانة الافتراضية، يعني العضو ممكن يبعته زي ما هو. فلازم
    يعدّي `is_arabic_name` — وإلا الفورم بيدّي العضو قيمة بترفضها قاعدته هو.
    وأهم من كده: مايطلعش نص نص. اسم نصه عربي ونصه لاتيني ماينفعش يتخزّن، فما
    ينفعش كمان يتعرض كاقتراح — الفورم اللي بيملي `محمد Salah` بيعلّم الشكل
    اللي المفروض مايوجدش.

    تلات نتايج بس:
      * الكلمتين اتعرفوا     → الاسم العربي كامل (`Nabil Ahmed` → `نبيل أحمد`)
      * الاسم الأول بس       → الاسم الأول لوحده (`Mohamed Elsayed` → `محمد`)
      * ولا واحد             → `""`، مفيش اقتراح خالص

    الحالة التانية بتسيب العضو يكتب كلمة واحدة بدل الاسم كله؛ ده أقل شغل من
    إنه يمسح اقتراح غلط ويكتب من الأول.
    """
    first = arabize_first_name(full_name or "")
    if not first or not is_arabic_name(first):
        return ""
    _first, last = split_full_name(full_name)
    arabized = []
    for tok in last.split():
        ar = arabize_name_token(tok)
        if not ar:
            # كلمة واحدة ماعرفناهاش بتوقّف اسم العيلة كله. نص الاسم بالعربي
            # ونصه لاتيني هو اللي احنا بنمنعه — الاسم الأول لوحده أنضف.
            return compose_full_name(first, "")
        arabized.append(ar)
    return compose_full_name(first, " ".join(arabized))


def _norm_latin_name(s: str) -> str:
    """تطبيع اسم لاتيني للبحث في الماب: إزالة التشكيل + حروف بس + lowercase."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = "".join(ch for ch in s if ch.isalpha())
    return s.lower().strip()


#: الأسماء الأولى المركّبة — مشتقّة من قيم الماب نفسها. أي قيمة فيها مسافة هي
#: اسم أول من كلمتين، فإضافة اسم جديد للماب بتعلّم القسمة عنه لوحدها. كانت فيه
#: ليستة مكتوبة بالإيد في `email_campaign_service` وفعلاً باظت: الماب بتطلّع
#: عبد الرؤوف وعبد المحسن وعبد المنعم، والليستة ماكانتش تعرف واحد فيهم.
_COMPOUND_FIRST_NAMES = frozenset(v for v in _AR_FIRST_NAMES.values() if " " in v)

#: مفاتيح لاتينية هي بادئة، مش اسم. `abdel` لوحدها ممكن تكون عبد الرحمن أو عبد
#: الحميد أو أي حاجة؛ الماب بتخمّن أشهرهم لما تيجي توكن لوحدها وده تخمين مقبول.
#: لكنها ماينفعش تضم كلمتين: `Abd El Hameed` كان بيطلع «عبد الرحمن» — اسم غلط
#: بثقة، وده أوحش من «عبد» المقطوعة اللي بنصلّحها.
_AMBIGUOUS_LATIN_PREFIXES = frozenset({"abdel", "abd", "abdul", "abdal"})


def first_name_token(full_name: str | None) -> str:
    """الاسم الأول كامل: كلمة، أو كلمتين/تلاتة لو الاسم مركّب. `""` لو مفيش اسم.

    دي القسمة الوحيدة في المشروع. `عبد الرحمن علي` اسمه الأول `عبد الرحمن` مش
    `عبد` — والقسمة على أول مسافة كانت بتخلّي التحية «أهلاً عبد»، وكانت بتخزّن
    `first_name = "عبد"` لكل واحد داخل بجوجل.

    بتشتغل على الشكلين: العربي بالمطابقة على الست، واللاتيني بضم الكلمات
    وسؤال الماب (`Abd El Hameed` → `abdelhameed` → `عبد الحميد`). الضم بيحصل
    بس لما الناتج يكون اسم مركّب فعلاً، فـ `Nour Hany` مابتتضمّش لـ `نورهان`.
    """
    parts = (full_name or "").split()
    if not parts:
        return ""
    # الأطول الأول: `Abd El Hameed` تلات كلمات لاسم واحد، ولو جرّبنا كلمتين
    # الأول كانوا هيبقوا `Abd El` — وهي بادئة مش اسم.
    for n in (3, 2):
        if len(parts) < n:
            continue
        head = " ".join(parts[:n])
        if head in _COMPOUND_FIRST_NAMES:
            return head
        key = _norm_latin_name(head)
        if key in _AMBIGUOUS_LATIN_PREFIXES:
            continue
        if _AR_FIRST_NAMES.get(key) in _COMPOUND_FIRST_NAMES:
            return head
    return parts[0]


def arabize_first_name(name: str):
    """
    يرجّع الصيغة العربية لاسم أول واحد:
      • لو فيه عربي أصلاً → يرجّعه زي ما هو.
      • لو لاتيني ومعروف في الماب → الترجمة العربية.
      • غير كده → None (المنادي يقرر الـ fallback).
    """
    if not name or not name.strip():
        return None
    tok = first_name_token(name)
    if is_arabic_text(tok):
        return tok
    return _AR_FIRST_NAMES.get(_norm_latin_name(tok))


def arabize_name_token(token: str | None) -> str | None:
    """الصيغة العربية لكلمة واحدة من الاسم — أو None لو مش معروفة.

    `arabize_first_name` بتاخد اسم كامل وبتطلّع الاسم الأول منه؛ دي بتشتغل على
    كلمة واحدة اتقسمت خلاص، عشان اسم العيلة يتعرّب بنفس الماب اللي بتعرّب
    الاسم الأول. أغلب أسامي العيلة المصرية هي أصلاً أسامي أولى (`صلاح`، `حسن`،
    `أحمد`) فهي موجودة في الماب من غير ما نضيف حاجة.

    بتقيس بـ `is_arabic_name` مش `is_arabic_text`: كلمة زي `Mohamedمحمد` فيها
    حروف عربية بس مش مكتوبة بالعربي، والرجوع بيها كأنها عربية هو بالظبط الشكل
    نص نص اللي مالوش مكان في أي اسم.
    """
    tok = (token or "").strip()
    if not tok:
        return None
    if is_arabic_name(tok):
        return tok
    return _AR_FIRST_NAMES.get(_norm_latin_name(tok))


#: اللي بننادي بيه عضو مالوش اسم نقدر نستخدمه. مركزي هنا عشان الشاشة تقدر
#: تعدّ كام واحد هيسمعه قبل ما الحملة تتبعت — من غير ما تخمّن النص.
FALLBACK_FIRST_NAME = "صديقنا"


def arabic_first_name(full_name: str | None) -> str:
    """اللي بننادي بيه العضو ده. بيرجّع نص جاهز للعرض — عمره ما بيرجّع فاضي.

    السلسلة، بالترتيب:
      ١. الاسم الأول معرّب لو عرفناه (`Mohamed` → `محمد`)، أو زي ما هو لو عربي أصلاً.
      ٢. وإلا الاسم الأول زي ما هو مكتوب — اسم لاتيني مش في الماب أحسن من لا شيء.
      ٣. وإلا `صديقنا`.

    كانت اسمها `_first_name` وكانت private جوه `email_service`. بقت public هنا
    لأن الإعلانات بقت بتناديها كمان؛ السلوك ما اتغيرش ولا حرف.

    بتقرا `full_name` وبس. مابتكتبش حاجة، ومابتلمسش الداتابيز.
    """
    name = (full_name or "").strip()
    if not name:
        return FALLBACK_FIRST_NAME
    tok = first_name_token(name)
    return arabize_first_name(tok) or tok


def resolves_to_arabic(full_name: str | None) -> bool:
    """هل العضو ده هيتنادى باسم **عربي** فعلاً؟

    مش نفس عكس `resolves_to_fallback`. فيه تلات حالات مش اتنين:
      • اسم بيتعرّب (`Mohamed` → `محمد`) أو عربي أصلاً  → دي.
      • اسم لاتيني مش في الماب (`Radhouane`)            → بيتعرض زي ما هو.
      • مفيش اسم خالص                                    → `صديقنا`.

    التانية هي الحالة الأكتر على الروستر الحقيقي، وهي اللي بتخلي اسم لاتيني
    يقع في نص عربي — والمشغّل لازم يشوفها قبل ما يبعت، مش بعدين.
    """
    name = (full_name or "").strip()
    if not name:
        return False
    return arabize_first_name(name) is not None


def resolves_to_fallback(full_name: str | None) -> bool:
    """هل العضو ده هيتنادي `صديقنا`؟

    السؤال ده بيتسأل قبل الإرسال — «كام واحد من دول مش هيتنادي باسمه؟» — وهو
    بيتجاوب من نفس الدالة اللي الإرسال بيستخدمها بالظبط، مش من نسخة تانية من
    نفس المنطق. ده الفرق بين رقم بيوصف اللي هيحصل ورقم بيوصف حاجة قريبة منه.
    """
    return arabic_first_name(full_name) == FALLBACK_FIRST_NAME
