# llm-freewatch（中文说明）

**在你的 Agent 踩坑之前，先知道今天哪些免费大模型 API 还能用。**

免费额度一直在变：模型上下架、限额悄悄调整、整个项目直接关停（GitHub Models
已于 2026-07-30 退役，老文章还在推荐它）。把“免费模型 ID”写死在代码里，
迟早静默翻车。

llm-freewatch 是一个零依赖的 Python 小工具，专门盯免费额度这件事：

- **实时雷达**：拉 OpenRouter 实时目录，列出当下真正 $0（输入+输出都免费）的
  模型，带上下文长度和是否支持工具调用；
- **变化对比**：每次扫描和上一次自动 diff，新增/下架了哪些免费模型一目了然；
- **故障转移链**：一键生成有序的免费模型回退链（JSON 或 LiteLLM 配置），
  某个模型 429/404 时按顺序往下走；
- **真实探活**（可选）：用你自己的 Key（只读环境变量、绝不落盘）发一次真实的
  工具调用，结果分 ok / hard / transient 三类——429 只报“暂时性”，不当结论；
- **人工核验的服务商表**：没有公开目录 API 的服务商（Groq、Gemini、NVIDIA NIM、
  Mistral、Cloudflare、Cohere）用人工核验表，每行都带来源链接和核验日期，
  包括要不要绑卡、是否拿免费数据训练这些“坑”，绝不冒充实时数据；
- **MCP 服务器**：Claude Code / Codex / Cursor 等 Agent 干活中途就能问
  “现在有哪些免费模型能用”，不用再靠猜；
- **配套 Skill**：仓库带 `skill/SKILL.md`，教 Agent 在写死模型 ID 之前先查雷达。

为什么做这个：作者自己用免费模型跑个人编程 Agent，免费阵容轮换太频繁，
被迫每天跑一次雷达做对比——这套东西就是那个日常流程的开源版。

## 快速开始

```bash
python3 -m llm_freewatch scan --tools   # 现在免费且支持工具调用的模型
python3 -m llm_freewatch providers      # 各服务商免费额度、限额和坑
python3 -m llm_freewatch chain          # 生成回退链
```

诚实边界：目前只有 OpenRouter 是实时拉取；其余是带日期的人工核验快照，
会过期，欢迎提 PR 更新（更新时必须同时更新来源和核验日期）。

许可证：MIT
