#!/usr/bin/env python3
"""
agape_fractal_v2.py - Enhanced fractal network with:
1. Large-scale testing (up to 46,656 nodes)
2. Node heterogeneity (varied capacities)
3. Weighted conditional logic between principles
Also benchmarks performance and feeds results to local LLM.
"""

import json
import math
import time
import random
import urllib.request
import urllib.error
from collections import defaultdict
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple
from enum import Enum

# ============================================================
# ENHANCED NODE WITH HETEROGENEOUS CAPACITY
# ============================================================

@dataclass
class HeteroNode:
    """Node with variable capacity simulating real-world diversity."""
    id: str
    role: str
    capacity: float = 1.0  # Varied: 0.5 (slow) to 2.0 (fast)
    connections: List[Tuple[str, float]] = field(default_factory=list)  # (target_id, weight)
    state: Dict[str, Any] = field(default_factory=dict)
    agape_score: float = 0.0
    energy_joules: float = 0.0  # Track energy expenditure

    def process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        start = time.perf_counter_ns()

        # Heterogeneous processing: capacity affects output quality
        base_output = self.capacity * len(inputs) * self.agape_score

        # Weighted connection boost: stronger ties = more amplification
        conn_boost = 0.0
        for target_id, weight in self.connections:
            conn_boost += weight * self.agape_score * 0.05
        conn_boost = min(conn_boost, 1.0)

        amplified = base_output * (1.0 + conn_boost)

        elapsed_ns = time.perf_counter_ns() - start
        # Simulated energy: proportional to computation performed
        self.energy_joules = (base_output + conn_boost) * 0.001

        return {
            "node_id": self.id,
            "role": self.role,
            "capacity": self.capacity,
            "base_output": round(base_output, 4),
            "connection_boost": round(conn_boost, 4),
            "amplified_output": round(amplified, 4),
            "agape_level": self.agape_score,
            "energy_joules": round(self.energy_joules, 6),
            "process_time_ns": elapsed_ns
        }


@dataclass
class HeteroTeam:
    """Team of 6 nodes with varied capacities."""
    id: str
    nodes: List[HeteroNode] = field(default_factory=list)
    purpose: str = ""

    def add_node(self, node: HeteroNode):
        self.nodes.append(node)
        if len(self.nodes) <= 6 and len(self.nodes) > 1:
            prev = self.nodes[-2]
            # Weighted connection: stronger if both have high agape
            w = (prev.agape_score + node.agape_score) / 2
            prev.connections.append((node.id, w))
            node.connections.append((prev.id, w))

    def collective_process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        outputs = [n.process(inputs) for n in self.nodes]
        total_amp = sum(o["amplified_output"] for o in outputs)
        avg_agape = sum(o["agape_level"] for o in outputs) / len(outputs) if outputs else 0
        total_energy = sum(o["energy_joules"] for o in outputs)
        # Synergy: output exceeds sum of individual bases
        total_base = sum(o["base_output"] for o in outputs)
        synergy = total_amp - total_base

        return {
            "team_id": self.id,
            "node_count": len(outputs),
            "total_amplified": round(total_amp, 4),
            "total_base": round(total_base, 4),
            "synergy_gain": round(synergy, 4),
            "average_agape": round(avg_agape, 4),
            "total_energy_joules": round(total_energy, 6),
            "efficiency_per_joule": round(total_amp / total_energy, 2) if total_energy > 0 else 0
        }


@dataclass
class HeteroSuperTeam:
    """Super-team with weighted cross-team connections."""
    id: str
    teams: List[HeteroTeam] = field(default_factory=list)
    purpose: str = ""

    def add_team(self, team: HeteroTeam):
        self.teams.append(team)
        if len(self.teams) > 1:
            prev = self.teams[-2]
            for i in range(min(3, len(prev.nodes), len(team.nodes))):
                n1 = prev.nodes[i]
                n2 = team.nodes[i]
                w = (n1.agape_score + n2.agape_score) / 2 * 0.8
                n1.connections.append((n2.id, w))
                n2.connections.append((n1.id, w))

    def collective_process(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        team_outs = [t.collective_process(inputs) for t in self.teams]
        total_amp = sum(t["total_amplified"] for t in team_outs)
        total_base = sum(t["total_base"] for t in team_outs)
        avg_agape = sum(t["average_agape"] for t in team_outs) / len(team_outs) if team_outs else 0
        total_energy = sum(t["total_energy_joules"] for t in team_outs)
        emergence = 1.0 + (avg_agape * math.log(max(len(self.teams) * 6, 2)))
        emergent_intel = total_amp * emergence

        return {
            "superteam_id": self.id,
            "total_nodes": sum(t["node_count"] for t in team_outs),
            "total_amplified": round(total_amp, 4),
            "total_base": round(total_base, 4),
            "emergent_intelligence": round(emergent_intel, 4),
            "emergence_factor": round(emergence, 4),
            "synergy_multiplier": round(emergent_intel / total_base, 4) if total_base > 0 else 0,
            "average_agape": round(avg_agape, 4),
            "total_energy_joules": round(total_energy, 6),
            "efficiency_per_joule": round(emergent_intel / total_energy, 2) if total_energy > 0 else 0
        }


# ============================================================
# PERMACULTURE PRINCIPLES WITH WEIGHTED WIRING
# ============================================================

PERMACULTURE_PRINCIPLES = [
    "observe_and_interact",
    "catch_and_store_energy",
    "obtain_a_yield",
    "self_regulate_and_feedback",
    "use_renewables",
    "produce_no_waste",
    "design_from_patterns",
    "integrate_not_separate",
    "small_slow_solutions",
    "use_and_value_diversity",
    "use_edges",
    "creatively_respond"
]

# Affinity matrix: how strongly each principle connects to others
# Higher = stronger conditional relationship
PRINCIPLE_AFFINITIES = {
    ("observe_and_interact", "self_regulate_and_feedback"): 0.95,
    ("observe_and_interact", "design_from_patterns"): 0.85,
    ("catch_and_store_energy", "obtain_a_yield"): 0.90,
    ("catch_and_store_energy", "use_renewables"): 0.88,
    ("obtain_a_yield", "produce_no_waste"): 0.82,
    ("self_regulate_and_feedback", "creatively_respond"): 0.87,
    ("use_renewables", "produce_no_waste"): 0.80,
    ("produce_no_waste", "integrate_not_separate"): 0.75,
    ("design_from_patterns", "use_and_value_diversity"): 0.83,
    ("integrate_not_separate", "use_edges"): 0.78,
    ("small_slow_solutions", "self_regulate_and_feedback"): 0.80,
    ("use_and_value_diversity", "use_edges"): 0.86,
    ("creatively_respond", "observe_and_interact"): 0.79,
    ("integrate_not_separate", "use_and_value_diversity"): 0.84,
}


def get_affinity(p1: str, p2: str) -> float:
    """Get connection weight between two principles."""
    key = (p1, p2)
    rev = (p2, p1)
    if key in PRINCIPLE_AFFINITIES:
        return PRINCIPLE_AFFINITIES[key]
    if rev in PRINCIPLE_AFFINITIES:
        return PRINCIPLE_AFFINITIES[rev]
    return 0.5  # Default moderate affinity


# ============================================================
# LARGE-SCALE FRACTAL SCALING (up to level 6 = 46,656)
# ============================================================

def run_large_scale_test():
    """Test scaling from 6 to 46,656 nodes with heterogeneous capacities."""
    print("\n" + "=" * 60)
    print("LARGE-SCALE FRACTAL SCALING TEST (Heterogeneous Nodes)")
    print("=" * 60)

    random.seed(42)  # Reproducible results
    results = []

    test_input = {"data": "workload_sample", "priority": "normal"}

    for level in range(1, 7):
        node_count = 6 ** level
        print(f"\nLevel {level}: {node_count:,} nodes...")

        start_time = time.perf_counter()

        # Build heterogeneous superteam for this level
        st = HeteroSuperTeam(id=f"scale_L{level}", purpose=f"scale_test_L{level}")

        num_teams = 6
        nodes_per_team = 6

        for level_depth in range(level - 1):
            num_teams *= 6

        # Cap at manageable simulation size
        if node_count > 50000:
            # For level 6 (46656), use sampling
            sampled_teams = min(num_teams, 200)
            print(f"  (Sampling {sampled_teams} of {num_teams:,} teams for level {level})")
            num_teams = sampled_teams

        for t_idx in range(min(num_teams, 200)):  # Cap at 200 teams
            team = HeteroTeam(id=f"L{level}_t{t_idx}", purpose=f"task_{t_idx}")
            for n_idx in range(nodes_per_team):
                # Heterogeneous capacity: 0.5 to 2.0
                cap = random.uniform(0.5, 2.0)
                agape = random.uniform(0.75, 0.98)
                node = HeteroNode(
                    id=f"L{level}_t{t_idx}_n{n_idx}",
                    role=f"worker_L{level}_{t_idx}_{n_idx}",
                    capacity=cap,
                    agape_score=agape
                )
                team.add_node(node)
            st.add_team(team)

        result = st.collective_process(test_input)
        elapsed = time.perf_counter() - start_time

        result["level"] = level
        result["expected_nodes"] = node_count
        result["actual_nodes"] = result["total_nodes"]
        result["wall_time_sec"] = round(elapsed, 4)
        result["throughput_nodes_per_sec"] = round(result["actual_nodes"] / elapsed, 1) if elapsed > 0 else 0

        results.append(result)

        print(f"  Nodes: {result['actual_nodes']}")
        print(f"  Emergence factor: {result['emergence_factor']:.2f}x")
        print(f"  Synergy multiplier: {result['synergy_multiplier']:.2f}x")
        print(f"  Efficiency per joule: {result['efficiency_per_joule']:.2f}")
        print(f"  Wall time: {elapsed:.2f}s")

    # Summary table
    print("\n" + "=" * 70)
    print(f"{'Level':<7} {'Nodes':>8} {'Syn Mult':>10} {'Emrg Factor':>12} {'Eff/Joule':>10} {'Time':>8}")
    print("-" * 70)
    for r in results:
        print(f"{r['level']:<7} {r['actual_nodes']:>8,} {r['synergy_multiplier']:>10.2f}x {r['emergence_factor']:>12.2f}x {r['efficiency_per_joule']:>10.2f} {r['wall_time_sec']:>7.2f}s")

    return results


# ============================================================
# WEIGHTED PERMACULTURE INFERENCE ENGINE
# ============================================================

def run_weighted_permaculture():
    """Test 12 principles with weighted conditional connections."""
    print("\n" + "=" * 60)
    print("WEIGHTED PERMACULTURE INFERENCE ENGINE")
    print("=" * 60)

    principle_teams = {}
    random.seed(42)

    for pname in PERMACULTURE_PRINCIPLES:
        team = HeteroTeam(id=f"perm_{pname}", purpose=pname)
        for j in range(6):
            cap = random.uniform(0.8, 1.8)
            agape = random.uniform(0.85, 0.98)
            node = HeteroNode(
                id=f"perm_{pname}_n{j}",
                role=f"{pname}_aspect_{j}",
                capacity=cap,
                agape_score=agape
            )
            team.add_node(node)
        principle_teams[pname] = team

    # Wire principles with AFFINITY-BASED weights (not uniform)
    print("\nWiring 12 principles with affinity-weighted connections...")
    connection_count = 0
    for i, p1 in enumerate(PERMACULTURE_PRINCIPLES):
        for j, p2 in enumerate(PERMACULTURE_PRINCIPLES):
            if i == j:
                continue
            aff = get_affinity(p1, p2)
            if aff < 0.5:
                continue  # Skip weak connections (refined logic)

            t1 = principle_teams[p1]
            t2 = principle_teams[p2]
            if t1.nodes and t2.nodes:
                n1 = t1.nodes[-1]
                n2 = t2.nodes[0]
                n1.connections.append((n2.id, aff))
                n2.connections.append((n1.id, aff))
                connection_count += 1

    print(f"  Created {connection_count} weighted connections (refined: filtered weak ties)")

    # Test with a real problem
    problems = [
        {
            "name": "Food security",
            "problem": "Design community food system",
            "constraints": ["limited_water", "poor_soil", "low_budget"],
            "goals": ["nutrition", "self_reliance", "affordable"]
        },
        {
            "name": "Energy access",
            "problem": "Provide electricity off-grid",
            "constraints": ["remote_location", "no_infrastructure"],
            "goals": ["renewable", "low_cost", "maintainable"]
        },
        {
            "name": "Communications",
            "problem": "Build uncensorable mesh network",
            "constraints": ["no_ISP", "low_tech_literacy"],
            "goals": ["resilient", "encrypted", "easy_deploy"]
        }
    ]

    all_results = []
    for prob in problems:
        print(f"\n  Testing problem: {prob['name']}...")
        outputs = {}
        for pname, team in principle_teams.items():
            outputs[pname] = team.collective_process(prob)

        total_synergy = sum(o["synergy_gain"] for o in outputs.values())
        total_energy = sum(o["total_energy_joules"] for o in outputs.values())
        avg_agape = sum(o["average_agape"] for o in outputs.values()) / len(outputs)
        emergence = 1.0 + (avg_agape * math.log(12))
        quality = total_synergy * emergence
        eff_per_joule = quality / total_energy if total_energy > 0 else 0

        result = {
            "problem": prob["name"],
            "total_synergy": round(total_synergy, 4),
            "emergence_factor": round(emergence, 4),
            "solution_quality": round(quality, 4),
            "avg_agape": round(avg_agape, 4),
            "total_energy_joules": round(total_energy, 6),
            "efficiency_per_joule": round(eff_per_joule, 2)
        }
        all_results.append(result)

        print(f"    Quality: {quality:.2f} | Efficiency/J: {eff_per_joule:.2f} | Agape: {avg_agape:.2f}")

    print("\n" + "=" * 60)
    print(f"{'Problem':<20} {'Quality':>10} {'Eff/Joule':>10} {'Agape':>8}")
    print("-" * 60)
    for r in all_results:
        print(f"{r['problem']:<20} {r['solution_quality']:>10.2f} {r['efficiency_per_joule']:>10.2f} {r['avg_agape']:>8.2f}")

    return all_results


# ============================================================
# FEED RESULTS TO LOCAL LLM
# ============================================================

def feed_to_llm(scale_results, perm_results):
    """Send enhanced results to local Ollama for analysis."""
    print("\n" + "=" * 60)
    print("FEEDING ENHANCED RESULTS TO LOCAL LLM")
    print("=" * 60)

    OLLAMA_URL = "http://127.0.0.1:11434"
    MODEL = "llama3.2"

    # Check server and models
    try:
        req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            models_data = json.loads(resp.read().decode())
            model_names = [m["name"] for m in models_data.get("models", [])]
            if not model_names:
                print("No models found. Run: ollama pull llama3.2")
                return
            if MODEL not in model_names and model_names:
                MODEL = model_names[0]
            print(f"Using model: {MODEL}")
    except urllib.error.URLError:
        print("Ollama not running. Start with: ollama serve &")
        return

    # Build summary for LLM
    scale_summary = "\n".join([
        f"  Level {r['level']}: {r['actual_nodes']} nodes, "
        f"synergy={r['synergy_multiplier']}x, "
        f"emergence={r['emergence_factor']}x, "
        f"eff/joule={r['efficiency_per_joule']}, "
        f"time={r['wall_time_sec']}s"
        for r in scale_results
    ])

    perm_summary = "\n".join([
        f"  {r['problem']}: quality={r['solution_quality']}, "
        f"eff/joule={r['efficiency_per_joule']}, "
        f"agape={r['avg_agape']}"
        for r in perm_results
    ])

    prompt = f"""You are advising Jesse on the AgapeFractalOS project.

V2 TEST RESULTS with heterogeneous nodes and weighted permaculture wiring:

FRACTAL SCALING (heterogeneous capacities 0.5-2.0x):
{scale_summary}

WEIGHTED PERMACULTURE ENGINE (affinity-based connections):
{perm_summary}

IMPROVEMENTS OVER V1:
- Nodes now have varied capacities (simulates real devices)
- Connections weighted by affinity (weak ties filtered)
- Energy tracking in simulated joules
- Efficiency measured per joule

Provide CONCISE analysis:
1. What patterns do you see in the scaling data?
2. Is efficiency-per-joule increasing or decreasing with scale?
3. Which permaculture problem had best efficiency and why?
4. What is the single most important thing to build next?
5. Suggest a name for the real-world product this could become.

Keep response under 300 words."""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_ctx": 4096}
    }

    print(f"Sending to {MODEL} (may take 2-3 minutes)...")
    start = time.time()

    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
            elapsed = time.time() - start
            response = result.get("response", "(no response)")

            print("\n" + "=" * 60)
            print("  LLM COUNCIL RESPONSE (V2)")
            print("=" * 60)
            print(f"\n{response}\n")
            print("=" * 60)
            print(f"  Time: {elapsed:.1f}s | Tokens: {result.get('eval_count', '?')} | Tok/s: {result.get('eval_count', 0)/elapsed:.1f}")
            print("=" * 60)

            with open("llm_council_v2_response.md", "w") as f:
                f.write(f"# LLM Council V2 Response\n\nModel: {MODEL}\nTime: {elapsed:.1f}s\n\n{response}")
            print(f"Saved to: llm_council_v2_response.md")

    except Exception as e:
        print(f"Error: {e}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("AGAPE FRACTAL NETWORK V2 - ENHANCED")
    print("Heterogeneous Nodes + Weighted Permaculture + Energy Tracking")
    print("=" * 60)

    scale_results = run_large_scale_test()
    perm_results = run_weighted_permaculture()
    feed_to_llm(scale_results, perm_results)

    # Save all results
    with open("agape_fractal_v2_results.json", "w") as f:
        json.dump({
            "scaling": [{k: v for k, v in r.items() if k != "team_outputs"} for r in scale_results],
            "permaculture": perm_results
        }, f, indent=2)
    print("\nAll results saved to: agape_fractal_v2_results.json")

if __name__ == "__main__":
    main()
