import pino from "pino";
import { config } from "../config.js";

export const logger = pino({
  level: config.LOG_LEVEL,
  base: { service: "specialty-lens-mcp", env: config.NODE_ENV },
  formatters: {
    level: (label) => ({ level: label }),
  },
  timestamp: pino.stdTimeFunctions.isoTime,
  redact: {
    paths: [
      "*.headers.authorization",
      "*.headers['x-fhir-access-token']",
      "*.fhir_token",
      "*.access_token",
    ],
    censor: "[redacted]",
  },
});
