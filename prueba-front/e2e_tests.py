#!/usr/bin/env python3
import base64
import json
import subprocess
import sys
import time
import urllib.request
from typing import Tuple, Dict


def run(cmd: str) -> Tuple[int, str, str]:
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_b, err_b = proc.communicate()
    return proc.returncode, out_b.decode().strip(), err_b.decode().strip()


def get_api_url() -> str:
    code, out, err = run('aws cloudformation describe-stacks --stack-name MediSupplyStack --query "Stacks[0].Outputs[?starts_with(OutputKey,\'MediSupplyAPIEndpoint\')].OutputValue" --output text')
    if code != 0 or not out:
        raise RuntimeError(f"No se pudo obtener API URL: {err or out}")
    return out.rstrip('/').strip() + '/products'


def b64url(data: Dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip('=')


def build_jwt(groups) -> str:
    now = int(time.time())
    header = {"alg": "none", "typ": "JWT"}
    payload = {"cognito:groups": groups, "sub": f"e2e-{('allow' if groups else 'deny')}-{now}", "iat": now}
    return f"{b64url(header)}.{b64url(payload)}."


def http_get(url: str, headers: Dict[str, str]) -> Tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, method='GET', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.getcode()
            resp_headers = {k: v for k, v in resp.headers.items()}
            body = resp.read()
            return status, resp_headers, body
    except urllib.error.HTTPError as e:
        return e.code, {k: v for k, v in e.headers.items()}, e.read()


def scenario(name: str, token: str | None) -> Tuple[str, int]:
    url = get_api_url()
    headers = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    status, _, _ = http_get(url, headers)
    return name, status


def main():
    api_url = get_api_url()
    print(f"API URL: {api_url}")

    token_admin = build_jwt(["admin"])     # esperado 200 (24/7)
    token_allow = build_jwt(["clientes"])  # esperado 200 (6-22h)
    token_sales = build_jwt(["ventas"])    # esperado 200 (5-23h)
    token_deny = build_jwt([])              # esperado 403
    token_malformed = "abc.def"            # esperado 403

    tests = [
        ("ALLOW_admin", token_admin),
        ("ALLOW_clientes", token_allow),
        ("ALLOW_ventas", token_sales),
        ("DENY_sin_grupos", token_deny),
        ("DENY_malformed_token", token_malformed),
        ("DENY_sin_header", None),
    ]

    results: Dict[str, int] = {}
    for name, tok in tests:
        n, status = scenario(name, tok)
        results[n] = status
        print(f"{n}: HTTP {status}")

    print("\nResumen esperado vs obtenido:")
    expectations = {
        "ALLOW_admin": 200,
        "ALLOW_clientes": 200,
        "ALLOW_ventas": 200,
        "DENY_sin_grupos": 403,
        "DENY_malformed_token": 403,
        "DENY_sin_header": 401,  # API Gateway returns 401 for missing auth header
    }

    ok = True
    for name, expected in expectations.items():
        got = results.get(name)
        ok_case = (got == expected)
        ok = ok and ok_case
        print(f"- {name}: esperado {expected}, obtenido {got}{'' if ok_case else '  <-- MISMATCH'}")

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()


