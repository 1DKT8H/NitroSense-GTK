from unittest.mock import patch, call
import pytest
from nitrosense.hardware import AN515_55
from nitrosense.helper import perform


@pytest.mark.parametrize("target,register,mode,value", [
    ("cpu", 0x22, "auto", 0x04), ("gpu", 0x21, "auto", 0x10),
    ("cpu", 0x22, "max", 0x08), ("gpu", 0x21, "max", 0x20)])
def test_firmware_modes_do_not_write_a_manual_speed(target, register, mode, value):
    with patch("nitrosense.helper.detect_profile", return_value=AN515_55), patch("nitrosense.helper.write_ec") as write:
        perform({"action": "fan", "target": target, "mode": mode})
        write.assert_called_once_with(register, value)


def test_manual_percentage_is_staged_before_mode():
    with patch("nitrosense.helper.detect_profile", return_value=AN515_55), patch("nitrosense.helper.write_ec") as write:
        perform({"action": "fan", "target": "cpu", "mode": "manual", "speed": 55})
        assert write.call_args_list == [call(0x37, 55), call(0x22, 0x0C)]


@pytest.mark.parametrize("speed", [-1, 0, 101, 255, True, "50"])
def test_invalid_speed_never_writes(speed):
    with patch("nitrosense.helper.detect_profile", return_value=AN515_55), patch("nitrosense.helper.write_ec") as write:
        with pytest.raises(SystemExit):
            perform({"action": "fan", "target": "gpu", "mode": "manual", "speed": speed})
        write.assert_not_called()
