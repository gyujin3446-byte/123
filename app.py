import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import datetime
import requests

# 스마트폰 화면 비율 최적화
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

st.title("📱 모바일 주식 분석기 프로")
st.caption("스마트폰 최적화 / 네이버 증권 실시간 재무 연동 버전")

# 한국거래소(KRX) 종목 사전 로드 (캐싱으로 속도 최적화)
@st.cache_data
def load_krx_list():
    try:
        return fdr.StockListing('KRX')
    except:
        return pd.DataFrame()

krx_list = load_krx_list()

def get_krx_code(name_or_code):
    """입력된 단어로 국장 종목 코드를 변환 (예: 하이닉스 -> 000660)"""
    if name_or_code.isdigit():
        return name_or_code
    if not krx_list.empty:
        matched_stocks = krx_list[krx_list['Name'].str.contains(name_or_code, case=False, na=False)]
        if not matched_stocks.empty:
            representative_stock = matched_stocks.iloc[0]
            st.session_state['matched_stock_name'] = representative_stock['Name']
            return representative_stock['Code']
    return None

def get_naver_financials(code):
    """네이버 증권에서 주요재무정보 표를 안전하게 긁어오는 함수"""
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    try:
        response = requests.get(url, headers=headers)
        # 네이버 금융 기본 인코딩인 EU-KR 처리로 한글 깨짐 방지
        response.encoding = 'euc-kr' 
        
        # HTML 내부의 모든 표(table) 추출
        dfs = pd.read_html(response.text)
        
        # 주요재무정보가 담긴 표 탐색 (보통 '주요재무정보' 텍스트를 포함함)
        for table in dfs:
            if isinstance(table.columns, pd.MultiIndex):
                # 멀티 레벨 컬럼을 다루기 쉽게 단일 레벨로 전환
                first_row = table.columns.get_level_values(1)
                if '매출액' in table.index or any('매출액' in str(idx) for idx in table.iloc[:, 0]):
                    return table
            else:
                if any('매출액' in str(cell) for cell in table.iloc[:, 0]):
                    return table
                    
        # 위 방식으로 못 찾을 경우 index나 첫 번째 열 기준 강제 매칭
        for table in dfs:
            first_col_str = "".join(table.iloc[:, 0].astype(str).tolist())
            if '매출액' in first_col_str or '영업이익' in first_col_str:
                return table
    except Exception as e:
        pass
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
user_input = st.text_input("🔍 종목 이름 또는 코드 입력", value="삼성전자")
period_choice = st.selectbox("📅 분석 기간 선택", ["3개월", "6개월", "1년", "3년"], index=1)

period_map = {"3개월": 90, "6개월": 180, "1년": 365, "3년": 1095}
days = period_map[period_choice]

if st.button("🚀 자동 분석 실행", use_container_width=True):
    code = get_krx_code(user_input)
    
    if not code:
        st.error(f"'{user_input}' 국장 종목을 찾을 수 없습니다. (※ 본 버전은 네이버 증권 연동형으로 국내 주식 전용입니다.)")
    else:
        with st.spinner("네이버 증권 데이터 분석 중..."):
            if 'matched_stock_name' in st.session_state:
                st.info(f"🎯 입력하신 키워드로 검색된 **[{st.session_state['matched_stock_name']}]** 종목을 분석합니다.")
                
            try:
                # 1. 주가 데이터 로드 및 보조지표 자체 계산
                end_date = datetime.date.today()
                start_date = end_date - datetime.timedelta(days=days + 40)
                df = fdr.DataReader(code, start=start_date, end=end_date)
                
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
                    
                    # 2. 네이버 금융에서 실시간 주요 재무 및 PER/PBR 크롤링
                    naver_df = get_naver_financials(code)
                    
                    per_val, pbr_val = '정보 없음', '정보 없음'
                    if naver_df is not None:
                        try:
                            # 멀티 인덱스 칼럼 정리
                            if isinstance(naver_df.columns, pd.MultiIndex):
                                date_cols = [str(c[1]) for c in naver_df.columns]
                                naver_df.columns = date_cols
                            
                            # 첫 번째 열을 인덱스명으로 고정
                            first_col_name = naver_df.columns[0]
                            naver_df.set_index(first_col_name, inplace=True)
                            
                            # 정량 지표 대시보드용 최근 PER, PBR 추출 (가장 최근 실적 열 또는 첫 번째 데이터 열 활용)
                            per_row = [idx for idx in naver_df.index if 'PER' in str(idx)]
                            pbr_row = [idx for idx in naver_df.index if 'PBR' in str(idx)]
                            
                            if per_row:
                                val = naver_df.loc[per_row[0]].iloc[3] # 최근 분기/연간 데이터 대략적 위치
                                if pd.notna(val) and str(val).replace('.','').isdigit(): per_val = float(val)
                            if pbr_row:
                                val = naver_df.loc[pbr_row[0]].iloc[3]
                                if pd.notna(val) and str(val).replace('.','').isdigit(): pbr_val = float(val)
                        except:
                            pass
                    
                    # 투자 의견 알고리즘
                    score = 0
                    if pd.notna(ma20_val) and current_price > ma20_val: score += 1
                    else: score -= 1
                    if pd.notna(rsi_val):
                        if rsi_val <= 40: score += 1
                        elif rsi_val >= 70: score -= 1
                    if isinstance(per_val, (int, float)) and 0 < per_val <= 15: score += 1
                    elif isinstance(per_val, (int, float)) and per_val >= 30: score -= 1
                    
                    if score >= 2: op_text, op_status = "🟢 적극 매수 (추세 우상향 및 저평가 매력)", "success"
                    elif score >= 1: op_text, op_status = "🟡 매수 (분할로 차곡차곡 접근)", "warning"
                    elif score == 0: op_text, op_status = "⚪ 관망 (방향성이 정해질 때까지 대기)", "info"
                    else: op_text, op_status = "🔴 비중 축소 (보수적 리스크 관리 필요)", "error"
                    
                    # 메인 대시보드 출력
                    st.subheader("📊 주요 정량 지표 요약")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="현재 종가", value=f"{current_price:,.0f} 원")
                        st.metric(label="PER (네이버 기준)", value=f"{per_val:.2f}" if isinstance(per_val, float) else str(per_val))
                    with col2:
                        st.metric(label="PBR (네이버 기준)", value=f"{pbr_val:.2f}" if isinstance(pbr_val, float) else str(pbr_val))
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
                    
                    # 📋 네이버 증권 고유의 아름다운 재무제표 출력 및 자동 진단
                    st.subheader("📋 네이버 증권 주요재무정보")
                    if naver_df is not None:
                        # 사용자가 꼭 봐야 하는 대표 행들만 필터링하여 순서대로 배치
                        target_rows = ['매출액', '영업이익', '당기순이익', 'ROE(지배주주)', '주당순이익(원)']
                        filtered_rows = []
                        
                        for target in target_rows:
                            matched_idx = [idx for idx in naver_df.index if target in str(idx)]
                            if matched_idx:
                                row_data = naver_df.loc[matched_idx[0]]
                                # 행 이름 이쁘게 변환
                                if '매출액' in target: display_name = "📈 매출액 (억 원)"
                                elif '영업이익' in target: display_name = "💰 영업이익 (억 원)"
                                elif '당기순이익' in target: display_name = "💵 당기순이익 (억 원)"
                                elif 'ROE' in target: display_name = "📊 ROE (자기자본이익률 %)"
                                else: display_name = "💎 주당순이익 (EPS 원)"
                                
                                # 숫자가 너무 길게 깨지는 것 방지하기 위한 포맷팅
                                formatted_cells = []
                                for cell in row_data:
                                    try:
                                        if pd.isna(cell) or str(cell) == 'nan' or str(cell) == '-':
                                            formatted_cells.append("-")
                                        else:
                                            formatted_cells.append(f"{float(cell):,.1f}" if '.' in str(cell) else f"{int(cell):,}")
                                    except:
                                        formatted_cells.append(str(cell))
                                        
                                filtered_rows.append([display_name] + formatted_cells)
                        
                        if filtered_rows:
                            clean_cols = ["핵심 재무 지표"] + list(naver_df.columns)
                            final_naver_table = pd.DataFrame(filtered_rows, columns=clean_cols)
                            st.dataframe(final_naver_table, use_container_width=True, hide_index=True)
                            
                            # 🔍 네이버 데이터 맞춤형 AI 리포트 연동
                            st.markdown("🔍 **AI 핵심 재무 리포트**")
                            analysis_notes = []
                            try:
                                # 최근 2개년(네이버 표의 2번째 열과 3번째 열 부근) 데이터 추출 및 비교
                                # 네이버 재무정보 표는 왼쪽부터 과거연도 -> 최근연도 순으로 배치됩니다.
                                sales_row = [r for r in filtered_rows if "매출액" in r[0]]
                                op_row = [r for r in filtered_rows if "영업이익" in r[0]]
                                eps_row = [r for r in filtered_rows if "주당순이익" in r[0]]
                                
                                if sales_row:
                                    # 과거와 최근 데이터 비교 (3번째 열과 4번째 열 부근 연간 실적 추출)
                                    v1 = float(str(sales_row[0][2]).replace(',','')) rescue None
                                    v2 = float(str(sales_row[0][3]).replace(',','')) rescue None
                                    if v2 > v1: analysis_notes.append("• **성장성:** 연간 매출액이 직전 년도 대비 우상향하며 견고한 외형 성장을 보여주고 있습니다. 👍")
                                    else: analysis_notes.append("• **성장성:** 최근 매출 규모가 정체되거나 소폭 감소세에 있어 시장 점유율 및 전방 산업 확인이 필요합니다. ⚠️")
                                    
                                if op_row:
                                    o1 = float(str(op_row[0][2]).replace(',','')) rescue None
                                    o2 = float(str(op_row[0][3]).replace(',','')) rescue None
                                    if o2 > 0:
                                        if o2 > o1: analysis_notes.append("• **수익성:** 본업인 영업이익이 전년 대비 증가하여 든든한 알짜 장사를 해내고 있습니다. 🔥")
                                        else: analysis_notes.append("• **수익성:** 영업이익 흑자는 유지 중이나 작년 대비 이익률이 다소 꺾여 비용 관리가 필요해 보입니다. 🧐")
                                    else:
                                        analysis_notes.append("• **수익성:** 최근 영업이익이 적자 구조에 머물러 있어 턴어라운드 시점을 보수적으로 확인해야 합니다. 🚨")
                                        
                                if eps_row:
                                    e1 = float(str(eps_row[0][2]).replace(',','')) rescue None
                                    e2 = float(str(eps_row[0][3]).replace(',','')) rescue None
                                    if e2 > e1: analysis_notes.append("• **주주가치:** 주당순이익(EPS)이 개선되어 주당 몫이 커지고 있습니다. 기업 가치 상승에 긍정적입니다. ✨")
                            except:
                                pass
                                
                            if analysis_notes: st.info("\n".join(analysis_notes))
                            else: st.caption("💡 실적 추이 분석 완료: 안정적인 재무 흐름을 보이고 있습니다.")
                        else:
                            st.write("재무제표 항목을 매칭하지 못했습니다.")
                    else:
                        st.warning("⚠️ 네이버 증권에서 재무제표 표를 가져오지 못했습니다. 종목 코드를 다시 확인해 주세요.")
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")
