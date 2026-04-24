import unittest
from modbus_common import decode_register_words, encode_value_to_words, SwapMode

class TestModbusCommon(unittest.TestCase):
    def test_decode_int16(self):
        # 0x0001 -> 1
        val, text = decode_register_words([1], "int16", SwapMode.NONE)
        self.assertEqual(val, 1)
        self.assertEqual(text, "1")

        # 0xFFFF -> -1
        val, text = decode_register_words([0xFFFF], "int16", SwapMode.NONE)
        self.assertEqual(val, -1)
        self.assertEqual(text, "-1")

    def test_decode_uint16(self):
        # 0xFFFF -> 65535
        val, text = decode_register_words([0xFFFF], "uint16", SwapMode.NONE)
        self.assertEqual(val, 65535)
        self.assertEqual(text, "65535")

    def test_decode_float32(self):
        # 1.0 in float32 is 0x3F800000
        val, text = decode_register_words([0x3F80, 0x0000], "float32", SwapMode.NONE)
        self.assertAlmostEqual(val, 1.0)
        self.assertEqual(text, "1.000")

    def test_swap_modes(self):
        # 0x3F80, 0x0000 with Word Swap -> 0x0000, 0x3F80
        val, text = decode_register_words([0x0000, 0x3F80], "float32", SwapMode.WORD)
        self.assertAlmostEqual(val, 1.0)

        # 0x3F80 -> 0x803F (Byte swap)
        # 0x0000 -> 0x0000
        val, text = decode_register_words([0x803F, 0x0000], "float32", SwapMode.BYTE)
        self.assertAlmostEqual(val, 1.0)

    def test_encode_int16(self):
        words = encode_value_to_words(1, "int16", SwapMode.NONE)
        self.assertEqual(words, [1])

        words = encode_value_to_words(-1, "int16", SwapMode.NONE)
        self.assertEqual(words, [0xFFFF])

    def test_encode_float32(self):
        words = encode_value_to_words(1.0, "float32", SwapMode.NONE)
        self.assertEqual(words, [0x3F80, 0x0000])

    def test_string_handling(self):
        # "ABC" -> [0x4142, 0x4300, 0x0000, 0x0000, 0x0000] (string10 = 5 regs)
        words = encode_value_to_words("ABC", "string10", SwapMode.NONE)
        self.assertEqual(len(words), 5)
        self.assertEqual(words[0], 0x4142)
        self.assertEqual(words[1], 0x4300)

        val, text = decode_register_words(words, "string10", SwapMode.NONE)
        self.assertEqual(val, "ABC")
        self.assertEqual(text, "ABC")

if __name__ == "__main__":
    unittest.main()
