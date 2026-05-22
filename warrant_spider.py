import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

# ====================== 設定 ======================
TARGET_BROKERS = [
    "永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", 
    "元大-南屯", "元大-北港", "兆豐-小港",
    # 寬鬆匹配關鍵字
    "永豐金", "群益金鼎", "華南永昌", "元大", "兆豐"
]

INTERVALS = [1, 5, 10, 20, 60]  # 天數
# ================================================

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y%m%d")
    print(f"🔍 執行權證分點爬蟲 - {today}")

    # 嘗試多個可能的 TWSE API
    urls = [
        f"https://www.twse.com.tw/exchangeReport/BFIAUU?response=json&date={today_str}",
        f"https://www.twse.com.tw/exchangeReport/BFT41U?response=json&date={today_str}",
    ]

    df = pd.DataFrame()
    success = False

    for url in urls:
        try:
            print(f"嘗試 API: {url}")
            res = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code != 200:
                continue
            js = res.json()
            if js.get("stat") == "OK" and "data" in js and js["data"]:
                df = pd.DataFrame(js["data"], columns=js["fields"])
                df["日期"] = today
                print(f"✅ 成功抓取 {len(df)} 筆數據")
                success = True
                break
        except Exception as e:
            print(f"⚠️ API 失敗: {e}")

    if not success or df.empty:
        print("❌ 今日無新數據（常見於非交易日）")
        matrix = {"updateTime": today, "message": "今日無新數據", "topTen": {}, "brokers": {}}
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=4)
        return

    # === 數據清洗 ===
    numeric_cols = ["買進股數", "賣出股數", "成交股數", "價格", "成交金額"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

    df["NetValue_萬"] = (df.get("買進股數", 0) - df.get("賣出股數", 0)) * df.get("價格", 0) / 10000
    df["TotalValue_萬"] = (df.get("買進股數", 0) + df.get("賣出股數", 0)) * df.get("價格", 0) / 10000

    # === 過濾六大分點（加強版）===
    df["券商"] = df["券商"].astype(str)
    broker_condition = df["券商"].str.contains("|".join(TARGET_BROKERS), na=False, regex=False)
    df_filtered = df[broker_condition].copy()
    print(f"✅ 六大分點過濾後: {len(df_filtered)} 筆")

    # === 歷史資料 ===
    hist_file = "history.csv"
    if os.path.exists(hist_file):
        df_hist = pd.read_csv(hist_file, encoding="utf-8")
        df_total = pd.concat([df_hist, df_filtered], ignore_index=True)
    else:
        df_total = df_filtered

    # 保留最近60天
    df_total["日期"] = pd.to_datetime(df_total["日期"], errors='coerce')
    cutoff = datetime.now() - timedelta(days=60)
    df_total = df_total[df_total["日期"] >= cutoff].copy()

    df_total.to_csv(hist_file, index=False, encoding="utf-8")

    # === 產生 data.json ===
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": {},           # 全市場前十大交易金額
        "brokers": {b: {} for b in TARGET_BROKERS[:6]}  # 只保留原始6個
    }

    # 1. 全市場前十大交易金額權證
    if not df.empty:
        top_market = df.groupby(["證券代號", "證券名稱"])["TotalValue_萬"].sum().reset_index()
        top10 = top_market.sort_values("TotalValue_萬", ascending=False).head(10)
        matrix["topTen"]["all"] = [
            {
                "rank": i+1,
                "code": str(row["證券代號"]),
                "name": str(row["證券名稱"]),
                "totalAmount": round(row["TotalValue_萬"], 1)
            } for i, row in top10.iterrows()
        ]

    # 2. 各分點 + 各期間排行
    dates = sorted(df_total["日期"].dt.strftime("%Y-%m-%d").unique(), reverse=True)

    for b in list(matrix["brokers"].keys()):
        for days in INTERVALS:
            key = str(days)
            matrix["brokers"][b][key] = []
            
            p_dates = dates[:days]
            df_p = df_total[df_total["日期"].dt.strftime("%Y-%m-%d").isin(p_dates)]
            
            if df_p.empty:
                continue
                
            df_b = df_p[df_p["券商"].str.contains(b, na=False)]
            if df_b.empty:
                continue
                
            sum_b = df_b.groupby(["證券代號", "證券名稱"])["NetValue_萬"].sum().reset_index()
            top_b = sum_b[sum_b["NetValue_萬"] > 0].sort_values("NetValue_萬", ascending=False).head(10)
            
            for i, row in top_b.iterrows():
                matrix["brokers"][b][key].append({
                    "rank": i+1,
                    "code": str(row["證券代號"]),
                    "name": str(row["證券名稱"]),
                    "amount": round(row["NetValue_萬"], 1)
                })

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 完整數據處理完成！")
    print(f"   全市場前10筆數: {len(matrix['topTen'].get('all', []))}")
    print(f"   歷史總筆數: {len(df_total)}")

if __name__ == "__main__":
    run_pipeline()
