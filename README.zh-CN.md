# Jev Ultrafast Portfolio

[![CI](https://github.com/winniw111/jev-ultrafast-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/winniw111/jev-ultrafast-portfolio/actions/workflows/ci.yml)

这是一个面向浏览器智能体方向的求职项目。智能体接收自然语言目标，把当前页面转换成带编号的可操作元素，再在一次模型请求中同时预测“操作类型”和该操作对应的目标，最后由受约束的执行器完成点击、输入、选择、滚动或等待。

演示视频与原始性能数据见 [docs/demo.mp4](docs/demo.mp4) 和 [docs/performance.md](docs/performance.md)。

## 项目来源与个人贡献

本仓库基于 Browser Use 团队以 MIT 许可证开源的 [browser-use/jev-ultrafast](https://github.com/browser-use/jev-ultrafast)。核心智能体、浏览器执行器及原始性能实验来自上游项目，仓库保留了原许可证和上游地址。

在此基础上，我完成了以下可独立核验的改进：

- 修复中文 Windows 环境下按 GBK 读取 UTF-8 JavaScript 文件导致程序无法启动的问题；
- 新增 `jev-report` 离线分析命令，可将运行轨迹或多轮基准数据汇总为 Markdown、JSON 或自包含 HTML 可视化页面；
- 增加报告模块的单元测试，当前项目共有 34 项离线测试；
- 增加 GitHub Actions，自动执行 Python 检查、离线测试、JavaScript 语法检查和打包；
- 补充中文说明、Windows 运行方式与适合面试讲解的架构说明。

## 核心设计

```text
自然语言目标
    ↓
页面快照 → 可见控件表 → 操作头 + 操作专属目标头（一次模型请求）
                                      ↓
                              受约束的浏览器执行器
                                      ↓
                         新页面状态、轨迹与独立结果校验
```

关键边界是“模型负责选择，代码负责执行”。模型不能生成 CSS 选择器、坐标、Shell 命令或可执行 JavaScript；执行目标必须来自刚刚观察到的 DOM 节点。页面变化后，旧决策会被判定为过期，浏览器写操作也不会盲目重试。

| 模块 | 作用 |
| --- | --- |
| `jev_ultrafast/agent.py` | 决策—执行—重新观察的主循环 |
| `jev_ultrafast/snapshot.js` | 原子化读取可见控件与页面状态 |
| `jev_ultrafast/browser.py` | Chrome 连接、页面新鲜度检查和动作执行 |
| `jev_ultrafast/model.py` | 动态操作空间、目标选择和文本生成 |
| `jev_ultrafast/report.py` | 离线轨迹统计与 Markdown/JSON 报告 |
| `tests/` | 不调用付费 API 的安全与行为契约测试 |

## 快速开始

需要 Python 3.12、[uv](https://docs.astral.sh/uv/) 和 Chrome。

```powershell
git clone https://github.com/winniw111/jev-ultrafast-portfolio.git
cd jev-ultrafast-portfolio
uv sync
Copy-Item .env.example .env
```

在 `.env` 中填写 `TYPESAFE_API_KEY` 与 `TEXT_MODEL_API_KEY`，再运行：

```powershell
uv run browser-harness --doctor
uv run jev
```

访问 `http://127.0.0.1:8766` 即可使用本地检查器。Windows 下不需要执行 `.venv\Scripts\Activate.ps1`，直接使用 `uv run ...` 可以避开 PowerShell 执行策略限制。

## 不使用 API 的离线验证

安装依赖后可以直接运行全部测试：

```powershell
uv run ruff check .
uv run pytest
uv build
```

也可以对仓库内已有实验数据生成报告，不需要密钥或浏览器：

```powershell
uv run jev-report docs/flights-measurement.json
uv run jev-report docs/full-speed-measurement.json --format json
uv run jev-report artifacts/my-run/state.json -o artifacts/my-run/report.md
uv run jev-report docs/flights-measurement.json --format html -o report.html
```

报告会给出任务耗时、浏览器动作数、决策请求数、中位决策延迟、文本模型调用成本、操作分布和独立校验结果。HTML 版本不加载远程字体、脚本或样式，双击文件即可离线展示。示例见 [docs/sample-report.md](docs/sample-report.md) 和 [docs/sample-report.html](docs/sample-report.html)。

## 面试时可以重点讲什么

1. 动态动作空间如何把开放式网页操作收敛为受约束选择题；
2. 为什么操作与目标在一次请求中并行预测，却只消费被选中操作对应的目标；
3. 如何通过页面指纹、新鲜度检查和“一次性消费决策”避免重复点击；
4. 为什么智能体宣称 `DONE` 后仍要进行独立结果校验；
5. 如何用离线测试和轨迹报告降低真实模型调用的调试成本。

## 当前限制

这是一个 MVP，不代表通用网页自动化已经解决。当前 DOM 读取器尚未完整覆盖 iframe、Shadow DOM、Canvas、上传控件、多标签弹窗和任意自定义键盘组件；实时示例还需要第三方模型密钥。性能数据来自有限任务和浏览器环境，应视为可复现实验记录，而不是普适基准。

## 后续计划

- 增加无需密钥的本地回放模式；
- 为 HTML 报告增加动作时间线和筛选交互；
- 增加更多网站与失败场景的回归用例；
- 对比不同模型在成功率、延迟和成本上的表现。

英文原始说明请参阅 [README.md](README.md)。
