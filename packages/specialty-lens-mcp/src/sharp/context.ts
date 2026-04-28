import { decodeJwt } from "jose";
import type { Request } from "express";
import { SHARP_HEADERS, COUNCIL_HEADERS } from "./constants.js";
import { logger } from "../observability/logger.js";

export interface SharpContext {
  fhirServerUrl: string;
  fhirAccessToken: string;
  patientId: string | null;
  /** Optional Council convening grouping headers (proposed RFC). */
  conveningId?: string;
  specialty?: string;
  roundId?: number;
}

/** Read a single header (case-insensitive) and return string or undefined. */
function readHeader(req: Request, name: string): string | undefined {
  const v = req.headers[name];
  if (Array.isArray(v)) return v[0];
  return v ?? undefined;
}

/**
 * Extract SHARP context from a request. Returns null only if the FHIR server URL
 * is completely missing — that's the one piece of context we genuinely cannot
 * proceed without (we wouldn't know where to send FHIR queries).
 *
 * The access token is allowed to be present-but-empty, matching the middleware's
 * lenient stance: Prompt Opinion's regression (observed 2026-04-26+) ships an
 * empty token in some workspace setups. When that happens we still attempt the
 * FHIR call — the server's anonymous-access path may serve, or the host's own
 * auth error surfaces with a more useful diagnostic than a 403 at our edge.
 *
 * patientId precedence: explicit X-Patient-ID header → JWT `patient` claim → null.
 */
export function extractSharpContext(req: Request): SharpContext | null {
  const fhirServerUrl = readHeader(req, SHARP_HEADERS.FHIR_SERVER_URL);
  const fhirAccessToken = readHeader(req, SHARP_HEADERS.FHIR_ACCESS_TOKEN);
  if (!fhirServerUrl) return null;
  // Token may be present-but-empty (PO regression). Normalise to "" rather than reject.
  const token = fhirAccessToken ?? "";

  const explicitPatientId = readHeader(req, SHARP_HEADERS.PATIENT_ID);
  let patientId = explicitPatientId ?? null;

  if (!patientId && token) {
    try {
      const decoded = decodeJwt(token) as Record<string, unknown>;
      const claim = decoded.patient ?? decoded["fhirUser"];
      if (typeof claim === "string") {
        patientId = claim.replace(/^Patient\//, "");
      }
    } catch (err) {
      logger.debug({ err }, "JWT decode failed (token may be opaque); patientId unresolved");
    }
  }

  const conveningId = readHeader(req, COUNCIL_HEADERS.CONVENING_ID);
  const specialty = readHeader(req, COUNCIL_HEADERS.SPECIALTY);
  const roundIdRaw = readHeader(req, COUNCIL_HEADERS.ROUND_ID);
  const roundId = roundIdRaw ? Number(roundIdRaw) : undefined;

  return {
    fhirServerUrl,
    fhirAccessToken: token,
    patientId,
    conveningId,
    specialty,
    roundId: Number.isFinite(roundId) ? roundId : undefined,
  };
}
