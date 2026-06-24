# requirements.txt
# streamlit
# yfinance
# google-genai
# pandas

import streamlit as st
import yfinance as yf
from google import genai
from datetime import datetime

st.set_page_config(page_title="Stock Briefing", page_icon="📊", layout="wide")

TICKERS = ["SPYD.DE", "MSFT", "GOOGL", "AMZN", "META"]
GEMINI_API_KEY = "Your Key"
with st.sidebar:
    st.markdown("## 설정")
    gemini_key = st.text_input("Gemini API Key", type="password", placeholder="AQ. 또는 AIza...")
    run_btn = st.button("브리핑 시작", use_container_width=True, type="primary")

st.title("📊 Stock Briefing")

def get_eur_rate():
    try:
        fx = yf.Ticker("EURUSD=X")
        usd_per_eur = getattr(fx.fast_info, "last_price", None)
        if usd_per_eur and usd_per_eur > 0:
            return 1.0 / usd_per_eur
    except Exception:
        pass
    return 0.92

def get_price_block(ticker_obj, symbol, eur_rate):
    info = ticker_obj.fast_info
    current = getattr(info, "last_price", None)
    prev_close = getattr(info, "previous_close", None)
    if current is None:
        raise ValueError(f"{symbol}: 현재가 데이터 없음")
    currency = getattr(info, "currency", "USD")
    rate = eur_rate if currency != "EUR" else 1.0
    current_eur = current * rate
    prev_eur = (prev_close * rate) if prev_close else None
    change_eur = (current_eur - prev_eur) if prev_eur is not None else None
    change_pct = (change_eur / prev_eur * 100) if (prev_eur and prev_eur != 0) else None
    if change_pct is None:
        arrow = "➡️"
    elif change_pct > 0:
        arrow = "📈"
    elif change_pct < 0:
        arrow = "📉"
    else:
        arrow = "➡️"
    return {"current_eur": current_eur, "change_eur": change_eur, "change_pct": change_pct, "arrow": arrow}

def format_news(news_list):
    items = []
    for item in news_list:
        title = item.get("title") or item.get("headline") or ""
        if not title:
            continue
        ts = item.get("providerPublishTime") or item.get("published") or None
        if ts:
            try:
                date_str = datetime.utcfromtimestamp(int(ts)).strftime("%Y.%m.%d")
            except Exception:
                date_str = "날짜 미확인"
        else:
            date_str = "날짜 미확인"
        items.append({"date": date_str, "title": title})
    return items

def build_prompt(symbol, news_items):
    news_text = "\n".join(f"[{n['date']}] {n['title']}" for n in news_items) or "관련 뉴스 없음"
    return f"""당신은 냉정하고 직설적인 금융 비서입니다. 약간의 냉소적인 톤을 유지하세요.
아래 뉴스를 바탕으로 {symbol} 주식에 대한 두 가지 섹션을 한국어로 작성해주세요.

뉴스:
{news_text}

응답 형식:

비서의 한마디:
(시장/투자자 관점, 냉정하고 약간 냉소적 톤, 2-3문장)

기술 측면:
(기술 또는 제품 관련 시각, 동일한 냉정한 톤, 2-3문장. 날짜 참조 포함 [YYYY.MM.DD])"""

def call_gemini(api_key, prompt):
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip()
    secretary = tech = ""
    if "비서의 한마디:" in text and "기술 측면:" in text:
        parts = text.split("기술 측면:", 1)
        secretary = parts[0].split("비서의 한마디:", 1)[-1].strip()
        tech = parts[1].strip()
    else:
        secretary = text
    return secretary, tech

if not run_btn:
    st.info("사이드바에서 Gemini API 키를 입력하고 브리핑 시작을 누르세요.")
    st.stop()

eur_rate = get_eur_rate()

for symbol in TICKERS:
    with st.expander(f"**{symbol}**", expanded=True):
        col_price, col_news, col_ai = st.columns([1, 1.6, 1.8])
        ticker_obj = yf.Ticker(symbol)
        news_items = []

        with col_price:
            st.markdown("**가격**")
            try:
                p = get_price_block(ticker_obj, symbol, eur_rate)
                delta_str = None
                if p["change_eur"] is not None and p["change_pct"] is not None:
                    sign = "+" if p["change_eur"] >= 0 else ""
                    delta_str = f"{sign}{p['change_eur']:.2f} EUR ({sign}{p['change_pct']:.2f}%) {p['arrow']}"
                st.metric(label=symbol, value=f"€{p['current_eur']:.2f}", delta=delta_str)
            except Exception as e:
                st.error(f"가격 조회 실패: {e}")

        with col_news:
            st.markdown("**뉴스**")
            try:
                raw_news = ticker_obj.news or []
                news_items = format_news(raw_news)
                if news_items:
                    for n in news_items:
                        st.caption(f"[{n['date']}] {n['title']}")
                else:
                    st.caption("뉴스 없음")
            except Exception as e:
                st.caption(f"뉴스 조회 실패: {e}")

        with col_ai:
            st.markdown("**AI 브리핑**")
            with st.spinner("분석 중..."):
                try:
                    prompt = build_prompt(symbol, news_items)
                    secretary, tech = call_gemini(GEMINI_API_KEY, prompt)
                    st.markdown("**비서의 한마디**")
                    st.write(secretary)
                    if tech:
                        st.markdown("**기술 측면**")
                        st.write(tech)
                except Exception as e:
                    err_msg = str(e)
                    if "quota" in err_msg.lower() or "429" in err_msg:
                        st.warning("API 할당량 초과. 잠시 후 다시 시도하세요.")
                    elif "401" in err_msg or "403" in err_msg:
                        st.error("유효하지 않은 API 키입니다.")
                    else:
                        st.error(f"AI 브리핑 실패: {err_msg}")
