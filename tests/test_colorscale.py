from app.dashboard.colorscale import sequential_color


def test_endpoints_match_documented_ramp_steps():
    bg_low, _ = sequential_color(0)
    bg_high, _ = sequential_color(100)
    assert bg_low == "#cde2fb"  # Rampenstufe 100
    assert bg_high == "#0d366b"  # Rampenstufe 700


def test_color_darkens_monotonically_with_percent():
    def luminance(hex_color):
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    luminances = [luminance(sequential_color(p)[0]) for p in range(0, 101, 10)]
    assert luminances == sorted(luminances, reverse=True)


def test_text_color_is_readable_against_background():
    for percent in range(0, 101, 5):
        bg, text = sequential_color(percent)
        assert text in ("#0b0b0b", "#ffffff")


def test_out_of_range_percent_is_clamped():
    assert sequential_color(-10) == sequential_color(0)
    assert sequential_color(150) == sequential_color(100)
