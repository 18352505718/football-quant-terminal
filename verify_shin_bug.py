import numpy as np
from scipy.optimize import root_scalar

def test_shin_broken(odds):
    invs = np.array([1.0 / o for o in odds])
    s = np.sum(invs)
    
    def equation(z):
        val = np.sum(np.sqrt(z**2 + 4.0 * (1.0 - z) * (invs / s))) - (2.0 - z)
        return val

    print(f"\n--- Testing odds {odds} ---")
    print(f"invs: {invs}, s: {s}")
    print(f"equation(0.0) = {equation(0.0)}")
    print(f"equation(0.4) = {equation(0.4)}")
    try:
        sol = root_scalar(equation, bracket=[0.0, 0.4], method='brentq')
        print(f"Root z = {sol.root}")
    except Exception as e:
        print(f"FAILED with error: {e}")

test_shin_broken([1.90, 3.50, 4.20])
test_shin_broken([1.20, 6.50, 12.0])
