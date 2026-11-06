"""Offline contract check, run inside the pinned Hermes image with no network/secrets."""
import asyncio
from contextlib import contextmanager
import json
from types import SimpleNamespace
from unittest.mock import patch

import yaml
from hermes_cli.plugins import discover_plugins, get_plugin_command_handler
from hermes_cli.tools_config import _get_platform_tools
from model_tools import get_tool_definitions
from gateway.config import GatewayConfig, Platform
from gateway.session import SessionSource
from gateway.run_inbound import GatewayInboundMixin
from gateway import session_context
from valren.config import Settings


discover_plugins()
config = yaml.safe_load(open('/work/hermes/config.yaml'))
for platform in ('cli', 'telegram'):
    enabled = _get_platform_tools(config, platform)
    definitions = get_tool_definitions(list(enabled), config['agent']['disabled_toolsets'], quiet_mode=True)
    names = sorted(tool.get('function', tool)['name'] for tool in definitions)
    assert names == ['valren_library_search'], (platform, enabled, names)
    print(json.dumps({'platform': platform, 'model_tools': names}))

for name in ('valren-tutor', 'valren-tutor-retry'):
    assert get_plugin_command_handler(name), name

@contextmanager
def bound(context):
    source = context.source
    tokens = session_context.set_session_vars(platform=source.platform.value,
        user_id=source.user_id, chat_id=source.chat_id)
    try:
        yield
    finally:
        session_context.clear_session_vars(tokens)

runner = SimpleNamespace(_draining=False, config=GatewayConfig(),
    _hm_quick_commands=lambda: {}, _session_key_for_source=lambda source: 'offline-test',
    _session_env_scope=bound, _run_in_executor_with_context=asyncio.to_thread)
settings = Settings(telegram={'user_ids': [123], 'chat_ids': [456]})

async def dispatch(user, chat, command='valren_tutor'):
    source = SessionSource(platform=Platform.TELEGRAM, user_id=str(user), chat_id=str(chat))
    event = SimpleNamespace(get_command_args=lambda: 'arxiv:2401.12345')
    return await GatewayInboundMixin._hm_dispatch_quick_and_plugin_commands(runner, event, source, command)

with patch('valren.config.load', return_value=settings), patch('subprocess.run') as run:
    run.return_value = SimpleNamespace(stdout=json.dumps({'lesson': 'offline lesson'}))
    assert asyncio.run(dispatch(123, 456))[1] == 'offline lesson'
    assert run.call_count == 1
    assert run.call_args.args[0][-2:] == ['--', 'arxiv:2401.12345']
    for user, chat in ((999, 456), (123, 999)):
        assert 'ValueError' in asyncio.run(dispatch(user, chat))[1]
    # An environment identity cannot authorize a direct call without a bound context.
    session_context.reset_session_vars()
    with patch.dict('os.environ', {'HERMES_SESSION_PLATFORM': 'telegram',
            'HERMES_SESSION_USER_ID': '123', 'HERMES_SESSION_CHAT_ID': '456'}):
        assert 'ValueError' in get_plugin_command_handler('valren-tutor')('arxiv:2401.12345')
    assert run.call_count == 1
print(json.dumps({'gateway_dispatch': 'pass', 'unauthorized_and_env_spoof': 'blocked', 'network': 'none'}))
