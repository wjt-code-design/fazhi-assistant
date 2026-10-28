"""启动期嵌入配置 fail-fast 校验（2026-10-27 部署核查）。

守护的缺陷：容器场景没有 backend/.env，配置只能靠 docker-compose 注入。若 EMBEDDING_API_KEY
未注入，settings.embedding_provider 会静默回落 "local" ⇒ 加载本地 BGE（+1GB 内存）且
rag_chain.COLLECTION_NAME 切到 _LOCAL 集合，与云端 1024 维库对不上 ⇒ 问答零召回，
而 /healthz 仍 200（健康检查不碰嵌入）⇒ 应用"健康"上线但答不了题。
"""

import pytest

import main
from settings import settings


@pytest.fixture
def _restore_embedding_settings():
    """用例内改 settings 后必须还原：settings 是进程级单例，泄漏会污染后续用例。"""
    saved = (
        settings.embedding_provider,
        settings.embedding_api_key,
        settings.embedding_base_url,
    )
    yield
    (
        settings.embedding_provider,
        settings.embedding_api_key,
        settings.embedding_base_url,
    ) = saved


def test_local_provider_never_raises(_restore_embedding_settings):
    """provider=local 走本地 BGE，不需要任何云凭据，不得拦截启动。"""
    settings.embedding_provider = "local"
    settings.embedding_api_key = ""
    settings.embedding_base_url = ""
    main.validate_embedding_config()  # 不抛即通过


def test_aliyun_without_key_raises(_restore_embedding_settings):
    settings.embedding_provider = "aliyun"
    settings.embedding_api_key = ""
    settings.embedding_base_url = "https://example.invalid/v1"
    with pytest.raises(RuntimeError) as ei:
        main.validate_embedding_config()
    assert "EMBEDDING_API_KEY" in str(ei.value)


def test_aliyun_without_base_url_raises(_restore_embedding_settings):
    settings.embedding_provider = "aliyun"
    settings.embedding_api_key = "sk-test"
    settings.embedding_base_url = ""
    with pytest.raises(RuntimeError) as ei:
        main.validate_embedding_config()
    assert "EMBEDDING_BASE_URL" in str(ei.value)


def test_aliyun_complete_config_passes(_restore_embedding_settings):
    settings.embedding_provider = "aliyun"
    settings.embedding_api_key = "sk-test"
    settings.embedding_base_url = "https://example.invalid/v1"
    main.validate_embedding_config()  # 不抛即通过
