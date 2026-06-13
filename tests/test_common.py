from pdftranslate.common import color_int_to_rgb, looks_untranslatable


def test_color_white():
    assert color_int_to_rgb(0xFFFFFF) == (1.0, 1.0, 1.0)


def test_color_black():
    assert color_int_to_rgb(0) == (0.0, 0.0, 0.0)


def test_color_red():
    assert color_int_to_rgb(0xFF0000) == (1.0, 0.0, 0.0)


def test_untranslatable_blank():
    assert looks_untranslatable("   ") is True


def test_untranslatable_bare_number():
    assert looks_untranslatable("12") is True


def test_untranslatable_equation():
    assert looks_untranslatable("x = a^2 + b^2") is True


def test_translatable_sentence():
    assert looks_untranslatable("This is a normal sentence.") is False


def test_translatable_heading():
    assert looks_untranslatable("3. Methodology and Results") is False
