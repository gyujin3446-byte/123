import streamlit as st
import yfinance as yf
import pandas as pd
import FinanceDataReader as fdr
import datetime
import re

# 스마트폰 화면 비율 최적화
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

st.title("📱 모바일 주식 분석기 프로")
st.caption("스마트폰 최적화 / 저용량 상시 접속 웹 버전")

# 한국거래소(KRX) 종목 사전 로드 (캐싱으로 속도 최적화)
@st.cache_data
def load_krx_list():
    try:
        return fdr.StockListing('KRX')
    except:
        return pd.DataFrame()

krx_list = load_krx_list()

# 재무제표 항목 한글 매핑 사전
FINANCIAL_MAP = {
    'Total Revenue': '매출액 (총수익)',
    'Operating Revenue': '영업수익',
    'Cost Of Revenue': '매출원가',
    'ReconciledCostOfRevenue': '조정 매출원가',
    'Gross Profit': '매출총이익',
    'Operating Expense': '영업비용',
    'TotalExpenses': '총 비용',
    'Research And Development': '연구개발비 (R&D)',
    'Selling General And Administrative': '판매비와 관리비 (판관비)',
    'Operating Income': '영업이익',
    'TotalOperatingIncomeAsReported': '보고된 총 영업이익',
    'EBITDA': 'EBITDA (상각전 영업이익)',
    'NormalizedEBITDA': '정규화 EBITDA',
    'EBIT': 'EBIT (이자/세금 차감전 이익)',
    'NetInterestIncome': '순이자수익',
    'Interest Expense': '이자비용',
    'InterestExpense': '이자비용',
    'Interest Income': '이자수익',
    'InterestIncome': '이자수익',
    'Pretax Income': '법인세차감전순이익',
    'Tax Provision': '법인세비용',
    'TaxEffectOfUnusualItems': '비경상항목 법인세효과',
    'TaxRateForCalcs': '계산용 법인세율',
    'Net Income': '당기순이익',
    'NetIncome': '당기순이익',
    'NetIncomeCommonStockholders': '보통주 지배주주 당기순이익',
    'NetIncomeFromContinuingOperationNetMinorityInterest': '계속영업순이익 (지배주주)',
    'NetIncomeFromContinuingAndDiscontinuedOperation': '계속/중단영업 당기순이익',
    'NormalizedIncome': '정규화 당기순이익',
    'BasicAverageShares': '가중평균주식수 (기본)',
    'DilutedAverageShares': '가중평균주식수 (희석)',
    'Basic EPS': '기본 주당순이익 (EPS)',
    'BasicEPS': '기본 주당순이익 (EPS)',
    'Diluted EPS': '희석 주당순이익 (EPS)',
    'DilutedEPS': '희석 주당순이익 (EPS)'
}

def get_yf_ticker(name_or_code):
    # 1. 영문 티커(미국주식 등)이거나 이미 시장 접미사가 붙은 경우
    if name_or_code.replace('.', '').encode().isalpha() or '.KS' in name_or_code or '.KQ' in name_or_code:
        return name_or_code.upper()
        
    # 2. 숫자로만 된 종목 코드인 경우 (예: 005930)
    if name_or_code.isdigit():
        if not krx_list.empty:
            res = krx_list[krx_list['Code'] == name_or_code]
            if not res.empty:
                mkt = str(res['Market'].values[0])
                return f"{name_or_code}.KS" if 'KOSPI' in mkt else f"{name_or_code}.KQ"
        return f"{name_or_code}.KS"

    # 3. ★ 핵심: 글자 포함(부분 일치) 자동 검색 기능 ★
    if not krx_list.empty:
        # 사용자가 입력한 글자가 종목명에 '포함'되어 있는지 검사 (예: '하이닉스' -> 'SK하이닉스' 포함됨)
        # 단, 네이버/다움 등 유사 종목 리스트가 많을 수 있으므로 시가총액/순서상 가장 상위에 있는 대표 종목을 선택
        matched_stocks = krx_list[krx_list['Name'].str.contains(name_or_code, case=False, na=False)]
        
        if not matched_stocks.empty:
            # 매칭된 종목 중 첫 번째(가장 대표 주식)를 자동 선택
            representative_stock = matched_stocks.iloc[0]
            code = representative_stock['Code']
            mkt = str(representative_stock['Market'])
            
            # 스트림릿 화면에 어떤 종목으로 자동 매칭되었는지 친절하게 알려주기 위해 세션 변수에 임시 저장
            st.session_state['matched_stock_name'] = representative_stock['Name']
            
            return f"{code}.KS" if 'KOSPI' in mkt else f"{code}.KQ"
            
    return None

# 수동 RSI 계산 함수 (pandas_ta 없이 자체 계산)
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
            try:
                # 8일선, 20일선 계산을 위해 시작일을 조금 더 넉넉하게 당김
                end_date = datetime.date.today()
                start_date = end_date - datetime.timedelta(days=days + 40)
                df = fdr.DataReader(fdr_ticker, start=start_date, end=end_date)
                
                if df.empty:
                    st.error("주가 데이터를 불러오지 못했습니다.")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                        
                    # 순수 파이썬 코드로 보조지표 직접 연산
                    df['SMA_8'] = df['Close'].rolling(window=8).mean()
                    df['SMA_20'] = df['Close'].rolling(window=20).mean()
                    df['RSI_14'] = calculate_rsi(df['Close'], period=14)
                    
                    # 사용자가 요청한 기간만 잘라내기
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
                        
                    # 투자 의견 스코어링 알고리즘
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
                    
                    # 대시보드 출력
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
                    
                    # 반응형 모바일 차트 시각화
                    st.subheader("📈 주가 및 이동평균선")
                    st.line_chart(df[['Close', 'SMA_8', 'SMA_20']])
                    
                    st.caption("🧭 RSI 과열/침체 지수 추이 (가이드선: 30, 70)")
                    df['매수선(30)'] = 30
                    df['매도선(70)'] = 70
                    st.line_chart(df[['RSI_14', '매수선(30)', '매도선(70)']])
                    
                    # 상세 재무제표 
                    with st.expander("📂 한글 상세 재무제표 펼치기"):
                        try:
                            fs = stock_info.get_income_stmt()
                            if fs.empty:
                                st.write("제공되는 연간 재무제표 데이터가 없습니다.")
                            else:
                                formatted_fs = []
                                for idx, row in fs.iterrows():
                                    kor_name = FINANCIAL_MAP.get(idx, idx)
                                    if not idx in FINANCIAL_MAP:
                                        kor_name = re.sub(r'(?<!^)(?=[A-Z])', ' ', str(idx))
                                    
                                    if '.KS' in yf_ticker or '.KQ' in yf_ticker:
                                        formatted_row = [f"{val/100000000:,.1f}억" if pd.notnull(val) else "-" for val in row]
                                    else:
                                        formatted_row = [f"{val:,.0f}" if pd.notnull(val) else "-" for val in row]
                                    formatted_fs.append([kor_name] + formatted_row)
                                
                                cols = ["회계 지표 항목"] + list(fs.columns.map(lambda x: x.strftime('%Y-%m')))
                                result_fs_df = pd.DataFrame(formatted_fs, columns=cols)
                                st.dataframe(result_fs_df, use_container_width=True)
                        except Exception as fe:
                            st.write("재무제표를 불러오는 중 오류가 발생했습니다.")
                            
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")
