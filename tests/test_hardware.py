from nitrosense.hardware import AN515_55


def test_an515_55_profile_is_complete():
    assert AN515_55.cpu_fan_mode == 0x22
    assert AN515_55.gpu_fan_mode == 0x21
    assert AN515_55.cpu_temp == 0xB0
    assert AN515_55.gpu_temp == 0xB6
