from types import SimpleNamespace

from legal_workflow.schemas import AgentStatus
from legal_workflow.service import execute_agent_request
from tests.test_legal_workflow_controller import FakeRepository, RecordingGateway, bootstrap, controller, initial_state


def test_abandoned_new_request_does_not_build_runtime(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("cancelled request must not allocate runtime")

    monkeypatch.setattr("legal_workflow.service.build_agent_runtime", forbidden)
    result = execute_agent_request(
        db=None, user_id=7, settings=None, bootstrap=bootstrap(), finalizer=None, cancelled=lambda: True
    )
    assert result.reason_code == "CLIENT_DISCONNECTED"


def test_cancelled_controller_persists_failure_without_gateway_work():
    repository = FakeRepository(initial_state())
    gateway = RecordingGateway()
    result = controller(repository, SimpleNamespace(), gateway).run("run-a", bootstrap(), cancelled=lambda: True)
    assert result.state.status == AgentStatus.FAILED
    assert repository.checkpoints[-1][1].reason_code == "CLIENT_DISCONNECTED"
    assert not gateway.calls
