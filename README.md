# Y_Chat

Y_Chat 是一个本地运行的智能桌宠项目。它的目标不是做一个网页聊天框，
而是在桌面上运行一个可以被事件驱动、能显示状态和气泡、未来可以接入
记忆、语音、视觉和外部软件交互的桌面伙伴。

项目还在早期开发阶段。目前仓库更像是一个可以运行的工程骨架，而不是完整
产品。

## 现在能做什么

- 启动 Electron 桌面壳。
- 显示透明桌宠窗口。
- 用 Canvas 渲染一个像素风桌宠占位形象。
- 在桌宠旁显示事件触发的像素风漫画气泡。
- 打开命令输入窗口并把输入发送到后端。
- 运行 Python FastAPI 后端。
- 通过 Debug 窗口查看状态、事件、日志、权限、模型配置、记忆和推理记录。
- 使用确定性 fallback 推理链路，不调用真实模型。

## 现在还不能做什么

这些能力已经在架构中预留，但默认没有启用：

- 真实 AI 回复。
- 自动长期记忆写入。
- 屏幕视觉感知。
- 语音输入和语音输出。
- VR 输出。
- 外部网络、LAN、OSC 等适配器。
- 文件写入、进程运行、输入控制等高风险动作。

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

如果你的 Python 环境名不是 `y_chat`，可以设置：

```powershell
$env:Y_CHAT_CONDA_ENV = "你的环境名"
```

也可以复制 `runtime/dev.local.example.ps1` 为 `runtime/dev.local.ps1`，
把自己的本机环境名写进去。这个文件不会提交到 git。

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

## 本地配置

`runtime/config.yaml` 是本机私有配置文件，不会提交到 git。它以后可能包含
API key、本地路径、私有桌宠代号等信息。

新环境可以从这个模板开始：

```text
runtime/config.example.yaml
```

## 当前状态

当前阶段是：

```text
Stage 1: runnable shell
```

也就是先把桌面窗口、事件链路、Debug 可视化、本地配置和后端骨架跑通。
真实模型、自动记忆、视觉、语音、外部动作等能力会在后续阶段逐步接入。

## 协议

代码使用 Apache-2.0 协议。

项目名称、角色名、角色形象、像素素材、图标、截图、语音设计、人格文案等
创意资产不随代码协议授权，除非某个文件明确说明可以使用。详情见
`BRANDING.md`。

## 说明

这个项目仍在快速变化。公开仓库主要用于记录当前工程进度和开放代码结构，
不是一个已经完成的桌宠产品。
