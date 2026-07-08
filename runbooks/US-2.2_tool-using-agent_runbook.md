# US 2.2 — Tool-Using Agent (Retrieve + Act) — Build Runbook

> **Project:** Clarvo · **Exam:** AIP-C01 (target Jul 16, 2026) · **US deadline:** Jul 7
> **Account:** `408897322877` · **Primary region:** `ap-southeast-1` · **Fallback:** `us-east-1`
> **Canonical bucket:** `aip-c01-bucket` · **Canonical KB:** `SI1PK19NAO` *(reconcile/retire `7SFJSQDMRI` before wiring the retrieve tool — see §1.4)*

---

## 0. Read this first — the architecture decision that changes the build

Your US 2.2 wording says *"A Bedrock Agent with Action Groups runs on AgentCore."* That sentence mixes two generations of the product, and the mismatch is itself exam-relevant:

- **Amazon Bedrock Agents Classic** (the Nov-2023 product with *Action Groups*, *orchestration prompt templates*, `bedrock-agent` / `bedrock-agent-runtime` APIs) is now in **maintenance mode**. It closes to **new customers on July 30, 2026**, and AWS explicitly redirects new builds to **Amazon Bedrock AgentCore**.
- **AgentCore** is the current, GA agentic platform: **Runtime, Memory, Gateway, Identity, Observability** (plus the GA **Managed Agent Harness**). It is framework-agnostic (Strands, LangGraph, CrewAI, LlamaIndex) and model-agnostic.

**Decision:** Build the agent on **AgentCore Runtime** with a **Strands** agent (model-driven ReAct), expose tools through **AgentCore Gateway as MCP**, and use **AgentCore Memory + Observability**. This satisfies every SMART criterion in the story and is the version the exam will test as "current."

### Concept mapping (keep this for Classic-phrased exam questions)

| Bedrock Agents Classic | AgentCore equivalent (what you build) |
|---|---|
| Agent + orchestration prompt | Strands agent (`Agent(...)`) on AgentCore Runtime |
| **Action Group** (Lambda + OpenAPI/function schema) | **Gateway target** (Lambda/OpenAPI/Smithy) exposed as **MCP tool** |
| KB association (`retrieveAndGenerate`) | **Gateway Connector target → Managed KB**, *or* a retrieve Lambda tool |
| Session state / memory | **AgentCore Memory** (short-term events + long-term strategies) |
| Agent trace | **AgentCore Observability** → CloudWatch GenAI observability (spans/traces) |
| `PrepareAgent` / alias | AgentCore Runtime **versions + endpoints** |

### Target architecture (Clarvo US 2.2)

```
 User task: "find the renewal date, then draft a reminder"
        │
        ▼
┌──────────────────────────────────────────────┐
│ AgentCore Runtime (microVM, session-isolated) │
│   Strands Agent  (ReAct: Reason→Act→Observe)  │
│   model = Intelligent Prompt Router ARN        │
│   ├─ AgentCore Memory (short + long term)      │
│   └─ MCP client ──────────────┐                │
└───────────────────────────────┼───────────────┘
                                 ▼
                    AgentCore Gateway (MCP server, OAuth inbound)
                    ├─ Target A: Connector → KB SI1PK19NAO   (RETRIEVE)
                    └─ Target B: Lambda clarvoDraftReminder  (ACT)
                                 │ IAM (SigV4) outbound
                                 ▼
                          Lambda / KB / DynamoDB
   observability: AgentCore → CloudWatch Transaction Search / GenAI dashboard
```

**Subtask → section map:** 2.6 → §2 · 2.1 → §3 · 2.4 → §4 · 2.9/2.16 → §5 · 2.3 → §6 · 2.2 spike → §7 · acceptance demo → §8 · error→fix → §9 · exam cards → §10.

---

## 1. Prerequisites & environment (do once)

### 1.1 Tooling
```bash
# Mac (BSD) — you're on zsh; keep BSD date in mind for any timestamps
python3 -m venv ~/clarvo/labs/us2_2/.venv && source ~/clarvo/labs/us2_2/.venv/bin/activate
pip install --upgrade \
  bedrock-agentcore \
  bedrock-agentcore-starter-toolkit \
  strands-agents strands-agents-tools \
  boto3
# CLI check
agentcore --version          # from bedrock-agentcore-starter-toolkit
aws sts get-caller-identity --profile ai_developer_jmr
```

### 1.2 Region + model access
- Confirm **AgentCore is enabled in `ap-southeast-1`**. AgentCore GA has been rolling region-by-region; if a capability (e.g. a specific built-in tool) isn't live in `ap-southeast-1` yet, build in **`us-east-1`** (your documented fallback) and note it in the runbook. Check the AgentCore **release notes** page for the current region matrix before you start.
- In **Bedrock → Model access**, ensure the models you'll route between are enabled (Claude family + Nova family recommended — see §5).

### 1.3 Profiles / assumed role
Use your existing chain: base `ai_dev_base` → assume `ai_developer_jmr` (role `ai_dev_user_role`). All CLI/boto3 below assume `--profile ai_developer_jmr` or `AWS_PROFILE=ai_developer_jmr`.

### 1.4 ⚠️ Reconcile the KB *before* wiring the retrieve tool
You have two KB IDs from rebuild churn: `SI1PK19NAO` (canonical) and `7SFJSQDMRI`. The retrieve tool must point at exactly one, or your ReAct trace will be non-deterministic across rebuilds.
```bash
# Inspect both, pick the one backed by the current OpenSearch collection + latest ingestion
aws bedrock-agent get-knowledge-base --knowledge-base-id SI1PK19NAO --profile ai_developer_jmr
aws bedrock-agent get-knowledge-base --knowledge-base-id 7SFJSQDMRI --profile ai_developer_jmr
aws bedrock-agent list-data-sources --knowledge-base-id SI1PK19NAO --profile ai_developer_jmr
# Confirm SI1PK19NAO is canonical, then delete the orphan (record in ClickUp first)
aws bedrock-agent delete-knowledge-base --knowledge-base-id 7SFJSQDMRI --profile ai_developer_jmr
```
> Ties directly to your "consolidate resource naming early" learning — same failure class as the `clarvo-ingest-*` vs `aip-c01-bucket` sprawl.

---

## 2. Subtask 2.6 — MCP tool server (Lambda tools + Gateway)

Build the tools **before** the agent. Two tools cover the 2-step task: **RETRIEVE** (KB) and **ACT** (draft reminder). Gateway "MCPfies" them behind one OAuth-protected MCP endpoint.

### 2.1 The ACT tool — `clarvoDraftReminder` Lambda

**Important schema quirk:** a Gateway-invoked Lambda does **not** receive a normal API event. Gateway passes the tool's input properties directly as the `event`, and puts the tool name in `context.client_context.custom['bedrockAgentCoreToolName']` (prefixed with the target name + `___`). You must strip the prefix.

`app.py`:
```python
import json, datetime

def lambda_handler(event, context):
    # Gateway passes inputSchema properties directly as the event
    delimiter = "___"
    raw = context.client_context.custom["bedrockAgentCoreToolName"]
    tool = raw[raw.index(delimiter) + len(delimiter):] if delimiter in raw else raw

    if tool == "draft_reminder":
        renewal_date = event["renewal_date"]        # e.g. "2026-09-01"
        client_name  = event.get("client_name", "the client")
        days_before  = int(event.get("days_before", 30))
        rd = datetime.date.fromisoformat(renewal_date)
        remind_on = rd - datetime.timedelta(days=days_before)
        draft = (
            f"Subject: Upcoming renewal for {client_name} on {renewal_date}\n\n"
            f"Reminder scheduled for {remind_on.isoformat()} "
            f"({days_before} days prior). Please confirm renewal terms."
        )
        return {"draft": draft, "remind_on": remind_on.isoformat()}

    return {"error": f"unknown tool {tool}"}
```

Deploy (Console-first is fine, but here's the CLI so you can capture IaC immediately):
```bash
cd ~/clarvo/labs/us2_2/tools/draft_reminder
zip -j fn.zip app.py
aws lambda create-function \
  --function-name clarvoDraftReminder \
  --runtime python3.13 --handler app.lambda_handler \
  --timeout 15 --memory-size 256 \
  --role arn:aws:iam::408897322877:role/clarvoToolLambdaRole \
  --zip-file fileb://fn.zip \
  --region ap-southeast-1 --profile ai_developer_jmr
```

### 2.2 The RETRIEVE tool — two options (pick the "least code" one)

**Option A (recommended, least code — your weak-spot pattern):** use the **Gateway Connector target for Managed Knowledge Bases**. No retrieval Lambda at all — Gateway exposes the KB as an MCP tool natively. This is the answer to any "most efficient / least dev" exam framing.

**Option B (more control):** a thin Lambda that calls `bedrock-agent-runtime` `retrieve` against `SI1PK19NAO`. Use only if you need custom filtering/formatting before the model sees results.

Option B `retrieve.py`:
```python
import boto3
rt = boto3.client("bedrock-agent-runtime")
KB_ID = "SI1PK19NAO"

def lambda_handler(event, context):
    q = event["query"]
    r = rt.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": q},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 4}},
    )
    hits = [{"text": h["content"]["text"], "score": h.get("score")}
            for h in r["retrievalResults"]]
    return {"results": hits}
```

### 2.3 Create the Gateway + attach targets

Inbound auth is **OAuth/JWT** (MCP requires it). The starter toolkit spins up a Cognito authorizer for you.

```python
import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

gwc = GatewayClient(region_name="ap-southeast-1")

# Creates a Gateway + Cognito JWT inbound authorizer (least code)
gateway = gwc.create_mcp_gateway(name="clarvo-tools-gw")

# Target B: the ACT Lambda (explicit tool schema)
gwc.create_mcp_gateway_target(
    gateway=gateway, name="clarvoDraftReminder", target_type="lambda",
    target_payload={
        "lambdaArn": "arn:aws:lambda:ap-southeast-1:408897322877:function:clarvoDraftReminder",
        "toolSchema": {"inlinePayload": [{
            "name": "draft_reminder",
            "description": "Draft a renewal reminder email given a renewal_date (ISO) and client_name.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "renewal_date": {"type": "string", "description": "ISO date e.g. 2026-09-01"},
                    "client_name":  {"type": "string"},
                    "days_before":  {"type": "integer", "description": "lead time in days"}
                },
                "required": ["renewal_date"]
            }
        }]}
    },
    credentials=None  # defaults to GATEWAY_IAM_ROLE
)
```

Target A (Connector → Managed KB) via the control-plane client:
```python
ac = boto3.client("bedrock-agentcore-control", region_name="ap-southeast-1")
# Use the "connector" target type pointing at KB SI1PK19NAO.
# (Console path: Gateway → Add target → "Amazon Bedrock Managed Knowledge Bases")
```
> Gateway also gives you **semantic tool selection** for free (an internal `x_amz_bedrock_agentcore_search` tool). With only 2 tools it's noise, but mention it in the runbook — it's the exam answer for "hundreds of tools, minimize prompt size / latency."

### 2.4 Outbound auth
Lambda + Smithy targets use **IAM (GATEWAY_IAM_ROLE / SigV4)** outbound — the Gateway's execution role must have `lambda:InvokeFunction` on the tool functions. (ALB/EC2-fronted MCP servers can't use SigV4 — they'd need OAuth/API-key. Not your case.)

### 2.5 Terraform / CDK note
- **Terraform:** the `aws-samples/sample-strands-agent-with-agentcore` repo ships **reusable TF modules** for `runtime`, `gateway`, `auth`, `gateway-tools` (Lambda MCP tools) — clone it as your IaC starting point rather than writing from zero. Capture your Console build into that module shape (matches your "Console → capture IaC" flow).
- **CDK:** works too (there's a TS CDK path via the starter toolkit); use selectively per your stated preference.

---

## 3. Subtask 2.1 — Strands agent on AgentCore Runtime (+ Memory)

### 3.1 Scaffold the project
```bash
cd ~/clarvo/labs/us2_2
agentcore create --name clarvo-agent
cd clarvo-agent
# Add AgentCore Memory with the three long-term strategies
agentcore add memory --name ClarvoAgentMemory \
  --strategies SEMANTIC,SUMMARIZATION,USER_PREFERENCE
```

### 3.2 The agent (`agent.py`) — Strands + MCP tools + Memory

```python
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

app = BedrockAgentCoreApp()

GATEWAY_URL = "https://<your-gateway-id>.gateway.bedrock-agentcore.ap-southeast-1.amazonaws.com/mcp"

SYSTEM = """You are Clarvo's document-intelligence agent.
Complete multi-step tasks by REASONING then ACTING with tools.
Always retrieve facts from the knowledge base before drafting.
When done, return the drafted artifact. Do not loop more than needed."""

@app.entrypoint
def invoke(payload):
    user_task = payload["prompt"]
    token = payload["gateway_token"]          # OAuth token minted for the Gateway

    mcp = MCPClient(lambda: streamablehttp_client(
        GATEWAY_URL, headers={"Authorization": f"Bearer {token}"}))

    with mcp:
        tools = mcp.list_tools_sync()          # draft_reminder + KB retrieve tool
        agent = Agent(
            model="arn:aws:bedrock:ap-southeast-1:408897322877:prompt-router/<your-router-id>",
            system_prompt=SYSTEM,
            tools=tools,
        )
        result = agent(user_task)              # Strands runs the ReAct loop
        return {"result": str(result)}

if __name__ == "__main__":
    app.run()
```

**Why this satisfies the story:** Strands *is* a model-driven ReAct loop (Reason → Act → Observe) — the model decides which MCP tool to call and when to stop. No hand-written orchestration.

### 3.3 Wire Memory into the agent (short + long term)
```python
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

cfg = AgentCoreMemoryConfig(memory_id=MEM_ID, session_id=SESSION_ID, actor_id=ACTOR_ID)
session_manager = AgentCoreMemorySessionManager(agentcore_memory_config=cfg,
                                                region_name="ap-southeast-1")
agent = Agent(model=ROUTER_ARN, system_prompt=SYSTEM, tools=tools,
              session_manager=session_manager)
```
> This replaces the hand-rolled DynamoDB conversational memory from US 1.2 for the *agent* path. Keep the DynamoDB note in your runbook as the "build-it-yourself" comparison — AgentCore Memory is the "least code" answer.

### 3.4 Local test, then deploy
```bash
agentcore dev        # local browser UI: chat, token usage, tool calls, trace timeline
# when happy:
agentcore deploy     # builds container, provisions Runtime + Memory, returns endpoint
agentcore invoke '{"prompt": "Find the renewal date for Acme, then draft a reminder"}'
```

### 3.5 Observability (this is your "visible ReAct trace" for the SMART criterion)
1. **One-time:** enable **CloudWatch Transaction Search** (Console → CloudWatch → Application Signals/Transaction Search, or CLI). Required for spans/traces to appear.
2. Instrument with the **ADOT SDK** (Strands ships OpenTelemetry hooks; AgentCore auto-traces runtime sessions).
3. View in **CloudWatch → GenAI Observability**: trajectory diagram, per-span tool calls, token usage, error breakdown. This is the artifact you screenshot for the acceptance demo.

---

## 4. Subtask 2.4 — Safety rails (stopping conditions, timeouts, IAM boundaries)

This is the SMART criterion "*stopping conditions + timeouts prevent runaway loops.*" Layer defenses:

### 4.1 Stopping conditions (agent loop)
- **Strands:** cap reasoning iterations. Set a max-iterations / max-tool-calls guard and a clear "stop when you have the draft" instruction in the system prompt. Add a hard cap in code (e.g. wrap the loop and abort after N tool invocations).
- Return early on repeated identical tool calls (loop detection).

### 4.2 Timeouts (defense in depth)
| Layer | Control | Suggested value |
|---|---|---|
| Tool Lambda | function `Timeout` | 15 s (ACT), 30 s (retrieve) |
| Model call | Converse/inference client read timeout | 60 s |
| AgentCore session | runtime session TTL (long-running max is 8 h — set far lower here) | 5 min |
| Gateway target | Lambda invoke timeout alignment | ≥ Lambda timeout |
| Step Functions (if used, §6) | state `TimeoutSeconds` + `HeartbeatSeconds` | 120 s / 30 s |

### 4.3 IAM boundaries
- **Least-privilege Gateway role:** `lambda:InvokeFunction` scoped to the two tool ARNs only; `bedrock:Retrieve` scoped to KB `SI1PK19NAO` only.
- **Permissions boundary** on the agent/runtime execution role so it can never exceed the tool set (attach a boundary policy — ties to your DevSecOps instinct and is a common "which control prevents privilege escalation" exam answer).
- **Session isolation** is free: AgentCore Runtime gives each session its own microVM — call this out as the "blast-radius containment" control.
- **Inbound auth:** Gateway OAuth/JWT with an explicit `allowedClients` allow-list (Cognito). Never leave the MCP endpoint unauthenticated.

---

## 5. Subtasks 2.9 / 2.16 — Cost-smart cascading + model routing

### 5.1 Intelligent Prompt Routing (least-code cascade)
Bedrock **Intelligent Prompt Routing** = one serverless endpoint that predicts response quality per request and routes cheap-vs-capable **within one model family** (Anthropic *or* Nova *or* Meta — no cross-family mixing). Up to ~30% cost cut with no orchestration code.

```bash
# Create a configured router (two models, same family) — e.g. Claude Haiku vs Sonnet
# Then use the router ARN as the agent's model (see §3.2)
# arn:aws:bedrock:ap-southeast-1:408897322877:prompt-router/<router-id>
```
Set the **routing criteria threshold** (e.g. only escalate to the strong model if predicted quality is ≥10% better). Simple "find the date" turns → cheap model; the "draft a polished reminder" turn → strong model — automatically.

### 5.2 Planner/executor split (AgentCore harness)
The GA **Managed Harness** lets you **switch models mid-session without losing context** — plan with a cheap model, execute with a capable one. This is the more advanced cascade and a strong exam differentiator vs. "just use routing."

### 5.3 Other native cost levers (name them in the runbook)
- **Prompt caching** for the stable system prompt / tool schemas (skip recompute of repeated prefixes).
- **Semantic tool selection** in Gateway (fewer tools in prompt = fewer tokens + smaller model can reason).
- **AgentCore per-second consumption billing** (you pay for actual CPU/memory incl. I/O-wait-free) — the "why serverless agent runtime is cheaper than pre-provisioned compute" answer.

> **Exam framing:** "reduce cost without rewriting orchestration" → **Intelligent Prompt Routing**. "reduce cost by using a small model for routing/most turns" → **Nova/Haiku + escalation**. "reduce cost on repeated system prompts" → **prompt caching**.

---

## 6. Subtask 2.3 — ReAct via Step Functions (the deterministic / glass-box path)

Strands gives a *model-driven* loop. Step Functions gives an *explicit, auditable* ReAct loop with **native retries/timeouts** — build both so you can speak to the trade-off (this exact contrast shows up in "most reliable / least custom code" questions).

### 6.1 Two ways to do it
1. **Wrap the whole agent:** Step Functions **`InvokeHarness`** state (or a task state calling `invoke_agent_runtime`) drops your AgentCore agent into a larger pipeline — Step Functions owns retries, timeouts, catch/fallback, and gives a visual execution trace for free.
2. **Explicit ReAct state machine:** model the loop yourself for full determinism:

```
Start → RetrieveContext (Task: Gateway/KB retrieve)
      → ReasonPlan (Task: bedrock:invokeModel — decide next action)
      → Choice: need another tool?
           ├─ yes → CallTool (Task: Lambda) → back to ReasonPlan
           └─ no  → DraftReminder (Task: Lambda) → End
   Each Task: TimeoutSeconds + Retry (backoff) + Catch → FailGracefully
   A counter variable enforces max N loops (stopping condition).
```

### 6.2 Why this is the "safety rails, least code" answer
Retries, exponential backoff, per-state timeouts, heartbeat, and catch/fallback are **built into ASL** — you don't write loop/timeout code. The `Choice` + counter gives a hard stopping condition. Use the **Bedrock optimized integration** (`bedrock:invokeModel`) for the reason step. This is the version to reach for when a question stresses *reliability + auditability + minimal custom orchestration*.

> Reuse your US 1.3 muscle memory: you already ran a Step Functions **Map** state for the prompt-QA harness — same IaC patterns, new state graph.

---

## 7. Subtask 2.2 (roadmap spike) — Multi-agent: Strands + Agent Squad

Keep this a **timeboxed spike** (it's roadmap, not on the Jul 7 critical path). Two complementary patterns:

### 7.1 Strands multi-agent (agents-as-tools / graph)
A supervisor Strands agent delegates to specialist sub-agents (e.g. `RetrievalAgent`, `DraftingAgent`), each a `@tool`. Worthwhile only when specialists need *different models, tools, or permissions* — otherwise it's needless coordination overhead (say this; it's the exam-correct nuance).

### 7.2 Agent Squad (classifier-router)
```bash
pip install "agent-squad[aws]"
```
```python
from agent_squad.orchestrator import AgentSquad
from agent_squad.agents import BedrockLLMAgent, BedrockLLMAgentOptions
# Default classifier = BedrockClassifier (LLM intent routing)
orch = AgentSquad()
orch.add_agent(BedrockLLMAgent(BedrockLLMAgentOptions(
    name="Renewal Agent",
    description="Handles renewal dates, reminders, contract timelines.")))
orch.add_agent(BedrockLLMAgent(BedrockLLMAgentOptions(
    name="Summary Agent",
    description="Summarizes and extracts from documents.")))
resp = orch.route_request("Find Acme's renewal date and draft a reminder",
                          user_id="madmax", session_id="s1")
```
- **Classifier** has a *global* view of history; each **agent** sees only its own — the routing pattern to remember.
- Conversation storage: **DynamoDB** (pluggable).
- Note the naming history for the exam: the framework was **Multi-Agent Orchestrator → renamed Agent Squad**; the PyPI `multi-agent-orchestrator` package is **deprecated** in favor of `agent-squad`.

### 7.3 Spike deliverable
A one-pager: "when to stay single-agent (now) vs. go multi-agent (scale trigger)" + which orchestration (Strands supervisor vs. Agent Squad classifier vs. Step Functions) fits which trigger. Park in the Sprint 2 parent task `86d3f2fg5`.

---

## 8. Acceptance test — the 2-step task + visible trace

**Goal (SMART "Measurable"):** completes *"find the renewal date, then draft a reminder"* with a visible ReAct trace and no runaway loop.

1. Seed the KB (`SI1PK19NAO`) with a doc containing a known renewal date (e.g. "Acme MSA renews 2026-09-01").
2. Invoke:
   ```bash
   agentcore invoke '{"prompt":"Find the renewal date for Acme, then draft a reminder 30 days before."}'
   ```
3. **Expected trajectory (verify in CloudWatch GenAI Observability):**
   - Span 1: `retrieve` tool → returns "2026-09-01"
   - Span 2: model reasons → calls `draft_reminder(renewal_date="2026-09-01", client_name="Acme", days_before=30)`
   - Span 3: returns draft + `remind_on = 2026-08-02`
   - Loop count ≤ cap; total session < timeout.
4. **Pass criteria checklist:**
   - [ ] ≥1 Lambda tool called **via MCP** (Gateway)
   - [ ] KB retrieval occurred (Target A)
   - [ ] 2-step task completed end-to-end
   - [ ] ReAct spans/trace visible in CloudWatch
   - [ ] Stopping condition + timeouts demonstrably active (force a loop to prove the cap fires)
   - [ ] Gateway inbound OAuth enforced; Gateway role least-privilege

---

## 9. Error → Fix table

| Symptom | Likely cause | Fix |
|---|---|---|
| Lambda tool returns `unknown tool` | Didn't strip the `___` target-name prefix from `bedrockAgentCoreToolName` | Strip prefix via the `delimiter` split (see §2.1) |
| Gateway target stuck `CREATE_PENDING_AUTH` | 3LO OAuth target awaiting consent | Complete the auth-code flow, or provide a **static `mcpToolSchema`** to skip dynamic discovery |
| `AccessDenied` invoking tool | Gateway IAM role lacks `lambda:InvokeFunction` on the tool ARN | Add scoped invoke permission to the Gateway execution role |
| Agent can't reach MCP endpoint (401) | Missing/expired Cognito JWT / client not in `allowedClients` | Mint fresh token; add client ID to authorizer allow-list |
| No spans in CloudWatch | Transaction Search not enabled / ADOT not instrumented | Do the one-time Transaction Search setup **and** add ADOT SDK |
| Retrieval hits wrong/empty KB | Pointed at orphan `7SFJSQDMRI` | Repoint to `SI1PK19NAO`; delete orphan (§1.4) |
| Agent loops forever | No stopping condition | Add iteration cap + loop-detection + system-prompt stop rule (§4.1) |
| `ValidationException` on router | Mixed model families in one router | Router must be **two models, same family** (§5.1) |
| Capability missing in `ap-southeast-1` | Region hasn't received that AgentCore feature | Build in `us-east-1` fallback; record region caveat |
| Import `multi_agent_orchestrator` fails | Package renamed | Use `pip install "agent-squad[aws]"` (§7.2) |

---

## 10. Exam trigger → answer cards (AIP-C01)

Aligns with your trigger→answer study frame and your "most efficient / least code" weak spot.

| Trigger phrasing | Answer |
|---|---|
| "New agent, take actions, tools, managed, production" | **AgentCore** (not Bedrock Agents Classic — Classic closes to new customers Jul 30 2026) |
| "Expose existing Lambda/API as an agent tool, no rewrite, MCP" | **AgentCore Gateway target** (Lambda/OpenAPI/Smithy → MCP) |
| "Agent needs isolated sessions + persistent memory, no infra mgmt" | **AgentCore Runtime + Memory** |
| "See what the agent did step by step / trace" | **AgentCore Observability → CloudWatch GenAI observability** (enable Transaction Search) |
| "Prevent runaway agent loops" | **Stopping conditions + timeouts** (Strands cap / Step Functions Choice+counter+TimeoutSeconds) |
| "Reliable multi-step, native retries/timeouts, least custom code" | **Step Functions** (ASL Retry/Catch/Timeout; `InvokeHarness` to embed the agent) |
| "Cut cost, route cheap vs strong, no orchestration code" | **Intelligent Prompt Routing** (two models, same family) |
| "Cut cost on repeated system prompt/tool schema" | **Prompt caching** |
| "Hundreds of tools, minimize prompt size/latency" | **Gateway semantic tool selection** |
| "Route request to the right specialist agent" | **Agent Squad classifier** (global-history classifier, per-agent history) |
| "Plan with cheap model, execute with strong, same session" | **AgentCore Managed Harness** mid-session model switch |
| "Model-driven loop, minimal orchestration code" | **Strands** (ReAct by design) |

---

## 11. ClickUp update (close out US 2.2)

Under Sprint 2 parent `86d3f2fg5` (list `901615536720`), mark subtask status:
- 2.6 MCP tool server — **done** (Gateway + 2 targets)
- 2.1 Agent on AgentCore — **done** (Strands + Runtime + Memory)
- 2.4 Safety rails — **done** (stopping/timeouts/IAM boundary + session isolation)
- 2.9/2.16 Cost routing — **done** (Intelligent Prompt Routing; harness split noted)
- 2.3 ReAct via Step Functions — **done** (both wrap + explicit variants)
- 2.2 Multi-agent — **spike/roadmap** (Strands supervisor vs Agent Squad one-pager)

Attach the CloudWatch trajectory screenshot as the acceptance-criteria evidence ("visible ReAct trace").

---

### Capture-IaC-after checklist (your standard flow)
- [ ] Terraform: adopt `aws-samples/sample-strands-agent-with-agentcore` modules (`runtime`, `gateway`, `auth`, `gateway-tools`)
- [ ] Commit `agent.py`, tool Lambdas, Gateway target configs, Step Functions ASL to `~/clarvo/labs/us2_2` Git repo
- [ ] Add Console-UI + CLI + Terraform + CDK variants per component to the master runbook
- [ ] Append this error→fix table to the master runbook's error index
