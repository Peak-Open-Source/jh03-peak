import logging
import unittest
logger = logging.getLogger(__name__)

import math

from src.database_entries.pdbe_entry import *
logging.getLogger("src.PDBeEntry").setLevel(logging.ERROR) # Disable warnings in PDBeEntry class

pdbe_weights["method_multiplier"]["x-ray"] = 0.8

test_entry = PDBeEntry({'id': '6II1', 'method': 'X-ray', 'resolution': '1.34 A', 'chains': 'B/D=1-145', 'protein_metadata': {'mass':15389, 'sequence_length':145, 'sequence': 'MVLSAADKGNVKAAWGKVGGHAAEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGAKVAAALTKAVEHLDDLPGALSELSDLHAHKLRVDPVNFKLLSHSLLVTLASHLPSDFTPAVHASLDKFLANVSTVLTSKYRPSD'}})

class TestPDBeEntry(unittest.TestCase):    
    def test_resolution_extraction(self):
        DEFAULT_RESOLUTION_SCORE = 0.1
        test_cases = [ # List of (input, expected_output, error message fragment) tuples
            ("1.34 A", 1.34, "valid float"),
            ("7 A", 7, "valid int"),
            ("1.34a A", DEFAULT_RESOLUTION_SCORE, "corrupted input"),
            ("1.34", DEFAULT_RESOLUTION_SCORE, "corrupted input"),
            ("1.34A", DEFAULT_RESOLUTION_SCORE, "corrupted input"),
            (".7 A", DEFAULT_RESOLUTION_SCORE, "corrupted input"),
            ("", DEFAULT_RESOLUTION_SCORE, "empty input"),
        ]
        for test_case in test_cases:
            test_entry.entry_data["resolution"] = test_case[0]
            val = test_entry.extract_resolution()
            self.assertEqual(val, test_case[1], f"Failed to parse {test_case[2]} correctly, expected {test_case[1]}, got {val}")

    def test_method_extraction(self):
        DEFAULT_METHOD_SCORE = 0.1
        test_cases = [ # List of (input, expected_output, error message fragment) tuples
            ("X-ray", "X-ray", "valid input"),
            ("othermethod", "othermethod", "valid input not in weights dictionary"),
            ("", None, "missing method")
        ]
        for test_case in test_cases:
            test_entry.entry_data["method"] = test_case[0]
            val = test_entry.extract_method()
            self.assertEqual(val, test_case[1], f"Failed to parse {test_case[2]} correctly, expected {test_case[1]}, got {val}")

        logger.warning("Partially implemented: need to implement more tests for extracting valid methods")

    def test_chain_length_extraction(self):
        DEFAULT_CHAIN_LENGTH_SCORE = 0.1
        test_cases = [ # List of (input, expected_output) tuples
            ("B/D=1-145", 145),
            ("B/D=73-100", 28),
            ("C/E=73-100", 28),
            ("C/E=100-73", 28), # Reverse ordering should still give positive value
            ("F=73-100", 28),
            ("A=1-23, B=50-79", 53),
            ("A=1-23,B=50-79", 53),
            ("A=1-23,       B=50-79", 53),
            ("A/B=1-23, C/D=50-79", 53),
            ("A=1-23, C/D=50-79", 53),
            ("A/B=1-23, D=50-79", 53),
            # Invalid / partially cases
            ("", DEFAULT_CHAIN_LENGTH_SCORE),
            ("B/D73-100", DEFAULT_CHAIN_LENGTH_SCORE),
            ("A=1, B=3", DEFAULT_CHAIN_LENGTH_SCORE),
            ("B/D=73100", DEFAULT_CHAIN_LENGTH_SCORE),
            ("A=1-28, B=3", 28),
        ] 
        for test_case in test_cases:
            test_entry.entry_data["chains"] = test_case[0]
            self.assertEqual(test_entry.extract_chain_length(), test_case[1], f"Failed to extract chain length from {test_case[0]}")

    def test_full_chain_length_extraction(self):
        logger.warning("Not Implemented: extraction of full protein chain length from metadata.")
        test_cases = [ # List of (protein metadata dict, expected output, error message fragment) tuples
            ({"sequence":"", "sequence_length":"0"}, 0, "0-length input"),
            ({"sequence":"A", "sequence_length":"1"}, 1, "1-length input"),
            ({"sequence":"DKAMFOWEMVLA", "sequence_length":"12"}, 12, "input"),
            ({"sequence":"", "sequence_length":"12"}, 12, "missing sequence data"),
            ({"sequence":"DKAMFOWEMVLA"}, 12, "missing reported sequence length data"),
            ({"sequence":"DKAMFOWEMVLA", "sequence_length":"na"}, 12, "corrupted reported sequence length data"),
            ({"sequence":"DKAMFOWEMVLA", "sequence_length":""}, 12, "corrupted reported sequence length data"),
            ({"sequence":"DKAMFOWEMVLA", "sequence_length":"0"}, 12, "mismatch between sequence and reported sequence length"),
            ({"sequence":"DKAMFOWEMVLA", "sequence_length":"10"}, 12, "mismatch between sequence and reported sequence length"),
            ({"sequence":"DKAMFOWEMVLA", "sequence_length":"20"}, 20, "mismatch between sequence and reported sequence length"),
            ({"sequence":"PQRMCUWEXI"*1000, "sequence_length":"10000"}, 10_000, "large input"),
            ({"sequence":"PQRMCUWEXI"*10000, "sequence_length":"100000"}, 100_000, "very large input"),
        ]

        for test_case in test_cases:
            test_entry.entry_data["protein_metadata"] = test_case[0]
            val = test_entry.extract_full_chain_length()
            self.assertEqual(val, test_case[1], f"Failed to handle {test_case[2]}, expected {test_case[1]}, got {val}.")

    def test_resolution_score_calculation(self):
        DEFAULT = pdbe_weights["resolution"]["default"]

        def test_vals (test_cases, precision=10):
            output = test_entry.calculate_resolution_score(None)
            self.assertEqual(output, DEFAULT, f"Failed to return default value on invalid resolution data, got {output}")
            for test_val, expected_output in test_cases:
                output = test_entry.calculate_resolution_score(test_val)
                self.assertAlmostEqual(output, expected_output, places=precision, msg=f"Failed to handle resolution of {test_val}, expected {expected_output}, got {output}")
        

        test_vals([]) # Just test for invalid value handling
        test_range = [i/10 for i in range(0, 100)]

        # Test linear weights scoring
        pdbe_weights["resolution"]["interpolation"] = "linear"
        pdbe_weights["resolution"]["weight_at_1"] = 0.5
        test_vals([(x, max(0, (pdbe_weights["resolution"]["weight_at_1"] - 1)*x +1)) for x in test_range]) # Value for any given x should be y=mx + 1, where m is the gradient, restricted to the value range 0-1
        pdbe_weights["resolution"]["weight_at_1"] = 0.9
        test_vals([(x, max(0,(pdbe_weights["resolution"]["weight_at_1"] - 1)*x +1)) for x in test_range]) # Value for any given x should be y=mx + 1, where m is the gradient, restricted to the value range 0-1
        pdbe_weights["resolution"]["weight_at_1"] = 0.99
        test_vals([(x, max(0,(pdbe_weights["resolution"]["weight_at_1"] - 1)*x +1)) for x in test_range]) # Value for any given x should be y=mx + 1, where m is the gradient, restricted to the value range 0-1
        
        # Test exponential weights scoring
        pdbe_weights["resolution"]["interpolation"] = "exponential"
        pdbe_weights["resolution"]["weight_at_1"] = 0.5
        test_vals([(0,1), (0.25,0.841), (0.5,0.707), (1,0.5), (1.5, 0.354), (5, 0.031), (10, 0.001), (15, 0.000)], precision=3) # Value for x should follow exponential decay curve (test val is correct to within 3 d.p.)
        pdbe_weights["resolution"]["weight_at_1"] = 0.9
        test_vals([(x, max(0,math.e**(math.log(pdbe_weights["resolution"]["weight_at_1"])*x))) for x in test_range]) # Value for any given x should follow an exponential decay curve based on weight at 1
        pdbe_weights["resolution"]["weight_at_1"] = 0.99
        test_vals([(x, max(0,math.e**(math.log(pdbe_weights["resolution"]["weight_at_1"])*x))) for x in test_range]) # Value for any given x should follow an exponential decay curve based on weight at 1
        
    def test_method_score_calculation(self):
        DEFAULT = pdbe_weights["method_multiplier"]["default"]
        test_cases = [(method, weight, f"valid input") for method, weight in pdbe_weights["method_multiplier"].items()]  # List of (input method, expected output, error message fragment) tuples
        test_cases += [
            ("x-ray", pdbe_weights["method_multiplier"]["x-ray"], "valid (lowercase) input"),
            ("X-RAY", pdbe_weights["method_multiplier"]["x-ray"], "valid (uppercase) input"),

            ("F12ioe", DEFAULT, "corrupted input"),
            ("X-rayz", DEFAULT, "corrupted input"),
            ("     ", DEFAULT, "whitespace input"),
            ("", DEFAULT, "missing input"),
        ]

        for test_case in test_cases:
            output = test_entry.calculate_method_score(test_case[0])
            self.assertEqual(output, test_case[1], f"Failed to extract chain length from {test_case[2]}: {test_case[0]}, expected {test_case[1]}, got {output}")

    def test_chain_length_score_calculation(self):
        DEFAULT = pdbe_weights["default_chain_length_score"]
        test_cases = [ # List of (record chain length, whole protein chain length, expected score) tuples
            (0, 762, 0.0),
            (0, 1, 0.0),
            (23, 23, 1.0),
            (2839, 2839, 1.0),
            (10, 100, 0.1),
            (234, 1000, 0.234),
            (35, 70, 0.5),
            (0, 0, DEFAULT), # Should not crash!
            (1, 0, DEFAULT),
            (37, 0, DEFAULT),
            (-35, 70, 0.5),
            (35, -70, 0.5),
            (-35, -70, 0.5),
            (None, 38, DEFAULT),
            (918, None, DEFAULT),
            (None, None, DEFAULT),
        ]
        test_cases += [(x, y, x/y) for x in range(1,30) for y in range(1,30)]
        for test_case in test_cases:
            output = test_entry.calculate_chain_length_score(test_case[0], test_case[1])
            self.assertEqual(output, test_case[2], f"Failed to extract chain length from chain-length={test_case[0]}, whole-protein-length={test_case[1]}, expected {test_case[2]}, got {output}")

    def test_fetch(self):
        def get_output(metadata_dict):
            test_entry = PDBeEntry(metadata_dict)
            return test_entry.fetch()
        self.assertEqual(len(get_output({'id': '1fsx'})), 440235, "Mismatching pdb file lengths for pdb-id 1sfx")
        

    # def test_overall_score_calculation(self):
    #     #pass

if __name__ == "__main__":
    unittest.main()
