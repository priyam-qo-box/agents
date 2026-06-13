# Sunny Orchestrator — Architecture & Workflow

Visual reference for the Sunny multi-agent system: component architecture, control flow, the verification/testing/production loops, shared-memory data flow, and state transitions.

> For prose explanation and run instructions, see [`README.md`](README.md).

---

## 0. System at a glance

**34 orchestrated agents** (plus a standalone documentation agent), driven through **11 bounded verify/fix loops**.

| Group | Count | Agents |
|-------|-------|--------|
| Orchestration & memory | 2 | `sunny`, `context-agent` |
| Architecture & boilerplate | 3 | `architecture-agent`, `architecture-verify-agent` (readonly), `architecture-fix-agent` |
| Backend build & verify | 3 | `jhipster-backend-agent`, `jhipster-verify-agent` (readonly), `issue-resolution-agent` |
| Database | 3 | `database-agent`, `database-verify-agent` (readonly), `database-fix-agent` |
| Backend tests (3 layers × gen/verify/fix) | 9 | `backend-{unit,integration,functional}-test-agent` + `-verify-agent` (readonly) + `-fix-agent` |
| Frontend tests (3 layers × gen/verify/fix) | 9 | `frontend-{unit,integration,functional}-test-agent` + `-verify-agent` (readonly) + `-fix-agent` |
| System integration tests (collective) | 3 | `system-integration-test-agent`, `system-integration-test-verify-agent` (readonly), `system-integration-test-fix-agent` |
| Production | 2 | `production-standards-agent` (readonly), `production-fix-agent` |
| Standalone (not orchestrated) | 1 | `documentation` |

- **11 verify/fix loops:** architecture + backend code + database + 3 backend test layers + 3 frontend test layers + system integration + production.
- **11 readonly auditors:** `architecture-verify-agent`, `jhipster-verify-agent`, `database-verify-agent`, the 6 per-layer test-verify agents, `system-integration-test-verify-agent`, and `production-standards-agent`.
- **Pipeline order:** architecture → backend (JHipster) → database → backend tests → frontend tests → system integration tests → production.
- **Every loop:** independent exit phrase + iteration counter, capped at **5** before escalating.
- **One writer of shared memory:** `context-agent` owns `.sunny/context/`.

---

## 1. System architecture (pipeline order)

The agents run as an **ordered pipeline**: design the architecture, generate the backend, verify and fix it, harden the database, then generate and verify tests (backend, then frontend), then collective system integration tests (frontend + backend + database together), then the final production audit. The Driver (main chat agent) launches each stage via the Task tool, and the Context Agent persists output between every stage. Read top to bottom — generation always precedes verification.

```mermaid
flowchart TB
    User([User]) --> Driver["Driver: main chat agent<br/>follows sunny-orchestrator.mdc"]

    subgraph pipeline [Execution Pipeline - top to bottom]
        direction TB
        S0["Stage 1 - Architecture & boilerplate<br/>architecture-agent<br/>verify: architecture-verify-agent (readonly)<br/>fix: architecture-fix-agent"]
        S1["Stage 2 - Generate backend<br/>jhipster-backend-agent"]
        S2["Stage 3 - Verify backend (readonly)<br/>jhipster-verify-agent<br/>fix: issue-resolution-agent"]
        SD["Stage 4 - Database hardening<br/>database-agent<br/>verify: database-verify-agent (readonly)<br/>fix: database-fix-agent"]
        S3["Stage 5 - Backend tests<br/>per layer: unit, integration, functional<br/>each layer has its own verify (readonly) + fix agent"]
        S4["Stage 6 - Frontend tests<br/>per layer: unit, integration, functional<br/>each layer has its own verify (readonly) + fix agent"]
        SI["Stage 7 - System integration tests (collective)<br/>frontend + backend + PostgreSQL together<br/>system-integration-test-agent<br/>verify: system-integration-test-verify-agent (readonly)<br/>fix: system-integration-test-fix-agent"]
        S5["Stage 8 - Production (readonly audit)<br/>production-standards-agent<br/>fix: production-fix-agent"]
        S0 --> S1 --> S2 --> SD --> S3 --> S4 --> SI --> S5
    end

    Driver -->|launches each stage in order| pipeline

    subgraph memory [Shared Memory]
        Ctx["context-agent"]
        Store[(".sunny/context/<br/>reports + state.json")]
        Ctx <-->|read / write| Store
    end

    pipeline -.output after each stage.-> Ctx
    Ctx -.trimmed handoff to next stage.-> pipeline
```

### 1.1 Agents and their responsibilities

Each agent with its key points, grouped by stage. Readonly agents only audit and report; all others write code/tests/config.

```mermaid
flowchart TB
    subgraph orch [Orchestration and Memory]
        direction LR
        DRV["Sunny / Driver<br/>• Orchestrates all 11 verify/fix loops<br/>• Matches exact exit phrases<br/>• Enforces quality gates<br/>• Escalates when blocked"]
        CTX["context-agent<br/>• Sole writer of .sunny/context<br/>• Structured summaries + state.json<br/>• Trims handoffs to next agent<br/>• Tracks phase + iteration counters"]
    end

    subgraph sArch [Stage 1 - Architecture and boilerplate]
        direction LR
        ARC["architecture-agent<br/>• Service decomposition (bounded contexts)<br/>• Domain model + API contract map<br/>• Draft JDL + boilerplate/scaffolding<br/>• Microservices, PostgreSQL, no mock data"]
        ARCV["architecture-verify-agent - readonly<br/>• Decomposition + API coverage review<br/>• JDL consistency + auth design<br/>• Exit: Architecture approved."]
        ARCF["architecture-fix-agent<br/>• Fixes blueprint/JDL/boilerplate findings"]
        ARC --> ARCV
        ARCV -->|issues| ARCF --> ARCV
    end

    subgraph s12 [Stage 2-3 - Backend build and verify]
        direction LR
        GEN["jhipster-backend-agent<br/>• Microservices: gateway + services + registry<br/>• PostgreSQL + Liquibase<br/>• JWT/OAuth2 + RBAC, Docker<br/>• No mock/fake data"]
        VER["jhipster-verify-agent - readonly<br/>• REST/OpenAPI/RFC7807 audit<br/>• Auth + vulnerability checks<br/>• Microservices + DB integrity<br/>• Exit: No issues found. Backend approved."]
        ISS["issue-resolution-agent<br/>• Fixes every verify finding<br/>• No control weakening<br/>• Rebuild + run tests<br/>• Returns for re-audit"]
        GEN --> VER
        VER -->|issues| ISS --> VER
    end

    subgraph sDb [Stage 4 - Database hardening]
        direction LR
        DBA["database-agent<br/>• PostgreSQL connections + HikariCP<br/>• Liquibase migrations, constraints, indexes<br/>• Schema standards, no mock data"]
        DBV["database-verify-agent - readonly<br/>• Schema/migrations + integrity audit<br/>• Migrations apply on fresh PostgreSQL<br/>• Exit: Database approved."]
        DBF["database-fix-agent<br/>• Fixes DB connection/schema/migration findings"]
        DBA --> DBV
        DBV -->|issues| DBF --> DBV
    end

    subgraph s3 [Stage 3 - Backend testing - per-layer verify and fix]
        direction TB
        subgraph s3u [Unit layer]
            direction LR
            BU["backend-unit-test-agent<br/>• JUnit5 + Mockito<br/>• Services, mappers, validators<br/>• Fully mocked/isolated"]
            BUV["backend-unit-test-verify-agent - readonly<br/>• Unit coverage + isolation<br/>• Exit: Backend unit testing requirements satisfied."]
            BUF["backend-unit-test-fix-agent<br/>• Closes unit-layer gaps"]
            BU --> BUV
            BUV -->|gaps| BUF --> BUV
        end
        subgraph s3i [Integration layer]
            direction LR
            BI["backend-integration-test-agent<br/>• Testcontainers PostgreSQL<br/>• Repos, queries, migrations<br/>• Real DB, no H2"]
            BIV["backend-integration-test-verify-agent - readonly<br/>• Real-DB + integration coverage<br/>• Exit: Backend integration testing requirements satisfied."]
            BIF["backend-integration-test-fix-agent<br/>• Closes integration-layer gaps"]
            BI --> BIV
            BIV -->|gaps| BIF --> BIV
        end
        subgraph s3f [Functional layer]
            direction LR
            BF["backend-functional-test-agent<br/>• REST Assured / MockMvc<br/>• Endpoints, auth, pagination<br/>• ProblemDetails + gateway E2E"]
            BFV["backend-functional-test-verify-agent - readonly<br/>• Endpoint + contract coverage<br/>• Exit: Backend functional testing requirements satisfied."]
            BFF["backend-functional-test-fix-agent<br/>• Closes functional-layer gaps"]
            BF --> BFV
            BFV -->|gaps| BFF --> BFV
        end
        s3u --> s3i --> s3f
    end

    subgraph s4 [Stage 4 - Frontend testing - per-layer verify and fix]
        direction TB
        subgraph s4u [Unit layer]
            direction LR
            FU["frontend-unit-test-agent<br/>• Vitest/Jest<br/>• Utils, hooks, stores<br/>• Isolated"]
            FUV["frontend-unit-test-verify-agent - readonly<br/>• Unit coverage + isolation<br/>• Exit: Frontend unit testing requirements satisfied."]
            FUF["frontend-unit-test-fix-agent<br/>• Closes unit-layer gaps"]
            FU --> FUV
            FUV -->|gaps| FUF --> FUV
        end
        subgraph s4i [Integration / component layer]
            direction LR
            FI["frontend-integration-test-agent<br/>• Testing Library + MSW<br/>• Components, pages, routing<br/>• Events + loading/error states"]
            FIV["frontend-integration-test-verify-agent - readonly<br/>• Component coverage + states<br/>• Exit: Frontend integration testing requirements satisfied."]
            FIF["frontend-integration-test-fix-agent<br/>• Closes component-layer gaps"]
            FI --> FIV
            FIV -->|gaps| FIF --> FIV
        end
        subgraph s4f [Functional / E2E layer]
            direction LR
            FF["frontend-functional-test-agent<br/>• Playwright E2E<br/>• Critical user journeys<br/>• Login, CRUD, navigation"]
            FFV["frontend-functional-test-verify-agent - readonly<br/>• Journey coverage in real browser<br/>• Exit: Frontend functional testing requirements satisfied."]
            FFF["frontend-functional-test-fix-agent<br/>• Closes E2E journey gaps"]
            FF --> FFV
            FFV -->|gaps| FFF --> FFV
        end
        s4u --> s4i --> s4f
    end

    subgraph sSi [Stage 7 - System integration testing - collective full-stack]
        direction LR
        SI["system-integration-test-agent<br/>• Runs whole stack together<br/>• Real frontend + gateway + services + PostgreSQL<br/>• Cross-tier journeys + auth propagation"]
        SIV["system-integration-test-verify-agent - readonly<br/>• Full-stack journey coverage on real stack<br/>• UI + API + DB persistence asserted<br/>• Exit: System integration testing requirements satisfied."]
        SIF["system-integration-test-fix-agent<br/>• Closes cross-tier journey gaps"]
        SI --> SIV
        SIV -->|gaps| SIF --> SIV
    end

    subgraph s5 [Stage 8 - Production]
        direction LR
        PS["production-standards-agent - readonly<br/>• Security + readiness audit<br/>• Industry standards + performance<br/>• Requires prior approved verdicts<br/>• Exit: Final approval granted. System is production-ready."]
        PF["production-fix-agent<br/>• Remediates PR findings<br/>• No control weakening<br/>• Rebuild + run tests<br/>• Returns for re-audit"]
        PS -->|blocked| PF --> PS
    end

    orch --> sArch --> s12 --> sDb --> s3 --> s4 --> sSi --> s5
```

---

## 2. End-to-end workflow (control flow)

The strict call order with all loops and their exact exit phrases.

```mermaid
flowchart TD
    Start([Frontend Input]) --> Intake["Intake<br/>context-agent creates<br/>project-context.md + state.json"]

    Intake --> AGen[architecture-agent]
    AGen --> PA1["context-agent<br/>architecture-summary.md"]
    PA1 --> AVer[architecture-verify-agent]
    AVer --> PA2["context-agent<br/>architecture-verify-report.md"]
    PA2 --> AApproved{"lastVerdict ==<br/>'Architecture approved.'?"}
    AApproved -->|No| CapA{"architectureVerifyIterations<br/>>= 5?"}
    CapA -->|No| AFix[architecture-fix-agent] --> PA3["context-agent<br/>architecture-fix-log.md"] --> AVer
    CapA -->|Yes| Blocked["phase = blocked<br/>escalate to user"]

    AApproved -->|Yes| Gen[jhipster-backend-agent]
    Gen --> P1["context-agent<br/>backend-summary.md"]

    P1 --> Verify[jhipster-verify-agent]
    Verify --> P2["context-agent<br/>verify-report.md"]
    P2 --> Approved{"lastVerdict ==<br/>'No issues found.<br/>Backend approved.'?"}
    Approved -->|No| CapB{"backendVerifyIterations<br/>>= 5?"}
    CapB -->|No| Fix[issue-resolution-agent] --> P3["context-agent<br/>issue-resolution-log.md"] --> Verify
    CapB -->|Yes| Blocked

    Approved -->|Yes| DGen[database-agent]
    DGen --> PD1["context-agent<br/>database-summary.md"]
    PD1 --> DVer[database-verify-agent]
    DVer --> PD2["context-agent<br/>database-verify-report.md"]
    PD2 --> DApproved{"lastVerdict ==<br/>'Database approved.'?"}
    DApproved -->|No| CapD{"databaseVerifyIterations<br/>>= 5?"}
    CapD -->|No| DFix[database-fix-agent] --> PD3["context-agent<br/>database-fix-log.md"] --> DVer
    CapD -->|Yes| Blocked

    DApproved -->|Yes| BGen["backend test generation<br/>unit + integration + functional<br/>context-agent: backend-test-report.md"]
    BGen --> BLoop["Backend per-layer verify/fix loops<br/>(see Section 4)<br/>unit -> integration -> functional<br/>each: verify -> fix -> re-verify, cap 5"]
    BLoop --> BSat{"all 3 backend layers<br/>satisfied?"}
    BSat -->|No, any layer hit cap 5| Blocked
    BSat -->|Yes| FGen

    FGen["frontend test generation<br/>unit + integration + functional<br/>context-agent: frontend-test-report.md"]
    FGen --> FLoop["Frontend per-layer verify/fix loops<br/>(see Section 5)<br/>unit -> integration -> functional<br/>each: verify -> fix -> re-verify, cap 5"]
    FLoop --> FSat{"all 3 frontend layers<br/>satisfied?"}
    FSat -->|No, any layer hit cap 5| Blocked
    FSat -->|Yes| SIGen[system-integration-test-agent]

    SIGen --> PSI1["context-agent<br/>system-integration-test-report.md"]
    PSI1 --> SIVer[system-integration-test-verify-agent]
    SIVer --> PSI2["context-agent<br/>system-integration-test-verify-report.md"]
    PSI2 --> SISat{"lastVerdict ==<br/>'System integration testing<br/>requirements satisfied.'?"}
    SISat -->|No| CapSI{"systemIntegrationTestVerifyIterations<br/>>= 5?"}
    CapSI -->|No| SIFix[system-integration-test-fix-agent] --> PSI3["context-agent<br/>system-integration-test-fix-log.md"] --> SIVer
    CapSI -->|Yes| Blocked
    SISat -->|Yes| Prod[production-standards-agent]
    Prod --> P10["context-agent<br/>production-report.md"]
    P10 --> PSat{"lastVerdict ==<br/>'Final approval granted.<br/>System is production-ready.'?"}
    PSat -->|No| CapP{"productionVerifyIterations<br/>>= 5?"}
    CapP -->|No| PFix[production-fix-agent] --> P11["context-agent<br/>production-fix-log.md"] --> Prod
    CapP -->|Yes| Blocked
    PSat -->|Yes| Final(["Final Approval<br/>System is production-ready."])
```

---

## 3. Code-level loops (detail)

Three generate → verify → fix loops run in order before testing: **architecture**, **backend code**, **database**. Each has its own exit phrase and iteration counter.

### 3.1 Architecture loop

```mermaid
flowchart LR
    G[architecture-agent] --> A[architecture-verify-agent]
    A --> B["context-agent<br/>architecture-verify-report.md"]
    B --> C{"Architecture approved?"}
    C -->|Yes| Exit([Exit to Backend generation])
    C -->|No| D{architectureVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[architecture-fix-agent]
    E --> F["context-agent<br/>architecture-fix-log.md"]
    F --> A
```

### 3.2 Backend code verification loop

```mermaid
flowchart LR
    A[jhipster-verify-agent] --> B["context-agent<br/>verify-report.md"]
    B --> C{Issues?}
    C -->|"No issues found.<br/>Backend approved."| Exit([Exit to Database])
    C -->|Issues found| D{backendVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[issue-resolution-agent]
    E --> F["context-agent<br/>issue-resolution-log.md"]
    F --> A
```

### 3.3 Database loop

```mermaid
flowchart LR
    G[database-agent] --> A[database-verify-agent]
    A --> B["context-agent<br/>database-verify-report.md"]
    B --> C{"Database approved?"}
    C -->|Yes| Exit([Exit to Backend tests])
    C -->|No| D{databaseVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[database-fix-agent]
    E --> F["context-agent<br/>database-fix-log.md"]
    F --> A
```

## 4. Backend testing loops (detail)

The three generation agents run **once** in order. Then each layer has its **own verify/fix loop** with its own exit phrase and counter, run in order: unit → integration → functional. Each layer's fix agent only touches that layer.

```mermaid
flowchart TB
    G1[backend-unit-test-agent] --> G2[backend-integration-test-agent] --> G3[backend-functional-test-agent]
    G3 --> P["context-agent<br/>backend-test-report.md"]

    P --> UA[backend-unit-test-verify-agent]
    UA --> UB{"unit satisfied?<br/>'Backend unit testing<br/>requirements satisfied.'"}
    UB -->|No| UD{backendUnitTestVerifyIterations >= 5?}
    UD -->|Yes| Stop([Blocked - escalate])
    UD -->|No| UE[backend-unit-test-fix-agent] --> UF["context-agent<br/>backend-unit-test-fix-log.md"] --> UA
    UB -->|Yes| IA[backend-integration-test-verify-agent]

    IA --> IB{"integration satisfied?<br/>'Backend integration testing<br/>requirements satisfied.'"}
    IB -->|No| ID{backendIntegrationTestVerifyIterations >= 5?}
    ID -->|Yes| Stop
    ID -->|No| IE[backend-integration-test-fix-agent] --> IF["context-agent<br/>backend-integration-test-fix-log.md"] --> IA
    IB -->|Yes| FA[backend-functional-test-verify-agent]

    FA --> FB{"functional satisfied?<br/>'Backend functional testing<br/>requirements satisfied.'"}
    FB -->|No| FD{backendFunctionalTestVerifyIterations >= 5?}
    FD -->|Yes| Stop
    FD -->|No| FE[backend-functional-test-fix-agent] --> FF["context-agent<br/>backend-functional-test-fix-log.md"] --> FA
    FB -->|Yes| Exit([Exit to Frontend tests])
```

## 5. Frontend testing loops (detail)

Same per-layer structure for the frontend: generate once, then unit → integration/component → functional/E2E, each with its own verify/fix loop, exit phrase, and counter.

```mermaid
flowchart TB
    G1[frontend-unit-test-agent] --> G2[frontend-integration-test-agent] --> G3[frontend-functional-test-agent]
    G3 --> P["context-agent<br/>frontend-test-report.md"]

    P --> UA[frontend-unit-test-verify-agent]
    UA --> UB{"unit satisfied?<br/>'Frontend unit testing<br/>requirements satisfied.'"}
    UB -->|No| UD{frontendUnitTestVerifyIterations >= 5?}
    UD -->|Yes| Stop([Blocked - escalate])
    UD -->|No| UE[frontend-unit-test-fix-agent] --> UF["context-agent<br/>frontend-unit-test-fix-log.md"] --> UA
    UB -->|Yes| IA[frontend-integration-test-verify-agent]

    IA --> IB{"integration satisfied?<br/>'Frontend integration testing<br/>requirements satisfied.'"}
    IB -->|No| ID{frontendIntegrationTestVerifyIterations >= 5?}
    ID -->|Yes| Stop
    ID -->|No| IE[frontend-integration-test-fix-agent] --> IF["context-agent<br/>frontend-integration-test-fix-log.md"] --> IA
    IB -->|Yes| FA[frontend-functional-test-verify-agent]

    FA --> FB{"functional satisfied?<br/>'Frontend functional testing<br/>requirements satisfied.'"}
    FB -->|No| FD{frontendFunctionalTestVerifyIterations >= 5?}
    FD -->|Yes| Stop
    FD -->|No| FE[frontend-functional-test-fix-agent] --> FF["context-agent<br/>frontend-functional-test-fix-log.md"] --> FA
    FB -->|Yes| Exit([Exit to System integration tests])
```

## 5.5 System integration testing loop (detail)

After both backend (§4) and frontend (§5) testing stages are satisfied, the collective full-stack loop runs the **whole system together** — the real frontend driving the real gateway + microservices, persisting to a real **PostgreSQL** database — to validate cross-tier journeys, auth propagation, and persistence. Generate once, then a single verify/fix loop.

```mermaid
flowchart LR
    G[system-integration-test-agent] --> A[system-integration-test-verify-agent]
    A --> B["context-agent<br/>system-integration-test-verify-report.md"]
    B --> C{"System integration testing<br/>requirements satisfied?"}
    C -->|Yes| Exit([Exit to Production])
    C -->|No| D{systemIntegrationTestVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[system-integration-test-fix-agent]
    E --> F["context-agent<br/>system-integration-test-fix-log.md"]
    F --> A
```

## 6. Production loop (detail)

```mermaid
flowchart LR
    A[production-standards-agent] --> B["context-agent<br/>production-report.md"]
    B --> C{"lastVerdict ==<br/>'Final approval granted.<br/>System is production-ready.'?"}
    C -->|Yes| Exit([Final Approval])
    C -->|No| D{productionVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[production-fix-agent]
    E --> F["context-agent<br/>production-fix-log.md"]
    F --> A
```

---

## 7. What happens when something fails (fix and re-verify)

Every stage uses the **same failure-handling mechanism**. When a verify/audit agent does not emit its exact exit phrase, the work goes to the matching fix agent, then back for a fresh re-audit — bounded by the 5-iteration cap.

```mermaid
flowchart TD
    V["verify / audit agent<br/>(readonly)"] --> R["Reports findings table<br/>ID, severity, category, location, fix"]
    R --> P["context-agent<br/>persist report<br/>set lastVerdict<br/>increment counter"]
    P --> Q{"exact exit<br/>phrase emitted?"}
    Q -->|Yes| Next([Advance to next stage])
    Q -->|No| Cap{"counter >= 5?"}
    Cap -->|Yes| Blocked["phase = blocked<br/>Sunny stops and escalates<br/>with blockers from state.json"]
    Cap -->|No| Fix["fix agent<br/>• reads findings as work queue<br/>• fixes every item by severity<br/>• no control / gate weakening<br/>• rebuild + run affected tests"]
    Fix --> P2["context-agent<br/>append fix-log"]
    P2 --> V
```

### The rules that make this safe

1. **The fixer cannot mark its own homework.** Only the readonly verify/audit agent can emit the exit phrase. A fix is "accepted" only when an independent re-audit passes.
2. **Re-verification is from scratch.** The verify agent re-audits the real code with no memory of the fixes, so an incomplete fix is caught again.
3. **One round = one iteration.** Each verify run increments that loop's own counter (`architectureVerifyIterations`; `backendVerifyIterations`; `databaseVerifyIterations`; the six per-layer test counters `backend/frontend{Unit,Integration,Functional}TestVerifyIterations`; `systemIntegrationTestVerifyIterations`; `productionVerifyIterations`).
4. **The cap is checked before fixing again.** If the counter hits `maxIterations` (default 5) without the exit phrase, Sunny sets `phase: "blocked"`, stops, and hands the remaining blockers to the user — never an infinite loop.
5. **New findings are allowed.** A fix may surface fresh issues; they appear in the next report and are addressed in the next round (while under the cap).
6. **Fixers never weaken controls.** They do not disable auth, loosen CORS to `*`, remove validation, lower coverage thresholds, or introduce mock data to force a pass — they fix the root cause.

### Same mechanism across all eleven loops

| Loop | Verify / audit agent | Fix agent | Counter | Exit phrase |
|------|----------------------|-----------|---------|-------------|
| Architecture | `architecture-verify-agent` | `architecture-fix-agent` | `architectureVerifyIterations` | `Architecture approved.` |
| Backend code | `jhipster-verify-agent` | `issue-resolution-agent` | `backendVerifyIterations` | `No issues found. Backend approved.` |
| Database | `database-verify-agent` | `database-fix-agent` | `databaseVerifyIterations` | `Database approved.` |
| Backend unit tests | `backend-unit-test-verify-agent` | `backend-unit-test-fix-agent` | `backendUnitTestVerifyIterations` | `Backend unit testing requirements satisfied.` |
| Backend integration tests | `backend-integration-test-verify-agent` | `backend-integration-test-fix-agent` | `backendIntegrationTestVerifyIterations` | `Backend integration testing requirements satisfied.` |
| Backend functional tests | `backend-functional-test-verify-agent` | `backend-functional-test-fix-agent` | `backendFunctionalTestVerifyIterations` | `Backend functional testing requirements satisfied.` |
| Frontend unit tests | `frontend-unit-test-verify-agent` | `frontend-unit-test-fix-agent` | `frontendUnitTestVerifyIterations` | `Frontend unit testing requirements satisfied.` |
| Frontend integration tests | `frontend-integration-test-verify-agent` | `frontend-integration-test-fix-agent` | `frontendIntegrationTestVerifyIterations` | `Frontend integration testing requirements satisfied.` |
| Frontend functional tests | `frontend-functional-test-verify-agent` | `frontend-functional-test-fix-agent` | `frontendFunctionalTestVerifyIterations` | `Frontend functional testing requirements satisfied.` |
| System integration tests | `system-integration-test-verify-agent` | `system-integration-test-fix-agent` | `systemIntegrationTestVerifyIterations` | `System integration testing requirements satisfied.` |
| Production | `production-standards-agent` | `production-fix-agent` | `productionVerifyIterations` | `Final approval granted. System is production-ready.` |

> Each side's three generation agents (unit/integration/functional) run once at the start; then each layer has its own verify/fix loop. On failure the layer's fix agent adds or repairs that layer's tests, then the layer re-verifies — the generators are not re-run.

---

## 8. Phase sequence (who talks to whom, when)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant S as Sunny (driver)
    participant C as Context Agent
    participant A as Architecture (gen+verify+fix)
    participant B as Backend Agent
    participant V as Verify Agent
    participant I as Issue Resolution
    participant D as Database (gen+verify+fix)
    participant BT as Backend Test Gen+Fix (per layer)
    participant BTV as Backend Layer Verifiers
    participant FT as Frontend Test Gen+Fix (per layer)
    participant FTV as Frontend Layer Verifiers
    participant SI as System Integration Gen+Fix
    participant SIV as System Integration Verify
    participant P as Production Standards
    participant PF as Production Fix

    U->>S: Frontend + requirements
    S->>C: Intake (project-context.md, state.json)

    rect rgb(120,120,120)
    note right of S: Stage 1 - Architecture (max 5)
    S->>A: Design blueprint + boilerplate
    A-->>S: architecture-summary
    S->>C: Persist architecture-summary.md
    loop until "Architecture approved"
        S->>A: Verify blueprint (readonly)
        A-->>S: report + verdict
        S->>C: Persist architecture-verify-report.md
        alt Not approved and iter < 5
            S->>A: architecture-fix-agent closes findings
            S->>C: Persist architecture-fix-log.md
        else Approved or max iterations
            note over S: break or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 2-3 - Generate and verify backend
    S->>B: Generate JHipster microservices
    B-->>S: backend output
    S->>C: Persist backend-summary.md
    loop until "Backend approved"
        S->>V: Audit backend
        V-->>S: verify report + verdict
        S->>C: Persist verify-report.md
        alt Issues found and iter < 5
            S->>I: Fix findings
            I-->>S: fix summary
            S->>C: Persist issue-resolution-log.md
        else Approved or max iterations
            note over S: break or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 4 - Database hardening (max 5)
    S->>D: Harden connections, schema, migrations
    D-->>S: database-summary
    S->>C: Persist database-summary.md
    loop until "Database approved"
        S->>D: Verify DB layer (readonly)
        D-->>S: report + verdict
        S->>C: Persist database-verify-report.md
        alt Not approved and iter < 5
            S->>D: database-fix-agent closes findings
            S->>C: Persist database-fix-log.md
        else Approved or max iterations
            note over S: break or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 5 - Backend tests (generate once, then per-layer loops)
    S->>BT: Generate unit, integration, functional
    BT-->>S: tests + coverage
    S->>C: Persist backend-test-report.md
    loop for each layer: unit -> integration -> functional (max 5 each)
        S->>BTV: Verify this layer's coverage/quality
        BTV-->>S: report + layer verdict
        S->>C: Persist backend-{layer}-test-verify-report.md
        alt Layer not satisfied and iter < 5
            S->>BT: backend-{layer}-test-fix-agent closes gaps
            BT-->>S: fix summary
            S->>C: Persist backend-{layer}-test-fix-log.md
        else Layer satisfied or max iterations
            note over S: next layer or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 6 - Frontend tests (generate once, then per-layer loops)
    S->>FT: Generate unit, integration, functional
    FT-->>S: tests + coverage
    S->>C: Persist frontend-test-report.md
    loop for each layer: unit -> integration -> functional (max 5 each)
        S->>FTV: Verify this layer's coverage/quality
        FTV-->>S: report + layer verdict
        S->>C: Persist frontend-{layer}-test-verify-report.md
        alt Layer not satisfied and iter < 5
            S->>FT: frontend-{layer}-test-fix-agent closes gaps
            FT-->>S: fix summary
            S->>C: Persist frontend-{layer}-test-fix-log.md
        else Layer satisfied or max iterations
            note over S: next layer or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 7 - System integration tests (collective, max 5)
    S->>SI: Generate full-stack tests (frontend + backend + PostgreSQL)
    SI-->>S: tests + run result
    S->>C: Persist system-integration-test-report.md
    loop until "System integration testing requirements satisfied"
        S->>SIV: Verify cross-tier journeys on real stack
        SIV-->>S: report + verdict
        S->>C: Persist system-integration-test-verify-report.md
        alt Not satisfied and iter < 5
            S->>SI: system-integration-test-fix-agent closes gaps
            SI-->>S: fix summary
            S->>C: Persist system-integration-test-fix-log.md
        else Satisfied or max iterations
            note over S: break or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 8 - Production (max 5)
    loop until "Final approval granted"
        S->>P: Final audit
        P-->>S: production report + verdict
        S->>C: Persist production-report.md
        alt Blocked and iter < 5
            S->>PF: Remediate findings
            PF-->>S: fix summary
            S->>C: Persist production-fix-log.md
        else Approved or max iterations
            note over S: break or blocked
        end
    end
    end

    S->>U: Summary + run guide
```

---

## 9. Shared-memory data flow

Only the Context Agent writes the store; every other agent reads trimmed handoffs.

```mermaid
flowchart LR
    subgraph store [".sunny/context/"]
        PC[project-context.md]
        AS[architecture-summary.md]
        AVR[architecture-verify-report.md]
        AFL[architecture-fix-log.md]
        BS[backend-summary.md]
        VR[verify-report.md]
        IRL[issue-resolution-log.md]
        DS[database-summary.md]
        DVR[database-verify-report.md]
        DFL[database-fix-log.md]
        BTR[backend-test-report.md]
        BTV6["backend-{unit,integration,functional}-<br/>test-verify-report.md (x3)"]
        BTF6["backend-{unit,integration,functional}-<br/>test-fix-log.md (x3)"]
        FTR[frontend-test-report.md]
        FTV6["frontend-{unit,integration,functional}-<br/>test-verify-report.md (x3)"]
        FTF6["frontend-{unit,integration,functional}-<br/>test-fix-log.md (x3)"]
        SIR[system-integration-test-report.md]
        SIVR[system-integration-test-verify-report.md]
        SIFL[system-integration-test-fix-log.md]
        PR[production-report.md]
        PFL[production-fix-log.md]
        ST[state.json]
    end

    Ctx[context-agent] -->|writes| store

    PC --> ARC[architecture-agent]
    AVR --> ARC
    AS --> ARCV[architecture-verify]
    PC --> ARCV
    AVR --> ARCF[architecture-fix]
    AS --> ARCF
    AFL --> ARCF

    PC --> BE[backend-agent]
    AS --> BE
    PC --> VER[verify-agent]
    BS --> VER
    AS --> VER
    VR --> FIX[issue-resolution]
    BS --> FIX
    IRL --> FIX

    BS --> DBA[database-agent]
    PC --> DBA
    DVR --> DBA
    DS --> DBV[database-verify]
    BS --> DBV
    DVR --> DBF[database-fix]
    DS --> DBF
    DFL --> DBF

    BS --> BTEST[backend test gen agents x3]
    PC --> BTEST
    BTV6 --> BTEST
    BTR --> BTVA["backend layer verify agents x3"]
    BS --> BTVA
    BTV6 --> BTFIX["backend layer fix agents x3"]
    BTR --> BTFIX
    BTF6 --> BTFIX
    PC --> FTEST[frontend test gen agents x3]
    FTV6 --> FTEST
    FTR --> FTVA["frontend layer verify agents x3"]
    FTV6 --> FTFIX["frontend layer fix agents x3"]
    FTR --> FTFIX
    FTF6 --> FTFIX

    PC --> SIT[system-integration-test-agent]
    AS --> SIT
    BS --> SIT
    DS --> SIT
    SIVR --> SIT
    SIR --> SIV2[system-integration-verify]
    PC --> SIV2
    SIVR --> SIF2[system-integration-fix]
    SIR --> SIF2
    SIFL --> SIF2

    BTV6 --> PROD[production-standards]
    FTV6 --> PROD
    SIVR --> PROD
    BS --> PROD
    PR --> PROD
    PR --> PFIX[production-fix]
    BS --> PFIX
    PC --> PFIX
    PFL --> PFIX
    ST -.drives loop decisions.-> Driver[Sunny driver]
```

---

## 10. Workflow state machine

`state.json.phase` transitions that the orchestrator follows.

```mermaid
stateDiagram-v2
    [*] --> intake
    intake --> architecture
    architecture --> architecture_verify
    architecture_verify --> architecture_fix: not approved
    architecture_fix --> architecture_verify: re-review
    architecture_verify --> backend: Architecture approved

    backend --> backend_verify
    backend_verify --> issue_resolution: issues found
    issue_resolution --> backend_verify: re-audit
    backend_verify --> database: Backend approved

    database --> database_verify
    database_verify --> database_fix: not approved
    database_fix --> database_verify: re-audit
    database_verify --> testing_backend: Database approved

    testing_backend --> testing_backend: layer not satisfied (fix and re-verify)
    testing_backend --> testing_frontend: all 3 backend layers satisfied

    testing_frontend --> testing_frontend: layer not satisfied (fix and re-verify)
    testing_frontend --> testing_system: all 3 frontend layers satisfied

    testing_system --> testing_system: not satisfied (fix and re-verify)
    testing_system --> production: System integration testing satisfied

    production --> production_fix: blocked (findings)
    production_fix --> production: re-audit
    production --> complete: Final approval granted
    complete --> [*]

    architecture_verify --> blocked: max iterations
    backend_verify --> blocked: max iterations
    database_verify --> blocked: max iterations
    testing_backend --> blocked: max iterations
    testing_frontend --> blocked: max iterations
    testing_system --> blocked: max iterations
    production --> blocked: max iterations
    blocked --> [*]: escalate to user
```

> Within `testing_backend` and `testing_frontend`, the layers are verified/fixed in order — unit → integration → functional — each with its own exit phrase and iteration counter. The side advances only when all three layers are satisfied.

---

## Legend

| Concept | Meaning |
|---------|---------|
| **Driver** | Main chat agent that follows the playbook and launches sub-agents via the Task tool |
| **Solid arrow** | Control flow / Task launch |
| **Dotted arrow** | Data flow (persist / handoff) |
| **readonly agent** | Audits and reports only; makes no code changes (architecture-verify, jhipster-verify, database-verify, the six per-layer test-verify agents, system-integration-test-verify, production-standards) |
| **Exit phrase** | Exact string in `state.json.lastVerdict` that breaks a loop |
| **Architecture exit** | `Architecture approved.` |
| **Backend code exit** | `No issues found. Backend approved.` |
| **Database exit** | `Database approved.` |
| **Backend test exits** | `Backend unit testing requirements satisfied.` / `Backend integration testing requirements satisfied.` / `Backend functional testing requirements satisfied.` |
| **Frontend test exits** | `Frontend unit testing requirements satisfied.` / `Frontend integration testing requirements satisfied.` / `Frontend functional testing requirements satisfied.` |
| **System integration exit** | `System integration testing requirements satisfied.` |
| **Production exit** | `Final approval granted. System is production-ready.` |
| **Max iterations** | Default 5 per loop; each loop has its own counter (`architectureVerifyIterations`; `backendVerifyIterations`; `databaseVerifyIterations`; the six `backend/frontend{Unit,Integration,Functional}TestVerifyIterations`; `systemIntegrationTestVerifyIterations`; `productionVerifyIterations`); exceeding it sets `phase = blocked` **before** launching the fix agent again |
