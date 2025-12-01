#!/usr/bin/env python3
"""Add notification before N2 escalation so user gets email on N1 failure"""
import requests
import json

N8N_API_URL = "https://n8n.aurastackai.com/api/v1"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkN2Q3ZTM2Mi1kMjJhLTQ4OWYtYTdkMi1lNjNjNGNmNjU3OTAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzYyNjk5MTUwfQ.Gi6k_zcap4NUNKQTrEf8BM1DAwbv-iV5eVYV2VoS44U"
WORKFLOW_ID = "m239OOMCarIbNa7C"

headers = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json"
}

response = requests.get(f"{N8N_API_URL}/workflows/{WORKFLOW_ID}", headers=headers)
w = response.json()

print(f"Workflow: {w['name']}")

# Add node to notify on failure before escalation
notify_failure_node = {
    "parameters": {
        "url": "https://n8n.aurastackai.com/webhook/auto-repare/notify",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={ \"type\": \"failure\", \"incident\": {{ JSON.stringify($('Evaluer Resultat').item.json) }} }",
        "options": {
            "timeout": 30000,
            "retry": {"maxRetries": 2, "waitBetweenRetries": 2000}
        },
        "method": "POST"
    },
    "id": "notify-failure",
    "name": "Notifier Echec",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": [3088, 100]  # Between Qdrant - Stocker Echec and Escalader N2
}

# Check if node exists
exists = any(n['name'] == 'Notifier Echec' for n in w['nodes'])
if not exists:
    w['nodes'].append(notify_failure_node)
    print("[OK] Added Notifier Echec node")
else:
    print("[SKIP] Notifier Echec already exists")

# Update connections: Qdrant - Stocker Echec -> Notifier Echec -> Escalader N2
# Find and update
for src, conns in w['connections'].items():
    if src == 'Qdrant - Stocker Echec':
        # Change from Escalader N2 to Notifier Echec
        w['connections'][src] = {"main": [[{"node": "Notifier Echec", "type": "main", "index": 0}]]}
        print("[OK] Updated Qdrant - Stocker Echec -> Notifier Echec")

# Add connection Notifier Echec -> Escalader N2
w['connections']['Notifier Echec'] = {"main": [[{"node": "Escalader N2", "type": "main", "index": 0}]]}
print("[OK] Added Notifier Echec -> Escalader N2")

# Update workflow
clean_data = {
    "name": w["name"],
    "nodes": w["nodes"],
    "connections": w["connections"],
    "settings": {"executionOrder": "v1"}
}

response = requests.put(
    f"{N8N_API_URL}/workflows/{WORKFLOW_ID}",
    headers=headers,
    json=clean_data
)

if response.status_code == 200:
    print("[OK] Workflow updated")
else:
    print(f"[ERROR] {response.status_code}: {response.text}")
