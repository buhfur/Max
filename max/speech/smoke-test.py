#!/usr/bin/env python3 


from faster_whisper import WhisperModel
model = WhisperModel("tiny", device="cuda", compute_type="float16")
print(model.backend) # Should indicate active acceleration, not CPU fall
