from nitrosense.telemetry import Snapshot, parse_nvidia


def test_missing_gpu_power_keeps_other_fields():
    snap = Snapshot()
    parse_nvidia("RTX 2060, 62, [N/A], 1500, 73, 4000, 6144, 90, 580.82, 90.06.00", snap)
    assert snap.gpu_power is None
    assert snap.gpu_usage == 73
    assert snap.vram_used == 4000
    assert snap.gpu_driver == "580.82"
    assert snap.gpu_limit == 90


def test_zero_is_not_missing():
    snap = Snapshot()
    parse_nvidia("RTX 2060, 40, 0, 0, 0, 0, 6144, 90, 580, bios", snap)
    assert snap.gpu_power == 0
    assert snap.gpu_usage == 0
    assert snap.vram_used == 0


def test_failed_driver_response_is_not_a_gpu_name():
    snap = Snapshot()
    parse_nvidia("NVIDIA-SMI has failed", snap)
    assert snap.gpu_name is None
    assert snap.gpu_error
