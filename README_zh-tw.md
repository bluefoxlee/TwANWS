<a href="https://www.buymeacoffee.com/tsunglung" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="30" width="120"></a>

航空氣象現代化系統（AOAWS）觀測資料 [AOAWS](https://aoaws.anws.gov.tw/) 支援 Home Assistant


這個整合是基於 MetOffice 所做的開發。

本分支整合基於 [tsunglung](https://github.com/tsunglung/TwANWS) 成果所進行的修正。因航空氣象似乎使用者少，不好麻煩，自己藉由 AI 進行小修正，作為自用。

# 安裝

你可以用 [HACS](https://hacs.xyz/) 安裝這個整合。步驟如下：HACS > Integrations > 右上角三點 > Custom repositories > URL: `https://github.com/bluefoxlee/TwANWS` > Category: Integration。

或是手動複製 `aoaws_anws` 資料夾到你的 config 資料夾的  `custom_components` 目錄下。

然後重新啟動 Home Assistant.

# 設定

**請使用 Home Assistant 整合設定**


1. 從 GUI. 設定 > 整合 > 新增整合 > Advanced Operational Aviation Weather System (AOAWS)
   1. 如果 TwANWS 沒有出現在清單裡，請 重新整理 (REFRESH) 網頁。
   2. 如果 TwANWS 還是沒有出現在清單裡，請清除瀏覽器的快取 (Cache)。
2. 選擇機場名稱。
3. 選擇語言。

# 本分支改良項目

- 保留 ANWS 原生 JSON 架構，不以全面 METAR parser 取代。
- 風速單位為 KT 時維持海里／小時，並支援 `00000KT` / `CALM` / 靜風。
- 避免將 `R06/1600U` 等 RVR 誤當成溫度／露點。
- 支援常見 RVR 格式；多跑道同時回報時取最低值，並在有 RVR 時覆蓋一般能見度。
- 保存結構化 RVR、趨勢、風組、能見度、天氣、雲組與報告標頭資料，供後續診斷與呈現使用。
- 支援 METAR／SPECI 的 `BECMG`、`TEMPO`、`NOSIG`、`AUTO`、`COR` 與 `NIL` 群組。
- ANWS JSON 欄位缺失或無效時，可回退使用 METAR 溫度、風組與能見度資料。
- 依 METAR 雲層群組補足雲量百分比與雲底高度；支援 `CAVOK`、`NSC`、`NCD` 與複合降水現象。
- 能見度分類與天氣文字依整合設定的繁中／英文顯示；標準天氣狀態代碼保持不變。
- 分開提供整合最後成功更新時間與機場報文觀測時間，方便辨識機場是否停止發布新資料。
- 將報文標頭、原始 METAR、RVR、風組、能見度、雲層與趨勢整理為可供卡片使用的屬性。
- 提供保守的本地觀測趨勢預覽，包含變化原因與信心程度；這不是飛航操作預報。
- API 或機場夜間暫停資料時保留最後有效觀測，下次五分鐘輪詢會自動重試。
- 改用 Home Assistant 的 `native_*` weather / sensor 數值與單位介面。

# 版本與維護說明

本專案是從原始 TwANWS 專案 fork 出來、獨立維護的分支。版本號與 release tag 由本分支自行管理，與原作者版本獨立；同時保留並註明原作者的貢獻。各版本的詳細變更記錄請見 [CHANGELOG.md](CHANGELOG.md)。

1.0.16 已依航空氣象電碼彙編進行 Code Book 稽核，涵蓋 ICAO/WMO 表 4678 天氣組合、風速限制、RVR 格式、AUTO 雲組，以及台灣 RMK 氣壓資料。

AOAWS 由交通部民用航空局飛航服務總臺（Air Navigation and Weather Services, CAA, MOTC；ANWS）提供與維運。

完整版本說明請見 [CHANGELOG.md](CHANGELOG.md)。


打賞

|  LINE Pay | LINE Bank | JKao Pay |
| :------------: | :------------: | :------------: |
| <img src="https://github.com/tsunglung/TwANWS/blob/master/linepay.jpg" alt="Line Pay" height="200" width="200">  | <img src="https://github.com/tsunglung/TwANWS/blob/master/linebank.jpg" alt="Line Bank" height="200" width="200">  | <img src="https://github.com/tsunglung/TwANWS/blob/master/jkopay.jpg" alt="JKo Pay" height="200" width="200">  |
