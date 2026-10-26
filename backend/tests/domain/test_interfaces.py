import pytest

from app.domain.interfaces import IUserInterface


def test_iuser_interface_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        IUserInterface()  # type: ignore
