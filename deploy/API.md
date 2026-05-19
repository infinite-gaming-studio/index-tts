# IndexTTS2 API 接口文档

## 服务信息

- **服务名称**: IndexTTS2
- **默认端口**: 8000
- **基础URL**: `http://localhost:8000`

## 启动服务

```bash
# 启动完整服务（API + WebUI）
python deploy/service.py --port 8000 --mode both

# 仅启动API服务
python deploy/service.py --mode api

# 仅启动WebUI服务
python deploy/service.py --mode webui

# 启用API鉴权（设置环境变量）
export INDEXTTS_API_TOKEN="your-secret-token"
python deploy/service.py --mode api
```

### 启动参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--port` | int | 8000 | 服务端口 |
| `--mode` | str | both | 部署模式：`api`仅API, `webui`仅WebUI, `both`两者 |
| `--repo-dir` | str | 自动检测 | 项目根目录路径 |
| `--no-fp16` | flag | - | 禁用FP16半精度推理 |

---

## API 端点

### 1. 语音合成

将文本转换为语音，使用参考音频克隆音色，支持 4 种情感控制模式。

- **URL**: `/api/tts`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`

#### 鉴权

如果设置了 `INDEXTTS_API_TOKEN` 环境变量，需要在请求头中携带 Token：

```
Authorization: Bearer <your-token>
```

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 要合成的文本内容 |
| `spk_audio` | file | 是 | - | 音色参考音频文件（支持 WAV、MP3 等格式） |
| `emo_mode` | int | 否 | 0 | 情感控制模式（见下表） |
| `emo_alpha` | float | 否 | 1.0 | 情感强度系数（0.0 - 2.0） |
| `emo_audio` | file | 否 | - | 情感参考音频（`emo_mode=1` 时使用） |
| `emo_vector` | string | 否 | - | 8维情感向量 JSON 数组（`emo_mode=2` 时使用） |
| `emo_text` | string | 否 | - | 情感描述文本（`emo_mode=3` 时使用） |
| `use_random` | bool | 否 | false | 情感随机采样（`emo_mode=2` 时可用） |
| `speed` | float | 否 | 1.0 | 语速调节系数（0.5 - 2.0，大于1.0加速，小于1.0减速） |
| `target_length_ms` | int | 否 | - | 目标时长毫秒数（若指定，则精确拉伸/压缩音频到该时长） |
| `do_sample` | bool | 否 | true | 是否进行采样 |
| `top_p` | float | 否 | 0.8 | Top-p 采样参数 |
| `top_k` | int | 否 | 30 | Top-k 采样参数 |
| `temperature` | float | 否 | 0.8 | 温度参数 |
| `length_penalty` | float | 否 | 0.0 | 长度惩罚 |
| `num_beams` | int | 否 | 3 | Beam search 宽度 |
| `repetition_penalty` | float | 否 | 10.0 | 重复惩罚 |
| `max_mel_tokens` | int | 否 | 1500 | 最大生成 token 数 |
| `max_text_tokens_per_segment` | int | 否 | 120 | 分句最大 token 数 |

#### 情感控制模式 (emo_mode)

| 值 | 模式 | 需要的额外参数 | 说明 |
|----|------|---------------|------|
| 0 | 与音色参考音频相同 | 无 | 使用说话人声音的情感（默认） |
| 1 | 使用情感参考音频 | `emo_audio` | 通过参考音频控制情感 |
| 2 | 使用情感向量控制 | `emo_vector` | 通过 8 维向量精确控制情感 |
| 3 | 使用情感描述文本控制 | `emo_text` | 通过文本自动检测情感（实验性） |

#### 情感向量说明 (emo_vector)

8 维情感向量格式: `[喜, 怒, 哀, 惧, 厌恶, 低落, 惊喜, 平静]`

每个维度取值范围 `0.0 - 1.0`。系统会自动应用偏置系数并归一化（总和不超过 0.8）。

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

**成功 (200)**:
- Content-Type: `audio/wav`
- 返回生成的音频文件（WAV格式）

**参数错误 (400)**:
```json
{
  "error": "emo_vector 必须是长度为8的JSON数组 [喜,怒,哀,惧,厌恶,低落,惊喜,平静]"
}
```

**失败 (500)**:
```json
{
  "error": "错误信息描述"
}
```

**模型未加载 (503)**:
```json
{
  "error": "模型未加载"
}
```

#### 调用示例

**模式 0 - 与音色参考音频相同（默认）**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  --output output.wav
```

**语速与时长控制示例**:
```bash
# 将语速设为 1.3 倍
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "speed=1.3" \
  --output output.wav

# 将音频绝对时长固定为 4500 毫秒（4.5秒）
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "target_length_ms=4500" \
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

**模式 3 - 使用情感描述文本控制**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "emo_mode=3" \
  -F "emo_text=开心快乐" \
  --output output.wav
```

**Python (requests - 模式 2 情感向量)**:
```python
import requests
import json

url = "http://localhost:8000/api/tts"

# 8维情感向量: [喜, 怒, 哀, 惧, 厌恶, 低落, 惊喜, 平静]
emo_vector = [0.8, 0, 0, 0, 0, 0, 0, 0]  # 开心

with open("reference.wav", "rb") as f:
    files = {"spk_audio": f}
    data = {
        "text": "今天天气真好啊",
        "emo_mode": 2,
        "emo_vector": json.dumps(emo_vector),
        "emo_alpha": 1.0,
        "speed": 1.2,                 # 👈 语速设为1.2倍
        "target_length_ms": 3000,     # 👈 目标时长3000毫秒（可选，设为None或不传则不启用）
    }
    response = requests.post(url, files=files, data=data)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("合成成功!")
else:
    print(f"错误: {response.json()}")
```

**Python (requests - 模式 1 情感参考音频)**:
```python
import requests

url = "http://localhost:8000/api/tts"

with open("reference.wav", "rb") as spk_f, open("emotion.wav", "rb") as emo_f:
    files = {"spk_audio": spk_f, "emo_audio": emo_f}
    data = {
        "text": "今天天气真好啊",
        "emo_mode": 1,
        "emo_alpha": 0.8,
    }
    response = requests.post(url, files=files, data=data)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
```

**Python (httpx - 带鉴权)**:
```python
import httpx
import json

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
formData.append("emo_mode", "2");
formData.append("emo_vector", JSON.stringify([0.8, 0, 0, 0, 0, 0, 0, 0]));
formData.append("emo_alpha", "1.0");

fetch("http://localhost:8000/api/tts", {
  method: "POST",
  body: formData
})
.then(response => response.blob())
.then(blob => {
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.play();
});
```

---

### 2. 健康检查

检查服务状态及模型加载情况。

- **URL**: `/api/health`
- **Method**: `GET`

#### 响应

```json
{
  "status": "ok",
  "model": "IndexTTS2",
  "device": "cuda:0",
  "loaded": true
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态，"ok"表示正常 |
| `model` | string | 模型名称 |
| `device` | string | 当前使用的计算设备 |
| `loaded` | boolean | 模型是否已加载 |

#### 调用示例

```bash
curl http://localhost:8000/api/health
```

---

### 3. 首页

- **URL**: `/`
- **Method**: `GET`
- **返回**: HTML页面，显示服务信息和入口链接

---

### 4. API 文档 (Swagger UI)

- **URL**: `/docs`
- **Method**: `GET`
- **返回**: FastAPI 自动生成的 Swagger UI 文档页面

---

### 5. WebUI 界面

- **URL**: `/ui`
- **Method**: `GET`
- **返回**: Gradio Web 交互界面

---

## 错误处理

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 401 | 未授权（Token 无效或缺失） |
| 500 | 服务器内部错误（如推理失败） |
| 503 | 服务不可用（模型未加载） |

### 错误响应格式

所有错误响应均为 JSON 格式：

```json
{
  "error": "详细的错误描述信息"
}
```

---

## 模型配置

### 配置类 (TTSConfig)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `cfg_path` | `checkpoints/config.yaml` | 模型配置文件路径 |
| `model_dir` | `checkpoints/` | 模型检查点目录 |
| `port` | 8000 | 服务端口 |
| `mode` | both | 服务模式 |
| `use_fp16` | true | 是否使用半精度推理 |
| `device` | cuda:0 / cpu | 推理设备 |

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `INDEXTTS_REPO_DIR` | 项目根目录路径 |
| `INDEXTTS_API_TOKEN` | API 鉴权 Token（可选，设置后 `/api/tts` 需要鉴权） |

---

## 服务启动器

### 从 Notebook 启动

```python
from deploy.launcher import quick_start

# 快速启动
launcher = quick_start(port=8000, mode="both")

# 带 ngrok 公网访问
launcher = quick_start(port=8000, mode="both", ngrok_token="your_token")
```

### 命令行启动器

```bash
# 启动
python deploy/launcher.py start --port 8000 --mode both

# 停止
python deploy/launcher.py stop

# 查看状态
python deploy/launcher.py status

# 查看日志
python deploy/launcher.py logs --lines 50
```

---

## 技术栈

- **Web 框架**: FastAPI
- **UI 框架**: Gradio
- **服务器**: Uvicorn
- **模型推理**: PyTorch
- **音频处理**: torchaudio, librosa, soundfile

---

## 注意事项

1. **模型加载时间**: 首次启动服务时需要加载模型，可能需要 10-30 秒
2. **显存要求**: 建议使用 GPU 进行推理，CPU 推理速度较慢
3. **参考音频**: 支持常见音频格式（WAV、MP3 等），建议使用 16kHz+ 采样率的清晰音频
4. **情感强度**: `emo_alpha` 参数范围建议 0.5-1.5，数值越大情感表达越强烈
