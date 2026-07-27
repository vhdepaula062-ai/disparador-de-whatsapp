import urllib.parse
import flet as ft
from security_guard import InputSanitizer

def main(page: ft.Page):
    page.title = "⚡ Lead Hunter Pro Mobile"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # Componentes da Interface Mobile
    lbl_titulo = ft.Text("⚡ Lead Hunter Pro", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.LIGHT_BLUE_400)
    lbl_status = ft.Text("🛡️ Shield de Segurança Ativo", size=12, color=ft.colors.GREEN_400)

    txt_telefone = ft.TextField(
        label="Número do WhatsApp (com DDD)",
        placeholder="5562999999999",
        keyboard_type=ft.KeyboardType.PHONE
    )
    txt_mensagem = ft.TextField(
        label="Mensagem de Abordagem",
        multiline=True,
        min_lines=3,
        max_lines=5
    )

    def enviar_whatsapp_mobile(e):
        tel = InputSanitizer.sanitizar_telefone(txt_telefone.value)
        msg = txt_mensagem.value.strip()

        if not tel or not msg:
            page.snack_bar = ft.SnackBar(ft.Text("✖ Preencha o telefone e a mensagem!"))
            page.snack_bar.open = True
            page.update()
            return

        # Aciona o App do WhatsApp nativo do Android via Deep Link Intent
        msg_encoded = urllib.parse.quote(msg)
        intent_url = f"https://api.whatsapp.com/send?phone={tel}&text={msg_encoded}"
        page.launch_url(intent_url)

    btn_enviar = ft.ElevatedButton(
        "🚀 Abrir no WhatsApp Android",
        icon=ft.icons.SEND,
        bgcolor=ft.colors.GREEN_700,
        color=ft.colors.WHITE,
        on_click=enviar_whatsapp_mobile
    )

    page.add(
        lbl_titulo,
        lbl_status,
        ft.Divider(),
        txt_telefone,
        txt_mensagem,
        ft.Container(height=10),
        btn_enviar
    )

if __name__ == "__main__":
    ft.app(target=main)