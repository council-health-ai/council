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

/** Call Gemini with an optional JSON-shaped response schema. Returns parsed JSON or text. */
export async function callGemini<T = unknown>(args: GeminiCallArgs): Promise<{ data: T; raw: string; latencyMs: number }> {
  const ai = getClient();
  const model = args.model ?? config.GEMINI_MODEL;
  const start = Date.now();

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
  logger.debug({ model, latencyMs, charCount: raw.length }, "Gemini response");

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
}

export { Type };
