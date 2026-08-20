# 🎬 Filmora WebUI — AI 视频工作台

把 **Filmora v13.8.71（Android 高级版）** 的视频编辑与 AI 能力**反编译分析后封装移植**为可部署的 Web 工程：
- **WebUI 视频工作台**：素材库 / 剪辑台 / AI 工坊 / 任务中心 / API 密钥管理
- **OpenAI 兼容 API**：`/v1/videos/generations`（文生视频）、`/v1/videos/edits`（AI 改视频），Bearer Token 鉴权
- **高级会员能力全部解锁**（镜像自破解版 APK 的 VIP 解除态），无广告、无功能门禁

> 本项目为授权/自有实验用途的技术移植。APK 分析结论用于功能面还原，服务器端用 ffmpeg / OpenCV / Whisper 等开源栈实现等价能力，不包含 APK 内的任何商业闭源代码或素材。

---

## 1. 逆向分析结论（来自 Filmora_13.8.71_pro.apk）

| 维度 | 结论 |
|---|---|
| 包名 / 版本 | `com.wondershare.filmora` · 13.8.71 · minSdk 24 / target 34 |
| 主入口 | `com.filmorago.phone.ui.SplashActivity` |
| 破解机制 | `libSignatureKiller.so`：`Java_bin_mt_signature_KillerApplication_hookApkPath`（MT 重打包签名校验 hook）+ ARouter VIP 空实现（`/vip/provider`）→ 会员永久解锁 |
| 剪辑引擎 | `libbzffmpeg`（内置 ffmpeg）、`libCodecEngine`、`libNLETimeline`、`libNLEPlayer`、`libNLEAudioAlg` 等 40+ arm64 原生库 |
| AI 能力 | 文本生成视频（`TextToVideoRequestParam` / `text2film_v2`）、AI 消除（`AiRemoveVideoCreateReq`，mask 云端链路）、智能字幕（`libWESCaption` + ASR）、语音克隆、AI 图片 |
| 资源 | `assets/filters/*/fragment.fs`（GLSL 滤镜）、makeup / humanseg / nle / captiontemplates 等 |
| 云端 API | `ai-api.300624.com`、`api.300624.com`、`sci.filmoragosource.com` 等 |

**移植映射**：NLE 原生库无法在 x86 服务器直接运行 → 用 `ffmpeg + OpenCV` 实现同等剪辑/滤镜能力；云端 AI → 本地开源模型 + 可插拔 provider（`T2V_API_BASE` 可切外部 OpenAI 兼容视频 API）；VIP 解锁 → WebUI 登录后全功能开放。

---

## 2. 功能清单

### WebUI（管理员密码保护）
- **登录**：管理员密码 → 签名会话 Cookie（JWT）
- **素材库**：上传/预览/删除 视频·图片·音频，自动探测时长/分辨率
- **剪辑台**：
  - 操作队列：滤镜（22 种）、变速（0.5x–4x）、倒放、旋转/翻转、裁剪、缩放、静音、标题文字、字幕烧录、时间裁剪
  - 导出：MP4（分辨率/方向/CRF/帧率）或 GIF
  - 多片段合并（concat）
  - 音频提取
- **AI 工坊**：
  - 文生视频（本地生成器直接产 MP4，支持 edge-tts 配音）
  - 智能字幕（faster-whisper 转写 → SRT → 烧录）
  - AI 消除（背景抠像：rembg 优先 / GrabCut 兜底；视频帧级处理）
  - AI 自动剪辑（场景检测 → 高光片段）
- **任务中心**：实时进度 / 状态 / 结果
- **API 密钥**：创建/复制/撤销 `sk-*` 密钥

### OpenAI 兼容 API
| 端点 | 说明 |
|---|---|
| `GET /v1/models` | 模型列表 |
| `POST /v1/videos/generations` | 文生视频（异步 202，轮询 `/v1/videos/{id}`） |
| `POST /v1/videos/edits` | AI 改视频：自然语言 prompt 或结构化 ops（滤镜/变速/倒放/字幕/背景消除/裁剪…） |
| `GET /v1/videos/{job_id}` | 任务状态 / 结果（url 或 b64_json） |
| `POST /v1/files` · `GET /v1/files/{id}` | 上传/查询媒体 |

鉴权：`Authorization: Bearer sk-xxx`。错误统一 OpenAI 格式 `{"error":{"message":...}}`。

---

## 3. 快速开始

### 方式 A：裸机（Python 3.11+，Node 22 可选）
```bash
# 依赖
sudo apt-get install -y ffmpeg
cd backend && pip install -r requirements.txt
# （可选）AI 增强
pip install -r requirements-ai.txt   # faster-whisper / rembg / edge-tts / PySceneDetect

# 构建前端
cd ../frontend && npm install && npm run build && cd ..

# 启动
cp .env.example .env   # 修改 ADMIN_PASSWORD / SECRET_KEY
bash start.sh          # 或 cd backend && python run.py
```
打开 http://127.0.0.1:8000 ，默认管理员密码 `admin123`（务必修改）。

### 方式 B：Docker
```bash
docker compose up -d --build
# 环境变量见 .env.example
```

---

## 4. OpenAI API 使用示例

```bash
BASE=http://127.0.0.1:8000
KEY=sk-你的密钥

# 1) 文生视频
curl -X POST $BASE/v1/videos/generations \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"filmora-t2v","prompt":"一只猫在弹钢琴","duration":5,"size":"1280x720"}'
# → {"id":"job_xxx","status":"queued",...}

# 2) 轮询结果
curl $BASE/v1/videos/job_xxx -H "Authorization: Bearer $KEY"
# → {"status":"completed","output":{"data":[{"url":"http://.../exports/t2v_....mp4"}]}}

# 3) AI 改视频（自然语言）
curl -X POST $BASE/v1/videos/edits \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"model":"filmora-video-edit","video":"m_上传的文件id","prompt":"make it black and white and speed up 2x"}'

# 4) 结构化 ops
curl -X POST $BASE/v1/videos/edits \
  -H "Authorization: Bearer $KEY" -H 'Content-Type: application/json' \
  -d '{"video":"m_xxx","ops":[{"op":"filter","filter":"vintage"},{"op":"trim","start":0,"end":5}]}'

# 5) 上传视频文件
curl -X POST $BASE/v1/files -H "Authorization: Bearer $KEY" -F "file=@clip.mp4"
```

Python SDK 风格调用：
```python
import requests
r = requests.post(f"{base}/v1/videos/generations",
    headers={"Authorization": f"Bearer {key}"},
    json={"model": "filmora-t2v", "prompt": "海边日落", "duration": 5})
job = r.json()["id"]
while True:
    j = requests.get(f"{base}/v1/videos/{job}", headers=H).json()
    if j["status"] in ("completed", "failed"): break
print(j["output"]["data"][0]["url"])
```

---

## 5. 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `ADMIN_PASSWORD` | `admin123` | WebUI 管理员密码 |
| `SECRET_KEY` | 随机 | 会话签名密钥，生产必改 |
| `PORT` / `HOST` | 8000 / 0.0.0.0 | 服务地址 |
| `MAX_UPLOAD_MB` | 2048 | 上传上限 |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8000` | API 返回绝对 URL 前缀 |
| `API_KEYS` | 空 | 静态 key（逗号分隔，可选） |
| `T2V_PROVIDER` | `local` | `local` / `openai` |
| `T2V_API_BASE` / `T2V_API_KEY` | 空 | 外部 OpenAI 兼容视频 API |
| `WHISPER_MODEL` / `WHISPER_DEVICE` | small / auto | 语音转写参数 |

---

## 6. 目录结构
```
filmora-webui/
├── backend/            # FastAPI 后端
│   ├── app/
│   │   ├── main.py     # 应用入口 + SPA 静态服务
│   │   ├── config.py / db.py / auth.py / jobs.py
│   │   ├── engine/     # ffmpeg / filters / subtitles / remove_bg / auto_clip / t2v
│   │   └── routers/    # auth / media / edit / ai / api_keys / openai_api
│   ├── requirements.txt / requirements-ai.txt
│   └── Dockerfile
├── frontend/           # Vite + React + Tailwind（HaizhucodexDesignSkill 设计）
│   └── dist/           # 构建产物（后端直接服务）
├── data/               # uploads / jobs / exports / db（运行数据）
├── docker-compose.yml
├── start.sh
├── .env.example
├── DESIGN.md           # 设计系统
└── README.md
```

---

## 7. 技术栈
- 后端：FastAPI · SQLite · asyncio 任务队列 · JWT 会话 · Bearer API Key
- 视频：ffmpeg 6 / ffprobe / OpenCV / Pillow
- AI：faster-whisper（可选）· rembg（可选）· PySceneDetect（可选）· edge-tts（可选）
- 前端：React 18 · Vite 5 · Tailwind CSS · TypeScript
