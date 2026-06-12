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
| 6 | **Testing Agent** | `testing-agent.md` | Generates backend + frontend tests | No |
| 7 | **Test Verify Agent** | `test-verify-agent.md` | Verifies test completeness and >=95% coverage | Yes |
| 8 | **Production Standards Agent** | `production-standards-agent.md` | Final security/readiness/performance audit | Yes |

---

## How it works

Cursor sub-agents run in **isolation** and are launched via the Task tool. Because an isolated sub-agent has no memory of previous runs, all state lives in a **file-based context store** owned by the Context Agent. The main chat agent acts as the orchestration driver, following the playbook in `../rules/sunny-orchestrator.mdc`.

The golden rule: **after every agent runs, the Context Agent persists its output before the next agent starts.** No agent assumes in-memory state from a previous step.

> For the full set of architecture, loop, data-flow, and state-machine diagrams, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

```mermaid
flowchart TD
    User([User: build backend for this frontend]) --> Sunny[Sunny Orchestrator]
    Sunny --> Ctx[(".sunny/context/ shared memory")]

    subgraph dev [Development]
        BE[JHipster Backend Agent]
    end
    subgraph verify [Backend Verification Loop]
        VER[JHipster Verify Agent]
        FIX[Issue Resolution Agent]
    end
    subgraph test [Testing Loop]
        TEST[Testing Agent]
        TVER[Test Verify Agent]
    end
    subgraph prod [Production]
        PROD[Production Standards Agent]
    end

    Sunny --> BE
    BE --> VER
    VER -->|"Issues found"| FIX
    FIX --> VER
    VER -->|"No issues found. Backend approved."| TEST
    TEST --> TVER
    TVER -->|"Coverage < 95%"| TEST
    TVER -->|"Testing requirements satisfied."| PROD
    PROD --> Final([Final Approval])

    BE -.persist.-> Ctx
    VER -.persist.-> Ctx
    FIX -.persist.-> Ctx
    TEST -.persist.-> Ctx
    TVER -.persist.-> Ctx
    PROD -.persist.-> Ctx
    Ctx -.handoff.-> BE
    Ctx -.handoff.-> VER
    Ctx -.handoff.-> FIX
    Ctx -.handoff.-> TEST
    Ctx -.handoff.-> TVER
    Ctx -.handoff.-> PROD
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
    participant T as Testing Agent
    participant TV as Test Verify
    participant P as Production Standards

    U->>S: Frontend + requirements
    S->>C: Intake (create project-context.md, state.json)

    Note over S,B: Phase 1 - Backend generation
    S->>B: Generate JHipster microservices
    B->>C: Persist backend-summary.md

    Note over S,I: Phase 2 - Verification loop (max 5)
    loop Until "Backend approved" or max iterations
        S->>V: Audit backend
        V->>C: Persist verify-report.md
        alt Issues found
            S->>I: Fix findings
            I->>C: Persist issue-resolution-log.md
        else No issues found. Backend approved.
            Note over S: Exit loop
        end
    end

    Note over S,TV: Phase 3 - Testing loop (max 5)
    S->>T: Generate tests (95% target)
    T->>C: Persist test-report.md
    loop Until "Testing requirements satisfied" or max iterations
        S->>TV: Verify coverage and edge cases
        TV->>C: Persist test-verify-report.md
        alt Coverage < 95%
            S->>T: Add tests for gaps
            T->>C: Persist test-report.md
        else Testing requirements satisfied.
            Note over S: Exit loop
        end
    end

    Note over S,P: Phase 4 - Production
    S->>P: Final audit
    P->>C: Persist production-report.md
    P->>S: Final approval granted
    S->>U: Summary + run guide
```

---

## Loop control and exit phrases

The orchestrator looks for **exact** verdict phrases to exit each loop:

| Loop | Exit phrase | Driven by |
|------|-------------|-----------|
| Backend verification | `No issues found. Backend approved.` | JHipster Verify Agent |
| Testing | `Testing requirements satisfied.` | Test Verify Agent |
| Final | `Final approval granted. System is production-ready.` | Production Standards Agent |

Each loop has a **max-iteration cap (default 5)** tracked in `state.json` (`backendVerifyIterations`, `testVerifyIterations`). If a loop hits the cap without the exit phrase, Sunny sets `phase: "blocked"`, records the blockers, stops, and escalates to the user instead of looping forever.

---

## Shared memory (`.sunny/context/`)

Created and maintained at runtime by the Context Agent. Other agents **read** from it; only the Context Agent **writes** to it.

```
.sunny/context/
├── project-context.md      # Frontend-derived domain model, API contract, auth, requirements
├── backend-summary.md      # Backend generation output
├── verify-report.md        # Latest backend verification findings + verdict
├── issue-resolution-log.md # History of fix cycles
├── test-report.md          # Latest test generation output + coverage
├── test-verify-report.md   # Latest test verification findings + verdict
├── production-report.md     # Final production audit
└── state.json              # phase, loop counters, lastVerdict, blockers
```

### `state.json` drives the loops

```json
{
  "workflowId": "...",
  "phase": "backend_verify",
  "backendVerifyIterations": 2,
  "testVerifyIterations": 0,
  "maxIterations": 5,
  "lastVerdict": "Issues found. Backend not approved.",
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
