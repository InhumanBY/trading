from odoo import api, models


class ScpSetup(models.AbstractModel):
    """Data provider for the MCP Setup Assistant OWL client action.

    Exposes a single read-only snapshot of everything the assistant needs to
    render diagnostics and generate client-configuration snippets, so the UI
    can stay a thin renderer over one ORM call.
    """

    _name = 'scp.setup'
    _description = 'MCP Setup Assistant'

    @api.model
    def get_status(self):
        """Return the current MCP setup state for the calling user."""
        icp = self.env['ir.config_parameter'].sudo()
        base_url = (icp.get_param('web.base.url') or '').rstrip('/')
        global_enabled = icp.get_param('svn_mcp_server.enabled', 'False') == 'True'

        access = self.env['scp.model.access'].sudo().search([('active', '=', True)])
        models = [
            {
                'model': rec.model_name,
                'name': rec.model_id.name,
                'read': rec.allow_read,
                'create': rec.allow_create,
                'write': rec.allow_write,
                'unlink': rec.allow_unlink,
            }
            for rec in access
        ]

        # We can only report the metadata of a key, never its value (Odoo
        # stores an irreversible hash), so the snippet uses a placeholder.
        # Listing them lets the assistant double as a key manager: generate
        # a fresh key or terminate one that leaked or is no longer used.
        keys = self.env['res.users.apikeys'].sudo().search(
            [('user_id', '=', self.env.uid)], order='create_date desc'
        )
        api_keys = [
            {
                'id': key.id,
                'name': key.name,
                'scope': key.scope or '',
                'create_date': key.create_date and str(key.create_date) or '',
                'expiration_date': key.expiration_date and str(key.expiration_date) or '',
            }
            for key in keys
        ]

        return {
            'global_enabled': global_enabled,
            'base_url': base_url,
            'db_name': self.env.cr.dbname,
            'health_url': base_url + '/mcp/health',
            'validate_url': base_url + '/mcp/auth/validate',
            'models_url': base_url + '/mcp/models',
            'models': models,
            'model_count': len(models),
            'has_api_key': bool(api_keys),
            'api_keys': api_keys,
            'user_login': self.env.user.login,
            'user_id': self.env.uid,
        }
