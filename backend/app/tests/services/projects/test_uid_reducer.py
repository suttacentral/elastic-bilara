from pathlib import Path
from unittest.mock import patch

import pytest


class TestUIDReducer:
    @pytest.mark.parametrize(
        "uids, start_index, end_index, expected",
        [
            (
                [
                    "test:1",
                    "test:2",
                    "test:3",
                    "test:4",
                    "test:5",
                    "test:6",
                    "test:7",
                    "test:8",
                    "test:9",
                ],
                2,
                8,
                True,
            ),
            (
                [
                    "test:1.test",
                    "test:2.test_a",
                    "test:3.test_b",
                    "test:4.test_c",
                    "test:5.test_d",
                    "test:6.test_e",
                    "test:7.test_f",
                    "test:8.test_g",
                    "test:9.test_h",
                ],
                2,
                8,
                True,
            ),
            (
                [
                    "test:1",
                    "test:2",
                    "test:3",
                    "test:6",
                    "test:8",
                    "test:10",
                    "test:11",
                    "test:12",
                    "test:20",
                ],
                2,
                8,
                False,
            ),
            (
                [
                    "test:1.test",
                    "test:2.test_a",
                    "test:3.test_b",
                    "test:5.test_c",
                    "test:12.test_d",
                    "test:13.test_e",
                    "test:20.test_f",
                    "test:30.test_g",
                    "test:100.test_h",
                ],
                2,
                8,
                False,
            ),
        ],
    )
    def test__is_digit_pattern_consistent(self, uid_reducer, uids, start_index, end_index, expected):
        path = Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json")
        reducer_instance, _, _ = uid_reducer(path, uids)
        result = reducer_instance._is_digit_pattern_consistent(uids, start_index, end_index)
        assert result == expected

    @pytest.mark.parametrize(
        "segment_id, data, expected_start_index, expected_end_index, expected_matched_pattern",
        [
            (
                "an1.1:1.2",
                {
                    "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                    "an1.1:0.2": "1. Rūpādivagga ",
                    "an1.1:1.0": "1 ",
                    "an1.1:1.1": "Evaṁ me sutaṁ—",
                    "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                    "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                    "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                    "an1.1:1.5": "Bhagavā etadavoca: ",
                    "an1.1:2.1": "Bhagavā etadavoca: ",
                },
                4,
                7,
                "has_digits_around_dot_pattern",
            ),
            (
                "an1.3:1.0",
                {
                    "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                    "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                    "an1.1:2.3": "Paṭhamaṁ. ",
                    "an1.2:1.1": "“Nāhaṁ, bhikkhave, aññaṁ ekasaddampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthisaddo. ",
                    "an1.2:1.2": "Itthisaddo, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                    "an1.2:1.3": "Dutiyaṁ. ",
                    "an1.3:1.0": "3 ",
                    "an1.3:1.1": "“Nāhaṁ, bhikkhave, aññaṁ ekagandhampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthigandho. ",
                    "an1.3:1.2": "Itthigandho, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                    "an1.3:1.3": "Tatiyaṁ. ",
                    "an1.4:1.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarasampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthiraso. ",
                    "an1.4:1.2": "Itthiraso, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                    "an1.4:1.3": "Catutthaṁ. ",
                    "an1.5:1.0": "5 ",
                    "an1.5:1.1": "“Nāhaṁ, bhikkhave, aññaṁ ekaphoṭṭhabbampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthiphoṭṭhabbo. ",
                },
                6,
                9,
                "has_digits_around_dot_pattern",
            ),
            (
                "test:1",
                {"test:1": "test", "test:2": "test2", "test:3": "test3", "test:4": "test4", "test:5": "test5"},
                0,
                4,
                "starts_with_digit_pattern",
            ),
            (
                "test:2.test_b",
                {
                    "test:1.test_a": "test",
                    "test:2.test_b": "test2",
                    "test:3.test_c": "test3",
                    "test:4.test_d": "test4",
                    "test:5.test_e": "test5",
                },
                1,
                4,
                "starts_with_digit_pattern",
            ),
            (
                "test:10",
                {"test:1": "test", "test:3": "test2", "test:10": "test3", "test:11": "test4", "test:20": "test5"},
                2,
                4,
                "starts_with_digit_pattern",
            ),
            (
                "test:test",
                {"test:test": "test", "abc:abc": "abc", "test_test:test_test": "test2", "def:def": "def"},
                None,
                None,
                None,
            ),
        ],
    )
    def test__get_pattern_boundaries(
        self, uid_reducer, segment_id, data, expected_start_index, expected_end_index, expected_matched_pattern
    ):
        path = Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json")
        reducer_instance, _, _ = uid_reducer(path, [segment_id])
        result = reducer_instance._get_pattern_boundaries(segment_id, data)
        expected_matched_pattern = (
            getattr(reducer_instance, expected_matched_pattern) if expected_matched_pattern else None
        )
        assert result == (expected_start_index, expected_end_index, expected_matched_pattern)

    @pytest.mark.parametrize(
        "segment_id, data, exact, expected_result",
        [
            (
                "an1.1:1.2",
                {
                    "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                    "an1.1:0.2": "1. Rūpādivagga ",
                    "an1.1:1.0": "1 ",
                    "an1.1:1.1": "Evaṁ me sutaṁ—",
                    "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                    "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                    "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                    "an1.1:1.5": "Bhagavā etadavoca: ",
                    "an1.1:2.1": "Bhagavā etadavoca: ",
                },
                False,
                {
                    "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                    "an1.1:0.2": "1. Rūpādivagga ",
                    "an1.1:1.0": "1 ",
                    "an1.1:1.1": "Evaṁ me sutaṁ—",
                    "an1.1:1.2": "Tatra kho bhagavā bhikkhū āmantesi: ",
                    "an1.1:1.3": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                    "an1.1:1.4": "Bhagavā etadavoca: ",
                    "an1.1:2.1": "Bhagavā etadavoca: ",
                },
            ),
            (
                "an1.1:1.2",
                {
                    "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                    "an1.1:0.2": "1. Rūpādivagga ",
                    "an1.1:1.0": "1 ",
                    "an1.1:1.1": "Evaṁ me sutaṁ—",
                    "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                    "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                    "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                    "an1.1:1.5": "Bhagavā etadavoca: ",
                    "an1.1:2.1": "Bhagavā etadavoca: ",
                },
                True,
                {
                    "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                    "an1.1:0.2": "1. Rūpādivagga ",
                    "an1.1:1.0": "1 ",
                    "an1.1:1.1": "Evaṁ me sutaṁ—",
                    "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                    "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                    "an1.1:1.5": "Bhagavā etadavoca: ",
                    "an1.1:2.1": "Bhagavā etadavoca: ",
                },
            ),
            (
                "test:2",
                {"test:1": "test", "test:2": "test2", "test:3": "test3", "test:4": "test4", "test:5": "test5"},
                False,
                {"test:1": "test", "test:2": "test3", "test:3": "test4", "test:4": "test5"},
            ),
            (
                "test:2",
                {"test:1": "test", "test:2": "test2", "test:3": "test3", "test:4": "test4", "test:5": "test5"},
                True,
                {"test:1": "test", "test:3": "test3", "test:4": "test4", "test:5": "test5"},
            ),
            (
                "test:3.test_c",
                {
                    "test:1.test_a": "test",
                    "test:2.test_b": "test2",
                    "test:3.test_c": "test3",
                    "test:4.test_d": "test4",
                    "test:5.test_e": "test5",
                },
                False,
                {
                    "test:1.test_a": "test",
                    "test:2.test_b": "test2",
                    "test:3.test_d": "test4",
                    "test:4.test_e": "test5",
                },
            ),
            (
                "test:3.test_c",
                {
                    "test:1.test_a": "test",
                    "test:2.test_b": "test2",
                    "test:3.test_c": "test3",
                    "test:4.test_d": "test4",
                    "test:5.test_e": "test5",
                },
                True,
                {
                    "test:1.test_a": "test",
                    "test:2.test_b": "test2",
                    "test:4.test_d": "test4",
                    "test:5.test_e": "test5",
                },
            ),
        ],
    )
    def test__reduce(self, uid_reducer, segment_id, data, exact, expected_result):
        path = Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json")
        reducer_instance, _, _ = uid_reducer(path, [segment_id], exact)
        result = reducer_instance._reduce(segment_id, data, path)
        assert result == expected_result

    @pytest.mark.parametrize(
        "uids, exact, existing_json_data, expected_data",
        [
            (
                ["an1.1:1.3"],
                False,
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                        "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.5": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                        "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.5": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                },
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.3": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.4": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.3": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.4": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                },
            ),
            (
                ["an1.1:1.3"],
                True,
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                        "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.5": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.3": "Tatra kho bhagavā bhikkhū āmantesi: ",
                        "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.5": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                },
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.5": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "an1.1:0.1": "Aṅguttara Nikāya 1 ",
                        "an1.1:0.2": "1. Rūpādivagga ",
                        "an1.1:1.0": "1 ",
                        "an1.1:1.1": "Evaṁ me sutaṁ—",
                        "an1.1:1.2": "ekaṁ samayaṁ bhagavā sāvatthiyaṁ viharati jetavane anāthapiṇḍikassa ārāme. ",
                        "an1.1:1.4": "“Bhadante”ti te bhikkhū bhagavato paccassosuṁ. ",
                        "an1.1:1.5": "Bhagavā etadavoca: ",
                        "an1.1:2.1": "“Nāhaṁ, bhikkhave, aññaṁ ekarūpampi samanupassāmi yaṁ evaṁ purisassa cittaṁ pariyādāya tiṭṭhati yathayidaṁ, bhikkhave, itthirūpaṁ. ",
                        "an1.1:2.2": "Itthirūpaṁ, bhikkhave, purisassa cittaṁ pariyādāya tiṭṭhatī”ti. ",
                        "an1.1:2.3": "Paṭhamaṁ. ",
                    },
                },
            ),
            (
                ["test:4"],
                False,
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1": "test",
                        "test:2": "test2",
                        "test:3": "test3",
                        "test:4": "test4",
                        "test:5": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1": "test-root",
                        "test:2": "test2-root",
                        "test:3": "test3-root",
                        "test:4": "test4-root",
                        "test:5": "test5-root",
                    },
                },
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1": "test",
                        "test:2": "test2",
                        "test:3": "test3",
                        "test:4": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1": "test-root",
                        "test:2": "test2-root",
                        "test:3": "test3-root",
                        "test:4": "test5-root",
                    },
                },
            ),
            (
                ["test:4"],
                True,
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1": "test",
                        "test:2": "test2",
                        "test:3": "test3",
                        "test:4": "test4",
                        "test:5": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1": "test-root",
                        "test:2": "test2-root",
                        "test:3": "test3-root",
                        "test:4": "test4-root",
                        "test:5": "test5-root",
                    },
                },
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1": "test",
                        "test:2": "test2",
                        "test:3": "test3",
                        "test:5": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1": "test-root",
                        "test:2": "test2-root",
                        "test:3": "test3-root",
                        "test:5": "test5-root",
                    },
                },
            ),
            (
                ["test:2.test_b"],
                False,
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1.test_a": "test",
                        "test:2.test_b": "test2",
                        "test:3.test_c": "test3",
                        "test:4.test_d": "test4",
                        "test:5.test_e": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1.test_a": "test-root",
                        "test:2.test_b": "test2-root",
                        "test:3.test_c": "test3-root",
                        "test:4.test_d": "test4-root",
                        "test:5.test_e": "test5-root",
                    },
                },
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1.test_a": "test",
                        "test:2.test_c": "test3",
                        "test:3.test_d": "test4",
                        "test:4.test_e": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1.test_a": "test-root",
                        "test:2.test_c": "test3-root",
                        "test:3.test_d": "test4-root",
                        "test:4.test_e": "test5-root",
                    },
                },
            ),
            (
                ["test:1.test_a"],
                True,
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:1.test_a": "test",
                        "test:2.test_b": "test2",
                        "test:3.test_c": "test3",
                        "test:4.test_d": "test4",
                        "test:5.test_e": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:1.test_a": "test-root",
                        "test:2.test_b": "test2-root",
                        "test:3.test_c": "test3-root",
                        "test:4.test_d": "test4-root",
                        "test:5.test_e": "test5-root",
                    },
                },
                {
                    Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json"): {
                        "test:2.test_b": "test2",
                        "test:3.test_c": "test3",
                        "test:4.test_d": "test4",
                        "test:5.test_e": "test5",
                    },
                    Path("root/pli/ms/sutta/test/test1/test1.1_root-pli-ms.json"): {
                        "test:2.test_b": "test2-root",
                        "test:3.test_c": "test3-root",
                        "test:4.test_d": "test4-root",
                        "test:5.test_e": "test5-root",
                    },
                },
            ),
        ],
    )
    @patch("app.services.projects.uid_reducer.get_json_data")
    def test_decrement_dry(self, mock_get_json_data, uid_reducer, uids, exact, existing_json_data, expected_data):
        path = Path("translation/en/test_user/sutta/test/test1/test1.1_translation-en-test_user.json")
        reducer_instance, _, mock_get_matches = uid_reducer(path, uids, exact, set(existing_json_data.keys()))

        def side_effect_helper(arg):
            return existing_json_data.get(arg)

        mock_get_json_data.side_effect = side_effect_helper
        result = reducer_instance.decrement_dry()
        assert result == expected_data
