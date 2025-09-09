from unpage.config import Config, PluginConfig, manager


def test_config_merge_plugins() -> None:
    cfg = manager.get_empty_config(profile="test")
    new_cfg = cfg.merge_plugins({"testplugin": PluginConfig(enabled=True, settings={})})
    assert "testplugin" in new_cfg.plugins
    assert new_cfg.plugins["testplugin"].enabled is True
    assert new_cfg.plugins["testplugin"].settings == {}
