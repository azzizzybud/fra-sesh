"""Quick test of fra_governance modules."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fra_governance import run_all_self_tests
results = run_all_self_tests()
print("\n=== RESULTS ===")
for k, v in results.items():
    print(f"  {k}: {'PASS' if v else 'FAIL'}")
passed = sum(1 for v in results.values() if v)
print(f"\n{passed}/{len(results)} passed")
sys.exit(0 if passed == len(results) else 1)
