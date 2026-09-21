from api.app import app


def test_when_name_is_passed():
    """
    It should return a JSON response with passed name and success status
    """
    with app.test_client() as client:
        response = client.get("/api/example?name=Flask")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Olá, Flask!",
        "success": True,
    }


def test_when_name_is_not_passed():
    """
    It should return a JSON response with default name and success status
    """
    with app.test_client() as client:
        response = client.get("/api/example")

    assert response.status_code == 200
    assert response.get_json() == {
        "message": "Olá, World!",
        "success": True,
    }
