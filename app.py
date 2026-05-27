import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
import datetime
import requests
import json
from streamlit.components.v1 import html

# 스마트폰 화면 비율 최적화
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

st.title("📱 글로벌 주식 분석기 프로")
st.caption("스마트폰 최적화 / 영구 히스토리 및 완벽 원터치 버전")

# --- 💾 1. 브라우저 localStorage 연동용 자바스크립트 컴포넌트 ---
if 'search_history' not in st.session_state:
    st.session_state['search_history'] = []

def sync_local_storage():
    js_code = """
    <script>
    const savedHistory = localStorage.getItem('stock_search_history');
    if (savedHistory) {
        window.parent.postMessage({
            type: 'streamlit:set_component_value',
            value: JSON.parse(savedHistory)
        }, '*');
    } else {
        window.parent.postMessage({
            type: 'streamlit:set_component_value',
            value: []
        }, '*');
    }
    
    window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'save_history') {
            localStorage.setItem('stock_search_history', JSON.stringify(e.data.data));
        }
    });
    </script>
    """
    return html(js_code, height=0)

storage_data = sync_local_storage()

# 로컬스토리지 데이터가 안전하게 수신되면 세션에 반영
if storage_data is not None and isinstance(storage_data, list) and len(storage_data) > 0:
    st.session_state['search_history'] = storage_data

# --- 🎯 2. 세션 제어용 상태 정착 및 연동 ---
if 'search_target' not in st.session_state:
    st.session_state['search_target'] = "삼성전자"
if 'search_period' not in st.session_state:
    st.session_state['search_period'] = "6개월"
if 'run_analysis' not in st.session_state:
    st.session_state['run_analysis'] = False

# 한국거래소(KRX) 종목 사전 로드
@st.cache_data
def load_krx_list():
    try:
        return fdr.StockListing('KRX')
    except:
        return pd.DataFrame()

krx_list = load_krx_list()

# 주요 해외 주식 한글 검색 매핑 사전
GLOBAL_SEARCH_MAP = {
    '엔비디아': 'NVDA', '팔란티어': 'PLTR', '애플': 'AAPL', '테슬라': 'TSLA',
    '마이크로소프트': 'MSFT', '마소': 'MSFT', '구글': 'GOOGL', '알파벳': 'GOOGL',
    '아마존': 'AMZN', '메타': 'META', '페이스북': 'META', '넷플릭스': 'NFLX',
    '아이온큐': 'IONQ', '스타벅스': 'SBUX', '코카콜라': 'KO', '아이비엠': 'IBM'
}

def search_global_ticker(keyword):
    keyword_clean = keyword.strip().replace(' ', '')
    if keyword_clean in GLOBAL_SEARCH_MAP:
        ticker = GLOBAL_SEARCH_MAP[keyword_clean]
        return ticker, ticker, "미국시장", keyword
        
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={keyword_clean}&lang=ko-KR"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5).json()
        quotes = res.get('quotes', [])
        if quotes:
            best_match = quotes[0]
            ticker = best_match.get('symbol', '').upper()
            shortname = best_match.get('shortname') or best_match.get('longname') or keyword
            if not ticker or any(ord('가') <= ord(ch) <= ord('힣') for ch in ticker):
                return None, None, None, None
            if ticker.endswith('.KS') or ticker.endswith('.KQ'):
                return ticker.split('.')[0], ticker, "국내시장", shortname
            return ticker, ticker, "미국시장", shortname
    except:
        pass
    return None, None, None, None

def get_stock_info(user_input):
    name_clean = user_input.strip()
    if name_clean.isalpha() and name_clean.isupper():
        return name_clean, name_clean, "미국시장", name_clean
    if name_clean.isdigit():
        if not krx_list.empty:
            res = krx_list[krx_list['Code'] == name_clean]
            if not res.empty:
                name = res['Name'].values[0]
                mkt = str(res['Market'].values[0])
                yf_suffix = f"{name_clean}.KS" if 'KOSPI' in mkt else f"{name_clean}.KQ"
                return name_clean, yf_suffix, "국내시장", name
        return name_clean, f"{name_clean}.KS", "국내시장", name_clean

    if name_clean not in GLOBAL_SEARCH_MAP:
        if not krx_list.empty:
            matched_stocks = krx_list[krx_list['Name'].str.contains(name_clean, case=False, na=False)]
            if not matched_stocks.empty:
                representative_stock = matched_stocks.iloc[0]
                return representative_stock['Code'], f"{representative_stock['Code']}.KS" if 'KOSPI' in str(representative_stock['Market']) else f"{representative_stock['Code']}.KQ", "국내시장", representative_stock['Name']

    g_code, g_yf_ticker, g_market, g_name = search_global_ticker(name_clean)
    if g_yf_ticker:
        return g_code, g_yf_ticker, g_market, g_name
    ticker_upper = name_clean.upper()
    return ticker_upper, ticker_upper, "미국시장", ticker_upper

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

# --- 📜 3. 사이드바 히스토리 타임라인 (상태 주입 및 즉시 실행 보장) ---
st.sidebar.header("📜 나의 검색 히스토리")

if not st.session_state['search_history']:
    st.sidebar.caption("아직 검색한 내역이 없습니다.")
else:
    st.sidebar.caption("💡 아래 항목을 터치하면 즉시 재분석합니다.")
    for idx, item in enumerate(reversed(st.session_state['search_history'])):
        btn_label = f"🔍 {item['name']} ({item['period']}) -> {item['opinion']}"
        # 콜백(on_click) 구조나 복잡한 주소 파라미터를 버리고, 세션 변수를 직관적으로 바꾼 뒤 rerun을 유도
        if st.sidebar.button(btn_label, key=f"hist_{idx}", use_container_width=True):
            st.session_state['search_target'] = item['name']
            st.session_state['search_period'] = item['period']
            st.session_state['run_analysis'] = True
            st.rerun()

# --- 📱 4. 메인 화면 UI 위젯 구성 ---
# 입력 필드의 값 자체를 세션의 타겟 상태와 다이렉트로 결합
user_input = st.text_input("🔍 국내/해외 종목 이름 입력", value=st.session_state['search_target'])

period_options = ["3개월", "6개월", "1년", "3년"]
period_index = period_options.index(st.session_state['search_period']) if st.session_state['search_period'] in period_options else 1
period_choice = st.selectbox("📅 분석 기간 선택", period_options, index=period_index)

period_map = {"3개월": 90, "6개월": 180, "1년": 365, "3년": 1095}
days = period_map[period_choice]

# 메인 검색 버튼 터치 시 상태 활성화
if st.button("🚀 자동 분석 실행", use_container_width=True):
    st.session_state['search_target'] = user_input
    st.session_state['search_period'] = period_choice
    st.session_state['run_analysis'] = True

# --- 📈 5. 진짜 실시간 주가 데이터 분석 실행 영역 (버튼 및 히스토리 원터치 통합) ---
if st.session_state['run_analysis']:
    # 실행 직후 플래그를 꺼서 불필요한 연속 렌더링 방지
    st.session_state['run_analysis'] = False
    
    code, yf_ticker, market_type, real_name = get_stock_info(st.session_state['search_target'])
    
    with st.spinner("🚀 글로벌 증권 데이터 분석 중..."):
        st.info(f"🎯 **[{real_name}]** ({market_type} / 티커: {yf_ticker}) 종목을 실시간 분석합니다.")
            
        try:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=days + 40)
            
            df = fdr.DataReader(code, start=start_date, end=end_date) if market_type == "국내시장" else yf.download(yf_ticker, start=start_date, end=end_date)
                
            if df.empty:
                st.error("주가 데이터를 불러오지 못했습니다.")
            else:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                    
                df['SMA_8'] = df['Close'].rolling(window=8).mean()
                df['SMA_20'] = df['Close'].rolling(window=20).mean()
                df['RSI_14'] = calculate_rsi(df['Close'], period=14)
                
                df = df.iloc[-days:]
                df.dropna(subset=['Close'], inplace=True)
                
                current_price = df['Close'].iloc[-1]
                ma20_val = df['SMA_20'].iloc[-1]
                rsi_val = df['RSI_14'].iloc[-1]
                
                per_val, pbr_val = '정보 없음', '정보 없음'
                if market_type == "국내시장":
                    if not krx_list.empty:
                        target_info = krx_list[krx_list['Code'] == code]
                        if not target_info.empty:
                            stock_meta = target_info.iloc[0]
                            if 'PER' in target_info.columns: per_val = stock_meta['PER']
                            if 'PBR' in target_info.columns: pbr_val = stock_meta['PBR']
                else:
                    try:
                        yf_meta = yf.Ticker(yf_ticker).info
                        per_val = yf_meta.get('forwardPE') or yf_meta.get('trailingPE') or '정보 없음'
                        pbr_val = yf_meta.get('priceToBook') or '정보 없음'
                    except:
                        pass
                
                score = 0
                if pd.notna(ma20_val) and current_price > ma20_val: score += 1
                else: score -= 1
                if pd.notna(rsi_val):
                    if rsi_val <= 40: score += 1
                    elif rsi_val >= 70: score -= 1
                if isinstance(per_val, (int, float)) and 0 < per_val <= 15: score += 1
                elif isinstance(per_val, (int, float)) and per_val >= 35: score -= 1
                
                if score >= 2: op_text = "🟢 적극 매수"
                elif score >= 1: op_text = "🟡 분할 매수"
                elif score == 0: op_text = "⚪ 관망 유지"
                else: op_text = "🔴 비중 축소"
                
                # 중복 확인 후 브라우저 영구 스토리지에 백업 이벤트를 전달
                history_exists = any(h['name'] == real_name and h['period'] == st.session_state['search_period'] for h in st.session_state['search_history'])
                if not history_exists:
                    st.session_state['search_history'].append({
                        'name': real_name,
                        'period': st.session_state['search_period'],
                        'opinion': op_text
                    })
                    html(f"""<script>window.parent.postMessage({{type: 'save_history', data: {json.dumps(st.session_state['search_history'])} }}, '*');</script>""", height=0)
                    st.rerun()
                
                # 대시보드 지표 카드 출력
                st.subheader("📊 주요 정량 지표 요약")
                unit = "원" if market_type == "국내시장" else "$"
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label="현재 종가", value=f"{current_price:,.0f} {unit}" if unit=="원" else f"{unit}{current_price:,.2f}")
                    st.metric(label="PER", value=f"{per_val:.2f}" if isinstance(per_val, float) else str(per_val))
                with col2:
                    st.metric(label="PBR", value=f"{pbr_val:.2f}" if isinstance(pbr_val, float) else str(pbr_val))
                    st.metric(label="RSI 지수", value=f"{rsi_val:.1f}")
                    
                if "🟢" in op_text: st.success(f"💡 종합 투자 의견: {op_text}")
                elif "🟡" in op_text: st.warning(f"💡 종합 투자 의견: {op_text}")
                elif "⚪" in op_text: st.info(f"💡 종합 투자 의견: {op_text}")
                else: st.error(f"💡 종합 투자 의견: {op_text}")
                
                st.subheader("📈 주가 및 이동평균선")
                st.line_chart(df[['Close', 'SMA_8', 'SMA_20']])
                
                df['매수선(30)'] = 30
                df['매도선(70)'] = 70
                st.line_chart(df[['RSI_14', '매수선(30)', '매도선(70)']])
                
                # 📋 핵심 재무제표 표 출력
                st.subheader("📋 핵심 재무제표 요약")
                if market_type == "국내시장":
                    meta = krx_list[krx_list['Code'] == code].iloc[0]
                    def format_amount(val):
                        try:
                            if pd.isna(val) or val == 0: return "-"
                            return f"{float(val)/100000000:,.1f}억"
                        except: return str(val)
                    financial_data = [
                        ["📈 매출액 (외형 성장)", format_amount(meta.get('Sales', 0))],
                        ["💰 영업이익 (알짜 수익)", format_amount(meta.get('OperatingProfit', 0))],
                        ["💵 당기순이익 (최종 이익)", format_amount(meta.get('NetIncome', 0))],
                        ["🏢 자산총계 (기반 체급)", format_amount(meta.get('Assets', 0))],
                        ["📉 부채총계 (재무 리스크)", format_amount(meta.get('Liabilities', 0))]
                    ]
                    fin_df = pd.DataFrame(financial_data, columns=["핵심 재무 지표 항목", "최근 결산 실적 수치"])
                    st.dataframe(fin_df, use_container_width=True, hide_index=True)
                else:
                    try:
                        ticker_obj = yf.Ticker(yf_ticker)
                        stmt = ticker_obj.get_income_stmt()
                        if not stmt.empty:
                            us_mapping = {'Total Revenue': '📈 매출액', 'Operating Income': '💰 영업이익', 'Net Income': '💵 당기순이익'}
                            us_rows = []
                            use_cols = list(stmt.columns[:3])
                            for k, display in us_mapping.items():
                                if k in stmt.index:
                                    raw_vals = stmt.loc[k]
                                    if isinstance(raw_vals, pd.DataFrame): raw_vals = raw_vals.iloc[0]
                                    cells = [f"${v/1000000:,.1f}M" if pd.notna(v) else "-" for v in raw_vals[use_cols].values]
                                    us_rows.append([display] + cells)
                            if us_rows:
                                headers = ["핵심 재무 지표 항목"] + [str(c).split('-')[0].strip() for c in use_cols]
                                st.dataframe(pd.DataFrame(us_rows, columns=headers), use_container_width=True, hide_index=True)
                    except:
                        st.write("해외 재무 정보를 로드하는 중입니다.")
                        
                # 🔍 AI 핵심 재무 진단 리포트
                st.subheader("🔍 AI 핵심 재무 진단")
                if current_price > ma20_val:
                    st.info("📈 **성장 및 추세**\n\n현재 주가가 20일 생명선 위에 안전하게 안착하여 우상향 기조에 있습니다.")
                else:
                    st.warning("⚠️ **성장 및 추세**\n\n현재 주가가 20일 생명선 아래에 위치해 있어 단기 리스크 관리가 필요합니다.")
                if isinstance(per_val, (int, float)) and per_val > 0:
                    if per_val <= 15: st.success(f"🔥 **밸류에이션**\n\n현재 PER이 {per_val:.1f}배 수준으로 기업 벌이 대비 상당한 저평가 구간입니다.")
                    elif per_val >= 30: st.error(f"🚨 **... 밸류에이션**\n\n현재 PER이 {per_val:.1f}배 수준으로 단기 오버슈팅 및 과열 양상을 보입니다.")
                    
        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {e}")
