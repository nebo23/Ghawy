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
import unicodedata


def split_full_name(full_name: str | None) -> tuple[str, str]:
    """Split a display name on the FIRST space.

    "محمد أحمد علي" -> ("محمد", "أحمد علي")
    "Mohamed"        -> ("Mohamed", "")
    """
    clean = " ".join((full_name or "").split())
    if not clean:
        return "", ""
    first, _, last = clean.partition(" ")
    return first, last


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
    """صح لو النص فيه أي حرف عربي."""
    return bool(s) and any("؀" <= ch <= "ۿ" for ch in s)


def _norm_latin_name(s: str) -> str:
    """تطبيع اسم لاتيني للبحث في الماب: إزالة التشكيل + حروف بس + lowercase."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = "".join(ch for ch in s if ch.isalpha())
    return s.lower().strip()


def arabize_first_name(name: str):
    """
    يرجّع الصيغة العربية لاسم أول واحد:
      • لو فيه عربي أصلاً → يرجّعه زي ما هو.
      • لو لاتيني ومعروف في الماب → الترجمة العربية.
      • غير كده → None (المنادي يقرر الـ fallback).
    """
    if not name or not name.strip():
        return None
    tok = name.strip().split()[0]
    if is_arabic_text(tok):
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
    tok = name.split()[0]
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
    return arabize_first_name(name.split()[0]) is not None


def resolves_to_fallback(full_name: str | None) -> bool:
    """هل العضو ده هيتنادي `صديقنا`؟

    السؤال ده بيتسأل قبل الإرسال — «كام واحد من دول مش هيتنادي باسمه؟» — وهو
    بيتجاوب من نفس الدالة اللي الإرسال بيستخدمها بالظبط، مش من نسخة تانية من
    نفس المنطق. ده الفرق بين رقم بيوصف اللي هيحصل ورقم بيوصف حاجة قريبة منه.
    """
    return arabic_first_name(full_name) == FALLBACK_FIRST_NAME
