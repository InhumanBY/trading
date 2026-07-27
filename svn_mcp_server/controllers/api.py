import json
import logging
import xmlrpc.client as xmlrpclib  # nosec
from datetime import datetime
from typing import Any, Optional, Tuple

import defusedxml.xmlrpc

from odoo import http
from odoo.addons.rpc.controllers.xmlrpc import dumps as odoo_dumps
from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.http import request
from odoo.service import (
    common as common_service_root,
    db as db_service_root,
    model as model_service_root,
)

from . import auth, utils
from .rate_limiting import check_rate_limit, record_api_request

_logger = logging.getLogger(__name__)
defusedxml.xmlrpc.monkey_patch()

# XML-RPC fault codes aligned with HTTP status codes
XMLRPC_FAULT_CODES = {
    'bad_request': 400,
    'unauthorized': 401,
    'forbidden': 403,
    'not_found': 404,
    'rate_limit': 429,
    'internal_error': 500,
}


def _generate_xmlrpc_fault(code: int, message: str) -> str:
    """
    Helper to generate an XML-RPC fault string with standardized codes.

    :param code: The fault code (HTTP status code)
    :type code: int
    :param message: The fault message
    :type message: str
    :return: XML-RPC fault response string
    :rtype: str
    """
    fault = xmlrpclib.Fault(code, message)
    return xmlrpclib.dumps(fault, methodresponse=1, allow_none=1)


def _get_client_ip() -> Optional[str]:
    """Get client IP address from request."""
    if request and hasattr(request, 'httprequest'):
        return request.httprequest.remote_addr
    return None


class MCPCommonController(http.Controller):
    @http.route('/mcp/xmlrpc/common', type='http', auth='none', methods=['POST'], csrf=False)
    def index(self, **kwargs):
        # Check if MCP is globally enabled
        if not utils.is_mcp_enabled():
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES['forbidden'],
                'MCP Server is disabled globally.',
            )
            return request.make_response(fault_response, [('Content-Type', 'text/xml')])

        data = request.httprequest.data
        try:
            params, method = xmlrpclib.loads(data)
            result = common_service_root.dispatch(method, params)
            response_data = xmlrpclib.dumps((result,), methodresponse=1, allow_none=1)
            return request.make_response(response_data, [('Content-Type', 'text/xml')])
        except xmlrpclib.Fault as e:
            _logger.warning(f'MCPCommonController XML-RPC Fault: Code {e.faultCode}, String: {e.faultString}')
            return request.make_response(
                xmlrpclib.dumps(e, methodresponse=1, allow_none=1),
                [('Content-Type', 'text/xml')],
            )
        except Exception as e:
            error_msg = str(e)
            _logger.error('Error in MCPCommonController: %s', error_msg, exc_info=True)
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES['internal_error'],
                f'MCPCommonController Error: {error_msg}',
            )
            return request.make_response(fault_response, [('Content-Type', 'text/xml')])


class MCPDatabaseController(http.Controller):
    @http.route('/mcp/xmlrpc/db', type='http', auth='none', methods=['POST'], csrf=False)
    def index(self, **kwargs):
        # Check if MCP is globally enabled
        if not utils.is_mcp_enabled():
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES['forbidden'],
                'MCP Server is disabled globally.',
            )
            return request.make_response(fault_response, [('Content-Type', 'text/xml')])

        data = request.httprequest.data
        try:
            params, method = xmlrpclib.loads(data)
            result = db_service_root.dispatch(method, params)
            response_data = xmlrpclib.dumps((result,), methodresponse=1, allow_none=1)
            return request.make_response(response_data, [('Content-Type', 'text/xml')])
        except xmlrpclib.Fault as e:
            _logger.warning(f'MCPDatabaseController XML-RPC Fault: Code {e.faultCode}, String: {e.faultString}')
            return request.make_response(
                xmlrpclib.dumps(e, methodresponse=1, allow_none=1),
                [('Content-Type', 'text/xml')],
            )
        except Exception as e:
            error_msg = str(e)
            _logger.error('Error in MCPDatabaseController: %s', error_msg, exc_info=True)
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES['internal_error'],
                f'MCPDatabaseController Error: {error_msg}',
            )
            return request.make_response(fault_response, [('Content-Type', 'text/xml')])


class MCPObjectController(http.Controller):
    def _validate_request(self, xmlrpc_method: str, params: list) -> None:
        """
        Validate XML-RPC method and parameters.

        :param xmlrpc_method: The XML-RPC method name
        :param params: The XML-RPC parameters
        :raises xmlrpclib.Fault: If validation fails
        """
        if xmlrpc_method != 'execute_kw':
            _logger.warning(f'MCPObjectController received non-execute_kw method: {xmlrpc_method}')
            if request and hasattr(request, 'env'):
                request.env['scp.log'].sudo().log_error(
                    error_message=f'MCPObjectController: Unsupported method {xmlrpc_method}. Only execute_kw is allowed.',
                    error_code='E400',
                    endpoint='/mcp/xmlrpc/object',
                    operation=xmlrpc_method,
                    ip_address=_get_client_ip(),
                )
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES['bad_request'],
                f'MCPObjectController: Unsupported method {xmlrpc_method}. Only execute_kw is allowed.',
            )

        if len(params) < 5:
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES['bad_request'],
                'MCPObjectController: Insufficient parameters for execute_kw.',
            )

    def _identify_user(self, auth_token: Any, uid: Any) -> Tuple[Optional[Any], Optional[int]]:
        """
        Identify user from API key or uid for rate limiting.

        :param auth_token: The authentication token (password or API key)
        :param uid: The user ID from params
        :return: Tuple of (user_obj, user_id)
        """
        user_obj = None
        user_id = None

        # First try to get user from API key if it looks like one. Suppress the
        # auth_success log: this runs per execute_kw, and the model_access entry
        # written for the same call already records user, ip and time.
        if isinstance(auth_token, str) and len(auth_token) > 20:
            user_obj = auth.get_user_from_api_key(auth_token, log_success=False)
            if user_obj:
                user_id = user_obj.id
                _logger.debug(f'MCP XML-RPC: Identified user {user_id} from API key for rate limiting.')

        # If no user from API key and uid is provided, use uid for rate limiting
        if not user_id and uid:
            user_id = uid

        return user_obj, user_id

    def _apply_rate_limiting(
        self,
        user_obj: Optional[Any],
        user_id: Optional[int],
        model_name: str,
        model_method: str,
    ) -> None:
        """
        Apply rate limiting if enabled.

        :param user_obj: The user object (if identified from API key)
        :param user_id: The user ID for rate limiting
        :param model_name: The model being accessed
        :param model_method: The method being called
        :raises xmlrpclib.Fault: If rate limit exceeded
        """
        is_enabled = request.env['ir.config_parameter'].sudo().get_param('svn_mcp_server.enable_rate_limiting', 'True') == 'True'
        if not is_enabled:
            return

        # Handle authenticated users
        if user_id:
            if not check_rate_limit(user_id):
                _logger.warning(f'MCP XML-RPC: Rate limit exceeded for user ID {user_id} on {model_name}.{model_method}.')
                env_for_log = request.env(user=user_obj.id) if user_obj else request.env
                env_for_log['scp.log'].sudo().log_rate_limit_exceeded(
                    user_id=user_id,
                    endpoint='/mcp/xmlrpc/object',
                    ip_address=_get_client_ip(),
                )
                raise xmlrpclib.Fault(
                    XMLRPC_FAULT_CODES['rate_limit'],
                    'Too many requests. Rate limit exceeded.',
                )
            record_api_request(user_id)
        else:
            anonymous_id = -1
            if not check_rate_limit(anonymous_id):
                raise xmlrpclib.Fault(
                    XMLRPC_FAULT_CODES['rate_limit'],
                    'Too many requests. Rate limit exceeded.',
                )
            record_api_request(anonymous_id)

    def _get_env_for_user(self, user_obj: Optional[Any], uid: Any) -> Any:
        """
        Get environment for the appropriate user context.

        :param user_obj: The user object (if identified from API key)
        :param uid: The user ID from params
        :return: Odoo environment for the user
        """
        if user_obj:
            return request.env(user=user_obj.id)

        if uid:
            try:
                return request.env(user=uid)
            except Exception as e:
                # Log the failure but continue with default environment
                _logger.debug(f'Failed to create environment for uid {uid}: {e}')

        return request.env

    def _result_record_ids(self, model_method: str, params: list, result: Any) -> Optional[list]:
        """Best-effort record IDs touched by the call, for the audit log.

        For read/write/unlink the IDs sit in the call args (``args[0]``); for
        create/search/search_read they are only knowable from the *result*.
        The previous implementation only inspected ``params[5][0]`` for an int,
        which never matched the ``execute_kw`` shape (args are ``[[ids], ...]``)
        nor domain-based reads, so this field was always blank. Defensive: an
        unrecognised shape logs no IDs rather than raising.
        """
        args = params[5] if len(params) > 5 and isinstance(params[5], list) else []
        if model_method in ('read', 'write', 'unlink') and args:
            first = args[0]
            if isinstance(first, int):
                return [first]
            if isinstance(first, list) and all(isinstance(i, int) for i in first):
                return list(first)
        if model_method == 'create' and isinstance(result, int):
            return [result]
        if model_method == 'search' and isinstance(result, (list, tuple)):
            return [r for r in result if isinstance(r, int)]
        if isinstance(result, (list, tuple)):  # search_read / read → dicts
            ids = [r['id'] for r in result if isinstance(r, dict) and isinstance(r.get('id'), int)]
            if ids:
                return ids
        return None

    def _summarize_request(self, model_method: str, params: list) -> str:
        """Compact, privacy-conscious description of the call.

        Records what was *asked* (method, domain/ids, requested fields, paging)
        but never the values written on create/write, which would copy business
        data into the log table. Only field *names* are kept for writes.
        """
        args = params[5] if len(params) > 5 and isinstance(params[5], list) else []
        kwargs = params[6] if len(params) > 6 and isinstance(params[6], dict) else {}
        detail: dict = {'method': model_method}
        if model_method in ('create', 'write'):
            if model_method == 'write' and args and isinstance(args[0], (int, list)):
                detail['ids'] = args[0]
            vals = args[-1] if args and isinstance(args[-1], dict) else {}
            detail['fields_written'] = sorted(vals.keys())
        else:
            if args:
                detail['args'] = args  # domain / ids / field list, non-sensitive
            for key in ('fields', 'limit', 'offset', 'order', 'groupby', 'domain'):
                if key in kwargs:
                    detail[key] = kwargs[key]
        try:
            return json.dumps(detail, default=str)
        except (TypeError, ValueError):
            return str(detail)

    def _summarize_result(self, model_method: str, result: Any) -> str:
        """Non-sensitive summary of what came back (shape/counts, not data)."""
        if isinstance(result, bool):
            return 'ok' if result else 'false'
        if isinstance(result, (list, tuple)):
            return f'{len(result)} record(s)'
        if isinstance(result, int):
            return f'id {result}' if model_method == 'create' else str(result)
        return type(result).__name__

    def _fault_for_exception(self, exc: Exception) -> Tuple[int, str]:
        """Map an Odoo exception to (XML-RPC fault code, audit error code).

        AccessDenied/AccessError/ValidationError are all UserError subclasses,
        so the specific ones are matched first; anything else is a genuine 500.
        """
        if isinstance(exc, AccessDenied):
            return XMLRPC_FAULT_CODES['unauthorized'], 'E401'
        if isinstance(exc, AccessError):
            return XMLRPC_FAULT_CODES['forbidden'], 'E403'
        if isinstance(exc, UserError):  # UserError / ValidationError
            return XMLRPC_FAULT_CODES['bad_request'], 'E400'
        return XMLRPC_FAULT_CODES['internal_error'], 'E500'

    def _clamp_result_limit(self, model_method: str, params: list) -> list:
        """Apply a per-call page ceiling to read queries when configured.

        Enforces `svn_mcp_server.max_records` (0 = unlimited, the default) on
        ``search`` / ``search_read`` so a single call cannot dump an entire
        table into the client / LLM context. This is a page ceiling, not a
        result cap: it truncates a raw list silently, so aggregation methods
        (``read_group`` / ``search_count``) are deliberately NOT limited, and
        clients are expected to paginate. Read-by-ids is left untouched.
        Behaviour is unchanged unless an admin sets a positive value.
        """
        if model_method not in ('search', 'search_read'):
            return params
        try:
            max_records = int(
                request.env['ir.config_parameter']
                .sudo()
                .get_param('svn_mcp_server.max_records', '0')
            )
        except (ValueError, TypeError):
            return params
        if max_records <= 0:
            return params

        params = list(params)
        if len(params) > 6 and isinstance(params[6], dict):
            current = params[6].get('limit')
            if not current or current > max_records:
                kwargs = dict(params[6])
                kwargs['limit'] = max_records
                params[6] = kwargs
        elif len(params) == 6:
            # No kwargs dict provided: append one carrying the cap.
            params.append({'limit': max_records})
        return params

    def _mcp_object_dispatch(self, xmlrpc_method: str, params: list):
        """
        Dispatch XML-RPC object calls with MCP access control.

        :param xmlrpc_method: The XML-RPC method name
        :type xmlrpc_method: str
        :param params: The XML-RPC parameters
        :type params: list
        :return: The result from Odoo's model service
        :raises xmlrpclib.Fault: If access is denied or parameters are invalid
        """
        self._validate_request(xmlrpc_method, params)

        # Standard params for execute_kw: (db_name, uid, password, model_name,
        # model_method, args_array, kwargs_dict)
        uid = params[1]
        auth_token = params[2]
        model_method = params[4]

        # Validate model name
        try:
            model_name = utils.sanitize_model_name(params[3])
        except ValueError as e:
            raise xmlrpclib.Fault(XMLRPC_FAULT_CODES['bad_request'], f'Invalid model name: {e}') from e

        # Identify user for rate limiting
        user_obj, user_id = self._identify_user(auth_token, uid)

        # Apply rate limiting if enabled
        self._apply_rate_limiting(user_obj, user_id, model_name, model_method)

        # Create environment for MCP access check
        env_for_check = self._get_env_for_user(user_obj, uid)

        # Track start time for performance logging
        start_time = datetime.now()
        ip_address = _get_client_ip()

        # Verify credentials BEFORE the MCP access check. Otherwise an
        # unauthenticated caller reaches check_mcp_access and can distinguish an
        # enabled model (passes) from a disabled one (distinct fault), quietly
        # enumerating the exposed surface. This repeats the check Odoo runs
        # inside dispatch, closing only the ordering gap; on success dispatch's
        # own check is a cheap indexed lookup (API keys) or a no-op.
        try:
            request.env['res.users'].sudo()._check_uid_passwd(int(uid), auth_token)
        except AccessDenied as exc:
            request.env['scp.log'].sudo().log_authentication(
                success=False,
                user_id=user_id,
                api_key_used=isinstance(auth_token, str) and len(auth_token) > 20,
                ip_address=ip_address,
                error_message='Invalid credentials',
            )
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES['unauthorized'], 'Authentication failed.'
            ) from exc

        # MCP Access Checks
        if not utils.check_mcp_access(env_for_check, model_name, model_method):
            env_for_check['scp.log'].sudo().log_permission_denied(
                model_name=model_name,
                operation=model_method,
                user_id=user_id,
                endpoint='/mcp/xmlrpc/object',
                ip_address=ip_address,
                error_message=f"Access denied by MCP for model '{model_name}' method '{model_method}'.",
            )
            raise xmlrpclib.Fault(
                XMLRPC_FAULT_CODES['forbidden'],
                f"Access denied by MCP for model '{model_name}' method '{model_method}'.",
            )

        # If all checks pass, dispatch to Odoo's standard model service
        _logger.info(f'MCP XML-RPC: Access GRANTED for {model_name}.{model_method} (User ID: {user_id if user_id else "N/A"})')

        # Enforce configured page-size cap for read queries (default: off).
        params = self._clamp_result_limit(model_method, params)

        try:
            result = model_service_root.dispatch(xmlrpc_method, params)

            # Log successful model access
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            env_for_check['scp.log'].sudo().log_model_access(
                model_name=model_name,
                operation=model_method,
                user_id=user_id,
                record_ids=self._result_record_ids(model_method, params, result),
                endpoint='/mcp/xmlrpc/object',
                http_method='POST',
                duration_ms=duration_ms,
                ip_address=ip_address,
                request_data=self._summarize_request(model_method, params),
                response_data=self._summarize_result(model_method, result),
                user_agent=request.httprequest.headers.get('User-Agent'),
            )

            return result
        except xmlrpclib.Fault:
            # Already carries a proper fault code (e.g. from a nested check).
            raise
        except Exception as e:
            # Map Odoo exceptions to the right XML-RPC fault + audit code, so
            # auth/permission/validation errors surface as 401/403/400 to the
            # client instead of a generic 500, and the log records the real
            # class of failure rather than a blanket E500.
            fault_code, err_code = self._fault_for_exception(e)
            env_for_check['scp.log'].sudo().log_error(
                error_message=str(e),
                error_code=err_code,
                endpoint='/mcp/xmlrpc/object',
                model_name=model_name,
                operation=model_method,
                user_id=user_id,
                ip_address=ip_address,
            )
            raise xmlrpclib.Fault(fault_code, str(e)) from e

    @http.route('/mcp/xmlrpc/object', type='http', auth='none', methods=['POST'], csrf=False)
    def index(self, **kwargs):
        # Check if MCP is globally enabled
        if not utils.is_mcp_enabled():
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES['forbidden'],
                'MCP Server is disabled globally.',
            )
            return request.make_response(fault_response, [('Content-Type', 'text/xml')])

        data = request.httprequest.data
        try:
            params, method = xmlrpclib.loads(data)
            result = self._mcp_object_dispatch(method, params)
            # Use Odoo's custom XML-RPC marshaller that handles date objects
            response_data = odoo_dumps((result,))
            return request.make_response(response_data, [('Content-Type', 'text/xml')])
        except xmlrpclib.Fault as e:
            _logger.warning(f'MCPObjectController XML-RPC Fault: Code {e.faultCode}, String: {e.faultString}')
            return request.make_response(
                xmlrpclib.dumps(e, methodresponse=1, allow_none=1),
                [('Content-Type', 'text/xml')],
            )
        except Exception as e:
            error_msg = str(e)
            _logger.error(
                'Critical error in MCPObjectController dispatch: %s',
                error_msg,
                exc_info=True,
            )
            fault_response = _generate_xmlrpc_fault(
                XMLRPC_FAULT_CODES['internal_error'],
                f'Internal Server Error in MCPObjectController: {error_msg}',
            )
            return request.make_response(fault_response, [('Content-Type', 'text/xml')])
