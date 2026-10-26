"""NVML via its stable C ABI: no nvidia-smi subprocess on every sample."""
import ctypes as c
import time


class Utilization(c.Structure):
    _fields_ = [("gpu", c.c_uint), ("memory", c.c_uint)]


class Memory(c.Structure):
    _fields_ = [("total", c.c_ulonglong), ("free", c.c_ulonglong), ("used", c.c_ulonglong)]


class Nvidia:
    def __init__(self):
        self.lib = None
        self.handle = c.c_void_p()
        self.retry_at = 0
        self.static = None

    def connect(self):
        if self.lib:
            return True
        if time.monotonic() < self.retry_at:
            return False
        self.retry_at = time.monotonic() + 30
        try:
            lib = c.CDLL("libnvidia-ml.so.1")
            if lib.nvmlInit_v2() != 0:
                return False
            if lib.nvmlDeviceGetHandleByIndex_v2(c.c_uint(0), c.byref(self.handle)) != 0:
                lib.nvmlShutdown()
                return False
            self.lib = lib
            return True
        except (OSError, AttributeError):
            return False

    def number(self, method, *extra, typ=c.c_uint):
        output = typ()
        try:
            status = getattr(self.lib, method)(self.handle, *[c.c_uint(x) for x in extra], c.byref(output))
            return output.value if status == 0 else None
        except AttributeError:
            return None

    def disconnect(self):
        """Release the monitoring session while the entire UI is inactive.

        Called on the same single sensor worker as sample(), never concurrently.
        """
        if self.lib:
            self.lib.nvmlShutdown()
        self.lib = None
        self.handle = c.c_void_p()
        self.retry_at = 0
        self.static = None

    def string(self, method, system=False):
        output = c.create_string_buffer(128)
        try:
            args = (output, c.c_uint(128)) if system else (self.handle, output, c.c_uint(128))
            return output.value.decode(errors="replace") if getattr(self.lib, method)(*args) == 0 else None
        except AttributeError:
            return None

    def sample(self, snapshot):
        if not self.connect():
            snapshot.gpu_error = "Sterownik NVIDIA jest niedostępny"
            return
        if self.static is None:
            self.static = (self.string("nvmlDeviceGetName"), self.string("nvmlSystemGetDriverVersion", system=True),
                           self.string("nvmlDeviceGetVbiosVersion"), self.number("nvmlDeviceGetTemperatureThreshold", 1))
        snapshot.gpu_name, snapshot.gpu_driver, snapshot.gpu_vbios, snapshot.gpu_critical = self.static
        snapshot.gpu_temp = self.number("nvmlDeviceGetTemperature", 0)
        power = self.number("nvmlDeviceGetPowerUsage")
        snapshot.gpu_power = None if power is None else power / 1000
        snapshot.gpu_clock = self.number("nvmlDeviceGetClockInfo", 0)
        snapshot.gpu_memory_clock = self.number("nvmlDeviceGetClockInfo", 2)
        snapshot.gpu_pstate = self.number("nvmlDeviceGetPerformanceState")
        limit = self.number("nvmlDeviceGetEnforcedPowerLimit")
        snapshot.gpu_limit = None if limit is None else limit / 1000
        reasons = self.number("nvmlDeviceGetCurrentClocksThrottleReasons", typ=c.c_ulonglong)
        snapshot.gpu_throttled = None if reasons is None else bool(reasons & (0x20 | 0x40))
        snapshot.gpu_power_limited = None if reasons is None else bool(reasons & (0x4 | 0x8 | 0x80))
        utilization, memory = Utilization(), Memory()
        if self.lib.nvmlDeviceGetUtilizationRates(self.handle, c.byref(utilization)) == 0:
            snapshot.gpu_usage = utilization.gpu
        if self.lib.nvmlDeviceGetMemoryInfo(self.handle, c.byref(memory)) == 0:
            snapshot.vram_used = memory.used // 1048576
            snapshot.vram_total = memory.total // 1048576


reader = Nvidia()
