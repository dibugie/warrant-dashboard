import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

TARGET_BROKERS = [
    "永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", 
    "元大-南屯", "元大-北港", "兆豐-小港",
    "永豐金", "群益金鼎", "華南永昌", "元大", "兆豐"
]

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y%m%d")
    print(f"🔍 執行權證分點爬蟲 - {today}")

    # 多 API 嘗試
    urls = [
        f"https://www.twse.com.tw/exchangeReport/BFIAUU?response=json&date={today_str}",  # 權證分點
        f"https://www.twse.com.tw/exchangeReport/BFT41U?response=json&date={today_str}",  # 盤後定價
    ]

    df = pd.DataFrame()
    success_url = ""

    for url in urls:
        try:
            print(f"嘗試: {url}")
            res = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            print(f"狀態碼: {res.status_code}")
            
            if res.status_code != 200:
                continue
                
            js = res.json()
            if js.get("stat") == "OK" and "data" in js and js["data"]:
                df = pd.DataFrame(js["data"], columns=js["fields"])
                df["日期"] = today
                success_url = url
                print(f"✅ 成功抓取 {len(df)} 筆數據")
                print(f"實際欄位: {list(df.columns)}")   # ← 關鍵！讓我們看到真實欄位
                break
        except Exception as e:
            print(f"失敗: {e}")

    if df.empty:
        print("❌ 今日無數據")
        matrix = {"updateTime": today, "message": "今日無新數據", "topTen": {}, "brokers": {}}
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=4)
        return

    # === 數據清洗 ===
    numeric_cols = ["買進股數", "賣出股數", "成交股數", "成交數量", "價格", "成交價", "成交金額"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

    df["NetValue_萬"] = (df.get("買進股數", 0) - df.get("賣出股數", 0)) * df.get("價格", df.get("成交價", 0)) / 10000
    df["TotalValue_萬"] = (df.get("買進股數", 0) + df.get("賣出股數", 0)) * df.get("價格", df.get("成交價", 0)) / 10000

    # === 過濾分點（如果有券商欄位）===
    if "券商" in df.columns:
        df_filtered = df[df["券商"].astype(str).str.contains("|".join(TARGET_BROKERS), na=False)].copy()
        print(f"六大分點過濾後: {len(df_filtered)} 筆")
    else:
        print("⚠️ 目前 API 沒有「券商」欄位，使用全部數據")
        df_filtered = df.copy()

    # 歷史資料處理（簡化版）
    hist_file = "history.csv"
    if os.path.exists(hist_file):
        df_hist = pd.read_csv(hist_file, encoding="utf-8")
        df_total = pd.concat([df_hist, df_filtered], ignore_index=True)
    else:
        df_total = df_filtered

    df_total.to_csv(hist_file, index=False, encoding="utf-8")

    # === 產生 data.json ===
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": {},
        "brokers": {b.split('-')[0]: {} for b in TARGET_BROKERS[:6]},
        "rawColumns": list(df.columns)  # 幫助除錯
    }

    # 全市場前十大交易金額
    if not df.empty and "TotalValue_萬" in df.columns:
        top = df.groupby(["證券代號", "證券名稱"])["TotalValue_萬"].sum().reset_index()
        top10 = top.sort_values("TotalValue_萬", ascending=False).head(10)
        matrix["topTen"] = [
            {"rank": i+1, "code": str(r["證券代號"]), "name": str(r["證券名稱"]), "totalAmount": round(r["TotalValue_萬"], 1)}
            for i, r in top10.iterrows()
        ]

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 執行完成！請看上方「實際欄位」來繼續調整")

if __name__ == "__main__":
    run_pipeline()
