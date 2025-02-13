import streamlit as st
from datetime import date,timedelta,datetime
import gspread
import os
import pandas as pd
from google.oauth2 import service_account
import pytz
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(layout="wide")
st.title("支払い管理アプリ")

#本日の日付を取得
japan_tz = pytz.timezone('Asia/Tokyo')
today = datetime.now(japan_tz).date()
formatted_date = today.strftime("%Y年%m月%d日")


        
@st.cache_resource #スプレッドシートにアクセス
def acsess_gc():
    scopes = [ 'https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    credentials = service_account.Credentials.from_service_account_info( st.secrets["gcp_service_account"], scopes=scopes)
    gc = gspread.authorize(credentials)
    # スプレッドシートからデータ取得
    SP_SHEET_KEY = st.secrets.SP_SHEET_KEY.key # スプレッドシートのキー
    sh = gc.open_by_key(SP_SHEET_KEY)
    sh = sh.worksheet("金額表")
    return sh

def get_date(today): #現在の金額の取得
    sh = acsess_gc()
    set_money = int(sh.acell("E2").value)
    df = pd.DataFrame(sh.get_all_values())
    df.columns = df.iloc[0]
    df = df.iloc[2:,:4]
    df["日付"] = pd.to_datetime(df["日付"],format="%Y年%m月%d日")
    df.set_index("日付",inplace=True)
    y_date = int(today.strftime("%Y"))
    m_date = int(today.strftime("%m"))
    # 年・月でフィルタリング
    df = df[(df.index.year == today.year) & (df.index.month == today.month)]
    df["金額"] = pd.to_numeric(df["金額"], errors="coerce")
    total_amount = df["金額"].sum()
    goal_money = set_money - total_amount
    df.index = df.index.date
    df["残高"] = set_money - df["金額"].cumsum()  # cumsum() で累積減少
    return goal_money,df,set_money

def update_amount(set_amount): #設定金額の変更
    sh = acsess_gc()
    sh.update_acell("E2",set_amount)

def update_money(pay_money,payment_items,pay_name,formatted_date): #支払い金額の追加
    sh = acsess_gc()
    find_items = [formatted_date, str(pay_money), payment_items, pay_name]
    if all(sh.find(item) for item in find_items):  # データ重複確認
        st.error("同じデータが入力されています")
    else:
        empty_row = sh.get_all_values()
        empty_row = len(empty_row) + 1 #空白の行を取得
        # 一括更新
        sh.update(f"A{empty_row}:D{empty_row}", [[formatted_date, payment_items, pay_name, pay_money]])
        st.success(f"[{payment_items}]{pay_name}:{pay_money}円支払いしました")

id_auth = st.text_input("IDを入力してください")
id_check = st.secrets.check_id.id

# 初回認証
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False  # 初期値は False

if st.button("確定", key="id_check"):
    if id_auth != id_check:
        st.info("認証されませんでした")
        st.session_state.authenticated = False
    else:
        st.session_state.authenticated = True  # 認証成功を記録
# 認証が完了している場合のみアプリを表示
if st.session_state.authenticated:
    goal_money, df, set_money = get_date(today)

    #サイドバーで金額変更
    with st.sidebar:
        st.write("目標金額変更")
        set_amount = st.sidebar.number_input("金額を入力(万円)",min_value=5,max_value=50,value=10)
        if st.button("金額確定"):
            set_amount *= 10000
            if goal_money == set_amount:
                st.error("金額が変わっていません")
            else:
                update_amount(set_amount)
                st.success(f"目標金額を{set_amount:,}円に変更しました")
        st.write(f"設定金額:{set_money:,}円")
    #現在の残高表示
    st.markdown(
        f"""
        <div style="font-size:24px;">
        <span>&lt;今月の残高&gt;</span>&nbsp;&nbsp;&nbsp;<span style="color:red;fontsize:30px;font-weight:bold;">{goal_money:,}円</span>
        </div>
        """,
        unsafe_allow_html=True)
    #画像の表示
    st.image("image/money.jpg")

    #支払い金額の表示
    payment_items = st.radio("支払い項目を選択してください",["食費","日用品","嗜好品","その他"])
    if payment_items == "食費":
        pay_name = st.radio("支払先を選択してください",["業務スーパー","オーケーストア","たまや","ロピア","ライフ","その他"])
        if pay_name == "その他":
            pay_name = st.text_input("入力してください。")
    elif payment_items == "日用品":
        pay_name = st.radio("支払先を選択してください",["HAC","サンドラッグ","その他"])
        if pay_name == "その他":
            pay_name = st.text_input("入力してください。")
    elif payment_items == "嗜好品":
        pay_name = st.radio("支払先を選択してください",["セブンイレブン","ローソン","ファミリーマート","その他"])
        if pay_name == "その他":
            pay_name = st.text_input("入力してください。")
    else:
        pay_name = st.text_input("支払い先を入力してください。")
    #金額入力
    pay_money = st.number_input("お支払い金額を入力",min_value=1,max_value=50000,value=8000) 
    # 確定ボタン押下後の処理
    if st.button("確定",key="amount_money"):
        if pay_name == "": #空の場合はERROR
            st.error("支払い先が入力されていません。")
        else:
            update_money(pay_money,payment_items,pay_name,formatted_date)

    st.write("履歴")
    st.dataframe(df,width=600)

    # **Plotly でグラフを作成**
    fig = go.Figure()

    # **棒グラフ（売上）**
    fig.add_trace(go.Bar(x=df.index, y=df["金額"], name="支払金額", marker_color="lightblue",yaxis="y1"))
    # **折れ線グラフ（売上）**
    fig.add_trace(go.Scatter(x=df.index, y=df["残高"], name="残高推移", mode="lines+markers", line=dict(color="red"),yaxis="y2"))

    # **レイアウト設定**
    fig.update_layout(
        title="支払金額と残高の推移",
        xaxis_title="日付",
        yaxis=dict(title="支払金額", tickformat=",d"),  # 左Y軸
        yaxis2=dict(title="残高", overlaying="y", side="right", tickformat=",d"),  # **右Y軸**
        xaxis=dict(tickformat="%Y-%m-%d"),  # 日付フォーマット
        template="plotly_white"
    )
    # **Streamlit で表示**
    st.plotly_chart(fig)

    # カテゴリごとの合計を計算
    category_totals = df.groupby('支払い項目')['金額'].sum().reset_index()

    # 円グラフを作成
    fig = px.pie(category_totals, values='金額', names='支払い項目', title='支払割合')

    # Streamlit アプリケーション
    st.plotly_chart(fig)
else:
    st.warning("認証が必要です。IDを入力してください。")