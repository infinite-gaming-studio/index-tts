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

将文本转换为语音，使用参考音频克隆音色。

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
| `spk_audio` | file | 是 | - | 参考音频文件（支持 WAV、MP3 等格式） |
| `emo_alpha` | float | 否 | 1.0 | 情感强度系数（0.0 - 2.0） |

#### 响应

**成功 (200)**:
- Content-Type: `audio/wav`
- 返回生成的音频文件（WAV格式）

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

**cURL (无鉴权)**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "emo_alpha=1.0" \
  --output output.wav
```

**cURL (带鉴权)**:
```bash
curl -X POST "http://localhost:8000/api/tts" \
  -H "Authorization: Bearer your-secret-token" \
  -F "text=你好，这是语音合成测试" \
  -F "spk_audio=@reference.wav" \
  -F "emo_alpha=1.0" \
  --output output.wav
```

**Python (requests - 无鉴权)**:
```python
import requests

url = "http://localhost:8000/api/tts"

with open("reference.wav", "rb") as f:
    files = {"spk_audio": f}
    data = {"text": "你好，这是语音合成测试", "emo_alpha": 1.0}
    response = requests.post(url, files=files, data=data)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("合成成功!")
else:
    print(f"错误: {response.json()}")
```

**Python (requests - 带鉴权)**:
```python
import requests

url = "http://localhost:8000/api/tts"
headers = {"Authorization": "Bearer your-secret-token"}

with open("reference.wav", "rb") as f:
    files = {"spk_audio": f}
    data = {"text": "你好，这是语音合成测试", "emo_alpha": 1.0}
    response = requests.post(url, headers=headers, files=files, data=data)

if response.status_code == 200:
    with open("output.wav", "wb") as f:
        f.write(response.content)
    print("合成成功!")
else:
    print(f"错误: {response.json()}")
```

**Python (httpx)**:
```python
import httpx

async def synthesize():
    url = "http://localhost:8000/api/tts"
    
    with open("reference.wav", "rb") as f:
        files = {"spk_audio": ("reference.wav", f, "audio/wav")}
        data = {"text": "你好，这是语音合成测试", "emo_alpha": 1.0}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files, data=data)
            
    if response.status_code == 200:
        with open("output.wav", "wb") as f:
            f.write(response.content)
```

**JavaScript (Fetch)**:
```javascript
const formData = new FormData();
formData.append("text", "你好，这是语音合成测试");
formData.append("spk_audio", fileInput.files[0]);
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
