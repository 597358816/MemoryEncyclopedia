# gpu_full.py
import time
import torch
import torch.multiprocessing as mp


def worker(gpu_id):
    torch.cuda.set_device(gpu_id)
    device = torch.device(f"cuda:{gpu_id}")

    print(f"[GPU {gpu_id}] {torch.cuda.get_device_name(gpu_id)}")

    # --------------------------------
    # 1. 准备计算矩阵
    # --------------------------------
    n = 16384

    a = torch.randn(
        n, n,
        dtype=torch.float16,
        device=device
    )

    b = torch.randn(
        n, n,
        dtype=torch.float16,
        device=device
    )

    # warmup
    for _ in range(5):
        c = torch.mm(a, b)

    torch.cuda.synchronize()

    # --------------------------------
    # 2. 占剩余显存
    # --------------------------------
    free_mem, total_mem = torch.cuda.mem_get_info(device)

    reserve = 2 * 1024**3  # 留 2 GiB
    occupy_bytes = max(0, free_mem - reserve)

    chunks = []
    chunk_size = 1024**3  # 每次分配 1 GiB

    while occupy_bytes > 0:
        current = min(chunk_size, occupy_bytes)

        try:
            x = torch.empty(
                current,
                dtype=torch.uint8,
                device=device
            )
            x.fill_(1)
            chunks.append(x)
            occupy_bytes -= current
        except torch.cuda.OutOfMemoryError:
            break

    torch.cuda.synchronize()

    allocated = torch.cuda.memory_allocated(device) / 1024**3
    total = total_mem / 1024**3

    print(
        f"[GPU {gpu_id}] memory: "
        f"{allocated:.2f}/{total:.2f} GiB"
    )

    # --------------------------------
    # 3. 持续计算
    # --------------------------------
    print(f"[GPU {gpu_id}] full load started")

    while True:
        c = torch.mm(a, b)
        a, c = c, a


def main():
    mp.set_start_method("spawn", force=True)

    processes = []

    for gpu_id in [0, 1]:
        p = mp.Process(
            target=worker,
            args=(gpu_id,)
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()