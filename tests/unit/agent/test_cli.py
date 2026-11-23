from copy import deepcopy

from src.agent import cli


class FakeApiClient:
    def set_execution_deadline(self, deadline):
        pass


class FakeGraph:
    def __init__(self):
        self.calls = []

    def invoke(self, state, config):
        self.calls.append((deepcopy(state), deepcopy(config)))
        return {**state, "answer": "Resposta de teste."}


def test_each_cli_run_starts_an_isolated_conversation(monkeypatch, capsys):
    conversation_ids = iter(("conversation-a", "conversation-b"))
    graph = FakeGraph()
    monkeypatch.setattr(cli, "uuid4", lambda: next(conversation_ids))
    monkeypatch.setattr(cli, "configure_tracing", lambda: None)
    monkeypatch.setattr(cli, "ApiClient", FakeApiClient)
    monkeypatch.setattr(cli.llm, "create_client", lambda: object())
    monkeypatch.setattr(cli, "create_policy_retriever", lambda: object())
    monkeypatch.setattr(cli, "build_scheduling_graph", lambda *_: graph)

    assert cli.run_scheduling_flow("Mensagem A.", interactive=False) == (
        "Resposta de teste."
    )
    assert cli.run_scheduling_flow("Mensagem B.", interactive=False) == (
        "Resposta de teste."
    )
    capsys.readouterr()

    assert len(graph.calls) == 2
    for (state, config), expected_id, expected_message in zip(
        graph.calls,
        ("conversation-a", "conversation-b"),
        ("Mensagem A.", "Mensagem B."),
        strict=True,
    ):
        assert state["conversation_id"] == expected_id
        assert config["configurable"]["thread_id"] == expected_id
        assert state["messages"][-1] == {
            "role": "user",
            "content": expected_message,
        }


def test_scheduling_case_keeps_tool_results_for_every_turn(monkeypatch):
    class MultiTurnGraph:
        def invoke(self, state, config):
            user_message = state["messages"][-1]["content"]
            return {
                **state,
                "answer": f"Resposta para {user_message}",
                "tool_results": [
                    {"name": "consulta_demo", "result": {"turn": user_message}}
                ],
            }

    graph = MultiTurnGraph()
    monkeypatch.setattr(cli, "configure_tracing", lambda: None)
    monkeypatch.setattr(cli, "ApiClient", FakeApiClient)
    monkeypatch.setattr(cli.llm, "create_client", lambda: object())
    monkeypatch.setattr(cli, "create_policy_retriever", lambda: object())
    monkeypatch.setattr(cli, "build_scheduling_graph", lambda *_: graph)

    result = cli.run_scheduling_case(["primeiro turno", "segundo turno"])

    assert [turn["input"] for turn in result["turns"]] == [
        "primeiro turno",
        "segundo turno",
    ]
    assert [item["result"]["turn"] for item in result["tool_results"]] == [
        "primeiro turno",
        "segundo turno",
    ]
