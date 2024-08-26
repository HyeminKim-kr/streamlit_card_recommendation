import streamlit as st
import pandas as pd
from io import BytesIO
from elastic_api import search_index, search_index2
import re

# 카드 ID를 사용하여 이미지 URL을 생성하는 함수
def extract_image_url(card_id):
    return f"https://woori-fisa-bucket.s3.ap-northeast-2.amazonaws.com/index_img/bcc_{card_id:03d}.png"

# 연회비 필터링을 위한 함수 추가
def clean_and_convert_cost(cost_str):
    try:
        numeric_str = ''.join(char for char in cost_str if char.isdigit() or char == '.')
        return float(numeric_str)
    except ValueError:
        return 0

def filter_by_yearly_fee(df, option):
    if 'abroad_year_cost' in df.columns:
        df['abroad_year_cost'] = df['abroad_year_cost'].apply(clean_and_convert_cost)
        
        if option == "전체 보기":
            return df
        elif option == "0만원 이상 1만원 미만":
            return df[(df['abroad_year_cost'] >= 0) & (df['abroad_year_cost'] < 10000)]
        elif option == "1만원 이상 3만원 미만":
            return df[(df['abroad_year_cost'] >= 10000) & (df['abroad_year_cost'] < 30000)]
        elif option == "3만원 이상 5만원 미만":
            return df[(df['abroad_year_cost'] >= 30000) & (df['abroad_year_cost'] < 50000)]
        elif option == "5만원 이상":
            return df[df['abroad_year_cost'] >= 50000]
    return df

st.title("선택하신 조건에 부합하는 카드를 보여드립니다")
index_name = "card_info"
field_name = "card_name"

st.sidebar.header("조회하고 싶은 카드조건을 입력하세요")
match_name = st.sidebar.text_input('카드 이름', value="").strip()

# 연회비 필터링 옵션 추가
yearly_fee_option = st.sidebar.radio(
    "해외 연회비 범위 선택",
    ("전체 보기", "0만원 이상 1만원 미만", "1만원 이상 3만원 미만", "3만원 이상 5만원 미만", "5만원 이상")
)

# 조회 결과 저장을 위한 함수
@st.cache_data
def fetch_data(index_name, field_name, match_name):
    if match_name == "":
        # 빈칸일 경우 전체 데이터를 가져오도록 변경
        result = search_index2(index_name)  # Using "*" to get all records
    else:
        # 띄어쓰기를 제거하여 검색하도록 처리
        normalized_match_name = re.sub(r'\s+', '', match_name)
        result = search_index(index_name, field_name, normalized_match_name)
    
    hits = result.to_dict()["hits"]["hits"]
    if hits:
        return pd.DataFrame([entry["_source"] for entry in hits])
    return pd.DataFrame()


# 조회 결과에서 카테고리 클래스를 추출하는 함수
def extract_categories(df):
    categories = set()
    if 'category' in df.columns:
        for categories_list in df['category'].dropna():
            for cat in categories_list:
                if 'class' in cat:
                    categories.add(cat['class'])
    return sorted(categories)

# 데이터 조회 및 필터링
df = fetch_data(index_name, field_name, match_name)

# No condition to display an error message, just process and display the dataframe
if not df.empty:
    categories = extract_categories(df)
    selected_classes = st.sidebar.multiselect('혜택', options=['All'] + categories, default=['All'])

    if selected_classes != ['All']:
        df = df[df['category'].apply(lambda cats: any(cat.get('class') in selected_classes for cat in cats))]

    # 연회비 필터링 적용
    df = filter_by_yearly_fee(df, yearly_fee_option)
    
    if 'id' in df.columns:
        df['card_image_url'] = df['id'].apply(extract_image_url)

    st.dataframe(df)
    
    # 각 카드 정보를 표시
    for _, row in df.iterrows():
        st.subheader(row.get('card_name', 'No Name'))

        # 이미지와 링크 출력
        card_link = row.get('card_link', '#')
        card_image_url = row.get('card_image_url', '')

        st.markdown(f'<a href="{card_link}" target="_blank"><img src="{card_image_url}" width="200"/></a>', unsafe_allow_html=True)
        
        # 카테고리 정보 출력
        category_info = "\n".join([f"  - {cat.get('class', 'No Class')}: {cat.get('benefit', 'No Benefit')}" for cat in row.get('category', [])])
        st.write("  - 카테고리:")
        st.write(category_info)
        
        st.write(f"정보:")
        st.write(f"  - 국내 연회비: {row.get('domestic_year_cost', 'No Cost')}")
        st.write(f"  - 해외 연회비: {row.get('abroad_year_cost', 'No Cost')}")
        st.write(f"  - 전월실적: {row.get('previous_month_performance', 'No Performance')}")
        
        # 유의사항 표시
        with st.expander("유의사항을 참고하세요!"):
            categories = row.get('category', [])
            for cat in categories:
                st.markdown(f"**{cat.get('class', 'No Class')}**: {cat.get('benefit', 'No Benefit')}", unsafe_allow_html=True)
                condition = cat.get('condition', None)
                if condition:
                    st.markdown(f"**조건**: {condition}", unsafe_allow_html=True)

    # CSV와 엑셀 다운로드 버튼 제공
    csv_data = df.to_csv(index=False)
    excel_data = BytesIO()
    df.to_excel(excel_data, index=False)
    excel_data.seek(0)
    
    st.download_button("CSV 파일 다운로드", csv_data, file_name='card_data.csv', mime='text/csv')
    st.download_button("엑셀 파일 다운로드", excel_data, file_name='card_data.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
else:
    st.write("현재 조회된 데이터가 없습니다. 필터를 조정해 보세요.")