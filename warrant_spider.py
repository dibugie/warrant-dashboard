import os
import pandas as pd
import json
import requests
from datetime import datetime

TARGET_BROKERS = ["永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", "元大-南屯", "元大-北港", "兆豐-小港"]

def run_pipeline():
    today_str = datetime.now().strftime("%Y%m%d")
    # 你原本用的 API（先保留測試）
    url = f"https://www.twse.com.tw/exchangeReport/BFT41U?response=json&date={today_str}"
    
    print(f"正在抓取 {today_str} 的數據...")

    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        js = res.json()
        
        if js.get("stat") != "OK" or "data" not in js:
            print("❌ API 回傳異常")
            return
            
        df = pd.DataFrame(js["data"], columns=js["fields"])
        df["日期"] = datetime.now().strftime("%Y-%m-%d")
        print(f"✅ 成功抓取 {len(df)} 筆原始數據")
        
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return

    # 數據清洗（只處理存在的欄位）
    numeric_cols = ["買進股數", "賣出股數", "成交股數", "價格", "成交金額"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

    # 如果有買賣超欄位就用，沒有就計算
    if "買賣超股數" in df.columns:
        df["淨金額_萬"] = df["買賣超股數"] * df.get("價格", 0) / 10000
    else:
        df["淨金額_萬"] = (df.get("買進股數", 0) - df.get("賣出股數", 0)) * df.get("價格", 0) / 10000

    # 過濾目標分點
    broker_condition = df["券商"].astype(str).str.contains("|".join(TARGET_BROKERS), na=False)
    df_filtered = df[broker_condition].copy()

    print(f"過濾後剩餘 {len(df_filtered)} 筆六大分點數據")

    # 歷史紀錄
    hist_file = "history.csv"
    if os.path.exists(hist_file):
        df_hist = pd.read_csv(hist_file, encoding="utf-8")
        df_total = pd.concat([df_hist, df_filtered], ignore_index=True)
    else:
        df_total = df_filtered

    # 保留最近60天
    if not df_total.empty:
        df_total["日期"] = pd.to_datetime(df_total["日期"], errors='coerce')
        recent_dates = sorted(df_total["日期"].dt.strftime("%Y-%m-%d").unique(), reverse=True)[:60]
        df_total = df_total[df_total["日期"].dt.strftime("%Y-%m-%d").isin(recent_dates)]

    df_total.to_csv(hist_file, index=False, encoding="utf-8")

    # 產生 data.json（簡化版）
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": {},
        "brokers": {b: {} for b in TARGET_BROKERS}
    }

    # ...（後續 matrix 產生邏輯可再補，如果現在先測試就先這樣）

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 執行完成！")

if __name__ == "__main__":
    run_pipeline()
