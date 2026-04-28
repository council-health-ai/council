import { writeFileSync } from "node:fs";
import { GoogleGenAI, Type } from "@google/genai";
import { config } from "../config.js";
import { logger } from "../observability/logger.js";

/**
 * Per-region Vertex client cache. Each lens specialty is routed to its own
 * Vertex region so the 8 lens calls don't fight over a single region's
 * Gemini RPM quota — same project, same trial billing, ~8× the burst headroom.
 *
 * AI Studio fallback (single client) when Vertex isn't configured.
 */
const clientByRegion = new Map<string, GoogleGenAI>();
let aiStudioClient: GoogleGenAI | null = null;

const REGION_BY_SPECIALTY: Record<string, string> = {
  cardiology:               "us-west1",
  oncology:                 "us-east4",
  nephrology:               "us-south1",
  endocrinology:            "europe-west1",
  obstetrics:               "europe-west4",
  developmental_pediatrics: "us-east5",      // asia-east1 had model availability issue
  psychiatry:               "asia-northeast1",
  anesthesia:               "asia-southeast1",
  // Concordance synthesis (Convener-side, not specialty-bound)
  concordance:              "us-central1",
};

let saMaterialized = false;
function materializeSAKey(): boolean {
  if (saMaterialized) return process.env.GOOGLE_APPLICATION_CREDENTIALS != null;
  const saJson = process.env.GCP_SA_KEY_JSON?.trim();
  if (!saJson) return false;
  const credPath = "/tmp/gcp-sa.json";
  try {
    writeFileSync(credPath, saJson, { mode: 0o600 });
    process.env.GOOGLE_APPLICATION_CREDENTIALS = credPath;
    saMaterialized = true;
    return true;
  } catch (err) {
    logger.error({ err }, "failed to materialize GCP SA key");
    return false;
  }
}

/**
 * Create or reuse a Vertex client for the given region. Falls back to AI
 * Studio if Vertex isn't configured.
 */
function getClient(region?: string): GoogleGenAI {
  const useVertex = (process.env.GOOGLE_GENAI_USE_VERTEXAI ?? "").toLowerCase() === "true";
  const project = process.env.GOOGLE_CLOUD_PROJECT;

  if (useVertex && project && materializeSAKey()) {
    const loc = region ?? process.env.GOOGLE_CLOUD_LOCATION ?? "us-central1";
    const cached = clientByRegion.get(loc);
    if (cached) return cached;
    logger.info({ project, location: loc }, "Gemini client: provisioning Vertex region");
    const c = new GoogleGenAI({ vertexai: true, project, location: loc });
    clientByRegion.set(loc, c);
    return c;
  }

  if (!aiStudioClient) {
    logger.warn("Gemini client: falling back to AI Studio (no Vertex SA configured)");
    aiStudioClient = new GoogleGenAI({ apiKey: config.GEMINI_API_KEY });
  }
  return aiStudioClient;
}

/** Resolve the right region for a given specialty. Specialties without a
 *  mapping (or `undefined`) get the default Vertex location. */
export function regionForSpecialty(specialty?: string): string | undefined {
  if (!specialty) return undefined;
  return REGION_BY_SPECIALTY[specialty];
}

export interface GeminiCallArgs {
  systemInstruction: string;
  userPrompt: string;
  responseSchema?: object;
  model?: string;
  temperature?: number;
  /** Vertex region override — let lenses route to their own region for
   *  independent quota. */
  region?: string;
}

function isRateLimit(err: unknown): boolean {
  const message = (err instanceof Error ? err.message : String(err)).toLowerCase();
  return message.includes("429") || message.includes("resource_exhausted") || message.includes("rate limit");
}

const MAX_429_RETRIES = 2;
const BACKOFF_BASE_MS = 1500;

async function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Call Gemini with an optional JSON-shaped response schema. Returns parsed JSON or text.
 *
 *  Retries up to 3 times on Vertex 429 with 4s/8s/16s backoff. On a trial-credit
 *  GCP project the rolling-minute quota gets hot if 8 specialty agents call in
 *  parallel and then the concordance brief lands within the same window —
 *  retrying transparently keeps the deliberation alive. */
export async function callGemini<T = unknown>(args: GeminiCallArgs): Promise<{ data: T; raw: string; latencyMs: number }> {
  const ai = getClient(args.region);
  const model = args.model ?? config.GEMINI_MODEL;
  const start = Date.now();

  let lastErr: unknown;
  for (let attempt = 0; attempt < MAX_429_RETRIES; attempt++) {
    try {
      const response = await ai.models.generateContent({
        model,
        contents: args.userPrompt,
        config: {
          systemInstruction: args.systemInstruction,
          temperature: args.temperature ?? 0.3,
          responseMimeType: args.responseSchema ? "application/json" : "text/plain",
          ...(args.responseSchema ? { responseJsonSchema: args.responseSchema } : {}),
        },
      });

      const latencyMs = Date.now() - start;
      const raw = response.text ?? "";
      logger.debug({ model, latencyMs, charCount: raw.length, attempt }, "Gemini response");

      if (args.responseSchema) {
        try {
          const data = JSON.parse(raw) as T;
          return { data, raw, latencyMs };
        } catch (err) {
          logger.error({ err, raw }, "Gemini returned invalid JSON despite schema");
          throw new Error(`Gemini JSON parse failed: ${(err as Error).message}`);
        }
      }
      return { data: raw as T, raw, latencyMs };
    } catch (err) {
      lastErr = err;
      if (!isRateLimit(err) || attempt === MAX_429_RETRIES - 1) throw err;
      const backoff = BACKOFF_BASE_MS * 2 ** attempt;
      logger.warn({ attempt: attempt + 1, backoff, err: (err as Error).message }, "Gemini 429; backing off");
      await sleep(backoff);
    }
  }
  throw lastErr;
}

export { Type };
