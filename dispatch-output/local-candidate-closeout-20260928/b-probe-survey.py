"""B 档探针选型勘察：解析候选环境实际存在的风险符号，并统计候选树源码的真实 import 面。

读数只用于确定「探针该桩哪些符号」，本身不构成可达性结论。
"""

from __future__ import annotations

import ast
import importlib
import json
import sys
from pathlib import Path

REPO = Path(r"C:/Users/33393/Desktop/ai-legal-helper")
EVIDENCE = REPO / "dispatch-output/local-candidate-closeout-20260928"
CANDIDATE = Path(r"C:/Users/33393/.codex/worktrees/local-candidate-closeout/ai-legal-helper")

PACKAGES = [
    "langchain",
    "langchain-core",
    "langchain-community",
    "langchain-openai",
    "langchain-chroma",
    "langchain-huggingface",
    "langsmith",
    "transformers",
    "sentence-transformers",
    "torch",
    "chromadb",
    "fastapi",
    "starlette",
    "pypdf",
    "pydantic",
]

# B 档三组风险 -> 需要桩住的候选符号（点号路径）。存在与否由本脚本实测，不预设。
GROUPS = {
    "G1_Core 反序列化与 prompt 模板注入": [
        "langchain_core.load.load",
        "langchain_core.load.loads",
        "langchain_core.load.dumps",
        "langchain_core.load.dump",
        "langchain_core.prompts.load_prompt",
        "langchain_core.prompts.PromptTemplate.from_template",
        "langchain_core.prompts.ChatPromptTemplate.from_messages",
        "langchain_core.messages.base.message_to_dict",
        "langchain.serializers.Serializable.loads",
    ],
    "G2_图片 token 计数（SSRF / DNS 重绑定）": [
        "langchain_openai.chat_models.base.get_num_tokens_from_messages",
        "langchain_openai.chat_models.base.ChatOpenAI.get_num_tokens_from_messages",
        "langchain_openai.chat_models.base.ChatOpenAI.get_num_tokens",
        "langchain_core.language_models.chat_models.BaseChatModel.get_num_tokens_from_messages",
        "langchain_core.language_models.base.BaseLanguageModel.get_num_tokens_from_messages",
        "langchain_core.language_models.base.LanguageModelLike.get_num_tokens_from_messages",
        "langchain_community.chat_models.utils.get_num_tokens_from_messages",
        "langchain_community.chat_models.openai.get_num_tokens_from_messages",
    ],
    "G3_Transformers 模型 config（代码执行）": [
        "transformers.PreTrainedModel.from_pretrained",
        "transformers.AutoModel.from_pretrained",
        "transformers.AutoConfig.from_pretrained",
        "transformers.PreTrainedTokenizerFast.from_pretrained",
        "transformers.modeling_utils.PreTrainedModel.from_pretrained",
        "transformers.configuration_utils.PretrainedConfig.from_pretrained",
        "sentence_transformers.SentenceTransformer",
        "sentence_transformers.SentenceTransformer._load_sbert_model",
    ],
    "G4_LangSmith 追踪与外部 prompt 源": [
        "langsmith.middleware.TracingMiddleware",
        "langsmith.client.Client",
        "langsmith.run_logs",
        "langchain_core.prompts.load_prompt",
        "langchain.chains.loading.load_chain",
    ],
}

# 只关心「这个带漏洞的模块有没有被 import 过」的项 —— 运行时由 import 监视器回答，不靠 grep。
MODULES_TO_WATCH = [
    "langchain_community.document_loaders.sitemap",
    "langchain_community.document_loaders.evernote",
    "langchain_community.document_loaders.docusaurus",
    "langchain_community.vectorstores.faiss",
    "langchain_community.chat_models.utils",
    "langchain.chains.graph_qa.cypher",
    "langchain.chains.graph_qa.graphql",
    "langchain_community.tools.azure_cognitive_search",
    "langchain_community.agent_toolkits.file_management",
    "langchain_core.load",
    "langchain_core.load.dump",
    "langchain_core.load.load",
    "langchain_core.prompts.loading",
    "langchain_openai.chat_models.tokenization",
    "langsmith.middleware",
    "langsmith.run_logs",
    "transformers.dynamic_module_utils",
    "sentence_transformers.SentenceTransformer",
    "pickle",
]

# 静态 import 面：候选树源码里实际出现的模块根，决定运行时探针「等谁被 import」。
IMPORT_ROOTS = {
    "langchain",
    "langchain_core",
    "langchain_community",
    "langchain_openai",
    "langchain_chroma",
    "langchain_huggingface",
    "langsmith",
    "transformers",
    "sentence_transformers",
    "torch",
    "chromadb",
    "pickle",
    "shutil",
    "subprocess",
    "urllib",
    "http",
    "requests",
    "socket",
}

# 静态符号命中：复核交接书 §6② 声称的「0 命中」，逐条给出文件与行号。
SYMBOL_PATTERNS = [
    "get_num_tokens",
    "load_prompt",
    "TracingMiddleware",
    "SitemapLoader",
    "FAISS",
    "GraphCypher",
    "EverNoteLoader",
    "pull_prompt",
    "save_pretrained",
    "LightGlue",
    "X-CLIP",
    "XCLIP",
    "LANGCHAIN_TRACING",
    "LANGSMITH",
    "from_pretrained",
    "load_default",
    "langchain_core.load",
    "Serializable",
    "pickle",
    "trust_remote_code",
]


def candidate_head() -> str:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(CANDIDATE), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return out.stdout.strip() or f"<rc={out.returncode} {out.stderr.strip()[:80]}>"
    except OSError as exc:
        return f"<git unavailable: {exc}>"


def package_versions() -> list[dict[str, str]]:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as pkg_version

    rows = []
    for name in PACKAGES:
        try:
            rows.append({"package": name, "version": pkg_version(name)})
        except PackageNotFoundError:
            rows.append({"package": name, "version": "<not installed>"})
    return rows


def resolve_symbol(dotted: str) -> dict[str, str]:
    """从最长模块前缀试到单段包名；区分「包导不进来」与「属性不存在」，别把仪器自身缺陷报成符号不存在。"""
    parts = dotted.split(".")
    failures: list[str] = []
    for cut in range(len(parts) - 1, 0, -1):
        mod = ".".join(parts[:cut])
        attrs = parts[cut:]
        try:
            obj: object = importlib.import_module(mod)
        except BaseException as exc:
            failures.append(f"cut={cut} import {mod} -> {type(exc).__name__}: {str(exc)[:120]}")
            continue
        ok = True
        for attr in attrs:
            try:
                obj = getattr(obj, attr)
            except (AttributeError, TypeError) as exc:
                failures.append(f"cut={cut} getattr {mod}.{attr} -> {type(exc).__name__}: {str(exc)[:120]}")
                ok = False
                break
        if ok:
            defining = getattr(obj, "__module__", mod)
            return {
                "symbol": dotted,
                "status": "EXISTS",
                "resolved_via": mod,
                "defining_module": str(defining),
                "kind": type(obj).__name__,
                "attempts": "; ".join(failures),
            }
    reason = "IMPORT_ERROR" if all("import " in f for f in failures) else "ATTRIBUTE_ABSENT"
    return {
        "symbol": dotted,
        "status": "ABSENT",
        "resolved_via": "",
        "defining_module": "",
        "kind": reason,
        "attempts": "; ".join(failures),
    }


def scan_tree(root: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    imports: list[dict[str, object]] = []
    seen_imports: set[tuple[str, int, str]] = set()
    hits: list[dict[str, object]] = []
    for py in sorted(root.rglob("*.py")):
        rel = py.relative_to(root).as_posix()
        try:
            src = py.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            src = py.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            imports.append({"file": rel, "lineno": 0, "module": f"<SyntaxError {exc}>", "kind": "parse-error"})
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in IMPORT_ROOTS:
                        key = (rel, node.lineno, alias.name)
                        if key not in seen_imports:
                            seen_imports.add(key)
                            imports.append({"file": rel, "lineno": node.lineno, "module": alias.name, "kind": "import"})
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                top = mod.split(".")[0]
                if top in IMPORT_ROOTS:
                    for alias in node.names:
                        key = (rel, node.lineno, f"{mod}.{alias.name}")
                        if key not in seen_imports:
                            seen_imports.add(key)
                            imports.append(
                                {
                                    "file": rel,
                                    "lineno": node.lineno,
                                    "module": f"{mod}.{alias.name}",
                                    "kind": "from-import",
                                }
                            )
        for pattern in SYMBOL_PATTERNS:
            for i, line in enumerate(src.splitlines(), start=1):
                if pattern in line:
                    hits.append({"file": rel, "lineno": i, "pattern": pattern, "text": line.strip()[:200]})
    return imports, hits


def main() -> int:
    backend = CANDIDATE / "backend"
    if not backend.is_dir():
        print(f"FATAL: candidate backend missing: {backend}", flush=True)
        return 2

    report: dict[str, object] = {
        "candidate_tree": str(CANDIDATE),
        "candidate_head": candidate_head(),
        "interpreter": sys.executable,
        "python": sys.version.split()[0],
        "packages": package_versions(),
        "modules_to_watch": MODULES_TO_WATCH,
    }

    print(f"candidate HEAD: {report['candidate_head']}")

    print(f"interpreter: {sys.executable}")
    print(f"python: {sys.version.split()[0]}")
    print("\n=== 候选环境包版本 ===")
    for row in report["packages"]:  # type: ignore[index]
        print(f"  {row['package']:26s} {row['version']}")  # type: ignore[typeddict-item]

    print("\n=== B 档目标符号在候选环境中是否存在 ===")
    symbols: list[dict[str, str]] = []
    for group, dotted_list in GROUPS.items():
        print(f"\n[{group}]")
        for dotted in dotted_list:
            row = resolve_symbol(dotted)
            row["group"] = group
            symbols.append(row)
            mark = "OK " if row["status"] == "EXISTS" else "-- "
            print(f"  {mark}{dotted:78s} {row['status']:7s} via={row['resolved_via']} def={row['defining_module']}")
            if row["status"] == "ABSENT":
                print(f"     {'':78s} reason={row['kind']}")
                print(f"     {'':78s} {row['attempts'][:400]}")
    report["symbols"] = symbols
    report["modules_to_watch"] = MODULES_TO_WATCH
    print(f"\n=== 交给运行时探针的 import 监视模块（{len(MODULES_TO_WATCH)} 个） ===")
    for mod in MODULES_TO_WATCH:
        print(f"  {mod}")

    imports, hits = scan_tree(backend)
    print(f"\n=== 候选树 backend 真实 import 面（{len(imports)} 条 from-import/import） ===")
    by_mod: dict[str, int] = {}
    for row in imports:
        top = str(row["module"]).split(".")[0]
        by_mod[top] = by_mod.get(top, 0) + 1
    for mod, cnt in sorted(by_mod.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {mod:26s} {cnt}")
    report["imports"] = imports

    app = [r for r in hits if not str(r["file"]).startswith("tests/") and not str(r["file"]).startswith("scripts/")]
    non_app = [r for r in hits if str(r["file"]).startswith("tests/") or str(r["file"]).startswith("scripts/")]
    print(f"\n=== 静态符号命中：应用侧 {len(app)} 条 / 测试与脚本侧 {len(non_app)} 条 ===")
    for row in app:
        print(f"  APP  {row['file']}:{row['lineno']} [{row['pattern']}] {row['text']}")
    for row in non_app[:40]:
        print(f"  T/S  {row['file']}:{row['lineno']} [{row['pattern']}] {row['text']}")
    if len(non_app) > 40:
        print(f"  ... 其余 {len(non_app) - 40} 条见 JSON")
    report["static_hits_app"] = app
    report["static_hits_tests_scripts"] = non_app

    out = EVIDENCE / "b-probe-survey.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(f"\njson -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
