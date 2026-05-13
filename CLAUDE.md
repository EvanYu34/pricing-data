# pricing-data — Claude Code 工作指南

## 一句话

每周自动抓取 Claude / Gemini / OpenAI 模型定价 + 能力，合并写入 `pricing.json`，供下游客户端通过 `raw.githubusercontent.com` HTTP 拉取。

## 技术栈

- Python 3.11+
- 抓取：`requests` + `beautifulsoup4` + `lxml`；动态页用 `playwright` (chromium)
- 主数据源：[litellm 模型目录](https://github.com/BerriAI/litellm)（便宜、覆盖广）
- 抓取作为兜底（覆盖率不够时 fallback 到 `scrapers/capabilities_fallback.py` 硬编码值）
- 部署：纯数据 repo，无服务器；GitHub Actions 周更 → 客户端 HTTP 拉取

## 常用命令

```bash
# 一次性环境准备
pip install -r requirements.txt
pip install -r requirements-dev.txt          # 仅本地开发需要（pytest）
python -m playwright install chromium        # 仅本地使用 Playwright 时

# 跑全部 provider（默认）
python main.py

# 跑单个 provider
python main.py --provider claude
python main.py --provider gemini
python main.py --provider openai

# 本地启用 Playwright（CI 自动开）
USE_PLAYWRIGHT=1 python main.py

# 跑测试
pytest -q                                     # 6 个测试文件
pytest --cov=. --cov-report=term-missing      # 带覆盖率

# 模拟 drift_check（不会真写 pricing.json）
DRY_RUN=true python main.py

# 审计失败时强制提交（应急）
FORCE_COMMIT=true python main.py
```

## 关键文件

- `main.py` — 编排：litellm fetch → scrapers → field-level merge → audit → 门控写入
- `scrapers/litellm_source.py` — litellm 目录拉取与规范化
- `scrapers/{claude,gemini,openai}_scraper.py` — 各家定价页面抓取（兜底用）
- `scrapers/capabilities_fallback.py` — 硬编码能力/上下文窗口/endpoint 数据
- `scripts/audit_pricing.py` — 审计：覆盖率、上游 fetch 状态、价格交叉验证（>5% 分歧报警）
- `utils/json_merger.py` — 字段级合并，保留旧字段不被空值覆盖
- `pricing.json` — 输出产物，**这是用户实际消费的文件**
- `.github/workflows/update_pricing.yml` — 每周一 UTC 00:00 自动跑
- `.github/workflows/drift_check.yml` — 每日 UTC 03:00 DRY_RUN 巡检，失败时去重开 issue

## 已知约束 / 坑

- **`pricing.json` 是对外契约**：webapp/客户端会读取它的字段名。改 schema 前必须确认下游消费者（目前已知：`personal-stack-shared/wrapper_client` 可能读取定价）。
- **`requirements-dev.txt` 在 CI 不装**：CI 靠 `audit_pricing.py` 兜底，不跑 pytest。本地开发才装 pytest。
- **audit 失败默认回滚**：`main.py` 写完 `pricing.json` 后跑 audit，若失败且非 `FORCE_COMMIT`，自动还原。`drift_check` 用 `DRY_RUN=true` 走相同审计但永远不写。
- **`.commit_message` 和 `AUDIT_REPORT.md` 是运行时产物**：都在 `.gitignore`，本地跑会出现在工作目录但不会被提交。CI 用它们生成提交信息和 job summary。
- **GitHub Actions runner 装了 `gh`**：drift_check workflow 用 `gh` 去重开 issue。本地没有 `gh` 不影响 main.py。

## 部署 / 发布

- 没有服务器部署。`pricing.json` 通过 `git push` 进 `main` 后，客户端从这里拉：
  ```
  https://raw.githubusercontent.com/EvanYu34/pricing-data/main/pricing.json
  ```
- 周更由 `update_pricing.yml` 自动完成；不需要人工 release。

## 项目特定信任分级

> 在 `C:\Users\admin\Documents\Projects\CLAUDE.md` 的通用分级基础上补充。

### 🟢 自动档（我直接做、合并）
- 修单个 scraper 的解析 bug + 加对应测试
- 升级 patch/minor 依赖（CI 全绿）
- 改 `scrapers/capabilities_fallback.py` 里的硬编码值（添新模型、修上下文窗口）
- 优化日志、错误信息措辞
- 改文档（README / CLAUDE.md）

### 🟡 同步档（开 PR 等用户 approve）
- 改 `pricing.json` 的 schema（增删字段、改字段类型）—— **下游消费者会受影响**
- 新增 provider scraper（schema 扩展）
- 改 `scripts/audit_pricing.py` 的告警阈值或规则
- 改 `utils/json_merger.py` 的合并语义
- 改 workflow cron 表达式或 trigger 行为
- 升级依赖大版本

### 🔴 阻塞档（动手前必须问用户）
- 删除 `pricing.json` 中已有的 model 条目（即使上游下线了，也要确认 downstream）
- 改变 raw URL 的稳定性（重命名仓库、改 default branch 等）
- 删除或重写 git 历史

## 评审简化

每次 PR body 里我会附 `/review` 自检结论。对这个项目特别要看的点：
- pricing.json 的 schema 是否真的改了（用 `git diff main -- pricing.json | head -50` 看）
- 新加的 scraper / parser 是否有覆盖测试
- CI workflow 改动是否会影响周更稳定性
