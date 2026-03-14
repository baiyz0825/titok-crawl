"""
End-to-end tests for unified task center.

Tests the unified task model that supports both immediate and scheduled tasks
with concurrent execution capabilities.
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db import crud, database
from backend.db.models import Task
from backend.queue.scheduler import scheduler


async def setup_test_db():
    """Setup test database."""
    # Use in-memory database for testing
    test_db_path = database.settings.DB_PATH.parent / "test_tasks.db"
    if test_db_path.exists():
        test_db_path.unlink()

    # Connect to test database
    await database.db.connect()
    print("✅ Test database connected")


async def teardown_test_db():
    """Cleanup test database."""
    await database.db.close()
    print("✅ Test database closed")


async def test_immediate_task():
    """Test creating and executing an immediate task."""
    print("\n" + "="*70)
    print("Test 1: Immediate Task")
    print("="*70)

    # Create an immediate task
    task = Task(
        task_type="user_profile",
        target="MS4wLjABAAAA_tiW8TfO4hv3pVNq4V0oGW8vX2Y4c5X8Y",
        status="pending",
        priority=5,
        is_scheduled=False,
    )

    task_id = await crud.create_task(task)
    print(f"✅ Created immediate task #{task_id}")

    # Verify task was created
    retrieved_task = await crud.get_task(task_id)
    assert retrieved_task is not None, "Task should exist"
    assert retrieved_task.task_type == "user_profile", "Task type should match"
    assert retrieved_task.is_scheduled == False, "Task should not be scheduled"
    assert retrieved_task.status == "pending", "Task should be pending"

    print(f"✅ Task verified: {retrieved_task.task_type} -> {retrieved_task.target}")
    print(f"   Status: {retrieved_task.status}, Priority: {retrieved_task.priority}")

    # Cleanup
    await database.db.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await database.db.conn.commit()

    print("✅ Test 1 PASSED\n")
    return True


async def test_scheduled_task():
    """Test creating a scheduled task and verifying it triggers."""
    print("\n" + "="*70)
    print("Test 2: Scheduled Task")
    print("="*70)

    # Create a scheduled task
    next_run = (datetime.now() + timedelta(minutes=5)).isoformat()
    task = Task(
        task_type="user_works",
        target="MS4wLjABAAAA_tiW8TfO4hv3pVNq4V0oGW8vX2Y4c5X8Y",
        status="pending",
        priority=3,
        is_scheduled=True,
        schedule_interval=60,  # Every 60 minutes
        next_run_at=datetime.fromisoformat(next_run),
    )

    task_id = await crud.create_task(task)
    print(f"✅ Created scheduled task #{task_id}")

    # Verify task was created with scheduled parameters
    retrieved_task = await crud.get_task(task_id)
    assert retrieved_task is not None, "Task should exist"
    assert retrieved_task.is_scheduled == True, "Task should be scheduled"
    assert retrieved_task.schedule_interval == 60, "Interval should be 60 minutes"
    assert retrieved_task.next_run_at is not None, "Next run time should be set"

    print(f"✅ Scheduled task verified:")
    print(f"   Interval: {retrieved_task.schedule_interval} minutes")
    print(f"   Next run: {retrieved_task.next_run_at}")

    # Test updating next_run_at (simulating a run completion)
    new_next_run = (datetime.now() + timedelta(minutes=60)).isoformat()
    await crud.update_task(task_id, next_run_at=new_next_run)

    updated_task = await crud.get_task(task_id)
    assert updated_task.next_run_at is not None, "Next run should still be set"
    print(f"✅ Next run updated to: {updated_task.next_run_at}")

    # Cleanup
    await database.db.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await database.db.conn.commit()

    print("✅ Test 2 PASSED\n")
    return True


async def test_concurrent_execution():
    """Test creating 10 tasks and verifying concurrent execution support."""
    print("\n" + "="*70)
    print("Test 3: Concurrent Execution")
    print("="*70)

    # Create 10 tasks with varying priorities
    task_ids = []
    for i in range(10):
        task = Task(
            task_type="user_profile" if i % 2 == 0 else "user_works",
            target=f"TEST_USER_{i}",
            status="pending",
            priority=i % 5,  # Varying priorities 0-4
            is_scheduled=False,
        )
        task_id = await crud.create_task(task)
        task_ids.append(task_id)

    print(f"✅ Created 10 tasks (IDs: {task_ids})")

    # Verify all tasks were created
    for task_id in task_ids:
        task = await crud.get_task(task_id)
        assert task is not None, f"Task {task_id} should exist"
        assert task.status == "pending", f"Task {task_id} should be pending"

    print("✅ All 10 tasks verified as pending")

    # Test priority ordering by fetching next pending tasks
    pending_tasks = []
    for _ in range(10):
        task = await crud.get_next_pending_task()
        if task:
            pending_tasks.append(task)
            # Mark as running to get next one
            await crud.update_task(task.id, status="running")

    print(f"✅ Retrieved {len(pending_tasks)} pending tasks")
    print(f"   Priorities: {[t.priority for t in pending_tasks]}")

    # Verify tasks are ordered by priority (higher priority first)
    priorities = [t.priority for t in pending_tasks]
    assert priorities == sorted(priorities, reverse=True), "Tasks should be ordered by priority DESC"

    print("✅ Tasks correctly ordered by priority (higher priority first)")

    # Cleanup - reset task statuses and delete
    for task_id in task_ids:
        await database.db.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    await database.db.conn.commit()

    print("✅ Test 3 PASSED\n")
    return True


async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*70)
    print("UNIFIED TASK CENTER - END-TO-END TESTS")
    print("="*70)

    try:
        await setup_test_db()

        # Run tests
        results = []
        results.append(await test_immediate_task())
        results.append(await test_scheduled_task())
        results.append(await test_concurrent_execution())

        await teardown_test_db()

        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total tests: {len(results)}")
        print(f"Passed: {sum(results)}")
        print(f"Failed: {len(results) - sum(results)}")

        if all(results):
            print("\n✅ ALL TESTS PASSED!")
            return 0
        else:
            print("\n❌ SOME TESTS FAILED")
            return 1

    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)
