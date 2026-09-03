#!/usr/bin/env python3
import math
import numpy as np

# Core Constants
PHI = (1.0 + math.sqrt(5.0)) / 2.0
RECIPROCAL_PHI = 1.0 / PHI
VESICA_RATIO = math.sqrt(3.0)
OCTAVE_FACTOR = 2.0

class GeometricAnalyzer:
    def __init__(self, tolerance=1e-3):
        self.tol = tolerance

    def analyze_ratio(self, val1, val2):
        if val2 == 0:
            return {"error": "Division by zero"}
        ratio = abs(val1 / val2)
        
        results = {
            "value": ratio,
            "matches": []
        }
        
        # Check Phi Alignment
        if abs(ratio - PHI) < self.tol:
            results["matches"].append("Golden Ratio (Phi)")
        elif abs(ratio - RECIPROCAL_PHI) < self.tol:
            results["matches"].append("Reciprocal Phi (1/Phi)")
            
        # Check Vesica Ratio Alignment
        if abs(ratio - VESICA_RATIO) < self.tol:
            results["matches"].append("Vesica Piscis Height/Width (sqrt(3))")
            
        # Check Octave Power Alignment
        log2_val = math.log2(ratio) if ratio > 0 else 0
        if abs(log2_val - round(log2_val)) < self.tol:
            results["matches"].append(f"Pure Octave Step (2^{int(round(log2_val))})")
            
        return results

    def analyze_3d_vectors(self, vectors):
        """Evaluates vector sets for Isotropic Vector Matrix (IVM) characteristics."""
        vecs = np.array(vectors)
        norms = np.linalg.norm(vecs, axis=1)
        
        # Check uniform vector length
        is_equidistant = np.allclose(norms, norms[0], atol=self.tol) if len(norms) > 0 else False
        
        # Compute dot products / angles
        angles = []
        num_vecs = len(vecs)
        for i in range(num_vecs):
            for j in range(i + 1, num_vecs):
                cos_theta = np.dot(vecs[i], vecs[j]) / (norms[i] * norms[j])
                cos_theta = np.clip(cos_theta, -1.0, 1.0)
                angles.append(math.degrees(math.acos(cos_theta)))
                
        has_60_deg = any(abs(a - 60.0) < self.tol for a in angles)
        has_90_deg = any(abs(a - 90.0) < self.tol for a in angles)
        
        is_ivm_compatible = is_equidistant and has_60_deg
        
        return {
            "uniform_length": is_equidistant,
            "has_60_degree_angles": has_60_deg,
            "has_90_degree_angles": has_90_deg,
            "ivm_octet_truss_compatible": is_ivm_compatible
        }

    def eval_agape_harmonic_resonance(self, frequency_hz, base_freq=432.0):
        """
        Evaluates harmonic alignment across Phi, Vesica (sqrt(3)), and Octave multipliers.
        Synergetic alignment score determines structural resonance.
        """
        ratio = frequency_hz / base_freq
        
        phi_score = math.exp(-((ratio % PHI) ** 2) / self.tol)
        vesica_score = math.exp(-((ratio % VESICA_RATIO) ** 2) / self.tol)
        octave_score = math.exp(-((math.log2(ratio) % 1.0) ** 2) / self.tol) if ratio > 0 else 0.0
        
        synergy_index = (phi_score + vesica_score + octave_score) / 3.0
        
        return {
            "input_frequency": frequency_hz,
            "base_reference": base_freq,
            "phi_resonance": phi_score,
            "vesica_resonance": vesica_score,
            "octave_resonance": octave_score,
            "agape_synergy_index": synergy_index
        }

if __name__ == "__main__":
    analyzer = GeometricAnalyzer()
    
    print("=== GEOMETRIC & HARMONIC ANALYSIS ===")
    
    # Analyze Ratio Example
    r_res = analyzer.analyze_ratio(1.73205, 1.0)
    print(f"\n[+] Ratio Analysis (1.73205 / 1.0): {r_res['matches']}")
    
    # Analyze IVM Vector Matrix Example (12 Vertices of Cuboctahedron)
    ivm_vectors = [
        [1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0],
        [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
        [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1]
    ]
    ivm_res = analyzer.analyze_3d_vectors(ivm_vectors)
    print(f"[+] IVM Octet-Truss Compatibility: {ivm_res['ivm_octet_truss_compatible']}")
    
    # Synergetic Resonance Evaluation
    agape_res = analyzer.eval_agape_harmonic_resonance(432.0 * PHI)
    print(f"[+] Agape Synergy Index (432 * Phi Hz): {agape_res['agape_synergy_index']:.4f}")
