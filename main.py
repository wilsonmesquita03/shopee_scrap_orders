import json
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
from collections import defaultdict
import re
from datetime import datetime

load_dotenv()

SHOPEE_EMAIL = os.getenv("SHOPEE_EMAIL")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

LOGIN_URL = "https://accounts.shopee.com.br/seller/login"
COOKIES_FILE = "cookies.json"

AUTH_COOKIES = [
    "SPC_EC",
    "SPC_R_T_ID",
    "SPC_R_T_IV",
    "SPC_T_ID",
    "SPC_T_IV",
    "SPC_SC_SESSION",
    "SPC_SEC_SI"
]

def parse_prazo(prazo_text):
    """
    Extrai a data do texto do pedido.
    Se não encontrar, assume hoje no horário local.
    Não faz conversão de fuso horário para evitar deslocamento.
    """
    match = re.search(r"\d{2}/\d{2}/\d{4}", prazo_text)
    if match:
        prazo = match.group(0)  # já está no formato correto
    else:
        prazo = datetime.now().strftime("%d/%m/%Y")  # hoje
    return prazo


def gerar_listas(orders):
    # Agrupa pedidos por prazo
    separacao = defaultdict(lambda: defaultdict(int))

    for order in orders:
        prazo = order.get("prazo", "Hoje")
        item = order["item"]
        quantidade = order.get("quantidade", 0) or 0

        separacao[prazo][item] += quantidade

    # Converte para lista de dicts dentro de cada prazo
    lista_separacao = {}
    for prazo, items in separacao.items():
        lista_separacao[prazo] = [
            {"item": nome, "quantidade": total} for nome, total in items.items()
        ]

    # Lista de pedidos é a original
    lista_pedidos = orders

    return lista_separacao, lista_pedidos

def load_cookies_if_exist(context):
    """Carrega cookies e verifica se os cookies essenciais de autenticação existem."""
    if not os.path.exists(COOKIES_FILE):
        print("⚠ Nenhum arquivo de cookies encontrado.")
        return False

    with open(COOKIES_FILE, "r") as f:
        cookies = json.load(f)

    # Verifica se possui pelo menos os cookies essenciais
    cookie_names = {c["name"] for c in cookies}

    has_auth = all(ac in cookie_names for ac in AUTH_COOKIES)

    if not has_auth:
        print("⚠ Cookies encontrados, mas NÃO há cookies de autenticação. Login será necessário.")
        return False

    print("🍪 Cookies de autenticação encontrados. Sessão carregada!")
    context.add_cookies(cookies)
    return True


def save_cookies(context):
    """Salva cookies mantendo apenas os essenciais de login."""
    all_cookies = context.cookies()

    # Filtra apenas cookies essenciais (opcional, mas recomendado)
    auth_cookies = [c for c in all_cookies if c["name"] in AUTH_COOKIES]

    with open(COOKIES_FILE, "w") as f:
        json.dump(auth_cookies, f)

    print("💾 Cookies de autenticação salvos.")


def login(page):
    print("➡ Aguardando campos de login...")

    # Espera forte pelos campos
    page.wait_for_selector("input[name='loginKey'], input[type='text']", timeout=20000)
    page.wait_for_selector("input[name='password'], input[type='password']", timeout=20000)

    # Preenche email
    page.fill("input[name='loginKey'], input[type='text']", SHOPEE_EMAIL)
    # Preenche senha
    page.fill("input[name='password'], input[type='password']", SHOPEE_PASSWORD)

    page.wait_for_load_state("networkidle")

    # Espera realmente o botão existir e estar clicável
    login_button = wait_for_login_button(page)

    print("➡ Clicando no botão...")
    login_button.click(timeout=10000)
    print("✔ Clique enviado!")

    print("➡ Aguardando página de verificação...")
    page.wait_for_load_state("networkidle")

    print("⏳ Aguardando você confirmar o e-mail...")

    try:
        time.sleep(10)
        click_email_verification(page)  # ✅ chama a função que clica no botão
        print("⏳ Aguarde até confirmar o e-mail...")
        page.wait_for_url("https://seller.shopee.com.br/portal/**", timeout=300000)
        print("✔ E-mail confirmado! Login liberado.")
    except Exception:
        print("⚠ Não foi necessário clicar em verificação por e-mail ou não encontrou botão.")


def wait_for_login_button(page):
    print("🔎 Tentando localizar o botão 'Entre' por texto...")

    # 1 — XPath por texto (funciona em 99% dos sites)
    try:
        btn = page.locator("//button[contains(., 'Entre')]")
        btn.wait_for(state="visible", timeout=8000)

        print("✔ Botão encontrado com XPath!")
        return btn
    except:
        print("❌ Botão via XPath não encontrado")

    # 2 — Buscas alternativas
    SELECTORS = [
        "button:has-text('Entre')",
        "button:has-text('ENTRE')",
        "button:has-text('Login')",
        "button.ZzzLTG",
        "button.gP623l",
        "button[disabled]",
        "button",
    ]

    for sel in SELECTORS:
        try:
            print(f"Testando seletor: {sel}")
            btn = page.locator(sel)
            btn.wait_for(state="visible", timeout=3000)
            print(f"✔ Botão encontrado: {sel}")
            return btn
        except:
            pass

    # 3 — Busca profunda dentro de todos elementos (fallback final)
    try:
        btns = page.locator("button").all()
        print(f"🔎 Encontrados {len(btns)} botões, analisando conteúdo...")

        for i, b in enumerate(btns):
            try:
                text = b.inner_text().strip()
                print(f"Botão {i}: {text}")
                if "entre" in text.lower():
                    print("✔ Botão encontrado pela varredura manual!")
                    return b
            except:
                pass
    except:
        pass

    raise Exception("❌ Nenhum botão com texto 'Entre' foi encontrado de forma alguma.")

def click_email_verification(page):
    print("🔎 Procurando botão 'Verificar via link por E-mail'...")

    # Seleciona todos os botões
    buttons = page.locator("button")
    count = buttons.count()
    print(f"🔎 Encontrados {count} botões, verificando texto interno...")

    for i in range(count):
        btn = buttons.nth(i)
        try:
            # inner_text pega texto de todos os filhos
            text = btn.inner_text().strip()
            if "verificar via link por e-mail" in text.lower():
                print(f"✔ Botão encontrado no índice {i}: {text}")
                btn.click()
                return True
        except Exception as e:
            print(f"Erro ao ler botão {i}: {e}")

    raise Exception("❌ Não encontrei o botão 'Verificar via link por E-mail'.")

def extract_orders(page):
    print("➡ Rolando página para carregar todos os pedidos...")
    previous_height = 0

    # Scroll infinito até não aparecer mais nada novo
    while True:
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1)

        height = page.evaluate("document.body.scrollHeight")
        if height == previous_height:
            break
        previous_height = height

    print("➡ Buscando cards de pedidos...")
    cards = page.query_selector_all(".order-card-body")
    print(f"📦 Total de pedidos encontrados: {len(cards)}")

    orders = []

    for card in cards:
        try:
            item_name = card.query_selector(".item-name")
            item_desc = card.query_selector(".item-description")
            item_amount = card.query_selector(".item-amount")
            status_desc = card.query_selector(".status-description")

            # Quantidade
            quantidade_raw = item_amount.inner_text().strip() if item_amount else None
            quantidade = int(quantidade_raw.replace("x", "").strip()) if quantidade_raw else None

            # Nome + descrição
            nome = item_name.inner_text().strip() if item_name else ""
            desc = item_desc.inner_text().strip() if item_desc else ""

            # Prazo
            prazo_text = status_desc.inner_text().strip() if status_desc else ""
            
            # Regex para encontrar data no formato dd/mm/yyyy
            prazo = parse_prazo(prazo_text)

            order = {
                "item": f"{nome} {desc}".strip(),
                "quantidade": quantidade,
                "prazo": prazo
            }

            orders.append(order)

        except Exception as e:
            print("Erro ao parsear card:", e)

    return orders

def extrair_pedidos():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        context = browser.new_context(
            locale="pt-BR",  # define o idioma do navegador
            extra_http_headers={"Accept-Language": "pt-BR"}  # define o cabeçalho HTTP
        )
        page = context.new_page()

        # Carrega cookies se existir
        has_cookies = load_cookies_if_exist(context)

        # Vai para página de pedidos
        page.goto("https://seller.shopee.com.br/portal/sale/order?type=toship&source=all&invoice_status=all_type&sort_by=ship_by_date_asc")

        # Faz login se necessário
        if not has_cookies or LOGIN_URL in page.url.lower():
            login(page)
            save_cookies(context)
            page.goto("https://seller.shopee.com.br/portal/sale/order?type=toship&source=all&invoice_status=all_type&sort_by=ship_by_date_asc")

        time.sleep(10)

        # Extrai os pedidos
        orders = extract_orders(page)

        browser.close()

        summary = gerar_listas(orders)

        return summary

if __name__ == "__main__":
    pedidos = extrair_pedidos()
