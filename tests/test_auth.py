import pytest
from django.urls import URLResolver, get_resolver
from pytest_django.asserts import assertRedirects

PUBLIC = {'login', 'logout'}


def app_paths(patterns, prefix='/'):
    """Every URL of the project except the public ones and the admin."""
    for pattern in patterns:
        if isinstance(pattern, URLResolver):
            # The admin has its own login
            if pattern.app_name != 'admin':
                yield from app_paths(pattern.url_patterns, prefix + str(pattern.pattern))
        elif pattern.name not in PUBLIC:
            yield prefix + str(pattern.pattern).replace('<int:pk>', '1')


def test_home_redirects_anonymous_user_to_login(client):
    response = client.get('/')
    assertRedirects(response, '/login/?next=/')


# A new view without @login_required makes this test fail
@pytest.mark.parametrize('path', list(app_paths(get_resolver().url_patterns)))
def test_every_page_requires_login(client, path):
    response = client.get(path)
    assert response.status_code == 302
    assert response.url.startswith('/login/')


def test_home_is_shown_to_logged_in_user(client, django_user_model):
    user = django_user_model.objects.create_user(username='alice', password='pw')
    client.force_login(user)
    response = client.get('/')
    assert response.status_code == 200
