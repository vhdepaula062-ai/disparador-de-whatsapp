import os
import sys
import subprocess

print("=" * 60)
print("🚀 INICIANDO A GERAÇÃO DO EXECUTÁVEL: Lead Hunter Pro v3.2.exe")
print("=" * 60)

# 1. Garante que as dependências de compilação estão atualizadas
print("\n📦 Verificando e instalando dependências de empacotamento...")
subprocess.run([
    sys.executable, "-m", "pip", "install", "--upgrade",
    "pyinstaller", "customtkinter", "pillow", "openpyxl",
    "pyautogui", "pyperclip", "requests", "selenium", "pywin32"
])

# 2. Verifica se o ícone personalizado existe na pasta raiz ou em /assets
icone_arg = []
if os.path.exists("leadhunterPro.ico"):
    icone_arg = ["--icon=leadhunterPro.ico"]
    print("🎨 Ícone 'leadhunterPro.ico' localizado na raiz e vinculado.")
elif os.path.exists(os.path.join("assets", "leadhunterPro.ico")):
    icone_arg = [f"--icon={os.path.join('assets', 'leadhunterPro.ico')}"]
    print("🎨 Ícone 'assets/leadhunterPro.ico' localizado e vinculado.")

# 3. Mapeamento de arquivos locais essenciais (.py) para inclusão
data_args = []
modulos_locais = ["security_guard.py", "browser_engine.py", "LHunter.py"]
for mod in modulos_locais:
    if os.path.exists(mod):
        data_args.append(f"--add-data={mod};.")
        print(f"📎 Módulo local '{mod}' embutido no pacote.")

# 4. Define os parâmetros de compilação completa e blindada
comando = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--name=Lead Hunter Pro v3.2",
    *icone_arg,
    *data_args,
    "--collect-all=customtkinter",
    "--collect-all=selenium",
    "--collect-all=google",
    "--collect-all=PIL",
    "--collect-all=requests",
    "--collect-all=openpyxl",
    "--hidden-import=security_guard",
    "--hidden-import=browser_engine",
    "--hidden-import=rust_engine",
    "--hidden-import=win32clipboard",
    "--hidden-import=win32gui",
    "--hidden-import=win32con",
    "new.py"
]

print("\n⚡ Empacotando o projeto em um único arquivo .exe com Shield de Segurança... Aguarde um momento...")
resultado = subprocess.run(comando)

# 5. Resultado final e verificação de saída
caminho_exe = os.path.abspath(os.path.join("dist", "Lead Hunter Pro v3.2.exe"))

if resultado.returncode == 0 and os.path.exists(caminho_exe):
    print("\n" + "=" * 60)
    print("🎉 COMPILAÇÃO CONCLUÍDA COM SUCESSO!")
    print("📁 O seu arquivo executável 'Lead Hunter Pro v3.2.exe' está pronto!")
    print(f"📍 Localização: {caminho_exe}")
    print("=" * 60)
else:
    print("\n✖ Ocorreu uma falha durante a geração do executável.")