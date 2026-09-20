from dataclasses import replace

def discrepancy(expected,actual): return {k: actual.get(k,0)-expected.get(k,0) for k in set(expected)|set(actual)}
