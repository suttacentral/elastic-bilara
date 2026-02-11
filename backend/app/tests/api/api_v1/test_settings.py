import pytest
from unittest.mock import MagicMock

from app.db.models.user_preference import UserPreference as UserPreferenceModel


@pytest.fixture
def mock_user_preference():
    """Create a mock UserPreference row."""
    pref = MagicMock(spec=UserPreferenceModel)
    pref.id = 1
    pref.github_id = 1
    pref.pali_lookup = True
    pref.dblclick_search = True
    return pref


# ── GET /settings ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_settings_auth_fail(async_client):
    """Unauthenticated request should return 401."""
    response = await async_client.get("/settings")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_settings_no_existing_row(
    async_client,
    mock_session,
    mock_get_current_user,
):
    """When no preference row exists, should return defaults (both True)."""
    mock_session.query.return_value.filter.return_value.first.return_value = None

    response = await async_client.get("/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 0
    assert data["github_id"] == 1
    assert data["pali_lookup"] is True
    assert data["dblclick_search"] is True


@pytest.mark.asyncio
async def test_get_settings_existing_row(
    async_client,
    mock_session,
    mock_get_current_user,
    mock_user_preference,
):
    """When a preference row exists, should return its values."""
    mock_user_preference.pali_lookup = False
    mock_user_preference.dblclick_search = True
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user_preference

    response = await async_client.get("/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert data["pali_lookup"] is False
    assert data["dblclick_search"] is True


@pytest.mark.asyncio
async def test_get_settings_null_values_default_to_true(
    async_client,
    mock_session,
    mock_get_current_user,
    mock_user_preference,
):
    """When DB columns are None, should default to True."""
    mock_user_preference.pali_lookup = None
    mock_user_preference.dblclick_search = None
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user_preference

    response = await async_client.get("/settings")
    assert response.status_code == 200

    data = response.json()
    assert data["pali_lookup"] is True
    assert data["dblclick_search"] is True


# ── PUT /settings ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_put_settings_auth_fail(async_client):
    """Unauthenticated request should return 401."""
    response = await async_client.put(
        "/settings",
        json={"pali_lookup": False},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_put_settings_update_existing(
    async_client,
    mock_session,
    mock_get_current_user,
    mock_user_preference,
):
    """When a preference row exists, should update matching fields."""
    mock_user_preference.pali_lookup = True
    mock_user_preference.dblclick_search = True
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user_preference

    response = await async_client.put(
        "/settings",
        json={"pali_lookup": False, "dblclick_search": False},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["pali_lookup"] is False
    assert data["dblclick_search"] is False


@pytest.mark.asyncio
async def test_put_settings_partial_update(
    async_client,
    mock_session,
    mock_get_current_user,
    mock_user_preference,
):
    """Only fields provided in payload should be updated; others stay unchanged."""
    mock_user_preference.pali_lookup = True
    mock_user_preference.dblclick_search = True
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user_preference

    response = await async_client.put(
        "/settings",
        json={"pali_lookup": False},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["pali_lookup"] is False
    # dblclick_search not in payload → should remain True
    assert data["dblclick_search"] is True


@pytest.mark.asyncio
async def test_put_settings_create_new(
    async_client,
    mock_session,
    mock_get_current_user,
):
    """When no preference row exists, should create a new one (upsert)."""
    mock_session.query.return_value.filter.return_value.first.return_value = None

    new_pref = MagicMock(spec=UserPreferenceModel)
    new_pref.id = 42
    new_pref.github_id = 1
    new_pref.pali_lookup = False
    new_pref.dblclick_search = True

    def fake_refresh(obj):
        obj.id = new_pref.id
        obj.github_id = new_pref.github_id
        obj.pali_lookup = new_pref.pali_lookup
        obj.dblclick_search = new_pref.dblclick_search

    mock_session.refresh.side_effect = fake_refresh

    response = await async_client.put(
        "/settings",
        json={"pali_lookup": False},
    )
    assert response.status_code == 200

    mock_session.add.assert_called_once()
    data = response.json()
    assert data["pali_lookup"] is False
    assert data["dblclick_search"] is True


@pytest.mark.asyncio
async def test_put_settings_empty_payload(
    async_client,
    mock_session,
    mock_get_current_user,
    mock_user_preference,
):
    """Empty payload (both fields None) should not change anything."""
    mock_user_preference.pali_lookup = True
    mock_user_preference.dblclick_search = False
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user_preference

    response = await async_client.put(
        "/settings",
        json={},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["pali_lookup"] is True
    assert data["dblclick_search"] is False


@pytest.mark.asyncio
async def test_put_settings_create_new_defaults(
    async_client,
    mock_session,
    mock_get_current_user,
):
    """Creating with empty payload should use defaults (both True)."""
    mock_session.query.return_value.filter.return_value.first.return_value = None

    new_pref = MagicMock(spec=UserPreferenceModel)
    new_pref.id = 10
    new_pref.github_id = 1
    new_pref.pali_lookup = True
    new_pref.dblclick_search = True

    def fake_refresh(obj):
        obj.id = new_pref.id
        obj.github_id = new_pref.github_id
        obj.pali_lookup = new_pref.pali_lookup
        obj.dblclick_search = new_pref.dblclick_search

    mock_session.refresh.side_effect = fake_refresh

    response = await async_client.put(
        "/settings",
        json={},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["pali_lookup"] is True
    assert data["dblclick_search"] is True
