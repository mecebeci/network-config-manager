from pytest_django.asserts import assertRedirects


def test_home_redirects_anonymous_user_to_login(client):
    response = client.get('/')
    assertRedirects(response, '/login/?next=/')


def test_home_is_shown_to_logged_in_user(client, django_user_model):
    user = django_user_model.objects.create_user(username='alice', password='pw')
    client.force_login(user)
    response = client.get('/')
    assert response.status_code == 200
