import pytest
from app.main import app
from app.services.users import permissions
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_get_users_inactive_dependency_fail(
    async_client,
    mock_session,
    mock_users,
):
    # seems not to override actual function return value
    app.dependency_overrides[permissions.is_admin_or_superuser] = lambda: None

    mock_session.query.return_value.all.return_value = mock_users

    response = await async_client.get("/users/")
    assert response.status_code == 401
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_users_not_admin_dependency_fail(
    async_client,
    mock_session,
    mock_users,
):
    # seems not to override actual function call value
    app.dependency_overrides[permissions.is_user_active] = lambda: None

    mock_session.query.return_value.all.return_value = mock_users

    response = await async_client.get("/users/")
    assert response.status_code == 401
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_get_users_authenticated(
    async_client,
    mock_session,
    mock_users,
):
    app.dependency_overrides[permissions.is_admin_or_superuser] = lambda: None
    app.dependency_overrides[permissions.is_user_active] = lambda: None

    mock_session.query.return_value.all.return_value = mock_users

    response = await async_client.get("/users/")
    assert response.status_code == 200
    assert len(response.json()) == len(mock_users)
    app.dependency_overrides = {}


@pytest.mark.asyncio
async def test_create_user(async_client, mock_session, mock_user, user, mock_is_admin_or_superuser_is_active):
    mock_session.query.return_value.filter.return_value.first.side_effect = [None, None, None, mock_user]
    mock_session.add.return_value = None

    response = await async_client.post("/users/", json=user.__dict__)

    assert response.status_code == 201


async def test_create_user_auth_fails(
    async_client,
    mock_session,
    mock_user,
    user,
):
    mock_session.query.return_value.filter.return_value.first.side_effect = [None, None, None, mock_user]
    mock_session.add.return_value = None

    response = await async_client.post("/users/", json=user.__dict__)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_user_validation_error(
    async_client, mock_session, mock_user, user, mock_is_admin_or_superuser_is_active
):
    del user.role
    del mock_user.role

    mock_session.query.return_value.filter.return_value.first.side_effect = [None, None, None, mock_user]
    mock_session.add.return_value = None
    response = await async_client.post("/users/", json=user.__dict__)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_user_github_id_already_exist(
    async_client, mock_session, mock_user, user, mock_is_admin_or_superuser_is_active
):
    mock_session.query.return_value.filter.return_value.first.side_effect = [mock_user, None, None, None]
    mock_session.add.return_value = None
    response = await async_client.post("/users/", json=user.__dict__)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_user_username_already_exist(
    async_client, mock_session, mock_user, user, mock_is_admin_or_superuser_is_active
):
    mock_session.query.return_value.filter.return_value.first.side_effect = [None, mock_user, None, None]
    mock_session.add.return_value = None
    response = await async_client.post("/users/", json=user.__dict__)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_user_email_already_exist(
    async_client, mock_session, mock_user, user, mock_is_admin_or_superuser_is_active
):
    mock_session.query.return_value.filter.return_value.first.side_effect = [None, None, mock_user, None]
    mock_session.add.return_value = None
    response = await async_client.post("/users/", json=user.__dict__)

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_user_missing_in_db(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.delete.return_value = None

    response = await async_client.delete("/users/123/")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_user_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.delete.return_value = None

    response = await async_client.delete("/users/0/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_user_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.delete.return_value = None

    response = await async_client.delete("/users/0/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_user_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user

    response = await async_client.get("/users/123/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_user_does_not_exist(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None

    response = await async_client.get("/users/123/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_user_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user

    response = await async_client.get("/users/123/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_is_active_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user

    response = await async_client.get("/users/123/is_active")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_is_active_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user

    response = await async_client.get("/users/123/is_active")
    assert response.status_code == 200
    assert response.json() is True


@pytest.mark.asyncio
async def test_user_is_active_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None

    response = await async_client.get("/users/123/is_active")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_activate_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None
    mock_user.is_active = False

    response = await async_client.patch("/users/123/activate")
    assert response.status_code == 200
    assert response.json()["is_active"] is True


@pytest.mark.asyncio
async def test_user_activate_already_active(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/activate")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_user_activate_no_user(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/activate")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_activate_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/activate")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_deactivate_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None
    mock_user.is_active = True

    response = await async_client.patch("/users/123/deactivate")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


@pytest.mark.asyncio
async def test_user_deactivate_already_inactive(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None
    mock_user.is_active = False

    response = await async_client.patch("/users/123/deactivate")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_user_deactivate_no_user(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/deactivate")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_deactivate_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/deactivate")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_role_change_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    assert mock_user.role == "reviewer"
    response = await async_client.patch("/users/123/role", params={"role": "writer"})
    assert response.status_code == 200
    assert response.json()["role"] == "writer"


@pytest.mark.asyncio
async def test_user_role_invalid(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    assert mock_user.role == "reviewer"
    response = await async_client.patch("/users/123/role", params={"role": "asdasd"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_role_no_user(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/role", params={"role": "writer"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_activate_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/role", params={"role": "superuser"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_roles_success(
    async_client,
    mock_is_admin_or_superuser_is_active,
):
    response = await async_client.get("/users/roles")
    assert response.status_code == 200
    roles = response.json()

    assert "reviewer" in roles
    assert "writer" in roles
    assert "administrator" in roles
    assert "superuser" in roles


@pytest.mark.asyncio
async def test_user_roles_fail_auth(
    async_client,
):
    response = await async_client.get("/users/roles")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_data(async_client, mock_session, mock_user, mock_get_current_user):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    response = await async_client.get("/users/me")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_current_user_data(async_client, mock_session, mock_user, mock_get_current_user):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    response = await async_client.get("/users/me")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_update_auth_fail(
    async_client,
    mock_session,
    mock_user,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch(
        "/users/123/",
        json={"role": "superuser"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_user_update_no_user(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = None
    mock_session.add.return_value = None

    response = await async_client.patch("/users/123/", json={"role": "superuser"})
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_user_update_success(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    payload = {
        "role": "superuser",
    }

    assert mock_user.role == "reviewer"
    response = await async_client.patch("/users/123/", json=payload)
    assert response.json()["role"] == "superuser"
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_user_update_no_action_taken(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    payload = {
        "github_id": "666",
    }

    response = await async_client.patch("/users/123/", json=payload)
    assert response.status_code == 200
    assert response.json()["github_id"] == 123

    response = response.json()
    # remove unnecessary fields/format differences
    del response["last_login"]
    del response["created_on"]
    del mock_user.last_login
    del mock_user.created_on
    del mock_user._sa_instance_state

    assert response == mock_user.__dict__


@pytest.mark.asyncio
async def test_user_update_no_action_taken_2(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    payload = {"github_id": "666", "asdasdasd": "asdasdasd", "id": 666}

    response = await async_client.patch("/users/123/", json=payload)
    assert response.status_code == 200
    assert response.json()["github_id"] == 123
    assert response.json()["id"] == 1
    assert "asdasdasd" not in response.json().keys()


@pytest.mark.asyncio
async def test_user_update_error(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.add.return_value = None

    payload = {"role": "asdasdasd"}

    response = await async_client.patch("/users/123/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_update_integrity_error(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.commit.side_effect = IntegrityError(None, None, None)

    payload = {"role": "writer"}

    response = await async_client.patch("/users/123/", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_user_update_value_error(
    async_client,
    mock_session,
    mock_user,
    mock_is_admin_or_superuser_is_active,
):
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_session.commit.side_effect = ValueError

    payload = {"role": "writer"}

    response = await async_client.patch("/users/123/", json=payload)
    assert response.status_code == 417
