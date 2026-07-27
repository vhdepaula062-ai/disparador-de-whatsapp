import os
import re
import json
import sqlite3
import datetime
import urllib.parse
import requests

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader
from kivy.core.window import Window
from kivy.utils import platform

# =============================================================================
# BANCO DE DADOS SQLITE NATIVO
# =============================================================================
class MobileDatabase:
    def __init__(self, db_path="historico_leads.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS leads_abordados (
                    telefone TEXT PRIMARY KEY,
                    nome TEXT NOT NULL,
                    data_envio TEXT NOT NULL
                );
            """)
            conn.commit()

    def lead_ja_abordado(self, telefone: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute("SELECT 1 FROM leads_abordados WHERE telefone = ?", (telefone,))
            return cur.fetchone() is not None

    def salvar_lead(self, nome: str, telefone: str):
        with sqlite3.connect(self.db_path) as conn:
            data = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
            conn.execute("INSERT OR REPLACE INTO leads_abordados VALUES (?, ?, ?)", (telefone, nome, data))
            conn.commit()

db_mobile = MobileDatabase()

# =============================================================================
# APLICAÇÃO KIVY NATIVA ANDROID
# =============================================================================
class LeadHunterProApp(App):
    def build(self):
        self.title = "⚡ Lead Hunter Pro Mobile"
        
        # Painel Principal com Abas
        tp = TabbedPanel(do_default_tab=False)

        # ---------------------------------------------------------------------
        # ABA 1: CAPTADOR LEADS MAPS & WEB
        # ---------------------------------------------------------------------
        tab_maps = TabbedPanelHeader(text="🛒 Leads B2B")
        layout_maps = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        layout_maps.add_widget(Label(text="🛒 Captador Google Maps & Web", font_size=18, bold=True, size_hint_y=None, height=40))
        self.txt_termo_maps = TextInput(text="Lojas em Anapolis GO", multiline=False, size_hint_y=None, height=45)
        layout_maps.add_widget(self.txt_termo_maps)

        btn_buscar_maps = Button(text="🔍 Iniciar Pesquisa Leads", background_color=(0.1, 0.5, 0.9, 1), size_hint_y=None, height=50)
        btn_buscar_maps.bind(on_release=self.buscar_leads_maps)
        layout_maps.add_widget(btn_buscar_maps)

        self.box_results_maps = BoxLayout(orientation='vertical', spacing=8, size_hint_y=None)
        self.box_results_maps.bind(minimum_height=self.box_results_maps.setter('height'))
        
        scroll_maps = ScrollView(size_hint=(1, 1))
        scroll_maps.add_widget(self.box_results_maps)
        layout_maps.add_widget(scroll_maps)
        
        tab_maps.content = layout_maps
        tp.add_widget(tab_maps)

        # ---------------------------------------------------------------------
        # ABA 2: COMPARADOR DE PREÇOS
        # ---------------------------------------------------------------------
        tab_precos = TabbedPanelHeader(text="⚖️ Preços")
        layout_precos = BoxLayout(orientation='vertical', padding=10, spacing=10)

        layout_precos.add_widget(Label(text="⚖️ Comparador Marketplace", font_size=18, bold=True, size_hint_y=None, height=40))
        self.txt_produto = TextInput(text="CapCut", multiline=False, size_hint_y=None, height=45)
        layout_precos.add_widget(self.txt_produto)

        btn_comparar = Button(text="🔎 Comparar Ofertas", background_color=(0.9, 0.6, 0.1, 1), size_hint_y=None, height=50)
        btn_comparar.bind(on_release=self.comparar_precos)
        layout_precos.add_widget(btn_comparar)

        self.box_results_precos = BoxLayout(orientation='vertical', spacing=8, size_hint_y=None)
        self.box_results_precos.bind(minimum_height=self.box_results_precos.setter('height'))

        scroll_precos = ScrollView(size_hint=(1, 1))
        scroll_precos.add_widget(self.box_results_precos)
        layout_precos.add_widget(scroll_precos)

        tab_precos.content = layout_precos
        tp.add_widget(tab_precos)

        # ---------------------------------------------------------------------
        # ABA 3: DISPARADOR WHATSAPP & IA GEMINI
        # ---------------------------------------------------------------------
        tab_zap = TabbedPanelHeader(text="🚀 Disparador")
        layout_zap = BoxLayout(orientation='vertical', padding=10, spacing=10)

        layout_zap.add_widget(Label(text="🚀 Disparador WhatsApp Direct", font_size=18, bold=True, size_hint_y=None, height=40))
        
        self.txt_gemini_key = TextInput(hint_text="🔑 Chave de API Google Gemini (Opcional)", password=True, multiline=False, size_hint_y=None, height=45)
        layout_zap.add_widget(self.txt_gemini_key)

        self.txt_tel_envio = TextInput(hint_text="📞 Telefone WhatsApp (Ex: 5562999999999)", multiline=False, size_hint_y=None, height=45)
        layout_zap.add_widget(self.txt_tel_envio)

        self.txt_msg_envio = TextInput(text="Olá! Gostaria de apresentar nossas soluções B2B.", multiline=True, size_hint_y=None, height=90)
        layout_zap.add_widget(self.txt_msg_envio)

        btn_abrir_zap = Button(text="🚀 Abrir no WhatsApp", background_color=(0.1, 0.7, 0.3, 1), size_hint_y=None, height=50)
        btn_abrir_zap.bind(on_release=self.abrir_whatsapp_direct)
        layout_zap.add_widget(btn_abrir_zap)

        tab_zap.content = layout_zap
        tp.add_widget(tab_zap)

        return tp

    # FUNÇÕES DE EXECUÇÃO
    def abrir_url(self, url):
        import webbrowser
        webbrowser.open(url)

    def buscar_leads_maps(self, instance):
        termo = self.txt_termo_maps.text.strip()
        self.box_results_maps.clear_widgets()

        if not termo:
            return

        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(termo + ' whatsapp')}"
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=6.0)
            telefones = list(set(re.findall(r'(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-.\s]?\d{4}', r.text)))[:10]

            if not telefones:
                self.box_results_maps.add_widget(Label(text="Nenhum número encontrado.", size_hint_y=None, height=30))
            else:
                for tel in telefones:
                    digitos = "".join(filter(str.isdigit, tel))
                    if len(digitos) >= 10:
                        tel_f = f"55{digitos}" if not digitos.startswith("55") else digitos
                        btn = Button(text=f"📞 Lead: {tel_f} (Abrir Zap)", size_hint_y=None, height=45, background_color=(0.1, 0.7, 0.3, 1))
                        btn.bind(on_release=lambda inst, t=tel_f: self.abrir_url(f"https://api.whatsapp.com/send?phone={t}"))
                        self.box_results_maps.add_widget(btn)
        except Exception as e:
            self.box_results_maps.add_widget(Label(text=f"Erro: {e}", size_hint_y=None, height=30))

    def comparar_precos(self, instance):
        prod = self.txt_produto.text.strip()
        self.box_results_precos.clear_widgets()

        if not prod:
            return

        try:
            api_url = f"https://shopee.com.br/api/v4/search/search_items?by=relevance&keyword={urllib.parse.quote(prod)}&limit=5&newest=0&order=desc&page_type=search&scenario=PAGE_SEARCH&version=2"
            r = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5.0)

            if r.status_code == 200:
                items = r.json().get("data", {}).get("items", [])
                for item in items[:5]:
                    basic = item.get("item_basic", {})
                    nome = basic.get("name", "Produto")[:35]
                    preco = round(basic.get("price", 0) / 100000.0, 2)
                    itemid = basic.get("itemid")
                    shopid = basic.get("shopid")
                    link = f"https://shopee.com.br/product/{shopid}/{itemid}" if shopid and itemid else "https://shopee.com.br"

                    btn = Button(text=f"📦 {nome} — R$ {preco:.2f}", size_hint_y=None, height=45, background_color=(0.2, 0.4, 0.8, 1))
                    btn.bind(on_release=lambda inst, u=link: self.abrir_url(u))
                    self.box_results_precos.add_widget(btn)
        except Exception as e:
            self.box_results_precos.add_widget(Label(text=f"Erro: {e}", size_hint_y=None, height=30))

    def abrir_whatsapp_direct(self, instance):
        tel = "".join(filter(str.isdigit, self.txt_tel_envio.text))
        msg = urllib.parse.quote(self.txt_msg_envio.text)
        if tel:
            db_mobile.salvar_lead("Lead Direct", tel)
            self.abrir_url(f"https://api.whatsapp.com/send?phone={tel}&text={msg}")

if __name__ == '__main__':
    LeadHunterProApp().run()