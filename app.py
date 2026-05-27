import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import yfinance as yf
import datetime
import requests

# 스마트폰 화면 비율 최적화
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

st.title("📱 글로벌 주식 분석기 프로")
st.caption("스마트폰 최적화 / 국내 및 해외주식 100% 한글 검색 지원 버전")

# --- 💾 1. 검색 히스토리 저장소 초기화 ---
if 'search_history' not in st.session_state:
    st.session_state['search_history'] = []

# 한국거래소(KRX) 종목 사전 로드 (캐싱으로 속도 최적화)
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

# --- 📋 2. 모바일 내비게이션 사이드바 (검색 히스토리) ---
st.sidebar.header("📜 나의 검색 히스토리")
if not st.session_state['search_history']:
    st.sidebar.caption("아직 검색한 내역이 없습니다.")
else:
    st.sidebar.caption("💡 아래 항목을 터치하면 즉시 재분석합니다.")
    # 히스토리 리스트 역순출력 (최신 검색이 맨 위로)
    for idx, item in enumerate(reversed(st.session_state['search_history'])):
        # 스마트폰에서 터치하기 편하도록 가로로 긴 버튼 구성
        btn_label = f"🔍 {item['name']} ({item['period']}) -> {item['opinion'].split(' ')[0]}"
        if st.sidebar.button(btn_label, key=f"hist_{len(st.session_state['search_history'])-1-idx}", use_container_width=True):
            # 히스토리 터치 시 입력창과 기간을 강제로 주입하고 페이지 새로고침 효과
            st.session_state['auto_search_input'] = item['name']
            st.session_state['auto_search_period'] = item['period']
            st.rerun()

# --- 📱 3. 메인 화면 UI 구성 ---
# 히스토리 링크 연동을 위한 세션 상태 바인딩
default_input = st.session_state.get('auto_search_input', "삼성전자")
default_period = st.session_state.get('auto_search_period', "6개월")

user_input = st.text_input("🔍 국내/해외 종목 이름 입력", value=default_input)
period_choice = st.selectbox("📅 분석 기간 선택", ["3개월", "6개월", "1년", "3년"], index=["3개월", "6개월", "1년", "3년"].index(default_period))

period_map = {"3개월": 90, "6개월": 180, "1년": 365, "3년": 1095}
days = period_map[period_choice]

# 자동 검색 실행 조건 트리거 (버튼 클릭 혹은 히스토리 터치 연동)
trigger_search = st.button("🚀 자동 분석 실행", use_container_width=True) or ('auto_search_input' in st.session_state)

if trigger_search:
    # 히스토리 자동 검색 트리거 해제 (무한 루프 방지)
    if 'auto_search_input' in st.session_state:
        del st.session_state['auto_search_input']
        del st.session_state['auto_search_period']

    code, yf_ticker, market_type, real_name = get_stock_info(user_input)
    
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
                
                if score >= 2: op_text, op_status = "🟢 적극 매수", "success"
                elif score >= 1: op_text, op_status = "🟡 분할 매수", "warning"
                elif score == 0: op_text, op_status = "⚪ 관망 유지", "info"
                else: op_text, op_status = "🔴 비중 축소", "error"
                
                # 💾 [핵심 로직] 중복 검색 방지하면서 히스토리에 데이터 적재
                history_exists = any(h['name'] == real_name and h['period'] == period_choice for h in st.session_state['search_history'])
                if not history_exists:
                    st.session_state['search_history'].append({
                        'name': real_name,
                        'period': period_choice,
                        'opinion': op_text
                    })
                    st.rerun() # 사이드바 메뉴 실시간 갱신용
                
                # 메인 화면 스코어보딩 출력
                st.subheader("📊 주요 정량 지표 요약")
                unit = "원" if market_type == "국내시장" else "$"
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label="현재 종가", value=f"{current_price:,.0f} {unit}" if unit=="원" else f"{unit}{current_price:,.2f}")
                    st.metric(label="PER", value=f"{per_val:.2f}" if isinstance(per_val, float) else str(per_val))
                with col2:
                    st.metric(label="PBR", value=f"{pbr_val:.2f}" if isinstance(pbr_val, float) else str(pbr_val))
                    st.metric(label="RSI 지수", value=f"{rsi_val:.1f}")
                    
                if op_status == "success": st.success(f"💡 종합 투자 의견: {op_text}")
                elif op_status == "warning": st.warning(f"💡 종합 투자 의견: {op_text}")
                elif op_status == "info": st.info(f"💡 종합 투자 의견: {op_text}")
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
                
                # 1. 성장 및 추세 진단
                if current_price > ma20_val:
                    st.info("📈 **성장 및 추세**\n\n현재 주가가 20일 생명선 위에 안전하게 안착했습니다. 중단기 매수세가 살아있으며, 흐름이 우상향하는 긍정적인 성장 궤도에 진입해 있습니다.")
                else:
                    st.warning("⚠️ **성장 및 추세**\n\n현재 주가가 20일 생명선 아래에 위치해 있습니다. 단기 하방 압력이 존재하므로 무리한 진입보다는 주요 지지선 낙폭을 먼저 확인하는 것이 안전합니다.")
                    
                # 2. 밸류에이션(PER) 진단
                if isinstance(per_val, (int, float)) and per_val > 0:
                    if per_val <= 15:
                        st.success(f"🔥 **밸류에이션 (적정 가치)**\n\n현재 PER이 {per_val:.1f}배 수준입니다. 기업이 벌어들이는 수익력에 비해 주가가 저평가되어 있어 가격 매리트가 뛰어난 구간입니다.")
                    elif per_val >= 30:
                        st.error(f"🚨 **... 가치 평가 (과열 경고)**\n\n현재 PER이 {per_val:.1f}배 수준으로 미래 성장 기대감이 강하게 선반영되어 있습니다. 주가가 다소 무거운 자리이므로 신중한 접근이 필요합니다.")
                    else:
                        st.info(f"🧐 **... 투자 밸류에이션**\n\n현재 PER이 {per_val:.1f}배 수준으로 주가 가치가 정상 범주 안에서 안정적인 가치 평가를 받고 있습니다.")
                
                # 3. 수급 및 RSI 온도계 진단
                if rsi_val <= 40:
                    st.success("✨ **수급 상태 (RSI 지수)**\n\nRSI 지수가 40 이하인 과매도(심리적 공포) 영역입니다. 기술적 반등을 노린 분할 매수 접근이 아주 유효합니다.")
                elif rsi_val >= 65:
                    st.error("🚨 **수급 상태 (RSI 지수)**\n\nRSI 지수가 65 이상으로 시장의 과열권에 진입했습니다. 무리한 추격 매수보다는 분할 익절 타이밍을 노리세요.")
                else:
                    st.info("⏳ **수급 상태 (RSI 지수)**\n\nRSI 지수가 40~60 사이의 안정적인 수급 상태입니다. 매수세와 매도세의 균형이 단단하여 급격한 붕괴 위험이 적습니다.")
                    
        except Exception as e:
            st.error(f"분석 중 오류가 발생했습니다: {e}")
