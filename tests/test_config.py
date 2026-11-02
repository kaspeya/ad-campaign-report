from ad_report.config import BASE_DIR, resolve_data_dir


def test_resolve_data_dir_default() -> None:
    assert resolve_data_dir({}) == BASE_DIR
    assert resolve_data_dir({"DATA_DIR": ""}) == BASE_DIR


def test_resolve_data_dir_from_env() -> None:
    assert resolve_data_dir({"DATA_DIR": "/data"}) == "/data"
