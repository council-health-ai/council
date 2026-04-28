import { writeFileSync } from "node:fs";
import { GoogleGenAI, Type } from "@google/genai";
import { config } from "../config.js";
import { logger } from "../observability/logger.js";

let client: GoogleGenAI | null = null;

/**
 * Create the Gemini client. Prefer Vertex when the GCP service account is
 * available so calls draw from the project's $300 GCP trial billing rather
 * than the depleted AI-Studio prepayment pool. Falls back to AI Studio (API
 * key) only when Vertex isn't configured — useful for local dev without GCP.
 */
function getClient(): GoogleGenAI {
  if (client) return client;

  const useVertex = (process.env.GOOGLE_GENAI_USE_VERTEXAI ?? "").toLowerCase() === "true";
  const project = process.env.GOOGLE_CLOUD_PROJECT;
  const location = process.env.GOOGLE_CLOUD_LOCATION ?? "us-central1";
  const saJson = process.env.GCP_SA_KEY_JSON?.trim();

  if (useVertex && project && saJson) {
    // The Node Google Auth library reads GOOGLE_APPLICATION_CREDENTIALS from a
    // file path, not from an env-encoded JSON blob. HF Spaces only persists
    // env vars, so we materialize the JSON to /tmp on first call.
    const credPath = "/tmp/gcp-sa.json";
    try {
      writeFileSync(credPath, saJson, { mode: 0o600 });
      process.env.GOOGLE_APPLICATION_CREDENTIALS = credPath;
    } catch (err) {
      logger.error({ err }, "failed to materialize GCP SA key; falling back to AI Studio");
    }
    if (process.env.GOOGLE_APPLICATION_CREDENTIALS === credPath) {
      logger.info({ project, location }, "Gemini client: using Vertex AI");
      client = new GoogleGenAI({ vertexai: true, project, location });
      return client;
    }
  }

  logger.warn("Gemini client: falling back to AI Studio (no Vertex SA configured)");
  client = new GoogleGenAI({ apiKey: config.GEMINI_API_KEY });
  return client;
}

export interface GeminiCallArgs {
  systemInstruction: string;
  userPrompt: string;
  responseSchema?: object;
  model?: string;
  temperature?: number;
}

function isRateLimit(err: unknown): boolean {
  const message = (err instanceof Error ? err.message : String(err)).toLowerCase();
  return message.includes("429") || message.includes("resource_exhausted") || message.includes("rate limit");
}

const MAX_429_RETRIES = 3;
const BACKOFF_BASE_MS = 4000;

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
  const ai = getClient();
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
