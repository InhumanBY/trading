import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { usePopover } from "@web/core/popover/popover_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

const LOGO = "/svn_mcp_server/static/description/";

// Each client differs in transport, config file location and format.
const CLIENTS = [
    { id: "claude-web", name: "Claude Web", logo: "img/claude_logo.png", kind: "remote" },
    { id: "claude-desktop", name: "Claude Desktop", logo: "img/claude_logo.png", kind: "json", path: "claude_desktop_config.json" },
    { id: "claude-code", name: "Claude Code", logo: "img/claude_logo.png", kind: "cli" },
    { id: "vscode", name: "VS Code", logo: "img/vscode_logo.png", kind: "json", path: ".vscode/mcp.json" },
    { id: "other", name: "Other Client", icon: true, kind: "json", path: "your client's MCP config" },
];

/** Env vars for the bridge, authenticating with the scoped API key. */
function buildEnv(s) {
    return {
        ODOO_URL: s.base_url,
        ODOO_DB: s.db_name,
        ODOO_USER: s.user_login,
        ODOO_API_KEY: "<your-api-key>",
    };
}

/** Build the copy-ready snippet + steps for a client, given the status. */
function buildGuide(client, s) {
    if (!s) {
        return { steps: [], code: "" };
    }
    const env = buildEnv(s);

    if (client.kind === "remote") {
        // Streaming clients (Claude web/mobile, openclaw, n8n…) need a public
        // HTTPS MCP endpoint. The addon doesn't expose one natively, so run the
        // bridge in streamable-http transport. Easiest place: on the Odoo host
        // itself, reusing Odoo's existing domain + TLS + reverse proxy.
        const host = new URL(s.base_url).host;
        const remoteEnv = { ...env, ODOO_MCP_HOST: "localhost", ODOO_MCP_ALLOWED_HOSTS: `${host},localhost` };
        const envLines = Object.entries(remoteEnv).map(([k, v]) => `${k}=${v} \\`);
        return {
            note: "Easiest setup: run this on the Odoo server and add one /mcp location to Odoo's existing reverse proxy. Full nginx recipe (and the 421/timeout gotchas) is in the README.",
            steps: [
                "Run the bridge as a local HTTP server (binds localhost, nothing public yet):",
                `Add a /mcp location to your reverse proxy → 127.0.0.1:8077. Two must-dos: forward the port in the Host header (proxy_set_header Host $host:$server_port) or the bridge returns 421, and raise proxy_read_timeout for the long-lived SSE stream.`,
                "This endpoint has NO built-in auth. Gate the /mcp location (basic auth or Cloudflare Access) and use a scoped, non-admin key.",
                `Add https://${host}/mcp as a custom connector in Claude.`,
            ],
            code: [...envLines, "uvx mcp-server-odoo --transport streamable-http --host localhost --port 8077"].join("\n"),
        };
    }
    if (client.kind === "cli") {
        const lines = ["claude mcp add odoo \\"];
        for (const [k, v] of Object.entries(env)) {
            lines.push(`  -e ${k}=${v} \\`);
        }
        lines.push("  -- uvx mcp-server-odoo");
        return { steps: ["Run this in your terminal (needs uv installed):"], code: lines.join("\n") };
    }
    // json
    const json = JSON.stringify(
        { mcpServers: { odoo: { command: "uvx", args: ["mcp-server-odoo"], env } } },
        null,
        2
    );
    return { steps: [`Add to ${client.path} and restart the client:`], code: json };
}

/** Popover content: tailored setup for one client. */
export class ClientGuide extends Component {
    static template = "svn_mcp_server.ClientGuide";
    static props = { client: Object, status: Object, copy: Function, close: Function };

    get logo() {
        return this.props.client.logo ? LOGO + this.props.client.logo : null;
    }
    get guide() {
        return buildGuide(this.props.client, this.props.status);
    }
}

/**
 * MCP Setup Assistant — diagnoses every link in the MCP chain and generates
 * copy-ready, per-client configuration. Reads one snapshot from
 * `scp.setup.get_status` and probes the live `/mcp/*` endpoints via the
 * browser session to confirm the real path.
 */
export class McpSetupAssistant extends Component {
    static template = "svn_mcp_server.SetupAssistant";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.clientPopover = usePopover(ClientGuide, { position: "bottom", popoverClass: 'fs-6', });
        this.clients = CLIENTS;
        this.state = useState({
            status: null,
            loading: true,
            probing: false,
            probe: null,
        });
        onWillStart(async () => {
            this.state.status = await this.orm.call("scp.setup", "get_status", []);
            this.state.loading = false;
        });
    }

    clientLogo(client) {
        return client.logo ? LOGO + client.logo : null;
    }

    openClient(ev, client) {
        this.clientPopover.open(ev.currentTarget, {
            client,
            status: this.state.status,
            copy: this.copy.bind(this),
        });
    }

    // ----- derived diagnostics ---------------------------------------------
    get checks() {
        const s = this.state.status;
        if (!s) {
            return [];
        }
        return [
            {
                key: "global",
                label: "MCP Server enabled",
                ok: s.global_enabled,
                hint: s.global_enabled
                    ? "Global switch is on."
                    : "Turn on 'MCP Server Access' in Settings › Integrations.",
            },
            {
                key: "models",
                label: "Models exposed",
                ok: s.model_count > 0,
                hint: s.model_count > 0
                    ? `${s.model_count} model(s) whitelisted.`
                    : "No model is exposed yet. Add one under MCP Available Models.",
            },
            {
                key: "apikey",
                label: "API key for your user",
                ok: s.has_api_key,
                hint: s.has_api_key
                    ? "At least one API key exists."
                    : "Generate a key in your Account Security to authenticate a client.",
            },
        ];
    }

    get ready() {
        const c = this.checks;
        return c.length > 0 && c.every((x) => x.ok);
    }

    get readyCount() {
        return this.checks.filter((x) => x.ok).length;
    }

    // ----- live HTTP probe --------------------------------------------------
    async testConnection() {
        this.state.probing = true;
        this.state.probe = { health: null, auth: null, models: null, read: null };
        const s = this.state.status;
        try {
            this.state.probe.health = await this._probe(s.health_url, false);
            this.state.probe.auth = await this._probe(s.validate_url, true);
            this.state.probe.models = await this._probe(s.models_url, true);
            this.state.probe.read = await this._readSanity();
        } finally {
            this.state.probing = false;
        }
    }

    /**
     * Prove data actually flows, not just that the endpoints answer. The most
     * common "the AI just returns null" report (see store reviews) is an
     * instance that connects fine but exposes nothing, or exposes only empty
     * models, so a real query comes back with no rows. We read a live count
     * from the first readable model to surface that before the user hits it in
     * their client. Counting runs as the current (admin) user, so it proves the
     * records exist; what the AI sees is still bounded by the key user's rights.
     */
    async _readSanity() {
        const models = (this.state.status.models || []).filter((m) => m.read);
        if (!models.length) {
            return { ok: false, reason: "no-models" };
        }
        const target = models[0];
        try {
            const count = await this.orm.searchCount(target.model, []);
            return { ok: true, model: target.model, count };
        } catch {
            return { ok: false, reason: "read-failed", model: target.model };
        }
    }

    async _probe(url, expectSuccessBody) {
        try {
            const res = await fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: { Accept: "application/json" },
            });
            if (!res.ok) {
                return "fail";
            }
            if (!expectSuccessBody) {
                return "ok";
            }
            const data = await res.json();
            return data && data.success ? "ok" : "fail";
        } catch {
            return "fail";
        }
    }

    async copy(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.notification.add("Copied to clipboard", { type: "success" });
        } catch {
            this.notification.add("Copy failed, select and copy manually", {
                type: "warning",
            });
        }
    }

    // ----- quick actions ----------------------------------------------------
    /**
     * A key with no expiration lives forever until revoked. Once it passes
     * ~30 days we nudge the user to rotate it — a leaked long-lived key is the
     * quiet landmine here. Self-expiring keys already handle their own rotation.
     */
    keyStale(key) {
        if (key.expiration_date || !key.create_date) {
            return false;
        }
        const created = new Date(key.create_date.replace(" ", "T") + "Z");
        return (Date.now() - created.getTime()) / 86400000 >= 30;
    }

    async _refreshStatus() {
        this.state.status = await this.orm.call("scp.setup", "get_status", []);
    }

    async generateApiKey() {
        const action = await this.orm.call("res.users", "api_key_wizard", [
            [this.state.status.user_id],
        ]);
        this.action.doAction(action, { onClose: () => this._refreshStatus() });
    }

    /**
     * Terminate one API key. `remove()` carries Odoo's @check_identity guard,
     * so it returns the identity-check wizard when re-auth is needed and an
     * act_window_close otherwise — doAction handles both, and we refresh after.
     */
    revokeKey(key) {
        this.dialog.add(ConfirmationDialog, {
            title: "Terminate API key",
            body:
                `"${key.name}" will stop working immediately. Any client still ` +
                `using it loses access at once. This cannot be undone.`,
            confirmLabel: "Terminate",
            confirmClass: "btn-danger",
            confirm: async () => {
                const action = await this.orm.call("res.users.apikeys", "remove", [[key.id]]);
                this.action.doAction(action, { onClose: () => this._refreshStatus() });
            },
            cancel: () => {},
        });
    }

    openModels() {
        this.action.doAction("svn_mcp_server.mcp_model_access_action");
    }

    async openSettings() {
        this.action.doAction("svn_mcp_server.mcp_open_settings_action");
    }
}

registry.category("actions").add("svn_mcp_server.setup_assistant", McpSetupAssistant);
