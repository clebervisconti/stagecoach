"""Guards for storing the original recording length. No database required."""

from pipeline.media_duration import persist_original_duration

SESSION = "11111111-1111-4111-8111-111111111111"


def test_persist_original_duration_rejects_values_it_cannot_store(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert persist_original_duration(SESSION, None) is False
    assert persist_original_duration(SESSION, 0) is False
    assert persist_original_duration(SESSION, -4) is False
    assert persist_original_duration(SESSION, float("nan")) is False
    assert persist_original_duration("not-a-uuid", 12.5, database_url="postgresql://stagecoach@127.0.0.1/none") is False
    assert persist_original_duration("", 12.5, database_url="postgresql://stagecoach@127.0.0.1/none") is False
    assert persist_original_duration(SESSION, 12.5, database_url="") is False
