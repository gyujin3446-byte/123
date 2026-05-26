import streamlit as st
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr
import datetime
import re

# 스마트폰 화면 비율 최적화
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

st.title("📱 모바일 주식 분석기 프로")
st.caption("스마트폰 최적화 / 핵심 지표 압축 버전")

# 한국거래소(KRX) 종목 사전 로드 (캐싱으로 속도 최적화)
@st.cache_data
def load_krx_list():
    try:
        return fdr.StockListing('KRX')
    except:
        return pd.DataFrame()

krx_list = load_krx_list()

# ★ [수정] 무조건 봐야 하는 핵심 5가지 지표만 남기고 다이어트 ★
FINANCIAL_MAP = {
    'Total Revenue': '📈 매출액 (외형 성장)',
    'Operating Income': '💰 영업이익 (알짜 수익)',
    'Net Income': '💵 당기순이익 (최종 이익)',
    'EBITDA': '🏭 EBITDA (현금창출력)',
    'Diluted EPS': '💎 주당순이익 (EPS)'
}

def get_yf_ticker(name_or_code):
    if name_or_code.replace('.', '').encode().isalpha() or '.KS' in name_or_code or '.KQ' in name_or_code:
        return name_or_code.upper()
    if name_or_code.isdigit():
        if not krx_list.empty:
            res = krx_list[krx_list['Code'] == name_or_code]
            if not res.empty:
                mkt = str(res['Market'].values[0])
                return f"{name_or_code}.KS" if 'KOSPI' in mkt else f"{name_or_code}.KQ"
        return f"{name_or_code}.KS"

    if not krx_list.empty:
        matched_stocks = krx_list[krx_list['Name'].str.contains(name_or_code, case=False, na=False)]
        if not matched_stocks.empty:
            representative_stock = matched_stocks.iloc[0]
            code = representative_stock['Code']
            mkt = str(representative_stock['Market'])
            st.session_state['matched_stock_name'] = representative_stock['Name']
            return f"{code}.KS" if 'KOSPI' in mkt else f"{code}.KQ"
    return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=period - 1, adjust=False).mean()
    ema_down = down.ewm(com=period - 1, adjust=False).mean()
    rs = ema_up / ema_down
    return 100 - (100 / (1 + rs))

# 모바일 터치 UI 구성
user_input = st.text_input("🔍 종목 이름 또는 티커 입력", value="삼성전자")
period_choice = st.selectbox("📅 분석 기간 선택", ["3개월", "6개월", "1년", "3년"], index=1)

period_map = {"3개월": 90, "6개월": 180, "1년": 365, "3년": 1095}
days = period_map[period_choice]

if st.button("🚀 자동 분석 실행", use_container_width=True):
    yf_ticker = get_yf_ticker(user_input)
    
    if not yf_ticker:
        st.error(f"'{user_input}' 종목을 찾을 수 없습니다.")
    else:
        fdr_ticker = yf_ticker.replace('.KS', '').replace('.KQ', '')
        
        with st.spinner("데이터 분석 중..."):
            if 'matched_stock_name' in st.session_state:
                st.info(f"🎯 입력하신 키워드로 검색된 **[{st.session_state['matched_stock_name']}]** 종목을 분석합니다.")
                
            try:
                end_date = datetime.date.today()
                start_date = end_date - datetime.timedelta(days=days + 40)
                df = fdr.DataReader(fdr_ticker, start=start_date, end=end_date)
                
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
                    
                    try:
                        stock_info = yf.Ticker(yf_ticker)
                        info = stock_info.info
                        per_val = info.get('forwardPE') or info.get('trailingPE') or '정보 없음'
                        pbr_val = info.get('priceToBook') or '정보 없음'
                    except:
                        per_val, pbr_val = '정보 없음', '정보 없음'
                        
                    score = 0
                    if pd.notna(ma20_val):
                        if current_price > ma20_val: score += 1
                        else: score -= 1
                    if pd.notna(rsi_val):
                        if rsi_val <= 40: score += 1
                        elif rsi_val >= 70: score -= 1
                    if isinstance(per_val, (int, float)) and 0 < per_val <= 15: score += 1
                    elif isinstance(per_val, (int, float)) and per_val >= 30: score -= 1
                    if isinstance(pbr_val, (int, float)) and 0 < pbr_val <= 1.2: score += 1
                    elif isinstance(pbr_val, (int, float)) and pbr_val >= 2.0: score -= 1
                    
                    if score >= 3: op_text, op_status = "🟢 적극 매수 (강한 추세 및 저평가)", "success"
                    elif score >= 1: op_text, op_status = "🟡 매수 (분할 접근 유효)", "warning"
                    elif score == 0: op_text, op_status = "⚪ 관망 (방향성 탐색 구간)", "info"
                    elif score <= -2: op_text, op_status = "🔴 적극 매도 (추세 이탈 및 고평가)", "error"
                    else: op_text, op_status = "🟠 비중 축소 (보수적 리스크 관리)", "error"
                    
                    st.subheader("📊 주요 정량 지표 요약")
                    unit = "원" if fdr_ticker.isdigit() else "$"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="현재 종가", value=f"{current_price:,.0f} {unit}" if unit=="원" else f"{unit}{current_price:,.2f}")
                        st.metric(label="PER (주가수익비율)", value=f"{per_val:.2f}" if isinstance(per_val, float) else str(per_val))
                    with col2:
                        st.metric(label="PBR (주가자산비율)", value=f"{pbr_val:.2f}" if isinstance(pbr_val, float) else str(pbr_val))
                        st.metric(label="RSI 지수", value=f"{rsi_val:.1f}" if pd.notna(rsi_val) else "계산 중")
                        
                    if op_status == "success": st.success(f"💡 종합 투자 의견: {op_text}")
                    elif op_status == "warning": st.warning(f"💡 종합 투자 의견: {op_text}")
                    elif op_status == "info": st.info(f"💡 종합 투자 의견: {op_text}")
                    else: st.error(f"💡 종합 투자 의견: {op_text}")
                    
                    st.subheader("📈 주가 및 이동평균선")
                    st.line_chart(df[['Close', 'SMA_8', 'SMA_20']])
                    
                    st.caption("🧭 RSI 과열/침체 지수 추이 (가이드선: 30, 70)")
                    df['매수선(30)'] = 30
                    df['매도선(70)'] = 70
                    st.line_chart(df[['RSI_14', '매수선(30)', '매도선(70)']])
                    
                    # ★ [수정] 5대 핵심 지표만 필터링하여 가독성 높게 표 구성 ★
                    st.subheader("📋 핵심 재무제표 (최근 4개년)")
                    try:
                        fs = stock_info.get_income_stmt()
                        if fs.empty:
                            st.write("제공되는 연간 재무제표 데이터가 없습니다.")
                        else:
                            formatted_fs = []
                            # FINANCIAL_MAP에 지정된 5가지 핵심 항목만 순서대로 골라냅니다.
                            for target_idx, kor_name in FINANCIAL_MAP.items():
                                if target_idx in fs.index:
                                    row = fs.loc[target_idx]
                                    if '.KS' in yf_ticker or '.KQ' in yf_ticker:
                                        # 국내 주식: 억 원 단위 변환 (단, EPS는 원 단위 유지)
                                        if 'EPS' in kor_name:
                                            formatted_row = [f"{val:,.0f}원" if pd.notnull(val) else "-" for val in row]
                                        else:
                                            formatted_row = [f"{val/100000000:,.1f}억" if pd.notnull(val) else "-" for val in row]
                                    else:
                                        # 해외 주식: 달러 수치 그대로 포맷팅 (단, EPS는 소수점 표시)
                                        if 'EPS' in kor_name:
                                            formatted_row = [f"${val:,.2f}" if pd.notnull(val) else "-" for val in row]
                                        else:
                                            formatted_row = [f"${val:,.0f}" if pd.notnull(val) else "-" for val in row]
                                    formatted_fs.append([kor_name] + formatted_row)
                            
                            if formatted_fs:
                                cols = ["핵심 회계 지표"] + list(fs.columns.map(lambda x: x.strftime('%Y-%m')))
                                result_fs_df = pd.DataFrame(formatted_fs, columns=cols)
                                
                                # 접어두지 않고 화면에 바로 시원하게 보여주기
                                st.dataframe(result_fs_df, use_container_width=True, hide_index=True)
                                st.caption("💡 매출액과 영업이익이 매년 우상향하는지 확인하는 것이 핵심입니다.")
                            else:
                                st.write("핵심 재무 항목을 매칭하지 못했습니다.")
                    except Exception as fe:
                        st.write("재무제표를 불러오는 중 오류가 발생했습니다.")
                            
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")
