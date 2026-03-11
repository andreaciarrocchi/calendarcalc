import flet as ft
from datetime import date, timedelta, datetime as _datetime
import calendar
import locale as _locale
import json
import os
import sys


APP_VERSION = "2.0"
APP_AUTHOR  = "Andrea Ciarrocchi"
APP_REPO    = "https://github.com/andreaciarrocchi/calendarcalc"
APP_WEB     = "https://andreaciarrocchi.altervista.org"
APP_PAYPAL  = "https://paypal.me/ciarro85"

# App icon loaded from assets/calendarcalc.svg (place the file in an assets/ folder next to the script)
_APP_ICON_SRC = "calendarcalc.svg"

# ── Cross-platform settings path ─────────────────────────────────────────────

def _get_settings_path() -> str:
    """
    Return a writable path for the settings file that works on:
      - Windows (normal, PyInstaller exe, MSIX)
      - Linux / macOS
      - Android (Flet)

    Priority:
      Windows  -> %APPDATA%\\CalendarCalc\\settings.json
                 MSIX virtualises %APPDATA% automatically, so this just works.
      Linux    -> $XDG_CONFIG_HOME/CalendarCalc/settings.json
                 (falls back to ~/.config/...)
      Android  -> ~/CalendarCalc/settings.json
                 (Flet maps ~ to the app private storage on Android)
    """
    app_name = "CalendarCalc"

    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "android":          # Flet sets this on Android
        base = os.path.expanduser("~")
    else:
        # Linux / macOS / everything else
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )

    folder = os.path.join(base, app_name)
    try:
        os.makedirs(folder, exist_ok=True)
    except OSError:
        # Fallback: write next to the executable / script
        folder = os.path.dirname(
            getattr(sys, "frozen", False) and sys.executable or
            os.path.abspath(__file__)
        )
    return os.path.join(folder, "settings.json")


SETTINGS_PATH = _get_settings_path()

_SETTINGS_DEFAULTS = {
    "work_days": [0, 1, 2, 3, 4],   # Mon–Fri
    "excl_holidays": True,
    "country": None,                  # None → detect from locale at runtime
    "working_only": False,
    "birthday": None,                 # "YYYY-MM-DD" or null
}


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Merge with defaults so new keys are always present
        merged = dict(_SETTINGS_DEFAULTS)
        merged.update(data)
        return merged
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(_SETTINGS_DEFAULTS)


def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
    except OSError:
        pass   # Silently ignore write errors (sandboxed envs, read-only FS)




def _picker_to_date(value) -> date:
    """
    Safely convert a Flet DatePicker value to a local date.

    Flet returns a timezone-aware datetime at midnight UTC.
    Calling .date() directly gives the UTC date which, for timezones
    east of UTC (e.g. UTC+1 Italy), is one day behind the selected date.
    We convert to the local timezone first, then extract year/month/day.
    """
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, _datetime):
        return value          # already a plain date, nothing to do
    try:
        local_dt = value.astimezone()   # converts UTC → local tz
        return date(local_dt.year, local_dt.month, local_dt.day)
    except Exception:
        # Fallback: read attributes directly (better than .date() at least)
        return date(value.year, value.month, value.day)

# ── Easter algorithm ────────────────────────────────────────────────────────

def easter_date(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


# ── Country → holiday database ──────────────────────────────────────────────
# Each entry: (flag, display_name, locale_codes, fixed_list, use_easter, extra_fn)
# fixed_list: list of (month, day, "Name")
# use_easter: bool – add Easter + Easter Monday
# extra_fn(year) -> list[(month, day, "Name")] for computed holidays

def _nth_weekday(year, month, weekday, n):
    """Return the n-th weekday (0=Mon…6=Sun) of the month. n<0 counts from end."""
    days = [d for d in range(1, calendar.monthrange(year, month)[1]+1)
            if date(year, month, d).weekday() == weekday]
    return date(year, month, days[n])



def _find_weekday_in_range(year, month_start, day_start, span, weekday):
    """Find first occurrence of weekday in a date range."""
    for offset in range(span):
        d = date(year, month_start, day_start) + timedelta(offset)
        if d.weekday() == weekday:
            return d
    return None


def _se_extra(y):
    results = [(easter_date(y)+timedelta(39)).month, (easter_date(y)+timedelta(39)).day, "Ascension Day"]
    asc = easter_date(y)+timedelta(39)
    out = [(asc.month, asc.day, "Ascension Day")]
    # Midsummer: Saturday June 20-26
    for d in range(20, 27):
        if date(y, 6, d).weekday() == 5:
            out.append((6, d, "Midsummer's Day"))
            break
    # All Saints: Saturday Oct 31 - Nov 6
    for offset in range(7):
        dd = date(y, 10, 31) + timedelta(offset)
        if dd.weekday() == 5:
            out.append((dd.month, dd.day, "All Saints' Day"))
            break
    return out


def _fi_extra(y):
    asc = easter_date(y) + timedelta(39)
    whit = easter_date(y) + timedelta(49)
    out = [
        (asc.month, asc.day, "Ascension Day"),
        (whit.month, whit.day, "Whit Sunday"),
    ]
    for d in range(20, 27):
        if date(y, 6, d).weekday() == 5:
            out.append((6, d, "Midsummer Day"))
            break
    for offset in range(7):
        dd = date(y, 10, 31) + timedelta(offset)
        if dd.weekday() == 5:
            out.append((dd.month, dd.day, "All Saints' Day"))
            break
    return out


COUNTRIES: dict[str, dict] = {
    "IT": {
        "flag": "🇮🇹", "name": "Italy",
        "locales": ["it_IT", "it"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(4,25,"Liberation Day"),
            (5,1,"Labour Day"),(6,2,"Republic Day"),(8,15,"Assumption of Mary"),
            (11,1,"All Saints' Day"),(12,8,"Immaculate Conception"),
            (12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
    },
    "US": {
        "flag": "🇺🇸", "name": "United States",
        "locales": ["en_US"],
        "fixed": [
            (1,1,"New Year's Day"),(6,19,"Juneteenth"),(7,4,"Independence Day"),
            (11,11,"Veterans Day"),(12,25,"Christmas Day"),
        ],
        "easter": False,
        "extra": lambda y: [
            (_nth_weekday(y,1,0,2).month, _nth_weekday(y,1,0,2).day, "Martin Luther King Jr. Day"),
            (_nth_weekday(y,2,0,2).month, _nth_weekday(y,2,0,2).day, "Presidents' Day"),
            (_nth_weekday(y,5,0,-1).month,_nth_weekday(y,5,0,-1).day,"Memorial Day"),
            (_nth_weekday(y,9,0,0).month, _nth_weekday(y,9,0,0).day, "Labor Day"),
            (_nth_weekday(y,10,0,1).month,_nth_weekday(y,10,0,1).day,"Columbus Day"),
            (_nth_weekday(y,11,3,3).month,_nth_weekday(y,11,3,3).day,"Thanksgiving Day"),
        ],
    },
    "GB": {
        "flag": "🇬🇧", "name": "United Kingdom",
        "locales": ["en_GB"],
        "fixed": [
            (1,1,"New Year's Day"),(1,2,"New Year Holiday (SCO)"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            (_nth_weekday(y,5,0,0).month, _nth_weekday(y,5,0,0).day, "Early May Bank Holiday"),
            (_nth_weekday(y,5,0,-1).month,_nth_weekday(y,5,0,-1).day,"Spring Bank Holiday"),
            (_nth_weekday(y,8,0,-1).month,_nth_weekday(y,8,0,-1).day,"Summer Bank Holiday"),
        ],
    },
    "FR": {
        "flag": "🇫🇷", "name": "France",
        "locales": ["fr_FR", "fr"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(5,8,"Victory in Europe Day"),
            (7,14,"Bastille Day"),(8,15,"Assumption of Mary"),(11,1,"All Saints' Day"),
            (11,11,"Armistice Day"),(12,25,"Christmas Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Monday"),
        ],
    },
    "DE": {
        "flag": "🇩🇪", "name": "Germany",
        "locales": ["de_DE", "de"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(10,3,"German Unity Day"),
            (12,25,"Christmas Day"),(12,26,"2nd Day of Christmas"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Monday"),
        ],
    },
    "ES": {
        "flag": "🇪🇸", "name": "Spain",
        "locales": ["es_ES", "es"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(5,1,"Labour Day"),
            (8,15,"Assumption of Mary"),(10,12,"National Day"),(11,1,"All Saints' Day"),
            (12,6,"Constitution Day"),(12,8,"Immaculate Conception"),(12,25,"Christmas Day"),
        ],
        "easter": True,
    },
    "PT": {
        "flag": "🇵🇹", "name": "Portugal",
        "locales": ["pt_PT", "pt"],
        "fixed": [
            (1,1,"New Year's Day"),(4,25,"Freedom Day"),(5,1,"Labour Day"),
            (6,10,"Portugal Day"),(8,15,"Assumption of Mary"),(10,5,"Republic Day"),
            (11,1,"All Saints' Day"),(12,1,"Restoration of Independence"),
            (12,8,"Immaculate Conception"),(12,25,"Christmas Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(60)).month,(easter_date(y)+timedelta(60)).day,"Corpus Christi"),
        ],
    },
    "NL": {
        "flag": "🇳🇱", "name": "Netherlands",
        "locales": ["nl_NL", "nl"],
        "fixed": [
            (1,1,"New Year's Day"),(4,27,"King's Day"),
            (5,5,"Liberation Day"),(12,25,"Christmas Day"),(12,26,"2nd Christmas Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Monday"),
        ],
    },
    "BE": {
        "flag": "🇧🇪", "name": "Belgium",
        "locales": ["fr_BE", "nl_BE"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(7,21,"National Day"),
            (8,15,"Assumption of Mary"),(11,1,"All Saints' Day"),(11,11,"Armistice Day"),
            (12,25,"Christmas Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Monday"),
        ],
    },
    "CH": {
        "flag": "🇨🇭", "name": "Switzerland",
        "locales": ["de_CH", "fr_CH", "it_CH"],
        "fixed": [
            (1,1,"New Year's Day"),(1,2,"Berchtoldstag"),(8,1,"Swiss National Day"),
            (12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Monday"),
        ],
    },
    "AT": {
        "flag": "🇦🇹", "name": "Austria",
        "locales": ["de_AT"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(5,1,"Labour Day"),
            (8,15,"Assumption of Mary"),(10,26,"National Day"),(11,1,"All Saints' Day"),
            (12,8,"Immaculate Conception"),(12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Monday"),
            ((easter_date(y)+timedelta(60)).month,(easter_date(y)+timedelta(60)).day,"Corpus Christi"),
        ],
    },
    "PL": {
        "flag": "🇵🇱", "name": "Poland",
        "locales": ["pl_PL", "pl"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(5,1,"Labour Day"),
            (5,3,"Constitution Day"),(8,15,"Assumption of Mary"),(11,1,"All Saints' Day"),
            (11,11,"Independence Day"),(12,25,"Christmas Day"),(12,26,"2nd Christmas Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Sunday"),
            ((easter_date(y)+timedelta(60)).month,(easter_date(y)+timedelta(60)).day,"Corpus Christi"),
        ],
    },
    "SE": {
        "flag": "🇸🇪", "name": "Sweden",
        "locales": ["sv_SE", "sv"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(5,1,"Labour Day"),
            (6,6,"National Day"),(12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: _se_extra(y),
    },
    "NO": {
        "flag": "🇳🇴", "name": "Norway",
        "locales": ["nb_NO", "nn_NO", "no"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(5,17,"Constitution Day"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)-timedelta(3)).month,(easter_date(y)-timedelta(3)).day,"Maundy Thursday"),
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Sunday"),
            ((easter_date(y)+timedelta(50)).month,(easter_date(y)+timedelta(50)).day,"Whit Monday"),
        ],
    },
    "DK": {
        "flag": "🇩🇰", "name": "Denmark",
        "locales": ["da_DK", "da"],
        "fixed": [
            (1,1,"New Year's Day"),(6,5,"Constitution Day"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)-timedelta(3)).month,(easter_date(y)-timedelta(3)).day,"Maundy Thursday"),
            ((easter_date(y)+timedelta(26)).month,(easter_date(y)+timedelta(26)).day,"Store Bededag"),
            ((easter_date(y)+timedelta(39)).month,(easter_date(y)+timedelta(39)).day,"Ascension Day"),
            ((easter_date(y)+timedelta(49)).month,(easter_date(y)+timedelta(49)).day,"Whit Sunday"),
            ((easter_date(y)+timedelta(50)).month,(easter_date(y)+timedelta(50)).day,"Whit Monday"),
        ],
    },
    "FI": {
        "flag": "🇫🇮", "name": "Finland",
        "locales": ["fi_FI", "fi"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(5,1,"May Day"),
            (6,4,"Flag Day of Finnish Armed Forces"),(12,6,"Independence Day"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: _fi_extra(y),
    },
    "GR": {
        "flag": "🇬🇷", "name": "Greece",
        "locales": ["el_GR", "el"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(3,25,"Independence Day"),
            (5,1,"Labour Day"),(8,15,"Assumption of Mary"),(10,28,"Ochi Day"),
            (12,25,"Christmas Day"),(12,26,"Synaxis of the Theotokos"),
        ],
        "easter": True,
    },
    "JP": {
        "flag": "🇯🇵", "name": "Japan",
        "locales": ["ja_JP", "ja"],
        "fixed": [
            (1,1,"New Year's Day"),(2,11,"National Foundation Day"),
            (2,23,"Emperor's Birthday"),(4,29,"Showa Day"),(5,3,"Constitution Memorial Day"),
            (5,4,"Greenery Day"),(5,5,"Children's Day"),(8,11,"Mountain Day"),
            (11,3,"Culture Day"),(11,23,"Labour Thanksgiving Day"),
        ],
        "easter": False,
        "extra": lambda y: [
            (_nth_weekday(y,1,0,1).month,_nth_weekday(y,1,0,1).day,"Coming of Age Day"),
            (_nth_weekday(y,7,0,2).month,_nth_weekday(y,7,0,2).day,"Marine Day"),
            (_nth_weekday(y,9,0,2).month,_nth_weekday(y,9,0,2).day,"Respect for the Aged Day"),
            # Autumnal Equinox ~Sept 23
            (9,23,"Autumnal Equinox Day"),
            (_nth_weekday(y,10,0,1).month,_nth_weekday(y,10,0,1).day,"Sports Day"),
        ],
    },
    "CN": {
        "flag": "🇨🇳", "name": "China",
        "locales": ["zh_CN", "zh"],
        "fixed": [
            (1,1,"New Year's Day"),(3,8,"International Women's Day (half-day)"),
            (5,1,"International Labour Day"),(6,1,"International Children's Day"),
            (10,1,"National Day"),(10,2,"National Day Holiday"),(10,3,"National Day Holiday"),
        ],
        "easter": False,
    },
    "IN": {
        "flag": "🇮🇳", "name": "India",
        "locales": ["hi_IN", "en_IN"],
        "fixed": [
            (1,26,"Republic Day"),(8,15,"Independence Day"),(10,2,"Gandhi Jayanti"),
            (12,25,"Christmas Day"),
        ],
        "easter": False,
    },
    "BR": {
        "flag": "🇧🇷", "name": "Brazil",
        "locales": ["pt_BR"],
        "fixed": [
            (1,1,"New Year's Day"),(4,21,"Tiradentes Day"),(5,1,"Labour Day"),
            (9,7,"Independence Day"),(10,12,"Our Lady of Aparecida"),
            (11,2,"All Souls' Day"),(11,15,"Republic Proclamation Day"),
            (11,20,"National Black Consciousness Day"),(12,25,"Christmas Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)-timedelta(47)).month,(easter_date(y)-timedelta(47)).day,"Carnival"),
            ((easter_date(y)-timedelta(46)).month,(easter_date(y)-timedelta(46)).day,"Carnival Tuesday"),
            ((easter_date(y)+timedelta(60)).month,(easter_date(y)+timedelta(60)).day,"Corpus Christi"),
        ],
    },
    "MX": {
        "flag": "🇲🇽", "name": "Mexico",
        "locales": ["es_MX"],
        "fixed": [
            (1,1,"New Year's Day"),(2,5,"Constitution Day"),(3,21,"Benito Juárez Birthday"),
            (5,1,"Labour Day"),(9,16,"Independence Day"),(11,20,"Revolution Day"),
            (12,25,"Christmas Day"),
        ],
        "easter": False,
    },
    "AR": {
        "flag": "🇦🇷", "name": "Argentina",
        "locales": ["es_AR"],
        "fixed": [
            (1,1,"New Year's Day"),(3,24,"Day of Remembrance"),(4,2,"Malvinas Day"),
            (5,1,"Labour Day"),(5,25,"May Revolution Day"),(6,20,"Flag Day"),
            (7,9,"Independence Day"),(12,8,"Immaculate Conception"),(12,25,"Christmas Day"),
        ],
        "easter": True,
    },
    "CA": {
        "flag": "🇨🇦", "name": "Canada",
        "locales": ["en_CA", "fr_CA"],
        "fixed": [
            (1,1,"New Year's Day"),(7,1,"Canada Day"),(11,11,"Remembrance Day"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            (_nth_weekday(y,5,0,-1).month,_nth_weekday(y,5,0,-1).day,"Victoria Day"),
            (_nth_weekday(y,9,0,0).month,_nth_weekday(y,9,0,0).day,"Labour Day"),
            (_nth_weekday(y,10,0,1).month,_nth_weekday(y,10,0,1).day,"Thanksgiving"),
        ],
    },
    "AU": {
        "flag": "🇦🇺", "name": "Australia",
        "locales": ["en_AU"],
        "fixed": [
            (1,1,"New Year's Day"),(1,26,"Australia Day"),(4,25,"ANZAC Day"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            (_nth_weekday(y,6,0,1).month,_nth_weekday(y,6,0,1).day,"Queen's Birthday (most states)"),
        ],
    },
    "NZ": {
        "flag": "🇳🇿", "name": "New Zealand",
        "locales": ["en_NZ"],
        "fixed": [
            (1,1,"New Year's Day"),(1,2,"Day after New Year's"),(2,6,"Waitangi Day"),
            (4,25,"ANZAC Day"),(12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            (_nth_weekday(y,6,0,0).month,_nth_weekday(y,6,0,0).day,"Queen's Birthday"),
            (_nth_weekday(y,10,0,3).month,_nth_weekday(y,10,0,3).day,"Labour Day"),
        ],
    },
    "ZA": {
        "flag": "🇿🇦", "name": "South Africa",
        "locales": ["af_ZA", "en_ZA"],
        "fixed": [
            (1,1,"New Year's Day"),(3,21,"Human Rights Day"),(4,27,"Freedom Day"),
            (5,1,"Workers' Day"),(6,16,"Youth Day"),(8,9,"National Women's Day"),
            (9,24,"Heritage Day"),(12,16,"Day of Reconciliation"),
            (12,25,"Christmas Day"),(12,26,"Day of Goodwill"),
        ],
        "easter": True,
    },
    "RU": {
        "flag": "🇷🇺", "name": "Russia",
        "locales": ["ru_RU", "ru"],
        "fixed": [
            (1,1,"New Year's Day"),(1,7,"Orthodox Christmas"),(2,23,"Defender of Fatherland Day"),
            (3,8,"International Women's Day"),(5,1,"Spring and Labour Day"),
            (5,9,"Victory Day"),(6,12,"Russia Day"),(11,4,"National Unity Day"),
        ],
        "easter": False,
    },
    "UA": {
        "flag": "🇺🇦", "name": "Ukraine",
        "locales": ["uk_UA", "uk"],
        "fixed": [
            (1,1,"New Year's Day"),(1,7,"Orthodox Christmas"),(3,8,"International Women's Day"),
            (5,1,"Labour Day"),(5,9,"Victory Day"),(6,28,"Constitution Day"),
            (8,24,"Independence Day"),(10,14,"Defender's Day"),
            (12,25,"Christmas Day"),
        ],
        "easter": False,
    },
    "TR": {
        "flag": "🇹🇷", "name": "Turkey",
        "locales": ["tr_TR", "tr"],
        "fixed": [
            (1,1,"New Year's Day"),(4,23,"National Sovereignty Day"),
            (5,1,"Labour Day"),(5,19,"Atatürk Commemoration Day"),
            (7,15,"Democracy Day"),(8,30,"Victory Day"),(10,29,"Republic Day"),
        ],
        "easter": False,
    },
    "IL": {
        "flag": "🇮🇱", "name": "Israel",
        "locales": ["he_IL", "he"],
        "fixed": [
            (4,14,"Passover (approx)"),(5,14,"Independence Day (approx)"),
            (9,15,"Rosh Hashana (approx)"),(9,24,"Yom Kippur (approx)"),
            (10,13,"Sukkot (approx)"),
        ],
        "easter": False,
    },
    "EG": {
        "flag": "🇪🇬", "name": "Egypt",
        "locales": ["ar_EG", "ar"],
        "fixed": [
            (1,7,"Coptic Christmas"),(1,25,"Revolution Day"),(4,25,"Sinai Liberation Day"),
            (5,1,"Labour Day"),(6,30,"June 30 Revolution"),(7,23,"National Day"),
            (10,6,"Armed Forces Day"),
        ],
        "easter": False,
    },
    "NG": {
        "flag": "🇳🇬", "name": "Nigeria",
        "locales": ["en_NG"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Workers' Day"),(6,12,"Democracy Day"),
            (10,1,"Independence Day"),(12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
    },
    "KE": {
        "flag": "🇰🇪", "name": "Kenya",
        "locales": ["sw_KE", "en_KE"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(6,1,"Madaraka Day"),
            (10,10,"Huduma Day"),(10,20,"Mashujaa Day"),(12,12,"Jamhuri Day"),
            (12,25,"Christmas Day"),(12,26,"Boxing Day"),
        ],
        "easter": True,
    },
    "KR": {
        "flag": "🇰🇷", "name": "South Korea",
        "locales": ["ko_KR", "ko"],
        "fixed": [
            (1,1,"New Year's Day"),(3,1,"Independence Movement Day"),(5,5,"Children's Day"),
            (6,6,"Memorial Day"),(8,15,"Liberation Day"),(10,3,"National Foundation Day"),
            (10,9,"Hangul Proclamation Day"),(12,25,"Christmas Day"),
        ],
        "easter": False,
    },
    "TH": {
        "flag": "🇹🇭", "name": "Thailand",
        "locales": ["th_TH"],
        "fixed": [
            (1,1,"New Year's Day"),(4,6,"Chakri Memorial Day"),(4,13,"Songkran"),
            (5,1,"Labour Day"),(5,4,"Coronation Day"),(6,3,"Queen's Birthday"),
            (7,28,"King's Birthday"),(8,12,"Mother's Day"),(10,13,"Memorial Day"),
            (10,23,"Chulalongkorn Day"),(12,5,"Father's Day"),(12,10,"Constitution Day"),
            (12,31,"New Year's Eve"),
        ],
        "easter": False,
    },
    "SG": {
        "flag": "🇸🇬", "name": "Singapore",
        "locales": ["en_SG"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(8,9,"National Day"),
            (12,25,"Christmas Day"),
        ],
        "easter": True,
    },
    "HK": {
        "flag": "🇭🇰", "name": "Hong Kong",
        "locales": ["zh_HK"],
        "fixed": [
            (1,1,"New Year's Day"),(4,4,"Ching Ming Festival"),(5,1,"Labour Day"),
            (7,1,"HKSAR Establishment Day"),(10,1,"National Day"),(12,25,"Christmas Day"),
            (12,26,"Boxing Day"),
        ],
        "easter": True,
    },
    "ID": {
        "flag": "🇮🇩", "name": "Indonesia",
        "locales": ["id_ID", "id"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(6,1,"Pancasila Day"),
            (8,17,"Independence Day"),(12,25,"Christmas Day"),
        ],
        "easter": True,
    },
    "PH": {
        "flag": "🇵🇭", "name": "Philippines",
        "locales": ["en_PH", "fil_PH"],
        "fixed": [
            (1,1,"New Year's Day"),(4,9,"Araw ng Kagitingan"),(5,1,"Labour Day"),
            (6,12,"Independence Day"),(8,21,"Ninoy Aquino Day"),(8,26,"National Heroes Day"),
            (11,1,"All Saints' Day"),(11,30,"Bonifacio Day"),(12,8,"Immaculate Conception"),
            (12,25,"Christmas Day"),(12,30,"Rizal Day"),(12,31,"New Year's Eve"),
        ],
        "easter": True,
    },
    "CZ": {
        "flag": "🇨🇿", "name": "Czech Republic",
        "locales": ["cs_CZ", "cs"],
        "fixed": [
            (1,1,"New Year's Day"),(5,1,"Labour Day"),(5,8,"Liberation Day"),
            (7,5,"Saints Cyril and Methodius Day"),(7,6,"Jan Hus Day"),
            (9,28,"Czech Statehood Day"),(10,28,"Independence Day"),
            (11,17,"Struggle for Freedom Day"),(12,24,"Christmas Eve"),
            (12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
    },
    "HU": {
        "flag": "🇭🇺", "name": "Hungary",
        "locales": ["hu_HU", "hu"],
        "fixed": [
            (1,1,"New Year's Day"),(3,15,"1848 Revolution Day"),(5,1,"Labour Day"),
            (8,20,"St. Stephen's Day"),(10,23,"1956 Revolution Day"),
            (11,1,"All Saints' Day"),(12,25,"Christmas Day"),(12,26,"2nd Day of Christmas"),
        ],
        "easter": True,
    },
    "RO": {
        "flag": "🇷🇴", "name": "Romania",
        "locales": ["ro_RO", "ro"],
        "fixed": [
            (1,1,"New Year's Day"),(1,2,"New Year Holiday"),(1,24,"Unification Day"),
            (5,1,"Labour Day"),(6,1,"Children's Day"),(8,15,"Assumption of Mary"),
            (11,30,"St. Andrew's Day"),(12,1,"National Day"),
            (12,25,"Christmas Day"),(12,26,"2nd Christmas Day"),
        ],
        "easter": True,
    },
    "HR": {
        "flag": "🇭🇷", "name": "Croatia",
        "locales": ["hr_HR", "hr"],
        "fixed": [
            (1,1,"New Year's Day"),(1,6,"Epiphany"),(5,1,"Labour Day"),
            (5,30,"Statehood Day"),(6,22,"Anti-Fascist Resistance Day"),
            (8,5,"Victory Day"),(8,15,"Assumption of Mary"),
            (10,8,"Independence Day"),(11,1,"All Saints' Day"),
            (12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            ((easter_date(y)+timedelta(60)).month,(easter_date(y)+timedelta(60)).day,"Corpus Christi"),
        ],
    },
    "SK": {
        "flag": "🇸🇰", "name": "Slovakia",
        "locales": ["sk_SK", "sk"],
        "fixed": [
            (1,1,"Slovak Republic Day"),(1,6,"Epiphany"),(5,1,"Labour Day"),
            (5,8,"Liberation Day"),(7,5,"Saints Cyril and Methodius Day"),
            (8,29,"Slovak National Uprising Day"),(9,1,"Constitution Day"),
            (9,15,"Our Lady of Sorrows Day"),(11,1,"All Saints' Day"),
            (11,17,"Struggle for Freedom Day"),(12,24,"Christmas Eve"),
            (12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
    },
    "RS": {
        "flag": "🇷🇸", "name": "Serbia",
        "locales": ["sr_RS", "sr"],
        "fixed": [
            (1,1,"New Year's Day"),(1,2,"New Year Holiday"),(2,15,"Statehood Day"),
            (2,16,"Statehood Day Holiday"),(11,11,"Armistice Day"),(12,25,"Orthodox Christmas"),
        ],
        "easter": False,
    },
    "IE": {
        "flag": "🇮🇪", "name": "Ireland",
        "locales": ["en_IE"],
        "fixed": [
            (1,1,"New Year's Day"),(3,17,"St. Patrick's Day"),
            (8,7,"August Bank Holiday"),(10,28,"October Bank Holiday"),
            (12,25,"Christmas Day"),(12,26,"St. Stephen's Day"),
        ],
        "easter": True,
        "extra": lambda y: [
            (_nth_weekday(y,5,0,0).month,_nth_weekday(y,5,0,0).day,"May Bank Holiday"),
            (_nth_weekday(y,6,0,0).month,_nth_weekday(y,6,0,0).day,"June Bank Holiday"),
        ],
    },
}


def get_default_country() -> str:
    """Detect the local country from system locale, fallback to IT."""
    try:
        loc = _locale.getlocale()[0] or ""
        # Try to map locale code to country
        for code, info in COUNTRIES.items():
            for lc in info["locales"]:
                if loc.lower().startswith(lc.lower()):
                    return code
        # Try last 2 chars of locale (e.g. en_US -> US)
        if "_" in loc:
            country_code = loc.split("_")[-1].upper()[:2]
            if country_code in COUNTRIES:
                return country_code
    except Exception:
        pass
    return "IT"


def get_holidays(year: int, month: int, country: str = "IT") -> dict[date, str]:
    """Return all Sundays + public holidays for the given month/year/country."""
    info = COUNTRIES.get(country, COUNTRIES["IT"])
    result: dict[date, str] = {}

    # Fixed public holidays
    for (mo, dy, name) in info["fixed"]:
        if mo == month:
            try:
                result[date(year, mo, dy)] = name
            except ValueError:
                pass

    # Easter-based holidays
    if info.get("easter", False):
        easter = easter_date(year)
        easter_mon = easter + timedelta(days=1)
        if easter.month == month:
            result[easter] = "Easter Sunday"
        if easter_mon.month == month:
            result[easter_mon] = "Easter Monday"

    # Computed / dynamic holidays
    if "extra" in info:
        try:
            for (mo, dy, name) in info["extra"](year):
                if mo == month:
                    try:
                        result[date(year, mo, dy)] = name
                    except (ValueError, TypeError):
                        pass
        except Exception:
            pass

    # All Sundays of the month
    num_days = calendar.monthrange(year, month)[1]
    for day in range(1, num_days + 1):
        d = date(year, month, day)
        if d.weekday() == 6:
            if d not in result:
                result[d] = "Sunday"
            else:
                result[d] += " (Sunday)"

    return result


# ── Theme palettes  (same structure as LexiFinder) ───────────────────────────
#
# ONE interactive accent (ACCENT) + ONE error accent (ACCENT_ERR).
# Structural colours (backgrounds, text, borders) switch with the OS theme.

_DARK_PAL: dict[str, str] = {
    "page_bg":    "#121212",   # LexiFinder: page_bg
    "card_bg":    "#1E1E1E",   # LexiFinder: nav_bg
    "input_bg":   "#2A2A2A",
    "border":     "#3A3A3A",
    "text_pri":   "#EEEEEE",
    "text_sec":   "#AAAAAA",   # LexiFinder: muted
    "drawer_bg":  "#181818",
    "accent":     "#90CAF9",   # LexiFinder dark accent – light blue
    "accent_err": "#EF5350",   # error / destructive
    "seed":       "#90CAF9",
}

_LIGHT_PAL: dict[str, str] = {
    "page_bg":    "#F5F5F5",   # LexiFinder: page_bg
    "card_bg":    "#FFFFFF",   # LexiFinder: log_inner_bg
    "input_bg":   "#EEEEEE",
    "border":     "#DDDDDD",
    "text_pri":   "#1A1A1A",
    "text_sec":   "#555555",   # LexiFinder: muted (light)
    "drawer_bg":  "#E8EAF6",   # LexiFinder: nav_bg (light)
    "accent":     "#1565C0",   # LexiFinder light accent – dark blue
    "accent_err": "#C62828",   # error / destructive
    "seed":       "#1565C0",
}

# Module-level colour aliases – reassigned by _apply_theme() at runtime.
# Start with dark values so module-level widget helpers have valid defaults
# before the first _apply_theme() call.
DARK_BG    = _DARK_PAL["page_bg"]
CARD_BG    = _DARK_PAL["card_bg"]
INPUT_BG   = _DARK_PAL["input_bg"]
BORDER_COL = _DARK_PAL["border"]
TEXT_PRI   = _DARK_PAL["text_pri"]
TEXT_SEC   = _DARK_PAL["text_sec"]
DRAWER_BG  = _DARK_PAL["drawer_bg"]
ACCENT     = _DARK_PAL["accent"]       # single interactive accent
ACCENT_ERR = _DARK_PAL["accent_err"]   # errors / destructive actions


# ── Reusable widget helpers ─────────────────────────────────────────────────

def section_title(text: str) -> ft.Text:
    return ft.Text(text, size=13, weight=ft.FontWeight.W_600,
                   color=TEXT_SEC)


def card(content, padding=20) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=CARD_BG,
        border_radius=16,
        padding=padding,
        border=ft.Border.all(1, BORDER_COL),
    )


def pill_badge(label: str, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.W_600),
        bgcolor=f"{color}22",
        border_radius=20,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border=ft.Border.all(1, f"{color}55"),
    )


# ── Page 1 – Days Between Dates ────────────────────────────────────────────

class DaysBetweenPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0,
                         expand=True)
        self._start: date | None = None
        self._end:   date | None = None

        # ---- date pickers (invisible, triggered by buttons) ----
        self.start_picker = ft.DatePicker(on_change=self._on_start_pick)
        self.end_picker   = ft.DatePicker(on_change=self._on_end_pick)

        # ---- display fields ----
        self.start_label = ft.Text("Not selected", color=TEXT_SEC, size=15)
        self.end_label   = ft.Text("Not selected", color=TEXT_SEC, size=15)

        # ---- result area ----
        self.result_days  = ft.Text("—", size=56, weight=ft.FontWeight.BOLD,
                                    color=ACCENT, text_align=ft.TextAlign.CENTER)
        self.result_sub   = ft.Text("", size=13, color=TEXT_SEC,
                                    text_align=ft.TextAlign.CENTER)
        self.result_card  = ft.Container(visible=False)

        # ---- inline error text ----
        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_inputs(),
            ft.Container(height=20),
            self._build_result_section(),
        ]

    # ---- header ----
    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.DATE_RANGE_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10,
                    padding=10,
                ),
                ft.Column([
                    ft.Text("Days Between Dates", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Calculate the gap between two dates",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ---- inputs ----
    def _date_row(self, label: str, icon: str, display_text: ft.Text,
                  on_click) -> ft.Container:
        return card(ft.Column([
            section_title(label),
            ft.Container(height=10),
            ft.Container(
                content=ft.Row([
                    ft.Icon(icon, color=ACCENT, size=20),
                    ft.Container(width=12),
                    display_text,
                    ft.Container(expand=True),
                    ft.TextButton("Change", on_click=on_click,
                                  style=ft.ButtonStyle(color=ACCENT)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=INPUT_BG, border_radius=12, padding=14,
                border=ft.Border.all(1, BORDER_COL),
                on_click=on_click, ink=True,
            ),
        ], spacing=0))

    def _build_inputs(self):
        return ft.Container(
            content=ft.Column([
                self._date_row("START DATE", ft.Icons.FLIGHT_TAKEOFF_ROUNDED,
                               self.start_label, self._open_start),
                ft.Container(height=12),
                self._date_row("END DATE", ft.Icons.FLIGHT_LAND_ROUNDED,
                               self.end_label, self._open_end),
                ft.Container(height=20),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=18),
                        ft.Text("Calculate", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8,
                       alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._calculate,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT, color=TEXT_PRI,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=8),
                ft.OutlinedButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                        ft.Text("Reset", size=13),
                    ], spacing=6,
                       alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._reset,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, BORDER_COL),
                        color=TEXT_SEC,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=12),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=4),
                self.error_text,
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ---- result ----
    def _build_result_section(self):
        self.result_card = card(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.INSIGHTS_ROUNDED, color=ACCENT, size=18),
                    ft.Text("Result", size=14, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),
                self.result_days,
                ft.Text("days", size=16, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER, weight=ft.FontWeight.W_500),
                ft.Container(height=8),
                self.result_sub,
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = False
        return ft.Container(
            content=self.result_card,
            padding=ft.Padding(left=20, top=0, right=20, bottom=30),
        )

    # ---- events ----
    def did_mount(self):
        self.page.overlay.append(self.start_picker)
        self.page.overlay.append(self.end_picker)
        self.page.update()

    def will_unmount(self):
        if self.start_picker in self.page.overlay:
            self.page.overlay.remove(self.start_picker)
        if self.end_picker in self.page.overlay:
            self.page.overlay.remove(self.end_picker)
        # NOTE: do NOT call page.update() here – switch_page() already does it,
        # and a second update mid-navigation causes a race condition on Android.

    def _open_start(self, _):
        self.start_picker.open = True
        # NOTE: no page.update() here – switch_page() already calls it.

    def _open_end(self, _):
        self.end_picker.open = True
        self.page.update()

    def _on_start_pick(self, e):
        if e.control.value:
            self._start = _picker_to_date(e.control.value)
            self.start_label.value = self._start.strftime("%d %B %Y")
            self.start_label.color = TEXT_PRI
            self.update()

    def _on_end_pick(self, e):
        if e.control.value:
            self._end = _picker_to_date(e.control.value)
            self.end_label.value = self._end.strftime("%d %B %Y")
            self.end_label.color = TEXT_PRI
            self.update()

    def _calculate(self, _):
        if not self._start or not self._end:
            self.error_text.value   = "⚠️  Please select both dates."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return
        self.error_text.visible = False
        delta = self._end - self._start
        days  = abs(delta.days)
        weeks, rem = divmod(days, 7)
        months = round(days / 30.44, 1)
        years  = round(days / 365.25, 2)
        direction = "ahead" if delta.days >= 0 else "ago"
        self.result_days.value = str(days)
        self.result_sub.value  = (
            f"≈ {weeks}w {rem}d  •  ≈ {months} months  •  ≈ {years} years\n"
            f"{self._end.strftime('%d %b %Y')} is {direction} of "
            f"{self._start.strftime('%d %b %Y')}"
        )
        self.result_card.visible = True
        self.update()

    def _reset(self, _):
        self._start = self._end = None
        self.start_label.value = "Not selected"
        self.end_label.value   = "Not selected"
        self.start_label.color = TEXT_SEC
        self.end_label.color   = TEXT_SEC
        self.result_card.visible = False
        self.error_text.visible  = False
        self.update()


# ── Page 2 – Monthly Holidays ──────────────────────────────────────────────

class HolidaysPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        today = date.today()
        self._year    = today.year
        self._month   = today.month
        self._country = get_default_country()

        self.month_dd = ft.Dropdown(
            options=[ft.dropdown.Option(str(i), calendar.month_name[i])
                     for i in range(1, 13)],
            value=str(self._month),
            bgcolor=INPUT_BG, color=TEXT_PRI,
            border_radius=12,
            expand=True,
        )
        self.year_field = ft.TextField(
            value=str(self._year),
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            border_color=BORDER_COL,
            focused_border_color=ACCENT,
            border_radius=12,
            text_align=ft.TextAlign.CENTER,
            text_size=15,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=14),
        )
        # Country dropdown – sorted by display name, flag + name in label
        sorted_countries = sorted(COUNTRIES.items(), key=lambda x: x[1]["name"])
        self.country_dd = ft.Dropdown(
            options=[
                ft.dropdown.Option(code, f"{info['flag']}  {info['name']}")
                for code, info in sorted_countries
            ],
            value=self._country,
            bgcolor=INPUT_BG, color=TEXT_PRI,
            border_radius=12,
            expand=True,   # ← stretch to full card width on Android
        )

        self.holiday_list = ft.Column(spacing=10)
        self.count_badge  = ft.Text("", color=TEXT_SEC, size=13)
        self.year_error   = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_selectors(),
            ft.Container(height=20),
            ft.Container(
                content=self.holiday_list,
                padding=ft.Padding.symmetric(horizontal=20),
            ),
            ft.Container(height=30),
        ]
        self._refresh()

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.CELEBRATION_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10,
                    padding=10,
                ),
                ft.Column([
                    ft.Text("Monthly Holidays", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Public holidays by month",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    def _build_selectors(self):
        return ft.Container(
            content=ft.Column([
                section_title("COUNTRY"),
                ft.Container(height=8),
                self.country_dd,
                ft.Container(height=16),
                section_title("SELECT PERIOD"),
                ft.Container(height=8),
                ft.Row([
                    ft.Container(content=self.month_dd,   expand=1),
                    ft.Container(content=self.year_field, expand=1),
                ], spacing=12),
                ft.Container(height=4),
                self.year_error,
                ft.Container(height=12),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SEARCH_ROUNDED, size=18),
                        ft.Text("Show Holidays", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8,
                       alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._on_calculate,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT,
                        color=TEXT_PRI,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=12),
                ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED,
                            color=TEXT_SEC, size=14),
                    self.count_badge,
                ], spacing=6),
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    def _make_holiday_tile(self, d: date, name: str) -> ft.Container:
        weekday  = d.strftime("%A")
        day_num  = d.strftime("%d")
        month_s  = d.strftime("%b")
        today    = date.today()
        is_past  = d < today
        is_today = d == today
        is_sunday = "Sunday" in name and name.strip() == "Sunday"

        # Color scheme: pink=today, purple=public holiday, blue=sunday, grey=past
        if is_today:
            chip_color = ACCENT
            border_col = f"{ACCENT}88"
        elif is_past:
            chip_color = TEXT_SEC
            border_col = BORDER_COL
        elif is_sunday:
            chip_color = ACCENT
            border_col = f"{ACCENT}33"
        else:
            chip_color = ACCENT
            border_col = f"{ACCENT}44"

        status_label = "Today" if is_today else ("Past" if is_past else "Upcoming")

        # Type badge
        if is_sunday:
            type_icon = ft.Icons.WB_SUNNY_OUTLINED
            type_label = "Sunday"
            type_color = ACCENT
        else:
            type_icon = ft.Icons.CELEBRATION_OUTLINED
            type_label = "Public Holiday"
            type_color = ACCENT if not is_past else TEXT_SEC

        return ft.Container(
            content=ft.Row([
                # day chip
                ft.Container(
                    content=ft.Column([
                        ft.Text(day_num, size=22, weight=ft.FontWeight.BOLD,
                                color=chip_color, text_align=ft.TextAlign.CENTER),
                        ft.Text(month_s, size=11, color=TEXT_SEC,
                                text_align=ft.TextAlign.CENTER),
                    ], spacing=0,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    bgcolor=f"{chip_color}18", border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    width=62,
                ),
                ft.Container(width=14),
                # details
                ft.Column([
                    ft.Text(name, size=15, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                    ft.Row([
                        ft.Icon(ft.Icons.SCHEDULE_ROUNDED, color=TEXT_SEC, size=13),
                        ft.Text(weekday, size=12, color=TEXT_SEC),
                        ft.Container(width=6),
                        pill_badge(status_label, chip_color),
                        ft.Container(width=4),
                        pill_badge(type_label, type_color),
                    ], spacing=4, wrap=True),
                ], spacing=4, expand=True),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=CARD_BG,
            border_radius=14,
            padding=14,
            border=ft.Border.all(1, border_col),
        )

    def _refresh(self):
        holidays = get_holidays(self._year, self._month, self._country)
        self.holiday_list.controls.clear()

        sundays = sum(1 for name in holidays.values() if "Sunday" in name)
        public  = len(holidays) - sundays

        if not holidays:
            self.holiday_list.controls.append(
                card(ft.Row([
                    ft.Icon(ft.Icons.SENTIMENT_SATISFIED_ALT,
                            color=TEXT_SEC, size=28),
                    ft.Text("No holidays this month.",
                            color=TEXT_SEC, size=14),
                ], spacing=14))
            )
            self.count_badge.value = "Nothing found"
        else:
            for d in sorted(holidays):
                self.holiday_list.controls.append(
                    self._make_holiday_tile(d, holidays[d])
                )
            self.count_badge.value = (
                f"{public} public holiday{'s' if public != 1 else ''}  •  "
                f"{sundays} Sunday{'s' if sundays != 1 else ''}"
            )

    def _on_calculate(self, _):
        raw = (self.year_field.value or "").strip()
        try:
            year = int(raw)
            if not (1 <= year <= 9999):
                raise ValueError
        except ValueError:
            self.year_error.value   = "⚠️  Enter a valid year (e.g. 2025)."
            self.year_error.visible = True
            self.update()
            return
        self.year_error.visible = False
        self._month   = int(self.month_dd.value)
        self._year    = year
        self._country = self.country_dd.value or "IT"
        self._refresh()
        self.update()



# ── Page 3 – Add / Subtract Days ──────────────────────────────────────────

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEEKDAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]



class AddSubtractPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)
        self._base: date | None = None

        # ── Load persisted settings ──────────────────────────────────────────
        cfg = load_settings()
        self._work_days: set[int]  = set(cfg["work_days"])
        self._excl_holidays: bool  = bool(cfg["excl_holidays"])
        self._working_only: bool   = bool(cfg["working_only"])
        self._country: str         = cfg["country"] or get_default_country()

        # Date picker
        self.date_picker = ft.DatePicker(on_change=self._on_date_pick)

        # Base date label
        self.base_label = ft.Text("Not selected", color=TEXT_SEC, size=15)

        # Days input
        self.days_field = ft.TextField(
            value="1",
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            border_color=BORDER_COL,
            focused_border_color=ACCENT,
            border_radius=12,
            text_align=ft.TextAlign.CENTER,
            text_size=18,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        )

        # Add / Subtract toggle – both OutlinedButton; style alone drives active state
        self._operation = "add"
        self.btn_add = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.ADD_ROUNDED, size=16),
                            ft.Text("Add", size=13, weight=ft.FontWeight.W_600)],
                           spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda _: self._set_op("add"),
            style=ft.ButtonStyle(
                bgcolor=ACCENT, color=DARK_BG,
                side=ft.BorderSide(1, ACCENT),
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(vertical=12),
            ),
            expand=True,
        )
        self.btn_sub = ft.OutlinedButton(
            content=ft.Row([ft.Icon(ft.Icons.REMOVE_ROUNDED, size=16),
                            ft.Text("Subtract", size=13, weight=ft.FontWeight.W_600)],
                           spacing=6, alignment=ft.MainAxisAlignment.CENTER),
            on_click=lambda _: self._set_op("sub"),
            style=ft.ButtonStyle(
                side=ft.BorderSide(1, BORDER_COL),
                color=TEXT_SEC,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(vertical=12),
            ),
            expand=True,
        )

        # Inline error text (shown when Calculate pressed without a base date)
        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        # Working days toggle – restored from settings
        self.working_switch = ft.Switch(
            value=self._working_only,
            active_color=ACCENT,
            on_change=self._on_working_toggle,
        )

        # Weekday checkboxes – restored from settings
        self.day_checks = []
        for i in range(7):
            chk = ft.Checkbox(
                value=(i in self._work_days),
                active_color=ACCENT,
                on_change=lambda e, idx=i: self._on_day_check(e, idx),
            )
            self.day_checks.append(chk)

        # Country dropdown – restored from settings
        sorted_countries = sorted(COUNTRIES.items(), key=lambda x: x[1]["name"])
        self.country_dd = ft.Dropdown(
            options=[
                ft.dropdown.Option(code, f"{info['flag']}  {info['name']}")
                for code, info in sorted_countries
            ],
            value=self._country,
            bgcolor=INPUT_BG, color=TEXT_PRI,
            border_radius=12,
        )
        self.country_dd.on_change = self._on_country_change

        # Exclude-holidays toggle – restored from settings
        self.holiday_switch = ft.Switch(
            value=self._excl_holidays,
            active_color=ACCENT,
            on_change=self._on_holiday_toggle,
        )

        # Options container (shown/hidden by working_switch)
        self.options_card = ft.Container(visible=False)

        # Result
        self.result_date_text = ft.Text("", size=32, weight=ft.FontWeight.BOLD,
                                        color=ACCENT,
                                        text_align=ft.TextAlign.CENTER)
        self.result_sub_text  = ft.Text("", size=13, color=TEXT_SEC,
                                        text_align=ft.TextAlign.CENTER)
        self.result_card = ft.Container(visible=False)

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_inputs(),
            ft.Container(height=16),
            self._build_options(),
            ft.Container(height=20),
            self._build_result(),
        ]

        # Restore expanded options panel if working_only was saved as True
        if self._working_only:
            self.options_card.content = self._build_options_content()
            self.options_card.visible = True

    # ── header ────────────────────────────────────────────────────────────────

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.EDIT_CALENDAR_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Add / Subtract Days", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Calculate a future or past date",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── inputs ────────────────────────────────────────────────────────────────

    def _build_inputs(self):
        return ft.Container(
            content=ft.Column([
                # Base date
                card(ft.Column([
                    section_title("BASE DATE"),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED,
                                    color=ACCENT, size=20),
                            ft.Container(width=12),
                            self.base_label,
                            ft.Container(expand=True),
                            ft.TextButton("Change",
                                          on_click=self._open_picker,
                                          style=ft.ButtonStyle(color=ACCENT)),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=INPUT_BG, border_radius=12, padding=14,
                        border=ft.Border.all(1, BORDER_COL),
                        on_click=self._open_picker, ink=True,
                    ),
                ], spacing=0)),
                ft.Container(height=12),
                # Number of days
                card(ft.Column([
                    section_title("NUMBER OF DAYS"),
                    ft.Container(height=10),
                    self.days_field,
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
                ft.Container(height=12),
                # Add / Subtract toggle
                card(ft.Column([
                    section_title("OPERATION"),
                    ft.Container(height=10),
                    ft.Row([self.btn_add, self.btn_sub], spacing=10),
                ], spacing=0)),
                ft.Container(height=20),
                # Calculate button
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=18),
                        ft.Text("Calculate", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._calculate,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT, color=DARK_BG,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=8),
                ft.OutlinedButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                        ft.Text("Reset", size=13),
                    ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._reset,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, BORDER_COL),
                        color=TEXT_SEC,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=12),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=4),
                self.error_text,
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── options card ──────────────────────────────────────────────────────────

    def _weekday_row(self):
        chips = []
        for i, (short, chk) in enumerate(zip(WEEKDAY_SHORT, self.day_checks)):
            is_weekend = i >= 5
            chips.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(short, size=11, color=TEXT_SEC,
                                text_align=ft.TextAlign.CENTER),
                        chk,
                    ], spacing=2,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    expand=True,
                )
            )
        return ft.Row(chips, spacing=4)

    def _build_options(self):
        inner = card(ft.Column([
            # Working days toggle
            ft.Row([
                ft.Icon(ft.Icons.WORK_ROUNDED, color=ACCENT, size=18),
                ft.Text("Working days only", size=14,
                        color=TEXT_PRI, weight=ft.FontWeight.W_500,
                        expand=True),
                self.working_switch,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),

            # Options (weekday selector + holiday) – shown only when switch ON
            self.options_card,
        ], spacing=0))

        return ft.Container(
            content=inner,
            padding=ft.Padding.symmetric(horizontal=20),
        )

    def _build_options_content(self):
        """Build the expanded options shown when working days is ON."""
        return ft.Column([
            ft.Divider(height=20, color=BORDER_COL),
            section_title("WORKING DAYS"),
            ft.Container(height=10),
            self._weekday_row(),
            ft.Divider(height=20, color=BORDER_COL),
            # Exclude holidays
            ft.Row([
                ft.Icon(ft.Icons.CELEBRATION_ROUNDED, color=ACCENT, size=18),
                ft.Text("Exclude public holidays", size=14,
                        color=TEXT_PRI, weight=ft.FontWeight.W_500,
                        expand=True),
                self.holiday_switch,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=12),
            section_title("COUNTRY FOR HOLIDAYS"),
            ft.Container(height=8),
            self.country_dd,
        ], spacing=0)

    # ── result ────────────────────────────────────────────────────────────────

    def _build_result(self):
        self.result_card = card(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, color=ACCENT, size=18),
                    ft.Text("Result", size=14, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),
                self.result_date_text,
                ft.Container(height=4),
                self.result_sub_text,
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = False
        return ft.Container(
            content=self.result_card,
            padding=ft.Padding(left=20, top=0, right=20, bottom=30),
        )

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def did_mount(self):
        self.page.overlay.append(self.date_picker)
        self.page.update()

    def will_unmount(self):
        if self.date_picker in self.page.overlay:
            self.page.overlay.remove(self.date_picker)
        # NOTE: no page.update() here – switch_page() already calls it.

    # ── event handlers ────────────────────────────────────────────────────────

    def _open_picker(self, _):
        self.date_picker.open = True
        self.page.update()

    def _on_date_pick(self, e):
        if e.control.value:
            v = e.control.value
            self._base = _picker_to_date(v)
            self.base_label.value = self._base.strftime("%d %B %Y")
            self.base_label.color = TEXT_PRI
            self.error_text.visible = False   # clear "no date" warning
            self.update()

    def _set_op(self, op: str):
        self._operation = op
        _active   = ft.ButtonStyle(
            bgcolor=ACCENT, color=DARK_BG,
            side=ft.BorderSide(1, ACCENT),
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(vertical=12),
        )
        _inactive = ft.ButtonStyle(
            bgcolor=ft.Colors.TRANSPARENT, color=TEXT_SEC,
            side=ft.BorderSide(1, BORDER_COL),
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(vertical=12),
        )
        self.btn_add.style = _active   if op == "add" else _inactive
        self.btn_sub.style = _active   if op == "sub" else _inactive
        self.update()

    # ── settings persistence ──────────────────────────────────────────────────

    def _persist(self):
        """Write current user preferences to disk."""
        save_settings({
            "work_days":      sorted(self._work_days),
            "excl_holidays":  self._excl_holidays,
            "working_only":   self._working_only,
            "country":        self._country,
        })

    def _on_working_toggle(self, e):
        self._working_only = e.control.value
        if self._working_only:
            self.options_card.content = self._build_options_content()
            self.options_card.visible = True
        else:
            self.options_card.visible = False
        self._persist()
        self.update()

    def _on_holiday_toggle(self, e):
        self._excl_holidays = e.control.value
        self._persist()

    def _on_day_check(self, e, idx: int):
        if e.control.value:
            self._work_days.add(idx)
        else:
            self._work_days.discard(idx)
        self._persist()

    def _on_country_change(self, e):
        self._country = e.control.value or "IT"
        self._persist()

    def _calculate(self, _):
        if not self._base:
            self.error_text.value   = "⚠️  Please select a base date."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return
        self.error_text.visible = False
        try:
            n_days = int(self.days_field.value or "0")
        except ValueError:
            self.error_text.value   = "⚠️  Please enter a valid number of days."
            self.error_text.visible = True
            self.update()
            return
        if n_days < 0:
            n_days = abs(n_days)

        if self._operation == "sub":
            n_days = -n_days

        if not self._working_only:
            result_date = self._base + timedelta(days=n_days)
            skipped_info = ""
        else:
            if not self._work_days:
                self.error_text.value   = "⚠️  Select at least one working day."
                self.error_text.visible = True
                self.update()
                return
            result_date, skipped = self._add_working_days(self._base, n_days)
            holiday_count = sum(1 for d in skipped
                                if d.weekday() in self._work_days)
            weekend_count = len(skipped) - holiday_count
            skipped_info = (
                f"Skipped: {weekend_count} weekend day(s)"
                + (f", {holiday_count} holiday(s)" if self._excl_holidays else "")
            )

        op_word = "after" if n_days >= 0 else "before"
        abs_days = abs(n_days)
        self.result_date_text.value = result_date.strftime("%d %B %Y")
        mode = "working " if self._working_only else ""
        self.result_sub_text.value = (
            f"{abs_days} {mode}day(s) {op_word} {self._base.strftime('%d %b %Y')}"
            + (f"\n{skipped_info}" if skipped_info else "")
        )
        self.result_card.visible = True
        self.update()

    def _add_working_days(self, start: date, n: int):
        """Walk n working days (positive=forward, negative=backward) from start."""
        step     = 1 if n >= 0 else -1
        remaining = abs(n)
        current  = start
        skipped: list[date] = []

        # Pre-build holiday set for years we might visit
        years_seen: set[int] = set()
        holiday_dates: set[date] = set()

        def ensure_year(y):
            if y not in years_seen:
                years_seen.add(y)
                if self._excl_holidays:
                    country = self.country_dd.value or "IT"
                    for mo in range(1, 13):
                        for d in get_holidays(y, mo, country):
                            # only fixed/public, not Sundays
                            name = get_holidays(y, mo, country)[d]
                            if "Sunday" not in name:
                                holiday_dates.add(d)

        ensure_year(start.year)

        while remaining > 0:
            current = current + timedelta(days=step)
            ensure_year(current.year)
            is_workday = current.weekday() in self._work_days
            is_holiday = current in holiday_dates
            if is_workday and not is_holiday:
                remaining -= 1
            else:
                skipped.append(current)

        return current, skipped

    def _reset(self, _):
        self._base = None
        self.base_label.value  = "Not selected"
        self.base_label.color  = TEXT_SEC
        self.days_field.value  = "1"
        self.error_text.visible = False
        self.result_card.visible = False
        self._set_op("add")
        self.update()



# ── Page 3b – Working Days Between Dates ─────────────────────────────────────




class WorkingDaysPage(ft.Column):
    """
    Calculates the number of working days between two dates.
    Shares work_days / excl_holidays / country settings with AddSubtractPage
    (same settings.json keys), and reloads them each time the page is shown.
    """

    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        self._start: date | None = None
        self._end:   date | None = None

        # Load shared settings
        cfg = load_settings()
        self._work_days:     set[int] = set(cfg["work_days"])
        self._excl_holidays: bool     = bool(cfg["excl_holidays"])
        self._country:       str      = cfg["country"] or get_default_country()

        # Two date pickers
        self.start_picker = ft.DatePicker(on_change=self._on_start_pick)
        self.end_picker   = ft.DatePicker(on_change=self._on_end_pick)

        # Date labels
        self.start_label = ft.Text("Not selected", color=TEXT_SEC, size=15)
        self.end_label   = ft.Text("Not selected", color=TEXT_SEC, size=15)

        # Weekday checkboxes (Mon–Sun)
        self.day_checks: list[ft.Checkbox] = []
        for i in range(7):
            chk = ft.Checkbox(
                value=(i in self._work_days),
                active_color=ACCENT,
                on_change=lambda e, idx=i: self._on_day_check(e, idx),
            )
            self.day_checks.append(chk)

        # Country dropdown
        sorted_countries = sorted(COUNTRIES.items(), key=lambda x: x[1]["name"])
        self.country_dd = ft.Dropdown(
            options=[
                ft.dropdown.Option(code, f"{info['flag']}  {info['name']}")
                for code, info in sorted_countries
            ],
            value=self._country,
            bgcolor=INPUT_BG, color=TEXT_PRI,
            border_radius=12,
        )
        self.country_dd.on_change = self._on_country_change

        # Exclude-holidays toggle
        self.holiday_switch = ft.Switch(
            value=self._excl_holidays,
            active_color=ACCENT,
            on_change=self._on_holiday_toggle,
        )

        # Result area
        self.result_card = ft.Container(visible=False)

        # Inline error text
        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            ft.Container(
                content=ft.Column([
                    self._build_date_section(),
                    ft.Container(height=16),
                    self._build_work_days_section(),
                    ft.Container(height=20),
                    self._build_buttons(),
                    ft.Container(height=20),
                    self.result_card,
                    ft.Container(height=30),
                ], spacing=0),
                padding=ft.Padding.symmetric(horizontal=20),
            ),
        ]

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def did_mount(self):
        # Register date pickers
        self.page.overlay.extend([self.start_picker, self.end_picker])
        # Inline settings sync (avoids a second self.update() call that would
        # race with the navigation update on Android).
        cfg = load_settings()
        self._work_days     = set(cfg["work_days"])
        self._excl_holidays = bool(cfg["excl_holidays"])
        self._country       = cfg["country"] or get_default_country()
        for i, chk in enumerate(self.day_checks):
            chk.value = (i in self._work_days)
        self.holiday_switch.value = self._excl_holidays
        self.country_dd.value     = self._country
        # Single page.update() covers both overlay registration and UI sync.
        self.page.update()

    def will_unmount(self):
        for p in (self.start_picker, self.end_picker):
            if p in self.page.overlay:
                self.page.overlay.remove(p)
        # NOTE: no page.update() here – switch_page() already calls it.

    def _sync_settings(self):
        """Re-read settings.json and update all controls to match."""
        cfg = load_settings()
        self._work_days     = set(cfg["work_days"])
        self._excl_holidays = bool(cfg["excl_holidays"])
        self._country       = cfg["country"] or get_default_country()
        # Sync checkboxes
        for i, chk in enumerate(self.day_checks):
            chk.value = (i in self._work_days)
        # Sync switches and dropdown
        self.holiday_switch.value = self._excl_holidays
        self.country_dd.value     = self._country
        self.update()

    # ── header ────────────────────────────────────────────────────────────────

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.WORK_HISTORY_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Working Days", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Count working days between two dates",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── date section ──────────────────────────────────────────────────────────

    def _date_row(self, icon_color, label_ctrl, open_fn):
        return ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED,
                        color=icon_color, size=20),
                ft.Container(width=12),
                label_ctrl,
                ft.Container(expand=True),
                ft.TextButton(
                    "Change",
                    on_click=open_fn,
                    style=ft.ButtonStyle(color=icon_color),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG, border_radius=12, padding=14,
            border=ft.Border.all(1, BORDER_COL),
            on_click=open_fn, ink=True,
        )

    def _build_date_section(self):
        return card(ft.Column([
            section_title("DATE RANGE"),
            ft.Container(height=10),
            ft.Text("Start date", size=12, color=TEXT_SEC),
            ft.Container(height=6),
            self._date_row(ACCENT, self.start_label, self._open_start),
            ft.Container(height=12),
            ft.Text("End date", size=12, color=TEXT_SEC),
            ft.Container(height=6),
            self._date_row(ACCENT, self.end_label, self._open_end),
        ], spacing=0))

    # ── work days section ─────────────────────────────────────────────────────

    def _weekday_row(self):
        chips = []
        for i, (short, chk) in enumerate(zip(WEEKDAY_SHORT, self.day_checks)):
            chips.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(short, size=11, color=TEXT_SEC,
                                text_align=ft.TextAlign.CENTER),
                        chk,
                    ], spacing=2,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    expand=True,
                )
            )
        return ft.Row(chips, spacing=4)

    def _build_work_days_section(self):
        return card(ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.WORK_ROUNDED, color=ACCENT, size=18),
                ft.Text("Working days of the week", size=14,
                        color=TEXT_PRI, weight=ft.FontWeight.W_500),
            ], spacing=8),
            ft.Container(height=12),
            self._weekday_row(),
            ft.Divider(height=20, color=BORDER_COL),
            # Exclude holidays row
            ft.Row([
                ft.Icon(ft.Icons.CELEBRATION_ROUNDED, color=ACCENT, size=18),
                ft.Text("Exclude public holidays", size=14,
                        color=TEXT_PRI, weight=ft.FontWeight.W_500,
                        expand=True),
                self.holiday_switch,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=12),
            section_title("COUNTRY FOR HOLIDAYS"),
            ft.Container(height=8),
            self.country_dd,
        ], spacing=0))

    # ── buttons ───────────────────────────────────────────────────────────────

    def _build_buttons(self):
        return ft.Column([
            ft.FilledButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=18),
                    ft.Text("Calculate", size=15, weight=ft.FontWeight.W_600),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                on_click=self._calculate,
                style=ft.ButtonStyle(
                    bgcolor=ACCENT, color=DARK_BG,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(vertical=14),
                ),
                width=float("inf"),
            ),
            ft.Container(height=8),
            ft.OutlinedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                    ft.Text("Reset", size=13),
                ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                on_click=self._reset,
                style=ft.ButtonStyle(
                    side=ft.BorderSide(1, BORDER_COL),
                    color=TEXT_SEC,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(vertical=12),
                ),
                width=float("inf"),
            ),
            ft.Container(height=4),
            self.error_text,
        ], spacing=0)

    # ── event handlers ────────────────────────────────────────────────────────

    def _open_start(self, _=None):
        self.start_picker.open = True
        # NOTE: no page.update() here – switch_page() already calls it.

    def _open_end(self, _=None):
        self.end_picker.open = True
        self.page.update()

    def _on_start_pick(self, e):
        if e.control.value:
            self._start = _picker_to_date(e.control.value)
            self.start_label.value = self._start.strftime("%d %B %Y")
            self.start_label.color = TEXT_PRI
            self.update()

    def _on_end_pick(self, e):
        if e.control.value:
            self._end = _picker_to_date(e.control.value)
            self.end_label.value = self._end.strftime("%d %B %Y")
            self.end_label.color = TEXT_PRI
            self.update()

    def _on_day_check(self, e, idx: int):
        if e.control.value:
            self._work_days.add(idx)
        else:
            self._work_days.discard(idx)
        self._persist()

    def _on_holiday_toggle(self, e):
        self._excl_holidays = e.control.value
        self._persist()

    def _on_country_change(self, e):
        self._country = e.control.value or "IT"
        self._persist()

    def _persist(self):
        """Save current work-days prefs – same keys as AddSubtractPage."""
        cfg = load_settings()
        cfg["work_days"]     = sorted(self._work_days)
        cfg["excl_holidays"] = self._excl_holidays
        cfg["country"]       = self._country
        save_settings(cfg)

    # ── calculation ───────────────────────────────────────────────────────────

    def _calculate(self, _=None):
        if not self._start or not self._end:
            self.error_text.value    = "⚠️  Please select both dates."
            self.error_text.visible  = True
            self.result_card.visible = False
            self.update()
            return

        if not self._work_days:
            self.error_text.value    = "⚠️  Select at least one working day."
            self.error_text.visible  = True
            self.result_card.visible = False
            self.update()
            return

        self.error_text.visible = False

        # Ensure start ≤ end
        start, end = (self._start, self._end) if self._start <= self._end \
                     else (self._end, self._start)
        swapped = self._start > self._end

        total_days     = (end - start).days + 1   # inclusive
        working_days   = 0
        weekend_days   = 0
        holiday_days   = 0

        # Build holiday set for all years in range
        holiday_dates: set[date] = set()
        if self._excl_holidays:
            for y in range(start.year, end.year + 1):
                for mo in range(1, 13):
                    for d, name in get_holidays(y, mo, self._country).items():
                        if "Sunday" not in name:
                            holiday_dates.add(d)

        current = start
        while current <= end:
            wd = current.weekday()
            if wd in self._work_days:
                if current in holiday_dates:
                    holiday_days += 1
                else:
                    working_days += 1
            else:
                weekend_days += 1
            current += timedelta(days=1)

        non_working = total_days - working_days
        weeks, rem  = divmod(working_days, len(self._work_days)) \
                      if self._work_days else (0, 0)
        months_approx = round(working_days / (len(self._work_days) * 52 / 12), 1) \
                        if self._work_days else 0.0

        range_label = (
            f"{start.strftime('%d %b %Y')} → {end.strftime('%d %b %Y')}"
            + (" (dates swapped)" if swapped else "")
        )

        # ── build result card ─────────────────────────────────────────────────
        chips_row = ft.Row([
            self._stat_chip("📆", str(total_days), "total days"),
            self._stat_chip("🚫", str(non_working),
                            "non-working" if not self._excl_holidays
                            else f"{weekend_days}wknd +\n{holiday_days}hol"),
        ], spacing=8)

        detail_rows = ft.Column([
            self._detail_row("📅", "Calendar days", str(total_days)),
            self._detail_row("🟢", "Working days", str(working_days)),
            self._detail_row("🔴", "Weekend days", str(weekend_days)),
        ] + ([
            self._detail_row("🎉", "Holiday days", str(holiday_days)),
        ] if self._excl_holidays else []) + [
            self._detail_row("≈", "Approx months", f"{months_approx} mo"),
        ], spacing=0)

        self.result_card.content = card(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.WORK_HISTORY_ROUNDED,
                            color=ACCENT, size=18),
                    ft.Text("Result", size=14, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),
                # Big number
                ft.Text(str(working_days), size=72,
                        weight=ft.FontWeight.BOLD, color=ACCENT,
                        text_align=ft.TextAlign.CENTER),
                ft.Text("working days", size=15, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_500),
                ft.Container(height=4),
                ft.Text(range_label, size=12, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=12),
                chips_row,
                ft.Divider(height=20, color=BORDER_COL),
                detail_rows,
            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = True
        self.update()

    def _stat_chip(self, emoji: str, value: str, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(emoji, size=20, text_align=ft.TextAlign.CENTER),
                ft.Text(value, size=16, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRI, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=10, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG, border_radius=12,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border=ft.Border.all(1, BORDER_COL),
            expand=True,
        )

    def _detail_row(self, icon: str, label: str, value: str) -> ft.Container:
        return ft.Container(
            content=ft.Row([
                ft.Text(icon, size=14),
                ft.Text(label, size=13, color=TEXT_SEC, expand=True),
                ft.Text(value, size=13, color=TEXT_PRI,
                        weight=ft.FontWeight.W_600),
            ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=7),
            border=ft.Border(
                bottom=ft.BorderSide(1, BORDER_COL)
            ),
        )

    def _reset(self, _=None):
        self._start = self._end = None
        self.start_label.value = self.end_label.value = "Not selected"
        self.start_label.color = self.end_label.color = TEXT_SEC
        self.result_card.visible = False
        self.error_text.visible  = False
        self.update()


# ── Page 4 – Birthday Countdown ───────────────────────────────────────────────




class BirthdayPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        cfg = load_settings()
        raw = cfg.get("birthday")
        self._birthday: date | None = None
        if raw:
            try:
                self._birthday = date.fromisoformat(raw)
            except (ValueError, TypeError):
                pass

        # DatePicker
        _today = date.today()
        self.date_picker = ft.DatePicker(
            on_change=self._on_date_pick,
            last_date=_today,   # cannot select a future date
        )

        # Display label for stored date of birth
        self.bday_label = ft.Text(
            self._birthday.strftime("%d %B %Y") if self._birthday else "Not set",
            color=TEXT_PRI if self._birthday else TEXT_SEC,
            size=15,
        )

        # Error text
        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        # Result area
        self.result_card = ft.Container(visible=False)
        self.result_content = ft.Column(
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_inputs(),
            ft.Container(height=20),
            ft.Container(
                content=self.result_card,
                padding=ft.Padding(left=20, top=0, right=20, bottom=30),
            ),
        ]

        # Auto-calculate if birthday already saved
        if self._birthday:
            self._run_calculation()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def did_mount(self):
        self.page.overlay.append(self.date_picker)
        self.page.update()

    def will_unmount(self):
        if self.date_picker in self.page.overlay:
            self.page.overlay.remove(self.date_picker)
        # NOTE: no page.update() here – switch_page() already calls it.

    # ── header ────────────────────────────────────────────────────────────────

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.CAKE_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Birthday Countdown", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Days until your next birthday",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── inputs ────────────────────────────────────────────────────────────────

    def _build_inputs(self):
        return ft.Container(
            content=ft.Column([
                card(ft.Column([
                    section_title("DATE OF BIRTH"),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PERSON_ROUNDED,
                                    color=ACCENT, size=20),
                            ft.Container(width=12),
                            self.bday_label,
                            ft.Container(expand=True),
                            ft.TextButton(
                                "Change",
                                on_click=self._open_picker,
                                style=ft.ButtonStyle(color=ACCENT),
                            ),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=INPUT_BG, border_radius=12, padding=14,
                        border=ft.Border.all(1, BORDER_COL),
                        on_click=self._open_picker, ink=True,
                    ),
                ], spacing=0)),
                ft.Container(height=20),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CELEBRATION_ROUNDED, size=18),
                        ft.Text("Calculate", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=lambda _: self._calculate(),
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT, color=TEXT_PRI,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=4),
                self.error_text,
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── events ────────────────────────────────────────────────────────────────

    def _open_picker(self, _):
        self.date_picker.open = True
        self.page.update()

    def _on_date_pick(self, e):
        if e.control.value:
            v = e.control.value
            picked = _picker_to_date(v)
            if picked > date.today():
                return   # safety guard (DatePicker last_date should prevent this)
            self._birthday = picked
            self.bday_label.value = picked.strftime("%d %B %Y")
            self.bday_label.color = TEXT_PRI
            # Persist full date (year is needed for age calculation)
            cfg = load_settings()
            cfg["birthday"] = picked.isoformat()
            save_settings(cfg)
            self.update()

    def _calculate(self):
        if not self._birthday:
            self.error_text.value   = "⚠️  Please select your date of birth first."
            self.error_text.visible = True
            self.update()
            return
        self.error_text.visible = False
        self._run_calculation()
        self.update()

    def _run_calculation(self):
        today = date.today()
        bday  = self._birthday

        # Next birthday this year or next
        try:
            next_bday = date(today.year, bday.month, bday.day)
        except ValueError:
            # Feb 29 on non-leap year → use Mar 1
            next_bday = date(today.year, 3, 1)

        if next_bday < today:
            try:
                next_bday = date(today.year + 1, bday.month, bday.day)
            except ValueError:
                next_bday = date(today.year + 1, 3, 1)

        days_left = (next_bday - today).days
        age_next  = next_bday.year - bday.year

        is_today  = days_left == 0
        weeks, rem = divmod(days_left, 7)
        months_approx = round(days_left / 30.44, 1)

        self.result_content.controls.clear()

        if is_today:
            self.result_content.controls += [
                ft.Container(
                    content=ft.Text("🎂", size=64,
                                    text_align=ft.TextAlign.CENTER),
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Text("Happy Birthday! 🎉",
                        size=26, weight=ft.FontWeight.BOLD,
                        color=ACCENT, text_align=ft.TextAlign.CENTER),
                ft.Text(f"You are turning {age_next} today!",
                        size=16, color=TEXT_PRI,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.Text("Have a wonderful day 🎊",
                        size=14, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ]
        else:
            self.result_content.controls += [
                ft.Text(str(days_left),
                        size=72, weight=ft.FontWeight.BOLD,
                        color=ACCENT, text_align=ft.TextAlign.CENTER),
                ft.Text("days to go",
                        size=16, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_500),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Column([
                        ft.Divider(color=BORDER_COL, height=1),
                        ft.Container(height=12),
                        ft.Row([
                            self._stat_chip("🗓️", f"{weeks}w {rem}d", "weeks & days"),
                            self._stat_chip("📅", f"≈{months_approx}mo", "months"),
                            self._stat_chip("🎂", f"{age_next}", "next age"),
                        ], spacing=8),
                        ft.Container(height=12),
                        ft.Text(
                            f"Your birthday: {next_bday.strftime('%A, %d %B %Y')}",
                            size=13, color=TEXT_SEC,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ], spacing=0,
                       horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.Padding.symmetric(horizontal=8),
                ),
            ]

        self.result_card.content = card(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.CAKE_ROUNDED, color=ACCENT, size=18),
                    ft.Text("Countdown", size=14,
                            weight=ft.FontWeight.W_600, color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),
                self.result_content,
            ], spacing=6,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = True

    def _stat_chip(self, emoji: str, value: str, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(emoji, size=20, text_align=ft.TextAlign.CENTER),
                ft.Text(value, size=16, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRI, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=11, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=2,
               horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border=ft.Border.all(1, BORDER_COL),
            expand=True,
        )



# ── Page 5 – Day of the Week ──────────────────────────────────────────────────


WEEKDAY_FULL  = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
WEEKDAY_EMOJI = ["💼","💼","💼","💼","💼","😴","😴"]   # weekday vs weekend

# ── Date-format options available in the UI ───────────────────────────────────
# key → (strptime_pattern, hint_example)
_FMT_OPTIONS: dict[str, tuple[str, str]] = {
    "DD/MM/YYYY": ("%d/%m/%Y", "e.g.  31/12/2025"),
    "MM/DD/YYYY": ("%m/%d/%Y", "e.g.  12/31/2025"),
    "YYYY-MM-DD": ("%Y-%m-%d", "e.g.  2025-12-31"),
}


def _detect_locale_fmt_key() -> str:
    """
    Return the _FMT_OPTIONS key that best matches the running system's locale.

    Strategy (in order):
      1. POSIX nl_langinfo(D_FMT) – available on Linux / macOS.
      2. Locale-name heuristic – covers Windows and Android.
      3. Hard fallback → DD/MM/YYYY.
    """
    try:
        # ── POSIX path ────────────────────────────────────────────────────────
        try:
            fmt = _locale.nl_langinfo(_locale.D_FMT)   # e.g. "%d/%m/%Y"
            if fmt.startswith("%Y"):
                return "YYYY-MM-DD"
            if fmt.startswith("%m"):
                return "MM/DD/YYYY"
            return "DD/MM/YYYY"
        except AttributeError:
            pass   # nl_langinfo not available on this platform

        # ── Locale-name heuristic ─────────────────────────────────────────────
        loc = (_locale.getlocale()[0] or "").upper()
        # Countries/languages that conventionally use M/D/Y
        if any(loc.startswith(p) for p in ("EN_US", "EN_PH", "EN_MH", "EN_FM")):
            return "MM/DD/YYYY"
        # East-Asian locales typically use Y-M-D
        if any(loc.startswith(p) for p in ("JA", "ZH", "KO", "MN")):
            return "YYYY-MM-DD"
    except Exception:
        pass

    return "DD/MM/YYYY"   # safe default


def _parse_with_fmt(text: str, fmt_key: str) -> date | None:
    """
    Parse *text* using only the field order implied by *fmt_key*.

    Accepts /, -, and . as interchangeable separators, plus a 2-digit year
    variant, but never guesses between DD/MM and MM/DD — that's the caller's
    responsibility (i.e. the user chose the format explicitly).

    The ISO key (YYYY-MM-DD) also accepts the unambiguous YYYY/MM/DD and
    YYYY.MM.DD variants.
    """
    text = text.strip()
    base = _FMT_OPTIONS[fmt_key][0]   # e.g. "%d/%m/%Y"

    # Build separator variants (same field order, different delimiter)
    patterns: list[str] = []
    for sep in ("/", "-", "."):
        patterns.append(base.replace("/", sep).replace("-", sep))
    # Also try 2-digit year (only meaningful for DMY / MDY)
    if "%Y" in base:
        short = base.replace("%Y", "%y")
        for sep in ("/", "-", "."):
            patterns.append(short.replace("/", sep).replace("-", sep))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for p in patterns:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    for fmt in unique:
        try:
            return _datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


class DayOfWeekPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        # ── Detect locale and set default format ─────────────────────────────
        self._fmt_key: str = _detect_locale_fmt_key()   # e.g. "DD/MM/YYYY"

        # ── Format dropdown ───────────────────────────────────────────────────
        locale_label = f"{self._fmt_key}  (system)"
        self._fmt_dropdown = ft.Dropdown(
            value=self._fmt_key,
            options=[
                ft.dropdown.Option(key="DD/MM/YYYY", text="DD/MM/YYYY  (e.g. 31/12/2025)"),
                ft.dropdown.Option(key="MM/DD/YYYY", text="MM/DD/YYYY  (e.g. 12/31/2025)"),
                ft.dropdown.Option(key="YYYY-MM-DD", text="YYYY-MM-DD  (e.g. 2025-12-31)"),
            ],
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            border_color=BORDER_COL,
            focused_border_color=ACCENT,
            border_radius=12,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=18),
            text_size=14,
            expand=True,
        )
        self._fmt_dropdown.on_change = self._on_fmt_change

        # Label shown below the dropdown
        self._fmt_locale_note = ft.Text(
            f"⚙️  Format detected from system locale: {self._fmt_key}",
            size=11, color=TEXT_SEC, text_align=ft.TextAlign.CENTER,
        )

        self.input_field = ft.TextField(
            hint_text=_FMT_OPTIONS[self._fmt_key][1],
            keyboard_type=ft.KeyboardType.DATETIME,
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            border_color=BORDER_COL,
            focused_border_color=ACCENT,
            border_radius=12,
            text_align=ft.TextAlign.CENTER,
            text_size=22,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=18),
            on_submit=self._on_submit,   # pressing Enter triggers calculation
        )

        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.result_card  = ft.Container(visible=False)
        self.weekday_text = ft.Text("", size=48, weight=ft.FontWeight.BOLD,
                                    color=ACCENT, text_align=ft.TextAlign.CENTER)
        self.date_text    = ft.Text("", size=15, color=TEXT_SEC,
                                    text_align=ft.TextAlign.CENTER)
        self.extra_text   = ft.Text("", size=13, color=TEXT_SEC,
                                    text_align=ft.TextAlign.CENTER)

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_input_section(),
            ft.Container(height=20),
            ft.Container(
                content=self.result_card,
                padding=ft.Padding(left=20, top=0, right=20, bottom=30),
            ),
        ]

    # ── header ────────────────────────────────────────────────────────────────

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.TODAY_ROUNDED, color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Day of the Week", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Find out what day any date falls on",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── input section ─────────────────────────────────────────────────────────

    def _build_input_section(self):
        return ft.Container(
            content=ft.Column([
                card(ft.Column([
                    section_title("ENTER A DATE"),
                    ft.Container(height=10),
                    # ── Format selector ───────────────────────────────────
                    ft.Row([
                        ft.Icon(ft.Icons.FORMAT_LIST_BULLETED_ROUNDED,
                                color=TEXT_SEC, size=14),
                        ft.Text("Date format", size=12, color=TEXT_SEC),
                    ], spacing=6),
                    ft.Container(height=4),
                    self._fmt_dropdown,
                    ft.Container(height=4),
                    self._fmt_locale_note,
                    ft.Divider(height=20, color=BORDER_COL),
                    # ── Date input ────────────────────────────────────────
                    self.input_field,
                    ft.Container(height=4),
                    self.error_text,
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
                ft.Container(height=20),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SEARCH_ROUNDED, size=18),
                        ft.Text("Find Day", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._on_submit,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT, color=DARK_BG,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=8),
                ft.OutlinedButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                        ft.Text("Reset", size=13),
                    ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._reset,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, BORDER_COL),
                        color=TEXT_SEC,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=12),
                    ),
                    width=float("inf"),
                ),
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── result card ───────────────────────────────────────────────────────────

    def _build_result_card(self, d: date):
        wd_idx   = d.weekday()          # 0=Mon … 6=Sun
        wd_name  = WEEKDAY_FULL[wd_idx]
        emoji    = WEEKDAY_EMOJI[wd_idx]
        is_wknd  = wd_idx >= 5
        today    = date.today()
        delta    = (d - today).days

        # Relative label
        if delta == 0:
            rel = "Today"
            rel_color = ACCENT
        elif delta == 1:
            rel = "Tomorrow"
            rel_color = ACCENT
        elif delta == -1:
            rel = "Yesterday"
            rel_color = TEXT_SEC
        elif delta > 0:
            rel = f"In {delta} days"
            rel_color = ACCENT
        else:
            rel = f"{abs(delta)} days ago"
            rel_color = TEXT_SEC

        # Day-type badge
        day_type_label = "Weekend" if is_wknd else "Weekday"
        day_type_color = ACCENT if is_wknd else ACCENT

        # Week number & day of year
        week_num      = d.isocalendar()[1]
        day_of_yr     = d.timetuple().tm_yday
        days_in_yr    = 366 if calendar.isleap(d.year) else 365
        days_remaining = days_in_yr - day_of_yr

        self.weekday_text.value = f"{emoji}  {wd_name}"
        self.weekday_text.color = ACCENT if is_wknd else ACCENT
        self.date_text.value    = d.strftime("%d %B %Y")
        self.extra_text.value   = ""

        self.result_card.content = card(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.TODAY_ROUNDED, color=ACCENT, size=18),
                    ft.Text("Result", size=14, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),
                # Big weekday name
                self.weekday_text,
                ft.Container(height=4),
                self.date_text,
                ft.Container(height=12),
                # Badges row
                ft.Row([
                    pill_badge(rel, rel_color),
                    pill_badge(day_type_label, day_type_color),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER, wrap=True),
                ft.Divider(height=20, color=BORDER_COL),
                # Stats row – week / year
                ft.Row([
                    self._info_chip("📅", f"Week {week_num}", "ISO week"),
                    self._info_chip("🗓️", str(d.year), "year"),
                ], spacing=8),
                ft.Container(height=8),
                # Day-of-year section
                ft.Row([
                    ft.Icon(ft.Icons.TIMELINE_ROUNDED, color=ACCENT, size=14),
                    ft.Text("Day of the Year", size=12,
                            weight=ft.FontWeight.W_600, color=TEXT_SEC),
                ], spacing=6),
                ft.Container(height=6),
                ft.Row([
                    self._info_chip(
                        "📆",
                        f"{day_of_yr} / {days_in_yr}",
                        "day of year",
                    ),
                    self._info_chip(
                        "⏳",
                        f"{days_remaining}",
                        "days to year end" if days_remaining > 0 else "last day!",
                    ),
                ], spacing=8),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = True

    def _info_chip(self, emoji: str, value: str, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(emoji, size=18, text_align=ft.TextAlign.CENTER),
                ft.Text(value, size=14, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRI, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=10, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG, border_radius=12,
            padding=ft.Padding.symmetric(horizontal=10, vertical=10),
            border=ft.Border.all(1, BORDER_COL),
            expand=True,
        )

    # ── events ────────────────────────────────────────────────────────────────

    def _on_fmt_change(self, e):
        """User explicitly changed the date format."""
        self._fmt_key = e.control.value
        hint, _ = _FMT_OPTIONS[self._fmt_key][1], None
        self.input_field.hint_text = _FMT_OPTIONS[self._fmt_key][1]
        # Clear any stale result / error so the user re-enters the date
        self.input_field.value      = ""
        self.error_text.visible     = False
        self.result_card.visible    = False
        self.update()

    def _on_submit(self, _=None):
        raw = self.input_field.value or ""
        parsed = _parse_with_fmt(raw, self._fmt_key)
        if parsed is None:
            fmt_example = _FMT_OPTIONS[self._fmt_key][1]
            self.error_text.value = (
                f"⚠️  Invalid date. Please use the {self._fmt_key} format  "
                f"({fmt_example.replace('e.g.  ', '')})"
            )
            self.error_text.visible  = True
            self.result_card.visible = False
            self.update()
            return
        self.error_text.visible = False
        self._build_result_card(parsed)
        self.update()

    def _reset(self, _=None):
        self.input_field.value   = ""
        self.error_text.visible  = False
        self.result_card.visible = False
        self.update()


# ── Page 6 – Age Calculator (con DatePicker) ─────────────────────────────────



class AgeCalculatorPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)
        self._dob: date | None = None

        self.date_picker = ft.DatePicker(on_change=self._on_date_pick)

        self.birthday_label = ft.Text(
            "Not selected", color=TEXT_SEC, size=15
        )

        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.result_card = ft.Container(visible=False)

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_input_section(),
            ft.Container(height=20),
            ft.Container(
                content=self.result_card,
                padding=ft.Padding(left=20, top=0, right=20, bottom=30),
            ),
        ]

    def did_mount(self):
        self.page.overlay.append(self.date_picker)
        self.page.update()

    def will_unmount(self):
        if self.date_picker in self.page.overlay:
            self.page.overlay.remove(self.date_picker)
        # NOTE: no page.update() here – switch_page() already calls it.

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.PERSON_ROUNDED, color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Age Calculator", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("How old is a person born on a given date?",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    def _build_input_section(self):
        return ft.Container(
            content=ft.Column([
                card(ft.Column([
                    section_title("DATE OF BIRTH"),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CAKE_ROUNDED,
                                    color=ACCENT, size=20),
                            ft.Container(width=12),
                            self.birthday_label,
                            ft.Container(expand=True),
                            ft.TextButton(
                                "Change",
                                on_click=self._open_picker,
                                style=ft.ButtonStyle(color=ACCENT),
                            ),
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        bgcolor=INPUT_BG, border_radius=12, padding=14,
                        border=ft.Border.all(1, BORDER_COL),
                        on_click=self._open_picker, ink=True,
                    ),
                    ft.Container(height=8),
                    self.error_text,
                ], spacing=0)),
                ft.Container(height=20),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CALCULATE_ROUNDED, size=18),
                        ft.Text("Calculate Age", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._calculate,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT, color=DARK_BG,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=8),
                ft.OutlinedButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                        ft.Text("Reset", size=13),
                    ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._reset,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, BORDER_COL),
                        color=TEXT_SEC,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=12),
                    ),
                    width=float("inf"),
                ),
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    def _open_picker(self, _):
        self.date_picker.open = True
        self.page.update()

    def _on_date_pick(self, e):
        if e.control.value:
            self._dob = _picker_to_date(e.control.value)
            self.birthday_label.value = self._dob.strftime("%d %B %Y")
            self.birthday_label.color = TEXT_PRI
            self.error_text.visible = False
            self.update()

    def _compute_age(self, dob: date, today: date):
        years = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            years -= 1

        last_bday_year = today.year if (today.month, today.day) >= (dob.month, dob.day) else today.year - 1
        try:
            last_bday = date(last_bday_year, dob.month, dob.day)
        except ValueError:
            last_bday = date(last_bday_year, 3, 1)

        months = (today.year - last_bday.year) * 12 + (today.month - last_bday.month)
        if today.day < last_bday.day:
            months -= 1

        # remaining_days = days elapsed since the most recent "month-anniversary"
        # of last_bday.  Special case: today IS last_bday → 0 days.
        if today == last_bday:
            remaining_days = 0
        else:
            # Find the date that was exactly `months` whole months after last_bday
            month_anchor_month = last_bday.month + months
            month_anchor_year  = last_bday.year + (month_anchor_month - 1) // 12
            month_anchor_month = (month_anchor_month - 1) % 12 + 1
            try:
                month_anchor = date(month_anchor_year, month_anchor_month, last_bday.day)
            except ValueError:
                # e.g. born on 31st but anchor month has fewer days → clamp to last day
                month_anchor = date(
                    month_anchor_year, month_anchor_month,
                    calendar.monthrange(month_anchor_year, month_anchor_month)[1],
                )
            remaining_days = (today - month_anchor).days
            if remaining_days < 0:
                remaining_days = 0

        total_days = (today - dob).days
        total_weeks = total_days // 7
        total_months = years * 12 + months
        total_hours = total_days * 24

        return years, months, remaining_days, total_days, total_weeks, total_months, total_hours

    def _next_birthday(self, dob: date, today: date):
        try:
            nb = date(today.year, dob.month, dob.day)
        except ValueError:
            nb = date(today.year, 3, 1)
        if nb <= today:
            try:
                nb = date(today.year + 1, dob.month, dob.day)
            except ValueError:
                nb = date(today.year + 1, 3, 1)
        return nb

    def _stat_chip(self, emoji, value, label):
        return ft.Container(
            content=ft.Column([
                ft.Text(emoji, size=18, text_align=ft.TextAlign.CENTER),
                ft.Text(value, size=14, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRI, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=10, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG, border_radius=12,
            padding=ft.Padding.symmetric(horizontal=10, vertical=10),
            border=ft.Border.all(1, BORDER_COL),
            expand=True,
        )

    def _calculate(self, _=None):
        if not self._dob:
            self.error_text.value = "Please select a date of birth."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return

        today = date.today()
        if self._dob > today:
            self.error_text.value = "⚠️  Date of birth cannot be in the future."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return

        self.error_text.visible = False

        years, months, days, total_days, total_weeks, total_months, total_hours =             self._compute_age(self._dob, today)

        nb = self._next_birthday(self._dob, today)
        days_to_nb = (nb - today).days
        is_bday = days_to_nb == 0

        age_label = f"{years} year{'s' if years != 1 else ''}"
        if months:
            age_label += f", {months} month{'s' if months != 1 else ''}"
        if days:
            age_label += f", {days} day{'s' if days != 1 else ''}"

        age_color = ACCENT if is_bday else ACCENT

        self.result_card.content = card(
            ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.PERSON_ROUNDED, color=ACCENT, size=18),
                    ft.Text("Age", size=14, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),

                *([
                    ft.Container(
                        content=ft.Text("🎂", size=48, text_align=ft.TextAlign.CENTER),
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Text("Happy Birthday! 🎉", size=20,
                            weight=ft.FontWeight.BOLD, color=ACCENT,
                            text_align=ft.TextAlign.CENTER),
                    ft.Container(height=4),
                ] if is_bday else []),

                ft.Text(str(years), size=72, weight=ft.FontWeight.BOLD,
                        color=age_color, text_align=ft.TextAlign.CENTER),
                ft.Text("years old", size=16, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER,
                        weight=ft.FontWeight.W_500),
                ft.Container(height=4),
                ft.Text(age_label, size=13, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),

                ft.Divider(height=20, color=BORDER_COL),

                ft.Row([
                    self._stat_chip("📅", f"{total_months:,}", "months"),
                    self._stat_chip("🗓️", f"{total_weeks:,}", "weeks"),
                    self._stat_chip("☀️", f"{total_days:,}", "days"),
                ], spacing=8),
                ft.Container(height=8),
                ft.Row([
                    self._stat_chip("⏰", f"{total_hours:,}", "hours"),
                    self._stat_chip("🎂", f"{self._dob.strftime('%d %b %Y')}", "born on"),
                    self._stat_chip("🎁",
                        "Today! 🎉" if is_bday else f"in {days_to_nb}d",
                        "next birthday"),
                ], spacing=8),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = True
        self.update()

    def _reset(self, _=None):
        self._dob = None
        self.birthday_label.value = "Not selected"
        self.birthday_label.color = TEXT_SEC
        self.error_text.visible = False
        self.result_card.visible = False
        self.update()


# ── Page 7 – Leap Year Check ──────────────────────────────────────────────────



class LeapYearPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        self.year_field = ft.TextField(
            value=str(date.today().year),
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=INPUT_BG,
            color=TEXT_PRI,
            border_color=BORDER_COL,
            focused_border_color=ACCENT,
            border_radius=12,
            text_align=ft.TextAlign.CENTER,
            text_size=22,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=18),
            on_submit=self._check,   # pressing Enter triggers check
        )

        self.error_text = ft.Text(
            "", color=ACCENT_ERR, size=13,
            text_align=ft.TextAlign.CENTER,
            visible=False,
        )

        self.result_card = ft.Container(visible=False)

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            self._build_input_section(),
            ft.Container(height=20),
            ft.Container(
                content=self.result_card,
                padding=ft.Padding(left=20, top=0, right=20, bottom=30),
            ),
        ]

    # ── header ────────────────────────────────────────────────────────────────

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    # Sostituito LEAPFROG_ROUNDED con CALENDAR_TODAY_ROUNDED (icona valida)
                    content=ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Leap Year", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Check if a year is leap and more",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── input section ─────────────────────────────────────────────────────────

    def _build_input_section(self):
        return ft.Container(
            content=ft.Column([
                card(ft.Column([
                    section_title("ENTER A YEAR"),
                    ft.Container(height=10),
                    self.year_field,
                    ft.Container(height=8),
                    ft.Text(
                        "e.g. 2024 · 1900 · 2000",
                        size=11, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=4),
                    self.error_text,
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
                ft.Container(height=20),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SEARCH_ROUNDED, size=18),
                        ft.Text("Check Leap Year", size=15,
                                weight=ft.FontWeight.W_600),
                    ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._check,
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT, color=DARK_BG,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=14),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=8),
                ft.OutlinedButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=16),
                        ft.Text("Reset", size=13),
                    ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=self._reset,
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, BORDER_COL),
                        color=TEXT_SEC,
                        shape=ft.RoundedRectangleBorder(radius=12),
                        padding=ft.Padding.symmetric(vertical=12),
                    ),
                    width=float("inf"),
                ),
            ], spacing=0),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── result card ───────────────────────────────────────────────────────────

    def _build_result_card(self, year: int):
        is_leap = (year % 400 == 0) or (year % 4 == 0 and year % 100 != 0)
        days_in_year = 366 if is_leap else 365
        today = date.today()
        current_year = today.year

        # Next leap year
        next_leap = year + 1
        while not ((next_leap % 400 == 0) or (next_leap % 4 == 0 and next_leap % 100 != 0)):
            next_leap += 1

        # Previous leap year
        prev_leap = year - 1
        while prev_leap > 0 and not ((prev_leap % 400 == 0) or (prev_leap % 4 == 0 and prev_leap % 100 != 0)):
            prev_leap -= 1

        # Distance from current year
        if year < current_year:
            when = f"{current_year - year} year(s) ago"
        elif year > current_year:
            when = f"in {year - current_year} year(s)"
        else:
            when = "this year"

        # Leap year icon / emoji
        icon = "🐸" if is_leap else "📅"

        # Main status
        status_text = f"{icon}  {year} is a leap year!" if is_leap else f"{year} is not a leap year."

        self.result_card.content = card(
            ft.Column([
                ft.Row([
                    # Sostituito LEAPFROG_ROUNDED con CALENDAR_TODAY_ROUNDED
                    ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, color=ACCENT, size=18),
                    ft.Text("Result", size=14, weight=ft.FontWeight.W_600,
                            color=TEXT_PRI),
                ], spacing=8),
                ft.Divider(height=16, color=BORDER_COL),

                # Big status
                ft.Text(status_text, size=24, weight=ft.FontWeight.BOLD,
                        color=ACCENT, text_align=ft.TextAlign.CENTER),
                ft.Container(height=8),

                # Stats chips
                ft.Row([
                    self._info_chip("📆", f"{days_in_year} days", "in the year"),
                    self._info_chip("📅", when, "relative to now"),
                ], spacing=8),
                ft.Container(height=8),

                ft.Row([
                    self._info_chip("⬅️", str(prev_leap) if prev_leap > 0 else "—",
                                    "prev leap year"),
                    self._info_chip("➡️", str(next_leap), "next leap year"),
                ], spacing=8),

                ft.Container(height=12),
                ft.Text(
                    "Leap years have 366 days, with an extra day on February 29.",
                    size=12, color=TEXT_SEC,
                    text_align=ft.TextAlign.CENTER,
                ),
            ], spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=20,
        )
        self.result_card.visible = True

    def _info_chip(self, emoji: str, value: str, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(emoji, size=18, text_align=ft.TextAlign.CENTER),
                ft.Text(value, size=14, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRI, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=10, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG, border_radius=12,
            padding=ft.Padding.symmetric(horizontal=8, vertical=10),
            border=ft.Border.all(1, BORDER_COL),
            expand=True,
        )

    # ── events ────────────────────────────────────────────────────────────────

    def _check(self, _=None):
        raw = self.year_field.value or ""
        raw = raw.strip()
        if not raw:
            self.error_text.value = "Please enter a year."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return
        try:
            year = int(raw)
        except ValueError:
            self.error_text.value = "⚠️  Invalid year. Please enter a number."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return
        # Optional: limit to reasonable range (e.g. 1-9999) but not strictly necessary
        if year < 1 or year > 9999:
            self.error_text.value = "⚠️  Year must be between 1 and 9999."
            self.error_text.visible = True
            self.result_card.visible = False
            self.update()
            return
        self.error_text.visible = False
        self._build_result_card(year)
        self.update()

    def _reset(self, _=None):
        self.year_field.value = str(date.today().year)
        self.error_text.visible = False
        self.result_card.visible = False
        self.update()


# ── Page 8 – Custom Countdowns ───────────────────────────────────────────────


# Emoji presets for event categories
_COUNTDOWN_EMOJIS = ["📅","💍","🎓","✈️","🎉","🏆","❤️","🏠","🎂","⚽","🎬","🎁","📝","💼","🌍"]


def _countdown_data_path() -> str:
    """Return a writable path for countdowns JSON (next to settings.json)."""
    return os.path.join(os.path.dirname(SETTINGS_PATH), "countdowns.json")


def _load_countdowns() -> list:
    try:
        with open(_countdown_data_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return []


def _save_countdowns(items: list) -> None:
    try:
        with open(_countdown_data_path(), "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


class CountdownPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        self._countdowns: list = _load_countdowns()   # list of dicts
        self._selected_emoji: str = "📅"
        self._selected_date: date | None = None
        self._editing_id: str | None = None           # None → add mode

        # ---- form controls ----
        self.name_field = ft.TextField(
            hint_text="e.g.  Wedding, Exam, Holiday…",
            bgcolor=INPUT_BG, color=TEXT_PRI,
            border_color=BORDER_COL, focused_border_color=ACCENT,
            border_radius=12, text_size=16,
            content_padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        )

        self.date_label = ft.Text("Not selected", color=TEXT_SEC, size=15)
        self.date_picker = ft.DatePicker(on_change=self._on_date_pick)

        # Emoji picker row
        self._emoji_buttons: list[ft.Container] = []
        for em in _COUNTDOWN_EMOJIS:
            em_ref = em
            btn = ft.Container(
                content=ft.Text(em_ref, size=22, text_align=ft.TextAlign.CENTER),
                width=42, height=42,
                border_radius=10,
                alignment=ft.Alignment(0, 0),
                bgcolor=f"{ACCENT}33" if em_ref == self._selected_emoji else INPUT_BG,
                border=ft.Border.all(2 if em_ref == self._selected_emoji else 1,
                                     ACCENT if em_ref == self._selected_emoji else BORDER_COL),
                on_click=lambda e, emoji=em_ref: self._pick_emoji(emoji),
                ink=True,
            )
            self._emoji_buttons.append(btn)

        self.emoji_row = ft.Row(
            controls=self._emoji_buttons,
            wrap=True, spacing=6, run_spacing=6,
        )

        self.form_error = ft.Text("", color=ACCENT_ERR, size=12, visible=False)

        # ---- list area ----
        self.list_col = ft.Column(spacing=12)

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            ft.Container(
                content=ft.Column([
                    self._build_form(),
                    ft.Container(height=24),
                    self._build_list_header(),
                    ft.Container(height=8),
                    self.list_col,
                    ft.Container(height=20),
                ], spacing=0),
                padding=ft.Padding.symmetric(horizontal=20),
            ),
        ]

        self._refresh_list()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def did_mount(self):
        self.page.overlay.append(self.date_picker)
        self.page.update()

    def will_unmount(self):
        if self.date_picker in self.page.overlay:
            self.page.overlay.remove(self.date_picker)
        # NOTE: no page.update() here – switch_page() already calls it.

    # ── header ────────────────────────────────────────────────────────────────

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.TIMER_ROUNDED, color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("Custom Countdowns", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("Track multiple upcoming events",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    # ── form ──────────────────────────────────────────────────────────────────

    def _build_form(self):
        return card(ft.Column([
            section_title("ADD NEW EVENT"),
            ft.Container(height=12),
            # Emoji row
            ft.Text("Choose an emoji", size=12, color=TEXT_SEC),
            ft.Container(height=6),
            self.emoji_row,
            ft.Container(height=12),
            # Name field
            ft.Text("Event name", size=12, color=TEXT_SEC),
            ft.Container(height=6),
            self.name_field,
            ft.Container(height=12),
            # Date selector
            ft.Text("Event date", size=12, color=TEXT_SEC),
            ft.Container(height=6),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=ACCENT, size=18),
                    ft.Container(width=10),
                    self.date_label,
                    ft.Container(expand=True),
                    ft.TextButton(
                        "Pick date",
                        on_click=lambda _: self._open_picker(),
                        style=ft.ButtonStyle(color=ACCENT),
                    ),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                bgcolor=INPUT_BG, border_radius=12, padding=14,
                border=ft.Border.all(1, BORDER_COL),
                on_click=lambda _: self._open_picker(), ink=True,
            ),
            ft.Container(height=8),
            self.form_error,
            ft.Container(height=4),
            ft.FilledButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD_ALARM_ROUNDED, size=18),
                    ft.Text("Save Countdown", size=15,
                            weight=ft.FontWeight.W_600),
                ], spacing=8, alignment=ft.MainAxisAlignment.CENTER),
                on_click=self._save_countdown,
                style=ft.ButtonStyle(
                    bgcolor=ACCENT, color=DARK_BG,
                    shape=ft.RoundedRectangleBorder(radius=12),
                    padding=ft.Padding.symmetric(vertical=14),
                ),
                width=float("inf"),
            ),
        ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.STRETCH))

    def _build_list_header(self):
        self._list_title = ft.Text(
            "Saved Countdowns", size=14,
            weight=ft.FontWeight.W_600, color=TEXT_PRI,
        )
        return ft.Row([
            ft.Icon(ft.Icons.LIST_ROUNDED, color=ACCENT, size=16),
            self._list_title,
        ], spacing=8)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _open_picker(self):
        self.date_picker.open = True
        self.page.update()

    def _pick_emoji(self, emoji: str):
        self._selected_emoji = emoji
        for btn in self._emoji_buttons:
            em = btn.content.value
            is_sel = (em == emoji)
            btn.bgcolor = f"{ACCENT}33" if is_sel else INPUT_BG
            btn.border  = ft.Border.all(2 if is_sel else 1,
                                        ACCENT if is_sel else BORDER_COL)
        self.update()

    def _on_date_pick(self, e):
        if e.control.value:
            self._selected_date = _picker_to_date(e.control.value)
            self.date_label.value = self._selected_date.strftime("%d %B %Y")
            self.date_label.color = TEXT_PRI
            self.update()

    def _save_countdown(self, _=None):
        name = (self.name_field.value or "").strip()
        if not name:
            self.form_error.value   = "⚠️  Please enter an event name."
            self.form_error.visible = True
            self.update()
            return
        if not self._selected_date:
            self.form_error.value   = "⚠️  Please pick a date."
            self.form_error.visible = True
            self.update()
            return
        self.form_error.visible = False

        new_entry = {
            "id":    str(int(_datetime.now().timestamp() * 1000)),
            "emoji": self._selected_emoji,
            "name":  name,
            "date":  self._selected_date.isoformat(),
        }
        self._countdowns.append(new_entry)
        # Sort by date ascending
        self._countdowns.sort(key=lambda x: x["date"])
        _save_countdowns(self._countdowns)

        # Reset form
        self.name_field.value  = ""
        self._selected_date    = None
        self.date_label.value  = "Not selected"
        self.date_label.color  = TEXT_SEC

        self._refresh_list()
        self.update()

    def _delete_countdown(self, cid: str):
        self._countdowns = [c for c in self._countdowns if c["id"] != cid]
        _save_countdowns(self._countdowns)
        self._refresh_list()
        self.update()

    # ── list rendering ────────────────────────────────────────────────────────

    def _refresh_list(self):
        self.list_col.controls.clear()
        count = len(self._countdowns)
        self._list_title.value = (
            f"Saved Countdowns  ({count})" if count else "No countdowns yet"
        )
        if not count:
            self.list_col.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text("🗓️", size=40, text_align=ft.TextAlign.CENTER),
                        ft.Text("Add your first event above",
                                size=13, color=TEXT_SEC,
                                text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
                    alignment=ft.Alignment(0, 0),
                    padding=ft.Padding.symmetric(vertical=30),
                )
            )
            return

        today = date.today()
        for item in self._countdowns:
            try:
                ev_date = date.fromisoformat(item["date"])
            except (ValueError, KeyError):
                continue
            self.list_col.controls.append(
                self._build_countdown_card(item, ev_date, today)
            )

    def _build_countdown_card(self, item: dict, ev_date: date, today: date) -> ft.Container:
        delta    = (ev_date - today).days
        emoji    = item.get("emoji", "📅")
        name     = item.get("name", "Event")
        cid      = item["id"]

        if delta > 0:
            big_label  = str(delta)
            sub_label  = "days to go"
            big_color  = ACCENT
            weeks, rem = divmod(delta, 7)
            months_approx = round(delta / 30.44, 1)
            extra_chips = ft.Row([
                self._mini_chip(f"{weeks}w {rem}d", "weeks & days"),
                self._mini_chip(f"≈{months_approx}mo", "months"),
                self._mini_chip(ev_date.strftime("%d %b %Y"), "event date"),
            ], spacing=6, wrap=True)
        elif delta == 0:
            big_label  = "🎉"
            sub_label  = "Today is the day!"
            big_color  = ACCENT
            extra_chips = ft.Row([
                self._mini_chip(ev_date.strftime("%d %b %Y"), "today"),
            ], spacing=6)
        else:
            big_label  = str(abs(delta))
            sub_label  = "days ago"
            big_color  = TEXT_SEC
            extra_chips = ft.Row([
                self._mini_chip(ev_date.strftime("%d %b %Y"), "event date"),
                pill_badge("Passed", TEXT_SEC),
            ], spacing=6, wrap=True)

        return card(ft.Column([
            # Header row: emoji + name + delete
            ft.Row([
                ft.Text(emoji, size=28),
                ft.Container(width=6),
                ft.Text(name, size=15, weight=ft.FontWeight.W_600,
                        color=TEXT_PRI, expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=TEXT_SEC, icon_size=18,
                    tooltip="Delete",
                    on_click=lambda _, c=cid: self._delete_countdown(c),
                    style=ft.ButtonStyle(
                        overlay_color=f"{ACCENT}22",
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(height=12, color=BORDER_COL),
            # Big number
            ft.Text(big_label, size=56, weight=ft.FontWeight.BOLD,
                    color=big_color, text_align=ft.TextAlign.CENTER),
            ft.Text(sub_label, size=13, color=TEXT_SEC,
                    text_align=ft.TextAlign.CENTER),
            ft.Container(height=8),
            extra_chips,
        ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER))

    def _mini_chip(self, value: str, label: str) -> ft.Container:
        return ft.Container(
            content=ft.Column([
                ft.Text(value, size=13, weight=ft.FontWeight.BOLD,
                        color=TEXT_PRI, text_align=ft.TextAlign.CENTER),
                ft.Text(label, size=10, color=TEXT_SEC,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=1, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            bgcolor=INPUT_BG, border_radius=10,
            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
            border=ft.Border.all(1, BORDER_COL),
        )


# ── About Page ───────────────────────────────────────────────────────────────

_page_ref: list = [None]   # set in main(); used by _open_url for Android


def _open_url(url: str) -> None:
    """Open a URL cross-platform via Flet's page.launch_url().

    ``webbrowser.open`` is a no-op on Android (Flet runs on Linux JVM there,
    so sys.platform == 'linux', never 'android').  page.launch_url() is the
    correct Flet API and works on Android, Windows, macOS and Linux alike.
    """
    if _page_ref[0] is not None:
        _page_ref[0].launch_url(url)
    else:
        import webbrowser
        webbrowser.open(url)


class AboutPage(ft.Column):
    def __init__(self):
        super().__init__(scroll=ft.ScrollMode.AUTO, spacing=0, expand=True)

        # ── named refs updated by _apply_theme ──────────────────────────────
        self._title_text   = ft.Text("Calendar Calc", size=28,
                                     weight=ft.FontWeight.BOLD, color=ACCENT)
        self._version_text = ft.Text(f"Version {APP_VERSION}", size=14,
                                     color=TEXT_SEC)
        self._tagline_text = ft.Text("Date utilities for every day",
                                     size=14, color=TEXT_PRI)
        self._author_text  = ft.Text(f"by {APP_AUTHOR}", size=13,
                                     color=TEXT_SEC)

        self._code_icon  = ft.Icon(ft.Icons.CODE,     size=16, color=ACCENT)
        self._web_icon   = ft.Icon(ft.Icons.LANGUAGE, size=16, color=ACCENT)
        self._repo_btn   = ft.TextButton(
            "GitHub Repository",
            url=APP_REPO,
            style=ft.ButtonStyle(color=ACCENT),
        )
        self._web_btn    = ft.TextButton(
            "Author Webpage",
            url=APP_WEB,
            style=ft.ButtonStyle(color=ACCENT),
        )

        self._support_icon  = ft.Icon(ft.Icons.FAVORITE, size=20,
                                      color=ACCENT_ERR)
        self._support_title = ft.Text("Support Calendar Calc", size=13,
                                      weight=ft.FontWeight.W_600,
                                      color=ACCENT_ERR)
        self._support_body  = ft.Text(
            "If you find Calendar Calc useful, consider supporting its "
            "development with a small donation. Every contribution is "
            "greatly appreciated!",
            size=12, color=TEXT_SEC,
        )
        self._donate_btn = ft.FilledButton(
            "💛  Donate via PayPal",
            url=APP_PAYPAL,
            style=ft.ButtonStyle(bgcolor=ACCENT),
        )
        self._support_box = ft.Container(
            content=ft.Column([
                ft.Row([self._support_icon, self._support_title], spacing=8),
                self._support_body,
                ft.Container(height=4),
                self._donate_btn,
            ], spacing=8),
            padding=ft.Padding.all(16),
            border_radius=12,
            bgcolor=INPUT_BG,
            border=ft.Border.all(1, BORDER_COL),
        )

        self.controls = [
            ft.Container(height=8),
            self._header(),
            ft.Container(height=20),
            ft.Container(
                content=ft.Column([
                    # ── App identity ─────────────────────────────────────
                    card(ft.Column([
                        ft.Row([
                            ft.Container(
                                content=ft.Image(src=_APP_ICON_SRC,
                                                 width=48, height=48),
                                bgcolor=f"{ACCENT}22", border_radius=14,
                                padding=10,
                            ),
                            ft.Column([
                                self._title_text,
                                self._version_text,
                            ], spacing=2),
                        ], spacing=16,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.Container(height=8),
                        self._tagline_text,
                        self._author_text,
                    ], spacing=4)),
                    ft.Container(height=16),
                    # ── Links ─────────────────────────────────────────────
                    card(ft.Column([
                        section_title("LINKS"),
                        ft.Container(height=8),
                        ft.Row([self._code_icon, self._repo_btn], spacing=4),
                        ft.Row([self._web_icon,  self._web_btn],  spacing=4),
                    ], spacing=0)),
                    ft.Container(height=16),
                    # ── Support box ───────────────────────────────────────
                    self._support_box,
                    ft.Container(height=30),
                ], spacing=0),
                padding=ft.Padding.symmetric(horizontal=20),
            ),
        ]

    def _header(self):
        return ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED,
                                    color=ACCENT, size=22),
                    bgcolor=f"{ACCENT}22", border_radius=10, padding=10,
                ),
                ft.Column([
                    ft.Text("About", size=20,
                            weight=ft.FontWeight.BOLD, color=TEXT_PRI),
                    ft.Text("App info & links",
                            size=12, color=TEXT_SEC),
                ], spacing=2),
            ], spacing=14),
            padding=ft.Padding.symmetric(horizontal=20),
        )

    def apply_theme(self):
        """Called by _apply_theme() after globals are updated."""
        self._title_text.color      = ACCENT
        self._version_text.color    = TEXT_SEC
        self._tagline_text.color    = TEXT_PRI
        self._author_text.color     = TEXT_SEC
        self._code_icon.color       = ACCENT
        self._web_icon.color        = ACCENT
        self._repo_btn.style        = ft.ButtonStyle(color=ACCENT)
        self._web_btn.style         = ft.ButtonStyle(color=ACCENT)
        self._support_icon.color    = ACCENT_ERR
        self._support_title.color   = ACCENT_ERR
        self._support_body.color    = TEXT_SEC
        self._donate_btn.style      = ft.ButtonStyle(bgcolor=ACCENT)
        self._support_box.bgcolor   = INPUT_BG
        self._support_box.border    = ft.Border.all(1, BORDER_COL)


# ── App Shell ───────────────────────────────────────────────────────────────

def main(page: ft.Page):
    _page_ref[0] = page   # make page accessible to _open_url on Android
    page.title    = "Calendar Calc"
    page.window.icon = "assets/calendarcalc.png"
    page.theme_mode = ft.ThemeMode.SYSTEM      # follow OS dark/light setting
    page.padding  = 0
    page.fonts    = {
        "Outfit": "https://fonts.gstatic.com/s/outfit/v11/QGYyz_MVcBeNP4NjuGObqx1XmO1I4TC1C4G-EiAou6Y.woff2"
    }

    # ══════════════════════════════════════════════════════════════════════════
    # ADAPTIVE THEME  –  dark / light following system preference
    # Same structure as LexiFinder: two palettes, _apply_theme(), on_platform_brightness_change
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_theme(_=None):
        global DARK_BG, CARD_BG, INPUT_BG, BORDER_COL, TEXT_PRI, TEXT_SEC, \
               DRAWER_BG, ACCENT, ACCENT_ERR

        is_dark = (page.platform_brightness == ft.Brightness.DARK
                   or page.theme_mode == ft.ThemeMode.DARK)
        pal = _DARK_PAL if is_dark else _LIGHT_PAL

        # ── Reassign module-level colour globals ─────────────────────────────
        DARK_BG    = pal["page_bg"]
        CARD_BG    = pal["card_bg"]
        INPUT_BG   = pal["input_bg"]
        BORDER_COL = pal["border"]
        TEXT_PRI   = pal["text_pri"]
        TEXT_SEC   = pal["text_sec"]
        DRAWER_BG  = pal["drawer_bg"]
        ACCENT     = pal["accent"]
        ACCENT_ERR = pal["accent_err"]

        # ── Page-level colours ───────────────────────────────────────────────
        page.bgcolor = DARK_BG
        page.theme   = ft.Theme(
            font_family="Outfit",
            color_scheme_seed=pal["seed"],
        )

        # ── Rebuild all page instances (picks up new globals) ────────────────
        new_pages = [
            # ── Quick lookups ────────────────────────────────────────────
            DayOfWeekPage(),          # 0
            LeapYearPage(),           # 1
            # ── Calculations between two dates ───────────────────────────
            DaysBetweenPage(),        # 2
            WorkingDaysPage(),        # 3
            # ── Arithmetic on a single date ──────────────────────────────
            AddSubtractPage(),        # 4
            # ── Age & countdowns ─────────────────────────────────────────
            AgeCalculatorPage(),      # 5
            BirthdayPage(),           # 6
            CountdownPage(),          # 7
            # ── Reference ────────────────────────────────────────────────
            HolidaysPage(),           # 8
            # ── About ────────────────────────────────────────────────────
            AboutPage(),              # 9
        ]
        pages[:] = new_pages
        body.content = pages[_cur[0]]
        body.bgcolor = DARK_BG

        # Apply theme to About page (has named widget refs)
        pages[9].apply_theme()

        # ── Drawer ───────────────────────────────────────────────────────────
        drawer.bgcolor               = DRAWER_BG
        _d_logo_bg.bgcolor           = f"{ACCENT}22"
        _d_title.color               = TEXT_PRI
        _d_tagline.color             = TEXT_SEC
        _d_divider.color             = BORDER_COL
        # ── AppBar ───────────────────────────────────────────────────────────
        appbar.bgcolor               = DARK_BG
        _ab_menu_btn.icon_color      = TEXT_PRI
        _ab_title.color              = TEXT_PRI

        page.update()

    # ── pages list & body container ──────────────────────────────────────────
    # Populated by _apply_theme(); use a mutable container so closures can
    # read the current index after switch_page() updates it.
    pages: list = []
    _cur  = [0]   # mutable current-page index (used by switch_page + _apply_theme)

    body = ft.Container(expand=True)

    def switch_page(idx: int):
        # Guard: ignore invalid indices (e.g. -1 fired programmatically by the
        # drawer when selected_index is reset, or header/divider taps).
        if not (0 <= idx < len(pages)):
            return
        _cur[0] = idx
        body.content = pages[idx]
        # NOTE: do NOT touch drawer.selected_index here – that re-fires on_change
        # with idx=-1, which in Python silently resolves to the last page and
        # can also start a second async drawer_change cycle.
        page.update()

    # ── NavigationDrawer ─────────────────────────────────────────────────────
    async def drawer_change(e):
        idx = e.control.selected_index
        # Switch the page content first so the UI responds immediately,
        # then close the drawer.  Awaiting close_drawer() *before* switching
        # causes a race condition on Android (slow animation -> double update).
        switch_page(idx)
        await page.close_drawer()

    # Named widget refs for theme updates
    _d_logo_icon = ft.Image(src=_APP_ICON_SRC, width=40, height=40)
    _d_logo_bg   = ft.Container(
        content=_d_logo_icon,
        bgcolor=f"{ACCENT}22", border_radius=12, padding=6,
    )
    _d_title    = ft.Text("Calendar Calc", size=18,
                          weight=ft.FontWeight.BOLD, color=TEXT_PRI)
    _d_subtitle = None   # merged into _d_title; kept as placeholder for theme compat
    _d_tagline  = ft.Text("Date utilities", size=12, color=TEXT_SEC)
    _d_divider  = ft.Divider(color=BORDER_COL)

    drawer = ft.NavigationDrawer(
        bgcolor=DRAWER_BG,
        indicator_color=f"{ACCENT}33",
        elevation=0,
        selected_index=0,
        on_change=drawer_change,
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Container(height=16),
                    ft.Row([_d_logo_bg,
                            _d_title],
                           spacing=14, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=8),
                    _d_tagline,
                    ft.Container(height=16),
                    _d_divider,
                ], spacing=0),
                padding=ft.Padding.symmetric(horizontal=20),
            ),
            # ── Quick lookups ────────────────────────────────────────────
            ft.NavigationDrawerDestination(
                icon=ft.Icons.TODAY_OUTLINED,
                selected_icon=ft.Icons.TODAY_ROUNDED,
                label="Day of the Week",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.CALENDAR_TODAY_OUTLINED,
                selected_icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
                label="Leap Year",
            ),
            # ── Calculations between two dates ────────────────────────
            ft.NavigationDrawerDestination(
                icon=ft.Icons.DATE_RANGE_OUTLINED,
                selected_icon=ft.Icons.DATE_RANGE_ROUNDED,
                label="Days Between Dates",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.WORK_HISTORY_OUTLINED,
                selected_icon=ft.Icons.WORK_HISTORY_ROUNDED,
                label="Working Days",
            ),
            # ── Arithmetic on a single date ───────────────────────────
            ft.NavigationDrawerDestination(
                icon=ft.Icons.EDIT_CALENDAR_OUTLINED,
                selected_icon=ft.Icons.EDIT_CALENDAR_ROUNDED,
                label="Add / Subtract Days",
            ),
            # ── Age & countdowns ──────────────────────────────────────
            ft.NavigationDrawerDestination(
                icon=ft.Icons.PERSON_OUTLINED,
                selected_icon=ft.Icons.PERSON_ROUNDED,
                label="Age Calculator",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.CAKE_OUTLINED,
                selected_icon=ft.Icons.CAKE_ROUNDED,
                label="Birthday Countdown",
            ),
            ft.NavigationDrawerDestination(
                icon=ft.Icons.TIMER_OUTLINED,
                selected_icon=ft.Icons.TIMER_ROUNDED,
                label="Custom Countdowns",
            ),
            # ── Reference ─────────────────────────────────────────────
            ft.NavigationDrawerDestination(
                icon=ft.Icons.CELEBRATION_OUTLINED,
                selected_icon=ft.Icons.CELEBRATION_ROUNDED,
                label="Monthly Holidays",
            ),
            # ── About ─────────────────────────────────────────────────
            ft.NavigationDrawerDestination(
                icon=ft.Icons.INFO_OUTLINE_ROUNDED,
                selected_icon=ft.Icons.INFO_ROUNDED,
                label="About",
            ),
        ],
    )

    # ── AppBar ───────────────────────────────────────────────────────────────
    async def open_drawer(_):
        await page.show_drawer()

    _ab_menu_btn = ft.IconButton(
        icon=ft.Icons.MENU_ROUNDED,
        icon_color=TEXT_PRI,
        on_click=open_drawer,
    )
    _ab_title    = ft.Text("Calendar Calc", weight=ft.FontWeight.BOLD,
                           color=TEXT_PRI, size=18)
    _ab_cal_icon = ft.Image(src=_APP_ICON_SRC, width=26, height=26)

    appbar = ft.AppBar(
        leading=_ab_menu_btn,
        title=_ab_title,
        bgcolor=DARK_BG,
        elevation=0,
        center_title=False,
        actions=[
            ft.Container(
                content=_ab_cal_icon,
                padding=ft.Padding.only(right=16),
                bgcolor=ft.Colors.TRANSPARENT,
            )
        ],
    )

    # ── Wire up drawer, appbar, then apply theme (builds pages too) ──────────
    page.drawer = drawer
    page.appbar = appbar

    page.on_platform_brightness_change = _apply_theme
    _apply_theme()   # initial theme + page build (matches LexiFinder startup call)

    page.add(body)
    page.update()


ft.run(main, assets_dir="assets")
