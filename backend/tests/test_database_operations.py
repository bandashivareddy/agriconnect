import main as api


def test_engine_uses_stale_connection_and_recycle_safety():
    assert api.engine.pool._pre_ping is True
    assert api.engine.pool._recycle == api.DATABASE_POOL_RECYCLE_SECONDS
    assert api.DATABASE_CONNECT_TIMEOUT_SECONDS == 5
