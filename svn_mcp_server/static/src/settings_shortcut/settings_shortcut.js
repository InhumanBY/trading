import { registry } from "@web/core/registry";

/**
 * Opens General Settings and scrolls to the MCP block.
 *
 * We open the general_settings tab (via context.module) then locate our block
 * by its field `mcp_enabled` — no URL hash needed — and scroll it into view,
 * re-asserting a few times to win against settings_page's scrollTop reset on
 * tab mount, plus a short highlight pulse.
 */
function openMcpSettings(env) {
    const done = env.services.action.doAction({
        type: "ir.actions.act_window",
        name: "Settings",
        res_model: "res.config.settings",
        view_mode: "form",
        views: [[false, "form"]],
        target: "inline",
        context: { module: "general_settings" },
    });

    done.then(() => {
        let tries = 0;
        const reveal = () => {
            const field = document.querySelector('.o_form_view [name="mcp_enabled"]');
            const el = field && (field.closest(".o_setting_box, .o_searchable_setting") || field);
            if (el) {
                const bring = () => el.scrollIntoView({ behavior: "smooth", block: "center" });
                bring();
                setTimeout(bring, 250);
                setTimeout(bring, 550);
                el.classList.add("o_setting_highlight");
                setTimeout(() => el.classList.remove("o_setting_highlight"), 3000);
                return;
            }
            if (tries++ < 40) {
                setTimeout(reveal, 50);
            }
        };
        setTimeout(reveal, 60);
    });

    return done;
}

registry.category("actions").add("svn_mcp_server.open_mcp_settings", openMcpSettings);
