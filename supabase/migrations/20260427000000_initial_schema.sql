-- The Council — initial schema
-- Audit trail + A2A message log + MCP tool-call observability for live demo rendering.
-- Mandel/MedLog hook: every reasoning step is queryable; audit_events is published via Realtime
-- so the demo can subscribe and stream events live as the Council deliberates.

-- ─── convening_sessions ─────────────────────────────────────────────────
-- One row per Council convening. Created when General Chat invokes the Convener.

create table public.convening_sessions (
    id              uuid        primary key default gen_random_uuid(),
    a2a_context_id  text        not null unique,
    workspace_id    text        not null,
    patient_id      text        not null,
    started_at      timestamptz not null default now(),
    ended_at        timestamptz,
    plan_artifact   jsonb,
    status          text        not null default 'active'
        check (status in ('active', 'completed', 'failed', 'timeout'))
);

create index convening_sessions_workspace_idx on public.convening_sessions (workspace_id);
create index convening_sessions_started_at_idx on public.convening_sessions (started_at desc);

comment on table public.convening_sessions is
    'One row per Council convening. a2a_context_id is the A2A v1 contextId shared across all peer messages in the session.';

-- ─── agent_messages ─────────────────────────────────────────────────────
-- Every A2A message in/out of the Council, per session, per round.

create table public.agent_messages (
    id            uuid        primary key default gen_random_uuid(),
    convening_id  uuid        not null references public.convening_sessions(id) on delete cascade,
    role          text        not null
        check (role in ('convener', 'cardiology', 'oncology', 'nephrology', 'endocrine',
                        'obstetrics', 'pediatrics', 'psychiatry', 'anesthesia', 'general-chat')),
    direction     text        not null check (direction in ('inbound', 'outbound')),
    round_id      int,
    a2a_task_id   text,
    a2a_message_id text,
    content       jsonb       not null,
    created_at    timestamptz not null default now()
);

create index agent_messages_convening_idx on public.agent_messages (convening_id, created_at);
create index agent_messages_round_idx     on public.agent_messages (convening_id, round_id);

comment on table public.agent_messages is
    'Every A2A message exchanged within a convening. direction is from THIS service''s perspective.';

-- ─── audit_events — the MedLog table ───────────────────────────────────
-- Mandel hook. Every meaningful reasoning step is logged here.
-- Published via Realtime so the demo audit panel can subscribe.

create table public.audit_events (
    id            uuid        primary key default gen_random_uuid(),
    convening_id  uuid        references public.convening_sessions(id) on delete cascade,
    actor         text        not null,
    action        text        not null
        check (action in (
            'session_started', 'session_ended',
            'message_received', 'message_emitted',
            'reasoning_started', 'reasoning_completed',
            'tool_called', 'tool_returned',
            'fhir_query', 'fhir_returned',
            'conflict_flagged', 'conflict_resolved',
            'plan_synthesized', 'guideline_referenced'
        )),
    payload       jsonb       not null default '{}',
    fhir_refs     jsonb,
    round_id      int,
    created_at    timestamptz not null default now()
);

create index audit_events_convening_idx on public.audit_events (convening_id, created_at);
create index audit_events_actor_idx     on public.audit_events (actor, created_at);

comment on table public.audit_events is
    'MedLog-style audit trail. Every reasoning step in a Council deliberation is logged with structured payload and FHIR refs.';

-- ─── mcp_tool_calls ─────────────────────────────────────────────────────
-- Observable MCP-server tool invocations.

create table public.mcp_tool_calls (
    id             uuid        primary key default gen_random_uuid(),
    convening_id   uuid        references public.convening_sessions(id) on delete set null,
    tool_name      text        not null,
    params         jsonb       not null,
    result         jsonb,
    status         text        not null default 'pending'
        check (status in ('pending', 'success', 'error')),
    error_message  text,
    latency_ms     int,
    created_at     timestamptz not null default now()
);

create index mcp_tool_calls_convening_idx on public.mcp_tool_calls (convening_id, created_at);
create index mcp_tool_calls_tool_idx      on public.mcp_tool_calls (tool_name, created_at);

comment on table public.mcp_tool_calls is
    'Observable MCP tool invocations from any agent. Useful for the demo trace panel.';

-- ─── Row Level Security ─────────────────────────────────────────────────
-- service_role bypasses RLS by default; we add policies for anon read-access
-- so a public demo viewer can subscribe to audit events without exposing service_role.

alter table public.convening_sessions enable row level security;
alter table public.agent_messages    enable row level security;
alter table public.audit_events      enable row level security;
alter table public.mcp_tool_calls    enable row level security;

create policy "anon read sessions" on public.convening_sessions
    for select to anon using (true);
create policy "anon read messages" on public.agent_messages
    for select to anon using (true);
create policy "anon read audit"    on public.audit_events
    for select to anon using (true);
create policy "anon read tools"    on public.mcp_tool_calls
    for select to anon using (true);

-- ─── Realtime ───────────────────────────────────────────────────────────
-- Add audit_events to the Realtime publication so the live demo panel
-- can subscribe via supabase-js .channel('audit').on('postgres_changes', ...).

alter publication supabase_realtime add table public.audit_events;
alter publication supabase_realtime add table public.mcp_tool_calls;
alter publication supabase_realtime add table public.agent_messages;
