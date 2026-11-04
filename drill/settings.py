import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from drill.model import identifier
from drill.store import lock, now, read_json, write_json


def default_settings():
    return {'driver': 'current_agent', 'endpoint': '', 'model': '', 'api_key_env': '', 'materialization': {'submodules': False, 'lfs': False, 'allow_network': False}}


def validate_settings(value):
    if not isinstance(value, dict) or set(value) - set(default_settings()):
        raise ValueError('Unknown setup field. Store an environment-variable name rather than an API key.')
    result = default_settings()
    result.update(value)
    if result['driver'] not in {'current_agent', 'model_api'}:
        raise ValueError('Choose the current agent or an explicit model API.')
    for key in ('endpoint', 'model', 'api_key_env'):
        if not isinstance(result[key], str):
            raise ValueError('Model connection fields must be text.')
        result[key] = result[key].strip()
    if result['endpoint']:
        endpoint = urlsplit(result['endpoint'])
        if endpoint.scheme not in {'http', 'https'} or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError('Use an HTTP or HTTPS endpoint without embedded credentials or query parameters.')
        if endpoint.scheme == 'http' and endpoint.hostname not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Remote model endpoints require HTTPS.')
    if result['api_key_env'] and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', result['api_key_env']):
        raise ValueError('Enter the environment-variable name that contains the API key.')
    materialization = result['materialization']
    if not isinstance(materialization, dict) or set(materialization) - {'submodules', 'lfs', 'allow_network'} or any(type(value) is not bool for value in materialization.values()):
        raise ValueError('Data setup options must be boolean values.')
    result['materialization'] = {key: materialization.get(key, False) for key in ('submodules', 'lfs', 'allow_network')}
    if result['driver'] == 'model_api' and (not result['endpoint'] or not result['model']):
        raise ValueError('An explicit model API requires an endpoint and model.')
    return result


def load_settings(repo):
    path = repo / '.drill/settings.json'
    return validate_settings(read_json(path)) if path.exists() else default_settings()


def save_settings(repo, value):
    settings = validate_settings(value)
    with lock(repo / '.drill/.dashboard.lock'):
        write_json(repo / '.drill/settings.json', settings)
    return settings


def load_goals(repo):
    path = repo / '.drill/goals.json'
    return read_json(path) if path.exists() else []


def add_goal(repo, text, campaign=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 12000:
        raise ValueError('Enter a goal with at most 12000 characters.')
    if campaign is not None:
        identifier(campaign)
    with lock(repo / '.drill/.dashboard.lock'):
        goals = load_goals(repo)
        goal = {'id': str(max((int(row['id']) for row in goals), default=0) + 1), 'text': text.strip(), 'campaign': campaign, 'created_at': now()}
        goals.append(goal)
        write_json(repo / '.drill/goals.json', goals)
    return goal


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, url):
        return None


def call_model(repo, prompt):
    settings = load_settings(repo)
    if settings['driver'] != 'model_api':
        raise ValueError('Select and save a model API before calling it. The current agent remains the default.')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 24000:
        raise ValueError('Enter a prompt with at most 24000 characters.')
    key = os.environ.get(settings['api_key_env'], '') if settings['api_key_env'] else ''
    if settings['api_key_env'] and not key:
        raise ValueError('The configured API key environment variable is not set in the server process.')
    if key and any(not 33 <= ord(character) <= 126 for character in key):
        raise ValueError('The API key environment variable contains whitespace or unsupported characters.')
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = Request(settings['endpoint'], data=json.dumps({'model': settings['model'], 'messages': [{'role': 'user', 'content': prompt.strip()}]}).encode(), headers=headers, method='POST')
    try:
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            data = response.read(1048577)
        if len(data) > 1048576:
            raise ValueError('The model response exceeds the supported size.')
        result = json.loads(data)
        text = result['choices'][0]['message']['content']
        if not isinstance(text, str):
            raise ValueError('The endpoint did not return a text chat response.')
        return {'text': text.replace(key, '[redacted]') if key else text}
    except HTTPError as exc:
        raise ValueError(f'The model endpoint returned HTTP {exc.code}.') from None
    except URLError:
        raise ValueError('The model endpoint could not be reached.') from None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise ValueError('The endpoint did not return a supported chat response.') from None
