import os
import pandas as pd
import json
import requests
from datetime import datetime

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    today_str = datetime.now().strftime("%Y%m%d")
    print(f"🔍 執行權證成交金額排行 - {today}")

    # 權證專用 API
    url = f"https://www.twse.com.tw/exchangeReport/BWIBU?response=json&date={today_str}"

    try:
        res = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        js = res.json()
        
        if js.get("stat") != "OK" or "data" not in js:
            print("❌ 今日尚無權證數據")
            matrix = {"updateTime": today, "topTen": [], "message": "今日無權證數據"}
            with open("data.json", "w", encoding="utf-8") as f:
                json.dump(matrix, f, ensure_ascii=False, indent=4)
            return

        df = pd.DataFrame(js["data"], columns=js["fields"])
        df["日期"] = today
        print(f"✅ 成功抓取 {len(df)} 筆權證數據")
        print(f"欄位: {list(df.columns)}")

    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return

    # 數據清洗 - 成交金額轉成萬
    if "成交金額" in df.columns:
        df["TotalValue_萬"] = pd.to_numeric(df["成交金額"].astype(str).str.replace(",", ""), errors='coerce').fillna(0) / 10000
    else:
        df["TotalValue_萬"] = 0

    # 1. 市場前十大交易金額權證
    topTen = []
    if not df.empty:
        # 按成交金額排序
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

    # 產生 JSON（只保留你想要的兩個功能）
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": topTen,
        "brokers": {}   # 分點部分暫時留空（目前公開 API 難抓）
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 權證前十大交易金額更新完成！")

if __name__ == "__main__":
    run_pipeline()
