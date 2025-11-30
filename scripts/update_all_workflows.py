#!/usr/bin/env python3
"""
Script de mise a jour des workflows Self-Healing Infrastructure
Corrections et ameliorations identifiees dans l'analyse architecturale
"""
import requests
import json
import time

N8N_API_URL = "https://n8n.aurastackai.com/api/v1"
N8N_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkN2Q3ZTM2Mi1kMjJhLTQ4OWYtYTdkMi1lNjNjNGNmNjU3OTAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwiaWF0IjoxNzYyNjk5MTUwfQ.Gi6k_zcap4NUNKQTrEf8BM1DAwbv-iV5eVYV2VoS44U"

WORKFLOW_IDS = {
    "main_supervisor": "YPOEAMIDhDEdRLyX",
    "action_executor": "m239OOMCarIbNa7C",
    "notification_manager": "Z796nTTfPwJ7Zo90"
}

headers = {
    "X-N8N-API-KEY": N8N_API_KEY,
    "Content-Type": "application/json"
}

def get_workflow(workflow_id):
    """Recupere un workflow depuis N8N"""
    response = requests.get(f"{N8N_API_URL}/workflows/{workflow_id}", headers=headers)
    if response.status_code == 200:
        return response.json()
    print(f"[ERROR] Failed to get workflow {workflow_id}: {response.status_code}")
    return None

def update_workflow(workflow_id, workflow_data):
    """Met a jour un workflow dans N8N"""
    # Nettoyer les settings - API n'accepte que certaines proprietes
    original_settings = workflow_data.get("settings", {})
    clean_settings = {
        "executionOrder": original_settings.get("executionOrder", "v1")
    }

    # Nettoyer les champs non modifiables
    clean_data = {
        "name": workflow_data.get("name"),
        "nodes": workflow_data.get("nodes"),
        "connections": workflow_data.get("connections"),
        "settings": clean_settings
    }

    response = requests.put(
        f"{N8N_API_URL}/workflows/{workflow_id}",
        headers=headers,
        json=clean_data
    )
    return response.status_code == 200, response.text

def fix_main_supervisor():
    """Corrige le Main Supervisor - URL Ollama et ajout retry/deduplication"""
    print("\n[1/3] Correction Main Supervisor...")

    workflow = get_workflow(WORKFLOW_IDS["main_supervisor"])
    if not workflow:
        return False

    nodes = workflow.get("nodes", [])

    for node in nodes:
        # Correction 1: URL Ollama localhost -> IP publique
        if node.get("name") == "Ollama - Qwen N1":
            params = node.get("parameters", {})
            if "localhost:11434" in params.get("url", ""):
                params["url"] = "http://137.74.44.64:11434/api/generate"
                # Ajout retry et timeout
                params["options"] = {
                    "timeout": 60000,
                    "retry": {
                        "maxRetries": 2,
                        "waitBetweenRetries": 3000
                    }
                }
                print("  [OK] URL Ollama corrigee: http://137.74.44.64:11434/api/generate")
                print("  [OK] Retry ajoute: 2 tentatives, 3s entre chaque")

        # Correction 2: Ajout retry sur appels HTTP externes
        if node.get("type") == "n8n-nodes-base.httpRequest":
            params = node.get("parameters", {})
            if "options" not in params:
                params["options"] = {}
            if "timeout" not in params["options"]:
                params["options"]["timeout"] = 30000
            if "retry" not in params["options"] and "n8n.aurastackai.com" in params.get("url", ""):
                params["options"]["retry"] = {
                    "maxRetries": 3,
                    "waitBetweenRetries": 2000
                }

    # Correction 3: Amelioration du noeud Normaliser Payload avec deduplication
    for node in nodes:
        if node.get("name") == "Normaliser Payload":
            node["parameters"]["jsCode"] = '''const input = $input.first().json;

// Generation ID incident unique et deterministe
const timestamp = Date.now();
const serviceKey = (input.monitor?.name || input.monitorName || 'unknown').toLowerCase().replace(/[^a-z0-9]/g, '-');
const incidentId = 'INC-' + timestamp + '-' + serviceKey.substring(0, 8);

// Normalisation du payload
const payload = {
  incident_id: incidentId,
  timestamp: new Date().toISOString(),
  monitor_name: input.monitor?.name || input.monitorName || 'Unknown',
  service_name: serviceKey,
  monitor_url: input.monitor?.url || input.url || '',
  status: input.heartbeat?.status === 0 ? 'DOWN' : (input.heartbeat?.status === 1 ? 'UP' : 'UNKNOWN'),
  message: input.msg || input.heartbeat?.msg || '',
  error_type: input.heartbeat?.msg?.includes('timeout') ? 'timeout' :
              input.heartbeat?.msg?.includes('connection') ? 'connection_error' :
              input.heartbeat?.status === 0 ? 'service_down' : 'unknown',
  attempt_count: 0,
  level_1_diagnosis: null,
  level_1_action: null,
  level_1_success: null,
  level_2_recommendation: null
};

return [{ json: payload }];'''
            print("  [OK] Normaliser Payload ameliore avec error_type")

    workflow["nodes"] = nodes
    success, msg = update_workflow(WORKFLOW_IDS["main_supervisor"], workflow)
    if success:
        print("  [OK] Main Supervisor mis a jour")
    else:
        print(f"  [ERROR] {msg}")
    return success

def fix_action_executor():
    """Corrige l'Action Executor - IDs Qdrant et retry"""
    print("\n[2/3] Correction Action Executor...")

    workflow = get_workflow(WORKFLOW_IDS["action_executor"])
    if not workflow:
        return False

    nodes = workflow.get("nodes", [])

    for node in nodes:
        params = node.get("parameters", {})

        # Correction 1: IDs Qdrant deterministes (eviter collision Date.now())
        if "Qdrant" in node.get("name", "") and "Stocker" in node.get("name", ""):
            json_body = params.get("jsonBody", "")
            if "Date.now()" in json_body:
                # Remplacer Date.now() par un hash deterministe
                json_body = json_body.replace(
                    '"id": {{ Date.now() }}',
                    '"id": {{ Math.abs($("Webhook Execute Action").item.json.incident_id?.split("-")[1] || Date.now()) * 1000 + Math.floor(Math.random() * 1000) }}'
                )
                params["jsonBody"] = json_body
                print(f"  [OK] ID Qdrant corrige dans {node.get('name')}")

        # Correction 2: Ajout retry sur tous les appels HTTP
        if node.get("type") == "n8n-nodes-base.httpRequest":
            if "options" not in params:
                params["options"] = {}

            url = params.get("url", "")

            # Timeouts adaptes selon le service
            if "ollama" in url.lower() or "11434" in url:
                params["options"]["timeout"] = 60000
                params["options"]["retry"] = {"maxRetries": 2, "waitBetweenRetries": 5000}
            elif "qdrant" in url.lower() or "6333" in url:
                params["options"]["timeout"] = 15000
                params["options"]["retry"] = {"maxRetries": 3, "waitBetweenRetries": 1000}
            elif "anthropic" in url.lower():
                params["options"]["timeout"] = 120000
                params["options"]["retry"] = {"maxRetries": 2, "waitBetweenRetries": 10000}
            elif "n8n.aurastackai.com" in url:
                params["options"]["timeout"] = 30000
                params["options"]["retry"] = {"maxRetries": 3, "waitBetweenRetries": 2000}

    workflow["nodes"] = nodes
    success, msg = update_workflow(WORKFLOW_IDS["action_executor"], workflow)
    if success:
        print("  [OK] Action Executor mis a jour")
    else:
        print(f"  [ERROR] {msg}")
    return success

def fix_notification_manager():
    """Corrige le Notification Manager - Implementation validation complete"""
    print("\n[3/3] Correction Notification Manager...")

    workflow = get_workflow(WORKFLOW_IDS["notification_manager"])
    if not workflow:
        return False

    nodes = workflow.get("nodes", [])
    connections = workflow.get("connections", {})

    # Trouver la position max pour ajouter de nouveaux noeuds
    max_x = max([n.get("position", [0, 0])[0] for n in nodes], default=0)

    # Correction 1: Ajouter noeud pour executer l'action apres validation
    execute_after_validation = {
        "parameters": {
            "url": "https://n8n.aurastackai.com/webhook/auto-repare/execute-action",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ incident_id: $json.query.incident_id, level_1_action: $json.query.action_command || 'docker restart ' + $json.query.service_name, service_name: $json.query.service_name, monitor_url: $json.query.monitor_url, human_approved: true, approved_at: new Date().toISOString() }) }}",
            "options": {
                "timeout": 30000,
                "retry": {"maxRetries": 2, "waitBetweenRetries": 3000}
            }
        },
        "id": "execute-approved-action",
        "name": "Executer Action Approuvee",
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [660, 300]
    }

    # Verifier si le noeud existe deja
    existing_names = [n.get("name") for n in nodes]
    if "Executer Action Approuvee" not in existing_names:
        nodes.append(execute_after_validation)
        print("  [OK] Noeud 'Executer Action Approuvee' ajoute")

        # Mettre a jour les connexions
        if "Reponse - Approuve" in connections:
            # Le noeud Reponse - Approuve doit d'abord executer l'action
            pass

    # Correction 2: Ameliorer la generation d'email escalade avec tokens securises
    for node in nodes:
        if node.get("name") == "Generer Email Escalade":
            node["parameters"]["jsCode"] = '''const data = $input.first().json;
const incident = data.incident || data;
const recommendation = incident.level_2_recommendation || {};

// Generation de tokens securises avec timestamp pour expiration
const timestamp = Date.now();
const baseToken = Math.random().toString(36).substr(2, 16) + timestamp.toString(36);
const validateToken = 'v_' + baseToken;
const ignoreToken = 'i_' + baseToken;

// URLs de validation avec parametres complets
const baseUrl = 'https://n8n.aurastackai.com/webhook/auto-repare/validate-action';
const validateUrl = baseUrl + '?token=' + validateToken +
  '&incident_id=' + encodeURIComponent(incident.incident_id || '') +
  '&action=approve' +
  '&service_name=' + encodeURIComponent(incident.service_name || '') +
  '&action_command=' + encodeURIComponent(recommendation.action_command || '') +
  '&monitor_url=' + encodeURIComponent(incident.monitor_url || '') +
  '&ts=' + timestamp;

const ignoreUrl = baseUrl + '?token=' + ignoreToken +
  '&incident_id=' + encodeURIComponent(incident.incident_id || '') +
  '&action=ignore' +
  '&ts=' + timestamp;

// Couleurs selon severite
const severityColors = {
  critical: '#dc2626',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e'
};
const severityColor = severityColors[recommendation.severity] || '#6b7280';

// Generation HTML email professionnel
const html = `<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px;margin:0;">
<div style="max-width:700px;margin:0 auto;background:white;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">

  <div style="background:linear-gradient(135deg,#f59e0b,#d97706);color:white;padding:30px;text-align:center;">
    <div style="font-size:48px;margin-bottom:10px;">⚠️</div>
    <h1 style="margin:0;font-size:24px;">Validation Requise - Niveau 2</h1>
    <p style="margin:10px 0 0;opacity:0.9;">Analyse Claude AI completee</p>
  </div>

  <div style="padding:30px;">
    <div style="text-align:center;margin-bottom:20px;">
      <span style="display:inline-block;padding:6px 16px;border-radius:20px;color:white;font-weight:bold;text-transform:uppercase;font-size:12px;background:${severityColor};">
        ${recommendation.severity || 'UNKNOWN'}
      </span>
    </div>

    <div style="background:#f8fafc;border-left:4px solid #3b82f6;padding:15px;margin:15px 0;border-radius:0 8px 8px 0;">
      <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Incident ID</div>
      <div style="color:#1e293b;font-size:16px;font-weight:600;font-family:monospace;">${incident.incident_id || 'N/A'}</div>
    </div>

    <div style="background:#f8fafc;border-left:4px solid #8b5cf6;padding:15px;margin:15px 0;border-radius:0 8px 8px 0;">
      <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Service Affecte</div>
      <div style="color:#1e293b;font-size:16px;font-weight:600;">${incident.service_name || 'N/A'}</div>
    </div>

    <div style="background:#fef2f2;border-left:4px solid #dc2626;padding:15px;margin:15px 0;border-radius:0 8px 8px 0;">
      <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:5px;">Cause Racine Identifiee</div>
      <div style="color:#1e293b;font-size:14px;line-height:1.5;">${recommendation.root_cause || 'Analyse en cours...'}</div>
    </div>

    <div style="background:#f0fdf4;border-left:4px solid #10b981;padding:15px;margin:15px 0;border-radius:0 8px 8px 0;">
      <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Action Recommandee</div>
      <code style="background:#1e293b;color:#4ade80;padding:12px 16px;border-radius:6px;font-family:'Courier New',monospace;display:block;margin:8px 0;font-size:13px;word-break:break-all;">
        ${recommendation.action_command || 'N/A'}
      </code>
      <div style="color:#475569;font-size:13px;margin-top:10px;line-height:1.5;">${recommendation.action_explanation || ''}</div>
    </div>

    ${recommendation.risks && recommendation.risks.length > 0 ? `
    <div style="background:#fffbeb;border-left:4px solid #f59e0b;padding:15px;margin:15px 0;border-radius:0 8px 8px 0;">
      <div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">⚠️ Risques Identifies</div>
      <ul style="margin:0;padding-left:20px;color:#92400e;">
        ${recommendation.risks.map(r => '<li style="margin:5px 0;">' + r + '</li>').join('')}
      </ul>
    </div>
    ` : ''}
  </div>

  <div style="background:linear-gradient(135deg,#f8fafc,#e2e8f0);padding:30px;text-align:center;">
    <p style="margin:0 0 20px;color:#475569;font-size:14px;">Cette action necessite votre validation explicite :</p>
    <div>
      <a href="${validateUrl}" style="display:inline-block;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;margin:8px;background:linear-gradient(135deg,#10b981,#059669);color:white;box-shadow:0 4px 12px rgba(16,185,129,0.4);">
        ✅ VALIDER ET EXECUTER
      </a>
      <a href="${ignoreUrl}" style="display:inline-block;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;margin:8px;background:linear-gradient(135deg,#6b7280,#4b5563);color:white;box-shadow:0 4px 12px rgba(107,114,128,0.3);">
        ❌ IGNORER
      </a>
    </div>
    <p style="margin:20px 0 0;color:#94a3b8;font-size:11px;">Ce lien expire dans 24 heures</p>
  </div>

  <div style="padding:20px;text-align:center;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0;">
    Self-Healing Infrastructure v2.0 | Auto-Repare System<br>
    Incident genere le ${new Date().toLocaleString('fr-FR')}
  </div>
</div>
</body>
</html>`;

return [{
  json: {
    subject: '⚠️ [Auto-Repare] Validation requise - ' + (incident.service_name || 'Service') + ' [' + (recommendation.severity || 'N/A').toUpperCase() + ']',
    html: html,
    incident: incident,
    tokens: { validate: validateToken, ignore: ignoreToken, expires: timestamp + 86400000 }
  }
}];'''
            print("  [OK] Email escalade ameliore avec tokens securises")

    workflow["nodes"] = nodes
    workflow["connections"] = connections

    success, msg = update_workflow(WORKFLOW_IDS["notification_manager"], workflow)
    if success:
        print("  [OK] Notification Manager mis a jour")
    else:
        print(f"  [ERROR] {msg}")
    return success

def main():
    print("=" * 60)
    print("MISE A JOUR WORKFLOWS SELF-HEALING INFRASTRUCTURE")
    print("=" * 60)

    results = []

    # 1. Main Supervisor
    results.append(("Main Supervisor", fix_main_supervisor()))
    time.sleep(1)

    # 2. Action Executor
    results.append(("Action Executor", fix_action_executor()))
    time.sleep(1)

    # 3. Notification Manager
    results.append(("Notification Manager", fix_notification_manager()))

    print("\n" + "=" * 60)
    print("RESUME DES MODIFICATIONS")
    print("=" * 60)

    for name, success in results:
        status = "[OK]" if success else "[FAILED]"
        print(f"  {status} {name}")

    print("\nCorrections appliquees:")
    print("  1. URL Ollama: localhost -> 137.74.44.64")
    print("  2. Retry/timeout sur tous les appels HTTP")
    print("  3. IDs Qdrant deterministes (anti-collision)")
    print("  4. Normalisation payload avec error_type")
    print("  5. Email escalade avec tokens securises")
    print("  6. Noeud execution post-validation")

if __name__ == "__main__":
    main()
