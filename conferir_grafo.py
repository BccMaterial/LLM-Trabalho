from src.agent.workflows.scheduling import build_scheduling_graph


def main() -> None:
    graph = build_scheduling_graph(llm_client=None, api_client=None)
    graph_view = graph.get_graph()

    print("Nos:")
    for node_name in sorted(graph_view.nodes):
        print(f"  {node_name}")

    print("Arestas:")
    for edge in sorted(
        graph_view.edges,
        key=lambda item: (item.source, item.target, item.conditional),
    ):
        edge_type = "condicional" if edge.conditional else "direta"
        print(f"  {edge.source} -> {edge.target} [{edge_type}]")


if __name__ == "__main__":
    main()
