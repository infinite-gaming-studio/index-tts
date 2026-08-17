# IndexTTS-2.5 API 接口文档

底层引擎为 **IndexTTS-2.5**（`indextts.infer_v2_5.IndexTTS2`），在旧版 IndexTTS2 API
基础上新增：多语言、语速/时长控制、Qwen 情感文本、BF16、base64 响应等特性。

## 服务信息

- **服务名称**: IndexTTS-2.5
- **默认端口**: 8000
- **基础URL**: `http://localhost:8000`
- **Swagger 文档**: `http://localhost:8000/docs`

## 启动服务

```bash
# 仅 API（推荐）
uv run --all-extras python deploy/service.py --mode api --port 8000

# API + WebUI（/ui）
uv run --all-extras python deploy/service.py --mode both --port 8000

# 鉴权说明: 默认固定 Key: indextts-fixed-key-2026 (见启动日志, 直接使用)
uv run --all-extras python deploy/service.py --mode api

# 自定义 Key (更安全, 仓库公开时建议设置)
export INDEXTTS_API_TOKEN="your-secret-token"
uv run --all-extras python deploy/service.py --mode api

# 显式关闭鉴权 (仅建议内网/本机使用)
export INDEXTTS_API_TOKEN=""
uv run --all-extras python deploy/service.py --mode api
```

### 启动参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--port` | int | 8000 | 服务端口 |
| `--mode` | str | api | `api`仅API, `webui`仅WebUI, `both`两者 |
| `--repo-dir` | str | 自动检测 | 项目根目录路径 |
| `--model-dir` | str | checkpoints | 模型目录（2.5 权重） |
| `--no-bf16` | flag | - | 禁用 BF16（2.5 默认开启半精度） |
| `--device` | str | 自动 | `cuda:0` / `cpu` 等 |
| `--deepspeed` | flag | - | 启用 DeepSpeed 加速 |
| `--cuda-kernel` | flag | - | 启用 BigVGAN CUDA kernel |
| `--accel` | flag | - | 启用 GPT2 加速引擎 |
| `--torch-compile` | flag | - | 启用 torch.compile |
| `--qwen-emo` | flag | - | 加载 QwenEmotion（emo_mode=3 需要） |
| `--default-lang` | str | ZH | WebUI 默认语言 |

> [!IMPORTANT]
> `emo_mode=3`（情感描述文本）需要 `--qwen-emo`，否则会报错。
> 并发请求由内部线程锁串行化（IndexTTS2 内部有说话人/情感缓存，需保护）。

---

## API 端点

### 1. 语音合成

将文本转换为语音，使用参考音频克隆音色，支持 4 种情感控制模式与多语言。

- **URL**: `/api/tts`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

#### 鉴权

**默认开启**：未设置 `INDEXTTS_API_TOKEN` 时，使用默认固定 Key：

```
Authorization: Bearer indextts-fixed-key-2026
```

- 自定义 Key：`export INDEXTTS_API_TOKEN="your-secret-token"`
- 关闭鉴权：`export INDEXTTS_API_TOKEN=""`（仅建议内网/本机使用）
- 注意：本仓库公开时默认 Key 也是公开的，生产环境请自定义 Key

所有合成请求需在请求头携带：

```
Authorization: Bearer <your-token>
```

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 要合成的文本内容 |
| `spk_audio` | file | 是 | - | 音色参考音频文件（WAV、MP3 等） |
| `lang` | string | 否 | ZH | 语言: `ZH`/`EN`/`JA`/`ES`/`AR`/`ZHEN`（2.5 多语言） |
| `emo_mode` | int | 否 | 0 | 情感控制模式（见下表） |
| `emo_alpha` | float | 否 | 1.0 | 情感强度系数（0.0 - 2.0） |
| `emo_audio` | file | 否 | - | 情感参考音频（`emo_mode=1` 时使用） |
| `emo_vector` | string | 否 | - | 8维情感向量 JSON 数组（`emo_mode=2` 时使用） |
| `emo_text` | string | 否 | - | 情感描述文本（`emo_mode=3` 时使用，缺省用主文本） |
| `use_random` | bool | 否 | false | 情感向量随机采样（`emo_mode=2` 时可用） |
| `duration_factor` | float | 否 | 1.0 | 语速/时长因子 0.5-2.0（2.5 新特性） |
| `do_sample` | bool | 否 | true | 是否进行采样 |
| `top_p` | float | 否 | 0.8 | Top-p 采样参数 |
| `top_k` | int | 否 | 30 | Top-k 采样参数 |
| `temperature` | float | 否 | 0.8 | 温度参数 |
| `length_penalty` | float | 否 | 0.0 | 长度惩罚 |
| `num_beams` | int | 否 | 3 | Beam search 宽度 |
| `repetition_penalty` | float | 否 | 10.0 | 重复惩罚 |
| `max_mel_tokens` | int | 否 | 1500 | 最大生成 token 数 |
| `max_text_tokens_per_segment` | int | 否 | 120 | 分句最大 token 数 |
| `response_format` | string | 否 | wav | `wav` 返回音频文件 / `json` 返回 base64 |

#### 情感控制模式 (emo_mode)

| 值 | 模式 | 需要的额外参数 | 说明 |
|----|------|---------------|------|
| 0 | 与音色参考音频相同 | 无 | 使用说话人声音的情感（默认） |
| 1 | 使用情感参考音频 | `emo_audio` | 通过参考音频控制情感 |
| 2 | 使用情感向量控制 | `emo_vector` | 通过 8 维向量精确控制情感 |
| 3 | 使用情感描述文本控制 | `emo_text` | 文本自动检测情感（需 `--qwen-emo`） |

#### 情感向量说明 (emo_vector)

8 维情感向量格式: `[喜, 怒, 哀, 惧, 厌恶, 低落, 惊喜, 平静]`

每个维度取值范围 `0.0 - 1.0`。系统自动应用偏置系数并归一化（总和不超过 0.8）。

| 索引 | 维度 | 说明 |
|------|------|------|
| 0 | 喜 (happy) | 快乐 |
| 1 | 怒 (angry) | 愤怒 |
| 2 | 哀 (sad) | 悲伤 |
| 3 | 惧 (afraid) | 恐惧 |
| 4 | 厌恶 (disgusted) | 厌恶 |
| 5 | 低落 (melancholic) | 低落 |
| 6 | 惊喜 (surprised) | 惊喜 |
| 7 | 平静 (calm) | 平静 |

#### 响应

**成功 (200) — `response_format=wav`（默认）**:
- Content-Type: `audio/wav`
- 返回生成的 WAV 音频文件

**成功 (200) — `response_format=json`**:
```json
{
  "audio_base64": "UklGRi4AAABXQVZF...",
  "sample_rate": 22050,
  "format": "wav",
  "lang": "ZH"
}
```

**参数错误 (400)**:
```json
{ "error": "emo_vector 必须是长度为8的JSON数组 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]" }
```

**鉴权失败 (401)**:
```json
{ "error": "Missing or invalid authentication token" }
```

**推理失败 (500)**:
```json
{ "error": "错误信息描述" }
```

**模型未加载 (503)**:
```json
{ "error": "模型未加载" }
```

#### 调用示例

**模式 0 - 与音色参考音频相同（默认）**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  --output output.wav
```

**模式 1 - 使用情感参考音频**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "emo_mode=1" \
  -F "emo_audio=@emotion_ref.wav" \
  -F "emo_alpha=0.8" \
  --output output.wav
```

**模式 2 - 使用情感向量控制**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "emo_mode=2" \
  -F "emo_vector=[0.8,0,0,0,0,0,0,0]" \
  -F "emo_alpha=1.0" \
  --output output.wav
```

**模式 3 - 使用情感描述文本控制（需 --qwen-emo 启动）**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "emo_mode=3" \
  -F "emo_text=开心快乐" \
  --output output.wav
```

**2.5 新特性 - 多语言英文 + 语速控制**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=Hello, this is IndexTTS-2.5 speaking English." \
  -F "spk_audio=@reference.wav" \
  -F "lang=EN" \
  -F "duration_factor=1.2" \
  --output output.wav
```

**Python (requests - 情感向量 + JSON 响应)**:
```python
import requests, json, base64

resp = requests.post(
    "http://localhost:8000/api/tts",
    files={"spk_audio": open("reference.wav", "rb")},
    data={
        "text": "今天天气真好啊",
        "lang": "ZH",
        "emo_mode": 2,
        "emo_vector": json.dumps([0.8, 0, 0, 0, 0, 0, 0, 0]),
        "response_format": "json",
    },
)
if resp.status_code == 200:
    data = resp.json()
    with open("output.wav", "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    print("合成成功!")
else:
    print(f"错误: {resp.json()}")
```

**Python (httpx - 带鉴权)**:
```python
import httpx, json

async def synthesize():
    url = "http://localhost:8000/api/tts"
    headers = {"Authorization": "Bearer your-secret-token"}
    with open("reference.wav", "rb") as f:
        files = {"spk_audio": ("reference.wav", f, "audio/wav")}
        data = {
            "text": "今天天气真好啊",
            "emo_mode": 2,
            "emo_vector": json.dumps([0.8, 0, 0, 0, 0, 0, 0, 0]),
            "emo_alpha": 1.0,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, files=files, data=data)
    if response.status_code == 200:
        with open("output.wav", "wb") as f:
            f.write(response.content)
```

**JavaScript (Fetch - 情感向量)**:
```javascript
const formData = new FormData();
formData.append("text", "今天天气真好啊");
formData.append("spk_audio", spkFileInput.files[0]);
formData.append("lang", "ZH");
formData.append("emo_mode", "2");
formData.append("emo_vector", JSON.stringify([0.8, 0, 0, 0, 0, 0, 0, 0]));
formData.append("emo_alpha", "1.0");

fetch("http://localhost:8000/api/tts", { method: "POST", body: formData })
  .then(r => r.blob())
  .then(blob => { const url = URL.createObjectURL(blob); new Audio(url).play(); });
```

---

### 2. 健康检查

- **URL**: `/api/health`
- **Method**: `GET`

#### 响应

```json
{
  "status": "ok",
  "model": "IndexTTS-2.5",
  "version": "2.5.0",
  "device": "cuda:0",
  "loaded": true,
  "bf16": true,
  "low_vram": false,
  "qwen_emo": false,
  "languages": ["ZH", "EN", "JA", "ES", "AR", "ZHEN"]
}
```

#### 调用示例

```bash
curl http://localhost:8000/api/health
```

---

### 3. 首页

- **URL**: `/`
- **Method**: `GET`
- **返回**: HTML 页面，显示服务信息和入口链接

---

### 4. API 文档 (Swagger UI)

- **URL**: `/docs`
- **Method**: `GET`
- **返回**: FastAPI 自动生成的 Swagger UI 文档页面

---

### 5. WebUI 界面（`--mode both` 时）

- **URL**: `/ui`
- **Method**: `GET`
- **返回**: Gradio Web 交互界面（与 API 共享同一模型实例）

---

## 错误处理

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 参数错误（如 lang 非法、emo_vector 长度不对、emo_mode 缺少配套参数） |
| 401 | 未授权（Token 无效或缺失） |
| 500 | 服务器内部错误（如推理失败） |
| 503 | 服务不可用（模型未加载） |

### 错误响应格式

所有错误响应均为 JSON 格式：

```json
{ "error": "详细的错误描述信息" }
```

---

## 环境变量

| 变量名 | 说明 |
|--------|------|
| `INDEXTTS_REPO_DIR` | 项目根目录路径 |
| `INDEXTTS_API_TOKEN` | API 鉴权 Token（可选，设置后 `/api/tts` 需要鉴权） |

---

## 注意事项

1. **模型加载时间**: 首次启动服务需要加载模型，约 10-30 秒（2.5 权重约 3-4 GB）。
2. **显存要求**: 建议 GPU（BF16 默认开启）；CPU 推理速度较慢（自动关 BF16）。
3. **参考音频**: 支持常见音频格式（WAV、MP3 等），建议 16kHz+ 清晰音频。
4. **情感强度**: `emo_alpha` 建议 0.5-1.5；`duration_factor` 建议 0.8-1.2。
5. **并发安全**: 服务内置线程锁，同一时刻仅一个推理请求执行，避免内部缓存冲突。
6. **低显存**: <10GB 显存时自动进入低显存模式（长文本自动分块）。
