/**
 * SHARP middleware enforcement tests.
 *
 * The 403 enforcement is The Council's single most-pointed-at SHARP-spec correctness
 * differentiator vs the three reference impls. These tests lock its behavior in.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import express from "express";
import request from "supertest";

// Set required env vars BEFORE importing modules that load config.
process.env.GEMINI_API_KEY = process.env.GEMINI_API_KEY ?? "test-fake-key-not-used-in-this-suite";

const { sharpEnforcement } = await import("../src/sharp/middleware.js");
const { SHARP_HEADERS } = await import("../src/sharp/constants.js");

function buildApp() {
  const app = express();
  app.use(express.json());
  app.post("/mcp", sharpEnforcement(), (req, res) => {
    res.json({ ok: true, body: req.body });
  });
  return app;
}

describe("SHARP middleware — 403 enforcement", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("passes initialize WITHOUT FHIR context (capability negotiation does not require headers)", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .send({ jsonrpc: "2.0", id: 1, method: "initialize", params: {} });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
  });

  it("passes tools/list WITHOUT FHIR context", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .send({ jsonrpc: "2.0", id: 2, method: "tools/list" });
    expect(res.status).toBe(200);
  });

  it("REJECTS tools/call without FHIR context — returns HTTP 403 (not 200 with JSON-RPC error)", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .send({
        jsonrpc: "2.0",
        id: 42,
        method: "tools/call",
        params: { name: "get_cardiology_perspective", arguments: { patient_id: "p1" } },
      });
    expect(res.status).toBe(403);
    expect(res.body.error.code).toBe(403);
    expect(res.body.error.data.reason).toBe("fhir_context_required");
    expect(res.body.error.data.spec).toContain("sharponmcp.com");
    expect(res.body.id).toBe(42);
  });

  it("REJECTS tools/call when only FHIR URL is present (token missing)", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .set(SHARP_HEADERS.FHIR_SERVER_URL, "https://example.org/fhir")
      .send({ jsonrpc: "2.0", id: 1, method: "tools/call", params: {} });
    expect(res.status).toBe(403);
    expect(res.body.error.data.received_headers["x-fhir-access-token"]).toBe("missing");
  });

  it("REJECTS tools/call when only token is present (URL missing)", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .set(SHARP_HEADERS.FHIR_ACCESS_TOKEN, "Bearer xyz")
      .send({ jsonrpc: "2.0", id: 1, method: "tools/call", params: {} });
    expect(res.status).toBe(403);
    expect(res.body.error.data.received_headers["x-fhir-server-url"]).toBe("missing");
  });

  it("ACCEPTS tools/call with both URL and token", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .set(SHARP_HEADERS.FHIR_SERVER_URL, "https://example.org/fhir")
      .set(SHARP_HEADERS.FHIR_ACCESS_TOKEN, "Bearer xyz")
      .send({ jsonrpc: "2.0", id: 1, method: "tools/call", params: {} });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
  });

  it("PASSES THROUGH tools/call when token header is present-but-empty (Prompt Opinion regression workaround, Discord 2026-04-26)", async () => {
    // Multiple users hit this on 2026-04-26: PO platform forwards X-FHIR-Access-Token
    // as an empty string. We allow empty-string headers through so the downstream FHIR
    // call can surface the platform-level error instead of cold-blocking at our edge.
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .set(SHARP_HEADERS.FHIR_SERVER_URL, "https://example.org/fhir")
      .set(SHARP_HEADERS.FHIR_ACCESS_TOKEN, "")
      .send({ jsonrpc: "2.0", id: 7, method: "tools/call", params: {} });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
  });

  it("PASSES THROUGH tools/call when URL header is present-but-empty (symmetric)", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .set(SHARP_HEADERS.FHIR_SERVER_URL, "")
      .set(SHARP_HEADERS.FHIR_ACCESS_TOKEN, "Bearer xyz")
      .send({ jsonrpc: "2.0", id: 8, method: "tools/call", params: {} });
    expect(res.status).toBe(200);
    expect(res.body.ok).toBe(true);
  });

  it("preserves the JSON-RPC id in the 403 envelope", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .send({ jsonrpc: "2.0", id: "custom-id-123", method: "tools/call" });
    expect(res.body.id).toBe("custom-id-123");
  });

  it("returns null id when the request body has none", async () => {
    const app = buildApp();
    const res = await request(app)
      .post("/mcp")
      .send({ jsonrpc: "2.0", method: "tools/call" });
    expect(res.body.id).toBeNull();
  });
});

describe("SHARP_CAPABILITIES — capability advertisement", () => {
  it("advertises BOTH spec form (experimental.fhir_context_required) AND impl form (extensions[ai.promptopinion/fhir-context])", async () => {
    const { SHARP_CAPABILITIES } = await import("../src/sharp/constants.js");

    expect(SHARP_CAPABILITIES.experimental.fhir_context_required.value).toBe(true);
    expect(
      SHARP_CAPABILITIES.extensions["ai.promptopinion/fhir-context"]
    ).toBeDefined();
    expect(
      SHARP_CAPABILITIES.extensions["ai.promptopinion/fhir-context"].scopes.length
    ).toBeGreaterThanOrEqual(8);

    // patient/Patient.rs is the only required scope per Po reference impls
    const required = SHARP_CAPABILITIES.extensions["ai.promptopinion/fhir-context"].scopes.filter(
      (s) => s.required
    );
    expect(required).toHaveLength(1);
    expect(required[0]?.name).toBe("patient/Patient.rs");
  });

  it("advertises the Council convening-session extension (proposed RFC)", async () => {
    const { SHARP_CAPABILITIES } = await import("../src/sharp/constants.js");
    const convening = SHARP_CAPABILITIES.extensions["ai.council-health/convening-session"];
    expect(convening).toBeDefined();
    expect(convening.headers).toEqual(
      expect.arrayContaining([
        "x-council-convening-id",
        "x-council-specialty",
        "x-council-round-id",
      ])
    );
  });
});
