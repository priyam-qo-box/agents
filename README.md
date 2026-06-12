# Sunny — Multi-Agent Backend Engineering System

A collection of **Cursor AI agents** that turn a frontend application into a complete, enterprise-grade **JHipster microservices** backend — fully generated, verified, tested to 95%+ coverage, and audited for production readiness.

At the center is **Sunny**, an orchestrator that coordinates specialized agents through continuous verify → fix and test → verify loops until every quality gate passes. A standalone **documentation** agent (Swagger + Postman + Javadoc) is also included.

---

## What this repo is

This repository contains **agent definitions and orchestration rules** for Cursor — not application code. Point the agents at a frontend project and they produce and validate the backend.

```
.cursor/
├── rules/
│   └── sunny-orchestrator.mdc      # Executable playbook the orchestrator follows
└── agents/
    ├── README.md                          # Deep dive on how the Sunny system works
    ├── ARCHITECTURE.md                    # All architecture + workflow diagrams
    ├── sunny.md                           # Orchestrator persona
    ├── context-agent.md                   # Shared memory (.sunny/context/ store)
    ├── jhipster-backend-agent.md          # Generates the microservices backend
    ├── jhipster-verify-agent.md           # Audits the backend (readonly)
    ├── issue-resolution-agent.md          # Fixes issues found by the verifier
    ├── backend-unit-test-agent.md                  # Backend unit tests
    ├── backend-unit-test-verify-agent.md           # Verifies backend unit tests (readonly)
    ├── backend-unit-test-fix-agent.md              # Closes backend unit-layer gaps
    ├── backend-integration-test-agent.md           # Backend integration tests (Testcontainers)
    ├── backend-integration-test-verify-agent.md    # Verifies backend integration tests (readonly)
    ├── backend-integration-test-fix-agent.md       # Closes backend integration-layer gaps
    ├── backend-functional-test-agent.md            # Backend functional/API tests
    ├── backend-functional-test-verify-agent.md     # Verifies backend functional tests (readonly)
    ├── backend-functional-test-fix-agent.md        # Closes backend functional-layer gaps
    ├── frontend-unit-test-agent.md                 # Frontend unit tests
    ├── frontend-unit-test-verify-agent.md          # Verifies frontend unit tests (readonly)
    ├── frontend-unit-test-fix-agent.md             # Closes frontend unit-layer gaps
    ├── frontend-integration-test-agent.md          # Frontend component tests (MSW)
    ├── frontend-integration-test-verify-agent.md   # Verifies frontend component tests (readonly)
    ├── frontend-integration-test-fix-agent.md      # Closes frontend component-layer gaps
    ├── frontend-functional-test-agent.md           # Frontend E2E tests (Playwright)
    ├── frontend-functional-test-verify-agent.md    # Verifies frontend E2E tests (readonly)
    ├── frontend-functional-test-fix-agent.md       # Closes frontend E2E-layer gaps
    ├── production-standards-agent.md      # Final production audit (readonly)
    ├── production-fix-agent.md            # Remediates production audit findings
    └── documentation.md                   # Standalone: Swagger + Postman + Javadoc
```

At runtime, the Context Agent creates a `.sunny/context/` store that acts as shared memory across agent runs.

---

## The agents

### Sunny orchestration system

| Agent | Role | Readonly |
|-------|------|----------|
| **Sunny** | Orchestrates all agents, runs loops, enforces quality gates | No |
| **Context Agent** | Shared memory; persists structured summaries between runs | No |
| **JHipster Backend Agent** | Generates JHipster microservices (gateway + services + registry) | No |
| **JHipster Verify Agent** | Audits API, security, architecture, database | Yes |
| **Issue Resolution Agent** | Fixes every issue the verifier reports | No |
| **Backend Unit Test Agent** | Isolated unit tests (services, mappers, validators) | No |
| **Backend Unit Test Verify Agent** | Verifies backend unit-layer coverage/quality | Yes |
| **Backend Unit Test Fix Agent** | Closes backend unit-layer gaps | No |
| **Backend Integration Test Agent** | Repository/DB tests on Testcontainers PostgreSQL | No |
| **Backend Integration Test Verify Agent** | Verifies backend integration-layer coverage/quality | Yes |
| **Backend Integration Test Fix Agent** | Closes backend integration-layer gaps | No |
| **Backend Functional Test Agent** | REST/API + gateway HTTP contract tests | No |
| **Backend Functional Test Verify Agent** | Verifies backend functional-layer coverage/quality | Yes |
| **Backend Functional Test Fix Agent** | Closes backend functional-layer gaps | No |
| **Frontend Unit Test Agent** | Isolated unit tests (utils, hooks, stores) | No |
| **Frontend Unit Test Verify Agent** | Verifies frontend unit-layer coverage/quality | Yes |
| **Frontend Unit Test Fix Agent** | Closes frontend unit-layer gaps | No |
| **Frontend Integration Test Agent** | Component/page tests with MSW, routing, state | No |
| **Frontend Integration Test Verify Agent** | Verifies frontend component-layer coverage/quality | Yes |
| **Frontend Integration Test Fix Agent** | Closes frontend component-layer gaps | No |
| **Frontend Functional Test Agent** | E2E user journeys (Playwright) | No |
| **Frontend Functional Test Verify Agent** | Verifies frontend E2E journey coverage | Yes |
| **Frontend Functional Test Fix Agent** | Closes frontend E2E gaps | No |
| **Production Standards Agent** | Final security / readiness / performance audit | Yes |
| **Production Fix Agent** | Remediates production audit findings | No |

### Standalone (not orchestrated by Sunny)

| Agent | Role |
|-------|------|
| **Documentation Agent** | Complete Swagger/OpenAPI docs, Postman collections + Newman CI, and Javadoc — leaving nothing undocumented |

---

## Workflow at a glance

```mermaid
flowchart LR
    FE([Frontend]) --> S[Sunny]
    S --> GEN[Generate backend]
    GEN --> VL{Verify loop}
    VL -->|issues| FIX[Fix] --> VL
    VL -->|"Backend approved"| BTL{"Backend test loops<br/>unit -> integration -> functional"}
    BTL -->|"layer not satisfied"| BFIX[Fix that layer] --> BTL
    BTL -->|"all 3 backend layers satisfied"| FTL{"Frontend test loops<br/>unit -> integration -> functional"}
    FTL -->|"layer not satisfied"| FFIX[Fix that layer] --> FTL
    FTL -->|"all 3 frontend layers satisfied"| PL{Production loop}
    PL -->|"blocked"| PFIX[Fix production] --> PL
    PL -->|"Final approval granted"| DONE([Production-ready])
```

Backend and frontend tests each split into **three layers — unit, integration, functional — and each layer has its own generation, verify, and fix agent**. Every phase — including production — runs a verify -> fix -> re-verify loop that breaks only on an **exact verdict phrase**, and caps at **5 iterations** per loop before escalating to the user:

| Loop | Exit phrase |
|------|-------------|
| Backend verification | `No issues found. Backend approved.` |
| Backend unit testing | `Backend unit testing requirements satisfied.` |
| Backend integration testing | `Backend integration testing requirements satisfied.` |
| Backend functional testing | `Backend functional testing requirements satisfied.` |
| Frontend unit testing | `Frontend unit testing requirements satisfied.` |
| Frontend integration testing | `Frontend integration testing requirements satisfied.` |
| Frontend functional testing | `Frontend functional testing requirements satisfied.` |
| Production | `Final approval granted. System is production-ready.` |

> Full diagrams (component architecture, sequence, loops, data flow, state machine) are in [`.cursor/agents/ARCHITECTURE.md`](.cursor/agents/ARCHITECTURE.md).

---

## Non-negotiable standards

Enforced by every relevant agent:

- **JHipster microservices** architecture — never monolithic.
- **PostgreSQL** for all persistent data.
- **No mock data**, no fake CSV files, no dummy records — real persistence only.
- **>= 95%** line and branch coverage (backend and frontend), with build-failing gates.
- Enterprise APIs: REST, versioning, OpenAPI, RFC 7807 errors, JWT/OAuth2, RBAC.
- Production readiness: Docker, logging, monitoring, externalized config.

---

## How to use

These agents run inside **Cursor**. The `.cursor/agents/*.md` files are picked up automatically as custom agents, and `.cursor/rules/sunny-orchestrator.mdc` provides the orchestration playbook.

### Run the full pipeline

In a Cursor chat, invoke Sunny and point it at your frontend:

> Sunny, build the JHipster microservices backend for the frontend in `./frontend`.

Sunny will analyze the frontend, generate the backend, run the verification and testing loops, and finish with a production audit — announcing each phase and iteration as it goes. Progress and intermediate summaries are written to `.sunny/context/`.

### Run the documentation agent (standalone)

> Use the documentation agent to fully document this backend — Swagger, Postman, and Javadoc.

---

## Learn more

- [`.cursor/agents/README.md`](.cursor/agents/README.md) — how the Sunny system works, phase by phase.
- [`.cursor/agents/ARCHITECTURE.md`](.cursor/agents/ARCHITECTURE.md) — architecture and workflow diagrams.
- [`.cursor/rules/sunny-orchestrator.mdc`](.cursor/rules/sunny-orchestrator.mdc) — the orchestration playbook.
- Individual agent definitions under [`.cursor/agents/`](.cursor/agents/).
