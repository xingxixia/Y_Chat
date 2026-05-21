# Y_Chat

Y_Chat 是一个本地运行的智能桌宠工程。它不是网页聊天站点，而是一个以
Electron 桌面窗口和 Python FastAPI 后端为基础的本地伴随式应用原型。

项目仍处在早期开发阶段。当前仓库公开的是可运行工程骨架，以及后续接入
视觉、语音、记忆和模型推理所需的接口边界。

## 当前能力

- Electron 透明桌面宠物窗口。
- Canvas 像素风桌宠占位渲染。
- 事件驱动的气泡输出。
- Python FastAPI 后端。
- Debug 窗口可查看状态、事件、日志、权限、模型配置、记忆和推理记录。
- 本地配置、权限门控、事件记录、结构化推理输出等基础模块。
- 屏幕观察、视觉证据、OCR/VLM、音频 ASR、模型 provider 等能力已有实验接口，
  但默认受到权限和本地配置约束。

## 还不是成品

以下能力不会在默认启动时静默开启：

- 屏幕捕获。
- 麦克风监听。
- 语音输出。
- 真实模型调用。
- 外部网络/LAN/OSC/VR 适配。
- 文件写入、进程执行、输入控制等高风险动作。

这些能力必须经过明确配置和权限门控后才会进入运行链路。

## 技术栈

- 桌面端：Electron + Vite + React + Canvas
- 后端：Python + FastAPI
- 本地配置：YAML
- 本地状态：SQLite
- 开发脚本：PowerShell

默认端口：

- 后端：`18080`
- Vite：`5173`

## 本地运行

先准备 Python 环境和前端依赖：

```powershell
cd <repo>
conda activate y_chat
pip install -r backend\requirements.txt

cd frontend
npm install
```

如果你的 conda 环境名不是 `y_chat`，可以设置：

```powershell
$env:Y_CHAT_CONDA_ENV = "你的环境名"
```

也可以复制 `runtime/dev.local.example.ps1` 为
`runtime/dev.local.ps1`，写入本机专用设置。这个文件不会提交到 git。

启动：

```powershell
cd <repo>
.\scripts\start_dev.ps1
```

停止：

```powershell
cd <repo>
.\scripts\stop_dev.ps1
```

## 本地配置和隐私

`runtime/config.yaml` 是本机私有配置文件，不会提交到 git。它可能包含 API key、
本地路径或私有运行设置。新环境可以从下面的模板开始：

```text
runtime/config.example.yaml
```

运行时数据库、日志、模型缓存、屏幕截图、音频备份和记忆原始材料都在
`runtime/` 下按规则忽略，不属于公开仓库内容。

## 协议

代码使用 Apache-2.0 协议。

项目名称、角色名称、角色形象、像素素材、图标、截图、语音设计、人格文案等
创意资产不随代码协议授权，除非具体文件另有明确说明。详情见 `BRANDING.md`。
