import { GoogleGenAI, Type } from "@google/genai";
import { config } from "../config.js";
import { logger } from "../observability/logger.js";

let client: GoogleGenAI | null = null;

function getClient(): GoogleGenAI {
  if (client) return client;
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
