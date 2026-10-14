"""Hard-delete helpers: leftover files, prefix isolation, content-free audit."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

from app.deletion import (
    CONTENT_KEYS,
    DictObjectStore,
    S3ObjectStore,
    assert_no_content,
    audit_details,
    count_files,
    delete_local_prefix,
    local_session_dir,
    session_object_prefix,
)


SESSION_A = "11111111-1111-4111-8111-111111111111"
SESSION_B = "22222222-2222-4222-8222-222222222222"
USER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_session_object_prefix_matches_spec_layout():
    prefix = session_object_prefix(USER_A, SESSION_A)
    assert prefix == f"users/{USER_A}/sessions/{SESSION_A}/"
    assert prefix.startswith("users/")
    assert "derived" not in prefix


def test_local_session_dir_rejects_escape_and_root(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    inside = local_session_dir(root, SESSION_A)
    assert inside == (root / SESSION_A).resolve()
    with pytest.raises(ValueError):
        local_session_dir(root, "..")
    with pytest.raises(ValueError):
        local_session_dir(root, ".")
    with pytest.raises(ValueError):
        local_session_dir(root, "../secret")


def test_delete_local_prefix_removes_session_files_only(tmp_path):
    root = tmp_path / "media"
    session_dir = root / SESSION_A
    other_dir = root / SESSION_B
    (session_dir / "upload").mkdir(parents=True)
    (session_dir / "derived").mkdir()
    (session_dir / "upload" / "original.bin").write_bytes(b"not-a-recording")
    (session_dir / "derived" / "report.json").write_text("{}")
    (session_dir / "derived" / "transcript.json").write_text('{"segments":[]}')
    other_dir.mkdir(parents=True)
    keep = other_dir / "keep.bin"
    keep.write_bytes(b"keep-me")
    shared = root / "smoke-fixture"
    shared.mkdir()
    (shared / "report.json").write_text("{}")

    deleted = delete_local_prefix(session_dir, root)
    assert deleted == 3
    assert not session_dir.exists()
    assert count_files(session_dir) == 0
    assert keep.is_file()
    assert (shared / "report.json").is_file()


def test_delete_local_prefix_refuses_media_root(tmp_path):
    root = tmp_path / "media"
    root.mkdir()
    (root / "keep.bin").write_bytes(b"x")
    with pytest.raises(ValueError):
        delete_local_prefix(root, root)
    assert (root / "keep.bin").is_file()


def test_dict_object_store_deletes_only_matching_prefix():
    prefix_a = session_object_prefix(USER_A, SESSION_A)
    prefix_b = session_object_prefix(USER_A, SESSION_B)
    store = DictObjectStore(
        [
            f"{prefix_a}original/clip.bin",
            f"{prefix_a}derived/job/report.json",
            f"{prefix_b}original/other.bin",
        ]
    )
    deleted = store.delete_prefix(prefix_a)
    assert deleted == 2
    assert store.remaining(prefix_a) == 0
    assert store.remaining(prefix_b) == 1
    assert f"{prefix_b}original/other.bin" in store.keys


class _FakeS3:
    def __init__(self, keys: list[str]):
        self.keys = set(keys)

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken=None):
        matching = sorted(key for key in self.keys if key.startswith(Prefix))
        return {"Contents": [{"Key": key} for key in matching], "IsTruncated": False}

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            self.keys.discard(item["Key"])
        return {}


def test_s3_object_store_prefix_delete_leaves_other_keys():
    prefix_a = session_object_prefix(USER_A, SESSION_A)
    prefix_b = session_object_prefix(USER_A, SESSION_B)
    fake = _FakeS3(
        [
            f"{prefix_a}original/a.bin",
            f"{prefix_a}derived/t.json",
            f"{prefix_b}original/b.bin",
        ]
    )
    store = S3ObjectStore(fake, bucket="stagecoach")
    assert store.delete_prefix(prefix_a) == 2
    assert store.remaining(prefix_a) == 0
    assert store.remaining(prefix_b) == 1


def test_audit_details_are_counts_only():
    details = audit_details(
        object_count=3,
        db_rows={"sessions": 1, "transcripts": 1, "insights": 1},
        prefixes=["local", "object_store"],
    )
    assert details["object_count"] == 3
    assert details["db_rows"]["transcripts"] == 1
    assert details["prefixes"] == ["local", "object_store"]
    for key in details:
        assert key.lower() not in CONTENT_KEYS


@pytest.mark.parametrize("key", sorted(CONTENT_KEYS))
def test_assert_no_content_rejects_content_keys(key):
    with pytest.raises(ValueError, match="must not contain"):
        assert_no_content({key: "secret-talk-text"})


def test_assert_no_content_rejects_nested_and_long_strings():
    with pytest.raises(ValueError):
        assert_no_content({"db_rows": {"title": "My confidential keynote"}})
    with pytest.raises(ValueError):
        assert_no_content({"note": "x" * 201})
    assert_no_content({"object_count": 1, "search_index": "not_deployed"})
