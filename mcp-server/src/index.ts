#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

const STILL_URL = process.env.STILL_URL ?? "http://localhost:8000";
const STILL_API_KEY = process.env.STILL_API_KEY ?? "";

if (!STILL_API_KEY) {
  process.stderr.write("Warning: STILL_API_KEY is not set\n");
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<unknown> {
  const url = `${STILL_URL}${path}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${STILL_API_KEY}`,
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Still API error ${res.status}: ${text}`);
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  // For file downloads return a description instead of raw bytes
  return { content_type: contentType, message: "Binary response (download via browser)" };
}

function buildQuery(params: Record<string, unknown>): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") {
      qs.set(k, String(v));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

// ---------------------------------------------------------------------------
// Tool schemas
// ---------------------------------------------------------------------------

const GetLibrarySchema = z.object({
  entry_type: z.string().optional().describe("Filter by entry type"),
  persona: z.string().optional().describe("Filter by persona relevance"),
  min_relevance: z.number().int().min(1).max(5).optional().describe("Minimum relevance score 1–5"),
  search: z.string().optional().describe("Full-text search in content"),
  campaign: z.string().optional().describe("Filter by campaign name"),
  topic: z.string().optional().describe("Filter by topic"),
  job_id: z.string().optional().describe("Filter by source job ID"),
  status: z
    .enum(["active", "evergreen", "needs_review", "retired"])
    .optional()
    .describe("Filter by lifecycle status"),
  funnel_stage: z
    .enum(["awareness", "consideration", "decision"])
    .optional()
    .describe("Filter by funnel stage"),
  sort_by: z
    .enum(["newest", "oldest", "most_used", "never_used", "expiring_soon"])
    .optional()
    .describe("Sort order"),
  limit: z.number().int().min(1).max(100).optional().describe("Results per page (max 100)"),
  offset: z.number().int().min(0).optional().describe("Pagination offset"),
  cursor: z.string().optional().describe("Cursor for cursor-based pagination (id:value)"),
});

const RemixContentSchema = z.object({
  still_ids: z.array(z.string()).describe("Array of still IDs to remix"),
  content_type: z
    .string()
    .optional()
    .default("linkedin")
    .describe("Output format, e.g. linkedin, blog, email"),
  angle: z.string().optional().describe("Optional angle or framing for the remix"),
});

const EditContentSchema = z.object({
  output_id: z.number().int().describe("ID of the output to edit"),
  instructions: z.string().describe("Plain-language editing instructions"),
});

const AdjustToneSchema = z.object({
  output_id: z.number().int().describe("ID of the output to adjust"),
  tone_preset: z.string().describe("Name of the tone preset to apply"),
  custom_instructions: z.string().optional().describe("Additional custom tone instructions"),
});

const SaveEditSchema = z.object({
  output_id: z.number().int().describe("ID of the output to save"),
  edited_content: z.string().describe("The edited content to save"),
  edit_note: z.string().optional().describe("Optional note about this edit"),
});

const ExportContentSchema = z.object({
  job_id: z.string().describe("Job ID to export"),
  format: z
    .enum(["json", "markdown"])
    .default("json")
    .describe("Export format: json (structured data) or markdown"),
});

const GetBrandVoiceSchema = z.object({
  include_config: z
    .boolean()
    .optional()
    .default(false)
    .describe("Also return the brand voice configuration"),
});

const ListPersonasSchema = z.object({
  include_custom: z
    .boolean()
    .optional()
    .default(true)
    .describe("Include custom user-created personas alongside defaults"),
});

const GetBatchStatusSchema = z.object({
  batch_id: z.string().describe("Batch ID returned from batch/upload"),
});

// ---------------------------------------------------------------------------
// Server setup
// ---------------------------------------------------------------------------

const server = new Server(
  { name: "still-mcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

// ---------------------------------------------------------------------------
// List tools
// ---------------------------------------------------------------------------

server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "get_library",
      description:
        "Browse and search the Still content library (stills/evergreen content). Supports filtering by type, persona, campaign, topic, status, funnel stage, and full-text search.",
      inputSchema: {
        type: "object",
        properties: {
          entry_type: { type: "string", description: "Filter by entry type" },
          persona: { type: "string", description: "Filter by persona relevance" },
          min_relevance: { type: "number", description: "Minimum relevance score 1–5" },
          search: { type: "string", description: "Full-text search in content" },
          campaign: { type: "string", description: "Filter by campaign name" },
          topic: { type: "string", description: "Filter by topic" },
          job_id: { type: "string", description: "Filter by source job ID" },
          status: {
            type: "string",
            enum: ["active", "evergreen", "needs_review", "retired"],
            description: "Filter by lifecycle status",
          },
          funnel_stage: {
            type: "string",
            enum: ["awareness", "consideration", "decision"],
            description: "Filter by funnel stage",
          },
          sort_by: {
            type: "string",
            enum: ["newest", "oldest", "most_used", "never_used", "expiring_soon"],
            description: "Sort order",
          },
          limit: { type: "number", description: "Results per page (max 100)" },
          offset: { type: "number", description: "Pagination offset" },
          cursor: { type: "string", description: "Cursor for cursor-based pagination" },
        },
      },
    },
    {
      name: "remix_content",
      description:
        "Generate new content by remixing one or more stills from the library. Returns a freshly generated piece in the specified format (linkedin, blog, email, etc.).",
      inputSchema: {
        type: "object",
        required: ["still_ids"],
        properties: {
          still_ids: {
            type: "array",
            items: { type: "string" },
            description: "Array of still IDs to use as source material",
          },
          content_type: {
            type: "string",
            description: "Output format, e.g. linkedin, blog, email (default: linkedin)",
          },
          angle: {
            type: "string",
            description: "Optional angle or framing for the remix",
          },
        },
      },
    },
    {
      name: "edit_content",
      description:
        "Apply plain-language editing instructions to an existing output. Returns both the original and the edited content along with a change summary.",
      inputSchema: {
        type: "object",
        required: ["output_id", "instructions"],
        properties: {
          output_id: { type: "number", description: "ID of the output to edit" },
          instructions: {
            type: "string",
            description: "Plain-language editing instructions, e.g. 'make it shorter and punchier'",
          },
        },
      },
    },
    {
      name: "adjust_tone",
      description:
        "Apply a tone preset to an existing output. Call get_tone_presets first to discover available presets.",
      inputSchema: {
        type: "object",
        required: ["output_id", "tone_preset"],
        properties: {
          output_id: { type: "number", description: "ID of the output to adjust" },
          tone_preset: { type: "string", description: "Name of the tone preset to apply" },
          custom_instructions: {
            type: "string",
            description: "Additional custom tone instructions",
          },
        },
      },
    },
    {
      name: "save_edit",
      description: "Persist edited content back to an output, recording the change in edit history.",
      inputSchema: {
        type: "object",
        required: ["output_id", "edited_content"],
        properties: {
          output_id: { type: "number", description: "ID of the output to save" },
          edited_content: { type: "string", description: "The edited content to save" },
          edit_note: { type: "string", description: "Optional note about this edit" },
        },
      },
    },
    {
      name: "export_content",
      description:
        "Export a completed job's outputs in JSON (structured data with stills, outputs, quality scores) or Markdown format.",
      inputSchema: {
        type: "object",
        required: ["job_id"],
        properties: {
          job_id: { type: "string", description: "Job ID to export" },
          format: {
            type: "string",
            enum: ["json", "markdown"],
            description: "Export format (default: json)",
          },
        },
      },
    },
    {
      name: "get_brand_voice",
      description:
        "Retrieve the user's brand voice profile (writing style analysis) and optionally their brand voice configuration (company info, tone per channel, vocabulary).",
      inputSchema: {
        type: "object",
        properties: {
          include_config: {
            type: "boolean",
            description: "Also return the brand voice configuration (default: false)",
          },
        },
      },
    },
    {
      name: "list_personas",
      description:
        "List available target personas. Returns default built-in personas and optionally custom user-created ones.",
      inputSchema: {
        type: "object",
        properties: {
          include_custom: {
            type: "boolean",
            description: "Include custom personas (default: true)",
          },
        },
      },
    },
    {
      name: "get_batch_status",
      description:
        "Check the processing status of a batch upload. Returns per-job progress, overall completion, and total cost.",
      inputSchema: {
        type: "object",
        required: ["batch_id"],
        properties: {
          batch_id: { type: "string", description: "Batch ID returned from the batch upload" },
        },
      },
    },
    {
      name: "get_tone_presets",
      description: "List all available tone presets that can be used with adjust_tone.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "get_library_stats",
      description: "Get aggregate statistics for the content library: total entries, counts by type, most-used stills.",
      inputSchema: { type: "object", properties: {} },
    },
    {
      name: "remix_search",
      description: "Search stills in the library by topic keyword before remixing.",
      inputSchema: {
        type: "object",
        required: ["topic"],
        properties: {
          topic: {
            type: "string",
            description: "Search term (minimum 2 characters)",
          },
        },
      },
    },
  ],
}));

// ---------------------------------------------------------------------------
// Call tools
// ---------------------------------------------------------------------------

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;

  try {
    let result: unknown;

    switch (name) {
      // ── get_library ────────────────────────────────────────────────────────
      case "get_library": {
        const params = GetLibrarySchema.parse(args);
        const qs = buildQuery(params as Record<string, unknown>);
        result = await apiFetch(`/api/library${qs}`);
        break;
      }

      // ── remix_content ──────────────────────────────────────────────────────
      case "remix_content": {
        const params = RemixContentSchema.parse(args);
        result = await apiFetch("/api/remix/generate", {
          method: "POST",
          body: JSON.stringify(params),
        });
        break;
      }

      // ── edit_content ───────────────────────────────────────────────────────
      case "edit_content": {
        const params = EditContentSchema.parse(args);
        result = await apiFetch("/api/edit/apply-changes", {
          method: "POST",
          body: JSON.stringify(params),
        });
        break;
      }

      // ── adjust_tone ────────────────────────────────────────────────────────
      case "adjust_tone": {
        const params = AdjustToneSchema.parse(args);
        result = await apiFetch("/api/edit/adjust-tone", {
          method: "POST",
          body: JSON.stringify(params),
        });
        break;
      }

      // ── save_edit ──────────────────────────────────────────────────────────
      case "save_edit": {
        const params = SaveEditSchema.parse(args);
        result = await apiFetch(`/api/edit/${params.output_id}/save`, {
          method: "POST",
          body: JSON.stringify(params),
        });
        break;
      }

      // ── export_content ─────────────────────────────────────────────────────
      case "export_content": {
        const params = ExportContentSchema.parse(args);
        const fmt = params.format ?? "json";
        result = await apiFetch(`/api/export/${params.job_id}/${fmt}`);
        break;
      }

      // ── get_brand_voice ────────────────────────────────────────────────────
      case "get_brand_voice": {
        const params = GetBrandVoiceSchema.parse(args);
        const profile = await apiFetch("/api/brand-voice/profile");
        if (params.include_config) {
          const config = await apiFetch("/api/brand-voice/config");
          result = { ...(profile as object), config };
        } else {
          result = profile;
        }
        break;
      }

      // ── list_personas ──────────────────────────────────────────────────────
      case "list_personas": {
        const params = ListPersonasSchema.parse(args);
        if (params.include_custom) {
          result = await apiFetch("/api/personas/all");
        } else {
          result = await apiFetch("/api/personas");
        }
        break;
      }

      // ── get_batch_status ───────────────────────────────────────────────────
      case "get_batch_status": {
        const params = GetBatchStatusSchema.parse(args);
        result = await apiFetch(`/api/batch/${params.batch_id}/status`);
        break;
      }

      // ── get_tone_presets ───────────────────────────────────────────────────
      case "get_tone_presets": {
        result = await apiFetch("/api/edit/tone-presets");
        break;
      }

      // ── get_library_stats ──────────────────────────────────────────────────
      case "get_library_stats": {
        result = await apiFetch("/api/library/stats");
        break;
      }

      // ── remix_search ───────────────────────────────────────────────────────
      case "remix_search": {
        const { topic } = z.object({ topic: z.string().min(2) }).parse(args);
        result = await apiFetch(`/api/remix/search?topic=${encodeURIComponent(topic)}`);
        break;
      }

      default:
        return {
          content: [{ type: "text", text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      content: [{ type: "text", text: `Error: ${message}` }],
      isError: true,
    };
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  process.stderr.write("Still MCP server running on stdio\n");
}

main().catch((err) => {
  process.stderr.write(`Fatal: ${err}\n`);
  process.exit(1);
});
