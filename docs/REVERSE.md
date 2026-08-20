# Filmora v13.8.71 Pro — 逆向分析报告

样本：`Filmora_13.8.71_pro.apk`
SHA-256：`75511d6cab92984c4a27a4d02039181f46876ddd781e6c4294f95911b1c49906`
分析工具：jadx 1.5.1 · androguard 4.1.4 · rz-bin/strings · ffprobe

## 1. 应用画像
| 项 | 值 |
|---|---|
| 包名 | `com.wondershare.filmora` |
| 版本 | 13.8.71（versionCode 213871） |
| 入口 | `com.filmorago.phone.ui.SplashActivity` |
| SDK | min 24 / target 34 / compile 34 |
| 架构 | arm64-v8a（40+ 原生库） |
| DEX | 8 个 classes*.dex（约 36MB 字节码） |

## 2. 破解机制（本包为高级版/已解锁态）
- `lib/arm64-v8a/libSignatureKiller.so`
  - 导出符号 `Java_bin_mt_signature_KillerApplication_hookApkPath`
  - 依赖 `xhook_register / xhook_refresh`，通过 hook `strcmp` 等绕过签名/包名校验（MT 管理器重打包特征）
- VIP 门面：`com.filmorago.router.vip.IVipProvider`（ARouter 接口）实现类 `za.b` 为**空实现**，路由 `/vip/provider` —— 即会员判定被掏空，恒为已解锁
- `VipHelper.isPro / isVip` 相关调用在破解态下全部放行

## 3. 功能面（移植到 WebUI 的能力）
### 剪辑/导出
- `libbzffmpeg` / `libbzffmpegcmd`：内置 ffmpeg 命令行能力
- `libCodecEngine` / `libNLE*`（Timeline/Player/Transcode/AudioAlg/OpenGLEffectMgr）：非线性剪辑引擎
- `lib7z` / `libGxun7zip`：工程打包
### AI（云端链路，客户端只做参数与结果编排）
- **文本生成视频**：`com.filmorago.phone.ui.text2video`
  - `TextToVideoRequestParam`：`keyword / duration / lang / size / orientation / expect / scene_id("text2film_v2") / long_sentence / short_sentence`
  - `TextToVideoResultBean.ListItem`：`id / type / title / tags / source / res_data / expect`
- **AI 消除**：`com.filmorago.phone.business.ai.bean.remove`
  - `AiRemoveVideoCreateReq`：`url_alias / file_link / file_info / mask`（mask 驱动的云端去除）
  - `AIRemoveParams`：TYPE_DYNAMIC_REMOVE(3) / IMAGE_REMOVE(2) / TIKTOK_REMOVE(1) / VIDEO_REMOVE(0)
- **智能字幕**：`libWESCaption` + ASR（assets/langid_model）
- **语音克隆**：`VoiceCloneGenerateResultActivity`
- **AI 图片**：homepage_ai_image
- **自动剪辑**：`saveAutoEditParam`（vibe/staticedit）
### 素材资源
- `assets/filters/*/fragment.fs`：GLSL 滤镜着色器（origin 等）
- `assets/makeup/*`（美妆）、`assets/humanseg/*`（人像分割）、`assets/nle/*`、`assets/captiontemplates/*`、`assets/fonts/*`
### 云端 API
- `ai-api.300624.com`（AI）、`api.300624.com`、`sci.filmoragosource.com`（内容资源）、`ct-api.wondershare.cc`（积分）、`face-api.wiseoel.com`（人脸）

## 4. 移植映射
| APK 能力 | WebUI 实现 |
|---|---|
| NLE 剪辑引擎 | ffmpeg 6.1 操作链（trim/merge/speed/reverse/rotate/crop/resize/export） |
| GLSL 滤镜 | ffmpeg filter 链（22 种预设，见 `app/engine/filters.py`） |
| 文本生成视频 | 本地生成器（PIL 逐帧 + ffmpeg 编码）+ 可插拔 `T2V_PROVIDER=openai` |
| AI 消除 | rembg(u2net) 优先 / OpenCV GrabCut 兜底 + inpaint |
| 智能字幕 | faster-whisper → SRT → 烧录 |
| 自动剪辑 | PySceneDetect 优先 / ffmpeg scene 兜底 |
| VIP 解锁态 | WebUI 登录即全功能开放（镜像破解态），API 用 Bearer key |
| 语音克隆/TTS | edge-tts 配音（文生视频 voiceover） |

## 5. 取证物
- `case/apk/`：APK 解包（manifest、dex、so、assets）
- `case/jadx-out/sources/`：jadx 全量反编译源码（8 dex）
- `case/Filmora.apk`：样本副本
