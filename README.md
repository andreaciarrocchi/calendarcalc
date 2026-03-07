# CalendarCalc

**CalendarCalc** is a collection of date utilities bundled into a single, clean graphical application. It covers the most common calendar-related tasks — counting days between two dates, calculating working days with public holiday awareness, finding the day of the week for any date, computing ages, setting up countdowns, and browsing a monthly holiday reference — all without the need for a spreadsheet or an online tool.

CalendarCalc is built with [Flet](https://flet.dev/) and runs on **Windows**, **Linux**, and **Android**. It adapts automatically to your system's dark or light theme and remembers your preferences across sessions.

---

## Releases

Three standalone releases are available, requiring no Python installation:

- **Windows**: `CalendarCalc_Setup_v2.0.exe` — a self-contained installer created with [InnoSetup](https://jrsoftware.org/isinfo.php) from a Flet build.
- **Linux**: `Calendar_Calc-x86_64.AppImage` — a portable AppImage created with [appimagetool](https://github.com/AppImage/appimagetool) from a Flet build.
- **Android**: `calendar_calc.apk` — a native Android package.

---

## Features

CalendarCalc is organised into nine tools, accessible from the side navigation drawer:

### Quick Lookups

- **Day of the Week** — enter any date and find out which day of the week it falls on.
- **Leap Year** — check whether a given year is a leap year.

### Calculations Between Two Dates

- **Days Between Dates** — compute the exact number of days separating two dates, with optional breakdown by weeks and remaining days.
- **Working Days** — count only working days between two dates, optionally excluding public holidays for your country. Configurable work week (any combination of weekdays).

### Arithmetic on a Single Date

- **Add / Subtract Days** — starting from any date, add or subtract a number of days, weeks, or months to find the resulting date.

### Age & Countdowns

- **Age Calculator** — enter a birth date to get the exact age in years, months, and days.
- **Birthday Countdown** — see how many days remain until your next birthday. Save your birth date in settings so it is always pre-filled.
- **Custom Countdowns** — create and track countdowns to any date you choose.

### Reference

- **Monthly Holidays** — browse public holidays month by month for any country in the supported list.

---

## Country Support

Working Days and Monthly Holidays are fully holiday-aware. CalendarCalc includes built-in holiday data for **over 40 countries**, with Easter-based and computed holidays (such as floating bank holidays and midsummer observances) calculated algorithmically for any year:

🇮🇹 Italy · 🇺🇸 United States · 🇬🇧 United Kingdom · 🇫🇷 France · 🇩🇪 Germany · 🇪🇸 Spain · 🇵🇹 Portugal · 🇳🇱 Netherlands · 🇧🇪 Belgium · 🇨🇭 Switzerland · 🇦🇹 Austria · 🇵🇱 Poland · 🇸🇪 Sweden · 🇳🇴 Norway · 🇩🇰 Denmark · 🇫🇮 Finland · 🇮🇪 Ireland · 🇭🇷 Croatia · 🇸🇰 Slovakia · 🇷🇸 Serbia · 🇷🇺 Russia · 🇺🇦 Ukraine · 🇹🇷 Turkey · 🇮🇱 Israel · 🇪🇬 Egypt · 🇯🇵 Japan · 🇨🇳 China · 🇮🇳 India · 🇧🇷 Brazil · 🇲🇽 Mexico · 🇦🇷 Argentina · 🇨🇦 Canada · 🇦🇺 Australia · 🇳🇿 New Zealand · 🇿🇦 South Africa · 🇳🇬 Nigeria · 🇰🇪 Kenya · and more.

The country is detected automatically from your system locale on first launch and can be changed at any time from the settings.

---

## Settings

CalendarCalc stores a small settings file so your preferences persist across sessions. You can configure:

- **Work days** — which days of the week count as working days (default: Monday to Friday).
- **Exclude public holidays** — whether public holidays are skipped when counting working days.
- **Country** — the country whose holiday calendar is used.
- **Birthday** — an optional birth date pre-filled in the Birthday Countdown tool.

Settings are stored in a platform-appropriate location:

| Platform | Path |
|---|---|
| Windows | `%APPDATA%\CalendarCalc\settings.json` |
| Linux | `$XDG_CONFIG_HOME/CalendarCalc/settings.json` (falls back to `~/.config/…`) |
| Android | App private storage |

---

## How to Contribute

Contributions of any kind are welcome:

- **Bug reports** — if something does not work as expected, please open an issue on the [GitHub repository](https://github.com/andreaciarrocchi/calendarcalc) with a description of the problem and the steps to reproduce it.
- **Feature requests** — suggestions for new tools or improvements can be submitted as issues.
- **Code contributions** — pull requests are welcome. Please keep changes focused and describe what they do and why.
- **Sponsorship** — if CalendarCalc saves you time, consider supporting its development via [PayPal](https://paypal.me/ciarro85).

---

## License

CalendarCalc is free software licensed under the **GNU General Public License v3** (GPLv3). You may redistribute and/or modify it under the terms of the GPLv3 as published by the Free Software Foundation. See the `LICENSE` file for details.

You are free to inspect, modify, and redistribute this software, provided that you preserve the GPL license and include the full source code when distributing.
