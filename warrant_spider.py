import os
import json
import requests
import pandas as pd
from datetime import datetime

TARGET_BROKERS = ["永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", "元大-南屯", "元大-北港", "兆豐-小港"]

def run_pipeline():
    # 1. 撈取今日證交所上市權證分點資料
    today_str = datetime.now().strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/exchangeReport/BFT41U?response=json&date={today_str}"
    
    try:
        res = requests.get(url, timeout=15)
        js = res.json()
        if js.get("stat") != "OK" or "data" not in js:
            print("今日非交易日或官方尚未公告數據。")
            return
        df_today = pd.DataFrame(js["data"], columns=js["fields"])
        df_today["日期"] = datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        print(f"證交所資料獲取失敗: {e}")
        return

    # 2. 篩選六大優質分點
    broker_condition = df_today["券商"].str.contains("|".join(TARGET_BROKERS), na=False)
    df_filtered = df_today[broker_condition].copy()

    if df_filtered.empty:
        print("今日六大分點無交易明細。")
        return

    # 3. 清洗數據
    df_filtered["買進股數"] = pd.to_numeric(df_filtered["買進股數"].astype(str).str.replace(",", ""), errors='coerce').fillna(0)
    df_filtered["賣出股數"] = pd.to_numeric(df_filtered["賣出股數"].astype(str).str.replace(",", ""), errors='coerce').fillna(0)
    df_filtered["價格"] = pd.to_numeric(df_filtered["價格"].astype(str).str.replace(",", ""), errors='coerce').fillna(0)
    df_filtered["淨金額_萬"] = (df_filtered["買進股數"] - df_filtered["賣出股數"]) * df_filtered["價格"] / 10000

    # 4. 歷史庫滾動
    hist_file = "history.csv"
    if os.path.exists(hist_file):
        try:
            df_hist = pd.read_csv(hist_file, encoding="utf-8")
            df_total = pd.concat([df_hist, df_filtered], ignore_index=True)
        except:
            df_total = df_filtered
    else:
        df_total = df_filtered

    dates = sorted(df_total["日期"].unique(), reverse=True)[:60]
    df_total = df_total[df_total["日期"].isin(dates)]
    df_total.to_csv(hist_file, index=False, encoding="utf-8")

    # 5. 建立動態 JSON 矩陣
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": {}, 
        "brokers": {b: {} for b in TARGET_BROKERS}
    }

    intervals = [1, 5, 10, 20, 60]
    for d in intervals:
        p_dates = dates[:d]
        df_p = df_total[df_total["日期"].isin(p_dates)]
        
        sum_stock = df_p.groupby(["證券代號", "證券名稱"])["淨金額_萬"].sum().reset_index()
        top_15 = sum_stock[sum_stock["淨金額_萬"] > 0].sort_values(by="淨金額_萬", ascending=False).head(15)
        total_sum = sum_stock["淨金額_萬"].sum() if sum_stock["淨金額_萬"].sum() > 0 else 1
        
        matrix["topTen"][str(d)] = []
        for idx, r in enumerate(top_15.itertuples(), 1):
            matrix["topTen"][str(d)].append({
                "rank": idx, "code": str(r.證券代號), "name": str(r.證券名稱),
                "totalAmount": round(r.淨金額_萬, 1), "ratio": round((r.淨金額_萬 / total_sum) * 100, 1),
                "change": "主力佈局", "majorBrokers": "六大分點聯合"
            })

        for b in TARGET_BROKERS:
            df_b = df_p[df_p["券商"].str.contains(b, na=False)]
            sum_b = df_b.groupby(["證券代號", "證券名稱"])["淨金額_萬"].sum().reset_index()
            top_b = sum_b[sum_b["淨金額_萬"] > 0].sort_values(by="淨金額_萬", ascending=False).head(15)
            total_b = sum_b["淨金額_萬"].sum() if sum_b["淨金額_萬"].sum() > 0 else 1
            
            matrix["brokers"][b][str(d)] = []
            for idx, r in enumerate(top_b.itertuples(), 1):
                matrix["brokers"][b][str(d)].append({
                    "rank": idx, "code": str(r.證券代號), "name": str(r.證券名稱),
                    "amount": round(r.淨金額_萬, 1), "ratio": round((r.淨金額_萬 / total_b) * 100, 1)
                })

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)
    print("數據清洗完成！")

if __name__ == "__main__":
    run_pipeline()
