"""Preset registry tests."""

import pytest

from gdcfetch.presets import get_preset, list_presets


def test_all_presets_have_search_kwargs():
    for name, preset in list_presets().items():
        kwargs = preset.search_kwargs()
        assert kwargs["data_type"], name
        assert kwargs["access"] in ("open", "controlled")


def test_somatic_mutations_covers_three_signature_classes():
    preset = get_preset("somatic-mutations")
    assert set(preset.signature_classes) == {"SBS", "DBS", "ID"}
    assert preset.access == "open"


def test_structural_variants_flagged_controlled():
    preset = get_preset("structural-variants")
    assert preset.access == "controlled"
    assert preset.signature_classes == ("SV",)


def test_gene_expression_is_covariate_not_signature():
    preset = get_preset("gene-expression")
    assert preset.is_covariate
    assert preset.signature_classes == ()


def test_unknown_preset_lists_available():
    with pytest.raises(ValueError, match="somatic-mutations"):
        get_preset("nope")


def test_list_presets_is_a_copy():
    presets = list_presets()
    presets.pop("somatic-mutations")
    assert "somatic-mutations" in list_presets()
