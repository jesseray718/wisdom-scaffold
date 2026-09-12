#!/usr/bin/env python3
from wisdom_scaffold.universal_wisdom_engine import UniversalWisdomEngine
from wisdom_scaffold.geom_analyzer import GeomAnalyzer

def run_pipeline():
    print("=== Running wisdom-scaffold Integration Pipeline ===")
    engine = UniversalWisdomEngine()
    analyzer = GeomAnalyzer()
    print("[+] Engine Pass:", engine.run_pass())
    print("[+] Geom Pass:", analyzer.analyze())
    print("[SUCCESS] Pipeline validation complete.")

if __name__ == "__main__":
    run_pipeline()
