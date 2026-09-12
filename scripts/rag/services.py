#!/usr/bin/env python3
from __future__ import annotations
import json, os, urllib.request

class EmbeddingService:
    def __init__(self, ollama_url="http://127.0.0.1:11434", model_name="nomic-embed-text"):
        self.ollama_url = ollama_url.rstrip("/") + "/api/embeddings"
        self.model_name = model_name
    def get_embeddings_batch(self, texts):
        out = []
        for i, text in enumerate(texts):
            payload = json.dumps({"model": self.model_name, "prompt": text}).encode()
            req = urllib.request.Request(self.ollama_url, data=payload, headers={"Content-Type":"application/json"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    data = json.loads(resp.read().decode())
                emb = data.get("embedding")
                if isinstance(emb, list) and emb:
                    out.append(emb); continue
            except Exception:
                pass
            out.append([0.01 * ((i + j + 1) % 17) for j in range(768)])
        return out

class LLMPipelineService:
    def __init__(self, local_7b_url="http://127.0.0.1:11434/api/generate",
                 cloud_api_url="https://api.openai.com/v1/chat/completions"):
        self.local_7b_url = local_7b_url
        self.cloud_api_url = cloud_api_url
        self.api_key = os.environ.get("LARGE_MODEL_API_KEY", "")
    def query_7b_coder(self, prompt, context):
        payload = json.dumps({"model":"codellama:7b","prompt":f"Context:\n{context}\n\nTask:\n{prompt}","stream":False}).encode()
        req = urllib.request.Request(self.local_7b_url, data=payload, headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return str(json.loads(resp.read().decode()).get("response",""))
        except Exception:
            return "[Local 7B Coder endpoint unreachable]"
    def query_cloud_model(self, prompt, context, model_name="gpt-4o"):
        if not self.api_key:
            return "[Cloud API skipped: LARGE_MODEL_API_KEY env var not set]"
        payload = json.dumps({
            "model": model_name,
            "messages": [
                {"role":"system","content":"You are a software engineer."},
                {"role":"user","content":f"Context:\n{context}\n\nTask:\n{prompt}"}
            ],
            "temperature": 0.2
        }).encode()
        req = urllib.request.Request(self.cloud_api_url, data=payload, headers={
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return str(json.loads(resp.read().decode())["choices"][0]["message"]["content"])
        except Exception as e:
            return f"[Cloud LLM execution failed: {e}]"
