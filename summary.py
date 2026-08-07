import requests
from datetime import datetime

NTFY_TOPIC = "moussa-news-1313"

INSTRUMENTS = [
    ("Petrole Brent", "BZ=F", "USD"),
    ("Petrole WTI", "CL=F", "USD"),
    ("Or (once)", "GC=F", "USD"),
    ("EUR/USD", "EURUSD=X", ""),
    ("Bitcoin", "BTC-USD", "USD"),
    ("Nasdaq", "^IXIC", "pts"),
    ("S&P 500", "^GSPC", "pts"),
    ("CAC 40", "^FCHI", "pts"),
]

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def get_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    meta = r.json()["chart"]["result"][0]["meta"]
    price = meta["regularMarketPrice"]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    change = (price - prev) / prev * 100 if prev else None
    return price, change

def fmt(price, change, unit):
    if price < 10:
        p = f"{price:.4f}"
    else:
        p = f"{price:,.2f}".replace(",", " ")
    c = f" ({change:+.2f}%)" if change is not None else ""
    u = f" {unit}" if unit else ""
    return f"{p}{u}{c}"

def main():
    lines = []
    for name, symbol, unit in INSTRUMENTS:
        try:
            price, change = get_quote(symbol)
            lines.append(f"{name} : {fmt(price, change, unit)}")
            print(f"OK {name}")
        except Exception as e:
            lines.append(f"{name} : indisponible")
            print(f"Erreur {name}: {e}")

    message = "\n".join(lines)
    requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode('utf-8'),
        headers={
            "Title": f"Marches du {datetime.now().strftime('%d/%m/%Y')}",
            "Tags": "chart_with_upwards_trend",
            "Priority": "default"
        },
        timeout=10
    )
    print("Resume envoye")

if __name__ == "__main__":
    main()
