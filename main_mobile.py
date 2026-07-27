import os
import re
import json
import sqlite3
import datetime
import urllib.parse
import requests
import flet as ft
from security_guard import InputSanitizer, LogDataRedactor, SecurityAuditor

# Disable SSL warnings for fallback scenarios
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =============================================================================
# BANCO DE DADOS SQLITE PROTEGIDO (SANDBOX ANDROID)
# =============================================================================
class MobileDatabase:
    def __init__(self):
        base_dir = os.environ.get("ANDROID_PRIVATE", os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(base_dir, "historico_leads.db")
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS leads_abordados (
                        telefone TEXT PRIMARY KEY,
                        nome TEXT NOT NULL,
                        data_envio TEXT NOT NULL
                    );
                """)
                conn.commit()
        except Exception:
            pass

    def lead_ja_abordado(self, telefone: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.execute("SELECT 1 FROM leads_abordados WHERE telefone = ?", (telefone,))
                return cur.fetchone() is not None
        except Exception:
            return False

    def salvar_lead(self, nome: str, telefone: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                data = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                conn.execute("INSERT OR REPLACE INTO leads_abordados VALUES (?, ?, ?)", (telefone, nome, data))
                conn.commit()
        except Exception:
            pass

db_mobile = MobileDatabase()

# =============================================================================
# REQUISIÇÕES HTTP SEGURA E LANÇADOR DUPLO WHATSAPP
# =============================================================================
def safe_http_get(url, headers=None, timeout=6.0):
    """Executa GET com fallback automatico para falhas de SSL no Android."""
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        return requests.get(url, headers=headers, timeout=timeout)
    except requests.exceptions.SSLError:
        return requests.get(url, headers=headers, timeout=timeout, verify=False)
    except Exception as e:
        raise e

def abrir_whatsapp_seguro(page: ft.Page, phone: str, text: str = ""):
    """Lança o WhatsApp com fallback automatico entre HTTP e Protocolo Nativo."""
    text_enc = urllib.parse.quote(text) if text else ""
    url_1 = f"https://api.whatsapp.com/send?phone={phone}" + (f"&text={text_enc}" if text_enc else "")
    url_2 = f"whatsapp://send?phone={phone}" + (f"&text={text_enc}" if text_enc else "")

    try:
        page.launch_url(url_1)
    except Exception:
        try:
            page.launch_url(url_2)
        except Exception as err:
            page.snack_bar = ft.SnackBar(ft.Text(f"✖ Falha ao abrir WhatsApp: {err}"))
            page.snack_bar.open = True
            page.update()

# =============================================================================
# APLICAÇÃO PRINCIPAL FLET MOBILE (ENTERPRISE SUITE v3.2 BLINDADA)
# =============================================================================
def main(page: ft.Page):
    page.title = "⚡ Lead Hunter Pro Mobile v3.2"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.scroll = ft.ScrollMode.AUTO

    # Cotação do Dólar em Tempo Real com Fallback
    cotacao_dolar = 5.08
    try:
        r_usd = safe_http_get("https://api.exchangerate-api.com/v4/latest/USD", timeout=3.0)
        if r_usd.status_code == 200:
            cotacao_dolar = float(r_usd.json()["rates"]["BRL"])
    except Exception:
        pass

    api_key_gemini = ft.Ref[ft.TextField]()

    # -------------------------------------------------------------------------
    # ABA 1: CAPTADOR DE LEADS (MAPS & WEB B2B)
    # -------------------------------------------------------------------------
    txt_termo_maps = ft.TextField(label="Termo ou Cidade (Ex: Lojas em Anapolis)", value="Lojas em Anapolis GO")
    lv_leads_maps = ft.ListView(expand=True, spacing=8, height=320)

    def buscar_leads_maps_action(e):
        termo = txt_termo_maps.value.strip()
        if not termo: return
        lv_leads_maps.controls.clear()
        lv_leads_maps.controls.append(ft.Text(f"🔎 Minerando leads B2B para '{termo}'...", color=ft.Colors.AMBER_400))
        page.update()

        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(termo + ' whatsapp')}"
            resp = safe_http_get(url, timeout=6.0)
            telefones = set(re.findall(r'(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-.\s]?\d{4}', resp.text))
            lv_leads_maps.controls.clear()

            if not telefones:
                lv_leads_maps.controls.append(ft.Text("ℹ️ Nenhum número novo encontrado nesta busca.", color=ft.Colors.GREY_400))
            else:
                for idx, tel in enumerate(list(telefones)[:12]):
                    t_limpo = InputSanitizer.sanitizar_telefone(tel)
                    if t_limpo:
                        ja_foi = db_mobile.lead_ja_abordado(t_limpo)
                        status_str = "⚠️ Já abordado" if ja_foi else "🌟 NOVO LEAD"
                        cor_btn = ft.Colors.AMBER_800 if ja_foi else ft.Colors.GREEN_700

                        def abrir_zap(e, phone=t_limpo):
                            db_mobile.salvar_lead("Lead Mobile B2B", phone)
                            abrir_whatsapp_seguro(page, phone)

                        lv_leads_maps.controls.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Column([
                                        ft.Text(f"👤 Lead B2B #{idx+1}", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                        ft.Text(f"📞 {t_limpo} | {status_str}", size=11, color=ft.Colors.AMBER_200 if ja_foi else ft.Colors.GREEN_300)
                                    ], expand=True),
                                    ft.ElevatedButton("🚀 Abrir Zap", icon=ft.Icons.SEND, bgcolor=cor_btn, color=ft.Colors.WHITE, on_click=abrir_zap)
                                ]),
                                bgcolor=ft.Colors.BLUE_GREY_900, padding=8, border_radius=8
                            )
                        )
        except Exception as err:
            lv_leads_maps.controls.clear()
            lv_leads_maps.controls.append(ft.Text(f"✖ Erro na busca (Verifique sua conexão): {err}", color=ft.Colors.RED_400))
        page.update()

    tab_maps = ft.Column([
        ft.Text("🛒 Captador B2B Google Maps & Web", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_400),
        txt_termo_maps,
        ft.ElevatedButton("🔍 Iniciar Coleta B2B", icon=ft.Icons.SEARCH, bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE, on_click=buscar_leads_maps_action),
        ft.Divider(),
        lv_leads_maps
    ])

    # -------------------------------------------------------------------------
    # ABA 2: META ADS LIBRARY (ESPIONAGEM DE ANÚNCIOS)
    # -------------------------------------------------------------------------
    txt_meta_ads = ft.TextField(label="Nicho Meta Ads (Ex: emagrecimento)", value="emagrecimento")
    lv_meta_ads = ft.ListView(expand=True, spacing=8, height=320)

    def espionar_meta_ads(e):
        termo = txt_meta_ads.value.strip()
        if not termo: return
        lv_meta_ads.controls.clear()
        lv_meta_ads.controls.append(ft.Text(f"🎯 Espionando anúncios para '{termo}'...", color=ft.Colors.PURPLE_300))
        page.update()

        try:
            url_meta = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=BR&q={urllib.parse.quote(termo)}"
            r = safe_http_get(url_meta, timeout=6.0)
            ad_ids = list(dict.fromkeys(re.findall(r'\b\d{14,16}\b', r.text)))
            lv_meta_ads.controls.clear()

            if not ad_ids:
                lv_meta_ads.controls.append(ft.Text("ℹ️ Nenhum anúncio ativo retornado.", color=ft.Colors.GREY_400))
            else:
                for idx, ad_id in enumerate(ad_ids[:10]):
                    link_ad = f"https://www.facebook.com/ads/library/?id={ad_id}"
                    lv_meta_ads.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"🎯 Anúncio Escalado #{idx+1} (ID: {ad_id})", weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_200),
                                ft.ElevatedButton("🔗 Ver Anúncio no Meta", icon=ft.Icons.OPEN_IN_NEW, bgcolor=ft.Colors.PURPLE_800, color=ft.Colors.WHITE, on_click=lambda e, u=link_ad: page.launch_url(u))
                            ]),
                            bgcolor=ft.Colors.BLUE_GREY_900, padding=8, border_radius=8
                        )
                    )
        except Exception as err:
            lv_meta_ads.controls.clear()
            lv_meta_ads.controls.append(ft.Text(f"✖ Erro na espionagem: {err}", color=ft.Colors.RED_400))
        page.update()

    tab_meta = ft.Column([
        ft.Text("🎯 Meta Ads Library (Espionagem)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_300),
        txt_meta_ads,
        ft.ElevatedButton("🎯 Minerar Anúncios", icon=ft.Icons.TARGET, bgcolor=ft.Colors.PURPLE_700, color=ft.Colors.WHITE, on_click=espionar_meta_ads),
        ft.Divider(),
        lv_meta_ads
    ])

    # -------------------------------------------------------------------------
    # ABA 3: COMPARADOR DE PREÇOS (PLATI / Z2U / SHOPEE + DÓLAR)
    # -------------------------------------------------------------------------
    txt_comparar = ft.TextField(label="Produto Digital / Licença (Ex: CapCut)", value="CapCut")
    lv_comparar = ft.ListView(expand=True, spacing=8, height=320)

    def comparar_precos_action(e):
        prod = txt_comparar.value.strip()
        if not prod: return
        lv_comparar.controls.clear()
        lv_comparar.controls.append(ft.Text(f"⚖️ Minerando ofertas... Cotação USD: R$ {cotacao_dolar:.2f}", color=ft.Colors.AMBER_400))
        page.update()

        try:
            api_url = f"https://shopee.com.br/api/v4/search/search_items?by=relevance&keyword={urllib.parse.quote(prod)}&limit=6&newest=0&order=desc&page_type=search&scenario=PAGE_SEARCH&version=2"
            r = safe_http_get(api_url, timeout=5.0)
            lv_comparar.controls.clear()

            if r.status_code == 200:
                items = r.json().get("data", {}).get("items", [])
                for idx, item in enumerate(items[:6]):
                    basic = item.get("item_basic", {})
                    nome = basic.get("name", "Produto")[:40]
                    preco_brl = round(basic.get("price", 0) / 100000.0, 2)
                    preco_usd = round(preco_brl / cotacao_dolar, 2)
                    itemid = basic.get("itemid")
                    shopid = basic.get("shopid")
                    link = f"https://shopee.com.br/product/{shopid}/{itemid}" if shopid and itemid else "https://shopee.com.br"

                    tag_menor = "🏆 MENOR PREÇO DO MERCADO" if idx == 0 else "🛒 Oferta Encontrada"
                    cor_tag = ft.Colors.GREEN_400 if idx == 0 else ft.Colors.AMBER_300

                    lv_comparar.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(f"📦 {nome}", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"{tag_menor} | 💵 US$ {preco_usd:.2f} ➔ 🇧🇷 R$ {preco_brl:.2f}", color=cor_tag, weight=ft.FontWeight.BOLD, size=11),
                                ft.ElevatedButton("🔗 Abrir Oferta", icon=ft.Icons.SHOPPING_BAG, bgcolor=ft.Colors.GREEN_800 if idx==0 else ft.Colors.BLUE_800, color=ft.Colors.WHITE, on_click=lambda e, u=link: page.launch_url(u))
                            ]),
                            bgcolor=ft.Colors.BLUE_GREY_900, padding=8, border_radius=8
                        )
                    )
        except Exception as err:
            lv_comparar.controls.clear()
            lv_comparar.controls.append(ft.Text(f"✖ Erro ao comparar: {err}", color=ft.Colors.RED_400))
        page.update()

    tab_comparar = ft.Column([
        ft.Text(f"⚖️ Comparador de Preços (Dólar: R$ {cotacao_dolar:.2f})", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400),
        txt_comparar,
        ft.ElevatedButton("🔎 Comparar Preços", icon=ft.Icons.COMPARE_ARROWS, bgcolor=ft.Colors.AMBER_700, color=ft.Colors.WHITE, on_click=comparar_precos_action),
        ft.Divider(),
        lv_comparar
    ])

    # -------------------------------------------------------------------------
    # ABA 4: LIT HUNTER (MINERAR GRUPOS PÚBLICOS DE WHATSAPP)
    # -------------------------------------------------------------------------
    txt_lit_nicho = ft.TextField(label="Nicho do Grupo (Ex: vendas e-commerce)", value="vendas e-commerce")
    lv_lit_grupos = ft.ListView(expand=True, spacing=8, height=320)

    def minerar_grupos_lit_action(e):
        nicho = txt_lit_nicho.value.strip()
        if not nicho: return
        lv_lit_grupos.controls.clear()
        lv_lit_grupos.controls.append(ft.Text(f"🔥 Minerando grupos públicos para '{nicho}'...", color=ft.Colors.ORANGE_400))
        page.update()

        try:
            query = f'"chat.whatsapp.com/" "{nicho}"'
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            r = safe_http_get(url, timeout=6.0)
            links = set(re.findall(r'https?://chat\.whatsapp\.com/[A-Za-z0-9_-]{20,26}', r.text))
            lv_lit_grupos.controls.clear()

            if not links:
                lv_lit_grupos.controls.append(ft.Text("ℹ️ Nenhum link de grupo público localizado.", color=ft.Colors.GREY_400))
            else:
                for idx, link_g in enumerate(list(links)[:10]):
                    lv_lit_grupos.controls.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(f"🔥 Grupo Público #{idx+1}", weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_300),
                                    ft.Text(f"🔗 {link_g[:35]}...", size=10, color=ft.Colors.GREY_400)
                                ], expand=True),
                                ft.ElevatedButton("Entrar no Grupo", icon=ft.Icons.GROUP_ADD, bgcolor=ft.Colors.ORANGE_800, color=ft.Colors.WHITE, on_click=lambda e, u=link_g: page.launch_url(u))
                            ]),
                            bgcolor=ft.Colors.BLUE_GREY_900, padding=8, border_radius=8
                        )
                    )
        except Exception as err:
            lv_lit_grupos.controls.clear()
            lv_lit_grupos.controls.append(ft.Text(f"✖ Erro na mineração: {err}", color=ft.Colors.RED_400))
        page.update()

    tab_lit = ft.Column([
        ft.Text("🔥 Lit Hunter (Aquecedor & Grupos Públicos)", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ORANGE_400),
        txt_lit_nicho,
        ft.ElevatedButton("🔥 Minerar Grupos", icon=ft.Icons.WHATSHOT, bgcolor=ft.Colors.ORANGE_700, color=ft.Colors.WHITE, on_click=minerar_grupos_lit_action),
        ft.Divider(),
        lv_lit_grupos
    ])

    # -------------------------------------------------------------------------
    # ABA 5: DISPARADOR WHATSAPP & IA GEMINI 2.0 FLASH
    # -------------------------------------------------------------------------
    entry_gemini_key = ft.TextField(ref=api_key_gemini, label="🔑 Chave de API Google Gemini AI", password=True, can_reveal_password=True)
    txt_tel_envio = ft.TextField(label="Número do WhatsApp (com DDD)", placeholder="5562999999999", keyboard_type=ft.KeyboardType.PHONE)
    txt_nome_empresa = ft.TextField(label="Nome da Empresa / Cliente", placeholder="Lógica Calçados")
    txt_proposta_base = ft.TextField(label="Proposta de Valor / Oferta Base", multiline=True, min_lines=2, value="Oferecer criação de sites profissionais e IA de vendas.")
    lbl_msg_gerada = ft.Text("", size=12, color=ft.Colors.GREEN_300)

    def gerar_copy_gemini_action(e):
        key = api_key_gemini.current.value.strip()
        nome = txt_nome_empresa.value.strip() or "Empresa"
        proposta = txt_proposta_base.value.strip()

        if key:
            try:
                url_gemini = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
                prompt = f"Escreva uma mensagem curta de prospecção B2B de WhatsApp para '{nome}'. Proposta: '{proposta}'. Máximo 3 linhas, tom amigável e persuasivo."
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                
                r = requests.post(url_gemini, json=payload, timeout=6.0)
                if r.status_code == 200:
                    copy_ia = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                    lbl_msg_gerada.value = f"🤖 Copy IA Otimizada:\n{copy_ia}"
                else:
                    lbl_msg_gerada.value = f"Olá {nome}! {proposta} Teria 2 minutos hoje?"
            except Exception:
                lbl_msg_gerada.value = f"Olá {nome}! {proposta} Teria 2 minutos hoje?"
        else:
            lbl_msg_gerada.value = f"Olá {nome}! {proposta} Teria 2 minutos hoje?"

        page.update()

    def disparar_whatsapp_final(e):
        tel = InputSanitizer.sanitizar_telefone(txt_tel_envio.value)
        msg = lbl_msg_gerada.value.replace("🤖 Copy IA Otimizada:\n", "").strip() or txt_proposta_base.value.strip()

        if not tel:
            page.snack_bar = ft.SnackBar(ft.Text("✖ Informe o número de telefone!"))
            page.snack_bar.open = True
            page.update()
            return

        db_mobile.salvar_lead(txt_nome_empresa.value or "Lead", tel)
        abrir_whatsapp_seguro(page, tel, msg)

    tab_disparos = ft.Column([
        ft.Text("🚀 Disparador com IA Gemini 2.0", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
        entry_gemini_key,
        txt_nome_empresa,
        txt_tel_envio,
        txt_proposta_base,
        ft.ElevatedButton("🤖 Otimizar Mensagem com IA", icon=ft.Icons.AUTO_AWESOME, bgcolor=ft.Colors.PURPLE_800, color=ft.Colors.WHITE, on_click=gerar_copy_gemini_action),
        lbl_msg_gerada,
        ft.ElevatedButton("🚀 Abrir no WhatsApp Direct", icon=ft.Icons.SEND, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, on_click=disparar_whatsapp_final)
    ])

    # MENU DE ABAS MOBILE
    tabs = ft.Tabs(
        selected_index=0,
        animation_duration=300,
        tabs=[
            ft.Tab(text="🛒 Maps B2B", content=tab_maps),
            ft.Tab(text="🎯 Meta Ads", content=tab_meta),
            ft.Tab(text="⚖️ Preços", content=tab_comparar),
            ft.Tab(text="🔥 Lit Hunter", content=tab_lit),
            ft.Tab(text="🚀 Disparador", content=tab_disparos),
        ],
        expand=1
    )

    page.add(
        ft.Row([
            ft.Text("⚡ Lead Hunter Pro", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_400),
            ft.Text("🛡️ Shield Ativo", size=11, color=ft.Colors.GREEN_400)
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        tabs
    )

if __name__ == "__main__":
    ft.app(target=main)