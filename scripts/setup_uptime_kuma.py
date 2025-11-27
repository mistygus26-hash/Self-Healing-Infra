#!/usr/bin/env python3
"""
Script de configuration automatique d'Uptime Kuma
Crée les monitors et le webhook pour le système auto-repare
"""

import sys
try:
    from uptime_kuma_api import UptimeKumaApi, MonitorType, NotificationType
except ImportError:
    print("Installation de uptime-kuma-api...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "uptime-kuma-api"])
    from uptime_kuma_api import UptimeKumaApi, MonitorType, NotificationType

# Configuration
UPTIME_KUMA_URL = "http://137.74.44.64:3001"
# À définir lors de la première utilisation
USERNAME = "admin"  # Changer selon votre config
PASSWORD = "CHANGE_ME"  # Changer selon votre config

# URL du webhook N8N (Main Supervisor)
N8N_WEBHOOK_URL = "https://n8n.aurastackai.com/webhook/auto-repare/alert"

# Monitors à créer
MONITORS_CONFIG = [
    {
        "name": "N8N Main",
        "type": MonitorType.HTTP,
        "url": "https://n8n.aurastackai.com",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 3,
        "description": "Interface principale N8N"
    },
    {
        "name": "N8N Webhook Health",
        "type": MonitorType.HTTP,
        "url": "https://n8n.aurastackai.com/webhook-test",
        "interval": 120,
        "retryInterval": 60,
        "maxretries": 2,
        "description": "Vérification webhooks N8N"
    },
    {
        "name": "VPS SSH",
        "type": MonitorType.PORT,
        "hostname": "137.74.44.64",
        "port": 22,
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 3,
        "description": "Port SSH du VPS"
    },
    {
        "name": "VPS HTTP (Uptime Kuma)",
        "type": MonitorType.HTTP,
        "url": "http://137.74.44.64:3001",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 3,
        "description": "Uptime Kuma lui-même"
    },
    {
        "name": "Docker N8N Main",
        "type": MonitorType.DOCKER,
        "docker_container": "n8n-main-prod",
        "docker_host": None,  # Socket local
        "interval": 30,
        "description": "Container N8N principal"
    },
    {
        "name": "Docker N8N Worker 1",
        "type": MonitorType.DOCKER,
        "docker_container": "n8n-worker-prod-1",
        "docker_host": None,
        "interval": 30,
        "description": "Worker N8N 1"
    },
    {
        "name": "Docker N8N Worker 2",
        "type": MonitorType.DOCKER,
        "docker_container": "n8n-worker-prod-2",
        "docker_host": None,
        "interval": 30,
        "description": "Worker N8N 2"
    },
    {
        "name": "Docker Redis",
        "type": MonitorType.DOCKER,
        "docker_container": "n8n-redis-prod",
        "docker_host": None,
        "interval": 30,
        "description": "Redis pour N8N"
    },
    {
        "name": "Docker PostgreSQL",
        "type": MonitorType.DOCKER,
        "docker_container": "n8n-postgres-prod",
        "docker_host": None,
        "interval": 30,
        "description": "Base de données N8N"
    },
    {
        "name": "Ollama API",
        "type": MonitorType.HTTP,
        "url": "http://localhost:11434/api/tags",
        "interval": 60,
        "retryInterval": 30,
        "maxretries": 2,
        "description": "API Ollama pour Qwen"
    }
]


def setup_uptime_kuma():
    """Configure Uptime Kuma avec les monitors et le webhook"""

    print(f"Connexion à Uptime Kuma: {UPTIME_KUMA_URL}")
    api = UptimeKumaApi(UPTIME_KUMA_URL)

    try:
        # Login
        api.login(USERNAME, PASSWORD)
        print("✅ Connecté à Uptime Kuma")

        # Créer la notification webhook
        print("\n📡 Création du webhook de notification...")
        notification_id = create_webhook_notification(api)

        # Créer les monitors
        print("\n📊 Création des monitors...")
        created_monitors = []

        for monitor_config in MONITORS_CONFIG:
            try:
                monitor = create_monitor(api, monitor_config, notification_id)
                if monitor:
                    created_monitors.append(monitor)
                    print(f"  ✅ {monitor_config['name']}")
            except Exception as e:
                print(f"  ❌ {monitor_config['name']}: {e}")

        print(f"\n✅ Configuration terminée!")
        print(f"   - {len(created_monitors)} monitors créés")
        print(f"   - Webhook configuré vers: {N8N_WEBHOOK_URL}")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        raise
    finally:
        api.disconnect()


def create_webhook_notification(api):
    """Crée la notification webhook vers N8N"""

    # Vérifier si elle existe déjà
    notifications = api.get_notifications()
    for notif in notifications:
        if "auto-repare" in notif.get("name", "").lower():
            print(f"  ℹ️  Notification existante trouvée: {notif['name']}")
            return notif["id"]

    # Créer la notification
    result = api.add_notification(
        name="Auto-Repare Webhook",
        type=NotificationType.WEBHOOK,
        webhookURL=N8N_WEBHOOK_URL,
        webhookContentType="application/json",
        isDefault=True,
        applyExisting=True
    )

    print(f"  ✅ Notification webhook créée (ID: {result['id']})")
    return result["id"]


def create_monitor(api, config, notification_id):
    """Crée un monitor avec la config donnée"""

    # Vérifier si le monitor existe déjà
    monitors = api.get_monitors()
    for m in monitors:
        if m.get("name") == config["name"]:
            print(f"  ℹ️  Monitor existant: {config['name']}")
            return m

    # Paramètres de base
    params = {
        "name": config["name"],
        "type": config["type"],
        "interval": config.get("interval", 60),
        "retryInterval": config.get("retryInterval", 30),
        "maxretries": config.get("maxretries", 3),
        "notificationIDList": [notification_id],
        "description": config.get("description", "")
    }

    # Paramètres spécifiques selon le type
    if config["type"] == MonitorType.HTTP:
        params["url"] = config["url"]
    elif config["type"] == MonitorType.PORT:
        params["hostname"] = config["hostname"]
        params["port"] = config["port"]
    elif config["type"] == MonitorType.DOCKER:
        params["docker_container"] = config["docker_container"]
        if config.get("docker_host"):
            params["docker_host"] = config["docker_host"]

    result = api.add_monitor(**params)
    return result


def print_usage():
    """Affiche les instructions d'utilisation"""
    print("""
╔══════════════════════════════════════════════════════════════════╗
║           CONFIGURATION UPTIME KUMA - AUTO-REPARE                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Ce script configure automatiquement Uptime Kuma avec:           ║
║  - 10 monitors (HTTP, Port, Docker)                              ║
║  - 1 webhook vers N8N pour les alertes                           ║
║                                                                  ║
║  PRÉREQUIS:                                                      ║
║  1. Uptime Kuma doit être démarré et accessible                  ║
║  2. Vous devez avoir créé un compte admin dans Uptime Kuma       ║
║  3. Modifiez USERNAME et PASSWORD dans ce script                 ║
║                                                                  ║
║  UTILISATION:                                                    ║
║  1. Éditez ce fichier et changez USERNAME/PASSWORD               ║
║  2. Exécutez: python3 setup_uptime_kuma.py                       ║
║                                                                  ║
║  NOTE: Pour les monitors Docker, ce script doit être exécuté     ║
║  sur le VPS lui-même (pas depuis Windows)                        ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print_usage()
    else:
        print_usage()
        print("\nDémarrage de la configuration...\n")
        setup_uptime_kuma()
