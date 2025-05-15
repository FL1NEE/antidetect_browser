# -*- coding: utf-8 -*-
import flet as ft
import os
import json
import asyncio
from playwright.async_api import async_playwright, BrowserContext
import random
import pytz

# Константы
SCREENS = (
    "800×600", "960×540", "1024×768", "1152×864", "1280×720",
    "1280×768", "1280×800", "1280×1024", "1366×768", "1408×792",
    "1440×900", "1400×1050", "1440×1080", "1536×864", "1600×900",
    "1600×1024", "1600×1200", "1680×1050", "1920×1080", "1920×1200",
    "2048×1152", "2560×1080", "2560×1440", "3440×1440"
)
LANGUAGES = ("en-US", "en-GB", "fr-FR", "ru-RU", "es-ES", "pl-PL", "pt-PT", "nl-NL", "zh-CN")
TIMEZONES = pytz.common_timezones

# Пути
CONFIG_DIR = "config"
COOKIES_DIR = "cookies"
PROFILES_DIR = "profiles"
os.makedirs(CONFIG_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR, exist_ok=True)
os.makedirs(PROFILES_DIR, exist_ok=True)

# Словарь для генерации имён устройств
ADJECTIVES = ["calm", "bold", "gentle", "fierce", "bright", "dark", "serene", "frosty", "lively", "vibrant"]
NOUNS = ["sky", "wave", "lake", "forest", "moon", "sun", "storm", "cloud", "tree", "light"]

def generate_device_name():
    return f"{random.choice(ADJECTIVES)}-{random.choice(NOUNS)}"

def get_random_user_agent():
    try:
        with open("locals/user-agent.txt", "r", encoding="utf-8") as f:
            uas = [line.strip() for line in f if line.strip()]
            return random.choice(uas) if uas else None
    except Exception as e:
        print(f"[!] Ошибка чтения User-Agent: {e}")
        return None

async def run_browser(config: dict, page_ref: ft.Ref) -> None:
    try:
        async with async_playwright() as p:
            width, height = map(int, config["real_screen_size"].split("×"))
            args = \
            [
                "--disable-infobars",
                "--disable-blink-features=AutomationControlled",
                "--disable-automation",
                "--enable-extensions",
                "--allow-running-insecure-content",
                "--disable-features=ExtensionInstallBlocklist",
                "--disable-component-update"
            ]
            if not config["webgl"]:
                args.append("--disable-webgl")
            if not config["webrtc"]:
                args.append("--disable-webrtc")

            user_data_dir = os.path.join("profiles", config["device_name"])
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel="chrome",
                headless=False,
                args=args,
                ignore_default_args=['--enable-automation', '--disable-extensions', "--disable-component-extensions-with-background-pages"],
                viewport={"width": width, "height": height},
                locale=config["language"],
                timezone_id=config["timezone"],
                has_touch=config["is_touch"],
                java_script_enabled=True,
                user_agent=config["user_agent"]
            )

            # Эмуляция характеристик
            await browser.add_init_script(f"""
                Object.defineProperty(navigator, 'vendor', {{ get: () => '{config["vendor"]}' }});
                Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {config["cpu"]} }});
                Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {config["ram"]} }});
                delete navigator.__proto__.webdriver;
            """)

            page = await browser.new_page()
            await page.goto("https://system-scanner.net/")

            if page_ref.current:
                page_ref.current.controls[1].text = "Остановить"
                page_ref.current.controls[1].icon = ft.Icons.STOP
                page_ref.current.update()

            # Ждём закрытия страницы, но не браузера
            #await page.wait_for_event("close")

            while True:
                cookies = await browser.cookies()
                with open(os.path.join(COOKIES_DIR, f"{config['device_name']}.json"), "w") as f:
                    json.dump(cookies, f, indent=4)
                await asyncio.sleep(1)

            #await browser.close()

    except Exception as e:
        print(f"Ошибка запуска браузера: {e}")


def load_config(profile: str):
    path = os.path.join(CONFIG_DIR, f"{profile}.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def save_config(name: str, data: dict):
    with open(os.path.join(CONFIG_DIR, f"{name}.json"), "w") as f:
        json.dump(data, f, indent=4)


def main(page: ft.Page):
    page.title = "1040Anti"
    page.adaptive = True
    page.window_width = 800
    page.window_height = 600
    page.padding = 20

    # Глобальные переменные
    browser_instances = {}  # Хранение активных браузеров {device_name: context}
    editing_profile = None  # Для редактирования

    RAM_VALUES = [4, 8, 16, 32, 64, 128, 256]
    CPU_MIN, CPU_MAX = 4, 48

    def create_new_profile(e):
        nonlocal editing_profile
        n = 1
        while os.path.exists(os.path.join(CONFIG_DIR, f"Profile_{n}.json")):
            n += 1
        device_name = generate_device_name()
        screen_size = "1600×900"
        real_screen_size = random.choice(SCREENS)
        random_cpu = random.randint(CPU_MIN, CPU_MAX)
        random_ram = random.choice(RAM_VALUES)
        vendor = "Google Inc."
        editing_profile = f"Profile_{n}"
        user_agent = get_random_user_agent() or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        page.session.set("device_name", device_name)
        page.session.set("user_agent", user_agent)
        page.session.set("screen_size", screen_size)
        page.session.set("real_screen_size", real_screen_size)
        page.session.set("timezone", "Europe/Moscow")
        page.session.set("language", "en-US")
        page.session.set("webgl", False)
        page.session.set("webrtc", False)
        page.session.set("vendor", vendor)
        page.session.set("cpu", random_cpu)
        page.session.set("ram", random_ram)
        page.session.set("is_touch", False)
        render_edit_form()

    def edit_profile(profile: str):
        config = load_config(profile)
        if not config:
            return
        nonlocal editing_profile
        editing_profile = profile
        page.session.set("device_name", config.get("device_name"))
        page.session.set("user_agent", config.get("user_agent"))
        page.session.set("screen_size", config.get("screen_size", "1600×900"))
        page.session.set("real_screen_size", config.get("real_screen_size", "1920×1080"))
        page.session.set("timezone", config.get("timezone", "Europe/Moscow"))
        page.session.set("language", config.get("language", "en-US"))
        page.session.set("webgl", config.get("webgl", False))
        page.session.set("webrtc", config.get("webrtc", False))
        page.session.set("vendor", config.get("vendor", "Google Inc."))
        page.session.set("cpu", config.get("cpu", 6))
        page.session.set("ram", config.get("ram", 6))
        page.session.set("is_touch", config.get("is_touch", False))
        render_edit_form()

    def regenerate_device_name(field: ft.TextField):
        new_name = generate_device_name()
        field.value = new_name
        page.session.set("device_name", new_name)
        page.update()

    def save_edited_profile(e):
        old_profile_name = editing_profile
        new_device_name = page.session.get("device_name")

        old_file_path = os.path.join(CONFIG_DIR, f"{old_profile_name}.json")

        config = {
            "device_name": new_device_name,
            "user_agent": page.session.get("user_agent"),
            "screen_size": page.session.get("screen_size"),
            "real_screen_size": page.session.get("real_screen_size"),
            "timezone": page.session.get("timezone"),
            "language": page.session.get("language"),
            "webgl": page.session.get("webgl"),
            "webrtc": page.session.get("webrtc"),
            "vendor": page.session.get("vendor"),
            "cpu": int(page.session.get("cpu")),
            "ram": int(page.session.get("ram")),
            "is_touch": page.session.get("is_touch")
        }

        if old_profile_name != new_device_name and os.path.exists(old_file_path):
            os.remove(old_file_path)

        save_config(new_device_name, config)
        goto_profiles(None)

    async def start_profile(profile: str, page_ref: ft.Ref):
        config = load_config(profile)
        if config:
            task = await run_browser(config, page_ref)
            browser_instances[config["device_name"]] = task

    def stop_profile(profile: str, page_ref: ft.Ref):
        config = load_config(profile)
        if config and config["device_name"] in browser_instances:
            task = browser_instances.pop(config["device_name"])
            task.cancel()
        if page_ref.current:
            page_ref.current.controls[1].text = "Старт"
            page_ref.current.controls[1].icon = ft.Icons.PLAY_ARROW
            page_ref.current.update()

    def render_edit_form():
        device_name = page.session.get("device_name") or generate_device_name()
        user_agent = page.session.get("user_agent") or "Mozilla/5.0..."
        screen_size = page.session.get("screen_size") or "1600×900"
        real_screen_size = page.session.get("real_screen_size") or "1920×1080"
        timezone = page.session.get("timezone") or "Europe/Moscow"
        language = page.session.get("language") or "en-US"
        webgl = page.session.get("webgl") or False
        webrtc = page.session.get("webrtc") or False
        vendor = page.session.get("vendor") or "Google Inc."
        cpu = page.session.get("cpu") or 6
        ram = page.session.get("ram") or 6
        is_touch = page.session.get("is_touch") or False

        device_name_field = ft.TextField(label="Имя устройства", value=device_name, border_color=ft.Colors.WHITE)
        regen_button = ft.IconButton(icon=ft.Icons.REFRESH, on_click=lambda _: regenerate_device_name(device_name_field))
        user_agent_field = ft.TextField(
            label="User Agent", value=user_agent, expand=True, border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("user_agent", e.control.value)
        )
        screen_dropdown = ft.Dropdown(
            label="Экран", value=screen_size,
            options=[ft.dropdown.Option(s) for s in SCREENS],
            border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("real_screen_size", e.control.value)
        )
        timezone_dropdown = ft.Dropdown(
            label="Часовой пояс", value=timezone,
            options=[ft.dropdown.Option(tz) for tz in TIMEZONES],
            border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("timezone", e.control.value)
        )
        language_dropdown = ft.Dropdown(
            label="Язык", value=language,
            options=[ft.dropdown.Option(lang) for lang in LANGUAGES],
            border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("language", e.control.value)
        )
        webgl_switch = ft.Switch(label="WebGL", value=webgl, on_change=lambda e: page.session.set("webgl", e.control.value))
        webrtc_switch = ft.Switch(label="WebRTC", value=webrtc, on_change=lambda e: page.session.set("webrtc", e.control.value))
        vendor_field = ft.TextField(
            label="Производитель", value=vendor, expand=True, border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("vendor", e.control.value)
        )
        cpu_field = ft.TextField(
            label="CPU (ядер)", value=str(cpu), keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("cpu", int(e.control.value) if e.control.value.isdigit() else 6)
        )
        ram_field = ft.TextField(
            label="RAM (ГБ)", value=str(ram), keyboard_type=ft.KeyboardType.NUMBER, border_color=ft.Colors.WHITE,
            on_change=lambda e: page.session.set("ram", int(e.control.value) if e.control.value.isdigit() else 6)
        )
        touch_switch = ft.Switch(label="Тачскрин", value=is_touch, on_change=lambda e: page.session.set("is_touch", e.control.value))

        page.controls = [
            ft.Column([
                ft.Text("Создать / Редактировать профиль", size=20),
                ft.Container(padding=20, content=ft.Row([device_name_field, regen_button, ft.FilledButton("Сохранить", icon=ft.Icons.CHECK, on_click=save_edited_profile)])),
                ft.Container(padding=20, content=ft.Row([user_agent_field])),
                ft.Container(padding=20, content=ft.Row([screen_dropdown])),
                ft.Container(padding=20, content=ft.Row([timezone_dropdown, language_dropdown])),
                ft.Container(padding=20, content=ft.Row([webgl_switch, webrtc_switch])),
                ft.Container(padding=20, content=ft.Row([vendor_field])),
                ft.Container(padding=20, content=ft.Row([cpu_field, ram_field, touch_switch]))
            ], spacing=15)
        ]
        page.update()

    def get_profiles_list():
        profiles = []
        for file in os.listdir(CONFIG_DIR):
            if file.endswith(".json"):
                profile = file[:-5]  # Убираем .json
                config = load_config(profile)
                if not config:
                    continue
                page_ref = ft.Ref[ft.Row]()
                config_row = ft.Row([
                    ft.Text(config["device_name"], size=20, weight=ft.FontWeight.W_600),
                    ft.FilledButton(text=config["language"], icon=ft.Icons.LANGUAGE, bgcolor=ft.Colors.WHITE24, color=ft.Colors.WHITE),
                    ft.FilledButton(text=config["timezone"], icon=ft.Icons.SCHEDULE, bgcolor=ft.Colors.WHITE24, color=ft.Colors.WHITE),
                ])
                action_row = ft.Row([
                    ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.WHITE70, on_click=lambda _, p=file: delete_profile(p)),
                    ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.WHITE70, on_click=lambda _, p=profile: edit_profile(p)),
                    ft.FilledButton(text="Старт", icon=ft.Icons.PLAY_ARROW, on_click=lambda _, p=profile, r=page_ref: asyncio.run(start_profile(p, r))),
                ], ref=page_ref)
                profiles.append(ft.Container(
                    bgcolor=ft.Colors.WHITE24,
                    padding=15,
                    border_radius=10,
                    shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.BLACK38, offset=(0, 2)),
                    content=ft.Column([config_row, action_row])
                ))
        if profiles:
            return [ft.Column([
                ft.Text("Конфиги", size=20),
                ft.Column(profiles, spacing=10)
            ], spacing=20)]
        else:
            return [ft.Text("Нет конфигов", size=20)]

    def delete_profile(file: str):
        os.remove(os.path.join(CONFIG_DIR, file))
        page.controls = get_profiles_list()
        page.update()

    def goto_profiles(e):
        page.appbar = ft.AppBar(
            title=ft.Text("1040Anti"),
            actions=[ft.IconButton(ft.Icons.ADD, on_click=create_new_profile)],
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.GREY_200)
        )
        page.controls = get_profiles_list()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.TUNE, label="Конфиги")
        ],
        on_change=goto_profiles,
        border=ft.Border(top=ft.BorderSide(1, ft.CupertinoColors.SYSTEM_GREY2))
    )
    page.appbar = ft.AppBar(
        title=ft.Text("Antic Browser"),
        actions=[ft.IconButton(ft.Icons.ADD, on_click=create_new_profile)],
        bgcolor=ft.Colors.with_opacity(0.04, ft.CupertinoColors.SYSTEM_BACKGROUND)
    )
    content = get_profiles_list()
    if content:
        page.add(content[0])
    else:
        page.add(ft.Text("Нет конфигов", size=20))


if __name__ == "__main__":
    ft.app(
        target = main
    )
