import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

# ================== 設定區 ==================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiZGlidWdpZSIsImVtYWlsIjoib3M2NzY2N0BvdXRsb29rLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.iy4FsYxoDfQufs9gkC8wpotIk10c9fRHm5nkS4d-xUI"   # ←←← 改成你的 Token

TARGET_BROKERS = ["永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", "元大-南屯", "元大-北港", "兆豐-小港"]
# ===========================================

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🔍 開始執行權證分點爬蟲 - {today}")

    # 抓取最近幾天權證分點資料（FinMind）
    try:
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockWarrantTradingDailyReport",
            "token": FINMIND_TOKEN,
            "start_date": (datetime.now() - timedelta(days=65)).strftime("%Y-%m-%d"),
            "end_date": today
        }
        
        res = requests.get(url, params=params, timeout=30)
        data = res.json()
        
        if data.get("status") == 200:
            df = pd.DataFrame(data["data"])
            print(f"✅ 成功抓取 {len(df)} 筆權證分點數據")
        else:
            print("❌ FinMind API 回傳異常:", data.get("msg"))
            return
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return

    # 數據清洗
    df["date"] = pd.to_datetime(df["date"])
    numeric_cols = ["BuyVolume", "SellVolume", "BuyValue", "SellValue"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df["NetValue"] = df.get("BuyValue", 0) - df.get("SellValue", 0)

    # 過濾目標分點
    df_filtered = df[df["Broker"].astype(str).str.contains("|".join(TARGET_BROKERS), na=False)].copy()

    # 存歷史
    hist_file = "history.csv"
    if os.path.exists(hist_file):
        df_hist = pd.read_csv(hist_file, encoding="utf-8")
        df_total = pd.concat([df_hist, df_filtered], ignore_index=True)
    else:
        df_total = df_filtered

    # 保留60天
    cutoff = datetime.now() - timedelta(days=60)
    df_total = df_total[df_total["date"] >= cutoff]
    df_total.to_csv(hist_file, index=False, encoding="utf-8")

    # 產生 data.json
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTenByVolume": [],           # 全市場交易金額前10
        "brokers": {b: {} for b in TARGET_BROKERS}
    }

    # TODO: 後續再根據你的前端需求補充 topTenByVolume 和 brokers 的統計

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 權證分點數據更新完成！")

if __name__ == "__main__":
    run_pipeline()
