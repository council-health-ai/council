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
 * Extract SHARP context from a request. Returns null if required headers are missing
 * — the middleware should already have rejected such requests with 403.
 *
 * patientId precedence: explicit X-Patient-ID header → JWT `patient` claim → null.
 */
export function extractSharpContext(req: Request): SharpContext | null {
  const fhirServerUrl = readHeader(req, SHARP_HEADERS.FHIR_SERVER_URL);
  const fhirAccessToken = readHeader(req, SHARP_HEADERS.FHIR_ACCESS_TOKEN);
  if (!fhirServerUrl || !fhirAccessToken) return null;

  const explicitPatientId = readHeader(req, SHARP_HEADERS.PATIENT_ID);
  let patientId = explicitPatientId ?? null;

  if (!patientId) {
    try {
      const decoded = decodeJwt(fhirAccessToken) as Record<string, unknown>;
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
    fhirAccessToken,
    patientId,
    conveningId,
    specialty,
    roundId: Number.isFinite(roundId) ? roundId : undefined,
  };
}
