-- The Council — relax overly tight audit constraints discovered during live testing.
--
-- The original schema's role check used 'endocrine'/'pediatrics' but the code uses
-- the canonical specialty names 'endocrinology'/'developmental_pediatrics'. Result:
-- every agent_messages insert from those two specialties was silently rejected,
-- masked by the audit module's try/except, leaving the audit log half-empty.
--
-- We drop the role check constraint entirely. The Specialty literal in
-- council_shared.models is the source of truth; SQL-level enforcement adds
-- maintenance friction without value for this demo.

alter table public.agent_messages
    drop constraint if exists agent_messages_role_check;
