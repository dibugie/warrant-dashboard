import os
import pandas as pd
import json
import requests
from datetime import datetime, timedelta

# ================== 設定 ==================
FINMIND_TOKEN = "這裡貼上你的_Token"   # ←←← 改成你剛建立的 Token

TARGET_BROKERS = ["永豐金-內湖", "群益金鼎-中壢", "華南永昌-台中", "元大-南屯", "元大-北港", "兆豐-小港"]
# =======================================

def run_pipeline():
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"🔍 執行權證分點爬蟲 - {today}")

    # 抓取權證分點數據 (過去65天)
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
        
        if data.get("status") != 200:
            print("❌ FinMind API 錯誤:", data.get("msg"))
            return
            
        df = pd.DataFrame(data.get("data", []))
        print(f"✅ 成功抓取 {len(df)} 筆權證分點數據")
        
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return

    if df.empty:
        print("❌ 今日無數據")
        return

    # 數據清洗
    df["date"] = pd.to_datetime(df["date"])
    for col in ["buy", "sell", "price"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df["NetValue"] = df.get("buy", 0) - df.get("sell", 0)   # 買賣金額差
    df["TotalValue"] = df.get("buy", 0) + df.get("sell", 0)  # 總交易金額

    # 過濾目標分點
    df_filtered = df[df["securities_trader"].astype(str).str.contains("|".join(TARGET_BROKERS), na=False)].copy()

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

    # 產生 data.json (先簡化)
    matrix = {
        "updateTime": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "topTen": {},
        "brokers": {b: {} for b in TARGET_BROKERS}
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=4)

    print("🎉 權證分點數據更新完成！")

if __name__ == "__main__":
    run_pipeline()
