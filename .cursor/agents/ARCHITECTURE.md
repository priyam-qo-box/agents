# Sunny Orchestrator — Architecture & Workflow

Visual reference for the Sunny multi-agent system: component architecture, control flow, the two verification loops, shared-memory data flow, and state transitions.

> For prose explanation and run instructions, see [`README.md`](README.md).

---

## 1. System architecture (components)

How the orchestrator, the shared-memory store, and the specialized agents relate.

```mermaid
flowchart TB
    User([User]) -->|"Sunny, build backend for this frontend"| Driver

    subgraph control [Control Plane]
        Driver["Main Chat Agent<br/>(driver)"]
        Playbook["sunny-orchestrator.mdc<br/>(playbook / rule)"]
        SunnyAgent["sunny.md<br/>(orchestrator persona)"]
        Driver -.follows.-> Playbook
        Driver -.consults.-> SunnyAgent
    end

    subgraph memory [Shared Memory]
        Ctx["context-agent"]
        Store[(".sunny/context/<br/>files + state.json")]
        Ctx <-->|read / write| Store
    end

    subgraph workers [Specialized Agents]
        BE["jhipster-backend-agent<br/>(generate)"]
        VER["jhipster-verify-agent<br/>(audit, readonly)"]
        FIX["issue-resolution-agent<br/>(fix)"]
        TEST["testing-agent<br/>(tests)"]
        TVER["test-verify-agent<br/>(audit, readonly)"]
        PROD["production-standards-agent<br/>(audit, readonly)"]
    end

    Driver -->|Task launch| BE
    Driver -->|Task launch| VER
    Driver -->|Task launch| FIX
    Driver -->|Task launch| TEST
    Driver -->|Task launch| TVER
    Driver -->|Task launch| PROD
    Driver -->|persist after each step| Ctx

    BE -.output.-> Ctx
    VER -.output.-> Ctx
    FIX -.output.-> Ctx
    TEST -.output.-> Ctx
    TVER -.output.-> Ctx
    PROD -.output.-> Ctx
    Ctx -.trimmed handoff.-> workers
```

---

## 2. End-to-end workflow (control flow)

The strict call order with both loops and their exact exit phrases.

```mermaid
flowchart TD
    Start([Frontend Input]) --> Intake["Intake<br/>context-agent creates<br/>project-context.md + state.json"]
    Intake --> Gen[jhipster-backend-agent]
    Gen --> P1["context-agent<br/>persist backend-summary.md"]

    P1 --> Verify[jhipster-verify-agent]
    Verify --> P2["context-agent<br/>persist verify-report.md"]
    P2 --> Approved{"Verdict ==<br/>'No issues found.<br/>Backend approved.'?"}

    Approved -->|No| CapBackend{"backendVerifyIterations<br/>>= 5?"}
    CapBackend -->|No| Fix[issue-resolution-agent]
    Fix --> P3["context-agent<br/>persist issue-resolution-log.md"]
    P3 --> Verify
    CapBackend -->|Yes| Blocked["phase = blocked<br/>escalate to user"]

    Approved -->|Yes| Test[testing-agent]
    Test --> P4["context-agent<br/>persist test-report.md"]
    P4 --> TVerify[test-verify-agent]
    TVerify --> P5["context-agent<br/>persist test-verify-report.md"]
    P5 --> Satisfied{"Verdict ==<br/>'Testing requirements<br/>satisfied.'?"}

    Satisfied -->|No| CapTest{"testVerifyIterations<br/>>= 5?"}
    CapTest -->|No| Test
    CapTest -->|Yes| Blocked

    Satisfied -->|Yes| Prod[production-standards-agent]
    Prod --> P6["context-agent<br/>persist production-report.md"]
    P6 --> Final([Final Approval])
```

---

## 3. Backend verification loop (detail)

```mermaid
flowchart LR
    A[jhipster-verify-agent] --> B["context-agent<br/>verify-report.md"]
    B --> C{Issues?}
    C -->|"No issues found.<br/>Backend approved."| Exit([Exit to Testing])
    C -->|Issues found| D{Iter >= 5?}
    D -->|Yes| Stop([Blocked - escalate])
    D -->|No| E[issue-resolution-agent]
    E --> F["context-agent<br/>issue-resolution-log.md"]
    F --> A
```

## 4. Testing loop (detail)

```mermaid
flowchart LR
    A[testing-agent] --> B["context-agent<br/>test-report.md"]
    B --> C[test-verify-agent]
    C --> D["context-agent<br/>test-verify-report.md"]
    D --> E{Coverage >= 95%?}
    E -->|"Testing requirements<br/>satisfied."| Exit([Exit to Production])
    E -->|No| F{Iter >= 5?}
    F -->|Yes| Stop([Blocked - escalate])
    F -->|No| A
```

---

## 5. Phase sequence (who talks to whom, when)

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant S as Sunny (driver)
    participant C as Context Agent
    participant B as Backend Agent
    participant V as Verify Agent
    participant I as Issue Resolution
    participant T as Testing Agent
    participant TV as Test Verify
    participant P as Production Standards

    U->>S: Frontend + requirements
    S->>C: Intake (project-context.md, state.json)

    rect rgb(120,120,120)
    note right of S: Phase 1 - Generation
    S->>B: Generate JHipster microservices
    B->>C: backend-summary.md
    end

    rect rgb(120,120,120)
    note right of S: Phase 2 - Verify loop (max 5)
    loop until "Backend approved"
        S->>V: Audit backend
        V->>C: verify-report.md
        alt Issues found
            S->>I: Fix findings
            I->>C: issue-resolution-log.md
        else Approved
            note over S: break
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Phase 3 - Test loop (max 5)
    S->>T: Generate tests
    T->>C: test-report.md
    loop until "Testing requirements satisfied"
        S->>TV: Verify coverage
        TV->>C: test-verify-report.md
        alt < 95%
            S->>T: Fill gaps
            T->>C: test-report.md
        else Satisfied
            note over S: break
        end
    end
    end

    rect rgb(120,120,120)
    note right of S: Phase 4 - Production
    S->>P: Final audit
    P->>C: production-report.md
    P->>S: Final approval granted
    end

    S->>U: Summary + run guide
```

---

## 6. Shared-memory data flow

Only the Context Agent writes the store; every other agent reads trimmed handoffs.

```mermaid
flowchart LR
    subgraph store [".sunny/context/"]
        PC[project-context.md]
        BS[backend-summary.md]
        VR[verify-report.md]
        IRL[issue-resolution-log.md]
        TR[test-report.md]
        TVR[test-verify-report.md]
        PR[production-report.md]
        ST[state.json]
    end

    Ctx[context-agent] -->|writes| store

    PC --> BE[backend-agent]
    PC --> VER[verify-agent]
    BS --> VER
    VR --> FIX[issue-resolution]
    BS --> FIX
    BS --> TEST[testing-agent]
    TR --> TVER[test-verify]
    TVR --> PROD[production-standards]
    BS --> PROD
    ST -.drives loop decisions.-> Driver[Sunny driver]
```

---

## 7. Workflow state machine

`state.json.phase` transitions that the orchestrator follows.

```mermaid
stateDiagram-v2
    [*] --> intake
    intake --> backend
    backend --> backend_verify
    backend_verify --> issue_resolution: issues found
    issue_resolution --> backend_verify: re-audit
    backend_verify --> testing: Backend approved
    testing --> test_verify
    test_verify --> testing: coverage < 95%
    test_verify --> production: Testing satisfied
    production --> complete: Final approval
    complete --> [*]

    backend_verify --> blocked: max iterations
    test_verify --> blocked: max iterations
    blocked --> [*]: escalate to user
```

---

## Legend

| Concept | Meaning |
|---------|---------|
| **Driver** | Main chat agent that follows the playbook and launches sub-agents via the Task tool |
| **Solid arrow** | Control flow / Task launch |
| **Dotted arrow** | Data flow (persist / handoff) |
| **readonly agent** | Audits and reports only; makes no code changes (verify, test-verify, production) |
| **Exit phrase** | Exact string the orchestrator matches to break a loop |
| **Max iterations** | Default 5 per loop; exceeding it sets `phase = blocked` |
