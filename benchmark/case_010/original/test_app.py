from app import Cache


def test_update_is_visible_to_lookup():
    cache = Cache()
    cache.update("x", 1)
    cache.update("x", 2)
    assert cache.get("x") == 2
