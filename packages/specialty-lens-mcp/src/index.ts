import express, { type Request, type Response } from "express";
import cors from "cors";
import pinoHttp from "pino-http";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { config } from "./config.js";
import { logger } from "./observability/logger.js";
import { initSentry, Sentry } from "./observability/sentry.js";
import { sharpEnforcement } from "./sharp/middleware.js";
import { SHARP_CAPABILITIES } from "./sharp/constants.js";
import { registerTools } from "./tools/index.js";

initSentry();

const app = express();

app.use(pinoHttp({ logger, autoLogging: { ignore: (req) => req.url === "/healthz" } }));
app.use(cors());
app.use(express.json({ limit: "4mb" }));

/** Service health probe — used by HF Spaces healthcheck and the GitHub Actions cron pinger. */
app.get("/healthz", (_req: Request, res: Response) => {
  res.json({
    ok: true,
    service: "specialty-lens-mcp",
    version: "0.1.0",
    sharp_enforcement: config.SHARP_ENFORCE_403,
  });
});

/** Public root — friendly response for anyone hitting the bare URL in a browser. */
app.get("/", (_req: Request, res: Response) => {
  res.json({
    service: "specialty-lens-mcp",
    description: "SHARP-on-MCP server for The Council. POST /mcp for MCP traffic; GET /healthz for liveness.",
    docs: "https://github.com/council-health-ai/council",
    sharp_capabilities: SHARP_CAPABILITIES,
  });
});

/** SHARP enforcement runs BEFORE the MCP transport — yields real HTTP 403 on missing context. */
app.post("/mcp", sharpEnforcement(), async (req: Request, res: Response) => {
  // Per-request MCP server instance (stateless pattern, matches po-community-mcp/typescript).
  // Tools capture `req` in closure to read SHARP context per invocation.
  const server = new McpServer(
    { name: "specialty-lens-mcp", version: "0.1.0" },
    { capabilities: SHARP_CAPABILITIES }
  );

  try {
    registerTools(server, req);

    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // stateless
    });
    res.on("close", () => {
      transport.close();
      server.close();
    });

    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  } catch (err) {
    logger.error({ err }, "MCP request handler failed");
    Sentry.captureException(err);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        id: (req.body as { id?: unknown })?.id ?? null,
        error: { code: -32603, message: "Internal server error" },
      });
    }
  }
});

const port = config.PORT;
app.listen(port, "0.0.0.0", () => {
  logger.info({ port, sharp_enforcement: config.SHARP_ENFORCE_403 }, "specialty-lens-mcp listening");
});
