"""批量导入条文（阶段5）：读 data/laws_extra.json，校验后幂等入库。

- 模板见 data/laws_extra.example.json（复制为 data/laws_extra.json 后填写）。
- --validate-only 校验整个输入文件，不连接知识库或加载嵌入模型。
- --dry-run 还会读取知识库，预览现有版本的替换与种子冲突。
- 版本化幂等：有明确生效日且同法名、条号的重传替换；时效不重叠的历史版本并存；库内或批内区间重叠、不明时整批阻断；与 origin=seed 种子重叠时警告并跳过
  （那种内容应改 data/laws.json 后运行 knowledge_base.py 重建）。
- origin 固定为 "import"（区别于 seed/manual/upload，管理端可显示第三态徽章）。

用法：cd backend && python scripts/import_laws.py [--input 路径] [--validate-only | --dry-run]

三段闸（B-45）：①`CHROMA_DIR` 与固定目标分歧 ⇒ CLI 入口即拒绝（读写之前）；②`--validate-only`
只校验输入文件，不连接知识库、不加载嵌入模型；③`--dry-run` 读库预览但**不写**——注意它仍然读库，
别把 `--dry-run` 当"不碰库"。默认（两个开关都不带）就是实写生产索引。
"""

import argparse
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from law_versions import ReplacementPlan, replaceable_version_ids, version_metadata  # noqa: E402
from retrieval_core import STATUS_WHITELIST  # noqa: E402
from scripts import chroma_dir_guard  # noqa: E402

DEFAULT_INPUT = os.path.join(BACKEND, "..", "data", "laws_extra.json")
# 本脚本的固定目标：它会**实写**生产索引（默认无 --dry-run，并按 file_hash 替换已有 chunk）。
PROD_CHROMA_DIR = os.path.join(BACKEND, "chroma_db")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED = ("title", "article_number", "content")
# 占位符拦截：防止「忘了替换原文」就导入（新手流程保护）
_PLACEHOLDER_RE = re.compile(r"请粘贴|条文原文，一字不差|【[^】]*原文[^】]*】|（条文原文|请替换|示例法律名称")

# 预检分类各自的措辞（T2）。⚠️ 行**只报数量与法名条号**，不抄旧块正文 —— 那是 10266 条
# 语料的库，逐条打印正文会把预检输出变成几十兆的噪音，而且复制粘贴反而会诱导人"看着像就放过"。
LINE_REPLACE = "  将替换 {n} 旧片段 + 新增：{title} {article}"
LINE_LEGACY = "  ⚠️ 与 {n} 条无时效旧块并存（将被 T1 取代）：{title} {article}"
LINE_HISTORICAL = "  保留 {n} 条不重叠历史版本：{title} {article}"
LINE_COEXIST = "  ✗ 与 {n} 条旧块存在未判定冲突（时效重叠或不明，或正文无法安全匹配，需人工判）：{title} {article}"


def preflight_lines(title: str, article: str, plan: ReplacementPlan) -> list[str]:
    """一条 entry 的预检输出；只消费分类结果，空类不输出。

    判据只有一份（`law_versions.replaceable_version_ids`），这里只负责说出来；
    本函数不许再判一次 `effective_from`/`version_id` 空不空（票 T2 判据 4）。
    """
    lines = [LINE_REPLACE.format(n=len(plan.replaceable), title=title, article=article)]
    if plan.legacy_undated:
        lines.append(LINE_LEGACY.format(n=len(plan.legacy_undated), title=title, article=article))
    if plan.compatible_versions:
        lines.append(LINE_HISTORICAL.format(n=len(plan.compatible_versions), title=title, article=article))
    if plan.conflicts:
        lines.append(LINE_COEXIST.format(n=len(plan.conflicts), title=title, article=article))
    return lines


def _text_field(entry: dict, key: str, errors: list[str]) -> str:
    value = entry.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        errors.append(f"{key} 必须是字符串")
        return ""
    return value.strip()


def validate_entry(e: dict) -> list[str]:
    if not isinstance(e, dict):
        return ["条目必须是对象"]
    errors: list[str] = []
    required = {k: _text_field(e, k, errors) for k in _REQUIRED}
    for k in _REQUIRED:
        if not required[k]:
            errors.append(f"缺少必填字段 {k}")
    content, title = required["content"], required["title"]
    if _PLACEHOLDER_RE.search(content) or _PLACEHOLDER_RE.search(title):
        errors.append("content/title 仍为占位符，请粘贴真实条文原文")
    status = _text_field(e, "status", errors)
    if not status:
        errors.append("status 必填：省略不等于「现行」，无人核过就写 未验证")
    elif status not in STATUS_WHITELIST:
        errors.append(f"status 必须是 {'/'.join(STATUS_WHITELIST)}，当前为 {status!r}")
    dates = {}
    for k in ("promulgated_at", "effective_from", "effective_to", "reviewed_at"):
        v = dates[k] = _text_field(e, k, errors)
        if v:
            try:
                if not _DATE_RE.fullmatch(v) or date.fromisoformat(v).isoformat() != v:
                    raise ValueError
            except ValueError:
                errors.append(f"{k} 必须是真实有效的 YYYY-MM-DD 日期（当前 {v!r}）")
    effective_from, effective_to = dates["effective_from"], dates["effective_to"]
    if effective_from and effective_to and effective_to < effective_from:
        errors.append("effective_to 不能早于 effective_from")
    if status in {"已修改", "已废止"} and not effective_to:
        errors.append(f"status={status} 时 effective_to 必填")
    if status in {"即将施行", "未生效"} and not effective_from:
        errors.append(f"status={status} 时 effective_from 必填")
    source_hash = _text_field(e, "source_document_sha256", errors)
    if source_hash and not re.fullmatch(r"[0-9a-f]{64}", source_hash):
        errors.append("source_document_sha256 必须为 64 位小写十六进制")
    source_url = _text_field(e, "source_url", errors)
    if source_url and not re.match(r"^https://[^\s]+$", source_url):
        errors.append("source_url 必须为 HTTPS URL")
    for k in ("category", "version_id", "supersedes_version_id"):
        _text_field(e, k, errors)
    return errors


def _load_entries(path: str) -> list:
    with open(path, encoding="utf-8") as source:
        data = json.load(source)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("entries"), list):
        return data["entries"]
    raise ValueError("文件格式错误：应为条文数组，或含 entries 数组的对象（见模板）")


def _seed_conflict(vectorstore, title: str, article: str) -> bool:
    """只认 `origin=="seed"` 的冲突 —— ⚠️ **今天对现网是死码**（E7 实测：该集合 10266 条 origin 全
    `upload`、`seed` 0 条 ⇒ 本函数恒 False）。它管的是"种子重建会覆盖 import 版本"那一类，
    **不是**"新旧条文重叠会不会被拦下"：后者从 T2 起由 `preflight_lines` 的并存报警负责。
    语义按票面保留不动；这段说明是为了别让下一个人把它当重叠防线（票 T2 §现象）。
    """
    # 存在 seed 即视为冲突（重建会覆盖 import 版本）
    matches = vectorstore._collection.get(
        where={"$and": [{"source": title}, {"article": article}]},
        include=["metadatas"],
    )
    return any(meta and meta.get("origin") == "seed" for meta in matches["metadatas"] or [])


def main():
    ap = argparse.ArgumentParser(description="批量导入法律条文（幂等）")
    ap.add_argument("--input", default=DEFAULT_INPUT, help="条文 JSON 路径（默认 data/laws_extra.json）")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true", help="只校验输入文件，不加载模型或连接知识库")
    mode.add_argument("--dry-run", action="store_true", help="读取知识库预览替换，不写入")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        print(f"未找到导入文件 {args.input}\n请复制 data/laws_extra.example.json 为 data/laws_extra.json 后填写。")
        sys.exit(1)

    try:
        entries = _load_entries(args.input)
    except (OSError, ValueError) as exc:
        print(f"读取导入文件失败：{exc}")
        sys.exit(1)
    if not entries:
        print("导入文件 entries 为空；未写入任何内容")
        sys.exit(1)
    all_errors = [(e, validate_entry(e)) for e in entries]
    bad = [(e, errs) for e, errs in all_errors if errs]
    if bad:
        print(f"共 {len(bad)} 条校验失败（不写入任何内容）：")
        for e, errs in bad:
            name = f"{e.get('title', '?')} {e.get('article_number', '?')}" if isinstance(e, dict) else "非对象条目"
            print(f"  [{name}] {'; '.join(errs)}")
        sys.exit(1)

    if args.validate_only:
        print(f"文件校验通过：{len(entries)} 条；未连接知识库")
        return

    import knowledge_service as ks  # noqa: PLC0415
    from rag_chain import vectorstore  # noqa: PLC0415

    print(f"共 {len(entries)} 条，开始{'预检' if args.dry_run else '导入'}：")
    # 两趟：**先全量判定并播报，再决定写不写**。判据 3 要的是"互不包含 ⇒ rc=1 且不写入任何内容"，
    # 边判边写做不到这一点（前几条已经落库了才发现第三条并存 ⇒ 只能回滚）。
    n_del = n_add = n_skip = n_legacy = 0
    blocked: list[str] = []
    pending: list[tuple[dict, dict]] = []
    seen_in_batch: dict[tuple[str, str], list[tuple[dict, str]]] = {}
    for e in entries:
        title, article = e["title"].strip(), e["article_number"].strip()
        if _seed_conflict(vectorstore, title, article):
            print(f"  跳过（与种子冲突，请改 laws.json 后重建）：{title} {article}")
            n_skip += 1
            continue
        extra = {
            "category": e.get("category", ""),
            **version_metadata(e, title=title, article=article, content=e["content"]),
        }
        existing = vectorstore._collection.get(
            where={"$and": [{"source": title}, {"article": article}]},
            include=["metadatas", "documents"],  # T1：判"遗留无时效块可否被取代"要看旧正文
        )
        plan = replaceable_version_ids(
            existing["ids"],
            existing.get("metadatas") or [],
            version_id=extra["version_id"],
            effective_from=extra["effective_from"],
            effective_to=extra["effective_to"],
            documents=existing.get("documents") or [],
            new_content=e["content"],
        )
        for line in preflight_lines(title, article, plan):
            print(line)
        n_del += len(plan.replaceable)
        n_legacy += len(plan.legacy_undated)
        n_add += 1
        if plan.conflicts:
            blocked.append(f"{title} {article}（{len(plan.conflicts)} 条）")
        prior = seen_in_batch.setdefault((title, article), [])
        if prior:
            batch_plan = replaceable_version_ids(
                [str(i) for i in range(len(prior))],
                [
                    {
                        "origin": "import",
                        "article": article,
                        "version_id": meta["version_id"],
                        "effective_from": meta["effective_from"],
                        "effective_to": meta["effective_to"],
                    }
                    for meta, _ in prior
                ],
                version_id=extra["version_id"],
                effective_from=extra["effective_from"],
                effective_to=extra["effective_to"],
                documents=[content for _, content in prior],
                new_content=e["content"],
            )
            if batch_plan.replaceable or batch_plan.conflicts:
                print(f"  ✗ 本批同法同条版本重复或时效冲突：{title} {article}")
                blocked.append(f"{title} {article}（本批重复或冲突）")
        prior.append((extra, e["content"]))
        pending.append((e, extra))

    if blocked:
        # 脚本无权替法务在两个不同版本里选一个删 ⇒ 整批不写入，交人工判（Owner 已裁的 rc 分档）。
        print(f"\n预检不通过：{len(blocked)} 处现有库或本批输入冲突，整批未写入任何内容：")
        for b in blocked:
            print(f"  - {b}")
        sys.exit(1)

    if args.dry_run:
        print(
            f"\n预检完成：将删除 {n_del} 旧片段（其中 {n_legacy} 条是**无时效遗留块**），"
            f"新增 {n_add} 条，跳过 {n_skip} 条。确认后去掉 --dry-run 实跑。"
        )
        return
    for e, extra in pending:
        title, article = e["title"].strip(), e["article_number"].strip()
        # 同版本旧片段删除由 add_text(origin="import") 在新片段写入成功后处理。
        n = ks.add_text(e["content"], source=title, article=article, origin="import", extra_meta=extra)
        print(f"  已导入：{title} {article}（{n} 片段）")
    print(f"\n导入完成：替换 {n_del} 旧片段，新增 {n_add} 条，跳过 {n_skip} 条。")


def _check_env_contract() -> None:
    """CLI 前置守卫（B-45）：`CHROMA_DIR` 与本脚本固定目标分歧时拒绝跑。

    为什么 import_laws 需要它：它经 `rag_chain.vectorstore` 写入，而那个目录是**环境变量出口**
    （`rag_chain.py:127`）——运维为了换嵌入/迁库导出过 `CHROMA_DIR` 之后，"我以为在往生产索引导入"
    和"实际写进了另一个目录"会同时成立，且脚本照常打印"导入完成"。同族的 `backup_data`/
    `rebuild_embeddings` 早就被这把锁检查过，本脚本是三类可改写生产索引的动作里唯一没被检查的。

    位置是硬约束（判例见 `chroma_dir_guard` 模块 docstring）：只在 `__main__` 路径上调，
    **不能进 `main()`、更不能在 import 期调** —— `tests/conftest.py` 无条件把 `CHROMA_DIR`
    指向进程临时库，而 `test_import_laws_preflight.py` 是直接 `monkeypatch sys.argv` 后调
    `main()` 的，守卫一旦进 `main()` 就把它们钉红。
    """
    chroma_dir_guard.assert_matches(PROD_CHROMA_DIR, "import_laws")


if __name__ == "__main__":
    # `--validate-only` 不套守卫，是判据推出来的例外而不是为了让测试过：那条模式在 `main()` 里
    # 早于 `import knowledge_service / rag_chain` 就在 `if args.validate_only:` 分支 return，
    # **结构上不可能写库**
    # ⇒ 没有需要保护的动作；而 `test_import_laws_validation.py` 正靠"把 CHROMA_DIR 指到一只不存在的
    # 目录"来证明 validate-only 不碰库，拦它等于守卫自己把测试钉红。
    # 已知粗糙处：按字符串查 argv，argparse 的前缀缩写（`--validate`）会落到"守卫跑"那一侧
    # ⇒ 偏保守（该放行的被拒），不会把该拦的放走。
    if "--validate-only" not in sys.argv:
        _check_env_contract()
    main()
