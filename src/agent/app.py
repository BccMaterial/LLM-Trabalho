from .cli import run_scheduling_flow
from .demo_data import populate_example_data

if __name__ == "__main__":
    print("Executando demonstração de solicitação de agendamento...")
    populate_example_data()
    print(run_scheduling_flow())
