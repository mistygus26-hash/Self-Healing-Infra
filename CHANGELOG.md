# Changelog

All notable changes to this project will be documented in this file.

## [2.1.0] - 2025-11-30

### Production Hardening Release

This release addresses architectural improvements identified during production readiness review.

### Fixed

- **Ollama URL**: Changed from `localhost:11434` to `137.74.44.64:11434` in Main Supervisor workflow to ensure proper network routing within Docker environment
- **Qdrant ID collision**: Replaced `Date.now()` with deterministic ID generation using incident timestamp + random suffix to prevent vector storage conflicts

### Added

- **Retry/Timeout on HTTP calls**: All external HTTP requests now include proper timeout and retry configuration:
  - Ollama API: 60s timeout, 2 retries, 5s between attempts
  - Qdrant API: 15s timeout, 3 retries, 1s between attempts
  - Claude API: 120s timeout, 2 retries, 10s between attempts
  - Internal webhooks: 30s timeout, 3 retries, 2s between attempts

- **Human validation execution**: Added "Executer Action Approuvee" node in Notification Manager to actually execute actions after human approval via email link

- **Enhanced incident payload**: Added `error_type` field to normalized payload for better incident categorization:
  - `timeout`: Connection timeout errors
  - `connection_error`: Network/connection issues
  - `service_down`: Service unavailable
  - `unknown`: Other errors

- **Secure validation tokens**: Email escalation links now include:
  - Timestamped tokens for expiration tracking (24h validity)
  - Complete action context (incident_id, service_name, action_command, monitor_url)
  - Separate approve/ignore tokens for security

- **Automated update script**: `scripts/update_all_workflows.py` for batch workflow updates via N8N API

### Changed

- **Email template**: Improved escalation email with:
  - Modern gradient design
  - Severity badge with color coding
  - Complete incident context display
  - Risk display section
  - Professional styling

### Security

- All validation URLs now include expiration timestamps
- Tokens are unique per incident and action type
- Complete audit trail in webhook parameters

## [2.0.0] - 2025-11-27

### Initial Release

- Main Supervisor workflow with Uptime Kuma webhook integration
- Action Executor with Qwen N1 analysis and safe command execution
- Notification Manager with email alerts and human validation
- RAG integration with Qdrant for incident learning
- Two-tier AI analysis (Qwen local + Claude cloud)
