import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y%m%d")
    print(f"🔍 執行權證分點爬蟲 - {today}")

    urls = [
        f"https://www.twse.com.tw/exchangeReport/BFIAUU?response=json&date={today_str}",
        f"https://www.twse.com.tw/exchangeReport/BFT41U?response=json&date={today_str}",
    ]

    df = pd.DataFrame()
    for url in urls:
        try:
            res = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                js = res.json()
                if js.get("stat") == "OK" and "data" in js:
                    df = pd.DataFrame(js["data"], columns=js["fields"])
                    df["日期"] = today
                    print(f"✅ 成功抓取 {len(df)} 筆數據")
                    print(f"實際欄位: {list(df.columns)}")
                    break
        except:
            continue

    if df.empty:
        print("❌ 今日無數據")
        matrix = {"updateTime": today, "message": "今日無新數據"}
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=4)
        return

    # 數據清洗
    numeric_cols = ["成交數量", "成交筆數", "成交金額", "成交價", "最後揭示買量", "最後揭示賣量"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors='coerce').fillna(0)

    df["TotalValue_萬"] = df.get("成交金額", 0) / 10000

    # 目前這個 API 沒有分點資訊，先產生全市場前十大
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": [],
        "brokers": {},
        "note": "目前 API 無分點資料，僅提供全市場前十大"
    }

    # 全市場前十大交易金額權證
    if not df.empty:
        top = df.groupby(["證券代號", "證券名稱"])["TotalValue_萬"].sum().reset_index()
        top10 = top.sort_values("TotalValue_萬", ascending=False).head(10)
        
        matrix["topTen"] = [
            {
                "rank": i+1,
                "code": str(row["證券代號"]),
                "name": str(row["證券名稱"]),
                "totalAmount": round(row["TotalValue_萬"], 2)
            } for i, row in top10.iterrows()
        ]

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    # 建立空的 history.csv 避免錯誤
    pd.DataFrame().to_csv("history.csv", index=False, encoding="utf-8")

    print("🎉 執行完成！已產生全市場前十大交易金額權證")

if __name__ == "__main__":
    run_pipeline()
