#!/usr/bin/env python3
"""Add failure email template to Notification Manager"""
import requests
import json

N8N_API_URL = "https://n8n.aurastackai.com/api/v1"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkN2Q3ZTM2Mi1kMjJhLTQ4OWYtYTdkMi1lNjNjNGNmNjU3OTAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzYyNjk5MTUwfQ.Gi6k_zcap4NUNKQTrEf8BM1DAwbv-iV5eVYV2VoS44U"
WORKFLOW_ID = "Z796nTTfPwJ7Zo90"

headers = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json"
}

response = requests.get(f"{N8N_API_URL}/workflows/{WORKFLOW_ID}", headers=headers)
w = response.json()

print(f"Workflow: {w['name']}")

# Modify the Type de Notification to handle 3 types: success, failure, escalation
# Currently it only checks for success -> else escalation
# We need: success, failure (new), else escalation

# Add failure type check node
check_failure = {
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
            "conditions": [{"id": "cond-failure", "leftValue": "={{ $json.type }}", "rightValue": "failure", "operator": {"type": "string", "operation": "equals"}}],
            "combinator": "and"
        },
        "options": {}
    },
    "id": "check-failure",
    "name": "Type Failure?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [448, 0]
}

# Add failure email generator
gen_failure_email = {
    "parameters": {
        "jsCode": '''const data = $input.first().json;
const incident = data.incident || data;
const html = '<html><body style="font-family:Arial;background:#fef2f2;padding:20px;"><div style="max-width:600px;margin:0 auto;background:white;border-radius:8px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);"><div style="background:linear-gradient(135deg,#ef4444,#dc2626);color:white;padding:30px;text-align:center;"><div style="font-size:48px;margin-bottom:10px;">⚠️</div><h1 style="margin:0;font-size:24px;">Auto-Reparation Echouee</h1><p style="margin:10px 0 0;opacity:0.9;">Escalade niveau 2 en cours</p></div><div style="padding:30px;"><div style="background:#fef2f2;border-left:4px solid #ef4444;padding:15px;margin:15px 0;"><div style="color:#6b7280;font-size:12px;text-transform:uppercase;margin-bottom:5px;">Incident ID</div><div style="color:#111827;font-size:16px;font-weight:500;">' + (incident.incident_id || 'N/A') + '</div></div><div style="background:#fef2f2;border-left:4px solid #ef4444;padding:15px;margin:15px 0;"><div style="color:#6b7280;font-size:12px;text-transform:uppercase;margin-bottom:5px;">Service</div><div style="color:#111827;font-size:16px;font-weight:500;">' + (incident.service_name || 'N/A') + '</div></div><div style="background:#fef2f2;border-left:4px solid #ef4444;padding:15px;margin:15px 0;"><div style="color:#6b7280;font-size:12px;text-transform:uppercase;margin-bottom:5px;">Action Tentee</div><div style="color:#111827;font-size:16px;font-weight:500;"><code style="background:#e5e7eb;padding:2px 6px;border-radius:4px;">' + (incident.level_1_action || 'N/A') + '</code></div></div><div style="background:#fef2f2;border-left:4px solid #ef4444;padding:15px;margin:15px 0;"><div style="color:#6b7280;font-size:12px;text-transform:uppercase;margin-bottom:5px;">Resultat</div><div style="color:#dc2626;font-size:14px;">' + (incident.execution_result?.stderr || incident.execution_result?.http_code || 'Service non restaure') + '</div></div></div><div style="background:#f9fafb;padding:20px;text-align:center;color:#6b7280;font-size:12px;">Auto-Repare - Escalade N2 automatique en cours</div></div></body></html>';
return [{ json: { subject: '⚠️ [Auto-Repare] Echec N1 - ' + (incident.service_name || 'Service') + ' - Escalade en cours', html: html, incident: incident } }];'''
    },
    "id": "gen-failure-email",
    "name": "Generer Email Echec",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [672, 0]
}

# Add failure email sender
send_failure_email = {
    "parameters": {
        "fromEmail": "auto-repare@aurastackai.com",
        "toEmail": "={{ $env.ALERT_EMAIL_TO || 'admin@aurastackai.com' }}",
        "subject": "={{ $json.subject }}",
        "html": "={{ $json.html }}",
        "options": {}
    },
    "id": "send-failure-email",
    "name": "Envoyer Email Echec",
    "type": "n8n-nodes-base.emailSend",
    "typeVersion": 2.1,
    "position": [896, 0],
    "credentials": {"smtp": {"id": "mIhtA6Kr4nLZtFxw", "name": "SMTP account"}}
}

# Check if nodes exist
existing_names = [n['name'] for n in w['nodes']]
if 'Type Failure?' not in existing_names:
    w['nodes'].append(check_failure)
    print("[OK] Added Type Failure? node")
if 'Generer Email Echec' not in existing_names:
    w['nodes'].append(gen_failure_email)
    print("[OK] Added Generer Email Echec node")
if 'Envoyer Email Echec' not in existing_names:
    w['nodes'].append(send_failure_email)
    print("[OK] Added Envoyer Email Echec node")

# Update connections
# Current: Type de Notification -> [success] Generer Email Succes, [else] Generer Email Escalade
# New: Type de Notification -> [success] Generer Email Succes, [else] Type Failure?
#      Type Failure? -> [true] Generer Email Echec -> Envoyer, [else] Generer Email Escalade

# Update Type de Notification else branch
for node in w['nodes']:
    if node['name'] == 'Type de Notification':
        node['position'] = [224, 0]

# Move success nodes
for node in w['nodes']:
    if node['name'] == 'Generer Email Succes':
        node['position'] = [448, -150]
    if node['name'] == 'Envoyer Email Succes':
        node['position'] = [672, -150]
    if node['name'] == 'Generer Email Escalade':
        node['position'] = [672, 150]
    if node['name'] == 'Envoyer Email Escalade':
        node['position'] = [896, 150]

# Update connections
w['connections']['Type de Notification'] = {
    "main": [
        [{"node": "Generer Email Succes", "type": "main", "index": 0}],  # success
        [{"node": "Type Failure?", "type": "main", "index": 0}]  # else -> check failure
    ]
}
w['connections']['Type Failure?'] = {
    "main": [
        [{"node": "Generer Email Echec", "type": "main", "index": 0}],  # failure
        [{"node": "Generer Email Escalade", "type": "main", "index": 0}]  # else (escalation)
    ]
}
w['connections']['Generer Email Echec'] = {"main": [[{"node": "Envoyer Email Echec", "type": "main", "index": 0}]]}

print("[OK] Updated connections")

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
    print("[OK] Notification Manager updated")
else:
    print(f"[ERROR] {response.status_code}: {response.text}")
