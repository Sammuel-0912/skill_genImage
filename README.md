# FAL Studio

透過 FAL AI 生成圖片與影片的 Windows 桌面應用程式。左邊操作面板、右邊作品牆。

## 啟動

雙擊 **`啟動.bat`**。第一次會自動裝 PySide6，之後直接開。

也可以手動：

```
pip install -r requirements.txt
pythonw run.pyw
```

第一次開啟請按右上角**偏好設定**，貼上 FAL 金鑰（fal.ai → Dashboard → Keys）。
金鑰存在專案資料夾的 `.env`，不會外傳。

## 資料夾

```
skill_genImage/
├── 啟動.bat          # 雙擊啟動
├── run.pyw           # 程式進入點
├── app/              # 程式碼
├── models.json       # 模型與參數設定（可自行增修）
├── pricing.json      # 成本估算價目表（可自行增修）
├── .env              # FAL_KEY
├── referenced_image/ # 拖曳進來的參考圖會複製到這裡
├── finished_file/    # 成品；.meta/ 存每張作品的提示詞與設定
└── fal_image.py      # 命令列版本（仍可單獨使用）
```

## 支援的模型

| 模式 | 模型 | 文生 | 參考圖／圖生 |
|---|---|---|---|
| 圖片 | Nano Banana 2 | `fal-ai/nano-banana-2` | `fal-ai/nano-banana-2/edit` |
| 圖片 | GPT Image 2 | `openai/gpt-image-2` | `openai/gpt-image-2/edit` |
| 影片 | Veo 3.1 | `fal-ai/veo3.1` | `fal-ai/veo3.1/image-to-video` |
| 影片 | Seedance 2.5 | `bytedance/seedance-2.5/text-to-video` | `bytedance/seedance-2.5/image-to-video` |

拖了參考圖就自動走該模型的圖生接口。影片模型只吃單張起始畫格。

### 加新模型

編輯 `models.json`，照現有格式加一筆就好，App 會自動長出對應的參數按鈕：

```json
{
  "id": "模型代號",
  "label": "顯示名稱",
  "endpoints": { "text": "接口 id", "ref": "圖生接口 id" },
  "ref_field": "image_urls",     // 或 image_url
  "ref_multi": true,
  "ref_max": 10,
  "params": [
    { "key": "aspect_ratio", "label": "比例", "type": "enum",
      "default": "16:9", "values": ["16:9", "1:1"] }
  ]
}
```

參數 `type` 支援 `enum`、`int`、`bool`。`values` 可以是字串陣列，也可以是
`{"label": "顯示文字", "value": "實際送出的值"}`。

## 成本估算

生成按鈕旁的 `~$x.xx` 是依 `pricing.json` 算出來的**估計值**，不是帳單。
fal 調價時自行修改該檔，重開 App 生效。

## 操作

- **Ctrl + Enter**：送出生成
- **點作品**：放大預覽，看得到當時的提示詞與所有設定
- **滑過作品**：右上角出現下載與刪除
- **深淺色**：跟隨 Windows 系統設定自動切換

## 已知限制

- 影片沒有內嵌播放器，預覽視窗會用系統播放器開啟。
- 參考圖以 base64 內嵌送出，單張建議別超過 30 MB。
- 生成最長等 15 分鐘，逾時會提示改用較低解析度。
