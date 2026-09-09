import json
from pathlib import Path
import subprocess
import sys
import zipfile
from streamlit.testing.v1 import AppTest


def test_demo_ui_and_changed_rules():
    app = AppTest.from_file("src/ordercheck_app.py").run(timeout=40)
    assert not app.exception
    app.button[0].click().run(timeout=40)
    assert not app.exception
    assert [x.value for x in app.metric] == ["12", "5", "7", "140.30"]
    rules = json.loads(app.text_area[0].value)
    rules["amount_max"] = "50"
    app.text_area[0].set_value(json.dumps(rules)).run()
    assert len(app.metric) == 0  # old result and downloads must disappear
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[1].value == "4"


def test_bad_rules_ui():
    app = AppTest.from_file("src/ordercheck_app.py").run(timeout=40)
    app.text_area[0].set_value("{}").run()
    assert not app.exception
    assert len(app.error) == 1


def test_cli_demo_and_no_overwrite(tmp_path):
    target = tmp_path / "report.zip"
    cmd = [sys.executable, "src/ordercheck_cli.py", "--demo", "--output", str(target)]
    result = subprocess.run(cmd, capture_output=True)
    assert result.returncode == 2  # successful report, rejected rows need review
    with zipfile.ZipFile(target) as archive:
        assert json.loads(archive.read("summary.json"))["accepted_rows"] == 5
    before = target.read_bytes()
    assert subprocess.run(cmd, capture_output=True).returncode == 1
    assert target.read_bytes() == before


def test_cli_all_valid(tmp_path):
    source = tmp_path / "valid.csv"
    source.write_text("order_id,store,date,amount\n001,A,2026-09-08,2\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "src/ordercheck_cli.py", "--input", str(source),
                             "--output", str(tmp_path / "report.zip")], capture_output=True)
    assert result.returncode == 0
