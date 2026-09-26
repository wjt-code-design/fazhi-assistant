"""批量导入条文（阶段5）：读 data/laws_extra.json，校验后幂等入库。

- 模板见 data/laws_extra.example.json（复制为 data/laws_extra.json 后填写）。
- --validate-only 校验整个输入文件，不连接知识库或加载嵌入模型。
- --dry-run 还会读取知识库，预览现有版本的替换与种子冲突。
- 版本化幂等：同法名、条号、生效日替换；不同生效日并存；与 origin=seed 种子重叠时警告并跳过
  （那种内容应改 data/laws.json 后运行 knowledge_base.py 重建）。
- origin 固定为 "import"（区别于 seed/manual/upload，管理端可显示第三态徽章）。

用法：cd backend && python scripts/import_laws.py [--input 路径] [--validate-only | --dry-run]
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

DEFAULT_INPUT = os.path.join(BACKEND, "..", "data", "laws_extra.json")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_REQUIRED = ("title", "article_number", "content")
# 占位符拦截：防止「忘了替换原文」就导入（新手流程保护）
_PLACEHOLDER_RE = re.compile(r"请粘贴|条文原文，一字不差|【[^】]*原文[^】]*】|（条文原文|请替换|示例法律名称")

# 预检播报的三个桶各自的措辞（T2）。⚠️ 行**只报数量与法名条号**，不抄旧块正文 —— 那是 10266 条
# 语料的库，逐条打印正文会把预检输出变成几十兆的噪音，而且复制粘贴反而会诱导人"看着像就放过"。
LINE_REPLACE = "  将替换 {n} 旧片段 + 新增：{title} {article}"
LINE_LEGACY = "  ⚠️ 与 {n} 条无时效旧块并存（将被 T1 取代）：{title} {article}"
LINE_COEXIST = "  ✗ 与 {n} 条旧块互不包含（库里是同一条文的另一套文字，需人工判）：{title} {article}"


def preflight_lines(title: str, article: str, plan: ReplacementPlan) -> list[str]:
    """一条 entry 在预检里要说的那几行 —— **纯函数**，三个桶各一行，空桶不吭声。

    判据只有一份（`law_versions.replaceable_version_ids` 的桶），这里只负责说出来；
    本函数不许再判一次 `effective_from`/`version_id` 空不空（票 T2 判据 4）。
    """
    lines = [LINE_REPLACE.format(n=len(plan.replaceable), title=title, article=article)]
    if plan.legacy_undated:
        lines.append(LINE_LEGACY.format(n=len(plan.legacy_undated), title=title, article=article))
    if plan.coexist:
        lines.append(LINE_COEXIST.format(n=len(plan.coexist), title=title, article=article))
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
    errors = []
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
    ids = vectorstore._collection.get(where={"$and": [{"source": title}, {"article": article}]}, include=["metadatas"])[
        "ids"
    ]
    if not ids:
        return False
    # 存在 seed 即视为冲突（重建会覆盖 import 版本）
    metas = vectorstore._collection.get(ids=ids[:1], include=["metadatas"])["metadatas"] or []
    return bool(metas) and metas[0].get("origin") == "seed"


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
            documents=existing.get("documents") or [],
            new_content=e["content"],
        )
        for line in preflight_lines(title, article, plan):
            print(line)
        n_del += len(plan.replaceable)
        n_legacy += len(plan.legacy_undated)
        n_add += 1
        if plan.coexist:
            blocked.append(f"{title} {article}（{len(plan.coexist)} 条）")
        pending.append((e, extra))

    if blocked:
        # 脚本无权替法务在两个不同版本里选一个删 ⇒ 整批不写入，交人工判（Owner 已裁的 rc 分档）。
        print(f"\n预检不通过：{len(blocked)} 条与库里同条文**互不包含**，整批未写入任何内容：")
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


if __name__ == "__main__":
    main()
