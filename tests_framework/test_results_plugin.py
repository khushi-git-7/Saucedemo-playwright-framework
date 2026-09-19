"""The run recorder (utils/results_plugin.py).

Most tests here start a real, in-process pytest session with ``pytester`` so
that the recorder is exercised through pytest's own hook order: setup, call
and teardown reports, skips, xfails, ``--collect-only`` and interruption.
The xdist behaviour is checked with stand-ins for the controller's view of a
worker report, because spawning worker processes is not something a unit test
should do.
"""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from utils import results_plugin
from utils.config import Config
from utils.results_plugin import ResultsRecorder

PLUGIN_CONFTEST = 'pytest_plugins = ["utils.results_plugin"]\n'


@pytest.fixture
def history(tmp_path, monkeypatch):
    """Points the recorder at a scratch history folder and returns it."""
    folder = tmp_path / "history"
    monkeypatch.setenv("TESTVERSE_HISTORY_DIR", str(folder))
    monkeypatch.delenv("TESTVERSE_RESULTS", raising=False)
    monkeypatch.delenv("TESTVERSE_RUN_GROUP", raising=False)
    monkeypatch.delenv("TESTVERSE_SUITE", raising=False)
    return folder


def run_files(history: Path) -> list:
    return sorted(history.glob("*.json")) if history.exists() else []


def record_run(pytester, history: Path, *args) -> dict:
    """Runs the pytester session with the recorder and returns the run file."""
    pytester.makeconftest(PLUGIN_CONFTEST)
    pytester.runpytest("-p", "no:cacheprovider", *args)
    files = run_files(history)
    assert len(files) == 1, f"expected exactly one run file, found {files}"
    return json.loads(files[0].read_text(encoding="utf-8"))


def by_name(run: dict) -> dict:
    return {test["name"]: test for test in run["tests"]}


# ---------------------------------------------------------------------------
# phases and outcomes
# ---------------------------------------------------------------------------
def test_each_phase_maps_to_the_right_outcome(pytester, history):
    pytester.makepyfile(
        """
        import pytest

        @pytest.fixture
        def broken_setup():
            raise RuntimeError("no browser")

        @pytest.fixture
        def broken_teardown():
            yield
            raise RuntimeError("context did not close")

        def test_passes():
            pass

        def test_fails_in_call():
            assert 1 == 2, "wrong answer"

        def test_errors_in_setup(broken_setup):
            pass

        def test_errors_in_teardown(broken_teardown):
            pass

        def test_fails_in_call_then_errors_in_teardown(broken_teardown):
            assert False

        def test_errors_in_setup_and_teardown(broken_teardown, broken_setup):
            pass
        """
    )

    run = record_run(pytester, history)
    tests = by_name(run)

    assert tests["test_passes"]["outcome"] == "passed"
    assert tests["test_passes"]["phase"] is None
    assert tests["test_passes"]["call_duration"] is not None

    assert tests["test_fails_in_call"]["outcome"] == "failed"
    assert tests["test_fails_in_call"]["phase"] == "call"
    assert tests["test_fails_in_call"]["message"].startswith("AssertionError: wrong answer")
    assert "assert 1 == 2" in tests["test_fails_in_call"]["details"]

    assert tests["test_errors_in_setup"]["outcome"] == "error"
    assert tests["test_errors_in_setup"]["phase"] == "setup"
    assert "no browser" in tests["test_errors_in_setup"]["message"]
    assert tests["test_errors_in_setup"]["call_duration"] is None  # the body never ran

    assert tests["test_errors_in_teardown"]["outcome"] == "error"
    assert tests["test_errors_in_teardown"]["phase"] == "teardown"

    # The first failing phase is the root cause and must not be overwritten
    # by a later one: the test body beats teardown, and setup beats teardown.
    assert tests["test_fails_in_call_then_errors_in_teardown"]["outcome"] == "failed"
    assert tests["test_fails_in_call_then_errors_in_teardown"]["phase"] == "call"
    assert tests["test_errors_in_setup_and_teardown"]["outcome"] == "error"
    assert tests["test_errors_in_setup_and_teardown"]["phase"] == "setup"
    assert "no browser" in tests["test_errors_in_setup_and_teardown"]["message"]

    assert run["summary"] == {"total": 6, "passed": 1, "failed": 2, "error": 3, "skipped": 0}
    assert run["exit_status"] == pytest.ExitCode.TESTS_FAILED


def test_skips_and_expected_failures_are_recorded_as_skipped(pytester, history):
    pytester.makepyfile(
        """
        import pytest

        @pytest.mark.skip(reason="not on this platform")
        def test_skipped_by_marker():
            pass

        def test_skipped_in_body():
            pytest.skip("needs a writable API")

        @pytest.mark.xfail(reason="known bug")
        def test_expected_failure():
            assert False

        @pytest.mark.xfail(reason="fixed upstream")
        def test_unexpected_pass():
            pass
        """
    )

    run = record_run(pytester, history)
    tests = by_name(run)

    assert tests["test_skipped_by_marker"]["outcome"] == "skipped"
    assert tests["test_skipped_by_marker"]["phase"] == "setup"
    assert "not on this platform" in tests["test_skipped_by_marker"]["message"]
    assert tests["test_skipped_in_body"]["outcome"] == "skipped"
    assert tests["test_skipped_in_body"]["phase"] == "call"
    assert "needs a writable API" in tests["test_skipped_in_body"]["message"]
    assert tests["test_expected_failure"]["outcome"] == "skipped"
    assert tests["test_unexpected_pass"]["outcome"] == "passed"
    assert run["summary"] == {"total": 4, "passed": 1, "failed": 0, "error": 0, "skipped": 3}


def test_duration_is_the_sum_of_all_phases(pytester, history):
    pytester.makepyfile(
        """
        import time, pytest

        @pytest.fixture
        def slow():
            time.sleep(0.05)
            yield
            time.sleep(0.05)

        def test_x(slow):
            time.sleep(0.05)
        """
    )

    test = record_run(pytester, history)["tests"][0]

    assert test["duration"] >= 0.15
    assert 0.05 <= test["call_duration"] < test["duration"]


# ---------------------------------------------------------------------------
# metadata attached to each record
# ---------------------------------------------------------------------------
def test_only_user_markers_are_recorded(pytester, history):
    pytester.makeini("[pytest]\nmarkers =\n    smoke: fast\n    ui: browser\n")
    pytester.makepyfile(
        """
        import pytest

        pytestmark = pytest.mark.ui

        @pytest.mark.smoke
        @pytest.mark.parametrize("value", [1, 2])
        @pytest.mark.usefixtures("tmp_path")
        def test_x(value):
            pass
        """
    )

    tests = by_name(record_run(pytester, history))

    assert tests["test_x[1]"]["markers"] == ["smoke", "ui"]
    assert tests["test_x[2]"]["markers"] == ["smoke", "ui"]
    assert tests["test_x[1]"]["layer"] == "ui"


def test_artifacts_recorded_by_fixtures_are_stored_relative_to_the_repo(pytester, history):
    screenshot = Config.ROOT_DIR / "screenshots" / "test_x_gw0_2026.png"
    pytester.makeconftest(
        f"""
        pytest_plugins = ["utils.results_plugin"]
        import pytest

        @pytest.fixture
        def page(request):
            yield
            request.node._artifacts = [{str(screenshot)!r}]  # what tests/conftest.py does
        """
    )
    pytester.makepyfile("def test_x(page):\n    assert False\n")
    pytester.runpytest("-p", "no:cacheprovider")

    test = json.loads(run_files(history)[0].read_text(encoding="utf-8"))["tests"][0]

    assert test["artifacts"] == ["screenshots/test_x_gw0_2026.png"]


def test_run_metadata(pytester, history, monkeypatch):
    monkeypatch.setenv("TESTVERSE_RUN_GROUP", "group-7")
    monkeypatch.setenv("TESTVERSE_SUITE", "custom")
    pytester.makepyfile("def test_x():\n    pass\n")

    run = record_run(pytester, history)

    assert run["schema"] == results_plugin.SCHEMA_VERSION
    assert run["run_group"] == "group-7"
    assert run["suite"] == "custom"
    assert run["exit_status"] == 0
    assert run["workers"] == 1
    assert run["tests"][0]["nodeid"] == "test_run_metadata.py::test_x"
    assert run["tests"][0]["module"] == "test_run_metadata.py"
    assert run["tests"][0]["worker"] is None
    assert set(run["git"]) == {"sha", "branch"}
    assert run["ci"]["provider"] in (None, "github")


# ---------------------------------------------------------------------------
# when nothing must be written
# ---------------------------------------------------------------------------
def test_collect_only_writes_nothing(pytester, history):
    pytester.makeconftest(PLUGIN_CONFTEST)
    pytester.makepyfile("def test_x():\n    pass\n")

    result = pytester.runpytest("-p", "no:cacheprovider", "--collect-only")

    assert result.ret == 0
    assert run_files(history) == []


def test_session_without_tests_writes_nothing(pytester, history):
    pytester.makeconftest(PLUGIN_CONFTEST)
    pytester.makepyfile("def test_x():\n    pass\n")

    pytester.runpytest("-p", "no:cacheprovider", "-k", "nothing_matches")

    assert run_files(history) == []


def test_recording_can_be_switched_off(pytester, history, monkeypatch):
    monkeypatch.setenv("TESTVERSE_RESULTS", "0")
    pytester.makeconftest(PLUGIN_CONFTEST)
    pytester.makepyfile("def test_x():\n    pass\n")

    pytester.runpytest("-p", "no:cacheprovider")

    assert run_files(history) == []


def test_interrupted_session_is_not_recorded(pytester, history):
    pytester.makeconftest(PLUGIN_CONFTEST)
    pytester.makepyfile(
        """
        def test_first():
            pass

        def test_ctrl_c():
            raise KeyboardInterrupt

        def test_never_runs():
            pass
        """
    )

    result = pytester.runpytest("-p", "no:cacheprovider", no_reraise_ctrlc=True)

    assert result.ret == pytest.ExitCode.INTERRUPTED
    assert run_files(history) == []


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def test_relative_to_root_uses_posix_separators():
    inside = str(Config.ROOT_DIR / "screenshots" / "x.png").replace("/", "\\")
    assert results_plugin.relative_to_root(inside) == "screenshots/x.png"
    assert results_plugin.relative_to_root(r"D:\elsewhere\shot.png") == "D:/elsewhere/shot.png"


@pytest.mark.parametrize(
    "nodeid, area",
    [
        ("tests/test_checkout.py::test_x", "checkout"),
        ("api/test_posts_api.py::test_y[1]", "posts"),
        ("tests/test_login.py::TestLogin::test_z", "login"),
    ],
)
def test_classify_area(nodeid, area):
    assert results_plugin.classify_area(nodeid) == area


def test_classify_layer_prefers_markers_over_the_path():
    assert results_plugin.classify_layer("tests/test_a.py::test_x", ["ui"]) == "ui"
    assert results_plugin.classify_layer("tests/test_a.py::test_x", ["api"]) == "api"
    assert results_plugin.classify_layer("tests/test_a.py::test_x", []) == "ui"
    assert results_plugin.classify_layer("api/test_a.py::test_x", []) == "api"
    assert results_plugin.classify_layer("tests_framework/test_a.py::test_x", []) == "other"


def test_git_info_is_empty_when_git_is_missing_or_not_a_repo(monkeypatch):
    for name in ("GITHUB_SHA", "GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        monkeypatch.delenv(name, raising=False)

    def missing(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", missing)
    assert results_plugin.git_info() == {"sha": "", "branch": ""}

    def not_a_repo(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 128, stdout="", stderr="fatal: not a git repository")

    monkeypatch.setattr(subprocess, "run", not_a_repo)
    assert results_plugin.git_info() == {"sha": "", "branch": ""}


def test_git_info_prefers_the_ci_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "abc123")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/x")
    assert results_plugin.git_info() == {"sha": "abc123", "branch": "feature/x"}


# ---------------------------------------------------------------------------
# xdist: workers record nothing, the controller sees every worker's reports
# ---------------------------------------------------------------------------
class _PluginManager:
    def __init__(self):
        self.registered = []

    def hasplugin(self, name):
        return False

    def register(self, plugin, name):
        self.registered.append(name)


def _stub_config(**attrs):
    config = SimpleNamespace(
        option=SimpleNamespace(numprocesses=None),
        stash=pytest.Stash(),
        args=["tests"],
        pluginmanager=_PluginManager(),
        getoption=lambda name, default=None: default,
    )
    for key, value in attrs.items():
        setattr(config, key, value)
    return config


def _report(nodeid, when, outcome="passed", worker=None, longrepr=None, **extra):
    report = pytest.TestReport(nodeid, ("tests/test_a.py", 1, nodeid), {}, outcome, longrepr, when, **extra)
    if worker:  # what xdist's controller attaches before re-emitting the hook
        report.node = SimpleNamespace(gateway=SimpleNamespace(id=worker))
    return report


def test_recorder_is_not_registered_on_xdist_workers():
    worker = _stub_config(workerinput={"workerid": "gw0"})
    controller = _stub_config()

    results_plugin.pytest_configure(worker)
    results_plugin.pytest_configure(controller)

    assert worker.pluginmanager.registered == []
    assert controller.pluginmanager.registered == ["testverse-results-recorder"]


def test_controller_attributes_reports_to_workers_and_counts_them():
    recorder = ResultsRecorder(_stub_config())
    for worker, nodeid in (("gw0", "tests/test_a.py::test_x"), ("gw1", "tests/test_a.py::test_y")):
        for when in ("setup", "call", "teardown"):
            recorder.pytest_runtest_logreport(_report(nodeid, when, worker=worker, duration=0.5))

    run = recorder.build_run(0)

    assert {t["nodeid"]: t["worker"] for t in run["tests"]} == {"tests/test_a.py::test_x": "gw0", "tests/test_a.py::test_y": "gw1"}
    assert run["workers"] == 2
    assert all(t["duration"] == 1.5 for t in run["tests"])
    assert run["summary"] == {"total": 2, "passed": 2, "failed": 0, "error": 0, "skipped": 0}


def test_worker_crash_report_is_recorded_as_an_error():
    # xdist synthesises this report on the controller when a worker dies
    # mid-test: outcome failed, phase "???", a plain string as longrepr.
    recorder = ResultsRecorder(_stub_config())
    crash = _report("tests/test_a.py::test_x", "???", "failed", worker="gw0", longrepr="worker 'gw0' crashed while running 'tests/test_a.py::test_x'")

    recorder.pytest_runtest_logreport(crash)

    test = recorder.build_run(1)["tests"][0]
    assert test["outcome"] == "error"
    assert test["phase"] == "???"
    assert test["message"].startswith("worker 'gw0' crashed")
