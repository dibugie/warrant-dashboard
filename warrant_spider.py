import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

TARGET_BROKERS = ["永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", "元大-南屯", "元大-北港", "兆豐-小港"]

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🔍 執行權證分點爬蟲 (TWSE 官方) - {today}")

    # TWSE 權證分點資料 API（每日更新）
    url = f"https://www.twse.com.tw/exchangeReport/BFIAUU?response=json&date={datetime.now().strftime('%Y%m%d')}&stockNo="

    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        js = res.json()
        
        if js.get("stat") != "OK" or "data" not in js:
            print("❌ 今日尚無權證分點數據（非交易日或資料未更新）")
            return
            
        df = pd.DataFrame(js["data"], columns=js["fields"])
        df["日期"] = today
        print(f"✅ 成功抓取 {len(df)} 筆權證分點數據")
        
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return

    # 數據清洗
    numeric_cols = ["買進股數", "賣出股數", "成交股數", "價格"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

    df["NetValue"] = (df.get("買進股數", 0) - df.get("賣出股數", 0)) * df.get("價格", 0) / 1000   # 千元單位
    df["TotalValue"] = (df.get("買進股數", 0) + df.get("賣出股數", 0)) * df.get("價格", 0) / 1000

    # 過濾六大分點
    df_filtered = df[df["券商"].astype(str).str.contains("|".join(TARGET_BROKERS), na=False)].copy()
    print(f"六大分點過濾後: {len(df_filtered)} 筆")

    # 存歷史
    hist_file = "history.csv"
    if os.path.exists(hist_file):
        df_hist = pd.read_csv(hist_file, encoding="utf-8")
        df_total = pd.concat([df_hist, df_filtered], ignore_index=True)
    else:
        df_total = df_filtered

    # 保留60天
    df_total["日期"] = pd.to_datetime(df_total["日期"], errors='coerce')
    cutoff = datetime.now() - timedelta(days=60)
    df_total = df_total[df_total["日期"] >= cutoff]

    df_total.to_csv(hist_file, index=False, encoding="utf-8")

    # 產生 data.json（簡化版）
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": {},
        "brokers": {b: {} for b in TARGET_BROKERS}
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 TWSE 權證分點更新完成！")

if __name__ == "__main__":
    run_pipeline()
