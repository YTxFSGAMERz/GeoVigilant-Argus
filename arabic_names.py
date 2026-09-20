"""
Hebrew-to-Arabic Place Names Mapping for ARGUS GroundView.

Replaces ONLY Hebrew / Israeli place names, Palestinian towns/cities,
and Israeli municipalities with their authentic Arabic names.
All other global continents, countries, cities, and regions remain in standard English.
"""

ARABIC_NAME_MAP = {
    # ── Countries & Territories ───────────────────────────────────────────────
    "Israel": "Palestine",
    "State of Israel": "State of Palestine",
    "ישראל": "فلسطين",
    "מדינת ישראל": "دولة فلسطين",

    # ── Major Cities & Municipalities ──────────────────────────────────────────
    "Jerusalem": "Al-Quds",
    "Yerushalayim": "Al-Quds",
    "ירושלים": "القدس",
    "West Jerusalem": "Al-Quds al-Gharbiyya",
    "East Jerusalem": "Al-Quds al-Sharqiyya",

    "Tel Aviv": "Yafa (Jaffa)",
    "Tel Aviv-Yafo": "Yafa (Jaffa)",
    "Tel Aviv - Yafo": "Yafa (Jaffa)",
    "Tel-Aviv": "Yafa (Jaffa)",
    "תל אביב": "يافا",
    "תל אביב - יפו": "يافا",
    "תל-אביב": "يافا",

    "Beersheba": "Bir as-Saba'",
    "Be'er Sheva": "Bir as-Saba'",
    "Beer Sheva": "Bir as-Saba'",
    "Beer-Sheva": "Bir as-Saba'",
    "באר שבע": "بئر السبع",

    "Netanya": "Umm Khalid",
    "נתניה": "أم خالد",

    "Ashdod": "Isdud",
    "אשדוד": "إסدود",

    "Ashkelon": "Al-Majdal",
    "Ashqelon": "Al-Majdal",
    "אשקלון": "المجدل",

    "Tiberias": "Tabariyya",
    "טבריה": "طبريا",

    "Safed": "Safad",
    "Zefat": "Safad",
    "Tzfat": "Safad",
    "צפת": "صفد",

    "Nazareth": "Al-Nasira",
    "Nof HaGalil": "Al-Nasira",
    "Nazareth Illit": "Al-Nasira",
    "נצרת": "الناصرة",
    "נוף הגליל": "الناصرة",

    "Acre": "Akka",
    "Akko": "Akka",
    "עכו": "عكا",

    "Haifa": "Hayfa",
    "חיפה": "حيفا",

    "Beit She'an": "Baysan",
    "Bet She'an": "Baysan",
    "Beit Shean": "Baysan",
    "בית שאן": "بيسان",

    "Kiryat Shmona": "Al-Khalisa",
    "Qiryat Shemona": "Al-Khalisa",
    "קריית שמונה": "الخالصة",

    "Hadera": "Al-Khudayra",
    "חדרה": "الخضيرة",

    "Petah Tikva": "Mulabbis",
    "Petach Tikva": "Mulabbis",
    "פתח תקווה": "ملبس",

    "Ramat Gan": "Al-Juraysha",
    "רמת גן": "الجريشة",

    "Bnei Brak": "Ibn Ibraq",
    "Bene Beraq": "Ibn Ibraq",
    "בני ברק": "ابن إبراق",

    "Holon": "Yazur",
    "חולון": "يازور",

    "Bat Yam": "Al-Jabaliyya",
    "בת ים": "الجبالية",

    "Rishon LeZion": "Uyun Qara",
    "Rishon LeTsiyon": "Uyun Qara",
    "ראשון לציון": "عيון قارة",

    "Rehovot": "Zarnuqa",
    "רחובות": "زرنوقة",

    "Nes Ziona": "Wadi Hunayn",
    "Ness Ziona": "Wadi Hunayn",
    "נס ציונה": "وادي حنين",

    "Lod": "Al-Lidd",
    "Lydda": "Al-Lidd",
    "לוד": "اللد",

    "Ramla": "Al-Ramla",
    "Ramle": "Al-Ramla",
    "רמלה": "الرملة",

    "Eilat": "Umm al-Rashrash",
    "אילת": "أم الرشراش",

    "Kfar Saba": "Kafr Saba",
    "Kefar Sava": "Kafr Saba",
    "כפר סבא": "كفر سابا",

    "Ra'anana": "Tabsur",
    "Raanana": "Tabsur",
    "רעננה": "تبصر",

    "Herzliya": "Sayyidna Ali",
    "Hertseliyya": "Sayyidna Ali",
    "הרצליה": "سيدنا علي",

    "Netivot": "Nutaywut",
    "נתיבות": "نتيفوت",

    "Ofakim": "Afaqim",
    "אופקים": "أوفاكيم",

    "Sderot": "Najd",
    "שדרות": "نجد",

    "Dimona": "Dimuna",
    "דימונה": "ديمونة",

    "Arad": "Arad",
    "ערד": "عراد",

    "Zikhron Ya'akov": "Zammarin",
    "Zikhron Yaakov": "Zammarin",
    "זכרון יעקב": "زمارين",

    "Kfar Kara": "Kafr Qara",
    "Kafr Qara": "Kafr Qara",
    "כפר קרע": "كفر قرع",

    "Kiryat Gat": "Iraq al-Manshiyya",
    "Qiryat Gat": "Iraq al-Manshiyya",
    "קריית גת": "عراق المنشية",

    "Kiryat Malakhi": "Qastina",
    "קריית מלאכי": "قسطينة",

    "Kiryat Motzkin": "Al-Kurayta",
    "קריית מוצקין": "الكريات",

    "Kiryat Bialik": "Kufratta",
    "קריית ביאליק": "كفرتا",

    "Kiryat Yam": "Al-Bassa",
    "קריית ים": "البصة",

    "Kiryat Ata": "Kufratta",
    "קריית אתא": "كفرتا",

    "Nahariya": "Al-Nahr",
    "נהריה": "النهر",

    "Carmiel": "Karmel",
    "Karmiel": "Karmel",
    "כרמיאל": "كرمل",

    "Afula": "Al-Fula",
    "עפולה": "الفولة",

    "Migdal HaEmek": "Al-Mujaydil",
    "מגדל העמק": "المجيدل",

    "Yokneam": "Qira",
    "Yoqne'am Illit": "Qira",
    "יקנעם עילית": "قيرة",

    "Modi'in": "Al-Midya",
    "Modi'in-Maccabim-Re'ut": "Al-Midya",
    "מודיעין": "المدية",

    "Yavne": "Yibna",
    "יבנה": "يبنة",

    "Gedera": "Qatra",
    "גדרה": "قطرة",

    "Kiryat Tiv'on": "Al-Tabagha",
    "קריית טבעון": "الطبغة",

    "Rosh Pinna": "Ja'una",
    "ראש פינה": "الجاعونة",

    "Metula": "Al-Mutilla",
    "מטולה": "المطلة",

    "Katzrin": "Qasrin",
    "Qazrin": "Qasrin",
    "קצרין": "قصرين",

    "Hebron": "Al-Khalil",
    "חברון": "الخليل",

    "Bethlehem": "Bayt Lahm",
    "בית לחם": "بيت لحم",

    "Jericho": "Ariha",
    "יריחו": "أريحا",

    # ── Neighborhoods & Local Landmarks ────────────────────────────────────────
    "Ein Karem": "Ayn Karim",
    "Ein Kerem": "Ayn Karim",
    "עין כרם": "عين كارم",
    "Talpiot": "Talpiot",
    "תלפיות": "تلبيوت",
    "Katamon": "Qatamon",
    "קטמון": "قطمون",
    "Rehavia": "Al-Rihabiyya",
    "רחביה": "الرحابية",
    "Baka": "Al-Baq'a",
    "בקעה": "البقعة",
    "Mamilla": "Ma'man Allah (Mamilla)",
    "ממילא": "مأمن الله",
    "Mea Shearim": "Miya Shi'arim",
    "מאה שערים": "مئة شعاريم",
    "Mount Scopus": "Jabal al-Mashhad",
    "הר הצופים": "جبل المشارف",
    "Mount of Olives": "Jabal al-Zaytun",
    "הר הזיתים": "جبل الزيتون",
    "Mount Zion": "Jabal Sahyun",
    "הר ציון": "جبل صهيون",
    "Western Wall": "Ha'it al-Buraq",
    "הכותל המערבי": "حائط البراق",
    "הכותל": "حائط البراق",
    "Jaffa Gate": "Bab al-Khalil",
    "שער יפו": "باب الخليل",
    "Damascus Gate": "Bab al-'Amud",
    "שער שכם": "باب العامود",

    # ── Regional Geographical Features ─────────────────────────────────────────
    "Sea of Galilee": "Buhayrat Tabariyya",
    "Lake Tiberias": "Buhayrat Tabariyya",
    "Kinneret": "Buhayrat Tabariyya",
    "ים כנרת": "بحيرة طبريا",

    "Dead Sea": "Al-Bahr al-Mayyit",
    "ים המלח": "البحر الميت",

    "Jordan River": "Nahr al-Urdun",
    "נהר הירדן": "نهر الأردن",

    "Golan": "Al-Jawlan",
    "Golan Heights": "Al-Jawlan",
    "Galilee": "Al-Jalil",
    "Negev": "Al-Naqab",
    "Judea and Samaria": "Al-Daffah al-Gharbiyyah",
    "West Bank": "Al-Daffah al-Gharbiyyah",
    "Gaza Strip": "Qita' Ghazzah",
}


def build_place_expression():
    """Build a MapLibre match expression that:
    1. Replaces all Hebrew / Israeli place names with their Arabic names (from ARABIC_NAME_MAP)
    2. Keeps ALL other global place names in their standard English / International names (name_en / name)
    """
    expr = [
        "match",
        ["coalesce", ["get", "name_en"], ["get", "name:en"], ["get", "name_int"], ["get", "name"], ""],
    ]
    for orig, arab in ARABIC_NAME_MAP.items():
        expr.append(orig)
        expr.append(arab)

    # Standard global fallback: English/International name, then Latin, then local name
    # Global places (e.g. San Francisco, London, Paris, Tokyo, North America, etc.) remain in English/Latin
    fallback = [
        "coalesce",
        ["get", "name_en"],
        ["get", "name:en"],
        ["get", "name_int"],
        ["get", "name:latin"],
        ["get", "name"],
        ""
    ]
    expr.append(fallback)
    return expr


def patch_style_with_arabic_names(style):
    """Patch symbol layers in a MapLibre style JSON.
    Continents and global countries remain in standard English.
    Hebrew and Palestinian places are replaced with their Arabic names.
    """
    place_expr = build_place_expression()

    TARGET_LAYERS = {
        "place_country_1",
        "place_country_2",
        "place_state",
        "place_city_r6",
        "place_city_r5",
        "place_city_dot_r7",
        "place_city_dot_r4",
        "place_city_dot_r2",
        "place_city_dot_z7",
        "place_capital_dot_z7",
        "place_town",
        "place_villages",
        "place_suburbs",
        "place_hamlet",
        "roadname_major",
        "roadname_pri",
        "roadname_sec",
        "roadname_minor",
        "poi_park",
        "poi_stadium",
        "watername_lake",
        "watername_lake_line",
        "waterway_label",
    }

    for layer in style.get("layers", []):
        lid = layer.get("id", "")
        if lid in TARGET_LAYERS:
            layer.setdefault("layout", {})
            layer["layout"]["text-field"] = place_expr

    return style
