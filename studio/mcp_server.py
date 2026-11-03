#!/usr/bin/env python3
"""Minimal MCP server over stdio (JSON-RPC 2.0, newline-delimited), no extra deps."""
import json, sys, traceback
import tools
def reply(i, result=None, error=None):
    m = {"jsonrpc": "2.0", "id": i}; m.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(m) + "\n"); sys.stdout.flush()
for line in sys.stdin:
    if not line.strip(): continue
    msg = json.loads(line); i, meth = msg.get("id"), msg.get("method")
    if i is None: continue  # notification
    try:
        if meth == "initialize":
            reply(i, {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "ikawn-studio", "version": "0.1.0"}})
        elif meth == "tools/list": reply(i, {"tools": tools.schema()})
        elif meth == "tools/call":
            pr = msg["params"]
            try: out, err = tools.call(pr["name"], pr.get("arguments")), False
            except Exception as e: out, err = {"error": type(e).__name__, "detail": str(e)}, True
            reply(i, {"content": [{"type": "text", "text": json.dumps(out, indent=2)}], "isError": err})
        elif meth == "ping": reply(i, {})
        else: reply(i, error={"code": -32601, "message": f"unknown method {meth}"})
    except Exception as e: reply(i, error={"code": -32603, "message": str(e), "data": traceback.format_exc()[-500:]})
