#!/data/data/com.termux/files/usr/bin/python3
"""FUSION CORE v1.0 - Progressive Enhancement + Primitive Fallback"""

import os, json
from datetime import datetime
from typing import Callable, Any

class FusionSystem:
    def __init__(self, name, primitive_method, modern_method, context_file):
        self.name = name
        self.primitive = primitive_method
        self.modern = modern_method
        self.context_file = context_file
        self.fallback_active = False

    def operate(self, *args, **kwargs):
        try:
            result = self.modern(*args, **kwargs)
            if self.fallback_active:
                self._log("MODERN_RESTORED", "Recovered from fallback.")
                self.fallback_active = False
            return result
        except Exception as e:
            self.fallback_active = True
            self._log("MODERN_FAILURE", str(e) + " - switching to primitive.")
            try:
                return self.primitive(*args, **kwargs)
            except Exception as e2:
                self._log("CRITICAL_FAILURE", "Both systems failed: " + str(e2))
                raise RuntimeError("Total system collapse.") from e2

    def _log(self, event_type, message):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "system": self.name,
            "event": event_type,
            "message": message,
            "status": "fallback_active" if self.fallback_active else "normal"
        }
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, 'r') as f:
                    ctx = json.load(f)
            except:
                ctx = {}
        else:
            ctx = {}
        if "events" not in ctx:
            ctx["events"] = []
        ctx["events"].append(entry)
        if len(ctx["events"]) > 100:
            ctx["events"] = ctx["events"][-50:]
        with open(self.context_file, 'w') as f:
            json.dump(ctx, f, indent=2)
        print("[FUSION-" + self.name + "] " + event_type + ": " + message)

if __name__ == "__main__":
    ctx_path = "os.environ.get("OPENROOT_BASE", "/sdcard/openroot") + "/"context_bridge/context.json"
    os.makedirs(os.path.dirname(ctx_path), exist_ok=True)

    def modern_fail():
        raise ConnectionError("Sensor offline")

    def primitive_works():
        return "Collected from transpiration bag (1.2L)"

    ws = FusionSystem("WaterProcurement", primitive_works, modern_fail, ctx_path)
    print("Attempting Water Acquisition...")
    try:
        result = ws.operate()
        print("Result: " + str(result))
    except RuntimeError as e:
        print("CRITICAL: " + str(e))
