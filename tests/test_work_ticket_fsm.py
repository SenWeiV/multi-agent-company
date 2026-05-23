from __future__ import annotations

import pytest

from app.company.models import (
    TERMINAL_STATUSES,
    VALID_TRANSITIONS,
    WorkTicket,
    WorkTicketStatus,
)
from app.control_plane.services import WorkTicketService
from app.store.base import InMemoryModelStore


def _ticket(status: WorkTicketStatus = WorkTicketStatus.DRAFT) -> WorkTicket:
    return WorkTicket(
        ticket_id="tk-001",
        title="Test ticket",
        ticket_type="task",
        status=status,
    )


# --- 合法状态转换 ---


class TestValidTransitions:
    def test_draft_to_submitted(self):
        ticket = _ticket(WorkTicketStatus.DRAFT).transition_to(WorkTicketStatus.SUBMITTED)
        assert ticket.status == WorkTicketStatus.SUBMITTED

    def test_submitted_to_working(self):
        ticket = _ticket(WorkTicketStatus.SUBMITTED).transition_to(WorkTicketStatus.WORKING)
        assert ticket.status == WorkTicketStatus.WORKING

    def test_working_to_review(self):
        ticket = _ticket(WorkTicketStatus.WORKING).transition_to(WorkTicketStatus.REVIEW)
        assert ticket.status == WorkTicketStatus.REVIEW

    def test_review_to_completed(self):
        ticket = _ticket(WorkTicketStatus.REVIEW).transition_to(WorkTicketStatus.COMPLETED)
        assert ticket.status == WorkTicketStatus.COMPLETED

    def test_working_to_blocked(self):
        ticket = _ticket(WorkTicketStatus.WORKING).transition_to(WorkTicketStatus.BLOCKED)
        assert ticket.status == WorkTicketStatus.BLOCKED

    def test_blocked_to_working(self):
        ticket = _ticket(WorkTicketStatus.BLOCKED).transition_to(WorkTicketStatus.WORKING)
        assert ticket.status == WorkTicketStatus.WORKING

    def test_working_to_failed(self):
        ticket = _ticket(WorkTicketStatus.WORKING).transition_to(WorkTicketStatus.FAILED)
        assert ticket.status == WorkTicketStatus.FAILED

    def test_any_non_terminal_to_canceled(self):
        for status in WorkTicketStatus:
            if status in TERMINAL_STATUSES:
                continue
            allowed = VALID_TRANSITIONS.get(status, set())
            if WorkTicketStatus.CANCELED in allowed:
                ticket = _ticket(status).transition_to(WorkTicketStatus.CANCELED)
                assert ticket.status == WorkTicketStatus.CANCELED


# --- 非法状态转换 ---


class TestInvalidTransitions:
    def test_completed_to_working_raises(self):
        with pytest.raises(ValueError, match="terminal"):
            _ticket(WorkTicketStatus.COMPLETED).transition_to(WorkTicketStatus.WORKING)

    def test_draft_to_completed_raises(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            _ticket(WorkTicketStatus.DRAFT).transition_to(WorkTicketStatus.COMPLETED)

    def test_failed_to_working_raises(self):
        with pytest.raises(ValueError, match="terminal"):
            _ticket(WorkTicketStatus.FAILED).transition_to(WorkTicketStatus.WORKING)

    def test_canceled_to_any_raises(self):
        with pytest.raises(ValueError, match="terminal"):
            _ticket(WorkTicketStatus.CANCELED).transition_to(WorkTicketStatus.DRAFT)


# --- 终态不可变 ---


class TestTerminalStatuses:
    def test_completed_is_terminal(self):
        assert WorkTicketStatus.COMPLETED in TERMINAL_STATUSES

    def test_failed_is_terminal(self):
        assert WorkTicketStatus.FAILED in TERMINAL_STATUSES

    def test_canceled_is_terminal(self):
        assert WorkTicketStatus.CANCELED in TERMINAL_STATUSES

    def test_draft_is_not_terminal(self):
        assert WorkTicketStatus.DRAFT not in TERMINAL_STATUSES

    def test_working_is_not_terminal(self):
        assert WorkTicketStatus.WORKING not in TERMINAL_STATUSES


# --- transition_to 不改变原对象 ---


class TestImmutability:
    def test_transition_returns_new_instance(self):
        original = _ticket(WorkTicketStatus.DRAFT)
        transitioned = original.transition_to(WorkTicketStatus.SUBMITTED)
        assert original.status == WorkTicketStatus.DRAFT
        assert transitioned.status == WorkTicketStatus.SUBMITTED
        assert original is not transitioned


# --- WorkTicketService 集成 ---


class TestWorkTicketServiceFSM:
    def _make_service(self) -> WorkTicketService:
        store: InMemoryModelStore[WorkTicket] = InMemoryModelStore(lambda t: t.ticket_id)
        return WorkTicketService(store)

    def test_service_transition_updates_store(self):
        service = self._make_service()
        ticket = _ticket(WorkTicketStatus.DRAFT)
        service._store.save(ticket)
        updated = service.set_status("tk-001", WorkTicketStatus.SUBMITTED)
        assert updated.status == WorkTicketStatus.SUBMITTED
        stored = service.get("tk-001")
        assert stored is not None
        assert stored.status == WorkTicketStatus.SUBMITTED

    def test_service_transition_invalid_raises_and_does_not_mutate(self):
        service = self._make_service()
        ticket = _ticket(WorkTicketStatus.DRAFT)
        service._store.save(ticket)
        with pytest.raises(ValueError):
            service.set_status("tk-001", WorkTicketStatus.COMPLETED)
        stored = service.get("tk-001")
        assert stored is not None
        assert stored.status == WorkTicketStatus.DRAFT

    def test_service_set_status_backward_compat_with_string(self):
        service = self._make_service()
        ticket = _ticket(WorkTicketStatus.DRAFT)
        service._store.save(ticket)
        updated = service.set_status("tk-001", "submitted")
        assert updated.status == WorkTicketStatus.SUBMITTED


# --- 向后兼容旧状态 ---


class TestLegacyStatusCompat:
    def test_legacy_captured_can_transition_to_working(self):
        ticket = _ticket(WorkTicketStatus.CAPTURED).transition_to(WorkTicketStatus.WORKING)
        assert ticket.status == WorkTicketStatus.WORKING

    def test_legacy_consulting_can_transition_to_completed(self):
        ticket = _ticket(WorkTicketStatus.CONSULTING).transition_to(WorkTicketStatus.COMPLETED)
        assert ticket.status == WorkTicketStatus.COMPLETED

    def test_legacy_queued_can_transition_to_working(self):
        ticket = _ticket(WorkTicketStatus.QUEUED).transition_to(WorkTicketStatus.WORKING)
        assert ticket.status == WorkTicketStatus.WORKING
