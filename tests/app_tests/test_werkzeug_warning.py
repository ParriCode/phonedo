"""El banner de Flask conserva la dirección sin el aviso de desarrollo."""
import ast
import logging
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SERVICES = (
    'apps/manager/manager.py',
    'apps/verifier/verifier.py',
    'apps/storage/main.py',
    'apps/publisher/publisher.py',
)


@pytest.mark.parametrize('service', SERVICES)
def test_werkzeug_banner_keeps_address_and_other_logs(service):
    path = ROOT / service
    tree = ast.parse(path.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'hide_werkzeug_dev_warning')
    namespace = {}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    filter_log = namespace['hide_werkzeug_dev_warning']

    banner = logging.LogRecord('werkzeug', logging.INFO, service, 1,
                               'WARNING: This is a development server. Do not use it in a production deployment.\n'
                               ' * Running on http://127.0.0.1:5000', (), None)
    assert filter_log(banner)
    assert banner.getMessage() == ' * Running on http://127.0.0.1:5000'

    warning = logging.LogRecord('werkzeug', logging.INFO, service, 1,
                                'WARNING: This is a development server.', (), None)
    assert filter_log(warning) is False

    request = logging.LogRecord('werkzeug', logging.INFO, service, 1, 'GET /info HTTP/1.1 200', (), None)
    assert filter_log(request)
    assert request.getMessage() == 'GET /info HTTP/1.1 200'
