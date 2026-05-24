/**
 * CLI argument parsing and help display
 */
import chalk from "chalk";
import { APP_NAME, CONFIG_DIR_NAME, ENV_AGENT_DIR, ENV_SESSION_DIR } from "../config.js";
const VALID_THINKING_LEVELS = ["off", "minimal", "low", "medium", "high", "xhigh"];
export function isValidThinkingLevel(level) {
    return VALID_THINKING_LEVELS.includes(level);
}
export function parseArgs(args) {
    const result = {
        messages: [],
        fileArgs: [],
        unknownFlags: new Map(),
        diagnostics: [],
    };
    for (let i = 0; i < args.length; i++) {
        const arg = args[i];
        if (arg === "--help" || arg === "-h") {
            result.help = true;
        }
        else if (arg === "--version" || arg === "-v") {
            result.version = true;
        }
        else if (arg === "--mode" && i + 1 < args.length) {
            const mode = args[++i];
            if (mode === "text" || mode === "json" || mode === "rpc") {
                result.mode = mode;
            }
        }
        else if (arg === "--continue" || arg === "-c") {
            result.continue = true;
        }
        else if (arg === "--resume" || arg === "-r") {
            result.resume = true;
        }
        else if (arg === "--provider" && i + 1 < args.length) {
            result.provider = args[++i];
        }
        else if (arg === "--model" && i + 1 < args.length) {
            result.model = args[++i];
        }
        else if (arg === "--api-key" && i + 1 < args.length) {
            result.apiKey = args[++i];
        }
        else if (arg === "--system-prompt" && i + 1 < args.length) {
            result.systemPrompt = args[++i];
        }
        else if (arg === "--append-system-prompt" && i + 1 < args.length) {
            result.appendSystemPrompt = result.appendSystemPrompt ?? [];
            result.appendSystemPrompt.push(args[++i]);
        }
        else if (arg === "--no-session") {
            result.noSession = true;
        }
        else if (arg === "--session" && i + 1 < args.length) {
            result.session = args[++i];
        }
        else if (arg === "--fork" && i + 1 < args.length) {
            result.fork = args[++i];
        }
        else if (arg === "--session-dir" && i + 1 < args.length) {
            result.sessionDir = args[++i];
        }
        else if (arg === "--models" && i + 1 < args.length) {
            result.models = args[++i].split(",").map((s) => s.trim());
        }
        else if (arg === "--no-tools" || arg === "-nt") {
            result.noTools = true;
        }
        else if (arg === "--no-builtin-tools" || arg === "-nbt") {
            result.noBuiltinTools = true;
        }
        else if ((arg === "--tools" || arg === "-t") && i + 1 < args.length) {
            result.tools = args[++i]
                .split(",")
                .map((s) => s.trim())
                .filter((name) => name.length > 0);
        }
        else if (arg === "--thinking" && i + 1 < args.length) {
            const level = args[++i];
            if (isValidThinkingLevel(level)) {
                result.thinking = level;
            }
            else {
                result.diagnostics.push({
                    type: "warning",
                    message: `Invalid thinking level "${level}". Valid values: ${VALID_THINKING_LEVELS.join(", ")}`,
                });
            }
        }
        else if (arg === "--print" || arg === "-p") {
            result.print = true;
            const next = args[i + 1];
            if (next !== undefined && !next.startsWith("@") && (!next.startsWith("-") || next.startsWith("---"))) {
                result.messages.push(next);
                i++;
            }
        }
        else if (arg === "--export" && i + 1 < args.length) {
            result.export = args[++i];
        }
        else if ((arg === "--extension" || arg === "-e") && i + 1 < args.length) {
            result.extensions = result.extensions ?? [];
            result.extensions.push(args[++i]);
        }
        else if (arg === "--no-extensions" || arg === "-ne") {
            result.noExtensions = true;
        }
        else if (arg === "--skill" && i + 1 < args.length) {
            result.skills = result.skills ?? [];
            result.skills.push(args[++i]);
        }
        else if (arg === "--prompt-template" && i + 1 < args.length) {
            result.promptTemplates = result.promptTemplates ?? [];
            result.promptTemplates.push(args[++i]);
        }
        else if (arg === "--theme" && i + 1 < args.length) {
            result.themes = result.themes ?? [];
            result.themes.push(args[++i]);
        }
        else if (arg === "--no-skills" || arg === "-ns") {
            result.noSkills = true;
        }
        else if (arg === "--no-prompt-templates" || arg === "-np") {
            result.noPromptTemplates = true;
        }
        else if (arg === "--no-themes") {
            result.noThemes = true;
        }
        else if (arg === "--no-context-files" || arg === "-nc") {
            result.noContextFiles = true;
        }
        else if (arg === "--list-models") {
            // Check if next arg is a search pattern (not a flag or file arg)
            if (i + 1 < args.length && !args[i + 1].startsWith("-") && !args[i + 1].startsWith("@")) {
                result.listModels = args[++i];
            }
            else {
                result.listModels = true;
            }
        }
        else if (arg === "--verbose") {
            result.verbose = true;
        }
        else if (arg === "--offline") {
            result.offline = true;
        }
        else if (arg.startsWith("@")) {
            result.fileArgs.push(arg.slice(1)); // Remove @ prefix
        }
        else if (arg.startsWith("--")) {
            const eqIndex = arg.indexOf("=");
            if (eqIndex !== -1) {
                result.unknownFlags.set(arg.slice(2, eqIndex), arg.slice(eqIndex + 1));
            }
            else {
                const flagName = arg.slice(2);
                const next = args[i + 1];
                if (next !== undefined && !next.startsWith("-") && !next.startsWith("@")) {
                    result.unknownFlags.set(flagName, next);
                    i++;
                }
                else {
                    result.unknownFlags.set(flagName, true);
                }
            }
        }
        else if (arg.startsWith("-") && !arg.startsWith("--")) {
            result.diagnostics.push({ type: "error", message: `Unknown option: ${arg}` });
        }
        else if (!arg.startsWith("-")) {
            result.messages.push(arg);
        }
    }
    return result;
}
export function printHelp(extensionFlags) {
    const extensionFlagsText = extensionFlags && extensionFlags.length > 0
        ? `\n${chalk.bold("Extension CLI Flags:")}\n${extensionFlags
            .map((flag) => {
            const value = flag.type === "string" ? " <value>" : "";
            const description = flag.description ?? `Registered by ${flag.extensionPath}`;
            return `  --${flag.name}${value}`.padEnd(30) + description;
        })
            .join("\n")}\n`
        : "";
    console.log(`${chalk.bold(APP_NAME)} - spec-led coding agent for traceable implementation

${chalk.bold("Usage:")}
  ${APP_NAME} [options] [@files...] [messages...]

${chalk.bold("Commands:")}
  ${APP_NAME} install <source> [-l]     Install an extension, skill, prompt, or theme
  ${APP_NAME} remove <source> [-l]      Remove an installed resource from settings
  ${APP_NAME} uninstall <source> [-l]   Alias for remove
  ${APP_NAME} update [source|self|mofu] Update mofu and installed resources
  ${APP_NAME} list                      List enabled project and user resources
  ${APP_NAME} config                    Open the resource configuration TUI
  ${APP_NAME} <command> --help          Show command-specific help

${chalk.bold("Options:")}
  --provider <name>              Provider name, chosen through the mofumofu provider contract
  --model <pattern>              Model ID or provider/model pattern, optionally with :<thinking>
  --api-key <key>                Runtime API key; prefer environment variables for persistence safety
  --system-prompt <text>         Replace the session system prompt
  --append-system-prompt <text>  Append text or file contents to the system prompt
  --mode <mode>                  Output mode: text (default), json, or rpc
  --print, -p                    Non-interactive mode for scripts and release checks
  --continue, -c                 Continue the previous session
  --resume, -r                   Select a session to resume
  --session <path|id>            Use a specific session file or partial UUID
  --fork <path|id>               Fork a session into a new branch
  --session-dir <dir>            Override session storage and lookup
  --no-session                   Run without writing a session log
  --models <patterns>            Comma-separated model cycle list for Ctrl+P
  --no-tools, -nt                Disable all built-in and extension tools
  --no-builtin-tools, -nbt       Disable built-in tools while keeping extension tools
  --tools, -t <tools>            Comma-separated tool allowlist
  --thinking <level>             Thinking level: off, minimal, low, medium, high, xhigh
  --extension, -e <path>         Load an extension file
  --no-extensions, -ne           Disable extension discovery
  --skill <path>                 Load a skill file or directory
  --no-skills, -ns               Disable skills discovery and loading
  --prompt-template <path>       Load prompt templates
  --no-prompt-templates, -np     Disable prompt template discovery and loading
  --theme <path>                 Load a theme file or directory; built-ins include mofumofu
  --no-themes                    Disable theme discovery and loading
  --no-context-files, -nc        Disable AGENTS.md and CLAUDE.md discovery
  --export <file>                Export a session file to HTML and exit
  --list-models [search]         List available models
  --verbose                      Show startup and resource details
  --offline                      Disable startup network operations
  --help, -h                     Show this help
  --version, -v                  Show version number

Extensions can register additional flags. Use the Python control plane for spec, audit, trace, gate, and release workflows: python -m mofu --help.${extensionFlagsText}

${chalk.bold("Examples:")}
  # Start a spec-led interactive session
  ${APP_NAME}

  # Start with a concrete implementation goal
  ${APP_NAME} "Implement REQ-GATE-001 and stop if the gate is not PASS."

  # Include source-of-truth files in the initial context
  ${APP_NAME} @.mofumofu/specs/product-release-baseline/tasks.md @docs/requirements.md "Audit remaining blockers."

  # Non-interactive release check
  ${APP_NAME} -p "Summarize the current release gate and cite the evidence files."

  # Resume the last session after compaction or interruption
  ${APP_NAME} --continue "Continue from the last validated blocker."

  # Use the local LM Studio/OpenAI-compatible provider
  ${APP_NAME} --provider openai --model qwen/qwen3.6-27b "Review the trace map."

  # Read-only review mode
  ${APP_NAME} --tools read,grep,find,ls -p "Review the code touched by Slice 11."

  # Export evidence for a session
  ${APP_NAME} --export ~/${CONFIG_DIR_NAME}/agent/sessions/--path--/session.jsonl
  ${APP_NAME} --export session.jsonl output.html

${chalk.bold("Provider Environment Variables:")}
  ANTHROPIC_API_KEY                - Anthropic Claude API key
  ANTHROPIC_OAUTH_TOKEN            - Anthropic OAuth token (alternative to API key)
  OPENAI_API_KEY                   - OpenAI GPT API key
  AZURE_OPENAI_API_KEY             - Azure OpenAI API key
  AZURE_OPENAI_BASE_URL            - Azure OpenAI/Cognitive Services base URL (e.g. https://{resource}.openai.azure.com)
  AZURE_OPENAI_RESOURCE_NAME       - Azure OpenAI resource name (alternative to base URL)
  AZURE_OPENAI_API_VERSION         - Azure OpenAI API version (default: v1)
  AZURE_OPENAI_DEPLOYMENT_NAME_MAP - Azure OpenAI model=deployment map (comma-separated)
  DEEPSEEK_API_KEY                 - DeepSeek API key
  GEMINI_API_KEY                   - Google Gemini API key
  GROQ_API_KEY                     - Groq API key
  CEREBRAS_API_KEY                 - Cerebras API key
  XAI_API_KEY                      - xAI Grok API key
  FIREWORKS_API_KEY                - Fireworks API key
  TOGETHER_API_KEY                 - Together AI API key
  OPENROUTER_API_KEY               - OpenRouter API key
  AI_GATEWAY_API_KEY               - Vercel AI Gateway API key
  ZAI_API_KEY                      - ZAI API key
  MISTRAL_API_KEY                  - Mistral API key
  MINIMAX_API_KEY                  - MiniMax API key
  MOONSHOT_API_KEY                 - Moonshot AI API key
  OPENCODE_API_KEY                 - OpenCode Zen/OpenCode Go API key
  KIMI_API_KEY                     - Kimi For Coding API key
  CLOUDFLARE_API_KEY               - Cloudflare API token (Workers AI and AI Gateway)
  CLOUDFLARE_ACCOUNT_ID            - Cloudflare account id (required for both)
  CLOUDFLARE_GATEWAY_ID            - Cloudflare AI Gateway slug (required for AI Gateway)
  XIAOMI_API_KEY                   - Xiaomi MiMo API key (api.xiaomimimo.com billing)
  XIAOMI_TOKEN_PLAN_CN_API_KEY     - Xiaomi MiMo Token Plan API key (China region)
  XIAOMI_TOKEN_PLAN_AMS_API_KEY    - Xiaomi MiMo Token Plan API key (Amsterdam region)
  XIAOMI_TOKEN_PLAN_SGP_API_KEY    - Xiaomi MiMo Token Plan API key (Singapore region)
  AWS_PROFILE                      - AWS profile for Amazon Bedrock
  AWS_ACCESS_KEY_ID                - AWS access key for Amazon Bedrock
  AWS_SECRET_ACCESS_KEY            - AWS secret key for Amazon Bedrock
  AWS_BEARER_TOKEN_BEDROCK         - Bedrock API key (bearer token)
  AWS_REGION                       - AWS region for Amazon Bedrock (e.g., us-east-1)
${chalk.bold("mofumofu Environment Variables:")}
  ${ENV_AGENT_DIR.padEnd(32)} - Config directory (default: ~/${CONFIG_DIR_NAME}/agent)
  ${ENV_SESSION_DIR.padEnd(32)} - Session storage directory (overridden by --session-dir)
  MOFUMOFU_LOCAL_BASE_URL          - Local OpenAI-compatible endpoint for control-plane E2E
  MOFUMOFU_HOSTED_BASE_URL         - Hosted OpenAI-compatible endpoint for control-plane probes
  MOFU_PACKAGE_DIR                 - Override package directory
  MOFU_OFFLINE                     - Disable startup network operations
  MOFU_TELEMETRY                   - Override install telemetry
  MOFU_SHARE_VIEWER_URL            - Base URL for /share command

${chalk.bold("Built-in Tool Names:")}
  read   - Read file contents for trace-backed context
  bash   - Execute validation, build, and release commands
  edit   - Edit files with find/replace
  write  - Write generated artifacts or implementation files
  grep   - Search file contents
  find   - Find files by glob pattern
  ls     - List directory contents
`);
}
//# sourceMappingURL=args.js.map