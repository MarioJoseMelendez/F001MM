import time
import numpy as np


BLOCK_SIZE = 64


def matmul_baseline(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # Compute matrix product using NumPy's @ operator and cast to float32
    return (a @ b).astype(np.float32)


def benchmark():
    m = 512
    k = 512
    n = 512

    rng = np.random.default_rng(0)

    a = rng.random((m, k), dtype=np.float32)
    b = rng.random((k, n), dtype=np.float32)

    # Correctness check
    result = matmul_baseline(a, b)
    reference = a @ b

    if not np.allclose(result, reference, rtol=1e-4, atol=1e-4):
        raise RuntimeError("Baseline failed correctness check")

    # Warmup
    for _ in range(3):
        matmul_baseline(a, b)

    # Benchmark
    times = []

    for _ in range(10):
        start = time.perf_counter()

        matmul_baseline(a, b)

        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)

    latency = np.median(times)
    latency_ms = latency
    print(f'Falen> latency_ms:{latency_ms}')

    print(f'Matrix: {m}x{k} @ {k}x{n}\n\nBlock size: {BLOCK_SIZE}\nLatency: {latency:.4f} ms\n\n')


def main():
    benchmark()


if __name__ == "__main__":
    main()