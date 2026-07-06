from build_exe import get_output_name, normalize_target


def test_normalize_target_aliases():
    assert normalize_target("windows") == "windows"
    assert normalize_target("WIN") == "windows"
    assert normalize_target("macos") == "darwin"
    assert normalize_target("darwin") == "darwin"
    assert normalize_target("linux") == "linux"


def test_output_name_for_each_platform():
    assert get_output_name("windows") == "SGIMI_TECNOGAS.exe"
    assert get_output_name("darwin") == "SGIMI_TECNOGAS.app"
    assert get_output_name("linux") == "SGIMI_TECNOGAS"
