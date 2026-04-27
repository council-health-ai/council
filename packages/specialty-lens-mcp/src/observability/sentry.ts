import * as Sentry from "@sentry/node";
import { config } from "../config.js";
import { logger } from "./logger.js";

export function initSentry(): void {
  if (!config.SENTRY_DSN) {
    logger.info("Sentry not configured (no DSN)");
    return;
  }
  Sentry.init({
    dsn: config.SENTRY_DSN,
    environment: config.SENTRY_ENVIRONMENT,
    tracesSampleRate: config.NODE_ENV === "production" ? 0.1 : 1.0,
    sendDefaultPii: false,
    beforeSend(event) {
      // Strip any leaked auth tokens defensively
      if (event.request?.headers) {
        delete event.request.headers["authorization"];
        delete event.request.headers["x-fhir-access-token"];
      }
      return event;
    },
  });
  logger.info({ environment: config.SENTRY_ENVIRONMENT }, "Sentry initialized");
}

export { Sentry };
