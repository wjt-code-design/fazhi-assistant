"""测试侧的写围栏（单一真源，conftest 与用例共用）。

`real_kb` 交给用例的是 **生产语料索引本体**（`rag_chain.DEFAULT_CHROMA_DIR`）。
原先"只读"这条只写在 docstring 里 ⇒ 任何一次手滑写入都会静默改变真实索引，
而且会影响之后所有依赖它的用例。把约定变成结构：读放行，写当场抛。

放在独立模块而不是 conftest 内部：这样它既能被 fixture 用，也能被用例直接引用做
正反控制，不需要 `import conftest`（那会二次执行 fixture 定义）。

强度要说实话：**这是绊线，不是沙箱**。目标是让"顺手写一句"当场炸，而不是防住一个
铁了心要写的人——`object.__setattr__`、直接改 `_fenced_target` 这类蓄意手法仍然能拿到真对象。
下面两处逃逸是独立复核（2026-10-16）实测点出来后补的：取内层引用、以及让真对象自己复制一份返回。
还有一个已知天花板没解决：名单按**动词**筛名字，所以"名字里没有写动词但语义是写"的方法
（`flush_` / `commit_` / `index_` 之类）既进不了围栏、也进不了那条覆盖率用例——真要封顶得在
chromadb client 层拦，不在本文件这一层。
"""

from __future__ import annotations

# langchain `Chroma` 与 chromadb `Collection` 上的写语义。
# 名单不是手抄的：由已安装类的 dir() 全集导出、再剔除 pydantic 模型管线名；
# 漂移由 test_admin_credential_guards.py::test_fence_covers_real_write_surface 钉住
# （第一轮手抄 10 个名字漏了 6 个真写入口，全靠主动比对才发现）。
FENCED_WRITES = {
    "add_documents",
    "aadd_documents",
    "add_texts",
    "aadd_texts",
    "add_images",
    "update_document",
    "update_documents",
    "delete",
    "adelete",
    "delete_collection",
    "reset_collection",
    "add",
    "upsert",
    "update",
    "modify",
    # 当前两个类上都不存在、但 langchain 基线里出现过的名字：留着不亏（升级后自动生效）
    "delete_documents",
}

# 不是"写"，但会**返回一个没被围栏包住的真实对象**，拿到它之后写就绕过围栏了。
# 单列一张表是因为两种漂移的修法不同：FENCED_WRITES 的判据是"真写面 ⊆ 名单"（升级会变红），
# 这张钉的是"别把裸对象交出去"。混在一张表里就说不清哪条错了。
FENCED_CLONES = {
    "copy",
    "model_copy",
    "construct",
    "model_construct",
    "parse_obj",
}


class _ReadOnlyFence:
    """两层围栏的公共部分：命中名单就抛，其余原样转发。"""

    __slots__ = ("_fenced_target",)

    def __init__(self, target):
        self._fenced_target = target

    @property
    def _inner(self):
        # 内层引用原来是个可读的 slot ⇒ `fenced._inner.add_documents(...)` 能把写直接打到生产库。
        # 改成读它就抛；名字保留是因为 conftest/用例的旧写法都叫 `_inner`，报错要对得上。
        raise AssertionError("围栏的内层引用不许取——取到它就绕过只读约定（真需要写库请用未围栏的句柄）")

    def _blocked(self, item: str, layer: str) -> None:
        if item in FENCED_WRITES:
            raise AssertionError(f"{layer}：禁止 {item}()——写坏它会静默影响之后所有真实语料用例")
        if item in FENCED_CLONES:
            raise AssertionError(f"{layer}：禁止 {item}()——它返回一个没包围栏的真对象，等于交出写入口")

    def __repr__(self) -> str:
        # 刻意不转发：pytest 失败时会 repr 现场对象，repr 去碰真库就把调试输出变成了副作用
        return f"<{type(self).__name__} over {type(self._fenced_target).__name__}>"


class ReadOnlyCollection(_ReadOnlyFence):
    """chroma 集合的只读围栏。"""

    __slots__ = ()

    def __getattr__(self, item):
        self._blocked(item, "real_kb 交出去的是生产语料索引本体")
        return getattr(self._fenced_target, item)


class ReadOnlyStore(_ReadOnlyFence):
    """langchain `Chroma` 的只读围栏；`_collection` 也返回围栏版。"""

    __slots__ = ()

    @property
    def _collection(self):
        return ReadOnlyCollection(self._fenced_target._collection)

    def __getattr__(self, item):
        self._blocked(item, "real_kb 只读（vectorstore 层）")
        return getattr(self._fenced_target, item)
