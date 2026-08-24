"""Teste de carga. Uso:
    uv run locust -f bench/locustfile.py --host http://localhost:8000 \
        -u 20 -r 2 -t 60s --headless --csv results/load
Depois: uv run python -m bench.load_report results/load_stats.csv > results/load_test.md
"""
import random

from locust import HttpUser, between, task

QUESTIONS = [
    "Quantos dias de férias tenho direito por ano?",
    "Posso vender parte das minhas férias?",
    "Quantos dias por semana posso trabalhar remoto?",
    "Qual o valor do reembolso de internet no home office?",
    "Qual a garantia do notebook da empresa?",
    "Qual o valor do vale-refeição?",
    "Qual o SLA para ticket de prioridade alta?",
    "Quantos dias de licença-maternidade tenho direito?",
]


class ChatUser(HttpUser):
    wait_time = between(0.5, 2)

    @task
    def chat(self):
        self.client.post("/chat", json={
            "question": random.choice(QUESTIONS),
            "session_id": f"load-{id(self)}",
        }, name="/chat")
