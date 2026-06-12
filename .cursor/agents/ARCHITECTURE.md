# Sunny Orchestrator — Architecture & Workflow

Visual reference for the Sunny multi-agent system: component architecture, control flow, the verification/testing/production loops, shared-memory data flow, and state transitions.

> For prose explanation and run instructions, see [`README.md`](README.md).

---

## 1. System architecture (pipeline order)

The agents run as an **ordered pipeline**: generate the backend, verify and fix it, then generate and verify tests (backend, then frontend), then the final production audit. The Driver (main chat agent) launches each stage via the Task tool, and the Context Agent persists output between every stage. Read top to bottom — generation always precedes verification.

```mermaid
flowchart TB
    User([User]) --> Driver["Driver: main chat agent<br/>follows sunny-orchestrator.mdc"]

    subgraph pipeline [Execution Pipeline - top to bottom]
        direction TB
        S1["Stage 1 - Generate backend<br/>jhipster-backend-agent"]
        S2["Stage 2 - Verify backend (readonly)<br/>jhipster-verify-agent<br/>fix: issue-resolution-agent"]
        S3["Stage 3 - Backend tests<br/>unit + integration + functional<br/>verify: backend-test-verify-agent (readonly)<br/>fix: backend-test-fix-agent"]
        S4["Stage 4 - Frontend tests<br/>unit + integration + functional<br/>verify: frontend-test-verify-agent (readonly)<br/>fix: frontend-test-fix-agent"]
        S5["Stage 5 - Production (readonly audit)<br/>production-standards-agent<br/>fix: production-fix-agent"]
        S1 --> S2 --> S3 --> S4 --> S5
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
        DRV["Sunny / Driver<br/>• Orchestrates all 4 loops<br/>• Matches exact exit phrases<br/>• Enforces quality gates<br/>• Escalates when blocked"]
        CTX["context-agent<br/>• Sole writer of .sunny/context<br/>• Structured summaries + state.json<br/>• Trims handoffs to next agent<br/>• Tracks phase + iteration counters"]
    end

    subgraph s12 [Stage 1-2 - Backend build and verify]
        direction LR
        GEN["jhipster-backend-agent<br/>• Microservices: gateway + services + registry<br/>• PostgreSQL + Liquibase<br/>• JWT/OAuth2 + RBAC, Docker<br/>• No mock/fake data"]
        VER["jhipster-verify-agent - readonly<br/>• REST/OpenAPI/RFC7807 audit<br/>• Auth + vulnerability checks<br/>• Microservices + DB integrity<br/>• Exit: No issues found. Backend approved."]
        ISS["issue-resolution-agent<br/>• Fixes every verify finding<br/>• No control weakening<br/>• Rebuild + run tests<br/>• Returns for re-audit"]
        GEN --> VER
        VER -->|issues| ISS --> VER
    end

    subgraph s3 [Stage 3 - Backend testing]
        direction LR
        BU["backend-unit-test-agent<br/>• JUnit5 + Mockito<br/>• Services, mappers, validators<br/>• Fully mocked/isolated<br/>• Unit layer to 95%"]
        BI["backend-integration-test-agent<br/>• Testcontainers PostgreSQL<br/>• Repos, queries, migrations<br/>• Real DB, no H2<br/>• Integration layer to 95%"]
        BF["backend-functional-test-agent<br/>• REST Assured / MockMvc<br/>• Endpoints, auth, pagination<br/>• ProblemDetails + gateway E2E"]
        BTV["backend-test-verify-agent - readonly<br/>• Runs coverage tools<br/>• Checks 3 layers + edge cases<br/>• >=95% line + branch<br/>• Exit: Backend testing requirements satisfied."]
        BTF["backend-test-fix-agent<br/>• Closes verify-reported gaps<br/>• Adds/repairs tests<br/>• No gate lowering<br/>• Returns for re-verify"]
        BU --> BI --> BF --> BTV
        BTV -->|gaps| BTF --> BTV
    end

    subgraph s4 [Stage 4 - Frontend testing]
        direction LR
        FU["frontend-unit-test-agent<br/>• Vitest/Jest<br/>• Utils, hooks, stores<br/>• Isolated<br/>• Unit layer to 95%"]
        FI["frontend-integration-test-agent<br/>• Testing Library + MSW<br/>• Components, pages, routing<br/>• Events + loading/error states<br/>• Integration layer to 95%"]
        FF["frontend-functional-test-agent<br/>• Playwright E2E<br/>• Critical user journeys<br/>• Login, CRUD, navigation<br/>• Measured separately"]
        FTV["frontend-test-verify-agent - readonly<br/>• Runs coverage tools<br/>• Checks 3 layers + edge cases<br/>• >=95% line + branch<br/>• Exit: Frontend testing requirements satisfied."]
        FTF["frontend-test-fix-agent<br/>• Closes verify-reported gaps<br/>• Adds/repairs tests<br/>• No threshold lowering<br/>• Returns for re-verify"]
        FU --> FI --> FF --> FTV
        FTV -->|gaps| FTF --> FTV
    end

    subgraph s5 [Stage 5 - Production]
        direction LR
        PS["production-standards-agent - readonly<br/>• Security + readiness audit<br/>• Industry standards + performance<br/>• Requires prior approved verdicts<br/>• Exit: Final approval granted. System is production-ready."]
        PF["production-fix-agent<br/>• Remediates PR findings<br/>• No control weakening<br/>• Rebuild + run tests<br/>• Returns for re-audit"]
        PS -->|blocked| PF --> PS
    end

    orch --> s12 --> s3 --> s4 --> s5
```

---

## 2. End-to-end workflow (control flow)

The strict call order with all loops and their exact exit phrases.

```mermaid
flowchart TD
    Start([Frontend Input]) --> Intake["Intake<br/>context-agent creates<br/>project-context.md + state.json"]
    Intake --> Gen[jhipster-backend-agent]
    Gen --> P1["context-agent<br/>backend-summary.md"]

    P1 --> Verify[jhipster-verify-agent]
    Verify --> P2["context-agent<br/>verify-report.md"]
    P2 --> Approved{"lastVerdict ==<br/>'No issues found.<br/>Backend approved.'?"}
    Approved -->|No| CapB{"backendVerifyIterations<br/>>= 5?"}
    CapB -->|No| Fix[issue-resolution-agent] --> P3["context-agent<br/>issue-resolution-log.md"] --> Verify
    CapB -->|Yes| Blocked["phase = blocked<br/>escalate to user"]

    Approved -->|Yes| BGen["backend test generation<br/>unit -> integration -> functional"]
    BGen --> P4["context-agent<br/>backend-test-report.md"]
    P4 --> BVer[backend-test-verify-agent]
    BVer --> P5["context-agent<br/>backend-test-verify-report.md"]
    P5 --> BSat{"lastVerdict ==<br/>'Backend testing<br/>requirements satisfied.'?"}
    BSat -->|No| CapBT{"backendTestVerifyIterations<br/>>= 5?"}
    CapBT -->|No| BFix[backend-test-fix-agent] --> P6["context-agent<br/>backend-test-fix-log.md"] --> BVer
    CapBT -->|Yes| Blocked

    BSat -->|Yes| FGen["frontend test generation<br/>unit -> integration -> functional"]
    FGen --> P7["context-agent<br/>frontend-test-report.md"]
    P7 --> FVer[frontend-test-verify-agent]
    FVer --> P8["context-agent<br/>frontend-test-verify-report.md"]
    P8 --> FSat{"lastVerdict ==<br/>'Frontend testing<br/>requirements satisfied.'?"}
    FSat -->|No| CapFT{"frontendTestVerifyIterations<br/>>= 5?"}
    CapFT -->|No| FFix[frontend-test-fix-agent] --> P9["context-agent<br/>frontend-test-fix-log.md"] --> FVer
    CapFT -->|Yes| Blocked

    FSat -->|Yes| Prod[production-standards-agent]
    Prod --> P10["context-agent<br/>production-report.md"]
    P10 --> PSat{"lastVerdict ==<br/>'Final approval granted.<br/>System is production-ready.'?"}
    PSat -->|No| CapP{"productionVerifyIterations<br/>>= 5?"}
    CapP -->|No| PFix[production-fix-agent] --> P11["context-agent<br/>production-fix-log.md"] --> Prod
    CapP -->|Yes| Blocked
    PSat -->|Yes| Final(["Final Approval<br/>System is production-ready."])
```

---

## 3. Backend code verification loop (detail)

```mermaid
flowchart LR
    A[jhipster-verify-agent] --> B["context-agent<br/>verify-report.md"]
    B --> C{Issues?}
    C -->|"No issues found.<br/>Backend approved."| Exit([Exit to Backend tests])
    C -->|Issues found| D{backendVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[issue-resolution-agent]
    E --> F["context-agent<br/>issue-resolution-log.md"]
    F --> A
```

## 4. Backend testing loop (detail)

Three generation agents run once in order, then verify <-> fix until satisfied.

```mermaid
flowchart LR
    G1[backend-unit-test-agent] --> G2[backend-integration-test-agent] --> G3[backend-functional-test-agent]
    G3 --> P["context-agent<br/>backend-test-report.md"]
    P --> A[backend-test-verify-agent]
    A --> B["context-agent<br/>backend-test-verify-report.md"]
    B --> C{"lastVerdict ==<br/>'Backend testing<br/>requirements satisfied.'?"}
    C -->|Yes| Exit([Exit to Frontend tests])
    C -->|No| D{backendTestVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[backend-test-fix-agent]
    E --> F["context-agent<br/>backend-test-fix-log.md"]
    F --> A
```

## 5. Frontend testing loop (detail)

```mermaid
flowchart LR
    G1[frontend-unit-test-agent] --> G2[frontend-integration-test-agent] --> G3[frontend-functional-test-agent]
    G3 --> P["context-agent<br/>frontend-test-report.md"]
    P --> A[frontend-test-verify-agent]
    A --> B["context-agent<br/>frontend-test-verify-report.md"]
    B --> C{"lastVerdict ==<br/>'Frontend testing<br/>requirements satisfied.'?"}
    C -->|Yes| Exit([Exit to Production])
    C -->|No| D{frontendTestVerifyIterations<br/>>= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[frontend-test-fix-agent]
    E --> F["context-agent<br/>frontend-test-fix-log.md"]
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

## 7. Phase sequence (who talks to whom, when)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant S as Sunny (driver)
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
    S->>C: Intake (project-context.md, state.json)

    rect rgb(120,120,120)
    note right of S: Stage 1-2 - Generate and verify backend
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
    note right of S: Stage 3 - Backend tests (max 5)
    S->>BT: unit, then integration, then functional
    BT-->>S: tests + coverage
    S->>C: Persist backend-test-report.md
    loop until "Backend testing requirements satisfied"
        S->>BTV: Verify backend coverage and layers
        BTV-->>S: report + verdict
        S->>C: Persist backend-test-verify-report.md
        alt Not satisfied and iter < 5
            S->>BT: backend-test-fix-agent closes gaps
            BT-->>S: fix summary
            S->>C: Persist backend-test-fix-log.md
        else Satisfied or max iterations
            note over S: break or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 4 - Frontend tests (max 5)
    S->>FT: unit, then integration, then functional
    FT-->>S: tests + coverage
    S->>C: Persist frontend-test-report.md
    loop until "Frontend testing requirements satisfied"
        S->>FTV: Verify frontend coverage and layers
        FTV-->>S: report + verdict
        S->>C: Persist frontend-test-verify-report.md
        alt Not satisfied and iter < 5
            S->>FT: frontend-test-fix-agent closes gaps
            FT-->>S: fix summary
            S->>C: Persist frontend-test-fix-log.md
        else Satisfied or max iterations
            note over S: break or blocked
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Stage 5 - Production (max 5)
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

## 8. Shared-memory data flow

Only the Context Agent writes the store; every other agent reads trimmed handoffs.

```mermaid
flowchart LR
    subgraph store [".sunny/context/"]
        PC[project-context.md]
        BS[backend-summary.md]
        VR[verify-report.md]
        IRL[issue-resolution-log.md]
        BTR[backend-test-report.md]
        BTVR[backend-test-verify-report.md]
        BTFL[backend-test-fix-log.md]
        FTR[frontend-test-report.md]
        FTVR[frontend-test-verify-report.md]
        FTFL[frontend-test-fix-log.md]
        PR[production-report.md]
        PFL[production-fix-log.md]
        ST[state.json]
    end

    Ctx[context-agent] -->|writes| store

    PC --> BE[backend-agent]
    PC --> VER[verify-agent]
    BS --> VER
    VR --> FIX[issue-resolution]
    BS --> FIX
    IRL --> FIX
    BS --> BTEST[backend test agents]
    PC --> BTEST
    BTVR --> BTEST
    BTR --> BTV[backend-test-verify]
    BS --> BTV
    BTVR --> BTFIX[backend-test-fix]
    BTR --> BTFIX
    BTFL --> BTFIX
    PC --> FTEST[frontend test agents]
    FTVR --> FTEST
    FTR --> FTV[frontend-test-verify]
    FTVR --> FTFIX[frontend-test-fix]
    FTR --> FTFIX
    FTFL --> FTFIX
    BTVR --> PROD[production-standards]
    FTVR --> PROD
    BS --> PROD
    PR --> PROD
    PR --> PFIX[production-fix]
    BS --> PFIX
    PC --> PFIX
    PFL --> PFIX
    ST -.drives loop decisions.-> Driver[Sunny driver]
```

---

## 9. Workflow state machine

`state.json.phase` transitions that the orchestrator follows.

```mermaid
stateDiagram-v2
    [*] --> intake
    intake --> backend
    backend --> backend_verify
    backend_verify --> issue_resolution: issues found
    issue_resolution --> backend_verify: re-audit
    backend_verify --> testing_backend: Backend approved

    testing_backend --> testing_backend: backend tests not satisfied (fix and re-verify)
    testing_backend --> testing_frontend: Backend tests satisfied

    testing_frontend --> testing_frontend: frontend tests not satisfied (fix and re-verify)
    testing_frontend --> production: Frontend tests satisfied

    production --> production_fix: blocked (findings)
    production_fix --> production: re-audit
    production --> complete: Final approval granted
    complete --> [*]

    backend_verify --> blocked: max iterations
    testing_backend --> blocked: max iterations
    testing_frontend --> blocked: max iterations
    production --> blocked: max iterations
    blocked --> [*]: escalate to user
```

---

## Legend

| Concept | Meaning |
|---------|---------|
| **Driver** | Main chat agent that follows the playbook and launches sub-agents via the Task tool |
| **Solid arrow** | Control flow / Task launch |
| **Dotted arrow** | Data flow (persist / handoff) |
| **readonly agent** | Audits and reports only; makes no code changes (jhipster-verify, backend/frontend-test-verify, production) |
| **Exit phrase** | Exact string in `state.json.lastVerdict` that breaks a loop |
| **Backend code exit** | `No issues found. Backend approved.` |
| **Backend tests exit** | `Backend testing requirements satisfied.` |
| **Frontend tests exit** | `Frontend testing requirements satisfied.` |
| **Production exit** | `Final approval granted. System is production-ready.` |
| **Max iterations** | Default 5 per loop (`backendVerifyIterations` / `backendTestVerifyIterations` / `frontendTestVerifyIterations` / `productionVerifyIterations`); exceeding it sets `phase = blocked` **before** launching the fix agent again |
