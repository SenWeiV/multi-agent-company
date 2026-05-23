from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Stub minio (with submodules) before importing app.feishu.services
_minio_mock = MagicMock()
_minio_error_mock = ModuleType("minio.error")
_minio_error_mock.S3Error = type("S3Error", (Exception,), {})
sys.modules.setdefault("minio", _minio_mock)
sys.modules.setdefault("minio.error", _minio_error_mock)

from app.feishu.models import FeishuOutboundMessageRecord
from app.feishu.services import FeishuSurfaceAdapterService
from app.store.base import InMemoryModelStore


def _make_failed_record(
    outbound_id: str,
    created_at: datetime | None = None,
    resolved_at: datetime | None = None,
    replayed_by_outbound_ref: str | None = None,
) -> FeishuOutboundMessageRecord:
    return FeishuOutboundMessageRecord(
        outbound_id=outbound_id,
        app_id="app-001",
        receive_id_type="chat_id",
        receive_id="oc_abc",
        text="test message",
        status="failed",
        error_detail="send failed",
        created_at=created_at or datetime.now(UTC),
        last_attempt_at=created_at or datetime.now(UTC),
        resolved_at=resolved_at,
        replayed_by_outbound_ref=replayed_by_outbound_ref,
    )


def _make_sent_record(outbound_id: str) -> FeishuOutboundMessageRecord:
    return FeishuOutboundMessageRecord(
        outbound_id=outbound_id,
        app_id="app-001",
        receive_id_type="chat_id",
        receive_id="oc_abc",
        text="test message",
        status="sent",
        created_at=datetime.now(UTC),
        last_attempt_at=datetime.now(UTC),
    )


class TestListDeadLetters:
    def test_returns_only_unresolved(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        # Unresolved failed
        store.save(_make_failed_record("dl-001"))
        # Resolved by resolved_at
        store.save(_make_failed_record("dl-002", resolved_at=datetime.now(UTC)))
        # Resolved by replayed_by_outbound_ref
        store.save(_make_failed_record("dl-003", replayed_by_outbound_ref="replay-001"))
        # Successful record (not a dead letter)
        store.save(_make_sent_record("sent-001"))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        dead_letters = service.list_dead_letters(include_resolved=False)
        assert len(dead_letters) == 1
        assert dead_letters[0].outbound_id == "dl-001"

    def test_include_resolved_returns_all_failed(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        store.save(_make_failed_record("dl-001"))
        store.save(_make_failed_record("dl-002", resolved_at=datetime.now(UTC)))
        store.save(_make_failed_record("dl-003", replayed_by_outbound_ref="replay-001"))
        store.save(_make_sent_record("sent-001"))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        dead_letters = service.list_dead_letters(include_resolved=True)
        assert len(dead_letters) == 3


class TestResolveDeadLetter:
    def test_resolve_marks_resolved_at(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        store.save(_make_failed_record("dl-001"))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        result = service.resolve_dead_letter("dl-001")
        assert result.resolved_at is not None
        assert result.outbound_id == "dl-001"
        # Verify persisted
        persisted = store.get("dl-001")
        assert persisted is not None
        assert persisted.resolved_at is not None

    def test_resolve_non_failed_raises(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        store.save(_make_sent_record("sent-001"))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        with pytest.raises(ValueError, match="Only failed messages can be resolved"):
            service.resolve_dead_letter("sent-001")

    def test_resolve_already_resolved_is_idempotent(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        original_time = datetime.now(UTC) - timedelta(hours=1)
        store.save(_make_failed_record("dl-001", resolved_at=original_time))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        result = service.resolve_dead_letter("dl-001")
        # Should keep original resolved_at (idempotent)
        assert result.resolved_at == original_time


class TestBulkResolveDeadLetters:
    def test_resolves_failed_before_cutoff(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        old_time = datetime.now(UTC) - timedelta(days=7)
        recent_time = datetime.now(UTC) - timedelta(hours=1)

        store.save(_make_failed_record("dl-old-001", created_at=old_time))
        store.save(_make_failed_record("dl-old-002", created_at=old_time))
        store.save(_make_failed_record("dl-recent-001", created_at=recent_time))
        store.save(_make_sent_record("sent-001"))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        cutoff = datetime.now(UTC) - timedelta(days=1)
        count = service.bulk_resolve_dead_letters(before=cutoff)
        assert count == 2

        # Old ones are resolved
        assert store.get("dl-old-001").resolved_at is not None
        assert store.get("dl-old-002").resolved_at is not None
        # Recent one is still unresolved
        assert store.get("dl-recent-001").resolved_at is None

    def test_skips_already_resolved(self):
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        old_time = datetime.now(UTC) - timedelta(days=7)

        store.save(_make_failed_record("dl-001", created_at=old_time, resolved_at=datetime.now(UTC)))
        store.save(_make_failed_record("dl-002", created_at=old_time))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        cutoff = datetime.now(UTC)
        count = service.bulk_resolve_dead_letters(before=cutoff)
        assert count == 1  # Only dl-002


class TestReplayAuditNoUnexplainedFailures:
    def test_all_dead_letters_can_be_resolved_or_replayed(self):
        """Verifies that any dead letter is either resolvable or replayable."""
        store: InMemoryModelStore[FeishuOutboundMessageRecord] = InMemoryModelStore(key_getter=lambda r: r.outbound_id)
        store.save(_make_failed_record("dl-001"))
        store.save(_make_failed_record("dl-002"))

        service = FeishuSurfaceAdapterService.__new__(FeishuSurfaceAdapterService)
        service._outbound = store

        dead_letters = service.list_dead_letters()
        for dl in dead_letters:
            assert dl.status == "failed"
            assert dl.error_detail is not None
            resolved = service.resolve_dead_letter(dl.outbound_id)
            assert resolved.resolved_at is not None

        # After resolving all, no unresolved dead letters remain
        remaining = service.list_dead_letters()
        assert len(remaining) == 0
