import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from browser.session import BrowserSessionConfig, safe_profile_name
from browser.skill import BrowserSkill, detect_gateway_block
from schemas import BrowserOutput


def test_profile_metadata_resolves_to_assignment_state_dir():
    cfg = BrowserSessionConfig.from_metadata(
        {"browser_profile": "HF Demo/Login", "headless": "false"}
    )

    assert cfg.profile == "HF_Demo_Login"
    assert cfg.headless is False
    assert cfg.storage_state is not None
    assert cfg.save_storage_state == cfg.storage_state
    assert cfg.storage_state.name == "HF_Demo_Login.json"
    assert cfg.storage_state.parent == (
        Path(__file__).resolve().parents[1] / "state" / "browser_profiles"
    )


def test_explicit_storage_state_and_user_data_dir_are_resolved(tmp_path):
    state_path = tmp_path / "state.json"
    user_data = tmp_path / "chrome-profile"
    cfg = BrowserSessionConfig.from_metadata(
        {
            "storage_state": str(state_path),
            "save_storage_state": str(state_path),
            "user_data_dir": str(user_data),
        }
    )

    assert cfg.storage_state == state_path
    assert cfg.save_storage_state == state_path
    assert cfg.user_data_dir == user_data
    assert cfg.output_metadata()["user_data_dir"] == str(user_data)


def test_safe_profile_name_never_returns_empty():
    assert safe_profile_name(" ../ ") == "default"
    assert safe_profile_name("Amazon buyer/session") == "Amazon_buyer_session"


def test_gateway_block_detection_covers_precondition_layer():
    assert detect_gateway_block("<div class=\"h-captcha\"></div>") == "hcaptcha"
    assert detect_gateway_block("Sign in to continue") == "login_wall"
    assert detect_gateway_block("Too many requests. Please slow down.") == "rate_limited"
    assert detect_gateway_block("This content is not available in your region") == "geo_block"
    assert detect_gateway_block("<article>ordinary article about browsers</article>") is None


def test_browser_output_exposes_profile_and_block_type():
    result = BrowserSkill()._pack_error(
        "https://example.test",
        "extract protected content",
        "gateway_blocked",
        "gateway_blocked: login_wall marker",
        block_type="login_wall",
        session_meta={
            "profile": "demo",
            "storage_state_path": "/tmp/demo.json",
            "user_data_dir": None,
        },
    )

    assert result.error_code == "gateway_blocked"
    output = BrowserOutput.model_validate(result.output)
    assert output.profile == "demo"
    assert output.storage_state_path == "/tmp/demo.json"
    assert output.block_type == "login_wall"
