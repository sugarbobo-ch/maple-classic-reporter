from __future__ import annotations

import unittest

from maple_reporter.recorder.audio_capture import (
    AudioCaptureError,
    ProcessLoopbackAudioRecorder,
    create_audio_recorder,
    normalize_audio_capture_mode,
)


class ProcessAudioCaptureTests(unittest.TestCase):
    def test_legacy_boolean_modes_are_normalized(self):
        self.assertEqual(normalize_audio_capture_mode(None, record_audio=False), "off")
        self.assertEqual(normalize_audio_capture_mode(None, record_audio=True), "system")
        self.assertEqual(normalize_audio_capture_mode("process"), "process")

    def test_off_mode_does_not_create_a_recorder(self):
        self.assertIsNone(create_audio_recorder("off", buffer_seconds=3))

    def test_process_mode_requires_a_target_process(self):
        with self.assertRaises(AudioCaptureError):
            create_audio_recorder("process", buffer_seconds=3)

    def test_process_mode_creates_process_tree_recorder(self):
        recorder = create_audio_recorder(
            "process", buffer_seconds=3, process_id=1234, source_name="Game"
        )
        self.assertIsInstance(recorder, ProcessLoopbackAudioRecorder)
        self.assertEqual(recorder.process_id, 1234)


if __name__ == "__main__":
    unittest.main()
