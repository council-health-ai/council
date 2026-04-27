import type { Request, Response, NextFunction } from "express";
import { SHARP_HEADERS } from "./constants.js";
import { config } from "../config.js";
import { logger } from "../observability/logger.js";

/**
 * SHARP 403 enforcement at request entry.
 *
 * The SHARP-on-MCP spec (https://sharponmcp.com/key-components.html) says servers
 * advertising `fhir_context_required` MUST return 403 when context headers are missing.
 * None of the three reference implementations (TypeScript, Python, .NET) in
 * `prompt-opinion/po-community-mcp` currently enforce this — they throw at tool-call time
 * via the JSON-RPC error envelope, which doesn't satisfy the spec wording.
 *
 * This middleware returns a real HTTP 403 for any `tools/call` request that arrives
 * with the required headers **completely missing**.
 *
 * **Important:** "completely missing" is intentional. We've observed agent hosts
 * forwarding `X-FHIR-Access-Token` as a present-but-empty header in some setups —
 * returning 403 on present-but-empty would block legitimate platform calls. Instead,
 * we let present-but-empty pass through and surface the resulting FHIR-server error,
 * which gives a more useful diagnostic ("the host sent an empty token") than a cold
 * 403 at our edge.
 */
export function sharpEnforcement() {
  return function enforce(req: Request, res: Response, next: NextFunction) {
    if (!config.SHARP_ENFORCE_403) return next();

    const body: unknown = req.body;
    if (!body || typeof body !== "object") return next();
    const method = (body as { method?: unknown }).method;
    const id = (body as { id?: unknown }).id ?? null;

    // Only enforce on actual tool invocations. Discovery / capability negotiation
    // does not require FHIR context — it advertises the requirement instead.
    if (method !== "tools/call") return next();

    const fhirUrlHeader = req.headers[SHARP_HEADERS.FHIR_SERVER_URL];
    const fhirTokenHeader = req.headers[SHARP_HEADERS.FHIR_ACCESS_TOKEN];

    // "Header present" — including empty-value present (Prompt Opinion regression workaround).
    // Strict 403 only when the header was completely absent from the request.
    const fhirUrlPresent = fhirUrlHeader !== undefined;
    const fhirTokenPresent = fhirTokenHeader !== undefined;

    if (fhirUrlPresent && fhirTokenPresent) {
      // Surface the empty-token case as a structured warning so the audit log can flag it.
      const fhirUrl = Array.isArray(fhirUrlHeader) ? fhirUrlHeader[0] : fhirUrlHeader;
      const fhirToken = Array.isArray(fhirTokenHeader) ? fhirTokenHeader[0] : fhirTokenHeader;
      if (!fhirUrl || !fhirToken) {
        logger.warn(
          {
            method,
            empty: { fhirUrl: !fhirUrl, fhirToken: !fhirToken },
            note: "FHIR header present but empty. Passing through; downstream FHIR call will surface the host-level error.",
          },
          "SHARP: tools/call with empty FHIR header"
        );
      }
      return next();
    }

    logger.warn(
      { method, missing: { fhirUrl: !fhirUrlPresent, fhirToken: !fhirTokenPresent } },
      "SHARP 403: tools/call without required FHIR context headers"
    );

    return res.status(403).json({
      jsonrpc: "2.0",
      id,
      error: {
        code: 403,
        message: "FHIR context required",
        data: {
          reason: "fhir_context_required",
          spec: "https://sharponmcp.com/key-components.html",
          required_headers: [
            "X-FHIR-Server-URL",
            "X-FHIR-Access-Token",
            "X-Patient-ID (optional; defaults to JWT patient claim)",
          ],
          received_headers: {
            "x-fhir-server-url": fhirUrlPresent ? "present" : "missing",
            "x-fhir-access-token": fhirTokenPresent ? "present" : "missing",
          },
        },
      },
    });
  };
}
