"""API tests against the real trained artifacts and a temporary SQLite database."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from recsys.config import PathsConfig, Settings

pytestmark = pytest.mark.real_data


@pytest.fixture(scope="module")
def client(tmp_path_factory, settings):
    if not (settings.p.models_dir / "serving" / "manifest.json").exists():
        pytest.skip("serving artifacts not found (run `uv run recsys train`)")
    db = tmp_path_factory.mktemp("db") / "test_app.db"
    test_settings = Settings(**{**settings.model_dump(), "paths": PathsConfig(**{**settings.paths.model_dump(),
                                                                                  "db_path": db})})
    with TestClient(create_app(test_settings)) as c:
        yield c


def _new_user(client, name="Test user") -> dict:
    r = client.post("/api/users", json={"display_name": name})
    assert r.status_code == 201, r.text
    return r.json()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["engine_loaded"]
    assert body["items_in_db"] == 3883


def test_genres(client):
    names = {g["name"] for g in client.get("/api/genres").json()}
    assert {"Comedy", "Drama", "Sci-Fi", "Film-Noir"} <= names and len(names) == 18


def test_user_crud_and_validation(client):
    user = _new_user(client, "Aysel")
    assert client.get(f"/api/users/{user['id']}").json()["display_name"] == "Aysel"
    assert any(u["id"] == user["id"] for u in client.get("/api/users").json())
    assert client.post("/api/users", json={"display_name": ""}).status_code == 422
    assert client.post("/api/users", json={"display_name": "   "}).status_code == 422
    assert client.get("/api/users/999999").status_code == 404
    assert client.delete(f"/api/users/{user['id']}").status_code == 204
    assert client.get(f"/api/users/{user['id']}").status_code == 404


def test_onboarding_and_cold_start(client):
    user = _new_user(client)
    bad = client.put(f"/api/users/{user['id']}/preferences", json={"genres": ["NotAGenre"]})
    assert bad.status_code == 422
    ok = client.put(f"/api/users/{user['id']}/preferences", json={"genres": ["Animation", "Children's"]})
    assert ok.json()["onboarding_done"] and ok.json()["preferred_genres"] == ["Animation", "Children's"]

    cands = client.get("/api/onboarding/candidates", params={"genres": ["Animation"], "k": 10}).json()
    assert len(cands) == 10
    assert sum("Animation" in c["genres"] for c in cands) >= 8

    recs = client.get(f"/api/users/{user['id']}/recommendations", params={"k": 10}).json()
    assert recs["bucket"] == "cold" and recs["history_size"] == 0
    top = recs["sections"][0]["items"]
    assert len(top) == 10
    assert sum(bool({"Animation", "Children's"} & set(t["item"]["genres"])) for t in top) >= 7

    # CF / content scores are constant for an empty history: those strategies must fall back to cold start
    # instead of returning the first catalog ids with a made-up "Trending" reason.
    for strategy in ("cf", "content"):
        r = client.get(f"/api/users/{user['id']}/recommendations", params={"k": 10, "strategy": strategy}).json()
        picks = r["sections"][0]["items"]
        assert len(picks) == 10 and {t["source"] for t in picks} == {"cold_start"}
        assert [t["item"]["id"] for t in picks] == [t["item"]["id"] for t in top]


def test_ratings_change_recommendations_and_exclude_seen(client):
    user = _new_user(client)
    before = client.get(f"/api/users/{user['id']}/recommendations", params={"k": 10}).json()
    liked = [1, 2355, 3114]  # Toy Story, A Bug's Life, Toy Story 2
    for item_id in liked:
        r = client.put(f"/api/users/{user['id']}/ratings/{item_id}", json={"rating": 5})
        assert r.status_code == 200 and r.json()["rating"] == 5
    after = client.get(f"/api/users/{user['id']}/recommendations", params={"k": 10}).json()
    assert after["bucket"] == "light" and after["history_size"] == 3
    ids_after = [t["item"]["id"] for t in after["sections"][0]["items"]]
    assert not set(liked) & set(ids_after)
    assert ids_after != [t["item"]["id"] for t in before["sections"][0]["items"]]
    assert any(s["key"] == "because_you_liked" for s in after["sections"])

    assert len(client.get(f"/api/users/{user['id']}/ratings").json()) == 3
    assert client.delete(f"/api/users/{user['id']}/ratings/1").status_code == 204
    assert len(client.get(f"/api/users/{user['id']}/ratings").json()) == 2


def test_explanations_never_cite_a_disliked_film(client):
    user = _new_user(client)
    assert client.put(f"/api/users/{user['id']}/ratings/1", json={"rating": 1}).status_code == 200
    recs = client.get(f"/api/users/{user['id']}/recommendations", params={"k": 10}).json()
    reasons = [t["reason"] for t in recs["sections"][0]["items"]]
    assert len(reasons) == 10 and not any(r.startswith("Because you liked") for r in reasons)


def test_rating_validation(client):
    user = _new_user(client)
    assert client.put(f"/api/users/{user['id']}/ratings/1", json={"rating": 6}).status_code == 422
    assert client.put(f"/api/users/{user['id']}/ratings/1", json={"rating": 0}).status_code == 422
    assert client.put(f"/api/users/{user['id']}/ratings/99999999", json={"rating": 4}).status_code == 404
    assert client.put("/api/users/99999999/ratings/1", json={"rating": 4}).status_code == 404


def test_favorites_and_history(client):
    user = _new_user(client)
    assert client.put(f"/api/users/{user['id']}/favorites/260").status_code == 200  # Star Wars
    assert client.put(f"/api/users/{user['id']}/favorites/260").status_code == 200  # idempotent
    favs = client.get(f"/api/users/{user['id']}/favorites").json()
    assert [f["item"]["id"] for f in favs] == [260]
    detail = client.get("/api/items/260", params={"user_id": user["id"]}).json()
    assert detail["is_favorite"] is True
    r = client.post(f"/api/users/{user['id']}/interactions", json={"kind": "search", "query": "space"})
    assert r.status_code == 201
    kinds = [h["kind"] for h in client.get(f"/api/users/{user['id']}/history").json()]
    assert kinds[0] == "search" and "favorite" in kinds
    assert client.delete(f"/api/users/{user['id']}/favorites/260").status_code == 204
    assert client.get(f"/api/users/{user['id']}/favorites").json() == []


def _concurrently(fn, n: int = 4) -> list:
    """Fire ``fn`` from n threads at once (a rapid double-click); return status codes or raised exceptions."""
    barrier, out = threading.Barrier(n), []

    def run():
        barrier.wait()
        try:
            out.append(fn().status_code)
        except Exception as exc:  # noqa: BLE001 - the server error is what the test reports
            out.append(repr(exc))

    threads = [threading.Thread(target=run) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


def test_concurrent_duplicate_writes_do_not_fail(client):
    # Two quick clicks send the same PUT/POST twice; the loser of the insert race used to hit a UNIQUE error (500).
    user = _new_user(client)
    uid = user["id"]
    assert _concurrently(lambda: client.put(f"/api/users/{uid}/ratings/1", json={"rating": 4})) == [200] * 4
    assert _concurrently(lambda: client.put(f"/api/users/{uid}/favorites/1")) == [200] * 4
    prefs = {"genres": ["Comedy", "Drama", "War"]}
    assert _concurrently(lambda: client.put(f"/api/users/{uid}/preferences", json=prefs)) == [200] * 4
    assert _concurrently(lambda: client.post("/api/users/from-movielens/2")) == [200] * 4

    assert [r["rating"] for r in client.get(f"/api/users/{uid}/ratings").json()] == [4]
    assert [f["item"]["id"] for f in client.get(f"/api/users/{uid}/favorites").json()] == [1]
    assert client.get(f"/api/users/{uid}").json()["preferred_genres"] == prefs["genres"]
    kinds = [h["kind"] for h in client.get(f"/api/users/{uid}/history").json()]
    assert kinds.count("favorite") == 1 and kinds.count("rate") == 4  # one "added" event, every rating logged
    assert sum(u["ml_user_id"] == 2 for u in client.get("/api/users").json()) == 1


def test_movielens_profile_gets_warm_recommendations(client, engine):
    r = client.post("/api/users/from-movielens/1")
    assert r.status_code == 200
    user = r.json()
    assert user["ml_user_id"] == 1
    assert client.post("/api/users/from-movielens/1").json()["id"] == user["id"]  # idempotent
    recs = client.get(f"/api/users/{user['id']}/recommendations", params={"k": 20}).json()
    assert recs["bucket"] == "warm"
    seen = {i for i, _ in engine.movielens_history(1)}
    assert not seen & {t["item"]["id"] for t in recs["sections"][0]["items"]}
    assert client.post("/api/users/from-movielens/999999").status_code == 404


def test_keyword_and_semantic_search(client):
    res = client.get("/api/search", params={"q": "toy story"}).json()
    assert res["results"][0]["item"]["title"].startswith("Toy Story")
    comedy = client.get("/api/search", params={"q": "love", "genre": "Comedy", "year_from": 1990}).json()
    assert all("Comedy" in r["item"]["genres"] and r["item"]["year"] >= 1990 for r in comedy["results"])
    # Filters apply to every keyword match, not to a truncated top-N pool (78 War films match "drama").
    war = client.get("/api/search", params={"q": "drama", "genre": "War", "k": 100}).json()
    assert war["total"] > 50 and len(war["results"]) == war["total"]
    assert all("War" in r["item"]["genres"] for r in war["results"])
    if client.get("/api/health").json()["semantic_search"]:
        sem = client.get("/api/search", params={"q": "animated toys come to life", "mode": "semantic",
                                                "k": 10}).json()
        assert any(r["item"]["id"] in (1, 3114) for r in sem["results"])
        blank = client.get("/api/search", params={"q": "   ", "mode": "semantic"}).json()
        assert blank["total"] == 0 and blank["results"] == []


def test_item_detail_and_similar(client):
    item = client.get("/api/items/2571").json()  # The Matrix
    assert item["title"] == "The Matrix" and item["year"] == 1999 and item["n_ratings"] > 1000
    sims = client.get("/api/items/2571/similar", params={"k": 10}).json()
    assert len(sims) == 10 and 2571 not in [s["item"]["id"] for s in sims]
    assert all(s["score"] > 0 for s in sims)
    assert client.get("/api/items/99999999").status_code == 404


def test_timestamps_carry_utc_offset(client):
    # SQLite hands back naive datetimes; without an offset the browser shows the stored UTC time as local time.
    user = _new_user(client)
    stamps = [
        user["created_at"],
        client.put(f"/api/users/{user['id']}/ratings/1", json={"rating": 4}).json()["created_at"],
        client.put(f"/api/users/{user['id']}/favorites/2").json()["created_at"],
        client.get(f"/api/users/{user['id']}/ratings").json()[0]["created_at"],
        client.get(f"/api/users/{user['id']}/history").json()[0]["created_at"],
    ]
    assert all(datetime.fromisoformat(s).utcoffset() == timedelta(0) for s in stamps), stamps


def test_discovery_endpoints(client):
    assert len(client.get("/api/items/trending", params={"k": 5}).json()) == 5
    top = client.get("/api/items/top-rated", params={"k": 5, "genre": "Film-Noir"}).json()
    assert all("Film-Noir" in t["genres"] for t in top)
    page = client.get("/api/genres/Western/items", params={"limit": 5, "sort": "popular"}).json()
    assert page["total"] > 5 and len(page["items"]) == 5
    assert client.get("/api/genres/NotAGenre/items").status_code == 404


def test_model_endpoints_serve_report_verbatim(client, settings):
    served = client.get("/api/model/evaluation").json()
    on_disk = json.loads((settings.p.reports_dir / "model_comparison.json").read_text(encoding="utf-8"))
    assert served == on_disk
    info = client.get("/api/model/info").json()
    assert info["serving"]["selected_model"] == on_disk["selection"]["selected"]
    eda = client.get("/api/model/eda").json()
    assert eda["n_interactions"] == 1_000_209
    assert client.get("/api/model/eda/charts/rating_distribution.png").headers["content-type"] == "image/png"
    assert client.get("/api/model/eda/charts/../../secret.png").status_code == 404


def test_degraded_mode_without_engine(tmp_path, settings):
    s = Settings(**{**settings.model_dump(), "paths": PathsConfig(**{**settings.paths.model_dump(),
                                                                     "db_path": tmp_path / "x.db"})})
    with TestClient(create_app(s, load_engine=False)) as c:
        assert c.get("/api/health").json()["status"] == "degraded"
        user = c.post("/api/users", json={"display_name": "x"}).json()
        r = c.get(f"/api/users/{user['id']}/recommendations")
        assert r.status_code == 503 and "recsys" in r.json()["detail"]


def test_unknown_genre_filters_are_rejected(client):
    user = _new_user(client)
    for path, params in [
        (f"/api/users/{user['id']}/recommendations", {"genre": "Nope"}),
        ("/api/items/trending", {"genre": "Nope"}),
        ("/api/items/top-rated", {"genre": "Nope"}),
        ("/api/onboarding/candidates", {"genres": ["Comedy", "Nope"]}),
        ("/api/search", {"q": "love", "genre": "Nope"}),
    ]:
        r = client.get(path, params=params)
        assert r.status_code == 422, (path, r.status_code)
        assert "Nope" in r.json()["detail"]


def test_popularity_strategy_does_not_claim_personal_reasons(client):
    user = _new_user(client)
    for item_id in (1, 2355, 3114):
        client.put(f"/api/users/{user['id']}/ratings/{item_id}", json={"rating": 5})
    recs = client.get(f"/api/users/{user['id']}/recommendations", params={"strategy": "popularity", "k": 10}).json()
    reasons = [t["reason"] for t in recs["sections"][0]["items"]]
    assert reasons and not any(r.startswith("Because you liked") for r in reasons)


def test_poster_endpoint_matches_poster_url(client):
    detail = client.get("/api/items/1").json()
    if detail["poster_url"] is None:
        assert client.get("/api/items/1/poster").status_code == 404
        pytest.skip("no cached posters (run `uv run recsys download-posters`)")
    r = client.get(detail["poster_url"])
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    assert client.get("/api/items/99999999/poster").status_code == 404
