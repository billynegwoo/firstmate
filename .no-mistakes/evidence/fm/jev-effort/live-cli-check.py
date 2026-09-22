#!/usr/bin/env python3
"""Manual checks of real Firstmate CLIs; no stub executables or API responses."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path('/data/codex/.no-mistakes/worktrees/7eae57f62fbf/01M347KYPDCYQPWNDNMQWVJX5F')
evidence = Path('/data/codex/.no-mistakes/evidence/01M347KYPDCYQPWNDNMQWVJX5F')
temp_base = root / '.test-tmp' / 'jev-effort'
temp_base.mkdir(parents=True, exist_ok=True)
records = []
capability = {
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'typesafe_key_in_process': bool(os.environ.get('TYPESAFE_API_KEY')),
    'worktree_dotenv_exists': (root / '.env').is_file(),
    'real_tools': {name: shutil.which(name) for name in ['bash', 'jq', 'curl', 'quota-axi']},
    'network': 'No API call is required for these local CLI paths. Proxy points to closed localhost port as a guard against an unexpected request.',
    'activation_value': 'noncredential-local-validation-only is a dummy parser opt-in, never an authorized Jev key.',
    'isolation': 'FM_HOME, FM_ROOT_OVERRIDE and temporary data are inside this worktree; bootstrap uses detect-only and skips network. No Herdr session or worker is launched.'
}
(evidence / 'live-capability.json').write_text(json.dumps(capability, indent=2) + '\n')

try:
    with tempfile.TemporaryDirectory(prefix='manual-', dir=temp_base) as temp:
        home = Path(temp)
        config_dir = home / 'config'
        config_dir.mkdir()
        (config_dir / 'backend').write_text('tmux\n')
        (config_dir / 'backlog-backend').write_text('manual\n')
        brief = home / 'brief.md'
        brief.write_text('# Task\nCorrect the stated off-by-one pagination condition and verify the boundary.\n')
        cfg_file = config_dir / 'crew-dispatch.json'
        env = os.environ.copy()
        for name in ['TYPESAFE_API_KEY', 'TYPESAFE_API_KEY_PRIVATE', 'FM_CONFIG_OVERRIDE', 'FM_STATE_OVERRIDE', 'FM_DATA_OVERRIDE', 'FM_PROJECTS_OVERRIDE', 'FM_TASK_ID', 'FM_TIMING_LOG', 'TMUX', 'TMUX_PANE', 'HERDR_ENV', 'HERDR_SESSION', 'HERDR_PANE_ID', 'HERDR_SOCKET_PATH', 'CMUX_WORKSPACE_ID', 'CMUX_SURFACE_ID', 'CMUX_SOCKET_PATH', 'TASKS_AXI_FILE', 'TASKS_AXI_BACKEND']:
            env.pop(name, None)
        env.update(FM_HOME=str(home), FM_ROOT_OVERRIDE=str(home), TMPDIR=str(home), FM_BOOTSTRAP_DETECT_ONLY='1', FM_BOOTSTRAP_NETWORK='skip', FM_BOOTSTRAP_VERBOSE_FACTS='1')
        env.update({k: 'http://127.0.0.1:9' for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']})
        env.update(NO_PROXY='', no_proxy='')

        def invoke(label, tool, config, typed=False):
            if config is None:
                cfg_file.unlink(missing_ok=True)
            else:
                cfg_file.write_text(json.dumps(config) + '\n')
            child_env = env.copy()
            if typed:
                child_env['TYPESAFE_API_KEY'] = 'noncredential-local-validation-only'
            command = [str(root / 'bin' / tool)]
            if tool == 'fm-dispatch-resolve.sh':
                command += [str(brief), '--project', 'jev-effort-lab']
            run = subprocess.run(command, cwd=home, env=child_env, text=True, capture_output=True, timeout=45)
            record = {'name': label, 'command': command, 'configuration': json.loads(cfg_file.read_text()) if config is not None else None, 'typed_opt_in': typed, 'live': True, 'exit_code': run.returncode, 'stdout': run.stdout, 'stderr': run.stderr}
            records.append(record)
            print(f'{label}: exit {run.returncode}', flush=True)
            return record

        supported = ['claude', 'codex', 'grok', 'agy', 'pi', 'pi-signed', 'omp', 'muse', 'rovo']
        auto_profiles = [{'harness': h, 'effort': 'auto', 'provider': 'codex' if h in ['pi','pi-signed','omp','codex'] else 'claude' if h in ['claude','muse'] else 'google' if h == 'rovo' else 'agy'} for h in supported]
        config = {'rules': [{'when': 'A bounded bug fix with its root cause already stated.', 'use': auto_profiles}], 'default': {'harness': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'auto'}}
        r = invoke('bootstrap-supported-auto-with-key-opt-in', 'fm-bootstrap.sh', config, True)
        assert r['exit_code'] == 0 and 'CREW_DISPATCH: invalid' not in r['stdout'] and 'crew dispatch active' in r['stdout'], r
        r = invoke('bootstrap-supported-auto-without-key', 'fm-bootstrap.sh', config)
        assert r['exit_code'] == 0 and 'CREW_DISPATCH: invalid' not in r['stdout'] and 'crew dispatch active' in r['stdout'], r
        r = invoke('auto-without-key-remains-off', 'fm-dispatch-resolve.sh', config)
        assert r['exit_code'] == 0 and r['stdout'] == '' and 'dispatch-resolve: off' in r['stderr'], r

        unsupported = ['gemini', 'opencode', 'kimi', 'cursor']
        invalid_config = {'rules': [{'when': 'Work.', 'use': [{'harness': h, 'effort': 'auto', 'provider': 'google'} for h in unsupported]}]}
        r = invoke('bootstrap-rejects-four-no-flag-auto-profiles', 'fm-bootstrap.sh', invalid_config, True)
        assert 'invalid effort: cursor:auto, gemini:auto, kimi:auto, opencode:auto' in r['stdout'], r
        for harness in unsupported:
            for location in ['use', 'default']:
                profile = {'harness': harness, 'effort': 'auto', 'provider': 'google'}
                cfg = {'rules': [{'when': 'Work.', 'use': profile}]} if location == 'use' else {'rules': [{'when': 'Work.', 'use': {'harness': 'codex'}}], 'default': profile}
                r = invoke(f'resolver-rejects-{harness}-auto-in-{location}', 'fm-dispatch-resolve.sh', cfg, True)
                assert r['exit_code'] == 2 and r['stdout'] == '' and f'each {location} profile effort must be supported' in r['stderr'], r

        invalid_config['rules'][0]['use'] = [p for p in invalid_config['rules'][0]['use'] if p['harness'] != 'gemini']
        r = invoke('bootstrap-rejects-no-flag-auto-without-key', 'fm-bootstrap.sh', invalid_config)
        assert 'invalid effort: cursor:auto, kimi:auto, opencode:auto' in r['stdout'], r

        legacy_profiles = [{'harness': 'gemini', 'model': 'gemini-3.8-flash-high', 'provider': 'google', 'effort': 'high'}, {'harness': 'codex', 'model': 'gpt-5.6-luna', 'effort': 'max'}, {'harness': 'claude', 'model': 'sonnet', 'effort': 'high'}, {'harness': 'pi', 'model': 'codex-native/gpt-6-astra', 'provider': 'codex', 'effort': 'ultra'}] + [{'harness': h, 'provider': 'google'} for h in unsupported]
        legacy = {'rules': [{'when': 'Work.', 'use': legacy_profiles}]}
        r = invoke('bootstrap-preserves-pinned-and-omitted-efforts', 'fm-bootstrap.sh', legacy, True)
        assert r['exit_code'] == 0 and 'CREW_DISPATCH: invalid' not in r['stdout'] and 'gemini/gemini-3.8-flash-high/high' in r['stdout'], r
        for label, cfg in [('missing-rules', None), ('default-only-auto', {'default': config['default']}), ('empty-rules-auto', {'rules': [], 'default': config['default']}), ('legacy-default-only', {'default': legacy_profiles})]:
            r = invoke(label, 'fm-dispatch-resolve.sh', cfg, True)
            assert r['exit_code'] == 0 and 'status: escalate' in r['stdout'] and 'reason: no rules to match' in r['stdout'] and 'profile:' not in r['stdout'], r
finally:
    (evidence / 'live-cli-transcript.json').write_text(json.dumps(records, indent=2) + '\n')
    lines = ['Firstmate real CLI manual validation', json.dumps(capability, indent=2), '']
    for r in records:
        lines += [r['name'], '$ ' + ' '.join(r['command']), 'config: ' + json.dumps(r['configuration']), 'typed opt-in: ' + str(r['typed_opt_in']), 'exit: ' + str(r['exit_code']), 'stdout:', r['stdout'].rstrip() or '<empty>', 'stderr:', r['stderr'].rstrip() or '<empty>', '']
    (evidence / 'live-cli-transcript.txt').write_text('\n'.join(lines) + '\n')
