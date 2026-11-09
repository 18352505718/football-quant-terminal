import numpy as np
from scipy.optimize import root_scalar

def test_shin_fixed(odds):
    invs = np.array([1.0 / o for o in odds])
    s = np.sum(invs)
    n = len(odds)
    
    # Shin equation
    def equation(z):
        # sum sqrt(z^2 + 4*(1-z)*invs_i/s) - (2 + (n-2)*z)
        val = np.sum(np.sqrt(z**2 + 4.0 * (1.0 - z) * (invs / s))) - (2.0 + (n - 2) * z)
        return val

    print(f"\n--- Testing odds {odds} ---")
    print(f"equation(0.0) = {equation(0.0)}")
    print(f"equation(0.4) = {equation(0.4)}")
    try:
        sol = root_scalar(equation, bracket=[0.0, 0.4], method='brentq')
        z = sol.root
        print(f"Found z = {z:.4f}")
        p_fair = (np.sqrt(z**2 + 4.0 * (1.0 - z) * (invs / s)) - z) / (2.0 * (1.0 - z))
        p_fair = p_fair / np.sum(p_fair)
        print(f"p_fair: {[round(p*100, 2) for p in p_fair]}")
    except Exception as e:
        print(f"FAILED: {e}")

test_shin_fixed([1.90, 3.50, 4.20])
test_shin_fixed([1.20, 6.50, 12.0])
