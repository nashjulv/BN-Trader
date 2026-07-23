import pytest

from services.automation_manager import (
    AutomationManager,
    AutomationTask,
    EVALUATING,
    RUNNING,
    STOPPED,
)


def test_tasks_never_auto_resume_after_reload(tmp_path):
    path = tmp_path / "automation.json"
    manager = AutomationManager(path)
    task = manager.tasks[0]
    manager.start(task.id, now_ts=10)
    assert task.status == RUNNING
    manager.save()

    reloaded = AutomationManager(path)
    assert all(item.status == STOPPED for item in reloaded.tasks)


def test_allocation_cannot_exceed_one_hundred_percent(tmp_path):
    manager = AutomationManager(tmp_path / "automation.json")
    with pytest.raises(ValueError, match="100%"):
        manager.add_allocation("SOLUSDT", 0.30)


def test_due_task_lifecycle(tmp_path):
    manager = AutomationManager(tmp_path / "automation.json")
    task = manager.tasks[0]
    manager.start(task.id, now_ts=100)
    assert manager.due_task(now_ts=100).id == task.id
    manager.mark_evaluating(task.id)
    assert task.status == EVALUATING
    assert manager.due_task(now_ts=101) is None
    manager.finish_evaluation(task.id, "暂无信号", now_ts=110)
    assert task.status == RUNNING
    assert task.next_run_ts == 110 + task.interval_seconds


def test_stopping_during_evaluation_never_restarts_task(tmp_path):
    manager = AutomationManager(tmp_path / "automation.json")
    task = manager.tasks[0]
    manager.start(task.id, now_ts=100)
    manager.mark_evaluating(task.id)
    manager.stop(task.id)
    manager.finish_evaluation(task.id, "后台返回买入信号", now_ts=110)
    assert task.status == STOPPED
    assert manager.due_task(now_ts=999) is None


def test_usdc_usdt_default_task_exists(tmp_path):
    manager = AutomationManager(tmp_path / "automation.json")
    task = next(item for item in manager.tasks if item.symbol == "USDCUSDT")
    assert task.strategy == "RANGING"
    assert task.status == STOPPED


def test_allocation_can_add_disable_and_delete_custom_symbol(tmp_path):
    manager = AutomationManager(tmp_path / "automation.json")
    manager.add_allocation("ada/usdt", 0.20)
    manager.add(AutomationTask.create("ADA 场景任务", "ADAUSDT"))
    assert manager.allocation_for("ADAUSDT").allocation_ratio == 0.20

    manager.update_allocation("ADAUSDT", 0.15, enabled=False)
    assert manager.allocation_for("ADAUSDT") is None
    assert manager.allocation_for(
        "ADAUSDT", enabled_only=False
    ).allocation_ratio == 0.15
    with pytest.raises(ValueError, match="停用"):
        manager.start(manager.tasks[-1].id)

    manager.remove_allocation("ADAUSDT")
    assert manager.allocation_for("ADAUSDT", enabled_only=False) is None
    assert all(task.symbol != "ADAUSDT" for task in manager.tasks)


def test_task_requires_symbol_in_allocation_table(tmp_path):
    manager = AutomationManager(tmp_path / "automation.json")
    with pytest.raises(ValueError, match="资金分配表"):
        manager.add(AutomationTask.create("ADA 任务", "ADAUSDT"))
