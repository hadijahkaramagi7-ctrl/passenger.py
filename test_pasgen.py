import string
import pytest
from passgen import generate, build_alphabet, AMBIGUOUS


def test_length():
    pw = generate(24, ["lower", "upper", "digits", "symbols"], False)
    assert len(pw) == 24


def test_contains_each_selected_set():
    pw = generate(16, ["lower", "upper", "digits", "symbols"], False)
    assert any(c in string.ascii_lowercase for c in pw)
    assert any(c in string.ascii_uppercase for c in pw)
    assert any(c in string.digits for c in pw)
    assert any(c not in string.ascii_letters + string.digits for c in pw)


def test_no_ambiguous():
    alphabet = build_alphabet(True)
    for chars in alphabet.values():
        assert not (set(chars) & AMBIGUOUS)


def test_too_short_raises():
    with pytest.raises(ValueError):
        generate(2, ["lower", "upper", "digits"], False)


def test_uniqueness():
    passwords = {generate(20, ["lower", "upper", "digits", "symbols"], False)
                 for _ in range(50)}
    assert len(passwords) == 50
