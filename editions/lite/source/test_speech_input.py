import base64
import io
import unittest
import wave
from speech_input import validate_audio


def recording(channels=1, rate=16000, frames=16000):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b'\0\0' * channels * frames)
    return base64.b64encode(stream.getvalue()).decode('ascii')


class AudioValidation(unittest.TestCase):
    def test_pcm_accepted(self):
        self.assertTrue(validate_audio(recording()).startswith(b'RIFF'))

    def test_invalid_encodings_rejected(self):
        for value in [None, '!', base64.b64encode(b'not audio').decode(), 'A' * 2600001]:
            with self.subTest(value=str(value)[:20]), self.assertRaises(ValueError):
                validate_audio(value)

    def test_nonconforming_audio_rejected(self):
        for arguments in [{'channels': 2}, {'rate': 48000}, {'frames': 100}, {'frames': 960001}]:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                validate_audio(recording(**arguments))

    def test_truncated_audio_rejected(self):
        raw = base64.b64decode(recording())[:-20]
        with self.assertRaises(ValueError):
            validate_audio(base64.b64encode(raw).decode())


if __name__ == '__main__':
    unittest.main()
