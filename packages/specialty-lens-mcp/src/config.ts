import { z } from "zod";

const envSchema = z.object({
  PORT: z.coerce.number().default(7860),
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  LOG_LEVEL: z.enum(["fatal", "error", "warn", "info", "debug", "trace"]).default("info"),

  // Optional: only used when Vertex AI is NOT configured (local dev fallback).
  // In production we use Vertex via GCP_SA_KEY_JSON + GOOGLE_GENAI_USE_VERTEXAI.
  GEMINI_API_KEY: z.string().optional().default(""),
  GEMINI_MODEL: z.string().default("gemini-2.5-flash"),

  SUPABASE_URL: z.string().url().optional(),
  SUPABASE_SERVICE_ROLE_KEY: z.string().optional(),

  SENTRY_DSN: z.string().url().optional(),
  SENTRY_ENVIRONMENT: z.string().default("development"),

  SHARP_ENFORCE_403: z
    .union([z.boolean(), z.string()])
    .default(true)
    .transform((v) => (typeof v === "boolean" ? v : v.toLowerCase() === "true")),
});

export type Config = z.infer<typeof envSchema>;

export function loadConfig(): Config {
  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues.map((i) => `  ${i.path.join(".")}: ${i.message}`).join("\n");
    console.error(`Invalid environment:\n${issues}`);
    process.exit(1);
  }
  return parsed.data;
}

export const config: Config = loadConfig();
