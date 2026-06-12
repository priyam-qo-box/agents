# Sunny Multi-Agent Orchestration System

Sunny is a central **Orchestrator Agent** that coordinates specialized sub-agents to turn a frontend application into a complete, enterprise-grade **JHipster microservices** backend — with verification, testing, and production-readiness loops that run until every quality gate passes.

This document explains how the agents work together, what each one does, and how to run the system.

---

## Non-negotiables

These constraints are enforced by every relevant agent:

- **JHipster microservices** architecture (gateway + services + registry) — never monolithic.
- **PostgreSQL** for all persistent data.
- **No mock data**, no fake CSV files, no dummy records — real database persistence only.
- **>= 95%** line and branch coverage for backend and frontend.
- Enterprise API standards: REST, versioning, OpenAPI, RFC 7807 errors, JWT/OAuth2, RBAC.
- Production readiness: Docker, logging, monitoring, externalized config.

---

## The agents

| # | Agent | File | Role | Readonly |
|---|-------|------|------|----------|
| 1 | **Sunny** (Orchestrator) | `sunny.md` + `../rules/sunny-orchestrator.mdc` | Coordinates all agents, runs loops, enforces gates | No |
| 2 | **Context Agent** | `context-agent.md` | Shared memory; persists summaries to `.sunny/context/` | No |
| 3 | **JHipster Backend Agent** | `jhipster-backend-agent.md` | Generates the microservices backend | No |
| 4 | **JHipster Verify Agent** | `jhipster-verify-agent.md` | Audits backend (API, security, architecture, DB) | Yes |
| 5 | **Issue Resolution Agent** | `issue-resolution-agent.md` | Fixes issues found by the verify agent | No |
| 6 | **Backend Unit Test Agent** | `backend-unit-test-agent.md` | Isolated unit tests (services, mappers, validators) | No |
| 7 | **Backend Integration Test Agent** | `backend-integration-test-agent.md` | Repository/DB tests on Testcontainers PostgreSQL | No |
| 8 | **Backend Functional Test Agent** | `backend-functional-test-agent.md` | REST/API + gateway HTTP contract tests | No |
| 9 | **Backend Test Verify Agent** | `backend-test-verify-agent.md` | Verifies backend test completeness and >=95% coverage | Yes |
| 10 | **Backend Test Fix Agent** | `backend-test-fix-agent.md` | Closes backend test gaps | No |
| 11 | **Frontend Unit Test Agent** | `frontend-unit-test-agent.md` | Isolated unit tests (utils, hooks, stores) | No |
| 12 | **Frontend Integration Test Agent** | `frontend-integration-test-agent.md` | Component/page tests with MSW, routing, state | No |
| 13 | **Frontend Functional Test Agent** | `frontend-functional-test-agent.md` | E2E user journeys (Playwright) | No |
| 14 | **Frontend Test Verify Agent** | `frontend-test-verify-agent.md` | Verifies frontend test completeness and >=95% coverage | Yes |
| 15 | **Frontend Test Fix Agent** | `frontend-test-fix-agent.md` | Closes frontend test gaps | No |
| 16 | **Production Standards Agent** | `production-standards-agent.md` | Final security/readiness/performance audit | Yes |
| 17 | **Production Fix Agent** | `production-fix-agent.md` | Remediates production audit findings | No |

---

## How it works

Cursor sub-agents run in **isolation** and are launched via the Task tool. Because an isolated sub-agent has no memory of previous runs, all state lives in a **file-based context store** owned by the Context Agent. The main chat agent acts as the orchestration driver, following the playbook in `../rules/sunny-orchestrator.mdc`.

The golden rule: **after every agent runs, the Context Agent persists its output before the next agent starts.** No agent assumes in-memory state from a previous step.

> For the full set of architecture, loop, data-flow, and state-machine diagrams, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

```mermaid
flowchart TD
    User([User: build backend for this frontend]) --> Sunny[Sunny Orchestrator]
    Sunny --> Ctx[(".sunny/context/ shared memory")]

    subgraph dev [Stage 1 - Development]
        BE[JHipster Backend Agent]
    end
    subgraph verify [Stage 2 - Backend Verification Loop]
        VER[JHipster Verify Agent]
        FIX[Issue Resolution Agent]
    end
    subgraph btest [Stage 3 - Backend Testing Loop]
        BGEN["unit + integration + functional<br/>test agents"]
        BTV[Backend Test Verify Agent]
        BTF[Backend Test Fix Agent]
    end
    subgraph ftest [Stage 4 - Frontend Testing Loop]
        FGEN["unit + integration + functional<br/>test agents"]
        FTV[Frontend Test Verify Agent]
        FTF[Frontend Test Fix Agent]
    end
    subgraph prod [Stage 5 - Production Loop]
        PROD[Production Standards Agent]
        PFIX[Production Fix Agent]
    end

    Sunny --> BE
    BE --> VER
    VER -->|"Issues found"| FIX
    FIX --> VER
    VER -->|"No issues found. Backend approved."| BGEN
    BGEN --> BTV
    BTV -->|"not satisfied"| BTF
    BTF --> BTV
    BTV -->|"Backend testing requirements satisfied."| FGEN
    FGEN --> FTV
    FTV -->|"not satisfied"| FTF
    FTF --> FTV
    FTV -->|"Frontend testing requirements satisfied."| PROD
    PROD -->|"blocked"| PFIX
    PFIX --> PROD
    PROD -->|"Final approval granted."| Final(["Final Approval<br/>System is production-ready."])

    BE -.persist.-> Ctx
    VER -.persist.-> Ctx
    FIX -.persist.-> Ctx
    BGEN -.persist.-> Ctx
    BTV -.persist.-> Ctx
    BTF -.persist.-> Ctx
    FGEN -.persist.-> Ctx
    FTV -.persist.-> Ctx
    FTF -.persist.-> Ctx
    PROD -.persist.-> Ctx
    PFIX -.persist.-> Ctx
```

---

## Phase-by-phase workflow

```mermaid
sequenceDiagram
    participant U as User
    participant S as Sunny
    participant C as Context Agent
    participant B as Backend Agent
    participant V as Verify Agent
    participant I as Issue Resolution
    participant BT as Backend Test Agents
    participant BTV as Backend Test Verify
    participant FT as Frontend Test Agents
    participant FTV as Frontend Test Verify
    participant P as Production Standards
    participant PF as Production Fix

    U->>S: Frontend + requirements
    S->>C: Intake (create project-context.md, state.json)

    Note over S,B: Stage 1 - Backend generation
    S->>B: Generate JHipster microservices
    S->>C: Persist backend-summary.md

    Note over S,I: Stage 2 - Verification loop (max 5)
    loop Until "Backend approved" or max iterations
        S->>V: Audit backend
        S->>C: Persist verify-report.md
        alt Issues found
            S->>I: Fix findings
            S->>C: Persist issue-resolution-log.md
        else No issues found. Backend approved.
            Note over S: Exit loop
        end
    end

    Note over S,BTV: Stage 3 - Backend testing loop (max 5)
    S->>BT: unit, then integration, then functional
    S->>C: Persist backend-test-report.md
    loop Until "Backend testing requirements satisfied"
        S->>BTV: Verify backend coverage and layers
        S->>C: Persist backend-test-verify-report.md
        alt Not satisfied
            S->>BT: backend-test-fix-agent closes gaps
            S->>C: Persist backend-test-fix-log.md
        else Backend testing requirements satisfied.
            Note over S: Exit loop
        end
    end

    Note over S,FTV: Stage 4 - Frontend testing loop (max 5)
    S->>FT: unit, then integration, then functional
    S->>C: Persist frontend-test-report.md
    loop Until "Frontend testing requirements satisfied"
        S->>FTV: Verify frontend coverage and layers
        S->>C: Persist frontend-test-verify-report.md
        alt Not satisfied
            S->>FT: frontend-test-fix-agent closes gaps
            S->>C: Persist frontend-test-fix-log.md
        else Frontend testing requirements satisfied.
            Note over S: Exit loop
        end
    end

    Note over S,PF: Stage 5 - Production loop (max 5)
    loop Until "Final approval granted" or max iterations
        S->>P: Final audit
        S->>C: Persist production-report.md
        alt Blocked
            S->>PF: Remediate findings
            S->>C: Persist production-fix-log.md
        else Final approval granted. System is production-ready.
            Note over S: Exit loop
        end
    end
    S->>U: Summary + run guide
```

---

## Loop control and exit phrases

The orchestrator looks for **exact** verdict phrases to exit each loop:

| Loop | Exit phrase | Driven by |
|------|-------------|-----------|
| Backend verification | `No issues found. Backend approved.` | JHipster Verify Agent |
| Backend testing | `Backend testing requirements satisfied.` | Backend Test Verify Agent |
| Frontend testing | `Frontend testing requirements satisfied.` | Frontend Test Verify Agent |
| Production | `Final approval granted. System is production-ready.` | Production Standards Agent |

Each loop has a **max-iteration cap (default 5)** tracked in `state.json` (`backendVerifyIterations`, `backendTestVerifyIterations`, `frontendTestVerifyIterations`, `productionVerifyIterations`). If a loop hits the cap without the exit phrase, Sunny sets `phase: "blocked"`, records the blockers, stops, and escalates to the user instead of looping forever.

---

## Shared memory (`.sunny/context/`)

Created and maintained at runtime by the Context Agent. Other agents **read** from it; only the Context Agent **writes** to it.

```
.sunny/context/
├── project-context.md             # Frontend-derived domain model, API contract, auth, requirements
├── backend-summary.md             # Backend generation output
├── verify-report.md               # Latest backend verification findings + verdict
├── issue-resolution-log.md        # History of backend code fix cycles
├── backend-test-report.md         # Backend test generation output + coverage
├── backend-test-verify-report.md  # Backend test verification findings + verdict
├── backend-test-fix-log.md        # History of backend test fix cycles
├── frontend-test-report.md        # Frontend test generation output + coverage
├── frontend-test-verify-report.md # Frontend test verification findings + verdict
├── frontend-test-fix-log.md       # History of frontend test fix cycles
├── production-report.md           # Latest production audit findings + verdict
├── production-fix-log.md          # History of production remediation cycles
└── state.json                     # phase, loop counters, lastVerdict, blockers
```

### `state.json` drives the loops

```json
{
  "workflowId": "...",
  "phase": "testing_backend",
  "backendVerifyIterations": 2,
  "backendTestVerifyIterations": 1,
  "frontendTestVerifyIterations": 0,
  "productionVerifyIterations": 0,
  "maxIterations": 5,
  "lastVerdict": "Backend testing requirements not met.",
  "blockers": [],
  "completedAgents": ["context-agent", "jhipster-backend-agent", "jhipster-verify-agent"],
  "updatedAt": "2026-06-12T06:20:00Z"
}
```

---

## How to run it

1. **Invoke Sunny** in a Cursor chat, pointing at your frontend:

   > Sunny, build the JHipster microservices backend for the frontend in `./frontend`.

2. The main agent loads `../rules/sunny-orchestrator.mdc` and drives the workflow:
   - Analyzes the frontend and runs intake through the Context Agent.
   - Generates the backend, then loops verify ↔ fix until approved.
   - Generates tests, then loops test ↔ verify until coverage is satisfied.
   - Runs the final production audit.

3. **Watch progress** via Sunny's phase announcements (e.g. "Starting backend verification, iteration 2/5") and the contents of `.sunny/context/`.

4. **On completion**, Sunny delivers a summary: architecture, services, coverage, security posture, and a run guide. On a blocked loop, Sunny lists the blockers and asks how to proceed.

---

## Design notes

- **Why a rule + an agent file for Sunny?** The `.mdc` rule is the executable playbook the main chat agent (which reliably has the Task tool) follows. The `sunny.md` agent file documents the persona and can be invoked directly to produce the next orchestration step.
- **Why a file-based Context Agent?** Sub-agents are isolated and context windows are limited. Persisting trimmed, structured summaries to disk lets long-running, multi-loop workflows survive across many isolated agent runs without losing critical decisions.
- **Why readonly verify/audit agents?** Verification must be objective and side-effect free. The verify, test-verify, and production agents only read and report; fixes are made exclusively by the Backend, Issue Resolution, and Testing agents.

---

## Standalone agents (not part of Sunny)

These live alongside the Sunny agents but run on demand and are **not** invoked by the orchestrator:

| Agent | File | Role |
|-------|------|------|
| **Documentation** | `documentation.md` | Complete Swagger/OpenAPI docs, Postman collections + environments (Newman CI), and Javadoc for a Spring Boot / JHipster codebase — leaving nothing undocumented. |
