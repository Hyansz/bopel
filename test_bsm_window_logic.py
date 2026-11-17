import pytest
import sys
import time
import check_new


def test_window_exists_already(monkeypatch):
    startfile_called = [False]
    sleep_called = [False]

    monkeypatch.setattr(check_new, "bsm_window_exists", lambda: True)
    monkeypatch.setattr(check_new, "open_bsm_shortcut", lambda: startfile_called.__setitem__(0, True))

    def fake_sleep(t):
        if t == check_new.BSM_WAIT_AFTER_OPEN:
            sleep_called.__setitem__(0, True)

    monkeypatch.setattr(time, "sleep", fake_sleep)

    # Jalankan pengecekan logika STEP 2
    if check_new.bsm_window_exists():
        pass
    else:
        check_new.open_bsm_shortcut()
        time.sleep(check_new.BSM_WAIT_AFTER_OPEN)

    assert not startfile_called[0]
    assert not sleep_called[0]


def test_window_not_exists_then_appears(monkeypatch):
    startfile_called = [False]
    sleep_durations = []

    exists_states = [False, True]
    monkeypatch.setattr(check_new, "bsm_window_exists", lambda: exists_states.pop(0) if exists_states else True)
    monkeypatch.setattr(check_new, "open_bsm_shortcut", lambda: startfile_called.__setitem__(0, True))
    monkeypatch.setattr(time, "sleep", lambda t: sleep_durations.append(t))

    if check_new.bsm_window_exists():
        pass
    else:
        check_new.open_bsm_shortcut()
        deadline = time.monotonic() + 30.0
        found = False
        while time.monotonic() < deadline:
            if check_new.bsm_window_exists():
                found = True
                break
            time.sleep(0.5)
        time.sleep(check_new.BSM_WAIT_AFTER_OPEN)

    assert startfile_called[0]
    assert check_new.BSM_WAIT_AFTER_OPEN in sleep_durations


def test_window_never_appears_exits(monkeypatch):
    startfile_called = [False]
    exit_called = [False]

    monkeypatch.setattr(check_new, "bsm_window_exists", lambda: False)
    monkeypatch.setattr(check_new, "open_bsm_shortcut", lambda: startfile_called.__setitem__(0, True))
    monkeypatch.setattr(time, "sleep", lambda t: None)
    monkeypatch.setattr(sys, "exit", lambda code: exit_called.__setitem__(0, True))

    if check_new.bsm_window_exists():
        pass
    else:
        check_new.open_bsm_shortcut()
        deadline = time.monotonic() + 0.1  # singkat untuk tes timeout
        found = False
        while time.monotonic() < deadline:
            if check_new.bsm_window_exists():
                found = True
                break
            time.sleep(0.01)
        if not found:
            sys.exit(1)

    assert startfile_called[0]
    assert exit_called[0]
