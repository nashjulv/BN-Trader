from gui.log_panel import format_log_entries


def test_format_log_entries_for_copy():
    text = format_log_entries([{
        "full_time": "2026-07-23 12:34:56",
        "category": "风控",
        "level": "WARNING",
        "message": "自动任务被风控拦截",
    }])

    assert text == (
        "[2026-07-23 12:34:56] [风控] [警告] "
        "自动任务被风控拦截"
    )
