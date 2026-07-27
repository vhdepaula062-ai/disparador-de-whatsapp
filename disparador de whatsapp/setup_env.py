import sys
import subprocess

DEPENDENCIAS = [
    "customtkinter",
    "selenium",
    "webdriver-manager",
    "pyautogui",
    "pyperclip",
    "pillow",
    "requests",
    "google-genai",
    "pywin32",
    "pywin62",
    "pyinstaller",
    "maturin"
]


def instalar_dependencias():
    print("🚀 [SETUP] Verificando e instalando dependências do Lead Hunter Pro...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])

    for pacote in DEPENDENCIAS:
        try:
            print(f"📦 Instalando/Atualizando: {pacote}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pacote])
        except subprocess.CalledProcessError as e:
            print(f"✖ Erro ao instalar {pacote}: {e}")

    print("\n🟢 [SUCESSO] Todas as dependências foram instaladas com sucesso!")
    print("👉 Agora você já pode executar o arquivo 'new.py' no PyCharm para testar a aplicação.")


if __name__ == "__main__":
    instalar_dependencias()
