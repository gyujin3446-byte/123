import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import FinanceDataReader as fdr
import datetime
import re

# 스마트폰 화면에 맞게 페이지 설정
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

# [1] 타이틀 설정
st.title("📱 모바일 주식 분석기 프로")
st.caption("스마트폰 최적화 / 저용량 웹 앱 버전")

# 한국거래소(KRX) 종목 목록 로드 (캐싱 처리로 속도 최적화)
@st.cache_data
def load_krx_list():
    try:
        return fdr.StockListing('KRX')
    except:
        return pd.DataFrame()

krx_list = load_krx_list()

# [2] 재무제표 항목 한글 매핑 사전
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

# [3] 티커 변환 함수
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
        res = krx_list[krx_list['Name'] == name_or_code]
        if not res.empty:
            code = res['Code'].values[0]
            mkt = str(res['Market'].values[0])
            return f"{code}.KS" if 'KOSPI' in mkt else f"{code}.KQ"
    return None

# [4] UI 입력부
user_input = st.text_input("🔍 종목 이름 또는 코드 입력", value="삼성전자")
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
                # 주가 데이터 로드
                end_date = datetime.date.today()
                start_date = end_date - datetime.timedelta(days=days)
                df = fdr.DataReader(fdr_ticker, start=start_date, end=end_date)
                
                if df.empty:
                    st.error("주가 데이터를 불러오지 못했습니다.")
                else:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                        
                    # 보조지표 계산
                    df.ta.sma(length=8, append=True)
                    df.ta.sma(length=20, append=True)
                    df.ta.rsi(length=14, append=True)
                    df.dropna(inplace=True)
                    
                    current_price = df['Close'].iloc[-1]
                    ma20_val = df['SMA_20'].iloc[-1]
                    rsi_val = df['RSI_14'].iloc[-1]
                    
                    # 재무 정보 가져오기
                    try:
                        stock_info = yf.Ticker(yf_ticker)
                        info = stock_info.info
                        per_val = info.get('forwardPE') or info.get('trailingPE') or '정보 없음'
                        pbr_val = info.get('priceToBook') or '정보 없음'
                    except:
                        per_val, pbr_val = '정보 없음', '정보 없음'
                        
                    # 투자 의견 알고리즘
                    score = 0
                    if current_price > ma20_val: score += 1
                    else: score -= 1
                    if rsi_val <= 40: score += 1
                    elif rsi_val >= 70: score -= 1
                    if isinstance(per_val, (int, float)) and 0 < per_val <= 15: score += 1
                    elif isinstance(per_val, (int, float)) and per_val >= 30: score -= 1
                    if isinstance(pbr_val, (int, float)) and 0 < pbr_val <= 1.2: score += 1
                    elif isinstance(pbr_val, (int, float)) and pbr_val >= 2.0: score -= 1
                    
                    if score >= 3: op_text, op_status = "🟢 적극 매수", "success"
                    elif score >= 1: op_text, op_status = "🟡 매수 (분할 접근)", "warning"
                    elif score == 0: op_text, op_status = "⚪ 관망 (방향성 없음)", "info"
                    elif score <= -2: op_text, op_status = "🔴 적극 매도 (과열/하락)", "error"
                    else: op_text, op_status = "🟠 비중 축소 (보수적 접근)", "error"
                    
                    # 결과 출력 (모바일 대시보드 형태)
                    st.subheader("📊 주요 정량 지표 요약")
                    unit = "원" if fdr_ticker.isdigit() else "$"
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="현재 종가", value=f"{current_price:,.0f} {unit}" if unit=="원" else f"{unit}{current_price:,.2f}")
                        st.metric(label="PER", value=f"{per_val:.2f}" if isinstance(per_val, float) else str(per_val))
                    with col2:
                        st.metric(label="PBR", value=f"{pbr_val:.2f}" if isinstance(pbr_val, float) else str(pbr_val))
                        st.metric(label="RSI (14)", value=f"{rsi_val:.1f}")
                        
                    if op_status == "success": st.success(f"💡 AI 투자 의견: {op_text}")
                    elif op_status == "warning": st.warning(f"💡 AI 투자 의견: {op_text}")
                    elif op_status == "info": st.info(f"💡 AI 투자 의견: {op_text}")
                    else: st.error(f"💡 AI 투자 의견: {op_text}")
                    
                    # 차트 시각화
                    st.subheader("📈 주가 및 보조지표 차트")
                    chart_data = df[['Close', 'SMA_8', 'SMA_20']]
                    st.line_chart(chart_data)
                    
                    # [수정된 부분] RSI 차트에 30, 70 기준선 표시선 레이어 추가
                    st.caption("RSI 지수 추이 (붉은선: 매도과열 70 / 푸른선: 매수침체 30)")
                    df['매수선(30)'] = 30
                    df['매도선(70)'] = 70
                    
                    # RSI선과 기준선들을 하나의 차트에 묶어서 플로팅
                    rsi_chart_data = df[['RSI_14', '매수선(30)', '매도선(70)']]
                    st.line_chart(rsi_chart_data)
                    
                    # 상세 재무제표 섹션
                    with st.expander("📊 한글 상세 재무제표 보기"):
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
                                st.caption("* 국내 종목 단위: 억 원 / 해외 종목 단위: 해당 시장 기본 통화")
                        except Exception as fe:
                            st.write("재무제표를 불러오는 중 오류가 발생했습니다.")
                            
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")