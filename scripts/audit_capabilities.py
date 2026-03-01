#!/usr/bin/env python3
# scripts/audit_capabilities.py
#
# 能力审计工具
# ============
# 对比 CAPABILITIES_FALLBACK（人工维护）与 infer_capabilities()（自动推断）的结果，
# 输出差异报告，帮助人工判断 fallback 是否需要更新。
#
# 人工只需审阅报告中 "需关注" 的条目，决定是否修改 capabilities_fallback.py。
#
# 两种运行模式
# ------------
# 快速模式（默认）：仅凭模型名称推断，不联网，秒级完成。
#   python scripts/audit_capabilities.py
#
# 文档模式（推荐，需 CI 环境）：抓取各平台文档页，用页面文本辅助推断，结果更准确。
#   python scripts/audit_capabilities.py --fetch
#   USE_PLAYWRIGHT=1 python scripts/audit_capabilities.py --fetch  # 本地启用 Playwright
#
# 输出
# ----
# - 终端彩色报告
# - AUDIT_REPORT.md（可直接贴入 GitHub Actions Job Summary）

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# 让脚本在仓库根目录的子目录里也能 import scrapers/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.capabilities_fallback import (  # noqa: E402
    CAPABILITIES_FALLBACK,
    infer_capabilities,
)

# ---------------------------------------------------------------------------
# ANSI 颜色（终端输出用；CI 环境 TERM=dumb 时自动降级）
# ---------------------------------------------------------------------------
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


RED    = "31"
YELLOW = "33"
GREEN  = "32"
CYAN   = "36"
BOLD   = "1"

# ---------------------------------------------------------------------------
# 审计逻辑
# ---------------------------------------------------------------------------

ALL_CAPABILITIES: List[str] = [
    "text_generation", "translation", "transcription", "text_to_speech",
    "image_understanding", "image_generation", "document_processing",
    "code_generation", "embedding", "function_calling", "structured_output",
]


def _diff(fallback: List[str], inferred: List[str]) -> Tuple[Set[str], Set[str]]:
    """
    返回 (可能缺失的能力, 可能多余的能力)。
    - 可能缺失：inferred 有但 fallback 没有 → 文档暗示该模型新增了此能力
    - 可能多余：fallback 有但 inferred 没有 → 可能是过时数据或推断规则未覆盖
    """
    fb  = set(fallback)
    inf = set(inferred)
    possibly_missing = inf - fb   # inferred 建议加，但 fallback 没有
    possibly_extra   = fb - inf   # fallback 有，但 inferred 不认为应该有
    return possibly_missing, possibly_extra


def audit_provider(
    provider: str,
    doc_texts: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    审计单个平台所有模型，返回有差异的条目列表。
    每条记录：{model_id, fallback, inferred, missing, extra}
    """
    results = []
    models = CAPABILITIES_FALLBACK.get(provider, {})

    for model_id, fallback_caps in models.items():
        doc_text = doc_texts.get(model_id, "")
        inferred_caps = infer_capabilities(model_id, doc_text)

        missing, extra = _diff(fallback_caps, inferred_caps)

        # 过滤掉噪音：inferred 规则未覆盖的能力不算"多余"
        # 只关注 inferred 主动认为"不应该有"的情况（即规则明确排除）
        # 实际上 infer_capabilities 是加法逻辑，不会主动标记"不该有"
        # 因此 extra 仅供参考，missing 是更有价值的信号
        if missing or extra:
            results.append({
                "model_id": model_id,
                "fallback":  sorted(fallback_caps),
                "inferred":  sorted(inferred_caps),
                "missing":   sorted(missing),
                "extra":     sorted(extra),
            })

    return results


def fetch_doc_texts(provider: str) -> Dict[str, str]:
    """
    抓取文档页并提取每个已知模型的上下文文本。
    失败时返回空字典（降级为纯名称推断）。
    """
    from bs4 import BeautifulSoup  # noqa: PLC0415

    # 各平台文档 URL 和正则
    DOC_CONFIG = {
        "claude": {
            "url": "https://docs.anthropic.com/en/docs/about-claude/models/overview",
            "pattern": r"claude-(?:opus|sonnet|haiku|instant|claude)[-\d.a-z]+",
        },
        "gemini": {
            "url": "https://ai.google.dev/gemini-api/docs/models",
            "pattern": r"(?:gemini-[\d.]+[-\w]*|text-embedding-\d+|embedding-\d+|imagen-[\d.]+[-\w]*)",
        },
        "openai": {
            "url": "https://platform.openai.com/docs/models",
            "pattern": (
                r"(?:gpt-[\w.-]+|o\d[\w.-]*|whisper-\w+|tts-\w+|"
                r"dall-e[-\w]+|text-embedding-[\w-]+"
            ),
        },
    }

    cfg = DOC_CONFIG.get(provider)
    if not cfg:
        return {}

    # 使用 BaseScraper 的 fetch 基础设施
    from scrapers.base_scraper import BaseScraper  # noqa: PLC0415

    class _FetchOnly(BaseScraper):
        def scrape_pricing(self): return {}
        def scrape_models(self): return {}
        def build_provider_data(self): return {}

    fetcher = _FetchOnly()
    print(f"  → 抓取 {cfg['url']} …", end="", flush=True)
    html = fetcher.fetch(cfg["url"])
    if not html:
        print(" 失败，降级为名称推断")
        return {}
    print(f" OK ({len(html)//1024} KB)")

    soup = BeautifulSoup(html, "lxml")
    texts: Dict[str, str] = {}
    for model_id in CAPABILITIES_FALLBACK.get(provider, {}):
        texts[model_id] = fetcher.extract_doc_text_for_model(soup, model_id)

    return texts


# ---------------------------------------------------------------------------
# 报告生成
# ---------------------------------------------------------------------------

def _severity(missing: Set[str], extra: Set[str]) -> str:
    """简单的严重程度分级。"""
    if missing:
        return "⚠️  需关注"   # inferred 认为有但 fallback 没有 → 可能漏标
    if extra:
        return "ℹ️  仅供参考"  # fallback 有但 inferred 不认为有 → 规则未覆盖，不一定错
    return "✅  一致"


def print_report(all_results: Dict[str, List[Dict[str, Any]]], fetch_mode: bool) -> None:
    mode_label = "文档模式" if fetch_mode else "快速模式（仅名称推断）"
    print()
    print(_c(f"═══ 能力审计报告  [{mode_label}] ═══", BOLD))
    print(_c(f"时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", CYAN))
    print()

    total_diffs = sum(len(v) for v in all_results.values())
    if total_diffs == 0:
        print(_c("✅  所有模型能力与推断结果一致，无需更新。", GREEN))
        return

    for provider, results in all_results.items():
        if not results:
            print(_c(f"✅  {provider.upper()}：全部一致", GREEN))
            continue

        print(_c(f"── {provider.upper()} ──", BOLD))
        for r in results:
            sev = _severity(r["missing"], r["extra"])
            print(f"  {sev}  {_c(r['model_id'], CYAN)}")
            if r["missing"]:
                print(
                    f"      {_c('可能缺失', YELLOW)}（推断有，fallback 无）: "
                    + ", ".join(_c(c, YELLOW) for c in r["missing"])
                )
            if r["extra"]:
                print(
                    f"      {_c('仅供参考', CYAN)}（fallback 有，推断无）: "
                    + ", ".join(r["extra"])
                )
        print()

    print("─" * 60)
    total_models = sum(len(CAPABILITIES_FALLBACK.get(p, {})) for p in all_results)
    print(f"共审计 {total_models} 个模型，发现 {total_diffs} 个差异条目。")
    if not fetch_mode:
        print(_c("提示：使用 --fetch 模式可利用文档页文本提升推断准确率。", CYAN))


def write_markdown_report(
    all_results: Dict[str, List[Dict[str, Any]]],
    fetch_mode: bool,
    output_path: Path,
) -> None:
    """生成 Markdown 报告，适合贴入 GitHub Actions Job Summary。"""
    lines: List[str] = []
    mode_label = "文档模式" if fetch_mode else "快速模式（仅模型名称推断）"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines += [
        "# 能力审计报告",
        "",
        f"> 生成时间：{now}  |  运行模式：{mode_label}",
        "",
    ]

    total_diffs = sum(len(v) for v in all_results.values())

    if total_diffs == 0:
        lines += ["## ✅ 全部一致", "", "所有模型能力与自动推断结果一致，无需更新 `capabilities_fallback.py`。"]
    else:
        lines += [
            "## 差异摘要",
            "",
            "| 平台 | 有差异模型数 | 审计总数 |",
            "|---|---|---|",
        ]
        for provider, results in all_results.items():
            total = len(CAPABILITIES_FALLBACK.get(provider, {}))
            lines.append(f"| {provider} | {len(results)} | {total} |")

        lines += [""]

        for provider, results in all_results.items():
            if not results:
                lines += [f"### ✅ {provider.upper()}：全部一致", ""]
                continue

            lines += [f"### {provider.upper()}", ""]

            # 仅显示"需关注"（missing）的条目
            critical = [r for r in results if r["missing"]]
            info_only = [r for r in results if not r["missing"]]

            if critical:
                lines += ["#### ⚠️ 需关注（推断建议新增能力）", ""]
                lines += ["| 模型 | 建议新增能力 | 说明 |", "|---|---|---|"]
                for r in critical:
                    missing_str = ", ".join(f"`{c}`" for c in r["missing"])
                    lines.append(
                        f"| `{r['model_id']}` | {missing_str} | "
                        "fallback 未标注，推断认为应有 |"
                    )
                lines += [""]

            if info_only:
                lines += [
                    "<details>",
                    "<summary>ℹ️ 仅供参考（fallback 标注了推断未覆盖的能力）</summary>",
                    "",
                    "| 模型 | fallback 有、推断无 |",
                    "|---|---|",
                ]
                for r in info_only:
                    extra_str = ", ".join(f"`{c}`" for c in r["extra"])
                    lines.append(f"| `{r['model_id']}` | {extra_str} |")
                lines += ["", "</details>", ""]

        lines += [
            "---",
            "",
            "## 如何处理差异",
            "",
            "1. **⚠️ 需关注** — 编辑 `scrapers/capabilities_fallback.py`，",
            "   对照[官方文档](#)确认能力后手动补充对应字段。",
            "2. **ℹ️ 仅供参考** — 推断规则未覆盖并不代表能力错误，",
            "   人工核实后如确认正确可忽略；如确认过时可删除。",
            "3. **✅ 一致** — 无需操作。",
            "",
            "> 推断规则定义于 `scrapers/capabilities_fallback.py` 的 `_NAME_CAPABILITY_RULES`",
            "> 和 `_TEXT_CAPABILITY_RULES`，可持续优化以提升准确率。",
        ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n📄 Markdown 报告已写入：{output_path}")


# ---------------------------------------------------------------------------
# Exit code 逻辑
# ---------------------------------------------------------------------------

def compute_exit_code(all_results: Dict[str, List[Dict[str, Any]]]) -> int:
    """
    退出码：
      0 — 无差异或仅有"仅供参考"条目
      1 — 存在"需关注"（missing）条目（供 CI 选择性报警用）
    """
    for results in all_results.values():
        for r in results:
            if r["missing"]:
                return 1
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="对比 CAPABILITIES_FALLBACK 与 infer_capabilities() 的差异"
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="抓取各平台文档页以获取更准确的上下文文本（需要网络；CI 中建议开启）",
    )
    parser.add_argument(
        "--provider",
        choices=list(CAPABILITIES_FALLBACK.keys()),
        default=None,
        help="只审计指定平台（默认全部）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "AUDIT_REPORT.md",
        help="Markdown 报告输出路径（默认：仓库根目录/AUDIT_REPORT.md）",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="发现 '需关注' 差异时以非零退出码退出（可用于 CI 强制检查）",
    )
    args = parser.parse_args()

    providers = [args.provider] if args.provider else list(CAPABILITIES_FALLBACK.keys())
    all_results: Dict[str, List[Dict[str, Any]]] = {}

    for provider in providers:
        print(f"\n[{provider.upper()}] 开始审计 "
              f"({len(CAPABILITIES_FALLBACK.get(provider, {}))} 个模型)…")

        doc_texts: Dict[str, str] = {}
        if args.fetch:
            doc_texts = fetch_doc_texts(provider)

        all_results[provider] = audit_provider(provider, doc_texts)

    # 终端输出
    print_report(all_results, args.fetch)

    # Markdown 报告
    write_markdown_report(all_results, args.fetch, args.output)

    # 退出码
    exit_code = compute_exit_code(all_results)
    if args.fail_on_diff and exit_code != 0:
        print("\n⚠️  发现需关注差异，以退出码 1 退出（--fail-on-diff 已启用）")
        sys.exit(1)


if __name__ == "__main__":
    main()
