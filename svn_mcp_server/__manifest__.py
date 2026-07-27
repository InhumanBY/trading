{
    'name': 'MCP Server: Easy Connect',
    'version': '1.1.1',
    'summary': 'Connect AI assistants to your Odoo instance via Model Context Protocol',
    'description': """
MCP Server for Odoo
===================

Enable AI assistants like Claude to securely
access your Odoo data through natural language queries.

Key Features
------------
* Search and retrieve any Odoo records using natural language
* Granular permissions control per model and operation
* Secure API key authentication with rate limiting
* Easy configuration through Odoo settings

How It Works
------------
1. Install this module and configure model access
2. Generate API keys for authentication
3. Install the MCP client on your AI assistant
4. Start querying your Odoo data naturally

Requirements: Odoo 19.0 and mcp-server-odoo client package
    """,
    'author': 'Sveltware Solutions',
    'website': 'https://www.linkedin.com/in/sveltware',
    'category': 'Productivity',
    'depends': ['base', 'base_setup', 'mail', 'rpc'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/mcp_model_selection.xml',
        'views/mcp_access.xml',
        'views/mcp_log.xml',
        'views/res_config.xml',
        'views/mcp_menu.xml',
        'views/mcp_setup.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'svn_mcp_server/static/src/setup_assistant/**/*',
            'svn_mcp_server/static/src/settings_shortcut/**/*',
        ],
    },
    'demo': [],
    'images': [
        'static/description/banner.png',
        'static/description/icon.png',
    ],
    'external_dependencies': {'python': ['defusedxml']},
    'license': 'LGPL-3',
}
