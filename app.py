import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import datetime

# 스마트폰 화면 비율 최적화
st.set_page_config(page_title="모바일 주식 분석기", page_icon="📱", layout="centered")

st.title("📱 모바일 주식 분석기 프로")
st.caption("스마트폰 최적화 / 5개년 추적 완벽 수정 버전")

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
        st.error(f"'{user_input}' 국장 종목을 찾을 수 없습니다. (※ 국내 주식 전용 버전입니다.)")
    else:
        with st.spinner("증권 데이터 분석 중..."):
            if 'matched_stock_name' in st.session_state:
                st.info(f"🎯 입력하신 키워드로 검색된 **[{st.session_state['matched_stock_name']}]** 종목을 분석합니다.")
                
            try:
                # 1. 주가 데이터 및 보조지표 연산
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
                    
                    # 기본 PER, PBR 메타 정보 획득
                    per_val, pbr_val = '정보 없음', '정보 없음'
                    if not krx_list.empty:
                        target_info = krx_list[krx_list['Code'] == code]
                        if not target_info.empty:
                            stock_meta = target_info.iloc[0]
                            if 'PER' in target_info.columns: per_val = stock_meta['PER']
                            if 'PBR' in target_info.columns: pbr_val = stock_meta['PBR']
                    
                    # 투자 의견 스코어링
                    score = 0
                    if pd.notna(ma20_val) and current_price > ma20_val: score += 1
                    else: score -= 1
                    if pd.notna(rsi_val):
                        if rsi_val <= 40: score += 1
                        elif rsi_val >= 70: score -= 1
                    if isinstance(per_val, (int, float)) and 0 < per_val <= 12: score += 1
                    elif isinstance(per_val, (int, float)) and per_val >= 30: score -= 1
                    
                    if score >= 2: op_text, op_status = "🟢 적극 매수 (추세 우상향 및 저평가 매력)", "success"
                    elif score >= 1: op_text, op_status = "🟡 매수 (분할로 차곡차곡 접근)", "warning"
                    elif score == 0: op_text, op_status = "⚪ 관망 (방향성이 정해질 때까지 대기)", "info"
                    else: op_text, op_status = "🔴 비중 축소 (보수적 리스크 관리 필요)", "error"
                    
                    # 지표 대시보드 출력
                    st.subheader("📊 주요 정량 지표 요약")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="현재 종가", value=f"{current_price:,.0f} 원")
                        st.metric(label="PER (가치 평가)", value=f"{per_val:.2f}" if isinstance(per_val, float) else str(per_val))
                    with col2:
                        st.metric(label="PBR (자산 가치)", value=f"{pbr_val:.2f}" if isinstance(pbr_val, float) else str(pbr_val))
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
                    
                    # 📋 에프앤가이드 정식 데이터 허브를 이용한 5개년 재무 표 빌드
                    st.subheader("📋 핵심 재무제표 (최근 5개년 추이)")
                    
                    fnguide_url = f"https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?gicode=A{code}"
                    
                    try:
                        raw_tables = pd.read_html(fnguide_url)
                        target_table = None
                        
                        for t in raw_tables:
                            first_col_str = "".join(t.iloc[:, 0].astype(str).tolist())
                            if '매출' in first_col_str and '영업이익' in first_col_str:
                                target_table = t
                                break
                                
                        if target_table is not None:
                            target_table.set_index(target_table.columns[0], inplace=True)
                            
                            valid_cols = [c for c in target_table.columns if '20' in str(c) or '전년' in str(c)]
                            valid_cols = valid_cols[:5]
                            
                            display_rows = {
                                '매출액': '📈 매출액 (외형 성장)',
                                '영업이익': '💰 영업이익 (알짜 수익)',
                                '당기순이익': '💵 당기순이익 (최종 이익)',
                                '자산': '🏢 자산총계 (기반 체급)',
                                '부채': '📉 부채총계 (재무 리스크)'
                            }
                            
                            final_rows = []
                            extracted_values = {}
                            
                            for key, display_name in display_rows.items():
                                matched_idx = [idx for idx in target_table.index if key in str(idx).replace(' ', '')]
                                if matched_idx:
                                    row_data = target_table.loc[matched_idx[0]]
                                    if isinstance(row_data, pd.DataFrame):
                                        row_data = row_data.iloc[0]
                                        
                                    subset_vals = row_data[valid_cols].values
                                    extracted_values[key] = subset_vals
                                    
                                    formatted_cells = []
                                    for cell in subset_vals:
                                        try:
                                            if pd.isna(cell) or str(cell) in ['nan', '-', '']:
                                                formatted_cells.append("-")
                                            else:
                                                formatted_cells.append(f"{float(cell):,.1f}억")
                                        except:
                                            formatted_cells.append(str(cell))
                                            
                                    final_rows.append([display_name] + formatted_cells)
                            
                            if final_rows:
                                # 🔥 [버그 원인 제거] col이 무조건 문자열(str)이 되도록 보장하여 sequence item 오류 완벽 차단
                                clean_headers = ["핵심 회계 지표 항목"] + [str(col).split('(')[0] if pd.notna(col) else "데이터" for col in valid_cols]
                                output_df = pd.DataFrame(final_rows, columns=clean_headers)
                                st.dataframe(output_df, use_container_width=True, hide_index=True)
                                
                                # 🔍 한 줄 한 줄 가독성을 극대화한 AI 핵심 재무 진단 리포트
                                st.subheader("🔍 AI 핵심 재무 진단")
                                
                                # 1. 성장 및 추세 진단
                                if current_price > ma20_val:
                                    st.info("📈 **성장 및 추세**\n\n현재 주가가 20일 생명선 위에 안전하게 안착했습니다. 중단기 매수세가 살아있으며, 흐름이 우상향하는 긍정적인 성장 궤도에 진입해 있습니다.")
                                else:
                                    st.warning("⚠️ **성장 및 추세**\n\n현재 주가가 20일 생명선 아래에 위치해 있습니다. 단기 하방 압력이 존재하므로 무리한 진입보다는 주요 지지선 낙폭을 먼저 확인하는 것이 안전합니다.")
                                    
                                # 2. 매출 및 실적 추이 진단
                                if '매출액' in extracted_values and len(extracted_values['매출액']) >= 2:
                                    s_data = extracted_values['매출액']
                                    try:
                                        if float(str(s_data[-1]).replace(',','')) > float(str(s_data[-2]).replace(',','')):
                                            st.success("🔥 **매출 성장세 (외형 성장)**\n\n최근 연간 매출액이 직전 년도 대비 확실하게 증가했습니다. 시장 점유율을 견고하게 넓혀가며 기업의 체급이 건강하게 커지고 있는 아주 긍정적인 신호입니다.")
                                        else:
                                            st.warning("🧐 **매출 성장세 (외형 정체)**\n\n최근 연간 매출 규모가 직전 년도 대비 다소 정체되거나 소폭 감소했습니다. 전방 산업의 수요가 일시적으로 둔화되었을 가능성이 있으니 다음 분기 실적 턴어라운드를 주시하세요.")
                                    except:
                                        pass
                                
                                # 3. 수급 및 RSI 온도계 진단
                                if rsi_val <= 40:
                                    st.success("✨ **수급 상태 (RSI 지수)**\n\nRSI 지수가 40 이하인 과매도(심리적 공포) 영역입니다. 단기 낙폭 과대로 인해 시장에 싼 매물이 나온 상태이므로, 기술적 반등을 노린 분할 매수 접근이 아주 유효합니다.")
                                elif rsi_val >= 65:
                                    st.error("🚨 **수급 상태 (RSI 지수)**\n\nRSI 지수가 65 이상으로 시장의 뜨거운 광기와 흥분이 섞인 과열권에 진입했습니다. 주가가 고점에 다다랐을 확률이 높으니 추격 매수보다는 분할 익절 타이밍을 노리세요.")
                                else:
                                    st.info("⏳ **수급 상태 (RSI 지수)**\n\nRSI 지수가 40~60 사이의 안정적인 밸런스를 유지하고 있습니다. 매수세와 매도세의 균형이 단단하여 급격한 붕괴 위험이 적은 수급 상태입니다.")
                            else:
                                st.write("재무제표의 핵심 지표 항목을 파싱하지 못했습니다.")
                        else:
                            st.warning("⚠️ 해당 종목의 5개년 연간 실적 데이터를 구성하는 중입니다.")
                    except Exception as ex:
                        st.error(f"재무 정보 추출 중 예상치 못한 분석 도구 오류가 발생했습니다: {ex}")
                        
            except Exception as e:
                st.error(f"분석 중 오류가 발생했습니다: {e}")
