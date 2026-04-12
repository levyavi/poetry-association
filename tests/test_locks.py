from poem_assoc.locks import RebuildLock


def test_rebuild_lock_acquire_and_release():
    lock = RebuildLock()
    assert not lock.is_rebuilding()

    assert lock.acquire() is True
    assert lock.is_rebuilding()

    lock.release()
    assert not lock.is_rebuilding()


def test_rebuild_lock_second_acquire_fails():
    lock = RebuildLock()
    assert lock.acquire() is True
    assert lock.acquire() is False
    assert lock.is_rebuilding()
    lock.release()


def test_rebuild_lock_release_without_acquire_is_safe():
    lock = RebuildLock()
    lock.release()  # Should not raise
    assert not lock.is_rebuilding()


def test_rebuild_lock_context_manager():
    lock = RebuildLock()
    with lock:
        assert lock.is_rebuilding()
    assert not lock.is_rebuilding()


def test_rebuild_lock_context_manager_releases_on_exception():
    lock = RebuildLock()
    try:
        with lock:
            raise ValueError("boom")
    except ValueError:
        pass
    assert not lock.is_rebuilding()
    assert lock.acquire() is True  # Can re-acquire
    lock.release()
