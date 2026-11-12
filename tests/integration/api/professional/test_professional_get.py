from uuid import uuid4

import pytest


def test_get_professional_and_missing_professional(client, create_professional):
    professional = create_professional()

    response = client.get(f"/api/professionals/{professional['id']}")
    missing_response = client.get(f"/api/professionals/{uuid4()}")
    invalid_id_response = client.get("/api/professionals/not-a-uuid")

    assert response.status_code == 200
    assert response.get_json()["id"] == professional["id"]
    assert missing_response.status_code == 404
    assert invalid_id_response.status_code == 404


def test_list_professionals_is_paginated_and_preserves_query_params(
    client, create_professional
):
    create_professional("Dra. Ana")
    create_professional("Dr. Bruno")

    first_page = client.get("/api/professionals?page_size=1&department=neuro")
    first_page_data = first_page.get_json()
    next_link = first_page_data["next_link"]

    assert first_page.status_code == 200
    assert set(first_page_data) == {
        "page",
        "page_size",
        "next_link",
        "value",
        "total_items",
    }
    assert first_page_data["page"] == 1
    assert first_page_data["page_size"] == 1
    assert first_page_data["total_items"] == 2
    assert len(first_page_data["value"]) == 1
    assert next_link.startswith("http://")
    assert "page=2" in next_link
    assert "page_size=1" in next_link
    assert "department=neuro" in next_link

    next_page_url = next_link.removeprefix("http://localhost")
    second_page = client.get(next_page_url)
    second_page_data = second_page.get_json()

    assert second_page.status_code == 200
    assert second_page_data["page"] == 2
    assert second_page_data["value"][0]["nome"] == "Dr. Bruno"
    assert second_page_data["next_link"] is None


def test_list_professionals_includes_inactive_and_empty_out_of_range_page(
    client, create_professional
):
    professional = create_professional()
    deactivation = client.delete(f"/api/professionals/{professional['id']}")

    response = client.get("/api/professionals?page=5&page_size=1")
    page_data = response.get_json()

    assert deactivation.status_code == 200
    assert deactivation.get_json()["status"] is False
    assert response.status_code == 200
    assert page_data["total_items"] == 1
    assert page_data["value"] == []
    assert page_data["next_link"] is None


@pytest.mark.parametrize("page", ["0", "-1", "invalid"])
def test_list_professionals_rejects_invalid_page(client, page):
    response = client.get(f"/api/professionals?page={page}")

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "Invalid page parameter",
        "status_code": 400,
        "action": "Use an integer greater than or equal to 1.",
    }


@pytest.mark.parametrize("page_size", ["0", "-1", "invalid", "501"])
def test_list_professionals_uses_default_for_invalid_page_size(client, page_size):
    response = client.get(f"/api/professionals?page_size={page_size}")

    assert response.status_code == 200
    assert response.get_json()["page_size"] == 50
