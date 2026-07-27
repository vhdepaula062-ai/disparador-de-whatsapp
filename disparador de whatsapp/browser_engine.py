"""
Lead Hunter Pro v3.0 Enterprise Suite - Browser Engine
======================================================
Módulo de abstração e gerenciamento dinâmico de motores de navegação Web.
Suporta conexão direta a instâncias ativas do navegador via CDP (Chrome DevTools Protocol),
permitindo realizar pesquisas em abas da janela principal já aberta do usuário.
"""

from __future__ import annotations

import os
import sys
import platform
import logging
import threading
import socket
import subprocess
import time
import re
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# ── Importação do Registro do Windows ─────────────────────────────────────────
try:
    import winreg
    SUPORTA_WINREG: bool = True
except ImportError:
    winreg = None  # type: ignore[assignment]
    SUPORTA_WINREG: bool = False

# ── Selenium 4 Imports ────────────────────────────────────────────────────────
from selenium import webdriver
from selenium.webdriver.remote.webdriver import WebDriver

from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.safari.options import Options as SafariOptions

# ── Fallback via WebDriverManager ─────────────────────────────────────────────
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.firefox import GeckoDriverManager
    from webdriver_manager.microsoft import EdgeChromiumDriverManager
    HAS_WEBDRIVER_MANAGER: bool = True
except ImportError:
    ChromeDriverManager = None  # type: ignore[assignment,misc]
    GeckoDriverManager = None   # type: ignore[assignment,misc]
    EdgeChromiumDriverManager = None  # type: ignore[assignment,misc]
    HAS_WEBDRIVER_MANAGER = False

# Logger Enterprise
logger = logging.getLogger("LeadHunterPro.BrowserEngine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def check_remote_debugging_port(port: int = 9222, host: str = "127.0.0.1") -> bool:
    """Verifica se a porta de depuração do navegador já está aberta no sistema em milissegundos."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.1)
            return s.connect_ex((host, port)) == 0
    except Exception:
        return False


def get_browser_major_version(exe_path: Optional[Path]) -> Optional[str]:
    """Obtém a versão principal (major) do executável do navegador."""
    if not exe_path or not exe_path.exists():
        return None
    try:
        if platform.system() == "Windows":
            cmd = f'powershell "(Get-Item \'{str(exe_path)}\').VersionInfo.ProductVersion"'
            res = subprocess.check_output(cmd, shell=True).decode().strip()
            if res:
                return res.split(".")[0]
    except Exception:
        pass
    return None


def ensure_remote_debugging(port: int = 9222, exe_path: Optional[Path] = None) -> bool:
    """Verifica de forma ultra-rápida se a porta CDP está aberta sem criar processos duplicados."""
    return check_remote_debugging_port(port)


class SupportedBrowsers(Enum):
    CHROME = "chrome"
    EDGE = "edge"
    BRAVE = "brave"
    OPERA = "opera"
    VIVALDI = "vivaldi"
    CHROMIUM = "chromium"
    COMET = "comet"
    FIREFOX = "firefox"
    TOR = "tor"
    SAFARI = "safari"
    UNKNOWN = "unknown"

    @classmethod
    def from_string(cls, val: str) -> Optional[SupportedBrowsers]:
        if not val:
            return None
        val_lower = str(val).lower()
        for b in cls:
            if b.value.lower() == val_lower or b.name.lower() == val_lower:
                return b
        return None


class BrowserFamily(Enum):
    """Famílias de motores de renderização."""
    CHROMIUM = "chromium"
    GECKO = "gecko"
    WEBKIT = "webkit"


@dataclass
class BrowserInfo:
    browser_type: SupportedBrowsers
    display_name: str
    binary_path: Optional[Path] = None
    version: Optional[str] = None
    is_installed: bool = False
    is_default: bool = False
    driver_type: str = "chromedriver"


class SystemEnvironment:
    """Utilitário de caminhos e ambiente compatível com PyInstaller."""

    @staticmethod
    def get_app_data_dir() -> Path:
        if platform.system() == "Windows":
            base = os.environ.get("APPDATA", os.path.expanduser("~\\AppData\\Roaming"))
        elif platform.system() == "Darwin":
            base = os.path.expanduser("~/Library/Application Support")
        else:
            base = os.path.expanduser("~/.config")

        path = Path(base) / "LeadHunterPro"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def get_resource_path(relative_path: str) -> Path:
        if hasattr(sys, '_MEIPASS'):
            return Path(sys._MEIPASS) / relative_path
        return Path(os.path.abspath(".")) / relative_path


class ProfileManager:
    """Gerencia e isola perfis de usuário por navegador no AppData ou LocalAppData."""

    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_system_user_data_path(cls, browser: SupportedBrowsers) -> Optional[Path]:
        """Localiza a pasta User Data nativa do usuário no SO para usar contas já logadas."""
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        app_data = os.environ.get("APPDATA", "")
        home = os.path.expanduser("~")

        if platform.system() == "Windows":
            if browser == SupportedBrowsers.CHROME:
                return Path(local_app_data) / "Google/Chrome/User Data"
            elif browser == SupportedBrowsers.EDGE:
                return Path(local_app_data) / "Microsoft/Edge/User Data"
            elif browser == SupportedBrowsers.BRAVE:
                return Path(local_app_data) / "BraveSoftware/Brave-Browser/User Data"
            elif browser == SupportedBrowsers.VIVALDI:
                return Path(local_app_data) / "Vivaldi/User Data"
            elif browser == SupportedBrowsers.OPERA:
                return Path(app_data) / "Opera Software/Opera Stable"
            elif browser in [SupportedBrowsers.COMET, SupportedBrowsers.CHROMIUM]:
                p1 = Path(local_app_data) / "Perplexity/Comet/User Data"
                if p1.exists():
                    return p1
                p2 = Path(local_app_data) / "Comet/User Data"
                if p2.exists():
                    return p2
                p3 = Path(local_app_data) / "Chromium/User Data"
                if p3.exists():
                    return p3

            try:
                detected_dict = BrowserDetector.detect_all()
                info = detected_dict.get(browser)
                if info and info.binary_path:
                    bin_path = info.binary_path
                    parts = bin_path.parts
                    for i, part in enumerate(parts):
                        if part.lower() == "application" and i > 0:
                            candidate = Path(*parts[:i]) / "User Data"
                            if candidate.exists():
                                return candidate
            except Exception:
                pass

        elif platform.system() == "Darwin":
            if browser == SupportedBrowsers.CHROME:
                return Path(home) / "Library/Application Support/Google/Chrome"
            elif browser == SupportedBrowsers.EDGE:
                return Path(home) / "Library/Application Support/Microsoft Edge"
            elif browser == SupportedBrowsers.BRAVE:
                return Path(home) / "Library/Application Support/BraveSoftware/Brave-Browser"
        elif platform.system() == "Linux":
            if browser == SupportedBrowsers.CHROME:
                return Path(home) / ".config/google-chrome"
            elif browser == SupportedBrowsers.CHROMIUM:
                return Path(home) / ".config/chromium"

        return None

    @classmethod
    def get_profile_path(cls, browser: SupportedBrowsers, use_system_profile: bool = False) -> Path:
        with cls._lock:
            if use_system_profile and check_remote_debugging_port(9222):
                sys_path = cls.get_system_user_data_path(browser)
                if sys_path and sys_path.exists():
                    logger.info(f"Utilizando perfil nativo do sistema para {browser.value}: {sys_path}")
                    return sys_path

            base_dir = SystemEnvironment.get_app_data_dir() / "profiles" / browser.value
            base_dir.mkdir(parents=True, exist_ok=True)
            return base_dir


class BrowserDetector:
    """Mapeia o navegador padrão do SO e os navegadores instalados no sistema."""

    @staticmethod
    def get_default_browser() -> tuple[SupportedBrowsers, str, Optional[Path]]:
        os_name = platform.system()

        if os_name == "Windows" and SUPORTA_WINREG and winreg is not None:
            try:
                reg_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path) as key:
                    prog_id, _ = winreg.QueryValueEx(key, "ProgId")

                command_key_path = fr"{prog_id}\shell\open\command"
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, command_key_path) as key:
                    cmd, _ = winreg.QueryValueEx(key, "")

                match = re.search(r'([A-Za-z]:\\[^"]+\.exe)', cmd, re.IGNORECASE)
                exe_path = Path(match.group(1)) if match else None

                prog_id_lower = str(prog_id).lower()
                cmd_lower = str(cmd).lower()
                exe_name = exe_path.name.lower() if exe_path else ""

                if "comet" in prog_id_lower or "comet" in cmd_lower or exe_name == "comet.exe":
                    return SupportedBrowsers.COMET, "Comet Browser", exe_path
                elif "chrome" in prog_id_lower or "chrome" in cmd_lower or exe_name == "chrome.exe":
                    return SupportedBrowsers.CHROME, "Google Chrome", exe_path
                elif "edge" in prog_id_lower or "msedge" in prog_id_lower or "edge" in cmd_lower or "msedge" in cmd_lower or exe_name == "msedge.exe":
                    return SupportedBrowsers.EDGE, "Microsoft Edge", exe_path
                elif "brave" in prog_id_lower or "brave" in cmd_lower or exe_name == "brave.exe":
                    return SupportedBrowsers.BRAVE, "Brave Browser", exe_path
                elif "opera" in prog_id_lower or "opera" in cmd_lower or exe_name == "opera.exe":
                    return SupportedBrowsers.OPERA, "Opera", exe_path
                elif "vivaldi" in prog_id_lower or "vivaldi" in cmd_lower or exe_name == "vivaldi.exe":
                    return SupportedBrowsers.VIVALDI, "Vivaldi", exe_path
                elif "firefox" in prog_id_lower or "firefox" in cmd_lower or exe_name == "firefox.exe":
                    return SupportedBrowsers.FIREFOX, "Mozilla Firefox", exe_path
                else:
                    return SupportedBrowsers.CHROME, f"Navegador Padrão ({prog_id})", exe_path
            except Exception as e:
                logger.warning(f"Erro ao ler registro do Windows: {e}")

        elif os_name == "Darwin":
            return SupportedBrowsers.SAFARI, "Safari", Path("/Applications/Safari.app/Contents/MacOS/Safari")

        return SupportedBrowsers.CHROME, "Google Chrome", None

    @classmethod
    def get_known_paths(cls) -> Dict[SupportedBrowsers, List[Path]]:
        os_name = platform.system()
        paths: Dict[SupportedBrowsers, List[Path]] = {b: [] for b in SupportedBrowsers}

        if os_name == "Windows":
            local = os.environ.get("LOCALAPPDATA", "")
            program_files = os.environ.get("PROGRAMFILES", "C:\\Program Files")
            program_files_x86 = os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")

            paths[SupportedBrowsers.CHROME] = [
                Path(program_files) / "Google/Chrome/Application/chrome.exe",
                Path(program_files_x86) / "Google/Chrome/Application/chrome.exe",
                Path(local) / "Google/Chrome/Application/chrome.exe",
            ]
            paths[SupportedBrowsers.EDGE] = [
                Path(program_files_x86) / "Microsoft/Edge/Application/msedge.exe",
                Path(program_files) / "Microsoft/Edge/Application/msedge.exe",
            ]
            paths[SupportedBrowsers.BRAVE] = [
                Path(program_files) / "BraveSoftware/Brave-Browser/Application/brave.exe",
                Path(local) / "BraveSoftware/Brave-Browser/Application/brave.exe",
            ]
            paths[SupportedBrowsers.OPERA] = [
                Path(local) / "Programs/Opera/opera.exe",
                Path(program_files) / "Opera/opera.exe",
            ]
            paths[SupportedBrowsers.VIVALDI] = [
                Path(local) / "Vivaldi/Application/vivaldi.exe",
                Path(program_files) / "Vivaldi/Application/vivaldi.exe",
            ]
            paths[SupportedBrowsers.COMET] = [
                Path(local) / "Perplexity/Comet/Application/comet.exe",
                Path(local) / "Comet/Application/comet.exe",
            ]
            paths[SupportedBrowsers.CHROMIUM] = [
                Path(local) / "Chromium/Application/chrome.exe",
            ]
            paths[SupportedBrowsers.FIREFOX] = [
                Path(program_files) / "Mozilla Firefox/firefox.exe",
                Path(program_files_x86) / "Mozilla Firefox/firefox.exe",
            ]
            paths[SupportedBrowsers.TOR] = [
                Path("C:\\Desktop\\Tor Browser\\Browser\\firefox.exe"),
                Path(os.path.expanduser("~\\Desktop\\Tor Browser\\Browser\\firefox.exe")),
            ]

        elif os_name == "Darwin":
            paths[SupportedBrowsers.CHROME] = [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
            paths[SupportedBrowsers.EDGE] = [Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
            paths[SupportedBrowsers.BRAVE] = [Path("/Applications/Brave Browser.app/Contents/MacOS/Brave Browser")]
            paths[SupportedBrowsers.FIREFOX] = [Path("/Applications/Firefox.app/Contents/MacOS/firefox")]
            paths[SupportedBrowsers.SAFARI] = [Path("/Applications/Safari.app/Contents/MacOS/Safari")]

        elif os_name == "Linux":
            paths[SupportedBrowsers.CHROME] = [Path("/usr/bin/google-chrome"), Path("/usr/bin/chrome")]
            paths[SupportedBrowsers.CHROMIUM] = [Path("/usr/bin/chromium"), Path("/usr/bin/chromium-browser")]
            paths[SupportedBrowsers.FIREFOX] = [Path("/usr/bin/firefox")]
            paths[SupportedBrowsers.EDGE] = [Path("/usr/bin/microsoft-edge")]

        return paths

    @classmethod
    def detect_all(cls) -> Dict[SupportedBrowsers, BrowserInfo]:
        default_browser, default_name, default_exe = cls.get_default_browser()
        known_paths = cls.get_known_paths()
        result: Dict[SupportedBrowsers, BrowserInfo] = {}

        for b_type, path_list in known_paths.items():
            found_path = None
            if default_browser == b_type and default_exe and default_exe.exists():
                found_path = default_exe
            else:
                for p in path_list:
                    if p.exists() and p.is_file():
                        found_path = p
                        break

            is_def = (b_type == default_browser)
            display_name = default_name if is_def else b_type.value.capitalize()

            if b_type in [SupportedBrowsers.CHROME, SupportedBrowsers.BRAVE, SupportedBrowsers.OPERA,
                          SupportedBrowsers.VIVALDI, SupportedBrowsers.CHROMIUM, SupportedBrowsers.COMET]:
                d_type = "chromedriver"
            elif b_type == SupportedBrowsers.EDGE:
                d_type = "msedgedriver"
            elif b_type in [SupportedBrowsers.FIREFOX, SupportedBrowsers.TOR]:
                d_type = "geckodriver"
            elif b_type == SupportedBrowsers.SAFARI:
                d_type = "safaridriver"
            else:
                d_type = "unknown"

            result[b_type] = BrowserInfo(
                browser_type=b_type,
                display_name=display_name,
                binary_path=found_path,
                is_installed=(found_path is not None or (b_type == SupportedBrowsers.SAFARI and platform.system() == "Darwin")),
                is_default=is_def,
                driver_type=d_type
            )

        return result


class BrowserCompatibility:
    """Ordem estrita de fallback prioritário protegida contra sequestro do Comet/Perplexity."""

    FALLBACK_ORDER: List[SupportedBrowsers] = [
        SupportedBrowsers.EDGE,
        SupportedBrowsers.CHROME,
        SupportedBrowsers.BRAVE,
        SupportedBrowsers.OPERA,
        SupportedBrowsers.VIVALDI,
        SupportedBrowsers.CHROMIUM,
        SupportedBrowsers.FIREFOX,
        SupportedBrowsers.TOR,
        SupportedBrowsers.SAFARI
    ]

    @classmethod
    def resolve_browser(cls, preferred: Optional[SupportedBrowsers] = None) -> BrowserInfo:
        detected = BrowserDetector.detect_all()

        if preferred and preferred in detected and detected[preferred].is_installed and preferred != SupportedBrowsers.COMET:
            return detected[preferred]

        default_browser, _, default_exe = BrowserDetector.get_default_browser()

        # Se o navegador padrão for o Comet (Perplexity), desvia automaticamente para Edge/Chrome
        # pois o Comet intercepta tráfego HTTP e força buscas via perplexity.ai com Cloudflare.
        if default_browser == SupportedBrowsers.COMET:
            logger.info("⚠️ Navegador Comet (Perplexity) detectado. Redirecionando motor de pesquisa para Edge/Chrome...")
            for b_type in [SupportedBrowsers.EDGE, SupportedBrowsers.CHROME, SupportedBrowsers.BRAVE, SupportedBrowsers.OPERA]:
                if b_type in detected and detected[b_type].is_installed:
                    return detected[b_type]

        if default_browser in detected and detected[default_browser].is_installed and default_browser != SupportedBrowsers.COMET:
            return detected[default_browser]

        for b_type in cls.FALLBACK_ORDER:
            if b_type in detected and detected[b_type].is_installed:
                return detected[b_type]

        return BrowserInfo(
            browser_type=SupportedBrowsers.CHROME,
            display_name="Google Chrome (Fallback Automático)",
            binary_path=None,
            is_installed=True,
            is_default=False,
            driver_type="chromedriver"
        )


class OptionsFactory:
    """Configura opções e flags anti-automação desativando extensões parasitas como Perplexity."""

    @classmethod
    def build_options(cls,
                      browser_info: BrowserInfo,
                      headless: bool = False,
                      custom_profile: bool = True,
                      use_system_profile: bool = False,
                      options_args: Optional[List[str]] = None) -> Any:

        b_type = browser_info.browser_type
        profile_path = ProfileManager.get_profile_path(b_type, use_system_profile=use_system_profile)

        if b_type in [SupportedBrowsers.CHROME, SupportedBrowsers.BRAVE, SupportedBrowsers.OPERA,
                      SupportedBrowsers.VIVALDI, SupportedBrowsers.CHROMIUM, SupportedBrowsers.COMET]:
            options = ChromeOptions()
            options.page_load_strategy = "eager"

            if check_remote_debugging_port(9222):
                logger.info("[CDP] Navegador em execução detectado! Conectando à janela principal ativa...")
                options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                return options

            if browser_info.binary_path:
                options.binary_location = str(browser_info.binary_path)

            if custom_profile:
                options.add_argument(f"--user-data-dir={str(profile_path)}")

            options.add_argument("--start-maximized")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-allow-origins=*")
            options.add_argument("--remote-debugging-port=0")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-default-apps")
            options.add_argument("homepage=https://www.google.com/")
            options.add_argument("--lang=pt-BR")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            if headless:
                options.add_argument("--headless=new")

            if options_args:
                for arg in options_args:
                    options.add_argument(arg)

            return options

        elif b_type == SupportedBrowsers.EDGE:
            options = EdgeOptions()
            options.page_load_strategy = "eager"

            if check_remote_debugging_port(9222):
                logger.info("[CDP] Navegador Edge em execução detectado! Conectando à janela principal ativa...")
                options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                return options

            if browser_info.binary_path:
                options.binary_location = str(browser_info.binary_path)

            if custom_profile:
                options.add_argument(f"--user-data-dir={str(profile_path)}")

            options.add_argument("--start-maximized")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--remote-allow-origins=*")
            options.add_argument("--remote-debugging-port=0")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-notifications")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-component-extensions-with-background-pages")
            options.add_argument("--disable-default-apps")
            options.add_argument("homepage=https://www.google.com/")
            options.add_argument("--lang=pt-BR")

            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)

            if headless:
                options.add_argument("--headless=new")

            if options_args:
                for arg in options_args:
                    options.add_argument(arg)

            return options

        elif b_type in [SupportedBrowsers.FIREFOX, SupportedBrowsers.TOR]:
            options = FirefoxOptions()
            options.page_load_strategy = "eager"

            if browser_info.binary_path:
                options.binary_location = str(browser_info.binary_path)

            if custom_profile:
                options.set_preference("profile", str(profile_path))

            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference('useAutomationExtension', False)

            if headless:
                options.add_argument("--headless")

            if options_args:
                for arg in options_args:
                    options.add_argument(arg)

            return options

        elif b_type == SupportedBrowsers.SAFARI:
            options = SafariOptions()
            options.page_load_strategy = "eager"
            return options

        raise ValueError(f"Motor de navegação não suportado: {b_type}")


class DriverFactory:
    """Instancia o driver com suporte nativo do Selenium 4 e fallback secundário."""

    @classmethod
    def create_driver(cls, browser_info: BrowserInfo, options: Any) -> WebDriver:
        b_type = browser_info.browser_type
        major_ver = get_browser_major_version(browser_info.binary_path)

        if b_type in [SupportedBrowsers.CHROME, SupportedBrowsers.BRAVE, SupportedBrowsers.OPERA,
                      SupportedBrowsers.VIVALDI, SupportedBrowsers.CHROMIUM, SupportedBrowsers.COMET]:
            if HAS_WEBDRIVER_MANAGER and ChromeDriverManager is not None and major_ver:
                try:
                    driver_path = ChromeDriverManager(driver_version=major_ver).install()
                    service = ChromeService(driver_path)
                    return webdriver.Chrome(service=service, options=options)
                except Exception as e_mgr:
                    logger.warning(f"WebDriverManager com versão {major_ver} falhou ({e_mgr}). Tentando Selenium Manager...")

            try:
                return webdriver.Chrome(options=options)
            except Exception as e1:
                logger.warning(f"Selenium Manager nativo falhou para Chromium ({e1}). Tentando WebDriverManager padrão...")
                if HAS_WEBDRIVER_MANAGER and ChromeDriverManager is not None:
                    driver_path = ChromeDriverManager().install()
                    service = ChromeService(driver_path)
                    return webdriver.Chrome(service=service, options=options)
                raise e1

        elif b_type == SupportedBrowsers.EDGE:
            if HAS_WEBDRIVER_MANAGER and EdgeChromiumDriverManager is not None and major_ver:
                try:
                    driver_path = EdgeChromiumDriverManager(driver_version=major_ver).install()
                    service = EdgeService(driver_path)
                    return webdriver.Edge(service=service, options=options)
                except Exception as e_mgr:
                    logger.warning(f"WebDriverManager Edge com versão {major_ver} falhou ({e_mgr}). Tentando Selenium Manager...")

            try:
                return webdriver.Edge(options=options)
            except Exception as e1:
                logger.warning(f"Selenium Manager nativo falhou para Edge ({e1}). Tentando WebDriverManager padrão...")
                if HAS_WEBDRIVER_MANAGER and EdgeChromiumDriverManager is not None:
                    driver_path = EdgeChromiumDriverManager().install()
                    service = EdgeService(driver_path)
                    return webdriver.Edge(service=service, options=options)
                raise e1

        elif b_type in [SupportedBrowsers.FIREFOX, SupportedBrowsers.TOR]:
            try:
                return webdriver.Firefox(options=options)
            except Exception as e1:
                logger.warning(f"Selenium Manager nativo falhou para Firefox ({e1}). Tentando WebDriverManager...")
                if HAS_WEBDRIVER_MANAGER and GeckoDriverManager is not None:
                    service = FirefoxService(GeckoDriverManager().install())
                    return webdriver.Firefox(service=service, options=options)
                raise e1

        elif b_type == SupportedBrowsers.SAFARI:
            return webdriver.Safari(options=options)

        raise ValueError(f"Driver não encontrado para {b_type}")


class BrowserFactory:
    """Fábrica principal para obtenção de instâncias do WebDriver na aplicação."""

    @classmethod
    def create(cls,
               preferred_browser: Optional[SupportedBrowsers] = None,
               headless: bool = False,
               custom_profile: bool = True,
               use_system_profile: bool = False,
               options_args: Optional[List[str]] = None) -> WebDriver:

        browser_info = BrowserCompatibility.resolve_browser(preferred=preferred_browser)
        logger.info(f"Iniciando navegação via [{browser_info.display_name}] | Executável: {browser_info.binary_path}")

        options = OptionsFactory.build_options(
            browser_info=browser_info,
            headless=headless,
            custom_profile=custom_profile,
            use_system_profile=use_system_profile,
            options_args=options_args
        )

        driver = DriverFactory.create_driver(browser_info, options)

        try:
            if browser_info.browser_type != SupportedBrowsers.SAFARI and driver is not None:
                driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
                })
        except Exception:
            pass

        return driver


class BrowserManager:
    """Gerenciador de Contexto para ciclo de vida seguro do navegador."""

    def __init__(self,
                 preferred_browser: Optional[SupportedBrowsers] = None,
                 headless: bool = False,
                 custom_profile: bool = True,
                 use_system_profile: bool = False,
                 options_args: Optional[List[str]] = None):
        self.preferred_browser = preferred_browser
        self.headless = headless
        self.custom_profile = custom_profile
        self.use_system_profile = use_system_profile
        self.options_args = options_args
        self.driver: Optional[WebDriver] = None

    def __enter__(self) -> WebDriver:
        self.driver = BrowserFactory.create(
            preferred_browser=self.preferred_browser,
            headless=self.headless,
            custom_profile=self.custom_profile,
            use_system_profile=self.use_system_profile,
            options_args=self.options_args
        )
        return self.driver

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Erro ao fechar sessão do driver: {e}")