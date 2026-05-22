import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

TARGET_BROKERS = ["永豐金", "群益金鼎", "華南永昌", "元大", "兆豐"]

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y%m%d")
    print(f"執行權證分點爬蟲 - {today}")

    # 抓取數據
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
                    print(f"成功抓取 {len(df)} 筆數據")
                    print(f"欄位: {list(df.columns)}")
                    break
        except:
            continue

    if df.empty:
        print("今日無數據")
        matrix = {"updateTime": today, "topTen": [], "brokers": {}}
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(matrix, f, ensure_ascii=False, indent=4)
        return

    # 清洗數據
    if "成交金額" in df.columns:
        df["TotalValue_萬"] = pd.to_numeric(df["成交金額"].astype(str).str.replace(",", ""), errors='coerce').fillna(0) / 10000
    else:
        df["TotalValue_萬"] = 0

    # 1. 市場前十大交易金額權證
    topTen = []
    if not df.empty:
        top = df.groupby(["證券代號", "證券名稱"])["TotalValue_萬"].sum().reset_index()
        top10 = top.sort_values("TotalValue_萬", ascending=False).head(10)
        topTen = [
            {
                "rank": i+1,
                "code": str(row["證券代號"]),
                "name": str(row["證券名稱"]),
                "totalAmount": round(row["TotalValue_萬"], 1)
            } for i, row in top10.iterrows()
        ]

    # 2. 六大分點排行（目前 API 無券商欄位，先留空）
    brokers_data = {b: {"1": [], "5": [], "10": [], "20": [], "60": []} for b in TARGET_BROKERS}

    # 產生最終 JSON
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": topTen,
        "brokers": brokers_data
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("執行完成！已產生市場前十大交易金額權證")

if __name__ == "__main__":
    run_pipeline()
