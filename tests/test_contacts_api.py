import pytest

BASE = "/api/v1/contacts"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "sqlite"


def test_create_contact(client, payload):
    response = client.post(BASE, json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["id"] > 0
    assert body["email"] == "ada@example.com"
    assert body["full_name"] == "Ada Lovelace"
    assert body["created_at"] and body["updated_at"]


def test_create_requires_valid_email(client, payload):
    response = client.post(BASE, json={**payload, "email": "not-an-email"})
    assert response.status_code == 422


def test_create_requires_names(client, payload):
    response = client.post(BASE, json={**payload, "first_name": ""})
    assert response.status_code == 422


def test_duplicate_email_conflicts(client, payload):
    assert client.post(BASE, json=payload).status_code == 201
    response = client.post(BASE, json={**payload, "email": "ADA@example.com"})
    assert response.status_code == 409


def test_get_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.get(f"{BASE}/{contact_id}")
    assert response.status_code == 200
    assert response.json()["id"] == contact_id


def test_get_missing_contact_returns_404(client):
    assert client.get(f"{BASE}/9999").status_code == 404


def test_list_pagination_and_total(client, payload):
    for index in range(5):
        client.post(BASE, json={**payload, "email": f"user{index}@example.com"})

    response = client.get(BASE, params={"limit": 2, "offset": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
    assert body["limit"] == 2 and body["offset"] == 2


def test_list_search(client, payload):
    client.post(BASE, json=payload)
    client.post(
        BASE,
        json={**payload, "first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com", "company": "US Navy"},
    )

    hits = client.get(BASE, params={"search": "hopper"}).json()
    assert hits["total"] == 1
    assert hits["items"][0]["last_name"] == "Hopper"

    by_company = client.get(BASE, params={"search": "navy"}).json()
    assert by_company["total"] == 1

    misses = client.get(BASE, params={"search": "nobody"}).json()
    assert misses["total"] == 0


def test_list_sorting(client, payload):
    client.post(BASE, json={**payload, "last_name": "Zhang", "email": "z@example.com"})
    client.post(BASE, json={**payload, "last_name": "Adams", "email": "a@example.com"})

    names = [
        item["last_name"]
        for item in client.get(BASE, params={"sort_by": "last_name", "order": "asc"}).json()["items"]
    ]
    assert names == ["Adams", "Zhang"]


def test_list_rejects_bad_sort_field(client):
    assert client.get(BASE, params={"sort_by": "; DROP TABLE contacts"}).status_code == 422


def test_patch_updates_only_sent_fields(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"phone": "+1-000-000-0000"})
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "+1-000-000-0000"
    assert body["first_name"] == "Ada"
    assert body["company"] == "Analytical Engines"


def test_patch_duplicate_email_conflicts(client, payload):
    first = client.post(BASE, json=payload).json()["id"]
    client.post(BASE, json={**payload, "email": "grace@example.com"})
    response = client.patch(f"{BASE}/{first}", json={"email": "grace@example.com"})
    assert response.status_code == 409


def test_patch_same_email_is_allowed(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.patch(f"{BASE}/{contact_id}", json={"email": payload["email"]})
    assert response.status_code == 200


def test_put_replaces_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    response = client.put(
        f"{BASE}/{contact_id}",
        json={"first_name": "Grace", "last_name": "Hopper", "email": "grace@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Grace Hopper"
    assert body["company"] is None  # omitted fields are cleared by PUT


def test_put_missing_contact_returns_404(client):
    response = client.put(
        f"{BASE}/9999",
        json={"first_name": "A", "last_name": "B", "email": "ab@example.com"},
    )
    assert response.status_code == 404


def test_delete_contact(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204
    assert client.get(f"{BASE}/{contact_id}").status_code == 404
    assert client.delete(f"{BASE}/{contact_id}").status_code == 404


def test_root_lists_entrypoints(client):
    body = client.get("/").json()
    assert body["contacts"] == BASE


# --- profile photo -------------------------------------------------------

PHOTO = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


def test_create_contact_with_photo(client, payload):
    response = client.post(BASE, json={**payload, "photo": PHOTO})
    assert response.status_code == 201
    assert response.json()["photo"] == PHOTO


def test_photo_defaults_to_none(client, payload):
    assert client.post(BASE, json=payload).json()["photo"] is None


def test_photo_must_be_an_image_data_url(client, payload):
    response = client.post(BASE, json={**payload, "photo": "https://example.com/a.png"})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "bad",
    [
        "data:image/png;base64,=",  # padding only, decodes to nothing
        "data:image/png;base64,a===b",  # padding in the middle
        "data:image/png;base64,!!!!",  # not base64 at all
        "data:image/png;base64,QUJD",  # valid base64, but the bytes are not a PNG
        "data:image/gif;base64,iVBORw0KGgoAAAANSUhEUg==",  # PNG bytes claiming to be a GIF
        # RIFF, but a WAVE container rather than WebP.
        "data:image/webp;base64,UklGRiQAAABXQVZFZm10IA==",
        # RIFF header too short to carry a FourCC at all.
        "data:image/webp;base64,UklGRgA=",
    ],
)
def test_malformed_photo_payloads_are_rejected(client, payload, bad):
    assert client.post(BASE, json={**payload, "photo": bad}).status_code == 422


def test_oversized_photo_is_rejected(client, payload):
    huge = "data:image/png;base64," + "A" * 3_000_000
    response = client.post(BASE, json={**payload, "photo": huge})
    assert response.status_code == 422


def test_patch_sets_and_clears_photo(client, payload):
    contact_id = client.post(BASE, json=payload).json()["id"]

    assert client.patch(f"{BASE}/{contact_id}", json={"photo": PHOTO}).json()["photo"] == PHOTO
    assert client.patch(f"{BASE}/{contact_id}", json={"photo": None}).json()["photo"] is None


def test_put_without_photo_clears_it(client, payload):
    """PUT is a full replace, so an omitted photo is cleared — the UI must resend it."""
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]

    body = client.put(f"{BASE}/{contact_id}", json=payload).json()
    assert body["photo"] is None


def test_put_preserves_photo_when_resent(client, payload):
    contact_id = client.post(BASE, json={**payload, "photo": PHOTO}).json()["id"]

    body = client.put(f"{BASE}/{contact_id}", json={**payload, "photo": PHOTO}).json()
    assert body["photo"] == PHOTO


# --- addresses (one-to-many) ---------------------------------------------

WORK = {"type": "Work", "street": "1 Market St", "city": "San Francisco", "state": "CA", "country": "USA"}
HOME = {"type": "Home", "street": "12 Hanover Sq", "city": "London", "country": "UK"}


def test_create_contact_with_several_addresses(client, payload):
    body = client.post(BASE, json={**payload, "addresses": [WORK, HOME]}).json()

    assert [a["type"] for a in body["addresses"]] == ["Work", "Home"]
    assert body["addresses"][0]["city"] == "San Francisco"
    # Each address is its own row with its own identity.
    assert len({a["id"] for a in body["addresses"]}) == 2


def test_contact_without_addresses_gets_an_empty_list(client, payload):
    assert client.post(BASE, json=payload).json()["addresses"] == []


def test_two_addresses_may_share_a_type(client, payload):
    """The relationship is one-to-many, not one-per-type."""
    body = client.post(BASE, json={**payload, "addresses": [WORK, {**WORK, "street": "2 Market St"}]}).json()
    assert len(body["addresses"]) == 2


def test_address_type_is_restricted(client, payload):
    response = client.post(BASE, json={**payload, "addresses": [{**WORK, "type": "Vacation"}]})
    assert response.status_code == 422


def test_addresses_survive_a_round_trip(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [WORK, HOME]}).json()["id"]
    fetched = client.get(f"{BASE}/{contact_id}").json()
    assert [a["type"] for a in fetched["addresses"]] == ["Work", "Home"]


def test_put_replaces_the_address_list(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [WORK, HOME]}).json()["id"]

    body = client.put(f"{BASE}/{contact_id}", json={**payload, "addresses": [HOME]}).json()
    assert [a["type"] for a in body["addresses"]] == ["Home"]


def test_put_without_addresses_clears_them(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [WORK]}).json()["id"]
    assert client.put(f"{BASE}/{contact_id}", json=payload).json()["addresses"] == []


def test_patch_leaves_addresses_alone_when_omitted(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [WORK]}).json()["id"]

    body = client.patch(f"{BASE}/{contact_id}", json={"job_title": "Countess"}).json()
    assert [a["type"] for a in body["addresses"]] == ["Work"]


def test_patch_can_replace_or_empty_the_addresses(client, payload):
    contact_id = client.post(BASE, json={**payload, "addresses": [WORK]}).json()["id"]

    assert client.patch(f"{BASE}/{contact_id}", json={"addresses": [HOME]}).json()["addresses"][0]["type"] == "Home"
    assert client.patch(f"{BASE}/{contact_id}", json={"addresses": []}).json()["addresses"] == []


def test_replacing_addresses_does_not_leave_orphan_rows(client, payload):
    """delete-orphan must remove the rows a replace dropped, not just unlink them."""
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import Address

    contact_id = client.post(BASE, json={**payload, "addresses": [WORK, HOME]}).json()["id"]
    client.put(f"{BASE}/{contact_id}", json={**payload, "addresses": [HOME]})

    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(Address)).scalar_one() == 1


def test_deleting_a_contact_deletes_its_addresses(client, payload):
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import Address

    contact_id = client.post(BASE, json={**payload, "addresses": [WORK, HOME]}).json()["id"]
    assert client.delete(f"{BASE}/{contact_id}").status_code == 204

    with SessionLocal() as db:
        assert db.execute(select(func.count()).select_from(Address)).scalar_one() == 0
